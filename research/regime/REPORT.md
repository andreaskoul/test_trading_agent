# Regime-dependent edges: what was searched, what held up

*2026-11-07. Pre-registration and every amendment: `research/regime/PREREG.md` (each committed before the statistics it
governs). Code: `regime.py` (panels), `search.py` (development search and the single OOS read), `intl.py` (the
international replication), `forward.py` (forward paper books). Nothing here trades.*

## The answer

**One regime edge held up on data it was not designed on: momentum crashes in a detectable panic state.**
* **Panic state:** the market's 252-session return is negative, and its 21-session realised volatility is above its
  median of the last 156 weekly decisions.
* **The edge:** holding momentum (12-1 month winners minus losers) only outside panic.

| Sample | Role | t (predicted) | p | Momentum net % a year, switched / always on | Sharpe, switched / always on | Worst fall |
|---|---|---:|---:|---|---|---|
| US 1927–1999 (Ken French UMD) | development | 1.68 | — | 8.6 / 7.9 | 0.89 / 0.63 | — |
| US 2000–2025 | OOS, one read, Holm across 4 | 1.72 | 0.043 alone, **0.096 Holm** | 6.9 / 2.5 | 0.55 / 0.23 | 2009: −9% / −50% |
| Europe, Japan, Asia Pacific ex Japan 1992–2025 | independent replication, one read, Holm across 2 | **2.72** | 0.003 alone, **0.007 Holm** | 9.5 / 7.7 | 1.14 / 0.70 | −30% / −51% |

The sign is right in every sample and every region (Europe t 3.14, Asia Pacific 1.66, Japan 1.49). This is the
Daniel & Moskowitz (2016) momentum-crash regime. It is known, not new, but here it is replicated cleanly on a sample
never read before.

## What it is, and what it is not

* **A risk regime, not a return source.** It acts only in panic weeks: about one week in six since 2000 (16.6%), mostly in
  2001–03, 2008–09, 2016, 2020 and 2022. Its value is the crash it avoids.
* **In the fund's universe, large-cap momentum has been weak.** The S&P 500 momentum decile book lost money in
  2020–2025 with or without the switch (−2.6% against −2.9% a year net). In the week of 30 Oct – 6 Nov 2026 it lost
  7.3% in a momentum reversal that was **not** a panic (the S&P 500 was up 13% on the year). The switch does not
  protect against every momentum loss, only the bear-market rebound kind.
* **The S&P AI books are momentum bets.** The rank correlation of their scores with 12-1 momentum was 0.49–0.64 on
  29 Oct and 0.59–0.89 on 5 Nov (ensemble 0.85). A panic would hit them as it hits momentum. This is the most
  direct use of the finding.

## What did not hold up (17 regime ideas in all)

On development data (≤ 2019, or ≤ 1999 for the long histories), these failed the development gate:

| Idea | Development t | Note |
|---|---:|---|
| Reversal earns more when volatility is high (Nagel) | 0.63 | |
| Sector-relative reversal when names co-move within sectors | 0.33 | |
| Momentum off in panic, S&P 500 2010–2019 | 1.19 | too few panics in that decade; tested on long history instead (H16) |
| Reversal stronger when news is homogeneous (news embeddings) | 0.03 | |
| Momentum unwinds after an abrupt shift in news topics (embeddings) | −0.82 | wrong sign |
| HMM high-volatility state favours reversal over momentum | 0.93 | |
| Earnings drift larger when many firms report (limited attention) | 1.26 | |
| Factor momentum | −1.15 | wrong sign: factors reverted |
| Sector momentum when sectors decouple | 1.30 | |
| Momentum scaled by its own volatility, S&P 500 | 0.50 | |
| Novel vs stale news (Tetlock), in embedding space | −0.47 | wrong sign |
| Industry momentum by cross-industry correlation, 1927–1999 | −0.79 | wrong sign |
| Momentum scaled by its own volatility, 1927–1999 | 1.20 | |

The finalists, read once out of sample:

| Idea | OOS t | Holm p | Verdict |
|---|---:|---:|---|
| News/no-news reversal × earnings season (H8) | 1.18 | 0.119 | no |
| The same, banded to cut turnover (H12) | 1.85 | 0.096 | no; it nets +1.4% against +0.8% a year, too small to matter |
| Factor reversal (H14) | 2.03 | 0.085 | no; mostly 2020, and **wrong sign internationally** (t −1.71) |
| Momentum off in panic (H16) | 1.72 | 0.096 | not alone; **passed in the international replication** |

**News embeddings, honestly:** neither the market-level news regimes (homogeneity, topic shift) nor the stock-level
novelty test found anything. The 31-name panel gives a weak measurement of the market's news state, and
2017–2019 is a short development window. The earnings calendar, which is hard news, carried the news/no-news split
better than embeddings did.

## Disclosures

* The panel build printed full-period means of the three unconditioned books before Amendment 1 (no regime
  statistic). The first OOS run crashed in a placeholder regression before any output or lock; it was fixed,
  committed, and re-run.
* 2020–2025 prices were used by earlier studies of other signals, and the momentum-crash literature is well known.
  The international factors were never read before Amendment 5.
* 2026 data were not read by any test. The forward books start on 2026-11-12.

## Taken forward (Amendment 6)

`forward.py` writes weekly paper records (never traded) to `research-data` (`fund_state/live/research/regime/`):
* S&P 500 momentum, always on and switched off in panic;
* a copy of the AI average book, always on and switched off in panic;
* the panic state with its inputs, frozen each week;
* each AI model's momentum exposure.

The website's section 5 shows them. There is no return verdict: each panic episode reports the loss avoided. Using
the switch in any traded or registered book needs its own protocol and the owner's decision.
