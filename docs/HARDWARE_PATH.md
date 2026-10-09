# Can cell-dev run faster on an FPGA or other custom hardware?

2026-10-09. This summarises four studies (mapping, platforms, throughput, codesign). A skeptic re-checked each one, and every number below is the corrected value.

**Labels.** **[M]** = measured in this repo or in the scratch kernels. **[S]** = sourced from outside (the URL and fetch date are in the Sources list at the end). **[E]** = estimated by a model or by reasoning. No hardware was synthesised or built.

**Terms.**
- **Box**: one rented 192-core CPU server (AWS c7a.48xlarge).
- **Pilot**: the real 29-run BODY-1 pilot, about 220 laptop-CPU-hours [M].
- **Fixed point**: a number stored as an integer with an implied scale. For example, Q16 means the integer divided by 65,536.
- **Integer ABI**: the same model in fixed point, with lookup tables in place of exp/log/tanh and integer timestamps. LIFE_ABI.md section 13 already reserves it as the "integer twin".
- **d_min = 0.5**: the shortest delay that any effect from one site to another may have.
- **PE (processing element)**: one small processor on a chip.
- **pw / pm**: person-weeks / person-months.

---

## 1. Short answer

**Custom hardware can run the cell logic. It would not make evolution much faster or cheaper at your current scale.**

**Today.**
- A whole pilot costs $6-16 as actually rented: one box for 1-1.5 h, including the idle tail [M, S prices].
- With every core busy at spot prices, the compute alone is about $1.8-2.4 [E from S].
- More speed is just more boxes. The 29 runs x 1,070 lives per generation are all independent.

**The cheapest speedups are on the CPU.**
- **Exact fast mode:** 1.24-1.35x [M], about 1 pw, with no change to the model.
- **Integer ABI on the CPU:** about 1.4-2.3x in total, fast mode included [E], for 4-10 pw. Per-tick arithmetic measured 2.1x faster and the membrane step 3.4x faster in microbenchmarks [M].

**Time-stepped GPU** (all cells advance together in fixed steps dt):
- Speed [E]:
  - H100: about 4.4x a box per wall-hour (2.6-6.6) at dt = 0.1, and 2.2-5.6x cheaper per unit of work.
  - L4: about 1.5x a box, and about 9x cheaper (5.7-13).
- The price is a lockstep clock inside the model. Arrivals that land in the same step as another input [M]:
  - 6-10% of a cell's spike arrivals at dt = 1/16
  - 1.6-2.7% at dt = 1/64
- Nobody has measured which dt leaves behaviour unchanged. At dt 1/16-1/64 the estimated gain spans 0.05-17x per dollar [E].
- Effort: 6-14 pw plus a statistical validation.

**FPGA (AWS F2, one AMD VU47P per instance):**
- **Bit-exact float64 port: no gain.**
  - AMD's exp/log cores are accurate only to 1 ULP [S], so glibc's algorithms would have to be rebuilt in hardware.
  - That gives an estimated 0.2-0.7x CPU cost-efficiency for 12-24 pm [E].
- **Integer design:**
  - Speed: about 0.2-1.2 of a box per FPGA, central 0.3-0.5 [E].
  - Cost per unit of work against today's CPU kernel: about 1.7-3x cheaper. The four estimates span 0.4-45x.
  - Against the integer CPU kernel it needs first: only about 0.8-2x [E].
  - Effort: 4-12 pm of FPGA work after the integer ABI exists [E].
  - At central estimates it never pays back.

**The rest:**
- **Neuromorphic chips** (SpiNNaker2, Loihi 2): no throughput gain, and they cannot be rented by the hour.
- **An asynchronous chip with one tile per cell:** not a throughput device. It is the long-term target.

**Where hardware does make sense: your long-term goal.** Three measured results make that path cheap:
1. **Exact parallel execution already exists.**
   - The ABI's window scheduler lets every site advance on its own and stops only at a fence every h <= d_min of model time.
   - It was bitwise identical to the production heap kernel in 528 of 528 life comparisons [M]: 3 checks, 4 evolved bodies, h = 0.5 / 0.25 / 0.125, non-zero tie and order seeds.
   - Each site needs only its own state and its neighbours' messages. This is the shape of a processor array.
2. **Fixed point does not change fitness.**
   - On all 11 pilot bests, with 1,024 new-seed paired lives each, F moved by -0.012 ± 0.020 [M]. For scale, three of the bests have F = 2.75, 3.51 and 6.83.
   - It is not behaviour-identical: final size shifts by up to about 4 cells.
3. **The precision traps are known** (section 3.2).

**Recommendation.** Do not build hardware for speed. Build the integer ABI now:
- it speeds up the CPU;
- it makes results bitwise portable across machines;
- it becomes the exact reference that any FPGA or chip must match.

After that, build one cell processor, then a small array.

---

## 2. The options

### Table A: speed and cost

"Speed" is per device and per wall-hour, compared with one box. "Cost" compares the cost per unit of work with rented CPUs; above 1 means cheaper. "Pays back after" is the CPU spending at which the dollars saved equal the engineering cost, valuing engineering at $3,000 per pw (an assumption) [E]. For scale, $10k is about 600-1,600 of today's pilots.

| Option | Speed (vs one box) | Cost per unit of work | Effort | Pays back after |
|---|---|---|---|---|
| CPU, exact kernel (today) | 1; a pilot in 1-1.5 h [M] | 1; $6-16 per pilot as rented, $1.8-2.4 fully used at spot [E/S] | 0 (resume and a pinned image: 0.5-1.5 pw) | — |
| CPU, exact fast mode | 1.24-1.35x [M] | 1.24-1.35x [M] | 0.5-1 pw | about $10k; the wall-time gain is immediate |
| CPU, integer ABI | about 1.4-2.3x, fast mode included [E] | same | 4-10 pw | about $35-50k; the real case is portability and a hardware reference |
| GPU, time-stepped | H100 about 4.4x (2.6-6.6) at dt 0.1, about 2.6x at dt 0.05; L4 about 1.5x [E] | H100 2.2-5.6x; L4 about 9x; at dt 1/16-1/64 (RTX 4090) 0.05-17x [E] | 6-14 pw + validation | about $35-40k, and only if a lockstep dt is accepted |
| GPU, exact windows on the integer ABI | RTX 4090 about 0.1-2 boxes, very uncertain [E] | unknown | 12-26 pw after the integer ABI | unknown (untested idea) |
| FPGA, bit-exact float64 port | about 0.04-0.13 box [E] | about 0.2-0.7x (worse) [E] | 12-24 pm | never |
| FPGA, integer life engines or time-shared PEs (AWS F2) | about 0.2-1.2 box per FPGA, central 0.3-0.5 [E] | about 1.7-3x vs today's kernel (0.4-45x across studies); 0.8-2x vs the integer CPU kernel [E] | 4-12 pm after the integer ABI | about $190k vs today's kernel; never vs the integer CPU kernel (central) |
| FPGA, spatial array (one PE per lattice site) | about 0.03-0.13 box; one body may need 1-4 FPGAs; one life in 4-13 ms vs 70-150 ms on a laptop core [E vs M] | about 0.2-0.7x [E] | 2-4 pm for a 37-PE prototype; 6-9 pm for a full region | never for throughput (it is a demonstrator) |
| SpiNNaker2 | far below 1 box per chip (about 1-15 laptop cores) [E] | no public price [S] | 2-6 pm + access | never for throughput |
| Loihi 2 | unknown (time-step rate unverified) | not rentable; INRC access free for qualified groups [S] | 2.5-8 pm + access | never for throughput |
| BrainScaleS-2 (analog) | not comparable: 512 neurons per chip, 1000x faster than biology [S] | research access (terms unverified) | 2-4 pm + calibration | never for throughput |
| Asynchronous / GALS tile chip (one tile per cell) | not a throughput device; real time at an estimated 0.3-1.6 nJ per cell per model unit [E] | Tiny Tapeout EUR 70 per tile, EUR 1,120 / 2,240 for a 16- / 32-tile slot; wafer.space $2-8k per 1,000 dies; chipIgnite $14,950 [S] | 1-2 pm for one cell; 6-18 pm for a multi-cell test chip; 6-12 months to fabricate [E] | the long-term goal only, after the ABI is frozen |

More on the FPGA integer design:
- One pilot would take 0.4-2 FPGA-hours, $0.8-4 on demand [E].
- F2 costs $1.98/h on demand and $0.659/h spot [S].
- The study ranges for this row disagree by up to about 10x, mostly over how many LUTs (FPGA logic cells) one engine needs.

### Table B: what changes in the model, and the main risks

| Option | What changes in the model | Main risks |
|---|---|---|
| CPU, exact | Nothing. | Bitwise drift across CPUs and glibc versions (libm picks FMA variants at load time). The torch mutation RNG must also be pinned. |
| CPU, fast mode | Nothing. The ledger is bitwise identical; only the verification hashes are skipped. | Gates and golden tests must keep using the full build. |
| CPU, integer ABI | A new arithmetic contract. Every life and every golden changes. No fitness effect on the 11 bests [M]; sizes shift by up to about 4 cells [M]. Integer time adds a few same-time coincidences. Still event-driven and clockless. | The tests so far were emulations: the world, the random-draw transforms and some state stayed float64, and walls, bounded FIFOs, a cheaper hash and the integer ledger were never built. No evolution has been run under it. |
| GPU, time-stepped | A model clock: lockstep dt, float32, behaviour depends on dt. A fixed tensor caps body size. | Breaks "no central clock" unless it is declared an approximation. The GPU's achieved fraction of peak is uncertain (6x swing). Faster conduction (d0 = 0.5) halves the usable dt. |
| GPU, exact windows | None beyond the integer ABI. | Gain unknown; thread divergence; never prototyped. |
| FPGA, float64 | None, if glibc is reproduced exactly. | Any glibc change breaks equality. Huge effort for no gain. |
| FPGA, integer engines | None beyond the integer ABI, if the hardware matches it bitwise. | The world/accountant is a serial unit that must also go into hardware, or the host becomes the bottleneck. Every model change must be built twice (C and hardware). Timing at 250 MHz across the chip's 3 dies is not guaranteed. |
| FPGA, spatial array | As the integer ABI, plus a fixed region with walls (an existing ABI rule, `fabric_R`). | Per 0.5-unit window the serial accountant handles 139-283 records and 33-57 receptor thinning tests [M]. Only about 20-25% of sites hold cells. Halving d_min nearly doubles a life's latency (1.9x [M]). |
| SpiNNaker2 | Needs the integer ABI (its cores have no float64). Can stay event-driven if the usual 1 ms timer loop is avoided. Growth needs pre-allocated slots. | Access and pricing are opaque; small user community. |
| Loihi 2 | Barrier-synchronised time steps (a model clock); fixed topology, so every site must be pre-allocated; GRN in microcode with no sigmoid. | Intel archived the Lava SDK on 2026-05-13 [S], and its successor is not public. |
| BrainScaleS-2 | Physical analog time: no exact replay, and chips differ. | Evolution may fit one chip's quirks; 512 neurons per chip. |
| Asynchronous tile chip | Exact if timestamps are carried as data. Without a replay guarantee if free-running oscillators set the timing. Growth means waking dormant tiles. | Long turnaround. The genome copy dominates each cell's area. Designing before the model stabilises. |

---

## 3. The long-term goal: cell logic natively on hardware

Prior work shows the idea is old but was never combined.
- Genome-carrying cell tissues on FPGAs exist: POEtic and BioWall [S].
- Fast FPGA spiking simulators exist: neuroAIx runs a cortical microcircuit at 20.36x real time [S].

All of them are synchronous and either fixed or small. None combines growth with a per-cell GRN. Your model is already closer to hardware than these were, because of the d_min rule.

### 3.1 What "optimal on hardware" will mean

In an estimated per-cell energy budget [E], GRN ticks take 65-87%, morphogen packets 8-12%, spikes plus arrivals 1-9%, receptor candidates 1-2%, and leakage 1-19%. The total is 0.3-1.6 nJ per cell per model unit, anchored to published 45 nm and Loihi per-operation energies [S].

So the knobs that matter in silicon are:
- **The GRN tick rate.**
- **The number of active genes.** Multiply-accumulates per tick are about G(G+9) + 23G: 384 at today's 8 active genes and about 770 at 16 [M arithmetic].
- **Bits of state per cell.** In a chip running at robot speed, leakage dominates, and leakage scales with stored bits.
- **Neighbour radius**, which sets the wiring.

Per cell, the fixed-point state is about 1.5-2 kbit [E]. The genome is 13.5 kbit at 16 bits [M], about 9x a cell's own state.

### 3.2 Choices to make now, so the hardware path stays cheap

**1. Make the integer ABI the next reference contract, folded into the planned ABI-4 cleanup.** That cleanup changes every life anyway. Widths that passed, from the two precision studies:

| Quantity | Width or grid | Evidence |
|---|---|---|
| Gene state g | Q16 (Q10 is the floor) | Q8 cost speck_s5 6.7% of F (z = -4.2) [M]. At lambda = 1/128 (possible by construction) a Q12 gene stalls 1.56% short of its target and a Q16 gene 0.098% short [M] |
| Sigmoid | 256-entry table, 12-bit output | error <= 0.008 [M] |
| exp, log (cell side) | exp2/log2 tables with 12 or more significant bits | error <= 0.002 [M] |
| GRN weights W, b | grid 1/64 or finer, range ±32 | evolved \|W\| reaches 23.7 [M] |
| Readout weights A, a0 | grid 1/128 or finer, range ±8 | a 1/32 grid cost s6 0.59 F and shrank bodies by 7.5-10.8 cells (replicated) [M] |
| GRN and readout sums | 8 fractional bits | [M] |
| Morphogens | 12-16 fractional bits, 3 integer bits | 4 bits cost up to 17% [M] |
| Traces f, r, rho | 8 fractional bits, 7 integer bits | r reaches 73 [M] |
| Twitch z | 8 bits or more | 4 bits cost lmax4_s5 8.4% (it moves the click thresholds) [M] |
| Sums of all kinds | integers, in any order | the sorted inbox and canonical-order float sums disappear |

Store the genome itself on these grids and let mutation act on the grid, so evolution never sees off-grid values.

**2. Use integer time with unbiased rounding.**
- Today's event times are full float64 values, so integer time is a real but tiny change [the throughput re-check read this in kernel.c].
- Rounding rules:
  - round delays and tick periods to the nearest step;
  - round threshold crossings up;
  - keep drawing receptor candidates as Poisson skips. A Bernoulli trial per step would cost 2-3 million draws per life against about 93k candidates [E].
- Measured, rounding every time up:

  | Grid | Rate lost (exact) | dF |
  |---|---|---|
  | 1/64 | 1.6% | -0.00 |
  | 1/16 | 6.1% | -0.08 |
  | 1/4 | 21.8% | -0.67 |

- Even with unbiased rounding, a 1/4 grid is not neutral: +0.11 ± 0.02 over 11 bodies [M], cause unknown.
- At 1/64, 1.1-2.1% of site batches hold 2 or more events, against 0.11-0.25% in the exact model [M]. The existing batch-order rules resolve these deterministically.
- Any grid from 2^-8 (measured safe, with margin) to section 13's 2^-20 is fine. A finer grid only costs timestamp bits.

**3. Keep the d_min rule as a hard design rule for every change.**
- Every effect from one site to another, the world's RECEPTOR events included, must take at least d_min, and nothing may read another site with zero delay.
- This rule is what makes barrier windows, local handshakes and exact replay possible on parallel hardware.
- Faster conduction (d0 = 0.5) with d_min = 0.25 was neutral under integer arithmetic (+0.013 ± 0.045 [M]). But it doubles the number of windows, and a spatial array's latency rises about 1.9x [M].
- With a radius-2 gene, two-hop messages must also take at least d_min.

**4. Decide how the world fits in.**
- The CATCH/SPECK accountant (dot physics, receptor thinning, records in canonical order) is the one global, serial part. In hardware it is a hub that has to sync with every sense and act cell at least every d_min.
- Either give the world an integer spec inside the bitwise contract, or declare it outside the contract.
- Either way, a per-region receptor rate or a tighter thinning bound would remove most rejected receptor candidates. These are 43-60% of all events, and about 95% of them are rejected in SPECK [M]. It would help the CPU too.

**5. Bound what hardware has to size.**
- **A fixed region with walls.** `fabric_R` = 7 x 4 planes (676 sites) left 97-100% of the bests' lives unchanged, and R = 6 stayed within 0.2% [M]. But speck_s0 reaches 290 cells at T = 1536, and 28% of random founders trip the n_max guard [M], so the region size is a real parameter.
- **Bounded arrival queues per neighbour slot**, with an overflow rule.
- **Possibly a cheaper hash.** splitmix64 needs 64x64-bit multiplies, about 16-20 DSP blocks per pipelined unit [E]. A 32-bit hash keyed by (site, birth index, counter) would be cheaper, but is untested.

**6. Shape the planned model changes for hardware.**
- **Per-time gene laws:** use the same exp2 unit. This makes the tick rate, the dominant energy knob, a free implementation choice.
- **Per-channel face weights:** a few small registers per face. Dropping `a_c*shat` later would also remove the per-tick division.
- **Gene duplication:** stays inside a 16-gene engine, but doubles the multiply-accumulates. Gaussian mutation never produces exact zeros (src/genome.py), so hardware could only exploit sparsity with gene deletion or a per-weight enable bit.
- **Radius gene:** in-plane contacts go from 6 to 18, so messages and wiring grow about 2.5-3x [E]. Cap the radius at 2 and price it per hop.

**7. Pricing by hardware energy: add a panel now, prices later.**
- Re-pricing the 11 bests by estimated energy changed F by at most 0.033 and kept their ranking (rank correlation 0.99-1.00) [M lives, E energies]. Today `c_live` already acts as a per-tick price, because every body ticks at the same rate with similar work per tick.
- Add a post-hoc "hardware energy" panel to the analysis. All the counts are already in the ledger.
- Introduce per-tick, per-MAC, per-packet or per-hop prices only together with the change that makes that quantity evolvable (a per-cell tick period, duplication, the radius gene):
  - make them a split of `c_live` that keeps the total calibrated;
  - test them as an A/B arm.

### 3.3 What "no central clock" means on hardware

There are several kinds of "clock". Only some of them enter the model:

| Kind of clock | Example | Does the model see it? | Exact replay? | Verdict |
|---|---|---|---|---|
| 1. Machine clock, with event times carried as data | the CPU today; an FPGA engine at 250 MHz | no | yes | fine |
| 2. Barrier fence every h <= d_min of model time | the ABI's window scheduler; a PE array | no: bitwise equal to the heap kernel, 528/528 [M] | yes | fine; a progress fence, not a model clock |
| 3. Local promises, no global barrier (GALS, Chandy-Misra-Bryant) | a tile chip where each tile tells its neighbours "nothing from me before t + d_min" | no | yes (reasoning; not built) | the most faithful clockless implementation; the world still syncs with sense and act cells every d_min |
| 4. A grid on event timestamps | the integer ABI at 2^-8 | barely: a few more same-time ties | yes, against the integer reference | fine at 1/64 or finer |
| 5. Lockstep time steps dt | time-stepped GPU; Loihi 2; SpiNNaker's usual 1 ms timer | yes: every cell updates each step | only against a stepped reference | breaks the requirement; acceptable only as a declared approximation |
| 6. Physical time | free-running per-cell oscillators; asynchronous or analog circuits; BrainScaleS-2 | there is no clock at all | no | truly clockless, but not deterministic |

Kinds 4 and 5 differ in an important way. A timestamp grid leaves every cell acting at its own jittered times, so nothing updates together. Lockstep updates every cell at every step.

Kind 6 loses more than bitwise replay:
- It loses forks.
- It loses the place-keyed shared random draws that give every genome in a generation the same physics. Selection would become noisier.
- Evolution would need the hardware in the loop.

### 3.4 What would change in your requirements

- **"No central clock" becomes three testable rules:**
  1. Each cell acts only on its own events, at its own jittered times; nothing updates all cells together.
  2. Every effect between sites, the world included, takes at least d_min.
  3. Results are bitwise identical for any processing order, tie seed and order seed. The window-equals-heap tests already check this.

  Machine clocks, barrier windows of h <= d_min and integer timestamps are then implementation details. Lockstep dt is not allowed in the model.
- **The bitwise reference moves** from "float64 plus glibc" to the integer ABI.
- **The region size becomes a world parameter** (`fabric_R` already exists), and the world must be either integer-specified or declared outside the contract.
- **Physical-time silicon** would mean accepting statistical rather than bitwise reproducibility. That can wait until a chip exists.
- **Minimal hard-coding is preserved.**
  - Bit widths, grids and tables are number formats, not behavioural rules.
  - Walls are an existing ABI rule.
  - The only new fixed rules are the rounding rules.
  - No roles, identities or schedules are added.

---

## 4. Staged roadmap, with gates

**Stage 0 — now, days, CPU only.**
- Merge exact fast mode (1.24-1.35x [M]).
- Add resume/checkpointing and a pinned image.
- Benchmark a rented box for 10 minutes. The server-core speed factor of about 1.7-2.0x a laptop core is an estimate.
- Write the clock policy (3.4) and the d_min rule (3.2, item 3) into LIFE_ABI.md.
- Add the per-cell "hardware budget" and energy panel to the analysis:
  - state bits
  - multiply-accumulates per tick
  - messages per unit
  - neighbour slots
- No gate is needed; these are cheap.

**Stage 1 — the integer ABI, 4-10 pw.**
- Build:
  - a C kernel and a Python reference that are bitwise equal;
  - the window scheduler equal to the heap under the integer ABI;
  - an integer world spec, or the world explicitly outside the contract;
  - each structural change (walls, the queue overflow rule, the hash) as its own test arm.
- **Gate**, on all 11 pilot bests with at least 1,024 new-seed paired lives each:
  - pooled dF within about ±2% of F (95%);
  - no body with |z| > 3 and |dF| > 0.2;
  - size shifts under 5 cells;
  - a founder-census rank correlation of at least 0.98 between float and integer. For scale: float against float on new seeds gives 0.953, and the emulation gave 0.993 [M].
  - Also measure the CPU speedup.

**Stage 2 — an evolution A/B, about one pilot of compute (a few dollars).**
- Run 3 SPECK seeds under the integer ABI and 3 under float, compared at matched generations. This is the real test that evolution loses nothing; so far only transplants and founders were checked.
- **Gate:** evolved F and the evolved mechanisms (column reflex, voting, coincidence detection, inhibition, gradient-made directional synapses) fall within the seed-to-seed range. Then adopt the integer ABI as the reference and re-baseline the goldens.

**Stage 3 — one cell processor.**
- Write it in Vitis HLS from the C integer kernel. Co-simulate it in Verilator against the reference, comparing per-site event digests on thousands of random lives, then synthesise it.
- Stages 3 and 4 together take about 2-4 pm [E], assuming FPGA experience.
- **Gate:**
  - the processor is bitwise equal to the reference;
  - you now have real LUT, DSP and memory counts per processor, the main unknown in every FPGA estimate. Under about 1.8k LUTs per processor, a whole body region fits on one VU47P [E]. Otherwise plan time-shared processors or several FPGAs.

**Stage 4 — a small spatial array.**
- One plane of radius 3 (37 processors) on a dev board or an F2 instance, with the world unit designed in from the start.
- Then a GALS / local-promise version: the clockless implementation, about 3-6 pm on top [E].
- **Gate:** bitwise equal to the reference while running a CATCH body in real time. Measure latency and power.

**Stage 5 — silicon, only after the ABI is frozen.**
- First, one cell on a Tiny Tapeout multi-tile slot (EUR 1,120-2,240 [S]; whether a full cell fits is an estimate).
- Then a GALS array of about 30-75 cells on wafer.space or chipIgnite ($2-15k [S]); 6-18 pm and 6-12 months to fabricate [E].
- **Gate:** stage 4 works, and you have decided physical time against timestamps (D3).

**Side branch: throughput hardware.** Only if compute spending grows to tens of thousands of dollars per year.
- Measure first, for 1-2 pw and under $20:
  - a CUDA prototype of the cell step on a rented L4, to measure the achieved fraction of peak;
  - a CPU time-stepped reference, to measure how F shifts at dt = 0.25, 0.1 and 0.05.
- Proceed only if F at dt >= 0.05 matches within noise and the achieved fraction is at least about 0.15.
- Prefer an exact window-synchronous GPU kernel on the integer ABI to time-stepping.
- FPGA life engines are not recommended: they lose to the integer CPU kernel per dollar.

---

## 5. Decisions for you, and open uncertainties

### Decisions

- **D1. Adopt the integer ABI as the next reference, folded into the ABI-4 cleanup?**
  - Gain: CPU speed (about 1.4-2.3x with fast mode [E]), bitwise portability across machines, and an exact reference for any hardware.
  - Cost: every golden changes, and pilot results become comparable only statistically.
  - My recommendation: yes.
- **D2. Define "no central clock" as the three rules in 3.4?** That allows machine clocks, barrier windows and timestamp grids, and forbids lockstep time steps inside the model. Recommendation: yes.
- **D3. Must future hardware replay lives exactly?**
  - If yes: hardware with timestamps carried as data (kinds 1-4).
  - If no: physical-time silicon becomes possible (kind 6), but you lose replay, forks and shared per-generation draws.
  - Recommendation: require exact replay for evolution, and allow physical time only for demos.
- **D4. The world in the bitwise contract or outside it?** It has to go into hardware eventually, so a small integer world spec is the cleaner choice.
- **D5. Time grid: 2^-8 or section 13's 2^-20?** Both are fine; it is timestamp bits against fewer ties.
- **D6. Genome storage in a silicon tissue** (matters only at stage 5):
  - each cell keeps its own copy and copies it to its daughter at division, as Embryonics did: about 37-75 cells per 15 mm² on SKY130 [E];
  - or one shared read-only copy streamed to all tiles: about 150-300 cells per 15 mm² [E]. This carries no state between cells.
- **D7. Hash:** keep splitmix64, or test a cheap 32-bit hash keyed by site and birth index as a stage-1 arm?
- **D8. d_min under faster conduction:** keep 0.5 (cheapest for hardware), or 0.25 (neutral so far, but twice the windows)?

### Open uncertainties

- **Every hardware throughput and cost number is an unsynthesised estimate.**
  - The biggest unknowns are the LUTs per processor or engine (2.6-4x swings) and the GPU's achieved fraction of peak (6x swing).
  - The four re-checks of FPGA cost per unit of work disagree by up to about 10x.
- **The fixed-point tests were emulations.**
  - The world, the random-draw transforms, traces, twitch and the decay divisions stayed float64.
  - Walls, bounded queues, a 32-bit hash and an integer ledger were never built.
  - No evolution has been run under integer arithmetic.
- **Integer arithmetic is fitness-neutral but not behaviour-identical.** Final sizes shifted by up to about 4 cells, significantly in 7 of 11 bodies [M].
- **The cause of the 1/4-grid effect is unknown.**
- **The 250 MHz F2 clock is the shell's interface clock.** User logic may use other clocks (AWS clock recipes), but timing closure across 3 dies at about 70% use is not guaranteed.
- **Not verified:**
  - Alveo card prices
  - RTX 4090 specs
  - AWS p5 price URL
  - Loihi 2 time-step rate
  - SpiNNaker2 core clock and access terms
  - Vivado licensing on F2
  - SKY130 flip-flop area
  - Europractice prices (checked only against a fetched summary)
  - details of Tufte & Haddow 2005
  - any NCA-on-FPGA work

  The web-search budget ran out, so sources were re-opened by URL only.
- **Effort figures assume FPGA expertise.** Once hardware exists, every model change has to be built twice.
- **Seeds.** The seed formula reached the studies garbled. They used `fresh_seeds` bases of 37,100,000 to 37,800,000 instead of 37,900,000, so seeds 37,900,000 and up remain unused.

---

## Sources (all fetched 2026-10-09)

Project data: `results/catch_pilot/compute_audit.json`, RESULTS.md "2026-10-09 — BODY-1 pilot" part 5, `results/catch_pilot/mechanisms.json`, `docs/LIFE_ABI.md` sections 6.3, 11.2 and 13.

Study records: `results/hardware_study/hardware_study.json` (every study and its skeptic's re-check; the scratch scripts were not kept).

**FPGA and cloud**
- AMD PG060 Floating-Point Operator v7.1 (2020-12-16), exp/log accurate to 1 ULP: https://docs.amd.com/go/en-US/pg060-floating-point
- AMD DS890 v4.10 (2026-05-21), Table 17. VU47P: 1,303,680 LUTs, 9,024 DSPs, 2,016 BRAM36, 960 URAM, 16 GB HBM. https://docs.amd.com/go/en-US/ds890-ultrascale-overview (opened by one study; later attempts on amd.com timed out)
- AWS F2 (VU47P, 16 GB HBM per FPGA): https://aws.amazon.com/ec2/instance-types/f2/
- f2.6xlarge: $1.980/h on demand, $0.659/h spot. https://instances.vantage.sh/aws/ec2/f2.6xlarge
- f2.48xlarge: $15.84 / $4.799. https://instances.vantage.sh/aws/ec2/f2.48xlarge
- F2 shell clock 250 MHz: https://raw.githubusercontent.com/aws/aws-fpga/f2/hdk/docs/AWS_Shell_Interface_Specification.md
- Other F2 design clocks: https://github.com/aws/aws-fpga/blob/f2/hdk/docs/Clock_Recipes_User_Guide.md

**CPU and GPU prices**
- c7a.48xlarge: $9.853/h on demand, $3.398/h spot. c8a.48xlarge: $10.346 / $5.549. instances.vantage.sh (the c7a.48xlarge and c8a.48xlarge pages)
- RunPod: H100 SXM $2.69 / $3.99, H100 PCIe $1.99 / $2.89, L4 $0.59, RTX 4090 $0.89 (the 4090 price was not re-checked). https://www.runpod.io/pricing
- AWS p5.48xlarge: $55.04/h ($6.88 per GPU). The URL was not recorded, so treat this as unverified.

**Neuromorphic**
- Davies et al. 2018, Loihi (discrete time steps, barrier synchronisation, 23.6 pJ per synaptic op): https://redwood.berkeley.edu/wp-content/uploads/2021/08/Davies2018.pdf
- Loihi 2: https://arxiv.org/html/2310.03251
- Lava archived 2026-05-13: https://github.com/lava-nc/lava
- INRC: https://www.intel.com/content/www/us/en/research/neuromorphic-computing.html
- SpiNNaker2 (152 Cortex-M4F cores per chip): https://arxiv.org/html/2401.04491
- SpiNNcloud (no prices listed): https://spinncloud.com/
- BrainScaleS-2 (Pehle et al. 2022): https://arxiv.org/abs/2201.11063

**Chip fabrication**
- Tiny Tapeout prices: https://app.tinytapeout.com/_build/assets/invoice-WoZjomWD.js
- Tiny Tapeout shuttles (next deadlines 2026-11-30 and 2026-12-07; delivery about 2027-06): https://tinytapeout.com/chips/
- wafer.space: https://wafer.space/
- chipIgnite: https://chipfoundry.io/

**Energy and prior art**
- Horowitz, ISSCC 2014 (per-operation energies at 45 nm): https://gwern.net/doc/cs/hardware/2014-horowitz-2.pdf
- neuroAIx (Kauth et al. 2023): https://www.frontiersin.org/articles/10.3389/fncom.2023.1144143/full
- POEtic: https://cordis.europa.eu/project/id/IST-2000-28027
- BioWall: https://en.wikipedia.org/wiki/BioWall
