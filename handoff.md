# Handoff: china-ma-match (mamatch)

Last updated 29 Oct 2026. Read this first, then `README.md`. Private background (not in the public repo):
`docs/research.md`, `docs/design-v2.md`, and Joe's pilot plan at
`~/Documents/kimi/tasks/2026-10-24/21-21-56-3d0b2468/china_small_ma_pilot_and_ai_website_plan.md`.
Research brief for Kimi (26 Oct): `docs/kimi-handoff.md`; Kimi writes its findings to `docs/kimi-research/`
(both gitignored). Read `docs/kimi-research/00-index.md` first when it exists.

Keep this file current after each meaningful piece of work (Joe's standing instruction).

## Evidence-bound document release (31 Oct 2026, branch kimi/release-controls)

- Joe approved the review recommendations and asked to build and show them on the website. First
  implementation: bilingual `/workflow` fictional walkthrough, clearer fee wording and worked examples,
  `ReleaseClaim` evidence records linked to mandate documents and hashes, analyst/seller approval hashes,
  seller info-memo approval, and release checks on public listing/detail pages and teaser distribution.
- Source/content/evidence changes invalidate release. Every assertion and public card field needs human
  evidence review. Fictional reviews are labelled and isolated from real mandates. Legacy hashless
  approvals are not trusted; example documents are regenerated, real documents require review.
- Document AI calls are disabled. Real mandates cannot use demo click NDAs, in-app buyer document downloads,
  name disclosure, post-NDA memo display or indicative offers until the verified-signature/external-VDR
  handoff is integrated. Fictional examples retain their demonstration flow.
- CSRF tokens protect signed-in forms; cross-origin submissions are rejected. Account sign-ins are limited
  after ten failures in a rolling 15-minute window. Docker now installs `uv.lock` with pinned uv.
- Prices are unchanged; the fee page explicitly shows the 15% effective minimum at RMB 2m and credits.
- Pending integrations: signature provider and signer authority proof; external VDR expiry/revocation;
  MFA, malware scanning, formal migrations, legal/data review; opt-in alerts/WeChat. The website labels
  these limits. Do not present this as a production launch or mainland CloudBase deployment.
- Validation: full offline test suite, legacy SQLite upgrade preserving 3 targets/40 buyers/13 matches,
  browser scenario checks and 375px layouts. PR: https://github.com/joechangaloha-sys/china-ma-match/pull/2. All 117 offline tests pass. Existing seller FAQ PR #1 is included
  in this branch; no merge or direct main push. Deploy only the pushed review branch to Lighthouse.

## Seller-page success-fee FAQ (31 Oct 2026, branch kimi/seller-fee-faq)

- Added a "Questions from sellers" / 卖方常见问题 section to the public seller page (`page_sell.html`), with one
  bilingual entry explaining the success fee for outreach clients: 4% of the deal value, minimum RMB 300,000,
  earlier preparation and outreach fees credited, charged only at closing; free-listing sellers pay no success
  fee. Amounts come from `config.py` (`SUCCESS_FEE_RATE`, `SUCCESS_FEE_MIN_RMB`), so they stay in step with the
  fees page, and the entry links to `/fees`. All 104 tests pass (`uv run pytest`); both editions render with no
  language leakage. PR: pending push access from this environment.

## Live fictional demo and Git updates (29 Oct 2026)

- **Lighthouse demo:** Singapore server `43.153.223.242`, temporary HTTPS address
  `https://43.153.223.242.sslip.io`. The public `main` branch contains the dynamic demo (`056ad25`) and Git
  deployment route (`93be97b`). Joe reports that the deployed site responds, `/health/ready` returns 200, existing
  records survived the switch (40 buyers, 15 teasers, 13 matches and others), and the outer passcode is unchanged.
- **Routine updates use Git, not ZIP uploads.** Change and test locally, commit, run `git push`, then run
  `deploy/lighthouse/deploy.sh` from the repository root. An optional branch argument deploys another branch.
  Only code pushed to GitHub is deployed. `UPLOAD_TO_LIGHTHOUSE.command` and `install.sh` are first-install-only;
  do not build new ZIP bundles for ordinary updates.
- `deploy.sh` connects as `ubuntu` using Joe's SSH key (`~/.ssh/id_ed25519`), then clones/pulls `origin/main` into
  `/opt/mamatch-src` and matches it exactly to GitHub with a remote hard reset. It rebuilds with Docker Compose,
  waits for `/health/ready`, and prunes old images. Never edit `/opt/mamatch-src` directly on the server.
- **Server layout:** `/opt/mamatch-src` is the deployment source; `/opt/mamatch` retains `.env` (PostgreSQL password,
  demo passcode and public URL) and `DEMO_LOGIN.txt`. Compose reads secrets with `--env-file`; `show_login.sh`
  remains the way to retrieve demo login details. `compose.git.yaml` changes only the web build context to `../..`.
  The Compose project remains `mamatch-lighthouse`, preserving the PostgreSQL, uploads, Caddy-data and Caddy-config
  volumes. **Never run `docker compose down -v`.**
- The repository is **public**: never commit `.env`, passwords, keys or genuine business data. Fictional demo data
  only. `.gitignore` excludes `release/`, `.test-tools/` and `.DS_Store`. On 29 Oct the old release ZIPs (with
  their `.sha256` files) and the extracted `release/mamatch-lighthouse-demo 2/3/4` folders were moved to the macOS
  Trash. `release/` still holds the original extracted folder, the two guides and the `verify-*` test folders.

## Where things are

- **Code:** public repo https://github.com/joechangaloha-sys/china-ma-match (`main`, remote `origin`). This Mac's
  `gh` and git use the **joechangaloha-sys** account by default.
- **Static demo (for reviewers, e.g. a colleague in China):** https://joechangaloha-sys.github.io/china-ma-match/
  (demo guide: `/zh/demo/index.html`). Rebuilt and redeployed by `.github/workflows/pages.yml` (tests + export,
  Node 24 action versions) on every push to `main`. Build locally with `uv run mamatch export-static`.
  github.io can be slow in mainland China; fallback is zipping `static-demo/` and sending it.
- **Kept out of the public repo:** `docs/research.md`, `docs/design-v2.md` (gitignored; scrubbed from history on
  25 Oct; a pre-rewrite backup bundle was saved in `$TMPDIR`).
- **Pending:** deleting the empty old repo `joechang-aloha/china-ma-match`. A terminal tab ("Delete old repo") runs
  `gh auth refresh -s delete_repo` for joechang-aloha, then deletes it and switches back to joechangaloha-sys;
  it was waiting for Joe to press Enter after approving in the browser. Check with
  `gh api repos/joechang-aloha/china-ma-match` (404 = deleted) and `gh api user --jq .login` (should be
  joechangaloha-sys).

## What Joe wants (decisions so far)

- An MVP following the pilot plan: a curated, AI-assisted marketplace and deal workspace for small private-company
  sales (pilot deals about RMB 2–20m), in Chinese and English, open to domestic and international buyers.
- **Stack: Python** (FastAPI + Jinja + SQLAlchemy; SQLite now, PostgreSQL when deployed). No Next.js rewrite.
- **Public site shows sellers only** (anonymised listings with size and the seller's ask, detailed search).
  Nothing about buyers is public. **Private portals** for sellers, buyers and advisers; **internal** pages for
  deal managers, clearly marked internal. Seller pages never mention plans or buyer-demand statistics.
- **Authority:** nothing reaches buyers until a deal manager verifies the owner's authority to sell. Advisers
  (accountants, lawyers, consultants) must be verified professionals and act only under the owner's own signed,
  revocable authorisation; approvals stay with the owner.
- **Fees** (placeholders in `config.py`): free listing and browsing; preparation pack RMB 40k; outreach retainer
  RMB 20k per 182 days; success fee 4% (min RMB 300k) for outreach clients, earlier fees credited; the platform
  takes 25% of fees the partner adviser invoices (site copy says so, disclosed to the client).
- **Brand:** "mamatch" for now; tagline 把企业交棒给对的人 / Hand your company on to the right owner. Founders
  described as having bulge-bracket, major law firm and Big Four experience; no personal names on the site.
  "Relay"/接棒 rejected as a brand (too close to existing M&A platforms and "Relay" M&A firms).
- **Look and languages** follow a separate reference project in `~/Documents` (read-only; never modify it):
  navy/brass house style; `/zh/` and `/en/` editions; neutral homepage picks the remembered switch choice, then the
  browser language, then English.
- Data residency, ICP and licensing are handled by Joe in China, outside the code. Patents: not now.
- Always ask before deleting any file under `~/Documents`.

## State of the code

104 tests pass (`MAMATCH_LLM=off uv run pytest`), including permission tests (other buyer, other seller, no data-room grant,
anonymous, adviser scope, revoked authorisation), the static export and dynamic-demo access/configuration tests.
Structure and routes: README.md.

Added 26 Oct: dynamic fictional-data demo deployment support. `web/demo.py` adds an expiring signed passcode
cookie, safe redirects, noindex headers and liveness/readiness checks; `web/app.py` validates configuration,
initialises the database and optionally seeds examples. `Dockerfile`, `container.py`, `compose.demo.yaml` and
`psycopg` support non-root CloudRun on `$PORT` with PostgreSQL. `deploy/tencent-cloud/README.md` is Joe's
account-to-publish guide; `demo.env.example` contains placeholders only. CloudRun maximum instances must stay
at 1 while startup seeding is enabled. Local uploads remain ephemeral until COS is implemented. Verified with
the full test suite, the `npm run dev` host/port preview check, and an equivalent isolated Docker/PostgreSQL 16
smoke test covering passcode access, health, seed data, English pages, seller form persistence and DB read-back.
`node scripts/visual_demo.mjs` also passed in isolated headless Chrome: passcode redirect, fictional-data warning,
Chinese homepage, English opportunities and 375 px Chinese opportunities, with no horizontal overflow. Screenshots
are in `artifacts/demo-visual/`; the script starts and stops the app and Chrome itself. Docker Compose itself was
not installed, so that exact Compose command was not executed. No Tencent resources were created and no real
credentials/data were used.

Local preview fix (27 Oct): executable `START_LOCAL_DEMO.command` starts the seeded fictional demo on port 7100
with passcode `demo-gate-local-only`; keep its Terminal window open, Ctrl+C stops it. It supports `--host`/`--port`,
and `npm run dev` uses the same launcher. Both `scripts/smoke_preview.py` and the full headless-Chrome visual test
pass through this launcher. This fixed Joe's `localhost refused to connect` report: a server must actually be running;
the preview URL alone does not start one in his external browser.

Tencent handoff package added 26 Oct: `scripts/build_tencent_bundle.py` creates `release/mamatch-tencent-demo.zip`,
a standalone operator guide and SHA256 file. The ZIP has Dockerfile at archive root and 105 files, with no local
DB, virtualenv, Git metadata, screenshots, research or credentials. `deploy/tencent-cloud/README.md` is the
comprehensive console-upload/redeploy/acceptance/troubleshooting guide; `deploy_demo.sh` is an optional redeploy
helper (`--check` tested only; no cloud deploy). The extracted ZIP independently passed all 104 tests and its
Docker image passed the isolated PostgreSQL 16 passcode/health/seed/seller-form/read-back smoke test. Verification
extraction directories are gitignored. The release ZIP is ready for console upload but is not deployed.

Layout is checked on phones and laptops: no page overflows sideways at 320, 375, 414, 768, 1280 or 1440 px (30
pages incl. every role's portal and the internal pages); the menu wraps on phones; wide tables scroll inside their
own box. Re-check with the iframe overflow script approach after big layout changes.

Added 25 Oct (after research on Acquire.com, Axial and similar marketplaces): **indicative offers** after the NDA in a fixed format
(`IndicativeOffer`, `offers.submit_offer`), compared side by side on the seller page (anonymised) and internally;
**send to ticked buyers in one step** on the seller page (`offers.approve_many`); **listing share panel** (QR code via
`segno`, copy text and link; links use `config.PUBLIC_BASE_URL`, set to the Pages address by the export); **guided
tour** (8 steps, both languages) in the static demo, started from the demo guide (`export.tour_steps`, `static-demo.js`).
Suggested but not built: a free indicative value range for sellers (careful: the plan rules out unreviewed AI
valuations) and saved searches with new-listing alerts for buyers.

Added 26 Oct (after a look across Axial and BizBuySell): listing pages show **what the sale includes** (premises,
permits, inventory: `Target.premises/permits/inventory`, vocab in `taxonomy.py`, set in the internal ask form), the
**year the figures cover** (`listing.figures_year`), **what buyers can get next** (NDA, info memo, data room:
`listing.readiness`) and **similar opportunities** (`listing.similar`). The board keeps short cards (`listing_card(full=)`).
**Report a problem** (`/opportunities/{id}/report`, stored as `listing_report` audit events, shown on the internal
mandate page) and a **code of conduct** page (`/conduct`, footer link). Six FAQ questions: what is sold, owner
handover, how the price is paid, no direct contact, avoiding scams, rules for everyone. Other ideas from that look,
not built: a seller "buyer demand" count, listing statistics for sellers, saved searches, buyer track-record
profiles, a quarterly market snapshot once there is enough data, a closed-deals page, and a buyer-side success fee
on a sliding scale as a pricing option.

Language: public pages and both portals show one language only, including match reasons (`i18n.reason`),
drafted teasers and memos (examples drafted separately in zh and en; `teaser.localised`), fee amounts and the
data-check label. Free text people type (offer conditions, notes) appears as typed. Test:
`test_wrong_language_text_stays_off_portal_pages`.

Rationale added to the FAQ and homepage (Joe's reasoning, 25 Oct; on 26 Oct the
market comparison on the site and in the FAQ became the US market: investment banks rarely below USD 25–50m, brokers and
marketplaces such as BizBuySell, PE-backed roll-ups in vets/HVAC/auto repair); the bakery and car-repair/dry-cleaner
examples; small companies are owners' main wealth; in China trust is the hard part. Joe's internal view: buyers
and sellers would use it even if ~7 in 10 listings were fully reliable at first, aiming for 9 in 10. The public
copy states only the 9-in-10 goal and shows per-listing verification (`listing.checks`). Next trust step promised
in the FAQ: document integrity checks (edited PDFs, registry-code match, balance sheet balances, figures agreeing
across documents, repeated invoice numbers), flagged for people to review.

Recent additions: detailed search (bands only, earnings only where the seller agreed), product/service line on
listings, landing-page rationale and FAQ, adviser portal with verified authorisation, tagline, static export,
GitHub Pages workflow.

## Next steps / open items

1. Finish deleting the old joechang-aloha repo (see Pending above).
2. Counsel review needed for the NDA text (`offers.NDA_TEXT`) and the owner's authorisation text
   (`authority.AUTH_TEXT`); final prices in `config.py`.
3. Not translated yet: matching reasons shown to sellers (English only); AI-drafted teasers and memos appear in the
   language they were drafted in.
4. From the plan, not built: MFA for deal managers, document watermarks, malware scanning of uploads, sign-in rate
   limiting, CSRF tokens, semantic matching (pgvector), WeChat sign-in, buyer saved searches, durable COS uploads
   and production database migrations.
5. Routine Lighthouse updates now follow the Git route above; `deploy/lighthouse/README.md` is the operating guide.
   Do not request Joe's password, secret keys or full database URL. No real domain or production/ICP launch yet.

## Useful commands

```bash
uv sync
uv run pytest
MAMATCH_LLM=off uv run mamatch init-db --seed     # local DB with fictional examples and demo users (see seed.py)
uv run mamatch create-user you@example.com --role deal_manager
uv run mamatch serve                               # http://127.0.0.1:8600
uv run mamatch export-static --out static-demo     # static demo; preview with the static-demo launch config (port 8601)
```
