#!/usr/bin/env python3
"""
Eva's setup scorer -- judge the chart, don't AND together filters.

SINGLE SOURCE OF TRUTH. The backtest and the live bot both import score_setup()
from here. If the live bot had its own copy, the two would drift and the
backtest would stop describing the thing that actually trades -- which is the
failure mode that made every earlier optimisation unverifiable.

WHY THIS EXISTS (Sage's diagnosis, 2026-09-02)
----------------------------------------------
Eva's filters are AND-ed, so they compound and none can see any other:

    141,960 bars -> 36,368 in buy zone -> 11,687 past the 3% width gate
                 -> 5,308 past the bullish-candle gate

3.7% survives, and 45% of the survivors still have reward-to-risk below 0.50.
The cascade selects FEW setups, not GOOD ones. On one afternoon it made both
possible errors at once:

    TSLA  zone width 2.96%  REJECTED by a 3.0% gate, after 37 buy-zone visits
                            with 14 bullish candles
    XOM   zone width 4.25%  ACCEPTED, with the target 0.38% away against a 4%
                            stop -- reward-to-risk 0.09, breakeven win rate 92%

A gate cannot trade one factor against another. A score can: TSLA's near-miss
width costs it two points instead of disqualifying it, and XOM's hopeless
reward-to-risk costs it five.

MEASURED (96 sessions, 20 symbols, $250, real spreads, real slot limits)
------------------------------------------------------------------------
                     cascade    score>=21
    net P&L           $15.81      $48.21
    profit factor       1.19        1.61
    green days           42%         52%
    worst day         -$9.96      -$7.59

Thresholds 21, 22 and 23 all beat the cascade on profit AND green days in all
three train/test splits -- a plateau, not a spike -- including split B, where
every other change tested that day failed.

NOT PROVEN. One dataset, one rallying regime, never seen a downtrend. Default
mode is SHADOW: score everything, log what it would have done, place nothing.

THE WEIGHTS ARE NOT TUNED. Six factors, equal weight, coarse 0-5 bands, all
fixed from trading reasoning BEFORE any result was seen. A scoring model has
far more freedom than a gate and is correspondingly easier to fit to noise;
the protection is refusing to adjust the bands afterwards. If it only works
after tweaking them, it does not work.
"""

MAX_SCORE = 30
DEFAULT_THRESHOLD = 21

FACTORS = ("reward_risk", "zone_width", "candle", "depth", "volume", "spread")


def score_setup(entry, stop, target, zone_low, swing_low,
                candle_open, candle_high, candle_low,
                volume, avg_volume, spread_pct):
    """Score one setup 0-30. Returns (total, {factor: points}) or (None, None)
    if the setup is structurally impossible (inverted stop or target).

    Takes plain numbers rather than the bot's dicts so the backtest and the
    live bot can both call it without sharing data structures.
    """
    if entry <= 0 or stop >= entry or target <= entry or zone_low <= 0:
        return None, None

    # 1. REWARD-TO-RISK, net of the round-trip spread. The cascade never looked
    #    at this at all, and it is what decides whether a trade is winnable.
    rr = (target - entry - entry * spread_pct / 100) / (entry - stop)
    s_rr = 0 if rr < 0.25 else 1 if rr < 0.5 else 2 if rr < 0.75 else \
           3 if rr < 1.0 else 4 if rr < 1.5 else 5

    # 2. ZONE WIDTH -- was a hard 3% gate. Scored, 2.96% is nearly as good as
    #    3.04% rather than being the whole difference between trading and not.
    width = (zone_low - swing_low) / zone_low * 100
    s_w = 0 if width < 1 else 1 if width < 2 else 2 if width < 3 else \
          3 if width < 4.5 else 4 if width < 6 else 5

    # 3. CANDLE -- was a hard bullish/not-bullish gate, which discards a doji
    #    sitting exactly on the low. Graded by body as a share of the range.
    rng = candle_high - candle_low
    body = (entry - candle_open) / rng if rng > 0 else 0.0
    s_c = 0 if body < -0.3 else 1 if body < 0 else 2 if body < 0.15 else \
          3 if body < 0.35 else 4 if body < 0.6 else 5

    # 4. DEPTH into the zone. Buying near the floor of the range beats buying
    #    at its ceiling, and the cascade treated both identically.
    depth = (zone_low - candle_low) / zone_low * 100
    s_d = 0 if depth < 0 else 1 if depth < 0.15 else 2 if depth < 0.4 else \
          3 if depth < 0.8 else 4 if depth < 1.5 else 5

    # 5. VOLUME -- someone else defending the level too. v13 tracked this but
    #    never gated on it (gating it hurt P&L); as a score it contributes.
    ratio = (volume / avg_volume) if avg_volume else 1.0
    s_v = 0 if ratio < 0.4 else 1 if ratio < 0.7 else 2 if ratio < 1.0 else \
          3 if ratio < 1.4 else 4 if ratio < 2.0 else 5

    # 6. SPREAD COST. IBRX at 0.127% eats a 0.4% target alive; NVDA at 0.005%
    #    does not. Cheap symbols never got credit for being cheap.
    s_sp = 5 if spread_pct < 0.015 else 4 if spread_pct < 0.025 else \
           3 if spread_pct < 0.04 else 2 if spread_pct < 0.07 else \
           1 if spread_pct < 0.11 else 0

    parts = {"reward_risk": s_rr, "zone_width": s_w, "candle": s_c,
             "depth": s_d, "volume": s_v, "spread": s_sp}
    return sum(parts.values()), parts


def explain(total, parts):
    """One-line human summary for the log, e.g. 21/30 rr5 w3 c4 d4 v2 sp3."""
    if total is None:
        return "n/a"
    short = {"reward_risk": "rr", "zone_width": "w", "candle": "c",
             "depth": "d", "volume": "v", "spread": "sp"}
    bits = " ".join(f"{short[k]}{parts[k]}" for k in FACTORS)
    return f"{total}/{MAX_SCORE} {bits}"
