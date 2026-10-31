# Data defect: SEC acceptance times in the P8 cache (found 2026-10-31)

## What was wrong

* **Source.** The P8 cache (`research/p8/edgar.py bulk`) took 8-K acceptance times from SEC's bulk submissions.zip
  and read them as US Eastern clock time.
* **SEC's live API** (`data.sec.gov/submissions`) writes the same field in true UTC. SEC's filing index pages confirm
  it: Apple 0000320193-24-000005 reads `2024-02-01T21:30:30.000Z` in the API, and the index page shows *Accepted
  2024-02-01 16:30:30* (EST).
* **The bulk file mixes encodings.** On 31,973 filings of 8 large filers it read 4–5 hours later than the API. In
  samples of other filers it matched the API for 7% of ordinary filings and for all 360 odd-hour filings.

## What it did to the report sessions (t0)

The 40,321 earnings events in `.cache/p8/events.parquet` (S&P 500 and S&P 400, 2012–2025) were matched to the live-API
time of the same 8-K 2.02. All matched. On the sessions covered by the price panel (from 2016):

| | events | t0 one session late | t0 right |
|---|---:|---:|---:|
| all | 30,646 | 6,591 (21.5%) | 24,055 |
| S&P 500 | | 22.5% | |
| S&P 400 | | 20.2% | |
| fit 2016–2021 | | 22.8% | |
| validation 2022–2025 | | 19.7% | |

* **Pattern.** The error is always one session late, never early. It is concentrated in winter (January 52%,
  December 35%, June 9%): before-open releases in standard time, read as afternoon.
* **2012–2015** (yfinance prices) was not re-checked here; it is assumed to be similar.

## Which results it touches

* **Family H (reads spent).**
  * H1 (sympathy reversal), H3a/H3b and the earnings windows of H4/H5 used these t0.
  * For a misplaced event, the window [t0 − 1, t0 + 1] became [true t0, true t0 + 2]. It still contains the reaction
    day, but the day before the report is dropped and the order of early and late reporters shifts by a day for about
    a fifth of events.
  * The validation (2026-10-27) and sealed reads are spent. They are **not** re-run here. A corrected re-read would be
    a new locked read with its own trial count, and that is the owner's decision.
* **The descriptive decay curve** (`decay_earnings.md`, SUE IC by horizon from t0 + 2) started about a fifth of its
  windows one session late. It is descriptive only.
* **Family E** uses the live-API times from the start (PREREG_family_E.md Amendment 1). No Family E statistic used the
  defective times.
* **R5** reads the live API as UTC (`fund/r5.py releases`). Its pre-release timestamp rule is unaffected.
* **The live fund.**
  * `fund/lifecycle.edgar_202` read the live API's UTC as Eastern. Amendment 2's B1 converts it (PR #125).
  * Amendment 8's reference-move table (`m_table`) still reads it unconverted. That is flagged for the owner.
