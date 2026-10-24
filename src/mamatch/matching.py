"""Rank buyers for a target, with reasons an adviser can check before sending a teaser.

Scoring is transparent on purpose: advisers need to defend every name on a shortlist to the
seller. Weights sum to 1.0; a buyer with no sector fit, or that excludes the deal type, is never
suggested. Only verified buyers become matches; suggested and invited buyers (mostly from CNINFO)
are ranked separately as people to invite.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Buyer, Match, Target
from .taxonomy import macro_region, sector_family, sector_label

W_SECTOR, W_REGION, W_SIZE, W_RECENCY = 0.45, 0.2, 0.2, 0.15


@dataclass
class Scored:
    buyer: Buyer
    score: float
    reasons: list[str] = field(default_factory=list)


def _as_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def score(target: Target, buyer: Buyer, now: datetime | None = None) -> Scored:
    now = now or datetime.now(timezone.utc)
    s, reasons = 0.0, []

    wanted = set(buyer.target_sectors or [])
    own = set(buyer.sectors or [])
    if target.sector in wanted:
        s += W_SECTOR
        reasons.append(f"Stated interest in {sector_label(target.sector)}")
    elif target.sector in own:
        s += W_SECTOR * 0.7
        reasons.append(f"Same business as target ({sector_label(target.sector)}): horizontal consolidation")
    elif sector_family(target.sector) and sector_family(target.sector) in {sector_family(c) for c in wanted | own}:
        s += W_SECTOR * 0.4
        reasons.append(f"Adjacent sector in the same family ({sector_family(target.sector)})")
    else:
        return Scored(buyer, 0.0, ["No sector fit"])
    if buyer.target_deal_types and target.deal_type not in buyer.target_deal_types:
        return Scored(buyer, 0.0, ["Deal type not wanted"])

    regions = set(buyer.target_regions or [])
    if not regions:
        s += W_REGION * 0.5
        reasons.append("No regional restriction stated")
    elif target.province in regions:
        s += W_REGION
        reasons.append(f"Has bought or targets companies in {target.province}")
    elif macro_region(target.province) in {macro_region(p) for p in regions}:
        s += W_REGION * 0.6
        reasons.append(f"Active in the same region ({macro_region(target.province)})")
    if buyer.province and buyer.province == target.province and target.province not in regions:
        s += W_REGION * 0.3
        reasons.append(f"Headquartered in {target.province}")

    value = target.asking_value
    lo, hi = buyer.deal_size_min, buyer.deal_size_max
    if value is None or (lo is None and hi is None):
        s += W_SIZE * 0.4
    elif (lo is None or value >= lo * 0.5) and (hi is None or value <= hi * 2):
        s += W_SIZE
        reasons.append(f"Deal size fits stated range (RMB {lo or 0:g}–{hi or 0:g}m)")
    else:
        reasons.append("Deal size outside stated range")

    latest = max((_as_aware(sig.published_at) for sig in buyer.signals if sig.published_at), default=None)
    if latest is not None:
        age = now - latest
        if age <= timedelta(days=180):
            s += W_RECENCY
            reasons.append(f"Acquisition announcement in the last 6 months ({latest:%Y-%m-%d})")
        elif age <= timedelta(days=730):
            s += W_RECENCY * 0.5
            reasons.append(f"Acquisition announcement within 2 years ({latest:%Y-%m-%d})")

    return Scored(buyer, round(min(s, 1.0), 3), reasons)


def rank(session: Session, target: Target, limit: int = 20, min_score: float = 0.3,
         statuses: tuple[str, ...] = ("verified",)) -> list[Scored]:
    buyers = session.scalars(select(Buyer).where(Buyer.status.in_(statuses))).all()
    scored = [score(target, b) for b in buyers]
    scored = [x for x in scored if x.score >= min_score]
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:limit]


def invite_candidates(session: Session, target: Target, limit: int = 10) -> list[Scored]:
    """Buyers not yet on the platform who look like a fit: worth inviting for this target."""
    return rank(session, target, limit, statuses=("suggested", "invited"))


def refresh(session: Session, target: Target, limit: int = 20) -> list[Match]:
    """Recompute suggestions among verified buyers. Matches already in the pipeline keep their stage."""
    existing = {m.buyer_id: m for m in target.matches}
    for x in rank(session, target, limit):
        m = existing.get(x.buyer.id)
        if m is None:
            m = Match(target=target, buyer=x.buyer, score=x.score, reasons=x.reasons)
            session.add(m)
        else:
            m.score, m.reasons = x.score, x.reasons
    session.flush()
    session.refresh(target)
    return target.matches
