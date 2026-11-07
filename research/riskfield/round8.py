"""Risk-field research, round 8 (PREREG.md Amendment 11): Avellaneda-Lee OU statistical arbitrage against the
mean field of a name's neighbours (text: S1, S2; co-movement: S3).

    python research/riskfield/round8.py dev     # development 2011-06..2019 -> DEV8_RESULT.md/json
    python research/riskfield/round8.py read    # ONCE; refuses if OOS8_READ.lock exists -> OOS8_RESULT.md/json
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "regime"))
import alpha as A                                                                     # noqa: E402
import panel as PN                                                                    # noqa: E402
import regime as RG                                                                   # noqa: E402
import risk as K                                                                      # noqa: E402
from oos import holm                                                                  # noqa: E402

DEV = (pd.Timestamp("2011-06-01"), pd.Timestamp("2019-12-31"))
OOS = (pd.Timestamp("2020-01-02"), pd.Timestamp("2025-12-30"))
WIN, BMAX, SO, SBC, SSC, COST = 60, 0.9672, 1.25, 0.75, 0.50, 5e-4
TESTS = {"S1": ("text", 2), "S2": ("text", 1), "S3": ("co", 2)}


def basket_returns(r, W):
    """r: L x N daily returns; W: N x N kernel. Basket return per name, renormalised over finite neighbours."""
    f = np.isfinite(r)
    num, den = np.nan_to_num(r) @ W.T, f.astype(float) @ W.T
    rowm = W.sum(1)
    return np.where((den >= 0.5 * rowm) & (rowm > 0), num / np.maximum(den, 1e-12), np.nan)


def scores(P, kind, lo, hi):
    """s-score, filter and beta per session and name (sessions lo..hi), from the last 60 returns."""
    S, names, r = P["S"], P["names"], P["r"]
    T, N = r.shape
    s = np.full((T, N), np.nan)
    beta = np.full((T, N), np.nan)
    rB = np.full((T, N), np.nan)
    month = None
    for t in range(lo, hi + 1):
        if (S[t].year, S[t].month) != month:
            month = (S[t].year, S[t].month)
            tau = t
            while tau > 0 and (S[tau - 1].year, S[tau - 1].month) == month:
                tau -= 1
            if kind == "text":
                W, _ = PN.text_kernel(names, S[tau])
            else:
                W = A.co_kernel(P["e"][tau - 252:tau], P["elig"][tau - 1])
            # basket returns for this month (and the 60 sessions before it, with this month's kernel)
            a = max(0, tau - WIN)
            end = t
            while end + 1 < T and (S[end + 1].year, S[end + 1].month) == month:
                end += 1
            RB = basket_returns(r[a:end + 1], W)
            off = a
        y = r[t - WIN + 1:t + 1]
        x = RB[t - WIN + 1 - off:t + 1 - off]
        rB[t] = RB[t - off]
        ok = np.isfinite(y).all(0) & np.isfinite(x).all(0) & P["elig"][t]
        if ok.sum() < 30:
            continue
        Y, X = y[:, ok], x[:, ok]
        xm, ym = X.mean(0), Y.mean(0)
        b = ((X - xm) * (Y - ym)).sum(0) / ((X - xm) ** 2).sum(0)
        b0 = ym - b * xm
        eps = Y - b0 - b * X
        Xc = np.cumsum(eps, 0)
        x0, x1 = Xc[:-1], Xc[1:]
        m0, m1 = x0.mean(0), x1.mean(0)
        bb = ((x0 - m0) * (x1 - m1)).sum(0) / ((x0 - m0) ** 2).sum(0)
        aa = m1 - bb * m0
        z = x1 - aa - bb * x0
        vz = z.var(0, ddof=1)
        good = (bb > 0) & (bb < BMAX)
        m = np.where(good, aa / (1 - bb), np.nan)
        seq = np.sqrt(vz / (1 - bb ** 2))
        mc = m - np.nanmean(m)
        sc = np.where(good, -mc / seq, np.nan)
        idx = np.where(ok)[0]
        s[t, idx] = sc
        beta[t, idx] = b
    return s, beta, rB


def simulate(P, s, beta, rB, lag, lo, hi, block=None):
    """A-L state machine on s (decided at close t). The position held over session d (close d-1 -> close d) is the
    decision of session d - lag: lag 1 = traded at close t, lag 2 = traded at close t+1. Costs are charged on the
    first session of a changed holding: 5 bp x |change| x (1 + |beta|)."""
    r = P["r"]
    T, N = r.shape
    Dp, Db = np.zeros((T, N)), np.zeros((T, N))
    pos, bpos = np.zeros(N), np.zeros(N)
    for t in range(lo - lag, hi + 1):
        st = s[t]
        new = pos.copy()
        opn = pos == 0
        if block is not None:                                       # Amendment 13: no new position after news
            opn = opn & ~block[t]
        new[opn & (st < -SO)] = 1
        new[opn & (st > SO)] = -1
        new[(pos == -1) & (st < SBC)] = 0
        new[(pos == 1) & (st > -SSC)] = 0
        new[(~P["elig"][t] | ~np.isfinite(r[t])) & (pos != 0)] = 0
        bpos = np.where(new != 0, np.where(pos == 0, np.nan_to_num(beta[t]), bpos), 0.0)
        pos = new
        Dp[t], Db[t] = pos, bpos
    daily, n_open, trades, hold = [], [], 0, 0
    for d in range(lo, hi + 1):
        h, hb = Dp[d - lag], Db[d - lag]
        h0, hb0 = Dp[d - lag - 1], Db[d - lag - 1]
        pnl = (h * (np.nan_to_num(r[d]) - hb * np.nan_to_num(rB[d]))).sum()
        ch = (h != h0) | ((h != 0) & (hb != hb0))
        cost = COST * (np.abs(h - h0) * (1 + np.abs(np.where(h != 0, hb, hb0))))[ch].sum()
        trades += int(((h != 0) & (h0 == 0)).sum())
        k = max(int((h != 0).sum()), int((h0 != 0).sum()))
        daily.append((pnl - cost) / k if k else 0.0)
        n_open.append(int((h != 0).sum()))
        hold += int((h != 0).sum())
    d = np.array(daily)
    yrs = len(d) / 252
    return d, {"trades_per_year": trades / yrs, "avg_open": float(np.mean(n_open)), "avg_hold_days": hold / max(trades, 1)}


def run(period):
    P = RG.panel()
    S = P["S"]
    lo = int(np.searchsorted(S.values, np.datetime64(period[0])))
    hi = int(np.searchsorted(S.values, np.datetime64(period[1]), side="right")) - 2
    lo = max(lo, 260)
    out, cache = {}, {}
    for k, (kind, lag) in TESTS.items():
        if kind not in cache:
            cache[kind] = scores(P, kind, lo - 1, hi)
        s, b, rB = cache[kind]
        d, info = simulate(P, s, b, rB, lag, lo, hi)
        m, t, n = K.nw_t(d, 10)
        out[k] = {"mean_bp_day": m * 1e4, "t": t, "days": n, "net_pct_yr": float((np.prod(1 + d) ** (252 / len(d)) - 1) * 100),
                  "sharpe": float(d.mean() / d.std(ddof=1) * np.sqrt(252)), **info,
                  "years": {int(y): float((np.prod(1 + d[S[lo:hi + 1].year == y]) - 1) * 100) for y in sorted(set(S[lo:hi + 1].year))}}
    return out


def table(r, title):
    L = [f"# Risk-field research, round 8 (OU stat-arb against the neighbour mean field): {title}", "",
         "| Test | net bp/day | NW t | net %/yr | Sharpe | trades/yr | avg open | avg hold (days) |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k in TESTS:
        a = r[k]
        L.append(f"| {k} | {a['mean_bp_day']:.2f} | {a['t']:.2f} | {a['net_pct_yr']:.2f} | {a['sharpe']:.2f} | {a['trades_per_year']:.0f} | "
                 f"{a['avg_open']:.0f} | {a['avg_hold_days']:.1f} |")
    L += ["", "By year, net %: " + "; ".join(f"{k}: " + ", ".join(f"{y} {v:+.1f}" for y, v in r[k]["years"].items()) for k in TESTS)]
    return L


def dev():
    r = run(DEV)
    r["finalists"] = [k for k in TESTS if r[k]["t"] >= 1.5 and r[k]["mean_bp_day"] > 0]
    json.dump(r, open(os.path.join(HERE, "DEV8_RESULT.json"), "w"), indent=1, default=float)
    L = table(r, "development 2011-06..2019") + ["", f"**Finalists:** {', '.join(r['finalists']) or 'none'}"]
    open(os.path.join(HERE, "DEV8_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def read():
    lock = os.path.join(HERE, "OOS8_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    fin = json.load(open(os.path.join(HERE, "DEV8_RESULT.json")))["finalists"]
    if not fin:
        raise SystemExit("no finalists: nothing to read")
    r = run(OOS)
    res = {k: {"p": float(norm.sf(r[k]["t"])), "ok": r[k]["mean_bp_day"] > 0} for k in fin}
    holm(res)
    for k in res:
        res[k]["pass"] = bool(res[k]["p_holm"] < 0.05 and res[k]["ok"])
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    json.dump({"read_at": at, "finalists": fin, "stats": r, "results": res}, open(os.path.join(HERE, "OOS8_RESULT.json"), "w"),
              indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    L = table(r, f"out-of-sample read 2020-2025 (one read, {at})") + ["", "Only finalists count.", ""] + [
        f"* **{k}**: p one-sided {v['p']:.4f}, Holm {v['p_holm']:.4f}, {'**pass**' if v['pass'] else 'fail'}" for k, v in res.items()]
    open(os.path.join(HERE, "OOS8_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"dev": dev, "read": read}[sys.argv[1]]()
