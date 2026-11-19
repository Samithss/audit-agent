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
- Open with "Dear <recipient_name>," when the summary has a recipient_name, otherwise
  "Dear Sir/Madam,". NEVER address the reader by an internal code like "Lender L001" --
  that is a database id, not a name. Refer to the lender id only as a reference
  (e.g. "your audit request for portfolio L001"), never in the salutation.
- State plainly the audit period, how many accounts were checked, how many checks
  were run, and how many accounts had at least one gap.
- Do NOT list per-check counts or severities in prose. The system inserts a results
  table (counts per check and status, plus severity) at the place where you write the
  line [[RESULTS_TABLE]] on its own, between blank lines. Introduce it with one short
  sentence just before. Cite nothing you cannot see in the summary.
- Layout: opening paragraph; one lead-in sentence; the [[RESULTS_TABLE]] line; then
  the paragraph about unsupported requirements (if any); then the closing sentence.
- Name the checks that had gaps in plain words, using each "check_label" from
  severity_by_check (for example "Consent - WhatsApp"), with the number of accounts
  and the severity, so the reader knows exactly which requirement or guideline failed.
  Never write the bare words "check type" or the raw code name; use the check_label.
- Severity names (CRITICAL, MAJOR, MINOR, ...) are labels from the request's own
  scale and may be written as they are.
- Never use softening language: no "minor", "isolated", "broadly compliant",
  "largely", "substantially compliant", "negligible", "only a few", "relatively",
  "mostly compliant". State counts plainly, even when the finding is unflattering.
- If "unsupported" is non-empty, explicitly say those specific requirements could
  not be tested and why -- do not omit this.
- End with exactly this sentence: "This is a draft for compliance review and has
  not been approved for external release."
- Plain prose paragraphs, no markdown, no bullet symbols -- this is a formal letter."""


def _summary_for_letter(request_id: str, decomposed_path, out_dir=OUT_DIR, recipient_name: str | None = None) -> dict:
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

    from .explain import check_label
    labels = {c["check_id"]: check_label(c) for c in spec["checks"]}
    by_check = (
        verdicts.groupby(["check_id", "check_type"])["status"]
        .value_counts().unstack(fill_value=0).reset_index().to_dict("records")
    )
    for r in by_check:
        r["check_label"] = labels.get(r["check_id"], r["check_type"])
    gap_accounts = verdicts[verdicts.status == "GAP"]
    severity_by_check = (
        gap_accounts.groupby(["check_id", "check_type", "severity"]).size()
        .reset_index(name="accounts_with_gap").to_dict("records")
        if len(gap_accounts) else []
    )
    for r in severity_by_check:
        r["check_label"] = labels.get(r["check_id"], r["check_type"])

    return {
        # Who the reply is actually going to, when we know (a Gmail-sourced run
        # knows the real sender). None for sample/upload runs -> "Dear Sir/Madam".
        "recipient_name": recipient_name,
        "lender_id": spec["lender_id"],
        "period": spec["period"],
        "accounts_sampled": int(verdicts.account_id.nunique()),
        "checks_run": len(spec["checks"]),
        "by_check": by_check,
        "total_accounts_with_gap": int(len(gap_accounts)),
        "severity_by_check": severity_by_check,
        "severity_order": spec.get("severity_order", []),
        "unsupported": [c["source_text"] for c in spec.get("unsupported", [])],
    }


STATUSES = [("EVIDENCED", "Evidenced"), ("GAP", "Gap"),
            ("CANNOT_DETERMINE", "Cannot determine"), ("NOT_APPLICABLE", "Not applicable")]


def _results_table(summary: dict) -> str:
    """Plain-text pipe table, built in code (never by the model), so the counts
    are exactly the summary's. One row per check."""
    sev_by_check = {}
    for r in summary.get("severity_by_check", []):
        sev_by_check.setdefault(r["check_id"], set()).add(r["severity"])
    order = summary.get("severity_order", [])
    rank = lambda x: order.index(x) if x in order else len(order)
    header = ["Check", "What was checked"] + [lbl for _, lbl in STATUSES] + ["Severity of gaps"]
    rows = []
    for r in summary["by_check"]:
        sev = "/".join(sorted(sev_by_check.get(r["check_id"], []), key=rank)) or "-"
        rows.append([r["check_id"], r.get("check_label", r["check_type"])] + [str(r.get(k, 0)) for k, _ in STATUSES] + [sev])
    w = [max(len(x[i]) for x in [header] + rows) for i in range(len(header))]
    line = lambda cells: "| " + " | ".join(c.ljust(w[i]) for i, c in enumerate(cells)) + " |"
    return "\n".join([line(header), "|" + "|".join("-" * (x + 2) for x in w) + "|"] + [line(r) for r in rows])


def _insert_table(text: str, summary: dict) -> str:
    table = _results_table(summary)
    if "[[RESULTS_TABLE]]" in text:
        return text.replace("[[RESULTS_TABLE]]", table)
    head, sep, tail = text.rpartition("\n\n")  # model forgot the marker: put it before the closing sentence
    return f"{head}\n\n{table}\n\n{tail}" if sep else f"{text}\n\n{table}"


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


def draft_and_validate(request_id: str, decomposed_path, out_dir=OUT_DIR,
                       recipient_name: str | None = None) -> dict:
    """Draft -> validate -> retry once with the failure reasons -> if still
    failing, return it anyway but flagged needs_human_review. Never ships a
    letter that passed on the first try without being checked."""
    summary = _summary_for_letter(request_id, decomposed_path, out_dir, recipient_name)

    text = _ask_model(summary)
    result = validate(text, summary)

    if not result["passed"]:
        text = _ask_model(summary, retry_reasons=result["reasons"])
        result = validate(text, summary)

    return {
        "text": _insert_table(text, summary),
        "summary": summary,
        "validation": result,
        "needs_human_review": not result["passed"],
    }


def iter_blocks(text: str):
    """Split a drafted letter into ("para", str) and ("table", rows) blocks.

    The letter carries its results table as a plain-text pipe table (built in
    code by _results_table, never by the model). Every renderer -- Word here,
    HTML email in gmail_client.send_reply -- needs the same parse, so it lives
    in one place: a block of lines that all start with "|" is the table, and
    the |---|---| separator row is dropped."""
    for para in text.split("\n\n"):
        if not para.strip():
            continue
        lines = para.strip().split("\n")
        if all(l.startswith("|") for l in lines):
            yield "table", [[c.strip() for c in l.strip().strip("|").split("|")]
                            for l in lines if not set(l) <= set("|- ")]
        else:
            yield "para", para.strip()


def save_letter_docx(request_id: str, text: str, out_dir=OUT_DIR) -> Path:
    doc = Document()
    doc.add_heading(f"Response to audit request -- {request_id}", level=1)
    for kind, block in iter_blocks(text):
        if kind == "table":
            cells = block
            t = doc.add_table(rows=len(cells), cols=len(cells[0]))
            t.style = "Table Grid"
            for i, row in enumerate(cells):
                for j, c in enumerate(row):
                    t.cell(i, j).text = c
                    if i == 0:
                        for r in t.cell(i, j).paragraphs[0].runs:
                            r.bold = True
        else:
            doc.add_paragraph(block)
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
