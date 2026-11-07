"""Risk-field research, round 5 (PREREG.md Amendment 8): intraday contagion of neighbours' earnings shocks.

    python research/riskfield/round5.py dev     # -> DEV5_RESULT.md/json
    python research/riskfield/round5.py read    # ONCE; refuses if OOS5_READ.lock exists -> OOS5_RESULT.md/json
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
import panel as P                                                                     # noqa: E402
import risk as K                                                                      # noqa: E402
from intl import dk_t                                                                 # noqa: E402
from oos import holm                                                                  # noqa: E402

DEV = (pd.Timestamp("2016-02-01"), pd.Timestamp("2019-12-31"))
OOS = (pd.Timestamp("2020-01-02"), pd.Timestamp("2025-12-31"))
TESTS = {"I1": "text", "I2": "co"}


def daily_beta(D):
    r = np.expm1(D.r)
    rm = r[:, D.si]
    lo, hi = np.minimum(-2 * rm, 4 * rm)[:, None], np.maximum(-2 * rm, 4 * rm)[:, None]
    w = pd.DataFrame(np.clip(r, lo, hi))
    m = pd.Series(rm)
    b = (w.rolling(252, min_periods=200).cov(m).div(m.rolling(252, min_periods=200).var(), axis=0)).to_numpy(copy=True)
    return np.vstack([np.full((1, D.N), np.nan), b[:-1]])                          # beta of t-1


def build(D, period):
    ev = pd.read_parquet(os.path.join(P.P8, "events.parquet"), columns=["ticker", "accepted_et", "t0"])
    ev = ev[(ev.t0 <= P.END)]
    ni = pd.Index(D.names).get_indexer(ev.ticker)
    ti = D.S.get_indexer(ev.t0)
    ok = (ni >= 0) & (ti >= 0)
    ev, ni, ti = ev[ok], ni[ok], ti[ok]
    acc = ev.accepted_et
    outside = (acc.dt.normalize() < ev.t0) | (acc.dt.hour * 60 + acc.dt.minute < 570)
    rep = np.zeros((D.T, D.N), bool)
    rep[ti, ni] = True                                             # any earnings reaction at t (excluded as targets)
    src = np.zeros((D.T, D.N), bool)
    src[ti[outside.to_numpy()], ni[outside.to_numpy()]] = True       # announced outside trading hours
    b = daily_beta(D)
    R = D.R
    first = R[:, 0] + R[:, 1]                                      # previous close -> 10:00
    rest = R[:, 2:].sum(1)                                         # 10:00 -> close (needs all bars)
    shock = first - b * first[:, [D.si]]
    tgt = rest - b * rest[:, [D.si]]
    has_shock = src & np.isfinite(shock) & D.stock
    shock0 = np.where(has_shock, shock, 0.0)
    out = {}
    for k, kind in TESTS.items():
        blocks, spread = [], []
        bounds = list(D.mstart) + [D.T]
        for a, bb in zip(bounds[:-1], bounds[1:]):
            W = D.kernel(kind, a)
            for t in range(a, bb):
                if not (period[0] <= D.S[t] <= period[1]):
                    continue
                nb = (W > 0) @ has_shock[t].astype(float)
                rows = D.stock & ~rep[t] & np.isfinite(tgt[t]) & (nb > 0) & (W.sum(1) > 0)
                if rows.sum() < 20:
                    continue
                f = W @ shock0[t]
                x = np.where(rows, f, np.nan)
                z = (x - np.nanmean(x)) / np.nanstd(x)
                blocks.append((np.full(D.N, t), np.where(rows, tgt[t], np.nan), z))
                q = np.nanquantile(z, [0.1, 0.9])
                spread.append(np.nanmean(np.where(z >= q[1], tgt[t], np.nan)) - np.nanmean(np.where(z <= q[0], tgt[t], np.nan)))
        bt, t_, n = dk_t(blocks)
        out[k] = {"b": bt, "t": t_, "n": n, "bp_per_sd": bt * 1e4, "sessions": len(blocks),
                  "spread_bp": float(np.nanmean(spread) * 1e4), "rows_per_session": n / max(len(blocks), 1)}
    return out


def table(r, title):
    L = [f"# Risk-field research, round 5 (intraday contagion of earnings shocks): {title}", "",
         "| Test | bp per sd (10:00 → close) | DK t | top − bottom decile, bp | sessions | rows/session |", "|---|---:|---:|---:|---:|---:|"]
    for k in TESTS:
        a = r[k]
        L.append(f"| {k} | {a['bp_per_sd']:.2f} | {a['t']:.2f} | {a['spread_bp']:.1f} | {a['sessions']} | {a['rows_per_session']:.0f} |")
    return L


def dev():
    r = build(K.Data(), DEV)
    r["finalists"] = [k for k in TESTS if r[k]["t"] >= 1.5 and r[k]["b"] > 0]
    json.dump(r, open(os.path.join(HERE, "DEV5_RESULT.json"), "w"), indent=1, default=float)
    L = table(r, "development") + ["", f"**Finalists:** {', '.join(r['finalists']) or 'none'}"]
    open(os.path.join(HERE, "DEV5_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def read():
    lock = os.path.join(HERE, "OOS5_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    fin = json.load(open(os.path.join(HERE, "DEV5_RESULT.json")))["finalists"]
    if not fin:
        raise SystemExit("no finalists: nothing to read")
    r = build(K.Data(), OOS)
    res = {k: {"p": float(norm.sf(r[k]["t"])), "ok_sign": r[k]["b"] > 0} for k in fin}
    holm(res)
    for k in res:
        res[k]["pass"] = bool(res[k]["p_holm"] < 0.05 and res[k]["ok_sign"])
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    json.dump({"read_at": at, "finalists": fin, "stats": r, "results": res}, open(os.path.join(HERE, "OOS5_RESULT.json"), "w"),
              indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    L = table(r, f"out-of-sample read (one read, {at})") + ["", "Only finalists count.", ""] + [
        f"* **{k}**: p one-sided {v['p']:.4f}, Holm {v['p_holm']:.4f}, {'**pass**' if v['pass'] else 'fail'}" for k, v in res.items()]
    open(os.path.join(HERE, "OOS5_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"dev": dev, "read": read}[sys.argv[1]]()
