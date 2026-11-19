"""
Step 7a -- the evidence pack: what a compliance reviewer actually reads.

Reads the CSVs run_checks.py already wrote (out/<REQ>/*.csv) plus the decomposed
checks.json (for "what we understood from the request" and the UNSUPPORTED list --
reported, never dropped). Writes:
  out/<REQ>/gap_report.xlsx            -- Summary / Gaps / Cannot-Determine sheets
  out/<REQ>/request_interpretation.md  -- what was asked, how it was decomposed
"""
import json
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .config import OUT_DIR


def _autofit(ws):
    for col in ws.columns:
        width = max((len(str(c.value)) if c.value is not None else 0) for c in col) + 2
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(width, 60)


def build_gap_report(request_id: str, out_dir=OUT_DIR) -> Path:
    """The one evidence-pack file: everything the UI shows, in a workbook a
    reviewer can filter. Sheets:
      Overview        -- request, period, counts
      Checks          -- every check run: what it tests, the request wording it came from
      Account results -- one row per account x check, in plain English
      Records tested  -- one row per record (call / message / visit ...) with pass/fail and why
      Consent records -- the consent rows behind every consent check
      Summary         -- counts per check and status
      Gaps            -- one row per gap item, never merged
      Cannot-Determine
    """
    from .explain import account_results, check_label

    od = Path(out_dir) / request_id
    spec = json.loads((od / "checks.json").read_text())
    verdicts = pd.read_csv(od / "verdicts.csv", dtype=str).fillna("")
    gaps = pd.read_csv(od / "gap_items.csv", dtype=str).fillna("")
    summary = pd.read_csv(od / "summary.csv", dtype=str).fillna("")
    labels = {c["check_id"]: check_label(c) for c in spec["checks"]}
    summary.insert(1, "check", summary["check_id"].map(labels))
    summary = summary.drop(columns=[c for c in ("check_type",) if c in summary.columns])

    results = account_results(request_id)
    acct_rows, rec_rows, consent_rows = [], [], []
    for r in results:
        base = dict(account_id=r["account_id"], check_id=r["check_id"], check=labels.get(r["check_id"], r["check_name"]),
                    channel=r["channel_label"])
        acct_rows.append(dict(base, result=r["status"].replace("_", " ").title(), severity=r.get("severity", ""),
                              what_we_found=r["headline"], explanation=r["summary"], items_tested=r.get("items_tested", ""),
                              rule=r.get("rule_refs", "")))
        for i in r.get("items", []):
            rec_rows.append(dict(base, record_id=i.get("contact_id", ""), time=i.get("time", ""),
                                 outcome=i.get("outcome", ""), detail=i.get("result", "")))
        for c in r.get("consent", []):
            consent_rows.append(dict(base, consent_id=c.get("consent_id", ""), status=c.get("status", ""),
                                     source=c.get("source", ""), captured=c.get("captured", ""),
                                     opted_out=c.get("opted_out", "")))

    checks_df = pd.DataFrame([dict(check_id=c["check_id"], check=labels[c["check_id"]], what_it_tests=c.get("test", ""),
                                   request_wording=c.get("source_text", ""),
                                   assumptions="; ".join(c.get("assumptions") or []))
                              for c in spec["checks"]])
    counts = verdicts.status.value_counts().to_dict()
    overview = pd.DataFrame([
        ("Request", request_id),
        ("Audit period", f"{spec['period']['from']} to {spec['period']['to']}"),
        ("Accounts tested", verdicts.account_id.nunique()), ("Checks run", len(spec["checks"])),
        ("Gap", counts.get("GAP", 0)), ("Cannot determine", counts.get("CANNOT_DETERMINE", 0)),
        ("Evidenced", counts.get("EVIDENCED", 0)), ("Not applicable", counts.get("NOT_APPLICABLE", 0)),
        ("Not tested (unsupported)", len(spec.get("unsupported", []))),
    ], columns=["", "value"])
    cd = verdicts[verdicts.status == "CANNOT_DETERMINE"][
        ["account_id", "check_id", "check_type", "cannot_determine_reasons", "evidence_ids"]
    ].rename(columns={"cannot_determine_reasons": "reason", "evidence_ids": "record_ids"})

    path = od / "gap_report.xlsx"
    sheets = [("Overview", overview), ("Checks", checks_df), ("Account results", pd.DataFrame(acct_rows)),
              ("Records tested", pd.DataFrame(rec_rows)), ("Consent records", pd.DataFrame(consent_rows)),
              ("Summary", summary), ("Gaps", gaps), ("Cannot-Determine", cd)]
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        for name, df in sheets:
            df.to_excel(xl, sheet_name=name, index=False)
        for sheet in xl.sheets.values():
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            sheet.freeze_panes = "A2"
            _autofit(sheet)
    return path


def build_request_interpretation(request_id: str, decomposed_path, out_dir=OUT_DIR) -> Path:
    spec = json.loads(Path(decomposed_path).read_text())
    od = Path(out_dir) / request_id
    od.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Request interpretation -- {request_id}",
        "",
        f"Period: {spec['period']['from']} to {spec['period']['to']}"
        f" | Source: {spec.get('source', '')}",
        "",
        f"## Checks extracted ({len(spec['checks'])})",
        "",
    ]
    for c in spec["checks"]:
        lines += [
            f"### {c['check_id']} -- {c['check_type']}",
            f'> "{c["source_text"]}"',
            "",
            f"**Test:** {c['test']}",
        ]
        if c.get("assumptions"):
            lines.append(f"**Assumptions:** {'; '.join(c['assumptions'])}")
        lines.append("")

    unsupported = spec.get("unsupported", [])
    lines.append(f"## Not tested -- reported, not dropped ({len(unsupported)})")
    lines.append("")
    if not unsupported:
        lines.append("None -- every requirement in the request mapped to a known check.")
    for c in unsupported:
        lines += [f'- "{c["source_text"]}" -- {c["test"]}', ""]

    lines += ["## Severity scale", "", f"Order (worst first): {', '.join(spec['severity_order'])}", ""]
    for r in spec["severity_rules"]:
        cond = ""
        if r.get("gap_types"):
            cond += f" (gap_types={r['gap_types']})"
        if r.get("min_late_business_days"):
            cond += f" (min_late_business_days={r['min_late_business_days']})"
        lines.append(f"- {r['check_type']}{cond} -> {r['severity']}")

    path = od / "request_interpretation.md"
    path.write_text("\n".join(lines))
    return path


def build_pack(request_id: str, decomposed_path, out_dir=OUT_DIR) -> dict:
    return {
        "gap_report": str(build_gap_report(request_id, out_dir)),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("request")
    ap.add_argument("--checks", required=True, help="path to the decomposed checks.json")
    a = ap.parse_args()
    for k, v in build_pack(a.request, a.checks).items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
