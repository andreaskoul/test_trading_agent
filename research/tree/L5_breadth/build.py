"""L5 breadth: freeze the parsed 13F holdings into one compact parquet (sha256) and build the weekly change-in-breadth
score aligned to a panel (dev.npz by default). Rules: STATE.json plan.

    OMP_NUM_THREADS=3 python3 research/tree/L5_breadth/build.py freeze
    OMP_NUM_THREADS=3 python3 research/tree/L5_breadth/build.py score
"""
import glob
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import sparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
C5 = os.path.join(ROOT, ".cache", "tree", "l5breadth")
HOLD = os.path.join(C5, "holdings.parquet")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def freeze(pattern="*.parquet", out=HOLD):
    fs = sorted(glob.glob(os.path.join(C5, "parsed", pattern)))
    h = pd.concat([pd.read_parquet(f).assign(src=os.path.basename(f)[:-8]) for f in fs], ignore_index=True)
    first = h.groupby(["filer", "period"]).filing_date.transform("min")
    h = h[h.filing_date == first]
    # one report per (filer, period): if two files carry the same earliest date, keep the first file's rows
    src0 = h.groupby(["filer", "period"]).src.transform("min")
    h = h[h.src == src0].drop(columns="src").drop_duplicates()
    h = h.sort_values(["period", "filer", "issuer"]).reset_index(drop=True)
    h["period"] = h.period.astype("datetime64[ms]")
    h["filing_date"] = h.filing_date.astype("datetime64[ms]")
    h.to_parquet(out, index=False, compression="zstd")
    mp = os.path.join(C5, "MANIFEST.json")
    man = json.load(open(mp))
    man[os.path.basename(out)] = {"sha256": sha(out), "rows": len(h), "files": [os.path.basename(f) for f in fs],
                                  "periods": sorted({str(p.date()) for p in h.period.unique()})}
    json.dump(man, open(mp, "w"), indent=1)
    print(os.path.basename(out), len(h), "rows", man[os.path.basename(out)]["sha256"])


def weekly_score(S, names, rows, hold=HOLD, ticker_cik=None, min_share=0.5):
    """(len(S), len(names)) float array, finite on `rows` where the name's issuer has a score."""
    PN = json.load(open(os.path.join(C5, "panel_names.json")))
    t2c = ticker_cik or {k: int(v) for k, v in PN["ticker_cik"].items()}
    h = pd.read_parquet(hold)
    if sha(hold) != json.load(open(os.path.join(C5, "MANIFEST.json")))[os.path.basename(hold)]["sha256"]:
        raise SystemExit("holdings parquet sha256 mismatch")
    filers = np.sort(h.filer.unique())
    issuers = np.sort(h.issuer[h.issuer >= 0].unique())
    fi = pd.Series(np.arange(len(filers)), index=filers)
    ii = pd.Series(np.arange(len(issuers)), index=issuers)
    periods = sorted(h.period.unique())
    H, FD = {}, {}
    for p in periods:
        g = h[h.period == p]
        rep = g[g.issuer == -1]
        fd = np.full(len(filers), np.datetime64("NaT"), dtype="datetime64[ms]")
        fd[fi[rep.filer].values] = rep.filing_date.values
        FD[pd.Timestamp(p)] = fd
        x = g[g.issuer >= 0]
        H[pd.Timestamp(p)] = sparse.csr_matrix((np.ones(len(x), np.float32), (fi[x.filer].values, ii[x.issuer].values)),
                                               shape=(len(filers), len(issuers)))
    qs = sorted(H)
    col = {}
    for j, n in enumerate(names):
        c = t2c.get(n)
        if c is not None and c in ii.index:
            col.setdefault(int(ii[c]), []).append(j)
    out = np.full((len(S), len(names)), np.nan)
    info = []
    for t in rows:
        d = np.datetime64(pd.Timestamp(S[t]).normalize(), "ms")
        prior = [q for q in qs if np.datetime64(q, "ms") < d]
        use = None
        for k in range(len(prior) - 1, 0, -1):
            p, pm = prior[k], prior[k - 1]
            if (p - pm).days > 95:
                continue
            A, B = FD[p] < d, FD[pm] < d                 # NaT compares False
            F = A & B
            if B.sum() and F.sum() >= min_share * B.sum():
                use = (p, pm, F)
                break
        if use is None:
            info.append({"t": str(S[t].date()), "period": None})
            continue
        p, pm, F = use
        f = F.astype(np.float32)
        a, b = f @ H[p], f @ H[pm]
        a, b = np.asarray(a).ravel(), np.asarray(b).ravel()
        db = (a - b) / F.sum()
        ok = (a > 0) & (b > 0)
        for i, js in col.items():
            if ok[i]:
                out[t, js] = db[i]
        info.append({"t": str(S[t].date()), "period": str(p.date()), "n_filers": int(F.sum()), "n_issuers_scored": int(ok.sum())})
    return out, info


def score_dev():
    sys.path.insert(0, os.path.dirname(HERE))
    import harness as H
    D = H.load()
    rows = np.concatenate([H.thursdays(D, y) for y in range(2013, 2020)])
    rows = rows[D["S"][rows] >= pd.Timestamp("2013-10-01")]
    sc, info = weekly_score(D["S"], D["names"], rows)
    np.save(os.path.join(C5, "score_dev.npy"), sc.astype(np.float32))
    json.dump(info, open(os.path.join(C5, "score_dev_info.json"), "w"), indent=0)
    print("score_dev.npy written;", sum(1 for x in info if x["period"]), "of", len(info), "Thursdays scored")


if __name__ == "__main__":
    {"freeze": freeze, "score": score_dev}[sys.argv[1]]()
