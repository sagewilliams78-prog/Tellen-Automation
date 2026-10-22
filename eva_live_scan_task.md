---
name: eva-live-scan
description: Real-money trading pass for Eva -- runs every 5 minutes during market hours (10:00-16:00 ET), fires the same Buy Zone / confirmation-candle strategy as sage_bot_v13.py, on the same account, logging to the same files.
---

You are running one real trading pass for Eva, a real-money day-trading strategy on Robinhood account **724375969** (nickname "Agentic"). This replaces the old standalone `sage_bot_v13.py` process (which needed its own separately-managed credential file that kept expiring) -- you run this directly, using your own live Robinhood connection, on a 5-minute schedule instead of a continuous 60-second loop.

**Every number and rule below must trace to the real files in `/Users/sagewilliams/Desktop/Sages trading bot/` -- nothing here is invented, and nothing here should drift from what `sage_bot_v13.py` actually does.** If you're ever unsure what a rule means, read the real function in that file rather than guess -- it's still there, just not running as a standalone process.

## Real math -- always via eva_calc.py, never freehand

**Never compute zone classification, stop price, target price, zone width, or position size yourself.** Real money is on the line and arithmetic drift is a real risk. Always call:

```
python3 "/Users/sagewilliams/Desktop/Sages trading bot/eva_calc.py" <zone_of|compute_stop|compute_target|zone_width_ok|size_position> '<json args>'
```

It imports the exact same functions `sage_bot_v13.py` has always used. See the file's own docstring for exact argument shapes. It prints `{"ok": true, "result": ...}` on stdout (a stderr OpenSSL warning is normal, ignore it) or `{"ok": false, "error": ...}` -- if `ok` is false, STOP and report the error, don't guess a workaround.

## Real constants (read them from sage_bot_v13.py, do not hardcode a stale copy here)

```
python3 -c "
import sys; sys.path.insert(0, '/Users/sagewilliams/Desktop/Sages trading bot')
import sage_bot_v13 as e
print('RISK_PER_TRADE_DOLLARS', e.RISK_PER_TRADE_DOLLARS)
print('MAX_NOTIONAL_PER_TRADE', e.MAX_NOTIONAL_PER_TRADE)
print('DAILY_LOSS_LIMIT', e.DAILY_LOSS_LIMIT)
print('TARGET_FRAC', e.TARGET_FRAC)
print('WEEKLY_WINRATE_FLOOR', e.WEEKLY_WINRATE_FLOOR)
print('WEEKLY_MIN_TRADES', e.WEEKLY_MIN_TRADES)
print('EARNINGS_BLACKOUT_DAYS', e.EARNINGS_BLACKOUT_DAYS)
"
```
Run this once per invocation so a future edit to the real strategy file is picked up automatically, never silently stale.

## Real files (same ones the dashboard and HQ already read -- do not change these paths)

- Watchlist: `/Users/sagewilliams/Desktop/Sages trading bot/_watchlist/current.json` (real symbols, `.symbols` array)
- Trade log: `~/trading_log_v9.csv` (append via `log_trade`-equivalent -- same columns: Date,Time,Symbol,Entry,Shares,Exit,P&L,Win/Loss,Return%,Reason)
- Daily journal: `~/sage_bot_daily_journal.csv`
- Floor-lead reviews: `~/sage_bot_floor_lead_reviews.csv`
- **New, for this scheduled version only** (sage_bot_v13.py never needed these since it held state in memory):
  - `/Users/sagewilliams/Desktop/Sages trading bot/_scheduled_state/positions.json` -- open positions this system opened: `{SYMBOL: {entry, shares, stop, target, depth, zone_width_pct, volume_ok, breadth_at_entry, opened_at}}`
  - `/Users/sagewilliams/Desktop/Sages trading bot/_scheduled_state/levels-YYYY-MM-DD.json` -- today's real RH/RL/SH/SL per symbol, computed once, reused all day (these don't move intraday -- see `get_daily_levels`'s own docstring)
  - `/Users/sagewilliams/Desktop/Sages trading bot/_scheduled_state/halted-YYYY-MM-DD.json` -- written only if the daily loss limit fires; its presence means STOP trading for the rest of that date

## Steps, in order

1. **Check real time.** `date` for local time; the strategy runs in ET. If it's a weekend, or before 10:00 ET, or at/after 16:00 ET, this is a normal, expected stop, not a failure -- **but still do step 13** before stopping (write a real, honest status file: `symbols: []`, `managed: 0`, `window_closed: true`, real current time). Without that write, the dashboard shows the last real scan frozen forever and looks broken/dead instead of correctly idle -- an honest "0 symbols, market's closed" is very different from a stale scan pretending to be current, and the dashboard needs to be able to tell those apart.

2. **Load the real watchlist** from `_watchlist/current.json`.

3. **Get/refresh today's real levels.** Check `_scheduled_state/levels-<today>.json`. If it doesn't exist yet today, compute it for real: call `get_equity_historicals` for the watchlist symbols, **batched at <=10 symbols per call** (it hard-rejects more -- this exact bug is why the standalone bot went dark on 2026-08-28, don't repeat it), `start_time` 14 days back, `interval: "day"`, `bounds: "regular"`. For each symbol, RL/RH = yesterday's real low/high, SL/SH = the lowest low / highest high over the last 5 trading sessions including yesterday (see `SWING_LOOKBACK_DAYS` in sage_bot_v13.py for the exact real number), with SH >= RH and SL <= RL enforced. Write the result to the day's levels file. If it already exists, just read it -- don't recompute.

4. **Get real confirmation candles.** `get_equity_historicals` for the watchlist, batched at <=10, `interval: "5minute"`, last ~90 minutes, `bounds: "regular"`. For each symbol take the latest FULLY CLOSED 5-minute bar (begins_at more than 5 minutes ago). A candle is "bullish" if close > open.

5. **Get real live prices.** `get_equity_quotes` for the watchlist.

6. **Get real earnings blackout.** `get_earnings_results` per symbol (one call each, it's not batch-limited) -- if next earnings report is within `EARNINGS_BLACKOUT_DAYS`, that symbol is blacked out today. Skip this step if it was already done today (cache alongside the levels file) -- earnings dates don't change intraday.

7. **Get the real weekly win-rate breaker.** Read `~/trading_log_v9.csv`, filter to the trailing 7 calendar days, and if there are at least `WEEKLY_MIN_TRADES`, compute the real win rate. If below `WEEKLY_WINRATE_FLOOR`, new entries are paused today (existing positions are still managed).

8. **Get real broker positions.** `get_equity_positions` for account 724375969 -- this is the real source of truth, not the state file. Reconcile: any symbol in `_scheduled_state/positions.json` no longer at the broker gets removed from the state file (already closed some other way). Any symbol at the broker not in the state file is **held by something else -- do not touch it, do not sell it, do not count it as yours.**

9. **Check `_scheduled_state/halted-<today>.json`.** If present, skip straight to step 11 (exits only, no new entries) -- the daily loss limit already fired today.

10. **Exits, for every symbol in the (reconciled) state file:**
    - If current price <= stored stop: **SELL immediately**, no confirmation needed. Real order via `place_equity_order` (side sell, type market, time_in_force gfd, market_hours regular_hours, quantity = stored shares). On confirmed success: append the real trade to `~/trading_log_v9.csv` and `~/sage_bot_floor_lead_reviews.csv` (reason "STOP"), remove the symbol from `positions.json`.
    - Else if current price >= stored target: same SELL flow, reason "TARGET".
    - If it's 15:55 ET or later (EOD flatten window) or 16:00 ET or later: **SELL every remaining open position unconditionally**, reason "EOD_FLATTEN", regardless of stop/target. If it's past 16:00 ET, do this and then stop for the day after logging (write the daily journal entry, same as `write_daily_journal` -- real trade count and real P&L summed from today's real log rows).

11. **Entries** -- only if: within 10:00-15:55 ET, not halted today, weekly breaker not paused, and a real broker-position read succeeded this pass.
    - For each watchlist symbol not already held (by this system OR anyone else) and not earnings-blacked-out: compute `zone_of` via eva_calc.py. If "BUY" and `zone_width_ok` and the 5-min confirmation candle's low <= RL and it's bullish -> it's a real candidate. Rank candidates by how deep into the zone they are (deepest first).
    - Real available slots = `int(buying_power // (RISK_PER_TRADE_DOLLARS / 0.04))` (the real minimum-possible-notional floor sage_bot_v13.py uses -- read it from the constants dump in the step above rather than hardcoding here). Get real buying power via `get_portfolio`.
    - For each candidate, up to the real slot count: compute stop via `compute_stop`, target via `compute_target`, shares via `size_position` (needs real fractional-tradability -- call `get_equity_tradability` for the account, batched at <=10). If stop >= price or target <= price or shares == 0, skip that symbol (log why, don't force a trade). Re-check real buying power immediately before each order; if it's no longer sufficient, stop placing entries this pass.
    - Place the real order via `place_equity_order` (side buy, type market). On confirmed success, write the position into `_scheduled_state/positions.json` with all the real fields (entry, shares, stop, target, depth, zone_width_pct, volume_ok, breadth_at_entry, opened_at = now).

12. **Daily loss limit.** Sum today's real P&L from `~/trading_log_v9.csv` (rows dated today). If <= `DAILY_LOSS_LIMIT`, flatten every remaining open position for real (same SELL flow, reason "DAILY_LOSS_LIMIT"), write `_scheduled_state/halted-<today>.json`, and stop.

13. **Always, as your last step -- INCLUDING when you stopped early at step 1 for being outside market hours -- write the real dashboard status file**, `_scheduled_state/live-scan-status.json`. This is what the HQ dashboard actually reads now -- `sage_bot_v13.py`'s old log is retired and will never advance again, so without a fresh write every single pass, the whole dashboard (Watchlist Wing, Bank, Tax Office, wall display) freezes on whatever the last real scan happened to be and looks broken/dead, even on a normal closed-market pass. Bump a real running counter (`_scheduled_state/scan_counter.json`, plain `{"n": <int>}`, increment by 1 each real pass -- start at 0 if the file doesn't exist) and write:
    ```json
    {
      "generated_at": "<real ISO timestamp, now>",
      "scan_num": <the bumped counter>,
      "time": "<real current ET time, e.g. '02:15:00 PM ET'>",
      "buying_power": <real float from get_portfolio, or null if outside hours and not checked>,
      "managed": <real count of open positions from the broker read, or 0 if outside hours and not checked>,
      "room_for": <real max_positions computed this pass, or 0 if outside hours>,
      "breadth": <real SPY % from open if you checked it, else null>,
      "market_closed": <true only on a weekend stop, else false>,
      "window_closed": <true on an outside-hours weekday stop (before 10:00 or at/after 16:00 ET), else false>,
      "symbols": [
        {"symbol": "IBRX", "price": 7.99, "zone": "BUY", "candle": "bull",
         "lowvol": false, "entry_flag": true, "buy_low": 7.46, "buy_high": 8.18,
         "target": 8.32, "narrow": false, "distance_pct": null}
        // one real entry per watchlist symbol you actually priced this pass -- EMPTY ARRAY on an
        // outside-hours stop, and that's correct: zero symbols really were scanned, say so plainly
      ],
      "earnings_blackout": ["<real symbols in blackout today, if any>"],
      "weekly_status": "<the real weekly win-rate line, same wording style as sage_bot_v13.py's own>"
    }
    ```
    Every field must be real -- pulled from what you actually computed/fetched this pass, or an honest empty/null/zero when you correctly didn't need to check something (outside hours). Never skip this write and never backfill a placeholder number.

14. **Also update `~/.eva_mechanic_status.json`** with a new `live_scan` key (same shape as `hourly`/`morning`: `last_run`, `status`, `summary`) so the dashboard's mechanic panel shows this is actually running, the same way the other mechanics already do.

## Standing rules

- Never place an order outside real, computed conditions above -- no discretionary trades, no "this looks like a good time," no reacting to news you weren't asked to check.
- Never invent a price, a level, or a P&L number. Every real number comes from a real tool call or a real file read in this pass.
- If any real data read fails (prices, positions, buying power), do not guess and do not place an entry on stale/missing data -- skip entries this pass and say so in the status update. Exits (stop/target/EOD) still matter even on a bad data pass -- don't skip a real stop because one other read failed, unless the price itself is what's missing for that symbol.
- If something looks genuinely wrong and you're not confident continuing is safe, stop and don't guess -- this handles real money.
