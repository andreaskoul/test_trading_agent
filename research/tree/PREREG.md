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
