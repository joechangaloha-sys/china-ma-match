from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from mamatch import config, fees, matching, pipeline, plans
from mamatch.models import Target


def _t(s, code):
    return s.scalar(select(Target).where(Target.code_name == code))


def _to_closing(s, t):
    m = next(m for m in t.matches if m.stage in ("nda_signed", "interested")) if t.matches else None
    if m is None:
        m = matching.refresh(s, t)[0]
    while m.stage != "closing":
        nxt = [x for x in pipeline.allowed_next(m.stage) if x != "dropped"][0]
        pipeline.move(s, m, nxt)
    return m


def test_success_fee_minimum_and_credits(seeded):
    jade = _t(seeded, "Project Jade")  # prep pack 40k + outreach 20k already paid
    small = fees.success_fee(jade, 5.0)  # 4% of RMB 5m = 200k, below the minimum
    assert small.gross == config.SUCCESS_FEE_MIN_RMB
    assert small.credited == config.PREP_PACK_FEE_RMB + config.SELLER_PLAN_FEE_RMB
    assert small.net == small.gross - small.credited
    big = fees.success_fee(jade, 90.0)
    assert big.gross == 90_000_000 * config.SUCCESS_FEE_RATE
    assert big.platform_share == round(big.net * config.PLATFORM_SHARE, 2)


def test_closing_records_success_fee_once(seeded):
    jade = _t(seeded, "Project Jade")
    m = _to_closing(seeded, jade)
    charge = fees.record_closing(seeded, m, 85.0, "INV-9")
    assert m.stage == "closed" and jade.closing_value == 85.0
    assert charge.kind == "success" and charge.amount == fees.success_fee(jade, 85.0).net
    assert charge in jade.charges
    with pytest.raises(ValueError):
        fees.record_closing(seeded, m, 85.0)


def test_listed_only_seller_pays_no_success_fee(seeded):
    kiln = _t(seeded, "Project Kiln")
    m = _to_closing(seeded, kiln)
    assert fees.record_closing(seeded, m, 40.0) is None
    assert m.stage == "closed" and not kiln.charges


def test_outreach_expires_after_one_period(seeded):
    jade = _t(seeded, "Project Jade")
    assert fees.outreach_active(jade) and plans.seller_outreach(jade)
    later = datetime.now(timezone.utc) + timedelta(days=config.OUTREACH_PERIOD_DAYS + 1)
    assert not fees.outreach_active(jade, now=later)
    jade.plan_paid_at = datetime.now(timezone.utc) - timedelta(days=config.OUTREACH_PERIOD_DAYS + 1)
    assert not plans.seller_outreach(jade) and not plans.seller_detailed_stats(jade)
    fees.record_outreach(jade, "INV-RENEW")
    assert plans.seller_outreach(jade)


def test_prep_pack_paid_once(seeded):
    with pytest.raises(ValueError):
        fees.record_prep_pack(_t(seeded, "Project Jade"), "again")
    delta = _t(seeded, "Project Delta")
    c = fees.record_prep_pack(delta, "INV-3")
    assert c.amount == config.PREP_PACK_FEE_RMB and c in delta.charges
