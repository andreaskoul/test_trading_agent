"""Desk 6 · PM + risk (PROTOCOL_fund.md, Amendment 2). Deterministic, no LLM. -> book.json

The news desk supplies the views; this desk only sizes and hedges them.

* fund / analyst: every covered S&P name with a non-zero score (red-team adjusted /
  pre red team), at most 10 per side ranked by |score| x confidence. Weight per name
  = score x confidence / 20 of NAV, so a 2-point, full-confidence view is 10% of NAV
  (the name cap) and the stock book's gross is at most 2. No view, no position: no
  ridge fill, and a week with no views is flat.
* quant: the frozen ridge's top/bottom 10 over the whole S&P 500 at 10% of NAV each:
  a benchmark for the news desk, not an input to it.
* core20 (Protocol 5): top/bottom 4 non-zero analyst scores among the dashboard's 20,
  equal weight 25%.  random: 10/10 drawn from the covered set at 10% each.

Risk, the same for fund, analyst, quant and random, in this order:
1. sector net <= 30% of NAV (the heavy side of the sector shrinks pro rata);
2. stock dollar net <= 20% of the stock gross (the heavy leg shrinks pro rata);
3. SPY takes the position that brings the book's 60-day beta to zero.
"""

import numpy as np
import pandas as pd

import glob
import json
import os

from common import MODE, STATE, asof_from_env, deadline_ok, load, save, week_dir

asof = asof_from_env()
S = pd.DataFrame(load(asof, "screen.json")["rows"]).set_index("ticker")
idea = load(asof, "ideation.json")
memos = load(asof, "analysts.json")["memos"]
final = load(asof, "redteam.json")["final_score"]
N, CORE_N, UNIT, SECTOR_CAP, DOLLAR_CAP = 10, 4, 1 / 20, 0.30, 0.10      # dollar cap 20% -> 10% (Amendment 4)
DEGRADED = 0.25                                  # more failed memos than this: hold last week's books
cov = [t for t in idea["coverage"] if t in S.index]            # book names need a price row
ok = lambda t: memos.get(t, {}).get("status") == "ok"
analyst = {t: (memos[t]["memo"]["score"] if ok(t) else 0) for t in cov}
conf = {t: (float(memos[t]["memo"]["confidence"]) if ok(t) else 0.0) for t in cov}
beta = (S["beta_hedge"] if "beta_hedge" in S else S["beta60"]).fillna(1.0)      # Amendment 4: Welch, shrunk
sector = S["GICS Sector"].fillna("Unknown")


def conviction_book(score, cf=None):
    """Non-zero views only, sized by score x confidence, at most N per side."""
    cf = conf if cf is None else cf
    w = pd.Series({t: score.get(t, 0) * cf.get(t, 0.0) * UNIT for t in cov}, dtype=float)
    w = w[w != 0]
    L = w[w > 0].sort_values(ascending=False).head(N)
    Sh = w[w < 0].sort_values().head(N)
    return pd.concat([L, Sh])


def risk(w):
    """Sector cap, dollar-net cap, then an SPY hedge to zero beta."""
    w, log = w.copy(), []
    if w.empty:
        return {}, {"n_long": 0, "n_short": 0, "stock_gross": 0.0, "stock_net": 0.0, "spy": 0.0,
                    "net_beta": 0.0, "sector_net": {}, "log": ["no views: flat"]}
    for sec, net in w.groupby(sector.reindex(w.index)).sum().items():
        if abs(net) > SECTOR_CAP + 1e-9:
            side = w.index[(sector.reindex(w.index) == sec) & (np.sign(w) == np.sign(net))]
            other = net - w[side].sum()
            k = (np.sign(net) * SECTOR_CAP - other) / w[side].sum()
            w[side] *= k
            log.append(f"sector {sec}: net {net:+.2f} -> {np.sign(net) * SECTOR_CAP:+.2f}")
    long_, short_ = w[w > 0].sum(), -w[w < 0].sum()
    gross, net = long_ + short_, long_ - short_
    if gross > 0 and abs(net) > DOLLAR_CAP * gross + 1e-9:
        # shrink the heavy leg until |L - S| = cap x (L + S)
        if net > 0:
            k = short_ * (1 + DOLLAR_CAP) / (1 - DOLLAR_CAP) / long_ if short_ > 0 else 0.0
            w[w > 0] *= k
        else:
            k = long_ * (1 + DOLLAR_CAP) / (1 - DOLLAR_CAP) / short_ if long_ > 0 else 0.0
            w[w < 0] *= k
        log.append(f"dollar net {net:+.2f} of gross {gross:.2f}: heavy leg x{k:.2f}")
        w = w[w != 0]
    if w.empty:
        return {}, {"n_long": 0, "n_short": 0, "stock_gross": 0.0, "stock_net": 0.0, "spy": 0.0,
                    "net_beta": 0.0, "sector_net": {}, "log": log + ["one-sided views and no room under the dollar cap: flat"]}
    stock_beta = float((w * beta.reindex(w.index)).sum())
    spy = -stock_beta
    rep = {"n_long": int((w > 0).sum()), "n_short": int((w < 0).sum()), "stock_gross": float(w.abs().sum()),
           "stock_net": float(w.sum()), "stock_beta": stock_beta, "spy": spy, "net_beta": 0.0,
           "gross_incl_spy": float(w.abs().sum() + abs(spy)),
           "max_name": float(w.abs().max()),
           "sector_net": w.groupby(sector.reindex(w.index)).sum().round(3).to_dict(), "log": log}
    out = {t: round(float(v), 5) for t, v in w.items()}
    if abs(spy) > 1e-6:
        out["SPY"] = round(spy, 5)
    return out, rep


if os.environ.get("FUND_SHADOW") == "1":
    # Shadow analyst books C2 / C3 (Amendment 4): the champion's sizing and risk rules on the shadow
    # scores. Written to shadow_book.json after the champion's book is committed; never traded.
    sh = load(asof, "shadow.json")
    out_b, out_r = {}, {}
    for k in ("c2_selfconsistency", "c3_textonly"):
        sc = {t: v["score"] for t, v in sh[k].items() if v}
        cf = {t: v["confidence"] for t, v in sh[k].items() if v}
        out_b[k], out_r[k] = risk(conviction_book(sc, cf))
        print(k, out_b[k], out_r[k]["log"])
    save(asof, "shadow_book.json", {"asof": str(asof.date()), "books": out_b, "risk": out_r})
    raise SystemExit(0)

if not deadline_ok(asof):
    save(asof, "book.json", {"asof": str(asof.date()), "status": "missed_deadline", "books": {}})
    raise SystemExit("missed the Thursday 19:00 UTC deadline: week logged flat")
fund_score = {t: final.get(t, 0) for t in cov}
books, reports = {}, {}
prev_dir = max([d for d in glob.glob(os.path.join(STATE, MODE, "20*")) if os.path.basename(d) < str(asof.date())
                and os.path.exists(os.path.join(d, "book.json"))
                and json.load(open(os.path.join(d, "book.json"))).get("status") in ("ok", "degraded_hold")], default=None)
prev = json.load(open(os.path.join(prev_dir, "book.json"))) if prev_dir else {"books": {}, "meta": {}}
failed = sum(not ok(t) for t in cov) / max(len(cov), 1)
status = "ok"
if failed > DEGRADED:
    # Degraded run (Amendment 4): a partial set of memos is not a book. Hold last week's fund and
    # analyst books (flat if there is none) and log it; the shadow books are computed as usual.
    status = "degraded_hold"
    for k in ("fund", "analyst"):
        books[k] = prev["books"].get(k, {})
        reports[k] = {"log": [f"degraded run: {failed:.0%} of memos failed; holding {os.path.basename(prev_dir) if prev_dir else 'nothing (flat)'}"]}
else:
    books["fund"], reports["fund"] = risk(conviction_book(fund_score))
    books["analyst"], reports["analyst"] = risk(conviction_book(analyst))
r = S["ridge_bp"].sort_values()
books["quant"], reports["quant"] = risk(pd.concat([pd.Series(0.1, index=r.index[-N:]), pd.Series(-0.1, index=r.index[:N])]))
core = [t for t in idea["core"] if t in S.index]
key = lambda t: analyst.get(t, 0) * max(conf.get(t, 0.0), 1e-3)
cL = sorted([t for t in core if analyst.get(t, 0) > 0], key=key, reverse=True)[:CORE_N]
cS = sorted([t for t in core if analyst.get(t, 0) < 0], key=key)[:CORE_N]
books["core20"] = {**{t: 1 / CORE_N for t in cL}, **{t: -1 / CORE_N for t in cS}}
rng = np.random.default_rng(int(str(asof.date()).replace("-", "")))
perm = list(rng.permutation(sorted(cov)))
books["random"], reports["random"] = risk(pd.concat([pd.Series(0.1, index=perm[:N]), pd.Series(-0.1, index=perm[N:2 * N])]))

# ---- shadow challenger books (Amendment 4), never traded; same risk rules as the champion
# C4: Grinold-style sizing, score x confidence / volatility, scaled to the champion's stock gross,
# with a band: a name held last week whose score is now 0 or uncovered keeps its weight one more week.
vol = (S["vol60_ann_pct"] / 100).clip(lower=0.10).fillna(0.30)
raw = pd.Series({t: fund_score.get(t, 0) * conf.get(t, 0.0) / vol[t] for t in cov}, dtype=float)
raw = raw[raw != 0]
raw = pd.concat([raw[raw > 0].nlargest(N), raw[raw < 0].nsmallest(N)])
fund_gross = sum(abs(v) for k, v in books.get("fund", {}).items() if k != "SPY")
c4 = (raw / raw.abs().sum() * fund_gross).clip(-0.10, 0.10) if len(raw) and fund_gross else raw * 0
age = {}
for t, w0 in prev["books"].get("c4_volscaled", {}).items():
    if t != "SPY" and t not in c4.index and fund_score.get(t, 0) == 0 and prev.get("meta", {}).get("c4_age", {}).get(t, 0) < 1:
        c4[t] = w0; age[t] = prev.get("meta", {}).get("c4_age", {}).get(t, 0) + 1
books["c4_volscaled"], reports["c4_volscaled"] = risk(c4.astype(float))
# C5: news-conditioned reversal. Covered names with a zero score and no event active in the last
# 7 days get a short-term reversal position (rank of last week's return, at most 3% of NAV each);
# the champion's news views are kept everywhere else.
def active_event(t):
    p_ = os.path.join(week_dir(asof), "research", f"{t}.json")
    if not os.path.exists(p_):
        return False
    lo_ = (asof - pd.Timedelta(days=6)).normalize()
    return any(pd.Timestamp(e["end"]) >= lo_ for e in json.load(open(p_)).get("events", []))
quiet = [t for t in cov if fund_score.get(t, 0) == 0 and not active_event(t)]
c5 = conviction_book(fund_score)
if len(quiet) >= 4:
    rk = S.loc[quiet, "ret_1w_pct"].rank()
    c5 = pd.concat([c5, -(rk - rk.mean()) / (len(quiet) / 2) * 0.03])
books["c5_reversal"], reports["c5_reversal"] = risk(c5.astype(float))
save(asof, "book.json", {"asof": str(asof.date()), "status": status, "books": books, "risk": reports,
                         "memo_failure_share": failed, "meta": {"c4_age": age, "quiet_names": quiet},
                         "scores": {"fund": fund_score, "analyst": analyst, "confidence": conf}})
for k, v in books.items():
    Lk = [f"{t} {w:.3f}" for t, w in v.items() if w > 0 and t != "SPY"]
    Sk = [f"{t} {w:.3f}" for t, w in v.items() if w < 0 and t != "SPY"]
    rp = reports.get(k)
    print(f"{k:8s} L {Lk}\n{'':8s} S {Sk}" + (
        f"\n{'':8s} stock gross {rp['stock_gross']:.2f} net {rp['stock_net']:+.2f} SPY {rp['spy']:+.2f} {rp['log']}" if rp else ""))
