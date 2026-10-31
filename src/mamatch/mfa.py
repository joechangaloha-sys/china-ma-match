"""Password-first TOTP challenges, encrypted seeds and single-use recovery codes."""
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, update, func
from . import auth, config
from .models import AccountInvite, AuditEvent, MfaChallenge, User


def now():
    return datetime.now(timezone.utc)


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def cipher():
    return Fernet(config.MFA_ENCRYPTION_KEY.encode())


def available():
    try:
        cipher()
        return True
    except (ValueError, TypeError):
        return False


def required(user):
    return bool(user.mfa_secret or (config.MFA_REQUIRED and not (config.DEMO_MODE and user.is_demo)))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def blocked(session, user):
    return session.scalar(select(func.count(AuditEvent.id)).where(
        AuditEvent.user_id == user.id, AuditEvent.action == 'mfa_failed',
        AuditEvent.created_at >= now() - timedelta(minutes=15))) >= 10


def safe_path(value):
    return (isinstance(value, str) and value.startswith('/') and not value.startswith('//')
            and len(value) <= 500 and '\\' not in value and not any(ord(c) < 32 for c in value))


def begin(session, user, next_path='/', enrollment=False):
    if not available() or not user.active or blocked(session, user):
        raise ValueError('MFA unavailable')
    if enrollment and (user.mfa_secret or (config.DEMO_MODE and user.is_demo)):
        raise ValueError('Use a personal account for enrollment')
    token = secrets.token_urlsafe(32)
    purpose = 'enroll' if not user.mfa_secret else 'verify'
    session.add(MfaChallenge(token_hash=digest(token), user_id=user.id, purpose=purpose,
                pending_secret=cipher().encrypt(pyotp.random_base32().encode()).decode() if purpose == 'enroll' else '',
                next_path=next_path if safe_path(next_path) else '/',
                expires_at=now() + timedelta(minutes=5)))
    session.flush()
    return token


def challenge(session, token):
    item = session.get(MfaChallenge, digest(token)) if token else None
    if not item or item.consumed or item.attempts >= 5 or aware(item.expires_at) <= now():
        return None, None
    user = session.get(User, item.user_id)
    if not user or not user.active or blocked(session, user):
        return None, None
    return item, user


def secret_for(item, user):
    return cipher().decrypt((item.pending_secret if item.purpose == 'enroll' else user.mfa_secret).encode()).decode()


def verify(session, token, code):
    # Serialize attempts on PostgreSQL; conditional writes also protect SQLite.
    if token:
        session.execute(select(MfaChallenge.token_hash).where(
            MfaChallenge.token_hash == digest(token)).with_for_update()).first()
    item, user = challenge(session, token)
    if item is None:
        return None
    # Conditional updates prevent a challenge, time-step or recovery code being used twice.
    claimed = session.execute(update(MfaChallenge).execution_options(synchronize_session='fetch').where(
        MfaChallenge.token_hash == item.token_hash, MfaChallenge.consumed == False,
        MfaChallenge.attempts < 5, MfaChallenge.expires_at > now()).values(
            attempts=MfaChallenge.attempts + 1).returning(MfaChallenge.token_hash)).first()
    if not claimed:
        return None
    code = code.strip().replace(' ', '').replace('-', '')
    step = int(time.time()) // 30
    accepted = False
    recovery = False
    try:
        otp = pyotp.TOTP(secret_for(item, user))
        matched = next((n for n in (step, step - 1, step + 1)
                        if len(code) == 6 and code.isascii() and code.isdigit()
                        and hmac.compare_digest(otp.at(n * 30), code)), None)
        if matched is not None:
            clauses = [User.id == user.id, User.mfa_last_step < matched]
            if item.purpose == 'enroll':
                clauses.append(User.mfa_secret == '')
            accepted = bool(session.execute(update(User).execution_options(synchronize_session='fetch').where(*clauses).values(
                mfa_last_step=matched).returning(User.id)).first())
        elif item.purpose == 'verify':
            hashed = digest(f'{user.id}:{code}')
            old = list(user.mfa_recovery_hashes or [])
            if hashed in old:
                accepted = bool(session.execute(update(User).execution_options(synchronize_session='fetch').where(User.id == user.id,
                    User.mfa_recovery_counter == user.mfa_recovery_counter).values(
                        mfa_recovery_counter=User.mfa_recovery_counter + 1,
                        mfa_recovery_hashes=[x for x in old if x != hashed])
                    .returning(User.id)).first())
                recovery = accepted
    except (InvalidToken, ValueError, TypeError):
        accepted = False
    if not accepted:
        auth.log(session, user, 'mfa_failed')
        return None
    consumed = session.execute(update(MfaChallenge).execution_options(synchronize_session='fetch').where(MfaChallenge.token_hash == item.token_hash,
        MfaChallenge.consumed == False).values(consumed=True, pending_secret='').returning(MfaChallenge.token_hash)).first()
    if not consumed:
        return None
    codes = []
    if item.purpose == 'enroll':
        # pending_secret was cleared in the database; capture from encrypted seed before the UPDATE below.
        user.mfa_secret = cipher().encrypt(otp.secret.encode()).decode()
        codes = [secrets.token_hex(10) for _ in range(10)]
        user.mfa_recovery_hashes = [digest(f'{user.id}:{value}') for value in codes]
        user.mfa_version += 1
        auth.end_all_sessions(session, user)
        auth.log(session, user, 'mfa_enabled')
    else:
        auth.log(session, user, 'mfa_recovery_used' if recovery else 'mfa_verified')
    session.flush()
    return user, item.next_path, codes


def invite(session, email):
    email = email.strip().lower()
    if '@' not in email or len(email) > 200 or session.scalar(select(User.id).where(User.email == email)):
        raise ValueError('Use a new personal email')
    token = secrets.token_urlsafe(32)
    session.add(AccountInvite(token_hash=digest(token), email=email, role='deal_manager',
                             expires_at=now() + timedelta(hours=1)))
    return token
