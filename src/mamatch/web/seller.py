"""The seller's portal: process status, documents, teaser approval, buyer approvals, disclosure.

A seller only ever reaches mandates linked to their own account; buyers appear anonymised until
both sides agree to disclose names.
"""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auth, documents, listing, offers, plans, teaser
from ..models import Match, Target, Teaser, User
from .common import anon_buyer, back, get_session, not_found, render, require, save_data, seller_reasons

router = APIRouter(prefix="/seller")
seller_only = require("seller")


def _mine(s: Session, user: User, target_id: int) -> Target:
    t = s.get(Target, target_id)
    if t is None or t.seller_user_id != user.id:
        not_found()
    return t


@router.get("", response_class=HTMLResponse)
def seller_home(request: Request, user: User = Depends(seller_only), s: Session = Depends(get_session)):
    rows = s.scalars(select(Target).where(Target.seller_user_id == user.id)).all()
    if len(rows) == 1:
        return RedirectResponse(f"/seller/{rows[0].id}", status_code=303)
    return render(request, "seller_home.html", user, portal="seller", rows=rows)


@router.get("/{target_id}", response_class=HTMLResponse)
def seller_page(target_id: int, request: Request, user: User = Depends(seller_only), s: Session = Depends(get_session)):
    t = _mine(s, user, target_id)
    outreach = plans.seller_outreach(t)
    latest_teaser = next((tz for tz in t.teasers if tz.status == "approved"), None)
    return render(request, "seller.html", user, portal="seller", t=t, card=listing.card(t), outreach=outreach,
                  candidates=offers.outreach_candidates(t) if outreach else [],
                  sent=[m for m in t.matches if m.stage not in ("suggested", "shortlisted")],
                  anon_buyer=anon_buyer, seller_reasons=seller_reasons, after_nda=offers.AFTER_NDA,
                  latest_teaser=latest_teaser, missing=documents.missing_kinds(t),
                  memo=next(iter(t.memos), None))


@router.post("/{target_id}/teasers/{teaser_id}/approve")
def seller_teaser_approve(target_id: int, teaser_id: int, user: User = Depends(seller_only),
                          s: Session = Depends(get_session)):
    t = _mine(s, user, target_id)
    tz = s.get(Teaser, teaser_id)
    if tz is None or tz.target_id != t.id:
        not_found()
    try:
        teaser.seller_approve(tz)
    except ValueError as exc:
        return back(f"/seller/{t.id}#teaser", str(exc))
    auth.log(s, user, "teaser_seller_approve", target_id=t.id, teaser_id=tz.id)
    return back(f"/seller/{t.id}#teaser", "已确认简介 Teaser approved")


@router.post("/{target_id}/visibility")
def seller_visibility(target_id: int, visibility: str = Form(...), user: User = Depends(seller_only),
                      s: Session = Depends(get_session)):
    t = _mine(s, user, target_id)
    try:
        if visibility == "listed":
            listing.publish(t)
        else:
            listing.unpublish(t)
    except ValueError as exc:
        return back(f"/seller/{t.id}#listing", str(exc))
    auth.log(s, user, "visibility_change", target_id=t.id, visibility=t.visibility)
    return back(f"/seller/{t.id}#listing", "已更新 Updated")


@router.post("/{target_id}/documents")
async def seller_upload(target_id: int, kind: str = Form("other"), file: UploadFile = File(...),
                        user: User = Depends(seller_only), s: Session = Depends(get_session)):
    t = _mine(s, user, target_id)
    data = await file.read(documents.MAX_BYTES + 1)
    try:
        documents.save(s, t, user, kind, file.filename or "upload", data, file.content_type or "")
    except ValueError as exc:
        return back(f"/seller/{t.id}#documents", str(exc))
    if t.status == "draft":
        t.status = "documents_requested"
    return back(f"/seller/{t.id}#documents", "已上传 Uploaded")


@router.post("/{target_id}/data")
async def seller_data(target_id: int, request: Request, user: User = Depends(seller_only),
                      s: Session = Depends(get_session)):
    t = _mine(s, user, target_id)
    save_data(t, await request.form())
    auth.log(s, user, "seller_data_saved", target_id=t.id)
    return back(f"/seller/{t.id}#data", "已保存，顾问会审核 Saved; your adviser will review it.")


@router.post("/{target_id}/matches/{match_id}/{action}")
def seller_match_action(target_id: int, match_id: int, action: str, user: User = Depends(seller_only),
                        s: Session = Depends(get_session)):
    t = _mine(s, user, target_id)
    m = s.get(Match, match_id)
    if m is None or m.target_id != t.id:
        not_found()
    try:
        if action == "approve":
            offers.approve_and_send(s, m)
            msg = "已发送简介 Teaser sent to this buyer"
        elif action == "decline":
            offers.decline_candidate(s, m)
            msg = "已跳过 Buyer skipped"
        elif action == "grant":
            offers.grant_data_room(s, m, user)
            msg = "已开放资料室 Data room opened to this buyer"
        elif action == "disclose":
            offers.disclose_names(m)
            msg = "已互相披露名称 Names disclosed to each other"
        else:
            not_found()
    except ValueError as exc:
        msg = str(exc)
    auth.log(s, user, f"seller_{action}", target_id=t.id, match_id=m.id)
    return back(f"/seller/{t.id}#buyers", msg)
