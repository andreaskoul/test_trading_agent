# Proposal: Protocol 10, hedge the stock book with the intraday-calibrated beta (draft for the owner)

*2026-11-08. Owner: "If it works successfully and statistically then we should enhance our models with these
additions; if that's a new protocol so be it." Nothing here is live. The code change below touches the traded
fund, so it needs the owner's approval.*

## What passed, and what it changes

| Addition | Evidence | Where it enters | Proposed |
|---|---|---|---|
| **B1 beta** = 0.0030 + 0.332 × HF beta over 21 sessions + 0.269 × HF beta over 63 sessions + 0.389 × the fund's winsorised 252-day OLS beta (`research/riskfield/FROZEN_B1.json`) | OOS 2020–25, read once: error in next month's realised beta −33% (t 7.56, Holm p < 1e−13); better in every year; hedged books' variance lower (P1, Holm p 0.016) | the SPY hedge of the 7B book, hence λ × hedge in the Protocol 9 account | **adopt, Protocol 10** |
| **F2 short-volume tilt** | OOS t −1.88 (p 0.030); +2.1% a year at 2 bp; S&P 400 replication p 0.054 (narrow fail) | — | **not yet**: forward paper book from 2026-11-12; adoption rule below |
| **Momentum panic switch** | US OOS + international replication (Holm p 0.007) | the S&P AI research books (momentum-heavy), not the 7B news book | forward paper books from 2026-11-12; unchanged |

## The rule (Protocol 10)

From session **P10 = 2026-11-23** (proposed: one week after Protocol 9's first traded session, so that its first
week is clean):
* **Hedge beta.** On every compute day, the SPY hedge of every lifecycle book (the live 7B model and its shadow
  control) is −Σ_lots n × B1(ticker), where B1(ticker) is the name's value in the latest weekly screen.
  * The latest screen is the one entered with the most recent cohort; its screen is as-of the Wednesday before.
  * A name without B1 (missing bars) uses its lot beta, as today.
* **Unchanged:**
  * the residual returns behind stops, targets, CAR and entry volatility keep the lot beta (`beta_hedge`), so the
    7B rules stay as calibrated;
  * sizing (`caps`), the REHEDGE band (10%), the account core, λ and the 1.9× cap are unchanged.
* **Why the 7B clock keeps running** (owner to confirm): the change is a risk-measurement change applied equally to
  the live book and its control. The 7B gate still compares the same stock-selection rules, and Protocol 9 already
  scores the account on its own fidelity gate.
* **Reversion rule** (mechanical). At 26 scored weeks of the forward beta records (`research-data:.../beta/ledger.json`,
  about 2027-05), if the mean weekly squared-error gain of B1 over B0 is ≤ 0, the hedge returns to B0 from the next
  session.
* **Data.** The weekly job's screen adds `beta_b1` from Alpaca 30-minute SIP bars, using the code and cache of the
  forward beta records (`research/riskfield/forward.py`, `~/.fund-runner/cache/spx`). The weekly job already has the
  Alpaca keys.
  * If the bars fail, `beta_b1` is NaN, the hedge falls back to B0, and an issue is opened. The desk is never
    blocked.

## F2 adoption rule (pre-registered now, decided later)

After 52 booked weeks of the forward F2 book (about 2027-11), F2 is proposed as an overlay if its forward net mean
is > 0 with one-sided p < 0.10. Size: a fixed small fraction of the account, set then. Otherwise it is retired.

## The code change (to apply on approval)

1. `fund/lifecycle_rules.py`: `P10 = pd.Timestamp(os.environ.get("FUND_P10") or "2026-11-23")`.
2. `fund/screen.py`: after `beta_hedge`, add `Z["beta_b1"]` from `research/riskfield/forward.py` (loaded by path):
   * `bars_for(members + ["SPY"], last 63 sessions to as-of)`, then `day_returns`;
   * `hf_beta` over the last 21 and 63 sessions;
   * `b1(FROZEN_B1, hf21, hf63, beta252w)`;
   * all in a `try`; on failure, NaN and `beta_b1_status` recorded in screen.json.
3. `fund/lifecycle.py`:
   * `cohorts()` carries `"beta_h": S["beta_b1"].dropna().to_dict()`;
   * `run()` keeps `hb_now`, updated with each cohort's `beta_h` on its entry day;
   * in step 4 (SPY hedge), `stock_beta = Σ n × (hb_now.get(ticker, L["beta"]) if d ≥ P10 else L["beta"])`.
4. Runner: one `allow_fail` step after the screen that opens an issue if `beta_b1_status` is not ok or coverage
   < 90%.
5. Tests (`fund/tests/test_p10.py`):
   * a rebuild of every recorded lifecycle day is unchanged to the cent (all before P10);
   * after P10, the hedge equals −Σ n × B1 on a fixture;
   * a missing B1 falls back to the lot beta;
   * the screen with failed bars still writes, with NaN.
6. `PROTOCOL_fund.md`: a Protocol 10 section; a CHANGELOG line; site: "Protocol 10 from 23 Nov" on the account
   section.

## Checks before the first session

* All contract tests pass.
* The shadow sessions of the week before P10 log both hedges (B0 and B1) for inspection.
* The owner gives go/no-go.
