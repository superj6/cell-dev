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
