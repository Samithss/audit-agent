"""
Policy rules (D12) and business-day logic.
Every value returned carries the rule_id it came from, so it can be cited.
"""
from datetime import date, time, timedelta
from functools import lru_cache

import pandas as pd


class Policy:
    def __init__(self, tools):
        self.df = tools.policy()
        h = tools.holidays()
        self.national = set(h.loc[h["scope"] == "NATIONAL", "date"])
        self.state = {s: set(g["date"]) for s, g in h[h["scope"] == "STATE"].groupby("state")}

    def _active(self, rule_type, lender, d, parameter=None):
        df = self.df[(self.df["rule_type"] == rule_type) & (self.df["lender_id"].isin(["ALL", lender]))]
        if parameter:
            df = df[df["parameter"] == parameter]
        df = df[(df["effective_from"] <= d) & (df["effective_to"].isna() | (df["effective_to"] >= d))]
        if df.empty:
            raise LookupError(f"No active {rule_type} rule for {lender} on {d}")
        return df

    # POL-GEN-012: where lender policy is stricter, it applies -> take the strictest active rule.
    @lru_cache(maxsize=None)
    def calling_window(self, lender, d):
        best = None
        for _, r in self._active("CALLING_HOURS", lender, d).iterrows():
            a, b = r["value"].split("-")
            s, e = time.fromisoformat(a), time.fromisoformat(b)
            if best is None or (s >= best[0] and e <= best[1]):
                best = (s, e, r["rule_id"])
        return best

    @lru_cache(maxsize=None)
    def cap(self, rule_type, lender, d):
        df = self._active(rule_type, lender, d)
        r = df.loc[df["value"].astype(int).idxmin()]
        return int(r["value"]), r["rule_id"]

    @lru_cache(maxsize=None)
    def notice_deadline_days(self, notice_type, lender, d):
        df = self._active("NOTICE_DEADLINE", lender, d, parameter=notice_type)
        r = df.loc[df["value"].astype(int).idxmin()]
        return int(r["value"]), r["rule_id"]

    # POL-GEN-006: business day excludes Sundays, 2nd & 4th Saturdays, national holidays and
    # holidays of the borrower's state; the trigger date itself is not counted.
    BUSINESS_DAY_RULE = "POL-GEN-006"

    def is_business_day(self, d, state):
        if d.weekday() == 6:
            return False
        if d.weekday() == 5 and ((d.day - 1) // 7 + 1) in (2, 4):
            return False
        return d not in self.national and d not in self.state.get(state, set())

    def add_business_days(self, d, n, state):
        cur, c = d, 0
        while c < n:
            cur += timedelta(days=1)
            if self.is_business_day(cur, state):
                c += 1
        return cur

    def business_days_between(self, a, b, state):
        n, cur = 0, a
        while cur < b:
            cur += timedelta(days=1)
            n += self.is_business_day(cur, state)
        return n
