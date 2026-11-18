"""GROUP 6b - is a route's duration the SUM of per-step delays?
Step 1: measure each bank-to-bank step's typical duration from 2-bank payments.
Step 2: predict multi-bank durations by adding the steps, compare with reality."""
import numpy as np, pandas as pd, pickle, time
from collections import defaultdict
from _common import parts, banks_of

t0 = time.time()
STRIDE = 3   # use 1 in 3 of the 2-bank rows to learn step delays (plenty of data)

hop = defaultdict(lambda: [0, 0.0])   # (bankA,bankB) -> [n, sum_duration]

# ---------- pass 1: learn step delays from 2-bank routes ----------
for i, fn in enumerate(parts()):
    d = pd.read_parquet(fn, columns=["BIC8_PATH", "TOTAL_DURATION", "PARTICIPANT_COUNT", "has_gap"])
    m = (d.PARTICIPANT_COUNT.to_numpy() == 2) & (~d.has_gap.to_numpy())
    sub = d[m]
    pat = sub.BIC8_PATH.to_numpy(dtype=object)[::STRIDE]
    du = sub.TOTAL_DURATION.to_numpy()[::STRIDE]
    for p, v in zip(pat, du):
        b, h = banks_of(p)
        if len(b) == 2 and h == 0:
            k = (b[0], b[1])
            e = hop[k]; e[0] += 1; e[1] += v
    del d, sub
    if i % 5 == 0: print(f"pass1 {i+1}/20 {time.time()-t0:.0f}s", flush=True)

step = {k: s / n for k, (n, s) in hop.items() if n >= 10}
print(f"steps learned: {len(step):,} (from {len(hop):,} observed pairs)")

# ---------- pass 2: test additivity on 3- and 4-bank routes ----------
res = defaultdict(lambda: {"n": 0, "ratios": [], "abs_err": []})
examples = defaultdict(list)
for i, fn in enumerate(parts()):
    d = pd.read_parquet(fn, columns=["BIC8_PATH", "TOTAL_DURATION", "PARTICIPANT_COUNT",
                                     "has_gap", "TRANSACTION_TYPE_CODE"])
    m = (d.PARTICIPANT_COUNT.to_numpy() >= 3) & (d.PARTICIPANT_COUNT.to_numpy() <= 4) & (~d.has_gap.to_numpy())
    sub = d[m]
    pat = sub.BIC8_PATH.to_numpy(dtype=object)
    du = sub.TOTAL_DURATION.to_numpy()
    tt = sub.TRANSACTION_TYPE_CODE.fillna("").to_numpy(dtype=object)
    for p, v, t in zip(pat, du, tt):
        b, h = banks_of(p)
        if h or len(b) < 3: continue
        need = [(b[j], b[j + 1]) for j in range(len(b) - 1)]
        if not all(k in step for k in need): continue
        pred = sum(step[k] for k in need)
        if pred <= 0: continue
        r = res[(t, len(b))]
        r["n"] += 1
        r["ratios"].append(v / pred)
        r["abs_err"].append(abs(v - pred) / pred)
        if len(examples[t]) < 3:
            examples[t].append((p, round(v), round(pred), [round(step[k]) for k in need]))
    del d, sub
    if i % 5 == 0: print(f"pass2 {i+1}/20 {time.time()-t0:.0f}s", flush=True)

print("\n=== PREDICTED vs ACTUAL (prediction = sum of the steps' own typical duration) ===")
print(f"{'type':<9}{'banks':>6}{'n':>9}{'median actual/predicted':>26}{'median error':>14}")
for (t, n), r in sorted(res.items()):
    if r["n"] < 500: continue
    print(f"{t:<9}{n:>6}{r['n']:>9,}{np.median(r['ratios']):>26.3f}{np.median(r['abs_err']):>13.1%}")

print("\n=== examples (path, actual seconds, predicted seconds, per-step values) ===")
for t, ex in examples.items():
    for e in ex: print(f"  {t:<9} {e[0]:<45} actual {e[1]:>5}s  predicted {e[2]:>5}s  steps {e[3]}")

# ---------- how different are the steps? ----------
vals = np.array(list(step.values()), dtype=float)
print("\n=== step delay spread ===")
print(f"  steps: {len(vals):,}  min {vals.min():.0f}s  p25 {np.percentile(vals,25):.0f}s  median {np.median(vals):.0f}s  p75 {np.percentile(vals,75):.0f}s  max {vals.max():.0f}s")
print(f"  share of steps under 60s: {(vals<60).mean():.1%}   over 1000s: {(vals>1000).mean():.1%}")

# ---------- does a step's delay depend on the countries involved? ----------
d2 = pd.DataFrame([(a[4:6], b[4:6], v) for (a, b), v in step.items()], columns=["oc", "bc", "delay"])
cp = d2.groupby(["oc", "bc"]).delay.agg(["count", "median"])
cp = cp[cp["count"] >= 30]
print(f"\n=== country pairs with >=30 steps: {len(cp):,} ===")
print("  fastest:", {f"{a}-{b}": round(m) for (a, b), m in cp["median"].nsmallest(5).items()})
print("  slowest:", {f"{a}-{b}": round(m) for (a, b), m in cp["median"].nlargest(5).items()})
print(f"  spread of country-pair medians: p10 {cp['median'].quantile(.1):.0f}s  p90 {cp['median'].quantile(.9):.0f}s")

# ---------- charts live in g6_charts.py (chart-only, reads cache_full + agg/) ----------
pickle.dump({"step": step, "res": {k: (v["n"], float(np.median(v["ratios"])), float(np.median(v["abs_err"])))
                                   for k, v in res.items()},
             "country_pairs": cp}, open("agg/g6b_agg.pkl", "wb"))
print(f"\ndone in {time.time()-t0:.0f}s")
