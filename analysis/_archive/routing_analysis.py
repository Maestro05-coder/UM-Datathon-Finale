"""GROUP 5: ROUTING — reverse-engineering BIC8_PATH, PARTICIPANT_COUNT,
TRANSACTION_TYPE_CODE, CONTINUITY_QFLAG."""
import pandas as pd, numpy as np
from load_data import load_core

pd.set_option("display.width", 200)
df = load_core()

# ---------- parse paths ----------
def parse_path(p):
    if p is None or (isinstance(p, float) and np.isnan(p)): return []
    return [s for s in str(p).split(";") if s]

paths = df["BIC8_PATH"].map(parse_path)
df["path_n_visible"] = paths.map(len)
df["path_first"] = paths.map(lambda l: l[0] if l else None)
df["path_last"]  = paths.map(lambda l: l[-1] if l else None)
df["has_gap"]    = df["BIC8_PATH"].str.contains(r"\.\.\.", na=False).fillna(False)
df["gap_hidden"] = df["BIC8_PATH"].map(
    lambda p: parse_path(p).count("...") if isinstance(p, str) else 0)
df["visibles"]   = paths.map(lambda l: [s for s in l if s != "..."])
df["n_visible_bics"] = df["visibles"].map(len)

print("="*80); print("BASIC RANGES")
print("participant_count:", sorted(df.PARTICIPANT_COUNT.unique()))
print("type counts:\n", df.TRANSACTION_TYPE_CODE.value_counts())
print("qflag counts:\n", df.CONTINUITY_QFLAG.value_counts())
print("has_gap counts:", df.has_gap.value_counts().to_dict())
print("n_visible_bics:", df.n_visible_bics.value_counts().sort_index().to_dict())
print("gap_hidden counts:", df.gap_hidden.value_counts().sort_index().to_dict())

# ---------- H1: path endpoints match O/B BICs; participants = visible BICs ----------
print("="*80); print("H1: PATH ENDPOINTS & PARTICIPANT_COUNT DERIVATION")
ok_first = (df.path_first == df.ORDERING_BIC8)
ok_last  = (df.path_last  == df.BENEFICIARY_BIC8)
print("first==ORDERING_BIC8:", ok_first.mean())
print("last ==BENEFICIARY_BIC8:", ok_last.mean())
mismatch = df.loc[~(ok_first & ok_last), ["ORDERING_BIC8","BENEFICIARY_BIC8","BIC8_PATH"]].head(5)
print("mismatch examples:\n", mismatch.to_string())
# participant count vs number of visible BICs
print("\nPARTICIPANT_COUNT vs n_visible_bics crosstab:")
print(pd.crosstab(df.n_visible_bics, df.PARTICIPANT_COUNT))
# participants vs visible + hidden
print("\nPARTICIPANT_COUNT == n_visible + n_hidden + 1?")
d2 = df.PARTICIPANT_COUNT - (df.n_visible_bics + df.gap_hidden)
print(d2.value_counts().sort_index().head(10))

# ---------- H2: type determined by participant count / path shape ----------
print("="*80); print("H2: TRANSACTION_TYPE_CODE vs PARTICIPANT_COUNT")
print(pd.crosstab(df.PARTICIPANT_COUNT, df.TRANSACTION_TYPE_CODE))
print("\ntype vs n_visible_bics:")
print(pd.crosstab(df.n_visible_bics, df.TRANSACTION_TYPE_CODE))

# ---------- H3: QFLAG <=> gap ----------
print("="*80); print("H3: CONTINUITY_QFLAG <=> '...' present")
print(pd.crosstab(df.has_gap, df.CONTINUITY_QFLAG))
# per-type determinism
for t in df.TRANSACTION_TYPE_CODE.dropna().unique():
    sub = df[df.TRANSACTION_TYPE_CODE == t]
    print(f"type={t}: n={len(sub)}, gap_rate={sub.has_gap.mean():.4f}, "
          f"yflag_rate={(sub.CONTINUITY_QFLAG=='Y').mean():.4f}, "
          f"pc={sorted(sub.PARTICIPANT_COUNT.unique())[:8]}")

# ---------- H4: what does the gap represent? hidden-hop count per type ----------
print("="*80); print("H4: GAP STRUCTURE BY TYPE")
g = df[df.has_gap]
print("gap rows:", len(g))
print(g.groupby("TRANSACTION_TYPE_CODE").agg(
    n=("has_gap","size"),
    mean_visible=("n_visible_bics","mean"),
    mean_pc=("PARTICIPANT_COUNT","mean"),
    mean_hidden=("gap_hidden","mean")))
# does participant_count over-count vs visible for gapped rows?
print("for gapped rows, PARTICIPANT_COUNT - n_visible distribution:")
print((g.PARTICIPANT_COUNT - g.n_visible_bics).value_counts().sort_index())

# ---------- H5: geography of intermediaries ----------
print("="*80); print("H5: INTERMEDIARY COUNTRIES (chars 5-6 of BIC8)")
def country(b):
    return str(b)[4:6] if isinstance(b, str) else None
oc = df.ORDERING_BIC8.map(country); bc = df.BENEFICIARY_BIC8.map(country)
inter = df["visibles"].map(lambda l: [str(b)[4:6] for b in l[1:-1]] if len(l) >= 3 else [])
flat = [c for l in inter for c in l]
print("intermediary country top15:", pd.Series(flat).value_counts().head(15).to_dict())
print("ordering country top10:", oc.value_counts().head(10).to_dict())
print("beneficiary country top10:", bc.value_counts().head(10).to_dict())
same_cc = (oc == bc)
print("\nsame-country rate by type:")
print(df.assign(same=same_cc).groupby("TRANSACTION_TYPE_CODE").same.mean())
print("\nsame-currency rate by type:")
print(df.assign(same=df.CURRENCY_CODE == df.CURRENCY_CODE).groupby("TRANSACTION_TYPE_CODE").size())

# ---------- cross-group: conversions vs participants (control: same country?) ----------
print("="*80); print("CROSS: FX CONVERSION COUNT vs PARTICIPANT_COUNT (by type)")
print(pd.crosstab(df.CURRENCY_CONVERSION_COUNT, df.TRANSACTION_TYPE_CODE))
# does cross-currency (ordering country country-currency vs beneficiary) drive conversions?
print("\nconversion rate when ordering country == beneficiary country vs not:")
tmp = pd.DataFrame({"same": same_cc, "conv": df.CURRENCY_CONVERSION_COUNT})
print(tmp.groupby("same").conv.value_counts().unstack(fill_value=0).head(6))
