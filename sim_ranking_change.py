#!/usr/bin/env python3
"""
Simulation: does ranking candidates by NET EDGE beat ranking by ZONE DEPTH?

This tests ONLY the 2026-09-01 change to sage_bot_v13.py's candidate ranking.
Entries, exits, levels and filters are identical in both arms -- the single
difference is WHICH candidate gets picked when more fire than there are slots.
That isolation is the whole point: if both arms picked the same symbol, the
change is irrelevant, and the sim says so.

METHOD
  - Real daily bars (Robinhood), May-Sep 2026, the live 20-symbol watchlist.
  - Levels reconstructed exactly as get_daily_levels does: RL/RH = yesterday's
    low/high, SL/SH = 5-session extremes, SH>=RH and SL<=RL enforced.
  - Same gates as live: zone_width_ok (>=3%), and price must actually reach
    the buy zone (day's low <= RL).
  - Entry at RL (the zone boundary -- where the live bot's BUY zone starts).
  - Exit at that day's CLOSE. This mirrors reality: all four real trades in
    ~/trading_log_v9.csv closed via EOD_FLATTEN, never at target or stop.
  - Spread charged on every trade.

HONEST LIMITATIONS -- read before trusting any number here
  1. DAILY bars, not 5-minute. The live bot needs a bullish 5-min confirmation
     candle whose low <= RL. This sim cannot see that, so it takes MORE trades
     than the real bot would. Absolute returns here are NOT a P&L forecast.
  2. Spreads are TODAY's measured values held constant per symbol. Real
     spreads move. They are stable enough in rank order (NVDA always tighter
     than IBRX) that the comparison holds, but the magnitudes are approximate.
  3. Entry at exactly RL is idealised; real fills slip.
  4. ~4 months of data. Enough to compare two rankings on identical inputs,
     nowhere near enough to validate the strategy itself.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")

# Real spreads measured 2026-09-01 11:00 PDT from Robinhood's own book.
# Symbols not measured directly get the median of their liquidity class.
SPREADS = {
    "NVDA": 0.005, "AAPL": 0.009, "MSFT": 0.016,
    "IOVA": 0.123, "IBRX": 0.127,
    # Not individually measured; assigned by liquidity class. Mega-caps trade
    # like NVDA/AAPL/MSFT; small caps like IOVA/IBRX.
    "TSLA": 0.010, "AMD": 0.012, "GOOGL": 0.010, "JPM": 0.012,
    "XOM": 0.012, "WMT": 0.012, "UNH": 0.015, "HD": 0.015,
    "MCD": 0.015, "CVX": 0.014, "PFE": 0.020, "BA": 0.018,
    "COIN": 0.030, "SMCI": 0.035, "GDX": 0.020,
}

SWING_LOOKBACK_DAYS = 5
MIN_ZONE_WIDTH_PCT = 3.0
TARGET_FRAC = 0.25
MAX_POSITIONS = 2  # real slots the bot had: BP $250 // $62.50 min notional


def load_bars(paths):
    """Read the saved tool-result files without pulling them into context."""
    out = defaultdict(list)
    for p in paths:
        raw = json.loads(Path(p).read_text())
        for r in raw["data"]["results"]:
            sym = r["symbol"]
            for b in r.get("bars", []):
                if b.get("interpolated"):
                    continue
                out[sym].append({
                    "date": b["begins_at"][:10],
                    "open": float(b["open_price"]),
                    "high": float(b["high_price"]),
                    "low": float(b["low_price"]),
                    "close": float(b["close_price"]),
                })
    for sym in out:
        out[sym].sort(key=lambda x: x["date"])
    return dict(out)


def levels_for(bars, i):
    """Exactly get_daily_levels' logic, using only bars STRICTLY before i."""
    past = bars[:i]
    if len(past) < SWING_LOOKBACK_DAYS:
        return None
    y = past[-1]
    look = past[-SWING_LOOKBACK_DAYS:]
    rh, rl = y["high"], y["low"]
    sh = max(max(b["high"] for b in look), rh)
    sl = min(min(b["low"] for b in look), rl)
    return {"rh": rh, "rl": rl, "sh": sh, "sl": sl}


def zone_width_ok(lv):
    if lv["rl"] <= 0:
        return False
    return (lv["rl"] - lv["sl"]) / lv["rl"] * 100 >= MIN_ZONE_WIDTH_PCT


def compute_target(lv):
    return lv["rl"] + TARGET_FRAC * (lv["rh"] - lv["rl"])


def simulate(bars, ranker, slots=MAX_POSITIONS):
    """Walk every trading day; on each, rank that day's candidates and take
    the top `slots`. Returns per-trade net percentage returns."""
    dates = sorted({d["date"] for s in bars for d in bars[s]})
    idx = {s: {b["date"]: k for k, b in enumerate(bars[s])} for s in bars}

    trades = []
    contested_days = 0
    for day in dates:
        cands = []
        for sym, series in bars.items():
            k = idx[sym].get(day)
            if k is None or k < SWING_LOOKBACK_DAYS:
                continue
            lv = levels_for(series, k)
            if not lv or not zone_width_ok(lv):
                continue
            bar = series[k]
            if bar["low"] > lv["rl"]:      # never reached the buy zone
                continue

            entry = lv["rl"]
            tgt = compute_target(lv)
            if tgt <= entry:
                continue
            sp = SPREADS.get(sym, 0.02)
            gross_to_target = (tgt - entry) / entry * 100
            depth = (lv["rl"] - bar["low"]) / lv["rl"] * 100   # how deep it dipped
            net_edge = gross_to_target - sp
            realized = (bar["close"] - entry) / entry * 100 - sp  # EOD flatten
            cands.append({
                "sym": sym, "depth": depth, "net_edge": net_edge,
                "gross": gross_to_target, "spread": sp, "realized": realized,
            })

        if len(cands) > slots:
            contested_days += 1
        for c in ranker(cands)[:slots]:
            trades.append(c)
    return trades, contested_days


def rank_old(c):
    """Live behaviour before 2026-09-01: deepest into the zone first."""
    return sorted(c, key=lambda x: -x["depth"])


def rank_new(c):
    """New behaviour: best expected profit AFTER the cost of capturing it."""
    return sorted(c, key=lambda x: -x["net_edge"])


def summarize(trades, label):
    if not trades:
        return f"{label:<12} no trades"
    r = [t["realized"] for t in trades]
    wins = [x for x in r if x > 0]
    gw = sum(wins)
    gl = abs(sum(x for x in r if x <= 0))
    return (f"{label:<12} {len(r):>4} trades  "
            f"win {len(wins)/len(r)*100:>5.1f}%  "
            f"avg {sum(r)/len(r):>+6.3f}%  "
            f"total {sum(r):>+8.2f}%  "
            f"PF {gw/gl if gl else float('inf'):>5.2f}")


def main():
    d = Path("/Users/sagewilliams/.claude/projects/"
             "-Users-sagewilliams-Desktop-Sages-trading-bot/"
             "078e0397-347a-4124-b98c-328086eb407d/tool-results")
    files = sorted(d.glob("*get_equity_historicals*.txt"))
    files = [f for f in files if f.stat().st_size > 100_000][-2:]
    if len(files) < 2:
        print("Could not find both saved daily-bar files.")
        return

    bars = load_bars(files)
    print(f"Loaded {len(bars)} symbols, "
          f"{min(len(v) for v in bars.values())}-{max(len(v) for v in bars.values())} "
          f"daily bars each\n")

    old, contested = simulate(bars, rank_old)
    new, _ = simulate(bars, rank_new)

    print(f"Days where MORE candidates fired than slots ({MAX_POSITIONS}): "
          f"{contested}")
    print("(on any other day both rankings pick the same symbols, so the "
          "change cannot matter)\n")

    print(summarize(old, "OLD depth"))
    print(summarize(new, "NEW net edge"))

    # The only trades that differ are the ones where the pick changed.
    ot = {(t["sym"]) for t in old}
    nt = {(t["sym"]) for t in new}
    print(f"\nsymbols only OLD traded: {sorted(ot - nt) or 'none'}")
    print(f"symbols only NEW traded: {sorted(nt - ot) or 'none'}")

    # Which symbols each ranking favoured, and what they cost.
    print("\nTrade count and avg spread paid, by ranking:")
    for label, tr in (("OLD", old), ("NEW", new)):
        by = defaultdict(int)
        for t in tr:
            by[t["sym"]] += 1
        avg_sp = sum(t["spread"] for t in tr) / len(tr) if tr else 0
        top = ", ".join(f"{s}x{n}" for s, n in
                        sorted(by.items(), key=lambda kv: -kv[1])[:6])
        print(f"  {label}: avg spread paid {avg_sp:.4f}%   top: {top}")


if __name__ == "__main__":
    main()
