"""
Synthetic data generator for the Audit Evidence Pack Agent (CO-04).

Generates D1 (thin), D4, D5, D10, D11, D12, notice dispatch history, holiday calendar,
collector roster, certification register, 3 audit requests with samples, and a ground-truth
gap key computed by a reference checker over the generated data.

Run:  python generate_data.py            (fixed seed -> identical output every time)
"""
import os, random, math
from datetime import datetime, date, timedelta, time
import pandas as pd

SEED = 42
rng = random.Random(SEED)
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(OUT, "audit_requests"), exist_ok=True)
os.makedirs(os.path.join(OUT, "ground_truth"), exist_ok=True)

IST = timedelta(hours=5, minutes=30)
P_START, P_END = date(2026, 1, 1), date(2026, 6, 30)        # contact data period

# --------------------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------------------
CITIES = [("Bengaluru", "KA"), ("Mysuru", "KA"), ("Chennai", "TN"), ("Coimbatore", "TN"),
          ("Mumbai", "MH"), ("Pune", "MH"), ("Hyderabad", "TG"), ("New Delhi", "DL"),
          ("Lucknow", "UP"), ("Ahmedabad", "GJ"), ("Kolkata", "WB"), ("Kochi", "KL")]
LANG = {"KA": ["kn", "en", "hi-en"], "TN": ["ta", "en"], "TG": ["te", "en", "hi-en"],
        "MH": ["hi-en", "en"], "DL": ["hi-en", "en"], "UP": ["hi-en"], "GJ": ["hi-en", "en"],
        "WB": ["en", "hi-en"], "KL": ["en"]}
FIRST = ["Ramesh", "Suresh", "Priya", "Lakshmi", "Arjun", "Kavya", "Mohammed", "Fatima", "Rahul",
         "Anjali", "Venkatesh", "Deepa", "Sanjay", "Meena", "Karthik", "Divya", "Imran", "Pooja",
         "Ganesh", "Swati", "Naveen", "Rekha", "Vikram", "Asha", "Harish", "Nandini", "Manoj", "Sunita"]
LAST = ["Kumar", "Reddy", "Sharma", "Iyer", "Patil", "Nair", "Khan", "Gowda", "Das", "Singh",
        "Rao", "Menon", "Joshi", "Shetty", "Pillai", "Verma", "Naidu", "Mehta", "Banerjee", "Shaikh"]
PRODUCTS = ["Personal Loan", "Two Wheeler Loan", "Consumer Durable Loan", "Credit Card", "Business Loan"]
LENDERS = {"L001": 700, "L002": 650, "L003": 650}
LENDER_AGENCIES = {"L001": ["AG01", "AG02"], "L002": ["AG03", "AG04"], "L003": ["AG05", "AG01"]}
AGENCY_NAMES = {"AG01": "Sahyog Recovery Services", "AG02": "Pragati Collections",
                "AG03": "Vishwas Credit Solutions", "AG04": "Samadhan Field Services",
                "AG05": "Dakshin Recovery Partners"}

# Synthetic holiday calendar (dates are representative, not an official gazette)
NATIONAL = {
    date(2026, 1, 26): "Republic Day", date(2026, 3, 4): "Holi", date(2026, 3, 20): "Id-ul-Fitr",
    date(2026, 3, 26): "Ram Navami", date(2026, 3, 31): "Mahavir Jayanti", date(2026, 4, 3): "Good Friday",
    date(2026, 4, 14): "Dr. Ambedkar Jayanti", date(2026, 5, 1): "Buddha Purnima",
    date(2026, 5, 27): "Id-ul-Zuha (Bakrid)", date(2026, 6, 26): "Muharram",
    date(2026, 8, 15): "Independence Day", date(2026, 9, 4): "Janmashtami",
    date(2026, 10, 2): "Gandhi Jayanti", date(2026, 10, 20): "Dussehra", date(2026, 11, 9): "Diwali",
    date(2026, 11, 24): "Guru Nanak Jayanti", date(2026, 12, 25): "Christmas",
    date(2027, 1, 26): "Republic Day", date(2027, 3, 10): "Id-ul-Fitr", date(2027, 3, 22): "Holi",
    date(2027, 3, 26): "Good Friday", date(2027, 4, 14): "Dr. Ambedkar Jayanti",
    date(2027, 5, 17): "Id-ul-Zuha (Bakrid)", date(2027, 8, 15): "Independence Day",
    date(2027, 10, 2): "Gandhi Jayanti", date(2027, 10, 29): "Diwali", date(2027, 12, 25): "Christmas",
}
STATE_HOL = {
    "KA": {date(2026, 3, 19): "Ugadi", date(2026, 5, 4): "Basava Jayanti", date(2026, 11, 1): "Kannada Rajyotsava",
           date(2027, 4, 7): "Ugadi", date(2027, 11, 1): "Kannada Rajyotsava"},
    "TN": {date(2026, 1, 15): "Pongal", date(2026, 1, 16): "Thiruvalluvar Day", date(2026, 1, 17): "Uzhavar Thirunal",
           date(2026, 4, 15): "Tamil New Year (observed)", date(2027, 1, 15): "Pongal", date(2027, 4, 14): "Tamil New Year"},
    "MH": {date(2026, 2, 19): "Chhatrapati Shivaji Maharaj Jayanti", date(2026, 3, 19): "Gudi Padwa",
           date(2026, 5, 1): "Maharashtra Day", date(2027, 4, 7): "Gudi Padwa", date(2027, 5, 1): "Maharashtra Day"},
    "TG": {date(2026, 1, 14): "Bhogi", date(2026, 3, 19): "Ugadi", date(2026, 6, 2): "Telangana Formation Day",
           date(2026, 10, 10): "Bathukamma", date(2027, 6, 2): "Telangana Formation Day"},
    "DL": {date(2026, 2, 5): "Delhi local holiday (synthetic)", date(2027, 2, 5): "Delhi local holiday (synthetic)"},
    "UP": {date(2026, 1, 24): "UP Diwas", date(2026, 2, 16): "Maha Shivratri (state)", date(2027, 1, 24): "UP Diwas"},
    "GJ": {date(2026, 1, 14): "Uttarayan", date(2026, 5, 1): "Gujarat Sthapna Divas", date(2027, 1, 14): "Uttarayan"},
    "WB": {date(2026, 1, 23): "Netaji Jayanti", date(2026, 4, 15): "Bengali New Year",
           date(2026, 10, 19): "Durga Puja (Saptami)", date(2027, 1, 23): "Netaji Jayanti"},
    "KL": {date(2026, 1, 2): "Mannam Jayanti", date(2026, 4, 15): "Vishu (observed)", date(2026, 8, 26): "Thiruvonam",
           date(2027, 9, 14): "Thiruvonam"},
}


def is_business_day(d, state):
    """Per POL-GEN-006: excludes Sundays, 2nd & 4th Saturdays, national holidays, state holidays."""
    if d.weekday() == 6:
        return False
    if d.weekday() == 5 and ((d.day - 1) // 7 + 1) in (2, 4):
        return False
    if d in NATIONAL or d in STATE_HOL.get(state, {}):
        return False
    return True


def add_business_days(d, n, state):
    cur, c = d, 0
    while c < n:
        cur += timedelta(days=1)
        if is_business_day(cur, state):
            c += 1
    return cur


def business_days_between(a, b, state):
    """number of business days in (a, b]"""
    n, cur = 0, a
    while cur < b:
        cur += timedelta(days=1)
        if is_business_day(cur, state):
            n += 1
    return n


def rand_date(a, b):
    return a + timedelta(days=rng.randint(0, (b - a).days))


def rand_time(h1, m1, h2, m2):
    s1, s2 = h1 * 3600 + m1 * 60, h2 * 3600 + m2 * 60
    s = rng.randint(s1, s2)
    return time(s // 3600, (s % 3600) // 60, s % 60)


def mask_phone():
    return f"+91-{rng.choice('6789')}XXXXXX{rng.randint(100, 999)}"


# --------------------------------------------------------------------------------------
# D11 Template registry
# --------------------------------------------------------------------------------------
templates = []
WA_TEXTS = [
    "Dear {{1}}, your EMI of Rs {{2}} for loan a/c ending {{3}} is due on {{4}}. Pay here: {{5}}",
    "Hi {{1}}, a friendly reminder that Rs {{2}} is overdue on your loan a/c ending {{3}}. Pay now: {{4}}",
    "Dear {{1}}, we could not reach you. Please call us on {{2}} regarding your loan a/c ending {{3}}.",
    "{{1}} ji, aapke loan a/c {{2}} par Rs {{3}} baaki hai. Kripya {{4}} tak bhugtan karein: {{5}}",
    "Dear {{1}}, thank you for your promise to pay Rs {{2}} on {{3}}. Pay securely: {{4}}",
]
LANGS_T = ["en", "hi", "kn", "ta", "te"]
tid = 1
for i in range(36):
    templates.append(dict(template_id=f"TPL-WA-{tid:03d}", channel="WHATSAPP", language=LANGS_T[i % 5],
                          template_name=f"wa_reminder_{i:02d}", registered_text=WA_TEXTS[i % len(WA_TEXTS)],
                          approval_status="APPROVED",
                          approved_date=rand_date(date(2024, 6, 1), date(2025, 11, 30)),
                          registered_by="Compliance-Comms"))
    tid += 1
for i in range(20):
    templates.append(dict(template_id=f"TPL-SMS-{i + 1:03d}", channel="SMS", language=LANGS_T[i % 5],
                          template_name=f"sms_reminder_{i:02d}",
                          registered_text="Dear Customer, Rs {#var#} is due on your loan a/c {#var#}. Pay at {#var#} -LENDER",
                          approval_status="APPROVED", approved_date=rand_date(date(2024, 6, 1), date(2025, 11, 30)),
                          registered_by="Compliance-Comms"))
# trap templates
trap_tpl = {
    "TPL-WA-037": dict(approval_status="REJECTED", approved_date=None, template_name="wa_urgent_legal_warning",
                       registered_text="FINAL WARNING {{1}}: legal action will be initiated today unless Rs {{2}} is paid."),
    "TPL-WA-038": dict(approval_status="PENDING", approved_date=None, template_name="wa_settlement_offer",
                       registered_text="Dear {{1}}, special one-time settlement offer of Rs {{2}} valid till {{3}}."),
    "TPL-WA-039": dict(approval_status="APPROVED", approved_date=date(2026, 3, 16), template_name="wa_field_visit_notice",
                       registered_text="Dear {{1}}, our representative will visit you on {{2}} regarding a/c ending {{3}}."),
    "TPL-WA-040": dict(approval_status="APPROVED", approved_date=date(2026, 5, 11), template_name="wa_restructure_offer",
                       registered_text="Dear {{1}}, you may be eligible to restructure your loan a/c ending {{2}}. Reply YES."),
}
for k, v in trap_tpl.items():
    templates.append(dict(template_id=k, channel="WHATSAPP", language="en", registered_by="Compliance-Comms", **v))
TPL = {t["template_id"]: t for t in templates}
WA_OK_TPL = [t["template_id"] for t in templates if t["channel"] == "WHATSAPP" and t["approval_status"] == "APPROVED"
             and t["approved_date"] and t["approved_date"] < date(2026, 1, 1)]
SMS_TPL = [t["template_id"] for t in templates if t["channel"] == "SMS"]

# --------------------------------------------------------------------------------------
# D12 Policy rules
# --------------------------------------------------------------------------------------
policy = [
    ("POL-GEN-001", "Fair Practices Code - Collections v4.2", "ALL", "CALLING_HOURS", "VOICE", "allowed_window", "08:00-19:00", "borrower local time", "2024-01-01", "",
     "Recovery agents shall call borrowers only between 08:00 hrs and 19:00 hrs, borrower local time. Applies to every outbound call attempt."),
    ("POL-GEN-002A", "Fair Practices Code - Collections v3.0", "ALL", "DAILY_CALL_CAP", "VOICE", "max_attempts_per_account_per_day", "4", "attempts", "2023-04-01", "2025-12-31",
     "No more than four call attempts per account per calendar day. (Superseded by v4.2)"),
    ("POL-GEN-002", "Fair Practices Code - Collections v4.2", "ALL", "DAILY_CALL_CAP", "VOICE", "max_attempts_per_account_per_day", "3", "attempts", "2026-01-01", "",
     "No more than three outbound call attempts per account per calendar day (borrower local date). Each unique attempt counts, whether or not connected."),
    ("POL-GEN-003", "Fair Practices Code - Collections v4.2", "ALL", "WEEKLY_CALL_CAP", "VOICE", "max_attempts_per_account_per_week", "10", "attempts", "2026-01-01", "",
     "No more than ten outbound call attempts per account per calendar week (Monday to Sunday)."),
    ("POL-GEN-004", "Notice Management Policy v2.1", "ALL", "NOTICE_DEADLINE", "NOTICE", "DEMAND_NOTICE", "7", "business days", "2025-04-01", "",
     "A demand notice shall be served on the borrower within 7 business days of the trigger date. Service means delivery to the borrower (proof of delivery), not dispatch."),
    ("POL-GEN-005", "Notice Management Policy v2.1", "ALL", "NOTICE_DEADLINE", "NOTICE", "PRE_LEGAL_NOTICE", "10", "business days", "2025-04-01", "",
     "A pre-legal notice shall be served on the borrower within 10 business days of the trigger date, evidenced by proof of delivery."),
    ("POL-GEN-006", "Notice Management Policy v2.1", "ALL", "BUSINESS_DAY_DEFINITION", "NOTICE", "business_day", "excl. Sundays, 2nd & 4th Saturdays, national holidays, holidays of borrower's state", "", "2025-04-01", "",
     "Business day excludes Sundays, the second and fourth Saturdays of the month, national holidays and public holidays notified in the borrower's state. The trigger date itself is not counted."),
    ("POL-GEN-007", "Digital Communication Policy v1.3", "ALL", "CONSENT", "WHATSAPP", "prior_consent_required", "true", "", "2024-01-01", "",
     "WhatsApp messages may be sent only where the borrower has given WhatsApp consent before the message and has not opted out at the time of the message."),
    ("POL-GEN-008", "Digital Communication Policy v1.3", "ALL", "TEMPLATE_APPROVAL", "WHATSAPP", "approved_template_required", "true", "", "2024-01-01", "",
     "Every WhatsApp message must use a template registered for the WhatsApp channel and approved on or before the date of sending."),
    ("POL-GEN-009", "Fair Practices Code - Collections v4.2", "ALL", "IDENTITY_VERIFICATION", "VOICE", "verify_before_disclosure", "true", "", "2024-01-01", "",
     "Before discussing or disclosing any amount due, the agent must establish that the person on the call is the borrower (e.g. name plus date of birth). Dues must never be disclosed to third parties or after failed verification."),
    ("POL-GEN-010", "Call Recording & Retention SOP v1.1", "ALL", "CALL_RECORDING", "VOICE", "record_all_connected_calls", "true", "", "2024-01-01", "",
     "Every connected call (including wrong-number connections) must be recorded and the recording/transcript retained for at least 24 months."),
    ("POL-GEN-011", "Recovery Agent Engagement Policy v2.0", "ALL", "AGENT_CERTIFICATION", "VOICE", "valid_certificate_on_call_date", "true", "", "2024-01-01", "",
     "Only recovery agents holding a valid DRA certificate on the date of the call may contact borrowers."),
    ("POL-GEN-012", "Policy Governance Note", "ALL", "PRECEDENCE", "ALL", "lender_policy_precedence", "stricter applies", "", "2024-01-01", "",
     "Where a lender-specific policy is stricter than the general Fair Practices Code, the lender policy applies."),
    ("POL-L002-004", "L002 Collections Policy Addendum 2025", "L002", "CALLING_HOURS", "VOICE", "allowed_window", "09:00-18:00", "borrower local time", "2025-10-01", "",
     "For L002 borrowers, calls are permitted only between 09:00 hrs and 18:00 hrs, borrower local time."),
    ("POL-L002-005", "L002 Collections Policy Addendum 2026", "L002", "DAILY_CALL_CAP", "VOICE", "max_attempts_per_account_per_day", "2", "attempts", "2026-05-01", "",
     "With effect from 1 May 2026, no more than two call attempts per L002 account per calendar day."),
    ("POL-L001-020", "L001 Settlement Delegation Grid", "L001", "DELEGATION", "ALL", "settlement_waiver_limit_manager", "15", "percent", "2025-01-01", "",
     "Branch managers may approve settlement waivers up to 15% of principal outstanding."),
    ("POL-L003-011", "L003 Field Visit Policy", "L003", "FIELD_VISIT", "FIELD", "visit_hours", "09:00-18:00", "", "2025-01-01", "",
     "Field visits only between 09:00 and 18:00 hrs; visits to be logged in the field app."),
    ("POL-GEN-013", "Grievance Redressal Policy v1.0", "ALL", "GRIEVANCE", "ALL", "acknowledge_within", "2", "business days", "2024-01-01", "",
     "Borrower grievances shall be acknowledged within 2 business days."),
]
policy_df = pd.DataFrame(policy, columns=["rule_id", "document_name", "lender_id", "rule_type", "channel", "parameter",
                                          "value", "unit", "effective_from", "effective_to", "clause_text"])


def hours_window(lender):
    return (time(9, 0), time(18, 0)) if lender == "L002" else (time(8, 0), time(19, 0))


def hours_rule(lender):
    return "POL-L002-004" if lender == "L002" else "POL-GEN-001"


def daily_cap(lender, d):
    if lender == "L002" and d >= date(2026, 5, 1):
        return 2, "POL-L002-005"
    return 3, "POL-GEN-002"


# --------------------------------------------------------------------------------------
# Collectors & certification register
# --------------------------------------------------------------------------------------
collectors, certs = [], []
agencies = list(AGENCY_NAMES)
cid = 1
for ag in agencies:
    for _ in range(24):
        collectors.append(dict(collector_id=f"COL-{cid:04d}", collector_name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                               agency_id=ag, agency_name=AGENCY_NAMES[ag],
                               joining_date=rand_date(date(2023, 1, 1), date(2025, 5, 31)), status="ACTIVE"))
        cid += 1
COL = {c["collector_id"]: c for c in collectors}
cert_no = 1


def add_cert(col, vf, vt):
    global cert_no
    certs.append(dict(cert_id=f"CERT-{cert_no:05d}", collector_id=col, cert_type="IIBF Debt Recovery Agent (DRA)",
                      certificate_number=f"DRA/{vf.year}/{rng.randint(100000, 999999)}", valid_from=vf, valid_to=vt))
    cert_no += 1


# trap collectors: 2 per agency type mix
trap_cols = {}  # collector_id -> dict(kind, good_windows[(a,b)], bad_window(a,b), boundary_date)
by_ag = {ag: [c["collector_id"] for c in collectors if c["agency_id"] == ag] for ag in agencies}
kinds = ["expired", "renewal_gap", "expired", "not_yet_valid", "renewal_gap"]
for i, ag in enumerate(agencies):
    for j, kind in enumerate([kinds[i], kinds[(i + 2) % 5]]):
        cidx = by_ag[ag][j]
        trap_cols[cidx] = dict(kind=kind)
for c in collectors:
    k = c["collector_id"]
    if k not in trap_cols:
        s = rand_date(date(2024, 8, 1), date(2025, 6, 30))
        add_cert(k, s, s + timedelta(days=364))
        add_cert(k, s + timedelta(days=365), s + timedelta(days=729))
        continue
    t = trap_cols[k]
    if t["kind"] == "expired":
        vt = rand_date(date(2026, 1, 20), date(2026, 5, 25))
        add_cert(k, vt - timedelta(days=364), vt)
        t.update(good=(P_START, vt), bad=(vt + timedelta(days=1), min(vt + timedelta(days=25), P_END)), boundary=vt)
        c["status"] = "ACTIVE"
    elif t["kind"] == "renewal_gap":
        vt = rand_date(date(2026, 1, 20), date(2026, 4, 30))
        gap = rng.randint(12, 30)
        add_cert(k, vt - timedelta(days=364), vt)
        add_cert(k, vt + timedelta(days=gap + 1), vt + timedelta(days=gap + 365))
        t.update(good=(vt + timedelta(days=gap + 1), P_END), bad=(vt + timedelta(days=1), vt + timedelta(days=gap)), boundary=vt)
    else:  # not yet valid
        vf = rand_date(date(2026, 2, 1), date(2026, 4, 30))
        add_cert(k, vf, vf + timedelta(days=364))
        c["joining_date"] = vf - timedelta(days=40)
        t.update(good=(vf, P_END), bad=(vf - timedelta(days=25), vf - timedelta(days=1)), boundary=vf)

# --------------------------------------------------------------------------------------
# Borrowers (internal) and D1 accounts
# --------------------------------------------------------------------------------------
borrowers = {}
for b in range(1, 1801):
    city, st = rng.choice(CITIES)
    borrowers[f"BRW{b:06d}"] = dict(name=f"{rng.choice(FIRST)} {rng.choice(LAST)}", city=city, state=st,
                                    dob=rand_date(date(1965, 1, 1), date(2000, 12, 31)),
                                    lang=rng.choice(LANG[st]))
bids = list(borrowers)
accounts = []
acc_no = 100001
for lender, n in LENDERS.items():
    for _ in range(n):
        accounts.append(dict(account_id=f"ACC{acc_no}", lender_id=lender))
        acc_no += 1
rng.shuffle(accounts)
for i, a in enumerate(accounts):
    a["borrower_id"] = bids[i] if i < len(bids) else rng.choice(bids)   # 200 borrowers hold a 2nd account
accounts.sort(key=lambda a: a["account_id"])
for a in accounts:
    b = borrowers[a["borrower_id"]]
    sanc = rng.choice([50000, 75000, 100000, 150000, 200000, 300000, 500000])
    dpd = rng.choice([rng.randint(1, 29), rng.randint(30, 59), rng.randint(60, 89), rng.randint(90, 180)])
    a.update(product=rng.choice(PRODUCTS), sanction_amount=sanc,
             total_dues=round(sanc * rng.uniform(0.05, 0.6), 0), dpd=dpd,
             bucket="X" if dpd < 30 else "B1" if dpd < 60 else "B2" if dpd < 90 else "NPA",
             disbursal_date=rand_date(date(2022, 1, 1), date(2025, 6, 30)),
             city=b["city"], state=b["state"], branch=f"{b['city']} Main",
             legal_flag="Y" if dpd >= 90 and rng.random() < 0.4 else "N",
             agency_id=rng.choice(LENDER_AGENCIES[a["lender_id"]]))
ACC = {a["account_id"]: a for a in accounts}

# --------------------------------------------------------------------------------------
# D4 Contact history
# --------------------------------------------------------------------------------------
contacts = []
cno = 10000001


def new_contact(acc, channel, ts, **kw):
    global cno
    a = ACC[acc]
    row = dict(contact_id=f"CT{cno}", account_id=acc, channel=channel, direction="OUTBOUND",
               number_or_handle=a.setdefault("phone", mask_phone()), contact_ts=ts, template_id="",
               collector_id="", agency_id=a["agency_id"], disposition="", duration_sec=0)
    row.update(kw)
    contacts.append(row)
    cno += 1
    return row


normal_pool = {ag: [c for c in by_ag[ag] if c not in trap_cols] for ag in agencies}
CONNECTED = ["CONNECTED_PTP", "CONNECTED_RTP", "CONNECTED_CALLBACK", "CONNECTED_DISPUTE"]


def voice_disposition():
    r = rng.random()
    if r < 0.12:
        return rng.choice(CONNECTED), rng.randint(45, 420)
    if r < 0.13:
        return "WRONG_NUMBER", rng.randint(15, 60)
    return rng.choice(["NO_ANSWER", "NO_ANSWER", "BUSY", "SWITCHED_OFF", "NOT_REACHABLE"]), 0


def voice_call(acc, d, t):
    a = ACC[acc]
    disp, dur = voice_disposition()
    return new_contact(acc, "VOICE", datetime.combine(d, t), collector_id=rng.choice(normal_pool[a["agency_id"]]),
                       disposition=disp, duration_sec=dur)


all_days = [P_START + timedelta(days=i) for i in range((P_END - P_START).days + 1)]
for a in accounts:
    acc, lender = a["account_id"], a["lender_id"]
    (h1, h2) = hours_window(lender)
    nv = rng.randint(8, 35)
    days = sorted(rng.sample(all_days, nv))
    for d in days:
        k = 2 if rng.random() < 0.08 else 1
        for _ in range(k):
            voice_call(acc, d, rand_time(h1.hour, 5, h2.hour - 1, 55))
    # --- hours traps / near misses
    r = rng.random()
    if r < 0.05:
        for _ in range(rng.randint(1, 2)):
            d = rng.choice(all_days)
            if lender == "L002" and rng.random() < 0.5:   # outside L002 window but inside general window
                t = rng.choice([rand_time(8, 0, 8, 50), rand_time(18, 10, 18, 55)])
            else:
                t = rng.choice([rand_time(7, 0, 7, 50), rand_time(19, 10, 21, 30)])
            voice_call(acc, d, t)
    elif r < 0.15:   # near miss, compliant
        d = rng.choice(all_days)
        t = rand_time(h1.hour, 0, h1.hour, 1) if rng.random() < 0.5 else rand_time(h2.hour - 1, 58, h2.hour - 1, 59)
        voice_call(acc, d, t)
    # --- frequency traps
    r = rng.random()
    if r < 0.04:       # daily cap breach
        d = rng.choice(all_days)
        for _ in range(rng.randint(4, 5)):
            voice_call(acc, d, rand_time(h1.hour, 5, h2.hour - 1, 55))
    elif r < 0.06:     # weekly cap breach without daily breach
        wk_start = rng.choice([d for d in all_days if d.weekday() == 0 and d <= P_END - timedelta(days=6)])
        for i, k in enumerate([3, 3, 3, 2]):
            for _ in range(k):
                voice_call(acc, wk_start + timedelta(days=i), rand_time(h1.hour, 5, h2.hour - 1, 55))
    elif r < 0.12:     # exactly 3 in a day (compliant except L002 after 1 May)
        d = rng.choice(all_days)
        rows = [voice_call(acc, d, rand_time(h1.hour, 5, h2.hour - 1, 55)) for _ in range(3)]
        if rng.random() < 0.3:
            contacts.append(dict(rows[0]))   # exact duplicate row (same contact_id) - dedup bait
    # --- WhatsApp
    if rng.random() < 0.9:
        for d in sorted(rng.sample(all_days, rng.randint(2, 8))):
            new_contact(acc, "WHATSAPP", datetime.combine(d, rand_time(9, 0, 20, 0)), template_id=rng.choice(WA_OK_TPL),
                        disposition=rng.choice(["SENT", "DELIVERED", "READ", "READ"]))
    # --- SMS (no checks, realism)
    for d in rng.sample(all_days, rng.randint(0, 4)):
        new_contact(acc, "SMS", datetime.combine(d, rand_time(9, 0, 20, 0)), template_id=rng.choice(SMS_TPL),
                    disposition="DELIVERED")

# template traps on WhatsApp messages (~4% of accounts)
wa_rows = [c for c in contacts if c["channel"] == "WHATSAPP"]
wa_by_acc = {}
for c in wa_rows:
    wa_by_acc.setdefault(c["account_id"], []).append(c)
for acc, rows in wa_by_acc.items():
    r = rng.random()
    if r < 0.04:
        row = rng.choice(rows)
        choice = rng.choice(["TPL-WA-037", "TPL-WA-038", "TPL-WA-039", "TPL-WA-040", "SMS"])
        row["template_id"] = rng.choice(SMS_TPL) if choice == "SMS" else choice
    elif r < 0.07:   # late-approved template used AFTER approval -> compliant near miss
        row = rng.choice(rows)
        tp = rng.choice(["TPL-WA-039", "TPL-WA-040"])
        if row["contact_ts"].date() >= TPL[tp]["approved_date"]:
            row["template_id"] = tp

# trap collectors: reassign some calls into their good and bad windows
voice_rows = [c for c in contacts if c["channel"] == "VOICE"]
for colid, t in trap_cols.items():
    ag = COL[colid]["agency_id"]
    pool = [c for c in voice_rows if c["agency_id"] == ag]
    bad = [c for c in pool if t["bad"][0] <= c["contact_ts"].date() <= t["bad"][1]]
    good = [c for c in pool if t["good"][0] <= c["contact_ts"].date() <= t["good"][1]]
    for c in rng.sample(bad, min(len(bad), rng.randint(8, 14))):
        c["collector_id"] = colid
    for c in rng.sample(good, min(len(good), 40)):
        c["collector_id"] = colid
    bd = [c for c in pool if c["contact_ts"].date() == t["boundary"]]
    for c in bd[:3]:
        c["collector_id"] = colid
# unknown collector
for c in rng.sample([c for c in voice_rows if c["agency_id"] == "AG04"], 8):
    c["collector_id"] = "COL-0999"


# collector ID format drift by agency dialer
def fmt_col(colid, ag):
    n = int(colid.split("-")[1])
    if ag == "AG04":
        return f"col{n}"
    if ag == "AG05":
        return f"COL{n:04d}"
    return colid


for c in contacts:
    if c["collector_id"]:
        c["collector_id_raw"] = fmt_col(c["collector_id"], c["agency_id"])

# --------------------------------------------------------------------------------------
# D10 Consent registry (UTC)
# --------------------------------------------------------------------------------------
consents = []
cons_no = 1


def add_consent(bid, ch, cap_utc, opt_utc=None, src=None):
    global cons_no
    consents.append(dict(consent_id=f"CNS{cons_no:07d}", borrower_id=bid, channel=ch,
                         consent_status="OPTED_OUT" if opt_utc else "ACTIVE",
                         captured_at=cap_utc.replace(microsecond=0),
                         opt_out_at=opt_utc.replace(microsecond=0) if opt_utc else None,
                         consent_source=src or rng.choice(["APP_ONBOARDING", "LOAN_AGREEMENT_ESIGN", "WEB_FORM", "BRANCH_FORM"])))
    cons_no += 1


wa_by_brw = {}
for c in contacts:
    if c["channel"] == "WHATSAPP":
        wa_by_brw.setdefault(ACC[c["account_id"]]["borrower_id"], []).append(c)
consent_trap = {}
for bid, b in borrowers.items():
    base = datetime.combine(rand_date(date(2022, 1, 1), date(2025, 9, 30)), rand_time(3, 0, 14, 0))
    add_consent(bid, "SMS", base)
    if rng.random() < 0.8:
        add_consent(bid, "VOICE", base)
    msgs = sorted(wa_by_brw.get(bid, []), key=lambda c: c["contact_ts"])
    if not msgs:
        if rng.random() < 0.5:
            add_consent(bid, "WHATSAPP", base)
        continue
    utc = [m["contact_ts"] - IST for m in msgs]
    r = rng.random()
    if r < 0.03:
        consent_trap[bid] = "no_consent_record"
    elif r < 0.06:      # late by minutes (hidden by IST vs UTC)
        add_consent(bid, "WHATSAPP", utc[0] + timedelta(minutes=rng.randint(3, 300)), src="WHATSAPP_OPTIN")
        consent_trap[bid] = "late_minutes"
    elif r < 0.08:      # late by days
        add_consent(bid, "WHATSAPP", utc[0] + timedelta(days=rng.randint(2, 20), minutes=rng.randint(0, 600)), src="WHATSAPP_OPTIN")
        consent_trap[bid] = "late_days"
    elif r < 0.11 and len(msgs) >= 3:   # opted out, still messaged
        k = rng.randint(1, len(msgs) - 1)
        opt = utc[k - 1] + (utc[k] - utc[k - 1]) * rng.uniform(0.2, 0.8)
        add_consent(bid, "WHATSAPP", base, opt_utc=opt)
        if rng.random() < 0.4 and k + 1 < len(msgs):   # re-consented later
            add_consent(bid, "WHATSAPP", utc[k] + (utc[k + 1] - utc[k]) * 0.5, src="WHATSAPP_OPTIN")
        consent_trap[bid] = "opt_out"
    elif r < 0.16:      # near miss: consent minutes before the first message
        add_consent(bid, "WHATSAPP", utc[0] - timedelta(minutes=rng.randint(2, 40)), src="WHATSAPP_OPTIN")
    elif r < 0.19:      # near miss: opted out after last message
        add_consent(bid, "WHATSAPP", base, opt_utc=utc[-1] + timedelta(hours=rng.randint(1, 72)))
    else:
        add_consent(bid, "WHATSAPP", base)
for c in consents:
    c["dnd_status"] = "N"
for bid in rng.sample(bids, 180):
    for c in consents:
        if c["borrower_id"] == bid:
            c["dnd_status"] = "Y"

# --------------------------------------------------------------------------------------
# D5 Call transcripts (UTC)
# --------------------------------------------------------------------------------------
LINES = {
    "en": dict(
        greet="Good {tod}, this is {agent} calling from {agency} on behalf of your lender. Am I speaking with {name}?",
        yes="Yes, speaking.", ask_dob="For security, could you please confirm your date of birth?",
        dob="It is {dob}.", verified="Thank you, your identity is verified.",
        disclose="I am calling about your {product} account ending {last4}. The total amount due is Rs {amt}.",
        context="I am calling regarding your loan account with us.",
        wrong_dob="It is {wdob}.", mismatch="Sorry, that does not match our records.",
        refuse="Why should I share that with you? I won't.",
        wrongno="No, there is no {name} here. You have the wrong number.",
        sorry="Apologies for the inconvenience. We will update our records. Thank you.",
        tp_disclose="Please inform {first} that Rs {amt} is overdue on his loan and he must pay immediately.",
        ptp="I will pay Rs {part} by next Friday.", rtp="I cannot pay right now, I lost my job.",
        cb="Please call me back in the evening.", disp="I have already paid this, I dispute the amount.",
        close="Thank you for your time. Have a good day."),
    "hi-en": dict(
        greet="Namaste, main {agent} bol raha hoon {agency} se, aapke lender ki taraf se. Kya meri baat {name} ji se ho rahi hai?",
        yes="Haan, bol raha hoon.", ask_dob="Verification ke liye apni date of birth bata dijiye.",
        dob="{dob}.", verified="Dhanyavaad, aapka verification ho gaya hai.",
        disclose="Aapke {product} account ending {last4} par total Rs {amt} baaki hai.",
        context="Main aapke loan account ke baare mein call kar raha hoon.",
        wrong_dob="{wdob}.", mismatch="Maaf kijiye, yeh hamare records se match nahi ho raha.",
        refuse="Main aapko kyun bataun? Nahi bataunga.",
        wrongno="Yahan koi {name} nahi hai, wrong number hai.",
        sorry="Asuvidha ke liye maafi, hum records update kar denge. Dhanyavaad.",
        tp_disclose="{first} ko bata dijiye ki unke loan par Rs {amt} overdue hai, turant bharna padega.",
        ptp="Main agle Friday tak Rs {part} bhar dunga.", rtp="Abhi nahi de sakta, naukri chali gayi hai.",
        cb="Shaam ko call kijiye.", disp="Maine already pay kar diya hai, amount galat hai.",
        close="Aapka samay dene ke liye dhanyavaad."),
    "kn": dict(
        greet="Namaskara, naanu {agent}, {agency} inda maatadtiddini. {name} avaru maatadtiddira?",
        yes="Haudu, heli.", ask_dob="Verification ge dayavittu nimma date of birth tilisi.",
        dob="{dob}.", verified="Dhanyavadagalu, nimma verification aaytu.",
        disclose="Nimma {product} account ending {last4} mele ottu Rs {amt} baaki ide.",
        context="Nimma loan account bagge call maadtiddini.",
        wrong_dob="{wdob}.", mismatch="Kshamisi, idu namma records jothe match aagtilla.",
        refuse="Adanna nimge yaake heLbeku? HeLalla.",
        wrongno="Illi {name} antha yaaru illa, wrong number.",
        sorry="Tondarege kshamisi, records update maadtivi. Dhanyavadagalu.",
        tp_disclose="{first} avarige heLi, avara loan mele Rs {amt} overdue ide, takshana kattabeku.",
        ptp="Mundina Friday olage Rs {part} kattuttene.", rtp="Eega kattoke aagalla, kelasa hogide.",
        cb="Sanje call maadi.", disp="Naanu already pay maadiddini, amount tappu.",
        close="Nimma samayakke dhanyavadagalu."),
    "ta": dict(
        greet="Vanakkam, naan {agent}, {agency} la irundhu pesuren. {name} avargala?",
        yes="Aamaa, sollunga.", ask_dob="Verification-kku unga date of birth sollunga.",
        dob="{dob}.", verified="Nandri, verification mudinjadhu.",
        disclose="Unga {product} account ending {last4} la total Rs {amt} pending irukku.",
        context="Unga loan account pathi pesa call panren.",
        wrong_dob="{wdob}.", mismatch="Mannikkavum, adhu engal records oda match aagala.",
        refuse="Adha naan ungalukku yen sollanum? Solla maaten.",
        wrongno="Inga {name} nu yaarum illa, wrong number.",
        sorry="Mannikkavum, records update panrom. Nandri.",
        tp_disclose="{first} kitta sollunga, avar loan la Rs {amt} overdue, udane kattanum.",
        ptp="Adutha Friday kulla Rs {part} kattiduven.", rtp="Ippo kattamudiyaadhu, velai poyiduchu.",
        cb="Saayangaalam call pannunga.", disp="Naan already pay pannitten, amount thappu.",
        close="Ungal neram kuduthadhukku nandri."),
    "te": dict(
        greet="Namaskaram, nenu {agent}, {agency} nundi matladutunnanu. {name} garu matladutunnara?",
        yes="Avunu, cheppandi.", ask_dob="Verification kosam mee date of birth cheppandi.",
        dob="{dob}.", verified="Dhanyavadalu, verification ayyindi.",
        disclose="Mee {product} account ending {last4} meeda total Rs {amt} baaki undi.",
        context="Mee loan account gurinchi call chestunnanu.",
        wrong_dob="{wdob}.", mismatch="Kshaminchandi, adi maa records tho match avvaledu.",
        refuse="Adi meeku enduku cheppali? Cheppanu.",
        wrongno="Ikkada {name} evaru leru, wrong number.",
        sorry="Ibbandiki kshaminchandi, records update chestamu. Dhanyavadalu.",
        tp_disclose="{first} gariki cheppandi, vari loan meeda Rs {amt} overdue undi, ventane kattali.",
        ptp="Vachhe Friday lopu Rs {part} kadatanu.", rtp="Ippudu kattalenu, udyogam poyindi.",
        cb="Sayantram call cheyandi.", disp="Nenu already pay chesanu, amount tappu.",
        close="Mee samayaniki dhanyavadalu."),
}
OUTCOME_LINE = {"CONNECTED_PTP": "ptp", "CONNECTED_RTP": "rtp", "CONNECTED_CALLBACK": "cb", "CONNECTED_DISPUTE": "disp"}

transcripts = []
call_truth = {}      # internal: call_id -> outcome (never exported into D5)
connected_calls = [c for c in contacts if c["channel"] == "VOICE" and c["disposition"] in CONNECTED + ["WRONG_NUMBER"]]
seen = set()
for c in connected_calls:
    if c["contact_id"] in seen:
        continue
    seen.add(c["contact_id"])
    if rng.random() < 0.025:
        call_truth[c["contact_id"]] = "transcript_missing"
        continue
    a = ACC[c["account_id"]]
    b = borrowers[a["borrower_id"]]
    lang = b["lang"]
    L = LINES[lang]
    hr = c["contact_ts"].hour
    f = dict(tod="morning" if hr < 12 else "afternoon" if hr < 17 else "evening",
             agent=COL.get(c["collector_id"], {"collector_name": "Ravi"})["collector_name"].split()[0],
             agency=AGENCY_NAMES[c["agency_id"]], name=b["name"], first=b["name"].split()[0],
             dob=b["dob"].strftime("%d %B %Y"), wdob=(b["dob"] + timedelta(days=rng.randint(40, 900))).strftime("%d %B %Y"),
             product=a["product"], last4=a["account_id"][-4:], amt=f"{int(a['total_dues']):,}",
             part=f"{int(a['total_dues'] * 0.3):,}")
    turns = []   # (speaker, key)
    if c["disposition"] == "WRONG_NUMBER":
        if rng.random() < 0.25:
            turns = [("AGENT", "greet"), ("CUSTOMER", "wrongno"), ("AGENT", "tp_disclose"), ("AGENT", "close")]
            outcome = "third_party_disclosure"
        else:
            turns = [("AGENT", "greet"), ("CUSTOMER", "wrongno"), ("AGENT", "sorry")]
            outcome = "ok"
    else:
        r = rng.random()
        end = [("CUSTOMER", OUTCOME_LINE[c["disposition"]]), ("AGENT", "close")]
        if r < 0.025:
            turns = [("AGENT", "greet"), ("CUSTOMER", "yes"), ("AGENT", "disclose"), ("AGENT", "ask_dob"),
                     ("CUSTOMER", "dob"), ("AGENT", "verified")] + end
            outcome = "disclosure_before_verification"
        elif r < 0.035:
            turns = [("AGENT", "greet"), ("CUSTOMER", "yes"), ("AGENT", "ask_dob"),
                     ("CUSTOMER", rng.choice(["wrong_dob", "refuse"])), ("AGENT", "mismatch"), ("AGENT", "disclose")] + end
            outcome = "disclosure_after_failed_verification"
        elif r < 0.15:   # near miss: generic context (no amount) before verification -> compliant
            turns = [("AGENT", "greet"), ("CUSTOMER", "yes"), ("AGENT", "context"), ("AGENT", "ask_dob"),
                     ("CUSTOMER", "dob"), ("AGENT", "verified"), ("AGENT", "disclose")] + end
            outcome = "ok"
        else:
            turns = [("AGENT", "greet"), ("CUSTOMER", "yes"), ("AGENT", "ask_dob"), ("CUSTOMER", "dob"),
                     ("AGENT", "verified"), ("AGENT", "disclose")] + end
            outcome = "ok"
    call_truth[c["contact_id"]] = outcome
    ts = c["contact_ts"] - IST + timedelta(seconds=rng.randint(2, 6))
    for i, (spk, key) in enumerate(turns, 1):
        transcripts.append(dict(call_id=c["contact_id"], account_id=c["account_id"], turn_no=i, speaker=spk,
                                text=L[key].format(**f), language=lang,
                                asr_confidence=round(rng.uniform(0.55, 0.99) if rng.random() < 0.1 else rng.uniform(0.82, 0.99), 2),
                                turn_start_ts=ts.replace(microsecond=0)))
        ts += timedelta(seconds=rng.randint(4, 25))

# --------------------------------------------------------------------------------------
# Notice dispatch history
# --------------------------------------------------------------------------------------
notices = []
nno = 1
DEADLINE = {"DEMAND_NOTICE": 7, "PRE_LEGAL_NOTICE": 10}
for a in accounts:
    st = a["state"]
    for _ in range(rng.choice([0, 1, 1, 2, 2, 3])):
        ntype = "PRE_LEGAL_NOTICE" if a["dpd"] >= 60 and rng.random() < 0.5 else "DEMAND_NOTICE"
        trig = rand_date(date(2025, 12, 1), date(2026, 10, 31))
        dl = add_business_days(trig, DEADLINE[ntype], st)
        dispatch = add_business_days(trig, rng.randint(1, 3), st)
        service = dispatch + timedelta(days=rng.randint(1, 3))
        status = "DELIVERED"
        r = rng.random()
        if r < 0.05:      # dispatched late
            dispatch = dl + timedelta(days=rng.randint(1, 12))
            service = dispatch + timedelta(days=rng.randint(1, 4))
        elif r < 0.09:    # dispatched on time, served late
            service = dl + timedelta(days=rng.randint(1, 12))
        elif r < 0.12:    # no proof of service
            service, status = None, rng.choice(["RETURNED_UNDELIVERED", "IN_TRANSIT"])
        elif r < 0.22:    # near miss: served exactly on deadline (needs state holidays / 2nd-4th Sat logic)
            service = dl
            dispatch = min(dispatch, service - timedelta(days=1))
        if service and service <= dispatch:
            service = dispatch + timedelta(days=1)
        notices.append(dict(notice_id=f"NTC{nno:06d}", account_id=a["account_id"], notice_type=ntype,
                            trigger_event="DPD_60_CROSSED" if ntype == "PRE_LEGAL_NOTICE" else "EMI_BOUNCE",
                            trigger_date=trig, dispatch_date=dispatch,
                            dispatch_mode=rng.choice(["SPEED_POST", "REGISTERED_AD", "COURIER"]),
                            tracking_ref=f"{rng.choice(['EE', 'RA', 'CP'])}{rng.randint(100000000, 999999999)}IN",
                            delivery_status=status, service_date=service))
        nno += 1

# --------------------------------------------------------------------------------------
# Write data CSVs
# --------------------------------------------------------------------------------------
d1 = pd.DataFrame(accounts)[["account_id", "lender_id", "borrower_id", "product", "sanction_amount", "total_dues", "dpd",
                             "bucket", "disbursal_date", "city", "state", "branch", "legal_flag"]]
d1.to_csv(f"{OUT}/d1_account_master_thin.csv", index=False)

d4 = pd.DataFrame(contacts)
d4["collector_id"] = d4["collector_id_raw"].fillna("")
d4["contact_ts"] = pd.to_datetime(d4["contact_ts"]).dt.strftime("%Y-%m-%d %H:%M:%S")
d4 = d4[["contact_id", "account_id", "channel", "direction", "number_or_handle", "contact_ts", "template_id",
         "collector_id", "agency_id", "disposition", "duration_sec"]].sample(frac=1, random_state=SEED)
d4.to_csv(f"{OUT}/d4_contact_history.csv", index=False)

d5 = pd.DataFrame(transcripts)
d5["turn_start_ts"] = pd.to_datetime(d5["turn_start_ts"]).dt.strftime("%Y-%m-%d %H:%M:%S")
d5.to_csv(f"{OUT}/d5_call_transcripts.csv", index=False)

d10 = pd.DataFrame(consents)
for col in ["captured_at", "opt_out_at"]:
    d10[col] = pd.to_datetime(d10[col]).dt.strftime("%Y-%m-%d %H:%M:%S")
d10.to_csv(f"{OUT}/d10_consent_registry.csv", index=False)

pd.DataFrame(templates).to_csv(f"{OUT}/d11_template_registry.csv", index=False)
policy_df.to_csv(f"{OUT}/d12_policy_rules.csv", index=False)
pd.DataFrame(notices).to_csv(f"{OUT}/notice_dispatch_history.csv", index=False)

hol = [dict(date=d, holiday_name=n, scope="NATIONAL", state="") for d, n in NATIONAL.items()]
for st, hs in STATE_HOL.items():
    hol += [dict(date=d, holiday_name=n, scope="STATE", state=st) for d, n in hs.items()]
pd.DataFrame(hol).sort_values(["date", "scope"]).to_csv(f"{OUT}/holiday_calendar.csv", index=False)
pd.DataFrame(collectors).to_csv(f"{OUT}/collector_roster.csv", index=False)
pd.DataFrame(certs).to_csv(f"{OUT}/certification_register.csv", index=False)

# --------------------------------------------------------------------------------------
# Audit requests + samples
# --------------------------------------------------------------------------------------
REQS = {
    "REQ-01": dict(lender="L001", start=date(2026, 1, 1), end=date(2026, 3, 31), n=300,
                   checks=[("C1", "Q1", "CONSENT_BEFORE_CONTACT"), ("C2", "Q1", "TEMPLATE_APPROVED"),
                           ("C3", "Q2", "CALL_HOURS"), ("C4", "Q2", "CALL_FREQUENCY"), ("C5", "Q3", "AGENT_CERTIFICATION")]),
    "REQ-02": dict(lender="L003", start=date(2026, 1, 1), end=date(2026, 6, 30), n=200,
                   checks=[("C1", "Q1", "VERIFICATION_BEFORE_DISCLOSURE"), ("C2", "Q1", "CALL_RECORDING"),
                           ("C3", "Q2", "NOTICE_TIMELINE")]),
    "REQ-03": dict(lender="L002", start=date(2026, 4, 1), end=date(2026, 6, 30), n=250,
                   checks=[("C1", "Q1", "CONSENT_BEFORE_CONTACT"), ("C2", "Q1", "CALL_HOURS"),
                           ("C3", "Q1", "CALL_FREQUENCY"), ("C4", "Q1", "VERIFICATION_BEFORE_DISCLOSURE"),
                           ("C5", "Q1", "AGENT_CERTIFICATION")]),
}
for rid, rq in REQS.items():
    pool = [a["account_id"] for a in accounts if a["lender_id"] == rq["lender"]]
    rq["sample"] = sorted(rng.sample(pool, rq["n"]))
    pd.DataFrame({"sr_no": range(1, rq["n"] + 1), "account_id": rq["sample"]}).to_csv(
        f"{OUT}/audit_requests/{rid}_annexure_A_sample.csv", index=False)

REQ01 = """From: internal.audit@l001-bank.example
To: collections.compliance@creditnirvana.example
Date: 14 Nov 2026 10:42 IST
Subject: Q1 2026 outsourced collections audit - evidence request (Ref: IA/COLL/2026/014)

Dear Compliance Team,

As part of our periodic review of outsourced collection activity, please provide evidence for the
300 accounts listed in Annexure A (attached), covering the period 1 January 2026 to 31 March 2026:

1. WhatsApp reminders were sent only to borrowers who had consented to WhatsApp communication, and
   only using approved templates.
2. Collection calls respected the permitted calling hours and call frequency limits.
3. All calls were made by recovery agents holding a valid certification.

For each point please share the underlying records (contact logs, consent records, certificates)
and clearly list any exceptions.

Exceptions will be graded as follows (Annexure B - Severity scale):
  CRITICAL - contact without valid consent; call made by an agent without valid certification
  MAJOR    - message sent using a template that was not approved; call outside permitted hours
  MINOR    - breach of call frequency limits

Please respond by 21 Nov 2026.

Regards,
Internal Audit - Retail Collections, L001
"""
REQ03 = """From: rm.collections@l002-finance.example
To: compliance@creditnirvana.example
Date: 17 Nov 2026 18:05 IST
Subject: quick one before the inspection

Hi team,

Ahead of the regulator's visit next month we need some comfort on fair practices for the accounts in the
attached list (250 accounts, Annexure A), for April to June 2026.

Basically we want to know we're only messaging people on WhatsApp who agreed to it, calling at the
right times and not harassing anyone with too many calls, making sure the person on the line is
actually the borrower before talking money, and only having certified people on the phones.

Please flag anything that's off - we'd rather hear it from you than from them.

Use our usual grading:
  P1 - regulatory breach with direct borrower impact (messaging without consent, talking dues before
       confirming identity / to someone else)
  P2 - regulatory breach (uncertified agent on calls, calls outside allowed hours)
  P3 - internal policy breach (too many calls)

Thanks,
Relationship Manager - Collections, L002
"""
open(f"{OUT}/audit_requests/REQ-01_email.txt", "w").write(REQ01)
open(f"{OUT}/audit_requests/REQ-03_email.txt", "w").write(REQ03)

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

ss = getSampleStyleSheet()
doc = SimpleDocTemplate(f"{OUT}/audit_requests/REQ-02_letter.pdf", pagesize=A4)
P = lambda t, s="BodyText": Paragraph(t, ss[s])
story = [P("L003 Housing &amp; Consumer Finance - Internal Audit Department", "Title"),
         P("Ref: IAD/OUTSRC/2026/041 &nbsp;&nbsp;&nbsp; Date: 12 November 2026"), Spacer(1, 10),
         P("To: The Head of Compliance, Collections Service Provider"), Spacer(1, 6),
         P("<b>Subject: Audit of outsourced recovery conduct and notice management - H1 2026</b>"), Spacer(1, 8),
         P("In accordance with the outsourcing agreement and the applicable guidelines on recovery agents, you are "
           "requested to furnish evidence in respect of the 200 loan accounts listed in Annexure A for the period "
           "1 January 2026 to 30 June 2026, on the following points:"),
         P("1. Confirm that on every connected collection call the identity of the borrower was established before any "
           "outstanding amount was discussed, and furnish the call recording for each such call."),
         P("2. Confirm that demand notices and pre-legal notices triggered during the period were served on the borrowers "
           "within the timelines prescribed in your Notice Management Policy, together with proof of service."),
         Spacer(1, 8), P("<b>Annexure B - Severity of observations</b>"),
         P("HIGH: disclosure of dues before or without establishing identity, including to third parties; notice served "
           "more than 5 business days beyond the prescribed deadline; notice without proof of service."),
         P("MEDIUM: notice served late by up to 5 business days; call recording not available for a connected call."),
         P("LOW: any other documentation lapse."), Spacer(1, 8),
         P("Kindly submit your response with the evidence pack within 7 days of receipt of this letter."),
         Spacer(1, 14), P("Chief Internal Auditor<br/>L003 Housing &amp; Consumer Finance")]
doc.build(story)

# --------------------------------------------------------------------------------------
# Reference checker -> ground truth
# --------------------------------------------------------------------------------------
uniq = {}
for c in contacts:                      # dedupe exact duplicate rows by contact_id
    uniq.setdefault(c["contact_id"], c)
U = list(uniq.values())
by_acc = {}
for c in U:
    by_acc.setdefault(c["account_id"], []).append(c)
cons_by_b = {}
for c in consents:
    cons_by_b.setdefault(c["borrower_id"], []).append(c)
certs_by_col = {}
for c in certs:
    certs_by_col.setdefault(c["collector_id"], []).append(c)
tx_calls = set(t["call_id"] for t in transcripts)
notices_by_acc = {}
for n in notices:
    notices_by_acc.setdefault(n["account_id"], []).append(n)


def in_period(c, rq):
    return rq["start"] <= c["contact_ts"].date() <= rq["end"]


def chk_consent(acc, rq):
    msgs = [c for c in by_acc.get(acc, []) if c["channel"] == "WHATSAPP" and in_period(c, rq)]
    wa = [c for c in cons_by_b.get(ACC[acc]["borrower_id"], []) if c["channel"] == "WHATSAPP"]
    items, ev = [], []
    for m in sorted(msgs, key=lambda x: x["contact_ts"]):
        mu = m["contact_ts"] - IST
        ok = [c for c in wa if c["captured_at"] < mu and (c["opt_out_at"] is None or c["opt_out_at"] > mu)]
        if ok:
            ev += [m["contact_id"], ok[0]["consent_id"]]
            continue
        if not wa:
            gt, refs = "no_consent_record", [m["contact_id"]]
            det = "No WhatsApp consent record for borrower"
        elif any(c["captured_at"] < mu and c["opt_out_at"] and c["opt_out_at"] <= mu for c in wa):
            oc = [c for c in wa if c["opt_out_at"] and c["opt_out_at"] <= mu][0]
            gt, refs = "message_after_opt_out", [m["contact_id"], oc["consent_id"]]
            det = f"Message {mu:%Y-%m-%d %H:%M} UTC after opt-out {oc['opt_out_at']:%Y-%m-%d %H:%M} UTC"
        else:
            fc = min(wa, key=lambda c: c["captured_at"])
            gt, refs = "consent_after_message", [m["contact_id"], fc["consent_id"]]
            det = f"Message {mu:%Y-%m-%d %H:%M} UTC; consent captured {fc['captured_at']:%Y-%m-%d %H:%M} UTC"
        items.append(dict(gap_type=gt, record_ids=refs, detail=det))
    return len(msgs), items, [], ev


def chk_template(acc, rq):
    msgs = [c for c in by_acc.get(acc, []) if c["channel"] == "WHATSAPP" and in_period(c, rq)]
    items, ev = [], []
    for m in msgs:
        t = TPL.get(m["template_id"])
        d = m["contact_ts"].date()
        if t is None:
            items.append(dict(gap_type="template_not_registered", record_ids=[m["contact_id"]], detail=m["template_id"]))
        elif t["channel"] != "WHATSAPP":
            items.append(dict(gap_type="template_channel_mismatch", record_ids=[m["contact_id"], t["template_id"]],
                              detail=f"{t['channel']} template used on WhatsApp"))
        elif t["approval_status"] != "APPROVED":
            items.append(dict(gap_type="template_not_approved", record_ids=[m["contact_id"], t["template_id"]],
                              detail=f"Template status {t['approval_status']}"))
        elif t["approved_date"] > d:
            items.append(dict(gap_type="template_used_before_approval", record_ids=[m["contact_id"], t["template_id"]],
                              detail=f"Sent {d}; approved {t['approved_date']}"))
        else:
            ev += [m["contact_id"], t["template_id"]]
    return len(msgs), items, [], ev


def voice_in(acc, rq):
    return [c for c in by_acc.get(acc, []) if c["channel"] == "VOICE" and in_period(c, rq)]


def chk_hours(acc, rq):
    calls = voice_in(acc, rq)
    lender = ACC[acc]["lender_id"]
    h1, h2 = hours_window(lender)
    items, ev = [], []
    for c in calls:
        t = c["contact_ts"].time()
        if h1 <= t <= h2:
            ev.append(c["contact_id"])
        else:
            items.append(dict(gap_type="outside_calling_hours", record_ids=[c["contact_id"], hours_rule(lender)],
                              detail=f"Call at {c['contact_ts']:%Y-%m-%d %H:%M:%S} IST; window {h1:%H:%M}-{h2:%H:%M}"))
    return len(calls), items, [], ev + [hours_rule(lender)]


def chk_freq(acc, rq):
    calls = voice_in(acc, rq)
    lender = ACC[acc]["lender_id"]
    items = []
    byday, bywk = {}, {}
    for c in calls:
        d = c["contact_ts"].date()
        byday.setdefault(d, []).append(c["contact_id"])
        bywk.setdefault(d - timedelta(days=d.weekday()), []).append(c["contact_id"])
    for d, ids in sorted(byday.items()):
        cap, rule = daily_cap(lender, d)
        if len(ids) > cap:
            items.append(dict(gap_type="daily_cap_exceeded", record_ids=ids + [rule],
                              detail=f"{len(ids)} attempts on {d} (cap {cap})"))
    for w, ids in sorted(bywk.items()):
        if len(ids) > 10:
            items.append(dict(gap_type="weekly_cap_exceeded", record_ids=ids + ["POL-GEN-003"],
                              detail=f"{len(ids)} attempts in week starting {w} (cap 10)"))
    return len(calls), items, [], [c["contact_id"] for c in calls] + ["POL-GEN-002", "POL-GEN-003"]


def chk_cert(acc, rq):
    calls = voice_in(acc, rq)
    items, cd, ev = [], [], []
    for c in calls:
        col, d = c["collector_id"], c["contact_ts"].date()
        if col not in COL:
            cd.append(dict(gap_type="collector_not_in_roster", record_ids=[c["contact_id"]], detail=c.get("collector_id_raw")))
            continue
        cs = certs_by_col.get(col, [])
        cover = [x for x in cs if x["valid_from"] <= d <= x["valid_to"]]
        if cover:
            ev += [c["contact_id"], cover[0]["cert_id"]]
            continue
        before = [x for x in cs if x["valid_to"] < d]
        after = [x for x in cs if x["valid_from"] > d]
        if before and after:
            gt = "certificate_lapsed_between_renewals"
        elif before:
            gt = "certificate_expired"
        else:
            gt = "certificate_not_yet_valid"
        items.append(dict(gap_type=gt, record_ids=[c["contact_id"]] + [x["cert_id"] for x in cs],
                          detail=f"{col} called on {d}; certs: " + "; ".join(f"{x['valid_from']}..{x['valid_to']}" for x in cs)))
    return len(calls), items, cd, ev


def connected_in(acc, rq):
    return [c for c in voice_in(acc, rq) if c["disposition"] in CONNECTED + ["WRONG_NUMBER"]]


def chk_verify(acc, rq):
    calls = connected_in(acc, rq)
    items, cd, ev = [], [], []
    for c in calls:
        o = call_truth[c["contact_id"]]
        if o == "transcript_missing":
            cd.append(dict(gap_type="transcript_missing", record_ids=[c["contact_id"]], detail="No recording/transcript in D5"))
        elif o == "ok":
            ev.append(c["contact_id"])
        else:
            items.append(dict(gap_type=o, record_ids=[c["contact_id"]], detail=f"{c['disposition']} call on {c['contact_ts']:%Y-%m-%d}"))
    return len(calls), items, cd, ev


def chk_recording(acc, rq):
    calls = connected_in(acc, rq)
    items = [dict(gap_type="recording_missing", record_ids=[c["contact_id"]],
                  detail=f"{c['disposition']} call at {c['contact_ts']:%Y-%m-%d %H:%M} IST, {c['duration_sec']}s, no transcript")
             for c in calls if c["contact_id"] not in tx_calls]
    return len(calls), items, [], [c["contact_id"] for c in calls if c["contact_id"] in tx_calls]


def chk_notice(acc, rq):
    st = ACC[acc]["state"]
    ns = [n for n in notices_by_acc.get(acc, []) if rq["start"] <= n["trigger_date"] <= rq["end"]]
    items, ev = [], []
    for n in ns:
        dl = add_business_days(n["trigger_date"], DEADLINE[n["notice_type"]], st)
        rule = "POL-GEN-004" if n["notice_type"] == "DEMAND_NOTICE" else "POL-GEN-005"
        if n["service_date"] is None:
            items.append(dict(gap_type="no_proof_of_service", record_ids=[n["notice_id"], rule], late_bd=None,
                              detail=f"Status {n['delivery_status']}; deadline {dl}"))
        elif n["service_date"] > dl:
            lb = business_days_between(dl, n["service_date"], st)
            items.append(dict(gap_type="served_late", record_ids=[n["notice_id"], rule], late_bd=lb,
                              detail=f"Served {n['service_date']}; deadline {dl}; {lb} business days late"))
        else:
            ev += [n["notice_id"], rule]
    return len(ns), items, [], ev


CHECKERS = {"CONSENT_BEFORE_CONTACT": chk_consent, "TEMPLATE_APPROVED": chk_template, "CALL_HOURS": chk_hours,
            "CALL_FREQUENCY": chk_freq, "AGENT_CERTIFICATION": chk_cert, "VERIFICATION_BEFORE_DISCLOSURE": chk_verify,
            "CALL_RECORDING": chk_recording, "NOTICE_TIMELINE": chk_notice}


def severity(rid, ctype, item):
    g = item["gap_type"]
    if rid == "REQ-01":
        return {"CONSENT_BEFORE_CONTACT": "CRITICAL", "AGENT_CERTIFICATION": "CRITICAL", "TEMPLATE_APPROVED": "MAJOR",
                "CALL_HOURS": "MAJOR", "CALL_FREQUENCY": "MINOR"}[ctype]
    if rid == "REQ-02":
        if ctype == "VERIFICATION_BEFORE_DISCLOSURE":
            return "HIGH"
        if ctype == "CALL_RECORDING":
            return "MEDIUM"
        if g == "no_proof_of_service" or (item.get("late_bd") or 0) > 5:
            return "HIGH"
        return "MEDIUM"
    return {"CONSENT_BEFORE_CONTACT": "P1", "VERIFICATION_BEFORE_DISCLOSURE": "P1", "AGENT_CERTIFICATION": "P2",
            "CALL_HOURS": "P2", "CALL_FREQUENCY": "P3"}[ctype]


SEV_RANK = {"CRITICAL": 0, "HIGH": 0, "P1": 0, "MAJOR": 1, "MEDIUM": 1, "P2": 1, "MINOR": 2, "LOW": 2, "P3": 2}
gt_rows, gap_rows = [], []
gid = 1
for rid, rq in REQS.items():
    for acc in rq["sample"]:
        for chk_id, q, ctype in rq["checks"]:
            n, items, cd, ev = CHECKERS[ctype](acc, rq)
            if n == 0:
                status = "NOT_APPLICABLE"
            elif items:
                status = "GAP"
            elif cd:
                status = "CANNOT_DETERMINE"
            else:
                status = "EVIDENCED"
            sevs = [severity(rid, ctype, i) for i in items]
            gt_rows.append(dict(request_id=rid, account_id=acc, check_id=chk_id, question=q, check_type=ctype,
                                status=status, items_tested=n, gap_items=len(items),
                                gap_types=";".join(sorted(set(i["gap_type"] for i in items))),
                                severity=min(sevs, key=lambda s: SEV_RANK[s]) if sevs else "",
                                cannot_determine_reasons=";".join(sorted(set(i["gap_type"] for i in cd)))))
            for i, s in zip(items, sevs):
                gap_rows.append(dict(gap_item_id=f"GAP-{gid:05d}", request_id=rid, account_id=acc, check_id=chk_id,
                                     check_type=ctype, gap_type=i["gap_type"], severity=s,
                                     record_ids=";".join(i["record_ids"]), detail=i["detail"]))
                gid += 1
gt = pd.DataFrame(gt_rows)
gt.to_csv(f"{OUT}/ground_truth/ground_truth_account_check.csv", index=False)
pd.DataFrame(gap_rows).to_csv(f"{OUT}/ground_truth/ground_truth_gap_items.csv", index=False)

# --------------------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------------------
print("Rows written:")
for f in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, f)
    if f.endswith(".csv"):
        print(f"  {f:38s} {sum(1 for _ in open(p)) - 1:>8,}")
print("\nGround truth (account x check status):")
print(gt.pivot_table(index=["request_id", "check_id", "check_type"], columns="status", values="account_id",
                     aggfunc="count", fill_value=0).to_string())
