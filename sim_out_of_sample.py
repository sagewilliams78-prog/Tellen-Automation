exec(open('disagree.py').read().split("bars = load_bars()")[0])
import statistics as st
from math import sqrt, erf

def ncdf(x): return 0.5*(1+erf(x/sqrt(2)))
def moments(x):
    n=len(x); m=st.mean(x); s=st.stdev(x)
    return m,s,sum(((v-m)/s)**3 for v in x)/n, sum(((v-m)/s)**4 for v in x)/n

def resolve2(o, max_bars=None):
    fwd = o["bars"][o["i"]+1:]
    for j,c in enumerate(fwd):
        if c["low"] <= o["stop"]:  return (o["stop"]-o["price"])/o["price"]*100,"stop",j+1
        if c["high"] >= o["target"]: return (o["target"]-o["price"])/o["price"]*100,"target",j+1
        if max_bars is not None and (j+1) >= max_bars:
            return (c["close"]-o["price"])/o["price"]*100,"timestop",j+1
    last=o["bars"][-1]
    return (last["close"]-o["price"])/o["price"]*100,"eod",len(fwd)

def policy(obs, days=None, cutoff_hour=None, max_bars=None, key="cascade"):
    trades, busy = [], 0
    for o in obs:
        if days is not None and o["day"] not in days: continue
        if not o[key] or o["t"] < busy: continue
        dt = o["bars"][o["i"]]["dt"]
        if cutoff_hour is not None and (dt.hour + dt.minute/60.0) >= cutoff_hour: continue
        pct, reason, held = resolve2(o, max_bars)
        net = pct - spread_for(o["sym"])
        rp = (o["price"]-o["stop"])/o["price"]*100
        notional = min((RISK_PER_TRADE/rp*100) if rp>0 else 0, 60.0)
        trades.append({"pnl": notional*net/100})
        busy = o["bars"][min(o["i"]+held, len(o["bars"])-1)]["t"]
    return trades

bars = load_bars()
sess = sorted({b["date"] for s in bars for b in bars[s]})
print(f"sessions loaded: {len(sess)}   {sess[0]} -> {sess[-1]}")
IS  = {d for d in sess if d >= "2026-08-04"}
OOS = {d for d in sess if d <  "2026-08-04"}
print(f"  IN-SAMPLE  (tuned on): {len(IS)} sessions")
print(f"  OUT-OF-SAMPLE  (new) : {len(OOS)} sessions\n")

OBS = observations(bars)

def report(label, days, **kw):
    tr = policy(OBS, days=days, **kw)
    if len(tr) < 3:
        print(f"  {label:<32} {len(tr):>4} trades  (too few)"); return None
    p=[t['pnl'] for t in tr]; m,s,sk,ku=moments(p); T=len(p); SR=m/s
    var=(1-sk*SR+(ku-1)*SR*SR/4); se=sqrt(var/T)
    print(f"  {label:<32} {T:>4} tr  net ${sum(p):>7.2f}  SR {SR:+.4f}  PSR {ncdf(SR/se)*100:>5.1f}%")
    return SR

print("="*78); print("OUT-OF-SAMPLE (Jun 1 - Aug 3) — never examined before this run"); print("="*78)
o1=report("1. shipped cascade", OOS)
o2=report("2. + 18-bar time-stop", OOS, max_bars=18)
o3=report("3. + 15:00 entry cutoff", OOS, cutoff_hour=15)
print("\nIN-SAMPLE (Aug 4 - Sep 2) — what I tuned on")
i1=report("1. shipped cascade", IS)
i2=report("2. + 18-bar time-stop", IS, max_bars=18)
i3=report("3. + 15:00 entry cutoff", IS, cutoff_hour=15)
print("\nFULL PERIOD")
f1=report("1. shipped cascade", None)
f2=report("2. + 18-bar time-stop", None, max_bars=18)
f3=report("3. + 15:00 entry cutoff", None, cutoff_hour=15)

print("\n"+"="*78); print("VERDICT vs WHAT I PREDICTED BEFORE FETCHING"); print("="*78)
for name,pred,i,o in (("1. shipped cascade","positive but small",i1,o1),
                      ("2. 18-bar time-stop","will NOT replicate (high conf)",i2,o2),
                      ("3. 15:00 cutoff","small positive survives",i3,o3)):
    if i is None or o is None: print(f"  {name}: insufficient"); continue
    print(f"  {name}: predicted {pred}")
    print(f"     IS SR {i:+.4f}  ->  OOS SR {o:+.4f}   "
          f"{'held up' if o>0 else 'FAILED out-of-sample'}")
