import pytest
from sqlalchemy import select

from mamatch import datacheck, fees, infomemo
from mamatch.models import Target


def _t(s, code):
    return s.scalar(select(Target).where(Target.code_name == code))


def test_rules_catch_seeded_issues(seeded):
    codes = {f["code"] for f in datacheck.rules(_t(seeded, "Project Jade"))}
    assert {"invoice_gap", "social_insurance", "permits_personal", "owner_guarantees"} <= codes
    assert "missing_financials" not in codes


def test_rules_flag_missing_data_and_inconsistencies(seeded):
    t = _t(seeded, "Project Delta")
    codes = {f["code"] for f in datacheck.rules(t)}
    assert {"missing_financials", "missing_disclosures"} <= codes
    y = datacheck.years()
    t.financials = {y[0]: {"revenue": 40, "net_profit": 2}, y[1]: {"revenue": 70, "net_profit": 3},
                    y[2]: {"revenue": 72, "gross_profit": 5, "net_profit": 6}}
    t.disclosures = {"land": "collective"}
    codes = {f["code"] for f in datacheck.rules(t)}
    assert {f"revenue_swing_{y[1]}", "np_above_gp", "intake_mismatch", "collective_land"} <= codes


def test_check_and_memo_need_the_prep_pack(seeded):
    delta = _t(seeded, "Project Delta")
    with pytest.raises(ValueError, match="preparation pack"):
        datacheck.run(seeded, delta)
    with pytest.raises(ValueError, match="preparation pack"):
        infomemo.draft(seeded, delta)
    fees.record_prep_pack(delta, "INV")
    assert datacheck.run(seeded, delta).generated_by == "rules"  # data export is off in tests


@pytest.mark.parametrize("language", ["zh", "en"])
def test_memo_masks_identity_and_has_exact_figures(seeded, language):
    t = _t(seeded, "Project Jade")
    m = infomemo.draft(seeded, t, language)
    text = str(m.body)
    for secret in (t.legal_name, t.short_name, t.owner_name, "宁波", "恒泰"):
        assert secret not in text
    assert m.name_findings == []
    assert "126" in text  # exact revenue in the financial table
    infomemo.approve(m)


def test_memo_with_a_name_cannot_be_approved(seeded):
    t = _t(seeded, "Project Jade")
    m = infomemo.draft(seeded, t)
    m.body["sections"][0]["paragraphs"].append(t.legal_name)
    from mamatch import reid

    _, found = reid.check(t, m.body)
    m.name_findings = [f for f in found if f["field"] in infomemo.IDENTITY_FIELDS]
    with pytest.raises(ValueError):
        infomemo.approve(m)
