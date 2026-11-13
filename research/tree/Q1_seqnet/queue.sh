#!/bin/zsh
# runs configurations one after another; each is skipped if already scored
cd "$(dirname "$0")"
for n in "$@"; do python -W ignore run.py $n > out_$n.log 2>&1; done
