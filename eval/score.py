"""
Score agent output against the answer key.

    python -m eval.score            # scores out/REQ-*/verdicts.csv
    python -m eval.score --run      # runs agent.run_checks --all first

Metrics (account x check level, which is how the acceptance criteria are stated):
  gap recall          = true gaps the agent reported as GAP / all true gaps            (target >= 95%)
  false gap rate      = agent GAPs that are not true gaps / all agent GAPs             (target <  5%)
  unsupported claims  = EVIDENCED verdicts with no cited records, or EVIDENCED where a gap exists  (target 0)
  severity accuracy   = correct severity on correctly found gaps
"""
import argparse
import sys

import pandas as pd

from agent.config import DATA_DIR, OUT_DIR

KEY = ["request_id", "account_id", "check_id"]


def score(verbose=True):
    truth = pd.read_csv(DATA_DIR / "ground_truth" / "ground_truth_account_check.csv", dtype=str)
    preds = [pd.read_csv(p, dtype=str) for p in sorted(OUT_DIR.glob("REQ-*/verdicts.csv"))]
    if not preds:
        sys.exit("No outputs in out/. Run: python -m agent.run_checks --all")
    pred = pd.concat(preds)
    m = truth.merge(pred, on=KEY, how="left", suffixes=("_true", "_pred"))
    m = m[m["request_id"].isin(pred["request_id"].unique())]
    m["status_pred"] = m["status_pred"].fillna("MISSING")
    m["evidence_count"] = pd.to_numeric(m["evidence_count"]).fillna(0)

    def metrics(d):
        tg, pg = d.status_true == "GAP", d.status_pred == "GAP"
        tp, fn, fp = (tg & pg).sum(), (tg & ~pg).sum(), (~tg & pg).sum()
        unsupported = ((d.status_pred == "EVIDENCED") & ((d.evidence_count == 0) | tg)).sum()
        sev_ok = (d[tg & pg].severity_true == d[tg & pg].severity_pred).sum()
        return pd.Series(dict(true_gaps=tg.sum(), found=tp, missed=fn, false_gaps=fp,
                              recall=tp / tg.sum() if tg.sum() else 1.0,
                              false_gap_rate=fp / pg.sum() if pg.sum() else 0.0,
                              unsupported_claims=unsupported,
                              severity_acc=sev_ok / tp if tp else 1.0,
                              status_acc=(d.status_true == d.status_pred).mean()))

    per_check = m.groupby(["request_id", "check_id", "check_type_true"]).apply(metrics, include_groups=False)
    overall = metrics(m)
    if verbose:
        pd.set_option("display.width", 200)
        fmt = per_check.copy()
        for c in ["recall", "false_gap_rate", "severity_acc", "status_acc"]:
            fmt[c] = (fmt[c] * 100).round(1).astype(str) + "%"
        print(fmt.to_string())
        print("\nOVERALL")
        print(f"  gap recall         : {overall.recall:.1%}   (target >= 95%)  {'PASS' if overall.recall >= .95 else 'FAIL'}")
        print(f"  false gap rate     : {overall.false_gap_rate:.1%}   (target <  5%)  {'PASS' if overall.false_gap_rate < .05 else 'FAIL'}")
        print(f"  unsupported claims : {int(overall.unsupported_claims)}       (target 0)     {'PASS' if overall.unsupported_claims == 0 else 'FAIL'}")
        print(f"  severity accuracy  : {overall.severity_acc:.1%}")
        print(f"  status accuracy    : {overall.status_acc:.1%}")
        bad = m[(m.status_true != m.status_pred)]
        if len(bad):
            print(f"\n{len(bad)} status mismatches (first 15):")
            print(bad[KEY + ["check_type_true", "status_true", "status_pred", "gap_types_true", "gap_types_pred"]].head(15).to_string(index=False))
    return overall, per_check, m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    if ap.parse_args().run:
        from agent.run_checks import main as run_main
        sys.argv = ["run_checks", "--all"]
        run_main()
    score()
