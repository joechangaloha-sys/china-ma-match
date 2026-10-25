import pytest
from sqlalchemy import select

from mamatch import reid, teaser
from mamatch.models import Target


def _jade(session) -> Target:
    return session.scalar(select(Target).where(Target.code_name == "Project Jade"))


def test_band_labels():
    assert teaser.band(126, [20, 50, 100, 200, 500], "百万元") == "100–200百万元"
    assert teaser.band(800, [20, 50, 100, 200, 500], "百万元") == "500百万元以上"
    assert teaser.band(None, [1], "x") == "未披露"


@pytest.mark.parametrize("language", ["zh", "en"])
def test_offline_draft_is_low_risk(seeded, language):
    tz = teaser.draft(seeded, _jade(seeded), language)
    assert tz.generated_by == "offline"
    assert reid.risk_label(tz.reid_score) == "low", tz.reid_findings
    teaser.approve(tz)
    assert tz.status == "approved"


def test_reid_flags_names_city_and_exact_figures(seeded):
    t = _jade(seeded)
    leaky = {"headline": "恒泰部件出售", "summary": "宁波工厂，2003年成立，员工180人，收入1.26亿，营收12,600万。",
             "highlights": ["电话 13812345678"], "ideal_buyer": ""}
    score, findings = reid.check(t, leaky)
    fields = {f["field"] for f in findings}
    assert {"short_name", "city", "exact_year", "exact_figure", "contact"} <= fields
    assert reid.risk_label(score) == "high"


def test_ranges_are_not_flagged(seeded):
    score, findings = reid.check(_jade(seeded), {"summary": "员工300–1000人，收入100–200百万元，经营20年以上，规模1000人以上"})
    assert findings == [] and score == 0


def test_cannot_approve_risky_teaser(seeded):
    t = _jade(seeded)
    tz = teaser.draft(seeded, t, "zh")
    tz.reid_score = 0.9
    with pytest.raises(ValueError):
        teaser.approve(tz)


def test_facts_never_contain_identifying_fields(seeded):
    t = _jade(seeded)
    text = str(teaser.facts(t))
    for secret in (t.legal_name, t.short_name, t.owner_name, "宁波"):
        assert secret not in text
