"""Data desk · news archive for the whole S&P 500 (fund/README.md).

Every S&P 500 member's Finnhub company news, one UTC day per file, in a private
Hugging Face dataset <hf user>/fund-news-archive:

    days/YYYY-MM-DD.parquet   one row per (sym, article), columns as pipeline/fetch.py writes them
    manifest.json             per day: complete? and which symbols still failed

    python fund/archive.py                   # daily: yesterday + today, then backfill until the budget
    ARCHIVE_MINUTES=330 python fund/archive.py   # a longer backfill run

Research reads these files for its coverage list, so a name ideation picks for the
first time already has its 91 days and fetch.py only fills the last hours. Queries
are one day per call, like fetch.py, because Finnhub's per-call cap is undocumented.
Prints `backlog=<n>` (days still incomplete) for the workflow to decide on chaining.
"""

import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import hashlib
import html
import re

import pandas as pd
from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi, hf_hub_download

WINDOW, KEEP = 91, 121                           # dashboard window; fetch.py keeps window + 30 days
REPO_NAME = "fund-news-archive"
LOCAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fund_archive")
FK = os.environ["FINNHUB_API_KEY"]
api = HfApi(token=os.environ["HF_TOKEN"])
repo = f"{api.whoami()['name']}/{REPO_NAME}"
api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
now = datetime.now(timezone.utc)
t_end = time.time() + 60 * float(os.environ.get("ARCHIVE_MINUTES", "40"))
if now.weekday() == 2:                           # Wednesday: Finnhub belongs to the weekly desks from 22:15 UTC
    t_end = min(t_end, datetime(now.year, now.month, now.day, 22, 10, tzinfo=timezone.utc).timestamp())
os.makedirs(os.path.join(LOCAL, "days"), exist_ok=True)

# universe: the latest S&P 500 membership (same source as the screen desk)
url = ("https://raw.githubusercontent.com/fja05680/sp500/master/"
       "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv")
with urllib.request.urlopen(url, timeout=60) as r:
    mem = pd.read_csv(io.BytesIO(r.read()), parse_dates=["date"])
universe = sorted(mem.iloc[-1].tickers.split(","))

files = set(api.list_repo_files(repo, repo_type="dataset"))
man = json.load(open(hf_hub_download(repo, "manifest.json", repo_type="dataset", local_dir=LOCAL))) \
    if "manifest.json" in files else {"days": {}}


# text cleaning verbatim from the dashboard's pipeline/fetch.py (pinned commit), so rows are identical
def clean(t):
    t = html.unescape(html.unescape(t or ""))
    if re.search("[\u00c2\u00c3\u00e2][\u0080-\u00bf\u20ac\u2122\u0153\u201c\u201d\u2018\u2019]", t):
        for enc in ("cp1252", "latin-1"):                  # UTF-8 that was decoded as Latin-1 upstream ("Palantirâ€™s")
            try: t = t.encode(enc).decode("utf-8"); break
            except UnicodeError: pass
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[​-‏﻿­]", "", t)
    t = re.sub(r"\s+([.,;:!?])", r"\1", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return "" if re.match(r"https?://\S+$", t) else t      # a bare URL is not a summary


def get(u):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(u, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(15 * (attempt + 1)); continue
            if e.code in (401, 403):
                raise SystemExit(f"Finnhub key refused (HTTP {e.code})")
            return None
        except Exception:
            time.sleep(3)
    return None


def load_day(day):
    p = os.path.join(LOCAL, "days", f"{day}.parquet")
    if not os.path.exists(p) and f"days/{day}.parquet" in files:
        hf_hub_download(repo, f"days/{day}.parquet", repo_type="dataset", local_dir=LOCAL)
    return pd.read_parquet(p) if os.path.exists(p) else pd.DataFrame()


def do_day(day, syms):
    """Query `syms` for one UTC day, union with what is stored. Returns the symbols that failed."""
    old = load_day(day)
    rows, failed = [], []
    for i, s in enumerate(syms):
        if time.time() > t_end:                                     # out of budget: the rest stays missing
            failed += syms[i:]; break
        d = get("https://finnhub.io/api/v1/company-news?" + urllib.parse.urlencode(
            {"symbol": s, "from": day, "to": day, "token": FK}))
        time.sleep(1.05)                                            # free tier: 60 calls / minute
        if d is None:
            failed.append(s); continue
        for a in d:
            h, sm = clean(a.get("headline")), clean(a.get("summary"))
            rows.append(dict(sym=s, src="finnhub", id=str(a.get("id")), t=h, desc=(sm if sm != h else ""),
                             ingested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             h=hashlib.sha1(f"{h}|{sm}".encode()).hexdigest()[:16],
                             tickers=[x for x in (a.get("related") or "").split(",") if x], publisher=a.get("source"),
                             published=datetime.fromtimestamp(a.get("datetime", 0), timezone.utc).isoformat(),
                             url=a.get("url")))
    new = pd.DataFrame(rows)
    # append-only (Amendment 4): the first-seen version of an article is never overwritten; a revised
    # text under the same id is kept as a further row (different content hash)
    key = ["sym", "src", "id", "h"] if "h" in old else ["sym", "src", "id"]
    df = pd.concat([old, new]).drop_duplicates(key, keep="first") if len(new) else old
    if len(df):
        df.sort_values(["sym", "published"]).to_parquet(os.path.join(LOCAL, "days", f"{day}.parquet"), index=False)
    return sorted(set(failed)), len(new)


changed, deleted = set(), []


def push(msg):
    ops = [CommitOperationAdd(f"days/{d}.parquet", os.path.join(LOCAL, "days", f"{d}.parquet"))
           for d in sorted(changed) if os.path.exists(os.path.join(LOCAL, "days", f"{d}.parquet"))]
    ops += [CommitOperationDelete(f"days/{d}.parquet") for d in deleted if f"days/{d}.parquet" in files]
    man["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(man, open(os.path.join(LOCAL, "manifest.json"), "w"), indent=0, sort_keys=True)
    ops.append(CommitOperationAdd("manifest.json", os.path.join(LOCAL, "manifest.json")))
    api.create_commit(repo, repo_type="dataset", operations=ops, commit_message=msg)
    files.update(f"days/{d}.parquet" for d in changed); files.difference_update(f"days/{d}.parquet" for d in deleted)
    changed.clear(); deleted.clear()


today, yday = now.date(), now.date() - timedelta(days=1)
# 1. fresh: yesterday (now complete) and today so far, every symbol
for day, complete in ((yday, True), (today, False)):
    failed, n = do_day(day.isoformat(), universe)
    man["days"][day.isoformat()] = {"complete": complete and not failed, "missing": failed}
    changed.add(day.isoformat())
    print(f"{day}: +{n} articles, {len(failed)} symbols failed", flush=True)
push(f"daily {today}")

# 2. backfill, newest first: whole days never done, then symbols that failed on a day
window = [today - timedelta(days=i) for i in range(2, WINDOW + 2)]
todo = [d.isoformat() for d in window if not man["days"].get(d.isoformat(), {}).get("complete")]
for k, day in enumerate(todo):
    if time.time() > t_end:
        break
    syms = (man["days"].get(day) or {}).get("missing") or universe
    failed, n = do_day(day, syms)
    man["days"][day] = {"complete": not failed, "missing": failed}
    changed.add(day)
    print(f"{day}: backfill {len(syms)} symbols, +{n} articles, {len(failed)} left", flush=True)
    if len(changed) >= 4:
        push(f"backfill to {day}")

# 3. retention: the same horizon fetch.py keeps
cut = (today - timedelta(days=KEEP)).isoformat()
for d in list(man["days"]):
    if d < cut:
        deleted.append(d); man["days"].pop(d)
push(f"backfill/retention {today}")
backlog = sum(1 for d in window if not man["days"].get(d.isoformat(), {}).get("complete"))
print(f"backlog={backlog}")
if os.environ.get("GITHUB_OUTPUT"):
    open(os.environ["GITHUB_OUTPUT"], "a").write(f"backlog={backlog}\n")
