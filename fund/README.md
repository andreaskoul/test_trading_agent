# The fund

A weekly equity long-short book and a currency book, run as a funnel of desks
the way a small discretionary-quant fund works. Pre-registered in
[`reports/research/PROTOCOL_fund.md`](../reports/research/PROTOCOL_fund.md).

```
Wed 22:15 UTC ─ 1 screen ─▶ 2 ideation ─▶ 3 research ─▶ 4 analysts ─▶ 5 red team ─▶ 6 PM + risk ─┐
                (500 names)  (≤ 45 names)  (narratives)   (memos)       (challenges)   (the book)    │
                                                                   8 macro FX ─────────────────────┤
                                               commit to `fund-data` before Thursday's close ◀─────┘
                                                            7 IC memo · 9 performance ─▶ commit
```

| desk | file | LLM? | output (`fund_state/live/<asof>/`) |
|---|---|---|---|
| 0 Data (daily) | `archive.py` | no | Hugging Face `<you>/fund-news-archive`: every S&P 500 member's Finnhub news, one file per UTC day, 91-day window |
| 1 Screen | `screen.py` | no | `screen.json`: signals, frozen ridge, beta, sector, news attention for every S&P 500 member |
| 2 Ideation | `ideate.py` | yes | `ideation.json`: nominated ideas with hypotheses, the coverage list and why each name is on it |
| 3 Research | `research.py` | via the dashboard pipeline | `research/<T>.json`: your narrative dashboard's output (stories with continuity, events) for every covered name |
| 4 Analysts | `analysts.py` | yes, one per name | `analysts.json`: news-driven thesis, catalysts, risks, score, confidence (blind to the quant forecast) |
| 5 Red team | `redteam.py` | yes, per conviction | `redteam.json`: uphold, or weaken with a named flaw; weekly calibration counts |
| 6 PM + risk | `pm_risk.py` | no | `book.json`: conviction-sized books (fund, analyst), benchmarks (quant, core20, random), sector and dollar caps, SPY beta hedge |
| 7 IC memo | `ic_memo.py` | yes | `ic_memo.md`: the week's written record |
| 8 Macro | `fx_desk.py` | yes | `fx.json`: 17-currency book plus quant and random |
| 10 Execution | `execute.py` | no | `execution.json`: orders for the Thursday closing auction on the Alpaca paper account; after the close `execution/fills.csv` (slippage vs the close), `nav.csv`, risk halts |
| 11 Shadow | `shadow.py` | yes | `shadow.json`, `shadow_book.json`: challenger analysts C2 (5-sample median) and C3 (text-only, masked); the weekly model canary. Never traded |
| 12 Daily review | `review.py` | yes | `reviews/<day>.json`: on each trading day between executions, held names are re-read against news since the last review; exit / reduce / increase on confirmed material news, traded at that day's close |
| 9 Performance | `score.py` | no | `performance/`: weekly P&L per book (net and in excess of cash), stage tests, attribution, `summary.md`, and the go-live gate `gate.md` |

**Research reuses the narrative dashboard.** `research.py` runs
`andreaskoul/my-website`'s `pipeline/fetch.py` and `build.py` at a pinned
commit on whatever this week's coverage list is. Curated firms keep your
match regexes; new names get one built from the S&P 500 security name.

**The news is stored, not re-fetched.** Every run (dry runs included) saves the
raw feeds and story state to the `fund-data` branch. Each week `fetch.py` asks
Finnhub only for the gap since a firm's newest stored article. The dashboard's
own 20 feeds (updated daily on my-website) are merged in first, so those usually
need no calls at all. Names new to coverage come from the S&P 500 news archive (desk 0,
`.github/workflows/fund_archive.yml`, daily 21:20 UTC), so no name pulls 91 days on
Wednesday once the archive's window is complete (until then fetch.py backfills as before).
A firm that drops out keeps its archive and catches up when it returns.
Embeddings are stored permanently in a private Hugging Face dataset
(`<you>/fund-embeddings`, via `fund/emb_store.py` and the `HF_TOKEN` secret), with
the Actions cache as a fast path, so only new articles are ever embedded.

**Quant for risk and attribution, news for views** (Amendment 2). The ridge forecast is
mostly market beta out of sample, so it is not shown to the analysts: it is a benchmark
book, and its signals are the factors the fund's returns are attributed to.

**Why the extra books.** Every stage has to earn its place against the one
before it. analyst − quant asks whether research and judgement beat the
screen; fund − analyst asks whether the red team helps. The ideation test asks
whether nominated names move more, and in the hypothesised direction. First
formal read at 52 weeks.

## Running it

* **Weekly:** `.github/workflows/fund_weekly.yml`, Wednesday 22:15 UTC. The PM
  desk refuses after Thursday 19:00 UTC.
* **Dry run:** Actions → *Fund · weekly desks* → *Run workflow* → tick
  **dry_run**. It makes real calls, has no deadline, and only produces a run
  artifact: nothing is committed or counted. Use it once after merging to
  check the live research path end to end.
* **Local mock** (no keys; the LLM returns a ridge echo and research copies the
  dashboard's published files): `FUND_MOCK=1 FUND_ASOF=2026-09-23 python fund/<desk>.py`
  in desk order.

Secrets: `OPENROUTER_API_KEY`, `FINNHUB_API_KEY`, `HF_TOKEN`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` (a paper account used only by the fund), and optionally `POLYGON_API_KEY`.

**Evidence review and Amendment 4.** `reports/Multi agent AI trading desk design.md` audits every desk against the literature. It found no case for more agents or debate. The fixes are to the measurement (alpha net of beta and reversal), the hedge (Welch beta), model continuity (pinned provider, canary) and replayability, plus six shadow challenger books that are never traded.

**Position ledger.** `fund_state/live/ledger/fund_positions.xlsx` on the `fund-data` branch is rebuilt after every weekly run and every execution/reconciliation (`fund/ledger.py`). It has one row per position per week, with entry/exit prices, returns, contributions, scores and theses, plus every order with its slippage and the weekly returns.

**Going live** is decided by `fund_state/live/performance/gate.md` (Amendment 3), not by a good month. Problems, risk halts and gate verdicts other than CONTINUE open a GitHub issue.
