#!/bin/bash
# Launch N detached R3 fit workers at nice 10 (no time-of-day pause; each worker stops below 4 GB free disk).
cd "$(dirname "$0")/../../.."
N=${1:-4}
for k in $(seq 1 $N); do
  nohup nice -n 10 ~/.cache/quant-tf-venv/bin/python -W ignore research/tree/R3_master_pit/r3.py worker >> research/tree/R3_master_pit/logs/worker$k.log 2>&1 &
  sleep 30
done
