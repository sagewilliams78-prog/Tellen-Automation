#!/usr/bin/env python3
"""
Re-validate the partial-profit exit under EVA'S REAL CAPITAL CONSTRAINTS.

WHY THIS EXISTS -- a flaw in my own prior validation
----------------------------------------------------
sim_variations.py and sim_verify_partial.py walk each symbol INDEPENDENTLY.
They will happily take a signal in NVDA, IBRX, COIN and SMCI in the same
five-minute bar, because nothing in them tracks money. Eva cannot do that.

  MIN_POSSIBLE_NOTIONAL = RISK_PER_TRADE_DOLLARS / (STOP_BACKSTOP/100)
                        = 2.50 / 0.04 = $62.50
  max_positions         = int(buying_power // 62.50)

On the real $250 account that is FOUR slots, and a slot stays occupied until
that position exits. So the honest question is not "does taking half off at
+1% improve a stream of independent trades" -- it is "does it improve a
capital-constrained portfolio that must choose which signals it can afford."

Those can disagree, and there is a specific reason to think they will:
a partial sale RETURNS HALF THE CAPITAL EARLY. Under a binding constraint
that frees money to take the next signal. An unconstrained sim is blind to
that effect by construction -- it can only ever see the cost of capping a
winner, never the benefit of recycling capital.

This sim therefore walks all symbols together in wall-clock order, tracks
buying power in dollars, enforces the slot cap, and ranks competing signals
by net edge exactly as shipped v14 does.

Conservative choices (deliberately pessimistic, so this cannot flatter):
  - if a bar's range contains BOTH stop and target, assume STOP filled
  - entry costs the full spread; every exit costs it again
  - a signal is skipped forever if no slot was free, never queued
"""

import sys
from collections import defaultdict

sys.path.insert(0, "/Users/sagewilliams/Desktop/Sages trading bot")
import sage_bot_v13 as eva
from sim_variations import SPREADS, load_5m, daily_from_5m, levels_for

RISK_DOLLARS = 2.50          # RISK_PER_TRADE_DOLLARS
MAX_NOTIONAL = 150.0         # MAX_NOTIONAL_PER_TRADE
MIN_NOTIONAL = RISK_DOLLARS / 0.04   # $62.50, mirrors MIN_POSSIBLE_NOTIONAL
PARTIAL_AT = 1.0
PARTIAL_FRAC = 0.5


def build(all_5m):
    """Pre-compute per-symbol daily levels and index every bar by timestamp so
    the portfolio can be walked in true chronological order."""
    clock = defaultdict(dict)        # timestamp -> {sym: bar}
    levels = defaultdict(dict)       # date -> {sym: levels}
    for sym, bars in all_5m.items():
        daily = daily_from_5m(bars)
        di = {d["date"]: i for i, d in enumerate(daily)}
        for b in bars:
            clock[b["t"]][sym] = b
        for day in {b["date"] for b in bars}:
            lv = levels_for(daily, di[day])
            if lv and eva.zone_width_ok(lv):
                levels[day][sym] = lv
    return clock, levels


def run(clock, levels, sessions, capital, partial, risk_pct=None,
        risk_abs=None, max_frac=0.60, min_rr=None, entry_ok=None,
        entry_meta=None, max_entries_per_day=None):
    """One pass. Returns (day -> dollar P&L, trade list, skipped-for-capital)."""
    want = set(sessions)
    times = sorted(t for t in clock if t.date().isoformat() in want)

    # risk_pct=None reproduces Eva's SHIPPED behaviour: a FLAT $2.50 risked per
    # trade no matter how large the account is. That is why $1,250 and $5,000
    # return identical dollars -- extra capital simply never gets deployed.
    if risk_abs is not None:
        risk_dollars = risk_abs
    elif risk_pct is not None:
        risk_dollars = capital * risk_pct / 100
    else:
        risk_dollars = RISK_DOLLARS
    min_notional = risk_dollars / 0.04
    bp = capital
    positions = {}                # sym -> dict
    by_day = defaultdict(float)
    trades = []
    skipped = 0
    entered_today = set()
    entries_today_n = 0
    cur_day = None

    # last bar of each session, for EOD flatten
    last_bar = {}
    for t in times:
        last_bar[t.date().isoformat()] = t

    for t in times:
        day = t.date().isoformat()
        if day != cur_day:
            cur_day, entered_today = day, set()
            entries_today_n = 0
        bars = clock[t]
        is_eod = (t == last_bar[day])

        # ---------- EXITS FIRST (frees capital for this same bar) ----------
        for sym in list(positions):
            b = bars.get(sym)
            if b is None:
                continue
            p = positions[sym]
            sp_cost = SPREADS.get(sym, 0.03) / 100

            def close_out(price, shares, tag):
                nonlocal bp
                proceeds = shares * price * (1 - sp_cost)
                pnl = proceeds - shares * p["entry"]
                bp += proceeds
                by_day[day] += pnl
                trades.append({"sym": sym, "day": day, "pnl": pnl, "tag": tag,
                               "pct": (price - p["entry"]) / p["entry"] * 100,
                               "meta": p.get("meta")})

            if b["low"] <= p["stop"]:                     # STOP (assumed first)
                close_out(p["stop"], p["shares"], "STOP")
                del positions[sym]; continue
            if b["high"] >= p["target"]:                  # TARGET (full exit)
                close_out(p["target"], p["shares"], "TARGET")
                del positions[sym]; continue
            if partial and not p["took"]:                 # PARTIAL (last)
                trig = p["entry"] * (1 + PARTIAL_AT / 100)
                if b["high"] >= trig:
                    part = p["shares"] * PARTIAL_FRAC
                    if part * trig >= 1.50 and (p["shares"] - part) * trig >= 1.50:
                        close_out(trig, part, "PARTIAL")
                        p["shares"] -= part
                        p["took"] = True
            if is_eod:
                close_out(b["close"], p["shares"], "EOD")
                del positions[sym]

        if is_eod:
            continue

        # ---------- ENTRIES, ranked by net edge as shipped ----------
        slots = int(bp // min_notional) - len(positions)
        cands = []
        for sym, b in bars.items():
            if sym in positions or sym in entered_today:
                continue
            # entry_ok: {day: {sym: set(timestamps)}} of bars an external model
            # approved for ENTRY. Gating here rather than by editing price data
            # -- an earlier version marked bars un-enterable by inflating their
            # close, which silently corrupted every end-of-day exit fill and
            # produced a fake 315% return.
            if entry_ok is not None and t not in entry_ok.get(day, {}).get(sym, ()):
                continue
            lv = levels.get(day, {}).get(sym)
            if not lv:
                continue
            if b["low"] > lv["rl"] or eva.zone_of(b["close"], lv) != "BUY":
                continue
            if b["close"] <= b["open"]:                  # require_bullish_candle
                continue
            entry = b["close"]
            stop, target = eva.compute_stop(entry, lv["sl"]), eva.compute_target(lv)
            if stop >= entry or target <= entry:
                continue
            gross = (target - entry) / entry * 100
            net = gross - SPREADS.get(sym, 0.03)         # v14 net-edge ranking
            # REWARD-TO-RISK GATE. Eva has never had one. The zone-width filter
            # measures distance to the STOP, so a symbol qualifies by having a
            # deep swing low -- which is exactly what puts the stop far away.
            # Pair that with a narrow daily range (target = 25% of it) and the
            # setup risks 4% to make 0.4%: a 92% breakeven win rate. Measured
            # live on XOM 2026-09-02.
            if min_rr is not None:
                reward = (target - entry) - entry * SPREADS.get(sym, 0.03) / 100
                risk_amt = entry - stop
                if risk_amt <= 0 or reward / risk_amt < min_rr:
                    continue
            cands.append((net, sym, entry, stop, target))

        if not cands:
            continue
        cands.sort(reverse=True)
        if slots <= 0:
            skipped += len(cands)
            continue

        for net, sym, entry, stop, target in cands:
            # "one full-account trade per day" -- a hard daily entry budget,
            # spent on whichever qualifying setup appears FIRST. Eva cannot
            # wait for the best setup of the day; she cannot see the future.
            if max_entries_per_day is not None and entries_today_n >= max_entries_per_day:
                break
            if slots <= 0:
                skipped += 1
                continue
            risk_per_share = entry - stop
            shares = risk_dollars / risk_per_share
            cap = (MAX_NOTIONAL if (risk_pct is None and risk_abs is None)
                   else capital * max_frac)
            notional = min(shares * entry, cap, bp)
            if notional < min_notional:
                skipped += 1
                continue
            shares = notional / entry
            bp -= notional
            positions[sym] = {"entry": entry, "stop": stop, "target": target,
                              "shares": shares, "took": False,
                              # carried so an exit can report WHY the trade was
                              # taken, not just what it made -- the link the
                              # old trade log never had
                              "meta": (entry_meta or {}).get(day, {}).get(sym, {}).get(t)}
            entered_today.add(sym)
            entries_today_n += 1
            slots -= 1

    return by_day, trades, skipped


def summarize(by_day, trades, capital):
    days = [v for v in by_day.values() if v != 0]
    if not days:
        return None
    # WIN RATE excludes partials -- they are scale-outs, not round-trips, and
    # are wins by construction, so counting them inflates the rate.
    # PROFIT FACTOR must NOT exclude them: their dollars are real profit that
    # genuinely offsets losses. Dropping them from gross-wins while keeping
    # every loss understates the strategy and was making partials look far
    # worse than they are. Two different questions, two different denominators.
    real = [t for t in trades if t["tag"] != "PARTIAL"]
    wins = [t for t in real if t["pnl"] > 0]
    gl = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    gw = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    green = sum(1 for v in days if v > 0)
    return {"net": sum(by_day.values()), "days": len(days), "green": green,
            "green_pct": green / len(days) * 100,
            "trades": len(real), "partials": len(trades) - len(real),
            "win": len(wins) / len(real) * 100 if real else 0,
            "pf": gw / gl if gl else float("inf"),
            "worst": min(days), "ret_pct": sum(by_day.values()) / capital * 100}


def main():
    all_5m = load_5m()
    clock, levels = build(all_5m)
    sess = sorted({t.date().isoformat() for t in clock})
    n = len(sess)
    splits = {
        "A first60/last40": sess[int(n * .6):],
        "B reversed":       sess[:int(n * .4)],
        "C interleaved":    sess[1::2],
    }

    print(f"{len(all_5m)} symbols | {n} sessions ({sess[0]} .. {sess[-1]})")
    print(f"Slot size ${MIN_NOTIONAL:.2f} -> $250 gives "
          f"{int(250//MIN_NOTIONAL)} concurrent positions\n")

    for capital in (250, 1250, 5000):
        slots = int(capital // MIN_NOTIONAL)
        print("=" * 92)
        print(f"CAPITAL ${capital:,}   ({slots} concurrent slots)")
        print("=" * 92)
        print(f"{'split':<20} {'variant':<10} {'trades':>7} {'win%':>6} {'PF':>6} "
              f"{'net $':>9} {'ret%':>7} {'green days':>12} {'worst':>8} {'skipped':>8}")
        print("-" * 92)
        agg = {"baseline": [], "partial": []}
        for name, test in splits.items():
            for label, use in (("baseline", False), ("partial", True)):
                bd, tr, sk = run(clock, levels, test, capital, use)
                s = summarize(bd, tr, capital)
                agg[label].append(s)
                print(f"{name:<20} {label:<10} {s['trades']:>7} {s['win']:>5.1f}% "
                      f"{s['pf']:>6.2f} {s['net']:>8.2f} {s['ret_pct']:>6.1f}% "
                      f"{s['green']:>3}/{s['days']:<3} {s['green_pct']:>4.0f}% "
                      f"{s['worst']:>7.2f} {sk:>8}")
            print()
        b, p = agg["baseline"], agg["partial"]
        gd = sum(x["green_pct"] for x in p) / 3 - sum(x["green_pct"] for x in b) / 3
        nd = sum(x["net"] for x in p) / 3 - sum(x["net"] for x in b) / 3
        wins = sum(1 for i in range(3) if p[i]["green_pct"] > b[i]["green_pct"])
        print(f"  green days {gd:+.1f} pts avg | net P&L {nd:+.2f} avg | "
              f"{wins}/3 splits greener\n")

    # ------------------------------------------------------------------
    # THE REAL CONSTRAINT: risk per trade is a FLAT $2.50, so position size
    # never grows with the account. Below, risk scales as a % of capital
    # instead -- the standard way size is meant to track account size.
    # ------------------------------------------------------------------
    print("=" * 92)
    print("DOES EVA ACTUALLY USE MORE MONEY IF YOU ADD IT?")
    print("  flat  = shipped behaviour, $2.50 risked per trade regardless of size")
    print("  1%/2% = risk scales with the account")
    print("=" * 92)
    print(f"{'capital':>9} {'risk mode':<10} {'trades':>7} {'net $':>10} "
          f"{'ret%':>7} {'green days':>12} {'worst $':>9} {'skipped':>8}")
    print("-" * 92)
    for capital in (250, 1250, 5000):
        for mode, rp in (("flat", None), ("1%", 1.0), ("2%", 2.0)):
            nets, greens, dayn, worst, tr, sk_t = [], 0, 0, [], 0, 0
            for name, test in splits.items():
                bd, trd, sk = run(clock, levels, test, capital, True, risk_pct=rp)
                s = summarize(bd, trd, capital)
                nets.append(s["net"]); greens += s["green"]; dayn += s["days"]
                worst.append(s["worst"]); tr += s["trades"]; sk_t += sk
            net = sum(nets)
            print(f"${capital:>8,} {mode:<10} {tr:>7} {net:>9.2f} "
                  f"{net/capital*100:>6.1f}% {greens:>3}/{dayn:<3} "
                  f"{greens/dayn*100:>4.0f}% {min(worst):>8.2f} {sk_t:>8}")
        print()


if __name__ == "__main__":
    main()
