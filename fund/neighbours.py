"""Amendment 6 · Neighbourhood (shadow; fund/AMENDMENT6_PLAN.md). No LLM. -> neighbours.json

For every covered name, the news that may reach it through other firms, from data the fund already has:
  * neighbours: the 5 S&P 500 firms most often in the same articles over the 91 days to the cutoff
    (same article id in both firms' Finnhub feeds, or both in an article's ticker tags; articles tagged
    to more than 10 firms are lists or market wraps and are dropped), weighted n_ab / sqrt(n_a n_b) so
    megacaps don't link to everything; each with its 3 latest headlines of the 7 days to the cutoff;
  * the same GICS sub-industry: one latest headline each from up to 5 other members, most unusual
    news flow (attention shock) first;
  * the firm's own SEC 8-K filings accepted in the 14 days to the cutoff (context archive).
Rendered as one block of at most ~3,200 characters per name.
"""

import glob
import itertools
import json
import os
import re
import subprocess

import numpy as np
import pandas as pd

from a6_common import filings, load_context
from common import MOCK, ROOT, asof_from_env, load, news_cutoff, save

asof = asof_from_env()
cutoff = news_cutoff(asof)
lo91, lo7 = cutoff - pd.Timedelta(days=91), cutoff - pd.Timedelta(days=7)
S = pd.DataFrame(load(asof, "screen.json")["rows"]).set_index("ticker")
cov = load(asof, "ideation.json")["coverage"]
universe = set(S.index)
COLS = ["sym", "src", "id", "t", "tickers", "publisher", "published"]

# ---- the S&P 500 news archive (fund/archive.py); in mock mode the dashboard's 20 feeds
if MOCK:
    site = os.path.join(ROOT, ".cache", "my-website")
    rows = []
    for f in glob.glob(os.path.join(site, "data", "raw", "*.jsonl")):
        rows += [dict(json.loads(l), sym=os.path.basename(f)[:-6]) for l in open(f)]
    A = pd.DataFrame(rows).reindex(columns=COLS)
    if A.empty:                                              # dashboard not checked out: build from git
        r = subprocess.run(["git", "-C", site, "ls-tree", "--name-only", "origin/HEAD", "data/raw/"], capture_output=True, text=True)
        for f in r.stdout.split():
            out = subprocess.run(["git", "-C", site, "show", f"origin/HEAD:{f}"], capture_output=True, text=True).stdout
            rows += [dict(json.loads(l), sym=f.split("/")[-1][:-6]) for l in out.splitlines() if l.strip()]
        A = pd.DataFrame(rows).reindex(columns=COLS)
else:
    from huggingface_hub import HfApi, snapshot_download
    api = HfApi(token=os.environ["HF_TOKEN"])
    repo = f"{api.whoami()['name']}/fund-news-archive"
    days = {str(d.date()) for d in pd.date_range(lo91.normalize(), cutoff.normalize())}
    want = [f for f in api.list_repo_files(repo, repo_type="dataset") if f.startswith("days/") and f[5:15] in days]
    d_ = snapshot_download(repo, repo_type="dataset", allow_patterns=want, local_dir=os.path.join(ROOT, "fund_archive"),
                           token=os.environ["HF_TOKEN"])
    A = pd.concat([pd.read_parquet(os.path.join(d_, f), columns=COLS) for f in want]) if want else pd.DataFrame(columns=COLS)
pub = pd.to_datetime(A["published"], utc=True, errors="coerce").dt.tz_localize(None)
A = A.assign(pub=pub)[(pub > lo91) & (pub <= cutoff)]
A["art"] = A["src"].astype(str) + ":" + A["id"].astype(str)
print(f"neighbours: {len(A)} archive rows, {A['art'].nunique()} articles, {A['sym'].nunique()} firms")

# ---- links: firms per article (feeds it appears in + its ticker tags), then pair counts
tags = A[["art", "tickers"]].explode("tickers").rename(columns={"tickers": "sym"})
M = pd.concat([A[["art", "sym"]], tags]).dropna().drop_duplicates()
M = M[M["sym"].isin(universe)]
size = M.groupby("art")["sym"].transform("size")
M = M[(size >= 2) & (size <= 10)]
n_a = pd.concat([A[["art", "sym"]], tags]).dropna().drop_duplicates().groupby("sym").size()     # same union as the links
pairs = pd.Series([p for g in M.groupby("art")["sym"] for p in itertools.combinations(sorted(g[1]), 2)], dtype=object).value_counts()
W = pd.DataFrame([(a, b, n) for (a, b), n in pairs.items() if n >= 3], columns=["a", "b", "n"])
if len(W):
    W["w"] = W["n"] / np.sqrt(W["a"].map(n_a).fillna(1) * W["b"].map(n_a).fillna(1))
    W = pd.concat([W, W.rename(columns={"a": "b", "b": "a"})])
# a headline counts for a firm only if it names it (short name or ticker, as research.py matches firms):
# Finnhub feeds carry many generic "stocks to buy" items under every symbol
SUFFIX = r"\b(incorporated|inc|corporation|corp|company|co|holdings?|group|plc|ltd|limited|the|class [a-z]|n\.?v|s\.?a)\b\.?"
def pat(t):
    core = re.sub(r"\s+", " ", re.sub(SUFFIX, "", re.sub(r"\(.*?\)|[,.]", " ", str(S["Security"].get(t, t)).lower()))).strip()
    alts = ([re.escape(core) if len(core) >= 5 else rf"\b{re.escape(core)}\b"] if core else []) + ([rf"\b{re.escape(t)}\b"] if len(t) >= 3 else [])
    return re.compile("|".join(alts) or "$^", re.I)
week = A[A["pub"] > lo7].sort_values("pub", ascending=False).drop_duplicates(["sym", "t"])
heads = {s: [f"{p:%Y-%m-%d} {pb}: {t}" for p, pb, t in zip(g["pub"], g["publisher"], g["t"]) if pat(s).search(str(t))]
         for s, g in week.groupby("sym")}
C = load_context(cutoff - pd.Timedelta(days=15), cutoff)
shock = pd.to_numeric(S.get("attention_shock"), errors="coerce")

issuer = S["Security"].astype(str).str.replace(r"\s*\(.*?\)", "", regex=True).str.strip()   # one share class per issuer
out = {}
for t in cov:
    nb = W[W["a"] == t].sort_values("w", ascending=False) if len(W) else W
    if len(nb):
        iss = nb["b"].map(lambda b: issuer.get(b, b))
        nb = nb[(iss != issuer.get(t, t)) & ~iss.duplicated()].head(5)
    sub = S["GICS Sub-Industry"].get(t) if t in S.index else None
    peers = [p for p in shock.reindex(S.index[S["GICS Sub-Industry"] == sub]).sort_values(ascending=False).index
             if p != t and p not in set(nb["b"]) and heads.get(p)][:5] if sub else []
    fl = filings(C, t, cutoff - pd.Timedelta(days=14), cutoff)
    lines = ["NEIGHBOURHOOD (firms most often in the same articles over 13 weeks; their news in the 7 days to the cutoff):"]
    for b, w in zip(nb["b"], nb["w"]):
        lines += [f"- {b} ({S['Security'].get(b, b)}, link {w:.2f}):"] + [f"    {h}" for h in heads.get(b, [])[:3]] \
            + ([] if heads.get(b) else ["    no news this week"])
    if nb.empty:
        lines.append("- none with enough shared coverage")
    lines += [f"SAME SUB-INDUSTRY ({sub or 'n/a'}), this week:"] + ([f"- {p}: {heads[p][0]}" for p in peers] or ["- none"])
    lines += ["SEC 8-K FILINGS by this firm, 14 days to the cutoff:"] + (
        [f"- {x['accepted']} {x['form']}: {', '.join(x['items'])}" for x in fl] or ["- none"])
    text = "\n".join(lines)
    out[t] = {"neighbours": [{"ticker": b, "w": round(float(w), 4), "n": int(n)} for b, w, n in zip(nb["b"], nb["w"], nb["n"])],
              "subindustry": peers, "filings": fl, "text": text[:3200]}
save(asof, "neighbours.json", {"asof": str(asof.date()), "cutoff": str(cutoff), "n_links": int(len(W) // 2), "names": out})
print(f"neighbours: {len(W) // 2} links; {sum(bool(v['neighbours']) for v in out.values())}/{len(out)} covered names with neighbours, "
      f"{sum(bool(v['filings']) for v in out.values())} with 8-Ks; median block {int(np.median([len(v['text']) for v in out.values()]))} chars")
