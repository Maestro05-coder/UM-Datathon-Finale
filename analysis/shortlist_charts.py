"""Charts for the two shortlist rules that had no picture yet.

Both come from cached full-data aggregates (agg/*.pkl) - no CSV access.
Run:  python analysis/shortlist_charts.py
Charts land in groups/g5_routing/ and groups/g2_currency/.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import savefig

import pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import _style as S

S.apply()
AGG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agg")

# ------------------------------------------------------------------ 1. g5: fraud avoids Covered
A = pickle.load(open(os.path.join(AGG, "g5_agg.pkl"), "rb"))
anom = A["anom"]


def covered_share(label):
    """Covered share among MULTI-BANK rows with this label (Covered needs 3+ banks)."""
    covered = anom.get((label, "Covered"), 0)
    multi = covered + anom.get((label, "Indirect"), 0)
    return 100 * covered / multi, multi


clean_c = anom[("", "Covered")]
clean_m = clean_c + anom[("", "Indirect")]
clean_share = 100 * clean_c / clean_m
rows = [
    ("Clean baseline", clean_share, clean_m, S.C_GREY),
    ("FAT_FINGER (mistake)", *covered_share("FAT_FINGER_MISTAKE"), S.C_ACCENT),
    ("DUPLICATE (mistake)", *covered_share("DUPLICATE_PAYMENT"), S.C_ACCENT),
    ("RECALL (mistake)", *covered_share("CUSTOMER_RECALL"), S.C_ACCENT),
    ("CEO_SCAM (fraud)", *covered_share("CEO_SCAM"), S.C_WARN),
    ("REPLACEMENT (fraud)", *covered_share("ACCOUNT_REPLACEMENT_SCAM"), S.C_WARN),
    ("ROMANCE (fraud)", *covered_share("ROMANCE_SCAM"), S.C_WARN),
]

fig, ax = plt.subplots(figsize=(9.5, 5.0))
ys = np.arange(len(rows))[::-1]
for y, (label, share, n, color) in zip(ys, rows):
    ax.barh(y, share, color=color, height=0.62)
    ax.annotate(f"{share:.1f}%   (n = {n:,})", xy=(share, y), xytext=(6, 0),
                textcoords="offset points", va="center", fontsize=10, color=S.C_TEXT)
S.clean(ax, grid="x")
S.title(ax, "Fraud avoids the Covered route; mistakes don't",
        "Covered share among multi-bank payments, per anomaly label. The three mistake "
        "labels sit at the clean rate; the three fraud labels collapse to ~0-2%.")
S.baseline(ax, clean_share, axis="x", label=f"clean {clean_share:.1f}%")
ax.set_yticks(ys)
ax.set_yticklabels([r[0] for r in rows])
ax.set_xlabel("Payments routed as Covered")
ax.set_xlim(0, 17.5)
S.pct_axis(ax, "x", xmax=100)
ax.set_ylim(-0.6, len(rows) - 0.4)
S.legend_below(ax, ncol=3, y=-0.24, handles=[
    Patch(facecolor=S.C_GREY, label="Clean baseline"),
    Patch(facecolor=S.C_ACCENT, label="Mistake labels"),
    Patch(facecolor=S.C_WARN, label="Fraud labels"),
])
savefig(fig, "routing_8_fraud_covered.png", group="g5_routing")

# ------------------------------------------------------------------ 2. g2: no FX-rate table
D = pd.read_pickle(os.path.join(AGG, "_g2_no_rate_deltas.pkl"))
med = D.delta.median()
n_far = int((D.delta.abs() > 0.03).sum())

rng = np.random.default_rng(7)
y = rng.uniform(-0.30, 0.30, len(D))
fig, ax = plt.subplots(figsize=(9.5, 4.3))
for x0, x1 in ((-0.15, -0.03), (0.03, 0.20)):
    ax.axvspan(x0, x1, color=S.C_WARN, alpha=0.08, zorder=0)
ax.scatter(D.delta, y, s=55, color=S.C_ACCENT, alpha=0.85,
           edgecolor="white", linewidth=0.6, zorder=3)
S.baseline(ax, med, axis="x", label=f"measured median {med:+.3f} dex")
ax.annotate("a real FX-rate table would force \u00b10.03\u20131.9 dex",
            xy=(0.06, 0.42), xytext=(0.085, 0.53), fontsize=10, color=S.C_WARN,
            va="center",
            arrowprops=dict(arrowstyle="-", color=S.C_WARN, lw=1.0))
S.clean(ax)
ax.set_yticks([])
ax.set_ylim(-0.62, 0.72)
ax.set_xlim(-0.15, 0.20)
ax.set_xlabel("log10 amount gap: foreign-currency vs home-currency payments (dex)\n"
              "each dot = one (sender country, currency) cell")
# two-line subtitle needs more headroom than S.title's fixed pad -> do it by hand
ax.set_title("No FX-rate table: foreign-currency payments sit at the home-currency level",
             loc="left", pad=56, color=S.C_TEXT)
ax.annotate(f"Held-country amount gap, foreign vs home currency \u2014 63 country\u00d7currency "
            f"cells, 457,972 rows.\nMedian {med:+.3f} dex (median |gap| 0.017); only {n_far} "
            f"of 63 cells even cross \u00b10.03 dex, where a real table would begin.",
            xy=(0, 1), xycoords="axes fraction", xytext=(0, 10),
            textcoords="offset points", ha="left", va="bottom",
            fontsize=10.5, color=S.C_MUTED, linespacing=1.45)
savefig(fig, "g2_5_no_fx.png", group="g2_currency")
