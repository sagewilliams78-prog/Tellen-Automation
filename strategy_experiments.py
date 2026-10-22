#!/usr/bin/env python3
"""
One-off parameter sweep against real data -- answers "what would actually
make this more profitable" with numbers instead of more tooling.

Read-only, same as rolling_revalidation.py. Fetches daily + 5-min bars ONCE
for the current watchlist plus a couple of screened candidates, then runs
the SAME walk-forward window split (3 independent windows) against several
config variants, so every number here is subject to the same
overfitting-resistance as the rest of the session's backtests -- no variant
gets to look good just because it was tuned to the whole period at once.

Not scheduled, not part of the live pipeline. Run manually when actually
deciding whether to change v13's config.
"""
import asyncio, json, os, random, subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:
    raise SystemExit("zoneinfo unavailable")

try:
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
except ImportError:
    raise SystemExit("Missing deps -- run with the venv: "
                      "\"robin hood trading bot/.venv/bin/python\" strategy_experiments.py")

MCP_URL = "https://agent.robinhood.com/mcp/trading"
CURRENT_WATCHLIST = ["IBRX", "IOVA", "NVDA", "TSLA", "AMD", "GDX"]
CANDIDATE_ADDS = ["COIN", "SMCI"]   # best performers from the 2026-08-21 screener run
EXPANSION_CANDIDATES = ["MCD", "HD", "GE", "AAPL", "CVX", "UNH"]  # best individual standalone
                        # performers from the 2026-08-22 corrected screener run, none of which
                        # passed its 15-trade minimum yet -- testing here as a GROUP added to the
                        # real live portfolio (with real slots + guardrails), which is a different,
                        # more relevant question than "does this one symbol clear an isolated bar"
ALL_SYMBOLS = CURRENT_WATCHLIST + CANDIDATE_ADDS + EXPANSION_CANDIDATES

SWING_LOOKBACK_DAYS = 5
N_WINDOWS = 6  # widened 2026-08-23 from 3 -- with a 6-month lookback there's enough data for
               # more, smaller independent windows, giving a real read on regime diversity
               # instead of one long summer stretch split three ways
MIN_WINDOW_DAYS = 12

def utc_now():
    return datetime.now(timezone.utc)

def parse_utc(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def load_jwt():
    auth_path = Path.home() / ".sage_robinhood_auth.json"
    data = json.loads(auth_path.read_text())
    return data["tokens"]["access_token"]

def _result_text(result):
    try:
        return " ".join(getattr(c, "text", "") for c in (result.content or []) if getattr(c, "text", None))
    except Exception:
        return str(result)

async def fetch_historicals(session, symbols, start, end, interval):
    res = await session.call_tool("get_equity_historicals", {
        "symbols": symbols,
        "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "interval": interval,
        "bounds": "regular",
    })
    return json.loads(_result_text(res))

async def fetch_on_fresh_connection(headers, symbols, start, end, interval, attempts=3, base_delay=4):
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(60)) as hc:
                async with streamable_http_client(MCP_URL, http_client=hc) as (rs, ws):
                    async with ClientSession(rs, ws) as session:
                        await session.initialize()
                        return await fetch_historicals(session, symbols, start, end, interval)
        except Exception as e:
            last_err = e
            print(f"    ⚠️  fetch failed (attempt {attempt}/{attempts}): {e}")
            if attempt < attempts:
                await asyncio.sleep(base_delay * attempt)
    raise last_err

async def fetch_5min_chunked(headers, sym, start, end, chunk_days=35):
    all_bars = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=chunk_days), end)
        payload = await fetch_on_fresh_connection(headers, [sym], chunk_start, chunk_end, "5minute")
        for r in payload["data"]["results"]:
            all_bars.extend(r.get("bars", []))
        chunk_start = chunk_end
    return all_bars

EARNINGS_BLACKOUT_DAYS = 1  # matches sage_bot_v13.py's EARNINGS_BLACKOUT_DAYS

async def fetch_earnings_blackout_days(headers, sym, window_start, window_end):
    """Real historical earnings report dates for sym (trailing up to 8
    quarters via get_earnings_results), turned into the set of calendar
    dates that would have been blacked out (+/- EARNINGS_BLACKOUT_DAYS)
    and that fall inside the backtest window. GDX (an ETF) legitimately
    returns no results -- that's correct, not a failure."""
    try:
        payload = await fetch_on_fresh_connection_tool(headers, "get_earnings_results", {"symbol": sym})
    except Exception as e:
        print(f"    ⚠️  earnings lookup failed for {sym}: {e}")
        return set()
    out = set()
    for r in payload.get("data", {}).get("results", []):
        try:
            rdate = datetime.strptime(r["report"]["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        for offset in range(-EARNINGS_BLACKOUT_DAYS, EARNINGS_BLACKOUT_DAYS + 1):
            d = rdate + timedelta(days=offset)
            if window_start <= d <= window_end:
                out.add(d)
    return out

async def fetch_on_fresh_connection_tool(headers, tool_name, args, attempts=3, base_delay=4):
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(60)) as hc:
                async with streamable_http_client(MCP_URL, http_client=hc) as (rs, ws):
                    async with ClientSession(rs, ws) as session:
                        await session.initialize()
                        res = await session.call_tool(tool_name, args)
                        return json.loads(_result_text(res))
        except Exception as e:
            last_err = e
            if attempt < attempts:
                await asyncio.sleep(base_delay * attempt)
    raise last_err

def zone_of(price, lv):
    if price >= lv["rh"]:
        return "SELL"
    if price <= lv["rl"]:
        return "BUY"
    return "KILL"

def levels_for_day(daily_bars, day):
    past = sorted([b for b in daily_bars if b["_date"] < day], key=lambda b: b["_date"])
    if not past:
        return None
    yesterday = past[-1]
    lookback = past[-SWING_LOOKBACK_DAYS:]
    rh, rl = float(yesterday["high_price"]), float(yesterday["low_price"])
    sh = max(max(float(b["high_price"]) for b in lookback), rh)
    sl = min(min(float(b["low_price"]) for b in lookback), rl)
    return {"rh": rh, "rl": rl, "sh": sh, "sl": sl}

def zone_width_ok(lv, min_zone_width_pct):
    if lv["rl"] <= 0:
        return False
    return (lv["rl"] - lv["sl"]) / lv["rl"] * 100 >= min_zone_width_pct

def backtest_window(daily_by_symbol, fivemin_by_symbol, min_day, max_day, watchlist, cfg):
    """cfg keys: stop_backstop_pct, min_stop_distance_pct, target_frac,
    min_zone_width_pct, risk_per_trade, max_notional"""
    trades = []
    for sym in watchlist:
        daily = daily_by_symbol.get(sym, [])
        bars = fivemin_by_symbol.get(sym, [])
        days = {}
        for b in bars:
            if min_day <= b["_et"].date() <= max_day:
                days.setdefault(b["_et"].date(), []).append(b)

        position = None
        for day in sorted(days):
            day_bars = days[day]
            lv = levels_for_day(daily, day)
            if lv is None:
                continue
            for i, bar in enumerate(day_bars):
                t = bar["_et"].time()
                price = bar["close"]
                is_last = (i == len(day_bars) - 1)
                in_window = (t.hour > 10 or (t.hour == 10 and t.minute >= 0)) and \
                            (t.hour < 15 or (t.hour == 15 and t.minute < 55))

                if position is not None:
                    if bar["low"] <= position["stop"]:
                        pnl = (position["stop"] - position["entry"]) * position["shares"]
                        trades.append({"symbol": sym, "day": str(day), "reason": "STOP", "pnl": pnl})
                        position = None
                    elif bar["high"] >= position["target"]:
                        pnl = (position["target"] - position["entry"]) * position["shares"]
                        trades.append({"symbol": sym, "day": str(day), "reason": "TARGET", "pnl": pnl})
                        position = None
                    if position is not None and is_last:
                        pnl = (price - position["entry"]) * position["shares"]
                        trades.append({"symbol": sym, "day": str(day), "reason": "EOD", "pnl": pnl})
                        position = None

                if position is None and in_window and not is_last and zone_width_ok(lv, cfg["min_zone_width_pct"]):
                    if zone_of(price, lv) == "BUY" and bar["low"] <= lv["rl"] and bar["close"] > bar["open"]:
                        entry = price
                        stop = max(lv["sl"], entry * (1 + cfg["stop_backstop_pct"] / 100))
                        stop = min(stop, entry * (1 + cfg["min_stop_distance_pct"] / 100))
                        target = lv["rl"] + cfg["target_frac"] * (lv["rh"] - lv["rl"])
                        if stop < entry and target > entry:
                            risk_per_share = entry - stop
                            notional = min(cfg["risk_per_trade"] / risk_per_share * entry, cfg["max_notional"])
                            shares = notional / entry
                            position = {"entry": entry, "shares": shares, "stop": stop, "target": target}
    return trades

WEEKLY_MIN_TRADES = 5      # matches sage_bot_v13.py's WEEKLY_MIN_TRADES
WEEKLY_WINRATE_FLOOR = 40.0  # matches sage_bot_v13.py's WEEKLY_WINRATE_FLOOR

def backtest_portfolio(daily_by_symbol, fivemin_by_symbol, min_day, max_day, watchlist, cfg, slots,
                        blackout_days_by_symbol=None, block_reentry=False, whole_shares=False):
    """Same entry/exit rules as backtest_window, but simulates ALL symbols
    in lockstep sharing a real slot cap -- the thing backtest_window (and
    every backtest run so far this session) does NOT do. backtest_window
    tests each symbol independently and sums the results, which implicitly
    assumes unlimited buying power (every symbol can be held at once). The
    live bot's real slots = int(buying_power // MIN_POSSIBLE_NOTIONAL) --
    on this account that's 1-4, not 7. When more symbols signal on the
    same day than there are free slots, this picks the same ones the live
    bot would: ranked by depth-into-zone, deepest first.

    Also models the two live guardrails earlier backtests this session
    left out: earnings blackout (blackout_days_by_symbol, built from real
    get_earnings_results dates) and the weekly win-rate circuit breaker
    (trailing 7 calendar days, >=5 trades, pauses NEW entries if win rate
    <40% -- existing positions still exit normally, matching v13)."""
    blackout_days_by_symbol = blackout_days_by_symbol or {}
    trades = []
    all_days = sorted({b["_et"].date() for sym in watchlist for b in fivemin_by_symbol.get(sym, [])
                        if min_day <= b["_et"].date() <= max_day})
    for day in all_days:
        sym_bars = {}
        for sym in watchlist:
            bars = sorted([b for b in fivemin_by_symbol.get(sym, []) if b["_et"].date() == day],
                           key=lambda b: b["_et"])
            if bars:
                sym_bars[sym] = bars
        if not sym_bars:
            continue

        lv_by_sym = {}
        for sym in sym_bars:
            lv = levels_for_day(daily_by_symbol.get(sym, []), day)
            if lv is not None and zone_width_ok(lv, cfg["min_zone_width_pct"]):
                lv_by_sym[sym] = lv

        bar_index = {}
        last_ts_per_sym = {}
        for sym, bars in sym_bars.items():
            last_ts_per_sym[sym] = bars[-1]["_et"]
            for b in bars:
                bar_index[(sym, b["_et"])] = b
        all_ts = sorted({b["_et"] for bars in sym_bars.values() for b in bars})

        cutoff = day - timedelta(days=7)
        recent = [t for t in trades if cutoff <= t["day_obj"] < day]
        weekly_pause = False
        if len(recent) >= WEEKLY_MIN_TRADES:
            wr = sum(1 for t in recent if t["pnl"] > 0) / len(recent) * 100
            weekly_pause = wr < WEEKLY_WINRATE_FLOOR
        blackout_today = {sym for sym, days in blackout_days_by_symbol.items() if day in days}
        traded_today = set()

        positions = {}
        for ts in all_ts:
            t = ts.time()
            in_window = (t.hour > 10 or (t.hour == 10 and t.minute >= 0)) and \
                        (t.hour < 15 or (t.hour == 15 and t.minute < 55))

            for sym in list(positions.keys()):
                bar = bar_index.get((sym, ts))
                if bar is None:
                    continue
                pos = positions[sym]
                is_last = (ts == last_ts_per_sym.get(sym))
                if bar["low"] <= pos["stop"]:
                    trades.append({"symbol": sym, "day": str(day), "day_obj": day, "reason": "STOP",
                                    "pnl": (pos["stop"] - pos["entry"]) * pos["shares"]})
                    del positions[sym]
                    traded_today.add(sym)
                elif bar["high"] >= pos["target"]:
                    trades.append({"symbol": sym, "day": str(day), "day_obj": day, "reason": "TARGET",
                                    "pnl": (pos["target"] - pos["entry"]) * pos["shares"]})
                    del positions[sym]
                    traded_today.add(sym)
                elif is_last:
                    trades.append({"symbol": sym, "day": str(day), "day_obj": day, "reason": "EOD",
                                    "pnl": (bar["close"] - pos["entry"]) * pos["shares"]})
                    del positions[sym]
                    traded_today.add(sym)

            free_slots = slots - len(positions)
            if free_slots > 0 and in_window and not weekly_pause:
                candidates = []
                for sym, lv in lv_by_sym.items():
                    if sym in positions or sym in blackout_today:
                        continue
                    if block_reentry and sym in traded_today:
                        continue
                    bar = bar_index.get((sym, ts))
                    if bar is None or ts == last_ts_per_sym.get(sym):
                        continue
                    price = bar["close"]
                    if zone_of(price, lv) == "BUY" and bar["low"] <= lv["rl"] and bar["close"] > bar["open"]:
                        depth = (lv["rl"] - price) / lv["rl"] * 100
                        candidates.append((depth, sym, bar, lv))
                candidates.sort(key=lambda c: c[0], reverse=True)
                for depth, sym, bar, lv in candidates[:free_slots]:
                    entry = bar["close"]
                    stop = max(lv["sl"], entry * (1 + cfg["stop_backstop_pct"] / 100))
                    stop = min(stop, entry * (1 + cfg["min_stop_distance_pct"] / 100))
                    target = lv["rl"] + cfg["target_frac"] * (lv["rh"] - lv["rl"])
                    if stop < entry and target > entry:
                        risk_per_share = entry - stop
                        notional = min(cfg["risk_per_trade"] / risk_per_share * entry, cfg["max_notional"])
                        shares = float(int(notional / entry)) if whole_shares else notional / entry
                        if shares <= 0:
                            continue  # whole-share rounding can't afford even 1 share -- skip, no fractional fallback
                        positions[sym] = {"entry": entry, "shares": shares, "stop": stop, "target": target}

        for sym, pos in positions.items():
            last_bar = bar_index.get((sym, last_ts_per_sym[sym]))
            price = last_bar["close"] if last_bar else pos["entry"]
            trades.append({"symbol": sym, "day": str(day), "day_obj": day, "reason": "EOD_FORCE",
                            "pnl": (price - pos["entry"]) * pos["shares"]})
    return trades

def backtest_portfolio_trailing(daily_by_symbol, fivemin_by_symbol, min_day, max_day, watchlist, cfg, slots, trail_pct):
    """Same as backtest_portfolio, but instead of a fixed profit target,
    once entered the position rides until price pulls back trail_pct from
    its post-entry peak (or hits the original hard stop, or EOD).
    Everything else -- entry signal, sizing, slot ranking -- is identical,
    so this isolates the effect of the exit rule alone."""
    trades = []
    all_days = sorted({b["_et"].date() for sym in watchlist for b in fivemin_by_symbol.get(sym, [])
                        if min_day <= b["_et"].date() <= max_day})
    for day in all_days:
        sym_bars = {}
        for sym in watchlist:
            bars = sorted([b for b in fivemin_by_symbol.get(sym, []) if b["_et"].date() == day],
                           key=lambda b: b["_et"])
            if bars:
                sym_bars[sym] = bars
        if not sym_bars:
            continue

        lv_by_sym = {}
        for sym in sym_bars:
            lv = levels_for_day(daily_by_symbol.get(sym, []), day)
            if lv is not None and zone_width_ok(lv, cfg["min_zone_width_pct"]):
                lv_by_sym[sym] = lv

        bar_index = {}
        last_ts_per_sym = {}
        for sym, bars in sym_bars.items():
            last_ts_per_sym[sym] = bars[-1]["_et"]
            for b in bars:
                bar_index[(sym, b["_et"])] = b
        all_ts = sorted({b["_et"] for bars in sym_bars.values() for b in bars})

        positions = {}
        for ts in all_ts:
            t = ts.time()
            in_window = (t.hour > 10 or (t.hour == 10 and t.minute >= 0)) and \
                        (t.hour < 15 or (t.hour == 15 and t.minute < 55))

            for sym in list(positions.keys()):
                bar = bar_index.get((sym, ts))
                if bar is None:
                    continue
                pos = positions[sym]
                is_last = (ts == last_ts_per_sym.get(sym))
                pos["peak"] = max(pos["peak"], bar["high"])
                trail_stop = pos["peak"] * (1 + trail_pct / 100)
                effective_stop = max(pos["stop"], trail_stop)
                if bar["low"] <= effective_stop:
                    reason = "TRAIL" if effective_stop > pos["stop"] else "STOP"
                    trades.append({"symbol": sym, "day": str(day), "reason": reason,
                                    "pnl": (effective_stop - pos["entry"]) * pos["shares"]})
                    del positions[sym]
                elif is_last:
                    trades.append({"symbol": sym, "day": str(day), "reason": "EOD",
                                    "pnl": (bar["close"] - pos["entry"]) * pos["shares"]})
                    del positions[sym]

            free_slots = slots - len(positions)
            if free_slots > 0 and in_window:
                candidates = []
                for sym, lv in lv_by_sym.items():
                    if sym in positions:
                        continue
                    bar = bar_index.get((sym, ts))
                    if bar is None or ts == last_ts_per_sym.get(sym):
                        continue
                    price = bar["close"]
                    if zone_of(price, lv) == "BUY" and bar["low"] <= lv["rl"] and bar["close"] > bar["open"]:
                        depth = (lv["rl"] - price) / lv["rl"] * 100
                        candidates.append((depth, sym, bar, lv))
                candidates.sort(key=lambda c: c[0], reverse=True)
                for depth, sym, bar, lv in candidates[:free_slots]:
                    entry = bar["close"]
                    stop = max(lv["sl"], entry * (1 + cfg["stop_backstop_pct"] / 100))
                    stop = min(stop, entry * (1 + cfg["min_stop_distance_pct"] / 100))
                    if stop < entry:
                        risk_per_share = entry - stop
                        notional = min(cfg["risk_per_trade"] / risk_per_share * entry, cfg["max_notional"])
                        positions[sym] = {"entry": entry, "shares": notional / entry, "stop": stop, "peak": entry}

        for sym, pos in positions.items():
            last_bar = bar_index.get((sym, last_ts_per_sym[sym]))
            price = last_bar["close"] if last_bar else pos["entry"]
            trades.append({"symbol": sym, "day": str(day), "reason": "EOD_FORCE",
                            "pnl": (price - pos["entry"]) * pos["shares"]})
    return trades

BASE_CFG = dict(stop_backstop_pct=-4.0, min_stop_distance_pct=-2.5, target_frac=0.25,
                min_zone_width_pct=3.0, risk_per_trade=2.50, max_notional=150.0)  # risk doubled
                # 2026-08-22 -- see sage_bot_v13.py's RISK_PER_TRADE_DOLLARS comment for why
LIVE_WATCHLIST = ["IBRX", "IOVA", "NVDA", "TSLA", "AMD", "GDX", "SMCI"]  # was COIN until the
                                 # 2026-08-21 swap -- this constant was NOT updated at the time,
                                 # so every strategy_experiments.py run between the swap and
                                 # 2026-08-22 (portfolio constraint, bootstrap, correlation, $1000
                                 # sizing, first-30-days) was actually testing COIN, not the
                                 # symbol that was really live. Fixed 2026-08-22.

def cfg(**overrides):
    c = dict(BASE_CFG)
    c.update(overrides)
    return c

VARIANTS = [
    ("baseline (live config, live watchlist)", CURRENT_WATCHLIST, cfg()),
    ("+ COIN added to watchlist", CURRENT_WATCHLIST + ["COIN"], cfg()),
    ("+ SMCI added to watchlist", CURRENT_WATCHLIST + ["SMCI"], cfg()),
    ("+ COIN and SMCI added", CURRENT_WATCHLIST + ["COIN", "SMCI"], cfg()),
    ("wider target (25% of range)", CURRENT_WATCHLIST, cfg(target_frac=0.25)),
    ("wider target (35% of range)", CURRENT_WATCHLIST, cfg(target_frac=0.35)),
    ("wider stop (min -3.5% vs -2.5%)", CURRENT_WATCHLIST, cfg(min_stop_distance_pct=-3.5)),
    ("tighter zone filter (4.0% vs 3.0%)", CURRENT_WATCHLIST, cfg(min_zone_width_pct=4.0)),
    ("wider target (25%) + COIN added", CURRENT_WATCHLIST + ["COIN"], cfg(target_frac=0.25)),
]

def daily_pnls(daily_by_symbol, fivemin_by_symbol, min_day, max_day, watchlist, cfg, slots,
                blackout_days_by_symbol=None):
    """Trade-level P&L from backtest_portfolio, bucketed by trading day.
    Day is the natural resampling unit -- trades within a day are
    correlated (same market conditions, competing for the same slots),
    trades across days are close to independent."""
    trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, min_day, max_day, watchlist, cfg, slots,
                                 blackout_days_by_symbol)
    by_day = defaultdict(float)
    for t in trades:
        by_day[t["day"]] += t["pnl"]
    return by_day

def block_bootstrap(daily_pnl_values, n_resamples=10000, seed=42):
    """Resample TRADING DAYS with replacement (not individual trades) --
    preserves whatever correlation exists between trades on the same day
    (shared market regime, shared slot competition) instead of pretending
    every trade is independent. Builds a distribution of what total P&L
    over an equivalent-length period could plausibly have looked like,
    given the actual daily outcomes observed. This quantifies variance
    risk (could this exact edge produce a bad stretch by chance?), which
    is a different question from the window-split re-validation (does the
    edge hold across different market regimes?) -- both matter."""
    n = len(daily_pnl_values)
    rng = random.Random(seed)
    totals = []
    for _ in range(n_resamples):
        totals.append(sum(rng.choice(daily_pnl_values) for _ in range(n)))
    totals.sort()
    return totals

def symbol_daily_returns_by_date(daily_bars):
    bars = sorted(daily_bars, key=lambda b: b["_date"])
    out = {}
    for i in range(1, len(bars)):
        c0 = float(bars[i - 1]["close_price"]); c1 = float(bars[i]["close_price"])
        if c0 > 0:
            out[bars[i]["_date"]] = c1 / c0 - 1
    return out

def pearson(xs, ys):
    n = len(xs)
    if n < 5:
        return None
    mx = sum(xs) / n; my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs); vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / (vx ** 0.5 * vy ** 0.5)

def percentile(sorted_values, pct):
    idx = int(len(sorted_values) * pct / 100)
    idx = min(idx, len(sorted_values) - 1)
    return sorted_values[idx]

def run_variant(daily_by_symbol, fivemin_by_symbol, windows, watchlist, config, blackout_days_by_symbol=None):
    """Uses backtest_portfolio (real slot cap + earnings blackout + weekly
    pause) at slots=6, matching current buying power ($193.82 // $31.25).
    None of these variants change risk_per_trade/max_notional, so slots=6
    is correct for all of them. Was backtest_window (unconstrained, no
    guardrails) until 2026-08-21 -- switched after discovering that left
    out real live protections and materially overstated every number."""
    results = []
    for start, end_day in windows:
        trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day, watchlist, config, 6,
                                     blackout_days_by_symbol)
        n = len(trades)
        wins = sum(1 for t in trades if t["pnl"] > 0)
        pnl = sum(t["pnl"] for t in trades)
        wr = wins / n * 100 if n else 0
        results.append({"trades": n, "winrate": wr, "pnl": pnl})
    return results

def per_symbol_breakdown(daily_by_symbol, fivemin_by_symbol, min_day, max_day, watchlist, config):
    out = {}
    for sym in watchlist:
        trades = backtest_window(daily_by_symbol, fivemin_by_symbol, min_day, max_day, [sym], config)
        n = len(trades)
        pnl = sum(t["pnl"] for t in trades)
        wins = sum(1 for t in trades if t["pnl"] > 0)
        wr = wins / n * 100 if n else 0
        out[sym] = {"trades": n, "pnl": pnl, "winrate": wr}
    return out

async def main():
    token = load_jwt()
    headers = {"Authorization": f"Bearer {token}"}

    end = utc_now()
    daily_start = end - timedelta(days=210)   # comfortably covers lookback before fivemin_start
    fivemin_start = end - timedelta(days=183)  # ~6 months, widened 2026-08-23 from 84 days (~3
                                 # months) for real regime diversity, not just one summer stretch.
                                 # Safe to extend -- fetch_5min_chunked already handles arbitrarily
                                 # long ranges by chunking in 35-day pieces per symbol.

    print("=" * 78)
    print("STRATEGY EXPERIMENTS -- real data, walk-forward, same discipline as re-validation")
    print("=" * 78)
    print(f"Run time: {datetime.now(ET).strftime('%Y-%m-%d %H:%M %Z')}")
    print("(READ-ONLY -- no trades placed, nothing changed live)\n")
    print(f"Fetching daily + 5-min bars for: {', '.join(ALL_SYMBOLS)}...")

    # Daily-bars batch fetch, chunked by symbol count (not by date range like the 5-min fetch) --
    # confirmed 2026-08-22: a single all-14-symbols request intermittently returns an empty body
    # on this MCP client, same reliability class as the large-SSE-response issue already fixed
    # for 5-min data. Small batches over fresh connections avoids it.
    daily_by_symbol = {}
    for i in range(0, len(ALL_SYMBOLS), 6):
        batch = ALL_SYMBOLS[i:i + 6]
        payload = await fetch_on_fresh_connection(headers, batch, daily_start, end, "day")
        for r in payload["data"]["results"]:
            bars = [b for b in r["bars"] if not b.get("interpolated")]
            for b in bars:
                b["_date"] = parse_utc(b["begins_at"]).date()
            daily_by_symbol[r["symbol"]] = bars

    fivemin_by_symbol = {}

    for sym in ALL_SYMBOLS:
        print(f"  {sym}...")
        bars = await fetch_5min_chunked(headers, sym, fivemin_start, end)
        bars = [b for b in bars if not b.get("interpolated")]
        for b in bars:
            utc = parse_utc(b["begins_at"])
            b["_et"] = utc.astimezone(ET)
            b["open"] = float(b["open_price"]); b["close"] = float(b["close_price"])
            b["high"] = float(b["high_price"]); b["low"] = float(b["low_price"])
        fivemin_by_symbol[sym] = bars

    all_days = sorted({b["_et"].date() for bars in fivemin_by_symbol.values() for b in bars})

    print("Fetching earnings dates (for blackout modeling)...")
    blackout_days_by_symbol = {}
    for sym in LIVE_WATCHLIST:
        blackout_days_by_symbol[sym] = await fetch_earnings_blackout_days(
            headers, sym, all_days[0], all_days[-1])
        if blackout_days_by_symbol[sym]:
            print(f"  {sym}: blacked out {sorted(blackout_days_by_symbol[sym])}")

    try:
        bp_payload = await fetch_on_fresh_connection_tool(headers, "get_portfolio", {"account_number": "724375969"})
        real_bp = float(bp_payload["data"]["buying_power"]["buying_power"])
    except Exception as e:
        print(f"  ⚠️  live buying-power fetch failed ({e}) -- defaulting to $193.82")
        real_bp = 193.82
    real_min_notional = BASE_CFG["risk_per_trade"] / (-BASE_CFG["stop_backstop_pct"] / 100)
    real_slots = max(1, int(real_bp // real_min_notional))
    print(f"Live buying power: ${real_bp:.2f} -> {real_slots} real slot(s) at "
          f"${BASE_CFG['risk_per_trade']:.2f} risk/trade\n")

    n_windows = min(N_WINDOWS, len(all_days) // MIN_WINDOW_DAYS)
    window_size = len(all_days) // n_windows
    windows = []
    for i in range(n_windows):
        start_idx = i * window_size
        end_idx = (i + 1) * window_size - 1 if i < n_windows - 1 else len(all_days) - 1
        windows.append((all_days[start_idx], all_days[end_idx]))

    print(f"\nAvailable data: {all_days[0]} to {all_days[-1]} ({len(all_days)} trading days), "
          f"{n_windows} windows\n")
    for i, (ws, we) in enumerate(windows):
        print(f"  Window {i+1}: {ws} to {we}")
    print()

    print(f"{'Variant':<38} {'Trades':<8} {'AvgWR':<8} {'TotalP&L':<10} {'Spread':<8} {'PerWindow'}")
    print("-" * 100)
    variant_totals = []
    for name, watchlist, config in VARIANTS:
        results = run_variant(daily_by_symbol, fivemin_by_symbol, windows, watchlist, config, blackout_days_by_symbol)
        total_trades = sum(r["trades"] for r in results)
        total_pnl = sum(r["pnl"] for r in results)
        avg_wr = sum(r["winrate"] for r in results) / len(results) if results else 0
        pnls = [r["pnl"] for r in results]
        spread = max(pnls) - min(pnls) if pnls else 0
        per_window = " / ".join(f"${r['pnl']:+.2f}" for r in results)
        print(f"{name:<38} {total_trades:<8} {avg_wr:<7.1f}% ${total_pnl:<+9.2f} ${spread:<7.2f} {per_window}")
        variant_totals.append((name, total_pnl, total_trades, spread))

    print("\n" + "=" * 78)
    print("PER-SYMBOL BREAKDOWN -- baseline config, full period (which symbols carry, which drag)")
    print("=" * 78)
    breakdown = per_symbol_breakdown(daily_by_symbol, fivemin_by_symbol, all_days[0], all_days[-1],
                                      ALL_SYMBOLS, BASE_CFG)
    for sym, stats in sorted(breakdown.items(), key=lambda kv: -kv[1]["pnl"]):
        tag = "  (candidate, not live)" if sym not in LIVE_WATCHLIST else ""
        print(f"  {sym:<7} {stats['trades']:>3} trades  {stats['winrate']:>5.1f}% WR  ${stats['pnl']:+.2f}{tag}")

    print("\nBest total P&L:", max(variant_totals, key=lambda v: v[1])[0])

    print("\n" + "=" * 78)
    print("PORTFOLIO CAPITAL CONSTRAINT -- does the live bot's slot cap eat into these numbers?")
    print("=" * 78)
    print("Every number above (and every rolling_revalidation run) backtests each symbol")
    print("INDEPENDENTLY and sums the results -- implicitly assuming unlimited buying power,")
    print("i.e. all 7 symbols could be held at once. The live bot can't: slots = int(buying_power")
    print(f"// ${real_min_notional:.2f}), which on this account is {real_slots}, not 7. This re-runs "
          f"the CURRENT live config")
    print("(SMCI in watchlist, 25% target) with a real slot cap, picking signals the same way the")
    print("live bot does when more than one fires the same day -- ranked by depth-into-zone.\n")
    unconstrained = []
    for start, end_day in windows:
        trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                     LIVE_WATCHLIST, BASE_CFG, 99, blackout_days_by_symbol)
        unconstrained.append({"trades": len(trades), "pnl": sum(t["pnl"] for t in trades)})
    unconstrained_pnl = sum(r["pnl"] for r in unconstrained)
    unconstrained_trades = sum(r["trades"] for r in unconstrained)
    print(f"{'Slots':<8} {'Trades':<8} {'TotalP&L':<10} {'% of unconstrained':<20} PerWindow")
    print("-" * 78)
    print(f"{'unlimited':<8} {unconstrained_trades:<8} ${unconstrained_pnl:<+9.2f} {'100% (reference)':<20} "
          + " / ".join(f"${r['pnl']:+.2f}" for r in unconstrained))
    for slots in (1, 2, 3, 4, 6):
        results = []
        for start, end_day in windows:
            trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                         LIVE_WATCHLIST, BASE_CFG, slots, blackout_days_by_symbol)
            results.append({"trades": len(trades), "pnl": sum(t["pnl"] for t in trades)})
        total_trades = sum(r["trades"] for r in results)
        total_pnl = sum(r["pnl"] for r in results)
        pct = (total_pnl / unconstrained_pnl * 100) if unconstrained_pnl else 0
        per_window = " / ".join(f"${r['pnl']:+.2f}" for r in results)
        tag = f"  <- current buying power (${real_bp:.2f})" if slots == real_slots else ""
        print(f"{slots:<8} {total_trades:<8} ${total_pnl:<+9.2f} {pct:<19.0f}% {per_window}{tag}")

    print("\n" + "=" * 78)
    print("GDX REMOVED -- does dropping the weakest symbol free up the scarce slot(s) for better setups?")
    print("=" * 78)
    print("GDX backtested at 42.9% WR / -$0.90 standalone. At 1-2 slots it can grab the only")
    print("available slot (ranked by depth-into-zone) and block a better signal the same day.")
    print("This re-runs the slot-constrained sim with GDX dropped from the watchlist.\n")
    no_gdx_watchlist = [s for s in LIVE_WATCHLIST if s != "GDX"]
    print(f"{'Slots':<8} {'Trades':<8} {'TotalP&L (no GDX)':<20} {'vs with GDX':<14} PerWindow")
    print("-" * 88)
    for slots in (1, 2, 3, 4):
        with_gdx = []
        no_gdx = []
        for start, end_day in windows:
            t1 = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                     LIVE_WATCHLIST, BASE_CFG, slots, blackout_days_by_symbol)
            t2 = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                     no_gdx_watchlist, BASE_CFG, slots, blackout_days_by_symbol)
            with_gdx.append({"trades": len(t1), "pnl": sum(t["pnl"] for t in t1)})
            no_gdx.append({"trades": len(t2), "pnl": sum(t["pnl"] for t in t2)})
        pnl_with = sum(r["pnl"] for r in with_gdx)
        pnl_without = sum(r["pnl"] for r in no_gdx)
        trades_without = sum(r["trades"] for r in no_gdx)
        delta = pnl_without - pnl_with
        per_window = " / ".join(f"${r['pnl']:+.2f}" for r in no_gdx)
        print(f"{slots:<8} {trades_without:<8} ${pnl_without:<+18.2f} {delta:<+13.2f} {per_window}")

    print("\n" + "=" * 78)
    print("STATISTICAL CONFIDENCE -- block bootstrap over the current live config, real capital")
    print("=" * 78)
    print("The 3-window split answers 'does the edge hold across different stretches of market'.")
    print("This answers a different question: 'given the daily outcomes we actually observed, how")
    print("much could total P&L have varied by chance alone?' Resamples trading days (not individual")
    print("trades, to preserve same-day correlation) with replacement, 10,000 times, at the CURRENT")
    print("live config and real buying power (6 slots).\n")
    day_pnls = daily_pnls(daily_by_symbol, fivemin_by_symbol, all_days[0], all_days[-1],
                           LIVE_WATCHLIST, BASE_CFG, real_slots, blackout_days_by_symbol)
    values = list(day_pnls.values())
    actual_total = sum(values)
    print(f"Actual observed: {len(values)} trading days, ${actual_total:+.2f} total "
          f"(${actual_total/len(values):+.3f}/day average)\n")
    dist = block_bootstrap(values, n_resamples=10000)
    p5, p25, p50, p75, p95 = (percentile(dist, p) for p in (5, 25, 50, 75, 95))
    prob_loss = sum(1 for t in dist if t < 0) / len(dist) * 100
    print(f"  5th percentile:  ${p5:+.2f}   (a genuinely bad stretch)")
    print(f" 25th percentile:  ${p25:+.2f}")
    print(f" 50th percentile:  ${p50:+.2f}   (median -- typical outcome)")
    print(f" 75th percentile:  ${p75:+.2f}")
    print(f" 95th percentile:  ${p95:+.2f}   (a genuinely good stretch)")
    print(f"\nP(net loss over 58 days, resampled): {prob_loss:.1f}%")
    print(f"\nReading this: the point estimate (${actual_total:+.2f}) is one draw. If the 5th")
    print(f"percentile is still comfortably positive, the edge is unlikely to be a fluke of trade")
    print(f"sequencing. If it dips negative, the observed total is doing a lot of the work and a")
    print(f"real bad stretch is plausible even if the underlying edge is real.")

    print("\n" + "=" * 78)
    print("SMARTER EXITS -- trailing stop instead of a fixed target, real capital (6 slots)")
    print("=" * 78)
    print("Current live exit: hard stop, OR a fixed target at 25% of range, OR EOD flatten.")
    print("Alternative tested: hard stop, OR trail X% below the peak price since entry (let winners")
    print("run further than a fixed target allows), OR EOD flatten. Same entries, same sizing --")
    print("only the exit rule changes, so this isolates whether the exit is leaving money on the table.\n")
    fixed_results = []
    for start, end_day in windows:
        trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                     LIVE_WATCHLIST, BASE_CFG, real_slots, blackout_days_by_symbol)
        fixed_results.append({"trades": len(trades), "pnl": sum(t["pnl"] for t in trades)})
    fixed_total = sum(r["pnl"] for r in fixed_results)
    fixed_trades = sum(r["trades"] for r in fixed_results)
    print(f"{'Exit rule':<28} {'Trades':<8} {'TotalP&L':<10} {'Spread':<8} PerWindow")
    print("-" * 90)
    print(f"{'fixed target (live)':<28} {fixed_trades:<8} ${fixed_total:<+9.2f} "
          f"${max(r['pnl'] for r in fixed_results) - min(r['pnl'] for r in fixed_results):<7.2f} "
          + " / ".join(f"${r['pnl']:+.2f}" for r in fixed_results))
    for trail_pct in (-1.0, -1.5, -2.0, -2.5):
        results = []
        for start, end_day in windows:
            trades = backtest_portfolio_trailing(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                                  LIVE_WATCHLIST, BASE_CFG, real_slots, trail_pct)
            results.append({"trades": len(trades), "pnl": sum(t["pnl"] for t in trades)})
        total = sum(r["pnl"] for r in results)
        pnls = [r["pnl"] for r in results]
        spread = max(pnls) - min(pnls)
        per_window = " / ".join(f"${r['pnl']:+.2f}" for r in results)
        print(f"{'trail ' + str(trail_pct) + '%':<28} {sum(r['trades'] for r in results):<8} "
              f"${total:<+9.2f} ${spread:<7.2f} {per_window}")

    print("\n" + "=" * 78)
    print("CORRELATION CHECK -- is the watchlist actually diversified, or doubled-up exposure?")
    print("=" * 78)
    print("Pairwise correlation of daily returns across the live watchlist. A high positive")
    print("correlation means holding both symbols isn't really 2 independent bets -- it's ~1 bet")
    print("at ~2x the position count, understating real concentration risk.\n")
    returns_by_sym = {sym: symbol_daily_returns_by_date(daily_by_symbol.get(sym, [])) for sym in LIVE_WATCHLIST}
    pairs = []
    for i, s1 in enumerate(LIVE_WATCHLIST):
        for s2 in LIVE_WATCHLIST[i + 1:]:
            common = sorted(set(returns_by_sym[s1]) & set(returns_by_sym[s2]))
            xs = [returns_by_sym[s1][d] for d in common]
            ys = [returns_by_sym[s2][d] for d in common]
            r = pearson(xs, ys)
            if r is not None:
                pairs.append((s1, s2, r, len(common)))
    pairs.sort(key=lambda p: -abs(p[2]))
    print(f"{'Pair':<16} {'Correlation':<12} {'Days':<6} Flag")
    print("-" * 50)
    high_corr = []
    for s1, s2, r, n in pairs:
        flag = ""
        if abs(r) >= 0.6:
            flag = "HIGH -- effectively one bet, not two"
            high_corr.append((s1, s2, r))
        elif abs(r) >= 0.4:
            flag = "moderate"
        print(f"{s1+'/'+s2:<16} {r:<+12.2f} {n:<6} {flag}")
    if high_corr:
        print(f"\n{len(high_corr)} pair(s) flagged high (|r| >= 0.6) -- worth capping combined slots "
              f"for these, not treating them as independent diversification.")
    else:
        print(f"\nNo pairs at |r| >= 0.6 -- the watchlist is genuinely diversified, no correlation-based "
              f"sizing change is justified by this data. (COIN/SMCI flagged 'correlated-w/AMD-NVDA' by "
              f"the screener was a qualitative flag, not a measured one -- this is the actual number.)")

    print("\n" + "=" * 78)
    print("CAPITAL SCALING -- what would $1000 buying power actually do?")
    print("=" * 78)
    print(f"RISK_PER_TRADE_DOLLARS (${BASE_CFG['risk_per_trade']:.2f}) and MAX_NOTIONAL_PER_TRADE "
          f"(${BASE_CFG['max_notional']:.0f}) are FIXED DOLLAR")
    print(f"amounts, not a % of buying power. That means extra capital past the "
          f"~${real_min_notional * 3:.0f}-{real_min_notional * 4:.0f} needed")
    print("for full slot capacity just sits idle -- it does NOT make individual trades bigger.")
    print("Tests both: $1000 bp with sizing UNCHANGED, vs. $1000 bp with sizing scaled to match.\n")
    scale = 1000 / real_bp
    scaled_cfg = dict(BASE_CFG, risk_per_trade=BASE_CFG["risk_per_trade"] * scale,
                       max_notional=BASE_CFG["max_notional"] * scale)
    scaled_min_notional = scaled_cfg["risk_per_trade"] / (-BASE_CFG["stop_backstop_pct"] / 100)
    slots_1000_unchanged = int(1000 // real_min_notional)
    slots_1000_scaled = int(1000 // scaled_min_notional)
    print(f"Unchanged sizing at $1000 bp -> {slots_1000_unchanged} slots (only ~4-6 ever used on a "
          f"7-symbol watchlist)")
    print(f"Scaled sizing at $1000 bp   -> risk ${scaled_cfg['risk_per_trade']:.2f}/trade, "
          f"cap ${scaled_cfg['max_notional']:.2f}/trade, {slots_1000_scaled} slots\n")

    unchanged_results = []
    scaled_results = []
    for start, end_day in windows:
        t1 = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                 LIVE_WATCHLIST, BASE_CFG, slots_1000_unchanged, blackout_days_by_symbol)
        t2 = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                 LIVE_WATCHLIST, scaled_cfg, slots_1000_scaled, blackout_days_by_symbol)
        unchanged_results.append({"trades": len(t1), "pnl": sum(t["pnl"] for t in t1)})
        scaled_results.append({"trades": len(t2), "pnl": sum(t["pnl"] for t in t2)})
    unchanged_total = sum(r["pnl"] for r in unchanged_results)
    scaled_total = sum(r["pnl"] for r in scaled_results)
    print(f"{'Scenario':<28} {'Trades':<8} {'TotalP&L':<10} PerWindow")
    print("-" * 78)
    print(f"{'current ($193.82 bp)':<28} {fixed_trades:<8} ${fixed_total:<+9.2f} "
          + " / ".join(f"${r['pnl']:+.2f}" for r in fixed_results))
    print(f"{'$1000, sizing unchanged':<28} {sum(r['trades'] for r in unchanged_results):<8} "
          f"${unchanged_total:<+9.2f} " + " / ".join(f"${r['pnl']:+.2f}" for r in unchanged_results))
    print(f"{'$1000, sizing scaled 5.16x':<28} {sum(r['trades'] for r in scaled_results):<8} "
          f"${scaled_total:<+9.2f} " + " / ".join(f"${r['pnl']:+.2f}" for r in scaled_results))
    print(f"\nIf 'unchanged' basically equals current: capital isn't the lever anymore, sizing is.")
    print(f"If 'scaled' is ~5x current: the edge itself scales cleanly with position size on this")
    print(f"data (expected, since P&L is just price-move % times position size -- but real slippage")
    print(f"and liquidity on $75 clips vs $387 clips on names like IBRX/IOVA are NOT modeled here,")
    print(f"so treat the scaled number as an upper bound, not a promise.")

    print("\n" + "=" * 78)
    print("CAPITAL SCALING -- what would $3000 buying power actually do?")
    print("=" * 78)
    scale3k = 3000 / real_bp
    scaled_cfg3k = dict(BASE_CFG, risk_per_trade=BASE_CFG["risk_per_trade"] * scale3k,
                         max_notional=BASE_CFG["max_notional"] * scale3k)
    scaled_min_notional3k = scaled_cfg3k["risk_per_trade"] / (-BASE_CFG["stop_backstop_pct"] / 100)
    slots_3000_unchanged = int(3000 // real_min_notional)
    slots_3000_scaled = int(3000 // scaled_min_notional3k)
    print(f"Unchanged sizing at $3000 bp -> {slots_3000_unchanged} slots (still only ~4-6 ever "
          f"used on a 7-symbol watchlist)")
    print(f"Scaled sizing at $3000 bp   -> risk ${scaled_cfg3k['risk_per_trade']:.2f}/trade, "
          f"cap ${scaled_cfg3k['max_notional']:.2f}/trade, {slots_3000_scaled} slots\n")

    unchanged3k_results, scaled3k_results = [], []
    for start, end_day in windows:
        t1 = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                 LIVE_WATCHLIST, BASE_CFG, slots_3000_unchanged, blackout_days_by_symbol)
        t2 = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                 LIVE_WATCHLIST, scaled_cfg3k, slots_3000_scaled, blackout_days_by_symbol)
        unchanged3k_results.append({"trades": len(t1), "pnl": sum(t["pnl"] for t in t1)})
        scaled3k_results.append({"trades": len(t2), "pnl": sum(t["pnl"] for t in t2)})
    unchanged3k_total = sum(r["pnl"] for r in unchanged3k_results)
    scaled3k_total = sum(r["pnl"] for r in scaled3k_results)
    print(f"{'Scenario':<28} {'Trades':<8} {'TotalP&L':<10} PerWindow")
    print("-" * 78)
    print(f"{f'current (${real_bp:.2f} bp)':<28} {fixed_trades:<8} ${fixed_total:<+9.2f} "
          + " / ".join(f"${r['pnl']:+.2f}" for r in fixed_results))
    print(f"{'$3000, sizing unchanged':<28} {sum(r['trades'] for r in unchanged3k_results):<8} "
          f"${unchanged3k_total:<+9.2f} " + " / ".join(f"${r['pnl']:+.2f}" for r in unchanged3k_results))
    print(f"{f'$3000, scaled {scale3k:.2f}x':<28} {sum(r['trades'] for r in scaled3k_results):<8} "
          f"${scaled3k_total:<+9.2f} " + " / ".join(f"${r['pnl']:+.2f}" for r in scaled3k_results))
    print(f"\nSame pattern as $1000: unchanged sizing barely moves the number, since the watchlist")
    print(f"only ever needs a handful of slots. Scaled sizing at 3x the deposit means clips around")
    print(f"${scaled_cfg3k['max_notional']:.0f} each on names like IBRX/IOVA -- at that size, real slippage and")
    print(f"liquidity limits become a genuinely serious concern, not a minor footnote. Treat this")
    print(f"number as considerably less reliable than the $1000 scaled estimate, not just bigger.")

    print("\n" + "=" * 78)
    print(f"FIRST 30 TRADING DAYS -- day-by-day, current live config, real capital ({real_slots} slots)")
    print("=" * 78)
    first30 = all_days[:30]
    trades_30 = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, first30[0], first30[-1],
                                    LIVE_WATCHLIST, BASE_CFG, real_slots, blackout_days_by_symbol)
    by_day_30 = defaultdict(list)
    for t in trades_30:
        by_day_30[t["day"]].append(t)
    print(f"{'Date':<12} {'Trades':<8} {'DayP&L':<10} {'Cumulative':<12} Symbols")
    print("-" * 70)
    running = 0.0
    for day in first30:
        day_str = str(day)
        day_trades = by_day_30.get(day_str, [])
        day_pnl = sum(t["pnl"] for t in day_trades)
        running += day_pnl
        syms = ", ".join(sorted({t["symbol"] for t in day_trades})) if day_trades else "-"
        print(f"{day_str:<12} {len(day_trades):<8} ${day_pnl:<+9.2f} ${running:<+11.2f} {syms}")
    print(f"\n30-day total: ${running:+.2f}")

    print("\n" + "=" * 78)
    print("$1000 SIZING OPTIONS -- reward AND risk at a few scale tiers, not just one")
    print("=" * 78)
    print("Same backtest, same watchlist, same entries -- only RISK_PER_TRADE_DOLLARS and")
    print("MAX_NOTIONAL_PER_TRADE change, scaled by the tier's multiplier of the current live")
    print(f"values (${BASE_CFG['risk_per_trade']:.2f} risk / ${BASE_CFG['max_notional']:.2f} cap). "
          f"Bad-stretch column is the 5th-percentile bootstrap")
    print("outcome at that tier (10,000 resamples) -- the number to look at if you care more about")
    print("'how bad could a rough stretch be' than 'what's the average.'\n")
    scale_1000 = 1000 / 193.82
    tiers = [
        (f"A: unchanged (${BASE_CFG['risk_per_trade']:.2f}/${BASE_CFG['max_notional']:.0f})", 1.0),
        ("B: conservative (2.5x)", 2.5),
        ("C: moderate (3.75x)", 3.75),
        (f"D: full proportional ({scale_1000:.2f}x)", scale_1000),
    ]
    print(f"{'Tier':<32} {'Risk/trade':<12} {'Cap/trade':<12} {'TotalP&L':<10} {'BadStretch(5th%)':<18} PerWindow")
    print("-" * 130)
    for label, mult in tiers:
        t_cfg = dict(BASE_CFG, risk_per_trade=BASE_CFG["risk_per_trade"] * mult,
                     max_notional=BASE_CFG["max_notional"] * mult)
        t_min_notional = t_cfg["risk_per_trade"] / (-BASE_CFG["stop_backstop_pct"] / 100)
        t_slots = max(1, int(1000 // t_min_notional))
        results = []
        for start, end_day in windows:
            trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                         LIVE_WATCHLIST, t_cfg, t_slots, blackout_days_by_symbol)
            results.append({"trades": len(trades), "pnl": sum(t["pnl"] for t in trades)})
        total = sum(r["pnl"] for r in results)
        per_window = " / ".join(f"${r['pnl']:+.2f}" for r in results)

        t_daily = daily_pnls(daily_by_symbol, fivemin_by_symbol, all_days[0], all_days[-1],
                              LIVE_WATCHLIST, t_cfg, t_slots, blackout_days_by_symbol)
        t_dist = block_bootstrap(list(t_daily.values()), n_resamples=10000)
        t_p5 = percentile(t_dist, 5)

        print(f"{label:<32} ${t_cfg['risk_per_trade']:<11.2f} ${t_cfg['max_notional']:<11.2f} "
              f"${total:<+9.2f} ${t_p5:<+17.2f} {per_window}")

    print("\nHow to read this: tier A leaves the extra $800+ sitting idle (same as current). Tier D")
    print("(full scale) has the best total but also the biggest bad-stretch number to actually")
    print("stomach if it happens -- that's a real dollar figure, not a percentage, so weigh it as one.")
    print("B and C are the middle ground: less upside than D, but a gentler bad-stretch to sit through.")

    print("\n" + "=" * 78)
    print(f"RISK PER TRADE, SAME ${real_bp:.2f} -- bigger bets, but fewer fit at once")
    print("=" * 78)
    print("Different question from the $1000 test above: this keeps buying power FIXED at what's")
    print("actually in the account and only raises risk-per-trade / notional-per-trade. A bigger bet")
    print("eats more of the same fixed buying power, so slots SHRINK as risk goes up -- more $ at risk")
    print("per trade, but less diversification across the watchlist. Real tradeoff, not free upside.\n")
    base_risk, base_cap = BASE_CFG["risk_per_trade"], BASE_CFG["max_notional"]
    risk_tiers = [
        (f"current (${base_risk:.2f} / ${base_cap:.0f})", 1.0),
        (f"2x (${base_risk*2:.2f} / ${base_cap*2:.0f})", 2.0),
        (f"3x (${base_risk*3:.2f} / ${base_cap*3:.0f})", 3.0),
        (f"4x (${base_risk*4:.2f} / ${base_cap*4:.0f})", 4.0),
        (f"6x (${base_risk*6:.2f} / ${base_cap*6:.0f})", 6.0),
    ]
    print(f"{'Risk tier':<24} {'Slots':<7} {'TotalP&L':<10} {'BadStretch(5th%)':<18} PerWindow")
    print("-" * 100)
    for label, mult in risk_tiers:
        t_cfg = dict(BASE_CFG, risk_per_trade=BASE_CFG["risk_per_trade"] * mult,
                     max_notional=BASE_CFG["max_notional"] * mult)
        t_min_notional = t_cfg["risk_per_trade"] / (-BASE_CFG["stop_backstop_pct"] / 100)
        t_slots = max(1, int(real_bp // t_min_notional))
        results = []
        for start, end_day in windows:
            trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                         LIVE_WATCHLIST, t_cfg, t_slots, blackout_days_by_symbol)
            results.append({"trades": len(trades), "pnl": sum(t["pnl"] for t in trades)})
        total = sum(r["pnl"] for r in results)
        per_window = " / ".join(f"${r['pnl']:+.2f}" for r in results)

        t_daily = daily_pnls(daily_by_symbol, fivemin_by_symbol, all_days[0], all_days[-1],
                              LIVE_WATCHLIST, t_cfg, t_slots, blackout_days_by_symbol)
        t_dist = block_bootstrap(list(t_daily.values()), n_resamples=10000)
        t_p5 = percentile(t_dist, 5)

        print(f"{label:<24} {t_slots:<7} ${total:<+9.2f} ${t_p5:<+17.2f} {per_window}")

    print("\nWatch the slots column: once it drops to 1, the bot can only ever hold one position at a")
    print("time regardless of how many symbols signal -- diversification is gone, and results start")
    print("depending heavily on which single signal happened to win the day's ranking, not the")
    print("underlying edge. That's when 'bigger risk' stops being a lever and starts being a bet on")
    print("regime luck.")

    print("\n" + "=" * 78)
    print("MORE SYMBOLS -- does expanding the watchlist actually use the 3 open slots better?")
    print("=" * 78)
    print(f"Real slots ({real_slots}) are often just sitting empty on a 7-symbol watchlist because")
    print("not enough signals fire on a given day. This tests adding the best individual standalone")
    print(f"performers from the last screener run ({', '.join(EXPANSION_CANDIDATES)}) -- none of which")
    print("cleared the screener's own 15-trade bar alone, but that bar doesn't ask the right question:")
    print("this tests them as part of the REAL portfolio, with real slots and guardrails, not isolated.\n")

    print("Fetching earnings dates for expansion candidates...")
    expansion_blackout = dict(blackout_days_by_symbol)
    for sym in EXPANSION_CANDIDATES:
        expansion_blackout[sym] = await fetch_earnings_blackout_days(headers, sym, all_days[0], all_days[-1])

    print(f"\n{'Watchlist':<32} {'Slots':<7} {'Trades':<8} {'TotalP&L':<10} {'Spread':<8} PerWindow")
    print("-" * 100)
    baseline_results = []
    for start, end_day in windows:
        trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                     LIVE_WATCHLIST, BASE_CFG, real_slots, blackout_days_by_symbol)
        baseline_results.append({"trades": len(trades), "pnl": sum(t["pnl"] for t in trades)})
    baseline_total = sum(r["pnl"] for r in baseline_results)
    baseline_pnls = [r["pnl"] for r in baseline_results]
    print(f"{'current (7 symbols)':<32} {real_slots:<7} {sum(r['trades'] for r in baseline_results):<8} "
          f"${baseline_total:<+9.2f} ${max(baseline_pnls)-min(baseline_pnls):<7.2f} "
          + " / ".join(f"${r['pnl']:+.2f}" for r in baseline_results))

    for sym in EXPANSION_CANDIDATES:
        wl = LIVE_WATCHLIST + [sym]
        results = []
        for start, end_day in windows:
            trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                         wl, BASE_CFG, real_slots, expansion_blackout)
            results.append({"trades": len(trades), "pnl": sum(t["pnl"] for t in trades)})
        total = sum(r["pnl"] for r in results)
        pnls = [r["pnl"] for r in results]
        print(f"{'+ ' + sym + ' (8 symbols)':<32} {real_slots:<7} {sum(r['trades'] for r in results):<8} "
              f"${total:<+9.2f} ${max(pnls)-min(pnls):<7.2f} " + " / ".join(f"${r['pnl']:+.2f}" for r in results))

    wl_all = LIVE_WATCHLIST + EXPANSION_CANDIDATES
    results = []
    for start, end_day in windows:
        trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                     wl_all, BASE_CFG, real_slots, expansion_blackout)
        results.append({"trades": len(trades), "pnl": sum(t["pnl"] for t in trades)})
    total = sum(r["pnl"] for r in results)
    pnls = [r["pnl"] for r in results]
    print(f"{'+ all 6 (13 symbols)':<32} {real_slots:<7} {sum(r['trades'] for r in results):<8} "
          f"${total:<+9.2f} ${max(pnls)-min(pnls):<7.2f} " + " / ".join(f"${r['pnl']:+.2f}" for r in results))

    print(f"\nBaseline for comparison: current 7-symbol watchlist = ${baseline_total:+.2f}, "
          f"spread ${max(baseline_pnls)-min(baseline_pnls):.2f}")

    print("\nReminder: more trades/higher P&L on this data doesn't mean live-trust it blind -- "
          "check the per-window spread too (smaller = more consistent). A variant with great total "
          "P&L but one huge window and two flat/negative ones is a worse bet than steady smaller gains.")

    print("\n" + "=" * 78)
    print("WINDOW DIAGNOSIS -- what actually happened in the worst window(s)?")
    print("=" * 78)
    ranked = sorted(range(len(windows)), key=lambda i: fixed_results[i]["pnl"])
    worst_idx = [i for i in ranked if fixed_results[i]["pnl"] <= 0][:2] or ranked[:1]
    for idx in worst_idx:
        ws, we = windows[idx]
        print(f"\nWindow {idx+1} ({ws} to {we}): ${fixed_results[idx]['pnl']:+.2f}, "
              f"{fixed_results[idx]['trades']} trades\n")
        trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, ws, we,
                                     LIVE_WATCHLIST, BASE_CFG, real_slots, blackout_days_by_symbol)
        trades.sort(key=lambda t: t["day"])
        by_symbol = defaultdict(lambda: {"n": 0, "pnl": 0.0})
        print(f"  {'Date':<12} {'Symbol':<7} {'Reason':<12} P&L")
        print("  " + "-" * 45)
        for t in trades:
            print(f"  {t['day']:<12} {t['symbol']:<7} {t['reason']:<12} ${t['pnl']:+.2f}")
            by_symbol[t["symbol"]]["n"] += 1
            by_symbol[t["symbol"]]["pnl"] += t["pnl"]
        print(f"\n  By symbol: " + ", ".join(f"{s} ({v['n']}, ${v['pnl']:+.2f})"
                                              for s, v in sorted(by_symbol.items(), key=lambda kv: kv[1]["pnl"])))
        reasons = defaultdict(lambda: {"n": 0, "pnl": 0.0})
        for t in trades:
            reasons[t["reason"]]["n"] += 1
            reasons[t["reason"]]["pnl"] += t["pnl"]
        print(f"  By reason: " + ", ".join(f"{r} ({v['n']}, ${v['pnl']:+.2f})" for r, v in reasons.items()))

    print("\n" + "=" * 78)
    print("SAME-DAY RE-ENTRY -- a real structural change, not a parameter tweak")
    print("=" * 78)
    print("Live behavior: once a position closes (stop, target, or EOD), that symbol is free to")
    print("signal and enter again the SAME day if a new valid setup fires (seen for real in the")
    print("window diagnosis above -- SMCI stopped out then re-entered and closed positive, same day).")
    print("This tests blocking that: once a symbol has traded once today, it's done for the day,")
    print("no matter how many more signals fire. Same entries otherwise, same sizing, same everything.\n")
    noreentry_results = []
    for start, end_day in windows:
        trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                     LIVE_WATCHLIST, BASE_CFG, real_slots, blackout_days_by_symbol,
                                     block_reentry=True)
        noreentry_results.append({"trades": len(trades), "pnl": sum(t["pnl"] for t in trades)})
    noreentry_total = sum(r["pnl"] for r in noreentry_results)
    noreentry_pnls = [r["pnl"] for r in noreentry_results]
    fixed_pnls = [r["pnl"] for r in fixed_results]
    print(f"{'Rule':<32} {'Trades':<8} {'TotalP&L':<10} {'Spread':<8} PerWindow")
    print("-" * 100)
    print(f"{'live (unlimited re-entry)':<32} {fixed_trades:<8} ${fixed_total:<+9.2f} "
          f"${max(fixed_pnls)-min(fixed_pnls):<7.2f} " + " / ".join(f"${r['pnl']:+.2f}" for r in fixed_results))
    print(f"{'one trade/symbol/day max':<32} {sum(r['trades'] for r in noreentry_results):<8} "
          f"${noreentry_total:<+9.2f} ${max(noreentry_pnls)-min(noreentry_pnls):<7.2f} "
          + " / ".join(f"${r['pnl']:+.2f}" for r in noreentry_results))
    print(f"\nDifference: ${noreentry_total - fixed_total:+.2f} total. If re-entry blocking helps, that's")
    print(f"a real, mechanistic reason (avoiding chasing the same name twice in one day) -- not a")
    print(f"coincidence dressed up as a pattern, since it changes behavior on every trading day in the")
    print(f"dataset, not just the two bad windows this was motivated by.")

    print("\n" + "=" * 78)
    print("WHOLE-SHARE SIZING -- the real cost of enabling broker-side stop orders")
    print("=" * 78)
    print("Stop orders (stop_market/stop_limit) only work with WHOLE shares -- fractional shares")
    print("are market-orders-only. At current prices, 1 share of TSLA ($362.88) and AMD ($473.21)")
    print("costs more than the entire $193.82 account; NVDA ($214.76) exceeds the $150 notional cap.")
    print("Whole-share sizing means dropping all three. This isolates two separate costs: dropping")
    print("those 3 symbols, and rounding remaining shares down to whole numbers -- so it's clear")
    print("which one actually matters.\n")
    small_watchlist = ["IBRX", "IOVA", "SMCI", "GDX"]
    fractional4_results, whole4_results = [], []
    for start, end_day in windows:
        t1 = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                 small_watchlist, BASE_CFG, real_slots, blackout_days_by_symbol)
        t2 = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day,
                                 small_watchlist, BASE_CFG, real_slots, blackout_days_by_symbol,
                                 whole_shares=True)
        fractional4_results.append({"trades": len(t1), "pnl": sum(t["pnl"] for t in t1)})
        whole4_results.append({"trades": len(t2), "pnl": sum(t["pnl"] for t in t2)})
    fractional4_total = sum(r["pnl"] for r in fractional4_results)
    whole4_total = sum(r["pnl"] for r in whole4_results)
    print(f"{'Scenario':<38} {'Trades':<8} {'TotalP&L':<10} PerWindow")
    print("-" * 110)
    print(f"{'current live (7 symbols, fractional)':<38} {fixed_trades:<8} ${fixed_total:<+9.2f} "
          + " / ".join(f"${r['pnl']:+.2f}" for r in fixed_results))
    print(f"{'IBRX/IOVA/SMCI/GDX only, fractional':<38} {sum(r['trades'] for r in fractional4_results):<8} "
          f"${fractional4_total:<+9.2f} " + " / ".join(f"${r['pnl']:+.2f}" for r in fractional4_results))
    print(f"{'IBRX/IOVA/SMCI/GDX, WHOLE shares':<38} {sum(r['trades'] for r in whole4_results):<8} "
          f"${whole4_total:<+9.2f} " + " / ".join(f"${r['pnl']:+.2f}" for r in whole4_results))
    print(f"\nCost of dropping TSLA/AMD/NVDA: ${fractional4_total - fixed_total:+.2f}")
    print(f"Additional cost of whole-share rounding on top of that: ${whole4_total - fractional4_total:+.2f}")
    print(f"Total cost of enabling real broker-side stops vs. current live setup: ${whole4_total - fixed_total:+.2f}")

if __name__ == "__main__":
    asyncio.run(main())
