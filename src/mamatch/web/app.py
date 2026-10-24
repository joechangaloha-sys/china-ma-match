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

from .. import db
from . import buyer, internal, public, seller

HERE = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="mamatch", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
app.include_router(internal.router)
app.include_router(seller.router)
app.include_router(buyer.router)
app.include_router(public.router)  # last: it ends with a catch-all for information pages
