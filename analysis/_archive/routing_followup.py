"""ROUTING follow-up: Covered-vs-Indirect differentiator + gap anatomy."""
import pandas as pd, numpy as np
from load_data import load_core
pd.set_option("display.width", 220)

df = load_core()
paths = df["BIC8_PATH"].map(lambda p: [s for s in str(p).split(";") if s])
df["path_first"] = paths.map(lambda l: l[0])
df["path_last"]  = paths.map(lambda l: l[-1])
df["has_gap"]    = df["BIC8_PATH"].str.contains(r"\.\.\.", na=False).fillna(False)
df["vis"]        = paths.map(lambda l: [s for s in l if s != "..."])
df["n_vis"]      = df["vis"].map(len)
df["n_hidden"]   = paths.map(lambda l: l.count("..."))
df["gap_head"]   = paths.map(lambda l: l[0] == "...")
df["gap_tail"]   = paths.map(lambda l: l[-1] == "...")
df["mid"]        = df["vis"].map(lambda l: l[1:-1] if len(l) >= 3 else [])
df["dup_bic"]    = df["vis"].map(lambda l: len(set(l)) != len(l))
df["first_mism"] = df.path_first != df.ORDERING_BIC8
df["last_mism"]  = df.path_last != df.BENEFICIARY_BIC8

print("== mismatch vs gap ==")
print(pd.crosstab([df.has_gap], [df.first_mism, df.last_mism]))
print("\n== gap position: head/tail/only-middle by type ==")
print(df.groupby("TRANSACTION_TYPE_CODE")[["gap_head","gap_tail","n_hidden"]].mean())
print("\n== sample gapped Direct paths ==")
print(df[(df.TRANSACTION_TYPE_CODE=="Direct") & df.has_gap]["BIC8_PATH"].head(8).to_string())
print("\n== sample gapped Indirect paths ==")
print(df[(df.TRANSACTION_TYPE_CODE=="Indirect") & df.has_gap]["BIC8_PATH"].head(8).to_string())

print("\n== Covered vs Indirect candidates ==")
sub = df[df.TRANSACTION_TYPE_CODE.isin(["Covered","Indirect"])]
print("dup BIC in path rate:", sub.groupby("TRANSACTION_TYPE_CODE").dup_bic.mean())
# middle bank is USD-clearing (US) ?
sub2 = sub.copy()
sub2["mid_us"] = sub2["mid"].map(lambda l: any(str(b)[4:6]=="US" for b in l) if len(l)>0 else False)
print("any-US-intermediary rate:\n", sub2.groupby("TRANSACTION_TYPE_CODE").mid_us.mean())
# currency USD?
sub2["cur_usd"] = sub2.CURRENCY_CODE == "USD"
print("\npayment currency==USD rate:\n", sub2.groupby("TRANSACTION_TYPE_CODE").cur_usd.mean())
# conversion count distribution by type
print("\nconversion count by type:\n", pd.crosstab(sub2.CURRENCY_CONVERSION_COUNT, sub2.TRANSACTION_TYPE_CODE, normalize="columns").head(6))
# ordering/beneficiary country USD?
sub2["oc"] = sub2.ORDERING_BIC8.str[4:6]; sub2["bc"] = sub2.BENEFICIARY_BIC8.str[4:6]
print("\nordering country US rate / beneficiary country US rate:\n",
      sub2.groupby("TRANSACTION_TYPE_CODE")[["oc","bc"]].apply(lambda g: (g=="US").mean()))
# does middle include ordering country and beneficiary country? (cover = leg via home bank?)
sub2["mid_has_oc"] = sub2.apply(lambda r: any(str(b)[4:6]==r.oc for b in r["mid"]) and len(r["mid"])>0, axis=1)
print("\nintermediary in ordering country rate:\n", sub2.groupby("TRANSACTION_TYPE_CODE").mid_has_oc.mean())
# beneficiary BIC appears among intermediaries?
sub2["benef_in_mid"] = sub2.apply(lambda r: r.BENEFICIARY_BIC8 in r["mid"], axis=1)
print("beneficiary bank also mid rate:\n", sub2.groupby("TRANSACTION_TYPE_CODE").benef_in_mid.mean())
sub2["order_in_mid"] = sub2.apply(lambda r: r.ORDERING_BIC8 in r["mid"], axis=1)
print("ordering bank also mid rate:\n", sub2.groupby("TRANSACTION_TYPE_CODE").order_in_mid.mean())
# same BIC consecutive repeat (path like A;A;B)?
sub2["adj_dup"] = df["vis"].map(lambda l: any(l[i]==l[i+1] for i in range(len(l)-1)))
print("adjacent-duplicate rate:\n", sub2.groupby("TRANSACTION_TYPE_CODE").adj_dup.mean())
print("\nexample Covered paths (pc=3):")
print(df[(df.TRANSACTION_TYPE_CODE=="Covered") & (df.PARTICIPANT_COUNT==3)][["ORDERING_BIC8","BENEFICIARY_BIC8","BIC8_PATH","CURRENCY_CODE","CURRENCY_CONVERSION_COUNT"]].head(8).to_string())
print("\nexample Indirect paths (pc=3):")
print(df[(df.TRANSACTION_TYPE_CODE=="Indirect") & (df.PARTICIPANT_COUNT==3)][["ORDERING_BIC8","BENEFICIARY_BIC8","BIC8_PATH","CURRENCY_CODE","CURRENCY_CONVERSION_COUNT"]].head(8).to_string())
# amount differences?
print("\nUSD_AMOUNT by type:\n", sub.groupby("TRANSACTION_TYPE_CODE").USD_AMOUNT.describe()[["mean","50%"]])
print("\nTOTAL_DURATION by type:\n", sub.groupby("TRANSACTION_TYPE_CODE").TOTAL_DURATION.describe()[["mean","50%"]])
