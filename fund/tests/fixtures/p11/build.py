"""How the Protocol 11 fixtures were made (kept for provenance; the tests never run it).

    python fund/tests/fixtures/p11/build.py state            # trimmed copy of the live records on origin/fund-data
    python fund/tests/fixtures/p11/build.py net              # Alpaca closes and calendar (needs the Alpaca keys)
    python fund/tests/fixtures/p11/build.py screen <dryrun>  # the four rows of a real P11 screen dry run

Run on 2026-11-14 from the fund-data commit then on origin. Only fields the rebuild or p11 read are kept.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
OUT = os.path.join(HERE, "rebuild", "live")
TICKERS = ["WMT", "CRM", "TTD", "ECHO", "FOX", "TTWO", "BA", "SPY"]      # the 11-12 entries, ECHO (no history), SPY
NAME_DROP = {"samples", "samples_h", "user", "why", "m_table", "structural_votes"}


def show(path):
    r = subprocess.run(["git", "-C", ROOT, "show", f"origin/fund-data:fund_state/live/{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def ls(path):
    r = subprocess.run(["git", "-C", ROOT, "ls-tree", "--name-only", f"origin/fund-data", f"fund_state/live/{path}"],
                       capture_output=True, text=True)
    return [os.path.basename(x) for x in r.stdout.split()]


def put(rel, obj):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if isinstance(obj, bytes):
        open(p, "wb").write(obj)
    else:
        json.dump(obj, open(p, "w"), indent=0, sort_keys=True)


def state():
    weeks = [w for w in ls("") if w.startswith("20")]
    for w in weeks:
        lj = show(f"{w}/lifecycle.json")
        if lj is None:
            continue
        L = json.loads(lj)
        names = {}
        for t, x in L.get("names", {}).items():
            y = {k: v for k, v in x.items() if k not in NAME_DROP}
            if isinstance(y.get("out"), dict):
                y["out"] = {k: y["out"].get(k) for k in ("event_type", "hard", "driving_event", "structural") if k in y["out"]}
            if isinstance(y.get("inputs"), dict):
                y["inputs"] = {k: v for k, v in y["inputs"].items() if k in ("news_session", "M", "p", "hard")}
            names[t] = y
        put(f"{w}/lifecycle.json", {"status": L["status"], "entry_day": L.get("entry_day"), "names": names, "asof": L.get("asof")})
        book = json.loads(show(f"{w}/book.json"))
        put(f"{w}/book.json", {k: book[k] for k in ("asof", "status", "books", "scores") if k in book})
        S = json.loads(show(f"{w}/screen.json"))
        keep = set(book["books"]["fund"])
        put(f"{w}/screen.json", {"asof": S["asof"], "rows": [{k: r.get(k) for k in ("ticker", "beta_hedge", "beta60", "beta_b1", "GICS Sector") if k in r}
                                                           for r in S["rows"] if r["ticker"] in keep]})
    for f in ls("lifecycle/live/"):
        if f.endswith(".json") and not f.endswith(".plan.json"):
            x = json.loads(show(f"lifecycle/live/{f}"))
            put(f"lifecycle/live/{f}", {k: x[k] for k in ("day", "asof", "status", "actions", "lots_after", "cool", "reviews", "hedge_w", "nav_model") if k in x})
    for f in ls("lifecycle/news/"):
        if f.endswith(".json") and f < "2026-10-15":                      # compute days before Protocol 7 read them
            x = json.loads(show(f"lifecycle/news/{f}"))
            put(f"lifecycle/news/{f}", {"day": x["day"], "close_ts": x["close_ts"],
                                        "lots": {i: {k: v for k, v in k_.items() if k in ("verdict", "news_until", "max_published")}
                                                 for i, k_ in x["lots"].items()}})
    for f in ("returns.csv", "rf_used.csv", "entries.json"):
        put(f"lifecycle/{f}", show(f"lifecycle/{f}"))
    st = json.loads(show("lifecycle/state.json"))
    put("../recorded_nav.json", {"updated": st["updated"], "nav": {r["date"]: r["nav"] for r in st["rows"]},
                                 "lots": sorted(L["id"] for L in st["lots"])})


def net():
    sys.path.insert(0, os.path.join(ROOT, "fund"))
    import broker
    import p11
    import pandas as pd
    s_, cal = broker.api("GET", "/v2/calendar?start=2025-01-01&end=2027-04-30")
    assert s_ == 200
    json.dump([{"date": c["date"], "close": c["close"]} for c in cal], open(os.path.join(HERE, "calendar.json"), "w"), indent=0)
    end = pd.Timestamp("2026-11-11")                                      # the 11-12 entries' information set
    px = p11.alpaca_closes(set(TICKERS), end - pd.Timedelta(days=420), end)
    px.to_csv(os.path.join(HERE, "closes.csv"))


def screen(path):
    x = json.load(open(path))
    keep = [t for t in TICKERS if t in x["rows"]]
    json.dump({**{k: x[k] for k in ("asof", "status", "coverage", "pooled", "defects", "sessions", "written")},
               "rows": {t: x["rows"][t] for t in keep}}, open(os.path.join(HERE, "p11_screen_2026-11-11.json"), "w"), indent=0, sort_keys=True)


if __name__ == "__main__":
    {"state": lambda: state(), "net": lambda: net(), "screen": lambda: screen(sys.argv[2])}[sys.argv[1]]()
