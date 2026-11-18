"""Probe round 4 (final): recall cross-label overlap, per-label amounts, recall pair-history size."""
import duckdb
from _common import PARTY_CACHE, full_glob

SEC = 86400

PG = full_glob(PARTY_CACHE)
con = duckdb.connect()

def df(sql):
    return con.execute(sql).df()

print("--- A. per-label USD amount profile (BIC8-currency USD_AMOUNT) ---")
print(df(f"""SELECT ANOMALY_TYPE, count(*) n, median(USD_AMOUNT) med,
           quantile_cont(USD_AMOUNT, 0.25) p25, quantile_cont(USD_AMOUNT, 0.75) p75,
           quantile_cont(USD_AMOUNT, 0.9) p90
    FROM read_parquet('{PG}') GROUP BY 1 ORDER BY 2 DESC""").to_string(index=False))

print("\n--- B. clean baseline amount profile ---")
print(df(f"""SELECT count(*) n, median(USD_AMOUNT) med, quantile_cont(USD_AMOUNT, 0.9) p90
    FROM read_parquet('{PG}') WHERE ANOMALY_TYPE IS NULL""").to_string(index=False))

print("\n--- C. RECALL: does the same (ordering,beneficiary) pair carry another label? ---")
print(df(f"""
    SELECT count(*) n_recall,
           count(*) FILTER (EXISTS (SELECT 1 FROM read_parquet('{PG}') p
               WHERE p.ANOMALY_TYPE IS NOT NULL AND p.ANOMALY_TYPE <> 'CUSTOMER_RECALL'
                 AND p.ORDERING_ACCOUNT = a.ORDERING_ACCOUNT
                 AND p.BENEFICIARY_ACCOUNT = a.BENEFICIARY_ACCOUNT)) AS n_pair_has_other_label
    FROM read_parquet('{PG}') a WHERE a.ANOMALY_TYPE = 'CUSTOMER_RECALL'""").to_string(index=False))
print("which other labels appear on recall pairs:")
print(df(f"""
    SELECT a.ANOMALY_TYPE AS recall, b.ANOMALY_TYPE AS other, count(*) n
    FROM read_parquet('{PG}') a
    JOIN read_parquet('{PG}') b
      ON a.ANOMALY_TYPE = 'CUSTOMER_RECALL' AND b.ANOMALY_TYPE NOT IN ('CUSTOMER_RECALL')
     AND a.ORDERING_ACCOUNT = b.ORDERING_ACCOUNT AND a.BENEFICIARY_ACCOUNT = b.BENEFICIARY_ACCOUNT
    GROUP BY 1, 2 ORDER BY n DESC""").to_string(index=False))

print("\n--- D. RECALL: prior-same-pair rate, clean baseline (30d window) ---")
print(df(f"""
    WITH s AS (
        SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, EPOCH_SECONDS ts
        FROM read_parquet('{PG}') WHERE ANOMALY_TYPE IS NULL
          AND ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL
        USING SAMPLE 5000 ROWS (reservoir, 7))
    SELECT count(*) n, count(*) FILTER (EXISTS (
        SELECT 1 FROM read_parquet('{PG}') p WHERE p.ANOMALY_TYPE IS NULL
          AND p.ORDERING_ACCOUNT = s.oa AND p.BENEFICIARY_ACCOUNT = s.ba
          AND p.EPOCH_SECONDS BETWEEN s.ts - 30*{SEC} AND s.ts)) AS n_prior
    FROM s""").to_string(index=False))

print("\n--- E. RECALL rows: how many total payments has that pair seen (history size)? ---")
print(df(f"""
    WITH hist AS (
        SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, count(*) n, min(EPOCH_SECONDS) t0
        FROM read_parquet('{PG}')
        WHERE ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL
        GROUP BY 1, 2)
    SELECT CASE WHEN a.ANOMALY_TYPE IS NULL THEN 'clean' ELSE a.ANOMALY_TYPE END grp,
           count(*) n, median(h.n) med_pair_history
    FROM read_parquet('{PG}') a JOIN hist h
      ON a.ORDERING_ACCOUNT = h.oa AND a.BENEFICIARY_ACCOUNT = h.ba
    WHERE a.ANOMALY_TYPE IS NULL OR a.ANOMALY_TYPE = 'CUSTOMER_RECALL'
    GROUP BY 1""").to_string(index=False))
