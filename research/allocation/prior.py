"""Inputs of the allocation pre-registration (PREREG_ALLOCATION.md): every number is read from a named field of a
committed result file, at a named git revision, and written to PRIOR.json. No new statistic of any return series is
computed here; the only arithmetic is pooling published Sharpe ratios, a normal-normal posterior, tangency sizing and
power. Run: python3 research/allocation/prior.py  (from the repo root)."""
import json
import math
import subprocess

from statistics import NormalDist

REV_MAIN = "e6d31de"                  # origin/main at registration (PR #190 merged)
REV_TREE = "7c13fd7"                  # research/tree-layer3, step 46 (R3)
N = NormalDist()


def show(rev, path):
    return json.loads(subprocess.check_output(["git", "show", f"{rev}:{path}"], text=True))


ovr = show(REV_MAIN, "research/sharpe/RESULT_OVERLAY_RULE.json")
r3 = show(REV_TREE, "research/tree/R3_master_pit/RESULT.json")
h7 = show(REV_TREE, "research/tree/H7_DECOMP.json")

S_c = ovr["core"]["S_c"]                                    # 1927-2026 core, arm M under (R)
sig_c = ovr["core"]["sigma_c_pct"]
sig_unit = ovr["sigma_unit_pct_MASTER_book_per_unit_gross"]
dev = ovr["rows"]["MASTER book, development 2013-2019"]
s25_unrep = ovr["rows"]["MASTER book, 2020-2025 walk-forward (reused)"]["S_hat"]
s25 = r3["P7_book_and_fund"]["REPAIRED"]["book"]["sharpe"]  # survivorship-repaired
pct25 = h7["fund"]["master_book_2026_vs_2020_2025"]["pct_2020_2025"]
pct26 = h7["fund"]["master_book_2026_vs_2020_2025"]["pct_2026"]
w26 = h7["fund"]["by_year_pct_per_year"]["2026"]["weeks"]
vol25 = pct25 / s25_unrep                                   # %/yr book vol implied by the unrepaired 2020-25 pair
s26 = pct26 / vol25                                         # 2026 book Sharpe, at the 2020-25 vol (approximation)
y26 = w26 / 52

samples = [("development 2013-2019 (walk-forward)", dev["S_hat"], dev["years"]),
           ("2020-2025 (walk-forward, reused, survivorship-repaired)", s25, 6.0),
           ("2026 to the sealed test's last week", s26, y26)]
T = sum(y for _, _, y in samples)
S_pool = sum(s * y for _, s, y in samples) / T
se_pool = math.sqrt((1 + S_pool ** 2 / 2) / T)              # Lo (2002), iid


def posterior(s, se, prior_sd=0.5):
    """Normal prior N(0, prior_sd^2) on the annual Sharpe, normal likelihood N(s, se^2)."""
    k = prior_sd ** 2 / (prior_sd ** 2 + se ** 2)
    return k * s, math.sqrt(1 / (1 / prior_sd ** 2 + 1 / se ** 2))


def tangency_gross(S_o):
    """Gross of the book at the two-sleeve tangency sigma_o / sigma_c = S_o / S_c (uncorrelated sleeves)."""
    return max(0.0, sig_c * S_o / S_c / sig_unit)


def combined(S_o_true, gross):
    """Excess Sharpe of core (S_c, sig_c) plus an uncorrelated book of `gross`, when the book's true Sharpe is S_o_true."""
    so = gross * sig_unit
    return (S_c * sig_c + S_o_true * so) / math.sqrt(sig_c ** 2 + so ** 2)


post_all = posterior(S_pool, se_pool)
post_25 = posterior(s25, math.sqrt((1 + s25 ** 2 / 2) / 6))

# power of a forward test of the book's Sharpe against the Sharpe implied by today's sizing
gross_now = 0.6
S_implied = S_c * gross_now * sig_unit / sig_c
power = {}
for weeks in (52, 104, 156, 260):
    yrs = weeks / 52
    for S_true in (0.4, 0.7):
        se = math.sqrt((1 + S_true ** 2 / 2) / yrs)
        z = (S_true - S_implied) / se
        power[f"{weeks}w_S{S_true}"] = round(1 - N.cdf(1.645 - z), 3)

out = {
    "revisions": {"main": REV_MAIN, "tree": REV_TREE},
    "core": {"S_c": S_c, "sigma_c_pct": sig_c, "sigma_unit_pct": sig_unit},
    "samples": [{"label": l, "sharpe": s, "years": y} for l, s, y in samples],
    "note_2026": "2026 Sharpe = pct_2026 / (pct_2020_2025 / S_hat_2020_2025_unrepaired): the 2020-25 book vol is used",
    "pooled": {"S": S_pool, "years": T, "se_lo2002": se_pool},
    "posterior_prior_sd_0.5": {"all_evidence": {"mean": post_all[0], "sd": post_all[1]},
                               "2020_2025_only": {"mean": post_25[0], "sd": post_25[1]}},
    "tangency_gross": {"S_implied_by_gross_0.6": S_implied, "posterior_all": tangency_gross(post_all[0]),
                       "posterior_2020_2025_only": tangency_gross(post_25[0]), "S_0.70": tangency_gross(0.70)},
    "combined_sharpe": {f"true_{t}": {f"gross_{g}": round(combined(t, g), 3) for g in (0.0, 0.43, 0.6, 0.9, 1.2, 1.96)}
                        for t in (0.0, 0.2, 0.4, 0.7)},
    "sharpe_needed_for_1": {"one_book": math.sqrt(1 - S_c ** 2), "two_equal_independent_books": math.sqrt((1 - S_c ** 2) / 2)},
    "power_one_sided_0.05_vs_S_implied": power,
    "posterior_prior_sd_1.0_all_evidence": dict(zip(("mean", "sd"), posterior(S_pool, se_pool, 1.0))),
}

# check that can fail: the tangency gross maximises the combined Sharpe on a fine grid (a wrong sign or a swapped
# ratio in tangency_gross fails it)
for S_true in (0.2, 0.4, 0.7):
    grid = [i / 1000 for i in range(0, 4001)]
    best = max(grid, key=lambda g: combined(S_true, g))
    if abs(best - tangency_gross(S_true)) > 0.002:
        raise SystemExit(f"tangency check failed at S={S_true}: grid {best} vs formula {tangency_gross(S_true):.4f}")
json.dump(out, open("research/allocation/PRIOR.json", "w"), indent=1)
print(json.dumps(out, indent=1))
