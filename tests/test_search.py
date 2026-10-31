from sqlalchemy import select

from mamatch import listing
from mamatch.models import Target


def _t(s, code):
    return s.scalar(select(Target).where(Target.code_name == code))


def _codes(s, **filters):
    return {t.code_name for t in listing.public_board(s, **filters)}


def test_keyword_matches_products_sector_and_synonyms(seeded):
    assert _codes(seeded, q="防腐涂料") == {"Project Kiln"}
    assert _codes(seeded, q="assembly lines") == {"Project Delta"}
    assert _codes(seeded, q="自动化") == {"Project Delta"}  # sector keyword, not in the product line
    assert _codes(seeded, q="coatings wind") == {"Project Kiln"}  # every word must match
    assert _codes(seeded, q="面包") == set()


def test_band_filters(seeded):
    kiln = _t(seeded, "Project Kiln")  # revenue 48, 65 staff, founded 2011
    assert "Project Kiln" in _codes(seeded, revenue_min="20", revenue_max="50")
    assert "Project Kiln" not in _codes(seeded, revenue_min="50")
    assert "Project Kiln" in _codes(seeded, employees_min="50", employees_max="100")
    assert "Project Kiln" not in _codes(seeded, employees_max="50")
    assert "Project Kiln" in _codes(seeded, years_min="10")
    assert "Project Kiln" not in _codes(seeded, years_min="20")
    assert kiln.sale_reason == "strategic"
    assert _codes(seeded, reasons=["strategic"]) == {"Project Kiln"}
    assert "Project Kiln" not in _codes(seeded, deal_types=["full_sale"])


def test_off_band_values_cannot_probe_exact_figures(seeded):
    # 48.0 is Kiln's exact revenue; a filter of 48 or 48.1 is not a published edge, so it is ignored.
    everyone = _codes(seeded)
    assert _codes(seeded, revenue_min="48") == everyone
    assert _codes(seeded, revenue_min="48.1") == everyone
    assert _codes(seeded, employees_min="66") == everyone


def test_profit_and_margin_only_where_the_seller_shows_earnings(seeded):
    delta = _t(seeded, "Project Delta")
    assert not delta.show_earnings
    assert _codes(seeded, profitable="yes") == {"Project Kiln"}  # Delta is profitable but did not agree to show it
    assert "Project Kiln" in _codes(seeded, margin_min="10")  # 6.0 / 48 = 12.5%
    assert "Project Kiln" not in _codes(seeded, margin_min="20")
    card = listing.card(_t(seeded, "Project Kiln"))
    assert card["profitable"] is True and card["margin_band"] == "10–20%"
    assert listing.card(delta)["margin_band"] == "" and listing.card(delta)["profitable"] is None


def test_product_text_is_checked_before_publishing(seeded):
    import pytest

    jade = _t(seeded, "Project Jade")
    jade.products_zh = "恒泰牌汽车空调管路"  # a brand
    with pytest.raises(ValueError, match="re-identification|seller must approve"):
        listing.publish(jade)


def test_cards_show_only_checks_actually_done(seeded):
    delta, kiln = _t(seeded, "Project Delta"), _t(seeded, "Project Kiln")
    assert [c.split()[0] for c in listing.card(delta)["checks"]] == ["出售权限已核验", "由已认证的会计师或律师协助准备"]
    assert listing.checks(kiln) == ["authority"]
    kiln.authority_verified_at = None
    assert listing.card(kiln)["checks"] == []


def test_check_heading_is_scoped_and_dated(seeded):
    delta, kiln = _t(seeded, "Project Delta"), _t(seeded, "Project Kiln")
    c = listing.card(delta)
    assert c["checks_as_of"] and len(c["checks_as_of"]) == 10  # YYYY-MM-DD
    kiln.authority_verified_at = None
    assert listing.card(kiln)["checks_as_of"] == ""
