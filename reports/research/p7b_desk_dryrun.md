# Protocol 7B desk dry run (as-of 2026-10-21, scratch copy, run 2026-10-27; nothing traded or recorded)

The live desk code was run with the Amendment 8 and 7B labels switched on for last week's as-of. The horizons in the last
column apply the averaging rule (`structural_mean`), recomputed from the run's own samples without new calls.

| name | side | event type | structural votes | A8 H | structural H (dated report) | 7B H (mean) | recorded A7 H | driving event |
|---|---|---|---|---|---|---|---|---|
| AAPL | S | analyst_revisions | FFFFF | 14 |  | 14 | 8 | Loop Capital downgrade and analyst concerns over slowing iPhone 18 dem |
| AEP | L | partnership | TTTTT | 5 | 5 | 5 | 3 | AEP signs Indiana nuclear pact with Amazon and X-energy for 960-MW pro |
| AMD | S | macro_readthrough | FFFFF | 16 |  | 16 | 3 | Sector-wide AI chip selloff and fizzled rebound pressure AMD shares ah |
| AVGO | S | other | FFFFF | 5 |  | 5 | 3 | CEO Hock Tan's 'casino' warning on AI spending still overhanging AVGO |
| BA | L | legal_regulatory | TTTTT | 4 | 4 | 4 | 5 | FAA certifies Boeing 737 MAX 10, clearing deliveries of 1,555 ordered  |
| CMG | S | analyst_revisions | FFFFF | 3 stale |  | not entered | 5 | TD Cowen downgrades Chipotle to Hold, cuts PT to $32 on soft October s |
| CRM | S | mna_rumour | FFFFF | 4 |  | 4 | 3 | Salesforce announces $5.66B all-cash Braze acquisition |
| CSX | L | earnings | FFFFF | 18 |  | 18 | 14 | CSX Q3 2026 earnings beat: revenue $4.02B, EPS $0.57, margin up 880bps |
| HAS | L | earnings | TTFFT | 3 | 40 | 25 | 13 | Q3 2026 earnings beat, Magic: The Gathering >$600M, FY26 guidance rais |
| LRCX | S | guidance | FFFFF | 16 |  | 16 | 14 | LRCX fiscal Q1 earnings beat but Q2 guidance only in line; outlook fai |
| META | L | earnings | FFFFT | 19 |  | 19 | 14 | Meta Q3 2026 double beat: EPS $7.40 vs $5.74, sales $64.6B vs $63.4B |
| MMM | L | partnership | TTFFT | 3 | 60 | 37 | 3 | 3M expands AWS data-center partnership with $6B purchase warrant; Q3 b |
| MRNA | S | dated_catalyst | FFFFF | 3 stale |  | not entered | 3 | Detailed Phase 3 melanoma data readout due Oct 24, topline win already |
| MSFT | S | dated_catalyst | FFFFF | 6 |  | 6 | 5 | Microsoft Q1 FY2027 earnings report on Oct 28 |
| NFLX | S | guidance | TTTFF | 3 | 60 | 37 | 14 | Q3 beat overshadowed by trimmed 2026 ad-revenue outlook, FCF cut and w |
| ROL | S | earnings | FFFFF | 24 |  | 24 | 14 | Q3 2026 earnings miss: sales $1.090B vs $1.106B estimate, EPS inline,  |
| SMCI | L | guidance | TFTFF | 4 |  | 4 | 13 | Supermicro raises Q1 FY27 revenue outlook to $18.5-19.5B on AI demand, |
| TSLA | L | mna_rumour | FTTTF | 3 stale |  | not entered | 4 | Musk confirms Tesla-SpaceX merger committees formed; boards study poss |
| WMT | L | product_launch | FFFFT | 7 |  | 7 | 3 | Walmart launches $120 joint Walmart+/Sam's Club membership bundle |
| XOM | L | macro_readthrough | FFFFF | 14 |  | 14 | 3 | Iran tensions push Brent above $110, lifting XOM to 52-week high |

**Read against the theses (rule 11).** Labelled structural by majority: NFLX (trimmed outlook, FCF cut), MMM (multi-year AWS
deal), AEP (nuclear pact), BA (737 MAX 10 certification), HAS (FY guidance raised). Not structural: downgrades, a deal
rumour, a product bundle, an oil spike, single-quarter beats (CSX, META). TSLA is labelled structural but stale (not entered).
Close votes (HAS, MMM 3-2) moved the majority-vote horizon from 3 to 40-60 sessions; the averaging rule gives 25 and 37
instead, Amendment 8's own remedy for label splits. Imminent reports (AEP, BA: 3-4 sessions) give short horizons; the
Amendment 8/9 review at the report then re-underwrites (up to 63 sessions in total).

Limit of this table: the run used the first version of R2 (majority vote), which computed the structural horizon only for
majority-structural names. Under the final rule a minority vote also enters the mean: SMCI (2 of 5), META and WMT (1 of 5)
would get somewhat longer horizons than the A8 values shown, by (votes / 5) x (structural H − A8 H).
