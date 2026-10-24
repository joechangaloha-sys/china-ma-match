"""Adviser workspace: buyer index, targets, teasers, matches and pipeline.

Single adviser firm per deployment for the MVP; authentication is not built yet, so only run
it on localhost or behind an authenticating proxy.
"""

from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import config, db, matching, pipeline, reid, teaser
from ..models import AdviserFirm, Buyer, BuyerSignal, Match, Target, Teaser
from ..taxonomy import DEAL_TYPES, REGIONS, SALE_REASONS, SECTORS, sector_label

HERE = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="mamatch", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals.update(
    SECTORS=SECTORS, REGIONS=REGIONS, DEAL_TYPES=DEAL_TYPES, SALE_REASONS=SALE_REASONS,
    STAGES=pipeline.STAGES, sector_label=sector_label, risk_label=reid.risk_label,
    region_flag=config.DEPLOYMENT_REGION,
)


def get_session() -> Iterator[Session]:
    with db.session_scope() as s:
        yield s


def render(request: Request, name: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(request, name, ctx)


def _firm(s: Session) -> AdviserFirm:
    firm = s.scalar(select(AdviserFirm).limit(1))
    if firm is None:
        firm = AdviserFirm(name="My advisory firm")
        s.add(firm)
        s.flush()
    return firm


@app.get("/", response_class=HTMLResponse)
def home(request: Request, s: Session = Depends(get_session)):
    targets = s.scalars(select(Target).order_by(Target.created_at.desc())).all()
    signals = s.scalars(select(BuyerSignal).order_by(BuyerSignal.published_at.desc()).limit(8)).all()
    counts = {
        "buyers": s.scalar(select(func.count(Buyer.id))),
        "targets": len(targets),
        "active": s.scalar(select(func.count(Match.id)).where(Match.stage.not_in(["suggested", "dropped", "closed"]))),
    }
    return render(request, "home.html", targets=targets, signals=signals, counts=counts, firm=_firm(s))


@app.get("/buyers", response_class=HTMLResponse)
def buyers(request: Request, q: str = "", sector: str = "", province: str = "", s: Session = Depends(get_session)):
    stmt = select(Buyer).order_by(Buyer.updated_at.desc())
    if q:
        stmt = stmt.where(or_(Buyer.name.contains(q), Buyer.external_id.contains(q), Buyer.rationale.contains(q)))
    rows = s.scalars(stmt).all()
    # JSON list columns: filter in Python (SQLite has no portable JSON containment).
    if sector:
        rows = [b for b in rows if sector in (b.target_sectors or []) or sector in (b.sectors or [])]
    if province:
        rows = [b for b in rows if not b.target_regions or province in b.target_regions]
    return render(request, "buyers.html", buyers=rows, q=q, sector=sector, province=province)


@app.get("/buyers/{buyer_id}", response_class=HTMLResponse)
def buyer_detail(buyer_id: int, request: Request, s: Session = Depends(get_session)):
    buyer = s.get(Buyer, buyer_id) or _404()
    return render(request, "buyer.html", buyer=buyer)


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
    def num(v: str, cast=float):
        return cast(v) if v.strip() else None

    t = Target(
        firm=_firm(s), code_name=code_name.strip(), legal_name=legal_name.strip(), short_name=short_name.strip(),
        owner_name=owner_name.strip(), city=city.strip(), uscc=uscc.strip(),
        brands=[b.strip() for b in brands.replace("，", ",").split(",") if b.strip()],
        province=province, sector=sector, description=description.strip(),
        founded_year=num(founded_year, int), employees=num(employees, int), revenue=num(revenue),
        net_profit=num(net_profit), asking_value=num(asking_value), deal_type=deal_type, sale_reason=sale_reason,
    )
    s.add(t)
    s.flush()
    return RedirectResponse(f"/targets/{t.id}", status_code=303)


@app.get("/targets/{target_id}", response_class=HTMLResponse)
def target_detail(target_id: int, request: Request, s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    return render(request, "target.html", t=t, facts=teaser.facts(t))


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


@app.post("/targets/{target_id}/match")
def target_match(target_id: int, s: Session = Depends(get_session)):
    t = s.get(Target, target_id) or _404()
    matching.refresh(s, t)
    return RedirectResponse(f"/targets/{t.id}#matches", status_code=303)


@app.post("/matches/{match_id}/move")
def match_move(match_id: int, to_stage: str = Form(...), note: str = Form(""),
               back: str = Form(""), s: Session = Depends(get_session)):
    m = s.get(Match, match_id) or _404()
    try:
        pipeline.move(s, m, to_stage, note)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return RedirectResponse(back or f"/targets/{m.target_id}#matches", status_code=303)


@app.get("/pipeline", response_class=HTMLResponse)
def pipeline_view(request: Request, s: Session = Depends(get_session)):
    rows = s.scalars(select(Match).where(Match.stage != "suggested").order_by(Match.updated_at.desc())).all()
    by_stage = {k: [m for m in rows if m.stage == k] for k in pipeline.STAGES if k != "suggested"}
    return render(request, "pipeline.html", by_stage=by_stage, allowed_next=pipeline.allowed_next)


def _404():
    raise HTTPException(404, "Not found")
