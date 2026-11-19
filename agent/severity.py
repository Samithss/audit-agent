"""Stage 5: grade gaps on the request's OWN severity scale. Rules are data (from checks.json), applied in code."""


def grade(finding, check_type, rules):
    for r in rules:
        if r.get("check_type", "*") not in ("*", check_type):
            continue
        if "gap_types" in r and finding.gap_type not in r["gap_types"]:
            continue
        if "min_late_business_days" in r and (finding.late_bd or 0) < r["min_late_business_days"]:
            continue
        return r["severity"]
    raise ValueError(f"No severity rule matches {check_type}/{finding.gap_type}: fix the scale mapping")


def worst(levels, order):
    return min(levels, key=order.index) if levels else None
