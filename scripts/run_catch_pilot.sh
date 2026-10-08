#!/usr/bin/env bash
# BODY-1 v1 S0 pilot (docs/BODY_DESIGN_PROPOSAL.md 8.2, decision 3): CATCH-T with the user's L_max 4 stack
# (configs/life_catch.yaml) and the control-planes-only L_max 2 stack (configs/life_catch_l2.yaml), two equal arms of
# 10 seeds x 500 generations with two-stage selection (configs/life.yaml, evolve.recheck_*). The runs share 2 job
# slots with 4 kernel threads each (at most 4 threads and about 0.4 GB per process) and start in seed order, the arms
# alternating, so they progress together. The clearly labelled seeded-ancestor arm (configs/life_catch_seeded.yaml:
# the gates' hand GRN 2-cell clicker, evolve.seed_genome catch_reflex) runs too by default, because the kernel census
# (GB10, RESULTS.md BODY-1 v1) found 1 genuine founder in 8,192 genomes at each L_max, below the proposal's 1 in
# 2,000 (proposal 7, step 3: then run the unseeded arm with a larger founder budget and the seeded arm, and report
# both). PILOT_SEEDED=0 leaves it out.
#
# Success and kill (proposal 8.2, pre-registered): >= 5 of 10 seeds reach F >= +2.0 (life.skill_at) within 500
# generations; kill if >= 8 of 10 seeds sit at <= 4 cells after 500 generations.
#
# Outputs: outputs/catch_pilot/{lmax4,lmax2}_hexprism_sex_s<seed>/ (each results row records git_rev and git_dirty),
# logs in logs/catch_pilot/, then the summary table in results/catch_pilot/. Commit first: a dirty tree is recorded
# per run.
#
# Dry run: PILOT_ROOT puts outputs/, logs/ and results/ under another directory, PILOT_SEEDS and PILOT_GENERATIONS
# shrink the matrix, PILOT_JOBS and PILOT_THREADS change the slots, and any arguments are passed to every run as
# key=value overrides:
#   PILOT_ROOT=/tmp/catch_dry PILOT_SEEDS=0 PILOT_GENERATIONS=2 scripts/run_catch_pilot.sh evolve.lam=28 evolve.mu=4
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
NAME=catch_pilot
ROOT=${PILOT_ROOT:+$PILOT_ROOT/}
SEEDS=${PILOT_SEEDS:-0,1,2,3,4,5,6,7,8,9}
GENERATIONS=${PILOT_GENERATIONS:-500}
JOBS=${PILOT_JOBS:-2}
THREADS=${PILOT_THREADS:-4}
CONFIGS=configs/life_catch.yaml,configs/life_catch_l2.yaml
if [ "${PILOT_SEEDED:-1}" = "1" ]; then
  CONFIGS=$CONFIGS,configs/life_catch_seeded.yaml
fi
if [ -n "$(git --no-optional-locks status --porcelain 2>/dev/null)" ]; then
  echo "warning: the working tree is dirty; every results row will say git_dirty=true" >&2
fi
$PY scripts/sweep.py --config "$CONFIGS" --seeds "$SEEDS" --jobs "$JOBS" --threads "$THREADS" --name "$NAME" \
    --out "${ROOT}outputs" --logs "${ROOT}logs" evolve.generations="$GENERATIONS" "$@"
$PY scripts/aggregate.py "${ROOT}outputs/$NAME" --out "${ROOT}results/$NAME"
echo "pilot done"
