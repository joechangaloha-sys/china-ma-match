# Handoff: china-ma-match (mamatch)

Last updated 25 Oct 2026. Read this first, then `README.md`. Private background (not in the public repo):
`docs/research.md`, `docs/design-v2.md`, and Joe's pilot plan at
`~/Documents/kimi/tasks/2026-10-24/21-21-56-3d0b2468/china_small_ma_pilot_and_ai_website_plan.md`.

Keep this file current after each meaningful piece of work (Joe's standing instruction).

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

93 tests pass (`uv run pytest`), including permission tests (other buyer, other seller, no data-room grant,
anonymous, adviser scope, revoked authorisation) and the static export. Structure and routes: README.md.

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
   limiting, CSRF tokens, semantic matching (pgvector), WeChat sign-in, buyer saved searches, PostgreSQL deployment.
5. Possible later: a Hong Kong demo server running the live app (password-protected, example data only) if the
   static demo is not enough for reviewers.

## Useful commands

```bash
uv sync
uv run pytest
MAMATCH_LLM=off uv run mamatch init-db --seed     # local DB with fictional examples and demo users (see seed.py)
uv run mamatch create-user you@example.com --role deal_manager
uv run mamatch serve                               # http://127.0.0.1:8600
uv run mamatch export-static --out static-demo     # static demo; preview with the static-demo launch config (port 8601)
```
