"""Database models.

Buyers come from the buyer-intent index (listed companies, PE funds, added by hand).
Targets are seller mandates held by an adviser firm; their identifying fields never leave
the adviser workspace. Teasers are the anonymised text that may be shared with buyers.
"""

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
    kind: Mapped[str] = mapped_column(String(20), default="listed")  # listed | pe | private
    source: Mapped[str] = mapped_column(String(20), default="manual")  # cninfo | manual | example
    external_id: Mapped[str] = mapped_column(String(40), default="")  # stock code for listed buyers
    province: Mapped[str] = mapped_column(String(20), default="")
    sectors: Mapped[list[str]] = mapped_column(JSON, default=list)  # own business
    target_sectors: Mapped[list[str]] = mapped_column(JSON, default=list)  # what it wants to buy
    target_regions: Mapped[list[str]] = mapped_column(JSON, default=list)  # provinces; empty = anywhere
    deal_size_min: Mapped[float | None] = mapped_column(Float, nullable=True)  # RMB m, enterprise value
    deal_size_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
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
