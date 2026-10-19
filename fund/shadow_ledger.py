"""Shadow books monitor (GitHub Pages: fund/site/shadow/). No orders, no LLM. -> ledger/shadow.json

Every weekly book that is scored but never sent to Alpaca (PROTOCOL_fund.md: books logged every week,
Amendments 4 and 6, Protocol 7's c0_weekly), marked the way score.py scores it: each week's weights
enter at the execution day's close and are held to the next execution day's close, 5 bp per side on the
change in weights, cash earns nothing (score.py's "net"). Each book starts at a notional $100,000 in its
first week, and the weeks chain. Between scorings the running week is marked at the latest close, or at
Alpaca's latest trade on a live page refresh. The C10 lifecycle book is shown from its own daily NAV
(fund/lifecycle.py). Nothing here feeds a decision or a test: score.py remains the record.
"""

import glob
import json
import os

import numpy as np
import pandas as pd
import yfinance as yf

import broker
from common import MODE, P7_START, STATE

START, COST = 100_000.0, 5e-4
# the weekly fund book: the champion until Protocol 7, then shadow c0_weekly; shown as one series
# The weekly books shown, in page order. Keys are the record names (C<n> = challenger n in PROTOCOL_fund.md); their
# names and descriptions live on the page (fund/site/shadow/index.html, NAMES and ABOUT), so wording ships with Pages.
BOOKS = ("c0_weekly", "analyst", "quant", "core20", "random", "c2_selfconsistency", "c3_textonly", "c4_volscaled",
         "c5_reversal", "c8_informed", "c9_ranker", "sp500_hold")
BENCH = {"sp500_hold": {"SPY": 1.0}}           # held through every week, flat weeks included
ORDER = list(BOOKS)


def _f(v):
    if isinstance(v, (np.floating, np.integer)):
        v = v.item()
    return None if v is None or (isinstance(v, float) and not np.isfinite(v)) else v


def weeks(base):
    out = []
    for wd in sorted(glob.glob(os.path.join(base, "20*"))):
        bp = os.path.join(wd, "book.json")
        if not os.path.exists(bp):
            continue
        b = json.load(open(bp))
        asof = pd.Timestamp(os.path.basename(wd))
        if b.get("status") not in ("ok", "degraded_hold"):    # missed deadline: every book is flat that week (score.py)
            out.append({"asof": asof, "books": None, "names": {"SPY": "SPDR S&P 500 ETF"}})
            continue
        ex_p = os.path.join(wd, "execution.json")
        halted = os.path.exists(ex_p) and str(json.load(open(ex_p)).get("reason") or "").startswith("HALT")
        books = {("c0_weekly" if k == "fund" else k): ({} if (k == "fund" and halted) else v)
                 for k, v in b.get("books", {}).items()}
        sp = os.path.join(wd, "shadow_book.json")
        if os.path.exists(sp):
            books.update(json.load(open(sp))["books"])
        sc = os.path.join(wd, "screen.json")
        names = {r["ticker"]: r.get("Security") for r in json.load(open(sc))["rows"]} if os.path.exists(sc) else {}
        out.append({"asof": asof, "books": {k: v for k, v in books.items() if k in BOOKS}, "names": {**names, "SPY": "SPDR S&P 500 ETF"}})
    return out


def prices(tickers, start, live):
    px = yf.download(sorted({t.replace(".", "-") for t in tickers}), start=start, end=pd.Timestamp.now() + pd.Timedelta(days=1),
                     progress=False, auto_adjust=True, threads=True)["Close"]
    if isinstance(px, pd.Series):
        px = px.to_frame(next(iter(tickers)))
    px = px.rename(columns=lambda c: c.replace("-", "."))
    px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
    px = px[px.index.dayofweek < 5].dropna(how="all")
    now = pd.Timestamp.now(tz=broker.ET)
    today = pd.Timestamp(now.date())
    if not live and now.hour * 60 + now.minute < 16 * 60 + 15:     # Yahoo's row for a session not yet closed is not a close
        px = px[px.index < today]
    if live:                                    # today's row at Alpaca's latest trades
        lp = broker.prices(sorted(tickers))
        row = px.loc[today] if today in px.index else pd.Series(np.nan, index=px.columns)
        for t, v in lp.items():
            if t in px.columns and v:
                row[t] = float(v)
        px.loc[today] = row
        px = px.sort_index()
    return px


def lifecycle(base):
    p = os.path.join(base, "lifecycle", "state.json")
    if not os.path.exists(p):
        return None
    st = json.load(open(p))
    if not st.get("rows"):
        return None
    nav = st["rows"][-1]["nav"]
    lots = [{"ticker": L["ticker"], "side": "Long" if L["side"] > 0 else "Short", "cohort": L.get("cohort"),
             "entry_day": L.get("entry_day"), "value": _f(L.get("n")), "weight": _f((L.get("n") or 0) / nav),
             "score": L.get("score"), "H": L.get("H"), "days": L.get("days"), "R": _f(L.get("R")), "W": _f(L.get("W")),
             "stop": _f(-2.0 * L["W"]) if L.get("W") else None, "target": _f(3.0 * L["W"]) if L.get("W") else None,
             "kill_conditions": L.get("kill_conditions") or []} for L in st.get("lots", [])]
    return {"nav": [{"date": r["date"], "value": _f(r["nav"])} for r in st["rows"]],
            "lots": lots, "events": [{k: _f(v) for k, v in e.items()} for e in st.get("events", [])][::-1],
            "updated": st.get("updated"), "is_fund_from": str(P7_START.date())}


def build(out_dir, live=False):
    base = os.path.join(STATE, MODE)
    W = weeks(base)
    if not W:
        return None
    tickers = {"SPY"} | {t for w in W for b in (w["books"] or {}).values() for t in b}
    px = prices(tickers, W[0]["asof"] - pd.Timedelta(days=7), live)
    days = px.index
    books = {}
    for i, w in enumerate(W):
        after = days[days > w["asof"]]
        if not len(after):
            continue                            # decided, not yet entered
        t0 = after[0]
        nxt = days[days >= w["asof"] + pd.Timedelta(days=8)]
        t1, running = (nxt[0], False) if len(nxt) else (days[-1], True)
        for k in set(books) | set(w["books"] or {}) | set(BENCH):
            B = books.setdefault(k, {"value": START, "prev": pd.Series(dtype=float), "series": [], "weeks": [],
                                     "trades": [], "positions": [], "started": str(t0.date())})
            if k not in BENCH and w["books"] is not None and k not in w["books"]:     # no book this week (e.g. too many failed C8 memos)
                B["weeks"].append({"asof": str(w["asof"].date()), "entry": str(t0.date()), "exit": str(t1.date()),
                                   "status": "no book", "return": None, "cost": None})
                if i == len(W) - 1 or running:
                    B["positions"] = []
                continue
            wt = pd.Series(BENCH.get(k) or (w["books"] or {}).get(k, {}), dtype=float)
            idx = wt.index.union(B["prev"].index)
            dw = wt.reindex(idx, fill_value=0) - B["prev"].reindex(idx, fill_value=0)
            cost = float(dw.abs().sum() * COST)
            v0 = B["value"] * (1 - cost)
            p0 = px.loc[t0].reindex(wt.index)
            for t, d in dw[dw.abs() > 1e-9].items():
                old, new = float(B["prev"].get(t, 0.0)), float(wt.get(t, 0.0))
                act = ("exit" if new == 0 else "new " + ("long" if new > 0 else "short") if old == 0
                       else "flip to " + ("long" if new > 0 else "short") if old * new < 0
                       else "add" if abs(new) > abs(old) else "trim")
                B["trades"].append({"week": str(w["asof"].date()), "day": str(t0.date()), "ticker": t, "name": w["names"].get(t),
                                    "action": "hedge " + act if t == "SPY" and k not in BENCH else act, "side": "buy" if d > 0 else "sell",
                                    "from_w": old, "to_w": new, "amount": abs(float(d)) * B["value"],
                                    "price": _f(px.at[t0, t]) if t in px.columns else None})
            seg = days[(days > t0) & (days <= t1)]
            if not len(B["series"]):
                B["series"].append({"date": str(t0.date()), "value": v0})
            else:
                B["series"][-1]["value"] = v0         # the entry-day cost lands on the boundary
            for d in seg:
                r = (px.loc[d].reindex(wt.index) / p0 - 1).fillna(0)
                B["series"].append({"date": str(d.date()), "value": v0 * (1 + float((wt * r).sum()))})
            end = v0 * (1 + float((wt * (px.loc[t1].reindex(wt.index) / p0 - 1).fillna(0)).sum())) if len(seg) else v0
            B["weeks"].append({"asof": str(w["asof"].date()), "entry": str(t0.date()), "exit": None if running else str(t1.date()),
                               "status": "running" if running else "closed", "return": end / B["value"] - 1, "cost": cost,
                               "names": 500 if k in BENCH else int((wt.index != "SPY").sum()), "gross": float(wt.abs().sum() if k in BENCH else wt.drop("SPY", errors="ignore").abs().sum()),
                               "spy": None if k in BENCH else float(wt.get("SPY", 0.0))})
            if running or i == len(W) - 1:
                cur = px.loc[t1].reindex(wt.index)
                B["positions"] = [{"ticker": t, "name": w["names"].get(t), "role": "beta hedge" if t == "SPY" and k not in BENCH else "stock",
                                   "side": "Long" if x > 0 else "Short", "weight": float(x), "amount": abs(float(x)) * v0,
                                   "entry_day": str(t0.date()), "entry_price": _f(p0.get(t)), "current_price": _f(cur.get(t)),
                                   "return": _f(np.sign(x) * (cur.get(t) / p0.get(t) - 1)) if p0.get(t) else None,
                                   "pnl": _f(x * v0 * (cur.get(t) / p0.get(t) - 1)) if p0.get(t) else None}
                                  for t, x in wt.sort_values(ascending=False).items()]
            if k in BENCH and B["positions"]:      # held since the start, not re-entered each week: show it that way
                t_s = pd.Timestamp(B["started"])
                for q in B["positions"]:
                    p_s, p_n = px.at[t_s, q["ticker"]], q["current_price"]
                    q.update({"entry_day": B["started"], "entry_price": _f(p_s), "amount": START * (1 - COST),
                              "return": _f(p_n / p_s - 1) if p_n else None,
                              "pnl": _f(START * (1 - COST) * (p_n / p_s - 1)) if p_n else None})
            B["value"], B["prev"] = end, wt
    out_books = []
    for k in sorted(books, key=lambda k: ORDER.index(k) if k in ORDER else 99):
        B = books[k]
        wk = [x for x in B["weeks"] if x["return"] is not None]
        out_books.append({"key": k, "started": B["started"], "value": B["value"],
                          "return": B["value"] / START - 1, "week_return": wk[-1]["return"] if wk else None,
                          "series": B["series"], "weeks": B["weeks"][::-1], "positions": B["positions"],
                          # newest execution day first, largest trades first within it
                          "trades": sorted(sorted(B["trades"], key=lambda t: -t["amount"]), key=lambda t: t["day"], reverse=True)})
    nav_p = os.path.join(base, "execution", "nav.csv")
    acct = None
    if os.path.exists(nav_p) and books:
        N = pd.read_csv(nav_p)
        N = N[N["date"].astype(str) >= min(B["started"] for B in books.values())]
        if len(N):
            acct = [{"date": str(r["date"]), "value": float(r["equity"])} for _, r in N.iterrows()]
    data = {"updated": pd.Timestamp.now(tz="UTC").isoformat(timespec="minutes"),
            "marks": f"live {pd.Timestamp.now(tz=broker.ET):%H:%M} ET" if live else "latest close",
            "start": START, "p7_start": str(P7_START.date()), "books": out_books, "lifecycle": lifecycle(base), "account": acct}

    def clean(v):
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()}
        if isinstance(v, list):
            return [clean(x) for x in v]
        return _f(v) if isinstance(v, (float, np.floating, np.integer)) else v

    os.makedirs(out_dir, exist_ok=True)
    json.dump(clean(data), open(os.path.join(out_dir, "shadow.json"), "w"), default=str, allow_nan=False)
    print(f"shadow monitor: {len(out_books)} books, " + ", ".join(f"{b['key']} {b['return'] * 100:+.2f}%" for b in out_books))
    return data


if __name__ == "__main__":
    build(os.path.join(STATE, MODE, "ledger"), live=os.environ.get("LEDGER_MARKS") == "live")
