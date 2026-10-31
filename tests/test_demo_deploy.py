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
        assert home.count('href="/teaser-demo/"') >= 2  # menu and prominent homepage action
        assert c.get(f'/{lang}/teaser-demo/').status_code == 200
    monkeypatch.setattr(config, 'DEMO_MODE', False)
    for path in protected:
        assert c.get(path).status_code == 404
    assert 'href="/teaser-demo/"' not in c.get('/en/').text


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
