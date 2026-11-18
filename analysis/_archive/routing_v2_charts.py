"""ROUTING v2 charts — renders from routing_v2_agg.pkl (full 10M data)."""
import pickle, numpy as np, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "charts"; os.makedirs(OUT, exist_ok=True)
with open("routing_v2_agg.pkl","rb") as f: A = pickle.load(f)
C = {"Direct":"#2b6cb0","Indirect":"#dd6b20","Covered":"#38a169"}

# 1 — type vs path length
xt = A["nvis"]; types_ = ["Direct","Indirect","Covered"]
ns = sorted(set(k[0] for k in xt))
fig, ax = plt.subplots(figsize=(8,4.5))
bottom = np.zeros(len(ns))
for t in types_:
    vals = [xt.get((n,t),0) for n in ns]
    ax.bar([str(n) for n in ns], vals, bottom=bottom, label=t, color=C[t]); bottom += vals
ax.set_yscale("log"); ax.set_xlabel("Visible banks in the route (BIC8_PATH)")
ax.set_ylabel("Payments (log scale)"); ax.legend()
ax.set_title("Routing type follows exactly from route length\nDirect = 2 banks (100%); 3+ banks = Indirect or Covered")
plt.tight_layout(); plt.savefig(f"{OUT}/routing_1_type_vs_pathlen.png", dpi=150); plt.close()

# 2 — qflag vs gap
qt = A["qflag_tally"]
xlab = ["no '...' in route", "'...' in route"]
yY = [qt[(False,"Y")], qt[(True,"Y")]]; yN = [qt[(False,"N")], qt[(True,"N")]]
fig, ax = plt.subplots(figsize=(6,4))
ax.bar(xlab, yY, label="QFLAG=Y", color="#2b6cb0"); ax.bar(xlab, yN, bottom=yY, label="QFLAG=N", color="#c53030")
for i,(a,b) in enumerate(zip(yY,yN)):
    ax.text(i, (a+b)*1.05, f"Y: {a/(a+b):.2%}\nN: {b/(a+b):.2%}", ha="center")
ax.set_yscale("log"); ax.set_ylabel("Payments (log)"); ax.legend()
ax.set_title("QFLAG is 100% decided by whether '...' appears in the route")
plt.tight_layout(); plt.savefig(f"{OUT}/routing_2_qflag_gap.png", dpi=150); plt.close()

# 3 — conversion rule validation (hold-out numbers in title)
iok, it, hok, ht, fok, ft = A["holdout"]
fig, ax = plt.subplots(figsize=(6,4))
bars = ["In-sample\n(all rows)", "HOLD-OUT\n(other half)", "All rows\n(country fallback)"]
vals = [iok/it, hok/ht, fok/ft]
ax.bar(bars, vals, color=["#a0aec0","#2b6cb0","#38a169"])
for i,v in enumerate(vals): ax.text(i, v+0.005, f"{v:.2%}", ha="center")
ax.set_ylim(0.9, 1.01); ax.set_ylabel("Share of payments where the rule predicts\nthe conversion count exactly")
ax.set_title("Currency-crossing rule survives out-of-sample test")
plt.tight_layout(); plt.savefig(f"{OUT}/routing_3_conversion_holdout.png", dpi=150); plt.close()

# 4 — anomaly x type
ab = A["anomaly_by_type"]; tc = A["type_counts"]
order = ["ROMANCE_SCAM","CEO_SCAM","ACCOUNT_REPLACEMENT_SCAM","DUPLICATE_PAYMENT","FAT_FINGER_MISTAKE","CUSTOMER_RECALL"]
fig, ax = plt.subplots(figsize=(9,4.5))
lefts = np.zeros(len(order))
for t in types_:
    vals = np.array([ab.get((o,t),0)/max(1,sum(ab.get((o,tt),0) for tt in types_)) for o in order])
    ax.barh(order, vals, left=lefts, color=C[t], label=t); lefts += vals
for i,o in enumerate(order):
    ax.text(1.01, i, f"n={sum(ab.get((o,tt),0) for tt in types_):,}", va="center", fontsize=9)
ax.set_xlabel("Share of that anomaly's payments"); ax.legend(loc="lower right")
ax.set_title("Fraud never travels Covered routes (0 of 1,677 fraud payments)")
plt.tight_layout(); plt.savefig(f"{OUT}/routing_4_anomaly_type.png", dpi=150); plt.close()

# 5 — mismatch
jm = A["joint_mism"]; tcx = A["type_counts"]
fig, ax = plt.subplots(figsize=(6.5,4))
x = np.arange(3); w=0.35
fv = [sum(v for k,v in jm.items() if k[0]==t and k[1]) / tcx[t] * 100 for t in types_]
lv = [sum(v for k,v in jm.items() if k[0]==t and k[2]) / tcx[t] * 100 for t in types_]
ax.bar(x-w/2, fv, w, label="route start != ORDERING_BIC8", color="#2b6cb0")
ax.bar(x+w/2, lv, w, label="route end != BENEFICIARY_BIC8", color="#dd6b20")
for i,v in enumerate(fv): ax.text(i-w/2, v+0.05, f"{v:.1f}%", ha="center", fontsize=9)
for i,v in enumerate(lv): ax.text(i+w/2, v+0.05, f"{v:.1f}%", ha="center", fontsize=9)
ax.set_xticks(x); ax.set_xticklabels(types_)
ax.set_ylabel("% of payments"); ax.set_ylim(0, 7)
ax.set_title("Bank labels disagree with the route on ~5% of payments per end\n(same rate for every routing type; the two ends are independent)")
ax.legend()
plt.tight_layout(); plt.savefig(f"{OUT}/routing_5_mismatch.png", dpi=150); plt.close()

# 6 — hubs
mids = A["mid_cty"]; ends = A["end_cty"]; tilts = A["tilts"]
sel = [c for c,_ in sorted(tilts.items(), key=lambda kv:-kv[1])][:12]
tm, te = sum(mids.values()), sum(ends.values())
fig, ax = plt.subplots(figsize=(8,4.5))
x = np.arange(len(sel)); w=0.38
ax.bar(x-w/2, [mids[c]/tm*100 for c in sel], w, label="share of middle hops", color="#2b6cb0")
ax.bar(x+w/2, [ends[c]/te*100 for c in sel], w, label="share of start/end banks", color="#a0aec0")
ax.set_xticks(x); ax.set_xticklabels(sel); ax.set_ylabel("% share"); ax.legend()
ax.set_title("Middle-of-route banks tilt toward BE/CH/CN (hub tilt = middle share / endpoint share)")
plt.tight_layout(); plt.savefig(f"{OUT}/routing_6_hubs.png", dpi=150); plt.close()

# 7 — covered duration at matched (pc=3)
dm = A["dur_med"]
fig, ax = plt.subplots(figsize=(7,4))
labels, cv_, iv_ = [], [], []
for cv in [0,1,2,3]:
    if ("Covered",3,cv) in dm and ("Indirect",3,cv) in dm:
        labels.append(f"{cv} conversions"); cv_.append(dm[("Covered",3,cv)]); iv_.append(dm[("Indirect",3,cv)])
x = np.arange(len(labels)); w=0.35
ax.bar(x-w/2, cv_, w, label="Covered", color=C["Covered"])
ax.bar(x+w/2, iv_, w, label="Indirect", color=C["Indirect"])
ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylabel("Median duration (seconds)")
ax.set_title("At 3 banks: Covered payments take ~3x longer than Indirect\n(same route length, same number of conversions)")
ax.legend()
plt.tight_layout(); plt.savefig(f"{OUT}/routing_7_covered_duration.png", dpi=150); plt.close()

print("charts written:", [f for f in os.listdir(OUT) if f.startswith("routing")])
