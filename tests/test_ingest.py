import json
from pathlib import Path

from sqlalchemy import select

from mamatch.ingest import cninfo, profile
from mamatch.models import Buyer

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "cninfo_query.json").read_text())


def test_parse_strips_highlight_tags_and_builds_pdf_url():
    anns = cninfo.parse(FIXTURE)
    assert len(anns) == 10
    a = anns[0]
    assert "<em>" not in a.title and "收购" in a.title
    assert a.url.startswith("http://static.cninfo.com.cn/finalpage/")
    assert a.published_at.tzinfo is not None


def test_offline_extract_reads_counterparty_and_province():
    ann = next(a for a in cninfo.parse(FIXTURE) if a.sec_code == "603010")  # 收购青岛金博行新材料科技有限公司
    sig = profile.extract_offline(ann)
    assert sig["is_acquisition"]
    assert "新材料" in sig["counterparty"]
    assert "chemicals" in sig["target_sectors"]
    assert sig["target_provinces"] == ["山东"]


def test_upsert_builds_profile_and_skips_duplicates(session):
    anns = cninfo.parse(FIXTURE)
    for a in anns:
        profile.upsert(session, a, profile.extract_offline(a), "offline")
    buyers = session.scalars(select(Buyer).where(Buyer.source == "cninfo")).all()
    assert len(buyers) == len({a.sec_code for a in anns})

    again = [profile.upsert(session, a, profile.extract_offline(a), "offline") for a in anns]
    assert all(x is None for x in again)


def test_related_party_deal_does_not_widen_profile(session):
    ann = next(a for a in cninfo.parse(FIXTURE) if "关联交易" in a.title)
    sig = {**profile.extract_offline(ann), "target_sectors": ["chemicals"]}
    profile.upsert(session, ann, sig, "offline")
    buyer = session.scalar(select(Buyer).where(Buyer.external_id == ann.sec_code))
    assert buyer.target_sectors == []
    assert len(buyer.signals) == 1
