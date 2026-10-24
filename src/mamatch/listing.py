"""The anonymised deal board that verified buyers browse.

A listed card is coarser than a teaser: macro-region instead of province, bands only, fixed
vocabulary for deal type and sale reason, and no free text from the adviser. It still goes
through the re-identification check, and a target can only be listed after the adviser has
approved a low-risk teaser for it.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import plans, reid, teaser
from .models import Buyer, Target
from .taxonomy import macro_region

CARD_FIELDS = ("sector_zh", "sector_en", "revenue_band", "net_profit_band", "valuation_band", "employees_band",
               "years_operating", "deal_type", "sale_reason")


def card(target: Target) -> dict:
    f = teaser.facts(target)
    return {"code_name": target.code_name, "region": macro_region(target.province) or "中国",
            **{k: f[k] for k in CARD_FIELDS}}


def publish(target: Target) -> None:
    if not any(t.status == "approved" for t in target.teasers):
        raise ValueError("Approve a low-risk teaser before listing this target.")
    score, findings = reid.check(target, card(target))
    if reid.risk_label(score) != "low":
        raise ValueError("The listing card failed the re-identification check: "
                         + "; ".join(f["message"] for f in findings))
    target.visibility = "listed"
    target.listed_at = datetime.now(timezone.utc)


def unpublish(target: Target) -> None:
    target.visibility = "private"
    target.listed_at = None


def board(session: Session, buyer: Buyer, sector: str = "", macro: str = "",
          now: datetime | None = None) -> list[Target]:
    """Listings this buyer may see now. Filters only apply for buyers whose plan includes search."""
    if buyer.status != "verified":
        return []
    now = now or datetime.now(timezone.utc)
    rows = session.scalars(select(Target).where(Target.visibility == "listed")
                           .order_by(Target.listed_at.desc())).all()
    rows = [t for t in rows if (v := plans.visible_from(t, buyer)) is not None and v <= now]
    if plans.can_search(buyer):
        if sector:
            rows = [t for t in rows if t.sector == sector]
        if macro:
            rows = [t for t in rows if macro_region(t.province) == macro]
    return rows


def hidden_count(session: Session, buyer: Buyer, now: datetime | None = None) -> int:
    """Listings still inside the priority head start for this buyer (shown as an upsell)."""
    if buyer.status != "verified":
        return 0
    now = now or datetime.now(timezone.utc)
    rows = session.scalars(select(Target).where(Target.visibility == "listed")).all()
    return sum(1 for t in rows if (v := plans.visible_from(t, buyer)) is not None and v > now)
