"""Run inside the demo web container; starts and stops its own test server."""

import os
import subprocess
import time
import uuid

import httpx
from sqlalchemy import func, select

from mamatch import db
from mamatch.models import Buyer, Target


BASE = "http://127.0.0.1:8080"
PASSCODE = os.environ["MAMATCH_DEMO_ACCESS_KEY"]
process = subprocess.Popen(["python", "-m", "mamatch.container"])
try:
    for attempt in range(120):
        if process.poll() is not None:
            raise RuntimeError(f"Container server exited with {process.returncode}")
        try:
            if httpx.get(f"{BASE}/health/ready", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.5)
    else:
        raise RuntimeError("Container server did not become ready")

    with httpx.Client(base_url=BASE, follow_redirects=False, timeout=10) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json() == {"status": "ready"}
        gated = client.get("/en/opportunities")
        assert gated.status_code == 303 and gated.headers["location"].startswith("/en/demo-access")
        entered = client.post("/en/demo-access", data={"access_key": PASSCODE, "next": "/en/opportunities"})
        assert entered.status_code == 303 and entered.headers["location"] == "/en/opportunities"
        board = client.get("/en/opportunities")
        assert board.status_code == 200 and "Project Delta" in board.text
        assert "all data is fictional" in board.text
        assert board.headers["x-robots-tag"] == "noindex, nofollow, noarchive"

        company = f"Container Smoke Fictional {uuid.uuid4().hex[:10]} Ltd"
        submitted = client.post("/en/sell", data={
            "company": company,
            "name": "Fictional Tester",
            "contact": "demo@example.test",
            "sector": "machinery",
            "province": "浙江",
            "revenue": "12.5",
            "consent": "1",
        })
        assert submitted.status_code == 303, submitted.text

    with db.session_scope() as session:
        target = session.scalar(select(Target).where(Target.legal_name == company))
        assert target is not None and target.status == "draft" and float(target.revenue) == 12.5
        assert session.scalar(select(func.count(Target.id)).where(Target.is_example)) >= 3
        assert session.scalar(select(func.count(Buyer.id)).where(Buyer.is_example)) >= 6
    print("Container smoke passed: passcode, health, fictional seed, form persistence and PostgreSQL reads")
finally:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
