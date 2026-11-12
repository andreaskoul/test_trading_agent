# Tree search over stock-selection models: protocol and pre-registration

*Written 2026-11-10, before any agent has run. Owner's brief (2026-11-10): explore the limits of mathematics, model
design and network design with several agents, as a tree search that explores and then exploits. Research only;
nothing in the traded fund changes.*

## 1. The problem a search creates, and the guard against it

A search over many models picks the luckiest one. On 353 development weeks, the standard error of a mean weekly rank
IC is about 0.01, so differences below 0.01 between models are noise. The guard is a holdout no agent can reach:

* **Development sample:** S&P 500 members, daily, 2009-01 .. 2019-12-31 (`.cache/tree/dev.npz`, built from the
  `research/quant_trials` panel). The file contains nothing after 2019.
* **Holdout:** 2020-01 .. 2025-12. Read once, by the coordinating session only, for at most three finalists.
* **Disclosure.** 2020–2025 is known in aggregate (momentum and volatility tilts did well; the MASTER 5-day model's
  results there are known). A new model's predictions there have not been seen. Forward weeks remain the only clean
  confirmation.

## 2. The task and the metric

Predict the cross-section of 5-session hedged returns entered at the next close (`y5`). Interface and rules: the
docstring of `harness.py`. Development metric: mean weekly Spearman IC on the Thursdays of 2013–2019, walk-forward
(each validation year predicted by a model fitted only on rows whose target ended before that year), ranks averaged
over 3 seeds; also IC by year and a decile spread net of 5 bp a side.

References on the development sample: ridge on the five characteristics, IC −0.002 (t −0.2); the MASTER 5-day model as
scored in October, IC 0.0125 (t 1.43).

## 3. The search

* **Round 1, explore (five branches, one agent each):** A loss mathematics; B network architecture; C features and
  econometrics; D trees, ensembles and stacking; E regime-adaptive models.
* **Round 2, exploit:** the two or three branches with the best development evidence are refined and combined.
* Every configuration scored is appended to the branch's `RESULTS.jsonl`. The total count is reported with the result.
* Budget per agent: about 15 configurations, each fit within about 6 minutes on 2 CPU threads.

## 4. Finalists and the one read

* **Finalists (at most three),** chosen by the coordinating session after round 2: the highest development IC t among
  configurations with a positive IC in at least 5 of the 7 years, at most one per branch.
* **Holdout run:** the finalist's `fit_predict`, annual refits 2020..2025 on the full panel, 3 seeds.
* **Tests (`READ.lock`):** for each finalist, (i) mean weekly IC > 0 (t with Newey–West, 4 lags), one-sided; Holm
  across the finalists at α = 0.05; (ii) reported, not tested: IC against the MASTER 5-day model's on the same weeks,
  the decile spread net of 5 bp, IC by year.
* **Consequences.** A finalist that passes (i): propose one forward paper book (research only). None passes: the
  search is closed on this panel and its count of configurations is recorded as the price of the null.

## 5. Not claimed

Nothing found on the development sample is evidence. A holdout pass is evidence for a forward test, not for trading.

## Amendment 1 (2026-11-12, before any holdout data is read): finalists

**Search size.** Round 1: 60 configurations (A 12, B 11, C 15, D 7, E 15). Round 2: X1 11, X2 11, X3 32 (14
online/yearly pairs and 4 staleness diagnostics). Total 114 logged configurations.

**Finalists by the §4 rule** (highest development IC t with a positive IC in at least 5 of 7 years, one per branch):

| Finalist | Branch | Development IC | t |
|---|---|---:|---:|
| X1_8p: D trees + C ridge + MLP, 4 horizons each, panic overlay | X1 | 0.0282 | 2.91 |
| A_mse_rank: MLP on ranked targets | A | 0.0188 | 2.45 |
| D_hgb_mh: boosted trees, 4 horizons | D | 0.0236 | 2.41 |

**One departure, disclosed.** The second-highest t (2.47) belongs to an X3 row that its agent labelled a post-hoc
diagnostic, "not proposed as a model": the same linear model run with a deliberate one-year extra lag. It is excluded
as not a candidate. The X2 row with t 2.41 is the same model as D_hgb_mh, reproduced; D's is used.

**Code check before the read.** Each finalist's `model.py` (`research/tree/finalists/`) must reproduce its logged
development IC to four decimals (`verify.py`, results in each `VERIFY.json`). A finalist that does not reproduce is
dropped, not repaired.

**Reported beside the registered tests** (not tested): each finalist's decile spread with the X2 score smoothing
(exponential, half-life 1 week, over the current and 12 preceding Thursdays), since branch X2 showed smoothing cuts
costs without lowering IC on the development sample.

## Result of the holdout read (2026-11-12, `HOLDOUT_RESULT.json`, `HOLDOUT_SMOOTHED.json`; 303 weeks, 2020-01 .. 2025-12)

| Finalist | IC | Newey–West t | one-sided p | Holm (α 0.05) | IC by year 2020 → 2025 | IC minus MASTER (t) |
|---|---:|---:|---:|---|---|---:|
| X1_8p combined | 0.0224 | 2.11 | 0.0173 | **fails** (needs 0.0167) | .035 .005 .023 .014 .026 .031 | −0.010 (−0.86) |
| D_hgb_mh trees | 0.0185 | 1.89 | 0.0293 | fails | .027 .001 .035 .002 .015 .031 | −0.014 (−1.21) |
| A_mse_rank MLP | 0.0078 | 0.79 | 0.2162 | fails | .017 −.015 .012 −.004 .031 .006 | −0.025 (−1.87) |
| MASTER 5-day (reference, already seen) | 0.0326 | 3.14 | | | | |

Reported, not tested: decile spread net of 5 bp a side, raw and with the X2 smoothing (half-life 1 week).

| | raw % a year (Sharpe) | smoothed % a year (Sharpe) |
|---|---:|---:|
| X1_8p | +2.6 (0.27) | +4.7 (0.53) |
| D_hgb_mh | +2.0 (0.22) | +2.8 (0.33) |
| A_mse_rank | −3.7 (−0.41) | −0.1 (−0.02) |

**Consequence as registered: no finalist passes; the search is closed on this panel.** It cost 114 logged
configurations. The best search model missed the Holm bar narrowly (p 0.0173 against 0.0167) and was positive in all
six holdout years, but it is below the MASTER 5-day model on the same weeks, which therefore remains the project's best
stock-selection model. Development leads of about +0.01 IC over MASTER did not survive the holdout: they reversed to
−0.010 to −0.025, the size of selection bias the protocol warned of (§1).
