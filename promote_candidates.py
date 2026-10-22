#!/usr/bin/env python3
"""
Widen the live watchlist from the screener's own backtested results.

This is NOT the nightly swap job (symbol_screener.py + watchlist_manager's
apply_swaps) -- that one changes WHICH 7 symbols are live, one-for-one,
every night, unattended. This is a deliberate, one-time GROWTH decision: take
the current watchlist and add more symbols to it, so more get scanned each
day. watchlist_manager.expand() exists specifically for this and explicitly
does not run automatically -- growing the floor is a considered decision a
human makes, not something a cron job should ever do on its own.

Selection is evidence-only. A symbol is eligible ONLY if:
  - it appears in last night's real screener backtest (_watchlist/screener-latest.json)
  - it cleared MIN_TRADES sampled trades, so the number isn't one lucky fill
  - its backtested P&L was actually POSITIVE
Ranked by real backtested P&L, highest first, until the watchlist reaches
TARGET_SIZE or eligible candidates run out -- whichever comes first.

TARGET_SIZE is a CEILING, not a quota. If the real universe only has, say,
seven symbols with a genuinely profitable backtest, the list grows to
7 + 7, not padded out to 20 with symbols that lost money in testing. Adding
a symbol because a slot needed filling is exactly the reasoning this project
has rejected everywhere else -- BTAI got dropped for exactly that.

Run it, read what it printed, then it's done -- current.json is updated and
the change is in the audit trail. The LIVE bot process does not see this
until its next restart (it reads WATCHLIST once at startup), so running this
mid-session cannot change what Eva is trading right now.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import watchlist_manager

SCREENER_FILE = os.path.join(watchlist_manager.DATA_DIR, "screener-latest.json")
MIN_TRADES = 3           # below this, a strong-looking pnl is likely noise
TARGET_SIZE = 20         # "scanning up to 20 stocks" -- Sage, 2026-08-26


def main():
    if not os.path.exists(SCREENER_FILE):
        print(f"No screener results at {SCREENER_FILE} -- nothing to promote from.")
        return 1

    with open(SCREENER_FILE) as f:
        screener = json.load(f)

    state = watchlist_manager.read_state()
    current = state["symbols"]
    room = TARGET_SIZE - len(current)
    if room <= 0:
        print(f"Watchlist already has {len(current)} symbols, at or above the "
              f"{TARGET_SIZE}-symbol target. Nothing to do.")
        return 0
    room = min(room, watchlist_manager.MAX_SYMBOLS - len(current))

    eligible = [r for r in screener.get("results", [])
                if r.get("trades", 0) >= MIN_TRADES
                and r.get("pnl", 0) > 0
                and r["symbol"] not in current]
    eligible.sort(key=lambda r: r.get("pnl", 0), reverse=True)
    picks = eligible[:room]

    skipped = len(screener.get("results", [])) - len(eligible) - len(current)
    if skipped > 0:
        print(f"{skipped} screened symbol(s) did NOT clear the bar (negative "
              f"backtest or fewer than {MIN_TRADES} trades) -- left out, "
              f"regardless of room available.\n")

    if not picks:
        print(f"No candidates in {SCREENER_FILE} clear the {MIN_TRADES}-trade, "
              f"positive-P&L bar and aren't already on the list. Nothing to do.")
        return 0

    if len(picks) < room:
        print(f"Target was {TARGET_SIZE}, but only {len(picks)} candidate(s) "
              f"actually cleared the bar -- growing to {len(current) + len(picks)}, "
              f"not padding the rest with losing backtests.\n")

    symbols = [p["symbol"] for p in picks]
    reason_bits = []
    for p in picks:
        bit = f"{p['symbol']} +{p['pnl']:.2f} ({p['trades']} trades, {p['winrate']:.0f}% WR)"
        if p.get("flags"):
            bit += f" [{', '.join(p['flags'])}]"
        reason_bits.append(bit)
    reason = (f"widened from {len(current)} to {len(current) + len(symbols)} symbols, "
              f"picked from the {screener.get('generated_at', 'last')} screener run "
              f"by real backtested P&L, {MIN_TRADES}+ sampled trades each: "
              + "; ".join(reason_bits))

    result = watchlist_manager.expand(symbols, reason=reason)

    print(f"Watchlist: {len(current)} -> {len(result['symbols'])} symbols")
    print(f"Added: {', '.join(result['added']) or '(none)'}")
    if result["refused"]:
        print("Refused:")
        for r in result["refused"]:
            print(f"  - {r}")
    print(f"\nFull list now: {', '.join(result['symbols'])}")
    print("\nThis takes effect at the bot's NEXT restart, not this session --")
    print("sage_bot_v13.py reads WATCHLIST once at startup.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
