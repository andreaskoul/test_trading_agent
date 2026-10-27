"""Protocol 7B rules (PROTOCOL_fund.md, Protocol 7B; owner 2026-10-27), pure so they are contract-tested
(fund/tests/test_lifecycle_rules.py). fund/lifecycle.py calls them; the catalyst session comes in as an argument.

"""
import math
import os

import numpy as np
import pandas as pd

N_SIDE = 10                     # as fund/lifecycle.py (Amendment 7)

# From session P7B the live book applies
# R1 no averaging down (a news increase only when the lot's R >= 0), R2 structural theses (desk label; horizon to the
# next earnings report + 1, between the Amendment 8 horizon and STRUCT_MAX, STRUCT_DEFAULT without a dated report;
# exit at a STRUCT_CHECK-session checkpoint if R / (sigma_e sqrt(days)) <= STRUCT_Z; review extensions up to
# STRUCT_MAX in total), R3 slot protection (a carried lot with R >= 0 inside its horizon keeps its slot).
# Gated by date so recorded days never change; desk cohorts from as-of P7B_ASOF carry the structural label.
P7B = pd.Timestamp(os.environ.get("FUND_P7B") or "2026-10-28")
P7B_ASOF = os.environ.get("FUND_P7B_ASOF") or "2026-10-28"
STRUCT_MAX, STRUCT_DEFAULT, STRUCT_CHECK, STRUCT_Z = 63, 40, 20, -1.0


def may_increase(d, L):
    """7B R1: from P7B a news increase needs the lot to be working (R >= 0); before P7B, Amendment 7 as it was."""
    return not (d >= P7B and L["R"] < 0)


def checkpoint_exit(d, L):
    """7B R2: a structural lot is checked every STRUCT_CHECK sessions inside its horizon; it exits when
    R / (sigma_e sqrt(days)) <= STRUCT_Z (sigma_e frozen at entry)."""
    return bool(d >= P7B and L.get("structural") and 0 < L["days"] < L["H"] and L["days"] % STRUCT_CHECK == 0
                and L["R"] / (L["sigma_e"] * math.sqrt(L["days"])) <= STRUCT_Z)


def slots(target, cur, key, d):
    """At most N_SIDE names a side by `key`; 7B R3: from P7B a carried lot that is working (R >= 0) inside its horizon
    is ranked ahead of every other name."""
    prot = {t for t in cur if t in target and d >= P7B and cur[t]["R"] >= 0 and cur[t]["days"] < cur[t]["H"]}
    keep = []
    for sgn in (1, -1):
        side_ = sorted([t for t in target if np.sign(target[t]) == sgn], key=lambda t: (t not in prot, -key[t]))
        keep += side_[:N_SIDE]
    return keep


def structural_h(h_a8, cal_e, days, t0, cs):
    """Protocol 7B, R2: a structural thesis is held to the firm's next earnings report (+1 session), between the
    Amendment 8 horizon and STRUCT_MAX; STRUCT_DEFAULT when the calendar has no report date within reach.
    cs: the session that first trades on the report (lifecycle.catalyst_session), or None."""
    if cs is not None and cs > t0:
        n_to = sum(1 for d in days if t0 < d <= cs)
        h = int(min(max(n_to + 1, h_a8), STRUCT_MAX))
        return h, f"structural: next report {cal_e[0]} ({cal_e[1] or 'time n/a'}): {n_to} sessions + 1 -> H {h}"
    h = int(min(max(STRUCT_DEFAULT, h_a8), STRUCT_MAX))
    return h, f"structural: no dated report -> H {h}"


def structural_mean(flags, hs, h_struct):
    """7B R2, the horizon over the desk's samples (as Amendment 8 averages its horizons, because a 3-2 split on a
    label moved the horizon by weeks): each sample's horizon is h_struct if that sample labels the thesis structural,
    else its own Amendment 8 horizon (0 if it would not enter); H is the mean, at most STRUCT_MAX."""
    hs7 = [h_struct if f else h for f, h in zip(flags, hs)]
    return min(float(sum(hs7)) / len(hs7), STRUCT_MAX), hs7
