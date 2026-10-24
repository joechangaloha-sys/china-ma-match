"""Public, anonymised listings of sellers who opted in.

A listing card is coarser than a teaser: macro-region instead of province, bands only, and fixed
vocabulary for the seller's ask (stake, payment, founder transition, staff, timing). No free text
from the adviser. It still goes through the re-identification check, and a target can only be
listed after the adviser has approved a low-risk teaser for it.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import reid, teaser
from .models import Target
from .taxonomy import FOUNDER_TRANSITION, PAYMENT_TERMS, TIMING, macro_region

CARD_FIELDS = ("sector_zh", "sector_en", "revenue_band", "net_profit_band", "employees_band",
               "years_operating", "deal_type", "sale_reason")
# Finer than the teaser's valuation bands: buyers screen on price first.
PRICE_EDGES = [2, 5, 10, 20, 30, 50, 80, 100, 150, 200, 300]  # pilot focus: RMB 2–20m deals


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
        "price_band": teaser.band(target.asking_value, PRICE_EDGES, "百万元") if target.asking_value else "面议 Open to offers",
        "earnings_band": teaser.band(target.normalized_earnings, [1, 2, 5, 10, 20, 50], "百万元")
        if target.show_earnings and target.normalized_earnings is not None else "",
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
    from . import dealstatus

    if target.status in dealstatus.TERMINAL or target.status == "matching_paused":
        raise ValueError("This mandate is not in market.")
    if not any(t.status == "approved" for t in target.teasers):
        raise ValueError("Approve a low-risk teaser before listing this target.")
    if not any(t.seller_approved_at for t in target.teasers):
        raise ValueError("The seller must approve the teaser before it is published.")
    score, findings = reid.check(target, card(target))
    if reid.risk_label(score) != "low":
        raise ValueError("The listing card failed the re-identification check: "
                         + "; ".join(f["message"] for f in findings))
    target.visibility = "listed"
    target.listed_at = datetime.now(timezone.utc)
    if target.status in ("draft", "documents_requested", "extraction_review", "seller_approval"):
        target.status = "in_market"


def unpublish(target: Target) -> None:
    target.visibility = "private"
    target.listed_at = None
