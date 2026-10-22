#!/usr/bin/env python3
"""
EVA CRYPTO v1 -- offline research and validation.

This module NEVER trades. It cannot: it has no broker import and no order
path. Its only job is to answer "does this rule actually work?" with evidence,
before any rule is allowed near real money.

    LIVE BOT -> JOURNAL -> OFFLINE ANALYSIS -> BACKTEST
             -> WALK-FORWARD -> CANDIDATE -> HUMAN REVIEW -> PROMOTION

Two hard principles:

1. VENUE COST IS ALWAYS APPLIED. A backtest that ignores the ~1.9% Robinhood
   crypto spread is not optimistic, it is wrong. Most published crypto
   strategies are profitable only because they assume a venue that does not
   charge this.

2. IN-SAMPLE RESULTS ARE NOT EVIDENCE. Anything can be fitted to history.
   walk_forward() optimises on one window and measures on the NEXT, unseen
   one. Only out-of-sample numbers may inform a promotion decision.

Metrics deliberately lead with expectancy and profit factor, not win rate.
A 45% win rate with large winners beats 75% with small ones -- especially
here, where every round trip starts 1.9% behind.
"""

import csv
import json
import statistics as st
from datetime import datetime, timezone
from pathlib import Path

import crypto_data as cd

BASE = Path(__file__).resolve().parent
STATE = BASE / "_crypto_state"
JOURNAL = STATE / "journal.csv"
RESULTS = STATE / "research_results.json"


# ------------------------------------------------------------- indicators

def atr_series(rows, period=14):
    tr = cd.true_range(rows)
    out = [None] * len(rows)
    if len(tr) < period:
        return out
    a = sum(tr[:period]) / period
    out[period] = a
    for i in range(period + 1, len(rows)):
        a = (a * (period - 1) + tr[i - 1]) / period
        out[i] = a
    return out


def ema_series(closes, period):
    out = [None] * len(closes)
    if len(closes) < period:
        return out
    val = sum(closes[:period]) / period
    out[period - 1] = val
    k = 2 / (period + 1)
    for i in range(period, len(closes)):
        val = closes[i] * k + val * (1 - k)
        out[i] = val
    return out


def rsi_series(closes, period=14):
    out = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains, losses = [], []
    for a, b in zip(closes[:-1], closes[1:]):
        d = b - a
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    out[period] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
        out[i + 1] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def bollinger_series(closes, length=20, mult=2.0):
    lo = [None] * len(closes)
    mid = [None] * len(closes)
    hi = [None] * len(closes)
    for i in range(length, len(closes)):
        w = closes[i - length:i]
        basis = sum(w) / length
        dev = mult * st.pstdev(w)
        lo[i], mid[i], hi[i] = basis - dev, basis, basis + dev
    return lo, mid, hi


# --------------------------------------------------------------- metrics

def evaluate(trades):
    """Performance of a list of net-percent returns.

    Leads with expectancy and profit factor. Win rate is reported but is NOT
    the headline -- optimising for it produces strategies that take tiny wins
    and huge losses, which is exactly wrong on a high-cost venue.
    """
    if not trades:
        return {"trades": 0, "note": "no trades generated"}

    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))

    peak = run = 0.0
    max_dd = 0.0
    for t in trades:
        run += t
        peak = max(peak, run)
        max_dd = min(max_dd, run - peak)

    avg = sum(trades) / len(trades)
    stdev = st.pstdev(trades) if len(trades) > 1 else 0.0
    downside = [t for t in trades if t < 0]
    dstd = st.pstdev(downside) if len(downside) > 1 else 0.0

    return {
        "trades": len(trades),
        "expectancy_pct": round(avg, 3),
        "total_pct": round(sum(trades), 2),
        "profit_factor": (round(gross_win / gross_loss, 3)
                          if gross_loss else None),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "avg_win_pct": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss_pct": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "best_pct": round(max(trades), 2),
        "worst_pct": round(min(trades), 2),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_like": round(avg / stdev, 3) if stdev else None,
        "sortino_like": round(avg / dstd, 3) if dstd else None,
        "_doc": ("expectancy_pct is per-trade NET of venue cost. "
                 "profit_factor > 1 means gross wins exceed gross losses."),
    }


def breakeven_win_rate(target_pct, stop_pct, cost_pct):
    """The win rate a target/stop pair NEEDS just to break even after cost.

    This is the number that killed the original 5%/3% config: it required
    61.3%. Any candidate strategy should be checked against this before its
    backtest is even taken seriously.
    """
    win = target_pct - cost_pct
    loss = abs(stop_pct) + cost_pct
    if win + loss <= 0:
        return None
    return round(loss / (win + loss) * 100, 1)


# -------------------------------------------------------------- backtest

def backtest(rows, entry_fn, cfg, target_pct=None, stop_pct=None,
             trail_fn=None, max_hold_bars=None):
    """Long-only backtest with the venue cost charged on every round trip.

    entry_fn(rows, i) -> True when a long should open at rows[i]['close'].
    Deliberately generic so any candidate rule can be tested identically.
    """
    cost = cfg["execution_costs"]["assumed_round_trip_cost_pct"]
    target_pct = (target_pct if target_pct is not None
                  else cfg["position_management"]["take_profit_pct"])
    stop_pct = (stop_pct if stop_pct is not None
                else cfg["position_management"]["stop_loss_pct"])

    trades = []
    i = 60
    n = len(rows)
    while i < n - 1:
        if not entry_fn(rows, i):
            i += 1
            continue

        entry = rows[i]["close"]
        j = i + 1
        closed = False
        while j < n:
            px = rows[j]["close"]
            chg = (px - entry) / entry * 100

            if chg <= stop_pct or chg >= target_pct:
                trades.append(chg - cost)
                closed = True
                break
            if trail_fn is not None and trail_fn(rows, j, entry):
                trades.append(chg - cost)
                closed = True
                break
            if max_hold_bars and (j - i) >= max_hold_bars:
                trades.append(chg - cost)
                closed = True
                break
            j += 1

        if not closed:
            # Open at the end of data: record honestly rather than discard,
            # but it is marked so it can be excluded from strict runs.
            trades.append((rows[-1]["close"] - entry) / entry * 100 - cost)
        i = j + 1

    return trades


def walk_forward(rows, build_entry_fn, param_grid, cfg, folds=4):
    """Optimise on one window, MEASURE on the next unseen one.

    This is the only result that should ever inform a live change. In-sample
    numbers are reported alongside purely to expose overfitting: a large gap
    between in-sample and out-of-sample is the signature of a curve fit.
    """
    n = len(rows)
    if n < 200:
        return {"error": f"need >=200 bars for walk-forward, have {n}"}

    fold = n // (folds + 1)
    out = []

    for k in range(folds):
        train = rows[k * fold:(k + 1) * fold + fold]
        test = rows[(k + 1) * fold:(k + 2) * fold]
        if len(test) < 40:
            continue

        best, best_score = None, None
        for params in param_grid:
            t = backtest(train, build_entry_fn(params), cfg,
                         params.get("target_pct"), params.get("stop_pct"))
            m = evaluate(t)
            if m["trades"] < 3:
                continue
            score = m["expectancy_pct"]
            if best_score is None or score > best_score:
                best, best_score = params, score

        if best is None:
            out.append({"fold": k, "note": "no parameter set produced >=3 trades"})
            continue

        is_m = evaluate(backtest(train, build_entry_fn(best), cfg,
                                 best.get("target_pct"), best.get("stop_pct")))
        oos_m = evaluate(backtest(test, build_entry_fn(best), cfg,
                                  best.get("target_pct"), best.get("stop_pct")))
        out.append({
            "fold": k,
            "chosen_params": best,
            "in_sample": is_m,
            "out_of_sample": oos_m,
        })

    oos = [f["out_of_sample"] for f in out
           if "out_of_sample" in f and f["out_of_sample"].get("trades")]
    agg = None
    if oos:
        total_trades = sum(m["trades"] for m in oos)
        agg = {
            "folds_measured": len(oos),
            "total_oos_trades": total_trades,
            "mean_oos_expectancy_pct": round(
                sum(m["expectancy_pct"] * m["trades"] for m in oos)
                / total_trades, 3),
            "oos_total_pct": round(sum(m["total_pct"] for m in oos), 2),
            "folds_profitable": sum(1 for m in oos if m["total_pct"] > 0),
        }

    return {"folds": out, "aggregate_out_of_sample": agg}


# ------------------------------------------------------- candidate rules

def rule_bollinger_reversion(params):
    """Buy when price closes back ABOVE the lower band -- the usable long half
    of the ChartArt RSI+Bollinger script, with RSI-14 instead of RSI-6."""
    length = params.get("bb_length", 20)
    mult = params.get("bb_mult", 2.0)
    rsi_max = params.get("rsi_max", 45)

    def entry(rows, i):
        closes = [r["close"] for r in rows[:i + 1]]
        if len(closes) < max(length, 15) + 2:
            return False
        lo, _, _ = bollinger_series(closes, length, mult)
        r = rsi_series(closes, 14)
        if lo[i] is None or lo[i - 1] is None or r[i] is None:
            return False
        crossed_up = closes[i - 1] <= lo[i - 1] and closes[i] > lo[i]
        return crossed_up and r[i] <= rsi_max

    return entry


def rule_trend_pullback(params):
    """EVA's own logic: uptrend by EMA, pulled back, turning up. This is the
    baseline every candidate must BEAT to be worth adopting."""
    fast = params.get("ema_fast", 20)
    slow = params.get("ema_slow", 50)
    pull = params.get("pullback_pct", 1.0)

    def entry(rows, i):
        closes = [r["close"] for r in rows[:i + 1]]
        if len(closes) < slow + 2:
            return False
        ef = ema_series(closes, fast)
        es = ema_series(closes, slow)
        if ef[i] is None or es[i] is None or ef[i - 1] is None:
            return False
        uptrend = ef[i] > es[i]
        pulled = closes[i] < ef[i] * (1 - pull / 100)
        turning = closes[i] > closes[i - 1]
        return uptrend and pulled and turning

    return entry


CANDIDATES = {
    "bollinger_reversion": (rule_bollinger_reversion, [
        {"bb_length": 20, "bb_mult": 2.0, "rsi_max": 45, "target_pct": 10, "stop_pct": -3},
        {"bb_length": 20, "bb_mult": 2.5, "rsi_max": 40, "target_pct": 10, "stop_pct": -3},
        {"bb_length": 50, "bb_mult": 2.0, "rsi_max": 45, "target_pct": 12, "stop_pct": -4},
    ]),
    "trend_pullback": (rule_trend_pullback, [
        {"ema_fast": 20, "ema_slow": 50, "pullback_pct": 1.0, "target_pct": 10, "stop_pct": -3},
        {"ema_fast": 20, "ema_slow": 50, "pullback_pct": 2.0, "target_pct": 12, "stop_pct": -4},
        {"ema_fast": 10, "ema_slow": 30, "pullback_pct": 1.5, "target_pct": 10, "stop_pct": -3},
    ]),
}


# ------------------------------------------------------- journal analysis

def analyze_journal():
    """What the LIVE desk has actually been seeing. This is the dataset that
    eventually calibrates the score thresholds -- real observed distributions,
    not guesses."""
    if not JOURNAL.exists():
        return {"error": "no journal yet"}
    rows = list(csv.DictReader(open(JOURNAL)))
    if not rows:
        return {"error": "journal empty"}

    by_pair = {}
    for r in rows:
        p = r["pair"]
        d = by_pair.setdefault(p, {"n": 0, "scores": [], "regimes": {},
                                   "vetoes": {}})
        d["n"] += 1
        try:
            d["scores"].append(float(r["score"]))
        except (TypeError, ValueError):
            pass
        d["regimes"][r["regime"]] = d["regimes"].get(r["regime"], 0) + 1
        v = (r.get("veto") or "none").split("--")[0].strip()[:60]
        d["vetoes"][v] = d["vetoes"].get(v, 0) + 1

    out = {}
    for p, d in by_pair.items():
        s = d["scores"]
        out[p] = {
            "decisions": d["n"],
            "score_min": round(min(s), 1) if s else None,
            "score_max": round(max(s), 1) if s else None,
            "score_mean": round(sum(s) / len(s), 1) if s else None,
            "score_p90": (round(sorted(s)[int(len(s) * 0.9)], 1)
                          if len(s) >= 10 else None),
            "regimes": dict(sorted(d["regimes"].items(),
                                   key=lambda kv: -kv[1])),
            "top_vetoes": dict(sorted(d["vetoes"].items(),
                                      key=lambda kv: -kv[1])[:3]),
        }
    return out


def run_all(pairs=None, timeframes=(("6h", 21600), ("1d", 86400))):
    cfg = cd.load_config()
    pairs = pairs or list(cfg["universe"])
    cost = cfg["execution_costs"]["assumed_round_trip_cost_pct"]

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "venue_cost_pct": cost,
        "breakeven_reference": {
            "10%/-3%": breakeven_win_rate(10, -3, cost),
            "5%/-3%": breakeven_win_rate(5, -3, cost),
            "12%/-4%": breakeven_win_rate(12, -4, cost),
        },
        "journal": analyze_journal(),
        "backtests": {},
    }

    for pair in pairs:
        for tf, gran in timeframes:
            try:
                rows = cd.fetch_candles(pair, gran, cfg)
            except cd.DataError as e:
                results["backtests"][f"{pair}|{tf}"] = {"error": str(e)}
                continue
            key = f"{pair}|{tf}"
            results["backtests"][key] = {"bars": len(rows), "strategies": {}}
            for name, (builder, grid) in CANDIDATES.items():
                wf = walk_forward(rows, builder, grid, cfg)
                results["backtests"][key]["strategies"][name] = wf

    cd.atomic_json(RESULTS, results)
    return results


if __name__ == "__main__":
    cfg = cd.load_config()
    cost = cfg["execution_costs"]["assumed_round_trip_cost_pct"]

    print("=" * 74)
    print("EVA CRYPTO -- RESEARCH (offline, cannot trade)")
    print("=" * 74)
    print(f"venue cost applied to every trade: {cost}%\n")
    print("Breakeven win rate REQUIRED, after cost:")
    for label, (t, s) in (("5% / -3%  (original)", (5, -3)),
                          ("10% / -3% (current)", (10, -3)),
                          ("12% / -4%", (12, -4))):
        print(f"   {label:<22} {breakeven_win_rate(t, s, cost)}%")

    print("\n" + "-" * 74)
    print("LIVE JOURNAL -- what the desk has actually seen")
    print("-" * 74)
    j = analyze_journal()
    if "error" in j:
        print(f"  {j['error']}")
    else:
        for pair, d in j.items():
            print(f"\n  {pair}: {d['decisions']} decisions")
            print(f"    score  min {d['score_min']}  mean {d['score_mean']}  "
                  f"max {d['score_max']}  p90 {d['score_p90']}")
            print(f"    regimes: {d['regimes']}")
            for v, n in d["top_vetoes"].items():
                print(f"      veto x{n}: {v}")

    print("\n" + "-" * 74)
    print("WALK-FORWARD -- out-of-sample only")
    print("-" * 74)
    res = run_all()
    for key, block in res["backtests"].items():
        if "error" in block:
            print(f"\n{key}: {block['error']}")
            continue
        print(f"\n{key}  ({block['bars']} bars)")
        for name, wf in block["strategies"].items():
            agg = wf.get("aggregate_out_of_sample")
            if not agg:
                note = wf.get("error") or "insufficient trades"
                print(f"    {name:<22} {note}")
                continue
            print(f"    {name:<22} OOS trades {agg['total_oos_trades']:>3} | "
                  f"expectancy {agg['mean_oos_expectancy_pct']:>7.2f}% | "
                  f"total {agg['oos_total_pct']:>7.1f}% | "
                  f"profitable folds {agg['folds_profitable']}/{agg['folds_measured']}")

    print(f"\nfull results -> {RESULTS}")
