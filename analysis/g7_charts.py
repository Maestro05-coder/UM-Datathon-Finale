"""g7 charts - simple, one idea per picture, rendered from full-data DuckDB.

Every number is exact (all 10,000,000 rows, cache_party/). Run:
    python analysis/g7_charts.py
Charts land in analysis/groups/g7_parties/.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ddb, full_glob, PARTY_CACHE, savefig

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import _style as S

S.apply()
GROUP = "g7_parties"
TOTAL = 10_000_000
con = ddb()
P = full_glob(PARTY_CACHE)


def q(sql):
    return con.execute(sql).df()


# ------------------------------------------------------------------ 1. account pools
print("1. account reuse")
reuse = q(f"""
    WITH u AS (
      SELECT 'Sender' side, ORDERING_ACCOUNT acct, COUNT(*) n
      FROM read_parquet('{P}') WHERE ORDERING_ACCOUNT IS NOT NULL GROUP BY 2
      UNION ALL
      SELECT 'Beneficiary', BENEFICIARY_ACCOUNT, COUNT(*)
      FROM read_parquet('{P}') WHERE BENEFICIARY_ACCOUNT IS NOT NULL GROUP BY 2
    )
    SELECT side,
           CASE WHEN n = 1 THEN '1' WHEN n < 5 THEN '2-4' WHEN n < 10 THEN '5-9'
                WHEN n < 50 THEN '10-49' ELSE '50+' END AS bucket,
           COUNT(*) AS accounts, SUM(n) AS payments
    FROM u GROUP BY 1, 2
""")
order = ["1", "2-4", "5-9", "10-49", "50+"]
send = reuse[reuse.side == "Sender"].set_index("bucket").reindex(order)
bene = reuse[reuse.side == "Beneficiary"].set_index("bucket").reindex(order)
print(reuse.to_string(index=False))

fig, axs = plt.subplots(1, 2, figsize=(12.0, 4.8))

ax = axs[0]
x = np.arange(len(order))
w = 0.38
b1 = ax.bar(x - w / 2, send.accounts / send.accounts.sum() * 100, w,
            color=S.C_ACCENT, label=f"Senders ({send.accounts.sum():,} accounts)")
b2 = ax.bar(x + w / 2, bene.accounts / bene.accounts.sum() * 100, w,
            color=S.C_GREY, label=f"Beneficiaries ({bene.accounts.sum():,} accounts)")
S.clean(ax)
S.title(ax, "Most senders pay again; most beneficiaries are one-off",
        "How many payments each account makes, as a share of that side's accounts.")
ax.set_xlabel("Payments made by the account")
ax.set_ylabel("Share of accounts")
ax.set_xticks(x)
ax.set_xticklabels(order)
ax.set_ylim(0, 100)
S.pct_axis(ax, "y", step=20, xmax=100)
for bars, vals in [(b1, send.accounts / send.accounts.sum() * 100),
                   (b2, bene.accounts / bene.accounts.sum() * 100)]:
    S.vlabels(ax, bars, [f"{v:.0f}%" for v in vals], fontsize=8.5)
S.legend_below(ax, ncol=2, y=-0.22)

ax = axs[1]
share_pay = send.payments / send.payments.sum() * 100
bars = ax.bar(x, share_pay, color=S.C_ACCENT, width=0.62)
S.vlabels(ax, bars, [f"{v:.0f}%" for v in share_pay])
S.clean(ax)
S.title(ax, "A few big senders carry almost all the payments",
        f"The {int(send.accounts.iloc[-1]):,} senders with 50+ payments send "
        f"{share_pay.iloc[-1]:.0f}% of everything.")
ax.set_xlabel("Payments made by the sender account")
ax.set_ylabel("Share of all 10,000,000 payments")
ax.set_xticks(x)
ax.set_xticklabels(order)
ax.set_ylim(0, 100)
S.pct_axis(ax, "y", step=20, xmax=100)
fig.tight_layout()
savefig(fig, "g7_1_accounts.png", group=GROUP)

# ------------------------------------------------------------------ 2. what is in DETAILS
print("\n2. token vocabulary")
TOKENS = ["chr", "street", "business", "city", "country_code", "line_break", "iban",
          "post_code", "other_words", "country_name", "company_keyword", "last_name"]
cols = ",\n           ".join(
    f"AVG(CASE WHEN ORDERING_TOKENS LIKE '%<{t}:%' THEN 1.0 ELSE 0 END) AS {t}" for t in TOKENS)
row = q(f"""
    SELECT {cols}
    FROM read_parquet('{P}') WHERE ORDERING_TOKENS IS NOT NULL
""").iloc[0]
tok = (row * 100).sort_values()
print(tok.round(2).to_string())

fig, ax = plt.subplots(figsize=(9.5, 5.4))
bars = ax.barh(tok.index, tok.values, color=S.C_ACCENT, height=0.72)
S.clean(ax, grid="x")
S.title(ax, "Every detail is built from a short list of text blocks",
        "Share of payments whose DETAILS contains each block (TOKENS is the template).")
ax.set_xlabel("Share of all 10,000,000 payments")
ax.set_ylabel("Block in the addressee details")
ax.set_xlim(0, 100)
S.pct_axis(ax, "x", step=20, xmax=100)
S.hlabels(ax, bars, [f"{v:.0f}%" for v in tok.values])
savefig(fig, "g7_2_tokens.png", group=GROUP)

# ------------------------------------------------------------------ 3. the decoy rule
print("\n3. decoy: address country vs bank country")
match = q(f"""
    WITH c AS (
      SELECT regexp_extract(ORDERING_TOKENS, '(country_code|country_name):([A-Z]{{2}})', 2) dc,
             upper(substr(ORDERING_BIC8, 5, 2)) bc
      FROM read_parquet('{P}') WHERE ORDERING_TOKENS IS NOT NULL)
    SELECT 'Sender' side, COUNT(*) n, AVG(CASE WHEN dc = bc THEN 1.0 ELSE 0 END) match
    FROM c WHERE dc != ''
    UNION ALL
    SELECT 'Beneficiary', COUNT(*), AVG(CASE WHEN dc = bc THEN 1.0 ELSE 0 END)
    FROM (
      SELECT regexp_extract(BENEFICIARY_TOKENS, '(country_code|country_name):([A-Z]{{2}})', 2) dc,
             upper(substr(BENEFICIARY_BIC8, 5, 2)) bc
      FROM read_parquet('{P}') WHERE BENEFICIARY_TOKENS IS NOT NULL) WHERE dc != ''
""")
print(match.to_string(index=False))
addr = q(f"""
    WITH c AS (SELECT regexp_extract(BENEFICIARY_TOKENS,
                    '(country_code|country_name):([A-Z]{{2}})', 2) dc
               FROM read_parquet('{P}') WHERE BENEFICIARY_TOKENS IS NOT NULL)
    SELECT dc, COUNT(*) n FROM c WHERE dc != '' GROUP BY 1 ORDER BY n DESC LIMIT 8
""")
bank = q(f"""
    SELECT upper(substr(BENEFICIARY_BIC8, 5, 2)) dc, COUNT(*) n
    FROM read_parquet('{P}') GROUP BY 1
""").set_index("dc").n
addr["addr_pct"] = addr.n / TOTAL * 100
addr["bank_pct"] = [bank.get(c, 0) / TOTAL * 100 for c in addr.dc]
print(addr.to_string(index=False))

fig, axs = plt.subplots(1, 2, figsize=(12.0, 5.0), gridspec_kw={"width_ratios": [1.65, 1]})

ax = axs[0]
y = np.arange(len(addr))[::-1]
h = 0.36
ax.barh(y + h / 2, addr.addr_pct, h, color=S.C_WARN, label="Country written in the address")
ax.barh(y - h / 2, addr.bank_pct, h, color=S.C_ACCENT, label="Country of the beneficiary bank")
ax.set_yticks(y)
ax.set_yticklabels(addr.dc)
S.clean(ax, grid="x")
S.title(ax, "The address world is not the bank world",
        "Top 8 address countries, next to the bank's country, as a share of all payments.")
ax.set_xlabel("Share of all 10,000,000 payments")
ax.set_ylabel("Country")
ax.set_xlim(0, max(addr.addr_pct.max(), addr.bank_pct.max()) * 1.25)
S.pct_axis(ax, "x", step=5, xmax=100)
S.legend_below(ax, ncol=1, y=-0.17)

ax = axs[1]
vals = [match.match.iloc[0] * 100, match.match.iloc[1] * 100]
bars = ax.bar(["Sender", "Beneficiary"], vals, color=[S.C_ACCENT, S.C_WARN], width=0.55)
for bar, v in zip(bars, vals):
    ax.annotate(f"{v:.2f}%" if v < 10 else f"{v:.0f}%",
                xy=(bar.get_x() + bar.get_width() / 2, v), xytext=(0, 4),
                textcoords="offset points", ha="center", va="bottom",
                fontsize=12, fontweight="bold")
S.clean(ax)
S.title(ax, "Only the sender's address is real",
        "Share of rows where the address country equals the bank's country.")
ax.set_xlabel("Side of the payment")
ax.set_ylabel("Address country = bank country")
ax.set_ylim(0, 108)
S.pct_axis(ax, "y", step=25, xmax=100)
ax.set_xticks([0, 1])
ax.set_xticklabels([f"Sender\n{match.n.iloc[0]:,} rows",
                    f"Beneficiary\n{match.n.iloc[1]:,} rows"], fontsize=10)
fig.tight_layout()
savefig(fig, "g7_3_country_decoy.png", group=GROUP)

# ------------------------------------------------------------------ 4. B = business, C = person
print("\n4. type semantics")
ts = q(f"""
    SELECT ORDERING_TYPE ot, ANOMALY_TYPE IS NOT NULL anom,
           AVG(CASE WHEN ORDERING_TOKENS LIKE '%<business:%'
                      OR ORDERING_TOKENS LIKE '%<company_keyword:%' THEN 1.0 ELSE 0 END) p_business,
           AVG(CASE WHEN ORDERING_TOKENS LIKE '%<first_name:%'
                      OR ORDERING_TOKENS LIKE '%<last_name:%' THEN 1.0 ELSE 0 END) p_person,
           COUNT(*) n
    FROM read_parquet('{P}') WHERE ORDERING_TOKENS IS NOT NULL
    GROUP BY 1, 2 ORDER BY 1, 2
""")
print(ts.round(4).to_string(index=False))

rows = []
for _, r in ts.iterrows():
    label = f"Type {r.ot} - {'anomalous' if r.anom else 'normal'}  (n={r.n:,})"
    biz = r.p_business * 100
    person = r.p_person * 100
    rows.append((label, biz, person, max(0.0, 100 - biz - person)))

fig, ax = plt.subplots(figsize=(10.5, 3.9))
ylabels = [r[0] for r in rows]
y = np.arange(len(rows))[::-1]
left = np.zeros(len(rows))
segs = [(1, "Business / company words", S.C_ACCENT),
        (2, "Person-name words", S.C_WARN),
        (3, "Neither", S.C_GREY_SOFT)]
for idx, name, col in segs:
    vals = np.array([r[idx] for r in rows])
    ax.barh(y, vals, left=left, color=col, height=0.62, label=name)
    for yy, vv, ll in zip(y, vals, left):
        if vv >= 6:
            ax.annotate(f"{vv:.0f}%", xy=(ll + vv / 2, yy), ha="center", va="center",
                        fontsize=10.5, color="white" if col != S.C_GREY_SOFT else S.C_TEXT,
                        fontweight="bold")
    left += vals
ax.set_yticks(y)
ax.set_yticklabels(ylabels)
S.clean(ax, grid="x")
S.title(ax, "Type B means business, type C means person",
        "What the sender's text blocks say, as a share of the rows of each type.")
ax.set_xlabel("Share of rows of that type")
ax.set_ylabel("Sender type")
ax.set_xlim(0, 100)
S.pct_axis(ax, "x", step=20, xmax=100)
S.legend_below(ax, ncol=3, y=-0.28)
savefig(fig, "g7_4_type_semantics.png", group=GROUP)

print("\nDONE g7 charts")
