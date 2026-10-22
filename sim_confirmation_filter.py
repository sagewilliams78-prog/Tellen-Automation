#!/usr/bin/env python3
"""
Measure what the 5-MINUTE CONFIRMATION CANDLE is actually worth.

This is the component nobody has quantified, and the daily-bar sim suggested
it is carrying the entire strategy: that sim took 252 trades and lost badly,
while Eva really took 4 trades over the same window and finished POSITIVE.
The confirmation filter is the main difference between those two worlds.

WHAT IS COMPARED (identical entries otherwise, one variable changed):

  ARM A  zone only          enter on the first 5m bar whose low <= RL
  ARM B  zone + bullish     ... and that bar closed above its open
  ARM C  zone + bullish     ... and it is Eva's real rule, including the
         + volume             VOLUME_CONFIRMATION_RATIO check she tracks

Everything else is Eva's live logic, read from sage_bot_v13.py rather than
re-typed: real levels (get_daily_levels), real zone width gate, real stop
(compute_stop), real target (compute_target), real EOD flatten at 15:55 ET.

REAL DATA: Robinhood 5-minute bars, 2026-07-01 .. 2026-09-01, 8 symbols.
Spread is charged on every trade at the values measured 2026-09-01.

HONEST LIMITS
  - 2 months, 8 symbols. Directional, not definitive.
  - Entry filled at the confirming bar's CLOSE; real fills slip.
  - Daily levels are rebuilt from the 5m bars themselves, so the first
    SWING_LOOKBACK_DAYS of the window are skipped.
  - No earnings blackout or weekly win-rate breaker -- those only ever REMOVE
    trades, so all three arms are equally affected and the comparison holds.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")
import sage_bot_v13 as eva          # real strategy math, not a copy

TOOLS = Path("/Users/sagewilliams/.claude/projects/"
             "-Users-sagewilliams-Desktop-Sages-trading-bot/"
             "078e0397-347a-4124-b98c-328086eb407d/tool-results")

SPREADS = {
    "NVDA": 0.005, "MSFT": 0.016, "AMD": 0.012, "TSLA": 0.010,
    "IBRX": 0.127, "IOVA": 0.123, "COIN": 0.030, "GDX": 0.020,
}

ET = timezone.utc  # bars are UTC; RTH bounds already applied by the API


def load_5m():
    """Every 5-minute bar from the saved tool-result files, keyed by symbol."""
    out = defaultdict(list)
    for f in sorted(TOOLS.glob("*get_equity_historicals*.txt")):
        if f.stat().st_size < 400_000:      # skip the daily-bar files
            continue
        try:
            raw = json.loads(f.read_text())
        except ValueError:
            continue
        for r in raw.get("data", {}).get("results", []):
            if r.get("interval") != "5minute":
                continue
            sym = r["symbol"]
            for b in r.get("bars", []):
                if b.get("interpolated"):
                    continue
                t = datetime.fromisoformat(b["begins_at"].replace("Z", "+00:00"))
                out[sym].append({
                    "t": t,
                    "date": t.date().isoformat(),
                    "open": float(b["open_price"]),
                    "high": float(b["high_price"]),
                    "low": float(b["low_price"]),
                    "close": float(b["close_price"]),
                    "volume": float(b.get("volume") or 0),
                })
    for s in out:
        out[s].sort(key=lambda x: x["t"])
        # de-dupe overlapping fetches
        seen, uniq = set(), []
        for b in out[s]:
            if b["t"] in seen:
                continue
            seen.add(b["t"])
            uniq.append(b)
        out[s] = uniq
    return dict(out)


def daily_from_5m(bars):
    """Roll 5m bars into true daily OHLC, so levels match get_daily_levels."""
    days = defaultdict(list)
    for b in bars:
        days[b["date"]].append(b)
    out = []
    for d in sorted(days):
        g = days[d]
        out.append({"date": d, "open": g[0]["open"], "close": g[-1]["close"],
                    "high": max(x["high"] for x in g),
                    "low": min(x["low"] for x in g)})
    return out


def levels_for(daily, i):
    """Eva's real level construction, from bars strictly before day i."""
    past = daily[:i]
    if len(past) < eva.SWING_LOOKBACK_DAYS:
        return None
    y = past[-1]
    look = past[-eva.SWING_LOOKBACK_DAYS:]
    rh, rl = y["high"], y["low"]
    sh = max(max(b["high"] for b in look), rh)
    sl = min(min(b["low"] for b in look), rl)
    return {"rh": rh, "rl": rl, "sh": max(sh, rh), "sl": min(sl, rl)}


def run_arm(all_5m, mode):
    """One trading arm. mode: 'zone' | 'bullish' | 'bullish_vol'."""
    trades = []
    for sym, bars in all_5m.items():
        sp = SPREADS.get(sym, 0.03)
        daily = daily_from_5m(bars)
        dindex = {d["date"]: i for i, d in enumerate(daily)}
        byday = defaultdict(list)
        for b in bars:
            byday[b["date"]].append(b)

        for day in sorted(byday):
            i = dindex[day]
            lv = levels_for(daily, i)
            if not lv or not eva.zone_width_ok(lv):
                continue

            session = byday[day]
            # Volume baseline = this day's trailing average, same spirit as
            # Eva's VOLUME_LOOKBACK_BARS check.
            vols = [b["volume"] for b in session]
            pos = None

            for k, b in enumerate(session):
                # ---- manage an open position first (exits beat entries) ----
                if pos:
                    if b["low"] <= pos["stop"]:
                        trades.append({"sym": sym, "day": day, "reason": "STOP",
                                       "ret": (pos["stop"] - pos["entry"]) / pos["entry"] * 100 - sp})
                        pos = None
                        continue
                    if b["high"] >= pos["target"]:
                        trades.append({"sym": sym, "day": day, "reason": "TARGET",
                                       "ret": (pos["target"] - pos["entry"]) / pos["entry"] * 100 - sp})
                        pos = None
                        continue
                    if k == len(session) - 1:      # EOD flatten
                        trades.append({"sym": sym, "day": day, "reason": "EOD",
                                       "ret": (b["close"] - pos["entry"]) / pos["entry"] * 100 - sp})
                        pos = None
                    continue

                if k == len(session) - 1:
                    continue                        # no entry on the last bar

                # ---- entry test ----
                if b["low"] > lv["rl"]:
                    continue                        # never reached the zone
                if eva.zone_of(b["close"], lv) != "BUY":
                    continue

                if mode in ("bullish", "bullish_vol"):
                    if b["close"] <= b["open"]:
                        continue                    # THE CONFIRMATION CANDLE
                if mode == "bullish_vol":
                    base = vols[max(0, k - 20):k]
                    avg = sum(base) / len(base) if base else 0
                    if avg > 0 and b["volume"] < avg * eva.VOLUME_CONFIRMATION_RATIO:
                        continue

                entry = b["close"]
                stop = eva.compute_stop(entry, lv["sl"])
                target = eva.compute_target(lv)
                if stop >= entry or target <= entry:
                    continue
                pos = {"entry": entry, "stop": stop, "target": target}

    return trades


def summarize(trades, label):
    if not trades:
        return f"{label:<22} no trades"
    r = [t["ret"] for t in trades]
    wins = [x for x in r if x > 0]
    gw = sum(wins)
    gl = abs(sum(x for x in r if x <= 0))
    reasons = defaultdict(int)
    for t in trades:
        reasons[t["reason"]] += 1
    rs = " ".join(f"{k}:{v}" for k, v in sorted(reasons.items()))
    return (f"{label:<22} {len(r):>4} trades  win {len(wins)/len(r)*100:>5.1f}%  "
            f"avg {sum(r)/len(r):>+6.3f}%  total {sum(r):>+8.2f}%  "
            f"PF {gw/gl if gl else float('inf'):>5.2f}   [{rs}]")


def main():
    all_5m = load_5m()
    if not all_5m:
        print("No 5-minute data found.")
        return
    days = sorted({b["date"] for s in all_5m for b in all_5m[s]})
    print(f"{len(all_5m)} symbols | {len(days)} sessions "
          f"({days[0]} .. {days[-1]}) | "
          f"{sum(len(v) for v in all_5m.values()):,} 5m bars\n")
    print(f"VOLUME_CONFIRMATION_RATIO from live code: "
          f"{eva.VOLUME_CONFIRMATION_RATIO}\n")

    arms = [("zone only (no filter)", "zone"),
            ("+ bullish candle", "bullish"),
            ("+ bullish + volume", "bullish_vol")]
    results = {}
    for label, mode in arms:
        t = run_arm(all_5m, mode)
        results[mode] = t
        print(summarize(t, label))

    z, b = results["zone"], results["bullish"]
    if z and b:
        print(f"\nConfirmation filter removed "
              f"{len(z) - len(b)} of {len(z)} trades "
              f"({(len(z)-len(b))/len(z)*100:.0f}%)")
        wz = sum(1 for t in z if t["ret"] > 0) / len(z) * 100
        wb = sum(1 for t in b if t["ret"] > 0) / len(b) * 100
        print(f"win rate {wz:.1f}% -> {wb:.1f}%   "
              f"({wb-wz:+.1f} points)")
        az = sum(t["ret"] for t in z) / len(z)
        ab = sum(t["ret"] for t in b) / len(b)
        print(f"expectancy {az:+.3f}% -> {ab:+.3f}% per trade "
              f"({ab-az:+.3f})")


if __name__ == "__main__":
    main()
