"""
BASELINE transcript analyzer (keyword rules) for VERIFICATION_BEFORE_DISCLOSURE.

This is a placeholder so the pipeline can be scored end to end. In Step 6 it is replaced by
an LLM reviewer that returns the verification/disclosure turns with exact quotes, which code
then verifies against the transcript. Keep this as a fallback / cross-check.
"""
import re

AMOUNT = re.compile(r"\bRs\.?\s?[\d,]+|₹\s?[\d,]+|rupaye", re.I)
ASK_ID = re.compile(r"date of birth|DOB|janam tithi", re.I)
ID_OK = re.compile(r"identity is verified|verification ho gaya|verification aaytu|verification mudinjadhu|"
                   r"verification ayyindi|verified", re.I)
ID_FAIL = re.compile(r"does not match|match nahi|match aagtilla|match aagala|match avvaledu|won't|nahi bataunga|"
                     r"heLalla|solla maaten|cheppanu", re.I)
WRONG_PARTY = re.compile(r"wrong number|no .* here|koi .* nahi hai|yaaru illa|yaarum illa|evaru leru", re.I)


def analyze_call(turns):
    """turns: DataFrame of one call sorted by turn_no.
    Returns (outcome, cited_turns, detail). outcome in ok | disclosure_before_verification |
    disclosure_after_failed_verification | third_party_disclosure"""
    first = lambda pat, spk=None: next((int(r.turn_no) for r in turns.itertuples()
                                        if (spk is None or r.speaker == spk) and pat.search(r.text)), None)
    disclose = first(AMOUNT, "AGENT")
    wrong = first(WRONG_PARTY, "CUSTOMER")
    ok = first(ID_OK, "AGENT")
    fail = first(ID_FAIL)
    ask = first(ASK_ID, "AGENT")
    if disclose is None:
        return "ok", [t for t in (ask, ok) if t], "No amount disclosed on call"
    if wrong is not None and wrong < disclose:
        return "third_party_disclosure", [wrong, disclose], f"Wrong party at turn {wrong}; amount disclosed at turn {disclose}"
    if ok is not None and ok < disclose:
        return "ok", [ask, ok, disclose], f"Verified at turn {ok}; amount disclosed at turn {disclose}"
    if fail is not None and fail < disclose:
        return "disclosure_after_failed_verification", [fail, disclose], f"Verification failed at turn {fail}; amount disclosed at turn {disclose}"
    return "disclosure_before_verification", [t for t in (disclose, ok) if t], \
        f"Amount disclosed at turn {disclose}; verification {'at turn ' + str(ok) if ok else 'never completed'}"
