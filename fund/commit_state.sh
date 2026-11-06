#!/usr/bin/env bash
# Commit fund_state/ and the research workspace's feeds and story state to the
# `fund-data` branch. The commit timestamp is the evidence that a decision
# predates its outcome.
set -euo pipefail
msg="$1"
what="${2:-all}"      # "research": only the news archive and story state (dry runs)
git config user.name 'fund-bot'
git config user.email 'fund-bot@users.noreply.github.com'
# one attempt = a fresh worktree on the latest fund-data, the copy, one commit and one push; a rejected push (a job
# pushed in between, or GitHub refused: 2026-10-28) is retried, and the script fails after 3 (CLAUDE.md 10)
pushed=""
for attempt in 1 2 3; do
  git fetch -q origin +refs/heads/fund-data:refs/remotes/origin/fund-data 2>/dev/null || true
  rm -rf /tmp/fund-data && git worktree prune
  if git rev-parse -q --verify origin/fund-data >/dev/null; then
    git worktree add -q --detach /tmp/fund-data origin/fund-data
  else                                   # first run: an orphan branch holding only fund data
    git worktree add -q --detach /tmp/fund-data
    (cd /tmp/fund-data && git checkout -q --orphan fund-data-init && git rm -rq --cached . && find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +)
  fi
  mkdir -p /tmp/fund-data/fund_research/data
  if [ "$what" = "all" ]; then mkdir -p /tmp/fund-data/fund_state && cp -a fund_state/. /tmp/fund-data/fund_state/; fi
  for d in raw state; do
    if [ -d "fund_research/data/$d" ]; then mkdir -p "/tmp/fund-data/fund_research/data/$d" && cp -a "fund_research/data/$d/." "/tmp/fund-data/fund_research/data/$d/"; fi
  done
  cd /tmp/fund-data
  for p in $([ "$what" = "all" ] && echo fund_state) fund_research/data/raw fund_research/data/state; do if [ -e "$p" ]; then git add -f "$p"; fi; done
  if git diff --cached --quiet; then cd - >/dev/null; pushed=1; break; fi
  git commit -q -m "$msg $(date -u +%Y-%m-%dT%H:%MZ)"
  if git push -q origin HEAD:fund-data; then cd - >/dev/null; pushed=1; break; fi
  cd - >/dev/null; echo "fund-data push rejected (attempt $attempt)"; sleep $((attempt * 10))
done
git worktree remove --force /tmp/fund-data
if [ -z "$pushed" ]; then echo "fund-data push rejected 3 times: records not saved"; exit 1; fi
