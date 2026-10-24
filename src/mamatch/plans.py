"""Who pays for what (pilot pricing, design note option B plus a buyer priority plan).

Sellers
- Listed (opt-in to the anonymised board): free. Sees the headline demand count.
- Private: the headline demand count is free; the paid plan unlocks detailed demand statistics
  and outreach (offers sent to matching buyers, one by one, with the seller's approval).

Buyers
- Free (verified): browses the board once a listing is older than the priority head start,
  receives private offers, expresses interest.
- Priority (paid): sees new listings immediately (config.PRIORITY_HEAD_START_DAYS head start),
  searches and filters the board, and is listed first among equally good fits when a seller
  picks buyers for outreach. Priority never lifts a buyer above a better-fitting one, and the
  seller sees that the buyer is a priority member.

Payments are invoiced offline during the pilot; the operator records them here.
"""

from datetime import datetime, timedelta, timezone

from . import config
from .models import Buyer, Target

SELLER_PLANS = {"free": "免费 Free", "paid": "私密推介 Private outreach"}
BUYER_PLANS = {"free": "免费 Free", "priority": "优先 Priority"}


def seller_detailed_stats(target: Target) -> bool:
    return target.seller_plan == "paid"


def seller_outreach(target: Target) -> bool:
    return target.visibility == "private" and target.seller_plan == "paid"


def mark_seller_paid(target: Target, invoice_ref: str) -> None:
    target.seller_plan = "paid"
    target.plan_paid_at = datetime.now(timezone.utc)
    target.plan_invoice_ref = invoice_ref.strip()


def mark_buyer_priority(buyer: Buyer, on: bool = True) -> None:
    buyer.plan = "priority" if on else "free"
    buyer.plan_paid_at = datetime.now(timezone.utc) if on else None


def is_priority(buyer: Buyer) -> bool:
    return buyer.plan == "priority"


def can_search(buyer: Buyer) -> bool:
    return is_priority(buyer)


def visible_from(target: Target, buyer: Buyer) -> datetime | None:
    """When a listing becomes visible to this buyer (None: not listed)."""
    if target.visibility != "listed" or target.listed_at is None:
        return None
    listed = target.listed_at if target.listed_at.tzinfo else target.listed_at.replace(tzinfo=timezone.utc)
    return listed if is_priority(buyer) else listed + timedelta(days=config.PRIORITY_HEAD_START_DAYS)
