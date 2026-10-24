# china-ma-match (mamatch)

An M&A matching service for private-company sales in China under RMB 100m, run as an
**invitation-only pilot** by an adviser/operator. Buyers register and say what they want to buy;
sellers see that demand only as anonymous totals, and choose whether to list anonymously or stay private.

Background and positioning: [docs/research.md](docs/research.md). Design and pricing: [docs/design-v2.md](docs/design-v2.md).

## What it does

1. **Buyer registration.** The operator invites buyers (CNINFO acquisition announcements suggest
   listed companies worth inviting and pre-fill their criteria). Buyers register on a private link,
   state sector, provinces, deal size and deal type, and are verified against the business registry.
2. **Aggregate demand.** Sellers see how many verified buyers want a company like theirs, for fixed
   sector × region buckets only. Groups under 5 show as "<5", counts round down to a multiple of 5,
   and a breakdown is hidden if any group in it is under 5. Buyer names are never shown.
3. **Two seller levels.**
   - **Listed (free):** an anonymised card (macro-region, bands, fixed vocabulary) on a board that
     verified buyers browse. Needs an approved, low-risk teaser first.
   - **Private:** not listed. The paid plan unlocks the detailed demand breakdown and outreach: the
     adviser shortlists matching buyers, the seller approves each one, and approval sends the teaser.
4. **Private-seller fees** (`fees.py`): teaser, demand total and listing are free. A one-off
   **preparation pack** covers a data check of what the seller submits (three years of figures and
   a diligence checklist: invoiced vs. book revenue, social insurance, permits in the founder's
   name, land, customer concentration, guarantees) and an **info memo** draft that buyers see only
   after an NDA. An **outreach retainer** runs per 182 days. A **success fee** (4%, minimum RMB 300k,
   placeholders) applies at closing for outreach clients, less fees already paid. Fees are
   invoiced by the partner adviser; the platform's 25% share is recorded with each charge.
5. **Buyer priority plan (paid):** new listings 7 days early, search and filters on the board, and
   first place among equally good fits in a seller's outreach list (shown to the seller).
6. **Teasers and re-identification check** (from v1) in Chinese, Japanese or English, and a
   **pipeline** from suggested to closed. Names are disclosed both ways only after an NDA and the
   seller's approval.

Pages: operator workspace at `/` (targets, buyers, demand, pipeline); seller page `/s/<token>`;
buyer page `/b/<token>`. Payments are invoiced offline and recorded by the operator; prices in
`config.py` are placeholders.

Claude (`claude-opus-5-5`) is used for announcement extraction and teaser drafting, with
server-side refusal fallback enabled. Every step has an offline fallback, so the app runs
without credentials (`MAMATCH_LLM=off`).

## Run it

```bash
uv sync
uv run mamatch init-db --seed        # tables (adds new columns to an old DB) plus fictional examples
uv run mamatch ingest-cninfo --days 90 --pages 2   # real buyer signals from CNINFO
uv run mamatch serve                 # http://127.0.0.1:8600
uv run pytest
```

Example records are fictional and labelled 示例 in the UI.

## Layout

```
src/mamatch/
  ingest/cninfo.py   CNINFO announcement search
  ingest/profile.py  announcement -> signal -> suggested buyer profile
  buyers.py          invite -> register -> verify
  demand.py          k-suppressed demand statistics
  plans.py           seller and buyer plans, what each unlocks
  listing.py         anonymised board and listing cards
  offers.py          seller-approved outreach, board interest, name disclosure
  fees.py            seller fees, retainer period, success fee with credits
  datacheck.py       checks on seller-submitted data
  infomemo.py        info memo drafts (masked identity, exact figures, post-NDA)
  teaser.py          banded facts, teaser drafting
  reid.py            re-identification check
  matching.py        buyer ranking with reasons
  pipeline.py        deal stages
  llm.py             Claude wrapper (structured JSON, fallback, offline mode)
  web/               FastAPI + Jinja adviser workspace
tests/               offline tests; fixtures/cninfo_query.json is a real CNINFO response
```

## Not built yet (deliberately)

- **Auth and multi-firm accounts.** The workspace assumes one operator firm and has no login; seller
  and buyer pages are private links. Run it on localhost only.
- **Payments.** Plans are invoiced offline and recorded by the operator.
- **Announcement PDFs.** Extraction reads titles only; `profile.extract(ann, body_text)` accepts
  PDF text once a PDF-to-text step is added. Deal sizes stay empty until then.
- **Open buyer self-sign-up, public (non-registered) listings, valuation opinions.** Out of scope
  for the invitation-only pilot; see the licensing section of the design note.

## Open issues before production

- **Data residency.** Deal data must be hosted in mainland China (PIPL, data-export rules).
  Calling the Claude API sends teaser inputs abroad. The inputs are banded and name-free, but
  confirm the setup with PRC counsel, or keep Claude to public announcement data only. The data
  check and info memo use exact financials, so they stay rule-based and template-based unless
  `MAMATCH_ALLOW_DATA_EXPORT=1` (set it only after counsel approves, or with a mainland-hosted model).
- **Platform licensing.** Paid plans for registered users make this an operating internet
  information service: it needs an ICP operating licence, and foreign ownership is capped, so a
  Chinese partner is needed. Stay clear of trading-venue rules: registered buyers only, one
  adviser-led deal at a time, no bidding, no payment handling.
- **Validation.** Interview 15–20 Yangtze River Delta advisers before building further.
