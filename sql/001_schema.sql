-- Audit evidence pack agent -- Postgres schema.
--
-- Design choice: every source table mirrors its CSV 1:1, EVERY column as TEXT,
-- matching pandas' current `pd.read_csv(..., dtype=str)` exactly. This is
-- deliberate, not an oversight -- the entire downstream pipeline (checks.py,
-- rules.py, decompose.py, pack.py, letter.py) was built and verified (100%
-- recall, 1.1% false-gap, real transcript labelling) against that exact dtype
-- behaviour. Storing native types and casting back risks subtle formatting
-- mismatches (e.g. "105725.0" vs "105725.00") that would silently break
-- string comparisons already proven correct. Native typing can be added later,
-- once this migration itself is proven stable -- not a blocker now.
--
-- agent/tools.py's _raw() is the ONLY thing that changes (CSV read -> SQL
-- query); every method built on top of it is untouched.
--
-- No PRIMARY KEY on the natural "ID" column of any source table, by design --
-- several of these CSVs have genuine, seeded duplicate rows that the Python
-- layer is specifically written to detect and handle (e.g. _contacts_all()'s
-- own dedup, which already produces "D4: N duplicate rows ignored"). A strict
-- PK here would reject rows that the proven pipeline is deliberately built to
-- see and act on. Plain indexes give the same query performance without that
-- risk. "our own" tables below (transcript_labels, runs, verdicts, gap_items)
-- are the opposite case -- we control every insert, so PKs there are correct.

CREATE SCHEMA IF NOT EXISTS audit;

-- D1 account master
CREATE TABLE IF NOT EXISTS audit.accounts (
    account_id      text PRIMARY KEY,
    lender_id       text,
    borrower_id     text,
    product         text,
    sanction_amount text,
    total_dues      text,
    dpd             text,
    bucket          text,
    disbursal_date  text,
    city            text,
    state           text,
    branch          text,
    legal_flag      text
);
CREATE INDEX IF NOT EXISTS ix_accounts_borrower ON audit.accounts (borrower_id);
CREATE INDEX IF NOT EXISTS ix_accounts_lender   ON audit.accounts (lender_id);

-- D4 contact history
CREATE TABLE IF NOT EXISTS audit.contact_log (
    contact_id        text,
    account_id        text,
    channel           text,
    direction         text,
    number_or_handle  text,
    contact_ts        text,
    template_id       text,
    collector_id      text,
    agency_id         text,
    disposition       text,
    duration_sec      text
);
CREATE INDEX IF NOT EXISTS ix_contact_account ON audit.contact_log (account_id);
CREATE INDEX IF NOT EXISTS ix_contact_id      ON audit.contact_log (contact_id);

-- D5 call transcripts (one row per speaker turn)
CREATE TABLE IF NOT EXISTS audit.transcripts (
    call_id         text,
    account_id      text,
    turn_no         text,
    speaker         text,
    text            text,
    language        text,
    asr_confidence  text,
    turn_start_ts   text
);
CREATE INDEX IF NOT EXISTS ix_transcripts_account ON audit.transcripts (account_id);
CREATE INDEX IF NOT EXISTS ix_transcripts_call    ON audit.transcripts (call_id, turn_no);

-- D10 consent registry
CREATE TABLE IF NOT EXISTS audit.consent (
    consent_id      text,
    borrower_id     text,
    channel         text,
    consent_status  text,
    captured_at     text,
    opt_out_at      text,
    consent_source  text,
    dnd_status      text
);
CREATE INDEX IF NOT EXISTS ix_consent_borrower ON audit.consent (borrower_id);
CREATE INDEX IF NOT EXISTS ix_consent_id        ON audit.consent (consent_id);

-- D11 template registry
CREATE TABLE IF NOT EXISTS audit.templates (
    template_id      text,
    channel          text,
    language         text,
    template_name    text,
    registered_text  text,
    approval_status  text,
    approved_date    text,
    registered_by    text
);
CREATE INDEX IF NOT EXISTS ix_templates_id ON audit.templates (template_id);

-- D12 policy rules
CREATE TABLE IF NOT EXISTS audit.policy (
    rule_id         text,
    document_name   text,
    lender_id       text,
    rule_type       text,
    channel         text,
    parameter       text,
    value           text,
    unit            text,
    effective_from  text,
    effective_to    text,
    clause_text     text
);
CREATE INDEX IF NOT EXISTS ix_policy_lender ON audit.policy (lender_id);
CREATE INDEX IF NOT EXISTS ix_policy_id     ON audit.policy (rule_id);

-- Notice dispatch history
CREATE TABLE IF NOT EXISTS audit.notices (
    notice_id       text,
    account_id      text,
    notice_type     text,
    trigger_event   text,
    trigger_date    text,
    dispatch_date   text,
    dispatch_mode   text,
    tracking_ref    text,
    delivery_status text,
    service_date    text
);
CREATE INDEX IF NOT EXISTS ix_notices_account ON audit.notices (account_id);
CREATE INDEX IF NOT EXISTS ix_notices_id      ON audit.notices (notice_id);

-- Holiday calendar
CREATE TABLE IF NOT EXISTS audit.holidays (
    date          text,
    holiday_name  text,
    scope         text,
    state         text
);

-- Collector roster
CREATE TABLE IF NOT EXISTS audit.roster (
    collector_id    text,
    collector_name  text,
    agency_id       text,
    agency_name     text,
    joining_date    text,
    status          text
);
CREATE INDEX IF NOT EXISTS ix_roster_id ON audit.roster (collector_id);

-- Certification register
CREATE TABLE IF NOT EXISTS audit.certificates (
    cert_id             text,
    collector_id        text,
    cert_type           text,
    certificate_number  text,
    valid_from          text,
    valid_to            text
);
CREATE INDEX IF NOT EXISTS ix_certificates_collector ON audit.certificates (collector_id);
CREATE INDEX IF NOT EXISTS ix_certificates_id        ON audit.certificates (cert_id);

-- ---------------------------------------------------------------------------
-- Our own generated data -- production audit trail, not CSV-sourced.
-- ---------------------------------------------------------------------------

-- Transcript labels (replaces data/cache/transcript_labels.json). Still
-- Option B: a call is labelled once, the first time a real request needs it,
-- and never re-sent to the model again.
CREATE TABLE IF NOT EXISTS audit.transcript_labels (
    call_id      text PRIMARY KEY,
    outcome      text NOT NULL,
    cited_turns  jsonb NOT NULL DEFAULT '[]',
    detail       text,
    labelled_at  timestamptz NOT NULL DEFAULT now()
);

-- One row per decompose() call. request_id is NOT the primary key -- the same
-- request can be re-decomposed over time (re-audits, prompt fixes), and every
-- run is kept, not overwritten.
CREATE TABLE IF NOT EXISTS audit.runs (
    run_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      text NOT NULL,
    lender_id       text,
    period_from     date,
    period_to       date,
    sample_file     text,
    source          text,
    checks          jsonb NOT NULL,
    unsupported     jsonb NOT NULL DEFAULT '[]',
    severity_order  jsonb NOT NULL,
    severity_rules  jsonb NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_runs_request ON audit.runs (request_id);

-- Verdicts and gap items, keyed by run_id -- same columns as verdicts.csv /
-- gap_items.csv (run_checks.py still writes those CSVs too; this is the
-- queryable, historical copy).
CREATE TABLE IF NOT EXISTS audit.verdicts (
    run_id                   uuid NOT NULL REFERENCES audit.runs(run_id),
    request_id               text NOT NULL,
    account_id               text NOT NULL,
    check_id                 text NOT NULL,
    check_type               text NOT NULL,
    status                   text NOT NULL,
    severity                 text,
    items_tested             integer,
    gap_items                integer,
    gap_types                text,
    cannot_determine_reasons text,
    evidence_count           integer,
    evidence_ids             text,
    rule_refs                text,
    PRIMARY KEY (run_id, account_id, check_id)
);
CREATE INDEX IF NOT EXISTS ix_verdicts_request ON audit.verdicts (request_id);

CREATE TABLE IF NOT EXISTS audit.gap_items (
    gap_item_id  text NOT NULL,
    run_id       uuid NOT NULL REFERENCES audit.runs(run_id),
    request_id   text NOT NULL,
    account_id   text NOT NULL,
    check_id     text NOT NULL,
    check_type   text NOT NULL,
    gap_type     text NOT NULL,
    severity     text,
    record_ids   text,
    detail       text,
    PRIMARY KEY (run_id, gap_item_id)
);
CREATE INDEX IF NOT EXISTS ix_gap_items_request ON audit.gap_items (request_id);
