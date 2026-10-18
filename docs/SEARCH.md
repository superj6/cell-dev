# Shared multiworld search

`src/search.py` is the opt-in life search used when `evolve.selection` or
`evolve.seed_population` is configured. Existing configurations retain the legacy loop.
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

## Local execution and artifacts

Use `scripts/run_local_queue.py` for bounded local jobs, fixed per-worker threads, memory headroom,
durable status and logs. No paid compute is required. Keep raw arrays, checkpoints, build products
and test scratch under `outputs/`. Commit code, configuration, concise results and selected visuals;
do not copy whole source trees and test directories into each result archive. Existing public
history is retained.
