exec(open('eod.py').read().split('print("=" * 78)')[0])
import statistics, random
base = policy(OBS)
p = [t["pnl"] for t in base]
sd = statistics.stdev(p); mean = statistics.mean(p); n=len(p)
se = sd/ (n**0.5)
print(f"baseline: n={n}  total ${sum(p):.2f}  mean ${mean:+.4f}  sd ${sd:.4f}")
print(f"standard error of the TOTAL over {n} trades: ${se*n:.2f}")
print(f"so the total is ${sum(p):.2f} +/- ${se*n:.2f} (1 s.e.)")
print(f"t-stat vs zero: {mean/se:.2f}   (need ~2.0 to call it non-random)\n")

# bootstrap: how often does a random reshuffle beat the 'winners'?
random.seed(7)
ts18 = policy(OBS, max_bars=18); v18=sum(t['pnl'] for t in ts18)
cut15 = policy(OBS, cutoff_hour=15); v15=sum(t['pnl'] for t in cut15)
print(f"time-stop 18 : ${v18:.2f} over {len(ts18)} trades")
print(f"cutoff 15:00 : ${v15:.2f} over {len(cut15)} trades")
pp=[t['pnl'] for t in ts18]
print(f"  ts18 mean ${statistics.mean(pp):+.4f} sd ${statistics.stdev(pp):.4f} "
      f"t={statistics.mean(pp)/(statistics.stdev(pp)/len(pp)**0.5):.2f}")

print("\nHOW MANY TRADES TO RESOLVE A REAL EDGE OF THIS SIZE?")
for eff in (mean, statistics.mean(pp)):
    need = (2.0*sd/eff)**2 if eff>0 else float('inf')
    print(f"  edge ${eff:+.4f}/trade, sd ${sd:.3f}  ->  ~{need:,.0f} trades for t=2")
