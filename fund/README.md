# The fund

A weekly, news-driven long-short book on S&P 500 stocks, run as a funnel of desks the way a
small discretionary-quant fund works, and traded on an Alpaca paper account. Every rule is
pre-registered in [`reports/research/PROTOCOL_fund.md`](../reports/research/PROTOCOL_fund.md)
(Protocol 6, Amendments 1–5); operational changes are logged in [`CHANGELOG.md`](CHANGELOG.md).

**Dashboard:** https://andreaskoul.github.io/test_trading_agent/ ·
**Ledger page (with Excel download):** https://andreaskoul.github.io/test_trading_agent/ledger/

## How a week runs

All scheduled operations are started by one external scheduler (cron-job.org), which sends a
`workflow_dispatch` request to GitHub at the times below. The workflows have no GitHub cron:
GitHub's scheduled runs started 3–6 hours late, or not at all, in the first live week. Every
job is idempotent, so a retry or a manual start never acts twice.

| when (UTC) | what | workflow | request body |
|---|---|---|---|
| daily 21:20 | news archive: Finnhub news for every S&P 500 member, one file per day; then the context archive (Amendment 6, shadow input only) | `fund_archive.yml` | `{"ref":"main","inputs":{"minutes":"40"}}` |
| Wed 22:15 | the desks decide next week's book (≈ 90 min), committed to `fund-data` before the Thursday 19:00 deadline; a week is decided once | `fund_weekly.yml` | `{"ref":"main"}` |
| Thu 16:15 (Fri 16:15 after a Thursday holiday) | orders for the closing auction; each week is traded once | `fund_execute.yml` | `{"ref":"main","inputs":{"mode":"trade"}}` |
| Mon, Tue, Wed, Fri 16:30 | daily review of held positions against new news; changes traded at that day's close | `fund_review.yml` | `{"ref":"main","inputs":{"mode":"trade"}}` |
| Tue–Sat 01:10 | reconcile the previous session: fills vs official close, broker NAV, cash activity, risk halts | `fund_execute.yml` | `{"ref":"main","inputs":{"mode":"reconcile"}}` |
| after each run of the above | ledger (Excel) and dashboard rebuilt and published | `fund_pages.yml` | (triggered by the runs) |

Each scheduler job: `POST https://api.github.com/repos/andreaskoul/test_trading_agent/actions/workflows/<workflow>/dispatches`
with headers `Authorization: Bearer <fine-grained token, Actions read and write on this repo only>`,
`Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`; GitHub answers 204.
A Claude scheduled task at 17:03 UTC on weekdays is a second line: it dispatches the trade or
the review if the day's record is missing.

Positions are held from one Thursday close to the next. A US holiday moves the trade to the next
session. Times are UTC, so Athens times shift with daylight saving; 16:15–16:30 UTC is inside
the trading window all year.

## The desks

```
daily ─ 0 news archive
Wed ─── 1 screen ─▶ 2 ideation ─▶ 3 research ─▶ 4 analysts ─▶ 5 red team ─▶ 6 PM + risk ─▶ commit
          500 names   ≤ 45 names    narratives     memos         filter        the book
        8 macro FX · 11 shadow challengers · 7 IC memo · 9 performance · ledger · dashboard
        then, shadow only (Amendment 6): macro brief · neighbourhood · C8 informed analysts · C9 re-score
Thu ─── 10 execution (closing auction)          Fri/Mon/Tue/Wed ─ 12 daily review
```

| desk | file | LLM | output (`fund_state/live/<week>/`) |
|---|---|---|---|
| 0 News archive | `archive.py` | no | private HF dataset `<you>/fund-news-archive`: one parquet per UTC day, 91-day window, append-only |
| 0b Context archive | `context_archive.py` | no | private HF dataset `<you>/fund-context-archive`: FRED release calendar, Kalshi macro markets, AI-GPR, GDELT theme volume and tone (best effort), Finnhub market news, S&P 500 8-K filings; point in time, append-only. Read by no champion desk (Amendment 6 shadow input) |
| 1 Screen | `screen.py` | no | `screen.json`: price facts, hedge beta (252-day Welch, shrunk to 1), sector, news attention, earnings in the holding week, the frozen ridge (benchmark only) |
| 2 Ideation | `ideate.py` | yes | `ideation.json`: nominated ideas with hypotheses and the coverage list (≤ 45 names) |
| 3 Research | `research.py` | via the dashboard pipeline | `research/<T>.json`: each name's news narratives (stories with continuity, events), built by `andreaskoul/my-website`'s pipeline at a pinned commit |
| 4 Analysts | `analysts.py` | yes, one per name | `analysts.json`: news-driven thesis, catalysts, risks, score −2..+2, confidence |
| 5 Red team | `redteam.py` | yes, per view | `redteam.json`: uphold, or weaken with a named flaw (factual, stale, recycled, contra, priced) |
| 6 PM + risk | `pm_risk.py` | no | `book.json`: weights = score × confidence / 20 of NAV (≤ 10 a side, ≤ 10% a name), sector net ≤ 30%, dollar net ≤ 10% of gross, SPY hedge to zero beta; flat with no views; benchmark and challenger books |
| 7 IC memo | `ic_memo.py` | yes | `ic_memo.md`: the week's written record |
| 8 Macro FX | `fx_desk.py` | yes | `fx.json`: 17-currency book (scored, not traded) |
| 9 Performance | `score.py` | no | `performance/`: weekly returns per book (net of 5 bp/side, in excess of cash), attribution, monitors, and the go-live gate `gate.md` |
| 10 Execution | `execute.py` | no | `execution.json`: closing-auction orders on Alpaca; `execution/fills.csv`, `nav.csv`, `activities.csv`; risk halts |
| 11 Shadow | `shadow.py` | yes | `shadow.json`, `shadow_book.json`: challenger analysts and the weekly model canary; never traded |
| 12 Daily review | `review.py` | yes | `reviews/<day>.json`: exit, reduce or increase held names on confirmed material new news |
| A6 Macro desk | `macro_desk.py` | yes, one call | `macro_brief.json`: one brief for every C8 analyst (calendar, regime, themes by sector, FX view); shadow only |
| A6 Neighbourhood | `neighbours.py` | no | `neighbours.json`: per covered name, co-covered firms' and sub-industry news, own 8-Ks; shadow only |
| A6 C8 / C9 | `shadow_info.py` | yes, one per name + one | `shadow_info.json`: informed analysts (C8) and a cross-sectional re-score (C9); books in `shadow_book.json`; never traded |
| A6 Review context | `review_context.py` | no | `review_context/<day>.json`: what a macro-aware review would have seen; logged only |
| Ledger | `ledger.py` | no | `ledger/fund_positions.xlsx` and `ledger/dashboard.json`: actual Alpaca trades only |

The model is `deepseek/deepseek-v4.1-flash` via OpenRouter, temperature 0, with the serving
provider left to OpenRouter's routing; the provider is logged for every call and the canary
tracks whether behaviour drifts.

## Risk controls

* Book limits as in desk 6; execution caps gross at 1.8× equity, drops names that cannot be
  traded or borrowed and hands their beta back to the SPY hedge.
* Daily review: at most 5 changes a day, one increase per name per week (to 1.5× the book
  weight, ≤ 10% NAV), no new names or flips, SPY re-hedged.
* Halts: broker NAV 10% below peak or −5% over five sessions → flat from the next trade until
  resumed by hand (`fund_execute.yml`, input `resume`).
* A live weekly run past its deadline is refused; a run where > 25% of analyst calls fail
  holds last week's book; LLM calls have a hard 240 s limit and desks have time budgets.
* Failures, halts and gate verdicts other than CONTINUE open a GitHub issue.

## How it is judged

Forward only: the model's training data rules out a backtest. The go-live gate
(`performance/gate.md`) looks at 13, 26, 39 and 52 scored weeks with O'Brien–Fleming
boundaries (t ≥ 4.05 / 2.86 / 2.34 / 2.02) on the fund's weekly return in excess of cash,
requiring the alpha net of SPY and the one-week reversal factor to cross too, and operations to
pass (decisions on time, orders filled, slippage ≤ 10 bp). STOP if the fund, its reversal-
adjusted difference to the quant book, or its adjusted score slope is significantly negative.

Shadow books measure every design choice against the traded fund, and one only replaces it
if it wins at a look by the stricter boundary for nine challengers (5.60 / 3.96 / 3.23 / 2.80):
timing (Wednesday close, Thursday open), 5-sample analysts, text-only analysts with names
masked, volatility-scaled sizing, news-conditioned reversal, the fund without the daily
review, and (Amendment 6) analysts given macro, peer and filing context (C8) and their cross-sectional re-score (C9). Benchmarks: the quant (ridge) book, an analyst book without the red team, the
dashboard's core 20, and a random book.

The evidence review behind these choices is in
[`reports/Multi agent AI trading desk design.md`](../reports/Multi%20agent%20AI%20trading%20desk%20design.md);
realistic expectations for a large-cap weekly news book are a Sharpe of roughly 0–0.5 after costs.

## Where things are stored

* `fund-data` branch: every week's inputs, prompts, decisions, orders, fills, reviews,
  performance, the ledger and dashboard data. The commit time is the evidence that a
  decision predates its outcome.
* Hugging Face (private): `<you>/fund-news-archive` (daily news), `<you>/fund-context-archive`
  (macro, geopolitical and filing context, Amendment 6) and `<you>/fund-embeddings` (embedding cache).
* GitHub Pages: the trade monitor (`fund/site/index.html`) and the ledger page (`fund/site/ledger/index.html`), with the Excel file as a download.

## Running and testing

* **Dry run:** Actions → *Fund · weekly desks* → Run workflow → tick **dry_run** (real calls,
  no deadline, results only as a run artifact; nothing enters the live record). Always tick it
  for tests.
* **Execution test:** *Fund · execution* with mode `plan`, optionally `mock_book` and
  `test_order` (sends and cancels one 1-share closing-auction order).
* **Review test:** *Fund · daily position review* with mode `plan`.
* **Provider check:** *Fund · LLM provider check* calls the model once through each candidate host.
* **Local mock** (no keys): `FUND_MOCK=1 FUND_ASOF=2026-09-23 python fund/<desk>.py` in desk order.

Secrets: `OPENROUTER_API_KEY`, `FINNHUB_API_KEY`, `HF_TOKEN`, `ALPACA_API_KEY`,
`ALPACA_SECRET_KEY` (a paper account used only by the fund), optionally `POLYGON_API_KEY`,
`FRED_API_KEY` and `SEC_USER_AGENT` (name and contact email, as the SEC requires; context archive).
Live trading is blocked unless `FUND_LIVE_TRADING=1` and a non-paper Alpaca endpoint are set
on purpose.
