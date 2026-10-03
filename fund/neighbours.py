"""Shadow desk · neighbourhood (PROTOCOL_fund.md, Amendment 6). No LLM. -> neighbours.json

For each covered name, what its peers did in the week to the cutoff:
* co-mention graph over the S&P 500 news archive, 91 days to the cutoff: an edge counts distinct
  articles (Finnhub article id) filed under both firms; round-ups filed under more than 10 firms say
  nothing about peers and are left out; a name's neighbours are ranked by that count over its own
  article count; top 5 with >= 3 shared articles;
* up to 3 deduplicated headlines per neighbour from the 7 days to the cutoff;
* up to 5 headlines from the rest of its GICS sub-industry in the same 7 days;
* its own 8-K filings accepted in those 7 days (context archive), items in plain words.
The text block per name is cut deterministically to 3,200 characters (about 800 tokens).
"""

import re

import pandas as pd

import infoflow
from common import asof_from_env, load, news_cutoff, require, save

require("HF_TOKEN")
asof = asof_from_env()
cutoff = news_cutoff(asof).tz_localize("UTC")
S = pd.DataFrame(load(asof, "screen.json")["rows"]).set_index("ticker")
cov = [t for t in load(asof, "ideation.json")["coverage"] if t in S.index]
members = set(S.index)
TOP, MIN_SHARED, PER_NB, SUB_N, CHARS, ROUNDUP = 5, 3, 3, 5, 3200, 10
ITEMS = {"1.01": "material agreement", "1.02": "agreement terminated", "1.03": "bankruptcy", "1.05": "cybersecurity incident",
         "2.01": "acquisition or disposal completed", "2.02": "results of operations", "2.03": "new debt obligation",
         "2.04": "debt acceleration", "2.05": "exit or restructuring costs", "2.06": "impairment",
         "3.01": "delisting notice", "3.02": "unregistered equity sale", "3.03": "change to holders' rights",
         "4.01": "auditor change", "4.02": "prior financials unreliable", "5.01": "change in control",
         "5.02": "officer or director change", "5.03": "bylaws or fiscal year change", "5.07": "shareholder vote",
         "7.01": "Reg FD disclosure", "8.01": "other events", "9.01": "exhibits"}

A = infoflow.news(cutoff - pd.Timedelta(days=91), cutoff)
A = A[A["sym"].isin(members)]
n_art = A.groupby("sym")["id"].nunique()
pairs = {}
for aid, syms in A.groupby("id")["sym"].agg(lambda s_: sorted(set(s_))).items():
    if 1 < len(syms) <= ROUNDUP:
        for x in syms:
            for y in syms:
                if x != y:
                    pairs[(x, y)] = pairs.get((x, y), 0) + 1
shared = pd.Series(pairs, dtype=float)
week = A[A["published"] > cutoff - pd.Timedelta(days=7)].sort_values("published", ascending=False)
norm = lambda s: re.sub(r"[^a-z0-9 ]", "", str(s).lower()).strip()


def headlines(rows, n):
    out, seen = [], set()
    for pub, sym, t in zip(rows["published"], rows["sym"], rows["t"]):
        k = norm(t)
        if t and k not in seen:
            seen.add(k); out.append(f"{pub:%m-%d} {sym}: {t}")
        if len(out) >= n:
            break
    return out


E = infoflow.context(cutoff, sources=["edgar"])
E = E.assign(acc=pd.to_datetime(E["published_at"], utc=True, errors="coerce"))
E = E[(E["acc"] > cutoff - pd.Timedelta(days=7)) & (E["acc"] <= cutoff)]
out = {}
for t in cov:
    nb = []
    if len(shared) and t in shared.index.get_level_values(0):
        s_ = shared.loc[t]
        s_ = s_[s_ >= MIN_SHARED] / n_art.get(t, 1)
        nb = list(s_.sort_values(ascending=False).head(TOP).index)
    sub = S.loc[t, "GICS Sub-Industry"] if "GICS Sub-Industry" in S else None
    peers = [x for x in S.index[S["GICS Sub-Industry"] == sub] if x != t] if sub is not None else []
    peer_week = week[~week["id"].isin(set(A.loc[A["sym"] == t, "id"]))]     # articles about the name itself are not peer news
    nb_heads = {x: headlines(peer_week[peer_week["sym"] == x], PER_NB) for x in nb}
    sub_heads = headlines(peer_week[peer_week["sym"].isin([p for p in peers if p not in nb])], SUB_N)
    fil = [{"accepted": f"{a:%Y-%m-%d %H:%M}", "form": p["form"],
            "items": [f"{i} {ITEMS.get(i, 'item')}" for i in str(p.get("items") or "").split(",") if i]}
           for a, p in zip(E["acc"], E["payload"]) if p.get("ticker") == t]
    lines = [f"NEIGHBOURHOOD of {t} (7 days to the cutoff):"]
    for x in nb:
        lines.append(f"- {x} ({S.loc[x, 'Security']}; {int(shared[(t, x)])} articles shared over 91 days):")
        lines += [f"    {h}" for h in nb_heads[x]] or ["    no headlines this week"]
    lines.append(f"- Sub-industry ({sub}): " + ("" if sub_heads else "no headlines this week"))
    lines += [f"    {h}" for h in sub_heads]
    lines.append("- Own 8-K filings: " + ("; ".join(f"{f['accepted']} {f['form']} ({', '.join(f['items'])})" for f in fil) or "none"))
    text = "\n".join(lines)
    out[t] = {"neighbours": [{"ticker": x, "shared_articles": int(shared[(t, x)]), "headlines": nb_heads[x]} for x in nb],
              "sub_industry": sub, "sub_industry_headlines": sub_heads, "filings": fil,
              "text": text if len(text) <= CHARS else text[:CHARS - 12] + "\n[truncated]"}
save(asof, "neighbours.json", {"asof": str(asof.date()), "cutoff": cutoff.isoformat(), "articles": int(len(A)),
                               "edges": int((shared >= MIN_SHARED).sum()) if len(shared) else 0, "names": out})
print(f"neighbours: {len(cov)} names, {len(A)} archive rows, {int((shared >= MIN_SHARED).sum()) if len(shared) else 0} edges; "
      f"median {pd.Series([len(v['neighbours']) for v in out.values()]).median():.0f} neighbours per name")
