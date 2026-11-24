#!/usr/bin/env bash
# H9 forward phase (PREREG Layer 3, Amendment 9): the weekly job, broad side. RUNBOOK.md steps 1-5, in order; the
# first non-zero exit stops the run, alerts (GitHub issue + iMessage, the fund runner's channels) and exits 1.
#
#   weekly.sh [--scheduled] [--no-fetch] [--no-push] [--no-alert] [--code DIR] [--y26 DIR] [--out DIR] [--h7-outd DIR]
#
#   --scheduled  launchd mode: run only from Saturday 14:00 UTC through Sunday 23:59 UTC, at most once per ISO week
#   --no-fetch   skip step 1 (no key, no network)
#   --no-push    no git at all: the code dir is used as it is; no commit, no push (dry runs)
#   --no-alert   print the alert instead of sending it
#   --code DIR   the checkout to run (default: the job's own worktree, $JOB_WT)
#   --y26 DIR    data folder (default: $DATA/tree/y2026); --out DIR: records folder (default: <code>/research/tree/F_forward)
#   --h7-outd    where h7_build writes its CHECKS.json (default: the run's log folder; never the committed H7_build/)
#
# Key-needing commands go only through the redacting wrapper; this script never reads a key file.
# It never prints a return of any construction: books/status print mechanical quantities only.
set -uo pipefail

# ---- run from a private copy: step 0 may check out a new revision of this very file
if [ -z "${H9_WEEKLY_COPY:-}" ]; then
  tmp="$(mktemp -t h9weekly).sh"; cp "$0" "$tmp"; export H9_WEEKLY_COPY="$tmp" H9_WEEKLY_ORIG="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  exec /bin/bash "$tmp" "$@"
fi
trap 'rm -f "$H9_WEEKLY_COPY"' EXIT

REPO_HOME="${REPO_HOME:-/Users/apollogodofthesun/test_trading_agent}"
JOB_WT="${JOB_WT:-$REPO_HOME/.claude/worktrees/tree-forward-job}"     # dedicated; never a shared worktree
DATA="${DATA:-$REPO_HOME/.claude/worktrees/tree-search/.cache}"        # the research data cache (.cache)
BRANCH="${BRANCH:-research/tree-layer3}"
PY="${PY:-$REPO_HOME/.venv/bin/python3}"                                 # the research venv (pandas, scipy, sklearn, lightgbm); /usr/local/bin/python3 has no pandas (2026-11-24 dry run)
QT_PY="${QT_PY:-$HOME/.cache/quant-tf-venv/bin/python}"
WRAP="${WRAP:-$HOME/.claude/hooks/with_secrets.py}"
STATE_DIR="${STATE_DIR:-$HOME/.fund-runner/tree-forward}"
LOGS="${LOGS:-$HOME/Library/Logs/fund/tree-forward}"
MIN_FREE_GB="${MIN_FREE_GB:-3}"                                         # new panels need ~1.5 GB; margin for the fund

SCHEDULED=0; FETCH=1; PUSH=1; ALERT=1; CODE=""; Y26=""; OUT=""; H7OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --scheduled) SCHEDULED=1 ;; --no-fetch) FETCH=0 ;; --no-push) PUSH=0 ;; --no-alert) ALERT=0 ;;
    --code) CODE="$2"; shift ;; --y26) Y26="$2"; shift ;; --out) OUT="$2"; shift ;; --h7-outd) H7OUT="$2"; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac; shift
done
CODE="${CODE:-$JOB_WT}"
Y26="${Y26:-$DATA/tree/y2026}"
OUT="${OUT:-$CODE/research/tree/F_forward}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$LOGS" "$STATE_DIR"
H7OUT="${H7OUT:-$LOGS/h7_checks-$stamp}"
LOG="$LOGS/run-$stamp.log"
STEP="start"

say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

fail() {                                               # alert, then exit 1 (records, if any, were saved first)
  say "FAILED at step: $STEP ($1)"
  body="$LOGS/alert-$stamp.txt"
  { echo "H9 forward weekly job failed at step: $STEP"; echo "reason: $1"; echo "log: $LOG"; echo
    echo "last log lines:"; tail -n 25 "$LOG"; } > "$body"
  if [ "$ALERT" = 1 ]; then
    (cd "$CODE" && "$PY" research/tree/F_forward/alert.py issue --body-file "$body") >> "$LOG" 2>&1 \
      || say "alert: GitHub issue NOT opened"
    (cd "$CODE" && "$PY" "$WRAP" "$PY research/tree/F_forward/alert.py text --body-file '$body'") >> "$LOG" 2>&1 \
      || say "alert: iMessage NOT sent"
  else
    say "alert (not sent, --no-alert): $(head -2 "$body" | tr '\n' ' ')"
    (cd "$CODE" && "$PY" research/tree/F_forward/alert.py issue --body-file "$body" --dry \
      && "$PY" research/tree/F_forward/alert.py text --body-file "$body" --dry) 2>&1 | tee -a "$LOG"
  fi
  exit 1
}

run() {                                                 # run one command; stop the job on a non-zero exit
  say "+ $*"
  "$@" >> "$LOG" 2>&1 || fail "exit $? from: $*"
}

# ---- scheduled gate: Saturday 14:00 UTC .. Sunday 23:59 UTC, once per ISO week (an attempt counts)
if [ "$SCHEDULED" = 1 ]; then
  dow=$(date -u +%u); hr=$(date -u +%H); wk=$(date -u +%G-W%V)
  { [ "$dow" = 6 ] && [ "$hr" -ge 14 ]; } || [ "$dow" = 7 ] || exit 0
  [ "$(cat "$STATE_DIR/last_attempt" 2>/dev/null)" = "$wk" ] && exit 0
  echo "$wk" > "$STATE_DIR/last_attempt"
fi
mkdir "$STATE_DIR/lock" 2>/dev/null || { echo "another run holds $STATE_DIR/lock" | tee -a "$LOG"; exit 1; }
trap 'rmdir "$STATE_DIR/lock" 2>/dev/null; rm -f "$H9_WEEKLY_COPY"' EXIT
caffeinate -i -w $$ &
say "H9 forward weekly: code $CODE, data $Y26, records $OUT, fetch $FETCH, push $PUSH, alert $ALERT"
export OMP_NUM_THREADS=3 OPENBLAS_NUM_THREADS=3 MKL_NUM_THREADS=3 H7_Y26="$Y26" H9_Y="$Y26" H9_OUT="$OUT" H7_OUTD="$H7OUT"
mkdir -p "$H7OUT"

# ---- step 0: preflight and the job's worktree
STEP="0 preflight"
free=$(df -g "$Y26" | awk 'NR==2 {print $4}')
[ "$free" -ge "$MIN_FREE_GB" ] || fail "only ${free} GB free on the data volume (need $MIN_FREE_GB)"
[ -d "$(dirname "$CODE")/quant-tf" ] || fail "$(dirname "$CODE")/quant-tf missing (panel400 and sp_panel need it)"
for f in "$QT_PY" "$PY" "$WRAP"; do [ -e "$f" ] || fail "missing $f"; done
"$PY" -c "import numpy, pandas, pyarrow, scipy, sklearn, lightgbm" 2>>"$LOG" || fail "$PY lacks a required package (numpy, pandas, pyarrow, scipy, sklearn, lightgbm)"
if [ "$PUSH" = 1 ]; then
  if [ ! -d "$CODE/.git" ] && [ ! -f "$CODE/.git" ]; then
    run git -C "$REPO_HOME" fetch -q origin "$BRANCH"
    run git -C "$REPO_HOME" worktree add -q --detach "$CODE" "origin/$BRANCH"
  fi
  [ -z "$(git -C "$CODE" status --porcelain --untracked-files=no)" ] || fail "job worktree $CODE has local changes"
  run git -C "$CODE" fetch -q origin "$BRANCH"
  ahead=$(git -C "$CODE" rev-list --count "origin/$BRANCH..HEAD")
  [ "$ahead" = 0 ] || fail "job worktree has $ahead unpushed commit(s): an earlier push failed; push them by hand first"
  run git -C "$CODE" checkout -q --detach "origin/$BRANCH"
  say "code: $BRANCH @ $(git -C "$CODE" rev-parse --short HEAD)"
fi
[ -e "$CODE/.cache" ] || ln -s "$DATA" "$CODE/.cache"
cd "$CODE" || fail "cannot cd to $CODE"

# ---- step 1: fetch (key-needing: only through the redacting wrapper)
STEP="1 fetch"
if [ "$FETCH" = 1 ]; then
  run "$PY" "$WRAP" "$PY research/tree/fetch_broad.py fwd"
  run "$PY" "$WRAP" "$PY research/tree/fetch_broad.py fwdraw"
else
  say "fetch skipped (--no-fetch)"
fi

# ---- step 2: extend the panels; the previous week's copies are kept in $Y26/prev for the frozen-field checks
STEP="2 panels"
mkdir -p "$Y26/prev"
for f in broad_panel.npz sp_panel.npz sp500_close_ext.parquet trees_20*.npy; do
  for g in "$Y26"/$f; do [ -f "$g" ] && { rm -f "$Y26/prev/$(basename "$g")"; cp -c "$g" "$Y26/prev/" 2>/dev/null || cp "$g" "$Y26/prev/"; }; done
done
run "$QT_PY" research/tree/h7_build.py sp_panel
run "$PY" research/tree/h7_build.py broad_panel
run "$PY" research/tree/h9_forward.py panelcheck --old "$Y26/prev/broad_panel.npz" --new "$Y26/broad_panel.npz"

# ---- step 3: predict with the frozen models (deterministic refits: same code, seeds 0-2, targets before the year)
STEP="3 trees"
year_now=$(date -u +%Y)
for y in $(seq 2026 "$year_now"); do
  if [ -f "$Y26/prev/trees_$y.npy" ]; then
    run "$PY" research/tree/h7_build.py trees "$y"
    run "$PY" research/tree/h9_forward.py treescheck --old "$Y26/prev/trees_$y.npy" --new "$Y26/trees_$y.npy" \
        --old-panel "$Y26/prev/broad_panel.npz" --new-panel "$Y26/broad_panel.npz"
  else
    has=$("$PY" -c "import numpy as np,pandas as pd; S=pd.DatetimeIndex(np.load('$Y26/broad_panel.npz')['S']); print(int(((S.year==$y)&(S.weekday==3)).sum()))")
    if [ "$has" -gt 0 ]; then
      say "trees_$y.npy: first fit of the year (Amendment 9 January refit; targets ending before $y)"
      run "$PY" research/tree/h7_build.py trees "$y"
    fi
  fi
done
say "fund side (MASTER scores, H7 fund NAV, MASTER decay monitor): SKIPPED. No saved MASTER weights exist (master_seeds hold scores), and the 5-hour refit is not run on the fund machine. The H7 increment itself (0.59 x F0_flat14 net) is in the broad records."

# ---- step 4: books (append-only records), then status (mechanical quantities only)
STEP="4 books"
run "$PY" research/tree/h9_forward.py books --through "$(date -u +%F)" --no-backfill
run "$PY" research/tree/h9_forward.py status
tail -n 8 "$LOG"

# ---- step 5: commit and push the records to $BRANCH; the push loop fails loudly
STEP="5 push"
if [ "$PUSH" = 1 ]; then
  files=""
  for f in RECORDS.jsonl WEIGHTS.jsonl CHECKS.json; do [ -f "research/tree/F_forward/$f" ] && files="$files research/tree/F_forward/$f"; done
  run git add $files
  if git diff --cached --quiet; then
    say "nothing new to commit"
  else
    last=$(tail -n 1 research/tree/F_forward/RECORDS.jsonl 2>/dev/null | "$PY" -c "import json,sys; print(json.loads(sys.stdin.read() or '{}').get('date','none'))")
    run git commit -q -m "F_forward: weekly records through $last (h9_forward books, run $stamp)"
    pushed=""
    for i in 1 2 3; do
      if git push -q origin "HEAD:refs/heads/$BRANCH" >> "$LOG" 2>&1; then pushed=1; break; fi
      say "push attempt $i rejected; rebasing on origin/$BRANCH"
      git fetch -q origin "$BRANCH" >> "$LOG" 2>&1
      git rebase -q "origin/$BRANCH" >> "$LOG" 2>&1 || { git rebase --abort >> "$LOG" 2>&1; say "rebase failed"; }
      sleep $((i * 20))
    done
    if [ -z "$pushed" ]; then fail "$BRANCH push rejected 3 times: records committed locally, not pushed"; fi
    say "pushed $(git rev-parse --short HEAD) to $BRANCH"
  fi
else
  say "commit and push skipped (--no-push)"
fi
STEP="done"
say "H9 forward weekly: ok"
