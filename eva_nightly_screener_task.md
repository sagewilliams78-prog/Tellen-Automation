---
name: eva-nightly-screener
description: Scans for new stocks each night, backtests every candidate, and updates Eva's watchlist for the next trading day — max 2 swaps, never dropping a symbol with an open position.
---

This is an automated run of a scheduled task. Sage is not present. This job changes what a REAL-MONEY trading bot will trade tomorrow, so be careful and be honest in the log — if something looks wrong, make no change and say so.

You are running the nightly watchlist refresh for **Eva**, Sage's live day-trading strategy on Robinhood account 724375969. Whatever you decide here takes effect at tomorrow's open, read by `eva-live-scan` from `_watchlist/current.json`.

Working directory for everything below: `/Users/sagewilliams/Desktop/Sages trading bot`

**Rebuilt 2026-08-28.** The old version of this task shelled out to `symbol_screener.py`'s own standalone MCP session, which read a separately-managed credential (`~/.sage_robinhood_auth.json`) that has no supported way to renew itself — the exact same dead end that killed the old standalone `sage_bot_v13.py` process. This version uses **your own live Robinhood connection** instead (the same one you're running with right now), the same fix already proven working in `eva-live-scan`. `symbol_screener.py`'s real backtest math (`backtest_symbol`, `levels_for_day`, `zone_of`, `zone_width_ok`) is untouched and still the one source of truth — reached now through `screener_calc.py`, never re-derived by hand. Real money is downstream of this decision; arithmetic drift here is a real risk, same as `eva-live-scan`.

**Important real constraint, confirmed 2026-08-28:** fetching your own tool results has a response-size cap that a raw HTTP script never hits — a single `get_equity_historicals` call for one symbol's 5-minute bars over more than ~3 calendar days can exceed it. This is NOT the same as the API's ~5000-bar/symbol cap; it's tighter, and it is why this version fetches 5-minute bars in small per-symbol chunks (below) and only scans a rotating slice of the full universe each night rather than all of it at once — scanning everything in one run is not practical at this granularity.

## Real math — always via screener_calc.py, never freehand

**Never simulate the day-by-day backtest walk yourself, and never classify a zone or width by hand.** Always call:
```
python3 "/Users/sagewilliams/Desktop/Sages trading bot/screener_calc.py" backtest '<json args>'
python3 "/Users/sagewilliams/Desktop/Sages trading bot/screener_calc.py" constants '{}'
```
`backtest` takes `{"daily_bars": [...], "fivemin_bars": [...], "blackout_days": ["YYYY-MM-DD", ...]}` — raw bars exactly as `get_equity_historicals` returns them for ONE symbol — and returns `{"trades": n, "wins": n, "pnl": float, "winrate": float}`, computed by the real, unmodified `symbol_screener.py` engine. If `ok` is false, STOP and report the error for that symbol, don't guess a workaround; skip that symbol this run rather than force it.

`constants` returns the real, current `CANDIDATE_UNIVERSE`, `SEMI_CORRELATED`, `HIGH_VOL_PROXY`, `MIN_PRICE`, `MAX_PRICE`, `EARNINGS_BLACKOUT_DAYS`, `SWING_LOOKBACK_DAYS`, `MIN_ZONE_WIDTH_PCT`, `PASS_MIN_TRADES`. Read it live every run — never hardcode a stale copy here.

## Real files

- Current watchlist: `_watchlist/current.json` (`.symbols` array) — managed by `watchlist_manager.py`. **Never edit `sage_bot_v13.py`.**
- Rotation state: `_watchlist/screener_rotation.json` — `{"queue": [symbols...], "cursor": <int>}`. If missing, build `queue` fresh (see step 2) and start `cursor` at 0.
- Rolling real results: `_watchlist/screener-latest.json` — `{"results": {SYMBOL: {trades, wins, pnl, winrate, tradable, price_ok, flags, computed_at}}}`. Each night only overwrites the symbols actually scanned that run; everything else carries forward unchanged. Real per-symbol freshness varies night to night by design — that's fine, the swap decision (step 6) uses whatever real numbers are present.
- Status: `_watchlist/nightly_status.json` (same shape as before).

## Steps, in order

1. **Get real live constants and the real current watchlist.** Call `screener_calc.py constants`. Read `_watchlist/current.json`.

2. **Build/refresh the rotation queue.** The full real universe = `CANDIDATE_UNIVERSE` ∪ current watchlist symbols (a symbol can be both — incumbents need real backtest numbers too, that's what step 6 compares against). If `_watchlist/screener_rotation.json` doesn't exist, or its `queue` (as a set) no longer matches this full universe (watchlist changed since it was built), rebuild `queue` as this full universe in a stable sorted order and reset `cursor` to 0.

3. **Pick tonight's batch.** Take **5 symbols** starting at `cursor` (wrapping around to the start of `queue` if it runs past the end). This keeps one run's real tool-call count bounded — do not scan more than this in one run, even if it seems fine early on.

4. **For each symbol in tonight's batch, fetch real data:**
   - Real tradability: `get_equity_tradability` for account `724375969`, batched with the rest of tonight's batch (≤10 symbols, tonight's batch of 5 fits in one call).
   - Real daily bars: `get_equity_historicals`, same batched call, `interval: "day"`, `start_time` 100 days back, `bounds: "regular"`. Skip a symbol immediately (log why) if not tradable or last close is outside `[MIN_PRICE, MAX_PRICE]` — don't spend the expensive 5-minute fetch on a symbol that will fail anyway.
   - Real 5-minute bars, **per symbol, chunked at ≤3 calendar days per call** (the real constraint above): loop from 84 days back to now in 3-day steps, one `get_equity_historicals` call per step (`interval: "5minute"`, `bounds: "regular"`), concatenating the real bars. If any chunk call still errors on size, halve that chunk's window and retry once; if it still fails, skip that symbol for tonight and log why — never substitute synthetic bars.
   - Real earnings: `get_earnings_results` for the symbol (one call, not batched). Build the real blackout date set: for each real report date, the calendar dates within `EARNINGS_BLACKOUT_DAYS` on either side that also fall inside the 84-day backtest window.

5. **Backtest each symbol for real.** Call `screener_calc.py backtest` with that symbol's real daily/5-minute bars and real blackout days. Merge the real result into `_watchlist/screener-latest.json` under that symbol, with real `tradable`, `price_ok`, `flags` (`"correlated-w/AMD-NVDA"` if in `SEMI_CORRELATED`, `"high-vol-proxy"` if in `HIGH_VOL_PROXY`), and `computed_at` = now. Advance `cursor` by 5 (wrapping) and write `_watchlist/screener_rotation.json`.

6. **Decide and apply — at most 2 swaps**, using the full real `_watchlist/screener-latest.json` (tonight's fresh numbers plus whatever's still on record for symbols not scanned tonight):
   - Get real open positions: `get_equity_positions` for account 724375969. If this call fails, make no change this run and log the failure — never guess at what's held.
   - Passers = candidates (not currently on the watchlist) with `pnl > 0` and `trades >= PASS_MIN_TRADES`, ranked by real P&L.
   - Weakest incumbents = current watchlist symbols with a real backtest on record, ranked by real P&L ascending.
   - Only propose a swap where a real passer's P&L genuinely beats a real weakest incumbent's P&L. Prefer no change over a marginal one. Be wary of `flags` — don't stack the watchlist with correlated or high-vol-proxy names.
   - Apply via:
     ```
     python3 -c "
     import watchlist_manager as w, json
     r = w.apply_swaps(add=[...], drop=[...], open_positions=[...], reason='nightly screener YYYY-MM-DD: <why, with the real numbers>')
     print(json.dumps(r, indent=2))
     "
     ```
     `watchlist_manager` enforces the rails itself (refuses to drop a held symbol, caps at 2 swaps, keeps the list 1-for-1). **Read the `refused` list and report it verbatim** — a refusal is information, not an error.

7. **Always, as your last step, write what actually happened** to `_watchlist/nightly_status.json`:
   ```
   python3 -c "
   import json
   from datetime import datetime
   json.dump({'last_run': datetime.now().astimezone().isoformat(),
              'status': 'changed',   # changed | no_change | blocked
              'summary': 'One real specific sentence: symbols scanned tonight, real numbers, and the real decision (or why blocked).'},
             open('_watchlist/nightly_status.json','w'), indent=2)
   "
   ```

## Standing rules

- Never edit `sage_bot_v13.py`.
- Never place, cancel, or modify an order. Never call any trading tool. `get_equity_positions` is the only account call you need, and it's read-only.
- Never add a symbol that did not pass the real backtest gate.
- Never drop a symbol with an open position — the manager blocks this, don't try to work around it.
- Never exceed 2 swaps, never exceed 5 symbols scanned in one run.
- Never invent a bar, a P&L number, or a trade count. Every number traces to a real tool call this run, or a real `computed_at` result already on record from a previous run.
- If in doubt, change nothing and log why.
