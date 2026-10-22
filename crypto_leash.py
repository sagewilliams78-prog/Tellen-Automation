#!/usr/bin/env python3
"""
EVA CRYPTO DESK -- the short leash.

Every hard limit the 24/7 BTC trader runs under, in one place, so the caps
are auditable at a glance instead of buried in trading logic. crypto_btc_monitor.py
imports these -- it never defines its own numbers.

WHY THESE ARE SMALLER THAN THE EQUITY BOT'S:
The equity side (sage_bot_v13.py) risks $2.50/trade, caps notional at $150,
and force-flattens every position at 15:55 ET -- the market close is a real,
guaranteed backstop. Crypto has NO close. A position can run all night while
nobody is watching, and BTC routinely moves several percent in hours. So the
crypto desk gets a tighter leash than the equity desk, not an equal one:
one position at a time, tiny notional, and a hard max hold so nothing drifts
indefinitely.

KILL SWITCH:
    touch "_scheduled_state/CRYPTO_HALT"
That file's mere existence stops all new entries immediately and flattens any
open position on the next cycle. Delete it to resume. Checked every cycle,
before anything else -- no restart needed, no code change, works even if the
rest of this file is wrong.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATE_DIR = BASE / "_scheduled_state"

# ---- The leash -----------------------------------------------------------

# Max USD in a single position. A total loss of one position is capped here.
# Raised 25 -> 100 on 2026-08-31 at Sage's direction, for overnight/after-hours
# crypto trading.
#
# THIS NUMBER IS ONLY SAFE BECAUSE THE DUPLICATE-ORDER BUG IS FIXED.
# Found live the same night: when a fill did not confirm within 3 seconds the
# desk considered itself flat and bought AGAIN on the next cycle -- two real
# $25 orders, 65 seconds apart, $50 spent against a $25 cap. At $100 that same
# loop would have been $100 per minute. The fix is PENDING_FILE below plus the
# open-order check in crypto_btc_monitor.py's trade_cycle(). Do not raise this
# number again without re-reading both.
MAX_POSITION_USD = 100.00

# Only ever one open crypto position. No stacking, no averaging down.
MAX_OPEN_POSITIONS = 1

# Cumulative realized loss (USD, negative) that halts trading for the rest of
# the day. Roughly two full stop-outs -- if the day is going that badly, stop.
# Scaled with the position size (was -15 when the cap was $25). A 2% stop on a
# $100 position is $2, but an overnight gap can be far worse -- this is the
# brake that ends the day regardless of what any single stop did.
DAILY_LOSS_LIMIT_USD = -25.00

# Per-position exits, as percentages from the REAL fill price.
#
# Widened 2026-08-31 after a live discovery: Robinhood's BTC book was quoting
# bid $78,340 / ask $79,828 -- a 1.9% spread. The original -2%/+3% was
# unrunnable against that, because a market round-trip surrenders the whole
# spread before the trade does anything. These are set so normal friction is a
# fraction of the move, not the whole thing.
STOP_LOSS_PCT = -3.0
TAKE_PROFIT_PCT = 5.0

# ---- Spread guard --------------------------------------------------------
# The single most important number here. Crypto spreads widen when liquidity
# is thin (overnight, holidays), and a wide book silently converts a winning
# strategy into a losing one. Above this, the desk does not enter at all --
# it is not "waiting for a signal", it is refusing to pay the toll.
# Every cycle logs the real observed spread so this can be tuned from real
# data instead of a guess.
MAX_SPREAD_PCT = 1.00

# ---- Order style ---------------------------------------------------------
# LIMIT, never market, for entries and target exits. A market order crosses
# the spread by definition; on a 1.9% book that is the entire edge. Limits are
# placed at the MARK (midpoint) -- fair value, no toll paid -- and simply do
# not fill if the market never comes to us. A trade that does not happen costs
# nothing; a trade that crosses a 1.9% spread costs 1.9%.
ENTRY_LIMIT_TIMEOUT_MINUTES = 20

# A STOP exit is the one case where getting out matters more than price: the
# limit is placed at the bid (aggressive, but still not crossing). If it has
# not filled after this many cycles, the desk escalates to a market order --
# taking the spread hit is better than riding an uncapped loss.
STOP_ESCALATE_AFTER_CYCLES = 3

# Churn cap. Even a winning strategy shouldn't trade 40x/day on a $25 book --
# fees and slippage eat it alive.
# Raised 4 -> 6 on 2026-08-31 at Sage's direction. Still a real brake: the
# -$25 daily loss limit is the binding constraint, not this. Six round trips
# is the ceiling on churn, not a target -- most days should use far fewer.
MAX_TRADES_PER_DAY = 6

# Nothing is held longer than this. Crypto has no market close, so this IS the
# close: a position that hasn't hit stop or target in this long gets flattened
# on the next cycle regardless of P&L.
MAX_HOLD_HOURS = 8.0

# How often the desk wakes up. 60s matches the equity bot's scan cadence.
CYCLE_SECONDS = 60

# ---- Entry gate ----------------------------------------------------------
# Deliberately narrow. This mirrors the equity strategy's philosophy: most of
# the time the correct action is nothing. Enter only on the existing
# "BULLISH WATCH" state -- EMA20 > EMA50 (real uptrend) AND RSI in 45-65
# (not extended, not falling knife). "EXTENDED" (RSI >= 70) never enters.
ENTRY_SETUPS = {"BULLISH WATCH"}

# ---- Real account --------------------------------------------------------
# rhs_account_number, not account_number -- crypto tools require the numeric
# one (confirmed via get_accounts: 724375969 for the "Agentic" account).
RHS_ACCOUNT = "724375969"
SYMBOL = "BTC-USD"

# ---- Files ---------------------------------------------------------------
KILL_SWITCH = STATE_DIR / "CRYPTO_HALT"
POSITION_FILE = STATE_DIR / "crypto-position.json"
# Written the INSTANT an entry order is placed, before any fill confirms. Its
# existence blocks a second entry on the next cycle. This is the fix for the
# real duplicate-buy bug seen live 2026-08-31 -- see MAX_POSITION_USD above.
PENDING_FILE = STATE_DIR / "crypto-pending.json"
# How long a pending entry can stay unconfirmed before the desk stops waiting
# and clears it. Long enough for a slow fill, short enough that a genuinely
# failed order does not block trading all night.
PENDING_TIMEOUT_MINUTES = 10
DAY_FILE = STATE_DIR / "crypto-day.json"
TRADE_LOG = Path.home() / "crypto_trade_log.csv"

TRADE_LOG_COLUMNS = [
    "Date", "Time", "Symbol", "Entry", "Quantity", "Exit",
    "P&L", "Win/Loss", "Return%", "Reason",
]


def leash_summary():
    """One-line-per-rule summary, for logging at startup so the real caps are
    visible in the log rather than assumed."""
    return [
        f"max position      ${MAX_POSITION_USD:.2f}",
        f"max open          {MAX_OPEN_POSITIONS}",
        f"daily loss limit  ${DAILY_LOSS_LIMIT_USD:.2f}",
        f"stop / target     {STOP_LOSS_PCT:+.1f}% / {TAKE_PROFIT_PCT:+.1f}%",
        f"order style       LIMIT at mark (never crosses the spread)",
        f"max spread        {MAX_SPREAD_PCT:.2f}% -- above this, no entries",
        f"max trades/day    {MAX_TRADES_PER_DAY}",
        f"max hold          {MAX_HOLD_HOURS:.1f}h",
        f"entry setups      {', '.join(sorted(ENTRY_SETUPS))}",
        f"kill switch       touch {KILL_SWITCH}",
    ]
