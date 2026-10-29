"""Verify npm run dev starts and forwards host/port, then stop every child process."""

import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import httpx


root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temporary:
    env = {
        **os.environ,
        "MAMATCH_DATABASE_URL": f"sqlite:///{temporary}/preview.db",
        "MAMATCH_UPLOAD_DIR": f"{temporary}/uploads",
        "MAMATCH_LLM": "off",
        "MAMATCH_DEMO_MODE": "false",
        "MAMATCH_SEED_DEMO": "false",
    }
    process = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "7100"],
        cwd=root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        for attempt in range(80):
            if process.poll() is not None:
                raise RuntimeError(f"npm run dev exited with {process.returncode}")
            try:
                response = httpx.get("http://127.0.0.1:7100/health/live", timeout=1)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            raise RuntimeError("npm run dev did not expose port 7100")
        home = httpx.get("http://127.0.0.1:7100/", follow_redirects=False)
        assert home.status_code == 302 and home.headers["location"].startswith("/en")
        print("Local preview passed: npm run dev starts and forwards host/port")
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
