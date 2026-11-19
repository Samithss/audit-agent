"""
LLM transcript reviewer (Step 6) — replaces the keyword baseline in transcript_rules.py.

OPTION B: label a call the first time it is actually needed by a real audit request
(verification_before_disclosure already only looks at the sampled accounts' calls —
it never touches the other ~2,000 accounts in the book). Once labelled, a call_id is
never sent to the model again — the result is cached to disk forever.

Output shape matches transcript_rules.analyze_call() exactly, so checks.py barely
changes: (outcome, cited_turns, detail) per call_id.

Uses Sarvam's conversational model (sarvam-105b-conversations) rather than a
generic reasoning model -- these transcripts are Hindi/English/regional
code-mixed call CONVERSATIONS, which is that model's specialty.

Cache lives in Postgres (audit.transcript_labels), not a JSON file -- same
Option B semantics (label once, ever, per call_id), just a real table so the
label history is queryable and survives across containers/deployments.
"""
from pydantic import BaseModel
from typing import Literal

from psycopg.types.json import Json

from . import db
from .llm import call_conversational, extract_json

BATCH_SIZE = 20  # transcripts per LLM call

OUTCOMES = (
    "ok",
    "disclosure_before_verification",
    "disclosure_after_failed_verification",
    "third_party_disclosure",
)


class CallLabel(BaseModel):
    call_id: str
    outcome: Literal[OUTCOMES]
    cited_turns: list[int]
    detail: str


class BatchLabels(BaseModel):
    calls: list[CallLabel]


SYSTEM_PROMPT = """You review debt-collection call transcripts for one thing only:
did the agent verify the borrower's identity BEFORE disclosing any dues amount?

For each call, decide one outcome:
- ok: no amount was disclosed, OR verification happened before the amount was disclosed
- disclosure_before_verification: an amount was disclosed and verification never happened first
- disclosure_after_failed_verification: verification was attempted and FAILED, then an amount was disclosed anyway
- third_party_disclosure: an amount or dues figure was ACTUALLY STATED to someone who is not the borrower, before or instead of verification

CRITICAL -- the most common mistake: a wrong-number call where the agent confirms
it's the wrong person and ends the call WITHOUT mentioning any amount is "ok", not
third_party_disclosure. "Wrong number" alone is not a violation. Only classify as
third_party_disclosure if a specific amount or the fact of a debt/dues was actually
spoken to that wrong person. If you cannot point to the exact words where an amount
or dues was mentioned, the outcome is "ok".

Example -- this is "ok", NOT third_party_disclosure, because no amount is ever mentioned:
  turn 1 [AGENT]: Good morning, am I speaking with Vikram Banerjee?
  turn 2 [CUSTOMER]: No, there is no Vikram Banerjee here. Wrong number.
  turn 3 [AGENT]: Apologies for the inconvenience. We will update our records. Thank you.
  -> outcome: ok (nothing about dues or an amount was ever said; confirming a wrong
     number and politely ending the call is correct behaviour, not a gap)

cited_turns: the turn_no values that prove your outcome (the disclosure turn, the
verification turn, the wrong-party turn — whichever apply). Must be real turn numbers
from the transcript you were given for that call. Never cite a turn as proof of
disclosure unless an amount or dues is literally stated in that turn's text.

detail: one short sentence, e.g. "Verified at turn 4; amount disclosed at turn 6."

Transcripts are code-mixed Hindi/English/regional language. Judge intent, not exact
keywords.

Respond with ONLY a JSON object of this exact shape, no other text:
{"calls": [{"call_id": "...", "outcome": "...", "cited_turns": [1, 2], "detail": "..."}]}"""


def _load_cache(call_ids) -> dict:
    """Only the labels we might need for THIS request, not the whole table."""
    ids = list(call_ids)
    if not ids:
        return {}
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT call_id, outcome, cited_turns, detail FROM audit.transcript_labels WHERE call_id = ANY(%s)",
            (ids,),
        )
        rows = cur.fetchall()
    return {r["call_id"]: [r["outcome"], r["cited_turns"], r["detail"]] for r in rows}


def _save_new_labels(new_labels: dict) -> None:
    """INSERT only what's new. ON CONFLICT DO NOTHING keeps this idempotent --
    a call_id is labelled once, ever, matching Option B exactly."""
    if not new_labels:
        return
    rows = [(cid, outcome, Json(turns), detail) for cid, (outcome, turns, detail) in new_labels.items()]
    with db.connect() as conn, conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO audit.transcript_labels (call_id, outcome, cited_turns, detail) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (call_id) DO NOTHING",
            rows,
        )
        conn.commit()


def _format_call(call_id, turns_df) -> str:
    lines = [f"CALL {call_id}:"]
    for r in turns_df.itertuples():
        lines.append(f"  turn {r.turn_no} [{r.speaker}]: {r.text}")
    return "\n".join(lines)


def _label_batch(call_ids: list[str], tx_by: dict) -> dict:
    prompt = "\n\n".join(_format_call(cid, tx_by[cid]) for cid in call_ids)
    raw = call_conversational([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    parsed = BatchLabels.model_validate(extract_json(raw))
    requested = set(call_ids)  # only the call_ids we actually put in THIS batch's prompt
    out = {}
    for c in parsed.calls:
        if c.call_id not in requested:
            # Hallucinated or mistyped call_id -- never seen in this batch's prompt.
            # Drop it rather than crash; it simply stays unlabelled and gets retried
            # on a future run (it's not written to cache).
            print(f"  warning: model returned unknown call_id {c.call_id!r}, ignoring")
            continue
        real_turns = set(tx_by[c.call_id]["turn_no"].astype(int))
        cited = [t for t in c.cited_turns if t in real_turns]  # drop hallucinated turn numbers
        out[c.call_id] = [c.outcome, cited, c.detail]
    return out


def label_calls(tx_by: dict) -> dict:
    """tx_by: {call_id: DataFrame of that call's turns}, already scoped to the
    accounts in THIS request only. Returns {call_id: (outcome, cited_turns, detail)}
    -- missing a key entirely means the model could never be made to echo that
    call_id correctly; checks.py treats that the same as a missing transcript
    (CANNOT_DETERMINE), never a silent guess."""
    cache = _load_cache(tx_by.keys())
    missing = [cid for cid in tx_by if cid not in cache]

    new_labels = {}
    for i in range(0, len(missing), BATCH_SIZE):
        batch = missing[i:i + BATCH_SIZE]
        new_labels.update(_label_batch(batch, tx_by))

    # Retry anything still missing ALONE (batch of 1) -- a crowded batch is where
    # the model mixes up similar-looking call_ids; alone, there's nothing to confuse
    # it with.
    still_missing = [cid for cid in missing if cid not in new_labels]
    for cid in still_missing:
        new_labels.update(_label_batch([cid], tx_by))

    _save_new_labels(new_labels)
    cache.update(new_labels)

    return {cid: tuple(cache[cid]) for cid in tx_by if cid in cache}
