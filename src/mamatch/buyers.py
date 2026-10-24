"""Buyer registration for the invitation-only pilot: invite -> register -> verify.

CNINFO announcements suggest listed companies worth inviting and pre-fill their criteria; the
buyer confirms or corrects them when registering. Nothing about a buyer reaches a seller except
until both sides agree to disclose names.
"""

import re
import secrets
from datetime import datetime, timezone

from .models import Buyer

_USCC = re.compile(r"^[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}$")


def new_token() -> str:
    return secrets.token_urlsafe(16)


def invite(buyer: Buyer) -> str:
    if not buyer.invite_token:
        buyer.invite_token = new_token()
    if buyer.status in (None, "suggested"):
        buyer.status = "invited"
    return buyer.invite_token


def register(buyer: Buyer, *, name: str, kind: str, uscc: str, contact_name: str, contact_email: str,
             target_sectors: list[str], target_regions: list[str], deal_size_min: float | None,
             deal_size_max: float | None, target_deal_types: list[str], consent: bool,
             thesis_text: str = "", excluded_sectors: list[str] | None = None, earnings_min: float | None = None,
             funding_min: float | None = None, funding_max: float | None = None, funding_evidence: str = "",
             experience: str = "") -> None:
    if buyer.status not in ("invited", "registered", "verified"):
        raise ValueError("Registration is by invitation.")
    if not consent:
        raise ValueError("Consent to the processing of registration data is required.")
    if not target_sectors:
        raise ValueError("Choose at least one sector.")
    if deal_size_min is not None and deal_size_max is not None and deal_size_min > deal_size_max:
        raise ValueError("Minimum deal size is above the maximum.")
    now = datetime.now(timezone.utc)
    uscc = uscc.strip().upper()
    if buyer.status == "verified" and uscc != buyer.uscc:
        buyer.status = "registered"  # a changed registry code needs checking again
        buyer.verified_at = None
    buyer.name, buyer.kind, buyer.uscc = name.strip() or buyer.name, kind, uscc
    buyer.contact_name, buyer.contact_email = contact_name.strip(), contact_email.strip()
    buyer.target_sectors, buyer.target_regions = target_sectors, target_regions
    buyer.deal_size_min, buyer.deal_size_max = deal_size_min, deal_size_max
    buyer.target_deal_types = target_deal_types
    buyer.thesis_text, buyer.experience = thesis_text.strip(), experience.strip()
    buyer.excluded_sectors = [x for x in (excluded_sectors or []) if x not in target_sectors]
    buyer.earnings_min, buyer.funding_min, buyer.funding_max = earnings_min, funding_min, funding_max
    buyer.funding_evidence = funding_evidence
    buyer.criteria_confirmed_at = now
    if buyer.status == "invited":
        buyer.status, buyer.registered_at = "registered", now


def verify(buyer: Buyer) -> None:
    """Operator step after checking the registry code against the business registry."""
    if buyer.status not in ("registered", "verified"):
        raise ValueError("Only registered buyers can be verified.")
    if buyer.kind != "individual" and not _USCC.match(buyer.uscc or ""):
        raise ValueError("A valid 18-character unified social credit code is required.")
    if buyer.funding_evidence in ("", "none") and buyer.source != "example":
        raise ValueError("Funding evidence is required before verification.")
    buyer.status, buyer.verified_at = "verified", datetime.now(timezone.utc)
