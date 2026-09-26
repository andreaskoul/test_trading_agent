# Protocol 5: LLM portfolio selector, forward test only

Committed before the selector has made a single decision.

## Question

Given the quantitative inputs from Protocols 3–4 (signal z-scores and a
frozen ridge forecast) plus the past week's headlines, does an LLM's
cross-sectional selection predict next-week returns **better than the
quantitative forecast it was handed**?

That comparison is the point. An LLM that merely echoes the ridge ranking
adds nothing. It has to add information, presumably from the news.

## Why forward only

`deepseek/deepseek-v4.1-flash` (OpenRouter, listed 2026-09-10) was trained
on text up to an unknown cutoff, probably mid-2026. Anything before that
date, including the Apr–Sep 2026 live window, may be in its training data:
it could "remember" what happened. **No historical backtest of the LLM is
valid.** Every decision is made about a week that hasn't happened yet. It is
written to `reports/llm_forward/decisions/` and committed to git before the
outcome exists; the commit timestamp is the proof.

## Weekly cycle (GitHub Actions, Wednesday 22:30 UTC)

1. `scripts/llm/build_inputs.py`: as of the Wednesday close.
   * **Stocks:** current S&P 500 members (latest row of the pinned
     membership file, refreshed from fja05680/sp500). Signals mom12_1, rev1m,
     rev1w, lowvol, high52 as cross-sectional z-scores, plus the frozen ridge
     forecast (coefficients fitted once on 2004-01 → 2026-03, stored in
     `artefacts/llm/ridge_stocks.json`). Headlines: Yahoo Finance news for
     each ticker from the last 7 days, at most 5 per name, title + summary +
     date + publisher.
   * **FX:** the 17 currencies of Protocol 3. Carry (lagged OECD rates),
     mom1/mom3/mom12, rev1w and value z-scores, plus the frozen FX ridge.
     Spot is from Yahoo (H.10 is published with a one-week lag, so it can't be
     used live). No FX headlines in v1.
2. `scripts/llm/select.py`: one call per universe. Model
   `deepseek/deepseek-v4.1-flash`, temperature 0, fixed prompt (hash
   stored). Output JSON: for **stocks, 25 longs and 25 shorts**; for
   **FX, 4 longs and 4 shorts**; each with a score in [−1, 1] and a reason
   of at most 25 words. The output is validated: names must be in the
   universe, counts exact, no overlap. On failure, one retry; on a second
   failure the week is logged as `no_decision` and is **not** excluded from
   the evaluation (it counts as a flat week for the LLM).
3. Positions: equal weight inside each leg, dollar-neutral, set at the
   Thursday close, held one week. A matched **quant book** (top/bottom 25 or
   4 by ridge forecast) and a **random book** (seeded by the date) are logged
   the same way.
4. `scripts/llm/score.py`: once a week's Thursday-to-Thursday returns
   exist, it scores all three books at 5 bp per side (stocks), Protocol 3
   costs (FX).

## Evaluation (pre-registered)

The primary statistic is **LLM minus quant**, not LLM on its own:

* Weekly return difference (LLM book − quant book), Newey–West t (lags 2).
* Rank-level: each week, the LLM's selected names (score) against next-week
  returns, compared with the ridge ranks restricted to the same names.

Power, stated honestly: a long-short difference with weekly SD of about 1.5%
needs roughly 90 weeks to detect a 0.3%/week edge at t = 2. **The first
formal read is at 52 weeks, the decision at 104.** Nothing in between counts
as evidence, and no prompt or model changes are allowed during the window.
A change restarts the clock under a new protocol number.

## Costs

`deepseek-v4.1-flash`: $0.035 per M input tokens, $0.29 per M output. About
150k input tokens per week, so under $0.01 a week.
