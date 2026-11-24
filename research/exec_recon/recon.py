"""Execution reconciliation of the paper account: orders, fills, timestamps, realised costs and the ledger.

    python3 research/exec_recon/recon.py <fund_data_export> <broker_dir> <history_dir> <out_dir>

<fund_data_export>: a copy of origin/fund-data's fund_state/ (git show, read only).
<broker_dir>: the read-only Alpaca snapshot written by fetch_broker.py.
<history_dir>: every committed version of the order-bearing records (git show <commit>:<path>).
Writes RESULT.json and fills_recon.csv to <out_dir>. Reads nothing else and changes no record.
"""

import glob
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

FD, BR, HIST, OUT = (os.path.abspath(a) for a in sys.argv[1:5])
LIVE = os.path.join(FD, "fund_state", "live")
NY = "America/New_York"
R = {}                                                  # RESULT.json


def jl(p):
    return json.load(open(p))


def q(x, ps=(50, 90)):
    x = pd.Series(x).dropna()
    if not len(x):
        return None
    return {"n": int(len(x)), "mean": round(float(x.mean()), 3), **{f"p{p}": round(float(np.percentile(x, p)), 3) for p in ps},
            "min": round(float(x.min()), 3), "max": round(float(x.max()), 3)}


# ------------------------------------------------------------------ calendar: session close of every day
cal = {c["date"]: pd.Timestamp(f"{c['date']} {c['close']}").tz_localize(NY).tz_convert("UTC") for c in jl(f"{BR}/calendar.json")}
sessions = sorted(cal)

# ------------------------------------------------------------------ the fund's records: every planned order
recs = [("execution", p) for p in glob.glob(f"{LIVE}/20*/execution.json")]
recs += [("review", p) for p in glob.glob(f"{LIVE}/20*/reviews/20*.json")]
recs += [("lifecycle", p) for p in glob.glob(f"{LIVE}/lifecycle/live/20*.json") if not p.endswith(".plan.json")]
plan_rows, rec_meta = [], []
for kind, p in sorted(recs, key=lambda x: x[1]):
    r = jl(p)
    day = r.get("exec_day") if kind == "execution" else r.get("day")
    rec_meta.append({"kind": kind, "path": os.path.relpath(p, FD), "day": day, "status": r.get("status"),
                     "n_orders": len(r.get("orders", [])), "reconciled": bool(r.get("reconciled")),
                     "equity": r.get("equity"), "rec_equity": (r.get("reconciled") or {}).get("equity"),
                     "rec_at": (r.get("reconciled") or {}).get("at"), "tracking_gross": (r.get("reconciled") or {}).get("tracking_gross"),
                     "decided_at": r.get("decided_at"), "submitted_at": r.get("submitted_at") or r.get("submitted_at_et"),
                     "nav_model": r.get("nav_model"), "halt": r.get("halt"),
                     "gross_target": sum(abs(v) for v in (r.get("target_weights") or {}).values())})
    for o in r.get("orders", []):
        plan_rows.append({"kind": kind, "record": os.path.relpath(p, FD), "day": day, "rec_status": r.get("status"),
                          "symbol": o["symbol"], "leg": o["leg"], "side": o["side"], "qty": float(o["qty"]),
                          "cid": o["client_order_id"], "attempts": o.get("attempts") or [], "ids": o.get("ids") or ([o["id"]] if o.get("id") else []),
                          "rec_order_status": o.get("status"), "rec_filled_qty": o.get("filled_qty"), "rec_fill": o.get("fill_price"),
                          "target_weight": o.get("target_weight"), "price_ref": o.get("price_ref"), "equity": r.get("equity"),
                          "cur_qty": float((r.get("current_qty") or {}).get(o["symbol"], 0)),
                          "quote": o.get("quote_at_send") or {}})
for row in (pd.read_csv(f"{LIVE}/execution/tests.csv", dtype=str).to_dict("records") if os.path.exists(f"{LIVE}/execution/tests.csv") else []):
    plan_rows.append({"kind": "test", "record": "execution/tests.csv", "day": row["day"], "rec_status": "submitted", "symbol": row["symbol"],
                      "leg": "test", "side": row["side"], "qty": float(row["qty"]), "cid": row["client_order_id"], "attempts": [],
                      "ids": row["ids"].split(), "rec_order_status": row["status"], "rec_filled_qty": float(row["filled_qty"]),
                      "rec_fill": float(row["fill"]), "target_weight": None, "price_ref": None, "equity": None, "cur_qty": np.nan, "quote": {}})
P = pd.DataFrame(plan_rows)
M = pd.DataFrame(rec_meta)

# ------------------------------------------------------------------ the broker: orders and executions
BO = pd.DataFrame(jl(f"{BR}/orders.json"))
for c in ("qty", "filled_qty", "filled_avg_price"):
    BO[c] = pd.to_numeric(BO[c], errors="coerce")
for c in ("submitted_at", "filled_at", "created_at", "canceled_at", "expired_at", "updated_at"):
    BO[c] = pd.to_datetime(BO[c], utc=True, errors="coerce")
BO["day"] = BO["submitted_at"].dt.tz_convert(NY).dt.date.astype(str)
FA = pd.DataFrame(jl(f"{BR}/fills.json"))
FA["qty"], FA["price"] = pd.to_numeric(FA["qty"]), pd.to_numeric(FA["price"])
FA["t"] = pd.to_datetime(FA["transaction_time"], utc=True)
FA["sgn"] = np.where(FA["side"].isin(["buy"]), 1, -1)            # buy | sell | sell_short
ACT = pd.DataFrame(jl(f"{BR}/activities.json"))

# 1. completeness ---------------------------------------------------
by_id = BO.set_index("id")
by_cid = BO.set_index("client_order_id")


def broker_orders_of(row):
    ids = set(row["ids"])
    cids = set(row["attempts"]) | {row["cid"]}
    hit = BO[BO["id"].isin(ids) | BO["client_order_id"].isin(cids) | BO["client_order_id"].str.startswith(row["cid"] + "-a")]
    return hit


P["n_broker"] = 0
P["broker_status"] = None
P["b_filled_qty"] = np.nan
P["b_vwap"] = np.nan
for c in ("b_first_submit", "b_last_fill", "b_first_fill"):
    P[c] = pd.Series(pd.NaT, index=P.index, dtype="datetime64[ns, UTC]")
P["b_type"] = None
P["ids_match"] = None
P["fa_qty"] = np.nan
P["fa_vwap"] = np.nan
P["n_exec"] = 0
matched_ids = set()
for i, row in P.iterrows():
    h = broker_orders_of(row)
    matched_ids |= set(h["id"])
    P.at[i, "n_broker"] = len(h)
    if not len(h):
        continue
    P.at[i, "broker_status"] = "+".join(sorted(set(h["status"])))
    P.at[i, "b_type"] = "+".join(sorted(set(h["type"] + "/" + h["time_in_force"])))
    fq = h["filled_qty"].fillna(0).sum()
    P.at[i, "b_filled_qty"] = fq
    P.at[i, "b_vwap"] = (h["filled_qty"].fillna(0) * h["filled_avg_price"].fillna(0)).sum() / fq if fq else np.nan
    P.at[i, "b_first_submit"] = h["submitted_at"].min()
    P.at[i, "b_last_fill"] = h["filled_at"].max()
    P.at[i, "ids_match"] = set(row["ids"]) == set(h["id"]) if row["ids"] else None
    fa = FA[FA["order_id"].isin(h["id"])]
    P.at[i, "n_exec"] = len(fa)
    if len(fa):
        P.at[i, "fa_qty"] = fa["qty"].sum()
        P.at[i, "fa_vwap"] = (fa["qty"] * fa["price"]).sum() / fa["qty"].sum()
        P.at[i, "b_first_fill"] = fa["t"].min()
orphans = BO[~BO["id"].isin(matched_ids)]

# the fund's fill ledger (fills.csv) against the plan
FC = pd.read_csv(f"{LIVE}/execution/fills.csv", dtype={"asof": str, "exec_day": str})
FC["key"] = FC["exec_day"] + "|" + FC["source"] + "|" + FC["symbol"] + "|" + FC["leg"] + "|" + FC["side"]
P["key"] = P["day"].astype(str) + "|" + P["kind"] + "|" + P["symbol"] + "|" + P["leg"] + "|" + P["side"]
dup_fc = FC[FC.duplicated("key", keep=False)]
P = P.merge(FC.drop_duplicates("key").set_index("key")[["status", "filled_qty", "fill", "filled_at", "close", "slip_bp", "close_alpaca"]]
            .add_prefix("fc_"), left_on="key", right_index=True, how="left")
plan_trade = P[P["kind"] != "test"]
no_fc = plan_trade[plan_trade["fc_status"].isna()]
fc_not_plan = FC[~FC["key"].isin(P["key"])]

comp = {
    "records": {k: int(v) for k, v in M.groupby("kind").size().items()},
    "records_with_orders": int((M["n_orders"] > 0).sum()),
    "records_status": {f"{k}": int(v) for k, v in Counter(M["status"].fillna("none")).items()},
    "planned_orders": int(len(plan_trade)), "pipeline_test_orders": int((P["kind"] == "test").sum()),
    "planned_with_broker_order": int((plan_trade["n_broker"] > 0).sum()),
    "planned_without_broker_order": plan_trade.loc[plan_trade["n_broker"] == 0, ["day", "symbol", "leg", "qty"]].to_dict("records"),
    "attempts_per_order": {str(k): int(v) for k, v in Counter(plan_trade["n_broker"]).items()},
    "broker_orders": int(len(BO)), "broker_orders_matched_to_plan": int(len(matched_ids)),
    "broker_orders_not_in_any_record": orphans[["client_order_id", "symbol", "status", "day"]].to_dict("records"),
    "broker_terminal_states": {f"{a}/{b}": int(v) for (a, b), v in BO.groupby(["status", "type"]).size().items()},
    "broker_non_terminal": int((~BO["status"].isin(["filled", "canceled", "expired", "rejected"])).sum()),
    "record_ids_equal_broker_ids": int((plan_trade["ids_match"] == True).sum()),  # noqa: E712
    "record_ids_differ": plan_trade.loc[plan_trade["ids_match"] == False, ["day", "symbol"]].to_dict("records"),  # noqa: E712
    "planned_without_fills_csv_row": no_fc.groupby("day").size().astype(int).to_dict(),
    "fills_csv_rows_without_plan": fc_not_plan[["exec_day", "source", "symbol", "leg"]].to_dict("records"),
    "fills_csv_duplicate_keys": int(len(dup_fc)),
    "fills_csv_rows": int(len(FC)),
    "fill_activities": int(len(FA)), "fill_activities_unmatched": int((~FA["order_id"].isin(BO["id"])).sum()),
}
# per-day matrix: planned, sent, broker terminal, fills.csv rows
pd_day = []
for d in sorted(set(plan_trade["day"]) | set(BO["day"])):
    a = plan_trade[plan_trade["day"] == d]
    b = BO[BO["day"] == d]
    pd_day.append({"day": d, "planned": int(len(a)), "sent": int((a["n_broker"] > 0).sum()), "broker_orders": int(len(b)),
                   "broker_filled": int((b["status"] == "filled").sum()), "broker_expired": int((b["status"] == "expired").sum()),
                   "broker_other": int((~b["status"].isin(["filled", "expired"])).sum()),
                   "fills_csv_rows": int(len(FC[FC["exec_day"] == d])),
                   "planned_unsent": int((a["n_broker"] == 0).sum()), "broker_unplanned": int(len(orphans[orphans["day"] == d]))})
comp["by_day"] = pd_day
R["1_completeness"] = comp

# record versions: did any order of a record change between its committed versions?
ver = defaultdict(list)
for p in sorted(glob.glob(f"{HIST}/*.json")):
    base = os.path.basename(p).rsplit("_", 1)[0]
    try:
        ver[base].append(jl(p))
    except ValueError:
        continue
changed = []
for base, vs in ver.items():
    sig = {json.dumps([(o["symbol"], o["leg"], o["side"], o["qty"], o.get("filled_qty"), o.get("fill_price")) for o in v.get("orders", [])]) for v in vs}
    if len(sig) > 1:
        changed.append(base)
R["1_completeness"]["record_versions"] = {"records": len(ver), "versions": int(sum(len(v) for v in ver.values())),
                                         "records_whose_orders_changed_between_versions": changed}

# 2. quantities, sides, positions ---------------------------------------
tr = plan_trade[plan_trade["n_broker"] > 0].copy()
tr["b_side"] = tr.apply(lambda r: "+".join(sorted(set(broker_orders_of(r)["side"]))), axis=1)
qty_checks = {
    "side_mismatch_plan_vs_broker": tr.loc[tr["b_side"] != tr["side"], ["day", "symbol", "side", "b_side"]].to_dict("records"),
    "broker_filled_ne_planned_qty": tr.loc[(tr["b_filled_qty"] - tr["qty"]).abs() > 1e-9, ["day", "symbol", "leg", "qty", "b_filled_qty", "broker_status"]].to_dict("records"),
    "record_filled_ne_broker": tr.loc[(pd.to_numeric(tr["rec_filled_qty"], errors="coerce").fillna(-1) - tr["b_filled_qty"]).abs() > 1e-9,
                                      ["day", "symbol", "rec_filled_qty", "b_filled_qty", "rec_order_status"]].to_dict("records"),
    "fills_csv_qty_ne_broker": tr.loc[(tr["fc_filled_qty"] - tr["b_filled_qty"]).abs() > 1e-9, ["day", "symbol", "fc_filled_qty", "b_filled_qty"]].to_dict("records"),
    "fills_csv_price_ne_broker_vwap_cents": int(((tr["fc_fill"] - tr["b_vwap"]).abs() > 0.005).sum()),
    "fills_csv_price_max_abs_diff": float((tr["fc_fill"] - tr["b_vwap"]).abs().max()),
    "executions_qty_ne_order_filled_qty": int(((tr["fa_qty"].fillna(0) - tr["b_filled_qty"]).abs() > 1e-9).sum()),
    "executions_vwap_ne_order_avg_cents": int(((tr["fa_vwap"] - tr["b_vwap"]).abs() > 0.005).sum()),
    "orders_with_multiple_executions": int((tr["n_exec"] > 1).sum()),
    # the order list gives microseconds, the single-order call nanoseconds: compare to 1 ms
    "fills_csv_filled_at_ne_broker_gt_1ms": int(((pd.to_datetime(tr["fc_filled_at"], utc=True, errors="coerce", format="ISO8601") - tr["b_last_fill"])
                                                 .dt.total_seconds().abs() > 1e-3).sum()),
    "fills_csv_filled_at_compared": int(tr["fc_filled_at"].notna().sum()),
}
# sizing: the planned quantity against the record's own target weight, equity, reference price and holding
lc = tr[tr["kind"] == "lifecycle"].copy()


def size_err(g):
    r0 = g.iloc[0]
    tq = int(round((r0["target_weight"] or 0) * r0["equity"] / r0["price_ref"])) if r0["price_ref"] else 0
    sgn = {"buy": 1, "sell": -1}
    traded = sum(sgn[x["side"]] * x["qty"] for _, x in g.iterrows())
    return tq - (r0["cur_qty"] + traded)


sz = lc.groupby(["day", "symbol"]).apply(size_err)
qty_checks["sizing_residual_shares"] = {"n": int(len(sz)), "nonzero": int((sz.abs() > 0).sum()),
                                        "nonzero_cases": [{"day": d, "symbol": s, "shares": float(v)} for (d, s), v in sz[sz.abs() > 0].items()][:20]}

# positions: cumulate every execution; compare with the holding each record saw before it traded
FA = FA.sort_values("t")
FA["day"] = FA["t"].dt.tz_convert(NY).dt.date.astype(str)
pos_after = {}                                          # day -> {symbol: qty} after that session's executions
run = defaultdict(float)
for d in sessions:
    for _, x in FA[FA["day"] == d].iterrows():
        run[x["symbol"]] += x["sgn"] * x["qty"]
    pos_after[d] = {k: v for k, v in run.items() if abs(v) > 1e-9}
pos_mis = []
for kind, p in sorted(recs, key=lambda x: x[1]):
    r = jl(p)
    if r.get("status") != "submitted" or "current_qty" not in r:
        continue
    day = r.get("exec_day") if kind == "execution" else r.get("day")
    prev = max([s for s in sessions if s < day], default=None)
    exp = pos_after.get(prev, {})
    # same-day earlier records (a review on the execution day) traded before this one: include today's earlier fills
    seen = {k: float(v) for k, v in r["current_qty"].items()}
    t_dec = pd.Timestamp(r.get("sized_at_et") or r.get("decided_at") or r.get("planned_at_et") or f"{day} 15:57").tz_convert("UTC") \
        if (r.get("sized_at_et") or r.get("decided_at") or r.get("planned_at_et")) else cal[day] - pd.Timedelta(minutes=3)
    e2 = dict(exp)
    for _, x in FA[(FA["day"] == day) & (FA["t"] < t_dec)].iterrows():
        e2[x["symbol"]] = e2.get(x["symbol"], 0) + x["sgn"] * x["qty"]
    e2 = {k: v for k, v in e2.items() if abs(v) > 1e-9}
    diff = {k: (seen.get(k, 0), e2.get(k, 0)) for k in set(seen) | set(e2) if abs(seen.get(k, 0) - e2.get(k, 0)) > 1e-9}
    if diff:
        pos_mis.append({"record": os.path.relpath(p, FD), "day": day, "diff_record_vs_fills": diff})
qty_checks["positions_seen_by_records_vs_cumulated_fills"] = {"records_checked": int(sum(1 for k, p in recs if jl(p).get("status") == "submitted")),
                                                             "mismatches": pos_mis}
now_pos = {x["symbol"]: (-1 if x["side"] == "short" else 1) * abs(float(x["qty"])) for x in jl(f"{BR}/positions.json")}
qty_checks["broker_positions_now"] = now_pos
qty_checks["cumulated_fills_now"] = {k: v for k, v in run.items() if abs(v) > 1e-9}
R["2_quantities"] = qty_checks

# 3. timestamps -------------------------------------------------------
tr["close_utc"] = tr["day"].map(cal)
tr["submit_s_before_close"] = (tr["close_utc"] - tr["b_first_submit"]).dt.total_seconds()
tr["fill_s_vs_close"] = (tr["b_last_fill"] - tr["close_utc"]).dt.total_seconds()
tr["first_fill_s_vs_close"] = (tr["b_first_fill"] - tr["close_utc"]).dt.total_seconds()
tr["latency_s"] = (tr["b_first_fill"] - tr["b_first_submit"]).dt.total_seconds()
pre = tr[tr["b_type"] == "market/day"]
open_utc = {d: pd.Timestamp(f"{c['date']} {c['open']}").tz_localize(NY).tz_convert("UTC") for c in jl(f"{BR}/calendar.json") for d in [c["date"]]}
FA["close_utc"] = FA["day"].map(cal)
FA["open_utc"] = FA["day"].map(open_utc)
outside = FA[(FA["t"] > FA["close_utc"]) | (FA["t"] < FA["open_utc"])]
dec = M[M["kind"] == "lifecycle"].copy()
dec["decided_s_before_close"] = (dec["day"].map(cal) - pd.to_datetime(dec["decided_at"], utc=True)).dt.total_seconds()
dec["record_submitted_s_after_close"] = (pd.to_datetime(dec["submitted_at"], utc=True) - dec["day"].map(cal)).dt.total_seconds()
R["3_timestamps"] = {
    "preclose_orders": int(len(pre)),
    "submit_seconds_before_close": q(pre["submit_s_before_close"], (5, 50, 95)),
    "submit_seconds_before_close_by_leg": {k: q(g["submit_s_before_close"], (50,)) for k, g in pre.groupby("leg")},
    "submit_outside_55_90s_window": pre.loc[(pre["submit_s_before_close"] < 55) | (pre["submit_s_before_close"] > 90), ["day", "symbol", "leg", "submit_s_before_close"]].to_dict("records"),
    "first_fill_latency_s": q(pre["latency_s"], (50, 90, 99)),
    "last_fill_seconds_vs_close": q(pre["fill_s_vs_close"], (5, 50, 95)),
    "fills_after_close": int((pre["fill_s_vs_close"] > 0).sum()),
    "executions_outside_regular_session": outside[["day", "symbol", "transaction_time", "qty"]].to_dict("records"),
    "executions_total": int(len(FA)),
    "moc_orders_2026_10_01": {"n": int((tr["b_type"] == "market/cls").sum()),
                              "submit_seconds_before_close": q(tr.loc[tr["b_type"] == "market/cls", "submit_s_before_close"], (50,)),
                              "partial_fill_times_s_vs_close": q(tr.loc[tr["b_type"] == "market/cls", "first_fill_s_vs_close"], (50,))},
    "decision_seconds_before_close": q(dec.loc[dec["n_orders"] > 0, "decided_s_before_close"], (5, 50, 95)),
    "record_submitted_seconds_after_close": q(dec["record_submitted_s_after_close"], (50, 95)),
}

# 4. realised costs ---------------------------------------------------
DB = jl(f"{BR}/daily_bars.json")
sip = {(s, pd.Timestamp(b["t"]).tz_convert(NY).date().isoformat()): b for s, bs in DB.items() for b in bs}
MB = jl(f"{BR}/minute_bars.json")


def minute(d, s, hhmm):
    for b in MB.get(d, {}).get(s, []):
        if pd.Timestamp(b["t"]).tz_convert(NY).strftime("%H:%M") == hhmm:
            return b
    return None


def adv(s, d, n=20):
    xs = sorted((k[1], b) for k, b in sip.items() if k[0] == s and k[1] < d)[-n:]
    return float(np.mean([b["c"] * b["v"] for _, b in xs])) if xs else np.nan


f = tr[tr["b_filled_qty"] > 0].copy()
f["sgn"] = np.where(f["side"] == "buy", 1, -1)
f["notional"] = f["b_filled_qty"] * f["b_vwap"]
f["close_yf"] = f["fc_close"]
f["close_sip"] = [sip.get((s, d), {}).get("c", np.nan) for s, d in zip(f["symbol"], f["day"])]
f["slip_yf_bp"] = f["sgn"] * (f["b_vwap"] / f["close_yf"] - 1) * 1e4
f["slip_sip_bp"] = f["sgn"] * (f["b_vwap"] / f["close_sip"] - 1) * 1e4
f["yf_vs_sip_bp"] = (f["close_yf"] / f["close_sip"] - 1) * 1e4
f["recorded_slip_bp"] = f["fc_slip_bp"]
sub_min = f["b_first_submit"].dt.tz_convert(NY).dt.strftime("%H:%M")
f["arr_px"] = [((minute(d, s, m) or {}).get("o", np.nan)) for d, s, m in zip(f["day"], f["symbol"], sub_min)]
f["arr_bp"] = f["sgn"] * (f["b_vwap"] / f["arr_px"] - 1) * 1e4          # fill against the SIP price at the send minute
f["drift_bp"] = f["sgn"] * (f["close_sip"] / f["arr_px"] - 1) * 1e4     # send minute to the official close
qmid = [((x.get("bid") or np.nan) + (x.get("ask") or np.nan)) / 2 if isinstance(x, dict) and x.get("bid") and x.get("ask") else np.nan for x in f["quote"]]
f["iex_mid"] = qmid
f["iex_spread_bp"] = [((x["ask"] - x["bid"]) / ((x["ask"] + x["bid"]) / 2) * 1e4) if isinstance(x, dict) and x.get("bid") and x.get("ask") else np.nan for x in f["quote"]]
f["adv_usd"] = [adv(s, d) for s, d in zip(f["symbol"], f["day"])]
f["participation"] = f["notional"] / f["adv_usd"]
stocks = f["symbol"] != "SPY"
terc = f.loc[stocks, "adv_usd"].quantile([1 / 3, 2 / 3]).to_numpy()
f["liq"] = np.where(~stocks, "SPY", np.where(f["adv_usd"] <= terc[0], "stock ADV low tercile",
                                            np.where(f["adv_usd"] <= terc[1], "stock ADV mid tercile", "stock ADV high tercile")))
f["regime"] = np.where(f["day"] < "2026-10-15", "weekly book and reviews (10-01..10-14)",
                       np.where(f["day"] < "2026-11-16", "per-trade lifecycle book (10-15..11-13)", "SPY core + book (11-16..)"))
f["reconciled_by_fund"] = f["fc_status"].notna()
f["cost_usd_sip"] = f["slip_sip_bp"] / 1e4 * f["notional"]
f["cost_usd_yf"] = f["slip_yf_bp"] / 1e4 * f["notional"]
f["cost_usd_arr"] = f["arr_bp"] / 1e4 * f["notional"]


def stats(g, col):
    x = g[col].dropna()
    if not len(x):
        return None
    w = g.loc[x.index, "notional"]
    return {"n": int(len(x)), "mean": round(float(x.mean()), 2), "median": round(float(x.median()), 2),
            "p90": round(float(np.percentile(x, 90)), 2), "p10": round(float(np.percentile(x, 10)), 2),
            "notional_weighted_mean": round(float((x * w).sum() / w.sum()), 2),
            "mean_abs": round(float(x.abs().mean()), 2), "se_mean": round(float(x.std(ddof=1) / np.sqrt(len(x))), 2) if len(x) > 1 else None}


mk = f[f["b_type"] == "market/day"]
cost = {"orders_with_fills": int(len(f)), "preclose_market_orders": int(len(mk)),
        "close_sip_available": int(mk["close_sip"].notna().sum()), "arrival_minute_available": int(mk["arr_px"].notna().sum()),
        "close_alpaca_recorded_in_fills_csv": int(FC["close_alpaca"].notna().sum()),
        "yfinance_vs_sip_close_bp": stats(mk.assign(notional=mk["notional"]), "yf_vs_sip_bp"),
        "yfinance_vs_sip_close_abs_gt_1bp": mk.loc[mk["yf_vs_sip_bp"].abs() > 1, ["day", "symbol", "close_yf", "close_sip", "yf_vs_sip_bp"]].round(3).to_dict("records"),
        "recorded_slip_minus_recomputed_bp_max": float((mk["recorded_slip_bp"] - mk["slip_yf_bp"]).abs().max()),
        "all": {c: stats(mk, c) for c in ("slip_yf_bp", "slip_sip_bp", "arr_bp", "drift_bp", "iex_spread_bp")}}
for by in ("side", "leg", "liq", "regime", "b_type"):
    cost[f"by_{by}"] = {str(k): {c: stats(g, c) for c in ("slip_sip_bp", "slip_yf_bp", "arr_bp")} for k, g in f.groupby(by)}
cost["participation_of_adv"] = q(mk["participation"] * 1e4, (50, 90, 99))     # in bp of 20-day ADV
cost["adv_tercile_bounds_usd"] = [float(t) for t in terc]
cost["worst_10_vs_sip_close"] = mk.nlargest(10, "slip_sip_bp")[["day", "symbol", "side", "leg", "b_filled_qty", "b_vwap", "close_sip", "slip_sip_bp", "arr_bp", "iex_spread_bp"]].round(3).to_dict("records")

# %/yr of NAV: realised cost dollars over the mean broker equity, annualised on the sessions covered
HB = jl(f"{BR}/history_3m.json")
H = pd.DataFrame({"t": pd.to_datetime(HB["timestamp"], unit="s", utc=True), "equity": HB["equity"]})
H["session"] = H["t"].dt.tz_convert(NY).dt.date.astype(str)
H = H[H["session"].isin(sessions)]
span = [s for s in sessions if mk["day"].min() <= s <= mk["day"].max()]
eq_mean = float(H[H["session"].isin(span)]["equity"].mean())
ann = 252 / len(span)


def per_year(g, col):
    return round(float(g[col].sum() / eq_mean * ann * 100), 3)


turn = float(mk["notional"].sum() / eq_mean * ann)
cost["annualised"] = {"sessions_covered": len(span), "first": span[0], "last": span[-1], "mean_broker_equity": round(eq_mean, 2),
                      "traded_notional_usd": round(float(mk["notional"].sum()), 2), "turnover_x_per_year": round(turn, 2),
                      "cost_pct_nav_per_year_vs_sip_close": per_year(mk, "cost_usd_sip"),
                      "cost_pct_nav_per_year_vs_yf_close": per_year(mk, "cost_usd_yf"),
                      "cost_pct_nav_per_year_vs_arrival": per_year(mk, "cost_usd_arr"),
                      "model_assumption_5bp_pct_nav_per_year": round(5e-4 * turn * 100, 3),
                      "fees_usd": round(float(pd.to_numeric(ACT.loc[ACT["activity_type"] == "FEE", "net_amount"]).sum()), 2),
                      "fees_pct_nav_per_year": round(float(pd.to_numeric(ACT.loc[ACT["activity_type"] == "FEE", "net_amount"]).sum()) / eq_mean * ann * -100, 4)}
for reg, g in mk.groupby("regime"):
    sp = [s for s in sessions if g["day"].min() <= s <= g["day"].max()]
    e = float(H[H["session"].isin(sp)]["equity"].mean())
    cost["annualised"][f"regime: {reg}"] = {"sessions": len(sp), "turnover_x_per_year": round(float(g["notional"].sum() / e * 252 / len(sp)), 2),
                                            "cost_pct_nav_per_year_vs_sip_close": round(float(g["cost_usd_sip"].sum() / e * 252 / len(sp) * 100), 3),
                                            "notional_weighted_bp_vs_sip": round(float(g["cost_usd_sip"].sum() / g["notional"].sum() * 1e4), 2)}
cost["not_yet_reconciled_by_fund"] = {"orders": int((~mk["reconciled_by_fund"]).sum()), "days": sorted(set(mk.loc[~mk["reconciled_by_fund"], "day"]))}
R["4_costs"] = cost

# 5. ledger -------------------------------------------------------------
# rebuild cash and holdings from executions, fees and dividends; mark at the SIP close; compare with the broker
cash, hold, rows = 100000.0, defaultdict(float), []
FEE = ACT[ACT["activity_type"] != "FILL"].copy()
FEE["amount"] = pd.to_numeric(FEE["net_amount"])
nav_csv = pd.read_csv(f"{LIVE}/execution/nav.csv", dtype={"date": str})
for d in [s for s in sessions if s >= "2026-10-01" and s <= H["session"].max()]:
    for _, x in FA[FA["day"] == d].iterrows():
        cash -= x["sgn"] * x["qty"] * x["price"]
        hold[x["symbol"]] += x["sgn"] * x["qty"]
    cash += float(FEE.loc[FEE["date"] == d, "amount"].sum())
    mv = sum(v * sip.get((k, d), {}).get("c", np.nan) for k, v in hold.items() if abs(v) > 1e-9)
    gl = sum(abs(v) * sip.get((k, d), {}).get("c", np.nan) for k, v in hold.items() if abs(v) > 1e-9)
    beq = H.loc[H["session"] == d, "equity"]
    rec = M[(M["day"] == d) & M["rec_equity"].notna()]
    rows.append({"session": d, "cash_rebuilt": round(cash, 2), "positions_mv": round(mv, 2), "gross_x": round(gl / (cash + mv), 3),
                 "equity_rebuilt": round(cash + mv, 2), "equity_broker_history": float(beq.iloc[0]) if len(beq) else None,
                 "nav_csv_same_label": (nav_csv.loc[nav_csv["date"] == d, "equity"].tolist() or [None])[0],
                 "reconcile_equity": (rec["rec_equity"].tolist() or [None])[-1], "reconcile_at": (rec["rec_at"].tolist() or [None])[-1]})
L = pd.DataFrame(rows)
L["rebuilt_minus_broker"] = L["equity_rebuilt"] - L["equity_broker_history"]
L["reconcile_minus_broker"] = L["reconcile_equity"] - L["equity_broker_history"]
# nav.csv: each value against the broker session it belongs to (label = session date + 1 calendar day?)
lab = {}
for _, x in H.iterrows():
    lab[x["t"].date().isoformat()] = x["session"]
nc = nav_csv[nav_csv["date"] >= "2026-09-28"].copy()
nc["broker_session_of_label"] = nc["date"].map(lab)
nc["label_is_session"] = nc["date"] == nc["broker_session_of_label"]
# the halt as each nightly reconcile saw it, and as it would have been with the session just closed
he = H[H["equity"] > 0].reset_index(drop=True)
halt_rows = []
for k in range(len(he)):
    e = he["equity"].to_numpy()[:k + 1]
    halt_rows.append({"session": he.at[k, "session"], "equity": float(e[-1]), "drawdown": round(float(1 - e[-1] / e.max()), 4),
                      "week": round(float(e[-1] / e[max(0, len(e) - 6)] - 1), 4) if len(e) > 1 else 0.0})
HR = pd.DataFrame(halt_rows)
HR["trips"] = (HR["drawdown"] >= 0.10) | (HR["week"] <= -0.05)
first_trip = HR[HR["trips"]].head(1).to_dict("records")
halt_file = open(f"{LIVE}/HALT").read().strip() if os.path.exists(f"{LIVE}/HALT") else None
# model NAV vs broker equity: daily returns while the account mirrored the model book (10-15..11-13)
st = jl(f"{LIVE}/lifecycle/state.json")
MN = pd.DataFrame(st["rows"])[["date", "nav", "cost", "stock_gross", "hedge"]].rename(columns={"date": "session", "nav": "nav_model"})
J = L.merge(MN, on="session", how="left")
J["r_broker"] = J["equity_broker_history"].pct_change()
J["r_model"] = J["nav_model"].pct_change()
J["r_diff_bp"] = (J["r_broker"] - J["r_model"]) * 1e4
mir = J[(J["session"] > "2026-10-15") & (J["session"] <= "2026-11-13")]
# decomposition of broker minus model while the account mirrored the book: the model's cash income and 5 bp cost,
# the realised execution cost against the close; the rest is share rounding and sizing on intraday equity
MS = pd.DataFrame(st["rows"]).set_index("date")
cday = f.groupby("day")["cost_usd_sip"].sum()
dec_rows = []
for s in mir["session"]:
    e0 = float(J.loc[J["session"] < s, "equity_broker_history"].iloc[-1])
    dec_rows.append({"session": s, "diff_bp": float(mir.loc[mir["session"] == s, "r_diff_bp"].iloc[0]),
                     "model_cash_bp": float(MS.at[s, "r_cash"]) * 1e4, "model_cost_bp": float(MS.at[s, "r_cost"]) * 1e4,
                     "realised_cost_bp": float(cday.get(s, 0.0)) / e0 * 1e4})
DD = pd.DataFrame(dec_rows)
DD["unexplained_bp"] = DD["diff_bp"] + DD["model_cash_bp"] - DD["model_cost_bp"] + DD["realised_cost_bp"]
mirror_decomp = {k: round(float(DD[k].sum()), 2) for k in ("diff_bp", "model_cash_bp", "model_cost_bp", "realised_cost_bp", "unexplained_bp")}
mirror_decomp["unexplained_daily_bp"] = q(DD["unexplained_bp"], (10, 50, 90))
# the SPY core sessions: the account's return against its design, core_w x r_SPY + lambda x (model book return without
# its cash income), the weights decided for that session (lifecycle/live/<day>.json: p9)
spy_c = {d: sip[("SPY", d)]["c"] for d in sessions if ("SPY", d) in sip}
p9_rows = []
for s in [x for x in sessions if "2026-11-17" <= x <= H["session"].max()]:
    prev = max(x for x in sessions if x < s)
    pr = jl(f"{LIVE}/lifecycle/live/{prev}.json").get("p9") or {}
    if not pr or s not in MS.index or prev not in MS.index:
        continue
    r_spy = spy_c[s] / spy_c[prev] - 1
    r_book = (MS.at[s, "nav"] - MS.at[s, "cash_income"] + MS.at[s, "cost"]) / MS.at[prev, "nav"] - 1   # gross of the model's cash and cost
    r_acct = float(J.loc[J["session"] == s, "r_broker"].iloc[0])
    held = jl(f"{LIVE}/lifecycle/live/{prev}.json")
    p9_rows.append({"session": s, "core_w": pr["core_w"], "overlay_k": pr["overlay_k"], "r_spy_pct": round(r_spy * 100, 3),
                    "r_book_gross_pct": round(r_book * 100, 3), "r_design_pct": round((pr["core_w"] * r_spy + pr["overlay_k"] * r_book) * 100, 3),
                    "r_account_pct": round(r_acct * 100, 3)})
P9R = pd.DataFrame(p9_rows)
if len(P9R):
    P9R["diff_bp"] = (P9R["r_account_pct"] - P9R["r_design_pct"]) * 100
R["5_ledger"] = {
    "sessions": int(len(L)),
    "rebuilt_minus_broker_usd": q(L["rebuilt_minus_broker"], (5, 50, 95)),
    "rebuilt_minus_broker_abs_gt_5usd": L.loc[L["rebuilt_minus_broker"].abs() > 5, ["session", "equity_rebuilt", "equity_broker_history", "rebuilt_minus_broker"]].round(2).to_dict("records"),
    "reconcile_equity_minus_broker_close_usd": q(L["reconcile_minus_broker"], (5, 50, 95)),
    "reconcile_equity_minus_broker_close_bp": q(L["reconcile_minus_broker"] / L["equity_broker_history"] * 1e4, (5, 50, 95)),
    "min_cash_rebuilt": float(L["cash_rebuilt"].min()), "min_cash_session": L.loc[L["cash_rebuilt"].idxmin(), "session"],
    "sessions_with_negative_cash": int((L["cash_rebuilt"] < 0).sum()), "max_gross_x": float(L["gross_x"].max()),
    "interest_or_borrow_activities": int(ACT["activity_type"].isin(["INT", "INTDEB", "INTCR", "SSO", "SSP", "CFEE"]).sum()),
    "activity_types": {k: int(v) for k, v in Counter(ACT["activity_type"]).items()},
    "dividends_usd": round(float(FEE.loc[FEE["activity_type"].str.startswith("DIV"), "amount"].sum()), 2),
    "fees_usd": round(float(FEE.loc[FEE["activity_type"] == "FEE", "amount"].sum()), 2),
    "broker_equity_now": float(jl(f"{BR}/account.json")["equity"]), "broker_cash_now": float(jl(f"{BR}/account.json")["cash"]),
    "nav_csv": {"rows_since_09_28": int(len(nc)), "labels_equal_to_their_session": int(nc["label_is_session"].sum()),
                "labels_one_day_late": int((pd.to_datetime(nc["date"]) - pd.to_datetime(nc["broker_session_of_label"]) == pd.Timedelta(days=1)).sum()),
                "labels_on_weekends": int(pd.to_datetime(nc["date"]).dt.weekday.ge(5).sum()),
                "last_label": nc["date"].iloc[-1], "last_label_session": nc["broker_session_of_label"].iloc[-1]},
    "halt": {"file": halt_file, "first_session_that_trips_rule": first_trip,
             "rows": HR[HR["session"] >= "2026-11-12"].to_dict("records")},
    "model_vs_broker_daily_return_while_mirroring": {"sessions": int(len(mir)), "diff_bp": q(mir["r_diff_bp"], (10, 50, 90)),
                                                     "cumulative_broker_pct": round(float((1 + mir["r_broker"]).prod() - 1) * 100, 3),
                                                     "cumulative_model_pct": round(float((1 + mir["r_model"]).prod() - 1) * 100, 3),
                                                     "sum_of_daily_bp": mirror_decomp},
    "core_sessions_account_vs_design": P9R.to_dict("records"),
    "tracking_gross_at_reconcile": q(M.loc[M["kind"] == "lifecycle", "tracking_gross"], (50, 90)),
}
# extras: the halt-day liquidation, the cost of the one-session halt delay, SPY against stocks, logging coverage
liq = mk[mk["day"] == "2026-11-24"]
eq_by = dict(zip(L["session"], L["equity_broker_history"]))
acct_now = float(jl(f"{BR}/account.json")["equity"])
R["extras"] = {
    "halt_liquidation_2026_11_24": {"orders": int(len(liq)), "notional_usd": round(float(liq["notional"].sum()), 2),
                                    "cost_usd_vs_sip_close": round(float(liq["cost_usd_sip"].sum()), 2),
                                    "cost_usd_vs_arrival": round(float(liq["cost_usd_arr"].sum()), 2),
                                    "notional_weighted_bp_vs_sip_close": round(float(liq["cost_usd_sip"].sum() / liq["notional"].sum() * 1e4), 2)},
    "halt_delay_one_session": {"equity_2026_11_23_close": eq_by.get("2026-11-23"), "equity_after_2026_11_24_close_flat": acct_now,
                               "change_usd": round(acct_now - eq_by.get("2026-11-23", np.nan), 2),
                               "change_pct": round((acct_now / eq_by.get("2026-11-23", np.nan) - 1) * 100, 3)},
    "spy_vs_stocks": {k: {"orders": int(len(g)), "notional_usd": round(float(g["notional"].sum()), 2),
                          "notional_weighted_bp_vs_sip_close": round(float(g["cost_usd_sip"].sum() / g["notional"].sum() * 1e4), 2),
                          "notional_weighted_bp_vs_arrival": round(float(g["cost_usd_arr"].sum() / g["notional"].sum() * 1e4), 2)}
                      for k, g in mk.groupby(np.where(mk["symbol"] == "SPY", "SPY", "stocks"))},
    "total_cost_usd": {"vs_sip_close": round(float(mk["cost_usd_sip"].sum()), 2), "vs_arrival": round(float(mk["cost_usd_arr"].sum()), 2)},
    "quote_at_send_logged": {k: [int(g["iex_spread_bp"].notna().sum()), int(len(g))] for k, g in mk.groupby("regime")},
    "submit_order_effect_corr_seconds_before_close_vs_abs_drift": round(float(np.corrcoef(mk["submit_s_before_close"], (mk["slip_sip_bp"] - mk["arr_bp"]).abs())[0, 1]), 3),
    "order_notional_usd": q(mk["notional"], (50, 90)),
}
L.to_csv(os.path.join(OUT, "ledger_recon.csv"), index=False)
keep = ["kind", "day", "symbol", "leg", "side", "qty", "b_type", "broker_status", "b_filled_qty", "b_vwap", "fc_fill", "b_first_submit", "b_first_fill",
        "b_last_fill", "submit_s_before_close", "fill_s_vs_close", "close_yf", "close_sip", "arr_px", "slip_yf_bp", "slip_sip_bp", "arr_bp",
        "drift_bp", "recorded_slip_bp", "iex_spread_bp", "adv_usd", "participation", "liq", "regime", "notional", "reconciled_by_fund"]
f[keep].to_csv(os.path.join(OUT, "fills_recon.csv"), index=False)
R["inputs"] = {"fund_data_commit": open(os.path.join(FD, "REV")).read().strip() if os.path.exists(os.path.join(FD, "REV")) else None,
               "broker_snapshot": jl(f"{BR}/fetch_log.json")}
json.dump(R, open(os.path.join(OUT, "RESULT.json"), "w"), indent=1, default=str)
print(json.dumps(R, indent=1, default=str)[:200])
