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
    # Acquisition thesis (buyer portal): free text, AI-structured into the fields above, confirmed by the buyer.
    thesis_text: Mapped[str] = mapped_column(Text, default="")
    excluded_sectors: Mapped[list[str]] = mapped_column(JSON, default=list)
    earnings_min: Mapped[float | None] = mapped_column(Float, nullable=True)  # RMB m net profit
    funding_min: Mapped[float | None] = mapped_column(Float, nullable=True)  # RMB m available for one deal
    funding_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    funding_evidence: Mapped[str] = mapped_column(String(30), default="")  # see taxonomy.FUNDING_EVIDENCE
    experience: Mapped[str] = mapped_column(Text, default="")  # relevant operating experience
    rationale: Mapped[str] = mapped_column(Text, default="")
    # Criteria above are inferred from announcements until the buyer confirms them; only
    criteria_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    asking_value: Mapped[float | None] = mapped_column(Float, nullable=True)  # RMB m, asking price for the stake
    deal_type: Mapped[str] = mapped_column(String(20), default="full_sale")
    sale_reason: Mapped[str] = mapped_column(String(20), default="succession")

    # The seller's ask, shown on the listing in fixed vocabulary (taxonomy.py) so it cannot identify them.
    stake_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # share of equity offered
    payment_terms: Mapped[str] = mapped_column(String(20), default="")
    founder_transition: Mapped[str] = mapped_column(String(20), default="")
    keep_employees: Mapped[bool | None] = mapped_column(nullable=True)
    timing: Mapped[str] = mapped_column(String(20), default="")
    premises: Mapped[str] = mapped_column(String(20), default="")  # taxonomy.PREMISES
    permits: Mapped[str] = mapped_column(String(20), default="")  # taxonomy.PERMITS
    inventory: Mapped[str] = mapped_column(String(20), default="")  # taxonomy.INVENTORY

    # private: not listed; the seller approves outreach buyer by buyer.
    # listed: an anonymised card on the board that verified buyers browse.
    visibility: Mapped[str] = mapped_column(String(20), default="private")
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seller_plan: Mapped[str] = mapped_column(String(20), default="free")  # free | paid (see plans.py)
    plan_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plan_invoice_ref: Mapped[str] = mapped_column(String(50), default="")
    seller_token: Mapped[str] = mapped_column(String(40), default="")  # one-time invite for the seller account
    seller_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft")  # see dealstatus.STATUSES
    contact_name: Mapped[str] = mapped_column(String(50), default="")  # from the public intake form
    contact_info: Mapped[str] = mapped_column(String(100), default="")
    # The owner's accountant, lawyer or adviser can submit for them and keeps their own engagement.
    submitted_by: Mapped[str] = mapped_column(String(20), default="owner")  # owner | adviser
    adviser_firm: Mapped[str] = mapped_column(String(200), default="")

    # Authority to sell: the owner confirms who they are in the company; a deal manager checks it
    # against the business licence and shareholder register before anything goes to buyers.
    owner_role: Mapped[str] = mapped_column(String(20), default="")  # authority.OWNER_ROLES
    owner_share_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    owner_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authority_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authority_verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    authority_note: Mapped[str] = mapped_column(Text, default="")
    normalized_earnings: Mapped[float | None] = mapped_column(Float, nullable=True)  # RMB m, adviser-approved
    show_earnings: Mapped[bool] = mapped_column(default=False)  # seller approved showing earnings and margin bands
    # Seller-approved public description of products and services (no names, brands or customers),
    # shown on the listing and searched by keyword. Checked for re-identification before publishing.
    products_zh: Mapped[str] = mapped_column(String(300), default="")
    products_en: Mapped[str] = mapped_column(String(300), default="")
    prep_pack_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Data the seller submits for the preparation pack. Exact figures: shown to the adviser and, in
    # the info memo, to buyers after an NDA.
    financials: Mapped[dict] = mapped_column(JSON, default=dict)  # {"2025": {"revenue": 126.0, ...}, ...}
    disclosures: Mapped[dict] = mapped_column(JSON, default=dict)  # answers to the diligence checklist
    closing_value: Mapped[float | None] = mapped_column(Float, nullable=True)  # RMB m, final deal value
    is_example: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    firm: Mapped[AdviserFirm] = relationship()
    teasers: Mapped[list["Teaser"]] = relationship(back_populates="target", cascade="all, delete-orphan",
                                                   order_by="desc(Teaser.version)")
    matches: Mapped[list["Match"]] = relationship(back_populates="target", cascade="all, delete-orphan",
                                                  order_by="desc(Match.score)")
    charges: Mapped[list["SellerCharge"]] = relationship(back_populates="target", cascade="all, delete-orphan",
                                                         order_by="SellerCharge.created_at")
    data_checks: Mapped[list["DataCheck"]] = relationship(back_populates="target", cascade="all, delete-orphan",
                                                          order_by="desc(DataCheck.created_at)")
    memos: Mapped[list["InfoMemo"]] = relationship(back_populates="target", cascade="all, delete-orphan",
                                                   order_by="desc(InfoMemo.version)")
    documents: Mapped[list["Document"]] = relationship(back_populates="target", cascade="all, delete-orphan",
                                                       order_by="desc(Document.created_at)")
    fields: Mapped[list["ExtractedField"]] = relationship(back_populates="target", cascade="all, delete-orphan",
                                                          order_by="ExtractedField.id")
    referrals: Mapped[list["ExpertReferral"]] = relationship(back_populates="target", cascade="all, delete-orphan",
                                                             order_by="ExpertReferral.created_at")
    authorizations: Mapped[list["MandateAuthorization"]] = relationship(
        back_populates="target", cascade="all, delete-orphan", order_by="MandateAuthorization.requested_at")


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
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved (by the analyst)
    seller_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analyst_approved_by: Mapped[str] = mapped_column(String(200), default="")
    analyst_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analyst_content_hash: Mapped[str] = mapped_column(String(64), default="")
    seller_approved_by: Mapped[str] = mapped_column(String(200), default="")
    seller_content_hash: Mapped[str] = mapped_column(String(64), default="")
    source_hash: Mapped[str] = mapped_column(String(64), default="")
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
    nda_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nda_version: Mapped[str] = mapped_column(String(20), default="")
    data_room_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    target: Mapped[Target] = relationship(back_populates="matches")
    buyer: Mapped[Buyer] = relationship()
    events: Mapped[list["DealEvent"]] = relationship(back_populates="match", cascade="all, delete-orphan",
                                                     order_by="DealEvent.created_at")
    feedback: Mapped[list["MatchFeedback"]] = relationship(back_populates="match", cascade="all, delete-orphan",
                                                           order_by="MatchFeedback.created_at")
    offers: Mapped[list["IndicativeOffer"]] = relationship(back_populates="match", cascade="all, delete-orphan",
                                                           order_by="desc(IndicativeOffer.submitted_at)")


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


class SellerCharge(Base):
    """A fee the seller has paid or owes: preparation pack, outreach retainer, success fee (see fees.py)."""

    __tablename__ = "seller_charges"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"))
    kind: Mapped[str] = mapped_column(String(20))  # prep_pack | outreach | success
    amount: Mapped[float] = mapped_column(Float)  # RMB, before VAT
    invoice_ref: Mapped[str] = mapped_column(String(50), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)  # success fee: deal value, rate, credits, shares
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    target: Mapped[Target] = relationship(back_populates="charges")


class DataCheck(Base):
    """Result of checking the seller's submitted data for gaps, inconsistencies and deal risks."""

    __tablename__ = "data_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"))
    findings: Mapped[list[dict]] = mapped_column(JSON, default=list)
    generated_by: Mapped[str] = mapped_column(String(40), default="rules")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    target: Mapped[Target] = relationship(back_populates="data_checks")


class InfoMemo(Base):
    """Information memorandum (信息备忘录): shared with a buyer only after an NDA and adviser approval."""

    __tablename__ = "info_memos"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    language: Mapped[str] = mapped_column(String(5), default="zh")
    body: Mapped[dict] = mapped_column(JSON)  # {"title": ..., "sections": [{"heading", "paragraphs", "table"}]}
    name_findings: Mapped[list[dict]] = mapped_column(JSON, default=list)  # names that must not appear
    generated_by: Mapped[str] = mapped_column(String(40), default="offline")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved
    seller_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analyst_approved_by: Mapped[str] = mapped_column(String(200), default="")
    analyst_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analyst_content_hash: Mapped[str] = mapped_column(String(64), default="")
    seller_approved_by: Mapped[str] = mapped_column(String(200), default="")
    seller_content_hash: Mapped[str] = mapped_column(String(64), default="")
    source_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    target: Mapped[Target] = relationship(back_populates="memos")


class User(Base):
    """A person who signs in: seller, buyer, deal manager (analyst/adviser)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(100), default="")
    role: Mapped[str] = mapped_column(String(20))  # seller | buyer | deal_manager
    organization: Mapped[str] = mapped_column(String(200), default="")
    buyer_id: Mapped[int | None] = mapped_column(ForeignKey("buyers.id"), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    buyer: Mapped[Buyer | None] = relationship()


class UserSession(Base):
    __tablename__ = "user_sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class Document(Base):
    """A file a seller (or the deal manager) uploaded. Shared in the data room only when flagged."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"))
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))  # documents.CHECKLIST key
    filename: Mapped[str] = mapped_column(String(200))
    stored_path: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(100), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    text: Mapped[str] = mapped_column(Text, default="")  # "[page N]" markers between pages
    security_status: Mapped[str] = mapped_column(String(20), default="quarantined")
    scanned_sha256: Mapped[str] = mapped_column(String(64), default="")
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    in_data_room: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    target: Mapped[Target] = relationship(back_populates="documents")


class ExtractedField(Base):
    """One financial figure read from a document, kept with its source until an analyst confirms it."""

    __tablename__ = "extracted_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    period: Mapped[str] = mapped_column(String(10))  # fiscal year, e.g. "2025"
    field: Mapped[str] = mapped_column(String(30))  # datacheck.FIN_FIELDS key
    value: Mapped[float] = mapped_column(Float)  # RMB m
    currency: Mapped[str] = mapped_column(String(5), default="CNY")
    unit_in_source: Mapped[str] = mapped_column(String(10), default="")  # 元 | 万元 | 百万元
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote: Mapped[str] = mapped_column(String(300), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    method: Mapped[str] = mapped_column(String(40), default="rules")
    status: Mapped[str] = mapped_column(String(20), default="proposed")  # proposed | confirmed | rejected
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    target: Mapped[Target] = relationship(back_populates="fields")
    document: Mapped[Document] = relationship()


class MatchFeedback(Base):
    """Why the analyst accepted or rejected a recommended match: training data for better matching."""

    __tablename__ = "match_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision: Mapped[str] = mapped_column(String(20))  # accept | reject
    reason: Mapped[str] = mapped_column(String(40), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    match: Mapped[Match] = relationship(back_populates="feedback")


class ExpertReferral(Base):
    """A lawyer, accountant, tax or diligence partner assigned to one matter."""

    __tablename__ = "expert_referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"))
    kind: Mapped[str] = mapped_column(String(20))  # legal | accounting | tax | diligence | financing
    partner: Mapped[str] = mapped_column(String(200))
    contact: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="proposed")  # proposed | engaged | done
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    target: Mapped[Target] = relationship(back_populates="referrals")


class AuditEvent(Base):
    """Append-only record of who did what: sign-ins, publication, disclosure, every document view."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[int | None] = mapped_column(ForeignKey("targets.id"), nullable=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User | None] = relationship()


class Adviser(Base):
    """An accountant, lawyer or consultant who acts for sellers. Verified before acting for anyone."""

    __tablename__ = "advisers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    firm: Mapped[str] = mapped_column(String(200))
    profession: Mapped[str] = mapped_column(String(20))  # authority.PROFESSIONS
    license_no: Mapped[str] = mapped_column(String(60), default="")  # CPA certificate, lawyer's practice licence, ...
    firm_uscc: Mapped[str] = mapped_column(String(18), default="")
    status: Mapped[str] = mapped_column(String(20), default="registered")  # registered | verified | suspended
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship()


class MandateAuthorization(Base):
    """The owner's written authority for one adviser to act on one sale, and its verification.

    requested (adviser prepared the mandate) -> owner_confirmed (owner signed in and accepted the
    authorisation text) -> verified (deal manager checked the owner's authority) ; revoked at any time
    by the owner or a deal manager.
    """

    __tablename__ = "mandate_authorizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"))
    adviser_id: Mapped[int] = mapped_column(ForeignKey("advisers.id"))
    status: Mapped[str] = mapped_column(String(20), default="requested")
    scope: Mapped[list[str]] = mapped_column(JSON, default=list)  # authority.SCOPES keys
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    text_version: Mapped[str] = mapped_column(String(20), default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    target: Mapped[Target] = relationship(back_populates="authorizations")
    adviser: Mapped[Adviser] = relationship()


class IndicativeOffer(Base):
    """A buyer's non-binding indication of interest after the NDA, in a fixed shape so offers compare.

    A buyer may revise: each submission is a new row and the latest one counts.
    """

    __tablename__ = "indicative_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    price_low: Mapped[float] = mapped_column(Float)  # RMB m, for the stake below
    price_high: Mapped[float] = mapped_column(Float)
    stake_pct: Mapped[float] = mapped_column(Float, default=100.0)
    cash_at_close_pct: Mapped[float] = mapped_column(Float, default=100.0)  # rest deferred or earn-out
    consideration: Mapped[str] = mapped_column(String(20), default="cash")  # offers.CONSIDERATION
    financing: Mapped[str] = mapped_column(String(20), default="own_funds")  # offers.FINANCING
    diligence_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_close: Mapped[str] = mapped_column(String(20), default="")  # taxonomy.TIMING key
    keeps_staff: Mapped[bool | None] = mapped_column(nullable=True)
    founder_role: Mapped[str] = mapped_column(String(20), default="")  # taxonomy.FOUNDER_TRANSITION key
    conditions: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    match: Mapped[Match] = relationship(back_populates="offers")


class ReleaseClaim(Base):
    """An immutable assertion-to-evidence review for one document content hash."""
    __tablename__ = "release_claims"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"))
    artifact_kind: Mapped[str] = mapped_column(String(10))
    artifact_id: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    claim_path: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    evidence_sha256: Mapped[str] = mapped_column(String(64), default="")
    evidence_ref: Mapped[str] = mapped_column(Text)
    reviewed_by: Mapped[str] = mapped_column(String(200))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DealHandoff(Base):
    """One NDA/access workflow per introduction. Providers remain mock-only until connected."""
    __tablename__ = 'deal_handoffs'
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey('matches.id'), unique=True)
    provider: Mapped[str] = mapped_column(String(30), default='mock')
    nda_state: Mapped[str] = mapped_column(String(30), default='draft')
    template_version: Mapped[str] = mapped_column(String(100), default='')
    template_hash: Mapped[str] = mapped_column(String(64), default='')
    party_hash: Mapped[str] = mapped_column(String(64), default='')
    envelope_id: Mapped[str] = mapped_column(String(100), default='')
    signed_document_hash: Mapped[str] = mapped_column(String(64), default='')
    evidence_ref: Mapped[str] = mapped_column(String(200), default='')
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nda_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authority_review_ref: Mapped[str] = mapped_column(Text, default='')
    reviewed_by: Mapped[str] = mapped_column(String(100), default='')
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    room_ref: Mapped[str] = mapped_column(String(100), default='')
    access_role: Mapped[str] = mapped_column(String(30), default='viewer')
    vdr_state: Mapped[str] = mapped_column(String(30), default='not_requested')
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seller_approved_hash: Mapped[str] = mapped_column(String(64), default='')
    seller_approved_by: Mapped[str] = mapped_column(String(100), default='')
    seller_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provisioned_by: Mapped[str] = mapped_column(String(100), default='')
    provisioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    match: Mapped['Match'] = relationship()


class HandoffEvent(Base):
    """Append-only application audit; no confidential documents or signature credentials."""
    __tablename__ = 'handoff_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    handoff_id: Mapped[int] = mapped_column(ForeignKey('deal_handoffs.id'))
    action: Mapped[str] = mapped_column(String(50))
    actor: Mapped[str] = mapped_column(String(100))
    provider_event_id: Mapped[str | None] = mapped_column(String(150), nullable=True, unique=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
