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
    od = Path(out_dir) / request_id
    verdicts = pd.read_csv(od / "verdicts.csv", dtype=str)
    gaps = pd.read_csv(od / "gap_items.csv", dtype=str)
    summary = pd.read_csv(od / "summary.csv", dtype=str)

    cd = verdicts[verdicts.status == "CANNOT_DETERMINE"][
        ["account_id", "check_id", "check_type", "cannot_determine_reasons", "evidence_ids"]
    ].rename(columns={"cannot_determine_reasons": "reason", "evidence_ids": "record_ids"})

    path = od / "gap_report.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        summary.to_excel(xl, sheet_name="Summary", index=False)
        gaps.to_excel(xl, sheet_name="Gaps", index=False)  # one row per gap, never merged
        cd.to_excel(xl, sheet_name="Cannot-Determine", index=False)
        for sheet in xl.sheets.values():
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            _autofit(sheet)
    return path


def build_request_interpretation(request_id: str, decomposed_path, out_dir=OUT_DIR) -> Path:
    spec = json.loads(Path(decomposed_path).read_text())
    od = Path(out_dir) / request_id
    od.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Request interpretation -- {request_id}",
        "",
        f"Lender: {spec['lender_id']} | Period: {spec['period']['from']} to {spec['period']['to']}"
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
        "request_interpretation": str(build_request_interpretation(request_id, decomposed_path, out_dir)),
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
