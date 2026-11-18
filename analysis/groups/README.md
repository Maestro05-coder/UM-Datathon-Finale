# Groups — one folder per feature group

Each folder holds the group's charts and a plain-language README.md with:
the rules found, what each chart means, and real rows from the CSV as proof.
(Cached aggregates the chart scripts render from live in `analysis/agg/`.)

| folder            | group                                 | status  |
| :---------------- | :------------------------------------ | :-----: |
| `g1_time/`        | When payments happen                  | ✅ done |
| `g2_currency/`    | Currencies & conversions              | ✅ done |
| `g3_amount/`      | Amounts                               | ✅ done |
| `g4_banks/`       | Banks & countries                     | ✅ done |
| `g5_routing/`     | Which banks a payment travels through | ✅ done |
| `g6_fx_duration/` | FX & how long payments take           | ✅ done |
| `g7_parties/`     | Parties & text fields                 | ✅ done |
| `g8_anomalies/`   | Anomalies                             | ✅ done |

### Headline rules per group

- **g1_time** — one shared 24-hour template (two busy windows) stamped on each
  country's own **integer-hour clock**: 18 distinct offsets turn a −0.02 curve
  correlation into +0.99, and the two windows hold statistically identical payments
  (so the "cut-off batch" story is dead).
- **g2_currency** — currency = sender side (first bank 93% vs beneficiary 19%);
  countries have home currencies (~92–97%); foreign = mostly EUR/USD leaning to the
  beneficiary; USD payments get nice-number amounts; **no FX-rate table exists**
  (within-country currency deltas ≈ 0).
- **g3_amount** — lognormal, one shared shape (sigma≈1.05) around a **free
  per-country centre** ($48 Guinea-Bissau … $31k Monaco): fixed (split-half
  r = 0.9977), not explained by size/mix/route (R² 0.46; corridor held fixed keeps
  the ladder, r = 0.986); USD gets a whole-number/{1,2,5}×10^k mode; **2.83% of rows
  are storm rows** (per day+currency injected base × integer multiples).
- **g4_banks** — **BIC8 is a fixed 8-slot layout** (4-digit pool of 1,075 numbers +
  country + one of 25 house letters + constant '0'; 0 exceptions in 25.8M
  appearances) and **type B adds a constant +0.865 dex (7.3×)** at every income
  level (167 countries, sd 0.100); banks add stable own tilts (split-half r 0.93).
  Bank/corridor censuses (8,727 banks, 24,017 corridors) are supporting facts, not rules.
- **g7_parties** — all accounts are `_FAKE_...` (54% IBAN-shaped, prefix = bank
  country 100%); 391k sender accounts (78.6% of rows from 29k whales) vs 2.6M
  one-off beneficiaries; TOKENS = the template of DETAILS (18 families);
  **decoy rule: sender address = bank country 100%, beneficiary address is a
  random-world pool (0.98% match)**; B=business / C=person confirmed in text.
- **g5_routing** — type = bank count; `...` = QFLAG N; ~5%-per-link hiding;
  conversion count rule; endpoint columns ~5% wrong.
- **g6_fx_duration** — duration = sum of per-step delays; conversions and hidden
  banks cost nothing.
- **g8_anomalies** — FAT_FINGER confirmed as `honest × 10^k` with **k varying per
  row** (56.0% land back in the sender's middle 50% after ÷10–1,000 vs 34.7% clean);
  the "one fixed comma position" and "copy of a real payment" versions are refuted;
  5 other labels: see its README.

Everything is from the 10m-row CSV only. Extra/superseded charts live in `analysis/_archive/`.

Scripts live in `analysis/`:
- analysis scripts (`g1_time.py` … `g8_anomalies.py`) compute and print the numbers,
  and `g1`–`g4` also draw their own charts;
- chart-only scripts `g5_charts.py`, `g6_charts.py`, `g7_charts.py`, `g8_charts.py`
  render the PNGs for groups 5–8 from cached aggregates in `analysis/agg/`, so charts
  can be restyled without re-streaming 10M rows.

Method notes (apply to every group):
- Charts use the shared style in `analysis/_style.py` (`import _style as S; S.apply()`):
  one idea per chart, the unit on each axis, values printed on the marks, and every
  legend placed below the plot area so it never covers the data.
- No log-scale bars (a bar's length would lie about the ratio). When a value spans
  orders of magnitude, use dots or points on a log axis, or a "times the baseline"
  linear bar with the baseline marked.
- Full-data work runs on **DuckDB** over the parquet caches (`cache_full/`, `cache_party/`).
  `cache_party/` = account + text columns, built once by `build_cache_party.py`.
- No systematic row-sampling (`::40`) for analysis; random samples only, and only for
  chart shapes. Every number quoted in a README is exact.
- Rare buckets get exact stats (counts, min/max, quantiles), never reservoir medians.
