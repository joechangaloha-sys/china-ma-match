"""Database models.

Buyers are invited by the operator (often a listed company found through CNINFO announcements),
register, state what they want to buy and are verified before they count anywhere. Targets are
seller mandates held by an adviser firm; their identifying fields never leave the workspace until
the seller approves name disclosure to one buyer. Teasers are the anonymised text shared with buyers.
"""

import secrets
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AdviserFirm(Base):
    __tablename__ = "adviser_firms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Buyer(Base):
    __tablename__ = "buyers"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="listed")  # listed | pe | private | individual
    source: Mapped[str] = mapped_column(String(20), default="manual")  # cninfo | manual | example
    # suggested (found, not contacted) -> invited -> registered (criteria stated) -> verified (counts, sees deals)
    status: Mapped[str] = mapped_column(String(20), default="suggested")
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free | priority (see plans.py)
    invite_token: Mapped[str] = mapped_column(String(40), default="")
    uscc: Mapped[str] = mapped_column(String(18), default="")
    contact_name: Mapped[str] = mapped_column(String(50), default="")
    contact_email: Mapped[str] = mapped_column(String(200), default="")
    # Stock code for CNINFO buyers; a random id for buyers added by hand (unique per source).
    external_id: Mapped[str] = mapped_column(String(40), default=lambda: "M-" + secrets.token_hex(6))
    province: Mapped[str] = mapped_column(String(20), default="")
    sectors: Mapped[list[str]] = mapped_column(JSON, default=list)  # own business
    target_sectors: Mapped[list[str]] = mapped_column(JSON, default=list)  # what it wants to buy
    target_regions: Mapped[list[str]] = mapped_column(JSON, default=list)  # provinces; empty = anywhere
    deal_size_min: Mapped[float | None] = mapped_column(Float, nullable=True)  # RMB m, enterprise value
    deal_size_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_deal_types: Mapped[list[str]] = mapped_column(JSON, default=list)  # empty = any
    rationale: Mapped[str] = mapped_column(Text, default="")
    # Criteria above are inferred from announcements until the buyer confirms them; only
    # criteria confirmed within config.CRITERIA_TTL_DAYS count in demand statistics.
    criteria_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_example: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    signals: Mapped[list["BuyerSignal"]] = relationship(back_populates="buyer", cascade="all, delete-orphan",
                                                         order_by="desc(BuyerSignal.published_at)")


class BuyerSignal(Base):
    """One piece of evidence of acquisition appetite: an announcement, a report passage, a past deal."""

    __tablename__ = "buyer_signals"
    __table_args__ = (UniqueConstraint("buyer_id", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    kind: Mapped[str] = mapped_column(String(30))  # announcement | annual_report | past_deal | note
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(500), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)  # output of the profile extractor
    buyer: Mapped[Buyer] = relationship(back_populates="signals")


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    firm_id: Mapped[int] = mapped_column(ForeignKey("adviser_firms.id"))
    code_name: Mapped[str] = mapped_column(String(50))  # e.g. "Project Jade"; the only name buyers see

    # Identifying fields: kept inside the adviser workspace, used by the re-identification check.
    legal_name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str] = mapped_column(String(50), default="")
    owner_name: Mapped[str] = mapped_column(String(50), default="")
    city: Mapped[str] = mapped_column(String(50), default="")
    uscc: Mapped[str] = mapped_column(String(18), default="")  # 统一社会信用代码
    brands: Mapped[list[str]] = mapped_column(JSON, default=list)

    province: Mapped[str] = mapped_column(String(20))
    sector: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")  # adviser's notes from the intake interview
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)  # RMB m, last full year
    net_profit: Mapped[float | None] = mapped_column(Float, nullable=True)  # RMB m
    asking_value: Mapped[float | None] = mapped_column(Float, nullable=True)  # RMB m, enterprise value
    deal_type: Mapped[str] = mapped_column(String(20), default="full_sale")
    sale_reason: Mapped[str] = mapped_column(String(20), default="succession")

    # private: not listed; the seller sees demand statistics and approves outreach buyer by buyer.
    # listed: an anonymised card on the board that verified buyers browse.
    visibility: Mapped[str] = mapped_column(String(20), default="private")
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seller_plan: Mapped[str] = mapped_column(String(20), default="free")  # free | paid (see plans.py)
    plan_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_invoice_ref: Mapped[str] = mapped_column(String(50), default="")
    seller_token: Mapped[str] = mapped_column(String(40), default="")  # seller's private link
    is_example: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    firm: Mapped[AdviserFirm] = relationship()
    teasers: Mapped[list["Teaser"]] = relationship(back_populates="target", cascade="all, delete-orphan",
                                                   order_by="desc(Teaser.version)")
    matches: Mapped[list["Match"]] = relationship(back_populates="target", cascade="all, delete-orphan",
                                                  order_by="desc(Match.score)")


class Teaser(Base):
    __tablename__ = "teasers"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    language: Mapped[str] = mapped_column(String(5), default="zh")  # zh | ja | en
    body: Mapped[dict] = mapped_column(JSON)  # headline, summary, highlights, financials, ...
    reid_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0 = safe, 1 = identifiable
    reid_findings: Mapped[list[dict]] = mapped_column(JSON, default=list)
    generated_by: Mapped[str] = mapped_column(String(40), default="offline")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    target: Mapped[Target] = relationship(back_populates="teasers")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("target_id", "buyer_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"))
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    score: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    stage: Mapped[str] = mapped_column(String(20), default="suggested")
    channel: Mapped[str] = mapped_column(String(20), default="offer")  # offer (private outreach) | listing
    seller_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    name_disclosed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    target: Mapped[Target] = relationship(back_populates="matches")
    buyer: Mapped[Buyer] = relationship()
    events: Mapped[list["DealEvent"]] = relationship(back_populates="match", cascade="all, delete-orphan",
                                                     order_by="DealEvent.created_at")


class DealEvent(Base):
    """Audit trail of a match moving through the pipeline."""

    __tablename__ = "deal_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    from_stage: Mapped[str] = mapped_column(String(20))
    to_stage: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    match: Mapped[Match] = relationship(back_populates="events")
