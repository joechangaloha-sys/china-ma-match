"""MFA bootstrap is a limited challenge, never an authenticated business session."""
import io
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session
import segno
from cryptography.fernet import InvalidToken
from .. import auth, config, mfa
from ..models import AccountInvite, User
from .common import COOKIE, back, current_user, get_session, render

def feature_enabled():
    if not config.MFA_ENABLED:
        raise HTTPException(404, 'Not found')


router = APIRouter(dependencies=[Depends(feature_enabled)])


def page(request, name, user=None, **ctx):
    response = render(request, name, user, omit_profile_name=True, **ctx)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; form-action 'self'; frame-ancestors 'none'"
    return response


@router.get('/account/mfa', response_class=HTMLResponse)
def settings(request: Request, user: User | None = Depends(current_user)):
    if not user:
        return RedirectResponse('/login', status_code=303)
    return page(request, 'mfa_settings.html', user, portal='internal' if user.role == 'deal_manager' else user.role,
                enabled=bool(user.mfa_secret), demo=config.DEMO_MODE and user.is_demo, available=mfa.available())


@router.post('/account/mfa/enroll')
def enroll(request: Request, password: str = Form(''), user: User | None = Depends(current_user), s: Session = Depends(get_session)):
    if not user:
        return RedirectResponse('/login', status_code=303)
    if auth.authenticate(s, user.email, password) != user:
        return back('/account/mfa', '密码不正确。 Incorrect password.')
    try:
        token = mfa.begin(s, user, '/account/mfa', enrollment=True)
    except ValueError:
        return back('/account/mfa', '请使用个人账户，或联系管理员。 Use a personal account or contact your administrator.')
    response = RedirectResponse('/mfa/challenge', status_code=303)
    response.delete_cookie(COOKIE)
    response.set_cookie('mm_mfa', token, httponly=True, samesite='strict', secure=request.url.scheme == 'https', max_age=300)
    return response


def challenge_page(request, s, failed=False):
    item, user = mfa.challenge(s, request.cookies.get('mm_mfa'))
    if not item:
        return RedirectResponse('/login', status_code=303)
    qr = ''
    if item.purpose == 'enroll':
        try:
            import pyotp
            uri = pyotp.TOTP(mfa.secret_for(item, user)).provisioning_uri(name=user.email, issuer_name='mamatch')
            # Generated locally; no third-party QR endpoint ever receives the seed.
            qr = segno.make(uri).svg_data_uri(scale=4)
        except (ValueError, TypeError, InvalidToken):
            return RedirectResponse('/login', status_code=303)
    return page(request, 'mfa_challenge.html', portal='public', enrolling=item.purpose == 'enroll', qr=qr, failed=failed)


@router.get('/mfa/challenge', response_class=HTMLResponse)
def prompt(request: Request, s: Session = Depends(get_session)):
    return challenge_page(request, s)


@router.post('/mfa/challenge')
def complete(request: Request, code: str = Form(''), s: Session = Depends(get_session)):
    result = mfa.verify(s, request.cookies.get('mm_mfa'), code)
    if not result:
        return challenge_page(request, s, True)
    user, destination, codes = result
    token = auth.start_session(s, user, mfa_verified=True)
    response = page(request, 'mfa_recovery.html', user, portal='public', codes=codes, destination=destination) if codes else RedirectResponse(destination, status_code=303)
    response.delete_cookie('mm_mfa')
    response.set_cookie(COOKIE, token, httponly=True, samesite='lax', secure=request.url.scheme == 'https', max_age=auth.SESSION_HOURS * 3600)
    return response


def invitation(s, token):
    row = s.get(AccountInvite, mfa.digest(token))
    return row if row and not row.consumed and mfa.aware(row.expires_at) > mfa.now() else None


@router.get('/account/activate/{token}', response_class=HTMLResponse)
def activate_page(token: str, request: Request, s: Session = Depends(get_session)):
    if not invitation(s, token):
        return RedirectResponse('/login', status_code=303)
    return page(request, 'account_activate.html', portal='public', token=token)


@router.post('/account/activate/{token}')
def activate(token: str, request: Request, password: str = Form(''), s: Session = Depends(get_session)):
    row = invitation(s, token)
    if not row or not mfa.available():
        return RedirectResponse('/login', status_code=303)
    try:
        user = auth.create_user(s, email=row.email, password=password, role=row.role)
    except ValueError:
        return page(request, 'account_activate.html', portal='public', token=token, failed=True)
    used = s.execute(update(AccountInvite).execution_options(synchronize_session='fetch').where(AccountInvite.token_hash == row.token_hash,
        AccountInvite.consumed == False).values(consumed=True).returning(AccountInvite.token_hash)).first()
    if not used:
        s.rollback()
        return RedirectResponse('/login', status_code=303)
    auth.log(s, user, 'personal_account_activated')
    # Personal administrators enroll before obtaining any application session, regardless of runtime policy.
    token = mfa.begin(s, user, '/internal/readiness', enrollment=True)
    response = RedirectResponse('/mfa/challenge', status_code=303)
    response.delete_cookie(COOKIE)
    response.set_cookie('mm_mfa', token, httponly=True, samesite='strict', secure=request.url.scheme == 'https', max_age=300)
    return response
