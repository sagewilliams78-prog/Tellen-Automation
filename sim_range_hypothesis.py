#!/usr/bin/env python3
"""Does the Range & Swing setup actually work better on wide-range symbols?

WHY THIS TEST EXISTS
--------------------
The concentration check showed the bot's entire +$4.67 came from COIN (105% of
total; ex-COIN it is -$0.25 over 121 trades). Two readings fit that:

  (a) COIN is noise -- 11 trades in a 66-session window, nothing more.
  (b) COIN has a property the strategy needs -- a wide daily range relative to
      price -- and the other 19 names mostly do not.

(b) would be actionable: screen for range characteristics instead of trading a
fixed list. (a) means the thread is dead.

THIS IS A POST-HOC HYPOTHESIS. It was formed AFTER seeing COIN win, which is
the weakest kind of evidence there is. It therefore has to clear more than a
full-window correlation:

  1. a monotonic relationship across range tiers, not just a good top tier
  2. survival when COIN itself is removed -- otherwise it is the same finding
     wearing a different hat
  3. the same sign out-of-sample

Failing any of the three means the answer is (a).
"""
import sys
sys.argv = ["x"]
exec(open('disagree.py').read().split("bars = load_bars()")[0])
import statistics as st
from math import sqrt, erf

def ncdf(x): return 0.5*(1+erf(x/sqrt(2)))

def moments(x):
    n=len(x); m=st.mean(x); s=st.stdev(x)
    return m, s, sum(((v-m)/s)**3 for v in x)/n, sum(((v-m)/s)**4 for v in x)/n

def stats(p, label):
    if len(p) < 3:
        print(f"  {label:<34}{len(p):>4} tr  (too few)"); return None
    m,s,sk,ku = moments(p); T=len(p); SR=m/s
    var=(1-sk*SR+(ku-1)*SR*SR/4); se=sqrt(var/T)
    print(f"  {label:<34}{T:>4} tr  net ${sum(p):>7.2f}  SR {SR:+.4f}  "
          f"PSR {ncdf(SR/se)*100:>5.1f}%")
    return SR

bars = load_bars()
sess = sorted({b["date"] for s in bars for b in bars[s]})
daily = {s: daily_from_5m(bb) for s, bb in bars.items()}

# Range character: mean daily (high-low)/close, in percent.
rng = {s: st.mean([(d["high"]-d["low"])/d["close"]*100 for d in dd if d["close"]>0])
       for s, dd in daily.items()}

OBS = observations(bars)

def run(obs, days=None, exclude=None, only=None):
    obs = sorted([o for o in obs if o["cascade"]], key=lambda x: x["t"])
    out, busy = [], 0
    for o in obs:
        if days is not None and o["day"] not in days: continue
        if exclude and o["sym"] in exclude: continue
        if only and o["sym"] not in only: continue
        if o["t"] < busy: continue
        ex, ei = None, len(o["bars"])-1
        for j, c in enumerate(o["bars"][o["i"]+1:], start=o["i"]+1):
            if c["low"] <= o["stop"]:   ex, ei = o["stop"], j; break
            if c["high"] >= o["target"]: ex, ei = o["target"], j; break
        if ex is None: ex = o["bars"][-1]["close"]
        net = (ex-o["price"])/o["price"]*100 - spread_for(o["sym"])
        rp = (o["price"]-o["stop"])/o["price"]*100
        out.append({"sym": o["sym"],
                    "pnl": min((RISK_PER_TRADE/rp*100) if rp>0 else 0, 60.0)*net/100,
                    "net_pct": net})
        busy = o["bars"][ei]["t"]
    return out

allt = run(OBS)
print(f"{len(sess)} sessions, {len(bars)} symbols, {len(allt)} trades\n")

print("="*78)
print("PER-SYMBOL: daily range vs strategy P&L")
print("="*78)
per = {}
for t in allt:
    per.setdefault(t["sym"], []).append(t)
print(f"  {'sym':<7}{'range%':>8}{'trades':>8}{'net $':>9}{'$/trade':>10}")
rows = []
for s in sorted(rng, key=lambda x: -rng[x]):
    g = per.get(s, [])
    if not g:
        print(f"  {s:<7}{rng[s]:>8.2f}{0:>8}{'--':>9}{'--':>10}"); continue
    tot = sum(x["pnl"] for x in g)
    rows.append((rng[s], tot/len(g), len(g), s, tot))
    print(f"  {s:<7}{rng[s]:>8.2f}{len(g):>8}{tot:>9.2f}{tot/len(g):>10.3f}")

# correlation between range and per-trade P&L
if len(rows) > 3:
    xs = [r[0] for r in rows]; ys = [r[1] for r in rows]
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a-mx)*(b-my) for a, b in zip(xs, ys))
    den = sqrt(sum((a-mx)**2 for a in xs) * sum((b-my)**2 for b in ys))
    r = num/den if den else 0
    print(f"\n  correlation(range%, $/trade) = {r:+.3f}   over {len(rows)} symbols")
    xs2 = [q[0] for q in rows if q[3] != "COIN"]; ys2 = [q[1] for q in rows if q[3] != "COIN"]
    if len(xs2) > 3:
        mx2, my2 = st.mean(xs2), st.mean(ys2)
        num2 = sum((a-mx2)*(b-my2) for a, b in zip(xs2, ys2))
        den2 = sqrt(sum((a-mx2)**2 for a in xs2)*sum((b-my2)**2 for b in ys2))
        print(f"  correlation EXCLUDING COIN   = {num2/den2 if den2 else 0:+.3f}")

print("\n" + "="*78)
print("TEST 1 — MONOTONIC ACROSS RANGE TIERS?")
print("="*78)
order = sorted(rng, key=lambda x: -rng[x])
tiers = {"wide (top 7)": order[:7], "mid (next 6)": order[7:13],
         "narrow (bottom 7)": order[13:]}
for name, syms in tiers.items():
    p = [t["pnl"] for t in allt if t["sym"] in syms]
    avg = st.mean([rng[s] for s in syms])
    stats(p, f"{name}  avg range {avg:.2f}%")

print("\n" + "="*78)
print("TEST 2 — DOES THE WIDE TIER SURVIVE WITHOUT COIN?")
print("="*78)
wide = [s for s in order[:7]]
print(f"  wide tier = {wide}")
stats([t["pnl"] for t in allt if t["sym"] in wide], "wide tier, all")
stats([t["pnl"] for t in allt if t["sym"] in wide and t["sym"] != "COIN"],
      "wide tier, ex-COIN")

print("\n" + "="*78)
print("TEST 3 — OUT-OF-SAMPLE (Jun 1 - Aug 3) vs IN-SAMPLE (Aug 4 - Sep 2)")
print("="*78)
IS  = {d for d in sess if d >= "2026-08-04"}
OOS = {d for d in sess if d <  "2026-08-04"}
for lbl, days in (("in-sample", IS), ("out-of-sample", OOS)):
    w = run(OBS, days=days, only=set(wide))
    nw = run(OBS, days=days, exclude=set(wide))
    stats([t["pnl"] for t in w],  f"{lbl}: wide tier")
    stats([t["pnl"] for t in nw], f"{lbl}: rest")
    wx = run(OBS, days=days, only=set(w2 for w2 in wide if w2 != "COIN"))
    stats([t["pnl"] for t in wx], f"{lbl}: wide ex-COIN")
    print()
