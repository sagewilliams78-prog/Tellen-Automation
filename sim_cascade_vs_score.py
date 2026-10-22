#!/usr/bin/env python3
"""Cascade vs eva_score on real 5m bars: how often do they disagree, and who wins?

Loads the Robinhood historicals already pulled to disk, rebuilds v13's levels
and decision logic exactly, and replays BOTH entry policies over the same bars
under the same one-position-at-a-time constraint.
"""
import json, glob, statistics
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import sys
sys.path.insert(0, "/mnt/user-data/uploads/Sages trading bot")
import eva_score

# ---- v13 constants (read from sage_bot_v13.py) ----
STOP_LOSS_BACKSTOP_PCT = -4.0
MIN_STOP_DISTANCE_PCT  = -2.5
TARGET_FRAC            = 0.25
SWING_LOOKBACK_DAYS    = 5
MIN_ZONE_WIDTH_PCT     = 3.0
SCORE_THRESHOLD        = 21
RISK_PER_TRADE         = 2.50

# Spread is 1 of 6 score factors and the cascade ignores it entirely.
# Tiered estimate anchored to eva_score.py's own cited values
# (NVDA 0.005%, IBRX 0.127%). Sensitivity is tested at the end.
WIDE = {"IBRX", "IOVA", "SMCI"}
def spread_for(sym, mult=1.0):
    return (0.120 if sym in WIDE else 0.020) * mult

ET = timezone(timedelta(hours=-4))   # EDT over the sample window

def load_bars():
    out = {}
    for f in glob.glob("/root/.claude/projects/-home-claude/*/tool-results/"
                       "mcp-robin_hood-get_equity_historicals-*.txt"):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for r in d.get("data", {}).get("results", []):
            bars = []
            for b in r["bars"]:
                if b.get("session") != "reg" or b.get("interpolated"):
                    continue
                t = datetime.fromisoformat(b["begins_at"].replace("Z", "+00:00"))
                bars.append({"t": t.timestamp(), "dt": t.astimezone(ET),
                             "date": t.astimezone(ET).date().isoformat(),
                             "open": float(b["open_price"]), "close": float(b["close_price"]),
                             "high": float(b["high_price"]), "low": float(b["low_price"]),
                             "volume": float(b["volume"])})
            if bars:
                bars.sort(key=lambda x: x["t"])
                out.setdefault(r["symbol"], []).extend(bars)
    for s in out:
        seen, ded = set(), []
        for b in sorted(out[s], key=lambda x: x["t"]):
            if b["t"] not in seen:
                seen.add(b["t"]); ded.append(b)
        out[s] = ded
    return out

def daily_from_5m(bars):
    by = defaultdict(list)
    for b in bars:
        by[b["date"]].append(b)
    return [{"date": d, "open": g[0]["open"], "close": g[-1]["close"],
             "high": max(x["high"] for x in g), "low": min(x["low"] for x in g)}
            for d, g in sorted(by.items())]

def levels(daily, i):
    past = daily[:i]
    if len(past) < SWING_LOOKBACK_DAYS:
        return None
    y = past[-1]; look = past[-SWING_LOOKBACK_DAYS:]
    rh, rl = y["high"], y["low"]
    return {"rh": rh, "rl": rl,
            "sh": max(max(b["high"] for b in look), rh),
            "sl": min(min(b["low"] for b in look), rl)}

def zone_of(p, lv):
    return "SELL" if p >= lv["rh"] else "BUY" if p <= lv["rl"] else "KILL"

def compute_stop(entry, sl):
    stop = max(sl, entry * (1 + STOP_LOSS_BACKSTOP_PCT / 100))
    return min(stop, entry * (1 + MIN_STOP_DISTANCE_PCT / 100))

def compute_target(lv):
    return lv["rl"] + TARGET_FRAC * (lv["rh"] - lv["rl"])

def zone_width_ok(lv):
    return lv["rl"] > 0 and (lv["rl"] - lv["sl"]) / lv["rl"] * 100 >= MIN_ZONE_WIDTH_PCT

def observations(bars_by_sym, spread_mult=1.0):
    """Every buy-zone bar, with BOTH policies' verdicts."""
    obs = []
    for sym, bars in bars_by_sym.items():
        daily = daily_from_5m(bars)
        di = {d["date"]: i for i, d in enumerate(daily)}
        by_day = defaultdict(list)
        for b in bars:
            by_day[b["date"]].append(b)

        for day, dbars in sorted(by_day.items()):
            lv = levels(daily, di[day])
            if not lv or lv["rl"] <= 0:
                continue
            width_ok = zone_width_ok(lv)
            tgt = compute_target(lv)
            for k, c in enumerate(dbars):
                p = c["close"]
                if zone_of(p, lv) != "BUY":
                    continue
                prev = dbars[max(0, k - 12):k]
                avgv = statistics.mean([x["volume"] for x in prev]) if prev else c["volume"]
                stop = compute_stop(p, lv["sl"])
                sp = spread_for(sym, spread_mult)
                tot, _ = eva_score.score_setup(p, stop, tgt, lv["rl"], lv["sl"],
                                               c["open"], c["high"], c["low"],
                                               c["volume"], avgv or 1.0, sp)
                cascade = (c["low"] <= lv["rl"]) and (c["close"] > c["open"]) and width_ok
                score_e = (tot is not None) and (tot >= SCORE_THRESHOLD)
                obs.append({"sym": sym, "day": day, "t": c["t"], "i": k,
                            "price": p, "stop": stop, "target": tgt,
                            "score": tot, "cascade": cascade, "score_enter": score_e,
                            "bars": dbars})
    obs.sort(key=lambda o: o["t"])
    return obs

def resolve(o):
    """Walk forward to stop / target / EOD flatten. Returns (pct, reason)."""
    for c in o["bars"][o["i"] + 1:]:
        if c["low"] <= o["stop"]:
            return (o["stop"] - o["price"]) / o["price"] * 100, "stop"
        if c["high"] >= o["target"]:
            return (o["target"] - o["price"]) / o["price"] * 100, "target"
    last = o["bars"][-1]
    return (last["close"] - o["price"]) / o["price"] * 100, "eod"

def run_policy(obs, key):
    """One position at a time, first qualifying signal wins."""
    trades, busy_until = [], 0
    for o in obs:
        if not o[key] or o["t"] < busy_until:
            continue
        pct, reason = resolve(o)
        sp = spread_for(o["sym"])
        net = pct - sp
        risk_pct = (o["price"] - o["stop"]) / o["price"] * 100
        notional = (RISK_PER_TRADE / risk_pct * 100) if risk_pct > 0 else 0
        notional = min(notional, 60.0)
        trades.append({"sym": o["sym"], "day": o["day"], "score": o["score"],
                       "net_pct": net, "reason": reason, "pnl": notional * net / 100})
        busy_until = o["bars"][-1]["t"]      # flat by EOD at the latest
    return trades

def summ(tr):
    if not tr:
        return None
    w = [t for t in tr if t["pnl"] > 0]
    gl = abs(sum(t["pnl"] for t in tr if t["pnl"] <= 0))
    return {"n": len(tr), "net": sum(t["pnl"] for t in tr),
            "win": len(w) / len(tr) * 100,
            "pf": (sum(t["pnl"] for t in w) / gl) if gl > 0 else float("inf")}

bars = load_bars()
print(f"symbols {len(bars)} | sessions "
      f"{len({b['date'] for s in bars for b in bars[s]})} | "
      f"bars {sum(len(v) for v in bars.values()):,}\n")

obs = observations(bars)
dis = [o for o in obs if o["cascade"] != o["score_enter"]]
print(f"buy-zone observations : {len(obs):,}")
print(f"cascade would enter   : {sum(o['cascade'] for o in obs):,}")
print(f"score would enter     : {sum(o['score_enter'] for o in obs):,}")
print(f"DISAGREEMENTS         : {len(dis):,}  ({len(dis)/len(obs)*100:.2f}% of observations)")
so = [o for o in dis if o["score_enter"]]
co = [o for o in dis if o["cascade"]]
print(f"   score-only entries : {len(so):,}")
print(f"   cascade-only       : {len(co):,}\n")

if dis:
    print("WHO WAS RIGHT ON THE DISAGREEMENTS (net of spread)")
    for label, group in (("score took, cascade skipped", so),
                         ("cascade took, score skipped", co)):
        if not group:
            print(f"  {label}: none"); continue
        res = [resolve(o)[0] - spread_for(o["sym"]) for o in group]
        wins = sum(1 for r in res if r > 0)
        print(f"  {label}: {len(group)} trades, "
              f"mean {statistics.mean(res):+.3f}%, win {wins/len(res)*100:.0f}%, "
              f"total {sum(res):+.2f}%")
    print()

print("FULL POLICY REPLAY (one position at a time, risk-sized, spread charged)")
for name, key in (("cascade (live today)", "cascade"), ("eva_score >=21", "score_enter")):
    s = summ(run_policy(obs, key))
    print(f"  {name:<22} " + (f"{s['n']:>3} trades  net ${s['net']:>7.2f}  "
          f"win {s['win']:>3.0f}%  PF {s['pf']:.2f}" if s else "no trades"))

print("\nSPREAD SENSITIVITY (does the conclusion depend on the spread guess?)")
for m, lbl in ((0.5, "half"), (1.0, "base"), (2.0, "double")):
    o2 = observations(bars, spread_mult=m)
    d2 = [o for o in o2 if o["cascade"] != o["score_enter"]]
    a = summ(run_policy(o2, "cascade")); b = summ(run_policy(o2, "score_enter"))
    print(f"  {lbl:<7} disagreements {len(d2):>4}  cascade "
          f"${a['net'] if a else 0:>7.2f}  score ${b['net'] if b else 0:>7.2f}")

print("\n" + "="*70)
print("WHERE THE MONEY GOES (cascade policy, base spread)")
tr = run_policy(obs, "cascade")
from collections import Counter
rc = Counter(t["reason"] for t in tr)
print("  exit mix:", dict(rc))
for r in ("target","stop","eod"):
    g=[t["pnl"] for t in tr if t["reason"]==r]
    if g: print(f"   {r:<7} {len(g):>3} trades  total ${sum(g):+7.2f}  avg ${statistics.mean(g):+.3f}")

print("\nTARGET_FRAC SWEEP (their v12 docstring swept this; on real Aug4-Sep2 bars)")
import copy
_orig = TARGET_FRAC
print(f"  {'frac':>5} {'casc n':>7} {'casc $':>9} {'score n':>8} {'score $':>9}")
for frac in (0.10,0.15,0.20,0.25,0.35,0.50,0.75,1.00):
    globals()['TARGET_FRAC'] = frac
    o = observations(bars)
    a = summ(run_policy(o,"cascade")); b = summ(run_policy(o,"score_enter"))
    print(f"  {frac:>5.2f} {a['n'] if a else 0:>7} {a['net'] if a else 0:>9.2f} "
          f"{b['n'] if b else 0:>8} {b['net'] if b else 0:>9.2f}")
globals()['TARGET_FRAC'] = _orig
