# GLOBAL GUARDRAILS (apply to every phase)
Method
- Never scan the CSV directly. Query the parquet caches in analysis/ with DuckDB
  (cache_full/ = light columns + path features; cache_party/ = accounts + text + ANOMALY_TYPE).
- Every number you quote in a README must be EXACT (full-data count, min/max, quantiles).
  Use random samples ONLY to draw chart shapes — never a ::40-style stride.
- Clean rows = `ANOMALY_TYPE IS NULL`. Sender country = chars 5–6 of the FIRST bank in
  BIC8_PATH (not ORDERING_BIC8, which is ~5% wrong).
- Every claim needs a CONTROL: compare anomalous vs clean while holding everything else
  fixed (same corridor, same bank count, same country). Report the clean baseline next to
  the anomalous number. If the effect vanishes under control, say so.
- Prefer a well-grounded partial or NEGATIVE result over a lucky guess. Negative results
  are deliverables, not failures.
- Model CAUSATION, not correlation. State what is sampled first and what depends on what.

# CHART DESIGN CONTRACT (this is the fix for "graphs got too complex/jargony")
Apply to EVERY chart, in every phase, before saving:
1. ONE idea per chart. If you need the word "and" in the title, split it into two charts.
2. The title is the FINDING in plain English, not the variable names.
   - Bad:  "Median log10(USD_AMOUNT) by coarse BIC8 country bucket"
   - Good: "Germany pays 40x more than Guinea-Bissau, on average"
3. No unexplained jargon or codes in titles, axes, or legends. Spell out acronyms the first
   time (e.g. "intermediary banks ('...' in the path)"), never show raw internal codes
   (BIC8, QFLAG, TYPE codes) without a plain-language gloss.
4. The unit is written on every axis ("count of payments", "median payment (USD)", "hours").
5. Print the actual value on or beside each mark — the reader should not estimate from a bar.
6. Never use a log-scale BAR (bar length would lie about the ratio). Use dots on a log axis,
   or a "times the baseline" linear bar with the baseline marked.
7. Legend goes BELOW the plot area, never on top of the data. Use the shared style:
   `import _style as S; S.apply()`. Save with `savefig(fig, "name.png", group="<group>")`.
8. Cap it: no dual y-axes, no more than ~4 series, no stacked bars over 4 categories.
   A chart a non-analyst cannot read in 5 seconds is a FAILED chart.
9. If a control is the point (e.g. effect shrinks 3.27x -> 1.14x), make THAT the chart:
   show the raw number and the controlled number side by side.