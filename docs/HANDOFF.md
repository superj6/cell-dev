# Handoff: cell-dev — 2026-10-20

This is the operating summary. Read [SEARCH.md](SEARCH.md), [RESEARCH_STATUS.md](RESEARCH_STATUS.md),
[TASK_VARIATION_PLAN.md §0](TASK_VARIATION_PLAN.md), and the newest entries at the bottom of
[RESULTS.md](../RESULTS.md). The
[previous full handoff](https://github.com/superj6/cell-dev/blob/86d44a1/docs/HANDOFF.md)
preserves the historical details; its old approval gates and proposed next studies are not the current queue.

## Current direction and status

**Running (2026-10-20): the open-world pilot v2** (eco v2 worlds, LIFE_ABI.md 9.8.7). [OPEN_WORLDS.md](OPEN_WORLDS.md) (§11 "As built") — five
open-ended worlds (plume foraging, predator field, home-base foraging, evasive prey, farming), trained together
from generation 0 on ABI 8 (nine gene-tuned modality slots and the eco world; contract in
[LIFE_ABI.md](LIFE_ABI.md)). Per-life worlds come from `src/life/ecology.py`; the search is
`src/open_search.py` (allocation with a floor, racing, behaviour grids; [SEARCH.md](SEARCH.md) "Open-world
search").
- **Runs:** D90 and AO lineages (padded to ABI 8) × arms U / LP / LPD, plus one from-scratch population in LP,
  G = 100 each. Configs `configs/open_worlds_pilot_*.yaml`.
- **Launch:** `outputs/open_worlds_pilot_v2/`, a frozen checkout at 0dd707e. `queue/monitor.json` there is
  authoritative for status.
- **Pilot v1** (`outputs/open_worlds_pilot/`, eco v1 worlds) was stopped after 14–16 generations, when the
  headroom check found world flaws. It is kept as cost and noise calibration: 0.54 CPU-hours per generation per run.
- **Budget:** four two-thread workers at nice 10, 450 CPU-hours / 120 elapsed hours, 8 GiB RSS cap.
- **Purpose:** a calibration (cost per life, noise, correlations, allocator behaviour), not a stage.
- **Headroom check:** OPEN_WORLDS.md §7, simplified; [results/headroom_20261020](../results/headroom_20261020/README.md).
- **Ask the user** before any rented compute; the main run (G = 300–400) may need it.

**Completed study:** four lineages ×250 generations across eight conditions in
`configs/multitask.yaml`. All eight influence breeding: POOL, persistent pursuit, two flash levels,
delayed matching, replenishing patches, contact-triggered food and harmful-target avoidance.
Each lineage preserves all 96 pre-flash/final-flash current/archive genomes at startup. The archive
has 64 slots, current population 32, offspring 224; 16 initial +16 recheck lives cover every task.
Fresh rechecking filters 128 candidates down to 96 breeding slots. Whole checkpointed state resumes exactly.
Run preparation and durable launch receipts are under `outputs/multitask_20261018/`; its `queue/monitor.json`
is authoritative for actual running status. See [SEARCH.md](SEARCH.md) for exact selection/reporting rules.
Budget: at most 7,651,336 lives including startup checks, 600 CPU-hours/96 elapsed hours, four two-thread
workers, nice 10, 8 GiB owned RSS and 4 GiB host-memory reserve. The fixed eight-condition benchmark
measured 11.62 lives/s at two threads and 38.26 at eight, with identical ledgers. Estimated elapsed time
was 2–3 days; actual elapsed time was 25.75 hours. Checkpoints were saved every five generations.

**Completed 2026-10-19 19:27 UTC:** all four workers finished on their first attempts from pinned source `e69858f`.
`launch_manifest.json` binds actual inputs, resolved configurations and commands; `launch_verified.json`
checks all 96 imported rows per lineage byte-for-byte and confirms startup numerical identities.
All eight training objectives were present. Final evaluation is complete; no worker remains in this queue.
Actual use: 188.77 CPU-hours, peak owned RSS 1.26 GiB. Preserve the pinned checkout/configurations and raw data.

[Final report](../results/multitask_20261018/REPORT.md): D90 improves acquisition across pursuit and resources,
including reserved variants. All four improve contact-produced harvest in both trained and reserved worlds;
s6 nearly doubles it (2.160 →4.186). AO reduces harmful taps while catching more food. Shape matching remains
strongly broad-biased; dark-flash captures regress in s6/s8, and cost savings sometimes mask food losses.
The 12 reporting genomes were selected from full stage cohorts, including all 96 starting rows. All four g0
choices are flash-trained, unlike the earlier illustrative original-row comparisons. Independent raw auditing
checks all 393,216 development/confirmation lives and all selected endpoints. No memory mechanism is established.
Next priorities: explain contact-production dependence, preserve behavioral abilities alongside costs, and
advance the obstacle-navigation direction. No follow-on experiment has been launched by this completion report.

Saved mid-run visual examples are available in
[the interactive comparison](../results/multitask_examples_20261018/examples.html) and
[its report](../results/multitask_examples_20261018/REPORT.md). These show AO through generation 100 and
D90/s6 through 75 using the existing training-POOL reporting role, not final generalist endpoints.
s6 shows early shrinkage, some internal-cell regrowth and improved resource collection relative to its
first original row, with pursuit still lower. Exact genetic replay verifies crossover and mutation
inheritance; it does not establish a causal circuit. The 27 fixed illustrative C/JS replay pairs agree
on all ledger bits and full hashes. Keep these examples separate from progress-panel averages and fresh
confirmation. The active evolution inputs, policies and budgets were not changed for this visualization.

One reporting genome per stage (0/125/250) was chosen on training-only development lives, then tested
unchanged on eight trained conditions plus eight reserved variations, 512 fresh lives per condition.
Report gains/losses in acquisition and physical costs, both matching classes and contact-origin food.
Do not substitute task-specific winners or call a specialist portfolio individual generalization.

The earlier **four ancestral populations ×120 generations** on the flash brightness ladder are complete.
Four brightness levels are four settings of one pursuit family, not four distinct capabilities.
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
The signal-removal diagnostic is also complete: D90, s6 and s8 show increased acquisition benefit from
target cues, while AO's change is unresolved; all four also gain without target signal. This does not
isolate neural memory. It used 4,096 new lives in 434.72 CPU/64.86 wall seconds; an independent raw audit
passes. See [the cue report](../results/flash_cue_probe_20261018/REPORT.md). Preserve these frozen endpoints;
the broader study starts from complete populations and has its own individual-generalization assessment.

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

The completed flash configuration used epsilon lexicase, 32 current genomes plus up to 32 reproducing archive genomes,
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
