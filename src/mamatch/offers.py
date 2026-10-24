"""Moving deals between sellers and buyers: private offers, board interest, name disclosure.

Every step that shares something with the other side checks who has agreed to it:
- a private target's teaser goes to a buyer only after the seller approves that buyer, and only
  on the paid plan (plans.seller_outreach);
- a buyer can express interest in a listing only once verified and once the listing is visible
  to them;
- the company name is disclosed to one buyer only after an NDA and the seller's approval. The
  buyer's name is disclosed to the seller at the same moment.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import matching, pipeline, plans
from .models import Buyer, DealEvent, Match, Target, Teaser

AFTER_NDA = {"nda_signed", "im_sent", "loi", "closing", "closed"}


def outreach_candidates(target: Target) -> list[Match]:
    """Shortlisted buyers awaiting the seller's decision: priority members first among equal fits."""
    rows = [m for m in target.matches if m.channel == "offer" and m.stage == "shortlisted"
            and m.seller_approved_at is None]
    return sorted(rows, key=lambda m: (-round(m.score, 1), not plans.is_priority(m.buyer), -m.score))


def shared_teaser(target: Target, language: str = "zh") -> Teaser | None:
    approved = [t for t in target.teasers if t.status == "approved"]
    return next((t for t in approved if t.language == language), approved[0] if approved else None)


def approve_and_send(session: Session, match: Match) -> DealEvent:
    """Seller approves one buyer; the approved teaser goes out at once."""
    target, buyer = match.target, match.buyer
    if not plans.seller_outreach(target):
        raise ValueError("Outreach needs a private target on the paid plan.")
    if buyer.status != "verified":
        raise ValueError("This buyer is not verified yet.")
    if match.stage != "shortlisted":
        raise ValueError("Only shortlisted buyers can be approved for outreach.")
    if shared_teaser(target) is None:
        raise ValueError("The adviser has not approved a teaser yet.")
    match.seller_approved_at = datetime.now(timezone.utc)
    return pipeline.move(session, match, "teaser_sent", "Seller approved; teaser sent")


def decline_candidate(session: Session, match: Match) -> DealEvent:
    return pipeline.move(session, match, "dropped", "Seller declined this buyer")


def buyer_respond(session: Session, match: Match, interested: bool) -> DealEvent:
    if match.stage != "teaser_sent":
        raise ValueError("Nothing to respond to.")
    if interested:
        return pipeline.move(session, match, "interested", "Buyer interested")
    return pipeline.move(session, match, "dropped", "Buyer declined")


def express_interest(session: Session, target: Target, buyer: Buyer) -> Match:
    """A verified, signed-in buyer asks for an introduction to a listed seller."""
    if buyer.status != "verified":
        raise ValueError("您的买方资料尚未通过审核 Your buyer profile is not verified yet.")
    if target.visibility != "listed":
        raise ValueError("该项目已下架 This listing is not available.")
    m = session.scalar(select(Match).where(Match.target_id == target.id, Match.buyer_id == buyer.id))
    if m is not None and m.stage != "dropped":
        return m
    scored = matching.score(target, buyer)
    if m is None:
        m = Match(target=target, buyer=buyer, score=scored.score, reasons=scored.reasons, channel="listing",
                  stage="interested")
        session.add(m)
    else:
        m.stage, m.channel = "interested", "listing"
    session.add(DealEvent(match=m, from_stage="listed", to_stage="interested", note="Interest from the board"))
    session.flush()
    return m


def public_inquiry(session: Session, target: Target, *, name: str, company: str, kind: str, contact: str,
                   message: str, consent: bool) -> Match:
    """Someone responds to a public listing. Recorded for the adviser, who screens them before any NDA."""
    if target.visibility != "listed":
        raise ValueError("该项目已下架 This listing is no longer available.")
    if not consent:
        raise ValueError("请同意顾问就此项目与您联系 Please agree to be contacted about this listing.")
    if not (name.strip() and contact.strip()):
        raise ValueError("请填写姓名和电话或邮箱 Please give your name and a phone number or email.")
    contact = contact.strip()
    buyer = session.scalar(select(Buyer).where(Buyer.source == "inquiry", Buyer.contact_email == contact))
    if buyer is None:
        buyer = Buyer(name=company.strip() or name.strip(), kind=kind, source="inquiry", status="registered",
                      contact_name=name.strip(), contact_email=contact, target_sectors=[target.sector])
        session.add(buyer)
        session.flush()
    note = f"Inquiry: {message.strip()[:500]}" if message.strip() else "Inquiry"
    m = session.scalar(select(Match).where(Match.target_id == target.id, Match.buyer_id == buyer.id))
    if m is None:
        m = Match(target=target, buyer=buyer, score=matching.score(target, buyer).score, reasons=["Public inquiry"],
                  channel="listing", stage="interested")
        session.add(m)
        session.add(DealEvent(match=m, from_stage="listed", to_stage="interested", note=note))
    elif m.stage == "dropped":
        session.add(DealEvent(match=m, from_stage="dropped", to_stage="interested", note=note))
        m.stage = "interested"
    else:  # already in progress: keep the stage, log the message
        session.add(DealEvent(match=m, from_stage=m.stage, to_stage=m.stage, note=note))
    session.flush()
    return m


def disclose_names(match: Match) -> None:
    if match.stage not in AFTER_NDA:
        raise ValueError("Names are disclosed only after an NDA is signed.")
    match.name_disclosed_at = datetime.now(timezone.utc)


NDA_VERSION = "v1-2026-10"
NDA_TEXT = (
    "保密承诺（平台模板，正式使用前需经律师审核）：本人/本机构承诺对通过本平台获得的目标公司信息严格保密，"
    "仅用于评估本次收购，不向第三方披露，不直接或间接绕开顾问与卖方、其员工、客户或供应商接触，"
    "在双方同意披露名称前不尝试识别目标公司。本承诺自接受之日起有效期三年。\n"
    "Confidentiality undertaking (platform template; have it reviewed by counsel before live use): I/we will keep "
    "all information about the company received through this platform confidential, use it only to evaluate this "
    "acquisition, not pass it to third parties, not approach the seller, its staff, customers or suppliers except "
    "through the adviser, and not try to identify the company before names are disclosed. Valid for three years."
)
REJECT_REASONS = {
    "sector": "行业不符 Sector fit", "size": "规模/价格 Size or price", "funding": "资金不足 Funding",
    "geography": "地域 Geography", "conflict": "利益冲突 Conflict", "seller": "卖方限制 Seller restriction",
    "quality": "买方资质 Buyer quality", "other": "其他 Other",
}


def analyst_decision(session: Session, match: Match, user, accept: bool, reason: str = "", note: str = "") -> None:
    """Every recommendation the analyst accepts or rejects is recorded with the reason."""
    from . import auth
    from .models import MatchFeedback

    match.feedback.append(MatchFeedback(user_id=user.id if user else None, decision="accept" if accept else "reject",
                                        reason=reason if reason in REJECT_REASONS else ("" if accept else "other"),
                                        note=note.strip()[:1000]))
    if accept and match.stage == "suggested":
        pipeline.move(session, match, "shortlisted", "Analyst accepted")
    elif not accept and match.stage not in ("dropped", "closed"):
        pipeline.move(session, match, "dropped", f"Analyst rejected: {REJECT_REASONS.get(reason, reason)}")
    auth.log(session, user, "match_decision", target_id=match.target_id, match_id=match.id,
             decision="accept" if accept else "reject", reason=reason)


def nda_available(match: Match) -> bool:
    """The buyer may sign once the introduction is approved: by the seller (outreach) or the analyst (inquiry)."""
    return match.stage == "interested" and (match.seller_approved_at is not None
                                            or any(f.decision == "accept" for f in match.feedback))


def accept_nda(session: Session, match: Match, user) -> None:
    from . import auth

    if not nda_available(match):
        raise ValueError("保密协议尚不可签署 The NDA is not available yet.")
    match.nda_accepted_at = datetime.now(timezone.utc)
    match.nda_version = NDA_VERSION
    pipeline.move(session, match, "nda_signed", f"NDA {NDA_VERSION} accepted online")
    auth.log(session, user, "nda_accept", target_id=match.target_id, match_id=match.id, version=NDA_VERSION)


def grant_data_room(session: Session, match: Match, user) -> None:
    """Seller-approved disclosure: this buyer may open the documents marked for the data room."""
    from . import auth

    if match.stage not in AFTER_NDA:
        raise ValueError("Documents are shared only after an NDA.")
    match.data_room_granted_at = datetime.now(timezone.utc)
    auth.log(session, user, "data_room_grant", target_id=match.target_id, match_id=match.id)


def can_view_document(match: Match | None, doc) -> bool:
    return (match is not None and doc.in_data_room and match.target_id == doc.target_id
            and match.data_room_granted_at is not None and match.stage in AFTER_NDA)
