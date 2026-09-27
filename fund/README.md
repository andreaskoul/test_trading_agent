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
| 1 Screen | `screen.py` | no | `screen.json`: signals, frozen ridge, beta, sector, news attention for every S&P 500 member |
| 2 Ideation | `ideate.py` | yes | `ideation.json`: nominated ideas with hypotheses, the coverage list and why each name is on it |
| 3 Research | `research.py` | via the dashboard pipeline | `research/<T>.json`: your narrative dashboard's output (stories with continuity, events) for every covered name |
| 4 Analysts | `analysts.py` | yes, one per name | `analysts.json`: thesis, catalysts, risks, score, confidence |
| 5 Red team | `redteam.py` | yes, per conviction | `redteam.json`: uphold / weaken / reverse, adjusted score |
| 6 PM + risk | `pm_risk.py` | no | `book.json`: fund, analyst, quant, core20 and random books, plus the risk report |
| 7 IC memo | `ic_memo.py` | yes | `ic_memo.md`: the week's written record |
| 8 Macro | `fx_desk.py` | yes | `fx.json`: 17-currency book plus quant and random |
| 9 Performance | `score.py` | no | `performance/`: weekly P&L per book, stage tests, `summary.md` |

**Research reuses the narrative dashboard.** `research.py` runs
`andreaskoul/my-website`'s `pipeline/fetch.py` and `build.py` at a pinned
commit on whatever this week's coverage list is. Curated firms keep your
match regexes; new names get one built from the S&P 500 security name.

**The news is stored, not re-fetched.** Every run (dry runs included) saves the
raw feeds and story state to the `fund-data` branch. Each week `fetch.py` asks
Finnhub only for the gap since a firm's newest stored article. The dashboard's
own 20 feeds (updated daily on my-website) are merged in first, so those usually
need no calls at all. Only a firm covered for the very first time pulls 91 days.
A firm that drops out keeps its archive and catches up when it returns.
Embeddings are stored permanently in a private Hugging Face dataset
(`<you>/fund-embeddings`, via `fund/emb_store.py` and the `HF_TOKEN` secret), with
the Actions cache as a fast path, so only new articles are ever embedded.

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

Secrets: `OPENROUTER_API_KEY`, `FINNHUB_API_KEY`, and optionally `POLYGON_API_KEY`.
