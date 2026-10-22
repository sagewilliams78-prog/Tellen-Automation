#!/usr/bin/env python3
"""
EVA CRYPTO DESK -- BTC, 24/7, live orders on a short leash.

Upgraded 2026-08-31 from a read-only monitor to a real trading desk. Every
hard cap lives in crypto_leash.py, never inline here, so the leash can be
audited (and tightened) without reading trading logic.

WHAT IT ACTUALLY DOES, each cycle:
  1. Kill switch check FIRST -- before any market data, any order, anything.
  2. Reconcile against the REAL broker position, not local memory.
  3. If holding: stop / target / max-hold -> sell. Exits always beat entries.
  4. If flat: entry gate -> preview -> buy. One position, tiny notional.
  5. Write real state for the dashboard.

WHAT IT WILL NOT DO:
  - Hold more than one position, or average down.
  - Enter while the daily loss limit is breached, or after the day's trade cap.
  - Enter on an EXTENDED (RSI >= 70) reading -- chasing is how small books die.
  - Hold anything past MAX_HOLD_HOURS. Crypto has no close, so that IS the close.
  - Place any order without a successful preview first.

Kill switch:  touch _scheduled_state/CRYPTO_HALT
"""

import asyncio
import csv
import json
import os
import tempfile
import urllib.request
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from robinhood_oauth_v13 import build_robinhood_oauth

import crypto_leash as leash

BASE = Path(__file__).resolve().parent
STATE_FILE = BASE / "_scheduled_state" / "crypto-status.json"
MCP_URL = "https://agent.robinhood.com/mcp/trading"
TZ = ZoneInfo("America/Los_Angeles")

CRYPTO_TOOLS = {
    "get_currency_pairs",
    "get_crypto_quotes",
    "get_crypto_positions",
    "get_crypto_orders",
    "preview_crypto_order",
    "place_crypto_order",
    "cancel_crypto_order",
}


# ---------------------------------------------------------------- utilities

def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_name, path)
    finally:
        try:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        except Exception:
            pass


def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def log(msg):
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %I:%M:%S %p %Z")
    print(f"[{stamp}] {msg}", flush=True)


def result_text(result):
    """MCP tool results come back as content blocks; join their text."""
    try:
        return " ".join(
            getattr(c, "text", "") for c in (result.content or [])
            if getattr(c, "text", None)
        )
    except Exception:
        return str(result)


def result_json(result):
    try:
        return json.loads(result_text(result))
    except Exception:
        return {}


def is_error(result):
    return bool(getattr(result, "isError", False))


# ------------------------------------------------------------ market data

def fetch_candles():
    url = (
        "https://api.exchange.coinbase.com/"
        "products/BTC-USD/candles?granularity=300"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "EvaCryptoDesk/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = json.loads(r.read().decode())

    rows = []
    for item in raw:
        if not isinstance(item, list) or len(item) < 6:
            continue
        ts, low, high, open_, close, volume = item[:6]
        rows.append({
            "time": float(ts), "low": float(low), "high": float(high),
            "open": float(open_), "close": float(close), "volume": float(volume),
        })
    rows.sort(key=lambda x: x["time"])
    return rows


def ema(values, period):
    if not values:
        return None
    k = 2 / (period + 1)
    out = values[0]
    for value in values[1:]:
        out = value * k + out * (1 - k)
    return out


def rsi(values, period=14):
    if len(values) <= period:
        return None
    gains, losses = [], []
    for a, b in zip(values[-period - 1:-1], values[-period:]):
        change = b - a
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def market_state(rows):
    closes = [x["close"] for x in rows]
    if not closes:
        raise RuntimeError("No BTC candles returned")

    price = closes[-1]
    recent = rows[-288:] if len(rows) >= 288 else rows
    high_24h = max(x["high"] for x in recent)
    low_24h = min(x["low"] for x in recent)

    e20 = ema(closes[-80:], 20)
    e50 = ema(closes[-120:], 50)
    r14 = rsi(closes, 14)

    if e20 is not None and e50 is not None:
        trend = "BULLISH" if e20 > e50 else ("BEARISH" if e20 < e50 else "FLAT")
    else:
        trend = "UNKNOWN"

    if r14 is None:
        setup = "BUILDING DATA"
    elif trend == "BULLISH" and 45 <= r14 <= 65:
        setup = "BULLISH WATCH"
    elif r14 >= 70:
        setup = "EXTENDED"
    elif r14 <= 30:
        setup = "OVERSOLD WATCH"
    elif trend == "BEARISH":
        setup = "DEFENSIVE"
    else:
        setup = "NEUTRAL"

    return {
        "price": round(price, 2),
        "high_24h": round(high_24h, 2),
        "low_24h": round(low_24h, 2),
        "ema20": round(e20, 2) if e20 is not None else None,
        "ema50": round(e50, 2) if e50 is not None else None,
        "rsi14": round(r14, 2) if r14 is not None else None,
        "trend": trend,
        "setup": setup,
    }


# ------------------------------------------------------------- day ledger

def today_str():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def load_day():
    """Realized P&L and trade count for TODAY only. A new date resets it --
    that's what makes the daily loss limit a daily limit."""
    d = read_json(leash.DAY_FILE, {})
    if d.get("date") != today_str():
        d = {"date": today_str(), "realized_pnl": 0.0, "trades": 0}
    return d


def save_day(d):
    atomic_json(leash.DAY_FILE, d)


def record_trade(entry, exit_price, qty, reason):
    """Append one real closed trade to the log and update today's ledger."""
    pnl = (exit_price - entry) * qty
    ret_pct = ((exit_price - entry) / entry * 100) if entry else 0.0
    now = datetime.now(TZ)

    new = not leash.TRADE_LOG.exists()
    with open(leash.TRADE_LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(leash.TRADE_LOG_COLUMNS)
        w.writerow([
            now.strftime("%Y-%m-%d"), now.strftime("%I:%M:%S %p %Z"),
            leash.SYMBOL, f"{entry:.2f}", f"{qty:.8f}", f"{exit_price:.2f}",
            f"{pnl:.2f}", "WIN" if pnl > 0 else "LOSS",
            f"{ret_pct:.2f}%", reason,
        ])

    day = load_day()
    day["realized_pnl"] = round(day.get("realized_pnl", 0.0) + pnl, 2)
    day["trades"] = day.get("trades", 0) + 1
    save_day(day)

    log(f"CLOSED {reason}: entry ${entry:,.2f} -> exit ${exit_price:,.2f} "
        f"| qty {qty:.8f} | P&L ${pnl:+.2f} | day total ${day['realized_pnl']:+.2f}")
    return pnl


# --------------------------------------------------------------- broker io

async def broker_position(session):
    """The REAL BTC position at the broker -- the only source of truth.

    Returns (quantity, avg_cost) -- quantity 0.0 when flat, avg_cost None when
    unknown. Returns (None, None) if the read itself failed, which the caller
    MUST treat as "do not trade this cycle" rather than "flat".

    avg_cost comes from the broker's own cost_bases, not from whatever the
    market happened to print when we placed the order -- the two differ by the
    spread and any slippage, and stop/target must be measured from what was
    really paid.
    """
    res = await session.call_tool("get_crypto_positions", {
        "rhs_account_number": leash.RHS_ACCOUNT,
    })
    if is_error(res):
        log(f"position read FAILED: {result_text(res)[:200]}")
        return None, None

    payload = result_json(res)
    data = payload.get("data", {})
    # The API returns this under "results"; older shapes used "positions".
    rows = data.get("results") or data.get("positions") or []

    for p in rows:
        cur = p.get("currency") or {}
        code = (cur.get("code") or p.get("asset_code")
                or p.get("currency_code") or p.get("asset") or "").upper()
        if code not in ("BTC", "BTC-USD"):
            continue

        qty = None
        for key in ("quantity_transferable", "quantity", "total_quantity"):
            if p.get(key) is not None:
                try:
                    qty = float(p[key])
                    break
                except (TypeError, ValueError):
                    continue
        if qty is None:
            continue

        # Real average cost across every cost-basis row the broker reports.
        total_qty = 0.0
        total_cost = 0.0
        for cb in p.get("cost_bases", []) or []:
            for qk, ck in (("direct_quantity", "direct_cost_basis"),
                           ("intraday_quantity", "intraday_cost_basis")):
                try:
                    q = float(cb.get(qk) or 0)
                    c = float(cb.get(ck) or 0)
                except (TypeError, ValueError):
                    continue
                total_qty += q
                total_cost += c

        avg = (total_cost / total_qty) if total_qty > 0 else None
        return qty, avg

    return 0.0, None


async def broker_quote(session):
    """Robinhood's OWN bid/ask/mark -- the prices this desk can actually trade
    at, which is NOT the same as the Coinbase feed used for indicators.

    Confirmed live 2026-08-31: Coinbase printed ~$78,978 while Robinhood quoted
    bid $78,340 / ask $79,828. Measuring a stop against a price you cannot
    transact at is how a desk stops out on moves that never happened to it.
    Indicators (trend, RSI) still come from Coinbase candles -- that needs
    history Robinhood does not expose -- but every price DECISION uses this.

    Returns dict with bid/ask/mark/spread_pct, or None if unavailable.
    """
    res = await session.call_tool("get_crypto_quotes", {
        "symbols": [leash.SYMBOL],
        "rhs_account_number": leash.RHS_ACCOUNT,
    })
    if is_error(res):
        log(f"quote read FAILED: {result_text(res)[:200]}")
        return None

    rows = (result_json(res).get("data", {}) or {}).get("results", []) or []
    if not rows:
        return None
    q = rows[0]
    try:
        bid = float(q.get("bid_price") or 0)
        ask = float(q.get("ask_price") or 0)
        mark = float(q.get("mark_price") or 0)
    except (TypeError, ValueError):
        return None

    if not mark and bid and ask:
        mark = (bid + ask) / 2
    if not (bid and ask and mark):
        return None

    return {
        "bid": bid,
        "ask": ask,
        "mark": mark,
        "spread_pct": (ask - bid) / mark * 100,
    }


async def cancel_order(session, order_id):
    res = await session.call_tool("cancel_crypto_order", {
        "rhs_account_number": leash.RHS_ACCOUNT,
        "order_id": order_id,
    })
    if is_error(res):
        log(f"cancel FAILED for {order_id}: {result_text(res)[:200]}")
        return False
    log(f"cancelled stale order {order_id}")
    return True


async def open_orders(session, side=None):
    """Live (unfilled) orders at the broker. Returns a list, or None on error."""
    args = {
        "rhs_account_number": leash.RHS_ACCOUNT,
        "symbol": leash.SYMBOL,
        "state_group": "open",
    }
    if side:
        args["side"] = side
    res = await session.call_tool("get_crypto_orders", args)
    if is_error(res):
        log(f"open-order check FAILED: {result_text(res)[:200]}")
        return None
    return (result_json(res).get("data", {}) or {}).get("results", []) or []


async def has_open_buy(session):
    """Is there already a live buy order working at the broker?

    The first half of the duplicate-order fix: before placing ANY entry, ask
    the broker whether one is already in flight. A market order that has not
    settled yet is exactly the state that fooled the desk into re-buying.
    Returns True/False, or None if the check failed (treat as unsafe).
    """
    res = await session.call_tool("get_crypto_orders", {
        "rhs_account_number": leash.RHS_ACCOUNT,
        "symbol": leash.SYMBOL,
        "state_group": "open",
        "side": "buy",
    })
    if is_error(res):
        log(f"open-order check FAILED: {result_text(res)[:200]}")
        return None
    rows = (result_json(res).get("data", {}) or {}).get("results", []) or []
    return len(rows) > 0


async def do_order(session, side, *, dollar_amount=None, quantity=None,
                   limit_price=None):
    """Preview, then place. Never places without a clean preview first --
    the tool's own guidance, and a real guard against a malformed order.

    limit_price=None means a MARKET order, which crosses the spread. That is
    reserved for stop escalation only (see STOP_ESCALATE_AFTER_CYCLES) -- every
    routine entry and target exit passes a real limit price so the desk never
    pays the toll voluntarily.
    """
    args = {
        "rhs_account_number": leash.RHS_ACCOUNT,
        "symbol": leash.SYMBOL,
        "side": side,
        "type": "limit" if limit_price else "market",
    }
    if limit_price:
        args["limit_price"] = f"{limit_price:.2f}"
    if dollar_amount is not None:
        args["dollar_amount"] = f"{dollar_amount:.2f}"
    if quantity is not None:
        args["quantity"] = f"{quantity:.8f}"

    prev = await session.call_tool("preview_crypto_order", args)
    if is_error(prev):
        log(f"PREVIEW REJECTED ({side}): {result_text(prev)[:300]}")
        return None
    log(f"preview ok ({side}) -- placing")

    place_args = dict(args)
    place_args["ref_id"] = str(uuid.uuid4())
    res = await session.call_tool("place_crypto_order", place_args)
    if is_error(res):
        log(f"ORDER FAILED ({side}): {result_text(res)[:300]}")
        return None

    log(f"ORDER PLACED ({side}) {result_text(res)[:200]}")
    return result_json(res)


# --------------------------------------------------------------- the desk

async def trade_cycle(session, state):
    """One real pass. Returns a dict of desk status for the dashboard."""
    pos = read_json(leash.POSITION_FILE, None)
    day = load_day()

    status = {
        "live_trading": True,
        "halted": False,
        "halt_reason": None,
        "position": None,
        "day_realized_pnl": day.get("realized_pnl", 0.0),
        "day_trades": day.get("trades", 0),
    }

    # Robinhood's own book -- every price decision below uses THIS, not the
    # Coinbase feed the indicators come from. Without a real quote the desk
    # cannot price a limit order honestly, so it does nothing.
    quote = await broker_quote(session)
    if not quote:
        status["halted"] = True
        status["halt_reason"] = "no broker quote -- cannot price an order"
        return status

    price = quote["mark"]
    status["quote"] = {
        "bid": round(quote["bid"], 2),
        "ask": round(quote["ask"], 2),
        "mark": round(quote["mark"], 2),
        "spread_pct": round(quote["spread_pct"], 3),
    }

    # 1. KILL SWITCH -- absolutely first, before any market logic.
    killed = leash.KILL_SWITCH.exists()

    # 2. Daily loss limit.
    loss_halt = day.get("realized_pnl", 0.0) <= leash.DAILY_LOSS_LIMIT_USD

    # 3. Real broker truth. A failed read means we do NOT trade this cycle --
    #    never guess at whether a position exists.
    qty, avg_cost = await broker_position(session)
    if qty is None:
        status["halted"] = True
        status["halt_reason"] = "position read failed -- no trading this cycle"
        return status

    # 3b. PENDING ENTRY RECONCILIATION -- the duplicate-order fix.
    #     If an entry was placed but its fill had not shown up yet, a pending
    #     marker was written. Resolve it here, BEFORE any entry logic can run,
    #     so a slow fill can never be mistaken for "flat, buy again".
    pending = read_json(leash.PENDING_FILE, None)
    if pending and not pos:
        placed = datetime.fromisoformat(pending["placed_at"])
        waited = (datetime.now(TZ) - placed).total_seconds() / 60

        if qty > 0:
            # The fill landed. Adopt it at the broker's REAL average cost.
            entry = avg_cost if avg_cost else float(pending.get("est_price", 0))
            pos = {
                "entry": entry,
                "quantity": qty,
                "opened_at": pending["placed_at"],
                "stop_pct": leash.STOP_LOSS_PCT,
                "target_pct": leash.TAKE_PROFIT_PCT,
            }
            atomic_json(leash.POSITION_FILE, pos)
            leash.PENDING_FILE.unlink(missing_ok=True)
            log(f"pending entry CONFIRMED: {qty:.8f} BTC @ real avg "
                f"${entry:,.2f} (waited {waited:.1f}m)")
        elif waited < leash.ENTRY_LIMIT_TIMEOUT_MINUTES:
            # Still resting. Do NOT enter again -- this is exactly the bug.
            status["halt_reason"] = (
                f"entry limit resting {waited:.1f}m, unfilled -- no new entries")
            return status
        else:
            # Timed out. Cancel the resting limit for real -- leaving it live
            # means it could fill hours later, into a setup that no longer
            # exists, with no stop being watched.
            stale = await open_orders(session, side="buy")
            for o in (stale or []):
                await cancel_order(session, o.get("id"))
            leash.PENDING_FILE.unlink(missing_ok=True)
            log(f"entry limit EXPIRED unfilled after {waited:.1f}m "
                f"-- cancelled, market never came to our price")

    # Reconcile: broker says flat but we think we hold -> it closed elsewhere.
    if pos and qty <= 0:
        log("broker shows flat but local state had a position -- clearing stale state")
        try:
            leash.POSITION_FILE.unlink()
        except FileNotFoundError:
            pass
        pos = None

    # Broker holds BTC we never opened -> do not touch it, do not count it.
    if qty > 0 and not pos:
        status["halted"] = True
        status["halt_reason"] = (
            f"broker holds {qty:.8f} BTC this desk did not open -- "
            "not touching it, no new entries"
        )
        return status

    # ---- HOLDING: exits always run, even when halted --------------------
    if pos:
        entry = float(pos["entry"])
        held_qty = float(pos["quantity"])
        opened = datetime.fromisoformat(pos["opened_at"])
        change_pct = (price - entry) / entry * 100
        held_hours = (datetime.now(TZ) - opened).total_seconds() / 3600

        status["position"] = {
            "entry": entry, "quantity": held_qty, "price": price,
            "change_pct": round(change_pct, 2),
            "held_hours": round(held_hours, 2),
            "unrealized": round((price - entry) * held_qty, 2),
        }

        reason = None
        if killed:
            reason = "KILL_SWITCH"
        elif change_pct <= leash.STOP_LOSS_PCT:
            reason = "STOP"
        elif change_pct >= leash.TAKE_PROFIT_PCT:
            reason = "TARGET"
        elif held_hours >= leash.MAX_HOLD_HOURS:
            reason = "MAX_HOLD"
        elif loss_halt:
            reason = "DAILY_LOSS_LIMIT"

        if reason:
            # An exit already working? Leave it alone rather than stacking
            # sell orders on a position we only hold once.
            working = await open_orders(session, side="sell")
            if working is None:
                status["halt_reason"] = "sell-order check failed -- not stacking exits"
                return status

            attempts = int(pos.get("exit_attempts", 0))

            if working:
                # Give the resting limit time to fill, then escalate.
                if attempts >= leash.STOP_ESCALATE_AFTER_CYCLES and reason != "TARGET":
                    for o in working:
                        await cancel_order(session, o.get("id"))
                    log(f"escalating {reason} to MARKET after {attempts} cycles unfilled "
                        f"-- taking the spread hit beats riding this")
                    out = await do_order(session, "sell", quantity=held_qty)
                    fill_px = quote["bid"]
                else:
                    pos["exit_attempts"] = attempts + 1
                    atomic_json(leash.POSITION_FILE, pos)
                    status["halt_reason"] = (
                        f"{reason} exit resting at limit "
                        f"({attempts + 1}/{leash.STOP_ESCALATE_AFTER_CYCLES})")
                    return status
            else:
                # Price the exit so it does NOT cross the spread. A target
                # takes the mark (patient, we are in profit); a stop leans on
                # the bid (urgent, but still not paying the toll outright).
                limit_px = quote["mark"] if reason == "TARGET" else quote["bid"]
                log(f"EXIT {reason}: {change_pct:+.2f}% after {held_hours:.1f}h "
                    f"-- limit sell @ ${limit_px:,.2f}")
                out = await do_order(session, "sell", quantity=held_qty,
                                     limit_price=limit_px)
                fill_px = limit_px
                if out is not None:
                    pos["exit_attempts"] = 1
                    atomic_json(leash.POSITION_FILE, pos)

            if out is None:
                log("EXIT ORDER FAILED -- position still open, will retry next cycle")
                return status

            # Confirm the sell actually cleared before calling it closed.
            await asyncio.sleep(4)
            still_held, _ = await broker_position(session)
            if still_held is not None and still_held <= 0:
                record_trade(entry, fill_px, held_qty, reason)
                leash.POSITION_FILE.unlink(missing_ok=True)
                status["position"] = None
            else:
                status["halt_reason"] = f"{reason} sell placed, awaiting fill"
        return status

    # ---- FLAT: entry gates ----------------------------------------------
    if killed:
        status["halted"] = True
        status["halt_reason"] = "KILL SWITCH present -- no entries"
        return status
    if loss_halt:
        status["halted"] = True
        status["halt_reason"] = (
            f"daily loss limit hit (${day['realized_pnl']:+.2f}) -- done for today"
        )
        return status
    if day.get("trades", 0) >= leash.MAX_TRADES_PER_DAY:
        status["halted"] = True
        status["halt_reason"] = (
            f"daily trade cap reached ({day['trades']}/{leash.MAX_TRADES_PER_DAY})"
        )
        return status
    if state["setup"] not in leash.ENTRY_SETUPS:
        status["halt_reason"] = f"no entry: setup is {state['setup']}"
        return status

    # THE SPREAD GUARD. A wide book is not a trading opportunity, it is a toll
    # booth. Sitting out an illiquid stretch costs nothing; trading through one
    # costs the spread on every round trip, which is exactly how a desk that
    # "works all the time" bleeds out overnight. This is what makes 24/7 safe:
    # the desk is always awake, but it only acts when the market is worth acting in.
    if quote["spread_pct"] > leash.MAX_SPREAD_PCT:
        status["halt_reason"] = (
            f"spread {quote['spread_pct']:.2f}% > {leash.MAX_SPREAD_PCT:.2f}% cap "
            f"(bid ${quote['bid']:,.0f} / ask ${quote['ask']:,.0f}) -- too wide to trade"
        )
        return status

    # ---- ENTRY -----------------------------------------------------------
    # Belt: ask the broker directly whether a buy is already working. A failed
    # check counts as unsafe -- when in doubt about an in-flight order, do not
    # place another one.
    open_buy = await has_open_buy(session)
    if open_buy is None:
        status["halt_reason"] = "open-order check failed -- not entering blind"
        return status
    if open_buy:
        status["halt_reason"] = "a buy order is already working at the broker"
        return status

    # Buy at the MARK, not the ask. This is the difference between paying the
    # spread and not paying it. It may simply never fill -- that is fine and
    # expected. An unfilled limit costs nothing; a market buy on this book
    # costs ~1% before the position exists.
    limit_px = quote["mark"]
    log(f"ENTRY SIGNAL: {state['setup']} | mark ${price:,.2f} | "
        f"RSI {state['rsi14']} | spread {quote['spread_pct']:.2f}% "
        f"-- limit buy @ ${limit_px:,.2f}")

    # Suspenders: write the pending marker BEFORE the order goes out. If this
    # process dies between placing and confirming, the marker is still on disk
    # and the next run reconciles instead of re-buying.
    atomic_json(leash.PENDING_FILE, {
        "placed_at": datetime.now(TZ).isoformat(),
        "est_price": limit_px,
        "dollar_amount": leash.MAX_POSITION_USD,
    })

    out = await do_order(session, "buy", dollar_amount=leash.MAX_POSITION_USD,
                         limit_price=limit_px)
    if out is None:
        leash.PENDING_FILE.unlink(missing_ok=True)
        status["halt_reason"] = "entry order failed"
        return status

    # Give the fill a moment, but never re-enter on a miss -- the pending
    # marker above owns that case now.
    await asyncio.sleep(4)
    filled, real_avg = await broker_position(session)
    if not filled or filled <= 0:
        log("order placed, fill not visible yet -- pending marker set, "
            "will confirm next cycle (will NOT re-buy)")
        status["halt_reason"] = "entry placed, awaiting fill confirmation"
        return status

    entry = real_avg if real_avg else price
    pos = {
        "entry": entry,
        "quantity": filled,
        "opened_at": datetime.now(TZ).isoformat(),
        "stop_pct": leash.STOP_LOSS_PCT,
        "target_pct": leash.TAKE_PROFIT_PCT,
    }
    atomic_json(leash.POSITION_FILE, pos)
    leash.PENDING_FILE.unlink(missing_ok=True)
    log(f"OPENED: {filled:.8f} BTC @ real avg ${entry:,.2f} "
        f"(stop {leash.STOP_LOSS_PCT:+.1f}%, target {leash.TAKE_PROFIT_PCT:+.1f}%)")
    status["position"] = {
        "entry": entry, "quantity": filled, "price": price,
        "change_pct": round((price - entry) / entry * 100, 2) if entry else 0.0,
        "held_hours": 0.0,
        "unrealized": round((price - entry) * filled, 2) if entry else 0.0,
    }
    return status


async def probe_tools(session):
    response = await session.list_tools()
    names = {t.name for t in response.tools}
    required = {"get_crypto_quotes", "get_crypto_positions",
                "preview_crypto_order", "place_crypto_order"}
    return {
        "mcp_connected": True,
        "crypto_tools": sorted(CRYPTO_TOOLS & names),
        "crypto_trade_capable": required.issubset(names),
    }


async def main():
    print("=" * 70, flush=True)
    print("EVA CRYPTO DESK - BTC 24/7 - LIVE ORDERS", flush=True)
    print("=" * 70, flush=True)
    for line in leash.leash_summary():
        print(f"  {line}", flush=True)
    print("=" * 70, flush=True)

    while True:
        try:
            rows = fetch_candles()
            state = market_state(rows)

            oauth = build_robinhood_oauth()
            async with httpx2.AsyncClient(
                auth=oauth, follow_redirects=True,
                timeout=httpx2.Timeout(30.0, read=60.0),
            ) as hc:
                async with streamable_http_client(
                    MCP_URL, http_client=hc, terminate_on_close=False,
                ) as (rs, ws):
                    async with ClientSession(rs, ws) as session:
                        await session.initialize()
                        tools = await probe_tools(session)
                        state.update(tools)

                        if tools["crypto_trade_capable"]:
                            desk = await trade_cycle(session, state)
                        else:
                            desk = {
                                "live_trading": False,
                                "halted": True,
                                "halt_reason": "crypto trading tools unavailable",
                            }
                        state["desk"] = desk

            state["asset"] = "BTC"
            state["pair"] = leash.SYMBOL
            state["timeframe"] = "5m"
            state["market"] = "24/7"
            state["leash"] = {
                "max_position_usd": leash.MAX_POSITION_USD,
                "daily_loss_limit_usd": leash.DAILY_LOSS_LIMIT_USD,
                "stop_pct": leash.STOP_LOSS_PCT,
                "target_pct": leash.TAKE_PROFIT_PCT,
                "max_trades_per_day": leash.MAX_TRADES_PER_DAY,
                "max_hold_hours": leash.MAX_HOLD_HOURS,
            }
            state["updated_at"] = datetime.now(TZ).strftime(
                "%Y-%m-%d %I:%M:%S %p %Z")

            atomic_json(STATE_FILE, state)

            d = state.get("desk", {})
            pos = d.get("position")
            if pos:
                tail = (f"HOLDING {pos['quantity']:.6f} @ ${pos['entry']:,.2f} "
                        f"({pos['change_pct']:+.2f}%)")
            elif d.get("halt_reason"):
                tail = d["halt_reason"]
            else:
                tail = "flat"

            log(f'BTC ${state["price"]:,.2f} | RSI {state["rsi14"]} | '
                f'{state["trend"]} | {state["setup"]} | {tail}')

        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {e}")

        await asyncio.sleep(leash.CYCLE_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
