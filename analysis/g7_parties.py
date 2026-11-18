"""g7 - Parties & text fields. Full-data DuckDB over cache_party.

Rules documented here:
  R1  every account string is a synthetic "_FAKE_..." placeholder (10M/10M rows,
      both sides). 54.4% are IBAN-shaped (_FAKE_ + 2 letters + 2 digits + digits);
      their embedded country matches the bank's country 100% (76 prefixes).
      Ordering accounts belong to exactly one bank (100%); beneficiary accounts
      97.6% (max 8 banks).
  R2  a small fixed sender pool, a huge one-off beneficiary pool: 391,132 distinct
      ordering accounts (avg 25.6 rows each, max 75,803) vs 2,590,877 beneficiary
      accounts (avg 3.9). 28,889 senders with >=50 rows carry 78.6% of all rows.
  R3  DETAILS is a party profile: line 1 echoes the account number (94.4% of rows),
      then name / street / city / country, wrapped at 35-char lines. 16% use a
      numbered 1/2/3 structure. TOKENS is the generator's template of DETAILS -
      the same structure written as <token:length> placeholders (18 token families).
  R4  THE DECOY RULE: the ORDERING side's details-country equals its bank's country
      100% of the time (8,453,693 rows with a country token). The BENEFICIARY
      side's details-country matches its bank only 0.98% - it is drawn from a
      population-weighted world pool (CN 14.5%, BR 9.0%, UA 7.2% ...), unrelated
      to the beneficiary bank (US 19.2%, CH 8.3% ...). Beneficiary addresses are
      decorative; the bank carries the real geography.
  R5  ORDERING_TYPE B = business, C = person, confirmed at the text level:
      B rows' tokens contain business/company_keyword 87.6% and person names 0%;
      C rows contain person names 90.7% and business 0%. Same on the beneficiary
      side and for anomalous rows (labels do not change the templates).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ddb

con = ddb()
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache_party", "part_*.parquet").replace("\\", "/")
GROUP = "g7_parties"

# ---------------------------------------------------------------- 1. account census
print("=== 1. account census ===")
r = con.execute(f"""
    SELECT AVG(length(ORDERING_ACCOUNT)) la, AVG(length(BENEFICIARY_ACCOUNT)) lb,
           SUM(CASE WHEN starts_with(ORDERING_ACCOUNT, '_FAKE_') THEN 1 ELSE 0 END) fake_o,
           SUM(CASE WHEN starts_with(BENEFICIARY_ACCOUNT, '_FAKE_') THEN 1 ELSE 0 END) fake_b,
           COUNT(*) n
    FROM read_parquet('{P}')
""").df()
print(r.T.round(3).to_string())
IBAN = r"^_FAKE_[A-Z]{2}[0-9]{2}"
r = con.execute(f"""
    SELECT 'ordering' side,
           AVG(CASE WHEN regexp_matches(ORDERING_ACCOUNT, '{IBAN}') THEN 1.0 ELSE 0 END) ibanish,
           COUNT(*) n
    FROM read_parquet('{P}')
    UNION ALL
    SELECT 'beneficiary',
           AVG(CASE WHEN regexp_matches(BENEFICIARY_ACCOUNT, '{IBAN}') THEN 1.0 ELSE 0 END), COUNT(*)
    FROM read_parquet('{P}')
""").df()
print("strict-IBAN share (2 letters + 2 digits):")
print(r.round(4).to_string(index=False))
r = con.execute(f"""
    WITH t AS (
      SELECT upper(substr(ORDERING_ACCOUNT, 7, 2)) ac, upper(substr(ORDERING_BIC8, 5, 2)) bc
      FROM read_parquet('{P}') WHERE regexp_matches(ORDERING_ACCOUNT, '{IBAN}')
    )
    SELECT AVG(CASE WHEN ac = bc THEN 1.0 ELSE 0 END) match, COUNT(DISTINCT ac) n_pfx FROM t
""").df()
print("iban prefix == bank country:", r.T.round(4).to_string())

# ---------------------------------------------------------------- 2. account -> bank + reuse
print("\n=== 2. account-to-bank + reuse ===")
r = con.execute(f"""
    WITH t AS (
      SELECT ORDERING_ACCOUNT a, COUNT(DISTINCT ORDERING_BIC8) nb, COUNT(*) n
      FROM read_parquet('{P}') GROUP BY 1
    )
    SELECT 'ordering' side, COUNT(*) n_acct, AVG(n*1.0) av_rows, MAX(n) mx,
           AVG(CASE WHEN nb = 1 THEN 1.0 ELSE 0 END) one_bank
    FROM t
    UNION ALL
    SELECT 'beneficiary', COUNT(*), AVG(n*1.0), MAX(n), AVG(CASE WHEN nb = 1 THEN 1.0 ELSE 0 END)
    FROM (
      SELECT BENEFICIARY_ACCOUNT a, COUNT(DISTINCT BENEFICIARY_BIC8) nb, COUNT(*) n
      FROM read_parquet('{P}') GROUP BY 1
    )
""").df()
print(r.round(3).to_string(index=False))
r = con.execute(f"""
    WITH s AS (SELECT ORDERING_ACCOUNT a, COUNT(*) c FROM read_parquet('{P}') GROUP BY 1)
    SELECT SUM(CASE WHEN c >= 50 THEN c ELSE 0 END) rows_big,
           SUM(CASE WHEN c >= 50 THEN 1 ELSE 0 END) n_acct FROM s
""").df()
print("senders with >=50 rows: %d accounts carrying %.1f%% of rows"
      % (r.n_acct[0], r.rows_big[0] / 1e5))
whale = con.execute(f"""
    SELECT ORDERING_ACCOUNT a, ORDERING_BIC8 bank, COUNT(*) n,
           COUNT(DISTINCT BENEFICIARY_ACCOUNT) nb, MEDIAN(log10(USD_AMOUNT)) m
    FROM read_parquet('{P}') GROUP BY 1, 2 ORDER BY n DESC LIMIT 5
""").df()
print("top-5 whale senders:")
print(whale.round(2).to_string(index=False))

# Charts live in g7_charts.py (chart-only, reads cache_party via DuckDB).

# ---------------------------------------------------------------- 3. details/tokens structure
print("\n=== 3. DETAILS / TOKENS structure ===")
r = con.execute(f"""
    SELECT AVG(CASE WHEN ORDERING_DETAILS LIKE '%' || substr(replace(ORDERING_ACCOUNT, '_FAKE_', ''), 1, 12) || '%'
                THEN 1.0 ELSE 0 END) echo,
           AVG(length(ORDERING_DETAILS)) av_len, MAX(length(ORDERING_DETAILS)) mx_len,
           AVG(CASE WHEN ORDERING_DETAILS LIKE '%1/%' THEN 1.0 ELSE 0 END) structured,
           COUNT(*) n
    FROM read_parquet('{P}') WHERE ORDERING_DETAILS IS NOT NULL
""").df()
print(r.T.round(3).to_string())
tv = con.execute(f"""
    WITH t AS (
      SELECT regexp_extract_all(ORDERING_TOKENS, '<[a-z_]+:') tok
      FROM read_parquet('{P}') USING SAMPLE 1 PERCENT (bernoulli, 7) LIMIT 40000
    ), u AS (SELECT unnest(tok) x FROM t)
    SELECT x, COUNT(*) c FROM u GROUP BY 1 ORDER BY c DESC LIMIT 12
""").df()
print("token vocabulary (top 12 of 18 families):")
print(tv.to_string(index=False))
r = con.execute(f"""
    SELECT AVG(CASE WHEN (regexp_matches(ORDERING_ACCOUNT, '{IBAN}') AND ORDERING_TOKENS LIKE '%<iban:%')
                     OR (NOT regexp_matches(ORDERING_ACCOUNT, '{IBAN}') AND ORDERING_TOKENS NOT LIKE '%<iban:%')
                THEN 1.0 ELSE 0.0 END) consistent
    FROM read_parquet('{P}') WHERE ORDERING_TOKENS IS NOT NULL AND ORDERING_TOKENS != ''
""").df()
print("account-shape <-> <iban:> template consistency:", float(r.consistent[0]))

# Charts live in g7_charts.py (chart-only, reads cache_party via DuckDB).

# ---------------------------------------------------------------- 4. the decoy rule
print("\n=== 4. details-country vs bank-country (the decoy rule) ===")
r = con.execute(f"""
    WITH c AS (
      SELECT regexp_extract(ORDERING_TOKENS, '(country_code|country_name):([A-Z]{{2}})', 2) dc,
             upper(substr(ORDERING_BIC8, 5, 2)) bc
      FROM read_parquet('{P}') WHERE ORDERING_TOKENS IS NOT NULL
    )
    SELECT 'ordering' side, COUNT(*) n, AVG(CASE WHEN dc = bc THEN 1.0 ELSE 0 END) match
    FROM c WHERE dc != ''
    UNION ALL
    SELECT 'beneficiary', COUNT(*), AVG(CASE WHEN dc = bc THEN 1.0 ELSE 0 END)
    FROM (
      SELECT regexp_extract(BENEFICIARY_TOKENS, '(country_code|country_name):([A-Z]{{2}})', 2) dc,
             upper(substr(BENEFICIARY_BIC8, 5, 2)) bc
      FROM read_parquet('{P}') WHERE BENEFICIARY_TOKENS IS NOT NULL
    ) WHERE dc != ''
""").df()
print(r.to_string(index=False))
bdc = con.execute(f"""
    WITH c AS (
      SELECT regexp_extract(BENEFICIARY_TOKENS, '(country_code|country_name):([A-Z]{{2}})', 2) dc
      FROM read_parquet('{P}') WHERE BENEFICIARY_TOKENS IS NOT NULL
    )
    SELECT dc, COUNT(*) n FROM c WHERE dc != '' GROUP BY 1 ORDER BY n DESC LIMIT 10
""").df()
bbc = con.execute(f"""
    SELECT upper(substr(BENEFICIARY_BIC8, 5, 2)) bc, COUNT(*) n
    FROM read_parquet('{P}') GROUP BY 1 ORDER BY n DESC LIMIT 10
""").df()
print("beneficiary details-country top10:", list(bdc.dc))
print("beneficiary bank-country top10:   ", list(bbc.bc))

# Charts live in g7_charts.py (chart-only, reads cache_party via DuckDB).

# ---------------------------------------------------------------- 5. B/C at text level
print("\n=== 5. type B vs C at the text level ===")
r = con.execute(f"""
    SELECT ORDERING_TYPE ot,
           AVG(CASE WHEN ORDERING_TOKENS LIKE '%<business:%' OR ORDERING_TOKENS LIKE '%<company_keyword:%' THEN 1.0 ELSE 0 END) p_business,
           AVG(CASE WHEN ORDERING_TOKENS LIKE '%<first_name:%' OR ORDERING_TOKENS LIKE '%<last_name:%' THEN 1.0 ELSE 0 END) p_person,
           COUNT(*) n
    FROM read_parquet('{P}') WHERE ORDERING_TOKENS IS NOT NULL GROUP BY 1
""").df()
print("ordering side:")
print(r.round(4).to_string(index=False))
r = con.execute(f"""
    SELECT ORDERING_TYPE ot, ANOMALY_TYPE IS NOT NULL anom,
           AVG(CASE WHEN ORDERING_TOKENS LIKE '%<business:%' OR ORDERING_TOKENS LIKE '%<company_keyword:%' THEN 1.0 ELSE 0 END) p_business,
           AVG(CASE WHEN ORDERING_TOKENS LIKE '%<first_name:%' OR ORDERING_TOKENS LIKE '%<last_name:%' THEN 1.0 ELSE 0 END) p_person
    FROM read_parquet('{P}') WHERE ORDERING_TOKENS IS NOT NULL GROUP BY 1, 2
""").df()
print("anomalous vs clean (same mix):")
print(r.round(3).to_string(index=False))

# Charts live in g7_charts.py (chart-only, reads cache_party via DuckDB).

# ---------------------------------------------------------------- 6. proof rows
print("\n=== 6. proof rows ===")
pr = con.execute(f"""
    SELECT ORDERING_ACCOUNT oa, ORDERING_BIC8 ob, ORDERING_DETAILS od
    FROM read_parquet('{P}') WHERE ORDERING_ACCOUNT = '_FAKE_41GBP/9 1 67' LIMIT 1
""").df()
print("whale sender:")
print(pr.to_string(index=False))
pr = con.execute(f"""
    SELECT ORDERING_ACCOUNT oa, ORDERING_DETAILS od
    FROM read_parquet('{P}') WHERE ORDERING_TOKENS LIKE '%<iban:22>%' AND ORDERING_TYPE = 'C'
      AND length(ORDERING_DETAILS) > 100 LIMIT 1
""").df()
print("\nretail sender with IBAN-shaped account:")
for _, rr in pr.iterrows():
    print(rr.oa, "|", str(rr.od).replace(chr(10), " / "))
print("\nDONE g7")
