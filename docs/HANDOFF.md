# Handoff: cell-dev (2026-10-14)

For an agent picking up this project. Read this first, then `docs/TASK_VARIATION_PLAN.md` section 0 (the current plan)
and the last few entries of `RESULTS.md`.

**Primary objective, clarified by the user (2026-10-14):** advance the sophistication of the algorithms we can
make emerge, especially in more interesting environments. Prioritize environments that reward richer computation.
Use mechanism analysis and search replication to guide and measure that progress; they are not prerequisites
that must be exhausted before exploring richer environments. The closed research batch remains closed.

**Autonomous work resumed (2026-10-14).** At the user's request, new bounded studies now prioritize richer
existing ABI 3 environments. U is prepared and reviewed: two four-generation ordinary searches from the fixed
I decoy winners, then four-condition fresh confirmation, under 7,200 CPU-seconds with half reserved for
confirmation. See `results/decoy_evolution_20261014/`. V prepares an unchanged external moving-target
information measurement, with independent review pending and no research release. Neither restarts the closed
P/Q/R batch or releases held S. No ABI change, new organism behavior, paid compute or population-responsive
world is authorized by these registrations.

**Wrap-up complete (2026-10-14).** All released research processes have exited. P completed both searches but
hit its fixed CPU cap during fresh confirmation; it has no confirmed fitness outcome. Q and R stopped at their
dependency guards before any measurement. S's scoring-budget comparison remains fully prepared but held, with
no readiness marker or run. Its unchanged protocol also requires completed P and R, which these terminal
statuses do not satisfy. Do not restart or launch experiments from those closed-batch prepared plans. The consolidated review
and terminal accounting are at the end of `RESULTS.md`.

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

**Completed continuations and fixed-tissue experiment (2026-10-14).** Both ordinary 16-generation sexual
continuations finished, including fresh confirmation. Relative to row38, final rank0 gains are **+0.633 ± 0.188**
and **+0.756 ± 0.202 F**, averaging T768/1024/1536 within each of 256 shared seeds. Both exceed 3 SE and +0.5 F;
T768 alone remains unresolved. Their total gains over original s5 are +1.602 ± 0.173 and +1.726 ± 0.182 F.
Both earn more capture income despite higher costs and larger bodies. One clicks and moves less, the other more.
This establishes additional progress in two fixed continuations, not general search reliability or a new algorithm.
`results/continuation_20261013/` records the 36,012-life study, final checkpoints, populations and lineage;
the monitor used 10,013.037438 of 10,800 CPU-seconds. No invalid/mismatched search evaluations occurred.

The first-step row38 gain also remains with tissue frozen after t768: +0.944 ± 0.159 F during t800..1536.
Its added lateral dependence is **+1.692 ± 0.178 F**, versus +2.498 ± 0.174 without freeze. All 512 pairs per
genotype pass constant-tissue checks; no guards occurred. This narrows the developmental explanation, but the
parent and winner keep different footprints and freeze also stops gene-regulatory computation. It establishes
neither adult maturity nor a new algorithm. `results/frozen_20261013/` archives 4,096 research lives using
1,216.191173 of 3,600 CPU-seconds; the separate 16-life validation is labeled.

**Decoy information measurement completed (2026-10-14).** The existing external controller beats the better
reflex at its own 56-cell footprint by **+11.754 ± 0.170 F** in the existing harmful-decoy world. Disabling its
broad decoy model removes **+9.902 ± 0.194 F**; the best of three do-less variants gains +0.966 ± 0.107 F.
All descriptive plan-0.4 checks pass, without automatically admitting a selection world. It uses old conduction
and T1024; central computation is free. `results/discrimination_20261013/` archives all 3,584 lives and the
independent reanalysis, using 496.441665 of 1,800 CPU-seconds. Its erratum corrects fast hashes: constant initial
values, not zero, and neither supplies replay evidence. Pinned preparation bytes remain unchanged.

**Structural policy completed (2026-10-14).** G's two fixed final endpoints differ from matched ordinary D
endpoints by **−0.252 ± 0.209** and **+0.325 ± 0.193 F**, averaging three durations within 256 fresh shared seeds.
Neither establishes a policy advantage. Both improve over row38 (+0.745 ± 0.189 and +1.197 ± 0.192 F), beyond 3 SE
and +0.5 F. Each ends with 9 active genes and one active duplicated-origin gene. J now finds zero single-copy knockout
effects in those endpoints, as recorded below. All 18 silent-duplication neutrality lives and full recorded-genetics
replay pass. The 37,548
research lives finished in 10,942.922121 of 14,400 worker CPU-seconds; evidence is in `results/structural_20261013/`.

**Hidden-message contribution measured (2026-10-14).** H completed all 6,144 lives on 512 shared block94 seeds,
using 2,674.948141 of 3,600 CPU-seconds. With tissue frozen at 768 and accounting over 800..1536, D51090 loses
**0.956 ± 0.172 F** when new hidden-cell sends stop. Its added loss over row38 is **+0.794 ± 0.207 F**, beyond 3 SE;
D51089's added loss is unresolved (−0.193 ± 0.190 F). Both gain lateral dependence (+2.842 ± 0.194 and
+2.470 ± 0.202 F). Freeze removes 0.914 ± 0.214 F of D51090's normal gain; it also stops gene-regulatory and
phenotype updates, so that contrast does not isolate development. All frozen triplets have constant tissue;
no guards, extinction or invalid flags occurred. `results/hidden_20261014/` preserves independent raw-data audits.
This establishes hidden-message contribution in one fixed descendant, not its algorithm or matched-footprint use.

**Decoy mutant screen completed (2026-10-14).** I's complete original 64-mutant panels select s5 row32 and s7
row1, with fresh 512-life gains of +1.431 ± 0.096 and +1.178 ± 0.102 F. Most of each gain comes from lower costs;
terminal cells fall by 38.525 and 22.660 while captures rise by 0.734 and 0.941. Absolute winner F is −0.240/+0.458.
This does not demonstrate discrimination or change world admission. All 11,328 lives on blocks95–97 completed
in 3,105.780628 of 3,600 CPU-seconds without guards/invalids; full independent evidence is in
`results/decoy_gradient_20261014/`. The prospective queue-release exception was unused.

**Copied-gene and trace measurements completed (2026-10-14).** J tests the only active duplicated-origin
copy in each G endpoint: slot14/origin56 and slot9/origin21. Their single-knockout effects are exactly zero on
both 512-life selection and 512-life fresh confirmation; all 60 scored/ledger columns match byte for byte.
All 4,096 research lives finished in 1,197.683334 of 7,200 CPU-seconds. This does not establish dispensability in
other genetic backgrounds. `results/duplicate_use_20261014/` preserves full ancestry and intervention evidence.
K's twelve reference traces match twelve C validation lives bitwise in all 57 ledger columns. Together they use
786.219558 of 1,800 CPU-seconds; startup validation is also inside that cap. Both D descendants have larger
lateral-hop shares among attributed receptor-origin chains; four descriptive seeds cannot identify an algorithm. All raw tables are preserved in
`results/traces_20261014/`; reanalysis needs the pinned repository source.

**Second lineage completed (2026-10-14).** Both ordinary s7 continuations improve over fixed row29:
**+0.900 ± 0.143** and **+1.072 ± 0.145 F**, averaging three durations within 256 fresh paired seeds.
Total gains over original s7 are +1.267 ± 0.146 and +1.439 ± 0.146 F. All six duration-specific gains over
row29 exceed 3 SE. Capture income rises more than costs; both grow larger, click and move more. This establishes
further adaptation in two searches from the second lineage, not a new algorithm or general search reliability.
All 36,012 research lives finished in 7,695.470841 of 14,400 CPU-seconds. Full recorded genetics and public raw
reanalysis pass; fresh confirmation has no guards/invalids. Initial-search guards (16/21 lives) retain penalties.
Evidence is in `results/s7_continuation_20261014/`.

**Copied-gene follow-up completed (2026-10-14).** Source inspection proves G51089's copied gene has no
outgoing physical influence, even after deleting its source; private regulatory state can differ. M therefore
reduced its original 4,096-life preparation to a four-arm G51090 test, preserving the original and amendment.
On 512 fresh seeds the copy/source interaction is exactly zero. Removing the source loses **7.277 ± 0.129 F**
with or without the copy; both copy-knockout comparisons match all 60 scored/ledger columns bitwise.
This finite G51090 result is not a universal silence proof or evidence of functional duplication. All 2,048
research lives completed in 410.154069 of 1,800 CPU-seconds; no guards/invalids occurred. Independent full
ancestry, packing and ledger reanalysis is in `results/gene_interaction_20261014/`.

**Information duration check completed (2026-10-14).** The unchanged external C4 controller remains above the
retained retuned reflex by **+13.257 ± 0.223 / +13.547 ± 0.204 F** in base/POOL at T768, and
**+13.112 ± 0.168 / +13.218 ± 0.151 F** at T1536. All fixed smaller/quieter variants score worse than that
reference. These are separate 512-paired-life comparisons, with no duration-paired inference or world-admission
decision. C4 is an external instrument with free computation, not an evolved organism. All 12,288 research and
40 validation lives completed in 1,385.715510 of 3,600 CPU-seconds. Full replay/parity evidence and independent
reanalysis are in `results/information_duration_20261014/`; capability-world G5 remains pending.

**Regulation study completed (2026-10-14).** With cell composition held fixed, the five-input gene-network
mask removes **+2.849 ± 0.175** and **+2.940 ± 0.176 F** more from D51089/D51090 than row38. All 4,608 lives
completed in 2,283.250535 of 3,600 CPU-seconds, with constant tissue and no guards/invalids. Own input losses
are 10.326/13.175/13.265 F; own full-freeze losses are only 0.111/0.290/0.604 F. Static contact information is
also masked, so this establishes specified input dependence, not learning or use of changing evidence.
`results/regulation_20261014/` contains the raw audit. The separate completed-data trace reanalysis in
`results/trace_hidden_20261014/` suggests inhibitory hidden-to-act feedback but does not establish its fitness role.

**Completed-data diagnostics (2026-10-14).** Rechecking changes 36.5% of parent slots across all 96 completed
D/G/L generations, with 76 strict displacements of the initial top score. This shows selection sensitivity to
finite samples, not better final fitness or a reason by itself to increase scoring. The full audit is in
`results/selection_noise_20261014/`. In K's saved normal-growing traces, 96.78%/98.21%/97.71% of cells alive at
t800 later change a quantized neural property for row38/D51089/D51090. Later births are excluded; the
counts establish continued updates, not their fitness value. `results/phenotype_updates_20261014/` contains
all twelve raw-event checks and per-life tables. Both analyses simulate zero new lives.

**Terminal and held studies.** P completed both ordinary 16-generation searches from the fixed D endpoints,
then stopped during confirmation at 14,381.265501 of 14,400 CPU-seconds. Both search exits were successful;
confirmation was terminated by the fixed budget monitor. Completed checkpoints and raw partial confirmation are
preserved in `results/next_step_20261014/`, with no partial endpoint comparison or confirmed fitness outcome.
Q's frozen s7 hidden/lateral-message study and R's local-weight-update decomposition ran zero measurement lives:
the dependency guards stopped them after P and Q, respectively. Their 14.165054/10.228412 CPU-seconds were
waiting/monitor overhead; separate `operational_status/` bundles preserve exact terminal records and original
preparation bytes. R's planned combined identity/phenotype clamp would separate continued effective receive-weight
updates from full freeze; autonomous chemical relaxation remains an alternative to sensory adaptation.
S is held without release. No research process remains active, and no budget was extended. Future allocations
should estimate developed-founder costs and reserve enough CPU for fresh confirmation. P's incomplete outcome
is a resource-planning limit, not evidence of an evolutionary plateau. Long-running work remains under
`outputs/`, with final evidence under the corresponding `results/` directories.
The D viewer at `results/continuation_20261013/watch.html` has eight C plus eight JS T32 validation lives:
all 57 ledger columns and five event hashes match bitwise, within 9.331079 of 15 validation CPU-seconds.
The s7 viewer at `results/s7_continuation_20261014/watch.html` has the same eight-case C/JS parity coverage,
using 11.250013 of 15 CPU-seconds. Both viewers start paused and retain their original scientific archives.
Full animations are illustrations. No unanswered approval decision has been assumed resolved.

## 1. What the project is

- **Goal, in the user's words:** evolve "genetic codes" for how cells divide and change, so that the grown tissue runs
  "some message passing algorithm that performs a task using the cells". The ultimate goal is to advance the
  sophistication of those evolved algorithms, especially in more interesting environments. Higher scores on the
  present task are useful evidence, but do not by themselves establish progress toward that goal.
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
| `results/open_headroom/` | original information-payoff harness, controllers and data (see its README) |
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
- **Open headroom (2026-10-10, historical measurement).**
  - **The tool.** A central controller that sees only the body's own pings, actions and clock (measurement only) is
    replay-checked for leakage.
  - **Base and POOL, 1,024 fresh lives:** it beats the best reflex by **+13.3 F in base and +13.2 in POOL**. With
    tissue-like handicaps it keeps +9.2 / +9.6.
  - **Historical score comparisons:** evolved s5/s7 were −1.3 / −1.9 F relative to the base reflex,
    the hand router +3.6. Their footprints differ; these are not information-share measurements. Matched BH3
    remains unmeasured.
  - **What pays** is active search from a belief (path integration of its own strokes, pings and the absence of
    pings).
  - **Switching:** in the motor-flip mix (50% of lives flip mid-life), the flip detector adds +12.7 F.
  - **Memory:** in the flash world, acting on memory while the target is dim adds +24.6 F. In renewal blink worlds it
    adds +2-4.
  - **Later measurements:** bounded base/POOL gradients and decoy information are now measured above. Prediction,
    full all-world gradients and capability-world duration transfer remain pending; N completes base/POOL duration checks.

## 5. Decision status and remaining approvals

Historical numbering from `docs/TASK_VARIATION_PLAN.md` 0.9 is retained for cross-references.
The standing admission principle is already instructed; the other decisions remain unassumed.
1. The user already requires judging worlds by information payoff, never by whether we can hand-build a
   winning body. The larger selection rollout and unanswered implementation decisions below remain unapproved;
   the standing principle is not a reason to reintroduce the old gates.
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
  blocks85–88 hold completed transfer/second-step/factorial scoring. Blocks91 and92 hold completed continuation
  confirmation and frozen-tissue measurements. Block30 holds discrimination; block93 is reserved for the structural
  policy comparison, block94 for hidden/lateral lesions, blocks95–97 for the decoy mutant panel and blocks98–99
  for duplicated-origin gene knockouts. Search seeds51089/51090
  use the production hash namespaces; they are not decimal blocks89/90. Block89 now holds K traces; block90
  is reserved for L s7 confirmation. Block100 holds M gene interactions; 101 holds O regulation; 102–104
  are allocated to released P/Q/R. Block105 is reserved for held S preparation and has not been simulated.
  Blocks106–107 are reserved for U decoy evolution/confirmation and validation; 108–109 for V moving-target
  information measurement and calibration. Search seeds53091/53092 use separately audited hashed namespaces.
  Blocks40–41 hold N duration-information measurements. P/S reuse search seeds52091/52092 intentionally;
  the S namespace audit records every overlap. Do not reuse decimal blocks or hashed IDs without a full audit.
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
