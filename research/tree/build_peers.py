"""Phase 2, M5 data: text-peer graph aligned to the development panel (.cache/tree/extra_peers.npz).
For each calendar year y in 2010..2019 and each name: the 10 names whose latest 10-K Item 1 (filed before Jan 1 of y and
within 550 days) is most similar by TF-IDF cosine (vectors from research/riskfield/panel.py, vocabulary fitted on
2011-2015 10-Ks), with their cosines. Use year y's graph for sessions in year y."""
import os, sys
import numpy as np, pandas as pd, scipy.sparse as sp
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); import harness as H
RF = "/Users/apollogodofthesun/test_trading_agent/.claude/worktrees/riskfield/.cache"
D = H.load(); names = D["names"]
meta = pd.read_parquet(f"{RF}/riskfield/text_meta.parquet"); meta["filed"] = pd.to_datetime(meta.filed)
z = np.load(f"{RF}/riskfield/text_X.npz"); X = sp.csr_matrix((z["data"], z["indices"], z["indptr"]), shape=tuple(z["shape"]))
X = X.multiply(1 / np.sqrt(X.multiply(X).sum(1)).clip(1e-12)).tocsr()
ev = pd.read_parquet(f"{RF}/p8/events.parquet"); t2c = ev.dropna(subset=["cik"]).groupby("ticker").cik.last().astype(int).to_dict()
YEARS = range(2010, 2020); K = 10
nb = np.full((len(YEARS), len(names), K), -1, np.int32); w = np.zeros((len(YEARS), len(names), K), np.float32)
for a, y in enumerate(YEARS):
    cut = pd.Timestamp(f"{y}-01-01")
    m = meta[(meta.filed < cut) & (meta.filed >= cut - pd.Timedelta(days=550))].sort_values("filed").groupby("cik").tail(1)
    row = dict(zip(m.cik, m.index))
    cols = [j for j, n in enumerate(names) if t2c.get(n) in row]
    if len(cols) < 20: continue
    V = X[[row[t2c[names[j]]] for j in cols]]
    C = (V @ V.T).toarray(); np.fill_diagonal(C, -1)
    top = np.argsort(-C, 1)[:, :K]
    for r, j in enumerate(cols):
        nb[a, j] = np.array(cols)[top[r]]; w[a, j] = C[r, top[r]]
    print(y, "names with a 10-K vector:", len(cols))
np.savez_compressed(os.path.join(ROOT, ".cache", "tree", "extra_peers.npz"), years=np.array(list(YEARS)), neighbours=nb, cosine=w,
    note=np.array("Text-peer graph: neighbours[a, j] = column indices (into load()['names']) of name j's 10 nearest names by 10-K Item 1 TF-IDF cosine, for calendar year years[a] (10-Ks filed before Jan 1 of that year, within 550 days); -1 = no vector. cosine[a, j] = their similarities. Use year y's graph for sessions in year y."))
