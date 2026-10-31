"""Shared web plumbing: templates, sessions, role checks, small form helpers."""

from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import upload_security, auth, authority, config, datacheck, db, dealstatus, documents, fees, i18n, offers, pipeline, reid, release, handoff, connections
from ..editorial import mainland
from ..models import AdviserFirm, Buyer, Match, Target, User
from ..taxonomy import (BUYER_KINDS, DEAL_TYPES, FOUNDER_TRANSITION, FUNDING_EVIDENCE, INVENTORY, MACRO_REGIONS, PAYMENT_TERMS,
                        PERMITS, PREMISES, REGIONS, SALE_REASONS, SECTORS, TIMING, macro_region, sector_label)

HERE = Path(__file__).parent
COOKIE = "mm_session"
LANG_COOKIE = "mm_lang"
I = "/internal"

templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals.update(
    SECTORS=SECTORS, REGIONS=REGIONS, DEAL_TYPES=DEAL_TYPES, SALE_REASONS=SALE_REASONS, PAYMENT_TERMS=PAYMENT_TERMS,
    FOUNDER_TRANSITION=FOUNDER_TRANSITION, TIMING=TIMING, PREMISES=PREMISES, PERMITS=PERMITS, INVENTORY=INVENTORY, FUNDING_EVIDENCE=FUNDING_EVIDENCE,
    STAGES=pipeline.STAGES, STATUSES=dealstatus.STATUSES, BUYER_KINDS=BUYER_KINDS,
    MACRO_REGIONS=MACRO_REGIONS, CHECKLIST=documents.CHECKLIST, ROLES=auth.ROLES,
    REJECT_REASONS=offers.REJECT_REASONS, AUTH_STATUS=authority.STATUS, OWNER_ROLES=authority.OWNER_ROLES,
    PROFESSIONS=authority.PROFESSIONS, SCOPES=authority.SCOPES, AUTH_TEXT=authority.AUTH_TEXT,
    CONSIDERATION=offers.CONSIDERATION, FINANCING=offers.FINANCING, latest_offer=offers.latest_offer, sector_label=sector_label, risk_label=reid.risk_label,
    macro_region=macro_region, FIN_FIELDS=datacheck.FIN_FIELDS, DISCLOSURES=datacheck.DISCLOSURES,
    SEVERITY=datacheck.SEVERITY, CHARGE_KINDS=fees.CHARGE_KINDS, fin_years=datacheck.years, fees=fees, cfg=config,
    HANDOFF_ACCESS_LABELS=connections.ACCESS_LABELS, NDA_LABELS=connections.NDA_LABELS,
    UPLOAD_STATUS=upload_security.LABELS, file_usable=upload_security.usable,
    handoff=handoff, release=release, I=I, css_version=int((HERE / "static" / "style.css").stat().st_mtime),
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


def browser_lang(accept_language: str) -> str | None:
    """First supported language in the browser's list, by preference order (q values respected)."""
    tags = []
    for i, part in enumerate(accept_language.split(",")):
        tag, _, q = part.strip().partition(";q=")
        try:
            weight = float(q) if q else 1.0
        except ValueError:
            weight = 0.0
        tags.append((-weight, i, tag.strip().lower().split("-")[0]))
    return next((code for _, _, code in sorted(tags) if code in i18n.LANGS), None)


def get_lang(request: Request) -> str:
    """The edition in the URL wins; otherwise the remembered switch choice, then the browser, then English."""
    edition = getattr(request.state, "lang", None)
    if edition in i18n.LANGS:
        return edition
    saved = request.cookies.get(LANG_COOKIE)
    if saved in i18n.LANGS:
        return saved
    return browser_lang(request.headers.get("accept-language", "")) or "en"


def render(request: Request, name: str, user: User | None = None, **ctx) -> HTMLResponse:
    lang = get_lang(request)
    path = request.url.path
    query = f"?{request.url.query}" if request.url.query else ""
    ctx = {"msg": request.query_params.get("msg", ""), "user": user, "lang": lang, "P": f"/{lang}",
           "edition_path": path + query, "here": path,
           "T": lambda zh, en: mainland(zh) if lang == "zh" else en,
           "L": lambda s: mainland(i18n.tr(s, lang)) if lang == "zh" else i18n.tr(s, lang),
           "V": lambda s: mainland(i18n.val(s, lang)) if lang == "zh" else i18n.val(s, lang),
           "R": lambda s: i18n.reason(s, lang), **ctx}
    response = templates.TemplateResponse(request, name, ctx)
    from .security import csrf_token
    import re
    token = csrf_token(request.cookies.get(COOKIE, ''))
    if token:
        html = re.sub(r'(<form\b[^>]*\bmethod=["\']post["\'][^>]*>)',
                      lambda m: m.group(1) + f'<input type="hidden" name="csrf_token" value="{token}">',
                      response.body.decode(), flags=re.IGNORECASE)
        return HTMLResponse(html, status_code=response.status_code)
    return response


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


def anon_buyer(b: Buyer, lang: str = "zh") -> str:
    kind = i18n.tr(BUYER_KINDS.get(b.kind, b.kind), lang)
    region = macro_region(b.province) if b.province else ""
    if not region:
        return kind
    return kind + (f" · 总部{region}" if lang == "zh" else f" · based in {i18n.val(region, 'en')}")


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
