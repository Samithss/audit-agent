"""
Run the deterministic pipeline (Stages 3-5) for one request, from a checks.json.

    python -m agent.run_checks REQ-01            # uses eval/hand_checks/REQ-01.json
    python -m agent.run_checks --all
    python -m agent.run_checks REQ-01 --checks path/to/llm_checks.json

Outputs out/<REQ>/verdicts.csv, gap_items.csv, summary.csv
"""
import argparse
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd

from .checks import CHECKS, Context
from .config import DATA_DIR, HAND_CHECKS, OUT_DIR
from .rules import Policy
from .severity import grade, worst
from .tools import Tools


def run(spec_path, tools=None, out_dir=OUT_DIR, verbose=True):
    spec = json.load(open(spec_path))
    rid = spec["request_id"]
    t0 = time.time()
    tools = tools or Tools()
    policy = Policy(tools)
    sample = pd.read_csv(DATA_DIR / spec["sample_file"], dtype=str)["account_id"].tolist()
    unknown = set(sample) - set(tools.accounts().index)
    if unknown:
        raise ValueError(f"{len(unknown)} sampled accounts not found in D1: {sorted(unknown)[:5]}")
    ctx = Context(tools, policy, rid, date.fromisoformat(spec["period"]["from"]), date.fromisoformat(spec["period"]["to"]))
    order = spec["severity_order"]
    verdicts = []
    for chk in spec["checks"]:
        fn = CHECKS[chk["check_type"]]
        for v in fn(ctx, chk, sample):
            for g in v.gaps:
                g.severity = grade(g, v.check_type, spec["severity_rules"])
            v.severity = worst([g.severity for g in v.gaps], order)
            verdicts.append(v)

    od = Path(out_dir) / rid
    od.mkdir(parents=True, exist_ok=True)
    vdf = pd.DataFrame([v.row() for v in verdicts])
    vdf.to_csv(od / "verdicts.csv", index=False)
    gaps = [dict(gap_item_id=f"{rid}-G{i + 1:04d}", request_id=rid, account_id=v.account_id, check_id=v.check_id,
                 check_type=v.check_type, gap_type=g.gap_type, severity=g.severity,
                 record_ids=";".join(g.record_ids), detail=g.detail)
            for i, (v, g) in enumerate((v, g) for v in verdicts for g in v.gaps)]
    pd.DataFrame(gaps, columns=["gap_item_id", "request_id", "account_id", "check_id", "check_type", "gap_type",
                                "severity", "record_ids", "detail"]).to_csv(od / "gap_items.csv", index=False)
    summ = (vdf.pivot_table(index=["check_id", "check_type"], columns="status", values="account_id",
                            aggfunc="count", fill_value=0).reset_index())
    summ.to_csv(od / "summary.csv", index=False)
    if verbose:
        print(f"\n=== {rid}: {len(sample)} accounts x {len(spec['checks'])} checks in {time.time() - t0:.1f}s ===")
        print(summ.to_string(index=False))
        for n in dict.fromkeys(tools.notes):
            print("  note:", n)
    return vdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--checks", help="path to a checks.json (default: eval/hand_checks/<REQ>.json)")
    a = ap.parse_args()
    reqs = sorted(p.stem for p in HAND_CHECKS.glob("*.json")) if a.all else [a.request]
    tools = Tools()
    for r in reqs:
        run(a.checks or HAND_CHECKS / f"{r}.json", tools)


if __name__ == "__main__":
    main()
