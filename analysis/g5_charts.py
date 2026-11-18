"""g5 charts - simple, one idea per picture, from the cached full-data aggregates.

Numbers come from agg/g5_agg.pkl (built by g5_routing.py on all 10,000,000 rows).
Run:  python analysis/g5_charts.py       Charts land in groups/g5_routing/.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import savefig

import pickle
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import _style as S

S.apply()
GROUP = "g5_routing"
A = pickle.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agg", "g5_agg.pkl"), "rb"))
C = {"Direct": S.C_ACCENT, "Indirect": "#dd6b20", "Covered": "#38a169"}
TYPES = ["Direct", "Indirect", "Covered"]
BANKS = list(range(2, 9))


def mfmt(n):
    return f"{n/1e6:.2f}M" if n >= 1e6 else f"{n/1e3:.0f}k"


# ------------------------------------------------------------------ 1. type vs route length
vb = A["vis_by_type"]
tot = {n: sum(vb.get((n, t), 0) or 0 for t in TYPES) for n in BANKS}
fig, ax = plt.subplots(figsize=(9.5, 4.8))
x = np.arange(len(BANKS))
bottom = np.zeros(len(BANKS))
for t in TYPES:
    vals = np.array([100 * (vb.get((n, t), 0) or 0) / tot[n] for n in BANKS])
    ax.bar(x, vals, bottom=bottom, color=C[t], width=0.64, label=t)
    bottom += vals
for xi, n in zip(x, BANKS):
    ax.annotate(mfmt(tot[n]), xy=(xi, 103), ha="center", va="bottom",
                fontsize=9.5, color=S.C_MUTED)
S.clean(ax)
S.title(ax, "Route length decides the routing label",
        "2 banks is always Direct; 3 or more is Indirect or Covered. "
        "Payments at each length are printed above the bars.")
ax.set_xlabel("Banks visible in the route")
ax.set_ylabel("Share of payments at that length")
ax.set_xticks(x)
ax.set_xticklabels([str(n) for n in BANKS])
ax.set_ylim(0, 109)
S.pct_axis(ax, "y", step=20, xmax=100)
S.legend_below(ax, ncol=3, y=-0.18)
savefig(fig, "routing_1_type_vs_pathlen.png", group=GROUP)

# ------------------------------------------------------------------ 2. gap chance per link
gk = A["gap_by_type_k"]
p = gk[("Direct", 0, True)] / (gk[("Direct", 0, True)] + gk[("Direct", 0, False)])
ks = [k for k in sorted({k[1] for k in gk if k[0] == "Indirect"})
      if (gk.get(("Indirect", k, True), 0) + gk.get(("Indirect", k, False), 0)) >= 5000]
links = np.array([k + 1 for k in ks])
obs = np.array([gk[("Indirect", k, True)] /
                (gk[("Indirect", k, True)] + gk.get(("Indirect", k, False), 0)) for k in ks])
fig, ax = plt.subplots(figsize=(9.0, 4.8))
xx = np.linspace(1, links.max(), 200)
ax.plot(xx, 100 * (1 - (1 - p) ** xx), color=S.C_WARN, lw=2.4,
        label=f"5% chance per link  (p = {p:.1%})")
ax.scatter(links, obs * 100, s=70, color=S.C_ACCENT, zorder=3, label="Measured in the data")
for lk, ob in zip(links, obs * 100):
    ax.annotate(f"{ob:.1f}%", xy=(lk, ob), xytext=(0, 8), textcoords="offset points",
                ha="center", fontsize=9, color=S.C_ACCENT)
S.clean(ax)
S.title(ax, "Each extra link adds a ~5% chance of hiding a bank",
        "Every route length follows the same per-link coin flip (red line).")
ax.set_xlabel("Links in the route (banks minus one)")
ax.set_ylabel("Payments showing a hidden bank (\"...\")")
ax.set_xlim(0.7, links.max() + 0.5)
ax.set_ylim(0, 100 * obs.max() * 1.15)
S.pct_axis(ax, "y", step=5, xmax=100)
S.legend_below(ax, ncol=2, y=-0.18)
savefig(fig, "routing_2_gap_per_hop.png", group=GROUP)

# ------------------------------------------------------------------ 3. conversion rule, hold-out
in_ok, in_tot, ho_ok, ho_tot = A["score"]
vals = [100 * in_ok / in_tot, 100 * ho_ok / ho_tot]
fig, ax = plt.subplots(figsize=(7.4, 4.6))
labels = [f"Training half\n(rule built here)\n{in_tot:,} rows",
          f"Test half\n(never seen)\n{ho_tot:,} rows"]
bars = ax.bar(labels, vals, color=[S.C_GREY, S.C_ACCENT], width=0.5)
for bar, v in zip(bars, vals):
    ax.annotate(f"{v:.2f}%", xy=(bar.get_x() + bar.get_width() / 2, v), xytext=(0, 4),
                textcoords="offset points", ha="center", va="bottom",
                fontsize=13, fontweight="bold")
S.clean(ax)
S.title(ax, "The FX rule is right on data it never saw",
        "Share of payments where the conversion count is predicted exactly. "
        "The axis starts at 99.5% to show the tiny difference.")
ax.set_xlabel("Half of the data")
ax.set_ylabel("Conversion count predicted exactly")
ax.set_ylim(99.5, 100.02)
ax.set_yticks([99.5, 99.7, 99.9, 100.0])
ax.set_yticklabels(["99.5%", "99.7%", "99.9%", "100%"])
savefig(fig, "routing_3_conversion_holdout.png", group=GROUP)

# ------------------------------------------------------------------ 4. the two bank columns
m = A["mism"]
tc = A["type_counts"]
fig, ax = plt.subplots(figsize=(9.5, 4.8))
x = np.arange(len(TYPES))
w = 0.36
f = [100 * m.get((t, "f"), 0) / tc[t] for t in TYPES]
l = [100 * m.get((t, "l"), 0) / tc[t] for t in TYPES]
b1 = ax.bar(x - w / 2, f, w, color=S.C_ACCENT, label="Route starts at a different bank")
b2 = ax.bar(x + w / 2, l, w, color="#dd6b20", label="Route ends at a different bank")
S.vlabels(ax, b1, [f"{v:.2f}%" for v in f])
S.vlabels(ax, b2, [f"{v:.2f}%" for v in l])
S.clean(ax)
S.title(ax, "The two bank columns are wrong about 5% of the time",
        "Each end is wrong independently; both ends together happen 0.25% of the time, "
        "exactly as chance predicts.")
ax.set_xlabel("Routing label")
ax.set_ylabel("Share of payments")
ax.set_xticks(x)
ax.set_xticklabels(TYPES)
ax.set_ylim(0, 6.2)
S.pct_axis(ax, "y", step=1, xmax=100)
S.legend_below(ax, ncol=2, y=-0.18)
savefig(fig, "routing_5_mismatch.png", group=GROUP)

# ------------------------------------------------------------------ 5. countries as middlemen
til = A["tilts"]
sel = [c for c, _ in sorted(til.items(), key=lambda kv: -kv[1])[:10]]
vals = [til[c] for c in sel]
fig, ax = plt.subplots(figsize=(9.0, 4.8))
y = np.arange(len(sel))[::-1]
bars = ax.barh(y, vals, color=S.C_ACCENT, height=0.62)
ax.set_yticks(y)
ax.set_yticklabels(sel)
S.clean(ax, grid="x")
S.title(ax, "Some countries act as middlemen far more than their traffic explains",
        "Middle-of-route share divided by start/end share. 1.0 = no preference.")
ax.set_xlabel("Middleman ratio (1.0 = used as a middle exactly as often as at the ends)")
ax.set_ylabel("Country")
ax.set_xlim(0, max(vals) * 1.18)
ax.set_xticks([0, 0.5, 1.0, 1.5])
S.baseline(ax, 1.0, "no preference", axis="x")
S.hlabels(ax, bars, [f"{v:.2f}" for v in vals])
savefig(fig, "routing_7_hub_tilt.png", group=GROUP)

print("done g5 charts")
