"""
Step 5 — turn a raw audit request's text into a checks.json (same shape as
eval/hand_checks/REQ-0X.json), using Deepseek (generic reasoning) via Sarvam.

Closed catalogue: the model classifies each clause into one of the check types
already wired in agent/checks.py -- it never invents a new one. Anything it can't
map goes into "unsupported" (reported, never silently dropped). checks.json still
only has a "checks" list for run_checks.py to execute, exactly as today --
"unsupported" is an extra key run_checks.py ignores, meant for pack.py later.

request_id / lender_id / sample_file are NOT guessed by the model -- in real
operation you already know these from how the request arrived (sender, attachment
name), the same way the hand-written checks.json files carry them separately from
the checks list. The model's job is: read the prose, produce checks + severity rules.

The audit period is normally supplied by the caller. If the caller leaves it blank,
the model may extract it from the letter, but only if the letter states it
explicitly: the model must quote the exact words (verified verbatim) and the dates
must parse and be in order. Otherwise decompose() raises rather than guess.
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
    "CALLER_NUMBER_SERIES": ["non_160_caller"],
    "MESSAGE_CONTENT": ["inappropriate_message"],
    "CALL_CONDUCT": ["abusive_or_threatening_language"],
    "FIELD_VISIT": ["visit_outside_hours"],
    "SECURITY_RELEASE": ["security_not_released"],
    "PENAL_CHARGES": ["penal_capitalised", "penal_on_penal", "penal_not_disclosed_in_reminder"],
}

CHECK_HELP = {
    "CALLER_NUMBER_SERIES": "recovery calls made only from the dedicated 160-series number",
    "MESSAGE_CONTENT": "WhatsApp/SMS text free of threats, shaming or privacy intrusion",
    "CALL_CONDUCT": "agents did not threaten, abuse or mislead borrowers on calls",
    "FIELD_VISIT": "field visits made only within the permitted hours",
    "SECURITY_RELEASE": "securities released after the loan is repaid or closed",
    "PENAL_CHARGES": "penal charges not capitalised, not levied on penal charges, and stated in reminders",
}

# Fallback severity, used ONLY when the request gives no grading for a check_type
# it extracted (e.g. a short pasted email or ad hoc upload with no severity
# section). Policy: treat an ungraded gap as the WORST level -- if the lender
# didn't say how serious it is, report it as the most serious. When the request
# has a scale of its own (e.g. P1/P2/P3) but skips one check, that scale's top
# level is used so the fallback stays on the lender's own scale. severity.grade()
# raises on an unmatched check_type/gap_type pair, so every check_type the model
# actually used MUST end up with at least one rule -- this is the code-level
# guarantee for that. A check_type the request DOES grade is never touched.
DEFAULT_SEVERITY_ORDER = ["CRITICAL"]


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


class PeriodSpec(BaseModel):
    from_date: str   # ISO YYYY-MM-DD
    to_date: str     # ISO YYYY-MM-DD, inclusive
    source_text: str # exact words in the request that state the period


class Decomposition(BaseModel):
    period: Optional[PeriodSpec] = None
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
    "period": {"from_date": "2026-01-01", "to_date": "2026-03-31",
               "source_text": "covering the period 1 January 2026 to 31 March 2026"},
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
{chr(10).join(f"  {k}: {v}" for k, v in CHECK_HELP.items())}
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

Also extract the audit period the request asks about, as "period":
{{"from_date": "YYYY-MM-DD", "to_date": "YYYY-MM-DD", "source_text": "<exact words from the request>"}}.
Dates are inclusive and must be ISO. source_text must be copied verbatim, like a check's, and
must contain BOTH the start date and the end date written out in full (e.g. "1 January 2026 to
31 March 2026"). Only fill this in if the request states both dates. A named quarter or month
("Q1 2026", "Jan-Mar"), a subject line, the email's sent date or a deadline is NOT enough --
then set "period" to null. Never guess.

Respond with ONLY a JSON object: {{"period": {{...}} or null, "checks": [...], "severity_order": [...], "severity_rules": [...]}}
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
    worst_level = severity_order[0]  # the request's own top level, or CRITICAL if it gave no scale
    mentioned = {r.get("check_type") for r in severity_rules}
    for check_type in dict.fromkeys(c["check_type"] for c in checks):
        if check_type not in mentioned:
            severity_rules.append({"check_type": check_type, "severity": worst_level})
    return severity_order, severity_rules


_MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DATE_RES = [
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}\.?,?\s+\d{{4}}\b",   # 1 January 2026
    rf"\b{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b",              # January 1, 2026
    r"\b\d{4}-\d{2}-\d{2}\b",                                                   # 2026-01-01
    r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{4}\b",                                       # 01/01/2026 (day first)
]


def _dates_in(text: str) -> set:
    """Every fully-written calendar date in `text`. Deterministic: this is what
    decides whether the model's quoted period really names a start and an end."""
    from dateutil import parser
    found = set()
    for rx in _DATE_RES:
        for m in re.finditer(rx, text, flags=re.I):
            try:
                found.add(parser.parse(m.group(0).replace("of ", ""), dayfirst=True).date())
            except (ValueError, OverflowError):
                pass
    return found


def _resolve_period(given: Optional[dict], extracted: Optional[PeriodSpec], request_text: str) -> tuple[dict, str]:
    """Caller-supplied dates always win. Otherwise use the model's extraction, but
    only if it is verbatim in the request, parses as ISO dates and is in order."""
    from datetime import date
    if given and given.get("from") and given.get("to"):
        return {"from": given["from"], "to": given["to"]}, "entered"
    fail = ValueError("Could not find an explicit audit period in the request -- "
                      "enter the 'Period from' and 'Period to' dates and run again.")
    if extracted is None or _normalize_ws(extracted.source_text) not in _normalize_ws(request_text):
        raise fail
    try:
        f, t = date.fromisoformat(extracted.from_date), date.fromisoformat(extracted.to_date)
    except ValueError:
        raise fail
    if f > t:
        raise fail
    # The quoted words themselves must contain both dates -- so "Q1 2026" in a
    # subject line, or dates the model made up, can never become the period.
    if not {f, t} <= _dates_in(extracted.source_text):
        raise fail
    return {"from": f.isoformat(), "to": t.isoformat()}, "extracted"


def decompose_from_guidelines(guideline_ids: list, request_id: str, lender_id: str, period: Optional[dict],
                              sample_file: str, source: str = "", base: Optional[dict] = None) -> dict:
    """Checks come from the chosen guidelines instead of (or on top of) the request text."""
    from .guidelines import checks_for
    if base is None:
        if not (period and period.get("from") and period.get("to")):
            raise ValueError("Enter the 'Period from' and 'Period to' dates -- there is no request text to read them from.")
        order, rules = _fill_severity_defaults([], [], [])
        base = {"request_id": request_id, "source": source, "lender_id": lender_id,
                "period": {"from": period["from"], "to": period["to"]}, "period_source": "entered",
                "sample_file": sample_file, "checks": [], "unsupported": [],
                "severity_order": order, "severity_rules": rules}
    key = lambda c: (c["check_type"], (c.get("params") or {}).get("channel"))
    have = {key(c) for c in base["checks"]}
    new, skipped = [], []
    for c in checks_for(guideline_ids, len(base["checks"]) + 1):
        (skipped if key(c) in have else new).append(c)
        have.add(key(c))
    for i, c in enumerate(new):          # renumber after dropping duplicates of checks the request already asked for
        c["check_id"] = f"C{len(base['checks']) + i + 1}"
    base["checks"] = base["checks"] + new
    base["guideline_checks_already_in_request"] = [c["source_question"] for c in skipped]
    base["severity_order"], base["severity_rules"] = _fill_severity_defaults(
        base["checks"], base["severity_order"], base["severity_rules"])
    base["source"] = (base["source"] + " + " if base["source"] else "") + "selected guidelines"
    return base


def decompose(request_text: str, request_id: str, lender_id: str, period: Optional[dict], sample_file: str,
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

    period, period_source = _resolve_period(period, parsed.period, request_text)

    severity_order, severity_rules = _fill_severity_defaults(
        checks, parsed.severity_order, [r.model_dump(exclude_none=True) for r in parsed.severity_rules]
    )

    return {
        "request_id": request_id,
        "source": source,
        "lender_id": lender_id,
        "period": period,
        "period_source": period_source,
        "sample_file": sample_file,
        "checks": checks,
        "unsupported": unsupported,
        "severity_order": severity_order,
        "severity_rules": severity_rules,
    }
