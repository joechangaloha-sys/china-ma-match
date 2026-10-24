from fastapi.testclient import TestClient

from mamatch import config, db
from mamatch.seed import seed


def _client(db_url, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", db_url)
    with db.session_scope(db_url) as s:
        seed(s)
    from mamatch.web.app import app

    return TestClient(app)


def test_end_to_end_flow(db_url, monkeypatch):
    c = _client(db_url, monkeypatch)
    assert "Project Jade" in c.get("/").text
    assert "示例·华东精密科技" in c.get("/buyers?sector=auto_parts").text

    r = c.post("/targets", data={"code_name": "Project Test", "legal_name": "测试有限公司", "province": "浙江",
                                 "sector": "machinery", "revenue": "80", "asking_value": "60"})
    assert r.status_code == 200 and "Project Test" in r.text
    target_url = str(r.url.path)

    r = c.post(f"{target_url}/teaser", data={"language": "zh"})
    assert "识别风险" in r.text and "测试有限公司" in r.text  # legal name shown only in the internal panel

    r = c.post(f"{target_url}/match")
    assert "示例·苏南智能装备" in r.text

    page = c.get("/pipeline")
    assert page.status_code == 200
