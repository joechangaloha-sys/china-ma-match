# Instructions for coding agents (Kimi and others)

Project: Mamatch (china-ma-match)
GitHub: https://github.com/joechangaloha-sys/china-ma-match (remote `origin`, account joechangaloha-sys)
On Joe's Mac the repository is at ~/Documents/china-ma-match. Anywhere else (a cloud agent), clone it first:
`git clone https://github.com/joechangaloha-sys/china-ma-match.git && cd china-ma-match`. Pushing needs write
access to that repository (a GitHub connection or a token Joe provides); without it, stop and say so.

## Read first
1. handoff.md (current state, Joe's decisions, what is pending)
2. README.md (how to run it)
3. docs/kimi-handoff.md if your task is research (private, not in git)

## Before you change anything
- `git fetch origin && git status`. Start from an up-to-date `main`.
- Create a branch for your work: `git switch -c kimi/<short-topic>` (e.g. `kimi/seller-faq`).

## While working
- Python stack: FastAPI + Jinja + SQLAlchemy. Run with `uv run mamatch serve` (http://127.0.0.1:8600).
- Never commit docs/research.md, docs/design-v2.md, docs/kimi-research/ or anything in .gitignore.
- Keep to Joe's rules in handoff.md (the public site shows sellers only; nothing reaches buyers before the owner's
  authority to sell is verified).

## Push to GitHub first, every time
1. Run the tests: `uv run pytest` (all must pass).
2. `git add <only the files you changed>`
3. `git commit -m "<what changed, in plain words>"`
4. `git push -u origin kimi/<short-topic>`
5. Open a pull request: `gh pr create --base main --fill`
6. Do NOT push to `main` directly and do not merge. Joe merges after review: every push to `main` redeploys the
   public demo at https://joechangaloha-sys.github.io/china-ma-match/.
7. Add a short note to handoff.md saying what you did and the PR link, in the same branch.

## Joe's standing language and visual instructions
- English and Chinese editions must have matching layouts and shared visual styling.
- Use the Japan IR Index-inspired institutional Wall Street style: navy, white,
  cool greys, serif headlines, fine rules and restrained controls. Use the shared palette.
- English pages are English-only and Chinese pages Chinese-only, including controls,
  notices, document content and downloads. Avoid cross-language fallback.
- Chinese finance copy must use a formal mainland investment-banking register,
  comparable to CICC, CITIC Securities and Guotai, without implying affiliation.
- Apply these rules to the main website and document/demo pages as ongoing standards.
  See docs/LANGUAGE_STYLE.md and docs/VISUAL_STYLE.md.
- When asked to show Chinese pages, open the actual Chinese live URLs and provide
  clear links and visual proof.
