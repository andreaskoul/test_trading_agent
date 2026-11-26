# Proxy constructions for Treasury and currency time-series momentum: contracts, coverage and 2003+ validation (2026-11-25)

**Status.** This checks data. It does not test a strategy. Two constructions are compared with executable ETFs on
the **spent** 2003-01 .. 2026-10 period:
* a synthetic constant-maturity Treasury par bond;
* a currency excess return (spot plus the interest differential).

The statistics describe how well the instruments track each other. **No Sharpe ratio, mean return or other
performance figure of any trend strategy was computed.**

**The 1962-01 .. 2002-12 returns stay unread.**
* Every computed series passes through `validation_window()` in `proxy.py`, which keeps dates on or after
  2003-01-01. The mask is applied to the level inputs before any difference is taken, and again to every output.
* The 92 computed series of the validation run all start on or after 2003-01-03 (`mask_check` in `VALIDATE.json`).
* On pre-2003 dates only presence was used: first and last dates, month counts, missing-value counts, and field
  contracts such as declared units, frequency and plausible ranges.

Machine-readable results: `VALIDATE.json`. Frozen inputs: `MANIFEST.json` (85 files with their sha256, fetched
2026-11-25). The data files sit in `.cache/xasset-proxy/` and are not committed. Code: `proxy.py`. Tests:
`test_proxy.py`.

**Thresholds were fixed before the data were looked at.** They are `THRESHOLDS` in `proxy.py`, committed in
140900d at 2026-11-25T01:07:44Z, before `validate` was first run:
* correlation of monthly excess returns ≥ 0.95;
* tracking error ≤ 0.35 × the ETF's volatility (two series of equal volatility with correlation 0.95 give 0.32);
* |mean difference| ≤ 1.0 %/yr;
* 12-month TSMOM sign agreement ≥ 90 %;
* |difference in sign switches per year| ≤ 0.5.

A pair validates only if all five hold.

## 1. Constructions

The formulas are in the docstring of `proxy.py`.

**Treasury excess return.**

  r = y_t Δt − D_t Δy_{t+1} + ½ C_t (Δy_{t+1})² − r_f,t Δt

* y is the FRED H.15 daily CMT yield (DGS*, investment basis), sampled at the last observation of each month. That
  observation must fall within the last 7 days of the month.
* D and C are the modified duration and convexity of a semi-annual par bond at y_t.
* r_f is DTB3. Its title declares a discount basis, so it is converted to a bond-equivalent yield,
  365d / (360 − 91d).
* Δt is calendar days divided by 365.
* The maturity N is read from the FRED title ("at N-Year Constant Maturity"), not from the series id.
* An exact par-bond repricing variant is a diagnostic. On the 2003+ months it correlates 0.99987 to 0.999999 with the
  Taylor form, and the mean absolute gap is 0.07–0.17 %/yr.

**Currency excess return** (USD per unit of foreign currency):

  r = Δ log S_{t+1} + (i_f,t − i_US,t) Δt

* S is the H.10 noon rate (DEX*). Whether to invert the quote is decided from the FRED **Units** field ("X to One
  U.S. Dollar" or "U.S. Dollars to One X").
* i is the OECD MEI 3-month interbank rate (IR3TIB01*) for the foreign country and for the US. The value for month m
  accrues over the period that starts at the end of month m, so there is no look-ahead.
* **A missing differential is the typed defect `missing_interest_differential`.** The observation is dropped and
  counted per currency and year. It is never set to zero.

**ETF comparators.**
* The return is the Yahoo adjusted close, frozen at first fetch, minus the **same** cash leg the proxy uses: DTB3 for
  Treasuries, the US 3-month interbank rate for currencies.
* Contract: on every 2003+ month, the adjusted-close return agrees with close plus dividends within 5 bp. The largest
  gap was 1.6 bp.
* UUP is compared with minus the dollar-index basket of the six currency proxies, using the ICE weights. Those weights
  are `reasoning`: they are standard published values, and no source was opened for them in this run.

## 2. Validation on 2003+ (spent)

Monthly excess returns over the same months for each pair:
* TE: tracking error, in %/yr, with the ratio to the ETF's volatility in brackets;
* bias: mean of (proxy − ETF), in %/yr, with the Newey-West SE in brackets (lags ⌊4(T/100)^{2/9}⌋ = 4–5);
* agree: the share of months with the same 12-month TSMOM sign (number of months);
* Δsw: sign switches per year, proxy minus ETF;
* β: the ETF regressed on the proxy;
* daily ρ: a diagnostic, not part of the verdict.

| ETF | Proxy | Role | Months | ρ | TE (÷vol) | Bias (SE) | Agree | Δsw | β | Daily ρ | Validates |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SHY | 2y (DGS2) | primary | 285 | 0.982 | 0.31 (0.22) | −0.09 (0.08) | 90.1 % (274) | +0.44 | 0.90 | 0.906 | **yes** (agreement and turnover at the margin) |
| SHY | 1y (DGS1) | alternate | 285 | 0.867 | 0.91 (0.64) | −0.11 (0.18) | 83.2 % | +0.09 | 1.87 | — | no: ρ, TE, agreement |
| SHY | 3y (DGS3) | alternate | 285 | 0.970 | 1.15 (0.81) | +0.01 (0.24) | 85.8 % | +0.61 | 0.56 | — | no: TE, agreement, turnover |
| IEI | 5y (DGS5) | primary | 237 | 0.994 | 0.52 (0.13) | −0.48 (0.12) | 96.5 % (226) | +0.21 | 0.93 | 0.963 | **yes** |
| IEI | 7y (DGS7) | alternate | 237 | 0.978 | 2.07 (0.53) | −0.16 (0.45) | 97.8 % | +0.11 | 0.67 | — | no: TE (duration mismatch) |
| IEF | 10y (DGS10) | primary | 285 | 0.990 | 1.38 (0.21) | −0.49 (0.28) | 96.4 % (274) | +0.18 | 0.87 | 0.966 | **yes** |
| IEF | 7y (DGS7) | alternate | 285 | 0.984 | 1.40 (0.21) | −0.83 (0.28) | 98.5 % | +0.00 | 1.13 | — | yes |
| TLT | 20y (DGS20) | primary | 285 | 0.987 | 2.59 (0.19) | −0.18 (0.46) | 96.7 % (274) | +0.26 | 1.12 | 0.955 | **yes** |
| TLT | 30y (DGS30) | alternate | 248 (from 2006-03) | 0.993 | 2.12 (0.15) | +0.05 (0.46) | 99.2 % | +0.10 | 0.91 | — | yes |
| FXE | EUR | primary | 241 | 0.995 | 0.95 (0.10) | +0.47 (0.12) | 97.3 % (219) | +0.11 | 1.00 | 0.843 | **yes** |
| FXY | JPY | primary | 235 | 0.995 | 0.99 (0.10) | +0.30 (0.13) | 97.7 % (213) | −0.11 | 1.00 | 0.859 | **yes** |
| FXB | GBP | primary | 235 | 0.992 | 1.13 (0.13) | +0.80 (0.12) | 95.3 % (213) | −0.23 | 0.97 | 0.875 | **yes** |
| FXF | CHF | primary | 243 | 0.994 | 1.04 (0.11) | +0.16 (0.14) | 98.2 % (221) | −0.11 | 1.01 | 0.859 | **yes** |
| FXA | AUD | primary | 243 | 0.992 | 1.57 (0.13) | +0.64 (0.22) | 96.8 % (221) | −0.11 | 1.00 | 0.826 | **yes** |
| FXC | CAD | primary | 243 | 0.990 | 1.26 (0.14) | +0.72 (0.18) | 96.4 % (221) | +0.44 | 0.99 | 0.812 | **yes** |
| UUP | −DXY basket | primary | 226 | 0.992 | 0.98 (0.13) | **+1.44** (0.14) | 90.2 % (204) | +0.00 | 1.00 | — | **no: bias** |

Windows: the ETF's first full month (SHY, IEF, TLT 2003-02; IEI 2007-02; FX ETFs 2006–2007) through 2026-10. EUR
and GBP end in 2026-02, where the OECD rate ends (§3).

**What this shows (sources are `reasoning` unless a file is named):**
* **Treasuries.**
  * Every primary maturity mapping validates: SHY–2y, IEI–5y, IEF–10y, TLT–20y.
  * The proxy's bias is negative: −0.1 to −0.5 %/yr after ETF fees of about 0.15 %/yr. The likely cause is that a
    constant-maturity par bond earns no roll-down. Under a positive slope this understates the return of a fund that
    holds bonds as they roll down the curve.
  * A bias of this size moves the 12-month sign only near zero.
  * SHY–2y passes agreement at 90.1 %, just above the 90 % line. The 1y and 3y proxies fail against SHY: they are a
    duration mismatch, and SHY's mix is close to 2 years.
  * The 1, 3, 7 and 30-year proxies therefore have no tight executable comparator, or only a partial one: 7y passes
    against IEF but fails TE against IEI, and 30y passes against TLT from 2006.
* **Currencies.**
  * All six single-currency proxies validate, with ρ 0.990–0.995 and agreement 95–98 %.
  * The bias is positive, +0.16 to +0.80 %/yr. That is consistent with the CurrencyShares fee of 0.40 %/yr plus
    deposit rates below interbank rates.
  * Daily correlation is only 0.81–0.88. That is expected from the timing: H.10 fixes at noon New York, the ETF closes
    at 16:00. The daily volatility ratios are 0.96–1.02, so daily proxies can still feed an EWMA volatility estimate.
* **UUP fails on bias** (+1.44 %/yr, SE 0.14). The likely components are UUP's fee of about 0.8 %/yr, T-bill
  collateral (the proxy's cash leg is interbank), and the futures basis. The basket's correlation (0.992) and
  agreement (90.2 %) pass. UUP is a dollar-index product, not a test instrument, so this failure concerns the
  comparator, not the single-currency constructions.

## 3. Defects

| Defect | Where | Count | Treatment |
|---|---|---|---|
| Values inside a declared discontinuation | DGS30. The FRED notes say "discontinued on February 18, 2002, and reintroduced on February 9, 2006", yet the CSV has values on every business day | 994 rows removed | Typed. Parsed from the notes; TLT–30y starts 2006-03 |
| `missing_interest_differential` | US 3-month rate missing for one month in 2020: 1 per currency, 9 currencies. EUR and GBP rates end 2026-01, so 8 months in 2026 each | 2003+: EUR 9, GBP 9, other currencies 1 each | Dropped, never zero |
| `basket_incomplete` | −DXY basket in 2026 (EUR and GBP rates end) | 8 | Dropped |
| Range contract failure | IRSTCI01CHM156N (Swiss call money): one value below −2 % (2016-08) | 1 | The whole series is unusable. The CHF call-money fallback is unavailable |
| Units mismatch (caught on the first run) | DEXUSUK declares "U.S. Dollars to One U.K. Pound Sterling" | — | The expected name was corrected to "U.K. Pound". The typed check worked as designed |
| Incomplete last ETF row | All 11 ETFs: the in-progress 2026-11-24 session had no close | 1 row each | Dropped and recorded |
| Point-in-time contract | GS1, GS3, GS5, GS10, TB3MS, EXGEUS (DEM): monthly series whose notes say they are averages | — | Excluded. Coverage only |
| Averaging convention not declared | IR3TIB01*: the FRED notes do not say whether values are monthly averages or month-end | — | Not a look-ahead either way (the month-m value accrues over month m+1). To be settled at registration |

## 4. Coverage of the never-read sample (presence counts only)

**Treasuries, 1962-01 .. 2002-12** (492 months; a month counts if it has a valid month-end observation):

| Series | Months | Gap |
|---|---:|---|
| DGS1, DGS3, DGS5, DGS10 | 492 / 492 each | none |
| DTB3 (cash) | 492 / 492 | none |
| DGS7 | 402 | before 1969-07 |
| DGS2 | 319 | before 1976-06 |
| DGS20 | 411 | 1987-01 .. 1993-09 |
| DGS30 | 300 | before 1977-02; from 2002-02 (discontinuation) |

**Currencies, 1972-01 .. 2002-12** (372 months of spot; 371 one-month periods):

| Currency | Spot months | Periods with a differential | First month of the foreign rate |
|---|---:|---:|---|
| GBP, AUD, CAD | 372 | **371 / 371** | GB 1957, AU 1968, CA 1956 |
| NOK | 372 | 287 | 1979-01 |
| SEK | 372 | 251 | 1982-01 |
| DKK | 372 | 191 | 1987-01 |
| CHF | 372 | 41 | 1999-07. The call-money fallback fails its contract |
| JPY | 372 | 8 | 2002-04. A call-money fallback (IRSTCI01JP, from 1985-07) would give 209. On 2003+ it validates against FXY as well as the 3-month rate does: ρ 0.995, agreement 98.1 % |
| EUR | 48 (from 1999-01) | 47 | EZ 1994 |
| DEM | no daily H.10 series on FRED; EXGEUS is a monthly average | — | DE 3-month rate from 1960 |

The US 3-month rate (IR3TIB01US) starts in 1964-06, so it covers 1972–2002 in full.

**Complete 1962–2002 rates coverage:** the 1, 3, 5 and 10-year maturities and the T-bill (492 of 492 months each).
The validated primary maturities are 2, 5, 10 and 20 years. Of those, only the 5 and 10-year proxies have both a
validating ETF and complete coverage from 1962. 2y covers from 1976-06, and 20y has a 1987–1993 gap.

**Complete 1972–2002 currency coverage, carry included:** GBP, AUD and CAD (371 of 371 periods). Spot alone is complete
for eight currencies.

**Independence reminder (SCOPE.md §1, S6).** The FX legs for 1990–2003 were read cross-sectionally in the
confirmation pass. On that basis SCOPE §7 restricts the FX sample to 1972–1989.

## 5. Tests (`python research/xasset/test_proxy.py`, 12 pass)

* **Date mask.**
  * `test_mask_holds_on_every_construction` runs every construction on a synthetic 1995–2010 fixture and passes.
  * `test_mask_check_fails_on_a_deliberate_fault` replaces `validation_window` with the identity on the same fixture.
    The check then raises, as it should.
  * `test_real_validation_run_is_masked` runs the full validation on the frozen data. All 92 series start on or after
    2003-01-01.
  * The fault is injected on synthetic data only, so no pre-2003 return of real data is ever computed.
* **Missing differential.**
  * `test_missing_differential_is_a_defect` uses a fixture missing one foreign month (2005-06) and one US month
    (2007-03). Both periods are dropped, and the defects are counted as {2005: 1, 2007: 1}.
  * `test_missing_differential_check_fails_on_a_deliberate_fault` zero-fills the rates, and the check raises.
* **Arithmetic.** The par-bond duration matches its closed form. The convexity matches a numerical second derivative.
  The Taylor and exact forms agree within 2 bp for a 10 bp move. An unchanged yield earns (y − r_f) Δt.
* **Real-fixture contracts.**
  * The quote direction comes from Units, and the maturity from the title.
  * DGS30 has no values inside its declared discontinuation.
  * The out-of-range Swiss call-money series is refused.
  * A frozen file whose sha256 differs from the manifest is refused.

## 6. Disclosures and limits

* **Pre-2003 values seen by accident.** Both are levels, not returns, and no statistic was computed from them:
  * the first TB3MS row (1934-01), printed by an endpoint probe;
  * the first SHY row (2002-07-30 close and adjusted close), printed by a file-header check.
* **Post-2003 values seen deliberately** (spent period): the Swiss call-money values for 2016-05 .. 2016-11, while
  diagnosing its range failure.
* **Network.** FRED refused curl (HTTP/2 INTERNAL_ERROR) and browser-like User-Agents. Python's default urllib
  User-Agent worked.
* **ETF prices** are Yahoo adjusted closes. Yahoo revises its adjustments, so they are frozen at first fetch
  (CLAUDE.md rule 4).
* **Not tried:** IMF IFS short rates (an alternative for the CHF and JPY carry before 1999/2002).
* **Not claimed:** that the proxies are executable, or that the 2003+ tracking carries over to 1962–2002. Bid-ask
  costs, the market structure and the CMT fitting method all differed then. That the bias explanations in §2 are
  right: they are `reasoning`.
* **The thresholds are proposals for the owner.** The pre-registration may adopt them or tighten them.
  * SHY–2y passes agreement by 0.15 points.
  * UUP fails.

## 7. Reproduce

```
python research/xasset/proxy.py fetch      # no-op once frozen; verifies sha256 against MANIFEST.json
python research/xasset/proxy.py validate   # rewrites VALIDATE.json (identical apart from written_utc)
python research/xasset/test_proxy.py
```
