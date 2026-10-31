"""Runtime settings, read from the environment (see .env.example)."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

UPLOAD_DIR = os.environ.get("MAMATCH_UPLOAD_DIR", str(ROOT / "data" / "uploads"))  # outside static/: served only after a permission check
DATABASE_URL = os.environ.get("MAMATCH_DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'mamatch.db'}")

# "auto": use Claude when credentials resolve, otherwise the offline heuristics.
# "off": always offline (tests, demos without network). "on": fail if Claude is unavailable.
LLM_MODE = os.environ.get("MAMATCH_LLM", "auto")
CLAUDE_MODEL = os.environ.get("MAMATCH_CLAUDE_MODEL", "claude-opus-5-5")

# Pilot prices in RMB, before VAT. Placeholders until the pilot pricing is decided; invoiced
# offline (by the partner adviser for seller fees), recorded in the workspace. See fees.py.
PREP_PACK_FEE_RMB = int(os.environ.get("MAMATCH_PREP_FEE", "40000"))  # data check + info memo, one-off
SELLER_PLAN_FEE_RMB = int(os.environ.get("MAMATCH_SELLER_FEE", "20000"))  # outreach retainer per period
OUTREACH_PERIOD_DAYS = 182
SUCCESS_FEE_RATE = float(os.environ.get("MAMATCH_SUCCESS_RATE", "0.04"))  # of final deal value
SUCCESS_FEE_MIN_RMB = int(os.environ.get("MAMATCH_SUCCESS_MIN", "300000"))
PLATFORM_SHARE = float(os.environ.get("MAMATCH_PLATFORM_SHARE", "0.25"))  # of fees the adviser collects

# Static export only: shows the demo guide page (`mamatch export-static`).
DEMO_GUIDE = False

# Isolated dynamic demo: passcode gate, fictional seed and noindex headers. Disabled by default.
DEMO_MODE = os.environ.get("MAMATCH_DEMO_MODE", "").lower() in ("1", "true", "yes")
DEMO_ACCESS_KEY = os.environ.get("MAMATCH_DEMO_ACCESS_KEY", "")
DEMO_ACCESS_HOURS = int(os.environ.get("MAMATCH_DEMO_ACCESS_HOURS", "12"))
SEED_DEMO = os.environ.get("MAMATCH_SEED_DEMO", "").lower() in ("1", "true", "yes")
SECURE_COOKIES = os.environ.get("MAMATCH_SECURE_COOKIES", "").lower() in ("1", "true", "yes")


def validate_runtime() -> None:
    if DEMO_MODE and len(DEMO_ACCESS_KEY) < 12:
        raise RuntimeError("MAMATCH_DEMO_ACCESS_KEY must contain at least 12 characters in demo mode")
    if DEMO_MODE and not 1 <= DEMO_ACCESS_HOURS <= 168:
        raise RuntimeError("MAMATCH_DEMO_ACCESS_HOURS must be between 1 and 168")
    if SEED_DEMO and not DEMO_MODE:
        raise RuntimeError("MAMATCH_SEED_DEMO requires MAMATCH_DEMO_MODE=true")


# Public address used in share links and QR codes (the static export sets the GitHub Pages address).
PUBLIC_BASE_URL = os.environ.get("MAMATCH_PUBLIC_URL", "")

# Optional trusted, locally installed ClamAV executable. No scanner means no file release.
CLAMSCAN_PATH = os.environ.get("MAMATCH_CLAMSCAN_PATH", "")
