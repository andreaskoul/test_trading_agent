# Proposal: a release review for positions held through an earnings report (draft, 2026-11-03)

**Status:** proposal for the owner. Phase 1 is measurement only. Phase 2 would be a Protocol 7B amendment, decided on
Phase 1's evidence.

## The case that prompted it: AAPL, November 2026

* **The position.** Short 2.5% of NAV from 2026-10-22 (cohort 2026-10-21), horizon 8 sessions. Kill condition 1:
  *"Apple reports stronger-than-expected iPhone 18 demand or raises forward guidance."*
* **The report.** Apple's 8-K item 2.02 was accepted at 21:30 UTC on Mon 2 Nov, after the close. The fund's last news
  check had run at 20:40 UTC, so no check had seen it.
* **The release (EX-99.1)** reported records: revenue $114.5B (+12%), record iPhone revenue, Services at an all-time
  high, EPS $2.10 (+14%). It gave no guidance; Apple gives guidance on its call.
* **The price.** AAPL fell about 2.8% after hours. The market judged the quarter against expectations and the
  outlook, not against last year.

**The gap.** The thesis is re-checked only through headlines (the news kill check, at T−20) and, at the horizon, the
end-of-horizon review. Neither sees:
* the reported numbers, with their source;
* what was expected (consensus);
* the guidance in numbers.

So a kill condition written in terms of expectations ("stronger than expected") is judged from headlines. "Record
iPhone revenue" can read as a match while the stock falls. Coverage of the call, where the guidance is, can also be
missed. Separately, the desk can open a position whose horizon runs through a known report without anyone choosing
that. 7B Amendment 1 treats only losing positions.

## The proposal

For every open position whose firm's 8-K item 2.02 is accepted while it is held:

1. **Detect the release.** The daily run reads SEC's live API for held tickers (`lifecycle.edgar_202`, times
   converted from UTC to Eastern by `fund/edgar_time.py`). Each acceptance is logged once.
2. **Freeze the expectation before the release.** Every daily run stores the earnings calendar's EPS and revenue
   estimates for held names with a report due within 10 sessions. The value is frozen at first fetch (CLAUDE.md
   rule 4). Only the snapshot taken before acceptance counts.
3. **Read the release itself.**
   * At the first decision after acceptance, take the EX-99.1 from the filing's typed index (`guards.typed_exhibit`)
     and run its content contract (`guards.release_check`).
   * One guarded model call at temperature 0, with R5's card schema, extracts revenue, EPS and any guidance in
     numbers.
   * Every number must appear in the release (`guards.grounding`). A failure is an `input_defect` and is counted.
4. **Surprise, computed rather than read.** Revenue and EPS surprise in percent against the frozen consensus.
   Guidance is raised, maintained, lowered or absent, as stated in the release.
5. **The thesis check on numbers.** The kill check for that position gets a "RELEASE FACTS" block (the numbers, the
   surprise and the guidance, each with its source). Conditions written in terms of expectations are judged against
   the surprise, not against year-on-year records. As before, no price is shown to the model.
6. **The market's reaction, recorded only.** The residual move from the last close before the release to the decision
   price is logged and never used in a decision.
7. **Exposure flag at entry, recorded only.** Each new position logs whether a dated report falls inside its horizon.

## Phase 1 (measurement only, operational): log the release review beside the live check

* The release review runs and is logged for every qualifying position. **Live decisions are unchanged.**
* The decision ledger gets one row per release event:
  * the headline check's verdict;
  * the release review's verdict;
  * the surprise and guidance;
  * the reaction move;
  * what followed: residual return over 1, 5 and 10 sessions.
* **Content checks** (CLAUDE.md rule 11): the first 10 release reviews are opened next to their press releases.
* CHANGELOG: "Could this change a decision? No."

## Phase 2 (a 7B amendment, owner decision): the release review decides the first session after a report

**When.** After at least 20 release events, or at the 13-week look, whichever comes later. We are in reporting season,
so 20 should come within weeks.

**What decides it (no return test).** At this size a returns test has no power (DESIGN_RULES.md rule 3). The criteria
are about getting the facts right:
* at least 95% of release reviews grounded, with input defects reported;
* every disagreement between the headline check and the release review audited by hand against the press release;
* the release review is adopted if it is right in at least 80% of the disagreements, and the headline check in no
  more than 20%.

Returns after each verdict are reported, descriptive only.

## Cost and effort

* About one model call per release event: under $0.01 each, and a few dollars a season.
* SEC requests stay within its fair-access limit.
* The code is assembled from existing parts: `guards.typed_exhibit`, `guards.release_check`, `guards.grounding`,
  R5's card schema, `lifecycle.edgar_202` and the earnings calendar. The new parts are the pre-release consensus
  snapshot, the RELEASE FACTS block, the ledger rows and contract tests on the AAPL release as a real fixture.

## What it does not do

* It does not override the fund by hand.
* It does not put prices in prompts.
* It does not change entries. The exposure flag only records.
* Whether to avoid entering ahead of known reports is a separate question. The flag supplies the evidence for it.

## Outcome of the AAPL case (added 2026-11-06): the headline check got it right

* **On 3 Nov,** the first check after the release, all three news passes rated kill condition 1 *partial*. They cited
  the facts that contradicted the thesis:
  * "upbeat sales forecast";
  * EPS and revenue above estimates;
  * a record iPhone quarter.

  All three also flagged the 45–46% holiday gross-margin guidance as hard news in the short's favour.
* **The end-of-horizon review** labelled the news CONTRADICTING. The short was bought back at $332.01, +3.8% net of
  SPY. AAPL rose +5.3% the next day.
* **The thesis** ("Loop Capital downgrade, caution on iPhone demand") was wrong. The trade earned on margins, a reason
  outside it.

**What this changes in the proposal.** For a heavily covered company, the headline check read the release correctly,
so the case for Phase 2 is narrower than first argued. The release review's value is likely to be greatest:
* for thinly covered names, where a 25- to 60-article window may hold no coverage of the results;
* where a kill condition turns on an exact number, such as a guidance range against consensus.

Phase 1 should therefore record each release event's article count, so its disagreements can be read by coverage. The
decision rule is unchanged.
