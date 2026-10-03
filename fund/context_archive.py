"""Data desk · context archive (Amendment 6, fund/AMENDMENT6_PLAN.md). Shadow input only: no champion
desk reads it.

Everything outside the firms' own news that a desk might want, stored point in time in a private
Hugging Face dataset <hf user>/fund-context-archive (CONTEXT_REPO overrides the name):

    days/YYYY-MM-DD.parquet   rows fetched that UTC day: source, key, published_at, fetched_at, h, payload (JSON)
    index.parquet             (source, key, h) of every row ever stored: a row is written once per distinct content
    manifest.json             per fetch day and source: ok?, rows added, error

Append-only: a value that changes (a Kalshi price, a revised GPR day, a GDELT point) is a new row with
its own fetched_at; nothing is overwritten. A desk reads only rows with fetched_at <= its cutoff.

Sources (each independent; a failure is logged and the others run):
  fred     release calendar, 14 days back and 21 ahead          FRED_API_KEY (skipped without it)
  kalshi   open markets of a fixed list of US macro series        public, no key
  gpr      Caldara-Iacoviello AI-GPR files (daily + splits)       public CSV
  gdelt    daily volume and tone for a fixed theme list, 14 days  public, 1 request / 5 s
  finnhub  general market news                                    FINNHUB_API_KEY
  edgar    8-K / 8-K/A of S&P 500 members, items + acceptance    SEC_USER_AGENT (skipped without it)

    python fund/context_archive.py                 # daily, after fund/archive.py
    CONTEXT_LOCAL_ONLY=1 python fund/context_archive.py   # fetch into fund_context/, push nothing
    CONTEXT_SOURCES=kalshi,gpr ...                        # only these sources
"""

import gzip
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(ROOT, "fund_context")
LOCAL_ONLY = os.environ.get("CONTEXT_LOCAL_ONLY") == "1"
if os.environ.get("FUND_MOCK") == "1":
    raise SystemExit(print("context archive: mock mode, nothing fetched") or 0)
now = datetime.now(timezone.utc)
today = now.date().isoformat()
UA = os.environ.get("SEC_USER_AGENT", "").strip()
KALSHI = ["KXFED", "KXFEDDECISION", "KXCPI", "KXCPIYOY", "KXCPICORE", "KXCPICOREYOY", "KXPCECORE", "KXPAYROLLS",
          "KXU3", "KXJOBLESSCLAIMS", "KXGDP", "KXRECSSNBER"]
THEMES = {"tariffs": "(tariff OR tariffs)", "export_controls": '"export controls"', "sanctions": "sanctions",
          "trade_war": '"trade war"', "ai_capex": '("data center" OR "data centers" OR "AI spending")',
          "oil_supply": '(OPEC OR "oil supply" OR "oil prices")', "fed": '"Federal Reserve"',
          "middle_east": '("Middle East" OR Iran OR Israel)', "russia_ukraine": "(Russia Ukraine)",
          "taiwan": "Taiwan", "shutdown": '"government shutdown"', "recession": "recession",
          "labour_strike": '("labor strike" OR "union strike" OR walkout)'}
GPR_FILES = ["ai_gpr_data_daily.csv", "ai_gpr_country_monthly.csv", "ai_gpr_eventtype_monthly.csv",
             "ai_gpr_country_eventtype_monthly.csv", "ai_gpr_bilateral_monthly.csv"]


def get(url, headers=None, raw=False, tries=3, wait=5):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", **(headers or {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
                b = gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404) or k == tries - 1:
                raise
            time.sleep(wait * (k + 1))
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(wait * (k + 1))


rows, status = [], {}


def add(source, key, published, payload):
    p = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    rows.append(dict(source=source, key=str(key), published_at=str(published or ""),
                     fetched_at=now.isoformat(timespec="seconds"), h=hashlib.sha1(p.encode()).hexdigest()[:16], payload=p))


def run(source, fn):
    n0, t0 = len(rows), time.time()
    try:
        msg = fn()                                           # None = complete; "skipped: ..." = no key, not a failure
        status[source] = {"ok": msg is None or msg.startswith("skipped"), "fetched": len(rows) - n0,
                          **({"note": msg} if msg else {})}
    except Exception as exc:
        del rows[n0:]
        status[source] = {"ok": False, "fetched": 0, "error": repr(exc)[:300]}
    print(f"context {source}: {status[source]} ({time.time() - t0:.0f} s)", flush=True)


def fred():
    k = os.environ.get("FRED_API_KEY", "").strip()
    if not k:
        return "skipped: FRED_API_KEY not set"
    lo, hi = (now - timedelta(days=14)).date(), (now + timedelta(days=21)).date()
    d = get("https://api.stlouisfed.org/fred/releases/dates?" + urllib.parse.urlencode(
        {"api_key": k, "file_type": "json", "realtime_start": lo, "realtime_end": hi, "limit": 1000,
         "include_release_dates_with_no_data": "true", "sort_order": "asc"}))
    for r in d.get("release_dates", []):
        add("fred", f"{r['release_id']}|{r['date']}", r["date"], {"release_id": r["release_id"],
                                                                 "release": r.get("release_name"), "date": r["date"]})


def kalshi():
    for s in KALSHI:
        cur = ""
        while True:
            d = get("https://api.elections.kalshi.com/trade-api/v2/markets?" + urllib.parse.urlencode(
                {"series_ticker": s, "status": "open", "limit": 200, **({"cursor": cur} if cur else {})}))
            for m in d.get("markets", []):
                add("kalshi", m["ticker"], m.get("close_time"), {
                    "series": s, "event": m.get("event_ticker"), "title": m.get("title"), "sub": m.get("yes_sub_title"),
                    "close": m.get("close_time"),
                    **{c: m.get(c) for c in ("yes_bid_dollars", "yes_ask_dollars", "last_price_dollars",
                                             "previous_price_dollars", "volume_24h_fp", "open_interest_fp")}})
            cur = d.get("cursor")
            time.sleep(0.2)
            if not cur or not d.get("markets"):
                break


def gpr():
    for f in GPR_FILES:
        df = pd.read_csv(io.BytesIO(get(f"https://www.matteoiacoviello.com/ai_gpr_files/{f}", raw=True)))
        df.columns = [str(c) for c in df.columns]
        k0 = df.columns[0]                                   # the date column
        idc = [c for c in df.columns[1:4] if df[c].dtype == object]   # country / event-type ids where present
        for r in df.to_dict("records"):
            key = "|".join([f, str(r[k0])] + [str(r[c]) for c in idc])
            add("gpr", key, r[k0], {c: (None if pd.isna(v) else v) for c, v in r.items()})


def gdelt():
    # 3 days back is enough: the archive runs daily, so history accumulates here (a 14-day query
    # takes ~13 s at GDELT). Hard cap of 8 minutes so a slow or rate-limited GDELT never holds the job.
    lo = (now - timedelta(days=3)).strftime("%Y%m%d000000")
    hi = now.strftime("%Y%m%d%H%M%S")
    # GDELT rate-limits shared IPs (GitHub runners included), so this source is best effort: the theme
    # order rotates by day, so a theme cut off today is near the front tomorrow, and the 3-day lookback
    # fills the gap.
    bad, end = [], time.time() + 8 * 60
    q_ = [(n, m) for n in THEMES for m in ("timelinevol", "timelinetone")]
    r_ = now.timetuple().tm_yday * 2 % len(q_)
    for name, mode in q_[r_:] + q_[:r_]:
        if time.time() > end:
            bad.append(f"{name}/{mode}: time cap"); continue
        time.sleep(10)                                       # GDELT asks for at most one request every 5 seconds
        try:
            d = get("https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(
                {"query": f"{THEMES[name]} sourcelang:english", "mode": mode, "format": "json",
                 "startdatetime": lo, "enddatetime": hi}), tries=2, wait=20)
        except Exception as exc:
            bad.append(f"{name}/{mode}: {exc!r}"[:80]); continue
        for ser in d.get("timeline", []):
            for pt in ser.get("data", []):
                add("gdelt", f"{name}|{mode}|{pt['date']}", pt["date"],
                    {"theme": name, "query": THEMES[name], "mode": mode, "date": pt["date"], "value": pt["value"]})
    return f"best effort, {len(q_) - len(bad)}/{len(q_)} queries: failed {bad[:2]}" if bad else None


def finnhub():
    k = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not k:
        return "skipped: FINNHUB_API_KEY not set"
    for a in get("https://finnhub.io/api/v1/news?" + urllib.parse.urlencode({"category": "general", "token": k})):
        add("finnhub", a.get("id"), datetime.fromtimestamp(a.get("datetime", 0), timezone.utc).isoformat(),
            {c: a.get(c) for c in ("headline", "summary", "source", "url", "related", "category")})


def edgar():
    if not UA:
        return "skipped: SEC_USER_AGENT not set"
    h = {"User-Agent": UA}
    mem = pd.read_csv(io.BytesIO(get("https://raw.githubusercontent.com/fja05680/sp500/master/"
                                     "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv", raw=True)))
    universe = sorted(mem.iloc[-1].tickers.split(","))
    cik = {v["ticker"]: int(v["cik_str"]) for v in get("https://www.sec.gov/files/company_tickers.json", h).values()}
    lo = (now - timedelta(days=100)).isoformat()
    miss, seen = [], set()
    for t in universe:
        c = cik.get(t.replace(".", "-"))
        if c is None:
            miss.append(t); continue
        if c in seen:                                        # share classes of one issuer file once
            continue
        seen.add(c)
        time.sleep(0.15)                                     # SEC fair access: < 10 requests per second
        try:
            r = get(f"https://data.sec.gov/submissions/CIK{c:010d}.json", h)["filings"]["recent"]
        except Exception:
            miss.append(t); continue
        for i, form in enumerate(r["form"]):
            if form in ("8-K", "8-K/A") and r["acceptanceDateTime"][i] >= lo:
                add("edgar", r["accessionNumber"][i], r["acceptanceDateTime"][i],
                    {"ticker": t, "cik": c, "form": form, "items": r["items"][i], "filed": r["filingDate"][i],
                     "doc": r["primaryDocument"][i], "desc": r["primaryDocDescription"][i]})
    return f"{len(miss)} members without filings data: {miss[:8]}" if len(miss) > 25 else None


ONLY = [x for x in os.environ.get("CONTEXT_SOURCES", "").split(",") if x]     # e.g. "kalshi,gpr" for a test
for name, fn in (("fred", fred), ("kalshi", kalshi), ("gpr", gpr), ("gdelt", gdelt), ("finnhub", finnhub),
                 ("edgar", edgar)):
    if not ONLY or name in ONLY:
        run(name, fn)

# ---- store: keep only content not stored before, append to today's file, update index and manifest
os.makedirs(os.path.join(LOCAL, "days"), exist_ok=True)
new = pd.DataFrame(rows, columns=["source", "key", "published_at", "fetched_at", "h", "payload"])
if LOCAL_ONLY:
    api = None
    idx_p = os.path.join(LOCAL, "index.parquet")
    idx = pd.read_parquet(idx_p) if os.path.exists(idx_p) else pd.DataFrame(columns=["source", "key", "h"])
    man_p = os.path.join(LOCAL, "manifest.json")
    man = json.load(open(man_p)) if os.path.exists(man_p) else {"days": {}}
    old = pd.read_parquet(os.path.join(LOCAL, "days", f"{today}.parquet")) \
        if os.path.exists(os.path.join(LOCAL, "days", f"{today}.parquet")) else None
else:
    from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download
    api = HfApi(token=os.environ["HF_TOKEN"])
    repo = f"{api.whoami()['name']}/{os.environ.get('CONTEXT_REPO', 'fund-context-archive')}"
    api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
    files = set(api.list_repo_files(repo, repo_type="dataset"))
    pull = lambda f: pd.read_parquet(hf_hub_download(repo, f, repo_type="dataset", local_dir=LOCAL))
    idx = pull("index.parquet") if "index.parquet" in files else pd.DataFrame(columns=["source", "key", "h"])
    man = json.load(open(hf_hub_download(repo, "manifest.json", repo_type="dataset", local_dir=LOCAL))) \
        if "manifest.json" in files else {"days": {}}
    old = pull(f"days/{today}.parquet") if f"days/{today}.parquet" in files else None
seen = set(zip(idx["source"], idx["key"], idx["h"]))
add_ = new[[(s, k, h) not in seen for s, k, h in zip(new.source, new.key, new.h)]].drop_duplicates(["source", "key", "h"])
day_p = os.path.join(LOCAL, "days", f"{today}.parquet")
day = pd.concat([old, add_]) if old is not None else add_
day.to_parquet(day_p, index=False)
idx = pd.concat([idx, add_[["source", "key", "h"]]], ignore_index=True)
idx.to_parquet(os.path.join(LOCAL, "index.parquet"), index=False)
added = add_.groupby("source").size().to_dict()
man["days"].setdefault(today, {})
for s, st in status.items():                                 # several runs a day: rows added accumulate
    prev = man["days"][today].get(s, {}).get("added", 0)
    man["days"][today][s] = {**st, "added": int(prev + added.get(s, 0)), "at": now.isoformat(timespec="seconds")}
man["updated"] = now.isoformat(timespec="seconds")
json.dump(man, open(os.path.join(LOCAL, "manifest.json"), "w"), indent=0, sort_keys=True)
if not LOCAL_ONLY:
    api.create_commit(repo, repo_type="dataset", commit_message=f"context {now:%Y-%m-%dT%H:%MZ}", operations=[
        CommitOperationAdd(f"days/{today}.parquet", day_p),
        CommitOperationAdd("index.parquet", os.path.join(LOCAL, "index.parquet")),
        CommitOperationAdd("manifest.json", os.path.join(LOCAL, "manifest.json"))])
print(f"context archive {today}: fetched {len(new)}, new {len(add_)} {added}; "
      f"sources ok {sum(s['ok'] for s in status.values())}/{len(status)}")
