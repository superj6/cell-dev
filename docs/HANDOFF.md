# Handoff: cell-dev (2026-10-13)

For an agent picking up this project. Read this first, then `docs/TASK_VARIATION_PLAN.md` section 0 (the current plan)
and the last few entries of `RESULTS.md`.

**Pickup progress (2026-10-13).** E1, E5 and E6 tooling are implemented; see the newest `RESULTS.md` entries. Life runs now
checkpoint every 25 generations; `src.run --resume` restores both RNGs and verified log offsets with strict source
and numerical pins. Use `--stop-after` with the original total generation target for a controlled interruption.
The 3 + resume + 3 versus 6 CLI tests pass in BELL and SPECK. Old pilot populations still cannot resume exactly.
The JS wound port has C/Python/JS truth lives, and the atlas embeds it. E6 readouts and the small-batch CLI are
documented in `docs/PROBE.md`; BH3 on matched evolved footprints is still unmeasured.
E7 preparation is in `results/taskvar/`: preregistration, recovered controllers, strict admission checks, bounded
replay/parity evidence, and measurement/gradient commands that default to dry-run. Full G0-G5 measurements are still
pending; see its gate table for approval/ABI dependencies. Prediction's recovered ablation measures the broader
moving-target model, so it cannot yet isolate prediction. No pending decision below has been assumed answered;
the work below uses bounded local studies, with no rented compute or large evolution matrix.

**Latest bounded measurement (2026-10-13).** `results/pool_mutants_20261013/` records a preregistered 64-mutant screen
per parent (s5/s7) in base-fast and POOL, with fresh 512-life confirmation and 256-life four-arm lateral lesions.
Gains are +0.846 ± 0.136 (s5/base), +0.638 ± 0.116 (s5/POOL), +0.755 ± 0.129 (s7/base), and +0.263 ± 0.092 (s7/POOL).
The first three clear 3 SE and +0.5 F, earn more capture income despite higher costs, and depend more on lateral
spikes. s5 selects the same genotype in both worlds. This establishes nearby improvements, not a new algorithm or
sustained accumulation. All 26,752 planned lives finished within 1.44 CPU-hours; the raw public archive reanalyzes
exactly. This is a separate bounded exploration, not the full G2/all-world study. Production selection shortlists on
3 lives, rechecks on 4 more, and keeps parents by their pooled 7-life mean.
The [lesion-semantics erratum](../results/pool_mutants_20261013/ERRATA.md) corrects the older archive's wording:
`lateral_off` suppresses new in-plane spike sends after the fork, retains their charge, and leaves already emitted
messages in flight. Vertical spikes and chemical packets continue. The archive's pinned bytes remain unchanged.

**Completed follow-through (2026-10-13).** `results/followthrough_20261013/` preserves three further fixed experiments:

- A: the unchanged winners have positive effects beyond 3 SE when averaged across T768/1024/1536 in fast conduction.
  The four paired gains are +0.586 ± 0.167, +0.953 ± 0.170, +0.532 ± 0.160 and +0.440 ± 0.120 F in the order above.
  Old-conduction T1024 effects remain unresolved; s5's fast-minus-old interaction clears 3 SE in both worlds.
- B: 224 new ordinary mutants of row38 compete with 32 founder copies. Both 3+4 and 12+16 scoring select row148.
  Its fresh additional gain is **+0.064 ± 0.142 F: no confirmed second step**. It remains +1.012 ± 0.129 F above
  original s5. This one cohort offers no winner-quality separation between scoring budgets or evidence of their
  relative efficiency at equal compute.
- C: the first chemical-input allele alone improves F by +0.548 ± 0.138 in base and +1.064 ± 0.115 in POOL.
  The second allele's added effect and the interaction remain unresolved. Both changes are not required together
  for a useful intermediate; this does not identify the circuit mechanism.

A/B/C completed 20,124 research genome-lives in 4,216.849317 monitored CPU-seconds (1.17 CPU-hours), with at most
four workers. Separate validation used 294 T32 lives. The offline `results/followthrough_20261013/watch.html` shows
the original s5 beside row38 on fixed descriptive seed 51,840,000. Its four T32 C lives plus four JS replays matched
all ledger bytes and hashes, costing 6.72 additional CPU-seconds; full animations remain illustrations.

**Currently running / queued.** After protocol commit `7462bbf`, two ordinary 16-generation sexual continuations
from the same row38 founder are running at `outputs/autonomous_continuation_20261013/`, seeds 51089/51090, four
workers total, shared cap 10,800 CPU-seconds. Read `budget.json` for live status; do not start another simulation
while all four workers are occupied. Initial populations contain one exact founder plus 31 point-mutated copies;
no founder is permanently protected. Each final population rank0 is frozen before fresh three-duration confirmation
against row38 and original s5 on block91. Checkpoints are every four generations with target16 fixed from startup.
Preserve engine/search and measurement-helper source pins while active; exact resume uses the E1 checkpoint.
The existing-ABI tissue-freeze/lateral experiment E is preregistered at `outputs/autonomous_frozen_20261013/` on
block92, but scientific scoring has not started. Its two workers wait until D has at most one two-worker job left.
Its tooling passed 16 short validation lives, separate from A/B/C's validation counts above. No D/E scientific result
exists yet. See `results/taskvar/prereg.md` for both fixed protocols and `RESULTS.md` for A/B/C.

## 1. What the project is

- **Goal, in the user's words:** evolve "genetic codes" for how cells divide and change, so that the grown tissue runs
  "some message passing algorithm that performs a task using the cells".
- **The model (BODY-1, ABI 3).**
  - Every cell runs the same genome: a 16-gene regulatory network (GRN) plus a leaky integrate-and-fire neuron.
  - The genome grows one zygote into a layered body on a hex-prism lattice:
    - z=0 senses;
    - z=1 acts (twitches the body);
    - z>=2 is hidden.
  - Cells only hear their neighbours, through spikes with conduction delays.
  - There is no global clock: the simulator is exact and event-driven.
- **The world (CATCH/SPECK).**
  - The body is a dot chasing a drifting target. Sense cells get receptor pings from the target's glow.
  - An act cell's spike nudges the dot. A spike of the hotspot cell (0,0,1) is a tap: inside the catch zone it is a
    capture (R_cap 500), otherwise it costs c_miss 10.
  - Cells cost c_live 0.02. Fitness F = income per unit time minus costs.
- **Evolution:** (32+224) selection with crossover and a two-stage recheck (K64 L4), common random numbers, and a life
  length drawn from {768, 1024, 1536}. About 1,070 lives per generation, at about 0.1 CPU-s each.

## 2. Non-negotiables and how the user works

**Standing requirements.**
- One continuous life per evaluation.
- No central clock.
- Local rules only (sensing, action, messaging).
- Death is driven by the genome.
- Minimal hard-coding: list every fixed rule with its reason.
- Evolution decides roles.
- Growth is bounded by physics plus costs.
- Fitness is task performance; no shaped score.

**Standing approval** (user, 2026-10-07): "do whatever minor tweaks you think will help us get the emergent behavior we
want without removing the central goals - local, async, self discovered behavior algorithm".
- Make and report minor tweaks without asking: world constants, selection details, logging, gates.
- **Ask first** before:
  - any global channel or clock in the organism;
  - hand-designed behaviour;
  - changing a stated goal;
  - spending money;
  - an ABI change;
  - a world that responds to the population.

**The newest principle** (user, 2026-10-10): "ideally the system should evolve to find capabilities beyond what hand
creation can do, that's the whole point".
- Never gate a world or task on whether *we* can hand-build a body that wins.
- Judge worlds by what the sense information pays (section 4 below). Hand-built bodies are yardsticks to beat.

**How the user likes to work.**
- Keep working autonomously while useful experiments remain within the authorized scope. A completed study or
  commit is a progress milestone, not a reason to stop. Report before large runs; the explicit approval boundaries
  above still apply.
- Explain new concepts plainly, with small diagrams, *before* asking a question. Ask one decision at a time and give a
  recommendation. They often discuss rather than pick from a menu.
- Report honestly: paired differences with SE on fresh lives, caveats, failures. Say what was skipped.
- The user cares most about watchable outcomes (atlas, playground) and about rollouts that could run natively on
  hardware. The search loop around them may use any ML machinery.
- **Commits.** Commit at milestones, ending the message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  Push to `origin master` (https://github.com/superj6/cell-dev, public).
- **House style.**
  - Every experiment gets a `RESULTS.md` entry (newest at the bottom).
  - Docs use short bullets, tables and plain words.
  - Python lines are at most 120 characters (`tests/test_style.py`); `ruff check src scripts tests` must be clean.

## 3. Where things are

| Path | What |
|---|---|
| `src/life/kernel.c` | exact event-driven C kernel; `-DLIFE_FAST` build skips hashes and is bitwise equal otherwise |
| `src/life/reference.py` | Python reference, bitwise equal to the kernel |
| `results/atlas/play/lifesim.js` | JS port, bitwise equal (`node test_lifesim.js`); glibc libm ports under the LGPL |
| `src/life/spec.py`, `build.py` | ABI, decode, world presets; `build.run(...)` runs lives |
| `src/life/evaluate.py`, `src/evolve.py`, `src/run.py` | evaluator (`fast_kernel`, elastic threads), selection (`rank_desc`), CLI |
| `src/life/handbuilt.py`, `probe.py`, `analysis.py` | hand bodies (reflex, router), mechanism probes, `fresh_seeds` and `paired` |
| `scripts/life_gates.py`, `scripts/sweep.py` | gates (SPECK: `--world speck`, GS1-GS6); sweeps (`--max-threads`) |
| `configs/life_speck.yaml` | the SPECK L4 config used by the pilot |
| `docs/TASK_VARIATION_PLAN.md` | **the current plan**: section 0 supersedes the older sections' hand-built gates |
| `docs/ROADMAP.md`, `POST_PILOT_CALLS.md`, `ALTERNATIVES.md`, `HARDWARE_PATH.md` | directions, calls, substrates, hardware |
| `docs/LIFE_ABI.md`, `LIFE_GATES.md`, `PROBE.md` | the simulation contract, gate verdicts, the probe toolkit |
| `results/catch_pilot/` | pilot analysis, mechanisms, compute audit |
| `results/taskvar_study/` | hand-built headroom study; `engineering/kernel_x.diff` holds the prototype blink/flip kernel |
| `results/open_headroom/` | latest study: controller harness, controllers, data (see its README) |
| `outputs/` (gitignored) | run outputs; `outputs/catch_pilot/*/best_genome.json`, `population.json`; `outputs/openhr/` |

## 4. Where the findings stand

- **Pilot (2026-10-09).**
  - SPECK L4 reached the skill bar in 7 of 10 runs.
  - Evolved bodies regrew the column reflex and added real local computation: neighbour voting, cooperative detection
    with feedback inhibition, gain set by crowding.
  - No evolved body routes signals like the hand router, and hidden planes are unused.
- **Task-variation study (2026-10-10, hand-built controls).**
  - Routing pays in POOL (sigma 0.4, lam_s 4, d0 0.5, d_min 0.25).
  - Regeneration pays.
  - Its gates were then replaced; see the next item.
- **Open headroom (2026-10-10, latest).**
  - **The tool.** A central controller that sees only the body's own pings, actions and clock (measurement only) is
    replay-checked for leakage.
  - **Base and POOL, 1,024 fresh lives:** it beats the best reflex by **+13.3 F in base and +13.2 in POOL**. With
    tissue-like handicaps it keeps +9.2 / +9.6.
  - **Our bodies use a quarter or less of that:** the evolved s5/s7 score -1.3 / -1.9 in base, the hand router +3.6.
  - **What pays** is active search from a belief (path integration of its own strokes, pings and the absence of
    pings).
  - **Switching:** in the motor-flip mix (50% of lives flip mid-life), the flip detector adds +12.7 F.
  - **Memory:** in the flash world, acting on memory while the target is dim adds +24.6 F. In renewal blink worlds it
    adds +2-4.
  - **Not yet measured:** prediction, discrimination, and the mutant gradient test.

## 5. Decisions the user has not answered yet

From `docs/TASK_VARIATION_PLAN.md` 0.9. My recommendation is yes on each.
1. Replace the hand-built gates with the admission rule (0.4).
2. Port within-life world changes (motor flip, blink, flash) into kernel, reference and JS as ABI 4 (about 5-6 pd).
3. The revised family (base 25%, POOL 25%, flip mix 25%, flash 12.5%, blink 12.5%), with arm M as POOL alternating
   with POOL plus flip mix.
4. After round 1, a scratch pilot of co-evolving prey: a world that responds to the population. The user also sets the
   prey's physical limits.

Earlier, still open:
- section 6 decisions 1-4: raw-F family fitness, wounds in selection, the fixed switching calendar, renting one 192-core
  box at $15-35 spot (cap $120, and only after resume plus a replay check);
- `docs/ROADMAP.md` "Decisions needed";
- a project LICENSE (the user's choice).

## 6. Next steps, in order (plan 0.7 and section 3)

Staged, so that arms B and P can launch before the ABI 4 port lands.

| Step | What | Approval | Estimate |
|---|---|---|---|
| E1 | **Implemented and replay-tested:** checkpoint/resume with determinism pinning | none | done |
| E2 | d0 0.5 / d_min 0.25 as the base; re-run GS1-GS6 (`scripts/life_gates.py --world speck`); re-tune reflex and router | report only | 0.5 day plus CPU |
| E3 | Family harness in `evaluate.py`, behind a flag that is off by default; prototype `results/taskvar_study/engineering/fam_eval.py` | decision 1 to *use* it | 0.5-1 day |
| E9 | ABI 4: flip (t_flip), blink, flash with dim level, in all three engines with truth lives | decision 2 | 0.5-1 day, the riskiest |
| E4 | Generation calendar for arm M: phase = floor(g / E) mod 2 | section 6 decision 3 | hours |
| E5 | **Implemented and parity-tested:** KILL (wounds) port to lifesim.js and embedded atlas | none | done |
| E6 | **Tooling implemented:** lateral shares, relay chains, BH3 data contract and ABI-3 BH4 readouts | none | matched BH3 scoring pending |
| E7 | **Tooling and bounded diagnostics complete:** confirmations, transfer, second-step cohort and allele effects archived | none for tooling; report before large runs | full G0-G5/all-world studies pending |
| E8 | Rental kit: pinned image, bitwise replay check on the new host | renting decision | hours |

E1 in detail:
- Every 25 generations, save the population, ids, origins, generation, the torch generator and the tie generator
  (`rank_desc`), and the log offsets.
- Add `run.py --resume`.
- Pin ATEN_CPU_CAPABILITY, the torch version, the libm FMA path and the kernel .so hash, and replay a golden life at
  start.
- Test: 3 generations + resume + 3 generations must equal 6 generations byte for byte, with wall times stripped.

After E1-E3 and their gates, launch **B (base) and P (POOL)**: 12 seeds x 500 generations, seeds 100-111. F, M and W
follow after E9. The matrix takes 4-10 hours on the rented box, or 4-8 days on the laptop.

Pre-registered criteria are R1-R3, G-1 to G-3 (plan 4.4) and BH1-BH4 (plan 0.6).

## 7. Operational notes and gotchas

**Machine.**
- 14 cores; CPUs 12-13 are slow, and about 8 threads is fastest. About 20 GB of RAM is free.
- It is shared with the user's other projects, and the load has hit 30. Check `uptime` before big jobs and keep within
  a thread budget.

**Commands.**
- Tests: `.venv/bin/python -m pytest -q` (about 1 minute; `-m slow` for the long ones).
- Lint: `.venv/bin/ruff check src scripts tests`.
- JS: `node results/atlas/play/test_lifesim.js`.
- The kernel compiles itself on first use (gcc, OpenMP).

**Never use /tmp for anything long.**
- A reboot wiped it mid-study. Put study scripts and results in `outputs/<study>/` (gitignored) and write results
  incrementally.
- Copy key artifacts into `results/` when committing.
- Subagent transcripts survive under `~/.claude/projects/-home-jgon-project-ml-cell-dev/*/subagents/workflows/`.
  `results/open_headroom/recover_replay.py` rebuilds files from them.

**Never `pkill -f`:** it can kill your own shell. Kill by PID.

**Exactness.** The kernel, reference and JS must stay bitwise equal. Any world or ABI change needs all three plus
truth lives. Only the fast build may skip hashes.

**Statistics.**
- Compare on the same fresh lives (common random numbers) and report paired mean ± SE.
- "Best reflex" means the better of the frozen reflex and the reflex re-tuned in that world, picked *on fresh lives*:
  re-tuning overfits its tuning lives by 0.15-0.5 F.
- Selection noise is large: the paired per-life SD is about 3-4 F.

**Prices.** The prices are frozen. c_live is load-bearing: at x3 the router's lead nearly vanishes.

**Seeds already used** (`fresh_seeds(n, seed0)`):
- 30-31.35M and 39-39.1M: earlier gates and studies;
- 40.1-40.8M: the task-variation study, with 40.8M + 5,000·block reserved for the plan's gates, confirmations and
  held-outs;
- 42.0-42.2M: tests;
- 43M + 10,000·block: open headroom, blocks 0-49, 100-179, 200-239, 300-419;
- 49M: a design diagnostic.
- 45.05M: short JS wound truth cases; 46M: E6 readout validation.
- 51M + 10,000·block: E7, reserved in `results/taskvar/prereg.md`; blocks 0-9 are validation only.
  A T32 validation smoke also spent block10's first two seeds; future G2 must start at 51,100,002.
  Blocks80–83 hold the completed nearby-mutant study; block84 is reserved for fixed descriptive viewer lives;
  blocks85–88 hold completed transfer/second-step/factorial scoring. Block91 is reserved for the running
  continuations' endpoint confirmation, and block92 for the queued frozen-tissue lesion. Search seeds51089/51090
  use the production hash namespaces; they are not decimal blocks89/90, which remain unallocated.
- Use 45M or above for new work.

**The controller harness.**
- Location: `outputs/openhr/harness/`, with a committed copy in `results/open_headroom/harness/`.
- Rebuild: `python3 make_ckernel.py && python3 make_ckernel.py --fast`.
- Test: `PYTHONPATH=.:<harness>:<harness>/tests .venv/bin/python -m pytest -q <harness>/tests/test_harness.py` (19
  tests).
- The base/POOL re-tuned reflex knobs survive in `results/open_headroom/data/headline.json`, under
  `reflex_knobs_verify[world].knobs`. Keep any new tuning parameters with their own tuning/verification seeds.

**Interrupted, unverified work in `outputs/openhr/`.**
- `prediction/`, `discrimination/`, `map/` (a 30-world headroom map) and `gradient/` (the mutant test).
- The prediction agent printed an ES-tuned controller at about F 37 against a reflex at about 2.1 in the fast-target
  world. It is unchecked, so re-establish it with the leakage test before trusting it.

**Pilot bodies.** `outputs/catch_pilot/speck_lmax4_hexprism_sex_s{0..9}/best_genome.json`. s5 and s7 are the usual
references.
