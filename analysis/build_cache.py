"""Build a chunked parquet 'working copy' of the FULL csv (light columns + derived path features).
Streams the 4.95GB csv once; low RAM."""
import pandas as pd, numpy as np, os, time

CSV = r"D:\downloads\UmDatathonV2\swift_umdac_datathon_2026_fictitious_payment_data.csv"
OUTDIR = r"D:\downloads\UmDatathonV2\analysis\cache_full"
os.makedirs(OUTDIR, exist_ok=True)

LIGHT_COLS = ["EPOCH_SECONDS","CURRENCY_CODE","USD_AMOUNT","ORDERING_BIC8","BENEFICIARY_BIC8",
              "BIC8_PATH","TOTAL_DURATION","CONTINUITY_QFLAG","CURRENCY_CONVERSION_COUNT",
              "PARTICIPANT_COUNT","TRANSACTION_TYPE_CODE","ORDERING_TYPE","BENEFICIARY_TYPE","ANOMALY_TYPE"]

def stable_half(epoch, path):
    # deterministic 50/50 row split for hold-out validation
    return (hash((epoch, path)) & 1)

t0 = time.time()
chunk_no = 0
min_ep, max_ep = None, None
total = 0
for chunk in pd.read_csv(CSV, usecols=LIGHT_COLS, chunksize=500_000,
                         dtype={"CURRENCY_CODE":"string","ORDERING_BIC8":"string","BENEFICIARY_BIC8":"string",
                                "BIC8_PATH":"string","CONTINUITY_QFLAG":"string","TRANSACTION_TYPE_CODE":"string",
                                "ORDERING_TYPE":"string","BENEFICIARY_TYPE":"string","ANOMALY_TYPE":"string"}):
    vis = chunk["BIC8_PATH"].map(lambda p: [s for s in str(p).split(";") if s] if isinstance(p, str) else [])
    chunk["n_vis"] = vis.map(len)
    chunk["has_gap"] = chunk["BIC8_PATH"].str.contains(r"\.\.\.", na=False).fillna(False)
    chunk["n_hidden"] = vis.map(lambda l: l.count("..."))
    chunk["gap_head"] = vis.map(lambda l: bool(l) and l[0] == "...")
    chunk["gap_tail"] = vis.map(lambda l: bool(l) and l[-1] == "...")
    chunk["first_mism"] = vis.map(lambda l: l[0] if l else None) != chunk["ORDERING_BIC8"]
    chunk["last_mism"]  = vis.map(lambda l: l[-1] if l else None) != chunk["BENEFICIARY_BIC8"]
    chunk["half"] = [stable_half(e, p) for e, p in zip(chunk.EPOCH_SECONDS, chunk.BIC8_PATH)]
    chunk.to_parquet(f"{OUTDIR}/part_{chunk_no:03d}.parquet", index=False)
    e = chunk.EPOCH_SECONDS
    min_ep = e.min() if min_ep is None else min(min_ep, e.min())
    max_ep = e.max() if max_ep is None else max(max_ep, e.max())
    total += len(chunk)
    print(f"chunk {chunk_no}: {total:,} rows, {time.time()-t0:.0f}s elapsed", flush=True)
    chunk_no += 1

pd.DataFrame({"min_epoch":[min_ep], "max_epoch":[max_ep], "rows":[total]}).to_csv(f"{OUTDIR}/_meta.csv", index=False)
print(f"DONE: {total:,} rows, {chunk_no} chunks, epoch range {min_ep}..{max_ep}")
import datetime
print("as dates:", datetime.datetime.utcfromtimestamp(min_ep), "->", datetime.datetime.utcfromtimestamp(max_ep))
