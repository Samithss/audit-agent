-- Guideline catalogue shown in the "Select your own" dropdown.
-- Each testable guideline maps to one of the agent's check types.
CREATE TABLE IF NOT EXISTS audit.guidelines (
    guideline_id  text PRIMARY KEY,
    category      text,   -- Voice | Digital | Notice | Field | Settlement | Payment
    title         text,
    rule_text     text,
    check_type    text,   -- empty when not testable yet
    params_json   text,
    source_type   text,   -- RBI_VERIFIED | LENDER_POLICY | UNVERIFIED
    source_ref    text,
    testable      text,   -- Y | N
    needs         text    -- what is missing when testable = N
);
