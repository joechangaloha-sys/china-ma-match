# china-ma-match (mamatch)

A curated, AI-assisted marketplace and deal workspace for selling and buying small private operating
businesses, in Chinese and English. Pilot deals: about RMB 2–20m. It follows
Joe's pilot plan (`~/Documents/kimi/tasks/2026-10-24/.../china_small_ma_pilot_and_ai_website_plan.md`):
a secure operating system for a concierge pilot, not an open marketplace.

Background research and design notes are kept privately, outside this repository. Current status and next steps: [handoff.md](handoff.md).

## NDA/VDR workflow with connections deferred (31 Oct 2026)

Joe explicitly deferred external setup. The full checklist is in `docs/INTEGRATIONS_TODO.md` and on the
signed-in deal-manager page `/internal/connections`. No provider account, credentials, subscription,
real signing process or external room invitation has been created.

The dynamic demo adds `/zh/handoff` and `/en/handoff`: nine isolated scenarios covering pending signing,
missing authority review, seller approval, pending provisioning, active/expired/revoked access, changed
parties and cancellation of an unsigned request. These use the same offline state machine as the private
portals and do not change saved mandates.

Open **NDA / VDR handoff** from a buyer row in an internal mandate to operate the persisted mock workflow:
prepare a request → simulate a receipt → review signatory authority → request read-only access for 1–30 days
→ mandate owner approves room/role/expiry in their seller portal → deal manager confirms mock provisioning.
Owner approval alone does not activate access. Owner/deal manager may revoke it; the demo can also advance
past expiry. Every action is recorded in `handoff_events`; duplicate/stale signing receipts cannot revive a
grant. Changed parties, agreement version, room, role or expiry invalidate the corresponding approvals.
Completed NDA evidence is retained; cancellation applies to unsigned requests, not executed contracts.

The mock adapter is rejected for real mandates. It produces only labelled illustrative hashes/references,
not signed PDFs, legal signatures or real VDR acknowledgements. Buyer demo downloads and memo display
require an active, current, unexpired grant on every request, replacing the old timestamp-only control.
Real provider callbacks, reconciliation, provider-side expiry/revocation, durable evidence archives and
external room connections remain deferred. A future real adapter must not treat mock state as production
proof or treat a local flag as confirmation that an external provider has revoked access.

## Evidence and approval controls (31 Oct 2026)

The dynamic fictional demo includes `/zh/workflow` and `/en/workflow`: a read-only walkthrough of
server-enforced release checks, including unsupported assertions, content/source changes, missing seller
approval, invalid revenue and supported loss-making businesses. Each request uses a throwaway database;
it cannot alter mandates or distribute documents. The page is unavailable outside demo mode.

Deal managers can open **Review evidence and version** under each teaser/memo in the internal mandate
page. Every non-empty assertion, including public-listing fields, needs a review linked to an existing
source document on the same mandate, its SHA256, and a page/section review note. Evidence reviews and
analyst/seller approvals bind to the document's content, version, language and source snapshot. Changed
content, changed source figures or replaced evidence locks release. Real reviews require authenticated
roles; clearly labelled fictional seed reviews are used only for example records. Legacy approvals without
hashes are untrusted; fictional seed documents are regenerated, and real documents require a new review.

Sellers now approve the current info-memo version in their portal. Public listing/detail pages and teaser
outreach recheck the release gate. Templates generate teasers and memos with AI calls disabled pending
provider/data-transfer review. A claim review records a human's judgement; it does not prove authenticity.

The fee page shows worked examples and credits; no-closing language applies only to the success fee.
The agreed pilot minimum remains unchanged. Signed-in mutations require a session-bound CSRF token,
cross-origin submissions are rejected, and ten failed account sign-ins trigger a 15-minute rolling limit.
The container installs the tested `uv.lock` using a pinned uv version.

**Remaining before real-data use:** reliable e-signature integration and signer-authority evidence,
external professional VDR grants/expiry/revocation, MFA, upload malware scanning, formal database
migrations and legal/data-processing review. Click acceptance is explicitly a fictional demonstration;
real mandates cannot use click acceptance, in-app buyer document downloads, name disclosure or indicative
offers as a substitute for that integration. Real post-NDA memos are not displayed in the buyer portal.
Opt-in alerts and WeChat integration remain later work. No new Tencent resources were created.

## Who sees what

| Area | URL | Who | What |
|---|---|---|---|
| Public site | `/`, `/opportunities`, `/sell`, `/buy`, `/fees`, `/security` | anyone | How it works, anonymised seller listings (ranges, product line, the seller's ask) with keyword and detailed search (revenue, profitability, margin, employees, years in business, price, reason for sale, deal type), seller intake form, anonymous inquiry form. Nothing about buyers is ever public. |
| Seller portal | `/seller` | seller (opened from a one-time invite link) | Progress, document checklist and upload, teaser approval, public listing on/off, sending the teaser to ticked buyers in one step, comparing indicative offers side by side, NDA-stage data-room grant and name disclosure, questionnaire, info memo. No plans or demand figures. |
| Adviser portal | `/adviser` | accountant, lawyer or consultant (registers at `/register/adviser`, verified by a deal manager) | Opens mandates for clients, sends the owner an authorisation link, uploads documents and answers the questionnaire while the owner's authorisation is active. Cannot approve teasers, publish, choose buyers or disclose names. |
| Buyer portal | `/buyer` | buyer (self-registers at `/register`) | Acquisition thesis in their own words, AI-structured and confirmed; funding range and evidence; introductions; click-accept NDA; info memo; data-room downloads (logged); a non-binding indicative offer in a fixed format. |
| Internal | `/internal/...` | deal managers | Mandates and status, document extraction review, teasers, buyer verification queue, matching with accept/reject reasons, fees, referrals, pipeline, pilot dashboard, audit log. Marked internal on every page. |

Authority is checked before anything reaches buyers (`authority.py`): the owner states their role (legal
representative, shareholder and stake, director, authorised by the shareholders) in their own account, and a
deal manager verifies it against the business licence and ownership documents. Advisers act only as verified
professionals and only under the owner's own authorisation for that sale, which the owner signs and can revoke.
Publishing and outreach are blocked until the owner's authority is verified.

Disclosure is staged: public ranges → seller-approved teaser → NDA and info memo (still no name) → seller-granted
data room → names disclosed both ways with the seller's consent.

## Languages and look

Two editions, `/zh/...` and `/en/...`: the neutral homepage `/` opens the
edition the visitor last chose with the header switch (remembered in localStorage and the `mm_lang` cookie),
otherwise the first supported browser language, otherwise English. Direct edition links never redirect; query
strings are kept, and redirects inside an edition stay in it (`LanguageEditions` in `web/app.py`). Labels are
written bilingually in code and `i18n.tr` / `i18n.val` pick the reader's side; public pages and both portals show
one language, internal pages stay bilingual for deal managers. The visual style (navy masthead over a brass rule,
serif headlines, IBM Plex, light only) is the project's house theme.

Detailed search filters only on the bands the cards already show, and on profit and margin only where the seller
agreed to show earnings; values that are not published band edges are ignored, so searches cannot reveal exact
figures (`listing.matches`).

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

## Run the complete local demo

On this Mac, double-click `START_LOCAL_DEMO.command`, or run it in Terminal. Keep the window open while using
the site; press Ctrl+C to stop. It uses a dedicated fictional SQLite database, seeds all role accounts and starts
at `http://127.0.0.1:7100` with outer passcode `demo-gate-local-only`.

```bash
./START_LOCAL_DEMO.command
# Optional: ./START_LOCAL_DEMO.command --host 127.0.0.1 --port 7100
```

`npm run dev -- --host 127.0.0.1 --port 7100` uses the same launcher for the Kimi Work preview.

## Run it manually

```bash
uv sync
uv run mamatch init-db --seed          # tables (adds new columns to an old DB) plus fictional examples and demo users
uv run mamatch create-user you@example.com --role deal_manager   # a real deal-manager sign-in
uv run mamatch serve                   # http://127.0.0.1:8600
uv run pytest
```

Demo sign-ins for local testing are defined in `seed.py` (`DEMO_USERS`, `DEMO_PASSWORD`). Example records are
fictional and labelled 示例.

## Dynamic demo (Docker and Tencent Cloud)

`Dockerfile` runs the app as a non-root user on port `8080`; `compose.demo.yaml` adds an isolated
PostgreSQL 16 database and fictional seed data. For a local container demo:

```bash
docker compose -f compose.demo.yaml up --build
# http://127.0.0.1:8600 — outer demo passcode: demo-gate-local-only
```

The demo has a separate expiring passcode gate, visible fictional-data warnings and `noindex` headers.
It is not a production security boundary. `deploy/tencent-cloud/README.md` is the Tencent account,
CloudBase CloudRun and private TencentDB for PostgreSQL publishing runbook; its `demo.env.example`
lists placeholders only. The default Tencent URL is for development/testing, not a production launch.
Uploaded files are ephemeral on CloudRun until private COS storage is implemented.

Build the clean console-upload package and standalone operator guide with:

```bash
python scripts/build_tencent_bundle.py
# release/mamatch-tencent-demo.zip
# release/mamatch-tencent-demo-guide.md
# release/mamatch-tencent-demo.sha256
```

The ZIP has `Dockerfile` at its root and excludes Git history, local databases, virtual environments, screenshots,
research notes and credentials. The extracted bundle is independently testable with `uv run --frozen pytest`.

## Static demo (GitHub Pages)

`uv run mamatch export-static --out static-demo` writes the whole demo as plain HTML: every page in both
editions and as each example role (visitor, seller, buyer, adviser, deal manager), with relative links, a
"static demo" banner, a demo guide (`/zh/demo/`, `/en/demo/`) with an 8-step guided tour, the opportunities search running in the browser
on band data only, and every other form disabled. It uses a throwaway database seeded with the fictional examples,
and drops Google Fonts (blocked in mainland China). `.github/workflows/pages.yml` builds and publishes it on each
push to `main` once Pages > Source is set to "GitHub Actions". Preview locally with the `static-demo` entry in
`.claude/launch.json` (port 8601).

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
recorded), durable COS uploads, and production database migrations. PostgreSQL and Tencent demo deployment are
prepared and locally smoke-tested, but no cloud resource has been deployed. Production hosting, ICP and
data-location setup in China are handled by Joe outside this code. The NDA text in `offers.py` is a template for
counsel to review.
