#!/bin/bash
# Launch N stage-S workers for M minutes and wait for all (one background job).
cd "$(dirname "$0")"
S=${1:-1}; N=${2:-3}; M=${3:-110}
for k in $(seq 1 $N); do
  ~/.cache/quant-tf-venv/bin/python -W ignore run.py $S $M >> logs/worker$k.log 2>&1 &
  sleep 20
done
wait
echo "workers exited $(date -u)"; tail -n 3 logs/worker*.log
