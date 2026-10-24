"""Deal stages for a target–buyer pair, from suggestion to closing.

Private outreach: suggested -> shortlisted (adviser) -> teaser_sent (only via offers.send, after
the seller approves this buyer) -> interested (buyer's answer) -> nda_signed -> ...
Listed deals: a verified buyer's interest on the board creates the pair at "interested".
"""

from sqlalchemy.orm import Session

from .models import DealEvent, Match

STAGES: dict[str, str] = {
    "suggested": "推荐 / Suggested",
    "shortlisted": "入围 / Shortlisted",
    "teaser_sent": "已发简介 / Teaser sent",
    "interested": "买方有意向 / Buyer interested",
    "nda_signed": "已签保密协议 / NDA signed",
    "im_sent": "已发信息备忘录 / IM sent",
    "loi": "意向书 / LOI",
    "closing": "交割中 / Closing",
    "closed": "已完成 / Closed",
    "dropped": "终止 / Dropped",
}

_ORDER = list(STAGES)
TERMINAL = {"closed", "dropped"}


def allowed_next(stage: str) -> list[str]:
    """Forward one step, or drop. Re-opening a dropped match goes back to shortlisted."""
    if stage == "dropped":
        return ["shortlisted"]
    if stage == "closed":
        return []
    i = _ORDER.index(stage)
    return [_ORDER[i + 1], "dropped"]


def move(session: Session, match: Match, to_stage: str, note: str = "") -> DealEvent:
    if to_stage not in allowed_next(match.stage):
        raise ValueError(f"Cannot move from {match.stage} to {to_stage}")
    event = DealEvent(match=match, from_stage=match.stage, to_stage=to_stage, note=note)
    match.stage = to_stage
    session.add(event)
    session.flush()
    return event
