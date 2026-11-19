# L5_insider: opportunistic insider trading (Cohen-Malloy-Pomorski) — failed the development gate (no 2020-2025 read)

*Written by the branch agent; saved by the coordinating session because subagent report writes are refused.
**Development (2013-2019, 353 Thursdays) only**; `READ_L5I.lock` was not created. Numbers from `RESULT.json`.*

| Configuration | IC | MASTER 5-day IC | Paired increment | NW t | Years + (of 7) | Gate |
|---|---|---|---|---|---|---|
| C1, equal-weight rank average of MASTER 5-day and the insider score | 0.0038 | 0.0125 | −0.0087 | −1.65 | 1 | fail |
| C2, sign-only overlay (MASTER rank + 0.1 × sign of 3-month net count) | 0.0114 | 0.0125 | −0.0011 | −1.24 | 1 | fail |

* **Insider score alone:** IC −0.0092 (t −1.47); increment over MASTER −0.0217 (t −1.90); top-minus-bottom decile
  book −2.61 %/yr net. It points the wrong way in 6 of 7 years on these large caps.
* **Survivorship contract: passes.** Verified-CIK indicator t −1.36 (defined in only 32 weeks); "any Form 4/5 before
  t" t −1.15.
* **Coverage: passes.**
  * All 80 quarters from 2006Q1 to 2025Q4 present; 178k-241k filings a year.
  * Eligible panel names with any Form 4/5 in the year: 96.8-99.8%; with a P or S trade: 91.6-96.7%.
  * 99.97% of eligible, priced name-weeks have a verified CIK.

**Data and method.**
* Source: SEC DERA Insider Transactions Data Sets, one quarter at a time, generic User-Agent. Zip sha256s are in
  `MANIFEST.json`; the zips were deleted after parsing.
* Kept: Forms 4/5 without amendments, codes P and S, for panel issuers. 872,871 trades (`trades.parquet` sha256
  d3808bc4…).
* Dating: the data sets have no acceptance time, so each filing is public at the first session after its filing
  date.
* **CIK map:** verified against the typed `ISSUERTRADINGSYMBOL` field. 464 verified, 212 switched, 26 renames kept,
  36 defects (mostly unpriced names). **`ciks.json` maps several reused tickers to their current owner rather than
  the historical issuer** (XOM, APA, BBT, COG, BBBY). See the coordinator's note in LAYER3_LOG step 36.
* Routine insiders (same calendar month in each of the 3 prior years) are dropped: 9.7% of trades. CMP's extra
  3-year history requirement was not applied (disclosed).
* Score: the mean rank of the net count and net dollar value over 1 and 3 months.
* Content check: Dimon's JPM purchase on 2016-02-11 appears as code P.
* Limits: one CIK per name over its whole span; dollar values not scaled by size.

Files: `fetch.py`, `lib.py`, `gate.py`, `RESULT.json`, `RESULTS.jsonl`, `cik_map_dev.json`, `STATE.json`, `fetch.log`;
`.cache/tree/l5insider/`.
