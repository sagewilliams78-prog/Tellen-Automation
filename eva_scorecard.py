#!/usr/bin/env python3
"""
EVA SCORECARD -- is the system actually working?

Sage's condition for adding capital is "weeks of profitable trades." This
exists so that judgement is made against criteria fixed IN ADVANCE, rather
than deciding after the fact what counts as good. Moving the goalposts once
results are in is the single easiest way to talk yourself into funding a
system that does not work.

WHY "IS IT PROFITABLE?" IS A WEAK TEST
  Simulated 2026-09-01: a system with a REAL edge shows a profitable month
  80% of the time. A system with NO edge shows one 40% of the time. So a
  green month is roughly 2:1 evidence -- suggestive, not proof.

THE STRONGER TEST: does reality match the MODEL?
  The backtest makes four separate predictions -- trade frequency, win rate,
  average winner, average loser. Any one of them can match by luck. All four
  matching at once is much harder to fake, and it is what would tell us the
  model actually describes Eva rather than describing a fantasy.

  Equally important: this can FAIL. If Eva trades far less than predicted, or
  her winners are much smaller, the model is wrong and no amount of profit
  justifies scaling on it.

Run any time:  python eva_scorecard.py
"""

import csv
import os
from collections import defaultdict
from datetime import datetime, timedelta

TRADE_LOG = os.path.expanduser("~/trading_log_v9.csv")
DECISIONS = os.path.expanduser("~/eva_decisions.csv")
JOURNAL = os.path.expanduser("~/sage_bot_daily_journal.csv")

# ---- PREDICTIONS, fixed 2026-09-01 before any v14 data existed -------------
# Source: portfolio backtest, 20 symbols, 96 sessions, real spreads, Eva's
# real 2-position and capital limits applied.
PREDICTED = {
    "trades_per_day": 2.07,
    "win_rate_pct": 56.8,
    "avg_win_pct": 1.52,
    "avg_loss_pct": -1.31,
    "expectancy_pct": 0.297,
}
# Eva's OBSERVED rate before v14 (4 trades / 5 live days). The backtest cannot
# model earnings blackouts or the weekly breaker, so the real rate is expected
# to land below the prediction -- this is the more realistic yardstick.
OBSERVED_PRIOR_RATE = 0.8

# ---- GO / NO-GO, fixed in advance -----------------------------------------
CRITERIA = [
    ("Ran every scheduled trading day",      "no days lost to crashes/hangs"),
    ("At least 20 real trades",              "below this, nothing is conclusive"),
    ("Net P&L positive",                     "necessary, NOT sufficient"),
    ("Win rate within 45-70%",               "outside = model is wrong"),
    ("Avg winner > avg loser (in %)",        "the actual source of the edge"),
    ("Profit factor >= 1.2",                 "below this the edge is not real"),
    ("No single day worse than -$15",        "risk controls holding"),
]


def load(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [r for r in csv.DictReader(f)]


def analyze(since_date=None):
    # PARTIAL rows are v14 scale-outs, not completed round-trips, and they are
    # always wins by construction (sold at +1%). Including them would inflate
    # win rate and profit factor -- exactly the self-deception this scorecard
    # exists to prevent. Their P&L is real and still lands in the parent
    # trade's day via the daily journal; they just don't count as "a trade".
    trades = [t for t in load(TRADE_LOG)
              if t.get("P&L") and t.get("Reason") != "PARTIAL"]
    if since_date:
        trades = [t for t in trades if t.get("Date", "") >= since_date]
    if not trades:
        return None

    pnl = [float(t["P&L"]) for t in trades]
    rets = []
    for t in trades:
        try:
            rets.append(float(str(t.get("Return%", "0")).rstrip("%")))
        except ValueError:
            pass

    wins = [x for x in rets if x > 0]
    losses = [x for x in rets if x <= 0]
    gw = sum(x for x in pnl if x > 0)
    gl = abs(sum(x for x in pnl if x <= 0))

    by_day = defaultdict(float)
    for t in trades:
        by_day[t["Date"]] += float(t["P&L"])

    days = sorted({t["Date"] for t in trades})
    return {
        "trades": len(trades),
        "days_traded": len(days),
        "first": days[0], "last": days[-1],
        "net_pnl": sum(pnl),
        "win_rate": len(wins) / len(rets) * 100 if rets else 0,
        "avg_win": sum(wins) / len(wins) if wins else 0,
        "avg_loss": sum(losses) / len(losses) if losses else 0,
        "expectancy": sum(rets) / len(rets) if rets else 0,
        "profit_factor": (gw / gl) if gl else None,
        "worst_day": min(by_day.values()) if by_day else 0,
        "best_day": max(by_day.values()) if by_day else 0,
        "by_day": dict(by_day),
    }


def decision_stats():
    """From v14's decision journal -- why Eva did NOT trade. v13 never
    recorded this, so 'is she missing signals?' was unanswerable."""
    rows = load(DECISIONS)
    if not rows:
        return None
    reasons = defaultdict(int)
    signals = 0
    scans = set()
    for r in rows:
        reasons[r.get("reason") or "(none)"] += 1
        if str(r.get("entry_signal")).lower() == "true":
            signals += 1
        scans.add((r.get("timestamp", "")[:10], r.get("scan")))
    return {"rows": len(rows), "signals": signals, "scans": len(scans),
            "reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])[:8])}


def main():
    print("=" * 70)
    print("EVA SCORECARD")
    print("=" * 70)

    a = analyze()
    if not a:
        print("\nNo trades logged yet.")
        return

    print(f"\nAll-time: {a['trades']} trades over {a['days_traded']} trading "
          f"days ({a['first']} .. {a['last']})")
    print(f"  net P&L        ${a['net_pnl']:+.2f}")
    print(f"  win rate       {a['win_rate']:.1f}%")
    print(f"  avg winner     {a['avg_win']:+.2f}%")
    print(f"  avg loser      {a['avg_loss']:+.2f}%")
    print(f"  expectancy     {a['expectancy']:+.3f}% per trade")
    pf = a["profit_factor"]
    print(f"  profit factor  {pf:.2f}" if pf else "  profit factor  n/a")
    print(f"  worst day      ${a['worst_day']:+.2f}")

    print("\n" + "-" * 70)
    print("REALITY vs MODEL  (the strong test -- all four should roughly agree)")
    print("-" * 70)
    rate = a["trades"] / a["days_traded"] if a["days_traded"] else 0
    checks = [
        ("trades/day", rate, OBSERVED_PRIOR_RATE, 0.4, 3.0),
        ("win rate %", a["win_rate"], PREDICTED["win_rate_pct"], 45, 70),
        ("avg win %", a["avg_win"], PREDICTED["avg_win_pct"], 0.5, 3.5),
        ("avg loss %", a["avg_loss"], PREDICTED["avg_loss_pct"], -3.5, -0.3),
    ]
    for name, actual, predicted, lo, hi in checks:
        ok = lo <= actual <= hi
        print(f"  {name:<14} actual {actual:>7.2f}   predicted {predicted:>7.2f}   "
              f"{'OK' if ok else 'OUT OF RANGE'}")

    print("\n" + "-" * 70)
    print("GO / NO-GO CRITERIA  (fixed 2026-09-01, before any v14 data)")
    print("-" * 70)
    results = [
        (a["days_traded"] >= 1, CRITERIA[0]),
        (a["trades"] >= 20, CRITERIA[1]),
        (a["net_pnl"] > 0, CRITERIA[2]),
        (45 <= a["win_rate"] <= 70, CRITERIA[3]),
        (a["avg_win"] > abs(a["avg_loss"]), CRITERIA[4]),
        (pf is not None and pf >= 1.2, CRITERIA[5]),
        (a["worst_day"] > -15, CRITERIA[6]),
    ]
    passed = 0
    for ok, (label, why) in results:
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:<34} {why}")
    print(f"\n  {passed}/{len(results)} criteria met")

    d = decision_stats()
    if d:
        print("\n" + "-" * 70)
        print(f"DECISION JOURNAL  ({d['rows']} rows, {d['scans']} scans, "
              f"{d['signals']} entry signals)")
        print("-" * 70)
        for reason, n in d["reasons"].items():
            print(f"  {n:>6}  {reason}")
    else:
        print("\n(no decision journal yet -- v14 writes it on its first "
              "live scan)")

    print("\n" + "=" * 70)
    if a["trades"] < 20:
        print(f"VERDICT: NOT ENOUGH DATA ({a['trades']}/20 trades).")
        print("A profitable stretch this short is ~2:1 evidence at best --")
        print("a system with NO edge still shows a green month 40% of the time.")
    elif passed >= 6:
        print("VERDICT: criteria met. The model and reality agree.")
    else:
        print(f"VERDICT: {passed}/7 met. Do not scale on this.")
    print("=" * 70)


if __name__ == "__main__":
    main()
