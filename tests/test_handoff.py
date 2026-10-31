from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import select, func

from mamatch import handoff, offers
from mamatch.models import DealHandoff, HandoffEvent, Target, User, Document


@pytest.fixture
def flow(seeded):
    t = seeded.scalar(select(Target).where(Target.code_name == 'Project Jade'))
    match = next(m for m in t.matches if m.stage in offers.AFTER_NDA)
    manager = seeded.scalar(select(User).where(User.role == 'deal_manager'))
    seller = seeded.get(User, t.seller_user_id)
    return match, handoff.get(match), manager, seller


def activate(flow):
    match, h, manager, seller = flow
    handoff.request_access(h, manager, 7)
    handoff.seller_approve(h, seller)
    assert not handoff.access_active(h)
    handoff.provision(h, manager)
    return h


def test_access_requires_review_owner_and_separate_provisioning(flow):
    match, h, manager, seller = flow
    h.reviewed_at = None
    with pytest.raises(ValueError, match='signer-authority'):
        handoff.request_access(h, manager)
    handoff.review_authority(h, manager, 'Fictional company resolution, section 2')
    handoff.request_access(h, manager)
    with pytest.raises(ValueError, match='seller'):
        handoff.provision(h, manager)
    handoff.seller_approve(h, seller)
    assert handoff.access_status(h) == 'pending_provisioning'
    assert match.data_room_granted_at is None
    handoff.provision(h, manager)
    assert handoff.access_active(h)


@pytest.mark.parametrize('changed', ['room_ref', 'access_role', 'access_expires_at'])
def test_access_scope_changes_invalidate_owner_approval(flow, changed):
    h = activate(flow)
    setattr(h, changed, {'room_ref':'mock-room:other', 'access_role':'editor',
                        'access_expires_at':handoff.now()+timedelta(days=14)}[changed])
    assert not handoff.access_active(h)
    assert handoff.access_status(h) == 'blocked'


def test_expiry_and_revocation_block_actual_demo_documents(flow, seeded):
    match, h, manager, seller = flow
    h = activate(flow)
    doc = Document(target_id=match.target_id, kind='other', filename='fixture.txt', stored_path='/not-served', in_data_room=True)
    seeded.add(doc); seeded.flush()
    assert offers.can_view_document(match, doc)
    h.access_expires_at = handoff.now() - timedelta(seconds=1)
    assert handoff.access_status(h) == 'expired'
    assert not offers.can_view_document(match, doc)
    handoff.request_access(h, manager); handoff.seller_approve(h, seller); handoff.provision(h, manager)
    handoff.revoke(h, seller)
    assert handoff.access_status(h) == 'revoked'
    assert not offers.can_view_document(match, doc)
    receipt = handoff.MockSignatureProvider.completion(h)
    handoff.apply_completion(h, receipt, manager)  # delivery retry cannot revive access
    assert not handoff.access_active(h)
    assert h.vdr_state == 'revoked'


def test_duplicate_completion_keeps_audit_count_and_approvals(flow, seeded):
    match, h, manager, seller = flow
    activate(flow)
    count = seeded.scalar(select(func.count(HandoffEvent.id)))
    original_hash = h.seller_approved_hash
    handoff.apply_completion(h, handoff.MockSignatureProvider.completion(h), manager)
    assert seeded.scalar(select(func.count(HandoffEvent.id))) == count
    assert h.seller_approved_hash == original_hash and handoff.access_active(h)


@pytest.mark.parametrize('field', ['envelope_id','template_hash','party_hash','signed_hash','evidence_ref','event_id'])
def test_mismatched_receipt_cannot_complete_or_change_a_workflow(flow, field):
    match, h, manager, seller = flow
    original = h.signed_document_hash
    bad = replace(handoff.MockSignatureProvider.completion(h), **{field:'forged-or-stale'})
    with pytest.raises(ValueError, match='Receipt'):
        handoff.apply_completion(h, bad, manager)
    assert h.signed_document_hash == original


def test_party_changes_and_template_updates_lock_access(flow, monkeypatch):
    match, h, manager, seller = flow
    activate(flow)
    original = match.buyer.uscc
    match.buyer.uscc = 'changed-company'
    assert not handoff.signature_complete(h) and not handoff.access_active(h)
    match.buyer.uscc = original
    assert handoff.access_active(h)
    monkeypatch.setattr(offers, 'NDA_VERSION', 'new-version')
    assert not handoff.signature_complete(h)


def test_mock_cannot_be_used_for_real_mandates(flow):
    match, h, manager, seller = flow
    match.target.is_example = False
    for call in (lambda:handoff.start(match,manager), lambda:handoff.request_access(h,manager),
                 lambda:handoff.review_authority(h,manager,'evidence'), lambda:handoff.seller_approve(h,seller),
                 lambda:handoff.provision(h,manager), lambda:handoff.revoke(h,manager)):
        with pytest.raises(ValueError): call()
    assert not handoff.access_active(h)


def test_roles_and_mandate_owner_are_enforced(flow, seeded):
    match, h, manager, seller = flow
    with pytest.raises(ValueError): handoff.review_authority(h, seller, 'note')
    with pytest.raises(ValueError): handoff.request_access(h, seller)
    handoff.request_access(h, manager)
    with pytest.raises(ValueError): handoff.seller_approve(h, manager)
    wrong = User(email='wrong-owner@example.invalid',password_hash='disabled',role='seller',active=True)
    seeded.add(wrong); seeded.flush()
    with pytest.raises(ValueError, match='mandate owner'): handoff.seller_approve(h, wrong)
    handoff.seller_approve(h, seller)
    with pytest.raises(ValueError): handoff.provision(h, seller)


@pytest.mark.parametrize('days', [-1, 0, 31, 365])
def test_access_period_is_bounded(flow, days):
    with pytest.raises(ValueError, match='1 and 30'):
        handoff.request_access(flow[1], flow[2], days)


def test_rechecking_authority_invalidates_an_existing_grant(flow):
    match, h, manager, seller = flow
    activate(flow)
    handoff.review_authority(h, manager, 'New fictional authority review')
    assert not handoff.access_active(h)
    assert h.vdr_state == 'awaiting_seller' and match.data_room_granted_at is None


def test_completed_mock_nda_cannot_be_cancelled_as_if_unsigned(flow):
    with pytest.raises(ValueError, match='unsigned'):
        handoff.cancel(flow[1], flow[2])


def test_cancelled_request_rejects_late_receipt_and_old_envelope(flow):
    match, h, manager, seller = flow
    h.nda_state = 'cancelled'
    handoff.start(match, manager)
    old = handoff.MockSignatureProvider.completion(h)
    handoff.cancel(h, manager)
    with pytest.raises(ValueError, match='pending'):
        handoff.apply_completion(h, old, manager)
    handoff.start(match, manager)
    with pytest.raises(ValueError, match='Receipt'):
        handoff.apply_completion(h, old, manager)
    assert h.nda_state == 'requested'


def test_seed_does_not_reactivate_revoked_access(flow, seeded):
    from mamatch.seed import seed
    h = activate(flow)
    handoff.revoke(h, flow[3])
    count = seeded.scalar(select(func.count(DealHandoff.id)))
    seed(seeded)
    assert h.vdr_state == 'revoked'
    assert seeded.scalar(select(func.count(DealHandoff.id))) == count
