# Multi-agent LLM trading systems: architectures, role design, and what the evidence supports (survey notes, researched 2026-09-28)

Scope note: primary sources are arXiv papers (2023–2026) and practitioner reporting from 2025–2026. Headline numbers are the authors' own claims unless labelled as a replication or critique. Where a detail comes only from a paper abstract, or from my prior knowledge of a paper I did not re-fetch this session, it is marked "(abstract-level)".

## 1. Role decompositions and which components have ablation evidence

### Takeaway
Nearly every framework uses the same template: analysts split by data type (fundamental, news, sentiment, technical), sometimes a bull/bear debate, then a trader or manager, a risk layer and reflection or memory. Component-level ablations are rare. The best-controlled one so far (TOPIX 100, 27 months, all out of sample) found that giving agents well-defined tasks with precomputed indicators mattered more than adding roles. Removing several analyst roles actually *improved* the Sharpe ratio.

### Cited Findings
- **TradingAgents (Xiao et al., Dec 2024; later revisions).** Seven roles: four analysts (fundamental, sentiment, news, technical), bull and bear researchers who debate over several rounds, a trader, a three-voice risk team (risk-seeking, neutral, conservative) and a fund manager who approves trades. Tested on AAPL, GOOGL and AMZN from 1 Jan to 29 Mar 2024 (3 months). Reported Sharpe ratios of 8.21, 6.39 and 5.60, with maximum drawdowns of 0.91–2.11%. **The paper has no component ablation and no significance tests.** The authors themselves say Sharpe ratios above 3 reflect "few pullbacks" in the test window and that the 3-month window was a budget constraint — [arXiv 2412.20138](https://arxiv.org/html/2412.20138)
- **FinCon (NeurIPS 2024).** A manager–analyst hierarchy: seven analysts (news, filings, sentiment, earnings-call audio via Whisper, data, stock selection) report to a single manager who makes the decisions. It has two risk layers: a within-episode CVaR trigger that turns risk-averse when daily P&L falls into the worst tail, and CVRF, an over-episode "conceptual verbal reinforcement" belief update. Trained Jan–Oct 2022 and tested 5 Oct 2022 – 10 Jun 2023 on GPT-4-Turbo. Reported results: TSLA cumulative return 82.87% with Sharpe 1.972; a TSLA/MSFT/PFE portfolio with cumulative return 113.84% and Sharpe 3.269, against 12.64% for Markowitz. In the ablations, agents without CVRF "consistently hold lower positions." — [arXiv 2407.06567](https://arxiv.org/html/2407.06567v3); [NeurIPS PDF](https://proceedings.neurips.cc/paper_files/paper/2024/file/f7ae4fe91d96f50abc2211f09b6a7e49-Paper-Conference.pdf)
- **Caveat on FinCon.** The whole test window falls *before* GPT-4-Turbo's training cutoff, so the backbone could have seen the outcomes — [arXiv 2407.06567](https://arxiv.org/html/2407.06567v3); the leakage is quantified in [Profit Mirage](https://arxiv.org/html/2510.07920v1) (section 4 below).
- **"Toward Expert Investment Teams" (Feb 2026).** A three-level hierarchy:
  - Level 1: technical, quantitative, qualitative and news agents score each stock from 0 to 100.
  - Level 2: sector and macro agents adjust those scores.
  - Level 3: a PM agent builds a long-short portfolio.

  Tested on TOPIX 100, Sep 2023 – Nov 2025 (27 months), entirely after the LLM's Aug 2023 cutoff. Monthly rebalancing, market neutral, 10 bp one-way costs.
  - Fine-grained tasks (precomputed rate-of-change, MACD, RSI, ROE, EV/EBITDA and similar) beat coarse ones (raw prices or raw statements) by a median Sharpe of +0.19 at 20 stocks and +0.26 at 50 stocks (p<0.0001).
  - Removing the technical agent cut Sharpe by 0.40–0.66.
  - **Removing the quantitative, qualitative or macro agent often *improved* performance.** The news agent's effect was inconsistent.
  - A 50/50 blend of the index and the agent composite had a Sharpe of 2.11 gross and 1.91 net of costs, against 1.68 for the index alone. The agent composite on its own returned only 13.7% gross.

  — [arXiv 2602.23330](https://arxiv.org/html/2602.23330v1)
- **AlphaAgents (BlackRock authors, Aug 2025).** Fundamental, sentiment and valuation agents debate round-robin until they reach consensus, with each agent required to speak at least twice. Risk tolerance is set through the prompt. Tested on 15 tech stocks, Feb–May 2024, with no costs disclosed and only charts, no tables of numbers. The multi-agent portfolio beat the single-agent portfolios in the risk-neutral setting. In the risk-averse setting every agent portfolio underperformed the equal-weight benchmark. **There is no debate-on versus debate-off ablation.** Risk-seeking and risk-neutral prompts produced "nearly indistinguishable" outputs — [arXiv 2508.11152](https://arxiv.org/html/2508.11152v1)
- **Other frameworks in the same family (abstract-level):**
  - FinMem: one agent with a profile module and layered short, mid and long-term memory with decay — [arXiv 2311.13743](https://arxiv.org/abs/2311.13743)
  - FinAgent: multimodal (price charts plus text), tool-augmented, with low-level and high-level reflection — [arXiv 2402.18485](https://arxiv.org/abs/2402.18485)
  - FinRobot: an open-source platform with a financial chain-of-thought and multi-agent workflow layer — [arXiv 2405.14767](https://arxiv.org/abs/2405.14767)
  - StockAgent: a simulation of LLM investor agents, not an alpha system — [arXiv 2407.18957](https://arxiv.org/abs/2407.18957)
  - HedgeAgents: a hedge-fund-style manager plus asset-class analyst agents — [arXiv 2502.13165](https://arxiv.org/abs/2502.13165)
  - MarketSenseAI: an LLM stock-selection pipeline on the S&P 100 — [arXiv 2401.03737](https://arxiv.org/abs/2401.03737)
  - Alpha-GPT: human-in-the-loop alpha-factor mining — [arXiv 2308.00016](https://arxiv.org/abs/2308.00016)
  - QuantAgent: an inner/outer loop that writes and refines code against a knowledge base — [arXiv 2402.03755](https://arxiv.org/abs/2402.03755)
- **CLQT benchmark (2026), live track** with models such as claude-sonnet-4.6, gpt-5.4-mini and gemini-3.5-flash. Agents' signal–action agreement was only about 0.59–0.61, and independent judges scored whether allocations matched the agents' own narratives at about 0.27. In other words, the stated reasoning often does not match the trades — [arXiv 2606.29771](https://arxiv.org/html/2606.29771)

### Inferences
- The analyst split by data type is copied from how human desks are organised, not derived from evidence. The one careful ablation suggests that *what each agent is asked to compute* matters more than *how many personas* there are. Extra qualitative agents can add noise.
- Precomputed quantitative features, such as a technical-indicator agent, look like the part carrying the value. This fits a reading in which the LLM mostly re-weights known factors rather than finding new information.
- Risk and PM layers mostly act as position-size dampeners. FinCon's evidence says belief updating raises position sizes, not that it improves risk-adjusted skill.
- Given CLQT's coherence gap, rationales from debate or reflection should not be treated as a faithful explanation of the trade.

### Gaps
- No published ablation of the TradingAgents bull/bear debate or of its three-voice risk team was found. Community reproductions exist, but I did not find a peer-reviewed one.
- I did not re-verify HedgeAgents' and MarketSenseAI's headline returns this session; treat them as unverified author claims.

## 2. Does debate or adversarial review help, or does it cause conformity, sycophancy and over-caution?

### Takeaway
Outside finance, the 2024–2026 evidence is mixed to negative. Debate often fails to beat simple majority voting or self-consistency at equal compute. Agents conform to the majority and flip correct answers to wrong ones more often than the reverse, and weak agents drag strong ones down. Inside finance, no study cleanly isolates the effect of debate. The indirect evidence points toward caution and lower exposure, not better accuracy.

### Cited Findings
- **Failure modes of debate (arXiv 2509.05396, Sep 2025).** Tested on CommonSenseQA, MMLU and GSM8K with GPT-4o-mini, Llama-3.1-8B and Mistral-7B, 5 seeds.
  - Debate often *reduced* accuracy compared with majority voting without discussion. For example, three Mistral agents on CommonSenseQA lost 5.0 points.
  - More agents flipped from correct to incorrect than the other way.
  - Resistance to social pressure falls after round 2.
  - Mixed teams do worse: two Llama agents plus one Mistral lost 8.2 points on MMLU.

  — [arXiv 2509.05396](https://arxiv.org/html/2509.05396)
- **Controlled study of what drives debate (arXiv 2511.07784).** The strongest predictors of final accuracy are the agents' initial accuracy and team size (R²=0.393). Showing agents each other's confidence, and debate order, were not significant. Majority pressure suppresses correction: weaker models overturned a wrong majority only 3.6% of the time, stronger models 30–34%. "Correcting a wrong consensus contributes most to final accuracy" but rarely happens — [arXiv 2511.07784](https://arxiv.org/pdf/2511.07784)
- **Sycophancy and identity bias.** CONSENSAGENT (ACL Findings 2025) targets sycophancy in consensus-seeking debate — [ACL Anthology](https://aclanthology.org/2025.findings-acl.1141/). Another study finds identity bias in debate and reduces it by anonymising which agent said what — [arXiv 2510.07517](https://arxiv.org/html/2510.07517v1). Free-MAD proposes consensus-free debate because consensus itself causes conformity — [arXiv 2509.11035](https://arxiv.org/html/2509.11035v1)
- **Early positive result.** Du et al. (2023) reported that multi-agent debate improves factuality and arithmetic (abstract-level) — [arXiv 2305.14325](https://arxiv.org/abs/2305.14325). Later benchmarking found that debate does not reliably beat self-consistency or ensembling at equal cost (abstract-level) — [Smit et al., "Should we be going MAD?", arXiv 2311.17371](https://arxiv.org/abs/2311.17371)
- **Finance: over-caution.** FINSABER reports that LLM strategies are "excessively conservative in bull markets" and have "inadequate risk controls in bear markets" — [arXiv 2505.07078](https://arxiv.org/html/2505.07078). AlphaAgents' risk-averse debate portfolios underperformed during the 2024 tech rally — [arXiv 2508.11152](https://arxiv.org/html/2508.11152v1). In FinCon, removing belief updating led to persistently smaller positions — [arXiv 2407.06567](https://arxiv.org/html/2407.06567v3)

### Inferences
- A typical desk pipeline runs a bull/bear debate, then a conservative risk voice, then PM approval. Each stage can only shrink the position, so by construction the system drifts toward hold or flat ("regress to zero"). Add the conformity effects above and debate probably reduces variance more than it adds skill.
- If adversarial review is used, the literature points to these design choices:
  - keep initial views independent, and log them before any discussion;
  - anonymise which agent said what;
  - aggregate by vote or average rather than by forced consensus;
  - use a strong model for the critic;
  - compare against a same-cost baseline of N independent samples.

### Gaps
- I found no finance paper that turns debate on and off with enough tickers, time and statistical tests to measure its effect on forecast accuracy or calibration (for example IC or Brier score).

## 3. Memory and reflection: does learning from past P&L help, and how is look-ahead avoided?

### Takeaway
Most frameworks feature reflection (FinMem's layered memory, FinAgent's dual reflection, FinCon's CVRF), but the supporting evidence comes from short windows that sit inside the backbone model's training period. There, "learning" cannot be separated from memorised outcomes. Only a few designs strictly block look-ahead, such as testing entirely after the model's cutoff or using point-in-time memory.

### Cited Findings
- FinCon's CVRF compares episodes that did better and worse, extracts "concepts", and passes belief updates only to the relevant agents. Without it, agents hold smaller positions. All of this took place before the model's cutoff — [arXiv 2407.06567](https://arxiv.org/html/2407.06567v3)
- **FinMem when re-evaluated.** It reported a Sharpe of 2.679 on its selected sample. Under FINSABER's 20-year, 100+ symbol evaluation, that fell to 0.404–0.927, and passive benchmarks often did better — [arXiv 2505.07078](https://arxiv.org/html/2505.07078)
- **CLQT** formalises memory across rounds (three tiers with decay and consolidation) and enforces point-in-time data. Net of costs, "agents clear the defensive baselines but not the index cleanly." — [arXiv 2606.29771](https://arxiv.org/html/2606.29771)
- **Ways to avoid look-ahead:**
  - Test entirely after the model's cutoff. "Toward Expert Investment Teams" tested Sep 2023 – Nov 2025 against an Aug 2023 cutoff — [arXiv 2602.23330](https://arxiv.org/html/2602.23330v1).
  - Use counterfactually perturbed inputs — [Profit Mirage](https://arxiv.org/html/2510.07920v1).
  - Use a point-in-time universe that includes delisted names — [FINSABER](https://arxiv.org/html/2505.07078).
  - A 2026 paper proposes using an LLM "oracle" to detect and mitigate look-ahead bias — [arXiv 2605.24564](https://arxiv.org/html/2605.24564) (not read in full).

### Inferences
- For a live paper-trading agent, reflection on the agent's *own* realised P&L is free of look-ahead by construction. The risk runs the other way: overfitting to noise when there are only a few dozen trades. Reflections should be treated as priors needing many observations before they change sizing.
- There is no evidence that verbal reflection beats a simple non-LLM rule, such as volatility targeting or cutting size after drawdowns, at equal risk.

### Gaps
- I found no study that ablates reflection or memory in a post-cutoff, multi-year, many-ticker setting.

## 4. How these systems were evaluated, and the documented flaws

### Takeaway
The original papers typically use 3–24 months and 3–100 tickers, often with no costs and no significance tests, and inside the LLM's training window. When evaluations are corrected for leakage, survivorship and window length, the reported edge largely disappears.

### Cited Findings
- **FINSABER (2025).** It surveys prior LLM timing strategies: evaluations of 3–24 months on 3–100 symbols, often without released code. It then re-tests FinMem and FinAgent over 2000–2024 on 100+ symbols, using historical S&P 500 membership including delisted stocks. It identifies three biases:
  - survivorship bias, which it puts at 0.1–0.9% a year of overstated returns;
  - look-ahead bias from using current index membership;
  - data snooping.

  Passive benchmarks often came out ahead — [arXiv 2505.07078](https://arxiv.org/html/2505.07078)
- **Profit Mirage (Oct 2025).** It ran FinMem, FinAgent, QuantAgent, FinCon and TradingAgents on GPT-4o over NASDAQ-100 names in two windows with similar market returns: Q2–Q3 2021 (market +13.79%, before cutoff) and Q3–Q4 2024 (+13.35%, after cutoff).
  - Sharpe decayed by 51.48% (QuantAgent) to 62.23% (FinCon).
  - Total return decayed by 50.18% (TradingAgents) to 71.85% (FinMem).
  - On FinLake-Bench (2,000 historical questions, Jan 2022 – Jun 2023) the models scored 85–93%, a sign of memorisation.
  - When inputs were perturbed counterfactually, predictions stayed the same 69–82% of the time.

  The authors propose FactFin (code generation, RAG, MCTS and a counterfactual simulator), which they report achieves 1.4 times the out-of-sample Sharpe of the baselines. This is the authors' own claim — [arXiv 2510.07920](https://arxiv.org/html/2510.07920v1)
- **Flaws in individual papers:**
  - TradingAgents: 3 months, 3 tickers, no significance tests, and Sharpe ratios of 5–8 that the authors put down to a calm market — [arXiv 2412.20138](https://arxiv.org/html/2412.20138).
  - AlphaAgents: 15 stocks, 4 months, one sector, no costs, no numeric tables — [arXiv 2508.11152](https://arxiv.org/html/2508.11152v1).
  - FinCon: about 8 months of testing, 8 tickers plus two 3-stock portfolios, before the model's cutoff — [arXiv 2407.06567](https://arxiv.org/html/2407.06567v3).
- **CLQT's list of gaps in prior benchmarks:**
  - no point-in-time enforcement;
  - costs ignored or flattened;
  - scoring of single assets rather than portfolios;
  - memory not formalised;
  - quality of tool use not measured;
  - no measure of strategy drift;
  - news treated as point-in-time snapshots rather than trajectories.

  — [arXiv 2606.29771](https://arxiv.org/html/2606.29771)
- **Counter-example with a better design:** 27 months, entirely post-cutoff, 100 names, 10 bp costs, and significance tests — [arXiv 2602.23330](https://arxiv.org/html/2602.23330v1). Its standalone agent performance is modest; the value comes from low correlation (about 0.4) with the index when blended.

### Inferences
- Any Sharpe ratio above about 2 on a single-name window of under a year that falls before the cutoff should be treated as uninformative.
- The minimum credible standard is:
  - post-cutoff (or point-in-time model) data;
  - at least 12–24 months, or live paper trading;
  - a broad universe that is point-in-time and includes delisted names;
  - costs included;
  - baselines of buy-and-hold, a simple factor, and a single LLM call at the same budget;
  - multiple seeds or runs;
  - significance testing, for example a bootstrap or a Deflated Sharpe ratio.

### Gaps
- Few papers report IC or hit rate alongside returns, so forecast skill cannot be separated from beta or timing luck.

## 5. What practitioners report (2025–2026)

### Takeaway
Institutions are deploying agents mainly in *research*: generating signals, reading documents and running backtests, with humans approving and checking each step. Nobody reports an autonomous multi-persona LLM "desk" making trading decisions end to end.

### Cited Findings
- **Man Group (Man Numeric), Jul 2025.** AlphaGPT mines data, writes rule-based signals as code, and backtests them. It has produced "several dozen investment signals that have been approved for live trading." PM Ziang Fang: "I wouldn't call it autopilot… we have a lot of checkpoints in place." The team reports "hallucinations and inconsistent outputs" and says it is "iterating with caution" — [Hedgeweek](https://www.hedgeweek.com/man-group-deploys-agentic-ai-for-quant-signal-discovery/); see also [Man Group insight](https://www.man.com/insights/what-ai-can-do-for-alpha)
- **Bridgewater AIA Labs.** It combines causal time-series ML with custom LLMs and agent workflows. The Macro strategy has been live since Dec 2023 and is reported at over $4.5bn. A model fine-tuned on expert-labelled examples reached 84.7% accuracy on research tasks, against the mid-to-high 70s for frontier models, and costs 13.8 times less per task. Claims of "market-beating returns" are unaudited and come via trade press — [AI Street](https://www.ai-street.co/p/bridgewater-trains-ai-to-think-like)
- **BlackRock.** AlphaAgents is a research paper; the authors say its views are their own, not the firm's — [arXiv 2508.11152](https://arxiv.org/html/2508.11152v1)
- **Other fund launches.** Plans for "fully agentic" AI hedge funds (for example Lumenai) appear in trade press, but no performance record was found — [Hedgeweek](https://www.hedgeweek.com/lumenai-plans-launch-of-fully-agentic-ai-hedge-fund/)

### Inferences
- The pattern at credible firms: LLM agents generate *checkable* artefacts (code, signals, summaries). These then go through conventional statistical validation and risk systems. The LLM is not the final decision-maker for sizing.

### Gaps
- I found no audited performance data for any LLM-agent-driven fund. Prop-desk reports are mostly marketing or blog posts and were excluded.

## 6. Ensembling and self-consistency across samples or models

### Takeaway
Aggregating many independent LLM forecasts is the best-supported way to combine LLM outputs. A 12-model crowd matched a human forecasting crowd. But individual LLMs are overconfident and biased toward "yes", and the ensemble gains most from being shown an independent anchor such as the human median.

### Cited Findings
- **Wisdom of the silicon crowd (Science Advances 2024).** An ensemble of 12 LLMs forecast 31 Metaculus questions (Oct 2023 – Jan 2024).
  - Brier scores: LLM crowd 0.20, human crowd of 925 forecasters 0.19 (difference not significant, p=0.85), always-50% baseline 0.25 (p=0.026).
  - The models said "yes" on average 57% of the time, although only 45% of questions resolved "yes".
  - Showing models the human median improved Brier scores by 17% for GPT-4 and 28% for Claude 2.
  - Individual models were poorly calibrated and overconfident.

  — [Science Advances](https://www.science.org/doi/10.1126/sciadv.adp1528); [arXiv 2402.19379](https://arxiv.org/html/2402.19379v6)
- **Self-consistency.** Sampling several reasoning paths and taking the majority vote improves reasoning accuracy (abstract-level) — [Wang et al., arXiv 2203.11171](https://arxiv.org/abs/2203.11171). In debate studies, majority voting without discussion often matched or beat debate — [arXiv 2509.05396](https://arxiv.org/html/2509.05396)
- **Retrieval plus aggregation.** A retrieval-augmented LLM forecaster that aggregates many samples approached human-crowd Brier scores (abstract-level) — [Halawi et al., arXiv 2402.18563](https://arxiv.org/abs/2402.18563)
- **Ensembling in finance.** An equal-risk composite of six LLM agent variants had about 0.4 correlation with the index and, blended with the index, raised the portfolio Sharpe — [arXiv 2602.23330](https://arxiv.org/html/2602.23330v1)

### Inferences
- For trading forecasts, a practical default is to take N independent samples or models, aggregate them by median or trimmed mean, and then recalibrate on out-of-sample history, for example with Platt or isotonic scaling. This has better evidence than persona debate.

### Gaps
- I found no finance-specific study measuring calibration (for example a Brier score on the sign of returns) of LLM ensembles compared with debate.
