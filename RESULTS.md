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
