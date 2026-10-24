"""Runtime settings, read from the environment (see .env.example)."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATABASE_URL = os.environ.get("MAMATCH_DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'mamatch.db'}")

# "auto": use Claude when credentials resolve, otherwise the offline heuristics.
# "off": always offline (tests, demos without network). "on": fail if Claude is unavailable.
LLM_MODE = os.environ.get("MAMATCH_LLM", "auto")
CLAUDE_MODEL = os.environ.get("MAMATCH_CLAUDE_MODEL", "claude-opus-5-5")

# Demand statistics: groups smaller than this are shown as "<K" so no buyer can be singled out,
# and counts are rounded down to a multiple of K. Buyers drop out when criteria go unconfirmed.
MIN_GROUP_SIZE = int(os.environ.get("MAMATCH_MIN_GROUP", "5"))
CRITERIA_TTL_DAYS = 180

# Pilot prices in RMB. Placeholders until the pilot pricing is decided; invoiced offline, the
# operator records payment in the workspace (no payment handling on the platform).
SELLER_PLAN_FEE_RMB = int(os.environ.get("MAMATCH_SELLER_FEE", "20000"))  # per private mandate
BUYER_PRIORITY_FEE_RMB = int(os.environ.get("MAMATCH_BUYER_FEE", "30000"))  # per year
PRIORITY_HEAD_START_DAYS = 7  # priority buyers see new listings this many days before everyone else

# Production deal data must stay on mainland-China hosting (PIPL / data-export rules).
# This flag is shown in the UI so a Japan-hosted demo is never mistaken for production.
DEPLOYMENT_REGION = os.environ.get("MAMATCH_REGION", "demo-local")
