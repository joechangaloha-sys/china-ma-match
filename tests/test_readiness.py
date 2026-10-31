from sqlalchemy import select
from mamatch import readiness
from mamatch.models import Target, Teaser


def test_readiness_uses_latest_language_version_and_invalidates_changed_source(seeded):
    target=seeded.scalar(select(Target).where(Target.code_name=='Project Delta'))
    current=readiness.snapshot(target,'en')
    assert current['teaser_ready']
    latest=current['teaser']
    draft=Teaser(target=target,version=latest.version+1,language='en',body=latest.body,
                 source_hash=latest.source_hash,reid_score=0)
    seeded.add(draft);seeded.flush()
    row=readiness.snapshot(target,'en')
    assert row['teaser']==draft and not row['teaser_ready'] and row['next']=='teaser'
    assert readiness.snapshot(target,'zh')['teaser_ready']
    seeded.delete(draft);seeded.flush();seeded.expire(target,['teasers'])
    target.revenue=(target.revenue or 0)+1
    assert not readiness.snapshot(target,'en')['teaser_ready']


def test_readiness_prioritises_authority_and_honours_terminal_state(seeded):
    target=seeded.scalar(select(Target).where(Target.code_name=='Project Jade'))
    target.authority_verified_at=None
    assert readiness.snapshot(target,'en')['next']=='authority'
    target.status='withdrawn'
    assert readiness.snapshot(target,'en')['next']=='terminal'


def test_expired_access_is_not_counted_as_current(seeded):
    from datetime import datetime,timedelta,timezone
    from mamatch.models import DealHandoff,User
    from mamatch import handoff
    h=seeded.scalar(select(DealHandoff).where(DealHandoff.nda_state=='completed'))
    assert h is not None
    target=h.match.target
    manager=seeded.scalar(select(User).where(User.role=='deal_manager'))
    seller=seeded.get(User,target.seller_user_id)
    handoff.request_access(h,manager,7);handoff.seller_approve(h,seller);handoff.provision(h,manager)
    before=readiness.snapshot(target,'en')['active']
    assert before>0
    h.access_expires_at=datetime.now(timezone.utc)-timedelta(days=1)
    row=readiness.snapshot(target,'en')
    assert row['active']==before-1
    assert (h.match,'expired') in row['attention']


def test_real_mandates_still_require_external_connections(seeded,monkeypatch):
    from mamatch import release
    target=seeded.scalar(select(Target).where(Target.code_name=='Project Delta'))
    from mamatch.models import InfoMemo
    seeded.add(InfoMemo(target=target,version=1,language='en',body={},source_hash='fixture'))
    seeded.flush()
    target.is_example=False
    monkeypatch.setattr(release,'ready',lambda artifact:True)
    assert readiness.snapshot(target,'en')['next']=='providers'
