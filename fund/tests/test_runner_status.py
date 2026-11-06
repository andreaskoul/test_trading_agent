"""Contract: the runner's job status in heartbeat.json (fund/local/runner.py: log_status, job_status), read by the
website's operations panel.

    python fund/tests/test_runner_status.py

The failure class: jobs that never ran or ended without a verdict line were noticed only by a person (2026-11-04: the
installed runner predated `spxmark`, so the S&P chart stayed empty). The fixtures are the ends of real logs from
2026-11-05/06; the failed, silent and missed cases are written here.
"""
import datetime as dt
import importlib.util
import os
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures", "runner_logs")
spec = importlib.util.spec_from_file_location("runner", os.path.join(HERE, "..", "local", "runner.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
NOW = dt.datetime(2026, 11, 6, 19, 30, tzinfo=dt.timezone.utc)


def test_real_logs_read_ok():
    for f, job in [("spx-20261106-0345.log", "spx"), ("spxmark-20261105-2145.log", "spxmark"),
                   ("reconcile-20261106-0110.log", "reconcile"), ("report-20261106-0550.log", "report")]:
        assert R.log_status(job, os.path.join(FIX, f), NOW) == "ok", f


def test_failed_silent_and_running():
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "spxmark-20261106-2145.log")
        open(p, "w").write("── Mark\n[2026-11-06 21:47:00Z] spxmark: FAILED in 1.2 min\n")
        assert R.log_status("spxmark", p, NOW) == "failed"
        open(p, "w").write("── Mark\nTraceback (most recent call last):\n")          # no verdict line
        old = (NOW - dt.timedelta(minutes=R.TIMEOUT["r5"] + 16)).timestamp()
        os.utime(p, (old, old))
        assert R.log_status("spxmark", p, NOW) == "no result"                       # past its group's time budget
        os.utime(p, (NOW.timestamp(), NOW.timestamp()))
        assert R.log_status("spxmark", p, NOW) == "running"
        open(p, "w").write("lifecycle: nothing to do\n[2026-11-06 21:47:00Z] spxmark: ok in 0.1 min\n")
        assert R.log_status("spxmark", p, NOW) == "nothing to do"
        q = os.path.join(d, "reconcile-20261106-0110.log")                          # reconcile reports as `execute`
        open(q, "w").write("[2026-11-06 01:13:26Z] execute: FAILED in 2.9 min\n")
        assert R.log_status("reconcile", q, NOW) == "failed"
    finally:
        shutil.rmtree(d)


def test_job_status_takes_each_jobs_latest_log_and_slot():
    d = tempfile.mkdtemp()
    try:
        for f in os.listdir(FIX):
            shutil.copy(os.path.join(FIX, f), d)
        open(os.path.join(d, "spx-20261030-0345.log"), "w").write("spx: FAILED\n")   # older log: ignored
        open(os.path.join(d, "spx-backfill.log"), "w").write("spx: FAILED\n")       # not a scheduled run's name
        old, R.LOGS = R.LOGS, d
        try:
            st = R.job_status(NOW)
        finally:
            R.LOGS = old
        assert set(st) == set(R.SCHEDULE)
        assert st["spx"]["status"] == "ok" and st["spx"]["started"] == "2026-11-06T03:45+00:00"
        assert st["spx"]["slot"] == "2026-11-06T03:45+00:00"
        assert st["spxmark"]["slot"] == "2026-11-05T21:45+00:00" and st["spxmark"]["status"] == "ok"
        assert "started" not in st["qshadow"] and st["qshadow"]["slot"] == "2026-11-05T03:30+00:00"   # no log: the page says "did not run"
        assert st["prices"]["every"] == 30 and st["prices"]["slot"] == "2026-11-06T19:15+00:00"
    finally:
        shutil.rmtree(d)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
