# Build status -- CO-04 Audit evidence pack agent

Team: agent.isAwake() -- CreditNirvana Agentathon, Nov 19-20 2026.

This file is the "what's actually done" record. `README.md` has the run instructions.

## TL;DR

All 9 build steps are done. The pipeline runs end to end against **Postgres**
(not CSV), behind a **FastAPI** backend and a **React** frontend (not
Streamlit -- that app still exists but is superseded). LLM calls go through
**Sarvam's gateway** (Deepseek for reasoning, Sarvam's own model for
conversational transcript review, Sarvam Prism for decision scoring), not
Anthropic.

Measured on REQ-01/02/03 against the synthetic ground truth:

| metric | result | target |
|---|---|---|
| gap recall | 100.0% | >= 95% |
| false gap rate | 1.7% | < 5% |
| unsupported claims | 0 | 0 |
| severity accuracy | 100.0% | -- |
| status accuracy | 99.9% | -- |

## What changed from the original plan, and why

The repo started as a CSV + pandas + DuckDB engine with a Streamlit demo in
mind. Two explicit pivots since:

1. **LLM provider**: swapped from Anthropic to Sarvam's gateway, per
   instruction from Ambuj Pratap Jain -- Deepseek (`deepseekv4.1-flash-1017`)
   for generic reasoning (request decomposition, letter drafting), Sarvam
   (`sarvam-105b-conversations`) for conversational work (transcript
   labelling), Sarvam Prism (`sarvam-prism`, `/v2/systemone`) wired up for
   structured decision scoring.
2. **Infra + UI**: "we need docker postgre that is must and ui need to
   improve and everything will move to prod dont think of just demo" ->
   Postgres in Docker replaced the CSV/DuckDB data layer, and React + FastAPI
   replaced the Streamlit demo as the primary UI.

## Step-by-step

- [x] **Steps 1-4** -- data layer, D12 rules engine, the 8 deterministic
  checks, `Verdict`/`severity` grading, `eval/score.py`. Unchanged by any of
  the above -- this is the part that was already proven and is never
  rewritten, only re-pointed at a new data source.
- [x] **Step 5** -- `agent/decompose.py`: Deepseek (via Sarvam) turns request
  text/PDF into a `checks.json`. Closed catalogue (`CHECK_TYPES` from
  `checks.py`) -- anything it can't map goes to `unsupported`, reported, never
  dropped. Verbatim-quote check on every extracted clause, whitespace-normalized
  so line-wrap isn't mistaken for paraphrasing.
- [x] **Step 6** -- `agent/transcript_review.py`: Sarvam's conversational
  model labels each call transcript (`ok` / `disclosure_before_verification` /
  `disclosure_after_failed_verification` / `third_party_disclosure`), one call
  ever per `call_id` (Option B caching), now cached in `audit.transcript_labels`
  (Postgres) instead of a JSON file. Includes a hand-fixed counter-example for
  a systematic "wrong number -> false disclosure" hallucination found during
  testing (false-gap rate dropped from 24-57% to ~1-3% after the fix).
- [x] **Step 7** -- `pack.py` (gap_report.xlsx + request_interpretation.md),
  `letter.py` (drafts a response letter from a summary only, never raw account
  rows), `validator.py` (softening language, unmasked phone numbers, DRAFT
  disclaimer, gap/unsupported mention checks). `draft_and_validate()` retries
  once on validator failure, then ships flagged `needs_human_review` rather
  than silently failing.
- [x] **Step 8** -- original Streamlit demo (`app.py`). Still in the repo and
  runnable, but **superseded** by Step 9 as the primary UI.
- [x] **Step 9** -- production path:
  - `docker-compose.yml` + `sql/001_schema.sql`: Postgres 16, one schema
    (`audit`), 10 source-mirror tables (all-TEXT columns, no PK on the natural
    ID -- the data has genuine seeded duplicates the Python layer is built to
    detect) + 4 generated-data tables with real PKs (`transcript_labels`,
    `runs`, `verdicts`, `gap_items`).
  - `scripts/load_to_postgres.py`: idempotent CSV -> Postgres loader
    (`TRUNCATE` + `COPY FROM STDIN`).
  - `agent/tools.py`: `_raw()` is the *only* method that changed -- CSV read
    became a Postgres `SELECT *`. Every method built on top of it is
    byte-identical in behavior; proven by re-running REQ-01/02/03 and getting
    the exact same per-check EVIDENCED/GAP/NOT_APPLICABLE counts as the CSV
    era.
  - `agent/run_checks.py`: additively persists every run to
    `audit.runs`/`verdicts`/`gap_items` (wrapped in try/except -- a DB hiccup
    never breaks the CSV output, which stays the source of truth for
    `pack.py`/`letter.py`/`eval/score.py`).
  - `api/main.py` (FastAPI): wraps decompose -> run_checks -> pack -> letter
    as background jobs keyed by `request_id`. Endpoints: request catalogue,
    raw text, start run, poll status/log, full result (checks + summary +
    score), filtered gaps, file downloads.
  - `frontend/` (React + Vite): same 5-pane flow as the Streamlit app --
    request picker, live run log, checks/unsupported, run summary, filterable
    gap table with a click-to-inspect evidence drawer, scorecard + letter +
    downloads. Dark/light theme aware, verified mobile-responsive.

## Verified live (this session)

- `pytest -q` -- 7 passed, no regression from the CSV -> Postgres swap.
- REQ-01/02/03 run against Postgres with results byte-identical to the
  earlier CSV-proven run.
- Postgres persistence independently queried: `audit.runs` (3 rows),
  `audit.verdicts` (grouped by status -- matches each run's printed summary),
  `audit.gap_items` (one row per finding).
- FastAPI: all 7 endpoints exercised via curl against a real run (REQ-01) --
  202 on start, log progression on poll, correct `result`/`gaps`/3 downloads.
- React: triggered a real run from the browser, watched the log stream live,
  confirmed every pane rendered correctly, clicked a gap row and confirmed the
  evidence drawer showed the exact record, confirmed scorecard metrics and
  download links, confirmed no console errors, found and fixed one real
  mobile-layout bug (summary table caused horizontal overflow at 375px).

## Known caveats

- The FastAPI job store (`_jobs` in `api/main.py`) is in-process memory -- a
  restart loses in-flight run status (not run *data*; `out/<REQ>/` and
  Postgres already hold that). Fine for one backend process; would need a
  shared store (Postgres row, Redis) behind more than one worker.
- `letter.draft_and_validate()` can still return `needs_human_review: true`
  on either draft attempt -- this is by design (validator catches it, UI
  surfaces it), not a bug, but it means a run isn't guaranteed a clean letter
  on the first try.
- Minor cosmetic nit, not fixed: the letter sometimes phrases CALL_FREQUENCY
  severity as "the lowest of the three severity tiers" instead of plainly
  "MINOR". Low priority.
- `.env` holds the real Sarvam key and is gitignored; `.env.example` is the
  template committed instead.
