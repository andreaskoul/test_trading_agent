"""News desk · ingest (Desk 18, plan: general news + video/podcast transcripts → firm/sector map → Thesis Tree
evidence). Research input only: no desk reads it, and no Protocol 7 input changes.

Sources (each independent; a failure is logged and the others run), all free:
  alpaca     Benzinga news via Alpaca: headline, summary, symbols         ALPACA_API_KEY / _SECRET_KEY
  gdelt      GDELT DOC 2.0 artlist (titles only) for the queries in sources.json   public, 1 request / 5 s
  finnhub    general market news, read from the context archive (no new Finnhub calls)   HF_TOKEN
  rss        official feeds (Fed, FDA, DoD contracts) and trade press: title + summary. The DoD feed only
             announces the daily notice; war.gov refuses scripted reads of the notice itself (403), so contract
             awards come from usaspending instead (which lags)
  fedreg     Federal Register documents: title, abstract, agencies          public API
  openfda    drug enforcement reports and Drugs@FDA submissions             public API (lags by days)
  usaspending  contract awards >= $10M                                     public API
  youtube    channels in sources.json: uploads listed with yt-dlp, captions with youtube-transcript-api
             (yt-dlp subtitles as fallback). YouTube refuses cloud IPs: this runs on the local runner only.
  podcasts   RSS feeds: the feed's own <podcast:transcript> when it has one, else the audio through
             mlx-whisper on the Mac (Apple Silicon only)

Text news is headline + summary only (owner's decision): article bodies are never scraped.

Every item carries published_at and fetched_at; available_at = fetched_at (a transcript exists only once it is
fetched: auto captions appear hours after upload, live streams after they end).

    python fund/news_ingest.py --probe --since 2026-10-13 --until 2026-10-15     # Phase 0 cost probe
    NEWS_SOURCES=gdelt,rss python fund/news_ingest.py --probe ...                 # only these sources

Each source in data/raw/news/sources.json has a status: active (fetched, transcribed), archive (listing metadata
only) or dropped (skipped); NEWS_ALL=1 treats archive channels as active (the Phase 0 probe measured everything).

--probe writes to fund_news_probe/ (gitignored) and pushes nothing. Over a window, a channel or show with fewer
than PROBE_MIN items in it is sampled instead: its latest items are fetched and scaled by its release rate, so
per-day volumes are comparable across daily and weekly sources.
"""

import argparse
import email.utils
import gzip
import hashlib
import html
import io
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import pandas as pd

try:                                                         # some APIs (usaspending) need a fuller CA bundle
    import certifi
    import ssl
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = None
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = json.load(open(os.path.join(ROOT, "data/raw/news/sources.json")))
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"}
PROBE_MIN, SAMPLE_N, SHORT_S, YT_SLEEP = 3, 3, 90, 2.5
GDELT_SLEEP, GDELT_SLICE_H = float(os.environ.get("NEWS_GDELT_SLEEP", 15)), int(os.environ.get("NEWS_GDELT_SLICE_H", 12))
WHISPER_MAX_S = int(os.environ.get("NEWS_WHISPER_MAX_S", 1200))       # audio transcribed per item (tokens scale per minute)
WHISPER = "mlx-community/whisper-large-v3-turbo"
now = datetime.now(timezone.utc)
NOW = now.isoformat(timespec="seconds")


def get(url, headers=None, data=None, raw=False, tries=3, wait=5, timeout=60):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"Accept-Encoding": "gzip", **UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                b = r.read()
                b = gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404) or k == tries - 1:
                raise
            time.sleep(wait * (k + 1))
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(wait * (k + 1))


def ts(x):
    """Any date string → aware UTC datetime (None if unparseable)."""
    if x is None or x == "":
        return None
    if isinstance(x, (int, float)):
        return datetime.fromtimestamp(x, timezone.utc)
    try:
        d = email.utils.parsedate_to_datetime(x)
    except Exception:
        try:
            d = pd.Timestamp(x).to_pydatetime()
        except Exception:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def strip(s, n=None):
    s = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()
    return s[:n] if n else s


class Run:
    """Collects items and transcripts for one run; each source is isolated."""

    def __init__(self, out, lo, hi):
        self.out, self.lo, self.hi = out, lo, hi
        self.items, self.status = [], {}
        os.makedirs(os.path.join(out, "yt"), exist_ok=True)
        os.makedirs(os.path.join(out, "pod"), exist_ok=True)

    def add(self, source, key, published, title, summary="", **kw):
        p = ts(published)
        row = dict(source=source, key=str(key), published_at=p.isoformat() if p else "", fetched_at=NOW,
                   available_at=NOW, title=strip(title, 500), summary=strip(summary, 4000), **kw)
        row["h"] = hashlib.sha1(json.dumps([row["title"], row["summary"], kw.get("text_path")],
                                           ensure_ascii=False).encode()).hexdigest()[:16]
        self.items.append(row)

    def in_window(self, d):
        return d is not None and self.lo <= d < self.hi

    def run(self, name, fn):
        n0, t0 = len(self.items), time.time()
        try:
            msg = fn(self)
            self.status[name] = {"ok": msg is None or str(msg).startswith("skipped"), "items": len(self.items) - n0,
                                 "seconds": round(time.time() - t0), **({"note": msg} if msg else {})}
        except Exception as exc:
            self.status[name] = {"ok": False, "items": len(self.items) - n0, "seconds": round(time.time() - t0),
                                 "error": repr(exc)[:300]}
        print(f"news {name}: {self.status[name]}", flush=True)

    def save_segments(self, sub, key, segs, meta):
        p = os.path.join(sub, re.sub(r"[^A-Za-z0-9_.-]", "_", key)[:120] + ".json.gz")
        with gzip.open(os.path.join(self.out, p), "wt") as fh:
            json.dump({**meta, "segments": segs}, fh, ensure_ascii=False)
        return p


# ----------------------------------------------------------------------------- text sources
def alpaca(R):
    k, s = os.environ.get("ALPACA_API_KEY", "").strip(), os.environ.get("ALPACA_SECRET_KEY", "").strip()
    if not (k and s):
        return "skipped: ALPACA keys not set"
    h = {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s}
    tok, pages = None, 0
    while True:
        q = {"start": R.lo.isoformat().replace("+00:00", "Z"), "end": R.hi.isoformat().replace("+00:00", "Z"),
             "limit": 50, "sort": "asc", "include_content": "false", **({"page_token": tok} if tok else {})}
        d = get("https://data.alpaca.markets/v1beta1/news?" + urllib.parse.urlencode(q), h)
        for a in d.get("news", []):
            R.add("alpaca", a["id"], a.get("created_at"), a.get("headline"), a.get("summary"), kind="text",
                  feed=a.get("source") or "benzinga", tier="text", url=a.get("url"), tickers_src=a.get("symbols") or [],
                  updated_at=a.get("updated_at"))
        tok, pages = d.get("next_page_token"), pages + 1
        if not tok or pages > 400:
            break
        time.sleep(0.35)


def gdelt(R):
    """Titles only. 250 records per request, so the window is cut into slices per query. GDELT rate-limits busy IPs
    harder than its stated 1 request / 5 s, so the spacing is generous."""
    bad = []
    if not SOURCES.get("gdelt_queries"):
        return "skipped: dropped in sources.json (DOC API refuses this IP)"
    for name, q in SOURCES["gdelt_queries"].items():
        a = R.lo
        while a < R.hi:
            b = min(a + timedelta(hours=GDELT_SLICE_H), R.hi)
            time.sleep(GDELT_SLEEP)                          # GDELT asks for at most one request every 5 s
            try:
                d = json.loads(get("https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(
                    {"query": f"{q} sourcelang:english", "mode": "artlist", "format": "json", "maxrecords": 250,
                     "startdatetime": a.strftime("%Y%m%d%H%M%S"), "enddatetime": b.strftime("%Y%m%d%H%M%S")}),
                    raw=True, tries=2, wait=20) or b"{}")
            except Exception as exc:
                bad.append(f"{name} {a:%d %H}: {exc!r}"[:80]); a = b; continue
            for x in d.get("articles", []):
                R.add("gdelt", x["url"], datetime.strptime(x["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc),
                      x.get("title"), kind="text", feed=x.get("domain"), tier="text", url=x["url"], query=name,
                      tickers_src=[])
            a = b
    return f"failed slices {len(bad)}: {bad[:2]}" if bad else None


def gdelt_gkg(R):
    """The raw GDELT GKG 2.1 files (one per 15 min, English, ~4.7 MB zipped): page title + the organisations and themes
    GDELT extracted. A plain download, so it is not subject to the DOC API's rate limit. The probe reads one file
    every GKG_EVERY_H hours and records the fraction it covers (sample_days)."""
    import zipfile
    every = int(os.environ.get("NEWS_GKG_EVERY_H", 3))
    stamps = pd.date_range(R.lo, R.hi - timedelta(minutes=15), freq=f"{every}h")
    n_ok, bad = 0, []
    for t in stamps:
        url = f"https://data.gdeltproject.org/gdeltv2/{t:%Y%m%d%H%M%S}.gkg.csv.zip"
        try:
            z = zipfile.ZipFile(io.BytesIO(get(url, raw=True, tries=2, timeout=120)))
        except Exception as exc:
            bad.append(f"{t:%d %H}: {exc!r}"[:60]); continue
        n_ok += 1
        for line in z.read(z.namelist()[0]).decode("utf-8", "replace").splitlines():
            f = line.split("\t")
            if len(f) < 27:
                continue
            m = re.search(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", f[26])
            orgs = sorted({o.split(",")[0] for o in f[14].split(";") if o})[:15]
            themes = sorted({x.split(",")[0] for x in f[8].split(";") if x})[:8]
            R.add("gdelt_gkg", f[0], datetime.strptime(f[1], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc),
                  m.group(1) if m else "", f"orgs: {'; '.join(orgs)} | themes: {'; '.join(themes)}", kind="text",
                  feed=f[3], tier="text", url=f[4], tone=f[15].split(",")[0], tickers_src=[], sample_days=None)
    covered = n_ok * 15 / 1440                               # days of news the sampled files cover
    for it in R.items:
        if it["source"] == "gdelt_gkg":
            it["sample_days"] = covered
    return f"failed {bad}" if bad else None


def finnhub(R):
    """General news already fetched daily by fund/context_archive.py: read it, no new Finnhub calls."""
    if not os.environ.get("HF_TOKEN"):
        return "skipped: HF_TOKEN not set"
    from huggingface_hub import HfApi, hf_hub_download
    api = HfApi(token=os.environ["HF_TOKEN"])
    repo = f"{api.whoami()['name']}/{os.environ.get('CONTEXT_REPO', 'fund-context-archive')}"
    days = pd.date_range(R.lo.date(), (R.hi + timedelta(days=1)).date())
    files = set(api.list_repo_files(repo, repo_type="dataset"))
    for d in days:
        f = f"days/{d.date()}.parquet"
        if f not in files:
            continue
        X = pd.read_parquet(hf_hub_download(repo, f, repo_type="dataset", local_dir=os.path.join(R.out, "_ctx")))
        for r in X[X.source == "finnhub"].itertuples():
            p = json.loads(r.payload)
            if R.in_window(ts(r.published_at)):
                R.add("finnhub", r.key, r.published_at, p.get("headline"), p.get("summary"), kind="text",
                      feed=p.get("source"), tier="text", url=p.get("url"),
                      tickers_src=[t for t in str(p.get("related") or "").split(",") if t])


def _rss_items(b):
    root = ET.fromstring(b)
    for it in root.iter():
        if it.tag.split("}")[-1] not in ("item", "entry"):
            continue
        f = {c.tag.split("}")[-1]: c for c in it}
        link = f.get("link")
        link = (link.get("href") or link.text) if link is not None else None
        yield {"title": f["title"].text if "title" in f else "", "link": link,
               "date": next((f[k].text for k in ("pubDate", "published", "updated", "date") if k in f), None),
               "summary": next((f[k].text for k in ("description", "summary", "encoded") if k in f), ""),
               "guid": f["guid"].text if "guid" in f else link}


def rss(R):
    bad = []
    for s in [x for x in SOURCES["rss"] if x.get("status") != "dropped"]:
        try:
            b = get(s["url"], raw=True, tries=2)
        except Exception as exc:
            bad.append(f"{s['name']}: {exc!r}"[:70]); continue
        for it in _rss_items(b):
            d = ts(it["date"])
            if not R.in_window(d):
                continue
            R.add("rss", it["guid"] or it["link"], d, it["title"], it["summary"], kind=s["kind"], feed=s["name"], tier=s["tier"],
                  url=it["link"], tickers_src=[])
    return f"failed {bad}" if bad else None


def fedreg(R):
    page, url = 1, None
    while True:
        q = [("per_page", 1000), ("page", page), ("conditions[publication_date][gte]", str(R.lo.date())),
             ("conditions[publication_date][lte]", str((R.hi - timedelta(seconds=1)).date()))] + \
            [("fields[]", f) for f in ("title", "abstract", "agencies", "type", "publication_date", "document_number", "html_url")]
        d = get("https://www.federalregister.gov/api/v1/documents.json?" + urllib.parse.urlencode(q))
        for x in d.get("results", []):
            R.add("fedreg", x["document_number"], x["publication_date"], x["title"],
                  f"[{x.get('type')}; {', '.join(a.get('name') or '' for a in x.get('agencies') or [])}] {x.get('abstract') or ''}",
                  kind="official", feed="Federal Register", tier="d", url=x.get("html_url"), tickers_src=[])
        if not d.get("next_page_url"):
            break
        page += 1


def openfda(R):
    """openFDA lags by days, so the probe reads the last 45 days and records the rate (sample_days)."""
    lo, hi = (R.hi - timedelta(days=45)).strftime("%Y%m%d"), R.hi.strftime("%Y%m%d")
    for ep, field in (("drug/enforcement", "report_date"), ("drug/drugsfda", "submissions.submission_status_date")):
        skip = 0
        while True:
            try:
                d = get(f"https://api.fda.gov/{ep}.json?search={field}:[{lo}+TO+{hi}]&limit=100&skip={skip}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    break
                raise
            for x in d.get("results", []):
                if ep == "drug/enforcement":
                    R.add("openfda", x.get("recall_number"), x.get("report_date"), f"Recall: {x.get('recalling_firm')}",
                          f"{x.get('classification')}: {x.get('product_description', '')[:400]} Reason: {x.get('reason_for_recall', '')}",
                          kind="official", feed="openFDA enforcement", tier="d", sample_days=45, tickers_src=[])
                else:
                    subs = [s for s in x.get("submissions", []) if lo <= s.get("submission_status_date", "") <= hi]
                    prods = ", ".join(sorted({p.get("brand_name", "") for p in x.get("products", [])}))[:200]
                    for s in subs:
                        R.add("openfda", f"{x.get('application_number')}|{s.get('submission_number')}|{s.get('submission_type')}",
                              s.get("submission_status_date"), f"FDA {s.get('submission_type')} {s.get('submission_status')}: {x.get('sponsor_name')}",
                              f"{prods}; {s.get('submission_class_code_description') or ''}", kind="official",
                              feed="openFDA approvals", tier="d", sample_days=45, tickers_src=[])
            skip += 100
            if skip >= d.get("meta", {}).get("results", {}).get("total", 0) or skip >= 1000:
                break


def usaspending(R):
    page = 1
    while page <= 10:
        body = json.dumps({"filters": {"award_type_codes": ["A", "B", "C", "D"],
                                       "time_period": [{"start_date": str(R.lo.date()), "end_date": str((R.hi - timedelta(seconds=1)).date())}],
                                       "award_amounts": [{"lower_bound": 10_000_000}]},
                           "fields": ["Award ID", "Recipient Name", "Award Amount", "Description", "Awarding Agency", "Start Date"],
                           "limit": 100, "page": page}).encode()
        d = get("https://api.usaspending.gov/api/v2/search/spending_by_award/", {"Content-Type": "application/json"}, data=body)
        for x in d.get("results", []):
            R.add("usaspending", x.get("Award ID"), R.lo, f"Award {x.get('Award ID')}: {x.get('Recipient Name')} ${x.get('Award Amount'):,.0f}",
                  f"{x.get('Awarding Agency')}: {x.get('Description') or ''}", kind="official", feed="USAspending", tier="d",
                  tickers_src=[])
        if not d.get("page_metadata", {}).get("hasNext"):
            break
        page += 1
    return "capped at 10 pages" if page > 10 else None


# ----------------------------------------------------------------------------- video
def _yt_list(cid, n=150):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "playlistend": n, "skip_download": True,
            "extractor_args": {"youtubetab": {"approximate_date": [""]}}}
    with yt_dlp.YoutubeDL(opts) as y:
        d = y.extract_info(f"https://www.youtube.com/playlist?list=UU{cid[2:]}", download=False)
    return [{"id": e["id"], "title": e.get("title"), "duration": e.get("duration"),
             "t": ts(e.get("timestamp")), "live": e.get("live_status")} for e in d.get("entries") or []]


def _yt_dlp_subs(vid):
    """Fallback: the auto/manual English captions through yt-dlp (json3)."""
    import yt_dlp
    with tempfile.TemporaryDirectory() as tmp:
        opts = {"quiet": True, "no_warnings": True, "skip_download": True, "writesubtitles": True,
                "writeautomaticsub": True, "subtitleslangs": ["en", "en-US", "en-orig"], "subtitlesformat": "json3",
                "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s")}
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=True)
        fs = [f for f in os.listdir(tmp) if f.endswith(".json3")]
        if not fs:
            return None, None
        ev = json.load(open(os.path.join(tmp, fs[0]))).get("events", [])
        segs = [[e["tStartMs"] / 1000, e.get("dDurationMs", 0) / 1000, "".join(s.get("utf8", "") for s in e["segs"]).strip()]
                for e in ev if e.get("segs")]
        manual = any(l.startswith("en") for l in (info.get("subtitles") or {}))
        return [s for s in segs if s[2]], "manual" if manual else "auto"


def _transcript(vid):
    """(segments [[start, dur, text]], caption_kind, error). Raises RuntimeError when YouTube blocks the IP."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api import _errors as E
    try:
        t = YouTubeTranscriptApi().fetch(vid, languages=["en", "en-US", "en-GB"])
        return [[s.start, s.duration, s.text] for s in t.snippets], "auto" if t.is_generated else "manual", None
    except (E.TranscriptsDisabled, E.NoTranscriptFound) as exc:
        return None, "none", type(exc).__name__
    except (E.RequestBlocked, E.IpBlocked) as exc:
        raise RuntimeError(f"blocked: {type(exc).__name__}")
    except Exception as exc:
        try:
            segs, kind = _yt_dlp_subs(vid)
            return segs, (kind or "none"), None if segs else f"{type(exc).__name__}; yt-dlp found none"
        except Exception as exc2:
            return None, "error", f"{type(exc).__name__} / {type(exc2).__name__}"[:120]


def _yt_audio_whisper(vid):
    """Captions blocked or missing: the audio stream (a different YouTube endpoint) through local whisper."""
    import yt_dlp
    with tempfile.TemporaryDirectory() as tmp:
        opts = {"quiet": True, "no_warnings": True, "noprogress": True, "format": "bestaudio[ext=m4a]/bestaudio",
                "outtmpl": os.path.join(tmp, "a.%(ext)s")}
        with yt_dlp.YoutubeDL(opts) as y:
            y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=True)
        f = os.path.join(tmp, os.listdir(tmp)[0])
        return _whisper_file(f)


def youtube(R):
    """Volumes come from the uploads listing (count and minutes per day, no transcription). Transcripts are fetched
    for a sample of SAMPLE_N videos per channel (in the window if it has them): captions while YouTube allows,
    else (NEWS_YT=whisper, or once captions are blocked) the audio through whisper. The cost report scales the
    sample by minutes per day."""
    only = os.environ.get("NEWS_CHANNELS")
    chans = [c for c in SOURCES["youtube"] if c.get("status") != "dropped" and (not only or c["name"] in only.split("|"))]
    bad, use_whisper = [], os.environ.get("NEWS_YT") == "whisper"
    blocked = "forced whisper" if use_whisper else None
    for c in chans:
        try:
            ups = _yt_list(c["id"])
        except Exception as exc:
            bad.append(f"{c['name']}: list {exc!r}"[:80]); continue
        longf = [u for u in ups if (u["duration"] or 0) >= SHORT_S]
        dated = [u for u in longf if u["t"]]
        win = [u for u in longf if R.in_window(u["t"])]
        if len(win) >= PROBE_MIN:
            mode, per_day, min_day = "window", len(win) / ((R.hi - R.lo).total_seconds() / 86400), \
                sum(u["duration"] for u in win) / 60 / ((R.hi - R.lo).total_seconds() / 86400)
        else:                                                # low volume: uploads over the last 30 days of the listing
            lb = [u for u in dated if u["t"] >= now - timedelta(days=30)]
            mode, per_day, min_day = "rate30", len(lb) / 30, sum(u["duration"] for u in lb) / 60 / 30
        if c.get("status") == "archive" and not os.environ.get("NEWS_ALL"):
            for u in win:                                    # metadata only: no transcript, no LLM
                R.add("youtube", u["id"], u["t"], u["title"], kind="video", feed=c["name"], tier=c["tier"],
                      channel_id=c["id"], url=f"https://www.youtube.com/watch?v={u['id']}", duration_s=u["duration"],
                      live=u["live"], caption_kind="archive", text_path=None, probe_mode=mode,
                      feed_items_per_day=per_day, feed_minutes_per_day=min_day, tickers_src=[])
            continue
        pool = win if win else longf
        pick = [pool[int(i * len(pool) / SAMPLE_N)] for i in range(min(SAMPLE_N, len(pool)))]
        for u in pick:
            time.sleep(YT_SLEEP)
            segs, kind, err, audio_s, wall = None, None, None, None, None
            if not blocked:
                try:
                    segs, kind, err = _transcript(u["id"])
                except RuntimeError as exc:
                    blocked = str(exc)
            if blocked:
                try:
                    segs, audio_s, wall = _yt_audio_whisper(u["id"]); kind, err = "whisper", None
                except Exception as exc:
                    kind, err = "error", repr(exc)[:150]
            path = R.save_segments("yt", u["id"], segs, {"video_id": u["id"], "channel": c["name"]}) if segs else None
            R.add("youtube", u["id"], u["t"], u["title"], kind="video", feed=c["name"], tier=c["tier"],
                  channel_id=c["id"], url=f"https://www.youtube.com/watch?v={u['id']}", duration_s=u["duration"],
                  live=u["live"], caption_kind=kind, error=err, text_path=path, probe_mode=mode,
                  feed_items_per_day=per_day, feed_minutes_per_day=min_day, n_listed=len(ups),
                  n_shorts=len(ups) - len(longf), audio_s=audio_s, whisper_s=wall, tickers_src=[])
    note = f"captions blocked ({blocked}), whisper used after that" if blocked and not use_whisper else None
    return "; ".join(x for x in (note, f"failed {bad}" if bad else None) if x) or None


# ----------------------------------------------------------------------------- podcasts
def _parse_caption_file(b, ctype):
    t = b.decode("utf-8", "replace")
    if "json" in ctype or t.lstrip().startswith("{"):
        d = json.loads(t)
        return [[s.get("startTime", 0), s.get("endTime", 0) - s.get("startTime", 0), s.get("body", "")]
                for s in d.get("segments", []) if s.get("body")]
    if "vtt" in ctype or "srt" in ctype or "-->" in t:
        segs, cur = [], None
        for line in t.splitlines():
            m = re.match(r"(\d+:)?(\d+):(\d+)[.,](\d+)\s*-->\s*(\d+:)?(\d+):(\d+)[.,](\d+)", line.strip())
            if m:
                g = m.groups()
                a = int((g[0] or "0:")[:-1]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000
                b_ = int((g[4] or "0:")[:-1]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7]) / 1000
                cur = [a, b_ - a, ""]; segs.append(cur)
            elif cur is not None and line.strip() and not line.strip().isdigit() and line.strip() != "WEBVTT":
                cur[2] = (cur[2] + " " + re.sub(r"<[^>]+>", "", line.strip())).strip()
        return [s for s in segs if s[2]]
    return [[0, 0, strip(t)]]                                # html / plain text: one block


def _whisper_file(path):
    """Local whisper on an audio file, first WHISPER_MAX_S seconds (the cost report works in tokens per minute)."""
    import av
    import mlx_whisper
    import numpy as np
    c = av.open(path)
    rs = av.AudioResampler(format="s16", layout="mono", rate=16000)
    pcm, n = [], 0
    for fr in c.decode(audio=0):
        for o in rs.resample(fr):
            a = o.to_ndarray().reshape(-1); pcm.append(a); n += len(a)
        if n >= WHISPER_MAX_S * 16000:
            break
    audio = (np.concatenate(pcm).astype(np.float32) / 32768.0)[:WHISPER_MAX_S * 16000]
    t0 = time.time()
    out = mlx_whisper.transcribe(audio, path_or_hf_repo=WHISPER, language="en", verbose=None)
    return [[s["start"], s["end"] - s["start"], s["text"].strip()] for s in out["segments"]], len(audio) / 16000, time.time() - t0


def _whisper(url):
    with tempfile.NamedTemporaryFile(suffix=".audio") as fh:
        fh.write(get(url, raw=True, timeout=600)); fh.flush()
        return _whisper_file(fh.name)


def _secs(x):
    """itunes:duration: seconds, MM:SS or HH:MM:SS."""
    try:
        parts = [float(p) for p in str(x).strip().split(":")]
    except (TypeError, ValueError):
        return None
    v = 0.0
    for p in parts:
        v = v * 60 + p
    return v or None


def podcasts(R):
    bad = []
    for s in [x for x in SOURCES["podcasts"] if x.get("status") != "dropped"]:
        try:
            root = ET.fromstring(get(s["feed"], raw=True, tries=2, timeout=120))
        except Exception as exc:
            bad.append(f"{s['name']}: {exc!r}"[:80]); continue
        eps = []
        for it in root.iter("item"):
            f = {c.tag.split("}")[-1]: c for c in it}
            trs = [c for c in it if c.tag.endswith("}transcript")]
            enc = f.get("enclosure")
            eps.append({"title": f["title"].text if "title" in f else "", "t": ts(f["pubDate"].text) if "pubDate" in f else None,
                        "guid": (f["guid"].text if "guid" in f else None) or (enc.get("url") if enc is not None else ""),
                        "audio": enc.get("url") if enc is not None else None,
                        "duration": f["duration"].text if "duration" in f else None,
                        "transcripts": [(c.get("url"), c.get("type") or "") for c in trs]})
        eps = [e for e in eps if e["t"]]
        eps.sort(key=lambda e: e["t"], reverse=True)
        last60 = [e for e in eps if e["t"] >= now - timedelta(days=60)]
        durs = [d for d in (_secs(e["duration"]) for e in last60) if d]
        per_day = len(last60) / 60
        min_day = per_day * (sum(durs) / len(durs) / 60 if durs else 0.0)
        win = [e for e in eps if R.in_window(e["t"])]
        has_tr = any(e["transcripts"] for e in eps[:5])
        mode = "window" if len(win) >= 2 else "rate60"
        pool = win if len(win) >= 2 else eps
        pick = pool[:(SAMPLE_N if has_tr else 1)]
        for e in pick:
            segs, kind, err, audio_s, wall = None, None, None, None, None
            try:
                if e["transcripts"]:
                    url, ctype = sorted(e["transcripts"], key=lambda x: ("json" not in x[1], "vtt" not in x[1], "srt" not in x[1]))[0]
                    segs, kind = _parse_caption_file(get(url, raw=True, tries=2), ctype), "feed"
                elif e["audio"]:
                    segs, audio_s, wall = _whisper(e["audio"])
                    kind = "whisper"
            except Exception as exc:
                err = repr(exc)[:200]
            path = R.save_segments("pod", e["guid"], segs, {"show": s["name"], "title": e["title"]}) if segs else None
            R.add("podcast", e["guid"], e["t"], e["title"], kind="podcast", feed=s["name"], tier=s["tier"], url=e["audio"],
                  duration_s=_secs(e["duration"]), caption_kind=kind, error=err, text_path=path, probe_mode=mode,
                  feed_items_per_day=per_day, feed_minutes_per_day=min_day,
                  audio_s=audio_s, whisper_s=wall, tickers_src=[])
    return f"failed {bad}" if bad else None


# gdelt and gdelt_gkg were dropped after the probe (sources.json "apis"); they run only when named in NEWS_SOURCES
DEFAULT_OFF = {"gdelt", "gdelt_gkg"}
FNS = {"alpaca": alpaca, "gdelt": gdelt, "gdelt_gkg": gdelt_gkg, "finnhub": finnhub, "rss": rss, "fedreg": fedreg, "openfda": openfda,
       "usaspending": usaspending, "podcasts": podcasts, "youtube": youtube}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="write to fund_news_probe/, push nothing")
    ap.add_argument("--since"); ap.add_argument("--until")
    a = ap.parse_args()
    if not a.probe:
        raise SystemExit("only --probe is implemented (Phase 0); the daily archive comes after the source list is chosen")
    lo = datetime.fromisoformat(a.since).replace(tzinfo=timezone.utc)
    hi = datetime.fromisoformat(a.until).replace(tzinfo=timezone.utc)
    out = os.path.join(ROOT, "fund_news_probe")
    R = Run(out, lo, hi)
    only = [x for x in os.environ.get("NEWS_SOURCES", "").split(",") if x]
    for name, fn in FNS.items():
        if (name in only) if only else (name not in DEFAULT_OFF):
            R.run(name, fn)
    X = pd.DataFrame(R.items)
    tag = "_".join(only) if only else "all"
    X.to_parquet(os.path.join(out, f"items_{tag}.parquet"), index=False)
    json.dump({"window": [str(lo), str(hi)], "fetched_at": NOW, "status": R.status},
              open(os.path.join(out, f"manifest_{tag}.json"), "w"), indent=1)
    print(f"news probe: {len(X)} items → {out}", flush=True)


if __name__ == "__main__":
    main()
