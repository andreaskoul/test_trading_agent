# The fund

A weekly, news-driven long-short book on S&P 500 stocks, run as a funnel of desks the way a
small discretionary-quant fund works, and traded on an Alpaca paper account. Every rule is
pre-registered in [`reports/research/PROTOCOL_fund.md`](../reports/research/PROTOCOL_fund.md)
(Protocol 6, Amendments 1–5); operational changes are logged in [`CHANGELOG.md`](CHANGELOG.md).

**Dashboard:** https://andreaskoul.github.io/test_trading_agent/ ·
**Ledger page (with Excel download):** https://andreaskoul.github.io/test_trading_agent/ledger/

## How a week runs

All scheduled operations run on the owner's Mac (`fund/local/`): a launchd agent runs
`runner.py tick` every minute, and each due job runs the same steps as its workflow in a fresh
clone of `main`. It restores fund state from `fund-data`, commits there, opens a GitHub issue on
failure, and starts `fund_pages.yml` after every weekly, trade, review and reconcile run so the
GitHub Pages monitor stays current. Every job is idempotent, so a retry or a manual start never
acts twice. The workflows remain, manual only, as the fallback when the Mac is off.

| when (UTC) | what | workflow | request body |
|---|---|---|---|
| daily 21:20 | news archive: Finnhub news for every S&P 500 member, one file per day; then the context archive (Amendment 6, shadow input only) | `fund_archive.yml` | `{"ref":"main","inputs":{"minutes":"40"}}` |
| Wed 22:15 | the desks decide next week's book (≈ 90 min), committed to `fund-data` before the Thursday 19:00 deadline; a week is decided once | `fund_weekly.yml` | `{"ref":"main"}` |
| Thu 16:15 (Fri 16:15 after a Thursday holiday) | orders sent in the last minute before the close (`fund/broker.py`); each week is traded once | `fund_execute.yml` | `{"ref":"main","inputs":{"mode":"trade"}}` |
| Mon, Tue, Wed, Fri 16:30 | daily review of held positions against new news; changes traded at that day's close | `fund_review.yml` | `{"ref":"main","inputs":{"mode":"trade"}}` |
| Tue–Sat 01:10 | reconcile the previous session: fills vs official close, broker NAV, cash activity, risk halts | `fund_execute.yml` | `{"ref":"main","inputs":{"mode":"reconcile"}}` |
| after each weekly, trade, review or reconcile run | ledger (Excel) and dashboard rebuilt and published on GitHub Pages | `fund_pages.yml` | (started by the runner) |

The trade job also runs on Fridays; it trades only when Thursday was a holiday. A slot missed
while the Mac slept still starts on wake, within a limit per job (3 h for trade, review and
archive; weekly until Thu 17:15; reconcile 12 h). The desks refuse out-of-window runs on top
of that. A Claude scheduled task at 17:03 UTC on weekdays is a second line: if the day's
trade or review record is missing, it dispatches the GitHub workflow.

**Local runner.** Install or update with `bash fund/local/install.sh`. It creates
`~/.fund-runner` (a native Python 3.11 venv, `secrets.env` from `fund/local/secrets.env.example`,
chmod 600) and the launchd agent `com.andreaskoul.fund-runner`. The schedule starts disabled.
`runner.py enable|disable|status`, `runner.py run <archive|weekly|trade|review|reconcile|execute>`
(options `--mode`, `--asof`, `--dry-run`, `--resume`). Logs are in `~/Library/Logs/fund/`. If a
workflow on `main` calls a script the runner does not run, the runner opens an issue. The Mac
must be awake at the slot times (on power, automatic sleep off). Each job holds a `caffeinate`
assertion while it runs.

Positions are held from one Thursday close to the next. A US holiday moves the trade to the next
session. Times are UTC, so Athens times shift with daylight saving; 16:15–16:30 UTC is inside
the trading window all year.

## The desks

```
daily ─ 0 news archive
Wed ─── 1 screen ─▶ 2 ideation ─▶ 3 research ─▶ 4 analysts ─▶ 5 red team ─▶ 6 PM + risk ─▶ commit
          500 names   ≤ 45 names    narratives     memos         filter        the book
        8 macro FX · 11 shadow challengers · 7 IC memo · 9 performance · ledger · dashboard
Thu ─── 10 execution (last minute before close)  Fri/Mon/Tue/Wed ─ 12 daily review
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
| 13 Macro brief | `macro_desk.py` | yes, 1 call | `macro_brief.json`: holding-week calendar, regime, themes, FX view from the context archive (Amendment 6, shadow) |
| 14 Neighbourhood | `neighbours.py` | no | `neighbours.json`: top co-mentioned peers, their and the sub-industry's headlines, own 8-Ks (Amendment 6, shadow) |
| 15 C8 / C9 | `shadow_info.py` | yes, one per name + 1 | `shadow_info.json`: informed analysts and the ranker; books in `shadow_book.json` (Amendment 6) |
| 16 Lifecycle C10 | `lifecycle.py` | yes, one per name + daily news checks | `lifecycle.json` per week; `lifecycle/state.json`: per-position horizon, stop/target, news exits, daily NAV (Amendment 7, shadow) |
| 17 Review context | `review_context.py` | no | `reviews/context/<day>.json`: what a macro-aware review would have seen (Amendment 6, logged only) |
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
if it wins at a look by the stricter boundary for seven challengers (5.44 / 3.85 / 3.14 / 2.72):
timing (Wednesday close, Thursday open), 5-sample analysts, text-only analysts with names
masked, volatility-scaled sizing, news-conditioned reversal, and the fund without the daily
review. Benchmarks: the quant (ridge) book, an analyst book without the red team, the
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
* **Execution test:** `runner.py run execute --mode plan` (orders built from the real account,
  nothing sent). `runner.py run filltest --test buy SPY 1` sends one labelled order through the
  pre-close path (`fund-test-…`), recorded in `execution/tests.csv`.
* **Review test:** `runner.py run review --mode plan` (writes `reviews/<day>.plan.json`, never the day's record).
* **Provider check:** *Fund · LLM provider check* calls the model once through each candidate host.

Secrets: `OPENROUTER_API_KEY`, `FINNHUB_API_KEY`, `HF_TOKEN`, `ALPACA_API_KEY`,
`ALPACA_SECRET_KEY` (a paper account used only by the fund), optionally `POLYGON_API_KEY`,
`FRED_API_KEY` and `SEC_USER_AGENT` (name and contact email, as the SEC requires; context archive).
Live trading is blocked unless `FUND_LIVE_TRADING=1` and a non-paper Alpaca endpoint are set
on purpose.
