"""Desk 10 · Execution (PROTOCOL_fund.md, Amendment 3). Alpaca paper account, no LLM.

    python fund/execute.py plan        # everything except sending orders (safe any time)
    python fund/execute.py trade       # Thursday: plan, wait for the close, send, record the fills
    python fund/execute.py reconcile   # after the close: fills, slippage, broker NAV, risk halts
    python fund/execute.py filltest buy SPY 1   # one labelled order through the same send path

The fund book (book.json, committed to `fund-data` before the Thursday deadline) is
turned into whole-share targets at the account's equity and traded at the close of the
first trading day after the as-of Wednesday, the price the performance desk scores at.
Orders go out in the last minute before the close (fund/broker.py: the paper account has
no closing auction, so market-on-close orders there only partly fill). A name that flips
side is closed first and reopened once the close leg has filled; those are logged as flips.

Pre-trade rules (all logged in execution.json):
* no valid book after the deadline, a HALT file, or a book that fails sanity checks
  (gross incl. SPY > 3, any stock > 12% of NAV) -> target flat;
* longs must be tradable, shorts shortable and easy to borrow; a dropped name's beta is
  given back to the SPY hedge so the book stays beta neutral;
* gross incl. SPY is scaled down to 1.8x equity if needed (Reg T overnight limit is 2x);
* the account must be dedicated to the fund: positions not in the book are closed.
Idempotent: client_order_id = fund-<asof>-<symbol>-<leg>, and a week with an
execution.json marked submitted is never traded again.
"""

import glob
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import broker
from broker import ET, api
from common import MODE, STATE, week_dir

mode = sys.argv[1]
assert mode in ("plan", "trade", "reconcile", "filltest"), mode
GROSS_MAX, NAME_MAX, BOOK_GROSS_MAX = 1.8, 0.12, 3.0
HALT_DD, HALT_WEEK = 0.10, 0.05
EXEC = os.path.join(STATE, MODE, "execution")
HALT = os.path.join(STATE, MODE, "HALT")
os.makedirs(EXEC, exist_ok=True)
if os.path.exists(os.path.join(EXEC, "problems.txt")):
    os.remove(os.path.join(EXEC, "problems.txt"))              # only this run's problems reach the alert

if mode == "filltest":                              # python fund/execute.py filltest buy|sell SYMBOL QTY
    side, sym, qty = sys.argv[2], sys.argv[3].upper(), int(sys.argv[4])
    assert side in ("buy", "sell") and qty > 0
    clock = broker.Clock()
    if not clock.is_open:
        raise SystemExit("filltest: the market is closed today")
    close_at = clock.next_close.timestamp()
    day = datetime.fromtimestamp(close_at, ET).date()
    o = {"symbol": sym, "leg": "test", "side": side, "qty": qty, "client_order_id": f"fund-test-{day:%Y%m%d}-{sym}-{side}"}
    print(f"pipeline test: {side} {qty} {sym} before the {datetime.fromtimestamp(close_at, ET):%H:%M} ET close", flush=True)
    broker.send([o], close_at, clock)
    tp = os.path.join(EXEC, "tests.csv")
    T = pd.read_csv(tp, dtype={"day": str}) if os.path.exists(tp) else pd.DataFrame()
    row = {"day": str(day), "symbol": sym, "side": side, "qty": qty, "status": o["status"], "filled_qty": o["filled_qty"],
           "fill": o["fill_price"], "ids": " ".join(o["ids"]), "client_order_id": o["client_order_id"],
           "close": np.nan, "slip_bp": np.nan}
    T = pd.concat([T[(T.get("client_order_id", pd.Series(dtype=str)) != o["client_order_id"])] if len(T) else T, pd.DataFrame([row])])
    T.to_csv(tp, index=False)
    print(f"pipeline test: {o['status']}, {o['filled_qty']:g}/{qty} filled at {o['fill_price']}")
    if o["status"] != "filled":
        open(os.path.join(EXEC, "problems.txt"), "w").write(f"pipeline test {day}: {o['status']} ({o['filled_qty']:g}/{qty})\n")
        sys.exit(1)
    sys.exit(0)


now_et = datetime.now(ET)
today = now_et.date()
if os.environ.get("FUND_ASOF"):
    asof = pd.Timestamp(os.environ["FUND_ASOF"])
else:
    asof = pd.Timestamp(today - timedelta(days=(today.weekday() - 2) % 7 or 7))   # latest Wednesday before today
st, cal = api("GET", f"/v2/calendar?start={(asof + pd.Timedelta(days=1)).date()}&end={(asof + pd.Timedelta(days=10)).date()}")
assert st == 200 and cal, f"calendar unavailable: {st} {cal}"
exec_day = pd.Timestamp(cal[0]["date"]).date()
close_et = datetime.combine(exec_day, datetime.strptime(cal[0]["close"], "%H:%M").time(), ET)
wd = week_dir(asof)
out_p = os.path.join(wd, "execution.json")
problems = []

# ------------------------------------------------------------------ reconcile
if mode == "reconcile":
    import yfinance as yf
    done = []
    # every order-bearing record: the weekly execution and each daily review (Amendment 5)
    recs = [(p, "execution") for p in glob.glob(os.path.join(STATE, MODE, "20*", "execution.json"))]
    recs += [(p, "review") for p in glob.glob(os.path.join(STATE, MODE, "20*", "reviews", "*.json"))]
    for p, kind in sorted(recs):
        ex = json.load(open(p))
        if ex.get("status") != "submitted" or ex.get("reconciled"):
            continue
        dstr = ex["exec_day"] if kind == "execution" else ex["day"]
        day = pd.Timestamp(dstr)
        if datetime.now(ET) < datetime.combine(day.date(), datetime.strptime(ex.get("close_et", "16:00"), "%H:%M").time(), ET) + timedelta(minutes=45):
            continue
        rows = []
        for o in ex["orders"]:
            ids = o.get("ids") or ([o["id"]] if o.get("id") else [])         # every attempt (broker.send)
            q, fpx, last = broker.fills(ids)
            rows.append({"symbol": o["symbol"], "leg": o["leg"], "side": o["side"], "qty": o["qty"],
                         "status": broker.fill_status(o["qty"], q, bool(ids)), "filled_qty": q,
                         "fill_ratio": q / o["qty"] if o["qty"] else np.nan,
                         "fill": fpx if fpx is not None else np.nan, "filled_at": last})
        F = pd.DataFrame(rows)
        if len(F):
            syms = sorted(F["symbol"].unique())
            px = yf.download([s.replace(".", "-") for s in syms], start=day, end=day + pd.Timedelta(days=1),
                             progress=False, auto_adjust=False)["Close"]
            px = px if isinstance(px, pd.DataFrame) else px.to_frame(syms[0].replace(".", "-"))
            close = px.rename(columns=lambda c: c.replace("-", ".")).iloc[-1] if len(px) else pd.Series(dtype=float)
            F["close"] = F["symbol"].map(close)
            F["slip_bp"] = np.where(F["side"] == "buy", 1, -1) * (F["fill"] / F["close"] - 1) * 1e4   # + = worse than the close
        F.insert(0, "asof", ex["asof"]); F.insert(1, "exec_day", dstr); F.insert(2, "source", kind)
        fp = os.path.join(EXEC, "fills.csv")
        old = pd.read_csv(fp, dtype={"asof": str, "exec_day": str}) if os.path.exists(fp) else pd.DataFrame({"asof": [], "exec_day": []})
        if "source" not in old:
            old["source"] = "execution"
        keep = ~((old["asof"] == ex["asof"]) & (old["exec_day"] == dstr) & (old["source"] == kind))
        pd.concat([old[keep], F]).sort_values(["asof", "exec_day"]).to_csv(fp, index=False)
        s_, acct = api("GET", "/v2/account")
        s_, pos = api("GET", "/v2/positions")
        eq = float(acct["equity"])
        real = {p_["symbol"]: float(p_["market_value"]) / eq for p_ in (pos or [])}
        tgt = ex["target_weights"]
        track = sum(abs(real.get(k, 0) - tgt.get(k, 0)) for k in set(real) | set(tgt))
        cls = F[F["leg"] != "flatten"] if len(F) else F
        ex["reconciled"] = {"at": datetime.utcnow().isoformat(timespec="seconds"), "equity": eq,
                            "n_orders": int(len(F)), "n_filled": int((F["status"] == "filled").sum()) if len(F) else 0,
                            "n_not_filled": int((F["status"] != "filled").sum()) if len(F) else 0,
                            "median_abs_slip_bp_close": float(cls["slip_bp"].abs().median()) if len(cls) and cls["slip_bp"].notna().any() else None,
                            "tracking_gross": track}
        json.dump(ex, open(p, "w"), indent=1, default=str)
        done.append(f"{kind} {ex['asof']} {dstr}")
        if ex["reconciled"]["n_not_filled"]:
            problems.append(f"{kind} {dstr}: {ex['reconciled']['n_not_filled']} orders not filled")
        print(f"reconciled {kind} {dstr}: {ex['reconciled']}")
    # labelled pipeline tests (filltest): official close and slippage once the day has closed
    tp = os.path.join(EXEC, "tests.csv")
    if os.path.exists(tp):
        T = pd.read_csv(tp, dtype={"day": str})
        # a test day is done 45 minutes after its close (the reconcile runs at 21:10 ET on the same date)
        done_ = pd.to_datetime(T["day"]) + pd.Timedelta(hours=16, minutes=45) <= pd.Timestamp(datetime.now(ET).replace(tzinfo=None))
        todo = T["close"].isna() & T["fill"].notna() & done_
        for i in T.index[todo]:
            px = yf.download(T.at[i, "symbol"].replace(".", "-"), start=T.at[i, "day"],
                             end=pd.Timestamp(T.at[i, "day"]) + pd.Timedelta(days=1), progress=False, auto_adjust=False)["Close"]
            if len(px):
                T.at[i, "close"] = float(np.ravel(px.to_numpy())[-1])
                T.at[i, "slip_bp"] = (1 if T.at[i, "side"] == "buy" else -1) * (T.at[i, "fill"] / T.at[i, "close"] - 1) * 1e4
                print(f"pipeline test {T.at[i, 'day']} {T.at[i, 'side']} {T.at[i, 'symbol']}: {T.at[i, 'status']}, "
                      f"fill {T.at[i, 'fill']:.2f} vs close {T.at[i, 'close']:.2f} = {T.at[i, 'slip_bp']:+.1f} bp")
                if T.at[i, "status"] != "filled" or abs(T.at[i, "slip_bp"]) > 10:
                    problems.append(f"pipeline test {T.at[i, 'day']}: {T.at[i, 'status']}, slippage {T.at[i, 'slip_bp']:+.1f} bp (limit 10)")
        T.to_csv(tp, index=False)
    # cash activity (dividends paid or received, fees, interest): the part of broker P&L that
    # price returns leave out
    s_, act = api("GET", "/v2/account/activities?activity_types=DIV,DIVCGL,DIVCGS,DIVNRA,DIVROC,DIVTXEX,FEE,INT,PTC&page_size=100")
    if s_ == 200 and act:
        A = pd.DataFrame([{"date": a.get("date") or (a.get("transaction_time") or "")[:10], "type": a.get("activity_type"),
                           "symbol": a.get("symbol"), "qty": a.get("qty"), "per_share": a.get("per_share_amount"),
                           "amount": float(a.get("net_amount") or 0), "id": a.get("id")} for a in act])
        ap = os.path.join(EXEC, "activities.csv")
        old = pd.read_csv(ap, dtype=str) if os.path.exists(ap) else pd.DataFrame(columns=A.columns)
        pd.concat([old, A.astype(str)]).drop_duplicates("id").sort_values("date").to_csv(ap, index=False)
    # broker equity curve and the risk halts (drawdown from peak, one-week loss)
    s_, ph = api("GET", "/v2/account/portfolio/history?period=1A&timeframe=1D")
    if s_ == 200 and ph and ph.get("equity"):
        N = pd.DataFrame({"date": pd.to_datetime(ph["timestamp"], unit="s").date, "equity": ph["equity"]}).dropna()
        N = N[N["equity"] > 0]
        N.to_csv(os.path.join(EXEC, "nav.csv"), index=False)
        if len(N) > 1:
            e = N["equity"].to_numpy()
            dd = 1 - e[-1] / e.max()
            wk = e[-1] / e[max(0, len(e) - 6)] - 1                     # ~5 trading days
            print(f"broker NAV {e[-1]:,.0f}, drawdown from peak {dd:.1%}, last 5 sessions {wk:+.1%}")
            if (dd >= HALT_DD or wk <= -HALT_WEEK) and not os.path.exists(HALT):
                open(HALT, "w").write(json.dumps({"at": datetime.utcnow().isoformat(timespec="seconds"),
                                                  "drawdown": dd, "week": wk}) + "\n")
                problems.append(f"HALT: drawdown {dd:.1%}, week {wk:+.1%}. The next execution goes flat until resumed.")
    print("reconcile:", done or "nothing to reconcile")
    if problems:
        open(os.path.join(EXEC, "problems.txt"), "w").write("\n".join(problems) + "\n")
        raise SystemExit("; ".join(problems))
    sys.exit(0)

# ------------------------------------------------------------------ plan / trade
clock = broker.Clock()
close_at = close_et.timestamp()
lead = broker.CLS_CUTOFF if broker.STYLE == "cls" else broker.PREPARE_AT + 30
if mode == "trade":
    if today != exec_day:
        print(f"no execution today: the week of {asof.date()} trades on {exec_day}"); sys.exit(0)
    if os.path.exists(out_p) and json.load(open(out_p)).get("status") == "submitted":
        print(f"{asof.date()} already executed; nothing to do"); sys.exit(0)
    if clock.now() > close_at - lead:
        problems.append(f"missed the execution window (orders are prepared by {datetime.fromtimestamp(close_at - lead, ET):%H:%M:%S} ET)")
deadline_passed = datetime.now(ET) >= datetime.combine(asof.date() + timedelta(days=1), datetime.min.time(),
                                                        ZoneInfo("UTC")).astimezone(ET) + timedelta(hours=19)

# the target: the fund book, or flat
reason, book, target = None, None, {}
bp = os.path.join(wd, "book.json")
if os.path.exists(HALT):
    reason = f"HALT file present ({open(HALT).read().strip()}): flat"
elif not os.path.exists(bp):
    if mode == "trade" and not deadline_passed:
        print("no book yet and the deadline has not passed: waiting for a later run"); sys.exit(0)
    reason = "no book for this week: flat"
else:
    book = json.load(open(bp))
    if book.get("status") not in ("ok", "degraded_hold"):
        reason = f"book status {book.get('status')!r}: flat"
    else:
        w = {k: float(v) for k, v in book["books"].get("fund", {}).items()}
        stock = {k: v for k, v in w.items() if k != "SPY"}
        if sum(map(abs, w.values())) > BOOK_GROSS_MAX or (stock and max(map(abs, stock.values())) > NAME_MAX):
            reason = "book fails sanity checks (gross or single-name limit): flat"
            problems.append(reason)
        else:
            target = w
if reason:
    print(reason)

acct = broker.account()
if not acct.get("shorting_enabled") and any(v < 0 for k, v in target.items()):
    problems.append("shorting is not enabled on the account (needs >= $2,000 equity and margin): shorts dropped")

# eligibility: longs tradable, shorts shortable and easy to borrow; hand dropped beta to SPY
beta = {}
sp = os.path.join(wd, "screen.json")
if os.path.exists(sp):
    beta = {r["ticker"]: r.get("beta_hedge", r.get("beta60")) for r in json.load(open(sp))["rows"]}
dropped = {}
for sym, wt in list(target.items()):
    s_, a = api("GET", f"/v2/assets/{sym}")
    ok = s_ == 200 and a.get("tradable") and a.get("status") == "active"
    if wt < 0:
        ok = ok and a.get("shortable") and a.get("easy_to_borrow") and acct.get("shorting_enabled")
    if not ok:
        dropped[sym] = {"weight": wt, "why": (a or {}).get("message") or {k: (a or {}).get(k) for k in ("tradable", "shortable", "easy_to_borrow", "status")}}
        target.pop(sym)
        if sym == "SPY":
            problems.append("SPY not tradable: the book is unhedged")
        else:
            target["SPY"] = target.get("SPY", 0.0) + wt * float(beta.get(sym) or 1.0)
target = {k: v for k, v in target.items() if abs(v) > 1e-6}
gross = sum(map(abs, target.values()))
scale = min(1.0, GROSS_MAX / gross) if gross else 1.0
target = {k: v * scale for k, v in target.items()}


def build_orders(equity, cur, price):
    """Whole-share orders from the target weights at the given equity, holdings and prices."""
    out, issues = [], []
    for sym in sorted(set(target) | set(cur)):
        cq = int(cur.get(sym, 0))
        if sym in target and sym not in price:
            issues.append(f"{sym}: no price, not traded"); continue
        tq = int(round(target.get(sym, 0.0) * equity / price[sym])) if sym in target else 0
        if tq == cq:
            continue
        if cq and tq and np.sign(tq) != np.sign(cq):      # through zero: close first, reopen once that has filled
            out.append({"symbol": sym, "leg": "flatten", "side": "sell" if cq > 0 else "buy", "qty": abs(cq)})
            out.append({"symbol": sym, "leg": "open", "side": "buy" if tq > 0 else "sell", "qty": abs(tq)})
        else:
            out.append({"symbol": sym, "leg": "close" if tq == 0 else "rebalance", "side": "buy" if tq > cq else "sell",
                        "qty": abs(tq - cq)})
    for o in out:
        o.update(target_weight=round(target.get(o["symbol"], 0.0), 5), price_ref=price.get(o["symbol"]),
                 client_order_id=f"fund-{asof.date()}-{o['symbol']}-{o['leg']}")
    return out, issues


def show(orders, equity):
    print(f"{asof.date()} -> trades {exec_day} (close {cal[0]['close']} ET, {broker.STYLE}); equity {equity:,.0f}; "
          f"{len(target)} targets, gross {sum(map(abs, target.values())):.2f}, scale {scale:.2f}; "
          f"{len(orders)} orders ({sum(o['leg'] == 'flatten' for o in orders)} flips); dropped {list(dropped)}", flush=True)
    for o in orders:
        print(f"  {o['leg']:9s} {o['side']:4s} {o['qty']:>6d} {o['symbol']:6s} @~{o['price_ref']} (target w {o['target_weight']:+.4f})")


cur = broker.positions()
equity = float(acct["equity"])
orders, issues = build_orders(equity, cur, broker.prices(set(target) | set(cur)))
plan = {"asof": str(asof.date()), "exec_day": str(exec_day), "close_et": cal[0]["close"], "mode": mode,
        "style": broker.STYLE, "planned_at_et": now_et.isoformat(timespec="seconds"), "equity": equity, "reason": reason,
        "scale": scale, "dropped": dropped, "target_weights": {k: round(v, 5) for k, v in target.items()},
        "current_qty": cur, "orders": orders, "problems": problems + issues}
show(orders, equity)

if mode == "plan" or any(p.startswith("missed") for p in problems):
    plan["status"] = "planned" if mode == "plan" else "missed_window"
    if mode == "trade":
        json.dump(plan, open(out_p, "w"), indent=1, default=str)
    if plan["problems"]:
        print("problems:", plan["problems"])
    sys.exit(1 if mode == "trade" and plan["problems"] else 0)

# ------------------------------------------------------------------ send
plan["status"] = "waiting"
json.dump(plan, open(out_p, "w"), indent=1, default=str)
if broker.STYLE == "preclose":
    print(f"waiting until {datetime.fromtimestamp(close_at - broker.PREPARE_AT, ET):%H:%M:%S} ET to size the orders", flush=True)
    clock.sleep_until(close_at - broker.PREPARE_AT)
    acct = broker.account()
    cur, equity = broker.positions(), float(acct["equity"])
    orders, issues = build_orders(equity, cur, broker.prices(set(target) | set(cur)))
    plan.update(equity=equity, current_qty=cur, orders=orders, sized_at_et=datetime.now(ET).isoformat(timespec="seconds"))
    show(orders, equity)
# any open order that is not part of this plan is cancelled (the account is dedicated to the fund)
s_, open_orders = api("GET", "/v2/orders?status=open&limit=500")
mine = tuple(o["client_order_id"] for o in orders)
for x in open_orders or []:
    if not x["client_order_id"].startswith(mine):
        api("DELETE", f"/v2/orders/{x['id']}")
broker.send(orders, close_at, clock)
problems += issues + broker.problems_of(orders)
plan.update(status="submitted", orders=orders, problems=problems, submitted_at_et=datetime.now(ET).isoformat(timespec="seconds"))
json.dump(plan, open(out_p, "w"), indent=1, default=str)
n_full = sum(o["status"] == "filled" for o in orders)
print(f"{n_full}/{len(orders)} orders fully filled")
if problems:
    print("problems:", problems)
    open(os.path.join(EXEC, "problems.txt"), "w").write("\n".join(f"{asof.date()}: {p}" for p in problems) + "\n")
    sys.exit(1)
