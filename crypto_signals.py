#!/usr/bin/env python3
"""
EVA CRYPTO v1 -- weighted trade-confidence engine.

Replaces "EMA crossed = BUY" with a scored assessment that records WHY it
reached its number. Every factor is stored on the result, so the journal can
answer "why did EVA act" months later rather than just "she acted".

Score = weighted positive factors  -  penalties.

Penalties matter more here than on a normal venue. Robinhood's measured crypto
spread is ~1.9% round trip (all three assets, peak session, 2026-09-01), so
spread is not a rounding detail -- it is the largest single cost in the trade
and is weighted accordingly.

Pure functions. No I/O, no orders. Directly testable on any snapshot.
"""


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def score_regime(regime):
    """Context is the heaviest single factor -- trading against the regime is
    the most reliable way to lose on a venue with a 1.9% toll."""
    policy = regime.get("policy", {})
    overall = regime.get("overall", "UNCERTAIN")
    if not policy.get("allow_long"):
        return 0.0, f"{overall} does not permit longs"
    table = {"TRENDING_UP": 1.0, "BREAKOUT": 0.85, "RANGE": 0.45}
    v = table.get(overall, 0.0)
    return v, f"{overall} permits longs (x{policy.get('size_mult')})"


def score_multi_timeframe(regime):
    """Agreement across 5m/15m/1h/4h, mapped from [-1,+1] to [0,1].

    A bullish 5m inside a bearish 4h scores near zero by construction -- this
    is the factor that stops EVA buying green candles in downtrends.
    """
    a = regime.get("agreement", 0.0)
    return _clamp((a + 1) / 2), f"agreement {a:+.2f}"


def score_trend(frames):
    """How many frames are in an EMA uptrend, weighted toward longer frames."""
    weights = {"5m": 0.1, "15m": 0.2, "1h": 0.3, "4h": 0.4}
    total = got = 0.0
    parts = []
    for name, w in weights.items():
        tf = frames.get(name)
        if not tf:
            continue
        total += w
        if tf.get("trend") == "UP":
            got += w
            parts.append(f"{name}:UP")
        elif tf.get("trend") == "DOWN":
            parts.append(f"{name}:DOWN")
    if total == 0:
        return 0.0, "no trend data"
    return got / total, ", ".join(parts) or "flat"


def score_momentum(frames):
    """RSI in the constructive band plus positive rate-of-change.

    Deliberately penalises RSI > 70: chasing an extended move on a 1.9%-cost
    venue means paying the toll at the worst possible price.
    """
    tf = frames.get("1h") or frames.get("15m")
    if not tf:
        return 0.0, "no momentum data"
    rsi = tf.get("rsi14")
    roc = tf.get("roc_10")
    if rsi is None:
        return 0.0, "no RSI"

    if 50 <= rsi <= 65:
        r = 1.0
    elif 45 <= rsi < 50:
        r = 0.7
    elif 65 < rsi <= 70:
        r = 0.5
    elif rsi > 70:
        r = 0.1
    elif 35 <= rsi < 45:
        r = 0.35
    else:
        r = 0.15

    m = 0.5
    if roc is not None:
        m = 1.0 if roc > 0.5 else 0.6 if roc > 0 else 0.2
    v = r * 0.7 + m * 0.3
    return _clamp(v), f"RSI {rsi:.1f}, ROC {roc if roc is None else round(roc, 2)}%"


def score_volume(frames):
    """Real participation. A move on no volume is not a move."""
    tf = frames.get("15m") or frames.get("5m")
    if not tf:
        return 0.0, "no volume data"
    vx = tf.get("volume_ratio")
    if vx is None:
        return 0.0, "no volume ratio"
    if vx >= 2.0:
        v = 1.0
    elif vx >= 1.3:
        v = 0.8
    elif vx >= 0.8:
        v = 0.5
    elif vx >= 0.5:
        v = 0.25
    else:
        v = 0.05
    return v, f"volume {vx:.2f}x baseline"


def score_order_book(quote):
    """Bid/ask imbalance from the real broker quote.

    Without a Level 2 feed this is a coarse read (mark's position between bid
    and ask). Honest and useful, but it is NOT true book depth -- when the
    Coinbase L2 WebSocket lands this factor should be upgraded rather than
    left looking more precise than it is.
    """
    if not quote:
        return 0.5, "no quote (neutral)"
    bid, ask, mark = quote.get("bid"), quote.get("ask"), quote.get("mark")
    if not (bid and ask and mark) or ask <= bid:
        return 0.5, "degenerate book (neutral)"
    pos = (mark - bid) / (ask - bid)
    return _clamp(pos), f"mark sits {pos:.0%} toward ask"


def score_liquidity(quote, cfg):
    """Tradability. On this venue the spread IS the liquidity signal."""
    if not quote:
        return 0.0, "no quote"
    sp = quote.get("spread_pct")
    if sp is None:
        return 0.0, "no spread"
    floor = cfg["execution_costs"]["assumed_round_trip_cost_pct"]
    if sp <= floor * 1.05:
        return 1.0, f"spread {sp:.2f}% at structural floor"
    if sp <= floor * 1.25:
        return 0.6, f"spread {sp:.2f}% mildly wide"
    if sp <= floor * 1.6:
        return 0.25, f"spread {sp:.2f}% wide"
    return 0.0, f"spread {sp:.2f}% far above floor"


def score_relative_strength(frames, peers):
    """Is this asset outperforming the others in the universe right now?"""
    tf = frames.get("1h")
    if not tf or tf.get("roc_10") is None:
        return 0.5, "no relative data (neutral)"
    mine = tf["roc_10"]
    others = [p for p in peers if p is not None]
    if not others:
        return 0.5, "no peers"
    avg = sum(others) / len(others)
    diff = mine - avg
    v = _clamp(0.5 + diff / 4)
    return v, f"1h ROC {mine:+.2f}% vs peers {avg:+.2f}%"


# ------------------------------------------------------------- penalties

def penalty_spread(quote, cfg, max_penalty):
    """The dominant cost on this venue. A trade must clear ~1.9% round trip
    before it earns anything, so a widened book is disqualifying, not just
    unattractive."""
    if not quote or quote.get("spread_pct") is None:
        return max_penalty, "no spread data -- assume worst"
    sp = quote["spread_pct"]
    cap = cfg["risk"]["max_spread_pct"]
    if sp > cap:
        return max_penalty, f"spread {sp:.2f}% exceeds {cap:.2f}% cap"
    floor = cfg["execution_costs"]["assumed_round_trip_cost_pct"]
    excess = max(0.0, sp - floor)
    span = max(0.01, cap - floor)
    return max_penalty * _clamp(excess / span), f"spread {sp:.2f}%"


def penalty_volatility(frames, max_penalty):
    """Violent conditions widen real slippage and make stops unreliable."""
    tf = frames.get("1h")
    if not tf or tf.get("atr_pct") is None:
        return max_penalty * 0.5, "no volatility data"
    atr = tf["atr_pct"]
    if atr <= 1.0:
        return 0.0, f"ATR {atr:.2f}% normal"
    if atr >= 4.0:
        return max_penalty, f"ATR {atr:.2f}% extreme"
    return max_penalty * ((atr - 1.0) / 3.0), f"ATR {atr:.2f}% elevated"


def penalty_news(news, max_penalty):
    """News never TRIGGERS a trade -- it can only reduce or veto one.

    A hard event (exchange outage, security incident, major regulatory shock)
    zeroes the score outright rather than merely discounting it.
    """
    if not news:
        return 0.0, "no news adapter"
    if news.get("halt"):
        return max_penalty, f"HALT: {news.get('reason', 'event risk')}"
    sev = news.get("severity", 0)
    return max_penalty * _clamp(sev / 10) * 0.3, news.get("reason", "elevated event risk")


# ---------------------------------------------------------------- engine

def score_asset(pair, analysis, regime, quote, cfg, peers=None, news=None):
    """Full weighted score with every factor retained for the journal."""
    frames = analysis.get("timeframes", {})
    w = cfg["trade_score"]["weights"]
    p = cfg["trade_score"]["penalties"]

    factors = {}
    total = 0.0

    for key, fn, args in (
        ("regime", score_regime, (regime,)),
        ("multi_timeframe_agreement", score_multi_timeframe, (regime,)),
        ("trend", score_trend, (frames,)),
        ("momentum", score_momentum, (frames,)),
        ("volume", score_volume, (frames,)),
        ("order_book", score_order_book, (quote,)),
        ("liquidity", score_liquidity, (quote, cfg)),
        ("relative_strength", score_relative_strength, (frames, peers or [])),
    ):
        value, why = fn(*args)
        weight = w.get(key, 0)
        pts = value * weight
        total += pts
        factors[key] = {"value": round(value, 3), "weight": weight,
                        "points": round(pts, 2), "why": why}

    penalties = {}
    for key, fn, args, cap in (
        ("spread", penalty_spread, (quote, cfg), p["spread_penalty_max"]),
        ("volatility", penalty_volatility, (frames,), p["volatility_penalty_max"]),
        ("news_event", penalty_news, (news,), p["news_event_penalty_max"]),
    ):
        pts, why = fn(*args, cap)
        total -= pts
        penalties[key] = {"points": round(-pts, 2), "why": why}

    final = max(0.0, min(100.0, total))
    t = cfg["trade_score"]["thresholds"]
    if final >= t["high_conviction"]:
        band = "HIGH_CONVICTION"
    elif final > t["watch"]:
        band = "GOOD"
    elif final > t["no_trade"]:
        band = "WATCH"
    else:
        band = "NO_TRADE"

    # The single most useful line for a human: why NOT.
    if band == "NO_TRADE":
        worst_pen = min(penalties.items(), key=lambda kv: kv[1]["points"])
        weakest = min(factors.items(), key=lambda kv: kv[1]["points"])
        if worst_pen[1]["points"] <= -10:
            reason = f"{worst_pen[0]}: {worst_pen[1]['why']}"
        else:
            reason = f"weak {weakest[0]}: {weakest[1]['why']}"
    else:
        reason = f"score {final:.0f}"

    return {
        "pair": pair,
        "score": round(final, 1),
        "band": band,
        "reason": reason,
        "factors": factors,
        "penalties": penalties,
        "_doc": "score = sum(factor.points) - sum(penalty magnitudes), clamped 0-100",
    }


if __name__ == "__main__":
    import crypto_data
    import crypto_regime

    cfg = crypto_data.load_config()
    pairs = list(cfg["universe"])

    analyses, regimes = {}, {}
    for pair in pairs:
        try:
            analyses[pair] = crypto_data.analyze_asset(pair, cfg)
            regimes[pair] = crypto_regime.classify_asset(analyses[pair])
        except crypto_data.DataError as e:
            print(f"{pair}: DATA ERROR -- {e}")

    for pair in analyses:
        peers = [analyses[o]["timeframes"].get("1h", {}).get("roc_10")
                 for o in analyses if o != pair]
        # No live quote in this standalone test -- crypto_broker supplies it
        # in the real pipeline. Absent a quote, spread scores worst-case,
        # which is the correct conservative default.
        s = score_asset(pair, analyses[pair], regimes[pair], None, cfg, peers)
        print(f"\n{pair}  score={s['score']}  [{s['band']}]  -- {s['reason']}")
        for k, v in s["factors"].items():
            print(f"    +{v['points']:>5.1f}  {k:<26} {v['why']}")
        for k, v in s["penalties"].items():
            if v["points"]:
                print(f"    {v['points']:>6.1f}  {k:<26} {v['why']}")
