#!/usr/bin/env python3
"""
Is MIN_ZONE_WIDTH_PCT = 3.0 the right threshold, under real capital limits?

WHY ASK
-------
On the live 2026-09-02 session, 16 of 20 watchlist symbols were disqualified
by this one filter before any other logic ran. That is a bigger reduction in
opportunity than anything in the exit rules, and it has never been re-tested
since capital constraints were modelled.

THE NON-OBVIOUS PART
--------------------
Eva has THREE slots on $250 and already skips ~90% of signals for lack of
capital. So the naive prediction -- "loosening the filter gives more trades,
which gives more profit" -- is probably wrong: she cannot afford more trades.

But it might still help, for a different reason. v14 ranks competing
candidates by NET EDGE and takes the best ones. A larger eligible pool means
a better top-3, even at an unchanged trade count. That is selection quality,
not volume, and it is invisible in any unconstrained sim.

It could equally hurt: the 2026-08-21 backtest found narrow zones produce
choppy signals, and that filter held on both walk-forward halves. Adding
junk to the pool could crowd out good setups if net edge ranks it highly.

Both stories are plausible, which is exactly why this needs measuring rather
than reasoning. Tested on three independent splits at the real $250.
"""

import sys
from collections import defaultdict

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")
import sage_bot_v13 as eva
from sim_variations import SPREADS, load_5m, daily_from_5m, levels_for
from sim_portfolio_constrained import run, summarize

THRESHOLDS = [0.0, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
CAPITAL = 250


def build_at(all_5m, min_width):
    """Same as sim_portfolio_constrained.build but with the width gate as a
    parameter instead of reading the module constant."""
    clock = defaultdict(dict)
    levels = defaultdict(dict)
    for sym, bars in all_5m.items():
        daily = daily_from_5m(bars)
        di = {d["date"]: i for i, d in enumerate(daily)}
        for b in bars:
            clock[b["t"]][sym] = b
        for day in {b["date"] for b in bars}:
            lv = levels_for(daily, di[day])
            if not lv or lv["rl"] <= 0:
                continue
            width = (lv["rl"] - lv["sl"]) / lv["rl"] * 100
            if width >= min_width:
                levels[day][sym] = lv
    return clock, levels


def main():
    all_5m = load_5m()
    sess = sorted({b["date"] for s in all_5m for b in all_5m[s]})
    n = len(sess)
    splits = {"A": sess[int(n * .6):], "B": sess[:int(n * .4)], "C": sess[1::2]}

    print(f"{len(all_5m)} symbols | {n} sessions | capital ${CAPITAL} "
          f"(3 slots) | partials ON")
    print("green% is of ALL sessions in the split, NOT just sessions that "
          "traded --\na day Eva sat out did not close profitable either, so it "
          "cannot count as a win.\n")
    print(f"{'min width':>10} {'trades':>7} {'PF':>6} {'net $':>9} "
          f"{'green A':>9} {'green B':>9} {'green C':>9} {'avg':>6} {'worst $':>9}")
    print("-" * 84)

    rows = []
    for w in THRESHOLDS:
        clock, levels = build_at(all_5m, w)
        per, nets, worst, tr = [], [], [], 0
        pfs = []
        for name, test in splits.items():
            bd, trd, sk = run(clock, levels, test, CAPITAL, True)
            s = summarize(bd, trd, CAPITAL)
            if not s:
                per.append(0.0); nets.append(0.0); worst.append(0.0); continue
            green = sum(1 for v in bd.values() if v > 0)
            per.append(green / len(test) * 100)      # denominator = ALL sessions
            nets.append(s["net"]); worst.append(s["worst"])
            tr += s["trades"]; pfs.append(s["pf"])
        avg = sum(per) / 3
        rows.append({"w": w, "net": sum(nets), "per": per, "avg": avg,
                     "worst": min(worst), "pf": sum(pfs)/len(pfs) if pfs else 0})
        mark = "  <- SHIPPED" if w == 3.0 else ""
        print(f"{w:>9.1f}% {tr:>7} {rows[-1]['pf']:>6.2f} {sum(nets):>8.2f} "
              f"{per[0]:>8.0f}% {per[1]:>8.0f}% {per[2]:>8.0f}% {avg:>5.0f}% "
              f"{min(worst):>8.2f}{mark}")

    ship = next(r for r in rows if r["w"] == 3.0)
    print("\n" + "=" * 84)
    print("vs SHIPPED 3.0%, judged on GREEN DAYS (the stated goal).")
    print("A threshold only counts if it wins on ALL THREE splits.")
    print("=" * 84)
    best = None
    for r in rows:
        if r["w"] == 3.0:
            continue
        beat = sum(1 for a, b in zip(r["per"], ship["per"]) if a > b)
        flag = "CONSISTENT 3/3" if beat == 3 else f"{beat}/3 only"
        print(f"  {r['w']:>4.1f}%  green {r['avg']:>4.0f}% "
              f"({r['avg']-ship['avg']:>+5.1f} pts)  net {r['net']:>7.2f} "
              f"({r['net']-ship['net']:>+6.2f})  worst {r['worst']:>7.2f}   {flag}")
        if beat == 3 and (best is None or r["avg"] > best["avg"]):
            best = r
    print("=" * 84)
    if best:
        print(f"  -> {best['w']:.1f}% beats shipped on green days in ALL THREE "
              f"splits: {best['avg']:.0f}% vs {ship['avg']:.0f}%,")
        print(f"     costing {ship['net']-best['net']:+.2f} in net P&L over "
              f"~5 months.")
    else:
        print("  -> NOTHING beats 3.0% consistently. The shipped value stands.")
    print("=" * 84)


if __name__ == "__main__":
    main()
