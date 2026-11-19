"""Layer 5 branch I: CIK verification, coverage, dating and the opportunistic insider signal (plan in STATE.json)."""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, ".cache", "tree", "l5insider")


def nt(x):
    return str(x).upper().replace(".", "").replace("-", "").replace("/", "").replace(" ", "").strip()


def load_raw():
    F = pd.read_parquet(os.path.join(OUT, "filings.parquet"))
    T = pd.read_parquet(os.path.join(OUT, "trades.parquet"))
    return F, T


def verify_ciks(names, S, elig, F):
    """Return {name: cik or None} and a decision table. Span = sessions where the name is eligible."""
    c = json.load(open(os.path.join(ROOT, ".cache", "p8", "edgar", "ciks.json")))
    out, rows = {}, []
    for j, n in enumerate(names):
        e = np.where(elig[:, j])[0]
        if len(e) == 0:
            out[n] = None
            rows.append({"name": n, "decision": "never eligible", "cik": None})
            continue
        a, b = S[e[0]], S[e[-1]]
        inspan = F[(F.filing_date >= a) & (F.filing_date <= b)]
        cik0 = c.get(n, {}).get("cik")
        how = c.get(n, {}).get("how")
        tk = inspan[inspan.sym == nt(n)]
        dom = tk.cik.value_counts()
        mine = inspan[inspan.cik == cik0] if cik0 else inspan.iloc[:0]
        share = float((mine.sym == nt(n)).mean()) if len(mine) else float("nan")
        r = {"name": n, "map_cik": cik0, "map_how": how, "span": [str(a.date()), str(b.date())],
             "map_cik_filings_in_span": int(len(mine)), "map_cik_symbol_match_share": share,
             "ticker_filings_in_span": int(len(tk)),
             "ticker_top_cik": int(dom.index[0]) if len(dom) else None,
             "ticker_top_cik_share": float(dom.iloc[0] / len(tk)) if len(dom) else None,
             "map_cik_top_symbols": mine.sym.value_counts().head(3).to_dict()}
        if cik0 and len(mine) and share >= 0.5:
            r.update(decision="verified", cik=int(cik0))
        elif len(dom) and dom.iloc[0] / len(tk) >= 0.8 and dom.iloc[0] >= 20 and (not cik0 or int(dom.index[0]) != int(cik0)):
            r.update(decision="switched to ticker's CIK", cik=int(dom.index[0]))
        elif cik0 and len(mine):
            r.update(decision="kept, symbol differs (rename?)", cik=int(cik0))
        else:
            r.update(decision="defect: no filings in span", cik=None)
        out[n] = r["cik"]
        rows.append(r)
    return out, rows


def public_index(S, dates):
    """Index of the first session strictly after each filing date (conservative 16:00 rule); len(S) if none."""
    return np.searchsorted(S.values, pd.DatetimeIndex(dates).values, side="right")


def opportunistic(T):
    """Flag routine trades: the insider-issuer pair has P/S trades in the same calendar month of each of the 3 prior
    years, in filings filed strictly before this trade's filing date."""
    T = T.dropna(subset=["trans_date", "owner", "cik"]).copy()
    T["y"], T["m"] = T.trans_date.dt.year, T.trans_date.dt.month
    first = T.groupby(["owner", "cik", "y", "m"]).filing_date.min().rename("fd_prev").reset_index()
    T["routine"] = True
    for k in (1, 2, 3):
        f = first.assign(y=first.y + k)
        x = T[["owner", "cik", "y", "m"]].merge(f, on=["owner", "cik", "y", "m"], how="left").fd_prev.values
        T["routine"] &= pd.notna(x) & (x < T.filing_date.values)
    return T


def accession_flows(T):
    """Per accession (opportunistic trades only): net value (P dollars - S dollars), net shares, sign for the count."""
    o = T[~T.routine].copy()
    sgn = np.where(o.code == "P", 1.0, -1.0)
    o["val"] = sgn * o.shares.fillna(0) * o.price.fillna(0)
    o["sh"] = sgn * o.shares.fillna(0)
    g = o.groupby(["acc", "cik", "filing_date"]).agg(val=("val", "sum"), sh=("sh", "sum")).reset_index()
    g["cnt"] = np.sign(np.where(g.val != 0, g.val, g.sh))
    return g


def components(S, names, cikmap, G, rows):
    """count/value over the last 21 and 63 sessions, at prediction rows; 0 for a verified CIK with no trades, NaN for
    no CIK."""
    n = len(names)
    pidx = public_index(S, G.filing_date)
    G = G.assign(p=pidx)
    G = G[G.p < len(S)]
    cols = {}
    for c, grp in G.groupby("cik"):
        cols[int(c)] = grp
    out = {k: np.full((len(rows), n), np.nan) for k in ("cnt1", "cnt3", "val1", "val3")}
    for j, nm in enumerate(names):
        c = cikmap.get(nm)
        if c is None:
            continue
        for k in out:
            out[k][:, j] = 0.0
        g = cols.get(int(c))
        if g is None:
            continue
        cc = np.zeros(len(S) + 1)
        vv = np.zeros(len(S) + 1)
        np.add.at(cc, g.p.values + 1, g.cnt.values)
        np.add.at(vv, g.p.values + 1, g.val.values)
        cc, vv = np.cumsum(cc), np.cumsum(vv)              # cc[i] = sum over p < i
        for L, s in ((21, "1"), (63, "3")):
            hi = rows + 1
            lo = np.maximum(rows + 1 - L, 0)
            out["cnt" + s][:, j] = cc[hi] - cc[lo]
            out["val" + s][:, j] = vv[hi] - vv[lo]
    return out
