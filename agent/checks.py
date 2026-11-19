"""
Deterministic test engine (Stage 4): one function per check type.
Signature: fn(ctx, spec, accounts) -> list[Verdict]
  ctx      = Context (tools + policy + request id)
  spec     = one check from checks.json (check_id, check_type, params ...)
  accounts = list of sampled account_ids
Batch retrieval per check (not per account) keeps a 300-account request fast.
"""
from collections import defaultdict
from datetime import timedelta

from .transcript_review import label_calls
from .verdict import Finding, Verdict

CONNECTED_PREFIX = "CONNECTED"


class Context:
    def __init__(self, tools, policy, request_id, start, end):
        self.tools, self.policy, self.request_id, self.start, self.end = tools, policy, request_id, start, end

    def V(self, spec, acc, **kw):
        return Verdict(request_id=self.request_id, check_id=spec["check_id"], check_type=spec["check_type"],
                       account_id=acc, **kw)


def _group(df, key="account_id"):
    return {k: g for k, g in df.groupby(key)} if len(df) else {}


# ------------------------------------------------------------------ consent before WhatsApp contact
def consent_before_contact(ctx, spec, accounts):
    channel = spec.get("params", {}).get("channel", "WHATSAPP")
    msgs = ctx.tools.contact_log(accounts, channel, ctx.start, ctx.end)
    acc = ctx.tools.accounts()
    cons = ctx.tools.consent(acc.loc[accounts, "borrower_id"].unique(), channel)
    cons_by_b = _group(cons, "borrower_id")
    by_acc = _group(msgs)
    out = []
    for a in accounts:
        m = by_acc.get(a)
        if m is None:
            out.append(ctx.V(spec, a, items_tested=0)); continue
        c = cons_by_b.get(acc.at[a, "borrower_id"])
        gaps, ev = [], []
        for r in m.sort_values("ts_utc").itertuples():
            t = r.ts_utc
            if c is None or c.empty:
                gaps.append(Finding("no_consent_record", [r.contact_id],
                                    f"Message {t:%Y-%m-%d %H:%M} UTC; no {channel} consent record for borrower"))
                continue
            valid = c[(c.captured_utc < t) & (c.opt_out_utc.isna() | (c.opt_out_utc > t))]
            if len(valid):
                ev += [r.contact_id, valid.iloc[0].consent_id]
                continue
            opted = c[(c.captured_utc < t) & c.opt_out_utc.notna() & (c.opt_out_utc <= t)]
            if len(opted):
                o = opted.iloc[0]
                gaps.append(Finding("message_after_opt_out", [r.contact_id, o.consent_id],
                                    f"Message {t:%Y-%m-%d %H:%M} UTC after opt-out {o.opt_out_utc:%Y-%m-%d %H:%M} UTC"))
            else:
                f = c.sort_values("captured_utc").iloc[0]
                gaps.append(Finding("consent_after_message", [r.contact_id, f.consent_id],
                                    f"Message {t:%Y-%m-%d %H:%M} UTC (D4 {r.ts_raw} IST); consent captured "
                                    f"{f.captured_utc:%Y-%m-%d %H:%M} UTC"))
        out.append(ctx.V(spec, a, items_tested=len(m), gaps=gaps, evidence_ids=ev, rule_refs=["POL-GEN-007"]))
    return out


# ------------------------------------------------------------------ approved template
def template_approved(ctx, spec, accounts):
    msgs = ctx.tools.contact_log(accounts, "WHATSAPP", ctx.start, ctx.end)
    tpl = ctx.tools.templates()
    by_acc = _group(msgs)
    out = []
    for a in accounts:
        m = by_acc.get(a)
        if m is None:
            out.append(ctx.V(spec, a, items_tested=0)); continue
        gaps, ev = [], []
        for r in m.itertuples():
            d = r.local_date
            if r.template_id not in tpl.index:
                gaps.append(Finding("template_not_registered", [r.contact_id], f"Template {r.template_id} not in D11"))
                continue
            t = tpl.loc[r.template_id]
            if t.channel != "WHATSAPP":
                gaps.append(Finding("template_channel_mismatch", [r.contact_id, t.template_id], f"{t.channel} template sent on WhatsApp"))
            elif t.approval_status != "APPROVED":
                gaps.append(Finding("template_not_approved", [r.contact_id, t.template_id], f"Template status {t.approval_status}"))
            elif t.approved_date > d:
                gaps.append(Finding("template_used_before_approval", [r.contact_id, t.template_id],
                                    f"Sent {d}; template approved {t.approved_date}"))
            else:
                ev += [r.contact_id, t.template_id]
        out.append(ctx.V(spec, a, items_tested=len(m), gaps=gaps, evidence_ids=ev, rule_refs=["POL-GEN-008"]))
    return out


# ------------------------------------------------------------------ calling hours
def call_hours(ctx, spec, accounts):
    calls = ctx.tools.contact_log(accounts, "VOICE", ctx.start, ctx.end)
    by_acc = _group(calls)
    out = []
    for a in accounts:
        c = by_acc.get(a)
        if c is None:
            out.append(ctx.V(spec, a, items_tested=0)); continue
        gaps, ev, rules = [], [], set()
        for r in c.itertuples():
            s, e, rule = ctx.policy.calling_window(r.lender_id, r.local_date)
            rules.add(rule)
            t = r.ts_local.time()
            if s <= t <= e:
                ev.append(r.contact_id)
            else:
                gaps.append(Finding("outside_calling_hours", [r.contact_id, rule],
                                    f"Call at {r.ts_local:%Y-%m-%d %H:%M:%S} borrower local time; allowed {s:%H:%M}-{e:%H:%M} ({rule})"))
        out.append(ctx.V(spec, a, items_tested=len(c), gaps=gaps, evidence_ids=ev, rule_refs=sorted(rules)))
    return out


# ------------------------------------------------------------------ call frequency
def call_frequency(ctx, spec, accounts):
    calls = ctx.tools.contact_log(accounts, "VOICE", ctx.start, ctx.end)   # already de-duplicated by contact_id
    by_acc = _group(calls)
    out = []
    for a in accounts:
        c = by_acc.get(a)
        if c is None:
            out.append(ctx.V(spec, a, items_tested=0)); continue
        lender = c.iloc[0].lender_id
        gaps, rules = [], set()
        for d, g in c.groupby("local_date"):
            cap, rule = ctx.policy.cap("DAILY_CALL_CAP", lender, d)
            rules.add(rule)
            if len(g) > cap:
                gaps.append(Finding("daily_cap_exceeded", list(g.contact_id) + [rule], f"{len(g)} attempts on {d} (cap {cap}, {rule})"))
        wk = c["local_date"].map(lambda d: d - timedelta(days=d.weekday()))
        for w, g in c.groupby(wk):
            cap, rule = ctx.policy.cap("WEEKLY_CALL_CAP", lender, g.local_date.max())  # rule in force on the calls' dates
            rules.add(rule)
            if len(g) > cap:
                gaps.append(Finding("weekly_cap_exceeded", list(g.contact_id) + [rule],
                                    f"{len(g)} attempts in week starting {w} (cap {cap}, {rule})"))
        out.append(ctx.V(spec, a, items_tested=len(c), gaps=gaps, evidence_ids=list(c.contact_id), rule_refs=sorted(rules)))
    return out


# ------------------------------------------------------------------ agent certification
def agent_certification(ctx, spec, accounts):
    calls = ctx.tools.contact_log(accounts, "VOICE", ctx.start, ctx.end)
    roster = ctx.tools.roster()
    certs = ctx.tools.certificates()
    certs_by = {k: g for k, g in certs.groupby("collector_id")}
    by_acc = _group(calls)
    out = []
    for a in accounts:
        c = by_acc.get(a)
        if c is None:
            out.append(ctx.V(spec, a, items_tested=0)); continue
        gaps, cd, ev = [], [], []
        for r in c.itertuples():
            col, d = r.collector_id, r.local_date
            if col not in roster.index:
                cd.append(Finding("collector_not_in_roster", [r.contact_id], f"Collector '{r.collector_id_raw}' not found in roster"))
                continue
            cs = certs_by.get(col)
            if cs is None:
                gaps.append(Finding("no_certificate_on_record", [r.contact_id], f"{col} has no certificate")); continue
            cover = cs[(cs.valid_from <= d) & (cs.valid_to >= d)]
            if len(cover):
                ev += [r.contact_id, cover.iloc[0].cert_id]; continue
            before, after = (cs.valid_to < d).any(), (cs.valid_from > d).any()
            gt = ("certificate_lapsed_between_renewals" if before and after else
                  "certificate_expired" if before else "certificate_not_yet_valid")
            gaps.append(Finding(gt, [r.contact_id] + list(cs.cert_id),
                                f"{col} called on {d}; certificates: " +
                                "; ".join(f"{x.valid_from}..{x.valid_to}" for x in cs.itertuples())))
        out.append(ctx.V(spec, a, items_tested=len(c), gaps=gaps, undetermined=cd, evidence_ids=ev, rule_refs=["POL-GEN-011"]))
    return out


# ------------------------------------------------------------------ verification before disclosure / recordings
def _connected(ctx, accounts):
    calls = ctx.tools.contact_log(accounts, "VOICE", ctx.start, ctx.end)
    return calls[calls.disposition.str.startswith(CONNECTED_PREFIX) | (calls.disposition == "WRONG_NUMBER")]


def verification_before_disclosure(ctx, spec, accounts):
    calls = _connected(ctx, accounts)
    tx = ctx.tools.transcripts(calls.contact_id)
    tx_by = {k: g for k, g in tx.groupby("call_id")}
    labels = label_calls(tx_by)  # Option B: labels only calls in THIS request; cached forever after
    by_acc = _group(calls)
    out = []
    for a in accounts:
        c = by_acc.get(a)
        if c is None:
            out.append(ctx.V(spec, a, items_tested=0)); continue
        gaps, cd, ev = [], [], []
        for r in c.itertuples():
            t = tx_by.get(r.contact_id)
            if t is None:
                cd.append(Finding("transcript_missing", [r.contact_id], "No recording/transcript; cannot test order of verification and disclosure"))
                continue
            label = labels.get(r.contact_id)
            if label is None:
                cd.append(Finding("label_failed", [r.contact_id], "Model could not reliably label this call; treated as cannot-determine"))
                continue
            outcome, turns, detail = label
            refs = [f"{r.contact_id}#turn{n}" for n in turns]
            if outcome == "ok":
                ev += [r.contact_id] + refs
            else:
                gaps.append(Finding(outcome, [r.contact_id] + refs, detail))
        out.append(ctx.V(spec, a, items_tested=len(c), gaps=gaps, undetermined=cd, evidence_ids=ev, rule_refs=["POL-GEN-009"]))
    return out


def call_recording(ctx, spec, accounts):
    calls = _connected(ctx, accounts)
    have = set(ctx.tools.transcripts(calls.contact_id).call_id)
    by_acc = _group(calls)
    out = []
    for a in accounts:
        c = by_acc.get(a)
        if c is None:
            out.append(ctx.V(spec, a, items_tested=0)); continue
        gaps = [Finding("recording_missing", [r.contact_id],
                        f"{r.disposition} call at {r.ts_raw} IST ({r.duration_sec}s) has no recording/transcript")
                for r in c.itertuples() if r.contact_id not in have]
        out.append(ctx.V(spec, a, items_tested=len(c), gaps=gaps,
                         evidence_ids=[x for x in c.contact_id if x in have], rule_refs=["POL-GEN-010"]))
    return out


# ------------------------------------------------------------------ notice timelines
def notice_timeline(ctx, spec, accounts):
    ns = ctx.tools.notices(accounts, ctx.start, ctx.end)
    acc = ctx.tools.accounts()
    P = ctx.policy
    by_acc = _group(ns)
    out = []
    for a in accounts:
        n = by_acc.get(a)
        if n is None:
            out.append(ctx.V(spec, a, items_tested=0)); continue
        st, lender = acc.at[a, "state"], acc.at[a, "lender_id"]
        gaps, ev, rules = [], [], {P.BUSINESS_DAY_RULE}
        for r in n.itertuples():
            days, rule = P.notice_deadline_days(r.notice_type, lender, r.trigger_date)
            rules.add(rule)
            dl = P.add_business_days(r.trigger_date, days, st)
            if r.service_date is None or str(r.service_date) in ("NaT", "nan"):
                gaps.append(Finding("no_proof_of_service", [r.notice_id, rule],
                                    f"{r.notice_type} triggered {r.trigger_date}; status {r.delivery_status}; deadline {dl}"))
            elif r.service_date > dl:
                lb = P.business_days_between(dl, r.service_date, st)
                gaps.append(Finding("served_late", [r.notice_id, rule],
                                    f"{r.notice_type} triggered {r.trigger_date}, dispatched {r.dispatch_date}, served "
                                    f"{r.service_date}; deadline {dl} ({days} business days, state {st}); {lb} business days late",
                                    late_bd=lb))
            else:
                ev += [r.notice_id]
        out.append(ctx.V(spec, a, items_tested=len(n), gaps=gaps, evidence_ids=ev, rule_refs=sorted(rules)))
    return out



# ================================================================== guideline checks (see data/rbi_guidelines.csv)
import re
from datetime import time as _time

import pandas as pd

# Phrases that RBI-style conduct rules prohibit (threats, shaming, privacy intrusion). A keyword screen, so
# every hit is cited with the exact words for a human to confirm.
CONDUCT_RE = re.compile(
    r"\b(police|jail|arrest(ed)?|employer|neighbou?rs?|chor|cheat|shame|your family|"
    r"send (people|men)|goons?|bhej denge|bata denge)\b", re.I)


def _blank(x):
    return x is None or (isinstance(x, float) and pd.isna(x)) or str(x).strip() == ""


def _in_period(ctx, series):
    d = pd.to_datetime(series, errors="coerce").dt.date
    return d.notna() & (d >= ctx.start) & (d <= ctx.end)


def _verdicts(ctx, spec, accounts, df, judge, rule):
    """judge(row) -> (list[Finding], evidence_ids). One Verdict per account."""
    by_acc = _group(df)
    out = []
    for a in accounts:
        c = by_acc.get(a)
        if c is None:
            out.append(ctx.V(spec, a, items_tested=0)); continue
        gaps, ev = [], []
        for r in c.itertuples():
            g, e = judge(r)
            gaps += g
            ev += e
        out.append(ctx.V(spec, a, items_tested=len(c), gaps=gaps, evidence_ids=ev, rule_refs=[rule]))
    return out


def caller_number_series(ctx, spec, accounts):
    calls = ctx.tools.contact_log(accounts, "VOICE", ctx.start, ctx.end)
    nums = ctx.tools.extra("caller_numbers").set_index("contact_id")["caller_number"]
    calls["caller_number"] = calls["contact_id"].map(nums).fillna("")

    def judge(r):
        if str(r.caller_number).startswith("160"):
            return [], [r.contact_id]
        return [Finding("non_160_caller", [r.contact_id],
                        f"Call at {r.ts_raw} IST was made from {r.caller_number or 'an unknown number'}, "
                        f"not the dedicated 160-series number")], []
    return _verdicts(ctx, spec, accounts, calls, judge, "G-VOICE-07")


def message_content(ctx, spec, accounts):
    channel = spec.get("params", {}).get("channel")
    msgs = pd.concat([ctx.tools.contact_log(accounts, ch, ctx.start, ctx.end)
                      for ch in ([channel] if channel else ["WHATSAPP", "SMS"])])
    text = ctx.tools.extra("message_content").set_index("contact_id")["message_text"]
    msgs["text"] = msgs["contact_id"].map(text).fillna("")

    def judge(r):
        m = CONDUCT_RE.search(r.text)
        if m:
            return [Finding("inappropriate_message", [r.contact_id],
                            f'{r.channel} message at {r.ts_raw} IST contains "{m.group(0)}": "{r.text[:120]}"')], []
        return [], [r.contact_id]
    return _verdicts(ctx, spec, accounts, msgs, judge, "G-DIG-05")


def call_conduct(ctx, spec, accounts):
    calls = _connected(ctx, accounts)
    said = {}   # call_id -> [(source, text)]
    tx = ctx.tools.transcripts(calls.contact_id)
    for r in tx[tx.speaker == "AGENT"].itertuples():
        said.setdefault(r.call_id, []).append((f"transcript turn {r.turn_no}", r.text))
    for r in ctx.tools.extra("call_conduct_log").itertuples():
        said.setdefault(r.call_id, []).append(("QA log", r.utterance))

    def judge(r):
        for src, t in said.get(r.contact_id, []):
            m = CONDUCT_RE.search(t)
            if m:
                return [Finding("abusive_or_threatening_language", [r.contact_id],
                                f'Call at {r.ts_raw} IST ({src}): agent said "{t[:140]}"')], []
        return [], [r.contact_id]
    return _verdicts(ctx, spec, accounts, calls, judge, "G-VOICE-06")


def field_visit(ctx, spec, accounts):
    """Field visits only inside the permitted hours (default 09:00-18:00)."""
    p = spec.get("params", {})
    lo = _time.fromisoformat(p.get("from", "09:00")); hi = _time.fromisoformat(p.get("to", "18:00"))
    v = ctx.tools.extra("field_visits")
    v = v[v.account_id.isin(set(accounts)) & _in_period(ctx, v.visit_ts)].copy()
    v["ts"] = pd.to_datetime(v.visit_ts)

    def judge(r):
        if lo <= r.ts.time() <= hi:
            return [], [r.visit_id]
        return [Finding("visit_outside_hours", [r.visit_id], f"Visit at {r.visit_ts}; allowed {lo:%H:%M}-{hi:%H:%M}")], []
    return _verdicts(ctx, spec, accounts, v, judge, "G-FLD-01")


def security_release(ctx, spec, accounts):
    c = ctx.tools.extra("closures")
    c = c[c.account_id.isin(set(accounts)) & _in_period(ctx, c.closure_date)].copy()

    def judge(r):
        if not _blank(r.security_release_date):
            return [], [r.closure_id]
        return [Finding("security_not_released", [r.closure_id],
                        f"Loan closed {r.closure_date} ({r.closure_type}); {r.security_held} not released")], []
    return _verdicts(ctx, spec, accounts, c, judge, "G-PAY-01")


def penal_charges(ctx, spec, accounts):
    c = ctx.tools.extra("penal_charges")
    c = c[c.account_id.isin(set(accounts)) & _in_period(ctx, c.charge_date)].copy()

    def judge(r):
        g = []
        if r.capitalised == "Y":
            g.append(Finding("penal_capitalised", [r.charge_id], f"Penal charge of {r.penal_charge_amount} on {r.charge_date} was capitalised"))
        if r.charged_on_penal == "Y":
            g.append(Finding("penal_on_penal", [r.charge_id], f"Penal charge on {r.charge_date} levied on earlier penal charges"))
        if not _blank(r.reminder_contact_id) and r.reminder_states_penal_charge == "N":
            g.append(Finding("penal_not_disclosed_in_reminder", [r.charge_id, r.reminder_contact_id],
                             f"Reminder {r.reminder_contact_id} did not state the applicable penal charges"))
        return g, ([] if g else [r.charge_id])
    return _verdicts(ctx, spec, accounts, c, judge, "G-PAY-02")


CHECKS = {
    "CONSENT_BEFORE_CONTACT": consent_before_contact,
    "TEMPLATE_APPROVED": template_approved,
    "CALL_HOURS": call_hours,
    "CALL_FREQUENCY": call_frequency,
    "AGENT_CERTIFICATION": agent_certification,
    "VERIFICATION_BEFORE_DISCLOSURE": verification_before_disclosure,
    "CALL_RECORDING": call_recording,
    "NOTICE_TIMELINE": notice_timeline,
    "CALLER_NUMBER_SERIES": caller_number_series,
    "MESSAGE_CONTENT": message_content,
    "CALL_CONDUCT": call_conduct,
    "FIELD_VISIT": field_visit,
    "SECURITY_RELEASE": security_release,
    "PENAL_CHARGES": penal_charges,
}
