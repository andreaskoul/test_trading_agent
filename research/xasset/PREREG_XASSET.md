# Non-equity trend following against the trend core, 1962–2002: precision estimate — pre-registration (2026-11-25)

Committed before any check or statistic below is computed. Inputs and their status: `SCOPE.md`, `LIT_PRIOR.md`,
`VALIDATE.md`, `PROCURE.md`, `FREE_DATA.md` (this folder). Owner's rulings (2026-11-25): the 1962–2002 yield-and-FX
proxy may serve as a **precision-estimation** experiment, not a standalone admission test; free futures data are
used (licence question waived by the owner); pre-2003 data checks that compare price levels, never returns, are
allowed; ETFs, futures and options are permitted for research only; no new instrument is authorised for trading.
Research only: nothing under `fund/` changes.

## 1. The quantity, and what it is not

**Estimated:** AR_proxy|core, the appraisal ratio of a non-equity time-series-momentum sleeve against the fund's
trend core (the 200-session 1.3×/0.7× rule on the US market), monthly, net of costs, 1962-01 to 2002-12.

**Not estimated:** AR_executable|core,MASTER, the quantity a promotion needs. MASTER does not exist before 2013. The
historical instruments are proxies and back-adjusted futures, not the ETFs a forward record would hold. Every result
line carries the label "against the core only; proxy and futures instruments".

**Three sources of evidence, kept apart** (owner, 2026-11-25):

| Source | Role |
|---|---|
| Published literature (`LIT_PRIOR.json`) | a discounted prior, built only from years **outside** 1962–2002 |
| This 1962–2002 read | the estimate of historical residual alpha against the core |
| The executable forward record (ETFs, registered later) | posterior update, implementation fidelity, dependence with MASTER |

The literature years inside 1962–2002 overlap this read and are not used in the update. That avoids counting
the same evidence twice.

## 2. Data (frozen; `MANIFEST.json`, `FREE_MANIFEST.json`)

| Leg | Markets | Construction | From |
|---|---|---|---|
| US Treasuries | 5-year, 10-year | `proxy.py` par-bond excess return (carry, duration, convexity, financing), daily H.15 yields | 1962 |
| Currencies | GBP, AUD, CAD (complete); JPY, CHF (BoJ, SNB short rates); DEM (BIS); NOK, SEK, DKK where covered | `proxy.py` spot log change + short-rate differential; a missing differential drops the month (typed defect) | 1972 |
| Non-US government bonds | UK, Germany, Japan, Canada, Switzerland | par-bond proxy on month-end yields, local short rate as financing, hedged to USD (local excess return) | 1970–1988 |
| Commodities | the pysystemtrade full-size markets, minis and micros excluded; splices flagged | excess return of the held contract: change in the back-adjusted price over the held contract's price | 1969–70 |

* The universe is **dynamic**: a market enters in the first month with 13 months of returns behind it (12 for the
  signal, 1 for volatility).
* The US 1-year and 3-year proxies failed validation against SHY and are not used. The US 2-, 20- and 30-year series
  are left out: they are incomplete over the sample, and extra maturities add almost nothing because bond trends are
  highly correlated (`FREE_DATA.md`).
* The dollar-index proxy (UUP) failed validation and is not used.

## 3. Checks before the read (a gate; the read script refuses to run unless all pass and are committed)

Thresholds as in `VALIDATE.md`: correlation ≥ 0.95, tracking error ≤ 0.35 × the instrument's volatility,
|bias| ≤ 1 %/yr, 12-month signal sign agreement ≥ 90 %, |difference in sign switches| ≤ 0.5 a year. All validation
statistics are computed on 2003-01 or later (spent).
1. **New constructions on 2003+:**
   * JPY and CHF carry (BoJ, SNB rates) and DEM (BIS), against FXY, FXF and the euro proxy;
   * the five non-US bond proxies, against the same-country government bond futures in pysystemtrade (gilt, Bund,
     JGB, CGB, Swiss);
   * pysystemtrade commodity excess returns against a second source on 2003+, which is any of: yfinance
     continuous futures, or the CHRIS-style mirror (front contract, roll days excluded).
   A market that fails is dropped, and the drop is recorded. The sample is not re-scoped afterwards.
2. **Pre-2003 level checks, never returns** (owner's ruling). For pysystemtrade commodities against the CHRIS-style
   mirror, on dates both hold the same contract:
   * count the sessions where the settlement prices agree within 0.5%;
   * a market with fewer than 95% agreeing is dropped;
   * the counts are recorded per market and decade.
   The script holds no return, signal or statistic of a pre-2003 date in memory beyond the level comparison.
3. **Splices and variants:** files flagged as splices (Eurodollar inside SOFR, unleaded gasoline inside RBOB) and
   December-only contracts are excluded. Minis and micros are excluded where a full-size contract exists.
4. **Content contracts** (CLAUDE.md rules 1–3) on every series; coverage is checked against the expected calendar.

## 4. The sleeve (fixed from Moskowitz–Ooi–Pedersen 2012; no choice is tuned)

* **Signal:** the sign of each market's excess return over the past 12 months (MOP: k = 12, h = 1), at each month
  end.
* **Position:** sign × 40% / σ̂, where σ̂ is the ex-ante annualised volatility from an exponentially weighted variance
  of daily returns (centre of mass 60 days, MOP). Where only month-end data exist (non-US yields), σ̂ is the
  36-month rolling sd of monthly returns.
* **Portfolio:**
  * equal weight across markets within each asset class (bonds, currencies, commodities);
  * equal weight across the asset classes present that month;
  * the sleeve scaled to 10% annualised volatility, using only past data (the 36-month rolling sd of the unscaled
    sleeve, starting after 36 months).

  The AR does not depend on that last scale; the allocation calculations in §6 do.
* **Costs, one-way, on |Δposition| (HOP Exhibit B1, copied in `LIT_PRIOR.json`):**
  * bonds 0.06% (to 1992), 0.02% (1993–2002);
  * currencies 0.18%, 0.06%;
  * commodities: no copied value, so they are charged at the currency rates (an assumption, labelled).

  **Sensitivity: 2× costs.**

## 5. Statistics (one read; `READ_XASSET.lock` written first)

* **Core returns:** the monthly excess return of the 1.3×/0.7× core, arm M under (R), from
  `research/sharpe/capital.py` sample (a), 1962–2002 (a spent sample, used as the benchmark).
* **Regression:** monthly sleeve excess return on core excess return. AR = α / σ(ε) × √12.
  * SE: Newey–West, 6 lags.
  * 90% interval: stationary block bootstrap, mean block 12 months, 10,000 draws, seed 20261125, paired months.
* **Second benchmark, the Huang et al. critique:** the core plus a static long position in the US 10-year proxy.
  This shows whether the sleeve is trend or bond term premium.
* **Diagnostics, for attribution, not selection:**
  * the full dynamic-universe sleeve (**primary**);
  * rates only (US + non-US);
  * the common rates-and-FX period (1972–2002);
  * commodities only;
  * by decade.
* **Realised cross-market correlation** of the markets' trend returns. Reported with the planning value it is
  compared against: ρ 0.1, from MOP Table 4 (within bonds 0.38, within FX 0.10, bonds–FX 0.05).

## 6. Results reported, and the verdict (owner's framework: rejected / inconclusive / supported)

* **Reported:**
  * AR (SE, 90% interval) at registered and 2× costs, against both benchmarks;
  * the correlation with the core in the core's worst 10% of months.
* **Constrained contribution to fund Sharpe:**
  * all weights ≥ 0, the core at its policy weight;
  * two exposure rules, side by side:
    * (i) the incumbent 1.9× cap on notional;
    * (ii) the volatility-equivalent rule: equity delta + non-equity positions at S&P-volatility equivalent
      ≤ 1.9, with a stress-loss limit of 25% of NAV in a joint 3-sd month and absolute notional ≤ 6×.

  Volatility scaling in calm markets is reported as the largest notional reached under (ii).
* **The verdict is a classification of the estimate, not a test pass:**
  * **supported:** 90% lower bound of AR > 0 at registered costs, against both benchmarks;
  * **rejected:** 90% upper bound < 0.15 (an AR too small to matter at the fund's scale);
  * **inconclusive:** otherwise.
* **Posterior:**
  * prior N(m₀, 0.20²), with m₀ the out-of-window literature value from `LIT_PRIOR.json` (sleeve AR 0.48, the
    agent's centre; its sd widened from 0.15 to 0.20 for disagreement between papers and digitising error);
  * combined with this read's estimate and SE;
  * then multiplied by the forward decay haircut 0.555 (`LIT_PRIOR.json`) to give a **forward planning AR**. That
    figure is the only input to any later sizing.
* **What happens next:** whatever the verdict, an ETF forward shadow is specified next (separate registration)
  as the executable record. Nothing is traded.

## 7. Not claimed

* Not a test of the fund with this sleeve, since MASTER is absent historically.
* Not tradable as run: the instruments are proxies and back-adjusted futures, and the costs are literature values,
  not ours.
* 1962–2002 is unread by this programme, but the field has read it (HOP, MOP). The verdict describes how much
  independent residual return non-equity trend plausibly offers, not the rediscovery of a known anomaly.
