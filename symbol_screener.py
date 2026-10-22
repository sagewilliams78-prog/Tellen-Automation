#!/usr/bin/env python3
"""
Symbol screener + mandatory-backtest gate for sage_bot_v13's watchlist.

Read-only. Same auth as sage_bot, but only ever calls get_equity_historicals
and get_equity_tradability -- no trading, no position/portfolio access.

Why this exists: the user asked for the bot to be able to "trade any stock
it sees fit." Doing that with zero vetting is exactly the mistake BTAI was
-- a symbol that looked fine on paper and quietly lost money for weeks
before anyone checked. This script is the compromise: scan a real universe
of liquid, well-known stocks, apply cheap filters first (price range,
fractional tradability, sane daily range -- same zone-width logic already
proven this session), then run every survivor through the EXACT SAME
backtest engine that caught BTAI and rejected AAPL/META/XLF/XLE, over the
same historical window sage_bot_v13's own parameters were validated on.

Nothing gets added to WATCHLIST automatically. This produces a report of
candidates with real backtested numbers, for a human to decide on --
same "options, not unilateral fixes" rule as everything else this session.

Usage:
    ./symbol_screener.py
"""
import asyncio, json, os, sys, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:
    raise SystemExit("zoneinfo unavailable")

# httpx/mcp are only needed by main()'s own standalone MCP session (which
# depends on the separately-managed ~/.sage_robinhood_auth.json credential --
# retired 2026-08-28, see eva-live-scan/eva-nightly-screener). Deferred into
# main() itself so this module stays import-safe under plain python3 (no
# venv, no httpx/mcp needed) for screener_calc.py, which only reuses the
# pure backtest functions below and never calls main().
MCP_URL = "https://agent.robinhood.com/mcp/trading"
ACCOUNT = "724375969"
OBSIDIAN_VAULT = os.path.expanduser("~/Documents/Eva Trading Journal")

def notify_macos(title, message):
    """Best-effort local notification -- same pattern as sage_bot_v13.py."""
    try:
        script = f'display notification "{message}" with title "{title}" sound name "Glass"'
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
    except Exception as e:
        print(f"  ⚠️  notification failed: {e}")
CURRENT_WATCHLIST = ["IBRX", "IOVA", "NVDA", "TSLA", "AMD", "GDX", "SMCI"]

# Candidate universe: liquid, well-known US equities and sector ETFs across
# a spread of sectors (deliberately NOT just more tech, to avoid stacking
# correlated names on top of the AMD/NVDA/TSLA already on the list).
# This is a curated starting point, not "every US stock" -- scanning the
# entire market isn't practical, and a human should add to this list
# deliberately rather than the screener wandering into penny stocks or
# illiquid names on its own.
CANDIDATE_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",              # already tested: AAPL/META rejected
    "JPM", "BAC", "WFC", "GS",                             # financials
    "XOM", "CVX",                                          # energy
    "UNH", "JNJ", "PFE", "LLY",                            # healthcare
    "WMT", "COST", "HD", "MCD",                            # consumer
    "CAT", "BA", "GE", "HON",                              # industrials
    "XLF", "XLE", "XLV", "XLI", "XLP", "XLU",              # sector ETFs
    "SMCI", "AVGO", "MU", "QCOM",                          # more semis (correlation risk w/ AMD/NVDA -- flagged in report)
    "COIN", "MSTR",                                        # high-vol proxies (flagged as high-risk in report)
]

MIN_STOP_DISTANCE_PCT = -2.5
STOP_LOSS_BACKSTOP_PCT = -4.0
TARGET_FRAC = 0.25
MIN_ZONE_WIDTH_PCT = 3.0
EARNINGS_BLACKOUT_DAYS = 1  # matches sage_bot_v13.py's EARNINGS_BLACKOUT_DAYS
SWING_LOOKBACK_DAYS = 5
RISK_PER_TRADE_DOLLARS = 2.50
MAX_NOTIONAL_PER_TRADE = 150.0
MIN_PRICE, MAX_PRICE = 5.0, 600.0
SEMI_CORRELATED = {"AVGO", "MU", "QCOM", "SMCI"}  # already have AMD+NVDA; flag, don't auto-exclude
HIGH_VOL_PROXY = {"COIN", "MSTR"}  # crypto proxies -- known for gap risk, flag clearly

def utc_now():
    return datetime.now(timezone.utc)

def parse_utc(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def load_jwt():
    return json.loads((Path.home() / ".sage_robinhood_auth.json").read_text())["tokens"]["access_token"]

def _result_text(result):
    try:
        return " ".join(getattr(c, "text", "") for c in (result.content or []) if getattr(c, "text", None))
    except Exception:
        return str(result)

async def call_on_fresh_connection(headers, name, args, attempts=3, base_delay=4):
    """Opens a brand new MCP connection per call and retries on a fresh
    one each time. The 'SSE stream ended without a response' failure seen
    testing this script kills the whole session's task group, not just
    the one request -- reusing that session for a retry doesn't reliably
    work, so this reconnects from scratch instead. The live bot never
    needs this (it never re-uses a session across a failure), but this
    script makes many more historicals calls back-to-back than the bot
    ever does in one run."""
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(120)) as hc:
                async with streamable_http_client(MCP_URL, http_client=hc) as (rs, ws):
                    async with ClientSession(rs, ws) as session:
                        await session.initialize()
                        return await session.call_tool(name, args)
        except Exception as e:
            last_err = e
            print(f"    ⚠️  {name} failed (attempt {attempt}/{attempts}): {e}")
            if attempt < attempts:
                await asyncio.sleep(base_delay * attempt)
    raise last_err

async def fetch_earnings_blackout_days(headers, sym, window_start, window_end):
    """Real historical earnings dates (get_earnings_results, trailing up
    to 8 quarters) turned into the calendar dates that would have been
    blacked out (+/- EARNINGS_BLACKOUT_DAYS) inside the backtest window.
    Added 2026-08-22 -- symbol_screener's own backtest was the last of the
    three companion tools still missing this (rolling_revalidation.py and
    strategy_experiments.py were fixed first). Weekly win-rate pause is
    NOT modeled here on purpose: it's a portfolio-wide signal (all
    WATCHLIST trades combined), and this screener deliberately tests each
    CANDIDATE in isolation, not as part of the live portfolio -- that
    portfolio-level question belongs to strategy_experiments.py, which
    already tested SMCI/COIN additions that way before either went live."""
    try:
        res = await call_on_fresh_connection(headers, "get_earnings_results", {"symbol": sym})
        payload = json.loads(_result_text(res))
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

async def fetch_5min_chunked(headers, sym, start, end, chunk_days=35):
    """Fetch one symbol's 5-min bars in reliable-sized chunks and
    concatenate. Same fix as rolling_revalidation.py: confirmed
    2026-08-21 that a single ~84-day/~4600-bar request for one symbol
    intermittently fails against this script's MCP client even though
    the identical request succeeds through a different client -- a
    client-library limitation handling large SSE responses, not an
    upstream rejection."""
    all_bars = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=chunk_days), end)
        res = await call_on_fresh_connection(headers, "get_equity_historicals", {
            "symbols": [sym],
            "start_time": chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "interval": "5minute", "bounds": "regular"})
        payload = json.loads(_result_text(res))
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

def backtest_symbol(daily_bars, fivemin_bars, blackout_days=None):
    blackout_days = blackout_days or set()
    trades = []
    position = None
    days = {}
    for b in fivemin_bars:
        days.setdefault(b["_et"].date(), []).append(b)
    for day in sorted(days):
        day_bars = days[day]
        lv = levels_for_day(daily_bars, day)
        if lv is None:
            continue
        blacked_out = day in blackout_days
        for i, bar in enumerate(day_bars):
            t = bar["_et"].time()
            price = bar["close"]
            is_last = (i == len(day_bars) - 1)
            in_window = (t.hour > 10 or (t.hour == 10 and t.minute >= 0)) and \
                        (t.hour < 15 or (t.hour == 15 and t.minute < 55))
            if position is not None:
                if bar["low"] <= position["stop"]:
                    trades.append({"pnl": (position["stop"] - position["entry"]) * position["shares"]})
                    position = None
                elif bar["high"] >= position["target"]:
                    trades.append({"pnl": (position["target"] - position["entry"]) * position["shares"]})
                    position = None
                if position is not None and is_last:
                    trades.append({"pnl": (price - position["entry"]) * position["shares"]})
                    position = None
            if position is None and in_window and not is_last and not blacked_out and zone_width_ok(lv):
                if zone_of(price, lv) == "BUY" and bar["low"] <= lv["rl"] and bar["close"] > bar["open"]:
                    entry = price
                    stop = max(lv["sl"], entry * (1 + STOP_LOSS_BACKSTOP_PCT / 100))
                    stop = min(stop, entry * (1 + MIN_STOP_DISTANCE_PCT / 100))
                    target = lv["rl"] + TARGET_FRAC * (lv["rh"] - lv["rl"])
                    if stop < entry and target > entry:
                        risk_per_share = entry - stop
                        notional = min(RISK_PER_TRADE_DOLLARS / risk_per_share * entry, MAX_NOTIONAL_PER_TRADE)
                        shares = notional / entry
                        position = {"entry": entry, "shares": shares, "stop": stop, "target": target}
    return trades

async def main():
    global httpx, ClientSession, streamable_http_client
    try:
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError:
        raise SystemExit("Missing deps -- run with the venv: "
                          "\"robin hood trading bot/.venv/bin/python\" symbol_screener.py")
    token = load_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    end = utc_now()
    daily_start = end - timedelta(days=100)
    # 88 days sits right on the API's 5000-bar/symbol cap and tips over depending on the
    # exact timestamp (confirmed 2026-08-21: same request estimated at 5060 bars and got
    # rejected -- the bot's MCP client turns that rejection into a confusing "SSE stream
    # ended" error instead of the real message). 84 days leaves real margin, still much
    # deeper than the 42-day shortcut that gave a misleading read on COIN/MSTR/SMCI earlier
    # (looked like winners on ~9 trades, proved to be net losers on the full 62-day test).
    fivemin_start = end - timedelta(days=84)

    candidates = [s for s in CANDIDATE_UNIVERSE if s not in CURRENT_WATCHLIST]

    print("=" * 70)
    print("EVA'S SYMBOL SCREENER -- candidates for sage_bot_v13's watchlist")
    print("=" * 70)
    print(f"Universe: {len(candidates)} candidates (current watchlist excluded)")
    print("(READ-ONLY -- no trades placed, nothing added to the live watchlist)\n")

    all_tradability = {}
    daily_by_symbol, fivemin_by_symbol = {}, {}

    async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(120)) as hc:
        async with streamable_http_client(MCP_URL, http_client=hc) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                print("✓ Connected (read-only)\n")

                for i in range(0, len(candidates), 10):  # 10 symbols/call cap for tradability + daily
                    batch = candidates[i:i + 10]
                    trad_res = await session.call_tool("get_equity_tradability", {
                        "account_number": ACCOUNT, "symbols": batch})
                    trad_payload = json.loads(_result_text(trad_res))
                    for r in trad_payload.get("data", {}).get("results", []):
                        all_tradability[r["symbol"]] = r.get("tradeable") is True

                    daily_res = await session.call_tool("get_equity_historicals", {
                        "symbols": batch,
                        "start_time": daily_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "interval": "day", "bounds": "regular"})
                    daily_payload = json.loads(_result_text(daily_res))
                    for r in daily_payload["data"]["results"]:
                        bars = [b for b in r["bars"] if not b.get("interpolated")]
                        for b in bars:
                            b["_date"] = parse_utc(b["begins_at"]).date()
                        daily_by_symbol[r["symbol"]] = bars

    # 5-min bars: chunked per symbol, fresh connection per chunk. Confirmed
    # (2026-08-21) a single ~84-day/~4600-bar request for one symbol
    # intermittently fails against this script's MCP client even though the
    # identical request succeeds through a different client -- a client
    # library limitation handling large SSE responses, not an upstream
    # rejection. Fetching in ~35-day chunks and concatenating avoids it.
    blackout_days_by_symbol = {}
    for sym in candidates:
        print(f"  fetching 5-min bars for {sym}...")
        bars = await fetch_5min_chunked(headers, sym, fivemin_start, end)
        bars = [b for b in bars if not b.get("interpolated")]
        for b in bars:
            utc = parse_utc(b["begins_at"])
            b["_et"] = utc.astimezone(ET)
            b["open"] = float(b["open_price"]); b["close"] = float(b["close_price"])
            b["high"] = float(b["high_price"]); b["low"] = float(b["low_price"])
        fivemin_by_symbol[sym] = bars
        if bars:
            window_start, window_end = bars[0]["_et"].date(), bars[-1]["_et"].date()
            blackout_days_by_symbol[sym] = await fetch_earnings_blackout_days(headers, sym, window_start, window_end)

    print(f"\n{'Symbol':<7} {'Tradable':<9} {'Price OK':<9} {'Trades':<7} {'WinRate':<8} {'P&L':<9} Flags")
    print("-" * 70)
    results = []
    for sym in candidates:
        daily = daily_by_symbol.get(sym, [])
        fivemin = fivemin_by_symbol.get(sym, [])
        tradable = all_tradability.get(sym, False)
        last_price = daily[-1]["close_price"] if daily else None
        price_ok = last_price is not None and MIN_PRICE <= float(last_price) <= MAX_PRICE

        flags = []
        if sym in SEMI_CORRELATED:
            flags.append("correlated-w/AMD-NVDA")
        if sym in HIGH_VOL_PROXY:
            flags.append("high-vol-proxy")

        if not tradable or not price_ok or not fivemin or not daily:
            print(f"{sym:<7} {str(tradable):<9} {str(price_ok):<9} {'--':<7} {'--':<8} {'--':<9} "
                  f"{'skip: not tradable/no data/price out of range'}")
            continue

        trades = backtest_symbol(daily, fivemin, blackout_days_by_symbol.get(sym))
        n = len(trades)
        wins = sum(1 for t in trades if t["pnl"] > 0)
        pnl = sum(t["pnl"] for t in trades)
        wr = wins / n * 100 if n else 0
        results.append({"symbol": sym, "trades": n, "winrate": wr, "pnl": pnl, "flags": flags})
        print(f"{sym:<7} {'Yes':<9} {'Yes':<9} {n:<7} {wr:>6.1f}% {pnl:>+8.2f}  {', '.join(flags)}")

    print()
    passers = [r for r in results if r["pnl"] > 0 and r["trades"] >= 15]
    passers.sort(key=lambda r: r["pnl"], reverse=True)
    if passers:
        print("=== Candidates that passed (positive P&L, enough trades to mean something) ===")
        for r in passers:
            flag_note = f"  [{', '.join(r['flags'])}]" if r["flags"] else ""
            print(f"  {r['symbol']}: {r['trades']} trades, {r['winrate']:.1f}% WR, ${r['pnl']:+.2f}{flag_note}")
        print("\nNone of these are added automatically -- review and decide which, if any, to add to WATCHLIST.")
    else:
        print("No candidates passed. Nothing to recommend adding right now.")

    write_obsidian_report(results, passers)
    write_json_results(results, passers)

    if passers:
        top = passers[0]
        notify_macos("Eva - Screener found candidates",
                      f"{len(passers)} candidate(s) passed backtesting, best: {top['symbol']} "
                      f"(${top['pnl']:+.2f}). Nothing added automatically -- review before deciding.")
    else:
        notify_macos("Eva - Monthly screener complete", "No new candidates passed backtesting this run.")

def write_json_results(results, passers):
    """Machine-readable twin of the Obsidian report.

    The nightly watchlist job needs to read these numbers reliably; parsing
    them back out of a markdown table would be brittle and would break
    silently the first time the report's formatting changed. Written to the
    bot's own _watchlist/ folder rather than the Obsidian vault, since it is
    machine state, not a document for a human to read.
    """
    try:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_watchlist")
        os.makedirs(out_dir, exist_ok=True)
        payload = {
            "generated_at": datetime.now(ET).isoformat(),
            "universe_size": len(results),
            "results": results,
            "passers": passers,
        }
        path = os.path.join(out_dir, "screener-latest.json")
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"JSON results: {path}")
    except Exception as e:
        print(f"  ⚠️  JSON results write failed (non-fatal): {e}")


def write_obsidian_report(results, passers):
    """Human-readable companion to the console output, in the same vault
    as the daily trading notes."""
    try:
        reports_dir = os.path.join(OBSIDIAN_VAULT, "Reports")
        os.makedirs(reports_dir, exist_ok=True)
        today = datetime.now(ET).strftime("%Y-%m-%d")

        lines = ["---", f"date: {today}", "tags: [eva, screener]", "---", "",
                 f"# Symbol Screener — {today}", "",
                 f"Scanned {len(results)} candidates against the current watchlist "
                 f"({', '.join(f'[[{s}]]' for s in CURRENT_WATCHLIST)}).", ""]

        if passers:
            lines.append(f"## Passed ({len(passers)})")
            lines.append("")
            lines.append("| Symbol | Trades | Win rate | P&L | Flags |")
            lines.append("|---|---|---|---|---|")
            for r in passers:
                lines.append(f"| [[{r['symbol']}]] | {r['trades']} | {r['winrate']:.1f}% | "
                              f"{'-' if r['pnl']<0 else '+'}${abs(r['pnl']):.2f} | "
                              f"{', '.join(r['flags']) if r['flags'] else '-'} |")
            lines.append("")
            lines.append("**None of these were added automatically** — review and decide before "
                          "changing the live watchlist in `sage_bot_v13.py`.")
        else:
            lines.append("No candidates passed this run (positive P&L with at least 15 trades). "
                          "Nothing to recommend.")
        lines.append("")
        lines.append("## All results")
        lines.append("")
        lines.append("| Symbol | Trades | Win rate | P&L | Flags |")
        lines.append("|---|---|---|---|---|")
        for r in sorted(results, key=lambda r: r["pnl"], reverse=True):
            lines.append(f"| [[{r['symbol']}]] | {r['trades']} | {r['winrate']:.1f}% | "
                          f"{'-' if r['pnl']<0 else '+'}${abs(r['pnl']):.2f} | "
                          f"{', '.join(r['flags']) if r['flags'] else '-'} |")

        with open(os.path.join(reports_dir, f"screener-{today}.md"), "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Obsidian report: {reports_dir}/screener-{today}.md")
    except Exception as e:
        print(f"  ⚠️  Obsidian report write failed (non-fatal): {e}")

if __name__ == "__main__":
    asyncio.run(main())
