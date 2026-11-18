"""g3 - Amounts. Full-data DuckDB over cache_full.

Rules documented here:
  R1  amounts are log-normal, one shape for everyone (sigma ~1.05-1.12 in log10),
      shifted per sender country: a wealth ladder from Guinea-Bissau (median $48)
      to Monaco (median $31k). Skewness of log10 = -0.08, kurtosis 0.05 on 10m rows.
  R1b the per-country centre is a free, fixed dial, not a by-product: split-half
      r = 0.9977 (mean |diff| 0.025 dex), width stays at 1.05 dex, holding the
      corridor fixed to the US keeps the ladder (r = 0.986), and every observable
      about the country together explains only R2 = 0.46.
  R2  nothing about the payment moves the amount: route length, type, hidden banks,
      weekend vs weekday are all flat (medians within 0.01 dex). The apparent
      0-conversion bump (+0.18 dex) is corridor composition, not causation.
  R3  USD payments have a whole-number rounding mode: 38.65% whole dollars
      (uniform over the whole window), 46% of those integers are 2-significant-
      figure values, 10.7% are exactly {1,2,5}x10^k. Non-USD: 0.99% / ~0 / ~0.01%.
  R4  ~2.83% of all rows are "storm" rows: per day and per currency (EUR/GBP/CHF/
      SGD/CNY - never USD), a base amount is injected as base x integer multiples
      into hundreds of otherwise-ordinary payments of random parties.
      Biggest: EUR 1,149.08 on 2023-06-23 (1,159 rows).
  R5  Benford: amounts fit Benford's law closely (31.4% vs 30.1% leading 1s),
      with excess on {1,2,5} from the USD pool.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ddb, full_glob, rand_sample, savefig
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import _style as S
S.apply()

con = ddb()
G = full_glob()
AGG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agg")
GROUP = "g3_amount"

# ---------------------------------------------------------------- 1. global shape
print("=== 1. global clean amount stats (exact) ===")
r = con.execute(f"""
    SELECT COUNT(*) n, MIN(USD_AMOUNT) mn, MAX(USD_AMOUNT) mx,
           APPROX_QUANTILE(USD_AMOUNT, 0.01) p01, APPROX_QUANTILE(USD_AMOUNT, 0.5) p50,
           APPROX_QUANTILE(USD_AMOUNT, 0.75) p75, APPROX_QUANTILE(USD_AMOUNT, 0.90) p90,
           APPROX_QUANTILE(USD_AMOUNT, 0.99) p99,
           AVG(log10(USD_AMOUNT)) m, STDDEV(log10(USD_AMOUNT)) s,
           SKEWNESS(log10(USD_AMOUNT)) sk, KURTOSIS(log10(USD_AMOUNT)) ku
    FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
""").df().T
print(r.to_string())
mu, sig = float(r.loc["m"][0]), float(r.loc["s"][0])

fig, ax = plt.subplots(figsize=(9.5, 4.8))
smp = rand_sample(con, f"SELECT log10(USD_AMOUNT) x FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0", pct=100)
smp = smp.x.sample(100000, random_state=7)
xs = np.linspace(-2, 10, 400)
fit = np.exp(-(xs-mu)**2/(2*sig**2))/(sig*np.sqrt(2*np.pi))
ax.hist(smp, bins=200, density=True, alpha=0.55, color=S.C_ACCENT_SOFT,
        label="100,000 random clean payments")
ax.plot(xs, fit, color=S.C_WARN, lw=2.6, label="Normal fit")
S.clean(ax)
S.title(ax, "Every amount comes from one log-normal shape",
        f"The same bell curve for all 10M payments: skew {r.loc['sk'][0]:+.2f}, kurtosis {r.loc['ku'][0]:+.2f}.")
ax.set_xlabel("Payment amount (USD, log scale)")
ax.set_ylabel("Density of payments")
ax.set_xticks([-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
ax.set_xticklabels(["$0.10", "$1", "$10", "$100", "$1k", "$10k",
                    "$100k", "$1M", "$10M", "$100M", "$1B"])
ax.set_xlim(-1.5, 9.5)
S.legend_below(ax, ncol=2, y=-0.20)
savefig(fig, "g3_1_lognormal.png", group=GROUP)

# ---------------------------------------------------------------- 2. wealth ladder
print("\n=== 2. per-country wealth ladder (clean, n>=2000) ===")
df = con.execute(f"""
    SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc, COUNT(*) n,
           MEDIAN(log10(USD_AMOUNT)) mu,
           APPROX_QUANTILE(log10(USD_AMOUNT), 0.25) q1, APPROX_QUANTILE(log10(USD_AMOUNT), 0.75) q3
    FROM read_parquet('{G}')
    WHERE gap_head = FALSE AND ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
    GROUP BY 1 HAVING COUNT(*) >= 2000
""").df()
df["sigma"] = (df.q3 - df.q1) / 1.349
df = df.sort_values("mu").reset_index(drop=True)
print("countries:", len(df))
print("sigma: min %.3f median %.3f max %.3f  | mu range %.3f .. %.3f" % (
    df.sigma.min(), df.sigma.median(), df.sigma.max(), df.mu.min(), df.mu.max()))
print("poorest 5:", list(zip(df.sc[:5], (10**df.mu[:5]).round(0))))
print("richest 5:", list(zip(df.sc[-5:], (10**df.mu[-5:]).round(0))))
# variance decomposition: E[sigma^2]+var(mu) should equal global var
w = df.n / df.n.sum()
mu_w = np.average(df.mu, weights=df.n); var_mu = np.average((df.mu-mu_w)**2, weights=df.n)
e_sig2 = (w * df.sigma**2).sum()
print("variance decomposition (n>=2000 countries): E[sigma_c^2] %.4f + var(mu_c) %.4f = %.4f  (global sigma^2 %.4f)"
      % (e_sig2, var_mu, e_sig2 + var_mu, sig**2))
df.to_pickle(os.path.join(AGG, "_g3_country_mu.pkl"))

poor = df.head(10); rich = df.tail(10)
plot = pd.concat([poor, rich]).reset_index(drop=True)     # poorest at the bottom
vals = 10 ** plot.mu
yy = np.arange(len(plot))
colors = [S.C_WARN] * 10 + [S.C_ACCENT] * 10
fig, ax = plt.subplots(figsize=(9.5, 6.0))
ax.scatter(vals, yy, s=95, color=colors, zorder=3, edgecolor="white", linewidth=1.2)
for x, yv, v in zip(vals, yy, vals):
    ax.annotate(f"${v:,.0f}", xy=(x, yv), xytext=(8, 0), textcoords="offset points",
                ha="left", va="center", fontsize=9.5, color=S.C_TEXT)
ax.set_xscale("log")
S.clean(ax, grid="x")
S.title(ax, "The country wealth ladder: 10 poorest vs 10 richest sender countries",
        f"Median clean payment per country ({len(df)} countries with 2,000+ clean rows); "
        f"from \\${vals.min():,.0f} to \\${vals.max():,.0f}.")
ax.set_xlabel("Median payment (USD, log scale)")
ax.set_ylabel("Sender country (BIC8 country code)")
ax.set_yticks(yy); ax.set_yticklabels(plot.sc)
ax.set_ylim(-0.8, len(plot) - 0.2)
ax.set_xlim(20, vals.max() * 3.5)
ax.set_xticks([100, 1e3, 1e4])
ax.set_xticklabels(["$100", "$1,000", "$10,000"])
S.baseline(ax, float(r.loc["p50"][0]), "all payments median", axis="x")
from matplotlib.patches import Patch
S.legend_below(ax, ncol=2, handles=[Patch(color=S.C_WARN), Patch(color=S.C_ACCENT)],
               labels=["10 poorest countries", "10 richest countries"], y=-0.12)
savefig(fig, "g3_2_wealth_ladder.png", group=GROUP)

# ---------------------------------------------------------------- 3. flatness (negative results)
print("\n=== 3. what does NOT move the amount (median log10, clean rows) ===")
for name, sql in [
    ("visible bank count", """
      SELECT n_vis k, COUNT(*) n, MEDIAN(log10(USD_AMOUNT)) m FROM read_parquet('{G}')
      WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0 GROUP BY 1 ORDER BY 1"""),
    ("transaction type", """
      SELECT TRANSACTION_TYPE_CODE k, COUNT(*) n, MEDIAN(log10(USD_AMOUNT)) m FROM read_parquet('{G}')
      WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0 GROUP BY 1 ORDER BY 3"""),
    ("hidden banks", """
      SELECT CAST(has_gap AS VARCHAR) k, COUNT(*) n, MEDIAN(log10(USD_AMOUNT)) m FROM read_parquet('{G}')
      WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0 GROUP BY 1"""),
    ("week/weekend", """
      SELECT CASE WHEN extract(dow from (timestamp '1970-01-01' + EPOCH_SECONDS * interval 1 second)) IN (0,6)
             THEN 'weekend' ELSE 'weekday' END k, COUNT(*) n, MEDIAN(log10(USD_AMOUNT)) m
      FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0 GROUP BY 1"""),
]:
    rr = con.execute(sql.format(G=G)).df()
    print(f"-- {name}:"); print(rr.round(3).to_string(index=False))
print("-- conversion count, split by same/cross-country corridor (composition control):")
rr = con.execute(f"""
    SELECT (upper(substr(split_part(BIC8_PATH,';',1),5,2)) = upper(substr(split_part(BIC8_PATH,';',-1),5,2))) same,
           CURRENCY_CONVERSION_COUNT k, COUNT(*) n, MEDIAN(log10(USD_AMOUNT)) m
    FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0 AND n_hidden = 0
    GROUP BY 1,2 ORDER BY 1,2
""").df()
print(rr[rr.k <= 2].round(3).to_string(index=False))

# ---------------------------------------------------------------- 4. USD structure
print("\n=== 4. USD whole-number mode (clean rows, amounts >= 1) ===")
mult = con.execute(f"""
    SELECT CURRENCY_CODE = 'USD' usd, COUNT(*) n,
           AVG(CASE WHEN ABS(USD_AMOUNT - ROUND(USD_AMOUNT)) < 1e-9 THEN 1.0 ELSE 0 END) int_share,
           AVG(CASE WHEN ABS(USD_AMOUNT/10 - ROUND(USD_AMOUNT/10)) < 1e-9 THEN 1.0 ELSE 0 END) d10,
           AVG(CASE WHEN ABS(USD_AMOUNT/100 - ROUND(USD_AMOUNT/100)) < 1e-9 THEN 1.0 ELSE 0 END) d100,
           AVG(CASE WHEN ABS(USD_AMOUNT/1000 - ROUND(USD_AMOUNT/1000)) < 1e-9 THEN 1.0 ELSE 0 END) d1000
    FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT >= 1 GROUP BY 1
""").df()
print(mult.round(4).to_string(index=False))
r = con.execute(f"""
    WITH t AS (
      SELECT CURRENCY_CODE = 'USD' usd,
             USD_AMOUNT / power(10, CAST(floor(log10(USD_AMOUNT)) AS INT)) mant
      FROM read_parquet('{G}')
      WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT >= 1 AND ABS(USD_AMOUNT - ROUND(USD_AMOUNT)) < 1e-9
    )
    SELECT usd, COUNT(*) n,
           AVG(CASE WHEN ABS(mant*10 - ROUND(mant*10)) < 1e-6 THEN 1.0 ELSE 0 END) sf2,
           AVG(CASE WHEN ABS(mant*100 - ROUND(mant*100)) < 1e-6 THEN 1.0 ELSE 0 END) sf3
    FROM t GROUP BY 1
""").df()
print("among integers, significant-figure profile:")
print(r.round(4).to_string(index=False))
r = con.execute(f"""
    WITH t AS (
      SELECT CURRENCY_CODE = 'USD' usd,
             USD_AMOUNT / power(10, CAST(floor(log10(USD_AMOUNT)) AS INT)) mant
      FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT >= 0.01
    )
    SELECT usd, COUNT(*) n,
           AVG(CASE WHEN ABS(mant - ROUND(mant)) < 1e-9 AND CAST(ROUND(mant) AS INT) IN (1,2,5) THEN 1.0 ELSE 0 END) pool
    FROM t GROUP BY 1
""").df()
print("exact {1,2,5}x10^k pool membership:")
print(r.round(4).to_string(index=False))
d = con.execute(f"""
    WITH t AS (
      SELECT CAST(floor(USD_AMOUNT / power(10, floor(log10(USD_AMOUNT)))) AS INT) dg
      FROM read_parquet('{G}')
      WHERE CURRENCY_CODE = 'USD' AND ANOMALY_TYPE IS NULL AND USD_AMOUNT >= 1
        AND ABS(USD_AMOUNT - ROUND(USD_AMOUNT)) < 1e-9
    )
    SELECT dg, COUNT(*) n, COUNT(*)*100.0/SUM(COUNT(*)) OVER () pct FROM t GROUP BY 1 ORDER BY 1
""").df()
ben = np.log10(1 + 1.0 / np.arange(1, 10)) * 100
print("leading digit of USD integers (USD vs Benford):")
print(pd.DataFrame({"digit": d.dg, "usd_pct": d.pct.round(2), "benford_pct": ben.round(2)}).to_string(index=False))

usd = mult[mult.usd].iloc[0]
oth = mult[~mult.usd].iloc[0]
cats = ["1", "10", "100", "1,000"]
u = np.array([usd.int_share, usd.d10, usd.d100, usd.d1000])
o = np.array([oth.int_share, oth.d10, oth.d100, oth.d1000])
yy = np.arange(len(cats))[::-1]
fig, ax = plt.subplots(figsize=(9.5, 4.8))
b1 = ax.barh(yy + 0.19, u, height=0.36, color=S.C_ACCENT, label="Paid in USD")
b2 = ax.barh(yy - 0.19, o, height=0.36, color=S.C_GREY, label="Paid in any other currency")
ax.set_yticks(yy); ax.set_yticklabels(cats)
S.clean(ax, grid="x")
S.title(ax, "Only USD amounts pile up on round numbers",
        "Share of clean amounts (at least USD 1) that are exactly round; all other currencies stay near zero.")
ax.set_xlabel("Share of clean payments")
ax.set_ylabel("Amount is a multiple of (USD)")
ax.set_xlim(0, 0.47)
S.pct_axis(ax, "x", step=0.1)
for bars, vals in [(b1, u), (b2, o)]:
    S.hlabels(ax, bars, [f"{v:.2%}" if v >= 0.001 else "<0.1%" for v in vals], fontsize=9.5)
S.legend_below(ax, ncol=2, y=-0.17)
savefig(fig, "g3_3_usd_roundness.png", group=GROUP)

# ---------------------------------------------------------------- 5. storms
print("\n=== 5. storm census: (currency, amount, day) cells with >=100 rows and >=50% of the value's rows ===")
cells = con.execute(f"""
    WITH perday AS (
      SELECT CURRENCY_CODE cur, USD_AMOUNT a, CAST((EPOCH_SECONDS - 1682832000)/86400 AS INT) d,
             COUNT(*) c
      FROM read_parquet('{G}') GROUP BY 1,2,3
    ),
    tot AS (
      SELECT CURRENCY_CODE cur, USD_AMOUNT a, COUNT(*) n FROM read_parquet('{G}') GROUP BY 1,2
    )
    SELECT p.cur, p.a, p.d, p.c FROM perday p JOIN tot t ON p.cur = t.cur AND p.a = t.a
    WHERE p.c >= 100 AND p.c >= 0.5 * t.n
""").df()
census = con.execute(f"SELECT CURRENCY_CODE cur, COUNT(*) n FROM read_parquet('{G}') GROUP BY 1").df().set_index("cur")
storm = cells.groupby("cur").c.sum()
print("storm cells:", len(cells), " rows:", int(cells.c.sum()), "= %.2f%% of all rows" % (cells.c.sum()/census.n.sum()*100))
for cur in ["EUR", "GBP", "CHF", "SGD", "CNY", "USD"]:
    print(f"  {cur}: {int(storm.get(cur,0)):>7,} storm rows = {storm.get(cur,0)/census.n[cur]*100:.2f}% of the currency's rows")
big = cells.sort_values("c", ascending=False).head(12)
import datetime
def tsd(d):
    return (datetime.datetime(2023, 4, 30) + datetime.timedelta(days=int(d))).strftime("%b %d")
print("biggest storms:")
for _, rr in big.iterrows():
    print(f"  {rr.cur} {rr.a:>12,.2f}  {tsd(rr.d)}  n={int(rr.c):>5}")

print("\nmultiplier ladder, June 9 EUR family of base 1159.42 (top 12):")
fam = con.execute(f"""
    SELECT USD_AMOUNT a, COUNT(*) c
    FROM read_parquet('{G}')
    WHERE CURRENCY_CODE = 'EUR' AND CAST((EPOCH_SECONDS - 1682832000)/86400 AS INT) = 40
      AND ANOMALY_TYPE IS NULL AND ABS(USD_AMOUNT/1159.42 - ROUND(USD_AMOUNT/1159.42)) < 1e-6
    GROUP BY 1 ORDER BY c DESC LIMIT 12
""").df()
fam["m"] = fam.a / 1159.42
fam = fam.sort_values("m")
print(fam.round(2).to_string(index=False))
fam_total = int(con.execute(f"""
    SELECT COUNT(*) FROM read_parquet('{G}')
    WHERE CURRENCY_CODE = 'EUR' AND CAST((EPOCH_SECONDS - 1682832000)/86400 AS INT) = 40
      AND ANOMALY_TYPE IS NULL AND ABS(USD_AMOUNT/1159.42 - ROUND(USD_AMOUNT/1159.42)) < 1e-6
""").fetchone()[0])
print("rows in this one family:", fam_total)

print("\ndaily EUR storm base drifts (top cell per day, c>=200, every 7th day):")
bases = con.execute(f"""
    WITH t AS (
      SELECT CAST((EPOCH_SECONDS - 1682832000)/86400 AS INT) d, USD_AMOUNT a, COUNT(*) c
      FROM read_parquet('{G}')
      WHERE CURRENCY_CODE = 'EUR' AND ANOMALY_TYPE IS NULL GROUP BY 1,2 HAVING COUNT(*) >= 200
    )
    SELECT d, a, c FROM t QUALIFY ROW_NUMBER() OVER (PARTITION BY d ORDER BY c DESC) = 1 ORDER BY d
""").df()
print(bases.iloc[::7].round(2).to_string(index=False))
print("base range: %.2f .. %.2f" % (bases.a.min(), bases.a.max()))

fig, ax = plt.subplots(figsize=(9.5, 4.8))
bars = ax.bar([f"\u00d7{int(round(m))}" for m in fam.m], fam.c, color=S.C_ACCENT, width=0.7)
S.vlabels(ax, bars, [f"{v:,}" for v in fam.c])
S.clean(ax)
S.title(ax, "A storm day: one amount, stamped in whole multiples",
        f"9 June 2023 (EUR): a base of 1,159.42 repeats in integer multiples - "
        f"{fam_total:,} payments in this one family.")
ax.set_xlabel("Multiple of the base amount (EUR 1,159.42)")
ax.set_ylabel("Payments on that day")
ax.set_ylim(0, fam.c.max() * 1.18)
savefig(fig, "g3_4_storms.png", group=GROUP)

# ---------------------------------------------------------------- 6. proof rows
print("\n=== 6. proof rows ===")
pr = con.execute(f"""
    SELECT EPOCH_SECONDS, BIC8_PATH, CURRENCY_CODE, USD_AMOUNT
    FROM read_parquet('{G}')
    WHERE (CURRENCY_CODE = 'EUR' AND USD_AMOUNT = 5667.0)
       OR (CURRENCY_CODE = 'EUR' AND CAST((EPOCH_SECONDS - 1682832000)/86400 AS INT) = 54
           AND USD_AMOUNT IN (1149.08, 11490.81))
       OR (CURRENCY_CODE = 'MC' OR upper(substr(split_part(BIC8_PATH,';',1),5,2)) = 'MC'
           AND ANOMALY_TYPE IS NULL AND USD_AMOUNT BETWEEN 30000 AND 32000)
    ORDER BY EPOCH_SECONDS LIMIT 8
""").df()
print(pr.to_string(index=False))

# =============================================================== 6. WHAT SETS THE CENTRE
# Rule 1 says: one shape, a per-country centre.  The next question a rule must
# answer is whether that centre is a free per-country value or a by-product of
# something observable (traffic, party mix, corridor mix).  Four tests, in order
# of how much they can rule out.
print("\n=== 6a. is the centre a fixed property of the country? (split half) ===")
h = con.execute(f"""
    SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc, half,
           COUNT(*) n, MEDIAN(log10(USD_AMOUNT)) mu
    FROM read_parquet('{G}')
    WHERE gap_head = FALSE AND ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
    GROUP BY 1,2
""").df()
m = (h[(h.half == 0) & (h.n >= 500)][["sc", "mu"]].rename(columns={"mu": "mu0"})
     .merge(h[(h.half == 1) & (h.n >= 500)][["sc", "mu"]].rename(columns={"mu": "mu1"}), on="sc"))
r_split = float(np.corrcoef(m.mu0, m.mu1)[0, 1])
print(f"  countries in both halves: {len(m)}   corr(mu half 0, mu half 1) = {r_split:.4f}")
print(f"  mean |difference| {np.abs(m.mu0-m.mu1).mean():.4f} dex, max {np.abs(m.mu0-m.mu1).max():.4f} dex")
print(f"  spread of the centre itself: sd {df.mu.std():.3f} dex "
      f"(range {df.mu.min():.3f} .. {df.mu.max():.3f})")
print(f"  -> between-country spread is {df.mu.std()/np.abs(m.mu0-m.mu1).mean():.0f}x "
      "the split-half noise")

print("\n=== 6b. does anything visible about the country predict the centre? ===")
comp = con.execute(f"""
    SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc, COUNT(*) n,
           AVG(CASE WHEN ORDERING_TYPE='B' THEN 1.0 ELSE 0 END) b_share,
           AVG(CASE WHEN BENEFICIARY_TYPE='B' THEN 1.0 ELSE 0 END) b_ben,
           AVG(CASE WHEN CURRENCY_CODE='USD' THEN 1.0 ELSE 0 END) usd_share,
           AVG(CASE WHEN CURRENCY_CODE='EUR' THEN 1.0 ELSE 0 END) eur_share,
           AVG(CASE WHEN upper(substr(split_part(BIC8_PATH,';',1),5,2))
                     <> upper(substr(split_part(BIC8_PATH,';',-1),5,2)) THEN 1.0 ELSE 0 END) cross_share,
           AVG(n_vis) mean_vis,
           AVG(CASE WHEN CURRENCY_CONVERSION_COUNT>0 THEN 1.0 ELSE 0 END) conv_share
    FROM read_parquet('{G}')
    WHERE gap_head = FALSE AND ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
    GROUP BY 1 HAVING COUNT(*) >= 2000
""").df()
comp = comp.merge(df[["sc", "mu"]], on="sc")
for c, nm in [("n", "traffic (log10)"), ("b_share", "business-sender share"),
              ("b_ben", "business-beneficiary share"), ("usd_share", "USD share"),
              ("eur_share", "EUR share"), ("cross_share", "cross-border share"),
              ("mean_vis", "mean visible banks"), ("conv_share", "conversion share")]:
    x = np.log10(comp.n) if c == "n" else comp[c]
    print(f"  corr(centre, {nm:28s}) = {np.corrcoef(comp.mu, x)[0,1]:+.3f}")
X = np.column_stack([np.log10(comp.n), comp.b_share, comp.b_ben, comp.usd_share,
                     comp.eur_share, comp.cross_share, comp.mean_vis, comp.conv_share])
X = (X - X.mean(0)) / X.std(0)
X = np.column_stack([np.ones(len(X)), X])
beta, *_ = np.linalg.lstsq(X, comp.mu.to_numpy(), rcond=None)
pred = X @ beta
r2 = 1 - ((comp.mu - pred) ** 2).sum() / ((comp.mu - comp.mu.mean()) ** 2).sum()
print(f"  multiple regression on all 8 observables: R-squared = {r2:.3f} (n={len(comp)})")
print("  -> most of the centre is NOT explained by anything else the file records")

print("\n=== 6c. hold the corridor fixed: sender dial vs destination mix ===")
cc = con.execute(f"""
    SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc, COUNT(*) n,
           MEDIAN(log10(USD_AMOUNT)) mu_us
    FROM read_parquet('{G}')
    WHERE gap_head = FALSE AND gap_tail = FALSE AND ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
      AND upper(substr(split_part(BIC8_PATH,';',-1),5,2)) = 'US'
    GROUP BY 1 HAVING COUNT(*) >= 500
""").df().merge(df[["sc", "mu"]], on="sc")
print(f"  countries sending to the US with >=500 rows: {len(cc)}; "
      f"corr(all-rows centre, to-US-only centre) = {np.corrcoef(cc.mu, cc.mu_us)[0,1]:+.3f}")
print(f"  centre spread, all rows {cc.mu.std():.3f} dex; to-US rows only {cc.mu_us.std():.3f} dex")
print("  -> the ladder is a property of the sender, not of who it pays")

print("\n=== 6d. party mix is additive, not the driver ===")
tt = con.execute(f"""
    SELECT upper(substr(split_part(BIC8_PATH,';',1),5,2)) sc, ORDERING_TYPE ot,
           COUNT(*) n, MEDIAN(log10(USD_AMOUNT)) mu
    FROM read_parquet('{G}')
    WHERE gap_head = FALSE AND ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0
    GROUP BY 1,2 HAVING COUNT(*) >= 300
""").df()
for t in ("B", "C"):
    s = tt[tt.ot == t]
    print(f"  within type {t}: {len(s)} countries, centre {s.mu.min():.3f} .. {s.mu.max():.3f} "
          f"(spread {s.mu.max()-s.mu.min():.3f} dex, sd {s.mu.std():.3f})")
print(f"  the full ladder is {df.mu.max()-df.mu.min():.3f} dex -> removing the type effect "
      "does not shrink it: party mix shifts the level, it does not create the ladder")

fig = plt.figure(figsize=(13.0, 5.3))
gs = fig.add_gridspec(1, 3, wspace=0.36)
ax = fig.add_subplot(gs[0, 0])
ax.scatter(m.mu0, m.mu1, s=18, color=S.C_ACCENT, alpha=0.65, linewidths=0)
lim = (m[["mu0", "mu1"]].min().min() - 0.15, m[["mu0", "mu1"]].max().max() + 0.15)
ax.plot(lim, lim, color=S.C_MUTED, ls="--", lw=1.2, label="Perfect agreement")
S.clean(ax, grid="both")
S.title(ax, "Fixed, not sampled",
        f"Two halves of the same rows: r = {r_split:.4f}.")
ax.set_xlabel("Country centre, first half (log10 USD)")
ax.set_ylabel("Country centre, second half (log10 USD)")
ax.set_xlim(*lim); ax.set_ylim(*lim)
ax.set_xticks([2, 3, 4]); ax.set_yticks([2, 3, 4])
ax.set_xticklabels(["$100", "$1k", "$10k"]); ax.set_yticklabels(["$100", "$1k", "$10k"])
S.legend_below(ax, ncol=1, y=-0.21)

ax = fig.add_subplot(gs[0, 1])
ax.scatter(df.mu, df.sigma, s=18, color=S.C_ACCENT, alpha=0.65, linewidths=0)
ax.axhline(df.sigma.median(), color=S.C_WARN, ls="--", lw=1.2,
           label=f"Median width {df.sigma.median():.2f} dex")
S.clean(ax, grid="both")
S.title(ax, "Only the centre moves",
        "Centre vs width, one dot per country.")
ax.set_xlabel("Country centre (log10 USD)")
ax.set_ylabel("Width of that country's amounts (log10 USD)")
ax.set_xticks([2, 3, 4]); ax.set_xticklabels(["$100", "$1k", "$10k"])
ax.set_ylim(0.85, 1.35)
S.legend_below(ax, ncol=1, y=-0.21)

ax = fig.add_subplot(gs[0, 2])
ax.scatter(cc.mu, cc.mu_us, s=26, color=S.C_ACCENT, alpha=0.75, linewidths=0)
lim2 = (cc[["mu", "mu_us"]].min().min() - 0.15, cc[["mu", "mu_us"]].max().max() + 0.15)
ax.plot(lim2, lim2, color=S.C_MUTED, ls="--", lw=1.2, label="Same as all rows")
S.clean(ax, grid="both")
S.title(ax, "Holding the corridor fixed",
        f"US payments only ({len(cc)} countries).")
ax.set_xlabel("Country centre, all its payments (log10 USD)")
ax.set_ylabel("Country centre, payments to the US only")
ax.set_xlim(*lim2); ax.set_ylim(*lim2)
ax.set_xticks([2, 3, 4]); ax.set_yticks([2, 3, 4])
ax.set_xticklabels(["$100", "$1k", "$10k"]); ax.set_yticklabels(["$100", "$1k", "$10k"])
S.legend_below(ax, ncol=1, y=-0.21)
savefig(fig, "g3_5_country_centre.png", group=GROUP)

comp.to_pickle(os.path.join(AGG, "_g3_centre_predictors.pkl"))
print("\nDONE g3")
