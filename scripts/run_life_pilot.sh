#!/usr/bin/env bash
# Overnight pilot of the one-life model (docs/ONE_LIFE_DESIGN.md, EVALUATION PROTOCOL): the full model on hex
# (configs/life_bell.yaml) and on square8 (configs/life_bell_square8.yaml), two equal arms of 10 seeds x 500
# generations with two-stage selection (configs/life.yaml, evolve.recheck_*). The 20 runs share 3 job slots with 3
# kernel threads each and start in seed order, hex and square8 alternating, so the arms progress together. Controls
# run later, once the real costs are known.
#
# Outputs: outputs/life_pilot/full_{hex,square8}_sex_s<seed>/ (each results row records git_rev and git_dirty), logs
# in logs/life_pilot/, then the summary table in results/life_pilot/. Commit first: a dirty tree is recorded per run.
#
# Dry run: PILOT_ROOT puts outputs/, logs/ and results/ under another directory, PILOT_SEEDS and PILOT_GENERATIONS
# shrink the matrix, and any arguments are passed to every run as key=value overrides:
#   PILOT_ROOT=/tmp/pilot_dry PILOT_SEEDS=0,1 PILOT_GENERATIONS=2 scripts/run_life_pilot.sh
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
NAME=life_pilot
ROOT=${PILOT_ROOT:+$PILOT_ROOT/}
SEEDS=${PILOT_SEEDS:-0,1,2,3,4,5,6,7,8,9}
GENERATIONS=${PILOT_GENERATIONS:-500}
if [ -n "$(git --no-optional-locks status --porcelain 2>/dev/null)" ]; then
  echo "warning: the working tree is dirty; every results row will say git_dirty=true" >&2
fi
$PY scripts/sweep.py --config configs/life_bell.yaml,configs/life_bell_square8.yaml --seeds "$SEEDS" \
    --jobs 3 --threads 3 --name "$NAME" --out "${ROOT}outputs" --logs "${ROOT}logs" \
    evolve.generations="$GENERATIONS" "$@"
$PY scripts/aggregate.py "${ROOT}outputs/$NAME" --out "${ROOT}results/$NAME"
echo "pilot done"
