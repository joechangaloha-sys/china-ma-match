"""Accounts, sign-in sessions and the audit log.

Passwords are hashed with scrypt (standard library). Sessions are random tokens stored server
side and sent as an HttpOnly, SameSite=Lax cookie. Every page and file request checks the role
and the matter on the server; hiding buttons is never the control.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .models import AuditEvent, User, UserSession

ROLES = {"seller": "卖方 Seller", "buyer": "买方 Buyer", "adviser": "顾问 Adviser", "deal_manager": "交易经理 Deal manager"}
SESSION_HOURS = 12
IDLE_MINUTES = 30
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
    except ValueError:
        return False
    test = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=_N, r=_R, p=_P)
    return hmac.compare_digest(test.hex(), digest)


def create_user(session: Session, *, email: str, password: str, role: str, name: str = "",
                organization: str = "", buyer_id: int | None = None) -> User:
    email = email.strip().lower()
    if role not in ROLES:
        raise ValueError("Unknown role")
    if "@" not in email:
        raise ValueError("请输入有效的邮箱 Enter a valid email address.")
    if len(password) < 10:
        raise ValueError("密码至少10位 Password must be at least 10 characters.")
    if session.scalar(select(User.id).where(User.email == email)):
        raise ValueError("该邮箱已注册 This email is already registered.")
    user = User(email=email, password_hash=hash_password(password), role=role, name=name.strip(),
                organization=organization.strip(), buyer_id=buyer_id)
    session.add(user)
    session.flush()
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    normalized = email.strip().lower()
    since = datetime.now(timezone.utc) - timedelta(minutes=15)
    attempts = session.scalar(select(func.count(AuditEvent.id)).where(
        AuditEvent.action == 'sign_in_failed', AuditEvent.created_at >= since,
        AuditEvent.detail['email'].as_string() == normalized))
    if attempts >= 10:
        return None
    user = session.scalar(select(User).where(User.email == normalized))
    if user is None or not user.active or not check_password(password, user.password_hash):
        log(session, None, 'sign_in_failed', email=normalized)
        return None
    return user


def start_session(session: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session.add(UserSession(token=token, user_id=user.id, last_seen_at=now, expires_at=now + timedelta(hours=SESSION_HOURS)))
    user.last_login_at = now
    log(session, user, "sign_in")
    return token


def user_for_token(session: Session, token: str | None) -> User | None:
    if not token:
        return None
    us = session.get(UserSession, token)
    if us is None:
        return None
    expires = us.expires_at if us.expires_at.tzinfo else us.expires_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    seen = us.last_seen_at
    if seen and not seen.tzinfo:
        seen = seen.replace(tzinfo=timezone.utc)
    if expires <= now or not seen or now - seen >= timedelta(minutes=IDLE_MINUTES) or not us.user.active:
        return None
    us.last_seen_at = now
    return us.user


def end_session(session: Session, token: str | None) -> None:
    if token and (us := session.get(UserSession, token)):
        session.delete(us)


def log(session: Session, user: User | None, action: str, *, target_id: int | None = None,
        match_id: int | None = None, document_id: int | None = None, **detail) -> AuditEvent:
    ev = AuditEvent(user_id=user.id if user else None, action=action, target_id=target_id, match_id=match_id,
                    document_id=document_id, detail=detail)
    session.add(ev)
    return ev


def end_all_sessions(session, user):
    from sqlalchemy import delete
    session.execute(delete(UserSession).where(UserSession.user_id == user.id))
    log(session, user, 'sign_out_all')
