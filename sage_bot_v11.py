#!/usr/bin/env python3
"""
SAGE BOT v11 - MCP LIVE TRADING (RANGE & SWING STRATEGY)

v11 replaces the flat "-2% from today's open" entry signal with the
Range & Swing zone strategy from sage's trading notes:

  RH = yesterday's daily high        SH = highest high, prior 5 sessions
  RL = yesterday's daily low         SL = lowest low, prior 5 sessions

  Buy Zone  = SL -> RL   (lower band, below yesterday's low)
  Kill Zone = RL -> RH   (the middle -- yesterday's range. No trades here.)
  Sell Zone = RH -> SH   (upper band, above yesterday's high)

Entry (BUY only -- this is a cash account, no shorting):
  Price is inside the Buy Zone AND the latest closed 5-minute candle dipped
  into the zone (low <= RL) AND closed bullish (close > open). That candle
  is the "confirmation" the notes call for -- a level by itself isn't an
  entry, you wait for the push down and the bounce.

Exit:
  - Hard stop: price <= stop. Stop is whichever is TIGHTER (closer to
    entry) of SL (the zone's structural low) and a fixed -4% backstop --
    a very wide 5-day range shouldn't be allowed to risk more than the
    backstop. This does not wait for a confirmation candle; a stop is a
    risk limit, not a setup.
  - Zone-confirmed target: price >= target (target = RH, the top of
    yesterday's range) AND the latest closed 5-minute candle is bearish
    (close < open) -- i.e. price reached the Sell Zone and showed the same
    kind of rejection candle the notes require for a sell, so an existing
    long is closed there. (No new short is opened -- cash account.)
  - EOD flatten (15:55 ET) and the daily-loss circuit breaker are
    unconditional, same as v10 -- they do not wait for a confirmation
    candle, because by that point safety matters more than the setup.

Levels (RH/RL/SH/SL) are computed once per symbol at startup from daily
bars -- they don't change intraday. The confirmation candle is refetched
every scan from 5-minute bars. Both come from the Robinhood MCP's
get_equity_historicals, not Finnhub (Finnhub's free tier has no candle
access on this API key -- checked before building this).

Inherits from v10: hard exit on weekends and expired JWT before ever
connecting to the broker, macOS notifications (low token, positions still
open at close, flatten failures, crashes, Ctrl+C), and the KeyboardInterrupt
handler correctly wrapping asyncio.run() (not main()) so it actually fires
on this Python version.

Inherits from v9/v8/v7: JWT bearer auth, isError checking, whole-share
fallback, live buying-power recheck before every order, restart-safe
position rehydration from the broker's average_buy_price, skipping entries
on a stale broker read.
"""
import requests, asyncio, csv, os, json, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---- MARKET TIME ----
# NEVER use datetime.now() for trading decisions. This machine is on Pacific;
# the market runs on Eastern. Using local time shifted the whole window 3 hours
# and made the 3:55pm flatten fire ~3 hours AFTER the close, where market orders
# don't fill -- they queue to the next open and carry overnight unprotected.
try:
    from zoneinfo import ZoneInfo
    MARKET_TZ = ZoneInfo("America/New_York")
except Exception:
    MARKET_TZ = None

def market_now():
    """Current time in US market timezone (handles EST/EDT automatically)."""
    if MARKET_TZ is None:
        raise RuntimeError("zoneinfo unavailable - cannot determine market time")
    return datetime.now(MARKET_TZ)

def utc_now():
    return datetime.now(timezone.utc)

def parse_utc(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

try:
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    MCP_OK = True
except:
    MCP_OK = False

FINNHUB_KEY = "REDACTED -- this old version (superseded by sage_bot_v13.py) had a real key hardcoded here; removed during a security review. Not used by anything live."
WATCHLIST = ["IBRX", "IOVA", "BTAI", "NVDA", "TSLA", "AMD", "GDX"]
ACCOUNT = "724375969"
MCP_URL = "https://agent.robinhood.com/mcp/trading"
AUTH_FILE = Path.home() / ".sage_robinhood_auth.json"
TRADE_LOG = os.path.expanduser("~/trading_log_v9.csv")

MIN_TRADE = 50.0
STOP_LOSS_BACKSTOP_PCT = -4.0   # never risk more than this from entry, even if SL is farther away
MIN_STOP_DISTANCE_PCT = -1.5    # never risk LESS than this either -- backtesting (2026-08-21)
                                 # found entries near the bottom of the Buy Zone put the stop
                                 # (SL) almost on top of entry, so ordinary 5-min noise clipped
                                 # it repeatedly (10 stop-outs on BTAI in one day). Widen any
                                 # stop tighter than this out to this floor.
DAILY_LOSS_LIMIT = -50.0
SWING_LOOKBACK_DAYS = 5          # prior trading sessions used for SH/SL
CONFIRMATION_INTERVAL = "5minute"
TOKEN_WARN_DAYS = 2.0

def notify_macos(title, message):
    """Best-effort local notification -- never let a notification failure
    take down the trading loop."""
    try:
        script = f'display notification "{message}" with title "{title}" sound name "Glass"'
        subprocess.run(["osascript", "-e", script], timeout=5,
                        capture_output=True)
    except Exception as e:
        print(f"  ⚠️  notification failed: {e}")

def jwt_days_left(token):
    """Decode JWT exp without verifying. Returns days remaining, or None."""
    try:
        import base64
        p = token.split(".")[1]
        p += "=" * (-len(p) % 4)
        exp = json.loads(base64.urlsafe_b64decode(p)).get("exp")
        if not exp:
            return None
        return (exp - utc_now().timestamp()) / 86400
    except Exception:
        return None

def load_jwt():
    """Load JWT token from auth file"""
    try:
        auth_path = Path.home() / ".sage_robinhood_auth.json"
        if not auth_path.exists():
            auth_path = Path(os.path.expanduser("~/.sage_robinhood_auth.json"))

        data = json.loads(auth_path.read_text())
        token = data.get("tokens", {}).get("access_token")
        if token:
            print(f"✓ Loaded token from {auth_path}")
            return token
        print(f"❌ No access_token in {auth_path}")
        return None
    except Exception as e:
        print(f"❌ Error loading token: {e}")
        return None

def get_prices(symbols):
    """Live tick quotes from Finnhub -- current price only. Candle/OHLC
    history is NOT available on this API key's plan, so levels and
    confirmation candles come from the Robinhood MCP instead (see
    get_daily_levels / get_confirmation_candles)."""
    prices = {}
    for sym in symbols:
        try:
            r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={FINNHUB_KEY}", timeout=5)
            if r.status_code == 200:
                d = r.json()
                cur = d.get("c", 0) or 0
                if cur <= 0:
                    continue
                prices[sym] = {"price": cur}
        except:
            pass
    return prices

def init_log():
    if not os.path.exists(TRADE_LOG):
        with open(TRADE_LOG, 'w', newline='') as f:
            csv.writer(f).writerow(["Date", "Time", "Symbol", "Entry", "Shares", "Exit", "P&L", "Win/Loss", "Return%", "Reason"])

def log_trade(sym, entry, shares, exit_price, reason=""):
    pnl = (exit_price - entry) * shares
    ret = ((exit_price - entry) / entry * 100) if entry > 0 else 0
    mt = market_now()
    with open(TRADE_LOG, 'a', newline='') as f:
        csv.writer(f).writerow([
            mt.strftime("%Y-%m-%d"),
            mt.strftime("%H:%M:%S ET"),
            sym, f"{entry:.2f}", f"{shares:.4f}", f"{exit_price:.2f}",
            f"{pnl:.2f}", "WIN" if pnl > 0 else "LOSS", f"{ret:.2f}%", reason
        ])

def _result_text(result):
    """Extract text payload from an MCP CallToolResult"""
    try:
        parts = []
        for c in (result.content or []):
            t = getattr(c, "text", None)
            if t:
                parts.append(t)
        return " ".join(parts)
    except Exception:
        return str(result)

async def get_daily_levels(session, symbols):
    """RH/RL = yesterday's daily high/low. SH/SL = highest high / lowest
    low over the prior SWING_LOOKBACK_DAYS sessions (yesterday included).
    Computed once per day at startup -- these don't move intraday."""
    end = utc_now()
    start = end - timedelta(days=14)  # comfortably covers 5+ trading days incl. weekends/holidays
    levels = {}
    try:
        res = await session.call_tool("get_equity_historicals", {
            "symbols": symbols,
            "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "interval": "day",
            "bounds": "regular",
        })
        payload = json.loads(_result_text(res))
        today_et = market_now().date()
        for r in payload["data"]["results"]:
            sym = r["symbol"]
            bars = [b for b in r.get("bars", []) if not b.get("interpolated")]
            past = [b for b in bars if parse_utc(b["begins_at"]).date() < today_et]
            past.sort(key=lambda b: b["begins_at"])
            if not past:
                continue
            yesterday = past[-1]
            lookback = past[-SWING_LOOKBACK_DAYS:]
            rh = float(yesterday["high_price"])
            rl = float(yesterday["low_price"])
            sh = max(float(b["high_price"]) for b in lookback)
            sl = min(float(b["low_price"]) for b in lookback)
            # guard against a degenerate (too-short) lookback inverting the zones
            sh = max(sh, rh)
            sl = min(sl, rl)
            levels[sym] = {"rh": rh, "rl": rl, "sh": sh, "sl": sl}
    except Exception as e:
        print(f"  ⚠️  daily levels fetch failed: {e}")
    return levels

async def get_confirmation_candles(session, symbols):
    """Latest FULLY CLOSED 5-minute bar per symbol -- the confirmation
    candle the notes call for (close vs open, nothing fancier)."""
    if not symbols:
        return {}
    now = utc_now()
    start = now - timedelta(minutes=45)
    candles = {}
    try:
        res = await session.call_tool("get_equity_historicals", {
            "symbols": symbols,
            "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "interval": CONFIRMATION_INTERVAL,
            "bounds": "regular",
        })
        payload = json.loads(_result_text(res))
        for r in payload["data"]["results"]:
            sym = r["symbol"]
            bars = [b for b in r.get("bars", []) if not b.get("interpolated")]
            complete = [b for b in bars if now - parse_utc(b["begins_at"]) >= timedelta(minutes=5)]
            if not complete:
                continue
            complete.sort(key=lambda b: b["begins_at"])
            last = complete[-1]
            o, c, lo = float(last["open_price"]), float(last["close_price"]), float(last["low_price"])
            candles[sym] = {"open": o, "close": c, "low": lo,
                             "bullish": c > o, "bearish": c < o}
    except Exception as e:
        print(f"  ⚠️  confirmation candle fetch failed: {e}")
    return candles

async def load_tradability(session):
    """Fetch per-symbol fractional eligibility. Returns {sym: can_buy_fractional}"""
    res = await session.call_tool("get_equity_tradability", {
        "account_number": ACCOUNT,
        "symbols": WATCHLIST,
    })
    frac = {}
    try:
        payload = json.loads(_result_text(res))
        for r in payload["data"]["results"]:
            frac[r["symbol"]] = (r.get("fractional_tradability") == "tradable"
                                 and r.get("tradeable") is True)
    except Exception as e:
        print(f"⚠️  Tradability lookup failed ({e}) - defaulting to whole shares")
        return {s: False for s in WATCHLIST}
    return frac

def size_position(sym, price, frac_ok):
    """Return share qty respecting fractional rules, or 0 if not fillable."""
    if price <= 0:
        return 0
    raw = MIN_TRADE / price
    if frac_ok.get(sym, False):
        return round(raw, 6)
    whole = int(raw)
    return whole

async def get_buying_power(session):
    """LIVE buying power. Must be re-read every scan -- other agents (scheduled
    Claude tasks) share this account and spend the same cash."""
    try:
        pf = await session.call_tool("get_portfolio", {"account_number": ACCOUNT})
        return float(json.loads(_result_text(pf))["data"]["buying_power"]["buying_power"])
    except Exception as e:
        print(f"  ⚠️  buying power read failed: {e}")
        return None

async def get_broker_positions(session):
    """What the BROKER says we hold -- the only source of truth."""
    try:
        r = await session.call_tool("get_equity_positions", {"account_number": ACCOUNT})
        data = json.loads(_result_text(r))["data"]["positions"]
        out = {}
        for p in data:
            q = float(p.get("quantity", 0) or 0)
            if q > 0:
                out[p.get("symbol")] = {
                    "qty": q,
                    "avg": float(p.get("average_buy_price", 0) or 0),
                    "sellable": float(p.get("shares_available_for_sells", q) or q),
                }
        return out
    except Exception as e:
        print(f"  ⚠️  position read failed: {e}")
        return None

async def execute_order(session, sym, side, shares):
    """Place a real order. Returns True ONLY on confirmed success."""
    import uuid
    try:
        result = await session.call_tool("place_equity_order", {
            "account_number": ACCOUNT,
            "symbol": sym,
            "side": side,
            "type": "market",
            "quantity": str(shares),
            "time_in_force": "gfd",
            "market_hours": "regular_hours",
            "ref_id": str(uuid.uuid4()),
        })

        body = _result_text(result)

        if getattr(result, "isError", False):
            print(f"     ✗ REJECTED: {body[:300]}")
            return False

        low = body.lower()
        if any(k in low for k in ['"error"', "rejected", "not allowed", "insufficient", "unauthorized"]):
            print(f"     ✗ REJECTED: {body[:300]}")
            return False

        print(f"     ✓ ACCEPTED: {body[:300]}")
        return True

    except Exception as e:
        print(f"     ✗ EXCEPTION: {e}")
        return False

async def flatten_all(session, positions, prices, daily_profit, reason):
    """Market-sell every tracked position. Used by the scheduled EOD
    flatten and the daily-loss circuit breaker -- unconditional, no
    confirmation candle required, safety over setup."""
    if not positions:
        return daily_profit
    print(f"\n🔔 FLATTEN ({reason}) - closing {len(positions)} position(s)")
    for sym in list(positions.keys()):
        if sym not in prices:
            print(f"  ⚠️  {sym}: no price, CANNOT FLATTEN - check manually")
            continue
        entry = positions[sym]["entry"]
        shares = positions[sym]["shares"]
        current = prices[sym]["price"]
        gain = ((current - entry) / entry * 100)
        print(f"\n→ SELL {sym} @ ${current:.2f} ({gain:+.2f}%)")
        if await execute_order(session, sym, "sell", shares):
            pnl = (current - entry) * shares
            daily_profit += pnl
            log_trade(sym, entry, shares, current, reason)
            del positions[sym]
            print(f"  ✓ ${pnl:+.2f}")
        else:
            print(f"  ✗ FLATTEN FAILED - {sym} STILL OPEN, close it manually")
    return daily_profit

def zone_of(price, lv):
    if price >= lv["rh"]:
        return "SELL"
    if price <= lv["rl"]:
        return "BUY"
    return "KILL"

def compute_stop(entry, sl):
    """Zone-based stop (SL), bounded between the -4% worst-case backstop
    and a -1.5% minimum distance -- SL alone can sit almost on top of
    entry when price enters near the bottom of the Buy Zone, which made
    ordinary noise clip the stop repeatedly (see MIN_STOP_DISTANCE_PCT)."""
    stop = max(sl, entry * (1 + STOP_LOSS_BACKSTOP_PCT / 100))
    stop = min(stop, entry * (1 + MIN_STOP_DISTANCE_PCT / 100))
    return stop

async def main():
    if not MCP_OK:
        print("❌ MCP not available")
        return

    token = load_jwt()
    if not token:
        return

    print("\n" + "="*70)
    print("SAGE BOT v11 - LIVE (RANGE & SWING STRATEGY)")
    print("="*70)
    print("✅ JWT token loaded")
    print("✅ Real Finnhub prices")
    print("✅ Real Robinhood trades + historicals via MCP")

    mt = market_now()
    lt = datetime.now()
    print("-"*70)
    print(f"  Market time : {mt.strftime('%a %Y-%m-%d %I:%M %p %Z')}")
    print(f"  Local time  : {lt.strftime('%a %Y-%m-%d %I:%M %p')}")
    off = round((lt.replace(tzinfo=None) - mt.replace(tzinfo=None)).total_seconds() / 3600)
    print(f"  Offset      : local is {off:+d}h vs market")
    print(f"  Entries     : 10:00-15:55 ET   EOD flatten 15:55 ET   Exit 16:00 ET")
    print(f"  Strategy    : Buy Zone entry + confirmation candle | zone-based stop/target")

    if mt.weekday() >= 5:
        print("  ⛔ WEEKEND - market closed. Exiting without connecting to the broker.")
        print("="*70 + "\n")
        return

    dleft = jwt_days_left(token)
    if dleft is not None:
        flag = "⚠️ " if dleft < 3 else "  "
        print(f"{flag}  Token       : {dleft:.1f} days left"
              + ("  <-- RENEW SOON" if dleft < 3 else ""))
        if dleft <= 0:
            print("  ❌ TOKEN EXPIRED - re-authorize before running")
            print("="*70 + "\n")
            notify_macos("Sage Bot - Auth Expired",
                         "JWT token has expired. Re-authorize before the bot can trade again.")
            return
        if dleft < TOKEN_WARN_DAYS:
            notify_macos("Sage Bot - Re-auth soon",
                         f"Robinhood token expires in {dleft:.1f} days. Re-authorize before it lapses.")
    print("="*70 + "\n")

    init_log()
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(30)) as hc:
            async with streamable_http_client(MCP_URL, http_client=hc) as (rs, ws):
                async with ClientSession(rs, ws) as session:
                    await session.initialize()
                    print("✓ Connected to Robinhood MCP")

                    acct_res = await session.call_tool("get_accounts", {})
                    acct_body = _result_text(acct_res)
                    if getattr(acct_res, "isError", False):
                        print(f"❌ Auth check FAILED: {acct_body[:300]}")
                        return
                    if ACCOUNT not in acct_body:
                        print(f"❌ Account {ACCOUNT} not visible to this token.")
                        print(f"   Response: {acct_body[:400]}")
                        return
                    if '"agentic_allowed":true' not in acct_body.replace(" ", ""):
                        print("⚠️  WARNING: agentic_allowed not confirmed - orders may reject")
                    print(f"✓ Auth verified - account {ACCOUNT} is live and agentic-enabled")

                    frac_ok = await load_tradability(session)
                    for s in WATCHLIST:
                        mode = "fractional" if frac_ok.get(s) else "WHOLE SHARES ONLY"
                        print(f"    {s}: {mode}")

                    # ---- DAILY LEVELS (computed once) ----
                    levels = await get_daily_levels(session, WATCHLIST)
                    missing = [s for s in WATCHLIST if s not in levels]
                    print()
                    print("📐 RANGE & SWING LEVELS")
                    for s in WATCHLIST:
                        if s in levels:
                            lv = levels[s]
                            print(f"    {s}: Sell [{lv['rh']:.2f}-{lv['sh']:.2f}] | "
                                  f"Kill [{lv['rl']:.2f}-{lv['rh']:.2f}] | "
                                  f"Buy [{lv['sl']:.2f}-{lv['rl']:.2f}]")
                    if missing:
                        print(f"  ⚠️  no levels for {', '.join(missing)} - will not be traded today")
                    print()

                    bp0 = await get_buying_power(session)
                    bpos = await get_broker_positions(session)
                    print(f"✓ Buying power ${bp0 or 0:.2f} -> {int((bp0 or 0)//MIN_TRADE)} slots of ${MIN_TRADE:.0f}")

                    # Rehydrate positions this bot already opened in a
                    # previous run/day. Stop/target are recomputed fresh
                    # from today's levels; if levels are missing for that
                    # symbol, fall back to the fixed backstop % so the
                    # position is still protected somehow.
                    positions = {}
                    if bpos:
                        adopted = []
                        foreign = []
                        for s, v in bpos.items():
                            if s in WATCHLIST:
                                entry = v["avg"]
                                if s in levels:
                                    stop = compute_stop(entry, levels[s]["sl"])
                                    target = levels[s]["rh"]
                                else:
                                    stop = entry * (1 + STOP_LOSS_BACKSTOP_PCT / 100)
                                    target = entry * 1.05
                                positions[s] = {"entry": entry, "shares": v["qty"], "stop": stop, "target": target}
                                adopted.append(s)
                            else:
                                foreign.append(s)
                        if adopted:
                            det = ", ".join(f"{s} x{bpos[s]['qty']:g} @ ${bpos[s]['avg']:.2f} "
                                             f"(stop ${positions[s]['stop']:.2f} / target ${positions[s]['target']:.2f})"
                                             for s in adopted)
                            print(f"🔄 Adopted pre-existing watchlist position(s) from broker: {det}")
                        if foreign:
                            det = ", ".join(f"{s} x{bpos[s]['qty']:g}" for s in foreign)
                            print(f"⚠️  Account also holds (outside watchlist, NOT managed here): {det}")
                    else:
                        print("✓ No open positions - clean start")
                    if (bp0 or 0) < MIN_TRADE and not positions:
                        print("❌ Insufficient buying power to place any trade, and nothing to manage. Exiting.")
                        return
                    if (bp0 or 0) < MIN_TRADE and positions:
                        print(f"⚠️  Buying power (${bp0 or 0:.2f}) below ${MIN_TRADE:.0f} minimum - no NEW entries "
                              f"this run, but {len(positions)} existing position(s) will still be fully managed.")
                    print()

                    scan = daily_trades = daily_profit = 0

                    while True:
                        scan += 1
                        now = market_now()
                        local = datetime.now()
                        ts = now.strftime("%I:%M:%S %p ET")
                        hour = now.hour

                        print(f"\n[{ts}] Scan #{scan}   (local {local.strftime('%I:%M %p')})")

                        prices = get_prices(WATCHLIST)
                        candles = await get_confirmation_candles(session, list(levels.keys()))

                        bp = await get_buying_power(session)
                        if bp is None:
                            bp = 0.0
                        broker = await get_broker_positions(session)
                        broker_read_ok = broker is not None

                        if broker is not None:
                            for s in list(positions.keys()):
                                if s not in broker:
                                    print(f"  🔄 {s} no longer held at broker - dropping from tracking")
                                    del positions[s]
                            foreign = [s for s in broker if s not in positions]
                            if foreign:
                                det = ", ".join(f"{s} x{broker[s]['qty']:g}" for s in foreign)
                                print(f"  👤 held by another agent (not managed here): {det}")
                        else:
                            print("  ⚠️  broker position read failed this scan - skipping entries to avoid a blind duplicate buy")

                        max_positions = int(bp // MIN_TRADE)
                        print(f"  💰 BP ${bp:.2f} | {len(positions)} managed"
                              f"{f' + {len(broker)-len(positions)} foreign' if broker and len(broker)>len(positions) else ''}"
                              f" | room for {max_positions} more")

                        print("📊 ZONES  (price | zone | candle)")
                        for sym in WATCHLIST:
                            if sym not in prices or sym not in levels:
                                continue
                            p = prices[sym]["price"]
                            lv = levels[sym]
                            zone = zone_of(p, lv)
                            cndl = candles.get(sym)
                            cndl_txt = ("bull" if cndl and cndl["bullish"] else
                                        "bear" if cndl and cndl["bearish"] else
                                        "flat" if cndl else "n/a")
                            entry_ready = (zone == "BUY" and sym not in positions and cndl
                                           and cndl["low"] <= lv["rl"] and cndl["bullish"])
                            sig = "⚡ ENTRY" if entry_ready else ""
                            print(f"  {sym}: ${p:.2f}  {zone:4s}  candle:{cndl_txt}  {sig}")

                        minute = now.minute
                        in_flatten = (hour == 15 and minute >= 55) or hour >= 16
                        window_open = (10 <= hour < 16) and not in_flatten
                        if not window_open:
                            why = "EOD flatten" if in_flatten else "entries run 10:00-15:55 ET"
                            print(f"  ⏸  Entry window CLOSED ({why}, now {hour:02d}:{minute:02d} ET)")
                        if window_open and not broker_read_ok:
                            print("  ⏸  Entries skipped this scan - stale broker position data")
                        if window_open and broker_read_ok:
                            held = set(positions) | set(broker or {})
                            candidates = []
                            for sym in WATCHLIST:
                                if sym in held or sym not in prices or sym not in levels:
                                    continue
                                p = prices[sym]["price"]
                                lv = levels[sym]
                                cndl = candles.get(sym)
                                if zone_of(p, lv) != "BUY" or not cndl:
                                    continue
                                if cndl["low"] <= lv["rl"] and cndl["bullish"]:
                                    depth = (lv["rl"] - p) / lv["rl"] * 100  # how far below RL, deeper = weaker
                                    candidates.append((depth, sym))
                            candidates.sort(reverse=True)  # deepest into the zone first

                            slots = max_positions
                            if candidates:
                                ranked = ", ".join(f"{s} ({d:+.2f}% into zone)" for d, s in candidates)
                                print(f"  🎯 {len(candidates)} signal(s) ranked: {ranked}")
                                if len(candidates) > slots:
                                    skipped = ", ".join(s for _, s in candidates[slots:])
                                    print(f"  ⏸  only {slots} slot(s) free - passing on {skipped}")

                            bought = 0
                            for depth, sym in candidates:
                                if bought >= slots:
                                    break
                                bp_now = await get_buying_power(session)
                                if bp_now is None or bp_now < MIN_TRADE:
                                    print(f"  ⏸  buying power re-check failed or insufficient (${bp_now if bp_now is not None else 'unknown'}) - stopping entries this scan")
                                    break
                                price = prices[sym]["price"]
                                lv = levels[sym]
                                stop = compute_stop(price, lv["sl"])
                                target = lv["rh"]
                                if stop >= price or target <= price:
                                    print(f"  ⏸  {sym} skipped - degenerate stop/target (stop ${stop:.2f} target ${target:.2f} price ${price:.2f})")
                                    continue
                                shares = size_position(sym, price, frac_ok)
                                if shares == 0:
                                    print(f"  ⏸  {sym} skipped - ${MIN_TRADE:.0f} < 1 whole share @ ${price:.2f} (no fractional)")
                                    continue
                                print(f"\n→ BUY {sym}: {shares} @ ${price:.2f} (~${shares*price:.2f})  "
                                      f"[Buy Zone, {depth:+.2f}% into it | stop ${stop:.2f} | target ${target:.2f}]")
                                if await execute_order(session, sym, "buy", shares):
                                    positions[sym] = {"entry": price, "shares": shares, "stop": stop, "target": target}
                                    daily_trades += 1
                                    bought += 1
                                    print("  ✓ EXECUTED")
                                else:
                                    print("  ✗ Failed")

                        if in_flatten and positions:
                            daily_profit = await flatten_all(session, positions, prices, daily_profit, "EOD_FLATTEN")

                        if hour >= 16:
                            if positions:
                                print(f"⚠️  {len(positions)} position(s) still open past the close: {list(positions)}")
                                notify_macos("Sage Bot - Positions still open",
                                             f"{len(positions)} position(s) still open past market close: {', '.join(positions)}")
                            print(f"\n💹 FINAL: {daily_trades} trades | ${daily_profit:.2f}")
                            print("Market closed. Exiting.")
                            break

                        # ---- EXITS (regular hours only) ----
                        for sym in (list(positions.keys()) if 9 <= hour < 16 else []):
                            if sym not in prices:
                                continue
                            entry = positions[sym]["entry"]
                            shares = positions[sym]["shares"]
                            stop = positions[sym]["stop"]
                            target = positions[sym]["target"]
                            current = prices[sym]["price"]
                            gain = ((current - entry) / entry * 100)
                            cndl = candles.get(sym)

                            if current <= stop:
                                # Hard stop -- no confirmation wait, risk limit not a setup.
                                print(f"\n→ SELL {sym} @ ${current:.2f} ({gain:.2f}%) [STOP ${stop:.2f}]")
                                if await execute_order(session, sym, "sell", shares):
                                    pnl = (current - entry) * shares
                                    daily_profit += pnl
                                    log_trade(sym, entry, shares, current, "STOP")
                                    del positions[sym]
                                    print(f"  ✓ ${pnl:.2f}")
                                else:
                                    print("  ✗ Failed")

                            elif current >= target and cndl and cndl["bearish"]:
                                # Sell Zone reached WITH the same rejection-candle
                                # confirmation the notes require -- exit the long.
                                print(f"\n→ SELL {sym} @ ${current:.2f} (+{gain:.2f}%) [TARGET ${target:.2f}, confirmed]")
                                if await execute_order(session, sym, "sell", shares):
                                    pnl = (current - entry) * shares
                                    daily_profit += pnl
                                    log_trade(sym, entry, shares, current, "TARGET_CONFIRMED")
                                    del positions[sym]
                                    print(f"  ✓ +${pnl:.2f}")
                                else:
                                    print("  ✗ Failed")

                        print(f"\n💹 {daily_trades} trades | ${daily_profit:.2f}")

                        if daily_profit <= DAILY_LOSS_LIMIT:
                            print(f"\n🛑 DAILY LOSS LIMIT HIT (${daily_profit:.2f} <= ${DAILY_LOSS_LIMIT:.2f})")
                            daily_profit = await flatten_all(session, positions, prices, daily_profit, "DAILY_LOSS_LIMIT")
                            if positions:
                                print(f"⚠️  {len(positions)} position(s) could NOT be flattened - check the Robinhood app now: {list(positions)}")
                                notify_macos("Sage Bot - FLATTEN FAILED",
                                             f"Daily loss limit hit and could not flatten: {', '.join(positions)}. Check the app now.")
                            else:
                                notify_macos("Sage Bot - Daily loss limit",
                                             f"Daily loss limit hit (${daily_profit:.2f}). Positions flattened, bot stopped for the day.")
                            print(f"\n💹 FINAL: {daily_trades} trades | ${daily_profit:.2f}")
                            break

                        await asyncio.sleep(60)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "!"*70)
        print("⚠️  BOT CRASHED. Open positions are UNPROTECTED - no broker-side stop.")
        print("⚠️  Check the Robinhood app and close manually if needed.")
        print("!"*70)
        notify_macos("Sage Bot - CRASHED", f"Bot crashed: {e}. Check positions manually.")

if __name__ == "__main__":
    # See v10 for why this wraps asyncio.run() rather than living inside
    # main() -- Ctrl+C surfaces as a real KeyboardInterrupt only here.
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n" + "!"*70)
        print("STOPPED BY USER")
        print("!"*70)
        print("⚠️  The stop/target logic lives ONLY in this script.")
        print("⚠️  There are NO stop orders resting at Robinhood.")
        print("⚠️  Any open position is now UNPROTECTED until you restart or sell.")
        print("Check open positions in the Robinhood app now.")
        print("!"*70)
        notify_macos("Sage Bot - STOPPED", "Bot stopped by Ctrl+C. Open positions are UNPROTECTED until restarted or sold.")
