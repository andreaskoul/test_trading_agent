"""Weekly LLM selection (PROTOCOL_llm.md, Amendment 2).

    OPENROUTER_API_KEY=... python scripts/llm/select.py --asof YYYY-MM-DD
    python scripts/llm/select.py --asof YYYY-MM-DD --mock      # pipeline test, never counted

Stocks: one call per narrative-dashboard firm (signals + ridge + that firm's
stories with their weekly continuity + this week's events) -> a score in
{-2..+2}; the book is the top/bottom 4 by (score, ridge). FX: one call over
the 17 currencies -> 4 longs / 4 shorts. Quant and seeded random books are
logged alongside. Output: reports/llm_forward/decisions/<asof>.json
(mock runs: reports/llm_forward/mock/).
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL = "deepseek/deepseek-v4.1-flash"
N_BOOK = {"stocks": 4, "fx": 4}

SYSTEM_FIRM = """You assess ONE large US-listed company for a weekly, dollar-neutral long-short book
over a fixed set of about 20 large caps. You get:
- quantitative signals as z-scores against the S&P 500 cross-section (mom12_1: 12-1 month momentum,
  rev1m / rev1w: minus last month's / week's return, lowvol: minus 60-day volatility, high52: price
  relative to the 52-week high), and a frozen ridge forecast of next week's relative return in bp
  with its rank among the S&P 500 and among the ~20 firms;
- the firm's news NARRATIVES as of the cutoff: stories with a stable identity over time, each with
  its weekly article counts and share of the firm's coverage (continuity: is it growing, fading,
  new?), a representative headline per week, and this week's articles; plus dated EVENTS
  (earnings, deals, rulings, launches) from the last 7 days.

Rules:
- Use ONLY this message. Do not use knowledge of prices, events or news after the as-of date;
  if you recognise the period, ignore what you think happened next.
- Your job is to improve on the ridge forecast, not to repeat it. Move away from it only when
  the narratives carry information the price signals cannot see: a story gaining share, a new
  story, a material event (guidance, earnings surprise, M&A, litigation, regulation, management),
  or a story that is fading. Recurring commentary (buy/sell opinions, ETF lists, price-target
  chatter) is not information.
- Output the expected return of this stock NEXT WEEK relative to the other ~20 firms:
  score -2 (strong underperform), -1, 0 (no view beyond the signals), +1, +2 (strong outperform).
- Return JSON only: {"score": int, "confidence": float in [0,1], "reason": str <= 25 words}"""

SYSTEM_FX = """You are a portfolio selector for a weekly, dollar-neutral long-short currency book.
You receive, for 17 currencies against USD, signals as cross-sectional z-scores (carry = interest
differential vs USD, momentum over 12-1 / 3 / 1 months, rev1w = minus last week's return, value =
minus 5-year change) and a frozen ridge forecast of next week's relative excess return in bp with
its rank (1 = best).

Rules:
- Use ONLY this message; ignore any knowledge of what happened after the as-of date.
- Improve on the ridge forecast; deviate only with a reason the signals cannot see.
- Choose exactly {n} longs and exactly {n} shorts, no overlap.
- Return JSON only: {{"longs": [{{"id": str, "reason": str <= 25 words}}, ...],
  "shorts": [{{"id": str, "reason": str <= 25 words}}, ...], "market_view": str <= 40 words}}"""


def firm_prompt(d, r):
    sig = {k: v for k, v in r.items() if k not in ("ticker", "narratives")}
    n = r["narratives"]
    lines = [f"As-of (Wednesday close) {d['asof']}; narratives snapshot {d['narratives_source']['commit_time']} "
             f"(cutoff {d['narratives_source']['cutoff_utc']} UTC).",
             f"Firm: {r['ticker']}. Firms in the book universe: {d['n']}.",
             f"Signals and ridge: {json.dumps(sig)}",
             f"Ridge coefficients, bp per 1 sd: {json.dumps(dict(zip(d['ridge_spec']['features'], [round(c * 1e4, 2) for c in d['ridge_spec']['coef']])))}",
             f"Coverage: {n['n_articles']} articles in the dashboard window, {n['n_relevant']} relevant; latest week {n['window']}.",
             "", "STORIES (most active this week first):"]
    for st in n["stories"]:
        wk = ", ".join(f"{x['week']}: n={x['n']} share={x['share']:.2f}" for x in st["weekly"])
        lines += [f"## {st['name']}{' [NEW]' if st['new'] else ''}: {st['blurb']}",
                  f"   total {st['articles_total']}, this week {st['articles_this_week']}; weekly: {wk}"]
        lines += [f"   {x['week']} headline: {x['headline']} ({x['publisher']})" for x in st["weekly_headline"]]
        lines += [f"   this week [{x['date']}, {x['publisher']}] {x['headline']} :: {x['summary']}" for x in st["this_week"]]
    lines += ["", "EVENTS (last 7 days):"] + ([
        f"- {e['name']} (story: {e['story']}) {e['start']} to {e['end']}, {e['articles']} articles: "
        + " | ".join(f"[{x['date']}, {x['publisher']}] {x['headline']}" for x in e["top"]) for e in n["events"]]
        or ["- none"])
    return "\n".join(lines)


def fx_prompt(d):
    cols = [c for c in d["rows"][0] if c != "ccy"]
    return "\n".join([f"As-of (Wednesday close) {d['asof']}. Universe: {d['universe']}.",
                      f"Ridge coefficients, bp per 1 sd: {json.dumps(dict(zip(d['ridge_spec']['features'], [round(c * 1e4, 2) for c in d['ridge_spec']['coef']])))}",
                      "", "ccy | " + " | ".join(cols)] + [f"{r['ccy']} | " + " | ".join(str(r[c]) for c in cols) for r in d["rows"]])


def call(system, user):
    body = json.dumps({"model": MODEL, "temperature": 0, "response_format": {"type": "json_object"},
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, headers={
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/andreaskoul/test_trading_agent", "X-Title": "llm-selector-forward-test"})
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.load(r)
    txt = resp["choices"][0]["message"]["content"].strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    return json.loads(txt), {"model": resp.get("model"), "usage": resp.get("usage"), "id": resp.get("id")}


def ask(system, user, check, mock_out):
    """Two attempts; returns (status, output, meta, error)."""
    err = None
    for _ in range(2):
        try:
            out, meta = (mock_out, {"model": "mock"}) if args.mock else call(system, user)
            err = check(out)
            if err is None:
                return "ok", out, meta, None
        except Exception as exc:
            err = repr(exc)
        time.sleep(0 if args.mock else 3)
    return "no_decision", None, {}, err


def check_firm(o):
    if not isinstance(o.get("score"), int) or o["score"] not in (-2, -1, 0, 1, 2):
        return f"bad score {o.get('score')!r}"
    c = o.get("confidence")
    return None if isinstance(c, (int, float)) and 0 <= c <= 1 else f"bad confidence {c!r}"


ap = argparse.ArgumentParser()
ap.add_argument("--asof", required=True)
ap.add_argument("--mock", action="store_true")
args = ap.parse_args()
if not args.mock and not os.environ.get("OPENROUTER_API_KEY"):
    raise SystemExit("OPENROUTER_API_KEY is not set. Add it as a repository secret (Settings -> Secrets -> "
                     "Actions) or run with --mock to test the pipeline.")
# A decision must exist before the Thursday close it trades at; a late cron
# never back-fills.
deadline = calendar.timegm(time.strptime(args.asof, "%Y-%m-%d")) + 86400 + 19 * 3600
if not args.mock and time.time() > deadline:
    raise SystemExit(f"too late for asof {args.asof}: decisions must be made before Thursday 19:00 UTC")
IN = os.path.join(ROOT, "reports", "llm_forward", "inputs_mock" if args.mock else "inputs")
out_dir = os.path.join(ROOT, "reports", "llm_forward", "mock" if args.mock else "decisions")
os.makedirs(out_dir, exist_ok=True)
record = {"asof": args.asof, "model": "mock" if args.mock else MODEL, "protocol": "reports/research/PROTOCOL_llm.md (Amendment 2)",
          "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
          "system_sha256": {"firm": hashlib.sha256(SYSTEM_FIRM.encode()).hexdigest(),
                            "fx": hashlib.sha256(SYSTEM_FX.encode()).hexdigest()}}

# ---- stocks: per firm
d = json.load(open(os.path.join(IN, f"{args.asof}_stocks.json")))
record["narratives_source"] = d["narratives_source"]
rows = d["rows"]


def one(r):
    user = firm_prompt(d, r)
    status, out, meta, err = ask(SYSTEM_FIRM, user, check_firm, {"score": 0, "confidence": 0.0, "reason": "mock"})
    return r["ticker"], {"status": status, "error": err, "meta": meta, "out": out,
                         "prompt_sha256": hashlib.sha256(user.encode()).hexdigest(), "prompt_chars": len(user)}


with ThreadPoolExecutor(1 if args.mock else 6) as ex:
    firms = dict(ex.map(one, rows))
ridge = {r["ticker"]: r["ridge_forecast_bp"] for r in rows}
score = {t: (f["out"]["score"] if f["status"] == "ok" else 0) for t, f in firms.items()}
n = N_BOOK["stocks"]
by_llm = sorted(ridge, key=lambda t: (score[t], ridge[t]), reverse=True)
by_quant = sorted(ridge, key=lambda t: ridge[t], reverse=True)
pick = np.random.default_rng(int(args.asof.replace("-", ""))).permutation(sorted(ridge))
record["stocks"] = {"firms": firms, "llm_score": score, "ridge_forecast_bp": ridge,
                    "llm": {"longs": by_llm[:n], "shorts": by_llm[-n:]},
                    "quant": {"longs": by_quant[:n], "shorts": by_quant[-n:]},
                    "random": {"longs": list(pick[:n]), "shorts": list(pick[n:2 * n])},
                    "status": "ok", "n_firm_failures": sum(f["status"] != "ok" for f in firms.values())}
print("stocks:", len(firms), "firms,", record["stocks"]["n_firm_failures"], "failures; scores", score)

# ---- FX: one call
f = json.load(open(os.path.join(IN, f"{args.asof}_fx.json")))
ids = [r["ccy"] for r in f["rows"]]
ranked = sorted(f["rows"], key=lambda r: r["ridge_rank"])
n = N_BOOK["fx"]


def check_fx(o):
    try:
        L = [x["id"] for x in o["longs"]]; S = [x["id"] for x in o["shorts"]]
    except Exception as exc:
        return f"schema: {exc}"
    if len(L) != n or len(S) != n or len(set(L) | set(S)) != 2 * n:
        return f"counts/overlap {len(L)}/{len(S)}"
    bad = (set(L) | set(S)) - set(ids)
    return f"unknown ids {sorted(bad)}" if bad else None


mock_fx = {"longs": [{"id": r["ccy"], "reason": "mock"} for r in ranked[:n]],
           "shorts": [{"id": r["ccy"], "reason": "mock"} for r in ranked[-n:]], "market_view": "mock"}
user = fx_prompt(f)
status, out, meta, err = ask(SYSTEM_FX.format(n=n), user, check_fx, mock_fx)
pick = np.random.default_rng(int(args.asof.replace("-", "")) + 1).permutation(sorted(ids))
record["fx"] = {"status": status, "error": err, "meta": meta, "out": out,
                "prompt_sha256": hashlib.sha256(user.encode()).hexdigest(),
                "llm": {"longs": [x["id"] for x in out["longs"]], "shorts": [x["id"] for x in out["shorts"]]} if status == "ok" else None,
                "quant": {"longs": [r["ccy"] for r in ranked[:n]], "shorts": [r["ccy"] for r in ranked[-n:]]},
                "random": {"longs": list(pick[:n]), "shorts": list(pick[n:2 * n])}}
print("fx:", status, err or "")
json.dump(record, open(os.path.join(out_dir, f"{args.asof}.json"), "w"), indent=1)
