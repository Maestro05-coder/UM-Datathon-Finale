"""Fact-check the three claims from Swift_Dataset_Anatomy_and_Generation_Rules.pdf
that our g8 did NOT test: (1) replacement = same sender+amount, different account;
(2) romance currency skew INR/CNY; (3) 2,624 unlabelled exact-duplicate groups."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import duckdb
from _common import PARTY_CACHE, full_glob

SEC = 86400  # epoch seconds per day

PG = full_glob(PARTY_CACHE)
con = duckdb.connect()

def df(sql):
    return con.execute(sql).df()

print("--- 1. replacement: same sender + same amount (+-1%), different beneficiary account ---")
print(df(f"""
    WITH r AS (
        SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, USD_AMOUNT amt, EPOCH_SECONDS ts
        FROM read_parquet('{PG}') WHERE ANOMALY_TYPE = 'ACCOUNT_REPLACEMENT_SCAM'),
     s AS (
        SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, USD_AMOUNT amt, EPOCH_SECONDS ts
        FROM read_parquet('{PG}') WHERE ANOMALY_TYPE IS NULL
          AND ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL
        USING SAMPLE 5000 ROWS (reservoir, 7))
    SELECT (SELECT count(*) FILTER (EXISTS (
                SELECT 1 FROM read_parquet('{PG}') p WHERE p.ANOMALY_TYPE IS NULL
                  AND p.ORDERING_ACCOUNT = r0.oa AND p.BENEFICIARY_ACCOUNT <> r0.ba
                  AND abs(p.USD_AMOUNT - r0.amt) / r0.amt < 0.01
                  AND p.EPOCH_SECONDS < r0.ts
                  AND p.EPOCH_SECONDS > r0.ts - 90*{SEC}))
            FROM r r0) AS scam_hits,
           (SELECT count(*) FROM r) AS n_scam,
           (SELECT count(*) FILTER (EXISTS (
                SELECT 1 FROM read_parquet('{PG}') p WHERE p.ANOMALY_TYPE IS NULL
                  AND p.ORDERING_ACCOUNT = s.oa AND p.BENEFICIARY_ACCOUNT <> s.ba
                  AND abs(p.USD_AMOUNT - s.amt) / s.amt < 0.01
                  AND p.EPOCH_SECONDS < s.ts
                  AND p.EPOCH_SECONDS > s.ts - 90*{SEC}))
            FROM s) AS clean_hits,
           (SELECT count(*) FROM s) AS n_clean""").to_string(index=False))

print("\n--- 2. romance: currency skew? (top 8 currencies, scam vs clean C-senders) ---")
print(df(f"""
    WITH s AS (
        SELECT CURRENCY_CODE cc, count(*) n FROM read_parquet('{PG}')
        WHERE ANOMALY_TYPE = 'ROMANCE_SCAM' GROUP BY 1),
     c AS (
        SELECT CURRENCY_CODE cc, count(*) n FROM (
            SELECT CURRENCY_CODE FROM read_parquet('{PG}')
            WHERE ANOMALY_TYPE IS NULL AND ORDERING_TYPE = 'C'
            USING SAMPLE 0.3 PERCENT (bernoulli, 7))
        GROUP BY 1)
    SELECT coalesce(s.cc, c.cc) AS cc, s.n AS scam_n, c.n AS clean_n
    FROM s FULL JOIN c ON s.cc = c.cc
    ORDER BY scam_n DESC NULLS LAST""").head(8).to_string(index=False))

print("\n--- 3. unlabelled exact-duplicate groups (same oa+ba+amount+currency) ---")
print(df(f"""
    WITH d AS (
        SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, USD_AMOUNT amt, CURRENCY_CODE cc,
               count(*) n, count(*) FILTER (ANOMALY_TYPE = 'DUPLICATE_PAYMENT') n_dup
        FROM read_parquet('{PG}')
        WHERE ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL
          AND USD_AMOUNT IS NOT NULL
        GROUP BY 1, 2, 3, 4 HAVING count(*) >= 2)
    SELECT count(*) AS groups_n2,
           count(*) FILTER (WHERE n_dup = 0) AS groups_all_clean,
           sum(n) FILTER (WHERE n_dup = 0) AS rows_in_clean_groups
    FROM d""").to_string(index=False))
