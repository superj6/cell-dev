# cell-dev: next research directions (2026-10-09)

This collects every direction worth pursuing after the BODY-1 pilot, what each could teach us, what it costs to get a
first visible result, and what has to happen first. It draws on RESULTS.md (the pilot and the three studies after
it), `docs/POST_PILOT_CALLS.md` (design review), `docs/HARDWARE_PATH.md` (hardware study), `docs/ALTERNATIVES.md`
(alternative substrates) and `results/catch_pilot/compute_audit.json`.

## Where we stand

- **Evolution finds local algorithms, but not yet multi-step ones.** In the SPECK world, 7 of 10 runs reached the
  skill bar; every body regrew the column reflex, and three lineages added genuine local computation on top: neighbour
  voting with an antenna fringe and a latch (s4), cooperative detection with feedback inhibition (s5), and gain set by
  crowding with in-life adaptation (s2). Every body built direction-specific synapses out of a morphogen gradient, and
  every grown lineage stops growing by contact inhibition. The better a body, the more it relies on neighbour messages
  (Spearman 0.71).
- **No evolved body routes signals the way the hand-built router does** (0 of 10), and none beats the hand-built
  reflex. The gap is earnings per cell, not catching skill. Hidden layers stay unused: the task never needs more than
  one or two processing steps.
- **Search is the binding constraint.** Each child is about 0.19 F worse than its parent, late progress is about
  0.005 F per generation, per-life scores are Poisson-noisy, and every run collapses to one lineage early. A harness bug
  (parents win exact ties) froze four original-task runs.
- **Compute is cheap and easy to scale.** About 0.1 CPU-s per life; a whole pilot is $6-16 on one rented 192-core box.
  Custom hardware does not pay for evolution throughput, but the model already maps onto tiles for native rollouts
  (exact window scheduler; fixed point is fitness-neutral).
- **Everything is visible.** The probe toolkit explains bodies causally, the atlas replays them, and the playground
  runs them live in a browser, bit for bit equal to the kernel.

## The questions worth answering

1. **What blocks multi-step computation:** search (noise, mutation, diversity), expressivity (missing primitives), or
   the world (nothing rewards it)?
2. **Can a body learn local optimisations while small and keep them as it grows?** Today nothing is learned during a
   life except gene-expression drift.
3. **Which worlds make hidden layers, memory, prediction and adaptation pay,** while keeping fitness = task
   performance and growth bounded by physics plus costs?
4. **Do bodies generalise** to new situations (task variety across and within lives)?
5. **Is the current cell the right substrate,** or does a learning or differentiable substrate get further, faster?
6. **Can an evolved organism run natively in hardware** in real time, and what model choices keep that cheap?

## Tracks

Costs are in CPU-hours (laptop-rate, an upper bound) or GPU-hours, and dollars on rented machines (2026-10-09 spot
prices: 192-core c7a about $3.40/h; an L4 GPU about $0.6/h; an H100 about $2-4/h).

### A. Harness fixes and speed (do first; days; no change to any organism rule)
- Random tie-breaking (fixes frozen plateaus); checkpoint/resume with a pinned environment and a bitwise check on new
  machines (makes spot rental safe); exact kernel fast mode (1.24-1.35x); cheaper receptor rejection; per-call
  thread growth; founder lives capped at 256 cells.
- Report-only readouts: income per cell, when each body stops growing, developmental speed, split-half reliability,
  hidden-layer cost, a hardware-energy panel.
- A **niche map**: for each world setting, does computation beat the reflex, and how much selection information does a
  CPU-second buy. It picks the worlds for everything below.
- *Learn:* nothing new about bodies, but every later result becomes cheaper and more trustworthy.

### B. Diagnose the routing barrier (Pilot 2, phase 1; about 230 CPU-h, about $5-10 rented)
- **Time:** continue the four best runs to 1,000 generations.
- **Reachability:** seed evolution with the hand-built router's genome and see whether selection keeps or erodes it.
- **Noise:** 4x lives against standard lives from the same population.
- *Learn:* whether the barrier is time, reachability, or selection and cell economy, which decides where to invest.

### C. Expressivity of the cell model (Pilot 2, phase 2; about 1,200-1,400 CPU-h, $15-45 spot)
- Faster conduction (d0 0.5) behind a re-tune gate; an ABI-4 cleanup (per-time gene laws, like-with-like gradient,
  gene split at ACK, drop tau_tr); gene duplication on; **per-channel face weights** (needs your approval).
- 20-seed matrix: control, face weights, duplication; pre-registered mechanism and router counts.
- *Learn:* whether a direct direction primitive or more genes produce routers and use of depth; whether chemistry
  stops being needed for synapse direction.

### D. Worlds that demand more (after the niche map)
- **Task family per life:** each life draws its world (halo width, noise, target speed, placement range, miss price)
  from a mapped range; fitness scaled per world by a fixed constant. *Learn:* generalisation; robustness.
- **Variety within one life (epochs):** the world switches statistics at random times (decoy-rich phases, fast
  targets). First a hand-built adaptive body must show the payoff. *Learn:* adaptation within a life.
- **Wound world:** random cell loss during life. *Learn:* regeneration and size regulation; gives genome-driven death
  a job.
- **Memory and prediction:** a target that blinks out or must be led (intercepted). Gate: a hand-built memory or
  interceptor body must beat the reflex first. *Learn:* whether hidden layers get a job.
- **Later worlds:** following a mouse cursor; reading a text stream (the original long-term ideas).

### E. Alternative substrates (see `docs/ALTERNATIVES.md`)
Four directions came out of a literature-backed brainstorm, judged on fidelity to the goals, a hardware-native
rollout, compute needed for visible outcomes, and scientific risk:
1. **Logic tissue (the organism):** each cell is a few dozen state bits plus one small gate circuit shared by every
   cell; spikes are bits; cells divide, die and steer the dot. The simulator *is* the netlist, so there is no gap
   between training and silicon; a stand-in ran in 2.6-7.6 ms per life on one core (today's kernel: about 100 ms).
2. **A shared neural cell (NCA family) as the trainer:** the same bit interface, trained by gradient through windows
   of continuous lives on a GPU, then compiled into gates. Fastest visible results: growth and regrowth in about a day,
   a grown body chasing in about two weeks.
3. **Plastic faces:** learning synapses in today's exact kernel. Cheap and decisive: can spike-timing plasticity
   rebuild "excite from below, inhibit from above" without the morphogen route?
4. **CellCode:** a language model edits the cell's integer event handlers and the exact kernel judges them. The most
   readable artefacts; unproven under noisy scores.

**Recommended first build, "spike-bit tissue"** (about three weeks, $45-110, capped at $150): direction 1 as the
organism, taught by direction 2, compiled to gates and refined by evolution with 64-256 paired lives per genome in a
bit-exact C engine. It keeps one continuous life, spikes, local rules, growth and death; it relaxes continuous time
to steps with random per-cell update enables, and must pass an asynchronous-replay test (no lockstep dependence).
Watchable milestones: M0 grow and regrow a shape; M1 a fixed tissue turns toward pings; M2 grow from one cell, then
chase; M3 regrow after losing half the body and catch again; M4 a mid-life motor flip that the body learns around.
Pre-registered bars include beating its own hand-built reflex with no more cells (the pilot: 0 of 10), a compiled
student keeping >= 90% of its teacher, and lateral messages carrying >= 50% of F.

**Side track on the current kernel** (about 100 CPU-h, $2-4): T1 can STDP replace the chemistry; T2 do paired lives
stay paired; T3 evolution strategies against the GA at equal lives (how much of the pilot's shortfall was search);
T4 silent gene duplication. The decisive comparison runs the current model, the current model with fixed search, and
the spike-bit tissue on the same world rules and budget.

### F. Hardware path for native rollouts (see `docs/HARDWARE_PATH.md`)
- **Integer ABI** as the next reference contract (folded into ABI 4): fixed point, table sigmoid and exp2/log2,
  integer timestamps; CPU 1.4-2.3x faster with fast mode; bitwise portable; the exact reference for any chip. Gate: all
  11 pilot bests within about ±2% F on 1,024 paired lives, then a 3+3-seed evolution A/B.
- **One cell processor** (HLS from the integer kernel, co-simulated in Verilator), then a **37-cell array** on a
  rented FPGA running a CATCH body in real time; then a clockless (GALS) version. About 2-4 person-months with FPGA
  experience.
- **Silicon** only after the ABI is frozen: one cell on a Tiny Tapeout slot (EUR 1-2k), later a 30-75-cell chip
  ($2-15k, 6-12 months).
- *Learn:* real area and energy per cell; an evolved body running in silicon.

### G. Scale and search infrastructure
- Rent many-core CPUs for cell-model matrices and GPUs for substrate experiments; keep a run portfolio (extend the most
  promising runs, judged by validation score only); quality-diversity archives or islands against early collapse;
  evolution strategies with paired lives for noisy scores.

### H. Visibility and analysis
- Every new body goes into the atlas and the playground (the JS engine is exact, so what you see is the model);
  the probe toolkit's router-vs-reflex signature becomes a standard readout; mechanism accounts keep being checked
  by a skeptic on fresh lives.

## Suggested order

1. **This week (laptop, about $0):** track A harness fixes (tie-breaking, resume, fast mode, readouts); start the
   spike-bit tissue's engines and its first growth GIFs; side-track tests T1-T4 begin.
2. **Weeks 2-3 (one rented GPU, about $25-70; a rented CPU box for a few hours):** teach, compile and evolve the
   spike-bit tissue (milestones M2-M4); in parallel run Pilot 2 phase 1 (track B, about $5-10) on the current model.
3. **Decision point (about 3 weeks):** compare the three pipelines on the same world and budget. If the tissue
   passes, take it to an FPGA (track F stages 3-4) and start the mouse-cursor world; if ES beats the GA by a lot, the
   current model stays alive and track C's matrix runs with ES; if neither beats its own reflex and the ceiling is near
   the reflex, change the world before the substrate (track D: occlusion, memory, sign flips).
4. **Then:** the integer ABI (track F stage 1) for whichever substrate continues; the niche map and a task family per
   life (track D); harder worlds; silicon only once a substrate and its ABI are frozen.

## Decisions needed from you

| # | Decision | My recommendation |
|---|---|---|
| 1 | Build the spike-bit tissue prototype (cells become small logic circuits; stepped time with random per-cell updates, checked by an asynchronous replay) | yes, 3 weeks, cap $150 |
| 2 | Rent compute: one GPU (40-80 GPU-h) and a 192-core CPU box for a few hours | yes, after resume and the bitwise check exist |
| 3 | Local capture and miss bits at the tapping cell as the only reward-like inputs (a local consequence signal, previously deferred) | yes; without it, nothing can be learned within a life |
| 4 | Per-channel face weights in the GRN model (only if track C runs) | yes |
| 5 | An integer ABI as the next reference contract | yes |
| 6 | "No central clock" defined as three testable rules (own times, every cross-site effect takes >= d_min, order-independent results) | yes |
| 7 | Exact replay required for evolution; free-running physical timing only for demos | yes |
| 8 | Fitness over a family of worlds, variety within a life, a wound world | approve the direction now; decide each after the niche map |
| 9 | Keep 4 layers (hidden planes) through Pilot 2 | yes |
| 10 | Keep the fixed tap cell at the centre; document the n_view founder prior as a units calibration | yes |
| 11 | A license for the public repository | your choice (MIT or Apache-2.0 are common for research code) |

## What we can hope to see

- The first body, evolved or trained, that **beats the hand-built reflex by passing signals across the body**
  (multi-hop local computation), and a readable account of how it does it.
- A body that **learns during its life**: after a mid-life motor flip its captures recover, and freezing its learnable
  bits removes that recovery.
- **Regeneration:** a body that loses half its cells, regrows and catches again; cell death finally given a job.
- **Hidden layers that matter**, once a world needs memory or prediction.
- **Generalisation** across a family of worlds and within-life changes.
- **A clear answer on what limited the GRN model**: search (ES against GA), primitives (face weights, plasticity), or
  the world.
- **An evolved body running bit-exact in hardware**, in real time on an FPGA, with measured gates, flip-flops and
  energy per cell; later one cell on a shared chip run.
- **Later worlds**: following a mouse cursor, reading a text stream.
