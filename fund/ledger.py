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

rows, orders = [], []
for d in weeks:
    asof = os.path.basename(d)
    book, ex = ld(d, "book.json"), ld(d, "execution.json")
    if book.get("status") not in ("ok", "degraded_hold"):
        continue
    halted = str(ex.get("reason") or "").startswith("HALT")
    target = ex.get("target_weights") if ex.get("status") == "submitted" else None
    w = target if target is not None else ({} if halted else book["books"].get("fund", {}))
    memos, rt = ld(d, "analysts.json").get("memos", {}), ld(d, "redteam.json")
    S = pd.DataFrame(ld(d, "screen.json").get("rows", [])).set_index("ticker") if ld(d, "screen.json") else pd.DataFrame()
    fills = {}
    for o in ex.get("orders", []):
        orders.append({"week": asof, "exec_day": ex.get("exec_day"), "ticker": o["symbol"], "leg": o["leg"],
                       "side": o["side"], "qty": o["qty"],
                       "order_type": "market-on-close" if o.get("tif") == "cls" else "market (flip)",
                       "ref_price": o.get("price_ref"), "target_weight": o.get("target_weight"),
                       "status": o.get("status"), "client_order_id": o.get("client_order_id")})
    fp = os.path.join(base, "execution", "fills.csv")
    if os.path.exists(fp):
        F = pd.read_csv(fp, dtype={"asof": str})
        for _, f in F[F["asof"] == asof].iterrows():
            if f["leg"] != "flatten" and pd.notna(f.get("fill")):
                fills[f["symbol"]] = float(f["fill"])
            for o in orders:
                if o["week"] == asof and o["ticker"] == f["symbol"] and o["leg"] == f["leg"]:
                    o.update(fill_price=f.get("fill"), official_close=f.get("close"), slippage_bp=f.get("slip_bp"),
                             status=f.get("status"))
    for t, wt in w.items():
        m = (memos.get(t) or {}).get("memo") or {}
        rv = ((rt.get("reviews") or {}).get(t) or {}).get("review") or {}
        r = S.loc[t] if t in S.index else None
        rows.append({"week": asof, "exec_day": ex.get("exec_day"), "ticker": t,
                     "name": (str(r["Security"]) if r is not None else ("SPDR S&P 500 ETF" if t == "SPY" else "")),
                     "sector": (str(r["GICS Sector"]) if r is not None else ("Index hedge" if t == "SPY" else "")),
                     "role": "beta hedge" if t == "SPY" else "position", "side": "Long" if wt > 0 else "Short",
                     "target_weight": float(wt),
                     "shares": ((ex.get("current_qty") or {}).get(t, 0) + sum((o["qty"] if o["side"] == "buy" else -o["qty"])
                                for o in ex.get("orders", []) if o["symbol"] == t and o.get("id"))) if ex else None,
                     "fill": fills.get(t), "analyst_score": m.get("score"), "confidence": m.get("confidence"),
                     "redteam": rv.get("verdict"), "flaw": rv.get("flaw"),
                     "final_score": (rt.get("final_score") or {}).get(t),
                     "earnings_in_week": (str(r["earnings_in_holding_week"]) if r is not None and "earnings_in_holding_week" in r else ""),
                     "beta_hedge": (float(r["beta_hedge"]) if r is not None and "beta_hedge" in r else None),
                     "ret_1w_before": (float(r["ret_1w_pct"]) / 100 if r is not None else None),
                     "attention_shock": (float(r["attention_shock"]) if r is not None and pd.notna(r.get("attention_shock")) else None),
                     "provider": ((memos.get(t) or {}).get("meta") or {}).get("provider"),
                     "thesis": m.get("thesis", "SPY hedge to zero beta" if t == "SPY" else ""),
                     "degraded_hold": book.get("status") == "degraded_hold", "halted": halted})

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
    ent, ext, mark, st, ed, xd = [], [], [], [], [], []
    for _, r in P.iterrows():
        px, t0, t1 = days[r.week]
        c = px[r.ticker] if r.ticker in px else pd.Series(dtype=float)
        e = r.fill if pd.notna(r.fill) else (c.get(t0) if t0 is not None else np.nan)
        ent.append(e); ed.append(str(t0.date()) if t0 is not None else r.exec_day)
        if t1 is not None and pd.notna(c.get(t1, np.nan)):
            ext.append(c[t1]); st.append("Closed"); xd.append(str(t1.date()))
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
         ("Quantity", "#,##0"), ("Order type", None), ("Reference price ($)", "#,##0.00"),
         ("Status", None), ("Fill price ($)", "#,##0.00"), ("Official close ($)", "#,##0.00"), ("Slippage vs close (bp)", "0.0"),
         ("Notional ($)", "#,##0"), ("Client order id", None)]
orecs = []
for _, o in (O.iterrows() if len(O) else []):
    orecs.append((lambda o: (lambda i: [o.week, o.exec_day, o.ticker, o.leg, o.side, o.qty, o.order_type, o.ref_price,
                                        o.status, o.get("fill_price"), o.get("official_close"),
                                        o.get("slippage_bp"), f'=IFERROR(F{i}*IF(J{i}<>"",J{i},H{i}),"")',
                                        o.client_order_id]))(o))
sheet(wo, ocols, orecs, {"Client order id": 34, "Order type": 16, "Status": 12})

ww = wb.create_sheet("Weekly")
wk = pd.read_csv(os.path.join(base, "performance", "weekly_books.csv")) if os.path.exists(os.path.join(base, "performance", "weekly_books.csv")) else pd.DataFrame()
wk = wk[wk["book"] == "fund"] if len(wk) else wk
wcols = [("Week (as-of Wed)", None), ("Gross return (%)", "0.00%"), ("Costs (%)", "0.00%"), ("Net return (%)", "0.00%"),
         ("Excess over cash (%)", "0.00%"), ("Cumulative net (%)", "0.00%")]
wrecs = []
for k, (_, r) in enumerate(wk.iterrows() if len(wk) else []):
    wrecs.append((lambda r, k: (lambda i: [r.asof, r.gross, r.cost, r.get("net"), r.get("excess"),
                                           "=D2" if i == 2 else f"=(1+F{i - 1})*(1+D{i})-1"]))(r, k))
sheet(ww, wcols, wrecs, {"Week (as-of Wed)": 14})
nav_p = os.path.join(base, "execution", "nav.csv")
if os.path.exists(nav_p):
    N = pd.read_csv(nav_p)
    ww.cell(row=1, column=8, value="Broker day").font = H_; ww.cell(row=1, column=8).fill = HF
    ww.cell(row=1, column=9, value="Paper NAV ($)").font = H_; ww.cell(row=1, column=9).fill = HF
    for i, (_, r) in enumerate(N.iterrows(), 2):
        ww.cell(row=i, column=8, value=str(r["date"])).font = F_
        c = ww.cell(row=i, column=9, value=float(r["equity"])); c.font, c.number_format = F_, "$#,##0"

wn = wb.create_sheet("Notes")
notes = [
    "Fund position ledger (Protocol 6). Rebuilt automatically after each weekly run and after each execution reconciliation; do not edit, changes are overwritten.",
    "Positions: one row per name per holding week. The book is re-decided every Wednesday and traded at the next session's close (market-on-close).",
    "Entry price: the fill if the name traded on the execution day, otherwise that day's official close. Exit price: the next execution day's official close.",
    "Status Open: the week has not ended; Return and P&L use the Current price (latest close). Returns are price returns, dividends excluded, before costs.",
    "P&L ($): signed shares x (exit or current price - entry). Weekly sheet: book-level returns from the performance desk, after 5 bp/side costs and in excess of cash.",
    "Confidence: the analyst's confidence (0-1); Red team: uphold or weaken. SPY rows are the beta hedge.",
    "Source records: fund-data branch, fund_state/live/<week>/ (book.json, execution.json, analysts.json, redteam.json) and fund_state/live/execution/fills.csv.",
]
for i, t in enumerate(notes, 1):
    c = wn.cell(row=i, column=1, value=t); c.font = F_
wn.column_dimensions["A"].width = 150
wb.calculation.fullCalcOnLoad = True
out = os.path.join(OUT, "fund_positions.xlsx")
wb.save(out)
print(f"ledger: {len(recs)} position rows, {len(orecs)} orders, {len(wrecs)} weeks -> {out}")
