"""The adviser's portal: prepare sales for clients under each client's own authorisation.

A verified adviser can open a mandate for a client and work on it (company facts, documents,
questionnaire) while the authorisation is active. The client confirms the authorisation in their
own account, and keeps every decision that commits them. Revoked or unconfirmed-and-unverified
mandates show nothing beyond what the adviser entered.
"""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auth, authority, documents, listing
from ..models import Adviser, MandateAuthorization, Target, User
from ..taxonomy import DEAL_TYPES, REGIONS, SALE_REASONS, SECTORS
from .common import anon_buyer, back, firm, get_session, not_found, num, render, require, save_data

router = APIRouter(prefix="/adviser")
adviser_only = require("adviser")


def _adviser(s: Session, user: User) -> Adviser:
    a = s.scalar(select(Adviser).where(Adviser.user_id == user.id))
    return a or not_found()


def _mandate(s: Session, adv: Adviser, target_id: int) -> tuple[Target, MandateAuthorization]:
    t = s.get(Target, target_id)
    a = authority.adviser_authorization(t, adv) if t else None
    if a is None:
        not_found()
    return t, a


@router.get("", response_class=HTMLResponse)
def home(request: Request, user: User = Depends(adviser_only), s: Session = Depends(get_session)):
    adv = _adviser(s, user)
    auths = s.scalars(select(MandateAuthorization).where(MandateAuthorization.adviser_id == adv.id)
                      .order_by(MandateAuthorization.requested_at.desc())).all()
    return render(request, "adviser_home.html", user, portal="adviser", adv=adv, auths=auths,
                  PROFESSIONS=authority.PROFESSIONS)


@router.post("/mandates")
def mandate_create(request: Request, user: User = Depends(adviser_only), s: Session = Depends(get_session),
                   company: str = Form(""), owner_name: str = Form(""), owner_contact: str = Form(""),
                   uscc: str = Form(""), city: str = Form(""), sector: str = Form(""), province: str = Form(""),
                   revenue: str = Form(""), net_profit: str = Form(""), employees: str = Form(""),
                   founded_year: str = Form(""), deal_type: str = Form("full_sale"), sale_reason: str = Form("succession"),
                   notes: str = Form(""), confirm: str = Form("")):
    adv = _adviser(s, user)
    if not confirm:
        return back("/adviser#new", "请确认您已获客户同意提交其信息 Confirm the client agreed to you submitting their information.")
    if not (company.strip() and owner_name.strip() and owner_contact.strip()):
        return back("/adviser#new", "请填写公司、企业主姓名和联系方式 Company, owner name and contact are required.")
    try:
        t = Target(firm=firm(s), code_name="待定 New", legal_name=company.strip()[:200], owner_name=owner_name.strip()[:50],
                   contact_name=owner_name.strip()[:50], contact_info=owner_contact.strip()[:100], uscc=uscc.strip()[:18],
                   city=city.strip()[:50], sector=sector if sector in SECTORS else "industrial_services",
                   province=province if province in REGIONS else "上海", revenue=num(revenue), net_profit=num(net_profit),
                   employees=num(employees, int), founded_year=num(founded_year, int),
                   deal_type=deal_type if deal_type in DEAL_TYPES else "full_sale",
                   sale_reason=sale_reason if sale_reason in SALE_REASONS else "other",
                   description=notes.strip()[:4000], status="draft")
    except ValueError:
        return back("/adviser#new", "数字格式不正确 Figures must be numbers.")
    s.add(t)
    s.flush()
    t.code_name = f"Project {t.id:03d}"
    try:
        authority.start_mandate(s, adv, t)
    except ValueError as exc:
        s.delete(t)
        return back("/adviser", str(exc))
    return RedirectResponse(f"/adviser/{t.id}", status_code=303)


@router.get("/{target_id}", response_class=HTMLResponse)
def mandate(target_id: int, request: Request, user: User = Depends(adviser_only), s: Session = Depends(get_session)):
    adv = _adviser(s, user)
    t, a = _mandate(s, adv, target_id)
    invite = f"{str(request.base_url).rstrip('/')}/invite/{t.seller_token}" if t.seller_token else ""
    return render(request, "adviser_mandate.html", user, portal="adviser", t=t, a=a, adv=adv, card=listing.card(t),
                  invite=invite, missing=documents.missing_kinds(t), anon_buyer=anon_buyer,
                  sent=[m for m in t.matches if m.stage not in ("suggested", "shortlisted")],
                  SCOPES=authority.SCOPES)


@router.post("/{target_id}/documents")
async def upload(target_id: int, kind: str = Form("other"), file: UploadFile = File(...),
                 user: User = Depends(adviser_only), s: Session = Depends(get_session)):
    adv = _adviser(s, user)
    t, a = _mandate(s, adv, target_id)
    if "documents" not in a.scope:
        return back(f"/adviser/{t.id}#documents", "授权范围不含上传文件 Uploading is outside your authorisation.")
    try:
        documents.save(s, t, user, kind, file.filename or "upload", await file.read(documents.MAX_BYTES + 1),
                       file.content_type or "")
    except ValueError as exc:
        return back(f"/adviser/{t.id}#documents", str(exc))
    return back(f"/adviser/{t.id}#documents", "已上传 Uploaded")


@router.post("/{target_id}/data")
async def data(target_id: int, request: Request, user: User = Depends(adviser_only), s: Session = Depends(get_session)):
    adv = _adviser(s, user)
    t, a = _mandate(s, adv, target_id)
    if "documents" not in a.scope:
        return back(f"/adviser/{t.id}#data", "授权范围不含填写问卷 The questionnaire is outside your authorisation.")
    save_data(t, await request.form())
    auth.log(s, user, "adviser_data_saved", target_id=t.id)
    return back(f"/adviser/{t.id}#data", "已保存 Saved")
