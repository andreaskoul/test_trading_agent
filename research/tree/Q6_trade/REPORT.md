# Branch Q6_trade (Layer 3, Amendment 8): trading less, under a square-root cost model

*Written by the branch agent; saved by the coordinating session because the agent's writes were refused.
**Development data only** (S&P 500 2013-2019, 352 scored weeks); not out of sample. 27 configurations (9
constructions × trees, IPCA, MASTER) declared before scoring; T7 (JKMP-style direct optimisation) not run; no other
tuning.*

**Verdict.** On trees, no registered rule beats the C2 control (`mvnl_nt`, net Sharpe 0.70 under the square-root model
at $10M). Best candidate: rank hysteresis T1 (enter at the 10% tails, exit outside 30%), 0.45 vs the C1 band's 0.38
(+0.34 %/yr, NW t 0.90; vol-matched +0.49, t 1.31); drawdown 14.3% vs 16.1%; turnover 17%/week vs 26%; keeps 0.34 at
$100M where C1 falls to 0.19 and deciles to −0.19. Behind C2 vol-matched (−1.41 %/yr, t −0.55). Hysteresis also helps
IPCA (T3 0.53 vs 0.39; best t 1.35). Every MASTER book is negative. Gârleanu-Pedersen partial trading (T4-T6) fails on
all three signals. Nothing significant; nothing nominated.

## Cost model (`lib.py`; `test_cost.py`, all pass)

Per name and week, fraction of AUM: `cost_i = |dw_i| (HS + K σ_i √(|dw_i| AUM / ADV_i))`.

* **HS = 2.3 bp**: mean quoted S&P 500 half-spread at 15:59 ET (`COST_STUDY.json`).
* **K = 0.5**, fixed before scoring, on daily total-return vol σ_i (past 60 sessions). JKMP anchor (via `L3_lit`): 1%
  of daily dollar volume costs 0.1% (Λ = 0.2/V); a square-root law through that point at 2% daily vol gives
  K = 0.001 / (0.02 × 0.1) = 0.5. Frazzini-Israel-Moskowitz check (via `L3_lit`): average large-cap impact 11.2 bp ≈
  K 0.5 at 1.5% vol and ~2% of ADV. Sensitivity K = 1.0 from Goyal-Jegadeesh-Wu (17.7 bp at 1% of ADV, via `L3_lit`),
  reported, not used for choosing. Literature numbers as read in-project, not re-checked here.
* **AUM** $10M per book (headline), $100M sensitivity; flat 5 bp also reported.
* **ADV — departure from the registration's wording.** FINRA `total` is off-exchange *share* volume and the panel has
  no price levels, so it cannot give dollar ADV. ADV_i = median past-20-session consolidated dollar volume from Yahoo
  split-adjusted close × split-adjusted volume (`fetch_dv.py`; request ends 2019-12-31; the split factor cancels).
  Content contract: kept only if Yahoo's daily return is within 1 pp of the panel's on ≥ 95% of sessions; 472 of 474
  pass. Fallback (CTVA, DOW; 63 name-weeks): FINRA shares × the day's cross-sectional median dollars per FINRA share.
  FINRA/consolidated share volume: median 0.22-0.25 by year, upper quartile 0.27-0.31 (names with no later split), so
  consolidated ≈ 3-4× FINRA. Median eligible ADV $151M (10th-90th $54M-$580M).
* **Tests (synthetic)**: zero trade → zero cost; held book pays only on entry; 4× trade → 2× impact per unit (8× total);
  impact per unit ∝ √(AUM/ADV); half-spread linear; 1% of ADV at 2% vol → 10 bp impact; net = gross − spread − impact.
* **Checks (flat 5 bp)**: C1 trees 0.346 (Q4 0.35); C2 trees 0.635 (Q4 0.64).

## Constructions (data ≤ t; y5 beta-hedged; SPY hedge not charged)

C0 deciles; C1 M1 band 0.1 (enter 10%, exit past 20%); C2 Q4 `mvnl_nt` (LW2020 mean-variance, dollar- and beta-
neutral, L1 no-trade k 2); T1 hysteresis (enter 10%, exit outside 30%); T2 deciles on rank(r_t + 0.5 r_{t−1}) (r =
centred rank; r_t alone without last week's); T3 = T1 on the T2 score; T4-T6 partial trading x_t = x_{t−1} +
θ_i(aim_t − x_{t−1}), aim = Q4's LW2020 target, θ_i = clip(θ √(ADV_i / median ADV), 0.05, 1), θ ∈ {0.25, 0.5, 0.75}
(stated before scoring: GP's rate ≈ √(γ/λ_i), λ_i ∝ 1/ADV_i), re-projected dollar- and beta-neutral at gross 1.

## Results

Net under the square-root model at $10M unless marked. "vs C1/C2": paired weekly net difference %/yr (NW t, 4 lags).
"vm": weights scaled to C1's vol and re-simulated (bigger book pays more impact); for "vs C2 vm" both at C1's vol.
"DD@C1": max drawdown of the vm series.

| config | net Sh | net %/yr | $100M Sh | flat 5bp Sh | K=1 Sh | gross Sh | turn/wk | vol | maxDD | DD@C1 | vs C1 | vs C1 vm | vs C2 | vs C2 vm | 13–16 | 17–19 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C0_trees | 0.16 | 1.12 | −0.19 | 0.14 | 0.00 | 0.48 | 45% | 6.9 | 19.1% | 17.6% | −1.27 (−2.64) | −1.32 (−2.95) | +0.15 (0.06) | −3.22 (−1.29) | 0.11 | 0.24 |
| C1_trees | 0.38 | 2.39 | 0.19 | 0.35 | 0.29 | 0.56 | 26% | 6.4 | 16.1% | 16.1% | – | – | +1.42 (0.61) | −1.90 (−0.75) | 0.24 | 0.60 |
| C2_trees | **0.70** | 0.97 | 0.65 | 0.64 | 0.68 | 0.79 | 4% | 1.4 | 2.7% | 12.0% | −1.42 (−0.61) | +1.90 (0.75) | – | – | 0.37 | 1.13 |
| **T1_trees** | **0.45** | 2.73 | 0.34 | 0.43 | 0.40 | 0.57 | 17% | 6.0 | 14.3% | 15.0% | +0.34 (0.90) | +0.49 (1.31) | +1.77 (0.79) | −1.41 (−0.55) | 0.27 | 0.75 |
| T2_trees | 0.33 | 2.19 | 0.07 | 0.31 | 0.21 | 0.56 | 32% | 6.7 | 17.4% | 16.5% | −0.20 (−0.39) | −0.30 (−0.63) | +1.22 (0.49) | −2.20 (−0.85) | 0.19 | 0.56 |
| T3_trees | 0.42 | 2.50 | 0.34 | 0.40 | 0.39 | 0.51 | 12% | 5.9 | 13.6% | 14.6% | +0.10 (0.17) | +0.29 (0.47) | +1.53 (0.69) | −1.61 (−0.61) | 0.24 | 0.74 |
| T4_trees (θ .25) | 0.17 | 0.22 | 0.08 | −0.03 | 0.13 | 0.41 | 11% | 1.3 | 3.4% | 15.7% | −2.17 (−0.88) | −1.64 (−0.53) | −0.74 (−1.52) | −3.54 (−1.55) | 0.27 | 0.04 |
| T5_trees (θ .5) | 0.22 | 0.28 | −0.02 | −0.13 | 0.11 | 0.71 | 21% | 1.3 | 3.2% | 16.5% | −2.11 (−0.88) | −1.87 (−0.64) | −0.69 (−1.47) | −3.77 (−1.68) | 0.22 | 0.21 |
| T6_trees (θ .75) | 0.22 | 0.28 | −0.17 | −0.21 | 0.04 | 0.91 | 28% | 1.3 | 3.2% | 17.1% | −2.11 (−0.88) | −2.38 (−0.81) | −0.69 (−1.38) | −4.28 (−1.81) | 0.19 | 0.25 |
| C0_ipca | 0.23 | 1.54 | −0.20 | 0.22 | 0.03 | 0.61 | 50% | 6.7 | 13.2% | 12.4% | −0.88 (−1.69) | −0.94 (−1.93) | +1.09 (0.51) | −0.04 (−0.02) | 0.05 | 0.45 |
| C1_ipca | 0.39 | 2.42 | 0.12 | 0.36 | 0.27 | 0.64 | 34% | 6.2 | 11.7% | 11.7% | – | – | +1.96 (1.00) | +0.89 (0.43) | 0.33 | 0.46 |
| C2_ipca | 0.27 | 0.45 | 0.21 | 0.20 | 0.24 | 0.39 | 6% | 1.7 | 3.8% | 13.8% | −1.96 (−1.00) | −0.89 (−0.43) | – | – | −0.09 | 0.80 |
| T1_ipca | 0.43 | 2.56 | 0.25 | 0.40 | 0.35 | 0.62 | 24% | 5.9 | 10.1% | 10.7% | +0.14 (0.29) | +0.27 (0.55) | +2.11 (1.13) | +1.17 (0.56) | 0.43 | 0.44 |
| T2_ipca | 0.49 | 3.27 | 0.18 | 0.48 | 0.35 | 0.77 | 38% | 6.7 | 14.3% | 13.3% | +0.85 (1.35) | +0.67 (1.14) | +2.82 (1.31) | +1.56 (0.75) | 0.51 | 0.47 |
| T3_ipca | 0.53 | 3.11 | 0.40 | 0.50 | 0.47 | 0.66 | 18% | 5.9 | 10.9% | 11.4% | +0.69 (0.81) | +0.84 (0.96) | +2.65 (1.39) | +1.74 (0.85) | 0.55 | 0.48 |
| T4_ipca (θ .25) | 0.18 | 0.47 | 0.11 | 0.07 | 0.15 | 0.34 | 13% | 2.6 | 4.8% | 11.2% | −1.95 (−0.95) | −1.39 (−0.57) | +0.02 (0.02) | −0.49 (−0.20) | −0.40 | 0.65 |
| T5_ipca (θ .5) | −0.08 | −0.11 | −0.37 | −0.44 | −0.21 | 0.48 | 25% | 1.4 | 3.7% | 18.1% | −2.53 (−1.24) | −3.82 (−1.70) | −0.56 (−1.11) | −2.93 (−1.44) | −0.55 | 0.61 |
| T6_ipca (θ .75) | −0.19 | −0.26 | −0.68 | −0.65 | −0.41 | 0.63 | 34% | 1.4 | 4.0% | 22.3% | −2.67 (−1.29) | −5.18 (−2.06) | −0.71 (−1.21) | −4.29 (−1.79) | −0.67 | 0.46 |
| C0_master | −0.26 | −1.73 | −0.74 | −0.27 | −0.48 | 0.15 | 53% | 6.6 | 23.2% | 21.5% | −1.63 (−2.89) | −1.45 (−2.68) | −1.60 (−0.76) | −0.80 (−0.32) | −0.27 | −0.26 |
| C1_master | −0.02 | −0.10 | −0.33 | −0.05 | −0.16 | 0.28 | 38% | 6.1 | 17.5% | 17.5% | – | – | +0.03 (0.01) | +0.65 (0.26) | −0.16 | 0.20 |
| C2_master | −0.09 | −0.13 | −0.16 | −0.18 | −0.12 | 0.06 | 7% | 1.5 | 3.8% | 14.8% | −0.03 (−0.01) | −0.65 (−0.26) | – | – | −0.05 | −0.13 |
| T1_master | −0.06 | −0.33 | −0.30 | −0.09 | −0.17 | 0.18 | 29% | 5.7 | 17.9% | 19.1% | −0.23 (−0.61) | −0.28 (−0.71) | −0.20 (−0.10) | +0.37 (0.14) | −0.34 | 0.35 |
| T2_master | −0.13 | −0.91 | −0.48 | −0.14 | −0.29 | 0.17 | 41% | 6.8 | 23.1% | 20.8% | −0.81 (−0.99) | −0.66 (−0.91) | −0.79 (−0.34) | −0.01 (−0.00) | −0.20 | −0.03 |
| T3_master | −0.19 | −1.10 | −0.35 | −0.22 | −0.26 | −0.02 | 23% | 5.9 | 21.2% | 21.8% | −1.00 (−1.18) | −1.05 (−1.20) | −0.97 (−0.46) | −0.39 (−0.15) | −0.32 | −0.00 |
| T4_master (θ .25) | 0.00 | 0.01 | −0.06 | −0.08 | −0.03 | 0.13 | 13% | 3.2 | 6.6% | 12.4% | +0.11 (0.06) | +0.05 (0.02) | +0.14 (0.12) | +0.70 (0.27) | −0.50 | 0.30 |
| T5_master (θ .5) | −0.45 | −0.74 | −0.70 | −0.76 | −0.56 | 0.04 | 25% | 1.7 | 6.7% | 24.4% | −0.64 (−0.36) | −3.26 (−1.84) | −0.61 (−1.07) | −2.61 (−1.18) | −0.58 | −0.28 |
| T6_master (θ .75) | −0.52 | −0.83 | −0.95 | −0.92 | −0.72 | 0.19 | 34% | 1.6 | 6.8% | 27.8% | −0.74 (−0.40) | −4.20 (−2.29) | −0.71 (−1.17) | −3.55 (−1.48) | −0.53 | −0.51 |

## Findings

* **At $10M, S&P 500 names under the square-root model cost about flat 5 bp**: C1 trees pays 1.19 %/yr (half spread,
  half impact), Sharpe 0.38 vs 0.35 flat. At $100M the band's impact triples (0.55 → 1.75 %/yr), Sharpe halves to
  0.19, deciles go negative (−0.19).
* **Rank hysteresis is the only rule that helps on two signals**: trees T1 cuts turnover by a third (26% → 17%) with no
  gross loss (0.57 vs 0.56) and keeps 0.34 at $100M; IPCA T3 0.53 vs 0.39. Not significant (best t 1.31 trees, 1.35
  IPCA). Larger in 2017-19 than 2013-16, as for every control.
* **Signal decay alone does not cut cost on trees** (turnover 32% vs 45%, net 0.33 < C1's 0.38; the trees score is
  already persistent, autocorrelation ~0.8 per Q5). On IPCA decay lifts gross to 0.77 and wins at $10M but loses at
  $100M (0.18).
* **Gârleanu-Pedersen partial trading fails** on every signal and θ (best trees 0.22; vs C2 t −1.4 to −1.5): small θ
  holds a stale book (gross 0.41 at θ .25); large θ recovers gross (0.91 at θ .75) but pays the trading. The L1 no-trade
  region (C2) is the better way to trade the mean-variance book (4%/week, gross 0.79).
* **C2 stays best on trees but does not carry over**: trees 0.70, 0.65 at $100M, 12.0% drawdown at C1's vol (needs
  4.6× gross to match, charged in vm); IPCA behind the band (0.27 vs 0.39; 2013-16 −0.09); MASTER all negative.
* **MASTER**: gross Sharpe 0.06-0.28 for every construction; nothing turns it positive.

## Best

Registered rule (highest net Sharpe at $10M, drawdown no worse than C1) among candidates on the primary signal:
**T1_trees** (`model.py`, `build_weights`; `python model.py` → `ok: True`, net Sharpe 0.4536). The control C2_trees
scores higher (0.70) but is not a candidate.

## Caveats

* Development results; signals selected on these years; with 27 rows a best paired t of ~1.3 is within the expected
  null maximum.
* Survivorship gap (241 of 738 names unpriced; 23.5% of eligible name-weeks without a target); delisting losses
  absent; candidates and controls share it.
* S&P 500 costs are far below the broad universe's (half-spread 2.3 vs 6.4 bp, 9.4 in its smallest third; much lower
  ADV), so savings here **understate** those on the broad book; the $100M column is the closer guide.
* ADV from Yahoo consolidated dollar volume (a new fetch, departing from the registered FINRA proxy, for the reason
  above); K a literature constant, not estimated on fills; SPY hedge and borrow costs not charged.
* No tuning: GP scaling and 10%/30% hysteresis widths fixed before scoring.

Files: `fetch_dv.py`, `lib.py` (`simulate_sqrt`, constructions, metrics), `test_cost.py`, `run.py`, `run.log`,
`model.py`, `RESULTS.jsonl` (27 rows), `STATE.json`. Weekly nets: `.cache/tree/preds/Q6_trade/<name>.npy` ($10M) and
`<name>_all.npz` ($100M, flat 5 bp, gross). Dollar volume: `.cache/tree/q6_dv.npz`.
