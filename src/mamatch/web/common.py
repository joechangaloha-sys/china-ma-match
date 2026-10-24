"""Shared web plumbing: templates, sessions, role checks, small form helpers."""

from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auth, config, datacheck, db, dealstatus, demand, documents, fees, offers, pipeline, reid
from ..models import AdviserFirm, Buyer, Match, Target, User
from ..taxonomy import (DEAL_TYPES, FOUNDER_TRANSITION, FUNDING_EVIDENCE, PAYMENT_TERMS, REGIONS, SALE_REASONS,
                        SECTORS, TIMING, macro_region, sector_label)

HERE = Path(__file__).parent
COOKIE = "mm_session"
I = "/internal"

templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals.update(
    SECTORS=SECTORS, REGIONS=REGIONS, DEAL_TYPES=DEAL_TYPES, SALE_REASONS=SALE_REASONS, PAYMENT_TERMS=PAYMENT_TERMS,
    FOUNDER_TRANSITION=FOUNDER_TRANSITION, TIMING=TIMING, FUNDING_EVIDENCE=FUNDING_EVIDENCE,
    STAGES=pipeline.STAGES, STATUSES=dealstatus.STATUSES, BUYER_KINDS=demand.BUYER_KINDS,
    MACRO_REGIONS=demand.MACRO_REGIONS, CHECKLIST=documents.CHECKLIST, ROLES=auth.ROLES,
    REJECT_REASONS=offers.REJECT_REASONS, sector_label=sector_label, risk_label=reid.risk_label,
    macro_region=macro_region, FIN_FIELDS=datacheck.FIN_FIELDS, DISCLOSURES=datacheck.DISCLOSURES,
    SEVERITY=datacheck.SEVERITY, CHARGE_KINDS=fees.CHARGE_KINDS, fin_years=datacheck.years, fees=fees, cfg=config,
    I=I,
)


def get_session() -> Iterator[Session]:
    with db.session_scope() as s:
        yield s


def current_user(request: Request, s: Session = Depends(get_session)) -> User | None:
    return auth.user_for_token(s, request.cookies.get(COOKIE))


def _login_redirect(request: Request):
    nxt = quote(request.url.path)
    raise HTTPException(status_code=303, headers={"Location": f"/login?next={nxt}"})


def require(role: str):
    def dep(request: Request, user: User | None = Depends(current_user)) -> User:
        if user is None:
            _login_redirect(request)
        if user.role != role:
            raise HTTPException(403, "此页面无权访问 You do not have access to this page.")
        return user

    return dep


def render(request: Request, name: str, user: User | None = None, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"msg": request.query_params.get("msg", ""), "user": user, **ctx})


def back(url: str, msg: str = "") -> RedirectResponse:
    if msg:
        path, _, frag = url.partition("#")
        sep = "&" if "?" in path else "?"
        url = f"{path}{sep}msg={quote(msg)}" + (f"#{frag}" if frag else "")
    return RedirectResponse(url, status_code=303)


def not_found():
    raise HTTPException(404, "Not found")


def num(v: str | None, cast=float):
    v = (v or "").strip()
    return cast(v) if v else None


def firm(s: Session) -> AdviserFirm:
    f = s.scalar(select(AdviserFirm).limit(1))
    if f is None:
        f = AdviserFirm(name="My advisory firm")
        s.add(f)
        s.flush()
    return f


# Reasons that are safe to show a seller: they describe fit, not who the buyer is.
SELLER_SAFE_REASONS = ("Stated interest", "Same business", "Adjacent sector", "No regional restriction",
                       "Has bought or targets companies in", "Active in the same region", "Deal size fits",
                       "Public inquiry")


def anon_buyer(b: Buyer) -> str:
    kind = demand.BUYER_KINDS.get(b.kind, b.kind)
    region = macro_region(b.province) if b.province else ""
    return kind + (f" · 总部{region}" if region else "")


def seller_reasons(m: Match) -> list[str]:
    # Drop a buyer's exact size range "(RMB 40–300m)": together with type and region it can fingerprint a buyer.
    return [r.split(" (")[0] for r in m.reasons if r.startswith(SELLER_SAFE_REASONS)]


def save_data(t: Target, form) -> None:
    """Financials and checklist answers from the shared data form (deal manager or seller)."""
    fin = dict(t.financials or {})
    for y in datacheck.years():
        row = {k: float(v) for k in datacheck.FIN_FIELDS if (v := str(form.get(f"fin_{y}_{k}", "")).strip())}
        if row:
            fin[y] = row
    disc = {}
    for key, (_, kind) in datacheck.DISCLOSURES.items():
        v = str(form.get(f"d_{key}", "")).strip()
        if kind == "bool":
            disc[key] = {"yes": True, "no": False}.get(v)
        elif kind == "number":
            disc[key] = float(v) if v else None
        else:
            disc[key] = v or None
    t.financials = fin
    t.disclosures = {k: v for k, v in disc.items() if v is not None}
