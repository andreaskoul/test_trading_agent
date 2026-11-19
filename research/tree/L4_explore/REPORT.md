# L4_explore: cross-asset trend sleeve (X1) fails its one read; overnight-intraday (X2) rejected at the survivorship contract

*Written by the branch agent; saved by the coordinating session because subagent report writes are refused.
Numbers from `RESULT.json` and the JSON files it collects.*

## X1, cross-asset trend sleeve — FAIL (no sleeve, no forward shadow)

The sleeve is time-series momentum on IEF, TLT, GLD, DBC and UUP: 12-month sign, equal risk at 10%, sleeve gross
cap 2, 5 bp. The test read 2020-2025 once (`READ_X1.lock` 2026-11-19T14:32:08Z, before any test return), over 302
paired weeks.

| | %/yr | Sharpe | Vol | Worst fall |
|---|---:|---:|---:|---:|
| B0, the fund | 21.69 | 0.937 | 22.4% | −30.0% |
| Fund + sleeve, gross capped at 1.9 | 17.28 | 1.052 | 15.7% | −19.5% |

* **By year, B0 vs with sleeve:** 2020 40.0 vs 35.3; 2021 26.4 vs 17.3; 2022 −16.3 vs −6.0; 2023 25.7 vs 17.4;
  2024 38.2 vs 25.7; 2025 25.3 vs 17.5.
* **Ledoit-Wolf HAC test** (matched volatility, Bartlett kernel, 5 lags): ΔSharpe +0.115 (SE 0.113), z 1.02,
  **p 0.154**.
* **Deflated Sharpe Ratio:** **0.617** at N = 44, below 0.95. It is 0.500 at N 100 and 0.409 at N 200; the
  registered count is larger still, so it fails at every N.
* **Sleeve alone, test** (excess of cash): Sharpe 0.132, 0.73 %/yr, vol 11.2%. By year +10.6, −1.8, +13.0, −7.0,
  −2.0, −6.5. Correlation with B0 −0.29.
* **Decomposition** (descriptive, computed after the read): most of the +0.115 comes from shrinking the fund to fit
  the 1.9 gross cap (mean scale 0.707), which cuts the margin cost charged at rf + 2.43%, not from the sleeve.
  * B0 scaled down the same way, with no sleeve: Sharpe 0.969.
  * B0 at a constant 0.707: 0.998.
  * Fund + sleeve with no cap: 0.985, 22.04 %/yr.
* **Development** (2003-07-31 .. 2019-12-19, 831 weeks): sleeve Sharpe 0.194, 1.67 %/yr, vol 12.7%, worst fall
  −34.7%.
  * Correlation with SPY −0.199. The gross cap bound almost always (mean gross 1.997).
  * Contributions, %/yr: IEF +1.17, TLT +0.27, GLD +1.68, DBC +1.32, UUP −1.33.
  * The core's development Sharpe is 0.511 (matching construct.py).
  * Sleeve weight 0.480 per core unit, from the registered formula with S_x halved to 0.097.
* **Data:** yfinance, frozen with sha256 (`.cache/tree/l4x/MANIFEST.json`). Content check: 0 defects; every
  dividend event consistent between Close and Adj Close. Spot checks against FRED series: IEF −0.96 with 10-year
  yield changes, TLT −0.94, UUP +0.67, DBC +0.40 with WTI. GLD has no independent check (stooq blocked).
* **Deviations:** the DSR uses V = 1/(T−1) and N = 44 (smaller than the registered count; it fails either way); the
  HAC uses a Bartlett kernel, not prewhitened QS.

## X2, overnight minus intraday — rejected before any signal was computed

* `dev.npz` has no open prices. `extra_intraday.npz` (2016-2019) holds current constituents only, about 57% of
  eligible names.
* Its availability indicator has IC +0.0244, **NW t 3.52** (198 weeks), against the limit |t| < 2, and no
  point-in-time gate exists.
* `READ_X2.lock` was not created. Disclosure: branch N3 had already looked at this signal on 2017-2019 (double ML
  t 1.02).

Files: `fetch_x1.py`, `spot_x1.py`, `x1.py`, `x1_decomp.py`, `x2.py`, `RESULT.json`, `STATE.json`, `X1_*.json`,
`X2_DEV.json`, `READ_X1.lock`; data `.cache/tree/l4x/`.
