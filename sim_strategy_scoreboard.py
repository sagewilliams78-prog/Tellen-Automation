exec(open('strats.py').read().split('print(f"{len(sess)} sessions')[0])
from collections import Counter

def simulate2(signals, tag=""):
    """Same as simulate() but frees the slot at the ACTUAL exit bar."""
    signals.sort(key=lambda x: x["t"])
    out, busy, syms = [], 0, []
    for g in signals:
        if g["t"] < busy: continue
        px, stop, tgt = g["price"], g["stop"], g["target"]
        if stop >= px: continue
        exit_px, exit_i = None, len(g["dbars"])-1
        for j, c in enumerate(g["dbars"][g["i"]+1:], start=g["i"]+1):
            if c["low"] <= stop:   exit_px, exit_i = stop, j; break
            if tgt and c["high"] >= tgt: exit_px, exit_i = tgt, j; break
        if exit_px is None: exit_px = g["dbars"][-1]["close"]
        net = (exit_px-px)/px*100 - spread_for(g["sym"])
        rp = (px-stop)/px*100
        out.append(min((RISK/rp*100) if rp>0 else 0, MAXN)*net/100)
        syms.append(g["sym"])
        busy = g["dbars"][exit_i]["t"]
    if tag: print(f"    {tag} symbol mix: {Counter(syms).most_common(5)}")
    return out

OBS = observations(bars)
casc = [{"t":o["t"],"sym":o["sym"],"price":o["price"],"stop":o["stop"],
         "target":o["target"],"dbars":o["bars"],"i":o["i"]}
        for o in OBS if o["cascade"]]

print("="*74); print("CORRECTED — slot frees at actual exit for every strategy"); print("="*74)
stats(simulate2(casc),            "YOUR BOT (cascade, shipped)")
stats(simulate2(orb()),           "1. opening range breakout")
stats(simulate2(reversal()),      "2. short-term reversal (5d)")
ts = tsmom()
stats(simulate2(ts, "tsmom"),     "3. time-series momentum (20d)")
stats(vol_target(OBS),            "4. vol-targeted sizing")

print("\n" + "="*74)
print("STRESS-TESTING MOMENTUM (it beat my prediction — so distrust it)")
print("="*74)
IS  = {d for d in sess if d >= "2026-08-04"}
OOS = {d for d in sess if d <  "2026-08-04"}
for lbl, days in (("in-sample  Aug4-Sep2", IS), ("out-of-sample Jun1-Aug3", OOS)):
    sub=[g for g in ts if g["dbars"][0]["date"] in days]
    stats(simulate2(sub), f"  tsmom {lbl}")

# concentration: drop the single best symbol and see what survives
allp = simulate2(ts)
bysym={}
busy=0
for g in sorted(ts,key=lambda x:x["t"]):
    if g["t"]<busy: continue
    px,stop=g["price"],g["stop"]
    if stop>=px: continue
    ex,ei=None,len(g["dbars"])-1
    for j,c in enumerate(g["dbars"][g["i"]+1:],start=g["i"]+1):
        if c["low"]<=stop: ex,ei=stop,j; break
    if ex is None: ex=g["dbars"][-1]["close"]
    net=(ex-px)/px*100-spread_for(g["sym"])
    rp=(px-stop)/px*100
    bysym.setdefault(g["sym"],[]).append(min((RISK/rp*100) if rp>0 else 0,MAXN)*net/100)
    busy=g["dbars"][ei]["t"]
tot=sum(sum(v) for v in bysym.values())
print(f"\n  tsmom P&L by symbol (total ${tot:+.2f}):")
for s,v in sorted(bysym.items(), key=lambda kv:-sum(kv[1]))[:6]:
    print(f"    {s:<6} {len(v):>3} trades  ${sum(v):+7.2f}")
top=max(bysym,key=lambda s:sum(bysym[s]))
rest=[x for s,v in bysym.items() if s!=top for x in v]
print(f"\n  drop {top}: ${tot-sum(bysym[top]):+.2f} over {len(rest)} trades")
if rest: stats(rest, f"  tsmom excluding {top}")
