"""
Step 7c -- plain code, no LLM. Blocks a letter that makes an uncited claim, uses
softening language, or leaks an unmasked phone number. letter.py calls this,
retries once with the failure reasons, and flags needs_human_review if it still
fails -- this module never fixes the text itself, only judges it.
"""
import re

SOFTENING_WORDS = [
    "minor", "isolated", "broadly compliant", "largely", "substantially compliant",
    "negligible", "only a few", "relatively", "mostly compliant",
]
PHONE_RE = re.compile(r"\b\d{10}\b")
LIMITATION_PHRASES = ["not test", "could not", "unable to", "outside the scope", "not supported", "not covered"]


def validate(text: str, summary: dict) -> dict:
    reasons = []
    lower = text.lower()

    # Severity names (e.g. MINOR) are the request's own scale labels, not softening.
    # Only the exact upper-case label is exempt; a lower-case "minor" is still flagged.
    labels = set(summary.get("severity_order", [])) | {r["severity"] for r in summary.get("severity_by_check", [])}
    scrubbed = text
    for lab in labels:
        scrubbed = scrubbed.replace(lab, "")
    scrubbed = scrubbed.lower()

    for w in SOFTENING_WORDS:
        if w in scrubbed:
            reasons.append(f"softening language: {w!r}")

    if PHONE_RE.search(text):
        reasons.append("unmasked 10-digit number found in letter text")

    if "draft" not in lower or "review" not in lower:
        reasons.append("missing the DRAFT / for-review disclaimer")

    total_gaps = summary.get("total_accounts_with_gap", 0)
    if total_gaps > 0 and "gap" not in lower and "exception" not in lower:
        reasons.append(f"letter never mentions gaps/exceptions, but {total_gaps} accounts have a gap in the summary")

    if summary.get("unsupported") and not any(p in lower for p in LIMITATION_PHRASES):
        reasons.append("request had unsupported items but the letter never mentions a testing limitation")

    return {"passed": not reasons, "reasons": reasons}
