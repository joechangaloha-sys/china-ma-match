"""Passcode gate and health checks for an isolated fictional-data demo.

Disabled by default. The passcode protects demonstration access only; the normal role, object
and workflow permissions still apply after it. No real data should be used in demo mode.
"""

import hashlib
import hmac
import time
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import config
from .common import get_session, render

router = APIRouter()
COOKIE = "mm_demo_access"


def _signature(expires: int) -> str:
    return hmac.new(config.DEMO_ACCESS_KEY.encode(), f"mamatch-demo:{expires}".encode(), hashlib.sha256).hexdigest()


def valid_cookie(value: str | None, now: int | None = None) -> bool:
    if not value or not config.DEMO_ACCESS_KEY:
        return False
    expiry, separator, signature = value.partition(".")
    if not separator or not expiry.isdigit():
        return False
    expires = int(expiry)
    return expires > (now or int(time.time())) and hmac.compare_digest(signature, _signature(expires))


def safe_next(value: str) -> str:
    return value if value.startswith("/") and not value.startswith("//") and len(value) <= 500 else "/"


class DemoAccess:
    """Require a short-lived signed demo cookie; LanguageEditions runs outside this middleware."""

    OPEN_PATHS = {"/demo-access", "/health/live", "/health/ready"}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not config.DEMO_MODE:
            await self.app(scope, receive, send)
            return

        async def send_noindex(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message["headers"] if k.lower() != b"x-robots-tag"]
                headers.append((b"x-robots-tag", b"noindex, nofollow, noarchive"))
                message = {**message, "headers": headers}
            await send(message)

        path = scope["path"]
        request = Request(scope)
        if path in self.OPEN_PATHS or path.startswith("/static/") or valid_cookie(request.cookies.get(COOKIE)):
            await self.app(scope, receive, send_noindex)
            return
        query = scope.get("query_string", b"").decode()
        destination = path + (f"?{query}" if query else "")
        response = RedirectResponse(f"/demo-access?next={quote(destination, safe='')}", status_code=303)
        await response(scope, receive, send_noindex)


@router.get("/demo-access", response_class=HTMLResponse)
def demo_access_page(request: Request, next: str = ""):
    response = render(request, "demo_access.html", None, portal="public", next=safe_next(next))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/demo-access")
def demo_access_submit(request: Request, access_key: str = Form(""), next: str = Form("")):
    if not config.DEMO_ACCESS_KEY or not hmac.compare_digest(access_key, config.DEMO_ACCESS_KEY):
        response = render(request, "demo_access.html", None, portal="public", next=safe_next(next),
                          msg="访问密码不正确 Incorrect demo passcode.")
        response.headers["Cache-Control"] = "no-store"
        return response
    expires = int(time.time()) + config.DEMO_ACCESS_HOURS * 3600
    response = RedirectResponse(safe_next(next), status_code=303)
    response.set_cookie(COOKIE, f"{expires}.{_signature(expires)}", max_age=config.DEMO_ACCESS_HOURS * 3600,
                        httponly=True, samesite="lax", secure=request.url.scheme == "https" or config.SECURE_COOKIES,
                        path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/health/live")
def live():
    return JSONResponse({"status": "ok"})


@router.get("/health/ready")
def ready(s: Session = Depends(get_session)):
    try:
        from .. import db
        db.check_schema()
        s.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ready"})
