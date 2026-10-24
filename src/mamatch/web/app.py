"""The website: public seller listings, each seller's private page, and internal pages.

- Public: `/` lists the sellers who opted in to an anonymised listing; `/listings/{id}` shows one,
  with an inquiry form. Nothing about buyers is ever shown publicly.
- Seller page `/s/{token}`: a private link the adviser sends the seller.
- Internal `/internal/...`: the adviser's seller workspace and deal pipeline. No login yet, so
  keep /internal behind an authenticating proxy or on localhost.
"""

from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import buyers as buyer_reg
from .. import config, datacheck, db, demand, fees, infomemo, listing, matching, offers, pipeline, plans, reid, teaser
from ..models import AdviserFirm, Buyer, InfoMemo, Match, Target, Teaser
from ..taxonomy import (DEAL_TYPES, FOUNDER_TRANSITION, PAYMENT_TERMS, REGIONS, SALE_REASONS, SECTORS, TIMING,
                        macro_region, sector_label)

HERE = Path(__file__).parent

# Reasons that are safe to show a seller: they describe fit, not who the buyer is.
SELLER_SAFE_REASONS = ("Stated interest", "Same business", "Adjacent sector", "No regional restriction",
                       "Has bought or targets companies in", "Active in the same region", "Deal size fits",
                       "Public inquiry")
I = "/internal"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="mamatch", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals.update(
    SECTORS=SECTORS, REGIONS=REGIONS, DEAL_TYPES=DEAL_TYPES, SALE_REASONS=SALE_REASONS, PAYMENT_TERMS=PAYMENT_TERMS,
    FOUNDER_TRANSITION=FOUNDER_TRANSITION, TIMING=TIMING, STAGES=pipeline.STAGES, BUYER_KINDS=demand.BUYER_KINDS,
    MACRO_REGIONS=demand.MACRO_REGIONS, sector_label=sector_label, risk_label=reid.risk_label,
    macro_region=macro_region, FIN_FIELDS=datacheck.FIN_FIELDS, DISCLOSURES=datacheck.DISCLOSURES,
    SEVERITY=datacheck.SEVERITY, CHARGE_KINDS=fees.CHARGE_KINDS, fin_years=datacheck.years, fees=fees, cfg=config,
    I=I,
)


def get_session() -> Iterator[Session]:
    with db.session_scope() as s:
        yield s


def render(request: Request, name: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"msg": request.query_params.get("msg", ""), **ctx})


def back(url: str, msg: str = "") -> RedirectResponse:
    if msg:
        path, _, frag = url.partition("#")
        url = f"{path}?msg={quote(msg)}" + (f"#{frag}" if frag else "")
    return RedirectResponse(url, status_code=303)


def _firm(s: Session) -> AdviserFirm:
    firm = s.scalar(select(AdviserFirm).limit(1))
    if firm is None:
        firm = AdviserFirm(name="My advisory firm")
        s.add(firm)
        s.flush()
    return firm


def _404():
    raise HTTPException(404, "Not found")


def _num(v: str, cast=float):
    return cast(v) if v.strip() else None


# ---------------------------------------------------------------- public listings

@app.get("/", response_class=HTMLResponse)
def listings(request: Request, sector: str = "", macro: str = "", s: Session = Depends(get_session)):
    rows = listing.public_board(s, sector, macro)
    return render(request, "listings.html", portal="public", rows=rows, cards={t.id: listing.card(t) for t in rows},
                  sector=sector, macro=macro)


def _listed(s: Session, target_id: int) -> Target:
    t = s.get(Target, target_id)
    if t is None or t.visibility != "listed":
        _404()
    return t


@app.get("/listings/{target_id}", response_class=HTMLResponse)
def listing_detail(target_id: int, request: Request, s: Session = Depends(get_session)):
    t = _listed(s, target_id)
    return render(request, "listing.html", portal="public", t=t, card=listing.card(t))


@app.post("/listings/{target_id}/inquiry")
def listing_inquiry(target_id: int, s: Session = Depends(get_session), name: str = Form(""), company: str = Form(""),
                    kind: str = Form("private"), contact: str = Form(""), message: str = Form(""),
                    consent: str = Form("")):
    t = _listed(s, target_id)
    try:
        offers.public_inquiry(s, t, name=name, company=company, kind=kind if kind in demand.BUYER_KINDS else "private",
                              contact=contact, message=message, consent=bool(consent))
    except ValueError as exc:
        return back(f"/listings/{t.id}#inquiry", str(exc))
    return back(f"/listings/{t.id}", "感谢您的咨询，顾问会尽快与您联系。Thank you: the adviser will contact you shortly.")


# ---------------------------------------------------------------- internal: sellers

@app.get(I, response_class=HTMLResponse)
def internal_home(request: Request, s: Session = Depends(get_session)):
    targets = s.scalars(select(Target).order_by(Target.created_at.desc())).all()
    inquiries = s.scalars(select(Match).where(Match.channel == "listing", Match.stage == "interested")
                          .order_by(Match.updated_at.desc())).all()
    counts = {
        "targets": len(targets),
        "listed": sum(t.visibility == "listed" for t in targets),
        "inquiries": len(inquiries),
        "active": s.scalar(select(func.count(Match.id)).where(Match.stage.not_in(["suggested", "dropped", "closed"]))),
    }
    return render(request, "sellers.html", portal="internal", targets=targets, inquiries=inquiries, counts=counts,
                  firm=_firm(s))


@app.get(I + "/targets/new", response_class=HTMLResponse)
def target_new(request: Request):
    return render(request, "target_new.html", portal="internal")


@app.post(I + "/targets")
def target_create(
    s: Session = Depends(get_session),
    code_name: str = Form(...), legal_name: str = Form(...), short_name: str = Form(""),
    owner_name: str = Form(""), city: str = Form(""), uscc: str = Form(""), brands: str = Form(""),
    province: str = Form(...), sector: str = Form(...), description: str = Form(""),
    founded_year: str = Form(""), employees: str = Form(""), revenue: str = Form(""),
    net_profit: str = Form(""), asking_value: str = Form(""),
    deal_type: str = Form("full_sale"), sale_reason: str = Form("succession"),
    stake_pct: str = Form(""), payment_terms: str = Form(""), founder_transition: str = Form(""),
    keep_employees: str = Form(""), timing: str = Form(""),
):
    t = Target(
        firm=_firm(s), code_name=code_name.strip(), legal_name=legal_name.strip(), short_name=short_name.strip(),
        owner_name=owner_name.strip(), city=city.strip(), uscc=uscc.strip(),
        brands=[b.strip() for b in brands.replace("，", ",").split(",") if b.strip()],
        province=province, sector=sector, description=description.strip(),
        founded_year=_num(founded_year, int), employees=_num(employees, int), revenue=_num(revenue),
        net_profit=_num(net_profit), deal_type=deal_type, sale_reason=sale_reason,
        seller_token=buyer_reg.new_token(),
    )
    _apply_ask(t, asking_value, stake_pct, payment_terms, founder_transition, keep_employees, timing)
    s.add(t)
    s.flush()
    return RedirectResponse(f"{I}/targets/{t.id}", status_code=303)


def _apply_ask(t: Target, asking_value: str, stake_pct: str, payment_terms: str, founder_transition: str,
               keep_employees: str, timing: str) -> None:
    t.asking_value = _num(asking_value)
    stake = _num(stake_pct)
    t.stake_pct = None if stake is None else min(max(stake, 1.0), 100.0)
    t.payment_terms = payment_terms if payment_terms in PAYMENT_TERMS else ""
    t.founder_transition = founder_transition if founder_transition in FOUNDER_TRANSITION else ""
    t.keep_employees = {"yes": True, "no": False}.get(keep_employees)
    t.timing = timing if timing in TIMING else ""


@app.get(I + "/targets/{target_id}", response_class=HTMLResponse)
def target_detail(target_id: int, request: Request, s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    if not t.seller_token:
        t.seller_token = buyer_reg.new_token()
    return render(request, "target.html", portal="internal", t=t, facts=teaser.facts(t), card=listing.card(t),
                  link=_link(request, "s", t.seller_token))


@app.post(I + "/targets/{target_id}/ask")
def target_ask(target_id: int, s: Session = Depends(get_session), asking_value: str = Form(""),
               stake_pct: str = Form(""), payment_terms: str = Form(""), founder_transition: str = Form(""),
               keep_employees: str = Form(""), timing: str = Form("")):
    t = s.get(Target, target_id) or _404()
    _apply_ask(t, asking_value, stake_pct, payment_terms, founder_transition, keep_employees, timing)
    return back(f"{I}/targets/{t.id}#listing", "Ask updated")


@app.post(I + "/targets/{target_id}/teaser")
def target_teaser(target_id: int, language: str = Form("zh"), s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    if language not in teaser.LANGUAGES:
        raise HTTPException(400, "Unknown language")
    teaser.draft(s, t, language)
    return RedirectResponse(f"{I}/targets/{t.id}#teasers", status_code=303)


@app.post(I + "/teasers/{teaser_id}/approve")
def teaser_approve(teaser_id: int, s: Session = Depends(get_session)):
    tz = s.get(Teaser, teaser_id) or _404()
    try:
        teaser.approve(tz)
    except ValueError as exc:
        return back(f"{I}/targets/{tz.target_id}#teasers", str(exc))
    return RedirectResponse(f"{I}/targets/{tz.target_id}#teasers", status_code=303)


@app.post(I + "/targets/{target_id}/visibility")
def target_visibility(target_id: int, visibility: str = Form(...), s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    return _set_visibility(t, visibility, f"{I}/targets/{t.id}#listing")


@app.post(I + "/targets/{target_id}/plan")
def target_plan(target_id: int, invoice_ref: str = Form(""), s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    if not invoice_ref.strip():
        return back(f"{I}/targets/{t.id}#fees", "Enter the invoice reference")
    plans.mark_seller_paid(t, invoice_ref)
    return back(f"{I}/targets/{t.id}#fees", "Outreach retainer recorded as paid")


@app.post(I + "/targets/{target_id}/prep-pack")
def target_prep_pack(target_id: int, invoice_ref: str = Form(""), s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    if not invoice_ref.strip():
        return back(f"{I}/targets/{t.id}#fees", "Enter the invoice reference")
    try:
        fees.record_prep_pack(t, invoice_ref)
    except ValueError as exc:
        return back(f"{I}/targets/{t.id}#fees", str(exc))
    return back(f"{I}/targets/{t.id}#fees", "Preparation pack recorded as paid")


@app.post(I + "/targets/{target_id}/data")
async def target_data(target_id: int, request: Request, s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    _save_data(t, await request.form())
    return back(f"{I}/targets/{t.id}#data", "Data saved")


@app.post(I + "/targets/{target_id}/datacheck")
def target_datacheck(target_id: int, s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    try:
        datacheck.run(s, t)
    except ValueError as exc:
        return back(f"{I}/targets/{t.id}#data", str(exc))
    return back(f"{I}/targets/{t.id}#data")


@app.post(I + "/targets/{target_id}/memo")
def target_memo(target_id: int, language: str = Form("zh"), s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    try:
        infomemo.draft(s, t, language)
    except ValueError as exc:
        return back(f"{I}/targets/{t.id}#memo", str(exc))
    return back(f"{I}/targets/{t.id}#memo")


@app.post(I + "/memos/{memo_id}/approve")
def memo_approve(memo_id: int, s: Session = Depends(get_session)):
    m = s.get(InfoMemo, memo_id) or _404()
    try:
        infomemo.approve(m)
    except ValueError as exc:
        return back(f"{I}/targets/{m.target_id}#memo", str(exc))
    return back(f"{I}/targets/{m.target_id}#memo", "Info memo approved")


@app.post(I + "/targets/{target_id}/match")
def target_match(target_id: int, s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    matching.refresh(s, t)
    return RedirectResponse(f"{I}/targets/{t.id}#matches", status_code=303)


@app.post(I + "/matches/{match_id}/close")
def match_close(match_id: int, deal_value: str = Form(""), invoice_ref: str = Form(""),
                s: Session = Depends(get_session)):
    m = s.get(Match, match_id) or _404()
    try:
        charge = fees.record_closing(s, m, _num(deal_value) or 0, invoice_ref)
    except ValueError as exc:
        return back(f"{I}/targets/{m.target_id}#fees", str(exc))
    msg = f"Closed. Success fee RMB {charge.amount:,.0f}" if charge else "Closed. No success fee (listed-only seller)."
    return back(f"{I}/targets/{m.target_id}#fees", msg)


@app.post(I + "/matches/{match_id}/move")
def match_move(match_id: int, to_stage: str = Form(...), note: str = Form(""),
               back_to: str = Form("", alias="back"), s: Session = Depends(get_session)):
    m = s.get(Match, match_id) or _404()
    dest = back_to if back_to.startswith(I) else f"{I}/targets/{m.target_id}#matches"
    if to_stage == "teaser_sent":
        return back(dest, "Teasers go out only when the seller approves the buyer on the seller page.")
    if to_stage == "closed":
        return back(f"{I}/targets/{m.target_id}#fees", "Record the closing value on the target page to close a deal.")
    try:
        pipeline.move(s, m, to_stage, note)
    except ValueError as exc:
        return back(dest, str(exc))
    return back(dest)


@app.get(I + "/pipeline", response_class=HTMLResponse)
def pipeline_view(request: Request, s: Session = Depends(get_session)):
    rows = s.scalars(select(Match).where(Match.stage != "suggested").order_by(Match.updated_at.desc())).all()
    by_stage = {k: [m for m in rows if m.stage == k] for k in pipeline.STAGES if k != "suggested"}
    return render(request, "pipeline.html", portal="internal", by_stage=by_stage, allowed_next=pipeline.allowed_next)


def _save_data(t: Target, form) -> None:
    """Financials and checklist answers from the shared data form (adviser or seller)."""
    fin = {}
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


def _link(request: Request, kind: str, token: str) -> str:
    return f"{str(request.base_url).rstrip('/')}/{kind}/{token}" if token else ""


def _set_visibility(t: Target, visibility: str, dest: str) -> RedirectResponse:
    try:
        if visibility == "listed":
            listing.publish(t)
        elif visibility == "private":
            listing.unpublish(t)
        else:
            raise HTTPException(400, "Unknown visibility")
    except ValueError as exc:
        return back(dest, str(exc))
    return back(dest, "Listed publicly (anonymised)" if visibility == "listed" else "Removed from the public listings")


# ---------------------------------------------------------------- seller page

def _seller(s: Session, token: str) -> Target:
    t = s.scalar(select(Target).where(Target.seller_token == token)) if token else None
    return t or _404()


def _seller_match(s: Session, t: Target, match_id: int) -> Match:
    m = s.get(Match, match_id)
    if m is None or m.target_id != t.id:
        _404()
    return m


def anon_buyer(b: Buyer) -> str:
    kind = demand.BUYER_KINDS.get(b.kind, b.kind)
    region = macro_region(b.province) if b.province else ""
    return kind + (f" · 总部{region}" if region else "")


def seller_reasons(m: Match) -> list[str]:
    # Drop a buyer's exact size range "(RMB 40–300m)": together with type and region it can fingerprint a buyer.
    return [r.split(" (")[0] for r in m.reasons if r.startswith(SELLER_SAFE_REASONS)]


@app.get("/s/{token}", response_class=HTMLResponse)
def seller_page(token: str, request: Request, s: Session = Depends(get_session)):
    t = _seller(s, token)
    sent = [m for m in t.matches if m.stage not in ("suggested", "shortlisted")]
    outreach = plans.seller_outreach(t)
    return render(request, "seller.html", t=t, portal="seller", card=listing.card(t), outreach=outreach,
                  candidates=offers.outreach_candidates(t) if outreach else [],
                  sent=sent, anon_buyer=anon_buyer, seller_reasons=seller_reasons,
                  after_nda=offers.AFTER_NDA, has_teaser=offers.shared_teaser(t) is not None)


@app.post("/s/{token}/visibility")
def seller_visibility(token: str, visibility: str = Form(...), s: Session = Depends(get_session)):
    t = _seller(s, token)
    return _set_visibility(t, visibility, f"/s/{token}")


@app.post("/s/{token}/data")
async def seller_data(token: str, request: Request, s: Session = Depends(get_session)):
    t = _seller(s, token)
    _save_data(t, await request.form())
    return back(f"/s/{token}#data", "Data saved. Your adviser will review it.")


@app.post("/s/{token}/matches/{match_id}/{action}")
def seller_match_action(token: str, match_id: int, action: str, s: Session = Depends(get_session)):
    t = _seller(s, token)
    m = _seller_match(s, t, match_id)
    try:
        if action == "approve":
            offers.approve_and_send(s, m)
            msg = "Teaser sent to this buyer"
        elif action == "decline":
            offers.decline_candidate(s, m)
            msg = "Buyer removed from outreach"
        elif action == "disclose":
            offers.disclose_names(m)
            msg = "Names disclosed to each other"
        else:
            raise HTTPException(400, "Unknown action")
    except ValueError as exc:
        msg = str(exc)
    return back(f"/s/{token}#outreach", msg)
