#!/usr/bin/env python3
"""
What SHOULD EVA Crypto's score threshold be?

THE GAP THIS FILLS
------------------
The equity desk got the score-not-gates treatment and got measured:
eva_score.py replaced an AND-ed cascade with a 0-30 score and checked it on 96
sessions across three splits ($15.81 -> $48.21, PF 1.19 -> 1.61, green days
42% -> 52%), with 21/22/23 all winning -- a plateau, not a spike.

The crypto desk never got that. crypto_config.json still says, in its own words:

    "PROVISIONAL and explicitly uncalibrated. The brief is right that these
     must be set by historical testing, not opinion. Until walk-forward
     validation exists, only high_conviction (80+) is permitted to trade."

This is that historical testing. It does NOT assume 80 is wrong. It asks what
the data says, using the discipline sim_lookback.py already applies: three
independent splits, judged against the SHIPPED value, and a change counts only
if it wins on ALL THREE. If 80 survives, "80 stands" is the answer and this
file has still done its job.

THE MECHANISM
-------------
For each evaluation timestamp T, slice every timeframe's candles to bars at or
before T, hand those to the REAL crypto_data.analyze_timeframe(), classify with
the REAL crypto_regime.classify_asset(), and score with the REAL
crypto_signals.score_asset(). No scoring logic is reimplemented here -- that is
exactly the drift failure eva_score.py's header warns about, where the backtest
quietly stops describing the thing that actually trades.

Then simulate the trade the config actually specifies: entry at mark, +10%
target, -3% stop, 120h max hold, 1.90% round-trip cost, one position at a time,
risk-sized under the configured notional cap.

WHAT THIS CANNOT SEE -- read before believing any number it prints
------------------------------------------------------------------
1. NO HISTORICAL ORDER BOOK. Coinbase candles carry no bid/ask, so
   score_order_book() is pinned to its neutral 0.5 on every bar. That factor
   carries weight 8, so a backtest score can differ from a live score by up to
   +/-4 points from this alone. Any "winner" within 4 points of the shipped
   value is noise. The verdict block flags this automatically.

2. SPREAD ASSUMED STRUCTURAL. The config measured 1.89-1.90% across three
   assets within 0.01pp and concluded it is Robinhood's revenue model, not a
   liquidity artifact. This uses that measured constant. If spread actually
   widened during the window, this is optimistic.

3. TWO VENUES. Signals from Coinbase, fills would be Robinhood. The config
   already caps that disagreement at 2.5%; this cannot detect a day it blew out.

4. REGIME COVERAGE IS THE REAL LIMIT. eva_score.py's own note -- "one dataset,
   one rallying regime, never seen a downtrend" -- applies double here. The run
   prints the regime mix it sampled and warns when it is one-sided. A threshold
   fitted to one regime is a threshold for one regime.

5. LIMIT FILLS ASSUMED AT MARK, and no slippage beyond the round trip. Both
   flatter the result.

CADENCE
-------
Default is hourly, not 5-minutely. This system holds up to 120 hours; scoring
it every five minutes is false precision that multiplies runtime by twelve
without adding an independent observation. Override with --cadence.

USAGE
-----
    python3 sim_crypto_threshold.py --dry-run          # imports + shapes, no fetch
    python3 sim_crypto_threshold.py --days 180         # fetch, cache, sweep
    python3 sim_crypto_threshold.py --days 180 --no-cache

Candles cache under _crypto_state/_calib_cache/ so repeat sweeps do not refetch.

NOTE ON THE FETCHER: crypto_data.fetch_candles() takes no start/end and returns
only the most recent 300 bars, so it cannot page. Paging is implemented here
against the same endpoint, returning crypto_data's exact row shape. The 4h
frame is built by aggregating 1h bars, mirroring fetch_all_timeframes(),
because Coinbase does not serve 14400s natively.
"""

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from bisect import bisect_right
from collections import Counter
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BOT_DIR))

import crypto_data          # noqa: E402
import crypto_regime        # noqa: E402
import crypto_signals       # noqa: E402

CACHE_DIR = BOT_DIR / "_crypto_state" / "_calib_cache"

MAX_CANDLES_PER_REQUEST = 300
POLITE_SLEEP_SECONDS = 0.35

# analyze_timeframe needs ema50 (50 bars) plus swing_structure/vwap/volume_ratio
# at lookback 20. 60 is the floor below which it returns Nones that quietly
# degrade the score rather than failing loudly.
MIN_BARS = 60
WINDOW_BARS = 300


# --------------------------------------------------------------------------
# FETCH  (paged -- crypto_data.fetch_candles cannot do this)
# --------------------------------------------------------------------------

def _fetch_window(pair, granularity, start, end, cfg, timeout=20):
    """One Coinbase request, returned in crypto_data's row shape."""
    base = cfg["data"]["coinbase_rest"]
    url = (f"{base}/products/{crypto_data.coinbase_product(pair)}/candles"
           f"?granularity={granularity}&start={int(start)}&end={int(end)}")
    req = urllib.request.Request(url, headers={"User-Agent": "EvaCryptoCalib/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = json.loads(r.read().decode())

    rows = []
    for item in raw:
        if not isinstance(item, list) or len(item) < 6:
            continue
        ts, low, high, open_, close, volume = item[:6]
        rows.append({"time": float(ts), "low": float(low), "high": float(high),
                     "open": float(open_), "close": float(close),
                     "volume": float(volume)})
    rows.sort(key=lambda x: x["time"])
    return rows


def fetch_history(pair, granularity, days, cfg, use_cache=True):
    """Page backwards until `days` of history is collected. Oldest first."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{pair}_{granularity}_{days}d.json"

    if use_cache and cache_file.exists():
        rows = json.loads(cache_file.read_text())
        print(f"    {pair:<9} {granularity:>6}s: {len(rows):>6} bars (cached)")
        return rows

    span = granularity * MAX_CANDLES_PER_REQUEST
    now = int(time.time())
    floor_t = now - days * 86400

    collected, cursor, requests_made, failures = {}, now, 0, 0
    while cursor > floor_t:
        window_start = max(cursor - span, floor_t)
        try:
            rows = _fetch_window(pair, granularity, window_start, cursor, cfg)
            requests_made += 1
        except (urllib.error.URLError, urllib.error.HTTPError,
                ValueError, OSError) as e:
            failures += 1
            if failures >= 3:
                print(f"    {pair:<9} {granularity:>6}s: giving up after 3 "
                      f"failures ({type(e).__name__}: {e})")
                break
            time.sleep(2.0)
            continue

        if not rows:
            break
        for r in rows:
            collected[r["time"]] = r
        oldest = min(r["time"] for r in rows)
        if oldest >= cursor:
            break
        cursor = int(oldest)
        time.sleep(POLITE_SLEEP_SECONDS)

    out = [collected[t] for t in sorted(collected)]
    if out:
        cache_file.write_text(json.dumps(out))
    print(f"    {pair:<9} {granularity:>6}s: {len(out):>6} bars "
          f"({requests_made} requests)")
    return out


def build_frames(pair, days, cfg, use_cache=True):
    """All four configured frames. 4h is aggregated from 1h exactly the way
    crypto_data.fetch_all_timeframes() does it, because Coinbase does not
    serve 14400s natively (confirmed in crypto_data's own comment)."""
    gran = cfg["data"]["candle_granularity_seconds"]
    frames = {}
    for name, seconds in gran.items():
        if seconds in crypto_data.COINBASE_GRANULARITIES:
            frames[name] = fetch_history(pair, seconds, days, cfg, use_cache)
            continue
        source = max((g for g in crypto_data.COINBASE_GRANULARITIES
                      if seconds % g == 0 and g < seconds), default=None)
        if source is None:
            raise RuntimeError(f"{name} ({seconds}s) cannot be aggregated")
        factor = seconds // source
        base_rows = fetch_history(pair, source, days, cfg, use_cache)
        frames[name] = crypto_data.aggregate_candles(base_rows, factor)
        print(f"    {pair:<9} {name:>6} : {len(frames[name]):>6} bars "
              f"(aggregated {factor}x from {source}s)")
    return frames


# --------------------------------------------------------------------------
# REPLAY
# --------------------------------------------------------------------------

def build_analysis_at(pair, frames, ts_by_frame, t):
    """The `analysis` dict the live bot would have held at time t, built with
    the REAL analyze_timeframe on a point-in-time slice of each frame."""
    out = {}
    for name, rows in frames.items():
        idx = bisect_right(ts_by_frame[name], t)
        if idx < MIN_BARS:
            return None
        window = rows[max(0, idx - WINDOW_BARS):idx]
        if not window:
            return None
        try:
            out[name] = crypto_data.analyze_timeframe(window)
        except Exception:
            return None
    return {"pair": pair, "timeframes": out}


def synth_quote(mark, cfg):
    """Historically-honest stand-in for the live quote. Spread is the config's
    MEASURED structural value; mark sits exactly mid-book so score_order_book()
    returns its neutral 0.5 -- the honest answer when no book exists, rather
    than a fabricated imbalance."""
    spread_pct = cfg["execution_costs"]["assumed_round_trip_cost_pct"]
    half = mark * (spread_pct / 100.0) / 2.0
    return {"bid": mark - half, "ask": mark + half,
            "mark": mark, "spread_pct": spread_pct}


def replay(pair, frames, peer_frames, cfg, cadence_seconds):
    ts_by_frame = {n: [r["time"] for r in rows] for n, rows in frames.items()}
    base = frames["1h"]
    peer_ts = {p: [r["time"] for r in f["1h"]] for p, f in peer_frames.items()}

    step = max(1, cadence_seconds // 3600)
    obs = []
    for i in range(MIN_BARS, len(base), step):
        t = base[i]["time"]
        analysis = build_analysis_at(pair, frames, ts_by_frame, t)
        if analysis is None:
            continue
        try:
            regime = crypto_regime.classify_asset(analysis)
        except Exception:
            continue

        mark = analysis["timeframes"]["1h"].get("close")
        if not mark or mark <= 0:
            continue

        peers = []
        for p, pf in peer_frames.items():
            j = bisect_right(peer_ts[p], t)
            if j < MIN_BARS:
                continue
            try:
                pa = crypto_data.analyze_timeframe(
                    pf["1h"][max(0, j - WINDOW_BARS):j])
                peers.append(pa.get("roc_10"))
            except Exception:
                pass

        try:
            score = crypto_signals.score_asset(
                pair, analysis, regime, synth_quote(mark, cfg), cfg,
                peers=peers, news=None)
        except Exception:
            continue

        policy = regime.get("policy", {}) or {}
        obs.append({"time": t, "price": mark, "score": score["score"],
                    "regime": regime.get("overall", "UNKNOWN"),
                    "allow_long": bool(policy.get("allow_long")),
                    "size_mult": policy.get("size_mult") or 1.0})
    return obs


# --------------------------------------------------------------------------
# SIMULATE
# --------------------------------------------------------------------------

def simulate(obs, price_rows, price_ts, cfg, threshold):
    pm, risk_cfg = cfg["position_management"], cfg["risk"]
    target_pct = pm["take_profit_pct"] / 100.0
    stop_pct = pm["stop_loss_pct"] / 100.0            # negative
    max_hold = pm["max_hold_hours"] * 3600
    cost = cfg["execution_costs"]["assumed_round_trip_cost_pct"] / 100.0
    max_risk = risk_cfg["max_risk_per_trade_usd"]
    max_notional = risk_cfg["max_notional_per_trade_usd"]

    trades, busy_until = [], 0
    for o in obs:
        if o["time"] < busy_until or o["score"] < threshold or not o["allow_long"]:
            continue

        entry = o["price"]
        stop = entry * (1 + stop_pct)
        target = entry * (1 + target_pct)
        per_unit = entry - stop
        if per_unit <= 0:
            continue
        notional = min((max_risk / per_unit) * entry, max_notional) * o["size_mult"]
        if notional <= 0:
            continue

        i = bisect_right(price_ts, o["time"])
        exit_price = exit_t = reason = None
        while i < len(price_rows):
            bar = price_rows[i]
            if bar["time"] - o["time"] > max_hold:
                exit_price, exit_t, reason = bar["close"], bar["time"], "max_hold"
                break
            # Stop checked before target: when one bar spans both levels, the
            # worse fill is the honest assumption.
            if bar["low"] <= stop:
                exit_price, exit_t, reason = stop, bar["time"], "stop"
                break
            if bar["high"] >= target:
                exit_price, exit_t, reason = target, bar["time"], "target"
                break
            i += 1
        if exit_price is None:
            continue                       # still open at end of data

        net = (exit_price - entry) / entry - cost
        trades.append({"time": o["time"], "score": o["score"], "reason": reason,
                       "regime": o["regime"], "net_pct": net * 100,
                       "pnl": notional * net})
        busy_until = exit_t
    return trades


def summarize(trades):
    if not trades:
        return None
    wins = [t for t in trades if t["pnl"] > 0]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    rets = [t["net_pct"] for t in trades]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets) if len(rets) > 1 else 0.0
    sd = math.sqrt(var)
    return {"trades": len(trades), "net": sum(t["pnl"] for t in trades),
            "win_rate": len(wins) / len(trades) * 100,
            "pf": (gross_win / gross_loss) if gross_loss > 0 else float("inf"),
            "sharpe_per_trade": (mean / sd) if sd > 0 else 0.0,
            "worst": min(t["pnl"] for t in trades)}


def make_splits(obs):
    """Three independent splits, mirroring sim_lookback.py."""
    n = len(obs)
    return {"A": obs[int(n * 0.6):], "B": obs[:int(n * 0.4)], "C": obs[1::2]}


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--cadence", type=int, default=3600)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    cfg = crypto_data.load_config()
    pairs = [p for p, v in cfg["universe"].items() if v.get("enabled")]
    shipped = cfg["trade_score"]["thresholds"]["high_conviction"]

    print("=" * 92)
    print("EVA CRYPTO -- SCORE THRESHOLD CALIBRATION")
    print("=" * 92)
    print(f"  universe        {', '.join(pairs)}")
    print(f"  shipped gate    {shipped} (high_conviction)")
    print(f"  target / stop   +{cfg['position_management']['take_profit_pct']}% / "
          f"{cfg['position_management']['stop_loss_pct']}%")
    print(f"  max hold        {cfg['position_management']['max_hold_hours']}h")
    print(f"  round trip      {cfg['execution_costs']['assumed_round_trip_cost_pct']}%"
          f" (measured, charged on every trade)")
    print(f"  history         {args.days}d @ {args.cadence}s cadence")
    print()

    if args.dry_run:
        import inspect
        print("DRY RUN -- module and shape checks only, nothing fetched.\n")
        for mod, fn in ((crypto_data, "analyze_timeframe"),
                        (crypto_data, "aggregate_candles"),
                        (crypto_data, "coinbase_product"),
                        (crypto_regime, "classify_asset"),
                        (crypto_signals, "score_asset")):
            ok = "OK" if hasattr(mod, fn) else "MISSING"
            print(f"  {mod.__name__}.{fn:<20} {ok}")
        print(f"\n  score_asset signature: "
              f"{inspect.signature(crypto_signals.score_asset)}")
        print(f"  granularities configured: "
              f"{cfg['data']['candle_granularity_seconds']}")
        native = {n: s for n, s in cfg["data"]["candle_granularity_seconds"].items()
                  if s in crypto_data.COINBASE_GRANULARITIES}
        derived = {n: s for n, s in cfg["data"]["candle_granularity_seconds"].items()
                   if s not in crypto_data.COINBASE_GRANULARITIES}
        print(f"  native from Coinbase    : {native}")
        print(f"  aggregated locally      : {derived}")
        print("\n  If that all reads correctly, run without --dry-run.")
        return

    print("FETCHING")
    frames = {p: build_frames(p, args.days, cfg, not args.no_cache) for p in pairs}
    print()

    thin = [p for p in pairs if len(frames[p].get("1h", [])) < 200]
    if thin:
        print(f"!! {', '.join(thin)} returned under 200 hourly bars -- not enough")
        print("   history to calibrate anything. Fix the fetch before reading")
        print("   any number below as meaningful.\n")

    all_results = {}
    for pair in pairs:
        peers = {p: f for p, f in frames.items() if p != pair}
        print(f"REPLAYING {pair} ...", flush=True)
        obs = replay(pair, frames[pair], peers, cfg, args.cadence)
        if not obs:
            print(f"  no scorable observations for {pair}\n")
            continue

        scores = sorted(o["score"] for o in obs)
        regimes = Counter(o["regime"] for o in obs)
        print(f"  {len(obs)} observations | score {scores[0]:.0f}-{scores[-1]:.0f} "
              f"(median {scores[len(scores)//2]:.0f})")
        print("  regime mix: " + ", ".join(
            f"{k} {v/len(obs)*100:.0f}%" for k, v in regimes.most_common()))
        top = regimes.most_common(1)[0][1] / len(obs)
        if top > 0.75:
            print(f"  !! {top*100:.0f}% of this sample is one regime. A threshold")
            print("     fitted here is fitted to that regime, not to the market.")
        if scores[-1] < shipped:
            print(f"  !! no observation in this whole window reached {shipped}."
                  f" The shipped gate would never have fired here.")
        print()

        price_rows = frames[pair]["1h"]
        price_ts = [r["time"] for r in price_rows]
        splits = make_splits(obs)

        rows = []
        for th in range(30, 96, 5):
            rows.append({
                "th": th,
                "full": summarize(simulate(obs, price_rows, price_ts, cfg, th)),
                "splits": {k: summarize(simulate(v, price_rows, price_ts, cfg, th))
                           for k, v in splits.items()},
            })
        all_results[pair] = rows

        print(f"  {'thresh':>7} {'trades':>7} {'net $':>9} {'win%':>6} {'PF':>6} "
              f"{'shrp/tr':>8} {'worst $':>9}   split net A / B / C")
        print("  " + "-" * 88)
        for r in rows:
            f, mark = r["full"], ("  <- SHIPPED" if r["th"] == shipped else "")
            if not f:
                print(f"  {r['th']:>7} {0:>7} {'--':>9} {'--':>6} {'--':>6} "
                      f"{'--':>8} {'--':>9}   no trades{mark}")
                continue
            sn = " / ".join(f"{r['splits'][k]['net']:+7.2f}" if r["splits"][k]
                            else "   --  " for k in ("A", "B", "C"))
            print(f"  {r['th']:>7} {f['trades']:>7} {f['net']:>9.2f} "
                  f"{f['win_rate']:>5.0f}% {f['pf']:>6.2f} "
                  f"{f['sharpe_per_trade']:>8.2f} {f['worst']:>9.2f}   {sn}{mark}")
        print()

    print("=" * 92)
    print(f"VERDICT -- must beat shipped {shipped} on net P&L in ALL THREE splits")
    print("=" * 92)
    for pair, rows in all_results.items():
        ship = next((r for r in rows if r["th"] == shipped), None)
        print(f"\n  {pair}:")
        if not ship:
            print(f"    shipped threshold {shipped} not in sweep range.")
            continue

        winners = []
        for r in rows:
            if r["th"] == shipped:
                continue
            beat = sum(1 for k in ("A", "B", "C")
                       if (r["splits"][k]["net"] if r["splits"][k] else 0.0)
                       > (ship["splits"][k]["net"] if ship["splits"][k] else 0.0))
            if beat == 3:
                winners.append(r)

        if not winners:
            print(f"    -> NOTHING beats {shipped} in all three splits. "
                  f"Shipped value stands.")
            continue

        best = max(winners, key=lambda r: r["full"]["net"] if r["full"] else 0.0)
        ship_net = ship["full"]["net"] if ship["full"] else 0.0
        print(f"    -> threshold {best['th']} beats {shipped} in all three splits "
              f"(net {best['full']['net']:+.2f} vs {ship_net:+.2f})")
        plateau = sorted(r["th"] for r in winners if abs(r["th"] - best["th"]) <= 10)
        print(f"       neighbours also winning: {plateau}  "
              f"{'(plateau -- more trustworthy)' if len(plateau) >= 3 else '(SPIKE -- likely noise)'}")
        if abs(best["th"] - shipped) <= 5:
            print(f"       !! within the +/-4pt order-book blind spot of {shipped}."
                  f" Not a real difference.")

    print()
    print("=" * 92)
    print("READ THIS BEFORE CHANGING ANY NUMBER")
    print("=" * 92)
    print("  * score_order_book() was pinned neutral on every bar -- no historical")
    print("    book exists. Weight 8 => backtest scores carry roughly +/-4 points")
    print("    of error against live. A winner within 4 points of shipped is noise.")
    print("  * A single-regime sample calibrates a single-regime threshold.")
    print("  * A plateau is evidence. A lone spike is curve-fitting.")
    print("  * execution.enabled is still false in crypto_config.json. Nothing here")
    print("    changes that, and no result here is on its own a reason to flip it.")
    print("=" * 92)


if __name__ == "__main__":
    main()
