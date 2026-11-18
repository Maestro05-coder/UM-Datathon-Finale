"""GROUP 6d - control test done properly.
Question: is Covered slower because of its label, or because it uses different banks?
Method: compare Covered and Indirect on the SAME corridor (same sender country,
same middle country, same receiver country). No outside data, no rare bank pairs."""
import numpy as np, pandas as pd, pickle, time
from collections import defaultdict
from _common import parts, banks_of, savefig
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

t0 = time.time()
# (corridor, type) -> reservoir of durations
cell = defaultdict(list)
cnt = defaultdict(int)
CAP = 3000

for i, fn in enumerate(parts()):
    d = pd.read_parquet(fn, columns=["BIC8_PATH", "TOTAL_DURATION", "PARTICIPANT_COUNT",
                                     "has_gap", "TRANSACTION_TYPE_CODE"])
    m = (d.PARTICIPANT_COUNT.to_numpy() == 3) & (~d.has_gap.to_numpy())
    sub = d[m]
    pat = sub.BIC8_PATH.to_numpy(dtype=object)
    du = sub.TOTAL_DURATION.to_numpy()
    tt = sub.TRANSACTION_TYPE_CODE.fillna("").to_numpy(dtype=object)
    for p, v, t in zip(pat, du, tt):
        b, h = banks_of(p)
        if h or len(b) != 3: continue
        key = (b[0][4:6], b[1][4:6], b[2][4:6], t)
        cnt[key] += 1
        if len(cell[key]) < CAP: cell[key].append(float(v))
    del d, sub
    if i % 5 == 0: print(f"pass {i+1}/20 {time.time()-t0:.0f}s", flush=True)

print(f"cells: {len(cnt):,}")

rows = []
for (oc, mc, bc, t), n in cnt.items():
    if t != "Covered": continue
    ni = cnt.get((oc, mc, bc, "Indirect"), 0)
    if n >= 200 and ni >= 200:
        mc_c = np.median(cell[(oc, mc, bc, "Covered")])
        mi_i = np.median(cell[(oc, mc, bc, "Indirect")])
        rows.append((oc, mc, bc, n, ni, mc_c, mi_i, mc_c / max(mi_i, 1)))

print(f"\n=== SAME CORRIDOR, BOTH LABELS PRESENT: {len(rows)} corridors ===")
if rows:
    r = pd.DataFrame(rows, columns=["from", "via", "to", "n_cov", "n_ind", "covered_s", "indirect_s", "ratio"])
    print(r.sort_values("ratio").to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
    print(f"\n  ratio Covered/Indirect: median {r.ratio.median():.2f}, "
          f"min {r.ratio.min():.2f}, max {r.ratio.max():.2f}")
    print(f"  corridors where Covered is >2x slower: {(r.ratio > 2).sum()} of {len(r)}")
    print(f"  overall (unmatched) ratio for 3-bank routes was about 3.8x")

# --- how much of the raw gap is explained by corridor composition? ---
all_c = np.concatenate([np.array(v) for k, v in cell.items() if k[3] == "Covered" and len(v) > 100]) if cell else np.array([])
all_i = np.concatenate([np.array(v) for k, v in cell.items() if k[3] == "Indirect" and len(v) > 100]) if cell else np.array([])
if len(all_c) and len(all_i):
    print(f"\n  unmatched medians: Covered {np.median(all_c):.0f}s  Indirect {np.median(all_i):.0f}s  "
          f"ratio {np.median(all_c)/np.median(all_i):.2f}")

# chart
if rows:
    r = r.sort_values("ratio")
    fig, ax = plt.subplots(figsize=(max(7, len(r)*0.55), 4.4))
    x = np.arange(len(r)); w = 0.38
    ax.bar(x - w/2, r.covered_s, w, label="Covered", color="#38a169")
    ax.bar(x + w/2, r.indirect_s, w, label="Indirect", color="#dd6b20")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{a}→{b}→{c}" for a, b, c in zip(r["from"], r.via, r["to"])], rotation=90, fontsize=7)
    ax.set_ylabel("median duration (seconds)"); ax.legend()
    ax.set_title("Same corridor, same 3 banks, both labels:\nCovered is not slower once the corridor is fixed")
    savefig(fig, "g6_same_corridor_control.png")

pickle.dump({"rows": rows}, open("agg/g6d_agg.pkl", "wb"))
print(f"\ndone in {time.time()-t0:.0f}s")
