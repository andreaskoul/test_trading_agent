"""Standard account P&L from the broker's own records: FIFO tax lots over every Alpaca fill.

    realized    closing fills only: shares closed x (close price - FIFO cost), signed for shorts
    unrealized  open shares x (mark - FIFO cost of the lots still open), at Alpaca's marks
    cash        dividends, fees and interest (every non-trade, non-transfer activity)
    account P&L = equity - net deposits = realized + unrealized + cash (the reconciliation check)

FIFO is Alpaca's cost-basis method, so open lots' costs match its avg_entry_price. Holding a name
across weeks, or a trim that leaves shares open, realizes nothing on the shares still held.
"""

from collections import defaultdict, deque

TRANSFERS = {"JNLC", "JNLS", "CSD", "CSW", "TRANS", "ACATC", "ACATS"}     # capital in or out, not P&L


def fifo(fills):
    """fills: Alpaca FILL activities, any order. Returns (closing trades, open lots by symbol)."""
    lots, trades = defaultdict(deque), {}
    for f in sorted(fills, key=lambda x: (x["transaction_time"], x["id"])):
        s, px = f["symbol"], float(f["price"])
        q = float(f["qty"]) * (1 if f["side"] == "buy" else -1)
        book = lots[s]
        while q and book and (book[0][0] > 0) != (q > 0):          # closes the oldest opposite lots first
            lq, lpx = book[0][:2]
            n = min(abs(q), abs(lq)) * (1 if lq > 0 else -1)          # shares closed, signed as the lot
            t = trades.setdefault(f["order_id"], {"day": f["transaction_time"][:10], "ticker": s,
                                                  "side": "Long" if lq > 0 else "Short", "shares": 0.0, "cost": 0.0,
                                                  "proceeds": 0.0})
            t["shares"] += n; t["cost"] += n * lpx; t["proceeds"] += n * px
            book[0][0] -= n; q += n
            if abs(book[0][0]) < 1e-9:
                book.popleft()
        if abs(q) > 1e-9:
            book.append([q, px, f["transaction_time"][:10]])
    out = []
    for t in trades.values():
        out.append({**t, "entry_price": t["cost"] / t["shares"], "exit_price": t["proceeds"] / t["shares"],
                    "pnl": t["proceeds"] - t["cost"], "return": (t["proceeds"] / t["cost"] - 1) * (1 if t["side"] == "Long" else -1)})
    return sorted(out, key=lambda t: t["day"]), {s: list(b) for s, b in lots.items() if b}


def standard(fills, other, positions, account):
    """The P&L summary, open positions and realized trades from the broker's raw records."""
    trades, lots = fifo(fills)
    opened = []
    for p in positions:
        s, q, mark = p["symbol"], float(p["qty"]), float(p["current_price"])
        cost = sum(lq * lpx for lq, lpx, _ in lots.get(s, []))
        opened.append({"ticker": s, "side": "Long" if q > 0 else "Short", "shares": q, "avg_cost": cost / q if q else None,
                       "current_price": mark, "market_value": q * mark, "unrealized": q * mark - cost,
                       "return": (mark / (cost / q) - 1) * (1 if q > 0 else -1) if q and cost else None,
                       "broker_avg_cost": float(p["avg_entry_price"]),
                       "since": min((d for *_, d in lots.get(s, [])), default=None)})
    deposits = sum(float(a.get("net_amount") or 0) for a in other if a["activity_type"] in TRANSFERS)
    cash = sum(float(a.get("net_amount") or 0) for a in other if a["activity_type"] not in TRANSFERS)
    # Alpaca's equity is cash + long + short market value; taking the market value from this positions snapshot
    # keeps the equity and the marks from one moment (the account endpoint's equity can lag it by seconds)
    equity = float(account["cash"]) + sum(o["market_value"] for o in opened)
    realized, unrealized = sum(t["pnl"] for t in trades), sum(o["unrealized"] for o in opened)
    return {"summary": {"equity": equity, "deposits": deposits, "account_pnl": equity - deposits,
                        "realized": realized, "unrealized": unrealized, "cash": cash,
                        "unexplained": equity - deposits - realized - unrealized - cash,
                        "method": "FIFO lots over Alpaca fills; marks and equity from the same Alpaca snapshot"},
            "open": opened, "realized_trades": trades,
            "cost_mismatch": [o["ticker"] for o in opened if o["avg_cost"] and abs(o["avg_cost"] - o["broker_avg_cost"]) > 0.01]}


def fetch(broker):
    """Every activity, the open positions and the account, all from Alpaca."""
    acts, tok = [], None
    while True:
        s, r = broker.api("GET", "/v2/account/activities?direction=asc&page_size=100" + (f"&page_token={tok}" if tok else ""))
        assert s == 200, f"activities unavailable: {s} {r}"
        if not r:
            break
        acts += r; tok = r[-1]["id"]
        if len(r) < 100:
            break
    s, pos = broker.api("GET", "/v2/positions")
    assert s == 200, f"positions unavailable: {s} {pos}"
    fills = [a for a in acts if a.get("activity_type") == "FILL"]
    return standard(fills, [a for a in acts if a.get("activity_type") != "FILL"], pos, broker.account())
