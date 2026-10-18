"""Research shadow books from the quant trials (PREREG_thesis_tree.md Amendment 2; PROTOCOL_fund.md "Research
shadow books"). Never traded, outside Protocol 7's challenger family and score.py; records on `research-data`.

Six weekly books on the 31-name news panel, one per horizon (h = 5, 10, 20 sessions) and model:
    q5   the shadow quant book's five price factors (fund/screen.py), refit by ridge
    qn   the same factors + the news state (decayed headline vectors scored against 16 topic prototypes)
Ridge tuned on validation rank IC; quarterly refits on an expanding window (Amendment 2's refit rule).
The owner's primaries (2026-10-17): qn at h = 10, q5 at h = 20. Books: top/bottom 5 at 10% of NAV,
then the champion's risk rules (sector net <= 30%, dollar net <= 10% of gross, SPY to zero 60-day beta).

    python fund/qshadow.py seed DIR       # historical text sums (thesis panel, <= 2025-12-31) into QS_HOME/hist
    python fund/qshadow.py backfill       # walk-forward books 2018-2025, then the October 2026 weeks
    python fund/qshadow.py weekly         # live: ingest news, refit on a new quarter, this week's books, ledger
    python fund/qshadow.py ledger         # marks every book -> ledger.json and LEDGER.md

Jan-Sep 2026 is the sealed P8 holdout: no text from it is used, no decision or target window may touch it,
and no book is formed in it. Live text (from 2026-10-01) is Finnhub news rewritten with the thesis pipeline's
prompt (caf_ml_v0 m0: deepseek-v4-flash, fact extraction, entity prefix, day and 20-day dedup at cosine 0.87)
and embedded with google/gemini-embedding-001, the model the history was embedded with.
"""

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

from common import MODE, ROOT, STATE

NAMES = ("AAPL", "AMD", "AMZN", "AXP", "C", "CMCSA", "COF", "COP", "CRM", "CVX", "DIS", "EBAY", "GE", "GME", "GOOG",
         "HAL", "JPM", "KO", "META", "MS", "MSFT", "MU", "NVDA", "OXY", "PNC", "QCOM", "SLB", "TSLA", "UNH", "USB",
         "XOM")
ENTITY = {"AAPL": "Apple Inc.", "AMD": "Advanced Micro Devices", "AMZN": "Amazon.com Inc.",
          "AXP": "American Express Company", "C": "Citigroup", "CMCSA": "Comcast Corporation",
          "COF": "Capital One Financial", "COP": "ConocoPhillips", "CRM": "Salesforce, Inc.",
          "CVX": "Chevron Corporation", "DIS": "The Walt Disney Company", "EBAY": "eBay Inc.", "GE": "GE Aerospace",
          "GME": "GameStop Corp.", "GOOG": "Alphabet Inc.", "HAL": "Halliburton Company",
          "JPM": "JPMorgan Chase & Co.", "KO": "Coca-Cola", "META": "Meta Platforms Inc.", "MS": "Morgan Stanley",
          "MSFT": "Microsoft Corporation", "MU": "Micron Technology", "NVDA": "NVIDIA Corporation",
          "OXY": "Occidental Petroleum", "PNC": "PNC Financial Services Group", "QCOM": "Qualcomm Incorporated",
          "SLB": "Schlumberger Limited", "TSLA": "Tesla Inc.", "UNH": "UnitedHealth Group", "USB": "U.S. Bancorp",
          "XOM": "ExxonMobil Corporation"}
MODELS = {"q5_h5": (5, False), "qn_h5": (5, True), "q5_h10": (10, False), "qn_h10": (10, True),
          "q5_h20": (20, False), "qn_h20": (20, True)}
PRIMARY = ("qn_h10", "q5_h20")
FACTORS = ("mom12_1", "rev1m", "rev1w", "lowvol", "high52")        # artefacts/llm/ridge_stocks.json order
DIM, K_PROTO, HL, N_SIDE, UNIT = 3072, 16, 5, 5, 0.10
SECTOR_CAP, DOLLAR_CAP, COST = 0.30, 0.10, 5e-4
ALPHAS = (1e-2, 1e-1, 1, 10, 100, 1e3, 1e4, 1e5)
FIT_START, HIST_END = pd.Timestamp("2016-01-04"), pd.Timestamp("2025-12-31")
SEALED = (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-09-30"))
LIVE_START = pd.Timestamp("2026-10-01")
BACKFILL_FIRST = pd.Timestamp("2018-01-03")
CLEAN_MODEL, EMBED_MODEL, DEDUP = "deepseek/deepseek-v4-flash", "google/gemini-embedding-001", 0.87
QS_HOME = os.environ.get("QS_HOME", os.path.expanduser("~/.fund-runner/cache/qshadow"))
REC = os.path.join(STATE, MODE, "research", "qshadow")
OR = "https://openrouter.ai/api/v1"


# ------------------------------------------------------------------------------------------------- data
def prices(end):
    import yfinance as yf
    px = yf.download(list(NAMES) + ["SPY"], start="2014-06-01", end=str((end + pd.Timedelta(days=1)).date()),
                     auto_adjust=True, progress=False, threads=True)["Close"]
    px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
    px = px[px.index <= end]
    missing = [t for t in NAMES if t not in px or px[t].iloc[-5:].isna().all()]
    if missing:
        raise SystemExit(f"no recent prices for {missing}")
    return px


def sector_map():
    meta = pd.read_csv(os.path.join(ROOT, "data", "raw", "stocks", "sp500_current.csv")).set_index("Symbol")
    s = {t: meta["GICS Sector"].get(t, None) for t in NAMES}
    s["GME"] = s.get("GME") or "Consumer Discretionary"
    return {t: (v if isinstance(v, str) else "Unknown") for t, v in s.items()}


def session_of(ts, S):
    """m0's rule: before 16:00 ET on a trading day -> that session; otherwise the next session (NaT past S)."""
    et = pd.to_datetime(ts, utc=True, format="mixed").tz_convert("America/New_York")
    day = et.tz_localize(None).normalize()
    if day in S and et.hour < 16:
        return day
    pos = S.searchsorted(day, side="right" if day in S else "left")
    return S[pos] if pos < len(S) else pd.NaT


def _live_path(t):
    return os.path.join(QS_HOME, "live", f"{t}.npz")


def load_facts(t):
    p = _live_path(t)
    if not os.path.exists(p):
        return {"ts": np.zeros(0, "int64"), "session": np.zeros(0, "datetime64[D]"), "vec": np.zeros((0, DIM), "float16")}
    z = np.load(p)
    return {k: z[k] for k in ("ts", "session", "vec")}


def text_panel(S):
    """(D, N, DIM) session sums and (D, N) counts: history <= 2025-12-31, live facts >= 2026-10-01."""
    idx = {d: i for i, d in enumerate(S.values.astype("datetime64[D]"))}
    X = np.zeros((len(S), len(NAMES), DIM), np.float32)
    n = np.zeros((len(S), len(NAMES)), np.int32)
    for j, t in enumerate(NAMES):
        h = os.path.join(QS_HOME, "hist", f"{t}_dedup.npz")
        if os.path.exists(h):
            z = np.load(h)
            for d, c, v in zip(z["session"], z["n"], z["sum"]):
                if d in idx and d <= np.datetime64(HIST_END.date()):
                    X[idx[d], j] += v
                    n[idx[d], j] += c
        f = load_facts(t)
        for d, v in zip(f["session"], f["vec"]):
            if d in idx and d >= np.datetime64(LIVE_START.date()):
                X[idx[d], j] += v.astype(np.float32)
                n[idx[d], j] += 1
    return X, n


class Panel:
    def __init__(self, end):
        px = prices(end)
        self.S = px.index
        self.close = px[list(NAMES)].values
        spy = px["SPY"].values
        self.spy = spy
        self.r = np.vstack([np.full((1, len(NAMES)), np.nan), self.close[1:] / self.close[:-1] - 1])
        self.rm = np.concatenate([[np.nan], spy[1:] / spy[:-1] - 1])
        self.beta252 = self._welch(252, 200)
        self.beta60 = self._welch(60, 50)
        lp = pd.DataFrame(np.log(self.close), index=self.S)
        sig = {"mom12_1": lp.shift(20) - lp.shift(252), "rev1m": -(lp - lp.shift(20)), "rev1w": -(lp - lp.shift(5)),
               "lowvol": -lp.diff().rolling(60, min_periods=50).std(),
               "high52": pd.DataFrame(self.close, index=self.S) / pd.DataFrame(self.close, index=self.S)
               .rolling(252, min_periods=200).max()}
        Z = np.stack([sig[c].values for c in FACTORS], -1)
        self.quant = ((Z - np.nanmean(Z, 1, keepdims=True)) / np.nanstd(Z, 1, keepdims=True)).astype(np.float32)
        self.tsum, self.n = text_panel(self.S)
        self._intensity()
        self._state()
        self.sealed = (self.S >= SEALED[0]) & (self.S <= SEALED[1])

    def _welch(self, win, minp):
        lo = np.minimum(-2 * self.rm, 4 * self.rm)[:, None]
        hi = np.maximum(-2 * self.rm, 4 * self.rm)[:, None]
        w = pd.DataFrame(np.clip(self.r, lo, hi), index=self.S)
        m = pd.Series(self.rm, index=self.S)
        b = w.rolling(win, min_periods=minp).cov(m).div(m.rolling(win, min_periods=minp).var(), axis=0)
        return ((2 / 3) * b.fillna(1.0) + 1 / 3).values

    def _intensity(self):
        n = self.n.astype(np.float32)
        lam = 0.5 ** (1 / HL)
        dec, since = np.zeros_like(n), np.zeros_like(n)
        acc, last = np.zeros(n.shape[1], np.float32), np.full(n.shape[1], 60.0, np.float32)
        for t in range(len(n)):
            acc = lam * acc + n[t]
            last = np.where(n[t] > 0, 0.0, np.minimum(last + 1, 60.0))
            dec[t], since[t] = acc, last
        self.intensity = np.stack([np.log1p(n), np.log1p(dec), np.log1p(since)], -1).astype(np.float32)

    def _state(self):
        lam = np.float32(0.5 ** (1 / HL))
        self.state = np.empty_like(self.tsum)
        S_, W = np.zeros(self.tsum.shape[1:], np.float32), np.zeros(self.n.shape[1], np.float32)
        for t in range(len(self.tsum)):
            S_ = lam * S_ + self.tsum[t]
            W = lam * W + self.n[t]
            self.state[t] = np.where(W[:, None] > 1e-3, S_ / np.maximum(W, 1e-3)[:, None], 0.0)

    def target(self, h):
        """Residual return close(d+1) -> close(d+1+h), demeaned; NaN where the window leaves the data or touches
        the sealed window, or the decision itself is in it."""
        D = len(self.S)
        r, rm = np.nan_to_num(self.r), np.nan_to_num(self.rm)
        cr = np.vstack([np.zeros((1, r.shape[1])), np.cumsum(r, 0)])
        cm = np.concatenate([[0], np.cumsum(rm)])
        y = np.full(r.shape, np.nan)
        sealed_cum = np.concatenate([[0], np.cumsum(self.sealed)])
        for d in range(D - 1 - h):
            a, b = d + 2, d + 2 + h
            if sealed_cum[b] - sealed_cum[d] > 0:
                continue
            y[d] = (cr[b] - cr[a]) - self.beta252[d] * (cm[b] - cm[a])
        return y - np.nanmean(y, 1, keepdims=True)


# ------------------------------------------------------------------------------------------------- model
def _ic(pred, y, idx):
    out = []
    for d in idx:
        m = np.isfinite(pred[d]) & np.isfinite(y[d])
        if m.sum() >= 10:
            a, b = pd.Series(pred[d][m]).rank().values, pd.Series(y[d][m]).rank().values
            if a.std() > 0 and b.std() > 0:
                out.append(np.corrcoef(a, b)[0, 1])
    return float(np.mean(out)) if out else np.nan


def features(p, news, C=None):
    blocks = [p.quant]
    if news:
        if getattr(p, "_U", None) is None:
            nrm = np.linalg.norm(p.state, axis=-1, keepdims=True)
            p._U = np.where(nrm > 0, p.state / np.maximum(nrm, 1e-9), 0.0).astype(np.float32)
        blocks += [p.intensity, (p._U @ C.T).astype(np.float32)]
    return np.concatenate(blocks, -1)


def fit(p, q, h, news):
    """Model for the quarter starting at session index q: rows from FIT_START whose target ends before q."""
    from sklearn.cluster import KMeans
    from sklearn.linear_model import Ridge
    lo = int(np.searchsorted(p.S, FIT_START))
    y = p.target(h)
    train = np.arange(lo, q)
    train = train[(train + 1 + h < q) & np.isfinite(y[train]).any(1)]
    C = None
    if news:
        rows = np.arange(lo, q)
        d, i = np.where(p.n[rows] > 0)
        V = p.tsum[rows[d], i] / p.n[rows[d], i][:, None]
        V = V / np.linalg.norm(V, axis=1, keepdims=True)
        if len(V) > 20000:
            V = V[np.random.default_rng(0).choice(len(V), 20000, replace=False)]
        km = KMeans(K_PROTO, n_init=2, random_state=0).fit(V)
        C = (km.cluster_centers_ / np.linalg.norm(km.cluster_centers_, axis=1, keepdims=True)).astype(np.float32)
    X = features(p, news, C)
    Xr = X[train].reshape(-1, X.shape[-1])
    mu, sd = np.nanmean(Xr, 0), np.nanstd(Xr, 0)
    sd[~np.isfinite(sd) | (sd == 0)] = 1.0
    Xs = (X - mu) / sd
    ys = y / np.nanstd(y[train])
    cut = int(len(train) * 0.8)
    tr, va = train[: cut - h - 1], train[cut:]

    def rows_(idx):
        A, b = Xs[idx].reshape(-1, X.shape[-1]), ys[idx].reshape(-1)
        k = np.isfinite(b) & np.isfinite(A).all(1)
        return A[k], b[k]
    best, bs = ALPHAS[0], -np.inf
    At, bt = rows_(tr)
    for a in ALPHAS:
        m = Ridge(alpha=a).fit(At, bt)
        pv = np.full(y.shape, np.nan)
        pv[va] = m.predict(np.nan_to_num(Xs[va]).reshape(-1, X.shape[-1])).reshape(len(va), -1)
        s = _ic(pv, ys, va)
        if np.isfinite(s) and s > bs:
            best, bs = a, s
    m = Ridge(alpha=best).fit(*rows_(train))
    return {"coef": m.coef_.tolist(), "intercept": float(m.intercept_), "mu": mu.tolist(), "sd": sd.tolist(),
            "alpha": best, "n_train": int(len(train)), "quarter": str(p.S[q].date()),
            "C": C.tolist() if C is not None else None}


def features_row(p, news, C, d):
    blocks = [p.quant[d]]
    if news:
        st = p.state[d]
        nrm = np.linalg.norm(st, axis=-1, keepdims=True)
        U = np.where(nrm > 0, st / np.maximum(nrm, 1e-9), 0.0)
        blocks += [p.intensity[d], (U @ C.T).astype(np.float32)]
    return np.concatenate(blocks, -1)


def predict(p, model, news, d):
    C = np.asarray(model["C"], np.float32) if news else None
    x = features_row(p, news, C, d)
    xs = (x - np.asarray(model["mu"])) / np.asarray(model["sd"])
    s = np.nan_to_num(xs) @ np.asarray(model["coef"]) + model["intercept"]
    s[~np.isfinite(x).all(1)] = np.nan
    return s


def quarter_start(p, d):
    """Index of the first session of d's calendar quarter."""
    q = p.S[d].to_period("Q").start_time
    return int(np.searchsorted(p.S, q))


# ------------------------------------------------------------------------------------------------- books
def risk(w, sector, beta):
    """fund/pm_risk.py risk(): sector net cap, dollar-net cap on the heavy leg, then SPY to zero beta."""
    w, log = w.copy(), []
    sec = pd.Series(sector).reindex(w.index)
    for s_, net in w.groupby(sec).sum().items():
        if abs(net) > SECTOR_CAP + 1e-9:
            side = w.index[(sec == s_) & (np.sign(w) == np.sign(net))]
            other = net - w[side].sum()
            w[side] *= (np.sign(net) * SECTOR_CAP - other) / w[side].sum()
            log.append(f"sector {s_}: net {net:+.2f} -> {np.sign(net) * SECTOR_CAP:+.2f}")
    long_, short_ = w[w > 0].sum(), -w[w < 0].sum()
    gross, net = long_ + short_, long_ - short_
    if gross > 0 and abs(net) > DOLLAR_CAP * gross + 1e-9:
        if net > 0:
            k = short_ * (1 + DOLLAR_CAP) / (1 - DOLLAR_CAP) / long_ if short_ > 0 else 0.0
            w[w > 0] *= k
        else:
            k = long_ * (1 + DOLLAR_CAP) / (1 - DOLLAR_CAP) / short_ if long_ > 0 else 0.0
            w[w < 0] *= k
        log.append(f"dollar net {net:+.2f} of gross {gross:.2f}: heavy leg x{k:.2f}")
        w = w[w != 0]
    out = {t: round(float(v), 5) for t, v in w.items()}
    spy = -float((w * pd.Series(beta).reindex(w.index)).sum())
    if abs(spy) > 1e-6:
        out["SPY"] = round(spy, 5)
    return out, log


def book(scores, sector, beta):
    s = pd.Series(scores).dropna().sort_values()
    if len(s) < 2 * N_SIDE:
        return {}, ["fewer than 10 scored names: flat"]
    w = pd.concat([pd.Series(UNIT, index=s.index[-N_SIDE:]), pd.Series(-UNIT, index=s.index[:N_SIDE])])
    return risk(w, sector, beta)


def week_record(p, d, models_cache, sector, kind):
    rec = {"asof": str(p.S[d].date()), "kind": kind, "models": {}}
    beta = dict(zip(NAMES, p.beta60[d]))
    for name, (h, news) in MODELS.items():
        q = quarter_start(p, d)
        key = (name, q)
        if key not in models_cache:
            models_cache[key] = fit(p, q, h, news)
        m = models_cache[key]
        sc = predict(p, m, news, d)
        scores = {t: (None if not np.isfinite(v) else round(float(v), 6)) for t, v in zip(NAMES, sc)}
        bk, log = book({t: v for t, v in scores.items() if v is not None}, sector, beta)
        rec["models"][name] = {"h": h, "news": news, "quarter": m["quarter"], "alpha": m["alpha"],
                               "n_train": m["n_train"], "scores": scores, "book": bk, "risk_log": log}
    rec["text_sessions_8w"] = int((p.n[max(0, d - 40): d + 1].sum(1) > 0).sum())
    rec["sha256"] = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
    return rec


# ------------------------------------------------------------------------------------------------- live text
def _post(path, payload, tries=3, limit=90):
    """OpenRouter call; every attempt goes to the fund's LLM call log (common._log_call: caller, model, provider,
    tokens, billed cost, prompt). Not guards.guarded_llm: the rewrite must use the history's model and its
    single-message, json_schema request (caf_ml_v0 m0), which common.llm cannot send."""
    from common import _log_call
    payload = {**payload, "usage": {"include": True}}
    prompt = payload["messages"][0]["content"] if "messages" in payload else f"[embeddings x{len(payload['input'])}]"
    err = None
    for _ in range(tries):
        resp = None
        try:
            req = urllib.request.Request(f"{OR}/{path}", data=json.dumps(payload).encode(), headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/andreaskoul/test_trading_agent", "X-Title": "fund-qshadow"})
            # hard deadline per call, as common.llm: OpenRouter keeps a slow request alive with whitespace, so a
            # socket timeout alone never fires (2026-10-17: one hung call stalled the October ingest for 40 min)
            t0, buf = time.time(), b""
            with urllib.request.urlopen(req, timeout=60) as r:
                while chunk := r.read1(65536):
                    buf += chunk
                    if time.time() - t0 > limit:
                        raise TimeoutError(f"call exceeded {limit} s")
            resp = json.loads(buf)
            _log_call("", prompt, payload.get("temperature", 0.0), {**resp, "model": resp.get("model") or payload["model"]},
                      "ok", None)
            return resp, None
        except urllib.error.HTTPError as exc:
            err = f"HTTP {exc.code}: {exc.read()[:300].decode(errors='replace')}"
        except Exception as exc:
            err = repr(exc)
        _log_call("", prompt, payload.get("temperature", 0.0), resp, "error", err)
        time.sleep(3)
    return None, err


def m0_prompt(title, snippet, entity):
    # caf_ml_v0/data/prep/m0.ipynb build_prompt, verbatim
    return f"""Filter and clean news about {entity} for semantic analysis.

HEADLINE: "{title}"
SNIPPET: "{snippet}"

TASK: Extract ALL distinct, semantically rich business facts from the combined headline and snippet that are temporally aligned with the publication timestamp. Each fact must be self-contained, mutually distinct, and suitable for embedding-based clustering. Do not extract multiple phrasings of the same underlying event—only genuinely separate facts or causal chains. Do not include facts that merely reference past events without new information.

KEEP — concrete business drivers with causal/relational depth:
- Operational metrics (revenue, margins, unit volumes) with magnitude context
- Strategic actions (acquisitions, partnerships, restructuring) with rationale
- Supply chain causality (tariff → cost increase → pricing response)
- Temporal anchors (Q1 2025, fiscal deadlines, launch timelines)
- Competitive positioning (market share shifts, entry/exit decisions)
- Regulatory dependencies (antitrust rulings, patent decisions with business impact)
- Executive changes with strategic context

DISCARD — low-information noise that collapses embedding clusters:
- Stock prices, price targets, ratings ("PT raised to $275", "shares up 3%")
- Market cap milestones, trading volume commentary
- Generic advice ("should you buy", "top picks")
- Vague clickbait without operational specifics ("Here's why...")
- Listicle mentions without {entity}-specific substance

EXTRACTION RULES:
- Emit one entry per distinct event, causal chain, or operational driver present in the text
- Each fact must be self-contained (requires no cross-referencing with other facts)
- Preserve causal chains (X enables Y) and temporal structure
- Include specific numbers, dates, actor names
- Strip stock-price framing ("shares surge after..." → keep the "after")
- Max 250 characters per fact
- No invented details

OUTPUT: JSON {{"discarded": boolean, "facts": ["fact 1", "fact 2", ...]}}"""


SCHEMA = {"type": "json_schema", "json_schema": {"name": "headline_cleanup", "strict": True, "schema": {
    "type": "object", "properties": {"discarded": {"type": "boolean"}, "facts": {"type": "array", "items": {"type": "string"}}},
    "required": ["discarded", "facts"], "additionalProperties": False}}}


def clean(title, snippet, entity):
    """One article -> (status, facts, detail). m0's validation: 20-250 chars, entity prefix, exact dedup."""
    resp, err = _post("chat/completions", {"model": CLEAN_MODEL, "temperature": 0, "response_format": SCHEMA,
                                           "messages": [{"role": "user", "content": m0_prompt(title, snippet, entity)}]})
    if resp is None:
        return "http_error", [], err
    try:
        raw = resp["choices"][0]["message"]["content"]
        obj = json.loads(raw)
        assert isinstance(obj.get("facts", []), list)
    except Exception as exc:
        return "bad_json", [], f"{exc!r}: {str(resp)[:300]}"
    if obj.get("discarded"):
        return "model_discarded", [], ""
    out, seen = [], set()
    first = entity.split()[0]
    for f in obj.get("facts", []):
        f = re.sub(r"\s+", " ", str(f)).strip()
        if not (20 <= len(f) <= 250):
            continue
        if first.lower() not in f.lower():
            f = f"{first}: {f}"
        if f.lower() not in seen:
            seen.add(f.lower())
            out.append(f)
    return ("kept" if out else "no_valid_facts"), out, ""


def embed(texts):
    vecs = []
    for k in range(0, len(texts), 90):
        resp, err = _post("embeddings", {"model": EMBED_MODEL, "input": texts[k: k + 90]})
        if resp is None:
            raise RuntimeError(f"embedding call failed: {err}")
        V = np.array([e["embedding"] for e in sorted(resp["data"], key=lambda e: e["index"])], np.float32)
        if V.shape[1] != DIM:
            raise RuntimeError(f"embedding dim {V.shape[1]} != {DIM}")
        vecs.append(V / np.linalg.norm(V, axis=1, keepdims=True))
        time.sleep(0.25)
    return np.vstack(vecs) if vecs else np.zeros((0, DIM), np.float32)


def ingest(lo, hi, S, threads=32):
    """Finnhub archive news for the 31 names published in [lo, hi] -> m0 facts -> embeddings -> live store.
    Saved name by name, so an interrupted run resumes; articles already processed are skipped; an article whose
    session is not known yet (after the last close) waits for the next run. Returns counts for the quality gate."""
    from infoflow import news
    lo = max(pd.Timestamp(lo, tz="UTC"), pd.Timestamp(LIVE_START, tz="UTC"))
    A = news(lo, pd.Timestamp(hi, tz="UTC"))
    only = os.environ.get("QS_ONLY")                     # testing: restrict to some names
    A = A[A["sym"].isin(only.split(",") if only else NAMES)].copy()
    pdone = os.path.join(QS_HOME, "live", "processed.json")
    os.makedirs(os.path.dirname(pdone), exist_ok=True)
    done = json.load(open(pdone)) if os.path.exists(pdone) else {}
    A["key"] = A["sym"] + "|" + A["h"].astype(str)
    A = A[~A["key"].isin(set(done))].drop_duplicates("key")
    A["session"] = [session_of(t, S) for t in A["published"]]
    A = A[A["session"].notna()]                         # after the last known session: left for the next run
    stats = {"articles": int(len(A)), "kept": 0, "failed": 0, "facts": 0, "dup_dropped": 0, "reasons": {}}
    for t, G in A.groupby("sym"):
        rows = list(G.itertuples())
        with cf.ThreadPoolExecutor(threads) as ex:
            res = list(ex.map(lambda r: clean(r.t, r.desc or "", ENTITY[r.sym]), rows))
        new, rejects = [], []
        for r, (st, facts, det) in zip(rows, res):
            stats["reasons"][st] = stats["reasons"].get(st, 0) + 1
            if st in ("http_error", "bad_json"):
                stats["failed"] += 1
                rejects.append({"key": r.key, "status": st, "detail": det})
                continue                                # not marked processed: retried next run
            stats["kept"] += st == "kept"
            new += [(pd.Timestamp(r.published), r.session, f) for f in facts]
        new.sort(key=lambda x: x[0])
        V = embed([f for _, _, f in new]) if new else np.zeros((0, DIM), np.float32)
        store = load_facts(t)
        ts, sess, vec = list(store["ts"]), list(store["session"]), list(store["vec"].astype(np.float32))
        for (when, s_, _), v in zip(new, V):
            # m0: day dedup then a 20-day window, both at cosine > 0.87 against earlier kept facts; the window
            # contains the day, so one pass over the earlier kept facts of the last 20 days is the same rule
            ns = int(when.value)
            if any(0 <= ns - ts[k] <= 20 * 86400 * 10**9 and float(v @ vec[k]) > DEDUP for k in range(len(ts))):
                stats["dup_dropped"] += 1
                continue
            ts.append(ns)
            sess.append(np.datetime64(s_.date()))
            vec.append(v)
            stats["facts"] += 1
        np.savez(_live_path(t), ts=np.array(ts, "int64"), session=np.array(sess, "datetime64[D]"),
                 vec=np.array(vec, np.float16).reshape(-1, DIM))
        for r, (st, _, _) in zip(rows, res):
            if st not in ("http_error", "bad_json"):
                done[r.key] = st
        json.dump(done, open(pdone, "w"))
        if rejects:
            with open(os.path.join(QS_HOME, "live", "rejects.jsonl"), "a") as f:
                for x in rejects:
                    f.write(json.dumps({**x, "at": pd.Timestamp.now(tz="UTC").isoformat()}) + "\n")
        print(f"  {t}: {len(rows)} articles, facts total {stats['facts']}, failed {stats['failed']}", flush=True)
    return stats


# ------------------------------------------------------------------------------------------------- ledger
def all_records():
    recs = []
    bf = os.path.join(REC, "backfill.json")
    if os.path.exists(bf):
        recs += json.load(open(bf))["records"]
    for f in sorted(os.listdir(REC)) if os.path.isdir(REC) else []:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f):
            recs.append(json.load(open(os.path.join(REC, f))))
    seen, out = set(), []
    for r in sorted(recs, key=lambda r: r["asof"]):
        if r["asof"] not in seen:
            seen.add(r["asof"])
            out.append(r)
    return out


def ledger(p=None):
    """Marks every book like shadow_ledger.py: weights enter at the execution day's close (first session after
    the as-of Wednesday), held to the next record's execution close; 5 bp per side on weight changes; cash
    earns nothing; gaps (the sealed window) are flat. Also each week's realised rank IC at the book's horizon."""
    recs = all_records()
    if not recs:
        return {}
    end = pd.Timestamp(recs[-1]["asof"]) + pd.Timedelta(days=40)
    p = p or Panel(min(end, pd.Timestamp.now().normalize()))
    S, closes = p.S, pd.DataFrame(p.close, index=p.S, columns=NAMES)
    closes["SPY"] = p.spy
    ex = [S[S > pd.Timestamp(r["asof"])][0] if (S > pd.Timestamp(r["asof"])).any() else None for r in recs]
    targets = {h: p.target(h) for h in (5, 10, 20)}
    out = {}
    for name, (h, _) in MODELS.items():
        nav, prev, rows = 100_000.0, {}, []
        for k, r in enumerate(recs):
            w = r["models"].get(name, {}).get("book", {})
            e0 = ex[k]
            e1 = ex[k + 1] if k + 1 < len(recs) else None
            gap = e1 is not None and (e1 - e0).days > 10
            if e0 is None or e1 is None or gap:
                rows.append({"asof": r["asof"], "kind": r["kind"], "ret": None, "nav": nav, "ic": None})
                prev = {} if gap else prev
                continue
            turn = sum(abs(w.get(t, 0) - prev.get(t, 0)) for t in set(w) | set(prev))
            px0, px1 = closes.loc[e0], closes.loc[e1]
            ret = sum(v * (px1[t] / px0[t] - 1) for t, v in w.items() if np.isfinite(px1[t] / px0[t])) - COST * turn
            nav *= 1 + ret
            d = int(np.searchsorted(S, pd.Timestamp(r["asof"])))
            sc = np.array([np.nan if r["models"][name]["scores"].get(t) is None else r["models"][name]["scores"][t]
                           for t in NAMES])
            yy = targets[h][d] if d < len(S) else np.full(len(NAMES), np.nan)
            m = np.isfinite(sc) & np.isfinite(yy)
            ic = float(pd.Series(sc[m]).corr(pd.Series(yy[m]), method="spearman")) if m.sum() >= 10 else None
            rows.append({"asof": r["asof"], "kind": r["kind"], "ret": ret, "nav": nav, "ic": ic})
            prev = w
        out[name] = rows
    os.makedirs(REC, exist_ok=True)
    last = recs[-1]
    json.dump({"generated": pd.Timestamp.now(tz="UTC").isoformat(), "primary": list(PRIMARY), "books": out,
               "latest": {"asof": last["asof"], "kind": last["kind"],
                          "books": {k: v["book"] for k, v in last["models"].items()}}},
              open(os.path.join(REC, "ledger.json"), "w"), default=float)
    write_md(out)
    return out


def write_md(out):
    def stats(rows):
        r = pd.Series([x["ret"] for x in rows if x["ret"] is not None], dtype=float)
        ic = pd.Series([x["ic"] for x in rows if x["ic"] is not None], dtype=float)
        if r.empty:
            return "| – | – | – | – | – |"
        cum = float(np.prod(1 + r) - 1)
        sh = float(r.mean() / r.std() * np.sqrt(52)) if len(r) > 1 and r.std() > 0 else np.nan
        v = np.concatenate([[1.0], np.cumprod(1 + r)])                    # the peak starts at the initial value
        dd = float((v / np.maximum.accumulate(v) - 1).min())
        f = lambda x, spec: "–" if not np.isfinite(x) else format(x, spec)
        return f"| {len(r)} | {cum:+.1%} | {f(sh, '+.2f')} | {dd:.1%} | {f(ic.mean() if len(ic) else np.nan, '+.3f')} |"
    spans = {"backfill 2018-21": lambda x: x["kind"] == "backfill" and x["asof"] < "2022",
             "backfill 2022-25 (seen in research)": lambda x: x["kind"] == "backfill" and "2022" <= x["asof"] < "2026",
             "Oct 2026 catch-up (computed late)": lambda x: x["kind"] == "catchup",
             "live (forward)": lambda x: x["kind"] == "live"}
    lines = ["# Research shadow books (quant trials)", "",
             "Never traded. Weekly, Thursday close to Thursday close, 5 bp per side, cash 0. Primaries: "
             + ", ".join(PRIMARY) + ". Jan-Sep 2026 is the sealed P8 window: no books. Only `live` rows are "
             "forward evidence.", ""]
    for span, keep in spans.items():
        lines += [f"## {span}", "", "| book | weeks | cumulative | Sharpe (ann.) | max drawdown | mean IC |",
                  "|---|---|---|---|---|---|"]
        for name, rows in out.items():
            lines.append(f"| {name}{' (primary)' if name in PRIMARY else ''} " + stats([x for x in rows if keep(x)]))
        lines.append("")
    open(os.path.join(REC, "LEDGER.md"), "w").write("\n".join(lines))


# ------------------------------------------------------------------------------------------------- commands
def cmd_seed(src):
    os.makedirs(os.path.join(QS_HOME, "hist"), exist_ok=True)
    for t in NAMES:
        z = np.load(os.path.join(src, f"{t}_dedup.npz"))
        keep = z["session"] <= np.datetime64(HIST_END.date())
        np.savez(os.path.join(QS_HOME, "hist", f"{t}_dedup.npz"), session=z["session"][keep], n=z["n"][keep],
                 sum=z["sum"][keep])
    print("seeded", len(NAMES), "names into", os.path.join(QS_HOME, "hist"))


def cmd_ingest(asof=None):
    """Fill the live store from 2026-10-01 to now (the catch-up weeks need it)."""
    end = pd.Timestamp(asof) if asof else pd.Timestamp.now().normalize()
    px = prices(end)
    print(ingest(LIVE_START, end + pd.Timedelta(hours=23, minutes=59), px.index))


def wednesdays(p, lo, hi):
    return [i for i, d in enumerate(p.S) if lo <= d <= hi and d.weekday() == 2]


def cmd_backfill(asof_end=None):
    end = pd.Timestamp(asof_end) if asof_end else pd.Timestamp.now().normalize()
    p = Panel(end)
    sector = sector_map()
    cache, recs = {}, []
    last_hist = max(i for i in wednesdays(p, BACKFILL_FIRST, HIST_END) if p.S[i + 1:].size and
                    (p.S[p.S > p.S[i]][0] <= HIST_END))
    for d in wednesdays(p, BACKFILL_FIRST, HIST_END):
        if d > last_hist:
            break
        recs.append(week_record(p, d, cache, sector, "backfill"))
        if len(recs) % 26 == 0:
            print("  backfill", recs[-1]["asof"], flush=True)
    for d in wednesdays(p, LIVE_START, end):
        if d + 1 < len(p.S):                          # its execution day exists: a catch-up week, computed late
            recs.append(week_record(p, d, cache, sector, "catchup"))
    os.makedirs(REC, exist_ok=True)
    body = {"generated": pd.Timestamp.now(tz="UTC").isoformat(), "records": recs}
    body["batch_sha256"] = hashlib.sha256(json.dumps(recs, sort_keys=True).encode()).hexdigest()
    json.dump(body, open(os.path.join(REC, "backfill.json"), "w"))
    print(f"backfill: {len(recs)} weeks ({recs[0]['asof']} .. {recs[-1]['asof']})")
    ledger(p)


def cmd_catchup(asof=None):
    """Append the October 2026 catch-up weeks (as-of Wednesdays from 2026-10-01 whose execution day has passed) to
    backfill.json; they need the live store filled first (`ingest`)."""
    end = pd.Timestamp(asof) if asof else pd.Timestamp.now().normalize()
    p = Panel(end)
    bf = os.path.join(REC, "backfill.json")
    body = json.load(open(bf))
    have = {r["asof"] for r in body["records"]}
    cache = {}
    for d in wednesdays(p, LIVE_START, end):
        if d + 1 < len(p.S) and str(p.S[d].date()) not in have:
            body["records"].append(week_record(p, d, cache, sector_map(), "catchup"))
            print("  catch-up", body["records"][-1]["asof"], flush=True)
    body["batch_sha256"] = hashlib.sha256(json.dumps(body["records"], sort_keys=True).encode()).hexdigest()
    json.dump(body, open(bf, "w"))
    ledger(p)


def cmd_weekly(asof=None):
    now = pd.Timestamp.now(tz="UTC")
    asof = pd.Timestamp(asof) if asof else (now.tz_localize(None).normalize() - pd.Timedelta(days=(now.weekday() - 2) % 7))
    if asof < LIVE_START:
        raise SystemExit("before the live start")
    out = os.path.join(REC, f"{asof.date()}.json")
    if os.path.exists(out):
        print(f"{out} exists: never re-run a week"); return
    px = prices(asof + pd.Timedelta(days=7))
    stats = ingest(asof - pd.Timedelta(days=21), asof + pd.Timedelta(hours=23, minutes=59), px.index)
    p = Panel(asof)
    if p.S[-1] != asof:
        raise SystemExit(f"{asof.date()} is not a session")
    rec = week_record(p, len(p.S) - 1, {}, sector_map(), "live")
    rec["ingest"] = stats
    rec["sha256"] = hashlib.sha256(json.dumps({k: v for k, v in rec.items() if k != "sha256"}, sort_keys=True)
                                   .encode()).hexdigest()
    os.makedirs(REC, exist_ok=True)
    json.dump(rec, open(out, "w"))
    print(json.dumps({k: rec["models"][k]["book"] for k in PRIMARY}, indent=1), stats)
    ledger()
    from guards import quality_gate                             # CLAUDE.md 9: the gate runs after saving
    ok, q = quality_gate(["error"] * stats["failed"] + ["ok"] * (stats["articles"] - stats["failed"]))
    if not ok:
        raise SystemExit(f"quality gate: {q}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["seed", "ingest", "backfill", "catchup", "weekly", "ledger"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--asof")
    a = ap.parse_args()
    {"seed": lambda: cmd_seed(a.arg), "ingest": lambda: cmd_ingest(a.asof), "backfill": lambda: cmd_backfill(a.asof),
     "catchup": lambda: cmd_catchup(a.asof), "weekly": lambda: cmd_weekly(a.asof),
     "ledger": lambda: ledger()}[a.cmd]()
