"""Accounts, sign-in sessions and the audit log.

Passwords are hashed with scrypt (standard library). Sessions are random tokens stored server
side and sent as an HttpOnly, SameSite=Lax cookie. Every page and file request checks the role
and the matter on the server; hiding buttons is never the control.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditEvent, User, UserSession

ROLES = {"seller": "卖方 Seller", "buyer": "买方 Buyer", "adviser": "顾问 Adviser", "deal_manager": "交易经理 Deal manager"}
SESSION_DAYS = 14
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
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.active or not check_password(password, user.password_hash):
        return None
    return user


def start_session(session: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session.add(UserSession(token=token, user_id=user.id, expires_at=now + timedelta(days=SESSION_DAYS)))
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
    if expires < datetime.now(timezone.utc) or not us.user.active:
        return None
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
