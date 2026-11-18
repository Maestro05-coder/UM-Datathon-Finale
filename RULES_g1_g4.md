# g1–g4: the rules, derived and explained

A single, plain-language summary of the first four feature groups of the UmDatathon 2026
payments file. Each rule lists **what it says**, **how we derived it**, **what it means**,
and a short **realism** note.

> Scope: groups g1 (time), g2 (currency), g3 (amount), g4 (banks). g5–g8 are in their
> own `analysis/groups/*/README.md` files and are not covered here.
>
> Source of every number: the full 10,000,000-row CSV, read through the parquet caches
> with DuckDB. All counts are exact; samples are used only for chart shapes. The file
> covers 90 days, 2023-04-30 to 2023-07-30.
>
> On "economically realistic": the datathon handbook itself is not stored in this repo,
> so the realism notes below are our own check against how correspondent banking and
> payment messages actually behave. If the handbook uses a formal checklist, map it
> against the scorecard at the end.

---

## How the rules were derived (the method, once)

Every rule below comes from the same loop:

1. **One question per group**, designed around a suspected mechanism — not "do anomaly
   rows look different" fishing.
2. **Group-bys on all 10M rows**, never on a sample. A full group-by takes seconds.
3. **A control for every claim.** Compare the anomalous group to a clean baseline while
   holding everything else fixed (same country, same bank count, same corridor). If the
   effect disappears under the control, it was composition, not a rule.
4. **Two clean definitions used throughout:**
   - *sender country* = characters 5–6 of the first bank in `BIC8_PATH` (not the
     `ORDERING_BIC8` column, which is ~5% wrong — g5 Rule 5);
   - *clean row* = `ANOMALY_TYPE IS NULL` (not `= ''`).
5. **Split-half validation** where possible: build the effect on one deterministic half
   of the rows, confirm it on the other.

Three habits worth naming because they decided several rules:

- *Correlation before and after alignment* (g1 Rule 1) — the same data, two framings.
- *Hold the country fixed* (g2 Rule 4, g3 Rule 2) — the only way to tell a currency
  effect from a country-wealth effect.
- *Split by corridor* (g3 Rule 2) — turns an apparent +0.18 dex effect into zero.

---

## g1 — Time

Group question: *when do payments happen?* Full detail: `analysis/groups/g1_time/README.md`.

### 1.1 Every country pays on its own local clock

**Rule.** Each country's payments-by-hour curve is the same shape, slid along the clock
by a whole number of hours.

**Derived from.** For each sender country, count payments by UTC hour (a 24-number
profile). Take the busiest country (US) as the reference. Try all 24 whole-hour rotations
of each country's profile and keep the rotation with the highest correlation to the
reference. Across the 113 countries with at least 5,000 rows:

| framing | mean correlation to the reference day |
| :--- | ---: |
| all countries on the shared UTC clock | **−0.02** (noise) |
| each country shifted by its own offset | **+0.99** (near-perfect) |

**What it means.** The generator gave each country a local working-day clock. Any
comparison of countries on raw UTC time is smeared by time zones and will understate
every real pattern.

**Realism.** Strong. Payment initiation follows local business hours, and time zones
genuinely differ by whole hours. Two caveats: the model has **no half-hour zones**
(India would really be +5:30), and offsets are recovered *relative to the US*, so we
cannot name absolute UTC offsets.

### 1.2 There are only 18 distinct clock offsets

**Rule.** Relative to the reference country, 18 whole-hour offsets appear. The most
common are +6h (28 countries), +7h (15), +1h (10), +8h (9), +5h (9), 0h (8).

**Derived from.** Histogram of the recovered rotations from Rule 1.1.

**What it means.** The generator drew a whole-hour offset per country from a small
dictionary of 18 values; it did not use a real timezone table.

**Realism.** Plausible as a simplification, implausible as geography. Earth has ~38
timezones including half-hour and 45-minute ones; 18 whole-hour values cover most of the
day but skip real zones.

### 1.3 One shared daily shape — with two busy windows

**Rule.** After alignment, every country follows the same day. The busiest hour is
**7.5×** busier than the quietest; the seven quietest hours hold only **8.8%** of
payments; the three hours around the peak hold **21.4%**; 10 of 24 hours sit below half
the peak.

**Derived from.** Average the aligned country profiles into one 24-hour shape, then
measure the peak, the trough and the tail shares.

**What it means.** There is one template day. Note that it has **two busy windows**, not
one hump — Germany's own day peaks at 06:00 and again at 15:00–17:00, and the UK, Japan,
Brazil and the US show the same pattern. "Working day" is shorthand for that two-window
shape, likely a start-of-day and an end-of-day batch.

**Realism.** Plausible. Real payment traffic peaks around submission and cut-off times
with a lunch-time dip; a 06:00 local peak is early for corporate cut-off but consistent
with overnight batch submission. A single clean noontime hump would have been the less
realistic result.

### 1.4 Weekends are quiet

**Rule.** Working days each carry 17.0–18.3% of payments; Saturday 4.35%, Sunday 6.84%.
The weekend holds **11.18%** of rows, versus 28.6% if every day were equal.

**Derived from.** Weekday share of all 10M rows, using the file's own UTC days.

**What it means.** The generator suppresses weekend activity but does not switch it off.

**Realism.** The direction is strong; the detail is odd: **Sunday (6.8%) is busier than
Saturday (4.4%)**, whereas real business/retail traffic usually falls further on Sunday.
There is also no holiday calendar in the file, so public holidays behave like ordinary
days — a known simplification.

---

## g2 — Currency

Group question: *which currency does a payment use, is there an FX table, and does the
currency label do anything?* Full detail: `analysis/groups/g2_currency/README.md`.

### 2.1 The currency is a sender-side label

**Rule.** `CURRENCY_CODE` tracks the sender side of the route, not the beneficiary side.

**Derived from.** Compute each bank's modal currency across all 10M rows, then ask what
share of rows match it:

| reference | match |
| :--- | ---: |
| first bank in the route (sender side) | **93.42%** |
| last bank in the route (beneficiary side) | **19.09%** |
| the `ORDERING_BIC8` column | 89.45% |

**What it means.** The currency is chosen with the ordering party. 19% on the beneficiary
side is about what random currency mixing would give, so the beneficiary side carries no
signal.

**Realism.** Direction is right — the ordering customer states the settlement currency —
but 93% sender-side is high for cross-border payments, which in reality often settle in a
vehicle currency (USD/EUR) or the exporter's currency rather than the payer's.

### 2.2 Every country has a home currency, used ~92% of the time

**Rule.** Each sender country has a modal ("home") currency. Rows-weighted home share
across 182 countries with ≥1,000 rows: median **91.9%**, max 98.3% (Martinique), min
**72.9%** (Russia, which pays EUR 23.2% of the time).

**Derived from.** Group by sender country and currency; the modal currency is the home
currency. Control: payments *within* one country use the home currency **96.78%** of the
time versus 93.15% across countries — the gap is the foreign-currency effect of Rule 2.3,
not a different rule.

**What it means.** A per-country currency table is baked into the generator; deviations
from it are the deliberate "foreign payment" cases.

**Realism.** Strong for domestic payments. The recovered table also behaves like a real
currency map — **31** of the 228 countries share EUR as home, which is what you would
expect from a currency union.

### 2.3 Foreign payments lean to the beneficiary's currency

**Rule.** When the payment is not in the sender's home currency (657,004 rows in
countries with ≥1,000 rows), it is mostly EUR (56.0%) or USD (25.6%), then GBP 6.1%,
CHF 3.4%, CNY 2.3%. And it tracks the beneficiary: **57.7%** of foreign rows use the
beneficiary country's home currency, far above chance for every currency:

| foreign currency | rows | matches beneficiary home | chance baseline |
| :--- | ---: | ---: | ---: |
| EUR | 368,002 | 62.1% | 41.8% |
| USD | 168,219 | 54.1% | 21.8% |
| GBP | 40,149 | 62.2% | 8.5% |
| CHF | 22,532 | 58.6% | 6.7% |
| CNY | 15,065 | 51.9% | 3.1% |
| JPY | 4,770 | 47.5% | 1.2% |

**Derived from.** Split rows into home-currency and foreign-currency. For each foreign
currency, compare the actual match rate to the baseline "share of foreign rows whose
beneficiary country has this home currency". The baseline is the control: any currency
that merely happens to be common would score high on actual *and* baseline.

**What it means.** The generator weights the foreign-currency choice toward the
beneficiary's currency, with EUR/USD as the fallback habit. It is probabilistic, not
deterministic: 42% of foreign rows still do not match the beneficiary.

**Realism.** Strong. This is the invoice-currency effect — exporters bill in their own
currency — and the baseline control is exactly how you would test it.

### 2.4 USD amounts are round; every other currency is not

**Rule.** Among clean amounts of at least 1 USD, USD rows are whole numbers **38.65%** of
the time (multiples of 10/100/1,000: 19.1%/15.6%/11.4%). Non-USD rows are at
**0.99% / 0.10% / 0.01% / 0.00%** — chance.

**Derived from.** Two controls. First, compare USD and non-USD globally. Second, hold the
sender country fixed and switch only the currency:

| country | home currency | in home currency | in USD |
| :--- | :--- | ---: | ---: |
| Germany | EUR | 0.94% | **37.5%** |
| United Kingdom | GBP | 0.97% | **39.2%** |
| Japan | JPY | 0.92% | **39.2%** |
| United States | USD | 38.7% | — (in EUR: 0.90%) |

**What it means.** The rounding mode is triggered by the *label* "USD", not by the
country, the amount size or the time of year. The whole-number share is stable at
38.6–38.8% in every 15-day bucket, so it is a permanent mode, not an event.

**Realism.** **Weak.** Round-number clustering is real, but it is a human/settlement
behaviour that appears in **every** currency (salaries, invoices, cash). Restricting it to
USD is a synthetic artefact. Real files also show currency-specific minor units (JPY has
no decimals, KWD has three), while here every amount has exactly two decimals.

### 2.5 Dead end: there is no FX-rate table

**Rule.** `CURRENCY_CODE` does not convert `USD_AMOUNT`. The amount is already in USD
terms.

**Derived from.** Compute the median `log10(USD_AMOUNT)` per (sender country, currency)
cell. Within each country, compare its foreign-currency cells to its home-currency cell.
Across 63 cells covering 457,972 rows, the differences are min −0.080, **median −0.001**,
max +0.133 dex (median absolute difference **0.017**). A real FX table would force
differences of about ±0.03 dex (EUR/USD) up to ±1.9 dex (USD/INR).

The naive version of this analysis *does* look like exchange rates — "median amount per
currency ⇒ implied rate" produces numbers like USD/INR ≈ 82. But those gaps are the
sender-country wealth ladder of g3, not conversion.

**What it means.** The amount is drawn in USD; the currency label rides along and only
feeds back into amounts through the USD rounding rule (2.4). There is no second FX layer.

**Realism.** Weak if `CURRENCY_CODE` is meant to be a settlement currency, because then
amount and currency must be consistent. Strong if `USD_AMOUNT` is a reporting value
converted once for monitoring — which is the only reading the data supports.

---

## g3 — Amounts

Group question: *how are amounts generated, what moves them, and why do some repeat?*
Full detail: `analysis/groups/g3_amount/README.md`.

### 3.1 One lognormal shape; the country sets the centre

**Rule.** Clean amounts follow a log-normal distribution with the same spread everywhere
and a different median per country.

**Derived from.** Global clean statistics: median **$3,678**, p75 $19,921, p90 $94,879,
p99 $1.27M, min $0.01, max $1.395B. In log10 space: mean 3.543, sigma 1.122, skewness
**−0.085**, kurtosis **+0.048** — essentially a perfect normal. Per sender country
(158 countries with ≥2,000 clean rows), sigma stays in **0.97–1.19** (median 1.050) while
the centre runs from mu 1.678 (**Guinea-Bissau, $48**) to 4.494 (**Monaco, $31,219**).

The two-level check: E[sigma_country²] + var(mu_country) = 1.1168 + 0.1498 = **1.2665**,
against the global sigma² of 1.2587. One shape plus country offsets reproduces the whole
distribution to within 0.6%.

**What it means.** Two numbers per country (its median and the shared sigma) describe the
entire amount distribution. There is no separate "rich country" distribution with a
different shape.

**Realism.** Direction strong, magnitude weak. Payment sizes are indeed right-skewed and
roughly lognormal, and richer countries pay more. But a **650×** spread in median payment
($48 → $31,219) is far beyond the real spread in GDP per capita (~100×), and a single
distribution spanning $0.01 to $1.4B with sigma 1.12 has a tail that is too thin for a
real payment system. Treat the ladder as a ranking, not as calibrated wealth.

### 3.2 Nothing about the payment itself moves the amount

**Rule.** Route length, transaction type, hidden banks and weekday make no difference.
The amount is set independently of how the payment travels.

**Derived from.** Medians of `log10(USD_AMOUNT)` across splits:

| split | medians (log10 USD) |
| :--- | :--- |
| visible bank count 2 / 3 / 4 / 5 / 6 | 3.563 / 3.564 / 3.565 / 3.566 / 3.566 |
| Direct / Indirect / Covered | 3.563 / 3.557 / 3.628 |
| hidden banks no / yes | 3.564 / 3.564 |
| weekday / weekend | 3.564 / 3.563 |

The one apparent effect — payments with **0 currency conversions** have median 3.72 versus
3.54 for 1 conversion (+0.18 dex) — is **corridor composition**. Split by corridor and the
gap disappears: same-country 0-conv 3.746 versus 2-conv 3.738 (no difference), while
cross-country 0-conv 3.704 versus 1-conv 3.540 just reflects that same-currency neighbours
(EUR-zone, US) are richer.

**What it means.** The amount belongs to the underlying trade, not to the route. It also
demonstrates the group's method: an apparent effect that survives no control is not a
rule.

**Realism.** Strong. The number of correspondent banks carrying a payment has no reason to
change its size. This is one of the most economically sensible results in the file.

### 3.3 The USD mode is a "nice-number pool", not just rounding

**Rule.** USD whole-dollar amounts are unusually round even among integers: **46.4%** have
≤2 significant figures and 59.2% have ≤3, and **10.7%** are exactly {1, 2, 5}×10^k
(non-USD: 0.02%). Leading digits of USD integers spike on 1 (34.98% vs Benford's 30.10%)
and 5 (14.12% vs 7.92%).

**Derived from.** Restrict to USD whole-dollar amounts, normalise each to its mantissa, and
test membership of the {1,2,5}×10^k set and of the significant-figure thresholds.

**What it means.** Part of the USD mode is a rounding step, part is a pool of preferred
values (1,000; 2,500; 50,000 …). That is why the leading-digit profile is not smooth.

**Realism.** Same verdict as Rule 2.4: realistic behaviour, unrealistically tied to one
currency.

### 3.4 Storm rows: one amount, many unrelated payments, one day

**Rule.** **2.83%** of all rows (282,771) belong to a "storm": hundreds of otherwise
ordinary payments share one exact amount on one day. By currency: **EUR 6.76%** of its
rows, CHF 3.61%, GBP 3.35%, SGD 1.42%, CNY 0.94%, **USD 0.00%**.

**Derived from.** Build (currency, amount, day) cells and keep those with ≥100 rows and
≥50% of that amount's total rows: 1,145 cells. Then take one family apart — 9 June 2023,
EUR, base 1,159.42: the base appears 727 times and its integer multiples 1–160 account for
**3,135 rows** in total that day (×10 598 rows, ×5 433, ×100 244, ×50 188 …). Storm rows
are ordinary in every other respect: the 5,667.00 example spans 42 sender countries, storm
type mix matches the currency, beneficiaries are near-unique, and anomaly labels appear at
the normal rate.

**What it means.** This is a per-day, per-currency **injection**: a base amount is stamped
into the file as integer multiples. It also explains exotic repeats such as 5,667.00
(= 1,133.40 × 5) and 115,942.00 (= 1,159.42 × 100). The daily base drifts slowly (EUR
~1,100–1,220), so it is a moving template, not a fixed table.

**Realism.** Mixed. Real files do contain many identical amounts on one day — payroll,
dividends, benefit runs — but they come from **one sender** for **one purpose**. Here the
parties are random across 42 countries, which has no economic story. Excluding USD from
storms is also arbitrary. Treat this as a data-injection artefact that *looks* like a
batch run.

### 3.5 Amounts follow Benford's law

**Rule.** Leading digits of all clean amounts are close to Benford: 1 → 31.44% (Benford
30.10%), 2 → 16.84% (17.61%), 5 → 8.84% (7.92%), 9 → 4.38% (4.58%).

**Derived from.** Count the first digit of every clean amount and compare with
log10(1 + 1/d).

**What it means.** Benford is not a separate generator rule: any log-normal-ish mixture of
scales produces it automatically. The remaining excess on 1, 2 and 5 is exactly the USD
pool of Rule 3.3.

**Realism.** Strong — and a useful consistency check. Deviations from Benford here have a
known cause rather than being unexplained.

---

## g4 — Banks and countries

Group question: *what is the bank universe, what roles do banks play, and do banks add
anything of their own?* Full detail: `analysis/groups/g4_banks/README.md`.

### 4.1 8,727 banks across 229 country codes; pool size tracks traffic

**Rule.** Bigger countries have more banks, up to a country-specific cap.

**Derived from.** Split every `BIC8_PATH` on `;`, drop the `...` placeholders, and count
distinct banks and appearances per country code (chars 5–6): **25,815,715** appearances,
8,727 banks, 229 codes. Banks per country: median 12, max **1,016** (US), min 1.
Correlation between appearances and banks: **0.94** on raw counts (0.83 on logs).

The useful outliers are small countries that host big intermediaries: Isle of Man handles
545,030 appearances with **12** banks; Finland 465,937 with **33**.

**What it means.** Each country has a bank pool scaled to its traffic. A country code can
carry huge traffic with a small pool when the big correspondent banks are registered there.

**Realism.** Strong. SWIFT has on the order of 11,000 member institutions, so 8,727 is the
right order of magnitude, and correspondent concentration in small jurisdictions is real.

### 4.2 No bank is endpoint-only; 45 are pure intermediaries

**Rule.** Every one of the 8,727 banks appears at least once as a sender or beneficiary
bank, and 45 appear **only** as a middle hop. The busiest middlemen:

| bank | middle hops | endpoint appearances |
| :--- | ---: | ---: |
| 0309CHZ0 | 492,743 | 299,130 |
| 0004IMD0 | 460,652 | 318,008 |
| 0085BEB0 | 329,656 | 209,470 |
| 0026FIH0 | 324,052 | 220,520 |
| 0380CNB0 | 283,834 | 188,481 |

Overall, 56.3% of bank appearances are in the middle of a route.

**Derived from.** For every bank, count appearances in positions 2…n−1 (middle) versus
position 1 or n (endpoint), on routes with no hidden end (`gap_head = FALSE AND
gap_tail = FALSE`).

**What it means.** Every bank can send and receive; a small set exists only to route. That
is a deliberate role structure, not an artefact of route length.

**Realism.** Strong. Correspondents and clearing institutions really do act as pure
intermediaries, and the top-hub concentration matches how correspondent banking works.

### 4.3 Market concentration varies enormously by country

**Rule.** The largest sender bank's share of a country's first-position payments ranges
from **4.4%** to **100%**, median **52.2%**.

**Derived from.** Per country, the top bank's share of first-position rows, with the number
of banks in the pool recorded alongside. US: top bank 0033US30 = 4.4% of 979 banks. UK:
8.2% of 584. One-bank countries (GP, GU, WF, NR, PW …) sit at 100%.

**What it means.** The generator models both competitive markets and single-bank markets.

**Realism.** Strong. Real banking markets vary from hundreds of institutions to a single
provider.

### 4.4 24,017 country corridors; flows are not reciprocal

**Rule.** There are 24,017 distinct sender→beneficiary country pairs, and A→B is not
balanced against B→A.

**Derived from.** Count rows per (sender country, beneficiary country) pair. Top flows:
US→US 395,503; CH→US 134,797; GB→US 130,410. For each unordered pair, compute
|n_AB − n_BA| / (n_AB + n_BA). Among the 322 pairs with ≥5,000 rows combined, the median
asymmetry is **0.114** and the 90th percentile 0.326.

**What it means.** Flows follow relationships, not a symmetric matrix. A generator that
balanced both directions would pile up at 0.

**Realism.** Strong. Bilateral trade and correspondent relationships are not balanced.

### 4.5 The BIC8 code has a rigid, generated structure

**Rule.** A bank code is always: 4 numeric characters + 2-character country + 1 per-country
letter + the digit `0`.

**Derived from.** Check every bank appearance: characters 1–4 are numeric in **all**
25.8M appearances (0 exceptions); character 8 is always `0` (1 distinct value); character
7 takes exactly **25 distinct values** and is constant within a country (US = `3`,
CH = `Z`, DE = `F`, FR = `P`, CN = `B`, JP = `J`). Character 7 is not a bank identifier —
`2` alone is shared by 30 countries (GB, IT, NL …).

**What it means.** The code is an internal ID scheme that encodes the country, which is why
chars 5–6 can serve as the country key everywhere in the project.

**Realism.** Weak as a SWIFT BIC. Real BICs are 4 **letters** + 2-letter country +
2-character location, so a numeric bank code is synthetic. The structure is at least
internally consistent and self-describing.

### 4.6 Party types are only B or C, and both ends shift the amount

**Rule.** `ORDERING_TYPE` / `BENEFICIARY_TYPE` are only ever `B` (business) or `C`
(person) — **0** `A`/`D` rows in 10M. Each business endpoint multiplies the median amount
by roughly 7.

**Derived from.** Census of the two type columns, then median amount per combination:

| pair | rows | median amount |
| :--- | ---: | ---: |
| B→B | 2,269,885 | $22,900 |
| B→C | 5,600,965 | $3,118 |
| C→B | 609,762 | $3,236 |
| C→C | 1,512,382 | $464 |

The B-vs-C offset is stable across countries (US +0.907 dex, DE +0.862, IN +0.875,
MC +0.865), and the country wealth ladder survives *within* each type (3.19 dex across 197
countries for B, 2.89 dex across 168 for C).

**What it means.** Country wealth and party type are two independent additive factors.
g3's ladder mixes the two types; this rule splits them.

**Realism.** Strong direction and plausible magnitude — business payments are much larger
than person-to-person ones. Carrying a B/C flag in the message is a simplification: real
SWIFT traffic infers party type from message type and fields rather than labelling it.

### 4.7 Banks have their own stable amount tilts

**Rule.** Beyond the country and the party type, a bank's typical payment size is a real,
reproducible property — and part of it is clientele.

**Derived from.** 2,221 (bank, country) cells with ≥500 rows. The bank's median
`log10(USD_AMOUNT)` deviates from its country's median with sigma **0.274** dex. That
deviation correlates **−0.584** with the bank's share of retail (C) senders. Split-half
validation: for the 2,200 banks with ≥250 rows in each disjoint half, the deviation
correlates **0.931** across halves. After predicting the deviation from the global type
mix, a residual of ~0.22 dex remains — a genuine bank property.

**What it means.** A bank is not just its country. Retail-heavy banks pay less; the rest is
a stable bank-level amount tilt.

**Realism.** Strong. Bank clientele and product mix really do shape payment sizes, and the
split-half test is the right way to show the tilts are not noise.

### 4.8 Dead ends in g4

- **Character 7 as a unique bank identifier** — no: it is per-country and collides.
- **Character 8** — always `0`; carries no information.
- **Corridor reciprocity** — no balancing (Rule 4.4).
- **Endpoint-only banks** — none exist; every bank can also route.

---

## Realism scorecard

Our read of how each rule stands up to how payments actually work. "Strong" = you could
describe this to a payments expert and they would nod; "Weak" = the generator's behaviour
is internally consistent but not something a real system would do.

| rule | verdict | why |
| :--- | :---: | :--- |
| 1.1 local clocks | strong | local business hours, whole-hour time zones |
| 1.2 only 18 offsets | plausible | timezone table simplified; no half-hour zones |
| 1.3 shared day, two windows | plausible | cut-off peaks are real; 06:00 peak is early |
| 1.4 weekend dip | plausible | direction right; Sunday busier than Saturday is odd |
| 2.1 sender-side currency | plausible | ordering customer decides; 93% is high for cross-border |
| 2.2 home currency per country | strong | domestic payments settle in home currency |
| 2.3 beneficiary pull | strong | invoice-currency effect, tested against a baseline |
| 2.4 USD-only round numbers | **weak** | round numbers are common in every currency |
| 2.5 no FX table | **weak** as a settlement label; strong as a reporting value | amount and currency are otherwise inconsistent |
| 3.1 lognormal + country ladder | strong direction / **weak magnitude** | 650× median spread is far beyond real GDP spread |
| 3.2 amount ignores the route | strong | route is a consequence, not a size driver |
| 3.3 {1,2,5} nice-number pool | **weak** | same reason as 2.4: tied to one currency |
| 3.4 storm rows | **weak** as economics, clear as a data injection | identical amounts, random unrelated parties, USD excluded |
| 3.5 Benford | strong | follows from the lognormal mixture; deviations explained |
| 4.1 bank universe and pools | strong | ~8.7k institutions is SWIFT-scale; hubs in small jurisdictions |
| 4.2 no endpoint-only banks, 45 pure hubs | strong | correspondents act as pure intermediaries |
| 4.3 concentration 4.4–100% | strong | real markets range from fragmented to single-bank |
| 4.4 corridors not reciprocal | strong | bilateral flows are not balanced |
| 4.5 BIC8 structure | **weak** as SWIFT, consistent as IDs | real BIC bank codes are letters, not digits |
| 4.6 B/C types, +0.87 dex each | strong | business payments larger; type flag is a simplification |
| 4.7 stable bank tilts | strong | client mix shapes amounts; split-half confirms |

**Bottom line.** g1, g2.1–2.3, g3.1–3.2, g3.5 and g4.1–4.4, 4.6–4.7 describe behaviour a
real payments system could show. The synthetic fingerprints are concentrated in four
places:

1. **USD-exclusive round numbers** (2.4, 3.3).
2. **A currency label that never converts the amount** (2.5).
3. **A 650× country amount ladder with a $0.01–$1.4B range** (3.1).
4. **Storm amounts with random parties** (3.4), and **numeric bank codes** (4.5).

If the handbook's "economically realistic" criterion is a gate, those are the rules to
present as generator simplifications rather than as real-world behaviour.

---

## Quick reference

| group | one-line rule |
| :--- | :--- |
| g1 | every country pays on its own local working-day clock |
| g2 | the currency is a sender-side label; foreign payments lean to the beneficiary; only USD rounds |
| g3 | one lognormal shape shifted by country wealth; route doesn't matter; 2.83% are single-day injected storms |
| g4 | 8,727 banks, all can send/receive, 45 pure hubs; country and party type independently scale the amount |

Full detail, charts and proof rows: `analysis/groups/g1_time/`, `g2_currency/`,
`g3_amount/`, `g4_banks/`.
