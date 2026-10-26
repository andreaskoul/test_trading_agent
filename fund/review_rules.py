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
"""


def review_rule(kill_hit, label, z, idisc, to, catalyst, z_hi, id_hi, to_lo):
    """(decision, rule) for a lot at its horizon: decision is "exit" or "extend"."""
    confirming, contradicting = label == "CONFIRMING", label == "CONTRADICTING"
    if kill_hit or contradicting:
        return "exit", 1
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
