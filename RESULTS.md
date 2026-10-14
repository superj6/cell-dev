# RESULTS

Living results table. Scores are the lateral readout: 1 = all firing on the target side, 0 = no lean or silence.
"valid" = fresh trials from the training distribution; "held-out" = unseen directions plus wider brightness ranges,
longer delays, new speeds or closer flicker rates.

## 2026-10-06 — random-genome census (`scripts/census.py`, 2048 genomes per lattice, held-out trials)
| lattice | sites | grew >1 | ≥10 cells | median cells | max cells | develop genomes/s | light | brightness | memory | motion | flicker |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hex | 271 | 0.55 | 0.52 | 27 | 116 | 707 | 0.94 | 0.59 | 0.79 | 0.36 | 0.19 |
| square4 | 293 | 0.55 | 0.52 | 28 | 88 | 993 | 0.96 | 0.59 | 0.75 | 0.30 | 0.17 |
| square8 | 293 | 0.55 | 0.52 | 30 | 150 | 580 | 0.96 | 0.69 | 0.60 | 0.34 | 0.17 |

Task columns are the best random genome's held-out score (random search with 2048 evaluations).
- The init distribution is healthy: about half the genomes grow, sizes span 2 to ~150 cells, and nothing fills the fabric.
- Rung 1 is solved by random search, as intended (it is the "start small" entry point). The later rungs leave room.
- A hand-built "fire where lit" disk (no messages) scores 0.72 on light, 0.24 on brightness, about 0 on memory, motion
  and flicker (enforced in `tests/test_tasks.py`).

### Readout lesson
With a plain cosine readout, random genomes reached ~0.99 on every rung, because cos(activity vector, target) ignores
magnitude, so any slight lean in the right direction earned full credit. Switching to the lateral score (how decisively
the firing sits on the target side) fixed that: see the table above.

## 2026-10-06 — first runs (hex, crossover, seed 0)
| run | evals | rung reached | valid | held-out | messages off | types shuffled | one type | cells | spikes/tick |
|---|---|---|---|---|---|---|---|---|---|
| ladder, 1500 gens | 385k | brightness (rung 2) | 0.57 | 0.44 | 0.42 | 0.44 | 0.44 | 38 | 3.3 |
| motion only, 600 gens | 155k | — | 0.46 | 0.36 | 0.36 | 0.13 | 0.03 | 28 | 0.06 |

- **Ladder**: rung 1 is passed by the founder at generation 0; brightness then plateaus (valid 0.5–0.73) and never
  reaches the 0.9 needed to advance. The final organism is a single cell type and barely uses messages (0.44 → 0.42).
- **Motion**: evolution beats random search (valid 0.11 → 0.46) by *placing* two cell types (shuffling them costs
  0.23; one type costs 0.33) but not by messaging: four near-threshold cells fire a spike or two when the spot
  lingers on them, and many trials are silent. One well-placed spike counts as fully decisive under the lateral score.
- **Diagnosis**: the readout already pools activity over the whole body, so any task whose answer is a linear
  function of what cells sense locally is solvable without communication. Messages are only *necessary* when
  information must travel (across the body, through time beyond one cell's leak) or be combined nonlinearly across
  places. Next step: rungs built so that information has to travel (`withdraw`, `context`, `jump`), each red-teamed for
  no-message cheats.

## 2026-10-06 — memory rung: lattice × breeding (3 seeds, 200 gens ≈ 52k evals) + baselines
`scripts/sweep.py --config configs/memory.yaml ... evolve.generations=200`; aggregate: `results/memory/`.

| setup | valid (median) | held-out (median) | messages off | cells (median) |
|---|---|---|---|---|
| hex · sex | 0.93 | 0.82 | 0.00 | 80 |
| hex · asex | 0.96 | 0.85 | 0.00 | 94 |
| square4 · sex | 0.91 | 0.83 | 0.00 | 83 |
| square4 · asex | 0.93 | 0.71 | 0.00 | 88 |
| square8 · sex | 0.88 | 0.79 | 0.00 | 97 |
| square8 · asex | 0.88 | 0.60 | 0.00 | 101 |
| hex · random search (52k genomes) | 0.88 | 0.81 | 0.00 | 113 |
| hex · fixed one-type disk (rule only) | 0.86 | 0.88 | 0.00 | 61 |

- **Memory needs messages**: every evolved solution scores 0 with messages switched off.
- **But it is too easy**: random search with the same budget and a fixed one-type disk do as well as grown tissue,
  so development and cell types add nothing here. A uniform excitable disk with reverberation solves it.
- Lattice / breeding differences are within noise at 3 seeds. Mutation-only is slightly worse on the square lattices,
  and one square8 run collapsed out of distribution (valid 0.84, held-out 0.00).
- **Smallest solution**: square8 seed 0 kept a **4-cell** organism (2×2 block, one type) with held-out 0.87. Mechanism:
  strong mutual inhibition (w = −2) plus a slow leak (1/16). The lit cells fire during the flash and push the dark-side
  cells deeply negative; the slow leak holds that through the delay, so when the "go" cue arrives the lit side crosses
  threshold first. A message *writes* the memory into the neighbours' voltage. GIFs:
  `outputs/memory_sweep/square8_sex_s0/replay/`.

## 2026-10-06 — message rungs built and red-teamed (workflow `message-rungs`, 10 agents)
Each rung: a builder (task file, tests, hand-built proof, no-message checks), two red-teamers (a no-message cheat
hunter with an exhaustive single-cell analysis plus layout search, and a stimulus/statistics auditor), and a fix pass.

| rung | hand-built with messages / off | random best (messages on / off) | short no-message evolution | best no-message cheat found | status |
|---|---|---|---|---|---|
| withdraw | 0.73 / 0.00 (13 cells) | 0.69 / 0.03 | 0.00 | 0.22 → **0.02** after fix | fixed: rest window = every pre-poke tick, poke after tick 10 |
| context | 0.84 / 0.00 (7 cells) | 0.34 / 0.02 | 0.00 | 0.17 | passes (bar 0.3) |
| jump | 0.68 / 0.00 (19 cells) | 0.11 / 0.03 | 0.00 | **0.50** → ≈0.13 after fix | fixed: wide onset range, short gap |

- **jump** had a real leak. B always follows A, so absolute time told the flashes apart: a 7-cell organism whose A and
  B sites never interact scored 0.50 held-out. The leak can only be bounded (≤ gap / onset range), not removed.
- **withdraw**: the cheat hunter enumerated all 8448 quantized single-cell rules and found that no quantized cell can
  first fire spontaneously after tick 10, so starting the poke after tick 10 and scoring every earlier tick as rest
  forces any tonic cell to show its firing. The red team's best cheats drop from 0.22 to ≤ 0.02 held-out.
- **Caveat** from the jump red team: with `cells.quantize=false` the jump rung breaks (no-message 0.55), because
  continuous parameters make better single-cell clocks. Quantization is part of the design.
- Bug found and fixed: `measure.knockouts` ignored `cells.messages=false`, so no-message control runs reported
  messages-on held-out numbers.

## 2026-10-06 — message rungs: evolution vs random search vs fixed disk vs no messages (hex, 3 seeds, ≈52k evals)
`scripts/run_rungs.sh`; aggregates in `results/{withdraw,context,jump}/`. Held-out medians (min–max):

| rung | evolution | random search | fixed one-type disk | evolution, messages off | evolved: types shuffled | evolved: cells |
|---|---|---|---|---|---|---|
| context | **0.73** (0.46–0.78) | 0.51 | 0.40 | 0.00 | 0.48 | 45 |
| jump | 0.40 (0.38–0.59) | 0.39 (0.09–0.52) | 0.24 | 0.00 | 0.40 | 14 |
| withdraw | 0.49 (0.00–0.64) | **0.65** | 0.56 | 0.00 | 0.49 | 20 |

- **These rungs need messages**: evolution with messages off ends at 0.00 everywhere, and every solution found in
  any other condition drops to 0.00 when messages are removed.
- **context** is the first rung where evolution clearly beats random search *and* grown structure matters: the evolved
  organisms use 2 cell types, and shuffling where they sit costs 0.25. A fixed one-type disk only reaches 0.40.
- **jump**: evolution beats random search on validation (0.44 vs 0.25) but not on held-out trials. Evolved solutions are
  tiny (9–29 cells, one type).
- **withdraw**: random search wins. Two search problems explain it: (1) seed 2's founder was a single cell, because no
  random genome scored above 0 on that seed's 12 training trials, and a 1-cell organism has no gradient to climb, so the
  run stayed at 0; (2) the other seeds stop improving after about 30 generations. The population descends from one
  founder, children change only 2 of 250 numbers, and selection on 12 noisy trials adds drift. Next: an ablation with
  several founders, larger mutations and more trials per evaluation.

## 2026-10-06 — what limits evolution? (`scripts/run_search_ablation.sh`, hex, 3 seeds, 200 gens)
| rung | variant | valid (median) | held-out (median, min–max) |
|---|---|---|---|
| jump | 1 founder (baseline) | 0.44 | 0.40 (0.38–0.59) |
| jump | **8 founders, crossover** | **0.57** | **0.51** (0.33–0.80) |
| jump | 8 founders, 4 mutations per child | 0.55 | 0.50 (0.45–0.56) |
| jump | 8 founders, 24 trials per evaluation | 0.47 | 0.32 (0.29–0.53) |
| jump | 8 founders, **mutation only** | 0.40 | 0.24 (0.17–0.33) |
| jump | random search | 0.25 | 0.39 (0.09–0.52) |
| withdraw | 1 founder (baseline) | 0.61 | 0.49 (0.00–0.64) |
| withdraw | 8 founders, crossover | 0.82 | 0.38 (0.00–0.62) |
| withdraw | 8 founders, 4 mutations per child | 0.80 | 0.49 (0.00–0.76) |
| withdraw | 8 founders, 24 trials per evaluation | 0.81 | 0.64 (0.00–0.69) |
| withdraw | 8 founders, mutation only | 0.80 | 0.49 (0.00–0.78) |
| withdraw | random search | 0.71 | 0.65 (0.52–0.68) |

- **Several founders help**, and on jump **cross-breeding between founder lines clearly beats mutation only**
  (held-out 0.51 vs 0.24). Bigger mutations or more trials per evaluation did not help further.
- withdraw: validation rises to about 0.8, but held-out lags (waves tuned to the training poke distances arrive early or
  late on held-out ones). Every variant keeps one seed at 0.00: seed 2's best founder was a dead single cell, because
  all 1024 random genomes scored at most their energy cost on that seed's trials.
- **Fixes adopted as defaults**: 8 founders; founder sampling now continues in batches of 1024 until some genome scores
  ≥ 0.05 (cap 8192), so a run can't start from a dead organism.

## 2026-10-06 — code review (workflow `review-cell-dev`: 4 subsystem reviewers, 2 reproducing skeptics per finding)
15 findings, 14 confirmed by both skeptics. All fixed or documented; 53 tests pass.

| finding | severity | effect on results so far | resolution |
|---|---|---|---|
| founder sampling stopped on *score* but picked founders by *fitness*, so dead single cells still won | high | would have hit the queued withdraw/ladder seed-2 runs (stopped before they started) | scorers are ranked first; checked: withdraw seed 2 now reaches 0.58 at generation 0 |
| ladder mixed 9 + 3 trials, breaking context's cued/uncued pairs (+0.065 training bonus for cue-blind tissue) and direction balance | medium | first ladder run only (brightness rung) | current rung keeps its full balanced set; an even number of extra trials from one earlier rung |
| flicker targets not direction-balanced (a stimulus-blind organism scores nonzero) | medium | first ladder run never reached flicker | fast light now always comes from the balanced direction |
| motion is solvable by one cell type with messages off (0.3–0.5) | medium | explains the motion run (type placement, no messages) | documented; `jump` is the message version |
| memory's *training* delays are solvable by one slow cell type with messages off (valid 0.5) | low | none: all evolved memory solutions score 0.00 without messages on both splits | documented |
| curves.png pooled different conditions into one line; evals_to_skill median dropped runs that never got there | medium | figures and that column only | curves per condition and generation; failures count as not reached (`reached` column, `inf` median) |
| evals_to_skill missing for random search, and wrong for ladders (first rung) | low | that column only | fixed |
| float32 potential: a cell converging to threshold can round up and fire after about 24 ticks | low | one saved score changes by 0.0007 | documented in `src/cells.py`; a fixed-point potential is the clean fix |
| hex + `contact=inverse_distance` gave unit contacts 1 ± 1 ulp | low | none (only `uniform` used) | distances snapped |
| results.jsonl appended on rerun, ladder advanced on the final generation, GIFs/replay ignored `cells.messages`, replay/analyze ignored custom ladder rungs, `keep_earlier=0` could not disable mixing | low | none so far | fixed |

Rejected (both skeptics refuted it): "the fixed-tissue control wastes evaluations on phenotypic clones".

## 2026-10-06 — context: lattice × breeding (8 founders, 3 seeds, 200 gens); withdraw rerun; first message ladder
| lattice | crossover held-out (median) | mutation-only held-out | crossover: types shuffled | reached valid ≥ 0.9 |
|---|---|---|---|---|
| hex | 0.81 | 0.70 | 0.62 | 2/3 vs 0/3 |
| square4 | 0.84 | 0.80 | 0.35 | 1/3 vs 0/3 |
| square8 | 0.88 | 0.73 | 0.79 | 3/3 vs 0/3 |

- **Crossover beats mutation only on every lattice** (as on jump), and only crossover runs reached valid ≥ 0.9.
- Several founders lifted context from 0.73 (1 founder) to 0.81–0.88. All solutions score 0.00 without messages.
- Lattices: square8 ≥ square4 ≥ hex here, but within seed noise at n = 3.
- **withdraw rerun** with the founder fix: no dead starts (valid 0.80–0.82 on all seeds). Seed 1 grew a **2-type
  organism (48 cells, held-out 0.83)** whose score collapses to 0.05 when its types are shuffled: the grown layout is
  doing the work.
- **Message ladder (withdraw → context → jump → memory), 800 gens: a curriculum failure.** All 3 seeds pass withdraw
  within 10–30 generations, then sit at valid ≈ 0.1 on context for 770 generations, while context alone reaches
  0.8+. The population descends entirely from withdraw winners (relay-wave organisms whose waves flood the tissue under
  whole-field light), so context has no foothold. Next: when the ladder advances, replace half the population with
  new founders sampled on the new rung (`evolve.immigrants: 0.5`), so crossover can hybridize the old lineage with
  breeds that can do the new rung.

## 2026-10-06 — message ladder with immigrants (`evolve.immigrants: 0.5`, 3 seeds, 800 gens)
| seed | rungs passed | final rung | valid | held-out | messages off |
|---|---|---|---|---|---|
| 0 | withdraw (gen 10) | context | 0.08 | 0.00 | 0.00 |
| 1 | withdraw (gen 30), **context (gen 50)** | jump | 0.32 (climbing from 0 at gen 360) | −0.02 | 0.00 |
| 2 | withdraw (gen 10) | context | 0.09 | 0.02 | 0.00 |

- One seed got past context, which no seed managed without immigrants, but the other two stayed stuck even though
  their immigrants scored 0.29–0.43 on context when sampled.
- Why: fitness mixes 12 new-rung trials with 4 revisited earlier-rung trials. The incumbents earn ≈ 0.8 on the
  revisited withdraw trials, while immigrants earn 0 there, so incumbents and immigrants tie on fitness. Then the
  incumbents win the noisy selection and the immigrants are lost before they improve.
- Next idea: protect new breeds while they develop (a "nursery" island that evolves on the new rung alone for a
  while before merging), or weigh the revisited rungs less.

## 2026-10-07 — One-life milestone 1-2: kernel verified, gates, census, throughput, smoke
The new model (docs/ONE_LIFE_DESIGN.md): one continuous, clockless life per genome in the BELL-1 world, run by a C
event kernel (`src/life/kernel.c`, contract `docs/LIFE_ABI.md`) and wired into evolution as `mode: life`. F is pumped
volume minus action costs per time unit, so it is **not comparable** with the trial scores above. A lone cell earns
+0.033.

**Kernel.**
- Bitwise tests pass: T1-T5, T11 and T12. They cover the window scheduler against the heap, tie orders, the Python
  reference, relabelling, threads and batch composition, deaths and refills, and sparse against dense fabric.
- New T6: starting the life at t0 = 1024 changes F by at most 2e-12, and every count is identical.
- Not built yet: T7-T10 and the integer twin.
- The legacy tick pipeline is bit-identical to b1bc7d5 (local_smoke under sex, asex and ladder).
- Whole runs do not depend on the thread count: 10-generation runs at 3 and 8 threads give identical trajectories
  (both benchmark populations below), and re-running the smoke runs repeats them exactly.

**Gates** (`docs/LIFE_GATES.md`). Each point uses 144-288 fresh lives (48 for G5; seeds 5,000,000 and up), shared
across sizes and organisms. 10 of 11 pass.

| gate | measured on fresh lives (mean ± SE) | verdict |
|---|---|---|
| G1 best lone cell | +0.0328 (b 1.625, τ 4, t_ref 4); the registered pump scores +0.0326 and ranks 11th | pass |
| G2 messages off (program-mode bodies only) | best body +0.006 at 2 cells, −0.020 at 3, −0.128 at 7, −0.368 at 19 (lone cell +0.033) | pass |
| G3 R25-v1 size curve | n* = 61, flat to 91, F* = +0.711 ± 0.017; F(91) = +0.697 ± 0.033; F(169) = −0.22 | pass |
| G4 ablation order | R25-v1 [61, 0.713] > no listen-before-talk [37, 0.530] > naive [37, 0.398] > flood [3, 0.044] > none [1, 0.033] | pass |
| G5 no frozen heterogeneity (48 lives) | F +1.89 ± 0.08 at 91 cells, +5.43 ± 0.49 at 397, +5.20 ± 0.91 at 547 (equal), against −8.40 ± 0.29 at 547 with it | pass |
| G6 spikes cut at T/2 | income per cell 31.9e-3 → 1.41e-3 | pass |
| G7 income per cell | at most 49.6e-3 in any body life, against 54.0e-3 for a lone life | pass |
| G8 lumen vs Euler | 0.024% error; bitwise across threads and schedulers | pass |
| G9 R25-v1 as GRN genome | +0.698 ± 0.030 vs program +0.697 ± 0.033 at 91 cells (z 0.04) | pass |
| G10 design choices D4, D5 | flank placement adds only +0.057 ± 0.037 over rate gating (z 1.5) | **fail** |
| S8 square8 curve | n* = 121, F* = +1.151 ± 0.063, flat from 81 to 121 | pass |

- **Corrected R25-v1 numbers.**
  - The registered F(91) = +0.928 was a lucky draw. The prototype keyed frozen physics to the seed, so every 91-cell
    registration shared the same 36 favourable bodies.
  - The reference is now n* = 61 (flat to 91) at F* = +0.71, about 22 times a lone cell, not 28.
  - The ladder on fresh lives: L3 +0.48 at 91 cells (best +0.594 at 61); L4 +0.788 at 91 (registered 0.745 and
    0.905).
  - L4 and R25-v1 are not separated. On the gate's 144 lives L4(91) − R25-v1(61) = +0.074 ± 0.031 (z 2.4), but each
    n* and F* is the argmax on those same lives, and on 288 lives the gap is +0.042 ± 0.024 (paired z 1.8; L4's next
    144 lives give +0.719 at 91).
- **R25-v1 has no stop rule** (`scripts/life_reference.py`).
  - Without the oracle cap every life grows into the N_max guard by t ≈ 376: F = −15.32 ± 0.08 (144 fresh lives).
  - With its lineage-timer gene at weight 1.125 (screened on separate lives): F = +0.454 ± 0.031, n_end median 44
    (q10-q90: 5-93), F > 0 in 97% of lives. That is 64% of the capped optimum.
  - So evolution has to find size control as well as coupling.

**Random-genome census** (`scripts/life_census.py`). 4096 genomes drawn exactly as founder sampling draws them; one life
each; hex; seed 0.

| | T = 512 | T = 1024 |
|---|---|---|
| lone cell, never divides (of which earn income) | 47.1% (13.5%) | 46.1% (13.4%) |
| bounded body, 2 or more cells (with spike traffic) | 13.5% (7.5%) | 11.2% (6.2%) |
| trips the N_max guard | 39.3% | 42.6% |
| extinct | 0% | 0% |
| F ≥ 0.02 (all of them lone pumps) | 3.7% | 3.9% |
| beats the best lone cell | 0% | 0% |
| n_end q10 / q50 / q90 | 1 / 6 / 1050 | 1 / 18 / 1050 |
| best F; best multi-cell F | +0.0318; +0.013 (2 cells) | +0.0317; +0.012 (2 cells) |

- **The distribution is bimodal.** About half of the genomes never divide, and about 40% explode into the guard
  (median trip at t ≈ 62). Only 11-13% grow bounded bodies. Nothing goes extinct, because p_die starts at 0.
- **Founders.** About 38 genomes per batch of 1024 clear the founder bar, so sampling stops after one batch (3-4 s).
  The 16 best re-measure on 64 fresh lives at their census F (+0.0315): there is no winner's curse among lone pumps.
- **Initialisation unchanged.** The zygotes match the design's stated intents: 50.5% tonic, 48% dividing. None of the
  failure modes that would justify retuning appeared (nearly everything extinct, or nearly everything at N_max).
- **Cost.** Guard-tripping lives hold 73-79% of the census kernel events.
- **square8** gives the same census within 1-2 points.

**Throughput** (`scripts/life_bench.py`). One generation is 256 genomes × 3 lives, including breeding and lineage.
Other jobs held a load average of 1-3 on the 14-thread laptop.

| population | 3 threads | 8 threads |
|---|---|---|
| founders, generations 0-9 (mean body 8 cells, 4.5% guard trips) | 1.52 s per generation | 1.04 s per generation |
| R25-sized: R25-v1 + timer 1.0 and its descendants (mean body 63) | 11.2 s per generation | 5.6 s per generation |
| kernel only, 768 R25-v1 + timer lives (n_end 94) | 9.9 s (0.61 µs per cell-unit per thread) | 5.9 s (0.97 µs) |

- The generation times include a valid + forks round every 10 generations (+6.3 s at 3 threads, +3.2 s at 8).
- **Concurrent jobs, R25-sized.** 3 jobs × 3 threads take 16.9 s per generation each; 4 × 3 take 20.9 s. The
  machine saturates at about 0.19 R25-sized generations per second (about 5.3 machine-seconds each), whatever the
  layout.
- The design assumed 0.3 µs per cell-unit unloaded (0.6 µs under load) and 1.2-3 s per late generation; here a late
  generation costs about 5.3 machine-seconds.
- **Pilot estimate.** 10 seeds plus 3 seeds of each of 6 controls is 28 runs × 500 generations = 14,000 generations.
  - About 0.8 h if every run stays at 1-7 cells, as in the smoke runs (0.35-0.96 s per generation with 3 jobs
    running).
  - About 21 h if every run had R25-sized bodies from the start.
  - In general, hours ≈ 0.8 + 20 f, where f is the fraction of generations spent at R25-sized bodies. If a quarter to a
    third of the runs reach bounded 30-90-cell bodies by mid-run, f ≈ 0.1-0.25, about 3-6 h. The design estimated
    2-4 h.
  - Each job uses about 0.31 GB.

**Smoke evolution** (`configs/life_bell.yaml`, 40 generations, 3 threads; not the pilot). Rerun after the review fixes:
every generation repeats exactly, and the rows gain the fields below.

| run | best genome (rank 0), F on 64 fresh lives | best of the top 8: picked on those lives → re-measured on 64 others | cells (q10-q90) | valid at gen 0 / 10 / 20 / 30 / 39 | spike reliance |
|---|---|---|---|---|---|
| full, seed 0 | +0.0247 ± 0.0057 | rank 3: +0.0362 → +0.0379 ± 0.0017 | 4.3 (3-7) | 0.032 / 0.033 / 0.026 / 0.030 / 0.010 | 0.90 |
| full, seed 1 | +0.03277 ± 0.00002 | rank 1: +0.0328 → +0.03278 ± 0.00001 | 1 | 0.029 / 0.032 / 0.033 / 0.033 / 0.033 | 0 |
| messages off, seed 0 | +0.03283 ± 0.00001 | rank 0: +0.0328 → +0.03281 ± 0.00001 | 1 | 0.032 / 0.033 / 0.033 / 0.033 / 0.033 | 0 |

- **Bodies do grow beyond a lone cell** in 1 of 2 seeds. Seed 0 left the lone pumps at generation 12 and settled on
  3-7-cell bodies.
  - These bodies use messages: undelivered spikes from T/2 cut their income by 90%.
  - Their beat is partly synchronous: Kuramoto R 0.86, local order 0.76, period 7.9, trap flag in 6% of lives.
- **The population's top-ranked genome is below a lone pump** on fresh lives (+0.025 ± 0.006 vs +0.033), though it
  scored 0.04-0.08 on the generation's own 3 lives.
- **But the run did find a body that beats the lone cell; selection ranked it 4th** (corrected in review; the first
  version of this entry said the bodies were no better than a lone pump).
  - Rank 3 is a message-dependent body of about 3 cells (n_end median 3, q10-q90 2-4; income per cell 38.3e-3).
  - On 512 independent lives it scores +0.0361 ± 0.0007, about 10% above the best lone cell on the same lives
    (paired +0.0033 ± 0.0007, z 5.0). The final evaluation's own re-measure on 64 separate lives gives
    +0.0379 ± 0.0017.
  - With spikes undelivered from birth, it drops to −0.195 (paired +0.231, z 31.6), so the gain needs messages.
  - Ranks 6 and 7 re-measure at +0.0333 and +0.0331, level with the lone cell.
- **So 3-life selection mis-ranks genomes near the plateau** (the design's winner's curse, visible from generation
  20 on). A lone pump's F is nearly deterministic (SE 1e-5), while a 3-4-cell body's lives spread by about ±0.05. The
  best of 224 noisy children on 3 lives therefore outranks a body with a better mean.
- **Messages off** stays a lone cell over 40 generations (1 seed, 40 of the design's 50 generations). This GRN-mode
  run, with chemistry on, is the only messages-off evidence for gene-network bodies so far: gate G2 searched
  program-mode bodies only, which cannot use chemistry.
- **Envelope column.** Every row now also reports F on the same 64 final lives under envelope physics: −0.0020 ±
  0.0044 against base for seed 0's best genome, −0.0002 for the lone pumps.

**Fixed while integrating.**
- `scripts/sweep.py` always passed `lattice.kind=hex` and `evolve.breeding=sex`, so the square8 and asex controls
  would have silently run as hex with crossover. In life mode the axes now default to the config's own values;
  trials mode is unchanged.

**Added.**
- The seeded control (`evolve.seed_genome`, `configs/life_ctl_seeded.yaml`).
- Per-generation `t_gen`, `t_eval`, `pop_guard`, `pop_lone` and `pop_body`.
- In the final evaluation: Kuramoto R, local order, beat period and the trap flag over the last T/8, a bootstrap 95%
  CI of F, and a size curve on paired lives with its flat top.

**Review fixes** (11 findings; each was reproduced before it was fixed).
- **The envelope control was judged under other physics than every other condition.** Its valid and final lives
  used envelope physics; everything else, including that row's own forks, phase statistics, size curve and held-out
  score, used base physics. The same genome (R25-v1 GRN + timer 1.125) on the same 64 final seeds scored
  +0.379 ± 0.041 under life_bell and −0.224 ± 0.073 under life_ctl_envelope.
  - Fix: the envelope now applies only to selection lives (generations and founder batches). Every F, valid and
    held-out score is measured under base physics.
  - Every results row now also reports `F_envelope`: the best genome on the same final lives under envelope physics,
    paired with F. It also records `selection_physics`.
  - `scripts/aggregate.py` reports F_envelope and refuses envelope-control rows written before the fix.
- **A deleted gene left its weights in other genes' rows.** Crossover could then attach them to another lineage's
  gene in the same slot, so a silent duplicate stopped being silent. In the reviewer's case, F at seed 202 went from
  −21.179 to −21.336. The same residue also arose through crossover: a child that did not inherit gene k kept a
  parent's regulator row with its weight from k.
  - Fix: `delete` and `crossover` now zero every W entry fed by an inactive gene (`LifeLayout.silence`).
  - Lives are unchanged, because the kernel table already masked these entries. The smoke trajectories are
    bitwise the same.
- **Duplications of one generation piled into one slot.** The slot registry was read once per batch: in a 60-generation
  run with duplication on, 145 of 270 duplications (54%) shared their slot with another duplication of the same
  generation. `mutate` now counts each duplication into its copy of the registry. This matters only from migration
  step 6 (duplication is off by default).
- **identity_clamp did not freeze g.** Every division still partitioned g between mother and daughter: under a clamp
  from t = 0, 1877 of 3081 dead cells had a different g at death than at birth.
  - Fix, in the kernel and the Python reference: the partition is skipped under the flag, so a daughter starts with
    her mother's g (LIFE_ABI.md 7.4, 12 and 15.31).
  - No gate uses the flag, and every gate number is bitwise the same with the new kernel library
    (`life_6ed6129a0071cbfe.so`).
  - Only identity_clamp forks change. Seed 0's best genome: d_income −0.0005 → −0.0045 ± 0.0044 at T/2.
- **The design's death-bump monitor (cheat 8) was missing.** The design logs income within 2 units of deaths. The
  final evaluation now measures it on the best genome's 16 fork lives, by replays with the ledger opened at each
  window edge.
  - It reports deaths per life, the share of time and of income in the 2 units after deaths, and `death_lift`, the
    income rate after deaths over the rate in the 2 units before them.
  - Example (R25-v1 GRN + timer, with p_die 2^-7; 16 lives): 55 deaths per life; 9% of the time and 24% of the income
    fall after deaths. The lift is 0.85, so deaths do not bump the pump.
  - Against the rest of the life the ratio is 3.1, which only reflects that deaths happen in the large, late body.
  - The smoke bodies have no deaths. The monitor runs once per run, not every generation.
- **The kernel's ledger_mismatch bit was never read.** No life had it (0 of 4 × 768). A life with the bit is now
  invalid, scored as the worst guard trip and counted: `mismatch` per genome, `pop_mismatch` and `pop_invalid` per
  generation, a `ledger_mismatch` log event, and `mismatch_lives` in the results row.
- **Best-of-top was reported on the lives it was picked on.** `top_best_F` is now re-measured on as many separate
  lives, with its SE; `top_best_F_pick` keeps the picked value. The smoke text above is corrected accordingly.
- **Documentation only.**
  - G2 searched program-mode bodies only, so it says nothing about chemistry. G10's grn_layer covers G1 and the
    R25-v1 curve only.
  - The G3 port check now uses a 4608-life prototype reference with the kernel's Irwin-Hall normals, judged at 2 SE.
    The kernel passes at z −0.37, −0.85 and +0.43. The old 1152-life reference was itself a ~2.3 SE draw, and the
    check had been loosened to 3 SE.
  - Corrected here: L4 vs R25-v1 (not separated), and G5's 48 lives.
  - LIFE_GATES.md now notes that n* and F* are picked and reported on the same lives.
- **Checks rerun.** Fast suite 347 passed, slow suite 56 passed. Gates: 10 of 11 pass, as before. The three smoke
  runs repeat every generation exactly; only their identity_clamp fork rows change. The legacy local_smoke (sex,
  asex, ladder) is identical to b1bc7d5.

**Open decisions for the pilot.**
1. **Lives per genome.** 3-life selection mis-ranks genomes near the plateau: in seed 0 a message-using 3-cell body
   that beats the lone cell by 10% (z 5) ranked 4th, behind a genome at +0.025. Keep 3 (the design), raise it, or
   re-measure the top of each generation on more lives before ranking?
2. **The G10 failure.** Keep the dedicated flank input to the gene network? With flank placement kept, the plain
   neighbour count does as well.
3. **Order of runs.** Run the 10 full-model seeds first and the controls after, since cost is driven by how many
   runs find bounded bodies.

## 2026-10-07 — Pilot preparation: two-stage selection, no flank input, hex and square8 as equal arms
The three open decisions above are settled (approved by the user): (1) two-stage selection, (2) the gene network loses
its flank_best input, (3) hex and square8 run as equal arms of 10 seeds each, and the controls run later.

**1. Two-stage selection.** Every generation, all 256 genomes live the 3 shared lives as before. The top 64 by that mean
(the shortlist) then live 4 more fresh lives, shared by the shortlist, and the 32 parents are the shortlist's top 32 by
the mean over all 7 lives. That is +256 lives per generation (+33%). Settings `evolve.recheck_k: 64`,
`recheck_lives: 4`, `recheck_key: all` (configs/life.yaml).
- **Recheck off.** With `recheck_k` or `recheck_lives` set to 0, the loop is f2142c8's loop exactly. f2142c8's
  evolve.py and the new one, both run on this tree with the recheck off, give bitwise identical runs: 5 smoke
  settings, life_bell for 3 generations, and the legacy loop under sex and asex.
  `test_recheck_off_is_the_one_stage_loop` pins recheck_k = 0 against recheck_lives = 0.
- One-stage runs do not reproduce f2142c8's own trajectories, because ABI 2 (part 2) shortened the genome from 809
  to 793 slots, which changes every random genome draw. For life_smoke over 3 generations, best F is 0.03228 /
  0.03175 / 0.03248 at f2142c8 and 0.02989 / 0.02997 / 0.03407 now.
- **The study.** I replayed selection on measured genome × life F matrices of real populations (128-256 lives per
  genome, 4000 replicates per generation, true F on held-out lives). "Regret" is the true mean F of the true top 32
  minus that of the 32 chosen; rr is the share of one-stage regret a scheme removes. One-stage selection chose
  parents of true F +0.0643 where the true top 32 had +0.0729 (body populations), and +0.610 vs +0.668 (R25-sized
  populations); on the lone-pump plateau every scheme is within 0.0003. Files: `results/selection_study/`. Its
  README.md lists the data, the exact commands and what is kept only locally. The full grid is in report_all.txt and
  the scripts are in scripts/. The forward runs' data is in data/, and `tests/test_selection_study.py` recomputes
  the counts below from it.

| scheme (K shortlist, L2 extra lives) | extra lives | rr escape / bodies / big | mean rr | ΔF bodies (SE) | ΔF big (SE) |
|---|---|---|---|---|---|
| one-stage (3 lives) | 0 | 0 / 0 / 0 | 0 | 0 | 0 |
| 4 lives for everyone | +33% | .22 / .13 / .14 | .16 | +.0012 (.0001) | +.009 (.001) |
| K128 L2, mean of all lives | +33% | .40 / .22 / .26 | .29 | +.0019 (.0001) | +.017 (.002) |
| **K64 L4, mean of all 7 lives (chosen)** | +33% | .51 / .29 / .35 | .38 | +.0025 (.0001) | +.023 (.002) |
| K64 L4, recheck lives only | +33% | .55 / .31 / .38 | .41 | +.0026 (.0001) | +.025 (.002) |
| K48 L5, recheck lives only | +31% | .56 / .27 / .42 | .42 | +.0023 (.0001) | +.027 (.003) |
| K64 L6, mean of all lives | +50% | .56 / .34 / .39 | .43 | +.0029 (.0001) | +.026 (.003) |

- **Why the all-lives key, not the slightly better recheck-only key, and what it costs.** The only plateau escape
  seen (hex seed 0, generation 12, ABI 1) went through a 2-cell body slightly *below* a lone cell (+0.0291 vs
  +0.0328) that survived on lucky lives. Forward runs from that state ("mostly bodies": at least half of the final 32
  parents end with 1.5 cells or more; Fisher p against one-stage selection):

  | from the escape state | one-stage | chosen key (all 7 lives) | recheck lives only |
  |---|---|---|---|
  | 20 generations, 48 runs: parents mostly bodies | 20 | 12 (p 0.13) | 5 (p 0.001) |
  | 50 generations, 24 runs: parents mostly bodies | 19 | 12 (p 0.07) | 5 (p < 0.001) |
  | 50 generations, 24 runs: parents beat the lone cell | 13 | 12 (p 1) | 5 (p 0.036) |
  | 50 generations: mean true F of the parents | +0.0420 | +0.0418 | +0.0358 |

  - The chosen key keeps the escape route much more open than the recheck-only key. It still cuts the runs that
    keep bodies to about 0.6 of one-stage selection's (not significant at 24-48 runs) and gains no F by 50
    generations. The recheck stops lucky genomes from winning, and some lucky genomes are small bodies.
  - A reviewer's check on the pilot config agrees, weakly (life_bell, hex seeds 0-5, 60 generations, no forks).
    With the recheck, the population held a dividing genome in 4-9 of the 60 generations on every seed. Without it,
    the count was 3-6 on 5 seeds, but 59 on seed 2 (rerun here: the same 59, and 7 with the recheck). In every run
    the parents' median size was 1 cell at every fifth generation.
  - In the body regime both keys beat one-stage selection by the same +0.0032 after 20 generations (SE 0.0016 and
    0.0022, 8 replicates). +50% buys only about 12% more regret removal, so I stayed at +33%.
- **Caveats.** The study ran under ABI 1 on one escaping lineage plus seeded populations. Escapes were rare: 1 of 49
  one-stage runs (hex seeds 0-18, square8 seeds 0-29, 60-150 generations). The real picks sat at the 0.64 percentile
  of the replayed one-stage distribution (z about 2), so the replay may overstate one-stage loss a little.

**2. No flank_best gene input (kernel ABI 2).** The gene network has 22 inputs and the genome 793 slots
(LIFE_ABI.md 15.32). Placement keeps its genetic φ·flank(e) term, and program mode keeps its flank gate as a hand-built
reference. R25-v1's GRN genome now gates division on n_view ≥ D − 1.
- **Neutral for founders.** Every ABI-1 founder had zero flank weights. The census's own 2048 founder draws per
  lattice, run under the ABI-1 kernel and (flank column dropped) under ABI 2, give bitwise equal ledgers in all
  8192 lives (hex and square8, T = 512 and 1024).
- **Gates** (docs/LIFE_GATES.md): 10 of 11 pass, the same verdicts as before. A rerun on the integrated tree
  reproduced gates.json leaf for leaf (501 s, 4 threads, 0.47 GB). A rerun after the review (458 s) reproduced every
  number; only three notes changed (G9, G10, S8). Re-registered rows:
  - G9: GRN genome (n_view gate) +0.690 ± 0.032 vs program +0.697 ± 0.033 at 91 cells (z −0.15, n 288).
  - G10, GRN: flank placement +0.754 ± 0.042 vs random placement +0.638 ± 0.029 (paired z 2.8). G10 still fails
    only on the program-mode placement term (+0.057 ± 0.037, z 1.5).
  - S8, GRN genome on square8: +0.978 ± 0.073 vs program +1.151 ± 0.063 (unpaired z −1.79, passes; paired
    −0.173 ± 0.080, z −2.2).
  - G6, GRN genome: income per cell 32.6e-3 → 1.36e-3 with spikes cut at T/2.
- **Not equivalent on square8** (review; `results/flank_square8/`, LIFE_GATES.md S8). G10's evidence came from hex
  only. On square8, R25-v1's genome gated on n_view ≥ 7 (ABI 2) is below its ABI-1 twin gated on flank_best at every
  size. The comparison is paired on the same 288 fresh lives per size:

  | square8 cells | 49 | 81 | 121 | 169 |
  |---|---|---|---|---|
  | n_view gate minus flank_best gate (SE) | −0.013 (0.010) | −0.051 (0.020) | −0.081 (0.052) | −0.165 (0.065) |
  | z | −1.3 | −2.5 | −1.6 | −2.5 |

  - F* is +1.015 vs +1.096 (−7%). Gates at n_view ≥ 5 or ≥ 6 do no better (144 lives).
  - On hex the same pair is equal (|z| < 1 at 61, 91 and 127 cells), which reproduces G10.
  - So the square8 arm evolves without a cue that the hand-built genome needs there. The code is unchanged; this
    is for the user to weigh ("Before launching").

**3. Census after the change** (`scripts/life_census.py`, 2048 genomes per lattice, seed 0; outputs/life_census_abi2/).
The founder distribution is unchanged within sampling noise. The new draw length gives different random genomes,
so the numbers move by noise only (the lives themselves are bitwise neutral, above).

| T = 1024 | hex ABI 1 (4096) | hex ABI 2 (2048) | square8 ABI 1 | square8 ABI 2 |
|---|---|---|---|---|
| lone cell / lone pump | 46.1% / 13.4% | 46.4% / 12.6% | 46.1% / 13.4% | 46.4% / 12.6% |
| bounded body (with spike traffic) | 11.2% (6.2%) | 10.5% (5.3%) | 10.2% (5.6%) | 9.3% (4.6%) |
| trips the N_max guard | 42.6% | 43.1% | 43.7% | 44.3% |
| F ≥ 0.02 / beats the best lone cell | 3.9% / 0% | 3.4% / 0% | 3.9% / 0% | 3.5% / 0% |
| n_end q10 / q50 / q90 | 1 / 18 / 1050 | 1 / 25.5 / 1051 | 1 / 21 / 1054 | 1 / 31.5 / 1054 |
| best F (all lone cells) | +0.0317 | +0.0319 | +0.0317 | +0.0319 |

- Every share moves by |z| ≤ 1.7 at both horizons, except zygote tonic 50.5% → 47.7% (z −2.1, one of about 40
  comparisons).
- The top 16 re-measured on 64 fresh lives: 13 sit within 0.0006 of their census F. Three are latent dividers: one
  census-lone genome divides on most fresh lives (−0.119, n_end 19), and two others re-measure 0.004 and 0.020
  lower. So the mean census F over the mean fresh F is 1.56, up from 1.01. This comes from the draw, not the change.

**4. Smoke evolution with the new selection** (configs/life_bell.yaml and life_bell_square8.yaml, seed 0,
60 generations, 3 threads, both at once while the gates ran; another user job held load 7-12).

| arm | best on 64 fresh final lives | cells | spike reliance | valid at gen 0 / 30 / 59 | parents changed by the recheck | s per generation |
|---|---|---|---|---|---|---|
| hex | +0.03279 ± 0.00001 | 1 | 0 | 0.0321 / 0.0326 / 0.0328 | 9.2 of 32 (0-25) | 0.44 |
| square8 | +0.03279 ± 0.00001 | 1 | 0 | 0.0321 / 0.0326 / 0.0328 | 9.2 of 32 (0-25) | 0.43 |

- **Both arms stayed lone pumps,** at the best lone cell's level (G1: +0.03281). From generation 5 on, not one of
  the 256 genomes per generation divided (56 of 60 generations had no dividing genome at all).
- **The recheck reshuffles lone pumps.** It changed 9 of 32 parents per generation, but the parents' F on the 4
  recheck lives differs from their 3-life F by a median 6e-5. It cannot create bodies. It stops lucky genomes from
  winning, and in the forward runs (part 1) those included small bodies that one-stage selection kept.
- **The two arms ran the same trajectory.** population.json is identical at generation 59, and every curve field
  except timing and population shares matches. A lone cell's life does not depend on the lattice, and the arms share
  seeds. So hex seed s and square8 seed s stay the same run until one of them selects a body: the arms are paired.
- **Time.** Runs take 45-46 s: setup and founders 9 s, generations 0-1 10-12 s, then 0.44 s per generation
  (recheck about 22% of it; valid and fork rounds every 10). Peak memory 0.30 GB.
- **Body regime** (`scripts/life_bench.py`, R25-v1 + timer population, 3 threads, one job). Rerun after the review
  with 8 generations (6 plain), load 3-6:
  - A plain generation takes 17.2 s on hex and 23.0 s on square8 (medians). The population's kernel time plus the
    recheck's, summed within each generation, account for all of it (median 17.2 and 23.0 s).
  - Summed over the 6 generations, the recheck adds 31% (hex) and 28% (square8) to the population's kernel time.
    The study's event count predicted +38-47%.
  - Within single generations the recheck adds 13-131%. Its cost follows the shortlist's bodies, not the
    population's: in generation 2, a recheck life cost about 4 times a population life, while the population
    averaged 24 live cells.
  - Correction: the first run of this bench (6 generations, load 7-14) was reported as "25.3 s = 19.5 s population
    kernel + 7.8 s recheck". Those were three separate medians that do not add up (19.5 + 7.8 = 27.3). The bench now
    keeps per-generation times. Its populations live bitwise the same lives in every run; only the times differ
    between the two runs (hex 25.3 → 17.2 s, square8 19.9 → 23.0 s), so single bench timings differ by up to 1.5
    times between runs.

**5. Pilot plumbing and time.** `PILOT_ROOT=… PILOT_SEEDS=0,1 PILOT_GENERATIONS=2 scripts/run_life_pilot.sh` ran 4
runs (3 jobs × 3 threads) and the aggregate in 38 s, all into the scratch root. Every row carries git_rev, git_dirty
and recheck K64 L4 all; evals = 1024 + 2 × (256 + 85.33); the summary groups by selection and lists the revision.
After the review the dry run took 45 s (peak memory 0.31 GB). A hedge dry run into the same root
(`PILOT_SEEDS=20 … scripts/run_life_pilot.sh evolve.recheck_k=0`) added 2 one-stage runs (evals 1024 + 2 × 256),
and the summary listed them as separate one-stage groups next to the two-stage ones, with the new `bodies_kept` and
`body_losses` columns.
- **Estimate for 20 runs × 500 generations** (10,000 generations, 3 jobs × 3 threads):
  - **About 0.5 h if every run stays on the plateau,** as both smoke arms did here and 48 of 49 study runs did.
    That is about 4 min per run.
  - **R25-sized bodies cost about 7 machine-seconds per generation** with the recheck: the earlier 5.3-5.6 s,
    times 1.28-1.31. That factor is approximate, since one generation's factor ranged from 1.13 to 2.31. That would
    be about 19-20 h if every generation had them.
  - **In general, hours ≈ 0.5 + 20 f,** where f is the share of generations spent at R25-sized bodies. For
    f = 0.1-0.25, about 2.5-5.5 h.
  - These figures assume the machine is otherwise idle. Under today's outside load (6-12), allow up to 1.5-2 times
    as long.

**Integration fixes** (both changes together): stale "ABI v1: 809 slots" and "flank count" comments in the configs.
`sweep.py --out/--logs` and `PILOT_ROOT` / `PILOT_SEEDS` / `PILOT_GENERATIONS` make a dry run possible; the defaults
are unchanged. `life_bench.py` reports the recheck time. The design doc gained dated notes (EVALUATION PROTOCOL,
rules 10 and 22). LIFE_GATES.md had one rounding slip (G5 default F(169) is −0.24).

**Checks.** ruff clean. Fast suite 359 passed; slow suite 57 passed. Gates 10 of 11 as before. The legacy tick pipeline
(local_smoke under sex, asex and ladder) is byte-identical to the f2142c8 snapshot; results rows differ only in wall_s.

**Review fixes (same day).** A review raised 7 findings, and all 7 reproduced. Each fix has a test, except the two
that are wording only (2 and 7), whose facts existing tests already pin.
1. *The recheck halves body escapes* (medium). Reproduced from the stored forward runs. One count differs a little:
   runs whose parents' median size is above 2 cells are 18 vs 11; the review's 17 vs 9 uses a 2.5-cell cut. Part 1,
   part 4 and "Before launching" now give the body numbers next to the beat-the-lone-cell numbers. Two-stage runs
   now record the bodies the recheck kept and dropped (rows, results.jsonl and the summary). The selection choice
   goes back to the user. Tests: `test_recheck_rows_count_the_bodies_it_keeps_and_drops`, the aggregate test, and
   `tests/test_selection_study.py`.
2. *"Checked bitwise against f2142c8"* (low). Reproduced. Reworded in part 1 and re-checked: f2142c8's loop and
   the new one, run on this tree, are identical in 8 of 8 cases.
3. *The study could not be rerun from the repo* (low). The forward runs' data and inputs are now in
   `results/selection_study/data/` (0.7 MB). Its README gives the exact commands. The other 24 MB are kept locally in
   `outputs/selection_study/`. The final F the review could not reproduce was not a script change: the stored rows
   used `--final_lives 32` (the default is 64). With that flag, the saved scripts reproduce stored rows bitwise.
   I checked rows from every stored file except the first parts of two split 50-generation runs (README).
4. *Lines over 120 characters* (low). Reproduced (160 and 122 characters). Both are split, together with an older
   125-character line in the same print. `tests/test_style.py` pins each file's count of long lines, all from
   f2142c8 or earlier, so no file can gain one; ruff ignores E501.
5. *The bench breakdown did not add up* (low). Reproduced (19.54 + 7.79 > 25.30). The bench now keeps per-generation
   times and ratios. The rerun's numbers are in part 4 and the estimate in part 5. Test:
   `test_bench_takes_the_recheck_share_within_each_generation`.
6. *The n_view gate is weaker on square8* (medium). Reproduced bitwise: the per-life arrays equal the review's, and
   so does the threshold check. The equivalence is now qualified as hex-only in LIFE_ABI.md 15.32, the design's
   rule-10 note, `handbuilt.r25_genome`, LIFE_GATES.md (G9, G10, S8, item 14) and the G9, G10 and S8 notes in
   `scripts/life_gates.py`. The evidence is in `results/flank_square8/`. No model code changed. Test:
   `test_square8_n_view_gate_against_the_abi1_flank_gate` (slow).
7. *345 mutable entries in the design doc* (low). Reproduced (337 under ABI 2). The rule-10 note now says so.

Checks after the review fixes:
- ruff clean.
- Fast suite: 365 passed, including 6 new tests. Slow suite: 58 passed, including 1 new test (2 min 6 s, 0.50 GB).
- Gates: 10 of 11 pass, every number reproduced (458 s, 4 threads, 0.47 GB).
- With the recheck off, f2142c8's loop and this one still match bitwise in 8 of 8 cases.
- The legacy tick pipeline is still byte-identical (local_smoke under sex, asex and ladder): results rows differ
  only in wall_s.
- The pilot dry run and a one-stage hedge dry run both work (part 5).

**Before launching.**
- **Commit first.** The tree is dirty, and every row records that.
- **Expect few bodies; two-stage selection makes them rarer.** Escapes were rare in the study, and in the smoke runs
  children stopped dividing altogether by generation 5. The pre-registered kill criterion (8 or more of 10 seeds at
  1-2 cells after 500 generations) is a real possibility, and the recheck makes it likelier. From the one observed
  escape, it cut the runs that kept bodies from 19/24 to 12/24 (p 0.07) and gained no F by 50 generations (part 1).
  - Every two-stage run now records what the recheck did to bodies, so a failure can be attributed. Each generation
    row gives `recheck_bodies_onestage` (bodies among the parents one-stage selection would have chosen) and
    `recheck_bodies` (bodies among the chosen parents), both measured on the generation's lives.
  - results.jsonl gives their totals and `recheck_body_losses`, the generations where the recheck dropped every such
    body. The summary table gives `bodies_kept` and `body_losses` per arm.
- **Two decisions for the user before launch** (both were approved before these measurements):
  1. Selection. Options: keep K64 L4 `all` in all 20 runs, as approved; or switch every run to one-stage selection
     (append `evolve.recheck_k=0` to the pilot command); or hedge by adding one-stage runs on other seeds after the
     main pilot, e.g. `PILOT_SEEDS=20,21,22,23,24 scripts/run_life_pilot.sh evolve.recheck_k=0` (10 runs, both
     arms). The hedge runs land in the same outputs/life_pilot, and the summary lists them as a separate one-stage
     group.
  2. The flank_best input on square8. The G10-style square8 check the review asked for is done (part 2: 288 lives
     per size, 49-169 cells): without the input, the hand-built genome loses 7% of F* there and nothing on hex.
     Options: accept that for the square8 arm (evolution may find another gate); or restore the input for both arms
     (a kernel change, a new ABI and a gate rerun).
- **Paired arms.** With shared seeds, the two arms are not independent until one diverges. For independent lineages,
  give square8 other seeds (for example 10-19).
- **ABI-1 outputs** (outputs/life_smoke40, life_census, life_reference) cannot be loaded or resumed under ABI 2.

## 2026-10-08 — BODY-1 v1: CATCH-T in the kernel (ABI 3), gates, census, smoke, review fixes
The approved body design (docs/BODY_DESIGN_PROPOSAL.md: the dot is the body; a hex-prism tissue rides on it; sense
plane z = 0, act plane z = 1, hidden planes above; surface-normal pulls; clicks only at the hotspot; arms L_max 2 and
4) now runs in the C kernel and the Python reference as ABI 3 (docs/LIFE_ABI.md 9.7 and section 15). A code review
then found six problems; five were real model or gate problems and are fixed below, with their tweaks. Nothing is
committed and no pilot was launched.

**Kernel verified.**
- Kernel = reference, bitwise, on every ABI-3 test life, on about 1,800 random CATCH lives (cross-check round 1), and
  after the fixes on 600 more random founders of the CATCH prior at L_max 4 and 2 (369 grew, 124 ended with a
  column that has no sense cell, the case the drag fix changes): 0 mismatches.
- BELL-1 under ABI 3: G1-G10 and S8 rerun on the fixed kernel are identical to the ABI-2 kernel's gates.json leaf for
  leaf (program and GRN mode alike), so BELL numbers moved by 0. 10 of 11 pass; G10 fails on its one known check, as
  before (601 s, 4 threads, 0.72 GB).
- heap = window and tie-order invariance for CATCH lives with growth, receptors, forks and the second blob (GB2;
  `test_life_time.py`, `test_life_reference_smoke.py`); the closed-form dot against Euler integration within 0.1%.
- The legacy tick pipeline: a local smoke run on this tree is identical to HEAD's (curves and results row, apart
  from wall_s).
- Tests: 610 fast and 111 slow pass; ruff clean. A CATCH run peaks at 0.43 GB (4 threads).

**Review findings** (6 reported; all reproduced with the reviewers' scripts):

| finding | reproduced | fix | regression test |
|---|---|---|---|
| slow blind clicking beats the lone zygote at c_miss 1; GB7 tested one fast presser | yes: best presser −0.0118 vs lone −0.0203, +0.0085 ± 0.0020; GRN version +0.0108 (z 5.5) | c_miss 2 (tweak 10); GB7 screens 480 blind pressers and two blind GRN genomes | `test_gb7_cheats_lose`, `test_blind_genomes_never_sense_and_click_slowly` |
| the message certificate gives a blind relay clicker msg_reliance 1.0 | yes: certificate removes 100%, receptor_off 0% | receptor_off joins the CATCH forks; runs report `sense_reliance`; GB6 requires both forks ≥ 95% and catches the blind relay | `test_a_blind_relay_passes_the_certificate_but_not_the_sensing_fork`, GB6 test, the CATCH run test |
| a clicker with two footless tonic drifters beats the 4-column body and is a local optimum | yes: +0.068 ± 0.005 over 4 columns (z 14), every neighbour lower | drag from the projected footprint (tweak 11); GB7 screens runners with 1-3 drifters and reports their neighbours | `test_footless_act_cells_add_drag`, Euler and record re-derivation tests |
| tiny t_resp or tau_turn hangs `life_run` | yes: t_resp 1e-20 never returned (killed at 30 s) | both are 0 or ≥ 2^-10 (spec and kernel; LIFE_ABI 4.7, 15.58) | `test_world_timers_below_the_step_floor_are_refused_so_every_life_ends`, world-range lists |
| the founder prior's b 0.25 and kappa 1.0 were credited to the proposal | yes: proposal 7 says b 0 and no kappa mean | b back to 0; kappa set to 1.5 and declared as our own (tweak 14), with a census | `test_the_catch_founder_settings_are_the_recorded_tweaks` (decodes the means) |
| kappa mean 1.0 decodes to kappa 1/2, not 1 | yes (KAPPA[rint(2y)]: y 1.0 → 1/2) | as above | as above |

**Gates (CATCH, 9 of 9 pass;** docs/LIFE_GATES.md BODY-1, outputs/life_gates/gates_catch.json, 808 s, 4 threads).
Fresh lives, paired; F at c_miss 2.

| gate | measured | verdict |
|---|---|---|
| GB3 first division pays | lone −0.0203; 2-cell clicker +0.0237 ± 0.0023; step +0.044 (z 19, n 2048) | PASS |
| GB4 ring ladder | rises to ring 3 (74 cells) +3.892 ± 0.025, 164× the clicker; ring 6 −3.32; port max z 2.67 | PASS |
| GB5 column by column | 29 of 30 steps uphill, none down, in 3 orders and ring 1 → 2; faintest +0.023 ± 0.004 | PASS |
| GB6 wire certificate | certificate and receptor_off each remove 99.6-100% at rings 0-6 and on two grown GRN bodies; blind relay: 100% and 0% | PASS |
| GB7 cheats | blind pressers lose to the lone zygote (best −0.046, z −17; GRN −0.061, z −21); runners with 1/2/3 drifters +0.060 / +0.043 / +0.053, all below the 4-column body (+0.071; z −2.7, −7.1, −4.5) and the 6-column body (z −27 to −31); islands −0.226 | PASS |
| GB8 2-hop hold (positive control) | ring 1 gain +0.484 ± 0.011 (z 46); lateral-off removes 100% | PASS |
| GB9 column reflex as a GRN genome | rings 0 and 1 grow exactly in 256/256 lives; after growth z +0.05 / −0.04 vs program twins; 80-cell grower −0.031 ± 0.042 | PASS |
| GB12 start robustness | v1: every first step uphill; clicker margin vanishes at v_t 0.05 and R_cap 50 as in the prototype | PASS |
| GB13 hidden planes | silent hidden cells cost exactly c_live (residual ≤ 8e-14); L_max 2 = 4 bitwise for column bodies | PASS |

- Not part of the gate: the runner screen repeated on the GRN grid (b 1.125-2, every tau_m and t_ref, kappa
  0.25-1, feet or not; 960 settings per drifter count): best runners +0.061 / +0.057 / +0.048, all below the
  4-column body (z −2.5, −3.4, −5.6).
- Before the fixes the same 9 gates also passed, because GB6 did not fork the receptors and GB7 screened neither slow
  pressers nor multi-drifter runners.

**Census (GB10;** 8,192 founder-distribution genomes, one CATCH life each, earners re-measured on 24 fresh lives;
the fixed world). The four rows differ only in the founder prior's b and kappa means:

| prior (b, kappa a0 means) | zygotes with kappa 1 | earners L_max 4 / 2 | genuine founders L_max 4 / 2 (all sense) | top-8 recheck F, L_max 4 / 2 |
|---|---|---|---|---|
| proposal 7 (0, BELL's 0.5) | 21% | 98 / 93 | 1 / 1 | −0.044 / −0.042 |
| before the review (0.25, 1.0) | 40% | 163 / 183 | 1 / 1 | −0.026 / −0.020 |
| (0.25, 1.5) | 60% | 222 / 246 | 1 / 1 | −0.021 / −0.019 |
| **adopted (0, 1.5)** | 60% | 194 / 213 | 1 / 1 | −0.017 / −0.018 |

- The genuine founder is the same genome in every row: a 2-cell clicker, F +0.020 ± 0.016, whose income receptor_off
  removes entirely. Rate 1 in 8,192 at each L_max (95% CI 1 in 1,471 to 1 in 323,567), below the proposal's
  1 in 2,000. Before the c_miss fix the census found 2; the other one (17 misses per life) no longer earns.
- 53% of random genomes never divide and 27-28% trip the 1024-cell guard (72-77% of the census's kernel events).
- So, as proposal 7 step 3 prescribes, the pilot script now runs the seeded-ancestor arm by default (tweak 15),
  next to the two unseeded arms with their larger founder budget.

**Smoke evolution** (1 seed × 30 generations per arm, the pilot configs; final values on 64 fresh lives):

| arm | founders | final best | F ± SE | msg / sense reliance | wall |
|---|---|---|---|---|---|
| L_max 4, unseeded | best of 16,384 (screen F +0.087) | 2-cell clicker | −0.0005 ± 0.0068 | 1.0 / 1.0 | 541 s |
| L_max 2, unseeded | best of 16,384 (screen F +0.087) | 2-cell clicker | +0.036 ± 0.012 | 1.0 / 1.0 | 612 s |
| seeded (hand GRN 2-cell clicker, L_max 4) | the seed | 48 cells (24 S, 24 M, 0 H) | +0.727 ± 0.073 | 1.0 / 1.0 | 165 s |

- Both unseeded arms found sensing 2-cell clickers (receptor_off and the certificate remove all of their income) and
  stayed at 2 cells for 30 generations. The seeded arm grew to about 50 cells within 10 generations. Thirty
  generations judge nothing; an earlier 300-generation unseeded run (before the fixes) reached 52 cells and +1.84.

**Tweaks beyond the approved proposal, and why** (each keeps sensing, acting and messaging local, adds no clock and
designs no behaviour; hand-built bodies stay references and gates only):
1. Vertical placement uses the 3D polarity vector as well as zeta (LIFE_ABI 15.37): no planar special case, so
   "grow up from the sense plane" can also come from chemistry.
2. Plane cues are 0 outside CATCH (15.38): BELL genomes get no stray input.
3. A cell with g_r 0 has no receptor (15.40): otherwise the genes could read the screen for free.
4. A dying act cell's residual pull is removed (15.43); 5. no sense-plane cell, no traction (15.44).
6. Founder prior: readout std 0.5 / 0.5, plane-cue weights std 2, n_view weights std 8 (census: with BELL's priors
   0 of 8,192 founded at either L_max).
7. Founder budget: all 16,384 samples, 2 lives each, keep the best 8 (proposal 7 arm a); 8. an extinct life pays
   c_live per remaining unit (otherwise dying at once would beat every losing body); 9. founder bar F ≥ 0.
10. **c_miss 2, not 1** (15.60): break-even capture rate per click 2 / 102 = 1.96%, above blind clicking's 1.55%.
    Cost: the clicker's margin over the lone cell falls from +0.070 to +0.044, and in GB12 the clicker no longer
    earns at c_live 0.04 or rho_c 0.7 (it did at c_miss 1): v1 sits closer to the edge of the good region.
11. **Drag from the projected footprint** (15.59): every occupied column in any plane, not only sense-plane cells.
    Column bodies are bitwise unchanged; footless act cells now slow the dot. It follows the proposal's own reason
    for the law (drag grows with the body's linear size).
12. World timers have the 2^-10 floor (15.58), a validity rule.
13. receptor_off is part of the CATCH fork set, and `sense_reliance` is reported next to `msg_reliance`.
14. Founder prior means: b 0 (the proposal's), kappa 1.5, our own, so the mean decodes to kappa 1, the one-spike click
    that proposal 6 step 1 says the act daughter needs (census above).
15. The pilot runs the seeded-ancestor arm by default (`PILOT_SEEDED=0` turns it off), as proposal 7 prescribes below
    1 in 2,000.

**Open issues.**
- Founders are rare (1 in 8,192 at each L_max). The unseeded arms start from noise-lucky genomes whose true F is
  near the lone cell's; whether they climb past 2 cells in 500 generations is what the pilot measures.
- Tweaks 10 and 11 change rule N10's price and rule N6's footprint; please confirm them. With c_miss 2 blind clicking
  still pays in the R_cap 200 world (the blind GRN presser +0.039 ± 0.004 over the lone cell, z 10, n 2048), which
  the configs use only for held-out scores and GB12 for robustness.
- The S1 world search (decision 3) was not started in this round: no S1 candidate has passed A1-A4, and no later
  stage is wired.
- GB9's single-mutant scan was not run; GB11 (growth stops) needs the pilot. The kernel's 2-cell clicker sits about
  9% above the prototype's at equal prices (unexplained). Footless bodies are no longer ported to the prototype.
- Before launching: commit (the tree is dirty), then `scripts/run_catch_pilot.sh` runs 30 runs (two unseeded arms
  and the seeded arm, 10 seeds each).

## 2026-10-08 — Pre-pilot: drag fix (RT-T1), life-length draw (GB11), SPECK gates in the kernel, smokes, pilot matrix
Everything between BODY-1 v1 and the pilot launch, in one section: the S1 red team's drag loophole closed in the kernel
(part 1); gate GB11 read from smoke runs, which switched on the per-generation life length (part 2); SPECK, the S1
candidate, tested in the real kernel (part 3); smoke runs with both changes (part 4); the pilot's run matrix and time
estimate (part 5); a review of this work, whose two findings were both reproduced (part 6); and the decisions taken
before launch, with the pilot's pre-registered criteria (part 10).

**In brief.**
- **Drag** now counts the filled footprint (holes counted). Bodies hollow in every plane lose their drag discount (the
  1-wide hollow ring 3: −0.504 F in catch_v1); every body that never encloses a tile lives bitwise as before, and the
  CATCH and BELL gates are unchanged leaf for leaf. Residual (review finding 2): a one-column slit to the outside
  reopens the discount (+0.18 F on a thick hollow body). Recorded, not closed: closing it would re-price many grown
  bodies, so it is the user's decision.
- **GB11:** evolved CATCH bodies were still growing at T in 89-98% of their lives, so each generation now draws its
  life length from 768, 1024 and 1536 in every CATCH and SPECK config (judged lives stay at 1024).
- **SPECK** (sigma 0.6, R_cap 500) passes A1-A4 in the kernel (GS1-GS4), and GS5 (the router as a GRN genome) passes.
  GS6 failed at c_miss 2 (a blind slow presser beat the lone zygote, though not the sensing clicker), so the SPECK
  presets now price a miss at 10, v1's ratio; there GS1-GS6 all pass (part 10). Caveats: the
  router's lead reverses at message delay d0 2. The valley-free growth path starts from the full ring-3 reflex. From
  the best tuned reflex, the sense-hollow ring 3, every path measured first falls by 0.22-0.44 F (z −2.0 to −4.0 on
  two seed sets; review finding 1, now reported by GS3).
- **Smokes:** unseeded v1 stayed at 2-cell clickers for 150 generations, and one seed lost its clicker. The seeded v1
  arm grew to 203 cells but is still below ring 1. SPECK seeded reached the ring-1 level in 40 generations.
- **Pilot matrix:** the default `v1_l4:10 v1_l2:3 v1_seeded:3:300` takes 3 / 6 / 21 h on 2 jobs (low / central /
  high). With the SPECK arms (`speck_l4:6 speck_seeded:3:300`) it takes 8 / 13 / 35 h.
- **Decided before launch** (part 10, under the user's standing approval of minor tweaks): SPECK at c_miss 10, the
  SPECK arms run, the slit residual stays recorded, and the matrix is 29 runs on 4 jobs x 3 threads, with SPECK's
  criteria pre-registered.

### 1. Drag from the filled footprint (RT-T1)
The S1 red team found a drag loophole in the prototype. Drag counted footprint cells, so a hollow body kept its size
but shed drag (28% for its hollow ring 3), and "hollow" competed with lateral routing for the wrong reason. Fixed in
the kernel, the reference and spec (docs/LIFE_ABI.md 9.7.2 and tweak 15.61): `gamma = n_fill^0.5`, where n_fill is the
projected footprint (the columns occupied in any plane) plus every tile it encloses (a free tile with no path of
edge-sharing free tiles to infinity). It is world physics, computed by the accountant from occupancy; no cell reads it.

**What moved** (paired lives, 4,096 per point, seeds 16,000,000 + s, the hand-built column reflex; the HEAD kernel
8395c12 against this one; differences are paired):

| world | body | cells | columns / filled | F before | F after | after − before | minus full ring 3, before → after |
|---|---|---|---|---|---|---|---|
| catch_v1 | full ring 3 | 74 | 37 / 37 | +3.863 ± 0.009 | bitwise the same | 0 | — |
| catch_v1 | hollow ring 3: centre + ring 3, both planes | 38 | 19 / 37 | +0.387 ± 0.005 | −0.117 ± 0.004 | −0.504 ± 0.005 | −3.477 → −3.980 |
| catch_v1 | thick hollow: centre + rings 2-3 | 62 | 31 / 37 | +1.978 ± 0.007 | +1.821 ± 0.007 | −0.157 ± 0.008 | −1.885 → −2.043 |
| catch_v1 | sense-hollow ring 3 (the prototype's; act disk full) | 56 | 37 / 37 | +4.312 ± 0.009 | bitwise the same | 0 | +0.449 ± 0.011 both |
| SPECK | full ring 3 | 74 | 37 / 37 | +5.047 ± 0.029 | bitwise the same | 0 | — |
| SPECK | hollow ring 3 | 38 | 19 / 37 | +0.689 ± 0.013 | +0.332 ± 0.012 | −0.358 ± 0.012 | −4.358 → −4.716 |
| SPECK | thick hollow | 62 | 31 / 37 | +0.409 ± 0.014 | +0.265 ± 0.013 | −0.144 ± 0.016 | −4.639 → −4.783 |
| SPECK | sense-hollow ring 3 | 56 | 37 / 37 | +5.406 ± 0.029 | bitwise the same | 0 | +0.358 ± 0.034 both |

SPECK = catch_v1 with sigma 0.6 and R_cap 500. The hollow ring 3's speed fell 0.148 → 0.106 (catch_v1) and
0.099 → 0.071 (SPECK), the factor sqrt(19 / 37) = 0.717.
- **In this kernel the prototype's hollow body had already lost its drag discount** to tweak 11 of BODY-1 v1 (15.59:
  the full act disk counts), so it is bitwise unchanged. Its lead over the full ring 3 is all cost: 18 fewer sense
  cells save 0.450 per unit (catch_v1) and 0.389 (SPECK), and income is equal within 1 SE. That is cell economy,
  which the world should keep, not drag. In the red team's prototype run (n 768) the same law moved its tuned hollow
  reflex from +0.69 above its tuned ring 3 to −0.56 below.
- **The loophole left here was bodies hollow in every plane.** Their drag discount was worth +0.50 F (catch_v1) and
  +0.36 F (SPECK) to the 1-wide ring, and is gone. With the column reflex none of these bodies beat the full ring 3
  before or after (an act ring's inner rim pulls toward the hole). A slit to the outside reopens part of it (part 6).
- Random GRN growers (a diagnostic of 40 dividing and dying genomes, 3 lives each): 17 of 120 lives changed, every
  one a life that enclosed a tile while the dot was pulled; 10 others enclosed tiles only while still (or with a
  residual force below an ulp of X) and stayed bitwise.
- **Kernel verified.** Bodies that never enclose a tile live bitwise as before: golden `all` hashes of the old kernel
  for 9 bodies (full disks, hidden stacks, a lopsided body, islands, turnover, three footless drifters, a footless ring
  that grows a foot, a square prism), 3 lives each. Kernel = reference bitwise on hole-forming lives (T3): a hollow
  ring 2 under turnover (holes open when a rim column dies and close when motors divide into the gap), a static hollow
  ring 3, a grower, and GRN genomes on hexprism, square4prism and square8prism. spec agrees with a brute-force flood
  fill on 1,200 random shapes on every base, and the kernel export with spec on 2,000. The Euler re-integration and
  the record re-derivation of the dot use the filled footprint (including a hollow ring and a GRN body whose holes
  open and close). A hollow ring drags bitwise like the same ring with quiet sense cells filling it, and the Euler
  drag with occupied columns alone is off by sqrt(37 / 19).
- **Cost:** P is kept sorted by (b, a); each column birth or death costs O(|P|) (insert plus one row-run sweep), never
  the bounding box's area.
- **Choices** (LIFE_ABI.md 15.61; please confirm): tiles connect through shared edges (hex: six neighbours; square
  bases: the four axial ones, also on square8, so a corner contact closes a gap); islands are not merged (no convex
  hull), so the gaps between separate pieces stay free and the GB7 islands keep footprint 7; the footprint changes at
  the record, so the motion up to t uses the footprint at t-.

### 2. The life-length draw (GB11)
Gate GB11 was read from smoke runs before the pilot: evolved CATCH bodies were still growing at T in 89-98% of their
lives, which meets its condition (more than 10% of lives growing by more than 10% after T/2). So the per-generation
life-length draw is on: `life.T_choices: [768, 1024, 1536]` in configs/life_catch.yaml, and so in the L_max 2, seeded
and SPECK configs too. Each generation's lives and its recheck lives last one length, drawn uniformly and keyed by the
run seed and the generation only; valid, held-out, final, clone, size-curve and founder lives keep T = 1024
(founder_T). What was checked, each with a test (`tests/test_life_evolve.py`):
- Seeds: the life seeds do not depend on the length (the same seeds with the draw off), and no cell reads T, so a
  generation's lives at 768 are the first part of the same lives at 1536 (fate logs agree up to the cut; also checked
  on evolved genomes of the 300-generation smoke). Over 300 generations the three lengths came up 80, 107 and 113
  times; a different run seed gives a different sequence.
- Recheck lives share the generation's length and the seeds they had without the draw.
- Fitness stays per unit of each life's own length: the window is its T, and the extinction charge runs to its own end
  (a zygote that dies at once scores -c_live at 768, 1024 and 1536). The hand-built 2-cell clicker scores the same at
  every length (F(768) - F(1536) = -0.0001 +- 0.0017, n 2048 paired), but its per-life SD is 0.111 at 768 and 0.080
  at 1536: short generations are noisier.
- Evals: `evals` still counts genome evaluations whatever the length (checked on every smoke run: the founders plus
  256 + 64 x 4 / 3 per generation); a generation at 1536 costs twice one at 768, so selection compute in nominal lives
  is about evals x T_sel_mean / 1024 (the draw's mean is 1109, +8%).
- Judged lives: the valid score of a run with the draw is the best genome on lives of the nominal T, recomputed.
- Added: curves.jsonl and lineage.jsonl rows record the generation's `T`; results rows add `T_choices` and
  `T_sel_mean`, and every CATCH row adds GB11's readout, `n_half` (the best genome's size at T/2 on its final lives cut
  there) and `growing` (the share of those lives that grew by more than 10% after T/2); a config that overrides its
  preset's world records `world_over`, and the aggregate shows such a world as `preset[key=value,...]`.
- Guard: evolution refuses a nominal `life.T` outside `T_choices` (a run that overrides T alone would otherwise select
  on other lengths than it is judged on; the tiny test configs scale the choices to 144, 192, 288).

### 3. SPECK in the kernel: gates GS1-GS6 (S1 acceptance A1-A4)
SPECK (catch_v1 with a small target halo, sigma 0.6, worth R_cap 500) was the S1 prototype study's candidate: an
outward router at ring 4 passed the no-cliff test A1-A4 there. It is now a preset (`catch_speck`, `_l4`, `_l2`; every
other key catch_v1's, c_miss 2 included) and is tested in the real kernel after RT-T1 by `scripts/life_gates.py
--world speck` (docs/LIFE_GATES.md, SPECK section; outputs/life_gates/gates_speck.json).

**Bodies** (`src/life/handbuilt.py`, SPECK section; program mode, references only). Role bodies whose cells take one of
six roles from the shape (rim or interior sensor by n_view, the centre sensor, rim or interior motor, the hotspot);
interior motors are quiet, since they can never pull. Six reflexes (full and sense-hollow rings 2-4; no lateral
weight) and the router at ring 4 (interior coincidence detectors relaying on channel 1, rim sensors firing on one
relay), each tuned in the kernel with the same budget (160 random candidates on 48 lives, then coordinate ascent with
restarts to 300 knob sets on 192 hill lives; tuning seeds 17-18 M) on grids of GRN-decodable values, from the red
team's knobs without the prototype-only slow state, polarity and hold. About 2.8 hours of 4-thread runs (two or three
at a time); the knobs are frozen in `handbuilt.SPECK_TUNED`. Gates on fresh lives (seeds 19,000,000 + s; 1024 paired
lives per point, 768 per growth-path point); the gate run took 23 minutes on 4 threads (peak 0.57 GB), and 29
minutes (0.64 GB) with GS3's reported path from the best reflex, part of it next to other jobs.

| gate | measured | verdict |
|---|---|---|
| GS1 (A1) the S0 champion earns | the GB4 ring-3 column reflex +4.995 ± 0.056 (catch_v1 +3.892); lone −0.020; paired +5.015 (z 89) | PASS |
| GS2 (A2) router beats every tuned reflex by 3 SE | router@ring4 +11.263 ± 0.089; best reflex (sense-hollow ring 3) +9.016 ± 0.084; **+2.247 ± 0.100 (z 22.4)**; the other reflexes z 26-77 | PASS |
| GS3 (A3) growth pays; path | router knobs on rings 1-6: +2.78, +3.99, +6.82, **+11.26**, +4.02, −2.53; re-tuned rings 3 and 5 +8.71, +7.54; every smaller body z ≥ 22 below; path from the ring-3 reflex: lowest −0.09 ± 0.07 (z −1.4), end +2.32 (z 20). Reported: from the best reflex (sense-hollow ring 3) the path first dips by 0.24 ± 0.11 (z −2.2) | PASS (registered); not valley-free from the best reflex (reported) |
| GS4 (A4) lateral_off removes the gain | router → +1.669 with lateral_off: removes +9.59, 4.3 times the gain; reflexes move ≤ 0.004 | PASS |
| GS5 router as a GRN genome | 0 role mismatches (11 gene states, 1,606 grown cells); ~50-column disks after growth +9.395 vs program twins +9.321 (z 0.5) | PASS |
| GS6 GB7's cheats in SPECK | best blind presser +0.292, above the lone zygote by +0.312 (z 29), below the clicker by 0.186; at c_miss 10 it loses (−0.289, z −27) | **FAIL** |

- **The router's lead is larger in the kernel than in the prototype** (+2.25 against +1.20 ± 0.12), with neither side
  given the prototype's per-cell slow state, and with the hollow reflex no longer drag-discounted (RT-T1). The router
  catches 28.3 targets per life against 21.0, at equal misses.
- **c_miss 2 vs the prototype's 1.** For A1-A4 nothing changes: re-priced at c_miss 1 every router − reflex difference
  moves by at most 0.006. But neither price keeps rule N10 in SPECK: a blind click breaks even at a 0.4% capture rate
  at c_miss 2 (0.2% at 1), against v1's 1.96%, so blind pressers (and the blind GRN presser) earn about +0.26 to +0.29,
  above the lone zygote though below the sensing clicker (+0.48). c_miss 10 restores v1's break-even rate; at that
  price every cheat loses and A1-A4 do not move (router − best reflex +2.246). The preset keeps c_miss 2 as
  specified; **decision for the user**.
- **Delay** (reported; knobs not re-tuned): router − best reflex +3.32 ± 0.11 at d0 0.5, +2.25 at d0 1, **−0.56 ± 0.08
  (z −6.8) at d0 2**, −0.48 at d0 2 with delay_sd and jit 0.5. As in the prototype, routing pays only while messages
  are fast compared with the small target's stay under the body.
- **The registered growth path is not smooth everywhere.** Judged against its start (the red team's valley depth) it
  never falls by more than 1.4 SE; step by step, one move falls: at ring 3 + 4 columns with interior gain 1/4 (a local
  high point, +9.10), adding gain or one more column costs 0.23-0.25 (z −2.3 to −2.5) before a plateau (+8.7 to +9.1)
  leads on.
- **From the best reflex the path has a valley** (review finding 1, part 6; reported in GS3, outside the verdict).
  The registered path starts at the full ring-3 reflex with deaf interior sensors, 0.24 ± 0.11 (z −2.2) below GS2's
  best tuned reflex, the sense-hollow ring 3. Started from the best reflex itself (the same grid with its knobs), the
  path dips to −0.24 ± 0.11 (z −2.2; on independent lives −0.44 ± 0.11, z −4.0) and is clearly above it only from
  ring 3 + 12 columns (16 on independent lives). Details in part 6.
- **GS5.** The router written as a GRN genome (`handbuilt.router_genome`: the GB9 column grower plus six role genes
  reading n_view and lineage) grows ragged disks of about 50 columns in which every cell decodes exactly its role, and
  earns what program twins of the same shapes earn. After growth it beats the placed best reflex by +0.39 ± 0.16
  (z 2.5); over the whole life, with growth, it ties it (−0.17 ± 0.14). The placed ring-4 router earns 1.8 more. The
  genome is a reference, not a seed.
- **Not tested:** A2's Rg (a reflex with a per-cell slow state; program mode has none), and A1's best evolved S0 body
  (it waits for the S0 pilot).

### 4. Smoke runs (with the drag fix and the draw)
configs/life_catch.yaml and life_catch_seeded.yaml with the draw, and the SPECK world as overrides (before the preset
existed); 4 threads per run, 3-4 runs at a time, load 11-27 on 14 CPUs, mean 18. Best genome after the last
generation, on 64 fresh lives at T 1024 (lives keyed 10,000 + seed, never seen by the run), paired against the
hand-built column reflex (program mode) on the same lives; reliance from the run's own final forks at T/2:

| arm (seed, generations) | best body: cells (S / M / H) | F | minus the 2-cell clicker | minus ring 1 | size at T/2 / T / 1.5 T | growing (best / population) | msg / sense reliance | s per generation |
|---|---|---|---|---|---|---|---|---|
| v1 L4 unseeded (s0, 150) | 2.0 (1.0 / 0.97 / 0.03) | +0.023 +- 0.011 | -0.007 +- 0.011 | -1.008 +- 0.052 | 1.8 / 2.0 / 2.0 | 0.14 / 0.10 | 1.0 / 1.0 | 0.90 (2-cell: 0.67) |
| v1 L4 unseeded (s1, 150) | extinct | -0.020 (charged) | — | — | 0 | 0 / 0 | — | 1.00 |
| v1 seeded (s0, 100) | 203 (103 / 100 / 0) | +0.237 +- 0.127 | +0.21 +- 0.13 | -0.79 +- 0.14 | 33 / 203 / 594 | 0.97 / 1.00 | 1.0 / 1.0 | 12.3 (gens 40-99: 14.8) |
| SPECK L4 unseeded (s0, 40) | 20.3 (9.8 / 8.9 / 1.6) | +0.626 +- 0.087 | +0.05 +- 0.09 | -2.18 +- 0.15 | 9.0 / 20.3 / 33.0 | 1.00 / 0.79 | 1.0 / 1.0 | 2.4 |
| SPECK seeded (s0, 40) | 77 (39 / 38 / 0) | +2.79 +- 0.17 | +2.22 +- 0.18 | -0.01 +- 0.19 | 22 / 77 / 190 | 1.00 / 1.00 | 1.0 / 1.0 | 10.8 |

References on those lives: v1 clicker +0.031 +- 0.013, ring 1 +1.03 +- 0.05; SPECK clicker +0.57 +- 0.06, ring 1 +2.80
+- 0.15. The run rows' own final F (their final lives): v1 s0 +0.025 +- 0.010; v1 seeded +0.33 +- 0.09 (the best of its
top 8, re-measured: +0.77 +- 0.06); SPECK L4 +0.65 +- 0.09; SPECK seeded +2.65 +- 0.19. No life was invalid and no
ledger check failed in any run.
- **Past the clicker and ring 1?** Unseeded v1: no. Both seeds sat at <= 2 cells for 150 generations, the best equal to
  the hand clicker (z -0.6), and seed 1 lost its clicker lineage at generations 144-148: the bodies among its 32 parents
  fell 27, 22, 6, 1, 0 while six short (T 768) generations ran in a row, and genomes that die at once (charged exactly
  -c_live) or stay a silent lone cell outscored clickers whose lives caught nothing. The founder is marginal: the
  census's genuine founder has F +0.020, and the hand clicker's margin over the lone cell, +0.04, is less than half its
  per-life SD of 0.08-0.11 (33-42% of its lives score at or below the lone cell). The earlier 300-generation unseeded
  run (before the review fixes) climbed only after generation 200. Seeded v1: it grew at generation 4, but after 100
  generations its best is +0.21 +- 0.13 above the clicker (1.6 SE) and -0.79 +- 0.14 below ring 1, at 10-15 times ring
  1's size. SPECK seeded: at the ring-1 level after 40 generations. SPECK unseeded: 18-20 cells by generation 40, equal
  to the clicker so far.
- **Do they stop growing before T?** No lineage that grows does. The seeded v1 best grows from 33 cells at T/2 to 203 at
  T and 594 at 1.5 T, and all 256 lives of its final population (32 genomes x 8) grew by more than 10% after T/2; the
  SPECK bests too (100%; their populations 79% and 100%). Only the 2-cell clickers are static. So GB11's condition holds
  in these runs too, and 100 generations of the draw have not stopped growth; the pilot reads it again from its own
  rows.
- **Message certificate.** Every living best genome passes both forks: the certificate (contacts, chemistry and division
  off at T/2) and receptor_off each remove 100% of the second-half income. lateral_off removes nothing from the seeded
  bodies (+0.12 +- 0.11, +0.18 +- 0.18) and 0.92 +- 0.40 of 1.77 from the SPECK unseeded body (2.3 SE; one body, 16
  forks: a hint, not a finding).
- **Time.** Founder sampling (16,384 genomes x 2 lives): 458-490 s in v1, 654 s in SPECK (93 earners, 8 founders, screen
  F +0.80). Generations: 0.5-1.6 s while bodies are 2 cells (mean 0.9-1.0); in the seeded runs about 4, 8 and 22-26 s at
  T 768, 1024 and 1536, and 41-56 s when the population's mean body passes 50 cells. Wall time is 0.32-0.54 us per
  cell-unit of selection lives on 4 threads. Peak memory: 0.29 GB (a seeded run of 30 generations with bodies up to 202
  cells, 4 threads).
- **SPECK configs** (prepared, not decided): configs/life_speck.yaml (unseeded, L_max 4) and life_speck_seeded.yaml
  (the same labelled seed genome as the v1 seeded arm) are life_catch.yaml in the preset `catch_speck_l4`. Our choices,
  recorded in the config: held-out worlds at the v1 list's relative steps around SPECK's values (v_t 0.05 and 0.2,
  R_cap 250 and 1000, sigma 0.4) plus sigma 1.5; skill_at 4.0, v1's rule (between ring 1 and ring 2) on SPECK's kernel
  ring curve. Measured while preparing (kernel, hand-built column reflex, n 256 per ring, paired):

| world | ring 0 (clicker) | ring 1 | ring 2 | ring 3 | ring 4 |
|---|---|---|---|---|---|
| v1 | +0.024 +- 0.006 | +0.984 +- 0.023 | +2.843 +- 0.035 | +3.854 +- 0.037 | +3.316 +- 0.027 |
| SPECK | +0.467 +- 0.029 | +2.958 +- 0.086 | +5.014 +- 0.125 | +5.064 +- 0.114 | +0.800 +- 0.079 |

- Selection noise is higher in SPECK: the per-life SD of F is 1.8-2.0 at rings 2-3, against 0.6 in v1.

### 5. Pilot run matrix and time estimate
`scripts/run_catch_pilot.sh` takes a run matrix by arm: `PILOT_ARMS="name:seeds[:generations] ..."`, arms v1_l4,
v1_l2, v1_seeded, speck_l4, speck_seeded; runs interleave by seed; `PILOT_PLAN=1` prints the plan. Per run, low /
central / high, at the smokes' load (assumed: at load 30 up to half again):

| arm | generations | per run (h) | assumption |
|---|---|---|---|
| v1 L4 or L2, unseeded | 500 | 0.26 / 0.62 / 2.7 | 0.13 h founders, 1 s per 2-cell generation; 0 / 3 / 10 of 10 seeds climb at generation 200, then 10 / 15 / 30 s per generation |
| seeded (v1 or SPECK) | 300 | 0.81 / 1.2 / 2.4 | bodies from generation 10, 10 / 15 / 30 s per generation (500 generations: 1.4 / 2.0 / 4.1) |
| SPECK L4, unseeded | 500 | 1.35 / 1.9 / 3.6 | 0.18 h founders, 100 small-body generations at 2 s, then 10 / 15 / 30 s |

- The full matrix (v1 L4 x10, v1 L2 x5, v1 seeded x5, SPECK L4 x10, SPECK seeded x5, all 500 generations): 31 / 49
  / 117 job-hours, **16 / 24 / 58 h** on 2 jobs. Over the budget.
- **Proposed: `v1_l4:10 v1_l2:3 v1_seeded:3:300 speck_l4:6 speck_seeded:3:300`**: 16 / 27 / 71 job-hours, **8 / 13 / 35
  h** on 2 jobs. Why: v1 L4 keeps 10 seeds x 500 generations because S0's success and kill rules are written for them;
  v1 L2 lives the same lives as L4 until a cell grows above the act plane (the v1 smoke bests carried hidden cells in 5
  of their 400 generations), so 3 seeds show whether hidden planes cost anything; the seeded arms are the declared hedge
  and grow within 10 generations, so 3 seeds x 300 generations answer "does evolution climb from a working reflex" at
  60% of the cost; SPECK L4 keeps the full 500 generations, because routing can only pay once bodies pass the reflex
  optimum (ring 2-3) and reach ring 4, and drops to 6 seeds to fit.
- **The script's default is that matrix's v1 part** (`v1_l4:10 v1_l2:3 v1_seeded:3:300`: 6 / 12 / 42 job-hours, 3 / 6 /
  21 h); the SPECK arms run only when PILOT_ARMS names them. `PILOT_PLAN=1` on this tree prints 16 runs (v1 L4 x10,
  v1 L2 x3, v1 seeded x3 at 300 generations), and 25 with the two SPECK arms.
- The range is wide because it depends on how many v1 seeds climb and how large grow-forever bodies get at T 1536; if
  most v1 seeds climb, the v1 L4 arm alone needs up to 27 job-hours.

### 6. Review of this work (2 findings, both reproduced with the reviewers' scripts and seeds)

| finding | reproduced | real? | fix | regression test |
|---|---|---|---|---|
| GS3's valley-free path starts at the full ring-3 reflex (with deaf interior sensors), 0.24-0.50 F below the best tuned reflex, the sense-hollow ring 3; from there the path first falls | yes, to the digit: start − hollow3 −0.242 ± 0.109 (z −2.2), lowest −0.335 ± 0.109 (z −3.1), crossing at ring 3 + 12 columns (+0.325, z 3.0) on the gate lives; −0.503 (z −4.6) to −0.303 on lives 40,000,000 + s | yes: "valley-free" held only from a sub-optimal reflex | GS3 reports the path against the best reflex and searches the same grid with the best reflex's knobs starting at it (`path_from_best_reflex`, `reported_checks`); the registered verdict is unchanged; LIFE_GATES.md and this file state the valley | `test_routing_knobs_are_silent_on_a_sense_hollow_body` (fast), `test_gs3_reports_the_path_from_the_best_reflex` (slow), and `_rejudge_speck` now re-derives `reported_checks` |
| a one-column slit from a hole to the outside restores the drag discount RT-T1 removed | yes, to the digit (n 2048, seeds 41,000,000 + s): slit body − same body with quiet sense cells refilling the slit +0.223 ± 0.010 F in catch_v1 (z 21), +0.177 ± 0.021 in SPECK | yes, a residual of 15.61's rule; low impact (such bodies are 2.2-4.7 F below the full ring 3; no gate changes) | recorded in LIFE_ABI.md 15.61 with the numbers and two candidate laws; not closed (part 9) | `test_a_slit_to_the_outside_leaves_the_hole_free` (spec, kernel export, and the kernel's dot drags like the 29 columns) |

**Finding 1 in detail.** GS2's best tuned reflex is the sense-hollow ring 3 (centre and ring-3 sensors under a full
act disk, 56 cells; +9.032 on GS3's 768 path lives), which is also the better reflex shape in catch_v1 (part 1), so an
evolved S0 population may well sit there. The registered path starts at the full ring-3 reflex with its 18 interior
sensors deaf (74 cells): 0.242 ± 0.109 below the best reflex (z −2.2), mostly their upkeep, and not clearly above it
(by 2 SE) until ring 3 + 12 columns. GS3 now also searches the same grid (ring 3 + 0-24 ring-4 columns × interior gain
0-1/2) with the best reflex's own knobs, starting at the best reflex itself. The routing knobs are silent on a
sense-hollow body (bitwise, at every gain), so the first real step fills the interior with 18 sensors at once. Best
monotone path, 768 paired lives per point, minus the best reflex:

| path point (grid with the best reflex's knobs) | gate lives (19,000,000 + s) | independent lives (40,000,000 + s) |
|---|---|---|
| interior filled, gain 1/4 | −0.224 ± 0.111 (z −2.0) | −0.291 ± 0.111 (z −2.6) |
| + 4 columns | −0.028 ± 0.111 | −0.295 ± 0.112 (z −2.6) |
| gain 3/8 (the lowest point) | −0.243 ± 0.109 (z −2.2) | −0.438 ± 0.111 (z −4.0) |
| + 8 columns | +0.004 ± 0.109 | −0.267 ± 0.105 (z −2.5) |
| + 12 columns | +0.263 ± 0.111 (z 2.4) | +0.198 ± 0.116 (z 1.7) |
| + 16 columns | +0.596 ± 0.112 (z 5.3) | +0.610 ± 0.111 (z 5.5) |
| ring 4, gain 1/2 (the end) | +1.974 ± 0.111 (z 17.8) | +1.946 ± 0.118 (z 16.5) |

The independent lives chose the same path. Both reported checks fail: by about 0.2 SE beyond the 2-SE line on the gate
lives, and clearly on the independent ones. GS3's registered verdict (PASS) is unchanged, since the registration names
the ring-3 reflex as the start.
- What it means for the pilot: from the best reflex's shape a SPECK lineage must first pay about 0.2-0.4 per unit
  (2.5-5% of F) for interior sensors and the first ring-4 columns before routing pays. That is small next to SPECK's
  selection noise (per-life SD 1.8-2.0; a parent is chosen on 7 lives, 3 plus 4 for the shortlist, an SE of about
  0.7), so drift can carry a population across, but selection does not pay for the first steps.
- Not searched: other path families, for example interior relays added ring by ring with roles placed by site. In the
  role bodies an interior sensor takes the relay role only when all six neighbours are present, so a partly filled
  interior holds only rim-role sensors under quiet motors.
- Two further checks by the reviewer, not rerun here (scripts in the review scratchpad): the registered path, chosen on
  the gate lives, is still valley-free against its own start on the independent lives (lowest point the start, worst
  step −0.099 ± 0.100); and A2 holds against a harder-tuned hollow reflex (700 evaluations, a widened grid, new seeds:
  +8.640 ± 0.082 on GS2's lives, below the frozen +9.016; router minus it +2.62 ± 0.10).

**Finding 2 in detail.** The thick hollow body (centre + rings 2-3 in every plane, n_fill 37) without the
edge-sharing columns (2, 0) and (3, 0) encloses nothing, so it drags like its 29 columns though it spans the same disk.
Against the same body with two quiet sense cells refilling those columns in the sense plane only (identical act-plane
faces and pulls; n_fill 37): catch_v1 +0.223 ± 0.010 (speed 0.401 against 0.356 = sqrt(37 / 29)), so about +0.18 F of
drag discount after the quiet cells' upkeep, the size RT-T1 removed from the closed thick hollow (−0.157); SPECK +0.177
± 0.021. Against the closed thick hollow the slit body gains in SPECK (+0.060 ± 0.025, z 2.4) and loses in catch_v1
(−0.199 ± 0.012). These bodies earn +1.62 (catch_v1) and +0.35 (SPECK) against the full ring 3's +3.86 and +5.05.
- Why not closed now. Two local, O(n) laws would close it: the morphological closing of P by the radius-1 disk before
  the fill, or the filled convex hull of each edge-connected piece (both give the slit body 36 tiles). Measured on
  geometry alone (scratchpad scripts `prepilot_fix/footprint_alts.py` and `footprint_alts_gb9.py`), neither re-prices
  a hand-built gate body without holes (rings 0-6, the 34 column-ladder bodies, runners, islands, tonic rings, the six
  SPECK shapes, GS3's 25 path bodies and 31 ring-4-plus bodies), but both charge ragged grown bodies for their
  notches. On the end-of-life bodies of the
  smokes' best genomes (32 lives each): the closing changes 24 of 32 seeded v1 bodies (mean 98.2 → 100.5 tiles), 16 of
  32 SPECK unseeded (10.7 → 11.3) and 12 of 32 SPECK seeded (38.6 → 39.2); the hull 25, 24 and 18 (98.2 → 103.6, 10.7
  → 12.3, 38.6 → 40.1); GS5's grown routers 6 and 8 of 16; the GB6 and GB9 column grower 10 and 11 of 32 (40.2 →
  40.5 and 40.6). Either is a kernel and spec change (new T-tests, gates and smokes rerun) that would raise the mean
  footprint of grown bodies by 1.6-5.6% (closing) or 3.9-15% (hull), to remove a discount that no competitive body
  uses. So it is left to the user.

### 7. Tweaks and choices
Each keeps sensing, acting and messaging local, adds no clock and designs no behaviour; hand-built bodies stay
references and gates.
1. **Drag from the filled footprint** (RT-T1, LIFE_ABI.md 15.61), with its choices: edge-sharing tiles, islands not
   merged, the footprint at t- for the motion up to t. Residual recorded: a slit to the outside (finding 2).
2. **The per-generation life-length draw is on** in every CATCH config (GB11's prescribed switch), and evolution refuses
   a nominal T outside the drawn lengths (a guard).
3. GB11's readout, the drawn length and world overrides are recorded per run.
4. **SPECK presets** `catch_speck`, `_l4`, `_l2` (catch_v1 with sigma 0.6 and R_cap 500); its configs' held-out worlds
   and skill_at 4.0 are ours.
5. **The pilot matrix by arm**, with per-arm seeds and generations (`scripts/sweep.py` takes `path:N[:G]` and
   `--plan`); the default drops from 10 seeds per arm (30 runs) to v1 L4 x10, v1 L2 x3 and seeded x3 at 300
   generations.
6. **SPECK gate choices** (LIFE_GATES.md, SPECK deviations): role bodies with quiet interior act cells; GRN-decodable
   grids widened from the red team's; equal tuning budget per body; GS3's criteria (the path judged against its start)
   with steps reported; GS5 and GS6 beyond the registration.
7. **This round:** GS3 also reports the growth path from the best tuned reflex (`path_from_best_reflex`,
   `reported_checks`), outside the verdict, because the registered path starts from the ring-3 reflex. The registered
   criteria and verdict are unchanged.

### 8. Verification
- **After RT-T1** (before this round's review): CATCH GB3-GB13 9 of 9 pass, gates_catch.json identical leaf for leaf
  (463 s, 4 threads, peak 0.60 GB): no gate body encloses a tile while it moves. BELL G1-G10 and S8 identical leaf for
  leaf (10 of 11 pass, G10 on its known check; 379 s, peak 0.73 GB). The kernel checks are in part 1.
- **SPECK tests** (with the gates): fast tests (`tests/test_life_handbuilt.py`) for the preset; role assignment and
  shapes; a role body equals the column reflex where no motor is interior (bitwise) and differs only by the quiet
  motors' spike costs at ring 2; grids and starts on the GRN grid; the tuner and the bottleneck path; routers (placed,
  with lateral_off, and grown) bitwise equal to the reference. Slow tests (`tests/test_life_gates.py`): the SPECK gate
  file, seed ranges and the frozen knobs, tune reproducibility, GS1-GS6 recomputed in part and pinned, and
  `main --world speck`.
- **Gates, rerun on this tree after the review** (kernel library `life_66f624a8719dfae0.so`, unchanged this round;
  4 threads each, two or three gate runs at a time):
  - BELL G1-G10 and S8: 10 of 11 pass (G10 on its known check); gates.json identical leaf for leaf (all 4134 leaves
    outside the metadata and run times); 582 s, peak 0.73 GB.
  - CATCH GB3-GB13: 9 of 9 pass; gates_catch.json identical leaf for leaf (4253 leaves); 674 s, peak 0.55 GB.
  - SPECK GS1-GS6: GS1-GS5 pass and GS6 fails, as before. Every leaf is identical except GS3's new reported block
    (333 leaves added, one criteria sentence and one note); GS3's two reported checks are False. 1745 s, peak 0.64 GB.
- **Tests, this round:** 631 fast tests pass (59 s); all 127 slow tests pass in one run on the final tree and gate
  files (349 s); ruff is clean on src, tests and scripts. New: two fast tests
  (`test_routing_knobs_are_silent_on_a_sense_hollow_body`, `test_a_slit_to_the_outside_leaves_the_hole_free`), one
  slow test (`test_gs3_reports_the_path_from_the_best_reflex`), and the SPECK re-judge now checks `reported_checks`.
  The style test's allowance for scripts/life_gates.py drops from 3 long lines to 2 (one was split).
- **Unchanged elsewhere:** the kernel, the reference, spec and every src/ file are untouched this round (only
  scripts/life_gates.py, tests, configs' comments and docs changed), so kernel = reference bitwise as in part 1. The
  legacy local smoke (configs/local_smoke.yaml) run on this tree is identical to HEAD's (curves and best genome
  byte for byte; the results row differs only in name and wall_s). Earlier in this pre-pilot work a BELL life smoke
  (configs/life_smoke.yaml) was identical to HEAD's too (curves, genomes, lineage, clones, population and results rows
  apart from times, git fields and the run name).

### 9. Open issues and decisions for the user (as left by the workflow; decided in part 10)
- **c_miss in SPECK** (GS6): at catch_v1's c_miss 2 blind clicking pays in SPECK (a blind click breaks even at a 0.4%
  capture rate); c_miss 10 restores v1's 1.96% and changes nothing in A1-A4. Keep 2, or set 10 for the SPECK arms
  (one line in configs/life_speck.yaml: `world: {c_miss: 10.0}`).
- **Whether the SPECK arms run**, and in which matrix (part 5). Caveats that travel with SPECK: the router's lead
  reverses at d0 2; Rg is untested; from the best reflex the growth path has a valley of 0.22-0.44 F (z −2.0 to
  −4.0 on two seed sets; finding 1), which a population could cross by drift (a parent's selection score on 7 lives
  has an SE of about 0.7 in SPECK, per-life SD 1.8-2.0) but which selection does not pay for.
- **The slit residual** (finding 2): keep the filled footprint as is (recorded), or close it with the closing or the
  per-piece hull (a kernel change that would re-price many grown bodies; part 6).
- **Still open from BODY-1 v1:** confirm tweaks 10 (c_miss 2) and 11 (projected footprint) and RT-T1's choices; the
  founder is rare (1 in 8,192) and marginal, so the unseeded v1 arm can lose its clicker to noise and the
  pre-registered kill rule (>= 8 of 10 seeds at <= 4 cells after 500 generations) may fire for that reason rather than
  for the world; growth does not stop (the seeded lineage reaches 594 cells at 1.5 T; the cell guard is 1,024), and big
  bodies at T 1536 dominate the compute; GB9's single-mutant scan was not run; the kernel's 2-cell clicker sits about
  9% above the prototype's at equal prices (unexplained).
- **Before launching:** commit (the tree is dirty; every results row records git_dirty), then
  `scripts/run_catch_pilot.sh` (default matrix) or with `PILOT_ARMS` naming the SPECK arms.

### 10. Decisions before launch and the pilot's pre-registration (2026-10-08)
Taken under the user's standing approval of minor tweaks that keep sensing, acting and messaging local, add no clock
and design no behaviour.
1. **SPECK prices a miss at 10** (LIFE_ABI.md 15.62). R_cap / c_miss = 50 as in v1, so a blind click again breaks even
   at 2 / 102. A price only: no cell reads it and lives are unchanged. SPECK gates rerun (`--world speck --threads 8`,
   1770 s, peak 0.66 GB): **GS1-GS6 all pass**. Champion +4.946 ± 0.056; router@ring4 +10.910 ± 0.090 against the
   best tuned reflex (sense-hollow ring 3) +8.664 ± 0.084, +2.246 ± 0.101 (z 22.3, unchanged from c_miss 2);
   lateral_off removes +9.641, 4.3 times the gain; the GRN router after growth +0.070 ± 0.154 against its twins; the
   2-cell clicker +0.463 (lone −0.020), and the best blind presser, re-screened at the new price, −0.065 ± 0.008
   (below the lone zygote, z −5.8). Delay: router minus best reflex −0.58 ± 0.08 at d0 2 (the pilot runs d0 1).
   From the best reflex the growth path still dips (start −0.25, lowest −0.34 ± 0.11, z −3.1), as reported in part 6.
2. **A SPECK smoke at c_miss 10** (1 seed x 40 generations, 4 threads, 389 s) checks that founders still exist: 8 of
   16,384 sampled genomes score (0.35% of the census at F >= 0, against 0.57% at c_miss 2; best founder +0.69). By
   generation 40 the best genome grows 63 cells (S 30, M 21, H 12.5) and earns +0.37 ± 0.09 on 64 fresh lives
   (the c_miss 2 smoke's best: +0.65 at 18.5 cells), with 5.3 misses per life against the c_miss 2 smoke's 30: the
   price selects for clicking on evidence. The message certificate removes all of its second-half income; lone cells
   are 0.4% of the population.
3. **The SPECK arms run.** SPECK passes every gate, and in the smokes it is the world where unseeded evolution leaves
   the 2-cell clicker quickly (the v1 founder's edge over the lone cell is +0.04 with per-life SD 0.08-0.11; SPECK's
   2-cell clicker is +0.48 above it).
4. **The slit residual stays recorded, not closed** (part 6, finding 2): no competitive body uses it, and both closing
   laws re-price ragged grown bodies. The pilot analysis checks it on the evolved bodies: if a final best body gains
   more than 0.1 F from a slit (its filled footprint against the closing law's), the law is revisited.
5. **The BODY-1 v1 tweaks are kept** (c_miss 2 in v1, the projected and then filled footprint, the extinction charge,
   the founder prior and budget) and the GS3 dip from the best reflex is reported, not acted on.
6. **Matrix:** `v1_l4:10 v1_l2:3 v1_seeded:3:300 speck_l4:10 speck_seeded:3:300` (29 runs, 500 generations unless
   noted), now the default of `scripts/run_catch_pilot.sh`, on 4 jobs x 3 threads (the machine's sweep setting, 12 of 14
   cores). About 22 / 34 / 86 job-hours at 4 threads (low / central / high), so roughly 7 / 11 / 29 h. SPECK L4 has 10
   seeds so its criteria count seeds like S0's.

**Pre-registered criteria** (judged from the results rows and final genomes; the seeded arms are hedges and never the
main result):
- **S0, v1 L4** (proposal 8.2, unchanged): success if >= 5 of 10 seeds reach F >= +2.0 (`skill_at`) within 500
  generations; kill if >= 8 of 10 seeds sit at <= 4 cells after 500 generations. v1 L2 is read against v1 L4 (do the
  hidden planes cost or help?).
- **S1 start, SPECK L4:** success if >= 5 of 10 seeds reach F >= +4.0 (`skill_at`, midway between ring 1 and ring 2)
  within 500 generations; kill if >= 8 of 10 seeds sit at <= 4 cells after 500 generations.
- **S1 routing, SPECK L4** (A2 and A4 on evolved bodies): count the seeds whose final best genome, on 1024 fresh lives
  at T 1024 (seeds disjoint from every gate and run), beats the best tuned reflex (`reflex@hollow3`, frozen
  `handbuilt.SPECK_TUNED` knobs, +8.66) by more than 3 paired SE, and loses at least half of that lead under
  lateral_off. Reported as a count out of 10; one such seed is the first evolved router.
- **GB11:** read from every results row (`n_half`, `growing`); growth that never stops is reported, not judged.


## 2026-10-09 — BODY-1 pilot: results, how the evolved bodies work, compute audit
The pilot of Pre-pilot part 10 ran to completion: 29 runs, 0 failed, 81.8 run-hours on 4 jobs x 3 threads, started
2026-10-08 07:09 and finished 2026-10-09 06:18 (the longest run, SPECK L4 s6, took 9.7 h). Code: git 8e75606. Seven
runs that started after the analysis script was added record `git_dirty`: the only differences were new, untracked
files (`scripts/catch_pilot_analysis.py` and its test); no tracked file changed. Analyses and audits ran on the same
laptop during the last hours (at nice 19, load up to 30-58), so late generations of the last runs ran up to 4-10x
slower and their wall times are not representative. Summary tables: `results/catch_pilot/` (`summary.md`,
`results.csv`, `analysis.md` from `scripts/catch_pilot_analysis.py`, `mechanisms.json`, `compute_audit.json`).

**In brief.**
- **S1 start (SPECK L4) succeeds:** 7 of 10 seeds reach F >= +4.0 (5 needed); none sits at <= 4 cells. Final bests
  +2.70 to +6.94, median +4.91.
- **S0 (v1 L4) neither succeeds nor is killed:** 4 of 10 reach +2.0 (5 needed) and 6 of 10 stay at 1-2 cells (8 needed
  to kill). Unseeded v1 starts growing in about 4 seeds in 10; every SPECK seed grows.
- **S1 routing: 0 of 10.** No evolved body beats the tuned reflex (+8.69); the best, s5, is at +7.06 (lead -1.63,
  z -17). Yet the better bodies depend more on lateral messages (Spearman 0.71 between F and the share lateral_off
  removes; s6 loses all of +6.22).
- **Bounded growth emerges in SPECK:** the five best SPECK bodies (s4-s8) stop growing within their life (GB11 share
  growing 0.00-0.02); the other five, all worse, are still growing at T.
- **Mechanisms (part 4, post hoc):** every evolved body regrew the column reflex; three lineages added local
  computation on top: neighbour voting with an antenna fringe and a latch (s4), cooperative detection with feedback
  inhibition (s5), gain set by crowding with in-life adaptation (s2). All four make direction-specific synapses from a
  morphogen gradient. Hidden planes are inert everywhere.
- **Selection is noisy:** within each generation's 64-genome recheck shortlist, first-pass and recheck F rank-correlate
  at a median of about 0.03; per-life F has an SD of about 2.0 in SPECK, almost all of it capture-count noise.
- **Compute (part 5):** about 0.1 CPU-s per life, so 24 CPU-h per 500-generation run of ~120-cell bodies; an exact
  "fast" kernel mode would give 1.24-1.35x; a rented 192-core CPU box would run a pilot this size in 1-1.5 h for
  $6-16; GPUs would not help.

### 1. Pre-registered criteria
| arm | seeds | final F by seed (results rows) | reached skill | <= 4 cells | median F | verdict |
|---|---|---|---|---|---|---|
| v1 L4 (S0) | 10 | +0.03 -0.02 -0.02 -0.02 -0.02 +2.66 +2.50 -0.02 +2.60 +2.72 | 4 (skill 2) | 6 | +0.01 | no success, not killed |
| v1 L2 | 3 | +0.03 +0.01 +3.10 | 1 (skill 2) | 2 | +0.03 | - |
| v1 seeded (300 gens) | 3 | +1.84 +2.17 +1.35 | 2 (skill 2) | 0 | +1.84 | - |
| SPECK L4 (S1 start) | 10 | +3.45 +3.07 +4.02 +2.70 +5.10 +6.94 +6.40 +6.29 +6.09 +4.72 | 7 (skill 4) | 0 | +4.91 | **success**, not killed |
| SPECK seeded (300 gens) | 3 | +1.36 +3.35 +4.38 | 2 (skill 4) | 0 | +3.35 | - |

- **S1 routing** (1024 fresh lives per body, seeds 23,000,000 + s; reflex@hollow3 +8.694 ± 0.084, router@ring4
  +10.964 ± 0.090): evolved F +2.66 to +7.06, all below the reflex by 1.6-6.0 (z -17 to -67), so no seed qualifies
  and the lateral-share test is moot. lateral_off for the whole life removes 7-107% of F (s2 7%; s5 63%, s6 107%, s7
  86%, s8 65%, s9 78%).
- **v1 L2 against v1 L4:** one L2 seed of 3 grew (+3.10, the best v1 body) against 4 of 10 at L4. Too few seeds to say
  whether hidden planes cost or help; part 4 finds them inert in the bodies that have them.
- **GB11:** in SPECK L4, s4-s8 reach their final size by T/2 and stop (share growing 0.00-0.02); s0-s3 and s9 still
  grow (share 1.00; s9 103 cells at T/2, 180 at T). The seeded arms all keep growing (speck seeded s0 reaches 322).
- **Slit check:** no evolved body gains more than 0.1 F from a slit (largest estimated gain +0.030 mean, +0.096 for one
  life of v1 s8; an enclosure in 5 of 736 lives), so the closing law is not revisited.

### 2. Selection dynamics (`analysis.md`, "Selection dynamics")
- Unfrozen runs keep about 27 of 224 children per generation and reach one breed (all parents descended from one
  founder) within 2-119 generations. Runs stuck at 1-2 cells freeze for long stretches (up to 256 generations).
- Inside the recheck shortlist, Spearman(F_base, F_recheck) has a median between -0.04 and +0.10 in every growing
  run. The compute audit (part 5) traces this to capture-count noise: each capture is 0.49 F in SPECK and a life has
  about 19, so a single life's F has an SD of about 2.0 (about 0.6 in v1). Common random numbers are already in place
  (every genome of a generation and its recheck share the life seeds and T).

### 3. Diagnostics: knockouts and faster conduction (256 paired lives each)
Genome knockouts set a knob to its neutral value (or zero an input's weights) for the whole life, development
included, so they mix behaviour and growth (cells at the end are reported with each dF).
- **The occupied-neighbour input (n_view) stops growth:** without it 14 of the 15 unseeded grown bodies grow to the
  1,024-cell guard (dF -16.5 to -28.0) and SPECK s6 stops at 287 (-9.4). Contact inhibition evolved in every lineage
  that grew without a seed.
- **The plane cues are developmental:** without is_S and is_M most bodies shrink to 1-41 cells (three keep 66-132),
  at dF -1.4 to -9.1.
- **Division geometry** (asym, zeta) runs away in many bodies; the seeded arms, which descend from hand-built genomes
  with many readout rows exactly zero, show 0.00 for every knob they do not use.
- **No body uses apoptosis** (p_die knockout 0.00 everywhere). delta and tau_tr are unused (|dF| <= 0.25); chi and phi
  matter in two bodies only (v1 L2 s2 chi -1.97; SPECK s8 chi -0.97, phi -1.40).
- **Chemistry is load-bearing in the best SPECK bodies** (secretion, polarity or anisotropy gain: -7 to -11 in s5-s7).
- **Channel 1:** removing emission on it costs -11.7 in SPECK s5, -7.0 in s9, -6.3 in s8 and -3.1 to -3.7 in s1 and s3,
  and nothing in s0, s2, s4, s6 and s7 (s2 and s4 send on one channel per plane; part 4).
- **Faster conduction** (d0 0.5, d_min 0.25) helps every body: the router +1.99, the reflex +0.99, evolved bodies +0.14
  to +1.70 (s6 +1.70, the most lateral-dependent body).
### 4. How the evolved bodies work (post hoc, exploratory; `src/life/probe.py`, docs/PROBE.md)
Not pre-registered. A probe toolkit traces single lives in the pure-Python reference (every trace's F equals the
kernel's bitwise), follows each act spike back through the spikes that caused it, and lesions messages per cell,
channel or direction after development (a reference lateral lesion equals the kernel's `lateral_off` fork bitwise;
`tests/test_probe.py`). It was validated on the two hand-built SPECK bodies: in reflex@hollow3 every receptor-started
rim-motor chain starts in the motor's own column (0 of 7,421 relayed); in router@ring4 38.5% start in another column
and reach the rim through in-plane hops, with latency quantised at about d0 per hop. Four evolved bodies were then
taken apart, one agent each, and a second agent tried to refute each account on fresh lives (seeds 31.0M-31.35M,
disjoint from every pre-registered range). Verdicts: s4 confirmed; s5, s2 and v1 s5 partly (the refuted sub-claims
are dropped below).

**Every body regrew the column reflex.** A sense cell's spike fires the act cell directly above it about 1.0 later
(one hop; 89% of motor spikes in s5, 99.9% in s4); rim act cells pull outward along their open face, so the side of
the body under the target drags the dot toward it; the centre sense cell drives the hotspot, which clicks. Hidden
cells are inert in all four (hidden_off after development changes F by at most +0.04 ± 0.16 where measured; in s4
they never fire).

**Directional wiring from chemistry (all four).** The genome has one weight per channel, the same for every input
slot. Every body instead reads direction from a standing morphogen gradient: the receiver scales each channel by
`1 + a_c ŝ` (LIFE_ABI.md 8), where ŝ is the neighbour-minus-self morphogen difference, so one spike's weight depends
on where it comes from. Going up it excites (about +0.9 to +3.4); coming down it inhibits or nearly vanishes (-0.1 to
-1.9); in-plane it ranges from near-cancellation (+0.3 in s5) to directed relays (s4's fringe +1.6 to +1.9 inward and
about 0 outward; s2's act plane 0.33 outward, 0.15 inward). In v1 s5, swapping the planes' secretion flips the
vertical signs and wrecks the score. s5 and v1 s5 emit every spike on both
channels (ch0 excitatory, ch1 inhibitory), which is why s5's emit1 knockout costs -11.7 F (part 3); s4 and s2 use one
channel per plane.

**On top of the reflex, three lineages evolved distinct local computations:**
- **SPECK s4 (+5.1): neighbour voting, an antenna fringe and a latch** (confirmed). A sensor is a leaky integrator
  (rest about -1.7, threshold 1): an own receptor event adds +2, a neighbour sensor's spike about +1.1, so it fires on
  two own events (about 1.0), one own event plus one neighbour spike (0.82-0.87) or 3-4 neighbour spikes (0.38-0.82),
  and almost never on one event alone (0.04). Sensors under one target confirm each other; isolated background events
  die. Act cells only bud straight up, so the sense disk outgrows the motor disk, and its roughly 20 motor-less fringe
  sensors excite inward (+1.6 to +1.9) and barely outward: an antenna for targets beyond the motor footprint. After a
  spike a sensor restarts at v = 0, above its rest, so for about 1.8 units one event re-fires it (worth 0.9-1.4 F).
  Lateral messages carry about 55% of F after development, all of it as capture reward; scrambling where the lateral
  drive lands (same amount and timing) gives -4.15 ± 0.39, worse than no lateral messages; no uniform excitability
  shift recovers more than +0.64 of the 3.3 loss.
- **SPECK s5 (+6.8): cooperative detection plus feedback inhibition** (partly confirmed). Sensors need two own events
  within about 4.6-5.5 units, or one event plus neighbour spikes. Weak lateral excitation (+0.3) primes sensors 1.5-3
  units outside the halo, so when the target passes over the body's interior the rim motors on its side keep pulling
  (approach speed at 1-3 units doubles). lateral_off after development costs -4.3 to -4.9, all reward; seven uniform
  gain substitutes recover none of it. About 1 unit after a twitch the act cell inhibits its own sensor; interior act
  cells, which cannot pull, serve as the sense sheet's inhibitory interneurons. Removing the downward feedback costs
  more (-5.6) than removing lateral messages (-4.7): without it the excitable sense sheet runs away, off-target spikes
  triple and pull aim collapses. s5 scores below the hand reflex because of cost (122 cells, 15 inert hidden, about 18
  interior act cells), not skill.
- **SPECK s2 (+4.4): gain set by crowding** (partly confirmed). The sense plane is a 1-bit retina. Each act cell's GRN
  reads its contact count and sets its gain: few contacts (the rim, which can pull) relay every spike; crowded cells
  need two inputs within about 2 units and pass activity outward (lateral 0.33 out, 0.15 in). This is causal and
  adapts in life: when a neighbour dies the cells around it drift to high gain over tens to about 100 units, not if
  their n_view input is held fixed. The outward relay pays only above about 70-75 cells (-1.50 ± 0.54 when removed at
  91 cells) and costs below about 60, so a body that keeps growing crosses from one sign to the other in its life.
- **v1 L4 s5 (+2.8)** is the hand reflex regrown, plus a centre sensor that needs about 2 events within 1 unit before
  it clicks (a single-event centre adds about 28 misses per life). Lateral messages are worth about 0.3 F; a plain
  column reflex was not ruled out for its steering sensors.

**Not seen in any body:** use of the hidden planes; a one-hop OR relay like the hand router's (s4 and s5 recruit
softly); channel codes beyond excitatory/inhibitory; apoptosis (part 3: p_die knockouts are 0 everywhere).
Every account is in `results/catch_pilot/mechanisms.json` (interpretation and verification per body).

### 5. Compute audit (workflow `compute-efficiency-audit`, `compute_audit.json`)
Four measurements, each re-checked by an independent skeptic. Taken on the loaded laptop (an Intel Core Ultra 7 255U,
mostly efficiency cores), so absolute times are pessimistic.
- **Per life:** 0.07-0.15 CPU-s at T 1024 for 85-145-cell bodies, about 1.2-1.5 µs per cell-time unit, linear in
  cell-time. A generation is about 1,070 lives (256 x 3 selection, 64 x 4 recheck, about 5% side rounds), so about 175
  CPU-s at 126 cells and about 24 CPU-h per 500 generations. Python is 0.2-0.4% of a generation; the population call
  is 72%, the recheck 23.5%, the side rounds 4%.
- **Where kernel time goes:** the scheduler handles about twice the ledger's `events`: receptor candidates are 43-60%
  of heap events, and only about 4% of them are accepted in SPECK. A fit gives CPU ≈ 187 ns per heap event + 1.9 µs
  per GRN tick. A sampling profile (single measurement, not re-checked) puts the event queue at 14-16%, readout and
  decode 12-13%, chemistry 9-11%, GRN 9-10%, hash folding about 10% and libm 19% of CPU: about half model arithmetic,
  half bookkeeping for exactness and verification.
- **Exact speedups (outputs bitwise unchanged):** a "fast" kernel mode without hash folds and per-packet records,
  1.24x (ledger identical in 62/62 lives; evolution never reads the hashes), and with a sparse readout and
  `-march=x86-64-v3`, 1.35x. Hazard: in fast mode every hash stays at its initial value, so the gates and golden tests,
  which compare hashes, must keep the full build. Threads do not contend, and results do not depend on thread count,
  batch composition or order, so any job layout is exact: fewer jobs with more threads, the longest arms first, and
  per-call thread counts that grow when runs finish (the pilot's last 2.5 h or more ran one 3-thread job).
- **Not exact but cheap:** capping founder lives at n_max 256 cuts the founder phase 4-5x (5.6% of the pilot) and kept
  the same top 8 in both batches tested; clone forks every 50 generations instead of 10 save about 3%.
- **Selection schemes:** the recheck is worth its lives (dropping it saves 1.33x lives but loses about as much
  progress per generation); schemes like 2 lives plus 5 for the top 64 may give 1.1-1.2x, but the model behind those
  numbers overpredicts real progress 10-30x, so they need an A/B. A denser score (distance or time near the target,
  already in the ledger) could cut the lives needed several-fold but changes the objective.
- **Renting:** GPUs do not fit (a generation is about 1,000 branchy lives, about 30 warps). Many-core CPU instances do,
  at 2026-10-09 prices: AWS c7a.48xlarge (192 cores, no SMT) $9.85/h on demand, $3.40 spot; c8a.48xlarge $10.35 /
  $5.53; hpc7a $7.20; GCP c3d-highcpu-360 $13.45 / $3.43; Modal $0.047 per core-hour. A pilot this size would take
  about 1-1.5 h on one 192-core box ($6-16) and a 40-run x 1000-generation ablation about 5 h ($25-30 spot); a server
  core's speed against this laptop is estimated (2-2.6x), not measured.
- **Before renting:** results are bitwise portable only with the same libm path (glibc picks an FMA or non-FMA path at
  run time) and the same torch CPU kernels (`torch.randn`, used for mutation noise, differs between ATEN CPU
  capabilities): pin the image (Ubuntu 24.04, glibc 2.39), set `ATEN_CPU_CAPABILITY=avx2`, use AVX2+FMA hosts and
  replay a fixed set of lives first. `src/run.py` cannot resume a run, so spot capacity would lose whole runs until
  checkpointing exists.

## 2026-10-09 — After the pilot: design review and the atlas
**Design review** (workflow `post-pilot-design-review`: four lenses with their own experiments, three critics, a
synthesis; `docs/POST_PILOT_CALLS.md`, every assessment and critique in `results/catch_pilot/design_review.json`).
New lives came from seed bases 36.1M-36.6M. Main findings beyond the pilot section:
- **The routing gap is earnings per cell, not catching skill.** s5 earns 9.65 per unit time against the tuned reflex's
  9.95 with about twice the cells, and capping its size lowers F, so its algorithm needs those cells.
- **A harness bug froze four v1 runs for 244-364 generations:** on exact ties parents always win (stable sorts with
  parents first, `src/evolve.py`), which switches off neutral drift exactly where drift is the only way out.
- **F tracks developmental speed** (cells at t = 64; rank correlation about 0.95 across the 10 SPECK bests), not final
  size; only s3 and s9 are measurably overgrown (+0.42 and +0.53 F available from stopping).
- **Direction-specific synapses exist only through morphogen chemistry,** which costs s5 about 10% of its running
  cost, couples synapse sign to division placement and breaks when the gene clock slows (s5 -10.25 F at 4x; traced
  to a tick-phase artefact in the gradient comparison).
- **Hidden planes have no job in a reactive world:** regrowing the same genomes at L_max 2 gains +0.32 F on average.
- **A shaped score is rejected:** distance and time-near-target predict F on other lives at r 0.09 against 0.17-0.19
  for F itself, yet are 10-17x more heritable per life, so selection would breed parking near targets.
Calls, in order (details and gates in the doc): random tie-breaking; checkpoint/resume with determinism pinning; exact
kernel speedups; report-only readouts; a niche map of worlds; then faster conduction (d0 0.5) behind a re-tune gate, an
ABI-4 cleanup bundle (per-time gene and fate laws, like-with-like gradient, gene split at ACK, drop tau_tr), gene
duplication on, and per-channel face weights (needs the user's approval); then Pilot 2 (three diagnostics, then a
20-seed matrix).

**Atlas** (`results/atlas/`, published as the "Spiking Tissue Atlas" artifact): the 2026-10-06 task-ladder specimens
plus, as part 1, the BODY-1 bodies. `extract.py` traces one life per body (the life with F nearest the median of 24,
seeds from 38,000,000; every trace's F equals the kernel's) and the pilot's evolution curves; `build2.py` assembles
`atlas.html` from `template2.html`.

## 2026-10-09 — Hardware path study
`docs/HARDWARE_PATH.md` (workflow `hardware-path-study`; records in `results/hardware_study/`). Four studies, each
re-checked by a skeptic; seeds 37.1M-37.8M.
- **For evolution throughput, custom hardware does not pay at this scale.** A pilot costs $6-16 on one rented 192-core
  box. A bit-exact float64 FPGA port would be worse per dollar (exp/log cores are 1 ULP, not glibc); an integer FPGA
  design is estimated at 0.8-2x the cost-efficiency of an integer CPU kernel for 4-12 person-months. Neuromorphic chips
  give no throughput gain and are not rentable by the hour. A time-stepped GPU port could be 2-9x cheaper per unit of
  work but puts a lockstep clock into the model, and the dt that leaves behaviour unchanged is unmeasured.
- **Fixed point is fitness-neutral.** Emulated integer arithmetic (12-16-bit genes and morphogens, table sigmoid and
  exp2/log2, 1/256 time grid) moved F by -0.012 ± 0.020 over the 11 pilot bests (1,024 paired lives each); final sizes
  shift by up to about 4 cells. Precision traps: gene state needs >= 10 fractional bits (Q8 cost s5 6.7%), twitch >= 8.
- **Exact parallel execution already works:** the ABI's window scheduler (each site advances alone, a fence every
  h <= d_min) was bitwise equal to the heap kernel in 528 of 528 life comparisons, so a processor array can replay
  lives exactly. The d_min rule is what makes this possible.
- **Recommendation:** make an integer ABI the next reference contract (folded into ABI 4): CPU speed (about 1.4-2.3x
  with fast mode, estimated), bitwise portability across machines, and the exact reference any FPGA or chip must
  match; then one cell processor, then a small spatial array; silicon only after the ABI is frozen.

**Playground** (2026-10-09, `results/atlas/play/`, published in the atlas): `lifesim.js` is a JavaScript transcription
of `src/life/reference.py` for CATCH bodies (GRN and program mode), with ports of glibc 2.39's FMA exp, log, sin, cos
and tanh. On 8 bodies x 32 fresh lives (seeds from 39,200,000) it equals the kernel bitwise in every life (F, all 57
ledger columns, the five hashes, rasters); the lateral_off fork at t 256 matches too (64/64). On top it adds an
interactive world: up to 6 user-placed targets whose halos add, drag and remove, drift on or off, and any cell-side
flag at any time. A target placed 3 units from a grown s5 is caught in 40/40 trials (median 12 time units; 0/40 with
receptors off). `export_bodies.py` regenerates `bodies.json` and the ground truth the node tests read
(`test_lifesim.js`, `test_playground.js`); `build_playground.py` inserts the playground into `atlas.html` as
`atlas_play.html`.

## 2026-10-09 — Alternative substrates and the roadmap
`docs/ALTERNATIVES.md` (workflow `alternative-paradigms`; record in `results/alternatives_study/`): five literature
passes and four judges under two user clarifications (the organism's rollout must be hardware-native, the training
loop may use anything; rank by compute to visible outcomes). Recommended first build: "spike-bit tissue", where each
cell is a small shared logic circuit exchanging spike bits, taught by a gradient-trained neural cell with the same bit
interface, compiled to gates and refined by evolution with many paired lives in a bit-exact engine (about three
weeks, under $150), with side tests on the current kernel (STDP in place of the morphogen route for synapse
direction; evolution strategies against the GA). `docs/ROADMAP.md` lays out every direction, its cost to a first
visible result, the suggested order and the decisions needed; the atlas has a "Where this goes next" section.

## 2026-10-10 — Quick fixes: random tie-breaking, fast kernel build, elastic sweep threads
- **Random tie-breaking** (`src/evolve.py`: `rank_desc`, `evolve.random_ties`, default on). Exact fitness ties in
  selection and in both recheck stages are broken by a random permutation from a generator of their own (seed + 7,919,001),
  so a generation without ties ranks exactly as before; `evolve.random_ties: false` restores index order. Fixes the
  frozen plateaus where parents (listed first) always beat equal children (four v1 runs froze for 244-364 generations).
- **Fast kernel build** (`-DLIFE_FAST`; `build.run(..., fast=True)`; `life.fast_kernel: true` in `configs/life_catch.yaml`
  and so in SPECK): skips hash folds and per-packet records and exact-zero weights. Ledger, raster and fate log are
  bitwise the full build's on random genomes, hand-built GRN genomes, program bodies, forks (`tests/test_life_fast.py`)
  and on 288 of 288 pilot-body lives (6 bodies x 48 lives, T 1024); 1.21x faster there with logging on (the audit
  measured 1.24x without). The full build's preprocessed source is unchanged, so gates and goldens are untouched.
- **Elastic sweep threads** (`scripts/sweep.py --max-threads`, default 32): the sweep publishes jobs x threads /
  running, capped, and every life run's kernel calls read it, so a run left alone at the end takes over the freed cores
  (the pilot's last 2.5+ h ran one 3-thread job). Lives do not depend on the thread count. Child jobs also get
  `OMP_WAIT_POLICY=PASSIVE`.

## 2026-10-10 — Task-variation design: which advanced circuits have headroom
`docs/TASK_VARIATION_PLAN.md` (workflow `task-variation-design`; record and key scripts in `results/taskvar_study/`;
seeds 40.1M-40.8M). Hand-built positive controls were tested against the reflex re-tuned in each world, on fresh paired
lives:
- **Routing has headroom, but only in the right world.** A GRN-grown router beats the best reflex by +0.06 F in today's
  base SPECK, +0.55-0.60 with fast conduction (d0 0.5), and **+3.83 ± 0.14 in "POOL"** (sigma 0.4, lam_s 4, d0 0.5),
  where it also beats s5 by +2.85. POOL is the only world where evolved bodies already beat the reflex (s5 +1.16). A
  48-world niche map ranks POOL first in selection information per CPU-second.
- **Regeneration has headroom:** a hand-built regenerating GRN router (`capabilities/regen7.py`) beats its
  non-regenerating twin by +1.79 in wounded lives (existing `kill_t`/`kill_frac` keys) and costs nothing unwounded;
  evolved bodies do not regrow the hotspot or centre.
- **Memory, prediction, context switching and discrimination have no passing control yet** (blinking target, fast
  straight targets, motor flip, b2 decoys): every hand-built body lost to the re-tuned reflex or latched on false
  triggers.
- **Literature:** goals that alternate over generations and share subproblems built modular circuits (Kashtan & Alon
  2005, 2007); scoring a mixture of worlds at once gave little speedup.
Plan: five arms on today's organism (base, POOL, a family per life, Kashtan-style switching every E generations,
family plus wounds), 12 seeds x 500 generations, about $15-35 on one rented box, after about two weeks of engineering
(resume, the family harness, gates).

## 2026-10-10 — Open headroom: admit worlds by what the sense information pays, not by what we can build
`docs/TASK_VARIATION_PLAN.md` section 0; record in `results/open_headroom/`. The earlier plan admitted a world only if
a hand-built body beat the reflex there, which made our design skill the ceiling. The new measuring sticks are central
controllers that see only the body's own sense pings, its own actions and its clock, and act through its own act cells.
They are measurement tools only. A replay test shows the controller reads nothing but pings.
- **Base already pays far more than any body earns.** On 1,024 fresh lives, an information-matched controller on the
  reflex's 56 cells beats the best reflex by **+13.31 ± 0.14 F in base** (22.56 against 9.25) and **+13.22 ± 0.13 in
  POOL**.
  - With tissue-like handicaps (one ping per 0.5, three hops of latency) it keeps +9.2 / +9.6.
  - Evolved s5 / s7 score -1.3 / -1.9 in base; the hand program router scores +3.6.
  - What pays is active search from a belief built by path integration, pings and the absence of pings.
- **Switching (motor flip mid-life) is admitted.** In the honest 50/50 flip mix, a flip detector adds **+12.7 ± 0.5 F**
  over the same controller without it. False alarms cost -0.27, against -3.02 for the hand-built trigger.
- **Memory is admitted.**
  - In the flash world (target bright for 5 after each placement, then dim), acting while dim is worth **+24.6 ± 0.2**.
  - In renewal blink worlds, memory is a secondary +2-4 F on top of tracking.
- **Not measured yet:** prediction, discrimination and the mutant gradient test. They were cut for time and are queued
  before round 2.
- **Plan changes:** the admission rule replaces every hand-built gate.
  - The family now includes flip mix and flash.
  - New "beyond hand" success criteria: beat the best hand body on record; gain where no hand body does; the share of the
    information gap captured.
  - New E9: port flip, blink and flash into kernel, reference and JS as ABI 4.
  - Open-ended track after round 1: co-evolving prey.
- **Process note:** a reboot wiped `/tmp` mid-study. The harness was rebuilt from its agent's transcript, and long
  studies now run in `outputs/`.

## 2026-10-13 — E1: deterministic checkpoint and resume
- Life runs save the population, ids/breeds, slot origins and next ids, completed generation, mutation and tie RNG
  states, evaluation counters, diagnostics and durable log offsets every 25 generations and at a controlled stop/end.
  `src.run --resume` continues the saved search; `--stop-after` permits a bounded interruption without changing the
  total generation target or adding premature final diagnostics.
- Startup pins AVX2 torch dispatch, torch/NumPy/Python versions, mutation-noise bytes, libm binary and resolved
  implementations, both kernel binaries/build flags, and search sources. The existing ring-1 CATCH golden hash
  `ebb3ad6fcad2d938` must replay, and the fast/full ledgers must agree byte for byte.
- Validation: real CLI runs of **3 + resume + 3 = 6** in BELL (sex/random ties) and SPECK (asex/legacy ties), with
  rechecks, structural mutations, variable life lengths and nontrivial diagnostic schedules. Population/genome bytes,
  logs, both RNG states and final results match after wall times are stripped. Partial crash tails are removed only
  after every log prefix is verified; a completed checkpoint can repeat final scoring without repeating evolution.
- Limits: exact resume requires the original generation target and numerical/source pins. Old pilot populations lack
  saved RNG state and remain continuations, not exact resumes. Host migration and rented-compute replay are untested.
  These checks used tiny populations and short lives; no large study or rental was launched.
