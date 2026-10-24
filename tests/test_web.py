import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from mamatch import config, datacheck, db
from mamatch.models import AuditEvent, Buyer, Document, Match, Target
from mamatch.seed import DEMO_PASSWORD, seed

I = "/internal"
DM, SELLER, BUYER, PENDING = ("dm@demo.mamatch.test", "seller.jade@demo.mamatch.test",
                              "buyer.huadong@demo.mamatch.test", "buyer.pending@demo.mamatch.test")


@pytest.fixture
def app(db_url, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATABASE_URL", db_url)
    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    with db.session_scope(db_url) as s:
        seed(s)
    from mamatch.web.app import app

    return app


def client(app, email: str | None = None) -> TestClient:
    c = TestClient(app)
    if email:
        r = c.post("/login", data={"email": email, "password": DEMO_PASSWORD})
        assert r.status_code == 200, r.text
    return c


def _get(db_url, model, **where):
    with db.session_scope(db_url) as s:
        return s.scalar(select(model).filter_by(**where))


def _matches(db_url, target_id):
    with db.session_scope(db_url) as s:
        return [(m.id, m.stage) for m in s.get(Target, target_id).matches]


def _buyer_names(db_url):
    with db.session_scope(db_url) as s:
        return [b.name for b in s.scalars(select(Buyer))]


# ---------------------------------------------------------------- public site

def test_public_pages_render(app):
    c = client(app)
    for url in ("/", "/opportunities", "/sell", "/buy", "/fees", "/security", "/login", "/register"):
        assert c.get(url).status_code == 200, url
    assert c.get("/no-such-page").status_code == 404


def test_public_site_shows_anonymised_sellers_only(app, db_url):
    c = client(app)
    page = c.get("/opportunities").text
    assert "Project Kiln" in page and "Project Delta" in page and "Project Jade" not in page
    assert "期望价格" in page and "出让股权" in page
    assert not [n for n in _buyer_names(db_url) if n in page]
    kiln = _get(db_url, Target, code_name="Project Kiln")
    detail = c.get(f"/opportunities/{kiln.id}").text
    for secret in (kiln.legal_name, kiln.short_name, kiln.owner_name, "无锡", "江苏"):
        assert secret not in detail
    jade = _get(db_url, Target, code_name="Project Jade")
    assert c.get(f"/opportunities/{jade.id}").status_code == 404


def test_seller_intake_creates_a_draft_mandate(app, db_url):
    c = client(app)
    r = c.post("/sell", data={"company": "示例·某贸易公司", "name": "李", "contact": "139", "sector": "b2b_distribution",
                              "province": "浙江", "revenue": "30", "consent": "1"})
    assert "已收到" in r.text
    t = _get(db_url, Target, legal_name="示例·某贸易公司")
    assert t.status == "draft" and t.code_name.startswith("Project ")
    assert "示例·某贸易公司" not in c.get("/opportunities").text


def test_anonymous_inquiry_reaches_the_deal_manager(app, db_url):
    c = client(app)
    kiln = _get(db_url, Target, code_name="Project Kiln")
    r = c.post(f"/opportunities/{kiln.id}/inquiry", data={"name": "张伟", "company": "示例·某涂料集团",
                                                          "contact": "zw@example.cn", "message": "寻找华东涂料企业"})
    assert "请同意" in r.text
    c.post(f"/opportunities/{kiln.id}/inquiry", data={"name": "张伟", "company": "示例·某涂料集团", "contact": "zw@example.cn",
                                                      "message": "寻找华东涂料企业", "consent": "1"})
    page = client(app, DM).get(I).text
    assert "示例·某涂料集团" in page and "寻找华东涂料企业" in page


# ---------------------------------------------------------------- access control

@pytest.mark.parametrize("url", ["/seller", "/buyer", I, f"{I}/pipeline", f"{I}/audit"])
def test_anonymous_users_are_sent_to_sign_in(app, url):
    r = client(app).get(url, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")


def test_roles_cannot_cross(app):
    assert client(app, SELLER).get(I).status_code == 403
    assert client(app, BUYER).get(I).status_code == 403
    assert client(app, BUYER).get("/seller").status_code == 403
    assert client(app, SELLER).get("/buyer").status_code == 403


def test_seller_cannot_open_another_mandate(app, db_url):
    kiln = _get(db_url, Target, code_name="Project Kiln")
    assert client(app, SELLER).get(f"/seller/{kiln.id}").status_code == 404


def test_wrong_password_is_refused_and_logged(app, db_url):
    r = client(app).post("/login", data={"email": DM, "password": "wrong-password"})
    assert "Wrong email or password" in r.text
    assert _get(db_url, AuditEvent, action="sign_in_failed") is not None


def test_internal_pages_are_marked_internal(app, db_url):
    c = client(app, DM)
    jade = _get(db_url, Target, code_name="Project Jade")
    for url in (I, f"{I}/pipeline", f"{I}/buyers", f"{I}/dashboard", f"{I}/audit", f"{I}/targets/new",
                f"{I}/targets/{jade.id}"):
        r = c.get(url)
        assert r.status_code == 200, url
        assert "Internal page for deal managers only" in r.text, url


# ---------------------------------------------------------------- seller portal

def test_seller_portal_hides_plans_demand_and_buyer_names(app, db_url):
    page = client(app, SELLER).get("/seller").text
    assert "Project Jade" in page and "期望价格" in page
    assert not [n for n in _buyer_names(db_url) if n in page]
    for word in ("方案", "需求统计", "成功费", "平台分成"):
        assert word not in page, word
    assert not re.search(r"\b(plan|demand)\b", page, re.I)
    assert not re.search(r"RMB [\d.]+–[\d.]*m", page)  # a buyer's own size range could fingerprint it


def test_seller_approves_a_buyer(app, db_url):
    jade = _get(db_url, Target, code_name="Project Jade")
    seller = client(app, SELLER)
    page = seller.get(f"/seller/{jade.id}").text
    match_id = int(re.search(rf"/seller/{jade.id}/matches/(\d+)/approve", page).group(1))
    assert "已发送简介" in seller.post(f"/seller/{jade.id}/matches/{match_id}/approve").text
    assert _get(db_url, Match, id=match_id).stage == "teaser_sent"


def test_seller_uploads_and_deal_manager_extracts(app, db_url):
    jade = _get(db_url, Target, code_name="Project Jade")
    csv = "单位：万元\n项目,2023,2024,2025\n营业收入,10400,11800,12600\n净利润,890,1020,1150\n".encode()
    r = client(app, SELLER).post(f"/seller/{jade.id}/documents", data={"kind": "financials"},
                                 files={"file": ("fs.csv", csv, "text/csv")})
    assert "已上传" in r.text
    doc = _get(db_url, Document, filename="fs.csv")
    dm = client(app, DM)
    r = dm.post(f"{I}/documents/{doc.id}/extract")
    assert "figures to review" in r.text and "营业收入,10400" in r.text
    with db.session_scope(db_url) as s:
        f = next(f for f in s.get(Target, jade.id).fields if f.field == "revenue" and f.period == "2025")
        assert f.value == 126.0 and f.unit_in_source == "万元"
        fid = f.id
    dm.post(f"{I}/fields/{fid}/review", data={"decision": "confirm", "value": "125.5"})
    assert _get(db_url, Target, id=jade.id).financials["2025"]["revenue"] == 125.5


def test_upload_rejects_unsupported_files(app, db_url):
    jade = _get(db_url, Target, code_name="Project Jade")
    r = client(app, SELLER).post(f"/seller/{jade.id}/documents", data={"kind": "other"},
                                 files={"file": ("run.exe", b"MZ", "application/octet-stream")})
    assert "Unsupported file type" in r.text


def test_seller_saves_questionnaire(app, db_url):
    jade = _get(db_url, Target, code_name="Project Jade")
    y = datacheck.years()[-1]
    r = client(app, SELLER).post(f"/seller/{jade.id}/data", data={f"fin_{y}_revenue": "127", "d_land": "leased"})
    assert "已保存" in r.text
    assert _get(db_url, Target, id=jade.id).disclosures["land"] == "leased"


# ---------------------------------------------------------------- buyer portal, NDA, data room

def test_buyer_registers_and_structures_a_thesis(app, db_url):
    c = client(app)
    r = c.post("/register", data={"email": "new.buyer@example.test", "password": "long-enough-pw", "name": "赵",
                                  "organization": "示例·新买方", "kind": "private", "consent": "1"})
    assert "收购方向" in r.text
    r = c.post("/buyer/thesis/suggest", data={"thesis_text": "收购浙江、江苏的精密加工企业，交易金额1000-3000万，不考虑食品。"})
    assert 'value="metal_fab" checked' in r.text and 'value="浙江" checked' in r.text
    r = c.post("/buyer/thesis", data={"name": "示例·新买方", "kind": "private", "uscc": "91320500MA00007777",
                                      "target_sectors": ["metal_fab"], "target_regions": ["浙江"], "deal_size_min": "10",
                                      "deal_size_max": "30", "funding_max": "30", "funding_evidence": "bank_letter",
                                      "consent": "1"})
    assert "已保存" in r.text
    b = _get(db_url, Buyer, name="示例·新买方")
    assert b.status == "registered" and b.funding_max == 30
    r = client(app, DM).post(f"{I}/buyers/{b.id}/verify")
    assert "已认证" in r.text and _get(db_url, Buyer, id=b.id).status == "verified"


def test_unverified_buyer_cannot_request_an_introduction(app, db_url):
    kiln = _get(db_url, Target, code_name="Project Kiln")
    assert "not verified" in client(app, PENDING).post(f"/opportunities/{kiln.id}/request").text


def test_buyer_request_then_analyst_approval_then_nda(app, db_url):
    delta = _get(db_url, Target, code_name="Project Delta")
    buyer = client(app, BUYER)
    assert "Request sent" in buyer.post(f"/opportunities/{delta.id}/request").text
    m = _get(db_url, Match, target_id=delta.id, buyer_id=_get(db_url, Buyer, external_id="EX000").id)
    assert "Accept and sign" not in buyer.get("/buyer").text
    client(app, DM).post(f"{I}/matches/{m.id}/decision", data={"decision": "accept"})
    assert "Accept and sign" in buyer.get("/buyer").text
    buyer.post(f"/buyer/deals/{m.id}/nda")
    m = _get(db_url, Match, id=m.id)
    assert m.stage == "nda_signed" and m.nda_version


def test_data_room_needs_nda_seller_grant_and_flag(app, db_url):
    jade = _get(db_url, Target, code_name="Project Jade")
    dm = client(app, DM)
    dm.post(f"{I}/targets/{jade.id}/documents", data={"kind": "license"},
            files={"file": ("licence.txt", "营业执照".encode(), "text/plain")})
    doc = _get(db_url, Document, filename="licence.txt")
    buyer, other = client(app, BUYER), client(app, PENDING)
    assert buyer.get(f"/buyer/documents/{doc.id}").status_code == 404  # not in the data room yet
    dm.post(f"{I}/documents/{doc.id}/data-room")
    assert buyer.get(f"/buyer/documents/{doc.id}").status_code == 404  # seller has not granted access
    nda = next(mid for mid, st in _matches(db_url, jade.id) if st == "nda_signed")
    client(app, SELLER).post(f"/seller/{jade.id}/matches/{nda}/grant")
    r = buyer.get(f"/buyer/documents/{doc.id}")
    assert r.status_code == 200 and r.content == "营业执照".encode()
    assert other.get(f"/buyer/documents/{doc.id}").status_code == 404  # another buyer
    with db.session_scope(db_url) as s:
        actions = [e.action for e in s.scalars(select(AuditEvent).where(AuditEvent.document_id == doc.id))]
    assert "document_view" in actions and actions.count("document_denied") >= 3


def test_buyer_cannot_act_on_another_buyers_deal(app, db_url):
    jade = _get(db_url, Target, code_name="Project Jade")
    nda = next(mid for mid, st in _matches(db_url, jade.id) if st == "nda_signed")
    assert client(app, PENDING).post(f"/buyer/deals/{nda}/nda").status_code == 404


# ---------------------------------------------------------------- deal manager

def test_deal_manager_mandate_flow(app, db_url):
    dm = client(app, DM)
    r = dm.post(f"{I}/targets", data={"code_name": "Project Test", "legal_name": "测试有限公司", "province": "浙江",
                                      "sector": "machinery", "revenue": "30", "net_profit": "3", "asking_value": "12",
                                      "stake_pct": "60", "payment_terms": "cash"})
    assert r.status_code == 200 and "Project Test" in r.text and "/invite/" in r.text
    url = str(r.url.path)
    tid = int(url.rsplit("/", 1)[1])
    assert "10–20百万元" in r.text and "60–70%" in r.text
    r = dm.post(f"{url}/teaser", data={"language": "zh"})
    tz = int(re.search(rf"{I}/teasers/(\d+)/approve", r.text).group(1))
    dm.post(f"{I}/teasers/{tz}/approve")
    assert "seller must approve" in dm.post(f"{url}/visibility", data={"visibility": "listed"}).text
    # The seller opens their account from the invite link and approves the teaser.
    token = re.search(r"/invite/([\w-]+)", dm.get(url).text).group(1)
    seller = client(app)
    seller.post(f"/invite/{token}", data={"name": "测", "email": "s.test@example.test", "password": "long-enough-pw"})
    assert seller.post(f"/seller/{tid}/teasers/{tz}/approve").status_code == 200
    seller.post(f"/seller/{tid}/visibility", data={"visibility": "listed"})
    t = _get(db_url, Target, id=tid)
    assert t.visibility == "listed" and t.status == "in_market"
    assert "测试有限公司" not in client(app).get(f"/opportunities/{tid}").text
    assert client(app).get(f"/invite/{token}").status_code == 404  # one-time link


def test_operator_cannot_skip_seller_or_nda_steps(app, db_url):
    jade = _get(db_url, Target, code_name="Project Jade")
    dm = client(app, DM)
    ms = _matches(db_url, jade.id)
    shortlisted = next(mid for mid, st in ms if st == "shortlisted")
    assert "seller approves" in dm.post(f"{I}/matches/{shortlisted}/move", data={"to_stage": "teaser_sent"}).text
    assert "signs the NDA" in dm.post(f"{I}/matches/{shortlisted}/move", data={"to_stage": "nda_signed"}).text


def test_closing_records_the_success_fee(app, db_url):
    jade = _get(db_url, Target, code_name="Project Jade")
    dm = client(app, DM)
    nda = next(mid for mid, st in _matches(db_url, jade.id) if st == "nda_signed")
    for stage in ("im_sent", "loi", "closing"):
        dm.post(f"{I}/matches/{nda}/move", data={"to_stage": stage})
    assert "Record the closing value" in dm.post(f"{I}/matches/{nda}/move", data={"to_stage": "closed"}).text
    assert "Success fee RMB" in dm.post(f"{I}/matches/{nda}/close", data={"deal_value": "88"}).text
    assert _get(db_url, Target, id=jade.id).status == "closed"


def test_status_changes_are_audited(app, db_url):
    delta = _get(db_url, Target, code_name="Project Delta")
    dm = client(app, DM)
    dm.post(f"{I}/targets/{delta.id}/status", data={"to": "matching_paused", "note": "seller on holiday"})
    t = _get(db_url, Target, id=delta.id)
    assert t.status == "matching_paused" and t.visibility == "private"  # paused mandates leave the public site
    assert "seller on holiday" in dm.get(f"{I}/audit?target={delta.id}").text
