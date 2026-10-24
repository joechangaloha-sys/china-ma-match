import re

from fastapi.testclient import TestClient
from sqlalchemy import select

from mamatch import config, datacheck, db
from mamatch.models import Buyer, Match, Target
from mamatch.seed import seed

I = "/internal"


def _client(db_url, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", db_url)
    with db.session_scope(db_url) as s:
        seed(s)
    from mamatch.web.app import app

    return TestClient(app)


def _get(db_url, model, **where):
    with db.session_scope(db_url) as s:
        return s.scalar(select(model).filter_by(**where))


def _buyer_names(db_url):
    with db.session_scope(db_url) as s:
        return [b.name for b in s.scalars(select(Buyer))]


def test_public_site_shows_listed_sellers_only(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    page = c.get("/").text
    assert "Project Kiln" in page and "Project Delta" in page
    assert "Project Jade" not in page  # private
    assert "期望价格" in page and "出让股权" in page  # size and the ask
    assert not [n for n in _buyer_names(db_url) if n in page]
    assert "内部" not in page and I not in page
    for gone in ("/buyers", "/demand", "/b/x"):
        assert c.get(gone).status_code == 404


def test_public_listing_never_identifies_the_seller(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    kiln = _get(db_url, Target, code_name="Project Kiln")
    page = c.get(f"/listings/{kiln.id}").text
    for secret in (kiln.legal_name, kiln.short_name, kiln.owner_name, "无锡", "江苏"):
        assert secret not in page
    jade = _get(db_url, Target, code_name="Project Jade")
    assert c.get(f"/listings/{jade.id}").status_code == 404


def test_inquiry_reaches_the_internal_pages(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    kiln = _get(db_url, Target, code_name="Project Kiln")
    r = c.post(f"/listings/{kiln.id}/inquiry", data={"name": "张伟", "company": "示例·某涂料集团", "kind": "listed",
                                                     "contact": "zw@example.cn", "message": "寻找华东涂料企业"})
    assert "请" in r.text  # consent missing: asked again
    r = c.post(f"/listings/{kiln.id}/inquiry", data={"name": "张伟", "company": "示例·某涂料集团", "kind": "listed",
                                                     "contact": "zw@example.cn", "message": "寻找华东涂料企业",
                                                     "consent": "1"})
    assert "Thank you" in r.text
    assert "示例·某涂料集团" not in c.get("/").text
    internal = c.get(I).text
    assert "示例·某涂料集团" in internal and "寻找华东涂料企业" in internal
    assert "示例·某涂料集团" in c.get(f"{I}/pipeline").text
    c.post(f"/listings/{kiln.id}/inquiry", data={"name": "张伟", "contact": "zw@example.cn", "consent": "1"})
    with db.session_scope(db_url) as s:
        assert len(s.scalars(select(Buyer).where(Buyer.contact_email == "zw@example.cn")).all()) == 1


def test_internal_pages_are_marked_internal(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    for url in (I, f"{I}/pipeline", f"{I}/targets/new"):
        page = c.get(url).text
        assert "Internal page for the adviser only" in page


def test_adviser_flow(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    r = c.post(f"{I}/targets", data={"code_name": "Project Test", "legal_name": "测试有限公司", "province": "浙江",
                                      "sector": "machinery", "revenue": "80", "asking_value": "36", "stake_pct": "60",
                                      "payment_terms": "cash", "founder_transition": "12m", "timing": "6m"})
    assert r.status_code == 200 and "Project Test" in r.text
    url = str(r.url.path)
    assert "30–50百万元" in r.text and "60–70%" in r.text and "50–80百万元" in r.text  # price, stake, implied value
    r = c.post(f"{url}/visibility", data={"visibility": "listed"})
    assert "Approve a low-risk teaser" in r.text
    r = c.post(f"{url}/teaser", data={"language": "zh"})
    assert "识别风险" in r.text and "测试有限公司" in r.text  # legal name only in the internal panel
    tid = url.rsplit("/", 1)[1]
    tz_id = re.search(rf"{I}/teasers/(\d+)/approve", r.text).group(1)
    c.post(f"{I}/teasers/{tz_id}/approve")
    c.post(f"{url}/visibility", data={"visibility": "listed"})
    assert "Project Test" in c.get("/").text
    page = c.get(f"/listings/{tid}").text
    assert "测试有限公司" not in page and "交割时现金支付" in page
    r = c.post(f"{url}/match")
    assert "示例·苏南智能装备" in r.text


def test_teaser_and_closing_only_through_their_own_steps(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    jade = _get(db_url, Target, code_name="Project Jade")
    with db.session_scope(db_url) as s:
        t = s.get(Target, jade.id)
        shortlisted = next(m.id for m in t.matches if m.stage == "shortlisted")
        nda = next(m.id for m in t.matches if m.stage == "nda_signed")
    r = c.post(f"{I}/matches/{shortlisted}/move", data={"to_stage": "teaser_sent"})
    assert "seller approves" in r.text
    assert _get(db_url, Match, id=shortlisted).stage == "shortlisted"
    for stage in ("im_sent", "loi", "closing"):
        c.post(f"{I}/matches/{nda}/move", data={"to_stage": stage})
    r = c.post(f"{I}/matches/{nda}/move", data={"to_stage": "closed"})
    assert "Record the closing value" in r.text
    r = c.post(f"{I}/matches/{nda}/close", data={"deal_value": "88", "invoice_ref": "INV-C"})
    assert "Success fee RMB" in r.text


def test_seller_page_has_no_plan_demand_or_buyer_names(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    jade = _get(db_url, Target, code_name="Project Jade")
    page = c.get(f"/s/{jade.seller_token}").text
    assert not [n for n in _buyer_names(db_url) if n in page]
    for word in ("方案", "需求", "成功费", "平台分成", "RMB 20000"):
        assert word not in page, word
    assert not re.search(r"\b(plan|demand)\b", page, re.I)
    assert not re.search(r"RMB [\d.]+–[\d.]*m", page)  # a buyer's own size range could fingerprint it
    assert "批准并发送" in page and "期望价格" in page
    assert c.get("/s/not-a-token").status_code == 404


def test_seller_approves_a_buyer(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    jade = _get(db_url, Target, code_name="Project Jade")
    page = c.get(f"/s/{jade.seller_token}").text
    match_id = re.search(rf"/s/{jade.seller_token}/matches/(\d+)/approve", page).group(1)
    r = c.post(f"/s/{jade.seller_token}/matches/{match_id}/approve")
    assert "Teaser sent" in r.text
    assert _get(db_url, Match, id=int(match_id)).stage == "teaser_sent"


def test_seller_submits_data_and_adviser_checks_it(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    delta = _get(db_url, Target, code_name="Project Delta")
    y = datacheck.years()[-1]
    r = c.post(f"/s/{delta.seller_token}/data", data={f"fin_{y}_revenue": "85", f"fin_{y}_net_profit": "9",
                                                       "d_permits_personal": "yes", "d_land": "leased"})
    assert "Data saved" in r.text
    t = _get(db_url, Target, code_name="Project Delta")
    assert t.financials[y]["revenue"] == 85 and t.disclosures["permits_personal"] is True
    r = c.post(f"{I}/targets/{t.id}/datacheck")
    assert "preparation pack" in r.text
    c.post(f"{I}/targets/{t.id}/prep-pack", data={"invoice_ref": "INV-7"})
    r = c.post(f"{I}/targets/{t.id}/datacheck")
    assert "实控人个人名下" in r.text
    assert "实控人个人名下" in c.get(f"/s/{delta.seller_token}").text  # the seller sees the questions
