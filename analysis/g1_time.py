"""GROUP 1 - TIME. Data only: no external timezone list.
Idea: each country's daily rhythm is measured from its own payments. We then ask
whether every country follows the SAME daily shape shifted by a whole number of hours.
If yes, the generator used a local working-day clock."""
import numpy as np, pandas as pd, pickle, time, datetime as dt
from collections import defaultdict
from _common import parts, savefig
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

t0 = time.time()
prof = defaultdict(lambda: np.zeros(24))     # country -> payments by UTC hour
wd = defaultdict(lambda: np.zeros(7))        # country -> payments by UTC weekday
tot_h = np.zeros(24); tot_wd = np.zeros(7); total = 0

for i, fn in enumerate(parts()):
    d = pd.read_parquet(fn, columns=["EPOCH_SECONDS", "ORDERING_BIC8"])
    ep = d.EPOCH_SECONDS.to_numpy()
    oc = d.ORDERING_BIC8.str[4:6].to_numpy(dtype=object)
    # vectorised: seconds -> hour and weekday without a python loop
    hours = ((ep // 3600) % 24).astype(int)
    days = ((ep // 86400) + 3) % 7            # 1970-01-01 was a Thursday (index 3 = Thu if Mon=0)
    np.add.at(tot_h, hours, 1); np.add.at(tot_wd, days, 1)
    dfh = pd.DataFrame({"c": oc, "h": hours, "d": days})
    for c, g in dfh.groupby("c"):
        if not isinstance(c, str) or len(c) != 2: continue
        prof[c] += np.bincount(g.h.to_numpy(), minlength=24)
        wd[c] += np.bincount(g.d.to_numpy(), minlength=7)
    total += len(ep)
    del d
    if i % 5 == 0: print(f"pass {i+1}/20 {time.time()-t0:.0f}s", flush=True)

print(f"\nrows {total:,}; countries with data: {len(prof)}")

# --- reference rhythm = the busiest country's own day (no outside knowledge needed) ---
big = sorted(prof, key=lambda c: -prof[c].sum())[:25]
ref_c = big[0]
ref = prof[ref_c] / prof[ref_c].sum()
print(f"reference country chosen by volume: {ref_c} ({prof[ref_c].sum():,} payments)")

def corr(a, b):
    if a.std() == 0 or b.std() == 0: return 0.0
    return float(np.corrcoef(a, b)[0, 1])

def norm(v): return v / v.sum() if v.sum() else v

# --- find each country's shift (whole hours) that best matches the reference ---
shifts = {}
for c in prof:
    p = norm(prof[c])
    if prof[c].sum() < 5000: continue
    best_s, best_r = 0, -9
    for s in range(24):
        r = corr(np.roll(p, s), ref)
        if r > best_r: best_r, best_s = r, s
    shifts[c] = (best_s, best_r)

# --- how similar are countries before vs after alignment? ---
raw = [corr(norm(prof[c]), ref) for c in shifts]
aligned = []
for c in shifts:
    aligned.append(shifts[c][1])
raw = np.array(raw); aligned = np.array(aligned)
print(f"\n=== SIMILARITY TO THE REFERENCE RHYTHM (n={len(raw)} countries) ===")
print(f"  as they are, on the shared UTC clock : mean correlation {raw.mean():+.3f}")
print(f"  after shifting each by its own offset: mean correlation {aligned.mean():+.3f}")

# --- the common daily shape ---
shape = np.zeros(24)
for c in shifts:
    s = shifts[c][0]
    shape += np.roll(norm(prof[c]), s)
shape /= len(shifts)
peak = int(shape.argmax()); trough = int(shape.argmin())
print(f"\n=== THE COMMON SHAPE (each country aligned to its own peak) ===")
print(f"  peak at {peak:02d}:00 of the aligned day, trough at {trough:02d}:00")
print(f"  peak/trough ratio: {shape[peak]/max(shape[trough],1e-12):.1f}x")
print(f"  quiet hours (below half the peak): {int((shape < shape[peak]/2).sum())} of 24")
print(f"  share of payments in the 3 hours around the peak: {shape[[(peak-1)%24,peak,(peak+1)%24]].sum():.2%}")

# --- do different countries really sit at different offsets? ---
from collections import Counter
cnt = Counter(v[0] for v in shifts.values())
print(f"\n=== RECOVERED OFFSETS (whole hours, relative to {ref_c}) ===")
print("  distinct offsets:", len(cnt), "| most common:", cnt.most_common(6))

# --- weekday, in the file's own UTC days ---
print(f"\n=== WEEKDAY (UTC) ===")
names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
for i, nm in enumerate(names):
    print(f"  {nm}: {tot_wd[i]/tot_wd.sum():6.2%}")
print(f"  weekend share: {(tot_wd[5]+tot_wd[6])/tot_wd.sum():.2%}  (28.6% if every day were equal)")

# ---------- charts: one idea each, legends below, units spelled out ----------
import _style as S
S.apply()
GROUP = "g1_time"

# Chart 1 - what the raw file looks like: payments by UTC hour.
share_h = tot_h / tot_h.sum()
fig, ax = plt.subplots(figsize=(9.5, 4.6))
ax.bar(np.arange(24), share_h, color=S.C_ACCENT, width=0.82)
S.clean(ax)
S.title(ax, "Payments by hour, on the file's shared UTC clock",
        "Lumpy, with several peaks: many countries' working days overlap on one clock.")
ax.set_xlabel("Hour of the day (UTC)")
ax.set_ylabel("Share of all payments")
ax.set_xticks(np.arange(0, 24, 2))
ax.set_xlim(-0.8, 23.8)
ax.set_ylim(0, share_h.max() * 1.18)
S.pct_axis(ax, "y")
savefig(fig, "g1_1_hours_utc.png", group=GROUP)

# Chart 2 - the same payments after each country is lined up by its own peak.
peak = int(shape.argmax())
mat = np.array([np.roll(norm(prof[c]), shifts[c][0]) for c in shifts])
lo, hi = np.percentile(mat, [10, 90], axis=0)
xs = np.arange(-12, 12)
idx = [(peak + k) % 24 for k in xs]
fig, ax = plt.subplots(figsize=(9.5, 4.8))
ax.fill_between(xs, lo[idx], hi[idx], color=S.C_ACCENT_SOFT, lw=0,
                label="10th-90th percentile of countries")
ax.plot(xs, shape[idx], color=S.C_ACCENT, lw=2.8,
        label=f"Average of {len(shifts)} countries")
ax.axvline(0, color=S.C_MUTED, lw=1, ls=":")
S.clean(ax)
S.title(ax, "The same payments, each country lined up by its busiest hour",
        "All 113 countries share one daily rhythm - only their clock offset differs.")
ax.set_xlabel("Hours from that country's busiest hour (0 = its busiest hour)")
ax.set_ylabel("Share of that country's payments")
ax.set_xticks(np.arange(-12, 12, 3))
ax.set_xlim(-12, 11)
ax.set_ylim(0, hi.max() * 1.12)
S.pct_axis(ax, "y")
S.legend_below(ax, ncol=2, y=-0.22)
savefig(fig, "g1_2_aligned_day.png", group=GROUP)

# Chart 3 - do countries peak at the same UTC hour? (no: one clock per country)
peak_hour = np.bincount([int(prof[c].argmax()) for c in shifts], minlength=24)
fig, ax = plt.subplots(figsize=(9.5, 4.6))
ax.bar(np.arange(24), peak_hour, color=S.C_ACCENT, width=0.82)
S.clean(ax)
S.title(ax, "Each country's busiest hour of the day, on the UTC clock",
        "Countries are spread across all 24 hours - they do not share one clock.")
ax.set_xlabel("Hour of the day (UTC)")
ax.set_ylabel("Number of countries at their peak then")
ax.set_xticks(np.arange(0, 24, 2))
ax.set_xlim(-0.8, 23.8)
ax.set_ylim(0, peak_hour.max() * 1.18)
ax.yaxis.set_major_locator(MultipleLocator(5))
savefig(fig, "g1_3_country_peaks.png", group=GROUP)

# Chart 4 - weekday rhythm.
share_wd = tot_wd / tot_wd.sum()
colors = [S.C_ACCENT] * 5 + [S.C_WARN] * 2
fig, ax = plt.subplots(figsize=(9.5, 4.6))
bars = ax.bar(names, share_wd, color=colors, width=0.68)
S.vlabels(ax, bars, [f"{v:.1%}" for v in share_wd])
S.clean(ax)
S.title(ax, "Payments by day of the week",
        f"Weekend holds {(tot_wd[5]+tot_wd[6])/tot_wd.sum():.1%} of payments; "
        "each working day carries 17-18%.")
ax.set_xlabel("Day of the week (UTC)")
ax.set_ylabel("Share of all payments")
ax.set_ylim(0, share_wd.max() * 1.18)
S.pct_axis(ax, "y", step=0.05)
from matplotlib.patches import Patch
S.legend_below(ax, ncol=2, handles=[Patch(color=S.C_ACCENT), Patch(color=S.C_WARN)],
               labels=["Working day", "Weekend"], y=-0.14)
savefig(fig, "g1_4_weekday.png", group=GROUP)

pickle.dump({"shape": shape, "shifts": {c: v for c, v in shifts.items()},
             "prof": {c: prof[c] for c in prof}, "hour": tot_h, "weekday": tot_wd, "ref": ref_c},
            open("agg/g1_agg.pkl","wb"))

# =============================================================== 5. THE MECHANISM
# Rule 1 says every country has its own clock.  That leaves two questions a rule
# has to answer: (a) is the clock EXACT or fitted?  (b) where does the two-humped
# shape come from - two kinds of payment (a submission window and a cut-off
# batch), or one shared template stamped on every country's clock?
# Both are answered by controls, not by eyeballing the curve.
import duckdb
from _common import full_glob
G = full_glob()
con = duckdb.connect()
q = lambda s: con.execute(s).df()

print("\n=== 5a. is the clock exact? (independent halves of the rows) ===")
rows = []
for hf in (0, 1):
    pr = q(f"""SELECT upper(substr(ORDERING_BIC8,5,2)) sc,
                      CAST(EPOCH_SECONDS/3600 AS BIGINT) % 24 h, count(*) n
               FROM read_parquet('{G}') WHERE half = {hf} GROUP BY 1,2""")
    vec = {}
    for sc, g in pr.groupby("sc"):
        v = np.zeros(24); v[g.h.to_numpy(dtype=int)] = g.n.to_numpy()
        if v.sum() >= 2000: vec[sc] = v
    rows.append(vec)
H0, H1 = rows
common = sorted(set(H0) & set(H1) & set(shifts))
same, off1 = 0, 0
shape_corr = []
for c in common:
    p0, p1 = norm(H0[c]), norm(H1[c])
    s0 = int(np.argmax([corr(np.roll(p0, s), ref) for s in range(24)]))
    s1 = int(np.argmax([corr(np.roll(p1, s), ref) for s in range(24)]))
    if s0 == s1: same += 1
    elif min((s0 - s1) % 24, (s1 - s0) % 24) == 1: off1 += 1
    shape_corr.append(corr(np.roll(p0, s0), np.roll(p1, s1)))
print(f"  countries recovered in both halves: {len(common)}")
print(f"  identical hour offset in both halves: {same}/{len(common)}")
print(f"  disagreeing by exactly 1 hour      : {off1}/{len(common)}")
print(f"  aligned 24-hour shape correlation between halves: min {min(shape_corr):.4f} "
      f"median {float(np.median(shape_corr)):.4f}")

print("\n=== 5b. do the two windows carry different payments? (within-country control) ===")
pk = pd.DataFrame({"sc": [c for c in shifts], "peak": [int(prof[c].argmax()) for c in shifts]})
con.register("pk", pk)
con.execute(f"""CREATE OR REPLACE TEMP TABLE t AS
    SELECT upper(substr(ORDERING_BIC8,5,2)) sc, pk.peak,
           ((CAST(EPOCH_SECONDS/3600 AS BIGINT) % 24) - pk.peak + 24) % 24 AS h,
           TOTAL_DURATION dur, USD_AMOUNT amt, ORDERING_TYPE ot, BENEFICIARY_TYPE bt,
           CURRENCY_CONVERSION_COUNT cv, CAST(has_gap AS INT) gap,
           (upper(substr(ORDERING_BIC8,5,2)) <> upper(substr(BENEFICIARY_BIC8,5,2))) AS is_cross
    FROM read_parquet('{G}') r JOIN pk ON upper(substr(r.ORDERING_BIC8,5,2)) = pk.sc
    WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0""")
W = q("""SELECT CASE WHEN h IN (22,23,0,1,2) THEN 'main'
                   WHEN h IN (13,14,15,16) THEN 'second' ELSE 'other' END w,
                count(*) n, round(median(dur),1) dur, round(median(amt),0) amt,
                round(avg(CASE WHEN ot='B' THEN 1.0 ELSE 0 END),4) b_send,
                round(avg(CASE WHEN bt='B' THEN 1.0 ELSE 0 END),4) b_ben,
                round(avg(CASE WHEN is_cross THEN 1.0 ELSE 0 END),4) cross_sh,
                round(avg(CASE WHEN cv>0 THEN 1.0 ELSE 0 END),4) conv_sh,
                round(avg(CASE WHEN gap=1 THEN 1.0 ELSE 0 END),4) gap_sh
         FROM t GROUP BY 1 ORDER BY 1""")
print(W.to_string(index=False))
D = q("""SELECT sc,
                median(amt) FILTER (WHERE h IN (22,23,0,1,2)) a_main,
                median(amt) FILTER (WHERE h IN (13,14,15,16)) a_second,
                avg(CASE WHEN is_cross THEN 1.0 ELSE 0 END) FILTER (WHERE h IN (22,23,0,1,2)) x_main,
                avg(CASE WHEN is_cross THEN 1.0 ELSE 0 END) FILTER (WHERE h IN (13,14,15,16)) x_second,
                avg(CASE WHEN ot='B' THEN 1.0 ELSE 0 END) FILTER (WHERE h IN (22,23,0,1,2)) b_main,
                avg(CASE WHEN ot='B' THEN 1.0 ELSE 0 END) FILTER (WHERE h IN (13,14,15,16)) b_second,
                count(*) n
         FROM t GROUP BY 1 HAVING count(*) >= 5000""")
D["amt_ratio"] = np.log10(D.a_second / D.a_main)
D["cross_diff"] = D.x_second - D.x_main
D["b_share_diff"] = D.b_second - D.b_main
def band(s):
    return (f"median {s.median():+.4f}  p10 {s.quantile(.1):+.4f}  p90 {s.quantile(.9):+.4f}")
print(f"  n countries = {len(D)}")
print("  log10(amount in second window / amount in main window):", band(D.amt_ratio))
print("  cross-border share, second minus main:                ", band(D.cross_diff))
print("  business-sender share, second minus main:              ", band(D.b_share_diff))
print(f"  countries whose two windows differ by >0.1 dex in amount: "
      f"{int((D.amt_ratio.abs() > 0.1).sum())}/{len(D)}")

# --- aligned template: each country rolled so its own busiest hour is hour 0 ---
alig = np.array([np.roll(norm(prof[c]), -int(prof[c].argmax())) for c in shifts])
al = alig.mean(0)
MAIN = [22, 23, 0, 1, 2]
SECOND = [13, 14, 15, 16]
print(f"\n  aligned template: peak {al[0]:.2%} at the busiest hour, quiet floor "
      f"{al[6:13].min():.2%} in hours 6-12, second hump {al[13:17].max():.2%} at hour "
      f"{13 + int(np.argmax(al[13:17]))}")
print(f"  main window holds {al[MAIN].sum():.1%} of payments in 5/24 of the hours "
      f"({5/24:.1%} if flat); second window {al[SECOND].sum():.1%} in 4/24 ({4/24:.1%} if flat)")

fig = plt.figure(figsize=(11.4, 9.0))
gs = fig.add_gridspec(2, 3, height_ratios=[1.15, 0.95], hspace=0.70, wspace=0.42)
ax = fig.add_subplot(gs[0, :])
cols = [S.C_GREY_SOFT] * 24
for h in MAIN: cols[h] = S.C_ACCENT
for h in SECOND: cols[h] = S.C_WARN
ax.bar(np.arange(24), al, color=cols, width=0.82)
S.clean(ax)
S.title(ax, "One daily template, stamped on every country's own clock",
        f"Average of 113 countries, each rolled so its busiest hour is hour 0.  "
        f"Blue = main window (hours 22-02): {al[MAIN].sum():.1%} of payments in 5 of 24 hours.  "
        f"Red = second window (hours 13-16): {al[SECOND].sum():.1%} in 4 hours.")
ax.set_xlabel("Hours after that country's busiest hour")
ax.set_ylabel("Share of that country's payments")
ax.set_xticks(np.arange(0, 24, 2))
ax.set_xlim(-0.8, 23.8)
ax.set_ylim(0, al.max() * 1.16)
S.pct_axis(ax, "y")

ax = fig.add_subplot(gs[1, 0])
ax.hist(D.amt_ratio, bins=26, color=S.C_ACCENT)
ax.axvline(0, color=S.C_WARN, ls="--", lw=1.4)
S.clean(ax)
S.title(ax, "Same amount", f"median {D.amt_ratio.median():+.3f} dex")
ax.set_xlabel("log10(amount, second / main)", fontsize=9.5)
ax.set_ylabel("Countries")
ax.set_xlim(-0.15, 0.15)
S.count_axis(ax, "y")

ax = fig.add_subplot(gs[1, 1])
ax.hist(D.cross_diff, bins=26, color=S.C_ACCENT)
ax.axvline(0, color=S.C_WARN, ls="--", lw=1.4)
S.clean(ax)
S.title(ax, "Same share going abroad", f"median {D.cross_diff.median():+.4f}")
ax.set_xlabel("Cross-border share, second - main", fontsize=9.5)
ax.set_ylabel("Countries")
ax.set_xlim(-0.02, 0.02)
S.pct_axis(ax, "x", step=0.01)

ax = fig.add_subplot(gs[1, 2])
ax.hist(D.b_share_diff, bins=26, color=S.C_ACCENT)
ax.axvline(0, color=S.C_WARN, ls="--", lw=1.4)
S.clean(ax)
S.title(ax, "Same sender mix", f"median {D.b_share_diff.median():+.4f}")
ax.set_xlabel("Business-sender share, second - main", fontsize=9.5)
ax.set_ylabel("Countries")
ax.set_xlim(-0.04, 0.04)
S.pct_axis(ax, "x", step=0.02)
savefig(fig, "g1_5_two_windows.png", group=GROUP)

# ---------- 6. the offset table: a per-country clock, not 113 free curves ----------
cnt2 = Counter(v[0] for v in shifts.values())
signed = {(k - 24 if k > 12 else k): v for k, v in cnt2.items()}
keys = sorted(signed)
fig, ax = plt.subplots(figsize=(8.6, 6.2))
yy = np.arange(len(keys))[::-1]
bars = ax.barh(yy, [signed[k] for k in keys], color=S.C_ACCENT, height=0.72)
S.hlabels(ax, bars, [f"{signed[k]} countr{'y' if signed[k]==1 else 'ies'}" for k in keys], fontsize=9.5)
S.clean(ax, grid="x")
S.title(ax, f"{len(keys)} distinct whole-hour clocks, not {len(shifts)} free curves",
        "Each row is one clock offset recovered from the data; the bar is how many "
        "countries sit at it.")
ax.set_xlabel("Number of countries")
ax.set_ylabel("Country clock minus the busiest country's clock (hours)")
ax.set_yticks(yy)
ax.set_yticklabels([f"{k:+d} h" if k else "0 h" for k in keys])
ax.set_ylim(-0.7, len(keys) - 0.3)
ax.set_xlim(0, max(signed.values()) * 1.22)
ax.xaxis.set_major_locator(MultipleLocator(5))
savefig(fig, "g1_6_offset_table.png", group=GROUP)

print(f"\ndone in {time.time()-t0:.0f}s")
