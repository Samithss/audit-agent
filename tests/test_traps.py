"""Unit tests for the traps that decide the score. Run: pytest -q"""
from datetime import date

import pytest

from agent.rules import Policy
from agent.tools import Tools, normalize_collector_id
from agent.verdict import Finding, Verdict

T = Tools()


def test_collector_id_formats():
    assert normalize_collector_id("col42") == normalize_collector_id("COL0042") == "COL-0042"


def test_d4_is_ist_converted_to_utc():
    c = T.contact_log(T.accounts().index[:5])
    r = c.iloc[0]
    assert r.ts_utc.tz_convert("Asia/Kolkata").tz_localize(None).strftime("%Y-%m-%d %H:%M:%S") == r.ts_raw


def test_duplicates_removed():
    assert not T._contacts_all().contact_id.duplicated().any()


def test_business_days_state_holiday_and_saturdays():
    P = Policy(T)
    assert not P.is_business_day(date(2026, 1, 15), "TN")     # Pongal (TN only)
    assert P.is_business_day(date(2026, 1, 15), "KA")
    assert not P.is_business_day(date(2026, 1, 10), "KA")     # 2nd Saturday
    assert P.is_business_day(date(2026, 1, 3), "KA")          # 1st Saturday


def test_lender_override_and_effective_dates():
    P = Policy(T)
    assert P.calling_window("L002", date(2026, 4, 1))[2] == "POL-L002-004"
    assert P.cap("DAILY_CALL_CAP", "L002", date(2026, 4, 30))[0] == 3
    assert P.cap("DAILY_CALL_CAP", "L002", date(2026, 5, 1))[0] == 2
    assert P.cap("DAILY_CALL_CAP", "L001", date(2026, 2, 1))[0] == 3   # superseded cap of 4 ignored


def test_no_evidenced_without_citation():
    with pytest.raises(ValueError):
        Verdict("R", "C1", "X", "ACC1", items_tested=1, evidence_ids=[])


def test_gap_beats_cannot_determine():
    v = Verdict("R", "C1", "X", "ACC1", items_tested=2, gaps=[Finding("g", ["a"], "")],
                undetermined=[Finding("u", ["b"], "")])
    assert v.status == "GAP"
