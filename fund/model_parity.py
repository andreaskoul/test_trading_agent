"""Model parity test: is a candidate model at least as good as the fund's model on every LLM operation?

Each operation is replayed from the prompts the desks saved (fund-data / research-data branches): the same system and
user text goes to the reference model twice and to the candidate once, with the desks' settings (JSON mode,
temperature 0). Per operation:

  valid       share of answers that parse and carry the operation's required fields
  noise       agreement between the two reference runs: how much the reference agrees with itself
  agreement   agreement between the candidate and the reference (mean over the two reference runs)
  cost, time  OpenRouter's billed cost (usage.include) and wall time per call

Agreement is measured on each operation's decision fields (an analyst's score, a red-team verdict, a kill-check
condition's status, an R5 overall call...), not on free text.

PASS RULE (fixed before the first run): the candidate passes an operation if
  valid(candidate) >= valid(reference) - 0.05   and   agreement >= noise - 0.10.
In words: the candidate is no less reliable, and it differs from the reference by no more than the reference differs
from itself, within a margin for a small sample. Parity is all this can show: whether either model makes better
decisions is a forward question (returns, earnings outcomes), not answerable from a replay.

    python fund/model_parity.py                       # every replayable operation, N prompts each
    python fund/model_parity.py --ops analysts,redteam --n 10 --budget 4
"""

import argparse
import gzip
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF, CAND = "deepseek/deepseek-v4.1-flash", "z-ai/glm-5.3-flash"
OUT_DIR = os.path.join(ROOT, "fund_parity")
REPORT = os.path.join(ROOT, "reports/research/model_parity_glm.md")
VALID_MARGIN, AGREE_MARGIN = 0.05, 0.10


def blob(branch, path):
    b = subprocess.run(["git", "-C", ROOT, "show", f"origin/{branch}:{path}"], capture_output=True).stdout
    return [json.loads(l) for l in gzip.decompress(b).decode().splitlines() if l.strip()] if b else []


def files(branch, pattern):
    out = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "--name-only", f"origin/{branch}"],
                         capture_output=True, text=True).stdout.split()
    return [f for f in out if pattern(f) and "_partial_run" not in f]


# ----------------------------------------------------------------------------- operations
def _int(x):
    return x if isinstance(x, int) and not isinstance(x, bool) else None


def sign(x):
    return None if x is None else (x > 0) - (x < 0)


def a_score(o):
    s = _int(o.get("score"))
    return None if s is None else {"score": s, "sign": sign(s)}


def a_redteam(o):
    v, a = o.get("verdict"), _int(o.get("adjusted_score"))
    return None if v not in ("uphold", "weaken") or a is None else {"verdict": v, "adjusted": a}


def a_card(o):
    e = o.get("event_type")
    return None if not isinstance(e, str) or not isinstance(o.get("kill_conditions"), list) else \
        {"event_type": e, "catalyst_date": o.get("catalyst_date")}


def a_check(o):
    c = o.get("conditions")
    if not isinstance(c, list) or not all(isinstance(x, dict) and x.get("status") in ("matched", "partial", "not") for x in c):
        return None
    h = o.get("hard_news_same_direction") or {}
    return {"statuses": tuple(x["status"] for x in sorted(c, key=lambda x: str(x.get("id")))), "hard": bool(h.get("present"))}


def a_ledger(o):
    ev, ov = o.get("events"), o.get("overall")
    if not isinstance(ev, list) or ov not in ("above", "inline", "below"):
        return None
    new = [e for e in ev if isinstance(e, dict) and e.get("new") and e.get("direction") in (-1, 0, 1) and e.get("size") in (1, 2, 3)]
    s = sum(e["direction"] * e["size"] * (1.5 if e.get("hard") else 1) for e in new) / math.sqrt(1 + len(new))
    return {"overall": ov, "own_sign": sign(round(s, 6))}


def a_peers(o):
    ps = o.get("peers")
    if not isinstance(ps, list) or not ps:
        return None
    return {"peers": tuple(sorted((str(p.get("peer")), p.get("channel"), p.get("direction")) for p in ps if isinstance(p, dict)))}


def a_rank(o):
    order = o.get("order")
    if not isinstance(order, list):
        return None
    r = {}
    for i, grp in enumerate(order):
        for t in (grp if isinstance(grp, list) else [grp]):
            r[str(t)] = i
    return {"rank": r}


def a_macro(o):
    th = o.get("themes")
    if not isinstance(th, list) or not isinstance(o.get("regime"), str):
        return None
    return {"sectors": frozenset(s for t in th if isinstance(t, dict) for s in (t.get("sectors") or []))}


def agree(op, x, y):
    """Agreement in [0, 1] between two answers' decision fields (None = an invalid answer: no agreement)."""
    if x is None or y is None:
        return 0.0
    if op in ("analysts", "c8"):
        return 0.5 * (x["score"] == y["score"]) + 0.5 * (x["sign"] == y["sign"])
    if op == "redteam":
        return 0.5 * (x["verdict"] == y["verdict"]) + 0.5 * (x["adjusted"] == y["adjusted"])
    if op == "lifecycle_card":
        return 0.5 * (x["event_type"] == y["event_type"]) + 0.5 * (x["catalyst_date"] == y["catalyst_date"])
    if op == "lifecycle_check":
        a, b = x["statuses"], y["statuses"]
        per = sum(p == q for p, q in zip(a, b)) / max(len(a), len(b), 1)
        return 0.75 * per + 0.25 * (x["hard"] == y["hard"])
    if op == "r5_ledger":
        return 0.5 * (x["overall"] == y["overall"]) + 0.5 * (x["own_sign"] == y["own_sign"])
    if op == "r5_peers":
        a, b = {p[0]: p[1:] for p in x["peers"]}, {p[0]: p[1:] for p in y["peers"]}
        ks = set(a) | set(b)
        return sum(a.get(k) == b.get(k) for k in ks) / max(1, len(ks))
    if op == "c9":
        ks = sorted(set(x["rank"]) & set(y["rank"]))
        if len(ks) < 3:
            return 0.0
        rx, ry = [x["rank"][k] for k in ks], [y["rank"][k] for k in ks]
        try:
            return max(0.0, statistics.correlation(rx, ry))     # Pearson on ranks (Spearman), floored at 0
        except statistics.StatisticsError:
            return 0.0
    if op == "macro":
        a, b = x["sectors"], y["sectors"]
        return len(a & b) / len(a | b) if a | b else 1.0
    raise KeyError(op)


def week_files(name):
    return files("fund-data", lambda f: f.startswith("fund_state/live/20") and f.endswith(f"/prompts_{name}.jsonl.gz"))


def load_op(op):
    """Saved prompts for an operation: list of {system, user, id}."""
    rows = []
    if op in ("analysts", "redteam", "c8", "c9", "macro"):
        for f in week_files(op):
            rows += [{**r, "id": f"{f.split('/')[2]}|{r.get('ticker', '')}"} for r in blob("fund-data", f)]
    elif op == "lifecycle_card":
        for f in week_files("lifecycle"):
            rows += [{**r, "id": f"{f.split('/')[2]}|{r.get('ticker', '')}"} for r in blob("fund-data", f)]
    elif op == "lifecycle_check":
        for f in files("fund-data", lambda f: "/lifecycle/news/" in f and f.endswith(".prompts.jsonl.gz")):
            rows += [{**r, "id": f"{f.split('/')[-1][:10]}|{r.get('ticker')}|{r.get('pass')}"} for r in blob("fund-data", f)
                     if str(r.get("pass")) in ("0", "1")]
    elif op in ("r5_ledger", "r5_peers"):
        want = ("ledger0", "ledger1") if op == "r5_ledger" else ("peers0",)
        for f in files("research-data", lambda f: "/research/r5/" in f and ".prompts." in f):
            rows += [{**r, "id": f"{f.split('/')[-1][:10]}|{r.get('ticker')}|{r.get('task')}"} for r in blob("research-data", f)
                     if r.get("task") in want]
    return [r for r in rows if r.get("system") and r.get("user")]


OPS = {"analysts": a_score, "redteam": a_redteam, "c8": a_score, "c9": a_rank, "macro": a_macro,
       "lifecycle_card": a_card, "lifecycle_check": a_check, "r5_ledger": a_ledger, "r5_peers": a_peers}
SMALL = {"c9", "macro"}                                     # one prompt a week: take them all


# ----------------------------------------------------------------------------- calls
def call(model, system, user):
    body = {"model": model, "temperature": 0.0, "response_format": {"type": "json_object"}, "usage": {"include": True},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + os.environ["OPENROUTER_" + "API_KEY"],
                                          "Content-Type": "application/json",
                                          "HTTP-Referer": "https://github.com/andreaskoul/test_trading_agent",
                                          "X-Title": "fund-model-parity"})
    t0 = time.time()
    for k in range(3):                                       # like common.llm: up to 3 tries on transport/parse errors
        try:
            r = json.load(urllib.request.urlopen(req, timeout=300))
            txt = (r["choices"][0]["message"].get("content") or "").strip()
            txt = txt.removeprefix("```json").removeprefix("```").removesuffix("```")
            out = json.loads(txt)
            u = r.get("usage") or {}
            return {"out": out, "cost": float(u.get("cost") or 0), "in": u.get("prompt_tokens"), "out_tok": u.get("completion_tokens"),
                    "s": round(time.time() - t0, 1), "provider": r.get("provider"), "tries": k + 1}
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}"
        except Exception as e:
            err = repr(e)[:200]
        time.sleep(3)
    return {"out": None, "cost": 0.0, "error": err, "s": round(time.time() - t0, 1), "tries": 3}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ops", default=",".join(OPS))
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--budget", type=float, default=4.0, help="stop starting new prompts past this spend (USD)")
    ap.add_argument("--seed", type=int, default=20261016)
    a = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    raw_p = os.path.join(OUT_DIR, "parity_raw.jsonl")
    done = {}
    if os.path.exists(raw_p):                                # resumable: keep earlier results
        for l in open(raw_p):
            d = json.loads(l); done[(d["op"], d["id"])] = d
    spent = [sum(d["cost"] for d in done.values())]
    rng = random.Random(a.seed)
    for op in a.ops.split(","):
        rows = load_op(op)
        rng.shuffle(rows)
        pick = rows if op in SMALL else rows[:a.n]
        todo = [r for r in pick if (op, r["id"]) not in done]
        print(f"{op}: {len(rows)} saved prompts, testing {len(pick)} ({len(todo)} new)", flush=True)

        def run(r):
            if spent[0] > a.budget:
                return None
            res = {m: call(mod, r["system"], r["user"]) for m, mod in (("ref1", REF), ("ref2", REF), ("cand", CAND))}
            spent[0] += sum(v["cost"] for v in res.values())
            d = {"op": op, "id": r["id"], "cost": sum(v["cost"] for v in res.values()), **res}
            with open(raw_p, "a") as fh:
                fh.write(json.dumps(d, default=str) + "\n")
            return d

        with ThreadPoolExecutor(4) as px:
            for d in px.map(run, todo):
                if d:
                    done[(op, d["id"])] = d
        print(f"  spent so far ${spent[0]:.3f}", flush=True)
    report(done)


def report(done):
    lines = ["# Model parity: GLM 5.3 flash vs DeepSeek v4.1 flash", "",
             f"Reference `{REF}` (run twice), candidate `{CAND}` (default reasoning), same saved prompts, JSON mode, "
             "temperature 0. Pass rule (fixed before the first run): valid(candidate) >= valid(reference) − "
             f"{VALID_MARGIN} and agreement >= noise − {AGREE_MARGIN}. Parity only: which model decides better is a forward question.", "",
             "| operation | prompts | valid ref | valid cand | noise (ref vs ref) | agreement (cand vs ref) | $/call ref | $/call cand | s/call ref | s/call cand | verdict |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    tot = {"ref": 0.0, "cand": 0.0}
    for op, fn in OPS.items():
        D = [d for (o, _), d in done.items() if o == op]
        if not D:
            continue
        f = lambda d, k: fn(d[k]["out"]) if isinstance(d[k].get("out"), dict) else None
        v_ref = statistics.mean([(f(d, "ref1") is not None) + (f(d, "ref2") is not None) for d in D]) / 2
        v_c = statistics.mean([f(d, "cand") is not None for d in D])
        noise = statistics.mean([agree(op, f(d, "ref1"), f(d, "ref2")) for d in D])
        ag = statistics.mean([(agree(op, f(d, "cand"), f(d, "ref1")) + agree(op, f(d, "cand"), f(d, "ref2"))) / 2 for d in D])
        c_ref = statistics.mean([(d["ref1"]["cost"] + d["ref2"]["cost"]) / 2 for d in D])
        c_c = statistics.mean([d["cand"]["cost"] for d in D])
        s_ref = statistics.mean([(d["ref1"]["s"] + d["ref2"]["s"]) / 2 for d in D])
        s_c = statistics.mean([d["cand"]["s"] for d in D])
        tot["ref"] += c_ref * len(D); tot["cand"] += c_c * len(D)
        ok = v_c >= v_ref - VALID_MARGIN and ag >= noise - AGREE_MARGIN
        lines.append(f"| {op} | {len(D)} | {v_ref:.2f} | {v_c:.2f} | {noise:.2f} | {ag:.2f} | {c_ref:.4f} | {c_c:.4f} | "
                     f"{s_ref:.0f} | {s_c:.0f} | {'**PASS**' if ok else 'FAIL'} |")
    if tot["ref"]:
        lines += ["", f"Cost of the same calls: reference ${tot['ref']:.3f}, candidate ${tot['cand']:.3f} "
                      f"({100 * (1 - tot['cand'] / tot['ref']):.0f}% {'cheaper' if tot['cand'] < tot['ref'] else 'dearer'})."]
    lines += ["", "Not replayable yet (no saved prompts; they need prompt capture first): ideation, IC memo, FX desk, "
                  "shadow challengers C2–C5 and the canary, daily review (action + confirm), R5 card (its saved prompt "
                  "is truncated), and the dashboard pipeline's story naming and summaries (andreaskoul/my-website)."]
    open(REPORT, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
