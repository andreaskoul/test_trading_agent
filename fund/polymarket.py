"""Polymarket events for the context archive (fund/context_archive.py). Shadow input: no desk reads it.

Pure functions, so the content contract can be tested on a saved response (fund/tests/test_polymarket.py).
An event is stored when its declared fields say so, never by its title:
* its `volume` is at least MIN_VOLUME dollars;
* none of its tag slugs is in EXCLUDE_TAGS (sports, games, entertainment, short-horizon crypto price markets).
A market of a stored event is a row only if it passes the content contract; otherwise it is an input defect,
counted and not stored (CLAUDE.md rules 1-3). A market the venue has not listed yet (`active` false, no prices, no
volume: a placeholder slot in a multi-candidate event) is neither: it is skipped and counted as unlisted.
"""
import json

MIN_VOLUME = 1_000_000.0
EXCLUDE_TAGS = {"sports", "games", "esports", "pop-culture", "crypto-prices", "tweets-markets", "weather", "hit-price"}
MAX_DEFECT_SHARE = 0.20                                  # above this the response is not what we expect: fail loudly
EVENT_FIELDS = ("id", "slug", "title", "markets")
MARKET_COPY = ("bestBid", "bestAsk", "lastTradePrice", "volumeNum", "volume24hr", "liquidityNum", "closed", "umaResolutionStatus")


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def wanted(event):
    """True if the event's typed fields select it; None if those fields are missing (a defect)."""
    vol = _num(event.get("volume"))
    tags = event.get("tags")
    if vol is None or not isinstance(tags, list):
        return None
    slugs = {t.get("slug") for t in tags if isinstance(t, dict)}
    return vol >= MIN_VOLUME and not (slugs & EXCLUDE_TAGS)


def market_defect(m):
    """None if the market passes the content contract, else the reason."""
    if not m.get("id") or not m.get("question"):
        return "no id or question"
    try:
        outcomes, prices = json.loads(m.get("outcomes") or ""), json.loads(m.get("outcomePrices") or "")
    except (TypeError, ValueError):
        return "outcomes or prices are not JSON lists"
    if not (isinstance(outcomes, list) and isinstance(prices, list) and len(outcomes) == len(prices) >= 2):
        return "outcomes and prices do not match"
    p = [_num(x) for x in prices]
    if any(v is None or not 0.0 <= v <= 1.0 for v in p):
        return "a price is outside [0, 1]"
    if abs(sum(p) - 1.0) > 0.10:
        return "prices do not sum to 1"
    return None


def unlisted(m):
    return m.get("active") is False and not m.get("outcomePrices") and not _num(m.get("volumeNum"))


def market_rows(events):
    """(rows, defects, n_unlisted) for a list of events as served by gamma-api /events.
    rows: (key, published_at, payload) per accepted market; defects: [{"event", "market", "why"}]."""
    rows, defects, skipped = [], [], 0
    for e in events:
        w = wanted(e)
        if w is None or any(not e.get(k) for k in EVENT_FIELDS if k != "markets") or not isinstance(e.get("markets"), list):
            defects.append({"event": str(e.get("id")), "market": None, "why": "event fields missing"})
            continue
        if not w:
            continue
        tags = sorted(t.get("slug") for t in e["tags"] if isinstance(t, dict) and t.get("slug"))
        for m in e["markets"]:
            if unlisted(m):
                skipped += 1
                continue
            why = market_defect(m)
            if why:
                defects.append({"event": str(e["id"]), "market": str(m.get("id")), "why": why})
                continue
            rows.append((f"{e['id']}|{m['id']}", m.get("endDate") or e.get("endDate"), {
                "event_id": str(e["id"]), "event_slug": e["slug"], "event_title": e["title"], "event_volume": _num(e.get("volume")),
                "tags": tags, "question": m["question"], "outcomes": json.loads(m["outcomes"]),
                "prices": [float(x) for x in json.loads(m["outcomePrices"])], "end": m.get("endDate") or e.get("endDate"),
                **{c: m.get(c) for c in MARKET_COPY}}))
    return rows, defects, skipped


def check(rows, defects):
    """Raise when the share of defects says the response is not what the contract expects."""
    n = len(rows) + len(defects)
    if n and len(defects) / n > MAX_DEFECT_SHARE:
        raise RuntimeError(f"polymarket: {len(defects)} of {n} items fail the content contract; first: {defects[:3]}")
