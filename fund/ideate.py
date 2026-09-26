"""Desk 2 · Ideation (PROTOCOL_fund.md).

The LLM reads one line per S&P 500 member and nominates <= 12 long and <= 12
short ideas with a falsifiable hypothesis. Coverage = dashboard core 20 +
nominations + ridge top/bottom 6 + attention-shock top 6, capped at 45
(nominations first). -> ideation.json
"""

import json
import os
import subprocess

import pandas as pd

from common import MOCK, ROOT, SITE_REPO, asof_from_env, llm, load, require, save

require("OPENROUTER_API_KEY")
asof = asof_from_env()
S = pd.DataFrame(load(asof, "screen.json")["rows"]).set_index("ticker")
CAP, N_IDEAS, N_RULE = 45, 12, 6

site = os.path.join(ROOT, ".cache", "my-website")
if not os.path.isdir(os.path.join(site, ".git")):
    subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", SITE_REPO, site], check=True)
subprocess.run(["git", "-C", site, "fetch", "-q", "origin"], check=True)
core = [f["ticker"] for f in json.loads(subprocess.run(["git", "-C", site, "show", "origin/HEAD:config/firms.json"],
                                                       capture_output=True, text=True, check=True).stdout)["firms"]]

SYSTEM = """You are the head of research at an equity long-short fund. Research time is scarce:
choose which S&P 500 names deserve a full analyst workup THIS week. You see, per stock: sector,
ridge forecast of next-week relative return (bp) and its rank, momentum / reversal / low-vol /
52w-high z-scores, 60-day beta, last week's return, news count over 7 days, attention_shock
(unusual news flow vs its own history and peers), and the two latest headlines.

Pick names where a workup could plausibly change the view: unusual attention, a headline that
suggests a catalyst, or a strong quantitative signal that news might confirm or contradict.
Do not pick names just because they are large. Use only the data given; ignore anything you
think you know about events after the as-of date.

Return JSON only: {"long_ideas": [{"ticker": str, "hypothesis": str <= 30 words}, ... up to 12],
"short_ideas": [...up to 12], "themes": [str <= 15 words, ... up to 5]}"""

cols = ["GICS Sector", "ridge_bp", "ridge_rank", "mom12_1", "rev1m", "rev1w", "lowvol", "high52", "beta60",
        "ret_1w_pct", "news_7d", "attention_shock"]
lines = [f"As-of Wednesday close {asof.date()}. {len(S)} members. Columns: ticker | " + " | ".join(cols) + " | headlines"]
for t, r in S.iterrows():
    vals = [str(r[c]) if isinstance(r[c], str) else ("" if pd.isna(r[c]) else f"{r[c]:.2f}") for c in cols]
    lines.append(f"{t} | " + " | ".join(vals) + " | " + " // ".join(h for h in (r["latest_headlines"] or []) if h)[:240])
user = "\n".join(lines)


def check(o):
    try:
        ids = [x["ticker"] for x in o["long_ideas"]] + [x["ticker"] for x in o["short_ideas"]]
    except Exception as exc:
        return f"schema {exc}"
    bad = [t for t in ids if t not in S.index]
    return f"unknown tickers {bad[:5]}" if bad else None


mock = {"long_ideas": [{"ticker": t, "hypothesis": "mock: top ridge"} for t in S.nsmallest(3, "ridge_rank").index],
        "short_ideas": [{"ticker": t, "hypothesis": "mock: bottom ridge"} for t in S.nlargest(3, "ridge_rank").index],
        "themes": ["mock"]}
status, out, meta, err = llm(SYSTEM, user, mock, check)
noms = ([x["ticker"] for x in out["long_ideas"][:N_IDEAS]] + [x["ticker"] for x in out["short_ideas"][:N_IDEAS]]) if out else []
rule = (list(S.nsmallest(N_RULE, "ridge_rank").index) + list(S.nlargest(N_RULE, "ridge_rank").index)
        + list(S["attention_shock"].dropna().nlargest(N_RULE).index))
coverage = list(dict.fromkeys(core + noms + rule))[:max(CAP, len(core))]
why = {t: [k for k, grp in (("core", core), ("nominated", noms), ("rule", rule)) if t in grp] for t in coverage}
save(asof, "ideation.json", {"asof": str(asof.date()), "status": status, "error": err, "meta": meta, "llm": out,
                              "core": core, "nominated": noms, "rule_based": rule, "coverage": coverage, "why": why,
                              "prompt_chars": len(user)})
print(f"ideation: {status}; {len(noms)} nominated, coverage {len(coverage)} ({len(set(coverage) - set(core))} beyond core)")
