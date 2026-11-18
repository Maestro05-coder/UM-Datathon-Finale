"""ROUTING v2 - full 10M dataset, single clean streaming pass.
Implements review feedback: hold-out validation, per-hop gap test, significance,
hub tilt metric, Covered-vs-Indirect power re-test, CUSTOMER_RECALL profile, examples."""
import pandas as pd, numpy as np, os, pickle, time
from collections import Counter, defaultdict

CACHE = r"D:\downloads\UmDatathonV2\analysis\cache_full"
files = sorted(f for f in os.listdir(CACHE) if f.startswith("part_"))
t0 = time.time()

class Res:
    def __init__(self, cap=200_000): self.data=[]; self.n=0; self.cap=cap
    def add(self, v):
        self.n += 1
        if len(self.data) < self.cap: self.data.append(v)
        else:
            i = np.random.randint(self.n)
            if i < self.cap: self.data[i] = v
    def med(self): return float(np.median(self.data)) if self.data else float("nan")

# ================= PASS 1: infer each bank's currency (train half only) =================
bank_cur_counts = defaultdict(Counter); cty_cur_counts = defaultdict(Counter)
for i, fn in enumerate(files):
    d = pd.read_parquet(f"{CACHE}/{fn}")
    tr = d[(d.half == 0) & (~d.has_gap) & (d.CURRENCY_CONVERSION_COUNT == 0)]
    cur = tr.CURRENCY_CODE.to_numpy()
    for b, c in zip(tr.ORDERING_BIC8.to_numpy(), cur):
        if isinstance(b, str): bank_cur_counts[b][c] += 1; cty_cur_counts[b[4:6]][c] += 1
    for b, c in zip(tr.BENEFICIARY_BIC8.to_numpy(), cur):
        if isinstance(b, str): bank_cur_counts[b][c] += 1; cty_cur_counts[b[4:6]][c] += 1
    del d, tr
    if i % 5 == 0: print(f"pass1 {i+1}/{len(files)} {time.time()-t0:.0f}s", flush=True)

bank_cur = {b: c.most_common(1)[0][0] for b, c in bank_cur_counts.items()}
cty_cur  = {c: v.most_common(1)[0][0] for c, v in cty_cur_counts.items()}
n_banks_seen = len(bank_cur)
print(f"inferred: {n_banks_seen:,} banks, {len(cty_cur)} countries  ({time.time()-t0:.0f}s)", flush=True)
del bank_cur_counts, cty_cur_counts

# ================= PASS 2: everything else =================
type_counts = Counter(); xt_type_nvis = Counter(); xt_qflag_gap = Counter()
gap_by_type_nvis = Counter(); gap_mism = Counter(); mism = Counter(); joint_mism = Counter()
anomaly_by_type = Counter()
recall_types = Counter(); recall_res = {"amt":Res(),"dur":Res(),"pc":Res()}
recall_cnt = {k: Counter() for k in ["otype","btype","cur"]}
end_cty = Counter(); mid_cty = Counter(); mid_cty_matchcur = Counter()
cur_all = Counter()
firsthop = Counter(); pair_type = Counter(); party_by_type = Counter()
cov_pc = Counter(); ind_pc = Counter(); cov_amt = Counter(); ind_amt = Counter()
dur_res = defaultdict(Res)
IN_T = IN_OK = HO_T = HO_OK = FB_T = FB_OK = 0
examples = defaultdict(list)

def add_example(name, row, keep=3):
    if len(examples[name]) < keep:
        examples[name].append({k: (None if pd.isna(row[k]) else row[k]) for k in
            ["BIC8_PATH","TRANSACTION_TYPE_CODE","PARTICIPANT_COUNT","CURRENCY_CODE",
             "CURRENCY_CONVERSION_COUNT","CONTINUITY_QFLAG","ORDERING_BIC8","BENEFICIARY_BIC8",
             "TOTAL_DURATION","USD_AMOUNT","ANOMALY_TYPE"]})

d0 = pd.read_parquet(f"{CACHE}/{files[0]}")
AMT_EDGES = [-np.inf, *d0.USD_AMOUNT.quantile([.1*i for i in range(1,10)]).values, np.inf]
del d0

for i, fn in enumerate(files):
    d = pd.read_parquet(f"{CACHE}/{fn}")
    paths   = d.BIC8_PATH.tolist()
    types   = d.TRANSACTION_TYPE_CODE.tolist()
    gaps    = d.has_gap.tolist()
    nviss   = d.n_vis.tolist()
    convs   = d.CURRENCY_CONVERSION_COUNT.tolist()
    halves  = d.half.tolist()
    curs    = d.CURRENCY_CODE.tolist()
    amts    = d.USD_AMOUNT.tolist()
    dus     = d.TOTAL_DURATION.tolist()
    pcs     = d.PARTICIPANT_COUNT.tolist()
    fms     = d.first_mism.tolist(); lms = d.last_mism.tolist()
    ants    = d.ANOMALY_TYPE.tolist()
    ots     = d.ORDERING_TYPE.tolist(); bts = d.BENEFICIARY_TYPE.tolist()
    obs     = d.ORDERING_BIC8.tolist(); bbs = d.BENEFICIARY_BIC8.tolist()

    for j in range(len(paths)):
        p = paths[j]; t = types[j]; g = bool(gaps[j])
        # --- integrity / bookkeeping ---
        xt_type_nvis[(nviss[j], t)] += 1; type_counts[t] += 1
        gap_by_type_nvis[(t, int(nviss[j]), g)] += 1
        # --- mismatches ---
        fm = bool(fms[j]) if isinstance(fms[j], (bool, np.bool_)) else False
        lm = bool(lms[j]) if isinstance(lms[j], (bool, np.bool_)) else False
        mism[(t,"f")] += fm; mism[(t,"l")] += lm
        joint_mism[(t, fm, lm)] += 1
        gap_mism[(t, g, fm or lm)] += 1
        # --- currency counters ---
        c = curs[j]
        if c is not None: cur_all[c] += 1
        # --- conversions scoring (continuous rows only) ---
        if p is not None and "..." not in p:
            banks = p.split(";")
            s_in = s_h = s_f = 0; prev = None; known_in = known_f = True
            for b in banks:
                bc = bank_cur.get(b)
                bc_f = bc if bc is not None else (cty_cur.get(b[4:6]) if isinstance(b, str) else None)
                if bc is None: known_in = False
                if bc_f is None: known_f = False
                if prev is not None:
                    if bc is not None and bc != prev: s_in += 1
                    if bc_f is not None and bc_f != prev_f: s_f += 1
                if bc is not None: prev = bc
                if bc_f is not None: prev_f = bc_f
            if known_in:
                IN_T += 1; IN_OK += (s_in == convs[j])
            if known_in and halves[j] == 1:
                HO_T += 1; HO_OK += (s_in == convs[j])   # same lookup, test-half rows only
            if known_f:
                FB_T += 1; FB_OK += (s_f == convs[j])
        # --- anomalies ---
        a_ = ants[j]
        if isinstance(a_, str):
            anomaly_by_type[(a_, t)] += 1
            if a_ == "CUSTOMER_RECALL":
                recall_types[t] += 1
                recall_res["amt"].add(amts[j]); recall_res["dur"].add(dus[j]); recall_res["pc"].add(pcs[j])
                if ots[j] is not None: recall_cnt["otype"][ots[j]] += 1
                if bts[j] is not None: recall_cnt["btype"][bts[j]] += 1
                if c is not None: recall_cnt["cur"][c] += 1
        # --- hubs ---
        if obs[j] is not None: end_cty[obs[j][4:6]] += 1
        if bbs[j] is not None: end_cty[bbs[j][4:6]] += 1
        if pcs[j] >= 3 and p is not None:
            banks = p.split(";")
            mids = [b for b in banks[1:-1] if b != "..."]
            for b in mids:
                cty = b[4:6]
                mid_cty[cty] += 1
                mid_cty_matchcur[(cty, c == cty_cur.get(cty))] += 1
            firsthop[(banks[0][4:6] in ("US","CH","GB"), t)] += 1
            # --- covered vs indirect ---
            if t in ("Covered","Indirect"):
                (cov_pc if t=="Covered" else ind_pc)[int(pcs[j])] += 1
                (cov_amt if t=="Covered" else ind_amt)[int(np.searchsorted(AMT_EDGES, amts[j], side="right"))] += 1
                pc = int(pcs[j]); cv = int(convs[j])
                if pc in (3,4,5) and cv in (0,1,2,3): dur_res[(t, pc, cv)].add(dus[j])
                if ots[j] is not None and bts[j] is not None:
                    party_by_type[((ots[j], bts[j]), t)] += 1
                if obs[j] is not None and bbs[j] is not None:
                    pair_type[(obs[j][4:6] + bbs[j][4:6], t)] += 1
    # --- examples (cheap, few per chunk) ---
    tt = d.TRANSACTION_TYPE_CODE; aa = d.ANOMALY_TYPE; hg = d.has_gap
    cvc = d.CURRENCY_CONVERSION_COUNT
    for name, mask in [("direct", (tt=="Direct") & (~hg)),
                       ("indirect_conv2", (tt=="Indirect") & (~hg) & (cvc==2)),
                       ("direct_gap", (tt=="Direct") & hg),
                       ("covered", (tt=="Covered") & (~hg)),
                       ("recall", aa=="CUSTOMER_RECALL"),
                       ("romance_direct", (aa=="ROMANCE_SCAM") & (tt=="Direct"))]:
        m = mask.fillna(False).to_numpy(dtype=bool)
        for j in np.where(m)[0][:3]:
            add_example(name, d.iloc[j])
    if i % 4 == 0: print(f"pass2 {i+1}/{len(files)} {time.time()-t0:.0f}s", flush=True)
    del d

# qflag tally (cheap second mini-pass avoided: recount from gap_mism impossible) -> compute here from pass2 need
# NOTE: qflag counted in pass3 quick loop
qflag_tally = Counter()
for fn in files:
    d = pd.read_parquet(f"{CACHE}/{fn}", columns=["CONTINUITY_QFLAG","has_gap","n_vis","PARTICIPANT_COUNT","TRANSACTION_TYPE_CODE"])
    for g, q in zip(d.has_gap, d.CONTINUITY_QFLAG): qflag_tally[(bool(g), q)] += 1
    # per-hop gap test on non-gapped multi-hop rows uses gap_by_type_nvis (already collected)
    del d

# ================= REPORT =================
print("\n" + "="*72)
print("INTEGRITY (bookkeeping) CHECKS  [full data]")
tot = sum(type_counts.values())
print(f"rows: {tot:,}   types: {dict(type_counts)}")
for t in type_counts:
    f_ = mism[(t,"f")]/type_counts[t]; l_ = mism[(t,"l")]/type_counts[t]
    both = joint_mism[(t,True,True)]/type_counts[t]
    print(f"  {t}: start-mismatch {f_:.4%}, end-mismatch {l_:.4%}, both {both:.5%} (product {f_*l_:.5%})")
print("qflag vs gap:", dict(qflag_tally))

print("\n" + "="*72)
print("CONVERSION RULE validation")
print(f"  in-sample  (all continuous rows, bank lookup): {IN_OK:,}/{IN_T:,} = {IN_OK/max(IN_T,1):.4%}")
print(f"  HOLD-OUT   (test half only):                   {HO_OK:,}/{HO_T:,} = {HO_OK/max(HO_T,1):.4%}")
print(f"  all rows with country fallback for unknown banks: {FB_OK:,}/{FB_T:,} = {FB_OK/max(FB_T,1):.4%}")

print("\n" + "="*72)
print("GAP: per-payment or per-hop?  (gap rate by route length)")
for t in ["Direct","Indirect","Covered"]:
    parts = []
    for n in sorted(set(k[1] for k in gap_by_type_nvis if k[0]==t))[:7]:
        g = gap_by_type_nvis[(t,n,True)]; ng = gap_by_type_nvis[(t,n,False)]
        parts.append(f"{n} banks: {g/(g+ng):.3f} (n={g+ng:,})")
    print(f"  {t}: " + " | ".join(parts))
print("  gap x endpoint-mismatch linkage (Direct):",
      {k[1:]: v for k, v in gap_mism.items() if k[0]=="Direct"})

print("\n" + "="*72)
print("FRAUD-NEVER-COVERED significance")
multi_total = sum(type_counts[t] for t in type_counts if t != "Direct")
cov_share = type_counts.get("Covered",0)/multi_total
print(f"  P(Covered | multi-hop) = {cov_share:.4%}")
for a_ in ["ROMANCE_SCAM","CEO_SCAM","ACCOUNT_REPLACEMENT_SCAM","DUPLICATE_PAYMENT"]:
    n_f = sum(anomaly_by_type[(a_,t)] for t in type_counts)
    pv = (1-cov_share)**n_f
    print(f"  {a_}: n={n_f:,}, Covered={anomaly_by_type[(a_,'Covered')]}, P(zero by chance)={pv:.2e}")

print("\n" + "="*72)
print("CUSTOMER_RECALL profile")
print(f"  n={sum(recall_types.values()):,}  by type: {dict(recall_types)}")
print(f"  median amount: {recall_res['amt'].med():,.0f}   median duration: {recall_res['dur'].med():.0f}s   median participants: {recall_res['pc'].med()}")
print(f"  party types: {dict(recall_cnt['otype'])} -> {dict(recall_cnt['btype'])}   currencies: {dict(recall_cnt['cur'].most_common(5))}")

print("\n" + "="*72)
print("HUB TILT = (share of intermediary hops) / (share of endpoints)")
tm = sum(mid_cty.values()); te = sum(end_cty.values())
tilts = {c: (mid_cty[c]/tm)/(end_cty[c]/te) for c in mid_cty if end_cty[c] > 5000}
for c, v in sorted(tilts.items(), key=lambda kv: -kv[1])[:10]:
    # currency link: does the payment currency equal the hub's currency more often than baseline?
    match = mid_cty_matchcur[(c, True)]/(mid_cty_matchcur[(c, True)]+mid_cty_matchcur[(c, False)])
    base = cur_all.get(cty_cur.get(c), 0)/sum(cur_all.values())
    print(f"  {c}: tilt {v:.2f}  |  P(payment in hub's currency | {c} intermediary) = {match:.3f} vs baseline {base:.3f}")

print("\n" + "="*72)
print("COVERED vs INDIRECT power re-test")
pct = {pc: cov_pc[pc]/(cov_pc[pc]+ind_pc[pc]) for pc in sorted(set(cov_pc)|set(ind_pc))}
print("  P(Covered|multi-hop) by participants:", {k: round(v,4) for k,v in pct.items()})
print("  by amount decile:", {d_: round(cov_amt[d_]/(cov_amt[d_]+ind_amt[d_]),4) for d_ in range(1,11) if cov_amt[d_]+ind_amt[d_]>5000})
fh_cov = firsthop[(True,"Covered")]/max(1,sum(v for k,v in firsthop.items() if k[1]=="Covered"))
fh_ind = firsthop[(True,"Indirect")]/max(1,sum(v for k,v in firsthop.items() if k[1]=="Indirect"))
print(f"  first hop is a hub bank (US/CH/GB): Covered {fh_cov:.4f} vs Indirect {fh_ind:.4f}")
print("  median duration, matched on (participants, conversions):")
for pc in [3,4,5]:
    for cv in [0,1,2,3]:
        c = dur_res[("Covered",pc,cv)].med(); i_ = dur_res[("Indirect",pc,cv)].med()
        if c==c and i_!=i_: pass
        nc = dur_res[("Covered",pc,cv)].n; ni = dur_res[("Indirect",pc,cv)].n
        if nc > 5000 and ni > 5000:
            print(f"    pc={pc} conv={cv}: Covered {c:.0f}s (n={nc:,}) | Indirect {i_:.0f}s (n={ni:,}) | ratio {c/i_:.2f}")
print("  party-type mix (Covered share):")
for k in sorted(set(k[0] for k in party_by_type)):
    nc = party_by_type[(k,"Covered")]; ni = party_by_type[(k,"Indirect")]
    if nc+ni > 20000: print(f"    {k}: {nc/(nc+ni):.4f}")
ps = defaultdict(lambda: [0,0])
for (pair, t), v in pair_type.items(): ps[pair][0 if t=="Covered" else 1] += v
rows = []
for p, v in ps.items():
    c, i2 = v
    if c + i2 >= 20000: rows.append((p, c/(c+i2), c+i2))
sds = np.std([r[1] for r in rows])
print(f"  corridors n>=20000: {len(rows)}, covered-rate sd {sds:.4f}")
rows.sort(key=lambda r: r[1])
print("  lowest:", [(r[0], round(r[1],3)) for r in rows[:4]]); print("  highest:", [(r[0], round(r[1],3)) for r in rows[-4:]])

with open("routing_v2_agg.pkl","wb") as f:
    pickle.dump({"type_counts":dict(type_counts), "nvis":dict(xt_type_nvis),
                 "gap_by_type_nvis":dict(gap_by_type_nvis), "qflag_tally":dict(qflag_tally),
                 "anomaly_by_type":dict(anomaly_by_type),
                 "recall_amt":recall_res["amt"].data, "recall_dur":recall_res["dur"].data,
                 "recall_cnt":recall_cnt, "recall_types":dict(recall_types),
                 "cov_amt":dict(cov_amt), "ind_amt":dict(ind_amt),
                 "cov_pc":dict(cov_pc), "ind_pc":dict(ind_pc),
                 "dur_med":{k:v.med() for k,v in dur_res.items()},
                 "examples":dict(examples), "tilts":tilts,
                 "holdout":(IN_OK,IN_T,HO_OK,HO_T,FB_OK,FB_T),
                 "joint_mism":dict(joint_mism),
                 "mid_cty":dict(mid_cty), "end_cty":dict(end_cty)}, f)
print("\nsaved routing_v2_agg.pkl | total", round(time.time()-t0), "s")
