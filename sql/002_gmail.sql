-- Gmail OAuth token storage (Step 10). Single-tenant, single-row-per-provider
-- design -- this app connects ONE mailbox (the compliance team's shared inbox
-- or the operator's own), not per-end-user accounts. refresh_token is the
-- long-lived credential; access_token/expiry are refreshed in place by
-- agent/gmail_client.py whenever they expire.

CREATE TABLE IF NOT EXISTS audit.oauth_tokens (
    provider      text PRIMARY KEY,
    refresh_token text NOT NULL,
    access_token  text,
    expiry        timestamptz,
    scope         text,
    updated_at    timestamptz NOT NULL DEFAULT now()
);
