#!/bin/bash
# Launch N detached stage-S workers (nohup, nice 10) for M minutes each; each logs to logs/worker<k>.log.
cd "$(dirname "$0")"
S=${1:-1}; N=${2:-4}; M=${3:-2880}
for k in $(seq 1 $N); do
  nohup nice -n 10 ~/.cache/quant-tf-venv/bin/python -u -W ignore run.py $S $M >> logs/worker$k.log 2>&1 < /dev/null &
  echo "worker$k pid $!"
  sleep 20
done
