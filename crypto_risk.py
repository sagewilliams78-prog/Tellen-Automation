#!/usr/bin/env python3
"""
EVA CRYPTO v1 -- risk engine.

The strategy engine PROPOSES. This engine DISPOSES. Strategy can say BUY and
this module answers NO, and that answer is final. Every veto is named, so the
journal records not just that EVA declined but exactly which rule declined.

Sizing is always dollars-at-risk. Coin quantity is an OUTPUT, never an input.
DOGE at $0.08 and BTC at $77,000 get the same risk budget; a cheap unit price
is not cheap risk, and treating "5,000 DOGE" as a position size is the fastest
way to be accidentally enormous.

Hard rules that are NOT configurable:
  - never average down
  - never martingale
  - never increase size to recover a loss
"""

from datetime import datetime, timedelta, timezone


class Veto(Exception):
    """Raised only where a caller wants exceptions; approve() returns a
    structured refusal instead so every rejection is journalable."""


def _now(cfg=None):
    return datetime.now(timezone.utc)


def check_data_health(health, cfg):
    """Stale or disagreeing data means STOP. Never trade a guess."""
    if not health:
        return "no health record -- refusing to trade blind"
    if not health.get("robinhood_ok"):
        return "Robinhood unreachable"
    if not health.get("market_data_ok"):
        return "market data feed unhealthy"
    age = health.get("data_age_seconds")
    limit = cfg["risk"]["stale_data_seconds"]
    if age is None or age > limit:
        return f"data stale ({age}s > {limit}s)"
    dis = health.get("price_disagreement_pct")
    max_dis = cfg["data"]["max_price_disagreement_pct"]
    if dis is not None and dis > max_dis:
        return f"price sources disagree {dis:.2f}% > {max_dis}%"
    return None


def check_loss_limits(perf, cfg):
    """Daily / rolling-24h / weekly brakes. Rolling matters more than the
    calendar day on a 24/7 asset -- midnight is a reporting boundary, not a
    risk boundary."""
    r = cfg["risk"]
    if perf.get("realized_today_usd", 0.0) <= r["daily_loss_limit_usd"]:
        return (f"daily loss limit hit "
                f"(${perf['realized_today_usd']:.2f} <= ${r['daily_loss_limit_usd']:.2f})")
    if perf.get("realized_24h_usd", 0.0) <= r["rolling_24h_loss_limit_usd"]:
        return (f"rolling 24h loss limit hit "
                f"(${perf['realized_24h_usd']:.2f})")
    if perf.get("drawdown_7d_usd", 0.0) <= r["weekly_drawdown_limit_usd"]:
        return (f"weekly drawdown limit hit "
                f"(${perf['drawdown_7d_usd']:.2f})")
    return None


def check_cooldown(perf, cfg, now=None):
    """After a loss EVA waits. After repeated losses she waits much longer.

    This is not superstition: consecutive losses usually mean the regime has
    changed underneath the strategy, and the correct response is to stop and
    let new data arrive rather than to keep paying ~1.9% per attempt.
    """
    now = now or _now()
    r = cfg["risk"]

    consec = perf.get("consecutive_losses", 0)
    last_loss = perf.get("last_loss_at")
    if not last_loss:
        return None
    try:
        t = datetime.fromisoformat(last_loss)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None

    if consec >= r["cooldown_after_consecutive_losses"]:
        hrs = r["cooldown_after_consecutive_losses_hours"]
        if now - t < timedelta(hours=hrs):
            left = hrs - (now - t).total_seconds() / 3600
            return (f"{consec} consecutive losses -- cooling down "
                    f"{left:.1f}h more")

    mins = r["cooldown_after_loss_minutes"]
    if now - t < timedelta(minutes=mins):
        left = mins - (now - t).total_seconds() / 60
        return f"cooling down {left:.0f}m after a loss"
    return None


def check_exposure(positions, cfg, pair):
    """Concurrency and total-exposure caps."""
    r = cfg["risk"]
    open_pos = [p for p in positions.values() if p.get("quantity", 0) > 0]

    if len(open_pos) >= r["max_concurrent_positions"]:
        return (f"already at max concurrent positions "
                f"({len(open_pos)}/{r['max_concurrent_positions']})")

    if any(p.get("pair") == pair for p in open_pos):
        return f"already holding {pair} -- never average down"

    exposure = sum(p.get("notional_usd", 0.0) for p in open_pos)
    if exposure >= r["max_total_crypto_exposure_usd"]:
        return (f"total crypto exposure ${exposure:.2f} at cap "
                f"${r['max_total_crypto_exposure_usd']:.2f}")
    return None


def check_market_conditions(quote, cfg):
    """Spread and liquidity gates -- the venue-cost reality check."""
    r = cfg["risk"]
    if not quote:
        return "no broker quote"
    sp = quote.get("spread_pct")
    if sp is None:
        return "no spread available"
    if sp > r["max_spread_pct"]:
        return f"spread {sp:.2f}% > {r['max_spread_pct']:.2f}% cap"
    return None


def size_position(entry, stop, cfg, regime_size_mult=1.0, quote=None):
    """Dollars-at-risk sizing. Returns a plan or a refusal.

    quantity = risk_budget / (entry - stop)

    Then clamped by max notional, buying power, and the venue's minimum. The
    same arithmetic serves BTC and DOGE -- only the numbers differ.
    """
    r = cfg["risk"]
    if entry <= 0 or stop <= 0 or stop >= entry:
        return None, f"invalid levels (entry {entry}, stop {stop})"

    risk_per_unit = entry - stop
    budget = r["max_risk_per_trade_usd"] * max(0.0, regime_size_mult)
    if budget <= 0:
        return None, "regime size multiplier is zero"

    qty = budget / risk_per_unit
    notional = qty * entry

    capped_by = None
    if notional > r["max_notional_per_trade_usd"]:
        notional = r["max_notional_per_trade_usd"]
        qty = notional / entry
        capped_by = "max_notional_per_trade"

    if notional < 1.0:
        return None, f"notional ${notional:.2f} below venue minimum"

    # What the spread will really cost this position, stated in dollars so it
    # is comparable to the risk budget rather than hidden as a percentage.
    spread_cost = None
    if quote and quote.get("spread_pct") is not None:
        spread_cost = notional * quote["spread_pct"] / 100

    return {
        "quantity": qty,
        "notional_usd": round(notional, 2),
        "entry": entry,
        "stop": stop,
        "risk_usd": round(qty * risk_per_unit, 2),
        "risk_per_unit": risk_per_unit,
        "capped_by": capped_by,
        "regime_size_mult": regime_size_mult,
        "estimated_spread_cost_usd": (round(spread_cost, 2)
                                      if spread_cost is not None else None),
    }, None


def approve(pair, score, regime, quote, positions, perf, health, cfg,
            buying_power=None, now=None):
    """The gate. Returns (decision_dict, plan_or_None).

    decision.approved is True only when EVERY check passes. Any single veto
    refuses the trade, and the reason is recorded verbatim.
    """
    vetoes = []

    # Order matters: cheapest and most fundamental checks first.
    for name, result in (
        ("data_health", check_data_health(health, cfg)),
        ("loss_limits", check_loss_limits(perf, cfg)),
        ("cooldown", check_cooldown(perf, cfg, now)),
        ("exposure", check_exposure(positions, cfg, pair)),
        ("market_conditions", check_market_conditions(quote, cfg)),
    ):
        if result:
            vetoes.append({"rule": name, "reason": result})

    # Score gate. In Phase 1 only HIGH_CONVICTION is even considered, because
    # the thresholds are explicitly uncalibrated until walk-forward runs.
    if score.get("band") != "HIGH_CONVICTION":
        vetoes.append({
            "rule": "score_threshold",
            "reason": (f"score {score.get('score')} [{score.get('band')}] -- "
                       f"only HIGH_CONVICTION trades until thresholds are "
                       f"calibrated"),
        })

    if vetoes:
        return {
            "approved": False,
            "pair": pair,
            "vetoes": vetoes,
            "primary_reason": vetoes[0]["reason"],
        }, None

    # ---- Build the plan -------------------------------------------------
    mark = quote["mark"]
    stop_pct = cfg["position_management"]["stop_loss_pct"]
    target_pct = cfg["position_management"]["take_profit_pct"]
    entry = mark
    stop = entry * (1 + stop_pct / 100)
    target = entry * (1 + target_pct / 100)

    # The trade must clear the venue's round-trip cost with real margin.
    min_target = cfg["risk"]["min_target_pct"]
    if target_pct < min_target:
        return {
            "approved": False, "pair": pair,
            "vetoes": [{"rule": "min_target",
                        "reason": (f"target {target_pct}% below {min_target}% "
                                   f"floor -- cannot clear the ~"
                                   f"{cfg['execution_costs']['assumed_round_trip_cost_pct']}% "
                                   f"round-trip cost")}],
            "primary_reason": "target too small for venue cost",
        }, None

    plan, err = size_position(
        entry, stop, cfg,
        regime.get("policy", {}).get("size_mult", 1.0), quote)
    if err:
        return {"approved": False, "pair": pair,
                "vetoes": [{"rule": "sizing", "reason": err}],
                "primary_reason": err}, None

    if buying_power is not None and plan["notional_usd"] > buying_power:
        return {"approved": False, "pair": pair,
                "vetoes": [{"rule": "buying_power",
                            "reason": (f"needs ${plan['notional_usd']:.2f}, "
                                       f"have ${buying_power:.2f}")}],
                "primary_reason": "insufficient buying power"}, None

    plan["pair"] = pair
    plan["target"] = target
    plan["target_pct"] = target_pct
    plan["stop_pct"] = stop_pct
    plan["score"] = score.get("score")

    return {"approved": True, "pair": pair, "vetoes": [],
            "primary_reason": f"approved at score {score.get('score')}"}, plan


if __name__ == "__main__":
    import json
    import crypto_data

    cfg = crypto_data.load_config()

    # Real arithmetic check: the same $3 risk budget on both assets.
    print("Dollars-at-risk sizing -- identical budget, wildly different unit prices:\n")
    for pair, entry in (("BTC-USD", 77231.17), ("DOGE-USD", 0.081909)):
        stop = entry * 0.97
        plan, err = size_position(entry, stop, cfg, 1.0,
                                  {"spread_pct": 1.90})
        if err:
            print(f"  {pair}: {err}")
            continue
        print(f"  {pair}")
        print(f"    entry ${entry:,.6f}  stop ${stop:,.6f}")
        print(f"    quantity {plan['quantity']:.8f}")
        print(f"    notional ${plan['notional_usd']}  risk ${plan['risk_usd']}"
              f"  capped_by={plan['capped_by']}")
        print(f"    spread will cost ${plan['estimated_spread_cost_usd']} "
              f"of that position\n")
