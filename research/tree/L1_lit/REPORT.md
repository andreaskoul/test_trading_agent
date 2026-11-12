# L1: literature on preprocessing for machine-learning return models

*An in-project reading by a separate AI session (2026-11-13), saved by the coordinating session because the agent's
writes were refused. It is not an outside review. Access labels: [read] = passage read in the source; [abstract] =
abstract or publisher page only; [search] = search-engine or third-party summary; [reasoning] = inference; [code] =
read in this repository. The coordinating session re-checked the survivorship counts from `dev.npz` (it measures
23.5% of eligible Thursday name-weeks 2013-2019 without a target; the agent's 27.3% used a different span). Actions
taken: PREREG Layer 3, Amendment 4; `LAYER3_LOG.md` step 6.*

**Most important finding:** survivorship in the development panel, not disclosed in `research/tree` docs before
Amendment 4. 241 of the 738 S&P 500 names ever eligible have no yfinance price; on average 136 of 501 eligible names
per day have no price (2013: 146 of 497; 2019: 80 of 505).

## 0. Our pipeline, as read [code]

* **Target y5** (`panel400.py:75-87`): sum of simple daily returns over sessions t+2..t+6 minus beta[t] times the same
  sum for SPY; demeaned across eligible names; NaN unless prices exist at both t and t+6 (`:84-85`).
* **Beta** (`:72-74`): 2/3 × 252-day rolling beta on clipped returns + 1/3; too little history → NaN → 1.0.
* **Z** (`:69`): five characteristics, z-scored per date, not winsorised.
* **D_ensembles**: Z clipped at ±4 and /4; 22 more inputs as cross-sectional ranks; NaN→0 (`:49-51`); target ranked
  per date; early stopping on the last 104 training Thursdays with an 8-row gap (`:86-98`).
* **C_features**: ranks scaled to sd 1, missing→0 (`:57-70`); target standardised per day, clipped ±3 (`:80`).
* **M2** (`ipca.py:79-80`): `xnorm` standardises the target per period, clips ±3.
* **Q1** (`Q1_seqnet/seq.py:58-79`): return channels as cross-sectional z-scores clipped ±5, or ranks; NaN→0.
* **Harness**: expanding window, annual refit; training ends 8 sessions before the year, label spans 6 rows
  (`harness.py:46-49`); equal-weight Spearman IC over eligible names with a y5 (`:75`).
* **Broad universe** (`panel_broad.py:36-41`, `fetch_broad.py:71`): `adjustment=all` bars; eligible if close > $5,
  ≥ 252 sessions, top 1,500 by 63-day dollar volume.

## 1. Design choices: literature vs our pipeline

| Design choice | Literature | Reported effect | Ours | Gap? |
|---|---|---|---|---|
| Characteristic scaling | GKX 2020: ranks to [-1,1] each period, following KPS 2019 and FNW [read]. CPZ: cross-sectional quantiles, "a standard transformation" used by KPS, KNS, FNW [read]. Qlib Alpha360 default: ProcessInf, ZScoreNorm, Fillna; Alpha158 none by default [read, code] | No rank-vs-z ablation in the papers read | Ranks in D, C, Q1-rank; Z z-scored, not winsorised (`panel400.py:69`) | partial |
| Per-sample normalisation of sequence inputs | Chen et al. 2026 (arXiv 2609.07122), CSI300 5-minute bars, 3 seeds [read] | Instance norm raised rank IC in all 8 encoders: GRU 0.0362→0.0878, LSTM 0.0372→0.0939; centering alone +0.0518 on GRU; scale-only −0.0028 (GRU), −0.0103 (linear); gain from price channels | Q1 uses returns, so the price-level offset is absent [reasoning]; returns not scaled per stock | no (offset); open (scaling) |
| Missing characteristics | GKX: cross-sectional median [read]. CPZ, KPS, FNW: complete cases only [read, CPZ fn 28]. BLLP: not missing at random; median imputation distorts [read]. FHNW 2025: conditional-mean imputation + WLS [abstract] | BLLP: median imputation "roughly twice as large imputation errors" as B-XS; >70% of firms (≈half of market cap) miss ≥1 of 45 characteristics; firms with missing values earn lower returns [read]. FHNW: "improved out-of-sample predictability" [abstract] | Missing → 0 (median rank), no indicator; price-only inputs, gaps mostly short history | partial (low stakes) |
| Target | GKX: monthly excess return, Huber loss [read]. MASTER: close τ+1 to τ+d, z-scored daily [read]. Qlib: DropnaLabel, CSZScoreNorm; label Ref(close,-2)/Ref(close,-1)-1 [read]. Poh et al. 2020: learning-to-rank vs regress-then-rank [read] | GKX: Huber versions "perform better" [read]. Poh et al. (monthly momentum, NYSE, no costs): Sharpe 0.265 MLP vs 2.156 LambdaMART, 1.970 ListNet [read] | Beta-hedged, demeaned 5-day, next-close entry; ranked or z-clipped in each model; A_loss tested losses; Q3 registered | no; partial (ranking losses) |
| Microcaps, filters, weighting | GKX: no price/share-code filter, ≈6,200 stocks/month [read]. HXZ: NYSE breakpoints, value weights [abstract]. JKP: capped value weights at NYSE 80th pct [read]. ACM [abstract]. CPZ: fit on all, score on large [read] | GKX NN4 Sharpe 1.35 VW vs 2.45 EW [read]. HXZ: 286 of 447 anomalies (64%) insignificant at 5% [abstract]. JKP: capped VW +8.5 points replication rate [read]. ACM: excluding microcaps/distressed/volatile periods "considerably attenuates profitability" [abstract]; −62/−68/−80% [search]. CPZ GAN Sharpe 1.4 (largest 1,500) vs 0.9 (largest ≈550) [read] | Large/mid caps; equal-weight IC | partial: no VW or size-bucket scoring |
| Survivorship, delisting | Shumway 1997: CRSP omits delisting returns, mostly negative [abstract]. JKP: missing performance delisting return → −30% [read] | Shumway-Warther 1999 (Nasdaq): −55% [search] | Dev panel: gap above. Broad panel: name stopping inside window gets y5 NaN (`panel400.py:84-85`) | **yes** |
| Look-ahead in filters | GKX lags characteristics 1/4/6 months; JKP lags accounting 4 months [read] | — | Price features causal; but the $5 filter reads `adjustment=all` closes (`panel_broad.py:38`), which embed later splits/dividends [reasoning] | **yes (small)** |
| Purging / embargo | López de Prado ch. 7 [search]; Chen et al. 2-day embargo [read]; GKX disjoint periods, yearly refit [read] | — | 8-row gap > 6-row label span; walk-forward; D's early stop keeps an 8-row gap | no |
| Validation, windows | GKX: 18y train, 12y validation rolled, 30y test [read]. MASTER, Qlib: one split, tuned on validation IC [read] | — | Expanding, annual refit; PREREG + holdout; X3 online (no gain) | no |
| Seeds, ensembles | GKX several seeds; MASTER 5; Qlib 20; CPZ 9 [read] | Qlib CSI300 Alpha158 across 20 seeds: ICIR ±0.00–0.05, IR up to ±0.46 (LSTM) [read] | 3 seeds, ranks averaged | partial |
| Complexity | KMZ 2024 is market timing, not cross-section [search]. JKP replication 77.3% (mega), 81.5% (large) [read]. CPZ: FFN and linear "mainly fitting small stocks" [read]. Leippold 2022: retail-driven small stocks [search] | see cells | Small models; dev IC s.e. ≈0.01 | context |
| Costs | JKMP 2025: cost-blind ML relies on "fleeting small-scale characteristics", poor net [abstract]. ACM high turnover [abstract] | No numbers reached | 5 bp; X2 smoothing; M1 band (X4 t 2–2.65) | partial |

## 2. Ranked changes to test (development data)

1. **Measure and repair the development-panel survivorship gap.** Fill missing names from Alpaca inactive symbols
   (2016 on); rescore reference models and M2/X4 leaders on 2016-19. Control: same models on the current panel. Sign
   unknown. Cost medium. No leakage; 2013-15 not repairable this way.
2. **Keep delisting returns in y5.** (a) return to last price then 0; (b) (a) plus −30% for non-merger delistings
   (needs a merger flag; otherwise a bound). Control: current drop rule. Cost low.
3. **Unadjusted prices for the $5 and dollar-volume filters.** Fixes the look-ahead. Control: current rule. Cost low.
4. **Score by size bucket and capped value-weighted spread** (descriptive). Control: equal-weight IC. Cost low.
5. **Rank Z to [-1,1], or winsorise 1/99% before z-scoring.** Basis: GKX/CPZ/KPS convention; no ablation found.
   Control: ridge reference and D on current Z.
6. **Missing indicators + past-only forward fill** for long-window features. Basis: BLLP. Control: D_hgb_mh.
7. **Per-stock volatility scaling of Q1 return inputs.** Basis: Poh et al. (no ablation); Chen et al. scale-only no
   help on prices. Possibly null.
8. **10 seeds for network finalists.** Lower variance, not higher mean.
9. **Ranking objective for trees (Q3, registered).** Poh et al.'s gap is against a weak MLP without costs; expect far
   less [reasoning].

Leakage checks that passed [code]: training ends 8 sessions before the year with labels at t+2..t+6; D's early-stop
split keeps an 8-row gap; C's market-state percentiles expand causally; beta[t] uses returns ≤ t. Minor: y5 sums
simple returns rather than compounding.

## 3. Search log

1. alphaXiv, GKX by title: not indexed.
2. alphaXiv, CPZ (1904.00745): read pp. 1, 21-40, 49, 69-71.
3. alphaXiv, MASTER (2312.15235): read in full.
4. Web fetch of GKX PDF (dachxiu.chicagobooth.edu): text extracted; sample, imputation footnotes, split, Table 1 text,
   portfolio section read.
5. Qlib GitHub: LightGBM Alpha158 yaml, benchmarks README, handler code read.
6. Two alphaXiv discovery searches (missing data; complexity/replication/cost): core finance papers not on arXiv.
7. Web searches for BLLP, ACM, HXZ, JKMP, KMZ, Leippold, Shumway, FHNW, López de Prado: summaries only.
8. ACM "PDF" at fre.snu.ac.kr was a Korean slide deck; not used.
9. RePEc abstract pages: ACM, HXZ (truncated), BLLP.
10. alphaXiv discovery on preprocessing ablations: 2609.07122, read in full.
11. alphaXiv PDF reads: BLLP NBER draft (pp. 1-4, 13-16, 34, 48, 52, 55, 64-71); JKP w28432 (pp. 1-8, 11, 29-37, 47-50).
12. AQR JKMP PDF: abstract only.
13. alphaXiv, Poh et al. (2012.07149): read in full.

Blocked or not reached: Shumway full text (JSTOR); ACM full text; JKMP tables; KMZ full text; Leippold full text
(open access, not opened); López de Prado's book; Elicit not run.

## 4. Bibliography

* Gu, Kelly, Xiu 2020, RFS 33(5) — read (sections above)
* Chen, Pelger, Zhu, arXiv 1904.00745 — read
* Li et al., MASTER, AAAI 2024 — read
* Qlib GitHub benchmarks and code — read; Qlib paper not opened
* Chen et al. 2026, arXiv 2609.07122 — read
* Bryzgalova, Lerner, Lettau, Pelger, Missing Financial Data (RFS 2025; NBER draft Jan 2023) — read (pages above)
* Freyberger, Höppner, Neuhierl, Weber, RFS 2025 — abstract
* Jensen, Kelly, Pedersen, JF 2023 — read
* Hou, Xue, Zhang, RFS 2020 — abstract
* Avramov, Cheng, Metzker, Management Science 2023 — abstract; percentages from press coverage (search)
* Jensen, Kelly, Malamud, Pedersen, RFS 2025 — abstract
* Kelly, Malamud, Zhou, JF 2024 — search
* Leippold, Wang, Zhou, JFE 2022 — search
* Shumway, JF 1997 — abstract (−30% as JKP apply it, read); Shumway-Warther 1999 — search
* Poh, Lim, Zohren, Roberts, arXiv 2012.07149 — read
* López de Prado 2018, ch. 7 — search
* Kelly-Pruitt-Su 2019, Freyberger-Neuhierl-Weber 2020 — not opened; cited as GKX and CPZ cite them
