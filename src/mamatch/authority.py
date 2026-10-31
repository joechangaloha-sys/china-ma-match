"""Who may sell, and who may act for the seller.

Nothing about a company reaches buyers until a deal manager has verified the owner's authority to
sell: the owner states their role (legal representative, controlling shareholder, ...) when they
open their account, and the deal manager checks it against the business licence and shareholder
documents in the file.

An accountant, lawyer or consultant can prepare a sale for a client, but only as a verified adviser
(professional licence and firm checked) and only under the owner's own authorisation for that sale,
which the owner accepts in their own account and can revoke at any time. Approvals that commit the
owner (teaser, publication, which buyers see it, disclosure of the name) always stay with the owner.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from . import auth
from .buyers import new_token
from .models import Adviser, MandateAuthorization, Target, User

PROFESSIONS = {"accountant": "会计师 Accountant", "lawyer": "律师 Lawyer", "consultant": "财务/并购顾问 Financial or M&A adviser",
               "other": "其他专业人士 Other professional"}
OWNER_ROLES = {"legal_rep": "法定代表人 Legal representative", "shareholder": "股东 Shareholder",
               "director": "董事/执行董事 Director", "authorised": "经股东会授权 Authorised by the shareholders"}
SCOPES = {"prepare": "准备并提交出售资料 Prepare and submit sale materials",
          "documents": "代为上传文件、填写问卷 Upload documents and answer the questionnaire",
          "liaise": "与交易经理和买方沟通（不含决定）Liaise with the deal manager and buyers (no decisions)"}
DEFAULT_SCOPE = list(SCOPES)
TEXT_VERSION = "auth-v1-2026-10"
AUTH_TEXT = (
    "授权书（平台模板，正式使用前需经律师审核）：本人确认本人有权出售或安排出售上述企业的股权或业务，"
    "并授权下列顾问在所列范围内代表本人处理本次出售事宜。简介确认、公开挂牌、向哪些买方发送资料以及披露公司名称，"
    "仍须由本人在本人账户中决定。本人可随时撤回本授权。\n"
    "Authorisation (platform template; to be reviewed by counsel before live use): I confirm that I am entitled to "
    "sell, or to arrange the sale of, the shares or business of the company above, and I authorise the adviser below "
    "to act for me in this sale within the scope listed. Approving the teaser, publishing a listing, choosing which "
    "buyers receive information and disclosing the company's name remain my decisions, taken in my own account. "
    "I may revoke this authorisation at any time."
)
ACTIVE = ("requested", "owner_confirmed", "verified")
STATUS = {"requested": "待客户确认 Waiting for the client", "owner_confirmed": "待交易经理核验 Being verified",
          "verified": "已生效 Active", "revoked": "已撤回 Revoked"}


def register_adviser(session: Session, user: User, *, firm: str, profession: str, license_no: str,
                     firm_uscc: str) -> Adviser:
    if profession not in PROFESSIONS:
        raise ValueError("Unknown profession")
    if not firm.strip() or not license_no.strip():
        raise ValueError("请填写机构名称和执业证书编号 Firm and professional licence number are required.")
    a = Adviser(user_id=user.id, firm=firm.strip()[:200], profession=profession, license_no=license_no.strip()[:60],
                firm_uscc=firm_uscc.strip().upper()[:18])
    session.add(a)
    session.flush()
    auth.log(session, user, "adviser_registered", adviser_id=a.id)
    return a


def verify_adviser(session: Session, adviser: Adviser, by: User) -> None:
    """Deal manager has checked the licence with the issuing body and the firm with the business registry."""
    adviser.status, adviser.verified_at = "verified", datetime.now(timezone.utc)
    auth.log(session, by, "adviser_verified", adviser_id=adviser.id)


def start_mandate(session: Session, adviser: Adviser, target: Target, scope: list[str] | None = None) -> MandateAuthorization:
    """A verified adviser prepares a sale; the owner is invited to confirm it and the authorisation."""
    if adviser.status != "verified":
        raise ValueError("顾问资格尚未通过审核 Your adviser profile is not verified yet.")
    target.submitted_by, target.adviser_firm = "adviser", adviser.firm
    target.seller_token = target.seller_token or new_token()
    a = MandateAuthorization(adviser_id=adviser.id, scope=[s for s in (scope or DEFAULT_SCOPE) if s in SCOPES],
                             text_version=TEXT_VERSION)
    target.authorizations.append(a)
    session.flush()
    auth.log(session, adviser.user, "authorization_requested", target_id=target.id, adviser_id=adviser.id)
    return a


def owner_confirm(session: Session, target: Target, owner: User, *, role: str, share_pct: float | None,
                  accept_authorizations: bool) -> None:
    """The owner, in their own account, states their authority and accepts any pending adviser authorisation."""
    if role not in OWNER_ROLES:
        raise ValueError("请选择您在公司中的身份 Please choose your role in the company.")
    if role == "shareholder" and (share_pct is None or not 0 < share_pct <= 100):
        raise ValueError("请填写持股比例 Please give your shareholding.")
    pending = [a for a in target.authorizations if a.status == "requested"]
    if pending and not accept_authorizations:
        raise ValueError("请确认对顾问的授权 Please confirm the adviser's authorisation.")
    now = datetime.now(timezone.utc)
    target.owner_role, target.owner_share_pct, target.owner_confirmed_at = role, share_pct, now
    for a in pending:
        a.status, a.owner_user_id, a.confirmed_at = "owner_confirmed", owner.id, now
        auth.log(session, owner, "authorization_confirmed", target_id=target.id, adviser_id=a.adviser_id,
                 version=a.text_version)
    auth.log(session, owner, "owner_authority_stated", target_id=target.id, role=role, share_pct=share_pct)


def verify_authority(session: Session, target: Target, by: User, note: str = "") -> None:
    """Deal manager checked the owner's stated role against the business licence and ownership documents."""
    if target.owner_confirmed_at is None:
        raise ValueError("The owner has not confirmed their authority yet.")
    from . import upload_security
    kinds = {d.kind for d in target.documents if upload_security.usable(d)}
    if not {"license", "ownership"} <= kinds:
        raise ValueError("Upload the business licence and the ownership documents before verifying authority.")
    now = datetime.now(timezone.utc)
    target.authority_verified_at, target.authority_verified_by = now, by.id
    target.authority_note = note.strip()[:1000]
    for a in target.authorizations:
        if a.status == "owner_confirmed":
            a.status, a.verified_at = "verified", now
    auth.log(session, by, "authority_verified", target_id=target.id, note=target.authority_note)


def revoke(session: Session, a: MandateAuthorization, by: User) -> None:
    if a.status not in ACTIVE:
        raise ValueError("This authorisation is not active.")
    a.status, a.revoked_at = "revoked", datetime.now(timezone.utc)
    auth.log(session, by, "authorization_revoked", target_id=a.target_id, adviser_id=a.adviser_id)


def adviser_authorization(target: Target, adviser: Adviser | None) -> MandateAuthorization | None:
    if adviser is None:
        return None
    return next((a for a in target.authorizations if a.adviser_id == adviser.id and a.status in ACTIVE), None)


def can_market(target: Target) -> bool:
    return target.authority_verified_at is not None
