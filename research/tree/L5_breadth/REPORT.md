# L5_breadth: 13F ownership breadth (Chen-Hong-Stein 2002) — failed the development gate (no 2020-2025 read)

*Written by the branch agent; saved by the coordinating session because subagent report writes are refused.
**Development (Thursdays 2014-2019) only**; `READ_L5B.lock` was not created. Numbers from `RESULT.json`.*

| | Weekly IC | MASTER 5-day IC (same weeks) | Paired increment | NW t | Years + | Gate (t ≥ 2.0, ≥ 4 of 6) |
|---|---|---|---|---|---|---|
| C1, equal-weight rank average of MASTER and the breadth change | 0.0102 | 0.0089 | +0.0012 | 0.27 | 4/6 | fail |
| C2, sign-only overlay (MASTER rank + 0.1 × sign) | 0.0091 | 0.0089 | +0.0002 | 0.10 | 4/6 | fail |

* **C1 increment by year:** −0.0052, +0.0074, +0.0053, +0.0078, +0.0046, −0.0134 (2014-2019). Score correlation with
  MASTER: C1 0.76, C2 0.96.
* **Breadth change alone:** IC +0.0070 (t 0.88). Decile spread +1.15 %/yr net (Sharpe 0.20), at book level.
* **Survivorship contract: passes** (availability indicator IC +0.0043, t 1.33).

**Data.**
* Source: SEC DERA Form 13F data sets, 26 files 2013q3-2019q4. Each file's sha256 is in `MANIFEST.json`; the zips
  were deleted after parsing.
* Filers per period: 3,442 (2013-06-30) to 5,087 (2018-12-31). Parsed rows match the summary totals in 92-95% of
  reports.
* Kept: original 13F-HR reports (earliest per filer and period); share positions with no put/call flag.
* Frozen input: `holdings.parquet`, 9,272,128 rows, sha256 b4335a68…dc6e5.
* CUSIP map by an exact rule: 13F issuer-name strings (used by ≥ 2 filers) must equal the SEC current or former
  names of a panel CIK. About 95-96% of panel CIKs with a valid name are mapped; 95.5-97.4% of priced eligible
  name-weeks have a score.
* Spot check (2016-06-30): AAPL is held by 2,321 filers, JPM by 1,967, MSFT by 2,244, WMT by 1,479.
* Signal: the change in breadth among filers present in both quarters, recomputed weekly from filings dated before
  the Thursday. It switches quarter once ≥ 50% of the previous quarter's filers have filed.

**Defects and disclosures.**
* XOM has no score (its current-ticker CIK is a 2026 holding company: the same `ciks.json` defect as step 36).
* Abbreviated issuer names stay unmatched.
* Issuer-level counting includes ETNs and similar CUSIPs (noise). FB has no CIK.
* Amendments made before any computation: 8-character CUSIP key; single-slash state suffixes removed in name
  normalisation.
* Development window 2014-2019 (the data start in 2013Q2). Baseline: dev.npz `master_h5_ref`.

Files: `STATE.json`, `fetch_parse.py`, `build.py`, `dev.py`, `RESULT.json`, `RESULTS.jsonl`; `.cache/tree/l5breadth/`.
