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

## State of the code

Last clean commit: `ca18ad3` (seller-only public site, 55 tests passing).

**After that, a large rebuild toward Joe's plan is in progress and only partly tested.** It is committed as a WIP
commit right after this file. Done in that WIP:

- `auth.py`: users (seller / buyer / deal_manager), scrypt passwords, server-side sessions (cookie `mm_session`),
  audit log helper. Models added in `models.py`: User, UserSession, Document, ExtractedField, MatchFeedback,
  ExpertReferral, AuditEvent; new fields on Target (status, seller_user_id, contact, normalized earnings), Buyer
  (thesis, funding, exclusions, experience), Match (NDA, data-room grant), Teaser (seller approval).
- `dealstatus.py`: explicit mandate statuses (draft → … → closed, paused, withdrawn, rejected), moved by people.
- `documents.py`: upload (PDF/CSV/TXT/images, 20 MB, stored under `data/uploads/`, outside static), pypdf text
  with `[page N]` markers, AI or rule-based extraction of financial fields with source page/quote/confidence,
  analyst confirm/correct/reject → writes `Target.financials`.
- `thesis.py`: buyer's free-text thesis → structured criteria (Claude or keyword rules); buyer confirms.
- `matching.py`: hard gates added (excluded sector, deal type, funding below asking price, earnings minimum).
- `offers.py`: analyst accept/reject with reasons (MatchFeedback), NDA click-accept (`NDA_TEXT`, needs counsel
  review), seller-granted data room, `can_view_document`, public inquiry, signed-in buyer introduction request.
- `analytics.py`: pilot funnel metrics for the dashboard.
- Web split into routers: `web/common.py` (templates, `require(role)`, helpers), `web/public.py` (home, /sell with
  intake form, /buy, /fees, /security, /opportunities, /login, /register, /invite/{token}),
  `web/seller.py` (/seller/{id}: progress, document checklist + upload, teaser approval, visibility, buyer
  approvals, data-room grant, name disclosure, questionnaire, memo), `web/buyer.py` (/buyer: thesis with AI
  pre-fill, introductions, NDA, memo, data-room downloads with audit), `web/internal.py` (/internal: mandates,
  buyer checks, documents/extraction review, matching decisions, status, fees, referrals, pipeline,
  /internal/dashboard, /internal/audit). `web/app.py` just wires routers (public last: it has a catch-all).
- Templates written for all of the above (`base.html` has public / seller / buyer / internal modes and the
  internal banner).
- `seed.py`: demo users (emails and the shared demo password are in `DEMO_USERS` / `DEMO_PASSWORD` in seed.py,
  .test domain, local only); example teasers are seller-approved; example statuses set.

## What is not finished (do these next, in order)

1. **Fix tests.** Non-web tests: 45/46 pass. Failing: `tests/test_offers.py::test_registration_flow` because
   `buyers.verify` now requires funding evidence (set `funding_evidence="bank_letter"` in that test's kwargs).
   **`tests/test_web.py` is still written for the old URLs** (`/listings`, `/s/{token}`, `/internal` without
   login) and must be rewritten: log in via `POST /login` with the seeded demo users, then test public pages,
   seller portal, buyer portal, internal pages, and especially the negative permission tests the plan asks for
   (a buyer cannot open another matter's document, a seller cannot open another seller's mandate, anonymous
   users get redirected from /seller, /buyer, /internal; a document view without a data-room grant returns 404
   and is logged).
2. **Run the app and click through** (`.claude/launch.json` → preview "mamatch", port 8600). Expect template
   bugs; none of the new templates has been rendered yet. Check `target.html`, `seller.html`, `buyer_home.html`
   (it uses `b[key]` on a SQLAlchemy object; Jinja falls back to getattr, but verify).
3. Local DB `data/mamatch.db` needs `uv run mamatch init-db --seed` after the model changes (additive migration
   in `db.py` adds columns; new tables are created). Backups from earlier steps are in `$TMPDIR`.
4. Add a CLI command to create a deal-manager user for real use (`mamatch create-user --role deal_manager`).
5. Unused after the restructure and candidates for deletion **(ask Joe first)**: templates `buyers.html`,
   `buyer.html`, `buyer_portal.html`, `demand.html`; modules `demand.py` (still imported for `BUYER_KINDS` and
   `MACRO_REGIONS`; move those to `taxonomy.py` first) and the buyer-priority parts of `plans.py` /
   `listing.board` / `listing.hidden_count` and `tests/test_demand.py`.
6. Unused imports to clean in `web/internal.py`, `web/seller.py`.
7. Update `README.md` (routes, accounts, demo sign-in pointer, new modules) and `docs/design-v2.md` (now
   superseded in part by Joe's plan; note the decisions above).
8. Later, per the plan: MFA for deal managers, watermarking, malware scanning of uploads, rate limiting on
   /login, semantic matching (pgvector), WeChat, PostgreSQL deployment.

## Useful commands

```bash
uv sync
uv run pytest
MAMATCH_LLM=off uv run mamatch init-db --seed
uv run mamatch serve   # http://127.0.0.1:8600
```
