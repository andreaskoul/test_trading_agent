# News-driven long-short fund

A weekly long-short book on S&P 500 stocks, decided by a funnel of LLM and quant desks
from each company's news narratives, hedged to zero market beta with SPY, traded in the
Thursday closing auction on an Alpaca paper account and reviewed daily against new news.
Every rule is pre-registered before results exist, and a pre-registered gate decides whether
it may ever trade real money.

* **How it works:** [`fund/README.md`](fund/README.md): schedule, desks, risk controls,
  evaluation, storage, testing.
* **Protocol:** [`reports/research/PROTOCOL_fund.md`](reports/research/PROTOCOL_fund.md)
  (Protocol 6 and its amendments); operational changes in [`fund/CHANGELOG.md`](fund/CHANGELOG.md).
* **Design evidence:** [`reports/Multi agent AI trading desk design.md`](reports/Multi%20agent%20AI%20trading%20desk%20design.md)
  and its notes in `research_notes/`.
* **Live monitor:** https://andreaskoul.github.io/test_trading_agent/
* **Records:** the `fund-data` branch (decisions, prompts, orders, fills, reviews,
  performance, Excel ledger).

## Layout

```
fund/                  desks, execution, review, ledger, dashboard page (fund/site/)
.github/workflows/     fund_weekly · fund_execute · fund_review · fund_archive · fund_pages · fund_llm_check
artefacts/llm/         frozen ridge specs (benchmark and FX desk)
data/raw/stocks/       S&P 500 membership fallback files
reports/               protocol and evidence review
research_notes/        notes behind the evidence review
```

The earlier projects (the DL+RL gold agent, research protocols 1–5 and their reports)
live on the `legacy-gold-agent` branch.
