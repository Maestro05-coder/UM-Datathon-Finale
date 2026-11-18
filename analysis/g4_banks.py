"""g4 - Banks & countries. Full-data DuckDB over cache_full.

The RULES (mechanisms):
  R1  BIC8 is a fixed 8-slot layout: 4 numeric bank digits (1,075 distinct values
      for 8,727 banks), the 2-char country, a per-country house letter (25 values,
      constant within all 229 countries, shared across countries), and a constant
      '0'. 0 exceptions in 25,815,715 appearances.
  R2  ORDERING_TYPE/BENEFICIARY_TYPE are only ever 'B' or 'C' (0 A/D rows in 10M).
      B (business) pays +0.865 dex (7.3x) more than C at every income level
      (167 countries, sd 0.100); the offset is additive, so country and type are
      separate dials (ladder spans 2.889 dex in C, 2.856 dex in B).
  R3  banks have their own stable amount tilts (split-half corr 0.93), partly
      explained by client-type mix (corr with share_C = -0.58).

The supporting FACTS (censuses, not rules):
  F1  8,727 banks across 229 country codes; bank count scales with traffic
      (corr 0.94) but the pool size is country-specific (US 1,016 banks vs
      IM 12 banks for 545k rows).
  F2  roles: every bank appears at least once as an endpoint; 45 banks are
      pure intermediaries (never an endpoint). Every bank can serve as middle.
  F3  dominant-bank concentration per country varies hugely: median top-bank
      share 52.2%, US the most fragmented (top bank 4.4% of 979).
  F4  24,017 sender->beneficiary country corridors; reciprocity is weak
      (median |n_ab - n_ba|/(n_ab + n_ba) = 0.114).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ddb, full_glob, savefig
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import _style as S
from matplotlib.patches import Patch
S.apply()

con = ddb()
G = full_glob()
AGG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agg")
GROUP = "g4_banks"

# ---------------------------------------------------------------- 1. census
print("=== 1. bank census ===")
r = con.execute(f"""
    WITH app AS (
      SELECT CASE WHEN x != '...' THEN x END bank FROM (
        SELECT unnest(string_split(BIC8_PATH, ';')) x FROM read_parquet('{G}')
      ) WHERE bank IS NOT NULL AND bank != '...' AND bank != ''
    )
    SELECT upper(substr(bank,5,2)) ctry, COUNT(DISTINCT bank) n_banks, COUNT(*) n_app
    FROM app GROUP BY 1 ORDER BY n_app DESC
""").df()
print("countries in paths:", len(r), "| total bank appearances:", int(r.n_app.sum()))
print("banks per country: max %d (US)  median %.0f  min %d" % (
    r.n_banks.max(), r.n_banks.median(), r.n_banks.min()))
corr_raw = float(np.corrcoef(r.n_app, r.n_banks)[0, 1])
corr_log = float(np.corrcoef(np.log10(r.n_app), np.log10(r.n_banks))[0, 1])
print("corr(rows, banks) raw = %.3f | on logs = %.3f" % (corr_raw, corr_log))
im_banks = float(r[r.ctry == "IM"].n_banks.iloc[0])
fi_banks = float(r[r.ctry == "FI"].n_banks.iloc[0])
small_pool = r[(r.n_app > 200000) & (r.n_banks < 40)][["ctry","n_banks","n_app"]]
print("small-pool outliers (rows>200k, banks<40):")
print(small_pool.to_string(index=False))
r.to_pickle(os.path.join(AGG, "_g4_ctry_banks.pkl"))

fig, ax = plt.subplots(figsize=(9.5, 5.2))
ax.scatter(r.n_app, r.n_banks, s=22, alpha=0.55, color=S.C_ACCENT, linewidths=0)
for ctry, dx, dy in [("US", -34, 6), ("GB", -4, 10), ("CH", 10, -2),
                     ("IM", 9, 2), ("FI", 9, 2), ("BE", 10, -4)]:
    row = r[r.ctry == ctry]
    if len(row):
        ax.annotate(ctry, (row.n_app.iloc[0], row.n_banks.iloc[0]),
                    xytext=(dx, dy), textcoords="offset points",
                    fontsize=9.5, color=S.C_MUTED)
ax.set_xscale("log"); ax.set_yscale("log")
S.clean(ax, grid="both")
S.title(ax, "Busier countries have more banks - up to a country-specific cap",
        f"One dot per country: bank appearances (x) vs distinct banks (y); r = {corr_raw:.2f}. "
        f"Isle of Man runs {im_banks:.0f} banks, Finland {fi_banks:.0f}.")
ax.set_xlabel("Bank appearances in payment routes (log scale)")
ax.set_ylabel("Distinct banks (log scale)")
ax.set_xlim(0.7, r.n_app.max() * 3)
savefig(fig, "g4_1_bank_census.png", group=GROUP)

# ---------------------------------------------------------------- 2. roles
print("\n=== 2. bank roles (endpoints vs middle) ===")
r = con.execute(f"""
    WITH p AS (
      SELECT split_part(BIC8_PATH,';',1) f, split_part(BIC8_PATH,';',-1) l, BIC8_PATH
      FROM read_parquet('{G}') WHERE gap_head = FALSE AND gap_tail = FALSE
    ),
    mid AS (
      SELECT CASE WHEN x != '...' THEN x END bank FROM (
        SELECT unnest(string_split(BIC8_PATH, ';')) x FROM p
      ) WHERE bank IS NOT NULL AND bank != '...' AND bank != ''
    ),
    ends AS (SELECT f bank FROM p UNION ALL SELECT l FROM p),
    st AS (
      SELECT bank,
             SUM(CASE WHEN pos = 'm' THEN 1 ELSE 0 END) nm,
             SUM(CASE WHEN pos = 'e' THEN 1 ELSE 0 END) ne
      FROM (
        SELECT bank, 'm' pos FROM mid
        UNION ALL SELECT bank, 'e' pos FROM ends
      ) GROUP BY 1
    )
    SELECT bank, nm, ne FROM st
""").df()
print("banks:", len(r), "| endpoint-only (nm=0):", int((r["nm"] == 0).sum()),
      "| middle-only (ne=0):", int((r["ne"] == 0).sum()),
      "| avg middle share: %.3f" % (r["nm"].sum() / (r["nm"] + r["ne"]).sum()))
top = r.sort_values("nm", ascending=False).head(10).iloc[::-1]
print("top middle banks:")
print(top.iloc[::-1].round(0).to_string(index=False))
fig, ax = plt.subplots(figsize=(9.5, 5.0))
bars = ax.barh(top.bank, top.nm, color=S.C_ACCENT, height=0.7)
S.clean(ax, grid="x")
S.title(ax, "The busiest banks are pure middlemen",
        f"{int((r['ne'] == 0).sum())} of {len(r):,} banks only ever appear as a middle hop - never as a sender or beneficiary bank.")
ax.set_xlabel("Visible middle-hop appearances")
ax.set_ylabel("Bank (BIC8 code)")
ax.set_xlim(0, top.nm.max() * 1.22)
S.count_axis(ax, "x")
S.hlabels(ax, bars, [f"{v:,.0f}" for v in top.nm])
savefig(fig, "g4_2_intermediaries.png", group=GROUP)

# ---------------------------------------------------------------- 3. concentration + corridors
print("\n=== 3. dominant bank per country ===")
r = con.execute(f"""
    WITH fb AS (
      SELECT split_part(BIC8_PATH,';',1) bank, COUNT(*) n
      FROM read_parquet('{G}') WHERE gap_head = FALSE GROUP BY 1
    )
    SELECT upper(substr(bank,5,2)) ctry, bank, n,
           n * 1.0 / SUM(n) OVER (PARTITION BY upper(substr(bank,5,2))) p,
           ROW_NUMBER() OVER (PARTITION BY upper(substr(bank,5,2)) ORDER BY n DESC) rn,
           COUNT(*) OVER (PARTITION BY upper(substr(bank,5,2))) n_banks
    FROM fb
""").df()
topb = r[r.rn == 1]
print("countries:", len(topb))
print("top-bank share: min %.3f  median %.3f  max %.3f" % (topb.p.min(), topb.p.median(), topb.p.max()))
print("most fragmented:", topb.sort_values("p").head(4)[["ctry","bank","n","p","n_banks"]].round(3).to_string(index=False))
print("most concentrated:", topb.sort_values("p").tail(3)[["ctry","bank","n","p"]].round(3).to_string(index=False))

print("\ncorridors + reciprocity:")
r = con.execute(f"""
    SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) a,
           upper(substr(split_part(BIC8_PATH,';',-1),5,2)) b, COUNT(*) n
    FROM read_parquet('{G}') WHERE gap_head = FALSE AND gap_tail = FALSE
    GROUP BY 1,2
""").df()
print("distinct corridors:", len(r))
print("top 8:")
print(r.sort_values("n", ascending=False).head(8).to_string(index=False))
m = r.merge(r.rename(columns={"a":"a2","b":"b2","n":"n2"}), left_on=["a","b"], right_on=["b2","a2"])
m = m[m.a <= m.b]
m["sym"] = (m.n - m.n2).abs() / (m.n + m.n2)
big = m[(m.n + m.n2) >= 5000]
print("pairs (sum>=5000): %d | reciprocity asymmetry: median %.3f  p90 %.3f" % (
    len(big), big.sym.median(), big.sym.quantile(.9)))
r.sort_values("n", ascending=False).head(20).to_pickle(os.path.join(AGG, "_g4_corridors.pkl"))
n_corr = len(r)

# 3a. the biggest country-to-country flows
t = r.sort_values("n", ascending=False).head(12).iloc[::-1]
fig, ax = plt.subplots(figsize=(9.5, 5.4))
bars = ax.barh([f"{aa} -> {bb}" for aa, bb in zip(t.a, t.b)], t.n, color=S.C_ACCENT, height=0.7)
S.clean(ax, grid="x")
S.title(ax, "The 12 biggest sender -> beneficiary country flows",
        f"Of {n_corr:,} country pairs, domestic US -> US is by far the largest "
        f"({int(t.n.max()):,} payments).")
ax.set_xlabel("Payments")
ax.set_ylabel("Sender country -> beneficiary country")
ax.set_xlim(0, t.n.max() * 1.22)
S.count_axis(ax, "x")
S.hlabels(ax, bars, [f"{v:,.0f}" for v in t.n])
savefig(fig, "g4_3_top_corridors.png", group=GROUP)

# 3b. are the two directions of a pair balanced? (no)
med_sym = float(big.sym.median())
fig, ax = plt.subplots(figsize=(9.5, 4.8))
ax.hist(big.sym, bins=40, color=S.C_ACCENT)
ax.axvline(med_sym, color=S.C_WARN, ls="--", lw=1.6)
ax.annotate(f"median {med_sym:.2f}", xy=(med_sym, 0.88), xycoords=("data", "axes fraction"),
            xytext=(6, 0), textcoords="offset points", color=S.C_WARN, fontsize=10.5, va="center")
S.clean(ax)
S.title(ax, "Country flows are not balanced in both directions",
        f"The two directions of each country pair differ by a median {med_sym:.0%}; "
        "a balanced generator would pile up at 0.")
ax.set_xlabel("Lopsidedness of a country pair (0 = equal both ways, 1 = one-way only)")
ax.set_ylabel("Number of country pairs")
ax.set_xlim(0, 1)
savefig(fig, "g4_4_reciprocity.png", group=GROUP)

# ---------------------------------------------------------------- 4. types (B/C only)
print("\n=== 4. ORDERING_TYPE / BENEFICIARY_TYPE: only B and C exist ===")
tc = con.execute(f"""
    SELECT ORDERING_TYPE ot, BENEFICIARY_TYPE bt, COUNT(*) n, MEDIAN(log10(USD_AMOUNT)) m
    FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
    GROUP BY 1,2 ORDER BY n DESC
""").df()
print(tc.round(3).to_string(index=False))
r = con.execute(f"""
    SELECT ORDERING_TYPE ot, BENEFICIARY_TYPE bt, COUNT(*) n
    FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NOT NULL
    GROUP BY 1,2 ORDER BY n DESC
""").df()
print("anomalous rows:", r.to_string(index=False))
print("within-country B-vs-C offset:")
for c in ["US", "DE", "IN", "MC"]:
    rr = con.execute(f"""
        SELECT ORDERING_TYPE ot, MEDIAN(log10(USD_AMOUNT)) m
        FROM read_parquet('{G}')
        WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
          AND upper(substr(split_part(BIC8_PATH,';',1),5,2)) = '{c}'
        GROUP BY 1 ORDER BY 1
    """).df()
    d = dict(zip(rr.ot, rr.m))
    print(f"  {c}: B {d['B']:.3f}  C {d['C']:.3f}  offset {d['B']-d['C']:+.3f} dex")
print("country ladder survives within type (mu range within each type):")
r = con.execute(f"""
    SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc, ORDERING_TYPE ot,
           MEDIAN(log10(USD_AMOUNT)) m
    FROM read_parquet('{G}')
    WHERE gap_head = FALSE AND ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
    GROUP BY 1,2 HAVING COUNT(*) >= 300
""").df()
for t in ["B", "C"]:
    s = r[r.ot == t]
    print(f"  type {t}: {len(s)} countries, mu {s.m.min():.3f} .. {s.m.max():.3f} (spread {s.m.max()-s.m.min():.3f})")

fig, ax = plt.subplots(figsize=(9.5, 5.2))
lbl = ["B -> B", "B -> C", "C -> B", "C -> C"]
tc2 = tc.set_index(["ot", "bt"])
pairs = [("B", "B"), ("B", "C"), ("C", "B"), ("C", "C")]
vals = [int(tc2.loc[p, "n"]) for p in pairs]
meds = [10 ** tc2.loc[p, "m"] for p in pairs]
base = meds[-1]                       # person -> person is the yardstick
mult = [v / base for v in meds]
bars = ax.bar(lbl, mult, color=S.C_ACCENT, width=0.62)
S.vlabels(ax, bars, [f"${m:,.0f}\n({v:.0f}\u00d7)" for m, v in zip(meds, mult)], fontsize=9.5)
S.clean(ax)
S.title(ax, "Both ends of a payment decide its size",
        "Median payment in USD. The bar is how many times a person-to-person payment it is.")
ax.set_xlabel("Sender type -> beneficiary type   (B = business, C = person)")
ax.set_ylabel("Median payment vs person-to-person (C -> C = 1\u00d7)")
ax.set_ylim(0, max(mult) * 1.20)
ax.set_xticks(range(4))
ax.set_xticklabels([f"{l}\n{v/1e6:.2f}M rows" for l, v in zip(lbl, vals)])
S.baseline(ax, 1.0)
savefig(fig, "g4_5_party_types.png", group=GROUP)

# ---------------------------------------------------------------- 5. bank amount tilts
print("\n=== 5. bank amount tilts: stable, partly type-mix ===")
r = con.execute(f"""
    SELECT split_part(BIC8_PATH,';',1) bank,
           upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc,
           COUNT(*) n,
           AVG(CASE WHEN ORDERING_TYPE = 'C' THEN 1.0 ELSE 0 END) pc,
           MEDIAN(log10(USD_AMOUNT)) mu
    FROM read_parquet('{G}')
    WHERE gap_head = FALSE AND ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
    GROUP BY 1,2 HAVING COUNT(*) >= 500
""").df()
cmu = r.groupby("sc").mu.median().rename("cmu")
r = r.join(cmu, on="sc")
r["dev"] = r.mu - r.cmu
print("cells (bank n>=500):", len(r), "| raw dev std %.3f" % r.dev.std())
print("corr(dev, share_C) = %.3f" % np.corrcoef(r.dev, r.pc)[0,1])
# split-half stability
rh = con.execute(f"""
    SELECT split_part(BIC8_PATH,';',1) bank,
           upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc,
           half, COUNT(*) n, MEDIAN(log10(USD_AMOUNT)) mu
    FROM read_parquet('{G}')
    WHERE gap_head = FALSE AND ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
    GROUP BY 1,2,3
""").df()
b0 = rh[(rh.half == 0) & (rh.n >= 250)][["bank","sc","mu"]].rename(columns={"mu":"mu0"})
b1 = rh[(rh.half == 1) & (rh.n >= 250)][["bank","sc","mu"]].rename(columns={"mu":"mu1"})
m2 = b0.merge(b1, on=["bank","sc"])
c0 = rh[rh.half == 0].groupby("sc").mu.median().rename("c0")
c1 = rh[rh.half == 1].groupby("sc").mu.median().rename("c1")
m2 = m2.merge(c0, on="sc").merge(c1, on="sc")
print("split-half stability: n=%d banks | corr(dev0, dev1) = %.3f" % (
    len(m2), np.corrcoef(m2.mu0 - m2.c0, m2.mu1 - m2.c1)[0,1]))

fig, ax = plt.subplots(figsize=(9.5, 5.2))
ax.scatter(r.pc, r.dev, s=8, alpha=0.25, color=S.C_ACCENT, linewidths=0,
           label="One bank")
band = pd.qcut(r.pc, 10, duplicates="drop")
line = r.groupby(band, observed=True).agg(x=("pc", "median"), y=("dev", "median"))
ax.plot(line.x, line.y, color=S.C_WARN, lw=2.6, label="Median bank in each 10% slice")
ax.axhline(0, color=S.C_MUTED, lw=1, ls=":")
S.clean(ax)
S.title(ax, "Banks that serve more retail clients pay smaller amounts",
        "Each dot is one bank; the red line is the median of the banks around it (r = -0.58).")
ax.set_xlabel("Share of the bank's senders that are retail (type C)")
ax.set_ylabel("Amount vs country median (log10 USD)")
ax.set_xlim(-0.02, 0.95)
S.pct_axis(ax, "x", step=0.2)
S.legend_below(ax, ncol=2, y=-0.17)
savefig(fig, "g4_6_bank_tilt.png", group=GROUP)

# ---------------------------------------------------------------- 6. BIC8 format
print("\n=== 6. BIC8 format census ===")
r = con.execute(f"""
    WITH app AS (
      SELECT CASE WHEN x != '...' THEN x END bank FROM (
        SELECT unnest(string_split(BIC8_PATH, ';')) x FROM read_parquet('{G}')
      ) WHERE bank IS NOT NULL AND bank != '...' AND bank != ''
    )
    SELECT COUNT(DISTINCT bank) nb,
           SUM(CASE WHEN NOT regexp_matches(substr(bank,1,4), '^[0-9]+$') THEN 1 ELSE 0 END) nonnum_code,
           COUNT(DISTINCT substr(bank,8,1)) c8vals, COUNT(DISTINCT substr(bank,7,1)) c7vals
    FROM app
""").df()
print(r.T.to_string())
r = con.execute(f"""
    WITH app AS (
      SELECT CASE WHEN x != '...' THEN x END bank FROM (
        SELECT unnest(string_split(BIC8_PATH, ';')) x FROM read_parquet('{G}')
      ) WHERE bank IS NOT NULL AND bank != '...' AND bank != ''
    )
    SELECT upper(substr(bank,5,2)) ctry, MIN(substr(bank,7,1)) c7, COUNT(DISTINCT bank) nb
    FROM app GROUP BY 1 ORDER BY nb DESC LIMIT 10
""").df()
print("char-7 per country (constant within country, 25 values overall):")
print(r.to_string(index=False))

# ---------------------------------------------------------------- 7. BIC8 structure (rule)
# The census above says WHEN banks appear; this says how the bank id itself is
# built, and it is exact: every one of the 25.8M appearances obeys the same layout.
print("\n=== 7a. BIC8 slot layout (all 25,815,715 appearances) ===")
sl = con.execute(f"""
    WITH app AS (
      SELECT CASE WHEN x != '...' THEN x END bank FROM (
        SELECT unnest(string_split(BIC8_PATH, ';')) x FROM read_parquet('{G}')
      ) WHERE bank IS NOT NULL AND bank != '...' AND bank != ''
    )
    SELECT COUNT(*) apps, COUNT(DISTINCT bank) banks,
           COUNT(DISTINCT substr(bank,1,1)) s1, COUNT(DISTINCT substr(bank,2,1)) s2,
           COUNT(DISTINCT substr(bank,3,1)) s3, COUNT(DISTINCT substr(bank,4,1)) s4,
           COUNT(DISTINCT substr(bank,5,2)) s56, COUNT(DISTINCT substr(bank,7,1)) s7,
           COUNT(DISTINCT substr(bank,8,1)) s8,
           SUM(CASE WHEN regexp_matches(substr(bank,1,4),'^[0-9]+$') THEN 0 ELSE 1 END) bad_num,
           SUM(CASE WHEN substr(bank,8,1) = '0' THEN 0 ELSE 1 END) bad_zero,
           COUNT(DISTINCT CAST(substr(bank,1,4) AS INT)) prefixes,
           MIN(CAST(substr(bank,1,4) AS INT)) pmin, MAX(CAST(substr(bank,1,4) AS INT)) pmax
    FROM app
""").df().iloc[0]
print(f"  appearances {int(sl.apps):,} | distinct banks {int(sl.banks):,}")
print(f"  distinct values per slot: 1:{int(sl.s1)}  2:{int(sl.s2)}  3:{int(sl.s3)}  4:{int(sl.s4)}  "
      f"5-6:{int(sl.s56)}  7:{int(sl.s7)}  8:{int(sl.s8)}")
print(f"  non-numeric first 4 chars: {int(sl.bad_num)} | char 8 not '0': {int(sl.bad_zero)}")
print(f"  numeric prefixes: {int(sl.prefixes):,} distinct in range {int(sl.pmin)}..{int(sl.pmax)} "
      f"for {int(sl.banks):,} banks -> the prefix alone is NOT the bank id")
c7 = con.execute(f"""
    WITH app AS (
      SELECT CASE WHEN x != '...' THEN x END bank FROM (
        SELECT unnest(string_split(BIC8_PATH, ';')) x FROM read_parquet('{G}')
      ) WHERE bank IS NOT NULL AND bank != '...' AND bank != ''
    )
    SELECT upper(substr(bank,5,2)) ctry, COUNT(DISTINCT substr(bank,7,1)) n7,
           COUNT(DISTINCT bank) nb, min(substr(bank,7,1)) c7
    FROM app GROUP BY 1
""").df()
n_multi = int((c7.n7 > 1).sum())
print(f"  countries whose char 7 is not constant: {n_multi} of {len(c7)}")
print("  char 7 letters are shared, not unique to a country:",
      ", ".join(f"'{k}'={v}" for k, v in c7.c7.value_counts().head(5).items()))

slots = ["char 1", "char 2", "char 3", "char 4", "chars 5-6", "char 7", "char 8"]
nv = [int(sl.s1), int(sl.s2), int(sl.s3), int(sl.s4), int(sl.s56), int(sl.s7), int(sl.s8)]
slot_col = [S.C_ACCENT, S.C_ACCENT, S.C_ACCENT, S.C_ACCENT, S.C_WARN, S.C_WARN, S.C_GREY]
fig, ax = plt.subplots(figsize=(9.5, 5.0))
bars = ax.bar(slots, nv, color=slot_col, width=0.66)
S.vlabels(ax, bars, [str(v) for v in nv])
S.clean(ax)
S.title(ax, "A bank id is 4 digits + country + a letter + '0' - with no exceptions",
        f"Distinct values found in each position of the 8-character bank code "
        f"({int(sl.apps):,} appearances, {int(sl.banks):,} banks); not one breaks the layout.")
ax.set_xlabel("Position in the bank code (example: 0309CHZ0)")
ax.set_ylabel("Distinct values found in that position")
ax.set_ylim(0, 270)
ax.annotate("the country\n(229 codes)", xy=(4, int(sl.s56)), xytext=(0, 18),
            textcoords="offset points", ha="center", fontsize=9.5, color=S.C_WARN)
S.legend_below(ax, ncol=3, y=-0.16,
               handles=[Patch(color=S.C_ACCENT), Patch(color=S.C_WARN), Patch(color=S.C_GREY)],
               labels=["Digits 1-4: always numeric (0 exceptions)",
                       "Country code + house letter", "Char 8: always '0' (0 exceptions)"])
savefig(fig, "g4_7_bic8_structure.png", group=GROUP)

# ---------------------------------------------------------------- 8. the B/C offset (rule)
# Rule 6 in one controlled picture: the business premium is the SAME absolute
# shift at every income level, so country and party type are separate dials.
print("\n=== 8a. business-vs-retail offset, one point per country ===")
r = con.execute(f"""
    SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc, ORDERING_TYPE ot,
           COUNT(*) n, MEDIAN(log10(USD_AMOUNT)) mu
    FROM read_parquet('{G}')
    WHERE gap_head = FALSE AND ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
    GROUP BY 1,2
""").df()
p = r.pivot(index="sc", columns="ot", values="mu").dropna()
nn = r.pivot(index="sc", columns="ot", values="n").dropna()
p = p[(nn.B >= 300) & (nn.C >= 300)]
p["gap"] = p.B - p.C
med_gap = float(p.gap.median())
print(f"  countries with >=300 business and >=300 retail payments: {len(p)}")
print(f"  offset B - C: min {p.gap.min():.3f} ({p.gap.idxmin()})  p25 {p.gap.quantile(.25):.3f}  "
      f"median {med_gap:.3f}  p75 {p.gap.quantile(.75):.3f}  max {p.gap.max():.3f} ({p.gap.idxmax()})")
print(f"  sd {p.gap.std():.3f} dex; {int(((p.gap>=.80)&(p.gap<=.95)).sum())}/{len(p)} countries "
      f"between 0.80 and 0.95 dex")
print(f"  the country ladder itself spans {p.C.max()-p.C.min():.3f} dex in retail and "
      f"{p.B.max()-p.B.min():.3f} dex in business -> the two effects do not collapse into one")

fig, ax = plt.subplots(figsize=(8.6, 6.4))
ax.scatter(p.C, p.B, s=26, color=S.C_ACCENT, alpha=0.7, linewidths=0,
           label=f"One country ({len(p)} countries)")
xs = np.linspace(p.C.min() - 0.1, p.C.max() + 0.1, 10)
ax.plot(xs, xs, color=S.C_MUTED, ls="--", lw=1.2, label="No difference (B = C)")
ax.plot(xs, xs + med_gap, color=S.C_WARN, lw=2.0,
        label=f"Measured offset (+{med_gap:.2f} dex = {10**med_gap:.1f}x)")
S.clean(ax, grid="both")
S.title(ax, "Every country charges its businesses the same multiple",
        "Median amount of a business sender (y) vs a retail sender (x), same country.")
ax.set_xlabel("Retail (type C) median payment, log10 USD")
ax.set_ylabel("Business (type B) median payment, log10 USD")
ax.set_xticks([1.5, 2, 2.5, 3, 3.5]); ax.set_yticks([2, 2.5, 3, 3.5, 4, 4.5])
ax.set_xticklabels(["$32", "$100", "$320", "$1k", "$3.2k"])
ax.set_yticklabels(["$100", "$320", "$1k", "$3.2k", "$10k", "$32k"])
ax.set_xlim(1.4, 4.0); ax.set_ylim(2.0, 4.7)
S.legend_below(ax, ncol=3, y=-0.17)
savefig(fig, "g4_8_bc_offset.png", group=GROUP)

# ---------------------------------------------------------------- 9. proof rows
print("\n=== 7. proof rows ===")
pr = con.execute(f"""
    SELECT BIC8_PATH, USD_AMOUNT, ORDERING_TYPE ot, BENEFICIARY_TYPE bt, TRANSACTION_TYPE_CODE t
    FROM read_parquet('{G}')
    WHERE (split_part(BIC8_PATH,';',1) = '0309CHZ0' AND PARTICIPANT_COUNT >= 4 AND ANOMALY_TYPE IS NULL)
       OR (upper(substr(split_part(BIC8_PATH,';',1),5,2)) = 'IM' AND ANOMALY_TYPE IS NULL)
    LIMIT 6
""").df()
print(pr.to_string(index=False))
print("\nDONE g4")
