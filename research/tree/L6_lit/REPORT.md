# L6_lit: literature map of the closed nodes, with 4 proposals (Layer 6, T3)

*Written by the research agent; saved by the coordinating session (condensed, wording kept). An in-project reading, not
an outside review. Access labels: [RD] read directly (alphaXiv, or PDFs extracted locally; quoted passages only);
[AB] abstract only; [SS] search summary only (unverified; no number from it is presented as read); [L1]/[L3] from
earlier in-project reviews; [BG] background knowledge, not read; [RS] reasoning. Nothing here is claimed to be new.
Full sources and labels are in STATE.json.*

## A. Closed nodes: best published version, and whether we tested it

| Node | Best published version | Tested that version? | Could the gap flip it? |
|---|---|---|---|
| Sequence nets (Q1) | Gu-Kelly-Xiu 2020 shallow feed-forward nets [L1 RD]; Jiang-Kelly-Xiu image CNN [BG] | partly | low: gains come from inputs and small names, not the encoder |
| Attention / cross-sectional transformers (Q2) | Kelly-Kuznetsov-Malamud-Xu AIPM, NBER w33351 (June 2026) [RD]: monthly, 132 JKP characteristics, the transformer as SDF. Gross SDF Sharpe 3.6 linear, 3.9 linear with attention, 4.6 for the 10-block transformer | no | plausible only with monthly data, characteristics and decades of history; JKP characteristics are not free for us |
| Ranking losses (Q3, A3) | Poh et al. 2021 LambdaMART [L1 RD], no costs, weak baseline | yes | moderate, through power only (A3 +.008, t 0.52) |
| RL allocation (Q5) | AlphaPortfolio, Cong et al. [SS] | partly | low: needs decades of monthly data |
| Neutralisation (Q8) | Ehsani-Harvey-Li 2023 [L3]; Numerai partial neutralisation [L2 RD] | yes | no |
| Industry-relative (Q7) | Novy-Marx-Velikov 2016 [L3 RD]; Huang et al. 2026, arXiv 2604.19476 [RD]: S&P 500 10-K peer networks, gross Sharpe 0.74-0.82, SIC 0.79, daily rebalancing; monthly 0.50 | partly | low for a weekly book |
| Headline news (N4) | Ke-Kelly-Xiu SESTM [SS]; Chen-Kelly-Xiu LLM news [SS] | partly | low: the effects sit in days 0-1 |
| Insider trading (L5) | Cohen-Malloy-Pomorski 2012 [RD]: 82 bp/month five-factor alpha (t 2.15), 1986-2007 | mostly | low: our signal was wrong-signed in 6 of 7 years |
| 13F breadth (L5) | Chen-Hong-Stein 2002 [SS]; Nagel 2005 finds no effect [SS] | yes | no |
| Post-earnings drift (L5) | Martineau, CFR 2022 [RD]: drift absent for large stocks since 2006 | yes | no: the literature predicts our null |
| Overnight (X2) | Lou-Polk-Skouras 2019 [RD]: the legs are large but cancel close to close | not scored | low for a close-to-close book |
| Cross-asset trend (X1) | Moskowitz-Ooi-Pedersen, Hurst-Ooi-Pedersen [BG]: about 60 futures; Huang et al. JFE 2020 [AB]: TSMOM ≈ historical-mean strategy | partly (5 ETFs) | moderate in principle; instruments are owner policy, and no free futures data |
| Vol targeting | Moreira-Muir 2017; Cederburg et al. 2020 [SS]: fails in real time for most strategies | yes | no |
| Nagel liquidity timing (Q10) | Nagel 2012 [AB]: reversal returns predictable with the VIX | partly (no VIX; calm window) | moderate; Layer 6 T1/T2 include the VIX |
| Adaptive exposure | fixed-share, multi-horizon trend [BG] | yes | no (samples spent) |
| MASTER variants | the MASTER paper [RD]: its own ablation shows the gate adds nothing on CSI300 | yes | moderate for A3/A4, through power only |
| Ensembling | multi-seed (Gu-Kelly-Xiu; Qlib) [L1 RD] | yes | no |
| Intraday-beta hedge | Hollstein-Prokopczuk-Wese Simen 2019 [SS] | partly (coverage) | no: the book is already about beta-neutral |
| Fund-variance regimes | HAR on daily realised variance [BG] | partly (weekly proxy) | low for Sharpe |
| Covariance book / hysteresis on MASTER | Jensen-Kelly-Malamud-Pedersen [L3 RD]: learned cost-aware weights, net Sharpe 0.94 → 1.38 | partly: B2 compared at equal gross, not equal risk | yes, if scaled to B0's book volatility, but the gross cap binds; forward only |
| Longer horizons (Q9) | Blitz et al. 2023 [SS] | partly | low-moderate |

**Correction to T1, before any result** (adopted as the Layer 6 amendment of 18:00 UTC). Guo-Huang-Li-Yu, arXiv
2608.23761 [RD]: KMZ random-feature timing has Sharpe ≈ historical-average timing over 1975-2020, and its gain
vanishes once predictors are centred. Nagel, NBER w34104 [SS], reads it as volatility-timed momentum.

## B. Proposals

Structural point [RS]: the book is about 0.22 of gross with the fund at the 1.9 cap, so freeing gross is worth more
than a better signal.

1. **P1, a capital-efficient core** (owner policy).
   * Δr ≈ (2.43% − s) × 0.3 × (share of weeks at 1.3×), with s the futures financing spread. That is about
     +0.45-0.55 %/yr at s ≈ 0.3% (D.E. Shaw, 2021-23 [RD]), and about half at the December 2024 peak of 1.4% [RD].
   * P1b: the freed gross allows a larger book, or the covariance book at equal risk.
   * Free historical futures-basis data: not available.
2. **P2, same-calendar-month seasonality ranked with MASTER.** Keloharju-Linnainmaa-Nyberg 2016 [RD]: 1.03 %/month
   (t 5.74), all but microcaps, ex-January; Jensen-Kelly-Pedersen 2023 [RD]: tangency Sharpe 0.65 → 0.74 with the
   seasonality factors.
   * Needs about 20 years of point-in-time prices per name, which we have only partly.
   * Likely survivorship-contract problem; the signal changes only monthly.
3. **P3, Lazy Prices (10-K/10-Q similarity), ranked with MASTER.** Up to 188 bp/month 1995-2014 [SS; the full text
   was blocked with 403]. No post-publication evidence found. EDGAR is free and point in time.
4. **P4, text-network peer returns (Hoberg-Phillips TNIC).** Ali-Hirshleifer 2020 [SS]; Huang et al. 2026 [RD]
   gross 0.82 on the S&P 500. The SIC network nearly matches the text network, so the prior is low-moderate.

## C. Blocked or cut short

* Elicit: every call refused (no API access on the plan).
* Harvard DASH Lazy Prices PDF: 403. CME financing article: timed out.
* Chen-Kelly-Xiu: not indexed on alphaXiv. WebFetch returned binary PDFs, which were extracted locally instead.
* Searches cut short: Lazy Prices replication after 2014 (one query); AlphaPortfolio net-of-cost numbers; SESTM
  tables; Huang et al. 2020 (abstract only); Nagel 2012 and Cederburg 2020 (abstract or summary only).
