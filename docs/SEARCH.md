# Shared multiworld search

`src/search.py` is the opt-in life search used when `evolve.selection` or
`evolve.seed_population` or `evolve.seed_archive` is configured. Existing configurations retain the legacy loop.
`evolve.allocation` selects the open-world variant (allocation-aware lives, racing, behaviour grids; see
"Open-world search" below).
These are training decisions outside the organism; cell rules and world physics do not change.

## Configuration

`life.training_tasks` lists `{name, world, overrides, weight}` entries. Each candidate lives
the same fresh seeded worlds within a generation. Integer weights repeat entries in a fixed
pattern; base and recheck life counts must each contain complete patterns. Fractional world
overrides are preserved. Task objectives are within-task means of ordinary production fitness,
including physical costs, invalid-life handling and extinction charges. A task name never enters
an organism's inputs. Reserved evaluation tasks stay outside this list.

`evolve.selection` supports:

- `mean`: ordinary life-weighted fitness at both survival stages, uniform mating.
- `pareto`: task-vector nondomination and crowding at both survival stages, uniform mating.
- `epsilon_lexicase`: random task ordering and inclusive near-best filtering for mating,
  shortlist and survival. Epsilon is the task's population median absolute deviation times
  `epsilon_multiplier` (default 1). Mating draws with replacement; retention draws without it.

This epsilon rule is a declared baseline, not an uncertainty estimator or a claim of optimality.
See [La Cava et al.](https://arxiv.org/abs/1709.05394). Its RNG is separate from mutation/crossover.

`evolve.seed_population` imports exactly `mu` saved genomes in their existing order. It records
the file hash and source IDs and assigns new local IDs. It does not restart from one winner.
Optional `evolve.seed_archive` imports exactly `archive_size` additional rows and requires
`seed_population`. Their local IDs and gene origins follow the current population without collisions.
Imported fitness is unknown until fresh evaluation; generation-zero snapshots and checkpoints retain
the complete archive. Neither input file is reread on resume.

## Reproducing archive

With `archive_size > 0`, archive genomes join current genomes before reproduction. Every parent
is re-evaluated on the same fresh generation lives; mating does not use cached historical scores.
Offspring and parents compete on those same lives. The shortlist receives fresh recheck lives,
and task means are recomputed from pooled per-life scores when `recheck_key: all`.

Current survivors are chosen by the configured policy. Up to `archive_size` other, exactly distinct
genotypes are retained using task-vector Pareto ordering and crowding of the rechecked candidates.
Current genotypes are excluded from the archive; lower fronts can fill unused places. Thus this
is a bounded collection of re-evaluated alternatives, not an immutable list of past champions.
Archive IDs, objectives and actual parent contributions are logged. Exact duplicate parents do
not receive extra mating tickets, except when preserving population size requires copies.

With 32 current genomes, 32 archive entries, 224 offspring, eight initial lives and a 64-genome
eight-life recheck, the upper bound is **2,816 selection lives per generation**. Duplicate removal
and a partially filled archive can reduce it. Logged `search_lives` records actual calls.

## Measurement and resume

`life.capability_panel` declares report-only tasks, lives, representatives, schedule and a fixed seed.
It measures task champions plus mean-ranked representatives from current and archived genomes;
at generation zero, before training scores exist, it uses the first input rows. These are progress
observations, not an untouched final test, and they never feed breeding. Records go into the
checkpointed `lineage.jsonl` stream. Selection outcomes remain identical with the panel disabled.

Whole current populations and archives are saved at generation zero, panel milestones and the
final generation under `populations/gNNNNNN.json`. Checkpoints include all archive tensors,
both RNG states and log offsets. The existing numerical/source/config checks still apply.
Use `python -m src.run --config ... --resume` after an interruption; do not alter search settings
or pinned source files mid-run. Completed family runs do not silently apply the old single-world
final report: fresh multiworld confirmation is separate.

## First application: flash accessibility

`configs/flash_ladder.yaml` mixes residual brightness 50%, 25%, 10% and zero every generation.
These are four settings of one family, not four substantially different objectives. They use the
existing flash physics and prices. Four ancestral populations receive 120 generations each.
The queue, founder hashes, measured resource budget and run configurations live under
`outputs/flash_ladder_20261017/`; compact conclusions belong in `RESULTS.md`.

Progress panels also measure older acquisition, matching, resource and decoy tasks. Fresh endpoint
confirmation compares generations 0, 60 and 120 using separately selected balanced and dark-phase
roles; each role is one unchanged genome across all brightness levels. A dark-phase performance
gain is evidence of useful adaptation, not by itself proof of memory circuitry. Cue-history and
mechanism controls follow a promising result. A negative result does not establish a substrate cap.

## Broader application: retained abilities across tasks

`configs/multitask.yaml` trains on POOL, persistent pursuit, two flash visibility levels, delayed
shape matching, replenishing patches, contact-triggered food and harmful-target avoidance. All eight
conditions influence mating and survival every generation; they cover several related demands using
the same sensory/action substrate, not eight orthogonal capabilities. Matching training uses a 5–10
blank interval to offer a shorter starting challenge. No cells, world laws, prices or behavioral bonuses change.

Four lineages each receive 250 generations. Each imports its whole pre-flash population as 32 current
genomes and all 64 final flash current/archive genomes as the initial archive. There are 224 offspring,
16 initial lives (two per task) and 16 fresh recheck lives for up to 128 candidates. Rechecking therefore
filters the combined 96 breeding slots as well as their current/archive membership. The selection upper
bound is 7,168 lives per generation per lineage. Noise remains a limitation of two initial lives per task.

Progress panels observe training tasks only. `scripts/confirm_multitask.py` selects one reporting genome
at generations 0/125/250 using a separate 32-life-per-training-task development panel. Exact genotypes
are deduplicated across all stages and share one percentile-rank reference, with average ranks for ties.
Each stage maximizes its weakest task rank, then mean rank, mean ordinary F, then lowest native ID.
All three choices freeze before 512 fresh lives per task on eight trained conditions and eight reserved
variations. Each reporting genome remains unchanged across all 16 conditions. Reserved means excluded
from this study's training, not necessarily never explored anywhere in the project's history.

Reports retain task-specific acquisitions, paired uncertainty, class-conditional matching choices,
initial/passively replenished/contact-origin food, misses, body size and additive physical costs.
Ordinary guards and extinction are retained at production scores; invalid capacity/accounting fails.
This distinguishes a versatile individual from a breeding population of specialists. Four exploratory
replicates without matched scalar/narrow-training controls cannot establish selection-method superiority
or the causal benefit of diversity. Inputs and run evidence live under `outputs/multitask_20261018/`.

## Open-world search (opt-in: `evolve.allocation`)

`src/open_search.py` implements the search of docs/OPEN_WORLDS.md §6. It runs only when `evolve.allocation`
is set; every configuration without it keeps the loop above unchanged (a test replays the first generation of a
scaled-down `configs/multitask.yaml` against a golden from the pre-allocation code). `race_k`, `race_lives`,
`novel_k` and `elites` without `allocation` are refused rather than ignored. All of this is bookkeeping outside
the organism: no task name, allocation, score or grid cell reaches a life.

**Allocation-aware draws.** `LifeEvaluator.draw_allocated(purpose, index, lives)` takes one life count per training
task, in the configured order, and builds the draw task-major. Life r of task t has seed
`task_life_seed(run_seed, purpose, index, name_t, r)` (its own hash stream, keyed by the task's name), so changing one
task's count never moves another task's seeds, reordering tasks moves no seed, and the purposes `gen`, `race`,
`probe` and `elite_confirm` never share lives. Task weights must be 1. Objectives are per-task means over the
explicit task list (a task with no lives is an error, never silently dropped); the scalar `fitness` used by `mean`
selection, archive fitness and reports is the **mean of the per-task means**, not weighted by the allocation.
Other row statistics (captures, cells, ...) remain life-weighted means. Unsized `gen`/`founders` draws of an
allocated run are an even keyed split (at least one life per task), which is what founder sampling uses.

**Per-life worlds.** Every task draw (generation, recheck, founders, race, probe, elite confirmation, capability
panel and the confirmation scripts) builds each life's world with `LifeEvaluator._life_world(task, T, seed)`, after
the seed is final and before envelope noise. By default it returns the task's fixed world, so nothing changes; an
engine whose worlds vary per life overrides it to draw that life's parameters from `seed` alone. `draw_tasks` takes
`seed=` (a study's fixed panel seed) and `keyed=` so callers no longer replace seeds after the worlds are built.

**Per-life ledger columns.** `LifeEvaluator.request_columns(names)` makes every evaluation also return
`LifeEval.life_columns` `[B, L, D]`: ledger fields of the ABI or the derived `window`, `invalid`, `mismatch`,
`extinct`, `guard`, `F_kernel`, `extinct_charge`. The behaviour grids request their descriptor columns this way.

**One generation.**

1. *Allocation* (`src/allocate.py`), recomputed every `period` generations and fixed within the block:
   `w_t = mix/K + (1 − mix)(a_t + ν_t)/Σ(a + ν)` (uniform if all zero); `a_t = max(0, |β̂_t|/SE(β̂_t) − 1)` with β̂_t
   the least-squares slope of task t's probe score over the last `window` generations (≥ 3 probe points, else 0);
   `ν_t = novelty_weight · min(novelty_cap, confirmed new behaviour cells of t in the last novelty_window
   generations)`; `L_t = floor + ` the Neyman share of the `budget − K·floor` flexible lives ∝ `w_t σ̂_t`, by largest
   remainder (exact rational arithmetic, ties to the earlier task), capped at `cap` with the excess shared.
   σ̂_t is the two-way ANOVA (genome × life) residual SD of task t's shared lives over the previous block's
   generations (1 before any estimate). `mode: uniform` keeps `L_t` equal (largest remainder to earlier tasks).
2. *Shared lives:* parents (current plus Pareto archive, deduplicated) and children live the generation's
   allocated lives. Mating is as in the family search.
3. *Elite parents:* with behaviour grids, `round(parent_share · lam)` children take parent A from a uniformly
   random filled cell (any task's grid; own RNG stream, checkpointed). Lineage marks them `pa_elite: [task, cell]`.
4. *Racing* (generalises the recheck, which must be off): the top `race_k` distinct candidates by the selection
   mode plus up to `novel_k` behaviourally novel ones (the best-scoring candidate of each grid cell that is empty and
   holds none of the top candidates, ranked by within-task rank) live `race_lives` more lives on the same allocation
   (the generation's vector when `race_lives == budget`, else apportioned in proportion). Scores are pooled per
   task. Survivors and the 64-slot Pareto archive come from the raced set exactly as from the recheck shortlist.
   Without racing (`race_k: 0`, no archive) survival uses the generation's lives of every distinct candidate.
5. *Behaviour grids* (`src/elites.py`), one per task that declares descriptors: incumbents relive the generation's
   lives of their task (reused when the genome is also a candidate) and fold them into a running mean whose count is
   capped at `cap`; per cell the best distinct candidate on those shared lives fills an empty cell or replaces the
   incumbent if its paired mean gain is positive and ≥ `admit_z` SE (paired on common random numbers; needs ≥ 2
   shared lives). A newly filled cell whose value is ≥ the median of the cells filled before the generation is a
   candidate new ability, confirmed if its mean on `confirm_lives` fresh paired lives is ≥ that of the lower-median
   elite. Confirmed events feed ν_t. Cells are fixed at admission; elites leave only when replaced.
6. *Probe:* every `period` generations (after generations 4, 9, …), the top `probe_top` distinct survivors/archive
   genomes of each task (by their pooled task objective) live `probe_lives` lives of that task whose seeds never
   change (purpose `probe`, index 0, `probe_seed`) at `life.T`. Both modes run and log it, so arms compare.

**Configuration** (`evolve`):

```yaml
race_k: 96          # raced top candidates (>= mu; > mu with an archive)
race_lives: 24      # more lives per raced candidate, on the same allocation
novel_k: 16         # novelty candidates added to the race (needs elites)
allocation:
  mode: uniform     # uniform | lp
  budget: 24        # lives per candidate per generation (K * floor <= budget <= K * cap)
  floor: 2          # >= 1: no task is ever dropped
  cap: 8
  mix: 0.2
  period: 5
  window: 30
  probe_top: 4
  probe_lives: 8    # 0 disables the probe (not allowed with lp)
  probe_seed: null  # null: the run seed (own purpose stream either way)
  novelty_weight: 1.0
  novelty_window: 10
  novelty_cap: 3
elites:
  shape: [4, 4]
  descriptors: {pool: [captures, misses], patches: [patch_harvest_0/patch_source_0, patch_geometric_misses]}
  bounds: {pool: [[0, 32], [0, 64]], patches: [[0, 1], [0, 64]]}   # fixed; outside values go to edge cells
  cap: 64
  admit_z: 1.0
  parent_share: 0.25
  confirm_lives: 8
```

Descriptor values are per-life ledger columns or per-life ratios `"a/b"` (0 where `b` is 0), averaged over a
genome's lives of that task. Duplication (`dup_rate`, `del_rate`, `dup_split`) and `n_mut_scale` act exactly as in
the family search; children of elite parents inherit the elite's gene origins.

**Logs, accounting and resume.** Curves rows add `allocation`, `race_allocation`, `raced`, `novel_raced`,
`elite_parent_draws`, `elites_filled`, `elite_admissions`, `elite_events`, an `allocator` record at each block start
(a, ν, w, σ̂, lives) and `probe` scores when measured. Lineage rows add the allocation, the race's IDs, seeds and
tasks, and every admission and new-ability check. `lives` counts actual lives by kind (`founders`, `gen`, `race`,
`elite`, `confirm`, `probe`); `search_lives` is their sum (capability panels stay separate in `panel_lives`).
Population snapshots add the allocation and every grid's elites. Checkpoints (`family_search_version: 2`) add the
allocator state, grids, confirmed events, the elite RNG and the life counters; 3 + resume + 3 generations equal 6
byte for byte, including a stop inside an allocation block.

**Configs.** `configs/open_worlds_base.yaml` (mu 32, archive 64, lam 224 → 320 candidates, budget 24 with floor 2
and cap 8, racing 96 + 16 on 24 lives, 4×4 grids, parent share 0.25, G 100, checkpoints every 5) and its arms
`open_worlds_pilot_U.yaml` (uniform), `_LP.yaml` (lp) and `_LPD.yaml` (lp, dup 0.02, del 0.01), which share the run
seed. Until the ABI-8 worlds exist, the base uses the eight multitask conditions and ABI-7 ledger columns as
placeholders; the world work replaces `life.training_tasks` and the descriptors together.

**Known limits.** With fixed probe seeds a nearly constant probe series can give a large t-statistic for a tiny
slope (a_t is a detectability measure, not an effect size); the floor and cap bound what that can cost. Admission
on 2–8 shared lives is noisy and takes the best challenger per cell, so false replacements of equal elites are
expected at roughly the one-SE rate; the running mean and re-evaluation every generation limit their effect.

## Local execution and artifacts

Use `scripts/run_local_queue.py` for bounded local jobs, fixed per-worker threads, memory headroom,
durable status and logs. No paid compute is required. Keep raw arrays, checkpoints, build products
and test scratch under `outputs/`. Commit code, configuration, concise results and selected visuals;
do not copy whole source trees and test directories into each result archive. Existing public
history is retained.
