"""Public, anonymised listings of sellers who opted in.

A listing card is coarser than a teaser: macro-region instead of province, bands only, and fixed
vocabulary for the seller's ask (stake, payment, founder transition, staff, timing). No free text
from the adviser. It still goes through the re-identification check, and a target can only be
listed after the adviser has approved a low-risk teaser for it.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import plans, reid, teaser
from .models import Buyer, Target
from .taxonomy import FOUNDER_TRANSITION, PAYMENT_TERMS, TIMING, macro_region

CARD_FIELDS = ("sector_zh", "sector_en", "revenue_band", "net_profit_band", "employees_band",
               "years_operating", "deal_type", "sale_reason")
# Finer than the teaser's valuation bands: buyers screen on price first.
PRICE_EDGES = [10, 20, 30, 50, 80, 100, 150, 200, 300]


def stake_label(pct: float | None, deal_type: str) -> str:
    if pct is None:
        return {"full_sale": "100%", "majority": "51%以上 Majority", "minority": "少数股权 Minority"}.get(deal_type, "—")
    if pct >= 100:
        return "100%"
    lo = int(pct // 10 * 10)
    return f"{lo}–{lo + 10}%"


def card(target: Target) -> dict:
    f = teaser.facts(target)
    ev = None
    if target.asking_value and target.stake_pct and 0 < target.stake_pct < 100:
        ev = teaser.band(target.asking_value * 100 / target.stake_pct, PRICE_EDGES, "百万元")
    return {
        "code_name": target.code_name, "region": macro_region(target.province) or "中国",
        **{k: f[k] for k in CARD_FIELDS},
        "price_band": teaser.band(target.asking_value, PRICE_EDGES, "百万元"),
        "implied_ev_band": ev,
        "stake": stake_label(target.stake_pct, target.deal_type),
        "payment_terms": PAYMENT_TERMS.get(target.payment_terms, ""),
        "founder_transition": FOUNDER_TRANSITION.get(target.founder_transition, ""),
        "keep_employees": {True: "希望保留全部员工 Wants all staff kept", False: "可协商 Open to discussion"}.get(
            target.keep_employees, ""),
        "timing": TIMING.get(target.timing, ""),
    }


def public_board(session: Session, sector: str = "", macro: str = "") -> list[Target]:
    """Everything sellers chose to list, newest first. Anyone can browse it."""
    rows = session.scalars(select(Target).where(Target.visibility == "listed")
                           .order_by(Target.listed_at.desc())).all()
    if sector:
        rows = [t for t in rows if t.sector == sector]
    if macro:
        rows = [t for t in rows if macro_region(t.province) == macro]
    return rows


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
