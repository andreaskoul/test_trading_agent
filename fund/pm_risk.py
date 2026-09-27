"""Desk 6 · PM + risk (PROTOCOL_fund.md). Deterministic, no LLM. -> book.json

Books: fund (red-team adjusted), analyst (pre red team), quant (ridge over the
whole S&P 500), core20 (Protocol 5), random. fund/analyst/quant go through the
same risk rules: 10 long / 10 short equal weight, sector net <= 20% of gross,
single name <= 10% of gross, short leg scaled for 60-day beta neutrality.
"""

import numpy as np
import pandas as pd

from common import asof_from_env, deadline_ok, load, save

asof = asof_from_env()
S = pd.DataFrame(load(asof, "screen.json")["rows"]).set_index("ticker")
idea = load(asof, "ideation.json")
memos = load(asof, "analysts.json")["memos"]
final = load(asof, "redteam.json")["final_score"]
N, CORE_N, SECTOR_CAP, NAME_CAP = 10, 4, 0.20, 0.10
cov = [t for t in idea["coverage"] if t in S.index]            # book names need a quantitative row
analyst = {t: (memos[t]["memo"]["score"] if memos.get(t, {}).get("status") == "ok" else 0) for t in cov}
conf = {t: (memos[t]["memo"]["confidence"] if memos.get(t, {}).get("status") == "ok" else 0.0) for t in cov}
ridge = S["ridge_bp"]


def pick(names, score):
    """Longs: positive score first by (score, confidence, ridge), then ridge fill; shorts mirrored."""
    key = lambda t: (score.get(t, 0), conf.get(t, 0.0) * np.sign(score.get(t, 0)), ridge[t])
    pos = sorted([t for t in names if score.get(t, 0) > 0], key=key, reverse=True)
    neg = sorted([t for t in names if score.get(t, 0) < 0], key=key)
    L = pos[:N] + [t for t in sorted(names, key=lambda t: -ridge[t]) if t not in pos and t not in neg][:max(0, N - len(pos))]
    Sh = neg[:N] + [t for t in sorted(names, key=lambda t: ridge[t]) if t not in neg and t not in L][:max(0, N - len(neg))]
    return L, Sh, pos + [t for t in sorted(names, key=lambda t: -ridge[t]) if t not in pos], \
        neg + [t for t in sorted(names, key=lambda t: ridge[t]) if t not in neg]


def risk(L, Sh, reserve_L, reserve_S):
    """Sector cap by substitution, then beta-neutral scaling of the short leg."""
    L, Sh, log = list(L), list(Sh), []
    for _ in range(40):
        w = pd.concat([pd.Series(1 / len(L), index=L), pd.Series(-1 / len(Sh), index=Sh)])
        net = w.groupby(S.loc[w.index, "GICS Sector"]).sum()
        bad = net[net.abs() > SECTOR_CAP * 2]                    # gross = 2
        if bad.empty:
            break
        sec, heavy = bad.index[0], (L if bad.iloc[0] > 0 else Sh)
        reserve = reserve_L if heavy is L else reserve_S
        out = [t for t in heavy if S.loc[t, "GICS Sector"] == sec][-1]                  # lowest-ranked in that sector
        sub = next((t for t in reserve if t not in L and t not in Sh and S.loc[t, "GICS Sector"] != sec), None)
        if sub is None:
            log.append(f"sector {sec} over cap, no substitute"); break
        heavy[heavy.index(out)] = sub
        log.append(f"sector {sec}: {out} -> {sub}")
    # Beta neutrality with gross fixed at 2: long leg a, short leg c, a*bL = c*bS, a + c = 2.
    # (The first version only scaled the short leg and clipped it at 0.5, which left a
    # low-beta-long / high-beta-short book at net beta -0.36 in the 2026-09-23 dry run.)
    b = S["beta60"].fillna(1.0).clip(lower=0.1)
    bL, bS = b[L].mean(), b[Sh].mean()
    a = 2 * bS / (bL + bS); c = 2 - a
    k = c / a
    w = pd.concat([pd.Series(a / len(L), index=L), pd.Series(-c / len(Sh), index=Sh)])
    w = w.clip(-NAME_CAP * w.abs().sum(), NAME_CAP * w.abs().sum())
    rep = {"net_beta": float((w * b[w.index]).sum()), "gross": float(w.abs().sum()), "net": float(w.sum()),
           "short_scale": k, "sector_net": w.groupby(S.loc[w.index, "GICS Sector"]).sum().round(3).to_dict(), "log": log}
    return {t: round(float(v), 5) for t, v in w.items()}, rep


books, reports = {}, {}
if not deadline_ok(asof):
    save(asof, "book.json", {"asof": str(asof.date()), "status": "missed_deadline", "books": {}})
    raise SystemExit("missed the Thursday 19:00 UTC deadline: week logged flat")
fund_score = {t: final.get(t, 0) for t in cov}
for name, sc, universe in (("fund", fund_score, cov), ("analyst", analyst, cov),
                           ("quant", {}, list(S.index))):
    L, Sh, rL, rS = pick(universe, sc)
    books[name], reports[name] = risk(L, Sh, rL, rS)
core = [t for t in idea["core"] if t in S.index]
L, Sh, _, _ = pick(core, analyst)
L, Sh = L[:CORE_N], Sh[:CORE_N]
books["core20"] = {**{t: 1 / CORE_N for t in L}, **{t: -1 / CORE_N for t in Sh}}
rng = np.random.default_rng(int(str(asof.date()).replace("-", "")))
perm = list(rng.permutation(sorted(cov)))
books["random"] = {**{t: 1 / N for t in perm[:N]}, **{t: -1 / N for t in perm[N:2 * N]}}
save(asof, "book.json", {"asof": str(asof.date()), "status": "ok", "books": books, "risk": reports,
                         "scores": {"fund": fund_score, "analyst": analyst, "confidence": conf}})
for k, v in books.items():
    Lk = [t for t, w in v.items() if w > 0]; Sk = [t for t, w in v.items() if w < 0]
    print(f"{k:8s} L {Lk}\n{'':8s} S {Sk}" + (f"\n{'':8s} net beta {reports[k]['net_beta']:+.2f} short scale {reports[k]['short_scale']:.2f} {reports[k]['log']}" if k in reports else ""))
