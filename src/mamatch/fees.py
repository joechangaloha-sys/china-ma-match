"""What a private seller pays, and how the success fee is worked out.

- Teaser and anonymous listing: free (listing needs an approved teaser, so it stays free).
- Preparation pack, one-off: data check of what the seller submits plus an info memo draft,
  both reviewed by the adviser before anything goes out.
- Outreach retainer, per period: the teaser sent to matching buyers, each approved by the seller.
- Success fee at closing, only for sellers who bought the outreach retainer: rate x final deal
  value, with a minimum, less everything already paid (prep pack and retainers are credited).

Listed-only sellers pay nothing. Seller fees are invoiced by the partner adviser under its own
engagement letter; the platform's share is recorded with each charge. Amounts are RMB before VAT.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from . import config, pipeline
from .models import Match, SellerCharge, Target

CHARGE_KINDS = {"prep_pack": "出售准备包 Preparation pack", "outreach": "推介服务 Outreach retainer",
                "success": "成功费 Success fee"}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def prep_pack_paid(target: Target) -> bool:
    return target.prep_pack_paid_at is not None


def outreach_until(target: Target) -> datetime | None:
    if target.seller_plan != "paid" or target.plan_paid_at is None:
        return None
    return _aware(target.plan_paid_at) + timedelta(days=config.OUTREACH_PERIOD_DAYS)


def outreach_active(target: Target, now: datetime | None = None) -> bool:
    until = outreach_until(target)
    return until is not None and until > (now or datetime.now(timezone.utc))


def _charge(target: Target, kind: str, amount: float, invoice_ref: str, **detail) -> SellerCharge:
    c = SellerCharge(kind=kind, amount=round(amount, 2), invoice_ref=invoice_ref.strip(),
                     detail={**detail, "platform_share": round(amount * config.PLATFORM_SHARE, 2)})
    target.charges.append(c)  # appending cascades into the target's session; setting c.target would not
    return c


def record_prep_pack(target: Target, invoice_ref: str) -> SellerCharge:
    if prep_pack_paid(target):
        raise ValueError("The preparation pack is already paid.")
    target.prep_pack_paid_at = datetime.now(timezone.utc)
    return _charge(target, "prep_pack", config.PREP_PACK_FEE_RMB, invoice_ref)


def record_outreach(target: Target, invoice_ref: str) -> SellerCharge:
    """Start or renew the outreach retainer for one period from today."""
    target.seller_plan = "paid"
    target.plan_paid_at = datetime.now(timezone.utc)
    target.plan_invoice_ref = invoice_ref.strip()
    return _charge(target, "outreach", config.SELLER_PLAN_FEE_RMB, invoice_ref,
                   period_days=config.OUTREACH_PERIOD_DAYS)


def success_fee_applies(target: Target) -> bool:
    return target.seller_plan == "paid" or any(c.kind == "outreach" for c in target.charges)


def credits(target: Target) -> float:
    return sum(c.amount for c in target.charges if c.kind in ("prep_pack", "outreach"))


@dataclass
class SuccessFee:
    deal_value_rmb: float
    gross: float  # max(rate x value, minimum)
    credited: float
    net: float  # what the seller still pays at closing
    platform_share: float


def success_fee(target: Target, deal_value_rmb_m: float) -> SuccessFee:
    value = deal_value_rmb_m * 1_000_000
    gross = max(value * config.SUCCESS_FEE_RATE, config.SUCCESS_FEE_MIN_RMB)
    credited = min(credits(target), gross)
    net = gross - credited
    return SuccessFee(value, round(gross, 2), round(credited, 2), round(net, 2),
                      round(net * config.PLATFORM_SHARE, 2))


def estimate(target: Target) -> SuccessFee | None:
    return success_fee(target, target.asking_value) if target.asking_value else None


def record_closing(session: Session, match: Match, deal_value_rmb_m: float, invoice_ref: str = "") -> SellerCharge | None:
    """Close the deal with this buyer and, if it applies, raise the success fee."""
    if match.stage != "closing":
        raise ValueError("Only a deal in the closing stage can be closed.")
    if deal_value_rmb_m <= 0:
        raise ValueError("Enter the final deal value.")
    target = match.target
    if any(c.kind == "success" for c in target.charges):
        raise ValueError("A success fee is already recorded for this target.")
    pipeline.move(session, match, "closed", f"Closed at RMB {deal_value_rmb_m:g}m")
    target.closing_value = deal_value_rmb_m
    if not success_fee_applies(target):
        return None
    fee = success_fee(target, deal_value_rmb_m)
    c = SellerCharge(kind="success", amount=fee.net, invoice_ref=invoice_ref.strip(),
                     detail={"deal_value_rmb": fee.deal_value_rmb, "rate": config.SUCCESS_FEE_RATE,
                             "minimum": config.SUCCESS_FEE_MIN_RMB, "gross": fee.gross, "credited": fee.credited,
                             "platform_share": fee.platform_share, "buyer_id": match.buyer_id})
    target.charges.append(c)
    session.flush()
    return c
