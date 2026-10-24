"""Aggregate buyer demand, shown to sellers without revealing any buyer.

Sellers only ever see counts for fixed buckets (sector x macro-region, broken down by size band,
buyer type, deal type or province). Free-form filters are not offered, so a seller cannot narrow
the count to one buyer by comparing two queries. On top of that:

- a count below K (config.MIN_GROUP_SIZE) is shown as "<K";
- counts are rounded down to a multiple of K ("10+");
- a breakdown is shown only when every non-empty cell has at least K buyers, otherwise the
  small cell could be worked out from the total.

Only verified buyers whose criteria were confirmed within config.CRITERIA_TTL_DAYS count.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .models import Buyer, Target
from .taxonomy import DEAL_TYPES, REGIONS, SECTORS, macro_region

SIZE_BANDS: list[tuple[str, float, float]] = [  # RMB m, enterprise value; same edges as teaser bands
    ("<20", 0, 20), ("20–50", 20, 50), ("50–100", 50, 100), ("100+", 100, float("inf")),
]
BUYER_KINDS = {"listed": "上市公司 Listed company", "pe": "投资机构 Fund", "private": "非上市企业 Private company",
               "individual": "个人 Individual"}
MACRO_REGIONS = sorted(set(REGIONS.values()), key=list(REGIONS.values()).index)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def eligible(session: Session, now: datetime | None = None) -> list[Buyer]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=config.CRITERIA_TTL_DAYS)
    rows = session.scalars(select(Buyer).where(Buyer.status == "verified")).all()
    return [b for b in rows if b.criteria_confirmed_at and _aware(b.criteria_confirmed_at) >= cutoff]


def wants_region(buyer: Buyer, macro: str) -> bool:
    return not buyer.target_regions or any(macro_region(p) == macro for p in buyer.target_regions)


def wants_province(buyer: Buyer, province: str) -> bool:
    return not buyer.target_regions or province in buyer.target_regions


def wants_size(buyer: Buyer, lo: float, hi: float) -> bool:
    bmin = buyer.deal_size_min if buyer.deal_size_min is not None else 0
    bmax = buyer.deal_size_max if buyer.deal_size_max is not None else float("inf")
    return bmin < hi and bmax >= lo


def bucket(buyers: list[Buyer], sector: str, macro: str) -> list[Buyer]:
    return [b for b in buyers if sector in (b.target_sectors or []) and wants_region(b, macro)]


def shown(n: int) -> str:
    """Display form of a count: '<5', '5+', '10+'."""
    k = config.MIN_GROUP_SIZE
    if n < k:
        return f"<{k}"
    return f"{n // k * k}+"


@dataclass
class Breakdown:
    title: str
    rows: list[tuple[str, str]] = field(default_factory=list)  # (label, shown count)
    suppressed: bool = False


def _breakdown(title: str, cells: list[tuple[str, int]]) -> Breakdown:
    k = config.MIN_GROUP_SIZE
    if any(0 < n < k for _, n in cells):
        return Breakdown(title, suppressed=True)
    return Breakdown(title, [(label, shown(n)) for label, n in cells if n > 0])


@dataclass
class Demand:
    sector: str
    macro: str
    total: str  # already suppressed and rounded
    enough: bool  # total >= K
    breakdowns: list[Breakdown] = field(default_factory=list)


def for_target(session: Session, target: Target, detailed: bool = False) -> Demand:
    macro = macro_region(target.province) or target.province
    group = bucket(eligible(session), target.sector, macro)
    d = Demand(target.sector, macro, shown(len(group)), len(group) >= config.MIN_GROUP_SIZE)
    if not detailed or not d.enough:
        return d
    d.breakdowns = [
        _breakdown("按交易规模 By deal size (RMB m)",
                   [(label, sum(wants_size(b, lo, hi) for b in group)) for label, lo, hi in SIZE_BANDS]),
        _breakdown("按买方类型 By buyer type",
                   [(label, sum(b.kind == kind for b in group)) for kind, label in BUYER_KINDS.items()]),
        _breakdown("按交易方式 By deal type",
                   [(label, sum(not b.target_deal_types or code in b.target_deal_types for b in group))
                    for code, label in DEAL_TYPES.items()]),
        _breakdown("按省份 By province",
                   [(p, sum(wants_province(b, p) for b in group)) for p, m in REGIONS.items() if m == macro]),
    ]
    return d


def overview(session: Session) -> dict[str, dict[str, str]]:
    """Sector x macro-region grid of shown counts, for the demand page."""
    buyers = eligible(session)
    return {code: {m: shown(len(bucket(buyers, code, m))) for m in MACRO_REGIONS} for code in SECTORS}
