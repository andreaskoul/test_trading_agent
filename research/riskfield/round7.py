"""Risk-field research, round 7 (PREREG.md Amendment 10): insider trading (N1 net purchase ratio, N2 opportunistic
insiders, N3 text-neighbour field), S&P 500 point in time, weekly decisions, 20-session staggered books.

    python research/riskfield/round7.py dev     # development 2013-2019 -> DEV7_RESULT.md/json
    python research/riskfield/round7.py read    # ONCE; refuses if OOS7_READ.lock exists -> OOS7_RESULT.md/json
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
from intl import dk_t                                                                 # noqa: E402
from oos import holm                                                                  # noqa: E402

DEV = (pd.Timestamp("2013-01-01"), pd.Timestamp("2019-12-31"))
OOS = (pd.Timestamp("2020-01-01"), pd.Timestamp("2025-12-31"))
HOLD, COST, WIN = 20, 5e-4, 63
TESTS = ("N1", "N2", "N3")


def insiders(S, names):
    """Trades mapped to panel columns: filing session index, owner, P/S, and the owner's class for N2."""
    D = pd.read_parquet(os.path.join(PN.CACHE, "insider_trades.parquet"))
    tc = PN.ticker_cik()
    cik_cols = {}
    for j, n in enumerate(names):
        if n in tc:
            cik_cols.setdefault(int(tc[n]), []).append(j)
    D = D[D.ISSUERCIK.isin(list(cik_cols))].copy()
    D["fs"] = np.searchsorted(S.values, D.FILING_DATE.values.astype("datetime64[ns]"))
    D = D[D.fs < len(S)]
    # N2 classes per (owner, issuer) and calendar year y, from trades in y-3..y-1 (trade dates)
    D["ty"], D["tm"] = D.TRANS_DATE.dt.year, D.TRANS_DATE.dt.month
    months = D.groupby(["RPTOWNERCIK", "ISSUERCIK", "ty"]).tm.agg(lambda x: frozenset(x)).to_dict()
    cls = {}
    def klass(o, i, y):
        k = (o, i, y)
        if k in cls:
            return cls[k]
        ms = [months.get((o, i, y - d)) for d in (1, 2, 3)]
        c = "u" if any(m is None for m in ms) else ("r" if ms[0] & ms[1] & ms[2] else "o")
        cls[k] = c
        return c
    # the class applies to trades filed in year y (classification at the start of y)
    D["fy"] = D.FILING_DATE.dt.year
    D["cls"] = [klass(o, i, y) for o, i, y in zip(D.RPTOWNERCIK, D.ISSUERCIK, D.fy)]
    rows = []
    for c, js in cik_cols.items():
        x = D[D.ISSUERCIK == c]
        for j in js:
            rows.append(x.assign(j=j))
    D = pd.concat(rows, ignore_index=True)[["fs", "j", "RPTOWNERCIK", "TRANS_CODE", "cls"]]
    return D


def signals(D, t, N):
    w = D[(D.fs >= t - WIN) & (D.fs <= t - 1)]
    n1, n2 = np.zeros(N), np.zeros(N)
    if len(w):
        g = w.drop_duplicates(["j", "RPTOWNERCIK", "TRANS_CODE"])
        b = g[g.TRANS_CODE == "P"].groupby("j").size()
        s = g[g.TRANS_CODE == "S"].groupby("j").size()
        tot = b.add(s, fill_value=0)
        r = (b.reindex(tot.index, fill_value=0) - s.reindex(tot.index, fill_value=0)) / tot
        n1[r.index.to_numpy()] = r.to_numpy()
        o = g[g.cls == "o"]
        ob = o[o.TRANS_CODE == "P"].groupby("j").size()
        os_ = o[o.TRANS_CODE == "S"].groupby("j").size()
        d = ob.sub(os_, fill_value=0)
        n2[d.index.to_numpy().astype(int)] = d.to_numpy()
    return n1, n2


def cohort(P, t, wts, cols):
    hedge = -float((wts * P["beta"][t, cols]).sum())
    a = t + 1
    px = pd.DataFrame(P["close"][a:a + HOLD + 1][:, cols]).ffill().to_numpy()
    sub = []
    for k in range(4):
        m0, m1 = 5 * k, 5 * (k + 1)
        R = px[m1] / px[m0] - 1
        Rm = P["spy"][a + m1] / P["spy"][a + m0] - 1
        sub.append(float(np.nansum(wts * R) + hedge * Rm))
    gu = np.abs(wts).sum() + abs(hedge)
    sub[0] -= COST * gu
    sub[-1] -= COST * gu
    return sub


def run(period):
    P = RG.panel()
    S, names, n = P["S"], P["names"], len(P["S"])
    D = insiders(S, names)
    cr = np.vstack([np.zeros((1, len(names))), np.nancumsum(np.nan_to_num(P["e"]), 0)])
    last = int(np.searchsorted(S.values, np.datetime64(period[1]), side="right")) - 1
    dec = [t for t in range(260, n) if S[t].weekday() == 3 and S[t] >= period[0] and t + HOLD + 1 <= last]
    month = None
    blocks = {k: [] for k in TESTS}
    blocks60 = {k: [] for k in TESTS}
    coh = {k: [] for k in TESTS}
    counts = {"N1_nonzero": [], "N2_nonzero": []}
    for w, t in enumerate(dec):
        if (S[t].year, S[t].month) != month:
            month = (S[t].year, S[t].month)
            tau = t
            while tau > 0 and (S[tau - 1].year, S[tau - 1].month) == month:
                tau -= 1
            Wt, has = PN.text_kernel(names, S[tau])
        el = P["elig"][t] & np.isfinite(P["close"][t + 1]) & np.isfinite(P["close"][t])
        n1, n2 = signals(D, t, len(names))
        n3 = A.fld(Wt, np.where(el & has, n1, np.nan))
        sig = {"N1": np.where(el, n1, np.nan), "N2": np.where(el, n2, np.nan), "N3": np.where(el & has, n3, np.nan)}
        counts["N1_nonzero"].append(int((sig["N1"] != 0).sum() - np.isnan(sig["N1"]).sum() * 0))
        counts["N2_nonzero"].append(int(np.nansum(sig["N2"] != 0)))
        y20 = np.where(el, cr[t + HOLD + 2] - cr[t + 2], np.nan)
        y60 = np.where(el, cr[min(t + 62, n)] - cr[t + 2], np.nan) if t + 62 <= last else np.full(len(names), np.nan)
        for k, s in sig.items():
            z = RG.zs(s)
            blocks[k].append((np.full(len(z), w), y20, z))
            blocks60[k].append((np.full(len(z), w), y60, z))
            if k == "N3":
                ok = np.isfinite(s)
                q = np.nanquantile(s[ok], [0.1, 0.9]) if ok.sum() > 50 else None
                L = ok & (s >= q[1]) if q is not None else np.zeros(len(s), bool)
                Sh = ok & (s <= q[0]) if q is not None else np.zeros(len(s), bool)
                if q is not None and q[1] == q[0]:
                    L = Sh = np.zeros(len(s), bool)
            else:
                L, Sh = np.nan_to_num(s) > 0, np.nan_to_num(s) < 0
            if L.sum() >= 5 and Sh.sum() >= 5:
                wts = np.zeros(len(names))
                wts[L], wts[Sh] = 0.5 / L.sum(), -0.5 / Sh.sum()
                cols = np.where(wts != 0)[0]
                coh[k].append(cohort(P, t, wts[cols], cols))
            else:
                coh[k].append(None)
    res = {}
    for k in TESTS:
        b, tt, nobs = dk_t(blocks[k])
        b6, t6, _ = dk_t([x for x in blocks60[k] if np.isfinite(x[1]).any()])
        wk = np.zeros(len(dec) + 4)
        for w, c in enumerate(coh[k]):
            if c is not None:
                for j, r in enumerate(c):
                    wk[w + j] += r / 4
        wk = wk[:len(dec)]
        res[k] = {"b": b, "t": tt, "n": nobs, "bp_per_sd_20": b * 1e4, "bp_per_sd_60": b6 * 1e4, "t60": t6,
                  "book": {"net_pct_yr": float((np.prod(1 + wk) ** (52 / len(wk)) - 1) * 100), "net_mean_bp_wk": float(wk.mean() * 1e4),
                           "sharpe": float(wk.mean() / wk.std(ddof=1) * np.sqrt(52)), "weeks": len(wk),
                           "cohorts": int(sum(c is not None for c in coh[k]))}}
    res["coverage"] = {"N1_names_with_trades_per_week": float(np.mean(counts["N1_nonzero"])),
                       "N2_names_nonzero_per_week": float(np.mean(counts["N2_nonzero"]))}
    return res


def table(r, title):
    L = [f"# Risk-field research, round 7 (insider trading): {title}", "",
         "| Test | bp per sd, 20 sessions | DK t | bp per sd, 60 sessions | t | book net %/yr | Sharpe | cohorts |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k in TESTS:
        a = r[k]
        L.append(f"| {k} | {a['bp_per_sd_20']:.1f} | {a['t']:.2f} | {a['bp_per_sd_60']:.1f} | {a['t60']:.2f} | {a['book']['net_pct_yr']:.2f} | "
                 f"{a['book']['sharpe']:.2f} | {a['book']['cohorts']} |")
    L += ["", f"Coverage: names with insider trades in the window per week {r['coverage']['N1_names_with_trades_per_week']:.0f}; "
          f"names with nonzero opportunistic net {r['coverage']['N2_names_nonzero_per_week']:.0f}."]
    return L


def dev():
    r = run(DEV)
    r["finalists"] = [k for k in TESTS if r[k]["t"] >= 1.5 and r[k]["book"]["net_mean_bp_wk"] > 0]
    json.dump(r, open(os.path.join(HERE, "DEV7_RESULT.json"), "w"), indent=1, default=float)
    L = table(r, "development 2013-2019") + ["", f"**Finalists:** {', '.join(r['finalists']) or 'none'}"]
    open(os.path.join(HERE, "DEV7_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def read():
    lock = os.path.join(HERE, "OOS7_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    fin = json.load(open(os.path.join(HERE, "DEV7_RESULT.json")))["finalists"]
    if not fin:
        raise SystemExit("no finalists: nothing to read")
    r = run(OOS)
    res = {k: {"p": float(norm.sf(r[k]["t"])), "ok": r[k]["book"]["net_mean_bp_wk"] > 0} for k in fin}
    holm(res)
    for k in res:
        res[k]["pass"] = bool(res[k]["p_holm"] < 0.05 and res[k]["ok"])
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    json.dump({"read_at": at, "finalists": fin, "stats": r, "results": res}, open(os.path.join(HERE, "OOS7_RESULT.json"), "w"),
              indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    L = table(r, f"out-of-sample read 2020-2025 (one read, {at})") + ["", "Only finalists count.", ""] + [
        f"* **{k}**: p one-sided {v['p']:.4f}, Holm {v['p_holm']:.4f}, {'**pass**' if v['pass'] else 'fail'}" for k, v in res.items()]
    open(os.path.join(HERE, "OOS7_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"dev": dev, "read": read}[sys.argv[1]]()
