"""ROUTING verify H6b: conversion_count = # participants whose local currency != payment currency."""
import pandas as pd, numpy as np
from load_data import load_core
pd.set_option("display.width", 220)

df = load_core()
paths = df["BIC8_PATH"].map(lambda p: [s for s in str(p).split(";") if s])
df["vis"] = paths.map(lambda l: [s for s in l if s != "..."])
df["has_gap"] = df["BIC8_PATH"].str.contains(r"\.\.\.", na=False).fillna(False)
df["n_vis"] = df["vis"].map(len)

oc = df.ORDERING_BIC8.str[4:6]; bc = df.BENEFICIARY_BIC8.str[4:6]
allc = pd.concat([oc, bc])
cur_by_cty = (pd.DataFrame({"cur": np.repeat(df.CURRENCY_CODE.to_numpy(), 2), "cc": allc.to_numpy()})
              .groupby("cc").cur.agg(lambda s: s.value_counts().idxmax()))

# continuous paths only first
cont = df[~df.has_gap]
def conv_pred(row):
    return sum(1 for b in row["vis"] if cur_by_cty.get(str(b)[4:6]) != row.CURRENCY_CODE)
pred = cont.apply(conv_pred, axis=1)
agree = pred == cont.CURRENCY_CONVERSION_COUNT
print("H6b continuous: agreement =", round(agree.mean(), 6))
print(pd.crosstab(pred, cont.CURRENCY_CONVERSION_COUNT).head(6))
bad = cont[~agree]
print("\nmismatch examples (pred vs actual):")
print(bad[["ORDERING_BIC8","BENEFICIARY_BIC8","BIC8_PATH","CURRENCY_CODE","CURRENCY_CONVERSION_COUNT"]].head(8).to_string())
print("\n disagreement magnitude:", (bad.CURRENCY_CONVERSION_COUNT - bad[~agree].index.map(pred)).abs().value_counts().head(5).to_dict()
      if len(bad) else "none")

# variant: exclude endpoints (only intermediaries)?
def conv_pred_mid(row):
    return sum(1 for b in row["vis"][1:-1] if cur_by_cty.get(str(b)[4:6]) != row.CURRENCY_CODE)
pred_mid = cont.apply(conv_pred_mid, axis=1)
print("\nvariant intermediaries-only agreement:", (pred_mid == cont.CURRENCY_CONVERSION_COUNT).mean())

# check on Direct subset specifically (cleanest)
direct = cont[cont.TRANSACTION_TYPE_CODE=="Direct"]
pd_direct = direct.apply(conv_pred, axis=1)
print("Direct subset agreement:", (pd_direct == direct.CURRENCY_CONVERSION_COUNT).mean())
print(pd.crosstab(pd_direct, direct.CURRENCY_CONVERSION_COUNT))

# gapped rows: prediction using visible only
g = df[df.has_gap]
gp = g.apply(conv_pred, axis=1)
print("\ngapped rows agreement (visible only):", (gp == g.CURRENCY_CONVERSION_COUNT).mean())
print("conv - pred distribution:", (g.CURRENCY_CONVERSION_COUNT - gp).value_counts().sort_index().head(8).to_dict())
