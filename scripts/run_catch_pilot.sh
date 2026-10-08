#!/usr/bin/env bash
# BODY-1 S0 pilot (docs/BODY_DESIGN_PROPOSAL.md 8.2, decision 3) and the S1 SPECK arms. The run matrix is a list of arms with a seed count each and, optionally, their own generations
# (PILOT_ARMS, "name:seeds[:generations] ..."; without generations an arm runs PILOT_GENERATIONS, default 500):
#
#   arm           config                              what it is
#   v1_l4         configs/life_catch.yaml             CATCH-T, the user's L_max 4 stack (two hidden planes)
#   v1_l2         configs/life_catch_l2.yaml          the hidden-planes-off control (L_max 2); bitwise the same lives as
#                                                     v1_l4 until a genome grows a cell above the act plane
#   v1_seeded     configs/life_catch_seeded.yaml      SEEDED ANCESTOR (declared hedge, never the main result): the
#                                                     gates' hand GRN 2-cell clicker, evolve.seed_genome catch_reflex
#   speck_l4      configs/life_speck.yaml             SPECK (spec preset catch_speck_l4: sigma 0.6, R_cap 500,
#                                                     c_miss 10), L_max 4
#   speck_seeded  configs/life_speck_seeded.yaml      SPECK from the same labelled seed genome (declared hedge)
#
# Every arm uses two-stage selection (K64 L4) and the per-generation life length of gate GB11 (T from 768, 1024 and
# 1536, one per generation; judged lives at T = 1024). Runs share PILOT_JOBS slots of PILOT_THREADS kernel threads
# (at most 4 threads and about 0.45 GB per process) and start in seed order with the arms interleaved (seed 0 of
# every arm, then seed 1 of every arm that has one, ...), so the arms progress together and an arm with fewer seeds
# drops out of the rotation early.
#
# Default matrix: v1_l4:10 v1_l2:3 v1_seeded:3:300 speck_l4:10 speck_seeded:3:300 (29 runs) on 4 jobs x 3 threads
# (the machine's sweep setting; 12 of 14 cores). SPECK passes GS1-GS6 in the kernel at its c_miss 10 (LIFE_ABI.md
# 15.62; at c_miss 2 blind clicking paid), with caveats in docs/LIFE_GATES.md (delay, the growth path's dip from the
# best reflex). SPECK L4 has 10 seeds so its start and routing criteria (RESULTS.md, Pre-pilot part 10) count seeds
# like S0's.
# Time per run (RESULTS.md, Pre-pilot, smoke runs with the drag fix and the T draw, 4 threads per job,
# load 11-27 on 14 CPUs; low / central / high): v1 unseeded 500 generations 0.26 / 0.62 / 2.7 h (founder sampling
# 0.13 h, then about 1 s per generation while bodies stay at 2 cells, 10-30 s once they grow; central: 3 of 10 seeds
# climb at generation 200); seeded 300 generations 0.8 / 1.2 / 2.4 h (500: 1.4 / 2.0 / 4.1 h); SPECK unseeded 500
# generations 1.35 / 1.9 / 3.6 h. Default matrix: 22 / 34 / 86 job-hours at 4 threads, about 7 / 11 / 29 h on 4
# jobs x 3 threads; at load 30 add up to half again.
#
# Success and kill (proposal 8.2, pre-registered for S0): >= 5 of 10 seeds reach F >= +2.0 (life.skill_at) within 500
# generations; kill if >= 8 of 10 seeds sit at <= 4 cells after 500 generations. GB11 is read from every results row
# (n_half, growing: the best genome's size at T/2 and the share of final lives still growing by more than 10%).
#
# Outputs: outputs/catch_pilot/<control>_hexprism_sex_s<seed>/ (control lmax4, lmax2, seeded, speck_lmax4,
# speck_seeded; each results row records git_rev and git_dirty), logs in logs/catch_pilot/, then the summary table in
# results/catch_pilot/. Commit first: a dirty tree is recorded per run.
#
# Dry run: PILOT_PLAN=1 prints the runs in start order and exits; PILOT_ROOT puts outputs/, logs/ and results/ under
# another directory, PILOT_GENERATIONS changes the default length, PILOT_JOBS and PILOT_THREADS change the slots, and
# any arguments are passed to every run as key=value overrides (an arm's own generations still win):
#   PILOT_PLAN=1 PILOT_ARMS="v1_l4:10 speck_l4:6" scripts/run_catch_pilot.sh
#   PILOT_ROOT=/tmp/catch_dry PILOT_ARMS="v1_l4:1 v1_seeded:1:2" PILOT_GENERATIONS=2 scripts/run_catch_pilot.sh \
#       evolve.lam=28 evolve.mu=4
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
NAME=catch_pilot
ROOT=${PILOT_ROOT:+$PILOT_ROOT/}
ARMS=${PILOT_ARMS:-v1_l4:10 v1_l2:3 v1_seeded:3:300 speck_l4:10 speck_seeded:3:300}
GENERATIONS=${PILOT_GENERATIONS:-500}
JOBS=${PILOT_JOBS:-4}
THREADS=${PILOT_THREADS:-3}

config_of() {
  case "$1" in
    v1_l4) echo configs/life_catch.yaml ;;
    v1_l2) echo configs/life_catch_l2.yaml ;;
    v1_seeded) echo configs/life_catch_seeded.yaml ;;
    speck_l4) echo configs/life_speck.yaml ;;
    speck_seeded) echo configs/life_speck_seeded.yaml ;;
    *) return 1 ;;
  esac
}

CONFIGS=""
MAX=0
for arm in $ARMS; do
  name=${arm%%:*}
  rest=${arm#*:}
  count=${rest%%:*}
  gens=""
  [ "$rest" != "$count" ] && gens=${rest#*:}:  # the trailing colon makes an empty generations field visible
  if [ "$name" = "$arm" ] || ! [[ "$count" =~ ^[1-9][0-9]*$ ]] || ! [[ "$gens" =~ ^([1-9][0-9]*:)?$ ]]; then
    echo "bad arm '$arm': write name:seeds or name:seeds:generations, e.g. v1_l4:10 or v1_seeded:5:300" >&2
    exit 2
  fi
  if ! cfg=$(config_of "$name"); then
    echo "unknown arm '$name' (v1_l4 v1_l2 v1_seeded speck_l4 speck_seeded)" >&2
    exit 2
  fi
  gens=${gens%:}
  CONFIGS=${CONFIGS:+$CONFIGS,}$cfg:$count${gens:+:$gens}
  [ "$count" -gt "$MAX" ] && MAX=$count
done
if [ -z "$CONFIGS" ]; then
  echo "PILOT_ARMS is empty" >&2
  exit 2
fi
SEEDS=$(seq -s, 0 $((MAX - 1)))
SWEEP=("$PY" scripts/sweep.py --config "$CONFIGS" --seeds "$SEEDS" --jobs "$JOBS" --threads "$THREADS" --name "$NAME"
       --out "${ROOT}outputs" --logs "${ROOT}logs")
if [ "${PILOT_PLAN:-0}" = "1" ]; then
  "${SWEEP[@]}" --plan evolve.generations="$GENERATIONS" "$@"
  exit $?
fi
if [ -n "$(git --no-optional-locks status --porcelain 2>/dev/null)" ]; then
  echo "warning: the working tree is dirty; every results row will say git_dirty=true" >&2
fi
"${SWEEP[@]}" evolve.generations="$GENERATIONS" "$@"
$PY scripts/aggregate.py "${ROOT}outputs/$NAME" --out "${ROOT}results/$NAME"
echo "pilot done"
