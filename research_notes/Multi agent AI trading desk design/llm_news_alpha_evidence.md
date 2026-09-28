# Empirical evidence on LLM-extracted return predictability from news (horizon, size, model, prompt, cost)

Scope note: goal is to judge signal design / horizon / universe for a weekly S&P 500 long-short book. Numbers below are gross of costs unless stated. "EW" = equal-weighted, "VW" = value-weighted. Contamination flag = sample period overlaps the model's pre-training data.

## Key studies and their numbers (Sharpe/IC, horizon, universe, costs)

### Takeaway
The headline Sharpe ratios (3-6) are daily-rebalanced, equal-weighted, small-cap-dominated, and mostly gross of costs; the part of the signal that survives out-of-sample is a 1-2 day drift concentrated in small caps and bad news, and it breaks even at roughly 10-20 bps round-trip costs. For large caps the pre-LLM evidence already shows news is priced within about one day.

### Cited Findings
**Lopez-Lira & Tang (JFE vol. 184, Oct 2026; arXiv 2304.07619 v6)**
- Published as "Can ChatGPT forecast stock price movements? Return predictability and large language models," Journal of Financial Economics 184 (Oct 2026), DOI 10.1016/j.jfineco.2026.104335 — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0304405X26001066)
- Sample: Oct 2021 – May 2024, 159,137 firm-headline-date observations, 4,123 US firms (~85% of CRSP); 82% overnight / 18% intraday news. The sample starts after the Sept 2021 training cutoff, so it is out-of-sample for GPT-4 pretraining — [arXiv v6 PDF](https://arxiv.org/pdf/2304.07619v6)
- GPT-4 hit rate on the *initial* (non-tradable) reaction: 93.3% (abstract: "approximately 90% portfolio-day hit rates") — [arXiv v6](https://arxiv.org/pdf/2304.07619v6); [arXiv abs](https://arxiv.org/abs/2304.07619)
- Tradable drift strategy on overnight news: annualised Sharpe 2.97; mean 34 bps/day long-short; long leg 8 bps, short leg 26 bps (most of the alpha is on the short side) — [arXiv v6](https://arxiv.org/pdf/2304.07619v6)
- Horizon: drift is significant for 1-2 trading days (34 bps on day 1, 19 bps on day 2), with no significant predictability beyond day 2 — [arXiv v6](https://arxiv.org/pdf/2304.07619v6)
- Size: drift is much stronger in small caps (small-cap interaction coefficient 0.404, t=4.75, vs base coefficient 0.087) — [arXiv v6](https://arxiv.org/pdf/2304.07619v6)
- Costs: cumulative return >300% at 5 bps round-trip, >100% at 10 bps, unprofitable at 20 bps — [arXiv v6](https://arxiv.org/pdf/2304.07619v6)
- Markets price transparent news (earnings, clinical trials) efficiently but underreact to complex news that needs synthesis (insider transactions, specialised conference announcements) — [ScienceDirect abstract](https://www.sciencedirect.com/science/article/abs/pii/S0304405X26001066)

**Chen, Kelly & Xiu, "Expected Returns and Large Language Models" (SSRN 4416687; working paper)**
- Approach: take LLM embeddings of news text, then fit a supervised regression or NN of returns on those embeddings. Reported daily EW Sharpe: ChatGPT embeddings 4.62, LLaMA2 4.16, BERT >3, Word2vec >3, SESTM 3.43, LMMD 2.29. A nonlinear (NN) head on ChatGPT embeddings gives 5.83, and an EW ensemble of all models gives 5.11. For monthly predictions, performance peaks with a 12-24 month lookback. Covers ~25 years of Thomson Reuters news, multi-country and multi-language — [FINM 33200 course discussion (secondary summary)](https://finm-33200.github.io/discussions/expected_returns_llms.html). NOTE: I could not verify these figures against the primary paper; the slides show them only as charts — [Kelly Wharton slides](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/Kelly-WhartonJL.pdf)
- Slides state "Larger LLMs perform better" and claim "strong out-of-sample success compared to existing predictive signals" — [Kelly Wharton slides](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/Kelly-WhartonJL.pdf)
- A published discussion exists (Sophia Zhengzi Li, Wharton Jacobs Levy 2024) — [Discussion slides](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/ExpectedReturnAndLLM_Discussion_SophiaZhengziLi_NoPause.pdf)

**Ke, Kelly & Xiu, "Predicting Returns with Text Data" (SESTM; NBER w26186) — the pre-LLM benchmark**
- Data: Dow Jones Newswires 1989-2017, 6.5M+ articles; out-of-sample test Feb 2004 – Jul 2017 — [NBER PDF](https://www.nber.org/system/files/working_papers/w26186/revisions/w26186.rev1.pdf)
- Daily long-short: EW Sharpe 4.29 (33 bps/day) vs VW Sharpe 1.33 (10 bps/day). RavenPack gets EW 3.24 and LM dictionary EW 1.71 — [NBER PDF](https://www.nber.org/system/files/working_papers/w26186/revisions/w26186.rev1.pdf)
- Net of 10 bps trading cost, with an optimised turnover constraint: Sharpe 2.30 — [NBER PDF](https://www.nber.org/system/files/working_papers/w26186/revisions/w26186.rev1.pdf)
- Speed of assimilation: large stocks respond 11 bps with 1-day assimilation; small stocks respond 52 bps with 3-day assimilation. Fresh news takes 4 days to be absorbed, stale news 2 days — [NBER PDF](https://www.nber.org/system/files/working_papers/w26186/revisions/w26186.rev1.pdf)

**Kirtac & Germano, "Sentiment trading with large language models" (Finance Research Letters 2024)**
- 965,375 US news articles, Jan 2010 – Jun 2023. Sentiment accuracy: OPT 74.4%, BERT 72.5%, FinBERT 72.2%, LM dictionary 50.1%. Long-short Sharpe: OPT 3.05, BERT 2.11, FinBERT 2.07, LM 1.23. OPT score coefficient on next-day returns is 0.274 / 0.254 — [arXiv 2412.19245](https://arxiv.org/abs/2412.19245); [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1544612324002575)
- FLAG: the sample overlaps the pretraining data of OPT and BERT (contamination risk). The abstract does not report results net of costs.

**Chen, Tang, Zhou & Zhu, "ChatGPT and DeepSeek: Can they predict the stock market and macroeconomy?" (arXiv 2502.10008)**
- Uses WSJ articles to predict the aggregate market, not the cross-section. ChatGPT has predictive power, DeepSeek underperforms (attributed to less English training), and other LLMs are weaker. Predictability comes from positive news in downturns and high-uncertainty periods; negative news is contemporaneous but not predictive — [arXiv abs](https://arxiv.org/abs/2502.10008)

### Inferences
- VW Sharpe is about 1/3 of EW in SESTM (1.33 vs 4.29), and the LLM papers report mostly EW. For an S&P 500 book, the relevant prior is a VW-like, large-cap Sharpe well below 1.5 gross, before any weekly-horizon decay.
- The LLT long/short asymmetry (26 vs 8 bps) and the small-cap concentration mean the gross numbers depend partly on shorting costs and short-sale constraints in illiquid names. S&P 500 names are cheap to short, but that is also why their mispricing is smaller.

### Gaps
- I could not extract primary-source VW, large-cap-only or net-of-cost figures for Chen-Kelly-Xiu (only a secondary summary and chart-only slides were available).
- I found no study reporting ICs (rank correlations) specifically for S&P 500 constituents at a 5-day horizon using LLM scores.

## Does predictability decay as LLM usage spreads? (post-2023 evidence)

### Takeaway
Yes, sharply, within the one clean out-of-sample study. Separately, much apparent pre-cutoff performance in other studies is lookahead contamination, so in-sample LLM backtests should be heavily discounted.

### Cited Findings
- LLT GPT-4 drift Sharpe by period: 2021Q4 6.54, 2022 3.68, 2023 2.33, Jan-May 2024 1.22 (gross) — [arXiv v6](https://arxiv.org/pdf/2304.07619v6). A secondary summary gives it as going from ~6 in late 2021 to ~2 by 2023 — [FINM 33200](https://finm-33200.github.io/discussions/expected_returns_llms.html)
- Authors interpret the decline as "consistent with improved price efficiency" as LLM adoption rises — [arXiv abs](https://arxiv.org/abs/2304.07619)
- Gao, Jiang & Yan, "Detecting Lookahead Bias in LLM Forecasts" (arXiv 2512.23847). Their "Lookahead Propensity" (LAP) measure is materially positive in-sample and collapses to ~0 right after the training cutoff. The predictive power of LLM forecasts of news-headline returns is amplified on high-LAP firm-dates, and the amplification disappears post-cutoff — [arXiv](https://arxiv.org/abs/2512.23847)
- Glasserman & Lin (arXiv 2309.17322; J. Financial Data Science). Anonymising company names in headlines *improved* in-sample performance, so the "distraction effect" (the model's general knowledge about the firm) outweighs lookahead bias. The effect is stronger for large firms. Out-of-sample, lookahead stops mattering but distraction persists, and they recommend anonymising — [arXiv](https://arxiv.org/abs/2309.17322)
- Look-Ahead-Bench (arXiv 2601.13770): standard LLMs (Llama 3.1 8B/70B, DeepSeek 3.2) show significant lookahead bias measured via alpha decay across regimes, while point-in-time-trained models generalise better — [arXiv](https://arxiv.org/abs/2601.13770)
- Related remedies: time-aware pretraining (DatedGPT) — [arXiv 2603.11838](https://arxiv.org/html/2603.11838); oracle-based mitigation — [arXiv 2605.24564](https://arxiv.org/html/2605.24564)

### Inferences
- Extrapolating the LLT trend (Sharpe of 1.22 in H1 2024, small-cap-dominated, daily), the 2025-26 gross daily Sharpe of a generic "is this headline good/bad" GPT-4-class signal is plausibly ≤1, and lower still in large caps. Any backtest of a current frontier model on pre-2025 news is contaminated by construction.
- Anonymisation is cheap, and the evidence says it helps most in large caps, which is exactly the S&P 500 universe.

### Gaps
- I found no peer-reviewed study with a clean post-2024 out-of-sample window for frontier (2025-26) models on cross-sectional US equities.

## Scoring design: direct forecasts vs sentiment vs probabilities; embeddings+regression vs prompting; calibration/logprobs; sampling

### Takeaway
Embeddings plus a supervised return head outperform zero-shot prompting in the reported numbers (ChatGPT embeddings EW Sharpe 4.62, NN head 5.83, vs a prompted GPT-4 drift Sharpe of about 3). The two were measured on different samples, though, and the embedding approach needs a long, uncontaminated training window. Evidence on logprobs, calibration and the number of samples is thin.

### Cited Findings
- Prompted design (LLT): a ternary YES/NO/UNKNOWN answer to "Is this headline good or bad for the stock price of [company] in the short term?", with the persona "Pretend you are a financial expert" — [arXiv v6](https://arxiv.org/pdf/2304.07619v6)
- Embedding + regression (CKX) beats pre-LLM supervised text (SESTM 3.43) and dictionaries (LMMD 2.29). Nonlinear heads add value (4.62 → 5.83), and ensembling across LLMs gives 5.11 — [FINM 33200 summary](https://finm-33200.github.io/discussions/expected_returns_llms.html)
- A supervised text score targeted at returns beats vendor sentiment (SESTM 4.29 vs RavenPack 3.24 EW) — [NBER PDF](https://www.nber.org/system/files/working_papers/w26186/revisions/w26186.rev1.pdf)
- Fine-tuned or encoder sentiment classifiers (OPT/BERT/FinBERT) beat dictionaries by a wide margin (Sharpe 3.05/2.11/2.07 vs 1.23), but that sample is contaminated — [arXiv 2412.19245](https://arxiv.org/abs/2412.19245)

### Inferences
- A return-supervised head on embeddings is the design with the best documented performance. It also sidesteps prompt sensitivity, and (with anonymisation) partly sidesteps distraction. Its risk is that the training window lies inside the model's pretraining period.

### Gaps
- I found no primary study quantifying logprob-weighted scores vs discrete labels, LLM confidence calibration for return direction, or the benefit of multiple samples / self-consistency for cross-sectional returns. I could not source these, so treat them as open questions.

## Does adding price/technical data to prompts help or hurt (anchoring)?

### Takeaway
I found no rigorous, contamination-controlled finance study on this. The available results are low-quality engineering papers.

### Cited Findings
- Search results were limited to hybrid LLM+transformer price-forecasting papers in lower-tier venues (e.g., [ScienceDirect Information Sciences 2026](https://www.sciencedirect.com/science/article/pii/S0020025526006420); [StockTime arXiv 2409.08281](https://arxiv.org/html/2409.08281v1)). They generally report accuracy gains from fusion, but I did not verify their evaluation designs and do not rely on them.
- Indirect evidence: a model's prior knowledge about a firm biases its reading of news, and removing firm identity helps (the distraction effect) — [Glasserman & Lin](https://arxiv.org/abs/2309.17322). An AEA 2026 paper, "What Does ChatGPT Make of Historical Stock Returns?", studies how LLMs extrapolate price paths — [AEA program](https://www.aeaweb.org/conference/2026/program/paper/zNrQ4Yn6) (not read in detail).

### Inferences
- The cleaner design is to keep the LLM text-only (and anonymised) and combine its score with price features (momentum, reversal, volume) in a separate statistical layer, so any interaction can be estimated rather than left to the prompt.

### Gaps
- There is no quantified evidence on whether numeric inputs inside prompts anchor or degrade text-based return signals.

## Weekly horizon: news-driven drift over ~5 days for large caps, and reversal of non-news moves

### Takeaway
The classic evidence supports "news moves continue, non-news moves reverse," but it is concentrated in small and illiquid stocks. For large caps, text-based signals are absorbed in about one day. A weekly S&P 500 book should therefore not expect much pure news drift. The more promising weekly signal is conditioning short-term reversal on whether a move had news.

### Cited Findings
- Chan (2003, JFE): post-news drift is strongest after bad news, and there is some reversal after extreme price moves without public news. Both effects "apply mainly to smaller stocks," and short-sale constraints play a role in post-bad-news drift. The horizon is monthly — [SSRN abstract](https://ssrn.com/abstract=262452); [IDEAS](https://ideas.repec.org/a/eee/jfinec/v70y2003i2p223-260.html)
- Tetlock (2010, RFS 23(9)), 2.2M news events 1979-2007: ten-day reversals of daily returns are 38% lower on news days. High-volume news days show continuation (momentum), and the effects are much stronger in small, illiquid firms, with gradual adjustment over days 2-10 — [Tetlock PDF](https://business.columbia.edu/sites/default/files-efs/pubfiles/4150/Tetlock%2004%2010%20News%20and%20Asymmetric%20Information-1.pdf); [RFS](https://academic.oup.com/rfs/article-abstract/23/9/3520/1671631)
- SESTM: large-stock news is assimilated in 1 day (11 bps), small stocks in 3 days (52 bps) — [NBER PDF](https://www.nber.org/system/files/working_papers/w26186/revisions/w26186.rev1.pdf)
- LLT: GPT-4 drift lasts 1-2 days, nothing significant after day 2, and it is stronger for small caps — [arXiv v6](https://arxiv.org/pdf/2304.07619v6)

### Inferences
- For a weekly S&P 500 rebalance, a news-drift signal formed at t and held from t+1 to t+5 will mostly miss the 1-day window where large-cap drift lives. A better-motivated weekly design is to separate the past week's return into a news component and a no-news component (using LLM news detection and materiality scoring), then bet on reversal of the no-news component and continuation of the high-materiality, complex news component. This follows Chan, Tetlock, and LLT's finding that complex news is underreacted to.

### Gaps
- I found no study that directly measures LLM-signal drift over days 1-5 for S&P 500 constituents post-2023.

## Model choice: bigger / reasoning vs small; open-weight vs closed

### Takeaway
Within a model generation, capability scales with size (GPT-4 ≫ GPT-3.5 ≫ Llama2-70B ≫ BERT/GPT-2 in zero-shot prompting). With embeddings plus supervised training, the gap narrows (LLaMA2 4.16 vs ChatGPT 4.62). I found no rigorous evidence on reasoning models specifically.

### Cited Findings
- LLT drift Sharpe: GPT-4 2.97, GPT-3.5 1.66, DistilBart-MNLI 1.26, BART-Large 1.05, Llama2-70B 0.97; GPT-1, GPT-2 and BERT are negative — [arXiv v6](https://arxiv.org/pdf/2304.07619v6)
- CKX embeddings: ChatGPT 4.62 vs LLaMA2 4.16, BERT >3 — [FINM 33200](https://finm-33200.github.io/discussions/expected_returns_llms.html); "Larger LLMs perform better" — [Kelly slides](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/Kelly-WhartonJL.pdf)
- ChatGPT beats DeepSeek on WSJ-based market prediction (attributed to English training) — [arXiv 2502.10008](https://arxiv.org/abs/2502.10008)
- DeepSeek 3.2 and Llama 3.1 show measurable lookahead bias — [Look-Ahead-Bench](https://arxiv.org/abs/2601.13770)

### Inferences
- The model-size effect is largest for zero-shot prompting and smallest for embedding plus supervised learning. A cheap open-weight embedding model with a trained head may capture most of the attainable signal at low cost. An expensive frontier or reasoning model is better spent on the harder, less-priced task: synthesising complex news and judging materiality and novelty.

### Gaps
- I found no peer-reviewed comparison of reasoning models (o-series, R1-class) vs non-reasoning models on cross-sectional return prediction with a clean post-cutoff test.
- I found no Qwen-specific finance return evidence.
