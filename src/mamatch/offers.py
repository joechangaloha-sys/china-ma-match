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
    """A verified buyer asks for more on a listed deal."""
    now = datetime.now(timezone.utc)
    visible = plans.visible_from(target, buyer)
    if buyer.status != "verified" or visible is None or visible > now:
        raise ValueError("This listing is not available to you.")
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


def disclose_names(match: Match) -> None:
    if match.stage not in AFTER_NDA:
        raise ValueError("Names are disclosed only after an NDA is signed.")
    match.name_disclosed_at = datetime.now(timezone.utc)
