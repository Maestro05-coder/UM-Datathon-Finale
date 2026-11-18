"""g8 charts - simple, one idea per picture, from full-data DuckDB over cache_party.

Every number is exact (all 10,000,000 rows); no sampling.
Run:  python analysis/g8_charts.py      Charts land in groups/g8_anomalies/.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ddb, full_glob, PARTY_CACHE, savefig

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import _style as S

S.apply()
GROUP = "g8_anomalies"
con = ddb()
PG = full_glob(PARTY_CACHE)
SEC = 86400

PRETTY = {
    "ROMANCE_SCAM": "Romance scam",
    "CEO_SCAM": "CEO scam",
    "ACCOUNT_REPLACEMENT_SCAM": "Account replacement",
    "DUPLICATE_PAYMENT": "Duplicate payment",
    "FAT_FINGER_MISTAKE": "Fat finger",
    "CUSTOMER_RECALL": "Customer recall",
    "clean": "Normal payment",
}


def q(sql):
    return con.execute(sql).df()


# ------------------------------------------------------------------ 1. amount profile
print("1. amount by label")
am = q(f"""
    SELECT CASE WHEN ANOMALY_TYPE IS NULL THEN 'clean' ELSE ANOMALY_TYPE END grp,
           COUNT(*) n, MEDIAN(USD_AMOUNT) med, QUANTILE_CONT(USD_AMOUNT, 0.9) p90
    FROM read_parquet('{PG}') GROUP BY 1
""")
am["label"] = am.grp.map(PRETTY)
am = am.sort_values("med").reset_index(drop=True)
print(am.round(0).to_string(index=False))

fig, ax = plt.subplots(figsize=(11.0, 5.2))
y = np.arange(len(am))
for i, r in am.iterrows():
    ax.plot([r.med, r.p90], [i, i], color=S.C_GREY_SOFT, lw=5,
            solid_capstyle="round", zorder=1)
    ax.scatter(r.med, i, s=90, color=S.C_GREY if r.grp == "clean" else S.C_ACCENT,
               zorder=3, edgecolor="white", linewidth=1.2)
    ax.scatter(r.p90, i, s=60, color="white",
               edgecolor=S.C_GREY if r.grp == "clean" else S.C_ACCENT,
               linewidth=1.6, zorder=3)
    ax.annotate(S.money(r.med), xy=(r.med, i), xytext=(-7, 0),
                textcoords="offset points", ha="right", va="center",
                fontsize=9.5, color=S.C_TEXT)
    ax.annotate(S.money(r.p90), xy=(r.p90, i), xytext=(7, 0),
                textcoords="offset points", ha="left", va="center",
                fontsize=9.5, color=S.C_MUTED)

ax.set_xscale("log")
ax.set_yticks(y)
ax.set_yticklabels(am.label)
ax.set_ylim(-0.7, len(am) - 0.3)
ax.set_xlim(20, 3e8)
ax.set_xticks([10, 1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8])
ax.set_xticklabels(["$10", "$100", "$1k", "$10k", "$100k", "$1M", "$10M", "$100M"])
S.clean(ax, grid="x")
S.title(ax, "Fat fingers and CEO scams dwarf normal payments",
        "Each line runs from the label's median payment (filled dot) to its 90th percentile (hollow dot).")
ax.set_xlabel("Payment amount (USD, log scale)")

from matplotlib.lines import Line2D
handles = [Line2D([], [], marker="o", ls="", color=S.C_ACCENT, markersize=8,
                  label="Median payment (typical)"),
           Line2D([], [], marker="o", ls="", markerfacecolor="white",
                  markeredgecolor=S.C_ACCENT, markersize=7,
                  label="90th percentile (1 in 10 is larger)")]
S.legend_below(ax, ncol=2, handles=handles, y=-0.14)
savefig(fig, "g8_label_amounts.png", group=GROUP)

# ------------------------------------------------------------------ 2. fat finger
print("\n2. fat finger deviation from the sender's own amounts")
q(f"""
    CREATE OR REPLACE TEMP TABLE sbase AS
    SELECT ORDERING_ACCOUNT AS oa, QUANTILE_CONT(USD_AMOUNT, 0.5) AS med_amt
    FROM read_parquet('{PG}')
    WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0 AND ORDERING_ACCOUNT IS NOT NULL
    GROUP BY 1 HAVING COUNT(*) >= 5
""")
ff = q(f"""
    WITH t AS (
      SELECT CASE WHEN a.ANOMALY_TYPE IS NULL THEN 'clean' ELSE 'fat_finger' END grp,
             LEAST(FLOOR(ABS(LOG10(a.USD_AMOUNT / b.med_amt)) * 2), 10) AS b
      FROM read_parquet('{PG}') a JOIN sbase b ON a.ORDERING_ACCOUNT = b.oa
      WHERE a.USD_AMOUNT > 0 AND (a.ANOMALY_TYPE IS NULL OR a.ANOMALY_TYPE = 'FAT_FINGER_MISTAKE'))
    SELECT grp, b, COUNT(*) n, 100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY grp) pct
    FROM t GROUP BY 1, 2 ORDER BY 1, 2
""")
print(ff.pivot(index="b", columns="grp", values=["n", "pct"]).round(2).to_string())

bins = np.arange(11)
fig, ax = plt.subplots(figsize=(10.0, 4.8))
w = 0.4
for i, (grp, col, name) in enumerate([
        ("clean", S.C_GREY, "Normal payments (exact)"),
        ("fat_finger", "#dd6b20", "Fat-finger payments (exact)")]):
    sub = ff[ff.grp == grp].set_index("b").reindex(bins).fillna(0)
    x = bins + (i - 0.5) * w
    ax.bar(x, sub.pct, w, color=col, label=name)
S.clean(ax)
S.title(ax, "A fat finger is far outside the sender's normal amounts",
        "How many orders of magnitude a payment is from the same sender's median amount.")
ax.set_xlabel("Distance from the sender's own median amount (orders of magnitude; 2 = 100x)")
ax.set_ylabel("Share of that group's payments")
ax.set_xticks(bins)
ax.set_xticklabels([f"{b/2:.1f}" if b < 10 else "5+" for b in bins])
ax.set_ylim(0, 45)
S.pct_axis(ax, "y", step=10, xmax=100)
S.legend_below(ax, ncol=2, y=-0.20)
savefig(fig, "g8_fatfinger_dev.png", group=GROUP)

# ---- the decisive chart: a decimal shift should bring the row back into the
# normal range.  Compare with the same test on clean rows (control).
print("\n2b. decimal-shift fingerprint")
sh = q(f"""
    WITH sbase AS (
      SELECT ORDERING_ACCOUNT oa, QUANTILE_CONT(USD_AMOUNT, 0.25) q25,
             QUANTILE_CONT(USD_AMOUNT, 0.75) q75
      FROM read_parquet('{PG}')
      WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0 AND ORDERING_ACCOUNT IS NOT NULL
      GROUP BY 1 HAVING COUNT(*) >= 5
    )
    SELECT CASE WHEN a.ANOMALY_TYPE = 'FAT_FINGER_MISTAKE' THEN 'fat_finger' ELSE 'clean' END grp,
           COUNT(*) n,
           AVG(CASE WHEN a.USD_AMOUNT       BETWEEN b.q25 AND b.q75 THEN 1.0 ELSE 0 END) d1,
           AVG(CASE WHEN a.USD_AMOUNT / 1e1 BETWEEN b.q25 AND b.q75 THEN 1.0 ELSE 0 END) d10,
           AVG(CASE WHEN a.USD_AMOUNT / 1e2 BETWEEN b.q25 AND b.q75 THEN 1.0 ELSE 0 END) d100,
           AVG(CASE WHEN a.USD_AMOUNT / 1e3 BETWEEN b.q25 AND b.q75 THEN 1.0 ELSE 0 END) d1000,
           AVG(CASE WHEN a.USD_AMOUNT / 1e4 BETWEEN b.q25 AND b.q75 THEN 1.0 ELSE 0 END) d10000
    FROM read_parquet('{PG}') a JOIN sbase b ON a.ORDERING_ACCOUNT = b.oa
    WHERE a.USD_AMOUNT > 0 AND (a.ANOMALY_TYPE IS NULL OR a.ANOMALY_TYPE = 'FAT_FINGER_MISTAKE')
    GROUP BY 1
""")
print(sh.round(4).to_string(index=False))
cols = ["d1", "d10", "d100", "d1000", "d10000"]
labels = ["divide by 1\n(no shift)", "divide by 10", "divide by 100",
          "divide by 1,000", "divide by 10,000"]
x = np.arange(len(cols))
w = 0.40
fig, ax = plt.subplots(figsize=(10.2, 5.0))
for i, (grp, col, name) in enumerate([("clean", S.C_GREY, "Normal payments (exact)"),
                                      ("fat_finger", "#dd6b20", "Fat-finger payments (exact)")]):
    vals = sh[sh.grp == grp][cols].iloc[0].to_numpy(dtype=float)
    bars = ax.bar(x + (i - 0.5) * w, vals, w, color=col, label=name)
    S.vlabels(ax, bars, [f"{v:.1%}" for v in vals], fontsize=9)
S.clean(ax)
S.title(ax, "A fat finger is a normal amount with its decimal point moved",
        "Share of payments that land inside the same sender's middle 50% of amounts "
        "after dividing by 1, 10, 100, 1,000 or 10,000.")
ax.set_xlabel("Divide the payment amount by ...")
ax.set_ylabel("Share inside the sender's normal range")
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=9.5)
ax.set_ylim(0, 0.64)
S.pct_axis(ax, "y", step=0.1)
S.legend_below(ax, ncol=2, y=-0.24)
savefig(fig, "g8_fatfinger_shift.png", group=GROUP)

# ------------------------------------------------------------------ 3. duplicate timing
print("\n3. gap between two identical payments")
q(f"""
    CREATE OR REPLACE TEMP TABLE gaps AS
    SELECT ANOMALY_TYPE, EPOCH_SECONDS - LAG(EPOCH_SECONDS) OVER w AS gap
    FROM read_parquet('{PG}')
    WHERE ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL
      AND USD_AMOUNT IS NOT NULL AND USD_AMOUNT > 0
    WINDOW w AS (PARTITION BY ORDERING_ACCOUNT, BENEFICIARY_ACCOUNT, USD_AMOUNT
                 ORDER BY EPOCH_SECONDS)
""")
ga = q(f"""
    WITH t AS (
      SELECT CASE WHEN ANOMALY_TYPE = 'DUPLICATE_PAYMENT' THEN 'duplicate'
                  WHEN ANOMALY_TYPE IS NULL THEN 'clean' END grp,
             CASE WHEN gap < 120 THEN 'under 2 min'
                  WHEN gap < 600 THEN '2-10 min'
                  WHEN gap < 1800 THEN '10-30 min'
                  WHEN gap < 3600 THEN '30-60 min'
                  WHEN gap < 21600 THEN '1-6 hours'
                  WHEN gap < 86400 THEN '6-24 hours'
                  WHEN gap < 259200 THEN '1-3 days'
                  ELSE '3-90 days' END AS bucket,
             gap
      FROM gaps WHERE gap IS NOT NULL AND gap >= 0 AND gap < 90 * {SEC}
    )
    SELECT grp, bucket, COUNT(*) n, 100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY grp) pct
    FROM t WHERE grp IS NOT NULL GROUP BY 1, 2
""")
order = ["under 2 min", "2-10 min", "10-30 min", "30-60 min",
         "1-6 hours", "6-24 hours", "1-3 days", "3-90 days"]
print(ga.pivot(index="bucket", columns="grp", values="pct").reindex(order).round(1).to_string())
print("median gap (all pairs):", q(f"""
    SELECT CASE WHEN ANOMALY_TYPE = 'DUPLICATE_PAYMENT' THEN 'duplicate'
                WHEN ANOMALY_TYPE IS NULL THEN 'clean' END grp,
           MEDIAN(gap) med_s
    FROM gaps WHERE gap IS NOT NULL AND gap >= 0 AND gap < 90 * {SEC}
      AND (ANOMALY_TYPE IS NULL OR ANOMALY_TYPE = 'DUPLICATE_PAYMENT') GROUP BY 1""")
      .set_index("grp").med_s.round(0).to_dict())

fig, ax = plt.subplots(figsize=(10.5, 4.8))
x = np.arange(len(order))
w = 0.4
for i, (grp, col, name) in enumerate([("duplicate", "#dd6b20", "Duplicate payments"),
                                      ("clean", S.C_GREY, "Normal repeat pairs")]):
    sub = ga[ga.grp == grp].set_index("bucket").reindex(order).fillna(0)
    bars = ax.bar(x + (i - 0.5) * w, sub.pct, w, color=col, label=name)
    S.vlabels(ax, bars, [f"{v:.0f}%" if v >= 1 else "" for v in sub.pct],
              fontsize=8.5, dy=2)
S.clean(ax)
S.title(ax, "Duplicates follow their own clock: minutes, not days",
        "Time between two identical payments (same sender, beneficiary and amount).")
ax.set_xlabel("Time between the two identical payments")
ax.set_ylabel("Share of that group's repeat pairs")
ax.set_xticks(x)
ax.set_xticklabels(order, rotation=18, ha="right")
ax.set_ylim(0, 82)
S.pct_axis(ax, "y", step=20, xmax=100)
S.legend_below(ax, ncol=2, y=-0.32)
savefig(fig, "g8_repeat_gaps.png", group=GROUP)

# ------------------------------------------------------------------ 4. romance escalation
print("\n4. romance-scam escalation")
rn = q(f"""
    WITH cc AS (
      SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, EPOCH_SECONDS ts, USD_AMOUNT amt
      FROM read_parquet('{PG}')
      WHERE ANOMALY_TYPE = 'ROMANCE_SCAM'
        AND ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL),
     seq AS (
      SELECT ROW_NUMBER() OVER (PARTITION BY oa, ba ORDER BY ts) AS i, amt FROM cc)
    SELECT i, COUNT(*) n, MEDIAN(amt) med_amt
    FROM seq WHERE i <= 8 GROUP BY i ORDER BY i
""")
print(rn.round(1).to_string(index=False))

fig, ax = plt.subplots(figsize=(9.4, 4.8))
bars = ax.bar(rn.i.astype(int).astype(str), rn.med_amt, color="#dd6b20", width=0.62)
S.vlabels(ax, bars, [S.money(v) for v in rn.med_amt])
S.clean(ax)
S.title(ax, "Romance scams escalate: small first asks, big last asks",
        "Median payment size by position in the burst (same victim, same beneficiary).")
ax.set_xlabel("Payment number inside the burst  (n = number of bursts reaching that step)")
ax.set_ylabel("Median payment amount (USD)")
ax.set_xticks(rn.i.astype(int).astype(str))
ax.set_xticklabels([f"{i}\nn={n}" for i, n in zip(rn.i.astype(int), rn.n)],
                   fontsize=9.5)
top = rn.med_amt.max()
ax.set_ylim(0, top * 1.18)
ax.set_yticks(np.arange(0, top * 1.15, 500))
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: S.money(v)))
savefig(fig, "g8_romance_escalation.png", group=GROUP)

print("\nDONE g8 charts")
