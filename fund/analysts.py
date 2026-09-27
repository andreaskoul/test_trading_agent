"""Desk 4 · Analysts (PROTOCOL_fund.md). One memo per covered name. -> analysts.json"""

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from common import MOCK, asof_from_env, llm, load, narrative_text, require, save, week_dir

require("OPENROUTER_API_KEY")
asof = asof_from_env()
cutoff = pd.Timestamp.now(tz="UTC").tz_localize(None) if not MOCK else asof + pd.Timedelta(days=1)
S = pd.DataFrame(load(asof, "screen.json")["rows"]).set_index("ticker")
idea = load(asof, "ideation.json")
hyp = {x["ticker"]: (side, x["hypothesis"]) for side in ("long", "short")
       for x in ((idea["llm"] or {}).get(f"{side}_ideas", []))}
cov = idea["coverage"]

SYSTEM = """You are an equity analyst at a long-short fund writing this week's memo on ONE stock.
The book is dollar- and beta-neutral, rebalanced weekly; the question is how this stock will
do NEXT WEEK relative to the other names the fund covers this week.

You get: sector, quantitative signals as z-scores against the S&P 500 (mom12_1 momentum, rev1m /
rev1w reversal, lowvol, high52), a frozen ridge forecast (bp) with its S&P 500 rank, 60-day beta,
last week's return, news attention, the ideation desk's hypothesis if any, and the firm's news
NARRATIVES over the last ~13 weeks: stories with a stable identity (what each is about, its weekly
share of the firm's coverage, whether it is new, rising or fading) with this week's articles under
each as evidence, and the dated events in the window (* = active in the last 7 days, with their
headlines). Read the structure for what is changing; read the articles for direction and specifics.

Rules:
- Use ONLY this material. Ignore anything you believe happened after the as-of date.
- The ridge forecast is the default view. Depart from it only for information the price signals
  cannot see: a story gaining share, a new story, a material dated event (guidance, earnings,
  M&A, litigation, regulation, management), or an important story fading. Opinion pieces,
  price-target chatter, ETF lists and recycled commentary are not information.
- Be specific: name the story or event that drives the view, with its date.

Return JSON only:
{"score": int in {-2,-1,0,1,2}, "confidence": float in [0,1],
 "thesis": str <= 60 words, "catalysts": [{"date": "YYYY-MM-DD or unknown", "what": str <= 15 words}],
 "risks": [str <= 15 words], "drivers": [story or event names used]}"""


def check(o):
    if o.get("score") not in (-2, -1, 0, 1, 2) or not isinstance(o.get("score"), int):
        return f"bad score {o.get('score')!r}"
    c = o.get("confidence")
    return None if isinstance(c, (int, float)) and 0 <= c <= 1 else f"bad confidence {c!r}"


def one(t):
    p = os.path.join(week_dir(asof), "research", f"{t}.json")
    narr = json.load(open(p)) if os.path.exists(p) else None
    r = S.loc[t] if t in S.index else None
    cols = ["GICS Sector", "GICS Sub-Industry", "ridge_bp", "ridge_rank", "mom12_1", "rev1m", "rev1w", "lowvol",
            "high52", "beta60", "ret_1w_pct", "news_7d", "attention_shock"]
    quant = "not an S&P 500 member: no quantitative row" if r is None else r[cols].to_json(double_precision=3)
    user = "\n".join([f"As-of Wednesday close {asof.date()}. Stock: {t} ({r['Security'] if r is not None else t}).",
                      f"Quant: {quant}",
                      f"Ideation hypothesis: {hyp[t][0]} - {hyp[t][1]}" if t in hyp else "Ideation hypothesis: none (covered by rule)",
                      "", narrative_text(narr, cutoff)])
    ms = 0 if r is None else int(max(-2, min(2, round(float(r["ridge_bp"]) / 15))))     # mock: a ridge echo
    status, out, meta, err = llm(SYSTEM, user, {"score": ms, "confidence": 0.5, "thesis": "mock", "catalysts": [],
                                                "risks": [], "drivers": []}, check)
    return t, {"status": status, "error": err, "meta": meta, "memo": out, "has_narratives": narr is not None,
               "prompt_chars": len(user)}


with ThreadPoolExecutor(1 if MOCK else 6) as ex:
    memos = dict(ex.map(one, cov))
save(asof, "analysts.json", {"asof": str(asof.date()), "memos": memos, "system": SYSTEM})
ok = [m for m in memos.values() if m["status"] == "ok"]
print(f"analysts: {len(ok)}/{len(memos)} memos; score counts",
      pd.Series([m["memo"]["score"] for m in ok]).value_counts().sort_index().to_dict())
