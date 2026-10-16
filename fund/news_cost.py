"""News desk · Phase 0 cost probe report. Reads what `news_ingest.py --probe` fetched (fund_news_probe/) and
measures, per source and per channel/show, what each would cost the desk per day:

  raw tokens        everything fetched (title + summary, or the whole transcript)
  prefiltered       only items/segments that name a universe firm (S&P 500 + 400) or a sector/theme keyword
  map input         what the tagging LLM would read: prefiltered text items, and transcript windows of
                    +-WINDOW_S seconds around each hit (merged), plus the prompt overhead per call
  ledger input      upper bound: every firm named gets the 3-pass ledger (card + its items), as if it had a card
  $                 tokens x the live OpenRouter price of the fund's model (common.MODEL), input and output

Tokens are counted with tiktoken cl100k_base and rescaled by the calibration sample (--calibrate sends ~20 real
tagging calls per source kind through common.llm and compares the provider's usage with the proxy).

    python fund/news_cost.py                     # report from the probe files
    python fund/news_cost.py --calibrate         # + calibration calls (needs OPENROUTER_API_KEY)
"""

import argparse
import glob
import gzip
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MODEL, ROOT, llm   # noqa: E402

PROBE = os.path.join(ROOT, "fund_news_probe")
OUT_MD = os.path.join(ROOT, "reports/research/news_desk_cost_probe.md")
WINDOW_DAYS, WINDOW_S = 2.0, 90
BATCH_TEXT, CALL_OVERHEAD, OUT_PER_UNIT = 10, 700, 90      # clusters per tagging call; system prompt + framing tokens
CARD_TOK, LEDGER_FRAME, PASSES = 600, 450, 3
# ledger pass output per firm, reasoning on / off: from the calibration (transcript-window calls ~2,000-2,600 output
# tokens with reasoning) and the reasoning-off side test (842 vs 7,662 output tokens on the same 10 items = 0.11)
LEDGER_OUT_ON, REASONING_OFF_OUT = 2300, 0.11
SUFFIX = r"\b(incorporated|inc|corporation|corp|company|co|holdings?|group|plc|ltd|limited|the|class [a-z]|n\.?v|s\.?a)\b\.?"
# names whose first word alone is safe to match (probe aliases; the desk's frozen alias file replaces this)
ALIASES = {"GOOGL": ["google", "alphabet", "youtube", "waymo"], "META": ["facebook", "instagram", "whatsapp", "meta platforms"],
           "JPM": ["jpmorgan", "jp morgan"], "BRK.B": ["berkshire"], "GS": ["goldman sachs"], "MS": ["morgan stanley"],
           "BAC": ["bank of america"], "WFC": ["wells fargo"], "C": ["citigroup", "citibank"], "AMZN": ["amazon", "aws"],
           "MSFT": ["microsoft", "azure"], "AAPL": ["apple inc", "iphone"], "NVDA": ["nvidia"], "TSLA": ["tesla"],
           "AMD": ["advanced micro devices"], "INTC": ["intel"], "AVGO": ["broadcom"], "UNH": ["unitedhealth"],
           "XOM": ["exxon"], "CVX": ["chevron"], "KO": ["coca-cola", "coca cola"], "PEP": ["pepsico", "pepsi"],
           "WMT": ["walmart"], "COST": ["costco"], "HD": ["home depot"], "BA": ["boeing"], "LMT": ["lockheed"],
           "RTX": ["raytheon"], "GE": ["ge aerospace"], "DIS": ["disney"], "NFLX": ["netflix"], "ORCL": ["oracle"],
           "CRM": ["salesforce"], "PLTR": ["palantir"], "MU": ["micron"], "QCOM": ["qualcomm"], "TXN": ["texas instruments"],
           "LLY": ["eli lilly", "lilly"], "PFE": ["pfizer"], "MRK": ["merck"], "JNJ": ["johnson & johnson"], "ABBV": ["abbvie"],
           "UPS": ["ups"], "FDX": ["fedex"], "F": ["ford motor", "ford"], "GM": ["general motors"], "CAT": ["caterpillar"]}
COMMON_EXTRA = {"nasdaq", "visa", "southern", "progressive", "equity", "regions", "match", "carrier", "united", "general"}
COMPANY_WORDS = r"(inc|corp|corporation|co|company|holdings|group|stores|brands|plc|ltd|shares|stock)\b"
THEMES = ["tariff", "export control", "sanction", "supply chain", "shortage", "strike", "layoff", "data center", "data centre",
          "semiconductor", "chipmaker", "chips", "oil price", "crude", "natural gas", "opec", "lng", "refiner", "airline",
          "homebuilder", "mortgage rate", "housing starts", "freight", "trucking", "shipping rates", "defense contract",
          "pentagon", "fda approv", "recall", "drug pricing", "medicare", "utility", "power grid", "electricity demand",
          "nuclear", "copper", "steel", "aluminum", "lithium", "ev sales", "electric vehicle", "auto sales", "consumer spending",
          "retail sales", "same-store", "ad spending", "cloud spending", "capex", "ai spending", "interest rate", "fed "]
TAG = """DRAFT (Phase 0 calibration). You map news onto listed US companies. For each numbered item, return the S&P 500/400
companies it concerns (ticker, role: subject|mentioned|competitor|customer|supplier), the GICS sub-industries it bears on,
the event type (earnings, guidance, product_launch, partnership, legal_regulatory, leadership, mna_rumour, macro_readthrough,
tariff, export_control, sanctions, conflict, energy, other), direction for the subject (-1|0|1), size 1-3, and hard (bool).
Ignore stock-price moves and analyst ratings. Return JSON only: {"items": [{"n": int, "entities": [{"ticker": str, "role": str}],
"sub_industries": [str], "event_type": str, "direction": -1|0|1, "size": 1|2|3, "hard": bool}]}"""


def tok_fn():
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    return lambda s: len(enc.encode(s, disallowed_special=())) if s else 0


def matchers():
    u = pd.concat([pd.read_csv(os.path.join(ROOT, f"data/raw/stocks/{f}.csv")) for f in ("sp500_current", "sp400_current")])
    u = u.drop_duplicates("Symbol")
    pats = {}
    words = set()
    if os.path.exists("/usr/share/dict/words"):
        words = {w.strip() for w in open("/usr/share/dict/words") if w.strip().islower()}
    words |= COMMON_EXTRA
    for t, name in zip(u.Symbol, u.Security):
        core = re.sub(r"\s+", " ", re.sub(SUFFIX, "", re.sub(r"\(.*?\)|[,.]", " ", str(name).lower()))).strip()
        if core in words or (len(core.split()) == 1 and len(core) < 4):
            # a name that is an everyday word ("target", "post", "gap", "news"): only with a company suffix
            alts = [rf"\b{re.escape(core)}\s+{COMPANY_WORDS}"]
        else:
            alts = [re.escape(core)] if len(core) >= 5 else ([rf"\b{re.escape(core)}\b"] if core else [])
        alts += [rf"\b{re.escape(a)}\b" for a in ALIASES.get(t, [])]
        if alts:
            pats[t] = re.compile(r"(?<![a-z])(" + "|".join(alts) + r")(?![a-z])")
    sym = set(u.Symbol)
    tick = re.compile(r"\$([A-Z]{1,5}(?:\.[A-Z])?)\b|\((?:NYSE|NASDAQ|Nasdaq|NYSEAMERICAN|AMEX)\s*:\s*([A-Z.]{1,6})\)")
    theme = re.compile("|".join(re.escape(x) for x in THEMES))

    def firms(text, src_tags=()):
        lo = text.lower()
        out = {t for t, p in pats.items() if p.search(lo)}
        out |= {a or b for a, b in tick.findall(text) if (a or b) in sym}
        out |= {t for t in src_tags if t in sym}
        return out
    return firms, (lambda text: bool(theme.search(text.lower())))


def windows(segs, hit_idx):
    """Merge +-WINDOW_S around each hit segment; returns lists of segment indices."""
    spans = sorted((max(0, segs[i][0] - WINDOW_S), segs[i][0] + segs[i][1] + WINDOW_S) for i in hit_idx)
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [[i for i, s in enumerate(segs) if a <= s[0] <= b] for a, b in merged]


def price():
    try:
        d = json.load(urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=60))
        m = next(x for x in d["data"] if x["id"] == MODEL)
        return float(m["pricing"]["prompt"]), float(m["pricing"]["completion"]), "openrouter /api/v1/models"
    except Exception as exc:
        print(f"price lookup failed ({exc!r}); using placeholders", flush=True)
        return 0.1e-6, 0.4e-6, "placeholder (lookup failed)"


def load():
    fs = sorted(glob.glob(os.path.join(PROBE, "items_*.parquet")))
    X = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    X = X.drop_duplicates(["source", "key"], keep="last").reset_index(drop=True)
    man = {}
    for f in glob.glob(os.path.join(PROBE, "manifest_*.json")):
        man.update(json.load(open(f))["status"])
    return X, man


def measure(X, firms_of, themed, ntok):
    """One row per item with token counts and hits; transcripts are windowed."""
    rows, units = [], []
    for r in X.itertuples():
        tags = list(r.tickers_src) if getattr(r, "tickers_src", None) is not None else []
        if r.source in ("youtube", "podcast"):
            segs = []
            if isinstance(r.text_path, str) and r.text_path:
                segs = json.load(gzip.open(os.path.join(PROBE, r.text_path), "rt"))["segments"]
            full = " ".join(s[2] for s in segs)
            hit_i, fset = [], set()
            for i, s in enumerate(segs):
                ctx = " ".join(x[2] for x in segs[max(0, i - 1):i + 2])  # names split across caption lines
                f = firms_of(ctx)
                if f or themed(s[2]):
                    hit_i.append(i); fset |= f
            fset |= firms_of(r.title or "")
            ws = windows(segs, hit_i) if hit_i else []
            wtxt = [" ".join(segs[i][2] for i in w) for w in ws]
            raw, pre = ntok(full), sum(ntok(w) for w in wtxt)
            aud = getattr(r, "audio_s", None)
            cov = aud if aud == aud and aud else (segs[-1][0] + segs[-1][1] if segs else 0.0)
            rows.append(dict(idx=r.Index, raw_tok=raw, pre_tok=pre, n_units=len(ws), firms=sorted(fset),
                             hit=bool(ws or fset), has_text=bool(segs), covered_min=cov / 60))
            units += [dict(idx=r.Index, kind=r.kind, text=w) for w in wtxt[:3]]
        else:
            text = f"{r.title} :: {r.summary}" if r.summary else str(r.title)
            f = firms_of(text, tags)
            hit = bool(f) or themed(text)
            t = ntok(text)
            rows.append(dict(idx=r.Index, raw_tok=t, pre_tok=t if hit else 0, n_units=1 if hit else 0, firms=sorted(f),
                             hit=hit, has_text=True))
            if hit:
                units.append(dict(idx=r.Index, kind=r.kind, text=text))
    M = pd.DataFrame(rows).set_index("idx")
    return X.join(M), units


def per_day_factor(r):
    """Multiply an item's numbers by this to get a per-day figure for its feed. Transcripts: the feed's minutes per
    day (from its listing) over the minutes the sample covers, so long and short uploads weigh by airtime."""
    if getattr(r, "sample_days", None) and r.sample_days == r.sample_days:
        return 1.0 / r.sample_days
    if r.source in ("youtube", "podcast"):
        return float(r.feed_minutes_per_day or 0.0) / r.feed_sampled_min if r.feed_sampled_min else 0.0
    return 1.0 / WINDOW_DAYS


def calibrate(units, ntok):
    """~20 real tagging calls per kind: provider usage vs the tiktoken proxy, and output tokens per unit."""
    by = defaultdict(list)
    for u in units:
        by[u["kind"]].append(u)
    res = {}
    for kind, us in by.items():
        us = us[:: max(1, len(us) // 20)][:20]
        batches = [us[i:i + (BATCH_TEXT if kind in ("text", "official", "trade") else 2)]
                   for i in range(0, len(us), BATCH_TEXT if kind in ("text", "official", "trade") else 2)]
        pin = pout = est = n = 0
        ok = 0
        for b in batches:
            user = "\n\n".join(f"[{i}] {u['text'][:12000]}" for i, u in enumerate(b))
            st, out, meta, err = llm(TAG, user)
            usage = meta.get("usage") or {}
            if usage:
                pin += usage.get("prompt_tokens", 0); pout += usage.get("completion_tokens", 0)
                est += ntok(TAG) + ntok(user); n += len(b); ok += st == "ok"
        res[kind] = {"calls": len(batches), "ok": ok, "units": n, "usage_in": pin, "proxy_in": est,
                     "ratio": round(pin / est, 3) if est else None, "out_per_unit": round(pout / n, 1) if n else None}
        print(f"calibration {kind}: {res[kind]}", flush=True)
    json.dump(res, open(os.path.join(PROBE, "calibration.json"), "w"), indent=1)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    a = ap.parse_args()
    ntok = tok_fn()
    firms_of, themed = matchers()
    X, man = load()
    M, units = measure(X, firms_of, themed, ntok)
    cal = calibrate(units, ntok) if a.calibrate else (json.load(open(os.path.join(PROBE, "calibration.json")))
                                                     if os.path.exists(os.path.join(PROBE, "calibration.json")) else {})
    p_in, p_out, p_src = price()
    ratio = {k: (v.get("ratio") or 1.0) for k, v in cal.items()}
    outpu = {k: (v.get("out_per_unit") or OUT_PER_UNIT) for k, v in cal.items()}

    if "covered_min" not in M:
        M["covered_min"] = 0.0
    M["feed_sampled_min"] = M.groupby(["source", "feed"])["covered_min"].transform("sum")
    for c in ("feed_minutes_per_day", "feed_items_per_day", "sample_days", "audio_s", "whisper_s"):
        if c not in M:
            M[c] = float("nan")
    M["f"] = [per_day_factor(r) for r in M.itertuples()]
    M["kind_r"] = M["kind"].map(lambda k: ratio.get(k, 1.0))
    M["units_out"] = M["kind"].map(lambda k: outpu.get(k, OUT_PER_UNIT))
    is_tx = M.source.isin(["youtube", "podcast"])
    # tagging calls: text in batches of BATCH_TEXT units; a transcript window is its own unit, ~2 per call
    M["calls"] = M.n_units / BATCH_TEXT
    M.loc[is_tx, "calls"] = (M.loc[is_tx, "n_units"] / 2).clip(lower=M.loc[is_tx, "n_units"].gt(0).astype(float))
    M["map_in"] = (M.pre_tok + M.calls * CALL_OVERHEAD) * M.kind_r
    M["map_out"] = M.n_units * M.units_out
    M["n_firms"] = M.firms.map(len)
    M["ledger_in"] = PASSES * M.pre_tok * (M.n_firms > 0) * M.kind_r     # firm-specific items re-read by 3 passes
    for c in ("raw_tok", "pre_tok", "map_in", "map_out", "ledger_in", "n_units", "n_firms"):
        M[c + "_d"] = M[c] * M.f
    M["items_d"] = M.f
    tx_ = M.source.isin(["youtube", "podcast"])
    M.loc[tx_, "items_d"] = M.loc[tx_, "feed_items_per_day"] / M[tx_].groupby(["source", "feed"])["key"].transform("size")
    M["firm_hits_d"] = M.n_firms * M.f
    M["map_usd_d"] = M.map_in_d * p_in + M.map_out_d * p_out
    M["ledger_usd_d"] = M.ledger_in_d * p_in
    M["map_usd_off_d"] = M.map_in_d * p_in + M.map_out_d * REASONING_OFF_OUT * p_out

    def agg(G):
        firms = set().union(*G.firms) if len(G) else set()
        tx = G[G.kind.isin(["video", "podcast"])]
        cap = tx.caption_kind.value_counts().to_dict() if len(tx) else {}
        air_min_d = float(tx.feed_minutes_per_day.iloc[0]) if len(tx) else 0.0
        return pd.Series({
            "tier": G.tier.iloc[0], "kind": G.kind.iloc[0], "mode": (G.probe_mode.iloc[0] if "probe_mode" in G and G.probe_mode.notna().any() else "window"),
            "fetched": len(G), "items_d": G.items_d.sum(), "raw_tok_d": G.raw_tok_d.sum(), "pre_tok_d": G.pre_tok_d.sum(),
            "map_in_d": G.map_in_d.sum(), "firm_hits_d": G.firm_hits_d.sum(), "unique_firms": len(firms),
            "map_usd_d": G.map_usd_d.sum(), "map_usd_off_d": G.map_usd_off_d.sum(), "ledger_usd_d": G.ledger_usd_d.sum(),
            "firms": firms,
            "captions": ", ".join(f"{k}:{v}" for k, v in cap.items()), "air_min_d": air_min_d,
            "hit_share": G.hit.mean()})

    M["grp"] = M.feed.where(M.source.isin(["youtube", "podcast", "rss", "openfda"]), M.source)
    T = M.groupby(["source", "grp"]).apply(agg).reset_index()
    T["usd_d"] = T.map_usd_d + T.ledger_usd_d
    T["usd_per_firm_hit"] = T.usd_d / T.firm_hits_d.where(T.firm_hits_d > 0)
    T["usd_month"] = T.usd_d * 30.4
    T = T.sort_values("usd_d", ascending=False)

    # whisper real-time factor → compute minutes per day if a feed's airtime goes through whisper
    w = M[M.caption_kind == "whisper"]
    rtf = float(w.audio_s.sum() / w.whisper_s.sum()) if len(w) and w.whisper_s.sum() else None
    T["whisper_min_d"] = (T.air_min_d / rtf if rtf else float("nan")) * ~T.captions.str.contains("feed")      # feed transcripts need none
    T.drop(columns=["firms"]).to_csv(OUT_MD.replace(".md", ".csv"), index=False)

    tiers = T.groupby("tier")[["items_d", "air_min_d", "raw_tok_d", "pre_tok_d", "firm_hits_d", "usd_d", "whisper_min_d"]].sum()
    news = T.source.isin(["alpaca", "finnhub"]) | T.kind.isin(["official", "trade"])
    tv3 = T.grp.isin(["CNBC Television", "Bloomberg Television", "Yahoo Finance"])
    pod3 = T.grp.isin(["Odd Lots", "Goldman Sachs Exchanges", "Morgan Stanley Thoughts on the Market"])
    gkg = T.source == "gdelt_gkg"
    sets = {"lean: Benzinga + Finnhub + official + trade press + CNBC/Bloomberg TV/Yahoo": T[news | tv3],
            "suggested: lean + all of tiers a, b + Odd Lots, GS Exchanges, MS Thoughts": T[news | T.tier.isin(["a", "b"]) | pod3],
            "everything except GDELT GKG": T[~gkg],
            "GDELT GKG alone (add-on)": T[gkg],
            "everything incl. GDELT GKG": T}

    def set_row(D):
        """Totals for a set. The ledger runs once per firm per day with new evidence: the firms a set names over the
        2-day window / 2 (sampled transcript feeds add little), each 3 passes of card + framing in, LEDGER_OUT out."""
        firms_d = len(set().union(*D.firms)) / WINDOW_DAYS if len(D) else 0
        fixed_in = firms_d * PASSES * (CARD_TOK + LEDGER_FRAME) * p_in
        led_on = D.ledger_usd_d.sum() + fixed_in + firms_d * PASSES * LEDGER_OUT_ON * p_out
        led_off = D.ledger_usd_d.sum() + fixed_in + firms_d * PASSES * LEDGER_OUT_ON * REASONING_OFF_OUT * p_out
        on, off = D.map_usd_d.sum() + led_on, D.map_usd_off_d.sum() + led_off
        yt = D[D.source == "youtube"].items_d.sum()
        return (f"| {D.items_d.sum():,.0f} | {D.air_min_d.sum():,.0f} | {D.pre_tok_d.sum():,.0f} | {D.firm_hits_d.sum():,.0f} | "
                f"{firms_d:.0f} | {D.map_usd_d.sum():.2f} / {D.map_usd_off_d.sum():.2f} | {led_on:.2f} / {led_off:.2f} | "
                f"**{on * 30.4:.0f} / {off * 30.4:.0f}** | {D.whisper_min_d.sum():.0f} | {yt:.0f} |")

    def fmt_tab(D):
        cols = ["source", "grp", "tier", "mode", "fetched", "items_d", "air_min_d", "raw_tok_d", "pre_tok_d", "map_in_d", "firm_hits_d",
                "unique_firms", "usd_d", "usd_month", "usd_per_firm_hit", "captions", "whisper_min_d"]
        D = D[cols].copy()
        for c in ("items_d", "firm_hits_d", "whisper_min_d", "air_min_d"):
            D[c] = D[c].round(1)
        for c in ("raw_tok_d", "pre_tok_d", "map_in_d"):
            D[c] = D[c].round(0).astype(int)
        D["usd_d"], D["usd_month"] = D.usd_d.round(3), D.usd_month.round(2)
        D["usd_per_firm_hit"] = D.usd_per_firm_hit.round(4)
        return D.to_markdown(index=False)

    L = ["# News desk: Phase 0 cost probe", "",
         f"Window: Tue 13 – Wed 14 Oct 2026 (UTC), fetched from {X.fetched_at.min()[:16]} UTC. "
         f"Model {MODEL}; price ${p_in * 1e6:.3f} / ${p_out * 1e6:.3f} per million input / output tokens ({p_src}).", "",
         "**How to read.** `_d` = per day. Text and official sources: the 2-day total / 2. openFDA lags, so its rate is "
         "over 45 days; GDELT GKG is sampled (one 15-minute file every 3 h) and scaled by the time it covers. Video and podcasts: "
         "volumes (`items_d`, `air_min_d` = minutes of airtime per day) come from the uploads listing / feed (the 2-day window "
         "when a channel had at least 3 uploads in it, else the last 30 days for video and 60 for podcasts); ~3 uploads per "
         "channel were transcribed and their tokens are scaled by airtime. `pre_tok` = tokens of items or transcript windows "
         "(±90 s) that name a universe firm or a sector/theme keyword. `usd_d` = tagging (map) + ledger cost; ledger is an "
         "upper bound (every named firm gets the 3-pass ledger). `whisper_min_d` = Mac compute minutes per day if the airtime "
         "goes through local whisper (0 where the feed publishes its own transcript). "
         "`usd_per_firm_hit` = cost per (item, firm) mention.", "",
         "## Totals by set", "", "Costs are shown as *reasoning on / reasoning off* (the model's default spends ~90% of its output on "
         "reasoning tokens; see Calibration). Ledger = 3 passes for every firm named that day (upper bound: only firms with a "
         "card would get one). Whisper = Mac compute minutes/day if all video airtime goes through local whisper; YouTube "
         "fetches/day = transcripts or audio downloads per day.", "",
         "| set | items/day | airtime min/day | prefiltered tokens/day | firm hits/day | firms/day | tagging $/day | ledger $/day | "
         "**$/month** | whisper min/day | YouTube fetches/day |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, D in sets.items():
        L.append(f"| {k} " + set_row(D))
    L += ["", "## Totals by tier", "", tiers.round(1).to_markdown(), "",
          "## Per source / channel / show (sorted by $/day)", "", fmt_tab(T), "",
          "## Calibration", "", "~20 real tagging calls per source kind through common.llm (default settings): provider-counted "
          "input tokens vs the tiktoken proxy (`ratio`), and output tokens per unit (item or transcript window).", "",
          "| kind | calls | ok | units | input ratio | output tokens / unit |", "|---|---|---|---|---|---|"] + \
         [f"| {k} | {v['calls']} | {v['ok']} | {v['units']} | {v['ratio']} | {v['out_per_unit']} |" for k, v in cal.items()] + \
         ["", "Side test, same 10 Benzinga items: reasoning on = 844 in / 7,662 out (7,085 reasoning), 40 s; "
          "`reasoning: {enabled: false}` = 819 in / 842 out, 3.4 s; the same 10 items tagged with the same tickers.", "",
          f"Whisper real-time factor on this Mac: {rtf:.1f}× (audio seconds per compute second)." if rtf else "Whisper: no episode transcribed.",
          "", "## Source status (fetch manifests)", ""]
    L += [f"- **{k}**: {v}" for k, v in man.items()]
    keep = ""                                                # hand-written findings survive a re-run
    if os.path.exists(OUT_MD):
        m = re.search(r"(?s)<!-- findings -->.*?<!-- /findings -->", open(OUT_MD).read())
        keep = m.group(0) if m else ""
    L.insert(2, keep or "<!-- findings -->\n<!-- /findings -->")
    open(OUT_MD, "w").write("\n".join(L) + "\n")
    print("\n".join(L[:20]))
    print(f"report → {OUT_MD}")


if __name__ == "__main__":
    main()
