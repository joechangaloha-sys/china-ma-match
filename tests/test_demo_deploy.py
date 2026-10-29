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
