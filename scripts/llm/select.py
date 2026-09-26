"""Weekly LLM selection (PROTOCOL_llm.md).

    OPENROUTER_API_KEY=... python scripts/llm/select.py --asof YYYY-MM-DD
    python scripts/llm/select.py --asof YYYY-MM-DD --mock      # pipeline test, never counted

Writes reports/llm_forward/decisions/<asof>.json with the LLM, quant and
random books, the prompt hash, the model id and the raw response. Mock runs
go to reports/llm_forward/mock/ instead.
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import time
import urllib.request

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IN = os.path.join(ROOT, "reports", "llm_forward", "inputs")
MODEL = "deepseek/deepseek-v4.1-flash"
N_PICK = {"stocks": 25, "fx": 4}

SYSTEM = """You are a portfolio selector for a weekly, dollar-neutral, long-short book.
You receive, for every asset in a fixed universe, quantitative signals already expressed as
cross-sectional z-scores (higher = more of that characteristic), a frozen ridge forecast of
next week's relative return in basis points (with its rank, 1 = best), and, for stocks, the
headlines published in the past 7 days.

Rules:
- Use ONLY the data in this message. Do not use any knowledge of prices, events or news
  after the as-of date; if you recognise the period, ignore what you think happened next.
- Your job is to improve on the ridge forecast. Keep it where you have no reason to deviate;
  deviate when the headlines contain information the signals cannot see (earnings surprises,
  guidance changes, M&A, litigation, regulatory action, management changes, index events).
- Choose exactly {n} longs and exactly {n} shorts from the universe, no overlap.
- Return JSON only, with this schema:
  {{"longs": [{{"id": str, "score": float in (0,1], "reason": str <= 25 words}}, ...],
    "shorts": [{{"id": str, "score": float in [-1,0), "reason": str <= 25 words}}, ...],
    "market_view": str <= 40 words}}"""


def build_user(universe: str, d: dict) -> str:
    rows = d["rows"]
    key = "ticker" if universe == "stocks" else "ccy"
    cols = [c for c in rows[0] if c not in (key, "headlines")]
    lines = [f"As-of date (Wednesday close): {d['asof']}. Universe: {d['universe']} ({d['n']} assets).",
             f"Ridge features and coefficients (frozen): {json.dumps(dict(zip(d['ridge_spec']['features'], [round(c * 1e4, 2) for c in d['ridge_spec']['coef']])))} bp per 1 sd.",
             "", "id | " + " | ".join(cols)]
    for r in rows:
        lines.append(f"{r[key]} | " + " | ".join(str(r[c]) for c in cols))
    if universe == "stocks":
        lines += ["", "HEADLINES (past 7 days, newest first):"]
        for r in rows:
            for h in r.get("headlines", []):
                lines.append(f"{r[key]} [{h['date']}, {h['publisher']}] {h['title']} :: {h['summary']}")
    return "\n".join(lines)


def validate(out: dict, ids: set, n: int) -> str | None:
    try:
        L = [x["id"] for x in out["longs"]]; S = [x["id"] for x in out["shorts"]]
    except Exception as exc:
        return f"schema: {exc}"
    if len(L) != n or len(S) != n:
        return f"counts {len(L)}/{len(S)} != {n}"
    if len(set(L)) != n or len(set(S)) != n or set(L) & set(S):
        return "duplicates or overlap"
    bad = (set(L) | set(S)) - ids
    return f"unknown ids {sorted(bad)[:5]}" if bad else None


def call_openrouter(system: str, user: str) -> tuple[dict, dict]:
    body = json.dumps({"model": MODEL, "temperature": 0, "response_format": {"type": "json_object"},
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, headers={
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/andreaskoul/test_trading_agent", "X-Title": "llm-selector-forward-test"})
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.load(r)
    txt = resp["choices"][0]["message"]["content"]
    txt = txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    return json.loads(txt), {"model": resp.get("model"), "usage": resp.get("usage"), "id": resp.get("id")}


def mock_llm(d: dict, universe: str, n: int) -> tuple[dict, dict]:
    """Deterministic stand-in: the ridge ranking. Used only to test the pipeline."""
    key = "ticker" if universe == "stocks" else "ccy"
    rows = sorted(d["rows"], key=lambda r: r["ridge_rank"])
    return ({"longs": [{"id": r[key], "score": 0.5, "reason": "mock"} for r in rows[:n]],
             "shorts": [{"id": r[key], "score": -0.5, "reason": "mock"} for r in rows[-n:]],
             "market_view": "mock"}, {"model": "mock"})


ap = argparse.ArgumentParser()
ap.add_argument("--asof", required=True)
ap.add_argument("--mock", action="store_true")
args = ap.parse_args()
if not args.mock and not os.environ.get("OPENROUTER_API_KEY"):
    raise SystemExit("OPENROUTER_API_KEY is not set. Add it as a repository secret (Settings -> Secrets -> "
                     "Actions) or run with --mock to test the pipeline.")
# A decision must exist before the Thursday close it trades at. The Actions
# cron can be delayed; if we are past Thursday 19:00 UTC the week is skipped
# (and logged by the workflow), never back-filled.
deadline = calendar.timegm(time.strptime(args.asof, "%Y-%m-%d")) + 86400 + 19 * 3600
if not args.mock and time.time() > deadline:
    raise SystemExit(f"too late for asof {args.asof}: decisions must be made before Thursday 19:00 UTC")
out_dir = os.path.join(ROOT, "reports", "llm_forward", "mock" if args.mock else "decisions")
os.makedirs(out_dir, exist_ok=True)

record = {"asof": args.asof, "model": "mock" if args.mock else MODEL, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
          "protocol": "reports/research/PROTOCOL_llm.md"}
for universe, n in N_PICK.items():
    d = json.load(open(os.path.join(IN, f"{args.asof}_{universe}.json")))
    key = "ticker" if universe == "stocks" else "ccy"
    ids = {r[key] for r in d["rows"]}
    system, user = SYSTEM.format(n=n), build_user(universe, d)
    entry = {"prompt_sha256": hashlib.sha256((system + "\n" + user).encode()).hexdigest(),
             "system_sha256": hashlib.sha256(system.encode()).hexdigest(), "n_assets": len(ids)}
    status, out, meta, err = "no_decision", None, {}, None
    for attempt in range(2):
        try:
            out, meta = mock_llm(d, universe, n) if args.mock else call_openrouter(system, user)
            err = validate(out, ids, n)
            if err is None:
                status = "ok"; break
        except Exception as exc:
            err = repr(exc)
        time.sleep(3)
    entry.update(status=status, error=err, meta=meta, llm=out)
    ranked = sorted(d["rows"], key=lambda r: r["ridge_rank"])
    entry["quant"] = {"longs": [r[key] for r in ranked[:n]], "shorts": [r[key] for r in ranked[-n:]]}
    rng = np.random.default_rng(int(args.asof.replace("-", "")) + (0 if universe == "stocks" else 1))
    pick = rng.permutation(sorted(ids))
    entry["random"] = {"longs": list(pick[:n]), "shorts": list(pick[n:2 * n])}
    record[universe] = entry
    print(universe, status, err or "", meta.get("usage", ""))
json.dump(record, open(os.path.join(out_dir, f"{args.asof}.json"), "w"), indent=1)
