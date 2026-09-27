"""Desk 7 · Investment committee memo (PROTOCOL_fund.md). A record, not a decision:
it is written after book.json exists and cannot change it. -> ic_memo.md"""

import json
import os

import pandas as pd

from common import asof_from_env, llm, load, require, week_dir

require("OPENROUTER_API_KEY")
asof = asof_from_env()
book = load(asof, "book.json")
memos = load(asof, "analysts.json")["memos"]
rt = load(asof, "redteam.json")
idea = load(asof, "ideation.json")
fx = load(asof, "fx.json")
fund = book["books"].get("fund", {})

SYSTEM = """You are the chief investment officer of a long-short fund writing the weekly
investment committee memo. It is a record for the file: plain, specific, no hype. Cover: the
book (longs and shorts with the one-line reason for each, taken from the analysts' theses and
the red team's verdicts), where the red team changed a view and why, the ideation themes,
the risk report (net beta, sector nets), the macro desk's currency book, and what would make
the fund wrong this week. Write in markdown, at most 600 words.
Return JSON only: {"memo_markdown": str}"""
payload = {
    "asof": str(asof.date()), "themes": (idea.get("llm") or {}).get("themes"),
    "book": {t: {"weight": w, "analyst": (memos.get(t, {}).get("memo") or {}).get("thesis"),
                 "score": book["scores"]["fund"].get(t), "red_team": (rt["reviews"].get(t, {}).get("review") or {})}
             for t, w in sorted(fund.items(), key=lambda kv: -kv[1])},
    "risk": book.get("risk", {}).get("fund"), "fx_book": fx.get("books", {}).get("fx"), "fx_view": (fx.get("llm") or {}).get("view"),
}
status, out, meta, err = llm(SYSTEM, json.dumps(payload, indent=1), {"memo_markdown": "# IC memo (mock)\n\n" + json.dumps(payload)[:2000]},
                             lambda o: None if isinstance(o.get("memo_markdown"), str) else "no memo")
text = out["memo_markdown"] if status == "ok" else f"# IC memo unavailable\n\n{err}"
open(os.path.join(week_dir(asof), "ic_memo.md"), "w").write(f"<!-- asof {asof.date()} · {meta.get('model')} -->\n" + text)
print("ic memo:", status)
