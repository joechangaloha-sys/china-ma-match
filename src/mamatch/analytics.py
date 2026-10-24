"""Pilot dashboard: the funnel and service measures from the 90-day plan, not traffic."""

from collections import Counter
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import dealstatus, documents
from .models import AuditEvent, Buyer, ExtractedField, Match, MatchFeedback, SellerCharge, Target, Teaser

LATER = {"nda_signed", "im_sent", "loi", "closing", "closed"}


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def metrics(s: Session) -> dict:
    targets = s.scalars(select(Target)).all()
    matches = s.scalars(select(Match)).all()
    buyers = s.scalars(select(Buyer).where(Buyer.source != "cninfo")).all()
    fields = s.scalars(select(ExtractedField).where(ExtractedField.status != "proposed")).all()
    feedback = s.scalars(select(MatchFeedback)).all()
    reviews = s.scalars(select(AuditEvent).where(AuditEvent.action == "field_review")).all()
    charges = s.scalars(select(SellerCharge)).all()
    teasers = s.scalars(select(Teaser)).all()

    complete = [t for t in targets if not documents.missing_kinds(t)]
    # Days from the last required document to the seller approving a teaser.
    lead_times = []
    for t in complete:
        req = [d.created_at for d in t.documents if d.kind in documents.REQUIRED]
        approved = [tz.seller_approved_at for tz in t.teasers if tz.seller_approved_at]
        if req and approved:
            lead_times.append((_aware(min(approved)) - _aware(max(req))).total_seconds() / 86400)
    corrected = sum(1 for e in reviews if e.detail.get("corrected"))
    confirmed = sum(1 for e in reviews if e.detail.get("decision") == "confirmed")
    return {
        "status": Counter(t.status for t in targets),
        "statuses": dealstatus.STATUSES,
        "mandates": len(targets),
        "docs_complete": len(complete),
        "lead_time_days": round(sum(lead_times) / len(lead_times), 1) if lead_times else None,
        "fields_reviewed": len(fields),
        "correction_rate": round(corrected / confirmed, 2) if confirmed else None,
        "buyers_registered": sum(b.status in ("registered", "verified") for b in buyers),
        "buyers_verified": sum(b.status == "verified" for b in buyers),
        "theses": sum(bool(b.thesis_text) for b in buyers),
        "recs_accepted": sum(f.decision == "accept" for f in feedback),
        "recs_rejected": sum(f.decision == "reject" for f in feedback),
        "reject_reasons": Counter(f.reason for f in feedback if f.decision == "reject"),
        "introductions": sum(m.stage not in ("suggested", "shortlisted") and (m.seller_approved_at is not None or m.channel == "listing")
                             for m in matches),
        "ndas": sum(m.nda_accepted_at is not None for m in matches),
        "data_rooms": sum(m.data_room_granted_at is not None for m in matches),
        "lois": sum(m.stage in ("loi", "closing", "closed") for m in matches),
        "closed": sum(m.stage == "closed" for m in matches),
        "withdrawn": sum(t.status == "withdrawn" for t in targets),
        "ai_teasers": sum(tz.generated_by not in ("offline",) for tz in teasers),
        "fees_total": sum(c.amount for c in charges),
        "platform_share": sum(c.detail.get("platform_share", 0) for c in charges),
    }
