# Build status -- CO-04 Audit evidence pack agent

Team: agent.isAwake() -- CreditNirvana Agentathon, Nov 19-20 2026.

This file is the "what's actually done" record. `README.md` has the run instructions.

## TL;DR

All 10 build steps are done. The pipeline runs end to end against **Postgres**
(not CSV), behind a **FastAPI** backend and a **React** frontend (not
Streamlit -- that app still exists but is superseded). LLM calls go through
**Sarvam's gateway** (Deepseek for reasoning, Sarvam's own model for
conversational transcript review, Sarvam Prism for decision scoring), not
Anthropic. Beyond the 3 canned demo requests, you can now run the agent
against an **uploaded PDF or pasted email text**, or against **real emails
pulled from a connected Gmail inbox** (OAuth, read-only).

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
- [x] **Step 10** -- three ways in, one pipeline:
  - **Upload your own**: `POST /api/custom/run` accepts a PDF or pasted text
    plus which lender's sample to test against (the dataset only has real
    account data for 3 lenders, independent of what the uploaded letter
    says). Generates its own `CUSTOM-xxxxxxxx` request_id so it never
    collides with the sample requests.
  - **Gmail inbox**: `agent/gmail_client.py` + `/api/inbox/*` -- OAuth
    (`gmail.readonly` + `gmail.send`), lists candidate audit-request emails
    by subject match, a human picks one from the UI and runs the agent on it
    (`GMAIL-<message_id>`). The refresh token lives in `audit.oauth_tokens`,
    one row, one mailbox. Needs a Google Cloud OAuth client the operator
    creates themselves -- see README.md "Gmail inbox setup". Fully coded;
    not live-tested end-to-end in this session since that requires a real
    Google OAuth client and consent grant (can't be done without the
    operator's own Google login).
  - **Sending the reply back**: `POST /api/requests/{id}/send-reply`
    (`gmail_client.send_reply`), reachable ONLY from a Gmail-sourced run and
    ONLY via an explicit button click in the new `ReplyPane` -- nothing in
    this codebase ever calls it automatically. The recipient, subject, and
    thread/`In-Reply-To` headers are re-fetched from the real Gmail message
    at send time (`get_message_meta`), never trusted from the browser. The
    UI shows the recipient, lets the human edit the letter text before
    sending, requires an extra "I've reviewed this" checkbox when the
    validator flagged `needs_human_review`, and a native browser confirm on
    top of that. A reply can only be sent once per request_id
    (`_jobs[id]["replied"]` guards against a double-send). Deliberately
    manual-only -- see the design discussion in this session's transcript:
    auto-sending an unreviewed compliance letter to a real lender is a real
    legal/reputational risk, not a UX nicety to skip.
  - UI: added a 3-tab picker (Sample requests / Upload your own / Gmail
    inbox) and a visual pass (tab bar, card shadows, consistent
    field/button styling, pill badges) across the React frontend.
  - **Bug found and fixed while testing this**: `decompose.py` could return
    an empty `severity_order`/`severity_rules` when the source request had
    no severity/grading section of its own (realistic for a short pasted
    email) -- `severity.grade()` then raised "no rule matches" and the run
    crashed. Fixed with a code-level backstop
    (`_fill_severity_defaults` in `agent/decompose.py`): every check_type
    actually extracted is guaranteed at least one severity rule, defaulting
    sensibly (consent/verification/certification -> CRITICAL, template/
    hours/recording/notice -> MAJOR, frequency -> MINOR) when the model
    didn't write one itself. A check_type the model DID grade (even
    partially, with `gap_types`) is left untouched.

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
- Step 10 upload flow: tested via curl (PDF upload, pasted text, missing
  file+text -> 400, unknown lender_id -> 400) and live in the browser (both
  the PDF and paste-text paths, including the full UI transition from
  "Running..." to rendered Checks/Summary/Gaps/Scorecard panes without a page
  reload, driven entirely by the frontend's own status polling). The
  severity-defaults bug above was caught by this testing, not invented --
  the minimal one-sentence pasted request is a realistic case, not an edge
  case contrived to find a bug.
- Step 10 Gmail flow: `/api/inbox/status` confirmed to correctly report
  `{"configured": false}` with no Google credentials set, and the UI
  correctly shows the "not configured" message on the Gmail inbox tab. The
  OAuth exchange / message listing / message-run code paths are written
  against the real Gmail API client library but could not be exercised
  end-to-end without a real Google OAuth client and a human consent grant.

## Step 11 -- Gmail inbox: persistent status, not just a live search

Previously, "Refresh inbox" re-ran the Gmail search fresh every time -- an
email already run, or already replied to, looked identical to one never
touched. `agent/inbox_runs.py` + `audit.inbox_runs` (`sql/005_inbox_runs.sql`)
fix that with one lifecycle per message:

```
NEW -> PROCESSING -> NEEDS_REVIEW -> REPLIED
                  \-> ERROR
```

- `GET /api/inbox/messages` now inserts a `NEW` row (with a Prism confidence
  score) for anything not seen before, and returns the persisted status for
  anything already tracked -- `sync_new_messages()` never re-classifies or
  duplicates a row on a later refresh (verified against the real connected
  mailbox: `created_at == updated_at` held after a second refresh).
- The Prism call (`sarvam-prism` / `/v2/systemone`) had never actually been
  exercised before this -- its request shape was discovered by iterating on
  real 422 errors from the live API, not guessed: a question needs
  `{"type": "noul", "instructions": "..."}`, returning a 0-1 probability
  under `answers.<key>.noul`. Confidence is purely informational -- it's
  shown as a caption in the UI, never filters or hides a message. Verified
  live: a real audit-request email scored 71.8%, an unrelated email scored
  3.3%, and on the actual connected mailbox, a GitHub notification whose repo
  name happens to contain "audit" (matching the coarse keyword search) was
  correctly scored 3.3% likely to be real.
- `start_inbox_run` flips to `PROCESSING`; `_execute()`'s existing
  success/error branches flip to `NEEDS_REVIEW`/`ERROR` (one `if
  request_id.startswith("GMAIL-")` each, no new parameters threaded through
  the generic pipeline function); `/send-reply` flips to `REPLIED`.
- UI: each inbox row now shows a status chip and the confidence caption;
  clicking a `NEEDS_REVIEW`/`ERROR`/`REPLIED` row jumps straight to that run's
  result instead of needing to remember which account list/dates were used.
- Still manual-start, per the earlier decision: reaching `NEW` never
  auto-triggers a run. A human still clicks "Run agent on this email."

## Parallel work landed from likhithg-png/audit-agent (synced into this branch)

likhith's team (with their own Claude Code session) independently built
almost exactly the RBI-guideline-driven check expansion discussed in this
session: a guideline catalogue (`audit.guidelines`, 16 entries, each labeled
`RBI_VERIFIED`/`LENDER_POLICY`/`UNVERIFIED` with its source) and 6 new check
types -- `CALLER_NUMBER_SERIES`, `MESSAGE_CONTENT`, `CALL_CONDUCT`,
`FIELD_VISIT`, `SECURITY_RELEASE`, `PENAL_CHARGES` -- with real synthetic
data and ground truth. Notably, the harassment/abusive-language check
(`CALL_CONDUCT`) was built as deterministic regex + a QA-logged conduct
table rather than an LLM call, more consistent with this project's actual
"deterministic code decides verdicts" design than the LLM-based version
proposed earlier in this session. Rebased cleanly; all data loaded into
Postgres; verified one new check live end-to-end (real seeded harassment
language caught with correct citations). Not yet done: these 6 checks aren't
wired into `eval/score.py`'s recall/false-gap-rate scoring yet, and the
`DND_COMPLIANCE`/agent-background-verification checks discussed earlier in
this session still aren't built.

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
