"""Runtime settings, read from the environment (see .env.example)."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATABASE_URL = os.environ.get("MAMATCH_DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'mamatch.db'}")

# "auto": use Claude when credentials resolve, otherwise the offline heuristics.
# "off": always offline (tests, demos without network). "on": fail if Claude is unavailable.
LLM_MODE = os.environ.get("MAMATCH_LLM", "auto")
CLAUDE_MODEL = os.environ.get("MAMATCH_CLAUDE_MODEL", "claude-opus-5-5")

# Production deal data must stay on mainland-China hosting (PIPL / data-export rules).
# This flag is shown in the UI so a Japan-hosted demo is never mistaken for production.
DEPLOYMENT_REGION = os.environ.get("MAMATCH_REGION", "demo-local")
