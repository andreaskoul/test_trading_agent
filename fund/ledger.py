"""Position ledger (Excel) for the traded fund book, rebuilt from the records every run.

    python fund/ledger.py      # -> fund_state/<mode>/ledger/fund_positions.xlsx

One row per position per holding week: the weekly book is fully re-decided every
Wednesday, so a name held for three weeks is three rows (consecutive_weeks counts
them). Entry is the execution-day fill when the name traded that day, otherwise the
official close of the execution day (the price the book is scored at). Exit is the
official close of the next execution day. Weeks still running are marked Open and
valued at the latest close. Returns are price returns (dividends excluded), long or
short as signed, computed by formulas so the sheet recalculates in Excel.

Sheets: Positions, Orders (every order with fill and slippage vs the close), Weekly
(book-level returns from the performance desk, broker NAV), Notes.
"""

import glob
import json
import os

import numpy as np
import pandas as pd
import yfinance as yf
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from common import MODE, STATE

base = os.path.join(STATE, MODE)
OUT = os.path.join(base, "ledger")
os.makedirs(OUT, exist_ok=True)
weeks = sorted(d for d in glob.glob(os.path.join(base, "20*")) if os.path.exists(os.path.join(d, "book.json")))
ld = lambda d, f: json.load(open(os.path.join(d, f))) if os.path.exists(os.path.join(d, f)) else {}

# actual fills, the source of every share count below: reconcile's fills.csv where a record is
# reconciled, else the filled quantity the send recorded; an order with neither is still pending
_fp = os.path.join(base, "execution", "fills.csv")
FQ = {}
if os.path.exists(_fp):
    for _, f in pd.read_csv(_fp, dtype={"asof": str, "exec_day": str}).iterrows():
        if pd.notna(f.get("filled_qty")):
            FQ[(f["asof"], f["exec_day"], f["symbol"], f["leg"])] = float(f["filled_qty"])


def filled_of(o, asof, day):
    k = (asof, str(day), o["symbol"], o["leg"])
    if k in FQ:
        return FQ[k]
    return float(o["filled_qty"]) if o.get("filled_qty") is not None else None


def signed(o, q):
    return q if o["side"] == "buy" else -q


ORDER_TYPE = {"preclose": "market, last minute before the close", "cls": "market-on-close"}
rows, orders = [], []
for d in weeks:
    asof = os.path.basename(d)
    book, ex = ld(d, "book.json"), ld(d, "execution.json")
    if book.get("status") not in ("ok", "degraded_hold"):
        continue
    if ex.get("status") != "submitted":            # only weeks actually traded on Alpaca
        continue
    halted = str(ex.get("reason") or "").startswith("HALT")
    # actual holdings after the week's orders: shares before + every share actually filled
    live = [o for o in ex.get("orders", []) if o.get("id")]
    held = dict(ex.get("current_qty") or {})
    for o in live:
        q = filled_of(o, asof, ex.get("exec_day"))
        if q:
            held[o["symbol"]] = held.get(o["symbol"], 0) + signed(o, q)
    w = {t: q for t, q in held.items() if q}
    memos, rt = ld(d, "analysts.json").get("memos", {}), ld(d, "redteam.json")
    S = pd.DataFrame(ld(d, "screen.json").get("rows", [])).set_index("ticker") if ld(d, "screen.json") else pd.DataFrame()
    fills = {}
    for o in live:
        orders.append({"week": asof, "exec_day": ex.get("exec_day"), "ticker": o["symbol"], "leg": o["leg"],
                       "side": o["side"], "qty": o["qty"], "filled_qty": filled_of(o, asof, ex.get("exec_day")),
                       "order_type": "market (flip close)" if o["leg"] == "flatten" else ORDER_TYPE[ex.get("style", "cls")],
                       "ref_price": o.get("price_ref"), "target_weight": o.get("target_weight"),
                       "status": o.get("status"), "client_order_id": o.get("client_order_id")})
    fp = os.path.join(base, "execution", "fills.csv")
    if os.path.exists(fp):
        F = pd.read_csv(fp, dtype={"asof": str})
        for _, f in F[F["asof"] == asof].iterrows():
            if f["leg"] != "flatten" and pd.notna(f.get("fill")) and str(f.get("exec_day")) == str(ex.get("exec_day")):
                fills[f["symbol"]] = float(f["fill"])
            for o in orders:
                if o["week"] == asof and o["ticker"] == f["symbol"] and o["leg"] == f["leg"] and str(o["exec_day"]) == str(f.get("exec_day")):
                    o.update(fill_price=f.get("fill"), official_close=f.get("close"), slippage_bp=f.get("slip_bp"),
                             status=f.get("status"))
    # Amendment 5: daily reviews change holdings mid-week. Each change closes the running lot at that
    # day's close and opens a new one, so one row = one lot with constant shares.
    segs = {t: [[q, None, None]] for t, q in w.items()}           # [shares, start day, end day]
    for rp in sorted(glob.glob(os.path.join(d, "reviews", "*.json"))):
        rv_ = json.load(open(rp))
        if rv_.get("status") != "submitted":
            continue
        for o in rv_.get("orders", []):
            if not o.get("id"):
                continue
            q = filled_of(o, asof, rv_["day"])
            orders.append({"week": asof, "exec_day": rv_["day"], "ticker": o["symbol"], "leg": o["leg"], "side": o["side"],
                           "qty": o["qty"], "filled_qty": q,
                           "order_type": ORDER_TYPE[rv_.get("style", "cls")] + " (daily review)", "ref_price": o.get("price_ref"),
                           "status": o.get("status"), "client_order_id": o.get("client_order_id")})
            if not q:
                continue
            lots = segs.setdefault(o["symbol"], [[0, None, None]])
            lots[-1][2] = rv_["day"]
            lots.append([lots[-1][0] + signed(o, q), rv_["day"], None])
    for t, lots in segs.items():
      for q, s_day, e_day in lots:
        if not q:
            continue
        wt = q
        m = (memos.get(t) or {}).get("memo") or {}
        rv = ((rt.get("reviews") or {}).get(t) or {}).get("review") or {}
        r = S.loc[t] if t in S.index else None
        rows.append({"week": asof, "exec_day": ex.get("exec_day"), "ticker": t,
                     "name": (str(r["Security"]) if r is not None else ("SPDR S&P 500 ETF" if t == "SPY" else "")),
                     "sector": (str(r["GICS Sector"]) if r is not None else ("Index hedge" if t == "SPY" else "")),
                     "role": "beta hedge" if t == "SPY" else "position", "side": "Long" if wt > 0 else "Short",
                     "shares": wt,
                     "fill": fills.get(t), "analyst_score": m.get("score"), "confidence": m.get("confidence"),
                     "redteam": rv.get("verdict"), "flaw": rv.get("flaw"),
                     "final_score": (rt.get("final_score") or {}).get(t),
                     "earnings_in_week": (str(r["earnings_in_holding_week"]) if r is not None and "earnings_in_holding_week" in r else ""),
                     "beta_hedge": (float(r["beta_hedge"]) if r is not None and "beta_hedge" in r else None),
                     "ret_1w_before": (float(r["ret_1w_pct"]) / 100 if r is not None else None),
                     "attention_shock": (float(r["attention_shock"]) if r is not None and pd.notna(r.get("attention_shock")) else None),
                     "provider": ((memos.get(t) or {}).get("meta") or {}).get("provider"),
                     "thesis": m.get("thesis", "SPY hedge to zero beta" if t == "SPY" else ""),
                     "degraded_hold": book.get("status") == "degraded_hold", "halted": halted,
                     "seg_start": s_day, "seg_end": e_day})

# fills for every order, weekly and daily-review alike: (week, day, ticker, leg)
_fp = os.path.join(base, "execution", "fills.csv")
if os.path.exists(_fp):
    _F = pd.read_csv(_fp, dtype={"asof": str, "exec_day": str}).set_index(["asof", "exec_day", "symbol", "leg"])
    for o in orders:
        k = (o["week"], str(o["exec_day"]), o["ticker"], o["leg"])
        if k in _F.index:
            f = _F.loc[k]
            f = f.iloc[0] if isinstance(f, pd.DataFrame) else f
            o.update(fill_price=f.get("fill"), official_close=f.get("close"), slippage_bp=f.get("slip_bp"), status=f.get("status"))
P = pd.DataFrame(rows)
if len(P):
    # prices: official closes of each execution day and the next one (raw, unadjusted)
    P["exec_day"] = P["exec_day"].fillna("")
    days = {}
    for a in P["week"].unique():
        px = yf.download(sorted({t.replace(".", "-") for t in P.loc[P.week == a, "ticker"]}), start=pd.Timestamp(a),
                         end=pd.Timestamp(a) + pd.Timedelta(days=16), progress=False, auto_adjust=False)["Close"]
        px = px if isinstance(px, pd.DataFrame) else px.to_frame()
        px.columns = [c.replace("-", ".") for c in px.columns]; px.index = pd.to_datetime(px.index).tz_localize(None)
        after = px.index[px.index > pd.Timestamp(a)]
        t0 = after[0] if len(after) else None
        t1s = px.index[px.index >= pd.Timestamp(a) + pd.Timedelta(days=8)]
        t1 = t1s[0] if len(t1s) else None
        days[a] = (px, t0, t1)
    # current price: the latest close for every ticker ever held
    lp = yf.download(sorted({t.replace(".", "-") for t in P.ticker}), period="10d", progress=False, auto_adjust=False)["Close"]
    lp = lp if isinstance(lp, pd.DataFrame) else lp.to_frame()
    last = {c.replace("-", "."): v for c, v in lp.ffill().iloc[-1].items()}
    # actual fills at lot boundaries (weekly executions and daily reviews). Using the fill of the order
    # traded at a boundary as both the old lot's exit and the new lot's entry makes the lots' P&L add
    # up exactly to the account's trading P&L. A flip's market order closes the old lot; its closing-
    # auction order opens the new one.
    fx = {}
    fp_ = os.path.join(base, "execution", "fills.csv")
    if os.path.exists(fp_):
        for _, f in pd.read_csv(fp_, dtype={"exec_day": str}).iterrows():
            if pd.isna(f.get("fill")):
                continue
            k = (str(f["exec_day"]), f["symbol"])
            if f["leg"] != "open":
                fx[k + ("exit",)] = float(f["fill"])
            if f["leg"] != "flatten":
                fx[k + ("entry",)] = float(f["fill"])
    ent, ext, mark, st, ed, xd = [], [], [], [], [], []
    for _, r in P.iterrows():
        px, t0, t1 = days[r.week]
        c = px[r.ticker] if r.ticker in px else pd.Series(dtype=float)
        has_s, has_e = isinstance(r.seg_start, str), isinstance(r.seg_end, str)
        s0 = pd.Timestamp(r.seg_start) if has_s else t0
        s1 = pd.Timestamp(r.seg_end) if has_e else t1
        e = fx.get((str(s0.date()), r.ticker, "entry"), c.get(s0) if s0 is not None else np.nan) if s0 is not None else np.nan
        ent.append(e); ed.append(str(s0.date()) if s0 is not None else r.exec_day)
        if s1 is not None and pd.notna(c.get(s1, np.nan)):
            ext.append(fx.get((str(s1.date()), r.ticker, "exit"), c[s1]))
            st.append("Closed (daily review)" if has_e else "Closed"); xd.append(str(s1.date()))
        else:
            ext.append(np.nan); st.append("Open"); xd.append("")
        mark.append(last.get(r.ticker, np.nan))
    P["entry_price"], P["exit_price"], P["mark_price"], P["status"], P["entry_day"], P["exit_day"] = ent, ext, mark, st, ed, xd
    P = P.sort_values(["week", "role", "side", "ticker"])
    held = {}
    cons = []
    for _, r in P.iterrows():                          # consecutive weeks held on the same side
        k = (r.ticker, r.side)
        prev_weeks = sorted(P.week.unique())
        i = prev_weeks.index(r.week)
        cons.append(held.get(k, (None, 0))[1] + 1 if i and held.get(k, (None, 0))[0] == prev_weeks[i - 1] else 1)
        held[k] = (r.week, cons[-1])
    P["consecutive_weeks"] = cons

# ------------------------------------------------------------------ workbook
wb = Workbook()
F_ = Font(name="Arial", size=10)
H_ = Font(name="Arial", size=10, bold=True, color="FFFFFF")
HF = PatternFill("solid", fgColor="1F3864")
BLUE = Font(name="Arial", size=10, color="0000FF")


def sheet(ws, cols, data, widths):
    for j, (h, _) in enumerate(cols, 1):
        c = ws.cell(row=1, column=j, value=h); c.font, c.fill = H_, HF
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = widths.get(h, 12)
    for i, rec in enumerate(data, 2):
        for j, (h, fmt) in enumerate(cols, 1):
            v = rec(i)[j - 1] if callable(rec) else rec[j - 1]
            c = ws.cell(row=i, column=j, value=None if (isinstance(v, float) and np.isnan(v)) else v)
            c.font = F_
            if fmt:
                c.number_format = fmt
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{max(len(data) + 1, 2)}"
    ws.row_dimensions[1].height = 30


ws = wb.active; ws.title = "Positions"
cols = [("Week (as-of Wed)", None), ("Ticker", None), ("Name", None), ("Role", None), ("Side", None), ("Status", None),
        ("Entry day", None), ("Exit day", None), ("Shares (signed)", "#,##0;-#,##0;-"), ("Entry price ($)", "#,##0.00"),
        ("Exit price ($)", "#,##0.00"), ("Current price ($)", "#,##0.00"), ("Return (%)", "0.00%;-0.00%;-"),
        ("P&L ($)", "#,##0;(#,##0);-"), ("Confidence", "0.00"), ("Red team", None), ("Thesis", None)]
# ---- Protocol 7: the lifecycle book trades every day and a lot can last several weeks. Its positions are rebuilt
# from the actual fills of the daily trade logs (lifecycle/live/<day>.json): one row per run of a position, from the
# first fill that opens it to the fill that takes it to zero; average entry price over the fills that add to it.
P7, P7_SEED = [], None
for lg in sorted((json.load(open(f)) for f in glob.glob(os.path.join(base, "lifecycle", "live", "*.json")) if not f.endswith(".plan.json")),
                 key=lambda x: x["day"]):
    if lg.get("status") != "submitted":
        continue
    lots_meta = {x["ticker"]: x for x in lg.get("lots_after", [])}
    if P7_SEED is None:                              # the holdings the first lifecycle trade found (Protocol 6's)
        P7_SEED = (lg["day"], {t: q for t, q in (lg.get("current_qty") or {}).items() if q}, lots_meta, lg.get("asof"))
    for o in lg["orders"]:
        q = filled_of(o, lg.get("asof"), lg["day"])
        orders.append({"week": lg.get("asof"), "exec_day": lg["day"], "ticker": o["symbol"], "leg": o["leg"], "side": o["side"],
                       "qty": o["qty"], "filled_qty": q, "order_type": ORDER_TYPE[lg.get("style", "preclose")] + " (lifecycle)",
                       "ref_price": o.get("price_ref"), "target_weight": o.get("target_weight"), "status": o.get("status"),
                       "client_order_id": o.get("client_order_id"), "fill_price": o.get("fill_price")})
        if q:
            P7.append({"day": lg["day"], "ticker": o["symbol"], "q": q if o["side"] == "buy" else -q,
                       "px": o.get("fill_price"), "meta": lots_meta.get(o["symbol"], {}), "asof": lg.get("asof")})
if P7 or P7_SEED:
    p7_rows, runs = [], {}
    if P7_SEED and P7_SEED[1]:
        # carried in at the first lifecycle session's official close: where Protocol 6's weekly rows end
        d0, held0, meta0, wk0 = P7_SEED
        c0 = yf.download(sorted(t.replace(".", "-") for t in held0), start=d0, end=pd.Timestamp(d0) + pd.Timedelta(days=1),
                         progress=False, auto_adjust=False)["Close"]
        c0 = c0 if isinstance(c0, pd.DataFrame) else c0.to_frame(sorted(held0)[0].replace(".", "-"))
        c0 = {k.replace("-", "."): float(v) for k, v in c0.iloc[-1].items()} if len(c0) else {}
        ref0 = {o["ticker"]: o.get("ref_price") for o in orders if o.get("exec_day") == d0}
        for t, q in held0.items():
            runs[t] = {"ticker": t, "shares": float(q), "entry_price": c0.get(t) or ref0.get(t), "entry_day": d0,
                       "meta": meta0.get(t, {}), "week": wk0}
    for f in P7:
        t, run_ = f["ticker"], runs.get(f["ticker"])
        if run_ and np.sign(run_["shares"] + f["q"]) != np.sign(run_["shares"]) and run_["shares"] + f["q"] != 0:
            # a flip through zero: close this run at the fill and open the other side with the remainder
            rest = run_["shares"] + f["q"]
            p7_rows.append({**run_, "status": "Closed", "exit_day": f["day"], "exit_price": f["px"]})
            runs[t] = run_ = None
            f = {**f, "q": rest}
        if not run_:
            runs[t] = {"ticker": t, "shares": f["q"], "entry_price": f["px"], "entry_day": f["day"], "meta": f["meta"],
                       "week": f["asof"]}
            continue
        if np.sign(f["q"]) == np.sign(run_["shares"]):          # adds: average the entry price
            run_["entry_price"] = (run_["entry_price"] * abs(run_["shares"]) + f["px"] * abs(f["q"])) / (abs(run_["shares"]) + abs(f["q"]))
        run_["shares"] += f["q"]
        if f["meta"]:
            run_["meta"] = f["meta"]
        if run_["shares"] == 0:
            p7_rows.append({**run_, "shares": run_["shares"] - f["q"], "status": "Closed", "exit_day": f["day"], "exit_price": f["px"]})
            runs[t] = None
    p7_rows += [{**r_, "status": "Open", "exit_day": "", "exit_price": np.nan} for r_ in runs.values() if r_]
    lp7 = yf.download(sorted({r_["ticker"].replace(".", "-") for r_ in p7_rows}), period="10d", progress=False, auto_adjust=False)["Close"]
    lp7 = lp7 if isinstance(lp7, pd.DataFrame) else lp7.to_frame(p7_rows[0]["ticker"].replace(".", "-"))
    last7 = {c.replace("-", "."): v for c, v in lp7.ffill().iloc[-1].items()}
    th = {}
    for r_ in p7_rows:
        wk = r_["meta"].get("cohort") or r_["week"]
        if wk and wk not in th:
            th[wk] = ld(os.path.join(base, wk), "analysts.json").get("memos", {})
    P = pd.concat([P, pd.DataFrame([{
        "week": r_["meta"].get("cohort") or r_["week"], "ticker": r_["ticker"],
        "name": "SPDR S&P 500 ETF" if r_["ticker"] == "SPY" else r_["ticker"],
        "role": "beta hedge" if r_["ticker"] == "SPY" else "position (lifecycle)", "side": "Long" if r_["shares"] > 0 else "Short",
        "status": r_["status"], "entry_day": r_["entry_day"], "exit_day": r_["exit_day"], "shares": r_["shares"],
        "entry_price": r_["entry_price"], "exit_price": r_["exit_price"], "mark_price": last7.get(r_["ticker"], np.nan),
        "confidence": ((th.get(r_["meta"].get("cohort") or r_["week"], {}).get(r_["ticker"]) or {}).get("memo") or {}).get("confidence"),
        "redteam": None,
        "thesis": ("SPY hedge to zero beta" if r_["ticker"] == "SPY" else
                   ((th.get(r_["meta"].get("cohort") or r_["week"], {}).get(r_["ticker"]) or {}).get("memo") or {}).get("thesis", "")
                   + (f" | horizon {r_['meta'].get('H')} days; exit if: " + "; ".join(r_["meta"].get("kill_conditions", []))
                      if r_["meta"].get("kill_conditions") else ""))}
        for r_ in p7_rows])], ignore_index=True)

recs = []
for _, r in (P.iterrows() if len(P) else []):
    recs.append((lambda r: (lambda i: [
        r.week, r.ticker, r["name"], r.role, r.side, r.status, r.entry_day, r.exit_day, r.shares,
        r.entry_price, r.exit_price, r.mark_price,
        # signed price return: exit (or current, while open) over entry, negated for shorts
        f'=IFERROR(IF(E{i}="Short",-1,1)*(IF(K{i}<>"",K{i},L{i})/J{i}-1),"")',
        # shares are signed (shorts negative), so this is the position's dollar P&L before costs
        f'=IFERROR(I{i}*(IF(K{i}<>"",K{i},L{i})-J{i}),"")',
        r.confidence, r.redteam, r.thesis]))(r))
sheet(ws, cols, recs, {"Name": 26, "Thesis": 90, "Week (as-of Wed)": 12, "Red team": 10})
for i in range(2, len(recs) + 2):
    ws.cell(row=i, column=17).alignment = Alignment(wrap_text=False)

wo = wb.create_sheet("Orders")
O = pd.DataFrame(orders)
ocols = [("Week (as-of Wed)", None), ("Execution day", None), ("Ticker", None), ("Leg", None), ("Side", None),
         ("Ordered", "#,##0"), ("Filled", "#,##0"), ("Order type", None), ("Reference price ($)", "#,##0.00"),
         ("Status", None), ("Fill price ($)", "#,##0.00"), ("Official close ($)", "#,##0.00"), ("Slippage vs close (bp)", "0.0"),
         ("Notional ($)", "#,##0"), ("Client order id", None)]
orecs = []
for _, o in (O.iterrows() if len(O) else []):
    orecs.append((lambda o: (lambda i: [o.week, o.exec_day, o.ticker, o.leg, o.side, o.qty,
                                        o.get("filled_qty") if pd.notna(o.get("filled_qty")) else "pending",
                                        o.order_type, o.ref_price, o.status, o.get("fill_price"), o.get("official_close"),
                                        o.get("slippage_bp"), f'=IFERROR(G{i}*IF(K{i}<>"",K{i},I{i}),"")',
                                        o.client_order_id]))(o))
sheet(wo, ocols, orecs, {"Client order id": 34, "Order type": 16, "Status": 12})

ww = wb.create_sheet("Account")
nav_p = os.path.join(base, "execution", "nav.csv")
N = pd.read_csv(nav_p) if os.path.exists(nav_p) else pd.DataFrame(columns=["date", "equity"])
N = N[N["date"].astype(str) >= min(P["entry_day"])] if len(P) else N.iloc[:0]   # from the first actual trade
nrecs = [(lambda r: (lambda i: [str(r["date"]), float(r["equity"]), "" if i == 2 else f"=B{i}/B{i - 1}-1",
                                f"=B{i}/$B$2-1"]))(r) for _, r in N.iterrows()]
sheet(ww, [("Day", None), ("Paper account value ($)", "$#,##0"), ("Daily return (%)", "0.00%;-0.00%;-"),
           ("Since first trade (%)", "0.00%;-0.00%;-")], nrecs, {"Day": 12, "Paper account value ($)": 16})

wc = wb.create_sheet("Cash activity")
ap_ = os.path.join(base, "execution", "activities.csv")
A_ = pd.read_csv(ap_) if os.path.exists(ap_) else pd.DataFrame(columns=["date", "type", "symbol", "qty", "per_share", "amount"])
A_ = A_[A_["date"].astype(str) >= min(P["entry_day"])] if len(P) and len(A_) else A_.iloc[:0]
arecs = [[str(r["date"]), r["type"], r["symbol"], r["qty"], r["per_share"], float(r["amount"])] for _, r in A_.iterrows()]
sheet(wc, [("Date", None), ("Type", None), ("Ticker", None), ("Quantity", "#,##0"), ("Per share ($)", "#,##0.0000"),
           ("Amount ($)", "#,##0.00;(#,##0.00);-")], arecs, {"Date": 12})

wn = wb.create_sheet("Notes")
notes = [
    "Fund position ledger (Protocol 6). Actual Alpaca paper-account trades only: weeks that were not executed, and model-only books, are left out. Rebuilt automatically after each weekly run and each execution/reconciliation; do not edit.",
    "Positions: one row per lot: a name held for a week, split where a daily review changed the shares (exit, reduce or increase at that day's close). The book is re-decided every Wednesday and traded at the next session's close (market-on-close).",
    "Entry price: the fill if the name traded on the execution day, otherwise that day's official close. Exit price: the next execution day's official close.",
    "Status Open: the week has not ended; Return and P&L use the Current price (latest close). Returns are price returns, dividends excluded, before costs.",
    "P&L ($): signed shares x (exit or current price - entry). Lot boundaries use the actual Alpaca fill of the order traded there (weekly or daily review), else the official close, so lot P&Ls add up to the account's trading P&L.",
    "Cash activity: dividends received on longs and paid on shorts, fees and interest from Alpaca; together with P&L they explain the Account sheet's value.",
    "Account sheet: the paper account's daily value from Alpaca, from the first trade on.",
    "Confidence: the analyst's confidence (0-1); Red team: uphold or weaken. SPY rows are the beta hedge.",
    "Source records: fund-data branch, fund_state/live/<week>/ (book.json, execution.json, analysts.json, redteam.json) and fund_state/live/execution/fills.csv.",
]
for i, t in enumerate(notes, 1):
    c = wn.cell(row=i, column=1, value=t); c.font = F_
wn.column_dimensions["A"].width = 150
wb.calculation.fullCalcOnLoad = True
out = os.path.join(OUT, "fund_positions.xlsx")
wb.save(out)
print(f"ledger: {len(recs)} position rows, {len(orecs)} orders, {len(nrecs)} account days -> {out}")

# ---- dashboard data (GitHub Pages): the same records with returns and P&L computed here
def _f(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v)


pos_out = []
for _, r in (P.iterrows() if len(P) else []):
    px_end = r.exit_price if pd.notna(r.exit_price) else r.mark_price
    sgn = -1 if r.side == "Short" else 1
    ret = sgn * (px_end / r.entry_price - 1) if pd.notna(px_end) and pd.notna(r.entry_price) and r.entry_price else None
    pnl = r.shares * (px_end - r.entry_price) if pd.notna(px_end) and pd.notna(r.entry_price) and pd.notna(r.shares) else None
    pos_out.append({k: _f(v) for k, v in {"week": r.week, "ticker": r.ticker, "name": r["name"], "role": r.role, "side": r.side,
                                          "status": r.status, "entry_day": r.entry_day, "exit_day": r.exit_day or None,
                                          "shares": r.shares, "entry_price": r.entry_price, "exit_price": r.exit_price,
                                          "current_price": r.mark_price, "return": ret, "pnl": pnl,
                                          "confidence": r.confidence, "redteam": r.redteam, "thesis": r.thesis}.items()})
# the page lists only orders that filled (in part or whole), at the quantity that filled
filled_orders = [{**{k: _f(v) for k, v in o.items() if k not in ("target_weight", "filled_qty")}, "qty": float(o["filled_qty"]),
                  "ordered_qty": o["qty"], "status": "filled" if o["filled_qty"] >= o["qty"] else "partial"} for o in orders if o.get("filled_qty") and o["filled_qty"] > 0]
_tp = os.path.join(base, "execution", "tests.csv")
if os.path.exists(_tp):
    for _, t_ in pd.read_csv(_tp, dtype={"day": str}).iterrows():
        if t_.get("filled_qty", 0) > 0:
            filled_orders.append({"week": None, "exec_day": t_["day"], "ticker": t_["symbol"], "leg": "pipeline test",
                                  "side": t_["side"], "qty": float(t_["filled_qty"]), "ordered_qty": int(t_["qty"]),
                                  "order_type": ORDER_TYPE["preclose"], "status": t_["status"], "fill_price": _f(t_["fill"]),
                                  "official_close": _f(t_.get("close")), "slippage_bp": _f(t_.get("slip_bp")),
                                  "client_order_id": t_["client_order_id"]})
_nav_all = pd.read_csv(nav_p) if os.path.exists(nav_p) else pd.DataFrame(columns=["date", "equity"])
dash = {"updated": pd.Timestamp.now(tz="UTC").isoformat(timespec="minutes"), "mode": MODE,
        # the paper account's latest value from Alpaca, shown even before the first trade
        "balance": {"equity": float(_nav_all["equity"].iloc[-1]), "date": str(_nav_all["date"].iloc[-1])} if len(_nav_all) else None,
        "positions": pos_out,
        "orders": filled_orders,
        "account": [{"date": str(r["date"]), "equity": float(r["equity"])} for _, r in N.iterrows()],
        "cash": [{"date": a[0], "type": a[1], "ticker": _f(a[2]), "amount": _f(a[5])} for a in arecs]}


def _clean(v):                                       # browsers reject NaN in JSON: every missing value is null
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_clean(x) for x in v]
    return None if isinstance(v, float) and not np.isfinite(v) else v


json.dump(_clean(dash), open(os.path.join(OUT, "dashboard.json"), "w"), default=str, allow_nan=False)
print(f"dashboard data: {len(pos_out)} positions, {len(orders)} orders -> {os.path.join(OUT, 'dashboard.json')}")
