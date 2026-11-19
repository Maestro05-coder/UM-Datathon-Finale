# Swift UMDAC Datathon 2026 — submitted pack

This folder is the submitted layer of the repository: the 10-page dashboard, the 17-slide
deck, the dataset anatomy report, and the pipeline that builds all three.

The eight feature-group deep dives live one level up in `../analysis/groups/`. They are the
first derivation of the same rules. This folder is the second one: same dataset, same
definitions for clean rows and sender country, independent implementation, built to produce
the pack that gets marked.

```
../swift_umdac_datathon_2026_fictitious_payment_data.csv    the supplied file, at the repo root
submission/
  README.md                  this file
  analysis/                  pipeline: CSV -> parquet -> panel tables -> docs
  dashboard/                 build.py, style.py, data/ (panel tables), png/ (previews)
  deck/                      build_deck.py, deck PDF and PPTX
  docs/                      Swift_Dashboard_Pack.pdf, dataset anatomy PDF and DOCX
```

## Read these first

| Document | What it is | Format |
| :--- | :--- | :--- |
| `docs/Swift_Dashboard_Pack.pdf` | The submission itself: ten 16:9 pages, one per reconstructed rule, each with a baseline and a chart. | PDF, 10 pp |
| `docs/Swift_Dataset_Anatomy_and_Generation_Rules.pdf` | Field-by-field anatomy: what every column is and how it is generated. | PDF, 6 pp |
| `../analysis/groups/<group>/README.md` | Deep dive per group: rules, the dead ends and the numbers that killed them, proof rows from the file. | Markdown |
| `deck/UM_Datathon_2026_Swift_Deck.pdf` | The 17-slide presentation. | PDF · PPTX |

The earlier ten-panel *Dashboard Specification* is retired. It described the panels before
the rebuild and quotes figures that no longer match, so it is stored with the superseded
exploration code in `analysis/archive.zip`, under `archive/superseded/`.

## Running it

Place the raw CSV at the repository root, then from this folder:

```
pip install -r ../requirements.txt

python analysis/convert_csv.py        # CSV -> analysis/payments.parquet (once, ~8 min)
python analysis/refresh_panels.py     # parquet -> dashboard/data/*.csv
python dashboard/build.py             # CSVs -> dashboard/png/*.png + docs/Swift_Dashboard_Pack.pdf
python deck/build_deck.py             # deck PDF and PPTX
```

`dashboard/build.py 3 7` rebuilds only the pages you name, which is the fast loop while
editing a chart.

### Just want to look at the figures?

`dashboard/data/` and `dashboard/png/` are committed, so the drawing steps work without the
raw file:

```
python dashboard/build.py             # -> dashboard/png/*.png and the pack PDF
python deck/build_deck.py             # -> deck PDF and PPTX
```

### Check the numbers

```
python analysis/verify.py --quick     # recompute the quoted figures, ~10 s
python analysis/verify_docs.py        # document structure and pack page count
```

`verify.py` was written against the ten-panel dashboard that preceded the rebuild. Against
the rebuilt panels it currently passes **41 of 48** quick checks; the seven failures all
assert the pre-rebuild definitions:

| Check | Documented | Now | Why it moved |
| :--- | ---: | ---: | :--- |
| local-currency share | 0.894 | 0.934 | sender country now read from the route's first bank, not `ORDERING_BIC8` |
| lowest local share (AU/CA) | 0.84 | 0.88 | same |
| EUR share of the foreign residual | 0.44 | 0.56 | same |
| USD share of the foreign residual | 0.219 | 0.256 | same |
| median B→B | 22,888 | 22,883 | amount medians now on clean rows only |
| median B→C | 3,119 | 3,118 | same |
| median C→B | 3,229 | 3,236 | same |

Those checks need their expected values updated to the rebuilt definitions. The checks
themselves are correct; only the constants they assert are stale.

## What the pack shows

One page per rule, in the order the deep dives use:

| Page | Group | Chart against a baseline |
| :-: | :--- | :--- |
| 1 | Cover | eight groups indexed, ten million rows, no external data |
| 2 | Method | the four tests applied to every rule, plus the findings that were withdrawn |
| 3 | When payments happen | 113 country curves on their own clocks against the same curves on one global clock |
| 4 | Which currency | 113 sender markets ranked against a 100% home-currency line |
| 5 | How much | the 158-market country ladder against the pooled median |
| 6 | Banks and parties | business against retail tickets in 167 markets, with the no-effect line |
| 7 | The chain | observed chain lengths against one geometric law |
| 8 | Duration | median and p10–p90 band, with conversion payments overlaid |
| 9 | Parties | the sender Lorenz curve against a book where every account carries equal volume |
| 10 | Anomalies | destination rates against the file average |

Every number drawn on a page is written to `dashboard/data/` as a CSV first, and
`dashboard/build.py` reads only those CSVs. No figure queries the parquet directly.

## Definitions

Two definitions were corrected when the panels were rebuilt, and both are the reason several
figures differ from the earlier documents:

- **Sender country** is characters 5–6 of the first bank in `BIC8_PATH`, not
  `ORDERING_BIC8`. The two disagree on 4.98% of rows; the route is the record of what
  happened.
- **Amount, duration and party statistics** use clean rows only (`ANOMALY_TYPE IS NULL`).
  The 7,006 injected rows otherwise leak into every median.

## Known limitations

- `BIC8_PATH` itself is noisy: about 5% of head hops and 5% of tail hops were replaced by a
  random different bank, so path-derived features describe the visible path.
- Anomaly typology names are the generator's labels, not a validated fraud taxonomy.
- The 19–23 June volume surge is unexplained and is treated as a scenario event.
- `intermediary_concentration.csv` orders tied banks by BIC, so its cumulative column can
  differ by at most 0.002 where counts tie; the headline shares are unchanged.

## What came from where

- The dataset and the organisers' handouts are not redistributed here. All credit for those
  belongs to Universiti Malaya UMDAC and Swift.
- `../analysis/` is the teammate's independent derivation, imported unchanged from
  `Maestro05-coder/UM-Datathon-Finale` at `77eb612`.
- Everything in this folder was produced for this entry from the supplied file alone. No
  third-party data or model is used anywhere in the pipeline.
