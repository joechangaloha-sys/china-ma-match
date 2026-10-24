"""The website: public pages, seller and buyer portals, and the deal manager's internal pages.

- Public (`/`, `/opportunities`, ...): how it works, anonymised seller listings, intake, sign-in.
  Nothing about buyers is ever public.
- Seller portal `/seller`, buyer portal `/buyer`: signed-in, role-checked on every request.
- Internal `/internal/...`: deal managers only, marked internal on every page.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .. import db, i18n
from . import adviser, buyer, internal, public, seller

HERE = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


class LanguageEditions:
    """/zh/... and /en/... are the two editions, as on the Japan IR Index.

    The prefix is stripped before routing and kept on the request (request.state.lang), and
    same-site redirects issued inside an edition stay in it. Direct edition links never
    negotiate or redirect; only the neutral homepage does (web/public.py).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        lang = next((code for code in i18n.LANGS if path == f"/{code}" or path.startswith(f"/{code}/")), None)
        if lang is None:
            return await self.app(scope, receive, send)
        rest = path[len(lang) + 1:] or "/"
        scope = {**scope, "path": rest, "raw_path": rest.encode(), "state": {**scope.get("state", {}), "lang": lang}}

        async def send_in_edition(message):
            if message["type"] == "http.response.start" and 300 <= message["status"] < 400:
                headers = []
                for k, v in message.get("headers", []):
                    if k.lower() == b"location":
                        loc = v.decode()
                        if loc.startswith("/") and not loc.startswith("//") and not loc.startswith("/static") \
                                and not any(loc == f"/{c}" or loc.startswith(f"/{c}/") for c in i18n.LANGS):
                            v = f"/{lang}{loc}".encode()
                    headers.append((k, v))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_in_edition)


app = FastAPI(title="mamatch", lifespan=lifespan)
app.add_middleware(LanguageEditions)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
app.include_router(internal.router)
app.include_router(seller.router)
app.include_router(buyer.router)
app.include_router(adviser.router)
app.include_router(public.router)  # last: it ends with a catch-all for information pages
