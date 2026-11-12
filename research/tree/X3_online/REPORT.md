# X3: does updating inside the validation year help?

Setup. Target rebuilt from `D["e"]` (sum over d+2..d+6, demeaned over eligible names): correlation with `y5` on training rows 0.9999. Online =
coefficients recomputed at every prediction Thursday t from all sessions d <= t-6 (closed windows only); yearly = the identical model with d <=
train_end. Rank-standardised target, all sessions. A scramble test (all data after row t replaced by noise) leaves every prediction at t unchanged. 32
rows logged in RESULTS.jsonl (14 online/yearly pairs + 4 staleness diagnostics). "Paired" = mean weekly IC difference online minus yearly, with its
own standard error (353 weeks); it is far tighter than the 0.01 SE of a level.

| # | scheme | features | yearly IC (t) | online IC (t) | paired diff (se) |
|---|---|---|---|---|---|
| 1 | pooled ridge, expanding | 5 | 0.0139 (1.39) | 0.0122 (1.22) | -0.0017 (0.0020) |
| 2 | ridge, exp. weights, half-life 26 w | 5 | 0.0088 (0.89) | 0.0000 (0.00) | -0.0088 (0.0089) |
| 2 | ridge, exp. weights, half-life 104 w | 5 | 0.0136 (1.39) | 0.0086 (0.86) | -0.0050 (0.0042) |
| 3 | Fama-MacBeth, last 26 w | 5 | 0.0014 (0.14) | 0.0004 (0.04) | -0.0010 (0.0128) |
| 3 | Fama-MacBeth, last 52 w | 5 | -0.0075 (-0.82) | -0.0058 (-0.57) | +0.0016 (0.0104) |
| 3 | Fama-MacBeth, last 104 w | 5 | 0.0093 (0.92) | 0.0012 (0.12) | -0.0081 (0.0071) |
| 3 | Fama-MacBeth, expanding | 5 | 0.0111 (1.09) | 0.0098 (0.96) | -0.0013 (0.0015) |
| 4 | exp.-weights mixing of signed single-characteristic experts | 5 | 0.0155 (1.48) | 0.0124 (1.18) | -0.0031 (0.0022) |
| 5 | characteristic timing, trailing 52 w IC | 5 | 0.0012 (0.12) | -0.0037 (-0.35) | -0.0048 (0.0091) |
| 6 | Fama-MacBeth, expanding | 32 | **0.0218 (2.22)** | 0.0193 (1.93) | -0.0024 (0.0017) |
| 6 | pooled ridge, expanding | 32 | 0.0199 (2.00) | 0.0175 (1.72) | -0.0023 (0.0017) |
| 7 | Fama-MacBeth, exp. weights, half-life 260 w | 32 | 0.0216 (2.10) | 0.0184 (1.74) | -0.0032 (0.0022) |
| 7 | Fama-MacBeth, last 104 w | 32 | 0.0190 (1.85) | 0.0099 (0.92) | -0.0090 (0.0051) |
| 8 | exp.-weights mixing of signed single-column experts | 32 | 0.0227 (1.96) | 0.0192 (1.62) | -0.0035 (0.0027) |

Staleness curve (diagnostic, row 6 online with a constant extra lag; paired against lag 0): 13 w IC 0.0207 (+0.0013, se 0.0016); 26 w 0.0216 (+0.0022,
se 0.0018); 52 w 0.0231, t 2.47, 7 of 7 years positive (+0.0037, se 0.0026); 104 w 0.0214 (+0.0021, se 0.0051). Post-hoc; not proposed as a model.

**Best configuration (model.py):** 32 columns, expanding Fama-MacBeth, fitted once a year: IC 0.0218, t 2.22, positive in 6 of 7 years, decile spread
net of costs -0.1 % per year. It is branch C's model on the rebuilt rank target, i.e. nothing new. Best online scheme: the same model updated weekly,
IC 0.0193 (t 1.93).

**Answer: no.** Updating inside the year did not help in any of 14 pairs. 13 of 14 paired differences are negative (-0.001 to -0.009), the one
positive is +0.002 with se 0.010; none is beyond 1.8 paired standard errors, and all are below the 0.01 standard error of an IC level. The staleness
curve agrees: a model deliberately a year out of date is no worse than a fresh one. The pairs are highly correlated (same weeks, nested models), so 13
of 14 is not 13 independent signs; the honest reading is "no benefit, possibly a small cost of about 0.002 (roughly 1.4 se)", not "freshness hurts".
Short memories (26-104 weeks) are worse than expanding windows whether or not they update, which says characteristic payoffs on this panel are not
persistent enough at 6-24 month horizons to time. The regime branch's negative result therefore stands after a fair test: staleness was not what held
it back.  Limits: linear models only; 2013-2019 only.
