# Tree search: evaluation after two phases, and the plan for layer 3

*2026-11-12. From `STATE.md`, `PREREG.md` (phase-1 and phase-2 results) and `HOLDOUT2_RESULT.json`. Plan only.*


## 0. The tree as it stands (checked against PHASE2_PLAN.md, 2026-11-12)

```
ROOT  S&P 500 daily panel 2009-2025 · weekly rank IC of 5-session hedged returns · dev 2013-19 · holdouts sealed
│
├── PHASE 1  EXPLORE (60)                                     dev best IC (t)       outcome
│   ├── A  loss mathematics            12   mse_rank          .0188 (2.45) ─┐
│   ├── B  network architecture        11   mlp_res_deep      .0162 (1.96)  │ pruned: no gain over small MLP
│   ├── C  features & econometrics     15   FM ridge, 32 f.   .0209 (2.29)  │ → feeds X1
│   ├── D  trees & ensembles            7   hgb 4 horizons    .0236 (2.41) ─┤
│   └── E  regime-adaptive             15   kernel + panic    .0167 (1.62)  │ → panic overlay feeds X1
│                                                                           │
├── PHASE 1  EXPLOIT (54)                                                   │
│   ├── X1 combine                     11   8p trees+FM+MLP   .0282 (2.91) ─┤
│   ├── X2 trading costs               11   smoothing         cost −1.0..−1.6%/yr; hurt MASTER in holdout
│   └── X3 online updating             32   (14 pairs)        no gain: pruned
│                                                                           │
├── HOLDOUT 1  S&P 500 2020-25 (spent) ◄────────────────────────────────────┘
│       X1_8p .0224 (2.11) fail by 0.0006 · D_hgb_mh .0185 (1.89) fail · A_mse_rank .0078 (0.79) fail
│
├── PHASE 2  TRACK M: methods (dev S&P 500 2013-19; read S&P 400 2019-25)
│   ├── M1 Garleanu-Pedersen trading   18   no-trade band     paired t 2.5 / 2.3 → construction rule
│   ├── M2 IPCA                        20   M05_U             .0224 (2.27) ──► READ S&P 400: .0183 (2.17) PASS
│   ├── M3 conditional autoencoder      8   ca2_c32_k3        .0213 (2.00)  not beaten its control; seed ensemble unrun
│   ├── M4 SDF shrinkage               12   S04 unshrunk 324  .0141 (3.67) ──► READ S&P 400: .0033 (0.86) fail
│   ├── M5 peer graph (10-K)           13   R4 peer ridge     .0186 (2.21)  edges lower IC in 6 of 7 pairs
│   ├── M6 self-supervised embeddings  12   con16_embZ        .0191 (2.08)  embedding adds nothing over control
│   ├── M7 double ML                   (used inside N1-N3)                  done
│   └── M8 nonlinear covariance         0   NOT RUN                         (M1 used linear Ledoit-Wolf only)
│
├── PHASE 2  TRACK N: new information over frozen MASTER (gate: increment t >= 1.5)
│   ├── N1 fundamentals (SEC XBRL)     23   fm_fixed70        +.0047 (2.29) ──► READ S&P 500: −.0001 (−0.02) fail
│   ├── N2 short volume (FINRA)        11   0.7/0.3 blend     +.0020 (1.14)  below gate (double ML t 1.61)
│   ├── N3 intraday (30-min bars)      20   0.8 M − 0.2 id21  +.0030 (1.53)  = 1-month reversal, not intraday
│   └── N4 news                         0   NOT RUN
│
└── PHASE 2  EXPLOIT                    0   NOT RUN
```

Total 251 logged configurations; 6 finalists read; 1 pass.

**Checked against PHASE2_PLAN.md:** M8 was planned and never run; M3's seed ensemble never ran; the planned phase-2
exploitation layer (combinations of passing branches) never ran; N4 never ran; the reported band comparison failed on
a bug (fixed after the reads, reported only); and the finalist rule was applied unevenly (Correction in PREREG.md).

## 0b. The policy, applied again to every node

The policy, written down now: **(1)** a node that failed a holdout is closed on that panel; **(2)** a node whose
method did not beat its declared control in development is pruned; **(3)** a node that passed, or failed narrowly with
at least 75% of its development IC kept, is exploited and replicated on a fresh panel; **(4)** an unrun node gets one
cheap visit only if it brings new information or its parent family is still open; **(5)** at most two finalists per
read, each with a declared control, chosen by a rule written before selection.

| Node | Rule | Decision for layer 3 |
|---|---|---|
| M2 IPCA | 3 (passed) | **Exploit:** replicate on the broad survivorship-free universe (L3.1); MASTER + IPCA blend; band; forward book |
| D trees 4 horizons | 3 (78% kept, near miss) | **Replicate** on L3.1 as the second finalist |
| X1 combined | 3 (79% kept, near miss) | Not a third finalist (rule 5). Its pieces are D + C; D carries it |
| M1 band | construction | **Carry** as the default book rule; it raised Sharpe slightly on both S&P 400 books |
| X2 smoothing | construction | Superseded by the band (M1 showed the band dominates smoothing) |
| A, M4, N1 | 1 | Closed |
| B, X3, M3, M5, M6 | 2 | Pruned. M3's seed ensemble is not run: its parent failed its control |
| N2 short volume | 2 (below gate) | Pruned as an increment; kept as its own validated forward book |
| N3 intraday | 2 | Pruned |
| M8 nonlinear covariance | 4 | **Pruned without a visit:** its only use is the mean-variance aim, and M1's mean-variance aims lost to the band in both covariance versions |
| N4 news | 4 (new information) | **One visit:** count and cost first, then dictionary features, judged as an increment over MASTER |
| Phase-2 exploit layer | 3 | **Run** as L3.2 on development data: MASTER + IPCA (correlation 0.26), IPCA + band |

The plan below (L3.1-L3.6) already matches these decisions; the two changes are that M8 and M3's ensemble are pruned
explicitly, and that L3.1's two candidates each carry a declared control: IPCA against C's Fama-MacBeth ridge on the
same 24 characteristics, the trees against the same trees on the 5-session target only.

## 1. State

* 18 branches opened, 17 run (news not started), 251 logged configurations, 2 holdout rounds, 6 finalists, 1 pass
  (IPCA on the S&P 400, Holm p 0.0149).
* Spent samples: S&P 500 2020–2025 (stock selection, phase 1); S&P 400 2019–2025 (IPCA, SDF); S&P 500 2020–2025 again
  for the fundamentals increment. Unspent: everything outside these two indices, and all forward weeks.

## 2. Evaluation

**What the holdouts said about development numbers.**

| Finalist | Development IC (t) | Holdout IC (t) | Kept | Read |
|---|---|---|---:|---|
| X1 combined | 0.0282 (2.91) | 0.0224 (2.11) | 79% | failed by 0.0006 in p |
| D trees, 4 horizons | 0.0236 (2.41) | 0.0185 (1.89) | 78% | failed |
| A ranked-target MLP | 0.0188 (2.45) | 0.0078 (0.79) | 41% | failed |
| **M2 IPCA** | 0.0224 (2.27) | **0.0183 (2.17)** S&P 400 | 82% | **passed**; 0.0121 (1.02) on the S&P 500, descriptive |
| M4 unshrunk SDF | 0.0141 (3.67) | 0.0033 (0.86) | 23% | failed |
| N1 fundamentals increment | +0.0047 (2.29) | −0.0001 (−0.02) | 0% | failed |
| MASTER (reference) | 0.0125 (1.43) | 0.0326 (3.14) | 261% | already validated |

* **The rank-based models kept about 80% of their development IC; the rest kept little or nothing.** Trees, IPCA and
  the combined model generalised; the MLP, the SDF and the fundamentals increment did not.
* **Development t did not predict survival.** The highest development t (SDF, 3.67) kept 23%; MASTER, the weakest in
  development, was the strongest out of sample.
* **The binding constraint is statistical power, not discovery.** With about 300 weekly ICs, the standard error of a
  mean IC is about 0.009, so a model with a true IC of 0.02 reaches t ≈ 2.2: about a coin flip against a Holm
  threshold. Two models with ~80% retention failed by small margins for this reason. Three finalists per read make it
  harder still.

**Exploration against exploitation.**

| | Branches | Configurations | Outcome |
|---|---:|---:|---|
| Exploration | 13 | about 190 | 1 pass (IPCA); 4 finalists that failed; 8 nulls |
| Exploitation | 3 (phase 1 only) | about 55 | cost control (smoothing, band); no gain from online updating; combination added +0.004 in development and kept 79% |

* Phase 2 had **no exploitation round**: each branch went straight to a finalist. Combinations of validated pieces
  (MASTER + IPCA, MASTER + short volume, IPCA + the no-trade band) were never built.
* **Network architecture was the least productive line:** attention, recurrent, convolutional, graph and
  self-supervised designs (branches B, M3, M5, M6; 44 configurations) never beat a small MLP or a ridge.
* **Linear characteristic models and trees on ranks were the most productive line**, together with cost control.
* **New information did not pay on these panels:** intraday, short volume and fundamentals all failed as increments
  over MASTER. News is the one source not yet tried.

## 3. Layer 3: actions

### L3.1 A larger, survivorship-free confirmation sample (raises power for every method)

Build a broad US universe from Alpaca daily bars, which keep delisted symbols: each week, the 1,500 most traded common
stocks by 63-session dollar volume with price above $5, **excluding** the S&P 500 panel names and the 346 S&P 400 names
already read. Point in time by construction (no membership file), 2016–2025. Roughly 1,000 names a week after the
exclusions: the standard error of a weekly IC falls by about √3 compared with the S&P 400 read.

* Use: one read, 2019–2025, of at most **two** candidates fixed before the data is built: IPCA (a survivorship-free
  replication of the pass) and the D trees on 4 horizons (the near-miss with 78% retention). Holm across the two.
* Cost: about 30–60 Alpaca requests through the redacting wrapper; no LLM.

### L3.2 An exploitation round on validated pieces (development data only, then forward)

* MASTER + IPCA on the S&P 500 (correlation 0.26 in the check): fixed 50/50 and 70/30 rank blends, scored on
  2013–2019 only; the 2020–2025 numbers stay descriptive.
* IPCA and the trees with M1's no-trade band, the cost rule that cleared paired t 2 on both bases.
* Fund level, descriptive and forward: core + MASTER book (large caps) + IPCA book (mid caps) + short-volume book, sized
  by the rule in the 21 November study.

### L3.3 Selection discipline before any further read

* Estimate the probability of backtest overfitting (combinatorially symmetric cross-validation, Bailey and López de
  Prado) and the deflated Sharpe ratio for each candidate before choosing finalists; record both.
* At most two finalists per read. Compute each read's power in advance and record it with the registration.

### L3.4 The untested source: news

Branch N4 with Alpaca/Benzinga headlines (2015 onward): first a count of articles per name and week and a cost
estimate; then dictionary features (counts, novelty, Loughran–McDonald tone) with no LLM; embeddings only if the cheap
features clear the development gate. Judged as an increment over MASTER, as N1–N3 were.

### L3.5 Forward records (the only fully clean evidence)

* IPCA forward paper book on S&P 400 and S&P 500 members with membership refreshed weekly, as the registered
  consequence of its pass. Needs the owner's decision: it adds a step to the Friday research job.
* No verdict on any forward book before 26 weeks.

### L3.6 Operations

* At most four agents at once (usage limits stopped agents five times); each keeps `STATE.json`.
* Agents return reports as text; the coordinator saves them.
* Each layer in its own worktree.

## 4. Order

| Step | What | Depends on |
|---|---|---|
| 1 | Register L3.1's two candidates and the universe rule; build the universe; power calculation | nothing |
| 2 | L3.2 exploitation round and L3.3 overfitting estimates (2 agents) | nothing |
| 3 | L3.4 news count and cost estimate | Alpaca keys via the wrapper |
| 4 | L3.1 read | step 1 |
| 5 | L3.5 IPCA forward book | owner decision |
