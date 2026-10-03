"""Shadow desks · C8 informed analysts and C9 ranker (PROTOCOL_fund.md, Amendment 6). -> shadow_info.json

C8: the champion analyst's prompt for each covered name, unchanged (from prompts_analysts.jsonl.gz),
with three blocks added: the shared block first (macro brief, ideation themes, FX view, every covered
name's ideation hypothesis), then the champion prompt, then the name's neighbourhood. System prompt: the
champion's plus one paragraph on the new blocks. Same schema and checks. No red team, so C8 against
the `analyst` book isolates the information. Desk budget 40 minutes, 6 threads.

C9: one call over every C8 memo and the brief, returning a relative order (ties allowed). Its book takes
the champion's caps, hedge and N per side, ordered by the ranker and sized by C8's score x confidence.

A week with more than 25% failed C8 memos is degraded: no C8 or C9 book (the champion's rule).
Never read by a champion desk; never traded.
"""

import gzip
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from common import asof_from_env, llm, load, require, save, save_prompts, week_dir

require("OPENROUTER_API_KEY")
asof = asof_from_env()
wd = week_dir(asof)
A = load(asof, "analysts.json")
idea = load(asof, "ideation.json")
brief = load(asof, "macro_brief.json") if os.path.exists(os.path.join(wd, "macro_brief.json")) else {"text": "MACRO BRIEF: unavailable this week."}
nbh = load(asof, "neighbours.json")["names"] if os.path.exists(os.path.join(wd, "neighbours.json")) else {}
fx = load(asof, "fx.json") if os.path.exists(os.path.join(wd, "fx.json")) else {}
champ = {}
with gzip.open(os.path.join(wd, "prompts_analysts.jsonl.gz"), "rt") as fh:
    for line in fh:
        r = json.loads(line)
        champ[r["ticker"]] = r
cov = [t for t in idea["coverage"] if t in champ]
DEGRADED, BUDGET = 0.25, 40 * 60

hyp = {x["ticker"]: f"{side.upper()}: {x['hypothesis']}" for side in ("long", "short")
       for x in ((idea.get("llm") or {}).get(f"{side}_ideas", []))}
shared = "\n".join([brief["text"], "",
                    f"IDEATION THEMES: {json.dumps((idea.get('llm') or {}).get('themes') or [])}",
                    f"FX DESK VIEW: {(fx.get('llm') or {}).get('view') or 'none'}", "",
                    "IDEATION HYPOTHESES FOR EVERY COVERED NAME (rule-based names have none):",
                    *[f"{t}: {hyp.get(t, 'covered by rule (no hypothesis)')}" for t in cov]])
EXTRA = """

You also get two added blocks. SHARED CONTEXT (first): the week's macro brief, the ideation themes, the
FX view and every covered name's ideation hypothesis; it is the same for every stock, so use it only
where it bears on THIS stock's news (a scheduled release its story depends on, a theme its sector is
exposed to). NEIGHBOURHOOD (last): what the stock's most co-mentioned peers and its sub-industry made
news with this week, and its own 8-K filings. Peer news is evidence only when it plainly transfers
(a customer's order cut, a competitor's recall, an industry ruling); otherwise ignore it."""


def check(o):
    if o.get("score") not in (-2, -1, 0, 1, 2) or not isinstance(o.get("score"), int):
        return f"bad score {o.get('score')!r}"
    c = o.get("confidence")
    return None if isinstance(c, (int, float)) and 0 <= c <= 1 else f"bad confidence {c!r}"


END = time.time() + BUDGET
PROMPTS = []


def c8(t):
    if time.time() > END:
        return t, {"status": "failed", "error": "desk time budget spent", "memo": None, "meta": {}}
    user = "\n".join(["SHARED CONTEXT:", shared, "", "=" * 40, "", champ[t]["user"], "", "=" * 40, "",
                      (nbh.get(t) or {}).get("text", f"NEIGHBOURHOOD of {t}: unavailable this week.")])
    system = champ[t]["system"] + EXTRA
    PROMPTS.append({"ticker": t, "system": system, "user": user})
    st, out, meta, err = llm(system, user, check)
    print(f"C8 {t}: {st}" + (f" score {out['score']}" if out else f" ({err})"), flush=True)
    return t, {"status": st, "error": err, "memo": out, "meta": {k: meta.get(k) for k in ("model", "provider", "usage")}}


with ThreadPoolExecutor(6) as ex:
    memos = dict(ex.map(c8, cov))
save_prompts(asof, "c8", PROMPTS)
ok = {t: m["memo"] for t, m in memos.items() if m["status"] == "ok"}
fail = 1 - len(ok) / max(len(cov), 1)
status = "degraded" if fail > DEGRADED else "ok"

ranking, rk_status, rk_err = None, "skipped", None
views = {t: m for t, m in ok.items() if m["score"] != 0}
if status == "ok" and views:
    RANK = """You are the portfolio manager of a long-short equity fund. Your analysts have written one memo per
stock for next week. Order the stocks with a non-zero view from the strongest long case to the strongest
short case, comparing the memos with each other and with the macro brief: which theses rest on material,
dated, not-yet-priced news, and which on weaker grounds. Ties are allowed. Do not add or drop stocks and do
not change any view's sign: longs stay above every short.
Return JSON only: {"order": [[tickers tied at rank 1], [rank 2], ...], "notes": str <= 80 words}"""
    rusr = "\n".join([brief["text"], "", "MEMOS:"] + [
        f"{t}: score {m['score']}, confidence {m['confidence']}; thesis: {m.get('thesis')}; "
        f"drivers: {json.dumps(m.get('drivers'))}; catalysts: {json.dumps(m.get('catalysts'))}" for t, m in views.items()])

    def rcheck(o):
        flat = [t for grp in o.get("order", []) for t in grp]
        if sorted(flat) != sorted(views):
            return "order must contain every stock with a view exactly once"
        pos = {t: i for i, grp in enumerate(o["order"]) for t in grp}
        longs, shorts = [t for t in views if views[t]["score"] > 0], [t for t in views if views[t]["score"] < 0]
        if longs and shorts and max(pos[t] for t in longs) >= min(pos[t] for t in shorts):
            return "every long must rank above every short"
        return None

    rk_status, ro, rmeta, rk_err = llm(RANK, rusr, rcheck)
    save_prompts(asof, "c9", [{"system": RANK, "user": rusr}])
    if rk_status == "ok":
        ranking = {t: i for i, grp in enumerate(ro["order"]) for t in grp}
save(asof, "shadow_info.json", {"asof": str(asof.date()), "status": status, "failed_share": fail,
                                "c8": memos, "c9": {"status": rk_status, "error": rk_err, "rank": ranking}})
print(f"C8: {len(ok)}/{len(cov)} memos ({status}); C9 ranker: {rk_status}" + (f" ({rk_err})" if rk_err else ""))
