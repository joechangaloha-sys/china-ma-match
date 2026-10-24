# china-ma-match (mamatch)

A curated, AI-assisted marketplace and deal workspace for selling and buying small private operating
businesses, in Chinese and English. Pilot deals: about RMB 2–20m. It follows
Joe's pilot plan (`~/Documents/kimi/tasks/2026-10-24/.../china_small_ma_pilot_and_ai_website_plan.md`):
a secure operating system for a concierge pilot, not an open marketplace.

Background: [docs/research.md](docs/research.md), [docs/design-v2.md](docs/design-v2.md) (pricing and
earlier decisions). Current status and next steps: [handoff.md](handoff.md).

## Who sees what

| Area | URL | Who | What |
|---|---|---|---|
| Public site | `/`, `/opportunities`, `/sell`, `/buy`, `/fees`, `/security` | anyone | How it works, anonymised seller listings (ranges, the seller's ask), seller intake form, anonymous inquiry form. Nothing about buyers is ever public. |
| Seller portal | `/seller` | seller (opened from a one-time invite link) | Progress, document checklist and upload, teaser approval, public listing on/off, approving each buyer, NDA-stage data-room grant and name disclosure, questionnaire, info memo. No plans or demand figures. |
| Buyer portal | `/buyer` | buyer (self-registers at `/register`) | Acquisition thesis in their own words, AI-structured and confirmed; funding range and evidence; introductions; click-accept NDA; info memo; data-room downloads (logged). |
| Internal | `/internal/...` | deal managers | Mandates and status, document extraction review, teasers, buyer verification queue, matching with accept/reject reasons, fees, referrals, pipeline, pilot dashboard, audit log. Marked internal on every page. |

Disclosure is staged: public ranges → seller-approved teaser → NDA and info memo (still no name) → seller-granted
data room → names disclosed both ways with the seller's consent.

## Languages and look

Two editions, `/zh/...` and `/en/...`, following the Japan IR Index rules: the neutral homepage `/` opens the
edition the visitor last chose with the header switch (remembered in localStorage and the `mm_lang` cookie),
otherwise the first supported browser language, otherwise English. Direct edition links never redirect; query
strings are kept, and redirects inside an edition stay in it (`LanguageEditions` in `web/app.py`). Labels are
written bilingually in code and `i18n.tr` / `i18n.val` pick the reader's side; public pages and both portals show
one language, internal pages stay bilingual for deal managers. The visual style (navy masthead over a brass rule,
serif headlines, IBM Plex, light only) matches the Japan IR Index house theme.

## AI with human control

- **Document extraction** (`documents.py`): PDF/CSV/TXT text → financial figures with document, page, quote, unit
  and confidence. An analyst confirms, corrects or rejects each figure before it reaches the financials.
- **Sale-readiness check** (`datacheck.py`): rules plus Claude; questions for the seller.
- **Teaser and info memo** (`teaser.py`, `infomemo.py`): re-identification check; analyst approval, then seller approval.
- **Buyer thesis** (`thesis.py`): free text → sectors, regions, size, earnings floor, funding, exclusions.
- **Matching** (`matching.py`): hard gates (sector, exclusions, deal type, funding vs. price, earnings), then
  ranking with written reasons; every analyst decision is recorded (`MatchFeedback`).

Claude (`claude-opus-5-5`) is used whenever available; every step has an offline fallback (`MAMATCH_LLM=off`).
Uploaded documents are treated as untrusted data. Status changes are made by people, never by a model response.

## Run it

```bash
uv sync
uv run mamatch init-db --seed          # tables (adds new columns to an old DB) plus fictional examples and demo users
uv run mamatch create-user you@example.com --role deal_manager   # a real deal-manager sign-in
uv run mamatch serve                   # http://127.0.0.1:8600
uv run pytest
```

Demo sign-ins for local testing are defined in `seed.py` (`DEMO_USERS`, `DEMO_PASSWORD`). Example records are
fictional and labelled 示例.

## Layout

```
src/mamatch/
  auth.py         users, scrypt passwords, sessions, audit log
  dealstatus.py   mandate statuses and allowed moves
  documents.py    uploads, text extraction, proposed figures, analyst review
  datacheck.py    sale-readiness checks
  thesis.py       buyer thesis structuring
  matching.py     hard gates + ranking with reasons
  offers.py       outreach, introductions, analyst decisions, NDA, data room, disclosure
  teaser.py reid.py infomemo.py listing.py fees.py analytics.py pipeline.py
  ingest/         CNINFO announcements (suggests listed buyers to approach)
  web/            app.py (wiring), public.py, seller.py, buyer.py, internal.py, common.py, templates/
tests/            offline tests incl. permission tests (another buyer, another seller, no grant, anonymous)
```

## Not built yet

MFA for deal managers, watermarking, malware scanning of uploads, rate limiting on sign-in, CSRF tokens (cookies
are SameSite=Lax), semantic retrieval for matching, WeChat sign-in, payments (fees are invoiced offline and
recorded), PostgreSQL deployment. Hosting, ICP and data-location setup in China are handled by Joe outside this code.
The NDA text in `offers.py` is a template for counsel to review.
