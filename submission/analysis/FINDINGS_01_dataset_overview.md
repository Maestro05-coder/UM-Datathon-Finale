# Swift UMDAC Datathon 2026 — Dataset Anatomy & Reconstructed Generation Rules
### Working note 01: what the file is, how it is built, and how we know

Confidence tags: **[V]** verified on all 10M rows · **[S]** strong (large-sample, >99% consistent) · **[T]** tentative / still being tested

---

## 1. What the file physically is

| Property | Value |
|---|---|
| Rows | 10,000,000 payment records |
| Columns | 20 |
| Raw size | ~5 GB CSV (col 0 = quoted multi-line DISCLAIMER on the first line) |
| Time span | 2023-04-30 19:22 → 2023-07-31 17:56 UTC (92 days, ~108k payments/day) |
| Distinct timestamps | 5,085,929 second-level values — timestamps are true second-resolution instants, not day buckets |
| Currencies | 155 |
| Ordering banks (BIC8) | 8,392 in the endpoint columns; 8,727 banks appear somewhere in a route |
| Beneficiary banks (BIC8) | 8,266 in the endpoint columns |
| USD_AMOUNT | mean 97,204 · median 3,662 · max 15.66 bn |
| TOTAL_DURATION | mean 771 s · median 56 s · max 21,649 s (6.0 h) |
| Labelled anomalies | 7,006 rows = 0.07% |

One row = **one payment message leg as observed on the Swift network**: who sent it, who received it, which banks it passed through, in which currency, how much, when, how long it took, plus masked party text.

The CSV is *not* sorted by time — it is a random-order export.

---

## 2. The 20 columns, grouped by role

| Group | Columns | Role |
|---|---|---|
| Timing | `EPOCH_SECONDS` | initiation instant (UTC seconds) |
| Money | `CURRENCY_CODE`, `USD_AMOUNT` | currency label + an amount already expressed in a common USD unit |
| Route | `ORDERING_BIC8`, `BENEFICIARY_BIC8`, `BIC8_PATH`, `PARTICIPANT_COUNT`, `TRANSACTION_TYPE_CODE`, `CONTINUITY_QFLAG` | the bank chain and its labels |
| FX | `CURRENCY_CONVERSION_COUNT` | how many times the currency changed along the chain |
| Latency | `TOTAL_DURATION` | end-to-end seconds |
| Party identity | `ORDERING_ACCOUNT`, `BENEFICIARY_ACCOUNT` | IBAN-like fake account numbers |
| Party text | `ORDERING_DETAILS`, `BENEFICIARY_DETAILS`, `ORDERING_TOKENS`, `BENEFICIARY_TOKENS` | Faker-generated name/address block + a tokenised template of it |
| Party class | `ORDERING_TYPE`, `BENEFICIARY_TYPE` | `B` = business, `C` = consumer |
| Label | `ANOMALY_TYPE` | empty for 99.93% of rows |

### BIC8 anatomy **[V]**
`0621US30` = bank code `0621` + ISO country `US` + location `30`. Country is always characters 5–6. There is no real bank directory behind the codes — codes are enumerated `0001…0988` per country, so bank "identity" is synthetic and country is the only meaningful geography.

---

## 3. Structural invariants (the "hard-coded rules")

These are exact, 1:1 relationships — the strongest evidence of deliberate construction.

### 3.1 `PARTICIPANT_COUNT` = number of visible BIC nodes **[V]**
Path segments = participants + number of `...` gaps. `A;B;C` → 3 participants; `A;...;B` → 2 participants + 1 hidden hop.

### 3.2 `TRANSACTION_TYPE_CODE` is a pure function of participant count **[V]**
- `Direct` ⟺ exactly 2 participants (6,323,280 rows, 63.2%)
- `Indirect` or `Covered` ⟺ ≥3 participants

`Indirect` and `Covered` share the *same* geometric length distribution: P(k) ≈ 0.63 · 0.37^(k−2) for Indirect, P(k) ≈ 0.63 · 0.37^(k−3) for Covered. In other words the generator first decides the number of hops with a coin (stop probability ≈ 0.37 per extra hop), then assigns the label.

### 3.3 `CURRENCY_CONVERSION_COUNT` = number of adjacent currency changes along the path **[S]**
Each bank's home currency was learned from zero-conversion payments, then the count was predicted on a held-out half: **99.91% correct on both halves** (~4 million rows each). Max conversion count = participants − 1. Direct payments: 84.3% have exactly 1 conversion.

**This is the single most useful reverse-engineering lever in the dataset**: it means each BIC carries a deterministic "home currency", and the payment currency is *the ordering bank's home currency*. The map is not real-world (e.g. `BQ→USD`), so it must be recovered from data, not from an FX table.

### 3.4 `CONTINUITY_QFLAG` = `N` ⟺ the path contains `...` **[V]**
Exactly 767,204 rows are `N`, and `ell_share` is 1.000 in that group and 0.000 in the `Y` group. Semantics: **`N` = the chain is broken/truncated** (one or more correspondents hidden), `Y` = fully visible chain. Rows with `N` also carry more participants (3.12 vs 2.54) and more conversions (1.80 vs 1.30) on average, i.e. longer routes are more likely to be truncated.

Hiding is about a **5% chance per link**: a route's gap probability fits 1 − (1 − 0.04986)^links (2 links → 9.7%, 3 links → 14.2%), within 0.4 percentage points at every route length.

### 3.5 Accounts and countries **[V]**
- `ORDERING_ACCOUNT` looks like `_FAKE_` + IBAN-ish string, whose country prefix equals the ordering BIC country in **100%** of rows; same for beneficiary.
- 391,132 distinct ordering accounts and 2,590,877 distinct beneficiary accounts **across all 10m rows** (heavy-tailed reuse: 130k used once, top account 75,803 times). On clean rows only the counts are 390,725 and 2,589,757 — the difference is the 7,006 labelled rows.
- Each ordering account is permanently bound to one country **and one `ORDERING_TYPE`** — parties are drawn as reusable entities, not generated per payment.

### 3.6 Party text country **[V]**
- `ORDERING_DETAILS` country token = ordering BIC country whenever present (39% of rows have no country token at all).
- `BENEFICIARY_DETAILS` country is **independent** of the beneficiary BIC country (**0.98%** match, vs 100% on the ordering side). It is a separate draw, skewed to emerging economies (CN 8.8%, BR 5.5%, UA 4.4%, ET 3.5%, IN 2.8%, MX 2.6%).

Interpretation: the ordering party's address is "where the bank is" (domestic customer), while the beneficiary is "someone abroad" — the generator models a remittance/correspondent world, not a corporate treasury world.

`ORDERING_TOKENS` / `BENEFICIARY_TOKENS` are **deterministic pattern summaries** of the details string: vocabulary `chr`, `street:N`, `city:CC:N`, `country_code:CC`, `country_name:CC:en-gb`, `line_break:35/70`, `iban:22`, `business:N`, `company_keyword:N`, `first_name:N`, `last_name:N`, `post_code:CC:N`, `other_words:N`, `numerical:N`, `separator`, `stop_word`, `finance_word`, `truncation`. The `:N` is the token length, so tokens are reversible to the masked text.

---

## 4. The economic layer: how values were generated

### 4.1 Time: one local business clock, shifted by whole hours **[V]**
Every country's hour-of-day histogram is the *same two-humped curve*, circularly shifted by an **integer clock offset**. There are **18 distinct offsets** across 113 sender markets; aligning each country to its own peak raises agreement with the template from −0.02 to **+0.99**. These offsets are a generator lookup, **not real time zones** — India's half-hour zone has no counterpart, and ±1-hour ties are exact.

So the generator drew a **local wall-clock hour** from one global activity curve, then added the country's integer offset. Consequences:
- the timestamp's UTC hour is *not* a behavioural variable — it is (local hour + integer offset);
- any "hour of day" dashboard must be localised or it will show a meaningless 24-hour smear.

Volume also has a calendar layer: weekdays carry 17.05–18.34% each, Saturday 4.35% and Sunday 6.84% → weekend **11.18%**, vs 28.6% if all days were equal, plus strong week-to-week intensity variation; the first and last days are partial.

### 4.2 FX: no rate table exists (an earlier claim withdrawn) **[V]**
An earlier reconstruction read a "daily rate table with a weekend freeze" out of per-currency median amounts (EUR series 1.1007 → 1.2177, with GBP 1.30, CHF 1.26, INR 0.0104 and so on). **That claim is withdrawn.** `USD_AMOUNT` is already a common-unit amount; median amount per currency just re-traces the sender-country wealth ladder, so no conversion factor can be computed and there is nothing to freeze at the weekend.

The decisive control holds the sender country fixed: across 63 country × currency cells (457,972 rows) the median `log10(USD_AMOUNT)` gap between foreign- and home-currency payments is **−0.001 dex** (min −0.080, max +0.133). A real rate table would force gaps of ±0.03–1.9 dex. The only currency that changes the amount is USD, through a round-number mode (§4.3); `CURRENCY_CODE` is otherwise a label.

### 4.3 Amount: party-class scale × round-number snapping **[S]**
Median USD amount by party pair:

| Ordering → Beneficiary | Median USD |
|---|---|
| B → B | 22,888 |
| B → C | 3,119 |
| C → B | 3,229 |
| C → C | 463 |

≈ ×7 per business side, i.e. a multiplicative "who is paying whom" factor, with a lognormal body (σ ≈ 2.29 in natural-log USD, ≈ 1.0 dex) and a heavy tail.

On top of that, the **USD label** turns on a round-number mode: **38.65%** of USD payments are whole dollars vs **0.99%** of non-USD payments, and the multiple-of-100 shares are 15.55% vs 0.01%. Holding the sender country fixed, switching the label to USD switches the mode on (DE-EUR 0.94% vs DE-USD 37.5%; US-EUR 0.90%); no conversion or local-currency draw is involved.

### 4.4 Currency choice **[V]**
The currency is decided on the **sender side**: read from the first bank of `BIC8_PATH`, it matches that bank's home currency on **93.42%** of rows, vs 19.09% for the beneficiary side and 89.45% for the `ORDERING_BIC8` column (which is ~5% wrong). Among 182 sender countries with ≥1,000 rows the home share runs from 72.9% to 98.3% (median 91.9%). The 6.6% foreign residual is mostly EUR (56.0%) and USD (25.6%) and leans toward the beneficiary's home currency. This is what produces `CURRENCY_CONVERSION_COUNT > 0`; it is not an FX pricing decision.

### 4.5 Routing: a popularity-weighted correspondent graph **[S/T]**
- 2.23 M distinct directed bank edges, 15 M path transitions.
- Intermediate banks are drawn from country weights that look like financial-centre shares; ordering and beneficiary bank countries are near-independent draws from similar weights (same-country only 7.1%).
- Some bank pairs repeat thousands of times (`0001MQM0→0009TNT0` 13,343 times, `0032MYK0→0010ALT0` 11,313) — hub structure, not uniform random.
- Ellipses are applied *after* the route is built, with a geometric gap count.

### 4.6 Latency: a route constant plus tiny noise **[S]**
For a given ordered bank pair, `TOTAL_DURATION` is essentially deterministic:

| Pair | n | median | sd | range |
|---|---|---|---|---|
| 0001MQM0→0009TNT0 | 12,642 | 1,594 s | 6.9 | 1,586–1,643 |
| 0032MYK0→0010ALT0 | 10,628 | 25 s | 33 | 12–3,354 |
| 0065SGS0→0472US30 | 6,924 | 923 s | 7.0 | 915–970 |

The residual noise is small and right-skewed (mode ≈ −5 s, 95th pct ≈ +20 s, sd ≈ 7 s). At route level, latency ≈ **sum of per-bank step delays + jitter**, not a behavioural wait time; conversions and hidden hops add nothing.

The route constants are **approximately additive in bank-level effects** (origin + beneficiary effects explain R² ≈ 0.99 of the variation across 18,063 bank pairs), and the bank effects are heavy-tailed: some banks add ~5–20 s, others ~1,000–5,000 s. This R² is a **pair-level** statement: with the exact banks known, duration is nearly deterministic. It does not mean duration can be forecast from coarse features — a model using amount, hour and label alone reaches only R² ≈ 0.2. Country-pair medians therefore span ~9 s to ~7,400 s purely because different banks are involved.

Practical implication: `TOTAL_DURATION` is a **route fingerprint**. It barely depends on amount, hour or weekday, so with the bank pair known it can check "is this payment's latency consistent with its stated path?" — a strong anomaly-detection feature in that setting.

### 4.7 Anomaly injection: labelled mutations of otherwise normal rows **[S/T]**
**7,006 rows = 0.07%** are labelled, and most labels have a distinct mechanical signature:

| Label | n | Signature |
|---|---|---|
| ROMANCE_SCAM | 2,476 | ordering type `C` only; 500 distinct sender accounts, 378 beneficiary accounts; repeated payments to the same beneficiary; median gap ~10 min; median amount $109; currencies skew INR/CNY |
| FAT_FINGER_MISTAKE | 1,940 | extreme amounts (median $260k, p90 $77m) — an honest amount × 10^k with **k varying per row**; ÷10–1,000 returns 56.0% into the sender's middle 50% vs 34.7% of clean rows. One fixed comma position and "a copy of a real payment" are both refuted |
| CEO_SCAM | 945 | ordering type `B` only; mean $1.38M |
| DUPLICATE_PAYMENT | 679 | shares ordering account, beneficiary account, amount **and** currency with another row; median gap ~18 min (1,099 s), vs ~14.7 days for clean repeats of the same trio |
| ACCOUNT_REPLACEMENT_SCAM | 649 | same ordering account + same amount but a *different* beneficiary account |
| CUSTOMER_RECALL | 317 | undocumented in the brief; **no payment-level signature** — amount, account freshness, repeat timing and paired labels all match the clean baseline. It behaves like a post-payment status |

Key insight: the anomaly is **not** a separate population — it is a small set of rows whose fields were mutated (or cloned) according to a rule. That is why duplicates exist among *unlabelled* rows too, and why unlabelled rows can still look anomalous.

---

## 5. Reconstructed generator pipeline (best current reconstruction)

```
1. WORLD SETUP
   - country list with weights (financial-centre-like), integer clock offset, dominant currency
   - per country: N banks, BIC8 = f"{code:04d}" + country + location2
   - country -> dominant-currency map (recovered from data; NO FX rate path)
   - global: local-hour activity curve, weekday factors, day-level intensity

2. PARTY SETUP  (reused entities)
   ordering  = (bank, account, type B/C)   # account ↔ country ↔ type fixed forever
   beneficiary = (bank, account, type B/C)
   details   = Faker text in the bank country's locale  (ordering)
               Faker text in an independently drawn beneficiary country (beneficiary)

3. ROUTE
   n_hops ~ Geometric(p≈0.37)  (Direct if 2 visible nodes)
   intermediates ~ bank popularity weights
   hide some hops with '...'  (geometric, ~7% one gap)
   -> BIC8_PATH, PARTICIPANT_COUNT, TRANSACTION_TYPE_CODE, CONTINUITY_QFLAG

4. MONEY
   USD_AMOUNT = round_snap(lognormal(centre = f(country, type_o, type_b)))
   CURRENCY_CODE = sender country's currency with prob p(country),
                   else mostly EUR/USD leaning to the beneficiary
   USD label adds a whole-number / {1,2,5}x10^k mode; no rate multiplication

5. TIME
   day ~ intensity(weekday, week)
   local_hour ~ global_curve
   EPOCH_SECONDS = utc(local datetime, integer_offset(country))

6. LATENCY
   base = g(origin bank) + g(beneficiary bank) (+ hop terms)
   TOTAL_DURATION = round(base + jitter)

7. ANOMALY INJECTION (7,006 rows = 0.07%)
   mutate/clone rows per six labels; CUSTOMER_RECALL has no payment-level signature
```

---

## 6. Why this matters for the analysis / dashboard

1. **Don't trust real-world priors where the generator defines its own mapping.** Country→currency, clock offsets, bank sizes and geography weights were randomised. Recover them from the data (we have the currency map; there is no FX table to recover).
2. **The 1:1 invariants are the skeleton.** Participant count, conversion count and continuity flag are deterministic functions of the path — any dashboard that treats them as independent KPIs is double-counting.
3. **Time must be localised** before any hour-of-day or "business hours" narrative.
4. **Amount must be read on two axes**: party class (×7 per business side) and the country centre (a 650× ladder), plus a USD-only round-number mode. A raw USD amount distribution mixes them all; there is no FX-day axis.
5. **Latency is a route fingerprint, not a service-level metric.** Service-level stories should be framed as "route/correspondent speed", not "processing delay varies with customer behaviour".
6. **Anomalies are injected mutations**, so detection rules should be structural (same account+amount+beneficiary; amount jump vs the account's history; latency inconsistent with path), not purely statistical outliers.
