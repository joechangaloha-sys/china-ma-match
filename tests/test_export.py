import posixpath
import re

from mamatch import config
from mamatch.export import export


def test_static_export_is_complete_and_self_contained(tmp_path, monkeypatch):
    for name in ("DATABASE_URL", "UPLOAD_DIR", "LLM_MODE", "DEMO_GUIDE"):
        monkeypatch.setattr(config, name, getattr(config, name))  # export() changes these; restore afterwards
    out = tmp_path / "site"
    files = export(out)
    for page in ("zh/index.html", "en/opportunities/index.html", "en/demo/index.html", "zh/seller/1/index.html",
                 "en/buyer/index.html", "en/adviser/index.html", "zh/internal/index.html", "en/faq/index.html"):
        assert page in files, page
    assert (out / "index.html").exists() and (out / ".nojekyll").exists() and (out / "static" / "static-demo.js").exists()
    for f in out.rglob("*.html"):
        rel = f.relative_to(out).as_posix()
        html = f.read_text()
        assert "fonts.googleapis" not in html  # blocked in mainland China
        for link in re.findall(r'(?:href|src)="([^"#?][^"]*)"', html):
            if link.startswith("http"):
                continue
            assert not link.startswith("/"), (rel, link)
            target = posixpath.normpath(posixpath.join(posixpath.dirname(rel), link.split("#")[0].split("?")[0]))
            assert (out / target).exists(), (rel, link)
        if rel != "index.html":
            assert "Static demo" in html or "静态演示" in html
    listing = (out / "en/opportunities/index.html").read_text()
    assert 'data-rev-lo="20"' in listing and "48" not in re.findall(r'data-[a-z-]+="([^"]*)"', listing)  # bands only
