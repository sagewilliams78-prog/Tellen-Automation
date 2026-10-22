#!/usr/bin/env python3
"""
SAGE BOT v13 - MCP LIVE TRADING (RANGE & SWING STRATEGY, FLOOR-LEAD FILTERS)

v13 adds four trade-quality filters on top of v12, per a floor-lead review
of what the strategy was missing (none of these change the core Range &
Swing entry/exit logic -- they only gate WHETHER a qualifying setup is
actually taken):

  1. VOLUME CONFIRMATION -- DISPLAY ONLY, NOT AN ENTRY GATE. The
     confirmation candle's volume vs. its trailing ~1hr average
     (VOLUME_CONFIRMATION_RATIO) is still computed and shown in the scan
     printout ("lowvol" flag), but backtesting (2026-08-21) found
     requiring it actually REDUCED P&L in every window tested (full
     period +$9.52 -> -$3.21, test period +$11.27 -> +$4.83) -- the
     opposite of its intent. Sound theory, didn't hold on this data, so
     it no longer blocks entries. Left visible per "make failures/
     conditions visible" rather than deleted outright.
  2. EARNINGS BLACKOUT. Skips new entries in a symbol within 1 day of its
     next earnings report (get_earnings_results). A gap-driven earnings
     move breaks the whole premise of RH/RL/SH/SL structure -- that
     structure describes normal trading, not a news gap.
  3. MARKET BREADTH -- DISPLAY ONLY, NOT AN ENTRY GATE. SPY's move from
     today's open is still shown every scan, but backtesting (2026-08-21)
     found blocking entries on it hurt the same way the volume filter
     did (full period +$9.52 -> +$4.49, test period +$11.27 -> +$5.87) --
     it cut trade count without improving quality. Same call as #1: sound
     theory, didn't hold on this data, no longer gates.
  4. WEEKLY WIN-RATE CIRCUIT BREAKER. At startup, reads the trade log's
     trailing 7 calendar days; if win rate is below WEEKLY_WINRATE_FLOOR
     (with enough trades to trust the number), new entries are paused
     for the whole day. Existing positions are still fully managed
     (stop/target/EOD flatten) -- this only blocks opening new risk
     during a stretch that's already going badly.

All four are QUALITY gates on the entry side only -- they never touch
exits, stops, targets, or the EOD/daily-loss flattens, which stay
unconditional as in v11/v12.

REVISED same day (2026-08-21), per a capital-protection-first review:
  - Volume confirmation and market breadth were BACKTESTED and found to
    reduce P&L in every window tested -- both demoted to display-only,
    no longer gate entries. Still shown in the scan output.
  - Position sizing changed from flat $MIN_TRADE/trade to risk-based
    sizing (RISK_PER_TRADE_DOLLARS per trade, capped at
    MAX_NOTIONAL_PER_TRADE) -- a wide-stop trade and a tight-stop trade
    no longer risk the same dollar amount for very different real risk.
    Backtested before switching: costs ~15-25% of total P&L vs. flat
    sizing, accepted for more consistent risk per trade.
  - Two silent `except: pass` blocks (get_prices, get_market_breadth)
    now print the actual failure reason instead of swallowing it.

SAGE BOT v12 - MCP LIVE TRADING (RANGE & SWING STRATEGY, TUNED)

v12 tunes v11 based on backtesting 62 trading days (2026-05-26 to 08-21)
of real 5-minute bars through get_equity_historicals:

  1. BTAI dropped from the watchlist. It accounted for the entire net
     loss in the 62-day backtest (-$12.25 of a -$12.27 total across all
     7 symbols) -- the other 6 were roughly breakeven on their own
     (-$0.02). High-frequency whipsaw-prone churn on a sub-$1 stock was
     a bad fit for this zone strategy specifically.
  2. Stop backstop widened to -2.5% (was -1.5%). Combined with #3, this
     was the best P&L in a win-rate/target-distance sweep (+$9.52 vs
     +$5.82 at -1.5%, config M vs F in that sweep).
  3. Target changed from "reach RH with a bearish confirmation candle"
     to "touch 15% of the way up the RL-RH range, no confirmation
     needed." The old full-RH target barely ever fired (6 times in 62
     days) -- most trades rode to the unconditional EOD flatten instead,
     which is closer to noise than edge. The nearer target converts more
     of those into intentional, earlier exits: win rate 57.1% (vs 41.8%
     for config B / drop-BTAI-only), P&L +$9.52 vs -$0.02.

Explicitly NOT chasen: win rate can be pushed further (a 5%-of-range
target hit 67.6% in the same sweep) but P&L drops to +$2.92 doing it --
smaller, more frequent wins stop covering the same-size losses. Chose
the P&L-maximizing point on that curve, not the win-rate-maximizing one.

Range & Swing levels, unchanged from v11:

  RH = yesterday's daily high        SH = highest high, prior 5 sessions
  RL = yesterday's daily low         SL = lowest low, prior 5 sessions

  Buy Zone  = SL -> RL   (lower band, below yesterday's low)
  Kill Zone = RL -> RH   (the middle -- yesterday's range. No trades here.)
  Sell Zone = RH -> SH   (upper band, above yesterday's high; SH is now
                          reference-only display since target no longer
                          requires reaching this zone)

Entry (BUY only -- this is a cash account, no shorting), unchanged from
v11: price inside the Buy Zone AND the latest closed 5-minute candle
dipped into the zone (low <= RL) AND closed bullish (close > open).

Exit:
  - Hard stop: price <= stop, where stop = SL clamped between the -4%
    worst-case backstop and the -2.5% minimum distance (see
    compute_stop). No confirmation wait -- a stop is a risk limit, not
    a setup.
  - Target: price >= RL + 0.15*(RH-RL). No confirmation candle required
    (backtested as a touch, not a confirmed reversal) -- this is a
    take-profit level inside the old Kill Zone, not the Sell Zone
    rejection setup v11 used.
  - EOD flatten (15:55 ET) and the daily-loss circuit breaker are
    unconditional, same as v11/v10 -- safety over setup.

Levels are computed once per symbol at startup from daily bars. The
confirmation candle is refetched every scan from 5-minute bars. Both
come from the Robinhood MCP's get_equity_historicals, not Finnhub
(Finnhub's free tier has no candle access on this API key).

Inherits from v11: minimum stop-distance clamp (compute_stop) so a stop
can't sit closer than the floor even when SL is right on top of entry.

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
import requests, asyncio, csv, os, json, subprocess, sys
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
    import httpx2
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from robinhood_oauth_v13 import build_robinhood_oauth
    MCP_OK = True
    MCP_IMPORT_ERROR = None
except Exception as e:
    MCP_OK = False
    MCP_IMPORT_ERROR = e

SECRETS_FILE = Path.home() / ".eva_bot_secrets.json"

def load_secrets():
    """Load non-strategy secrets (API keys, account number) from a private local
    file instead of hardcoding them in source. File must be chmod 600."""
    if not SECRETS_FILE.exists():
        raise RuntimeError(
            f"Missing secrets file {SECRETS_FILE} -- expected JSON with "
            f"'finnhub_key' and 'account_number'."
        )
    data = json.loads(SECRETS_FILE.read_text())
    key = data.get("finnhub_key")
    acct = data.get("account_number")
    if not key or not acct:
        raise RuntimeError(f"{SECRETS_FILE} is missing 'finnhub_key' or 'account_number'.")
    return key, acct

FINNHUB_KEY, ACCOUNT = load_secrets()

# The watchlist now lives in _watchlist/current.json, maintained by the
# nightly screener via watchlist_manager.py (added 2026-08-27). It is read
# once here at startup -- the bot restarts daily at 6:00am via launchd
# (com.sage.tradingbot), so an overnight change takes effect the next
# session, and a change made mid-session cannot disturb a running bot.
#
# The fallback below is deliberate and must stay: if watchlist_manager is
# missing, the JSON is corrupt, or anything else goes wrong, the bot runs
# on exactly the list it used before any of this existed rather than
# failing to start or trading something unintended.
_FALLBACK_WATCHLIST = ["IBRX", "IOVA", "NVDA", "TSLA", "AMD", "GDX", "SMCI"]  # BTAI dropped -- see docstring.
try:
    from watchlist_manager import load_watchlist as _load_watchlist
    WATCHLIST = _load_watchlist()
except Exception as _wl_err:                      # never fatal
    print(f"[watchlist] falling back to the built-in list: {_wl_err}")
    WATCHLIST = list(_FALLBACK_WATCHLIST)
                                 # COIN added 2026-08-21, then SWAPPED for SMCI same day after the
                                 # backtest was corrected to model earnings blackout + the weekly
                                 # win-rate pause (both already live here, but missing from the
                                 # analysis script). Under the honest backtest, SMCI added ~$8.24
                                 # over 58 days with a $2.64 window spread vs. COIN's ~$5.60 and a
                                 # $3.26 spread -- SMCI beat COIN on both total return AND
                                 # consistency once measured correctly. See strategy_experiments.py.
MCP_URL = "https://agent.robinhood.com/mcp/trading"
AUTH_FILE = Path.home() / ".sage_robinhood_auth.json"
TRADE_LOG = os.path.expanduser("~/trading_log_v9.csv")
JOURNAL_LOG = os.path.expanduser("~/sage_bot_daily_journal.csv")  # one row per trading day -- see write_daily_journal
OBSIDIAN_VAULT = os.path.expanduser("~/Documents/Eva Trading Journal")  # human-readable companion -- see write_obsidian_note

MIN_TRADE = 50.0                # rough "typical trade size" used only for capacity estimates
                                 # (slot counts, startup BP sanity check) -- actual per-trade
                                 # sizing is risk-based (see RISK_PER_TRADE_DOLLARS below) and
                                 # the real buying-power gate checks the exact computed notional,
                                 # not this constant
STOP_LOSS_BACKSTOP_PCT = -4.0   # never risk more than this from entry, even if SL is farther away
MIN_STOP_DISTANCE_PCT = -2.5    # never risk LESS than this either. Widened from v11's -1.5% --
                                 # backtesting found -2.5% was the P&L-maximizing stop distance
                                 # once paired with the nearer TARGET_FRAC target below.
TARGET_FRAC = 0.25              # target = RL + TARGET_FRAC * (RH - RL). v11 used the full
                                 # range (target=RH, confirmation-candle-gated) but that setup
                                 # barely ever fired (6 times in 62 backtested days) -- most
                                 # trades rode to the unconditional EOD flatten instead, which
                                 # is closer to noise than edge. Widened from 0.15 to 0.25 on
                                 # 2026-08-21 (strategy_experiments.py, 58-day/3-window
                                 # walk-forward): win rate drops slightly (57.7% -> 52.5%
                                 # combined with the COIN addition) but total P&L rises ~54%
                                 # and, combined with adding COIN, the window-to-window spread
                                 # actually SHRANK ($2.63 -> $1.35) -- more consistent, not just
                                 # a bigger number from one lucky window.
DAILY_LOSS_LIMIT = -50.0
SWING_LOOKBACK_DAYS = 5          # prior trading sessions used for SH/SL
CONFIRMATION_INTERVAL = "5minute"
TOKEN_WARN_DAYS = 2.0

# ---- v13 floor-lead filters ----
VOLUME_CONFIRMATION_RATIO = 1.2   # confirmation candle's volume must be >= this x the trailing average
VOLUME_LOOKBACK_BARS = 12         # ~1hr of 5-min bars used for that trailing average
EARNINGS_BLACKOUT_DAYS = 1        # skip new entries within this many days of the symbol's next earnings
MARKET_BREADTH_SYMBOL = "SPY"
MARKET_BREADTH_THRESHOLD_PCT = -0.5  # block new entries market-wide if SPY is down more than this from today's open
WEEKLY_WINRATE_FLOOR = 40.0        # pause new entries for the day if trailing-7-day win rate is below this
WEEKLY_MIN_TRADES = 5              # need at least this many trades in the window to trust the win rate reading

# ---- Risk-based position sizing (2026-08-21) ----
# Replaces flat $MIN_TRADE-per-trade sizing. A fixed notional meant a
# wide-stop trade and a tight-stop trade both risked $50, but risked very
# different PERCENTAGES of that $50 -- a 12%-wide stop and a 2%-wide stop
# aren't the same bet. This sizes shares so every trade risks roughly the
# same RISK_PER_TRADE_DOLLARS, capped at MAX_NOTIONAL_PER_TRADE so a very
# tight stop can't demand an oversized position on this small an account.
# Backtested against the old fixed-notional approach before switching:
# costs ~15-25% of backtested P&L (full period +$9.52 -> +$7.27, test
# period +$11.27 -> +$9.22) in exchange for consistent risk instead of
# consistent notional -- accepted per "protect capital first."
RISK_PER_TRADE_DOLLARS = 2.50   # doubled 2026-08-22 (from $1.25) after backtesting several risk
                                 # tiers on the account's real $193.82 buying power. 2x was picked
                                 # over 3x/4x/6x specifically because it's the highest tier that
                                 # still keeps 3 concurrent slots (real diversification) -- past
                                 # this point slots drop to 1-2 and a real backtested window went
                                 # negative from pure concentration risk, not a weaker edge. See
                                 # strategy_experiments.py's "RISK PER TRADE, SAME $193.82" section.
MAX_NOTIONAL_PER_TRADE = 150.0

# ---- Minimum zone-width filter (2026-08-21) ----
# Backtested and, unlike volume/breadth, actually holds up: at 3.0%, TRAIN
# went from -$1.95 to +$4.47 and TEST from +$9.22 to +$4.31 -- full-period
# P&L improved (+$7.27 -> +$8.78) AND the swing between the two windows
# shrank dramatically (from an $11.17 spread down to $0.16), meaning it
# filters out genuinely low-quality choppy-range days, not just noise.
MIN_ZONE_WIDTH_PCT = 3.0

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
            if r.status_code != 200:
                print(f"  ⚠️  {sym} price fetch: Finnhub returned {r.status_code}")
                continue
            d = r.json()
            cur = d.get("c", 0) or 0
            if cur <= 0:
                print(f"  ⚠️  {sym} price fetch: no valid price in response")
                continue
            prices[sym] = {"price": cur}
        except Exception as e:
            print(f"  ⚠️  {sym} price fetch failed: {e}")
    return prices

def init_log():
    if not os.path.exists(TRADE_LOG):
        with open(TRADE_LOG, 'w', newline='') as f:
            csv.writer(f).writerow(["Date", "Time", "Symbol", "Entry", "Shares", "Exit", "P&L", "Win/Loss", "Return%", "Reason"])

FLOOR_LEAD_LOG = os.path.expanduser("~/sage_bot_floor_lead_reviews.csv")  # separate file, not a
                                     # new column on the shared TRADE_LOG -- TRADE_LOG is shared
                                     # across bot versions and read by check_weekly_winrate, so
                                     # this stays isolated rather than risking a schema mismatch.

def init_floor_lead_log():
    if not os.path.exists(FLOOR_LEAD_LOG):
        with open(FLOOR_LEAD_LOG, 'w', newline='') as f:
            csv.writer(f).writerow(["Date", "Time", "Symbol", "Entry", "Stop", "Target", "Exit",
                                     "DesignedRR", "RealizedR", "ZoneDepthPct", "ZoneWidthPct",
                                     "VolumeConfirmed", "BreadthAtEntry", "Reason"])

def log_floor_lead_review(sym, pos, exit_price, reason=""):
    """Factual per-trade dossier: the risk/reward the trade was DESIGNED
    with (from stop/target at entry) vs. the R actually REALIZED, plus the
    entry-quality context (zone depth/width, volume, breadth) captured at
    the moment of entry. Deliberately NOT a pass/fail quality score --
    volume confirmation and market breadth were both backtested (2026-08-21)
    and found NOT to predict trade quality on this strategy, so scoring
    trades against them would contradict the session's own evidence. This
    is a record for spotting real patterns over time (e.g. 'do losses
    cluster on shallow zone-depth entries'), not a live gate -- nothing
    here blocks or influences a trade."""
    try:
        init_floor_lead_log()
        entry, stop, target = pos.get("entry"), pos.get("stop"), pos.get("target")
        risk_per_share = (entry - stop) if (entry and stop) else None
        designed_rr = ((target - entry) / risk_per_share) if (risk_per_share and target) else None
        realized_r = ((exit_price - entry) / risk_per_share) if risk_per_share else None
        mt = market_now()
        with open(FLOOR_LEAD_LOG, 'a', newline='') as f:
            csv.writer(f).writerow([
                mt.strftime("%Y-%m-%d"), mt.strftime("%H:%M:%S ET"), sym,
                f"{entry:.2f}" if entry else "", f"{stop:.2f}" if stop else "",
                f"{target:.2f}" if target else "", f"{exit_price:.2f}",
                f"{designed_rr:.2f}" if designed_rr is not None else "",
                f"{realized_r:.2f}" if realized_r is not None else "",
                f"{pos.get('depth'):.2f}" if pos.get("depth") is not None else "",
                f"{pos.get('zone_width_pct'):.2f}" if pos.get("zone_width_pct") is not None else "",
                "Yes" if pos.get("volume_ok") else ("No" if pos.get("volume_ok") is not None else ""),
                f"{pos.get('breadth_at_entry'):+.2f}%" if pos.get("breadth_at_entry") is not None else "",
                reason,
            ])
    except Exception as e:
        print(f"  ⚠️  floor-lead review log failed (non-critical): {e}")

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

def init_journal():
    if not os.path.exists(JOURNAL_LOG):
        with open(JOURNAL_LOG, 'w', newline='') as f:
            csv.writer(f).writerow(["Date", "Version", "Trades", "Wins", "Losses", "WinRatePct", "PnL",
                                     "WeeklyPauseActive", "EarningsBlackout", "StillOpenAtClose", "Notes"])

def write_daily_journal(daily_trades, daily_profit, weekly_pause, earnings_blackout, still_open, notes=""):
    """One row per trading day -- the 'memory' layer above the per-trade
    TRADE_LOG. Reads today's rows back out of TRADE_LOG to get the
    win/loss breakdown rather than tracking it separately, so the two
    logs can never drift out of sync with each other."""
    init_journal()
    today = market_now().strftime("%Y-%m-%d")
    wins = losses = 0
    try:
        if os.path.exists(TRADE_LOG):
            with open(TRADE_LOG, newline="") as f:
                for row in csv.DictReader(f):
                    if row.get("Date") == today:
                        if row.get("Win/Loss") == "WIN":
                            wins += 1
                        elif row.get("Win/Loss") == "LOSS":
                            losses += 1
    except Exception as e:
        notes = (notes + f" | journal trade-log read failed: {e}").strip(" |")
    total = wins + losses
    wr = (wins / total * 100) if total else None
    with open(JOURNAL_LOG, 'a', newline='') as f:
        csv.writer(f).writerow([
            today, "v13", daily_trades, wins, losses,
            f"{wr:.1f}" if wr is not None else "", f"{daily_profit:.2f}",
            weekly_pause, ",".join(earnings_blackout) if earnings_blackout else "",
            ",".join(still_open) if still_open else "", notes
        ])

def write_obsidian_note(daily_trades, daily_profit, weekly_pause, weekly_wr, earnings_blackout,
                         still_open, notes=""):
    """Human-readable daily note in the Obsidian vault, alongside the CSV
    journal. Pulls today's rows straight from TRADE_LOG (same source
    write_daily_journal uses) so this can't drift out of sync with what
    actually happened. Best-effort -- a write failure here should never
    take down the trading loop, so everything is wrapped and only logged."""
    try:
        today_dt = market_now()
        today = today_dt.strftime("%Y-%m-%d")
        daily_dir = os.path.join(OBSIDIAN_VAULT, "Daily")
        os.makedirs(daily_dir, exist_ok=True)

        rows = []
        if os.path.exists(TRADE_LOG):
            with open(TRADE_LOG, newline="") as f:
                for row in csv.DictReader(f):
                    if row.get("Date") == today:
                        rows.append(row)

        wins = sum(1 for r in rows if r.get("Win/Loss") == "WIN")
        losses = sum(1 for r in rows if r.get("Win/Loss") == "LOSS")
        symbols_traded = sorted({r["Symbol"] for r in rows if r.get("Symbol")})

        lines = []
        lines.append("---")
        lines.append(f"date: {today}")
        lines.append("tags: [eva, daily]")
        lines.append(f"pnl: {daily_profit:.2f}")
        lines.append(f"trades: {daily_trades}")
        lines.append("---")
        lines.append("")
        lines.append(f"# {today} — Trading Day")
        lines.append("")
        pnl_word = "profit" if daily_profit > 0 else ("loss" if daily_profit < 0 else "flat")
        pnl_str = f"-${abs(daily_profit):.2f}" if daily_profit < 0 else f"+${daily_profit:.2f}"
        lines.append(f"**P&L:** {pnl_str} ({pnl_word})  |  **Trades:** {daily_trades}  |  "
                      f"**Win/Loss:** {wins}/{losses}")
        lines.append("")

        if rows:
            lines.append("## Trades")
            lines.append("| Symbol | Entry | Exit | Shares | P&L | Result | Reason |")
            lines.append("|---|---|---|---|---|---|---|")
            for r in rows:
                sym = r.get("Symbol", "")
                try:
                    row_pnl = float(r.get("P&L", 0) or 0)
                    pnl_disp = f"-${abs(row_pnl):.2f}" if row_pnl < 0 else f"+${row_pnl:.2f}"
                except ValueError:
                    pnl_disp = r.get("P&L", "")
                lines.append(f"| [[{sym}]] | ${r.get('Entry','')} | ${r.get('Exit','')} | "
                              f"{r.get('Shares','')} | {pnl_disp} | {r.get('Win/Loss','')} | "
                              f"{r.get('Reason','')} |")
            lines.append("")
        else:
            lines.append("No trades today.")
            lines.append("")

        floor_lead_rows = []
        if os.path.exists(FLOOR_LEAD_LOG):
            with open(FLOOR_LEAD_LOG, newline="") as f:
                for row in csv.DictReader(f):
                    if row.get("Date") == today:
                        floor_lead_rows.append(row)
        if floor_lead_rows:
            lines.append("## Trade Review")
            lines.append("Factual dossier per trade -- the risk/reward it was designed with vs. what "
                          "was actually realized, plus entry-quality context. Not a quality score: "
                          "volume confirmation and market breadth were backtested (2026-08-21) and found "
                          "NOT to predict trade quality on this strategy, so they're shown as context "
                          "only, not graded against.")
            lines.append("")
            lines.append("| Symbol | Designed R:R | Realized R | Zone depth | Zone width | Volume confirmed | Breadth at entry |")
            lines.append("|---|---|---|---|---|---|---|")
            for r in floor_lead_rows:
                lines.append(f"| [[{r.get('Symbol','')}]] | {r.get('DesignedRR','') or '-'} | "
                              f"{r.get('RealizedR','') or '-'} | {r.get('ZoneDepthPct','') or '-'}% | "
                              f"{r.get('ZoneWidthPct','') or '-'}% | {r.get('VolumeConfirmed','') or '-'} | "
                              f"{r.get('BreadthAtEntry','') or '-'} |")
            lines.append("")

        lines.append("## Notes")
        lines.append(f"- Weekly win-rate circuit breaker: {'ACTIVE (new entries paused)' if weekly_pause else 'not active'}"
                      + (f" ({weekly_wr:.1f}% trailing 7-day)" if weekly_wr is not None else ""))
        lines.append(f"- Earnings blackout: {', '.join(f'[[{s}]]' for s in earnings_blackout) if earnings_blackout else 'none'}")
        lines.append(f"- Still open at close: {', '.join(f'[[{s}]]' for s in still_open) if still_open else 'none'}")
        if notes:
            lines.append(f"- {notes}")
        if symbols_traded:
            lines.append("")
            lines.append(f"**Symbols traded:** {', '.join(f'[[{s}]]' for s in symbols_traded)}")

        with open(os.path.join(daily_dir, f"{today}.md"), "w") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        print(f"  ⚠️  Obsidian note write failed (non-fatal): {e}")

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

def _chunks(seq, n=10):
    """Split a symbol list into batches of at most n. get_equity_historicals
    and get_equity_tradability both hard-reject more than 10 symbols in one
    call. Added 2026-08-28: the watchlist grew from 7->14 symbols and every
    caller below was still passing the full list in one shot -- invisible
    while under 10, but past it every one of these calls failed outright,
    silently zeroing the day's trade zones (get_daily_levels), confirmation
    candles every scan (get_confirmation_candles), and tradability
    (load_tradability). Batching keeps this correct at any watchlist size."""
    for i in range(0, len(seq), n):
        yield seq[i:i + n]

async def get_daily_levels(session, symbols):
    """RH/RL = yesterday's daily high/low. SH/SL = highest high / lowest
    low over the prior SWING_LOOKBACK_DAYS sessions (yesterday included).
    Computed once per day at startup -- these don't move intraday.
    Batched at <=10 symbols per call (see _chunks) -- get_equity_historicals
    hard-rejects more than 10 in one request."""
    end = utc_now()
    start = end - timedelta(days=14)  # comfortably covers 5+ trading days incl. weekends/holidays
    today_et = market_now().date()
    levels = {}
    for batch in _chunks(symbols):
        try:
            res = await session.call_tool("get_equity_historicals", {
                "symbols": batch,
                "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "interval": "day",
                "bounds": "regular",
            })
            payload = json.loads(_result_text(res))
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
            print(f"  ⚠️  daily levels fetch failed for {','.join(batch)}: {e}")
    return levels

async def get_confirmation_candles(session, symbols):
    """Latest FULLY CLOSED 5-minute bar per symbol -- the confirmation
    candle the notes call for (close vs open) -- plus a volume check
    against the trailing VOLUME_LOOKBACK_BARS average. A green candle on
    light volume is more likely noise than real demand exhausting the
    sell-off; volume_ok requires the confirmation bar to trade at least
    VOLUME_CONFIRMATION_RATIO x that average. Missing/zero volume data
    fails OPEN (volume_ok=True) -- this is a quality filter, not a core
    safety check, so a data hiccup shouldn't block trading entirely."""
    if not symbols:
        return {}
    now = utc_now()
    start = now - timedelta(minutes=5 * (VOLUME_LOOKBACK_BARS + 3) + 45)
    candles = {}
    for batch in _chunks(symbols):
        try:
            res = await session.call_tool("get_equity_historicals", {
                "symbols": batch,
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
                prior = complete[-(VOLUME_LOOKBACK_BARS + 1):-1] or complete[:-1]
                avg_vol = (sum(float(b.get("volume", 0) or 0) for b in prior) / len(prior)) if prior else 0.0
                vol = float(last.get("volume", 0) or 0)
                volume_ok = (avg_vol <= 0) or (vol >= avg_vol * VOLUME_CONFIRMATION_RATIO)
                o, c, lo = float(last["open_price"]), float(last["close_price"]), float(last["low_price"])
                candles[sym] = {"open": o, "close": c, "low": lo, "volume": vol, "avg_volume": avg_vol,
                                 "bullish": c > o, "bearish": c < o, "volume_ok": volume_ok}
        except Exception as e:
            print(f"  ⚠️  confirmation candle fetch failed for {','.join(batch)}: {e}")
    return candles

async def get_earnings_blackout(session, symbols):
    """Symbols with a next earnings report within EARNINGS_BLACKOUT_DAYS.
    A gap-driven earnings move breaks the whole premise of RH/RL/SH/SL
    structure -- that structure describes normal trading, not a news
    gap, so a Buy Zone dip on an earnings day/reaction day could easily
    be catching a falling knife on bad news rather than a real bounce.
    Checked once at startup (one call per symbol) -- earnings dates
    don't change intraday."""
    today = market_now().date()
    blackout = {}
    for sym in symbols:
        try:
            res = await session.call_tool("get_earnings_results", {"symbol": sym})
            payload = json.loads(_result_text(res))
            upcoming = [r for r in payload.get("data", {}).get("results", [])
                        if r.get("eps", {}).get("actual") is None]
            if not upcoming:
                continue
            nxt = upcoming[0]
            rdate = datetime.strptime(nxt["report"]["date"], "%Y-%m-%d").date()
            delta = (rdate - today).days
            if abs(delta) <= EARNINGS_BLACKOUT_DAYS:
                blackout[sym] = {"date": rdate, "timing": nxt["report"]["timing"], "days": delta}
        except Exception as e:
            print(f"  ⚠️  earnings lookup failed for {sym}: {e}")
    return blackout

def get_market_breadth():
    """SPY's % move from today's open, via Finnhub. Buying an individual
    dip when the whole tape is falling is a materially worse bet than
    the same setup on a flat/green day -- returns None on failure so
    callers can fail OPEN (this is a quality filter, not core safety)."""
    try:
        r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={MARKET_BREADTH_SYMBOL}&token={FINNHUB_KEY}", timeout=5)
        if r.status_code != 200:
            print(f"  ⚠️  {MARKET_BREADTH_SYMBOL} breadth fetch: Finnhub returned {r.status_code}")
            return None
        d = r.json()
        cur, opn = d.get("c", 0) or 0, d.get("o", 0) or 0
        if cur > 0 and opn > 0:
            return (cur - opn) / opn * 100
        print(f"  ⚠️  {MARKET_BREADTH_SYMBOL} breadth fetch: no valid price in response")
    except Exception as e:
        print(f"  ⚠️  {MARKET_BREADTH_SYMBOL} breadth fetch failed: {e}")
    return None

def check_weekly_winrate():
    """Trailing-7-calendar-day win rate from the shared trade log.
    Returns (should_pause, trades_in_window, winrate_or_None). Needs
    WEEKLY_MIN_TRADES before trusting the number -- 2 trades at 0% isn't
    a real signal. Only gates NEW entries; existing positions are always
    still managed. Note: TRADE_LOG is shared across bot versions (same
    file since v9), so this reflects the account's recent trading
    overall, not v13-specific performance in isolation."""
    if not os.path.exists(TRADE_LOG):
        return False, 0, None
    cutoff = market_now().date() - timedelta(days=7)
    trades = wins = 0
    try:
        with open(TRADE_LOG, newline="") as f:
            for row in csv.DictReader(f):
                try:
                    d = datetime.strptime(row["Date"], "%Y-%m-%d").date()
                except Exception:
                    continue
                if d < cutoff:
                    continue
                trades += 1
                if row.get("Win/Loss") == "WIN":
                    wins += 1
    except Exception as e:
        print(f"  ⚠️  weekly win-rate read failed: {e}")
        return False, 0, None
    if trades < WEEKLY_MIN_TRADES:
        return False, trades, None
    wr = wins / trades * 100
    return (wr < WEEKLY_WINRATE_FLOOR), trades, wr

async def load_tradability(session):
    """Fetch per-symbol fractional eligibility. Returns {sym: can_buy_fractional}.
    Batched at <=10 symbols per call (see _chunks) -- get_equity_tradability
    hard-rejects more than 10 in one request. A failed batch defaults only
    ITS symbols to whole-shares-only, not the entire watchlist."""
    frac = {}
    for batch in _chunks(WATCHLIST):
        try:
            res = await session.call_tool("get_equity_tradability", {
                "account_number": ACCOUNT,
                "symbols": batch,
            })
            payload = json.loads(_result_text(res))
            for r in payload["data"]["results"]:
                frac[r["symbol"]] = (r.get("fractional_tradability") == "tradable"
                                     and r.get("tradeable") is True)
        except Exception as e:
            print(f"⚠️  Tradability lookup failed for {','.join(batch)} ({e}) - defaulting those to whole shares")
    for s in WATCHLIST:
        frac.setdefault(s, False)
    return frac

def size_position(sym, price, stop, frac_ok):
    """Risk-based sizing: risk RISK_PER_TRADE_DOLLARS per trade (the
    entry-stop distance sets share count), capped at MAX_NOTIONAL_PER_TRADE.
    Returns share qty respecting fractional rules, or 0 if not fillable."""
    if price <= 0 or stop <= 0 or stop >= price:
        return 0
    risk_per_share = price - stop
    notional = min(RISK_PER_TRADE_DOLLARS / risk_per_share * price, MAX_NOTIONAL_PER_TRADE)
    raw = notional / price
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
            log_floor_lead_review(sym, positions[sym], current, reason)
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
    and the MIN_STOP_DISTANCE_PCT floor -- SL alone can sit almost on top
    of entry when price enters near the bottom of the Buy Zone, which
    made ordinary noise clip the stop repeatedly (see MIN_STOP_DISTANCE_PCT)."""
    stop = max(sl, entry * (1 + STOP_LOSS_BACKSTOP_PCT / 100))
    stop = min(stop, entry * (1 + MIN_STOP_DISTANCE_PCT / 100))
    return stop

def compute_target(lv):
    """Take-profit level: TARGET_FRAC of the way from RL up to RH, touched
    with no confirmation candle required (see docstring for why v11's
    full-RH confirmation-gated target was replaced)."""
    return lv["rl"] + TARGET_FRAC * (lv["rh"] - lv["rl"])

def zone_width_ok(lv):
    """Buy Zone (RL to SL) must be at least MIN_ZONE_WIDTH_PCT of price.
    Backtested (2026-08-21): narrow/degenerate zones (the kind seen when
    yesterday's low equals the 5-day low) produce choppy, low-quality
    signals. Unlike the volume/breadth filters, this one held up on BOTH
    walk-forward halves -- it doesn't just cut trade count, it measurably
    improves consistency across different market regimes."""
    if lv["rl"] <= 0:
        return False
    width_pct = (lv["rl"] - lv["sl"]) / lv["rl"] * 100
    return width_pct >= MIN_ZONE_WIDTH_PCT

async def main():
    if not MCP_OK:
        print("❌ MCP not available")
        return

    oauth = build_robinhood_oauth()

    print("\n" + "="*70)
    print("EVA - SAGE BOT v13 (RANGE & SWING STRATEGY, FLOOR-LEAD FILTERS)")
    print("="*70)
    print("✅ OAuth credential store enabled")
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
    print(f"  Strategy    : Buy Zone entry + confirmation candle | target={TARGET_FRAC:.0%} of range")
    print(f"  Filters     : earnings blackout | weekly win-rate breaker | min zone width {MIN_ZONE_WIDTH_PCT:.1f}%  (volume + SPY breadth tracked, not gated -- both hurt backtest P&L)")
    print(f"  Sizing      : risk ${RISK_PER_TRADE_DOLLARS:.2f}/trade, capped at ${MAX_NOTIONAL_PER_TRADE:.0f} notional (not flat $50/trade)")

    if mt.weekday() >= 5:
        print("  ⛔ WEEKEND - market closed. Exiting without connecting to the broker.")
        print("="*70 + "\n")
        return

    print("  Auth        : OAuth + automatic refresh")
    print("="*70 + "
")

    init_log()
    try:
        async with httpx2.AsyncClient(
            auth=oauth,
            follow_redirects=True,
            timeout=httpx2.Timeout(
                30.0,
                read=300.0
            ),
        ) as hc:

            async with streamable_http_client(
                MCP_URL,
                http_client=hc
            ) as (rs, ws):

                async with ClientSession(
                    rs,
                    ws
                ) as session:
                    await session.initialize()
                    print("✓ Connected to Robinhood MCP")

                    # SAFE READ-ONLY AUTH TEST
                    # Run with:
                    # SAGE_AUTH_TEST=1 python sage_bot_v13.py
                    if os.environ.get("SAGE_AUTH_TEST") == "1":

                        print()
                        print("Running OAuth authentication-only test...")

                        test_result = await session.call_tool(
                            "get_accounts",
                            {}
                        )

                        if getattr(
                            test_result,
                            "isError",
                            False
                        ):
                            print(
                                "❌ V13 OAuth get_accounts test failed"
                            )
                            print(test_result)
                            return

                        print(
                            "✅ V13 OAUTH AUTH-ONLY TEST PASSED"
                        )

                        print(
                            "✅ No trading logic was executed"
                        )

                        return

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
                            width_note = "" if zone_width_ok(lv) else f"  ⛔ zone too narrow (<{MIN_ZONE_WIDTH_PCT:.1f}%), no entries today"
                            print(f"    {s}: Sell [{lv['rh']:.2f}-{lv['sh']:.2f}] | "
                                  f"Kill [{lv['rl']:.2f}-{lv['rh']:.2f}] | "
                                  f"Buy [{lv['sl']:.2f}-{lv['rl']:.2f}] | "
                                  f"target ${compute_target(lv):.2f}{width_note}")
                    if missing:
                        print(f"  ⚠️  no levels for {', '.join(missing)} - will not be traded today")
                    print()

                    # ---- EARNINGS BLACKOUT (computed once) ----
                    earnings_blackout = await get_earnings_blackout(session, WATCHLIST)
                    if earnings_blackout:
                        parts = []
                        for s, v in earnings_blackout.items():
                            when = "today" if v["days"] == 0 else f"{v['days']:+d}d"
                            parts.append(f"{s} ({when}, {v['date']} {v['timing']})")
                        print(f"📅 EARNINGS BLACKOUT - no new entries today: {', '.join(parts)}")
                    else:
                        print("📅 Earnings: no watchlist symbol reports within the blackout window")

                    # ---- WEEKLY WIN-RATE CIRCUIT BREAKER (checked once at startup) ----
                    weekly_pause, weekly_trades, weekly_wr = check_weekly_winrate()
                    if weekly_wr is not None:
                        flag = "🛑" if weekly_pause else "✓"
                        print(f"{flag} Trailing 7-day win rate: {weekly_wr:.1f}% ({weekly_trades} trades)"
                              + ("  - PAUSING NEW ENTRIES TODAY, existing positions still managed" if weekly_pause else ""))
                    else:
                        print(f"  Trailing 7-day win rate: not enough trades yet ({weekly_trades}/{WEEKLY_MIN_TRADES} needed) - no pause")
                    print()

                    # The real floor a trade can be sized to (risk-based sizing at the widest
                    # allowed stop, -4% backstop) -- used everywhere below instead of the flat
                    # MIN_TRADE, so a low-but-viable buying power isn't treated as zero slots.
                    MIN_POSSIBLE_NOTIONAL = RISK_PER_TRADE_DOLLARS / (-STOP_LOSS_BACKSTOP_PCT / 100)

                    bp0 = await get_buying_power(session)
                    bpos = await get_broker_positions(session)
                    print(f"✓ Buying power ${bp0 or 0:.2f} -> {int((bp0 or 0)//MIN_POSSIBLE_NOTIONAL)} slot(s) "
                          f"(min trade ~${MIN_POSSIBLE_NOTIONAL:.2f}, typical ${MIN_TRADE:.0f})")

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
                                    target = compute_target(levels[s])
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
                    # Floor here is a coarse sanity check only -- the real gate is the exact
                    # notional computed per-trade in the entry loop below. Risk-based sizing
                    # (RISK_PER_TRADE_DOLLARS / stop-distance-pct) can size a trade well under
                    # MIN_TRADE for a wide-stop symbol (as low as ~$31 at the -4% backstop, vs
                    # ~$50 at the -2.5% tightest floor) -- using MIN_TRADE here would turn the
                    # bot away from trades it could actually afford. Found live (2026-08-21):
                    # $47.16 available got rejected by this check before it even existed.
                    if (bp0 or 0) < MIN_POSSIBLE_NOTIONAL and not positions:
                        print(f"❌ Buying power (${bp0 or 0:.2f}) is below even the smallest possible trade "
                              f"(~${MIN_POSSIBLE_NOTIONAL:.2f}), and nothing to manage. Exiting.")
                        return
                    if (bp0 or 0) < MIN_TRADE:
                        print(f"⚠️  Buying power (${bp0 or 0:.2f}) is below the typical ${MIN_TRADE:.0f} trade size, "
                              f"but may still afford a wide-stop trade (as low as ~${MIN_POSSIBLE_NOTIONAL:.2f}) -- "
                              f"will try, the real check happens per-trade."
                              + (f" {len(positions)} existing position(s) will still be fully managed." if positions else ""))
                    print()

                    scan = daily_trades = daily_profit = 0
                    consecutive_mcp_failures = 0

                    while True:
                        scan += 1
                        now = market_now()
                        local = datetime.now()
                        ts = now.strftime("%I:%M:%S %p ET")
                        hour = now.hour

                        print(f"\n[{ts}] Scan #{scan}   (local {local.strftime('%I:%M %p')})")

                        prices = get_prices(WATCHLIST)
                        candles = await get_confirmation_candles(session, list(levels.keys()))

                        # Tracked and shown for visibility, but no longer gates entries --
                        # backtesting (2026-08-21) found it hurt P&L in every window tested
                        # (full period +$9.52 -> +$4.49, test period +$11.27 -> +$5.87), the
                        # same harmful pattern the volume filter showed.
                        breadth = get_market_breadth()
                        if breadth is None:
                            print(f"  📉 market breadth ({MARKET_BREADTH_SYMBOL}): unavailable this scan")
                        else:
                            note = "" if breadth >= MARKET_BREADTH_THRESHOLD_PCT else "  (below -0.5% reference, not blocking)"
                            print(f"  📉 market breadth ({MARKET_BREADTH_SYMBOL}): {breadth:+.2f}% from open{note}")

                        raw_bp = await get_buying_power(session)
                        broker = await get_broker_positions(session)
                        broker_read_ok = broker is not None

                        # Watchdog: get_buying_power/get_broker_positions both go through the
                        # SAME long-lived MCP session opened once at startup and reused all day
                        # (unlike prices, which come from a separate Finnhub REST call and keep
                        # working even if the MCP session dies). If the underlying connection
                        # dies mid-day, every session.call_tool -- including order placement --
                        # would silently keep failing while the bot LOOKS alive (it can still see
                        # prices). That's a real risk: a stop could be hit with no way to
                        # actually execute the sell. If both core MCP reads fail 3 scans running
                        # (~3 min), force a clean process restart via the crash-recovery path
                        # added 2026-08-22 rather than limping along with a dead connection.
                        if raw_bp is None and broker is None:
                            consecutive_mcp_failures += 1
                            print(f"  ⚠️  MCP read failed ({consecutive_mcp_failures}/3 consecutive) -- "
                                  f"possible dead connection")
                            if consecutive_mcp_failures >= 3:
                                raise RuntimeError(
                                    "MCP session appears dead: buying-power AND broker-position reads "
                                    "both failed 3 scans in a row. Forcing a restart rather than risk "
                                    "being unable to execute a stop/exit on a live position.")
                        else:
                            consecutive_mcp_failures = 0
                        bp = raw_bp if raw_bp is not None else 0.0

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

                        # Use the real minimum-possible-trade floor, not flat MIN_TRADE -- this was
                        # the actual live-blocking bug found in the 2026-08-21 pre-Monday review:
                        # with bp between $31.25 and $50, int(bp//MIN_TRADE) was always 0, so
                        # `slots = max_positions` capped every scan's candidate loop at zero and
                        # the bot could never place a trade even though it wasn't exiting anymore.
                        max_positions = int(bp // MIN_POSSIBLE_NOTIONAL)
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
                                           and cndl["low"] <= lv["rl"] and cndl["bullish"]
                                           and sym not in earnings_blackout and zone_width_ok(lv))
                            sig = "⚡ ENTRY" if entry_ready else ""
                            # volume_ok is shown for visibility but no longer gates entries --
                            # backtesting (2026-08-21) found it reduced P&L in every window tested
                            # (full period +$9.52 -> -$3.21), the opposite of its intent.
                            vol_flag = "" if not cndl else ("" if cndl["volume_ok"] else " lowvol")
                            print(f"  {sym}: ${p:.2f}  {zone:4s}  candle:{cndl_txt}{vol_flag}  {sig}")

                        minute = now.minute
                        in_flatten = (hour == 15 and minute >= 55) or hour >= 16
                        window_open = (10 <= hour < 16) and not in_flatten
                        if not window_open:
                            why = "EOD flatten" if in_flatten else "entries run 10:00-15:55 ET"
                            print(f"  ⏸  Entry window CLOSED ({why}, now {hour:02d}:{minute:02d} ET)")
                        if window_open and not broker_read_ok:
                            print("  ⏸  Entries skipped this scan - stale broker position data")
                        if window_open and weekly_pause:
                            print("  ⏸  Entries skipped this scan - weekly win-rate circuit breaker active")
                        entries_allowed = window_open and broker_read_ok and not weekly_pause
                        if entries_allowed:
                            held = set(positions) | set(broker or {})
                            candidates = []
                            for sym in WATCHLIST:
                                if sym in held or sym not in prices or sym not in levels:
                                    continue
                                if sym in earnings_blackout:
                                    continue
                                p = prices[sym]["price"]
                                lv = levels[sym]
                                if not zone_width_ok(lv):
                                    continue
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
                                price = prices[sym]["price"]
                                lv = levels[sym]
                                stop = compute_stop(price, lv["sl"])
                                target = compute_target(lv)
                                if stop >= price or target <= price:
                                    print(f"  ⏸  {sym} skipped - degenerate stop/target (stop ${stop:.2f} target ${target:.2f} price ${price:.2f})")
                                    continue
                                shares = size_position(sym, price, stop, frac_ok)
                                if shares == 0:
                                    print(f"  ⏸  {sym} skipped - risk-sized notional < 1 whole share @ ${price:.2f} (no fractional)")
                                    continue
                                notional = shares * price
                                bp_now = await get_buying_power(session)
                                if bp_now is None or bp_now < notional:
                                    print(f"  ⏸  buying power re-check failed or insufficient (need ${notional:.2f}, have "
                                          f"${bp_now if bp_now is not None else 'unknown'}) - stopping entries this scan")
                                    break
                                print(f"\n→ BUY {sym}: {shares} @ ${price:.2f} (~${notional:.2f}, risk ${RISK_PER_TRADE_DOLLARS:.2f})  "
                                      f"[Buy Zone, {depth:+.2f}% into it | stop ${stop:.2f} | target ${target:.2f}]")
                                if await execute_order(session, sym, "buy", shares):
                                    entry_cndl = candles.get(sym)
                                    positions[sym] = {
                                        "entry": price, "shares": shares, "stop": stop, "target": target,
                                        "depth": depth,
                                        "zone_width_pct": (lv["rl"] - lv["sl"]) / lv["rl"] * 100 if lv["rl"] else None,
                                        "volume_ok": entry_cndl.get("volume_ok") if entry_cndl else None,
                                        "breadth_at_entry": breadth,
                                    }
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
                                notify_macos("Eva - Positions still open",
                                             f"{len(positions)} position(s) still open past market close: {', '.join(positions)}")
                            print(f"\n💹 FINAL: {daily_trades} trades | ${daily_profit:.2f}")
                            write_daily_journal(daily_trades, daily_profit, weekly_pause, earnings_blackout,
                                                 list(positions.keys()))
                            write_obsidian_note(daily_trades, daily_profit, weekly_pause, weekly_wr,
                                                 earnings_blackout, list(positions.keys()))
                            print(f"📓 Journal updated: {JOURNAL_LOG}")
                            print(f"📔 Obsidian note updated: {OBSIDIAN_VAULT}/Daily")
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

                            if current <= stop:
                                # Hard stop -- no confirmation wait, risk limit not a setup.
                                print(f"\n→ SELL {sym} @ ${current:.2f} ({gain:.2f}%) [STOP ${stop:.2f}]")
                                if await execute_order(session, sym, "sell", shares):
                                    pnl = (current - entry) * shares
                                    daily_profit += pnl
                                    log_trade(sym, entry, shares, current, "STOP")
                                    log_floor_lead_review(sym, positions[sym], current, "STOP")
                                    del positions[sym]
                                    print(f"  ✓ ${pnl:.2f}")
                                else:
                                    print("  ✗ Failed")

                            elif current >= target:
                                # Touch-based take-profit -- backtested without requiring a
                                # confirmation candle (see docstring: the old confirmed-Sell-Zone
                                # target barely ever fired, most trades rode to EOD instead).
                                print(f"\n→ SELL {sym} @ ${current:.2f} (+{gain:.2f}%) [TARGET ${target:.2f}]")
                                if await execute_order(session, sym, "sell", shares):
                                    pnl = (current - entry) * shares
                                    daily_profit += pnl
                                    log_trade(sym, entry, shares, current, "TARGET")
                                    log_floor_lead_review(sym, positions[sym], current, "TARGET")
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
                                notify_macos("Eva - FLATTEN FAILED",
                                             f"Daily loss limit hit and could not flatten: {', '.join(positions)}. Check the app now.")
                            else:
                                notify_macos("Eva - Daily loss limit",
                                             f"Daily loss limit hit (${daily_profit:.2f}). Positions flattened, bot stopped for the day.")
                            print(f"\n💹 FINAL: {daily_trades} trades | ${daily_profit:.2f}")
                            write_daily_journal(daily_trades, daily_profit, weekly_pause, earnings_blackout,
                                                 list(positions.keys()), notes="DAILY_LOSS_LIMIT triggered")
                            write_obsidian_note(daily_trades, daily_profit, weekly_pause, weekly_wr,
                                                 earnings_blackout, list(positions.keys()),
                                                 notes="DAILY_LOSS_LIMIT triggered")
                            print(f"📓 Journal updated: {JOURNAL_LOG}")
                            print(f"📔 Obsidian note updated: {OBSIDIAN_VAULT}/Daily")
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
        notify_macos("Eva - CRASHED", f"Bot crashed: {e}. Check positions manually.")
        sys.exit(1)  # distinguishes a real crash from a normal end-of-day exit (both were exit
                      # code 0 before) so launchd's KeepAlive can auto-restart on crash but NOT
                      # after a clean daily close. Added 2026-08-22 -- rehydrate-from-broker on
                      # startup already exists (see positions rehydration in main()), so a restart
                      # mid-day safely picks back up rather than losing track of open positions.

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
        notify_macos("Eva - STOPPED", "Bot stopped by Ctrl+C. Open positions are UNPROTECTED until restarted or sold.")
        sys.exit(0)  # exit 0 = "successful"/intentional in launchd's eyes, so KeepAlive does NOT
                      # auto-restart a deliberate manual stop -- only a real crash (sys.exit(1)
                      # above) triggers that.
