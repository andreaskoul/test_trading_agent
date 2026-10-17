"""Thesis Tree R5 · forward predictions before each quarterly report (PREREG_thesis_tree.md §5, R5 v1). Research only.

For every S&P 500 / S&P 400 firm whose report is dated D (Finnhub earnings calendar), from information to the
cutoff C = 22:00 UTC on the last trading day before D:
* card (1 LLM call): drivers, guidance and kill conditions from the firm's previous earnings release (the EX-99.1
  of its latest 8-K with item 2.02 accepted before C);
* own ledger (3 passes): the firm's deduplicated news since that release -> events, each with driver, direction
  for the coming report, size, hard/soft and new/recap;
* peers (3 passes): the current-season releases of same-sub-industry peers that reported before C -> channel
  (contagion / competitive / none), direction and size for the firm's coming report.
Scores (fixed in the pre-registration): own = median over passes of sum(dir x size x (1.5 if hard)) over NEW events
/ sqrt(1 + n_new); peer likewise over peers with a channel; combined = own + 0.5 x peer. No LLM sees a price.

Records go to fund_state/<mode>/research/r5/<D>.json (append-only per ticker), with a SHA-256 per record and per
batch. The runner commits them to the `research-data` branch and posts the batch hash to the timestamp-log issue, so
every prediction has a server-side time before the firm's 8-K is accepted.

    python fund/r5.py [--date YYYY-MM-DD] [--limit N] [--only T1,T2]     # FUND_DRYRUN=1: dry run, never committed
"""

import argparse
import functools
import gzip
import hashlib
import html
import json
import math
import os
import random
import re
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

import guards
from common import MODE, MODEL, ROOT, STATE, require

VERSION = "r5-v2"          # Amendment 1 (2026-10-16): typed exhibit, content and grounding checks, repair, re-runs, gate
NEWS_MAX, PEERS_MAX, CARD_CHARS, PEER_CHARS, SEASON_DAYS, SUMMARY = 60, 5, 15000, 4000, 45, 150
HARD_W, PEER_W, PASSES = 1.5, 0.5, 3
UA = os.environ.get("SEC_USER_AGENT", "").strip()
OUT = os.path.join(STATE, MODE, "research", "r5")


# ----------------------------------------------------------------------------- data
def universe():
    """Current S&P 500 and S&P 400 members with GICS fields (repo files; survivorship stated in the prereg)."""
    a = pd.read_csv(os.path.join(ROOT, "data/raw/stocks/sp500_current.csv")).assign(index_="SP500")
    b = pd.read_csv(os.path.join(ROOT, "data/raw/stocks/sp400_current.csv")).assign(index_="SP400")
    u = pd.concat([a, b])[["Symbol", "Security", "GICS Sector", "GICS Sub-Industry", "index_"]]
    return u.drop_duplicates("Symbol").set_index("Symbol")


def get(url, headers=None, tries=4, raw=False):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403) and "finnhub" in url:
                raise SystemExit("Finnhub key refused")
            if e.code == 404:
                return None
            time.sleep(5 * (k + 1))
        except Exception:
            time.sleep(3 * (k + 1))
    return None


_last_fh, _fh_lock = [0.0], threading.Lock()


def finnhub(path):
    """Finnhub free tier: 60 calls a minute, spaced by 1.05 s across threads."""
    with _fh_lock:
        wait = 1.05 - (time.time() - _last_fh[0])
        if wait > 0:
            time.sleep(wait)
        _last_fh[0] = time.time()
    sep = "&" if "?" in path else "?"
    return get(f"https://finnhub.io/api/v1/{path}{sep}token={os.environ['FINNHUB_API_KEY']}")


_last_sec, _sec_lock = [0.0], threading.Lock()


def sec(url, raw=False):
    """SEC fair access: <= 10 requests a second across threads, with the required User-Agent."""
    with _sec_lock:
        wait = 0.15 - (time.time() - _last_sec[0])
        if wait > 0:
            time.sleep(wait)
        _last_sec[0] = time.time()
    return get(url, {"User-Agent": UA}, raw=raw)


def text_of(b, limit):
    """HTML -> plain text: scripts and tags dropped, entities decoded, whitespace collapsed."""
    s = b.decode("utf-8", errors="replace") if isinstance(b, bytes) else b
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()[:limit]


_cik = {}


def cik_of(t):
    if not _cik:
        d = sec("https://www.sec.gov/files/company_tickers.json") or {}
        _cik.update({v["ticker"].upper(): int(v["cik_str"]) for v in d.values()})
    return _cik.get(t.replace(".", "-").upper())


@functools.lru_cache(maxsize=None)
def releases(t, before):
    """8-K filings with item 2.02 accepted before `before` (UTC), newest first: (accepted, accession, primary doc)."""
    c = cik_of(t)
    if c is None:
        return c, []
    s = sec(f"https://data.sec.gov/submissions/CIK{c:010d}.json")
    if not s:
        return c, []
    r = s["filings"]["recent"]
    out = []
    for i, form in enumerate(r["form"]):
        if form in ("8-K", "8-K/A") and "2.02" in (r["items"][i] or ""):
            acc = pd.Timestamp(r["acceptanceDateTime"][i]).tz_convert("UTC") if pd.Timestamp(r["acceptanceDateTime"][i]).tzinfo \
                else pd.Timestamp(r["acceptanceDateTime"][i], tz="UTC")
            if acc <= before:
                out.append((acc, r["accessionNumber"][i], r["primaryDocument"][i]))
    return c, sorted(out, reverse=True)


@functools.lru_cache(maxsize=None)
def release_text(cik, acc, primary, limit):
    """The earnings press release of an 8-K item 2.02, chosen by its declared SEC type (EX-99.1, else the first
    EX-99.x) from the filing index, then held to the press-release content contract (guards.release_check).
    Returns (text, name, url, how, defect); defect is None when the document is usable. Never the primary 8-K:
    on 2026-10-15/16 the file-name rule fed 7 of 20 cards an 8-K cover page."""
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    page = sec(f"{base}/{acc}-index.htm", raw=True)
    doc, how = guards.typed_exhibit(guards.filing_documents(page.decode("utf-8", errors="replace") if page else ""))
    if doc is None:
        return "", None, None, how, how
    url = f"{base}/{doc['name']}"
    b = sec(url, raw=True)
    full = text_of(b, 200000) if b else ""
    defect = guards.release_check(full) if full else "exhibit could not be fetched"
    return full[:limit], doc["name"], url, how, defect


def norm(s):
    return " ".join("".join(ch for ch in str(s or "").lower() if ch.isalnum() or ch == " ").split())


def own_news(t, lo, hi):
    """Finnhub company news in (lo, hi], fetched in 30-day chunks, deduplicated: exact headline, then token-set
    Jaccard >= 0.7 within 3 days (the earliest kept). Over NEWS_MAX: the last 30 days in full, older ones sampled
    evenly in time."""
    arts, a = [], lo
    while a < hi:
        b = min(a + pd.Timedelta(days=30), hi)
        x = finnhub(f"company-news?symbol={t.replace('.', '-')}&from={a.date()}&to={b.date()}")
        arts += [y for y in (x or []) if lo.timestamp() < y.get("datetime", 0) <= hi.timestamp()]
        a = b + pd.Timedelta(days=1) if b < hi else hi
    arts = sorted({y["id"]: y for y in arts if y.get("headline")}.values(), key=lambda y: y["datetime"])
    kept = []
    for y in arts:
        ny = set(norm(y["headline"]).split())
        dup = False
        for k in kept[-60:]:
            if y["datetime"] - k["datetime"] > 3 * 86400:
                continue
            nk = set(norm(k["headline"]).split())
            if ny and nk and len(ny & nk) / len(ny | nk) >= 0.7:
                dup = True; break
        if not dup:
            kept.append(y)
    if len(kept) > NEWS_MAX:
        recent = [y for y in kept if y["datetime"] > hi.timestamp() - 30 * 86400][-NEWS_MAX:]
        older = [y for y in kept if y not in recent]
        k_ = NEWS_MAX - len(recent)
        older = [older[int(i * len(older) / k_)] for i in range(k_)] if k_ > 0 else []
        kept = older + recent
    return [{"date": datetime.fromtimestamp(y["datetime"], timezone.utc).strftime("%Y-%m-%d"), "source": y.get("source"),
             "headline": y["headline"], "summary": (y.get("summary") or "")[:SUMMARY]} for y in kept], len(arts)


# ----------------------------------------------------------------------------- LLM tasks
CARD = """You read a company's latest quarterly earnings press release and write the analyst's card for the NEXT
quarterly report. Use only the release. Ignore stock prices, ratings and price targets.
- drivers: the 3-5 business drivers that will decide whether the next quarter's results come in better or worse
  than this release set up (e.g. a segment's revenue, margins, volumes, pricing, a cost item, a product ramp).
  For each: what this release said about it, and any guidance for the next quarter or year.
- guidance: the company's own outlook in numbers if given, else null.
- kill_conditions: 1-3 things that, if reported in later news, would mean the next quarter is going worse than this
  release set up (observable in a headline, not a price move).
Return JSON only: {"drivers": [{"id": "D1", "name": str (<= 8 words), "last_report": str (<= 30 words),
"guidance": str (<= 30 words) or null}], "guidance": str (<= 60 words) or null, "kill_conditions": [str (<= 25 words)]}"""

LEDGER_A = """You keep the evidence ledger for one company between two quarterly reports. You get the card written
from its last earnings release (its drivers) and the company's news since that release, oldest first.
List the distinct EVENTS in the news that bear on the NEXT quarterly report's results relative to what the last
release set up. One entry per event, however many articles repeat it. Ignore stock-price moves, analyst ratings,
price targets and opinion pieces: they are not events.
For each event: "driver" = the card driver id it affects, or "other"; "direction" = +1 if it points to results
better than the last release set up, -1 worse, 0 unclear; "size" = 1 small, 2 material, 3 major; "hard" = true if
it is a hard fact with a number or a signed contract/decision, false if soft (talk, plans, rumours); "new" = true
only if it happened AFTER the last release (not a recap or analysis of it).
Also give your overall read: will the next report's results come in above, in line with, or below what the last
release set up?
Return JSON only: {"events": [{"what": str (<= 20 words), "date": "YYYY-MM-DD", "driver": str, "direction": -1|0|1,
"size": 1|2|3, "hard": bool, "new": bool}] (at most 15), "overall": "above"|"inline"|"below", "confidence": float 0-1}"""

LEDGER_B = """Below are a company's drivers (from its last earnings release) and the news published since then. Work
out which distinct events reported in this news change the outlook for the next quarterly report against what the
last release led people to expect. Count each underlying event once. Price moves, broker ratings, target prices
and commentary are not events. For every event say which driver it affects (or "other"), whether it points
to better (+1), worse (-1) or unclear (0) results than the last release set up, how big it is (1 small, 2 material,
3 major), whether it is a hard fact (numbers, signed deals, decisions) or soft, and whether it happened after the
last release ("new") or merely revisits earlier news. Then give an overall call: above, inline or below.
Return JSON only: {"events": [{"what": str (<= 20 words), "date": "YYYY-MM-DD", "driver": str, "direction": -1|0|1,
"size": 1|2|3, "hard": bool, "new": bool}] (at most 15), "overall": "above"|"inline"|"below", "confidence": float 0-1}"""

PEERS = """A company is about to report its quarter. Some of its industry peers have already reported this season.
You get the company's drivers and the peers' earnings releases. For each peer, judge what its release implies for
the company's coming results against what the company's last release set up:
- "channel": "contagion" if the peer's news reveals conditions shared by the industry (demand, pricing, costs,
  supply) that apply to the company too; "competitive" if it reveals a shift of business between them (share
  gains or losses), which points the other way for the company; "none" if it says nothing about the company.
- "direction" for the COMPANY: +1 better, -1 worse, 0 unclear; "size" 1-3; "driver" the company's driver id or
  "other". Ignore stock prices.
Return JSON only: {"peers": [{"peer": str (ticker), "channel": "contagion"|"competitive"|"none", "direction": -1|0|1,
"size": 1|2|3, "driver": str, "why": str (<= 25 words)}]}"""


def chk_card(o):
    d = o.get("drivers")
    if not isinstance(d, list) or not 1 <= len(d) <= 6 or not all(isinstance(x, dict) and x.get("id") and x.get("name") for x in d):
        return "drivers: 1-6 objects with id and name"
    k = o.get("kill_conditions")
    return None if isinstance(k, list) and 1 <= len(k) <= 3 else "kill_conditions: 1-3"


def chk_ledger(o):
    ev = o.get("events")
    if not isinstance(ev, list) or len(ev) > 20:
        return "events: a list of at most 15"
    for e in ev:
        if e.get("direction") not in (-1, 0, 1) or e.get("size") not in (1, 2, 3) or not isinstance(e.get("hard"), bool) \
                or not isinstance(e.get("new"), bool):
            return "each event needs direction -1/0/1, size 1-3, hard and new as booleans"
    return None if o.get("overall") in ("above", "inline", "below") else "overall: above, inline or below"


def chk_peers(names):
    def f(o):
        ps = o.get("peers")
        if not isinstance(ps, list) or sorted(p.get("peer") for p in ps) != sorted(names):
            return f"one entry per peer: {names}"
        for p in ps:
            if p.get("channel") not in ("contagion", "competitive", "none") or p.get("direction") not in (-1, 0, 1) \
                    or p.get("size") not in (1, 2, 3):
                return "channel, direction -1/0/1 and size 1-3 per peer"
        return None
    return f


def own_score(o):
    new = [e for e in o["events"] if e["new"]]
    return sum(e["direction"] * e["size"] * (HARD_W if e["hard"] else 1.0) for e in new) / math.sqrt(1 + len(new))


def peer_score(o):
    ps = [p for p in o["peers"] if p["channel"] != "none"]
    return sum(p["direction"] * p["size"] for p in ps) / math.sqrt(1 + len(ps))


def med(xs):
    return float(statistics.median(xs)) if len(xs) >= 2 else None


# ----------------------------------------------------------------------------- one firm
def one(t, D, C, U, season_rel, prompts):
    rec = {"ticker": t, "index": U.loc[t, "index_"], "sector": U.loc[t, "GICS Sector"], "sub_industry": U.loc[t, "GICS Sub-Industry"]}
    cik, rel = releases(t, C)
    if not rel:
        return {**rec, "status": "no_release_found"}
    acc, accession, primary = rel[0]
    if (C - acc).days < SEASON_DAYS:                       # already reported this season: the calendar is stale
        return {**rec, "status": "already_reported", "last_release": str(acc)}
    card_txt, card_file, card_url, how, defect = release_text(cik, accession, primary, CARD_CHARS)
    src = {"last_release": str(acc), "release_url": card_url, "release_doc": how}
    if defect:                                              # input contract: no LLM call on the wrong document
        return {**rec, **src, "status": "input_defect", "error": defect}
    st, card, meta, err, glog = guards.guarded_llm(CARD, f"Company {t} ({U.loc[t, 'Security']}). Earnings release accepted {acc:%Y-%m-%d}:\n\n{card_txt}", chk_card)
    prompts.append({"ticker": t, "task": "card", "system": CARD, "user": card_txt[:200] + "..."})
    if st != "ok":
        return {**rec, **src, "status": "card_failed", "error": err, "card_log": glog}
    claims = " ".join(f"{d.get('last_report') or ''} {d.get('guidance') or ''}" for d in card["drivers"]) + f" {card.get('guidance') or ''}"
    grounded, gstats = guards.grounding(claims, card_txt)
    if not grounded:                                        # output contract: the card must rest on its release
        return {**rec, **src, "status": "card_ungrounded", "error": f"card numbers not in the release: {gstats}",
                "card": card, "card_log": glog, "grounding": gstats}
    news, n_raw = own_news(t, acc, C)
    drivers = "\n".join(f"{d['id']}. {d['name']}: last report: {d.get('last_report')}; guidance: {d.get('guidance')}" for d in card["drivers"])
    listing = lambda xs: "\n".join(f"[{i}] {x['date']} {x['source']}: {x['headline']} :: {x['summary']}" for i, x in enumerate(xs))
    shuffled = news[:]
    random.Random(f"{t}|{D.date()}").shuffle(shuffled)
    def ledger_pass(k_sys_xs):
        k, (sysp, xs) = k_sys_xs
        user = (f"Company {t} ({U.loc[t, 'Security']}). Last earnings release: {acc:%Y-%m-%d}. News up to {C:%Y-%m-%d %H:%M} UTC.\n"
                f"DRIVERS:\n{drivers}\nGUIDANCE: {card.get('guidance')}\n\nNEWS ({len(xs)} items):\n{listing(xs) or 'none'}")
        s_, o, m_, e_, lg = guards.guarded_llm(sysp, user, chk_ledger)
        prompts.append({"ticker": t, "task": f"ledger{k}", "system": sysp, "user": user})
        return {"status": s_, "out": o, "error": e_, "provider": m_.get("provider"), "log": lg}

    specs = list(enumerate(((LEDGER_A, news), (LEDGER_B, news), (LEDGER_A, shuffled))))
    with ThreadPoolExecutor(PASSES) as px:                  # the three passes are independent
        own_passes = list(px.map(ledger_pass, specs))
        again = [i for i, x in enumerate(own_passes) if x["status"] != "ok"]
        for i, x in zip(again, px.map(ledger_pass, [specs[i] for i in again])):   # one re-run of a failed pass
            own_passes[i] = {**x, "rerun": True, "first_error": own_passes[i]["error"]}
    okp = [p["out"] for p in own_passes if p["status"] == "ok"]
    own = med([own_score(o) for o in okp])
    overall = [o["overall"] for o in okp]
    # peers: same sub-industry, reported this season before the cutoff (most recent first)
    sub = U.loc[t, "GICS Sub-Industry"]
    peers = [p for p in season_rel.get(sub, []) if p[0] != t][:PEERS_MAX]
    peer_passes, peer = [], None
    peer_defects = {}
    if peers:
        blocks, kept = [], []
        for p, (pacc, pcik, paccn, pprim) in peers:
            txt, _, _, _, pdef = release_text(pcik, paccn, pprim, PEER_CHARS)
            if pdef:
                peer_defects[p] = pdef; continue
            kept.append((p, (pacc, pcik, paccn, pprim)))
            blocks.append(f"=== PEER {p} ({U.loc[p, 'Security']}), release accepted {pacc:%Y-%m-%d}:\n{txt}")
        peers = kept
        names = [p for p, _ in peers]
        order = [list(range(len(blocks))), list(range(len(blocks))), list(reversed(range(len(blocks))))]
        def peer_pass(k_idx):
            k, idx = k_idx
            user = (f"Company {t} ({U.loc[t, 'Security']}). DRIVERS:\n{drivers}\n\nPEER RELEASES:\n" + "\n\n".join(blocks[i] for i in idx))
            s_, o, m_, e_, lg = guards.guarded_llm(PEERS, user, chk_peers(names))
            prompts.append({"ticker": t, "task": f"peers{k}", "system": PEERS, "user": user})
            return {"status": s_, "out": o, "error": e_, "provider": m_.get("provider"), "log": lg}

        if not peers:
            order = []
        with ThreadPoolExecutor(PASSES) as px:
            peer_passes = list(px.map(peer_pass, enumerate(order)))
            again = [i for i, x in enumerate(peer_passes) if x["status"] != "ok"]
            for i, x in zip(again, px.map(peer_pass, [(i, order[i]) for i in again])):
                peer_passes[i] = {**x, "rerun": True, "first_error": peer_passes[i]["error"]}
        peer = med([peer_score(o) for o in [x["out"] for x in peer_passes if x["status"] == "ok"]])
    combined = None if own is None else own + PEER_W * (peer or 0.0)
    return {**rec, **src, "status": "ok" if own is not None else "ledger_failed",
            "card": card, "card_provider": meta.get("provider"), "card_log": glog, "grounding": gstats,
            "peer_defects": peer_defects, "news_raw": n_raw, "news_used": len(news),
            "own_passes": own_passes, "peers": [p for p, _ in peers], "peer_passes": peer_passes,
            "score_own": own, "score_peer": peer, "score_combined": combined,
            "overall_votes": overall, "overall": max(set(overall), key=overall.count) if overall else None}


def canon(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date"); ap.add_argument("--limit", type=int); ap.add_argument("--only")
    a = ap.parse_args()
    require("OPENROUTER_API_KEY", "FINNHUB_API_KEY")
    if not UA:
        raise SystemExit("SEC_USER_AGENT is required (name and contact email, as the SEC requires)")
    D = pd.Timestamp(a.date) if a.date else pd.Timestamp(datetime.now(timezone.utc).date())
    import broker                                           # the exchange calendar (Alpaca), as every desk
    s_, cal = broker.api("GET", f"/v2/calendar?start={(D - pd.Timedelta(days=10)).date()}&end={(D - pd.Timedelta(days=1)).date()}")
    assert s_ == 200 and cal, f"calendar unavailable: {s_}"
    prev = max(pd.Timestamp(x["date"]) for x in cal)
    C = pd.Timestamp(prev.date(), tz="UTC") + pd.Timedelta(hours=22)
    now = pd.Timestamp.now(tz="UTC")
    if now < C:
        raise SystemExit(f"r5: the cutoff {C} for reports dated {D.date()} has not passed yet")
    U = universe()
    E = (finnhub(f"calendar/earnings?from={D.date()}&to={D.date()}") or {}).get("earningsCalendar", [])
    todo = {}
    for e in E:
        t = e["symbol"].replace("-", ".")
        if t in U.index and e.get("date") == str(D.date()):
            todo[t] = {"hour": e.get("hour") or "", "eps_estimate": e.get("epsEstimate"), "revenue_estimate": e.get("revenueEstimate"),
                       "fiscal": f"{e.get('year')}Q{e.get('quarter')}"}
    if a.only:
        todo = {t: v for t, v in todo.items() if t in a.only.split(",")}
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, f"{D.date()}.json")
    old = json.load(open(p)) if os.path.exists(p) else {"records": {}}
    todo = {t: v for t, v in sorted(todo.items()) if t not in old["records"]}                  # append-only
    if a.limit:
        todo = dict(list(todo.items())[:a.limit])
    print(f"r5 {D.date()}: cutoff {C}, {len(E)} calendar entries, {len(todo)} universe firms to predict", flush=True)
    if not todo:
        return
    # this season's releases by sub-industry, for the peer rung: every universe firm in a sub-industry with a firm to predict
    season_rel = {}
    subs = {U.loc[t, "GICS Sub-Industry"] for t in todo}
    for q in U.index[U["GICS Sub-Industry"].isin(subs)]:
        c, rel = releases(q, C)
        if rel and (C - rel[0][0]).days < SEASON_DAYS:
            season_rel.setdefault(U.loc[q, "GICS Sub-Industry"], []).append((q, (rel[0][0], c, rel[0][1], rel[0][2])))
    for k in season_rel:
        season_rel[k].sort(key=lambda x: x[1][0], reverse=True)
    prompts = []
    code = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

    def run(t):
        try:
            r = one(t, D, C, U, season_rel, prompts)
        except Exception as exc:                            # one firm's failure never stops the batch
            r = {"ticker": t, "status": "error", "error": repr(exc)}
        r.update(todo[t], report_date=str(D.date()), cutoff=str(C), decided_at=pd.Timestamp.now(tz="UTC").isoformat(),
                 model=MODEL, version=VERSION, code=code)
        r["sha256"] = hashlib.sha256(canon({k: v for k, v in r.items() if k != "sha256"}).encode()).hexdigest()
        print(f"r5 {t}: {r['status']}" + (f" own {r['score_own']:+.2f} peer {r['score_peer']} combined {r['score_combined']:+.2f} "
                                           f"({r['news_used']} news, {len(r['peers'])} peers)" if r.get("score_combined") is not None else
                                           f" ({r.get('error', '')})"), flush=True)
        return t, r

    with ThreadPoolExecutor(8) as ex:                       # Finnhub and SEC are paced globally; LLM calls overlap
        new = dict(ex.map(run, list(todo)))
    old["records"].update(new)
    old.update(report_date=str(D.date()), cutoff=str(C), version=VERSION,
               batch_sha256=hashlib.sha256(canon({t: r["sha256"] for t, r in sorted(old["records"].items())}).encode()).hexdigest())
    json.dump(old, open(p, "w"), indent=1, default=str, ensure_ascii=False)
    with gzip.open(os.path.join(OUT, f"{D.date()}.prompts.{datetime.now(timezone.utc):%H%M%S}.jsonl.gz"), "wt") as fh:
        for x in prompts:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    passed, q = guards.quality_gate([r["status"] for r in new.values()])
    old.setdefault("runs", []).append({"at": pd.Timestamp.now(tz="UTC").isoformat(), "version": VERSION, "code": code, "quality": q})
    json.dump(old, open(p, "w"), indent=1, default=str, ensure_ascii=False)
    ok = sum(r["status"] == "ok" for r in new.values())
    print(f"r5 {D.date()}: {ok}/{len(new)} ok; quality {q}; batch sha256 {old['batch_sha256']}")
    if not passed:                                          # records are saved and committed first (runner: when=always)
        raise SystemExit(f"r5 quality gate failed: {q['bad']} of {q['attempted']} input defects or failures "
                         f"(threshold {q['threshold']:.0%}): {q['counts']}")


if __name__ == "__main__":
    main()
