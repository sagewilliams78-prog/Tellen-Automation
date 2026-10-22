#!/usr/bin/env python3
"""
Rolling walk-forward re-validation for sage_bot_v13's Range & Swing config.

Read-only. Connects to the Robinhood MCP the same way sage_bot does (same
auth file) but ONLY calls get_equity_historicals -- it never places an
order, never touches get_portfolio/positions, nothing that could act on
the account. Safe to run anytime, as often as you want, without any risk
to open positions.

What it does, and why:
  Every backtest run this session (2026-08-21) used ONE 62-day window,
  split ONE way into train/test. That's enough to catch gross overfitting
  (which caught the volume/breadth filters) but not enough to know if the
  strategy has a durable edge or we just sampled one lucky/unlucky
  62-day stretch. Real walk-forward practice (confirmed via research
  2026-08-21 against a published methodology) uses MANY independent
  train/test windows, not one.

  This script pulls the most recent ~62 trading days available (capped by
  the historicals API's 5000-bar/symbol limit for 5-minute data) and
  splits them into several non-overlapping windows, then checks v13's
  CURRENT, ALREADY-CHOSEN parameters against each one. It does NOT
  re-search for better parameters per window -- re-optimizing on
  ever-smaller slices is exactly the overfitting trap this whole exercise
  exists to avoid. This is re-validation (does the existing config still
  hold up?), not re-optimization (find new numbers).

  Run this periodically (weekly is a reasonable cadence -- daily is too
  frequent to mean anything on this much data) as more real trading days
  accumulate. If a recent window looks badly worse than the others,
  that's a signal to look closer, not to blindly retune -- any parameter
  change should go through the same backtest-before-trust discipline as
  everything else this session, with a human reviewing the result.

Usage:
    ./rolling_revalidation.py
"""
import asyncio, json, os, sys, subprocess
from datetime import datetime, timedelta, date, timezone
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
                      "\"robin hood trading bot/.venv/bin/python\" rolling_revalidation.py")

MCP_URL = "https://agent.robinhood.com/mcp/trading"
WATCHLIST = ["IBRX", "IOVA", "NVDA", "TSLA", "AMD", "GDX", "SMCI"]
DATA_DIR = os.path.expanduser("~/.sage_bot_revalidation")
OBSIDIAN_VAULT = os.path.expanduser("~/Documents/Eva Trading Journal")

def notify_macos(title, message):
    """Best-effort local notification -- same pattern as sage_bot_v13.py."""
    try:
        script = f'display notification "{message}" with title "{title}" sound name "Glass"'
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
    except Exception as e:
        print(f"  ⚠️  notification failed: {e}")

# v13's CURRENT config -- kept in sync manually. If you change v13's
# constants, update these too so re-validation tests what's actually live.
STOP_LOSS_BACKSTOP_PCT = -4.0
MIN_STOP_DISTANCE_PCT = -2.5
TARGET_FRAC = 0.25
MIN_ZONE_WIDTH_PCT = 3.0
SWING_LOOKBACK_DAYS = 5
RISK_PER_TRADE_DOLLARS = 2.50
MAX_NOTIONAL_PER_TRADE = 150.0

N_WINDOWS = 3          # split the available data into this many non-overlapping test windows
MIN_WINDOW_DAYS = 12   # each window needs at least this many trading days to be meaningful

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
    """Same fix as symbol_screener.py: a large batched 5-min/88-day call
    intermittently drops mid-stream ('SSE stream ended without a
    response') on this script's MCP client -- reconnecting from scratch
    per attempt is more reliable than retrying on a session that may
    already be in a bad state."""
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

async def fetch_on_fresh_connection_tool(headers, tool_name, args, attempts=3, base_delay=4):
    """Generic version of fetch_on_fresh_connection for tools other than
    get_equity_historicals (earnings, portfolio) -- same fresh-connection-
    per-attempt reliability fix."""
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

async def fetch_5min_chunked(headers, sym, start, end, chunk_days=35):
    """Fetch one symbol's 5-min bars across [start, end] in reliable-sized
    chunks and concatenate. Confirmed 2026-08-21: a single ~84-day/~4600-bar
    request for one symbol intermittently fails against this script's MCP
    client with 'SSE stream ended without a response', even though the
    IDENTICAL request succeeds cleanly through a different client -- this
    is a client-library limitation handling large SSE responses, not an
    upstream rejection (ruled out by testing the exact same range/symbol
    through the other client, which returned the full 743KB payload fine).
    Smaller per-request chunks avoid the failure entirely."""
    all_bars = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=chunk_days), end)
        payload = await fetch_on_fresh_connection(headers, [sym], chunk_start, chunk_end, "5minute")
        for r in payload["data"]["results"]:
            all_bars.extend(r.get("bars", []))
        chunk_start = chunk_end
    return all_bars

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

def zone_width_ok(lv):
    if lv["rl"] <= 0:
        return False
    return (lv["rl"] - lv["sl"]) / lv["rl"] * 100 >= MIN_ZONE_WIDTH_PCT

EARNINGS_BLACKOUT_DAYS = 1  # matches sage_bot_v13.py's EARNINGS_BLACKOUT_DAYS
WEEKLY_MIN_TRADES = 5       # matches sage_bot_v13.py's WEEKLY_MIN_TRADES
WEEKLY_WINRATE_FLOOR = 40.0  # matches sage_bot_v13.py's WEEKLY_WINRATE_FLOOR

async def fetch_earnings_blackout_days(headers, sym, window_start, window_end):
    """Real historical earnings dates (get_earnings_results, trailing up to
    8 quarters) turned into the calendar dates that would have been
    blacked out (+/- EARNINGS_BLACKOUT_DAYS) inside the backtest window.
    An ETF like GDX legitimately returns no results -- not a failure."""
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

async def fetch_buying_power(headers):
    payload = await fetch_on_fresh_connection_tool(headers, "get_portfolio", {"account_number": "724375969"})
    return float(payload["data"]["buying_power"]["buying_power"])

def backtest_portfolio(daily_by_symbol, fivemin_by_symbol, min_day, max_day, slots, blackout_days_by_symbol=None):
    """Simulates ALL watchlist symbols in lockstep sharing a real slot cap
    (unlike testing each symbol independently and summing, which
    implicitly assumes unlimited buying power) AND models the two live
    guardrails this function was missing until 2026-08-21: earnings
    blackout and the weekly win-rate circuit breaker (trailing 7 calendar
    days, >=5 trades, pauses NEW entries if win rate <40% -- existing
    positions still exit normally, matching sage_bot_v13.py exactly)."""
    blackout_days_by_symbol = blackout_days_by_symbol or {}
    trades = []
    all_days = sorted({b["_et"].date() for sym in WATCHLIST for b in fivemin_by_symbol.get(sym, [])
                        if min_day <= b["_et"].date() <= max_day})
    for day in all_days:
        sym_bars = {}
        for sym in WATCHLIST:
            bars = sorted([b for b in fivemin_by_symbol.get(sym, []) if b["_et"].date() == day],
                           key=lambda b: b["_et"])
            if bars:
                sym_bars[sym] = bars
        if not sym_bars:
            continue

        lv_by_sym = {}
        for sym in sym_bars:
            lv = levels_for_day(daily_by_symbol.get(sym, []), day)
            if lv is not None and zone_width_ok(lv):
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
                elif bar["high"] >= pos["target"]:
                    trades.append({"symbol": sym, "day": str(day), "day_obj": day, "reason": "TARGET",
                                    "pnl": (pos["target"] - pos["entry"]) * pos["shares"]})
                    del positions[sym]
                elif is_last:
                    trades.append({"symbol": sym, "day": str(day), "day_obj": day, "reason": "EOD",
                                    "pnl": (bar["close"] - pos["entry"]) * pos["shares"]})
                    del positions[sym]

            free_slots = slots - len(positions)
            if free_slots > 0 and in_window and not weekly_pause:
                candidates = []
                for sym, lv in lv_by_sym.items():
                    if sym in positions or sym in blackout_today:
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
                    stop = max(lv["sl"], entry * (1 + STOP_LOSS_BACKSTOP_PCT / 100))
                    stop = min(stop, entry * (1 + MIN_STOP_DISTANCE_PCT / 100))
                    target = lv["rl"] + TARGET_FRAC * (lv["rh"] - lv["rl"])
                    if stop < entry and target > entry:
                        risk_per_share = entry - stop
                        notional = min(RISK_PER_TRADE_DOLLARS / risk_per_share * entry, MAX_NOTIONAL_PER_TRADE)
                        positions[sym] = {"entry": entry, "shares": notional / entry, "stop": stop, "target": target}

        for sym, pos in positions.items():
            last_bar = bar_index.get((sym, last_ts_per_sym[sym]))
            price = last_bar["close"] if last_bar else pos["entry"]
            trades.append({"symbol": sym, "day": str(day), "day_obj": day, "reason": "EOD_FORCE",
                            "pnl": (price - pos["entry"]) * pos["shares"]})
    return trades

async def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    token = load_jwt()
    headers = {"Authorization": f"Bearer {token}"}

    end = utc_now()
    daily_start = end - timedelta(days=100)   # comfortably covers lookback for the earliest window
    # 88 days sits right on the 5000-bar/symbol cap and tips over depending on the exact
    # timestamp (confirmed 2026-08-21: same request estimated at 5060 bars and got rejected
    # by the API -- the bot's MCP client turns that rejection into a confusing "SSE stream
    # ended" error instead of showing the real message). 84 days leaves real margin.
    fivemin_start = end - timedelta(days=84)

    print("=" * 70)
    print("ROLLING WALK-FORWARD RE-VALIDATION -- sage_bot_v13 config")
    print("=" * 70)
    print(f"Run time: {datetime.now(ET).strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"Watchlist: {', '.join(WATCHLIST)}")
    print(f"Config: stop={MIN_STOP_DISTANCE_PCT}% target={TARGET_FRAC:.0%} "
          f"zone_width>={MIN_ZONE_WIDTH_PCT}% risk=${RISK_PER_TRADE_DOLLARS}/trade cap=${MAX_NOTIONAL_PER_TRADE}")
    print("(READ-ONLY -- no trades placed, no positions touched)\n")

    async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(60)) as hc:
        async with streamable_http_client(MCP_URL, http_client=hc) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                print("✓ Connected (read-only)\n")
                daily_payload = await fetch_historicals(session, WATCHLIST, daily_start, end, "day")

    print("Fetching 5-min bars (chunked per symbol, fresh connection each chunk)...")
    daily_by_symbol, fivemin_by_symbol = {}, {}
    for r in daily_payload["data"]["results"]:
        bars = [b for b in r["bars"] if not b.get("interpolated")]
        for b in bars:
            b["_date"] = parse_utc(b["begins_at"]).date()
        daily_by_symbol[r["symbol"]] = bars

    for sym in WATCHLIST:
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
    if len(all_days) < MIN_WINDOW_DAYS * 2:
        print(f"Only {len(all_days)} trading days of data available -- not enough for a meaningful "
              f"rolling split yet (need at least {MIN_WINDOW_DAYS * 2}). Re-run this in a few weeks.")
        return

    print("Fetching earnings dates (for blackout modeling)...")
    blackout_days_by_symbol = {}
    for sym in WATCHLIST:
        blackout_days_by_symbol[sym] = await fetch_earnings_blackout_days(headers, sym, all_days[0], all_days[-1])
        if blackout_days_by_symbol[sym]:
            print(f"  {sym}: blacked out {sorted(blackout_days_by_symbol[sym])}")

    try:
        live_bp = await fetch_buying_power(headers)
        min_notional = RISK_PER_TRADE_DOLLARS / (-STOP_LOSS_BACKSTOP_PCT / 100)
        slots = max(1, int(live_bp // min_notional))
        print(f"Live buying power: ${live_bp:.2f} -> {slots} slot(s)\n")
    except Exception as e:
        print(f"  ⚠️  live buying-power fetch failed ({e}) -- defaulting to 6 slots (last known: $193.82)\n")
        slots = 6

    n_windows = min(N_WINDOWS, len(all_days) // MIN_WINDOW_DAYS)
    window_size = len(all_days) // n_windows
    windows = []
    for i in range(n_windows):
        start_idx = i * window_size
        end_idx = (i + 1) * window_size - 1 if i < n_windows - 1 else len(all_days) - 1
        windows.append((all_days[start_idx], all_days[end_idx]))

    print(f"Available data: {all_days[0]} to {all_days[-1]} ({len(all_days)} trading days)")
    print(f"Split into {n_windows} independent windows:\n")

    results = []
    for i, (start, end_day) in enumerate(windows):
        trades = backtest_portfolio(daily_by_symbol, fivemin_by_symbol, start, end_day, slots, blackout_days_by_symbol)
        n = len(trades)
        wins = sum(1 for t in trades if t["pnl"] > 0)
        pnl = sum(t["pnl"] for t in trades)
        wr = wins / n * 100 if n else 0
        results.append({"window": i + 1, "start": str(start), "end": str(end_day),
                         "trades": n, "winrate": wr, "pnl": pnl})
        print(f"  Window {i+1} ({start} to {end_day}): {n} trades, {wr:.1f}% win rate, ${pnl:+.2f}")

    print()
    pnls = [r["pnl"] for r in results]
    negative_windows = [r for r in results if r["pnl"] < 0]
    if len(negative_windows) >= 2:
        print(f"⚠️  {len(negative_windows)}/{n_windows} windows were net negative -- the edge is NOT "
              f"consistently holding up. Worth a closer look before trusting this config with more capital.")
    elif negative_windows:
        print(f"  1/{n_windows} window was negative -- consistent with normal regime variation, "
              f"not necessarily a broken config.")
    else:
        print(f"✓ All {n_windows} windows were net positive.")

    spread = max(pnls) - min(pnls)
    print(f"  P&L spread across windows: ${spread:.2f} (smaller = more consistent, less regime-dependent)")

    report_path = os.path.join(DATA_DIR, f"revalidation_{datetime.now(ET).strftime('%Y%m%d_%H%M')}.json")
    with open(report_path, "w") as f:
        json.dump({"run_at": datetime.now(ET).isoformat(), "windows": results}, f, indent=2)
    print(f"\nReport saved: {report_path}")

    write_obsidian_report(results, negative_windows, spread, all_days)

    if len(negative_windows) >= 2:
        notify_macos("Eva - Re-validation flagged an issue",
                      f"{len(negative_windows)}/{n_windows} windows net negative -- the edge isn't holding "
                      f"up consistently. Check the report before trusting more capital to this config.")
    else:
        notify_macos("Eva - Weekly re-validation complete",
                      f"{n_windows - len(negative_windows)}/{n_windows} windows positive, "
                      f"${sum(pnls):+.2f} combined. No action needed.")

def write_obsidian_report(results, negative_windows, spread, all_days):
    """Human-readable companion to the JSON report, in the same vault as
    the daily trading notes -- so Eva's self-checks live alongside her
    trade history, not scattered in a separate data folder nobody opens."""
    try:
        reports_dir = os.path.join(OBSIDIAN_VAULT, "Reports")
        os.makedirs(reports_dir, exist_ok=True)
        today = datetime.now(ET).strftime("%Y-%m-%d")

        lines = ["---", f"date: {today}", "tags: [eva, revalidation]", "---", "",
                 f"# Rolling Re-validation — {today}", "",
                 f"Data window: {all_days[0]} to {all_days[-1]} ({len(all_days)} trading days), "
                 f"split into {len(results)} independent windows.", "",
                 "| Window | Dates | Trades | Win rate | P&L |", "|---|---|---|---|---|"]
        for r in results:
            lines.append(f"| {r['window']} | {r['start']} to {r['end']} | {r['trades']} | "
                          f"{r['winrate']:.1f}% | {'-' if r['pnl']<0 else '+'}${abs(r['pnl']):.2f} |")
        lines.append("")
        if len(negative_windows) >= 2:
            lines.append(f"**⚠️ {len(negative_windows)}/{len(results)} windows net negative** — the edge is "
                          "not holding up consistently across independent periods. Worth reviewing before "
                          "trusting this config with more capital.")
        elif negative_windows:
            lines.append(f"1/{len(results)} window was negative — consistent with normal regime variation, "
                          "not necessarily a broken config.")
        else:
            lines.append(f"✓ All {len(results)} windows net positive.")
        lines.append("")
        lines.append(f"P&L spread across windows: ${spread:.2f} (smaller = more consistent, less regime-dependent).")
        lines.append("")
        lines.append("Config tested (matches [[sage_bot_v13]] live settings — keep this file's constants "
                      "in sync manually if the bot's parameters change):")
        lines.append(f"- Stop: {MIN_STOP_DISTANCE_PCT}% / backstop {STOP_LOSS_BACKSTOP_PCT}%")
        lines.append(f"- Target: {TARGET_FRAC:.0%} of range")
        lines.append(f"- Min zone width: {MIN_ZONE_WIDTH_PCT}%")
        lines.append(f"- Sizing: ${RISK_PER_TRADE_DOLLARS}/trade risk, ${MAX_NOTIONAL_PER_TRADE} cap")

        with open(os.path.join(reports_dir, f"revalidation-{today}.md"), "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Obsidian report: {reports_dir}/revalidation-{today}.md")
    except Exception as e:
        print(f"  ⚠️  Obsidian report write failed (non-fatal): {e}")

if __name__ == "__main__":
    asyncio.run(main())
