#!/usr/bin/env python3
"""
EVA CRYPTO v1 -- market regime detector.

Classifies what KIND of market each asset is in, so the right strategy can
activate (or none can). The brief is explicit that this is one of the most
important components, and the reason is simple: forcing one strategy onto
every market condition is the most common way a backtest-good system loses
real money.

Regimes:
  TRENDING_UP      directional up  -- pullback continuation logic applies
  TRENDING_DOWN    directional down -- longs stand aside
  RANGE            bounded         -- reversion logic, or stand aside
  BREAKOUT         leaving a range -- requires volume AND liquidity proof
  HIGH_VOLATILITY  violent         -- size down hard
  LOW_VOLATILITY   compressed      -- often precedes expansion; wait
  PANIC            dislocation     -- no new entries, full stop
  UNCERTAIN        conflicted      -- DO NOTHING. Not a soft "maybe".

UNCERTAIN is a real, common, CORRECT answer. A detector that always produces
a confident label is not measuring the market, it is guessing.

Pure functions over the digest crypto_data.analyze_asset() returns. No I/O,
no orders, no config mutation -- so it is directly testable against any
historical snapshot.
"""

# Thresholds, expressed against ATR-as-percent-of-price so BTC and DOGE are
# judged on the same scale despite unit prices six orders of magnitude apart.
# Calibrated against real observed 1h ATR%: BTC ~0.58%, DOGE ~0.83% during a
# normal session on 2026-09-01. These are starting points and MUST be
# revisited with real historical distributions -- see crypto_research.py.
HIGH_VOL_ATR_PCT = 2.00
LOW_VOL_ATR_PCT = 0.25
PANIC_ATR_PCT = 4.00
PANIC_ROC_PCT = -8.00

# A breakout must clear its recent range AND bring real participation. Volume
# confirmation is what separates a breakout from a drift that merely printed a
# new high on nobody trading.
BREAKOUT_VOLUME_RATIO = 1.60
BREAKOUT_PROXIMITY_PCT = 0.30

# How close EMA20/EMA50 must be (as % of price) before "trend" is really just
# noise around a flat mean.
FLAT_EMA_SEPARATION_PCT = 0.15


def _sep_pct(tf):
    """EMA20 vs EMA50 separation as a percent of price. This is the honest
    measure of trend STRENGTH -- a crossover with no separation is noise."""
    e20, e50, close = tf.get("ema20"), tf.get("ema50"), tf.get("close")
    if not e20 or not e50 or not close:
        return None
    return abs(e20 - e50) / close * 100


def classify_timeframe(tf):
    """Regime for a SINGLE timeframe, from that frame's own evidence."""
    atr_pct = tf.get("atr_pct")
    roc = tf.get("roc_10")
    vol_x = tf.get("volume_ratio")
    structure = tf.get("structure")
    trend = tf.get("trend")
    sep = _sep_pct(tf)
    dist_high = tf.get("dist_from_high_pct")
    dist_low = tf.get("dist_from_low_pct")

    # PANIC first -- it overrides every other reading. A violent directional
    # dislocation is not a "trend" to join.
    if atr_pct is not None and atr_pct >= PANIC_ATR_PCT:
        if roc is not None and roc <= PANIC_ROC_PCT:
            return "PANIC", f"ATR {atr_pct:.2f}% with {roc:.1f}% drop"
        return "HIGH_VOLATILITY", f"ATR {atr_pct:.2f}% (extreme)"

    if atr_pct is not None and atr_pct >= HIGH_VOL_ATR_PCT:
        return "HIGH_VOLATILITY", f"ATR {atr_pct:.2f}% > {HIGH_VOL_ATR_PCT}%"

    # BREAKOUT: at the edge of the recent range, with real volume behind it.
    if (vol_x is not None and vol_x >= BREAKOUT_VOLUME_RATIO
            and dist_high is not None
            and abs(dist_high) <= BREAKOUT_PROXIMITY_PCT):
        return "BREAKOUT", f"at range high on {vol_x:.1f}x volume"

    if atr_pct is not None and atr_pct <= LOW_VOL_ATR_PCT:
        return "LOW_VOLATILITY", f"ATR {atr_pct:.2f}% (compressed)"

    # Directional: EMAs and price STRUCTURE must agree. Requiring both is
    # deliberate -- EMAs lag and structure is noisy, but they fail in
    # different ways, so agreement is real evidence rather than one indicator
    # confirming itself.
    if trend == "UP" and structure == "UPTREND":
        if sep is not None and sep >= FLAT_EMA_SEPARATION_PCT:
            return "TRENDING_UP", f"EMAs up {sep:.2f}% apart, higher highs/lows"
        return "RANGE", "up bias but EMAs too close to call a trend"

    if trend == "DOWN" and structure == "DOWNTREND":
        if sep is not None and sep >= FLAT_EMA_SEPARATION_PCT:
            return "TRENDING_DOWN", f"EMAs down {sep:.2f}% apart, lower highs/lows"
        return "RANGE", "down bias but EMAs too close to call a trend"

    if structure == "RANGE":
        return "RANGE", "bounded structure"

    # EMAs and structure disagree -- that is genuinely uncertain, and saying so
    # is more useful than inventing a label.
    if trend in ("UP", "DOWN") and structure in ("UPTREND", "DOWNTREND"):
        return "UNCERTAIN", f"EMA says {trend}, structure says {structure}"

    return "UNCERTAIN", f"trend={trend}, structure={structure}"


# What each regime permits. The pipeline reads this rather than hardcoding
# strategy choices, so adding a regime cannot silently enable trading.
REGIME_POLICY = {
    "TRENDING_UP":     {"allow_long": True,  "strategy": "pullback_continuation", "size_mult": 1.0},
    "BREAKOUT":        {"allow_long": True,  "strategy": "breakout_confirmation", "size_mult": 0.75},
    "RANGE":           {"allow_long": True,  "strategy": "range_reversion",       "size_mult": 0.5},
    "LOW_VOLATILITY":  {"allow_long": False, "strategy": "wait_for_expansion",    "size_mult": 0.0},
    "HIGH_VOLATILITY": {"allow_long": False, "strategy": "stand_aside",           "size_mult": 0.0},
    "TRENDING_DOWN":   {"allow_long": False, "strategy": "stand_aside",           "size_mult": 0.0},
    "PANIC":           {"allow_long": False, "strategy": "halt",                  "size_mult": 0.0},
    "UNCERTAIN":       {"allow_long": False, "strategy": "do_nothing",            "size_mult": 0.0},
}

# Ranked worst-to-best. The overall regime takes the WORST of the higher
# timeframes: a 5m breakout inside a 4h panic is a 4h panic.
_SEVERITY = ["PANIC", "HIGH_VOLATILITY", "TRENDING_DOWN", "UNCERTAIN",
             "LOW_VOLATILITY", "RANGE", "BREAKOUT", "TRENDING_UP"]


def classify_asset(analysis):
    """Regime for every timeframe plus one overall verdict.

    The overall regime is driven by the CONTEXT frames (4h, 1h), not the
    tactical ones. A bullish 5m inside a bearish 4h is a bearish market that
    happens to have a green candle in it -- and the whole point of the
    multi-timeframe design is to stop treating that as a buy signal.
    """
    per_frame = {}
    for name, tf in analysis.get("timeframes", {}).items():
        regime, why = classify_timeframe(tf)
        per_frame[name] = {"regime": regime, "why": why}

    context = [per_frame[n]["regime"] for n in ("4h", "1h") if n in per_frame]
    if context:
        overall = min(context, key=lambda r: _SEVERITY.index(r)
                      if r in _SEVERITY else 0)
    else:
        overall = "UNCERTAIN"

    policy = REGIME_POLICY.get(overall, REGIME_POLICY["UNCERTAIN"])

    # Agreement across ALL frames, scored 0-1. This feeds the trade score
    # directly: full agreement is the strongest context evidence available.
    labels = [v["regime"] for v in per_frame.values()]
    bullish = sum(1 for r in labels if r in ("TRENDING_UP", "BREAKOUT"))
    bearish = sum(1 for r in labels if r in ("TRENDING_DOWN", "PANIC"))
    total = len(labels) or 1
    agreement = (bullish - bearish) / total

    return {
        "overall": overall,
        "why": next((per_frame[n]["why"] for n in ("4h", "1h")
                     if n in per_frame and per_frame[n]["regime"] == overall),
                    "derived from context frames"),
        "per_timeframe": per_frame,
        "policy": policy,
        "agreement": round(agreement, 3),
        "_agreement_doc": "+1 all frames bullish, -1 all bearish, 0 conflicted",
    }


if __name__ == "__main__":
    import crypto_data

    cfg = crypto_data.load_config()
    for pair in cfg["universe"]:
        try:
            analysis = crypto_data.analyze_asset(pair, cfg)
        except crypto_data.DataError as e:
            print(f"{pair}: DATA ERROR -- {e}")
            continue
        r = classify_asset(analysis)
        print(f"\n{pair}  ->  {r['overall']}   ({r['why']})")
        print(f"  agreement: {r['agreement']:+.2f}   "
              f"allow_long={r['policy']['allow_long']}  "
              f"strategy={r['policy']['strategy']}  "
              f"size_mult={r['policy']['size_mult']}")
        for name in ("5m", "15m", "1h", "4h"):
            if name in r["per_timeframe"]:
                v = r["per_timeframe"][name]
                print(f"    {name:>3}  {v['regime']:<16} {v['why']}")
