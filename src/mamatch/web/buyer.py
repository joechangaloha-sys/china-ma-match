"""The buyer's portal: acquisition thesis, verification status, introductions, NDA, data room.

A buyer sees a company only after an approved introduction (seller-approved outreach, or an
analyst-approved request from a public listing), the info memo only after the NDA, and documents
only after the seller grants data-room access. Every document view is logged.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auth, buyers, infomemo, offers, thesis
from ..models import Buyer, Document, Match, User
from ..taxonomy import DEAL_TYPES, FUNDING_EVIDENCE, REGIONS, SECTORS
from .common import back, get_session, not_found, num, render, require

router = APIRouter(prefix="/buyer")
buyer_only = require("buyer")


def _buyer(s: Session, user: User) -> Buyer:
    b = s.get(Buyer, user.buyer_id) if user.buyer_id else None
    if b is None:
        not_found()
    return b


@router.get("", response_class=HTMLResponse)
def buyer_home(request: Request, user: User = Depends(buyer_only), s: Session = Depends(get_session)):
    b = _buyer(s, user)
    deals = s.scalars(select(Match).where(Match.buyer_id == b.id, Match.stage.not_in(["suggested", "shortlisted"]))
                      .order_by(Match.updated_at.desc())).all()
    return render(request, "buyer_home.html", user, portal="buyer", b=b, deals=deals, proposal=None,
                  shared_teaser=offers.shared_teaser, shared_memo=infomemo.shared_memo, after_nda=offers.AFTER_NDA,
                  nda_available=offers.nda_available, nda_text=offers.NDA_TEXT, latest_offer=offers.latest_offer,
                  CONSIDERATION=offers.CONSIDERATION, FINANCING=offers.FINANCING)


@router.post("/thesis/suggest", response_class=HTMLResponse)
def thesis_suggest(request: Request, thesis_text: str = Form(""), user: User = Depends(buyer_only),
                   s: Session = Depends(get_session)):
    """Pre-fill the form from the buyer's own words; nothing is saved until they confirm."""
    b = _buyer(s, user)
    proposal, by = thesis.structure(thesis_text)
    proposal["thesis_text"], proposal["generated_by"] = thesis_text, by
    deals = s.scalars(select(Match).where(Match.buyer_id == b.id, Match.stage.not_in(["suggested", "shortlisted"]))).all()
    return render(request, "buyer_home.html", user, portal="buyer", b=b, deals=deals, proposal=proposal,
                  shared_teaser=offers.shared_teaser, shared_memo=infomemo.shared_memo, after_nda=offers.AFTER_NDA,
                  nda_available=offers.nda_available, nda_text=offers.NDA_TEXT, latest_offer=offers.latest_offer,
                  CONSIDERATION=offers.CONSIDERATION, FINANCING=offers.FINANCING,
                  msg="已根据描述预填，请核对后提交 Pre-filled from your description: check and confirm.")


@router.post("/thesis")
async def thesis_save(request: Request, user: User = Depends(buyer_only), s: Session = Depends(get_session)):
    b = _buyer(s, user)
    f = await request.form()
    try:
        buyers.register(
            b, name=str(f.get("name", "")), kind=str(f.get("kind", b.kind)), uscc=str(f.get("uscc", "")),
            contact_name=str(f.get("contact_name", "")), contact_email=user.email,
            target_sectors=[x for x in f.getlist("target_sectors") if x in SECTORS],
            target_regions=[x for x in f.getlist("target_regions") if x in REGIONS],
            deal_size_min=num(str(f.get("deal_size_min", ""))), deal_size_max=num(str(f.get("deal_size_max", ""))),
            target_deal_types=[x for x in f.getlist("target_deal_types") if x in DEAL_TYPES],
            consent=bool(f.get("consent")), thesis_text=str(f.get("thesis_text", "")),
            excluded_sectors=[x for x in f.getlist("excluded_sectors") if x in SECTORS],
            earnings_min=num(str(f.get("earnings_min", ""))), funding_min=num(str(f.get("funding_min", ""))),
            funding_max=num(str(f.get("funding_max", ""))),
            funding_evidence=str(f.get("funding_evidence", "")) if f.get("funding_evidence") in FUNDING_EVIDENCE else "",
            experience=str(f.get("experience", "")))
    except ValueError as exc:
        return back("/buyer#thesis", str(exc))
    auth.log(s, user, "thesis_saved")
    return back("/buyer", "已保存，顾问审核后即可接收项目 Saved. Once the adviser verifies you, you can receive companies.")


@router.post("/deals/{match_id}/offer")
async def deal_offer(match_id: int, request: Request, user: User = Depends(buyer_only), s: Session = Depends(get_session)):
    b = _buyer(s, user)
    m = s.get(Match, match_id)
    if m is None or m.buyer_id != b.id:
        not_found()
    f = await request.form()
    try:
        offers.submit_offer(
            s, m, user, price_low=num(str(f.get("price_low", ""))), price_high=num(str(f.get("price_high", ""))),
            stake_pct=num(str(f.get("stake_pct", ""))), cash_at_close_pct=num(str(f.get("cash_at_close_pct", ""))),
            consideration=str(f.get("consideration", "")), financing=str(f.get("financing", "")),
            diligence_weeks=num(str(f.get("diligence_weeks", "")), int), target_close=str(f.get("target_close", "")),
            keeps_staff={"yes": True, "no": False}.get(str(f.get("keeps_staff", ""))),
            founder_role=str(f.get("founder_role", "")), conditions=str(f.get("conditions", "")))
    except ValueError as exc:
        return back(f"/buyer#offer-{m.id}", str(exc))
    return back(f"/buyer#offer-{m.id}", "已提交意向报价 Indicative offer submitted")


@router.post("/deals/{match_id}/{action}")
def deal_action(match_id: int, action: str, user: User = Depends(buyer_only), s: Session = Depends(get_session)):
    b = _buyer(s, user)
    m = s.get(Match, match_id)
    if m is None or m.buyer_id != b.id:
        not_found()
    try:
        if action == "interested":
            offers.buyer_respond(s, m, True)
        elif action == "decline":
            offers.buyer_respond(s, m, False)
        elif action == "nda":
            offers.accept_nda(s, m, user)
        else:
            not_found()
    except ValueError as exc:
        return back("/buyer#deals", str(exc))
    auth.log(s, user, f"buyer_{action}", target_id=m.target_id, match_id=m.id)
    return back("/buyer#deals")


@router.get("/documents/{doc_id}")
def document(doc_id: int, user: User = Depends(buyer_only), s: Session = Depends(get_session)):
    b = _buyer(s, user)
    doc = s.get(Document, doc_id)
    if doc is None:
        not_found()
    m = s.scalar(select(Match).where(Match.target_id == doc.target_id, Match.buyer_id == b.id))
    if not offers.can_view_document(m, doc):
        auth.log(s, user, "document_denied", target_id=doc.target_id, document_id=doc.id)
        return PlainTextResponse("Not found", status_code=404)  # returned, not raised, so the log is kept
    auth.log(s, user, "document_view", target_id=doc.target_id, match_id=m.id, document_id=doc.id)
    return FileResponse(Path(doc.stored_path), media_type=doc.content_type or "application/octet-stream",
                        filename=doc.filename, headers={"Cache-Control": "no-store"})
