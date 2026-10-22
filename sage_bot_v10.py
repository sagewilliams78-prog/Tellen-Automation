#!/usr/bin/env python3
"""
SAGE BOT v10 - MCP LIVE TRADING (DAILY AUTO-START)

v10 adds the guardrails needed to run this unattended every weekday via a
launchd job, instead of being started by hand from a terminal each morning:
  - Hard exit on weekends before ever touching the broker (no MCP connect,
    no chance of a stray order off stale weekend quote data).
  - Hard exit if the JWT is already expired, instead of limping into a
    doomed MCP connection.
  - A macOS local notification when the JWT has < 2 days left, so an
    unattended run surfaces "re-auth soon" instead of just silently
    failing once the token dies.

Inherits from v9: daily-loss circuit breaker that flattens instead of
abandoning positions, restart-safe position rehydration from the broker's
average_buy_price, live buying-power recheck before every order, and
skipping entries on a stale broker read.

Inherits from v8/v7: smart slot priority (weakest signal first), JWT bearer
auth, isError checking, from-open signal, whole-share fallback, EOD flatten
at 3:55pm ET.
"""
import requests, asyncio, csv, os, json, subprocess
from datetime import datetime
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

PROFIT_TARGET = 5.0
STOP_LOSS = -4.0
MIN_TRADE = 50.0
ENTRY_THRESHOLD = -2.0
DAILY_LOSS_LIMIT = -50.0
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
        from datetime import timezone
        return (exp - datetime.now(timezone.utc).timestamp()) / 86400
    except Exception:
        return None

def load_jwt():
    """Load JWT token from auth file"""
    try:
        # Try user home first
        auth_path = Path.home() / ".sage_robinhood_auth.json"
        if not auth_path.exists():
            # Fallback to expanduser
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
    """
    Finnhub /quote fields:
      c = current, o = today's OPEN, pc = previous close, dp = % chg vs PREVIOUS CLOSE
    Entry signal uses change from TODAY'S OPEN, not dp.
    """
    prices = {}
    for sym in symbols:
        try:
            r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={FINNHUB_KEY}", timeout=5)
            if r.status_code == 200:
                d = r.json()
                cur = d.get("c", 0) or 0
                opn = d.get("o", 0) or 0
                if cur <= 0:
                    continue
                from_open = ((cur - opn) / opn * 100) if opn > 0 else 0.0
                from_close = d.get("dp", 0) or 0.0
                prices[sym] = {
                    "price": cur,
                    "open": opn,
                    "change_pct": from_open,     # SIGNAL: vs today's open
                    "from_close": from_close,    # reference only
                }
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
    mt = market_now()   # log in market time so entries/exits line up with the tape
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
            # 'tradable' = can buy fractional.
            # 'position_closing_only' = SELL fractional only, buys must be whole shares
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
    whole = int(raw)  # floor
    return whole  # 0 means $50 can't buy even one whole share

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
    """What the BROKER says we hold -- the only source of truth.
    Catches positions opened by the scheduled Claude tasks, manual app
    trades, or a previous crashed run of this bot."""
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

        # MCP tool-level failure does NOT raise -- must check isError
        if getattr(result, "isError", False):
            print(f"     ✗ REJECTED: {body[:300]}")
            return False

        # Some gateways return isError=False but an error payload
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
    """Market-sell every tracked position. Used by both the scheduled EOD
    flatten and the daily-loss circuit breaker -- the daily-loss break used
    to exit the loop without this, leaving positions open and unprotected."""
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

async def main():
    if not MCP_OK:
        print("❌ MCP not available")
        return

    token = load_jwt()
    if not token:
        return

    print("\n" + "="*70)
    print("SAGE BOT v10 - LIVE (DAILY AUTO-START)")
    print("="*70)
    print("✅ JWT token loaded")
    print("✅ Real Finnhub prices")
    print("✅ Real Robinhood trades via MCP")

    mt = market_now()
    lt = datetime.now()
    print("-"*70)
    print(f"  Market time : {mt.strftime('%a %Y-%m-%d %I:%M %p %Z')}")
    print(f"  Local time  : {lt.strftime('%a %Y-%m-%d %I:%M %p')}")
    off = round((lt.replace(tzinfo=None) - mt.replace(tzinfo=None)).total_seconds() / 3600)
    print(f"  Offset      : local is {off:+d}h vs market")
    print(f"  Entries     : 10:00-15:55 ET   EOD flatten 15:55 ET   Exit 16:00 ET")

    # ---- WEEKEND HARD EXIT ----
    # This runs unattended off a daily scheduler now, so it WILL get invoked
    # on Saturday/Sunday. Exit before ever connecting to the broker or
    # fetching a quote -- there's no legitimate entry signal off a closed
    # market, and stale/zero weekend data is exactly the kind of edge case
    # that shouldn't get anywhere near live order placement.
    if mt.weekday() >= 5:
        print("  ⛔ WEEKEND - market closed. Exiting without connecting to the broker.")
        print("="*70 + "\n")
        return

    # ---- JWT EXPIRY HARD EXIT ----
    # Previously this only printed a warning and let the loop try (and fail)
    # to connect. Unattended, that just burns a scheduled run for nothing --
    # exit clean instead so the log clearly says "needs re-auth."
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

    # Create HTTP client with Bearer token
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(30)) as hc:
            async with streamable_http_client(MCP_URL, http_client=hc) as (rs, ws):
                async with ClientSession(rs, ws) as session:
                    await session.initialize()
                    print("✓ Connected to Robinhood MCP")

                    # VERIFY AUTH IS LIVE before trusting the loop
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

                    # Per-symbol fractional eligibility (BTAI etc. reject fractional BUYS)
                    frac_ok = await load_tradability(session)
                    for s in WATCHLIST:
                        mode = "fractional" if frac_ok.get(s) else "WHOLE SHARES ONLY"
                        print(f"    {s}: {mode}")

                    # Buying power + positions are re-read EVERY scan inside the loop
                    # (shared account). This is just the opening snapshot.
                    bp0 = await get_buying_power(session)
                    bpos = await get_broker_positions(session)
                    print(f"✓ Buying power ${bp0 or 0:.2f} -> {int((bp0 or 0)//MIN_TRADE)} slots of ${MIN_TRADE:.0f}")

                    # Rehydrate tracking for positions this bot already opened in a
                    # previous run. Without this, a restart (crash, manual bounce,
                    # or simply a NEW DAY'S launchd run) makes the reconciliation
                    # loop below treat our own open positions as "foreign" and
                    # silently stop managing them -- no profit-target, no
                    # stop-loss, no EOD flatten, forever.
                    # We can't tell which broker positions are genuinely ours vs.
                    # another agent's, so we adopt anything on OUR watchlist using
                    # the broker's average_buy_price as entry. Positions in symbols
                    # outside WATCHLIST are left alone (not something this bot trades).
                    positions = {}
                    if bpos:
                        adopted = []
                        foreign = []
                        for s, v in bpos.items():
                            if s in WATCHLIST:
                                positions[s] = {"entry": v["avg"], "shares": v["qty"]}
                                adopted.append(s)
                            else:
                                foreign.append(s)
                        if adopted:
                            det = ", ".join(f"{s} x{bpos[s]['qty']:g} @ ${bpos[s]['avg']:.2f}" for s in adopted)
                            print(f"🔄 Adopted pre-existing watchlist position(s) from broker: {det}")
                            print("    Treating broker average_buy_price as entry - will be managed (profit/stop/EOD) from here.")
                        if foreign:
                            det = ", ".join(f"{s} x{bpos[s]['qty']:g}" for s in foreign)
                            print(f"⚠️  Account also holds (outside watchlist, NOT managed here): {det}")
                    else:
                        print("✓ No open positions - clean start")
                    if (bp0 or 0) < MIN_TRADE:
                        print("❌ Insufficient buying power to place any trade. Exiting.")
                        return
                    print()

                    scan = daily_trades = daily_profit = 0

                    while True:
                        scan += 1
                        now = market_now()                       # EASTERN, not local
                        local = datetime.now()
                        ts = now.strftime("%I:%M:%S %p ET")
                        hour = now.hour

                        print(f"\n[{ts}] Scan #{scan}   (local {local.strftime('%I:%M %p')})")

                        prices = get_prices(WATCHLIST)

                        # ---- RECONCILE WITH BROKER (every scan) ----
                        # This account is shared with the scheduled Claude tasks.
                        # Cached buying power goes stale the moment they trade.
                        bp = await get_buying_power(session)
                        if bp is None:
                            bp = 0.0
                        broker = await get_broker_positions(session)
                        broker_read_ok = broker is not None

                        if broker is not None:
                            # positions we think we hold but broker doesn't -> already sold
                            for s in list(positions.keys()):
                                if s not in broker:
                                    print(f"  🔄 {s} no longer held at broker - dropping from tracking")
                                    del positions[s]
                            # positions broker holds that we didn't open -> not ours to manage
                            foreign = [s for s in broker if s not in positions]
                            if foreign:
                                det = ", ".join(f"{s} x{broker[s]['qty']:g}" for s in foreign)
                                print(f"  👤 held by another agent (not managed here): {det}")
                        else:
                            print("  ⚠️  broker position read failed this scan - skipping entries to avoid a blind duplicate buy")

                        slots_used = len(positions) + (len(broker) - len(positions) if broker else 0)
                        max_positions = int(bp // MIN_TRADE)
                        print(f"  💰 BP ${bp:.2f} | {len(positions)} managed"
                              f"{f' + {len(broker)-len(positions)} foreign' if broker and len(broker)>len(positions) else ''}"
                              f" | room for {max_positions} more")

                        print("📊 SIGNALS  (vs OPEN | vs prev close)")
                        for sym in WATCHLIST:
                            if sym in prices:
                                p = prices[sym]["price"]
                                chg = prices[sym]["change_pct"]
                                pc = prices[sym]["from_close"]
                                op = prices[sym]["open"]
                                sig = "⚡ ENTRY" if chg <= ENTRY_THRESHOLD and sym not in positions else ""
                                print(f"  {sym}: ${p:.2f} (open ${op:.2f})  {chg:+.2f}% | {pc:+.2f}%  {sig}")

                        # ENTRIES - stop before the EOD flatten so we never
                        # buy and immediately sell in the same scan
                        # All gates below are EASTERN market time.
                        # Market: 09:30-16:00 ET. Entries 10:00-15:55 ET.
                        minute = now.minute
                        in_flatten = (hour == 15 and minute >= 55) or hour >= 16
                        window_open = (10 <= hour < 16) and not in_flatten
                        if not window_open:
                            why = "EOD flatten" if in_flatten else "entries run 10:00-15:55 ET"
                            print(f"  ⏸  Entry window CLOSED ({why}, now {hour:02d}:{minute:02d} ET)")
                        if window_open and not broker_read_ok:
                            print("  ⏸  Entries skipped this scan - stale broker position data")
                        if window_open and broker_read_ok:
                            # ---- SMART SLOT PRIORITY ----
                            # Slots are scarce (cash account). When more signals fire
                            # than we have room for, take the STRONGEST ones -- biggest
                            # drop from today's open -- instead of whatever happens to
                            # sit earliest in WATCHLIST.
                            held = set(positions) | set(broker or {})   # never double up
                            candidates = [
                                (prices[s]["change_pct"], s)
                                for s in WATCHLIST
                                if s in prices
                                and s not in held
                                and prices[s]["change_pct"] <= ENTRY_THRESHOLD
                            ]
                            candidates.sort()  # most negative (weakest) first

                            # cap by LIVE buying power, not a startup snapshot
                            slots = max_positions
                            if candidates:
                                ranked = ", ".join(f"{s} {c:+.2f}%" for c, s in candidates)
                                print(f"  🎯 {len(candidates)} signal(s) ranked: {ranked}")
                                if len(candidates) > slots:
                                    skipped = ", ".join(s for _, s in candidates[slots:])
                                    print(f"  ⏸  only {slots} slot(s) free - passing on {skipped}")

                            bought = 0
                            for chg, sym in candidates:
                                if bought >= slots:
                                    break
                                # re-check live buying power before EVERY order --
                                # a stale per-scan estimate can overspend when
                                # another agent trades the same account mid-scan.
                                bp_now = await get_buying_power(session)
                                if bp_now is None or bp_now < MIN_TRADE:
                                    print(f"  ⏸  buying power re-check failed or insufficient (${bp_now if bp_now is not None else 'unknown'}) - stopping entries this scan")
                                    break
                                price = prices[sym]["price"]
                                shares = size_position(sym, price, frac_ok)
                                if shares == 0:
                                    print(f"  ⏸  {sym} skipped - ${MIN_TRADE:.0f} < 1 whole share @ ${price:.2f} (no fractional)")
                                    continue
                                print(f"\n→ BUY {sym}: {shares} @ ${price:.2f} (~${shares*price:.2f})  [{chg:+.2f}% from open]")
                                if await execute_order(session, sym, "buy", shares):
                                    positions[sym] = {"entry": price, "shares": shares}
                                    daily_trades += 1
                                    bought += 1
                                    print("  ✓ EXECUTED")
                                else:
                                    print("  ✗ Failed")

                        # ---- END OF DAY FLATTEN (3:55 PM ET) ----
                        # Market orders only execute in regular hours. Anything still
                        # open at the bell would otherwise be carried overnight with
                        # NO broker-side stop protecting it.
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
                        # Market orders tagged regular_hours won't fill after 4pm,
                        # they queue for the next open at an unknown price.
                        for sym in (list(positions.keys()) if 9 <= hour < 16 else []):
                            if sym in prices:
                                entry = positions[sym]["entry"]
                                shares = positions[sym]["shares"]
                                current = prices[sym]["price"]
                                gain = ((current - entry) / entry * 100)

                                if gain >= PROFIT_TARGET:
                                    print(f"\n→ SELL {sym} @ ${current:.2f} (+{gain:.2f}%)")
                                    if await execute_order(session, sym, "sell", shares):
                                        pnl = (current - entry) * shares
                                        daily_profit += pnl
                                        log_trade(sym, entry, shares, current, "PROFIT")
                                        del positions[sym]
                                        print(f"  ✓ +${pnl:.2f}")
                                    else:
                                        print("  ✗ Failed")

                                elif gain <= STOP_LOSS:
                                    print(f"\n→ SELL {sym} @ ${current:.2f} ({gain:.2f}%)")
                                    if await execute_order(session, sym, "sell", shares):
                                        pnl = (current - entry) * shares
                                        daily_profit += pnl
                                        log_trade(sym, entry, shares, current, "STOP")
                                        del positions[sym]
                                        print(f"  ✓ ${pnl:.2f}")
                                    else:
                                        print("  ✗ Failed")

                        print(f"\n💹 {daily_trades} trades | ${daily_profit:.2f}")

                        if daily_profit <= DAILY_LOSS_LIMIT:
                            print(f"\n🛑 DAILY LOSS LIMIT HIT (${daily_profit:.2f} <= ${DAILY_LOSS_LIMIT:.2f})")
                            # Flatten before exiting -- previously this broke the
                            # loop immediately, leaving any open positions with no
                            # broker-side stop and no further management for the
                            # rest of the day. Losing money is the exact moment
                            # this must NOT silently abandon open risk.
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
    # NOTE: under asyncio.run() on this Python version, Ctrl+C surfaces as
    # asyncio.CancelledError INSIDE main() (at whatever await point was
    # active), not as a KeyboardInterrupt raised in that frame -- so a
    # try/except KeyboardInterrupt placed inside main() never fires on a
    # real Ctrl+C. The actual KeyboardInterrupt is raised here, after the
    # cancelled task has unwound, by asyncio.run() itself. This is the only
    # place that reliably catches it.
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n" + "!"*70)
        print("STOPPED BY USER")
        print("!"*70)
        print("⚠️  The -4% stop loss lives ONLY in this script.")
        print("⚠️  There are NO stop orders resting at Robinhood.")
        print("⚠️  Any open position is now UNPROTECTED until you restart or sell.")
        print("Check open positions in the Robinhood app now.")
        print("!"*70)
        notify_macos("Sage Bot - STOPPED", "Bot stopped by Ctrl+C. Open positions are UNPROTECTED until restarted or sold.")
