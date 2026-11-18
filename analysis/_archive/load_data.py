"""Shared loader: caches the light columns (routing, banks, currency, time, anomalies)
as parquet so we don't re-parse the 518MB CSV every run."""
import pandas as pd, numpy as np, os

CSV = r"D:\downloads\UmDatathonV2\swift_umdac_datathon_2026_fictitious_payment_data.csv"
CACHE = r"D:\downloads\UmDatathonV2\analysis\core_cache.parquet"

LIGHT_COLS = [
    "EPOCH_SECONDS","CURRENCY_CODE","USD_AMOUNT","ORDERING_BIC8","BENEFICIARY_BIC8",
    "BIC8_PATH","TOTAL_DURATION","CONTINUITY_QFLAG","CURRENCY_CONVERSION_COUNT",
    "PARTICIPANT_COUNT","TRANSACTION_TYPE_CODE","ORDERING_TYPE","BENEFICIARY_TYPE","ANOMALY_TYPE",
]

def load_core():
    if os.path.exists(CACHE):
        return pd.read_parquet(CACHE)
    df = pd.read_csv(CSV, usecols=LIGHT_COLS, dtype={
        "CURRENCY_CODE":"string","ORDERING_BIC8":"string","BENEFICIARY_BIC8":"string",
        "BIC8_PATH":"string","CONTINUITY_QFLAG":"string","TRANSACTION_TYPE_CODE":"string",
        "ORDERING_TYPE":"string","BENEFICIARY_TYPE":"string","ANOMALY_TYPE":"string"})
    df.to_parquet(CACHE)
    return df

if __name__ == "__main__":
    df = load_core()
    print(df.shape)
    print(df.dtypes)
    print(df.head(3).to_string())
