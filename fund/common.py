"""Shared plumbing for the fund desks (PROTOCOL_fund.md).

Every desk reads and writes JSON under fund_state/<mode>/<asof>/. FUND_DRYRUN=1 makes
real calls with no deadline and keeps the results out of the live record.
"""

import calendar
import json
import os
import sys
import time
import urllib.error
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DRYRUN = os.environ.get("FUND_DRYRUN") == "1"       # real calls, no deadline, never committed, never scored as live
MODE = "dryrun" if DRYRUN else "live"
# Protocol 7 (PROTOCOL_fund.md): from this session the lifecycle book (fund/lifecycle.py trade) trades the account;
# the weekly execution and the Amendment 5 daily review stop trading.
# FUND_P7_START moves it (a failed gate defers Protocol 7 by a week without a code change).
P7_START = pd.Timestamp(os.environ.get("FUND_P7_START") or "2026-10-15")
MODEL = "deepseek/deepseek-v4.1-flash"
# Serving provider left to OpenRouter's routing (owner's decision, 2026-09-28), so any available
# host serves the model. The provider that answered is logged with every call, and the frozen
# canary measures whether scores drift when the host changes.
PROVIDER = None
SITE_REPO = "https://github.com/andreaskoul/my-website"
SITE_PIN = "2c8723905b7977ccabf335bb2565e69775b06cc3"      # pipeline code pinned for the protocol window
STATE = os.path.join(ROOT, "fund_state")
CALL_LIMIT = 240                                    # seconds per LLM call, all tries of a call <= 3 x this
# What the analyst and red-team desks see about price: facts, not a forecast (Amendment 2).
PRICE_FACTS = ["GICS Sector", "GICS Sub-Industry", "beta60", "vol60_ann_pct", "ret_1w_pct", "ret_1m_pct",
               "ret_12_1_pct", "pct_below_52w_high", "news_7d", "attention_shock", "earnings_in_holding_week"]


def news_cutoff(asof) -> pd.Timestamp:
    """Amendment 4: a fixed cutoff (Wednesday 22:00 UTC) instead of the run's wall clock, so a run can be replayed."""
    return pd.Timestamp(asof) + pd.Timedelta(hours=22)


def save_prompts(asof, desk, rows):
    """Every prompt sent, gzipped next to the desk's output (Amendment 4: decisions are replayable)."""
    import gzip
    with gzip.open(os.path.join(week_dir(asof), f"prompts_{desk}.jsonl.gz"), "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


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
    if missing:
        raise SystemExit(f"missing repository secret(s): {', '.join(missing)} (Settings -> Secrets -> Actions)")


def deadline_ok(asof) -> bool:
    """Decisions must exist before Thursday 19:00 UTC after the as-of Wednesday."""
    return DRYRUN or time.time() < calendar.timegm(pd.Timestamp(asof).timetuple()) + 86400 + 19 * 3600


def llm(system: str, user: str, check=None, tries: int = 3, temperature: float = 0.0):
    """JSON-mode chat call. Returns (status, output, meta, error)."""
    err = None
    for _ in range(tries):
        try:
            body = json.dumps({"model": MODEL, "temperature": temperature,
                               **({"provider": PROVIDER} if PROVIDER else {}),
                               "response_format": {"type": "json_object"},
                               "messages": [{"role": "system", "content": system},
                                            {"role": "user", "content": user}]}).encode()
            req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/andreaskoul/test_trading_agent", "X-Title": "fund-pipeline"})
            # Hard deadline per call. OpenRouter keeps a slow request alive with whitespace, so a
            # socket timeout alone never fires on a hung generation (dry run 5: analysts stalled
            # for 80+ minutes). Read in chunks and give up after CALL_LIMIT seconds.
            t0, buf = time.time(), b""
            with urllib.request.urlopen(req, timeout=90) as r:
                while chunk := r.read1(65536):              # whatever has arrived, not a full block
                    buf += chunk
                    if time.time() - t0 > CALL_LIMIT:
                        raise TimeoutError(f"LLM call exceeded {CALL_LIMIT} s")
            resp = json.loads(buf)
            txt = (resp["choices"][0]["message"].get("content") or "").strip()
            if not txt:                          # reasoning spent the budget: nothing to parse, retry
                raise ValueError("empty content")
            txt = txt.removeprefix("```json").removeprefix("```").removesuffix("```")
            out, meta = json.loads(txt), {"model": resp.get("model"), "provider": resp.get("provider"),
                                          "usage": resp.get("usage"), "raw": txt[:4000]}
            err = check(out) if check else None
            if err is None:
                return "ok", out, meta, None
        except urllib.error.HTTPError as exc:               # keep the provider's reason (e.g. a data-policy 404)
            err = f"HTTP {exc.code}: {exc.read()[:300].decode(errors='replace')}"
        except Exception as exc:
            err = repr(exc)
        time.sleep(3)
    return "failed", None, {}, err


def narrative_text(d: dict | None, cutoff: pd.Timestamp) -> str:
    """Hybrid narrative input (PROTOCOL_fund.md, Amendment 1): structure first, evidence second.

    Structure: every story over the full dashboard window (~13 weeks): weekly share of the
    firm's relevant coverage, rising/fading/new label vs its own 4-week average, and every
    dated event in the window (* = active in the 7 days to the cutoff).
    Evidence: this week's articles under each story (date, publisher, headline, summary cut
    to 200 characters) and the top headlines of this week's events, because direction and
    specifics (downgrades, deal sizes, guidance) mostly live in the text, not the structure."""
    if not d:
        return "NARRATIVES: none available this week (no research output)."
    weeks = d.get("weeks", [])
    names = {s["id"]: s["name"] for s in d.get("stories", [])}
    lo = (cutoff - pd.Timedelta(days=7)).normalize()
    out = [f"NARRATIVE STRUCTURE: {d.get('n_relevant')} relevant articles of {d.get('n_articles')} over {len(weeks)} weeks "
           f"({weeks[0] if weeks else '?'} to {weeks[-1] if weeks else '?'}); latest week {d.get('latest_from')}-{d.get('latest_to')}.",
           "Story share = % of the firm's relevant coverage per week, oldest to newest, weeks: "
           + " ".join(w[5:] for w in weeks), "", "STORIES (most active this week first):"]
    for s in sorted(d.get("stories", []), key=lambda x: -x.get("latest_n", 0)):
        ser = {x["week"]: x for x in s.get("series", [])}
        sh = [ser.get(w, {}).get("share", 0.0) * 100 for w in weeks]
        prev4 = sh[-5:-1] if len(sh) >= 5 else sh[:-1]
        base = sum(prev4) / len(prev4) if prev4 else 0.0
        delta = (sh[-1] if sh else 0.0) - base
        trend = "NEW" if s.get("new") else "rising" if delta > 5 else "fading" if delta < -5 else "stable"
        out += [f"## [{s['id']}] {s['name']} ({trend}; {s.get('n')} articles, {s.get('latest_n')} this week; "
                f"share now {sh[-1] if sh else 0:.0f}% vs 4-week avg {base:.0f}%)",
                f"   about: {s.get('blurb')}",
                "   share by week: " + " ".join(f"{v:.0f}" for v in sh)]
        out += [f"   this week [{x.get('date')}, {x.get('p')}] {x.get('t')} :: {(x.get('d') or '')[:200]}"
                for x in s.get("latest", [])]
    ev = sorted(d.get("events", []), key=lambda e: e["start"])
    out += ["", f"EVENTS in the window ({len(ev)}; * = active in the last 7 days):"]
    for e in ev:
        now = pd.Timestamp(e["end"]) >= lo
        out.append(f"- {'*' if now else ' '} {e['start']} to {e['end']}: {e['name']} (story: {names.get(e.get('story'), 'other')}; "
                   f"{e['n']} articles; weekly: " + ", ".join(f"{k[5:]}={v}" for k, v in sorted(e.get("weeks", {}).items())) + ")")
        if now:
            out += [f"     [{x.get('date')}, {x.get('p')}] {x.get('t')}" for x in e.get("top", [])]
    if not ev:
        out.append("- none")
    return "\n".join(out)
