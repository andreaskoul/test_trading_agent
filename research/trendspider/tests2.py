"""Pre-registration 2 (research/trendspider/PREREG_2.md): the short mirror and long/short book (B), robustness of the
published long rules (C), and intraday momentum long and short (D).

    python3 research/trendspider/tests2.py B   # once
    python3 research/trendspider/tests2.py C
    python3 research/trendspider/tests2.py D   # once

Results go to research/trendspider/results/{B,C,D}.json. Sharpe ratios use daily returns, rf = 0, sqrt(252).
"""
import json, math, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import replica as R

OUT = R.OUT
W0, W1 = "2016-03-01", "2026-11-03"
SEED = 20261104


# ---------- statistics ----------
def sharpe(r):
    r = np.asarray(r, float)
    return float(r.mean() / r.std() * 252 ** .5) if r.std() > 0 else 0.0


def summary(r):
    r = pd.Series(r).dropna()
    w = (1 + r).cumprod()
    yrs = len(r) / 252
    return dict(cagr=float(w.iloc[-1] ** (1 / yrs) - 1), vol=float(r.std() * 252 ** .5), sharpe=sharpe(r),
                maxdd=float((w / w.cummax() - 1).min()), days=int(len(r)))


def nw_t(r, lags=5):
    r = np.asarray(r, float); n = len(r); e = r - r.mean()
    v = e @ e / n
    for k in range(1, lags + 1):
        v += 2 * (1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / n
    return float(r.mean() / math.sqrt(v / n))


def stationary_idx(n, block, rng):
    idx = np.empty(n, int); i = rng.integers(n)
    for t in range(n):
        idx[t] = i
        i = rng.integers(n) if rng.random() < 1 / block else (i + 1) % n
    return idx


def boot(fn, X, draws=5000, block=10, seed=SEED):
    rng = np.random.default_rng(seed); n = len(X)
    return np.array([fn(X[stationary_idx(n, block, rng)]) for _ in range(draws)])


# ---------- B: mirror and long/short ----------
def mirror_signal(df, p):
    x = R.indicators(df, p)
    ll = pd.Series(df.low.to_numpy(float)).rolling(p["brk_n"]).min().shift(1).to_numpy()
    filt = (x["sma_f"] < x["sma_s"]) & (x["adx"] > p["adx_min"])
    a = (x["c"] < ll) & (x["v"] >= (1 + p["volA"]) * x["vs"])
    diff = x["c"] - x["vwap"]                       # VWAP crosses below the close  <=>  close - VWAP turns positive
    cross = (diff > 0) & (np.r_[np.nan, diff[:-1]] <= 0) & x["same_day"]
    b = cross & (x["rsi"] < 100 - p["rsi_min"]) & (x["v"] >= (1 + p["volB"]) * x["vs"])
    return np.nan_to_num(filt & (a | b)).astype(bool)


def simulate_ls(df, sig_l, sig_s, p, cost, borrow=0.03):
    """One position at a time; entries only when flat; next-open fills; exits judged on closes."""
    o, c = df.open.to_numpy(float), df.close.to_numpy(float)
    day = df["day"].to_numpy()
    n = len(c); eq = np.empty(n)
    E, d, e, ext, nbar, pending = 1.0, 0, 0.0, 0.0, 0, None
    trades = []
    for i in range(n):
        if i and day[i] != day[i - 1] and d == -1:
            E -= E0 * borrow / 252                                 # borrow accrues per session held short
        if pending in ("long", "short"):
            d = 1 if pending == "long" else -1
            e = o[i] * (1 + cost * d); E0 = E; ext = c[i]; nbar = 0; ent = i
        elif pending == "exit":
            px = o[i] * (1 - cost * d)
            E = E + E0 * d * (px / e - 1); trades.append((ent, i, d, d * (px / e - 1))); d = 0
        pending = None
        if d:
            nbar += 1
            ext = max(ext, c[i]) if d == 1 else min(ext, c[i])
            pnl = d * (c[i] / e - 1)
            if (pnl < -p["stop"] or pnl > p["target"] or d * (c[i] / ext - 1) < -p["trail"]
                    or (nbar >= p["t1"] and pnl < 0) or (nbar >= p["t2"] and pnl < p["t2_pnl"])):
                pending = "exit"
            eq[i] = E + E0 * d * (c[i] / e - 1)
        else:
            if sig_l is not None and sig_l[i]:
                pending = "long"
            elif sig_s is not None and sig_s[i]:
                pending = "short"
            eq[i] = E
    daily = pd.Series(eq).groupby(day).last(); daily.index = pd.to_datetime(daily.index)
    return daily.pct_change().fillna(0.0), trades


def spy_daily():
    df = R.load("SPY")
    px = df.groupby("day").close.last(); px.index = pd.to_datetime(px.index)
    return px.pct_change().fillna(0.0)


def test_B():
    p, res = R.P0, {}
    spy = spy_daily().loc[W0:W1]
    for sym in ("SSO", "SPY"):
        df = R.load(sym)
        sl, ss = R.signal(df, p, "plus", "vwap_over"), mirror_signal(df, p)
        books = {"long_only": simulate_ls(df, sl, None, p, 0.0002),
                 "short_only": simulate_ls(df, None, ss, p, 0.0002),
                 "long_short": simulate_ls(df, sl, ss, p, 0.0002)}
        out = {}
        for k, (r, tr) in books.items():
            r = r.loc[W0:W1]
            t = [x for x in tr if pd.Timestamp(W0) <= pd.Timestamp(df.ts.iloc[x[0]].date())]
            out[k] = dict(**summary(r), trades=len(t), win=float(np.mean([x[3] > 0 for x in t])) if t else 0.0,
                          avg_trade=float(np.mean([x[3] for x in t])) if t else 0.0,
                          by_year={str(y): float((1 + g).prod() - 1) for y, g in r.groupby(r.index.year)})
        out["spy_buyhold"] = summary(spy)
        if sym == "SSO":
            rs = books["short_only"][0].loc[W0:W1].to_numpy()
            bm = boot(lambda x: x.mean(), rs)
            out["B1_p_mean_le_0"] = float((bm <= 0).mean())
            out["B1_pass"] = bool(rs.mean() > 0 and out["B1_p_mean_le_0"] < 0.05)
            j = pd.concat([books["long_short"][0].loc[W0:W1], spy], axis=1).dropna().to_numpy()
            bd = boot(lambda x: sharpe(x[:, 0]) - sharpe(x[:, 1]), j)
            out["B2_sharpe_minus_spy"] = sharpe(j[:, 0]) - sharpe(j[:, 1])
            out["B2_p_diff_le_0"] = float((bd <= 0).mean())
            out["B2_pass"] = bool(out["long_short"]["sharpe"] > out["long_only"]["sharpe"]
                                  and out["long_short"]["sharpe"] > out["spy_buyhold"]["sharpe"]
                                  and out["B2_p_diff_le_0"] < 0.10)
        res[sym] = out
    json.dump(res, open(f"{OUT}/B.json", "w"), indent=1)
    print(json.dumps({s: {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "by_year"})
                          for k, v in o.items()} for s, o in res.items()}, indent=1))


# ---------- C: robustness of the long rules ----------
def resample(df, minutes):
    m = (df.ts.dt.hour * 60 + df.ts.dt.minute - 570) // minutes
    g = df.groupby([df["day"], m])
    out = pd.DataFrame({"ts": g.ts.first(), "open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                        "close": g.close.last(), "volume": g.volume.sum()}).reset_index(drop=True)
    out["day"] = out.ts.dt.date
    return out


def test_C():
    p, res = R.P0, {}
    df = R.load("SSO")
    sig = R.signal(df, p, "plus", "vwap_over")
    spy = spy_daily().loc[W0:W1]
    res["costs"] = {}
    for bp in (0, 1, 2, 5, 10):
        d, _, _ = R.simulate(df, sig, p, bp / 1e4)
        res["costs"][f"{bp}bp"] = summary(d.pct_change().fillna(0).loc[W0:W1])
    res["bars"] = {}
    for mins in (30, 60):
        d2 = resample(df, mins)
        d, tr, _ = R.simulate(d2, R.signal(d2, p, "plus", "vwap_over"), p, 0.0002)
        res["bars"][f"{mins}m"] = dict(**summary(d.pct_change().fillna(0).loc[W0:W1]), trades=len(tr))
    res["spy_buyhold"] = summary(spy)
    # walk-forward selection over the read-1 grid
    rng = np.random.default_rng(SEED)
    cfgs = [p] + [R.perturb(rng) for _ in range(300)]
    rets = []
    for q in cfgs:
        d, _, _ = R.simulate(df, R.signal(df, q, "plus", "vwap_over"), q, 0.0002)
        rets.append(d.pct_change().fillna(0))
    M = pd.concat(rets, axis=1)
    segs, picks = [], []
    for start in pd.date_range("2018-03-01", "2026-09-01", freq="6MS"):
        tr = M.loc[start - pd.DateOffset(years=2): start - pd.Timedelta(days=1)]
        best = int((tr.mean() / tr.std()).values.argmax())
        segs.append(M.loc[start: start + pd.DateOffset(months=6) - pd.Timedelta(days=1)].iloc[:, best]); picks.append(best)
    wf = pd.concat(segs).loc[:W1]
    res["walk_forward"] = dict(**summary(wf), picks_published=int(sum(1 for b in picks if b == 0)), segments=len(picks),
                               spy_same_span=summary(spy.loc[wf.index[0]:]))
    j = pd.concat([M.iloc[:, 0].loc[W0:W1], spy], axis=1).dropna().to_numpy()
    bd = boot(lambda x: sharpe(x[:, 0]) - sharpe(x[:, 1]), j)
    res["replica_minus_spy_sharpe"] = dict(point=sharpe(j[:, 0]) - sharpe(j[:, 1]),
                                           ci90=[float(np.percentile(bd, 5)), float(np.percentile(bd, 95))])
    json.dump(res, open(f"{OUT}/C.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


# ---------- D: intraday momentum (Zarattini, Aziz & Barbon 2024) ----------
def im_panel():
    df = R.load("SPY")
    df["k"] = ((df.ts.dt.hour * 60 + df.ts.dt.minute - 570) // 15).astype(int)    # 0 = 9:30 bar ... 25 = 15:45 bar
    P = {f: df.pivot(index="day", columns="k", values=f) for f in ("open", "high", "low", "close", "volume")}
    P = {f: v.reindex(columns=range(26)) for f, v in P.items()}
    days = pd.to_datetime(P["close"].index)
    op = P["open"][0].to_numpy()
    C = P["close"].to_numpy()
    last = P["close"].ffill(axis=1)[25].to_numpy()                 # session close (half-days: the last bar)
    tp = ((P["high"] + P["low"] + P["close"]) / 3).to_numpy()
    V = P["volume"].to_numpy()
    vwap = np.nancumsum(tp * V, axis=1) / np.nancumsum(V, axis=1)
    move = np.abs(C / op[:, None] - 1)
    sig = pd.DataFrame(move).rolling(14, min_periods=14).mean().shift(1).to_numpy()
    prev = np.r_[np.nan, last[:-1]]
    ub = np.maximum(op, prev)[:, None] * (1 + sig)
    lb = np.minimum(op, prev)[:, None] * (1 - sig)
    ret = pd.Series(last).pct_change()
    vol = ret.rolling(14).std().shift(1).to_numpy()                 # previous 14 daily returns, ddof 1
    nxt_open = np.c_[P["open"].to_numpy()[:, 1:], np.full(len(op), np.nan)]
    return dict(days=days, op=op, C=C, last=last, vwap=vwap, ub=ub, lb=lb, vol=vol, nxt=nxt_open)


def im_sim(X, legs="both", sizing=True, fill="close", cost_mult=1.0):
    marks = list(range(1, 25, 2))                                  # bars ending 10:00, 10:30, ..., 15:30
    fee = (0.0035 + 0.001) * cost_mult
    E, out = 1e5, []
    for t in range(len(X["days"])):
        if not np.isfinite(X["vol"][t]) or not np.isfinite(X["ub"][t]).any() or not np.isfinite(X["op"][t]):
            out.append(0.0); continue
        lev = min(4.0, 0.02 / X["vol"][t]) if sizing else 1.0
        sh = math.floor(E * lev / X["op"][t])
        pos, ent, pnl = 0, 0.0, 0.0
        for j in marks:
            c = X["C"][t, j]
            if not np.isfinite(c):
                continue
            ub, lb, vw = X["ub"][t, j], X["lb"][t, j], X["vwap"][t, j]
            px = c if fill == "close" else X["nxt"][t, j]
            if not np.isfinite(px):
                px = c
            want = pos
            if pos == 1:
                want = -1 if c < lb else (0 if c < max(ub, vw) else 1)
            elif pos == -1:
                want = 1 if c > ub else (0 if c > min(lb, vw) else -1)
            else:
                want = 1 if c > max(ub, vw) else (-1 if c < min(lb, vw) else 0)
            if legs == "long" and want == -1: want = 0
            if legs == "short" and want == 1: want = 0
            if want != pos:
                if pos:
                    pnl += pos * sh * (px - ent) - fee * sh
                if want:
                    ent = px; pnl -= fee * sh
                pos = want
        if pos:
            pnl += pos * sh * (X["last"][t] - ent) - fee * sh
        r = pnl / E
        E += pnl; out.append(r)
    return pd.Series(out, index=X["days"])


def test_D():
    X = im_panel()
    spy = pd.Series(X["last"], index=X["days"]).pct_change().fillna(0)
    wins = {"confirmatory": ("2025-01-02", W1), "replication": ("2016-03-01", "2024-12-31")}
    variants = {"full": {}, "long_only": dict(legs="long"), "short_only": dict(legs="short"),
                "next_open_fill": dict(fill="open"), "costs_x2": dict(cost_mult=2.0), "no_vol_sizing": dict(sizing=False)}
    S = {k: im_sim(X, **kw) for k, kw in variants.items()}
    res = {"windows": wins}
    for w, (a, b) in wins.items():
        o = {k: summary(s.loc[a:b]) for k, s in S.items()}
        o["spy_buyhold"] = summary(spy.loc[a:b])
        f, sp = S["full"].loc[a:b], spy.loc[a:b]
        o["risk_matched_spy"] = summary(sp * f.std() / sp.std())
        o["spy_plus_overlay"] = summary(sp + f)
        o["corr_with_spy"] = float(np.corrcoef(f, sp)[0, 1])
        o["nw_t_full"] = nw_t(f.to_numpy())
        o["by_year_full"] = {str(y): float((1 + g).prod() - 1) for y, g in f.groupby(f.index.year)}
        res[w] = o
    res["D_pass"] = bool(res["confirmatory"]["full"]["cagr"] > 0 and res["confirmatory"]["nw_t_full"] >= 1.65)
    json.dump(res, open(f"{OUT}/D.json", "w"), indent=1)
    for w in wins:
        print(w, pd.DataFrame({k: v for k, v in res[w].items() if isinstance(v, dict) and "sharpe" in v}).T.round(3).to_string(), sep="\n")
        print("NW t", round(res[w]["nw_t_full"], 2), "corr", round(res[w]["corr_with_spy"], 2), res[w]["by_year_full"])
    print("D_pass", res["D_pass"])


if __name__ == "__main__":
    {"B": test_B, "C": test_C, "D": test_D}[sys.argv[1]]()
