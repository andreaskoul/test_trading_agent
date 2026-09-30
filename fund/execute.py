"""Desk 10 · Execution (PROTOCOL_fund.md, Amendment 3). Alpaca paper account, no LLM.

    python fund/execute.py plan        # everything except sending orders (safe any time)
    python fund/execute.py trade       # Thursday: send the week's orders for the closing auction
    python fund/execute.py reconcile   # after the close: fills, slippage, broker NAV, risk halts

The fund book (book.json, committed to `fund-data` before the Thursday deadline) is
turned into whole-share targets at the account's equity and traded at the close of the
first trading day after the as-of Wednesday, the price the performance desk scores at:
market-on-close orders (time_in_force "cls"), sent while the market is open. Alpaca
rejects an order that takes a position through zero, so a name that flips side is
closed with a market order first and reopened on the close; those are logged as flips.

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
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from common import MODE, STATE, week_dir

mode = sys.argv[1]
assert mode in ("plan", "trade", "reconcile"), mode
BASE = os.environ.get("ALPACA_BASE", "https://paper-api.alpaca.markets")
if "paper" not in BASE and os.environ.get("FUND_LIVE_TRADING") != "1":
    raise SystemExit("refusing a non-paper Alpaca endpoint without FUND_LIVE_TRADING=1")
DATA = os.environ.get("ALPACA_DATA", "https://data.alpaca.markets")
H = {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"], "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"],
     "Content-Type": "application/json"}
ET = ZoneInfo("America/New_York")
GROSS_MAX, NAME_MAX, BOOK_GROSS_MAX = 1.8, 0.12, 3.0
HALT_DD, HALT_WEEK = 0.10, 0.05
EXEC = os.path.join(STATE, MODE, "execution")
HALT = os.path.join(STATE, MODE, "HALT")
os.makedirs(EXEC, exist_ok=True)
if os.path.exists(os.path.join(EXEC, "problems.txt")):
    os.remove(os.path.join(EXEC, "problems.txt"))              # only this run's problems reach the alert


def api(method, path, body=None, base=BASE):
    """One REST call; returns (status, parsed json). 5xx and 429 are retried."""
    for attempt in range(4):
        req = urllib.request.Request(base + path, method=method, headers=H,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                txt = r.read()
                return r.status, (json.loads(txt) if txt else None)
        except urllib.error.HTTPError as e:
            txt = e.read()
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt * 2); continue
            try:
                return e.code, json.loads(txt)
            except Exception:
                return e.code, {"message": txt.decode(errors="replace")}
        except Exception as exc:
            if attempt == 3:
                return 0, {"message": repr(exc)}
            time.sleep(2 ** attempt * 2)


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
            if not o.get("id"):
                rows.append({**{k: o.get(k) for k in ("symbol", "leg", "side", "qty")}, "status": o.get("status", "not_sent")}); continue
            s_, od = api("GET", f"/v2/orders/{o['id']}")
            rows.append({"symbol": o["symbol"], "leg": o["leg"], "side": o["side"], "qty": o["qty"],
                         "status": od.get("status"), "filled_qty": float(od.get("filled_qty") or 0),
                         "fill": float(od["filled_avg_price"]) if od.get("filled_avg_price") else np.nan,
                         "filled_at": od.get("filled_at")})
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
if mode == "trade":
    if today != exec_day:
        print(f"no execution today: the week of {asof.date()} trades on {exec_day}"); sys.exit(0)
    if os.path.exists(out_p) and json.load(open(out_p)).get("status") == "submitted":
        print(f"{asof.date()} already executed; nothing to do"); sys.exit(0)
    if now_et > close_et - timedelta(minutes=15):
        problems.append(f"missed the execution window (closing auction cutoff {close_et - timedelta(minutes=10):%H:%M} ET)")
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

s_, acct = api("GET", "/v2/account")
assert s_ == 200, f"account unavailable: {s_} {acct}"
equity = float(acct["equity"])
if acct.get("trading_blocked") or acct.get("account_blocked"):
    raise SystemExit("Alpaca account is blocked")
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

# prices for sizing: latest trade (IEX), else today's or yesterday's daily bar
s_, pos = api("GET", "/v2/positions")
assert s_ == 200, f"positions unavailable: {s_} {pos}"
cur = {p_["symbol"]: (-1 if p_["side"] == "short" else 1) * abs(float(p_["qty"])) for p_ in pos}
syms = sorted(set(target) | set(cur))
price = {}
for i in range(0, len(syms), 100):
    s_, snap = api("GET", "/v2/stocks/snapshots?feed=iex&symbols=" + ",".join(syms[i:i + 100]), base=DATA)
    for k, v in (snap or {}).items():
        for f in ("latestTrade", "dailyBar", "prevDailyBar"):
            px = ((v or {}).get(f) or {}).get("p" if f == "latestTrade" else "c")
            if px:
                price[k] = float(px); break
orders = []
for sym in syms:
    tq = int(round(target.get(sym, 0.0) * equity / price[sym])) if sym in target and sym in price else 0
    if sym in target and sym not in price:
        problems.append(f"{sym}: no price, not traded"); tq = int(cur.get(sym, 0))
    cq = int(cur.get(sym, 0))
    if tq == cq:
        continue
    if cq and tq and np.sign(tq) != np.sign(cq):          # through zero: flatten now, reopen on the close
        orders.append({"symbol": sym, "leg": "flatten", "side": "sell" if cq > 0 else "buy", "qty": abs(cq), "tif": "day"})
        orders.append({"symbol": sym, "leg": "open", "side": "buy" if tq > 0 else "sell", "qty": abs(tq), "tif": "cls"})
    else:
        d = tq - cq
        orders.append({"symbol": sym, "leg": "close" if tq == 0 else "rebalance", "side": "buy" if d > 0 else "sell",
                       "qty": abs(d), "tif": "cls"})
for o in orders:
    o.update(target_weight=round(target.get(o["symbol"], 0.0), 5), price_ref=price.get(o["symbol"]),
             client_order_id=f"fund-{asof.date()}-{o['symbol']}-{o['leg']}")

plan = {"asof": str(asof.date()), "exec_day": str(exec_day), "close_et": cal[0]["close"], "mode": mode,
        "planned_at_et": now_et.isoformat(timespec="seconds"), "equity": equity, "reason": reason,
        "scale": scale, "dropped": dropped, "target_weights": {k: round(v, 5) for k, v in target.items()},
        "current_qty": cur, "orders": orders, "problems": problems}
print(f"{asof.date()} -> trades {exec_day} (close {cal[0]['close']} ET); equity {equity:,.0f}; "
      f"{len(target)} targets, gross {sum(map(abs, target.values())):.2f}, scale {scale:.2f}; "
      f"{len(orders)} orders ({sum(o['leg'] == 'flatten' for o in orders)} flips); dropped {list(dropped)}")
for o in orders:
    print(f"  {o['leg']:9s} {o['side']:4s} {o['qty']:>6d} {o['symbol']:6s} @~{o['price_ref']} tif={o['tif']} (target w {o['target_weight']:+.4f})")

if mode == "plan" or any(p.startswith("missed") for p in problems):
    plan["status"] = "planned" if mode == "plan" else "missed_window"
    if mode == "trade":
        json.dump(plan, open(out_p, "w"), indent=1, default=str)
    if problems:
        print("problems:", problems)
    sys.exit(1 if mode == "trade" and problems else 0)

# ------------------------------------------------------------------ send
# Idempotency: orders this week's plan already sent (an earlier run that died before saving)
# are adopted, not resent; any other open order on the account is cancelled.
s_, today_orders = api("GET", f"/v2/orders?status=all&limit=500&after={exec_day}T00:00:00Z")
sent = {x["client_order_id"]: x for x in (today_orders or [])}
mine = {o["client_order_id"] for o in orders}
for x in today_orders or []:
    if x["status"] in ("new", "accepted", "pending_new", "held", "partially_filled") and x["client_order_id"] not in mine:
        api("DELETE", f"/v2/orders/{x['id']}")
s_, clock = api("GET", "/v2/clock")
for o in orders:
    if o["client_order_id"] in sent:
        o["id"], o["status"] = sent[o["client_order_id"]]["id"], sent[o["client_order_id"]]["status"]; continue
    if o["leg"] == "flatten" and not clock.get("is_open"):
        o["status"] = "skipped: market closed, cannot flatten before the close"; problems.append(f"{o['symbol']}: flip skipped")
        continue
    if o["leg"] == "open" and any(x["symbol"] == o["symbol"] and x["leg"] == "flatten" and x.get("status") != "filled" for x in orders):
        o["status"] = "skipped: flatten leg not filled"; problems.append(f"{o['symbol']}: reopen skipped"); continue
    s_, r = api("POST", "/v2/orders", {"symbol": o["symbol"], "qty": str(o["qty"]), "side": o["side"], "type": "market",
                                        "time_in_force": o["tif"], "client_order_id": o["client_order_id"]})
    if s_ not in (200, 201):
        o["status"] = f"rejected: {r.get('message') if r else s_}"; problems.append(f"{o['symbol']} {o['leg']}: {o['status']}")
        continue
    o["id"], o["status"] = r["id"], r["status"]
    if o["leg"] == "flatten":                                           # wait for the fill before reopening
        for _ in range(45):
            time.sleep(2)
            s_, r = api("GET", f"/v2/orders/{o['id']}")
            if r.get("status") in ("filled", "canceled", "rejected", "expired"):
                break
        o["status"] = r.get("status")
        o["fill_price"] = float(r["filled_avg_price"]) if r.get("filled_avg_price") else None
plan.update(status="submitted", problems=problems, submitted_at_et=datetime.now(ET).isoformat(timespec="seconds"))
json.dump(plan, open(out_p, "w"), indent=1, default=str)
print(f"submitted {sum(1 for o in orders if o.get('id'))}/{len(orders)} orders")
if problems:
    print("problems:", problems)
    open(os.path.join(EXEC, "problems.txt"), "w").write("\n".join(f"{asof.date()}: {p}" for p in problems) + "\n")
    sys.exit(1)
