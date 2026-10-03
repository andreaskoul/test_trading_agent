"""Alpaca access and the pre-close send (PROTOCOL_fund.md, Amendment 3, execution note of 2026-10-03).

Alpaca's paper engine has no closing auction. It fills a market-on-close ("cls") order against
the quote in the last seconds before the close, partially at random, and expires the rest: on
2026-10-01 all 20 of the fund's orders expired, 6 of them partly filled. Orders are therefore sent
as plain market orders just before the close. For large caps that tracks the official close within
a few basis points (closing auction vs 4 pm midquote: median 1.7 bp, Bogousslavsky & Muravyev).

    T-75 s          flip close legs (Alpaca cannot take a position through zero in one order)
    T-60 s          every other order, SPY included; a flip's open leg follows its filled close leg
    T-30 .. T-10 s  every 10 s, an order with no new fill is cancelled and its remainder resent (<= 3 attempts)
    T-10 s          nothing new is sent (a day order after the close would wait for the next session)
    T+5 s           whatever is still open is cancelled; the residual is logged, never carried

T is the session close from Alpaca's clock, corrected for this machine's clock offset. Each attempt
has client order id <base>-a<n>, so a rerun adopts what an earlier run already sent. With
FUND_EXEC_STYLE=cls, real market-on-close orders are sent instead (a live account with auction routing).
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BASE = os.environ.get("ALPACA_BASE", "https://paper-api.alpaca.markets")
DATA = os.environ.get("ALPACA_DATA", "https://data.alpaca.markets")
if "paper" not in BASE and os.environ.get("FUND_LIVE_TRADING") != "1":
    raise SystemExit("refusing a non-paper Alpaca endpoint without FUND_LIVE_TRADING=1")
H = {"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"], "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"],
     "Content-Type": "application/json"}
ET = ZoneInfo("America/New_York")
STYLE = os.environ.get("FUND_EXEC_STYLE", "preclose")
assert STYLE in ("preclose", "cls"), f"FUND_EXEC_STYLE={STYLE!r}"
FLIP_AT, SEND_AT, RETRY_FROM, LAST_SEND, SWEEP_AFTER = 75, 60, 30, 10, 5      # seconds around the close
PREPARE_AT = 150                                    # orders are sized from prices fetched at T-150 s
RETRY_EVERY, MAX_ATTEMPTS, POLL = 10, 3, 2
CLS_CUTOFF = 15 * 60                                # market-on-close orders are refused from 15:50 ET
OPEN = ("new", "accepted", "pending_new", "partially_filled", "held", "accepted_for_bidding", "pending_replace",
        "pending_cancel", "calculated")


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
            except ValueError:
                return e.code, {"message": txt.decode(errors="replace")}
        except Exception as exc:
            if attempt == 3:
                return 0, {"message": repr(exc)}
            time.sleep(2 ** attempt * 2)


def ts(s):
    """Alpaca timestamps carry up to 9 fractional digits; Python parses at most 6."""
    return datetime.fromisoformat(re.sub(r"(\.\d{6})\d+", r"\1", s.replace("Z", "+00:00")))


class Clock:
    """Alpaca's market clock; now() is this machine's time corrected to the broker's."""

    def __init__(self):
        s, c = api("GET", "/v2/clock")
        assert s == 200 and c, f"clock unavailable: {s} {c}"
        self.offset = ts(c["timestamp"]).timestamp() - time.time()
        self.is_open = bool(c["is_open"])
        self.next_close = ts(c["next_close"])
        if abs(self.offset) > 2:
            print(f"clock: this machine is {-self.offset:+.1f} s off the broker; corrected", flush=True)

    def now(self):
        return time.time() + self.offset

    def sleep_until(self, t):
        while (d := t - self.now()) > 0:
            time.sleep(min(d, 30))


def account():
    s, a = api("GET", "/v2/account")
    assert s == 200, f"account unavailable: {s} {a}"
    if a.get("trading_blocked") or a.get("account_blocked"):
        raise SystemExit("Alpaca account is blocked")
    return a


def positions():
    """Signed share counts by symbol."""
    s, pos = api("GET", "/v2/positions")
    assert s == 200, f"positions unavailable: {s} {pos}"
    return {p["symbol"]: (-1 if p["side"] == "short" else 1) * abs(float(p["qty"])) for p in pos}


def prices(symbols):
    """Latest trade (IEX), else today's or the previous daily close."""
    out, symbols = {}, sorted(set(symbols))
    for i in range(0, len(symbols), 100):
        s, snap = api("GET", "/v2/stocks/snapshots?feed=iex&symbols=" + ",".join(symbols[i:i + 100]), base=DATA)
        for k, v in (snap or {}).items():
            for f in ("latestTrade", "dailyBar", "prevDailyBar"):
                px = ((v or {}).get(f) or {}).get("p" if f == "latestTrade" else "c")
                if px:
                    out[k] = float(px); break
    return out


def fills(ids):
    """Total filled quantity, volume-weighted fill price and last fill time over a set of broker order ids."""
    q = v = 0.0; last = None
    for i in ids:
        s, x = api("GET", f"/v2/orders/{i}")
        if s != 200 or not x:
            continue
        fq = float(x.get("filled_qty") or 0)
        q += fq; v += fq * float(x.get("filled_avg_price") or 0)
        last = max(filter(None, [last, x.get("filled_at")]), default=None)
    return q, (v / q if q else None), last


def fill_status(qty, filled_qty, sent):
    return "filled" if filled_qty >= qty else "partial" if filled_qty > 0 else "unfilled" if sent else "not_sent"


def send(orders, close_at, clock, log=print):
    """Send a day's orders around the close and wait for the outcome.

    orders: dicts with symbol, leg (flatten | open | anything else), side, qty and client_order_id (the base id).
    close_at: the session close (epoch seconds). Each order gets ids, id (the last attempt), attempts,
    filled_qty, fill_price and status (filled | partial | unfilled | not_sent | skipped: ...).
    """
    for o in orders:
        o.setdefault("attempts", [])
    since = datetime.fromtimestamp(close_at - 16 * 3600, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seen = {}                                       # client order id -> latest broker state

    def refresh():
        s, xs = api("GET", f"/v2/orders?status=all&limit=500&direction=asc&after={since}")
        for x in xs if s == 200 and isinstance(xs, list) else []:
            seen[x["client_order_id"]] = x

    def sent(o):
        return [seen[c] for c in o["attempts"] if c in seen]

    def filled(o):
        return sum(float(x.get("filled_qty") or 0) for x in sent(o))

    def live(o):
        return [x for x in sent(o) if x["status"] in OPEN]

    def submit(o, tif):
        n = len(o["attempts"]) + 1
        rem = int(round(o["qty"] - filled(o)))
        if n > MAX_ATTEMPTS or rem <= 0:
            return
        cid = f"{o['client_order_id']}-a{n}"
        s, r = api("POST", "/v2/orders", {"symbol": o["symbol"], "qty": str(rem), "side": o["side"], "type": "market",
                                         "time_in_force": tif, "client_order_id": cid})
        if s == 422 and "client_order_id" in json.dumps(r or {}):          # an earlier run sent it: adopt
            s, r = api("GET", f"/v2/orders:by_client_order_id?client_order_id={cid}")
        o["attempts"].append(cid)
        if s in (200, 201) and r:
            seen[cid] = r
            log(f"  sent {o['side']:4s} {rem:>6d} {o['symbol']:6s} {o['leg']} ({cid})")
        else:
            o.setdefault("errors", []).append(f"{cid}: {(r or {}).get('message') or s}")
            log(f"  REJECTED {o['symbol']} {o['leg']}: {o['errors'][-1]}")

    refresh()
    for o in orders:                                # adopt every attempt an earlier run of this plan sent
        for n in range(1, MAX_ATTEMPTS + 1):
            cid = f"{o['client_order_id']}-a{n}"
            if cid in seen and cid not in o["attempts"]:
                o["attempts"].append(cid)
    first = [o for o in orders if o["leg"] == "flatten"]
    opens = [o for o in orders if o["leg"] == "open"]
    rest = [o for o in orders if o["leg"] not in ("flatten", "open")]
    leg_of = {o["symbol"]: o for o in first}

    if STYLE == "cls":                              # live account with auction routing: one MOC order per name
        for o in first:
            if not o["attempts"]:
                submit(o, "day")
        for o in rest:
            if not o["attempts"]:
                submit(o, "cls")
        deadline = min(close_at - CLS_CUTOFF, clock.now() + 120)
        while opens and clock.now() < deadline:
            time.sleep(POLL); refresh()
            for o in opens:
                if not o["attempts"] and filled(leg_of[o["symbol"]]) >= leg_of[o["symbol"]]["qty"]:
                    submit(o, "cls")
        clock.sleep_until(close_at + 120)
    else:
        clock.sleep_until(close_at - FLIP_AT)
        for o in first:
            if not o["attempts"]:
                submit(o, "day")
        clock.sleep_until(close_at - SEND_AT)
        for o in rest:
            if not o["attempts"]:
                submit(o, "day")
        progress = {id(o): (filled(o), clock.now()) for o in orders}
        while clock.now() < close_at - LAST_SEND:
            time.sleep(POLL); refresh()
            for o in opens:
                if not o["attempts"] and filled(leg_of[o["symbol"]]) >= leg_of[o["symbol"]]["qty"]:
                    submit(o, "day"); progress[id(o)] = (0.0, clock.now())
            if close_at - clock.now() > RETRY_FROM:
                continue
            for o in first + rest + opens:
                f, since_t = progress[id(o)]
                if filled(o) > f:
                    progress[id(o)] = (filled(o), clock.now()); continue
                if filled(o) >= o["qty"] or not o["attempts"] or len(o["attempts"]) >= MAX_ATTEMPTS:
                    continue
                if clock.now() - since_t < RETRY_EVERY:
                    continue
                for x in live(o):                   # stalled: cancel, wait for the cancel, resend the remainder
                    api("DELETE", f"/v2/orders/{x['id']}")
                for _ in range(10):
                    time.sleep(0.5); refresh()
                    if not live(o):
                        break
                if not live(o) and clock.now() < close_at - LAST_SEND:
                    submit(o, "day")
                progress[id(o)] = (filled(o), clock.now())
        clock.sleep_until(close_at + SWEEP_AFTER)
        refresh()
        for o in orders:                            # the residual is cancelled, never carried
            for x in live(o):
                api("DELETE", f"/v2/orders/{x['id']}")
        time.sleep(3)
    refresh()
    for o in orders:
        xs = sent(o)
        fq = filled(o)
        o["ids"] = [x["id"] for x in xs]
        o["id"] = o["ids"][-1] if o["ids"] else None
        o["filled_qty"] = fq
        o["fill_price"] = (sum(float(x.get("filled_qty") or 0) * float(x.get("filled_avg_price") or 0) for x in xs) / fq
                           if fq else None)
        if o["leg"] == "open" and not o["attempts"]:
            o["status"] = "skipped: flatten leg not filled"
        else:
            o["status"] = fill_status(o["qty"], fq, bool(xs))
    return orders


def problems_of(orders):
    return [f"{o['symbol']} {o['leg']}: {o['status']} ({o['filled_qty']:g}/{o['qty']} filled)"
            for o in orders if o["status"] != "filled"]
