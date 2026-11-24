#!/usr/bin/env bash
# Read-only copy of the fund-data records this reconciliation uses (git show; nothing on fund-data changes).
#   bash research/exec_recon/export.sh <dest>
# <dest>/fd: fund_state/live execution, lifecycle live records, reviews, HALT, state; <dest>/fd/REV: the commit.
# <dest>/hist: every committed version of each order-bearing record, named <dir>_<file>_<commit>.json.
set -euo pipefail
D="$1"; mkdir -p "$D/fd" "$D/hist"
git fetch -q origin '+refs/heads/fund-data:refs/remotes/origin/fund-data'
git rev-parse origin/fund-data > "$D/fd/REV"
git ls-tree -r --name-only origin/fund-data \
  | grep -E "fund_state/live/(execution/|lifecycle/live/|lifecycle/state.json|lifecycle/core/|lifecycle/checks.json|HALT|20[0-9-]+/execution.json|20[0-9-]+/reviews/20[0-9-]+\.json)" \
  | while read -r p; do mkdir -p "$D/fd/$(dirname "$p")"; git show "origin/fund-data:$p" > "$D/fd/$p"; done
for f in $(git ls-tree -r --name-only origin/fund-data fund_state/live/lifecycle/live/) \
         fund_state/live/2026-09-30/execution.json fund_state/live/2026-10-07/execution.json; do
  for c in $(git log origin/fund-data --format=%h -- "$f"); do
    git show "${c}:${f}" > "$D/hist/$(basename "$(dirname "$f")")_$(basename "$f" .json)_${c}.json"
  done
done
