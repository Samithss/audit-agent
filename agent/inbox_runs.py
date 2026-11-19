"""
Step 10 follow-up -- persistent status for the Gmail inbox tab (audit.inbox_runs).

Without this, GET /api/inbox/messages re-runs the Gmail search fresh every
call and a message already processed looks identical to one never touched.
This module is the memory: every message Gmail returns gets a row here,
and its status only ever moves forward through the one lifecycle:

    NEW -> PROCESSING -> NEEDS_REVIEW -> REPLIED
                      \-> ERROR

Classification (is_audit_request / confidence) is informational only -- it
is shown in the UI as a caption, never used to filter or hide a message. A
low-confidence email still shows up; a human decides whether to run it.
"""
from . import db
from .llm import call_decision


def sync_new_messages(candidates: list[dict]) -> None:
    """candidates: list_candidate_messages()'s output. Inserts a NEW row (with
    a Prism confidence score) for any message_id not already tracked; never
    touches a row that already exists -- status only moves forward elsewhere."""
    if not candidates:
        return
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT message_id FROM audit.inbox_runs WHERE message_id = ANY(%s)",
                    ([c["message_id"] for c in candidates],))
        known = {r["message_id"] for r in cur.fetchall()}
        for c in candidates:
            if c["message_id"] in known:
                continue
            is_audit_request, confidence = _classify(c["subject"], c["snippet"])
            cur.execute(
                """INSERT INTO audit.inbox_runs
                   (message_id, thread_id, subject, from_address, received_at,
                    status, is_audit_request, confidence)
                   VALUES (%s, %s, %s, %s, %s, 'NEW', %s, %s)
                   ON CONFLICT (message_id) DO NOTHING""",
                (c["message_id"], c.get("thread_id"), c["subject"], c["from"], c["date"],
                 is_audit_request, confidence),
            )
        conn.commit()


def _classify(subject: str, snippet: str) -> tuple:
    """One Prism call: is this plausibly a real audit/compliance request?
    Never raises into the caller -- a classification hiccup should not stop
    the message from showing up in the list, just with no score attached."""
    try:
        r = call_decision(
            state=f'Email subject: "{subject}". Snippet: "{snippet}".',
            questions={"is_audit_request": {
                "type": "noul",
                "instructions": "True if this email is a genuine audit or compliance evidence "
                                 "request from a lender, false otherwise.",
            }},
        )
        confidence = r["answers"]["is_audit_request"]["noul"]
        return confidence >= 0.5, confidence
    except Exception:
        return None, None


def list_statuses(message_ids: list[str]) -> dict:
    """message_id -> full row, for merging onto the live Gmail candidate list."""
    if not message_ids:
        return {}
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM audit.inbox_runs WHERE message_id = ANY(%s)", (message_ids,))
        return {r["message_id"]: r for r in cur.fetchall()}


def mark_processing(message_id: str, request_id: str) -> None:
    _update(message_id, status="PROCESSING", request_id=request_id, error=None)


def mark_needs_review(message_id: str) -> None:
    _update(message_id, status="NEEDS_REVIEW")


def mark_error(message_id: str, error: str) -> None:
    _update(message_id, status="ERROR", error=error)


def mark_replied(message_id: str) -> None:
    _update(message_id, status="REPLIED")


def _update(message_id: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = %s" for k in fields) + ", updated_at = now()"
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE audit.inbox_runs SET {cols} WHERE message_id = %s",
                    (*fields.values(), message_id))
        conn.commit()
