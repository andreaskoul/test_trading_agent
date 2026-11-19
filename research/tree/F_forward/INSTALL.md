# Installing the H9 forward weekly job (for the coordinator; nothing here has been loaded)

The owner approved a weekly runner on 2026-11-14. These steps install it. None of them has been run.

## 0. Prerequisites

* **Free disk space: at least 3 GB on the data volume.**
  * Each run rewrites `broad_panel.npz` (1 GB), `sp_panel.npz` (0.3 GB) and the trees files. The previous week's
    copies are kept as APFS clones in `y2026/prev/`.
  * On 2026-11-14 this Mac had **about 2 GB free (100% used)**. weekly.sh refuses to start below `MIN_FREE_GB`
    (default 3). Free space first.
* **Commit and push the forward-phase code to `research/tree-layer3`.** The job runs `origin/research/tree-layer3`,
  never a working copy. The files are `research/tree/{h9_forward.py,fetch_broad.py,h7_build.py}` and
  `research/tree/F_forward/{weekly.sh,alert.py,RUNBOOK.md,INSTALL.md,*.plist.template}`. Leave out the
  scratch-only logs.
* `gh` must be logged in, for the alert issue. The redacting wrapper `~/.claude/hooks/with_secrets.py` must provide
  the Alpaca keys and `IMESSAGE_TO`. Messages.app is already signed in for the fund's alerts.

## 1. The job's own worktree (never a shared one)

```
git -C /Users/apollogodofthesun/test_trading_agent fetch origin research/tree-layer3
git -C /Users/apollogodofthesun/test_trading_agent worktree add --detach \
    /Users/apollogodofthesun/test_trading_agent/.claude/worktrees/tree-forward-job origin/research/tree-layer3
```

* It sits next to `.claude/worktrees/quant-tf`, which `panel400.py` and `sp_panel` find as `../quant-tf`.
* weekly.sh links its `.cache` to the research data cache, `.claude/worktrees/tree-search/.cache` (`DATA=`).
* Each run checks out `origin/research/tree-layer3` detached and commits only `F_forward/{RECORDS,WEIGHTS}.jsonl`
  and `CHECKS.json`, pushing `HEAD:research/tree-layer3`.
* A run stops before it checks out anything if the worktree has local changes or an unpushed commit.
* The coordinator's own branch must pull these commits before pushing.

## 2. A manual run, before loading

```
bash .claude/worktrees/tree-forward-job/research/tree/F_forward/weekly.sh --no-push --no-alert
```

This fetches through the wrapper, builds and checks everything, and does not commit. A first fetch on or after
2026-11-14 writes `.cache/tree/y2026/fwd_<end>/`. Before 2026-12-05 it must append **0 forward records**.

## 3. Load the agent

```
sed -e "s#@JOB_WT@#/Users/apollogodofthesun/test_trading_agent/.claude/worktrees/tree-forward-job#g" \
    -e "s#@HOME@#$HOME#g" \
    .claude/worktrees/tree-forward-job/research/tree/F_forward/com.andreaskoul.tree-forward.plist.template \
    > ~/Library/LaunchAgents/com.andreaskoul.tree-forward.plist
plutil -lint ~/Library/LaunchAgents/com.andreaskoul.tree-forward.plist
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.andreaskoul.tree-forward.plist
```

* Schedule: launchd starts it every hour. weekly.sh `--scheduled` runs only from Saturday 14:00 UTC through Sunday
  23:59 UTC, once per ISO week; `~/.fund-runner/tree-forward/last_attempt` holds the week of the last attempt.
* Retrying a failed week is manual: `weekly.sh` without `--scheduled`. Automatic retries would repeat the alert
  every hour.
* Logs: `~/Library/Logs/fund/tree-forward.log` (launchd) and one file per run in
  `~/Library/Logs/fund/tree-forward/run-<UTC stamp>.log`. Each run's h7_build checks go to
  `~/Library/Logs/fund/tree-forward/h7_checks-<stamp>/`.
* Unload: `launchctl bootout "gui/$(id -u)/com.andreaskoul.tree-forward"`.

## First runs

| Saturday | last session fetched | forward records |
|---|---|---|
| 2026-11-21 (first gate window) | 2026-11-20 | 0. The 2026-11-19 book's target needs the close 6 sessions after 2026-11-19. |
| 2026-11-28 | 2026-11-27 | 0. Thanksgiving (Thu 2026-11-26) closes the market, so 6 sessions after 2026-11-19 is **Mon 2026-11-30**, not 2026-11-27. There is no 2026-11-26 Thursday book: the panel has no 26 November session, as in H7's Thursday rule. |
| 2026-12-05 | 2026-12-04 | the first forward record: 2026-11-19, all four constructions |

Loading the agent before 2026-11-21 is harmless: the runs on 11-21 and 11-28 append nothing and commit only
`CHECKS.json`.

## On failure

* weekly.sh stops at the first non-zero exit.
* It opens a GitHub issue ("Research: H9 forward weekly job FAILED <date>"). This uses `alert.py issue`, which is
  `gh issue create -R <runner.py GH_REPO>`, as in `fund/local/runner.py`.
* It texts the owner through `alert.py text`, which is `runner.py imessage()`, run through the redacting wrapper.
* It exits 1. Records that were already written stay written: `books` saves before its quality gate (CLAUDE.md rule 9).

## Not run on this machine

The fund-side H7 extension (MASTER 2026 scores for new weeks, the fund NAV and the MASTER decay monitor) does not run
here. `master_seeds/` holds per-seed **scores**, not model weights, so scoring a new week means the 5-hour MPS refit.
Every run logs that this step was skipped. The H7 increment the registration tests (k × the broad book's weekly net,
k 0.59) is fully in the records as `F0_flat14`.
