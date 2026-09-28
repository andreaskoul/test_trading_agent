"""Desk 3 · Research (PROTOCOL_fund.md).

Runs the narrative-dashboard pipeline (my-website pipeline/fetch.py +
build.py at the pinned commit) on this week's coverage list in its own
workspace, fund_research/. Feeds (data/raw) and story state (data/state)
persist across weeks on the fund-data branch, so a name keeps its stories'
identity and history. New names backfill the dashboard window (91 days).
-> research/<TICKER>.json (the dashboard's per-firm output) + research.json
"""

import json
import os
import re
import shutil
import subprocess

import pandas as pd

from common import MOCK, ROOT, SITE_PIN, SITE_REPO, asof_from_env, load, require, save, week_dir

require("OPENROUTER_API_KEY", "FINNHUB_API_KEY")
asof = asof_from_env()
cov = load(asof, "ideation.json")["coverage"]
S = pd.DataFrame(load(asof, "screen.json")["rows"]).set_index("ticker")
site = os.path.join(ROOT, ".cache", "my-website")
work = os.path.join(ROOT, "fund_research")
out_dir = os.path.join(week_dir(asof), "research")
os.makedirs(out_dir, exist_ok=True)

# firm list: the dashboard's curated entries where they exist, generated ones otherwise
curated = {f["ticker"]: f for f in json.loads(subprocess.run(
    ["git", "-C", site, "show", f"{SITE_PIN}:config/firms.json"], capture_output=True, text=True, check=True).stdout)["firms"]}
SUFFIX = r"\b(incorporated|inc|corporation|corp|company|co|holdings?|group|plc|ltd|limited|the|class [a-z]|n\.?v|s\.?a)\b\.?"
firms = []
for t in cov:
    if t in curated:
        firms.append(curated[t]); continue
    name = str(S.loc[t, "Security"]) if t in S.index else t
    core = re.sub(r"\s+", " ", re.sub(SUFFIX, "", re.sub(r"\(.*?\)|[,.]", " ", name.lower()))).strip()
    alts = [re.escape(core) if len(core) >= 5 else rf"\b{re.escape(core)}\b"] + ([rf"\b{re.escape(t.lower())}\b"] if len(t) >= 3 else [])
    firms.append({"ticker": t, "name": name, "match": "|".join(a for a in alts if a)})

status = {}
if MOCK:
    # no keys in mock mode: reuse the dashboard's published output where it exists
    for t in cov:
        r = subprocess.run(["git", "-C", site, "show", f"origin/HEAD:site/data/{t}.json"], capture_output=True, text=True)
        if r.returncode == 0:
            open(os.path.join(out_dir, f"{t}.json"), "w").write(r.stdout); status[t] = "ok (mock: dashboard copy)"
        else:
            status[t] = "no_data (mock)"
else:
    os.makedirs(work, exist_ok=True)
    for sub in ("pipeline",):                      # pinned pipeline code
        shutil.rmtree(os.path.join(work, sub), ignore_errors=True)
        subprocess.run(f"git -C {site} archive {SITE_PIN} {sub} | tar -x -C {work}", shell=True, check=True)
    # News archive: fund_research/data/raw persists on `fund-data`, so each week only the gap since a
    # firm's newest stored article is fetched (fetch.py catches up from there; --days 1 below).
    # Firms the dashboard already tracks are topped up from its feed first (it updates daily), so
    # their gap is usually zero Finnhub calls. Union by (source, id); nothing is ever overwritten.
    os.makedirs(os.path.join(work, "data", "raw"), exist_ok=True)

    def union(t, add):
        """Add rows to fund_research/data/raw/<t>.jsonl by (source, id); nothing is overwritten."""
        dst = os.path.join(work, "data", "raw", f"{t}.jsonl")
        mine = [json.loads(l) for l in open(dst)] if os.path.exists(dst) else []
        have = {(x["src"], str(x["id"])) for x in mine}
        add = [x for x in add if (x["src"], str(x["id"])) not in have]
        if add:
            with open(dst, "w") as fh:
                for x in sorted(mine + add, key=lambda x: x["published"]):
                    fh.write(json.dumps(x, ensure_ascii=False) + "\n")
        return len(add)

    merged = {}
    for t in cov:
        r = subprocess.run(["git", "-C", site, "show", f"origin/HEAD:data/raw/{t}.jsonl"], capture_output=True, text=True)
        if r.returncode == 0:
            merged[t] = union(t, [json.loads(l) for l in r.stdout.splitlines() if l.strip()])
    print("research: merged from the dashboard's feeds:", merged)
    # The S&P 500 news archive (fund/archive.py, updated daily): every covered name arrives with its
    # window already stored, so fetch.py only asks for the hours since the archive's last run.
    try:
        from huggingface_hub import HfApi, snapshot_download
        api = HfApi(token=os.environ["HF_TOKEN"])
        arepo = f"{api.whoami()['name']}/fund-news-archive"
        d_ = snapshot_download(arepo, repo_type="dataset", allow_patterns=["manifest.json"],
                               local_dir=os.path.join(ROOT, "fund_archive"), token=os.environ["HF_TOKEN"])
        man = json.load(open(os.path.join(d_, "manifest.json")))["days"]
        today = pd.Timestamp.now(tz="UTC").normalize()
        gaps = [str(d.date()) for d in pd.date_range(today - pd.Timedelta(days=92), today - pd.Timedelta(days=2))
                if not man.get(str(d.date()), {}).get("complete")]
        # a partial window would hide the gap from fetch.py (it only looks at the newest stored article)
        if gaps:
            raise RuntimeError(f"archive window incomplete ({len(gaps)} days, e.g. {gaps[:3]})")
        lo = str((today - pd.Timedelta(days=121)).date())
        want = [f for f in api.list_repo_files(arepo, repo_type="dataset") if f.startswith("days/") and f[5:15] >= lo]
        d_ = snapshot_download(arepo, repo_type="dataset", allow_patterns=want,
                               local_dir=os.path.join(ROOT, "fund_archive"), token=os.environ["HF_TOKEN"])
        A = pd.concat([pd.read_parquet(os.path.join(d_, f)) for f in want])
        A = A[A["sym"].isin(cov)]
        got = {t: union(t, [{k: (list(v) if k == "tickers" else v) for k, v in r.items() if k not in ("sym", "ingested_at", "h")}
                            for r in g.to_dict("records")]) for t, g in A.groupby("sym")}
        print(f"research: merged from the S&P 500 archive ({len(want)} days):", got)
    except Exception as exc:                                          # never block research on the archive
        print(f"research: archive unavailable ({exc!r}); fetch.py backfills new names itself")
    # build.py expects these to exist (it writes per-firm story state and site files)
    for d_ in ("data/state", "data/cache", "site/data"):
        os.makedirs(os.path.join(work, d_), exist_ok=True)
    # a firm the dashboard already tracks keeps its fitted stories (ids, names, history) on first coverage
    for t in cov:
        dst = os.path.join(work, "data", "state", f"{t}.json")
        if not os.path.exists(dst):
            r = subprocess.run(["git", "-C", site, "show", f"origin/HEAD:data/state/{t}.json"], capture_output=True, text=True)
            if r.returncode == 0:
                open(dst, "w").write(r.stdout)
    os.makedirs(os.path.join(work, "config"), exist_ok=True)
    json.dump({"window_days": 91, "firms": firms}, open(os.path.join(work, "config", "firms.json"), "w"), indent=1)
    env = {**os.environ, "EMBED_MODEL": "openrouter:google/gemini-embedding-2",
           "OPENROUTER_MODEL": "deepseek/deepseek-v4.1-flash"}
    f = subprocess.run(["python", "pipeline/fetch.py", "--days", "1"], cwd=work, env=env)
    b = subprocess.run(["python", "pipeline/build.py", "--refit"], cwd=work, env=env)
    for t in cov:
        p = os.path.join(work, "site", "data", f"{t}.json")
        if os.path.exists(p):
            shutil.copy(p, os.path.join(out_dir, f"{t}.json")); status[t] = "ok"
        else:
            status[t] = f"no_output (fetch rc={f.returncode}, build rc={b.returncode})"

save(asof, "research.json", {"asof": str(asof.date()), "pipeline": SITE_REPO, "pipeline_commit": SITE_PIN,
                             "firms": firms, "status": status})
n_ok = sum(v.startswith('ok') for v in status.values())
print(f"research: {n_ok}/{len(cov)} firms with narratives")
if n_ok == 0 and not MOCK:        # never let the analysts run blind without saying so
    raise SystemExit("research produced no narratives for any covered firm; see the pipeline output above")
