# Data Handling and Leakage for LLM News-Driven Equity Strategies

Scope: the data layer (news pipelines, point-in-time integrity, storage) and the look-ahead / memorisation problem when evaluating LLMs on historical data. Research conducted 2026-09-28. Budget-limited (about 25 tool calls), so some practitioner topics (dedup tooling, vendor pricing) are thinner and flagged in Gaps.

## 1. Look-ahead / memorisation bias in LLM financial forecasting, and mitigations

### Takeaway
The evidence is now strong (2025–2026) that general-purpose LLMs memorise pre-cutoff market outcomes, and that prompting ("don't use future knowledge") and entity/date masking do not reliably stop this. Pre-cutoff backtests of off-the-shelf LLMs are not credible. The defensible options are (a) evaluate only after the model's *effective* cutoff, (b) use point-in-time (PiT) model families with dated checkpoints, or (c) run a contamination diagnostic such as Lookahead Propensity and report results conditional on it. Masking helps with *distraction* but does not remove memorisation.

### Cited Findings
**Evidence that LLMs "know" outcomes**
- Lopez-Lira, Tang & Zhu (Apr 2025, rev. Dec 2025): LLMs "have memorized economic and financial data, recalling exact values before their knowledge cutoff"; "instructions to respect historical boundaries fail to prevent recall-level accuracy"; anonymisation is ineffective because "LLMs reconstruct entities and dates from minimal context"; "post-cutoff, we observe no recall"; "memorization extends to embeddings"; counterfactual forecasting ability is "non-identified when the model has seen the realized values." — [arXiv 2504.14765](https://arxiv.org/abs/2504.14765)
- Gao, Jiang & Yan (CUHK, 2025/2026), "Detecting Lookahead Bias in LLM Forecasts": the Lookahead Propensity (LAP) diagnostic queries the model with only firm name, ticker and target date (no news) and reads first-token probabilities for up/down/unknown; LAP = P(up)+P(down). With Llama-3.3-70B (Dec 2023 cutoff), mean LAP ≈ 0.88 on the stock-news sample (peaking 2020) vs ≈ 0.05 for earnings calls; in the post-cutoff 2024 period LAP collapses (max < 1e-4). A 1-s.d. increase in LAP raises the LLM headline-signal effect by ~0.067 pp (~32% of baseline); for earnings-call capex forecasts, +~12% (t = 2.01). The pure "recall" signal (P(up)−P(down) with no news) predicts returns with t = 3.53, concentrated in high-LAP observations. — [arXiv 2512.23847](https://arxiv.org/html/2512.23847)
- DatedGPT authors report that models with lookahead exposure show a statistically significant premium of 26.4 bp per s.d. (t = 10.65) on news-headline return prediction relative to the lookahead-free setup. — [arXiv 2603.11838](https://arxiv.org/html/2603.11838)
- FinCAD (Li, Wang & Ma, Edinburgh, v2 Aug 2026) frames "parametric look-ahead bias": correcting it cut in-sample backtest returns by up to 67.1% across five 7–14B models on five mega-caps, while 2025 out-of-sample Sharpe changed by only ±0.10 — i.e. most in-sample alpha on mega-caps was memory. — [arXiv 2605.24564](https://arxiv.org/html/2605.24564)
- Look-Ahead-Bench (Benhenda, Jan 2026): standard LLMs (Llama 3.1 8B/70B, DeepSeek 3.2) show "significant lookahead bias … as measured with alpha decay" across regimes, while PiT models (Pitinf-Small/Medium/Large) do not show the same decay. Single-author, vendor-linked benchmark (PiT-Inference) — treat as weaker evidence. — [arXiv 2601.13770](https://arxiv.org/abs/2601.13770)
- Audit of 164 LLM-in-finance papers (2023–2025): look-ahead bias discussed in only 26.8%, survivorship bias in 1.2%; no bias discussed in more than 28% of studies. — [Kong et al., arXiv 2602.14233 (Feb 2026)](https://arxiv.org/html/2602.14233v1)

**Anonymisation / entity masking**
- Glasserman & Lin (Sep 2023): stripping company identifiers from headlines; in-sample, *anonymised* headlines produced *higher* returns — a "distraction effect" (general knowledge about the firm interferes with sentiment reading) that outweighed look-ahead bias, stronger for large firms. Out of sample, look-ahead bias was not a concern but distraction could still be. — [arXiv 2309.17322](https://arxiv.org/abs/2309.17322)
- Contradicting/qualifying: Lopez-Lira et al. find masking is ineffective against recall because models reconstruct entities/dates from context. — [arXiv 2504.14765](https://arxiv.org/abs/2504.14765)

**Post-cutoff evaluation**
- Lopez-Lira & Tang, "Can ChatGPT Forecast Stock Price Movements?" (v6, Oct 2025) deliberately used post-knowledge-cutoff headlines; GPT-4 reaches ~90% portfolio-day hit rates on initial reactions; scores predict drift "especially for small stocks and negative news"; strategy returns decline as LLM adoption rises. — [arXiv 2304.07619](https://arxiv.org/abs/2304.07619)

**Point-in-time (time-restricted) model families**
- ChronoBERT / ChronoGPT (He, Lv, Manela, Wu, Feb 2025): annual vintages 1999–2024, first checkpoint on 460B tokens of pre-2000 text, +65B tokens per year; long-short decile Sharpe 4.80 on news vs 4.90 for Llama 3.1 and 4.18 for BERT; lookahead bias in that application estimated as "relatively modest." — [arXiv 2502.21206](https://arxiv.org/html/2502.21206v1)
- DatedGPT (Yan, Tang, Gao, Jiang, Lu; 2026): twelve 1.3B models, ~100B tokens each, annual cutoffs 2013–2024, from FineWeb-Edu filtered by crawl year, plus a time-aware instruction set (~60k QA/year); annualised Sharpe 3.20 on 61k firm-day headlines in a lookahead-free setup. — [arXiv 2603.11838](https://arxiv.org/html/2603.11838)
- PIT models (Kelly, Malamud, Schwab, Xu): PIT-1.5B (170B tokens) and PIT-4B (1T tokens) with *monthly* checkpoints 2013–2024; HellaSwag 72.2 vs 76.0 for LLaMA-7B/Gemma-3-4B; mega-cap news-embedding portfolio Sharpe up to ~0.80, 3–4x the ChronoGPT baseline. — [arXiv 2607.11889](https://arxiv.org/html/2607.11889v1). Note: the fetched page gave a date of 24 Apr 2026 while the arXiv ID implies July 2026 — date uncertain.
- NoLBERT is another small time-restricted encoder on Hugging Face. — [HF alikLab/NoLBERT](https://huggingface.co/alikLab/NoLBERT/blob/main/README.md)
- Sarkar & Vafa, "Lookahead Bias in Pretrained Language Models" (SSRN 2024; ICML 2025) is the canonical framing paper for this problem. — [SSRN 4754678](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4754678), [ICML 2025](https://icml.cc/virtual/2025/51018) (content not fetched; cite for framing only).

**Inference-time debiasing**
- FinCAD: contrastive decoding that subtracts logits from a "memory-activation" prompt, (1+α)M(x_ctx) − αM(x_prior), with per-entity/per-date α; general-benchmark accuracy changed by ≥ −1.7 points for 4 of 5 models; Spearman rank agreement between in-sample and 2025 model rankings rose from 0.779 to 0.846 across 11 LLMs. Needs logit access (open weights). — [arXiv 2605.24564](https://arxiv.org/html/2605.24564)

**Determining a model's effective cutoff**
- "Dated Data" (Cheng et al., Mar 2024): *effective* cutoffs, estimated by probing the model against many dated versions of a resource, "often differ from reported cutoffs," because CommonCrawl dumps include much old data and near-duplicate/semantic-duplicate handling is imperfect. — [arXiv 2403.12958](https://arxiv.org/abs/2403.12958), [code](https://github.com/nexync/dated_data/)
- LAP gives a direct finance-specific cutoff probe: plot mean LAP by month and look for the collapse (Llama-3.3-70B: collapse in 2024 against a stated Dec 2023 cutoff). — [arXiv 2512.23847](https://arxiv.org/html/2512.23847)
- DeepSeek: no official cutoff published; a security firm claims July 2024 from an extracted system prompt, and users have raised the question on the official repo without a definitive answer. — [Knostic](https://www.knostic.ai/blog/exposing-deepseek-system-prompts), [GitHub issue #615](https://github.com/deepseek-ai/DeepSeek-R1/issues/615). Low-quality evidence; test empirically.

### Inferences
- For a paper-trading agent using a frontier API model, the only clean backtest window is after the model's *measured* effective cutoff, plus some buffer, and live forward paper-trading is the gold standard. Every model upgrade resets the clean window. Log the model version and date for each decision.
- For historical research, use open-weight models where you can run LAP (it needs first-token probabilities) and report results split by LAP tercile. If the edge sits in high-LAP names, it is memory.
- Anonymise names and tickers anyway: it reduces distraction (Glasserman & Lin), which is a real gain even out of sample. But do not treat it as a leakage fix. Also strip dates and use relative time ("day t"), since dates are an easy cue for recall.
- Mega-caps and well-known episodes (2020 COVID, 2022 rate shock) are where contamination is worst. Small-cap and less-covered names in post-cutoff windows are cleaner tests, and this is where the post-cutoff alpha also concentrates (Lopez-Lira & Tang).
- PiT models (ChronoGPT, DatedGPT, PIT-4B) are small (≤4B). They suit embedding/scoring pipelines and robustness checks, not agentic reasoning. A practical design is to replicate the signal with a PiT model as a contamination control.

### Gaps
- Did not fetch Sarkar & Vafa's full text, so their specific quantification is not included.
- No authoritative DeepSeek (V3/R1/V3.x) effective cutoff found; only secondary claims.
- No systematic evidence on memorisation in closed frontier models from 2025–2026 (GPT-5-class, Claude 4-class) specifically on returns; most quantified work uses Llama/GPT-4-era models.

## 2. Point-in-time news data integrity

### Takeaway
The academic literature gives strong evidence that *novelty* matters: stale or recycled news is priced differently, and "new" news carries information. Engineering best practice on timestamps, revisions and dedup is mostly practitioner knowledge. I did not find strong primary sources for it within budget, so most of this section is inference. The key discipline is: every item needs an "available-at" timestamp you captured yourself, and all joins must be as-of on that timestamp.

### Cited Findings
- Vendor timestamps: Alpaca's news API (Benzinga-sourced) returns both `created_at` and `updated_at` per article. Articles are revised after publication, so the backtest should use the first-seen version, not the latest. — [Alpaca docs](https://docs.alpaca.markets/us/docs/historical-news-data)
- SEC EDGAR dissemination timing: filings are accepted Mon–Fri 6:00–22:00 ET; submissions after 17:30 ET (22:00 for Forms 3/4/5) are disseminated the *next business day*. Filing date therefore ≠ public availability time. — [SEC Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
- Stale news: Tetlock (RFS 2011) tests whether investors distinguish new from old (reprinted) information about firms, using a text-similarity "staleness" measure. — [RFS abstract](https://academic.oup.com/rfs/article-abstract/24/5/1481/1613314), [working paper PDF](https://business.columbia.edu/sites/default/files-efs/pubfiles/3099/Tetlock%20Fit%20to%20Reprint%2010%2010.pdf)
- News novelty (entropy): Glasserman, Mamaysky & Qin (Sep 2023) measure novelty with an LSTM trained on 1.6M Reuters articles over 27 years. A 1-s.d. rise in entropy predicts a 2.8% lower S&P 500 return over 12 months in-sample; out-of-sample R² is 0.024–0.051, beating CAPE and EPU. — [arXiv 2309.05560](https://arxiv.org/html/2309.05560)
- Survivorship: only 1.2% of 164 LLM-finance papers discuss survivorship bias. Recommended practice is "dynamic universe construction" that includes delisted names and avoids survivor-conditioned sampling. — [arXiv 2602.14233](https://arxiv.org/html/2602.14233v1)
- Formal treatment: a 2026 paper frames look-ahead-freedom as "temporal non-interference," a verifiable property for backtesting and agentic trading pipelines. — [arXiv 2607.04958](https://arxiv.org/html/2607.04958v1) (not fetched; title/abstract level only).

### Inferences
- Store three timestamps per item: vendor `published_at`, vendor `updated_at`, and your own `ingested_at` (wall-clock, UTC). In backtests, set `available_at = max(published_at, ingested_at_if_live)` plus a latency buffer. For historical vendor pulls, where ingestion time is unknown, add a conservative lag (for example, trade at the next bar open, never the bar containing the timestamp).
- Revisions: keep every version (append-only). The model sees the version that existed at decision time. Headline edits and ticker-tag additions after the fact are a quiet source of leakage, for example tickers added to an article hours later.
- Dedup of syndicated news: a standard pipeline is exact-hash, then MinHash/LSH (Jaccard on shingles, for example ≥0.8) for near-duplicates, then embedding cosine clustering within a time window (for example 24–72h) for same-event rewrites. Keep the earliest item as canonical and use the cluster size as a "coverage intensity" feature. (Practitioner convention; no primary source fetched.)
- Novelty feature: compute cosine similarity of a new item's embedding against the firm's trailing news. Tetlock's and Glasserman et al.'s results suggest treating low-novelty items differently, since the stale-news reaction tends to reverse.
- Universe: build the tradeable universe from historical index membership as of each date, including delisted tickers. Map tickers to a permanent ID (CIK/FIGI), because ticker changes break joins.

### Gaps
- No primary source fetched quantifying vendor latency (publication-to-API delay) for Benzinga, Finnhub or Polygon.
- Tetlock's specific effect sizes (magnitude of reversal after stale news) were not retrieved.
- No peer-reviewed benchmark found comparing MinHash vs embedding dedup on financial news.

## 3. Structuring news for LLMs (raw vs summaries vs clusters; context length; retrieval)

### Takeaway
Long context degrades with position ("lost in the middle"), so feeding many raw articles into one prompt is inferior to deduplicated, clustered, per-event inputs placed at the start or end of the prompt. Headlines alone already carry most of the published signal in the key papers.

### Cited Findings
- Liu et al., "Lost in the Middle" (2023; TACL 2024): performance is highest when relevant information is at the beginning or end of the context and degrades significantly in the middle (U-shaped curve), even for long-context models. — [arXiv 2307.03172](https://arxiv.org/abs/2307.03172), [TACL](https://aclanthology.org/2024.tacl-1.9/)
- Most return-prediction results use headlines only: Lopez-Lira & Tang ([arXiv 2304.07619](https://arxiv.org/abs/2304.07619)), Glasserman & Lin ([arXiv 2309.17322](https://arxiv.org/abs/2309.17322)), DatedGPT (61k firm-day headlines; [arXiv 2603.11838](https://arxiv.org/html/2603.11838)).
- Embedding-based pipelines also work: PIT models build portfolios from news *embeddings* plus random-feature regressions. — [arXiv 2607.11889](https://arxiv.org/html/2607.11889v1)
- Memorisation "extends to embeddings," so embedding pipelines built on non-PiT models are also contaminated pre-cutoff. — [arXiv 2504.14765](https://arxiv.org/abs/2504.14765)
- Glasserman & Lin's distraction effect implies extra firm context can *hurt* sentiment extraction for large firms. — [arXiv 2309.17322](https://arxiv.org/abs/2309.17322)

### Inferences
- Recommended layering: (1) dedup clusters → one canonical "event" record per cluster with earliest timestamp, source count and novelty score; (2) per-event LLM scoring on short text (headline plus lede); (3) only then an aggregation or "narrative" step over scored events for the agent. This keeps each LLM call short and auditable.
- Summaries generated by an LLM become a leakage path if the summariser is post-cutoff relative to the event. Store summaries with the model version and generation date, and regenerate them with the evaluated model for backtests.
- Retrieval must be time-filtered at the index level (`available_at <= t`), not by prompt instruction.

### Gaps
- No finance-specific study found comparing raw article vs summary vs cluster inputs on return prediction.

## 4. Data sources/APIs for retail and small funds

### Takeaway
Free and cheap sources are adequate for research but have coverage and history limits. Alpaca/Benzinga (from 2015, ~130 articles/day) is the most convenient for a US-equity paper-trading agent. EDGAR is free and authoritative but has dissemination timing quirks. GDELT is broad but metadata-only and noisy.

### Cited Findings
- Alpaca News API: sourced from Benzinga; history from 2015; "an average of 130+ news articles per day"; stocks and crypto; fields include created_at, updated_at, symbols, content; real-time websocket stream available. — [Alpaca historical news](https://docs.alpaca.markets/us/docs/historical-news-data), [Alpaca real-time news](https://docs.alpaca.markets/us/docs/streaming-real-time-news)
- Benzinga direct offers a news websocket stream. — [Benzinga docs](https://docs.benzinga.com/ws-reference/data-websocket/get-news-stream)
- SEC EDGAR: free; maximum 10 requests/second; a declared User-Agent with contact email is required; JSON submissions and XBRL APIs on data.sec.gov; history from 1994Q3; dissemination timing as in Section 2. — [SEC](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
- GDELT 2.0: updates every 15 minutes; translates 65 languages; 2.0 format starts 19 Feb 2015; stores events, GKG metadata and URLs/tone measures rather than full article text. — [GDELT blog](https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/). Industry commentary (Sept 2026) argues GDELT falls short for compliance-grade use. — [FinTech Global](https://fintech.global/2026/09/21/why-gdelt-falls-short-for-compliance-teams/) (not fetched)
- Finnhub: official rate-limit and pricing pages exist but did not render on fetch. Secondary sources describe a free tier of about 60 calls/min with limited news history. — [Finnhub rate limits](https://finnhub.io/docs/api/rate-limit), [Finnhub pricing](https://finnhub.io/pricing) (figures unverified)

### Inferences
- Licensing: Benzinga content via Alpaca is licensed for the user's own use. Redistribution (for example, showing full text on a public dashboard) likely needs a separate agreement. Check terms before publishing.
- ~130 articles/day across all tickers means sparse per-name coverage outside large caps. Pair it with EDGAR 8-Ks for small caps.

### Gaps
- Could not verify Finnhub free-tier history depth or rate limit from a primary source.
- Polygon.io (now Massive) news and Tiingo news terms were not researched within budget.
- No reliable source on earnings-call transcript APIs for retail (for example FMP, API Ninjas) and their licensing.

## 5. Storage, reproducibility, audit trails, pre-commitment

### Takeaway
There is little academic literature specific to this. The literature's recommendations (temporal sanitation, disclosing model cutoffs, point-in-time data) translate directly into engineering rules: immutable raw archives, as-of joins, full logging of prompts, model versions and outputs, and time-stamped pre-commitment of decisions before outcomes are known.

### Cited Findings
- The structural-validity framework recommends "temporal sanitation" (non-anticipativity, disclosed training cutoffs, PiT data), abstention as a valid output, and realistic execution: "execute trades at delayed prices" and account for latency and costs. — [arXiv 2602.14233](https://arxiv.org/html/2602.14233v1)
- Survey respondents: 74% of 50 practitioners/researchers say bias-evaluation tools are "scarce" or "non-existent." — [arXiv 2602.14233](https://arxiv.org/html/2602.14233v1)
- A 2026 paper proposes look-ahead-freedom as a *verifiable* correctness property ("temporal non-interference") for agentic trading pipelines. This supports designing pipelines so leakage can be tested mechanically. — [arXiv 2607.04958](https://arxiv.org/html/2607.04958v1)

### Inferences
- Raw layer: append-only, write-once storage of every API response (JSONL/Parquet partitioned by ingest date), stored with its content hash and `ingested_at`. Never overwrite; revisions become new rows.
- Derived layers (dedup clusters, scores, features) are versioned by code commit, model id and prompt hash, so any past decision can be rebuilt exactly (DVC, lakeFS, Delta/Iceberg time travel, or git-tracked Parquet for small scale).
- Decision log per trade: timestamp, input item IDs, full prompt, model name and version string, temperature/seed, raw output, parsed action. Commit the log (for example to git in GitHub Actions) *before* market outcome is observable. The commit timestamp is a cheap, third-party-verifiable pre-commitment.
- Mechanical leakage tests: (a) assert that every feature row's max(`available_at`) ≤ decision time; (b) a "shuffle-future" test, where perturbing any data after t must not change decisions at t (the non-interference idea); (c) the LAP-by-month plot for the model in use.
- Temperature 0 does not guarantee determinism on hosted APIs. Store outputs rather than relying on re-running them.

### Gaps
- No primary source found quantifying API nondeterminism for current hosted models.
- No academic source found specific to storage patterns for LLM trading; recommendations here are engineering inference.
