"""ROUTING follow-up 2: what makes Covered different; anatomy of endpoint mismatches."""
import pandas as pd, numpy as np
from load_data import load_core
pd.set_option("display.width", 220)

df = load_core()
paths = df["BIC8_PATH"].map(lambda p: [s for s in str(p).split(";") if s])
df["vis"] = paths.map(lambda l: [s for s in l if s != "..."])
df["n_vis"] = df["vis"].map(len)
df["has_gap"] = df["BIC8_PATH"].str.contains(r"\.\.\.", na=False).fillna(False)
df["first_mism"] = df["vis"].map(lambda l: l[0]) != df.ORDERING_BIC8
df["last_mism"]  = df["vis"].map(lambda l: l[-1]) != df.BENEFICIARY_BIC8
df["any_mism"] = df.first_mism | df.last_mism

print("== mismatch rate by type ==")
print(df.groupby("TRANSACTION_TYPE_CODE")[["first_mism","last_mism","any_mism"]].mean())
print("\n== mismatch rate by type x gap ==")
print(df.groupby(["TRANSACTION_TYPE_CODE","has_gap"]).any_mism.mean())

print("\n== mismatch rows: is mismatch bank a plausible correspondent of the true endpoint? ==")
mm = df[df.any_mism].copy()
mm["mism_bank"] = np.where(mm.first_mism, mm["vis"].map(lambda l: l[0]), mm["vis"].map(lambda l: l[-1]))
mm["true_bank"] = np.where(mm.first_mism, mm.ORDERING_BIC8, mm.BENEFICIARY_BIC8)
print("n mismatch rows:", len(mm))
print("mismatch bank country distribution top10:",
      mm.mism_bank.str[4:6].value_counts().head(10).to_dict())
print("true bank country distribution top10:",
      mm.true_bank.str[4:6].value_counts().head(10).to_dict())
print("same country (mism vs true) rate:", (mm.mism_bank.str[4:6] == mm.true_bank.str[4:6]).mean())
print("same bank-code prefix (first 4 chars) rate:", (mm.mism_bank.str[:4] == mm.true_bank.str[:4]).mean())
# is the mismatch bank anywhere else in the path?
mm["mism_in_path_twice"] = mm.apply(lambda r: r.BIC8_PATH.count(r.mism_bank) >= 2, axis=1)
print("mismatch bank appears 2+ times in path:", mm.mism_in_path_twice.mean())
# how often is the TRUE endpoint bank entirely absent from the path?
mm["true_absent"] = ~mm.apply(lambda r: r.true_bank in r.BIC8_PATH, axis=1)
print("true endpoint bank absent from path entirely:", mm.true_absent.mean())
print("\nsample mismatch rows:")
print(mm[["ORDERING_BIC8","BENEFICIARY_BIC8","BIC8_PATH","TRANSACTION_TYPE_CODE","has_gap"]].head(10).to_string())

# ---------- Covered vs Indirect: control for pc, compare conditional distributions ----------
print("\n== Covered vs Indirect controlling for pc and conversion count ==")
sub = df[df.TRANSACTION_TYPE_CODE.isin(["Covered","Indirect"])]
for pc in [3,4,5]:
    for cv in [0,1,2]:
        s = sub[(sub.PARTICIPANT_COUNT==pc)&(sub.CURRENCY_CONVERSION_COUNT==cv)]
        if len(s) > 200:
            m = s.groupby("TRANSACTION_TYPE_CODE").USD_AMOUNT.median()
            d = s.groupby("TRANSACTION_TYPE_CODE").TOTAL_DURATION.median()
            print(f"pc={pc} conv={cv}: n={len(s)}, median amount C={m.get('Covered',np.nan):.0f} I={m.get('Indirect',np.nan):.0f}, median dur C={d.get('Covered',np.nan):.0f} I={d.get('Indirect',np.nan):.0f}")

# third-currency hypothesis: currency != currency of either endpoint country
# infer country->dominant currency from data
df["oc"] = df.ORDERING_BIC8.str[4:6]; df["bc"] = df.BENEFICIARY_BIC8.str[4:6]
cur_by_cty = df.groupby("oc").CURRENCY_CODE.agg(lambda s: s.value_counts().idxmax())
print("\ncountry->dominant currency:", cur_by_cty.to_dict())
df["oc_cur"] = df.oc.map(cur_by_cty)
cur_by_bcty = df.groupby("bc").CURRENCY_CODE.agg(lambda s: s.value_counts().idxmax())
df["bc_cur"] = df.bc.map(cur_by_bcty)
df["third_cur"] = (df.CURRENCY_CODE != df.oc_cur) & (df.CURRENCY_CODE != df.bc_cur)
print("\nthird-currency rate by type:\n", df.groupby("TRANSACTION_TYPE_CODE").third_cur.mean())
print("party-type mix by type:\n", pd.crosstab([df.ORDERING_TYPE,df.BENEFICIARY_TYPE], df.TRANSACTION_TYPE_CODE, normalize="columns"))
print("\nanomaly mix by type:\n", pd.crosstab(df.ANOMALY_TYPE, df.TRANSACTION_TYPE_CODE, normalize="columns").round(4))
