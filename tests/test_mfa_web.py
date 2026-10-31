import re
import pytest
import pyotp
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from mamatch import auth, config, db, mfa
from mamatch.models import MfaChallenge, User, UserSession
from test_web import app, client, DM, BrowserClient


@pytest.fixture
def policy(app, db_url, monkeypatch):
    monkeypatch.setattr(config, 'MFA_REQUIRED', True)
    monkeypatch.setattr(config, 'MFA_ENABLED', True)
    monkeypatch.setattr(config, 'MFA_ENCRYPTION_KEY', Fernet.generate_key().decode())
    # Shared seed exemptions exist only inside an explicit fictional-data demo.
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    with db.session_scope(db_url) as s:
        auth.create_user(s, email='personal@example.test', password='long-test-password', role='deal_manager')
    return app


def test_password_only_session_is_never_created_and_enrollment_requires_csrf(policy, db_url):
    c = BrowserClient(policy)
    r = c.post('/en/login', data={'email':'personal@example.test', 'password':'long-test-password'}, follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/en/mfa/challenge'
    assert c.cookies.get('mm_mfa') and not c.cookies.get('mm_session')
    assert c.get('/en/internal/readiness', follow_redirects=False).status_code == 303
    page = c.get('/en/mfa/challenge')
    assert 'data:image/svg+xml' in page.text and 'Set up authenticator' in page.text
    assert page.headers['cache-control'] == 'no-store'
    assert page.headers['referrer-policy'] == 'no-referrer'
    with db.session_scope(db_url) as s:
        item, user = mfa.challenge(s, c.cookies.get('mm_mfa'))
        secret = mfa.secret_for(item, user)
        assert not s.scalars(select(UserSession).where(UserSession.user_id == user.id)).all()
    raw = TestClient(policy); raw.cookies.update(c.cookies)
    assert raw.post('/mfa/challenge', data={'code':'000000'}).status_code == 403
    result = c.post('/en/mfa/challenge', data={'code':pyotp.TOTP(secret).now()})
    assert 'MFA is enabled' in result.text and c.cookies.get('mm_session')
    assert not c.cookies.get('mm_mfa')
    codes = re.findall(r'<code>([a-f0-9]{20})</code>', result.text)
    assert len(codes) == 10 and secret not in result.text
    assert c.get('/en/internal/readiness').status_code == 200
    c.post('/logout')
    c.post('/en/login', data={'email':'personal@example.test', 'password':'long-test-password'})
    assert not c.cookies.get('mm_session')
    assert c.get('/en/internal/readiness', follow_redirects=False).status_code == 303
    assert c.post('/en/mfa/challenge', data={'code':codes[0]}).status_code == 200
    assert c.get('/en/internal/readiness').status_code == 200
    c.post('/logout')
    c.post('/en/login', data={'email':'personal@example.test', 'password':'long-test-password'})
    c.post('/en/mfa/challenge', data={'code':codes[0]})
    assert not c.cookies.get('mm_session')


def test_personal_invite_single_use_and_mfa_gated(policy, db_url):
    with db.session_scope(db_url) as s:
        token = mfa.invite(s, 'new-manager@example.test')
    c = BrowserClient(policy)
    assert c.get('/en/account/activate/'+token).status_code == 200
    c.post('/en/account/activate/'+token, data={'password':'new-manager-password'})
    assert c.cookies.get('mm_mfa') and not c.cookies.get('mm_session')
    assert c.get('/internal/readiness', follow_redirects=False).status_code == 303
    assert c.get('/account/activate/'+token, follow_redirects=False).headers['location'] == '/login'


def test_required_policy_also_gates_public_registration(policy):
    c = BrowserClient(policy)
    c.post('/en/register', data={'email':'new-buyer@example.test','password':'buyer-long-password','name':'Buyer','consent':'1'})
    assert c.cookies.get('mm_mfa') and not c.cookies.get('mm_session')
    assert c.get('/buyer', follow_redirects=False).status_code == 303


def test_staged_mfa_has_no_live_routes_or_navigation(app, monkeypatch):
    monkeypatch.setattr(config, 'MFA_ENABLED', False)
    c = client(app, DM)
    for path in ['/account/mfa','/mfa/challenge','/account/activate/unused']:
        assert c.get(path).status_code == 404
    assert c.post('/account/mfa/enroll',data={'password':'unused'}).status_code == 404
    for path in ['/en/internal/readiness','/zh/account/sessions']:
        assert '/account/mfa' not in c.get(path).text
