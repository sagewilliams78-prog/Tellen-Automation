#!/usr/bin/env python3
"""
Find a strategy worth building. Benchmark: buy-and-hold, +15.2%.

WHY THE OLD ONE IS BEING REPLACED
----------------------------------
Measured over 96 sessions on the same 20 symbols:

    buy and hold, equal weight ....... +15.2%
    Eva's filter cascade .............  +9.4%

She underperformed doing nothing, in a market where 14 of 20 symbols rose.
Live she took 5 trades for +$0.86, and EVERY ONE exited EOD_FLATTEN -- she
never once reached a target or a stop. The strategy does not complete; it
times out at 15:55 and closes whatever it happens to hold.

The cause is geometry. Target = 25% of yesterday's range, which on a typical
day is +0.4%. Stop = the 5-day swing low, which clamps to the -4% backstop.
Risking 4% to make 0.4% needs a 92% win rate. Live reward-to-risk scored
0.83 out of 5. No amount of filter tuning fixes a trade that cannot be won.

So every candidate here inverts that: targets are ATR-scaled and LARGER than
stops, and positions may be held overnight.

THE OTHER LESSON: EXPOSURE
--------------------------
Buy-and-hold won because it was invested 100% of the time. Eva is long maybe
2% of the time -- intraday only, 1-2 positions, a handful of trades. In a
rising market, time in the market beat timing it. Candidates that hold longer
are therefore tested explicitly, including a pure overnight-gap capture, since
being flat overnight is exactly where a rising market does its work.

THE BAR
-------
Must beat +15.2% buy-and-hold on ALL THREE splits. Not "profitable" -- better
than doing nothing. That is the standard the old bot failed.

Costs are real measured spreads. Nothing here is free.
"""

import sys
import statistics
from collections import defaultdict

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")
import sage_bot_v13 as eva
from sim_variations import SPREADS, load_5m, daily_from_5m


def atr(bars, i, n=14):
    """True range average over the n days ending at i-1 (causal)."""
    if i < n + 1:
        return None
    trs = []
    for k in range(i - n, i):
        h, l, pc = bars[k]["high"], bars[k]["low"], bars[k - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)


def buy_hold(daily, lo, hi, sp):
    """Benchmark. Buy at the open of the window, sell at the end."""
    if hi - lo < 2:
        return None
    return (daily[hi - 1]["close"] - daily[lo]["close"]) / daily[lo]["close"] * 100 - sp


def strat(daily, lo, hi, sp, cfg):
    """One symbol, one window. Returns list of trade returns in %."""
    out = []
    pos = None
    for i in range(max(lo, 20), hi):
        b = daily[i]
        if pos:
            held = i - pos["i"]
            # stop first (pessimistic), then target, then time
            if b["low"] <= pos["stop"]:
                out.append((pos["stop"] - pos["e"]) / pos["e"] * 100 - sp)
                pos = None
                continue
            if pos["tgt"] and b["high"] >= pos["tgt"]:
                out.append((pos["tgt"] - pos["e"]) / pos["e"] * 100 - sp)
                pos = None
                continue
            if held >= cfg["maxhold"]:
                out.append((b["close"] - pos["e"]) / pos["e"] * 100 - sp)
                pos = None
                continue
            if cfg.get("trail_atr"):
                a = atr(daily, i)
                if a:
                    pos["stop"] = max(pos["stop"], b["close"] - cfg["trail_atr"] * a)
            continue

        a = atr(daily, i)
        if not a or a <= 0:
            continue
        e = b["close"]
        sig = False
        if cfg["entry"] == "dip":
            ma = sum(x["close"] for x in daily[i - 20:i]) / 20
            sig = e < ma - cfg["k"] * a
        elif cfg["entry"] == "breakout":
            hh = max(x["high"] for x in daily[i - cfg["look"]:i])
            sig = e > hh
        elif cfg["entry"] == "trend_pullback":
            ma = sum(x["close"] for x in daily[i - 50:i]) / 50 if i >= 50 else None
            if ma:
                ma20 = sum(x["close"] for x in daily[i - 20:i]) / 20
                sig = e > ma and e < ma20      # uptrend, short-term dip
        elif cfg["entry"] == "always":
            sig = True
        if not sig:
            continue
        pos = {"i": i, "e": e,
               "stop": e - cfg["stop_atr"] * a,
               "tgt": e + cfg["tgt_atr"] * a if cfg["tgt_atr"] else None}
    return out


CANDIDATES = {
    "dip 1atr, tgt3/stop1.5, 10d":
        {"entry": "dip", "k": 1.0, "tgt_atr": 3, "stop_atr": 1.5, "maxhold": 10},
    "dip 1atr, tgt4/stop2, 20d":
        {"entry": "dip", "k": 1.0, "tgt_atr": 4, "stop_atr": 2, "maxhold": 20},
    "dip 0.5atr, tgt3/stop1.5, 15d":
        {"entry": "dip", "k": 0.5, "tgt_atr": 3, "stop_atr": 1.5, "maxhold": 15},
    "breakout 20d, tgt4/stop2":
        {"entry": "breakout", "look": 20, "tgt_atr": 4, "stop_atr": 2, "maxhold": 20},
    "breakout 20d, trail 2atr":
        {"entry": "breakout", "look": 20, "tgt_atr": None, "stop_atr": 2,
         "maxhold": 40, "trail_atr": 2},
    "breakout 10d, tgt3/stop1.5":
        {"entry": "breakout", "look": 10, "tgt_atr": 3, "stop_atr": 1.5, "maxhold": 15},
    "uptrend pullback, tgt3/stop2":
        {"entry": "trend_pullback", "tgt_atr": 3, "stop_atr": 2, "maxhold": 20},
    "uptrend pullback, trail 2atr":
        {"entry": "trend_pullback", "tgt_atr": None, "stop_atr": 2,
         "maxhold": 40, "trail_atr": 2},
    "always in, trail 3atr":
        {"entry": "always", "tgt_atr": None, "stop_atr": 3,
         "maxhold": 60, "trail_atr": 3},
}


def main():
    all_5m = load_5m()
    dailies = {s: daily_from_5m(b) for s, b in all_5m.items()}
    n = min(len(d) for d in dailies.values())
    splits = {"A": (int(n * .6), n), "B": (0, int(n * .4)),
              "C": (int(n * .3), int(n * .8))}

    # benchmark
    bh = {}
    for k, (lo, hi) in splits.items():
        r = [buy_hold(d, lo, hi, SPREADS.get(s, .03))
             for s, d in dailies.items()]
        r = [x for x in r if x is not None]
        bh[k] = sum(r) / len(r)
    print(f"{len(dailies)} symbols, {n} sessions. Real spreads applied.")
    print(f"BENCHMARK buy & hold:  A {bh['A']:+.1f}%   B {bh['B']:+.1f}%   "
          f"C {bh['C']:+.1f}%\n")
    print(f"{'candidate':<32} {'trades':>7} {'win':>6} {'PF':>6} "
          f"{'A':>8} {'B':>8} {'C':>8}  beats B&H")
    print("-" * 92)

    winners = []
    for name, cfg in CANDIDATES.items():
        per = {}
        tot_t = 0
        allr = []
        for k, (lo, hi) in splits.items():
            rs = []
            for s, d in dailies.items():
                rs += strat(d, lo, hi, SPREADS.get(s, .03), cfg)
            # equal-weight per-symbol average return over the window
            per[k] = sum(rs) / len(dailies) if rs else 0.0
            tot_t += len(rs)
            allr += rs
        if not allr:
            continue
        w = [x for x in allr if x > 0]
        gl = abs(sum(x for x in allr if x <= 0))
        pf = (sum(w) / gl) if gl else 99
        beat = sum(1 for k in splits if per[k] > bh[k])
        flag = "  *** 3/3" if beat == 3 else f"  {beat}/3"
        print(f"{name:<32} {tot_t:>7} {len(w)/len(allr)*100:>5.0f}% {pf:>6.2f} "
              f"{per['A']:>+7.1f}% {per['B']:>+7.1f}% {per['C']:>+7.1f}%{flag}")
        if beat == 3:
            winners.append((name, cfg, per, pf, tot_t))

    print("\n" + "=" * 92)
    if winners:
        for name, cfg, per, pf, t in winners:
            print(f"  BEATS BUY & HOLD ON ALL THREE: {name}")
            print(f"    {t} trades, PF {pf:.2f}, "
                  f"A {per['A']:+.1f}% B {per['B']:+.1f}% C {per['C']:+.1f}%")
    else:
        print("  NOTHING beat buy & hold on all three splits.")
        print("  That is a real result: it says do not run a bot on this data.")
    print("=" * 92)


if __name__ == "__main__":
    main()
