"""Layer 3, Amendment 6, E1: what does it cost to trade the broad names? Coordinating session only; run through the
redacting wrapper (needs the Alpaca keys). Reads quotes only: no returns, no predictions.

Design (fixed before running): 12 trading days drawn with seed 20261113 from 2019-2025 sessions of the broad panel;
on each, every eligible broad name and every eligible S&P 500 panel name; the last SIP quote in the one second
15:59:00-15:59:01 New York time (the fund trades at T-60 s). Half-spread = (ask - bid) / (2 * mid), valid when
0 < bid < ask and the spread is under 20% of mid. Reported: median and mean half-spread in bp by universe and, for
broad names, by dollar-volume tercile (63-session mean, unadjusted, as eligibility uses).

    python3 ~/.claude/hooks/with_secrets.py 'python3 research/tree/cost_study.py'   # -> COST_STUDY.json
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "fund"))
import read3 as R3  # noqa: E402


def quotes(broker, syms, day):
    t0 = pd.Timestamp(f"{day} 15:59:00", tz="America/New_York").tz_convert("UTC")
    t1 = t0 + pd.Timedelta(seconds=1)
    last = {}
    for i in range(0, len(syms), 50):
        chunk, token = syms[i:i + 50], None
        while True:
            q = (f"/v2/stocks/quotes?symbols={','.join(chunk)}&start={t0.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                 f"&end={t1.strftime('%Y-%m-%dT%H:%M:%SZ')}&feed=sip&limit=10000" + (f"&page_token={token}" if token else ""))
            b = None
            for wait in (0, 5, 15, 45):
                time.sleep(wait)
                s, b = broker.api("GET", q, base=broker.DATA)
                if s == 200:
                    break
                if s == 400:
                    b = None
                    break
            if not isinstance(b, dict):
                break
            for sym, xs in (b.get("quotes") or {}).items():
                if xs:
                    last[sym] = (float(xs[-1]["bp"]), float(xs[-1]["ap"]))
            token = b.get("next_page_token")
            if not token:
                break
    return last


def main():
    import broker
    D, isb = R3.load_panel()
    S = D["S"]
    cand = np.where((S.year >= 2019) & (S.year <= 2025))[0]
    rng = np.random.default_rng(20261113)
    days = sorted(rng.choice(cand, 12, replace=False))
    names = np.array(D["names"])
    rows = []
    for t in days:
        day = str(S[t].date())
        el = D["elig"][t]
        syms = list(names[el])
        last = quotes(broker, syms, day)
        dv = D["dv"][t]
        broad = el & isb
        terc = pd.Series(dv[broad]).rank(pct=True).to_numpy()
        tmap = dict(zip(names[broad], np.ceil(terc * 3).clip(1, 3).astype(int)))
        for s in syms:
            if s not in last:
                rows.append({"day": day, "sym": s, "broad": bool(s in tmap), "terc": tmap.get(s), "hs_bp": None})
                continue
            bp, ap = last[s]
            mid = (bp + ap) / 2
            ok = bp > 0 and ap > bp and (ap - bp) / mid < 0.2
            rows.append({"day": day, "sym": s, "broad": bool(s in tmap), "terc": tmap.get(s),
                         "hs_bp": float((ap - bp) / (2 * mid) * 1e4) if ok else None})
        print(day, len(syms), "names,", len(last), "quoted", flush=True)
    df = pd.DataFrame(rows)

    def summ(x):
        v = x.hs_bp.dropna()
        return {"names": int(len(x)), "quoted": int(len(v)), "median_bp": float(v.median()) if len(v) else None,
                "mean_bp": float(v.mean()) if len(v) else None, "p90_bp": float(v.quantile(.9)) if len(v) else None}
    out = {"days": [str(S[t].date()) for t in days], "sp500": summ(df[~df.broad]), "broad": summ(df[df.broad]),
           "broad_by_dv_tercile": {int(k): summ(g) for k, g in df[df.broad].groupby("terc")},
           "note": "quoted half-spread one second before 15:59 ET; excludes impact and fees; the backtests charge "
                   "COST per unit traded, so the comparable figure is the half-spread",
           "run": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump(out, open(os.path.join(HERE, "COST_STUDY.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
