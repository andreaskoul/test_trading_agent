"""Shadow book C10 · per-trade lifecycle (PROTOCOL_fund.md, Amendment 7). Never traded before Protocol 7.

    python fund/lifecycle.py desk     # weekly shadow stage: each fund-book name's event, horizon, kill conditions
    python fund/lifecycle.py daily    # after each close: news kill checks, then rebuild the book from its inputs
    python fund/lifecycle.py replay   # mechanical check: H = 5, no barriers, no news exits vs the weekly book
    python fund/lifecycle.py trade [--plan]   # Protocol 7: decide live before the close and trade the account

Each week's fund book is a cohort. Every position keeps its own life:

* Horizon (vertical barrier), from a pre-registered table, not an LLM guess. The desk's one call per name
  classifies the driving event, dates its first report and any upcoming catalyst, and writes 1-3
  falsifiable kill conditions. H = H_type - news_age (trading days since the first report), clamped to
  3..20; a dated catalyst gives trading days to the catalyst + 1. H_type - news_age <= 2: stale, not entered.
* Stop and target (horizontal barriers), on hedged residual returns e = r - beta x r_SPY, at the close:
  sigma_e = EWMA (span 60) of e to the entry close, floored at 0.75 x the 252-day std, frozen at entry;
  W = sigma_e x sqrt(H). Exit when R = side x sum(e since entry) <= -2.0 W (stop) or >= +3.0 W (target),
  never on the entry day. After a stop, no same-side re-entry for 5 trading days without a new event
  of at least the same |score|; after a target, not without a new event.
* News exit: each day, only stories new since the last check go to a checker that classifies each kill
  condition as matched / partial / not, quoting the article, in three independent passes (two
  wordings, one with the articles shuffled). Matched in >= 2 passes: exit. Partial or matched in >= 2: halve.
  New hard-number news in the position's direction in >= 2 passes: once per lot, up to 1.5x the entry
  weight (10% of NAV at most).
* Book across weeks: carried lots keep their weight (rebalanced only when the caps move them by more than
  25%). A re-selected name with a new event extends to max(remaining, new H) at max(old, new) weight; the
  same story is not renewed; an opposite view closes the lot. At most 10 a side (carried names ranked by
  |w| x share of horizon left, new ones by |w| - 10 bp), then the champion's caps (sector net 30%, dollar
  net 10% of stock gross, gross incl. SPY 1.8) and SPY re-hedged on a trading day when |net beta| > 10%
  of gross, and always on cohort days.
* Accounting: a self-financing book on $100,000, marked at official (total-return) closes; cash earns the
  3-month bill; 5 bp per side on every trade, the hedge included. Daily returns are frozen when first
  seen, and every LLM output is logged, so a rebuild from the inputs gives the same NAV to the cent.

Files (fund_state/<mode>/): <asof>/lifecycle.json (desk), lifecycle/returns.csv (frozen daily returns),
lifecycle/entries.json (frozen entry volatility), lifecycle/news/<day>.json (kill checks),
lifecycle/state.json (lots, events, daily NAV), lifecycle/checks.json (mechanical gates).
"""

import glob
import io
import json
import math
import os
import random
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from common import MODE, P7_START, STATE, asof_from_env, llm, load, news_cutoff, require, save, save_prompts

mode = sys.argv[1]
assert mode in ("desk", "daily", "replay", "trade"), mode
LC = os.path.join(STATE, MODE, "lifecycle")
os.makedirs(os.path.join(LC, "news"), exist_ok=True)

# ---- pre-registered parameters (Amendment 7)
EVENTS = {"earnings": 15, "guidance": 15, "capital_return": 15, "analyst_revisions": 10, "legal_regulatory": 7,
          "product_launch": 5, "partnership": 5, "leadership": 5, "macro_readthrough": 5, "mna_rumour": 5,
          "dated_catalyst": None, "other": 5}
H_MIN, H_MAX, STALE_AT = 3, 20, 2
STOP_K, TARGET_K, SPAN, FLOOR = 2.0, 3.0, 60, 0.75
COOLDOWN, BAND, N_SIDE, NEW_COST = 5, 0.25, 10, 0.001
SECTOR_CAP, DOLLAR_CAP, GROSS_CAP, REHEDGE, NAME_CAP, UP = 0.30, 0.10, 1.8, 0.10, 0.10, 1.5
COST, CAPITAL, PASSES = 5e-4, 100_000.0, 3
# Protocol 7: from this session on the book trades. Each day's decision is taken live (news at T-20 min,
# prices at T-3 min), logged in lifecycle/live/<day>.json and applied as logged when the day is rebuilt.
NEWS_AT, PRICES_AT = 1200, 180                      # seconds before the close
LIVE = os.path.join(LC, "live")


# ======================================================================= desk (weekly)
def desk():
    import infoflow
    import broker
    require("OPENROUTER_API_KEY", "HF_TOKEN")
    asof = asof_from_env()
    cutoff = news_cutoff(asof).tz_localize("UTC")
    book = load(asof, "book.json")
    if book.get("status") not in ("ok", "degraded_hold"):
        save(asof, "lifecycle.json", {"asof": str(asof.date()), "status": "no_book", "names": {}}); return
    fund = {t: w for t, w in book["books"]["fund"].items() if t != "SPY"}
    memos = load(asof, "analysts.json")["memos"]
    s_, cal = broker.api("GET", f"/v2/calendar?start={(asof - pd.Timedelta(days=130)).date()}&end={(asof + pd.Timedelta(days=70)).date()}")
    assert s_ == 200 and cal, f"calendar unavailable: {s_}"
    days = [pd.Timestamp(c["date"]) for c in cal]
    t0 = next(d for d in days if d > asof)                 # entry: the execution day's close
    A = infoflow.news(cutoff - pd.Timedelta(days=30), cutoff)
    SYSTEM = f"""You classify the news event behind ONE stock position of a long-short fund, as of {cutoff:%Y-%m-%d %H:%M} UTC.
You get the analyst's thesis and the firm's headlines of the last 30 days (oldest first). Use only them.
- event_type: the single event the thesis rests on, one of {sorted(EVENTS)}.
  Use dated_catalyst only for a scheduled future event (earnings date, FDA decision, vote, court date) the
  thesis is positioned for; use earnings/guidance/capital_return/analyst_revisions/legal_regulatory/product_launch/
  partnership/leadership/macro_readthrough/mna_rumour for news that has already happened; other if none fits.
- first_reported: the date (YYYY-MM-DD) the headlines FIRST report that event (the earliest matching headline).
- catalyst_date: the scheduled date for dated_catalyst, else null.
- kill_conditions: 1-3 falsifiable conditions that, if a later news article reported them, would END the thesis.
  Each must be observable in a headline or article (e.g. "company cuts FY guidance", "FDA issues a CRL",
  "deal terminated"), not a price move, not an opinion.
Return JSON only: {{"event_type": str, "driving_event": str (<= 20 words), "first_reported": "YYYY-MM-DD",
"catalyst_date": "YYYY-MM-DD" or null, "kill_conditions": [str (<= 25 words)]}}"""

    def one(t):
        m = (memos.get(t) or {}).get("memo") or {}
        g = A[A["sym"] == t].sort_values("published")
        heads = [f"{p:%Y-%m-%d} {pub}: {h}" for p, pub, h in zip(g["published"], g["publisher"], g["t"])]
        heads = heads[-60:]
        user = (f"Stock {t}, position {'LONG' if fund[t] > 0 else 'SHORT'}.\nTHESIS: {m.get('thesis')}\n"
                f"Catalysts named by the analyst: {json.dumps(m.get('catalysts'))}\nDrivers: {json.dumps(m.get('drivers'))}\n\n"
                "HEADLINES (last 30 days, oldest first):\n" + ("\n".join(heads) or "none in the archive"))
        lo = (cutoff - pd.Timedelta(days=91)).date()

        def check(o):
            if o.get("event_type") not in EVENTS:
                return f"event_type must be one of {sorted(EVENTS)}"
            try:
                fr = pd.Timestamp(o["first_reported"]).date()
            except Exception:
                return "first_reported must be YYYY-MM-DD"
            if not lo <= fr <= cutoff.date():
                return f"first_reported must be between {lo} and {cutoff.date()}"
            kc = o.get("kill_conditions")
            if not isinstance(kc, list) or not 1 <= len(kc) <= 3 or not all(isinstance(x, str) and x.strip() for x in kc):
                return "kill_conditions must be 1-3 non-empty strings"
            if o.get("catalyst_date") is not None:
                try:
                    pd.Timestamp(o["catalyst_date"])
                except Exception:
                    return "catalyst_date must be YYYY-MM-DD or null"
            return None

        st, out, meta, err = llm(SYSTEM, user, check)
        rec = {"status": st, "error": err, "weight": fund[t], "out": out, "provider": meta.get("provider"), "user": user}
        if st == "ok":
            fr = pd.Timestamp(out["first_reported"])
            age = sum(1 for d in days if fr < d <= t0)
            cat = pd.Timestamp(out["catalyst_date"]) if out.get("catalyst_date") else None
            if out["event_type"] == "dated_catalyst" and cat is not None and cat > t0 and cat in days \
                    and (n_to := sum(1 for d in days if t0 < d <= cat)) <= H_MAX:
                h_raw, why = n_to + 1, f"dated catalyst {cat.date()}: {n_to} trading days + 1"
            else:
                typ = "other" if out["event_type"] == "dated_catalyst" else out["event_type"]
                h_raw, why = EVENTS[typ] - age, f"{typ} H {EVENTS[typ]} - news age {age}"
            rec.update(news_age=age, H_raw=h_raw, H=int(min(max(h_raw, H_MIN), H_MAX)), stale=bool(h_raw <= STALE_AT), why=why,
                       kill_conditions=out["kill_conditions"], first_reported=str(fr.date()))
        print(f"lifecycle desk {t}: {st}" + (f" {out['event_type']}, age {rec['news_age']}, H {rec['H']}"
                                             f"{' STALE' if rec['stale'] else ''}" if st == "ok" else f" ({err})"), flush=True)
        return t, rec

    with ThreadPoolExecutor(6) as ex:
        names = dict(ex.map(one, sorted(fund)))
    save_prompts(asof, "lifecycle", [{"ticker": t, "system": SYSTEM, "user": r.pop("user")} for t, r in names.items()])
    ok = sum(r["status"] == "ok" for r in names.values())
    save(asof, "lifecycle.json", {"asof": str(asof.date()), "status": "ok", "entry_day": str(t0.date()), "names": names})
    print(f"lifecycle desk: {ok}/{len(names)} classified; {sum(r.get('stale', False) for r in names.values())} stale")


# ======================================================================= inputs for the engine
def cohorts(replay=False):
    """Every week with a book and (unless replay) a lifecycle desk output: entry day, weights, names."""
    out = []
    for wd in sorted(glob.glob(os.path.join(STATE, MODE, "20*"))):
        bp, lp = os.path.join(wd, "book.json"), os.path.join(wd, "lifecycle.json")
        if not os.path.exists(bp):
            continue
        book = json.load(open(bp))
        if book.get("status") not in ("ok", "degraded_hold"):
            continue
        if replay:
            out.append({"asof": os.path.basename(wd), "w": book["books"]["fund"], "names": {}, "scores": {}}); continue
        if not os.path.exists(lp):
            continue
        L = json.load(open(lp))
        if L.get("status") != "ok":
            continue
        sc = book.get("scores", {}).get("fund") or json.load(open(os.path.join(wd, "redteam.json"))).get("final_score", {})
        S = pd.DataFrame(json.load(open(os.path.join(wd, "screen.json")))["rows"]).set_index("ticker")
        out.append({"asof": os.path.basename(wd), "entry_day": L["entry_day"], "w": book["books"]["fund"], "names": L["names"],
                    "scores": sc, "beta": (S["beta_hedge"] if "beta_hedge" in S else S["beta60"]).fillna(1.0).to_dict(),
                    "sector": S["GICS Sector"].fillna("Unknown").to_dict()})
    return out


def closes(tickers, start, end):
    """Daily closes adjusted for splits and dividends: Alpaca's consolidated (SIP) bars, which carry the official
    close and are queryable once 15 minutes old; yfinance only for a ticker Alpaca does not return."""
    import broker
    stop = min(pd.Timestamp(end) + pd.Timedelta(days=1), pd.Timestamp.now(tz="UTC").tz_localize(None) - pd.Timedelta(minutes=16))
    rows, token = [], None
    syms = ",".join(sorted(tickers))
    while True:
        q = (f"/v2/stocks/bars?symbols={syms}&timeframe=1Day&adjustment=all&feed=sip&limit=10000"
             f"&start={pd.Timestamp(start).date()}&end={stop.strftime('%Y-%m-%dT%H:%M:%SZ')}" + (f"&page_token={token}" if token else ""))
        s_, b = broker.api("GET", q, base=broker.DATA)
        if s_ != 200:
            print(f"lifecycle: Alpaca bars unavailable ({s_}); yfinance for all", flush=True); break
        for t, xs in (b.get("bars") or {}).items():
            rows += [{"date": pd.Timestamp(x["t"][:10]), "ticker": t, "close": float(x["c"])} for x in xs]
        token = b.get("next_page_token")
        if not token:
            break
    px = pd.DataFrame(rows).pivot_table(index="date", columns="ticker", values="close") if rows else pd.DataFrame()
    miss = sorted(set(tickers) - set(px.columns))
    if miss:
        import yfinance as yf
        y = yf.download([t.replace(".", "-") for t in miss], start=pd.Timestamp(start), end=pd.Timestamp(end) + pd.Timedelta(days=1),
                        progress=False, auto_adjust=True)["Close"]
        y = y if isinstance(y, pd.DataFrame) else y.to_frame(miss[0].replace(".", "-"))
        y.columns = [c.replace("-", ".") for c in y.columns]
        y.index = pd.to_datetime(y.index).tz_localize(None)
        print(f"lifecycle: yfinance for {miss}", flush=True)
        px = pd.concat([px, y], axis=1)
    return px.sort_index()


def returns(tickers, start):
    """Frozen daily total-return returns from `start` to the last complete session; new days appended, never rewritten."""
    p = os.path.join(LC, "returns.csv")
    R = pd.read_csv(p, parse_dates=["date"]) if os.path.exists(p) else pd.DataFrame(columns=["date", "ticker", "ret"])
    have = {t: set(g["date"]) for t, g in R.groupby("ticker")}
    from zoneinfo import ZoneInfo
    now_et = datetime.now(ZoneInfo("America/New_York"))
    last_ok = pd.Timestamp(now_et.date()) - (pd.Timedelta(days=0) if now_et.hour >= 17 else pd.Timedelta(days=1))
    r = closes(tickers, pd.Timestamp(start) - pd.Timedelta(days=10), last_ok).pct_change()
    new = []
    for t in r.columns:
        s_ = r[t].dropna()
        for d, v in s_[(s_.index >= pd.Timestamp(start)) & (s_.index <= last_ok)].items():
            if d not in have.get(t, set()):
                new.append({"date": d, "ticker": t, "ret": float(v)})
    if new:
        R = pd.concat([R, pd.DataFrame(new)], ignore_index=True).sort_values(["date", "ticker"])
        R.to_csv(p, index=False)
    return R.pivot_table(index="date", columns="ticker", values="ret")


def entry_vol(asof, t, day, beta, upto=None):
    """sigma_e frozen at entry: EWMA (span 60) of residual returns to the entry close, floored at 0.75 x 252-day std."""
    p = os.path.join(LC, "entries.json")
    E = json.load(open(p)) if os.path.exists(p) else {}
    k = f"{asof}|{t}|{day}"
    if k not in E:
        end = pd.Timestamp(upto or day)               # a live entry: history to the previous close
        px = closes({t, "SPY"}, end - pd.Timedelta(days=420), end)
        r = px.loc[:end].pct_change().dropna()
        e = r[t] - beta * r["SPY"]
        ew, sd = float(e.ewm(span=SPAN).std().iloc[-1]), float(e.iloc[-252:].std())
        E[k] = {"beta": beta, "sigma_ewma": ew, "sigma_252": sd, "sigma_e": max(ew, FLOOR * sd), "n_days": int(len(e))}
        json.dump(E, open(p, "w"), indent=0, sort_keys=True)
    return E[k]


def rf_daily():
    try:
        with urllib.request.urlopen("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3", timeout=60) as r:
            s = pd.read_csv(io.BytesIO(r.read()), na_values=".")
        s.columns = ["date", "v"]
        s = s.assign(date=pd.to_datetime(s.date)).set_index("date")["v"].dropna() / 100
        p = os.path.join(LC, "rf.csv")
        old = pd.read_csv(p, parse_dates=["date"]).set_index("date")["v"] if os.path.exists(p) else pd.Series(dtype=float)
        s = pd.concat([old, s[~s.index.isin(old.index)]]).sort_index()        # frozen once seen
        s.rename("v").to_csv(p, index_label="date")
        return s
    except Exception:
        p = os.path.join(LC, "rf.csv")
        return pd.read_csv(p, parse_dates=["date"]).set_index("date")["v"] if os.path.exists(p) else pd.Series(dtype=float)


# ======================================================================= news kill checks
CHECK_A = """You check new news against a stock position's pre-registered exit conditions. You do not judge the
position, the stock or its price: only whether an article below REPORTS what a condition describes.
Only events that HAPPENED AFTER the position was opened count. An article that recaps, analyses or comments
on something that happened before (an earnings report, a deal, a rating already known at entry) counts as
nothing, however recent the article is.
For each condition: "matched" if an article plainly reports it; "partial" if an article reports part of it or a
clear step towards it; "not" otherwise. Quote the article's words and give its number for matched or partial.
Separately: does any article report a NEW, material, hard-number event that happened after the position was
opened (results, a guidance change, a contract or deal with a figure, a buyback or dividend change) and that
supports the position's direction? Recaps, previews, price targets, ratings and opinion pieces do not count.
Return JSON only: {"conditions": [{"id": int, "status": "matched"|"partial"|"not", "quote": str, "article": int or null}],
"hard_news_same_direction": {"present": bool, "quote": str, "article": int or null}}"""
CHECK_B = """Below are exit conditions written when a position was opened, and articles published since the last
check. Decide for each condition whether the articles show it has happened (matched), partly happened or begun
(partial), or not (not), counting only events that took place after the position was opened: coverage of
earlier events, however fresh the article, is not evidence. Base every decision on what an article states,
never on inference or prices, and cite the article number and its words. Also report whether any article gives
a new, material, quantified company event that occurred after the opening (earnings, a guidance change, an order
or deal with a number, a buyback or dividend change) in the position's favour; previews, recaps, ratings and
price targets are not such events.
Return JSON only: {"conditions": [{"id": int, "status": "matched"|"partial"|"not", "quote": str, "article": int or null}],
"hard_news_same_direction": {"present": bool, "quote": str, "article": int or null}}"""


def finnhub_news(t, lo, hi):
    key = os.environ["FINNHUB_API_KEY"]
    url = f"https://finnhub.io/api/v1/company-news?symbol={t.replace('.', '-')}&from={lo.date()}&to={hi.date()}&token={key}"
    for k in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                arts = json.load(r)
            time.sleep(1.05)
            return [a for a in arts if lo.timestamp() < a.get("datetime", 0) <= hi.timestamp()]
        except Exception:
            time.sleep(5 * (k + 1))
    return None


def kill_check(day, close_ts, lots, seen, news_dir=None):
    """One day's checks for the open lots, on news published up to close_ts; logged to lifecycle/news/<day>.json
    (a plan run writes elsewhere) and never rerun."""
    news_dir = news_dir or os.path.join(LC, "news")
    os.makedirs(news_dir, exist_ok=True)
    p = os.path.join(news_dir, f"{day.date()}.json")
    if os.path.exists(p):
        return json.load(open(p))
    require("OPENROUTER_API_KEY", "FINNHUB_API_KEY")
    hi = pd.Timestamp(close_ts, unit="s", tz="UTC")
    res, prompts = {}, []

    def one(lot):
        t = lot["ticker"]
        lo = pd.Timestamp(lot.get("news_until") or lot["entry_close_ts"], unit="s", tz="UTC")
        arts = finnhub_news(t, lo, hi)
        if arts is None:
            return lot["id"], {"status": "news_unavailable"}
        arts = sorted([a for a in arts if norm(a.get("headline")) not in seen.get(lot["id"], set())],
                      key=lambda a: a["datetime"])[-25:]
        if not arts:
            return lot["id"], {"status": "no_new_news", "news_until": int(hi.timestamp())}
        listing = lambda xs: "\n".join(f"[{i}] {datetime.fromtimestamp(a['datetime'], timezone.utc):%Y-%m-%d %H:%M} "
                                       f"{a.get('source')}: {a.get('headline')} :: {(a.get('summary') or '')[:300]}"
                                       for i, a in enumerate(xs))
        conds = "\n".join(f"{i}. {c}" for i, c in enumerate(lot["kill_conditions"]))
        shuffled = arts[:]
        random.Random(f"{t}|{day.date()}").shuffle(shuffled)
        passes = []
        for k, (sysp, xs) in enumerate(((CHECK_A, arts), (CHECK_B, arts), (CHECK_A, shuffled))):
            user = (f"Stock {t}, position {'LONG' if lot['side'] > 0 else 'SHORT'}, opened at the close of {lot['entry_day']} "
                    f"(US market close). Only events after that close count.\nEXIT CONDITIONS:\n{conds}\n\n"
                    f"ARTICLES (published {lo:%Y-%m-%d %H:%M} to {hi:%Y-%m-%d %H:%M} UTC):\n{listing(xs)}")

            def chk(o, n=len(xs)):
                cs = o.get("conditions")
                if not isinstance(cs, list) or sorted(c.get("id") for c in cs) != list(range(len(lot["kill_conditions"]))):
                    return "one entry per condition id"
                for c in cs:
                    if c.get("status") not in ("matched", "partial", "not"):
                        return "status must be matched, partial or not"
                    if c["status"] != "not" and not (isinstance(c.get("article"), int) and 0 <= c["article"] < n and c.get("quote")):
                        return "matched/partial needs an article number and a quote"
                hn = o.get("hard_news_same_direction")
                return None if isinstance(hn, dict) and isinstance(hn.get("present"), bool) else "hard_news_same_direction missing"

            st, out, meta, err = llm(sysp, user, chk)
            prompts.append({"ticker": t, "pass": k, "system": sysp, "user": user})
            passes.append({"status": st, "out": out, "error": err, "provider": meta.get("provider")})
        okp = [x["out"] for x in passes if x["status"] == "ok"]
        cnt = lambda pred: max([sum(1 for o in okp if pred(o, i)) for i in range(len(lot["kill_conditions"]))], default=0)
        matched = cnt(lambda o, i: next(c for c in o["conditions"] if c["id"] == i)["status"] == "matched")
        partial = cnt(lambda o, i: next(c for c in o["conditions"] if c["id"] == i)["status"] != "not")
        hard = sum(1 for o in okp if o["hard_news_same_direction"]["present"])
        verdict = "exit" if matched >= 2 else "reduce" if partial >= 2 else "increase" if hard >= 2 else "hold"
        print(f"kill check {day.date()} {t}: {len(arts)} new articles -> {verdict}", flush=True)
        return lot["id"], {"status": "checked", "verdict": verdict, "passes_ok": len(okp), "matched": matched,
                           "partial": partial, "hard": hard, "news_until": int(hi.timestamp()),
                           "headlines": [norm(a.get("headline")) for a in arts], "passes": passes,
                           "max_published": max(a["datetime"] for a in arts)}

    with ThreadPoolExecutor(4) as ex:
        res = dict(ex.map(one, lots))
    rec = {"day": str(day.date()), "close_ts": close_ts, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "lots": res}
    json.dump(rec, open(p, "w"), indent=1)
    if prompts:
        import gzip
        with gzip.open(os.path.join(news_dir, f"{day.date()}.prompts.jsonl.gz"), "wt") as fh:
            for r in prompts:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rec


def norm(s):
    return " ".join("".join(ch for ch in str(s or "").lower() if ch.isalnum() or ch == " ").split())


# ======================================================================= the book
def caps(w, sector, beta):
    """The champion's risk rules (pm_risk.risk, in the same order): sector net, dollar net, then the SPY hedge."""
    w = w.copy()
    sec = pd.Series({t: sector.get(t, "Unknown") for t in w.index})
    for s_, net in w.groupby(sec).sum().items():
        if abs(net) > SECTOR_CAP + 1e-9:
            side = w.index[(sec == s_) & (np.sign(w) == np.sign(net))]
            other = net - w[side].sum()
            w[side] *= (np.sign(net) * SECTOR_CAP - other) / w[side].sum()
    long_, short_ = w[w > 0].sum(), -w[w < 0].sum()
    gross, net = long_ + short_, long_ - short_
    if gross > 0 and abs(net) > DOLLAR_CAP * gross + 1e-9:
        if net > 0:
            w[w > 0] *= short_ * (1 + DOLLAR_CAP) / (1 - DOLLAR_CAP) / long_ if short_ > 0 else 0.0
        else:
            w[w < 0] *= long_ * (1 + DOLLAR_CAP) / (1 - DOLLAR_CAP) / short_ if long_ > 0 else 0.0
        w = w[w != 0]
    spy = -float(sum(v * beta.get(t, 1.0) for t, v in w.items()))
    g = w.abs().sum() + abs(spy)
    if g > GROSS_CAP:
        w, spy = w * GROSS_CAP / g, spy * GROSS_CAP / g
    return w, spy


def trading_days(R):
    return [d for d in R.index if "SPY" in R.columns and not math.isnan(R.at[d, "SPY"])]


def run(replay=False, fetch_news=True, live=None):
    """Rebuild the book from its inputs. Deterministic: the same inputs give the same NAV.

    Days before P7_START: decisions computed at each close (the shadow C10). From P7_START: a completed day applies
    the decisions logged live that day (lifecycle/live/<day>.json); a day without a live log holds (nothing traded).
    live = {"day", "ret", "news_ts", "news_dir"}: after the completed days, decide today on live prices (the trade)."""
    C = cohorts(replay)
    if not C:
        return None
    import broker
    if not replay:
        for c in C:
            c["entry_day"] = pd.Timestamp(c["entry_day"])
    else:
        s_, cal = broker.api("GET", f"/v2/calendar?start={C[0]['asof']}&end={(pd.Timestamp(C[-1]['asof']) + pd.Timedelta(days=20)).date()}")
        days_ = [pd.Timestamp(x["date"]) for x in cal]
        for c in C:
            a = pd.Timestamp(c["asof"])
            c["entry_day"] = next(d for d in days_ if d > a)
            c["exit_day"] = next(d for d in days_ if d >= a + pd.Timedelta(days=8))
    tickers = {"SPY"} | {t for c in C for t in c["w"]}
    R = returns(tickers, C[0]["entry_day"])
    s_, cal_ = broker.api("GET", f"/v2/calendar?start={C[0]['entry_day'].date()}&end={datetime.now(timezone.utc).date()}")
    assert s_ == 200, f"calendar unavailable: {s_}"
    close_of = {pd.Timestamp(x["date"]): int(datetime.combine(pd.Timestamp(x["date"]).date(),
                                                              datetime.strptime(x["close"], "%H:%M").time(), broker.ET).timestamp())
                for x in cal_}
    rf = rf_daily()
    days = [d for d in trading_days(R) if d >= C[0]["entry_day"]]
    if live is not None:
        days = [d for d in days if d < live["day"]]
    seq = [(d, R.loc[d], close_of[d], False) for d in days]
    if live is not None:
        seq.append((live["day"], pd.Series(live["ret"]), live["news_ts"], True))
    logs = {}
    for f in glob.glob(os.path.join(LIVE, "*.json")):
        if not f.endswith(".plan.json"):
            x = json.load(open(f))
            if x.get("status") == "submitted":
                logs[pd.Timestamp(x["day"])] = x
    by_entry = {c["entry_day"]: c for c in C}
    nav, hedge, lots, events, rows, cool, seen, nid = CAPITAL, 0.0, [], [], [], {}, {}, 0
    beta_all = {t: b for c in C for t, b in c.get("beta", {}).items()}
    sector_all = {t: s for c in C for t, s in c.get("sector", {}).items()}
    prev_day = None
    out_live = None
    for d, r, close_ts, is_live in seq:            # close_ts: the session's real close (a live day: the news cutoff)
        act = "compute" if replay or d < P7_START or is_live else ("apply" if d in logs else "hold")
        nav0 = nav
        cash0 = nav0 - sum(L["n"] for L in lots) - hedge
        # 1. mark to today's close
        pnl_lots = pnl_hedge = 0.0
        for L in lots:
            ri = r.get(L["ticker"], np.nan)
            if math.isnan(ri):                      # halted or delisted: marked flat, as score.py does, and logged
                ri = 0.0
                events.append({"day": str(d.date()), "id": L["id"], "ticker": L["ticker"], "action": "no_price",
                               "from": round(L["n"], 2), "to": round(L["n"], 2)})
            pnl_lots += L["n"] * ri
            L["n"] *= 1 + ri
            L["R"] += L["side"] * (ri - L["beta"] * r["SPY"])
            L["days"] += 1
        pnl_hedge = hedge * r["SPY"]
        hedge *= 1 + r["SPY"]
        rf_rate = float(rf.asof(d)) if len(rf) and not math.isnan(rf.asof(d)) else 0.0
        cash_inc = cash0 * rf_rate * ((d - prev_day).days if prev_day is not None else 1) / 360
        nav = nav0 + pnl_lots + pnl_hedge + cash_inc
        cost = 0.0
        traded = False

        def trade(L, new_n, why):
            nonlocal cost, traded
            cost += abs(new_n - L["n"]) * COST
            events.append({"day": str(d.date()), "id": L["id"], "ticker": L["ticker"], "action": why,
                           "from": round(L["n"], 2), "to": round(new_n, 2), "R": round(L["R"], 6), "W": round(L.get("W", 0), 6),
                           "days_held": L["days"]})
            L["n"] = new_n
            traded = True

        # 2. exits and changes at today's close (never on the entry day)
        if act == "apply":                          # Protocol 7: the decisions taken live, as logged
            lg = logs[d]
            acts = {}
            for e in lg["actions"]:
                acts.setdefault(e["id"], e)
            after = {x["id"]: x for x in lg["lots_after"]}
            nf = os.path.join(LC, "news", f"{d.date()}.json")
            news = json.load(open(nf)) if os.path.exists(nf) else {"lots": {}}
            for L in list(lots):
                k = news["lots"].get(L["id"], {})
                if k.get("news_until"):
                    L["news_until"] = k["news_until"]
                seen.setdefault(L["id"], set()).update(k.get("headlines", []))
                if L["id"] not in after:
                    trade(L, 0.0, acts.get(L["id"], {}).get("action", "exit"))
            for lid, x in after.items():
                L = next((y for y in lots if y["id"] == lid), None)
                if L is None:
                    L = {**{k: v for k, v in x.items() if k not in ("w", "n", "R", "days")}, "n": 0.0, "R": 0.0, "days": 0}
                    lots.append(L)
                else:
                    for k in ("H", "kill_conditions", "first_reported", "w0", "reduced", "increased"):
                        if k in x:
                            L[k] = x[k]
                if lid in acts:
                    trade(L, x["w"] * nav, acts[lid]["action"])
            cool = {tuple([k.rsplit("|", 1)[0], int(k.rsplit("|", 1)[1])]): {**v, "until": pd.Timestamp(v["until"]) if v.get("until") else None}
                    for k, v in lg.get("cool", {}).items()}
            if "SPY" in acts:
                cost += abs(lg["hedge_w"] * nav - hedge) * COST
                events.append({"day": str(d.date()), "id": "SPY", "ticker": "SPY", "action": "hedge",
                               "from": round(hedge, 2), "to": round(lg["hedge_w"] * nav, 2)})
                hedge = lg["hedge_w"] * nav
            traded = bool(acts)
        elif act == "hold":
            events.append({"day": str(d.date()), "id": "-", "ticker": "-", "action": "no_live_run", "from": 0, "to": 0})
        elif replay:
            for L in [L for L in lots if L["exit_day"] == d]:
                trade(L, 0.0, "replay_exit")
        else:
            open_ = [L for L in lots if L["days"] >= 1]
            nd = (live or {}).get("news_dir") if is_live else None
            nf = os.path.join(nd or os.path.join(LC, "news"), f"{d.date()}.json")
            news = kill_check(d, close_ts, open_, seen, nd) if (open_ and (fetch_news or is_live)) else \
                (json.load(open(nf)) if os.path.exists(nf) else {"lots": {}})
            for L in open_:
                k = news["lots"].get(L["id"], {})
                if k.get("news_until"):
                    L["news_until"] = k["news_until"]
                seen.setdefault(L["id"], set()).update(k.get("headlines", []))
                if L["R"] <= -STOP_K * L["W"]:
                    trade(L, 0.0, "stop"); cool[(L["ticker"], L["side"])] = {"until": d, "kind": "stop", "score": L["score"],
                                                                         "first_reported": L["first_reported"]}
                elif L["R"] >= TARGET_K * L["W"]:
                    trade(L, 0.0, "target"); cool[(L["ticker"], L["side"])] = {"until": None, "kind": "target", "score": L["score"],
                                                                           "first_reported": L["first_reported"]}
                elif k.get("verdict") == "exit":
                    trade(L, 0.0, "news_exit")
                elif L["days"] >= L["H"]:
                    trade(L, 0.0, "horizon")
                elif k.get("verdict") == "reduce" and not L.get("reduced"):
                    trade(L, L["n"] * 0.5, "news_reduce"); L["reduced"] = True
                elif k.get("verdict") == "increase" and not L.get("increased"):
                    tgt = L["side"] * min(UP * abs(L["w0"]), NAME_CAP) * nav
                    room = GROSS_CAP * nav - sum(abs(x["n"]) for x in lots) - abs(hedge)
                    if abs(tgt) > abs(L["n"]) and abs(tgt) - abs(L["n"]) <= room:
                        trade(L, tgt, "news_increase"); L["increased"] = True
        lots = [L for L in lots if L["n"] != 0.0]
        # 3. this week's cohort enters at today's close
        c = by_entry.get(d) if act == "compute" else None
        if c is not None:
            if replay:
                for t, w in c["w"].items():
                    if t == "SPY":
                        continue
                    nid += 1
                    lots.append({"id": f"{c['asof']}|{t}", "ticker": t, "side": 1 if w > 0 else -1, "n": 0.0, "w0": w, "beta": 0.0,
                                 "R": 0.0, "days": 0, "exit_day": c["exit_day"]})
                    trade(lots[-1], w * nav, "replay_entry")
                cost += abs(c["w"].get("SPY", 0.0) * nav - hedge) * COST
                hedge = c["w"].get("SPY", 0.0) * nav
                traded = False                      # replay: the hedge is the book's own SPY weight
            else:
                cur = {L["ticker"]: L for L in lots}
                cand = {}
                for t, w in c["w"].items():
                    if t == "SPY" or not w:
                        continue
                    info = c["names"].get(t, {})
                    if info.get("status") != "ok" or info.get("stale"):
                        continue
                    side = 1 if w > 0 else -1
                    cd = cool.get((t, side))
                    new_event = cd is None or pd.Timestamp(info["first_reported"]) > pd.Timestamp(cd["first_reported"])
                    if cd and cd["kind"] == "stop" and not (new_event and abs(c["scores"].get(t, 0)) >= abs(cd["score"])) \
                            and sum(1 for x in days if cd["until"] < x <= d) < COOLDOWN:
                        continue
                    if cd and cd["kind"] == "target" and not new_event:
                        continue
                    cand[t] = (w, side, info)
                # re-selection rules for names already held
                target = {}
                for t, L in cur.items():
                    if t in cand:
                        w, side, info = cand.pop(t)
                        if side != L["side"]:
                            trade(L, 0.0, "flip_close")
                            cand[t] = (w, side, info)        # reopens as a new lot below
                            continue
                        if pd.Timestamp(info["first_reported"]) > pd.Timestamp(L["first_reported"]):   # a new event
                            L["H"] = L["days"] + max(L["H"] - L["days"], info["H"])
                            L["kill_conditions"], L["first_reported"] = info["kill_conditions"], info["first_reported"]
                            L["w0"] = side * max(abs(L["n"]) / nav, abs(w))
                    target[t] = L["n"] / nav
                lots = [L for L in lots if L["n"] != 0.0]
                cur = {L["ticker"]: L for L in lots}
                for t, (w, side, info) in cand.items():
                    target[t] = w
                # capacity: carried by |w| x share of horizon left, new by |w| - 10 bp; then the caps
                key = {t: (abs(target[t]) * max(cur[t]["H"] - cur[t]["days"], 0) / cur[t]["H"]) if t in cur else abs(target[t]) - NEW_COST
                       for t in target}
                keep = []
                for sgn in (1, -1):
                    side_ = sorted([t for t in target if np.sign(target[t]) == sgn], key=lambda t: -key[t])
                    keep += side_[:N_SIDE]
                for t in [t for t in cur if t not in keep]:
                    trade(cur[t], 0.0, "capacity")
                w_cap, _ = caps(pd.Series({t: target[t] for t in keep}, dtype=float), sector_all, beta_all)
                for t in keep:
                    tw = float(w_cap.get(t, 0.0))
                    if t in cur:
                        L = cur[t]
                        if tw == 0.0:
                            trade(L, 0.0, "caps")
                        elif abs(tw * nav - L["n"]) > BAND * abs(L["n"]):
                            trade(L, tw * nav, "caps_rebalance")
                    elif tw != 0.0:
                        w, side, info = cand[t]
                        ev = entry_vol(c["asof"], t, str(d.date()), float(c["beta"].get(t, 1.0)), upto=prev_day if is_live else None)
                        nid += 1
                        L = {"id": f"{c['asof']}|{t}", "ticker": t, "side": side, "n": 0.0, "w0": tw, "beta": ev["beta"],
                             "sigma_e": ev["sigma_e"], "H": info["H"], "W": ev["sigma_e"] * math.sqrt(info["H"]), "R": 0.0, "days": 0,
                             "kill_conditions": info["kill_conditions"], "first_reported": info["first_reported"],
                             "score": c["scores"].get(t, 0), "cohort": c["asof"], "entry_day": str(d.date()),
                             "entry_close_ts": close_ts}
                        lots.append(L)
                        trade(L, tw * nav, "entry")
                lots = [L for L in lots if L["n"] != 0.0]
        # 4. SPY hedge: on cohort days always, otherwise on trading days when |net beta| > 10% of gross
        if act == "compute" and not replay:
            stock_beta = sum(L["n"] * L["beta"] for L in lots)
            gross = sum(abs(L["n"]) for L in lots) + abs(hedge)
            if (c is not None or traded) and (c is not None or abs(stock_beta + hedge) > REHEDGE * gross):
                cost += abs(-stock_beta - hedge) * COST
                if abs(-stock_beta - hedge) > 1e-9:
                    events.append({"day": str(d.date()), "id": "SPY", "ticker": "SPY", "action": "hedge",
                                   "from": round(hedge, 2), "to": round(-stock_beta, 2)})
                hedge = -stock_beta
        nav -= cost
        if is_live:
            out_live = {"day": str(d.date()), "nav": nav, "hedge": hedge, "lots": lots,
                        "actions": [e for e in events if e["day"] == str(d.date())],
                        "cool": {f"{k[0]}|{k[1]}": {**v, "until": str(v["until"].date()) if v.get("until") is not None else None}
                                 for k, v in cool.items()}}
            break
        rows.append({"date": str(d.date()), "nav": nav, "pnl_lots": pnl_lots, "pnl_hedge": pnl_hedge, "cash_income": cash_inc,
                     "cost": cost, "r_gross": (pnl_lots + pnl_hedge) / nav0, "r_cost": cost / nav0, "r_cash": cash_inc / nav0,
                     "n_long": sum(L["side"] > 0 for L in lots), "n_short": sum(L["side"] < 0 for L in lots),
                     "stock_gross": sum(abs(L["n"]) for L in lots) / nav, "hedge": hedge / nav,
                     "net_beta": (sum(L["n"] * L["beta"] for L in lots) + hedge) / nav if not replay else None,
                     "traded": bool(traded or c is not None)})
        prev_day = d
    return {"rows": rows, "lots": lots, "events": events, "cohorts": [c["asof"] for c in C], "live": out_live}


def checks(st):
    """Mechanical gates (Amendment 7): reconciliation, limits, triggers, no look-ahead, determinism."""
    out, fails = {}, []
    D = pd.DataFrame(st["rows"])
    if len(D):
        prev = pd.Series([CAPITAL] + list(D["nav"].iloc[:-1]))
        resid = (D["nav"] - prev - D["pnl_lots"] - D["pnl_hedge"] - D["cash_income"] + D["cost"]).abs().max()
        out["reconcile_max_cents"] = float(resid * 100)
        if resid > 0.005:
            fails.append(f"daily P&L does not reconcile to NAV ({resid:.4f} $)")
        T = D[D["traded"]]                          # limits bind when the book trades; prices may drift it between
        bad = T[(T["n_long"] > N_SIDE) | (T["n_short"] > N_SIDE) | (T["stock_gross"] + T["hedge"].abs() > GROSS_CAP + 1e-6)]
        if len(bad):
            fails.append(f"limits broken on {list(bad['date'])}")
    ids = [L["id"] for L in st["lots"]]
    if len(ids) != len(set(ids)) or len({L["ticker"] for L in st["lots"]}) != len(st["lots"]):
        fails.append("duplicate open lots")
    for e in st["events"]:
        if e["action"] == "stop" and not e["R"] <= -STOP_K * e["W"] + 1e-12:
            fails.append(f"stop without trigger: {e}")
        if e["action"] == "target" and not e["R"] >= TARGET_K * e["W"] - 1e-12:
            fails.append(f"target without trigger: {e}")
    for p in sorted(glob.glob(os.path.join(LC, "news", "*.json"))):
        rec = json.load(open(p))
        for k in rec["lots"].values():
            if k.get("max_published") and k["max_published"] > rec["close_ts"]:
                fails.append(f"look-ahead: news after the close used on {rec['day']}")
    gaps = [f"{e['ticker']} {e['day']}" for e in st["events"] if e["action"] == "no_price"]
    out["no_price"] = gaps                          # reported; a name without a price for 3+ sessions needs a person
    from collections import Counter
    long_gaps = [t for t, n in Counter(g.split()[0] for g in gaps).items() if n >= 3]
    if long_gaps:
        fails.append(f"no price for 3+ sessions: {long_gaps} (halted or delisted: decide by hand)")
    out["fails"] = fails
    return out


def daily():
    st = run()
    if st is None:
        print("lifecycle: no cohort with a desk output yet; nothing to do"); return
    again = run(fetch_news=False)                       # determinism: a second rebuild from the logged inputs
    ck = checks(st)
    if [r["nav"] for r in again["rows"]] != [r["nav"] for r in st["rows"]]:
        ck["fails"].append("rebuild from the logged inputs does not reproduce the NAV")
    sp = os.path.join(LC, "state.json")
    if os.path.exists(sp):                              # no retroactive change to days already recorded
        old = {r["date"]: r["nav"] for r in json.load(open(sp))["rows"]}
        drift = [d for d, v in old.items() if any(r["date"] == d and abs(r["nav"] - v) > 0.005 for r in st["rows"])]
        if drift:
            ck["fails"].append(f"recorded days changed on rebuild: {drift[:5]}")
    json.dump({**st, "updated": datetime.now(timezone.utc).isoformat(timespec="seconds")}, open(sp, "w"), indent=0, default=str)
    json.dump(ck, open(os.path.join(LC, "checks.json"), "w"), indent=1)
    last = st["rows"][-1] if st["rows"] else {}
    print(f"lifecycle C10: {len(st['rows'])} days, NAV {last.get('nav', CAPITAL):,.2f}, {len(st['lots'])} open lots, "
          f"{len(st['events'])} events; checks: {'PASS' if not ck['fails'] else ck['fails']}")
    if ck["fails"]:
        raise SystemExit("lifecycle mechanical checks failed: " + "; ".join(ck["fails"]))


def replay():
    """H = the week, no barriers, no news, the book's own weights: the engine's gross return for each week (or the
    part of it that has closed) must equal the book's return computed directly, sum of w x compounded return, within
    1 bp; once score.py has scored the week, it must also match the weekly book (c7_noreview) within 1 bp."""
    st = run(replay=True, fetch_news=False)
    if st is None:
        print("replay: no weeks"); return
    import broker
    D = pd.DataFrame(st["rows"]).set_index("date")
    R = pd.read_csv(os.path.join(LC, "returns.csv"), parse_dates=["date"]).pivot_table(index="date", columns="ticker", values="ret")
    wb_p = os.path.join(STATE, MODE, "performance", "weekly_books.csv")
    W = pd.read_csv(wb_p, dtype={"asof": str}) if os.path.exists(wb_p) and os.path.getsize(wb_p) > 1 else pd.DataFrame(columns=["asof", "book", "gross"])
    res = []
    for a in st["cohorts"]:
        s_, cal = broker.api("GET", f"/v2/calendar?start={(pd.Timestamp(a) + pd.Timedelta(days=1)).date()}&end={(pd.Timestamp(a) + pd.Timedelta(days=20)).date()}")
        days_ = [x["date"] for x in cal]
        t0, t1 = days_[0], next(x for x in days_ if pd.Timestamp(x) >= pd.Timestamp(a) + pd.Timedelta(days=8))
        end = min(t1, D.index[-1])
        if end <= t0:
            continue
        seg = D.loc[(D.index > t0) & (D.index <= end)]
        nav0 = D.loc[t0, "nav"] + D.loc[t0, "cost"]
        g = float((seg["pnl_lots"] + seg["pnl_hedge"]).sum() / nav0)
        w = json.load(open(os.path.join(STATE, MODE, a, "book.json")))["books"]["fund"]
        Rs = R.loc[(R.index > pd.Timestamp(t0)) & (R.index <= pd.Timestamp(end))]
        direct = float(sum(v * ((1 + Rs[t]).prod() - 1) for t, v in w.items()))
        ref = W[(W["asof"] == a) & (W["book"] == "c7_noreview")]["gross"]
        res.append({"asof": a, "through": end, "complete": end == t1, "engine_gross": g, "direct_gross": direct,
                    "diff_direct_bp": (g - direct) * 1e4,
                    "weekly_gross": float(ref.iloc[0]) if len(ref) and end == t1 else None,
                    "diff_weekly_bp": (g - float(ref.iloc[0])) * 1e4 if len(ref) and end == t1 else None})
    ok = all(abs(x["diff_direct_bp"]) <= 1 and (x["diff_weekly_bp"] is None or abs(x["diff_weekly_bp"]) <= 1) for x in res)
    json.dump({"weeks": res, "pass": ok}, open(os.path.join(LC, "replay.json"), "w"), indent=1)
    for x in res:
        print(f"replay {x['asof']} through {x['through']}: engine {x['engine_gross'] * 100:+.4f}%, direct {x['direct_gross'] * 100:+.4f}% "
              f"({x['diff_direct_bp']:+.4f} bp)" + (f", weekly book {x['weekly_gross'] * 100:+.4f}% ({x['diff_weekly_bp']:+.4f} bp)"
                                                   if x["weekly_gross"] is not None else ""))
    if not ok:
        raise SystemExit("replay: the engine does not reproduce the weekly book within 1 bp")


def trade(plan_only):
    """Protocol 7, every trading day: news checks at T-20 min, prices at T-3 min, the decision logged, then the
    account traded to it in the last minute before the close (fund/broker.py). A plan run decides and logs to
    <day>.plan.json (news checks in lifecycle/plan_news/), and sends nothing."""
    import broker
    require("OPENROUTER_API_KEY", "FINNHUB_API_KEY", "HF_TOKEN")
    clock = broker.Clock()
    if not clock.is_open and not plan_only:            # a plan run may decide for the next session at any time
        print("lifecycle trade: the market is closed today"); return
    close_at = clock.next_close.timestamp()
    day = pd.Timestamp(datetime.fromtimestamp(close_at, broker.ET).date())
    os.makedirs(LIVE, exist_ok=True)
    log_p = os.path.join(LIVE, f"{day.date()}{'.plan' if plan_only else ''}.json")
    if not plan_only:
        if day < P7_START:
            print(f"lifecycle trade: Protocol 7 trades from {P7_START.date()}; nothing to do on {day.date()}"); return
        if os.path.exists(log_p) and json.load(open(log_p)).get("status") == "submitted":
            print(f"lifecycle trade: {day.date()} already traded"); return
    if clock.now() > close_at - NEWS_AT - 60 and not plan_only:
        raise SystemExit(f"lifecycle trade: missed the decision window for {day.date()}")
    news_dir = os.path.join(LC, "plan_news") if plan_only else None
    C = cohorts()
    tickers = sorted({"SPY"} | {t for c in C for t in c["w"]})

    def decide(phase):
        s_, cal = broker.api("GET", f"/v2/calendar?start={(day - pd.Timedelta(days=10)).date()}&end={day.date()}")
        prev = max(pd.Timestamp(x["date"]) for x in cal if pd.Timestamp(x["date"]) < day)
        last = closes(set(tickers), prev - pd.Timedelta(days=10), prev).loc[:prev].iloc[-1]
        px = broker.prices(tickers)
        ret = {t: px[t] / last[t] - 1 for t in tickers if t in px and t in last and last[t] > 0}
        st = run(live={"day": day, "ret": ret, "news_ts": int(close_at - NEWS_AT), "news_dir": news_dir})
        print(f"lifecycle {phase}: {len(st['live']['lots'])} lots, {len(st['live']['actions'])} actions", flush=True)
        return st["live"], px, ret

    if clock.now() < close_at - NEWS_AT and not plan_only:
        print(f"lifecycle trade: waiting for the news checks at {datetime.fromtimestamp(close_at - NEWS_AT, broker.ET):%H:%M:%S} ET", flush=True)
        clock.sleep_until(close_at - NEWS_AT)
    decide("news checks (T-20 min)")                       # kill checks run and are logged now; prices refresh below
    if not plan_only:
        clock.sleep_until(close_at - PRICES_AT)
    lv, px, ret = decide("decision (T-3 min)")
    nav = lv["nav"]
    target = {L["ticker"]: L["n"] / nav for L in lv["lots"]}
    if abs(lv["hedge"]) > 1e-9:
        target["SPY"] = lv["hedge"] / nav
    acct = broker.account()
    equity, cur = float(acct["equity"]), broker.positions()
    orders = []
    for sym in sorted(set(target) | set(cur)):
        cq = int(cur.get(sym, 0))
        if sym in target and sym not in px:
            continue
        tq = int(round(target.get(sym, 0.0) * equity / px[sym])) if sym in target else 0
        if tq == cq:
            continue
        if cq and tq and np.sign(tq) != np.sign(cq):
            orders.append({"symbol": sym, "leg": "flatten", "side": "sell" if cq > 0 else "buy", "qty": abs(cq)})
            orders.append({"symbol": sym, "leg": "open", "side": "buy" if tq > 0 else "sell", "qty": abs(tq)})
        else:
            orders.append({"symbol": sym, "leg": "close" if tq == 0 else "rebalance", "side": "buy" if tq > cq else "sell",
                           "qty": abs(tq - cq)})
    for o in orders:
        o.update(target_weight=round(target.get(o["symbol"], 0.0), 5), price_ref=px.get(o["symbol"]),
                 client_order_id=f"fund-lc-{day.date()}-{o['symbol']}-{o['leg']}")
    asof = max((c["asof"] for c in C if pd.Timestamp(c["asof"]) < day), default=None)
    rec = {"day": str(day.date()), "asof": asof, "close_et": datetime.fromtimestamp(close_at, broker.ET).strftime("%H:%M"),
           "news_ts": int(close_at - NEWS_AT), "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "style": broker.STYLE, "nav_model": nav, "hedge_w": lv["hedge"] / nav, "actions": lv["actions"], "cool": lv["cool"],
           "lots_after": [{**{k: v for k, v in L.items() if k != "n"}, "w": L["n"] / nav} for L in lv["lots"]],
           "prices": {t: px.get(t) for t in target}, "equity": equity, "current_qty": cur, "target_weights": target,
           "orders": orders, "problems": [], "status": "planned" if plan_only else "sending"}
    json.dump(rec, open(log_p, "w"), indent=1, default=str)
    print(f"lifecycle {day.date()}: {len(lv['lots'])} lots, actions "
          f"{[(e['ticker'], e['action']) for e in lv['actions']]}; {len(orders)} orders", flush=True)
    for o in orders:
        print(f"  {o['leg']:9s} {o['side']:4s} {o['qty']:>6d} {o['symbol']:6s} @~{o['price_ref']} (target w {o['target_weight']:+.4f})")
    if plan_only:
        return
    s_, open_orders = broker.api("GET", "/v2/orders?status=open&limit=500")
    mine = tuple(o["client_order_id"] for o in orders)
    for x in open_orders or []:
        if not x["client_order_id"].startswith(mine):
            broker.api("DELETE", f"/v2/orders/{x['id']}")
    broker.send(orders, close_at, clock)
    rec.update(orders=orders, problems=broker.problems_of(orders), status="submitted",
               submitted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    json.dump(rec, open(log_p, "w"), indent=1, default=str)
    print(f"lifecycle {day.date()}: {sum(o['status'] == 'filled' for o in orders)}/{len(orders)} orders fully filled")
    if rec["problems"]:
        os.makedirs(os.path.join(STATE, MODE, "execution"), exist_ok=True)
        open(os.path.join(STATE, MODE, "execution", "problems.txt"), "w").write("\n".join(rec["problems"]) + "\n")
        raise SystemExit("; ".join(rec["problems"]))


if mode == "trade":
    trade("--plan" in sys.argv)
else:
    {"desk": desk, "daily": daily, "replay": replay}[mode]()
