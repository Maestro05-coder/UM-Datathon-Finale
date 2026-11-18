"""ROUTING FINAL - full 10M, correct definitions, hold-out validated.
Fixes: n_visible excludes '...'; bank currency inferred on TRAIN half only, scored on TEST half."""
import pandas as pd, numpy as np, os, pickle, time
from collections import Counter, defaultdict

CACHE = r"D:\downloads\UmDatathonV2\analysis\cache_full"
files = sorted(f for f in os.listdir(CACHE) if f.startswith("part_"))
t0 = time.time()

def banks_of(p):
    """visible banks only, plus count of hidden hops"""
    if not isinstance(p, str): return [], 0
    parts = p.split(";")
    return [b for b in parts if b != "..."], sum(1 for b in parts if b == "...")

# ============ PASS 1: infer currency per bank, TRAIN HALF ONLY ============
bank_cur_t = defaultdict(Counter)
for fn in files:
    d = pd.read_parquet(f"{CACHE}/{fn}", columns=["BIC8_PATH","CURRENCY_CODE","CURRENCY_CONVERSION_COUNT","has_gap","half"])
    m = (~d.has_gap.to_numpy()) & (d.CURRENCY_CONVERSION_COUNT.to_numpy() == 0) & (d.half.to_numpy() == 0)
    cur = d.CURRENCY_CODE.to_numpy(); pat = d.BIC8_PATH.to_numpy()
    for j in np.where(m)[0]:
        for b in banks_of(pat[j])[0]:
            bank_cur_t[b][cur[j]] += 1
    del d
bank_cur = {b: c.most_common(1)[0][0] for b, c in bank_cur_t.items()}
print(f"pass1: {len(bank_cur):,} banks inferred from TRAIN half ({time.time()-t0:.0f}s)", flush=True)
del bank_cur_t

# ============ PASS 2: aggregates + validated scoring ============
type_counts = Counter()
vis_by_type = Counter()        # (n_visible, type) -> rows
gap_by_type_k = Counter()      # (type, n_interior_hops, gap?) -> rows
mism = Counter()               # (type, 'f'/'l') -> count
joint = Counter()              # (type, f, l)
anom = Counter()               # (anomaly, type)
recall = {"amt":[], "dur":[], "pc":[]}; recall_type = Counter(); recall_party = Counter()
in_ok = in_tot = ho_ok = ho_tot = 0
err_mag = Counter(); bad_ex = []
end_cty = Counter(); mid_cty = Counter(); mid_curmatch = Counter()
cur_totals = Counter()
cov_pc = Counter(); ind_pc = Counter(); cov_amt = Counter(); ind_amt = Counter()
dur_samples = defaultdict(list)   # (type, pc, conv) -> durations (capped)
cov_same = Counter(); ind_same = Counter()
pair_ty = Counter()
ex = defaultdict(list)
AMT_EDGES = None

def cap_append(lst, v, cap=150_000):
    if len(lst) < cap: lst.append(v)

for i, fn in enumerate(files):
    d = pd.read_parquet(f"{CACHE}/{fn}")
    if AMT_EDGES is None:
        AMT_EDGES = [-np.inf, *d.USD_AMOUNT.quantile([.1*k for k in range(1,10)]).values, np.inf]
    pat = d.BIC8_PATH.fillna("").to_numpy(dtype=object)
    cur = d.CURRENCY_CODE.fillna("").to_numpy(dtype=object)
    cv  = d.CURRENCY_CONVERSION_COUNT.to_numpy()
    tt  = d.TRANSACTION_TYPE_CODE.fillna("").to_numpy(dtype=object)
    gapf= d.has_gap.to_numpy()
    half= d.half.to_numpy()
    pc  = d.PARTICIPANT_COUNT.to_numpy()
    fm  = d.first_mism.to_numpy(); lm = d.last_mism.to_numpy()
    ants= d.ANOMALY_TYPE.fillna("").to_numpy(dtype=object)
    amt = d.USD_AMOUNT.to_numpy(); dur = d.TOTAL_DURATION.to_numpy()

    for j in range(len(pat)):
        visible, hidden = banks_of(pat[j])
        nv = len(visible); t = tt[j]
        type_counts[t] += 1
        vis_by_type[(nv, t)] += 1
        # gap rate by number of INTERIOR hops (only routes with >=3 visible banks have interior hops)
        if nv >= 3:
            gap_by_type_k[(t, nv - 2, bool(gapf[j]))] += 1
        elif nv == 2:
            gap_by_type_k[(t, 0, bool(gapf[j]))] += 1
        # endpoint mismatch
        if fm[j]: mism[(t,"f")] += 1
        if lm[j]: mism[(t,"l")] += 1
        joint[(t, bool(fm[j]), bool(lm[j]))] += 1
        # currency totals
        cur_totals[cur[j]] += 1
        # ---- conversion rule scoring (continuous routes only) ----
        if not gapf[j] and nv >= 2:
            s = 0; known = True; prev = None
            for b in visible:
                bc = bank_cur.get(b)
                if bc is None: known = False; break
                if prev is not None and bc != prev: s += 1
                prev = bc
            if known:
                ok = int(s == cv[j])
                if half[j] == 0: in_tot += 1; in_ok += ok
                else:            ho_tot += 1; ho_ok += ok
                if not ok:
                    err_mag[abs(s - cv[j])] += 1
                    if len(bad_ex) < 6:
                        bad_ex.append((pat[j], cur[j], int(cv[j]), s))
        # ---- anomalies ----
        a = ants[j]
        if isinstance(a, str):
            anom[(a, t)] += 1
            if a == "CUSTOMER_RECALL":
                recall_type[t] += 1
                cap_append(recall["amt"], amt[j]); cap_append(recall["dur"], dur[j]); cap_append(recall["pc"], pc[j])
        # ---- hubs ----
        if isinstance(d.ORDERING_BIC8.iat[j], str):
            end_cty[d.ORDERING_BIC8.iat[j][4:6]] += 1
        if isinstance(d.BENEFICIARY_BIC8.iat[j], str):
            end_cty[d.BENEFICIARY_BIC8.iat[j][4:6]] += 1
        # ---- covered vs indirect ----
        if t in ("Covered","Indirect") and nv >= 3:
            mids = visible[1:-1]
            for b in mids: mid_cty[b[4:6]] += 1
            for b in mids:
                cty = b[4:6]
                mid_curmatch[(cty, cur[j] == bank_cur.get(b))] += 1
            (cov_pc if t=="Covered" else ind_pc)[int(pc[j])] += 1
            (cov_amt if t=="Covered" else ind_amt)[int(np.searchsorted(AMT_EDGES, amt[j], side="right"))] += 1
            same = visible[0][4:6] == visible[-1][4:6]
            (cov_same if t=="Covered" else ind_same)[same] += 1
            k = (t, int(pc[j]), int(cv[j]))
            if pc[j] in (3,4) and cv[j] in (0,1,2,3):
                cap_append(dur_samples[k], int(dur[j]))
            pair_ty[(t, visible[0][4:6] + visible[-1][4:6])] += 1
    # examples
    for name, mask in [
        ("direct", (tt=="Direct") & (~gapf)),
        ("direct_gap", (tt=="Direct") & gapf),
        ("indirect", (tt=="Indirect") & (~gapf) & (cv==2)),
        ("covered_same_country", (tt=="Covered") & (~gapf)),
        ("recall", ants=="CUSTOMER_RECALL"),
        ("romance", ants=="ROMANCE_SCAM"),
    ]:
        idx = np.where(np.asarray(mask, dtype=bool))[0][:2]
        for j in idx:
            if len(ex[name]) < 2:
                ex[name].append({k: (None if pd.isna(d[k].iat[j]) else d[k].iat[j]) for k in
                    ["ORDERING_BIC8","BENEFICIARY_BIC8","BIC8_PATH","TRANSACTION_TYPE_CODE","PARTICIPANT_COUNT",
                     "CURRENCY_CODE","CURRENCY_CONVERSION_COUNT","CONTINUITY_QFLAG","TOTAL_DURATION","USD_AMOUNT","ANOMALY_TYPE"]})
    del d
    if i % 5 == 0: print(f"pass2 {i+1}/{len(files)} {time.time()-t0:.0f}s", flush=True)

# ============ REPORT ============
print("\n" + "="*74)
print(f"rows: {sum(type_counts.values()):,}  {dict(type_counts)}")
print("\n[1] ROUTE LENGTH BY TYPE (visible banks; '...' excluded)")
for t in ["Direct","Indirect","Covered"]:
    dist = {n: vis_by_type[(n,t)] for n in range(0,9) if vis_by_type[(n,t)]}
    print(f"  {t}: {dist}")
d2 = vis_by_type[(2,"Direct")]; tot_d = type_counts["Direct"]
print(f"  -> Direct with exactly 2 visible banks: {d2:,}/{tot_d:,} = {d2/tot_d:.4%}")

print("\n[2] HIDDEN-HOP (gap) RATE vs NUMBER OF INTERIOR HOPS")
for t in ["Direct","Indirect","Covered"]:
    print(f"  {t}:")
    for k in sorted(set(kk[1] for kk in gap_by_type_k if kk[0]==t))[:7]:
        g = gap_by_type_k[(t,k,True)]; ng = gap_by_type_k[(t,k,False)]
        print(f"    {k} interior hop(s): {g/(g+ng):.4f}   (n={g+ng:,})")

print("\n[3] CONVERSION RULE (hold-out validated)")
print(f"  TRAIN-half rows scored: {in_ok:,}/{in_tot:,} = {in_ok/max(in_tot,1):.4%}")
print(f"  TEST-half  rows scored: {ho_ok:,}/{ho_tot:,} = {ho_ok/max(ho_tot,1):.4%}")
print("  error size (predicted minus actual):", dict(sorted(err_mag.items())))
print("  mismatch examples:", bad_ex)

print("\n[4] ENDPOINT LABEL MISMATCH")
for t in ["Direct","Indirect","Covered"]:
    n = type_counts[t]
    print(f"  {t}: start {mism[(t,'f')]/n:.4%}  end {mism[(t,'l')]/n:.4%}  "
          f"both {joint[(t,True,True)]/n:.5%}  (independent would be {(mism[(t,'f')]/n)*(mism[(t,'l')]/n):.5%})")

print("\n[5] ANOMALY x ROUTING TYPE")
cov_share = type_counts["Covered"]/sum(type_counts[t] for t in type_counts if t != "Direct")
for a in ["ROMANCE_SCAM","CEO_SCAM","ACCOUNT_REPLACEMENT_SCAM","DUPLICATE_PAYMENT","FAT_FINGER_MISTAKE","CUSTOMER_RECALL"]:
    n = sum(anom[(a,t)] for t in type_counts)
    if n == 0: continue
    c_ = anom[(a,"Covered")]
    print(f"  {a}: n={n:,}  Direct {anom[(a,'Direct')]:,} Indirect {anom[(a,'Indirect')]:,} Covered {c_:,}"
          f"  |  P(this few Covered by chance)={ (1-cov_share)**n if c_==0 else float('nan') }")

print("\n[6] CUSTOMER_RECALL")
print(f"  n={sum(recall_type.values()):,} types={dict(recall_type)}")
for k in ["amt","dur","pc"]:
    v = np.array(recall[k], dtype=float)
    print(f"  {k}: median {np.median(v):,.1f}  p25 {np.percentile(v,25):,.1f}  p75 {np.percentile(v,75):,.1f}")

print("\n[7] HUB TILT (middle hops vs start/end banks)")
tm, te = sum(mid_cty.values()), sum(end_cty.values())
til = {c: (mid_cty[c]/tm)/(end_cty[c]/te) for c in mid_cty if end_cty[c] > 5000}
for c, v in sorted(til.items(), key=lambda kv: -kv[1])[:8]:
    m = mid_curmatch[(c,True)]/max(1, mid_curmatch[(c,True)]+mid_curmatch[(c,False)])
    print(f"  {c}: tilt {v:.2f}   payment already in this bank's currency: {m:.3f}")

print("\n[8] COVERED vs INDIRECT")
print("  by participants:", { k: round(cov_pc[k]/(cov_pc[k]+ind_pc[k]),4) for k in sorted(set(cov_pc)|set(ind_pc)) if k<=8})
print("  by amount decile:", {k: round(cov_amt[k]/(cov_amt[k]+ind_amt[k]),4) for k in range(1,11) if cov_amt[k]+ind_amt[k]>5000})
print("  same-country endpoints:", {k: f"{cov_same[k]/(cov_same[k]+ind_same[k]):.4f}" for k in cov_same})
print("  median duration (particiants, conversions):")
for k in sorted(dur_samples):
    if k[0]=="Covered" and len(dur_samples[k])>5000 and len(dur_samples[("Indirect",k[1],k[2])])>5000:
        c = np.median(dur_samples[k]); i_ = np.median(dur_samples[("Indirect",k[1],k[2])])
        print(f"    pc={k[1]} conv={k[2]}: Covered {c:.0f}s | Indirect {i_:.0f}s | ratio {c/i_:.2f}"
              f"  (n={len(dur_samples[k]):,} / {len(dur_samples[('Indirect',k[1],k[2])]):,})")
ps = defaultdict(lambda:[0,0])
for (t,pair),v in pair_ty.items(): ps[pair][0 if t=="Covered" else 1] += v
rows = [(p, c/(c+i2), c+i2) for p,(c,i2) in ps.items() if c+i2 >= 20000]
print(f"  corridors (n>=20k): {len(rows)}, covered-rate sd {np.std([r[1] for r in rows]):.4f}")
rows.sort(key=lambda r: r[1]); print("   lowest:", [(r[0],round(r[1],3)) for r in rows[:3]],
                                       "highest:", [(r[0],round(r[1],3)) for r in rows[-3:]])

with open("routing_final_agg.pkl","wb") as f:
    pickle.dump({"type_counts":dict(type_counts), "vis_by_type":dict(vis_by_type),
                 "gap_by_type_k":dict(gap_by_type_k), "anom":dict(anom),
                 "mism":dict(mism), "joint":dict(joint),
                 "recall_amt":recall["amt"], "recall_dur":recall["dur"], "recall_type":dict(recall_type),
                 "tilts":til, "cov_pc":dict(cov_pc), "ind_pc":dict(ind_pc),
                 "cov_amt":dict(cov_amt), "ind_amt":dict(ind_amt),
                 "dur":{k:list(v) for k,v in dur_samples.items()},
                 "examples":dict(ex),
                 "score":(in_ok,in_tot,ho_ok,ho_tot)}, f)
print(f"\nsaved. total {time.time()-t0:.0f}s")
