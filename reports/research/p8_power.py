"""Power of the P8 decision rule for a monthly long-short signal with true annual Sharpe S.

Model: monthly long-short returns i.i.d. with mean mu, sd sigma, SR_m = S / sqrt(12). Over T months the FM / mean
t-statistic is approx N(delta, 1) with delta = SR_m * sqrt(T) (large-T; NW lag 3 changes little under i.i.d.).
Validation T = 48 (2022-25), halves 24 + 24, sealed T = 9 (Jan-Sep 2026).
Pass = validation one-sided p < Holm threshold (best case: first step, 0.05/7)
       AND both halves' means > 0
       AND sealed one-sided p < 0.05 / k (Holm among k survivors; best case k = 1)
Monte Carlo on the exact Gaussian model, 200k draws.
"""
import numpy as np
from scipy.stats import norm

rng = np.random.default_rng(7)
N = 200_000


def p_pass(S, T_val=48, T_seal=9, m=7, k_seal=1, holm_step=1):
    srm = S / np.sqrt(12)
    a_val = 0.05 / (m - holm_step + 1)
    h1 = rng.normal(srm * np.sqrt(24), 1, N)          # t of each half
    h2 = rng.normal(srm * np.sqrt(24), 1, N)
    t_val = (h1 + h2) / np.sqrt(2)                     # t of the full 48 months
    val = (t_val > norm.ppf(1 - a_val)) & (h1 > 0) & (h2 > 0)
    t_seal = rng.normal(srm * np.sqrt(T_seal), 1, N)
    seal = t_seal > norm.ppf(1 - 0.05 / k_seal)
    return val.mean(), (val & seal).mean()


def s_needed(target=0.5, **kw):
    lo, hi = 0.0, 6.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if p_pass(mid, **kw)[1] < target:
            lo = mid
        else:
            hi = mid
    return hi


print("true annual Sharpe | P(pass validation) | P(pass validation and sealed)")
for S in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
    v, b = p_pass(S)
    print(f"{S:>5.2f} | {v:6.3f} | {b:6.3f}")
print(f"Sharpe needed for 50% overall pass (as registered): {s_needed():.2f}")
print(f"... if validation were 2019-25 (84 months):        {s_needed(T_val=84):.2f}")
print(f"... and the sealed read were 21 months (to 2027-09): {s_needed(T_val=84, T_seal=21):.2f}")
# false positive rate under the null for one signal, and family-wise across 7 nulls (independent approx.)
v0, b0 = p_pass(0.0)
print(f"null: P(one signal passes everything) = {b0:.5f}; family-wise (7 indep.) ~ {1 - (1 - b0) ** 7:.5f}")

# event-level test (H1, H3b, H4): t ~ rho * sqrt(n / DE), DE = 1 + (m_c - 1) * icc (cluster design effect)
print("\nevent-level: correlation rho needed for 80% power at alpha 0.05/7 one-sided")
z = norm.ppf(1 - 0.05 / 7) + norm.ppf(0.8)
for n, mc, icc in ((4800, 15, 0.05), (4800, 15, 0.15), (1200, 15, 0.10)):
    de = 1 + (mc - 1) * icc
    print(f"n={n}, cluster size {mc}, ICC {icc}: design effect {de:.2f}, n_eff {n / de:.0f}, rho* = {z / np.sqrt(n / de):.3f}")

# R3: binary target, LPM slope; hit rate h vs 0.5 with n reports per season, design effect DE
print("\nR3: t per season for centred hit rate h, n = 900")
for h in (0.52, 0.55, 0.58):
    for de in (1.0, 2.0, 3.0):
        print(f"h {h}: DE {de}: t = {(h - 0.5) / np.sqrt(0.25 * de / 900):.2f}")


def p_alt(S, rule, T_val=48, T_seal=9, m=7):
    srm = S / np.sqrt(12)
    h1 = rng.normal(srm * np.sqrt(T_val / 2), 1, N); h2 = rng.normal(srm * np.sqrt(T_val / 2), 1, N)
    t_val = (h1 + h2) / np.sqrt(2); ts = rng.normal(srm * np.sqrt(T_seal), 1, N)
    c = norm.ppf(1 - 0.05 / m)
    if rule == "sealed_sign":      # validation as registered; sealed only needs the right sign
        ok = (t_val > c) & (h1 > 0) & (h2 > 0) & (ts > 0)
    elif rule == "pooled":         # one Holm test on validation + sealed pooled, halves sign kept
        tp = (t_val * np.sqrt(T_val) + ts * np.sqrt(T_seal)) / np.sqrt(T_val + T_seal)
        ok = (tp > c) & (h1 > 0) & (h2 > 0)
    return ok.mean()


print("\nalternatives (P overall pass), validation 48 months, sealed 9")
print("Sharpe | registered | sealed sign only | pooled 57 months | sealed sign, validation 2017-25 (108 m)")
for S in (0.5, 0.75, 1.0, 1.5):
    print(f"{S:>5.2f} | {p_pass(S)[1]:.3f} | {p_alt(S, 'sealed_sign'):.3f} | {p_alt(S, 'pooled'):.3f} | {p_alt(S, 'sealed_sign', T_val=108):.3f}")
for rule in ("sealed_sign", "pooled"):
    print(rule, "null P(pass) per signal:", round(p_alt(0.0, rule), 5))
