# china-ma-match (mamatch)

An AI deal-origination workspace for Chinese boutique M&A advisers (accountants, law firms,
small FAs) working on private-company sales under RMB 100m. It is built on a **buyer-intent
index**: listed companies' acquisition announcements, turned into structured buyer profiles.

Background and positioning: [docs/research.md](docs/research.md).

## What the MVP does

1. **Buyer-intent index**: pulls acquisition announcements from CNINFO (巨潮资讯), extracts the
   sectors, regions and deal sizes each listed buyer goes after, and keeps the announcements as evidence.
2. **Seller intake and teaser**: the adviser records a target. Identifying details (name, owner,
   city, USCC, brands) stay in the workspace. A teaser is drafted in Chinese, Japanese or English
   from banded figures only, then a **re-identification check** flags anything that could reveal
   the company. Only low-risk teasers can be approved.
3. **Matching**: ranks buyers per target on sector, region, deal size and recency, with written reasons.
4. **Pipeline**: suggested → shortlisted → teaser sent → NDA → IM → LOI → closing → closed, with an event log.

Claude (`claude-opus-5-5`) is used for announcement extraction and teaser drafting, with
server-side refusal fallback enabled. Every step has an offline fallback, so the app runs
without credentials (`MAMATCH_LLM=off`).

## Run it

```bash
uv sync
uv run mamatch init-db --seed        # tables plus fictional example buyers and targets
uv run mamatch ingest-cninfo --days 90 --pages 2   # real buyer signals from CNINFO
uv run mamatch serve                 # http://127.0.0.1:8600
uv run pytest
```

Example records are fictional and labelled 示例 in the UI.

## Layout

```
src/mamatch/
  ingest/cninfo.py   CNINFO announcement search
  ingest/profile.py  announcement -> signal -> buyer profile
  teaser.py          banded facts, teaser drafting
  reid.py            re-identification check
  matching.py        buyer ranking with reasons
  pipeline.py        deal stages
  llm.py             Claude wrapper (structured JSON, fallback, offline mode)
  web/               FastAPI + Jinja adviser workspace
tests/               offline tests; fixtures/cninfo_query.json is a real CNINFO response
```

## Not built yet (deliberately)

- **Auth and multi-firm accounts.** The workspace assumes one firm and has no login: run it on
  localhost only.
- **Announcement PDFs.** Extraction reads titles only; `profile.extract(ann, body_text)` accepts
  PDF text once a PDF-to-text step is added. Deal sizes stay empty until then.
- **Public listings, buyer self-sign-up, payments, valuation opinions.** Out of scope; see the
  licensing notes in the research report.

## Open issues before production

- **Data residency.** Deal data must be hosted in mainland China (PIPL, data-export rules).
  Calling the Claude API sends teaser inputs abroad. The inputs are banded and name-free, but
  confirm the setup with PRC counsel, or keep Claude to public announcement data only.
- **Platform licensing.** A paid online information service needs an ICP licence; a foreign
  operator likely needs a Chinese partner. Stay an adviser tool, not a trading venue.
- **Validation.** Interview 15–20 Yangtze River Delta advisers before building further.
