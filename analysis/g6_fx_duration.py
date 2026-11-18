"""GROUP 6 - FX & DURATION.
Question: what makes a payment slow, and what does a currency conversion cost in time?
Streams all 10m rows once; keeps samples of durations per (routing type, banks, conversions)."""
import numpy as np, pandas as pd, pickle, time
from collections import Counter, defaultdict
from _common import parts, banks_of, country_of, Res, med, q

t0 = time.time()
dur = defaultdict(Res)          # (type, banks, conversions) -> durations
dur_gap = defaultdict(Res)      # (banks, conversions, has_gap) -> durations
sample = []                     # every 40th row of each part, for pair/country work
NTH = 40

for i, fn in enumerate(parts()):
    d = pd.read_parquet(fn, columns=["BIC8_PATH", "TOTAL_DURATION", "CURRENCY_CONVERSION_COUNT",
                                     "PARTICIPANT_COUNT", "TRANSACTION_TYPE_CODE", "has_gap",
                                     "ORDERING_BIC8", "BENEFICIARY_BIC8", "USD_AMOUNT", "CURRENCY_CODE"])
    du = d.TOTAL_DURATION.to_numpy()
    cv = d.CURRENCY_CONVERSION_COUNT.to_numpy()
    pc = d.PARTICIPANT_COUNT.to_numpy()
    tt = d.TRANSACTION_TYPE_CODE.fillna("").to_numpy(dtype=object)
    gp = d.has_gap.to_numpy()
    for j in range(len(du)):
        dur[(tt[j], int(pc[j]), int(cv[j]))].add(float(du[j]))
        dur_gap[(int(pc[j]), int(cv[j]), bool(gp[j]))].add(float(du[j]))
    sample.append(d.iloc[::NTH])
    del d
    if i % 5 == 0: print(f"pass {i+1}/20 {time.time()-t0:.0f}s", flush=True)

sample = pd.concat(sample, ignore_index=True)
print(f"streamed in {time.time()-t0:.0f}s; sample rows {len(sample):,}")

print("\n=== 1. MEDIAN DURATION BY (type, banks, conversions) ===")
rows = []
for (t, n, c), r in sorted(dur.items()):
    if r.n >= 3000 and n <= 6 and c <= 4:
        rows.append((t, n, c, r.n, r.med(), q(r.data, 25), q(r.data, 75)))
print(f"{'type':<9}{'banks':>6}{'conv':>5}{'n':>10}{'median':>9}{'p25':>8}{'p75':>9}")
for t, n, c, k, m, a, b in rows:
    print(f"{t:<9}{n:>6}{c:>5}{k:>10,}{m:>9.0f}{a:>8.0f}{b:>9.0f}")

print("\n=== 2. DOES A CONVERSION ADD TIME? (fixed banks and type) ===")
for t in ["Direct", "Indirect"]:
    for n in [2, 3, 4]:
        line = []
        for c in range(0, 4):
            r = dur.get((t, n, c))
            if r and r.n >= 3000:
                line.append(f"conv={c}: {r.med():.0f}s (n={r.n:,})")
        if line: print(f"  {t}, {n} banks -> " + " | ".join(line))

print("\n=== 3. IS DURATION A PROPERTY OF THE BANK PAIR? (2-bank, no gap) ===")
s2 = sample[(sample.PARTICIPANT_COUNT == 2) & (~sample.has_gap)].copy()
s2["pair"] = s2.ORDERING_BIC8 + "->" + s2.BENEFICIARY_BIC8
g = s2.groupby("pair").TOTAL_DURATION.agg(["count", "median",
                                           lambda x: np.percentile(x, 25),
                                           lambda x: np.percentile(x, 75),
                                           "nunique"])
g.columns = ["n", "median", "p25", "p75", "distinct_values"]
g = g[g.n >= 20]
g["spread"] = (g.p75 - g.p25) / g["median"].replace(0, np.nan)
print(f"pairs with >=20 payments: {len(g):,}")
print(f"  median within-pair spread ((p75-p25)/median): {g.spread.median():.3f}")
print(f"  share of pairs with spread < 0.1: {(g.spread < .1).mean():.1%}")
print(f"  share of pairs with a single repeated duration: {(g.distinct_values == 1).mean():.1%}")
print("  tightest pairs:")
print(g.sort_values("spread").head(5)[["n", "median", "p25", "p75", "distinct_values"]].to_string())
print("  loosest pairs:")
print(g.sort_values("spread").tail(5)[["n", "median", "p25", "p75", "distinct_values"]].to_string())

print("\n=== 4. DO HIDDEN BANKS ADD TIME? (2 banks, same conversions) ===")
for c in [0, 1]:
    a = dur_gap.get((2, c, False)); b = dur_gap.get((2, c, True))
    if a and b:
        print(f"  conv={c}: no gap {a.med():.0f}s (n={a.n:,}) | gap {b.med():.0f}s (n={b.n:,})")

print("\n=== 5. DOES THE COUNTRY PAIR MATTER? (2 banks, conv=0) ===")
s3 = s2[s2.CURRENCY_CONVERSION_COUNT == 0].copy()
s3["oc"] = s3.ORDERING_BIC8.str[4:6]; s3["bc"] = s3.BENEFICIARY_BIC8.str[4:6]
by_b = s3.groupby("bc").TOTAL_DURATION.agg(["count", "median"])
by_b = by_b[by_b["count"] >= 500].sort_values("median")
print("  fastest beneficiary countries:", {k: round(v) for k, v in by_b["median"].head(5).items()})
print("  slowest beneficiary countries:", {k: round(v) for k, v in by_b["median"].tail(5).items()})
s3["same_cc"] = s3.oc == s3.bc
print("  same country both ends:", s3.groupby("same_cc").TOTAL_DURATION.median().round(0).to_dict())

print("\n=== 6. THE COVERED PUZZLE, restated ===")
for n in [3, 4]:
    for c in [1, 2]:
        a = dur.get(("Covered", n, c)); b = dur.get(("Indirect", n, c))
        if a and b and a.n > 2000 and b.n > 2000:
            print(f"  {n} banks, conv={c}: Covered {a.med():.0f}s | Indirect {b.med():.0f}s | ratio {a.med()/b.med():.2f}")

# ---------- charts live in g6_charts.py (chart-only, reads cache_full + agg/) ----------
pickle.dump({"dur": {k: (v.n, v.med(), q(v.data, 25), q(v.data, 75)) for k, v in dur.items()},
             "dur_gap": {k: (v.n, v.med()) for k, v in dur_gap.items()},
             "pairs": g[["n", "median", "p25", "p75", "distinct_values", "spread"]].head(2000),
             "by_country": by_b}, open("agg/g6_agg.pkl", "wb"))
print(f"\ndone in {time.time()-t0:.0f}s")
