#!/usr/bin/env python3
"""Local scheduler for the fund: runs every scheduled operation on this Mac instead of
GitHub Actions + cron-job.org. Standard library only.

    runner.py tick                      launchd calls this every minute; starts the jobs that are due
    runner.py run <job> [options]       run one job now (archive | weekly | trade | review | reconcile | execute)
    runner.py enable | disable          switch the schedule on or off (manual `run` always works)
    runner.py status                    schedule, last start of each job, secrets present

Each run mirrors its workflow in .github/workflows/: a fresh clone of origin/main, fund state
restored from `fund-data`, the same steps and conditions, the same commits to `fund-data`, a
GitHub issue on failure, and the GitHub Pages deploy (fund_pages.yml) started after every run
that can change the trade record. Jobs in one concurrency group never overlap (file locks).

Home: ~/.fund-runner (secrets.env, venv, state, caches, work dirs); logs: ~/Library/Logs/fund.
"""
import argparse
import calendar
import datetime as dt
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time

HOME = os.path.expanduser("~/.fund-runner")
LOGS = os.path.expanduser("~/Library/Logs/fund")
SECRETS = os.path.join(HOME, "secrets.env")
VENV_BIN = os.path.join(HOME, "venv", "bin")
STATE = os.path.join(HOME, "state.json")
ENABLED = os.path.join(HOME, "enabled")
REPO = "https://github.com/andreaskoul/test_trading_agent"
GH_REPO = "andreaskoul/test_trading_agent"

# The schedule (UTC), as in fund/README.md. late = how long after its slot a job may still start
# (the Mac was asleep or off); the desks refuse their own out-of-window runs on top of this.
# Each script is idempotent, so trade runs Thu and Fri (a Friday run trades only after a Thursday holiday).
SCHEDULE = {
    "archive":   {"days": "0123456", "at": "21:20", "late": 180},
    "weekly":    {"days": "2",       "at": "22:15", "late": 1140},   # still decidable before Thu 19:00
    "trade":     {"days": "34",      "at": "16:15", "late": 180},
    "review":    {"days": "0124",    "at": "16:30", "late": 180},
    "reconcile": {"days": "12345",   "at": "01:10", "late": 720},
}
# weekday(): Mon=0 ... Sun=6
NEEDS = {
    "archive": ["FINNHUB_API_KEY", "HF_TOKEN"],
    "weekly": ["OPENROUTER_API_KEY", "FINNHUB_API_KEY", "HF_TOKEN"],
    "trade": ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
    "review": ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "OPENROUTER_API_KEY", "FINNHUB_API_KEY"],
    "reconcile": ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
}
GROUP = {"archive": "archive", "weekly": "weekly", "execute": "execute", "review": "execute"}
TIMEOUT = {"archive": 350, "weekly": 340, "execute": 60, "review": 60}     # minutes, as the workflows
PAGES_AFTER = {"weekly", "execute", "review"}                               # fund_pages.yml's workflow_run list


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def log(msg):
    print(f"[{now_utc():%Y-%m-%d %H:%M:%SZ}] {msg}", flush=True)


def load_secrets():
    env = {}
    if os.path.exists(SECRETS):
        for line in open(SECRETS):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = re.split(r"\s+#", v, maxsplit=1)[0].strip().strip('"').strip("'")     # drop a trailing comment
                if v:
                    env[k.strip()] = v
    return env


def read_state():
    try:
        return json.load(open(STATE))
    except (OSError, ValueError):
        return {}


def write_state(s):
    tmp = STATE + ".tmp"
    json.dump(s, open(tmp, "w"), indent=1)
    os.replace(tmp, STATE)


def last_slot(job, now):
    """The latest scheduled time of `job` at or before `now`."""
    sc = SCHEDULE[job]
    h, m = map(int, sc["at"].split(":"))
    for back in range(8):
        d = (now - dt.timedelta(days=back)).date()
        if str(d.weekday()) in sc["days"]:
            slot = dt.datetime(d.year, d.month, d.day, h, m, tzinfo=dt.timezone.utc)
            if slot <= now:
                return slot
    return None


# ------------------------------------------------------------------ tick (launchd, every minute)
def tick(args):
    os.makedirs(LOGS, exist_ok=True)
    now = now_utc()
    state = read_state()
    if args.init:                                   # mark every past slot as handled: nothing fires retroactively
        write_state({j: last_slot(j, now).isoformat() for j in SCHEDULE}); log("schedule state initialised"); return
    if not os.path.exists(ENABLED):
        return
    secrets = load_secrets()
    changed = False
    for job in SCHEDULE:
        slot = last_slot(job, now)
        if slot is None or state.get(job, "") >= slot.isoformat():
            continue
        state[job] = slot.isoformat(); changed = True          # one attempt per slot, whatever happens next
        late = (now - slot).total_seconds() / 60
        if late > SCHEDULE[job]["late"]:
            log(f"{job}: slot {slot:%a %H:%M}Z missed by {late:.0f} min (Mac asleep or off); skipped"); continue
        missing = [k for k in NEEDS[job] if k not in secrets]
        if missing:
            log(f"{job}: not started, missing in {SECRETS}: {', '.join(missing)}"); continue
        lf = open(os.path.join(LOGS, f"{job}-{now:%Y%m%d-%H%M}.log"), "a")
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "run", job], stdout=lf, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True, env={**os.environ, "RUNNER_LOG": lf.name})
        log(f"{job}: started for slot {slot:%a %H:%M}Z ({late:.0f} min after it); log {lf.name}")
    if changed:
        write_state(state)


# ------------------------------------------------------------------ run one job
class Job:
    def __init__(self, name, env, work):
        self.name, self.env, self.work, self.failed = name, env, work, False
        self.deadline = time.time() + TIMEOUT[GROUP[name]] * 60

    def step(self, title, cmd, when="success", allow_fail=False, timeout_min=None):
        """GitHub step semantics: when = success (no earlier failure) | always | failure."""
        if (when == "success" and self.failed) or (when == "failure" and not self.failed):
            return None
        left = self.deadline - time.time()
        t = min(left, timeout_min * 60) if timeout_min else left
        log(f"── {title}")
        if t <= 0:
            log("   job time budget spent"); self.failed = True; return 1
        try:
            rc = subprocess.run(["bash", "-c", "set -eo pipefail\n" + cmd], cwd=self.work, env=self.env, timeout=t).returncode
        except subprocess.TimeoutExpired:
            log(f"   timed out after {t / 60:.0f} min"); rc = 124
        if rc:
            log(f"   exit {rc}{' (continue on error)' if allow_fail else ''}")
            if not allow_fail:
                self.failed = True
        return rc


RESTORE = """git fetch -q origin +refs/heads/fund-data:refs/remotes/origin/fund-data 2>/dev/null || exit 0
for p in {paths}; do git checkout origin/fund-data -- "$p" 2>/dev/null || echo "fund-data has no $p yet"; done"""

COMMIT_EXEC = """git config user.name 'fund-bot'; git config user.email 'fund-bot@users.noreply.github.com'
FD="$RUNNER_TMP/fd"
for attempt in 1 2 3; do
  git fetch -q origin +refs/heads/fund-data:refs/remotes/origin/fund-data
  rm -rf "$FD" && git worktree prune && git worktree add -q --detach "$FD" origin/fund-data
  {copy}
  for f in fund_state/live/20*/reviews/*.json; do [ -f "$f" ] && mkdir -p "$FD/$(dirname "$f")" && cp "$f" "$FD/$f"; done
  [ -d fund_state/live/ledger ] && mkdir -p "$FD/fund_state/live/ledger" && cp -a fund_state/live/ledger/. "$FD/fund_state/live/ledger/"
  cd "$FD" && git add -A fund_state/live
  if git diff --cached --quiet; then cd - >/dev/null; break; fi
  git commit -q -m "{msg} $(date -u +%Y-%m-%dT%H:%MZ)"
  if git push -q origin HEAD:fund-data; then cd - >/dev/null; break; fi
  cd - >/dev/null; sleep 5
done"""

COPY_EXEC = """mkdir -p "$FD/fund_state/live/execution"
  [ -d fund_state/live/execution ] && cp -a fund_state/live/execution/. "$FD/fund_state/live/execution/"
  for f in fund_state/live/20*/execution.json; do [ -f "$f" ] && mkdir -p "$FD/$(dirname "$f")" && cp "$f" "$FD/$f"; done
  if [ -f fund_state/live/HALT ]; then cp fund_state/live/HALT "$FD/fund_state/live/HALT"; else rm -f "$FD/fund_state/live/HALT"; fi"""


def issue(j, title, body_cmd):
    j.step("Alert (GitHub issue)", f'gh issue create -R {GH_REPO} --title "{title} $(date -u +%F)" '
                                    f'--body "$({body_cmd})\n\n(local runner on $(hostname -s); log {j.env["RUN_LOG"]}) @andreaskoul"',
           when="failure")


def job_archive(j, a):
    minutes = a.minutes or "40"
    j.env["ARCHIVE_MINUTES"] = minutes
    j.step("News archive", "python fund/archive.py")
    if minutes != "330":
        j.step("Context archive (Amendment 6)", "python fund/context_archive.py", when="always", allow_fail=True, timeout_min=25)
    if not j.failed:
        backlog = "0"
        for line in open(j.env["GITHUB_OUTPUT"]):
            if line.startswith("backlog="):
                backlog = line.strip().split("=", 1)[1]
        if backlog != "0":
            n = now_utc()
            if n.weekday() == 2 and n.hour >= 12:          # the weekly desks need Finnhub from 22:15 UTC
                log(f"backlog {backlog} days: left for the daily runs")
            else:
                log(f"backlog {backlog} days: continuing the backfill in a new run")
                lf = open(os.path.join(LOGS, f"archive-backfill-{n:%Y%m%d-%H%M}.log"), "a")
                subprocess.Popen([sys.executable, os.path.abspath(__file__), "run", "archive", "--minutes", "330"],
                                 stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True,
                                 env={**os.environ, "RUNNER_LOG": lf.name})
    issue(j, "Fund: news archive failed", "echo Local run failed; see the log on the Mac.")


def job_weekly(j, a):
    dry = a.dry_run
    j.env["FUND_DRYRUN"] = "1" if dry else "0"
    if not dry:                                     # a week is decided once
        rc = j.step("Guard: is this week already decided?", """
git fetch -q origin +refs/heads/fund-data:refs/remotes/origin/fund-data 2>/dev/null || exit 0
a=$(cd fund && python -c "from common import asof_from_env; print(asof_from_env().date())")
if git show "origin/fund-data:fund_state/live/$a/book.json" 2>/dev/null | grep -Eq '"status": "(ok|degraded_hold)"'; then
  echo "week $a already decided: nothing to do"; exit 78
fi""")
        if rc == 78:
            j.failed = False; return "skip"
    j.step("Restore fund state", RESTORE.format(paths="fund_state fund_research"))
    j.step("Embedding cache (persistent)", f'mkdir -p fund_research/data "{HOME}/cache/emb" && rm -rf fund_research/data/cache && '
                                          f'ln -s "{HOME}/cache/emb" fund_research/data/cache')
    if not dry:
        j.step("Refuse a live run past its deadline", """cd fund && python -c "
from common import asof_from_env, deadline_ok
a = asof_from_env()
raise SystemExit(0 if deadline_ok(a) else f'live run for {a.date()} is past its Thursday 19:00 UTC deadline: nothing to decide.')" """)
    j.step("Desk 1 · screen", "python fund/screen.py")
    j.step("Desk 2 · ideation", "python fund/ideate.py")
    j.step("Pull embedding cache from Hugging Face", "python fund/emb_store.py pull")
    j.step("Desk 3 · research", "python fund/research.py")
    j.step("Push embedding cache to Hugging Face", "python fund/emb_store.py push", when="always")
    j.step("Save news archive and story state", 'bash fund/commit_state.sh "research data" research', when="always")
    j.step("Desk 4 · analysts", "python fund/analysts.py")
    j.step("Desk 5 · red team", "python fund/redteam.py")
    j.step("Desk 6 · PM + risk", "python fund/pm_risk.py")
    j.step("Desk 8 · macro FX", "python fund/fx_desk.py")
    if not dry:
        j.step("Commit decisions (before the Thursday close)", 'bash fund/commit_state.sh "fund decisions"')
    j.step("Shadow analysts and model canary (never traded)",
           "ls fund_state/*/*/book.json >/dev/null 2>&1 || exit 0\npython fund/shadow.py\nFUND_SHADOW=1 python fund/pm_risk.py",
           when="always", allow_fail=True)
    # Amendment 6 parts 2-4 (shadow stage; run once they are on main, never fail the job)
    for f, title in (("macro_desk", "Macro desk (Amendment 6)"), ("neighbours", "Neighbourhood (Amendment 6)"),
                     ("shadow_info", "C8 informed analysts and C9 ranker (Amendment 6)")):
        if os.path.exists(os.path.join(j.work, "fund", f + ".py")):
            j.step(title, f"ls fund_state/*/*/book.json >/dev/null 2>&1 || exit 0\npython fund/{f}.py", when="always", allow_fail=True)
    j.step("Desk 7 · IC memo", "python fund/ic_memo.py", when="always")
    j.step("Desk 9 · performance", "python fund/score.py", when="always")
    j.step("Position ledger (Excel)", "python fund/ledger.py", when="always", allow_fail=True)
    if not dry:
        j.step("Commit memo and performance", 'bash fund/commit_state.sh "fund memo + performance"', when="always")
        j.step("Gate verdict (issue when it is not CONTINUE)", f"""f=fund_state/live/performance/gate.json
[ -f "$f" ] || exit 0
v=$(python -c "import json;print(json.load(open('$f'))['verdict'])"); echo "gate: $v"
[ "$v" = CONTINUE ] || gh issue create -R {GH_REPO} --title "Fund gate: $v ($(date -u +%F))" --body "$(cat fund_state/live/performance/gate.md) @andreaskoul" """,
               when="always")
    else:
        out = os.path.join(HOME, "dryruns", now_utc().strftime("%Y%m%d-%H%M"))
        j.step("Keep the dry-run results", f'[ -d fund_state/dryrun ] && mkdir -p "{out}" && cp -a fund_state/dryrun/. "{out}/" && echo "dry run kept in {out}"',
               when="always")
    issue(j, "Fund: weekly desks failed", "echo Local run failed; see the log on the Mac.")


def job_execute(j, a):
    mode = a.mode
    j.step("Restore fund state", RESTORE.format(paths="fund_state"))
    if a.resume:
        j.step("Resume after a risk stop", 'rm -f fund_state/live/HALT && echo "HALT removed by hand (local runner)"')
    j.step(f"Execute ({mode})", f"python fund/execute.py {mode}")
    if mode != "plan":
        j.step("Position ledger (Excel)", "python fund/ledger.py", when="always", allow_fail=True)
    if mode != "plan" or a.resume:
        j.step("Commit execution records", COMMIT_EXEC.format(copy=COPY_EXEC, msg=f"execution {mode}"), when="always")
    issue(j, f"Fund execution: {mode} problem",
          f'echo "Execution {mode} needs attention."; [ -f fund_state/live/execution/problems.txt ] && cat fund_state/live/execution/problems.txt || true')


def job_review(j, a):
    mode = a.mode
    j.step("Restore fund state", RESTORE.format(paths="fund_state"))
    j.step(f"Review ({mode})", f"python fund/review.py {mode}")
    if mode == "trade":
        j.step("Position ledger (Excel)", "python fund/ledger.py", when="always", allow_fail=True)
        j.step("Commit review records", COMMIT_EXEC.format(copy="", msg="daily review"), when="always")
    issue(j, "Fund: daily review failed", "echo Local run failed; see the log on the Mac.")


def run(args):
    name = args.job
    if name in ("trade", "reconcile"):              # scheduled names for the execution modes
        args.mode, name = name, "execute"
    elif name == "review" and not args.mode:
        args.mode = "trade"
    elif name == "execute" and not args.mode:
        args.mode = "plan"
    group = GROUP[name]
    os.makedirs(os.path.join(HOME, "locks"), exist_ok=True)
    lock = open(os.path.join(HOME, "locks", group), "w")
    log(f"{name} {args.mode or ''}: waiting for the '{group}' lock")
    fcntl.flock(lock, fcntl.LOCK_EX)                # like `concurrency: cancel-in-progress: false`

    stamp = now_utc().strftime("%Y%m%d-%H%M%S")
    work = os.path.join(HOME, "work", f"{name}-{stamp}")
    env = {k: v for k, v in os.environ.items() if not k.startswith("FUND_")}
    env.update(load_secrets())
    env.update({"PATH": f"{VENV_BIN}:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                "VIRTUAL_ENV": os.path.dirname(VENV_BIN), "PYTHONUNBUFFERED": "1", "GIT_TERMINAL_PROMPT": "0",
                "FUND_ASOF": args.asof or "", "RUNNER_TMP": os.path.join(work, ".tmp"),
                "GITHUB_OUTPUT": os.path.join(work, ".tmp", "github_output"),
                "RUN_LOG": os.environ.get("RUNNER_LOG", "terminal")})
    env.pop("PYTHONHOME", None)
    log(f"{name} {args.mode or ''}: cloning main into {work}")
    if subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "main", REPO, work], env=env).returncode:
        log("clone failed"); sys.exit(1)
    os.makedirs(env["RUNNER_TMP"], exist_ok=True); open(env["GITHUB_OUTPUT"], "w").close()
    # the dashboard repo clone survives between runs (ideation fetches it every run)
    os.makedirs(os.path.join(HOME, "cache", "site"), exist_ok=True)
    os.symlink(os.path.join(HOME, "cache", "site"), os.path.join(work, ".cache"))
    log(f"code: main @ {subprocess.run(['git', '-C', work, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()}")

    j = Job(name, env, work)
    started = time.time()
    awake = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])    # no idle sleep while the job runs
    drift(j)
    res = {"archive": job_archive, "weekly": job_weekly, "execute": job_execute, "review": job_review}[name](j, args)
    if name in PAGES_AFTER and res != "skip" and not args.no_pages:
        j.step("GitHub Pages: rebuild the dashboard (fund_pages.yml)",
               f"gh workflow run fund_pages.yml -R {GH_REPO} --ref main", when="always", allow_fail=True)
    awake.terminate()
    log(f"{name}: {'FAILED' if j.failed else 'ok'} in {(time.time() - started) / 60:.1f} min")
    subprocess.run(["git", "-C", work, "worktree", "prune"])
    shutil.rmtree(work, ignore_errors=True)
    prune()
    sys.exit(1 if j.failed else 0)


# The fund scripts each local job knows (runs or deliberately leaves to GitHub). A workflow on main that calls
# one not listed here means the workflow changed and this runner needs the same change.
KNOWN = {"archive": {"archive", "context_archive"},
         "weekly": {"common", "screen", "ideate", "emb_store", "research", "commit_state", "analysts", "redteam", "pm_risk",
                    "fx_desk", "shadow", "macro_desk", "neighbours", "shadow_info", "ic_memo", "score", "ledger"},
         "execute": {"execute", "ledger", "screen", "ideate", "research", "analysts", "redteam", "pm_risk"},   # mock desks: GitHub only
         "review": {"review", "ledger"}}
WORKFLOW = {"archive": "fund_archive.yml", "weekly": "fund_weekly.yml", "execute": "fund_execute.yml", "review": "fund_review.yml"}


def drift(j):
    try:
        y = open(os.path.join(j.work, ".github", "workflows", WORKFLOW[j.name])).read()
    except OSError:
        return
    new = sorted(set(re.findall(r"fund/([a-z_0-9]+)\.(?:py|sh)", y)) - KNOWN[j.name])
    mark = os.path.join(HOME, f"drift-{j.name}")
    if new and (not os.path.exists(mark) or open(mark).read() != ",".join(new)):
        open(mark, "w").write(",".join(new))
        log(f"WARNING: {WORKFLOW[j.name]} calls {', '.join(new)}, which the local runner does not run: update fund/local/runner.py")
        subprocess.run(["gh", "issue", "create", "-R", GH_REPO, "--title", f"Fund local runner: {WORKFLOW[j.name]} changed ({', '.join(new)})",
                        "--body", "The workflow on main calls scripts the local runner does not run. Port the change to "
                                  "fund/local/runner.py and re-run fund/local/install.sh. @andreaskoul"], env=j.env)
    elif new:
        log(f"WARNING: {WORKFLOW[j.name]} calls {', '.join(new)}, which the local runner does not run (issue already open)")


def prune():
    cut = time.time() - 60 * 86400
    for d in (LOGS, os.path.join(HOME, "work")):
        for f in os.listdir(d) if os.path.isdir(d) else []:
            p = os.path.join(d, f)
            if os.path.getmtime(p) < cut:
                shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)


def status(_):
    now, state, secrets = now_utc(), read_state(), load_secrets()
    print(f"schedule {'ENABLED' if os.path.exists(ENABLED) else 'DISABLED (runner.py enable)'}; now {now:%a %Y-%m-%d %H:%M}Z")
    for job, sc in SCHEDULE.items():
        days = ",".join(calendar.day_abbr[int(d)] for d in sc["days"])
        miss = [k for k in NEEDS[job] if k not in secrets]
        print(f"  {job:<10} {days:<28} {sc['at']}Z  last slot handled {state.get(job, '-')[:16]}"
              f"{'  MISSING ' + ','.join(miss) if miss else ''}")
    opt = [k for k in ("POLYGON_API_KEY", "FRED_API_KEY", "SEC_USER_AGENT") if k not in secrets]
    if opt:
        print(f"  optional secrets not set: {', '.join(opt)}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tick"); t.add_argument("--init", action="store_true"); t.set_defaults(f=tick)
    r = sub.add_parser("run")
    r.add_argument("job", choices=["archive", "weekly", "trade", "review", "reconcile", "execute"])
    r.add_argument("--mode", choices=["plan", "trade", "reconcile"], help="execute: plan|trade|reconcile; review: plan|trade")
    r.add_argument("--asof", help="as-of Wednesday YYYY-MM-DD (weekly, execute)")
    r.add_argument("--dry-run", action="store_true", help="weekly: real calls, no deadline, nothing committed")
    r.add_argument("--resume", action="store_true", help="execute: remove the HALT file after a risk stop")
    r.add_argument("--minutes", help="archive: Finnhub budget (default 40; backfill 330)")
    r.add_argument("--no-pages", action="store_true", help="do not start the GitHub Pages deploy afterwards")
    r.set_defaults(f=run)
    sub.add_parser("enable").set_defaults(f=lambda _: (open(ENABLED, "w").close(), print("schedule enabled")))
    sub.add_parser("disable").set_defaults(f=lambda _: (os.path.exists(ENABLED) and os.remove(ENABLED), print("schedule disabled")))
    sub.add_parser("status").set_defaults(f=status)
    a = p.parse_args()
    os.makedirs(HOME, exist_ok=True)
    a.f(a)


if __name__ == "__main__":
    main()
