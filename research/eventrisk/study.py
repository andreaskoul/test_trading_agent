"""Scheduled-event risk (research/eventrisk/PREREG.md). Nothing here trades; nothing after 2025-12-31 is read.

    python research/eventrisk/study.py dev      # development: targets ending <= 2019-12-31
    python research/eventrisk/study.py oos      # the one out-of-sample read (writes OOS_READ.lock; refuses a second)
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
EV = os.path.join(ROOT, ".cache", "p8", "events.parquet")
END = pd.Timestamp("2025-12-31")
SPAN, FLOOR, STOP_K, TARGET_K = 60, 0.75, 2.0, 3.0
PERIODS = {"dev": ("2017-01-03", "2019-12-31"), "oos": ("2020-01-02", "2025-12-31")}


def nw_t(x, lags):
    """Mean and Newey-West t of a series (Bartlett weights)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < lags + 5:
        return float("nan"), float("nan"), n
    d = x - x.mean()
    v = d @ d / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (d[l:] @ d[:-l]) / n
    return float(x.mean()), float(x.mean() / math.sqrt(v / n)) if v > 0 else float("nan"), n


def p_one(t):
    return float(0.5 * math.erfc(t / math.sqrt(2))) if np.isfinite(t) else float("nan")


def sigma(e):
    """The fund's entry volatility on a (T, N) frame: max(EW std span 60, 0.75 x 252-session std)."""
    ew = e.ewm(span=SPAN, min_periods=SPAN, ignore_na=True).std()
    sd = e.rolling(252, min_periods=120).std()
    return np.maximum(ew, FLOOR * sd)


def load(shift=0):
    """Amendment 1: daily returns from the P8 Alpaca closes (adjusted for splits and dividends), point-in-time members."""
    sys.path.insert(0, os.path.join(ROOT, "research", "p8"))
    import prices as PX
    A = PX.panel()
    A = A[A.index <= END]
    S = pd.DatetimeIndex(A.index)
    r = A.pct_change(fill_method=None)
    rm = r["SPY"]
    mem = PX.members(S)
    ev = pd.read_parquet(EV)
    ev = ev[(ev.universe == "sp500") & (ev.t0 <= END)]
    names = sorted((set(t for ts in mem for t in ts) | set(ev.ticker)) & set(r.columns) - {"SPY"})
    ix = pd.Index(names)
    M = np.zeros((len(S), len(names)), bool)
    for j, ts in enumerate(mem.reindex(S)):
        k = ix.get_indexer(list(ts))
        M[j, k[k >= 0]] = True
    r = r[names]
    lo, hi = np.minimum(-2 * rm, 4 * rm), np.maximum(-2 * rm, 4 * rm)
    w = r.clip(lower=lo, upper=hi, axis=0)
    ols = w.rolling(252, min_periods=200).cov(rm).div(rm.rolling(252, min_periods=200).var(), axis=0)
    b = (2 / 3 * ols + 1 / 3).shift(1)
    e = r.sub(b.mul(rm, axis=0))
    ev = ev[ev.ticker.isin(names)]
    pos = S.searchsorted(pd.DatetimeIndex(ev.t0))                                   # a non-session date -> the next session
    ok = pos < len(S)
    Ea = np.zeros((len(S), len(names)), bool)
    Ea[pos[ok], ix.get_indexer(ev.ticker[ok])] = True
    E = pd.DataFrame(Ea, index=S, columns=names)
    if shift:                                                                       # the failure control's placebo calendar
        E = E.shift(shift, fill_value=False)
    sector = ev.groupby("ticker").sector.last().reindex(names)
    return S, e, E, sector, pd.DataFrame(M, index=S, columns=names), int(np.median(M.sum(1)))


def multiples(e, E, sd_d):
    """Announcement ratios q, the pooled multiple c and shrinkage k (monthly refit on past events), and each firm's
    shrunk multiple c* at the close of every session."""
    T, N = e.shape
    q = (e ** 2 / sd_d.shift(1) ** 2).where(E)
    qv = q.to_numpy()
    month = e.index.to_period("M")
    first = np.r_[True, month[1:] != month[:-1]]
    c_t, k_t = np.full(T, np.nan), np.full(T, np.nan)
    c, k = np.nan, np.nan
    for t in range(T):
        if first[t]:
            past = qv[:t]
            n_i = np.isfinite(past).sum(0)
            if n_i.sum() >= 200:
                c = float(np.nanmean(past))
                two = n_i >= 2
                mean_i = np.nanmean(past[:, two], 0)
                s_w = float(np.nansum((past[:, two] - mean_i) ** 2) / (n_i[two].sum() - two.sum()))
                tau = max(float(mean_i.var(ddof=1)) - s_w * float((1 / n_i[two]).mean()), 0.0)
                k = float(np.clip(s_w / tau, 1, 200)) if tau > 0 else 200.0
        c_t[t], k_t[t] = c, k
    # firm mean of the last <= 12 ratios, events up to and including t
    cf, nf = np.full((T, N), np.nan), np.zeros((T, N))
    for i in range(N):
        idx = np.where(np.isfinite(qv[:, i]))[0]
        if not len(idx):
            continue
        vals = qv[idx, i]
        m = np.array([vals[max(0, j - 11):j + 1].mean() for j in range(len(idx))])
        n = np.minimum(np.arange(1, len(idx) + 1), 12)
        seg = np.searchsorted(idx, np.arange(T), side="right") - 1
        has = seg >= 0
        cf[has, i], nf[has, i] = m[seg[has]], n[seg[has]]
    cs = (np.nan_to_num(cf) * nf + k_t[:, None] * c_t[:, None]) / (nf + k_t[:, None])
    return q, c_t, k_t, cs


def build(shift=0):
    S, e, E, sector, member, expected = load(shift)
    sd_e = sigma(e)
    e_d = e.mask(E)
    sd_d = sigma(e_d).ffill(limit=1)                                               # an event session keeps the last value
    q, c_t, k_t, cs = multiples(e, E, sd_d)
    csum = E.cumsum()
    elig = ((csum - csum.shift(300)) >= 3) & member
    return dict(expected=expected, member=member, S=S, e=e, E=E, sector=sector, sd_e=sd_e, sd_d=sd_d, q=q, c=c_t, k=k_t, cs=cs, csum=csum, elig=elig)


def window(D, H):
    """Forecasts, target and masks for the window t+1..t+H."""
    e, E = D["e"], D["E"]
    nE = (D["csum"].shift(-H) - D["csum"]).to_numpy()
    rv = (e ** 2).rolling(H, min_periods=H).sum().shift(-H).to_numpy()
    vd, ve = (D["sd_d"] ** 2).to_numpy(), (D["sd_e"] ** 2).to_numpy()
    F = {"B0": H * ve, "M1": H * vd, "C1": (H - nE) * vd + nE * D["c"][:, None] * vd, "C3": (H - nE) * vd + nE * D["cs"] * vd}
    ok = np.isfinite(rv) & (rv > 0) & D["elig"].to_numpy() & np.isfinite(nE)
    for f in F.values():
        ok &= np.isfinite(f) & (f > 0)
    return F, rv, nE, ok


def in_period(S, H, period):
    lo, hi = (pd.Timestamp(x) for x in PERIODS[period])
    end = pd.Series(S).shift(-H).to_numpy()
    return (S >= lo) & (pd.DatetimeIndex(end) <= hi)


def qlike(rv, f):
    x = rv / f
    return x - np.log(x) - 1


def gain(rv, fa, fb, mask, lags):
    """Daily cross-sectional mean of L(fa) - L(fb) on `mask`; positive = fb better."""
    d = np.where(mask, qlike(rv, fa) - qlike(rv, fb), np.nan)
    with np.errstate(all="ignore"):
        day = np.nanmean(d, 1)
    m, t, n = nw_t(day, lags)
    return {"gain": m, "t": t, "days": n, "rows": int(mask.sum())}


def stops(D, H, F, nE, ok, per):
    """S1: stop-hit rates of hypothetical lots, both sides, barriers -2W / +3W on cumulative e at closes."""
    e = D["e"].to_numpy()
    T, N = e.shape
    cum = np.full((H, T, N), np.nan)
    acc = np.zeros((T, N))
    for k in range(1, H + 1):
        nxt = np.vstack([e[k:], np.full((k, N), np.nan)])
        acc = acc + nxt
        cum[k - 1] = acc
    Ef = D["E"].to_numpy()
    ev_at = np.stack([np.vstack([Ef[k:], np.zeros((k, N), bool)]) for k in range(1, H + 1)])
    m = ok & per[:, None]
    out = {}
    for name in ("B0", "C3"):
        W = np.sqrt(F[name])
        hit, on_ev = [], []
        for side in (1, -1):
            c = side * cum
            fs = np.where((c <= -STOP_K * W).any(0), (c <= -STOP_K * W).argmax(0), H + 1)
            ft = np.where((c >= TARGET_K * W).any(0), (c >= TARGET_K * W).argmax(0), H + 1)
            h = (fs < ft) & (fs < H)
            hit.append(h)
            on_ev.append(h & np.take_along_axis(ev_at, np.minimum(fs, H - 1)[None], 0)[0])
        h, oe = np.stack(hit), np.stack(on_ev)
        ev_w, no_w = m & (nE >= 1), m & (nE == 0)
        out[name] = {"stop_rate_event_windows": float(h[:, ev_w].mean()), "stop_rate_other_windows": float(h[:, no_w].mean()),
                     "share_of_event_window_stops_on_the_event_session": float(oe[:, ev_w].sum() / max(h[:, ev_w].sum(), 1))}
    out["gaussian_noise_rate"] = float(math.erfc((STOP_K + 0.5826 / math.sqrt(H)) / math.sqrt(2)))
    return out


def macro(D, period):
    """E4: variance ratios of hedged returns on macro announcement days, name and sector level."""
    S, e, E = D["S"], D["e"], D["E"]
    lo, hi = (pd.Timestamp(x) for x in PERIODS[period])
    per = (S >= lo) & (S <= hi)
    cal = json.load(open(os.path.join(HERE, "macro_dates.json")))
    ratio = (e ** 2 / D["sd_d"].shift(1) ** 2).mask(E).where(D["elig"])
    name_day = ratio.mean(1)
    sec = D["sector"]
    cnt = e.T.groupby(sec).count().T
    sm = e.T.groupby(sec).mean().T.where(cnt >= 5)
    sv = sm.ewm(span=SPAN, min_periods=SPAN, ignore_na=True).var().shift(1)
    sec_day = (sm ** 2 / sv).mean(1)
    out = {}
    for g in ("fomc", "cpi", "employment"):
        pos = np.unique(S.searchsorted(pd.DatetimeIndex(cal[g])))
        is_g = np.zeros(len(S), bool)
        is_g[pos[pos < len(S)]] = True
        for level, x in (("name", name_day), ("sector", sec_day)):
            a, b = x[per & is_g].dropna(), x[per & ~is_g].dropna()
            se = math.sqrt(a.var() / len(a) + b.var() / len(b))
            t = float((a.mean() - b.mean()) / se)
            out[f"{g}_{level}"] = {"ratio": float(a.mean() / b.mean()), "macro_mean": float(a.mean()), "other_mean": float(b.mean()),
                                   "t": t, "p_one_sided": p_one(t), "macro_days": int(len(a)), "other_days": int(len(b))}
    return out


def run(period, shift=0):
    D = build(shift)
    S = D["S"]
    res = {"coverage": {}, "params": {}}
    last = np.where(S <= pd.Timestamp(PERIODS[period][1]))[0][-1]
    res["params"] = {"pooled_c_at_period_end": float(D["c"][last]), "k_at_period_end": float(D["k"][last]),
                     "pooled_c_at_period_start": float(D["c"][np.where(S >= pd.Timestamp(PERIODS[period][0]))[0][0]])}
    for H in (5, 15):
        F, rv, nE, ok = window(D, H)
        per = in_period(S, H, period)
        m = ok & per[:, None]
        evw, now = m & (nE >= 1), m & (nE == 0)
        res["coverage"][f"H{H}"] = {"names_per_day_mean": float(m[per].sum(1).mean()), "members_per_day": float(D["member"].to_numpy()[per].sum(1).mean()),
                                    "members_without_complete_calendar_per_day": float((D["member"].to_numpy() & ~D["elig"].to_numpy())[per].sum(1).mean()),
                                    "share_of_windows_with_event": float(evw.sum() / m.sum())}
        lags = H + 5
        res[f"E1_H{H}"] = gain(rv, F["B0"], F["C3"], m, lags)
        res[f"E1_H{H}_event_windows"] = gain(rv, F["B0"], F["C3"], evw, lags)
        res[f"E1_H{H}_other_windows"] = gain(rv, F["B0"], F["C3"], now, lags)
        res[f"M1_vs_B0_H{H}"] = gain(rv, F["B0"], F["M1"], m, lags)
        res[f"event_term_H{H}"] = gain(rv, F["M1"], F["C3"], evw, lags)          # the failure control reads this one
        res[f"C1_vs_B0_H{H}"] = gain(rv, F["B0"], F["C1"], m, lags)
        if H == 15:
            res["E2_H15"] = gain(rv, F["C1"], F["C3"], evw, lags)
        res[f"level_H{H}"] = {k: {"all": float(np.mean(rv[m] / f[m])), "event_windows": float(np.mean(rv[evw] / f[evw])),
                                  "other_windows": float(np.mean(rv[now] / f[now]))} for k, f in F.items()}
        if not shift:
            res[f"S1_H{H}"] = stops(D, H, F, nE, ok, per)
        if H == 5:                                                                  # P-E1, Thursday origins
            thu = np.array([d.weekday() == 3 for d in S]) & per
            x = (D["e"].rolling(5, min_periods=5).sum().shift(-5).to_numpy()) ** 2
            s = np.sqrt(F["M1"] / F["C3"])
            mm = ok & thu[:, None] & np.isfinite(x)
            s_ = np.where(mm, s, np.nan)
            kt = 1 / np.nanmean(s_, 1)
            un, sc = np.where(mm, x, np.nan), np.where(mm, (kt[:, None] * s_) ** 2 * x, np.nan)
            d = np.nanmean(un, 1) - np.nanmean(sc, 1)
            mean, t, n = nw_t(d[thu], 2)
            res["PE1"] = {"D": mean, "t": t, "weeks": n, "variance_ratio_scaled_to_unscaled": float(np.nansum(sc) / np.nansum(un)),
                          "share_of_positions_scaled": float((s_ < 0.999).sum() / mm.sum()),
                          "mean_scalar_when_scaled": float(np.nanmean(np.where(s_ < 0.999, s_, np.nan)))}
    if not shift:
        res["E4"] = macro(D, period)
    return res


def main():
    period = sys.argv[1]
    lock = os.path.join(HERE, "OOS_READ.lock")
    if period == "oos":
        if os.path.exists(lock):
            sys.exit("the out-of-sample read was already made: " + open(lock).read())
        open(lock, "w").write(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    res = run(period)
    res["placebo_calendar_shift_21"] = {k: v for k, v in run(period, shift=21).items() if k.startswith(("event_term", "E1_", "E2", "PE1", "params"))}
    res["run"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    res["period"] = period
    name = {"dev": "DEV_RESULT.json", "oos": "OOS_RESULT.json"}[period]
    json.dump(res, open(os.path.join(HERE, name), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
