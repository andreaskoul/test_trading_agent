# L3: literature — more net Sharpe from the fast trees book and the combined fund

*An in-project literature reading by a separate AI session (2026-11-13), saved by the coordinating session. Not an
outside review. Access: [RD] full text read, number copied; [AB] abstract only; [SS] search summary or secondary
write-up (unverified); [RS] the agent's reasoning. No idea is claimed to be new. Tool reliability: alphaXiv finance
coverage thin, PDF queries failed twice; Elicit failed twice; SSRN and CEPR returned 403.*

## 1. Ideas

| # | Idea | Sources (access) | Reported effect (source's numbers) | Application |
|---|---|---|---|---|
| a1 | Learn weights directly, cost-aware, trade part of the way to an "aim" (implementable efficient frontier) | Jensen-Kelly-Malamud-Pedersen (RFS forthcoming; SFI WP 22-63), read as a chapter of T.I. Jensen's CBS thesis 2023 [RD] | Table II, 1981-2020, monthly, $10B: Portfolio-ML net SR 1.38 (gross 1.43, turnover 0.32/month, leverage 3.60); Static-ML net 0.94 (turnover 0.76); Static-ML* 1.11; Markowitz-ML gross 2.00, turnover 56.33, net hugely negative; decile sort gross 1.10, net −11.87 (TC 1.972). About +20% net Sharpe, +60% utility over the second best. Impact 0.1% for 1% of daily dollar volume (Λ = 0.2/V). Naive ML leans on "1-month reversal for small stocks" | Our situation exactly (LW mean-variance gross ~1.0, 37% weekly turnover). Choose weights for net utility with dollar-volume-scaled impact |
| a2 | Dynamic trading: aim in front of the target, trade part way | Gârleanu-Pedersen JF 2013 [AB/SS] | Closed form: aim weights signals by alpha decay; trade a fraction each period; "superior net returns" (numbers not retrieved) | Basis for θ < 1; slow features weigh more in the aim than 1-5-day reversal |
| a3 | Buy/hold spread (sS rule) | Novy-Marx-Velikov RFS 2016 [RD WP] | %/month, value-weighted: short-run reversal decile TO 90.9%, TC 1.65, net −1.28 (t −6.02); 10%/50% buy/hold TO 57.1%, TC 1.00, net −0.72. High-frequency combo (industry momentum + industry-relative reversal) plain net 0.16 (t 1.11), buy/hold TO 53.6%, net 0.35 (t 2.83). Low-vol industry-relative reversal plain 0.19 (t 1.41), buy/hold 0.28 (t 2.41). "most anomalies with turnover less than 50% per month generate significant net spreads … few with higher turnover do" | Close to the band that failed OOS (counts against); the variant that worked is industry-relative + low-vol |
| a4 | Trading costs and capacity | Frazzini-Israel-Moskowitz 2012 draft [RD]; 2018 version [SS] | Impact ∝ √(fraction of daily volume). Break-even: SMB $103B, HML $83B, UMD $52B, STR $9.5B. STR 6.75%/yr at 305% monthly turnover, 18.4 bp a trade. Value+momentum $98B (trades offset). Average trade impact: large caps 11.21 bp, small caps 21.27 bp | Replace flat bp with a square-root model in any optimiser |
| a5 | Characteristics net each other's trades | DeMiguel-Martín-Utrera-Nogales-Uppal RFS 2020 [AB] | With costs 15 characteristics jointly significant vs 6 without, "because the trades … often cancel out" | Optimise one combined book; netting only inside the trees signal (different universes) [RS] |
| a6 | Parametric portfolio policies | Brandt-Santa-Clara-Valkanov RFS 2009 [AB/SS] | Extendable to costs (L1 penalty, secondary); a replication finds barely better than value-weighted after costs, gains fade after 1999 [SS] | Low-parameter direct weights; JKMP extend it |
| a7 | ML alpha decays; short-horizon ML stopped paying after costs | Avramov-Cheng-Metzker MS 2023 [AB]; Blitz-Hanauer-Hoogteijling-Howard JFDS 2023 [SS] | ML profit mainly microcaps, distressed, high-vol periods; "deteriorates … because of high turnover". Short-horizon ML profitable mainly before 2004; 3/6/12-month targets more reliably net positive 2004-2021; buy-and-hold rule helped at every horizon | Our IC is highest in the least liquid third; longer targets and partial trading are the literature's answer |
| b1 | Residual reversal | Blitz-Huij-Lansdorp-Verbeek JFM 2013 [SS/AB] | ~2× conventional reversal risk-adjusted; profitable after costs "even among large-cap stocks in the post-1990 period" | Already in our features |
| b2 | Reversal net of news; within-industry reversal + across-industry momentum | Da-Liu-Schaumburg MS 2014 [AB]; Hameed-Mian JFQA 2015 [AB; magnitudes SS] | ~4× standard reversal (2011 WP: ~3×); intra-industry reversals "pervasive", stronger after declines and volatile times; draft: 1.46%/month industry vs 1.05% market-wide, 1963-2006 gross | We lack industry-relative reversal and short-run industry momentum |
| b3 | Liquidity shapes reversals | Dai-Medhat-Novy-Marx-Rizova 2023 WP [RD partial] | Announcement-adjusted industry-relative 5-day reversals 1973-2021: high-vol names faster and initially stronger; low-turnover: reversal "continues to grow for almost three months"; high-turnover: "is over after only two weeks"; size matters little outside microcaps; holds internationally | Horizon and trade rate per name by turnover; mask earnings windows |
| b4 | Short-term momentum | Medhat-Schmeling RFS 2022 [AB] | Low-turnover stocks reverse; high-turnover show 1-month momentum; "survives transaction costs and is strongest among the largest, most liquid" | Turnover × past-return interactions (trees may already have them) |
| b5 | Reversal = price of liquidity provision, time-varying | Nagel RFS 2012 [AB]; Khandani-Lo [SS]; Cheng-Hameed-Subrahmanyam-Titman JFQA [SS] | Reversal returns predictable with VIX, Sharpe spikes in turmoil; daily contrarian declined 1995-2007; weaker after decimalisation, loser-quintile 0.49-1.22%/month after 2000 | Do not de-risk the reversal book in high vol [RS]; conflicts with generic vol targeting |
| c1 | Sector neutrality | Ehsani-Harvey-Li FAJ 2023 [AB/SS] | Long-short likely benefit from hedging sector bets; keeping across-sector helps long-short in 20% of bootstrap trials vs 78% long-only; rule: neutralise if SR(across)/SR(within) < their correlation | Cheap test with their ex-ante rule |
| d1 | Volatility-managed portfolios | Moreira-Muir JF 2017 [AB]; Cederburg et al. JFE 2020 [AB/SS]; Barroso-Detzel JFE 2021 [AB]; Barroso-Santa-Clara JFE 2015 [SS]; Harvey et al. JPM 2018 [SS] | Large alphas (M-M); 53 vs 50 of 103 portfolios, real-time generally worse (Cederburg); zero gain after costs except the market (Barroso-Detzel); momentum SR 0.53 → 0.97 (B-SC); US equity 0.40 → 0.48-0.51, left-tail benefit (Harvey) | Vol-target the combined fund and core, not the market-neutral books |
| e1 | Closing-auction execution | Goyal-Jegadeesh-Wu JFQA 2026 [SS]; Bogousslavsky-Muravyev JFM 2023 [AB/SS]; Besson-Lasnier arXiv 2301.05677 [title only] | Auction impact lower than continuous "for all stocks except Nasdaq microcaps"; square root fits better; 1% of ADV: 2.35 bp linear vs 17.7 bp square root; 9-21 bp ex-microcaps. Auction deviations revert quickly, mostly overnight | MOC probably cheaper for most broad names, not Nasdaq microcaps |
| f1 | Post-publication decay | McLean-Pontiff JF 2016 [AB/SS]; Chen-Velikov JFQA 2023 [AB] | Returns 26% lower out of sample, 58% after publication; after spreads, publication and data-mining correction the average anomaly nets 4 bp/month, strongest "at best, 10 bps", combinations ~20 bps; price impact left out | Planning haircut on our OOS numbers |

## 2. Ranked testable changes (development S&P 500 2013-2019 and forward weeks only; [RS] effect ranges)

1. **Partial trading toward a multi-horizon aim, rate scaled by liquidity** (Gârleanu-Pedersen; JKMP):
   w_t = w_{t−1} + θ_i (aim_t − w_{t−1}), aim = the LW mean-variance target on horizon-weighted forecasts, θ_i rising
   with dollar volume, cost Λ_i = 0.2/V_i plus half-spread. Control: deciles and the L1 no-trade MV book. ≤ 3 θ values,
   all reported, frozen before forward weeks.
2. **Per-name cost hurdle**: trade only when |Δ expected alpha| > the name's half-spread + square-root impact, one
   fixed multiple (1.0×). Forward only for the broad universe. Risk high (a relative failed OOS).
3. **Industry-relative, announcement-masked reversal + short-run industry momentum features**; industry codes and
   earnings dates from typed fields, frozen at first use.
4. **Name-specific horizon by turnover** (Dai et al.; Medhat-Schmeling), mapping fixed from the papers.
5. **Sector neutralisation** of the market-neutral books, with Ehsani-Harvey-Li's ex-ante rule.
6. **Square-root cost model in every evaluation**: half-spread + k σ_i √(trade/ADV), k from the literature. Comes
   before 1-2.
7. **Closing auction vs T−60 s**, measured on forward weeks (Nasdaq microcaps split out).
8. **Volatility target on the combined fund only** (owner policy, rule 17: once, pre-registered, long history).
9. **Planning haircut and decay monitoring**: expected forward Sharpe of the trees book about 0.7-0.75× the OOS
   figure (0.65 → about 0.45-0.5) [RS], plus a rolling 26-week IC decay test.

Not recommended: VIX or regime gates on the reversal book (Nagel predicts the opposite sign); bigger trees and ranking
losses (already failed).

## 3. Search log

alphaXiv discover ×2 (cost-aware ML portfolios; residual reversal net of costs): mostly 2024-26 RL/portfolio papers,
none central; JKMP not indexed; arXiv 2301.05677 PDF failed twice. Elicit ×2: failed. WebSearch, 21 queries (JKMP;
Novy-Marx-Velikov; DeMiguel et al.; Medhat-Schmeling; Gârleanu-Pedersen; Frazzini-Israel-Moskowitz; Blitz residual
reversal; Da-Liu-Schaumburg; Nagel; Avramov-Cheng-Metzker; Chen-Velikov; Harvey vol targeting; Cederburg; McLean-
Pontiff; closing-auction costs ×2; Brandt et al.; Hameed-Mian; Blitz ML alpha term structure; Ehsani-Harvey-Li;
Barroso-Santa-Clara; Moreira-Muir; Khandani-Lo; reversal after decimalisation; Barroso-Detzel).

Read [RD] (PDF text via pypdf): Jensen thesis, JKMP chapter (research-api.cbs.dk/ws/portalfiles/portal/92853994/);
Novy-Marx-Velikov 2015 WP (mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf); Frazzini-Israel-Moskowitz 2012
(conference.nber.org/conf_papers/f68262/f68262.pdf); Dai-Medhat-Novy-Marx-Rizova 2023 (…/novy-marx/research/RRLP.pdf).

Blocked: SSRN 4187217 (JKMP), CEPR DP15857 (Medhat-Schmeling): 403. Not covered: risk parity between a trend core
and market-neutral books, drawdown control (Grossman-Zhou); no paper read compares T−60 s with the auction.

Bibliography with access labels: as in the table (JKMP RFS forthcoming [RD via thesis]; Novy-Marx-Velikov RFS 2016
29(1):104-147 [RD WP]; Frazzini-Israel-Moskowitz 2012 [RD], 2018 [SS]; Gârleanu-Pedersen JF 2013 68(6) [AB/SS];
DeMiguel et al. RFS 2020 33(5) [AB]; Brandt et al. RFS 2009 22(9) [AB/SS]; Avramov et al. MS 2023 69(5) [AB]; Blitz et
al. JFDS 2023 [SS]; Blitz et al. JFM 2013 16(3) [SS/AB]; Da-Liu-Schaumburg MS 2014 60(3) [AB]; Hameed-Mian JFQA 2015
[AB]; Dai et al. 2023 WP [RD partial]; Medhat-Schmeling RFS 2022 35(3) [AB]; Nagel RFS 2012 25(7) [AB]; Khandani-Lo JFM
2011 [SS]; Cheng et al. JFQA [SS]; Ehsani-Harvey-Li FAJ 2023 79(3) [AB/SS]; Moreira-Muir JF 2017 72(4) [AB]; Cederburg
et al. JFE 2020 138(1) [AB/SS]; Barroso-Detzel JFE 2021 140(3) [AB]; Barroso-Santa-Clara JFE 2015 116(1) [SS]; Harvey
et al. JPM 2018 45(1) [SS]; DeMiguel-Martín-Utrera-Uppal JF 2024 [SS]; Goyal-Jegadeesh-Wu JFQA 2026 [SS];
Bogousslavsky-Muravyev JFM 2023 [AB/SS]; Besson-Lasnier [title only]; McLean-Pontiff JF 2016 71(1) [AB/SS];
Chen-Velikov JFQA 2023 58(3) [AB]).
