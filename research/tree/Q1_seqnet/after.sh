#!/bin/zsh
# wait until no run.py of this branch runs and no queue is waiting, then run the given configurations
cd "$(dirname "$0")"
sleep 60
while pgrep -f "Q1_seqnet.*kill -0|while kill -0 94660" >/dev/null || pgrep -f "^/bin/zsh ./queue.sh" >/dev/null; do sleep 20; done
./queue.sh "$@"
