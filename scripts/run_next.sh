#!/usr/bin/env bash
# Lattice x breeding on context (where grown structure matters), a withdraw rerun with adaptive founders,
# then the message ladder (withdraw -> context -> jump -> memory) on 3 seeds.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
$PY scripts/sweep.py --config configs/context.yaml --lattices hex,square4,square8 --breeding sex,asex --seeds 0,1,2 \
    --jobs 4 --threads 3 --name context_lattice evolve.generations=200 logging.gif=false
$PY scripts/sweep.py --config configs/withdraw.yaml --lattices hex --breeding sex --seeds 0,1,2 --jobs 3 --threads 4 \
    --name withdraw_v2 evolve.generations=200 logging.gif=false
$PY scripts/sweep.py --config configs/ladder_msg.yaml --lattices hex --breeding sex --seeds 0,1,2 --jobs 3 --threads 4 \
    --name ladder_msg
echo "all done"
