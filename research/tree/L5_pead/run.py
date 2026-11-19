"""Layer 5, branch P (research/tree/PREREG.md "Layer 5"): post-earnings-announcement drift (Bernard and Thomas 1989)
as an event-time book added at whole-fund level beside the MASTER book. One configuration. Plan: STATE.json.

    OMP_NUM_THREADS=3 python3 research/tree/L5_pead/run.py dev     # survivorship contract + development gate (<= 2019)
    OMP_NUM_THREADS=3 python3 research/tree/L5_pead/run.py read    # only after a dev pass; creates READ_L5P.lock first
"""
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "3")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
sys.path.insert(0, TREE)
from holdout2 import load_module  # noqa: E402

L4 = load_module(os.path.join(TREE, "L4_exploit", "run.py"), "l4run_l5p")
K, H = L4.K, L4.H
EV = os.path.join(ROOT, ".cache", "p8", "events.parquet")
DECAY = os.path.join(ROOT, ".cache", "p8", "decay_earnings_events.parquet")
LOCK = os.path.join(HERE, "READ_L5P.lock")
SIDE, HOLD, WIN, MIN_PRIOR, MIN_SIDE, CAP = 0.3, 20, 252, 500, 5, 1.9
DEV_YEARS, TEST_YEARS = range(2013, 2020), range(2020, 2026)


def log(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def state(**kw):
    p = os.path.join(HERE, "STATE.json")
    st = json.load(open(p))
    for k, v in kw.items():
        st[k] = st.get(k, []) + v if k == "done" else v
    st["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(st, open(p, "w"), indent=1)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


# ---------------------------------------------------------------- events
def t0_rule(acc, S):
    after = acc.hour * 60 + acc.minute >= 16 * 60
    i = S.searchsorted(pd.Timestamp(acc.date()), side="right" if after else "left")
    return S[i] if i < len(S) else pd.NaT


def load_events(S, names):
    ev = pd.read_parquet(EV)
    info = {"events_sha256": sha(EV), "rows": int(len(ev))}
    e = ev[(ev.universe == "sp500") & np.isfinite(ev.sue)].copy()
    info["sp500_with_sue"] = int(len(e))
    # t0 rule re-check from the acceptance time, on the panel's sessions
    e["t0_check"] = [t0_rule(a, S) for a in e.accepted_et]
    info["t0_rule_mismatch"] = int((e.t0 != e.t0_check).sum())
    i0 = S.get_indexer(pd.DatetimeIndex(e.t0))
    info["t0_not_a_panel_session"] = int((i0 < 0).sum())
    e["i0"] = i0
    e = e[e.i0 >= 0]
    col = pd.Index(names).get_indexer(e.ticker)
    info["ticker_not_in_panel"] = int((col < 0).sum())
    e["j"] = col
    # causal quintile breakpoints: S&P 500 events with t0 in i0-252 .. i0-1 (all S&P 500 events with sue, panel or not)
    e = e.sort_values("i0").reset_index(drop=True)
    iv, sv = e.i0.to_numpy(), e.sue.to_numpy()
    lo_q, hi_q, n_prior = np.full(len(e), np.nan), np.full(len(e), np.nan), np.zeros(len(e), int)
    for i in np.unique(iv):
        a, b = np.searchsorted(iv, i - WIN), np.searchsorted(iv, i)
        m = iv == i
        n_prior[m] = b - a
        if b - a >= MIN_PRIOR:
            lo_q[m], hi_q[m] = np.quantile(sv[a:b], [0.2, 0.8])
    e["q20"], e["q80"], e["n_prior"] = lo_q, hi_q, n_prior
    e["side"] = np.where(np.isnan(hi_q), 0, np.where(sv >= hi_q, 1, np.where(sv <= lo_q, -1, 0)))
    info["unclassified_lt_500_prior"] = int(np.isnan(hi_q).sum())
    info["first_classified_t0"] = str(e.t0[np.isfinite(hi_q)].min().date())
    # cross-check against decay_earnings_events on the overlap (ticker, t0, sue only; outcome columns never read)
    dk = pd.read_parquet(DECAY, columns=["ticker", "universe", "t0", "sue"])
    dk = dk[dk.universe == "sp500"].merge(ev[["ticker", "t0", "sue"]], on=["ticker", "t0"], how="left", suffixes=("", "_ev"))
    info["decay_overlap"] = {"decay_sp500_rows": int(len(dk)), "matched_share": float(dk.sue_ev.notna().mean()),
                             "sue_differs_share": float(((dk.sue - dk.sue_ev).abs() > 1e-9).mean()),
                             "sha256": sha(DECAY)}
    e = e[e.j >= 0]
    info["used_events"] = int(len(e))
    return e[["ticker", "t0", "i0", "j", "sue", "side", "q20", "q80"]], info


def pead_weights(e, d):
    """(T, N) weight matrix of the PEAD book at each Thursday decision t; NaN-free; zero rows when no book."""
    S, N = d["S"], len(d["names"])
    W = np.zeros((len(S), N))
    nL, nS = np.zeros(len(S), int), np.zeros(len(S), int)
    ev = e[e.side != 0]
    iv, jv, sv = ev.i0.to_numpy(), ev.j.to_numpy(), ev.side.to_numpy()
    order = np.argsort(iv)
    iv, jv, sv = iv[order], jv[order], sv[order]
    for t in np.where(S.weekday == 3)[0]:
        a, b = np.searchsorted(iv, t - HOLD + 1), np.searchsorted(iv, t + 1)    # t0 in [t-19, t]
        el = d["elig"][t]
        L = np.unique(jv[a:b][(sv[a:b] == 1) & el[jv[a:b]]])
        Sh = np.unique(jv[a:b][(sv[a:b] == -1) & el[jv[a:b]]])
        nL[t], nS[t] = len(L), len(Sh)
        if len(L) < MIN_SIDE or len(Sh) < MIN_SIDE:
            continue
        W[t, L] += SIDE / len(L)
        W[t, Sh] -= SIDE / len(Sh)
    return W, nL, nS


# ---------------------------------------------------------------- whole fund: B0 + k * PEAD (k fits gross cap)
def fit_k(s, wm, wp, beta):
    def g(k):
        w = wm + k * wp
        return abs(s - float((w * beta).sum())) + np.abs(w).sum()
    lim = max(CAP, g(0.0))
    if g(1.0) <= lim:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if g(mid) <= lim else (lo, mid)
    return lo


def sim_fund(d, master, W, years, rf, mode):
    """mode 'B0': MASTER book only; 'F1': MASTER + k*PEAD; 'P': PEAD book alone at k = 1 (core still run)."""
    S, spy = d["S"], pd.Series(d["spy"])
    ma = spy.rolling(K.ST.TREND, min_periods=K.ST.TREND).mean().values
    rows, prev, prev_spy, prev_s = [], None, 0.0, None
    for t, R, Rm, days in K.ST.periods(d, years):
        s = K.ST.UP if np.isfinite(ma[t]) and d["spy"][t] > ma[t] else K.ST.DOWN
        beta = np.nan_to_num(d["beta"][t], nan=1.0)
        ok = np.isfinite(master[t]) & d["elig"][t]
        wm = K.deciles(master[t], ok) if mode in ("B0", "F1") else np.zeros(len(beta))
        wp = W[t] if mode in ("F1", "P") else np.zeros(len(beta))
        k = fit_k(s, wm, wp, beta) if mode == "F1" and np.abs(wp).sum() > 0 else (1.0 if mode == "P" else 0.0)
        w = wm + k * wp
        w_spy = -float((w * beta).sum())
        dw = np.abs(w - (prev if prev is not None else 0)).sum() + abs(w_spy - prev_spy)
        book = float((w * np.nan_to_num(R)).sum() + w_spy * Rm) - L4.COST * dw
        mrate = (float(rf.asof(S[t] - pd.Timedelta(days=1))) + K.ST.MARGIN_SPREAD) * days / 360
        sleeve = s * Rm - L4.COST * abs(s - (prev_s if prev_s is not None else s))
        total = sleeve + book - max(s + float(w.sum()) + w_spy - 1, 0) * mrate
        rows.append({"date": S[t], "year": S[t].year, "days": days, "book": book, "total": total, "spy": Rm,
                     "turnover": dw, "book_cost": L4.COST * dw, "core_cost": L4.COST * abs(s - (prev_s if prev_s is not None else s)),
                     "k": k, "gross": abs(s + w_spy) + np.abs(w).sum(), "s": s, "has_pead": bool(np.abs(wp).sum() > 0)})
        prev, prev_spy, prev_s = w, w_spy, s
    return pd.DataFrame(rows).set_index("date")


def book_stats(df):
    b = (df.book * 7 / df.days).to_numpy()
    yrs = df.days.sum() / 365.25
    by = {}
    for y, g in df.groupby("year"):
        x = (g.book * 7 / g.days).to_numpy()
        by[int(y)] = {"pct": round(100 * 52 * float(x.mean()), 2),
                      "sharpe": round(float(x.mean() / x.std(ddof=1) * 52 ** .5), 3) if x.std() > 0 else None}
    m, t, n = L4.nw(b)
    return {"pct_per_year_arith": 100 * 52 * float(b.mean()), "sharpe": float(b.mean() / b.std(ddof=1) * 52 ** .5),
            "vol_pct": 100 * float(b.std(ddof=1) * 52 ** .5), "nw_t": t, "weeks": n,
            "weeks_with_book_share": float(df.has_pead.mean()), "turnover_x_per_year": float(df.turnover.sum() / yrs),
            "cost_pct_per_year": 100 * float(df.book_cost.sum() / yrs), "by_year": by}


def increment(f, b):
    x = L4.wk(f) - L4.wk(b)
    m, t, n = L4.nw(x)
    yr = pd.Series(x, index=f.index).groupby(f.year).sum()
    pos = int((yr > 0).sum())
    return {"mean_pct_per_year": 100 * 52 * m, "nw_t": t, "weeks": n,
            "by_year_pct": {int(k): round(100 * float(v), 3) for k, v in yr.items()},
            "years_positive": pos, "years": int(len(yr)), "x": x}


# ---------------------------------------------------------------- survivorship contract (A1 method)
def survivorship(e_all):
    D = H.load()
    rows = np.concatenate([H.thursdays(D, y) for y in H.VAL_YEARS])
    names = D["names"]
    has = np.array([n in set(e_all.ticker) for n in names])
    # time-varying: an S&P 500 event with sue and t0 in the last 252 sessions up to t
    S = D["S"]
    tv = np.zeros((len(S), len(names)), bool)
    ix = pd.Index(names)
    for tk, g in e_all.groupby("ticker"):
        j = ix.get_indexer([tk])[0]
        if j < 0:
            continue
        for d0 in g.t0:
            a = S.searchsorted(d0)
            tv[a:a + WIN, j] = True

    def ind_ic(ind):
        out, cov = [], []
        for t in rows:
            m = np.isfinite(D["y5"][t]) & D["elig"][t]
            x = (ind if ind.ndim == 1 else ind[t])[m].astype(float)
            if len(x):
                cov.append(x.mean())
            if m.sum() < 50 or x.std() == 0:
                continue
            out.append(pd.Series(x).corr(pd.Series(D["y5"][t][m].astype(float)), method="spearman"))
        a, t_, n = L4.nw(np.array(out))
        return {"ic": a, "nw_t": t_, "weeks": n, "coverage": float(np.mean(cov))}
    return {"by_name_primary": ind_ic(has), "time_varying_disclosed": ind_ic(tv),
            "dev_panel": f"{S.min().date()}..{S.max().date()}, Thursdays 2013-2019"}


# ---------------------------------------------------------------- stages
def common():
    d = K.T.build()
    rf = K.ST.dtb3()
    K.RF, K.GROSS_SIDE = rf, SIDE
    master = np.load(os.path.join(L4.QTC, "sp500_tf_master_h5.npz"))["h5"].astype(np.float64)
    e, info = load_events(d["S"], d["names"])
    W, nL, nS = pead_weights(e, d)
    return d, rf, master, e, info, W, nL, nS


def side_counts(d, nL, nS, years):
    th = np.array([t for t, *_ in K.ST.periods(d, years)])
    return {"mean_long_names": float(nL[th].mean()), "mean_short_names": float(nS[th].mean()),
            "min_long": int(nL[th].min()), "min_short": int(nS[th].min())}


def dev():
    res = {"label": "development, 2013-2019", "run_start": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    d, rf, master, e, info, W, nL, nS = common()
    res["events"] = info
    log("events", info)
    state(done=[f"events loaded: {info['used_events']} S&P 500 events in panel; t0 rule mismatches {info['t0_rule_mismatch']}"],
          running=["survivorship contract"])
    ev_all = pd.read_parquet(EV)
    ev_all = ev_all[(ev_all.universe == "sp500") & np.isfinite(ev_all.sue) & (ev_all.t0 <= "2019-12-31")]
    sv = survivorship(ev_all)
    res["survivorship_contract"] = sv
    res["survivorship_pass"] = bool(abs(sv["by_name_primary"]["nw_t"]) < 2)
    log("survivorship", sv)
    state(done=[f"survivorship: by-name IC {sv['by_name_primary']['ic']:+.4f} (t {sv['by_name_primary']['nw_t']:+.2f}); "
                f"time-varying IC {sv['time_varying_disclosed']['ic']:+.4f} (t {sv['time_varying_disclosed']['nw_t']:+.2f})"],
          running=["development simulation"])
    if not res["survivorship_pass"]:
        json.dump(res, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1, default=float)
        state(running=[], next=["STOPPED: survivorship contract failed"])
        sys.exit("survivorship contract failed")
    # B0 identity on development years
    K.YEARS = DEV_YEARS
    ref = K.run(d, master, "S0", L4.COST, K.sectors(d["names"]), np.zeros(len(d["names"]), int), K.panic_flags(d))
    B0 = sim_fund(d, master, W, DEV_YEARS, rf, "B0")
    same = bool(np.allclose(ref.total.values, B0.total.values, rtol=0, atol=1e-12))
    res["B0_identical_to_construct_run_2013_2019"] = same
    if not same:
        json.dump(res, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1, default=float)
        sys.exit("B0 not reproduced")
    F1 = sim_fund(d, master, W, DEV_YEARS, rf, "F1")
    P = sim_fund(d, master, W, DEV_YEARS, rf, "P")
    inc = increment(F1, B0)
    x = inc.pop("x")
    gate = bool(inc["nw_t"] >= 2.0 and inc["years_positive"] >= math.ceil(2 * inc["years"] / 3))
    res["book_alone_dev"] = book_stats(P)
    res["book_alone_dev"].update(side_counts(d, nL, nS, DEV_YEARS))
    res["whole_fund_dev"] = {"B0": L4.summary(B0), "F1": L4.summary(F1)}
    res["F1_scaling_dev"] = {"mean_k_weeks_with_book": float(F1.k[F1.has_pead].mean()),
                             "mean_k_core_up_1.3": float(F1.k[F1.has_pead & (F1.s > 1)].mean()),
                             "mean_k_core_down_0.7": float(F1.k[F1.has_pead & (F1.s < 1)].mean()),
                             "share_weeks_core_up": float((F1.s > 1).mean()),
                             "share_weeks_k_below_0.05": float((F1.k[F1.has_pead] < 0.05).mean())}
    res["increment_dev"] = inc
    res["increment_corr_with_B0"] = float(np.corrcoef(x, L4.wk(B0))[0, 1])
    res["development_gate"] = {"rule": "NW t >= 2.0 and yearly increment > 0 in >= 2/3 of years", "pass": gate}
    res["run_end"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(res, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1, default=float)
    log("book alone", res["book_alone_dev"])
    log("scaling", res["F1_scaling_dev"])
    log("increment", inc, "gate", gate)
    state(done=[f"development: book alone {res['book_alone_dev']['pct_per_year_arith']:.2f} %/yr, Sharpe {res['book_alone_dev']['sharpe']:.3f}; "
                f"whole-fund increment {inc['mean_pct_per_year']:+.3f} %/yr, NW t {inc['nw_t']:+.2f}, positive {inc['years_positive']}/{inc['years']} years; gate {'PASS' if gate else 'FAIL'}"],
          running=[], next=["read 2020-2025 (READ_L5P.lock first)"] if gate else ["no read: development gate failed; report"])


def read():
    res = json.load(open(os.path.join(HERE, "RESULT.json")))
    if not res.get("development_gate", {}).get("pass"):
        sys.exit("no read: development gate not passed")
    if os.path.exists(LOCK):
        sys.exit("READ_L5P.lock exists: the read is spent")
    open(LOCK, "w").write(datetime.now(timezone.utc).isoformat(timespec="seconds") + " L5 PEAD 2020-2025 read\n")
    state(running=["2020-2025 read (lock created)"])
    d, rf, master, e, info, W, nL, nS = common()
    B0 = sim_fund(d, master, W, TEST_YEARS, rf, "B0")
    F1 = sim_fund(d, master, W, TEST_YEARS, rf, "F1")
    P = sim_fund(d, master, W, TEST_YEARS, rf, "P")
    rec = json.load(open(os.path.join(TREE, "OOS_RETURNS.json")))["MASTER|gross 0.6|5bp"]
    s0 = L4.summary(B0)
    t = {"label": "2020-2025 walk-forward test (one read)",
         "B0_reproduction": {"pct_per_year": s0["pct_per_year"], "sharpe": s0["sharpe"],
                             "recorded_pct_per_year": rec["pct_per_year"], "recorded_sharpe": rec["sharpe"]},
         "whole_fund": {"B0": s0, "F1": L4.summary(F1)}, "book_alone": book_stats(P)}
    inc = increment(F1, B0)
    inc.pop("x")
    t["increment"] = inc
    a, b = L4.wk(F1), L4.wk(B0)
    t["lw2008_hac"] = L4.lw_hac_test(a, b)
    t["lw2008_block_bootstrap"] = L4.lw_boot(a, b, np.random.default_rng(L4.SEED))
    n = {"L4 N_used (incl. L4 exploit's 7)": 162, "L4 explore X1, X2": 2, "L4 arch variants (upper count)": 4,
         "Layer 5: I 2, B 2, P 1, E 1": 6}
    trials, sharpes = L4.count_trials()
    sharpes += [s0["sharpe"], t["whole_fund"]["F1"]["sharpe"]]
    var_sr_w = float(np.var(sharpes, ddof=1)) / 52
    t["N_trials"] = {"sources": n, "N": sum(n.values())}
    t["dsr"] = L4.dsr(a, sum(n.values()), var_sr_w)
    t["holm"] = "own one-sided HAC p reported; Holm across Layer 5 read candidates applied by the coordinator"
    res["test_2020_2025"] = t
    json.dump(res, open(os.path.join(HERE, "RESULT.json"), "w"), indent=1, default=float)
    state(done=[f"read: Sharpe diff {t['lw2008_hac']['sharpe_diff_ann']:+.3f}, p {t['lw2008_hac']['p_one_sided']:.3f}, DSR {t['dsr']['dsr']:.3f}"],
          running=[], next=["coordinator review"])


if __name__ == "__main__":
    {"dev": dev, "read": read}[sys.argv[1]]()
