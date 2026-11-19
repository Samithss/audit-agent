-- Supporting data for the guideline checks (synthetic; see scripts/generate_conduct_data.py)
CREATE TABLE IF NOT EXISTS audit.caller_numbers (
    contact_id text,
    caller_number text
);
CREATE TABLE IF NOT EXISTS audit.message_content (
    contact_id text,
    channel text,
    message_text text
);
CREATE TABLE IF NOT EXISTS audit.call_conduct_log (
    call_id text,
    account_id text,
    collector_id text,
    speaker text,
    utterance text,
    logged_by text
);
CREATE TABLE IF NOT EXISTS audit.field_visits (
    visit_id text,
    account_id text,
    collector_id text,
    visit_ts text,
    logged_in_app text,
    logged_ts text,
    outcome text,
    dues_disclosed_to_third_party text
);
CREATE TABLE IF NOT EXISTS audit.closures (
    closure_id text,
    account_id text,
    closure_date text,
    closure_type text,
    security_held text,
    security_release_date text
);
CREATE TABLE IF NOT EXISTS audit.penal_charges (
    charge_id text,
    account_id text,
    charge_date text,
    amount_in_default text,
    penal_charge_amount text,
    capitalised text,
    charged_on_penal text,
    reminder_contact_id text,
    reminder_states_penal_charge text
);
CREATE INDEX IF NOT EXISTS ix_caller_contact ON audit.caller_numbers (contact_id);
CREATE INDEX IF NOT EXISTS ix_msgcontent_contact ON audit.message_content (contact_id);
CREATE INDEX IF NOT EXISTS ix_conduct_call ON audit.call_conduct_log (call_id);
