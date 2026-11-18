"""Quick probes for the remaining g8 mechanism questions. Throwaway - results get folded into g8_anomalies.py."""
import duckdb
from _common import PARTY_CACHE, full_glob

SEC = 86400

PG = full_glob(PARTY_CACHE)
con = duckdb.connect()

def df(sql):
    return con.execute(sql).df()

print("--- A. null accounts per label ---")
print(df(f"""SELECT ANOMALY_TYPE, count(*) n,
    count(*) FILTER (ORDERING_ACCOUNT IS NULL) null_oa,
    count(*) FILTER (BENEFICIARY_ACCOUNT IS NULL) null_ba,
    count(*) FILTER (ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL) both_ok
    FROM read_parquet('{PG}') WHERE ANOMALY_TYPE IS NOT NULL GROUP BY 1 ORDER BY 2 DESC""").to_string(index=False))

print("\n--- B. ROMANCE: victim pair structure ---")
print(df(f"""
    WITH cc AS (
        SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, EPOCH_SECONDS ts, USD_AMOUNT amt
        FROM read_parquet('{PG}')
        WHERE ANOMALY_TYPE = 'ROMANCE_SCAM'
          AND ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL),
     pairs AS (
        SELECT oa, ba, count(*) n, min(ts) t0, max(ts) t1,
               count(DISTINCT ts) n_distinct_ts, median(amt) med_amt, max(amt) max_amt
        FROM cc GROUP BY 1, 2)
    SELECT count(*) n_pairs, min(n) min_n, median(n) med_n, max(n) max_n,
           median(t1 - t0) med_span_s, max(t1 - t0) max_span_s,
           median(n_distinct_ts) med_distinct_ts,
           median(med_amt) med_of_med, median(max_amt) med_of_max
    FROM pairs""").to_string(index=False))
print("\nsample victim pairs:")
print(df(f"""
    WITH cc AS (
        SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, EPOCH_SECONDS ts, USD_AMOUNT amt
        FROM read_parquet('{PG}')
        WHERE ANOMALY_TYPE = 'ROMANCE_SCAM'
          AND ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL)
    SELECT oa, ba, ts, amt FROM cc ORDER BY oa, ba, ts LIMIT 25""").to_string(index=False))

print("\n--- C. ROMANCE: same-victim payments to the SAME ba but from ALL anomaly labels? ---")
print(df(f"""
    SELECT a.ANOMALY_TYPE, count(*) n,
           count(*) FILTER (EXISTS (
               SELECT 1 FROM read_parquet('{PG}') p
               WHERE p.ANOMALY_TYPE IS NULL AND p.ORDERING_ACCOUNT = a.ORDERING_ACCOUNT
                 AND p.BENEFICIARY_ACCOUNT = a.BENEFICIARY_ACCOUNT
                 AND p.EPOCH_SECONDS < a.EPOCH_SECONDS)) AS had_prior_same_pair
    FROM read_parquet('{PG}') a
    WHERE a.ANOMALY_TYPE IN ('ROMANCE_SCAM','CEO_SCAM','DUPLICATE_PAYMENT','ACCOUNT_REPLACEMENT_SCAM','CUSTOMER_RECALL')
      AND a.ORDERING_ACCOUNT IS NOT NULL AND a.BENEFICIARY_ACCOUNT IS NOT NULL
    GROUP BY 1""").to_string(index=False))

print("\n--- D. ACCOUNT REPLACEMENT: same name, different account, before/after ---")
print(df(f"""
    WITH r AS (
        SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, BENEFICIARY_TOKENS tok,
               EPOCH_SECONDS ts, USD_AMOUNT amt
        FROM read_parquet('{PG}')
        WHERE ANOMALY_TYPE = 'ACCOUNT_REPLACEMENT_SCAM'
          AND ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL
          AND BENEFICIARY_TOKENS IS NOT NULL)
    SELECT count(*) n_scam,
           count(*) FILTER (EXISTS (
               SELECT 1 FROM read_parquet('{PG}') p
               WHERE p.ANOMALY_TYPE IS NULL AND p.ORDERING_ACCOUNT = r.oa
                 AND p.BENEFICIARY_TOKENS = r.tok AND p.BENEFICIARY_ACCOUNT <> r.ba
                 AND p.EPOCH_SECONDS BETWEEN r.ts - 90*{SEC} AND r.ts)) AS n_name_paid_other_acct_before,
           count(*) FILTER (EXISTS (
               SELECT 1 FROM read_parquet('{PG}') p
               WHERE p.ANOMALY_TYPE IS NULL AND p.ORDERING_ACCOUNT = r.oa
                 AND p.BENEFICIARY_ACCOUNT = r.ba
                 AND p.EPOCH_SECONDS BETWEEN r.ts + 1 AND r.ts + 90*{SEC})) AS n_new_acct_paid_again_after
    FROM r""").to_string(index=False))

print("\n--- E. baseline: same name-different-account-before rate for CLEAN rows ---")
print(df(f"""
    WITH s AS (
        SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, BENEFICIARY_TOKENS tok, EPOCH_SECONDS ts
        FROM read_parquet('{PG}') WHERE ANOMALY_TYPE IS NULL
          AND ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL
          AND BENEFICIARY_TOKENS IS NOT NULL
        USING SAMPLE 5000 ROWS (reservoir, 7))
    SELECT count(*) n,
           count(*) FILTER (EXISTS (
               SELECT 1 FROM read_parquet('{PG}') p
               WHERE p.ANOMALY_TYPE IS NULL AND p.ORDERING_ACCOUNT = s.oa
                 AND p.BENEFICIARY_TOKENS = s.tok AND p.BENEFICIARY_ACCOUNT <> s.ba
                 AND p.EPOCH_SECONDS BETWEEN s.ts - 90*{SEC} AND s.ts)) AS n_name_other_acct_before
    FROM s""").to_string(index=False))

print("\n--- F. RECALL rows: nulls? what do they look like ---")
print(df(f"""SELECT count(*) n,
    count(*) FILTER (ORDERING_ACCOUNT IS NULL) null_oa,
    count(*) FILTER (BENEFICIARY_ACCOUNT IS NULL) null_ba
    FROM read_parquet('{PG}') WHERE ANOMALY_TYPE = 'CUSTOMER_RECALL'""").to_string(index=False))

print("\n--- G. FAT FINGER: clean baseline of log10(amt / own-sender-median) ---")
print(df(f"""
    WITH s AS (
        SELECT a.USD_AMOUNT / b.med_amt AS ratio
        FROM read_parquet('{PG}') a
        JOIN (SELECT ORDERING_ACCOUNT oa, quantile_cont(USD_AMOUNT,0.5) med_amt
              FROM read_parquet('{PG}')
              WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0 AND ORDERING_ACCOUNT IS NOT NULL
              GROUP BY 1 HAVING count(*) >= 5) b ON a.ORDERING_ACCOUNT = b.oa
        WHERE a.ANOMALY_TYPE IS NULL AND a.USD_AMOUNT > 0
        USING SAMPLE 0.5 PERCENT (bernoulli, 7))
    SELECT count(*) n, median(log10(ratio)) med_log, quantile_cont(log10(ratio), 0.01) p01,
           quantile_cont(log10(ratio), 0.99) p99,
           avg(CASE WHEN abs(log10(ratio)) > 2 THEN 1.0 ELSE 0.0 END) frac_gt_100x
    FROM s""").to_string(index=False))
