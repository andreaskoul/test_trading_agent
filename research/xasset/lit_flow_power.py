"""Design arithmetic for LIT_FLOW (no data read). Normal approximations.
Predictive regression: noncentrality = sqrt(T * R2 / (1 - R2)); one-sided power = Phi(nc - z).
Mean difference (spike months vs others): nc = d / (sigma*sqrt(1/n1+1/n2)).
Plug-in TE null bias (Kirkley 2025, eq. S34): C^l (C^k - 1)(C - 1) / (2N), as printed.
Gaussian TE for a linear R2 (Barnett-Barrett-Seth 2009, eq. 13): TE = F/2, F = -ln(1 - R2) nats; bits = /ln 2.
Timed Sharpe (Campbell-Thompson style identity, reasoning): S*^2 = (S^2 + R2)/(1 - R2), monthly.
"""
import json, math
from statistics import NormalDist
N = NormalDist()
Z = {"5%": N.inv_cdf(0.95), "0.10/40": N.inv_cdf(1 - 0.10/40), "family_holm_0.10/6": N.inv_cdf(1 - 0.10/6)}
out = {"z": {k: round(v, 3) for k, v in Z.items()}, "regression": {}, "spike": {}, "te": {}, "timed_sharpe": {}}
for name, T in {"H1_T480": 480, "H2_T264": 264, "H3_T348": 348, "daily_T10000": 10000}.items():
    for r2 in (0.0025, 0.005, 0.01, 0.02, 0.035) if "daily" not in name else (0.0002, 0.0005, 0.001):
        nc = math.sqrt(T * r2 / (1 - r2))
        out["regression"][f"{name}_R2_{r2}"] = {"nc": round(nc, 2), **{k: round(N.cdf(nc - z), 2) for k, z in Z.items()}}
sigma = 0.044
for T, n1 in ((480, 48), (480, 77), (312, 48)):
    n2 = T - n1
    se = sigma * math.sqrt(1/n1 + 1/n2)
    for d in (0.005, 0.01, 0.015):
        nc = d / se
        out["spike"][f"T{T}_n1_{n1}_d_{d}"] = {"se": round(se, 4), "nc": round(nc, 2), **{k: round(N.cdf(nc - z), 2) for k, z in Z.items()}}
for C in (2, 3, 5):
    for Nn in (480, 10000):
        out["te"][f"bias_bits_C{C}_N{Nn}"] = round(C * (C - 1) * (C - 1) / (2 * Nn), 5)
for r2 in (0.001, 0.005, 0.01, 0.02):
    F = -math.log(1 - r2)
    out["te"][f"gauss_te_bits_R2_{r2}"] = round(F / 2 / math.log(2), 5)
S = 0.42 / math.sqrt(12)
for r2 in (0.0025, 0.005, 0.01, 0.02):
    s = math.sqrt((S**2 + r2) / (1 - r2))
    out["timed_sharpe"][f"R2_{r2}"] = {"monthly": round(s, 3), "annual": round(s * math.sqrt(12), 2)}
out["timed_sharpe"]["base_annual"] = 0.42
print(json.dumps(out, indent=1))
