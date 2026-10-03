"""Desk 8 · Macro (FX) (PROTOCOL_fund.md): Protocol 5's FX call. -> fx.json

17 currencies vs USD, Protocol 3 signals as cross-sectional z-scores, frozen
FX ridge; the LLM picks 4 longs / 4 shorts. Quant (ridge) and random books
are logged alongside.
"""

import io
import json
import os
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

from common import ROOT, asof_from_env, deadline_ok, llm, require, save

require("OPENROUTER_API_KEY")
asof = asof_from_env()
N = 4
FX = {"EUR": ("EURUSD=X", True, "EZ"), "JPY": ("JPY=X", False, "JP"), "GBP": ("GBPUSD=X", True, "GB"),
      "CHF": ("CHF=X", False, "CH"), "AUD": ("AUDUSD=X", True, "AU"), "NZD": ("NZDUSD=X", True, "NZ"),
      "CAD": ("CAD=X", False, "CA"), "SEK": ("SEK=X", False, "SE"), "NOK": ("NOK=X", False, "NO"),
      "MXN": ("MXN=X", False, "MX"), "ZAR": ("ZAR=X", False, "ZA"), "PLN": ("PLN=X", False, "PL"),
      "HUF": ("HUF=X", False, "HU"), "CZK": ("CZK=X", False, "CZ"), "KRW": ("KRW=X", False, "KR"),
      "ILS": ("ILS=X", False, "IL"), "CLP": ("CLP=X", False, "CL")}

raw = yf.download([v[0] for v in FX.values()], start=asof - pd.Timedelta(days=6 * 365), end=asof + pd.Timedelta(days=1),
                  interval="1d", progress=False, auto_adjust=False, threads=True)["Close"]
raw.index = pd.to_datetime(raw.index).tz_localize(None).normalize()
spot = pd.DataFrame({c: (raw[t] if usd else 1 / raw[t]) for c, (t, usd, _) in FX.items()})
spot = spot[spot.index <= asof]


def fred(fid):
    with urllib.request.urlopen(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fid}", timeout=60) as r:
        s = pd.read_csv(io.BytesIO(r.read()), na_values=".")
    s.columns = ["date", "v"]
    return s.assign(date=pd.to_datetime(s.date)).set_index("date")["v"].dropna() / 100


rates = pd.DataFrame({c: fred(f"IR3TIB01{cc}M156N") for c, (_, _, cc) in FX.items()})
rates["USD"] = fred("IR3TIB01USM156N")
mr = rates.reindex(pd.date_range(rates.index.min(), asof + pd.DateOffset(months=3), freq="MS")).ffill()
dnow = mr[list(FX)].sub(mr["USD"], axis=0)
dsig = dnow.copy(); dsig.index = dsig.index + pd.DateOffset(months=2)     # publication lag (Protocol 3)
fdays = pd.date_range(spot.index.min(), asof, freq="D")
fw = spot.reindex(fdays).ffill(limit=3)
fw = fw[fw.index.dayofweek == 2]
xw = np.log(fw).diff() + dnow.reindex(fw.index, method="ffill") / 52
sig = pd.DataFrame({
    "carry": dsig.reindex(fw.index, method="ffill").iloc[-1],
    "mom12": xw.shift(4).rolling(48, min_periods=40).sum().iloc[-1],
    "mom3": xw.rolling(13, min_periods=11).sum().iloc[-1],
    "mom1": xw.rolling(4, min_periods=4).sum().iloc[-1],
    "rev1w": -xw.iloc[-1],
    "value": -(np.log(fw).iloc[-1] - np.log(fw.shift(260)).iloc[-1])}).dropna()
Z = (sig - sig.mean()) / sig.std()
spec = json.load(open(os.path.join(ROOT, "artefacts/llm/ridge_fx.json")))
Z["ridge_bp"] = (Z[spec["features"]].to_numpy() @ np.asarray(spec["coef"]) + spec["intercept"]) * 1e4
Z["ridge_rank"] = Z["ridge_bp"].rank(ascending=False).astype(int)
Z["carry_pct"] = sig["carry"] * 100

SYSTEM = f"""You run the macro desk of a long-short fund: a weekly, dollar-neutral currency book.
For 17 currencies against USD you get cross-sectional z-scores (carry = interest differential vs USD,
momentum over 12-1 / 3 / 1 months, rev1w = minus last week's return, value = minus the 5-year change)
and a frozen ridge forecast of next week's relative excess return (bp) with its rank (1 = best).
Carry is the one premium that survived three disjoint samples in the fund's own research; momentum
changed sign between decades.

Rules: use only this message; ignore any knowledge of what happened after the as-of date.
Choose exactly {N} longs and exactly {N} shorts, no overlap.
Return JSON only: {{"longs": [{{"id": str, "reason": str <= 25 words}}], "shorts": [...], "view": str <= 40 words}}"""
user = f"As-of Wednesday close {asof.date()}.\n" + Z.round(3).to_csv(sep="|")


def check(o):
    try:
        L = [x["id"] for x in o["longs"]]; S = [x["id"] for x in o["shorts"]]
    except Exception as exc:
        return f"schema {exc}"
    if len(L) != N or len(S) != N or len(set(L) | set(S)) != 2 * N:
        return "counts/overlap"
    return None if set(L) | set(S) <= set(Z.index) else "unknown ids"


rk = Z.sort_values("ridge_rank").index
status, out, meta, err = llm(SYSTEM, user, check) if deadline_ok(asof) else ("missed_deadline", None, {}, None)
perm = list(np.random.default_rng(int(str(asof.date()).replace("-", "")) + 1).permutation(sorted(Z.index)))
eq = lambda L, S: {**{c: 1 / N for c in L}, **{c: -1 / N for c in S}}
books = {"fx": eq([x["id"] for x in out["longs"]], [x["id"] for x in out["shorts"]]) if status == "ok" else {},
         "fx_quant": eq(list(rk[:N]), list(rk[-N:])), "fx_random": eq(perm[:N], perm[N:2 * N])}
save(asof, "fx.json", {"asof": str(asof.date()), "status": status, "error": err, "meta": meta, "llm": out,
                       "signals": json.loads(Z.round(4).to_json(orient="index")), "books": books})
print("fx desk:", status, err or "", books["fx"])
