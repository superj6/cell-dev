# Handoff: cell-dev — 2026-10-17

This is the operating summary. Read [SEARCH.md](SEARCH.md), [RESEARCH_STATUS.md](RESEARCH_STATUS.md),
[TASK_VARIATION_PLAN.md §0](TASK_VARIATION_PLAN.md), and the newest entries at the bottom of
[RESULTS.md](../RESULTS.md). The
[previous full handoff](https://github.com/superj6/cell-dev/blob/86d44a1/docs/HANDOFF.md)
preserves the historical details; its old approval gates and proposed next studies are not the current queue.

## Current direction and status

Shared multiworld search and **four whole ancestral populations for 120 generations each** on the flash
brightness ladder are complete. Broader task diversity
still matters: four brightness levels are four settings of one pursuit family, not four distinct capabilities.
Obstacle navigation and other qualitatively different demands remain future directions, not prerequisites.

**Completed 2026-10-18:** all four first attempts finished training and fresh confirmation in 6.26 elapsed
hours /48.48 CPU-hours, peak aggregate RSS 1.34 GiB. The primary dark-specialist improvement criterion passed
in 3/4 lineages. All four improved dark captures, but every endpoint makes more misses, bodies shrink,
and all remain negative-F in complete darkness after the flash. These are acquisition gains, not demonstrated
memory or generality. Small report-only panels suggest older-task losses and generally fewer hidden cells.
See [the report](../results/flash_ladder_20261017/REPORT.md) and its paired measurements/figure.

Raw evidence remains under `outputs/flash_ladder_20261017/`, pinned source `54c5310` in `checkout/`.
Independent analysis rederived all 24 reporting choices and 2,112 statistics from the 36 raw blocks; all
131,072 development/confirmation lives have status zero. Preserve the source, inputs and frozen endpoints.
Next interpret cue dependence with the bounded signal-removal diagnostic under
`outputs/flash_cue_probe_20261018/`, then reassess broader task training and retention. Do not automatically
extend all four searches: late progress and tradeoffs differ by lineage. No second large study is launched.

The four inputs are complete ordered 32-row populations, not four copies of one champion:

| Lineage | Population source |
|---|---|
| AO, descended from SPECK s7 | `results/retained_depth_20261015/runs/balanced/population.json` |
| D90 Z, descended from SPECK s5 | `results/visibility_continuation_20261014/runs/s53220/population.json` |
| SPECK s6 | `outputs/catch_pilot/speck_lmax4_hexprism_sex_s6/population.json` |
| SPECK s8 | `outputs/catch_pilot/speck_lmax4_hexprism_sex_s8/population.json` |

`outputs/flash_ladder_20261017/founder_populations.json` binds their hashes, original IDs and order.
The s6/s8 originals are local artifacts: preserve them and do not silently substitute a public endpoint.

## Search, physics and reporting

[configs/flash_ladder.yaml](../configs/flash_ladder.yaml) defines the application. Shared implementation is in
`src/search.py` and `src/selection.py`; `src/life/evaluate.py` supplies task-labelled draws and within-task
ordinary fitness. `src/evolve.py` dispatches opt-in family runs; legacy configurations retain their old loop.
`src/run.py` and `src/checkpoint.py` handle CLI results, exact continuation and numerical/source pins.

The flash configuration uses epsilon lexicase, 32 current genomes plus up to 32 reproducing archive genomes,
224 offspring, eight initial lives and a 64-genome/eight-life fresh recheck. Every generation contains
50%, 25%, 10% and zero residual brightness, twice each, in both stages. Parents and archive are freshly
measured together; task objectives are ordinary production F, including physical and extinction charges.
Archive membership is bounded, deduplicated and rechecked. Actual archived-parent contributions are logged.
Selection has a separate checkpointed RNG; no score or task label is supplied to a cell.

Use the original `catch_speck_flash5_dim25_l4` law: each target placement is bright for five time units,
then its sensory contribution has the configured residual brightness until ordinary replacement. Background
pings, target movement, capture geometry, rewards and costs continue unchanged. T=1024, d_min=0.5 and d0=1.
There is no new organism clock, visibility input, behavior rule or population-responsive difficulty.
ABI7 is available, but contact-resource dynamics are neutral in these flash lives.

Capability panels are report-only observations at generation zero, every 25 generations, and 60/120.
They measure training-selected representatives from current and archived genomes on flash and older tasks.
The repeated fixed panel is development evidence; it never feeds breeding and is not fresh confirmation.
Whole populations/archives are saved under `populations/gNNNNNN.json`; checkpointed logs record panels.
`scripts/confirm_flash_ladder.py` handles separately frozen balanced/dark roles from generations 0/60/120
on fresh shared seeds. Each reported role is one unchanged genome across brightness levels. Retain both
acquisition and physical costs, low-light captures, paired uncertainty, and the selection/confirmation boundary.

Focused native tests passed: all three selection modes reproduce exact 3+resume3 versus six generations;
archives actually breed; imported rows stay byte-identical at generation zero; fixed panels do not change
the genetic trajectory. See `outputs/flash_ladder_20261017/{evaluator_checks,family_checks,confirmation_checks}/`.
Engineering tests establish implementation behavior, not evolved capability.

## Running safely without repeated permission loops

The user authorizes judgment-led local implementation, environment extensions and bounded experiments.
Report substantial compute budgets before launch and continue authorized work; the historical handoff's
section 5 approval list is superseded for this scope. Do not turn routine reviews or milestones into requests
for the same permission. Paid compute, a project LICENSE and changing the user's central goals remain separate.

Use `scripts/run_local_queue.py`: at most **four workers × two compute threads**, **8 GiB aggregate owned RSS**,
at least **4 GiB host available-memory reserve**, and **nice 10**. Set explicit cumulative CPU/wall caps in jobs.
The completed benchmark measured **13.14 lives/s at two threads** and **40.00 lives/s at eight threads**,
with identical ledgers on its fixed 256-life cohort. Ten calls/2,560 engineering lives used 492.29 CPU seconds,
136.24 wall seconds and 347,471,872 peak owned RSS bytes. These are serial-call measurements, not measured
four-worker throughput or a guaranteed evolution ETA. Final receipt: `benchmark_run/benchmark.json`.

Freeze actual code, configuration, input-population bytes and seed identities before scientific execution.
Never edit active pinned source/configuration, extend its cap, shrink its panel or replace a reporting endpoint.
Resume an existing search with its unchanged config and `--resume`; both RNGs, archives and log offsets are
checkpointed. Queue jobs use the explicit `--train --resume-if-present` wrapper, so an authorized retry
continues training before confirmation. Failed jobs never retry automatically. Set
`ATEN_CPU_CAPABILITY=avx2` before importing Torch for the numerical identity/golden check.
Use the queue's durable identity/exit receipts; do not launch duplicate workers or kill by process-name pattern.
Preserve failures and distinguish an invocation/reader repair from new simulator calls or a scientific retry.

## Scientific invariants and evidence limits

The goal is increasingly capable, general evolved algorithms: one unchanged genome combining abilities and
handling reserved cases without per-case redesign. Tissue remains local and asynchronous throughout a
continuous life. Evolution decides cell roles, development and behavior; death remains genome-driven.
Do not add a global organism channel/clock, hand-scripted behavior, shaped behavioral bonus or a world whose
laws react to population performance. External search/measurement machinery may be centralized; label it as such.
Judge an environment by useful sensory information and accessible partial rewards, never a hand-built-body
success gate. Strong active baselines are measuring instruments, not a target program or a capacity ceiling.

Keep cumulative comparisons honest. The completed depth descendant recovered POOL/persistent acquisition
relative to the degraded Pareto comparator. Versus earlier AO, its POOL capture gain is unresolved
(+0.335938 ±0.230696), while POOL misses increase **2.085938 ±0.276485**; miss point estimates rise in all six
worlds. See `results/resource_patch_depth_20261015/summary.json` and its report. “More captures/fewer misses”
needs its comparator named and does not establish cumulative precision improvement.

Neither those studies nor structural audits establish memory, a gene-count/representation ceiling, superiority
to strong handwritten algorithms, or that a larger body means a richer algorithm. A flash gain can motivate
cue-history/mechanism tests; it is not itself a memory certificate. A bounded null does not prove impossibility.
Maintain ordinary-price and physical-cost comparisons when testing incentives; do not relabel cheapness as skill.

## Artifacts, publication and code map

Keep raw arrays, checkpoints, build products, scratch tests and durable run logs under `outputs/`, not `/tmp`.
Commit reusable code/configuration, concise results and useful selected visuals; avoid duplicating source trees,
whole test directories or large redundant raw files into each result archive. Retain enough hashes and receipts
for audit. Existing public archives, frozen viewers and historical endpoints are immutable evidence.

Append each experiment's outcome to `RESULTS.md`; update this handoff and the evidence map when state changes.
Commit completed milestones and push to public `origin master` (`https://github.com/superj6/cell-dev`).
Use the exact trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
Do not rewrite history or change licensing. Python lines are at most 120 characters; use focused meaningful
tests and Ruff, then integration checks appropriate to the change rather than repeatedly rerunning all history.

Core physics: `src/life/{kernel.c,reference.py,spec.py,build.py}` and [LIFE_ABI.md](LIFE_ABI.md).
Maintained browser engine/UI: `results/atlas/play/lifesim.js` and the task viewer helpers. Keep C/Python/JS
bitwise parity; fast C omits hashes, so a fast-ledger replay alone is not a full-trajectory hash proof.
The population explorer and frozen behavior viewers linked in `RESULTS.md` help inspect actual organisms;
visual illustrations do not replace aggregate fresh-life evidence.
