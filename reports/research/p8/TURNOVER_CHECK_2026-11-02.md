# Turnover cuts on the live record: not worth an amendment (2026-11-02)

**Proposed in** `reports/Actionable ideas for the event fund.md`: renewal at horizon expiry, resize bands and hedge
netting. The research notes put the renewal saving at about 0.1–0.3% a year. **Checked on** the live lifecycle record
(fund-data, `lifecycle/state.json`): 17 sessions, 2026-10-08 to 10-30, about $98k NAV.

**Traded notional: $460,516, about 70× NAV a year. Recorded cost: $230 at 5 bp, about 3.4% a year.**

| action | trades | notional | share |
|---|---:|---:|---:|
| entry | 59 | 192,685 | 41.8% |
| hedge (SPY) | 8 | 91,588 | 19.9% |
| horizon exit | 24 | 83,909 | 18.2% |
| news increase | 16 | 34,373 | 7.5% |
| capacity exit | 9 | 24,594 | 5.3% |
| news reduce / exit, flip, stop | 12 | 33,355 | 7.2% |

* **Renewal** (an exit followed within 5 sessions by a same-side re-entry of the same name): 2 cases, NVDA on 10-14 and
  NFLX on 10-21.
  * They are 1.5% of turnover; renewing would have saved $1.0–3.4 over the period, 0.03–0.1% a year.
  * Holding through the gap would have earned −212 and −427 bp.
* **Hedge netting.** One SPY order per decision is already the rule. Of the four pairs of hedge trades on consecutive
  sessions, only one (10-29 → 10-30) ran in opposite directions.
  * Netting it would have saved $11.9k of notional, 2.6% of turnover, worth $1.8–6.
  * Hedge trades are 6–47% of stock gross: changes in the book, not drift. A beta band would remove almost none.
* **Resize bands.** Resizes already wait for a 25% band (`BAND`), and news increases are rare after 7B R1.

**Conclusion.** About 4% of turnover is avoidable by these rules, worth about 0.05% a year at live cost and 0.14% at
the registered cost. That does not justify a decision-changing amendment. **Turnover comes from the design itself:**
weekly cohorts, horizons of about 4–20 sessions, and a hedge that follows the book. It falls only if the book trades
fewer names, and that needs an entry bar that picks better trades. No such bar is known yet:
* hard news is about break-even (`HARD_NEWS.md`);
* the desk's weight rank IC is −0.12 at 5 sessions over 3 cohorts (decision ledger).

Re-check when the record is 13 weeks long (late January 2027).
