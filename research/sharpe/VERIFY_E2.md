# Verifying the 2× fund holding for the trend core (2026-11-24)

**The proposal.** The trend core holds 1.3× the S&P 500 in up-trends and 0.7× in down-trends. Today the extra 0.3 is
borrowed on margin (T-bill + 2.43 %/yr). The proposal holds 0.7 SPY + 0.3 SSO (a 2× daily-reset S&P 500 fund) in
up-trends and 0.7 SPY in down-trends. The capital study (`RESULT_CAPITAL.md`) found +0.25 %/yr against margin on the
fund's 2020-2025 positions (HAC SE 0.08). It also found the proposal removed all 159 weeks above the 1.9× gross cap.

**What this is.** A descriptive check on data the capital study has already seen. It is not a new hypothesis test.
Nothing was tuned: spreads and margin rates are scenario grids, shown side by side. Research only; the choice of
instrument is the owner's policy.

Code: `verify_e2.py`. Numbers: `VERIFY_E2.json` (field paths in brackets). Inputs: the capital study's frozen SPY, SSO
and ledger files (sha256 and git blob checked), plus a new yfinance download of SPY, SSO and UPRO with volume, frozen
with sha256 at first fetch (`.cache/e2verify/MANIFEST.json`). Its daily returns match the frozen files on 100% of
days (largest gap 0.014 bp). The script reproduces the capital study exactly: real-data E2 − margin +0.2352 %/yr,
2006-10 to 2026-11, and +0.2530 %/yr on the fund ledger.

## Verdict

E2 passes all four checks as long as margin really costs about T-bill + 1.5 %/yr or more.
* The 2× fund tracks with a steady drag (about 1.2-1.6 %/yr in normal years). Its large daily misses are closing-price
  timing noise that reverses the next day.
* In stress windows E2 was never materially worse than margin. Its worst gap was 0.04% over a window with daily
  weights, and 0.03% with weekly rebalancing.
* Spread costs are tiny. The break-even quoted spread is about 53 bp; SSO's quoted spread is about 1 bp.
* The edge depends on the margin spread. Below about **1.3-1.4 %/yr over the T-bill**, margin is cheaper. Alpaca's
  published "elite" margin rate (5.00% flat, about T-bill + 1.0% today) is below that line.

## 1. Tracking

Definition: SSO's daily return minus (2 × SPY − T-bill) [`q1_sso_tracking`]. SPY's returns are already net of its fee,
so the comparable assumed drag is 1.20 %/yr.

* **All days, 2006-07 to 2026-11:** drag 1.73 %/yr; tracking sd 3.63 %/yr.
* **By year:** 0.9-1.6 %/yr in 2009-2023. It was higher in 2007 (2.14), 2008 (7.95), 2024 (1.80) and 2025 (2.28).
  The drag rises with interest rates: 1.41 %/yr when the T-bill was under 0.5%, 2.04 %/yr otherwise
  [`q4_financing.sso_drag_by_regime_pct_per_year`]. SSO's swaps pay a spread over the short rate.
* **Tracking sd** is 0.6-1.6 %/yr in calm years. It was 13.8 in 2008, 3.1 in 2020 and 3.0 in 2025.
* **The largest daily misses come in pairs that reverse.** For example, 2008-10-13 was −663 bp, followed by +158 and
  +258 bp. 2020-03-16 was −147, then +163. 2025-04-09 was −225, then +176. These are closing-price timing gaps on days
  when the index moved 10% or more, not lost value. A fund trading at the close still bears them as execution noise.

| Stress window | Days | Drag, %/yr | Drag over window, % | Tracking sd, %/yr | Core days at 1.3 | E2 − margin over window, % (daily weights) | E2 − margin, % (weekly rebalanced) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2008-09 to 2009-03 | 146 | 11.04 | 6.40 | 17.87 | 0% | 0.00 | 0.00 |
| 2010-05 flash crash month | 20 | 1.80 | 0.14 | 1.10 | 75% | −0.005 | −0.017 |
| 2011-08 | 23 | 4.62 | 0.42 | 2.23 | 9% | −0.014 | 0.00 |
| 2015-08 | 21 | 1.75 | 0.15 | 1.30 | 67% | +0.024 | −0.009 |
| 2018-02 Volmageddon | 19 | 4.68 | 0.35 | 1.96 | 100% | −0.040 | +0.016 |
| 2018-Q4 | 63 | 1.57 | 0.39 | 1.57 | 37% | +0.043 | −0.029 |
| 2020-02-19 to 2020-04-30 | 51 | 1.35 | 0.27 | 6.70 | 18% | +0.027 | +0.382 |
| 2022 | 251 | 1.47 | 1.46 | 0.77 | 19% | +0.117 | +0.036 |

Sources: [`q1_sso_tracking.windows`], [`q1_window_E2_vs_M_daily_weights`], [`q1_window_E2_vs_M_weekly_rebalanced`].
"Daily weights" is the capital study's convention. "Weekly rebalanced" uses Thursday decisions, trades at the next
close, and lets every leg drift within the week (`weekly_sim`).

* **The worst SSO episode (2008) never reached the core.** The trend rule was in its 0.7 state for the whole crisis
  window, so E2 held no SSO.
* **On the fund ledger:** E2 − margin was +0.41% over the 2020 window and +0.02% over 2022
  [`c_fund_2020_2025.windows_net_R_2.43`].

## 2. Path and gap risk

**One day held at 1.3** [`q2_path_gap`], close to close:
* On days the core was actually at 1.3, the worst day was −7.51% for E2 against −7.50% on margin (2020-06-11).
* If held at 1.3 on every day, the worst day was −14.67% for E2 against −14.23% on margin (2020-03-16). The core was
  at 0.7 that day.
* E2 trailed margin by more than 25 bp on only 1 of 4,014 days at 1.3: 2009-07-17, −61 bp. That was a timing gap that
  had gone +212 bp the day before.

**Weekly rebalanced, 2006-10 to 2026-11** [`weekly_rebalanced_b`]:
* E2 − margin was +0.26 %/yr (HAC SE 0.04), the same as with daily weights.
* E2's worst week against margin was −32 bp (week from 2007-07-27).
* Its best week was +39 bp (week from 2020-02-21, SPY −11%). Daily reset lowers E2's exposure as the market falls,
  while a margin position's leverage rises.
* Whipsaw weeks cost E2 a few basis points. No week cost more than 0.32%.

**Daily reset made E2 materially worse in no week of 2006-2026** (worst −0.32%). It was worse by more than 0.25% on
one day of 4,014 (−0.61%), and that was a timing gap.

**Gap risk:**
* The worst index day since 1927 was −17.4% (1987-10-19). The modelled 2× fund loses 34.8% that day. The portfolio
  loses 1.3 × 17.4% in either arm.
* SSO is wiped out only by a one-session index fall of 50% or more. In that case E2 loses at most what it holds,
  while margin keeps losing beyond it.
* **Not modelled:**
  * intraday risk (SSO's intraday leverage drifts, and the core has no intraday stops);
  * the fund trading at a premium or discount to NAV (+0.07% on 2026-11-23, from the ProShares NAV $61.11 and market
    price $61.15);
  * swap-counterparty risk and the risk the fund is closed;
  * market-closure gaps.

## 3. Transaction costs

**Liquidity and spread:**
* **SSO, from ProShares** (read directly, fetched 2026-11-24, page text summarised by the fetch tool):
  * "30-Day Median Bid Ask Spread" 0.01% as of 11/23/2026; one cent at $61.15 is 1.6 bp;
  * "Trading Volume" 8.8 million shares on 11/23/2026;
  * "Net Assets" $6.36 billion;
  * "Net Expense Ratio" 0.84% with a contractual waiver to 2027-09-30, gross 0.88%. The capital study assumed 0.89%.
* **Dollar volume from yfinance**, 63 sessions to 2026-11-23 [`liquidity_yfinance`]: median $252 million a day for
  SSO, against $32.7 billion for SPY.
  * A 0.3 × NAV trade stays under 1% of SSO's daily volume for a fund under about $8 million, and under 10% up to
    about $80 million. Market impact is negligible at the fund's size.

**Extra trading** [`weekly_rebalanced_b.costs`], weekly rebalancing to target:
* Margin trades 2.07 × NAV of SPY a year: weekly drift plus 0.6 per trend switch.
* E2 trades 0.98 × NAV of SSO and 0.22 of SPY a year: 1.20 in all, against 2.07. A trend switch moves 0.3 SSO
  instead of 0.6 SPY, but SSO drifts more within the week and needs more top-ups.
* The ledger gives the same picture: 0.93 SSO and 0.30 SPY against 2.07 SPY [`c_fund_2020_2025.turnover_2.43`].
* The capital study's 2 bp-per-unit switching charge is kept identical in both arms. The costs below come on top of
  it, at half the quoted spread (SPY at 0.2 bp).

| SSO full quoted spread | 1 bp | 2 bp | 5 bp | 10 bp | 20 bp |
|---|---:|---:|---:|---:|---:|
| Extra cost, %/yr, 2006-2026 | 0.003 | 0.008 | 0.023 | 0.047 | 0.096 |
| Extra cost, %/yr, fund ledger 2020-2025 | 0.003 | 0.008 | 0.021 | 0.045 | 0.091 |

* **Break-even full spread:** 53 bp on 2006-2026 and 55 bp on the ledger. That is about 50 times today's quoted
  spread.

## 4. Financing

The E2 − margin difference by margin spread over the T-bill, in %/yr (HAC SE in brackets). It is computed with daily
weights on real SPY and SSO [`q4_financing.daily_weights_b`] and on the fund ledger [`c_fund_2020_2025`].

| Margin spread | 1.0% | 1.5% | 2.43% | 3.0% |
|---|---:|---:|---:|---:|
| 2006-10 to 2026-11, all days | −0.11 (0.05) | +0.01 (0.05) | +0.24 (0.05) | +0.37 (0.05) |
| T-bill < 0.5% | −0.05 (0.07) | +0.07 (0.07) | +0.30 (0.07) | +0.43 (0.07) |
| T-bill ≥ 0.5% | −0.16 (0.07) | −0.04 (0.07) | +0.17 (0.07) | +0.31 (0.07) |
| 2006-10 to 2008-12 (T-bill 3.1%) | −0.26 (0.26) | −0.19 (0.26) | −0.05 (0.26) | +0.04 (0.26) |
| 2009-2015, zero rates | −0.04 (0.09) | +0.08 (0.09) | +0.31 (0.09) | +0.45 (0.09) |
| 2016-2019 | −0.11 (0.07) | +0.02 (0.07) | +0.27 (0.07) | +0.42 (0.07) |
| 2020-03 to 2022-03, zero rates | −0.10 (0.06) | +0.03 (0.06) | +0.27 (0.06) | +0.42 (0.06) |
| 2022-03 to 2026-11 (T-bill 4.1%) | −0.13 (0.04) | −0.01 (0.04) | +0.21 (0.04) | +0.34 (0.04) |
| Fund ledger 2020-2025, net debit | −0.06 (0.08) | +0.05 (0.08) | +0.25 (0.08) | +0.38 (0.08) |
| Fund ledger, segregated short proceeds | −0.05 (0.08) | +0.07 (0.08) | +0.29 (0.08) | +0.42 (0.08) |

* **Break-even margin spread:**
  * 1.44 %/yr over 2006-2026: 1.21 at near-zero rates, 1.69 otherwise
    [`q4_financing.break_even_margin_spread_pct_daily_weights_b`];
  * 1.29 %/yr on the fund ledger [`c_fund_2020_2025.break_even_margin_spread_pct`].
* **The edge does not vanish at near-zero rates; it is slightly larger there.** SSO's own financing drag is lower when
  rates are low (1.41 against 2.04 %/yr).
* **What matters is the margin spread the broker actually charges.** Alpaca's margin documentation (search summary,
  not opened) lists a flat 5.00 %/yr for "elite" users and 6.50 %/yr for others; another Alpaca page shows 6.25%.
  Against a T-bill of about 4.0% (DTB3, October 2026):
  * "elite" is about T-bill + 1.0%, where E2 loses about 0.1 %/yr;
  * the other rates are T-bill + 2.2-2.5%, where E2 gains about 0.2 %/yr.
  * A flat rate is a much wider spread when the T-bill is near zero, which would widen E2's edge in that regime.
  * The interactivebrokers.com margin-rates page did not load (HTTP 403).
* **Margin requirement.** FINRA Regulatory Notice 09-53 (search summary, not opened) scales maintenance margin on
  leveraged ETFs by their leverage: 50% for a 2× long position. So 0.3 SSO needs the same maintenance as 0.6 SPY.
  E2 lowers market-value gross, which is what the fund's 1.9× cap counts. It does not lower the broker's maintenance
  requirement or the risk. Check the broker's house rule before relying on the freed gross.

## 5. Alternative: UPRO (3×) for the excess

E3 holds 0.85 SPY + 0.15 UPRO in up-trends, which also has 1.0 of gross. This is descriptive only; UPRO data start
2009-06-25.

* **Tracking against 3 × SPY − 2 × T-bill** [`q5_upro_tracking`]:
  * drag 2.11 %/yr and tracking sd 2.98 %/yr, against SSO's 1.40 and 1.70 on the same days;
  * 3.78 %/yr in 2025;
  * stress windows: 1.48% over 2018-02 and 1.03% over the 2020 window.
* **Against margin, at 2.43%:**
  * daily weights, 2009-2026: E3 +0.38 %/yr against E2 +0.28; E3 − E2 = +0.10 (SE 0.04)
    [`q5_daily_weights_upro_sample`];
  * weekly rebalanced: +0.38 against +0.28 [`weekly_rebalanced_upro_sample`];
  * fund ledger: +0.36 (SE 0.11) against +0.25 [`c_fund_2020_2025.0.0243.E3_net_R`].
  * The gain comes from paying the fund's drag on 0.15 of NAV instead of 0.3.
* **Costs:** "30-Day Median Bid Ask Spread" 0.03% (ProShares, read directly, 11/23/2026). Break-even spread 139 bp.
* **Weaknesses:**
  * Its worst stress window against margin was −0.16% (2018-02), four times E2's −0.04%.
  * Break-even margin spread 0.81 %/yr on the ledger; 0.49 at near-zero rates.
  * A one-session index fall of 33% wipes UPRO out. That is closer to history (−17.4% in 1987) than SSO's 50%.
  * Maintenance margin is 75%.

## Conditions under which E2 should not be used

1. **When the broker's margin rate is under about T-bill + 1.3-1.4 %/yr.** Then plain margin is cheaper (break-even
   1.29 on the ledger, 1.44 on 2006-2026). Check the account's actual rate tier. Alpaca's "elite" 5.00% is about
   T-bill + 1.0% today.
2. **When SSO's quoted spread is wider than about 50 bp,** or the fund trades it at a premium to NAV. Then trading
   costs consume the edge. Watch for spreads widening at the close.
3. **When freed gross is assumed to free broker margin.** Maintenance on SSO is 2 × 25%. The 1.9× cap relief is a
   market-value relief only.
4. **When SSO's drag over 2 × SPY − T-bill runs persistently above the margin spread** (2008: 7.95; 2025: 2.28;
   about 1.4 %/yr on the days E2 held SSO in 2006-2026). The edge is about 0.3 × share of up-trend days × (margin
   spread − SSO drag on those days). Recheck it yearly on the fund's own fills.
5. **When the fund would hold SSO through a closure, a counterparty event, or a one-session fall near 50%.** None of
   this is modelled; intraday risk is not modelled either.
6. **Not as a reason to hold the whole core in the 2× fund.** That arm (E1) loses 0.33-0.38 %/yr against margin
   (capital study).
7. **UPRO is not the default.** It earned +0.10 %/yr more on seen data. But it has a lower break-even margin spread
   (0.81), wipes out at a 33% fall, and had a worse stress window. Any switch would be the owner's call, on forward
   records.

**Not checked here:** real fills against modelled closes, and Alpaca's house margin on leveraged ETFs. Both should be
read from the paper account's first weeks before real money.
