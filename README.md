# UM Datathon 2026 — Swift case study

Two independent reconstructions of the same hidden generator, kept in one repository so
every headline number can be read twice.

`main` holds the group-level analysis on its own. This branch, `adam/submission-pack`,
adds the submitted pack on top of it and leaves `main` untouched.

| layer | where | what it is |
| :--- | :--- | :--- |
| Group deep dives | `analysis/` and `analysis/groups/<group>/` | One DuckDB script per feature group, cached aggregates, and a README per group with the rules, the dead ends and proof rows. Includes `RULES_g1_g4.md`. |
| Submitted pack | `submission/` | The 10-page dashboard, the 17-slide deck, the dataset anatomy report, and the second pipeline that builds them. |

Both layers start from the single supplied file and nothing else:

```
swift_umdac_datathon_2026_fictitious_payment_data.csv    10,000,000 rows, ~4.95 GB
```

The file is not in this repository. Place it at the repository root and both layers can
be rebuilt from it.

## The eight rules

| # | rule | headline number | deep dive | pack page |
| :-: | :--- | :--- | :--- | :-: |
| 1 | Payments follow one working-day template stamped on local clocks, not a global clock | 17 clocks, pairwise agreement 0.19 → 0.98 | `analysis/groups/g1_time/` | 3 |
| 2 | The currency is decided on the sender side; no FX-rate table exists | 93.4% bill at home, 73–98% across 113 markets | `analysis/groups/g2_currency/` | 4 |
| 3 | Amounts are one lognormal shape around a free per-country centre | 650× from the poorest to the richest market | `analysis/groups/g3_amount/` | 5 |
| 4 | A bank id is a fixed eight-slot code, and business payers add a constant premium | 0 exceptions in 25.8M appearances; 7.3× | `analysis/groups/g4_banks/` | 6 |
| 5 | Route length is geometric, so bank count is the route type | 63% use two banks; 0.368 per extra bank | `analysis/groups/g5_routing/` | 7 |
| 6 | Duration is the sum of per-bank step delays; conversions and hidden banks cost nothing | 39 s at two banks to 1,704 s at ten | `analysis/groups/g6_fx_duration/` | 8 |
| 7 | A small pool of senders carries most of the volume, and the payer's address is real | 78.6% from 28,878 of 390,725 senders | `analysis/groups/g7_parties/` | 9 |
| 8 | The six anomaly labels are distinct mechanisms, not a severity scale | 7,006 rows; 33 to 7,914 per 100,000 by destination | `analysis/groups/g8_anomalies/` | 10 |

## Where the two derivations differ, and why

The differences are denominators and statistics, not disagreements about the mechanism.
Each is stated with its definition so neither number has to be taken on trust.

| Item | Pack (`submission/`) | Deep dives (`analysis/`) | Reconciliation |
| :--- | :--- | :--- | :--- |
| Clock alignment | 17 clocks, pairwise agreement 0.19 → 0.98 | 18 clocks, similarity to a fitted template −0.02 → +0.99 | Same shift rule; the template figure is measured against a curve fitted to the same data, the pairwise figure needs no reference. The pack quotes the pairwise number. |
| Country codes | 228 | 229 | 228 codes ever appear as a **sender** (`ER` never sends); 229 appear anywhere in a route. |
| Banks | 8,386 endpoints | 8,727 | 8,727 is every bank in every visible route; 8,386 is endpoints only. Both reproduce exactly. |
| Corridors | not quoted | 24,017 | Reproduced exactly on either pipeline. |
| Storm rows | not quoted | 2.83% of rows | A real injected-amount mechanism found in the deep dives; not yet a pack panel. |

## Layout

```
analysis/                    group deep dives: g0..g8 scripts, groups/, agg/, _archive/
  _common.py                 paths, DuckDB helpers, reservoir sampler
  _style.py                  the shared chart contract
  build_cache.py             raw CSV -> cache_full/ (light columns + path features)
  build_cache_party.py       raw CSV -> cache_party/ (accounts and text)
  groups/<group>/README.md   rules, dead ends, proof rows, charts
submission/                  the submitted pack
  analysis/                  second pipeline: convert, refresh panels, verify, docs
  dashboard/                 build.py + style.py + data/ + png/
  deck/                      build_deck.py + PDF + PPTX
  docs/                      Swift_Dashboard_Pack.pdf, dataset anatomy PDF/DOCX
README.md                    this file
rules.md                     method guardrails and chart contract
RULES_g1_g4.md               long-form write-up of groups 1-4
AGENTS.md                    working conventions for this repository
```

## Running each layer

**Deep dives** (from the repository root):

```
pip install -r requirements.txt
python analysis/build_cache.py            # caching step, ~2.3 GB, once
python analysis/build_cache_party.py
cd analysis && python g1_time.py          # or g2_currency.py ... g8_anomalies.py
```

**Submitted pack** (from `submission/`):

```
cd submission
python analysis/convert_csv.py            # raw CSV -> analysis/payments.parquet, once
python analysis/refresh_panels.py         # parquet -> dashboard/data/*.csv
python dashboard/build.py                 # CSVs -> dashboard/png/*.png + docs/Swift_Dashboard_Pack.pdf
python deck/build_deck.py                 # deck PDF + PPTX
python analysis/verify.py --quick         # recompute the quoted numbers
```

`verify.py --quick` passes 48 of 48 checks. Seven of its constants asserted pre-rebuild
definitions and were updated to the rebuilt ones; `submission/README.md` lists the seven
and why they moved.

The pack only ever reads the CSVs in `submission/dashboard/data/`, so every figure on
every page can be checked from the committed tables without touching the parquet.

## Data and caches

Everything large is ignored: the raw CSV, `analysis/cache_full/`, `analysis/cache_party/`,
and `submission/analysis/payments.parquet`. The panel CSVs under
`submission/dashboard/data/` are tracked on purpose: they are the audit trail behind the
pack, which is why the root `.gitignore` carries an explicit exception for them.

## Provenance

- `analysis/`, `rules.md`, `RULES_g1_g4.md`, `AGENTS.md`: `Maestro05-coder/UM-Datathon-Finale`
  at `77eb612`, imported unchanged.
- `submission/`: `adamzikry870-dev/swift-umdatathon` at `0c478db`, imported as one commit.
- The earlier ten-panel dashboard specification was retired when the pack was rebuilt and
  now lives inside `submission/analysis/archive.zip` under `archive/superseded/`.
