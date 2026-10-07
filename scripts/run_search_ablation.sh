#!/usr/bin/env bash
# What limits evolution on the message rungs? Variants vs the baseline (founders 1, n_mut 2, trials 12), 3 seeds each.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
for r in ${RUNGS:-withdraw jump}; do
  common="--config configs/$r.yaml --lattices hex --breeding sex --seeds 0,1,2 --jobs 1 --threads 3"
  $PY scripts/sweep.py $common --name ${r}_f8 evolve.generations=200 evolve.founders=8 logging.gif=false &
  $PY scripts/sweep.py $common --name ${r}_f8m4 evolve.generations=200 evolve.founders=8 evolve.n_mut=4 logging.gif=false &
  $PY scripts/sweep.py $common --name ${r}_f8t24 evolve.generations=200 evolve.founders=8 task.trials=24 logging.gif=false &
  $PY scripts/sweep.py $common --name ${r}_f8asex evolve.generations=200 evolve.founders=8 evolve.breeding=asex logging.gif=false &
  wait
  echo "=== $r done"
done
