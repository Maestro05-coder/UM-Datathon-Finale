"""GROUP 6e - tighter control: same corridor AND same middle bank.
Also: does the middle bank itself decide the duration?"""
import numpy as np, pandas as pd, pickle, time
from collections import defaultdict, Counter
from _common import parts, banks_of, savefig
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

t0 = time.time()
cell = defaultdict(list); cnt = Counter()
mid_all = defaultdict(list)
mid_type = Counter()
CAP = 2000

for i, fn in enumerate(parts()):
    d = pd.read_parquet(fn, columns=["BIC8_PATH", "TOTAL_DURATION", "PARTICIPANT_COUNT",
                                     "has_gap", "TRANSACTION_TYPE_CODE"])
    m = (d.PARTICIPANT_COUNT.to_numpy() == 3) & (~d.has_gap.to_numpy())
    sub = d[m]
    pat = sub.BIC8_PATH.to_numpy(dtype=object); du = sub.TOTAL_DURATION.to_numpy()
    tt = sub.TRANSACTION_TYPE_CODE.fillna("").to_numpy(dtype=object)
    for p, v, t in zip(pat, du, tt):
        b, h = banks_of(p)
        if h or len(b) != 3: continue
        mid = b[1]
        k = (b[0][4:6], mid, b[2][4:6], t)
        cnt[k] += 1
        if len(cell[k]) < CAP: cell[k].append(float(v))
        if len(mid_all[mid]) < CAP: mid_all[mid].append(float(v))
        mid_type[(mid, t)] += 1
    del d, sub
    if i % 5 == 0: print(f"pass {i+1}/20 {time.time()-t0:.0f}s", flush=True)

rows = []
for (oc, mid, bc, t), n in cnt.items():
    if t != "Covered": continue
    ni = cnt.get((oc, mid, bc, "Indirect"), 0)
    if n >= 100 and ni >= 100:
        c = np.median(cell[(oc, mid, bc, "Covered")]); i2 = np.median(cell[(oc, mid, bc, "Indirect")])
        rows.append((oc, mid, bc, n, ni, c, i2, c / max(i2, 1)))

print(f"\n=== SAME CORRIDOR + SAME MIDDLE BANK: {len(rows)} cells with both labels ===")
if rows:
    r = pd.DataFrame(rows, columns=["from", "via", "to", "n_cov", "n_ind", "covered_s", "indirect_s", "ratio"])
    print(r.sort_values("ratio").to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
    print(f"\n  ratio: median {r.ratio.median():.2f}  p25 {r.ratio.quantile(.25):.2f}  p75 {r.ratio.quantile(.75):.2f}")
    print(f"  cells where Covered >2x slower: {(r.ratio>2).sum()} of {len(r)}")
else:
    print("  none at this strictness")

print("\n=== DOES THE MIDDLE BANK DECIDE DURATION? (all 3-bank routes) ===")
stats = {m: (len(v), float(np.median(v))) for m, v in mid_all.items() if len(v) >= 500}
meds = np.array([s[1] for s in stats.values()])
print(f"  middle banks with >=500 routes: {len(stats):,}")
print(f"  median duration by middle bank: p10 {np.percentile(meds,10):.0f}s  median {np.median(meds):.0f}s  p90 {np.percentile(meds,90):.0f}s")
top = sorted(stats.items(), key=lambda kv: -kv[1][1])[:5]
bot = sorted(stats.items(), key=lambda kv: kv[1][1])[:5]
print("  slowest middles:", {k: f"{v[1]:.0f}s (n={v[0]:,})" for k, v in top})
print("  fastest middles:", {k: f"{v[1]:.0f}s (n={v[0]:,})" for k, v in bot})

print("\n=== IS THE LABEL TIED TO WHICH MIDDLE BANK IS USED? ===")
cov_tot = sum(v for (m, t), v in mid_type.items() if t == "Covered")
ind_tot = sum(v for (m, t), v in mid_type.items() if t == "Indirect")
share = []
for m in stats:
    nc = mid_type.get((m, "Covered"), 0); ni = mid_type.get((m, "Indirect"), 0)
    if nc + ni >= 1000:
        share.append((m, nc / (nc + ni), nc + ni, stats[m][1]))
share.sort(key=lambda x: -x[1])
print(f"  base Covered share among 3-bank routes: {cov_tot/(cov_tot+ind_tot):.3f}")
print("  middles most associated with Covered:",
      {m: f"{s:.1%}" for m, s, n, d in share[:5]})
print("  middles least associated with Covered:",
      {m: f"{s:.1%}" for m, s, n, d in share[-5:]})
print("  spread of Covered share across middle banks:",
      f"p10 {np.percentile([s for _, s, _, _ in share],10):.1%} .. p90 {np.percentile([s for _, s, _, _ in share],90):.1%}")

if rows:
    r = r.sort_values("ratio")
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = np.arange(len(r)); w = .38
    ax.bar(x - w/2, r.covered_s, w, label="Covered", color="#38a169")
    ax.bar(x + w/2, r.indirect_s, w, label="Indirect", color="#dd6b20")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{a}→{m}→{c}" for a, m, c in zip(r["from"], r.via, r["to"])], rotation=90, fontsize=6)
    ax.set_ylabel("median duration (s)"); ax.legend()
    ax.set_title("Same corridor and same middle bank: the gap narrows but does not vanish")
    savefig(fig, "g6_same_middle_control.png")

pickle.dump({"rows": rows, "mid_stats": stats,
             "share": share, "base": cov_tot/(cov_tot+ind_tot)}, open("agg/g6e_agg.pkl", "wb"))
print(f"\ndone in {time.time()-t0:.0f}s")
