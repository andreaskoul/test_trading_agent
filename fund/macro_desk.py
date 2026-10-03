"""Amendment 6 · Macro desk (shadow; fund/AMENDMENT6_PLAN.md). One LLM call -> macro_brief.json

Turns the context archive (as fetched before the week's cutoff) into one short brief that every C8
analyst reads first. It writes context, never a score: the macro desk takes no positions.

Inputs, all point in time (fetched_at <= Wednesday 22:00 UTC):
  * FRED release calendar: major US releases inside the holding week (Thursday close -> next Thursday close);
  * Kalshi: the nearest open event of each US macro series, mid price now and a week earlier;
  * AI-GPR: daily index, last 7 days vs its past year, spikes; latest monthly country split;
  * GDELT: theme volume and tone over the last days stored (best effort);
  * Finnhub general market news of the 7 days to the cutoff;
  * this week's FX desk view and ideation themes (already produced, so free).
"""

import gzip
import json
import os

import numpy as np
import pandas as pd

from a6_common import GICS, MAJOR, effective_cutoff, latest, load_context
from common import asof_from_env, llm, news_cutoff, require, save, week_dir

require("OPENROUTER_API_KEY")
asof = asof_from_env()
cutoff = effective_cutoff(news_cutoff(asof))       # = news_cutoff in every live run
t0, t1 = (asof + pd.Timedelta(days=1)).date(), (asof + pd.Timedelta(days=8)).date()
C = load_context(asof - pd.Timedelta(days=21), cutoff)
wd = week_dir(asof)
out = []

# ---- calendar: major releases in the holding week
f = latest(C, "fred")
cal = sorted({(p["date"], p["release"]) for p in f["p"] if str(t0) <= p["date"] <= str(t1) and MAJOR.search(p["release"] or "")})
out += ["CALENDAR (major US releases, holding week " + f"{t0} to {t1}):"] + ([f"- {d}: {r}" for d, r in cal] or ["- none found"])

# ---- Kalshi: nearest open event per series, mid now vs a week before the cutoff
k_now, k_wk = latest(C, "kalshi"), latest(C, "kalshi", before=cutoff - pd.Timedelta(days=7))
mid = lambda p: np.nanmean([float(p.get("yes_bid_dollars") or np.nan), float(p.get("yes_ask_dollars") or np.nan)])
wk = {k: mid(p) for k, p in zip(k_wk["key"], k_wk["p"])}
lines = []
for s, g in k_now.assign(series=k_now["p"].map(lambda p: p["series"]), close=k_now["p"].map(lambda p: p.get("close") or "")).groupby("series"):
    g = g[g["close"] >= str(cutoff.date())]
    if g.empty:
        continue
    ev = g.sort_values("close")["p"].iloc[0]["event"]
    rows = [(p["title"] + (f" [{p['sub']}]" if p.get("sub") else ""), mid(p), wk.get(k)) for k, p in zip(g["key"], g["p"]) if p["event"] == ev]
    rows = sorted([r for r in rows if 0.03 <= r[1] <= 0.97], key=lambda r: -r[1])[:6]   # informative strikes only
    lines += [f"- {s} ({ev}): " + "; ".join(f"{t[:110]} {m:.0%}" + (f" (week ago {w:.0%})" if w == w and w is not None else "")
                                             for t, m, w in rows)] if rows else []
out += ["", "PREDICTION MARKETS (Kalshi, probability = mid price):"] + (lines or ["- unavailable"])

# ---- geopolitical risk
g = latest(C, "gpr")
gd = g[g["key"].str.startswith("ai_gpr_data_daily.csv|")]
if len(gd):
    s = pd.Series({pd.Timestamp(p["Date"]): p.get("GPR_AI") for p in gd["p"]}, dtype=float).sort_index().dropna()
    s = s[s.index <= cutoff]
    last7, past = s.iloc[-7:], s[(s.index > s.index[-1] - pd.Timedelta(days=372)) & (s.index <= s.index[-1] - pd.Timedelta(days=7))]
    spikes = [str(d.date()) for d, v in last7.items() if v > past.mean() + 2 * past.std()]
    out += ["", f"GEOPOLITICAL RISK (AI-GPR daily, data through {s.index[-1].date()}): last 7 days mean {last7.mean():.0f} "
                f"vs past-year mean {past.mean():.0f} (sd {past.std():.0f}); spike days: {', '.join(spikes) or 'none'}"]
gc = g[g["key"].str.startswith("ai_gpr_country_monthly.csv|")]
if len(gc):
    m = pd.DataFrame(list(gc["p"])).assign(Date=lambda x: pd.to_datetime(x["Date"])).set_index("Date").sort_index()
    m = m[m.index <= cutoff]
    cols = [c for c in m.columns if c.endswith("_all")]
    if len(m) >= 2 and cols:
        top = m[cols].iloc[-1].sort_values(ascending=False).head(6)
        out.append(f"By country ({m.index[-1]:%Y-%m}, change vs prior month): " + ", ".join(
            f"{c[:-4]} {v:.0f} ({v - m[c].iloc[-2]:+.0f})" for c, v in top.items()))

# ---- GDELT themes (best effort)
gl = latest(C, "gdelt")
if len(gl):
    G = pd.DataFrame(list(gl["p"]))
    G["d"] = pd.to_datetime(G["date"], format="%Y%m%dT%H%M%SZ", errors="coerce")
    G = G[G["d"] <= cutoff]
    lines = []
    for th, x in G.groupby("theme"):
        v, t = x[x["mode"] == "timelinevol"].set_index("d")["value"].sort_index(), x[x["mode"] == "timelinetone"].set_index("d")["value"].sort_index()
        if len(v) >= 2:
            lines.append(f"- {th}: volume last 3 days {v.iloc[-3:].mean():.2f} vs earlier {v.iloc[:-3].mean() if len(v) > 3 else float('nan'):.2f}"
                         + (f", tone {t.iloc[-3:].mean():+.1f}" if len(t) else ""))
    out += ["", "NEWS THEMES (GDELT, share of global coverage; best effort, may be partial):"] + (lines or ["- unavailable"])

# ---- market headlines
n = latest(C, "finnhub")
n = n[(pd.to_datetime(n["published_at"], utc=True, errors="coerce").dt.tz_localize(None) > cutoff - pd.Timedelta(days=7))
      & (pd.to_datetime(n["published_at"], utc=True, errors="coerce").dt.tz_localize(None) <= cutoff)]
hl = sorted({(a[:10], p.get("source"), p.get("headline")) for a, p in zip(n["published_at"], n["p"]) if p.get("headline")}, reverse=True)[:50]
out += ["", "MARKET HEADLINES (7 days to the cutoff, newest first):"] + ([f"- {d} {s}: {h}" for d, s, h in hl] or ["- unavailable"])

# ---- already produced this week
fx = json.load(open(os.path.join(wd, "fx.json"))) if os.path.exists(os.path.join(wd, "fx.json")) else {}
idea = json.load(open(os.path.join(wd, "ideation.json"))) if os.path.exists(os.path.join(wd, "ideation.json")) else {}
fx_view = (fx.get("llm") or {}).get("view") or "unavailable"
themes = (idea.get("llm") or {}).get("themes") or []
out += ["", f"FX DESK VIEW: {fx_view}", "IDEATION THEMES: " + ("; ".join(themes) or "none")]
user = f"As-of Wednesday close {asof.date()}; holding week {t0} to {t1}.\n\n" + "\n".join(out)

SYSTEM = f"""You are the macro strategist of a long-short US equity fund. Every equity analyst reads your
brief before writing this week's single-stock memos. You do not take positions; the book is beta- and
sector-hedged, so what matters is which sectors and kinds of firms the week's macro and geopolitical
news pushes with or against, and which scheduled releases fall inside the holding week.

Use only the material given; ignore anything you think happened after the as-of date. Prediction-market
probabilities and their weekly change are the market's own view: report them, don't second-guess them.
Be specific and plain; no forecasts of the index.

Return JSON only: {{"regime": str <= 60 words, "calendar": [{{"date": "YYYY-MM-DD", "event": str <= 8 words,
"why": str <= 15 words}}] (holding week only), "themes": [{{"name": str <= 6 words, "evidence": str <= 30 words,
"sectors": [GICS sector names from {GICS}], "direction": "tailwind"|"headwind"|"mixed"}}] (at most 4),
"watch": [str <= 15 words] (at most 3)}}"""


def check(o):
    try:
        bad = [s for t in o["themes"] for s in t["sectors"] if s not in GICS]
        assert isinstance(o["regime"], str) and isinstance(o["calendar"], list) and len(o["themes"]) <= 4
    except Exception as exc:
        return f"schema {exc!r}"
    return f"unknown sectors {bad[:3]}" if bad else None


mock = {"regime": "mock", "calendar": [{"date": d, "event": r[:40], "why": "mock"} for d, r in cal[:3]], "themes": [], "watch": []}
status, o, meta, err = llm(SYSTEM, user, mock, check)
brief = None
if status == "ok":
    brief = "\n".join(
        [f"MACRO BRIEF (as-of {asof.date()}; the same for every stock; context, not a view on any stock)",
         f"Regime: {o['regime']}", "Holding week calendar:"]
        + ([f"- {c.get('date')}: {c.get('event')} ({c.get('why')})" for c in o["calendar"]] or ["- no major release"])
        + ["Live themes:"] + ([f"- {t['name']}: {t['direction']} for {', '.join(t['sectors']) or 'no sector'}. {t['evidence']}"
                               for t in o["themes"]] or ["- none"])
        + (["Watch: " + "; ".join(o.get("watch") or [])] if o.get("watch") else [])
        + [f"FX desk view: {fx_view}", "Ideation themes: " + ("; ".join(themes) or "none")])[:3200]
with gzip.open(os.path.join(wd, "prompts_macro.jsonl.gz"), "wt") as fh:
    fh.write(json.dumps({"system": SYSTEM, "user": user}, ensure_ascii=False) + "\n")
save(asof, "macro_brief.json", {"asof": str(asof.date()), "cutoff": str(cutoff), "status": status, "error": err, "meta": meta,
                                "llm": o, "brief": brief, "input_chars": len(user),
                                "context_rows": C.groupby("source").size().to_dict() if len(C) else {}})
print(f"macro desk: {status}; input {len(user)} chars; context rows {C.groupby('source').size().to_dict() if len(C) else {}}")
if brief:
    print(brief)
