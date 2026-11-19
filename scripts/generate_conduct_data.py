"""
Supporting data for the guideline catalogue. SYNTHETIC, fixed seed, and purely
additive: it reads the existing CSVs and writes NEW files only -- the original
datasets (and their ground truth) are never touched.

    python -m scripts.generate_conduct_data

Writes data/*.csv plus data/ground_truth/conduct_violations.csv (the injected
violations, as an answer key for testing the new checks).
"""
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
rng = random.Random(43)

acc = pd.read_csv(DATA / "d1_account_master_thin.csv", dtype=str)
acc["dpd"] = acc["dpd"].astype(int)
acc["total_dues"] = acc["total_dues"].astype(float)
d4 = pd.read_csv(DATA / "d4_contact_history.csv", dtype=str, keep_default_na=False).drop_duplicates("contact_id")
tpl = pd.read_csv(DATA / "d11_template_registry.csv", dtype=str).set_index("template_id")
roster = pd.read_csv(DATA / "collector_roster.csv", dtype=str)

truth = []   # injected violations


def mark(table, key, kind):
    truth.append(dict(table=table, record_id=key, violation=kind))


def rdate(a, b):
    return a + timedelta(days=rng.randint(0, (b - a).days))


P0, P1 = date(2026, 1, 1), date(2026, 6, 30)

# ------------------------------------------------------------------ caller numbers (G-VOICE-07)
voice = d4[d4.channel == "VOICE"]
rows = []
BAD_AGENCY = {"AG03": 0.30}   # one agency's dialer often shows a personal mobile instead of the 160 series
for r in voice.itertuples():
    if rng.random() < BAD_AGENCY.get(r.agency_id, 0.02):
        num = f"+91-{rng.choice('6789')}XXXXXX{rng.randint(100, 999)}"
        mark("caller_numbers", r.contact_id, "non_160_caller")
    else:
        num = "1600" + "".join(rng.choice("0123456789") for _ in range(6))
    rows.append((r.contact_id, num))
pd.DataFrame(rows, columns=["contact_id", "caller_number"]).to_csv(DATA / "caller_numbers.csv", index=False)

# ------------------------------------------------------------------ message content (G-DIG-05)
FILL = ["Customer", "12,500", "4821", "15 Mar", "https://pay.example/x"]
ROGUE = [
    "Pay today or we will inform your employer and neighbours about your default.",
    "You are a cheat. Pay now or face arrest.",
    "Your family will come to know about your loan default if you do not pay.",
    "We will send people to your house to shame you in front of everyone.",
]
msgs = d4[d4.channel.isin(["WHATSAPP", "SMS"])]
rows = []
for r in msgs.itertuples():
    text = ""
    if r.template_id in tpl.index:
        it = iter(FILL * 3)
        text = re.sub(r"\{\{\d\}\}|\{#var#\}", lambda m: next(it), tpl.at[r.template_id, "registered_text"])
    if rng.random() < 0.008:
        text = rng.choice(ROGUE)
        mark("message_content", r.contact_id, "inappropriate_message")
    rows.append((r.contact_id, r.channel, text))
pd.DataFrame(rows, columns=["contact_id", "channel", "message_text"]).to_csv(DATA / "message_content.csv", index=False)

# ------------------------------------------------------------------ call conduct log (G-VOICE-06)
THREATS = [
    "Agar aaj paise nahi diye toh police ko bhej denge.",
    "Tum chor ho, sab ko bata denge ki tum paisa nahi dete.",
    "We will tell your employer and your neighbours about this loan.",
    "I will send people to your house tonight if you do not pay.",
    "You will go to jail if you do not pay today.",
]
connected = voice[voice.disposition.str.startswith("CONNECTED")]
rows = []
for r in connected.itertuples():
    if rng.random() < 0.012:
        rows.append((r.contact_id, r.account_id, r.collector_id, "AGENT", rng.choice(THREATS), "QA_SAMPLE"))
        mark("call_conduct_log", r.contact_id, "abusive_or_threatening_language")
pd.DataFrame(rows, columns=["call_id", "account_id", "collector_id", "speaker", "utterance", "logged_by"]
             ).to_csv(DATA / "call_conduct_log.csv", index=False)

# ------------------------------------------------------------------ field visits (G-FLD-01)
field_accts = acc[acc.dpd >= 60].sample(frac=0.35, random_state=43)
by_ag = {ag: g.collector_id.tolist() for ag, g in roster[roster.status == "ACTIVE"].groupby("agency_id")}
rows, n = [], 1
for a in field_accts.itertuples():
    for _ in range(rng.randint(1, 3)):
        d = rdate(P0, P1)
        late = rng.random() < 0.07
        hh = rng.choice([6, 7, 19, 20]) if late else rng.randint(9, 17)
        ts = datetime(d.year, d.month, d.day, hh, rng.randint(0, 59))
        vid = f"FV{n:05d}"; n += 1
        logged = "N" if rng.random() < 0.08 else "Y"
        outcome = rng.choices(["MET_BORROWER", "NOT_AVAILABLE", "MET_THIRD_PARTY"], [0.5, 0.35, 0.15])[0]
        disclosed = "Y" if outcome == "MET_THIRD_PARTY" and rng.random() < 0.3 else "N"
        col = rng.choice(by_ag[rng.choice(list(by_ag))])
        rows.append((vid, a.account_id, col, ts.strftime("%Y-%m-%d %H:%M:%S"), logged,
                     "" if logged == "N" else (ts + timedelta(hours=rng.randint(1, 6))).strftime("%Y-%m-%d %H:%M:%S"),
                     outcome, disclosed))
        if late: mark("field_visits", vid, "visit_outside_hours")
        if logged == "N": mark("field_visits", vid, "visit_not_logged")
        if disclosed == "Y": mark("field_visits", vid, "third_party_disclosure")
pd.DataFrame(rows, columns=["visit_id", "account_id", "collector_id", "visit_ts", "logged_in_app", "logged_ts",
                            "outcome", "dues_disclosed_to_third_party"]).to_csv(DATA / "field_visits.csv", index=False)

# ------------------------------------------------------------------ closures / security release (G-PAY-01)
SEC = {"Two Wheeler Loan": "Vehicle RC and hypothecation", "Business Loan": "Original property documents",
       "Personal Loan": "Post-dated cheques", "Consumer Durable Loan": "Post-dated cheques"}
rows, n = [], 1
for a in acc.sample(n=260, random_state=44).itertuples():
    if a.product not in SEC: continue
    cd = rdate(P0, P1 - timedelta(days=20))
    cid = f"CLS{n:04d}"; n += 1
    released = "" if rng.random() < 0.12 else (cd + timedelta(days=rng.randint(0, 20))).isoformat()
    rows.append((cid, a.account_id, cd.isoformat(), rng.choice(["FULL_REPAYMENT", "SETTLEMENT"]), SEC[a.product], released))
    if not released: mark("closures", cid, "security_not_released")
pd.DataFrame(rows, columns=["closure_id", "account_id", "closure_date", "closure_type", "security_held",
                            "security_release_date"]).to_csv(DATA / "closures.csv", index=False)

# ------------------------------------------------------------------ penal charges (G-PAY-02)
msg_by_acc = {k: g for k, g in d4[d4.channel.isin(["WHATSAPP", "SMS"])].groupby("account_id")}
rows, n = [], 1
for a in acc[acc.dpd >= 15].sample(n=420, random_state=45).itertuples():
    d = rdate(P0, P1)
    default_amt = round(a.total_dues * rng.uniform(0.04, 0.12))
    cap = "Y" if rng.random() < 0.05 else "N"
    on_pen = "Y" if rng.random() < 0.04 else "N"
    rem, states = "", ""
    g = msg_by_acc.get(a.account_id)
    if g is not None and len(g):
        r = g.iloc[rng.randrange(len(g))]
        rem = r.contact_id
        states = "N" if rng.random() < 0.22 else "Y"
    pid = f"PEN{n:04d}"; n += 1
    rows.append((pid, a.account_id, d.isoformat(), default_amt, round(default_amt * 0.02), cap, on_pen, rem, states))
    if cap == "Y": mark("penal_charges", pid, "penal_capitalised")
    if on_pen == "Y": mark("penal_charges", pid, "penal_on_penal")
    if rem and states == "N": mark("penal_charges", pid, "penal_not_disclosed_in_reminder")
pd.DataFrame(rows, columns=["charge_id", "account_id", "charge_date", "amount_in_default", "penal_charge_amount",
                            "capitalised", "charged_on_penal", "reminder_contact_id", "reminder_states_penal_charge"]
             ).to_csv(DATA / "penal_charges.csv", index=False)

(DATA / "ground_truth").mkdir(exist_ok=True)
pd.DataFrame(truth).to_csv(DATA / "ground_truth" / "conduct_violations.csv", index=False)
print(pd.DataFrame(truth).groupby(["table", "violation"]).size())
