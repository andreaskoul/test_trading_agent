"""Desk 12 · Daily position review (PROTOCOL_fund.md, Amendment 5).

    python fund/review.py plan     # decide, no orders
    python fund/review.py trade    # decide, then trade in the last minute before the close (fund/broker.py)

On every trading day strictly between the week's execution day and the next one, each
held stock is re-read against the news published since the last review (or since the
weekly book's Wednesday 22:00 UTC cutoff). No new article: hold, no LLM call.
Otherwise one reviewer call proposes hold / exit / reduce / increase, and any action
other than hold needs a second, adversarial confirmation naming no flaw.
* exit -> 0; reduce -> half the current weight; increase -> 1.5x the book's weight,
  capped at 10% of NAV, at most once per name per week. At most 5 actions a day,
  largest positions first.
* Increases are dropped if stock dollar net would exceed 10% of stock gross and be more unbalanced than before.
* SPY is re-hedged to zero beta with the same hedge betas as the book.
Trades go out in the last minute before the same day's close (fund/broker.py).
-> fund_state/<mode>/<asof>/reviews/<YYYY-MM-DD>.json (plan mode: <YYYY-MM-DD>.plan.json)
"""

import glob
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from common import MODE, STATE, llm, news_cutoff, require

mode = sys.argv[1]
assert mode in ("plan", "trade"), mode
require("OPENROUTER_API_KEY", "FINNHUB_API_KEY")
import broker                                       # noqa: E402  (needs the Alpaca keys checked above)
from broker import ET, api                          # noqa: E402
NAME_CAP, DOLLAR_CAP, MAX_ACTIONS, UP, DOWN = 0.10, 0.10, 5, 1.5, 0.5


now_utc = datetime.now(timezone.utc)
now_et = now_utc.astimezone(ET)
today = now_et.date()
base = os.path.join(STATE, MODE)
# the week being held: the latest executed book
execs = sorted(p for p in glob.glob(os.path.join(base, "20*", "execution.json"))
               if json.load(open(p)).get("status") == "submitted")
if not execs:
    print("review: no executed week yet; nothing is held"); sys.exit(0)
wd = os.path.dirname(execs[-1])
asof = pd.Timestamp(os.path.basename(wd))
ex = json.load(open(execs[-1]))
exec_day = pd.Timestamp(ex["exec_day"]).date()
s_, cal = api("GET", f"/v2/calendar?start={exec_day}&end={exec_day + timedelta(days=14)}")
assert s_ == 200 and cal, f"calendar unavailable: {s_} {cal}"
days = [pd.Timestamp(c["date"]).date() for c in cal]
next_exec = next(d for d in days if d > (asof + pd.Timedelta(days=7)).date())
if mode == "trade" and not (exec_day < today < next_exec and today in days):
    print(f"review: {today} is not a review day for the week of {asof.date()} "
          f"(executed {exec_day}, next execution {next_exec})"); sys.exit(0)
close_et = datetime.combine(today, datetime.strptime(next((c["close"] for c in cal if pd.Timestamp(c["date"]).date() == today), "16:00"), "%H:%M").time(), ET)
rdir = os.path.join(wd, "reviews")
os.makedirs(rdir, exist_ok=True)
out_p = os.path.join(rdir, f"{today}.json" if mode == "trade" else f"{today}.plan.json")
if mode == "trade" and os.path.exists(out_p) and json.load(open(out_p)).get("status") in ("submitted", "no_action"):
    print(f"review: {today} already done"); sys.exit(0)
if os.path.exists(os.path.join(base, "HALT")):
    print("review: HALT active; no reviews until resumed"); sys.exit(0)
clock = broker.Clock()
lead = broker.CLS_CUTOFF if broker.STYLE == "cls" else broker.PREPARE_AT + 30
if mode == "trade" and clock.now() > close_et.timestamp() - lead:
    raise SystemExit(f"review: past the order window for {today}")

prior = sorted(p for p in glob.glob(os.path.join(rdir, "*.json"))
               if not p.endswith(".plan.json") and os.path.basename(p) < f"{today}.json")
prev_reviews = [json.load(open(p)) for p in prior]
since = pd.Timestamp(prev_reviews[-1]["news_until"]) if prev_reviews else news_cutoff(asof).tz_localize("UTC")
increased = {t for r in prev_reviews for t, d in r.get("decisions", {}).items() if d.get("final") == "increase"}
memos = json.load(open(os.path.join(wd, "analysts.json")))["memos"]
S = pd.DataFrame(json.load(open(os.path.join(wd, "screen.json")))["rows"]).set_index("ticker")
beta = (S["beta_hedge"] if "beta_hedge" in S else S["beta60"]).fillna(1.0)
book_w = ex.get("target_weights", {})

s_, acct = api("GET", "/v2/account"); equity = float(acct["equity"])
s_, pos = api("GET", "/v2/positions")
held = {p["symbol"]: {"qty": (-1 if p["side"] == "short" else 1) * abs(float(p["qty"])), "mv": float(p["market_value"]),
                      "price": float(p["current_price"]), "plpc": float(p.get("unrealized_plpc") or 0),
                      "entry": float(p["avg_entry_price"])} for p in pos or []}
w_now = {t: h["mv"] / equity for t, h in held.items()}

REVIEW = """You are the portfolio manager of a long-short equity fund reviewing ONE position between
weekly rebalances. You get the position (side, weight), the analyst thesis it was opened on, the
move since entry, and ONLY the news published since the last review. Decide:
  hold     - default. Nothing new and material, or the news is opinion, price-target chatter,
             recycled coverage, or already reflected in the move since entry.
  exit     - a new, dated, material event directly breaks the thesis (e.g. guidance cut for a long,
             a takeover bid for a short, a thesis catalyst cancelled, fraud/regulatory action).
  reduce   - new material news weakens the thesis or triggers one of its stated risks, without breaking it.
  increase - new material news confirms the thesis beyond what it already expected and the move since
             entry has not priced it.
Cite the numbered articles you rely on. Return JSON only:
{"action": "hold"|"exit"|"reduce"|"increase", "evidence": [int], "reason": str <= 50 words}"""
CONFIRM = """You are the fund's risk officer. A proposed trade on an existing position must be justified by
NEW, dated, material news. Confirm it unless you can name one of these flaws:
  factual    - the reason misstates what the articles say
  stale      - the cited news predates the review window or repeats what the thesis already knew
  recycled   - the cited items are syndicated copies, opinion or price-target chatter
  priced     - the move since entry already reflects the news
  immaterial - the news cannot plausibly move this stock's next-days return relative to peers
Return JSON only: {"verdict": "confirm"|"reject", "flaw": null|"factual"|"stale"|"recycled"|"priced"|"immaterial",
"note": str <= 40 words}"""
ok_action = lambda o: None if o.get("action") in ("hold", "exit", "reduce", "increase") and (
    o["action"] == "hold" or (isinstance(o.get("evidence"), list) and o["evidence"])) else "bad action"
ok_conf = lambda o: None if o.get("verdict") in ("confirm", "reject") and (
    o["verdict"] == "confirm" or o.get("flaw") in ("factual", "stale", "recycled", "priced", "immaterial")) else "bad verdict"


def news(t):
    arts, lo = {}, since.date()
    for d in pd.date_range(lo, today):
        u = "https://finnhub.io/api/v1/company-news?" + urllib.parse.urlencode(
            {"symbol": t, "from": str(d.date()), "to": str(d.date()), "token": os.environ["FINNHUB_API_KEY"]})
        try:
            with urllib.request.urlopen(u, timeout=30) as r:
                for a in json.load(r):
                    if a.get("datetime", 0) > since.timestamp():
                        arts[str(a.get("id"))] = a
        except Exception as exc:
            print(f"review: news for {t} {d.date()} unavailable ({exc!r})")
        time.sleep(1.05)
    return sorted(arts.values(), key=lambda a: a["datetime"])[-25:]


decisions = {}
for t in sorted([t for t in held if t != "SPY"], key=lambda t: -abs(w_now[t])):
    h = held[t]
    memo = (memos.get(t) or {}).get("memo") or {}
    arts = news(t)
    d = {"weight_now": w_now[t], "n_articles": len(arts), "final": "hold",
         "articles": [{"when": datetime.fromtimestamp(a["datetime"], timezone.utc).isoformat(timespec="minutes"),
                       "source": a.get("source"), "headline": a.get("headline")} for a in arts]}
    if not arts or not memo:
        decisions[t] = d; continue
    listing = "\n".join(f"[{i}] {datetime.fromtimestamp(a['datetime'], timezone.utc):%Y-%m-%d %H:%M} {a.get('source')}: "
                        f"{a.get('headline')} :: {(a.get('summary') or '')[:300]}" for i, a in enumerate(arts))
    user = (f"Stock {t}. Position: {'LONG' if h['qty'] > 0 else 'SHORT'}, {abs(w_now[t]):.1%} of NAV. "
            f"Move since entry: {h['price'] / h['entry'] - 1:+.1%} (price {h['price']:.2f}, entry {h['entry']:.2f}).\n"
            f"THESIS at entry (score {memo.get('score')}, confidence {memo.get('confidence')}): {memo.get('thesis')}\n"
            f"Catalysts: {json.dumps(memo.get('catalysts'))}\nRisks: {json.dumps(memo.get('risks'))}\n\n"
            f"NEWS since {since:%Y-%m-%d %H:%M} UTC:\n{listing}")
    st, out, meta, err = llm(REVIEW, user, ok_action)
    d.update(proposal=out, proposal_status=st, provider=meta.get("provider"), error=err)
    if st == "ok" and out["action"] != "hold":
        if out["action"] == "increase" and (t in increased or np.sign(book_w.get(t, 0)) != np.sign(h["qty"])):
            d["final"] = "hold"; d["why"] = "already increased this week, or not in this week's book"
        else:
            cu = user + f"\n\nPROPOSED: {out['action']} because {out['reason']} (evidence {out['evidence']})"
            st2, c, meta2, err2 = llm(CONFIRM, cu, ok_conf)
            d.update(confirmation=c, confirmation_status=st2)
            d["final"] = out["action"] if st2 == "ok" and c["verdict"] == "confirm" else "hold"
    decisions[t] = d
    print(f"review {t}: {len(arts)} new articles -> {d['final']}" + (f" (proposed {out['action']})" if out else ""), flush=True)

# ---- new targets
acts = [t for t, d in decisions.items() if d["final"] != "hold"][:MAX_ACTIONS]
for t in [t for t, d in decisions.items() if d["final"] != "hold"][MAX_ACTIONS:]:
    decisions[t]["final"], decisions[t]["why"] = "hold", f"over the {MAX_ACTIONS}-actions-a-day limit"
target = dict(w_now)
for t in acts:
    a = decisions[t]["final"]
    target[t] = 0.0 if a == "exit" else w_now[t] * DOWN if a == "reduce" else \
        np.sign(w_now[t]) * min(abs(book_w.get(t, w_now[t])) * UP, NAME_CAP)
stock = {k: v for k, v in target.items() if k != "SPY"}
gross, net = sum(map(abs, stock.values())), sum(stock.values())
net0 = sum(v for k, v in w_now.items() if k != "SPY")
if gross and abs(net) > DOLLAR_CAP * gross + 1e-9 and abs(net) > abs(net0) + 1e-9:   # only if it worsens the imbalance
    for t in [t for t in acts if decisions[t]["final"] == "increase"]:
        target[t] = w_now[t]; decisions[t]["final"], decisions[t]["why"] = "hold", "increase would break the dollar-net cap"
    acts = [t for t in acts if decisions[t]["final"] != "hold"]
if acts:
    target["SPY"] = -sum(v * float(beta.get(k, 1.0)) for k, v in target.items() if k != "SPY")
    if np.sign(target["SPY"]) != np.sign(w_now.get("SPY", target["SPY"])) and w_now.get("SPY"):
        target["SPY"] = 0.0                            # the hedge cannot cross zero in one closing-auction order



def size(prices, held_qty):
    out = []
    for t in (acts + ["SPY"]) if acts else []:
        px = prices.get(t) or held.get(t, {}).get("price")
        cq = int(held_qty.get(t, 0))
        tq = int(round(target.get(t, 0.0) * equity / px)) if px else cq
        if tq != cq:
            out.append({"symbol": t, "leg": f"review-{decisions.get(t, {}).get('final', 'rehedge')}",
                        "side": "buy" if tq > cq else "sell", "qty": abs(tq - cq), "price_ref": px,
                        "client_order_id": f"fund-{asof.date()}-{t}-r{today:%Y%m%d}"})
    return out


problems = []
orders = size(broker.prices(acts + ["SPY"]) if acts else {}, {t: h["qty"] for t, h in held.items()})
if mode == "trade" and orders:
    close_at = close_et.timestamp()
    if broker.STYLE == "preclose":
        print(f"review: waiting until {datetime.fromtimestamp(close_at - broker.PREPARE_AT, ET):%H:%M:%S} ET to size the orders", flush=True)
        clock.sleep_until(close_at - broker.PREPARE_AT)
        orders = size(broker.prices(acts + ["SPY"]), broker.positions())
    broker.send(orders, close_at, clock)
    problems += broker.problems_of(orders)
rec = {"asof": str(asof.date()), "day": str(today), "mode": mode, "close_et": close_et.strftime("%H:%M"), "news_since": str(since), "news_until": now_utc.isoformat(),
       "equity": equity, "decisions": decisions, "weights_before": w_now, "target_weights": target if acts else w_now,
       "orders": orders, "problems": problems,
       "status": ("submitted" if orders else "no_action") if mode == "trade" else "planned"}
json.dump(rec, open(out_p, "w"), indent=1, default=str)
print(f"review {today}: {sum(d['n_articles'] > 0 for d in decisions.values())}/{len(decisions)} names with news, "
      f"actions {[(t, decisions[t]['final']) for t in acts]}, {len(orders)} orders")
if problems:
    raise SystemExit("; ".join(problems))
