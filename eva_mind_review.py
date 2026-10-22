#!/usr/bin/env python3
"""
Build Eva's Mind from evidence, and check whether her factors are real.

This is the learning loop, and it is deliberately not an optimiser. It asks one
question per factor -- did setups that scored HIGH on it actually trade better
than setups that scored LOW? -- and writes the answer down, including when the
answer is "there is not enough data to say," which is the answer most of the
time and the one an optimiser would quietly skip.

Nothing here changes how Eva trades. It produces notes a person reads.

Two sources, kept separate on purpose:
  BACKTEST  96 sessions of scored setups with known outcomes. Enough rows to
            say something, but one market regime and simulated fills.
  LIVE      ~/eva_score_shadow.csv, what the scorer said on real data, plus
            trading_log_v9.csv for what actually filled. Few rows, but real.

Run:  python eva_mind_review.py
"""

import csv
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")
import sage_bot_v13 as eva
import eva_mind
from eva_score import DEFAULT_THRESHOLD, FACTORS, score_setup
from sim_variations import SPREADS, load_5m, daily_from_5m, levels_for
from sim_portfolio_constrained import run, summarize

SHADOW_LOG = os.path.expanduser("~/eva_score_shadow.csv")
CAPITAL, RISK = 250, 4.95


def build_scored_with_meta(all_5m, threshold):
    """Same eligibility as the live scorer, but keeping each setup's factor
    breakdown so an outcome can be traced back to the reasoning."""
    clock = defaultdict(dict)
    levels = defaultdict(dict)
    keep = defaultdict(dict)
    meta = defaultdict(lambda: defaultdict(dict))
    for sym, bars in all_5m.items():
        daily = daily_from_5m(bars)
        di = {d["date"]: i for i, d in enumerate(daily)}
        byday = defaultdict(list)
        for b in bars:
            clock[b["t"]][sym] = b
            byday[b["date"]].append(b)
        for day, session in byday.items():
            lv = levels_for(daily, di[day])
            if not lv or lv["rl"] <= 0:
                continue
            levels[day][sym] = lv
            vols = [x["volume"] for x in session]
            ok = set()
            for k, b in enumerate(session):
                if eva.zone_of(b["close"], lv) != "BUY":
                    continue
                base = vols[max(0, k - 20):k]
                avg = sum(base) / len(base) if base else 0
                entry = b["close"]
                stop = eva.compute_stop(entry, lv["sl"])
                target = eva.compute_target(lv)
                total, parts = score_setup(
                    entry, stop, target, lv["rl"], lv["sl"],
                    b["open"], b["high"], b["low"], b["volume"], avg,
                    SPREADS.get(sym, 0.03))
                if total is None or total < threshold:
                    continue
                ok.add(b["t"])
                meta[day][sym][b["t"]] = (total, parts)
            keep[day][sym] = ok
    return clock, levels, keep, meta


def main():
    print("Building Eva's Mind\n" + "=" * 60)
    all_5m = load_5m()
    sess = sorted({b["date"] for s in all_5m for b in all_5m[s]})
    clock, levels, keep, meta = build_scored_with_meta(all_5m, DEFAULT_THRESHOLD)

    bd, trades, skipped = run(clock, levels, sess, CAPITAL, True,
                              risk_abs=RISK, max_frac=0.80,
                              entry_ok=keep, entry_meta=meta)
    real = [t for t in trades if t["tag"] != "PARTIAL" and t.get("meta")]
    print(f"  {len(sess)} sessions, {len(real)} completed trades with reasoning\n")

    # ---- factor buckets: does a high score on X actually trade better? ----
    buckets = {f: defaultdict(lambda: {"n": 0, "wins": 0, "pnl": 0.0})
               for f in FACTORS}
    symbols = defaultdict(lambda: {"n": 0, "taken": 0, "wins": 0, "pnl": 0.0,
                                   "score_sum": 0, "spread": 0.0})
    for t in real:
        total, parts = t["meta"]
        win = t["pnl"] > 0
        for f in FACTORS:
            b = buckets[f][parts[f]]
            b["n"] += 1
            b["wins"] += win
            b["pnl"] += t["pnl"]
        s = symbols[t["sym"]]
        s["n"] += 1; s["taken"] += 1; s["wins"] += win
        s["pnl"] += t["pnl"]; s["score_sum"] += total
        s["spread"] = SPREADS.get(t["sym"], 0.03)

    overall_wr = sum(1 for t in real if t["pnl"] > 0) / len(real) * 100 if real else 0

    # ---- write the vault ----
    eva_mind.write_note("", "Eva Scoring Model", eva_mind.model_note())
    print("  factor verdicts:")
    verdicts = {}
    for f in FACTORS:
        note = eva_mind.factor_note(f, dict(buckets[f]), overall_wr)
        eva_mind.write_note("Factors", eva_mind.FACTOR_TITLES[f], note)
        v = "unknown"
        for line in note.splitlines():
            if line.startswith("**Verdict:"):
                v = line.replace("**Verdict:", "").strip(" *")
        verdicts[f] = v
        print(f"    {eva_mind.FACTOR_TITLES[f]:<22} {v}")

    for sym, rec in symbols.items():
        eva_mind.write_note("Symbols", sym, eva_mind.symbol_note(sym, rec))

    by_day = defaultdict(lambda: {"trades": 0, "pnl": 0.0, "scored": 0,
                                  "passed": 0, "median_score": 0})
    day_scores = defaultdict(list)
    for t in real:
        d = by_day[t["day"]]
        d["trades"] += 1; d["pnl"] += t["pnl"]
        day_scores[t["day"]].append(t["meta"][0])
    for day, sc in day_scores.items():
        by_day[day]["scored"] = len(sc)
        by_day[day]["passed"] = len(sc)
        by_day[day]["median_score"] = int(statistics.median(sc))
    for day, stats in by_day.items():
        eva_mind.write_note("Sessions", f"Session {day}",
                            eva_mind.session_note(day, stats))

    # ---- live shadow data, kept honestly separate from the backtest ----
    live_line = ""
    if os.path.exists(SHADOW_LOG):
        rows = list(csv.DictReader(open(SHADOW_LOG)))
        dis = sum(1 for r in rows if r.get("agree") == "False")
        would = sum(1 for r in rows if r.get("score_would_enter") == "True")
        live_line = (f"Live shadow log: **{len(rows)} setups scored**, "
                     f"{would} would have been entered, {dis} disagreements "
                     f"with the old filters. This is the record that will "
                     f"eventually settle whether the model is real -- it is "
                     f"far too small to mean anything yet.")

    strong = [eva_mind.FACTOR_TITLES[f] for f, v in verdicts.items()
              if v.startswith("PREDICTIVE")]
    dead = [eva_mind.FACTOR_TITLES[f] for f, v in verdicts.items()
            if v.startswith("NO SIGNAL") or v.startswith("INVERTED")]
    headline = (
        f"On {len(real)} backtested trades, "
        + (f"**{', '.join(strong)}** separated winners from losers. " if strong
           else "no factor yet separates winners from losers with enough data. ")
        + (f"**{', '.join(dead)}** did not, and their weight is currently "
           f"unjustified. " if dead else "")
        + "Weights have not been changed -- that stays a human decision.\n\n"
        + live_line)

    eva_mind.write_note("", "Index",
                        eva_mind.rebuild_index(list(FACTORS), symbols.keys(),
                                               by_day.keys(), headline))
    print(f"\n  vault written to {eva_mind.VAULT}")
    print(f"  {len(symbols)} symbols, {len(by_day)} sessions, "
          f"{len(FACTORS)} factor notes")
    if dead:
        print(f"\n  ⚠️  factors showing NO SIGNAL: {', '.join(dead)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
