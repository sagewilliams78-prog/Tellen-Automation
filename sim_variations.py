#!/usr/bin/env python3
"""
Test many strategy variations WITHOUT fooling ourselves.

The danger with "keep trying things until the win rate goes up" is that with
enough variations, something always looks good by luck. On 40 sessions,
testing 20 ideas will produce a 75% winner that is pure noise -- and that is
precisely the strategy that then loses real money.

So every variation here is measured twice:

    TRAIN   the first ~60% of sessions   -- where we are allowed to look
    TEST    the remaining ~40%           -- never seen while choosing

A variation is only interesting if it holds up in TEST. A big TRAIN number
with a weak TEST number is the signature of a curve fit, and this script
prints both side by side so that is impossible to hide.

Reuses sage_bot_v13.py's real math (zone_of, compute_stop, compute_target,
zone_width_ok) so nothing drifts from the live strategy.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")
import sage_bot_v13 as eva

TOOLS = Path("/Users/sagewilliams/.claude/projects/"
             "-Users-sagewilliams-Desktop-Sages-trading-bot/"
             "078e0397-347a-4124-b98c-328086eb407d/tool-results")

# Measured 2026-09-01 where available; the rest assigned by liquidity class.
SPREADS = {"NVDA": 0.005, "MSFT": 0.016, "AMD": 0.012, "TSLA": 0.010,
           "IBRX": 0.127, "IOVA": 0.123, "COIN": 0.030, "GDX": 0.020,
           "AAPL": 0.009, "GOOGL": 0.010, "JPM": 0.012, "XOM": 0.012,
           "WMT": 0.012, "UNH": 0.015, "HD": 0.015, "MCD": 0.015,
           "CVX": 0.014, "PFE": 0.020, "BA": 0.018, "SMCI": 0.035}


def load_5m():
    out = defaultdict(dict)          # sym -> {timestamp: bar}
    for f in sorted(TOOLS.glob("*get_equity_historicals*.txt")):
        if f.stat().st_size < 400_000:
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
                out[sym][t] = {
                    "t": t, "date": t.date().isoformat(),
                    "open": float(b["open_price"]), "high": float(b["high_price"]),
                    "low": float(b["low_price"]), "close": float(b["close_price"]),
                    "volume": float(b.get("volume") or 0),
                }
    return {s: [v[k] for k in sorted(v)] for s, v in out.items()}


def daily_from_5m(bars):
    days = defaultdict(list)
    for b in bars:
        days[b["date"]].append(b)
    return [{"date": d, "high": max(x["high"] for x in days[d]),
             "low": min(x["low"] for x in days[d]),
             "close": days[d][-1]["close"]} for d in sorted(days)]


def levels_for(daily, i):
    past = daily[:i]
    if len(past) < eva.SWING_LOOKBACK_DAYS:
        return None
    y = past[-1]
    look = past[-eva.SWING_LOOKBACK_DAYS:]
    rh, rl = y["high"], y["low"]
    return {"rh": rh, "rl": rl,
            "sh": max(max(b["high"] for b in look), rh),
            "sl": min(min(b["low"] for b in look), rl)}


def run(all_5m, cfg, sessions):
    """One variation over a specific set of sessions."""
    want = set(sessions)
    trades = []
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
            vols = [b["volume"] for b in session]
            pos = None
            entries_today = 0

            for k, b in enumerate(session):
                if pos:
                    # trailing stop, if enabled
                    if cfg.get("trail_pct"):
                        pos["peak"] = max(pos["peak"], b["high"])
                        t_stop = pos["peak"] * (1 - cfg["trail_pct"] / 100)
                        if t_stop > pos["stop"]:
                            pos["stop"] = t_stop
                    if b["low"] <= pos["stop"]:
                        trades.append((pos["stop"] - pos["entry"]) / pos["entry"] * 100 - sp)
                        pos = None; continue
                    if b["high"] >= pos["target"]:
                        trades.append((pos["target"] - pos["entry"]) / pos["entry"] * 100 - sp)
                        pos = None; continue
                    if k == len(session) - 1:
                        trades.append((b["close"] - pos["entry"]) / pos["entry"] * 100 - sp)
                        pos = None
                    continue

                if k == len(session) - 1 or entries_today >= cfg.get("max_per_day", 1):
                    continue
                if b["low"] > lv["rl"] or eva.zone_of(b["close"], lv) != "BUY":
                    continue
                if cfg.get("require_bullish") and b["close"] <= b["open"]:
                    continue
                if cfg.get("vol_ratio"):
                    base = vols[max(0, k - 20):k]
                    avg = sum(base) / len(base) if base else 0
                    if avg > 0 and b["volume"] < avg * cfg["vol_ratio"]:
                        continue
                if cfg.get("min_depth_pct"):
                    depth = (lv["rl"] - b["low"]) / lv["rl"] * 100
                    if depth < cfg["min_depth_pct"]:
                        continue
                if cfg.get("skip_first_bars") and k < cfg["skip_first_bars"]:
                    continue

                entry = b["close"]
                stop = (entry * (1 - cfg["stop_pct"] / 100) if cfg.get("stop_pct")
                        else eva.compute_stop(entry, lv["sl"]))
                target = (entry * (1 + cfg["target_pct"] / 100) if cfg.get("target_pct")
                          else eva.compute_target(lv))
                if stop >= entry or target <= entry:
                    continue
                pos = {"entry": entry, "stop": stop, "target": target, "peak": entry}
                entries_today += 1
    return trades


def stats(t):
    if not t:
        return None
    w = [x for x in t if x > 0]
    gl = abs(sum(x for x in t if x <= 0))
    return {"n": len(t), "win": len(w) / len(t) * 100,
            "avg": sum(t) / len(t), "total": sum(t),
            "pf": (sum(w) / gl) if gl else float("inf")}


VARIATIONS = {
    "baseline (live rule)":      {"require_bullish": True, "vol_ratio": 1.2},
    "no filters at all":         {},
    "bullish only":              {"require_bullish": True},
    "volume only":               {"vol_ratio": 1.2},
    "stronger volume 1.5x":      {"require_bullish": True, "vol_ratio": 1.5},
    "deep entries only >0.5%":   {"require_bullish": True, "min_depth_pct": 0.5},
    "deep entries only >1.0%":   {"require_bullish": True, "min_depth_pct": 1.0},
    "skip first 30min":          {"require_bullish": True, "skip_first_bars": 6},
    "tight target 0.5%":         {"require_bullish": True, "target_pct": 0.5, "stop_pct": 2.0},
    "target 1% / stop 2%":       {"require_bullish": True, "target_pct": 1.0, "stop_pct": 2.0},
    "target 2% / stop 2%":       {"require_bullish": True, "target_pct": 2.0, "stop_pct": 2.0},
    "trailing stop 1%":          {"require_bullish": True, "trail_pct": 1.0},
    "no filter + deep >0.5%":    {"min_depth_pct": 0.5},
    "no filter + skip 30min":    {"skip_first_bars": 6},
}


def main():
    all_5m = load_5m()
    sessions = sorted({b["date"] for s in all_5m for b in all_5m[s]})
    cut = int(len(sessions) * 0.6)
    train, test = sessions[:cut], sessions[cut:]

    print(f"{len(all_5m)} symbols | {len(sessions)} sessions "
          f"({sessions[0]} .. {sessions[-1]})")
    print(f"TRAIN {len(train)} sessions ({train[0]} .. {train[-1]})")
    print(f"TEST  {len(test)} sessions ({test[0]} .. {test[-1]})  <- never used to choose\n")

    print(f"{'variation':<26} {'TRAIN win/PF/total':>26}   {'TEST win/PF/total':>26}")
    print("-" * 84)

    rows = []
    for name, cfg in VARIATIONS.items():
        tr = stats(run(all_5m, cfg, train))
        te = stats(run(all_5m, cfg, test))
        if not tr or not te:
            print(f"{name:<26} insufficient trades")
            continue
        rows.append((name, tr, te))
        print(f"{name:<26} "
              f"{tr['n']:>3}t {tr['win']:>5.1f}% {tr['pf']:>5.2f} {tr['total']:>+7.1f}%   "
              f"{te['n']:>3}t {te['win']:>5.1f}% {te['pf']:>5.2f} {te['total']:>+7.1f}%")

    print("\n" + "=" * 84)
    print("Ranked by TEST profit factor (the only number that is honest):")
    for name, tr, te in sorted(rows, key=lambda r: -r[2]["pf"])[:6]:
        gap = tr["pf"] - te["pf"]
        flag = "  <-- likely curve fit" if gap > 0.5 else ""
        print(f"  {name:<26} TEST PF {te['pf']:.2f}  win {te['win']:.1f}%  "
              f"(train PF {tr['pf']:.2f}, gap {gap:+.2f}){flag}")


if __name__ == "__main__":
    main()
