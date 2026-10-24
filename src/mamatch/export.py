"""Export the demo as a static website (for GitHub Pages or any file host).

Seeds a throwaway database with the fictional examples, renders every page in both editions and as
each demo role (visitor, seller, buyer, adviser, deal manager), rewrites links to relative paths, and
adds a banner, an in-browser search and form blocking. Nothing in the output can submit data.
"""

import os
import posixpath
import re
import shutil
import tempfile
from pathlib import Path

from . import config

LANGS = ("zh", "en")
_ATTR = re.compile(r'(href|src|action)="(/[^"]*)"')


def _key(url: str) -> str:
    return url.split("#")[0].split("?")[0].rstrip("/") or "/"


def _file_for(path: str) -> str:
    path = path.split("#")[0].split("?")[0].strip("/")
    return f"{path}/index.html" if path else "index.html"


def _relative(from_file: str, to_file: str) -> str:
    return posixpath.relpath(to_file, posixpath.dirname(from_file) or ".")


def export(out: Path) -> list[str]:
    tmp = Path(tempfile.mkdtemp())
    config.DATABASE_URL = f"sqlite:///{tmp / 'demo.db'}"
    config.UPLOAD_DIR = str(tmp / "uploads")
    config.LLM_MODE = "off"
    config.DEMO_GUIDE = True
    os.environ["MAMATCH_LLM"] = "off"

    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from . import db
    from .models import Adviser, MandateAuthorization, Target, User
    from .seed import DEMO_PASSWORD, seed
    from .web.app import app

    db.init_db()
    with db.session_scope() as s:
        seed(s)
        listed = [t.id for t in s.scalars(select(Target).where(Target.visibility == "listed"))]
        targets = [t.id for t in s.scalars(select(Target))]
        jade = s.scalar(select(Target.id).where(Target.code_name == "Project Jade"))
        adv_user = s.scalar(select(User).where(User.role == "adviser"))
        adv = s.scalar(select(Adviser).where(Adviser.user_id == adv_user.id))
        adv_targets = [a.target_id for a in s.scalars(select(MandateAuthorization).where(MandateAuthorization.adviser_id == adv.id))]

    def client(email=None, lang="zh"):
        c = TestClient(app, headers={"Accept-Language": lang})
        if email:
            c.post("/login", data={"email": email, "password": DEMO_PASSWORD})
        return c

    pages: dict[str, str] = {}  # url path -> html
    aliases: dict[str, str] = {}

    def grab(c, url):
        r = c.get(url, follow_redirects=False)
        if r.status_code in (302, 303, 307):
            loc = r.headers["location"]
            aliases[_key(url)] = _key(loc)
            r = c.get(loc, follow_redirects=False)
            url = loc
        if r.status_code == 200:
            pages[_key(url)] = r.text

    for L in LANGS:
        anon = client()
        for p in ["/", "/opportunities", "/sell", "/buy", "/fees", "/security", "/faq", "/demo", "/login", "/register",
                  "/register/adviser", *[f"/opportunities/{i}" for i in listed]]:
            grab(anon, f"/{L}{p}" if p != "/" else f"/{L}/")
        grab(client("seller.jade@demo.mamatch.test"), f"/{L}/seller")
        grab(client("buyer.huadong@demo.mamatch.test"), f"/{L}/buyer")
        a = client(adv_user.email)
        for p in ["/adviser", *[f"/adviser/{i}" for i in adv_targets]]:
            grab(a, f"/{L}{p}")
        dm = client("dm@demo.mamatch.test")
        for p in ["/internal", "/internal/buyers", "/internal/advisers", "/internal/pipeline", "/internal/dashboard",
                  "/internal/audit", "/internal/targets/new", *[f"/internal/targets/{i}" for i in targets]]:
            grab(dm, f"/{L}{p}")

    if out.exists():
        shutil.rmtree(out)
    (out / "static").mkdir(parents=True)
    static_src = Path(__file__).parent / "web" / "static"
    for f in static_src.iterdir():
        shutil.copy(f, out / "static" / f.name)

    def resolve(link: str, lang: str) -> str | None:
        path, _, frag = link.partition("#")
        key = _key(path)
        key = aliases.get(key, key)
        if key == "/":
            key = f"/{lang}"
        if key not in pages and f"/{lang}{key}" in pages:
            key = f"/{lang}{key}"  # internal pages link without the edition prefix
        if key not in pages:
            return None
        return _file_for(key) + (f"#{frag}" if frag else "")

    written = []
    for url, html in pages.items():
        lang = url.strip("/").split("/")[0]
        here = _file_for(url)
        html = re.sub(r'<link rel="(preconnect|stylesheet)" href="https://fonts\.[^"]*"[^>]*>\n?', "", html)

        def fix(m):
            attr, link = m.group(1), m.group(2)
            if link.startswith("/static/"):
                return f'{attr}="{_relative(here, link.lstrip("/").split("?")[0])}"'
            target = resolve(link, lang)
            if target is None:
                return f'{attr}="#"'
            return f'{attr}="{_relative(here, target)}"'

        html = _ATTR.sub(fix, html)
        demo = _relative(here, f"{lang}/demo/index.html")
        banner = (f'<div class="demo-banner">静态演示：全部为虚构示例数据，表单与按钮不会提交 · '
                  f'<a href="{demo}">演示指南</a></div>' if lang == "zh" else
                  f'<div class="demo-banner">Static demo: all data is fictional; forms and buttons do not submit · '
                  f'<a href="{demo}">Demo guide</a></div>')
        html = re.sub(r"(<body[^>]*>)", r"\1\n" + banner, html, count=1)
        html = html.replace("</head>", f'<script src="{_relative(here, "static/static-demo.js")}" defer></script>\n</head>', 1)
        target_file = out / here
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(html, encoding="utf-8")
        written.append(here)

    (out / "index.html").write_text(ROOT_INDEX, encoding="utf-8")
    (out / ".nojekyll").write_text("")
    shutil.rmtree(tmp, ignore_errors=True)
    return sorted(written)


# The neutral homepage: same rule as the live site and the Japan IR Index (remembered switch choice,
# then the first supported browser language, then English).
ROOT_INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>mamatch · demo</title>
<script>
(() => {
  let saved; try { saved = localStorage.getItem('mm-language'); } catch {}
  const preferred = (navigator.languages || [navigator.language])
    .map(t => (t || '').toLowerCase().split('-')[0]).find(l => l === 'zh' || l === 'en');
  const lang = ['zh', 'en'].includes(saved) ? saved : preferred || 'en';
  location.replace(lang + '/index.html' + location.hash);
})();
</script></head>
<body><p><a href="zh/index.html">中文</a> · <a href="en/index.html">English</a></p></body></html>
"""
