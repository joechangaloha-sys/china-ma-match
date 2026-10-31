import time
from datetime import timedelta
import pytest
import pyotp
from cryptography.fernet import Fernet
from sqlalchemy import select
from mamatch import auth, config, mfa
from mamatch.models import MfaChallenge, User


@pytest.fixture
def personal(seeded, monkeypatch):
    monkeypatch.setattr(config, 'MFA_ENCRYPTION_KEY', Fernet.generate_key().decode())
    return auth.create_user(seeded, email='personal@example.test', password='test-password-long', role='deal_manager')


def enroll(seeded, personal):
    token = mfa.begin(seeded, personal, enrollment=True)
    item, _ = mfa.challenge(seeded, token)
    secret = mfa.secret_for(item, personal)
    result = mfa.verify(seeded, token, pyotp.TOTP(secret).now())
    assert result and result[0] == personal
    return secret, result[2]


def test_enrollment_encrypts_seed_requires_proof_and_revokes_old_sessions(seeded, personal):
    old = auth.start_session(seeded, personal); seeded.flush()
    token = mfa.begin(seeded, personal, enrollment=True)
    item, _ = mfa.challenge(seeded, token)
    secret = mfa.secret_for(item, personal)
    assert secret not in item.pending_secret
    assert not personal.mfa_secret
    assert mfa.verify(seeded, token, 'wrong') is None
    result = mfa.verify(seeded, token, pyotp.TOTP(secret).now())
    assert len(result[2]) == 10 and secret not in personal.mfa_secret
    assert not any(c in personal.mfa_recovery_hashes for c in result[2])
    assert auth.user_for_token(seeded, old) is None
    assert not mfa.challenge(seeded, token)[0]
    with pytest.raises(ValueError):
        auth.start_session(seeded, personal)
    token = auth.start_session(seeded, personal, mfa_verified=True);seeded.flush()
    assert auth.user_for_token(seeded, token) == personal


def test_codes_cannot_replay_and_recovery_consumed_once(seeded, personal, monkeypatch):
    secret, codes = enroll(seeded, personal)
    token = mfa.begin(seeded, personal)
    assert mfa.verify(seeded, token, pyotp.TOTP(secret).now()) is None
    future = time.time() + 60
    monkeypatch.setattr(mfa.time, 'time', lambda: future)
    assert mfa.verify(seeded, token, pyotp.TOTP(secret).at(future))
    token = mfa.begin(seeded, personal)
    assert mfa.verify(seeded, token, codes[0])
    token = mfa.begin(seeded, personal)
    assert mfa.verify(seeded, token, codes[0]) is None


def test_expired_attempt_limited_and_account_throttled(seeded, personal):
    token = mfa.begin(seeded, personal)
    item, _ = mfa.challenge(seeded, token)
    item.expires_at = mfa.now() - timedelta(seconds=1)
    assert mfa.verify(seeded, token, '000000') is None
    for _ in range(2):
        token = mfa.begin(seeded, personal)
        for _ in range(5):
            assert mfa.verify(seeded, token, 'wrong') is None
        assert mfa.challenge(seeded, token)[0] is None
    with pytest.raises(ValueError):
        mfa.begin(seeded, personal)


def test_required_mfa_never_issues_password_session_for_personal_users(seeded, personal, monkeypatch):
    monkeypatch.setattr(config, 'MFA_REQUIRED', True)
    monkeypatch.setattr(config, 'DEMO_MODE', True)
    assert mfa.required(personal)
    with pytest.raises(ValueError):
        auth.start_session(seeded, personal)
    demo = seeded.scalar(select(User).where(User.email == 'dm@demo.mamatch.test'))
    assert demo.is_demo and not mfa.required(demo)
    with pytest.raises(ValueError):
        mfa.begin(seeded, demo, enrollment=True)
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    assert mfa.required(demo)


def test_no_key_fails_closed(seeded, personal, monkeypatch):
    monkeypatch.setattr(config, 'MFA_ENCRYPTION_KEY', '')
    assert not mfa.available()
    with pytest.raises(ValueError):
        mfa.begin(seeded, personal)


def test_activation_tokens_redacted_in_access_logs():
    import logging
    from mamatch.logging_security import SensitivePathFilter
    record = logging.LogRecord('uvicorn.access',20,'',0,'%s - "%s %s HTTP/%s" %d',
        ('127.0.0.1','GET','/zh/account/activate/private-token','1.1',200),None)
    assert SensitivePathFilter().filter(record)
    assert 'private-token' not in record.getMessage() and '[redacted]' in record.getMessage()


@pytest.mark.parametrize('value', ['//external.test', '/\\external.test', '/ok\r\nLocation: bad', '/'+'x'*501])
def test_mfa_destination_is_same_site_only(seeded, personal, value):
    assert not mfa.safe_path(value)
    token = mfa.begin(seeded, personal, value)
    item, _ = mfa.challenge(seeded, token)
    assert item.next_path == '/'
