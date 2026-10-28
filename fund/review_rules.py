"""The horizon-end review's decision (PROTOCOL_fund.md, Amendment 8 B, as amended by Amendment 9): pure, so the
rules are tested on their own (fund/tests/test_review_rules.py). fund/lifecycle.py computes the inputs from data.

First match wins:
1. kill partial, or CONTRADICTING news: exit;
2. z <= 0 and no catalyst: exit (the thesis has not worked);
3. z >= z_hi with neither CONFIRMING news nor a catalyst: exit (the move is done);
4. ID > id_hi and TO < to_lo, without CONFIRMING news: exit (a jumpy path on fading interest);
5. extend if 0 < z < z_hi and (CONFIRMING, or a catalyst, or ID <= 0 with TO >= to_lo);
   Amendment 9: also extend if z >= z_hi and (CONFIRMING, or a catalyst), the case rule 3 exempts;
   otherwise exit.

Protocol 7B Amendment 1 (owner, 2026-10-28; live book only, from session A7B1): a losing lot with earnings expected
stays open, and closes only if the thesis is structurally changed. After rule 1 (kill condition or CONTRADICTING
news, which still closes it):
E1. z <= 0 and the firm's next earnings report falls within the hold cap: extend past the report;
E2. z <= 0, the lot was held for a report that has now passed, and the news did not contradict it: extend.
The extension limit (two), the hold cap (40 sessions in total, 63 for structural theses) and the stop still bound it.
"""


def review_rule(kill_hit, label, z, idisc, to, catalyst, z_hi, id_hi, to_lo,
                earnings_hold=False, report_within_cap=False, after_report=False):
    """(decision, rule) for a lot at its horizon: decision is "exit" or "extend".
    earnings_hold: Protocol 7B Amendment 1 applies (the live book from A7B1; never the shadow control).
    report_within_cap: the next earnings report falls within the hold cap. after_report: the lot was held for a report
    that has passed."""
    confirming, contradicting = label == "CONFIRMING", label == "CONTRADICTING"
    if kill_hit or contradicting:
        return "exit", 1
    if earnings_hold and z <= 0:
        if report_within_cap:
            return "extend", "E1"
        if after_report:
            return "extend", "E2"
    if z <= 0 and not catalyst:
        return "exit", 2
    if z >= z_hi and not confirming and not catalyst:
        return "exit", 3
    if idisc > id_hi and to < to_lo and not confirming:
        return "exit", 4
    if 0 < z < z_hi and (confirming or catalyst or (idisc <= 0 and to >= to_lo)):
        return "extend", 5
    if z >= z_hi and (confirming or catalyst):
        return "extend", 5
    return "exit", 5
