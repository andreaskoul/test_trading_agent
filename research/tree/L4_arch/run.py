"""Resumable runner for Layer 4 A (one process = one worker; exits before the 2-hour job limit).

    python run.py 1 [minutes]   # stage 1 tasks (data <= 2019-12-31 only)
    python run.py 2 [minutes]   # stage 2 tasks for the gate passers in RESULT.json (needs stage 1 gate)

Each task is one fit: (variant, seed, refit year). Predictions go to .cache/tree/l4arch/pred_<task>.npz (float32),
the in-progress training state to ckpt_<task>.pt (deleted when the fit is done). The runner sleeps through the fund's
trading window (weekdays 15:30-21:15 UTC) and stops below 6 GB free disk.
"""
import fcntl
import json
import os
import sys
import time

import numpy as np
import pandas as pd

import arch as A

STATE = os.path.join(A.HERE, "STATE.json")
RESULT = os.path.join(A.HERE, "RESULT.json")
os.makedirs(A.CACHE, exist_ok=True)


def tasks(stage):
    if stage == 1:
        return [f"{v}_s{s}_y2018" for s in A.SEEDS for v in A.VARIANTS]
    res = json.load(open(RESULT))
    passers = res["stage1"]["go_on"]
    return [f"{v}_s{s}_y{y}" for y in range(2020, 2026) for v in passers for s in A.SEEDS]


def parse(t):
    v, s, y = t.split("_")
    return v, int(s[1:]), int(y[1:])


def pred_path(t):
    return os.path.join(A.CACHE, f"pred_{t}.npz")


def lock_path(t):
    return os.path.join(A.CACHE, f"lock_{t}")


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def claim(t):
    lp = lock_path(t)
    if os.path.exists(lp):
        try:
            pid = int(open(lp).read().strip() or 0)
        except ValueError:
            pid = 0
        if pid and pid_alive(pid) and pid != os.getpid():
            return False
    with open(lp, "w") as f:
        f.write(str(os.getpid()))
    return True


def update_state(fn):
    with open(STATE + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        st = json.load(open(STATE))
        fn(st)
        st["updated"] = pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        json.dump(st, open(STATE + ".tmp", "w"), indent=1)
        os.replace(STATE + ".tmp", STATE)


def main():
    stage = int(sys.argv[1])
    minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 110
    deadline = time.time() + minutes * 60
    todo = tasks(stage)
    d = None
    while time.time() < deadline:
        if A.disk_free_gb() < 4:
            A.log(f"free disk {A.disk_free_gb():.1f} GB < 4: stop")
            sys.exit(3)
        # 2026-11-19 (owner): research runs independently of the live fund; no trading-window pause (runs under nice)
        pending = [t for t in todo if not os.path.exists(pred_path(t))]
        if not pending:
            A.log("all tasks done")
            return
        t = next((t for t in pending if claim(t)), None)
        if t is None:
            A.log("every pending task is claimed by a live worker")
            return
        if d is None:
            d = A.build("2019-12-31" if stage == 1 else "2025-12-31")
            A.log(f"built: {len(d['S'])} sessions to {d['S'][-1].date()}, {len(d['names'])} names")
        v, seed, year = parse(t)
        S = d["S"]
        years = (2018, 2019) if stage == 1 else (year,)
        days = np.concatenate([A.thursdays(S, np.where(S.year == y)[0]) for y in years])
        update_state(lambda st: st["running"].__setitem__(t, {"pid": os.getpid(), "since": time.strftime(
            "%Y-%m-%dT%H:%M:%S")}))
        ck = os.path.join(A.CACHE, f"ckpt_{t}.pt")
        status, out, info = A.fit(d, v, seed, year, days, ck, deadline=deadline)
        if status == "paused":
            A.log(f"{t} paused at epoch {info['epoch']}")
            update_state(lambda st: st["running"].pop(t, None))
            continue
        np.savez_compressed(pred_path(t) + ".tmp.npz", scores=out.astype(np.float32), rows=days,
                            dates=np.array([str(x.date()) for x in S[days]]), n_names=len(d["names"]),
                            info=json.dumps(info))
        os.replace(pred_path(t) + ".tmp.npz", pred_path(t))
        if os.path.exists(ck):
            os.remove(ck)
        A.log(f"{t} done: epochs {info['epochs']} best {info['best_epoch']} val_ic {info['val_ic']:.4f} "
              f"train {info['train_sec'] / 60:.1f} min")

        def fin(st):
            st["running"].pop(t, None)
            if t not in st["done"]:
                st["done"].append(t)
            st["fits"][t] = {k: info[k] for k in ("epochs", "best_epoch", "val_ic", "train_sec", "stopped_by_rule")}
            st["next"] = [x for x in st["plan"] if x not in st["done"]][:4]
        update_state(fin)
        os.remove(lock_path(t))
    A.log("deadline reached")


if __name__ == "__main__":
    main()
