"""R5's news controls, measured on exactly the news each R5 forecast saw (PREREG_thesis_tree.md Amendment 9).

    python3 research/p8/r5_news_features.py      -> reports/research/p8/R5_NEWS_FEATURES.csv (one row per R5 record)

Input: the R5 records and their archived prompts on the `research-data` branch (frozen at first use). The news list is
the one in the record's first own-ledger prompt (`ledger0`): at most 60 items, "[i] date source: headline :: summary".
Nothing is fetched again.

* tone = (P - N) / (P + N) over all items' words (headline and summary), where P and N count Loughran-McDonald (2014)
  positive and negative words (research/p8/data/lm_2014_*.txt). 0 when P + N = 0. This is R3's control "the mean news
  tone of the quarter": the news runs from the last release to the cutoff.
* tone_emb = the mean over items of (x - m).w/|w|, where x is the item's L2-normalised google/gemini-embedding-001
  embedding ("headline. summary") and w, m the positive-minus-negative direction and midpoint of Financial PhraseBank's
  all-agree sentences. Used only if the contract (held-out AUC >= 0.90, neutral between the class means) passes;
  written to reports/research/p8/R5_TONE_CONTRACT.json. Embeddings are cached by sha256 of the text (first use).
  Needs OPENROUTER_API_KEY (run through the redacting wrapper).
* quantified = the share of items whose headline contains a digit, "%" or "$" (descriptive).
* n_used = items listed; news_raw = items before deduplication and sampling (from the record) (descriptive).
No price and no outcome is read.
"""
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "reports", "research", "p8", "R5_NEWS_FEATURES.csv")
BR, DIR = "origin/research-data", "fund_state/live/research/r5"
EMB_MODEL = "google/gemini-embedding-001"
EMB_CACHE = os.path.join(ROOT, ".cache", "p8", "emb_gemini001.parquet")
PB = os.path.join(ROOT, ".cache", "p8", "phrasebank", "Sentences_AllAgree.txt")
PB_SHA = "5fb370b3005b9a2759f708849a691ad2e4d2593d4c995c1afde229398a516594"
CONTRACT = os.path.join(ROOT, "reports", "research", "p8", "R5_TONE_CONTRACT.json")
AUC_MIN = 0.90
ITEM = re.compile(r"^\[(\d+)\] (\d{4}-\d{2}-\d{2}) (.*?): (.*?)(?: :: (.*))?$")
WORD = re.compile(r"[a-z]+")


def lexicon():
    load = lambda k: {w.strip() for w in open(os.path.join(HERE, "data", f"lm_2014_{k}.txt")) if w.strip() and not w.startswith("#")}
    return load("positive"), load("negative")


def items(user):
    """The news items of an own-ledger prompt: [(date, source, headline, summary)]."""
    if "\nNEWS (" not in user:
        return []
    body = user.split("\nNEWS (", 1)[1].split("\n", 1)[1] if "\n" in user.split("\nNEWS (", 1)[1] else ""
    out = []
    for line in body.splitlines():
        m = ITEM.match(line.strip())
        if m:
            out.append((m.group(2), m.group(3), m.group(4), m.group(5) or ""))
    return out


def features(its, P, N):
    p = n = 0
    for _, _, h, s in its:
        ws = WORD.findall(f"{h} {s}".lower())
        p += sum(w in P for w in ws)
        n += sum(w in N for w in ws)
    q = sum(bool(re.search(r"[\d%$]", h)) for _, _, h, _ in its)
    return {"tone": (p - n) / (p + n) if p + n else 0.0, "lm_pos": p, "lm_neg": n,
            "quantified": q / len(its) if its else None, "n_used": len(its)}


def sha(t):
    return hashlib.sha256(t.encode()).hexdigest()


def embed(texts):
    """{text: unit vector}; cached by sha256 at first use, never recomputed. Batches of 64, one request at a time."""
    C = pd.read_parquet(EMB_CACHE) if os.path.exists(EMB_CACHE) else pd.DataFrame(columns=["sha", "model", "vec"])
    have = dict(zip(C["sha"], C["vec"]))
    todo = sorted({t for t in texts if sha(t) not in have})
    new, spent = [], 0.0
    for i in range(0, len(todo), 64):
        batch = todo[i:i + 64]
        body = json.dumps({"model": EMB_MODEL, "input": batch}).encode()
        for k in range(4):
            try:
                req = urllib.request.Request("https://openrouter.ai/api/v1/embeddings", data=body, headers={
                    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"})
                d = json.load(urllib.request.urlopen(req, timeout=120))
                vecs = [x["embedding"] for x in sorted(d["data"], key=lambda x: x["index"])]
                assert len(vecs) == len(batch), "embedding count"
                spent += float((d.get("usage") or {}).get("cost") or 0)
                served = d.get("model", EMB_MODEL)
                break
            except Exception as e:                           # transient: wait and retry, then fail loudly
                if k == 3:
                    raise RuntimeError(f"embeddings failed at batch {i // 64}: {e!r}")
                time.sleep(5 * (k + 1))
        new += [{"sha": sha(t), "model": served, "vec": list(map(float, v))} for t, v in zip(batch, vecs)]
        time.sleep(0.5)
    if new:
        C = pd.concat([C, pd.DataFrame(new)], ignore_index=True)
        os.makedirs(os.path.dirname(EMB_CACHE), exist_ok=True)
        C.to_parquet(EMB_CACHE)
        have.update({x["sha"]: x["vec"] for x in new})
        print(f"embedded {len(new)} new texts (${spent:.3f})", flush=True)
    unit = lambda v: (lambda a: a / np.linalg.norm(a))(np.asarray(v, float))
    return {t: unit(have[sha(t)]) for t in texts}


def auc(pos, neg):
    """P(score of a positive > score of a negative), ties half (Mann-Whitney)."""
    x = np.concatenate([pos, neg])
    r = pd.Series(x).rank().to_numpy()
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def direction():
    """The tone direction from PhraseBank (all-agree), with its held-out contract. Returns (w_unit, m, contract)."""
    raw = open(PB, "rb").read()
    assert hashlib.sha256(raw).hexdigest() == PB_SHA, "PhraseBank file changed"
    S = [l.rsplit("@", 1) for l in raw.decode("latin-1").splitlines() if "@" in l]
    S = pd.DataFrame(S, columns=["text", "label"])
    E = embed(list(S["text"]))
    X = np.stack([E[t] for t in S["text"]])
    rng = np.random.default_rng(0)
    half = np.zeros(len(S), bool)
    for lab in ("positive", "negative", "neutral"):                 # stratified 50/50
        idx = np.flatnonzero(S["label"].to_numpy() == lab)
        half[rng.permutation(idx)[: len(idx) // 2]] = True

    def fit(mask):
        mp, mn = X[mask & (S["label"] == "positive").to_numpy()].mean(0), X[mask & (S["label"] == "negative").to_numpy()].mean(0)
        w = mp - mn
        return w / np.linalg.norm(w), (mp + mn) / 2

    w, m = fit(half)
    sc = (X - m) @ w
    test = ~half
    lab = S["label"].to_numpy()
    a = auc(sc[test & (lab == "positive")], sc[test & (lab == "negative")])
    mp_, mn_, mu_ = sc[test & (lab == "positive")].mean(), sc[test & (lab == "negative")].mean(), sc[test & (lab == "neutral")].mean()
    ok = bool(a >= AUC_MIN and mn_ < mu_ < mp_)
    w_all, m_all = fit(np.ones(len(S), bool))
    c = {"model": EMB_MODEL, "phrasebank_sha256": PB_SHA, "n": {k: int((lab == k).sum()) for k in ("positive", "negative", "neutral")},
         "heldout_auc": a, "heldout_means": {"positive": float(mp_), "neutral": float(mu_), "negative": float(mn_)},
         "auc_min": AUC_MIN, "passed": ok}
    json.dump(c, open(CONTRACT, "w"), indent=1)
    print(f"tone contract: held-out AUC {a:.3f}, means pos {mp_:+.3f} / neutral {mu_:+.3f} / neg {mn_:+.3f} -> "
          f"{'PASS' if ok else 'FAIL'}", flush=True)
    return w_all, m_all, c


def git(*a, text=True):
    return subprocess.run(["git", *a], capture_output=True, text=text, cwd=ROOT).stdout


def main():
    git("fetch", "-q", "origin", "research-data")
    P, N = lexicon()
    files = git("ls-tree", "-r", "--name-only", BR, DIR).split()
    rows = []
    for f in sorted(x for x in files if re.search(r"/\d{4}-\d{2}-\d{2}\.json$", x)):
        D = os.path.basename(f)[:-5]
        rec = json.loads(git("show", f"{BR}:{f}"))["records"]
        recs = rec.items() if isinstance(rec, dict) else [(r.get("ticker"), r) for r in rec]
        prompts = {}                                         # ticker -> [(run time HHMMSS, ledger0 user)]
        for pf in sorted(x for x in files if os.path.basename(x).startswith(f"{D}.prompts.")):
            raw = subprocess.run(["git", "show", f"{BR}:{pf}"], capture_output=True, cwd=ROOT).stdout
            hhmmss = pf.rsplit(".prompts.", 1)[1].split(".")[0]
            for line in gzip.open(io.BytesIO(raw), "rt"):
                x = json.loads(line)
                if x.get("task") == "ledger0":
                    prompts.setdefault(x["ticker"], []).append((hhmmss, x["user"]))
        for t, r in recs:
            if r.get("status") != "ok":
                continue
            cand = prompts.get(t, [])
            if not cand:
                rows.append({"report_date": D, "ticker": t, "defect": "no ledger prompt"}); continue
            dec = str(r.get("decided_at") or "")
            dec_hms = re.sub(r"\D", "", dec[11:19]) if len(dec) >= 19 else None
            # the run that produced the record: the latest prompt archive written at or after its decision time
            pick = [c for c in cand if dec_hms is None or c[0] >= dec_hms] or cand
            run, user = sorted(pick)[0] if dec_hms else sorted(cand)[-1]
            its = items(user)
            rows.append({"report_date": D, "ticker": t, "run": run, "news_raw": r.get("news_raw"),
                         "news_used_record": r.get("news_used"), **features(its, P, N),
                         "_texts": [f"{h}. {s_}".strip() for _, _, h, s_ in its]})
    w, m, c = direction()
    allt = sorted({x for r in rows for x in r.get("_texts", [])})
    E = embed(allt) if c["passed"] else {}
    for r in rows:
        ts = r.pop("_texts", [])
        r["tone_emb"] = float(np.mean([(E[x] - m) @ w for x in ts])) if (c["passed"] and ts) else None
    X = pd.DataFrame(rows)
    X.to_csv(OUT, index=False)
    ok = X[X.get("defect").isna()] if "defect" in X else X
    print(f"R5 news features: {len(X)} records, {len(X) - len(ok)} defects; items parsed = record's news_used in "
          f"{int((ok['n_used'] == ok['news_used_record']).sum())}/{len(ok)}")
    return X


if __name__ == "__main__":
    main()
