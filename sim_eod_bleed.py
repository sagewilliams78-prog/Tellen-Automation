#!/usr/bin/env python3
"""Where does the EOD bleed come from, and can anything fix it?

22 of 27 cascade trades exit at the EOD flatten averaging -$0.097. That leak
is bigger than any entry-filter question. This asks three things:

  1. Is the bleed concentrated in late-day entries (a trade opened at 15:40
     cannot reach target -- it can only flatten)?
  2. Does an entry-time cutoff help, and does it survive three splits?
  3. Does a time-stop (give up after N bars) help, and does it survive?

Every candidate is judged by sim_lookback.py's rule: it must beat the shipped
behaviour on ALL THREE splits, not just on the full window. The TARGET_FRAC
sweep already showed how badly a full-window number can mislead here.
"""
exec(open('disagree.py').read().split("bars = load_bars()")[0])
import statistics
from collections import defaultdict, Counter

bars = load_bars()
sess = sorted({b["date"] for s in bars for b in bars[s]})
n = len(sess)
SPL = {"A": set(sess[int(n*.6):]), "B": set(sess[:int(n*.4)]), "C": set(sess[1::2])}
OBS = observations(bars)


def resolve2(o, max_bars=None):
    """Walk forward to stop / target / time-stop / EOD."""
    fwd = o["bars"][o["i"] + 1:]
    for j, c in enumerate(fwd):
        if c["low"] <= o["stop"]:
            return (o["stop"] - o["price"]) / o["price"] * 100, "stop", j + 1
        if c["high"] >= o["target"]:
            return (o["target"] - o["price"]) / o["price"] * 100, "target", j + 1
        if max_bars is not None and (j + 1) >= max_bars:
            return (c["close"] - o["price"]) / o["price"] * 100, "timestop", j + 1
    last = o["bars"][-1]
    return (last["close"] - o["price"]) / o["price"] * 100, "eod", len(fwd)


def policy(obs, days=None, cutoff_hour=None, max_bars=None, key="cascade"):
    """cutoff_hour: no NEW entries at/after this ET hour."""
    trades, busy_until = [], 0
    for o in obs:
        if days is not None and o["day"] not in days:
            continue
        if not o[key] or o["t"] < busy_until:
            continue
        dt = o["bars"][o["i"]]["dt"]
        if cutoff_hour is not None and (dt.hour + dt.minute / 60.0) >= cutoff_hour:
            continue
        pct, reason, held = resolve2(o, max_bars)
        net = pct - spread_for(o["sym"])
        risk_pct = (o["price"] - o["stop"]) / o["price"] * 100
        notional = min((RISK_PER_TRADE / risk_pct * 100) if risk_pct > 0 else 0, 60.0)
        trades.append({"sym": o["sym"], "day": o["day"], "hour": dt.hour,
                       "reason": reason, "held": held,
                       "pnl": notional * net / 100, "net_pct": net})
        # slot frees when the trade actually exits, not automatically at EOD
        exit_i = min(o["i"] + held, len(o["bars"]) - 1)
        busy_until = o["bars"][exit_i]["t"]
    return trades


def net(tr):
    return sum(t["pnl"] for t in tr)


print("=" * 78)
print("1. IS THE BLEED CONCENTRATED BY ENTRY TIME?")
print("=" * 78)
base = policy(OBS)
by_hour = defaultdict(list)
for t in base:
    by_hour[t["hour"]].append(t)
print(f"  {'ET hour':>8} {'trades':>7} {'net $':>9} {'avg $':>9}   exit mix")
for h in sorted(by_hour):
    g = by_hour[h]
    mix = dict(Counter(t["reason"] for t in g))
    print(f"  {h:>6}:00 {len(g):>7} {net(g):>9.2f} {statistics.mean([t['pnl'] for t in g]):>9.3f}   {mix}")

held_eod = [t["held"] for t in base if t["reason"] == "eod"]
held_tgt = [t["held"] for t in base if t["reason"] == "target"]
print(f"\n  bars held  -- eod exits: median {statistics.median(held_eod):.0f}"
      f"  | target exits: median {statistics.median(held_tgt):.0f}" if held_tgt else "")

print("\n" + "=" * 78)
print("2. ENTRY-TIME CUTOFF  (must beat shipped on ALL THREE splits)")
print("=" * 78)
b = {k: net(policy(OBS, days=SPL[k])) for k in "ABC"}
bf = net(base)
print(f"  {'cutoff':>8} {'A':>8} {'B':>8} {'C':>8} {'full':>8} {'n':>4}  verdict")
print(f"  {'none':>8} {b['A']:>8.2f} {b['B']:>8.2f} {b['C']:>8.2f} {bf:>8.2f} "
      f"{len(base):>4}  SHIPPED")
for cut in (11, 12, 13, 14, 15, 15.5):
    v = {k: net(policy(OBS, days=SPL[k], cutoff_hour=cut)) for k in "ABC"}
    f = policy(OBS, cutoff_hour=cut)
    beat = sum(1 for k in "ABC" if v[k] > b[k])
    print(f"  {cut:>8} {v['A']:>8.2f} {v['B']:>8.2f} {v['C']:>8.2f} {net(f):>8.2f} "
          f"{len(f):>4}  {'WINS 3/3' if beat==3 else f'{beat}/3'}")

print("\n" + "=" * 78)
print("3. TIME-STOP  (give up after N 5-minute bars)")
print("=" * 78)
print(f"  {'bars':>8} {'A':>8} {'B':>8} {'C':>8} {'full':>8} {'n':>4}  verdict")
print(f"  {'none':>8} {b['A']:>8.2f} {b['B']:>8.2f} {b['C']:>8.2f} {bf:>8.2f} "
      f"{len(base):>4}  SHIPPED")
for mb in (6, 12, 18, 24, 36, 48):
    v = {k: net(policy(OBS, days=SPL[k], max_bars=mb)) for k in "ABC"}
    f = policy(OBS, max_bars=mb)
    beat = sum(1 for k in "ABC" if v[k] > b[k])
    print(f"  {mb:>8} {v['A']:>8.2f} {v['B']:>8.2f} {v['C']:>8.2f} {net(f):>8.2f} "
          f"{len(f):>4}  {'WINS 3/3' if beat==3 else f'{beat}/3'}")

print("\n" + "=" * 78)
print("4. BEST COMBINATION FOUND, IF ANY")
print("=" * 78)
winners = []
for cut in (None, 12, 13, 14, 15):
    for mb in (None, 12, 24, 36):
        v = {k: net(policy(OBS, days=SPL[k], cutoff_hour=cut, max_bars=mb)) for k in "ABC"}
        if all(v[k] > b[k] for k in "ABC"):
            f = policy(OBS, cutoff_hour=cut, max_bars=mb)
            winners.append((net(f), cut, mb, len(f), v))
if not winners:
    print("  NOTHING beats shipped on all three splits. Current behaviour stands.")
else:
    for tot, cut, mb, cnt, v in sorted(winners, reverse=True)[:5]:
        print(f"  cutoff={str(cut):>4} timestop={str(mb):>4}  full ${tot:>6.2f}  "
              f"n={cnt:>3}  splits {v['A']:+.2f}/{v['B']:+.2f}/{v['C']:+.2f}")
    print(f"\n  shipped for comparison: full ${bf:.2f}  n={len(base)}  "
          f"splits {b['A']:+.2f}/{b['B']:+.2f}/{b['C']:+.2f}")
