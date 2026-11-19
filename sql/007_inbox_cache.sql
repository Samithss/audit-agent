-- Cache the list-view fields so the Gmail tab can render from the database
-- instead of re-querying Gmail on every refresh.
ALTER TABLE audit.inbox_runs ADD COLUMN IF NOT EXISTS snippet  text;
ALTER TABLE audit.inbox_runs ADD COLUMN IF NOT EXISTS has_pdf  boolean DEFAULT false;
