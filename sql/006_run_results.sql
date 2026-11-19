-- The drafted letter + who to reply to, so a finished run survives an API
-- restart. Everything else /result returns is already on disk under
-- out/<request_id>/ (checks.json, summary.csv, verdicts.csv, gap_items.csv);
-- only these two things lived purely in api/main.py's in-memory _jobs dict.
--
-- Without this, a Gmail message that reached NEEDS_REVIEW became unreachable
-- the moment uvicorn reloaded: the status row said "waiting for a human" but
-- the draft it referred to was gone, so the reply could never be sent.

CREATE TABLE IF NOT EXISTS audit.run_results (
    request_id          text PRIMARY KEY,
    letter_text         text,
    needs_human_review  boolean,
    validation          jsonb,
    reply_to            text,          -- full From header of the originating email
    reply_subject       text,
    reply_thread_id     text,
    reply_in_reply_to   text,          -- the original Message-Id, for threading
    replied             boolean NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);
