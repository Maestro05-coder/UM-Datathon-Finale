"""g2 - Currencies & conversions. Full-data DuckDB over cache_full.

Rules documented here:
  R1  the payment currency is the SENDER-side currency: it matches the first bank's
      modal currency ~93% and the sender country's home currency ~93-97%,
      the beneficiary bank's only ~19%.
  R2  every country has a home currency (modal, exact table in agg/_g2_home_cur_all.pkl);
      big countries pay home ~97% of the time. Within-country payments: 96.8% home.
  R3  foreign payments (the ~3-7% rest) are mostly EUR (56%) / USD (26%) and lean to
      the BENEFICIARY's currency: 57.7% match beneficiary home vs tiny baselines.
  R4  USD nice-number rule: amounts in USD are rounded to whole dollars 38.7% and to
      multiples of 100 15.6%, INDEPENDENT of the sender country. Non-USD: ~1% / ~0.01%.
  R5  dead end: there is NO FX-rate table converting CURRENCY_CODE into USD_AMOUNT.
      Within a country, foreign-currency payments have the same amount distribution
      (median delta ~ +-0.02 dex); the huge cross-currency median gaps are country
      wealth effects, not rates.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ddb, full_glob, rand_sample, savefig
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

con = ddb()
G = full_glob()
AGG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agg")
GROUP = "g2_currency"

def wmean(df, col, weight="n"):
    """Row-weighted mean of boolean/float column col."""
    return float((df[col] * df[weight]).sum() / df[weight].sum())

# ---------------------------------------------------------------- 0. home table
print("=== home currency per country (modal over ALL rows, sender side) ===")
allr = con.execute(f"""
    SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc, CURRENCY_CODE cur, COUNT(*) n
    FROM read_parquet('{G}') WHERE gap_head = FALSE GROUP BY 1,2
""").df()
HOMES = allr.sort_values(["sc", "n"], ascending=[True, False]).groupby("sc").head(1).set_index("sc").cur.to_dict()
pd.Series(HOMES).rename("home_cur").to_pickle(os.path.join(AGG, "_g2_home_cur_all.pkl"))
print("sender countries (any size):", len(HOMES))

# ---------------------------------------------------------------- 1. census
print("\n=== 1. currency census (exact) ===")
cens = con.execute(f"""
    SELECT CURRENCY_CODE cur, COUNT(*) n FROM read_parquet('{G}') GROUP BY 1 ORDER BY 2 DESC
""").df()
print("distinct currencies:", len(cens), "| top5:", list(cens.head(5).itertuples(index=False, name=None)))
print("currencies with <1000 rows:", int((cens.n < 1000).sum()), "| <100 rows:", int((cens.n < 100).sum()))
cens.to_pickle(os.path.join(AGG, "_g2_census.pkl"))

# ---------------------------------------------------------------- 2. home share per country
print("\n=== 2. home-currency share per country (rows weighted, n>=1000, exact) ===")
cc = allr.groupby("sc").n.sum()
allr2 = allr.copy()
allr2["home"] = [float(cur == HOMES.get(sc)) for sc, cur in zip(allr2.sc, allr2.cur)]
bigc = allr2[allr2.sc.map(cc) >= 1000]
hs = bigc.groupby("sc").apply(lambda s: (s.home * s.n).sum() / s.n.sum())
print("countries n>=1000:", len(hs))
print("home share: min %.4f  p25 %.4f  median %.4f  max %.4f" % (hs.min(), hs.quantile(.25), hs.median(), hs.max()))
print("countries with home share < 90%:", int((hs < 0.90).sum()))
for sc in hs.sort_values().head(4).index:
    sub = bigc[bigc.sc == sc].sort_values("n", ascending=False)
    print("  lowest:", sc, "home:", HOMES[sc], "share %.3f" % hs[sc], "| mix:", list(zip(sub.cur.head(3), sub.n.head(3))))
for sc in hs.sort_values().tail(2).index:
    print("  highest:", sc, "home:", HOMES[sc], "share %.4f" % hs[sc])

# ---------------------------------------------------------------- 3. cells + same-country control
print("\n=== 3. corridor cells + same-country control (rows weighted) ===")
r = con.execute(f"""
    WITH paid AS (
      SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc,
             upper(substr(split_part(BIC8_PATH,';',-1),5,2)) bc,
             CURRENCY_CODE cur
      FROM read_parquet('{G}') WHERE gap_head = FALSE AND gap_tail = FALSE
    )
    SELECT sc, bc, cur, COUNT(*) n FROM paid GROUP BY 1,2,3
""").df()
r["hs"] = r.sc.map(HOMES)
r["hb"] = r.bc.map(HOMES)
same = r[r.sc == r.bc]
cross = r[r.sc != r.bc]
ph = ((same.cur == same.hs) * same.n).sum() / same.n.sum()
ph_c = ((cross.cur == cross.hs) * cross.n).sum() / cross.n.sum()
print(f"same-country payments: {int(same.n.sum()):,} rows -> currency==home {ph*100:.2f}%")
print(f"cross-country payments: {int(cross.n.sum()):,} rows -> currency==home {ph_c*100:.2f}%")
r.to_pickle(os.path.join(AGG, "_g2_paid_cells.pkl"))

# ---------------------------------------------------------------- 4. foreign composition + beneficiary pull
print("\n=== 4. foreign-currency rows: which currency, and is it the beneficiary's? ===")
tot_s = r.groupby("sc").n.sum()
big = r[r.sc.map(tot_s) >= 1000]
fh = big[big.cur != big.hs]
n_home = big[big.cur == big.hs].n.sum()
print(f"big rows {int(big.n.sum()):,} | home {n_home/big.n.sum()*100:.2f}% | foreign {int(fh.n.sum()):,}")
comp = fh.groupby("cur").n.sum().sort_values(ascending=False)
csum = comp.sum()
print("foreign choice: EUR %.1f%%  USD %.1f%%  GBP %.1f%%  CHF %.1f%%  CNY %.1f%%  other %.1f%%" % (
    comp["EUR"]/csum*100, comp["USD"]/csum*100, comp.get("GBP",0)/csum*100,
    comp.get("CHF",0)/csum*100, comp.get("CNY",0)/csum*100,
    100 - comp[["EUR","USD","GBP","CHF","CNY"]].sum()/csum*100))
m = fh[fh.cur == fh.hb].n.sum()
print(f"currency==beneficiary-home among foreign rows: {int(m):,} = {m/fh.n.sum()*100:.1f}%")
# row-weighted baseline: among ALL foreign rows, share whose beneficiary home == cur
rows = []
for c in ["EUR", "USD", "GBP", "CHF", "CNY", "JPY", "SGD", "AUD"]:
    sub = fh[fh.cur == c]
    if not len(sub): continue
    hit = sub[sub.cur == sub.hb].n.sum() / sub.n.sum()
    bl = fh[fh.hb == c].n.sum() / fh.n.sum()
    rows.append((c, int(sub.n.sum()), hit*100, bl*100))
mt = pd.DataFrame(rows, columns=["cur", "n", "match_pct", "baseline_pct"])
print(mt.round(1).to_string(index=False))
mt.to_pickle(os.path.join(AGG, "_g2_foreign_match.pkl"))


# ---------------------------------------------------------------- 5. USD nice-number rule
print("\n=== 5. USD nice-number rule (country held fixed, clean rows) ===")
cells = con.execute(f"""
    SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc, CURRENCY_CODE cur, COUNT(*) n,
           AVG(CASE WHEN ABS(USD_AMOUNT - ROUND(USD_AMOUNT)) < 1e-9 THEN 1.0 ELSE 0 END) int_share,
           AVG(CASE WHEN ABS(USD_AMOUNT/100 - ROUND(USD_AMOUNT/100)) < 1e-9 THEN 1.0 ELSE 0 END) m100_share
    FROM read_parquet('{G}')
    WHERE gap_head = FALSE AND ANOMALY_TYPE IS NULL AND USD_AMOUNT >= 1
    GROUP BY 1,2 HAVING COUNT(*) >= 2000
""").df()
sel = cells[cells.sc.isin(["DE", "GB", "JP", "US"])].sort_values(["sc", "n"], ascending=[True, False])
print(sel.to_string(index=False))

q = con.execute(f"""
    SELECT CURRENCY_CODE = 'USD' isusd,
           AVG(CASE WHEN ABS(USD_AMOUNT - ROUND(USD_AMOUNT)) < 1e-9 THEN 1.0 ELSE 0 END) s,
           AVG(CASE WHEN ABS(USD_AMOUNT/100 - ROUND(USD_AMOUNT/100)) < 1e-9 THEN 1.0 ELSE 0 END) s100
    FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT >= 1
    GROUP BY 1
""").df()
print(q.to_string(index=False))

# ---------------------------------------------------------------- 6. no FX-rate table (dead end, quantified)
print("\n=== 6. dead-end check: within a country, does currency change the amount? ===")
amt = con.execute(f"""
    SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc, CURRENCY_CODE cur,
           MEDIAN(log10(USD_AMOUNT)) m, COUNT(*) n
    FROM read_parquet('{G}')
    WHERE gap_head = FALSE AND ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
    GROUP BY 1,2 HAVING COUNT(*) >= 2000
""").df()
print("amt cells:", len(amt), "| home mapped nulls:", int(amt.cur.map(HOMES).isna().sum()))
amt["home_cur"] = amt.sc.map(HOMES)
deltas = []
for sc, s in amt.groupby("sc"):
    h = s[s.cur == s.home_cur]
    if not len(h): continue
    hm = h.m.iloc[0]
    for _, rr in s[s.cur != s.home_cur].iterrows():
        deltas.append((sc, rr["cur"], int(rr["n"]), rr["m"] - hm))
D = pd.DataFrame(deltas, columns=["sc", "cur", "n", "delta"])
print("same-country foreign cells:", len(D), " total rows:", int(D.n.sum()))
print("delta = median_log10(foreign) - median_log10(home): min %.3f  median %.3f  max %.3f  (|delta| median %.3f)"
      % (D.delta.min(), D.delta.median(), D.delta.max(), D.delta.abs().median()))
print("(a real FX-rate story would need deltas of ~0.03-1.9 dex, e.g. USD/INR ~1.9)")
print(D.sort_values("delta").head(3).to_string(index=False))
print(D.sort_values("delta").tail(3).to_string(index=False))
D.to_pickle(os.path.join(AGG, "_g2_no_rate_deltas.pkl"))

# ---------------------------------------------------------------- 7. bank-level confirmation
print("\n=== 7. bank-level: whose currency? (all rows, gap-free head) ===")
bank = con.execute(f"""
    SELECT split_part(BIC8_PATH,';',1) bank, CURRENCY_CODE cur, COUNT(*) n
    FROM read_parquet('{G}') WHERE gap_head = FALSE GROUP BY 1,2
""").df()
bmod = bank.sort_values("n", ascending=False).groupby("bank").head(1).set_index("bank").cur.to_dict()
pd.Series(bmod).rename("bank_cur").to_pickle(os.path.join(AGG, "_g2_bank_cur.pkl"))
print("distinct first-position banks:", len(bmod))
firstb = con.execute(f"""
    SELECT split_part(BIC8_PATH,';',1) fb, split_part(BIC8_PATH,';',-1) lb,
           ORDERING_BIC8 ob, BENEFICIARY_BIC8 bb, CURRENCY_CODE cur
    FROM read_parquet('{G}')
""").df()
firstb["pf"] = [float(cur == bmod.get(b)) for cur, b in zip(firstb.cur, firstb.fb)]
firstb["pl"] = [float(cur == bmod.get(b)) for cur, b in zip(firstb.cur, firstb.lb)]
firstb["po"] = [float(cur == bmod.get(b)) for cur, b in zip(firstb.cur, firstb.ob)]
firstb["pb"] = [float(cur == bmod.get(b)) for cur, b in zip(firstb.cur, firstb.bb)]
MATCH_FIRST = float(firstb.pf.mean()); MATCH_LAST = float(firstb.pl.mean())
print("currency == first-bank modal currency : %.2f%%  (all rows, '...' heads counted as mismatch)" % (MATCH_FIRST*100))
print("currency == last-bank modal currency  : %.2f%%" % (MATCH_LAST*100))
print("currency == ORDERING_BIC8 bank modal  : %.2f%%" % (firstb.po.mean()*100))
print("currency == BENEFICIARY_BIC8 bank mod : %.2f%%" % (firstb.pb.mean()*100))
del firstb

# ---------------------------------------------------------------- 8. proof rows
print("\n=== 8. proof rows ===")
pr = con.execute(f"""
    SELECT BIC8_PATH, CURRENCY_CODE, USD_AMOUNT, CURRENCY_CONVERSION_COUNT
    FROM read_parquet('{G}')
    WHERE (upper(substr(split_part(BIC8_PATH,';',1),5,2)) = 'DE' AND CURRENCY_CODE = 'USD'
           AND ABS(USD_AMOUNT/100 - ROUND(USD_AMOUNT/100)) < 1e-9 AND ANOMALY_TYPE IS NULL)
       OR (upper(substr(split_part(BIC8_PATH,';',1),5,2)) = 'GT' AND CURRENCY_CODE = 'GTQ')
    LIMIT 6
""").df()
print(pr.to_string(index=False))

# ---------------------------------------------------------------- charts
# One idea per chart, units on every axis, legend below the plot area.
import _style as S
S.apply()

# 1. currency census: which currencies exist and how big they are.
tot_rows = cens.n.sum()
top = cens.head(15).iloc[::-1]                   # biggest bar at the top
share = (top.n / tot_rows).to_numpy()
fig, ax = plt.subplots(figsize=(9.5, 5.4))
bars = ax.barh(top.cur, share, color=S.C_ACCENT, height=0.72)
S.clean(ax, grid="x")
S.title(ax, f"The 15 most-used currencies (of {len(cens)} in the file)",
        f"EUR, USD, GBP, CHF and SGD together carry {cens.n.head(5).sum()/tot_rows:.0%} of all payments.")
ax.set_xlabel("Share of all 10,000,000 payments")
ax.set_ylabel("Payment currency")
ax.set_xlim(0, share.max() * 1.20)
S.pct_axis(ax, "x")
S.hlabels(ax, bars, [f"{100*v:.1f}%" for v in share])
savefig(fig, "g2_1_currency_census.png", group=GROUP)

# 2. whose currency is it? sender side vs beneficiary side.
fig, ax = plt.subplots(figsize=(9.5, 3.6))
sides = ["Sender side\n(first bank in the route)", "Beneficiary side\n(last bank in the route)"]
vals = [MATCH_FIRST, MATCH_LAST]
bars = ax.barh(sides, vals, color=[S.C_ACCENT, S.C_GREY], height=0.55)
S.clean(ax, grid="x")
S.title(ax, "The currency label is decided on the sender side",
        "Share of payments whose currency matches that side's usual currency.")
ax.set_xlabel("Share of payments whose currency matches that side's usual currency")
ax.set_xlim(0, 1.05)
S.pct_axis(ax, "x", step=0.2)
S.hlabels(ax, bars, [f"{v:.1%}" for v in vals])
savefig(fig, "g2_2_whose_currency.png", group=GROUP)

# 3. USD nice-number rule, holding the sender country fixed.
pairs = [("DE", "EUR"), ("DE", "USD"), ("GB", "GBP"), ("GB", "USD"),
         ("JP", "JPY"), ("JP", "USD"), ("US", "USD"), ("US", "EUR")]
rows = []
for sc, cur in pairs:
    v = cells[(cells.sc == sc) & (cells.cur == cur)]
    if len(v):
        rows.append((f"{sc} - {cur}", float(v.int_share.iloc[0]), cur == "USD"))
rows = rows[::-1]                                # read top-down in country order
fig, ax = plt.subplots(figsize=(9.5, 5.0))
labels = [r[0] for r in rows]
vals = [r[1] for r in rows]
colors = [S.C_ACCENT if r[2] else S.C_GREY for r in rows]
bars = ax.barh(labels, vals, color=colors, height=0.68)
S.clean(ax, grid="x")
S.title(ax, "Whole-number amounts switch on when the currency is USD",
        "Same sender country, different payment currency: the bar jumps only for USD.")
ax.set_xlabel("Share of amounts that are whole numbers (no cents)")
ax.set_ylabel("Sender country - payment currency")
ax.set_xlim(0, max(vals) * 1.22)
S.pct_axis(ax, "x")
S.hlabels(ax, bars, [f"{v:.1%}" for v in vals])
from matplotlib.patches import Patch
S.legend_below(ax, ncol=2, handles=[Patch(color=S.C_ACCENT), Patch(color=S.C_GREY)],
               labels=["Paid in US dollars (USD)", "Paid in any other currency"], y=-0.16)
savefig(fig, "g2_3_usd_roundness.png", group=GROUP)

# 4. foreign-currency choice vs the beneficiary's currency.
m2 = mt.sort_values("match_pct")
y = np.arange(len(m2))
fig, ax = plt.subplots(figsize=(9.5, 5.0))
ax.barh(y + 0.19, m2.match_pct / 100, height=0.36, color=S.C_ACCENT,
        label="Actual: chosen currency = beneficiary's home currency")
ax.barh(y - 0.19, m2.baseline_pct / 100, height=0.36, color=S.C_GREY,
        label="Chance alone: this is anyway the beneficiary's currency")
ax.set_yticks(y); ax.set_yticklabels(m2.cur)
S.clean(ax, grid="x")
S.title(ax, "Foreign-currency payments lean to the beneficiary's own currency",
        "Every currency is used far more often than chance alone would explain.")
ax.set_xlabel("Share of foreign-currency payments")
ax.set_ylabel("Foreign currency chosen")
ax.set_xlim(0, 0.75)
S.pct_axis(ax, "x", step=0.1)
S.legend_below(ax, ncol=1, y=-0.20)
savefig(fig, "g2_4_beneficiary_pull.png", group=GROUP)

print("\nDONE g2")
