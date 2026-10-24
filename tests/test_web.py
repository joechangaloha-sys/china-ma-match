import re

from fastapi.testclient import TestClient
from sqlalchemy import select

from mamatch import config, db
from mamatch.models import Buyer, Target
from mamatch.seed import seed


def _client(db_url, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", db_url)
    with db.session_scope(db_url) as s:
        seed(s)
    from mamatch.web.app import app

    return TestClient(app)


def _get(db_url, model, **where):
    with db.session_scope(db_url) as s:
        return s.scalar(select(model).filter_by(**where))


def test_operator_flow(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    home = c.get("/").text
    assert "Project Jade" in home and "示例·待审核买方A" in home
    assert "示例·华东精密科技" in c.get("/buyers?status=verified&sector=auto_parts").text
    assert c.get("/demand").status_code == 200

    r = c.post("/targets", data={"code_name": "Project Test", "legal_name": "测试有限公司", "province": "浙江",
                                 "sector": "machinery", "revenue": "80", "asking_value": "60"})
    assert r.status_code == 200 and "Project Test" in r.text
    target_url = str(r.url.path)
    r = c.post(f"{target_url}/teaser", data={"language": "zh"})
    assert "识别风险" in r.text and "测试有限公司" in r.text  # legal name shown only in the internal panel
    r = c.post(f"{target_url}/match")
    assert "示例·苏南智能装备" in r.text
    assert c.get("/pipeline").status_code == 200


def test_operator_cannot_send_teaser_by_moving_stage(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    jade = _get(db_url, Target, code_name="Project Jade")
    with db.session_scope(db_url) as s:
        m = next(m for m in s.get(Target, jade.id).matches if m.stage == "shortlisted")
    r = c.post(f"/matches/{m.id}/move", data={"to_stage": "teaser_sent"})
    assert "seller approves" in r.text
    with db.session_scope(db_url) as s:
        assert s.get(type(m), m.id).stage == "shortlisted"


def test_seller_page_hides_buyer_names(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    jade = _get(db_url, Target, code_name="Project Jade")
    page = c.get(f"/s/{jade.seller_token}").text
    with db.session_scope(db_url) as s:
        names = [b.name for b in s.scalars(select(Buyer))]
    assert not [n for n in names if n in page]
    assert not re.search(r"RMB [\d.]+–[\d.]*m", page) and "Deal size fits stated range" in page  # fit shown, buyer's range not
    assert "批准并发送" in page and "按买方类型" in page  # paid plan: outreach and breakdown

    kiln = _get(db_url, Target, code_name="Project Kiln")
    page = c.get(f"/s/{kiln.seller_token}").text
    assert "按买方类型" not in page and "私密推介方案" in page  # free plan: total only
    assert c.get("/s/not-a-token").status_code == 404


def test_seller_approves_buyer_and_buyer_responds(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    jade = _get(db_url, Target, code_name="Project Jade")
    page = c.get(f"/s/{jade.seller_token}").text
    match_id = re.search(rf"/s/{jade.seller_token}/matches/(\d+)/approve", page).group(1)
    r = c.post(f"/s/{jade.seller_token}/matches/{match_id}/approve")
    assert "Teaser sent" in r.text
    with db.session_scope(db_url) as s:
        from mamatch.models import Match

        buyer_token = s.get(Match, int(match_id)).buyer.invite_token
    page = c.get(f"/b/{buyer_token}").text
    assert "Project Jade" in page or "汽车零部件" in page
    r = c.post(f"/b/{buyer_token}/matches/{match_id}/respond", data={"interested": "1"})
    assert "买方有意向" in r.text


def test_buyer_registers_from_invite(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    b = _get(db_url, Buyer, external_id="EXP002")  # invited
    page = c.get(f"/b/{b.invite_token}").text
    assert "Listed deals" not in page  # not verified yet
    r = c.post(f"/b/{b.invite_token}/register", data={
        "name": "示例·已邀请买方B", "kind": "private", "uscc": "91320500MA00004321",
        "target_sectors": ["food", "packaging"], "target_regions": ["江苏"], "deal_size_min": "10",
        "deal_size_max": "60", "consent": "1"})
    assert "Criteria saved" in r.text
    assert _get(db_url, Buyer, external_id="EXP002").status == "registered"
    assert c.get("/b/not-a-token").status_code == 404


def test_free_buyer_sees_old_listing_only(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    with db.session_scope(db_url) as s:
        token = s.scalar(select(Buyer.invite_token).where(Buyer.status == "verified", Buyer.plan == "free"))
    page = c.get(f"/b/{token}").text
    assert "Project Kiln" in page and "Project Delta" not in page
    assert "priority members only" in page


def test_operator_invites_two_buyers_by_hand(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    for name in ("手动买方一", "手动买方二"):
        r = c.post("/buyers", data={"name": name, "kind": "private"})
        assert r.status_code == 200 and "/b/" in r.text


def test_seller_submits_data_and_sees_fees(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    delta = _get(db_url, Target, code_name="Project Delta")
    page = c.get(f"/s/{delta.seller_token}").text
    assert "出售准备包" in page and "平台分成" not in page  # seller never sees the platform share
    from mamatch import datacheck

    y = datacheck.years()[-1]
    r = c.post(f"/s/{delta.seller_token}/data", data={f"fin_{y}_revenue": "85", f"fin_{y}_net_profit": "9",
                                                       "d_permits_personal": "yes", "d_land": "leased"})
    assert "Data saved" in r.text
    t = _get(db_url, Target, code_name="Project Delta")
    assert t.financials[y]["revenue"] == 85 and t.disclosures["permits_personal"] is True

    r = c.post(f"/targets/{t.id}/datacheck")
    assert "preparation pack" in r.text
    c.post(f"/targets/{t.id}/prep-pack", data={"invoice_ref": "INV-7"})
    r = c.post(f"/targets/{t.id}/datacheck")
    assert "实控人个人名下" in r.text


def test_buyer_sees_memo_only_after_nda(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    jade = _get(db_url, Target, code_name="Project Jade")
    with db.session_scope(db_url) as s:
        t = s.get(Target, jade.id)
        nda = next(m for m in t.matches if m.stage == "nda_signed")
        waiting = next(m for m in t.matches if m.stage == "shortlisted")
        nda_token, waiting_token = nda.buyer.invite_token, waiting.buyer.invite_token
    assert "信息备忘录" in c.get(f"/b/{nda_token}").text
    assert "四、财务摘要" not in c.get(f"/b/{waiting_token}").text


def test_closing_goes_through_the_fee_form(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    jade = _get(db_url, Target, code_name="Project Jade")
    with db.session_scope(db_url) as s:
        m = next(m for m in s.get(Target, jade.id).matches if m.stage == "nda_signed")
        mid = m.id
    for stage in ("im_sent", "loi", "closing"):
        c.post(f"/matches/{mid}/move", data={"to_stage": stage})
    r = c.post(f"/matches/{mid}/move", data={"to_stage": "closed"})
    assert "Record the closing value" in r.text
    r = c.post(f"/matches/{mid}/close", data={"deal_value": "88", "invoice_ref": "INV-C"})
    assert "Success fee RMB" in r.text
