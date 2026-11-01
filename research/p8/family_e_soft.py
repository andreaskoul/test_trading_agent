"""Family E, E3 and rule A (reports/research/PREREG_family_E.md §4 E3, §5 rule A, Amendments 1-3).

    python3 ~/.claude/hooks/with_secrets.py 'python3 research/p8/family_e_soft.py news'      # Finnhub, resumable
    python3 ~/.claude/hooks/with_secrets.py 'python3 research/p8/family_e_soft.py bars'      # Alpaca 2024-06 .. now
    python3 ~/.claude/hooks/with_secrets.py 'python3 research/p8/family_e_soft.py classify'  # guarded LLM, capped
    python3 research/p8/family_e_soft.py check       # pipeline check on the fit window; sample for inspection
    python3 research/p8/family_e_soft.py read        # ONCE: rule A on the pooled holdout -> E_SOFT_READ.*

Decided before any Finnhub data was fetched (this file's first commit):
* Universe: today's S&P 500 list. Window: news published 2025-10-25 .. 2026-10-31.
* Shock: >= 5 articles in a session and >= 3x the name's median daily count over the window (by publish time, 16:00 ET
  rule), not within +-2 sessions of the firm's 8-K 2.02. One shock per name per 5 sessions.
* Classifier: one guarded call per shock, at most 30 of the session's headlines, no prices. The holdout window
  (2026-05-01 .. 2026-10-31) is labelled first, then the fit window, up to 3,000 shocks in all. Over the cap, a
  seeded random sample (seed 0) within each window.
* Soft = event type in {product_launch, partnership, leadership, macro_readthrough, mna_rumour, other} and not hard.
"""
import glob
import json
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import family_e as FE                                            # noqa: E402
import inference as I                                            # noqa: E402
import prices as PX                                              # noqa: E402
import residuals as RS                                           # noqa: E402
sys.path.insert(0, os.path.join(PX.ROOT, "fund"))
from edgar_time import et_from_api                               # noqa: E402

NEWS = os.path.join(PX.CACHE, "finnhub")
BARS = os.path.join(PX.CACHE, "alpaca_bars_soft.parquet")
LABELS = os.path.join(PX.CACHE, "soft_labels.jsonl")
W0, W1 = pd.Timestamp("2025-10-25"), pd.Timestamp("2026-10-31")
FIT = (pd.Timestamp("2025-11-01"), pd.Timestamp("2026-04-30"))
HOLD = (pd.Timestamp("2026-05-01"), pd.Timestamp("2026-10-31"))
CAP, SPLIT_AT = 3000, 200
BUDGET, MAX_TOKENS = 5.0, 8000                                # $ per classify run; provider-side answer cap
SOFT = {"product_launch", "partnership", "leadership", "macro_readthrough", "mna_rumour", "other"}
TYPES = ["earnings", "guidance", "capital_return", "analyst_revisions", "legal_regulatory", "product_launch", "partnership",
         "leadership", "macro_readthrough", "mna_rumour", "dated_catalyst", "other"]
LOCK = os.path.join(PX.OUT, "E_SOFT_READ.lock")
ET = "America/New_York"


def universe():
    return sorted(pd.read_csv(os.path.join(PX.ROOT, "data", "raw", "stocks", "sp500_current.csv"))["Symbol"])


# ----------------------------------------------------------------------------- data
def _company_news(t, a, b, key):
    import urllib.request
    url = f"https://finnhub.io/api/v1/company-news?symbol={t}&from={a.date()}&to={b.date()}&token={key}"   # class shares: BRK.B
    for k in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                x = json.load(r)
            time.sleep(1.05)
            return x
        except Exception:
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"Finnhub failed: {t} {a.date()}..{b.date()}")


def _window(t, a, b, key):
    arts = _company_news(t, a, b, key)
    if len(arts) >= SPLIT_AT and (b - a).days >= 1:              # possibly truncated: split
        m = a + (b - a) / 2
        return _window(t, a, m.normalize(), key) + _window(t, m.normalize() + pd.Timedelta(days=1), b, key)
    return arts


def news():
    key = os.environ["FINNHUB_API_KEY"]
    os.makedirs(NEWS, exist_ok=True)
    for t in universe():
        p = os.path.join(NEWS, f"{t}.parquet")
        if os.path.exists(p):
            continue
        rows, a = [], W0
        while a <= W1:
            b = min(a + pd.Timedelta(days=29), W1)
            rows += _window(t, a, b, key)
            a = b + pd.Timedelta(days=1)
        D = pd.DataFrame([{"id": x.get("id"), "datetime": x.get("datetime"), "headline": x.get("headline"),
                           "source": x.get("source")} for x in rows]).drop_duplicates("id")
        D.to_parquet(p)
        print(f"{t}: {len(D)} articles", flush=True)


def bars():
    import broker
    names = universe() + ["SPY"]
    rows = []
    for i in range(0, len(names), 50):
        chunk, token = names[i:i + 50], None
        while True:
            q = (f"/v2/stocks/bars?symbols={','.join(chunk)}&timeframe=1Day&adjustment=all&feed=sip&limit=10000"
                 f"&start=2024-06-01&end={pd.Timestamp.now(tz='UTC').date()}T00:00:00Z" + (f"&page_token={token}" if token else ""))
            s, b = broker.api("GET", q, base=broker.DATA)
            if s != 200:
                raise SystemExit(f"Alpaca bars failed for {chunk[:3]}: {s}")
            for t, xs in (b.get("bars") or {}).items():
                rows += [(x["t"][:10], t, float(x["c"])) for x in xs]
            token = b.get("next_page_token")
            if not token:
                break
    D = pd.DataFrame(rows, columns=["date", "ticker", "close"])
    D["date"] = pd.to_datetime(D["date"])
    D.to_parquet(BARS)
    print(f"bars: {len(D):,}, {D['ticker'].nunique()} symbols, to {D['date'].max().date()}")


def returns_soft():
    P = pd.read_parquet(BARS).pivot_table(index="date", columns="ticker", values="close").sort_index()
    R = P.pct_change(fill_method=None)
    bad = R.drop(columns=["SPY"]).abs() > 0.75
    return R.mask(bad.reindex(columns=R.columns, fill_value=False)).iloc[1:]


def releases_202():
    """8-K 2.02 Eastern times per ticker, 2025-10 .. 2026-10, from the live-API histories (Amendment 1)."""
    C = json.load(open(os.path.join(FE.ED.CACHE, "ciks.json")))
    out = {}
    for t in universe():
        c = (C.get(t) or {}).get("cik")
        p = os.path.join(FE.LIVE, f"{c}.json")
        if not c or not os.path.exists(p):
            continue
        s = json.load(open(p))
        if not s:
            continue
        F = FE.ED._filings(s)
        F = F[F["form"].isin(["8-K", "8-K/A"]) & F["items"].astype(str).str.contains("2.02", regex=False)]
        out[t] = [et_from_api(x) for x in F["acceptanceDateTime"] if x >= "2025-10-01"]
    return out


def session_of(ts_et, sessions):
    d = pd.Timestamp(ts_et.date())
    late = ts_et.hour * 60 + ts_et.minute >= 16 * 60
    i = sessions.searchsorted(d, side="right" if late else "left")
    return sessions[i] if i < len(sessions) else None


def shocks(sessions):
    rel = releases_202()
    out = []
    for p in sorted(glob.glob(os.path.join(NEWS, "*.parquet"))):
        t = os.path.basename(p)[:-8]
        D = pd.read_parquet(p)
        if not len(D):
            continue
        et = pd.to_datetime(D["datetime"], unit="s", utc=True).dt.tz_convert(ET).dt.tz_localize(None)
        D = D.assign(et=et, s=[session_of(x, sessions) for x in et])
        D = D[D["s"].notna()]
        cnt = D.groupby("s").size().reindex(sessions[(sessions >= W0) & (sessions <= W1)], fill_value=0)
        med = max(float(cnt.median()), 1.0)
        rel_i = [sessions.get_loc(x) for x in (session_of(a, sessions) for a in rel.get(t, [])) if x is not None]
        last = -99
        for s_, n in cnt.items():
            i = sessions.get_loc(s_)
            if n >= 5 and n >= 3 * med and not any(abs(i - j) <= 2 for j in rel_i) and i - last >= 5:
                g = D[D["s"] == s_].sort_values("et")
                out.append({"ticker": t, "session": s_, "n": int(n), "median": med, "first_et": g["et"].iloc[0],
                            "headlines": [h for h in g["headline"].fillna("").tolist() if h][:30]})
                last = i
    return pd.DataFrame(out)


# ----------------------------------------------------------------------------- the classifier
SYSTEM = """You classify the news event behind a burst of articles about ONE listed company on ONE day.
Use only the headlines given. Types: earnings (a results release), guidance (company outlook numbers), capital_return
(buyback, dividend), analyst_revisions (rating or target changes), legal_regulatory (court, regulator, government
decision or action), product_launch, partnership (deal, contract, collaboration, supply agreement), leadership
(executive or board change), macro_readthrough (news about the economy, sector or another company that bears on this
one), mna_rumour (reported or rumoured takeover talks not yet agreed), dated_catalyst (a scheduled event ahead),
other.
hard = true only if the event is a reported or official fact with numbers or legal force (results, guidance numbers,
a signed or cancelled contract with stated terms, a regulatory or court decision). Opinions, previews, rumours,
recaps and leadership changes are not hard.
Return JSON only: {"event_type": one of the types, "hard": true|false}"""


def _check(o):
    if not isinstance(o, dict) or o.get("event_type") not in TYPES:
        return "event_type must be one of the listed types"
    if not isinstance(o.get("hard"), bool):
        return "hard must be true or false"
    return None


def classify():
    sys.path.insert(0, os.path.join(PX.ROOT, "fund"))
    import guards
    R = returns_soft()
    S = shocks(R.index)
    S["win"] = np.where(S["session"] >= HOLD[0], "hold", np.where(S["session"] >= FIT[0], "fit", "pre"))
    S = S[S["win"] != "pre"]
    done = {(x["ticker"], x["session"]) for x in map(json.loads, open(LABELS))
            if x["status"] != "budget_stop"} if os.path.exists(LABELS) else set()
    pick = []
    for w in ("hold", "fit"):
        g = S[S["win"] == w]
        room = CAP - len(pick)
        idx = list(g.index)
        if len(idx) > room:
            random.Random(0).shuffle(idx)
            idx = sorted(idx[:room])
        pick += idx
    todo = [S.loc[i] for i in pick if (S.loc[i, "ticker"], str(S.loc[i, "session"].date())) not in done]
    print(f"shocks: {len(S)} ({(S['win'] == 'hold').sum()} holdout); labelled {len(pick)} at most; to do {len(todo)}", flush=True)

    spent = [0.0]

    def one(r):
        if spent[0] >= BUDGET:                                     # cost stop: the rest is not labelled (missing)
            return {"ticker": r["ticker"], "session": str(r["session"].date()), "win": r["win"], "status": "budget_stop"}
        user = f"Company ticker {r['ticker']}. Headlines of {r['session'].date()}:\n" + "\n".join(f"- {h}" for h in r["headlines"])
        st, out, meta, err, glog = guards.guarded_llm(SYSTEM, user, _check, max_tokens=MAX_TOKENS)
        spent[0] += float((meta.get("usage") or {}).get("cost") or 0)
        return {"ticker": r["ticker"], "session": str(r["session"].date()), "win": r["win"], "n": r["n"],
                "first_et": str(r["first_et"]), "status": st, "out": out, "error": err, "provider": meta.get("provider"),
                "rejected": glog["attempts"]}
    with open(LABELS, "a") as fh, ThreadPoolExecutor(6) as ex:
        for k, x in enumerate(ex.map(one, todo)):
            fh.write(json.dumps(x, default=str) + "\n")
            if k % 200 == 0:
                print(f"labelled {k + 1}/{len(todo)}, ${spent[0]:.2f}", flush=True)
    L = [json.loads(x) for x in open(LABELS)]
    print(f"labels: {len(L)}, ok {sum(x['status'] == 'ok' for x in L)}; this run ${spent[0]:.2f}")


# ----------------------------------------------------------------------------- rule A
def lag_minutes():
    """L (Amendment 3): the 95th percentile of the late-served lag in the live news audit, all days on fund-data."""
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", "origin/fund-data"], capture_output=True, text=True, cwd=PX.ROOT).stdout
    lags = []
    for p in [x for x in out.split() if "lifecycle/news_audit/20" in x]:
        a = json.loads(subprocess.run(["git", "show", f"origin/fund-data:{p}"], capture_output=True, text=True, cwd=PX.ROOT).stdout)
        lags += [m["lag_lb_min"] for L in a["lots"].values() for m in L.get("missed", []) if m.get("kind", "late") == "late"]
    return float(np.quantile(lags, 0.95)), len(lags)


def finnhub_rows(R, L_min, a, b):
    lab = {(x["ticker"], x["session"]): x for x in map(json.loads, open(LABELS)) if x["status"] == "ok"}
    S = shocks(R.index)
    gi = FE.gics_of()
    rows = []
    for r in S.itertuples():
        x = lab.get((r.ticker, str(r.session.date())))
        if not x or not (a <= r.session <= b):
            continue
        soft = x["out"]["event_type"] in SOFT and not x["out"]["hard"]
        if not soft or r.ticker not in R:
            continue
        i0 = R.index.get_loc(r.session)
        d = np.sign(FE.day0(R, r.ticker, i0))
        ent = FE.fund_entry(pd.Timestamp(r.first_et) + pd.Timedelta(minutes=L_min), R.index)
        if not d or ent is None:
            continue
        y, end = FE.resid_sum(R, r.ticker, R.index.get_loc(ent), 5, i0 - 1)
        if end is None or not np.isfinite(y):
            continue
        rows.append({"src": "finnhub", "ticker": r.ticker, "t0": r.session, "y": d * y,
                     "industry": (gi.get(r.ticker) or {}).get("industry_code", "NA"), "type": x["out"]["event_type"]})
    return pd.DataFrame(rows)


def eightk_rows(a, b):
    R = FE.returns_2016()
    E3 = FE.filing_events("soft", R)
    gi = FE.gics_of()
    rows = []
    for r in FE.first_per_window(E3[(E3["t0"] >= a) & (E3["t0"] <= b)], 5).itertuples():
        d = np.sign(FE.day0(R, r.ticker, r.i0))
        ent = FE.fund_entry(r.accepted_et, R.index)
        if not d or ent is None:
            continue
        y, end = FE.resid_sum(R, r.ticker, R.index.get_loc(ent), 5, r.i0 - 1)
        if end is None or end > b or not np.isfinite(y):
            continue
        rows.append({"src": "8-K", "ticker": r.ticker, "t0": r.t0, "y": d * y,
                     "industry": (gi.get(r.ticker) or {}).get("industry_code", "NA"), "type": r.items})
    return pd.DataFrame(rows)


def applicability():
    """Share of the live book's soft entries (from session 2026-10-15) whose side equals the sign of the residual move
    on the news session. Records on fund-data; returns from lifecycle/returns.csv; betas from the cohort's screen."""
    import io
    g = lambda p: subprocess.run(["git", "show", f"origin/fund-data:fund_state/live/{p}"], capture_output=True, text=True, cwd=PX.ROOT).stdout
    st = json.loads(g("lifecycle/state.json"))
    R = pd.read_csv(io.StringIO(g("lifecycle/returns.csv")), parse_dates=["date"]).pivot_table(index="date", columns="ticker", values="ret")
    agree, n = 0, 0
    for e in st["events"]:
        if e["action"] != "entry" or e["day"] < "2026-10-15" or "|" not in e["id"]:
            continue
        a, t = e["id"].split("|", 1)
        L = json.loads(g(f"{a}/lifecycle.json"))["names"].get(t) or {}
        o = L.get("out") or {}
        if o.get("event_type") not in SOFT or o.get("hard"):
            continue
        s0 = (L.get("inputs") or {}).get("news_session") or o.get("first_reported")
        s0 = R.index[R.index >= pd.Timestamp(s0)]
        S = {x["ticker"]: x.get("beta_hedge") or 1.0 for x in json.loads(g(f"{a}/screen.json"))["rows"]}
        if not len(s0) or t not in R:
            continue
        mv = R.at[s0[0], t] - float(S.get(t, 1.0)) * R.at[s0[0], "SPY"]
        if not np.isfinite(mv) or mv == 0:
            continue
        n += 1
        agree += int(np.sign(mv) == np.sign(e["to"]))
    return agree, n


def check():
    R = returns_soft()
    L_min, nl = lag_minutes()
    F = finnhub_rows(R, L_min, *FIT)
    L = [json.loads(x) for x in open(LABELS)]
    ok = [x for x in L if x["status"] == "ok"]
    print(f"lag L = {L_min:.0f} min (95th percentile of {nl} late-served articles)")
    print(f"labels {len(L)}: ok {len(ok)}, failed {len(L) - len(ok)}; types {pd.Series([x['out']['event_type'] for x in ok]).value_counts().to_dict()}")
    print(f"hard share {np.mean([x['out']['hard'] for x in ok]):.2f}; soft shocks usable in the fit window: {len(F)}")
    m, t, n, G = FE.week_t(F["y"], F["t0"])
    print(f"fit window (pipeline check, descriptive): n {n}, mean {m * 1e4:+.1f} bp, t {t:+.2f}")
    sample = random.Random(1).sample(ok, min(50, len(ok)))
    S = shocks(R.index).set_index(["ticker"]).assign(session=lambda d: d["session"].astype(str))
    with open(os.path.join(PX.OUT, "E_SOFT_SAMPLE.md"), "w") as fh:
        fh.write("# E3 classifier: 50 random labels next to their headlines (CLAUDE.md rule 11)\n\n")
        for x in sample:
            h = S[(S.index == x["ticker"]) & (S["session"] == x["session"])]["headlines"]
            fh.write(f"## {x['ticker']} {x['session']}: {x['out']['event_type']}, hard {x['out']['hard']}\n\n"
                     + "".join(f"- {y}\n" for y in (list(h.iloc[0])[:8] if len(h) else [])) + "\n")
    print("sample for inspection: reports/research/p8/E_SOFT_SAMPLE.md")


def read():
    if os.path.exists(LOCK):
        raise SystemExit(f"{LOCK} exists: the rule A read has been made")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=PX.ROOT).stdout.strip()
    open(LOCK, "w").write(f"{datetime.now(timezone.utc).isoformat()} commit {commit}\n")
    L_min, nl = lag_minutes()
    A = eightk_rows(FE.V0, FE.V1)
    F = finnhub_rows(returns_soft(), L_min, *HOLD)
    X = pd.concat([A, F], ignore_index=True)
    mt = I.mean_test(X["y"].values, pd.to_datetime(X["t0"]).dt.strftime("%G-%V").values, X["industry"].values,
                     null=FE.C_LIVE * 1e-4, direction=1, B=9999)              # H0: mean <= 2c = 4 bp
    agree, n_live = applicability()
    share = agree / n_live if n_live else float("nan")
    keep = bool(mt["p"] <= 0.10 and (n_live and share >= 0.60))
    out = {"lock": open(LOCK).read().strip(), "lag_min": L_min, "lag_n": nl, "n_8k": int(len(A)), "n_finnhub": int(len(F)),
           "mean_bp": mt["mean"] * 1e4, "mean_8k_bp": float(A["y"].mean() * 1e4) if len(A) else None,
           "mean_finnhub_bp": float(F["y"].mean() * 1e4) if len(F) else None, "p_vs_4bp": mt["p"], "p_parts": mt["p_parts"],
           "desk_agreement": {"agree": agree, "n": n_live, "share": share}, "decision": "KEEP" if keep else "STOP"}
    json.dump(out, open(os.path.join(PX.OUT, "E_SOFT_READ.json"), "w"), indent=1, default=str)
    md = ["# Rule A: soft-news entries (pooled holdout, read once)", "", f"Lock: {out['lock']}", "",
          "KEEP iff the one-sided p of H0: mean <= 4 bp (the live round trip) is <= 0.10 and the desk's sides agree with the "
          "news-day move on >= 60% of its soft entries; otherwise STOP (PREREG_family_E.md rule A).", "",
          f"* Events: 8-K items 5.02/1.01, 2022-2025: {len(A)} (mean {out['mean_8k_bp']:+.1f} bp); Finnhub soft shocks, "
          f"2026-05 .. 2026-10: {len(F)} (mean {out['mean_finnhub_bp'] if out['mean_finnhub_bp'] is None else round(out['mean_finnhub_bp'], 1)} bp).",
          f"* Pooled mean of y (5 sessions after the fund's entry, in the news-day direction): **{out['mean_bp']:+.1f} bp**; "
          f"p (H0: <= 4 bp) **{mt['p']:.4f}** ({', '.join(f'{k} {v:.4f}' for k, v in mt['p_parts'].items())}).",
          f"* Desk agreement: {agree}/{n_live} = {share:.0%}.", f"* Fund-time lag L = {L_min:.0f} min ({nl} late-served articles).", "",
          f"**Decision: {out['decision']}.**"]
    open(os.path.join(PX.OUT, "E_SOFT_READ.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    {"news": news, "bars": bars, "classify": classify, "check": check, "read": read}[sys.argv[1]]()
