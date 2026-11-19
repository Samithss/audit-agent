"""
Step 5 — turn a raw audit request's text into a checks.json (same shape as
eval/hand_checks/REQ-0X.json), using Deepseek (generic reasoning) via Sarvam.

Closed catalogue: the model classifies each clause into one of the check types
already wired in agent/checks.py -- it never invents a new one. Anything it can't
map goes into "unsupported" (reported, never silently dropped). checks.json still
only has a "checks" list for run_checks.py to execute, exactly as today --
"unsupported" is an extra key run_checks.py ignores, meant for pack.py later.

request_id / lender_id / period / sample_file are NOT guessed by the model -- in
real operation you already know these from how the request arrived (sender,
attachment name), the same way the hand-written checks.json files carry them
separately from the checks list. The model's only job is: read the prose, produce
checks + severity rules.
"""
import json
import re

from pydantic import BaseModel
from typing import Optional

from .checks import CHECKS
from .llm import call_reasoning, extract_json

CHECK_TYPES = tuple(CHECKS.keys())

# The exact gap_type strings the check engine emits, per check_type. A severity
# rule's "gap_types" field is matched literally against these at grading time
# (agent/severity.py) -- a rule using any other string silently never matches and
# severity.grade() raises. Keep this in sync with the Finding(...) calls in checks.py.
GAP_TYPES_BY_CHECK = {
    "CONSENT_BEFORE_CONTACT": ["no_consent_record", "message_after_opt_out", "consent_after_message"],
    "TEMPLATE_APPROVED": ["template_not_registered", "template_channel_mismatch",
                          "template_not_approved", "template_used_before_approval"],
    "CALL_HOURS": ["outside_calling_hours"],
    "CALL_FREQUENCY": ["daily_cap_exceeded", "weekly_cap_exceeded"],
    "AGENT_CERTIFICATION": ["no_certificate_on_record"],
    "VERIFICATION_BEFORE_DISCLOSURE": ["disclosure_before_verification",
                                       "disclosure_after_failed_verification", "third_party_disclosure"],
    "CALL_RECORDING": ["recording_missing"],
    "NOTICE_TIMELINE": ["no_proof_of_service", "served_late"],
}

# Fallback severity, used ONLY when the model didn't produce any rule at all
# for a check_type it extracted (e.g. the request has no grading/severity
# section of its own -- common for a short pasted email or ad hoc upload).
# severity.grade() raises on an unmatched check_type/gap_type pair, so every
# check_type the model actually used MUST end up with at least one rule --
# this is the code-level guarantee for that, independent of whether the model
# remembered to write one. A check_type the request DOES grade explicitly is
# never touched here (see _fill_severity_defaults).
DEFAULT_SEVERITY_ORDER = ["CRITICAL", "MAJOR", "MINOR"]
DEFAULT_SEVERITY_BY_CHECK = {
    "CONSENT_BEFORE_CONTACT": "CRITICAL",
    "VERIFICATION_BEFORE_DISCLOSURE": "CRITICAL",
    "AGENT_CERTIFICATION": "CRITICAL",
    "TEMPLATE_APPROVED": "MAJOR",
    "CALL_HOURS": "MAJOR",
    "CALL_RECORDING": "MAJOR",
    "NOTICE_TIMELINE": "MAJOR",
    "CALL_FREQUENCY": "MINOR",
}


class CheckSpec(BaseModel):
    check_id: str
    source_question: str
    check_type: str
    params: dict = {}
    source_text: str
    test: str
    assumptions: list[str] = []


class SeverityRule(BaseModel):
    check_type: str
    gap_types: Optional[list[str]] = None
    min_late_business_days: Optional[int] = None
    severity: str


class Decomposition(BaseModel):
    checks: list[CheckSpec]
    severity_order: list[str]
    severity_rules: list[SeverityRule]


# Worked example baked into the prompt -- REQ-01, verbatim, with its real hand_checks
# output. This is what tells the model the exact shape and the "exact substring" rule,
# not just prose instructions.
_EXAMPLE_REQUEST = """From: internal.audit@l001-bank.example
To: collections.compliance@creditnirvana.example
Date: 14 Nov 2026 10:42 IST
Subject: Q1 2026 outsourced collections audit - evidence request (Ref: IA/COLL/2026/014)

Dear Compliance Team,

As part of our periodic review of outsourced collection activity, please provide evidence for the
300 accounts listed in Annexure A (attached), covering the period 1 January 2026 to 31 March 2026:

1. WhatsApp reminders were sent only to borrowers who had consented to WhatsApp communication, and
   only using approved templates.
2. Collection calls respected the permitted calling hours and call frequency limits.
3. All calls were made by recovery agents holding a valid certification.

For each point please share the underlying records (contact logs, consent records, certificates)
and clearly list any exceptions.

Exceptions will be graded as follows (Annexure B - Severity scale):
  CRITICAL - contact without valid consent; call made by an agent without valid certification
  MAJOR    - message sent using a template that was not approved; call outside permitted hours
  MINOR    - breach of call frequency limits

Please respond by 21 Nov 2026.

Regards,
Internal Audit - Retail Collections, L001"""

_EXAMPLE_OUTPUT = {
    "checks": [
        {"check_id": "C1", "source_question": "Q1", "check_type": "CONSENT_BEFORE_CONTACT",
         "params": {"channel": "WHATSAPP"},
         "source_text": "WhatsApp reminders were sent only to borrowers who had consented to WhatsApp communication",
         "test": "Every WhatsApp message has a WhatsApp consent captured before it and not opted out at that time",
         "assumptions": ["Consent is held per borrower; an opt-out ends consent until a new consent is captured"]},
        {"check_id": "C2", "source_question": "Q1", "check_type": "TEMPLATE_APPROVED", "params": {},
         "source_text": "and only using approved templates",
         "test": "Every WhatsApp message uses a WhatsApp template approved on or before the send date",
         "assumptions": []},
        {"check_id": "C3", "source_question": "Q2", "check_type": "CALL_HOURS", "params": {},
         "source_text": "Collection calls respected the permitted calling hours",
         "test": "Every voice attempt falls inside the D12 calling window in borrower local time",
         "assumptions": ["Every attempt counts, connected or not"]},
        {"check_id": "C4", "source_question": "Q2", "check_type": "CALL_FREQUENCY", "params": {},
         "source_text": "and call frequency limits",
         "test": "Unique voice attempts per account within D12 daily and weekly caps",
         "assumptions": ["Weeks run Monday-Sunday; only attempts inside the audit period are counted"]},
        {"check_id": "C5", "source_question": "Q3", "check_type": "AGENT_CERTIFICATION", "params": {},
         "source_text": "All calls were made by recovery agents holding a valid certification",
         "test": "The calling collector held a certificate valid on the call date",
         "assumptions": []},
    ],
    "severity_order": ["CRITICAL", "MAJOR", "MINOR"],
    "severity_rules": [
        {"check_type": "CONSENT_BEFORE_CONTACT", "severity": "CRITICAL"},
        {"check_type": "AGENT_CERTIFICATION", "severity": "CRITICAL"},
        {"check_type": "TEMPLATE_APPROVED", "severity": "MAJOR"},
        {"check_type": "CALL_HOURS", "severity": "MAJOR"},
        {"check_type": "CALL_FREQUENCY", "severity": "MINOR"},
    ],
}

SYSTEM_PROMPT = f"""You read an audit request email or letter from a lender and turn it
into a structured checklist.

The ONLY check types that exist are: {", ".join(CHECK_TYPES)}.
Never invent a new check_type. If a sentence asks for something that doesn't map to
one of these, still include it as a check but set check_type to "UNSUPPORTED" --
never silently drop a requirement.

A single sentence can produce MULTIPLE checks if it bundles several requirements
(e.g. "calls were in hours and by certified agents" -> CALL_HOURS + AGENT_CERTIFICATION).

source_text must be an EXACT, verbatim substring of the request below -- copy it
character for character, do not paraphrase. This is the citation for the check.

Also read the request's own severity/grading section (it may be called Annexure B,
"grading", "severity scale", or something else) and extract:
- severity_order: the scale's levels, worst first, exactly as named in the request
- severity_rules: one rule per check_type naming which severity it maps to. A rule
  may optionally include gap_types or min_late_business_days if the request's
  grading language distinguishes sub-cases of the same check_type.

If a rule needs "gap_types", you MUST use the exact strings below -- these are the
literal values the check engine produces, not names you choose. Never invent your
own gap_type spelling; a rule using any other string will never match and the run
will fail:
{chr(10).join(f"  {ct}: {gts}" for ct, gts in GAP_TYPES_BY_CHECK.items())}

Most rules don't need "gap_types" at all -- only add it when the request's grading
text explicitly distinguishes sub-cases within one check_type (like REQ-02's notice
rules below, which split "no proof of service" from "served late").

Respond with ONLY a JSON object: {{"checks": [...], "severity_order": [...], "severity_rules": [...]}}
No text before or after the JSON.

--- WORKED EXAMPLE ---
REQUEST:
{_EXAMPLE_REQUEST}

OUTPUT:
{json.dumps(_EXAMPLE_OUTPUT)}
--- END EXAMPLE ---"""


def _normalize_ws(s: str) -> str:
    """Collapse whitespace runs (including line-wrap newlines from how the source
    email/PDF happens to wrap) to a single space. The verbatim check cares about
    the model not paraphrasing CONTENT, not about reproducing incidental line
    breaks -- at temperature=1 the model sometimes types a wrapped phrase with a
    plain space instead of the source's literal newline, which is not paraphrasing
    and should not be flagged as an unverified quote."""
    return re.sub(r"\s+", " ", s).strip()


def _fill_severity_defaults(checks: list[dict], severity_order: list[str], severity_rules: list[dict]) -> tuple:
    """Guarantee every check_type actually extracted has at least one severity
    rule mentioning it, so severity.grade() can never raise with "no rule
    matches" just because the source request never spelled out a grading
    scale. A check_type the model DID write a rule for (even a partial,
    gap_types-qualified one) is left exactly as the model wrote it -- this
    only fills in check_types with ZERO rules at all."""
    severity_order = list(severity_order) or list(DEFAULT_SEVERITY_ORDER)
    severity_rules = list(severity_rules)
    mentioned = {r.get("check_type") for r in severity_rules}
    for check_type in dict.fromkeys(c["check_type"] for c in checks):
        if check_type in mentioned:
            continue
        severity = DEFAULT_SEVERITY_BY_CHECK.get(check_type, "MAJOR")
        severity_rules.append({"check_type": check_type, "severity": severity})
        if severity not in severity_order:
            severity_order.append(severity)
    return severity_order, severity_rules


def decompose(request_text: str, request_id: str, lender_id: str, period: dict, sample_file: str,
              source: str = "") -> dict:
    """Returns a dict in the same shape as eval/hand_checks/REQ-0X.json, plus an
    extra "unsupported" key. Raises if the model's output doesn't validate -- callers
    should surface that as a failure, not guess at a partial result."""
    raw = call_reasoning([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request_text},
    ])
    parsed = Decomposition.model_validate(extract_json(raw))

    normalized_request = _normalize_ws(request_text)
    checks, unsupported = [], []
    for c in parsed.checks:
        verbatim = _normalize_ws(c.source_text) in normalized_request
        if not verbatim:
            c.test = f"[UNVERIFIED QUOTE -- source_text not found verbatim] {c.test}"
        if c.check_type in CHECK_TYPES and verbatim:
            checks.append(c.model_dump())
        else:
            unsupported.append(c.model_dump())

    severity_order, severity_rules = _fill_severity_defaults(
        checks, parsed.severity_order, [r.model_dump(exclude_none=True) for r in parsed.severity_rules]
    )

    return {
        "request_id": request_id,
        "source": source,
        "lender_id": lender_id,
        "period": period,
        "sample_file": sample_file,
        "checks": checks,
        "unsupported": unsupported,
        "severity_order": severity_order,
        "severity_rules": severity_rules,
    }
