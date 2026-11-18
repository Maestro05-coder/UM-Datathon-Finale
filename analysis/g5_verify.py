"""Verify the 5%-per-link model, anomaly significance, and dump example rows."""
import pickle, numpy as np, math
A = pickle.load(open("agg/g5_agg.pkl","rb"))
gk = A["gap_by_type_k"]

print("=== GAP MODEL: each link hidden with prob p; p estimated from Direct (1 link) ===")
p = gk[("Direct",0,True)] / (gk[("Direct",0,True)] + gk[("Direct",0,False)])
print(f"p (per link) = {p:.5f}")
print(f"{'interior hops':>13} {'links':>6} {'observed':>9} {'predicted':>10} {'n':>10}")
for k in range(0, 8):
    g = gk.get(("Indirect",k,True),0); ng = gk.get(("Indirect",k,False),0)
    if g+ng == 0: continue
    obs = g/(g+ng); links = k+1
    pred = 1-(1-p)**links
    print(f"{k:>13} {links:>6} {obs:>9.4f} {pred:>10.4f} {g+ng:>10,}")

print("\n=== ANOMALY vs COVERED: binomial test using base rate 11.31% among multi-hop ===")
tc = A["type_counts"]; an = A["anom"]
cov_share = tc["Covered"]/(tc["Indirect"]+tc["Covered"])
print(f"base P(Covered | multi-hop) = {cov_share:.4f}")
def binom_sf(k, n, pr):
    """P(X <= k) for X~Bin(n,pr)"""
    return sum(math.comb(n,i)*pr**i*(1-pr)**(n-i) for i in range(k+1))
for a in ["ROMANCE_SCAM","CEO_SCAM","ACCOUNT_REPLACEMENT_SCAM","DUPLICATE_PAYMENT","FAT_FINGER_MISTAKE","CUSTOMER_RECALL"]:
    multi = an.get((a,"Indirect"),0)+an.get((a,"Covered"),0)
    cov = an.get((a,"Covered"),0)
    if multi == 0: continue
    exp = multi*cov_share
    pv = binom_sf(cov, multi, cov_share)
    verdict = "FEWER Covered than chance" if pv < 0.01 else ("MORE" if binom_sf(multi-cov, multi, 1-cov_share) < 0.01 else "as expected")
    print(f"  {a:<26} multi-hop n={multi:>5}  Covered={cov:>4}  expected={exp:>6.1f}  P(<=obs)={pv:.2e}  -> {verdict}")

print("\n=== EXAMPLE ROWS ===")
for name, rows in A["examples"].items():
    print(f"\n--- {name} ---")
    for r in rows[:2]:
        print({k: v for k, v in r.items()})

print("\n=== DURATION samples sanity ===")
for k in sorted(A["dur"]):
    if k[0]=="Covered" and len(A["dur"][k])>1000:
        ind = A["dur"].get(("Indirect",k[1],k[2]),[])
        if len(ind)>1000:
            print(k, "covered med", np.median(A["dur"][k]), "indirect med", np.median(ind))
