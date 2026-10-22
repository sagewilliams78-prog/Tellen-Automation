#!/usr/bin/env python3
"""
Score setups like a trader reads a chart, instead of AND-ing hard filters.

SAGE'S POINT, 2026-09-02
------------------------
"maybe we have too many filters -- we need to look at it as a living trader
with all the knowledge of a seasoned trader that makes good decisions, not off
of filters but the charts themselves."

He is right, and the funnel proves it:

    141,960 bars -> 36,368 in buy zone -> 11,687 wide enough -> 5,308 bullish

3.7% survives. Worse, of those 5,308 survivors 45% have reward-to-risk under
0.50 and 15% under 0.25. The cascade discards 96% of setups and still admits
trades that need a 92% win rate. It is not selecting GOOD setups, it is
selecting FEW setups.

The reason is structural: every gate is AND-ed, so they compound
multiplicatively, and no gate can see any other. On 2026-09-02 that produced
two opposite errors on the same afternoon --
  TSLA  zone 2.96% -> REJECTED by the 3.0% gate, despite 37 buy-zone visits
        with 14 bullish candles
  XOM   zone 4.25% -> ACCEPTED, despite a target 0.38% away against a 4% stop
                      (reward-to-risk 0.09, breakeven win rate 92%)
A hard gate cannot trade one factor off against another. A score can.

THE ANTI-CURVE-FIT RULE
-----------------------
A scoring model has far more free parameters than a gate, so it is far easier
to fit to noise. The weights below are therefore fixed BEFORE seeing any
result, are all EQUAL, and are coarse 0-5 integer bands chosen on trading
reasoning alone. They are not tuned afterwards. If the model only works after
adjusting weights, it does not work.

Same protocol as everything else: three independent splits, real capital
limits, and it must win on all three or it does not ship.
"""

import sys
from collections import defaultdict

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")
import sage_bot_v13 as eva
from sim_variations import SPREADS, load_5m, daily_from_5m, levels_for
from sim_portfolio_constrained import run, summarize, RISK_DOLLARS

CAPITAL = 250
RISK = 4.95          # live setting
MAX_FRAC = 0.80


# The rubric now lives in eva_score.py -- the SAME module the live bot imports,
# so the backtest cannot silently drift from what actually trades.
from eva_score import score_setup as _score


def score_setup(b, lv, sym, vol_avg):
    entry = b["close"]
    stop = eva.compute_stop(entry, lv["sl"])
    target = eva.compute_target(lv)
    return _score(entry, stop, target, lv["rl"], lv["sl"],
                  b["open"], b["high"], b["low"],
                  b["volume"], vol_avg, SPREADS.get(sym, 0.03))


def build_scored(all_5m, threshold):
    """Same portfolio clock as the gate version, but eligibility comes from the
    score rather than from AND-ed filters. Only the buy zone itself is kept as
    a hard condition -- that is the strategy's definition, not a filter."""
    clock = defaultdict(dict)
    levels = defaultdict(dict)
    keep = defaultdict(dict)     # (day, sym) -> set of timestamps allowed
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
                total, _ = score_setup(b, lv, sym, avg)
                if total is not None and total >= threshold:
                    ok.add(b["t"])
            keep[day][sym] = ok
    return clock, levels, keep


def main():
    all_5m = load_5m()
    sess = sorted({b["date"] for s in all_5m for b in all_5m[s]})
    n = len(sess)
    splits = {"A": sess[int(n * .6):], "B": sess[:int(n * .4)], "C": sess[1::2]}

    from sim_portfolio_constrained import build as build_gates
    gclock, glevels = build_gates(all_5m)

    print(f"CAPITAL ${CAPITAL} | risk ${RISK} | partials ON")
    print("BASELINE = the current AND-ed filter cascade\n")
    print(f"{'model':<22} {'trades':>7} {'win%':>6} {'PF':>6} {'net $':>9} "
          f"{'grn A':>6} {'grn B':>6} {'grn C':>6} {'avg':>5} {'worst':>8}")
    print("-" * 92)

    def measure(clock, levels, label, mark="", entry_ok=None):
        per, nets, worst, tr, pfs, wins = [], [], [], 0, [], []
        for k, test in splits.items():
            bd, trd, sk = run(clock, levels, test, CAPITAL, True,
                              risk_abs=RISK, max_frac=MAX_FRAC, entry_ok=entry_ok)
            s = summarize(bd, trd, CAPITAL)
            if not s:
                per.append(0); nets.append(0); worst.append(0); continue
            per.append(sum(1 for v in bd.values() if v > 0) / len(test) * 100)
            nets.append(s["net"]); worst.append(s["worst"])
            tr += s["trades"]; pfs.append(s["pf"]); wins.append(s["win"])
        avg = sum(per) / 3
        print(f"{label:<22} {tr:>7} {sum(wins)/len(wins) if wins else 0:>5.1f}% "
              f"{sum(pfs)/len(pfs) if pfs else 0:>6.2f} {sum(nets):>8.2f} "
              f"{per[0]:>5.0f}% {per[1]:>5.0f}% {per[2]:>5.0f}% {avg:>4.0f}% "
              f"{min(worst):>7.2f}{mark}")
        return {"per": per, "nets": nets, "net": sum(nets), "avg": avg,
                "tr": tr, "worst": min(worst)}

    base = measure(gclock, glevels, "filter cascade", "  <- CURRENT")
    print()
    results = {}
    for th in (12, 15, 18, 21, 24):
        clock, levels, keep = build_scored(all_5m, th)
        results[th] = measure(clock, levels, f"score >= {th}/30", entry_ok=keep)

    print("\n" + "=" * 92)
    print("vs the filter cascade. Must win on ALL THREE splits to count.")
    print("=" * 92)
    for th, r in results.items():
        gb = sum(1 for x, y in zip(r["per"], base["per"]) if x > y)
        nb = sum(1 for x, y in zip(r["nets"], base["nets"]) if x > y)
        print(f"  score >= {th:>2}   green {r['avg']:>4.0f}% "
              f"({r['avg']-base['avg']:>+5.1f})  net {r['net']:>7.2f} "
              f"({r['net']-base['net']:>+6.2f})  trades {base['tr']}->{r['tr']:<5} "
              f"green {gb}/3, net {nb}/3")
    print("=" * 92)
    ok = [th for th, r in results.items()
          if sum(1 for x, y in zip(r["nets"], base["nets"]) if x > y) == 3
          and sum(1 for x, y in zip(r["per"], base["per"]) if x > y) == 3]
    print(f"  -> {'SHIPPABLE at ' + str(ok) if ok else 'nothing wins 3/3 on both. Do not ship.'}")
    print("=" * 92)


if __name__ == "__main__":
    main()
