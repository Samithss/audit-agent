"""
Verdict objects (Stage 4 output). The guardrail lives in code:
a verdict can never be EVIDENCED without cited records.
"""
from dataclasses import dataclass, field
from typing import Optional

EVIDENCED, GAP, CANNOT_DETERMINE, NOT_APPLICABLE = "EVIDENCED", "GAP", "CANNOT_DETERMINE", "NOT_APPLICABLE"


@dataclass
class Finding:
    gap_type: str
    record_ids: list
    detail: str
    late_bd: Optional[int] = None
    severity: Optional[str] = None


@dataclass
class Verdict:
    request_id: str
    check_id: str
    check_type: str
    account_id: str
    items_tested: int
    gaps: list = field(default_factory=list)
    undetermined: list = field(default_factory=list)
    evidence_ids: list = field(default_factory=list)
    rule_refs: list = field(default_factory=list)
    status: str = ""
    severity: Optional[str] = None

    def __post_init__(self):
        if self.items_tested == 0:
            self.status = NOT_APPLICABLE
        elif self.gaps:
            self.status = GAP                 # a gap always wins
        elif self.undetermined:
            self.status = CANNOT_DETERMINE    # never upgrade missing evidence to compliant
        else:
            self.status = EVIDENCED
        if self.status == EVIDENCED and not self.evidence_ids:
            raise ValueError(f"{self.account_id}/{self.check_id}: EVIDENCED without cited records is not allowed")

    def row(self):
        return dict(request_id=self.request_id, account_id=self.account_id, check_id=self.check_id,
                    check_type=self.check_type, status=self.status, severity=self.severity or "",
                    items_tested=self.items_tested, gap_items=len(self.gaps),
                    gap_types=";".join(sorted({g.gap_type for g in self.gaps})),
                    cannot_determine_reasons=";".join(sorted({u.gap_type for u in self.undetermined})),
                    evidence_count=len(self.evidence_ids),
                    evidence_ids=";".join(dict.fromkeys(self.evidence_ids)),
                    rule_refs=";".join(dict.fromkeys(self.rule_refs)))
