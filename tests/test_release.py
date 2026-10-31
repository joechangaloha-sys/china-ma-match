from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from mamatch import infomemo, listing, offers, release, teaser
from mamatch.models import Document, ReleaseClaim, Target, User


def jade(s):
    return s.scalar(select(Target).where(Target.code_name == 'Project Jade'))


def test_edited_body_and_changed_sources_invalidate_both_approvals(seeded):
    t = jade(seeded)
    a = offers.shared_teaser(t)
    assert release.ready(a)
    original = dict(a.body)
    a.body = {**a.body, 'summary': 'An unsupported replacement description'}
    assert not release.evidence_complete(a)
    assert not release.ready(a)
    assert offers.shared_teaser(t) is None
    a.body = original
    assert release.ready(a)
    t.revenue += 1
    assert not release.ready(a)
    with pytest.raises(ValueError):
        listing.publish(t)


def test_memo_needs_seller_approval_for_same_version(seeded):
    t = jade(seeded)
    a = infomemo.draft(seeded, t, 'en', use_llm=False)
    infomemo.approve(a)
    # Hide other memo versions: only this one is under test.
    for m in t.memos:
        if m is not a:
            m.status = 'draft'
    assert infomemo.shared_memo(t, 'en') is None
    infomemo.seller_approve(a)
    assert infomemo.shared_memo(t, 'en') is a
    a.body = {**a.body, 'title': 'Changed memo'}
    assert infomemo.shared_memo(t, 'en') is None


def test_real_evidence_requires_owned_document_and_named_review(seeded, clean_file):
    t = jade(seeded)
    a = teaser.draft(seeded, t, 'en', use_llm=False)
    t.is_example = False
    reviewer = seeded.scalar(select(User).where(User.role == 'deal_manager'))
    owner = seeded.get(User, t.seller_user_id)
    path = release.assertions(a.body)[0][0]
    with pytest.raises(ValueError, match='source document'):
        release.review_claim(a, path, 'Just a reference string is insufficient', reviewer)
    wrong = Document(target_id=seeded.scalar(select(Target.id).where(Target.code_name == 'Project Delta')),
                     kind='other', filename='wrong.txt', stored_path='/not-served', sha256='wrong')
    source = Document(target_id=t.id, kind='other', filename='source.txt', stored_path='/not-served', sha256='first')
    clean_file(source)
    seeded.add_all([wrong, source]); seeded.flush()
    with pytest.raises(ValueError, match='this mandate'):
        release.review_claim(a, path, 'page 1', reviewer, wrong.id)
    with pytest.raises(ValueError, match='deal manager'):
        release.review_claim(a, path, 'page 1', owner, source.id)
    for claim_path, _ in release.assertions(a.body):
        release.review_claim(a, claim_path, 'Checked page 1 against source document', reviewer, source.id)
    teaser.approve(a, reviewer)
    teaser.seller_approve(a, owner)
    assert release.ready(a)
    source.sha256 = 'replacement'
    assert not release.ready(a)


def test_old_approvals_without_hashes_are_not_trusted(seeded):
    a = offers.shared_teaser(jade(seeded))
    a.analyst_content_hash = ''
    assert not release.ready(a)
    with pytest.raises(ValueError):
        teaser.seller_approve(a)


def test_invalid_revenue_blocked_but_disclosed_losses_allowed(seeded):
    t = jade(seeded)
    t.net_profit = -2
    a = teaser.draft(seeded, t, 'en', use_llm=False)
    assert 'Loss-making' in str(a.body)
    teaser.approve(a)
    teaser.seller_approve(a)
    assert release.ready(a)
    t.revenue = -30
    b = teaser.draft(seeded, t, 'en', use_llm=False)
    with pytest.raises(ValueError, match='Invalid financial'):
        teaser.approve(b)


def test_drafting_never_calls_ai_with_intake_or_financials(seeded, monkeypatch):
    from mamatch import llm
    monkeypatch.setattr(llm, 'structured', lambda *a, **kw: pytest.fail('Document generator called AI'))
    t = jade(seeded)
    assert teaser.draft(seeded, t, use_llm=True).generated_by == 'offline'
    assert infomemo.draft(seeded, t, use_llm=True).generated_by == 'offline'


def test_real_mandates_cannot_click_sign_or_download_uploads(seeded, clean_file):
    t = jade(seeded)
    m = next(m for m in t.matches if m.stage in offers.AFTER_NDA)
    doc = Document(target_id=t.id, kind='other', filename='confidential.txt', stored_path='/not-served', in_data_room=True)
    clean_file(doc)
    seeded.add(doc); seeded.flush()
    from mamatch import handoff
    manager = seeded.scalar(select(User).where(User.role == 'deal_manager'))
    owner = seeded.get(User, t.seller_user_id)
    h = handoff.get(m)
    handoff.request_access(h, manager)
    handoff.seller_approve(h, owner)
    handoff.provision(h, manager)
    assert offers.can_view_document(m, doc)
    t.is_example = False
    assert not offers.can_view_document(m, doc)
    with pytest.raises(ValueError, match='e-signature provider'):
        offers.accept_nda(seeded, m, None)


def test_fictional_seed_is_idempotent_and_never_repairs_real_approvals(seeded):
    from mamatch.seed import seed
    before = seeded.scalar(select(ReleaseClaim.id).order_by(ReleaseClaim.id.desc()))
    seed(seeded)
    after = seeded.scalar(select(ReleaseClaim.id).order_by(ReleaseClaim.id.desc()))
    assert before == after


def test_signin_failures_are_limited_per_account(seeded):
    from mamatch import auth
    from mamatch.seed import DEMO_PASSWORD
    email = 'dm@demo.mamatch.test'
    for _ in range(10):
        assert auth.authenticate(seeded, email, 'wrong-password') is None
    assert auth.authenticate(seeded, email, DEMO_PASSWORD) is None
    assert auth.authenticate(seeded, 'seller.jade@demo.mamatch.test', DEMO_PASSWORD) is not None


def test_invalid_or_future_approval_dates_never_release(seeded):
    from datetime import timedelta
    a = offers.shared_teaser(jade(seeded))
    a.seller_approved_at = datetime.now(timezone.utc) + timedelta(days=1)
    assert not release.ready(a)
    # Avoid flushing an invalid database type: test the time validator directly.
    assert not release.valid_time('not-a-date')
    assert not release.valid_time(None)
