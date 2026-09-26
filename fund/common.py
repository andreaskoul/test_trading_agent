"""Shared plumbing for the fund desks (PROTOCOL_fund.md).

Every desk reads and writes JSON under fund_state/<asof>/. FUND_MOCK=1 turns
off every paid or keyed call (LLM, Finnhub, embeddings) so the whole
pipeline can be exercised end to end; mock outputs never count.
"""

import calendar
import json
import os
import sys
import time
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
MOCK = os.environ.get("FUND_MOCK") == "1"
DRYRUN = os.environ.get("FUND_DRYRUN") == "1"       # real calls, no deadline, never committed, never scored as live
MODE = "mock" if MOCK else "dryrun" if DRYRUN else "live"
MODEL = "deepseek/deepseek-v4.1-flash"
SITE_REPO = "https://github.com/andreaskoul/my-website"
SITE_PIN = "2c8723905b7977ccabf335bb2565e69775b06cc3"      # pipeline code pinned for the protocol window
STATE = os.path.join(ROOT, "fund_state")


def asof_from_env() -> pd.Timestamp:
    """The Wednesday whose close the week's signals use (FUND_ASOF overrides)."""
    if os.environ.get("FUND_ASOF"):
        a = pd.Timestamp(os.environ["FUND_ASOF"])
    else:
        t = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
        a = t - pd.Timedelta(days=(t.dayofweek - 2) % 7)
    assert a.dayofweek == 2, f"asof {a.date()} is not a Wednesday"
    return a


def week_dir(asof) -> str:
    d = os.path.join(STATE, MODE, str(pd.Timestamp(asof).date()))
    os.makedirs(d, exist_ok=True)
    return d


def load(asof, name):
    return json.load(open(os.path.join(week_dir(asof), name)))


def save(asof, name, obj):
    json.dump(obj, open(os.path.join(week_dir(asof), name), "w"), indent=1, default=str)


def require(*keys):
    missing = [k for k in keys if not os.environ.get(k)]
    if missing and not MOCK:
        raise SystemExit(f"missing repository secret(s): {', '.join(missing)} (Settings -> Secrets -> Actions)")


def deadline_ok(asof) -> bool:
    """Decisions must exist before Thursday 19:00 UTC after the as-of Wednesday."""
    return MOCK or DRYRUN or time.time() < calendar.timegm(pd.Timestamp(asof).timetuple()) + 86400 + 19 * 3600


def llm(system: str, user: str, mock_out: dict, check=None, tries: int = 2):
    """JSON-mode chat call. Returns (status, output, meta, error)."""
    err = None
    for _ in range(tries):
        try:
            if MOCK:
                out, meta = mock_out, {"model": "mock"}
            else:
                body = json.dumps({"model": MODEL, "temperature": 0, "response_format": {"type": "json_object"},
                                   "messages": [{"role": "system", "content": system},
                                                {"role": "user", "content": user}]}).encode()
                req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, headers={
                    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/andreaskoul/test_trading_agent", "X-Title": "fund-pipeline"})
                with urllib.request.urlopen(req, timeout=300) as r:
                    resp = json.load(r)
                txt = resp["choices"][0]["message"]["content"].strip()
                txt = txt.removeprefix("```json").removeprefix("```").removesuffix("```")
                out, meta = json.loads(txt), {"model": resp.get("model"), "usage": resp.get("usage")}
            err = check(out) if check else None
            if err is None:
                return "ok", out, meta, None
        except Exception as exc:
            err = repr(exc)
        time.sleep(0 if MOCK else 3)
    return "failed", None, {}, err


def narrative_text(d: dict | None, cutoff: pd.Timestamp) -> str:
    """The dashboard's per-firm output as prompt text: every story with its
    8-week continuity, weekly headlines and this week's articles; events that
    ended in the 7 days to the cutoff."""
    if not d:
        return "NARRATIVES: none available this week (no research output)."
    names = {s["id"]: s["name"] for s in d.get("stories", [])}
    out = [f"Coverage: {d.get('n_articles')} articles in the window, {d.get('n_relevant')} judged relevant; "
           f"latest week {d.get('latest_from')} to {d.get('latest_to')} (updated {d.get('updated')}).", "", "STORIES:"]
    for s in sorted(d.get("stories", []), key=lambda x: -x.get("latest_n", 0)):
        wk = ", ".join(f"{x['week']}: n={x['n']} share={x['share']:.2f}" for x in s.get("series", [])[-8:])
        out += [f"## {s['name']}{' [NEW]' if s.get('new') else ''}: {s.get('blurb')}",
                f"   total {s.get('n')}, this week {s.get('latest_n')}; weekly: {wk}"]
        out += [f"   {x['week']} headline: {x.get('h')} ({x.get('p')})" for x in s.get("evolution", [])[-4:]]
        out += [f"   this week [{x.get('date')}, {x.get('p')}] {x.get('t')} :: {(x.get('d') or '')[:400]}"
                for x in s.get("latest", [])]
    ev = [e for e in d.get("events", []) if pd.Timestamp(e["end"]) >= (cutoff - pd.Timedelta(days=7)).normalize()]
    out += ["", "EVENTS (last 7 days):"] + ([
        f"- {e['name']} (story: {names.get(e.get('story'))}) {e['start']} to {e['end']}, {e['n']} articles: "
        + " | ".join(f"[{x.get('date')}, {x.get('p')}] {x.get('t')}" for x in e.get("top", [])) for e in ev] or ["- none"])
    return "\n".join(out)
