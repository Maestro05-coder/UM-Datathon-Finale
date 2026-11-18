"""ROUTING: infer per-BIC currency from conv=0 rows, then test rule variants."""
import pandas as pd, numpy as np, pickle
from load_data import load_core
pd.set_option("display.width", 220)

df = load_core()
paths = df["BIC8_PATH"].map(lambda p: [s for s in str(p).split(";") if s])
df["vis"] = paths.map(lambda l: [s for s in l if s != "..."])
df["has_gap"] = df["BIC8_PATH"].str.contains(r"\.\.\.", na=False).fillna(False)
cont = df[~df.has_gap]

# ---- Step 1: infer bank currency = modal payment currency among conv==0 continuous rows ----
# explode: (bank, payment currency) for rows with conv == 0
ex = cont[cont.CURRENCY_CONVERSION_COUNT == 0].explode("vis")
ex = ex.dropna(subset=["vis"])
ex = ex.rename(columns={"vis": "bank", "CURRENCY_CODE": "cur"})
tab = ex.groupby(["bank", "cur"]).size().unstack(fill_value=0)
bank_cur = tab.idxmax(axis=1)
bank_cnt = tab.max(axis=1)
bank_tot = tab.sum(axis=1)
print("banks seen:", len(bank_tot))
print("inference sample strength: median obs per bank =", bank_tot.median())
print("dominant-currency share >=95%:", (bank_cnt / bank_tot >= 0.95).mean().round(4))
print("share >=99%:", (bank_cnt / bank_tot >= 0.99).mean().round(4))
# does inferred bank currency match country modal? (sanity)
bc_map = (pd.DataFrame({"cur": np.repeat(df.CURRENCY_CODE.to_numpy(), 2),
                        "cc": pd.concat([df.ORDERING_BIC8, df.BENEFICIARY_BIC8]).str[4:6].to_numpy()})
          .groupby("cc").cur.agg(lambda s: s.value_counts().idxmax()))
inferred_cc = bank_cur.index.str[4:6]
match_country = (bank_cur.values == inferred_cc.map(bc_map).values)
print("inferred bank currency == country modal:", match_country.mean().round(4))

# ---- Step 2: test rules on continuous paths ----
def predict(row, mode):
    banks = row["vis"]
    curs = [bank_cur.get(b) for b in banks]
    pc = row.CURRENCY_CODE
    if mode == "participants":
        return sum(c is not None and c != pc for c in curs)
    else:  # adjacent changes
        return sum(1 for i in range(len(curs)-1)
                   if curs[i] is not None and curs[i+1] is not None and curs[i] != curs[i+1])

sub = cont.copy()
sub["pred_part"] = sub.apply(lambda r: predict(r, "participants"), axis=1)
sub["pred_adj"]  = sub.apply(lambda r: predict(r, "adj"), axis=1)
known = sub["vis"].map(lambda l: all(bank_cur.get(b) is not None for b in l))
print("\nrows with all path banks inferred:", known.mean().round(4))

for name, p in [("participants-rule", "pred_part"), ("adjacent-rule", "pred_adj")]:
    s = sub[known]
    print(f"\n{name} agreement (all-banks-known):", (s[p] == s.CURRENCY_CONVERSION_COUNT).mean().round(6))
    print(pd.crosstab(s[p], s.CURRENCY_CONVERSION_COUNT).head(6))

# break down errors of the better rule
best = "pred_part"
s = sub[known]
err = s[s[best] != s.CURRENCY_CONVERSION_COUNT]
print("\nerror magnitude:", (err.CURRENCY_CONVERSION_COUNT - err[best]).value_counts().sort_index().head(6).to_dict())
print("error examples:")
print(err[["ORDERING_BIC8","BENEFICIARY_BIC8","BIC8_PATH","CURRENCY_CODE","CURRENCY_CONVERSION_COUNT",best]].head(10).to_string())

with open("bank_cur.pkl", "wb") as f:
    pickle.dump(bank_cur, f)
print("\nsaved bank_cur.pkl")
