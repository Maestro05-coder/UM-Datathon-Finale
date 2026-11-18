# UM Datathon 2026 — reverse-engineering a synthetic SWIFT payment feed

This repository holds the full analysis for the **Universiti Malaya UMDAC Datathon 2026
(Finals) — Swift Case Study**. We were given a 10,000,000-row, ~4.95 GB synthetic SWIFT-like
payment file produced by a hidden generator, and asked to work out the rules that generated it
per feature area ("group") and prove each rule with numbers.

Everything here is derived from that single CSV. No external data was used.

---

## What was found (one headline rule per group)

| group | feature area | headline rule |
| :--- | :--- | :--- |
| `g1_time` | when payments happen | One shared 24-hour template with two busy windows, stamped on each of 18 country **integer-hour clocks** (curve correlation −0.02 → +0.99 after alignment). The two windows hold statistically identical payments, so the "cut-off batch" story is dead. |
| `g2_currency` | currencies & conversions | Currency is decided on the **sender side** (first bank 93% vs beneficiary 19%). Countries have home currencies (~92–97%); foreign payments lean EUR/USD toward the beneficiary; USD gets round-number amounts. **No FX-rate table exists.** |
| `g3_amount` | amounts | Lognormal with one shared shape (σ≈1.05) around a **free per-country centre** ($48 Guinea-Bissau … $31k Monaco). Stable under split-half validation (r = 0.9977) and not explained by size, mix or route. USD has a whole-number {1,2,5}×10^k mode. **2.83% of rows are "storm" rows** (per day+currency injected base × integer multiples). |
| `g4_banks` | banks & countries | **BIC8 is a fixed 8-slot layout** (4-digit pool of 1,075 numbers + country + one of 25 house letters + constant `0`; 0 exceptions in 25.8M appearances). **Type B adds a constant +0.865 dex (≈7.3×)** at every income level across 167 countries (sd 0.100). Banks also carry stable own tilts (split-half r = 0.93). |
| `g5_routing` | banks a payment travels through | Type code = number of banks; `...` = a hidden intermediary (QFLAG N); ~5% hiding per link; conversion count follows its own rule; the endpoint columns disagree with the route ~5% of the time. |
| `g6_fx_duration` | FX & duration | Total duration is the **sum of per-step delays**; conversions and hidden banks cost nothing. |
| `g7_parties` | parties & text fields | All accounts are `_FAKE_...` (54% IBAN-shaped, prefix = bank country 100%); 391k sender accounts (78.6% of rows come from 29k whales) vs 2.6M one-off beneficiaries. TOKENS is the template of DETAILS (18 families). **Decoy rule:** sender address = bank country 100%, beneficiary address is a random-world pool (0.98% match). |
| `g8_anomalies` | injected anomalies | FAT_FINGER confirmed as `honest × 10^k` with **k varying per row** (56.0% land back in the sender's middle 50% after ÷10–1,000 vs 34.7% clean). The "one fixed comma position" and "copy of a real payment" versions are refuted. Five other anomaly labels are dissected in its README. |

Each group folder (`analysis/groups/<group>/`) contains a `README.md` with the rules, the dead
ends (with the numbers that killed them), chart explanations, and real rows from the CSV as
proof, plus that group's charts.

---

## Repository layout

```
AGENTS.md                     working conventions for agents/contributors in this repo
rules.md                      global method guardrails + chart design contract
RULES_g1_g4.md                long-form write-up of groups 1–4
*.pdf                         the original case-study brief
analysis/
  _common.py                  shared paths + DuckDB helpers (ddb, full_glob, rand_sample, savefig)
  _style.py                   shared matplotlib style (one idea per chart, values on marks)
  build_cache.py              builds cache_full/  (light columns + derived route features)
  build_cache_party.py        builds cache_party/ (account + DETAILS/TOKENS text columns)
  g0_map.py … g8_*.py         one entry script per group (+ control/follow-up scripts)
  agg/                        cached aggregates (*.pkl) the chart-only scripts render from
  groups/<group>/             README.md + charts, one folder per feature group
  _archive/                   superseded scripts and charts (history only)
```

---

## Reproducing

Requirements: Python 3.9+, and

```
pip install -r requirements.txt
```

1. Place `swift_umdac_datathon_2026_fictitious_payment_data.csv` in `analysis/` (it is **not**
   in this repo — see below).
2. Build the parquet caches once (they are what every script queries):

   ```
   python analysis/build_cache.py
   python analysis/build_cache_party.py
   ```

3. Run any group script from the `analysis/` directory, for example:

   ```
   cd analysis
   python g8_anomalies.py
   ```

   Chart-only scripts (`g5_charts.py`, `g6_charts.py`, `g7_charts.py`, `g8_charts.py`) render
   the PNGs from the cached aggregates in `agg/`, so charts can be restyled without
   re-streaming ten million rows. Full reruns take ~1–2 minutes per group.

## What is *not* in this repo

- The raw 4.95 GB source CSV.
- `analysis/cache_full/` and `analysis/cache_party/` (~2.3 GB of parquet caches).

Both are excluded by `.gitignore`: they exceed GitHub's file/repo limits and are fully
rebuildable with the two build scripts above. Everything else — code, cached aggregates,
charts and documentation — is committed.

## Method in one paragraph

The raw CSV is never scanned directly; it is converted once to Parquet and then queried on all
10M rows with DuckDB, so "full-data" really means full-data and no number in the READMEs comes
from a sample. Sampling (random, never a stride) is used only to draw chart shapes. Every claim
is paired with a **control**: anomalous rows are compared with clean rows (`ANOMALY_TYPE IS
NULL`) holding the corridor, bank count and country fixed, and the clean baseline is reported
next to the effect. Negative results are documented too. See `rules.md` for the full contract.
