import time

import pytest
from fastapi.testclient import TestClient

from mamatch import config
from mamatch.seed import seed
from mamatch.web.demo import safe_next, valid_cookie


PASSCODE = "demo-test-passcode"


@pytest.fixture
def demo_app(db_url, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATABASE_URL", db_url)
    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_ACCESS_KEY", PASSCODE)
    monkeypatch.setattr(config, "DEMO_ACCESS_HOURS", 12)
    monkeypatch.setattr(config, "SEED_DEMO", False)
    monkeypatch.setattr(config, "SECURE_COOKIES", False)
    from mamatch import db

    with db.session_scope(db_url) as s:
        seed(s)
    from mamatch.web.app import app

    return app


def test_health_and_static_are_available_but_noindexed(demo_app):
    c = TestClient(demo_app)
    assert c.get("/health/live").json() == {"status": "ok"}
    assert c.get("/health/ready").json() == {"status": "ready"}
    css = c.get("/static/style.css")
    assert css.status_code == 200
    assert css.headers["x-robots-tag"] == "noindex, nofollow, noarchive"


def test_demo_gate_wrong_and_correct_passcode(demo_app):
    c = TestClient(demo_app, follow_redirects=False)
    gated = c.get("/opportunities?sector=machinery")
    assert gated.status_code == 303
    assert gated.headers["location"] == "/demo-access?next=%2Fopportunities%3Fsector%3Dmachinery"
    wrong = c.post("/demo-access", data={"access_key": "wrong", "next": "/opportunities"})
    assert wrong.status_code == 200 and "Incorrect demo passcode" in wrong.text
    assert "mm_demo_access" not in wrong.cookies
    entered = c.post("/demo-access", data={"access_key": PASSCODE, "next": "/opportunities"})
    assert entered.status_code == 303 and entered.headers["location"] == "/opportunities"
    assert entered.headers["cache-control"] == "no-store"
    page = c.get("/opportunities")
    assert page.status_code == 200 and "Project Delta" in page.text
    assert "all data is fictional" in page.text
    assert page.headers["x-robots-tag"] == "noindex, nofollow, noarchive"


def test_demo_gate_preserves_language_and_blocks_open_redirect(demo_app):
    c = TestClient(demo_app, follow_redirects=False)
    gated = c.get("/zh/opportunities")
    assert gated.headers["location"].startswith("/zh/demo-access?next=")
    entered = c.post("/zh/demo-access", data={"access_key": PASSCODE, "next": "//evil.example"})
    assert entered.status_code == 303 and entered.headers["location"] == "/zh/"


def test_demo_cookie_signature_and_expiry(demo_app, monkeypatch):
    assert not valid_cookie("not-a-cookie")
    expired = str(int(time.time()) - 10)
    from mamatch.web.demo import _signature

    assert not valid_cookie(f"{expired}.{_signature(expired)}")
    assert safe_next("/zh/opportunities") == "/zh/opportunities"
    assert safe_next("https://evil.example") == "/"
    assert safe_next("//evil.example") == "/"


def test_demo_seed_cannot_be_enabled_for_normal_mode(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(config, "SEED_DEMO", True)
    with pytest.raises(RuntimeError, match="requires MAMATCH_DEMO_MODE"):
        config.validate_runtime()


def test_demo_mode_requires_a_real_passcode(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_ACCESS_KEY", "short")
    with pytest.raises(RuntimeError, match="at least 12"):
        config.validate_runtime()


def test_standalone_kimi_teaser_and_assets_share_the_demo_gate(demo_app, monkeypatch):
    c = TestClient(demo_app, follow_redirects=False)
    protected = ['/teaser-demo/', '/teaser-demo/assets/app.js', '/teaser-demo/assets/styles.css',
                 '/teaser-demo/assets/favicon.svg', '/teaser-demo/data/teaser.json']
    for path in protected:
        assert c.get(path).status_code == 303
    c.post('/demo-access', data={'access_key': PASSCODE})
    page = c.get('/teaser-demo/')
    assert page.status_code == 200
    assert 'Project Willow' in page.text
    assert 'Kimi’s original standalone teaser' in page.text
    assert 'id="teaser-content"' in page.text and 'id="print-button"' in page.text
    assert 'Fictional preview' in page.text and 'Ready for demo' not in page.text
    for path in protected:
        r = c.get(path)
        assert r.status_code == 200, path
        assert r.headers['x-robots-tag'] == 'noindex, nofollow, noarchive'
    assert c.get('/teaser-demo/data/teaser.json').json()['project_code'] == 'Project Willow'
    assert c.get('/teaser-demo/unknown.txt').status_code == 404
    assert c.get('/teaser-demo/assets/%2e%2e/%2e%2e/config.py').status_code == 404
    for lang in ('zh', 'en'):
        home = c.get(f'/{lang}/').text
        assert home.count(f'href="/{lang}/teaser-demo/"') >= 2  # menu and prominent homepage action
        assert c.get(f'/{lang}/teaser-demo/').status_code == 200
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    for path in protected:
        assert c.get(path).status_code == 404
    assert 'href="/en/teaser-demo/"' not in c.get('/en/').text


def test_document_demos_are_gated_bilingual_and_do_not_create_deals(demo_app, monkeypatch):
    from mamatch.db import get_engine
    from sqlalchemy import text
    def counts():
        with get_engine().connect() as conn:
            return [conn.execute(text('SELECT count(*) FROM ' + table)).scalar()
                    for table in ('targets', 'matches', 'deal_handoffs', 'handoff_events')]
    before = counts()
    c = TestClient(demo_app, follow_redirects=False)
    assert c.get('/en/document-demos/info-memo').status_code == 303
    c.post('/demo-access', data={'access_key': PASSCODE})
    for lang in ('en', 'zh'):
        hub = c.get(f'/{lang}/document-demos')
        assert hub.status_code == 200
        for kind, states in {'info-memo': ('draft','review','buyer'), 'nda': ('draft','sent','complete'), 'loi': ('draft','review','revised')}.items():
            assert f'/{lang}/document-demos/{kind}' in hub.text
            for state in states:
                r = c.get(f'/{lang}/document-demos/{kind}?state={state}')
                assert r.status_code == 200
                assert 'noindex' in r.headers['x-robots-tag']
                assert 'document-preview' in r.text and 'document-download' in r.text
                assert ('UNSIGNED' if lang == 'en' else '未签署') in r.text
            assert c.post(f'/{lang}/document-demos/{kind}').status_code == 405
        assert c.get(f'/{lang}/document-demos/nda?state=wrong').status_code == 400
    assert counts() == before
    assert c.get('/document-demos/unknown').status_code == 404
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    for path in ('/document-demos', '/document-demos/nda', '/document-demos/loi', '/document-demos/info-memo'):
        assert c.get(path).status_code == 404


def test_public_and_document_editions_do_not_mix_language(demo_app):
    import re
    from html.parser import HTMLParser

    class VisibleText(HTMLParser):
        def __init__(self):
            super().__init__()
            self.skip = 0
            self.parts = []
        def handle_starttag(self, tag, attrs):
            if tag in ('script', 'style', 'code'):
                self.skip += 1
        def handle_endtag(self, tag):
            if tag in ('script', 'style', 'code'):
                self.skip -= 1
        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data)

    c = TestClient(demo_app)
    c.post('/demo-access', data={'access_key': PASSCODE})
    paths = ['/', '/sell', '/buy', '/fees', '/security', '/conduct', '/faq',
             '/opportunities', '/workflow', '/handoff', '/login', '/register', '/register/adviser', '/demo-access', '/document-demos']
    from mamatch.db import session_scope
    from mamatch.models import Target
    from sqlalchemy import select
    with session_scope() as session:
        listed = session.scalar(select(Target).where(Target.code_name == 'Project Kiln'))
        paths += [f'/opportunities/{listed.id}', f'/opportunities/{listed.id}/report']
    paths += [f'/document-demos/{kind}?state={state}' for kind, states in
              {'info-memo': ('draft','review','buyer'), 'nda': ('draft','sent','complete'),
               'loi': ('draft','review','revised')}.items() for state in states]
    for lang in ('en', 'zh'):
        for path in paths + ['/teaser-demo/']:
            r = c.get(f'/{lang}{path}')
            assert r.status_code == 200
            parser = VisibleText(); parser.feed(r.text)
            text = re.sub(r'https?://\S+', '', ' '.join(parser.parts))
            forbidden = r'[\u4e00-\u9fff]' if lang == 'en' else r'[A-Za-z]'
            assert not re.search(forbidden, text), (lang, path, re.findall(r'.{0,20}' + forbidden + r'.{0,20}', text))
    page = c.get('/zh/document-demos/loi').text
    for term in ('标的公司', '股权转让对价', '先决条件', '尽职调查', '法律约束力'):
        assert term in page
    assert '息税折旧及摊销前利润' in c.get('/zh/document-demos/info-memo').text
    assert c.get('/zh/teaser-demo/?state=preview').status_code == 200
    assert c.get('/zh/teaser-demo/?state=unknown').status_code == 400


def test_chinese_teaser_uses_the_same_shell_controls_and_styles_as_english(demo_app):
    from html.parser import HTMLParser
    class Structure(HTMLParser):
        def __init__(self): super().__init__(); self.items = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            self.items.append((tag, attrs.get('class'), attrs.get('id'), attrs.get('role')))
    c = TestClient(demo_app)
    c.post('/demo-access', data={'access_key': PASSCODE})
    pages = [c.get(f'/{lang}/teaser-demo/') for lang in ('en', 'zh')]
    structures = []
    for page in pages:
        assert page.status_code == 200
        parser = Structure(); parser.feed(page.text); structures.append(parser.items)
        assert 'assets/styles.css?v=navy-20261031' in page.text
        for control in ('render-button','checks-button','copy-button','download-button','print-button',
                        'tab-button-checks','tab-button-data','tab-button-rules'):
            assert f'id="{control}"' in page.text
    assert structures[0] == structures[1]
    assert 'href="/en/teaser-demo/"' in pages[1].text
    assert 'href="/zh/document-demos"' in pages[1].text
    data = [c.get(f'/{lang}/teaser-demo/data/teaser.json').json() for lang in ('en','zh')]
    for key in ('revenue_min','revenue_max','profit_min','profit_max','employee_count_min','site_count_max'):
        assert data[0][key] == data[1][key]
    assert data[1]['project_code'] == '柳树项目'


def test_document_editions_share_structure_styles_and_controls_in_every_stage(demo_app):
    from html.parser import HTMLParser
    class Structure(HTMLParser):
        def __init__(self): super().__init__(); self.items=[]
        def handle_starttag(self, tag, attrs):
            a=dict(attrs)
            # Only the language selector's current-edition marker should differ.
            if a.get('hreflang'):
                a.pop('class', None)
            self.items.append((tag,a.get('class'),a.get('id'),a.get('role')))
    c=TestClient(demo_app);c.post('/demo-access',data={'access_key':PASSCODE})
    for kind, states in {'info-memo':('draft','review','buyer'),'nda':('draft','sent','complete'),'loi':('draft','review','revised')}.items():
        for state in states:
            structures=[]
            for lang in ('en','zh'):
                page=c.get(f'/{lang}/document-demos/{kind}?state={state}')
                assert page.status_code==200
                assert '/static/palette.css?v=navy-20261031' in page.text
                assert '/static/document-demos.css?v=layout-parity-20261031' in page.text
                assert 'id="document-download"' in page.text and 'id="document-print"' in page.text
                parser=Structure();parser.feed(page.text);structures.append(parser.items)
            assert structures[0]==structures[1],(kind,state)
    css=c.get('/static/document-demos.css')
    assert css.status_code==200 and '@media print' in css.text and 'var(--navy)' in css.text


def test_main_public_editions_share_layout_and_institutional_styles(demo_app):
    from html.parser import HTMLParser
    class Structure(HTMLParser):
        def __init__(self): super().__init__(); self.items=[]
        def handle_starttag(self,tag,attrs):
            a=dict(attrs)
            if a.get('hreflang'): a.pop('class',None)
            self.items.append((tag,a.get('class'),a.get('id'),a.get('role')))
    c=TestClient(demo_app);c.post('/demo-access',data={'access_key':PASSCODE})
    paths=['/','/opportunities','/sell','/buy','/fees','/security','/faq','/conduct',
           '/login','/register','/register/adviser','/document-demos']
    for path in paths:
        structures=[]
        for lang in ('en','zh'):
            r=c.get(f'/{lang}{path}');assert r.status_code==200
            assert '/static/palette.css?v=navy-20261031' in r.text
            parser=Structure();parser.feed(r.text);structures.append(parser.items)
        assert structures[0]==structures[1],path
    zh=c.get('/zh/').text
    assert '中小企业股权转让与并购服务' in zh and '项目负责人' in zh
    assert '当前演示未启用人工智能模型调用' in zh
    palette=c.get('/static/palette.css').text
    assert '--house-navy: #0b2545' in palette and '--house-paper: #ffffff' in palette


def test_scanner_setup_enables_only_needed_version_command():
    from pathlib import Path
    script = (Path(__file__).parents[1] / 'deploy/lighthouse/setup-scanner-mfa.sh').read_text()
    assert "'EnableVersionCommand':'true'" in script
    assert "'EnableShutdownCommand':'false'" in script
    assert "'EnableReloadCommand':'false'" in script
    assert "'LocalSocketMode':'660'" in script
    assert "Environment=TZ=UTC" in script
