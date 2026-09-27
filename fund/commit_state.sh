#!/usr/bin/env bash
# Commit fund_state/ and the research workspace's feeds and story state to the
# `fund-data` branch. The commit timestamp is the evidence that a decision
# predates its outcome.
set -euo pipefail
msg="$1"
what="${2:-all}"      # "research": only the news archive and story state (dry runs)
git config user.name 'fund-bot'
git config user.email 'fund-bot@users.noreply.github.com'
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
if ! git diff --cached --quiet; then
  git commit -q -m "$msg $(date -u +%Y-%m-%dT%H:%MZ)"
  git push -q origin HEAD:fund-data
fi
cd - >/dev/null
git worktree remove --force /tmp/fund-data
