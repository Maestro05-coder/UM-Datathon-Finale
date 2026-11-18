"""Probe round 3: label type profiles, recall mechanisms, replacement vs 'new account anywhere', ff tail quantiles."""
import duckdb
from _common import PARTY_CACHE, full_glob

SEC = 86400

PG = full_glob(PARTY_CACHE)
con = duckdb.connect()

def df(sql):
    return con.execute(sql).df()

print("--- A. type profile per label ---")
print(df(f"""SELECT ANOMALY_TYPE, ORDERING_TYPE, BENEFICIARY_TYPE, count(*) n
    FROM read_parquet('{PG}') WHERE ANOMALY_TYPE IS NOT NULL
    GROUP BY ALL ORDER BY ANOMALY_TYPE, n DESC""").to_string(index=False))

print("\n--- B. is the beneficiary account fresh? (ever seen in the whole 90d window, any sender) ---")
print(df(f"""
    WITH ba_seen AS (
        SELECT BENEFICIARY_ACCOUNT ba, min(EPOCH_SECONDS) AS t0
        FROM read_parquet('{PG}') WHERE BENEFICIARY_ACCOUNT IS NOT NULL GROUP BY 1),
     a AS (
        SELECT ANOMALY_TYPE, BENEFICIARY_ACCOUNT ba, EPOCH_SECONDS ts
        FROM read_parquet('{PG}') WHERE ANOMALY_TYPE IS NOT NULL),
     s AS (
        SELECT BENEFICIARY_ACCOUNT ba, EPOCH_SECONDS ts
        FROM read_parquet('{PG}') WHERE ANOMALY_TYPE IS NULL
        USING SAMPLE 0.2 PERCENT (bernoulli, 7)),
     allrows AS (
        SELECT ANOMALY_TYPE, ba, ts FROM a
        UNION ALL
        SELECT NULL, ba, ts FROM s)
    SELECT CASE WHEN ANOMALY_TYPE IS NULL THEN 'clean' ELSE ANOMALY_TYPE END AS grp,
           count(*) n,
           avg(CASE WHEN b.t0 >= r.ts THEN 1.0 ELSE 0.0 END) AS ba_never_seen_before
    FROM allrows r JOIN ba_seen b ON r.ba = b.ba
    GROUP BY 1 ORDER BY 2 DESC""").to_string(index=False))

print("\n--- C. RECALL: swapped-direction match? ratio to prior same-pair payment? ---")
print(df(f"""
    WITH r AS (
        SELECT a.EPOCH_SECONDS ts, a.ORDERING_ACCOUNT oa, a.BENEFICIARY_ACCOUNT ba, a.USD_AMOUNT amt
        FROM read_parquet('{PG}') a WHERE a.ANOMALY_TYPE = 'CUSTOMER_RECALL'),
     swapped AS (
        SELECT count(*) n, count(*) FILTER (EXISTS (
            SELECT 1 FROM read_parquet('{PG}') p WHERE p.ANOMALY_TYPE IS NULL
              AND p.ORDERING_ACCOUNT = r.ba AND p.BENEFICIARY_ACCOUNT = r.oa
              AND abs(p.USD_AMOUNT - r.amt) / r.amt < 0.02
              AND p.EPOCH_SECONDS BETWEEN r.ts - 30*{SEC} AND r.ts)) n_swapped
        FROM r),
     prior_any AS (
        SELECT count(*) n, count(*) FILTER (EXISTS (
            SELECT 1 FROM read_parquet('{PG}') p WHERE p.ANOMALY_TYPE IS NULL
              AND p.ORDERING_ACCOUNT = r.oa AND p.BENEFICIARY_ACCOUNT = r.ba
              AND p.EPOCH_SECONDS BETWEEN r.ts - 30*{SEC} AND r.ts)) n_prior_any
        FROM r)
    SELECT swapped.n, swapped.n_swapped, prior_any.n_prior_any FROM swapped, prior_any""").to_string(index=False))
print("sample recall rows with prior same-pair payments:")
print(df(f"""
    WITH r AS (
        SELECT a.EPOCH_SECONDS ts, a.ORDERING_ACCOUNT oa, a.BENEFICIARY_ACCOUNT ba, a.USD_AMOUNT amt
        FROM read_parquet('{PG}') a WHERE a.ANOMALY_TYPE = 'CUSTOMER_RECALL')
    SELECT r.ts, r.amt, p.EPOCH_SECONDS prior_ts, p.USD_AMOUNT prior_amt
    FROM r JOIN read_parquet('{PG}') p
      ON p.ORDERING_ACCOUNT = r.oa AND p.BENEFICIARY_ACCOUNT = r.ba
     AND p.ANOMALY_TYPE IS NULL AND p.EPOCH_SECONDS BETWEEN r.ts - 30*{SEC} AND r.ts
    LIMIT 12""").to_string(index=False))

print("\n--- D. FAT FINGER: |log10| quantiles ---")
print(df(f"""
    WITH sbase AS (
        SELECT ORDERING_ACCOUNT oa, quantile_cont(USD_AMOUNT, 0.5) med_amt
        FROM read_parquet('{PG}')
        WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0 AND ORDERING_ACCOUNT IS NOT NULL
        GROUP BY 1 HAVING count(*) >= 5),
     rows AS (
        SELECT abs(log10(a.USD_AMOUNT / b.med_amt)) AS dev
        FROM read_parquet('{PG}') a JOIN sbase b ON a.ORDERING_ACCOUNT = b.oa
        WHERE a.ANOMALY_TYPE = 'FAT_FINGER_MISTAKE' AND a.USD_AMOUNT > 0)
    SELECT count(*) n, quantile_cont(dev,0.1) p10, quantile_cont(dev,0.25) p25,
           median(dev) med, quantile_cont(dev,0.75) p75, quantile_cont(dev,0.9) p90,
           min(dev) min_dev
    FROM rows""").to_string(index=False))

print("\n--- E. clean baseline: |log10(amt/own-median)| quantiles ---")
print(df(f"""
    WITH sbase AS (
        SELECT ORDERING_ACCOUNT oa, quantile_cont(USD_AMOUNT, 0.5) med_amt
        FROM read_parquet('{PG}')
        WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0 AND ORDERING_ACCOUNT IS NOT NULL
        GROUP BY 1 HAVING count(*) >= 5),
     rows AS (
        SELECT abs(log10(a.USD_AMOUNT / b.med_amt)) AS dev
        FROM read_parquet('{PG}') a JOIN sbase b ON a.ORDERING_ACCOUNT = b.oa
        WHERE a.ANOMALY_TYPE IS NULL AND a.USD_AMOUNT > 0
          AND random() < 0.002)
    SELECT count(*) n, quantile_cont(dev,0.9) p90, quantile_cont(dev,0.99) p99,
           quantile_cont(dev,0.999) p999, max(dev) max_dev
    FROM rows""").to_string(index=False))

print("\n--- F. DUPLICATE: are there clean same-pair repeats within 2h? (false-positive check) ---")
print(df(f"""
    WITH gaps AS (
        SELECT ANOMALY_TYPE, EPOCH_SECONDS - lag(EPOCH_SECONDS) OVER w AS gap
        FROM read_parquet('{PG}')
        WHERE ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL
          AND USD_AMOUNT IS NOT NULL AND USD_AMOUNT > 0
        WINDOW w AS (PARTITION BY ORDERING_ACCOUNT, BENEFICIARY_ACCOUNT, USD_AMOUNT
                     ORDER BY EPOCH_SECONDS))
    SELECT CASE WHEN ANOMALY_TYPE = 'DUPLICATE_PAYMENT' THEN 'duplicate'
                WHEN ANOMALY_TYPE IS NULL THEN 'clean' ELSE 'other' END grp,
           count(*) FILTER (gap BETWEEN 0 AND 7200) n_within_2h
    FROM gaps WHERE gap IS NOT NULL AND gap >= 0 GROUP BY 1""").to_string(index=False))
