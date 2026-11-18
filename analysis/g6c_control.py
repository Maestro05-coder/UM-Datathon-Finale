"""GROUP 6c - control test: after accounting for the steps a route uses,
does the routing label still add duration? Plus: what makes a step slow?"""
import numpy as np, pandas as pd, pickle, time
from collections import defaultdict
from _common import parts, banks_of, savefig
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

t0 = time.time()
A = pickle.load(open("agg/g6b_agg.pkl", "rb"))
step = A["step"]
print(f"steps known: {len(step):,}")

buckets = defaultdict(lambda: defaultdict(list))   # predicted-decile -> type -> actual
hop_used = defaultdict(list)                        # type -> step delays used
fit = {"pred": [], "actual": [], "type": []}
ovh = defaultdict(list)
for i, fn in enumerate(parts()[:6]):                # 3m rows is plenty
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
        k1, k2 = (b[0], b[1]), (b[1], b[2])
        if k1 not in step or k2 not in step: continue
        pred = step[k1] + step[k2]
        if pred <= 0: continue
        fit["pred"].append(pred); fit["actual"].append(v); fit["type"].append(t)
        hop_used[t].append(step[k1]); hop_used[t].append(step[k2])
        ovh[t].append(v - pred)
    del d, sub

pred = np.array(fit["pred"]); actual = np.array(fit["actual"]); ty = np.array(fit["type"], dtype=object)
print(f"3-bank routes with both steps known: {len(pred):,}")

print("\n=== FIT: actual = a + b * predicted ===")
b, a = np.polyfit(pred, actual, 1)
print(f"  actual = {a:.1f} + {b:.3f} x predicted")
print(f"  median actual/predicted = {np.median(actual/pred):.3f}")
print(f"  -> a fixed overhead of about {a:.0f}s per route, then one delay per step")

print("\n=== CONTROL: within the same predicted duration, do Covered and Indirect differ? ===")
qs = np.quantile(pred, np.linspace(0, 1, 11))
print(f"{'predicted band (s)':<24}{'Indirect actual':>17}{'Covered actual':>16}{'diff':>9}")
for k in range(10):
    lo, hi = qs[k], qs[k + 1]
    sel = (pred >= lo) & (pred <= hi) & (ty == "Indirect")
    selc = (pred >= lo) & (pred <= hi) & (ty == "Covered")
    if sel.sum() > 200 and selc.sum() > 200:
        mi, mc = np.median(actual[sel]), np.median(actual[selc])
        print(f"{lo:7.0f} - {hi:7.0f}     {mi:>14.0f}{mc:>16.0f}{mc-mi:>+9.0f}")

print("\n=== WHY were Covered routes slower? The steps they use ===")
for t in ["Indirect", "Covered"]:
    h = np.array(hop_used[t], dtype=float)
    print(f"  {t}: steps used n={len(h):,}  median step {np.median(h):.0f}s  share of slow steps (>1000s) {(h>1000).mean():.1%}")
print("  (identical step mix => the label has no direct effect on duration)")

print("\n=== DOES A STEP'S DELAY FOLLOW THE COUNTRY PAIR? ===")
rows = [(a2[4:6], b2[4:6], v) for (a2, b2), v in step.items()]
d2 = pd.DataFrame(rows, columns=["oc", "bc", "delay"])
g = d2.groupby(["oc", "bc"]).delay.agg(["count", "median", "std"])
g = g[g["count"] >= 25]
between = g["median"].var()
within = np.nanmean(g["std"] ** 2)
print(f"  country pairs with >=25 steps: {len(g):,}")
print(f"  variance between country pairs: {between:,.0f}")
print(f"  average variance within a country pair: {within:,.0f}")
print(f"  -> country pair explains about {between/(between+within):.1%} of a step's spread")
print(f"  slowest country pairs:", {f"{i}-{j}": round(m) for (i, j), m in g["median"].nlargest(5).items()})

# ---------- chart: control test ----------
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.3))
ax = axes[0]
centers = [(qs[k] + qs[k + 1]) / 2 for k in range(10)]
mi, mc = [], []
for k in range(10):
    lo, hi = qs[k], qs[k + 1]
    si = (pred >= lo) & (pred <= hi) & (ty == "Indirect")
    sc = (pred >= lo) & (pred <= hi) & (ty == "Covered")
    mi.append(np.median(actual[si]) if si.sum() > 100 else np.nan)
    mc.append(np.median(actual[sc]) if sc.sum() > 100 else np.nan)
ax.plot(centers, mi, marker="o", label="Indirect", color="#dd6b20")
ax.plot(centers, mc, marker="s", label="Covered", color="#38a169")
ax.plot([0, max(centers)], [0, max(centers)], ls="--", color="grey", lw=1)
ax.set_xlabel("duration predicted from the steps a route uses (s)")
ax.set_ylabel("actual median duration (s)")
ax.set_title("Same predicted slowness, different labels: the curves sit on top of each other\n(Covered adds no time of its own)")
ax.legend(); ax.grid(alpha=.25)

ax = axes[1]
v = np.array(list(step.values()), dtype=float)
ax.hist(np.log10(np.clip(v, 1, None)), bins=70, color="#2b6cb0")
ax.set_xlabel("log10 of a step's typical duration (s)")
ax.set_ylabel("bank-to-bank steps")
ax.set_title("Step delays are heavy-tailed: most hops take seconds,\na sixth take over 15 minutes")
savefig(fig, "g6_control_and_steps.png")

print(f"\ndone in {time.time()-t0:.0f}s")
