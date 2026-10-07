#!/usr/bin/env bash
# Does evolution find message-passing solutions on the message rungs, and do growth / cell types matter?
# Per rung, 4 conditions x 3 seeds at equal evaluations (1024 + 200 x 256): evolution, random search,
# fixed one-type disk (rule only), and evolution with messages switched off. 4 conditions run side by side.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
for r in ${RUNGS:-withdraw context jump}; do
  common="--config configs/$r.yaml --lattices hex --breeding sex --seeds 0,1,2 --jobs 1 --threads 3"
  $PY scripts/sweep.py $common --name ${r}_evo evolve.generations=200 logging.gif=false &
  $PY scripts/sweep.py $common --name ${r}_random evolve.generations=0 evolve.init_samples=52224 logging.gif=false &
  $PY scripts/sweep.py $common --name ${r}_fixed evolve.generations=200 develop.mode=fixed logging.gif=false &
  $PY scripts/sweep.py $common --name ${r}_nomsg evolve.generations=200 cells.messages=false logging.gif=false &
  wait
  echo "=== $r done"
done
