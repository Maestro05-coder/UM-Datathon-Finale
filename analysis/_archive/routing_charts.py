"""ROUTING: generate dashboard charts (PNG)."""
import pandas as pd, numpy as np, pickle, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from load_data import load_core

OUT = "charts"; os.makedirs(OUT, exist_ok=True)
df = load_core()
with open("bank_cur.pkl","rb") as f: bank_cur = pickle.load(f)
paths = df["BIC8_PATH"].map(lambda p: [s for s in str(p).split(";") if s])
df["vis"] = paths.map(lambda l: [s for s in l if s != "..."])
df["n_vis"] = df["vis"].map(len)
df["has_gap"] = df["BIC8_PATH"].str.contains(r"\.\.\.", na=False).fillna(False)

# ---------- Chart 1: type vs visible path length ----------
ct = pd.crosstab(df.n_vis, df.TRANSACTION_TYPE_CODE)
fig, ax = plt.subplots(figsize=(8,4.5))
bottom = np.zeros(len(ct))
colors = {"Direct":"#2b6cb0","Indirect":"#dd6b20","Covered":"#38a169"}
for t in ["Direct","Indirect","Covered"]:
    ax.bar(ct.index.astype(str), ct[t], bottom=bottom, label=t, color=colors[t])
    bottom += ct[t].values
ax.set_yscale("log"); ax.set_xlabel("Visible BICs in BIC8_PATH")
ax.set_ylabel("Payments (log)"); ax.set_title("Routing type is a deterministic function of visible path length")
ax.legend()
ax.annotate("Direct = exactly 2 participants (100%)", xy=(0, 6.6e5), xytext=(0.5, 2e5),
            arrowprops=dict(arrowstyle="->"))
plt.tight_layout(); plt.savefig(f"{OUT}/routing_1_type_vs_pathlen.png", dpi=150); plt.close()

# ---------- Chart 2: QFLAG <-> gap ----------
tab = pd.crosstab(df.has_gap, df.CONTINUITY_QFLAG)
fig, ax = plt.subplots(figsize=(6,4))
x = ["no '...' in path", "'...' in path"]
yY = [tab.loc[False,"Y"], tab.loc[True,"Y"]]
yN = [tab.loc[False,"N"], tab.loc[True,"N"]]
ax.bar(x, yY, label="QFLAG=Y", color="#2b6cb0")
ax.bar(x, yN, bottom=yY, label="QFLAG=N", color="#c53030")
for i,(a,b) in enumerate(zip(yY,yN)):
    tot = a+b
    ax.text(i, tot*1.02, f"Y: {a/tot:.1%}\nN: {b/tot:.1%}", ha="center")
ax.set_yscale("log"); ax.set_ylabel("Payments (log)")
ax.set_title("CONTINUITY_QFLAG is 100% determined by presence of '...' in BIC8_PATH")
ax.legend()
plt.tight_layout(); plt.savefig(f"{OUT}/routing_2_qflag_gap.png", dpi=150); plt.close()

# ---------- Chart 3: conversion rule ----------
cont = df[~df.has_gap].copy()
def predict(row):
    return sum(1 for i in range(len(row["vis"])-1)
               if bank_cur.get(row["vis"][i]) != bank_cur.get(row["vis"][i+1])
               and bank_cur.get(row["vis"][i]) is not None and bank_cur.get(row["vis"][i+1]) is not None)
cont["pred"] = cont.apply(predict, axis=1)
known = cont["vis"].map(lambda l: all(bank_cur.get(b) is not None for b in l))
s = cont[known]
agree = (s.pred == s.CURRENCY_CONVERSION_COUNT)
mx = max(s.pred.max(), s.CURRENCY_CONVERSION_COUNT.max())
hm = np.zeros((mx+1, mx+1))
for a,b in zip(s.pred, s.CURRENCY_CONVERSION_COUNT):
    hm[a,b] += 1
fig, ax = plt.subplots(figsize=(6.5,5.5))
im = ax.imshow(np.log10(hm+1), origin="lower", cmap="Blues")
ax.set_xlabel("Reconstructed: adjacent pairs with differing bank currency")
ax.set_ylabel("CURRENCY_CONVERSION_COUNT in data")
ax.set_title(f"FX hops reconstructed from path currencies\nagreement = {agree.mean():.2%} (n={len(s):,})")
plt.colorbar(im, label="log10 count")
plt.tight_layout(); plt.savefig(f"{OUT}/routing_3_conversion_rule.png", dpi=150); plt.close()

# ---------- Chart 4: anomaly x type ----------
ct2 = pd.crosstab(df.ANOMALY_TYPE, df.TRANSACTION_TYPE_CODE)
order = ["ROMANCE_SCAM","CEO_SCAM","ACCOUNT_REPLACEMENT_SCAM","DUPLICATE_PAYMENT","FAT_FINGER_MISTAKE","CUSTOMER_RECALL"]
ct2 = ct2.loc[[o for o in order if o in ct2.index]]
p = ct2.div(ct2.sum(axis=1), axis=0)
fig, ax = plt.subplots(figsize=(9,4.5))
bottom = np.zeros(len(p))
for t in ["Direct","Indirect","Covered"]:
    ax.barh(p.index, p[t], left=bottom, color=colors[t], label=t)
    bottom += p[t].values
for i,(idx,row) in enumerate(p.iterrows()):
    ax.text(1.01, i, f"n={ct2.loc[idx].sum():,}", va="center", fontsize=9)
ax.set_xlabel("Share of anomaly rows"); ax.set_title("Fraud anomalies never occur on Covered routes (0 of 1,316 fraud payments)")
ax.legend(loc="lower right")
plt.tight_layout(); plt.savefig(f"{OUT}/routing_4_anomaly_type.png", dpi=150); plt.close()

# ---------- Chart 5: endpoint mismatch ----------
df["first_mism"] = df["vis"].map(lambda l: l[0]) != df.ORDERING_BIC8
df["last_mism"]  = df["vis"].map(lambda l: l[-1]) != df.BENEFICIARY_BIC8
r = df.groupby("TRANSACTION_TYPE_CODE")[["first_mism","last_mism"]].mean() * 100
fig, ax = plt.subplots(figsize=(6.5,4))
x = np.arange(len(r)); w=0.35
ax.bar(x-w/2, r.first_mism, w, label="path start != ORDERING_BIC8", color="#2b6cb0")
ax.bar(x+w/2, r.last_mism, w, label="path end != BENEFICIARY_BIC8", color="#dd6b20")
for i,v in enumerate(r.first_mism): ax.text(i-w/2, v+0.1, f"{v:.1f}%", ha="center", fontsize=9)
for i,v in enumerate(r.last_mism): ax.text(i+w/2, v+0.1, f"{v:.1f}%", ha="center", fontsize=9)
ax.set_xticks(x); ax.set_xticklabels(r.index)
ax.set_ylabel("% of payments"); ax.set_ylim(0,7)
ax.set_title("Endpoint labels disagree with the path on ~5% of rows per endpoint\n(independent of routing type, and of each other)")
ax.legend()
plt.tight_layout(); plt.savefig(f"{OUT}/routing_5_mismatch.png", dpi=150); plt.close()

# ---------- Chart 6: hub concentration of intermediaries ----------
inter = df["vis"].map(lambda l: [str(b)[4:6] for b in l[1:-1]] if len(l) >= 3 else [])
flat = pd.Series([c for l in inter for c in l])
mid_share = flat.value_counts(normalize=True)
end_share = pd.concat([df.ORDERING_BIC8.str[4:6], df.BENEFICIARY_BIC8.str[4:6]]).value_counts(normalize=True)
comp = pd.DataFrame({"as intermediary": mid_share, "as endpoint": end_share}).head(12)
comp["ratio"] = comp["as intermediary"] / comp["as endpoint"]
comp = comp.sort_values("ratio", ascending=False)
fig, ax = plt.subplots(figsize=(8,4.5))
x = np.arange(len(comp)); w=0.38
ax.bar(x-w/2, comp["as intermediary"]*100, w, label="share of intermediary hops", color="#2b6cb0")
ax.bar(x+w/2, comp["as endpoint"]*100, w, label="share of endpoints", color="#a0aec0")
ax.set_xticks(x); ax.set_xticklabels(comp.index)
ax.set_ylabel("% share"); ax.legend()
ax.set_title("US/CH/GB are over-represented as intermediaries vs endpoints (correspondent hubs)")
plt.tight_layout(); plt.savefig(f"{OUT}/routing_6_hubs.png", dpi=150); plt.close()
print(comp.round(3).to_string())
print("charts saved to", os.path.abspath(OUT))
