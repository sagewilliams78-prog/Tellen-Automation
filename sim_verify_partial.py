#!/usr/bin/env python3
"""
Verify the partial-profit exit EXACTLY as shipped in eva_v14.py.

Why this exists separately from sim_variations.py:

The variation that got chosen was modelled loosely. The code that actually
shipped evaluates exits in a specific ORDER -- stop, then target, then
partial -- because a gap straight through the target must take the whole
position, not half of it. That ordering is a real behavioural difference
from the loose model, so the number that justified the change has to be
re-earned against the code that will really run. Otherwise the validation
is of a strategy nobody is running.

Also enforces the shipped $1.50-per-side minimum: a partial that would
leave either half below it is skipped, exactly as the live guard does.

Measured on three independent train/test splits, because a single split
is how you get fooled.
"""

import sys
from collections import defaultdict

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")
import sage_bot_v13 as eva
from sim_variations import SPREADS, load_5m, daily_from_5m, levels_for

PARTIAL_AT = 1.0      # eva_v14_config.json exits.partial_at_pct
PARTIAL_FRAC = 0.5    # exits.partial_fraction
NOTIONAL = 150.0      # Eva's per-trade cap; both halves must clear $1.50


def run(all_5m, sessions, partial=False):
    """Returns (trade_returns, per_day_pnl_pct). Mirrors the shipped branch
    order: STOP -> TARGET -> PARTIAL."""
    want = set(sessions)
    trades = []
    by_day = defaultdict(float)

    for sym, bars in all_5m.items():
        sp = SPREADS.get(sym, 0.03)
        daily = daily_from_5m(bars)
        di = {d["date"]: i for i, d in enumerate(daily)}
        byday = defaultdict(list)
        for b in bars:
            byday[b["date"]].append(b)

        for day in sorted(byday):
            if day not in want:
                continue
            lv = levels_for(daily, di[day])
            if not lv or not eva.zone_width_ok(lv):
                continue
            session = byday[day]
            pos = None
            entries_today = 0

            for k, b in enumerate(session):
                if pos:
                    size = pos["size"]          # fraction of position still held

                    # ---- STOP (checked first, as shipped) ----
                    if b["low"] <= pos["stop"]:
                        r = (pos["stop"] - pos["entry"]) / pos["entry"] * 100 - sp
                        trades.append(r * size); by_day[day] += r * size
                        pos = None
                        continue

                    # ---- TARGET (before partial: a gap to target exits ALL) ----
                    if b["high"] >= pos["target"]:
                        r = (pos["target"] - pos["entry"]) / pos["entry"] * 100 - sp
                        trades.append(r * size); by_day[day] += r * size
                        pos = None
                        continue

                    # ---- PARTIAL (last) ----
                    if partial and not pos["took"]:
                        trig = pos["entry"] * (1 + PARTIAL_AT / 100)
                        if b["high"] >= trig:
                            part_notional = NOTIONAL * size * PARTIAL_FRAC
                            rest_notional = NOTIONAL * size * (1 - PARTIAL_FRAC)
                            # shipped guard: skip if either side is too small
                            if part_notional >= 1.50 and rest_notional >= 1.50:
                                r = PARTIAL_AT - sp
                                took = size * PARTIAL_FRAC
                                trades.append(r * took); by_day[day] += r * took
                                pos["size"] = size - took
                                pos["took"] = True

                    if k == len(session) - 1:
                        r = (b["close"] - pos["entry"]) / pos["entry"] * 100 - sp
                        trades.append(r * pos["size"]); by_day[day] += r * pos["size"]
                        pos = None
                    continue

                if k == len(session) - 1 or entries_today >= 1:
                    continue
                if b["low"] > lv["rl"] or eva.zone_of(b["close"], lv) != "BUY":
                    continue
                if b["close"] <= b["open"]:          # require_bullish_candle
                    continue
                entry = b["close"]
                stop = eva.compute_stop(entry, lv["sl"])
                target = eva.compute_target(lv)
                if stop >= entry or target <= entry:
                    continue
                pos = {"entry": entry, "stop": stop, "target": target,
                       "size": 1.0, "took": False}
                entries_today += 1

    return trades, by_day


def stats(trades, by_day):
    if not trades:
        return None
    w = [x for x in trades if x > 0]
    gl = abs(sum(x for x in trades if x <= 0))
    days = [v for v in by_day.values()]
    green = sum(1 for v in days if v > 0)
    return {"n": len(trades), "win": len(w) / len(trades) * 100,
            "total": sum(trades), "pf": (sum(w) / gl) if gl else float("inf"),
            "days": len(days), "green": green,
            "green_pct": green / len(days) * 100 if days else 0,
            "worst_day": min(days) if days else 0}


def main():
    all_5m = load_5m()
    sess = sorted({b["date"] for s in all_5m for b in all_5m[s]})
    n = len(sess)
    splits = {
        "A first60/last40": (sess[:int(n * .6)], sess[int(n * .6):]),
        "B reversed":       (sess[int(n * .4):], sess[:int(n * .4)]),
        "C interleaved":    (sess[::2], sess[1::2]),
    }

    print(f"{len(all_5m)} symbols | {n} sessions ({sess[0]} .. {sess[-1]})")
    print("Exit order as shipped: STOP -> TARGET -> PARTIAL\n")
    print(f"{'split':<20} {'variant':<12} {'trades':>7} {'win%':>7} "
          f"{'PF':>6} {'total%':>8} {'green days':>12} {'worst day':>10}")
    print("-" * 90)

    verdict = []
    for name, (_, test) in splits.items():
        row = {}
        for label, use in (("baseline", False), ("partial", True)):
            t, d = run(all_5m, test, partial=use)
            s = stats(t, d)
            row[label] = s
            print(f"{name:<20} {label:<12} {s['n']:>7} {s['win']:>6.1f}% "
                  f"{s['pf']:>6.2f} {s['total']:>7.1f}% "
                  f"{s['green']:>4}/{s['days']:<3} {s['green_pct']:>4.0f}% "
                  f"{s['worst_day']:>9.1f}%")
        better = row["partial"]["green_pct"] > row["baseline"]["green_pct"]
        pf_held = row["partial"]["pf"] >= row["baseline"]["pf"] * 0.90
        verdict.append((name, better, pf_held))
        print()

    print("=" * 90)
    ok = sum(1 for _, b, p in verdict if b and p)
    for name, b, p in verdict:
        print(f"  {name:<20} green days {'UP' if b else 'DOWN':<5} | "
              f"profit factor {'held' if p else 'DEGRADED'}")
    print(f"\n  {ok}/3 splits improved green days without losing edge")
    if ok == 3:
        print("  -> holds up as shipped. Keep it enabled.")
    elif ok >= 2:
        print("  -> mostly holds. Marginal; watch it live.")
    else:
        print("  -> DOES NOT hold as shipped. Set partial_enabled=false.")
    print("=" * 90)


if __name__ == "__main__":
    main()
