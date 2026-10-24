from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from mamatch import config, demand
from mamatch.models import Buyer, Target


def _buyer(session, i, **kw):
    spec = dict(name=f"B{i}", kind="listed", status="verified", target_sectors=["food"], target_regions=["江苏"],
                deal_size_min=10, deal_size_max=40, criteria_confirmed_at=datetime.now(timezone.utc))
    spec.update(kw)
    b = Buyer(**spec)
    session.add(b)
    return b


def _target(session, **kw):
    from mamatch.models import AdviserFirm

    t = Target(firm=AdviserFirm(name="f"), code_name="T", legal_name="L", province="浙江", sector="food", **kw)
    session.add(t)
    session.flush()
    return t


def test_shown_suppresses_and_rounds():
    k = config.MIN_GROUP_SIZE
    assert demand.shown(0) == f"<{k}"
    assert demand.shown(k - 1) == f"<{k}"
    assert demand.shown(k) == f"{k}+"
    assert demand.shown(2 * k + 3) == f"{2 * k}+"


def test_small_group_has_no_breakdown(session):
    for i in range(4):
        _buyer(session, i)
    d = demand.for_target(session, _target(session), detailed=True)
    assert d.total == "<5" and not d.enough and d.breakdowns == []


def test_breakdown_hidden_when_any_cell_is_small(session):
    for i in range(6):
        _buyer(session, i)
    _buyer(session, 99, kind="pe")  # one fund among listed companies: identifiable by elimination
    d = demand.for_target(session, _target(session), detailed=True)
    assert d.total == "5+"
    by_type = next(b for b in d.breakdowns if "buyer type" in b.title)
    assert by_type.suppressed and by_type.rows == []
    by_size = next(b for b in d.breakdowns if "deal size" in b.title)
    assert not by_size.suppressed and all(n.endswith("+") for _, n in by_size.rows)


def test_only_verified_and_recently_confirmed_buyers_count(session):
    for i in range(5):
        _buyer(session, i)
    _buyer(session, 10, status="registered")
    _buyer(session, 11, criteria_confirmed_at=datetime.now(timezone.utc) - timedelta(days=config.CRITERIA_TTL_DAYS + 1))
    assert len(demand.eligible(session)) == 5


def test_region_matching_uses_macro_region(session):
    for i in range(5):
        _buyer(session, i, target_regions=["广东"])
    assert demand.for_target(session, _target(session)).total == "<5"  # 浙江 is 长三角, not 珠三角
    for i in range(5, 10):
        _buyer(session, i, target_regions=[])  # anywhere
    assert demand.for_target(session, _target(session)).total == "5+"


def test_seeded_demand_never_contains_buyer_names(seeded):
    names = [b.name for b in seeded.scalars(select(Buyer))]
    for t in seeded.scalars(select(Target)):
        text = repr(demand.for_target(seeded, t, detailed=True))
        assert not any(n in text for n in names)
