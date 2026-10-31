"""Deal-manager pages: mandates, verification, document review, matching, disclosure, pipeline.

Every route here requires a signed-in deal manager. The pages are marked internal on screen.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import (analytics, auth, authority, buyers, datacheck, dealstatus, documents, fees, infomemo, listing, matching, offers,
                pipeline, plans, teaser)
from .. import config, upload_security
from ..models import (Adviser, AuditEvent, Buyer, Document, ExpertReferral, ExtractedField, InfoMemo,
                      MandateAuthorization, Match, Target, Teaser, User)
from ..taxonomy import FOUNDER_TRANSITION, INVENTORY, PAYMENT_TERMS, PERMITS, PREMISES, TIMING
from .common import I, back, firm, get_lang, get_session, not_found, num, render, require, save_data

router = APIRouter(prefix=I)
dm = require("deal_manager")
REFERRAL_KINDS = {"legal": "律师 Legal", "accounting": "会计 Accounting", "tax": "税务 Tax", "diligence": "尽调 Diligence",
                  "financing": "融资 Financing"}


def _t(s: Session, target_id: int) -> Target:
    return s.get(Target, target_id) or not_found()


@router.get("", response_class=HTMLResponse)
def home(request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    targets = s.scalars(select(Target).order_by(Target.created_at.desc())).all()
    inquiries = s.scalars(select(Match).where(Match.channel == "listing", Match.stage == "interested")
                          .order_by(Match.updated_at.desc())).all()
    to_verify = s.scalars(select(Buyer).where(Buyer.status == "registered")).all()
    return render(request, "sellers.html", user, portal="internal", targets=targets, inquiries=inquiries,
                  to_verify=to_verify, firm=firm(s), nda_available=offers.nda_available)


@router.get("/readiness", response_class=HTMLResponse)
def readiness_page(request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    from .. import readiness
    from .common import get_lang
    targets = s.scalars(select(Target).order_by(Target.created_at.desc())).all()
    rows = [readiness.snapshot(t, get_lang(request)) for t in targets]
    return render(request, "readiness.html", user, portal="internal", rows=rows, omit_profile_name=True)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    return render(request, "dashboard.html", user, portal="internal", m=analytics.metrics(s))


@router.get("/audit", response_class=HTMLResponse)
def audit(request: Request, target: int | None = None, user: User = Depends(dm), s: Session = Depends(get_session)):
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(300)
    if target:
        stmt = stmt.where(AuditEvent.target_id == target)
    return render(request, "audit.html", user, portal="internal", events=s.scalars(stmt).all(), target=target)


# ---------------------------------------------------------------- buyers (verification queue)

@router.get("/buyers", response_class=HTMLResponse)
def buyer_queue(request: Request, status: str = "registered", user: User = Depends(dm), s: Session = Depends(get_session)):
    rows = s.scalars(select(Buyer).where(Buyer.status == status, Buyer.source != "cninfo")
                     .order_by(Buyer.updated_at.desc())).all()
    counts = dict(s.execute(select(Buyer.status, func.count(Buyer.id)).where(Buyer.source != "cninfo")
                            .group_by(Buyer.status)).all())
    return render(request, "buyer_queue.html", user, portal="internal", rows=rows, status=status, counts=counts)


@router.post("/buyers/{buyer_id}/verify")
def buyer_verify(buyer_id: int, user: User = Depends(dm), s: Session = Depends(get_session)):
    b = s.get(Buyer, buyer_id) or not_found()
    try:
        buyers.verify(b)
    except ValueError as exc:
        return back(f"{I}/buyers", str(exc))
    auth.log(s, user, "buyer_verified", buyer_id=b.id)
    return back(f"{I}/buyers", f"已认证 Verified: {b.name}")


@router.get("/advisers", response_class=HTMLResponse)
def adviser_queue(request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    rows = s.scalars(select(Adviser).order_by(Adviser.created_at.desc())).all()
    return render(request, "adviser_queue.html", user, portal="internal", rows=rows, PROFESSIONS=authority.PROFESSIONS)


@router.post("/advisers/{adviser_id}/verify")
def adviser_verify(adviser_id: int, user: User = Depends(dm), s: Session = Depends(get_session)):
    a = s.get(Adviser, adviser_id) or not_found()
    authority.verify_adviser(s, a, user)
    return back(f"{I}/advisers", f"已认证 Verified: {a.firm}")


@router.post("/targets/{target_id}/authority")
def authority_verify(target_id: int, note: str = Form(""), user: User = Depends(dm), s: Session = Depends(get_session)):
    t = _t(s, target_id)
    try:
        authority.verify_authority(s, t, user, note)
    except ValueError as exc:
        return back(f"{I}/targets/{t.id}#authority", str(exc))
    return back(f"{I}/targets/{t.id}#authority", "出售权限已核验 Authority to sell verified")


@router.post("/authorizations/{auth_id}/revoke")
def authorization_revoke(auth_id: int, user: User = Depends(dm), s: Session = Depends(get_session)):
    a = s.get(MandateAuthorization, auth_id) or not_found()
    try:
        authority.revoke(s, a, user)
    except ValueError as exc:
        return back(f"{I}/targets/{a.target_id}#authority", str(exc))
    return back(f"{I}/targets/{a.target_id}#authority", "Authorisation revoked")


# ---------------------------------------------------------------- mandates

@router.get("/targets/new", response_class=HTMLResponse)
def target_new(request: Request, user: User = Depends(dm)):
    return render(request, "target_new.html", user, portal="internal")


def _apply_ask(t: Target, f) -> None:
    t.asking_value = num(f.get("asking_value"))
    stake = num(f.get("stake_pct"))
    t.stake_pct = None if stake is None else min(max(stake, 1.0), 100.0)
    t.payment_terms = f.get("payment_terms") if f.get("payment_terms") in PAYMENT_TERMS else ""
    t.founder_transition = f.get("founder_transition") if f.get("founder_transition") in FOUNDER_TRANSITION else ""
    t.keep_employees = {"yes": True, "no": False}.get(f.get("keep_employees"))
    t.timing = f.get("timing") if f.get("timing") in TIMING else ""
    t.premises = f.get("premises") if f.get("premises") in PREMISES else ""
    t.permits = f.get("permits") if f.get("permits") in PERMITS else ""
    t.inventory = f.get("inventory") if f.get("inventory") in INVENTORY else ""
    t.normalized_earnings = num(f.get("normalized_earnings"))
    t.show_earnings = bool(f.get("show_earnings"))
    t.products_zh = str(f.get("products_zh", "")).strip()[:300]
    t.products_en = str(f.get("products_en", "")).strip()[:300]


@router.post("/targets")
async def target_create(request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    from ..buyers import new_token

    f = await request.form()
    t = Target(
        firm=firm(s), code_name=str(f.get("code_name", "")).strip(), legal_name=str(f.get("legal_name", "")).strip(),
        short_name=str(f.get("short_name", "")).strip(), owner_name=str(f.get("owner_name", "")).strip(),
        city=str(f.get("city", "")).strip(), uscc=str(f.get("uscc", "")).strip(),
        brands=[b.strip() for b in str(f.get("brands", "")).replace("，", ",").split(",") if b.strip()],
        province=str(f.get("province", "上海")), sector=str(f.get("sector", "machinery")),
        description=str(f.get("description", "")).strip(), founded_year=num(f.get("founded_year"), int),
        employees=num(f.get("employees"), int), revenue=num(f.get("revenue")), net_profit=num(f.get("net_profit")),
        deal_type=str(f.get("deal_type", "full_sale")), sale_reason=str(f.get("sale_reason", "succession")),
        seller_token=new_token(),
    )
    if not t.code_name or not t.legal_name:
        return back(f"{I}/targets/new", "代号和公司名称必填 Code name and legal name are required.")
    _apply_ask(t, f)
    s.add(t)
    s.flush()
    auth.log(s, user, "mandate_created", target_id=t.id)
    return RedirectResponse(f"{I}/targets/{t.id}", status_code=303)


@router.get("/targets/{target_id}", response_class=HTMLResponse)
def target_detail(target_id: int, request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    t = _t(s, target_id)
    invite = f"{str(request.base_url).rstrip('/')}/invite/{t.seller_token}" if t.seller_token else ""
    seller = s.get(User, t.seller_user_id) if t.seller_user_id else None
    return render(request, "target.html", user, portal="internal", t=t, facts=teaser.facts(t), card=listing.card(t),
                  invite=invite, seller=seller, next_statuses=dealstatus.allowed_next(t.status),
                  missing=documents.missing_kinds(t), referral_kinds=REFERRAL_KINDS,
                  OWNER_ROLES=authority.OWNER_ROLES, PROFESSIONS=authority.PROFESSIONS,
                  offer_rows=offers.offer_table(t),
                  nda_available=offers.nda_available, reports=listing.reports(s, t),
                  REPORT_REASONS=listing.REPORT_REASONS)


@router.post("/targets/{target_id}/status")
def target_status(target_id: int, to: str = Form(...), note: str = Form(""), user: User = Depends(dm),
                  s: Session = Depends(get_session)):
    t = _t(s, target_id)
    try:
        dealstatus.move(s, t, to, user, note)
    except ValueError as exc:
        return back(f"{I}/targets/{t.id}", str(exc))
    return back(f"{I}/targets/{t.id}")


@router.post("/targets/{target_id}/ask")
async def target_ask(target_id: int, request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    t = _t(s, target_id)
    _apply_ask(t, await request.form())
    auth.log(s, user, "ask_updated", target_id=t.id)
    return back(f"{I}/targets/{t.id}#listing", "Ask updated")


@router.post("/targets/{target_id}/teaser")
def target_teaser(target_id: int, language: str = Form("zh"), user: User = Depends(dm), s: Session = Depends(get_session)):
    t = _t(s, target_id)
    if language not in teaser.LANGUAGES:
        raise HTTPException(400, "Unknown language")
    tz = teaser.draft(s, t, language)
    auth.log(s, user, "teaser_draft", target_id=t.id, teaser_id=tz.id, generated_by=tz.generated_by)
    return RedirectResponse(f"{I}/targets/{t.id}#teasers", status_code=303)


@router.post("/teasers/{teaser_id}/approve")
def teaser_approve(teaser_id: int, user: User = Depends(dm), s: Session = Depends(get_session)):
    tz = s.get(Teaser, teaser_id) or not_found()
    try:
        teaser.approve(tz, user)
    except ValueError as exc:
        return back(f"{I}/targets/{tz.target_id}#teasers", str(exc))
    auth.log(s, user, "teaser_approve", target_id=tz.target_id, teaser_id=tz.id, content_hash=tz.analyst_content_hash)
    if tz.target.status in ("draft", "documents_requested", "extraction_review"):
        tz.target.status = "seller_approval"
    return back(f"{I}/targets/{tz.target_id}#teasers", "已批准，等待卖方确认 Approved; waiting for the seller")


@router.post("/targets/{target_id}/visibility")
def target_visibility(target_id: int, visibility: str = Form(...), user: User = Depends(dm),
                      s: Session = Depends(get_session)):
    t = _t(s, target_id)
    try:
        listing.publish(t) if visibility == "listed" else listing.unpublish(t)
    except ValueError as exc:
        return back(f"{I}/targets/{t.id}#listing", str(exc))
    auth.log(s, user, "visibility_change", target_id=t.id, visibility=t.visibility)
    return back(f"{I}/targets/{t.id}#listing", "Listed publicly (anonymised)" if t.visibility == "listed"
                else "Removed from the public listings")


@router.post("/targets/{target_id}/plan")
def target_plan(target_id: int, invoice_ref: str = Form(""), user: User = Depends(dm), s: Session = Depends(get_session)):
    t = _t(s, target_id)
    if not invoice_ref.strip():
        return back(f"{I}/targets/{t.id}#fees", "Enter the invoice reference")
    plans.mark_seller_paid(t, invoice_ref)
    auth.log(s, user, "fee_recorded", target_id=t.id, kind="outreach")
    return back(f"{I}/targets/{t.id}#fees", "Outreach retainer recorded as paid")


@router.post("/targets/{target_id}/prep-pack")
def target_prep_pack(target_id: int, invoice_ref: str = Form(""), user: User = Depends(dm),
                     s: Session = Depends(get_session)):
    t = _t(s, target_id)
    if not invoice_ref.strip():
        return back(f"{I}/targets/{t.id}#fees", "Enter the invoice reference")
    try:
        fees.record_prep_pack(t, invoice_ref)
    except ValueError as exc:
        return back(f"{I}/targets/{t.id}#fees", str(exc))
    auth.log(s, user, "fee_recorded", target_id=t.id, kind="prep_pack")
    return back(f"{I}/targets/{t.id}#fees", "Preparation pack recorded as paid")


@router.post("/targets/{target_id}/data")
async def target_data(target_id: int, request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    t = _t(s, target_id)
    save_data(t, await request.form())
    auth.log(s, user, "data_saved", target_id=t.id)
    return back(f"{I}/targets/{t.id}#data", "Data saved")


@router.post("/targets/{target_id}/datacheck")
def target_datacheck(target_id: int, user: User = Depends(dm), s: Session = Depends(get_session)):
    t = _t(s, target_id)
    try:
        dc = datacheck.run(s, t)
    except ValueError as exc:
        return back(f"{I}/targets/{t.id}#data", str(exc))
    auth.log(s, user, "data_check", target_id=t.id, findings=len(dc.findings), generated_by=dc.generated_by)
    return back(f"{I}/targets/{t.id}#data")


@router.post("/targets/{target_id}/memo")
def target_memo(target_id: int, language: str = Form("zh"), user: User = Depends(dm), s: Session = Depends(get_session)):
    t = _t(s, target_id)
    try:
        m = infomemo.draft(s, t, language)
    except ValueError as exc:
        return back(f"{I}/targets/{t.id}#memo", str(exc))
    auth.log(s, user, "memo_draft", target_id=t.id, memo_id=m.id)
    return back(f"{I}/targets/{t.id}#memo")


@router.post("/memos/{memo_id}/approve")
def memo_approve(memo_id: int, user: User = Depends(dm), s: Session = Depends(get_session)):
    m = s.get(InfoMemo, memo_id) or not_found()
    try:
        infomemo.approve(m, user)
    except ValueError as exc:
        return back(f"{I}/targets/{m.target_id}#memo", str(exc))
    auth.log(s, user, "memo_approve", target_id=m.target_id, memo_id=m.id, content_hash=m.analyst_content_hash)
    return back(f"{I}/targets/{m.target_id}#memo", "Info memo approved")


# ---------------------------------------------------------------- documents and extraction

@router.post("/targets/{target_id}/documents")
async def doc_upload(target_id: int, kind: str = Form("other"), file: UploadFile = File(...), user: User = Depends(dm),
                     s: Session = Depends(get_session)):
    t = _t(s, target_id)
    try:
        documents.save(s, t, user, kind, file.filename or "upload", await file.read(documents.MAX_BYTES + 1),
                       file.content_type or "")
    except ValueError as exc:
        return back(f"{I}/targets/{t.id}#documents", str(exc))
    return back(f"{I}/targets/{t.id}#documents", "Uploaded")


@router.get("/documents/{doc_id}")
def doc_view(doc_id: int, request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    doc = s.get(Document, doc_id) or not_found()
    if not upload_security.usable(doc):
        return PlainTextResponse("文件已隔离或不可用。" if get_lang(request) == "zh" else "File is quarantined or unavailable.", status_code=423)
    auth.log(s, user, "document_view", target_id=doc.target_id, document_id=doc.id)
    return FileResponse(Path(doc.stored_path), media_type=doc.content_type or "application/octet-stream",
                        filename=doc.filename, headers={"Cache-Control": "no-store"})


@router.post("/documents/{doc_id}/extract")
def doc_extract(doc_id: int, user: User = Depends(dm), s: Session = Depends(get_session)):
    doc = s.get(Document, doc_id) or not_found()
    if not upload_security.usable(doc):
        return back(f"{I}/upload-security", "文件尚未通过安全检查 File has not passed security checks.")
    fields = documents.extract(s, doc, user)
    if doc.target.status in ("draft", "documents_requested"):
        doc.target.status = "extraction_review"
    return back(f"{I}/targets/{doc.target_id}#documents", f"{len(fields)} 个数字待审核 figures to review")


@router.post("/documents/{doc_id}/data-room")
def doc_data_room(doc_id: int, user: User = Depends(dm), s: Session = Depends(get_session)):
    doc = s.get(Document, doc_id) or not_found()
    if not upload_security.usable(doc):
        return back(f"{I}/upload-security", "文件尚未通过安全检查 File has not passed security checks.")
    doc.in_data_room = not doc.in_data_room
    auth.log(s, user, "data_room_flag", target_id=doc.target_id, document_id=doc.id, in_data_room=doc.in_data_room)
    return back(f"{I}/targets/{doc.target_id}#documents")


@router.post("/fields/{field_id}/review")
def field_review(field_id: int, decision: str = Form(...), value: str = Form(""), user: User = Depends(dm),
                 s: Session = Depends(get_session)):
    f = s.get(ExtractedField, field_id) or not_found()
    try:
        corrected = num(value)
    except ValueError:
        return back(f"{I}/targets/{f.target_id}#documents", "Value must be a number")
    try:
        documents.review(s, f, user, decision == "confirm", corrected)
    except ValueError as exc:
        return back(f"{I}/targets/{f.target_id}#documents", str(exc))
    return back(f"{I}/targets/{f.target_id}#documents")


# ---------------------------------------------------------------- matching and pipeline

@router.post("/targets/{target_id}/match")
def target_match(target_id: int, user: User = Depends(dm), s: Session = Depends(get_session)):
    t = _t(s, target_id)
    matching.refresh(s, t)
    auth.log(s, user, "matching_run", target_id=t.id)
    return RedirectResponse(f"{I}/targets/{t.id}#matches", status_code=303)


@router.post("/matches/{match_id}/decision")
def match_decision(match_id: int, decision: str = Form(...), reason: str = Form(""), note: str = Form(""),
                   user: User = Depends(dm), s: Session = Depends(get_session)):
    m = s.get(Match, match_id) or not_found()
    try:
        offers.analyst_decision(s, m, user, decision == "accept", reason, note)
    except ValueError as exc:
        return back(f"{I}/targets/{m.target_id}#matches", str(exc))
    return back(f"{I}/targets/{m.target_id}#matches")


@router.post("/matches/{match_id}/close")
def match_close(match_id: int, deal_value: str = Form(""), invoice_ref: str = Form(""), user: User = Depends(dm),
                s: Session = Depends(get_session)):
    m = s.get(Match, match_id) or not_found()
    try:
        charge = fees.record_closing(s, m, num(deal_value) or 0, invoice_ref)
    except ValueError as exc:
        return back(f"{I}/targets/{m.target_id}#fees", str(exc))
    m.target.status = "closed"
    auth.log(s, user, "deal_closed", target_id=m.target_id, match_id=m.id, value=m.target.closing_value)
    msg = f"Closed. Success fee RMB {charge.amount:,.0f}" if charge else "Closed. No success fee (listed-only seller)."
    return back(f"{I}/targets/{m.target_id}#fees", msg)


@router.post("/matches/{match_id}/move")
def match_move(match_id: int, to_stage: str = Form(...), note: str = Form(""), back_to: str = Form("", alias="back"),
               user: User = Depends(dm), s: Session = Depends(get_session)):
    m = s.get(Match, match_id) or not_found()
    dest = back_to if back_to.startswith(I) else f"{I}/targets/{m.target_id}#matches"
    if to_stage == "teaser_sent":
        return back(dest, "Teasers go out only when the seller approves the buyer.")
    if to_stage == "nda_signed":
        return back(dest, "The buyer signs the NDA in their portal.")
    if to_stage == "closed":
        return back(f"{I}/targets/{m.target_id}#fees", "Record the closing value on the target page to close a deal.")
    try:
        pipeline.move(s, m, to_stage, note)
    except ValueError as exc:
        return back(dest, str(exc))
    auth.log(s, user, "stage_change", target_id=m.target_id, match_id=m.id, to_stage=to_stage)
    return back(dest)


@router.post("/targets/{target_id}/referrals")
def referral_add(target_id: int, kind: str = Form(...), partner: str = Form(...), contact: str = Form(""),
                 note: str = Form(""), user: User = Depends(dm), s: Session = Depends(get_session)):
    t = _t(s, target_id)
    if kind not in REFERRAL_KINDS or not partner.strip():
        return back(f"{I}/targets/{t.id}#referrals", "Choose a type and enter the partner")
    t.referrals.append(ExpertReferral(kind=kind, partner=partner.strip(), contact=contact.strip(), note=note.strip()))
    auth.log(s, user, "referral_added", target_id=t.id, kind=kind)
    return back(f"{I}/targets/{t.id}#referrals")


@router.post("/referrals/{ref_id}/status")
def referral_status(ref_id: int, status: str = Form(...), user: User = Depends(dm), s: Session = Depends(get_session)):
    r = s.get(ExpertReferral, ref_id) or not_found()
    if status in ("proposed", "engaged", "done"):
        r.status = status
    return back(f"{I}/targets/{r.target_id}#referrals")


@router.get("/pipeline", response_class=HTMLResponse)
def pipeline_view(request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    rows = s.scalars(select(Match).where(Match.stage != "suggested").order_by(Match.updated_at.desc())).all()
    by_stage = {k: [m for m in rows if m.stage == k] for k in pipeline.STAGES if k != "suggested"}
    return render(request, "pipeline.html", user, portal="internal", by_stage=by_stage, allowed_next=pipeline.allowed_next)


@router.get("/review/{kind}/{artifact_id}", response_class=HTMLResponse)
def document_review(kind: str, artifact_id: int, request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    from .. import release
    artifact = _review_artifact(s, kind, artifact_id)
    checked = {r.claim_path: r for r in release.reviews(artifact)}
    return render(request, "document_review.html", user, portal="internal", a=artifact, kind=kind,
                  claims=release.assertions(artifact.body), checked=checked,
                  errors=release.validation_errors(artifact))


def _review_artifact(s, kind, artifact_id):
    if kind not in ('teaser', 'memo'):
        not_found()
    return s.get(Teaser if kind == 'teaser' else InfoMemo, artifact_id) or not_found()


@router.post("/review/{kind}/{artifact_id}")
def review_assertion(kind: str, artifact_id: int, claim_path: str = Form(''), evidence_ref: str = Form(''), document_id: int = Form(0),
                     user: User = Depends(dm), s: Session = Depends(get_session)):
    from .. import release
    artifact = _review_artifact(s, kind, artifact_id)
    try:
        record = release.review_claim(artifact, claim_path, evidence_ref, user, document_id)
        auth.log(s, user, 'claim_evidence_reviewed', target_id=artifact.target_id,
                 claim_path=claim_path, content_hash=record.content_hash, evidence_ref=record.evidence_ref)
    except ValueError as exc:
        return back(f'{I}/review/{kind}/{artifact_id}', str(exc))
    return back(f'{I}/review/{kind}/{artifact_id}', '证据审核已记录 Evidence review recorded')


@router.get('/upload-security', response_class=HTMLResponse)
def upload_queue(request: Request, user: User = Depends(dm), s: Session = Depends(get_session)):
    return render(request, 'upload_security.html', user, portal='internal', omit_profile_name=True,
                  scanner_configured=bool(config.CLAMSCAN_PATH),
                  docs=s.scalars(select(Document).order_by(Document.created_at.desc())).all())


@router.post('/documents/{doc_id}/scan')
def document_scan(doc_id: int, user: User = Depends(dm), s: Session = Depends(get_session)):
    doc = s.get(Document, doc_id) or not_found()
    documents.scan(s, doc, user)
    return back(f'{I}/upload-security')
