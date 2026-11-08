"""Risk-field research, round 10 (PREREG.md Amendment 14): options (O1-O4) and FINRA short volume (F1, F2).

    python research/riskfield/round10.py iv      # -> .cache/riskfield/opt_daily.parquet (daily O1-O3 per name; no statistic)
    python research/riskfield/round10.py dev     # development -> DEV10_RESULT.md/json
    python research/riskfield/round10.py read    # ONCE; refuses if OOS10_READ.lock exists -> OOS10_RESULT.md/json
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.special import ndtr
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "regime"))
import alpha as A                                                                     # noqa: E402
import panel as PN                                                                    # noqa: E402
import regime as RG                                                                   # noqa: E402
from intl import dk_t                                                                 # noqa: E402
from oos import holm                                                                  # noqa: E402

RAW = os.path.join(PN.CACHE, "options")
ODAILY = os.path.join(PN.CACHE, "opt_daily.parquet")
PER = {"O": {"dev": (pd.Timestamp("2024-03-07"), pd.Timestamp("2024-12-31")), "oos": (pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-24"))},
       "F": {"dev": (pd.Timestamp("2012-04-01"), pd.Timestamp("2019-12-31")), "oos": (pd.Timestamp("2020-01-01"), pd.Timestamp("2025-12-24"))}}
SIGN = {"O1": 1, "O2": -1, "O3": -1, "O4": 1, "F1": 0, "F2": 0}


# ------------------------------------------------------------------------------------------------------ implied vol
def bs(S, K, T, r, sig, call):
    d1 = (np.log(S / K) + (r + 0.5 * sig ** 2) * T) / (sig * np.sqrt(T))
    d2 = d1 - sig * np.sqrt(T)
    c = S * ndtr(d1) - K * np.exp(-r * T) * ndtr(d2)
    return np.where(call, c, c - S + K * np.exp(-r * T))


def implied(price, S, K, T, r, call):
    lo, hi = np.full(price.shape, 0.01), np.full(price.shape, 5.0)
    for _ in range(60):                                                 # bisection, vectorised
        mid = (lo + hi) / 2
        too = bs(S, K, T, r, mid, call) > price
        hi, lo = np.where(too, mid, hi), np.where(too, lo, mid)
    iv = (lo + hi) / 2
    ok = (iv > 0.011) & (iv < 4.99)
    return np.where(ok, iv, np.nan)


def iv():
    B = pd.read_parquet(os.path.join(RAW, "bars.parquet"))
    C = pd.read_parquet(os.path.join(RAW, "contracts_kept.parquet"))
    S = pd.read_parquet(os.path.join(RAW, "stock_daily.parquet"))
    B = B.merge(C[["symbol", "underlying", "type", "strike", "expiry"]], on="symbol")
    B["date"] = pd.to_datetime(B.date)
    S["date"] = pd.to_datetime(S.date)
    B = B.merge(S.rename(columns={"ticker": "underlying", "vwap": "s_vwap", "volume": "s_vol", "close": "s_close"}), on=["underlying", "date"])
    r = pd.read_csv(os.path.join(PN.QT, "dtb3.csv"))
    r.columns = ["date", "dtb3"]
    r["date"] = pd.to_datetime(r.date)
    r["dtb3"] = pd.to_numeric(r.dtb3, errors="coerce")
    r = r.dropna().set_index("date").dtb3.sort_index()
    B["r"] = np.log1p(r.reindex(B.date, method="ffill").to_numpy() / 100)
    B["T"] = (pd.to_datetime(B.expiry) - B.date).dt.days / 365
    B["m"] = B.strike / B.s_vwap
    call = (B.type == "call").to_numpy()
    intrinsic = np.where(call, np.maximum(B.s_vwap - B.strike, 0), np.maximum(B.strike - B.s_vwap, 0))
    keep = (B["T"] * 365 >= 10) & (B["T"] * 365 <= 60) & (B.m >= 0.85) & (B.m <= 1.15) & (B.volume >= 1) & (B.vwap > intrinsic)
    B = B[keep].copy()
    B["iv"] = implied(B.vwap.to_numpy(), B.s_vwap.to_numpy(), B.strike.to_numpy(), B["T"].to_numpy(), B.r.to_numpy(),
                      (B.type == "call").to_numpy())
    B = B.dropna(subset=["iv"])
    rows = []
    for (u, d), g in B.groupby(["underlying", "date"]):
        # O1: call-put pairs, same strike and expiry, K/S in [0.9, 1.1]
        h = g[(g.m >= 0.9) & (g.m <= 1.1)]
        c, p = h[h.type == "call"], h[h.type == "put"]
        pr = c.merge(p, on=["strike", "expiry"], suffixes=("_c", "_p"))
        o1 = np.average(pr.iv_c - pr.iv_p, weights=np.minimum(pr.volume_c, pr.volume_p)) if len(pr) else np.nan
        # O2: put nearest K/S 0.90 in [0.85, 0.95] minus mean call IV with K/S in [0.95, 1.05]
        pp = g[(g.type == "put") & (g.m >= 0.85) & (g.m <= 0.95)]
        cc = g[(g.type == "call") & (g.m >= 0.95) & (g.m <= 1.05)]
        o2 = (pp.iloc[(pp.m - 0.90).abs().argsort().iloc[0]].iv - cc.iv.mean()) if len(pp) and len(cc) else np.nan
        o3v = g.volume.sum()
        rows.append((u, d, o1, o2, o3v, g.s_vol.iloc[0]))
    O = pd.DataFrame(rows, columns=["ticker", "date", "o1", "o2", "optvol", "stockvol"])
    O.to_parquet(ODAILY)
    print(f"option bars with IV {len(B)}; name-days {len(O)}; names {O.ticker.nunique()}; O1 finite {O.o1.notna().mean():.0%}; "
          f"O2 finite {O.o2.notna().mean():.0%}; median IV {B.iv.median():.3f}; median O1 {O.o1.median():.4f}")


# ---------------------------------------------------------------------------------------------------------- panel
def weekly_mean(df, col, S, names, t, k=5, need=3):
    """Mean of the daily values over sessions t-k+1..t per name (>= need days), from a long frame (ticker, date, col)."""
    days = S[t - k + 1:t + 1]
    x = df[df.date.isin(days)]
    g = x.groupby("ticker")[col].agg(["mean", "count"])
    g = g[g["count"] >= need]["mean"]
    return pd.Series(g).reindex(names).to_numpy(dtype=float)


def build(fam, period, P=None):
    P = P if P is not None else RG.panel()
    S, names, n = P["S"], P["names"], len(P["S"])
    cr = np.vstack([np.zeros((1, len(names))), np.nancumsum(np.nan_to_num(P["e"]), 0)])
    last = int(np.searchsorted(S.values, np.datetime64(period[1]), side="right")) - 1
    dec = [t for t in range(260, n) if S[t].weekday() == 3 and S[t] >= period[0] and t + 6 <= last]
    if fam == "O":
        O = pd.read_parquet(ODAILY)
        O["os"] = 100 * O.optvol / O.stockvol
        O = O[O.date.isin(S)]
        keys = ("O1", "O2", "O3", "O4")
    else:
        F = pd.read_parquet(os.path.join(PN.CACHE, "finra_short.parquet"))
        F = F[F.date.isin(S) & F.ticker.isin(names)]
        Fs = F.pivot(index="date", columns="ticker", values="short").reindex(S).reindex(columns=names)
        Ft = F.pivot(index="date", columns="ticker", values="total").reindex(S).reindex(columns=names)
        cs = np.vstack([np.zeros((1, len(names))), np.nancumsum(Fs.to_numpy(), 0)])
        ct = np.vstack([np.zeros((1, len(names))), np.nancumsum(Ft.to_numpy(), 0)])
        cn = np.vstack([np.zeros((1, len(names))), np.cumsum(np.isfinite(Ft.to_numpy()), 0)])
        keys = ("F1", "F2")
    rows = {k: [] for k in keys}
    month = None
    for w, t in enumerate(dec):
        el = P["elig"][t] & np.isfinite(P["close"][t + 1])
        y = np.where(el, cr[t + 7] - cr[t + 2], np.nan)
        R, Rm = RG.hold_ret(P, t)
        sig = {}
        if fam == "O":
            if (S[t].year, S[t].month) != month:
                month = (S[t].year, S[t].month)
                tau = t
                while tau > 0 and (S[tau - 1].year, S[tau - 1].month) == month:
                    tau -= 1
                Wt, has = PN.text_kernel(names, S[tau])
            o1 = weekly_mean(O, "o1", S, names, t)
            sig["O1"] = o1
            sig["O2"] = weekly_mean(O, "o2", S, names, t)
            sig["O3"] = weekly_mean(O, "os", S, names, t)
            sig["O4"] = np.where(has, A.fld(Wt, np.where(has & el, o1, np.nan)), np.nan)
        else:
            sv = lambda a, b: np.where(cn[b + 1] - cn[a] >= 0.8 * (b - a + 1), (cs[b + 1] - cs[a]) / np.where(ct[b + 1] - ct[a] > 0, ct[b + 1] - ct[a], np.nan), np.nan)
            sig["F1"] = sv(t - 4, t) - sv(t - 64, t - 5)
            sig["F2"] = sv(t - 19, t)
        for k in keys:
            z = RG.zs(np.where(el, sig[k], np.nan))
            rows[k].append((w, t, z, y, R, Rm))
    return rows, P


def evaluate(rows, P, k, sign=None):
    blocks = [(np.full(len(z), w), y, z) for w, t, z, y, R, Rm in rows]
    b, tt, nobs = dk_t(blocks)
    sgn = sign if sign else (1 if b > 0 else -1)
    out = {"b": b, "t": tt, "n": nobs, "bp_per_sd": b * 1e4, "sign_used": sgn}
    for cn, c in (("2bp", 2e-4), ("5bp", 5e-4)):
        prev, net = None, []
        for w, t, z, y, R, Rm in rows:
            wts, h = RG.decile_book(sgn * z, P["beta"][t])
            g = float(np.nansum(wts * R) + h * Rm)
            to = 1.0 if prev is None else float(np.abs(wts - prev[0]).sum() + abs(h - prev[1]))
            prev = (wts, h)
            net.append(g - c * to)
        net = np.array(net)
        out[cn] = {"net_bp_wk": float(net.mean() * 1e4), "net_pct_yr": float((np.prod(1 + net) ** (52 / len(net)) - 1) * 100),
                   "sharpe": float(net.mean() / net.std(ddof=1) * np.sqrt(52)), "weeks": len(net)}
    out["names"] = float(np.mean([np.isfinite(z).sum() for _, _, z, *_ in rows]))
    return out


def ridge(rows_by_key, keys, signs, fit_rows=None, lam=1.0):
    """Ridge on the weekly z-scores (signed), fitted on fit_rows; returns weights."""
    X, Y = [], []
    for i in range(len(rows_by_key[keys[0]])):
        zs = np.column_stack([signs[k] * rows_by_key[k][i][2] for k in keys])
        y = rows_by_key[keys[0]][i][3]
        ok = np.all(np.isfinite(zs), 1) & np.isfinite(y)
        X.append(zs[ok]); Y.append(y[ok] - y[ok].mean())
    X, Y = np.vstack(X), np.concatenate(Y)
    return np.linalg.solve(X.T @ X + lam * len(Y) * 1e-4 * np.eye(len(keys)), X.T @ Y)


def combo_rows(rows_by_key, keys, signs, wts):
    out = []
    for i in range(len(rows_by_key[keys[0]])):
        w, t, _, y, R, Rm = rows_by_key[keys[0]][i]
        zs = np.column_stack([signs[k] * rows_by_key[k][i][2] for k in keys])
        s = np.where(np.all(np.isfinite(zs), 1), zs @ wts, np.nan)
        out.append((w, t, RG.zs(s), y, R, Rm))
    return out


def run(mode):
    res, rowsets = {}, {}
    for fam in ("O", "F"):
        rows, P = build(fam, PER[fam][mode])
        rowsets[fam] = (rows, P)
        for k in rows:
            res[k] = evaluate(rows[k], P, k, SIGN[k] or None)
    return res, rowsets


def table(r, title):
    L = [f"# Risk-field research, round 10 (options and short volume): {title}", "",
         "| Test | bp per sd (next week) | DK t | sign used | 2 bp: net %/yr | Sharpe | 5 bp: net %/yr | names | weeks |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for k, a in r.items():
        if not isinstance(a, dict) or "2bp" not in a:
            continue
        L.append(f"| {k} | {a['bp_per_sd']:.1f} | {a['t']:.2f} | {a['sign_used']:+d} | {a['2bp']['net_pct_yr']:.2f} | {a['2bp']['sharpe']:.2f} | "
                 f"{a['5bp']['net_pct_yr']:.2f} | {a['names']:.0f} | {a['2bp']['weeks']} |")
    return L


def dev():
    r, rowsets = run("dev")
    fin = []
    for k, a in list(r.items()):
        s = SIGN[k] if SIGN[k] else a["sign_used"]
        if s * a["t"] >= 1.5 and a["2bp"]["net_bp_wk"] > 0:
            fin.append(k)
        a["registered_sign"] = s
    combo = [k for k in ("O1", "O2", "O3", "O4") if (SIGN[k] * r[k]["t"]) >= 1.0]
    r["combo_O"] = {"members": combo}
    if len(combo) >= 2:
        rows, P = rowsets["O"]
        signs = {k: SIGN[k] for k in combo}
        w = ridge(rows, combo, signs)
        r["combo_O"]["weights"] = [float(x) for x in w]
        cr = combo_rows(rows, combo, signs, w)
        e = evaluate(cr, P, "combo", 1)
        r["combo_O"].update(e)
        if e["t"] >= 1.5 and e["2bp"]["net_bp_wk"] > 0:
            fin.append("combo_O")
    r["finalists"] = fin
    json.dump(r, open(os.path.join(HERE, "DEV10_RESULT.json"), "w"), indent=1, default=float)
    L = table(r, "development (options 2024-03..12; FINRA 2012-2019)")
    L += ["", f"Ridge combination of options signals with development |t| >= 1.0: {r['combo_O'].get('members')}" +
          (f", weights {r['combo_O'].get('weights')}, t {r['combo_O'].get('t', float('nan')):.2f}" if "t" in r["combo_O"] else " (fewer than two: not built)"),
          "", f"**Finalists:** {', '.join(fin) or 'none'}"]
    open(os.path.join(HERE, "DEV10_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def read():
    lock = os.path.join(HERE, "OOS10_READ.lock")
    if os.path.exists(lock):
        raise SystemExit("already read: " + open(lock).read())
    dv = json.load(open(os.path.join(HERE, "DEV10_RESULT.json")))
    fin = dv["finalists"]
    if not fin:
        raise SystemExit("no finalists: nothing to read")
    res_all, out = {}, {}
    for fam in ("O", "F"):
        keys = [k for k in fin if k.startswith(fam) or (fam == "O" and k == "combo_O")]
        if not keys:
            continue
        rows, P = build(fam, PER[fam]["oos"])
        for k in keys:
            if k == "combo_O":
                c = dv["combo_O"]
                signs = {m: SIGN[m] for m in c["members"]}
                out[k] = evaluate(combo_rows(rows, c["members"], signs, np.array(c["weights"])), P, k, 1)
            else:
                out[k] = evaluate(rows[k], P, k, dv[k]["registered_sign"])
            s = out[k]["sign_used"]
            res_all[k] = {"p": float(norm.sf(s * out[k]["t"])), "ok": out[k]["2bp"]["net_bp_wk"] > 0}
    holm(res_all)
    for k in res_all:
        res_all[k]["pass"] = bool(res_all[k]["p_holm"] < 0.05 and res_all[k]["ok"])
    at = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    json.dump({"read_at": at, "finalists": fin, "stats": out, "results": res_all}, open(os.path.join(HERE, "OOS10_RESULT.json"), "w"),
              indent=1, default=float)
    open(lock, "w").write(f"read {at}\n")
    L = table(out, f"out-of-sample read (one read, {at})") + ["", "Only finalists count.", ""] + [
        f"* **{k}**: p one-sided {v['p']:.4f}, Holm {v['p_holm']:.4f}, {'**pass**' if v['pass'] else 'fail'}" for k, v in res_all.items()]
    open(os.path.join(HERE, "OOS10_RESULT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"iv": iv, "dev": dev, "read": read}[sys.argv[1]]()
