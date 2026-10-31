"""CSRF protection for signed-in mutations and same-origin browser submissions."""
import hashlib
import hmac
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse


def csrf_token(session_token):
    return hashlib.sha256(('mamatch-csrf:' + session_token).encode()).hexdigest() if session_token else ''


class RequestProtection(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            origin = request.headers.get('origin')
            own = urlsplit(str(request.url))
            if origin and origin.rstrip('/') != f'{own.scheme}://{own.netloc}':
                return PlainTextResponse('Cross-origin submission denied', status_code=403)
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return PlainTextResponse('Cross-site submission denied', status_code=403)
            token = request.cookies.get('mm_session')
            if token:
                provided = request.headers.get('x-csrf-token', '')
                if not provided:
                    # Cache before parsing so the downstream route can read uploads/forms again.
                    await request.body()
                    try:
                        form = await request.form()
                        provided = str(form.get('csrf_token', ''))
                        await form.close()
                    except Exception:
                        provided = ''
                if not hmac.compare_digest(provided, csrf_token(token)):
                    return PlainTextResponse('CSRF check failed. Reload the page and try again.', status_code=403)
        response = await call_next(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        if request.cookies.get('mm_session'):
            response.headers.setdefault('Cache-Control', 'no-store')
        return response
