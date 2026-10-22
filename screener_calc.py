#!/usr/bin/env python3
"""
Real screener math, callable from the command line -- built for the
migrated eva-nightly-screener (2026-08-28) so that invocation NEVER
re-derives the backtest walk itself. It calls this, which imports the
exact same functions symbol_screener.py has always used
(zone_width_ok, levels_for_day, backtest_symbol). One source of truth
for the backtest, not a parallel copy an LLM free-hands step-by-step --
the sequential day-by-day position-tracking walk is exactly the kind of
thing arithmetic drift ruins silently.

symbol_screener.py is safe to import: its httpx/mcp imports are deferred
into main() (2026-08-28 fix), so importing this module needs no venv and
makes no network call.

Data (daily_bars, fivemin_bars) is fetched by the caller via its own live
Robinhood MCP connection -- this script only ever computes on bars handed
to it. blackout_days is a list of "YYYY-MM-DD" strings (real earnings
dates +/- EARNINGS_BLACKOUT_DAYS, from get_earnings_results).

Usage:
    python3 screener_calc.py constants '{}'
    python3 screener_calc.py backtest '{"daily_bars": [...], "fivemin_bars": [...], "blackout_days": ["2026-08-15"]}'

daily_bars: raw bars from get_equity_historicals (interval=day) for ONE
symbol -- each needs begins_at, high_price, low_price (as returned by the
tool, strings are fine).
fivemin_bars: raw bars from get_equity_historicals (interval=5minute) for
the SAME symbol -- each needs begins_at, open_price, close_price,
high_price, low_price.

Prints one line of JSON: {"ok": true, "result": {...}} or
{"ok": false, "error": "..."}. On success, result is
{"trades": <n>, "wins": <n>, "pnl": <float>, "winrate": <float 0-100>}.
"""
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")
import symbol_screener as ss  # noqa: E402  (path insert must come first)


def _parse_utc(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _prep_daily(raw_bars):
    out = []
    for b in raw_bars:
        if b.get("interpolated"):
            continue
        nb = dict(b)
        nb["_date"] = _parse_utc(b["begins_at"]).date()
        out.append(nb)
    return out


def _prep_fivemin(raw_bars):
    out = []
    for b in raw_bars:
        if b.get("interpolated"):
            continue
        nb = dict(b)
        utc = _parse_utc(b["begins_at"])
        nb["_et"] = utc.astimezone(ss.ET)
        nb["open"] = float(b["open_price"])
        nb["close"] = float(b["close_price"])
        nb["high"] = float(b["high_price"])
        nb["low"] = float(b["low_price"])
        out.append(nb)
    return out


def backtest(args):
    daily_bars = _prep_daily(args["daily_bars"])
    fivemin_bars = _prep_fivemin(args["fivemin_bars"])
    blackout_days = {
        datetime.strptime(d, "%Y-%m-%d").date() for d in args.get("blackout_days", [])
    }
    trades = ss.backtest_symbol(daily_bars, fivemin_bars, blackout_days)
    n = len(trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    pnl = sum(t["pnl"] for t in trades)
    wr = wins / n * 100 if n else 0
    return {"trades": n, "wins": wins, "pnl": pnl, "winrate": wr}


def constants(_args):
    return {
        "CANDIDATE_UNIVERSE": ss.CANDIDATE_UNIVERSE,
        "SEMI_CORRELATED": sorted(ss.SEMI_CORRELATED),
        "HIGH_VOL_PROXY": sorted(ss.HIGH_VOL_PROXY),
        "MIN_PRICE": ss.MIN_PRICE,
        "MAX_PRICE": ss.MAX_PRICE,
        "EARNINGS_BLACKOUT_DAYS": ss.EARNINGS_BLACKOUT_DAYS,
        "SWING_LOOKBACK_DAYS": ss.SWING_LOOKBACK_DAYS,
        "MIN_ZONE_WIDTH_PCT": ss.MIN_ZONE_WIDTH_PCT,
        "PASS_MIN_TRADES": 15,  # same gate main() uses: pnl > 0 and trades >= 15
    }


FUNCS = {"backtest": backtest, "constants": constants}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in FUNCS:
        print(json.dumps({"ok": False, "error": f"usage: screener_calc.py <{'|'.join(FUNCS)}> '<json args>'"}))
        sys.exit(1)
    name, raw_args = sys.argv[1], sys.argv[2]
    try:
        args = json.loads(raw_args)
        result = FUNCS[name](args)
        print(json.dumps({"ok": True, "result": result}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
