"""
Step 7b -- draft response letter. Written from a verdict/gap SUMMARY only (counts,
not raw account rows) -- the model never sees account-level data, so it cannot
leak anything the summary doesn't already contain.
"""
import json
from pathlib import Path

import pandas as pd
from docx import Document

from .config import OUT_DIR
from .llm import call_reasoning
from .validator import validate

SYSTEM_PROMPT = """You draft a professional response letter from CreditNirvana's
compliance team to a lender who sent an audit request, based ONLY on the JSON
summary you are given -- never invent a fact not present in it.

Rules:
- State plainly how many accounts were checked and how many checks were run.
- For every check with gaps, state the gap count and severity. Cite nothing you
  cannot see in the summary.
- Never use softening language: no "minor", "isolated", "broadly compliant",
  "largely", "substantially compliant", "negligible", "only a few", "relatively",
  "mostly compliant". State counts plainly, even when the finding is unflattering.
- If "unsupported" is non-empty, explicitly say those specific requirements could
  not be tested and why -- do not omit this.
- End with exactly this sentence: "This is a draft for compliance review and has
  not been approved for external release."
- Plain prose paragraphs, no markdown, no bullet symbols -- this is a formal letter."""


def _summary_for_letter(request_id: str, decomposed_path, out_dir=OUT_DIR) -> dict:
    """Everything here is counted in ONE unit -- accounts, using verdicts.csv's
    own status/severity columns (severity is already the account-level worst
    severity computed by severity.worst() in run_checks.py). gap_items.csv is
    finding-level (one account's GAP can have several findings) and is
    deliberately NOT mixed in here -- it belongs in the Gaps sheet of the xlsx,
    not the letter, or the two counts don't reconcile and the model (correctly)
    flags a "discrepancy" that is really just a unit mismatch on our side."""
    spec = json.loads(Path(decomposed_path).read_text())
    od = Path(out_dir) / request_id
    verdicts = pd.read_csv(od / "verdicts.csv", dtype=str)

    by_check = (
        verdicts.groupby(["check_id", "check_type"])["status"]
        .value_counts().unstack(fill_value=0).reset_index().to_dict("records")
    )
    gap_accounts = verdicts[verdicts.status == "GAP"]
    severity_by_check = (
        gap_accounts.groupby(["check_id", "check_type", "severity"]).size()
        .reset_index(name="accounts_with_gap").to_dict("records")
        if len(gap_accounts) else []
    )

    return {
        "lender_id": spec["lender_id"],
        "period": spec["period"],
        "accounts_sampled": int(verdicts.account_id.nunique()),
        "checks_run": len(spec["checks"]),
        "by_check": by_check,
        "total_accounts_with_gap": int(len(gap_accounts)),
        "severity_by_check": severity_by_check,
        "unsupported": [c["source_text"] for c in spec.get("unsupported", [])],
    }


def _ask_model(summary: dict, retry_reasons=None) -> str:
    user_content = json.dumps(summary, indent=2)
    if retry_reasons:
        user_content += (
            "\n\nYour previous draft was rejected for these reasons -- fix them:\n"
            + "\n".join(f"- {r}" for r in retry_reasons)
        )
    text = call_reasoning(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_content}],
        reasoning_effort="low",
    )
    return text.strip()


def draft_and_validate(request_id: str, decomposed_path, out_dir=OUT_DIR) -> dict:
    """Draft -> validate -> retry once with the failure reasons -> if still
    failing, return it anyway but flagged needs_human_review. Never ships a
    letter that passed on the first try without being checked."""
    summary = _summary_for_letter(request_id, decomposed_path, out_dir)

    text = _ask_model(summary)
    result = validate(text, summary)

    if not result["passed"]:
        text = _ask_model(summary, retry_reasons=result["reasons"])
        result = validate(text, summary)

    return {
        "text": text,
        "summary": summary,
        "validation": result,
        "needs_human_review": not result["passed"],
    }


def save_letter_docx(request_id: str, text: str, out_dir=OUT_DIR) -> Path:
    doc = Document()
    doc.add_heading(f"Response to audit request -- {request_id}", level=1)
    for para in text.split("\n\n"):
        if para.strip():
            doc.add_paragraph(para.strip())
    od = Path(out_dir) / request_id
    od.mkdir(parents=True, exist_ok=True)
    path = od / "response_letter_DRAFT.docx"
    doc.save(path)
    return path


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("request")
    ap.add_argument("--checks", required=True)
    a = ap.parse_args()
    result = draft_and_validate(a.request, a.checks)
    path = save_letter_docx(a.request, result["text"])
    print(f"letter: {path}")
    print(f"needs_human_review: {result['needs_human_review']}")
    if result["needs_human_review"]:
        print("reasons:", result["validation"]["reasons"])


if __name__ == "__main__":
    main()
