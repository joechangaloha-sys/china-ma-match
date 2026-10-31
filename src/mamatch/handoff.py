"""NDA and VDR handoff state machine, with an explicitly fictional provider.

No provider credentials, network calls, invitations or contracts are created here.
The mock adapter is refused for non-example mandates at every mutation boundary.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import object_session

from . import release
from .models import DealHandoff, HandoffEvent


def now():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def future(value):
    return value is not None and aware(value) > now()


def get(match):
    s = object_session(match)
    return s.scalar(select(DealHandoff).where(DealHandoff.match_id == match.id)) if s else None


def require_demo(match):
    if not match.target.is_example:
        raise ValueError('External connections are deferred. Only fictional mandates can use this simulator.')
    if match.target.authority_verified_at is None or match.buyer.status != 'verified':
        raise ValueError('Verified seller authority and buyer qualification are required.')
    if match.stage in {'suggested', 'shortlisted', 'teaser_sent', 'dropped', 'closed'}:
        raise ValueError('An approved, interested introduction is required.')
    if match.seller_approved_at is None and not any(f.decision == 'accept' for f in match.feedback):
        raise ValueError('The introduction must be approved before requesting an NDA.')


def actor(user, match, role):
    if user is None or user.role != role or not user.active:
        raise ValueError(f'An active {role} account is required.')
    if role == 'seller' and user.id != match.target.seller_user_id:
        raise ValueError('Only this mandate owner can approve access.')
    if role == 'buyer' and user.buyer_id != match.buyer_id:
        raise ValueError('Only this introduction buyer can accept the demo NDA.')
    return f'user:{user.id}'


def log(h, action, who, event_id=None, **detail):
    event = HandoffEvent(handoff_id=h.id, action=action, actor=who, provider_event_id=event_id, detail=detail)
    object_session(h).add(event)
    return event


def events(h):
    return object_session(h).scalars(select(HandoffEvent).where(HandoffEvent.handoff_id == h.id)
                                    .order_by(HandoffEvent.id.desc())).all()


def party_hash(match):
    return release.digest({'match': match.id, 'target': match.target_id, 'buyer': match.buyer_id,
        'seller_account': match.target.seller_user_id, 'seller_name': match.target.legal_name,
        'seller_uscc': match.target.uscc, 'buyer_name': match.buyer.name, 'buyer_uscc': match.buyer.uscc})


def template():
    from .offers import NDA_TEXT, NDA_VERSION
    return NDA_VERSION, release.digest(NDA_TEXT)


def start(match, user):
    require_demo(match)
    who = actor(user, match, 'deal_manager') if getattr(user, 'role', None) == 'deal_manager' else actor(user, match, 'buyer')
    h = get(match)
    if h is None:
        h = DealHandoff(match=match)
        object_session(match).add(h); object_session(match).flush()
    if h.nda_state == 'requested' and current(h):
        return h
    if h.nda_state == 'completed' and signature_complete(h):
        return h
    # A new request invalidates all old evidence, approval and mock access immediately.
    h.template_version, h.template_hash = template()
    h.party_hash, h.envelope_id = party_hash(match), f'mock-{uuid4().hex}'
    h.provider, h.nda_state = 'mock', 'requested'
    h.signed_document_hash = h.evidence_ref = h.authority_review_ref = h.reviewed_by = ''
    h.signed_at = h.nda_expires_at = h.reviewed_at = None
    h.vdr_state = 'not_requested'
    h.seller_approved_hash = h.seller_approved_by = h.provisioned_by = ''
    h.seller_approved_at = h.provisioned_at = h.revoked_at = h.access_expires_at = None
    match.data_room_granted_at = None
    log(h, 'mock_nda_requested', who, envelope_id=h.envelope_id, template_version=h.template_version,
        template_hash=h.template_hash, party_hash=h.party_hash)
    return h


def current(h):
    version, fingerprint = template()
    return h.provider == 'mock' and h.match.target.is_example and h.template_version == version \
        and h.template_hash == fingerprint and h.party_hash == party_hash(h.match)


@dataclass(frozen=True)
class SignatureReceipt:
    envelope_id: str
    template_hash: str
    party_hash: str
    signed_hash: str
    evidence_ref: str
    event_id: str


class MockSignatureProvider:
    """A deterministic test adapter, never evidence of a legally executed NDA."""
    @staticmethod
    def completion(h):
        return SignatureReceipt(h.envelope_id, h.template_hash, h.party_hash,
            release.digest({'simulated': True, 'envelope': h.envelope_id, 'template': h.template_hash, 'parties': h.party_hash}),
            f'mock-evidence:{h.envelope_id}', f'mock-complete:{h.envelope_id}')


def apply_completion(h, receipt, user):
    require_demo(h.match)
    who = actor(user, h.match, 'deal_manager') if getattr(user, 'role', None) == 'deal_manager' else actor(user, h.match, 'buyer')
    if not current(h) or receipt != MockSignatureProvider.completion(h):
        raise ValueError('Receipt does not match the current mock request and document.')
    s = object_session(h)
    duplicate = s.scalar(select(HandoffEvent).where(HandoffEvent.provider_event_id == receipt.event_id))
    if duplicate:
        return h  # replay cannot reset review or revive a revoked/expired room
    if h.nda_state != 'requested':
        raise ValueError('Only a pending mock request can complete.')
    h.nda_state, h.signed_document_hash, h.evidence_ref = 'completed', receipt.signed_hash, receipt.evidence_ref
    h.signed_at = now()
    h.match.nda_accepted_at = h.signed_at
    h.match.nda_version = h.template_version
    if h.match.stage == 'interested':
        from . import pipeline
        pipeline.move(s, h.match, 'nda_signed', 'Fictional signing completion; no external provider connected')
    try:
        h.nda_expires_at = h.signed_at.replace(year=h.signed_at.year + 3)
    except ValueError:
        h.nda_expires_at = h.signed_at.replace(year=h.signed_at.year + 3, day=28)
    log(h, 'mock_nda_completed', who, receipt.event_id, signed_hash=receipt.signed_hash,
        evidence_ref=receipt.evidence_ref, template_hash=h.template_hash, party_hash=h.party_hash,
        signed_at=h.signed_at.isoformat(), nda_expires_at=h.nda_expires_at.isoformat())
    s.flush()
    return h


def signature_complete(h):
    return bool(h and current(h) and h.nda_state == 'completed' and release.valid_time(h.signed_at)
                and future(h.nda_expires_at)
                and h.signed_document_hash == MockSignatureProvider.completion(h).signed_hash
                and h.evidence_ref == MockSignatureProvider.completion(h).evidence_ref)


def evidence_reviewed(h):
    return signature_complete(h) and bool(h.reviewed_by and h.authority_review_ref) and release.valid_time(h.reviewed_at)


def review_authority(h, user, reference):
    require_demo(h.match)
    who = actor(user, h.match, 'deal_manager')
    if not signature_complete(h):
        raise ValueError('Complete the current mock NDA before reviewing signer authority.')
    if not reference.strip() or len(reference.strip()) > 2000:
        raise ValueError('Record the fictional signer-authority evidence you checked (up to 2,000 characters).')
    h.authority_review_ref, h.reviewed_by, h.reviewed_at = reference.strip(), who, now()
    # Re-review requires a fresh owner decision, even if the new note is similar.
    h.seller_approved_hash = ''
    h.seller_approved_at = None
    if h.vdr_state in {'active', 'pending_provisioning', 'awaiting_seller'}:
        h.vdr_state = 'awaiting_seller'
        h.match.data_room_granted_at = None
    log(h, 'signer_authority_reviewed', who)


def access_hash(h):
    return release.digest({'match': h.match_id, 'envelope': h.envelope_id, 'signed_hash': h.signed_document_hash,
        'evidence_ref': h.evidence_ref, 'authority_ref': h.authority_review_ref,
        'room': h.room_ref, 'role': h.access_role, 'expires': aware(h.access_expires_at)})


def request_access(h, user, days=7):
    require_demo(h.match)
    who = actor(user, h.match, 'deal_manager')
    if not evidence_reviewed(h):
        raise ValueError('Current NDA completion and signer-authority review are required.')
    if not 1 <= days <= 30:
        raise ValueError('The demo access period must be between 1 and 30 days.')
    h.room_ref, h.access_role = f'mock-room:{h.match.target_id}', 'viewer'
    h.access_expires_at = min(now() + timedelta(days=days), aware(h.nda_expires_at))
    h.vdr_state = 'awaiting_seller'
    h.seller_approved_hash = h.seller_approved_by = h.provisioned_by = ''
    h.seller_approved_at = h.provisioned_at = h.revoked_at = None
    h.match.data_room_granted_at = None
    log(h, 'vdr_access_requested', who, role=h.access_role, expires=h.access_expires_at.isoformat())


def seller_approve(h, user):
    require_demo(h.match)
    who = actor(user, h.match, 'seller')
    if h.vdr_state != 'awaiting_seller' or not evidence_reviewed(h) or not future(h.access_expires_at):
        raise ValueError('A current, reviewed NDA and pending access scope are required.')
    h.seller_approved_hash = access_hash(h)
    h.seller_approved_at, h.seller_approved_by = now(), who
    h.vdr_state = 'pending_provisioning'
    log(h, 'seller_access_approved', who, scope_hash=h.seller_approved_hash)


def approval_current(h):
    return bool(evidence_reviewed(h) and h.seller_approved_hash and h.seller_approved_hash == access_hash(h)
                and release.valid_time(h.seller_approved_at) and h.seller_approved_by
                and future(h.access_expires_at))


def provision(h, user):
    require_demo(h.match)
    who = actor(user, h.match, 'deal_manager')
    if h.vdr_state != 'pending_provisioning' or not approval_current(h):
        raise ValueError('The seller must approve this access scope before mock provisioning.')
    h.vdr_state, h.provisioned_at, h.provisioned_by = 'active', now(), who
    h.match.data_room_granted_at = h.provisioned_at
    log(h, 'mock_vdr_access_confirmed', who, room=h.room_ref)


def access_active(h):
    return bool(h and h.vdr_state == 'active' and approval_current(h) and release.valid_time(h.provisioned_at)
                and h.provisioned_by and h.revoked_at is None and h.match.buyer.status == 'verified'
                and h.match.target.authority_verified_at is not None
                and h.match.stage not in {'dropped', 'closed'})


def revoke(h, user):
    # Revocation must still work after qualification or authority has been withdrawn.
    if not h.match.target.is_example or h.provider != 'mock':
        raise ValueError('External provider revocation is not connected.')
    who = actor(user, h.match, 'deal_manager') if getattr(user, 'role', None) == 'deal_manager' else actor(user, h.match, 'seller')
    if h.vdr_state == 'revoked':
        return
    h.vdr_state, h.revoked_at = 'revoked', now()
    h.seller_approved_hash = ''
    h.seller_approved_at = None
    h.match.data_room_granted_at = None
    log(h, 'mock_vdr_access_revoked', who)


def access_status(h):
    if h is None:
        return 'not_requested'
    if h.vdr_state == 'revoked':
        return 'revoked'
    if h.access_expires_at and not future(h.access_expires_at):
        return 'expired'
    if h.vdr_state == 'active' and not access_active(h):
        return 'blocked'
    return h.vdr_state


def cancel(h, user):
    require_demo(h.match)
    who = actor(user, h.match, 'deal_manager') if getattr(user, 'role', None) == 'deal_manager' else actor(user, h.match, 'buyer')
    if h.nda_state == 'cancelled':
        return
    if h.nda_state != 'requested':
        raise ValueError('Only an unsigned pending request can be cancelled; completed NDA evidence is retained.')
    h.nda_state = 'cancelled'
    h.vdr_state, h.revoked_at = 'revoked', now()
    h.match.data_room_granted_at = None
    log(h, 'mock_nda_cancelled', who)


def expire_demo(h, user):
    if not h.match.target.is_example or h.provider != 'mock':
        raise ValueError('Only mock access can simulate expiry.')
    who = actor(user, h.match, 'deal_manager')
    h.access_expires_at = now() - timedelta(seconds=1)
    h.match.data_room_granted_at = None
    log(h, 'mock_access_expiry_simulated', who)


def seed_examples(session):
    """Backfill fictional NDA evidence only. Never repairs or grants existing access."""
    from .models import Match, User
    manager = session.scalar(select(User).where(User.email == 'dm@demo.mamatch.test'))
    if manager is None:
        return
    for match in session.scalars(select(Match)):
        if match.target.is_example and match.stage in {'nda_signed', 'im_sent', 'loi', 'closing'} and get(match) is None:
            h = start(match, manager)
            apply_completion(h, MockSignatureProvider.completion(h), manager)
            review_authority(h, manager, 'FICTIONAL SEED: illustrative company/signatory authorisation, not real evidence')
    session.flush()
