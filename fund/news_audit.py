"""Late-served news audit (measurement only: no language model, nothing feeds a decision).

    python fund/news_audit.py            # audits up to MAX_DAYS live check days not yet audited

The live kill checks (fund/lifecycle.py kill_check) read the articles Finnhub serves at T-20 min, published since the
previous check. An article published before a cutoff but served after it falls in no window. Each night this audit
re-fetches every audited window (lo, hi] once the vendor has caught up, and records the articles the live check did
not see: lifecycle/news_audit/<day>.json, written once. `lag_lb_min` is a lower bound on the serving delay: the
article was published that many minutes before the check that missed it. Each missed article is classed by
cause: "late" (newer than the oldest article the check read: not yet served when it ran) or "capped" (older than
that, on a check that read its full 25: cut by kill_check's cap on the newest articles).
"""

import glob
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MODE, STATE                                    # noqa: E402
from newsio import finnhub_news, norm                             # noqa: E402

LC = os.path.join(STATE, MODE, "lifecycle")
OUT = os.path.join(LC, "news_audit")
MAX_DAYS, SETTLE_H = int(os.environ.get("NEWS_AUDIT_MAX_DAYS", 4)), 6                         # days audited per run; hours after a check before it is audited
CAP = 25                                          # kill_check reads the 25 newest articles of a window (lifecycle.py)


def audit_day(rec, prior, fetch=finnhub_news):
    """rec: one live check record (lifecycle/news/<day>.json). prior: {lot id: (news_until, set of headlines)} from the
    earlier records. Returns the audit record for that day."""
    hi = pd.Timestamp(rec["close_ts"], unit="s", tz="UTC")
    checked = pd.Timestamp(rec.get("checked_at") or hi)
    checked = checked.tz_localize("UTC") if checked.tzinfo is None else checked.tz_convert("UTC")
    lots, n_seen, n_missed, n_late, n_capped = {}, 0, 0, 0, 0
    for i, k in rec["lots"].items():
        if k.get("status") not in ("checked", "no_new_news"):
            continue
        until, before = prior.get(i, (None, set()))
        lo = pd.Timestamp(until, unit="s", tz="UTC") if until else hi - pd.Timedelta(hours=24)
        arts = fetch(i.split("|")[-1], lo, hi)
        if arts is None:
            lots[i] = {"status": "news_unavailable"}; continue
        own = set(k.get("headlines") or [])
        had = own | before
        miss = [a for a in arts if norm(a.get("headline")) not in had]
        # Two causes. The check keeps the CAP newest articles: on a busy day the older ones are cut ("capped"). An
        # article newer than the oldest one checked was not there when the check ran ("late": served after it).
        t_own = [a["datetime"] for a in arts if norm(a.get("headline")) in own]
        oldest = min(t_own) if t_own else None
        full = len(own) >= CAP
        kinds = ["capped" if full and oldest is not None and a["datetime"] < oldest else "late" for a in miss]
        n_seen += len(own); n_missed += len(miss)
        n_late += kinds.count("late"); n_capped += kinds.count("capped")
        lots[i] = {"ticker": i.split("|")[-1], "lo": int(lo.timestamp()), "lo_approx": until is None,
                   "n_checked": len(own), "n_missed": len(miss), "n_late": kinds.count("late"), "n_capped": kinds.count("capped"),
                   "missed": [{"published": int(a["datetime"]), "source": a.get("source"), "headline": a.get("headline"), "kind": kd,
                               "lag_lb_min": round((checked.timestamp() - a["datetime"]) / 60, 1)} for a, kd in zip(miss, kinds)]}
    return {"day": rec["day"], "hi": rec["close_ts"], "checked_at": rec.get("checked_at"), "n_checked": n_seen,
            "n_missed": n_missed, "n_late": n_late, "n_capped": n_capped, "lots": lots,
            "audited_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def main():
    os.makedirs(OUT, exist_ok=True)
    recs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(LC, "news", "*.json")))]
    prior, done = {}, 0
    for rec in recs:
        p = os.path.join(OUT, f"{rec['day']}.json")
        age_h = (datetime.now(timezone.utc) - pd.Timestamp(rec["close_ts"], unit="s", tz="UTC")).total_seconds() / 3600
        if not os.path.exists(p) and done < MAX_DAYS and age_h >= SETTLE_H:
            a = audit_day(rec, prior)
            json.dump(a, open(p, "w"), indent=1)
            done += 1
            print(f"news audit {rec['day']}: {a['n_checked']} articles checked live; never checked: {a['n_late']} served "
                  f"after the check, {a['n_capped']} cut by the {CAP}-article cap")
        for i, k in rec["lots"].items():                 # the next window starts where this check ended
            if k.get("news_until"):
                u, h = prior.get(i, (None, set()))
                prior[i] = (k["news_until"], h | set(k.get("headlines") or []))
    A = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(OUT, "20*.json")))]
    lags = [m["lag_lb_min"] for a in A for L in a["lots"].values() for m in L.get("missed", []) if m.get("kind", "late") == "late"]
    summ = {"days": len(A), "checked": sum(a["n_checked"] for a in A), "missed": sum(a["n_missed"] for a in A),
            "late": sum(a.get("n_late", 0) for a in A), "capped": sum(a.get("n_capped", 0) for a in A),
            "lag_lb_min_quantiles": {q: float(pd.Series(lags).quantile(q)) for q in (0.5, 0.9, 0.95)} if lags else {}}
    json.dump(summ, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    print(f"news audit: {summ['days']} days, {summ['checked']} checked live; never checked: {summ['late']} served late, "
          f"{summ['capped']} cut by the cap; late-serving lag lower bound quantiles (min) {summ['lag_lb_min_quantiles']}")


if __name__ == "__main__":
    main()
