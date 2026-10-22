exec(open('strats2.py').read().split('print("="*74); print("CORRECTED')[0])
from collections import Counter

def bysymbol(signals):
    signals.sort(key=lambda x:x["t"]); busy=0; d={}
    for g in signals:
        if g["t"]<busy: continue
        px,stop,tgt=g["price"],g["stop"],g["target"]
        if stop>=px: continue
        ex,ei=None,len(g["dbars"])-1
        for j,c in enumerate(g["dbars"][g["i"]+1:],start=g["i"]+1):
            if c["low"]<=stop: ex,ei=stop,j; break
            if tgt and c["high"]>=tgt: ex,ei=tgt,j; break
        if ex is None: ex=g["dbars"][-1]["close"]
        net=(ex-px)/px*100-spread_for(g["sym"])
        rp=(px-stop)/px*100
        d.setdefault(g["sym"],[]).append(min((RISK/rp*100) if rp>0 else 0,MAXN)*net/100)
        busy=g["dbars"][ei]["t"]
    return d

OBS=observations(bars)
casc=[{"t":o["t"],"sym":o["sym"],"price":o["price"],"stop":o["stop"],
       "target":o["target"],"dbars":o["bars"],"i":o["i"]} for o in OBS if o["cascade"]]

print("="*74); print("CONCENTRATION CHECK — does one symbol carry the result?"); print("="*74)
for name, sigs in (("YOUR BOT (cascade)", casc),
                   ("short-term reversal", reversal())):
    d=bysymbol(sigs); tot=sum(sum(v) for v in d.values())
    allp=[x for v in d.values() for x in v]
    top=max(d,key=lambda s:sum(d[s]))
    rest=[x for s,v in d.items() if s!=top for x in v]
    print(f"\n{name}: total ${tot:+.2f} over {len(allp)} trades")
    for s,v in sorted(d.items(), key=lambda kv:-sum(kv[1]))[:4]:
        print(f"    {s:<6} {len(v):>3} tr  ${sum(v):+7.2f}")
    print(f"  top contributor {top} = ${sum(d[top]):+.2f} "
          f"({sum(d[top])/tot*100 if tot else 0:.0f}% of total)")
    if len(rest)>3:
        stats(rest, f"  excluding {top}")
