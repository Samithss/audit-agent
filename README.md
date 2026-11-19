# Audit Evidence Pack Agent (CO-04)

For each audit request, the agent returns a verdict per account and check: EVIDENCED, GAP, CANNOT_DETERMINE or NOT_APPLICABLE. Every verdict cites records, and gaps are graded on the request's own severity scale.

Design: **the LLM plans and writes; deterministic code decides verdicts.**

## Setup (Ubuntu)

Run once:
```bash
cd ~/Desktop/audit-agent
python3 -m venv .venv
```

Run in every new terminal:
```bash
source .venv/bin/activate
```

Install the dependencies:
```bash
pip install -r requirements.txt
```

## Run

Run the checks for REQ-01 to REQ-03 using `eval/hand_checks/*.json`, writing to `out/<REQ>/`:
```bash
python -m agent.run_checks --all
```

Score `out/` against `data/ground_truth/`:
```bash
python -m eval.score
```

Or run the checks and score in one go:
```bash
python -m eval.score --run
```

Run the trap unit tests:
```bash
pytest -q
```

Each request writes three files to `out/<REQ>/`:
- `verdicts.csv`: one row per account and check, with evidence IDs and rule references.
- `gap_items.csv`: one row per gap (never merged), with record IDs and severity.
- `summary.csv`: counts per check and status.

## Layout
```
config/source_registry.yaml   sources, keys, and the time zone of every timestamp (D4 = IST; D5, D10 = UTC)
agent/tools.py                read-only evidence tools: UTC conversion, collector-ID normalization, de-duplication
agent/rules.py                D12 rules (effective dates, strictest applies) and the business-day calendar
agent/verdict.py              Verdict class: EVIDENCED without citations raises an error
agent/checks.py               the 8 deterministic checks
agent/transcript_rules.py     temporary keyword transcript analyzer (an LLM reviewer replaces it in step 6)
agent/severity.py             grades gaps on the request's scale
agent/run_checks.py           runner for stages 3-5
eval/hand_checks/REQ-0X.json  hand-written checks.json (what the LLM decomposer must produce)
eval/score.py                 recall, false-gap rate, unsupported claims, severity accuracy
data/                         synthetic data and ground truth (regenerate: python scripts/generate_data.py)
```

## Status
- [x] Steps 1-4: data layer, rules, 8 checks, verdicts, severity, scorer. On the 3 public requests, the hand-written checks score 100% recall, 0% false gaps and 0 unsupported claims.
  - Caveat: the synthetic answer key applies the same rule readings as this engine, so 100% here proves the code is wired correctly, not that it is robust. The organizers' real data will differ, so re-check every assumption in `source_registry.yaml`.
- [ ] Step 5, `agent/decompose.py`: the LLM turns request text or PDF into checks.json. Target: match `eval/hand_checks`.
- [ ] Step 6, `agent/transcript_review.py`: the LLM finds the verification and disclosure turns with exact quotes; code verifies the quotes.
- [ ] Step 7:
  - `pack.py`: index.html, extracts, record references.
  - `letter.py`: the draft letter.
  - `validator.py`: no uncited claims, counts reconcile, no softening words, PII masked.
- [ ] Step 8: Streamlit demo and a 300-account timing run.
