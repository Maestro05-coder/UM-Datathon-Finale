"""Debug the conversion rule on full data: why 84.6% here vs 99.8% on the 1M slice?
- infer bank currency from ALL conv==0 continuous rows (all path banks, like v1)
- score agreement overall, BY MONTH, and error magnitude
- also endpoint-only inference variant
- plus: pc vs n_vis crosstab, n_hidden distribution, P(Covered) by conv and same-country
"""
import pandas as pd, numpy as np, os, time
from collections import Counter, defaultdict

CACHE = r"D:\downloads\UmDatathonV2\analysis\cache_full"
files = sorted(f for f in os.listdir(CACHE) if f.startswith("part_"))
t0 = time.time()

# ---- PASS 1: two inference variants ----
bank_all = defaultdict(Counter)     # all path banks (v1 style)
bank_end = defaultdict(Counter)     # endpoints only (v2 style)
for fn in files:
    d = pd.read_parquet(f"{CACHE}/{fn}", columns=["BIC8_PATH","CURRENCY_CODE","CURRENCY_CONVERSION_COUNT","has_gap"])
    m = (~d.has_gap.to_numpy()) & (d.CURRENCY_CONVERSION_COUNT.to_numpy() == 0)
    cur = d.CURRENCY_CODE.to_numpy(); pat = d.BIC8_PATH.to_numpy()
    for j in np.where(m)[0]:
        c = cur[j]
        for b in pat[j].split(";"):
            bank_all[b][c] += 1
        bank_end[pat[j].split(";")[0]][c] += 1
        bank_end[pat[j].split(";")[-1]][c] += 1
    del d
cur_all_banks = {b: c.most_common(1)[0][0] for b, c in bank_all.items()}
cur_endpoints = {b: c.most_common(1)[0][0] for b, c in bank_end.items()}
print(f"inferred {len(cur_all_banks):,} banks (all-bank style), {len(cur_endpoints):,} (endpoint style) {time.time()-t0:.0f}s", flush=True)
del bank_all, bank_end

MONTH_STARTS = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]  # not used; use epoch month
def month_of(ep):
    import datetime
    return (datetime.datetime.fromtimestamp(ep, datetime.timezone.utc).year,
            datetime.datetime.fromtimestamp(ep, datetime.timezone.utc).month)

# ---- PASS 2: score ----
agree_all = defaultdict(lambda: [0, 0]); agree_end = defaultdict(lambda: [0, 0])   # (y, m) -> [ok, tot]
err_mag = Counter()
pc_nvis = Counter(); n_hidden_ct = Counter()
cov_by_conv = Counter(); ind_by_conv = Counter()
cov_same = Counter(); ind_same = Counter()
dir_gap_pc = Counter()
examples_gapped_direct = []
examples_bad_conv = []
for i, fn in enumerate(files):
    d = pd.read_parquet(f"{CACHE}/{fn}", columns=["BIC8_PATH","CURRENCY_CODE","CURRENCY_CONVERSION_COUNT",
                                                  "has_gap","half","EPOCH_SECONDS","PARTICIPANT_COUNT","TRANSACTION_TYPE_CODE",
                                                  "ORDERING_BIC8","BENEFICIARY_BIC8","USD_AMOUNT"])
    pat = d.BIC8_PATH.tolist(); cur = d.CURRENCY_CODE.tolist(); cv = d.CURRENCY_CONVERSION_COUNT.tolist()
    gap = d.has_gap.tolist(); pc = d.PARTICIPANT_COUNT.tolist(); tt = d.TRANSACTION_TYPE_CODE.tolist()
    ep = d.EPOCH_SECONDS.tolist()
    for j in range(len(pat)):
        p = pat[j]
        if p is None: continue
        banks = p.split(";")
        y, mth = month_of(ep[j])
        if not gap[j]:
            # score both variants
            for lookup, acc in ((cur_all_banks, agree_all), (cur_endpoints, agree_end)):
                s = 0; known = True; prev = None
                for b in banks:
                    bc = lookup.get(b)
                    if bc is None: known = False; break
                    if prev is not None and bc != prev: s += 1
                    prev = bc
                if known:
                    ok = (s == cv[j])
                    a = acc[(y, mth)]
                    a[0] += ok; a[1] += 1
                    if acc is agree_all and not ok:
                        err_mag[abs(s - cv[j])] += 1
                        if len(examples_bad_conv) < 8:
                            examples_bad_conv.append((p, cur[j], cv[j], s))
        else:
            n_hidden_ct[p.count("...")] += 1
            if tt[j] == "Direct":
                dir_gap_pc[pc[j]] += 1
                if len(examples_gapped_direct) < 6:
                    examples_gapped_direct.append((p, pc[j], d.ORDERING_BIC8.iat[j], d.BENEFICIARY_BIC8.iat[j]))
        # pc vs nvis
        pc_nvis[(pc[j], len([b for b in banks if b != "..."]))] += 1
        # covered by conv & same-country
        if tt[j] == "Covered": cov_by_conv[cv[j]] += 1
        elif tt[j] == "Indirect": ind_by_conv[cv[j]] += 1
        if tt[j] in ("Covered","Indirect") and pc[j] >= 3:
            same = banks[0][4:6] == banks[-1][4:6]
            (cov_same if tt[j]=="Covered" else ind_same)[same] += 1
    if i % 5 == 0: print(f"pass2 {i+1}/{len(files)} {time.time()-t0:.0f}s", flush=True)
    del d

print("\n== conversion rule: all-bank-currency inference ==")
tot = sum(v[1] for v in agree_all.values()); ok = sum(v[0] for v in agree_all.values())
print(f"overall: {ok:,}/{tot:,} = {ok/max(tot,1):.4%}")
print("by month:")
for k in sorted(agree_all):
    o, t = agree_all[k]; print(f"  {k}: {o/t:.4%} (n={t:,})")
print("error magnitude (pred - actual):", dict(sorted(err_mag.items())[:6]))
print("examples of mismatches (path, paycur, actual conv, predicted):")
for e in examples_bad_conv: print("  ", e)

print("\n== endpoint-only inference variant ==")
tot2 = sum(v[1] for v in agree_end.values()); ok2 = sum(v[0] for v in agree_end.values())
print(f"overall: {ok2:,}/{tot2:,} = {ok2/max(tot2,1):.4%}")

print("\n== participant_count vs visible banks ==")
mism2 = {k: v for k, v in pc_nvis.items() if k[0] != k[1]}
print("rows where pc != n_visible:", sum(mism2.values()))
print("top (pc, nvis) combos:", sorted(pc_nvis.items(), key=lambda kv: -kv[1])[:8])
print("\ngapped Direct rows by participant_count:", dict(sorted(dir_gap_pc.items())))
print("n_hidden distribution (gapped rows):", dict(sorted(n_hidden_ct.items())))
print("gapped Direct examples (path, pc, O, B):")
for e in examples_gapped_direct: print("  ", e)

print("\n== P(Covered | multi-hop) by conversion count ==")
for c_ in sorted(set(cov_by_conv) | set(ind_by_conv))[:6]:
    c_, i_ = cov_by_conv[c_], ind_by_conv[c_]
    print(f"  conv={c_}: Covered {c_/(c_+i_):.4%} (n={c_+i_:,})")
print("\n== P(Covered | multi-hop) by same-country endpoints ==")
print({k: f"{cov_same[k]/(cov_same[k]+ind_same[k]):.4%} (n={cov_same[k]+ind_same[k]:,})" for k in cov_same})
print("\ntime", round(time.time()-t0), "s")
