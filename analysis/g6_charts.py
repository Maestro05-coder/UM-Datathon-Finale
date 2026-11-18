"""g6 charts - simple, one idea per picture, from the cached aggregates + cache_full.

Sources: cache_full/ (exact medians), agg/g6b_agg.pkl, agg/g6d_agg.pkl, agg/g6e_agg.pkl.
Run:  python analysis/g6_charts.py      Charts land in groups/g6_fx_duration/.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ddb, full_glob, savefig

import pickle
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import _style as S

S.apply()
GROUP = "g6_fx_duration"
HERE = os.path.dirname(os.path.abspath(__file__))
con = ddb()
G = full_glob()


def q(sql):
    return con.execute(sql).df()


# ------------------------------------------------------------------ 1. what makes a payment slow
print("1. duration vs route length / conversions")
byn = q(f"""
    SELECT PARTICIPANT_COUNT n, COUNT(*) rows, MEDIAN(TOTAL_DURATION) med
    FROM read_parquet('{G}') WHERE has_gap = FALSE AND PARTICIPANT_COUNT BETWEEN 2 AND 8
    GROUP BY 1 ORDER BY 1
""")
byc = q(f"""
    SELECT PARTICIPANT_COUNT n, CURRENCY_CONVERSION_COUNT c, COUNT(*) rows,
           MEDIAN(TOTAL_DURATION) med
    FROM read_parquet('{G}')
    WHERE has_gap = FALSE AND PARTICIPANT_COUNT IN (3, 4)
    GROUP BY 1, 2 ORDER BY 1, 2
""")
print(byn.to_string(index=False))
print(byc.to_string(index=False))

fig, axs = plt.subplots(1, 2, figsize=(12.0, 4.8))

ax = axs[0]
bars = ax.bar(byn.n.astype(int).astype(str), byn.med, color=S.C_ACCENT, width=0.62)
S.vlabels(ax, bars, [f"{v:.0f}" for v in byn.med])
S.clean(ax)
S.title(ax, "Each extra bank adds minutes to a payment",
        "Median payment time by number of banks (hidden banks excluded).")
ax.set_xlabel("Banks visible in the route")
ax.set_ylabel("Median duration (seconds)")
ax.set_ylim(0, byn.med.max() * 1.16)

ax = axs[1]
width = 0.38
colors = {3: S.C_ACCENT, 4: "#dd6b20"}
for i, n in enumerate([3, 4]):
    sub = byc[byc.n == n].sort_values("c")
    x = sub.c.to_numpy() + (i - 0.5) * width
    bars = ax.bar(x, sub.med, width, color=colors[n], label=f"{n} banks")
    S.vlabels(ax, bars, [f"{v:.0f}" for v in sub.med], fontsize=9)
S.clean(ax)
S.title(ax, "Extra currency conversions add no time",
        "At the same number of banks, the conversion count does not add delay.")
ax.set_xlabel("Currency conversions in the route")
ax.set_ylabel("Median duration (seconds)")
ax.set_xticks([0, 1, 2, 3])
ax.set_ylim(0, byc.med.max() * 1.16)
S.legend_below(ax, ncol=2, y=-0.20)
fig.tight_layout()
savefig(fig, "g6_duration_vs_length.png", group=GROUP)

# ------------------------------------------------------------------ 2. the Covered puzzle
print("\n2. the Covered gap shrinks under control")
raw = q(f"""
    SELECT TRANSACTION_TYPE_CODE t, MEDIAN(TOTAL_DURATION) med
    FROM read_parquet('{G}')
    WHERE PARTICIPANT_COUNT = 3 AND has_gap = FALSE
      AND TRANSACTION_TYPE_CODE IN ('Covered', 'Indirect')
    GROUP BY 1
""").set_index("t").med
D = pickle.load(open(os.path.join(HERE, "agg", "g6d_agg.pkl"), "rb"))["rows"]
E = pickle.load(open(os.path.join(HERE, "agg", "g6e_agg.pkl"), "rb"))["rows"]
ratios = [raw["Covered"] / raw["Indirect"],
          float(np.median([r[7] for r in D])),
          float(np.median([r[7] for r in E]))]
labels = ["All 3-bank routes", "Same corridor\n(same 3 countries)", "Same corridor +\nsame middle bank"]
print("raw", raw.round(1).to_dict(), "cells", len(D), len(E), "ratios", np.round(ratios, 2))

fig, ax = plt.subplots(figsize=(8.6, 4.8))
colors = [S.C_WARN, S.C_GREY, S.C_ACCENT]
bars = ax.bar(labels, ratios, color=colors, width=0.55)
for bar, v in zip(bars, ratios):
    ax.annotate(f"{v:.2f}\u00d7", xy=(bar.get_x() + bar.get_width() / 2, v), xytext=(0, 4),
                textcoords="offset points", ha="center", va="bottom",
                fontsize=13, fontweight="bold")
S.clean(ax)
S.title(ax, "The \"Covered is slow\" gap disappears when the banks are held fixed",
        "Covered duration divided by Indirect duration, as the comparison gets fairer.")
ax.set_xlabel("Comparison")
ax.set_ylabel("Covered \u00f7 Indirect (1.0 = same speed)")
ax.set_ylim(0, max(ratios) * 1.22)
ax.axhline(1.0, color=S.C_MUTED, lw=1.1, ls="--", zorder=1)
savefig(fig, "g6_gap_shrinks.png", group=GROUP)

# ------------------------------------------------------------------ 3. duration = sum of steps
print("\n3. steps add up; step delays are bimodal")
A = pickle.load(open(os.path.join(HERE, "agg", "g6b_agg.pkl"), "rb"))
res = A["res"]
names = [("Indirect", 3), ("Covered", 3), ("Indirect", 4), ("Covered", 4)]
err = [res[k][2] * 100 for k in names]
lab = [f"{t}\n{n} banks" for t, n in names]
steps = np.array(list(A["step"].values()), dtype=float)
buckets = [("under 1 min", (steps < 60).mean() * 100),
           ("1-15 min", ((steps >= 60) & (steps < 900)).mean() * 100),
           ("15-60 min", ((steps >= 900) & (steps < 3600)).mean() * 100),
           ("over 1 hour", (steps >= 3600).mean() * 100)]

fig, axs = plt.subplots(1, 2, figsize=(12.0, 4.8))

ax = axs[0]
bars = ax.bar(lab, err, color=S.C_ACCENT, width=0.58)
S.vlabels(ax, bars, [f"{v:.0f}%" for v in err])
S.clean(ax)
S.title(ax, "Adding up the steps predicts the total",
        "Typical error between the real duration and the sum of its steps.")
ax.set_xlabel("Route (hidden banks excluded)")
ax.set_ylabel("Median error (share of the duration)")
ax.set_ylim(0, max(err) * 1.25)
S.pct_axis(ax, "y", step=5, xmax=100)

ax = axs[1]
bar_x = [b[0] for b in buckets]
bar_v = [b[1] for b in buckets]
bars = ax.bar(bar_x, bar_v, color=S.C_ACCENT, width=0.62)
S.vlabels(ax, bars, [f"{v:.0f}%" for v in bar_v])
S.clean(ax)
S.title(ax, "Steps are either quick or slow, rarely in between",
        "Share of bank-to-bank steps by how long they take.")
ax.set_xlabel("Time for one bank-to-bank step")
ax.set_ylabel("Share of steps")
ax.set_ylim(0, 80)
S.pct_axis(ax, "y", step=20, xmax=100)
fig.tight_layout()
savefig(fig, "g6_step_additivity.png", group=GROUP)

print("\nDONE g6 charts")
