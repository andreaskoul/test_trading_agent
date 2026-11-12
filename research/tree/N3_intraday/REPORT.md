# Branch N3: intraday return structure on top of MASTER

*Saved by the coordinating session from the agent's hand-back (its file write was refused).*

Validation 2017-2019 only (151 Thursdays, about 350 names; current constituents: survivorship). MASTER IC on these
weeks 0.0165. Features selected on 2016 only (rules in `screen.py`): `id21` (21-session intraday return, sign -) and
`on21 - id21` (sign +). 8 configurations, 20 logged rows.

| config | IC | increment | t | by year 17/18/19 | corr with MASTER | decile net %/yr |
|---|---:|---:|---:|---|---:|---:|
| 0.8 MASTER - 0.2 id21 | .0196 | +.0030 | 1.53 | -.000/+.001/+.008 | 0.98 | +1.8 |
| 0.8 / 0.1 / 0.1 | .0191 | +.0025 | 1.41 | -.000/+.001/+.007 | 0.98 | +1.0 |
| pooled ridge, MASTER + 4 features | .0192 | +.0026 | 0.14 | +.003/-.017/+.023 | -0.14 | +1.5 |
| Fama-MacBeth, MASTER + 4 | .0201 | +.0036 | 0.18 | +.007/-.020/+.025 | -0.15 | +0.7 |
| MASTER weight fixed, features on residual | .0283 | +.0118 | 0.92 | +.003/-.004/+.037 | 0.56 | +3.4 |
| control: 0.8 MASTER - 0.2 total 21-session return | .0202 | +.0037 | 1.72 | +.001/+.002/+.008 | 0.98 | +2.5 |

Double ML (MASTER and Z partialled out, cross-fitted trees): id21 theta -0.020 (t -1.22), on21-id21 +0.011 (t 1.02),
both carried by 2019.

**Verdict: no finalist.** The increment is ordinary 1-month reversal (Z's reversal has Spearman -0.80 with id21); plain
reversal adds more than the intraday split. Lead for the coordinator: MASTER + 1-month reversal (t 1.72 on 2017-19),
to be judged on 2013-2019 under phase-1 rules.
