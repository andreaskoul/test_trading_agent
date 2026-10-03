"""Shadow desk · macro brief (PROTOCOL_fund.md, Amendment 6). One LLM call. -> macro_brief.json

Reads only context-archive rows fetched before the week's cutoff (Wednesday 22:00 UTC):
* FRED release calendar: releases scheduled in the holding week, and the last 7 days;
* Kalshi US macro markets: the most active open market of each series, with its price change;
* AI-GPR (Caldara-Iacoviello): the latest daily level against its own 1-year distribution
  (level only: the file is revised and published with a lag, so it never times anything);
* GDELT: 7-day news volume and tone per theme against the 7 days before;
* Finnhub general market news of the last 3 days (headlines);
plus this week's FX desk view and the ideation themes. The model returns a fixed schema; the
rendered brief is one text block, identical for every C8 analyst call. Never read by a champion desk.
"""

import json
import os

import numpy as np
import pandas as pd

import infoflow
from common import asof_from_env, llm, load, news_cutoff, require, save, save_prompts, week_dir

require("OPENROUTER_API_KEY", "HF_TOKEN")
asof = asof_from_env()
cutoff = news_cutoff(asof).tz_localize("UTC")
hold_lo, hold_hi = (asof + pd.Timedelta(days=1)).date(), (asof + pd.Timedelta(days=8)).date()
GICS = ["Communication Services", "Consumer Discretionary", "Consumer Staples", "Energy", "Financials", "Health Care",
        "Industrials", "Information Technology", "Materials", "Real Estate", "Utilities"]
C = infoflow.context(cutoff)
by = {s: g for s, g in C.groupby("source")}
P = lambda s: [r for r in by[s]["payload"]] if s in by else []

# ---- FRED calendar: the holding week, and the last 7 days
cal = sorted({(p["date"], p["release"]) for p in P("fred")
              if str(hold_lo) <= p["date"] <= str(hold_hi) or str((cutoff - pd.Timedelta(days=7)).date()) <= p["date"] <= str(cutoff.date())})
cal_ahead = [f"{d} {r}" for d, r in cal if d >= str(hold_lo)]
cal_past = [f"{d} {r}" for d, r in cal if d < str(hold_lo)]

# ---- Kalshi: per series, the open market with the most 24h volume
kal = []
if "kalshi" in by:
    K = pd.DataFrame(P("kalshi"))
    for c_ in ("last_price_dollars", "previous_price_dollars", "volume_24h_fp", "volume_fp"):
        if c_ in K:
            K[c_] = pd.to_numeric(K[c_], errors="coerce")
    K = K[pd.to_datetime(K["close"], utc=True, errors="coerce") > cutoff]
    vol = "volume_24h_fp" if "volume_24h_fp" in K else "volume_fp" if "volume_fp" in K else None
    for s_, g in K.groupby("series"):
        g = g.sort_values(vol, ascending=False) if vol else g
        r = g.iloc[0]
        chg = r["last_price_dollars"] - r["previous_price_dollars"] if pd.notna(r.get("previous_price_dollars")) else np.nan
        kal.append(f"{s_}: {r['title']} -> {r['last_price_dollars'] * 100:.0f}% (1-day change {chg * 100:+.0f} pts)"
                   if pd.notna(r["last_price_dollars"]) else f"{s_}: {r['title']} (no price)")

# ---- AI-GPR daily level vs its own last year (level only)
gpr = "unavailable"
if "gpr" in by:
    G = pd.DataFrame([p for k, p in zip(by["gpr"]["key"], P("gpr")) if k.startswith("ai_gpr_data_daily.csv|")])
    if len(G) and "GPR_AI" in G:
        G["Date"] = pd.to_datetime(G["Date"]); G = G.sort_values("Date")
        G = G[G["Date"] <= cutoff.tz_localize(None)]
        y = G[G["Date"] > G["Date"].max() - pd.Timedelta(days=365)]["GPR_AI"].astype(float)
        last = float(G["GPR_AI"].iloc[-1])
        gpr = f"latest {G['Date'].iloc[-1].date()}: {last:.0f}, {(y < last).mean() * 100:.0f}th percentile of the last year (median {y.median():.0f})"

# ---- GDELT themes: 7-day volume and tone vs the 7 days before
gd = []
if "gdelt" in by:
    D = pd.DataFrame(P("gdelt"))
    D["date"] = pd.to_datetime(D["date"], format="%Y%m%dT%H%M%SZ", utc=True, errors="coerce")
    D = D[D["date"] <= cutoff]
    for th, g in D.groupby("theme"):
        v, t_ = g[g["mode"] == "timelinevol"], g[g["mode"] == "timelinetone"]
        w1 = v[v["date"] > cutoff - pd.Timedelta(days=7)]["value"].astype(float)
        w0 = v[(v["date"] <= cutoff - pd.Timedelta(days=7)) & (v["date"] > cutoff - pd.Timedelta(days=14))]["value"].astype(float)
        tone = t_[t_["date"] > cutoff - pd.Timedelta(days=7)]["value"].astype(float)
        if len(w1):
            gd.append(f"{th}: volume {w1.mean():.3f} vs {w0.mean():.3f} the week before"
                      + (f", tone {tone.mean():+.2f}" if len(tone) else ""))

# ---- market news headlines, last 3 days
mn = []
if "finnhub" in by:
    M = by["finnhub"].assign(pub=pd.to_datetime(by["finnhub"]["published_at"], utc=True, errors="coerce"))
    M = M[(M["pub"] <= cutoff) & (M["pub"] > cutoff - pd.Timedelta(days=3))].sort_values("pub", ascending=False)
    seen = set()
    for pub, p in zip(M["pub"], M["payload"]):
        h = (p.get("headline") or "").strip()
        if h and h.lower() not in seen:
            seen.add(h.lower()); mn.append(f"{pub:%m-%d %H:%M} {p.get('source')}: {h}")
        if len(mn) >= 30:
            break

fx = load(asof, "fx.json") if os.path.exists(os.path.join(week_dir(asof), "fx.json")) else {}
idea = load(asof, "ideation.json")
fx_view = (fx.get("llm") or {}).get("view") or "none"
themes = (idea.get("llm") or {}).get("themes") or []

SYSTEM = f"""You are the macro strategist of a long-short US equity fund. Write the brief every analyst
reads before next week's single-stock calls (holding week {hold_lo} to {hold_hi}). Use ONLY the inputs given;
no outside knowledge, no forecasts of numbers. Be concrete and short.
Return JSON exactly:
{{"calendar": [{{"date": "YYYY-MM-DD", "release": str, "why": str (<= 15 words)}}],   (holding-week releases that matter for equities, <= 8)
 "regime": str (<= 60 words: rates, growth, risk appetite, as the inputs show them),
 "themes": [{{"name": str, "evidence": str (<= 30 words, cite the input), "sectors": [GICS sector names]}}],   (<= 3)
 "fx_view": str (<= 25 words)}}
GICS sectors: {", ".join(GICS)}."""
user = "\n".join([f"Cutoff {cutoff:%Y-%m-%d %H:%M} UTC.", "",
                  "SCHEDULED RELEASES IN THE HOLDING WEEK (FRED):", *(cal_ahead[:40] or ["none listed"]), "",
                  "RELEASES IN THE LAST 7 DAYS:", *(cal_past[:30] or ["none listed"]), "",
                  "PREDICTION MARKETS (Kalshi, most active open market per series):", *(kal or ["unavailable"]), "",
                  f"GEOPOLITICAL RISK (AI-GPR daily, level only): {gpr}", "",
                  "NEWS THEMES (GDELT, share of coverage, 7 days vs the 7 before):", *(gd or ["unavailable"]), "",
                  "MARKET HEADLINES, LAST 3 DAYS:", *(mn or ["unavailable"]), "",
                  f"FX DESK VIEW THIS WEEK: {fx_view}", f"IDEATION THEMES THIS WEEK: {json.dumps(themes)}"])


def check(o):
    if not isinstance(o.get("regime"), str) or not isinstance(o.get("fx_view"), str):
        return "regime / fx_view missing"
    if not isinstance(o.get("calendar"), list) or not isinstance(o.get("themes"), list) or len(o["themes"]) > 3:
        return "calendar / themes malformed"
    for t in o["themes"]:
        if not isinstance(t, dict) or not set(t.get("sectors") or []) <= set(GICS):
            return f"theme sectors must be GICS sector names: {t}"
    return None


status, out, meta, err = llm(SYSTEM, user, check)
save_prompts(asof, "macro", [{"system": SYSTEM, "user": user}])
if status == "ok":
    brief = "\n".join(["MACRO BRIEF (same for every name this week; context, not a view on any stock):",
                       f"Regime: {out['regime']}",
                       "Holding-week calendar: " + ("; ".join(f"{c['date']} {c['release']} ({c.get('why', '')})" for c in out["calendar"][:8]) or "none"),
                       "Themes: " + (" | ".join(f"{t['name']} [{', '.join(t['sectors'])}]: {t['evidence']}" for t in out["themes"]) or "none"),
                       f"FX: {out['fx_view']}"])
else:
    brief = "MACRO BRIEF: unavailable this week."
save(asof, "macro_brief.json", {"asof": str(asof.date()), "cutoff": cutoff.isoformat(), "status": status, "error": err,
                                "meta": meta, "brief": out, "text": brief,
                                "inputs": {"calendar_ahead": len(cal_ahead), "kalshi": len(kal), "gdelt": len(gd), "headlines": len(mn),
                                           "gpr": gpr}})
print(f"macro desk: {status}" + (f" ({err})" if err else ""))
print(brief)
