import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ddb, full_glob
con = ddb(); G = full_glob()
q = lambda s: con.execute(s).df()

print("=== route shape (clean rows) ===")
print(q(f"""
SELECT PARTICIPANT_COUNT nb, COUNT(*) n,
       ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER (),2) pct,
       ROUND(AVG(CASE WHEN ORDERING_TYPE='B' THEN 1.0 ELSE 0 END),4) b_send,
       ROUND(AVG(CASE WHEN CURRENCY_CONVERSION_COUNT>0 THEN 1.0 ELSE 0 END),4) conv_any,
       ROUND(AVG(CASE WHEN has_gap THEN 1.0 ELSE 0 END),4) gap_any,
       ROUND(MEDIAN(TOTAL_DURATION),0) med_dur
FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NULL
GROUP BY 1 ORDER BY 1""").to_string(index=False))

print("\n=== same vs cross country x route length ===")
print(q(f"""
SELECT (upper(substr(split_part(BIC8_PATH,';',1),5,2)) = upper(substr(split_part(BIC8_PATH,';',-1),5,2))) same,
       PARTICIPANT_COUNT nb, COUNT(*) n,
       ROUND(AVG(CASE WHEN CURRENCY_CONVERSION_COUNT>0 THEN 1.0 ELSE 0 END),4) conv_any,
       ROUND(AVG(CURRENCY_CONVERSION_COUNT),3) mean_conv,
       ROUND(MEDIAN(CURRENCY_CONVERSION_COUNT),1) med_conv
FROM read_parquet('{G}')
WHERE ANOMALY_TYPE IS NULL AND gap_head=FALSE AND gap_tail=FALSE
GROUP BY 1,2 ORDER BY 1,2""").to_string(index=False))

print("\n=== overall shares (clean) ===")
print(q(f"""
SELECT COUNT(*) n,
  ROUND(AVG(CASE WHEN upper(substr(split_part(BIC8_PATH,';',1),5,2))
                    = upper(substr(split_part(BIC8_PATH,';',-1),5,2)) THEN 1.0 ELSE 0 END),4) same_country,
  ROUND(AVG(CASE WHEN ORDERING_TYPE='B' THEN 1.0 ELSE 0 END),4) b_send,
  ROUND(AVG(CASE WHEN BENEFICIARY_TYPE='B' THEN 1.0 ELSE 0 END),4) b_ben,
  ROUND(AVG(CASE WHEN CURRENCY_CONVERSION_COUNT>0 THEN 1.0 ELSE 0 END),4) conv_any,
  ROUND(AVG(CASE WHEN has_gap THEN 1.0 ELSE 0 END),4) gap_any,
  ROUND(AVG(CASE WHEN TRANSACTION_TYPE_CODE='Covered' THEN 1.0 ELSE 0 END),4) covered
FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NULL""").to_string(index=False))

print("\n=== per-bank currency: does the middle bank decide conversions? ===")
print(q(f"""
SELECT (upper(substr(bank,5,2)) = upper(substr(split_part(BIC8_PATH,';',1),5,2))) same_as_sender,
       COUNT(*) n
FROM (SELECT BIC8_PATH, unnest(string_split(BIC8_PATH,';')) bank
      FROM read_parquet('{G}') WHERE ANOMALY_TYPE IS NULL AND PARTICIPANT_COUNT=3)
GROUP BY 1""").to_string(index=False))
