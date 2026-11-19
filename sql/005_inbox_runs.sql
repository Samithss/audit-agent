-- Step 10 follow-up: persistent memory for the Gmail inbox tab. Without this,
-- "Refresh inbox" re-runs the Gmail search fresh every time and a message you
-- already ran (or replied to) looks identical to one you've never touched.

CREATE TABLE IF NOT EXISTS audit.inbox_runs (
    message_id        text PRIMARY KEY,
    thread_id         text,
    subject           text,
    from_address      text,
    received_at       text,
    status            text NOT NULL DEFAULT 'NEW',   -- NEW / PROCESSING / NEEDS_REVIEW / ERROR / REPLIED
    is_audit_request  boolean,                        -- Prism's classification -- informational, never filters the list
    confidence        numeric,
    request_id        text,                           -- set once a run starts (GMAIL-<message_id>)
    error             text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
