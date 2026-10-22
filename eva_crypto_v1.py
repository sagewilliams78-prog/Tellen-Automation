#!/usr/bin/env python3
"""
EVA CRYPTO v1 -- the desk.

Runs the full pipeline continuously and writes real state for Trading HQ:

  MARKET DATA -> HEALTH -> REGIME -> MULTI-TIMEFRAME -> SIGNALS -> SCORE
              -> RISK ENGINE -> PREVIEW -> (EXECUTION) -> POSITIONS -> JOURNAL

Completely separate from sage_bot_v13.py. Its own config, state directory,
journal and risk budget. It never reads or writes anything the equity desk owns.

PHASE 1 BEHAVIOUR (config.execution.enabled = false):
Everything runs for real -- real market data, real broker reads, real scoring,
real risk decisions, real order PREVIEWS -- but no order is placed. That is the
point: prove the intelligence is correct before giving it money.

The philosophy this implements:
    most of the time   WAIT
    evidence strong    PREPARE
    evidence + risk    ACT
    thesis fails       EXIT
    data unreliable    STOP
"""

import asyncio
import csv
import json
import signal
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import crypto_data
import crypto_regime
import crypto_signals
import crypto_risk
from crypto_broker import CryptoBroker, BrokerError

BASE = Path(__file__).resolve().parent
STATE = BASE / "_crypto_state"
JOURNAL = BASE / "_crypto_state" / "journal.csv"

JOURNAL_COLUMNS = [
    "timestamp", "pair", "action", "price", "regime", "agreement",
    "tf_5m", "tf_15m", "tf_1h", "tf_4h", "rsi_1h", "atr_pct_1h",
    "volume_ratio", "spread_pct", "score", "band", "reason",
    "approved", "veto", "planned_qty", "planned_notional",
    "planned_risk", "planned_stop", "planned_target", "preview_ok",
]

_running = True


def log(msg):
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %I:%M:%S %p %Z")
    print(f"[{ts}] {msg}", flush=True)


def _stop(signum, frame):
    global _running
    _running = False
    log(f"signal {signum} -- shutting down after this cycle")


def journal_row(row):
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    new = not JOURNAL.exists()
    with open(JOURNAL, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=JOURNAL_COLUMNS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def load_performance():
    p = crypto_data.read_json(STATE / "performance.json", None)
    if not p:
        p = {
            "realized_today_usd": 0.0,
            "realized_24h_usd": 0.0,
            "drawdown_7d_usd": 0.0,
            "consecutive_losses": 0,
            "last_loss_at": None,
            "trades": [],
        }
    return p


def build_health(analyses, quotes, broker_ok, cfg):
    """Real data-health record. Anything unhealthy means the risk engine
    refuses to trade -- health is a gate, not a display field."""
    now = datetime.now(timezone.utc)
    ages, disagreements = [], []

    # A candle's timestamp is the START of its window, so the newest 5m bar is
    # legitimately up to 300s old while still being the CURRENT bar. Measuring
    # raw age flagged healthy data as stale at 316s. What matters is lateness
    # BEYOND the bar's own span -- that is what indicates a feed has stopped.
    bar_seconds = cfg["data"]["candle_granularity_seconds"].get("5m", 300)
    for pair, a in analyses.items():
        tf = a["timeframes"].get("5m")
        if tf and tf.get("bar_time"):
            try:
                bar = datetime.fromisoformat(tf["bar_time"])
                if bar.tzinfo is None:
                    bar = bar.replace(tzinfo=timezone.utc)
                lateness = (now - bar).total_seconds() - bar_seconds
                ages.append(max(0.0, lateness))
            except ValueError:
                pass
        q = quotes.get(pair)
        if q and tf and tf.get("close"):
            # Coinbase (signals) vs Robinhood (execution) legitimately differ
            # by roughly the spread. A gap far beyond that means one feed is
            # wrong and neither should be traded on.
            disagreements.append(
                abs(q["mark"] - tf["close"]) / tf["close"] * 100)

    age = max(ages) if ages else None
    dis = max(disagreements) if disagreements else None

    return {
        "generated_at": now.isoformat(),
        "robinhood_ok": broker_ok,
        "market_data_ok": bool(analyses),
        "data_age_seconds": round(age) if age is not None else None,
        "price_disagreement_pct": round(dis, 3) if dis is not None else None,
        "assets_ok": sorted(analyses),
        "_disagreement_doc": ("Coinbase vs Robinhood. ~1.9% is EXPECTED here "
                              "-- that is the spread, not an error."),
    }


async def run_cycle(cfg, broker):
    """One full pass of the pipeline. Returns the state written for HQ."""
    pairs = [p for p, v in cfg["universe"].items() if v.get("enabled")]

    # --- MARKET DATA -----------------------------------------------------
    analyses, data_errors = {}, {}
    for pair in pairs:
        try:
            analyses[pair] = crypto_data.analyze_asset(pair, cfg)
        except crypto_data.DataError as e:
            data_errors[pair] = str(e)
            log(f"{pair}: DATA ERROR -- {e}")

    # --- BROKER TRUTH ----------------------------------------------------
    broker_ok, snap = True, {}
    try:
        snap = await broker.snapshot(pairs)
    except BrokerError as e:
        broker_ok = False
        log(f"BROKER ERROR -- {e}")

    quotes = snap.get("quotes", {})
    positions = snap.get("positions", {})
    buying_power = snap.get("buying_power")

    # --- HEALTH ----------------------------------------------------------
    health = build_health(analyses, quotes, broker_ok, cfg)
    crypto_data.atomic_json(STATE / "health.json", health)

    perf = load_performance()
    assets, candidate = {}, None

    for pair in pairs:
        if pair not in analyses:
            assets[pair] = {"pair": pair, "error": data_errors.get(pair)}
            continue

        analysis = analyses[pair]
        regime = crypto_regime.classify_asset(analysis)
        quote = quotes.get(pair)

        peers = [analyses[o]["timeframes"].get("1h", {}).get("roc_10")
                 for o in analyses if o != pair]
        score = crypto_signals.score_asset(pair, analysis, regime, quote,
                                           cfg, peers, news=None)

        decision, plan = crypto_risk.approve(
            pair, score, regime, quote, positions, perf, health, cfg,
            buying_power)

        frames = analysis["timeframes"]
        tf1h = frames.get("1h", {})

        assets[pair] = {
            "pair": pair,
            "price": quote["mark"] if quote else tf1h.get("close"),
            "quote": quote,
            "regime": regime["overall"],
            "regime_why": regime["why"],
            "agreement": regime["agreement"],
            "policy": regime["policy"],
            "timeframes": {
                n: {"trend": frames[n]["trend"],
                    "structure": frames[n]["structure"],
                    "rsi14": frames[n]["rsi14"],
                    "atr_pct": frames[n]["atr_pct"],
                    "volume_ratio": frames[n]["volume_ratio"],
                    "close": frames[n]["close"],
                    "regime": regime["per_timeframe"][n]["regime"]}
                for n in frames
            },
            "score": score["score"],
            "band": score["band"],
            "reason": score["reason"],
            "factors": score["factors"],
            "penalties": score["penalties"],
            "approved": decision["approved"],
            "veto": decision.get("primary_reason"),
            "vetoes": decision.get("vetoes", []),
            "plan": plan,
            "position": positions.get(pair),
        }

        journal_row({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pair": pair,
            "action": "APPROVED" if decision["approved"] else "NO_TRADE",
            "price": quote["mark"] if quote else None,
            "regime": regime["overall"],
            "agreement": regime["agreement"],
            "tf_5m": frames.get("5m", {}).get("trend"),
            "tf_15m": frames.get("15m", {}).get("trend"),
            "tf_1h": frames.get("1h", {}).get("trend"),
            "tf_4h": frames.get("4h", {}).get("trend"),
            "rsi_1h": tf1h.get("rsi14"),
            "atr_pct_1h": tf1h.get("atr_pct"),
            "volume_ratio": frames.get("15m", {}).get("volume_ratio"),
            "spread_pct": quote["spread_pct"] if quote else None,
            "score": score["score"],
            "band": score["band"],
            "reason": score["reason"],
            "approved": decision["approved"],
            "veto": decision.get("primary_reason"),
            "planned_qty": plan["quantity"] if plan else None,
            "planned_notional": plan["notional_usd"] if plan else None,
            "planned_risk": plan["risk_usd"] if plan else None,
            "planned_stop": plan["stop"] if plan else None,
            "planned_target": plan["target"] if plan else None,
            "preview_ok": None,
        })

        if decision["approved"] and plan:
            if candidate is None or plan["score"] > candidate["plan"]["score"]:
                candidate = {"pair": pair, "plan": plan, "score": score}

    # --- PREVIEW / EXECUTION --------------------------------------------
    execution = {"enabled": cfg["execution"]["enabled"], "acted": False,
                 "candidate": None, "preview": None, "note": None}

    if candidate:
        plan = candidate["plan"]
        execution["candidate"] = plan
        crypto_data.atomic_json(STATE / "candidate_order.json", {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "plan": plan,
        })
        log(f"CANDIDATE {plan['pair']} score={plan['score']} "
            f"qty={plan['quantity']:.8f} notional=${plan['notional_usd']}")

        # A preview is real and free -- always run it, even in Phase 1, so the
        # execution path is exercised and its estimated cost is journalled.
        try:
            prev = await broker.preview(
                plan["pair"], "buy",
                quantity=plan["quantity"],
                limit_price=plan["entry"])
            execution["preview"] = {"ok": True, "raw": str(prev)[:500]}
            log(f"PREVIEW OK for {plan['pair']}")
        except BrokerError as e:
            execution["preview"] = {"ok": False, "error": str(e)}
            log(f"PREVIEW FAILED for {plan['pair']}: {e}")

        if not cfg["execution"]["enabled"]:
            execution["note"] = ("PHASE 1 -- execution disabled in config. "
                                 "Order was scored, risk-approved and "
                                 "previewed but NOT placed.")
            log(execution["note"])
    else:
        crypto_data.atomic_json(STATE / "candidate_order.json", {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "plan": None,
        })

    # --- STATE FOR HQ ----------------------------------------------------
    market = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_local": datetime.now().astimezone().strftime(
            "%Y-%m-%d %I:%M:%S %p %Z"),
        "phase": cfg["phase"],
        "execution_enabled": cfg["execution"]["enabled"],
        "assets": assets,
        "health": health,
        "buying_power": buying_power,
        "positions": positions,
        "execution": execution,
        "venue_cost_pct": cfg["execution_costs"]["assumed_round_trip_cost_pct"],
    }
    crypto_data.atomic_json(STATE / "market.json", market)
    crypto_data.atomic_json(STATE / "broker.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "buying_power": buying_power,
        "positions": positions,
        "open_orders": snap.get("open_orders", []),
        "ok": broker_ok,
    })
    crypto_data.atomic_json(STATE / "performance.json", perf)

    for pair, a in assets.items():
        if "error" in a:
            log(f"{pair}: ERROR {a['error']}")
            continue
        pos = a.get("position")
        tail = (f"HOLDING {pos['quantity']:.8f}" if pos
                else (a.get("veto") or a.get("reason")))
        log(f"{pair}: ${a['price']:,.6f} | {a['regime']} | "
            f"score {a['score']} [{a['band']}] | {tail}")

    return market


async def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    cfg = crypto_data.load_config()
    pairs = [p for p, v in cfg["universe"].items() if v.get("enabled")]

    print("=" * 74, flush=True)
    print("EVA CRYPTO v1", flush=True)
    print("=" * 74, flush=True)
    print(f"  universe          {', '.join(pairs)}", flush=True)
    print(f"  phase             {cfg['phase']}", flush=True)
    print(f"  execution         "
          f"{'LIVE' if cfg['execution']['enabled'] else 'DISABLED (analysis only)'}",
          flush=True)
    print(f"  venue round-trip  "
          f"{cfg['execution_costs']['assumed_round_trip_cost_pct']}% "
          f"(measured, structural)", flush=True)
    print(f"  risk/trade        ${cfg['risk']['max_risk_per_trade_usd']}", flush=True)
    print(f"  max notional      ${cfg['risk']['max_notional_per_trade_usd']}", flush=True)
    print(f"  target / stop     "
          f"+{cfg['position_management']['take_profit_pct']}% / "
          f"{cfg['position_management']['stop_loss_pct']}%", flush=True)
    print(f"  daily loss limit  ${cfg['risk']['daily_loss_limit_usd']}", flush=True)
    print(f"  max spread        {cfg['risk']['max_spread_pct']}%", flush=True)
    print("=" * 74, flush=True)

    interval = cfg["health"]["heartbeat_seconds"]

    while _running:
        try:
            async with CryptoBroker(cfg) as broker:
                await run_cycle(cfg, broker)
        except Exception as e:
            log(f"CYCLE ERROR {type(e).__name__}: {e}")
            traceback.print_exc()

        for _ in range(interval):
            if not _running:
                break
            await asyncio.sleep(1)

    log("stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
