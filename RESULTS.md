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

## 2026-10-13 — E6: paired readouts and search observations
- Added report-only `src/life/readouts.py`, `scripts/life_readouts.py` and usage/data contracts in `docs/PROBE.md`.
  Lateral lesions report both loss as a share of net F and loss as a share of the lead over the best reflex. Per-world
  comparisons retain paired leads against the reflex and s5. Ratio SEs retain covariance and never clip negative
  values or values above 100%; weak denominators cannot establish BH3 progress.
- Relay summaries reuse the existing largest-input chains and state their attribution limits. BH4 measures exact
  distance through an explicit ping-free time window, sampled capture-zone occupancy, and clicks per capture. The
  added probe observer records existing motion segments without inserting events or changing the life.
- Validation: 12 focused tests plus the existing probe tests; two-life short router/POOL and s5/base smoke reports
  under `outputs/e6_readouts/`. Traces remain kernel-checked. Guarded, capacity-failed, accounting-invalid and
  truncated traces are rejected, including direct relay-summary calls. No evolutionary claim follows from these
  small plumbing checks.
- **Still unmeasured:** BH3 on each evolved body's actual footprint. The API requires matched worlds, ordered fresh
  seeds and footprint/protocol identifiers; substituting published hollow3 scores or an evolved body's final shape
  would not satisfy that contract. Flip recovery and dim captures remain unavailable under ABI 3.

## 2026-10-13 — E5: browser wound parity
- Ported the existing ABI-3 KILL event to `lifesim.js` and rebuilt the embedded atlas. Wounds retain the kernel's
  event ordering, uid targeting and living/secretion accounting; they do not change organism rules or the ABI.
- Committed 33 short C/reference-checked truth lives: all eight bodies, partial/zero/full wounds, birth/end boundaries,
  shifted time origin, accounting opened at the wound, apoptosis_off, a coincident tick, turnover, regrowth and stale
  uid events. The final JS engine matches all ledger bytes, hashes, rasters and death times, both whole and stepped.
  The final extended JS suite also passes 64/64 standard lives and 18/18 interactive checks. Eight compact baseline
  lives make the default JS test command work from
  committed fixtures instead of requiring missing local truth files.
- The playground's wall-clock throughput assertion remains below its threshold on this host; 75/76 checks passed.
  A suspected regression prompted a smaller wound handler and a fixed-work comparison on fast CPU 0: baseline
  median 0.615 s, final engine 0.590 s, with identical 26,306 events, 1,525 spikes and 9 captures. Three interleaved
  fresh-process samples per engine, after warmup, support no slowdown in that bounded comparison, not a general
  speedup claim. Timing artifacts and logs are in `outputs/e5_wounds/`.

## 2026-10-13 — E7: pre-registration and bounded measurement validation
- Committed preparation under `results/taskvar/` and `scripts/taskvar_{gates,gradient,measure,replay}.py`. The gate
  checker follows plan 0.4: at least 512 fresh paired lives, an own-footprint information gap and matched capability
  ablation clearing 1 F and 3 SE, and do-less gains below one quarter of the gap. Larger matched footprints may
  supply the capability contrast. Missing evidence stays incomplete; no hand-built tissue win is required.
- Archived the interrupted prediction/discrimination controller sources and knobs with provenance. Corrected the
  measurement-only harness's unused decoy-epoch alias and verified ordinary tissue and null/inert world parity
  against ABI 3. Both full and ablated controllers passed **24/24 bitwise callback-stream replay comparisons** in
  two 64-unit lives per variant, including different hidden worlds; all closed-loop controls differed. Audits bind
  the controller, kernel, harness, adapter and config sources.
- Two-life, 32-unit capability smokes (seven candidates each) correctly report incomplete. A four-mutant/two-life
  base smoke checks the gradient pipeline, which preserves genomes/ops, pins numerical identity, saves each row,
  uses production extinction accounting and retains penalized guard mutants in the denominator. These are plumbing
  checks, not capability or mutant-gradient findings. Key evidence is in `results/taskvar/validation/`; working
  artifacts are in `outputs/taskvar_e7/`. The 27 targeted gate/style tests and repository lint pass.
- **Still pending:** full G0-G5 measurements, all-admitted-world gradients, fresh mutant confirmations/lesions,
  matched-footprint BH3, and approval-dependent selection/ABI work. The recovered prediction ablation removes the
  moving-target model broadly, so its named capability check remains incomplete. The pre-registration makes each
  dependency explicit and reserves disjoint seed blocks. No full study, evolution matrix or rental was launched.
- **Integration validation:** all 696 default (non-slow) Python tests pass, repository-wide ruff and diff checks
  are clean, and the final JS suite passes 64 standard lives, 33 wound truth lives and 18 interactive checks. The
  separate playground wall-clock speed assertion remains the host-dependent limitation noted in E5 above.

## 2026-10-13 — Nearby mutant gains in base and POOL
- **Question:** do ordinary random mutations offer useful steps from the evolved s5/s7 bodies, and do those steps
  need lateral spikes? Protocol committed before scoring in `d90665f`; evidence, raw scores, genomes, plots and
  reusable analysis are in `results/pool_mutants_20261013/`.
- **Design:** 64 mutants per parent, identical across base-fast and POOL, screened on 32 paired T1024 lives. Re-score
  the top four per parent/world on 512 fresh lives, freeze one winner, and confirm against its parent on another 512.
  Four-arm parent/winner × intact/lateral-off measurements use 256 further paired lives, a fork at 256 and full-life
  accounting. Blocks 80–83 are disjoint. This is a separately registered exploration, not full 256-by-64/all-world G2.

| Comparison | Winner genome row | Confirmed ΔF ± SE | Additional gain removed by lateral lesion ± SE |
|---|---:|---:|---:|
| s5 / base-fast | 38 | +0.846 ± 0.136 | +2.110 ± 0.211 |
| s5 / POOL | 38 | +0.638 ± 0.116 | +1.644 ± 0.160 |
| s7 / base-fast | 15 | +0.755 ± 0.129 | +1.400 ± 0.178 |
| s7 / POOL | 29 | +0.263 ± 0.092 | +0.273 ± 0.133 |

- **Three of four comparisons clear 3 SE and +0.5 F**, involving two successful unique genotypes. The same s5 mutant
  wins in both worlds. s7/POOL misses both confirmation thresholds; its lateral interaction also misses 3 SE. No
  candidate or sample-size extension followed that outcome.
- **The strong gains buy more captures despite higher costs.** For example, s5/base adds 2.270 ± 0.280 captures per
  life: +1.108 F income minus 0.262 F additional costs = +0.846 F. It ends with 14.36 more cells; s7/base adds 23.23.
  The paired accounting includes living, spiking, movement, messaging, division, secretion, missed-click and receptor
  costs, plus production guard/extinction charges. Size and allele changes alone do not identify the mechanism.
- **The gains depend on lateral spikes.** In the first three comparisons, blocking them after 256 reverses the
  mutant's advantage; the four-arm interaction exceeds 3 SE. Under ABI 3, the lesion suppresses creation of new
  in-plane spike messages after the fork; already emitted messages still arrive, and outgoing-message costs remain
  charged. Vertical spikes and chemical packets continue. The lesion can change later development, so it does not
  isolate an adult circuit or demonstrate a new routing algorithm. The selected mutations affect gene regulation
  and initial gene levels; the s5 winner changes a chemical-input coefficient and a local motor-plane-input coefficient.
  See the [lesion-semantics erratum](results/pool_mutants_20261013/ERRATA.md); the earlier archive's pinned files
  remain unchanged for reproducibility.
- **Exploratory selection-noise check:** splitting the independent s5 confirmation pairs into disjoint three-life
  batches ranks the winner no better than its parent in 30.0% of base batches and 31.8% of POOL batches. Actual search
  shortlists 64 of 256 on 3 lives, evaluates 4 more lives, then keeps 32 using the pooled 7-life mean. This readout is
  pairwise, not a tournament replay, and does not show that ranking noise caused earlier search outcomes.
- **Interpretation and next step:** useful nearby improvements exist in both tested worlds. Check the winners across
  the normal T=768/1024/1536 mixture before using them as continuation founders, then test a fixed second-generation
  mutant pool with ordinary and more precise scoring. The old parents evolved with slower conduction, so adaptation
  to the faster setting may explain part of these gains. Long-run accumulation, richer algorithms, functional hidden
  layers and matched-footprint information-gap shares remain unestablished. No hand-built-body win gates a world.
- **Validation and budget:** all 26,752 planned genome-lives completed; all eight jobs exited successfully. Monitored
  simulation CPU plus benchmark allowance was 5,185 s (1.44 CPU-hours), below the 2-hour cap, with at most four workers.
  The public archive reanalysis reproduced the entire summary and cross-world results exactly. Confirmation tooling
  passed 39 focused tests, including source/seed checks, frozen selection, guard/extinction accounting and atomic
  resume. No organism rule, ABI, world default or fitness price changed; no rented compute or evolution matrix ran.

## 2026-10-13 — Transfer persists; a second mutation cohort does not confirm another gain

- **Scope:** three preregistered follow-ups to the nearby-mutant study, using existing worlds, prices and ordinary
  mutations. Public scores, genomes, protocols, paired analysis and figures are in `results/followthrough_20261013/`.
  Outcomes never changed the chosen first-step genotypes, second-step founder, candidate count or scoring budget.
- **A: transfer of the unchanged first-step winners.** Each winner and its original parent share 256 fresh seeds
  at fast-conduction T768, T1024 and T1536, plus old-conduction T1024. The equal-duration effect averages the three
  differences within each seed before estimating SE; these are 256 paired clusters, not 768 independent lives.

| Fixed winner | Equal-duration ΔF ± SE | Old-conduction T1024 ΔF ± SE | Fast minus old T1024 gain ± SE |
|---|---:|---:|---:|
| s5 / base | +0.586 ± 0.167 | -0.132 ± 0.166 | +0.768 ± 0.241 |
| s5 / POOL | +0.953 ± 0.170 | +0.212 ± 0.136 | +0.721 ± 0.227 |
| s7 / base | +0.532 ± 0.160 | -0.011 ± 0.164 | +0.574 ± 0.245 |
| s7 / POOL | +0.440 ± 0.120 | +0.107 ± 0.113 | +0.316 ± 0.172 |

  All four duration averages exceed 3 SE; s7/POOL still misses the separate +0.5-F practical threshold. This does
  not mean every individual duration clears 3 SE. The old-conduction gains are unresolved. The fast-minus-old
  interaction clears 3 SE for the same s5 genotype in both worlds, supporting conduction-dependent expression of
  its advantage. Old-conduction POOL does not recreate the original base-world training distribution. Four
  comparisons involve three unique selected genotypes; they are not four independent discoveries.
- **B: no confirmed second accumulation step.** A fixed POOL/T1024 cohort contains 224 ordinary mutants of s5
  row38 and 32 copies of that founder in the selector. All 225 candidate rows share 28 lives; the actual production
  top64/keep32 ranking is replayed with either 3+4 or 12+16 lives, including all three random tie permutations.
  Both rules select the identical candidate row148. On 512 independent paired confirmation lives, its additional
  gain over row38 is **+0.064 ± 0.142 F**, while its total lead over original s5 is +1.012 ± 0.129 F. Higher-budget
  minus lower-budget choice is exactly zero because the genotype is identical. The first-step founder itself
  remains +0.948 ± 0.124 F above original s5 on these lives. This cohort does not demonstrate another useful step
  or a winner-quality advantage from more scoring. It is one fixed candidate pool, not a multi-generation run or
  a comparison at equal compute. The inconclusive second-step result was retained without extending the search.
- **C: one discovered allele already provides a useful intermediate.** Four fixed genotypes copy the original
  parent, evolved allele A alone (`W[1,16]`, first internal chemical input), allele B alone (`W[4,24]`, local
  motor-plane cue), or the exact observed pair AB. There is no allele tuning. Each world uses 512 fresh shared lives.

| World | A minus parent, F ± SE | B minus parent | AB minus parent | Interaction AB − A − B + parent |
|---|---:|---:|---:|---:|
| base-fast | +0.548 ± 0.138 | -0.143 ± 0.053 | +0.550 ± 0.140 | +0.145 ± 0.075 |
| POOL | +1.064 ± 0.115 | -0.009 ± 0.042 | +0.984 ± 0.112 | -0.071 ± 0.065 |

  A alone clears 3 SE and +0.5 F in both worlds. B's added effect on A is +0.001 ± 0.058 F in base and
  -0.080 ± 0.050 F in POOL; neither it nor the interaction clears 3 SE. The gain does not require both changes
  together on this evidence. Unresolved effects are not zero effects. These gene-regulation changes can alter
  development, so the experiment does not identify an adult circuit or a new routing algorithm.
- **Budget and evidence:** A used 8,192, B 7,836 and C 4,096 research genome-lives: **20,124 total**. B's identical
  choices share one confirmation evaluation, with both roles retained. Completed external monitors record
  **4,216.849317 CPU-seconds (1.17 CPU-hours)** across A/B and C; row timings alone total 4,196.367151 seconds.
  At most four research workers ran, within the registered two-hour A/B and half-hour C caps. Separate plumbing
  checks used 294 T32 lives; a smoke consumed reserved G2 seeds 51,100,000 and 51,100,001, which future G2 must omit.
  The new `watch.html` embeds the unchanged JS engine and exact parent/row38 genomes on fixed illustrative seed
  51,840,000. Four T32 C lives and four JS replays matched all 57 ledger columns and five hashes, costing a further
  6.72 CPU-seconds. These checks and user-driven animations are not research evidence or example selection.
- **Direction:** retain the demonstrated first step and test whether ordinary evolution can accumulate more.
  Two preregistered 16-generation sexual continuations from row38 are now running under a shared three-CPU-hour
  cap; final population rank0 from each will be compared with the unchanged founder and original s5 on fresh lives
  across all three durations. A separately preregistered lateral lesion with tissue held fixed is queued to separate
  some developmental effects from later message dependence. Neither has a result yet. No organism rule, ABI, world
  default or price changed, and no rental or large evolution matrix was launched.

## 2026-10-14 — Two ordinary continuations add confirmed gains

- **Design:** two fixed 16-generation sexual searches from the previously confirmed s5 row38 founder in fast POOL.
  Each starts with one exact founder and 31 ordinary mutants, uses production 32+224 / 3+4 selection and the normal
  T768/1024/1536 draws, and keeps no protected founder. Final population rank0 is frozen before confirmation;
  checkpoint/population identity is verified. The protocol was committed before launch in `aa79221`/`7462bbf`.
- **Fresh confirmation:** both endpoints, row38 and original s5 share 256 new seeds at all three durations. Effects
  average durations within each seed before estimating SE over 256 clusters; correlated durations are not treated
  as independent lives. All endpoints are retained, with no validation-best reselection.

| Search seed | Additional gain over row38, F ± SE | Total gain over original s5, F ± SE |
|---|---:|---:|
| 51089 | +0.633 ± 0.188 | +1.602 ± 0.173 |
| 51090 | +0.756 ± 0.202 | +1.726 ± 0.182 |

- Both primary contrasts clear 3 SE and +0.5 F. T768 alone is unresolved (+0.500 ± 0.223 and +0.680 ± 0.246);
  T1024 and T1536 each clear 3 SE. This confirms additional accumulation beyond the earlier single mutation
  cohort's unresolved second step. Two fixed exploratory replicates do not estimate general search reliability.
- **What pays:** additional capture income is +1.162 ± 0.187 and +1.947 ± 0.203 F, exceeding additional total costs
  of 0.529 ± 0.023 and 1.191 ± 0.026 F. Both bodies end about 47 cells larger than row38. The first gains captures
  while clicking less (−8.83 ± 0.50 clicks) and travelling less; the second captures more while clicking more
  (+12.97 ± 0.53) and travelling farther. These are duration-averaged paired descriptions, not circuit mechanisms.
- **Evidence and budget:** `results/continuation_20261013/` preserves the complete lineage, final checkpoints and
  populations, configurations and numerical pins, full confirmation ledgers, independent analyzer and figure.
  All 36,012 research lives finished in 10,013.037438 monitored CPU-seconds (2.78 CPU-hours), within the three-hour
  cap and four-worker limit. Search invalid/mismatch counts are zero; valid guarded mutants retain their normal
  penalty. Confirmation contains no guards or extinction. Fitness progress alone establishes no new algorithm,
  functional hidden layer or share of the available information at a matched footprint.
- **Watchable comparison:** `results/continuation_20261013/watch.html` embeds the four fixed genomes and unchanged
  JS engine, starts paused, and uses descriptive seed51,840,000 without choosing a favorable life. Either side is
  selectable; base-world playback is labeled a transfer illustration. Synthetic controls and exact data/engine
  hashes pass. At this entry, the eight-case T32 C/JS parity check was awaiting a free worker; its later pass
  is recorded below. No browser rendering check
  has been performed. Animations are illustrations, not research scoring.

## 2026-10-14 — The first gain retains added lateral dependence with tissue held fixed

- **Design:** fixed original s5 and row38, each under normal, freeze, lateral-off and combined interventions.
  All eight arms share 512 fresh block92 lives in fast POOL, T1536. Interventions start at768; all fitness and
  capture/cost comparisons use800..1536 after a fixed settling interval. This study was registered independently
  of the continuation outcomes. No intervention enters evolution.
- **Primary result:** the winner's additional lateral dependence under freeze is **+1.692 ± 0.178 F**, beyond
  3 SE. Its frozen gain over the parent is +0.944 ± 0.159 F; suppressing new lateral messages reverses that gain
  to −0.748 ± 0.090 F. The primary interaction is almost entirely capture income (+1.710 F), with −0.018 F from
  cost savings. Ordinary accounting and production guard/extinction penalties remain intact.
- Without freeze, gain is +0.988 ± 0.160 F and added lateral dependence is +2.498 ± 0.174 F. Gain lost under
  freeze is unresolved (+0.044 ± 0.204 F), while the reduction in lateral interaction is +0.805 ± 0.217 F.
  Unresolved does not mean zero. Both genotypes pass constant-tissue checks in all 512 frozen pairs: no measured
  births/deaths, equal end counts between their frozen arms, and integrated cell-time matching constant size.
- **Interpretation:** added message dependence persists after this intervention holds tissue fixed. Freeze also
  stops gene-regulatory/phenotype updates; the two genotypes keep their own different footprints and earlier
  dynamic state. This does not identify mature tissue, a new algorithm, or matched-footprint information use.
  The lateral lesion prevents new in-plane spike messages but retains their charge; previously emitted messages,
  vertical spikes and chemicals continue. The settling interval does not erase prior state.
- **Evidence and budget:** `results/frozen_20261013/` preserves all full ledgers, paired contrasts, structural
  checks, source/numerical pins and independent reanalysis. All 4,096 research lives finished without guards in
  1,216.191173 monitored CPU-seconds (0.34 CPU-hours), within the one-hour/two-worker cap. The separately archived
  16-life validation is excluded from scientific estimates. No organism rule, ABI, fitness price or world default
  changed. The next bounded studies measure existing decoy information and test the approved structural operators.

## 2026-10-14 — Decoy information pays at the reflex footprint

- **Design:** the unchanged recovered D2 controller and its matched ablation are external measuring tools only.
  Seven fixed candidates share 512 new T1024 lives in the existing harmful-decoy SPECK world (b2_amp1,
  b2_sigma1.2, b2_value−50, b2_p1, b2_mode1), with old conduction d0=1 / d_min=0.5 and unchanged prices.
  Full and ablated controllers use the same 56-cell hollow3 footprint as the frozen and retuned reflexes.
  The protocol and exact inputs were committed before scoring in `e380214`; there was no new tuning.
- **Information gap:** full controller minus the better whole reflex (retuned) is **+11.754 ± 0.170 F**;
  full minus the frozen reflex is +12.084 ± 0.173 F. The full controller scores 12.616 F versus 0.862 for the
  retuned reflex. Reference selection uses whole-candidate means, never a different reference per life.
- **Decoy-model contribution:** full minus ablated is **+9.902 ± 0.194 F**. The single existing model switch
  removes decoy belief, attribution of pings, steering avoidance and tap veto, while retaining ordinary target
  tracking. It measures this broad decoy-aware mechanism, not one classifier, tap rule or evolved algorithm.
- **Do-less check:** the best of three fixed smaller/quieter variants gains +0.966 ± 0.107 F, below one quarter
  of the information gap (2.938 F). All three descriptive plan-0.4 checks pass. This does not automatically
  admit the world into selection; the limited do-less set is not an exhaustive optimum.
- **What pays:** versus the retuned reflex, the controller adds 21.346 captures per life. The paired F gain
  decomposes into +10.423 capture income, +1.386 poison-cost savings, −0.008 missed-click savings and −0.046
  other-cost savings. Removing its decoy model loses +6.555 F capture income and +2.812 F poison-cost savings,
  plus +0.543 F missed-click savings, offset by −0.008 F other-cost savings.
- **Limits:** central computation is free, though cells, pings, virtual relay spikes and actions pay. Parameters
  were transferred from ring5 without tuning at hollow3. This establishes useful sense information at the tested
  footprint, conduction and duration, not local-tissue attainability or duration transfer. Both fixed-reflex
  contrasts are retained; uncertainty for outcome-selected references is conditional and descriptive.
- **Evidence and budget:** all 3,584 lives completed without invalid/guarded lives in 496.441665 monitored
  CPU-seconds, below the 1,800-second/two-worker cap. `results/discrimination_20261013/` preserves full ledgers,
  controller diagnostics, generated C/library, source/configuration receipts and independent analysis. All
  seven raw files round-trip byte for byte; all 57 ledger columns reconcile; 12 earlier bounded callback-replay
  checks still verify. Fourteen independent analysis/archive tests pass. These T64 audits do not prove universal
  long-duration parity. The preparation incorrectly called fast event hashes zero: the fast build retains its
  constant initializer. An erratum corrects that wording while preserving all pinned preparation bytes.
- **Next:** a bounded mutant diagnostic can test accessibility in this existing world without adding it to the
  selection family or requiring a hand-built tissue win. The structural-policy runs are already underway;
  fixed-tissue hidden-message measurements are being prepared independently of their outcome.
## 2026-10-14 — Duplication and deletion add no resolved advantage in two fixed searches

- **Design:** two 16-generation searches from s5 row38 use the existing silent-duplication/deletion policy
  (rates 0.02/0.01, split off), against the two completed ordinary D continuations. Initialization, run seeds,
  production selection, life-length draws, physics and prices match; structural draws then change the subsequent
  mutation paths. This compares whole search policies, including gene-count-scaled point mutation, not the isolated
  effect of a duplication event. The protocol was committed before launch in `e380214`.
- **Fresh confirmation:** all six fixed genotypes (original s5, row38, both D endpoints and both G endpoints)
  share 256 new block93 seeds at T768/1024/1536. Each contrast averages durations within a seed before estimating
  SE over 256 seed clusters. Both final population-rank0 endpoints are retained, without validation reselection.

| Search seed | Structural minus ordinary endpoint, F ± SE | Structural endpoint minus row38, F ± SE |
|---|---:|---:|
| 51089 | −0.252 ± 0.209 | +0.745 ± 0.189 |
| 51090 | +0.325 ± 0.193 | +1.197 ± 0.192 |

- Neither primary policy contrast clears 3 SE or +0.5 F. Both structural searches nevertheless improve over row38
  beyond both thresholds; total gains over original s5 are +1.477 ± 0.166 and +1.928 ± 0.179 F. Unresolved policy
  effects do not establish equivalence, and two fixed search replicates cannot estimate general superiority.
- **Accounting:** versus row38, capture income increases by +1.236 ± 0.192 and +2.175 ± 0.193 F, exceeding additional
  costs of 0.490 ± 0.027 and 0.979 ± 0.022. The second endpoint's unresolved advantage over its ordinary counterpart
  instead consists of almost unchanged capture income (−0.003 ± 0.192) plus 0.328 ± 0.030 F cost savings. This is
  ledger decomposition, not evidence of a new circuit or capability.
- **Structural history:** exact genetic replay records 73/37 and 71/45 duplication/deletion events across the two
  searches. Each fixed endpoint has9 active genes, compared with 8 in its ordinary counterpart. Each retains one
  active duplicated-origin gene: slot 14 / origin 56 and slot 9 / origin 21. Counts and ancestry alone do not establish
  use. The already registered J study will delete every eligible gene and independently confirm its effect;
  its rule was fixed before these endpoints were inspected.
- **Validation and evidence:** all 18 dedicated neutrality lives preserve full ledgers, event hashes, spikes and
  fate records bitwise, except the added gene's state column, which matches its source. Full crossover/mutation/
  duplication/deletion replay reconstructs every stored population and origin registry. Search invalid/mismatch
  counters are zero; ordinary guarded mutants keep their production penalty. Confirmation contains no guards or
  extinction. `results/structural_20261013/` preserves the endpoint/checkpoint/lineage evidence, all confirmation
  ledgers, independent analysis and figures. Root separately recomputed all six duration-mixture contrasts from
  the 18 hashed raw rows.
- **Budget:** all 37,548 research lives completed in 10,942.922121 worker CPU-seconds (3.04 CPU-hours), within the
  fixed 14,400-second/four-worker cap. The 18 neutrality lives and numerical startup replays are validation, with
  their CPU included. H's fixed-tissue hidden/lateral measurements and I's decoy mutant screen are now running;
  J's copied-gene interventions and K's descriptive traces remain queued. No organism rule, ABI, price or
  selection world changed.

## 2026-10-14 — One ordinary descendant gains useful hidden-cell messaging

- **Design:** fixed row38 and both ordinary D endpoints share 512 fresh block94 seeds in fast POOL, T1536.
  Four arms are normal, freeze, freeze+lateral_off and freeze+hidden_off. Interventions begin at 768; accounting
  uses 800..1536 after a fixed settling interval. Both endpoints and all contrasts were registered before scoring.
- **Primary result:** D51090's added hidden-message dependence over row38 is **+0.794 ± 0.207 F**, beyond 3 SE.
  Its own frozen hidden-message loss is +0.956 ± 0.172 F, compared with row38's unresolved +0.162 ± 0.109 F.
  D51089's added dependence is unresolved at −0.193 ± 0.190 F; its own loss is −0.031 ± 0.147 F. Both signs and
  both endpoints are retained. These are life-level uncertainties for fixed genomes, not estimates across searches.
- **What pays:** D51090's primary interaction consists of +0.783 ± 0.207 F capture income and
  +0.011 ± 0.006 F cost savings, with zero guard/extinction terms. Hidden sends can affect other planes indirectly;
  this identifies conditional message contribution, not the computation performed by the hidden cells.
- **Lateral dependence:** added loss relative to row38 is +2.842 ± 0.194 F for D51089 and +2.470 ± 0.202 F
  for D51090, both beyond 3 SE. Their own frozen lateral losses are +10.255 ± 0.152 and +9.883 ± 0.160 F.
- **Freeze matters differently:** D51089's normal/frozen gains over row38 are +0.972 ± 0.176 and
  +0.814 ± 0.180 F; the loss under freeze is unresolved. D51090's gains are +1.341 ± 0.173 and
  +0.427 ± 0.190 F; freeze removes +0.914 ± 0.214 F of its normal gain. Freeze stops GRN/phenotype updates
  as well as new division/death decisions, so this does not isolate development from ongoing regulation.
- **Intervention limits:** hidden_off prevents new spike sends from z≥2, while cells still receive, fire and pay
  their ordinary would-be charges. In-flight messages and chemicals continue. Frozen genotypes retain different
  bodies and earlier states. This establishes neither mature tissue, a new algorithm nor matched-footprint
  information use. The ordinary D endpoints here are distinct from the structural G endpoints in study J.
- **Validation and budget:** all 6,144 research lives completed in 2,674.948141 of 3,600 CPU-seconds. All
  three sets of 512 frozen triplets pass constant-cell checks; no guards, extinction or invalid flags occur.
  `results/hidden_20261014/` preserves all 12 raw rows, independent reconstruction of 57 ledger columns and 20
  paired contrast vectors, source/numerical pins, figures and a standalone public reanalysis. Root separately
  recomputed the six interaction contrasts from hashed raw ledgers. Thirty pure analysis tests pass.
- **Watchable validation:** `results/continuation_20261013/watch.html` now compares original s5, row38 and both
  descendants. Eight T32 C lives and eight JS replays match all 57 ledger columns and five event hashes bitwise,
  using 9.331079 of 15 validation CPU-seconds. Full animations use a fixed descriptive seed and are illustrations;
  this bounded check does not establish universal long-life parity or a browser-render test. L's independent
  second-lineage evolution study is queued; its offline analyzer has 33 independently checked pure tests.

## 2026-10-14 — Decoy-world mutant gains mainly reduce ordinary costs

- **Design:** reuse both entire original panels, each parent plus 64 ordinary mutants, without filtering by
  their earlier base/POOL scores. All 130 rows share 32 block95 screening lives in the existing harmful-decoy
  world, T1024, old conduction and unchanged prices. Four mutants per parent plus the parent receive 512
  block96 rescoring lives; both winners are fixed before either 512-life block97 confirmation begins.
- **Fresh gains:** s5 selects original row32 and improves by **+1.431 ± 0.096 F**; s7 selects row1 and improves
  by **+1.178 ± 0.102 F**. Both exceed 3 SE and 0.5 F. Their absolute mean fitness remains modest: s5 moves
  from −1.671 to −0.240 F, and s7 from −0.720 to +0.458 F. No negative outcome was discarded or extra candidate added.
- **Accounting:** s5's gain consists of +0.359 capture income, +0.016 poison-cost saving, +0.067 missed-click
  saving and +0.990 other-cost saving. For s7 these are +0.460, +0.158, +0.046 and +0.514 F. Captures rise by
  0.734 ± 0.184 and 0.941 ± 0.190 per life, but terminal cells fall by 38.525 ± 0.542 and 22.660 ± 0.343.
  Most of each net gain comes from lower costs; positive fitness alone does not establish target/decoy
  discrimination. No copied controller behavior enters these organisms.
- **Full panels:** 44/64 s5 and 20/64 s7 mutants have positive mean screening differences; only 2/64 and 1/64
  exceed 3 SE on those 32 lives. These are descriptive fixed-panel fractions, not general beneficial-mutation
  probabilities. Screening/rescoring effects are selected; fresh confirmation supplies the primary evidence.
- **Limits:** two backgrounds and 64 nearby mutations each do not establish long-term accumulation or general
  evolvability. The prior base/POOL diagnostics used fast conduction, so their comparison with this study is
  not a controlled world-only effect. This study changes neither world admission nor the selection family.
- **Evidence and budget:** all 11,328 research lives completed in 3,105.780628 of 3,600 CPU-seconds, with zero
  guards, extinction or invalid flags. The two T200 startup golden lives are separate validation inside the cap.
  `results/decoy_gradient_20261014/` preserves all 144 raw checkpoints, every screening row and mutation record,
  frozen selections, full ledgers, source/numerical pins and independent standalone reanalysis. All 291 public
  artifact hashes and both fresh paired estimates were separately checked by root. Thirty-five pure analysis
  tests pass. The prepared abnormal-stop supervisor was unused; no cap extension or scheduling exception occurred.

## 2026-10-14 — The two retained copied genes have zero measured single-knockout effects

- **Design:** J's eligibility and selection rules were registered before seeing the G endpoints. Each has one
  eligible active duplicated-origin gene: G51089 slot14/origin56 and G51090 slot9/origin21. Delete each using
  the existing whole-life operation; verify its runtime packing against a canonical active-bit mask. Intact
  and knockout genomes share 512 block98 screening lives and 512 fresh block99 confirmation lives in fast POOL,
  T1024. Both endpoints are retained, without an outcome-dependent exclusion.
- **Result:** both fresh intact-minus-knockout differences are **0.000000 ± 0.000000 F**. Every recorded ledger
  and scored column is byte-identical between the paired arms in both stages, not merely close in their means.
  No guards, extinction or invalid rows occur. This finding does not by itself rule out a role in another
  genetic background or prove general dispensability.
- **Interpretation:** active-gene count and recorded duplication ancestry do not establish functional use.
  Whole-life deletion also cannot isolate mature computation. The hidden-message result in ordinary D51090
  concerns a different endpoint and cannot be attributed to either copied gene tested here.
- **Evidence and budget:** all 4,096 research lives completed in 1,197.683334 of 7,200 CPU-seconds. Independent
  NumPy replay reconstructs every recorded genetic operation and final origin registry; it preserves checkpoint
  bytes and the original checkpoint-validation receipt without independently deserializing those checkpoints.
  `results/duplicate_use_20261014/` preserves all raw interventions, paired contrasts and ancestry evidence;
  public reanalysis passes and root verified all 179 artifact hashes. Two startup golden lives remain separate
  validation within the CPU cap. No organism rule or selection policy changed.

## 2026-10-14 — Fixed descendant traces show more lateral relay and different movement

- **Design:** K records the exact reference simulator for row38 and both D endpoints on four fixed block89
  seeds, T1536 fast POOL. All 12 traces are retained in seed-first order. Each is checked against a full C life;
  all 57 ledger columns match bitwise. Raw event tables round-trip before any geometric relabeling and reproduce
  the existing E6 search/relay readouts without simulation. These are normal growing lives, including the
  800..1536 subwindow, rather than H's frozen counterfactuals.
- **Descriptive relay:** among rim-actuator spike chains attributed to receptor events, the mean fraction with
  at least one lateral hop is 0.379 for row38, 0.802 for D51089 and 0.729 for D51090. Paired changes are
  +0.423 ± 0.021 and +0.350 ± 0.028 over the four lives. The fraction of all receptor-origin chains with at
  least two lateral hops changes by +0.299 ± 0.015 and +0.201 ± 0.019. These paths follow the largest input at
  each firing step and omit subthreshold integration; they are not complete causal explanations.
- **Descriptive movement:** distance during the preset silence intervals falls by 28.359 ± 3.113 and
  15.577 ± 7.228, while total distance changes by +0.625 ± 27.767 and +163.992 ± 36.147. Clicks per capture,
  averaged as per-life ratios, change by −0.466 ± 0.157 and +0.080 ± 0.217. Different growth, shapes and states
  remain. Silence movement does not demonstrate that silence is used as evidence; no significance test or
  new-algorithm claim is made from these four descriptive seeds.
- **Evidence and budget:** twelve reference lives plus twelve C validation lives used 786.219558 of 1,800
  CPU-seconds, with one simulation worker. Existing numerical startup validation is inside that cap.
  `results/traces_20261014/` preserves approximately 41 MB of lossless raw event tables, all readouts and source
  receipts. Its public reanalysis requires the pinned repository sources and is not a standalone package.
  Both s7 continuation runs have now started under L's registered four-worker/14,400-second cap.

## 2026-10-14 — Both ordinary s7 continuations earn further capture-driven gains

- **Design:** L starts from the original s7 POOL mutant winner, row29, whose original confirmation was weak.
  Two fixed seeds, 51891/51892, each initialize one exact founder and 31 ordinary point-mutated copies, then
  run the unchanged 32+224 sexual search for 16 generations with 3+4 scoring and T768/1024/1536 draws.
  Neither founder nor endpoint is selected using the intervening H/I/J/K results. Final population rank0
  from each complete search is fixed before either fresh confirmation; no validation-best reselection occurs.
- **Fresh gains:** on 256 shared block90 seeds, averaging the three duration differences within each seed,
  endpoints improve over row29 by **+0.900 ± 0.143** and **+1.072 ± 0.145 F**. Both exceed 3 SE and 0.5 F.
  Total gains over original s7 are **+1.267 ± 0.146** and **+1.439 ± 0.146 F**. All six separate duration
  effects over row29 also exceed 3 SE: +0.946/+0.882/+0.873 and +1.174/+1.075/+0.967 F at T768/1024/1536.
- **Accounting:** extra capture income is +1.279 ± 0.144 and +1.864 ± 0.148 F, exceeding additional costs
  of 0.378 ± 0.014 and 0.792 ± 0.017 F. Mean captures rise by 2.820 ± 0.310 and 4.081 ± 0.316 per life;
  terminal cells rise by 14.048 ± 0.543 and 25.221 ± 0.625. Both click and move more. These gains come from
  obtaining more task reward despite higher costs. Income uses each duration's own denominator before averaging.
- **Interpretation:** ordinary production search now has confirmed further gains in both original starting
  lineages, with two fixed searches from each nearby winner. This does not establish a new algorithm or general
  search reliability, and it does not make a controlled comparison between lineages. Different founders,
  mutations, duration draws and search costs remain. No message lesion has yet identified the s7 mechanisms.
- **Integrity and budget:** all 36,012 research lives completed in 7,695.470841 of 14,400 CPU-seconds. The
  prospective initial populations and every recorded genetic operation replay exactly. Each search retains
  eight active genes, with no duplication/deletion. Initial evaluation has 16/21 guarded lives with penalties
  retained; invalid/mismatch counts are zero. All 3,072 fresh confirmation lives have status zero. Startup
  golden checks are separate validation within the cap. `results/s7_continuation_20261014/` preserves 207
  artifacts, full checkpoints and lineage, every raw confirmation row, and exact public reanalysis. Root
  separately verified all artifact hashes/sizes and recomputed all four headline paired estimates.

## 2026-10-14 — Copied-gene follow-up finds no contribution in either source context

- **Pre-release amendment:** J's exactly zero copy-knockout effects motivated a source audit before any M
  measurement. G51089's copied slot14 has exactly zero outgoing regulatory and phenotype-readout columns,
  including after deletion of source slot5. Private gene state can differ, but other state updates, arithmetic
  order, event keys and physical charges cannot change. Its physical/fitness interaction is therefore zero
  analytically. The original 4,096-life preparation is preserved, and M was reduced to 2,048 lives/1,800 CPU-seconds.
- **Remaining experiment:** G51090's copy slot9/origin21 retains a possible binary emit1 output. A valid-state
  counterexample prevents a universal silence proof without showing that state is reachable. All four fixed
  arms—intact, copy knockout, source slot0 knockout, and double knockout—therefore share 512 fresh block100
  lives at T1024 in fast POOL, with unchanged prices and existing whole-life deletion operations.
- **Result:** the paired interaction, intact − copy knockout − source knockout + double knockout, is
  **0.000000 ± 0.000000 F**. Removing the source loses **7.277 ± 0.129 F** whether the copy remains or not.
  Intact/copy-knockout and source-knockout/double-knockout pairs match byte for byte in all 60 scored/ledger
  columns on every life. No guards, extinction or invalid rows occur.
- **Interpretation:** the G51090 copy has no measured contribution in either tested source context, extending
  J's intact-background null. This finite sample is not a universal silence proof. The source gene's large loss
  is a whole-life effect, which can include development and morphology. These results do not demonstrate
  functional duplication, a new algorithm or a structural-search advantage; they do not rule out duplication
  becoming useful in other evolutionary histories or conditions.
- **Evidence and budget:** all 2,048 research lives completed in 410.154069 of 1,800 cumulative CPU-seconds,
  with two workers. Two startup golden lives are separate validation inside the cap. Independent analysis
  verifies full recorded ancestry, source/copy mapping, canonical runtime packing, all raw ledgers and paired
  contrasts. Thirty-six pure analysis tests pass. `results/gene_interaction_20261014/` preserves 308 artifacts,
  both preparation versions, the analytical proof and all measurements. Root and an independent reviewer each
  checked every artifact hash/size and recomputed zero interaction and byte-identical copy effects.

## 2026-10-14 — The s7 continuation viewer preserves exact archived genomes

- **Display:** `results/s7_continuation_20261014/watch.html` starts paused with row29 beside endpoint51891.
  Both selectors include original s7, row29, and both fixed endpoints. POOL is the measured world; base is a
  transfer illustration. The unchanged JS engine embeds all four exact genomes, and the evidence panel uses
  the archived paired duration-mixture comparisons. The default descriptive seed remains 51,840,000.
- **Validation:** all eight T32 C cases match stepped JS execution and state reads bitwise in all 57 ledger
  columns and five event hashes. The single-worker check used 11.250013 of 15 CPU-seconds. These eight C lives
  and eight JS replays are validation only. Synthetic UI checks pass; a browser rendering check was not performed.
- **Provenance:** the viewer has a separate manifest under `viewer/`; all 207 sealed scientific artifacts and
  their original manifest remain unchanged. Full animations are illustrations, not fresh scientific evidence.

## 2026-10-14 — Information payoff persists at shorter and longer lifetimes

- **Design:** N measures unchanged default C4 and five fixed reflex references in the original fast base/POOL
  worlds at T768 and T1536. Each world/duration uses 512 paired seeds; block40 belongs to T768 and block41 to
  T1536. There is no retuning, endpoint selection or new controller behavior. C4 and both primary reflexes use
  the same 56-cell hollow3 footprint, with existing action charges and latency but free central computation.
- **Primary comparisons:** C4 minus the retained retuned reflex is **+13.257 ± 0.223 F** in base/T768,
  **+13.547 ± 0.204 F** in POOL/T768, **+13.112 ± 0.168 F** in base/T1536, and **+13.218 ± 0.151 F** in POOL/T1536.
  Its fixed comparisons against the original frozen reflex are +13.403 ± 0.223, +13.784 ± 0.205,
  +13.128 ± 0.166 and +13.335 ± 0.146 F respectively. Every comparison retains all 512 lives.
- **Do-less checks:** the retained retuned reflex has the higher whole-sample mean in all four conditions.
  The best of the three prescribed smaller/quieter variants gains −1.182 ± 0.127, −0.393 ± 0.116,
  −0.965 ± 0.095 and −0.358 ± 0.085 F in the same order. Every fixed variant scores worse than that reference.
  All descriptive >3 SE, >=1 F information-gap and quarter-gap checks pass. Best-reference/variant summaries
  reuse the scored sample and are conditional descriptive estimates; the fixed contrasts are primary.
- **Interpretation:** the existing sensory information remains valuable across both lifetime endpoints under
  the original fast physics. Different duration blocks do not support paired duration-change claims. This
  does not complete G5 across capability worlds, isolate a particular capability, show that an evolved local
  tissue can attain C4, or decide world admission. The external controller never enters an organism.
- **Validation and budget:** all 12,288 research lives and 40 T64 validation lives completed in 1,385.715510
  of 3,600 CPU-seconds. The 24 research rows have no guards, extinction or invalid status. Recorded-ping replay,
  controller-copy checks, scratch/production reflex parity and null/inert stream checks all pass; the two
  historical diagnostic columns and combined hash are excluded only from the documented scratch/production check.
  `results/information_duration_20261014/` preserves 244 artifacts, including all 71 preparation files, generated
  C/libraries, raw validation logs and research ledgers. Independent analysis passes 45 synthetic tests and
  standalone public reanalysis. Root separately checked all artifact hashes/sizes and the four raw paired effects.

## 2026-10-14 — Complete publication of manifest-listed evidence

- A Git-index audit found 19 locally preserved evidence files omitted from earlier commits because their
  nested directory names matched `outputs/` or `logs/` ignore rules. These are D/L search and confirmation
  logs, G's copied D logs, I's resource-dependency pins, and F's archived replay streams. Their exact original
  bytes are now committed; scientific manifests, measurements and conclusions are unchanged.
- The same check caught and repaired 24 namespace-audit inputs in Q's preparation before Q was released.
  Future archive checks must verify Git-index coverage in addition to local file hashes and sizes.

## 2026-10-14 — Fixed-tissue descendants depend more on local gene-network inputs

- **Design:** O fixes row38 and both D generation-16 rank-zero descendants, crossing each with structure held,
  structure held plus `genes_blind`, and full freeze. All nine arms share 512 fresh block101 seeds, fast POOL,
  T1536, fork at 768 and accounting over 800..1536. The mask zeros gene-network inputs 18–22: own and incoming spike
  traces, contact fraction and receptor trace. Neural receptors, spikes, morphogens and plane cues remain.
- **Primary result:** added input dependence over row38 is **+2.849 ± 0.175 F** for D51089 and
  **+2.940 ± 0.176 F** for D51090, both beyond 3 SE. Their structure-held gains over row38 are
  +0.851 ± 0.174 and +1.094 ± 0.173 F; with masked inputs those contrasts become −1.998 ± 0.037 and
  −1.845 ± 0.040 F. All descendants and effect signs are retained.
- **Own losses:** masking costs row38 +10.326 ± 0.135 F, D51089 +13.175 ± 0.155 and D51090 +13.265 ± 0.146.
  Full freeze costs much less relative to structure held: +0.111 ± 0.144, +0.290 ± 0.165 and +0.604 ± 0.180 F.
  Added structure-minus-freeze effects over row38 remain unresolved at 3 SE: +0.179 ± 0.219 and +0.493 ± 0.230.
- **Interpretation:** successful fixed tissues depend on the specified local gene-network inputs. This does not
  establish memory, learning or use of changing evidence: the mask also removes static contact information.
  Full freeze stops gene, phenotype and effective-weight updates together. Different genotypes retain different
  bodies and pre-fork states; this is not a matched-footprint information-share measurement.
- **Validation and resources:** all 4,608 research lives completed in 2,283.250535 of 3,600 CPU-seconds. All 1,536
  three-arm tissue checks pass; no guards, extinction, invalid status or post-open births/deaths occurred.
  Independent offline analysis checks the full raw ledgers and every paired contrast; root separately reproduced
  all 16 means and SEs directly from the nine raw rows. Evidence is in `results/regulation_20261014/`.

## 2026-10-14 — Saved traces suggest inhibitory hidden-to-act feedback

- An exploratory reanalysis of K's twelve completed traces finds predominantly negative hidden-to-act membrane
  inputs and positive act-to-hidden inputs. After t800, D51090 has 536–968 nonrefractory hidden-to-act arrivals
  per saved life, 95.7–100% negative. Row38 also has negative hidden-to-act inputs, with 119–362 arrivals.
- These are four descriptive lives per genotype, with different bodies and states. Events are not independent
  replicates. The signs are consistent with inhibitory feedback but do not explain H's causal hidden-message
  effect: these traces are normal growing lives, while H froze tissue. No new algorithm or memory claim follows.
- `results/trace_hidden_20261014/` publishes all 48 full-life/post800 descriptions and a portable NumPy-only
  analyzer. It reproduces the earlier independently reviewed rows exactly; a second review checks raw input
  hashes, mask semantics, zeros and public reanalysis. No new lives were simulated.

## 2026-10-14 — Rechecking often changes which parents survive

- The completed D/G/L search logs preserve all 6,144 shortlisted candidates across 96 generations in six
  searches. Adding four fresh recheck lives to the initial three replaces **1,120 of 3,072 parent slots (36.5%)**.
  In 76 generations, no initial maximum-score candidate remains among the recorded pooled maxima; the recorded
  survivor cutoff resolves every such comparison. There are no tie-only leader swaps or ambiguous comparisons.
- Rechecking consumes 25% of selection genome-lives. Its logged share of evaluation wall time is 25.2%; that is
  not a CPU estimate. Recheck-minus-initial means range from −1.739 to −0.979 F across searches, conditional on
  having passed the initial shortlist. These are not estimates of unconditional fitness noise.
- The records show that small samples change immediate selection. They do not establish that rechecking improves
  independent fitness, or that more scoring beats more generations at a fixed budget. Related candidates, shared
  life seeds, varying durations and adaptive generations prevent treating candidate rows as independent replicates.
- `results/selection_noise_20261014/` preserves every candidate, generation, run and duration breakdown, two
  independent reviews and 16 synthetic checks. Public reanalysis reproduces the tables exactly. No new lives
  or active-study outcome reads were used. This motivates a prospective comparison of scoring policies.

## 2026-10-14 — Cells alive at time 800 keep changing neural properties

- An analysis of K's twelve saved normal-growing traces fixes the cohort to cells alive at time 800, then counts
  logged quantized changes through 1536. The mean fraction changing a neural property is **96.78% for row38,
  98.21% for D51089 and 97.71% for D51090**. Fractions average four lives per genotype; cells are not independent
  replicates. Later births are counted separately and cannot inflate this cohort.
- The nine named neural properties include receive-weight parameters, bias, membrane/refractory constants,
  emission channels, delay and receptor gain. Bias and receptor gain often change; emission channels never
  switch after 800 in this cohort. Changes continue in the final time bin, and repeated reversals are retained.
- Every transition chain and all 20 terminal gridded properties agree exactly with the saved traces. Continuous
  asymmetry and secretion updates are unlogged; effective incoming weights are a separate local calculation.
  These observations establish ongoing updates, not their fitness value, maturity, learning or sensory adaptation.
  Normal growing traces also differ from the tissue-clamped mechanism studies.
- `results/phenotype_updates_20261014/` publishes per-life, property, age and time-bin counts, 11 synthetic tests,
  an independent raw-event recount of all twelve lives and a portable reanalysis. No additional lives were run.

## 2026-10-14 — Copied genes acquired connections during search, without demonstrated final use

- A completed-data reconstruction of both G searches finds 73 and 71 duplication events. Five and fourteen
  new origins survive their birth generation. Four and eleven origins later occur in offspring with nonzero
  coefficient paths to phenotype readouts; two and seven have such paths in retained genomes.
- G51089's final copy remains disconnected, as M proved. Earlier carriers of that same origin include twelve
  connected offspring, one retained. G51090's final copy reaches only emit1, agreeing with M. J/M's final-copy
  knockout effects remain zero; intermediate variants were not tested for fitness dependence.
- These paths show potential coupling, not reachable cell-property changes, positive selection, fitness use or
  expanded computation. Copies, carriers and related candidates are not independent trials; crossover can erase
  or combine paths. The final nulls do not imply that copied genes never acquired connections.
- `results/copy_connectivity_20261014/` preserves every carrier and mutation-opportunity record. Final populations
  and origins reproduce exactly. Independent packed-coefficient checks cover 8,194 genome observations and
  4,755 copy records, with 944 synthetic graphs plus seven semantic tests. No new lives were run.

## 2026-10-14 — Scoring-budget comparison prepared, held for wrap-up

- S is fully prepared and independently reviewed but **not released**. It would compare eight generations with
  6+8 scoring against P's sixteen generations with 3+4, using exactly matched initial populations and RNG states.
  Both policies spend 16,384 selection genome-lives per branch; duration exposure and actual CPU costs differ.
- All six fixed D/P/S roles would receive fresh block105 confirmation. The plan covers 37,484 research lives
  under a 14,400 CPU-second cap, with at most four simulation workers after R. It freezes both completed P
  references before either S search. No outcome-dependent founder or endpoint replacement is allowed.
- All 103 pure/mock preparation checks pass. `results/scoring_budget_20261014/` preserves the exact protocols,
  initialization/namespace audits and independent science/resource reviews. There is no readiness marker,
  resource record, reference freeze or simulation output. The user's wrap-up request puts this study on hold.

## 2026-10-14 — Wrap-up interpretation corrections

- The older plan's quarter-of-information claim and pilot −10%/+9% ratios mixed body footprints. They are now
  explicitly labeled historical unmatched-footprint comparisons, not BH3 measurements. The external controller
  still demonstrates substantial information payoff; evolved bodies' matched-footprint share remains unmeasured.
- The older plan's controller-ceiling language is also corrected: heuristic controllers demonstrate information
  payoff, not proven upper bounds on evolved performance. Its larger-footprint observation is limited to the
  measured examples.
- Historical running-status text is marked as superseded, and the README's simulator parity statement is bounded
  to retained validation cases. No scientific data, pinned study source or result changed. The standing user rule
  against hand-built admission gates remains in force; broader unanswered execution decisions remain open.

## 2026-10-14 — Consolidated review at the user's wrap-up request

The most convincing progress is repeated ordinary adaptation and useful local communication. We have not yet
identified a new message-passing algorithm or established memory, learning, functional genome expansion, or
a matched-footprint share of available information. The entries below distinguish fixed-genotype comparisons
from evolutionary replication. All reported ± values are paired standard errors, not standard deviations.

| Work | What was tried | What the completed evidence shows |
|---|---|---|
| E1 | Checkpoint/resume with source and numerical pins | Interrupted 3+3 generation runs reproduce uninterrupted 6-generation populations, logs and RNG states. Old pilots still lack exact resume state; host migration remains untested. |
| E5 | Existing wound events in the browser simulator | 33 wound truth lives, 64 standard lives and 18 interactive checks pass. A host throughput threshold remained unmet; a bounded fixed-work comparison found no slowdown. |
| E6/E7 | Paired readouts, mechanism measurements and information-payoff admission tooling | Tooling, source/replay checks and bounded measurements work; the full all-world G0–G5 program and matched-footprint BH3 remain incomplete. The integration suite passed 696 Python tests plus retained JS parity cases. |
| Nearby mutants | 64 ordinary mutants per original s5/s7 in base/POOL | Fresh gains are +0.846±0.136, +0.638±0.116, +0.755±0.129 and +0.263±0.092 F; the first three clear 3 SE and +0.5 F. Capture income and lateral dependence increase. |
| A: transfer | Keep the same winners; vary duration and conduction | All four fast-conduction duration-mixture gains clear 3 SE; old-conduction T1024 effects remain unresolved. |
| B: second cohort | One 224-mutant cohort with ordinary versus larger scoring budgets | Both policies choose the same winner. Its additional +0.064±0.142 F is unresolved; one larger-budget cohort did not establish improved selection. |
| C: allele effects | Test the two first-step mutations separately and together | The first allele alone gives +0.548±0.138 F in base and +1.064±0.115 in POOL. The second allele's added contribution and interaction remain unresolved. |
| D/L: ordinary continuation | Two 16-generation searches from each selected s5/s7 founder | Additional gains are +0.633±0.188/+0.756±0.202 F for s5 and +0.900±0.143/+1.072±0.145 for s7. All four are capture-funded, with higher costs and larger bodies. |
| E/H: fixed tissue and messages | Freeze later growth/computation; suppress lateral or hidden sends | Row38 keeps +0.944±0.159 F of gain after freeze and adds +1.692±0.178 F lateral dependence. D51090 adds +0.794±0.207 hidden dependence; D51089's hidden interaction is unresolved. |
| F/N: information payoff | Existing external controllers, reflexes and smaller/quieter controls | Decoy information gap +11.754±0.170 F; base/POOL gaps remain roughly +13 F at both T768/T1536. Controller computation is free and external. These results do not measure local attainability or evolved information share. |
| G: structural mutation | Add silent gene duplication/deletion in two matched searches | Differences from ordinary search are −0.252±0.209/+0.325±0.193 F: no resolved policy advantage. Both final genomes contain one copied-origin gene. |
| I: decoy mutants | Score the full original mutant panels in the existing decoy world | Winners gain +1.431±0.096/+1.178±0.102 F, mostly by reducing costs. This does not establish discrimination. |
| J/M: copied-gene use | Knock out each final copy, then remove its source as well | Final copy effects are exactly zero on the registered ledgers/lives. One copy is analytically disconnected; deleting the other copy's source loses +7.277±0.129 F with or without the copy. |
| K and completed-data audits | Saved event traces, late phenotype changes, ancestry and selection logs | More lateral relay hops, mostly inhibitory hidden-to-act inputs, and late neural-property changes are descriptive. Copied-gene connections occurred during search. Rechecking changes 36.5% of parent slots; none of these observations alone proves function or policy superiority. |
| O: regulatory inputs | Hold tissue composition fixed; mask five local gene-network inputs | Added losses are +2.849±0.175/+2.940±0.176 F. The mask includes static contact information, so this establishes specified input dependence rather than learning or use of changing evidence. |
| P: further ordinary step | Another 16 generations from both D endpoints | Both searches completed; fresh confirmation stopped at the fixed CPU cap. No confirmed additional gain or plateau result. |
| Q: second-lineage messages | Frozen hidden/lateral-message tests of both s7 descendants | Dependency guard stopped the study after P was incomplete; zero measurement lives, no scientific outcome. |
| R: continued local updates | Separate gene/phenotype updates from effective receive-weight refresh | Dependency guard stopped the study after Q; zero measurement lives. Chemical relaxation would remain a possible explanation of a future weight-refresh effect. |
| S: scoring allocation | Eight generations with 6+8 scoring versus P's sixteen with 3+4 | 103 preparation checks pass; held without readiness or a run. Its frozen prerequisites also require completed P/R, which the final statuses do not satisfy. |

The completed research studies through O total **204,652 research genome-lives** and **51,610.008 monitored
CPU-seconds (14.34 CPU-hours)**. K contributes twelve reference research lives; its twelve C validation lives
are separate. Monitor totals include study startup/validation overhead and the initial screen's conservatively
carried ten CPU-seconds. Separate engineering checks and viewer validation are outside that total. Incomplete P
adds 14,381.265501 CPU-seconds; Q/R add 24.393466 seconds of waiting/monitor overhead and no measurement lives.
The combined monitored total is **66,015.667 CPU-seconds (18.34 CPU-hours)**. The 204,652-life count covers
completed studies only, excluding P's incomplete allocation. All compute is local; no rental or paid compute was used.

The important limits are systematic. Four ordinary continuations come from two fixed selected founders; fresh
life-seed SE does not estimate general search reliability. Repeated mechanism studies of the same genotypes do
not create new evolutionary replicates. Three-SE flags are descriptive within registered comparisons, not a
project-wide multiple-testing guarantee. Different genotypes keep different bodies and histories. Freeze changes
gene and phenotype computation as well as growth. H lacks a combined hidden-plus-lateral arm, so its two lesions
cannot establish independent pathway contributions.

At wrap-up I recommended consolidating ordinary-search repeatability and explaining the evolved message
and regulatory mechanisms before expanding task or genome complexity. The user's subsequent objective
clarification below supersedes that sequencing recommendation. The base/POOL information payoff already
justifies that work. The held scoring-allocation design addresses a concrete uncertainty, but the noisy-selection
audit does not prejudge its answer. ABI 4, task-family rollout, population-responsive worlds and rented compute
remain separate decisions; no unanswered approval has been inferred. No further experiments are being added
during this wrap-up.

## 2026-10-14 — Research batch closed; final confirmation incomplete

- **P:** both registered 16-generation searches exited successfully. Fresh confirmation began, but the fixed
  monitor terminated it at 14,381.265501 of 14,400 CPU-seconds (`incomplete`, `cpu_budget_exhausted`).
  `results/next_step_20261014/` preserves the searches, checkpoints, partial raw confirmation, original
  preparation and exact exit receipts. The complete-only analyzer returns `incomplete` without confirmation
  or endpoint comparisons; the archive summary records no confirmation. No partial endpoint comparison,
  budget extension or rescue run was used.
- **Q/R:** dependency guards exited with `monitor_failed` / `ValueError` after P and Q stopped. Neither study
  started measurement or validation; their 14.165054 and 10.228412 CPU-seconds were waiting/monitor overhead.
  Separate `operational_status/` archives preserve terminal records, pinned release sources and host/session
  exit evidence without altering their original preparation or offline-analysis bundles.
- **Held work:** S remains prepared but unreleased, without readiness, reference freeze or simulation output.
  Its unchanged protocol requires completed P and R; their terminal statuses prevent execution as written.
  Any future recovery would require a new registered plan, not just release of the existing bundle.
  The proposed intermediate-copy knockout follow-up was not prepared or launched. All original research
  monitors, workers and their process groups have exited; no experiment remains active.
- **What to learn from the incomplete allocation:** search completion alone cannot establish further progress.
  Future cost estimates should use developed founders and reserve confirmation CPU before allocating search.
  This allocation failure provides no evidence for or against an evolutionary plateau. Q/R's absent results
  must not be treated as null biological effects. The full review above is the final evidence inventory.

## 2026-10-14 — Objective clarified: more sophisticated algorithms in richer environments

The user clarified: "my ultimate goal is to advance the sophistication of generated algorithms we are able to
make emerge, especially in more interesting environments".

This corrects the emphasis of my earlier consolidation recommendation. Future research should prioritize
conditions that reward richer evolved computation. Mechanism studies and independent search replicates support
that goal by helping choose the next challenge and verify the capability that emerged; they are not prerequisites
to exploring richer environments. Better fitness on the current task alone does not demonstrate increased
algorithmic sophistication, and larger genomes or bodies do not establish it either.

Candidate capabilities include retaining information after cues disappear, combining distributed or temporally
separated evidence, prediction, and context-dependent behavior. The task should reward successful behavior while
evolution discovers its implementation. World admission remains based on information payoff, without a
hand-built-body gate. Local asynchronous rules, existing approval boundaries and the closed-batch status are
unchanged. No experiment was prepared, released or restarted for this clarification.

## 2026-10-14 — Autonomous exploration resumed: decoy evolution prepared

At the user's request, work resumes toward more sophisticated evolved algorithms in richer environments.
Study U uses the existing harmful-decoy world, where an external information-matched instrument already
shows substantial payoff. Two four-generation ordinary searches start from the fixed I s5/s7 winners;
512 fresh shared lives then compare both descendants and founders under trained conditions, reversed glow
widths, and matched frozen-tissue conditions with and without new lateral messages.

The 16,460 research lives have a 7,200 local CPU-second cap, with at most half allocated to search and at
most four simulation workers. Six startup validation lives are separate and within the same cap. Preparation
simulates zero lives. The 24 measurement, 40 monitor and 19 independent synthetic analysis checks pass;
world/source identity, initialization replay and seed namespaces have independent reviews. No scientific
result exists yet. `results/decoy_evolution_20261014/` preserves the prospective protocol and evidence.

Useful discrimination remains a question: prior decoy gains mostly reduced costs, and width reversal alters
sensing geometry as well as useful cue association. The new study reports complete costs, captures and harmful
clicks alongside fitness. Frozen lateral effects do not alone identify an algorithm. V's separate existing
moving-target information preparation is under independent review. The old P/Q/R studies remain terminal and
S remains held; no unanswered approval boundary has been crossed.

## 2026-10-14 — Moving-target information measurement prepared

V will measure the unchanged external moving-target controller against fixed whole/smaller/quieter reflexes
and its broad model ablation on 512 fresh shared lives per candidate. All seven candidates use the existing
fast, persistent-target ABI 3 world at T1024; full-controller and whole-reflex footprints match at 56 cells.
The planned 3,584 research lives have a 3,600 CPU-second cap and two workers. U is currently running;
V remains unreleased until every U process/group has exited and root records resource clearance.

Four fixed calibration lives consumed 11.558130849 CPU-seconds, including compilation/startup, and that cost
carries into the total cap. All 57 calibration ledger columns and fitness reconcile independently; twelve
retained action replays match exactly. Twenty-five preparation tests and eleven independent lifecycle tests
pass. Review caught and fixed descendant cleanup and unsafe-resume handling before research release.
No controller parameter was changed and no calibration score is scientific evidence.

`results/prediction_information_20261014/` preserves source/library pins, replay records, calibration evidence,
namespace audit and independent review. Full minus ablated measures the broad moving-target model, including
tracking and action prediction; prediction-specific admission remains incomplete. This is an external
information instrument with free computation, not an evolved algorithm or evidence of local attainability.

## 2026-10-14 — Flash and irregular blink port approved; engineering begins

The user approved the limited ABI 4 visibility extension in `docs/ABI4_VISIBILITY_PROPOSAL.md`: flash gives a
brief strong cue after placement and then a weak cue; renewal blink alternates irregular bright/dark intervals
while the target keeps moving. Four world fields and one low-light capture readout are appended. Genome fields,
cell inputs, messages and local asynchronous update rules remain unchanged. Motor flip, large selection runs,
population-responsive worlds and paid compute are outside this approval.

Work begins in isolated `outputs/abi4_visibility_20261014/` while U confirmation and the queued V measurement
retain their existing source pins. Before the port, 32 intentionally repeated ABI 2/3 validation lives at T64
were archived with complete ledger/hash/raster/fate outputs in `outputs/abi4_visibility_validation_20261014/`.
They used 0.186 CPU-seconds. These are compatibility fixtures, not scientific evidence or hand-built-body gates.
No ABI 4 outcome or parity claim exists yet.

## 2026-10-14 — Decoy evolution: further economy and one cue-pattern specialization

U completed both ordinary four-generation searches and all 8,192 fresh confirmation lives. Relative to their
fixed I founders, final rank-zero gains in the trained world are **+0.959061 ± 0.096004** (s5) and
**+0.319289 ± 0.100348 F** (s7). Both clear three SE, but only s5 clears +0.5 F. Capture changes are unresolved
(+0.246094 ± 0.181965 and +0.109375 ± 0.189304 per life). Capture income explains +0.120163/+0.053406 F;
the remaining +0.838898/+0.265883 comes from cost savings. Terminal bodies shrink by 26.270/7.926 cells.

The s7 descendant makes **1.373047 ± 0.315032 fewer harmful clicks per life**. Its fitness difference changes
from +0.319289 in the trained world to −0.761024 ± 0.150367 when target and decoy glow widths are exchanged;
the paired interaction is **+1.080313 ± 0.177314 F**. This establishes dependence on that cue pattern but does
not identify a discrimination algorithm: width reversal changes the useful signal's spatial geometry too.
The s5 width interaction is unresolved (+0.149407 ± 0.156922). Added frozen-tissue lateral dependence is
unresolved in both descendants (−0.314812 ± 0.169383 / −0.228469 ± 0.155575); freeze also stops regulatory updates.

All 16,460 research lives plus six T200 startup validation lives used **2,919.475449 of 7,200 CPU-seconds**.
Every confirmation ledger passes independent accounting and frozen-tissue checks, with no guards or invalids.
Recorded genetic replay reproduces both final populations/origins; all search invalid/mismatch fields are zero.
The s7 initial-generation evaluation includes three guards with production penalties retained; retained summaries
do not recover every recheck guard count. All processes/groups exited. Full artifacts and independent reanalysis
are in `results/decoy_evolution_20261014/`, including the prospective preparation, raw outcomes and figure.
This is further adaptation from two fixed founders, mostly economy, without a new algorithm claim.

## 2026-10-14 — Moving-target information pays chiefly through additional captures

V completed all seven fixed candidates on 512 shared fresh T1024 lives in the existing fast persistent-target
world. The unchanged external controller beats the better whole reflex at its 56-cell footprint by
**+17.168891 ± 0.217671 F**; versus the frozen whole reflex it gains +17.258915 ± 0.218154. Broad motion-model
ablation loses **12.958032 ± 0.224547 F**. The best of the fixed smaller/quieter references gains only
+0.341977 ± 0.077174 over the better whole reflex. All comparisons use paired life-seed SE; best-reference
selection remains descriptive and conditional on this fixed set.

The full controller gains 34.486328 ± 0.446245 captures while making 4.816406 ± 0.554675 fewer clicks per life
than the better whole reflex. Capture income accounts for +16.839027 F, fewer misses +0.383816, and other costs
−0.053952. The broad ablation loses 26.033203 ± 0.461465 captures. These results establish substantial useful
information in this world. They do not isolate prediction: the ablation removes filtering, tracking,
propagation, tapping and steering together. Prediction-specific admission remains incomplete. The controller
is an external instrument with free central computation, not an evolved algorithm or a proven performance ceiling.

All **3,584 research lives** finished on the first attempt in **320.819621 of 3,600 CPU-seconds**, including
11.558131 calibration seconds. Readiness followed verified U process clearance; every V process/group has
now exited. Independent analysis reconciles all 57 ledger columns, source/library identity, seeds, checkpoint
coverage and CPU accounting; 47 synthetic analyzer tests pass. The earlier 12 exact action replays and bounded
T64 production parity remain the validation scope. `results/prediction_information_20261014/` preserves raw
rows, independent contrasts, complete terminal evidence and prospective preparation. No large run was launched.

## 2026-10-14 — Approved flash and irregular-blink worlds implemented and checked

ABI 4 appends four world fields and `low_light_captures` without changing genomes, cell inputs, messages or
local asynchronous rules. Flash weakens the target cue after each placement; renewal blink alternates irregular
bright/dark intervals while the target continues moving. Both presets retain SPECK prices and old conduction.
Callers opt in explicitly; ABI 2/3 defaults, ledger shapes and full-mode hashes remain compatible. Historical
checkpoint source/numerical pins are not relaxed. Trace and ledger tools support the new readout explicitly.

All **32 pre-port legacy execution fixtures** reproduce ledger/hash/raster/fate bytes. Sixteen T96 fixtures
match between C, Python and maintained JS for every ledger byte, all five full-mode hashes and retained spike
logs; C/Python also match full fate arrays. Six include low-light captures. Both worlds match across one/two
threads, heap/window scheduling and C full/fast physical outputs. Six checkpoint tests pass, including exact
3 + resume + 3 versus 6 searches in BELL, CATCH, flash and blink. These tiny searches are engineering validation.

The twelve-case T64 bridge to retained scratch visibility physics matches all 55 unchanged physical ledger
columns and complete spike/fate logs. Scratch dark captures map exactly to production column 57, with positive
flash/blink cases. New visibility records intentionally change world/all hashes across this bridge. A portable
replay pins its old source and checks raw ABI sizes before dispatch. Old unchecked controller harnesses must
not import the new kernel's array sizes while loading ABI 3 libraries.

The default regression suite covers **861 distinct tests** after targeted repairs: the initial non-checkpoint
run passed 850/855; missing isolated-environment linkage, uncommitted historical logs and line-length style
caused five failures. All 23 affected/related checks then pass; 127 slow tests were excluded. The unchanged
historical logs were published as `859ddc8`. Earlier exact receipts and the two final docstring-only wraps are
recorded rather than rewritten. `results/abi4_visibility_20261014/` preserves sources, truth, bridge outcomes,
test receipts and a hash verifier. This is engineering evidence, with no new information-payoff or evolved-memory
claim. Fresh payoff measurements and bounded evolution remain separate work; no large run or paid compute began.

## 2026-10-14 — Fresh flash/blink information study prepared

X fixes thirteen historical controller/reflex variants in each approved visibility world at T1024, on 512
fresh shared seeds. It will measure information payoff at the reflex's own 56-cell footprint, low-light captures,
and capture income versus economy. Neither its broad model ablation nor suppression of actions while believed
dark removes only memory. The older plan0.3 memory-admission wording is corrected while preserving its scores.

The fixed scope is 13,312 research lives plus 82 validation/calibration calls under 3,600 cumulative CPU-seconds,
including a 180-second validation allocation. Source isolation, exact raw ABI checks, monitor ownership,
callback/action replay instrumentation and independent raw accounting are prepared. Blocks113/116 are registered;
the duration extension is held. `results/visibility_information_20261014/` preserves prospective inputs and reviews.
No X scientific life or compilation has occurred at this milestone. Real compatibility checks must pass before
research; no large evolution run, new organism behavior or paid compute is released.

## 2026-10-14 — Flash/blink measurement stopped at initialization, without scientific outcomes

X's numerical-identity guard rejected its first fresh worker before compilation or any simulated life.
Preparation had imported Torch and recorded its bundled OpenMP library; the fresh validation worker checked
identity before importing Torch and loaded the system OpenMP library instead. The exact-equality check
correctly rejected those different runtimes. This was an initialization-order defect in the measurement
wrapper, not a world, controller or fitness result.

The terminal monitor consumed **0.716548 CPU-seconds**, cleared its worker group and reported incomplete.
No seed was simulated and no candidate outcome exists. The original sources, release marker, failure log
and budget remain preserved. X will not be reset or resumed. A separate X2 preparation will initialize
Torch consistently before recording/checking runtime identity, retain strict equality and the same scientific
matrix, and verify the actual fresh-process environment before release. Its proposed caps of 3,599 total and
179 validation CPU-seconds conservatively include X's failed startup within the original 3,600/180 allocations.

## 2026-10-14 — Corrected flash/blink initialization prepared as X2

X2 consistently imports Torch before recording/checking numerical-library identity. All 77 preparation tests
pass, including actual fresh worker startup, frozen-source-first startup, production-import-first startup
and rejection of a deliberately different OpenMP runtime. Exact equality remains required. The complete
world/candidate arrays, seeds, analysis and expected numerical identity are unchanged from X.

The separate preparation in `results/visibility_information_x2_20261014/` transfers the registered but
unconsumed blocks113/116 and binds X's terminal no-life evidence. Its 3,599/179 total/validation CPU-second
caps leave both attempts within the original 3,600/180 allocation. No X2 compilation or simulated life has
occurred at this milestone. This repairs measurement initialization and produces no scientific result.

## 2026-10-14 — Flash and blink pay for useful information, chiefly through extra captures

X2 completed all 13,312 research lives and 82 validation/calibration lives. At the same 56-cell footprint,
the unchanged external controller beats the better whole reflex (R1 in both worlds) by **+7.726926 ± 0.144557 F
in flash** and **+5.551957 ± 0.119805 F in irregular blink**. The fixed R0 comparisons are +7.780598 ± 0.143183
and +5.578772 ± 0.118970. Values are paired means ± SE across 512 fresh seeds; selecting the reference by
whole-sample mean makes that comparison descriptive. Both information-payoff and do-less-quarter checks pass.
None of the eight fixed do-less variants has a positive mean advantage over R1; the best (D6) differs by
−0.119854 ± 0.043303 in flash and −0.026815 ± 0.012284 in blink.

| Full controller minus R1 | Flash | Irregular blink |
|---|---:|---:|
| Extra captures per life | +16.957 ± 0.298 | +11.494 ± 0.249 |
| Extra low-light captures | +14.375 ± 0.279 | +3.197 ± 0.107 |
| Extra bright captures | +2.582 ± 0.081 | +8.297 ± 0.220 |
| Capture-income contribution to F | +8.279800 | +5.612373 |
| Combined cost-saving contribution to F | −0.552875 | −0.060417 |

The gains buy additional captures despite higher costs. About 84.8% of flash's extra captures occur while
dim, versus 27.8% of blink's extra captures while dark (ratios of paired means). These timing readouts do not
isolate memory. Removing the broad visibility model loses **2.085273 ± 0.160657 F in flash**, but only
**0.087616 ± 0.129221 in blink**, an unresolved effect. Suppressing actions while believed dark loses
10.660042 ± 0.140670 and 2.487956 ± 0.136208 respectively. Neither intervention removes only memory;
capability-specific admission and duration transfer remain incomplete. The controller has free central
computation and is an external instrument, not an evolved algorithm or a demonstrated local implementation.

The final independent audit required a separate analyzer correction: initial cells are excluded from the
kernel's birth counter, and wall/ordinary rejections and delivered/dropped arrivals are disjoint counts.
The frozen analyzer's assumptions were wrong. Its source and failed invocation remain preserved; the corrected
version changes those bookkeeping checks only. Two independent source reviews, all 82 actual validation
ledgers and 164 tests verify the correction before full outcome analysis. Prices, fitness, candidates,
contrasts and all 109 released source pins remain unchanged. No simulations were repeated.

X2 used **1,348.464197 CPU-seconds**, including 68.524434 for validation; together with X's failed startup,
total use is **1,349.180745 CPU-seconds**. Every process/group exited. Full raw records, both analyzers,
the explicit erratum and portable corrected reanalysis are in `results/visibility_information_x2_20261014/`.
The next bounded diagnostic will test ordinary mutations around the stronger D90/L92 evolved founders in
irregular blink, emphasizing capture gains versus economy. This is a Phase 0 accessibility measurement,
with no hand-built winning-body gate and no automatic memory-admission claim.

## 2026-10-14 — Ordinary mutation study registered in irregular blink

Y tests whether ordinary mutations around the stronger confirmed D90/L92 evolved founders can exploit the
approved blink environment. Each founder receives 64 mutants under the unchanged mutation policy. All mutants
and the parent share 32 screening lives; both selected mutant rows are frozen before mutant/parent comparisons
on 512 fresh paired lives. There is no intermediate rescore. Blocks117/118/119 and mutation RNG 53117/53118
are registered after the namespace review found no overlap with prior scientific seeds or reservations.

The fixed scope is **6,208 research plus ten validation lives**, with one two-thread worker and a **5,400
CPU-second cap**. Startup and screens are capped at 3,400, reserving 2,000 for confirmation and cleanup.
Eight ABI4 calibration lives must support the unchanged scope before screening; two retained numerical goldens
also count in startup. Guard/extinction penalties and all ordinary costs remain in fitness. The additional
low-light readout carries no reward. Exact growing founders, mutation operations, all raw ledger columns and
fresh paired comparisons will distinguish capture income from economy.

This is a bounded accessibility diagnostic motivated by X2's capture-driven information payoff. It does not
require a hand-built winning body, prescribe an organism algorithm, or claim memory from dark captures alone.
Both fixed panels reproduce exactly under genetic replay. All 44 preparation checks and 165 independent
analysis/accounting tests pass without simulation or compilation. The prospective record is preserved at
`results/visibility_gradient_20261014/`; no large selection matrix or paid compute is released.

## 2026-10-14 — One ordinary blink mutant catches more while travelling less

Y completed both full 64-mutant panels and fresh confirmation of their fixed selections. D90 row58 gains
**+0.445151 ± 0.077087 F** and **+0.888672 ± 0.156826 captures per life** relative to its exact founder.
Both exceed three paired SE. L92 row24's fitness and capture gains remain unresolved. Each comparison uses
512 fresh paired T1024 seeds, separate from the 32-life screens; both selected rows were frozen before either
confirmation. These SE describe the fixed selected genomes across world seeds, not independent search reliability.

| Selected mutant minus own founder | D90 row58 | L92 row24 |
|---|---:|---:|
| Fitness F | +0.445151 ± 0.077087 | +0.091042 ± 0.074829 |
| Captures per life | +0.888672 ± 0.156826 | +0.197266 ± 0.153978 |
| Dark captures per life | +0.134766 ± 0.060312 | +0.044922 ± 0.075211 |
| Bright captures per life | +0.753906 ± 0.149774 | +0.152344 ± 0.146720 |
| Capture-income contribution to F | +0.433922 ± 0.076575 | +0.096321 ± 0.075184 |
| Ordinary cost-saving contribution to F | +0.011229 ± 0.006844 | −0.005279 ± 0.004113 |

D90's gain is chiefly additional capture income. It makes **233.588 ± 39.972 fewer spikes** and travels
**35.402 ± 0.876 less distance** per life while catching more. Its terminal-cell difference is unresolved
(+0.244 ± 0.384); the bodies are not experimentally matched. Absolute capture means rise from 9.391 to 10.279,
and F from 0.093 to 0.538. Most additional captures occur while bright. Neither lineage has a dark-capture change
resolved at three SE, and dark captures alone would not identify memory. This is an ordinary mutation improving
performance in a richer environment, without identifying a new algorithm or explaining its mechanism.

All **6,208 research lives plus ten validation lives** finished in **1,768.464936 of 5,400 CPU-seconds**.
Startup/screens used 1,240.066735; confirmation/cleanup used 528.398201. All 6,216 raw ABI4 lives have zero status
flags, including all eight calibration lives; the two retained ABI3 numerical goldens separately match their
expected hashes. Both panels and all mutation operations replay exactly. Every experiment process/group exited.

The frozen analyzer initially stopped before scientific output because it required a session-ID field absent
from the monitor's persisted identity record. The separate corrected reader checks the actual process, parent,
group and start-time fields, retaining attempt/release/source/budget checks. Its change has independent source
reviews and five regressions using the actual receipts. Scientific accounting, prices, selection, comparisons
and all 62 released pins are unchanged. The original reader and failed invocation remain preserved; no lives
were repeated. Independent reanalysis reproduces the summary and all 150 paired arrays exactly.

`results/visibility_gradient_20261014/` contains the prospective record, raw outcomes, explicit correction,
portable reanalysis and confirmation figure. A short four-generation native blink continuation is being prepared
from both fixed selected mutants, regardless of confirmation sign, to test whether further gains accumulate.
It will retain fresh comparisons against the Y starts and original founders; it is not released by this result.

## 2026-10-14 — Short ordinary blink continuation registered

Z registers two four-generation native searches from Y's exact selected mutants, D90 row58 and L92 row24,
using run seeds 53220/53221. Both starts were fixed irrespective of Y confirmation sign. The ordinary 32+224,
three-plus-four-life policy, mutation/breeding and approved blink physics are unchanged. Both final rank-zero
endpoints must freeze before fresh six-role confirmation against their own starts and original founders.
Block120 supplies 512 shared new seeds (52,200,000–52,200,511); native search/diagnostic IDs are independently
derived and checked for overlap.

The fixed scope is **11,340 research plus six startup validation lives**, capped at **7,200 CPU-seconds** with
at most 3,600 for startup/search and 3,600 reserved for confirmation/cleanup. Actual Y developed-body rows support
the declared estimates: 3,115.984392 and 1,582.851613 CPU-seconds respectively. No extra calibration is scheduled.
The reserve remains enforced even if evolved mutants cost more than these estimates. This tests whether ordinary
evolution accumulates further gains in a richer world; capture income and cost savings remain separate outcomes.
No Z library or life has run at registration. Exact initial populations replay, and 20 focused analysis checks
pass. Inputs, source, independent analysis and reviews are prospectively preserved as 186 artifacts at
`results/visibility_continuation_20261014/`; release follows publication.

## 2026-10-14 — Blink continuation improves economy, without a confirmed capture gain

Z completed both four-generation native searches from the fixed Y mutants and all six-role confirmation on
512 new shared seeds. Both final population rank-zero endpoints were frozen before confirmation. World,
ordinary mutation/breeding, prices and production penalties were unchanged. Differences below are means ±
paired SE over those fresh lives; these two fixed lineages do not estimate search reliability.

| Endpoint minus its Y start | D90 lineage | L92 lineage |
|---|---:|---:|
| Fitness F | +1.45095 ± .08356 | +.65631 ± .07804 |
| Capture-income contribution to F | −.10586 ± .08276 | −.17834 ± .07821 |
| Ordinary cost saving in F | +1.55681 ± .01642 | +.83464 ± .01137 |
| Captures per life | −.21680 ± .16950 | −.36523 ± .16018 |
| Dark captures per life | −.19141 ± .06523 | −.28906 ± .06932 |
| Final cells | −71.85938 ± .76191 | −32.47461 ± .47545 |
| Spikes per life | −5,069.72461 ± 51.46823 | −1,283.57031 ± 24.45346 |
| Path length | −68.57214 ± 1.06618 | −37.56735 ± 1.18973 |

Both fitness gains clear the descriptive three-SE threshold, and cost savings explain them. Neither lineage
has a resolved capture increase. L92's dark-capture decline clears three SE; D90's decline does not. Fewer
cells, spikes, clicks and movement accompany the gains. This supports economical adaptation, not a demonstrated
increase in algorithmic sophistication, memory or prediction. Against the original founders, endpoint fitness
gains are +1.77308 ± .08546 and +.58204 ± .08575 F; their total-capture changes remain unresolved at three SE.

The six-role design also retests the earlier Y mutants on new lives. **Y_D90's capture gain replicates**:
+.66016 ± .16151 captures and +.32212 ± .07969 F against original D90, essentially all capture income.
Y_L92 remains unresolved (−.07427 ± .07598 F). These new comparisons are retained separately from Y's original
confirmation rather than used to replace or select endpoints.

All 11,340 research and six retained ABI3 startup-golden lives completed. Inclusive CPU was **2,716.806021 / 7,200**,
including 2,015.493339 for startup/search and 701.312682 for confirmation/cleanup. All four recorded processes
and three owned groups exited. The recorded genetic trajectory and survivor selection replay bitwise; all
3,072 raw confirmation lives have no guard, extinction, capacity or ledger-mismatch status. Eight initial-search
guarded lives retained their penalties; native logs do not enumerate every recheck guard life or retain all
search raw ledgers. All reported search invalid/mismatch metrics are zero.

The frozen independent analyzer passed without changes. Root reanalysis reproduces the summary and all
450 paired arrays. `results/visibility_continuation_20261014/` preserves the prospective archive, native logs,
checkpoints, six raw confirmation rows, independent analysis, process clearance and decomposition figure.
A small fixed-tissue lateral-message probe is being prepared with all six genomes retained, to investigate
communication dependence before scaling selection. Its existing interventions cannot isolate memory and
do not make different genotypes' bodies identical.

## 2026-10-14 — Fixed-tissue blink communication probe registered

AA retains all six Z roles (original D90/L92, both Y mutants and both Z endpoints) irrespective of their score
signs. Each receives 128 new shared block121 seeds (52,210,000–52,210,127) in normal, freeze, and
freeze+lateral_off conditions. Existing fork controls take effect at life age 512; measurement opens at 544
after direct pending events have settled, and life ends at 1024. Different genotypes still have different
developed bodies. Freeze also stops gene, phenotype and effective-weight updates; it is a broad intervention.

The primary comparison asks how the Y-to-Z change in capture income differs between frozen tissue with and
without lateral sends. Original-to-Y and cumulative comparisons, ordinary gains, freeze losses and each
genome's own lateral loss are retained. Report all costs, guard/extinction charges and structural-check coverage;
keep every fitness row. No supported intervention here isolates memory or prediction.

The fixed scope is 2,304 research plus two standard ABI3 startup-golden lives, one two-thread worker and an
inclusive **1,200 CPU-second cap**. Six actual Z confirmation timing rows give **921.608490 CPU-seconds** under
`180 + 1.5*3*128*sum(CPU_per_life)`, below the 1,190-second release threshold. Changed lesion dynamics can exceed
that estimate; the hard cap still applies. No retry, scope reduction or endpoint substitution is allowed.
Registration and preparation run no simulations or compilation. Twenty source/synthetic and 31 independent
accounting/reader checks pass. The 153-artifact prospective record is preserved at
`results/visibility_lateral_20261014/`; release follows publication.

## 2026-10-14 — Frozen D90 tissue uses lateral signals; the cheaper continuation uses them less

AA completed all six original/Y/Z roles under normal, freeze and freeze+lateral_off in approved irregular
blink. The 128 fresh paired seeds are shared across all roles and conditions. Existing flags act at life age
512; accounting covers 544..1024. Figures below are means ± paired SE. The primary interaction is each step's
capture-income gain under freeze minus its gain with both freeze and lateral sends disabled. Positive values
mean the descendant relies more on lateral sends for capture income in this frozen condition.

| Change in lateral capture-income contribution | D90 lineage | L92 lineage |
|---|---:|---:|
| Y mutant minus original founder | +.55339 ± .29546 | −.17090 ± .18333 |
| Z endpoint minus Y mutant (primary) | −1.42415 ± .28322 | +.49642 ± .18665 |
| Z endpoint minus original founder | −.87077 ± .28155 | +.32552 ± .22427 |

D90's Z step **reduces** this contribution beyond three SE, while L92's primary effect remains unresolved.
Neither Y step shows a resolved increase; this does not establish absence of a change. L92's primary total-F
interaction is positive (+.81116 ± .21484), but its capture-income interaction remains unresolved. Reduced
costs cannot substitute for the registered capture-income outcome.

The D90 lineage has clear conditional communication use. Disabling lateral sends from its frozen tissue loses
**2.60156 ± .22930 / 3.13281 ± .22877 / 1.76563 ± .18107 captures** in original/Y/Z respectively. Those losses
supply **2.70996 ± .23885 / 3.26335 ± .23830 / 1.83919 ± .18861 F** in capture income. The corresponding L92
capture effects are −.21094 ± .14826 / −.37500 ± .11946 / +.10156 ± .16816; its Y mutant's negative effect
clears three SE. These are conditional effects, not a new algorithm or an isolated memory mechanism.

Freezing is broad: it stops growth, gene, phenotype and effective-weight updates while leaving membrane,
chemistry and motion dynamics. In L92, mean measured-window spikes rise from roughly **1,365 to 7,430** in the
original, **1,365 to 8,650** in Y, and **793 to 4,908** in Z when tissue is frozen. The intervention therefore
alters ongoing operation substantially and cannot be treated as a neutral body clamp. All 768 frozen genotype-
seed pairs nevertheless retain identical cell composition between their two frozen conditions, with the
expected live-time integrals. No pair is excluded. Different genotypes retain different developed bodies.
Lateral-off suppresses new in-plane spike sends while retaining would-be send charges; vertical spikes and
chemical communication continue. Pending direct pre-fork events settle before the measurement opens, which
does not erase earlier internal history.

All **2,304 research plus two standard ABI3 golden lives** completed in **355.924793 of 1,200 CPU-seconds**.
All raw research status flags are zero, and both recorded processes and their owned group have exited.
Late-window accounting handles events crossing its opening boundary. The frozen analyzer passes unchanged;
independent raw reconstruction reproduces all 36 registered contrasts and **2,700 paired arrays** exactly.
`results/visibility_lateral_20261014/` preserves raw ledgers, prospective sources, process receipts, reviews and
the communication-effect figure. The late-window normal results retain the continuation's economy pattern;
they do not replace Z's separate 512-life whole-life confirmation.

Before scaling depth, a new small comparison is being prepared: four ordinary 3+4-life generations versus one
12+16-life generation from each fixed Z endpoint, matching selection calls. Offline Z records show 93/256
parent slots change after rechecking and 7/8 initial leaders are displaced. These conditional ranking changes
motivate testing allocation; they do not establish a benefit from precision. The proposed comparison changes
both precision and depth and will retain capture income separately from cost savings. It is source-only,
with no new seeds, genotypes, compilation or lives released; the larger continuation remains a proposal.

## 2026-10-14 — Blink selection precision-versus-depth comparison registered

AB compares four ordinary 3+4-life generations with one 12+16-life generation from each fixed Z endpoint,
matching 4,096 selection calls per branch. Within each background, both policies share the initial population
and first candidate cohort through native seeds 53222/53223; later selection can diverge. All four final
population-rank-zero endpoints must freeze before six-role confirmation on 512 fresh block122 seeds.
Primary comparisons are precision minus depth; endpoint-minus-founder effects and capture income versus
ordinary costs remain separate. This tests allocation between precision and depth, not precision alone or equal
CPU. Two fixed founder/run pairs cannot establish general superiority or algorithmic sophistication.

Scope is 19,576 research plus ten standard ABI3 startup goldens, capped at 9,000 inclusive CPU-seconds.
Startup/search have a 7,200 ceiling and confirmation/cleanup a 1,800 reserve. At most two two-thread workers
search, followed by one two-thread confirmation worker. Actual Z developed-body rates project 6,604.114171
search and 1,221.604796 confirmation CPU-seconds, without bounding unseen mutants. No automatic retry, extension
or scope reduction. Fresh namespace review passes with the intentional paired overlaps explicitly retained.
Preparation has no simulated lives or builds; final input/reader reviews and prospective publication precede
release. Existing organism rules, physics, prices and guard/extinction penalties remain unchanged. This new
bounded study does not reopen held S or release the larger continuation proposal.

Both 32-row initial populations replay exactly from their 124 recorded point mutations. All 36 preparation
checks and 39 independent reader/native checks pass. The 176-artifact prospective archive is preserved at
`results/visibility_precision_20261014/`; its copied sources also replay the initial populations outside the
repository without a live-source fallback. The first actual offspring cohorts will be checked before confirmation
and independently replayed after execution. Release follows publication.

## 2026-10-14 — More precise scoring does not show a fitness advantage over depth

AB completed the matched-selection-call comparison from both fixed Z endpoints: four 3+4-life generations
versus one 12+16-life generation. Each branch spent 4,096 selection calls. Within each background, all 256 first
candidate genomes match bitwise across policies. All four final population-rank-zero endpoints were fixed
before fresh six-role confirmation on 512 shared block122 seeds. Values below are means ± paired SE.

| Precision endpoint minus depth endpoint (primary) | D90 | L92 |
|---|---:|---:|
| Production fitness F | −.17843 ± .07883 | −.13330 ± .07509 |
| Captures per life | +.95117 ± .16147 | −.00781 ± .15446 |
| Capture-income contribution to F | +.46444 ± .07884 | −.00381 ± .07542 |
| Ordinary cost-saving contribution to F | −.64287 ± .01331 | −.12949 ± .00751 |

Neither primary fitness effect clears the descriptive three-SE threshold. D90 precision clearly catches more
than its depth counterpart, but costs more. That relative capture advantage is not a confirmed improvement
from the common start: depth lost captures, while precision's own capture change is unresolved.

| Endpoint minus own fixed Z start | Fitness F | Captures | Capture income in F | Ordinary cost saving in F |
|---|---:|---:|---:|---:|
| D90 depth | +.37224 ± .07738 | −.72266 ± .16122 | −.35286 ± .07872 | +.72510 ± .01305 |
| D90 precision | +.19381 ± .07475 | +.22852 ± .15290 | +.11158 ± .07466 | +.08223 ± .00599 |
| L92 depth | +.05621 ± .07274 | −.21680 ± .14934 | −.10586 ± .07292 | +.16207 ± .00773 |
| L92 precision | −.07709 ± .07089 | −.22461 ± .14582 | −.10967 ± .07120 | +.03258 ± .00390 |

Only D90 depth has a resolved own-start fitness gain; it saves costs while making fewer captures. It ends with
30.55078 ± .56991 fewer cells and fires 956.34961 ± 30.32611 fewer spikes. The precision endpoint has
28.95117 ± .58791 more cells than depth, fires 428.63672 ± 28.01400 more spikes, and travels 41.81997 ± 1.09504
less distance. Bodies and policies both differ; this is not a matched-footprint mechanism test. No own-start or
primary dark-capture gain clears three SE. None of the four endpoints demonstrates a capture gain over its
start, and no new algorithm, memory or prediction has been established.

This does not show that additional scoring is intrinsically useless: precision is exchanged for three further
generations, the two policies share their first cohort, and there are only two founder/run pairs. Equal selection
calls do not imply equal CPU or total diagnostic calls. Fresh life-level uncertainty concerns these fixed
genomes rather than evolutionary reliability. The observed ranking instability justified the diagnostic;
it did not guarantee a benefit from precision.

All **19,576 research plus ten standard ABI3 startup-golden lives** completed in **3,028.748398 / 9,000 CPU-seconds**.
Startup/search used 2,647.633121; confirmation/cleanup used 381.115277. All six recorded processes and five owned
groups exited. Both complete first cohorts and all four final 32-row populations replay exactly from recorded
operations. The depth branches contain 896 offspring/1,854 point mutations each; precision branches contain
224 offspring/510 point mutations each, including their initial copies. This is recorded-operation replay,
not a replay of random draws or unsaved per-life search ledgers. Twenty-one initial-search guarded evaluation
calls retained penalties (four L92 depth and seventeen L92 precision); these include deliberately shared life IDs.
All logged invalid/mismatch metrics are zero and all 3,072 confirmation status fields are exactly zero.

The frozen independent reader passed unchanged; separate reanalysis matches the summary and all **450 paired
arrays**. The full prospective inputs, native logs/checkpoints, raw confirmation, reviews and decomposition
figure are preserved in `results/visibility_precision_20261014/`. The result supports trying a different approved
visibility regime rather than automatically extending blink searches. A source-only flash diagnostic is being
prepared with both complete Y panels and fresh two-world confirmation; it is not gated on AB success, and no
AC seeds, new genotype copies, builds or lives have been released.

## 2026-10-14 — Registered retained-panel flash diagnostic (AC)

AC reuses both exact Y panels: each original D90/L92 parent and all 64 recorded ordinary mutants. No new
candidate genotype is generated, and neither AB nor AA outcomes determine which rows enter. The approved
flash world is screened on 32 shared seeds per row. Select the greatest mean production-F mutant in each panel,
with smallest-row tie breaking; retain that selection even if it loses to its parent. Fixed blink controls remain
Y rows 58/24. Freeze both flash selections and the six-role genome table before any confirmation-cost decision.

Confirm P_D90, P_L92, B_D90, B_L92, H_D90, H_L92 in both approved flash and blink on the same 512 fresh seeds.
Duplicate roles are evaluated again. Primary effects are flash H−P in each background. Retain H−P, B−P and H−B
within both worlds and flash-minus-blink interactions for H−P and H−B. Form interactions per seed before estimating
means and SE. Report capture income, all ordinary costs, guard/extinction charges and dim/bright capture counts.
A capture-supported improvement requires positive primary F and capture income beyond the descriptive three-SE
threshold; this label never controls selection, sample size or inclusion. World interactions do not by themselves
show that H beats B in flash. The worlds jointly change residual cue strength, visibility scheduling and placement
reset semantics; this is not an isolated memory test or a measure of evolutionary reliability.

Scope is 4,160 screen + 6,144 confirmation = **10,304 research lives**, plus one standard ABI3 identity pair and
eight ABI4 calibration lives: **10,314 total**. One persistent two-thread worker has a **7,200 CPU-second** inclusive
cap, startup/calibration ceiling 180, cumulative startup/screen ceiling 3,400 and confirmation reserve 3,800. Fixed
cost projections use all twelve confirmation roles, including duplicates, with 1.5× observed rates and 180 seconds
reserve. Before screening, unknown blink winner cost uses the largest historical rate among all 65 rows; after
selection, exact selected-row flash and historical blink rates replace it. Hard caps remain binding. Failed cost
checks, numerical checks or ceilings leave this first attempt incomplete without retry, reselection or reduced scope.

The namespace review registered calibration 52,230,000–52,230,001, screen 52,240,000–52,240,031 and
confirmation 52,250,000–52,250,511, disjoint from prior research. AB is an operational dependency only: its terminal
budget and cleared processes suffice regardless of scientific outcome. All 26 prior process identities and 19 groups
are clear. One-time retained-input copying is authorized; independent actual-input/reader review and prospective
public archive are required before root runtime release. No compilation or simulated lives have run at registration.

Preparation is complete: both 65-row panels and all 130 historical timing records match Y exactly; independent
replay reconstructs all rows from 256 recorded point additions. The four configurations preserve every field
except the approved flash preset (blink is unchanged). Forty-four producer checks, 33 independent reader checks
and three focused protocol-binding checks pass. The frozen reader retains all 16 contrasts and 1,200 paired
metric arrays, including all signs and duplicate roles. The protocol binds 167 local and 35 production files.
The complete prospective archive is `results/visibility_flash_gradient_20261014/`; runtime release follows its
publication. No new candidate genotypes, libraries or simulated lives were created during preparation.

## 2026-10-14 — Flash selects different mutations, with economy and a tentative capture lead

AC screened both complete Y panels in flash without generating new candidates. The selected mutants were
D90 row54 and L92 row16, distinct from the fixed blink controls at rows58/24. All six roles had distinct genome
hashes; both selections and the full role table were frozen before the confirmation-cost decision. Each role was
then evaluated in both worlds on the same 512 fresh seeds. H denotes the flash selection, B the prior blink
selection, and P the original parent. Values below are means ± paired SE; the registered criterion is three SE.

| H minus own parent | Fitness F | Captures | Capture income in F | Ordinary cost saving in F |
|---|---:|---:|---:|---:|
| D90 in flash (primary) | +1.09996 ± .09207 | −1.45898 ± .18119 | −.71239 ± .08847 | +1.81236 ± .01768 |
| L92 in flash (primary) | +.31244 ± .09345 | +.56836 ± .19139 | +.27752 ± .09345 | +.03492 ± .00992 |
| D90 in blink | +.79558 ± .08330 | −2.09961 ± .17117 | −1.02520 ± .08358 | +1.82078 ± .01735 |
| L92 in blink | +.12226 ± .07677 | +.16406 ± .15619 | +.08011 ± .07626 | +.04215 ± .00925 |

Both primary fitness gains clear three SE. D90 does so through economy despite fewer captures: in flash it ends
with 83.69141 ± .83314 fewer cells and fires 3,772.06641 ± 40.23280 fewer spikes. L92's point estimate is mostly
capture income, but that primary capture change narrowly misses the fixed criterion: .568359 < 3×.191390.
It is therefore a tentative capture lead, not a registered capture-supported primary improvement. The small cost
saving is resolved. The sample is not extended to move this borderline result over the threshold.

| H minus prior blink selection B | Fitness F | Captures | Capture income in F | Ordinary cost saving in F |
|---|---:|---:|---:|---:|
| D90 in flash | +.94127 ± .10003 | −1.80273 ± .19587 | −.88024 ± .09564 | +1.82152 ± .01800 |
| L92 in flash | +.38214 ± .09221 | +.68945 ± .18827 | +.33665 ± .09193 | +.04549 ± .00995 |
| D90 in blink | +.45299 ± .08349 | −2.83203 ± .16917 | −1.38283 ± .08260 | +1.83581 ± .01785 |
| L92 in blink | +.02692 ± .08224 | −.04883 ± .16840 | −.02384 ± .08223 | +.05076 ± .00949 |

L92's secondary flash comparison against B resolves in both fitness and capture income. That does not replace
the parent-relative primary outcome. D90's higher fitness than B in both worlds again accompanies fewer captures.
The previous B_D90−P_D90 improvement replicates on fresh blink lives: **+.34259 ± .07907 F** and
**+.73242 ± .16103 captures**. The other three B−P world/background comparisons remain unresolved in both F
and captures. All twelve within-world contrasts are retained in the archive and figure.

| Paired flash-minus-blink interaction | Fitness F | Captures |
|---|---:|---:|
| D90 H−P | +.30439 ± .11442 | +.64063 ± .23267 |
| L92 H−P | +.19018 ± .11696 | +.40430 ± .24055 |
| D90 H−B | +.48829 ± .11917 | +1.02930 ± .24214 |
| L92 H−B | +.35522 ± .11871 | +.73828 ± .24447 |

Both H−P interactions are unresolved. D90's positive H−B interaction reflects less capture loss in flash; H still
catches fewer than B in both worlds. L92's H−B fitness interaction narrowly misses three SE (.355221 < .356130),
while its capture interaction narrowly exceeds it (.738281 > .733418). These are separate outcomes, not a reason
to relabel the F interaction. Reciprocal specialization is not established: the blink-selected B is not shown to
beat H in blink. Different screen winners alone cannot establish specialization.

The flash D90 H−P low-light capture change is −1.50000 ± .18151; L92's is +.55273 ± .19148 and unresolved.
The low-light counts use different physical regimes across worlds and do not isolate history dependence.
Residual cue strength, visibility scheduling and placement resets all differ. No memory, prediction or richer
algorithm has been established. These two fixed panels and life-seed uncertainties do not estimate independent
search reliability. Every positive, negative and near-threshold result remains reported.

All **10,304 research plus ten startup lives** completed in **2,044.626301 / 7,200 CPU-seconds**. Startup/screening
used 879.179945, confirmation/cleanup 1,165.446356. Both fixed cost gates passed. All 146 raw rows contain
10,312 complete status-zero lives, with the two standard identity lives accounted separately. All processes and
the owned group exited; no retry, dropped row, reselection or scope extension occurred. The frozen independent
reader passed unchanged; separate raw recount and reanalysis match all **1,200 paired vectors**, all sixteen
contrasts and full production accounting. All 204 local and 35 production release pins remain unchanged.
The complete prospective inputs, raw rows, process receipts, reviews and both figures are preserved in
`results/visibility_flash_gradient_20261014/`.

The next source-only direction tests whether information still pays when the existing flash becomes fully dark
after five time units. It changes one preapproved world constant, retains the existing external controller
algorithms and matches their known dark-amplitude parameter to zero. It is not an evolved-memory claim or an
automatic large search. Existing silent-duplication studies already failed to establish a useful copied gene;
there is no evidence yet that controller capacity is the main bottleneck. AD remains unregistered and unlaunched.

## 2026-10-14 — Exploratory capture-value sensitivity of the fixed flash-panel outcomes

The repeated economy gains motivate checking the reward-to-cost balance using AC's saved data. This is a
post hoc analysis chosen after seeing AC, with no new simulations, selection or production-price changes.
All twelve within-world contrasts are retained at capture values 500, 1,000 and 2,000. For each paired seed,
reprice F as `original F difference + (new value / 500 - 1) * capture-income difference`, leaving every ordinary
cost, guard charge and extinction charge fixed. Means and SE are computed from the repriced paired vectors.

| D90 flash-selected H minus prior blink-selected B | Capture value 500 | 1,000 | 2,000 |
|---|---:|---:|---:|
| Flash F difference | +.94127 ± .10003 | +.06103 ± .19489 | −1.69945 ± .38576 |
| Blink F difference | +.45299 ± .08349 | −.92984 ± .16514 | −3.69550 ± .32986 |

Doubling capture value nearly eliminates the economical D90 mutant's advantage in flash; quadrupling it
reverses the ranking beyond three SE. This shows that the price balance matters for which existing genome
ranks better. It does not show that changing the price would produce more captures, sophisticated algorithms
or a different evolutionary trajectory. The same outcomes are reused, so these are not additional independent
confirmations. L92's flash H−P and H−B means rise with capture value; all signed outcomes remain archived.

Independent reconstruction from all twelve raw AC confirmation ledgers reproduces all **36 paired vectors**
bytewise, including means, SE and threshold flags. Direct per-life repricing followed by paired subtraction
agrees within 7.11e−15, the observed floating-point operation-order difference. Source review confirms that
capture value feeds capture income but no physical or organism input; accounting ledger bytes may change.
The compact public replay uses 24 extracted source vectors. Full raw auditing uses the exact already-published
AC records identified by commit and hashes. Both draft review-helper errors are preserved separately; neither
changed the analysis or generated lives. Evidence: `results/capture_value_sensitivity_20261014/`.

## 2026-10-14 — Fully dark flash information payoff registered (AD)

AD changes the existing flash world's residual target-cue multiplier from .25 to zero. The target is visible
for five time units after placement, then emits no target receptor pings until the next placement. All other
physical parameters stay fixed. Thirteen existing X2 external instruments are retained in order R0, R1, I, A,
B, D0–D7; only I/B's declared physical dark-amplitude parameter changes to match zero. Bodies, controller
programs and all other parameter values are unchanged. These are measuring instruments with free central
computation, not evolved organisms or a hand-built winning-body requirement. R0/R1 are retained references,
not newly optimized darkness reflexes.

Each instrument receives the same 512 fresh T1024 seeds, 52,270,000–52,270,511: 6,656 research lives. Report
fixed I−R0 and I−R1, the gap above the better whole-mean reference, all eight do-less comparisons, and broad
model/action ablations I−A/I−B. Preserve all costs, both signs and all 836 paired metric vectors. The existing
descriptive checks require an information gap above 1 F and three paired SE, and do-less advantages below a
quarter of that gap. They do not establish a memory-specific result. Motor persistence, queued signals,
retained direction, blind search and capture-triggered new flashes remain alternatives; the retained external
controller also approximates the fixed flash deadline with an exponential transition model. No paired causal
comparison against X2's old .25 world is registered, because that study used different seeds.

The fixed validation matrix has 76 calls: eight scratch/production bridge, twelve full/fast, fifteen callback
record/replay/control, 39 cost calibration and two standard ABI3 seed11/T200 identity lives. The production
identity runs exactly once in an isolated owned subprocess before scratch imports. Validation seeds are
52,260,000–52,260,002, with all intentional engineering reuse counted. Total scope is **6,732 calls** under
**2,400 inclusive CPU-seconds**, including a 180-second validation ceiling and ten-second stop margins.
One two-thread worker runs at a time. Before research, require
`180 + 1.5 * 512 * sum(max(new role CPU / 3, historical role CPU / 512)) <= 2390` across all thirteen roles.
Compilation, descendants, monitoring, failures and cleanup count. First attempt only; no retry, extension,
resumption, row dropping or reduced scope.

Preparation was invoked once without compilation or simulation. Protocol `ee041636…100fe` binds 98 local
and 56 production/provenance files. The 42-file ABI3 bundle, all candidates and thirteen historical timing rows
match their sources; independent reviews verify only the stated amplitude changes. Twenty-five distinct reader
checks pass, including a complete synthetic 76+6,656-call fixture. The reader's scientific and operational logic
is unchanged after source review. A mistaken pin-count assertion in one binding test was corrected to the exact
X2∪Y source map; its failure is preserved, with no reader or producer logic change. All seven registration-pinned
review receipts remain unchanged.

The namespace review checks both fresh ranges against historical records and all AC IDs. AC's terminal status
is solely an operational dependency, with no scientific-success prerequisite. All 28 prior identities, 20 groups
and nine budgets are clear. The prospective archive is `results/visibility_dark_tail_information_20261014/`;
its scientific inputs are bundled, while exact historical namespace evidence already in Git is referenced by
path, commit and hash. Full namespace provenance therefore needs those earlier repository artifacts. A retained
historical scratch library is provenance, not a new AD compilation. Root runtime release follows publication.
This bounded diagnostic changes no organism rule, ABI, reward or population-dependent world behavior, and
does not release held S or the larger selection proposals.

## 2026-10-14 — Information still pays after the flash becomes fully dark

AD completed all thirteen retained instruments on the same 512 fresh T1024 seeds. After each five-unit flash,
the target's cue multiplier is zero; background sensing remains. The full external controller I and the two
retained reflexes R0/R1 have the same 56-cell footprint. R1 is the better whole-mean reference. All values below
are paired means ± SE; both fixed reference contrasts remain reported.

| Contrast | Fitness F | Captures per life | Captures while target dark |
|---|---:|---:|---:|
| I−R0 | +4.67936 ± .09515 | +9.33789 ± .19900 | +7.82227 ± .17989 |
| I−R1 | +4.67278 ± .09527 | +9.31055 ± .19926 | +7.79883 ± .18046 |
| I−A, broad visibility-model ablation | +.96402 ± .09744 | +1.75000 ± .20180 | +1.67383 ± .19160 |
| I−B, suppress actions while believed dark | +3.64750 ± .08966 | +7.84375 ± .18590 | +7.01953 ± .17549 |

Capture income explains **+4.54617 ± .09729 F** of I's gain over R1. I makes **14.92188 ± .43015 fewer misses**,
saving **.14572 ± .00420 F**, while spike and movement costs rise slightly. This is predominantly more captures,
with free external computation; it is not a demonstrated locally attainable policy. The full instrument averages
11.67773 captures, versus 2.36719 for R1. Its 9.97656 dark captures per life do not themselves establish memory.

| Fixed do-less control minus R1 | Fitness F |
|---|---:|
| D0 | +.26137 ± .04380 |
| D1 | +.28770 ± .04392 |
| D2 | +.08807 ± .04217 |
| D3 | +.34865 ± .03640 |
| D4 | −.74478 ± .03627 |
| D5 | −.06674 ± .02148 |
| D6 | −.00400 ± .00941 |
| D7 | −.06303 ± .03689 |

The best whole-mean do-less control is the two-cell clicker D3. Its gain is **7.4614% ± .7833 percentage points**
of I's gap, using the registered ratio of paired means. Its quarter-gap margin is **+.81954 ± .04209 F**;
all eight controls have positive quarter-gap margins. Both registered descriptive information-payoff and do-less
checks pass. Selecting the better whole reference/control conditions these uncertainties; neither is a bound
over all possible reflexes or economy strategies. The retained references were not optimized for darkness.

The broad model and action interventions help explain this external instrument's advantage, but neither isolates
memory. The controller retains an approximate exponential visibility model even though the physical flash ends
after a fixed five units. Persistent motion, queued signals, retained direction, blind search and new flashes after
capture remain alternatives when studying future organisms. There is no evolved-memory claim or automatic
capability-specific admission. The .25-light X2 experiment used different seeds and is not a paired world-effect
comparison. No organism rule, genotype, price or ABI changed in AD.

All **6,656 research plus 76 validation lives** completed in **514.140424 / 2,400 CPU-seconds**. Validation used
57.698988; research and cleanup used 456.441436. The fixed calibration projected 1,221.299322 CPU-seconds and
passed before research. All 6,656 research statuses and all 74 raw validation statuses are zero; the two standard
identity goldens are separately recorded. Three recorded process leaders and both worker groups exited. All
140 local and 56 production release pins remain unchanged. No retry, dropped instrument or scope extension.

The frozen reader passed unchanged on the complete data. Independent raw accounting reproduces the scientific
summary and all **836 paired arrays** exactly, with raw costs below the corresponding monitored stage totals.
The prospective source/inputs, validation replay logs, runtime artifacts, raw research rows, reviews and figure
are archived at `results/visibility_dark_tail_information_20261014/`. Preparation prose remains frozen historical
evidence; the terminal readme records the final status. The next source-only preparation tests whether ordinary
mutants of the existing evolved founders can exploit V's fast persistent-target world. That is an accessibility
question, without prescribing a prediction algorithm; no AE seeds, inputs, compilation or lives are released yet.

## 2026-10-14 — Persistent-target mutation accessibility registered (AE)

AE tests ordinary retained mutations in V's existing fast persistent-target world: target speed .3, heading
persistence 200, continuous visibility, T1024 and unchanged prices. Both complete Y panels enter: each original
D90/L92 founder and all 64 recorded ordinary mutants. No new candidate is generated or filtered by previous
results. The world exactly matches V's 66-field ABI3 packing, including d0=1 and d_min=.5. Y used the same
conduction; target motion and visibility differ. V's external information payoff motivates this accessibility
test but does not prescribe an organism algorithm or require a hand-built winning body.

Each of the 130 rows receives 32 fresh shared screen lives. Select the greatest mean production-F mutant
among rows1–64 in each background, with lowest-row tie breaking; keep it even if worse than the parent.
Freeze both selections and the ordered four-role table P_D90, P_L92, H_D90, H_L92 before the confirmation-cost
decision. Confirm all four roles on the same 512 fresh lives, including any duplicate roles. The two primary
contrasts are H minus its own P. Report both signs and paired SE for fitness, captures, capture income, all
ordinary costs, guard/extinction charges and body/activity measures: 128 paired metric vectors in total.
The strict three-SE label is descriptive and never changes inclusion or sample size. No comparison with
historical Y scores is paired evidence, and these two founder neighborhoods do not estimate search reliability.
Capture gains would support accessible task improvement; economy gains answer a narrower question. Neither
alone demonstrates prediction, memory, learning or a new algorithm. A negative result does not reject the world.

Scope is **4,160 screen + 2,048 confirmation = 6,208 research lives**, plus two standard ABI3 seed11/T200
identity lives and eight calibration lives: **6,218 calls total**. Calibration uses parent row0 and mutant row1
from each panel on two seeds. One persistent two-thread worker has a **5,400 inclusive CPU-second** cap,
a 180-second startup/calibration ceiling, cumulative startup/screen ceiling 3,400 and confirmation reserve
2,000. Stop margins are ten seconds. Compilation, descendants, monitoring, failures and cleanup count.

Before screening, each row's projected rate is the larger of that background's maximum new calibration rate
and its own historical Y rate. Sum all 130 rates, multiply by 32 and 1.5, then add monitored startup CPU;
require at most 3,390 seconds. For confirmation, each known parent uses its own calibration/historical maximum;
each unknown winner uses the maximum calibration or any historical rate in its background. Require
`180 + 1.5 * 512 * sum(four role rates) <= 1990`. After selection, replace each role's rate with the maximum
of its measured screen rate and its own historical rate; apply the same reserve check before confirmation.
All 130 historical timings remain included. Rates do not guarantee future costs; hard ceilings remain binding.
This is the first attempt only, without retry, resumption, reduced scope, reselection or extension.

Fresh IDs are calibration 52,280,000–52,280,001, screen 52,290,000–52,290,031 and confirmation
52,300,000–52,300,511. The namespace audit checks all three whole blocks against recorded historical seed
payloads and subsequent files; all 546 IDs are disjoint. Historical namespace evidence already committed in Git
is referenced by exact commit, path and hash. AD is an operational dependency only: its terminal budget and
cleared processes suffice independently of its scientific outcome. All 31 prior identities, 22 groups and ten
budgets are clear. Registration authorizes one-time retained-input copying; actual-input review, reader binding,
prospective publication and root release precede any compilation or simulation. The public record is
`results/prediction_gradient_20261014/`. Held S, large selection rollouts and paid compute remain unreleased.

## 2026-10-14 — A small capture gain in the persistent-target world, alongside larger economy gains

AE screened both complete retained Y mutation panels in the exact V world, then confirmed all four fixed
selected-mutant/parent roles on 512 fresh shared lives. D90 selected row54, the same genotype selected earlier
in flash; L92 selected row31, distinct from its earlier blink and flash selections. Both selections and the role
table were fixed before the confirmation-cost decision. Values below are means ± paired SE.

| Selected mutant minus own parent | Fitness F | Captures per life | Capture income in F | Ordinary cost saving in F |
|---|---:|---:|---:|---:|
| D90 row54 | +1.73327 ± .07687 | −.32813 ± .14990 | −.16022 ± .07319 | +1.89349 ± .01880 |
| L92 row31 | +.72874 ± .05238 | +.41797 ± .10489 | +.20409 ± .05122 | +.52466 ± .01074 |

Both fitness gains exceed three paired SE. L92's capture and capture-income gains also exceed that criterion:
mean captures rise from **3.45703 to 3.87500** per life. This is a modest accessible task improvement in this
fixed mutation neighborhood. Most of its fitness gain still comes from cost savings, and its absolute mean F
remains **−.82235**, versus −1.55110 for its parent. It ends with **21.09570 ± .41017 fewer cells** and fires
**868.54688 ± 34.97134 fewer spikes**, while misses fall by **6.45508 ± .58638**. These correlated changes do
not identify how the capture gain arises.

D90's gain is economical: it saves more in costs than its total fitness increase. Its negative capture estimate
is unresolved under the fixed three-SE rule. It ends with **83.66992 ± .83538 fewer cells** and fires
**5,409.87109 ± 80.10837 fewer spikes**; misses fall by **7.88477 ± .27796**. Absolute mean F rises from
−1.64433 to .08894. Selecting the same D90 genotype in two worlds does not establish persistent-target
specialization. No historical cross-world score comparison is treated as paired evidence.

The recorded L92 point additions are W[7,7]−.61441535 and W[5,0]+.30493116; the D90 additions remain
W[0,23]−.78306687 and W[7,24]−.64946520. Both pairs and all panel rows replay exactly from recorded float32
operations. No single-allele intervention was performed, so neither mutation is assigned an isolated function.
These two fixed neighborhoods do not estimate independent search reliability. Capture improvement alone does
not establish tracking, prediction, memory, learning or a more sophisticated generated algorithm.

All **6,208 research plus ten validation lives** completed in **1,226.079103 / 5,400 CPU-seconds** and
540.565354 wall seconds. Startup/calibration used 13.689933 CPU-seconds; cumulative startup/screening used
874.767044, leaving confirmation/cleanup at 351.312059. Both fixed cost gates passed. All **6,216 raw lives**
across 138 rows have status zero, with two standard numerical-identity goldens recorded separately. Neither
contrast has guard or extinction charges. Both recorded processes and the owned group exited; all 235 local
and 35 production release pins remain unchanged. There was no retry, omitted row, reselection or extension.

The frozen reader passed unchanged. An independent raw accountant and separate archive-compatible reanalysis
reproduce both contrasts, the full summary and all **128 paired vectors** exactly. Full prospective inputs,
raw rows, operation receipts, reviews and the capture-versus-economy figure are preserved in
`results/prediction_gradient_20261014/`. Frozen preparation prose remains historical evidence; the terminal
readme records completion.

L92 supplies a reason to test whether capture improvement can accumulate. A source-only AF proposal now
prepares two short ordinary continuations from **both** fixed AE selections, retaining the less encouraging
D90 lineage as well. Its prospective scope is four generations per start and four endpoint/start roles on fresh
confirmation lives, with prices, world and asynchronous local rules unchanged. No AF registration, seeds,
input copying, genetic draws, builds or lives are released by this result. Fully dark flash remains another
useful direction; neither world is admitted or rejected by hand-built bodies or these local accessibility results.

## 2026-10-14 — Watchable persistent-target comparison, with exact existing-life replay

`results/atlas/persistent_target.html` is a standalone comparison of both AE parents and selected mutants
in the exact existing persistent-target world. The first recorded confirmation seed, 52,300,000, is used
regardless of outcome: L92's mutant catches two versus three for its parent on that life, although its
512-life mean advantage is +.41797 ± .10489. The page shows the full-study estimates beside the illustration.
Play/pause, restart, lineage and speed controls change viewing only; local rules, prices and world stay fixed.

All four browser-engine replays reproduce all 57 C ledger columns bitwise (228 matches), using only
already-published outcomes. They used 10.375161 CPU-seconds and all exited. No new C/Python lives, research
observations, genetic draws or compilation occurred. Sixty mock UI checks cover controls, paused/hidden-tab
behavior, two screen widths and finite drawing coordinates; no real-browser screenshot was available.
The initial export helper's incorrect archive path failed before any output or life and is preserved.
Source, exact inputs, truth, replay budget and UI checks: `results/ae_watchable_20261014/`.

## 2026-10-14 — Short persistent-target continuations registered (AF)

AF asks whether ordinary evolution can accumulate further capture improvement in the existing persistent-target
world. It retains **both** fixed AE selections: D90 row54 and L92 row31, regardless of either earlier confirmation
sign. Each starts one four-generation native search with 32 parents and 224 offspring, three initial evaluation
lives and four additional lives for the top 64. Initialization keeps the exact start plus 31 ordinary two-point
mutants; both initial populations and their random-generator states/operations are frozen once before search.
Duplication and deletion remain disabled. The ABI3 world is exactly V/AE: target speed .3, heading persistence
200, continuous visibility, T1024, d0=1 and d_min=.5. Prices and local asynchronous rules are unchanged.

After both searches complete, freeze each generation-four rank-zero endpoint together, then compare both
endpoints and both own starts on the same 512 fresh lives. The two endpoint-minus-own-start capture contrasts
lead the behavioral interpretation, accompanied by production fitness, capture income, ordinary costs, guard
and extinction charges. Report both signs with paired SE and the fixed strict three-SE descriptive criterion.
A fitness gain explained by economy remains an economy result; capture gains alone do not establish prediction,
memory or a more sophisticated algorithm. These two fixed continuations do not estimate reliability over
independent evolutionary runs. Native search retains curves/checkpoints and diagnostics, while full 57-column
raw ledgers are retained for all 2,048 confirmation lives.

The fixed scope is **8,268 native search/diagnostic plus 2,048 confirmation lives**, with six startup goldens:
**10,322 total calls**. Two two-thread search workers precede one two-thread confirmation worker. The inclusive
CPU ceiling is **5,400 seconds**, with startup/search capped at 3,400 and at least 2,000 reserved for confirmation
and cleanup. Six actual AE timing rows give prospective search/confirmation estimates of 2,365.459/992.014
CPU-seconds with fixed margins; these are planning estimates, not guarantees for new mutants. Hard caps bind,
with no retry, resume, dropped lineage, scope reduction or extension.

Runs 53224/53225 supply 128 audited unique native life IDs; confirmation uses 52,310,000–52,310,511. The two
half-duration diagnostics per search reuse their registered final seed IDs; call counts and unique IDs differ.
The namespace audit also accounts for the viewer's copies of already-used seed 52,300,000. All 34 prior process
identities, 24 owned groups and twelve budgets are clear. Registration authorizes one-time input copying and
recorded ordinary initialization only. Protocol `ebdc3f37…15b5e0` pins 50 local and 35 production files.
Preparation performs no compilation or lives. Independent input/reader review, prospective publication and root
runtime release precede measurement. Evidence: `results/prediction_continuation_20261014/`. Held S, broader
selection families, population-responsive worlds and paid compute remain unreleased.

## 2026-10-14 — Persistent-target continuation improves economy while losing captures (AF)

Both four-generation ordinary searches completed from the fixed AE selections. Their final rank-zero endpoints
were frozen together before comparison with their own starts on 512 fresh shared lives. The unchanged world,
prices and native selection objective reward net fitness, so capture performance and physical costs are reported
separately. Values are means ± paired SE.

| Endpoint minus own AE start | Fitness F | Captures per life | Capture income in F | Ordinary cost saving in F |
|---|---:|---:|---:|---:|
| D90 | +.73529 ± .06459 | −.34180 ± .13345 | −.16689 ± .06516 | +.90218 ± .01283 |
| L92 | +1.43758 ± .05065 | −1.92969 ± .10146 | −.94223 ± .04954 | +2.37981 ± .01221 |

Both fitness gains exceed the fixed three-SE criterion; neither gains captures. D90's negative capture estimate
is unresolved under that criterion. L92's capture loss resolves strongly: mean captures fall from **3.85938 to
1.92969**, while absolute mean F rises from −.83237 to +.60520. Its mean terminal body shrinks from **108.96094
to 13.06250 cells**, and spikes fall from **2,517.89063 to 84.01563**. It makes **28.83789 ± .51566 fewer misses**
and travels **150.59793 ± 1.97385 less distance**. Living-cell costs supply the largest saving. These measurements
establish an economical endpoint with less capture activity; they do not identify a particular circuit or policy.

D90 ends with **39.26758 ± .52442 fewer cells** and fires **2,582.44727 ± 52.52066 fewer spikes**. Its mean
captures change from 5.81445 to 5.47266, with absolute F rising from +.12332 to +.85861. Neither continuation
accumulates a demonstrated capture improvement, and no prediction, memory, communication mechanism or richer
algorithm is established. The two fixed evolutionary runs do not estimate search reliability. AE's earlier L92
mutation remains its own positive result; AF does not include original parents as new comparison arms.

All **10,316 research/diagnostic plus six startup golden lives** completed in **1,191.290362 / 5,400 CPU-seconds**
and 372.726189 wall seconds. Search used **1,012.253396** CPU-seconds; confirmation and cleanup used **179.036966**.
Both final populations and recorded genetic/selection operations replay exactly. Native initial-evaluation logs
retain **18 D90 and nine L92 guarded lives** with penalties; those summaries do not provide every raw search
ledger or every recheck guard count. All **2,048 full raw confirmation lives** have status zero, with no guard or
extinction charges. All four recorded process leaders and three owned groups exited, and all 117 local/35
production release pins are unchanged. There was no retry, reselection, dropped lineage or extension.

The frozen reader passed unchanged. A separate raw accountant and native/full reanalysis reproduce the summary
and all **146 paired vectors**, including exact saved vector bytes. The prospective archive remains unchanged;
terminal evidence, reviews and a capture-versus-economy figure are at `results/prediction_continuation_20261014/`.
The root publication helper initially expected the wrong archive-review status label and stopped before writing
release prerequisites or staging; that metadata-only error is preserved and did not affect study code or lives.

The result weakens the case for an automatic longer continuation of these endpoints. Source-only AG instead
prepares one ordinary-mutant accessibility test in AD's fully dark flash world, using the complete retained Y
panels and unchanged prices. Fresh captures and dark-phase captures will accompany fitness/cost accounting;
dark captures alone cannot establish memory. No AG registration, input copying, genetic draws, builds or lives
are released by this result. Worlds continue to be judged by information payoff, not by these local mutation
neighborhoods or hand-built bodies.

## 2026-10-14 — Ordinary-mutant accessibility in fully dark flash registered (AG)

AG tests whether nearby evolved programs can improve capture performance in the exact dark-flash environment
whose information payoff was measured in AD. After each five-unit flash, target cue strength is zero; background
sensing continues. The existing ABI4 world, prices and local asynchronous rules are unchanged. AD's external
instrument motivates the task through measured information payoff; it is neither an evolved policy nor a
hand-built-body prerequisite. These mutation neighborhoods cannot admit or reject the world.

Reuse both **complete original Y panels**, each containing its original D90/L92 founder and all 64 ordinary
mutants, regardless of previous world outcomes. Screen all 130 rows on 32 shared fresh lives. Select the highest
mean-production-F mutant per founder, with lowest row index breaking ties; retain either sign. Freeze both
selected rows and the four-role genotype table before the confirmation-cost decision. Confirm both selected
mutants and both parents on **512 fresh paired lives** in the single dark-flash world. No new genotype is drawn.

The two selected-mutant-minus-parent capture contrasts lead the behavioral interpretation, with native dark-phase
captures alongside full production fitness, capture income, ordinary costs and guard/extinction charges. Report
means ± paired SE and the fixed strict three-SE descriptive indicators for both lineages. A cost-supported
fitness gain remains an economy result. Dark captures alone do not establish memory: coasting, delayed signals,
retained direction and blind search remain alternatives. This is not a paired dark-versus-dim comparison, an
estimate of evolutionary repeatability, or a demonstrated advance in algorithmic sophistication.

Fixed scope is **6,208 research plus ten startup/calibration lives**, under **5,400 inclusive CPU-seconds** with
one two-thread worker. Startup/screening is capped at 3,400, preserving 2,000 for confirmation and cleanup;
startup/calibration must complete within 180. All 130 historical AC dim-flash timing rows supply per-row cost
floors. Their planning estimates, including fixed allowances/margins, are 1,293.700 CPU-seconds for screening
and 1,206.546 for confirmation. Eight fixed calibration lives in the actual dark world may raise those estimates;
the unchanged scope must fit before screening. Both winners are then frozen before a second cost check based
on their measured screen rates. No retry, omitted row, reselection, scope reduction or extension is allowed.

Audited fresh seed blocks 132/133/134 provide calibration 52,320,000–52,320,001, screening
52,330,000–52,330,031, and confirmation 52,340,000–52,340,511. All 38 prior process identities, 27 owned groups
and thirteen terminal budgets are clear. One-time preparation copies all retained panel and timing rows;
protocol `ff9af8c7…a7955f` pins **170 local and 35 production files**, including the exact 70-field ABI4 packing.
No compilation, genetic draws or lives ran during preparation. Independent input/reader review, prospective
publication and root runtime release precede measurement. Evidence: `results/visibility_dark_tail_gradient_20261014/`.
Held S, broader selection families, motor flip, population-responsive worlds and paid compute remain unreleased.

## 2026-10-14 — Dark-flash accessibility: modest capture gain, larger economy gains (AG)

AG completed its fixed retained-panel study in AD's exact ABI4 dark-flash world. Each target placement starts
five bright time units, after which target cues disappear until the next placement; background sensing continues.
All 130 retained Y rows received the registered 32-life screen. D90 row54 and L92 row61 were fixed before either
selected-mutant/parent comparison on 512 fresh paired lives. Prices, local asynchronous cell rules and genomes
were unchanged by the study infrastructure; no new genetic draw was needed.

| Selected mutant minus own parent | D90 row54 | L92 row61 |
|---|---:|---:|
| Production fitness F | +1.829303 ± 0.039531 | +0.551484 ± 0.036924 |
| Captures per life | +0.048828 ± 0.069281 | +0.220703 ± 0.071139 |
| Dark-phase captures per life | +0.013672 ± 0.067297 | +0.207031 ± 0.069563 |
| Capture-income contribution to F | +0.023842 ± 0.033828 | +0.107765 ± 0.034736 |
| Ordinary cost saving in F | +1.805461 ± 0.018085 | +0.443719 ± 0.010579 |
| Terminal cells | −88.443359 ± 0.851705 | −20.431641 ± 0.478091 |
| Spikes | −2672.970703 ± 26.636438 | −186.804688 ± 12.356626 |

All entries are means ± paired SE over 512 fresh seeds. L92's capture gain narrowly clears the fixed strict
three-SE descriptive criterion; its dark-phase gain narrowly does not. Use the unrounded values in the archived
summary for those indicators. Mean L92 captures rise from 1.589844 to 1.810547. Most of its fitness gain still
comes from economy, and its mean net F remains negative (−1.663042). D90's capture change is unresolved, while
its fitness gain is almost entirely cost saving. Both guard and extinction charge differences are zero.

This establishes one modest accessible capture improvement in the dark-flash world. It does not establish
memory, a new algorithm, reliable evolutionary improvement across starts, or a controlled dark-versus-dim world
effect. Dark captures alone would not isolate memory even with a resolved gain: coasting, delayed signaling and
blind search remain alternatives. These local mutation neighborhoods do not admit or reject a world whose
information payoff was measured separately.

The fixed **6,208 research plus ten startup calls** completed in **1,204.022071 CPU-seconds** and 529.776304 wall
seconds. Startup/screens used 858.650131 CPU-seconds and confirmation/cleanup used 345.371940, within the
5,400/3,400/2,000 ceilings. All 6,216 retained ABI4 raw lives have status zero; the other two calls are the standard
identity goldens. Both recorded process leaders and the worker group exited. All **232 local and 35 production**
release pins remain unchanged. There was no retry, dropped row, reselection, new genotype or extension.

The frozen analyzer passed unchanged. Independent raw accounting and replay reproduce all **132 paired vectors**
and the complete summary. The prospective archive remains byte-for-byte preserved; terminal data, resource
records, independent reviews and a three-SE capture/cost figure are in
`results/visibility_dark_tail_gradient_20261014/`. The reader's earlier test-only checksum typo and its corrected
passing tests remain in the source history; it never affected simulation inputs or the bound analysis.

The next source-only preparation, AH, tests a small change to external selection in the persistent-target world:
one ordinary control and one arm that temporarily reserves two breeding places for uniformly chosen new
offspring, returning to ordinary selection in the final generation. This may give an initially uncompetitive
mutation a chance to contribute descendants. It leaves task F, prices, worlds and organism rules unchanged,
and cannot make permanently uneconomic behavior competitive. The proposed pilot is one matched pair from the
fixed AE L92 start, not a reliability estimate or a large rollout. No AH registration, genetic draws, builds or
lives are released by this result. Held S, motor flip, larger selection families and paid compute remain held.

## 2026-10-14 — A small exploratory reserve in external selection registered (AH)

Repeated short searches have often improved net fitness by reducing costs while losing captures. AH tests
whether reserving a few breeding places for randomly chosen fresh offspring changes the outcome. It keeps
the existing task F, prices, persistent-target world, mutation operators and local asynchronous organism rules.
This is a small external selection-policy change under standing preapproval, not a prescribed cell behavior,
new reward, global organism clock, or population-responsive world.

One matched pair starts from the fixed AE L92 row31 genotype. This is a deliberately chosen case: that genotype
had a modest capture gain, then its AF continuation lost captures while improving F. The new ordinary control
is run afresh; historical AF is not reused as its comparator. Both arms share one recorded 32-member initial
cohort, native genetic seed and life-seed schedule. Their first candidate populations must match byte-for-byte;
later populations may diverge after different selection. Each arm runs four generations of 32 parents plus
224 offspring, three initial lives per candidate and four more lives for exactly 64 rechecked candidates.

The control uses ordinary selection throughout. In treatment generations 0–2, a separate deterministic lottery
selects two distinct fresh offspring uniformly, independent of fitness, captures, morphology and genotype.
Those two plus the best 62 other candidates receive recheck lives. The two protected offspring plus the best
30 others by pooled seven-life F form the 32 breeders, ordered by the existing full F ranking. All breed with
equal probability; protection lasts for one breeding opportunity. Generation 3 returns to ordinary selection.
The lottery does not consume the native mutation or tie-breaking random streams. All existing ranking calls,
tie handling and checkpoint identities are preserved or explicitly extended to bind the external adapter.

Both generation-3 rank-zero endpoints are frozen before confirmation. The start, control endpoint and reserve
endpoint each receive 512 fresh shared lives, retaining duplicate roles if they occur. Reserve-minus-control
captures is the primary behavioral comparison; both endpoint-minus-start comparisons remain. Report all three
contrasts with paired SE, unchanged F, capture income, ordinary costs and guard/extinction charges. The strict
three-SE descriptions concern uncertainty across evaluation lives for these fixed genomes. One paired search
does not estimate policy reliability. Capture improvement with worse F is a tradeoff; higher F from economy
alone does not demonstrate a richer algorithm. A protected ancestor would not prove a necessary stepping stone.

The fixed scope is 8,268 native search/diagnostic plus 1,536 confirmation lives and six numerical-identity
goldens: **9,810 total calls**. Two two-thread searches precede one two-thread confirmation worker. The inclusive
CPU cap is **5,400 seconds**, with startup/search capped at 3,400 and 2,000 reserved for confirmation and cleanup.
All 65 historical AE L92 screen timings supply a conservative maximum; fixed margins project about 2,690 CPU
seconds for search and 957 for confirmation. New reserve offspring may cost more: hard limits bind, with no
retry, resume, scope reduction, endpoint substitution or extension. Equal life counts do not imply equal CPU.

The paired native seed and fresh confirmation block are independently audited before registration, including
intentional sharing within the pair and native final-diagnostic seed reuse. Full lineage metadata records all
candidate scores/IDs, ranking inputs, lottery indices, shortlist and survivors for independent policy/genetic
replay. All final confirmation lives retain complete ABI3 physical ledgers. Synthetic tests cover ordinary-mode
equivalence, reserve exclusions, exact ties, identity binding and interrupted/restarted adapter state without
new simulation lives; no live resume experiment is claimed or used.

One-time preparation has generated exactly one shared 32-row native initialization: the fixed founder plus
31 ordinary two-point mutants, with all 62 additions recorded. Both configurations and fixed inputs are frozen.
It ran no life or compiler. Actual-input and independent reader review, prospective publication and separate root
release precede measurement. The completed AG resource state is a dependency; its scientific sign is not. Evidence: `results/exploratory_reserve_20261014/`. The larger selection
family, motor flip, held S and paid compute remain unreleased.

The audited shared native run seed is **53226**. Its 64 unique native life IDs are intentionally reused across
the two arms; fresh confirmation uses **52,350,000–52,350,511** (block 135). The 576 combined unique IDs exclude
prior study IDs and standard golden seed 11. All 40 prior process identities, 28 groups and fourteen terminal
budgets are clear. Actual protocol `0a9e5059…4c61be4` pins **102 local and 35 production files**, with exact
66-coordinate ABI3 world packing. The source reviews include 20 producer and 47 reader checks plus one focused
archive-portability check. No runtime release is implied by registration or successful genetic preparation.

## 2026-10-14 — AH complete: a temporary offspring reserve improves the endpoint relative to matched ordinary selection

**Question.** In the persistent-target world, does briefly keeping two randomly chosen new offspring help search
retain useful alternatives? This was one deliberately chosen AE L92 starting genome and one matched pair of
four-generation searches. Generations 0–2 protected two uniformly sampled fresh offspring through recheck and
breeder selection; generation 3 used ordinary selection in both arms. Task fitness, prices, world, mutation,
crossover and local asynchronous organism rules stayed fixed. No behavior was prescribed.

**Fresh confirmation, 512 paired lives; mean ± paired SE:**

| Fixed contrast | Captures per life | Fitness F | Capture-income contribution to F | Ordinary cost saving in F |
|---|---:|---:|---:|---:|
| Reserve − control (primary) | **+0.556641 ± 0.110184** | **+0.254917 ± 0.054269** | +0.271797 ± 0.053801 | −0.016880 ± 0.007637 |
| Control − start | −0.218750 ± 0.115289 | +1.094887 ± 0.057418 | −0.106812 ± 0.056293 | +1.201699 ± 0.011916 |
| Reserve − start | +0.337891 ± 0.115967 | +1.349804 ± 0.057343 | +0.164986 ± 0.056625 | +1.184818 ± 0.012074 |

Reserve beats control by the fixed three-SE criterion for both captures and F. Extra capture income explains
the relative advantage; mean ordinary costs are slightly higher, with their difference unresolved at three SE.
Reserve's capture gain over the starting genome narrowly misses that criterion (3 SE = 0.347902); control's
capture change is also unresolved. Both large fitness gains over the start come mainly from ordinary cost savings.
No guard or extinction difference contributes to these contrasts.

Mean captures are **3.525391 → 3.306641 / 3.863281** for start → control / reserve; mean F is
**−0.979188 → +0.115699 / +0.370616**. Mean terminal cells shrink **108.908203 → 60.976563 / 60.035156**.
Reserve fires **192.001953 ± 15.684410** more spikes per life than control while ending with
**0.941406 ± 0.281649** fewer cells. These are descriptive organism differences, not identified computation.

**What the experiment establishes.** The fixed reserve endpoint performs better than the fixed control endpoint
on fresh lives. The 512-life uncertainty concerns those endpoints; a single evolutionary pair does not establish
that the policy works reliably across search seeds. It also does not show a necessary low-fitness stepping stone,
memory, prediction or a new algorithm. A second independent matched pair with the unchanged policy is the most
direct next experiment. A longer ordinary continuation after early body contraction remains a separate candidate.

**Integrity and resources.** The shared initial population and all first 256 candidate genomes match bytewise,
as do their first base-fitness values. Independent recorded-operation replay reproduces both complete final
populations: 896 sexual offspring and 1,854 point additions including initialization per arm, no structural
mutation, eight active genes throughout. All 24 ranking calls and the six protected IDs reproduce exactly.
All six protected offspring lay outside both the ordinary initial top64 and their treatment shortlist's ordinary
pooled top32. This describes actual retention, not the unobserved full ordinary counterfactual for later treatment
cohorts. The final generation contains no protected slots.

All **9,804 research plus six golden calls** complete in **862.767205 CPU-seconds** and **257.302628 wall seconds**.
Search consumes 720.896357 CPU-seconds; confirmation and cleanup consume 141.870848. The hard caps remain
5,400 total, 3,400 search and 2,000 confirmation reserve. All 1,536 retained confirmation ledgers have zero status.
Initial-search logs retain **12 control / 18 reserve guarded lives** with penalties; complete per-life native search
ledgers are not retained, so there is no all-search-health claim. All four process leaders and three owned groups
have exited; **208 released local / 35 production pins** are unchanged. No retry, resume, extension or paid compute.

The unchanged frozen reader, separate literal-ledger accountant and complete genetic/policy reanalysis agree on
all **219 paired vectors**. Raw accounting uses every confirmation life and includes all costs and penalties.
Numerical identities cover the six goldens and bind the external selection adapter in addition to production code.

**Post hoc lineage check.** The reserve winner has no genealogical descent from any of the six protected
children. Protected ID329 has descendants in three of the final 32 population members; the other five have none.
The changed selection can still redirect later breeding by displacing or reordering parents. These observations
rule out a protected-ancestor explanation for this particular winner, but do not identify which policy consequence
caused its behavioral advantage. They do not establish necessary stepping stones or retained functional alleles.

**Artifacts.** `results/exploratory_reserve_20261014/` preserves prospective preparation, raw confirmation,
both native populations and logs, exact readers, independent checks, terminal resource evidence and the four-panel
figure. Fixed endpoint IDs are control **870**, reserve **895**; raw genome hashes begin `4bf7a2b2…` / `3cc5a0db…`.
Protocol `0a9e5059…4c61be4`; budget `24dadeb2…8a76ce6`; summary `fc097ab9…132aa26`.
The prospective protocol was published at `e7246f2` before release. Historical failed source-test outputs remain
preserved alongside passing final reviews; none is rewritten as a success.

## 2026-10-15 — AI registered and prepared: independent repeat of the two-slot exploratory-reserve comparison

**Why repeat.** AH's reserve endpoint beat its matched ordinary-selection endpoint on fresh lives by
+0.556641 ± 0.110184 captures and +0.254917 ± 0.054269 F. Its capture gain over the start was unresolved.
One search pair does not establish policy reliability, and the winner has no protected-offspring ancestry.
AI repeats the same comparison with an independent search seed and fresh confirmation, rather than changing the
policy after observing that result. The choice to run this replication is explicitly motivated by AH's outcome.

**Frozen scientific scope.** Use the same AE L92 row31 founder, exact ABI3 persistent-target world, unchanged
fitness and prices, ordinary genetic operators, 32 parents and 224 offspring. Both arms share one new initial
population consisting of that founder and 31 recorded ordinary two-point mutants. They also share the native
life schedule and first 256 candidates. In reserve generations 0–2, the unchanged stateless lottery protects two
distinct fresh offspring through the 64-member recheck and 32-member breeder selection. All remaining places
follow ordinary F ranking; generation 3 is ordinary in both arms. The exact lottery domain remains
`cell-dev:AH:reserve:v1`: a new study label does not change the policy. No capture, morphology, genotype or novelty
score enters the lottery. Later populations may diverge.

Both final generation4 rank-zero endpoints are fixed together before confirmation. Evaluate the three roles
`AE_L92`, `AI_control`, `AI_reserve` on 512 fresh shared lives, retaining any duplicate role. The primary contrast
is reserve minus control captures, with F, full income/cost/penalty decomposition and both endpoint-minus-start
contrasts. All 219 paired vectors are retained. Describe AI separately from AH; do not treat 512 lives as 512
independent searches or pool life-level precision into a policy-reliability claim. Two pairs on one deliberately
chosen background still leave broad evolutionary reliability, memory and algorithmic sophistication unestablished.

**Fixed accounting and limits.** Each arm uses 4,096 selection, 32 periodic validation and six small final
diagnostic lives: 4,134 native lives per arm, 8,268 total. Add 1,536 confirmation lives for **9,804 research calls**,
plus six startup numerical goldens for **9,810 calls**. Two search workers have two threads each; confirmation
uses one two-thread worker. The total cap is **5,400 CPU-seconds**, startup/search ceiling **3,400**, confirmation
reserve **2,000**; stop thresholds 5,390/3,390 leave cleanup room. There is no retry, resume, scope reduction,
endpoint replacement or extension. Historical cost projections use all 65 fixed AE L92 timing rows, not the
faster AH outcome; the hard runtime caps remain binding.

One-time preparation copied the fixed inputs and generated exactly one shared 32-row initialization with
62 recorded ordinary point additions. It ran no compiler or life. Actual-input review, exact bound-reader review and prospective public
publication precede a separate root runtime release. AH's clean terminal resource state is a prerequisite;
its positive relative result is the openly stated reason for this follow-up. Prices, task F, organism rules,
production code and ABI stay fixed. No paid compute or larger family is authorized.

The audited native seed is **53227**, with 64 native life IDs intentionally shared across the arms. Confirmation
uses **52,360,000–52,360,511** in fresh block 136; the 576 combined unique IDs exclude prior allocations and
standard golden seed 11. All 44 prior process identities, 31 groups and fifteen terminal budgets are clear.
Protocol `0dc385199dc871a86f7a31a62c393b2c160f0cbae018ceece3ec8f51bb6dff00` pins **103 local / 35 production files**. Five focused producer and five reader checks
pass; complete-module comparisons preserve AH's scientific logic and reuse its substantive tests. Actual-input,
bound-reader and prospective-publication checks precede runtime release. The initial shared-path collision
between two administrative helper-review receipts was resolved by recovering the original bytes exactly;
both reviews and their recovery record are preserved, with no scientific source change or engine execution.

## 2026-10-15 — AI complete: the reserve advantage reverses; ordinary selection improves captures

The unchanged exploratory-reserve comparison was repeated with an independent search seed from the same
deliberately chosen AE L92 founder. Both four-generation searches shared their initialization and life schedule;
the final endpoints were fixed before confirmation. The world, task fitness, prices, genetic operators and local
asynchronous organism rules stayed fixed.

**Fresh confirmation, 512 paired lives; mean ± paired SE:**

| Fixed contrast | Captures per life | Fitness F | Capture-income contribution to F | Ordinary cost saving in F |
|---|---:|---:|---:|---:|
| Reserve − control (primary) | **−0.513672 ± 0.119015** | **−0.274444 ± 0.057401** | −0.250816 ± 0.058113 | −0.023628 ± 0.007421 |
| Control − start | **+0.695313 ± 0.127998** | +1.477951 ± 0.063427 | +0.339508 ± 0.062499 | +1.138443 ± 0.012923 |
| Reserve − start | +0.181641 ± 0.126883 | +1.203507 ± 0.063512 | +0.088692 ± 0.061955 | +1.114815 ± 0.012963 |

Reserve loses to control in both captures and F by the fixed three-SE criterion. Its lower capture income and
slightly higher ordinary costs both contribute. This reverses AH's relative advantage (+0.556641 ± 0.110184
captures): the two independent search pairs give **no consistent reserve-policy advantage**. They share one
chosen starting genome; evaluation lives are not independent evolutionary repetitions, and two pairs cannot
establish broad policy reliability. No pooled life-level policy test is reported.

Ordinary control improves captures over its own start beyond three SE. Mean captures rise
**4.027344 → 4.722656**, while reserve reaches **4.208984**. Mean F changes **−0.750661 → +0.727290 / +0.452846**
for start → control / reserve. Both fitness gains still come mainly from economy. Mean terminal cells shrink
**108.775391 → 64.400391 / 63.857422**, and mean spikes fall **2512.343750 → 972.757813 / 1074.375000**.
These measurements establish a modest ordinary capture improvement, without identifying prediction, memory
or a richer algorithm. A longer ordinary continuation is the next design candidate; no new run is released here.

**Integrity and resources.** Both shared initial populations and their first 256 candidate genomes/base fitness
match exactly. Recorded-operation replay reconstructs all 896 sexual offspring and 1,854 point additions per
arm, including initialization, plus all 24 ranking calls and both final populations. There is no structural mutation;
eight genes remain active. Five of the six protected children were outside their ordinary initial top64;
ID656 was already inside. All six were outside their treatment shortlist's ordinary pooled top32. This describes
actual retention, not a full counterfactual ordinary search or a necessary stepping stone. No AI ancestry claim
is made.

All **9,804 research plus six golden calls** complete in **1,068.361098 CPU-seconds** and **305.364878 wall seconds**.
Search uses 923.782077 CPU-seconds; confirmation and cleanup use 144.579021, within unchanged caps of 5,400
total and 3,400 search, with 2,000 reserved for confirmation. All 1,536 confirmation ledgers have zero status and
no guard/extinction contribution. Native initial-search logs retain **three guarded lives in each arm**, with
penalties; full per-life native ledgers are not retained. Four process leaders and three groups have exited;
**210 local / 35 production release pins** are unchanged. There was no retry, resume, extension or paid compute.

The frozen reader, independent literal-ledger accountant and full genetic/policy replay agree on all
**219 paired vectors**; independently regenerated summary and vector archive bytes match exactly. Numerical
identity checks include all six goldens and the external selection adapter. Prospective publication was commit
`cae942b`; original preparation and failed administrative/source-check attempts remain preserved.

**Artifacts.** `results/exploratory_reserve_replication_20261014/` contains the complete prospective and terminal
record, raw confirmation, populations, readers, independent checks, resource receipts and a four-panel figure.
Fixed endpoint IDs are control **668**, reserve **887**; raw genotype hashes begin `657326d5…` / `7944ce86…`.
Protocol `0dc38519…b6dff00`; budget `e8e7f316…4e098d`; summary `a070f5b9…c3f2f9`.

## 2026-10-15 — Watchable AI comparison, with exact JavaScript replay and a bounded browser check

`results/atlas/exploratory_reserve_replication.html` shows all three fixed AI roles side by side: AE L92 start,
ordinary control and exploratory reserve. It starts paused and retains every aggregate contrast above the
animation. The seed was fixed in advance to the first confirmation life, 52,360,000. It shows 9 / 8 / 5 captures
for start / control / reserve, despite control's positive 512-life gain over start. This illustrates variability;
the seed was not changed to make the outcome look better. Later target placements depend on each body's actions.

The unchanged JavaScript engine reproduces all **171 retained C ledger values** in three full engineering
replays, with zero statuses, in **5.198112 child CPU-seconds**. Mock UI tests pass 84 assertions at two widths.
A separate guarded Firefox screenshot renders the paused page with exactly three initializations at time zero,
zero simulation advances and all aggregate rows/panels present. Firefox did not exit before its cleanup threshold;
the monitor terminated it at **43.048262 wall / 2.608106 child CPU-seconds** and verified group clearance.
That attempt remains `incomplete_no_retry`; the screenshot checks layout, without establishing browser playback
or long-run numerical parity. No completed life occurred in the browser diagnostic, and no new research life,
C/Python simulation, genotype, kernel build, price, world or organism-rule change was introduced.

`results/ai_watchable_20261014/` preserves the export, full truth, Node and mock checks, original source/build,
guarded screenshot, browser failure/cleanup, root review and publication manifest. Only the final viewer footer
changes from the original build to state the browser outcome accurately. Runtime profile/cache files stay under
`outputs/`. Existing LGPL math-port notices remain intact. Artifact hashes and the standalone viewer are pinned.

The next source-only candidate, AJ, keeps the full AI-control final population for a twelve-generation ordinary
continuation in the same world. This is an outcome-informed choice to build on confirmed captures, not a claim
that the population is generally superior or that contraction has ended. Registration and a bounded launch
report remain ahead; no AJ inputs, genetic draws, builds or lives are released by this viewer milestone.

## 2026-10-15 — Shared mutation panels: transferable economy, no confirmed broad capture improvement

A NumPy-only retrospective joins all 130 exact genotypes from the two retained Y panels across blink, dim flash,
persistent target and dark flash: 520 screen rows of 32 lives plus 24 retained confirmation rows of 512 lives.
Within-world mutant-parent pairing is preserved; different worlds have different seeds and are not elementwise
paired. All rows, physical costs and healthy statuses reconcile. Root independently reran the analyzer and all
8 output files match bytewise, including 12,552 paired arrays. No new life, build or genetic draw occurred.

Only L92 rows 3, 41, 59 have positive capture estimates in all four screens; every individual effect remains within
three SE and none has 512-life confirmation. D90 row54 has confirmed fitness gains across all four worlds chiefly
from economy: it loses 2.100 ± 0.171 captures in blink and 1.459 ± 0.181 in dim flash. Existing evidence therefore
establishes transferable cost saving, without a confirmed broad capture improvement. This post hoc inspection
uses selection data from 128 mutants and is not a held-out generalization test. Full evidence and limitations:
`results/cross_world_reuse_20261015/`.

## 2026-10-15 — AK registered and prepared: does a continuing lineage retain and extend capability?

Following the user's emphasis on cumulative capability, this diagnostic freezes three actual stages of one lineage:
L92 ancestral POOL endpoint, its ordinary mutant AE_L92 (Y row31), and the AI ordinary-control descendant.
All three unchanged genomes receive 256 shared fresh lives in each of four worlds: exact ancestral POOL,
current persistent target, persistent with mean turn time 100 instead of 200, and persistent with irregular
mean 80 on / 5 off visibility and zero residual cue. Dark intervals have no upper bound. All physical prices,
development, local asynchronous rules and ABI3/4 implementations remain unchanged.

The primary contrasts are AI_control minus L92 captures in POOL and AI_control minus AE_L92 captures in
persistent. The reader also retains all within-world pairs, environment contrasts, interactions, full fitness
and cost decomposition, guards and extinction. A conventional 10% mean capture-loss tolerance uses the lower
three-SE bound of the paired new−0.9×reference vector; it is diagnostic, never a selection gate. Unresolved loss
does not establish retention. All 2,254 paired vectors are retained. POOL changes several physical parameters;
only the two new edges isolate changes from persistent. Fresh-seed transfer in this chosen lineage does not
establish broad generalization or evolutionary reliability; every revealed case becomes development data.

The exact scope is 3,072 research plus four existing ABI3/4 truth lives, one two-thread worker, and hard caps of
2,400 CPU-seconds and 1,800 wall seconds, including startup and cleanup. Historical timing suggests about 1,121
CPU-seconds with padding; the hard caps bind. There is no mutation, endpoint replacement, retry, resume or scope
extension. Block 138 reserves 52,380,000–52,389,999; actual lives use 52,380,000–52,380,255. The fresh-ID audit
reopened 242 distinct retained seed payloads and found no overlap. AJ's candidate block 137 remains unregistered.

Thirty-seven pure reader checks and seven synthetic monitor checks pass; independent source review verifies
exact ancestry, physics, prices, ABI packing, startup identities and original production scoring. One-time
preparation copies inputs without a compiler or life. Actual-input review and prospective publication precede
separate root runtime release. No new organism behavior, global channel, clock, paid compute or responsive world.
Protocol: `0b41f8f98d00536c2333389245c8866d568300c6151316801794200b5e5b56b3`.
Evidence: `results/retention_frontier_20261015/`.

## 2026-10-15 — AK complete: nearby transfer, but substantial ancestral capability loss

The three fixed stages of the L92 → AE_L92 → AI-control lineage were evaluated unchanged on 256 fresh shared
seeds in each of four worlds. The central result is a real trade-off: the latest genome improves persistent-target
captures but retains only **61.4% of its ancestor's mean captures in the ancestral POOL task**.

| Fixed contrast | Captures per life, mean ± paired SE | Fitness F | Ordinary cost saving in F |
|---|---:|---:|---:|
| AI − L92 in ancestral POOL (primary) | **−7.328125 ± 0.351782** | −2.028231 ± 0.166636 | +1.549955 ± 0.018839 |
| AI − AE in persistent (primary) | **+0.679688 ± 0.175635** | +1.468414 ± 0.088533 | +1.136536 ± 0.018658 |
| AI − AE with more frequent turns | +0.746094 ± 0.186496 | +1.505514 ± 0.092003 | +1.141211 ± 0.018460 |
| AI − AE with brief irregular darkness | +0.886719 ± 0.155560 | +1.542000 ± 0.076836 | +1.109032 ± 0.018619 |

Mean POOL captures fall **18.988 → 17.523 → 11.660**, while persistent captures rise **3.406 → 3.660 → 4.340**.
The first mutant already loses 1.464844 ± 0.348044 ancestral captures; the later AI step loses another
5.863281 ± 0.323560. The conventional 90%-retention diagnostic fails clearly in POOL: its paired margin is
−5.429297 ± 0.328948. Persistent retention relative to AE passes with a resolved actual capture gain.

Economy is substantial in every world. Mean terminal POOL cells fall 116.133 → 97.961 → 58.770; persistent
cells fall 129.586 → 108.414 → 64.270. About 77% of the latest persistent fitness gain comes from cost saving.
In POOL, lost capture income exceeds those savings and fitness declines too. These whole-genome, whole-life
comparisons do not establish body size as the causal mechanism.

AI's advantage over AE transfers to both nearby environments, but their gain-over-persistent interactions are
unresolved: +0.066406 ± 0.226664 captures for faster turns and +0.207031 ± 0.165222 for darkness. Thus there is
nearby transfer without demonstrated improved perturbation robustness, memory, prediction or a richer algorithm.
POOL changes several physical settings; all revealed contexts become development data. This deliberately chosen
lineage is not an evolutionary replication, and fresh seeds are not held-out tasks.

All **3,072 research plus four existing truth lives** complete in **448.458997 CPU / 193.319466 wall seconds**,
within 2,400 / 1,800 caps. Every research status is zero, with no guard/extinction contribution. ABI3 startup
identity and ABI4 full/fast renewal truth agree. Both process leaders and the owned worker group exited in the
original PID namespace. The unchanged reader and separate literal-index accountant agree exactly on all
**2,254 paired vectors**, and a separate reader run reproduces summary/vector archive bytes. A helper's initial
output-directory collision is retained as a failure before raw reading; the unchanged helper succeeded in a fresh
subdirectory. No scientific source change, retry, extension or paid compute occurred.

The result changes the next priority: address retained capability before another harder-edge-only continuation.
Native held-out reports observe forgetting without affecting reproduction. A small two-context selection
comparison is being designed; no new search or outstanding family-fitness decision is released here. AJ stays held.

`results/retention_frontier_20261015/` preserves all raw rows, source/input pins, original genomes, startup truth,
resource receipts, independent checks and a three-panel figure. Prospective publication: `08eaa5b`.
Protocol `0b41f8f9…5b56b3`; summary `313ed555…979dc3`; budget `9492e7f1…42b8d1d`.

## 2026-10-15 — Watchable retention trade-off; limited two-context selection proposal awaits a decision

`results/atlas/retention_frontier.html` shows all three fixed AK lineage stages in ancestral POOL and persistent
targets, with world buttons and both worlds’ aggregate means and all paired lineage contrasts always visible.
It starts paused and uses the first AK seed, 52,380,000, for both worlds. Illustrative captures are **17 / 17 / 13**
in POOL and **2 / 5 / 5** in persistent. The examples were retained without seed shopping; later target placements
depend on each body's actions. The 256-life results, not this single seed, establish the trade-off.

The unchanged JavaScript engine reproduces all **342 C ledger values** from six existing lives byte for byte,
with every status zero. Bounded validation uses **9.802703 child CPU / 8.329846 wall seconds**, with original-host
process-group clearance. No new C/Python life, genetic draw or research observation is added. Mock controls pass
106 assertions at two widths; no real browser was run. Exact source/export pins, raw truth, first-attempt logs,
reviews and the unchanged LGPL engine are archived in `results/ak_watchable_20261015/`. Root corrected reversed
target-speed wording before export: POOL speed 0.1/mean-turn 20; persistent speed 0.3/mean-turn 200. Scientific world
bytes and scoring were unchanged. The standalone viewer and all archive bytes are pinned.

The reviewed proposal in `docs/TWO_CONTEXT_RETENTION_PILOT.md` compares one ordinary four-generation persistent
continuation with an equal-life-budget, fixed 50/50 POOL/persistent branch, starting from all 32 AI-control survivors.
It tests both fixed endpoints and AI-start on fresh lives in three development contexts plus the previously
unmeasured combined turn100+blink80_5 context. Captures, retention and economy remain separate. A positive relative
POOL effect alone could reflect control deterioration; actual recovery requires improvement over the start too.
Its fixed 10% persistent-retention tolerance is diagnostic, not a lossless-retention guarantee or a new fitness term.

The limited approval question is pending because HANDOFF section 5 leaves raw-F family fitness undecided. Scope,
if approved: **13,396 total calls**, one two-thread worker, hard **5,400 CPU-seconds**, with 3,600 for search/startup
and 1,800 reserved for confirmation. No new seeds, inputs, selection adapter or run are released by this proposal;
AJ remains held. `results/retention_selection_proposal_20261015/` preserves the draft, contract, conservative
cost projection and independent design review. The larger family, in-life rule changes and paid compute remain
outside the requested decision.

## 2026-10-15 — AL registered: selection for two tasks along one continuing lineage

The user authorized continuing on our judgment, then explicitly permitted safe local experiments. AL compares
four generations of persistent-only selection against a fixed 50/50 POOL/persistent mixture. Both import all 32
ordered AI-control survivors, retain duplicate genomes, reset scores/RNG state and use native 32+224 breeding,
four initial lives and four top 64 recheck lives. Native scoring, prices, genetics and local asynchronous cells
stay unchanged. No context label or population-responsive world is introduced. Both final rank 0 endpoints are
fixed before confirmation, and their first 224 offspring must reconstruct identically from recorded operations.

The primary is mixture-minus-control ancestral POOL captures. Actual recovery also requires a resolved
mixture-minus-start POOL capture gain. Persistent retention uses a conventional 10% tolerance, with the lower
three-SE bound of endpoint−0.9×start above zero. This permits some loss; unresolved loss is not retention.
Strict simultaneous improvement requires resolved capture gains over AI start in both training worlds. Full
fitness and physical costs remain separate so economy cannot masquerade as richer behavior.

AI start and both endpoints receive 256 fresh shared lives in each of POOL, persistent, blink80_5 and the new
combined turn100+blink80_5 case. The combination stays outside selection and endpoint choice. One nearby
transfer case and one paired evolutionary realization do not establish broad generalization or policy reliability.
No fresh original L92 reference is included, so this cannot establish full ancestral restoration.

Scope: 13,388 research plus 8 existing startup lives, 13,396 total. Block 139 reserves 52,390,000–52,399,999;
confirmation uses its first 256 IDs. Both searches intentionally share native seed 53229 and 68 derived IDs.
AJ 53228/block 137 remain held. The audit finds no collision in 242 distinct reopened historical seed payloads.
Caps are 5,400 total CPU-seconds, 3,600 search and 1,800 confirmation, 3,600 wall seconds, one two-thread worker.
Memory safeguards enforce 8 GiB address space per worker, stop at 4 GiB owned aggregate RSS or below 4 GiB host
available memory. There is no paid compute, retry, resume, scope reduction or cap extension.

Focused checks pass: 23 loader/selection/completion tests, 12 recorded-genetics tests, 14 reader tests and 10
monitor/lifecycle tests. All 32 actual inputs match the prior checkpoint bytewise and preparation consumes no
scientific genetic draws, compiler calls or lives. Prior 51 process identities and 36 groups are clear in their
original host namespace. Full raw-genome replay follows the run; ordinary logs cannot reconstruct omitted
parent base scores or exact tie permutations, so ranking claims remain limited to recorded evidence.

Protocol: `25575f9ef690d00741fea0c62570d15aeb526d66a13a42025a91c5cd2fad19bf`.
Prospective evidence: `results/retention_selection_20261015/`; exact scope: `docs/TWO_CONTEXT_RETENTION_PILOT.md`.
Publication and final actual-input review precede root runtime release. No AL research life has run at registration.

## 2026-10-15 — AL complete: ancestral capture recovery at extra cost; persistent retention unresolved

Fixed two-task selection improves POOL captures over its AI start by **3.683594 ± 0.298366 per life**. Mean
captures rise **11.324 → 15.008**, while the persistent-only branch falls to **4.504**. The primary mixture-minus-
control effect is **10.503906 ± 0.296786**; the separate own-start gain shows actual partial recovery beyond
control deterioration. This experiment includes no fresh original L92 reference and does not establish full
ancestral restoration.

Persistent captures are **4.765625 → 4.687500** for start → mixture, a change of **−0.078125 ± 0.199511**.
The 90% retention margin is **+0.398438 ± 0.189813**, lower three-SE bound **−0.171000**: retention remains
unresolved despite the 98.36% mean ratio. Mixture-minus-start captures also remain unresolved in brief darkness
(−0.101562 ± 0.183552) and the untrained turn-plus-darkness combination (−0.011719 ± 0.162366). There is no
strict simultaneous gain, memory, new algorithm or broad generalization claim. All revealed cases become
development data.

Mixture POOL F rises **1.203470 ± 0.142712**, from **1.798630** additional capture income despite **0.595160**
extra ordinary cost. Persistent F falls **0.687747 ± 0.096043**, chiefly because ordinary costs rise **0.649600**.
Mean terminal cells grow from about **59 to 83** in POOL and **65 to 90** in persistent. More cells, spikes or
hidden cells do not establish richer circuitry. Whole-genome development differences prevent a size-causality claim.

The persistent-only endpoint loses **2.636719 ± 0.160385 persistent captures** and **0.331624 ± 0.076098 F**
despite cost saving. Its poor result therefore cannot be explained solely as optimizing economy successfully;
sparse selection and evolutionary noise remain plausible contributors. This is one paired four-generation search.

All **13,388 research + eight startup calls** complete in **1,098.051813 CPU /450.990839 wall seconds**, with
peak sampled owned RSS **324,759,552 bytes** (about 310 MiB). Four process identities and three groups are clear.
All 3,072 confirmation statuses are zero; four control and two mixture initial guarded search lives retain their
penalties. Each arm's 896 offspring, 1,792 point additions and all 32 final genomes/origins replay bytewise.
Logged pooled selection passes; omitted unsuccessful-parent scores and tie permutations limit initial-ranking
verification. The frozen reader and independent literal accountant agree exactly on all **2,254 vectors** and
independent summary/vector bytes match. No retry, extension or paid compute.

Evidence and figure: `results/retention_selection_20261015/REPORT.md`. Prospective commits `da2a01f`, `6ad0266`;
protocol `25575f9e…ad19bf`; summary `29e46492…d5555`; budget `e7602ddc…69d00`.

## 2026-10-15 — Cost incentives and watchable AL outcomes

The user explicitly asks whether cost penalties encourage the intended capabilities. Post hoc analysis of AL's
unchanged saved trajectories shows maintenance is **79.36%** of the mixture's persistent ordinary cost, while
spikes plus messages are **0.72%**. Mixture beats the small control by **2.558594 ± 0.160285 captures** but loses
**0.356124 ± 0.075793 F** under current prices. Halving all ordinary charges changes that fixed-trajectory F
contrast to **+0.446595 ± 0.076461**; halving living cost alone gives **+0.297835 ± 0.075940**. Reducing spike/message
charges to one quarter barely changes it (**−0.345725 ± 0.075851**).

This is ranking sensitivity, not an optimal price or a prediction of evolution. Mixture's persistent point-estimate
F still trails AI start under every requested nonnegative multiplier because its capture change is unresolved
and its costs are higher. All four contexts, original charges, 12 contrasts and 240 absolute/paired vectors are
retained. Root independently reconstructs every vector from raw cost/live-time/spike/contact columns, agreeing
within 5.31e-13. No new life, genetic draw, compiler call or production-price change. Evidence:
`results/cost_incentives_20261015/al_posthoc/`.

`results/atlas/retention_selection.html` shows the three fixed AL roles in POOL and persistent, starts paused,
and keeps both full 256-life aggregate comparisons visible. First-seed illustrations at52,390,000 give captures
**12 /5 /13** in POOL and **2 /5 /2** in persistent; the latter deliberately differs from the aggregate ordering.
All six existing JS lives match **342 C ledger values** bitwise, using **8.367305 child CPU /6.976489 wall seconds**
and **97,071,104 bytes** peak RSS. Host cleanup passes; 106 mock UI checks pass and no real browser was run.
No new C/Python research lives. Engine and LGPL notice are preserved in `results/al_watchable_20261015/`.

AM is being prepared as a local incentive comparison from all 32 AL-mixture survivors: current capture value500
versus2,000 during fixed two-task selection, with all penalties unchanged and more evaluation lives in both arms.
Fresh confirmation uses common original prices and includes both earlier AI and AL starts. Report captures,
retention, full physical cost and click accuracy; extra bodies or blind clicks are plausible outcomes, not algorithmic
progress. No AM run is launched by this milestone. Safe local experimentation is authorized; report if meaningful
progress appears to require substantially more resources.

## 2026-10-15 — AM registered: can stronger capture incentives improve cumulative capability?

From all32 ordered AL-mixture survivors, two four-generation native32+224 branches use fixed equal POOL and
persistent selection. Both increase evaluation to8 initial plus8 recheck lives; only generation capture value
differs:500 versus2,000. Physical penalties, local asynchronous cells and all organism dynamics stay unchanged.
Native diagnostics and fresh confirmation use original500. This tests one incentive contrast, not an optimal
price; cross-study differences cannot isolate evaluation precision. Blind clicking and body growth remain
alternatives to richer computation.

Both fixed endpoints, AL start and earlier AI start receive512 shared fresh lives in all four known AL contexts.
Co-primary high-minus-current capture effects are separate in POOL and persistent; joint benefit requires both
lower three-SE bounds above zero. Own-start gains,90% retention margins, physical costs, click accuracy and
all54 contrast groups remain explicit. Every context is development data, so no held-out-world claim is available.

Scope:28,748 research+8 startup calls, native53230 and confirmation block140,52,400,000–52,400,511.
Hard caps:10,800 totalCPU seconds,7,200search/3,600confirmation,5,400wall;one2thread worker,4GiB ownedRSS,
8GiBaddress space,4GiBhost headroom. No automatic retry/extension or paid compute. Full source/config/world
and seed reviews pass; preparation imports all32 rows without a genetic draw, build or life. Prior56 identities
and40groups are clear. Actual-input review and prospective publication precede root runtime release.

Protocol `9210e218d92d912f8b63822980de7fab868ad8904417d0f438a55e2b42922294`.
Prospective evidence: `results/capture_value_selection_20261015/`.

## 2026-10-15 — AM complete: cumulative capture gains; higher reward has no joint task advantage

The original-price continuation improves captures over its AL start in all four known contexts. POOL rises
15.417969 →16.750000 (**+1.332031 ±0.229478**) and persistent4.458984 →5.324219
(**+0.865234 ±0.135134**). Original-price F improves **+0.504278 ±0.109905 /+0.245150 ±0.066728**
respectively despite extra ordinary costs0.146128/0.177328F. Terminal cells increase about82→88 and90→96.
Captures also improve in brief darkness **+0.443359 ±0.128503** and turns-plus-darkness **+0.695312 ±0.127998**.
All four capture gains clear the fixed lower-three-SE criterion. No memory or richer algorithm is established.

Higher selection reward2,000 versus500 produces co-primary high-minus-current capture effects
**+1.568359 ±0.241853 POOL /−0.433594 ±0.151231 persistent**: no joint advantage. The latter loss narrowly
remains unresolved at three SE. Higher reward increases bodies to106/118 cells and misses to37.58/39.38 per
life; aggregate capture/click fractions fall from43.29%→32.77% and15.80%→11.05% versus current value.
At common original prices, its persistent F is **0.799722 ±0.075178 lower** than current value. More hidden
cells (persistent7.97 versus1.09) do not establish useful circuitry. No optimal-price or general policy claim.

Both endpoints pass90% capture retention against AL in both training worlds and AI in persistent; both improve
AL captures in both training worlds. The high-value persistent gain only barely clears three SE, lower bound
+0.001540. Fresh AL-versus-AI persistent90% retention now passes: margin **+0.408984 ±0.118987**, lower bound
+0.052024; this does not imply lossless retention. Current-value persistent F still trails AI by0.421625±0.065424.
Both arms used more evaluation lives than AL, so this study does not isolate precision from further evolution.

A useful weakness remains: current-value's capture gain is **0.421875 ±0.132148 smaller under brief darkness
than persistent**, a resolved negative interaction. Dark-capture gains remain unresolved. Improved transfer
performance therefore does not establish better occlusion robustness. All four cases are development data.

All28,748research+8startup calls finish in **5,112.441715 CPU /2,065.705032 wall seconds**; peak ownedRSS
326,066,176bytes. Four identities/three groups are clear. All8,192 confirmation statuses are zero. All offspring,
final genomes/origins and logged pooled selection reconstruct; original guard penalties remain included. The
independent literal accountant matches all4,064 vectors exactly, and separate frozen-reader output is byte-identical.
Offline genetics used another4.043801CPU seconds with no simulations. No retry, extension or rented compute.

The user's new guideline is to finish each experiment and reconsider the highest-value next step, avoiding a
narrow tuning track. After comparing richer tasks, longer search, causal probes, operators and reward adjustments,
choose AN: one eight-generation continuation of the current-price population, with longer irregular cue gaps
and both old tasks retained. It is source-only, unprepared and unregistered. Midpoint/final genomes will be fixed
before fresh confirmation; no automatic price sweep or mechanism gate. Exact decision: AM/discussion/ROOT_DECISION.md.

Report/figure/evidence: `results/capture_value_selection_20261015/REPORT.md`.
Prospective commits `bf431b6`, `16e46cd`; protocol9210e218…922294; summary00bdc977…6b2137; budget70242fe1…252604.

## 2026-10-15 — AN registered: acquire longer-gap performance and measure retained capability

After the complete AM result, choose one eight-generation continuation from all32 original-price AM survivors.
Keep ordinary prices500, with fixed2POOL/2persistent/4blink80_20 selection lives per8initial, repeated for8extra
recheck lives. Longer darkness changes meanoff5→20 at meanon80; all persistent physics and cell rules remain.
Generation4 and8rank0 genomes are fixed during uninterrupted selection, then tested alongside AM start on512
shared fresh lives in POOL,persistent,blink80_5,blink80_20,andturn100+blink80_20. Final is never replaced by midpoint.

Primary: final-minus-start captures in longer darkness. Both checkpoints receive separate90%old-task retention
diagnostics; physical costs, misses/click fractions, dark/bright captures and all39pairedcontrast groups remain.
The archive audit found no prior exact80/20setting; the faster-turn combination is untrained in AN and at most
a narrow transfer case. Neither dark captures nor one continuation establish memory, curriculum/depth superiority
or broad generalization. Reconsider competing directions after the complete result rather than queueing a sweep.

Prepared exact32rows with no genetic draw, compilation or life.54focusedchecks pass, both actual-input reviews
agree, prior60identities/43groups clear. Native53231 has180unique life IDs; confirmation52,410,000–52,410,511
is in block141. Scope20,534search+7,680confirmationresearch+8startup=28,222calls. Hardcaps10,800CPUtotal,
7,200search/3,600confirmation,5,400wall;one2threadworker,4GiBownedRSS,8GiBAS,4GiBhostheadroom. No retry,
extension or paid compute. Prospective publication precedes runtime release.

Protocol`ca277b17294bbce52a4fd6bde77e5847b6b5230c00d285ba8492538f7508b26b`.
Evidence:`results/occlusion_acquisition_20261015/`; source lineage from completed AM milestone`2b346af`.
## 2026-10-15 — AN complete: longer-gap acquisition, followed by economy and an older-task tradeoff

Longer-gap captures improve3.527344→3.988281 (**+0.460938 ±0.110891**, lower3SE+0.128266), with narrow
untrained turns-plus-longer-gap transfer **+0.630859 ±0.120726**. Brief-gap gain is+0.453125±0.133757;
persistent gain+0.353516±0.143199 remains unresolved. FinalPOOLcaptures fall **1.341797 ±0.230936**.
Generation4 already gains0.425781±0.122610targetcaptures and passes both90%old-task retention diagnostics.
Generation8 retains92.0%POOL in the point estimate, but90%retention is unresolved: margin+0.337500±0.220262,
lower3SE−0.323287. Persistent retention passes. Unresolved retention is not established failure below90%.

From4→8, longer-gap captures change only **+0.035156 ±0.120157**, while POOL loses **1.125000 ±0.234506**.
Longer-gap F improves0.237060±0.060541, including0.219894ordinary cost savings. Bodies shrink (persistent
96.92→91.74→81.16cells), with fewer misses than start. Longer-gap aggregate capture/click fraction rises
14.12%→19.01%→18.15%; counts remain visible. Final longer-gap dark-capture gain **+0.013672±0.020774** and
its persistent-relative capture interaction **+0.107422±0.153306** are unresolved. Almost all capture gain is
in bright periods. No memory, richer algorithm, broad generalization or plateau is established.

All28,214research+8startupcalls complete in **3679.509834CPU/1484.136535wall**, peak312.824219MiB.
All7680confirmationstatuses0; initialguards[0,0,0,8,0,6,0,0] retain penalties. Threeidentities/twogroups clear.
All1792offspring/3584mutations andfinal32genomes/origins replay, including independently verified midpoint32rows
and logprefix. All2933literal pairedvectors match exactly; separate frozen-reader bytes reproduce;15accuracy
ratios reconcile. Nativeaudit adds4.886713CPU without simulations. Missing unsuccessful-parent base scores and
tie permutations limit initial-ranking proof. A pre-release wrong-status-label wrapper failed before any
attempt/build/life; a separate accuracy helper's three descriptive keys were corrected with both versions retained.
No scientific change, research retry, scope extension or rented compute.

The user says promising strategies may deserve more generations or evaluation rollouts. Choose AO after comparing
competing directions: two matched24generation continuations fromALL32ANfinal survivors, fixedknowncontexts and
prices, unchanged25/25/50 versus50/25/25 POOL/persistent/blink20 allocation. Both get more time; AMreference
remains the earlier retention anchor. AN's late tradeoff has estimated mixedF+0.107797±0.048847, unresolved at
three SE, so precision alone may still reward it. The paired uncertainty was added in the later cost reanalysis.
This is source-only/unreleased, with no automatic harder-task or price ladder.

Report/figure: `results/occlusion_acquisition_20261015/REPORT.md`. Viewer: `results/atlas/occlusion_acquisition.html`;
all6existingJS lives match345ledger values,108mockUIassertions, no real browser run. Illustrations use the fixed
first seed even though those particular lives look worse;512-life aggregates remain visible.
Prospectivecommit0a95793; protocolca277b17…08b26b; summary1ce6412d…c64512; budget29f26b5c…ac5365.

## 2026-10-15 — AO registered: more evolution with a direct retention-allocation comparison

Give all32 ordered ANfinal survivors24 more generations in each of two matched fresh searches. Both retain
ordinary prices500,8initial+8recheck lives, native32+224 breeding and unchanged local asynchronous cells.
The sole branch difference is fixed POOL/persistent/blink80_20 allocation:25/25/50 versus50/25/25. Only two
blink positions per8 becomePOOL; persistent and existingPOOLpositions retain their shared random-life IDs.
These are fresh full-population continuations with matchedRNG, not exact resumes of AN.

The user explicitly values letting promising strategies play out longer. AN's target capture acquisition motivates
more time; its later tradeoff has a positive mixedF estimate, unresolved at three SE, so greater precision alone
could reinforce old-task loss. This qualification comes from the later paired cost reanalysis.
Retain an unchanged-allocation branch and an olderAMreference. Fix each branch's generation8 and24rank0,
then measure allfour descendants plusANstart andAMreference in the five known ANworlds,512freshpaired lives
perrow. No outcome-based checkpoint replacement. Joint primary: balanced24 beatsunchanged24POOLcaptures
and retains90%of its longer-gap captures, each lower3SE>0; actualblinkdifference is reported evenifnegative.
Allown-start/older-reference retention, physicalcosts, click fractions and11967pairedvectors remain visible.
Allworlds aredevelopment-known; one matchedpair doesnotestablish optimalallocation, searchreliability,
causaldepthsuperiority, memory or broadgeneralization. See `discussion/ROOT_DECISION.md` in the archive.

Scope:2×61558searchresearch+15360confirmationresearch+12startup=**138488calls**. Native53232 supplies500unique
IDs deliberately shared acrossarms; block142 confirmation52,420,000–52,420,511 is fresh. Hardcaps28800CPUtotal,
24000search/4800confirmation,14400wall,one2threadworker,4GiBownedRSS,8GiBAS,4GiBhostheadroom. MeasuredANphase
scaling with1.5margin projects23230.450search/3295.046confirmationCPU and fits. Older generic pessimistic
projections37881.945/4883.709 do notfit and remain an explicit completionrisk if bodies/eventrates grow.
No retry, arm-dropping, scope shrinking, cap extension or paidcompute.

Preparation imports exact32rows with no build, life or scientificgeneticdraw.63focusedchecks pass, bothactual
inputreviews agree, prior64identities/46groups clear with18.9GBavailable. Prospectivepublication precedes release.
Protocol`2cfc3ac9a6d41e2d3c49e630a7bc611ff9737962175def3d1eb89e6d8de6d68d`.
Evidence:`results/retained_depth_20261015/`; completedANmilestone`4eff70d`.

## 2026-10-15 — AN cost reanalysis: maintenance favors the later economical phenotype

Reprice the retained AN start, generation 4 and generation 8 trajectories in the three training worlds,
preserving the 25%/25%/50% mixture and covariance across the 512 shared seeds. This post hoc analysis was
specified before reading any AO outcomes. It uses nine existing rows (4,608 lives) and runs no new simulation.

At original prices, generation 8 minus generation 4 has mixed F **+0.107797 ±0.048847 SE**, unresolved at
three SE, and mixed captures **−0.225098 ±0.098195**, also unresolved. Maintenance savings contribute
**+0.204059 F**, while capture income falls 0.109911 and missed-click charges rise 0.009332. Earlier wording
that called this a "true" mixed-F improvement was too strong; the report and current summaries now state
the paired uncertainty. The original AN report is retained in its report_history directory and Git history.

For these fixed trajectories, halving maintenance makes the mixed F contrast **+0.005768 ±0.048043**;
quartering it makes **−0.045247 ±0.047771**. The mean crossing is 0.471735 times the original charge.
Changing missed-click prices from 0.5 to 4 times has much less effect. Only doubling maintenance among
these comparisons gives a positive contrast exceeding three SE. These are descriptive price sensitivities,
not an optimal price, a confidently better generation-4 phenotype, or predictions of altered evolution.

The pinned kernel confirms both prices affect accounting without feeding back into cell dynamics.
Maintenance also scales guard and extinction charges; all nine retained rows have status zero.
Independent source/math review passes, and the published analyzer reproduces the summary byte-for-byte.
No production defaults, AO inputs, scientific source or run limits changed. At this cost-analysis milestone,
AO was continuing its fixed longer evolution comparison; its completed result and next priority follow below.

Note and figure: `results/an_cost_sensitivity_20261015/NOTE.md` and `price_sensitivity.png`.
Summary SHA `9fc29a1828ca452c21d9e2c141e9c6c2cb22dc1c823dfc0a801f01af4d036274`.

## 2026-10-15 — AO complete: late acquisition and a retention-allocation tradeoff

Both fixed 24-generation branches from all 32 ordered AN survivors complete with unchanged local cells,
original prices and 8+8 evaluation lives. The matched fresh searches differ only in fixed POOL/persistent/
longer-gap allocation: 25/25/50 versus 50/25/25. Six fixed genomes receive 512 shared fresh lives in each of
five development-known worlds. All estimates below are paired means ± SE; three-SE bounds are descriptive,
not simultaneous guarantees across the 11,967 vectors. This is one evolutionary pair, not 512 search replicates.

The unchanged branch adds acquisition after generation 8: generation 24 gains **+0.808594 ±0.138866 persistent**,
**+0.693359 ±0.136585 brief-gap** and **+0.445312 ±0.114106 longer-gap captures** over generation 8.
Longer-gap F rises 0.254071 ±0.055074, with only 0.036633 from ordinary cost savings. POOL change is unresolved
(+0.013672 ±0.197245). Final versus AN start gains **+0.902344 ±0.150742 persistent**, **+0.861328 ±0.141995
brief-gap**, **+0.539062 ±0.121137 longer-gap** and **+0.437500 ±0.126005 turns-plus-gap captures**, but loses
**2.283203 ±0.217140 POOL captures**. Its POOL retention is about 84.7% of AN and 76.0% of AM; both 90% margins
remain below zero at their upper three-SE bounds. More time was useful along this trajectory, without proving
a generally superior 24-generation policy or solving retention.

More-POOL generation 24 versus unchanged24 gains **+3.033203 ±0.215803 POOL captures**, but loses
**0.503906 ±0.119337 longer-gap captures**. Both absolute effects exceed three SE. Its explicit 90% longer-gap
margin is **−0.035742 ±0.112710**, spanning zero; the registered joint primary does not pass. This failure
does not establish a loss greater than 10%. More-POOL gains **+0.750000 ±0.216118 POOL captures** over AN start
and passes all five specified own-start/AM-reference retention diagnostics. Passing allows actual loss:
versus AM it loses **0.949219 ±0.219510 POOL captures**, despite 94.29% point retention.

From generation 8→24, more-POOL loses **1.500000 ±0.246892 POOL captures**, while longer-gap capture change
is unresolved (+0.017578 ±0.113541). Its longer-gap F gain 0.302484 ±0.056551 is chiefly ordinary savings
(0.293901); mean terminal cells fall 100.91→88.01. The fixed generation-24 endpoints remain primary.
Allocation changes both objective weighting and per-context sample counts; it does not isolate weighting
from precision or establish an optimal mixture. Body or hidden-cell counts do not identify a circuit mechanism.

Neither branch adds resolved dark captures over AN start: longer-gap differences are **−0.005859 ±0.021145**
(unchanged) and **−0.013672 ±0.021674** (more POOL). Most added captures occur in bright periods. No new memory,
prediction, broad held-out generalization, capacity ceiling or need for rented compute is established.

All **138,476 research +12 startup =138,488 calls** finish within the original limits in **24,128.826457 CPU /
9,719.899554 wall seconds**, peak owned memory 314.410156 MiB. All 15,360 confirmation statuses are zero;
native guarded evaluations retain their penalties. Four process identities and three worker groups are clear.
Native replay checks all 10,752 offspring and 21,504 mutations, both final 32-row populations and independent
midpoint reconstruction. Missing unsuccessful-parent base scores and exact tie permutations limit initial-ranking
proof. Independent literal accounting matches all 30 raw rows, 11,967 vectors and 30 accuracy rows exactly.
Separate corrected-reader replay reproduces summary and compressed arrays byte-for-byte. Native and raw audits
add 8.882293 and 5.016802 CPU seconds respectively, with no simulations, builds or scientific random draws.

The original frozen analyzer stopped before outcomes because a server restart reparented the surviving monitor.
Its PID/group/start time and worker ownership stayed exact. A separately reviewed reader permits only the recorded
parent change; all scientific functions and other checks remain unchanged. The original reader, failed output,
metadata diagnosis, host clearances and patch/equivalence evidence are retained. No scientific input rewrite,
research retry, scope reduction or cap extension occurred.

The user prioritized richer interaction before outcome inspection and authorized autonomous environment/ABI work
of this kind. Proceed with [ABI5 delayed shape matching](docs/ABI5_DELAYED_MATCH_PROPOSAL.md): sample, blank,
then a choice whose value depends on the earlier cue, with unchanged local asynchronous cells. Implementation
remains isolated; AO's original sources are preserved in its completed archive. Select the continuing population explicitly from
development evidence; measure earlier skills and fresh conditional choices, reserving separate generalization
cases. Perfect retention, price tuning and a complete circuit account are not prerequisites to this exploration.

Report and evidence: `results/retained_depth_20261015/REPORT.md`; viewer: `results/atlas/retained_depth.html`.
Working archive: `outputs/autonomous_retained_depth_20261015/`. Protocol2cfc3ac9…e6d68d;
summary73282b17…cf895; native auditb4697b95…4a8e; independent raw auditd148ad5e…c4d6e.


## 2026-10-15 — ABI5 integrated: delayed shape matching, with unchanged cell rules

The authorized extension adds sample→blank→choice trials: narrow/broad cues disappear before fresh opposed
choices appear, and the first hit pays according to the earlier sample. No cell-visible phase, class, reward,
shared clock, genome field or message is added. Explicit ABI5 appends seven world fields and twelve
class-specific choice counters; legacy caller defaults and shapes remain unchanged. Conditional scoring uses
correctness independently of physical slot, and all ports enforce per-class opportunity conservation.

The default regression suite passes **945 tests, 127 slow deselected**, including byte-identical three-plus-resume-
three versus six-generation ABI5 evolution. That run used140.40CPU seconds and peaked at593MiB. An independent
review then found missing defensive count reconciliation in C/JS; after fixing it,85affected tests, eight fresh-
directory C-full/C-fast/Python truth cases and JS full/stepped parity all pass. Prior valid truth outputs remain
identical. Legacy/visibility JS checks,64-bit trial hashing, viewer DOM smoke, lint and whitespace checks pass.
The full suite predates the defensive fix; final targeted checks bind exact source hashes. Original fixture,
lint and instrumentation failures are retained. No real-browser validation is claimed.

This is engineering evidence, not a new evolved algorithm or world admission. The fixed preview uses an existing
reflex fixture without choosing a favorable body or seed. Next prepare a bounded six-genome development baseline
and sensory-information instrument, keeping short-episode evidence distinct from repeated-task admission,
retaining old-task checks and reserving separate transfer cases. No delayed-matching selection has run.
Evidence: `results/abi5_delayed_match_20261015/README.md`.

## 2026-10-15 — Delayed-matching baseline prepared: all six continuing-lineage endpoints

Evaluate the six fixed AO comparison genomes on the new delayed-matching preset at T85 and T1024,
using 32 shared development seeds at each duration. Six predetermined full-log repeats inspect early
sensory-plane growth and verify C-full/C-fast agreement. The total is **390 calls**, with no evolution,
endpoint selection or replacement. Block143 is reserved for development; these cases cannot become
later confirmation or generalization data.

The one-thread, one-worker attempt is capped at **600 CPU seconds, 900 wall seconds and 2 GiB RSS**,
with 8 GiB address space and 4 GiB host-memory headroom. Every outcome is retained. Report both sample
classes, narrow/broad/no-choice counts, physical costs, guards and unfinished trials. Positive reward is
insufficient evidence of matching; sensory-plane occupancy alone does not show functional cue decoding.
This is a development diagnostic, not the 512-seed sensory-information admission test. No lives have
run at this prospective registration. Evidence: `results/delayed_match_baseline_20261015/`.

## 2026-10-15 — Delayed-matching baseline complete: pursuit transfers, conditional matching not demonstrated

All six fixed genomes reach targets in the richer environment, but their observed choices strongly favor
the broad shape regardless of the earlier sample. Across 32 shared T1024 development lives per genome,
**97.2–99.8% of completed choices are broad**. Correct narrow choices cover only **0.47–2.75%** of narrow-cue
opportunities, while correct broad choices cover **92.66–96.36%** of broad-cue opportunities. Near-half
overall correctness and some positive fitness therefore do not demonstrate conditional matching or memory.
Repeated trials belong to 32 life clusters, not hundreds of independent lives.

At T85, each life opens one opportunity: 17 narrow and 15 broad samples. Only 0–2 narrow choices are correct
per genome. All six predetermined full traces develop an off-center sensory-plane cell at t4.588794 and
have 13–14 such cells at t14, before the earliest sample disappearance. This establishes early physical
sensor positions in those traces, not functional receptor gain, cue decoding or stable exposure during motion.
The diagnostic selects no new champion and establishes neither world admission nor an evolutionary gradient.

All **390 calls** finish in **29.254298 CPU /29.605673 wall seconds**, peak owned memory 324.101562 MiB.
All statuses are zero; six full/fast ledger repeats match bitwise and all worker descendants are cleared.
Independent arithmetic reconciles all 390 rows, costs and class counts. Public reanalysis reproduces the
summary, CSV and generated report byte-for-byte. Preparation's native-CSV fidelity amendment preceded all
lives; original files remain archived. There is no retry, replacement, evolution or additional startup life.

Next measure the payoff of retained sample information while preserving current sensing and movement.
The external instrument's memory-erased and never-stored arms already match in engineering checks;
scientific development and confirmation remain pending. Earlier tasks remain retention checks, and this
entire baseline block 143 is development-only. Report: `results/delayed_match_baseline_20261015/TERMINAL_REPORT.md`.
Prospective commit 04613c9; protocol 35a4af4a…c4bf7; summary 90323020…1805e.

## 2026-10-15 — Delayed-matching information measurement prepared

The new T85 study measures what remembering the early shape pays at a fixed 56-cell footprint. An external
instrument uses only delivered receptor events, its own clock and its own commanded actions. It stores one
sample statistic; the ablation erases only that statistic, preserving current-choice sensing, steering and taps.
No controller is installed in the organism. All 40 engineering calls pass within 22.32 CPU seconds, including
the initial zero-life cache failure; three memory-erased/never-stored pairs match all ledgers, hashes and logs.
Source review documents the limits of the supplied-input tests and the fixed engineering parameter setting.

Scientific execution is **1,024 development +5,632 confirmation calls**: 12 reflex and 4 instrument settings
on 64 development seeds, then 11 fixed roles on 512 fresh paired lives. Roles include fixed narrow/broad preferences,
unchanged and development-selected reflexes, and four quieter/smaller controls. Every outcome is retained.
Blocks 144/145 are independently audited and disjoint from the completed baseline. Native physical costs,
both sample classes, coverage, wrong choices and unfinished trials accompany paired fitness contrasts.
The current harness supplies whole-life reflex counters; reflex first-trial outcomes and actual capture times
are explicitly unmeasured. Instrument first-opportunity and sample-calibration readouts remain available.

Including engineering, the maximum is **6,696 calls**, **3,600 cumulative CPU /5,400 wall seconds**,
one worker/thread, 4 GiB RSS, 8 GiB address space and 4 GiB host-memory reserve. Measured engineering, seed audit
and preparation use are deducted before the scientific worker starts; development must preserve 2,400 CPU
seconds for confirmation/cleanup. No automatic retry, reduced confirmation panel or additional tuning occurs.
The user has been told this budget. No scientific life has run at prospective publication.

The original section 0.4 information, retained-statistic and do-less thresholds remain unchanged. A passing
result would apply to this exact short T85 task and external instrument, without establishing an evolved
algorithm, local attainability or repeated T1024 admission. Evidence: `results/delayed_match_information_20261015/`.

## 2026-10-15 — Delayed matching rewards retained cue information

On 512 fresh paired T85 lives, retaining the early sample statistic adds **2.945493 ±0.143336 F** over
zeroing it while preserving current-choice sensing, movement and taps. The remembering instrument completes
480 choices: 479 correct and one wrong, leaving 32 unfinished. Its memory-erased counterpart completes 482:
246 correct and 236 wrong, leaving 30 unfinished. Correctness among completed choices falls from 99.79% to 51.04%.
The narrower/broader cue class totals are 257/255; correct choices cover 94.16%/92.94% of those opportunities.
The separately measured sample classifier is 511/512 correct, which is not the final-choice accuracy.

Information gains over the unchanged and development-selected reflexes are **5.486980 ±0.065351** and
**5.480072 ±0.065344 F**. Fixed narrow/broad preferences lose **2.913659 ±0.154851 /3.022762 ±0.145101 F**.
All eight do-less criteria pass; the smallest mixture-minus-control margin is 0.882445 ±0.016333 F.
All finite reflex/do-less arms make zero choices, so “best reflex” means the declared tested family.
The full memory-erased and never-stored records match bitwise on all 512 pairs, as do retained/erased sealed
sample statistics and pre-choice spike prefixes. This supports the isolated retained-information contribution.
Maintenance is 95.2 energy per instrument life; other ordinary charges differ little across memory conditions.
Extra correct-choice income supplies 227.539063 of the 250.366873 energy gain. Avoiding wrong choices
saves another 22.949219; other ordinary charges increase by 0.121408.

All section 0.4 thresholds pass for this exact short T85 world. This is an external instrument with free central
computation, not evolved behavior, local attainability, repeated T1024 admission or an accessible mutation gradient.
The earlier evolved baseline demonstrates pursuit with a broad-shape bias, not conditional matching.

All **6,656 scientific +40 engineering =6,696 calls** complete, with every status 0 and all owned execution cleared.
Scientific execution uses **573.692021 CPU /609.873344 wall seconds**, peak 329.61 MiB. Adding the 50.93 CPU-second
prior allocation gives 624.622021 CPU seconds; saved-data audit and packaging are separately metered. Independent
all-row accounting, selection ties, hashes and paired-statistic recount pass without new lives. The public raw
archive preserves all 6,656 NPZ files; frozen reanalysis is available. No research retry or cap extension occurred.

Next proceed into bounded ordinary delayed-matching evolution from an inherited full population, measuring
conditional choices, costs, earlier skills and fixed-genome transfer. Report the exact next budget before launch.
Report: `results/delayed_match_information_20261015/REPORT.md`. Prospective commit 222092e;
protocol da37b128…6ef78a; summary 54855e9c…1ed723.

## 2026-10-15 — Delayed-matching evolution prepared: new context dependence with earlier skills retained in selection

One 24-generation ordinary search starts from every ordered survivor of AO balanced24, chosen for its earlier
retention evidence. Fixed selection uses four matching T85, two POOL and two persistent lives per eight, repeated
for the eight-life recheck. Native physical F, extinction charge, prices, 32+224 search, mutation operators and
local asynchronous cell rules are unchanged. No controller or prescribed matching algorithm enters the organism.
This mixture is a deliberate cumulative-capability choice, not an established optimum or retention guarantee.

Generation 24 rank 0 is primary; generation 8 is a passive fixed observation. Both, the starting genome and the AM
reference receive 512 shared fresh lives in seven worlds: matching T85, POOL, persistent, longer-gap retention,
development-known repeated matching T1024, short-blank diagnostics, and a reserved blank 10–30/radius 3–5 combination.
Class-specific correct/wrong/unfinished choices, coverage, cue-dependent narrow-choice response, physical costs
and native fitness are reported together. Ratio differences use paired life-cluster uncertainty; repeated trials
are not independent lives. Older-task 90% retention is diagnostic, and the same fixed genomes face every world.
This tests a narrow step toward reusable capability, not superiority to practical handwritten algorithms.

The complete maximum is **75,902 calls**, with a **10,800 CPU /7,200 wall-second package allocation**, including
120 CPU/120 wall seconds reserved for preparation. Monitored execution gets 10,680 CPU/7,080 wall seconds;
8,280 CPU seconds for search and 2,400 for confirmation. One two-thread worker has 8 GiB address space, a 4 GiB
combined owned RSS stop and a 4 GiB host-memory reserve. The exact budget was reported before launch. There is
no automatic retry, cap extension or favorable-midpoint substitution.

Simulation-free checks found that the native half-duration growth diagnostic requests fractional 42.5, which
the ABI rejects. The study adapter maps only those two nonselection diagnostic lives to T42, retaining their
native seeds. Selection and principal confirmation remain T85. All 53 adapter/replay tests and saved-row accounting
checks pass. A later terminal-replay metadata expectation fix is separately source-reviewed with original files
and test receipt preserved; it changes no scientific inputs. Native 53233/block 146 are collision-audited.
No scientific life has run at prospective publication. Evidence: `results/delayed_match_evolution_20261015/`.

## 2026-10-15 — Delayed-matching continuation improves economy, without demonstrated matching

The fixed 24-generation continuation from all 32 AO balanced survivors gains **1.194293 ±0.101150 F**
on trained T85 matching. Lower physical costs supply 0.941535 F, about 79% of that mean gain; fewer missed
clicks supply 0.536765 F, maintenance 0.249689 and division 0.121358. Empty clicks fall by 4.5625 per life,
and final cell count falls from 81.26 to 63.35. These are useful efficiency changes, not an isolated
information-dependent circuit or memory mechanism.

The endpoint completes 489 of 512 observed opportunities, versus 460 for the ancestor. It makes 257 correct
and 232 wrong choices, with 23 unfinished; 470/489 completed choices favor the broad physical target.
Correct narrow choices are only 12/248 narrow-cue opportunities, versus 7/248 initially. The conditional
narrow-choice response improves **0.025503 ±0.023872**, unresolved. Repeated T1024, shorter-blank and
reserved delay/distance-combination response gains are also unresolved. Repeated matching adds correct
narrow hits, but also adds narrow hits after broad cues; physical slot captures do not establish matching.
Reserved-transfer F improves 0.729445 while income falls 0.275735 F and savings add 1.005181 F.

Older acquisition declines: final-minus-start POOL captures **−3.287109 ±0.235408** (79.15% point retention),
persistent **−0.750000 ±0.140817** (87.31%), and longer-gap **−0.455078 ±0.112698** (88.75%). All absolute
losses are resolved at the descriptive three-SE level. POOL loses more than the 10% diagnostic tolerance;
persistent/longer-gap 90% margins remain unresolved. Later generations add completion/income as well as
savings on matching, but from generation 8 to 24 POOL loses another 2.496094 ±0.219939 captures. The fixed
final endpoint remains primary. One continuation does not establish a capacity ceiling or general search limit.

All **75,894 research +8 startup =75,902 calls** complete in **4,676.217354 CPU /2,315.306468 wall seconds**,
peak 346.78 MiB, with all 14,336 confirmation statuses zero and owned workers clear. No retry, cap extension,
reduced matrix or scientific-source change occurred. Frozen recorded-genetics replay verifies 5,376 offspring,
10,752 additions and all 32 midpoint/final rows. Independent all-row accounting agrees on all 25,772 numeric
summary values. A separate fixed 12 C +12 JS illustration batch matches 840 full-C/retained-fast-C ledger
values and 840 JS/full-C ledger values; JS also matches 60 full-C hashes and 4,067 spike pairs. Supplied-state
UI checks pass; browser rendering is untested.

The user's cumulative-building-block principle now guides the next environment: familiar pursuit should
pay immediately, and nearby additions should be useful before a complicated combination is complete.
Prioritize persistent, depletable food patches with observable local consequences and fixed physical laws.
Only collected resources minus physical costs would pay; no named behavior or hand-built circuit is required.
The full AO balanced population is the leading next starting candidate, preserving stronger older acquisition;
that future choice does not replace this study's registered endpoint. Prepare the concrete world contract
and information-payoff measurement before any new evolution run. No paid compute is needed.

Report: `results/delayed_match_evolution_20261015/TERMINAL_REPORT.md`;
viewer: `results/atlas/delayed_match_evolution.html`. Protocol 2941610e…64d9345;
summary 80963876…3fe91a33; prospective commit 382761c.

## 2026-10-15 — Persistent resource patches implemented for cumulative-capability experiments

ABI6 adds fixed, independently replenished food
patches whose stock changes the existing local sensory field. Harvest depletes stock without relocating the
patch; only collected food minus ordinary physical costs pays. Genome, cell inputs, asynchronous local rules
and prices stay unchanged. This tests the cumulative direction: inherited pursuit can obtain food immediately,
while nearby additions may improve use of continuing supply. No behavior sequence is prescribed.

Engineering checks are complete: eight C-full/C-fast/Python truth triples, eight whole and eight stepped JS
replays, 71 direct C boundary cases, older ABI compatibility, observer purity and deterministic ABI6 resume.
The default suite has 1,086 passes with two fixture/style corrections passing separately; 127 slow cases were
not run. Runtime validation, including failed commands, used 168.893127 CPU seconds and 624.40 MiB peak owned
RSS; all workers are clear. The fixed paused preview is an engineering illustration, not evolved patch behavior.
See `results/abi6_resource_patches_20261015/README.md` and `docs/ABI6_RESOURCE_PATCHES.md`.

Next measure the full inherited AO balanced population and fixed AO/AM references on the new world and old
pursuit tasks. Keep initial and replenished food separate, retain all rows, and do not select a new endpoint from
this diagnostic. Information-payoff instruments and evolution are separate next investments. Neither world
admission nor useful new circuitry is established yet; local resources remain adequate.

## 2026-10-15 — Inherited pursuit already collects replenished resources

Without patch-world evolution, the fixed AO genome
collects 21.4375 ±0.8636 packets per life, including 15.5000 ±0.8531 from replenishment; the fixed older AM reference
collects 16.3438 ±1.1462 total, including 10.9063 ±1.0154 replenished. Paired AO−AM gains are 5.0938 ±1.4102 captures
and 2.8504 ±0.7032 F over 32 shared development lives. AO harvests from all three patches in 31/32 lives, a descriptive
coverage count rather than evidence of revisit order or memory. Every one of the 32 inherited rows has positive
mean F on eight separate shared development lives; none is selected as a replacement endpoint.

The same unchanged references still acquire food in POOL and persistent pursuit; their differences there are
unresolved in this small panel. All 448 scientific +8 engineering calls complete with status 0 and exact full/fast
pairs in 37.901941 CPU seconds, peak 333.96 MiB, with owned workers clear. Independent accounting reconciles all
456 rows and 7,210 summary numbers. Evidence: `results/resource_patch_baseline_20261015/REPORT.md`.

This establishes an inherited foothold for cumulative improvement, not newly evolved patch circuitry or formal
world admission. Next test the whole-life contribution of stock-dependent sensory modulation on these same fixed
genomes, using exact constant-amplitude controls and explicit reuse of development rows. Food laws, ordinary
cell rules and prices stay fixed; actual actions and development may diverge. This small causal probe precedes
investment in an external allocator or new evolution. Memory, broad generality and plan 0.4 admission remain open.

## 2026-10-15 — Inherited pursuit benefits from local depletion cues

The unchanged AO genome collects **21.4375 packets per life** with stock-dependent patch brightness, versus
**16.1875** at constant amplitude 0.55 and **13.15625** at constant 1. Native minus 0.55 adds **5.2500 ±0.9103
captures**, including **4.4063 ±0.8612 replenished packets**, and **2.924125 ±0.455617 F**. Extra food supplies
87.67% of the mean F gain; costs supply the rest. Empty-patch clicks fall **19.1563 ±2.2869**, geometric misses
18.0000 ±2.8131, and travel 89.3627 ±8.6863. Native minus constant 1 gains 8.2813 ±0.9527 captures and
4.630532 ±0.471862 F. The fixed older AM genome also benefits: native minus 0.55 gains 4.0000 ±1.3236
captures and 2.196039 ±0.638725 F.

This demonstrates useful inherited sensory behavior in a new resource setting before any patch-world evolution.
The 32 life seeds and 64 native scientific rows are explicitly reused development data. Whole-life changes can
alter development, sensory dose and actions. Neither constant control establishes matched realized footprints,
memory, a stock estimator, visit order or formal world admission. Ordinary local cell rules and prices remain
unchanged; only an isolated measurement renderer replaces the stock-dependent amplitude with exact constants.

All **148 new calls** return: 128 scientific plus 20 engineering. Eight native-hook comparisons reproduce saved
ledgers/hashes; four C-full/C-fast/Python triples pass. All 212 combined CSV rows have status 0. Monitored execution
uses **31.042736 CPU /30.724609 wall seconds**, peak **334.42 MiB**, with all owned workers cleared. Initial
analysis then fails because file metadata `path` collides with the native distance column. All original evidence
remains intact. A separately reviewed one-key metadata repair completes saved-data analysis in 0.933887 CPU
seconds, with no repeated life or build. Independent accounting verifies all raw rows, 28,408 CSV numbers and
2,166 summary values, plus the preserved failure/recovery chain.

Next test cumulative adaptation through a bounded ordinary continuation of the full AO population, retaining
earlier tasks and reserving a new resource combination. Section 0.4 now explicitly permits this exploratory
accessibility test separately from formal admission; its numerical criteria and outstanding comparator gaps
remain unchanged. No new evolution is released by this result entry.

Report: `results/resource_patch_modulation_20261015/REPORT.md`; protocol 435d8439…568209c1;
summary 48989b63…b38fc940; manifest 34a3d3a1…7b5239e1.

## 2026-10-15 — Cumulative resource-patch pilot registered

Eight ordinary generations import all 32 ordered AO balanced24 survivors. Fixed selection allocates four patch,
two POOL and two persistent pursuit lives per eight, repeated for rechecking. Physical prices, local rules and
ordinary mutation/mating stay fixed. This tests whether useful inherited behavior can improve cumulatively;
it uses the explicit bounded-exploration exception and makes no formal world-admission claim.

Generation 8 rank 0 is primary and generation 4 is a passive observation. AO start and both endpoints each
receive 512 fresh paired lives in trained patches, POOL, persistent pursuit, earlier longer cue gaps and a
reserved four-patch/radius 3–5/refill 100–200 combination. Replenished food, total capture, empty clicks and costs
accompany F; direct older-task capture retention uses the existing 90% diagnostic. No favorable midpoint or
different winner for each environment can replace the fixed final endpoint.

The maximum is **28,222 calls**, including eight startup engineering lives, under **5,400 CPU /3,600 wall
seconds**, two threads, 4 GiB owned RSS, 8 GiB address space and 4 GiB host reserve. Preparation and terminal
work receive 120 CPU seconds; search receives at most 4,080 and confirmation/cleanup 1,200. Native 53234 and
block 149 are collision-audited. All 47 adapter and 13 saved-reader checks pass without new lives or builds.
Runtime release follows exact-input review and prospective publication; no simulation runs during registration.

Evidence: `results/resource_patch_evolution_20261015/`; protocol `0b0fd4e0…c452da1`.
The separate [inherited AO preview](results/resource_patch_preview_20261015/resource_patch_AO.html) matches
107 ledger values and five hashes in one JS replay against a previously saved C life. It illustrates the starting
lineage and contains no resource-evolved endpoint; real-browser rendering remains untested.

## 2026-10-15 — Resource evolution improves economy, without demonstrated cumulative acquisition

Eight ordinary generations gain
**0.595798 ±0.161773 F** on trained patches, with 0.436534 F (73.27%) from lower physical costs.
Total acquisition gains 0.326172 ±0.328844 captures and replenished food 0.373047 ±0.302795, both unresolved.
Empty-patch attempts rise 1.964844 ±0.297662 while geometric misses fall. Final tissue shrinks from 83.12 to
68.98 cells on average. POOL loses **1.861328 ±0.216181 captures** (88.39% point retention); persistent and
longer-gap point retention are 94.79%/94.67%. All three 90% retention margins remain unresolved, so a POOL
loss exceeding 10% is not established. The reserved patch combination loses **1.382813 ±0.267868 captures**
and 0.929688 ±0.216024 replenished packets. Generation 8 stays primary; generation 4 does not replace it.

All **28,222 calls** complete in **1724.714517 CPU /857.732643 wall seconds**, peak 359.39 MiB, with all
7,680 confirmation statuses zero and owned workers clear. Independent accounting checks 20,979 summary
numbers and every native row; recorded replay reproduces 1,792 offspring, 3,584 additions and all midpoint/final
population rows. A zero-call launcher preflight correction is preserved separately; scientific execution has
no retry or source change. Evidence: `results/resource_patch_evolution_20261015/REPORT.md`.

This establishes economy, not a new cumulative acquisition primitive. The next priority is one bounded
selection comparison: ordinary mean-F against keeping candidates with useful task-specific acquisition
advantages, using the same inherited final population, worlds, prices and ordinary mutation. One fixed genome
per branch must face every evaluation world; a portfolio of specialists is insufficient. The leading design
is four generations per branch, with a common endpoint rule and a new reserved combination. Source review,
exact budget and prospective registration precede execution. See the completed archive's `NEXT_DECISION.md`;
this result does not release a new run. Safe local resources remain adequate.

## 2026-10-15 — Preserving partial acquisition advantages: selection comparison registered

Two four-generation branches now inherit all 32 ordered
survivors of the completed resource continuation. One uses ordinary mean fitness; the other preserves
nondominated tradeoffs among patch, POOL and persistent capture plus ordinary fitness. Worlds, physical
prices, mutation, mating and life budgets are identical. This tests whether useful partial acquisition
advantages survive long enough to combine, without prescribing circuitry or changing the organism.

Both branches use the same final-genome rule: maximize the weakest relative acquisition across the three
training worlds, using cached selection lives and fixed ancestral reference scales. Each chosen genome and
both ancestors then face the same 512 fresh lives in five worlds. The reserved combination has two patches,
radii 3.5–5.5 and refill intervals 60/180; the earlier count-four combination is now development evidence.
One unchanged genome must carry the gains; population specialization alone is insufficient.

Maximum **30,808 calls** (30,796 research +12 startup), under **5,400 CPU /3,600 wall seconds** including
120 seconds preparation/terminal allowance. One two-thread worker, 4 GiB owned RSS, 8 GiB address space and
4 GiB host-memory reserve. Native 53235/block 150 are collision-audited. Source and supplied-data checks,
exact-input review and prospective archive verification pass with zero new lives. A stale prose review pin
was corrected with original failure evidence preserved; scientific inputs did not change. Protocol
`529d6571…31d8dd`, evidence `results/resource_patch_selection_20261015/`. Runtime release follows publication;
this note records no result and makes no formal admission, memory or generality claim.

## 2026-10-15 — Preserving acquisition strengths changes tradeoffs, without joint retention

The fixed Pareto endpoint beats the
ordinary-selection endpoint by **1.193359 ±0.334373 patch captures**, **0.755859 ±0.213004 POOL captures**
and **1.474609 ±0.251871 captures in a reserved patch arrangement**. It loses **0.708984 ±0.141300 persistent**
and **0.539063 ±0.113514 longer-gap captures**. All five capture differences exceed three paired SE in their
stated direction over 512 fresh shared lives. Added trained-patch food supplies +0.582695 F, with extra costs
subtracting 0.218366 F; the resulting +0.364329 ±0.162168 F is unresolved at three SE.

This changes which acquisition strengths survive, but does not establish cumulative joint improvement.
Versus its own G8 start, Pareto's patch gain is unresolved (+0.191406 ±0.302464), POOL recovers
0.894531 ±0.208193, and persistent/longer-gap capture falls. All three Pareto 90% retention margins versus AO
remain unresolved despite resolved absolute losses. One matched pair does not establish strategy reliability
or novelty over every founding row. Both branches used the same endpoint rule; mean rank0/ID663 and Pareto
rank11/ID883 remain fixed. A favorable population member cannot replace either after confirmation.

All **30,808 calls** complete in **1854.964639 CPU /924.584002 wall seconds**, peak 346.70 MiB, with all
10,240 confirmation statuses zero and owned workers cleared. Independent scalar accounting, recorded genetics
and independent selection mathematics pass. Evidence: `results/resource_patch_selection_20261015/REPORT.md`.
The [four-genome preview](results/resource_patch_selection_preview_20261015/resource_patch_selection.html)
passes 428 ledger comparisons in four JS replays; full-C trajectory hashes and browser rendering are untested.

Next inspect all 32 survivors of G8 and both branches on one fixed small development panel, including the
unchanged AO reference. This asks whether useful combinations remain in the populations or whether noisy
endpoint selection obscures them; it cannot certify a new winner or prove combinations absent. The proposed
97-genome × five-world × 32-life panel has 15,520 research +4 startup calls. No new evolution, endpoint replacement
or extra resources follow automatically. Local resources remain adequate; freeze the diagnostic before launch.

## 2026-10-15 — Whole-population acquisition diagnostic registered

**Whole-population development panel registered (2026-10-15).** Measure every ordered survivor from the G8,
mean4 and Pareto4 populations, plus unchanged AO: 97 genomes, five existing worlds and 32 fresh shared lives.
This asks whether useful combinations remain available and how the reporting rule's small cached sample ranks
them. It retains duplicates and historical endpoints, reports uncertainty over shared life seeds, and certifies
no new winner. The previously reserved patch arrangement is now development evidence.

Maximum **15,524 calls** (15,520 research +4 startup), under **2,700 CPU /1,800 wall seconds**, including a
60-second preparation/terminal reserve. One two-thread worker, 4 GiB owned RSS, 8 GiB address space and 4 GiB
host-memory reserve. Block 151 is collision-audited. Source checks and seven supplied-array reader checks pass;
the actual 97-row input is checked against the original checkpoints. Protocol `6fb2a4f9…a5ee33f`, evidence
`results/resource_patch_population_20261015/`. Runtime release follows publication; this registration records
no new organism life or outcome. Reassess the next experiment after the full panel.

## 2026-10-15 — Useful survivor variation and unstable cached reporting ranks

**Whole-population diagnostic complete (2026-10-15).** Useful survivor variation remains. By the same joint
acquisition rule, the historically reported mean/Pareto genomes move from cached rank 1 to fresh ranks
**29/32 and 25/32** within their populations; G8's reported genome ranks 15/32. These 32-life development
ranks do not certify replacement winners. The cached samples had only four POOL and four persistent lives.

Across all survivors, Pareto gains **1.166016 ±0.239681 POOL captures** over mean selection and
**0.875977 ±0.191965** over G8. Its patch, persistent, longer-gap and revealed-combination capture changes
remain unresolved. The large pursuit losses of the earlier fixed endpoint are not established population-wide;
that earlier 512-life result remains valid for its fixed genomes. Higher physical costs are population-wide.
Point estimates retain at least 90% of AO captures in all three old worlds for 10 G8, 8 mean and 16 Pareto rows;
none clears all three descriptive lower-three-SE margins. No new joint capability or memory is established.

All **15,524 calls** complete in **861.068225 CPU /429.966323 wall seconds**, peak 344.30 MiB, with all research
statuses zero and owned workers clear. Independent accounting checks every research ledger and 25,288
statistics. An inefficient saved-data reader hit its CPU cap; caching each cohort once fixes it without new
scientific calls. Original failure evidence is retained. Report and population/ranking plots:
`results/resource_patch_population_20261015/REPORT.md`; manifest `c950f9b3…1223f5`.

Next give the full Pareto population eight more generations with 32 initial +32 recheck lives, unchanged
objectives/world allocation/physics/operators, and a separate all-survivor endpoint panel before fresh
confirmation. Include development-selected starting row26/ID918 as a new-study comparator, never a replacement
for historical ID883. This tests combined depth and measurement effort, not the causal superiority of a sampling
policy. Freeze the new budget/inputs before launch; no run follows automatically. Reconsider a richer accessible
interaction after the bounded result rather than automatically tuning selection again.

## 2026-10-16 — Deeper cumulative resource continuation registered

**Deeper continuation registered (2026-10-16).** The full 32-row Pareto population now receives eight more
generations with 32 initial and 32 recheck lives per candidate, retaining the existing acquisition objectives,
world allocation, physical prices and genetic operators. This follows the completed evidence that useful
variation survives and small cached samples rank reporting genomes poorly. It tests combined depth and
denser evaluation, not the causal superiority of either change.

After search, a separate 32-life panel in each training world selects one final survivor by weakest relative
acquisition, weighted ordinary fitness, then ID. Its genome is frozen before 512 fresh lives in six worlds,
alongside unchanged AO and development-selected G8/Pareto4 ancestors. The new reserved case has four
capacity-three patches, placement radii 2.5–4.5 and refill periods 60/180. Initial stock and replenished
harvest remain separate. Historical reporting endpoints are not replaced.

Maximum **97,342 calls** (97,334 research +8 startup), under **10,800 CPU /7,200 wall seconds**, including
180 seconds preparation/terminal allowance. One two-thread worker at a time, 4 GiB owned RSS, 8 GiB address
space and 4 GiB host-memory reserve. The native seed and two fresh panel blocks pass collision review.
Source checks, 14 supplied-data tests and exact-input review precede publication and runtime release.
Protocol `86593f75…2653bb`; evidence: `results/resource_patch_depth_20261015/`. This registration records no new organism outcome.
Reassess cumulative acquisition and retention after this bounded continuation, then reconsider a richer
accessible interaction rather than automatically making another selection tweak.

## 2026-10-16 — Linked population explorer from completed measurements

The standalone [population explorer](results/resource_patch_population_explorer_20261016/population_explorer.html)
links all 97 fixed genomes across four plots: trained-patch captures against POOL, persistent pursuit,
longer-gap pursuit and the revealed two-patch arrangement. Hover, keyboard focus or selection highlights the
same genome throughout. Selected rows show all five task means, standard errors, historical endpoint status
and descriptive cached/fresh ranks. Historical AO scales used for ranking are distinguished from the displayed
32-life AO estimates. No endpoint is replaced.

All 485 CSV rows and 3,880 embedded numeric values reconcile exactly with the completed population archive.
Root and independent reviews confirm identities, markers, axes and uncertainty labels; syntax checks pass.
No real browser was tested. Rendering and two wording corrections use saved data only: zero simulations,
builds or scientific random draws. Original receipts and final mapping checks are retained.
The ongoing depth study's frozen files, budget and scientific inputs remain unchanged.

Evidence: `results/resource_patch_population_explorer_20261016/`; manifest
`9022e94b4f15eaee9ca225ac05f9e98fb69cd77b9f0c4b360be6b92f851db65e`.

## 2026-10-16 — Deeper continuation recovers older acquisition without a joint patch gain

**Deeper continuation complete (2026-10-16).** The frozen descendant (row 24 / ID 1415) gains
**0.812500 ±0.223576 POOL captures** and **0.849609 ±0.144374 persistent-pursuit captures** over the fixed
Pareto4 comparator on 512 fresh shared lives. Ordinary F rises **0.330844 ±0.106961** and
**0.386901 ±0.071118** respectively despite added physical costs. All four gains exceed three paired SE.
Trained patches (−0.529297 ±0.365804 captures), longer gaps (+0.246094 ±0.122139), the revealed patch
layout and the new reserved capacity-three layout remain unresolved in the primary comparison.

All nine older-world 90% retention margins against AO/G8/Pareto4 clear three SE. This permits up to 10% loss
and does not establish lossless retention. The revealed two-patch layout loses **0.982422 ±0.233320 captures**
against the fixed G8 comparator. Thus this is partial recovery of older acquisition, without demonstrated joint
superiority or a new patch strategy. Refilled food does not improve demonstrably; reserved-layout totals include
more initial food. One combined depth/denser-evaluation pilot cannot identify which change caused the gains.
Historical reporting endpoints are unchanged; new-study G8/Pareto4 comparators remain distinct from them.

All **97,342 calls** finish on the first scientific attempt in **7291.161815 CPU /3611.875809 wall seconds**,
peak **343.80 MiB**, with both owned phases cleared. The full 180-second outside-runtime reserve fits the
10,800 CPU /7200 wall package cap. Independent recorded-genetics/selection and scalar-accounting checks pass:
81,920 selection lives, 1,792 offspring, all 32 final rows, 3,072 endpoint and 12,288 confirmation ledgers,
weighted endpoint selection and eight startup calls. All confirmation statuses are zero. Report and six-world
plots: `results/resource_patch_depth_20261015/REPORT.md`; follow-up judgment: `NEXT_DECISION.md` in that archive.

Retain the population and fixed reporting genome. Reconsider accessible richer interactions and a concrete
information/mechanism or representation hypothesis before another automatic selection tweak or unbounded
continuation. This outcome establishes neither a capacity ceiling nor performance beyond strong handwritten
baselines. No further scientific study was launched.

## 2026-10-16 — Fixed depth-study replay and acquisition behavior

The [four-genome viewer](results/resource_patch_depth_preview_20261015/resource_patch_depth.html)
replays the predetermined first confirmation seed, 52530000, in the trained patch world. The new descendant
collects 9 packets versus 17 for Pareto4 joint in this particular life; the example is retained unchanged.
Across the full panel, patch improvement was unestablished. A favorable animation was not substituted.

Saved pursuit measurements sharpen the observed change: POOL mean captures rise 15.4023 to 16.2148 while
clicks fall 37.9199 to 33.3750; persistent captures rise 5.4844 to 6.3340 while clicks fall 33.7988 to 30.6582.
Misses decrease in both tasks and bodies are slightly larger. These observations do not distinguish causal
changes in development, sensory processing or action timing, and additional hidden cells do not prove a circuit.

All four JS replays match all 428 saved native ledger values. They use no new C/Python lives or builds;
fast-C hashes provide no full-trajectory comparison and no real browser was tested. Replay uses 3.642834 CPU /
3.605601 wall seconds, within its separate 15 CPU / 60 wall package. Saved-input and public-archive verification pass.
The original research archive remains unchanged. Evidence: `results/resource_patch_depth_preview_20261015/`.
