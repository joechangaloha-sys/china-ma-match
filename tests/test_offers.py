
import pytest
from sqlalchemy import select

from mamatch import buyers, listing, matching, offers, pipeline, plans, teaser
from mamatch.models import Buyer, Target


def _t(s, code):
    return s.scalar(select(Target).where(Target.code_name == code))


def _verified(s, **kw):
    return s.scalar(select(Buyer).where(Buyer.status == "verified", Buyer.plan == kw.get("plan", "free")))


def test_free_private_seller_cannot_send_offers(seeded):
    delta = _t(seeded, "Project Delta")
    listing.unpublish(delta)
    m = matching.refresh(seeded, delta)[0]
    pipeline.move(seeded, m, "shortlisted")
    with pytest.raises(ValueError, match="paid plan"):
        offers.approve_and_send(seeded, m)
    plans.mark_seller_paid(delta, "INV-1")
    offers.approve_and_send(seeded, m)
    assert m.stage == "teaser_sent" and m.seller_approved_at is not None


def test_listed_target_cannot_send_offers_even_when_paid(seeded):
    kiln = _t(seeded, "Project Kiln")
    plans.mark_seller_paid(kiln, "INV-2")
    assert plans.seller_detailed_stats(kiln) and not plans.seller_outreach(kiln)


def test_publish_requires_approved_teaser_and_card_is_coarse(seeded):
    from mamatch.models import AdviserFirm

    t = Target(firm=seeded.scalar(select(AdviserFirm)), code_name="Project New", legal_name="新公司", city="嘉兴市",
               province="浙江", sector="food", revenue=30.0)
    seeded.add(t)
    seeded.flush()
    with pytest.raises(ValueError, match="teaser"):
        listing.publish(t)
    tz = teaser.draft(seeded, t, "zh")
    teaser.approve(tz)
    with pytest.raises(ValueError, match="seller must approve"):
        listing.publish(t)
    teaser.seller_approve(tz)
    listing.publish(t)
    assert t.status == "in_market"
    card = listing.card(t)
    assert card["region"] == "长三角"
    assert "浙江" not in str(card) and "嘉兴" not in str(card) and "新公司" not in str(card)


def test_verified_buyer_can_request_an_introduction(seeded):
    free = _verified(seeded, plan="free")
    delta = _t(seeded, "Project Delta")
    m = offers.express_interest(seeded, delta, free)
    assert m.channel == "listing" and m.stage == "interested"
    assert not offers.nda_available(m)  # the analyst approves the introduction first
    offers.analyst_decision(seeded, m, None, accept=True)
    assert offers.nda_available(m)


def test_unverified_buyer_sees_nothing(seeded):
    pending = seeded.scalar(select(Buyer).where(Buyer.status == "registered"))
    assert listing.board(seeded, pending) == []
    with pytest.raises(ValueError):
        offers.express_interest(seeded, _t(seeded, "Project Kiln"), pending)


def test_interest_from_board_and_name_disclosure(seeded):
    free = _verified(seeded, plan="free")
    kiln = _t(seeded, "Project Kiln")  # listed 12 days ago
    m = offers.express_interest(seeded, kiln, free)
    assert m.channel == "listing" and m.stage == "interested"
    assert offers.express_interest(seeded, kiln, free) is m  # no duplicates
    with pytest.raises(ValueError, match="NDA"):
        offers.disclose_names(m)
    pipeline.move(seeded, m, "nda_signed")
    offers.disclose_names(m)
    assert m.name_disclosed_at is not None


def test_outreach_candidates_put_priority_first_among_equal_fits(seeded):
    jade = _t(seeded, "Project Jade")
    cands = offers.outreach_candidates(jade)
    assert cands
    for a, b in zip(cands, cands[1:]):
        assert round(a.score, 1) >= round(b.score, 1)


def test_registration_flow(seeded):
    b = Buyer(name="新买方", kind="private")
    seeded.add(b)
    with pytest.raises(ValueError, match="invitation"):
        buyers.register(b, name="x", kind="private", uscc="", contact_name="", contact_email="",
                        target_sectors=["food"], target_regions=[], deal_size_min=None, deal_size_max=None,
                        target_deal_types=[], consent=True)
    buyers.invite(b)
    kw = dict(name="新买方", kind="private", uscc="91320500MA00001234", contact_name="张", contact_email="a@b.cn",
              target_sectors=["food"], target_regions=["江苏"], deal_size_min=10.0, deal_size_max=50.0,
              target_deal_types=[], funding_evidence="bank_letter", funding_max=40.0)
    with pytest.raises(ValueError, match="Consent"):
        buyers.register(b, consent=False, **kw)
    buyers.register(b, consent=True, **kw)
    assert b.status == "registered" and b.criteria_confirmed_at
    buyers.verify(b)
    assert b.status == "verified"
    buyers.register(b, consent=True, **{**kw, "uscc": "91320500MA00009999"})
    assert b.status == "registered"  # changed registry code is checked again


def test_verify_rejects_bad_uscc(seeded):
    b = Buyer(name="x", kind="listed", status="registered", uscc="123")
    with pytest.raises(ValueError, match="credit code"):
        buyers.verify(b)
