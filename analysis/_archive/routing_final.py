"""ROUTING final: conversion=crossings rule, anomaly x type counts, covered duration."""
import pandas as pd, numpy as np
from load_data import load_core
pd.set_option("display.width", 220)

df = load_core()
paths = df["BIC8_PATH"].map(lambda p: [s for s in str(p).split(";") if s])
df["vis"] = paths.map(lambda l: [s for s in l if s != "..."])
df["has_gap"] = df["BIC8_PATH"].str.contains(r"\.\.\.", na=False).fillna(False)

# ---- country -> dominant currency map (from data itself) ----
oc = df.ORDERING_BIC8.str[4:6]; bc = df.BENEFICIARY_BIC8.str[4:6]
allc = pd.concat([oc, bc])
cur_by_cty = (pd.DataFrame({"cur": np.repeat(df.CURRENCY_CODE.to_numpy(), 2),
                            "cc": allc.to_numpy()})
              .groupby("cc").cur.agg(lambda s: s.value_counts().idxmax()))
print("map size:", len(cur_by_cty))

# ---- H6: conversion_count == # adjacent currency-boundary crossings (continuous paths) ----
cont = df[~df.has_gap]
def crossings(row):
    banks = row["vis"]
    cc = [str(b)[4:6] for b in banks]
    curs = [cur_by_cty.get(c) for c in cc]
    return sum(1 for i in range(len(curs)-1) if curs[i] != curs[i+1])
cross = cont.apply(crossings, axis=1)
agree = (cross == cont.CURRENCY_CONVERSION_COUNT)
print("\nH6 continuous paths: conversion_count == crossings, agreement =", round(agree.mean(), 6))
print(pd.crosstab(cross, cont.CURRENCY_CONVERSION_COUNT).head(8))

# gapped rows: does the rule still hold if we only count visible crossings + assume each gap adds its own?
g = df[df.has_gap]
gcross = g.apply(crossings, axis=1)
print("\ngapped rows agreement (visible-only crossings):", (gcross == g.CURRENCY_CONVERSION_COUNT).mean())
print("gapped rows: conv minus visible-crossings distribution:")
print((g.CURRENCY_CONVERSION_COUNT - gcross).value_counts().sort_index())

# ---- anomaly x type: clean counts ----
print("\n== counts: anomaly type x routing type ==")
ct = pd.crosstab(df.ANOMALY_TYPE, df.TRANSACTION_TYPE_CODE)
ct["TOTAL"] = ct.sum(axis=1)
print(ct)
print("\nrow share of each anomaly within its type:")
print((ct.drop(columns="TOTAL").div(ct.drop(columns="TOTAL").sum(axis=0), axis=1) * 1).round(4))
print("\nP(type | anomaly):")
pt = ct.drop(columns="TOTAL").div(ct.drop(columns="TOTAL").sum(axis=1), axis=0)
print(pt.round(4))
print("\noverall anomaly prevalence:", df.ANOMALY_TYPE.notna().mean())

# ---- Covered vs Indirect duration at fixed pc & conv (matched comparison) ----
print("\n== duration Covered vs Indirect, matched on (pc, conv) ==")
sub = df[df.TRANSACTION_TYPE_CODE.isin(["Covered","Indirect"]) & ~df.has_gap]
rows = []
for pc in [3,4,5]:
    for cv in [1,2,3]:
        s = sub[(sub.PARTICIPANT_COUNT==pc)&(sub.CURRENCY_CONVERSION_COUNT==cv)]
        if len(s) > 300:
            m = s.groupby("TRANSACTION_TYPE_CODE").TOTAL_DURATION.median()
            rows.append((pc, cv, len(s), m.get("Covered",np.nan), m.get("Indirect",np.nan),
                         m.get("Covered",np.nan)/m.get("Indirect",np.nan)))
print(pd.DataFrame(rows, columns=["pc","conv","n","Covered_med_dur","Indirect_med_dur","ratio"]).to_string())

# ---- Covered probability vs amount (soft rule?) ----
sub2 = df[df.TRANSACTION_TYPE_CODE.isin(["Covered","Indirect"])].copy()
sub2["dec"] = pd.qcut(sub2.USD_AMOUNT, 10, labels=False, duplicates="drop")
p = sub2.groupby("dec").apply(lambda g: (g.TRANSACTION_TYPE_CODE=="Covered").mean())
print("\nP(Covered | multi-hop) by USD_AMOUNT decile:")
print(p.round(4).to_string())

# ---- gap rate by type and hop count ----
print("\ngap rate by (type, n_vis):")
sub3 = df.copy(); sub3["n_vis"] = sub3["vis"].map(len)
print(pd.crosstab(sub3[sub3.PARTICIPANT_COUNT<=5].n_vis, sub3[sub3.PARTICIPANT_COUNT<=5].TRANSACTION_TYPE_CODE, normalize="index").round(3))
