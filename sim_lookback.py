#!/usr/bin/env python3
"""
Does SWING_LOOKBACK_DAYS = 5 cause the degenerate zones that shut Eva down?

THE MECHANISM (observed live, 2026-09-02)
-----------------------------------------
    SL = min(low of the last N sessions)
    RL = yesterday's low
    buy zone = RL .. SL, and it is rejected if narrower than 3%

In a sustained rally, yesterday's low IS frequently the N-day low. Then
RL == SL, the buy zone has ZERO width, and the symbol is disqualified before
any signal logic runs. On 2026-09-02 that happened to 8 of 20 symbols
outright, and 17 of 20 failed the width gate overall. The three survivors
never pulled back; the three that did pull back (TSLA, COIN, MSFT) were all
disqualified. Result: 96 scans, zero trades.

So the width gate is not the disease, it is the thermometer. The lookback is
what sets the zone.

THE HYPOTHESIS
--------------
A LONGER lookback reaches further back for the swing low, so SL sits below
yesterday's low more often, the zone stays open, and Eva is eligible on days
she currently sits out.

WHY IT MIGHT STILL LOSE
-----------------------
compute_stop() is anchored to SL. A deeper SL means a wider stop, which under
fixed $2.50 risk means FEWER SHARES, and beyond ~4% it just clamps to
STOP_LOSS_BACKSTOP_PCT anyway. So a longer lookback could buy eligibility and
pay for it in position size and in stops that no longer sit under real
support. More trades is not the goal -- more GREEN DAYS is.

Judged on green days as a share of ALL sessions, on three independent splits.
A change counts only if it wins on all three.
"""

import sys
from collections import defaultdict

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")
import sage_bot_v13 as eva
from sim_variations import load_5m, daily_from_5m
from sim_portfolio_constrained import run, summarize

LOOKBACKS = [2, 3, 4, 5, 7, 10, 15, 20]
CAPITAL = 250
MIN_WIDTH = 3.0


def levels_lb(daily, i, lb):
    past = daily[:i]
    if len(past) < lb:
        return None
    y = past[-1]
    look = past[-lb:]
    rh, rl = y["high"], y["low"]
    return {"rh": rh, "rl": rl,
            "sh": max(max(b["high"] for b in look), rh),
            "sl": min(min(b["low"] for b in look), rl)}


def build_lb(all_5m, lb):
    clock = defaultdict(dict)
    levels = defaultdict(dict)
    elig = degen = total = 0
    for sym, bars in all_5m.items():
        daily = daily_from_5m(bars)
        di = {d["date"]: i for i, d in enumerate(daily)}
        for b in bars:
            clock[b["t"]][sym] = b
        for day in {b["date"] for b in bars}:
            lv = levels_lb(daily, di[day], lb)
            if not lv or lv["rl"] <= 0:
                continue
            total += 1
            if lv["rl"] == lv["sl"]:
                degen += 1
            if (lv["rl"] - lv["sl"]) / lv["rl"] * 100 >= MIN_WIDTH:
                levels[day][sym] = lv
                elig += 1
    return clock, levels, elig, degen, total


def main():
    all_5m = load_5m()
    sess = sorted({b["date"] for s in all_5m for b in all_5m[s]})
    n = len(sess)
    splits = {"A": sess[int(n * .6):], "B": sess[:int(n * .4)], "C": sess[1::2]}

    print(f"{len(all_5m)} symbols | {n} sessions | ${CAPITAL} | "
          f"width gate {MIN_WIDTH}% | partials ON")
    print("green% = share of ALL sessions closing green (a day Eva sat out "
          "is not a win)\n")
    print(f"{'lookback':>9} {'eligible':>9} {'degen':>7} {'trades':>7} {'PF':>6} "
          f"{'net $':>9} {'grn A':>7} {'grn B':>7} {'grn C':>7} {'avg':>6} "
          f"{'worst':>8}")
    print("-" * 96)

    rows = []
    for lb in LOOKBACKS:
        clock, levels, elig, degen, total = build_lb(all_5m, lb)
        per, nets, worst, tr, pfs = [], [], [], 0, []
        for name, test in splits.items():
            bd, trd, sk = run(clock, levels, test, CAPITAL, True)
            s = summarize(bd, trd, CAPITAL)
            if not s:
                per.append(0.0); nets.append(0.0); worst.append(0.0); continue
            per.append(sum(1 for v in bd.values() if v > 0) / len(test) * 100)
            nets.append(s["net"]); worst.append(s["worst"])
            tr += s["trades"]; pfs.append(s["pf"])
        avg = sum(per) / 3
        rows.append({"lb": lb, "net": sum(nets), "per": per, "avg": avg,
                     "worst": min(worst), "pf": sum(pfs)/len(pfs) if pfs else 0,
                     "trades": tr})
        mark = "  <- SHIPPED" if lb == 5 else ""
        print(f"{lb:>9} {elig:>9} {degen/total*100:>6.0f}% {tr:>7} "
              f"{rows[-1]['pf']:>6.2f} {sum(nets):>8.2f} "
              f"{per[0]:>6.0f}% {per[1]:>6.0f}% {per[2]:>6.0f}% {avg:>5.0f}% "
              f"{min(worst):>7.2f}{mark}")

    ship = next(r for r in rows if r["lb"] == 5)
    print("\n" + "=" * 96)
    print("vs SHIPPED lookback 5, judged on GREEN DAYS. Must win ALL THREE splits.")
    print("=" * 96)
    best = None
    for r in rows:
        if r["lb"] == 5:
            continue
        beat = sum(1 for a, b in zip(r["per"], ship["per"]) if a > b)
        flag = "CONSISTENT 3/3" if beat == 3 else f"{beat}/3 only"
        print(f"  lookback {r['lb']:>2}  green {r['avg']:>4.0f}% "
              f"({r['avg']-ship['avg']:>+5.1f})  net {r['net']:>7.2f} "
              f"({r['net']-ship['net']:>+6.2f})  trades {r['trades']:>4} "
              f"  worst {r['worst']:>7.2f}   {flag}")
        if beat == 3 and (best is None or r["avg"] > best["avg"]):
            best = r
    print("=" * 96)
    if best:
        print(f"  -> lookback {best['lb']} beats shipped on green days in ALL "
              f"THREE splits ({best['avg']:.0f}% vs {ship['avg']:.0f}%),")
        print(f"     net P&L {best['net']-ship['net']:+.2f}, "
              f"trades {ship['trades']} -> {best['trades']}.")
    else:
        print("  -> NOTHING beats lookback 5 consistently. Shipped value stands.")
    print("=" * 96)


if __name__ == "__main__":
    main()
