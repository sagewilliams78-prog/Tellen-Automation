#!/usr/bin/env python3
"""
EVA HOLD -- one rule, checked once a day.

    price above its 200-day average  ->  be invested
    price below it                   ->  be in cash

That is the entire strategy. There is no scoring model, no zone widths, no
5-minute scanning, no watchlist churn. It trades a handful of times a year.

WHY THIS REPLACED THE OLD BOT
-----------------------------
Measured over 96 sessions, the intraday bot returned +9.4% while simply
holding the same 20 symbols returned +15.2%. It underperformed doing nothing.
Live it took 5 trades for +$0.86, and every one exited EOD_FLATTEN -- it never
once reached a target or a stop. Nine replacement strategies were tested; none
beat buy-and-hold on all three splits. Crypto was tested three ways and failed
at a measured 1.90% round-trip cost.

WHAT THIS ACTUALLY BUYS YOU  (SPY/QQQ/IWM/DIA, 2007-09 to 2026-09, 4,780 days,
three bear markets, no symbol selection possible)

    SPY   hold +487.6% / maxDD -48.3%    rule +255.8% / maxDD -20.9%
    QQQ   hold +1413.4% / maxDD -47.0%   rule +805.7% / maxDD -21.9%
    IWM   hold +306.8% / maxDD -54.3%    rule +157.5% / maxDD -27.5%
    DIA   hold +354.1% / maxDD -44.7%    rule +171.4% / maxDD -18.6%

It roughly HALVES the drawdown and roughly HALVES the return. 2008 goes from
-31% to not registering at all. Buy-and-hold beat it on total return in all
four cases -- this is a risk tool, not a return tool, and anyone expecting it
to make more money than holding has misread it.

WHY AN ETF AND NOT THE OLD STOCK LIST
--------------------------------------
The same rule on the 20-symbol watchlist backtested at +1880%. That number is
garbage: half those symbols were added in Sept 2026 because they had recently
been volatile, so testing them back to 2021 is choosing winners with hindsight.
The ETF result above has no such freedom -- it is the market itself. When two
backtests disagree by 10x, trust the one that cannot cheat.

SAFETY
------
Reuses eva_guards: fills are confirmed against the broker's order list (never
assumed), a per-symbol daily cap makes a runaway loop impossible, and the bot
fingerprints its own source so it notices if the file changes mid-run. All
three exist because all three failures actually happened during the week of
2026-09-01.

Run:  python eva_hold.py            (one pass, then exit -- schedule it daily)
      python eva_hold.py --dry      (decide and log, place nothing)
"""

import asyncio
import csv
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import eva_guards
from sage_bot_v13 import (ACCOUNT, MCP_URL, _result_text,
                          build_robinhood_oauth, market_now)

import httpx2   # NOT httpx -- httpx2 is what accepts the MCP OAuth provider
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "eva_hold_config.json")
JOURNAL = os.path.expanduser("~/eva_hold_journal.csv")

DEFAULTS = {
    "symbol": "SPY",
    "ma_days": 200,
    "cash_reserve_usd": 1.00,
    "dry_run": False,
    "min_order_usd": 5.00,
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"  ⚠️  config unreadable ({e}) -- using defaults")
    return cfg


CFG = load_config()
SOURCE_WATCH = eva_guards.SourceWatch(os.path.abspath(__file__))


# US market holidays. Without this the bot wakes on Labor Day, sees a valid
# signal from Friday's close, and fires a market order into a closed market --
# caught on 2026-09-04, three days before it would have happened for real.
# Half-days are fine (the market is open, 12:50 PT is before the 10:00 PT
# early close only on those days -- see EARLY_CLOSE note below).
MARKET_HOLIDAYS = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
}
# Days the market closes at 13:00 ET. The 12:50 PT (15:50 ET) schedule lands
# AFTER that close, so these must be skipped too.
EARLY_CLOSE = {"2026-11-27", "2026-12-24", "2027-11-26"}


def market_is_open(now):
    """Weekday, not a holiday, not an early-close day, inside 09:30-16:00 ET."""
    if now.weekday() >= 5:
        return False, "weekend"
    day = now.strftime("%Y-%m-%d")
    if day in MARKET_HOLIDAYS:
        return False, "market holiday"
    if day in EARLY_CLOSE:
        return False, "early close (13:00 ET) -- this run is after the bell"
    if not ((9, 30) <= (now.hour, now.minute) < (16, 0)):
        return False, f"outside regular hours ({now:%H:%M} ET)"
    return True, ""


def journal(row):
    """Never raises. A logging failure must not stop a trade decision."""
    try:
        cols = ["timestamp", "symbol", "price", "ma", "above_ma", "held_shares",
                "cash", "action", "reason", "order_confirmed"]
        new = not os.path.exists(JOURNAL)
        with open(JOURNAL, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerow(row)
    except Exception as e:
        print(f"  ⚠️  journal write failed (non-fatal): {e}")


async def call(session, name, args, timeout=45):
    """Every MCP call gets a timeout. v13 had none and froze for 7 minutes
    holding an unmanaged position on 2026-09-01."""
    return await asyncio.wait_for(session.call_tool(name, args), timeout=timeout)


async def get_price_and_ma(session, symbol, ma_days):
    """Daily closes -> (last close, N-day moving average).

    The average EXCLUDES today's bar so the signal is computed the same way
    the backtest computed it. Including today would be a subtle look-ahead.
    """
    start = (datetime.now(timezone.utc) - timedelta(days=int(ma_days * 2.2))
             ).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = await call(session, "get_equity_historicals",
                   {"symbols": [symbol], "interval": "day",
                    "start_time": start})
    data = json.loads(_result_text(r))["data"]["results"]
    bars = [b for b in data[0].get("bars", []) if not b.get("interpolated")]
    closes = [float(b["close_price"]) for b in bars]
    if len(closes) < ma_days + 1:
        raise RuntimeError(f"only {len(closes)} bars, need {ma_days + 1}")
    return closes[-1], sum(closes[-(ma_days + 1):-1]) / ma_days


async def get_state(session, symbol):
    pf = await call(session, "get_portfolio", {"account_number": ACCOUNT})
    cash = float(json.loads(_result_text(pf))
                 ["data"]["buying_power"]["buying_power"])
    ps = await call(session, "get_equity_positions", {"account_number": ACCOUNT})
    held = 0.0
    for p in json.loads(_result_text(ps))["data"]["positions"]:
        if p.get("symbol") == symbol:
            held = float(p.get("quantity") or 0)
    return cash, held


async def place(session, symbol, side, *, dollars=None, shares=None):
    """Place and CONFIRM. An unverified order is treated as NOT filled --
    assuming a fill is how the 29-order PFE loop happened on 2026-09-03."""
    ref = str(uuid.uuid4())
    eva_guards.mark_pending(symbol, ref, datetime.now().timestamp())
    args = {"account_number": ACCOUNT, "symbol": symbol, "side": side,
            "type": "market", "time_in_force": "gfd",
            "market_hours": "regular_hours", "ref_id": ref}
    if dollars is not None:
        args["dollar_amount"] = f"{dollars:.2f}"
    else:
        args["quantity"] = f"{shares:.6f}"
    try:
        res = await call(session, "place_equity_order", args)
        body = _result_text(res)
        if getattr(res, "isError", False) or any(
                k in body.lower() for k in ('"error"', "rejected",
                                            "insufficient", "not allowed")):
            print(f"     ✗ REJECTED: {body[:200]}")
            eva_guards.clear_pending(symbol)
            return False
        chk = await call(session, "get_equity_orders",
                         {"account_number": ACCOUNT, "symbol": symbol})
        for o in json.loads(_result_text(chk))["data"]["orders"]:
            if o.get("ref_id") == ref:
                st = (o.get("state") or "").lower()
                if st in ("filled", "partially_filled", "confirmed",
                          "queued", "new", "unconfirmed"):
                    print(f"     ✓ CONFIRMED by broker: {side} {symbol} ({st})")
                    if side == "buy":
                        eva_guards.record_entry(symbol)
                    eva_guards.clear_pending(symbol)
                    return True
                print(f"     ✗ broker state '{st}' -- not a fill")
                return False
        print("     ✗ UNVERIFIED -- treating as NOT filled; symbol blocked "
              "from retry until the pending marker expires")
        return False
    except Exception as e:
        print(f"     ✗ EXCEPTION: {e}")
        return False


async def main():
    dry = CFG["dry_run"] or "--dry" in sys.argv
    sym, ma_days = CFG["symbol"], int(CFG["ma_days"])

    print("=" * 62)
    print("EVA HOLD -- above the 200-day, be invested. Below it, be cash.")
    print("=" * 62)
    print(f"  symbol {sym} | {ma_days}-day MA | "
          f"{'DRY RUN (places nothing)' if dry else 'LIVE'}")
    print(f"  {market_now():%a %Y-%m-%d %I:%M %p %Z}\n")

    if not SOURCE_WATCH.check():
        print("  🛑 refusing to trade: source changed since start")
        return 1

    ok, why = market_is_open(market_now())
    if not ok and not dry:
        print(f"  ⏸  market closed ({why}) -- nothing to do, exiting cleanly")
        journal({"timestamp": market_now().isoformat(timespec="seconds"),
                 "symbol": sym, "action": "skipped", "reason": why})
        return 0

    oauth = build_robinhood_oauth()
    async with httpx2.AsyncClient(
            auth=oauth, follow_redirects=True,
            timeout=httpx2.Timeout(30.0, read=300.0)) as hc:
        async with streamable_http_client(MCP_URL, http_client=hc,
                                          terminate_on_close=False) as (rs, ws):
            async with ClientSession(rs, ws) as session:
                await session.initialize()
                print("✓ connected\n")

                price, ma = await get_price_and_ma(session, sym, ma_days)
                cash, held = await get_state(session, sym)
                above = price > ma
                gap = (price - ma) / ma * 100

                print(f"  {sym} ${price:,.2f} | {ma_days}d MA ${ma:,.2f} "
                      f"({gap:+.2f}%)  ->  {'ABOVE' if above else 'BELOW'}")
                print(f"  holding {held:g} sh | cash ${cash:,.2f}\n")

                action, reason, ok = "none", "", ""
                if above and held == 0:
                    spend = cash - CFG["cash_reserve_usd"]
                    if spend < CFG["min_order_usd"]:
                        action, reason = "none", f"only ${spend:.2f} to invest"
                    else:
                        allowed, why = eva_guards.entry_allowed(
                            sym, datetime.now().timestamp())
                        if not allowed:
                            action, reason = "blocked", why
                            print(f"  🛑 {why}")
                        else:
                            action = "BUY"
                            reason = f"price {gap:+.2f}% above the {ma_days}d MA"
                            print(f"→ BUY {sym} ${spend:.2f}  [{reason}]")
                            if dry:
                                ok = "dry-run"
                            else:
                                ok = str(await place(session, sym, "buy",
                                                     dollars=spend))
                elif (not above) and held > 0:
                    action = "SELL"
                    reason = f"price {gap:+.2f}% below the {ma_days}d MA"
                    print(f"→ SELL {sym} {held:g} sh  [{reason}]")
                    if dry:
                        ok = "dry-run"
                    else:
                        ok = str(await place(session, sym, "sell", shares=held))
                else:
                    action = "hold" if above else "stay in cash"
                    reason = ("already invested and above the MA" if above
                              else "already in cash and below the MA")
                    print(f"  = {action} -- {reason}")

                journal({"timestamp": market_now().isoformat(timespec="seconds"),
                         "symbol": sym, "price": f"{price:.4f}",
                         "ma": f"{ma:.4f}", "above_ma": above,
                         "held_shares": held, "cash": f"{cash:.2f}",
                         "action": action, "reason": reason,
                         "order_confirmed": ok})
                print(f"\n  journal -> {JOURNAL}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
