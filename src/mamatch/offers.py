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

from . import matching, pipeline, plans, release
from .models import Buyer, DealEvent, Match, Target, Teaser

AFTER_NDA = {"nda_signed", "im_sent", "loi", "closing", "closed"}


def outreach_candidates(target: Target) -> list[Match]:
    """Shortlisted buyers awaiting the seller's decision, best fit first."""
    rows = [m for m in target.matches if m.channel == "offer" and m.stage == "shortlisted"
            and m.seller_approved_at is None]
    return sorted(rows, key=lambda m: -m.score)


def shared_teaser(target: Target, language: str = "zh") -> Teaser | None:
    approved = [t for t in target.teasers if release.ready(t)]
    return next((t for t in approved if t.language == language), None)


def approve_and_send(session: Session, match: Match) -> DealEvent:
    """Seller approves one buyer; the approved teaser goes out at once."""
    target, buyer = match.target, match.buyer
    if not plans.seller_outreach(target):
        raise ValueError("Outreach needs a private target on the paid plan.")
    if target.authority_verified_at is None:
        raise ValueError("卖方的出售权限尚未核验 The owner's authority to sell has not been verified yet.")
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
    if not match.target.is_example:
        raise ValueError("Real name disclosure requires a verified NDA and external VDR handoff.")
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

    if not match.target.is_example:
        raise ValueError("A verified e-signature provider is required for real mandates.")
    if not nda_available(match):
        raise ValueError("保密协议尚不可签署 The NDA is not available yet.")
    match.nda_accepted_at = datetime.now(timezone.utc)
    match.nda_version = NDA_VERSION
    pipeline.move(session, match, "nda_signed", f"NDA {NDA_VERSION} accepted online")
    auth.log(session, user, "nda_accept", target_id=match.target_id, match_id=match.id, version=NDA_VERSION)


def grant_data_room(session: Session, match: Match, user) -> None:
    """Seller-approved disclosure: this buyer may open the documents marked for the data room."""
    from . import auth

    if not match.target.is_example:
        raise ValueError("Real documents must be shared through an approved professional VDR.")
    if match.stage not in AFTER_NDA:
        raise ValueError("Documents are shared only after an NDA.")
    match.data_room_granted_at = datetime.now(timezone.utc)
    auth.log(session, user, "data_room_grant", target_id=match.target_id, match_id=match.id)


def can_view_document(match: Match | None, doc) -> bool:
    return (match is not None and match.target.is_example and doc.in_data_room and match.target_id == doc.target_id
            and match.data_room_granted_at is not None and match.stage in AFTER_NDA)


# ---------------------------------------------------------------- indicative offers (after NDA)

CONSIDERATION = {"cash": "全部现金 All cash", "cash_earnout": "现金 + 业绩对赌 Cash plus earn-out",
                 "cash_deferred": "现金 + 分期支付 Cash plus deferred payment", "shares": "含股份支付 Partly in shares"}
FINANCING = {"own_funds": "自有资金 Own funds", "bank_loan": "银行并购贷款 Bank acquisition loan",
             "fund": "基金出资 Fund capital", "mixed": "组合 Mixed"}


def latest_offer(match: Match):
    return match.offers[0] if match.offers else None


def submit_offer(session: Session, match: Match, user, *, price_low: float | None, price_high: float | None,
                 stake_pct: float | None, cash_at_close_pct: float | None, consideration: str, financing: str,
                 diligence_weeks: int | None, target_close: str, keeps_staff: bool | None, founder_role: str,
                 conditions: str):
    """A buyer who has signed the NDA submits (or revises) a non-binding indication of interest."""
    from . import auth
    from .models import IndicativeOffer
    from .taxonomy import FOUNDER_TRANSITION, TIMING

    if not match.target.is_example:
        raise ValueError("A verified NDA workflow is required for real mandates.")
    if match.stage not in AFTER_NDA or match.stage == "closed":
        raise ValueError("签署保密协议后才能提交意向报价 Offers can be submitted only after the NDA.")
    if price_low is None or price_high is None or price_low <= 0 or price_high < price_low:
        raise ValueError("请填写有效的价格区间 Enter a valid price range.")
    stake = stake_pct if stake_pct is not None else 100.0
    cash = cash_at_close_pct if cash_at_close_pct is not None else 100.0
    if not (0 < stake <= 100 and 0 <= cash <= 100):
        raise ValueError("比例应在0到100之间 Percentages must be between 0 and 100.")
    o = IndicativeOffer(price_low=price_low, price_high=price_high, stake_pct=stake, cash_at_close_pct=cash,
                        consideration=consideration if consideration in CONSIDERATION else "cash",
                        financing=financing if financing in FINANCING else "own_funds",
                        diligence_weeks=diligence_weeks, target_close=target_close if target_close in TIMING else "",
                        keeps_staff=keeps_staff, founder_role=founder_role if founder_role in FOUNDER_TRANSITION else "",
                        conditions=conditions.strip()[:2000])
    match.offers.insert(0, o)
    session.flush()
    auth.log(session, user, "offer_submitted", target_id=match.target_id, match_id=match.id,
             price_low=price_low, price_high=price_high, stake=stake)
    return o


def offer_table(target: Target) -> list[tuple[Match, object]]:
    """The latest offer from each buyer still in the process, highest midpoint first."""
    rows = [(m, latest_offer(m)) for m in target.matches if m.offers and m.stage not in ("dropped",)]
    return sorted(rows, key=lambda r: -(r[1].price_low + r[1].price_high) / 2 * 100 / (r[1].stake_pct or 100))


def approve_many(session: Session, target: Target, match_ids: list[int], user) -> tuple[int, list[str]]:
    """Seller sends the teaser to several shortlisted buyers at once; skipped buyers stay shortlisted."""
    from . import auth

    sent, errors = 0, []
    wanted = set(match_ids)
    for m in outreach_candidates(target):
        if m.id not in wanted:
            continue
        try:
            approve_and_send(session, m)
            sent += 1
        except ValueError as exc:
            errors.append(str(exc))
    auth.log(session, user, "seller_bulk_send", target_id=target.id, sent=sent, selected=len(wanted))
    return sent, errors
