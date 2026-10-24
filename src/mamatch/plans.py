"""What a seller's paid services unlock (prices and the success fee: fees.py).

Listing anonymously is free. The outreach retainer lets the deal manager send the teaser to
matching buyers, one by one, each approved by the seller, for one period. Payments are invoiced
offline during the pilot; the deal manager records them.
"""

from . import fees
from .models import Target


def seller_outreach(target: Target) -> bool:
    return target.visibility == "private" and fees.outreach_active(target)


def mark_seller_paid(target: Target, invoice_ref: str) -> None:
    fees.record_outreach(target, invoice_ref)
