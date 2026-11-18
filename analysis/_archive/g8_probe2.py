"""Probe round 2: account-replacement alternatives, recall gaps, fat-finger tail, CEO fixed, romance types."""
import duckdb
from _common import PARTY_CACHE, full_glob

SEC = 86400

PG = full_glob(PARTY_CACHE)
con = duckdb.connect()

def df(sql):
    return con.execute(sql).df()

print("--- A. ROMANCE rows: ordering/beneficiary TYPE columns ---")
print(df(f"""SELECT ORDERING_TYPE, BENEFICIARY_TYPE, count(*) n
    FROM read_parquet('{PG}') WHERE ANOMALY_TYPE = 'ROMANCE_SCAM'
    GROUP BY 1, 2 ORDER BY n DESC""").to_string(index=False))

print("\n--- B. CEO fixed: clean baseline = anomaly IS NULL ---")
print(df(f"""
    WITH bb AS (
        SELECT EPOCH_SECONDS ts, ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, USD_AMOUNT amt,
               ANOMALY_TYPE = 'CEO_SCAM' AS ceo,
               row_number() OVER (PARTITION BY ORDERING_ACCOUNT, BENEFICIARY_ACCOUNT
                                  ORDER BY EPOCH_SECONDS) = 1 AS first_contact
        FROM read_parquet('{PG}')
        WHERE ORDERING_TYPE = 'B' AND BENEFICIARY_TYPE = 'B'
          AND ORDERING_ACCOUNT IS NOT NULL AND BENEFICIARY_ACCOUNT IS NOT NULL AND USD_AMOUNT IS NOT NULL)
    SELECT CASE WHEN ceo THEN 'ceo' WHEN ceo IS NULL THEN 'clean' ELSE 'other-label' END AS grp,
           count(*) n, median(amt) med_amt, quantile_cont(amt, 0.9) p90_amt,
           avg(CASE WHEN first_contact THEN 1.0 ELSE 0.0 END) first_contact_rate
    FROM bb GROUP BY 1""").to_string(index=False))

print("\n--- C. ACCOUNT REPLACEMENT alt 1: same oa, same beneficiary BANK, different account, earlier ---")
print(df(f"""
    WITH r AS (
        SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, BENEFICIARY_BIC8 bbnk, EPOCH_SECONDS ts
        FROM read_parquet('{PG}') WHERE ANOMALY_TYPE = 'ACCOUNT_REPLACEMENT_SCAM')
    SELECT count(*) n_scam,
           count(*) FILTER (EXISTS (
               SELECT 1 FROM read_parquet('{PG}') p WHERE p.ANOMALY_TYPE IS NULL
                 AND p.ORDERING_ACCOUNT = r.oa AND p.BENEFICIARY_ACCOUNT <> r.ba
                 AND p.EPOCH_SECONDS < r.ts
                 AND (p.BENEFICIARY_BIC8 = r.bbnk OR p.BENEFICIARY_TOKENS = (SELECT q.BENEFICIARY_TOKENS FROM read_parquet('{PG}') q WHERE q.ANOMALY_TYPE='ACCOUNT_REPLACEMENT_SCAM' AND q.BENEFICIARY_ACCOUNT=r.ba AND q.ORDERING_ACCOUNT=r.oa LIMIT 1))
           )) AS n_prior_other_acct_same_bank
    FROM r""").to_string(index=False))

print("\n--- C2. per-scam-row: was THIS beneficiary account ever paid by this oa before/after? ---")
print(df(f"""
    WITH r AS (
        SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, EPOCH_SECONDS ts
        FROM read_parquet('{PG}') WHERE ANOMALY_TYPE = 'ACCOUNT_REPLACEMENT_SCAM')
    SELECT count(*) n_scam,
           count(*) FILTER (EXISTS (
               SELECT 1 FROM read_parquet('{PG}') p WHERE p.ANOMALY_TYPE IS NULL
                 AND p.ORDERING_ACCOUNT = r.oa AND p.BENEFICIARY_ACCOUNT = r.ba
                 AND p.EPOCH_SECONDS < r.ts)) AS ba_seen_before,
           count(*) FILTER (EXISTS (
               SELECT 1 FROM read_parquet('{PG}') p WHERE p.ANOMALY_TYPE IS NULL
                 AND p.ORDERING_ACCOUNT = r.oa AND p.BENEFICIARY_ACCOUNT = r.ba
                 AND p.EPOCH_SECONDS > r.ts)) AS ba_paid_after
    FROM r""").to_string(index=False))

print("\n--- C3. example: history of one replacement victim's payments around the scam row ---")
ex = df(f"""SELECT ORDERING_ACCOUNT oa, BENEFICIARY_ACCOUNT ba, EPOCH_SECONDS ts
    FROM read_parquet('{PG}') WHERE ANOMALY_TYPE = 'ACCOUNT_REPLACEMENT_SCAM' LIMIT 1""")
oa, ba = ex.oa.iloc[0], ex.ba.iloc[0]
print(f"victim {oa} / scam ba {ba}")
print(df(f"""SELECT EPOCH_SECONDS ts, BENEFICIARY_ACCOUNT ba, USD_AMOUNT amt, ANOMALY_TYPE
    FROM read_parquet('{PG}') WHERE ORDERING_ACCOUNT = '{oa}'
      AND EPOCH_SECONDS BETWEEN {int(ex.ts.iloc[0]) - 30*SEC} AND {int(ex.ts.iloc[0]) + 30*SEC}
    ORDER BY ts""").to_string(index=False))

print("\n--- D. FAT FINGER: tail of log10 ratio vs clean ---")
print(df(f"""
    WITH sbase AS (
        SELECT ORDERING_ACCOUNT oa, quantile_cont(USD_AMOUNT, 0.5) med_amt
        FROM read_parquet('{PG}')
        WHERE ANOMALY_TYPE IS NULL AND USD_AMOUNT > 0 AND ORDERING_ACCOUNT IS NOT NULL
        GROUP BY 1 HAVING count(*) >= 5),
     rows AS (
        SELECT a.USD_AMOUNT / b.med_amt AS ratio, a.ANOMALY_TYPE = 'FAT_FINGER_MISTAKE' AS ff
        FROM read_parquet('{PG}') a JOIN sbase b ON a.ORDERING_ACCOUNT = b.oa
        WHERE a.USD_AMOUNT > 0
          AND (a.ANOMALY_TYPE = 'FAT_FINGER_MISTAKE'
               OR (a.ANOMALY_TYPE IS NULL AND random() < 0.002)))
    SELECT CASE WHEN ff THEN 'fat_finger' ELSE 'clean' END grp, count(*) n,
           median(log10(ratio)) med_log10,
           avg(CASE WHEN abs(log10(ratio)) > 2 THEN 1.0 ELSE 0.0 END) frac_100x_off,
           avg(CASE WHEN abs(log10(ratio) - round(log10(ratio))) < 0.15 THEN 1.0 ELSE 0.0 END) near_pow10
    FROM rows GROUP BY 1""").to_string(index=False))

print("\n--- E. fat finger + recall on same pair? (mistake then recall) ---")
print(df(f"""
    SELECT count(*) n_recall,
           count(*) FILTER (EXISTS (
               SELECT 1 FROM read_parquet('{PG}') p WHERE p.ANOMALY_TYPE = 'FAT_FINGER_MISTAKE'
                 AND p.ORDERING_ACCOUNT = a.ORDERING_ACCOUNT AND p.BENEFICIARY_ACCOUNT = a.BENEFICIARY_ACCOUNT
                 AND abs(p.EPOCH_SECONDS - a.EPOCH_SECONDS) < {SEC})) AS n_ff_pair_1d
    FROM read_parquet('{PG}') a WHERE a.ANOMALY_TYPE = 'CUSTOMER_RECALL'""").to_string(index=False))

print("\n--- F. RECALL: gap to the matching prior payment (same pair + amount +-1%, <=30d before) ---")
print(df(f"""
    WITH r AS (
        SELECT a.EPOCH_SECONDS ts, (SELECT max(p.EPOCH_SECONDS) FROM read_parquet('{PG}') p
               WHERE p.ANOMALY_TYPE IS NULL AND p.ORDERING_ACCOUNT = a.ORDERING_ACCOUNT
                 AND p.BENEFICIARY_ACCOUNT = a.BENEFICIARY_ACCOUNT
                 AND abs(p.USD_AMOUNT - a.USD_AMOUNT) / a.USD_AMOUNT < 0.01
                 AND p.EPOCH_SECONDS BETWEEN a.EPOCH_SECONDS - 30*{SEC} AND a.EPOCH_SECONDS) AS prior_ts
        FROM read_parquet('{PG}') a WHERE a.ANOMALY_TYPE = 'CUSTOMER_RECALL')
    SELECT count(*) n, count(*) FILTER (prior_ts IS NOT NULL) matched,
           quantile_cont(ts - prior_ts, 0.25) p25_gap, median(ts - prior_ts) med_gap,
           quantile_cont(ts - prior_ts, 0.75) p75_gap, max(ts - prior_ts) max_gap
    FROM r""").to_string(index=False))
