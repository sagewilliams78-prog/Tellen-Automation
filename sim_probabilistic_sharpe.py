exec(open('eod.py').read().split('print("=" * 78)')[0])
import statistics as st, math
from math import sqrt, log, erf

def ncdf(x): return 0.5*(1+erf(x/sqrt(2)))
def nppf(p):   # Acklam inverse normal
    a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00]
    b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,6.680131188771972e+01,-1.328068155288572e+01]
    c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,-2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00]
    d=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,3.754408661907416e+00]
    pl=0.02425
    if p<pl:
        q=sqrt(-2*log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p>1-pl:
        q=sqrt(-2*log(1-p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q=p-0.5; r=q*q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

def moments(x):
    n=len(x); m=st.mean(x); s=st.stdev(x)
    sk=sum(((v-m)/s)**3 for v in x)/n
    ku=sum(((v-m)/s)**4 for v in x)/n
    return m,s,sk,ku

def analyse(label, pnl):
    m,s,sk,ku = moments(pnl); T=len(pnl); SR=m/s
    var = (1 - sk*SR + (ku-1)*SR*SR/4)
    se  = sqrt(var/T)
    psr = ncdf(SR/se)                                  # P(true SR > 0)
    mintrl = var*(1.645/SR)**2 if SR>0 else float('inf')
    print(f"\n{label}")
    print(f"  trades T           {T}")
    print(f"  per-trade Sharpe   {SR:+.4f}   (mean ${m:+.4f} / sd ${s:.4f})")
    print(f"  skew {sk:+.2f}  kurtosis {ku:.2f}")
    print(f"  PSR  P(true SR>0)  {psr*100:.1f}%      (want >95%)")
    print(f"  MinTRL @95%        {mintrl:,.0f} trades   (have {T})")
    return SR, se, T

base = policy(OBS); ts18 = policy(OBS, max_bars=18)
b_sr,b_se,b_T = analyse("SHIPPED (cascade, no time-stop)", [t['pnl'] for t in base])
t_sr,t_se,t_T = analyse("BEST FOUND TODAY (18-bar time-stop)", [t['pnl'] for t in ts18])

print("\n" + "="*70)
print("FALSE STRATEGY THEOREM  — E[max Sharpe] from PURE NOISE across N trials")
print("="*70)
g=0.5772156649
for N in (1,5,10,20,40,80):
    emax = (1-g)*nppf(1-1.0/N) + g*nppf(1-1.0/(N*math.e)) if N>1 else 0.0
    print(f"  N={N:>3} trials -> expected best-of-N Sharpe from noise alone: "
          f"{emax*t_se:+.4f}  (in this sample's units)")
print(f"\n  I tested roughly N=40 configurations today.")
emax40 = ((1-g)*nppf(1-1.0/40) + g*nppf(1-1.0/(40*math.e)))*t_se
print(f"  noise would be expected to produce a best Sharpe of {emax40:+.4f}")
print(f"  the 18-bar time-stop actually produced            {t_sr:+.4f}")
print(f"  -> {'BELOW the noise expectation. No evidence of skill.' if t_sr<emax40 else 'above noise expectation.'}")
