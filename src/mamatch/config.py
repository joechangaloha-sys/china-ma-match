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

# Demand statistics: groups smaller than this are shown as "<K" so no buyer can be singled out,
# and counts are rounded down to a multiple of K. Buyers drop out when criteria go unconfirmed.
MIN_GROUP_SIZE = int(os.environ.get("MAMATCH_MIN_GROUP", "5"))
CRITERIA_TTL_DAYS = 180

# Pilot prices in RMB, before VAT. Placeholders until the pilot pricing is decided; invoiced
# offline (by the partner adviser for seller fees), recorded in the workspace. See fees.py.
PREP_PACK_FEE_RMB = int(os.environ.get("MAMATCH_PREP_FEE", "40000"))  # data check + info memo, one-off
SELLER_PLAN_FEE_RMB = int(os.environ.get("MAMATCH_SELLER_FEE", "20000"))  # outreach retainer per period
OUTREACH_PERIOD_DAYS = 182
SUCCESS_FEE_RATE = float(os.environ.get("MAMATCH_SUCCESS_RATE", "0.04"))  # of final deal value
SUCCESS_FEE_MIN_RMB = int(os.environ.get("MAMATCH_SUCCESS_MIN", "300000"))
PLATFORM_SHARE = float(os.environ.get("MAMATCH_PLATFORM_SHARE", "0.25"))  # of fees the adviser collects
BUYER_PRIORITY_FEE_RMB = int(os.environ.get("MAMATCH_BUYER_FEE", "30000"))  # per year
PRIORITY_HEAD_START_DAYS = 7  # priority buyers see new listings this many days before everyone else
