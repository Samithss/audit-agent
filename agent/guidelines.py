"""Guideline catalogue (audit.guidelines, CSV fallback) -> checks the engine can run."""
import json

import pandas as pd

from .config import DATA_DIR


def list_guidelines() -> list[dict]:
    try:
        from .db import connect
        with connect() as conn:
            rows = conn.execute("SELECT * FROM audit.guidelines ORDER BY guideline_id").fetchall()
        if rows:
            return rows
    except Exception:
        pass
    return pd.read_csv(DATA_DIR / "rbi_guidelines.csv", dtype=str).fillna("").to_dict("records")


def checks_for(guideline_ids: list[str], first_n: int = 1) -> list[dict]:
    """Turn selected guideline ids into check specs (same shape the decomposer emits)."""
    by_id = {g["guideline_id"]: g for g in list_guidelines()}
    out = []
    for gid in guideline_ids:
        g = by_id.get(gid)
        if g is None:
            raise ValueError(f"unknown guideline {gid}")
        if g["testable"] != "Y" or not g["check_type"]:
            raise ValueError(f"{gid} cannot be tested yet: {g['needs']}")
        out.append({
            "check_id": f"C{first_n + len(out)}",
            "source_question": gid,
            "check_type": g["check_type"],
            "params": json.loads(g["params_json"] or "{}"),
            "source_text": f"{g['title']} [{gid}]",
            "test": g["rule_text"],
            "assumptions": [f"Source: {g['source_ref']}"],
        })
    return out
