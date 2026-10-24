import pytest
from sqlalchemy import select

from mamatch import matching, pipeline
from mamatch.models import Buyer, Target


def _target(session, code):
    return session.scalar(select(Target).where(Target.code_name == code))


def test_jade_ranks_auto_parts_buyer_first(seeded):
    ranked = matching.rank(seeded, _target(seeded, "Project Jade"))
    assert ranked[0].buyer.name == "示例·华东精密科技"
    assert any("Stated interest" in r for r in ranked[0].reasons)
    names = [x.buyer.name for x in ranked]
    assert "示例·皖江食品" not in names  # no sector fit


def test_scores_are_bounded_and_explained(seeded):
    for x in matching.rank(seeded, _target(seeded, "Project Kiln"), min_score=0):
        assert 0 <= x.score <= 1
        assert x.reasons


def test_no_sector_fit_scores_zero(seeded):
    jade = _target(seeded, "Project Jade")
    food = seeded.scalar(select(Buyer).where(Buyer.name == "示例·皖江食品"))
    assert matching.score(jade, food).score == 0


def test_refresh_keeps_pipeline_stage(seeded):
    jade = _target(seeded, "Project Jade")
    matches = matching.refresh(seeded, jade)
    first = matches[0]
    pipeline.move(seeded, first, "shortlisted", "call booked")
    matching.refresh(seeded, jade)
    assert first.stage == "shortlisted"
    assert len({m.buyer_id for m in jade.matches}) == len(jade.matches)


def test_pipeline_rules(seeded):
    m = matching.refresh(seeded, _target(seeded, "Project Jade"))[0]
    with pytest.raises(ValueError):
        pipeline.move(seeded, m, "loi")
    for stage in ["shortlisted", "teaser_sent", "nda_signed", "im_sent", "loi", "closing", "closed"]:
        pipeline.move(seeded, m, stage)
    assert pipeline.allowed_next("closed") == []
    assert [e.to_stage for e in m.events][-1] == "closed"
