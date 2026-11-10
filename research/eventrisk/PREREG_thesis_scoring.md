# Are the theses' confidence and labels informative? Pre-registration of one read

*Written 2026-11-10, before any outcome statistic was computed. `PLAN.md`, Decision 7. Research only: nothing here
changes a desk. Any change to sizing or prompts that the result suggests is a proposal for the owner.*

## 1. What was already seen (disclosed)

On 2026-11-09, to size this read, the live record was counted: 69 entries; 49 exits (29 at the horizon, 11 for
capacity, 5 on news, 3 flips, 1 stop); five-sample classification for 23 entries, 5 of them not unanimous on the news
type. While inspecting the file format, the fields of one open position were displayed, including its running
return. No outcome was tabulated against confidence, news type or sample agreement.

## 2. When, and on what

* **Trigger:** the first scheduled count on or after 2027-01-16 that finds at least **150 closed positions** in the
  live book (`fund_state/live/lifecycle/state.json` on `fund-data`). Checks before that count positions only.
* **Unit:** a closed position (a lot with a final exit of any cause).
* **Outcome:** R ÷ W at exit: the position's cumulative hedged return, signed by its side, in units of its own
  stop width W, both as recorded by the fund.
* **Inputs, as recorded at entry:** the confidence used for sizing (after the critic); the news type and its hard or
  soft class; the classification samples of the weekly record.
* **Contracts:** a position without a recorded confidence, W or exit is an input defect: counted, reported, excluded.
  Coverage is reported against all closed positions.

## 3. Three questions, one read (`THESIS_READ.lock`)

| | Question | Statistic and test | Needs |
|---|---|---|---|
| **Q1** | Do higher-confidence positions do better? | Spearman correlation of confidence with R ÷ W; one-sided permutation test (10,000 permutations within the entry week, seed 20261110) | all positions |
| **Q2** | Do hard-news and soft-news positions end differently? | share ending by a news exit or a stop ("the thesis failed"), hard against soft; Fisher's exact test, two-sided | at least 20 in each class |
| **Q3** | Do positions whose five samples agreed on the news type do better than split ones? | difference of mean R ÷ W, unanimous minus split; one-sided permutation test within the entry week | at least 30 in each group |

Holm across the questions that meet their minimum, at α = 0.05. A question below its minimum is reported, not tested.

**Reported beside the tests:** exit cause by news type with Wilson intervals (the base rates); mean and median R ÷ W
by score (−2, −1, +1, +2); every result again without capacity exits; the number of defects.

## 4. Power, stated beforehand

With 150 positions, a true rank correlation of 0.2 is detected with about 80% probability (one-sided 5%); 0.1 is not.
A null here means "no evidence at this sample size", not "confidence is uninformative".

## 5. Consequences, fixed now

* **Q1 passes:** sizing by confidence stays; it then becomes worth asking the model for the probability of a defined
  event, and that proposal goes to the owner (the return half of the second tightening of the prediction-to-price
  model depends on it).
* **Q1 fails:** propose to the owner that weights no longer depend on confidence (score only), as a protocol; no
  probability elicitation.
* **Q2:** the base rates become the benchmark any model probability must beat; no rule changes by itself.
* **Q3 passes:** propose that a split classification scales the entry down; fails: nothing.
* The read is made once. Re-reading after more positions accumulate needs a dated amendment written first.
