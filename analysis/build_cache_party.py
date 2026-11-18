"""Build cache_party/ = account + text columns of the FULL csv, as chunked parquet.
Streams the 4.95GB csv once with pandas (same pattern as build_cache.py - it parses
the messy quoting in DETAILS/TOKENS correctly). Serves g8_anomalies and g7_parties."""
import pandas as pd, os, time

CSV = r"D:\downloads\UmDatathonV2\swift_umdac_datathon_2026_fictitious_payment_data.csv"
OUT = r"D:\downloads\UmDatathonV2\analysis\cache_party"
os.makedirs(OUT, exist_ok=True)

KEEP = ["EPOCH_SECONDS", "CURRENCY_CODE", "USD_AMOUNT", "ORDERING_BIC8", "BENEFICIARY_BIC8",
        "ORDERING_ACCOUNT", "BENEFICIARY_ACCOUNT", "ORDERING_DETAILS", "ORDERING_TOKENS",
        "BENEFICIARY_DETAILS", "BENEFICIARY_TOKENS", "ORDERING_TYPE", "BENEFICIARY_TYPE",
        "ANOMALY_TYPE"]
STR = {c: "string" for c in KEEP if c not in ("EPOCH_SECONDS", "USD_AMOUNT")}

t0 = time.time()
part = 0
total = 0
for chunk in pd.read_csv(CSV, usecols=KEEP, chunksize=500_000, dtype=STR):
    chunk.to_parquet(f"{OUT}/part_{part:03d}.parquet", index=False)
    total += len(chunk)
    if part % 5 == 0:
        print(f"part {part}: {total:,} rows, {time.time()-t0:.0f}s", flush=True)
    part += 1

import duckdb
con = duckdb.connect()
print("verify:", con.execute(
    f"SELECT count(*), count(*) FILTER (ANOMALY_TYPE <> '') "
    f"FROM read_parquet('{OUT}/part_*.parquet')").fetchall())
print(f"DONE: {total:,} rows in {part} parts, {time.time()-t0:.0f}s")
