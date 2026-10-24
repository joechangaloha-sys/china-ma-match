# Handoff: china-ma-match (mamatch)

Written 25 Oct 2026 when the session's credit ran low. Read this first, then `README.md`, `docs/design-v2.md`
and Joe's plan at `~/Documents/kimi/tasks/2026-10-24/21-21-56-3d0b2468/china_small_ma_pilot_and_ai_website_plan.md`.

## What Joe wants (decisions so far)

- An MVP website for small private-company sales in China, following the plan above: a curated, AI-assisted
  marketplace and deal workspace. Pilot focus: Shanghai–Suzhou–Hangzhou–Ningbo, deals of about RMB 2–20m.
- **Stack: keep Python** (FastAPI + Jinja + SQLAlchemy, SQLite now, PostgreSQL when deployed in China). Do not
  rewrite in Next.js.
- **Buyer side: a private buyer portal** (thesis, funding evidence, verification, introductions, NDA, data room).
  Nothing about buyers is ever public. The public site shows sellers (anonymised listings) only.
- Seller-facing pages must not mention plans or buyer demand statistics. Listings must show approximate size and
  the seller's ask (price band, stake, payment terms, founder transition, staff, timing).
- Internal pages must be clearly marked internal.
- **Ignore data residency/ICP/licensing in the code**: Joe will set that up inside China. Claude is used whenever
  it is available (offline fallbacks remain so tests run without credentials).
- Pricing (placeholders in `config.py`): free listing and browsing; seller preparation pack RMB 40k (data check +
  info memo); outreach retainer RMB 20k per 182 days; success fee 4% (min RMB 300k) for outreach clients with
  earlier fees credited; platform takes 25% of fees the partner adviser invoices.
- Patents: Joe said not now. Never touch `~/Documents/japan-ir-index`. Always ask before deleting any file
  under `~/Documents`.

## State of the code (updated 25 Oct 2026)

The rebuild toward Joe's plan is done and tested: 73 tests pass, including permission tests. Every page was
requested on the live app as each role (all 200), and the public home, listing and seller portal were checked
in the browser. See README.md for the structure.

## Next steps

1. Click through the internal mandate page and buyer portal in the browser as the deal manager and the demo
   buyer (tests cover them, but they have not been looked at visually).
2. Candidates for deletion, unused since the restructure **(ask Joe first)**: templates `buyers.html`,
   `buyer.html`, `buyer_portal.html`, `demand.html`; the buyer-priority parts of `plans.py` and
   `listing.board` / `listing.hidden_count`; `demand.py` (move `BUYER_KINDS` and `MACRO_REGIONS` to
   `taxonomy.py` first) and `tests/test_demand.py`.
3. From the plan, not built: MFA for deal managers, watermarks, malware scanning, sign-in rate limiting, CSRF
   tokens, semantic matching (pgvector), WeChat, PostgreSQL deployment, saved searches for buyers.
4. Pricing is placeholder (`config.py`); the NDA text in `offers.py` needs counsel review.

## Useful commands

```bash
uv sync
uv run pytest
MAMATCH_LLM=off uv run mamatch init-db --seed
uv run mamatch create-user you@example.com --role deal_manager
uv run mamatch serve   # http://127.0.0.1:8600
```
