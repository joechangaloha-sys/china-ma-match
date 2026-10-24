"""Operator workspace plus the seller and buyer pages of the invitation-only pilot.

- Operator (adviser) workspace: targets, buyers, demand, pipeline. No login yet, so run it on
  localhost or behind an authenticating proxy.
- Seller page /s/{token} and buyer page /b/{token}: private links the operator sends out. They
  only show what that seller or buyer may see; buyer identities reach a seller only as
  k-suppressed counts, or by name after both sides agree to disclose.
"""

from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import buyers as buyer_reg
from .. import config, db, demand, listing, matching, offers, pipeline, plans, reid, teaser
from ..models import AdviserFirm, Buyer, Match, Target, Teaser
from ..taxonomy import DEAL_TYPES, REGIONS, SALE_REASONS, SECTORS, macro_region, sector_label

HERE = Path(__file__).parent

BUYER_STATUSES = {"verified": "已认证 Verified", "registered": "待审核 Awaiting check",
                  "invited": "已邀请 Invited", "suggested": "候选 Candidate"}
# Reasons that are safe to show a seller: they describe fit, not who the buyer is.
SELLER_SAFE_REASONS = ("Stated interest", "Same business", "Adjacent sector", "No regional restriction",
                       "Has bought or targets companies in", "Active in the same region", "Deal size fits")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="mamatch", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals.update(
    SECTORS=SECTORS, REGIONS=REGIONS, DEAL_TYPES=DEAL_TYPES, SALE_REASONS=SALE_REASONS,
    STAGES=pipeline.STAGES, BUYER_KINDS=demand.BUYER_KINDS, BUYER_STATUSES=BUYER_STATUSES,
    MACRO_REGIONS=demand.MACRO_REGIONS, SELLER_PLANS=plans.SELLER_PLANS, BUYER_PLANS=plans.BUYER_PLANS,
    sector_label=sector_label, risk_label=reid.risk_label, macro_region=macro_region,
    region_flag=config.DEPLOYMENT_REGION, cfg=config, K=config.MIN_GROUP_SIZE,
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


# ---------------------------------------------------------------- operator workspace

@app.get("/", response_class=HTMLResponse)
def home(request: Request, s: Session = Depends(get_session)):
    targets = s.scalars(select(Target).order_by(Target.created_at.desc())).all()
    by_status = dict(s.execute(select(Buyer.status, func.count(Buyer.id)).group_by(Buyer.status)).all())
    counts = {
        "targets": len(targets),
        "verified": by_status.get("verified", 0),
        "candidates": by_status.get("suggested", 0) + by_status.get("invited", 0),
        "active": s.scalar(select(func.count(Match.id)).where(Match.stage.not_in(["suggested", "dropped", "closed"]))),
    }
    to_verify = s.scalars(select(Buyer).where(Buyer.status == "registered")).all()
    interests = s.scalars(select(Match).where(Match.channel == "listing", Match.stage == "interested")
                          .order_by(Match.updated_at.desc())).all()
    totals = {t.id: demand.for_target(s, t).total for t in targets}
    return render(request, "home.html", targets=targets, counts=counts, to_verify=to_verify, interests=interests,
                  totals=totals, firm=_firm(s))


@app.get("/buyers", response_class=HTMLResponse)
def buyers(request: Request, q: str = "", sector: str = "", province: str = "", status: str = "verified",
           s: Session = Depends(get_session)):
    stmt = select(Buyer).order_by(Buyer.updated_at.desc())
    if status:
        stmt = stmt.where(Buyer.status == status)
    if q:
        stmt = stmt.where(or_(Buyer.name.contains(q), Buyer.external_id.contains(q), Buyer.rationale.contains(q)))
    rows = s.scalars(stmt).all()
    # JSON list columns: filter in Python (SQLite has no portable JSON containment).
    if sector:
        rows = [b for b in rows if sector in (b.target_sectors or []) or sector in (b.sectors or [])]
    if province:
        rows = [b for b in rows if not b.target_regions or province in b.target_regions]
    by_status = dict(s.execute(select(Buyer.status, func.count(Buyer.id)).group_by(Buyer.status)).all())
    return render(request, "buyers.html", buyers=rows, q=q, sector=sector, province=province, status=status,
                  by_status=by_status)


@app.post("/buyers")
def buyer_add(s: Session = Depends(get_session), name: str = Form(...), kind: str = Form("private")):
    b = Buyer(name=name.strip(), kind=kind, source="manual")
    s.add(b)
    buyer_reg.invite(b)
    s.flush()
    return back(f"/buyers/{b.id}", "Invitation link created")


@app.get("/buyers/{buyer_id}", response_class=HTMLResponse)
def buyer_detail(buyer_id: int, request: Request, s: Session = Depends(get_session)):
    buyer = s.get(Buyer, buyer_id) or _404()
    return render(request, "buyer.html", buyer=buyer, link=_link(request, "b", buyer.invite_token))


@app.post("/buyers/{buyer_id}/invite")
def buyer_invite(buyer_id: int, s: Session = Depends(get_session)):
    b = s.get(Buyer, buyer_id) or _404()
    buyer_reg.invite(b)
    return back(f"/buyers/{b.id}", "Invitation link created")


@app.post("/buyers/{buyer_id}/verify")
def buyer_verify(buyer_id: int, s: Session = Depends(get_session)):
    b = s.get(Buyer, buyer_id) or _404()
    try:
        buyer_reg.verify(b)
    except ValueError as exc:
        return back(f"/buyers/{b.id}", str(exc))
    return back(f"/buyers/{b.id}", "Verified")


@app.post("/buyers/{buyer_id}/plan")
def buyer_plan(buyer_id: int, plan: str = Form(...), s: Session = Depends(get_session)):
    b = s.get(Buyer, buyer_id) or _404()
    plans.mark_buyer_priority(b, plan == "priority")
    return back(f"/buyers/{b.id}")


@app.get("/demand", response_class=HTMLResponse)
def demand_view(request: Request, s: Session = Depends(get_session)):
    return render(request, "demand.html", grid=demand.overview(s), eligible=len(demand.eligible(s)))


@app.get("/targets/new", response_class=HTMLResponse)
def target_new(request: Request):
    return render(request, "target_new.html")


@app.post("/targets")
def target_create(
    s: Session = Depends(get_session),
    code_name: str = Form(...), legal_name: str = Form(...), short_name: str = Form(""),
    owner_name: str = Form(""), city: str = Form(""), uscc: str = Form(""), brands: str = Form(""),
    province: str = Form(...), sector: str = Form(...), description: str = Form(""),
    founded_year: str = Form(""), employees: str = Form(""), revenue: str = Form(""),
    net_profit: str = Form(""), asking_value: str = Form(""),
    deal_type: str = Form("full_sale"), sale_reason: str = Form("succession"),
):
    t = Target(
        firm=_firm(s), code_name=code_name.strip(), legal_name=legal_name.strip(), short_name=short_name.strip(),
        owner_name=owner_name.strip(), city=city.strip(), uscc=uscc.strip(),
        brands=[b.strip() for b in brands.replace("，", ",").split(",") if b.strip()],
        province=province, sector=sector, description=description.strip(),
        founded_year=_num(founded_year, int), employees=_num(employees, int), revenue=_num(revenue),
        net_profit=_num(net_profit), asking_value=_num(asking_value), deal_type=deal_type, sale_reason=sale_reason,
        seller_token=buyer_reg.new_token(),
    )
    s.add(t)
    s.flush()
    return RedirectResponse(f"/targets/{t.id}", status_code=303)


@app.get("/targets/{target_id}", response_class=HTMLResponse)
def target_detail(target_id: int, request: Request, s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    if not t.seller_token:
        t.seller_token = buyer_reg.new_token()
    return render(request, "target.html", t=t, facts=teaser.facts(t), card=listing.card(t),
                  demand=demand.for_target(s, t, detailed=True), candidates=matching.invite_candidates(s, t),
                  link=_link(request, "s", t.seller_token))


@app.post("/targets/{target_id}/teaser")
def target_teaser(target_id: int, language: str = Form("zh"), s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    if language not in teaser.LANGUAGES:
        raise HTTPException(400, "Unknown language")
    teaser.draft(s, t, language)
    return RedirectResponse(f"/targets/{t.id}#teasers", status_code=303)


@app.post("/teasers/{teaser_id}/approve")
def teaser_approve(teaser_id: int, s: Session = Depends(get_session)):
    tz = s.get(Teaser, teaser_id) or _404()
    try:
        teaser.approve(tz)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return RedirectResponse(f"/targets/{tz.target_id}#teasers", status_code=303)


@app.post("/targets/{target_id}/visibility")
def target_visibility(target_id: int, visibility: str = Form(...), back_to: str = Form(""),
                      s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    return _set_visibility(t, visibility, back_to or f"/targets/{t.id}#listing")


@app.post("/targets/{target_id}/plan")
def target_plan(target_id: int, invoice_ref: str = Form(""), s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    if not invoice_ref.strip():
        return back(f"/targets/{t.id}#listing", "Enter the invoice reference")
    plans.mark_seller_paid(t, invoice_ref)
    return back(f"/targets/{t.id}#listing", "Plan recorded as paid")


@app.post("/targets/{target_id}/match")
def target_match(target_id: int, s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    matching.refresh(s, t)
    return RedirectResponse(f"/targets/{t.id}#matches", status_code=303)


@app.post("/matches/{match_id}/move")
def match_move(match_id: int, to_stage: str = Form(...), note: str = Form(""),
               back_to: str = Form("", alias="back"), s: Session = Depends(get_session)):
    m = s.get(Match, match_id) or _404()
    dest = back_to or f"/targets/{m.target_id}#matches"
    if to_stage == "teaser_sent":
        return back(dest, "Teasers go out only when the seller approves the buyer on the seller page.")
    try:
        pipeline.move(s, m, to_stage, note)
    except ValueError as exc:
        return back(dest, str(exc))
    return back(dest)


@app.get("/pipeline", response_class=HTMLResponse)
def pipeline_view(request: Request, s: Session = Depends(get_session)):
    rows = s.scalars(select(Match).where(Match.stage != "suggested").order_by(Match.updated_at.desc())).all()
    by_stage = {k: [m for m in rows if m.stage == k] for k in pipeline.STAGES if k != "suggested"}
    return render(request, "pipeline.html", by_stage=by_stage, allowed_next=pipeline.allowed_next)


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
    return back(dest, "Listed on the board" if visibility == "listed" else "Removed from the board")


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
    return render(request, "seller.html", t=t, portal="seller", card=listing.card(t),
                  demand=demand.for_target(s, t, detailed=plans.seller_detailed_stats(t)),
                  candidates=offers.outreach_candidates(t) if plans.seller_outreach(t) else [],
                  sent=sent, anon_buyer=anon_buyer, seller_reasons=seller_reasons,
                  is_priority=plans.is_priority, after_nda=offers.AFTER_NDA,
                  has_teaser=offers.shared_teaser(t) is not None)


@app.post("/s/{token}/visibility")
def seller_visibility(token: str, visibility: str = Form(...), s: Session = Depends(get_session)):
    t = _seller(s, token)
    return _set_visibility(t, visibility, f"/s/{token}")


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


# ---------------------------------------------------------------- buyer page

def _buyer(s: Session, token: str) -> Buyer:
    b = s.scalar(select(Buyer).where(Buyer.invite_token == token)) if token else None
    if b is None or b.status == "suggested":
        _404()
    return b


@app.get("/b/{token}", response_class=HTMLResponse)
def buyer_page(token: str, request: Request, sector: str = "", macro: str = "", s: Session = Depends(get_session)):
    b = _buyer(s, token)
    mine = s.scalars(select(Match).where(Match.buyer_id == b.id, Match.stage.not_in(["suggested", "shortlisted"]))
                     .order_by(Match.updated_at.desc())).all()
    interested_ids = {m.target_id for m in mine if m.stage != "dropped"}
    return render(request, "buyer_portal.html", b=b, portal="buyer",
                  board=listing.board(s, b, sector, macro), hidden=listing.hidden_count(s, b),
                  cards={t.id: listing.card(t) for t in listing.board(s, b, sector, macro)},
                  mine=mine, interested_ids=interested_ids, shared_teaser=offers.shared_teaser,
                  can_search=plans.can_search(b), sector=sector, macro=macro)


@app.post("/b/{token}/register")
def buyer_register(token: str, s: Session = Depends(get_session), name: str = Form(...), kind: str = Form(...),
                   uscc: str = Form(""), contact_name: str = Form(""), contact_email: str = Form(""),
                   target_sectors: list[str] = Form([]), target_regions: list[str] = Form([]),
                   deal_size_min: str = Form(""), deal_size_max: str = Form(""),
                   target_deal_types: list[str] = Form([]), consent: str = Form("")):
    b = _buyer(s, token)
    try:
        buyer_reg.register(b, name=name, kind=kind, uscc=uscc, contact_name=contact_name,
                           contact_email=contact_email,
                           target_sectors=[x for x in target_sectors if x in SECTORS],
                           target_regions=[x for x in target_regions if x in REGIONS],
                           deal_size_min=_num(deal_size_min), deal_size_max=_num(deal_size_max),
                           target_deal_types=[x for x in target_deal_types if x in DEAL_TYPES],
                           consent=bool(consent))
    except ValueError as exc:
        return back(f"/b/{token}#criteria", str(exc))
    return back(f"/b/{token}", "Criteria saved")


@app.post("/b/{token}/listings/{target_id}/interest")
def buyer_interest(token: str, target_id: int, s: Session = Depends(get_session)):
    b = _buyer(s, token)
    t = s.get(Target, target_id) or _404()
    try:
        offers.express_interest(s, t, b)
    except ValueError as exc:
        return back(f"/b/{token}#board", str(exc))
    return back(f"/b/{token}#deals", "Interest sent to the adviser")


@app.post("/b/{token}/matches/{match_id}/respond")
def buyer_respond(token: str, match_id: int, interested: str = Form(...), s: Session = Depends(get_session)):
    b = _buyer(s, token)
    m = s.get(Match, match_id)
    if m is None or m.buyer_id != b.id:
        _404()
    try:
        offers.buyer_respond(s, m, interested == "1")
    except ValueError as exc:
        return back(f"/b/{token}#deals", str(exc))
    return back(f"/b/{token}#deals")
