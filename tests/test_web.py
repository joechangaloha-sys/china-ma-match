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


def client(app, email: str | None = None, lang: str = "zh-CN") -> TestClient:
    c = TestClient(app, headers={"Accept-Language": lang})
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
    assert "邮箱或密码不正确" in r.text
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
    assert "个数字待审核" in r.text and "营业收入,10400" in r.text
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
    assert "仅支持" in r.text


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
    assert "尚未通过审核" in client(app, PENDING).post(f"/opportunities/{kiln.id}/request").text


def test_buyer_request_then_analyst_approval_then_nda(app, db_url):
    delta = _get(db_url, Target, code_name="Project Delta")
    buyer = client(app, BUYER)
    assert "已提交引荐申请" in buyer.post(f"/opportunities/{delta.id}/request").text
    m = _get(db_url, Match, target_id=delta.id, buyer_id=_get(db_url, Buyer, external_id="EX000").id)
    assert "接受并签署" not in buyer.get("/buyer").text
    client(app, DM).post(f"{I}/matches/{m.id}/decision", data={"decision": "accept"})
    assert "接受并签署" in buyer.get("/buyer").text
    assert "Accept and sign" in buyer.get("/en/buyer").text
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
    # The seller opens their account from the invite link, states their authority and approves the teaser.
    token = re.search(r"/invite/([\w-]+)", dm.get(url).text).group(1)
    seller = client(app)
    seller.post(f"/invite/{token}", data={"name": "测", "email": "s.test@example.test", "password": "long-enough-pw",
                                          "owner_role": "legal_rep", "confirm_authority": "1"})
    assert seller.post(f"/seller/{tid}/teasers/{tz}/approve").status_code == 200
    r = seller.post(f"/seller/{tid}/visibility", data={"visibility": "listed"})
    assert "尚未核验" in r.text  # authority not verified yet
    assert "Upload the business licence" in dm.post(f"{url}/authority").text
    for kind in ("license", "ownership"):
        seller.post(f"/seller/{tid}/documents", data={"kind": kind}, files={"file": (f"{kind}.txt", b"x", "text/plain")})
    dm.post(f"{url}/authority", data={"note": "licence checked"})
    seller.post(f"/seller/{tid}/visibility", data={"visibility": "listed"})
    t = _get(db_url, Target, id=tid)
    assert t.visibility == "listed" and t.status == "in_market" and t.authority_verified_at
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


# ---------------------------------------------------------------- languages (same rules as the Japan IR Index)

@pytest.mark.parametrize("accept, expected", [("zh-CN,zh;q=0.9,en;q=0.8", "/zh/"), ("en-GB,en;q=0.9", "/en/"),
                                              ("ja-JP,ja;q=0.9", "/en/"), ("de-DE,en;q=0.5,zh;q=0.8", "/zh/"), ("", "/en/")])
def test_neutral_homepage_follows_the_browser(app, accept, expected):
    r = client(app, lang=accept).get("/?ref=x", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == expected + "?ref=x"


def test_remembered_switch_wins_and_editions_never_redirect(app):
    c = client(app, lang="en-US")
    c.cookies.set("mm_lang", "zh")
    assert c.get("/", follow_redirects=False).headers["location"] == "/zh/"
    r = c.get("/en/opportunities", follow_redirects=False)
    assert r.status_code == 200 and '<html lang="en">' in r.text  # a direct edition link is never redirected


def test_english_edition_has_no_chinese_interface_text(app, db_url):
    import re as _re

    c = client(app, lang="zh-CN")
    data_names = _buyer_names(db_url)
    with db.session_scope(db_url) as s:
        data_names += [t.code_name for t in s.scalars(select(Target))] + ["示例·长三角并购顾问事务所"]
    for url in ("/en/", "/en/opportunities", "/en/sell", "/en/buy", "/en/fees", "/en/security", "/en/login", "/en/register"):
        text = _re.sub(r"<[^>]+>", " ", c.get(url).text)
        for name in data_names:
            text = text.replace(name, "")
        text = text.replace("中文", "")  # the language switch names itself
        assert not _re.search(r"[\u4e00-\u9fff]", text), (url, _re.findall(r".{20}[\u4e00-\u9fff]+.{20}", text)[:3])


def test_links_and_redirects_stay_in_the_edition(app, db_url):
    c = client(app, lang="zh-CN")
    page = c.get("/en/opportunities").text
    assert 'href="/en/opportunities/' in page and 'href="/zh/opportunities"' in page  # cards, switch
    kiln = _get(db_url, Target, code_name="Project Kiln")
    r = c.post(f"/en/opportunities/{kiln.id}/inquiry", data={"name": "Li"}, follow_redirects=False)
    assert r.headers["location"].startswith(f"/en/opportunities/{kiln.id}")
    r = client(app, lang="zh-CN").get("/en/seller", follow_redirects=False)
    assert r.headers["location"].startswith("/en/login")


def test_portals_in_english(app):
    seller = client(app, SELLER, lang="en-US").get("/seller").text
    for words in ("Where your sale stands", "Document checklist", "Your listing card", "Questions buyers will ask"):
        assert words in seller
    assert "资料清单" not in seller and "补充问卷" not in seller
    buyer = client(app, BUYER, lang="en-US").get("/buyer").text
    assert "Acquisition thesis" in buyer and "收购方向" not in buyer


def test_detailed_search_page(app):
    c = client(app, lang="en-US")
    page = c.get("/en/opportunities?q=coatings&revenue_min=20&profitable=yes&reasons=strategic").text
    assert "Detailed search" in page and "Project Kiln" in page and "Project Delta" not in page
    assert "1 of 2 listings" in page and "Net margin" in page and "Industrial anti-corrosion coatings" in page
    zh = client(app).get("/zh/opportunities?margin_min=10").text
    assert "详细搜索" in zh and "工业防腐涂料" in zh


def test_faq_and_why_section_in_both_languages(app):
    en = client(app, lang="en-US")
    home = en.get("/en/").text
    assert "Why we built this" in home and "Joe Chang" not in home
    assert "Hand your company on to the right owner" in home
    assert "把企业交棒给对的人" in client(app).get("/zh/").text
    assert "bulge-bracket investment banks, major law firms and Big Four accounting firms" in home
    faq = en.get("/en/faq").text
    assert "Frequently asked questions" in faq and "How do fees work for advisers?" in faq and "25%" in faq and "unaffected" not in home
    zh = client(app).get("/zh/faq").text
    assert "常见问题" in zh and "顾问的收费如何安排" in zh
    assert "How do you verify authority?" in faq and "Can an adviser make decisions for the client?" in faq


def test_adviser_can_submit_for_a_client(app, db_url):
    c = client(app)
    r = c.post("/sell", data={"company": "示例·客户公司", "name": "王会计", "contact": "138", "consent": "1",
                              "submitted_by": "adviser"})
    assert "请填写您的机构名称" in r.text
    c.post("/sell", data={"company": "示例·客户公司", "name": "王会计", "contact": "138", "consent": "1",
                          "submitted_by": "adviser", "adviser_firm": "示例·某会计师事务所"})
    t = _get(db_url, Target, legal_name="示例·客户公司")
    assert t.submitted_by == "adviser" and t.adviser_firm == "示例·某会计师事务所"
    assert "示例·某会计师事务所" in client(app, DM).get(I).text



ADVISER = "adviser@demo.mamatch.test"


def test_adviser_journey_with_client_authorisation(app, db_url):
    # 1. A new adviser registers and must be verified before acting for anyone.
    adv = client(app)
    adv.post("/register/adviser", data={"email": "cpa@example.test", "password": "long-enough-pw", "name": "周",
                                        "firm": "示例·某会计师事务所", "profession": "accountant", "license_no": "CPA-123",
                                        "consent": "1"})
    data = {"company": "示例·客户企业有限公司", "owner_name": "示例·赵总", "owner_contact": "139", "sector": "food",
            "province": "浙江", "revenue": "30", "confirm": "1"}
    adv.post("/adviser/mandates", data=data)
    assert _get(db_url, Target, legal_name="示例·客户企业有限公司") is None
    from mamatch.models import Adviser
    a = _get(db_url, Adviser, firm="示例·某会计师事务所")
    dm = client(app, DM)
    assert "示例·某会计师事务所" in dm.get(f"{I}/advisers").text
    dm.post(f"{I}/advisers/{a.id}/verify")
    # 2. The verified adviser opens the mandate and gets the owner's authorisation link.
    r = adv.post("/adviser/mandates", data=data)
    t = _get(db_url, Target, legal_name="示例·客户企业有限公司")
    assert t.submitted_by == "adviser" and "/invite/" in r.text
    token = re.search(r"/invite/([\w-]+)", r.text).group(1)
    # 3. The owner opens their account, states their role and signs the adviser's authorisation.
    invite = client(app).get(f"/invite/{token}").text
    assert "示例·某会计师事务所" in invite and "授权" in invite
    owner = client(app)
    r = owner.post(f"/invite/{token}", data={"name": "赵", "email": "owner@example.test", "password": "long-enough-pw",
                                             "owner_role": "shareholder", "share_pct": "80", "confirm_authority": "1"})
    assert "请确认对顾问的授权" in r.text  # the authorisation must be accepted explicitly
    owner.post(f"/invite/{token}", data={"name": "赵", "email": "owner@example.test", "password": "long-enough-pw",
                                         "owner_role": "shareholder", "share_pct": "80", "confirm_authority": "1",
                                         "accept": "1"})
    def auth_state(tid):
        with db.session_scope(db_url) as s:
            tt = s.get(Target, tid)
            return tt.owner_role, tt.owner_share_pct, tt.authority_verified_at, [(a.id, a.status) for a in tt.authorizations]

    role, share, _, auths = auth_state(t.id)
    assert role == "shareholder" and share == 80 and auths[0][1] == "owner_confirmed"
    # 4. The adviser uploads the documents; the deal manager verifies authority, which activates the authorisation.
    for kind in ("license", "ownership"):
        r = adv.post(f"/adviser/{t.id}/documents", data={"kind": kind}, files={"file": (f"{kind}.txt", b"x", "text/plain")})
        assert "已上传" in r.text
    dm.post(f"{I}/targets/{t.id}/authority", data={"note": "执照与股东名册一致"})
    _, _, verified_at, auths = auth_state(t.id)
    assert verified_at and auths[0][1] == "verified"
    # 5. The adviser cannot make the owner's decisions, and loses access when the owner revokes.
    assert adv.post(f"/seller/{t.id}/visibility", data={"visibility": "listed"}).status_code == 403
    owner.post(f"/seller/{t.id}/authorizations/{auths[0][0]}/revoke")
    assert adv.get(f"/adviser/{t.id}").status_code == 404
    with db.session_scope(db_url) as s:
        actions = {e.action for e in s.scalars(select(AuditEvent).where(AuditEvent.target_id == t.id))}
    assert {"authorization_requested", "authorization_confirmed", "authority_verified", "authorization_revoked"} <= actions


def test_adviser_sees_only_authorised_mandates(app, db_url):
    adv = client(app, ADVISER)
    delta = _get(db_url, Target, code_name="Project Delta")  # authorised in the seed
    jade = _get(db_url, Target, code_name="Project Jade")
    assert adv.get(f"/adviser/{delta.id}").status_code == 200
    assert adv.get(f"/adviser/{jade.id}").status_code == 404
    assert client(app, ADVISER).get(I).status_code == 403


# ---------------------------------------------------------------- offers, bulk send, sharing

def test_seller_compares_offers_without_seeing_buyer_names(app, db_url):
    jade = _get(db_url, Target, code_name="Project Jade")
    page = client(app, SELLER, lang="en-US").get(f"/en/seller/{jade.id}").text
    assert "Offers side by side" in page and "85–95" in page and "70–80" in page
    assert page.index("85–95") < page.index("70–80")  # highest implied value first
    assert not [n for n in _buyer_names(db_url) if n in page]
    internal = client(app, DM).get(f"{I}/targets/{jade.id}").text
    assert "示例·华东精密科技" in internal and "85–95" in internal


def test_buyer_offer_needs_nda_and_own_deal(app, db_url):
    jade = _get(db_url, Target, code_name="Project Jade")
    buyer = client(app, BUYER)
    nda = next(mid for mid, st in _matches(db_url, jade.id) if st == "nda_signed"
               and _get(db_url, Match, id=mid).buyer_id == _get(db_url, Buyer, external_id="EX000").id)
    r = buyer.post(f"/buyer/deals/{nda}/offer", data={"price_low": "90", "price_high": "88"})
    assert "有效的价格区间" in r.text
    r = buyer.post(f"/buyer/deals/{nda}/offer", data={"price_low": "90", "price_high": "100", "stake_pct": "100",
                                                       "consideration": "cash", "financing": "own_funds"})
    assert "已提交意向报价" in r.text
    with db.session_scope(db_url) as s:
        m = s.get(Match, nda)
        assert m.offers[0].price_high == 100 and len(m.offers) == 2  # revised; the latest counts
    assert client(app, PENDING).post(f"/buyer/deals/{nda}/offer", data={"price_low": "1", "price_high": "2"}).status_code == 404
    delta = _get(db_url, Target, code_name="Project Delta")
    m2 = client(app, BUYER).post(f"/opportunities/{delta.id}/request")
    mid = _get(db_url, Match, target_id=delta.id, buyer_id=_get(db_url, Buyer, external_id="EX000").id).id
    assert "签署保密协议后" in buyer.post(f"/buyer/deals/{mid}/offer", data={"price_low": "1", "price_high": "2"}).text


def test_seller_sends_to_ticked_buyers_in_one_step(app, db_url):
    jade = _get(db_url, Target, code_name="Project Jade")
    seller = client(app, SELLER)
    page = seller.get(f"/seller/{jade.id}").text
    ids = re.findall(r'name="match_ids" value="(\d+)"', page)
    assert len(ids) >= 2
    r = seller.post(f"/seller/{jade.id}/send", data={"match_ids": ids[:1]})  # the other one is left out
    assert "已发送给 1 位买方" in r.text
    stages = dict(_matches(db_url, jade.id))
    assert stages[int(ids[0])] == "teaser_sent" and stages[int(ids[1])] == "shortlisted"
    assert "请至少勾选" in seller.post(f"/seller/{jade.id}/send", data={}).text


def test_listing_share_panel(app, db_url):
    kiln = _get(db_url, Target, code_name="Project Kiln")
    page = client(app).get(f"/zh/opportunities/{kiln.id}").text
    assert "分享此项目" in page and "<svg" in page and "复制链接" in page
    assert re.search(r"<title>Project Kiln · mamatch</title>", page)  # nothing leaked into the title
    assert f"/zh/opportunities/{kiln.id}/" in page and "把企业交棒给对的人" in page
    for secret in (kiln.legal_name, kiln.short_name, kiln.owner_name, "无锡"):
        assert secret not in page
    en = client(app).get(f"/en/opportunities/{kiln.id}").text
    assert "Share this listing" in en and "For sale: Project Kiln" in en



def test_wrong_language_text_stays_off_portal_pages(app, db_url):
    data = _buyer_names(db_url) + ["示例·华东精密 并购部", "示例·王先生", "示例·长三角并购顾问事务所", "示例·李会计师",
                                   "示例·长三角会计师事务所"]  # example names are data, not interface text
    for email, url in ((SELLER, "/seller/1"), (BUYER, "/buyer")):
        en = client(app, email, lang="en-US").get(f"/en{url}").text
        en = re.sub(r"<(script|style|textarea)[^>]*>.*?</\1>", " ", en, flags=re.S)
        en = re.sub(r"<[^>]+>", " ", en)
        for name in sorted(data, key=len, reverse=True):
            en = en.replace(name, "")
        assert not re.search(r"[\u4e00-\u9fff]{2,}", en.replace("中文", "")), re.findall(r".{15}[\u4e00-\u9fff]{2,}.{15}", en)[:3]
        zh = client(app, email).get(f"/zh{url}").text
        for english in ("Full sale", "successor", "Stated interest", "Deal size fits", "rules"):
            assert english not in re.sub(r"<(script|textarea)[^>]*>.*?</\1>", " ", zh, flags=re.S), english
