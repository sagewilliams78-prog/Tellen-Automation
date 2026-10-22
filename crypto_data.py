#!/usr/bin/env python3
"""
EVA CRYPTO v1 -- market data layer.

Fetches multi-timeframe candles and computes the technical measurements the
rest of the pipeline scores on. Pure functions over real data: nothing here
places an order, reads a credential, or decides anything. It reports what the
market IS; crypto_regime/crypto_signals decide what that means.

SOURCES, and why each:
  Coinbase REST  -- candle history across 5m/15m/1h/4h. Robinhood exposes no
                    OHLC endpoint, so indicators must come from a real
                    exchange feed. Public, no key, no account linkage.
  Robinhood MCP  -- bid/ask/mark. This is EXECUTION truth and lives in
                    crypto_broker.py; this module never guesses at it.

The two legitimately differ by roughly the spread (~1.9% on this venue).
Beyond max_price_disagreement_pct one feed is wrong, and the health layer
must stop trading rather than act on a bad price.

Deliberately NOT an indicator soup. Every measurement below exists because a
specific scoring factor consumes it.
"""

import json
import math
import os
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATE_DIR = BASE / "_crypto_state"
CONFIG_FILE = BASE / "crypto_config.json"


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def atomic_json(path, data):
    """Write-then-rename so a reader (Trading HQ) never sees a half-written
    file. Every state write in EVA Crypto goes through this."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


# ---------------------------------------------------------------- candles

class DataError(Exception):
    """Raised when real data could not be fetched. Callers must treat this as
    'do not trade', never as 'assume flat/neutral'."""


def coinbase_product(pair):
    """'BTC-USD' -> 'BTC-USD'. Coinbase uses the same hyphenated form."""
    return pair.upper()


def fetch_candles(pair, granularity_seconds, cfg=None, timeout=12):
    """Real OHLCV candles, oldest-first.

    Coinbase returns [time, low, high, open, close, volume] newest-first and
    caps a response at 300 candles. Oldest-first is what every indicator below
    expects, so the flip happens once, here.
    """
    cfg = cfg or load_config()
    base = cfg["data"]["coinbase_rest"]
    url = (f"{base}/products/{coinbase_product(pair)}/candles"
           f"?granularity={granularity_seconds}")
    req = urllib.request.Request(url, headers={"User-Agent": "EvaCryptoV1/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = json.loads(r.read().decode())
    except (urllib.error.URLError, ValueError, OSError) as e:
        raise DataError(f"{pair} {granularity_seconds}s candles: "
                        f"{type(e).__name__}: {e}") from e

    if not isinstance(raw, list) or not raw:
        raise DataError(f"{pair} {granularity_seconds}s: empty candle response")

    rows = []
    for item in raw:
        if not isinstance(item, list) or len(item) < 6:
            continue
        ts, low, high, open_, close, volume = item[:6]
        rows.append({
            "time": float(ts),
            "low": float(low),
            "high": float(high),
            "open": float(open_),
            "close": float(close),
            "volume": float(volume),
        })

    if not rows:
        raise DataError(f"{pair} {granularity_seconds}s: no usable candles")

    rows.sort(key=lambda x: x["time"])
    return rows


# Coinbase supports ONLY these candle granularities. Confirmed live
# 2026-09-01: any other value returns HTTP 400. Notably 14400 (4h) is NOT
# supported, so the brief's 4h regime frame must be aggregated from 1h bars
# rather than requested directly.
COINBASE_GRANULARITIES = {60, 300, 900, 3600, 21600, 86400}


def aggregate_candles(rows, factor):
    """Combine N consecutive candles into one larger candle.

    Used to build the 4h regime frame from real 1h bars. Aggregation is
    anchored to epoch multiples of the target period so buckets are stable
    across polls -- otherwise the "current" 4h bar would shift its boundaries
    every cycle and the regime read would flicker for no market reason.

    The final bucket is dropped when incomplete: a partial 4h candle would
    misreport its high/low/close and the regime layer treats this frame as
    settled context.
    """
    if factor <= 1 or not rows:
        return rows

    period = None
    if len(rows) >= 2:
        period = rows[1]["time"] - rows[0]["time"]
    if not period or period <= 0:
        return rows
    target = period * factor

    buckets = {}
    for r in rows:
        key = int(r["time"] // target) * target
        buckets.setdefault(key, []).append(r)

    out = []
    for key in sorted(buckets):
        group = sorted(buckets[key], key=lambda x: x["time"])
        if len(group) < factor:
            continue  # incomplete bucket -- never report a partial bar
        out.append({
            "time": float(key),
            "open": group[0]["open"],
            "close": group[-1]["close"],
            "high": max(g["high"] for g in group),
            "low": min(g["low"] for g in group),
            "volume": sum(g["volume"] for g in group),
        })
    return out


def fetch_all_timeframes(pair, cfg=None):
    """Every configured timeframe for one asset.

    A partial result is NOT returned: multi-timeframe agreement is a core
    scoring factor, and silently scoring 3 of 4 frames would quietly change
    the meaning of the score. All or DataError.

    Timeframes Coinbase cannot serve natively are built by aggregating the
    largest supported granularity that divides evenly into them.
    """
    cfg = cfg or load_config()
    gran = cfg["data"]["candle_granularity_seconds"]
    out = {}

    for name, seconds in gran.items():
        if seconds in COINBASE_GRANULARITIES:
            out[name] = fetch_candles(pair, seconds, cfg)
            continue

        # Find the largest supported granularity that divides this one evenly.
        source = max((g for g in COINBASE_GRANULARITIES
                      if seconds % g == 0 and g < seconds), default=None)
        if source is None:
            raise DataError(
                f"{pair}: timeframe {name} ({seconds}s) is not supported by "
                f"Coinbase and cannot be aggregated from a supported one")

        factor = seconds // source
        base_rows = fetch_candles(pair, source, cfg)
        agg = aggregate_candles(base_rows, factor)
        if not agg:
            raise DataError(
                f"{pair}: not enough {source}s bars to build a single "
                f"{name} candle")
        out[name] = agg

    return out


# ------------------------------------------------------------- indicators

def ema(values, period):
    """Seeded with an SMA of the first `period` values rather than values[0].

    Seeding on a single price (the old monitor's approach) lets one outlier
    bias the whole series; on a short window that bias is still visible at the
    end, which would distort the trend read this system leans on.
    """
    if not values or len(values) < period:
        return None
    k = 2 / (period + 1)
    out = sum(values[:period]) / period
    for v in values[period:]:
        out = v * k + out * (1 - k)
    return out


def rsi(values, period=14):
    """Wilder's RSI over the full series, not just the last `period` bars.

    The legacy monitor averaged only the final 14 deltas, which is a simple
    average, not Wilder smoothing -- it reacts far too sharply and made RSI
    swing 60 -> 74 -> 33 within minutes. This is the standard formulation.
    """
    if len(values) <= period:
        return None

    gains, losses = [], []
    for a, b in zip(values[:-1], values[1:]):
        change = b - a
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def true_range(rows):
    """Per-bar true range: the real bar span including overnight-style gaps."""
    out = []
    for prev, cur in zip(rows[:-1], rows[1:]):
        out.append(max(
            cur["high"] - cur["low"],
            abs(cur["high"] - prev["close"]),
            abs(cur["low"] - prev["close"]),
        ))
    return out


def atr(rows, period=14):
    """Average True Range -- the volatility measure position sizing uses.

    Returned in PRICE units. As a percentage of price it is comparable across
    BTC and DOGE, which is the only way to size two assets whose unit prices
    differ by six orders of magnitude on the same risk budget.
    """
    tr = true_range(rows)
    if len(tr) < period:
        return None
    val = sum(tr[:period]) / period
    for t in tr[period:]:
        val = (val * (period - 1) + t) / period
    return val


def volume_ratio(rows, lookback=20):
    """Current bar's volume vs the trailing average. >1 means unusual
    participation, which is what separates a real breakout from drift."""
    if len(rows) < lookback + 1:
        return None
    recent = rows[-1]["volume"]
    baseline = sum(r["volume"] for r in rows[-lookback - 1:-1]) / lookback
    if baseline <= 0:
        return None
    return recent / baseline


def vwap(rows, lookback=20):
    """Volume-weighted average price over the window -- the level large flow
    actually transacted at, not merely where price closed."""
    window = rows[-lookback:] if len(rows) >= lookback else rows
    total_v = sum(r["volume"] for r in window)
    if total_v <= 0:
        return None
    return sum(((r["high"] + r["low"] + r["close"]) / 3) * r["volume"]
               for r in window) / total_v


def rate_of_change(rows, bars=10):
    """Percent change over N bars -- momentum, independent of any average."""
    if len(rows) < bars + 1:
        return None
    old = rows[-bars - 1]["close"]
    if old == 0:
        return None
    return (rows[-1]["close"] - old) / old * 100


def swing_structure(rows, lookback=20, pivot=2):
    """Higher-highs/higher-lows structure -- trend as PRICE describes it,
    independent of any moving average.

    A pivot high is a bar whose high exceeds `pivot` bars on both sides. Two
    rising pivot highs and two rising pivot lows is an uptrend by structure.
    This is deliberately a separate opinion from EMAs so multi-timeframe
    agreement is not just the same indicator agreeing with itself.
    """
    window = rows[-lookback:] if len(rows) >= lookback else rows
    if len(window) < pivot * 2 + 3:
        return "UNKNOWN"

    highs, lows = [], []
    for i in range(pivot, len(window) - pivot):
        seg = window[i - pivot:i + pivot + 1]
        if window[i]["high"] == max(s["high"] for s in seg):
            highs.append(window[i]["high"])
        if window[i]["low"] == min(s["low"] for s in seg):
            lows.append(window[i]["low"])

    hh = len(highs) >= 2 and highs[-1] > highs[-2]
    hl = len(lows) >= 2 and lows[-1] > lows[-2]
    lh = len(highs) >= 2 and highs[-1] < highs[-2]
    ll = len(lows) >= 2 and lows[-1] < lows[-2]

    if hh and hl:
        return "UPTREND"
    if lh and ll:
        return "DOWNTREND"
    if len(highs) >= 2 and len(lows) >= 2:
        return "RANGE"
    return "UNKNOWN"


def distance_pct(a, b):
    """b relative to a, as a percentage. None-safe."""
    if a in (None, 0) or b is None:
        return None
    return (b - a) / a * 100


def realized_volatility_pct(rows, bars=20):
    """Stdev of bar-to-bar returns, in percent -- how violently this asset has
    been moving, used to penalise entries in chaotic conditions."""
    if len(rows) < bars + 1:
        return None
    window = rows[-bars - 1:]
    rets = []
    for prev, cur in zip(window[:-1], window[1:]):
        if prev["close"]:
            rets.append((cur["close"] - prev["close"]) / prev["close"])
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * 100


# ------------------------------------------------------- timeframe digest

def analyze_timeframe(rows):
    """Every measurement for ONE timeframe, from real candles.

    Returned as a flat dict so the journal can record exactly what EVA saw at
    decision time -- the brief requires the 5M/15M/1H/4H condition on every
    entry, and this is that record.
    """
    closes = [r["close"] for r in rows]
    last = rows[-1]
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    a = atr(rows, 14)
    vw = vwap(rows, 20)

    if e20 is not None and e50 is not None:
        if e20 > e50:
            trend = "UP"
        elif e20 < e50:
            trend = "DOWN"
        else:
            trend = "FLAT"
    else:
        trend = "UNKNOWN"

    window = rows[-20:] if len(rows) >= 20 else rows
    recent_high = max(r["high"] for r in window)
    recent_low = min(r["low"] for r in window)

    return {
        "bars": len(rows),
        "close": last["close"],
        "high": last["high"],
        "low": last["low"],
        "open": last["open"],
        "volume": last["volume"],
        "bar_time": datetime.fromtimestamp(last["time"], timezone.utc).isoformat(),
        "ema20": e20,
        "ema50": e50,
        "trend": trend,
        "structure": swing_structure(rows),
        "rsi14": rsi(closes, 14),
        "atr": a,
        "atr_pct": (a / last["close"] * 100) if a and last["close"] else None,
        "realized_vol_pct": realized_volatility_pct(rows),
        "volume_ratio": volume_ratio(rows),
        "vwap": vw,
        "dist_from_vwap_pct": distance_pct(vw, last["close"]),
        "dist_from_ema20_pct": distance_pct(e20, last["close"]),
        "roc_10": rate_of_change(rows, 10),
        "recent_high": recent_high,
        "recent_low": recent_low,
        "dist_from_high_pct": distance_pct(recent_high, last["close"]),
        "dist_from_low_pct": distance_pct(recent_low, last["close"]),
        "candle": ("bull" if last["close"] > last["open"]
                   else "bear" if last["close"] < last["open"] else "flat"),
    }


def analyze_asset(pair, cfg=None):
    """Full multi-timeframe picture for one asset. Raises DataError rather
    than returning partial data -- see fetch_all_timeframes."""
    cfg = cfg or load_config()
    frames = fetch_all_timeframes(pair, cfg)
    return {
        "pair": pair,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timeframes": {name: analyze_timeframe(rows) for name, rows in frames.items()},
    }


if __name__ == "__main__":
    # Real smoke test against the live market.
    cfg = load_config()
    for pair in cfg["universe"]:
        try:
            a = analyze_asset(pair, cfg)
        except DataError as e:
            print(f"{pair}: DATA ERROR -- {e}")
            continue
        print(f"\n{pair}")
        for name in ("5m", "15m", "1h", "4h"):
            t = a["timeframes"][name]
            print(f"  {name:>3}  close={t['close']:<12} trend={t['trend']:<8} "
                  f"struct={t['structure']:<9} rsi={t['rsi14'] and round(t['rsi14'], 1)}"
                  f"  atr%={t['atr_pct'] and round(t['atr_pct'], 2)}"
                  f"  vol_x={t['volume_ratio'] and round(t['volume_ratio'], 2)}")
