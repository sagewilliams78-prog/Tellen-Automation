exec(open('disagree.py').read().split("bars = load_bars()")[0])
bars = load_bars()
sess = sorted({b["date"] for s in bars for b in bars[s]})
n=len(sess)
SPL = {"A": set(sess[int(n*.6):]), "B": set(sess[:int(n*.4)]), "C": set(sess[1::2])}
print(f"{n} sessions  A={len(SPL['A'])} B={len(SPL['B'])} C={len(SPL['C'])}\n")

def net_for(frac, days, key):
    globals()['TARGET_FRAC'] = frac
    o = [x for x in observations(bars) if x["day"] in days]
    s = summ(run_policy(o, key))
    return (s["net"] if s else 0.0), (s["n"] if s else 0)

print("TARGET_FRAC, cascade policy — net $ per split")
print(f"  {'frac':>5} {'A':>8} {'B':>8} {'C':>8} {'full':>8} {'n':>4}  verdict")
base = {}
for k in ("A","B","C"): base[k] = net_for(0.25, SPL[k], "cascade")[0]
basefull, _ = net_for(0.25, set(sess), "cascade")
for frac in (0.05,0.10,0.15,0.20,0.25,0.30,0.35):
    vals = {k: net_for(frac, SPL[k], "cascade")[0] for k in ("A","B","C")}
    full, cnt = net_for(frac, set(sess), "cascade")
    beat = sum(1 for k in ("A","B","C") if vals[k] > base[k])
    tag = "SHIPPED" if frac==0.25 else ("WINS 3/3" if beat==3 else f"{beat}/3")
    print(f"  {frac:>5.2f} {vals['A']:>8.2f} {vals['B']:>8.2f} {vals['C']:>8.2f} "
          f"{full:>8.2f} {cnt:>4}  {tag}")
