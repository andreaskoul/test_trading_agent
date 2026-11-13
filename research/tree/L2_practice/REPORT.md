# L2: practitioner survey — exploiting the broad trees book and the combined fund

*An in-project survey by a separate AI session (2026-11-13), saved by the coordinating session. Not an outside review.
Access: [RD] read directly; [SS] search summary only (numbers secondary); [R] the agent's reasoning. Forum and blog
numbers are anecdotal single runs on other data: none is evidence of an effect size for us.*

## 1. Practices

| # | Practice | Sources (access) | Claimed effect (credibility) | Application here |
|---|---|---|---|---|
| 1 | Partial neutralisation of predictions per date: `scores -= p * exposures @ pinv(exposures) @ scores`, rescale | forum.numer.ai /t/899, /t/7486, /t/4955 [RD]; docs.numer.ai FNC [SS] | Example model, validation: correlation 0.0291 → 0.0255, validation Sharpe 0.9608 → 1.2436; "proportion of 0.5 … boosted val SR ~1.7"; bias rises and variance falls with p, sweet spot "around p = 0.5"; "Neutralizing linear models makes them worse". Low-medium (single validation splits, obfuscated features, tuned p) | Per-era correlation = our weekly rank IC. Neutralise the weekly score against a declared set (beta, size/dollar volume, vol, maybe industry) at p 0.5 vs 0; judge on the net decile book, not IC |
| 2 | Industry (sub-industry) neutralisation | WorldQuant BRAIN third-party guides [SS]; Blitz-van der Grient-Honarvar 2023 via Quantpedia [SS], Robeco summary [RD] | Reversal "can be revived by counteracting its conflicting tendencies with short-term industry and factor momentum"; "Enhanced reversal strategies offer double the risk-adjusted return" (no baseline or costs on the page). Low-medium (SSRN 4575689 not opened) | Industry-adjusted reversal + short-term industry momentum features; or an industry-neutral final step |
| 3 | Ensembles across target variants | forum.numer.ai /t/5842 [RD]; Volkova Jane Street 2024 solution.md [RD] | Equal-weight ensemble on two targets "tends to improve both portfolio return and Sharpe ratio" (no numbers); auxiliary targets "+0.001" CV/LB. Low-medium | We average horizons; not yet tried: targets differing in neutralisation (raw, beta-hedged, industry+beta residual, vol-scaled) |
| 4 | Tail weighting | docs.numer.ai CORR [RD]; Jane Street 2021 winner quoted on /t/4338 [RD] | CORR uses power 1.5 "to accentuate the tails"; sample-weight training "gives a boost". Low (design choices) | Weight training rows by target tail; declare a tail-IC development metric for the decile book |
| 5 | Era boosting | forum.numer.ai /t/189 [RD] | In-sample Sharpe 21.99 ("absolutely an overfit"); out of sample 0.037 / Sharpe 1.43 vs regular 0.036 / 1.49. Evidence against | Not recommended |
| 6 | Online / frequent refitting | Volkova solution.md [RD] | Online update "+0.008" CV vs best single 0.0105; "MLP, time-series transformers, cross-symbol attention, and embeddings" did not work. Medium-low (intraday, CV only) | Weekly refits of the trees; expect far less on weekly data |
| 7 | Rank hysteresis (buy/hold spread) | Quantpedia short-term reversal [RD]; de Groot-Huij-Zhou JBF 2012 [SS]; Qlib TopkDropout [SS]; Novy-Marx-Velikov [SS] | Net "30 to 50 bp per week" for large caps with lower-turnover construction; hold until the stock leaves the top/bottom half; "turnover and trading costs … more than halve" [SS]. Medium (peer-reviewed, replicated) | Not the weight band that failed: enter at decile 1/10, exit only past a looser rank threshold |
| 8 | No-trade region: trade to the band edge; widen beyond the backtest optimum | Robot Wealth no-trade-region post [RD]; Martin-Schöneborn arXiv 1103.4934 [SS] | ETF example Sharpe ~0.7 → ~0.9, turnover one-tenth; widen by "a quarter to a half"; width ∝ cost^(1/3) [SS]. Low for us | May explain the band's OOS failure (too tight; trading to target, not edge) [R]; no re-tuning on spent data |
| 9 | Signal decay (smoothing) | WorldQuant guides [SS]; Kakushadze, 101 Formulaic Alphas, arXiv 1601.00991 [RD] | Holding 0.6-6.4 days; pairwise correlation 15.9%; returns depend on volatility, not turnover. Low-medium | Blend this week's score with last week's (d 0.5-1) |
| 10 | Universe and liquidity decide reversal's net result | Quantpedia [RD]; Alpha Architect [SS]; closing-auction impact [SS] | Weekly long/short net of costs: 1,500 stocks −31.4 bp/wk, 500 stocks +10.6, 100 stocks +29.0; drag "largely driven by excessive trading in small-cap stocks"; STREV cost 1.94%/month subsumes gross; Blitz et al. 2022 composite gross alpha >12%/yr, costs ate much; auction impact ex-microcaps "9 to 21 bps" [SS]. Medium | Our smallest third (IC .032, 9.4 bp): cost-aware per-name filter; check cost model against auction impact, not half-spread alone |
| 11 | Execution delay and MOC | Concretum post [RD]; QuantConnect, r/quant [SS] | SPY mean reversion: close 31 bp/trade, 15:45 signal + MOC 27 bp, next open 22 bp. Low as size, medium as direction | Audit the broad book's assumed fill vs live; T−60 s checked for S&P only |
| 12 | Reading competition winners | JPX 1st README [RD]; G-Research wrap-up [RD] | JPX 1st = LinearRegression on raw OHLCV; G-Research top 3 LightGBM; leaderboards "many big jumps and precipitous drops". High confidence in the lesson | Mechanisms and validation hygiene only (e.g. 200-date gap), never effect sizes |

## 2. Ranked testable changes

DEV = S&P 500 2013-2019 (survivorship gap); FWD = forward weeks; broad 2017-2025 and S&P 500 2020-2025 spent; 2026
reserved for H7. Power note [R]: per-week IC sd ≈ 0.12, so 52 forward weeks give an IC standard error ≈ 0.017; forward
weeks can verify turnover and realised cost (nearly mechanical), not IC changes. DEV is large caps: cost effects do not
carry over; a DEV pass is necessary, not sufficient.

1. **Rank hysteresis for the broad decile book**: enter decile 1/10, hold until outside a declared wider band (e.g.
   30%), no grid. Control: weekly decile rebuild. DEV (gross loss) + FWD (turnover, cost). Pass rule declared in
   advance (turnover cut ≥ X, gross loss ≤ Y). Risk medium (resembles the failed band).
2. **Signal decay**: score_t = rank(s_t + 0.5 s_{t−1}), d fixed. Control: current score. Test with 1 as a declared 2×2.
3. **Partial neutralisation, p 0.5**, against beta, log dollar volume, 60-day vol, sector dummies. Control p 0. DEV;
   judge on net decile Sharpe and weekly-IC sd.
4. **Industry-adjusted reversal + short-term industry momentum features** (Blitz et al. 2023). DEV; point-in-time
   industry map frozen at first use; features enter as one set.
5. **Cost-aware, liquidity-tiered book**: alpha minus per-name cost, or weight × min(1, κ / half-spread), κ from the
   published cost literature. FWD only (DEV spreads uniform). Risk high for any parameter from the spent tiers.
6. **Target-variant ensemble** (industry+beta residual, vol-scaled targets). DEV. Gains likely ~+0.001.
7. **Tail-weighted training + tail-IC metric.** DEV. Cousin of ranking losses (which gave nothing).
8. **Weekly refits.** DEV. Small expected gain.
9. **Execution audit** of the broad book (signal time, fill type, realised vs assumed spread). FWD; measurement only;
   the likeliest place for the last few hundredths of Sharpe to vanish [R].

Not recommended: era boosting; re-tuning the band on spent data; cross-name attention.

## 3. Search log

Queries: Numerai neutralisation/Sharpe; era boosting; Jane Street 2021 and 2024 1st place; Ubiquant 1st (Pearson
loss, GitHub); JPX 1st; Optiver Trading at the Close 1st (2 variants); G-Research crypto 1st; Quantpedia residual
reversal; Robot Wealth reversal costs (×2); Alpha Architect STREV costs; Numerai multi-target; Numerai CORR 1.5;
WorldQuant BRAIN neutralisation/decay; Qlib Alpha158/TopkDropout; r/quant small-cap stat arb and MOC; de Groot-Huij-
Zhou; Blitz et al. 2023; Numerai TC.

Opened: forum.numer.ai 189, 899, 7486, 4955, 1059, 5842, 4338; docs.numer.ai MMC and CORR; Volkova solution.md
(master); J-Quants JPX winner README and folder; gresearch.com wrap-up; Quantpedia short-term reversal; Robot Wealth
no-trade region; Concretum execution delay; Robeco reversal summary; arXiv 1601.00991 abstract.

Blocked: Kaggle discussion 224348 (title only, JS-rendered), so the Ubiquant, Optiver and Jane Street 2024 1st-place
Kaggle write-ups were not read; Volkova solution.md on main (404; found on master); alphaarchitect.com (403 ×2); one
Quantpedia fetch and one Robot Wealth search hit a usage limit and were redone.

Not reached: QuantNet, Ernie Chan, QuantStart, Quantocracy, official WorldQuant docs, the full Qlib docs, SSRN papers
(Blitz et al. 2023 and 2022; de Groot-Huij-Zhou in full). No novelty claim.
