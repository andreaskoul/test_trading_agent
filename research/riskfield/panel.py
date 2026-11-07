"""Risk-field research (research/riskfield/PREREG.md): data panels. No statistic is computed here.

    python research/riskfield/panel.py bars     # 30-minute bars -> .cache/riskfield/hf.npz (RV, RQ, 14 returns a day)
    python research/riskfield/panel.py text     # 10-K Item 1 TF-IDF vectors -> .cache/riskfield/text_*.npz
    python research/riskfield/panel.py news     # 31-name news unusualness -> .cache/riskfield/news.npz

Nothing after 2025-12-31 is read.
"""
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, ".cache", "riskfield")
QT = os.path.join(ROOT, ".cache", "quant_trials")
P8 = os.path.join(ROOT, ".cache", "p8")
BARS = os.environ.get("RF_BARS", os.path.expanduser("~/Stock2Vec-agentic-refactor/data/raw/bars_20160101.parquet"))
END = pd.Timestamp("2025-12-31")
HF = os.path.join(CACHE, "hf.npz")


# ------------------------------------------------------------------------------------------------------- intraday
def bars():
    """Regular-session 30-minute bars -> per session and name: 13 intraday log returns and the overnight return."""
    b = pd.read_parquet(BARS, columns=["timestamp", "ticker", "open", "close"],
                        filters=[("timestamp", "<", pd.Timestamp("2026-01-01", tz="UTC"))])
    et = b.pop("timestamp").dt.tz_convert("America/New_York")
    mins = et.dt.hour * 60 + et.dt.minute - 570
    b = b[(mins >= 0) & (mins <= 360) & (mins % 30 == 0)].copy()
    b["k"] = (mins[b.index] // 30).astype(int)
    b["date"] = et[b.index].dt.tz_localize(None).dt.normalize()
    b = b[b.date <= END]
    full = b.groupby(["date", "ticker"]).k.transform("size") == 13
    b = b[full]
    names = sorted(b.ticker.unique())
    spy_days = np.sort(b.loc[b.ticker == "SPY", "date"].unique())
    S = pd.DatetimeIndex(spy_days)
    di = S.get_indexer(b.date)
    b = b[di >= 0]
    di = di[di >= 0]
    ni = pd.Index(names).get_indexer(b.ticker)
    C = np.full((len(S), 13, len(names)), np.nan)
    C[di, b.k.to_numpy(), ni] = np.log(b.close.to_numpy())
    O = np.full((len(S), len(names)), np.nan)
    o = b.k.to_numpy() == 0
    O[di[o], ni[o]] = np.log(b.open.to_numpy()[o])
    R = np.empty((len(S), 14, len(names)))
    R[:, 0] = O - np.vstack([np.full((1, len(names)), np.nan), C[:-1, 12]])     # overnight
    R[:, 1] = C[:, 0] - O
    R[:, 2:] = np.diff(C, axis=1)
    bad = np.any(np.abs(R[:, 1:]) > 0.4, axis=1) | (np.abs(R[:, 0]) > 0.4)
    R[np.broadcast_to(bad[:, None, :], R.shape)] = np.nan
    rv = np.where(np.isfinite(R).all(1), (R ** 2).sum(1), np.nan)
    rq = np.where(np.isfinite(rv), 13 / 3 * (R[:, 1:] ** 4).sum(1), np.nan)
    rv = np.where(rv > 0, rv, np.nan)
    np.savez_compressed(HF, S=S.values.astype("datetime64[D]"), names=np.array(names), R=R.astype(np.float32),
                        rv=rv, rq=rq, defects=bad.sum(0))
    cov = np.isfinite(rv).sum(1)
    print(f"{len(S)} sessions {S[0].date()}..{S[-1].date()}, {len(names)} names; name-days valid per session: "
          f"median {np.median(cov):.0f}, min {cov.min()} on {S[int(cov.argmin())].date()}; defects {int(bad.sum())}")


def load_hf():
    z = np.load(HF, allow_pickle=False)
    return {k: z[k] for k in z.files} | {"S": pd.DatetimeIndex(z["S"])}


# ------------------------------------------------------------------------------------------------------------ text
TOK = re.compile(r"[a-z]{3,}")


def _item1(f):
    sys.path.insert(0, os.path.join(ROOT, "research", "p8"))
    import sections as SE                                                            # noqa: E402
    t = SE.load(f["cik"], f["accession"])
    if t is None:
        return None
    s = SE.extract(t, "10-K").get("1")
    if s is None or len(s) < 2000:
        return None
    return f["cik"], f["accession"], f["filed"], " ".join(TOK.findall(s.lower()))


def text():
    """Every cached 10-K's Item 1 as a TF-IDF vector; vocabulary and idf fitted on 10-Ks filed 2011-2015 only."""
    from scipy import sparse
    from sklearn.feature_extraction.text import TfidfVectorizer
    idx = [f for f in json.load(open(os.path.join(P8, "edgar", "filings_text_index.json")))
           if f["form"] == "10-K" and f["filed"] <= str(END.date())]
    with ProcessPoolExecutor(8) as ex:
        got = [g for g in ex.map(_item1, idx, chunksize=20) if g is not None]
    meta = pd.DataFrame([g[:3] for g in got], columns=["cik", "accession", "filed"])
    docs = [g[3] for g in got]
    fit = (meta.filed >= "2011-01-01") & (meta.filed <= "2015-12-31")
    vec = TfidfVectorizer(min_df=5, max_df=0.5, sublinear_tf=True, token_pattern=r"[a-z]{3,}", dtype=np.float32)
    vec.fit([d for d, f in zip(docs, fit) if f])
    X = vec.transform(docs)
    sparse.save_npz(os.path.join(CACHE, "text_X.npz"), X.tocsr())
    meta.to_parquet(os.path.join(CACHE, "text_meta.parquet"))
    print(f"10-Ks in index {len(idx)}, Item 1 extracted {len(got)}, fitted on {int(fit.sum())} (2011-2015); "
          f"vocabulary {len(vec.vocabulary_)}; firms {meta.cik.nunique()}")


def ticker_cik():
    c = json.load(open(os.path.join(P8, "edgar", "ciks.json")))
    return {t: v["cik"] for t, v in c.items() if v.get("cik")}


def text_kernel(names, t_date, k=10, cache={}):
    """Text kernel at t_date among `names`: each name's latest 10-K Item 1 filed <= t_date - 1 day and within 550
    days; top-k cosine neighbours, weights proportional to cosine. Returns (rows, cols, weights) and has-vector mask."""
    from scipy import sparse
    if "X" not in cache:
        cache["X"] = sparse.load_npz(os.path.join(CACHE, "text_X.npz"))
        m = pd.read_parquet(os.path.join(CACHE, "text_meta.parquet"))
        m["filed"] = pd.to_datetime(m.filed)
        cache["meta"] = m.reset_index(drop=True)
        cache["tc"] = ticker_cik()
    X, meta, tc = cache["X"], cache["meta"], cache["tc"]
    lo, hi = t_date - pd.Timedelta(days=550), t_date - pd.Timedelta(days=1)
    m = meta[(meta.filed >= lo) & (meta.filed <= hi)].sort_values("filed").groupby("cik").tail(1)
    row_of = dict(zip(m.cik, m.index))
    rows = np.array([row_of.get(tc.get(n), -1) for n in names])
    has = rows >= 0
    # one CIK can map to two share classes (GOOG/GOOGL): they are each other's neighbours, which is right
    V = X[rows[has]]
    Sm = (V @ V.T).toarray()
    np.fill_diagonal(Sm, -np.inf)
    idx = np.where(has)[0]
    W = np.zeros((len(names), len(names)))
    kk = min(k, len(idx) - 1)
    top = np.argpartition(-Sm, kk - 1, axis=1)[:, :kk]
    for a, js in enumerate(top):
        s = np.maximum(Sm[a, js], 0)
        if s.sum() > 0:
            W[idx[a], idx[js]] = s / s.sum()
    return W, has


# ------------------------------------------------------------------------------------------------------------ news
def news():
    """31 names: per session, article count and unusualness u = 1 - cos(today's mean embedding, the mean embedding
    of the name's news over sessions t-63..t-1); 0 on no-news days (and when there is no earlier news)."""
    H = load_hf()
    S = H["S"]
    out_n, out_u, names = [], [], []
    for f in sorted(os.listdir(os.path.join(QT, "text"))):
        if not f.endswith("_dedup.npz"):
            continue
        tk = f.split("_")[0]
        z = np.load(os.path.join(QT, "text", f))
        ses = pd.DatetimeIndex(z["session"])
        keep = ses <= END
        ses, n, sm = ses[keep], z["n"][keep], z["sum"][keep]
        ix = S.get_indexer(ses)
        N = np.zeros(len(S))
        E = np.zeros((len(S), sm.shape[1]), dtype=np.float32)
        ok = ix >= 0
        N[ix[ok]] = n[ok]
        E[ix[ok]] = sm[ok]
        cs = np.vstack([np.zeros((1, E.shape[1]), dtype=np.float64), np.cumsum(E, 0, dtype=np.float64)])
        cn = np.r_[0, np.cumsum(N)]
        u = np.zeros(len(S))
        for t in np.where(N > 0)[0]:
            a = max(0, t - 63)
            k = cn[t] - cn[a]
            if k <= 0:
                continue
            past = (cs[t] - cs[a]) / k
            today = E[t] / N[t]
            u[t] = 1 - float(today @ past / (np.linalg.norm(today) * np.linalg.norm(past)))
        out_n.append(N)
        out_u.append(u)
        names.append(tk)
    np.savez_compressed(os.path.join(CACHE, "news.npz"), names=np.array(names), n=np.column_stack(out_n),
                        u=np.column_stack(out_u), S=S.values.astype("datetime64[D]"))
    first = [S[int(np.argmax(c > 0))].date() for c in out_n]
    print(f"{len(names)} names; first news session from {min(first)} to {max(first)}; "
          f"news name-days {int(sum((c > 0).sum() for c in out_n))}")


if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True)
    {"bars": bars, "text": text, "news": news}[sys.argv[1]]()
