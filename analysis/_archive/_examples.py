"""Pull a few real rows from the cache, to quote as examples in the group write-ups."""
import pandas as pd
from _common import parts

picked = {}
cols = None
for fn in parts()[:4]:
    d = pd.read_parquet(fn)
    cols = [c for c in d.columns]
    tt = d.TRANSACTION_TYPE_CODE.fillna("")
    for label, mask in [
        ("direct2", (tt == "Direct")),
        ("indirect3", (tt == "Indirect") & (d.PARTICIPANT_COUNT == 3)),
        ("covered3", (tt == "Covered") & (d.PARTICIPANT_COUNT == 3)),
        ("gap", d.BIC8_PATH.str.contains("...", regex=False, na=False)),
    ]:
        if label not in picked:
            s = d[mask].head(1)
            if len(s):
                picked[label] = s
    if len(picked) == 4:
        break

print("COLUMNS:", cols)
for label, s in picked.items():
    r = s.iloc[0]
    print()
    print("===", label, "===")
    for c in cols:
        print(f"{c}: {r[c]}")
