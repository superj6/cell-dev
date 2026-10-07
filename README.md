# cell-dev

Evolve "genetic codes" that grow a tissue of spiking cells on a lattice, where the grown tissue solves tasks by
**local message passing**. There are no input or output cells: every cell senses the stimulus where it sits, and the
environment reads *where* the firing ends up. Living, firing and dividing cost energy.

```
genome ──develop──> tissue (cells, types) ──spiking ticks──> where activity ends up ──> score − energy
  │  GRN: divide / asym split / secrete / type        LIF per cell type: neighbour spikes + local stimulus
  └─ evolution: (μ+λ), two-parent crossover ("sex") or mutation only ("asex")
```

## How it works
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

## Task ladder (same two stimulus channels throughout: light, cue)
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

### Message rungs: information has to travel
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

### Controls (same harness, same evaluation budget)
- `cells.messages=false`: cells never hear their neighbours (no-message control).
- `develop.mode=fixed`: a pre-made one-type disk; only the cell rule evolves (does growth matter?).
- `evolve.generations=0 evolve.init_samples=N`: random search over N genomes.
- `evolve.breeding=asex`: mutation only (does crossover matter?); `lattice.kind=square4|square8`.

## Run
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

## Layout
```
configs/   base.yaml is the single source of truth; others `extends` it
src/       lattice, genome, develop, cells, tasks/, evolve, measure, render, run, common (from alt-arcs)
scripts/   census, replay, analyze, sweep, aggregate, run_rungs.sh
tests/     lattice / development / cells / tasks / evolution invariants and a smoke run
```
See `RESULTS.md` for the living results and the planning notes in the plan file for the literature map.
