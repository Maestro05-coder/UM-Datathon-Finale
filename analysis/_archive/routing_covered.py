"""ROUTING: bank-currency sanity + what drives Covered."""
import pandas as pd, numpy as np, pickle
from load_data import load_core
pd.set_option("display.width", 220)

df = load_core()
with open("bank_cur.pkl","rb") as f: bank_cur = pickle.load(f)

# ---- sanity: currency distribution by bank country ----
bdf = pd.DataFrame({"bank": bank_cur.index, "cur": bank_cur.values})
bdf["cc"] = bdf.bank.str[4:6]
for c in ["US","DE","GB","CH","JP"]:
    s = bdf[bdf.cc==c].cur.value_counts(normalize=True).head(4)
    print(c, "->", {k: round(v,3) for k,v in s.items()})

# ---- Covered drivers: is it the intermediary bank identity? ----
paths = df["BIC8_PATH"].map(lambda p: [s for s in str(p).split(";") if s])
df["vis"] = paths.map(lambda l: [s for s in l if s != "..."])
sub = df[(df.PARTICIPANT_COUNT==3) & (df.BIC8_PATH.str.contains(r"\.\.\.", na=False)==False)]
sub = sub.copy()
sub["mid"] = sub["vis"].map(lambda l: l[1])
rates = sub.groupby("mid").apply(lambda g: pd.Series({
    "n": len(g), "covered_rate": (g.TRANSACTION_TYPE_CODE=="Covered").mean()}), include_groups=False)
rates = rates[rates.n >= 100].sort_values("covered_rate")
print("\nintermediary banks (pc=3): n banks with >=100 obs:", len(rates))
print("covered-rate distribution:")
print(rates.covered_rate.describe())
print("lowest:\n", rates.head(5))
print("highest:\n", rates.tail(5))

# ordering/beneficiary bank identity?
sub2 = sub.copy()
o_rates = sub.groupby(sub.ORDERING_BIC8).apply(lambda g: (g.TRANSACTION_TYPE_CODE=="Covered").mean(), include_groups=False)
cnt = sub.groupby(sub.ORDERING_BIC8).size()
o_rates = o_rates[cnt>=100]
print("\nordering-bank covered-rate sd (pc=3):", o_rates.std().round(4), " (if random, sd ~ binomial noise)")
# corridor (country pair)?
sub["occ"] = sub.ORDERING_BIC8.str[4:6]; sub["bcc"] = sub.BENEFICIARY_BIC8.str[4:6]
pair = sub.groupby(["occ","bcc"]).apply(lambda g: pd.Series({"n":len(g),"cov":(g.TRANSACTION_TYPE_CODE=="Covered").mean()}), include_groups=False)
pair = pair[pair.n>=200]
print("\ncorridor covered-rate sd:", pair.cov.std().round(4), "n corridors:", len(pair))
print(pair.sort_values("cov").head(3).to_string(), "\n...\n", pair.sort_values("cov").tail(3).to_string())
# conversion count effect (already seen) + gap effect on multi-hop
multi = df[df.PARTICIPANT_COUNT>=3]
print("\nP(Covered|multi-hop) by conversion count:")
print(multi.groupby("CURRENCY_CONVERSION_COUNT").apply(lambda g:(g.TRANSACTION_TYPE_CODE=="Covered").mean(), include_groups=False).head(6).round(4))
print("P(Covered|multi-hop) by gap:")
print(multi.groupby(multi.BIC8_PATH.str.contains(r"\.\.\.", na=False)).apply(lambda g:(g.TRANSACTION_TYPE_CODE=="Covered").mean(), include_groups=False).round(4))
print("\nP(Indirect|multi-hop) by pc:")
print(multi.groupby("PARTICIPANT_COUNT").apply(lambda g:(g.TRANSACTION_TYPE_CODE=="Indirect").mean(), include_groups=False).round(4))
