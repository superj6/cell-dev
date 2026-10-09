# cell-dev

Evolve "genetic codes" for how cells divide and change, so that the tissue they grow runs **emergent, local,
asynchronous message-passing algorithms** that perform a task. Every cell runs the same genome; cells only ever hear
their immediate neighbours; nobody wires an input or an output; fitness is task performance minus the cost of living
cells.

**See it:** `results/atlas/atlas_play.html` (open in a browser) replays evolved bodies, explains how each one works,
and has a live playground where you drop targets and an evolved body chases them. The playground's simulator is a
JavaScript port that matches the C kernel bit for bit.

## The current model: one continuous life (BODY-1)

```
genome (16-gene regulatory network, the same in every cell)
   │  each cell, on its own jittered clock: read local inputs -> update gene expression -> decode 23 knobs
   ▼
one zygote ──divide / specialise / die──> a layered body on a hex-prism lattice ──spikes to neighbours──> behaviour
                                            z=0 senses the screen, z=1 twitches the body, z>=2 hidden
```

- **Cells** are leaky integrate-and-fire neurons with two value-less spike channels to up to 8 neighbours (about one
  time unit per hop). Each cell's weights, thresholds, division, death, secretion and polarity are read off its gene
  expression, so cell types and wiring emerge during growth.
- **One continuous life:** growth, sensing and behaviour happen together; there is no separate development stage and
  no global clock. The simulator is exact and event-driven (C kernel `src/life/kernel.c`, a bitwise-equal Python
  reference `src/life/reference.py`, contract `docs/LIFE_ABI.md`).
- **World (CATCH / SPECK):** the body is a dot on a screen chasing a drifting target. Bottom-layer cells get receptor
  "pings" when the target's glow is under them; a spike in the layer above twitches the dot outward on that cell's
  side; the centre cell of that layer taps, and a tap with the target inside the catch zone is a catch.
- **Evolution:** (32+224) with crossover and a two-stage recheck, about 1,000 lives per generation
  (`src/life/evaluate.py`, `src/run.py`, `src/evolve.py`).

**What we found** (RESULTS.md, 2026-10-09): in the SPECK world 7 of 10 runs reached the skill bar. Every body regrew
the column reflex, and lineages added genuine local computation on top (neighbour voting with an antenna fringe,
cooperative detection with feedback inhibition, gain set by crowding), built direction-specific synapses out of
morphogen gradients, and stopped growing by contact inhibition. No evolved body yet routes signals like the
hand-built router or beats the hand-built reflex; hidden layers stay unused.

### Documents
| file | what it is |
|---|---|
| `RESULTS.md` | the lab notebook: every experiment, newest at the bottom |
| `docs/ROADMAP.md` | next research directions, costs, decisions |
| `docs/POST_PILOT_CALLS.md` | what worked and what did not in the BODY-1 pilot, ranked calls |
| `docs/ALTERNATIVES.md` | alternative substrates (neural CA, learning synapses, logic tissue, grown wires) |
| `docs/HARDWARE_PATH.md` | running the cell logic natively on FPGA / custom silicon |
| `docs/LIFE_ABI.md` | the exact simulation contract (events, handlers, decode, world) |
| `docs/ONE_LIFE_DESIGN.md`, `docs/BODY_DESIGN_PROPOSAL.md` | design of the one-life model and the dot-body world |
| `docs/LIFE_GATES.md`, `docs/PROBE.md` | verification gates; the mechanism probe toolkit |

### Run
```
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # CPU torch: see requirements.txt
.venv/bin/python -m pytest -q                                        # about 1 minute
.venv/bin/python -m src.run --config configs/life_smoke.yaml         # a short evolution run
.venv/bin/python -m src.run --config configs/life_speck.yaml seed=0  # one SPECK run (hours on a laptop)
scripts/run_catch_pilot.sh                                           # the 29-run pilot matrix
.venv/bin/python scripts/catch_pilot_analysis.py --threads 8         # its pre-registered analysis
```
The kernel compiles itself on first use (gcc with OpenMP). Mechanism probes: `from src.life import probe as P`
(`docs/PROBE.md`). Atlas: `results/atlas/` (`extract.py`, `build2.py`, `play/build_playground.py`).

### Layout
```
src/life/   kernel.c (C), reference.py, spec.py (ABI, decode, presets), build.py, evaluate.py, handbuilt.py,
            analysis.py, probe.py
src/        run.py, evolve.py, genome.py, common.py, plus the earlier task-ladder model (lattice, develop, cells, tasks)
scripts/    sweeps, pilots, analysis, gates, benchmarks
configs/    life_*.yaml (one-life model), the rest for the task ladder; `extends` chains
results/    per-study outputs, the atlas and playground (results/atlas)
tests/      pytest suite (kernel = reference, gates, analysis, probes, style)
```

## License
No license has been chosen for the project yet, so default copyright applies. `results/atlas/play/lifesim.js`
contains ports of GNU C Library math routines and is distributed under the LGPL-2.1-or-later (see the notice in the
file and `results/atlas/play/COPYING.LGPL-2.1`).

## The earlier model: the task ladder (2026-10-06)
The first version grew a flat tissue in a separate development stage and then ran short timed trials on a global tick.
It is kept for reference; its specimens are part 2 of the atlas.

Evolve "genetic codes" that grow a tissue of spiking cells on a lattice, where the grown tissue solves tasks by
**local message passing**. There are no input or output cells: every cell senses the stimulus where it sits, and the
environment reads *where* the firing ends up. Living, firing and dividing cost energy.

```
genome ──develop──> tissue (cells, types) ──spiking ticks──> where activity ends up ──> score − energy
  │  GRN: divide / asym split / secrete / type        LIF per cell type: neighbour spikes + local stimulus
  └─ evolution: (μ+λ), two-parent crossover ("sex") or mutation only ("asex")
```

### How it works
- **Fabric** (`src/lattice.py`): sites plus a neighbour table, so lattices swap freely: `hex` (6 contacts, default),
  `square4`, `square8`. Edges have fewer neighbours; there is no wraparound.
- **Development** (`src/develop.py`): one seed cell; each step every cell updates its gene state from its own genes,
  local morphogens, how crowded it is and its age; secretes morphogens that diffuse; and may divide into an empty
  neighbouring site picked by how its genes weigh the morphogens there. Asymmetric division gives the daughter
  `g + asym·Q` and the mother `g − asym·Q`. The final gene state picks one of 4 cell types.
- **Cells** (`src/cells.py`): quantized leaky integrate-and-fire per type: weights per incoming spike channel (1/8 steps
  in [−2, 2]), gain per stimulus channel, bias, a power-of-two leak, 0–3 refractory ticks, which channels it emits on.
  A spike crosses one contact per tick. Every update is local: own state, neighbours' spikes, stimulus at its site.
- **Readout** (`src/tasks/base.py`): over a response window, how decisively the firing sits on the side of the target
  direction (spike-weighted mean cosine of the firing cells' offsets from the body centre). 1 = all firing on the
  target side, 0 = no lean or silence, −1 = wrong side.
- **Genome** (`src/genome.py`): 250 numbers, a GRN block and a cell-rule block. Crossover inherits whole units (each gene,
  each cell type, the globals) from one parent; mutation touches a few entries inside one block.
- **Evolution** (`src/evolve.py`): (μ+λ) with fresh trials every generation. The population starts from 8 founders
  ("breeds"): random genomes sampled in batches until some genome actually scores, scorers ranked first, so a run never
  starts from a dead single cell. `breeding: sex` crosses individuals, including across breeds; `asex` only mutates.
  On a ladder, `immigrants` > 0 replaces that share of the population with new founders sampled on each new rung.

### Task ladder (same two stimulus channels throughout: light, cue)
| rung | trial | what it forces |
|---|---|---|
| `light` | light gradient from a random direction; face it | sensing (2+ cells already score) |
| `brightness` | the same with brightness ×0.2–×5 per trial | contrast that survives saturation / dimness |
| `memory` | flash, random dark delay, uniform "go" cue; point where the flash was | self-sustaining activity |
| `motion` | a light spot drifts across; point the way it moves | timing; solvable by one cell type without messages (use `jump` for the message version) |
| `flicker` | two opposite lights, fast vs slow flicker; point at the fast one | timing filters (single-cell refractoriness already helps) |

`ladder` trains on the current rung (keeping 25% earlier-rung trials) and moves up when the best genome's score on
fresh training-distribution trials ("valid") reaches `evolve.advance_at`. Held-out trials (unseen directions plus wider
brightness ranges, longer delays, new speeds or closer flicker rates) measure generalization separately.

#### Message rungs: information has to travel
The readout already pools activity over the whole body, so a task whose answer is a linear function of what each cell
senses locally can be solved without any communication (and evolution finds those solutions: see `RESULTS.md`).
These rungs are built so that it cannot. Each one was red-teamed: an exhaustive single-cell analysis plus searches for
message-free cheats, and a stimulus audit for target leaks.

| rung | trial | why messages are needed | hand-built (messages / off) | best no-message cheat |
|---|---|---|---|---|
| `withdraw` | a brief poke on one side; activity must end up on the *other* side | the far side cannot sense the poke | 0.73 / 0.00 (13 cells) | 0.02 |
| `context` | a local cue on half the trials flips "face the light" into "face away" | most cells cannot sense the cue | 0.84 / 0.00 (7 cells) | 0.17 |
| `jump` | two flashes, A then B; point the way it jumped | B's response must depend on A's | 0.68 / 0.00 (19 cells) | ≈ 0.13 (bounded timing leak) |
| `memory` | (above) flash, delay, go cue | beyond a single cell's leak | evolved: 4 cells, 0.87 / 0.00 | 0.00 |

`configs/ladder_msg.yaml` chains them: withdraw → context → jump → memory.

#### Controls (same harness, same evaluation budget)
- `cells.messages=false`: cells never hear their neighbours (no-message control).
- `develop.mode=fixed`: a pre-made one-type disk; only the cell rule evolves (does growth matter?).
- `evolve.generations=0 evolve.init_samples=N`: random search over N genomes.
- `evolve.breeding=asex`: mutation only (does crossover matter?); `lattice.kind=square4|square8`.

### Run
```
source .venv/bin/activate
pytest
python -m src.run --config configs/local_smoke.yaml                 # < 1 min
python -m src.run --config configs/ladder.yaml evolve.generations=1500
python scripts/replay.py outputs/ladder --lattice square8             # GIFs; try the design on another lattice
python scripts/analyze.py outputs/ladder                              # knockouts + importance maps per rung
python scripts/census.py                                              # what random genomes do on each lattice
python scripts/sweep.py --config configs/memory.yaml --lattices hex,square4,square8 --breeding sex,asex \
    --seeds 0,1,2 --jobs 4 --threads 3 --name memory_sweep
python scripts/aggregate.py outputs/memory_sweep --out results/memory_sweep
scripts/run_rungs.sh                                                  # evolution vs random vs fixed vs no-message, per rung
python -m src.run --config configs/ladder_msg.yaml
```
Each run writes `outputs/<run>/{config.yaml, curves.jsonl, results.jsonl, best_genome.json, gifs/}`.
On this laptop 8 threads is fastest for one run; for sweeps use 3–4 jobs × 3 threads (≈8 GB RAM free).

### Layout
```
configs/   base.yaml is the single source of truth; others `extends` it
src/       lattice, genome, develop, cells, tasks/, evolve, measure, render, run, common (from alt-arcs)
scripts/   census, replay, analyze, sweep, aggregate, run_rungs.sh
tests/     lattice / development / cells / tasks / evolution invariants and a smoke run
```
See `RESULTS.md` for the living results and the planning notes in the plan file for the literature map.
