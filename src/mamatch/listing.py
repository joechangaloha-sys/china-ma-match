"""Public, anonymised listings of sellers who opted in.

A listing card is coarser than a teaser: macro-region instead of province, bands only, and fixed
vocabulary for the seller's ask (stake, payment, founder transition, staff, timing). The only free
text is a short, seller-approved description of products and services. The card still goes through
the re-identification check, and a target can only be listed after the adviser has approved a
low-risk teaser for it.

The detailed search filters on the same bands the cards show (and on earnings only where the
seller agreed to show them), so a search can never reveal more than the cards do.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import reid, teaser
from .models import Target
from .taxonomy import FOUNDER_TRANSITION, PAYMENT_TERMS, SECTOR_KEYWORDS, SECTORS, TIMING, macro_region

CARD_FIELDS = ("sector_zh", "sector_en", "revenue_band", "net_profit_band", "employees_band",
               "years_operating", "deal_type", "sale_reason")
# Finer than the teaser's valuation bands: buyers screen on price first.
PRICE_EDGES = [2, 5, 10, 20, 30, 50, 80, 100, 150, 200, 300]  # pilot focus: RMB 2–20m deals
MARGIN_EDGES = [5, 10, 20, 30]  # net margin, %


def margin(target: Target) -> float | None:
    """Net margin in %, from the adviser-approved normalised earnings, only if the seller agreed to show it."""
    if not target.show_earnings or target.normalized_earnings is None or not target.revenue:
        return None
    return target.normalized_earnings / target.revenue * 100


def bounds(value: float | None, edges: list[float]) -> tuple[float | None, float | None]:
    """The band a value falls in, as (lower edge, upper edge); None outside the edges or when unknown."""
    if value is None:
        return None, None
    lo = 0.0
    for e in edges:
        if value < e:
            return lo, e
        lo = e
    return lo, None


def search_attrs(target: Target) -> dict:
    """Band edges and labels the in-browser search (static demo) filters on: never exact figures."""
    years = _years(target)
    rev, emp, yrs, price = (bounds(target.revenue, teaser.REVENUE_EDGES), bounds(target.employees, teaser.EMPLOYEE_EDGES),
                            bounds(years, teaser.YEARS_EDGES), bounds(target.asking_value, PRICE_EDGES))
    m = margin(target)
    zh, en, _ = SECTORS.get(target.sector, ("", "", ""))
    words = " ".join([target.products_zh, target.products_en, zh, en, *SECTOR_KEYWORDS.get(target.sector, [])]).lower()
    fmt = lambda v: "" if v is None else f"{v:g}"  # noqa: E731
    return {"sector": target.sector, "macro": macro_region(target.province), "rev-lo": fmt(rev[0]), "rev-hi": fmt(rev[1]),
            "emp-lo": fmt(emp[0]), "emp-hi": fmt(emp[1]), "yrs-lo": fmt(yrs[0]), "price-hi": fmt(price[1]),
            "price-lo": fmt(price[0]), "profitable": {True: "yes", False: "no", None: ""}[card_profitable(target)],
            "margin-lo": fmt(bounds(m, MARGIN_EDGES)[0]) if m is not None else "", "reason": target.sale_reason,
            "deal": target.deal_type, "words": words}


def stake_label(pct: float | None, deal_type: str) -> str:
    if pct is None:
        return {"full_sale": "100%", "majority": "51%以上 Majority", "minority": "少数股权 Minority"}.get(deal_type, "—")
    if pct >= 100:
        return "100%"
    lo = int(pct // 10 * 10)
    return f"{lo}–{lo + 10}%"


CHECKS = {
    "authority": "出售权限已核验 Authority to sell verified",
    "adviser": "由已认证的会计师或律师协助准备 Prepared with a verified accountant or lawyer",
    "figures": "财务数字已对照原始文件核对 Figures checked against source documents",
    "data_check": "已完成出售准备核查 Sale-readiness check done",
}


def checks(target: Target) -> list[str]:
    """What has been verified for this listing, in the order buyers care about. Only checks actually done."""
    done = []
    if target.authority_verified_at is not None:
        done.append("authority")
    if any(a.status == "verified" and a.adviser.status == "verified" for a in target.authorizations):
        done.append("adviser")
    if any(f.status == "confirmed" for f in target.fields):
        done.append("figures")
    if target.data_checks:
        done.append("data_check")
    return done


def card(target: Target) -> dict:
    f = teaser.facts(target)
    ev = None
    if target.asking_value and target.stake_pct and 0 < target.stake_pct < 100:
        ev = teaser.band(target.asking_value * 100 / target.stake_pct, PRICE_EDGES, "百万元")
    return {
        "code_name": target.code_name, "region": macro_region(target.province) or "中国",
        **{k: f[k] for k in CARD_FIELDS},
        "price_band": teaser.band(target.asking_value, PRICE_EDGES, "百万元") if target.asking_value else "面议 Open to offers",
        "earnings_band": teaser.band(target.normalized_earnings, teaser.PROFIT_EDGES, "百万元")
        if target.show_earnings and target.normalized_earnings is not None else "",
        "profitable": (target.normalized_earnings > 0) if target.show_earnings and target.normalized_earnings is not None
        else None,
        "margin_band": teaser.band(margin(target), MARGIN_EDGES, "%") if margin(target) is not None else "",
        "products_zh": target.products_zh, "products_en": target.products_en,
        "implied_ev_band": ev,
        "stake": stake_label(target.stake_pct, target.deal_type),
        "payment_terms": PAYMENT_TERMS.get(target.payment_terms, ""),
        "founder_transition": FOUNDER_TRANSITION.get(target.founder_transition, ""),
        "keep_employees": {True: "希望保留全部员工 Wants all staff kept", False: "可协商 Open to discussion"}.get(
            target.keep_employees, ""),
        "timing": TIMING.get(target.timing, ""),
        "checks": [CHECKS[c] for c in checks(target)],
    }


def public_board(session: Session, sector: str = "", macro: str = "", **filters) -> list[Target]:
    """Everything sellers chose to list, newest first, narrowed by `search_filter`. Anyone can browse it."""
    rows = session.scalars(select(Target).where(Target.visibility == "listed")
                           .order_by(Target.listed_at.desc())).all()
    return [t for t in rows if matches(t, sector=sector, macro=macro, **filters)]


def _years(target: Target) -> int | None:
    return None if target.founded_year is None else datetime.now(timezone.utc).year - target.founded_year


def _in_band(value: float | None, lo: float | None, hi: float | None) -> bool:
    """lo/hi are band edges (anything else is ignored by `edge`), so this only tests band membership."""
    if lo is None and hi is None:
        return True
    if value is None:
        return False
    return (lo is None or value >= lo) and (hi is None or value < hi)


def edge(value, edges: list[float]) -> float | None:
    """Accept only a published band edge; anything else (an attempt to probe exact figures) is ignored."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v in edges else None


def keyword_hit(target: Target, q: str) -> bool:
    words = [w for w in q.lower().replace("，", " ").replace(",", " ").split() if w]
    zh, en, _ = SECTORS.get(target.sector, ("", "", ""))
    haystack = " ".join([target.products_zh, target.products_en, zh, en, *SECTOR_KEYWORDS.get(target.sector, [])]).lower()
    return all(w in haystack for w in words)


def matches(t: Target, *, sector: str = "", macro: str = "", q: str = "", revenue_min=None, revenue_max=None,
            employees_min=None, employees_max=None, years_min=None, price_max=None, profitable: str = "",
            margin_min=None, reasons: list[str] | None = None, deal_types: list[str] | None = None) -> bool:
    if sector and t.sector != sector:
        return False
    if macro and macro_region(t.province) != macro:
        return False
    if q.strip() and not keyword_hit(t, q):
        return False
    if not _in_band(t.revenue, edge(revenue_min, teaser.REVENUE_EDGES), edge(revenue_max, teaser.REVENUE_EDGES)):
        return False
    if not _in_band(t.employees, edge(employees_min, teaser.EMPLOYEE_EDGES), edge(employees_max, teaser.EMPLOYEE_EDGES)):
        return False
    if not _in_band(_years(t), edge(years_min, teaser.YEARS_EDGES), None):
        return False
    if not _in_band(t.asking_value, None, edge(price_max, PRICE_EDGES)):
        return False
    if profitable == "yes" and card_profitable(t) is not True:
        return False
    m = edge(margin_min, MARGIN_EDGES)
    if m is not None and (margin(t) is None or margin(t) < m):
        return False
    if reasons and t.sale_reason not in reasons:
        return False
    if deal_types and t.deal_type not in deal_types:
        return False
    return True


def card_profitable(t: Target) -> bool | None:
    if not t.show_earnings or t.normalized_earnings is None:
        return None
    return t.normalized_earnings > 0


def publish(target: Target) -> None:
    from . import dealstatus

    if target.status in dealstatus.TERMINAL or target.status == "matching_paused":
        raise ValueError("This mandate is not in market.")
    if not any(t.status == "approved" for t in target.teasers):
        raise ValueError("Approve a low-risk teaser before listing this target.")
    if not any(t.seller_approved_at for t in target.teasers):
        raise ValueError("The seller must approve the teaser before it is published.")
    if target.authority_verified_at is None:
        raise ValueError("卖方的出售权限尚未核验 The owner's authority to sell has not been verified yet.")
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
