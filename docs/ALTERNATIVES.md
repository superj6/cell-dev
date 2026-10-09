# Alternatives to the cell model: what to build next (2026-10-09)

**Your question:** "do you have ideas for any alternatives to the cell based evolution that may be able to better utilize current hardware or machine learning directions? ..."

**Your two clarifications, both treated as binding:**
1. The organism's rollout must be hardware-native: its units, messages, growth and any learning during the life. The outer loop that searches or trains it can use any GPU or ML machinery.
2. Any direction is open. Rank them by how cheaply and quickly they produce outcomes you can watch and measure.

**How this was put together:**
- Five research passes covered developmental and NCA systems, local learning rules, networks that grow, hardware-native evolution, and current ML directions.
- Four judges scored the candidates: fidelity to your goals, hardware-native runtime, compute needed for visible outcomes, and scientific risk.
- Everything was checked against RESULTS.md, docs/POST_PILOT_CALLS.md, docs/HARDWARE_PATH.md, docs/LIFE_ABI.md and src/.
- Labels: **[M]** measured (in the repo or in scratch benchmarks), **[E]** estimated, **[S]** quoted from a source. Scratch benchmarks (alt/ncadev) are not kept; the study record is results/alternatives_study/alternatives_study.json.

**Terms used below:**
- **NCA (neural cellular automaton).** Every lattice site runs the same small neural network on its own state plus its neighbours' messages. The network's weights are the genome, and cell types appear as different stable states of that one rule.
- **Logic tissue / netlist.** The cell's rule is a fixed circuit of logic gates (AND, XOR and so on). A "netlist" is the list of gates and their wires, which is exactly what an FPGA or chip implements.
- **Bit-slicing.** One bit from each of 64-512 separate lives is packed into one machine word, so a single AND/OR/XOR instruction advances all of them at once.
- **Differentiable logic (DiffLogic).** During training each gate is a soft mixture of the 16 possible two-input functions, so gradients can flow. Afterwards each gate is "hardened" to its single most likely function.
- **Distillation.** A big, easy-to-train "teacher" model is copied into a small "student" by training the student to give the same outputs for the same inputs.
- **CGP (Cartesian genetic programming).** Evolution of circuits by mutating gate types and wires. Gates that nothing reads are inactive, which allows neutral drift.
- **ES (evolution strategies).** Each generation tries many small random changes to one parent genome, then moves the parent toward the better-scoring changes, weighted by score.
- **Paired lives (CRN, common random numbers).** Two genomes are scored on exactly the same random lives (same targets, same Poisson draws), so most of the Poisson noise cancels in their difference.
- **Straight-through estimator.** A training trick: the forward pass uses a hard 0/1 bit, and the backward pass pretends it was a smooth sigmoid, so gradients still flow through bits.
- **LFSR.** A tiny shift-register random-number generator (a handful of flip-flops and XORs). Seeded per cell, it produces the same "random" sequence in software and in silicon.
- **Function-preserving growth.** Adding a unit, gene or wire so that behaviour is exactly unchanged at that moment (for example a new gate that passes its input straight through). The standard ML reference is Net2Net.

---

## Short answer

Yes. Under your two clarifications, the best plan separates **what the organism is** from **how it is trained**.

1. **The organism: logic tissue.** Each cell is a few dozen state bits plus one small gate circuit shared by all cells. It exchanges value-less spike bits with its neighbours, divides, dies and steers the dot.
   - The simulator *is* the netlist, so there is no gap between training-time simulation and hardware.
   - Bit-sliced, a stand-in ran in 2.6-7.6 ms per life on one laptop core [M]. Today's kernel takes about 100 ms.
   - A frozen rule is hardwired, so cells need no genome copy. In the GRN tile the genome copy is about 9x the cell's own state.
2. **The trainer: a shared neural cell (NCA) on a GPU or the laptop.** Give it exactly the same bit interface as the logic cell and train it with gradients through windows of continuous lives. This is where current ML is strongest, and it gives the fastest visible results: a growth-and-regrowth GIF in about a day on the laptop, a grown body chasing the dot in about two weeks. The trained rule is then compiled into gates.
3. **Plastic faces: learning synapses in today's exact kernel.** A cheap, decisive side experiment with no sim-to-hardware gap. Can plain spike-timing plasticity (STDP) rebuild "excite from below, inhibit from above" without the morphogen chemistry that costs s5 10.1 F when removed? It needs about a week of kernel work and under 1 CPU-h of runs.
4. **CellCode: an LLM writes the cell's integer event handlers, and the exact kernel judges them.** A dark horse. It produces the most readable artefacts, but it is unproven on noisy scores.

**What I would build first: "spike-bit tissue".**
- The organism is direction 1.
- It is taught by direction 2, then compiled to gates and refined by evolution inside the bit-exact runtime.
- Direction 3's tests run alongside on the current kernel, together with ES and paired lives as a fix to the current search.
- It keeps one continuous life, spikes as bits, local rules, growth and death.
- It relaxes event-driven continuous time to steps with random per-cell update enables. Those steps can still run on clockless silicon, with no global clock, through local handshakes (section 3.4).
- About three weeks and under about $150: GIFs from week 1, a hardware-native body that chases by week 3, and a pre-registered comparison against the current model.

**The pilot points at search as much as at the cell.**
- In the same LIF substrate, the hand-placed ring-4 router beats the best tuned reflex by +2.25 ± 0.10 F (GS2). Written as a GRN genome it grows and works (GS5).
- Evolution never found it, for three reasons:
  - per-life reliability is 0.026, so selection cannot see small differences;
  - each child is about 0.19 F worse than its parent;
  - runs collapse to one breed within 2-119 generations.
- So the recommended plan changes the search as well: gradients for the continuous part, 64-256 paired lives per genome in the bit engine, and several lineages kept alive. The side track measures how much of the pilot's shortfall was search alone.

**Ranking at a glance.** Judge scores are out of 10: fidelity / hardware runtime / compute-to-visible / scientific risk.

| Direction | Role in the plan | Judges | First visible result | Runtime on silicon |
|---|---|---|---|---|
| 1. Logic tissue | the organism | 7 / 9 / 5 / 7.5 | hand-written reflex netlist chasing: ~1 week | a few hundred to 1k gates per cell, bit-exact |
| 2. Shared neural cell (NCA) | the teacher; fastest visuals | 7-8 / 4.5-6 / 7-8 / 5.5-7 | growth + regrowth GIF: ~1 day | int8 MLP per cell (heavy) unless compiled |
| 3. Plastic faces | side track; within-life learning | 8 / 8 / 6 / 8 | learned weight maps: ~1 week | today's tile plus a trace-learning engine |
| 4. CellCode | alternative search operator | 7 / 7 / 5 / 6.5 | ~2 weeks | microcode for a per-tile core |

---

## 1. The four directions

### Direction 1. Logic tissue: each cell is a small gate circuit, and spikes are bits

This merges "Logic tissue: differentiable-logic CA" (NCA pass) and "Logic tissue: evolved gate-circuit cells, bit-sliced" (hardware pass).

**Unit and messages.**
- **State.** A site holds 32-64 bits:
  - alive and newborn bits;
  - a few polarity bits;
  - a 3-4 bit counter that can play the membrane;
  - free "gene" bits;
  - a couple of memory bits per face;
  - an inbox of latched incoming spikes.
- **Rule.** One netlist of about 128-1,000 two-input gates, shared by every cell, is the genome. A gate is a 4-bit truth table plus two input pointers, so a genome is 3-25 kbit, the same order as today's 13.5 kbit.
  - **Inputs:** own bits, the inbox, receptor and contact bits, a plane cue, and a few random bits from the cell's own LFSR.
  - **Outputs:** next state, 2 spike bits, divide and its direction, die, twitch and tap.
- **The membrane is not a given.** A leaky integrator becomes one possible circuit (a counter), so evolution and training can build coincidence detectors, latches and voters directly. s4's voting sensor ("fire on 2 own events, or 1 own plus 1 neighbour, never on 1") is a few dozen gates [E].
- **Messages.** 2 value-less bits per update, as today's two spike channels. They are delivered through per-edge delay lines and latched in the receiver's inbox until it next updates.

**Learning.**
- **Outer loop, any of three:**
  - (a) CGP evolution of gate functions and wiring, with neutral drift through inactive gates;
  - (b) DiffLogic gradient training of a relaxed circuit, then hardening;
  - (c) distillation from a trained teacher (direction 2), then CGP refinement.
  - The plan in section 3 uses (c), with (a) inside the runtime.
- **Inner loop (within the life):** only through state bits. Per-face memory bits written by the cell's own rule are a binary synapse, so a learning rule can emerge rather than be fixed. It is weaker than continuous weights.

**Growing without losing what was learned.**
- Daughters copy the mother's state bits, so anything a cell has latched (a face bit, a gene pattern) spreads with growth.
- The genome grows by adding pass-through gates or switching on inactive nodes, which leaves behaviour bitwise unchanged.
- The rule does not depend on body size. DiffLogic CA's checkerboard rule, run on a grid four times larger for four times longer, "works just as well in this new setting".

**Multidirectional circuits.** Any recurrent circuit along lattice paths. A→B depends on B's handling of the face facing A, and B→A on A's handling of the face facing B, so the two directions are independent. Inhibition, latches and feedback are just gates. Long range needs relays (or wire slots, section 5).

**Why GPUs now and hardware later.**
- **Training throughput.** It needs no GPU at all, which is unusual and useful. Measured stand-ins:
  - **C, one laptop core:** random 512-gate netlist on 300 sites, 4,096 steps. 7.6 ms per life interpreted, 4.2 ms compiled, 2.6 ms with AVX2 over 256 lives [M].
  - **numpy:** 900 sites × 1,000 gates × 1,024 steps, 64 lives per word, Python overhead included: 21.6 ms per life [M].
  - **Caveat:** the C stand-in had one ring neighbour rather than 8 hex-prism faces, and no world, receptor sampling or growth bookkeeping.
  - **Expectation:** about 5-15x below today's kernel per core once those are added [E]. It also gives 64-512 paired lives of one genome per word for free, which is exactly what the Poisson noise needs.
- **On silicon.**
  - A hardwired cell is a few hundred to 1k gates plus about 60 flip-flops [E]. A programmable cell (truth tables in registers) is roughly 1-3k LUT6 [E, unverified].
  - It plausibly fits one Tiny Tapeout tile at EUR 70 [S, fit not verified].
  - It is orders of magnitude below the GRN tile's estimated 0.3-1.6 nJ per cell per model unit, which HARDWARE_PATH notes is dominated by GRN ticks (65-87%).
  - The bit-sliced simulator is the netlist, so the sim-to-hardware gap is zero apart from timing, which section 3.4 closes.

**Shown in the literature.**
- **Logic CA.** Miotti, Niklasson, Randazzo & Mordvintsev 2025, Differentiable Logic Cellular Automata, https://google-research.github.io/self-organising-systems/difflogic-ca/.
  - Learned rules: Game of Life with 336 active gates; a checkerboard with 22 gates, 6 after pruning; a lizard grown with 577 gates.
  - Timing: a synchronously trained rule still worked under asynchronous inference, and asynchronous training was "relatively easy" for the checkerboard.
  - Stated limitation: complex shapes needed extensive hyperparameter tuning.
- **Gate networks.**
  - Petersen, Borgelt, Kuehne & Deussen 2022, Deep Differentiable Logic Gate Networks, https://arxiv.org/abs/2210.08277: over a million MNIST images per second on one CPU core.
  - Petersen, Kuehne, Borgelt, Welzel & Ermon 2024, https://arxiv.org/abs/2411.04732: 86.29% on CIFAR-10 with 61M gates. Library: https://github.com/Felix-Petersen/difflogic.
- **Networks that compile to FPGA lookup tables.**
  - Umuroglu, Akhauri, Fraser & Blott 2020, LogicNets, https://arxiv.org/abs/2004.03021: quantised networks with small fan-in convert directly into a netlist of truth tables, with under 15 ns latency and hundreds of millions of inferences per second on an FPGA.
  - Bacellar et al. 2024, Differentiable Weightless Neural Networks, https://arxiv.org/abs/2410.11112: lookup-table networks trained by gradient that beat prior FPGA solutions on latency, throughput, energy and area.
- **Evolved circuits.** CGP (Miller & Thomson, late 1990s). Only a summary was opened, https://en.wikipedia.org/wiki/Cartesian_genetic_programming; the original papers were behind a paywall.
- **Rotation-invariant rules.** Mordvintsev, Randazzo & Fouts 2022, Growing Isotropic NCA, https://arxiv.org/abs/2205.01681: symmetry is broken by the seed or by asynchrony.
- **Gap.** No published logic CA steers a body in closed loop, learns within a life, or was evolved rather than gradient-trained on a noisy task.

**What it relaxes.**
- **Relaxed:**
  - continuous event times, which become steps with random per-cell enables;
  - the continuous membrane and analog GRN, which become counters and gene bits.
- **Kept:** value-less spikes, one continuous life, growth, death, local rules and one shared genome.
- **Why it is worth it:** it is the only direction where the trained artefact is the hardware itself.

**Risks.**
- **Search can stall.** CGP on large circuits with noisy closed-loop fitness may stall, since single gate edits are often destructive. Gradient training of relaxed gates over long horizons is unproven. Hence the teacher.
- **Graded integration costs gates.** Gains and time constants must be built from counters.
- **Least biological.** It is the least bio-like of the four, and within-life learning is limited to bits.

### Direction 2. A shared neural cell (NCA family): the fast trainer and the quickest visible results

This merges Grow-and-Act NCA (NCA pass), Vector-message tissue (hardware pass), Shared in-context cell (frontier pass) and Maturing tissue (growth pass).

**Unit and messages.**
- **State.** Each lattice site holds 16-32 numbers: an "alive" value, a polarity (the cell's own front), and free channels. Some free channels can stay fast like a membrane, others slow like genes.
- **Rule.** One small network shared by all cells (an MLP or GRU of 2-12k parameters) is the genome.
  - **Reads:** own state, the incoming face messages, local receptor input and a noise input.
  - **Writes:** a state update, outgoing messages, divide and die decisions with a direction, and twitch or tap.
- **Messages.** Small vectors per face, or, as recommended here, the same 2 spike bits as the logic cell, made trainable with straight-through gradients.

**Learning.**
- **Outer loop, gradient:** backprop through time (BPTT) on windows of persistent lives ("pool training"). About 1,024 lives are each advanced 32-64 steps per update and written back, so each is still one zygote-to-death life.
  - **Training aids.** A soft-edged capture disk and expected (not sampled) receptor rates, plus a learned critic that values the rest of the life beyond the window (the SHAC recipe).
  - **Selection** always uses the real Poisson world with a hard disk.
- **Outer loop, evolutionary:** Population-Based Training (PBT). 8-16 lineages train in parallel, and the worst periodically copies the best and perturbs its hyperparameters. This keeps several breeds alive instead of collapsing to one.
- **Alternative arm:** ES with paired lives on the true score, no gradients through the life. It suits discrete growth naturally but needs large populations in about 10k dimensions.
- **Inner loop:** the cell's state dynamics. Drawing the world per life (motor sign, target speed, receptor density) forces adaptation within the life (in-context learning as in VSML and GPICL).

**Growing without losing what was learned.**
- **Size.** The rule is identical in every cell and independent of body size. Train at a cap of 16-64 cells, then raise the cap and continue with the same weights.
- **Inheritance.** Daughters copy the mother's state.
- **Capacity.** It grows without changing behaviour: new channels start with zero output weights, and a duplicated hidden unit splits its outgoing weights with its copy (Net2Net).
- **Newborns.** A newborn flag lets the rule keep new cells quiet until they fit in, and a "birth deficit" readout measures whether it does.

**Multidirectional circuits.** Any directed recurrent circuit along lattice paths, because every face is read separately. A neighbour-index table instead of a dense box also allows grown long-range wires later.

**Why GPUs now and hardware later.**
- **GPU-native.** One step is a gather from 8 neighbours plus one batched small matrix multiply.
- **Measured [M]:**
  - forward plus backward, 242 sites, 1.9k parameters, 64 lives, 32-step windows: 89 µs per trained life-step on this laptop CPU. A Growing-NCA-scale training run is therefore about 30 minutes locally, so the first growth GIF needs no GPU.
  - forward only, a dense 900-site box: 222 ms per life on 12 threads, and 0.31-0.67 CPU-s per life on one core for 300 cells. That is 3-25x *more* CPU time per life than today's kernel.
- **On a GPU [E]:** about 1-3k lives per second forward on a 4090-class card. The real gain is gradient information per batch, not lives per dollar.
- **On silicon:** an int8 MLP per cell is local, fixed point and bounded in fan-in, so it is legal in your sense. But at about 5-12k multiply-adds per update it is heavy, which is why the plan compiles it into gates.

**Shown in the literature.**
- **Growth and repair from one shared rule.**
  - Mordvintsev, Randazzo, Niklasson & Levin 2020, Growing Neural Cellular Automata, https://distill.pub/2020/growing-ca/. About 8k parameters, pool training, regeneration, and a random 50% per-cell update mask to avoid global synchronisation.
  - Randazzo et al. 2020, Self-classifying MNIST Digits, https://distill.pub/2020/selforg/mnist/: body-wide agreement through local messages only.
  - Sudhakaran et al. 2021, https://arxiv.org/abs/2103.08737: 3D NCAs grow and regrow functional machines.
  - Horibe, Walker & Risi 2021, https://arxiv.org/abs/2102.02579: evolved NCAs regrow soft robots that partly regain locomotion.
- **Control.**
  - Variengien, Nichele, Glover & Pontes-Filho 2021, https://arxiv.org/abs/2106.15240: an NCA controls a cart-pole and tolerates input deletion.
  - Nadizar, Medvet, Nichele & Pontes-Filho 2022, https://arxiv.org/abs/2204.02099: spiking NCAs, one per voxel with only local information, control soft robots competitively and adapt better to unforeseen changes. This is the nearest published analogue of spiking cells steering a body.
  - Hamon, Etcheverry, Chan, Moulin-Frier & Oudeyer, Sensorimotor Lenia, https://developmentalsystems.org/sensorimotor-lenia/: gradient-trained creatures navigate and survive asynchrony and damage. The Science Advances 2024 version returned 403.
  - Huang, Mordatch & Pathak 2020, https://arxiv.org/abs/2007.04976: one shared module policy with messages steers unseen bodies.
- **Learning inside the rule.**
  - Kirsch & Schmidhuber 2021, VSML, https://arxiv.org/abs/2012.14905.
  - Kirsch, Harrison, Sohl-Dickstein & Metz 2022, GPICL, https://arxiv.org/abs/2212.04458: state size matters more than parameter count.
  - Nisioti et al. 2024, https://arxiv.org/abs/2405.08510: grown networks need diverse internal states.
- **Training recipes.**
  - Xu et al. 2022, SHAC, https://arxiv.org/abs/2204.07137: short-window BPTT plus a smooth critic, more than 17x faster training on muscle-actuated locomotion.
  - Jaderberg et al. 2017, PBT, https://arxiv.org/abs/1711.09846.
  - Chen, Goodfellow & Shlens 2016, Net2Net, https://arxiv.org/abs/1511.05641.
  - Vicol, Metz & Sohl-Dickstein 2021, Persistent ES, https://arxiv.org/abs/2112.13835, and Li et al. 2023, Noise-Reuse ES, https://arxiv.org/abs/2304.12180: unbiased ES gradients over long unrolls.
- **Tooling.**
  - EvoTorch (Toklu et al. 2023, https://arxiv.org/abs/2302.12600), torch-native.
  - evosax (Lange 2022, https://arxiv.org/abs/2212.04180) and CAX (Faldor & Cully 2024, https://arxiv.org/abs/2410.02651), both JAX.
- **Gap.** No published NCA grows a body and steers it within one life (one narrow arXiv query, not exhaustive), and none at this project's Poisson noise level.

**What it relaxes.**
- **Relaxed:**
  - the clock during training (steps with random masks);
  - "no gradients" (used only in the outer loop);
  - spikes, unless the binary interface is used;
  - GRN readability.
- **Kept:** one continuous life (pool training), local rules, growth and death.
- **Why it is worth it:** the fastest feedback loop available, and the strongest current tooling.

**Risks.**
- **Long horizons.** Gradients over more than 1,000 steps explode or vanish; windows plus a critic are the mitigation.
- **Proxy breeding.** A soft capture disk is a training device. Your design review showed that shaped scores breed parking near targets, so selection must stay on the real score.
- **Lockstep artefacts.** Rules trained in lockstep may only work in lockstep; your v1 collapsed under asynchrony.
- **Opacity.** An MLP is harder to read than GRN rows.
- **Hard bits.** Training through hard bits is harder than through real-valued messages.

### Direction 3. Plastic faces: learning synapses in today's exact kernel

This merges Plastic faces (local-learning pass), the plasticity arm of Tensor spiking tissue, and the edge rule of Maturing tissue.

**Unit and messages.**
- **Unit.** Today's cell: GRN, LIF membrane, 2 value-less spike channels, morphogens.
- **What is added.** For each face d (up to 8) and channel c (2):
  - a learned weight offset p[d][c];
  - a slow consolidated copy u[d][c];
  - a presynaptic trace x[d][c];
  - an eligibility e[d][c];
  - plus one postsynaptic trace y per cell.
  - About 50 numbers, Q8 weights and Q16 traces.
- **Where it plugs in.** The kernel already stores per-face weights `weff[DMAX][2]` (src/life/kernel.c:201) and sums them on spike arrival (:1063), so this extends an existing slot.
- **Messages.** Unchanged, plus one local modulator carried in the existing morphogen packets.

**Learning.**
- **Inner loop.** An input on face d shortly before the cell fires strengthens that face; one shortly after weakens it (STDP).
  - A three-factor term lets a locally released modulator turn recent coincidences into lasting change.
  - A capture reaches the tapping cell only as a local sensory event. Its GRN decides whether to release modulator, so there is no global reward broadcast.
  - The GRN sets the coefficients, so evolution decides which cells learn and when.
- **Outer loop.** GA or ES over GRN rows and rule coefficients. It is Baldwinian: learned weights are not written into the genome.

**Growing without losing what was learned.**
- Daughters copy the mother's learned face table, scaled by a GRN-set fraction h, so "copy what I learned" is evolved rather than imposed.
- Old cells consolidate (u follows p slowly) while young cells stay plastic.

**Multidirectional circuits.** Nearest-neighbour recurrent circuits, with sign and strength learned per face and per channel.

**Why GPUs now and hardware later.**
- **GPUs:** no. It stays on the exact CPU kernel, at an estimated +10-30% per life [E].
- **Hardware:** the most native learning of all four. Trace-based three-factor rules are what on-chip learning silicon implements:
  - Loihi: Davies et al. 2018, https://doi.org/10.1109/MM.2018.112130359.
  - ReckOn: Frenkel & Indiveri 2022, https://arxiv.org/abs/2208.09759, with 0.45 mm², under 150 µW training and 0.8% memory overhead.
- **The gap:** zero, because the organism is the exact kernel. Updates are local to the receiving cell, so the window scheduler stays bitwise exact.

**A sharp prediction to test first.**
- **The timing.** In evolved bodies, sense-to-act spikes are about 1.0 time unit apart, and act-to-sense feedback lands after the sense spike.
- **The prediction.** Pair STDP should therefore learn "strengthen from below, weaken from above" on its own. Every SPECK body paid to build that profile from chemistry:
  - s5 loses 10.10 ± 0.41 F when its weights are made isotropic;
  - secretion is about 10% of its running cost;
  - the route breaks when the gene clock is 4x slower.
- **The test needs no evolution.** Switch off s5's chemical direction, sweep hand-set STDP settings, and run 256 paired lives per setting.

**Shown in the literature.**
- **Evolved local rules.**
  - Najarro & Risi 2020, https://arxiv.org/abs/2007.02686: evolved Hebbian rules let random networks learn to walk and adapt to unseen damage in under 100 steps.
  - Pedersen & Risi 2021, https://arxiv.org/abs/2104.07959: fewer shared rules generalise better.
  - Jordan, Schmidt, Senn & Petrovici 2021, https://doi.org/10.7554/eLife.66273: evolution finds interpretable spiking plasticity rules.
- **Stability and degeneracy.** Confavreux, Agnes, Zenke, Sprekeler & Vogels 2025, https://doi.org/10.1371/journal.pcbi.1012910: stability is the hardest constraint, and many rules work equally well.
- **Timing makes connections one-way.** Song, Miller & Abbott 2000, https://doi.org/10.1038/78829; Clopath et al. 2010, https://doi.org/10.1038/nn.2479.
- **Consolidation.** Benna & Fusi 2016, https://doi.org/10.1038/nn.4401.
- **Learning can guide evolution.** Hinton & Nowlan 1987, https://www.complex-systems.com/abstracts/v01_i03_a06/.
- **Gap.** None of this has been done in a growing tissue that steers a body.

**What it relaxes.**
- **Kept:** every standing preference.
- **Added:** per-contact memory and one fixed rule form. It is bitwise today's model when the coefficients are 0.
- **Conflict:** it contradicts docs/DOWNSTREAM.md M9's "no synapse memory" stance.

**Risks.**
- **Runaway excitation.** It needs a weight clip and probably homeostatic or inhibitory plasticity.
- **Learning switched off.** In a world that never changes within a life, evolution may set learning rates to 0.
- **Slow reward learning.** Captures are sparse (about 19 per life).
- **No speed-up.** It does not make search faster by itself.

### Direction 4. CellCode: an LLM edits the cell's integer event handlers, and the exact kernel judges

This is the frontier pass's candidate 1.

**Unit and messages.**
- The lattice, spikes, delays and one continuous life all stay as they are.
- The genome becomes a short integer program for the handlers the kernel already has: on_tick, on_arrival(face, channel), on_receptor and on_birth. Its constants form a separate vector.
- The GRN stays available as one callable primitive, so the first program is exactly today's model.
- A linter allows only what a cell can sense today, plus the arrival face. It rejects floats and unbounded loops.
- Instructions executed per event are charged as energy.

**Learning.**
- **Outer loop, structure.** An LLM proposes diffs to parent programs inside 4-8 islands and a MAP-Elites grid (FunSearch, AlphaEvolve style), with probe.py knockout reports in the prompt.
- **Outer loop, constants.** The existing GA or CMA-ES tunes them.
- **Inner loop.** Whatever the program implements: counters, gated weight changes, set points.
- **Control arm.** The same loop with the LLM replaced by random instruction edits (AutoML-Zero style).

**Growing, circuits and hardware.**
- **Growth and circuits:** the program decides, with face-aware handlers.
- **Hardware:** integer code with bounded loops is microcode for a per-tile core, and the per-event instruction budget is a cycle budget. There is no sim-to-hardware gap.
- **Cost:** about 15 CPU-h per seed plus $10-300 of LLM calls [E].

**Shown in the literature.**
- FunSearch: Romera-Paredes et al. 2024, Nature, https://www.nature.com/articles/s41586-023-06924-6 (metadata via Europe PMC).
- AlphaEvolve: Novikov et al. 2025, https://arxiv.org/abs/2506.13131.
- ELM: Lehman et al. 2022, https://arxiv.org/abs/2206.08896.
- ShinkaEvolve: Lange, Imajuku & Cetin 2025, https://arxiv.org/abs/2509.19349.
- OpenEvolve: https://github.com/codelion/openevolve.
- AutoML-Zero: Real et al. 2020, https://arxiv.org/abs/2003.03384.
- LLM-evolved spiking architectures: Zhao et al. 2026, https://arxiv.org/abs/2609.40258.
- LLM-evolved RL update rules: Sygkounas, Loutfi & Persson 2026, https://arxiv.org/abs/2603.28416.
- **Gap.** Published successes had cheap, low-noise evaluators; per-life reliability here is 0.026. Nothing evolves a developmental tissue.

**Relaxes and risks.**
- **Relaxes:** nothing in the substrate.
- **Risks:**
  - the LLM's human prior writes designed roles, against your minimal-hard-coding rule (the control arm measures this);
  - noisy feedback can mislead it;
  - API model drift hurts reproducibility.

### Search-side changes that help whichever unit you choose

Every pass proposed these, so treat them as shared infrastructure rather than as candidates.
- **ES with paired lives instead of truncation selection.** It can be tested on today's kernel within days (Salimans, Ho, Chen, Sidor & Sutskever 2017, https://arxiv.org/abs/1703.03864).
  - First measure whether paired lives stay correlated when a genome is perturbed, because chaotic spiking and growth could break the pairing.
- **Several breeds per run.** Islands, PBT lineages or a MAP-Elites archive keyed on what the probes already measure: lateral share of F, size at T/2, growth-stop time (Mouret & Clune 2015, https://arxiv.org/abs/1504.04909). Add the planned random tie-breaking (N1).
- **Growth operators that do not change behaviour, plus a "birth deficit" readout.**
  - Silent gene duplication already exists in src/genome.py but is off (`dup_rate` 0.0).
  - Pass-through gates, zero-weight channels and Net2Net splits are the equivalents elsewhere.
  - Report child F minus parent F on paired lives as a standard number.
- **A task ceiling and positive controls.**
  - Build the non-local event-centroid controller that BODY_DESIGN_PROPOSAL lists as an upper bound "to build".
  - Show that every new substrate can express the reflex and the router before searching.
  - The router's lead is narrow: it is +2.2 F in base SPECK, about 0 with a twin target, near placement or decoy-lite, and −1.28 with sparse receptors. "Beat the reflex" therefore needs a ceiling to be read.
- **A small panel of worlds drawn per life,** including worlds that change within the life, so that adaptation and depth have a job. Hidden planes are inert today: hidden_off moves F by at most +0.04.
- **A clockless gate.** Search may run in steps; accepted rules must keep their score under unseen update densities, unseen delays and fully asynchronous replay.

---

## 2. Comparison with the current cell model

| | Current (GRN+LIF, GA) | 1. Logic tissue | 2. Shared neural cell (NCA) | 3. Plastic faces | 4. CellCode |
|---|---|---|---|---|---|
| **Unit** | 16-gene GRN + LIF | 32-64 bits + shared ≤1k-gate netlist | 16-32 channels + shared MLP/GRU, 2-12k params | today's cell + ~50 learned numbers | today's cell, handlers as integer code |
| **Messages** | 2 value-less spike channels, ~1 unit delay; morphogens | 2 spike bits per update, per-edge delay | vectors or bits per face | unchanged + local modulator | unchanged |
| **Cost per life (its own simulator)** | ~0.1 CPU-s [M] | stand-in 2.6-7.6 ms per core [M]; ~5-15x below kernel with world [E] | CPU 3-25x more than kernel [M]; GPU ~1-3k lives/s forward [E] | +10-30% [E] | kernel + ~0.3 s compile per candidate [E] |
| **Search efficiency** | reliability 0.026/life; ~0.005 F/gen late; children −0.19 F | CGP, but 64-512 paired lives per genome for free; gradients via teacher | gradients per batch, or ES at large populations | same search; learning may smooth it (Baldwin, untested) | large semantic edits; untested under noise |
| **First visible result** | exists (atlas) | hand reflex netlist chasing, ~1 week | growth + regrowth GIF ~1 day; chase ~2 weeks | weight maps after ~1 week of kernel work | ~2 weeks |
| **Growth that keeps what was learned** | shared GRN; duplication off | daughters copy bits; pass-through gates; size-independent rule | size-independent rule; Net2Net widening; newborn flag | daughters copy learned face table; consolidation | program decides; regression gate |
| **Circuitry** | nearest neighbours; direction only via chemistry | lattice paths; per-face bits | lattice paths; per-face messages; wires possible | nearest neighbours; learned direction per face | face-aware handlers |
| **Locality and timing** | local, exact, clockless | local; steps with LFSR enables; async replay as a test | local; steps with masks; must pass the async gate | local, exact, clockless | local, exact, clockless |
| **Interpretability** | high (GRN rows, probes) | pruned netlists read as Boolean formulas; probes | low-medium (lesions; distil to read) | high | highest (readable code) |
| **Runtime on silicon** | integer GRN tile, 0.3-1.6 nJ per cell per unit [E]; genome copy ~9x cell state | few hundred-1k gates + ~60 flip-flops; hardwired rule, no genome copy [E] | int8 MLP, ~5-12k MACs per update: heavy | GRN tile + trace learning engine (Loihi/ReckOn precedent) | small integer core per tile |
| **Sim-to-hardware gap** | none under the integer ABI (sizes shift ≤ ~4 cells vs float [M]) | none: the simulator is the netlist | float→int8, sync→async, soft→hard world | none | none |
| **Evidence** | this pilot | patterns, Game of Life, growth; no control | strong for growth and repair; small control; no grow-and-steer | strong for plasticity; none in grown bodies | strong on cheap evaluators; none on tissues |
| **Effort (person-weeks)** | 0 | 1-2 engine + 1 search | 1-2 world port + trainer | 1-3 | ~2 |
| **Relaxes** | nothing | continuous time and membrane (steps, counters) | clock in training, gradients, spikes unless bits | adds per-contact memory + one rule form | LLM prior in the mutation operator |

---

## 3. The hybrid I recommend building first: "spike-bit tissue"

**The idea.** The organism is a logic tissue (direction 1). A neural cell with exactly the same bit interface (direction 2) is the trainer: it is trained by gradient, then compiled into gates, then refined by evolution in the bit-exact runtime. Plastic faces (direction 3) and ES on the current kernel run as a cheap side track.

**Why this combination:**
- It satisfies clarification 1 by construction: the thing that runs is a netlist, and the simulator that scores it is that netlist.
- It satisfies clarification 2 because:
  - the teacher gives watchable growth within days, and chasing within about two weeks, on the laptop plus one rented GPU;
  - the bit engine gives 64-256 paired lives per genome cheaply, so selection can finally see small differences.

### 3.1 The organism (the rollout: hardware-native)

**Body and world.** SPECK/BODY-1 unchanged in its rules:
- the hex-prism lattice with sense, hidden and act planes;
- receptor pings as Poisson events;
- twitches that pull the dot along the cell's surface normal;
- the centre cell's tap to catch.

The world is re-implemented per life in integer arithmetic inside the bit engine. Prototype box: a hex disk of radius 6 (127 sites per plane) × 3 planes = 381 sites, with a cell cap rising 16 → 64 → 256.

**Cell state (57 bits visible to the rule, plus 16 LFSR bits):**

| Field | Bits | Written by | Purpose |
|---|---|---|---|
| alive | 1 | rule (clearing it is death) | |
| newborn | 1 | set by division; cleared by the rule | lets the rule keep new cells quiet until they fit in |
| polarity | 3 | rule (values 0-5) | the cell's own in-plane heading; in-plane faces are presented relative to it |
| counter | 4 | rule | an integrator or timer, if the rule wants one (the "membrane") |
| gene bits | 16 | rule | slow internal state; cell types emerge as stable patterns |
| synapse bits | 2 × 8 faces = 16 | rule only | per-face memory (gate, sign, strength); the within-life learning store |
| inbox | 2 × 8 = 16 | set by arriving spikes; cleared when read | spikes are not lost while the cell skips steps |
| LFSR | 16 | hardware | the update enable plus 3 random bits per update |

**Rule inputs (73 bits):**
- the 57 state bits;
- receptor ping (sense plane);
- 8 occupied-face bits;
- 2 plane-cue bits;
- 3 random bits;
- 1 capture bit, which is set only at the tapping cell when a tap catches;
- 1 miss bit, set only at the tapping cell when a tap misses.

**Rule outputs (50 bits):**
- 41 next-state bits;
- 2 spike bits;
- divide (1) plus its face (3);
- an orient-daughter bit (copy the mother's polarity, or point it away from her);
- twitch (1) and tap (1). These only act where the world lets them: twitch on the act plane, tap at the centre.

**The rule.** One feedforward netlist of at most 1,024 two-input gates, shared by every cell and hardwired once frozen. Its state bits make it recurrent across updates.

**Message format.**
- 2 value-less spike bits per update, sent to every occupied neighbour, as today.
- What a spike *means* is decided at the receiver, by its synapse bits for that face. A→B and B→A are therefore independent.
- Per-face sending (16 output bits instead of 2) is an option if lateral routing turns out to be the bottleneck.

**Update schedule.**
- Steps of dt = 1/4 world unit, so 4,096 steps per 1,024-unit life.
- On each step, a cell updates only if its LFSR enable bit is 1, with density p.
  - p is 0.5 nominally, drawn per life from 0.3-0.7 during training.
  - Updating cells read the previous step's bits.
- Each directed edge gets a fixed delay of 3, 4 or 5 steps (0.75-1.25 units; mean 1 unit, the pilot's d0 = 1). The delay is drawn when the edge forms. d0 = 0.5 is a knob, since faster conduction helped every pilot body.
- The world advances every step.

**Growth operator.**
- **Division.** When divide = 1 and the chosen face is empty, a daughter appears there on the next step.
  - In-plane faces are counted from the cell's polarity; up and down are absolute.
  - Two cells claiming one site in the same step are resolved by random priority bits at that site, a local rule with no order dependence.
- **The daughter:**
  - copies the mother's gene bits, counter and synapse bits;
  - takes the mother's polarity, or points away from her, as the orient bit says;
  - has newborn = 1, an empty inbox, and a fresh LFSR seed derived from the mother's.
- **Death.** It clears the site, and neighbours see an empty face.
- **Bounding growth.** A living cost per cell and a cost per spike bound growth, as now. The box is only a guard.
- **Function preservation, at three levels:**
  - **Genome growth is exactly neutral.** New gates enter as pass-throughs; a new state bit enters as "hold" (next = current). The hardened rule is bitwise unchanged until something uses them. The teacher widens by Net2Net.
  - **Learned state is inherited.** Whatever a cell has latched in its synapse and gene bits is stamped into its daughters, so a direction profile learned in a 10-cell body appears in every new column.
  - **New cells can enter quietly.** The newborn bit lets the rule hold a new cell's output until it fits in. Whether the rule does so is measured by the birth deficit: F with one forced extra division at T/2, minus F without it, on paired lives.

**Within-life learning.**
- The synapse bits are written only by the cell's own rule, from local signals: its inbox, its own spikes, its counter, random bits and the capture bit.
- No learning-rule form is fixed. Whatever the trained and evolved netlist does with these bits *is* the learning rule.
- A 1-bit STDP latch fits easily ("set the face bit when an input on that face precedes my spike; clear it when one follows"), at a dozen or so gates per face [E].
- If the side track's STDP test succeeds, that latch is offered as a seed module.
- The capture and miss bits are the only reward-like inputs. They are local to the tapping cell, and the rule must spread them as spikes if it wants to.

**Fixed rules this design adds, each with its reason** (per your minimal-hard-coding rule):
1. **The division operation** (copy state into the chosen empty face, set newborn, random-priority claims). Growth needs some mechanics; this is the pilot's, minus the morphogen placement.
2. **In-plane faces presented relative to the cell's own polarity.** This removes a built-in compass, at the cost of a 6-way rotation per bit in hardware.
3. **Capture and miss bits at the tapping cell.** Without a local consequence signal, learning within the life has no input.
4. **LFSR update enables and per-edge fixed delays.** They make the "random" timing used in training exactly reproducible in silicon.
5. **The gate budget and state size.** These are physical bounds.

Roles, learning, when to divide or die, and what spikes mean are all left to the rule.

### 3.2 Training (the outer loop: any machinery)

**Stage 1. The teacher (torch; laptop, then one GPU).**
- **Model.** The same 73-in, 50-out interface and the same 41 state bits. Inside is an MLP 73 → 64 → 64 → 50, about 12k parameters.
- **Bits during training.** Every state and spike bit is a sigmoid during warm-up, then hard in the forward pass with straight-through gradients, on an annealed temperature.
- **Worlds.** It trains in a torch port of the world that has two modes:
  - a soft mode, with expected receptor rates and a capture disk with a 0.2-unit soft edge;
  - a hard mode, with Poisson pings and a hard disk, used for every score.
- **Pool training.**
  - 1,024 persistent lives, each advanced 32-64 steps per update, then written back.
  - Each is replaced by a fresh zygote at T, so every life is one continuous zygote-to-death life.
  - Update density and edge delays are drawn per life.
- **The loss.** Expected captures, minus living cost per alive cell, minus cost per spike bit.
  - A critic, a separate network that sees global information during training only, values the rest of the life beyond each window (the SHAC recipe).
  - Selection never uses the loss: it uses hard-mode F.
- **Warm start.** Behavioural cloning of the hand-written reflex netlist: an exact per-cell target, taking minutes. The teacher therefore chases on day one, and training improves from there.
- **Evolutionary layer.** PBT with 8 lineages. The worst periodically copies the best and perturbs costs, window length, temperature schedule and mask density, judged on hard-mode F over 256 paired lives.
- **Curriculum.** A fixed 19-cell tissue first, then growth from one cell at cap 64, then cap 256.

**Stage 2. Compile to gates.**
1. Collect (73 input bits → 50 output bits) pairs from the teacher's hard-mode lives: about 10^7 cell updates.
2. Train a relaxed DiffLogic network (at most 1,024 gates) on them, one cross-entropy per output bit.
3. Harden it.
4. Run the hardened student in the C engine and record the states *it* visits. Label them with the teacher, add them and retrain. Two or three rounds, which is DAgger: Ross, Gordon & Bagnell 2011, https://arxiv.org/abs/1011.0686. This fixes the compounding errors that make copied policies drift off course.

Only the hardened student is ever scored.

**Stage 3. Evolve in the runtime (C bit engine).**
- **Mutations.** CGP point mutations on gate functions and wires, with inactive gates as neutral reservoirs.
- **Selection.** (1+λ) per island, λ 4-16, over 4 islands. Each candidate is scored on 64-256 paired lives (1-4 machine words) in the real Poisson world, with random tie-breaking.
- **Archive.** A MAP-Elites log over size at T/2, lateral share and growth-stop time, used to reseed a stalled island.
- **Readability.** A final pruning pass yields a minimal netlist to read.

**Optional "evolution only" arm.** OpenES with antithetic paired lives on the teacher's weights, scored on true hard-mode F, with no gradients through the life. This tells you whether gradients were needed.

### 3.3 Task panel

- **Training panel, drawn per life:**
  - base SPECK;
  - sparse receptors;
  - **motor-sign flip:** in half the lives twitches push instead of pull, so a fixed reflex fails and the body must find out within the life. This gives memory, and so depth, a job.
- **Held-out panel:** twin target, decoy-lite, near placement, and target speed doubled at T/2.
- **Watchable milestones** (each one a GIF, a number and a time box):
  - **M0:** grow a shape from one cell on the hex prism and regrow it after a cut. This is the classic Growing-NCA test; it checks the engine and that the bit teacher trains at all.
  - **M1:** a fixed 19-cell tissue turns the dot toward pings.
  - **M2:** grow from one cell, then chase.
  - **M3:** remove half the body at T/2; it regrows and catches again.
  - **M4:** flip the motor sign at T/2; captures recover within the life.

### 3.4 What it relaxes, kept honest

- **The clock.**
  - The rule runs in steps, but those steps need no chip-wide clock. Each tile can compute its step k once its neighbours' step k−1 bits have arrived (a local handshake). Nehaniv proved that asynchronous automata networks can emulate any synchronous one: Nehaniv 2004, Int. J. Algebra and Computation 14(5-6):719-739, https://doi.org/10.1142/S0218196704002043 (Crossref metadata only).
  - With LFSR enables the silicon is bit-exact to the simulator, whether driven by a clock or by handshakes.
  - Your "behaviour must not depend on lockstep" becomes a test the rule must pass:
    - F within 10% across unseen update densities and delays;
    - at least 90% of F in a fully asynchronous replay, where each cell updates at its own Poisson times.
- **Continuous life:** kept. Pool training is windowed but never resets a life, and every score is one continuous life.
- **Spikes:** kept, as 2 value-less bits.
- **Continuous membrane and GRN:** replaced by a counter and gene bits inside the netlist.
- **Gradients:** used, but only in the outer loop. Nothing is backpropagated inside a life.
- **Evolution:** keeps choosing lineages (PBT) and does the final discrete refinement (CGP). It no longer has to do all the fine continuous tuning.

### 3.5 What it reuses from this project

- **Geometry:** src/lattice.py (`offsets3`, `rotate3`, `in_plane_slots`, `vertical_slots`) for the hex prism and polarity rotation.
- **Batched growth and pictures:** src/develop.py (batched division claims) and src/render.py (`development_gif`, `activity_gif`) for day-1 GIFs; src/cells.py (quantised stepped LIF) as a reference for stepped spikes.
- **World rules:** docs/LIFE_ABI.md (section 9.7, CATCH/SPECK) and src/life as the specification the torch and bit-engine worlds must follow.
- **Baselines and positive controls:** src/life/handbuilt.py (reflex, ring-4 router, `router_genome`), rewritten as small netlists. The pilot's numbers as the reference bar: reflex@hollow3 +8.69, s5 +7.06, GS2 +2.25, GS5.
- **Evaluation conventions:** paired-life seeding (`LifeDraw`, `life_seed` in src/life/evaluate.py), the 40-mutant protocol, and random tie-breaking (N1).
- **Analysis:** probe.py's knockouts (lateral_off, hidden_off, receptor_off, lineage tables), which are masks in the bit engine; the atlas viewer, fed from one shared state-dump format so pilot bodies and gate bodies can be watched side by side.
- **Hardware study:**
  - the energy model and tile estimates as the comparison column;
  - the window-scheduler argument;
  - Tiny Tapeout pricing;
  - AWS F2 FPGA instances at $0.659/h spot [S, HARDWARE_PATH] for a hardware run without buying a board.
- **The exact kernel:** it stays the reference for event-driven semantics and runs the side track.

---

## 4. First prototype plan (3 weeks)

### Week 1: engines, positive controls, first GIFs (laptop, $0)

- **Days 1-4: the C bit engine.**
  - Hex prism, 64 lives per word, cell bits as bit planes, LFSR enables, per-edge delay lines, division claims, death.
  - The world per life in integers: dot physics, run-and-tumble target, receptor pings by skip sampling between events, capture.
  - Probe masks.
  - Measure lives per second per core against the kernel at equal T and size.
- **Days 1-3 (in parallel): the torch side.**
  - The soft and hard torch world.
  - The bit-interface teacher.
  - **M0:** growth and regrowth of a shape, trained in minutes to hours on the laptop. This is also the early kill test for "can a bit-state teacher train?".
- **Days 4-5: positive controls.**
  - A hand-written reflex netlist and a ring-4 router netlist run in both the C engine and torch hard mode. F must agree within 1 SE on 1,024 paired lives. That shows the training simulator matches the runtime.
  - The teacher, cloned from the reflex, chases in torch (**M1** for a fixed tissue).
  - The event-centroid ceiling controller runs in the torch world.
- **Side track starts** (see below).

### Week 2: teach (one rented L4 or RTX 4090)

- Pool BPTT with a critic, from the cloned start; PBT with 8 lineages; curriculum fixed 19 cells → grow from 1 cell at cap 64 → cap 256; the training panel.
- **M2** (grow and chase) and **M3** (half-body cut at T/2, regrowth).
- A smoke test of the compile pipeline on the reflex-cloned teacher. Its gate count is itself a result: how many gates the reflex needs.

### Week 3: compile, evolve, test

- Compile the best teacher to gates with 2-3 DAgger rounds, harden, and score in C.
- CGP refinement: about one laptop-day plus a few box-hours.
- Build a small fully asynchronous referee: each cell has its own Poisson clock and continuous delays (an event loop of about 200 lines in C or Python for 256 cells).
- Run the gates below, **M4** (sign flip), the cap-transfer and birth-deficit tests, and yosys + abc LUT6 counts for a hardwired and a programmable cell.
- Final scoring on 1,024 fresh paired lives per body, on base SPECK and on the held-out panel.

### Side track (CPU, existing kernel, through all three weeks)

| Test | How | Decides |
|---|---|---|
| **T1. Timing teaches direction** | s5 and s4 with chemical direction off (a_c = 0; costs s5 −10.1 F); a sweep of hand-set STDP settings (wider than 3-5), 256 paired lives each, best confirmed on fresh lives. Needs plastic fields in reference.py, then kernel.c, with golden tests showing bitwise ABI 3 at zero coefficients. | Recovers ≥50% of the lost F → plasticity can replace the chemistry, and the STDP latch is worth seeding into the gate cell |
| **T2. Do paired lives stay paired?** | Correlation of F between paired lives for s5 and perturbed copies at ES-sized and mutation-sized changes | Whether ES with paired lives can beat the noise on this kernel |
| **T3. ES against GA** | Antithetic ES vs the GA at equal lives, 3 seeds × 200 generations, base SPECK | How much of the pilot's shortfall was search |
| **T4. Silent gene duplication** | Turn on `dup_rate` with the silent copy, and check that the birth deficit is 0 bitwise | A neutral source of new genes for the current model |

If time runs short, keep T1 and T3 and cut the rest.

### Compute and budget

| Item | Where | Amount | Cost |
|---|---|---|---|
| Engines, world port, M0, cloning, positive controls | laptop | week 1 | $0 |
| Teacher training + PBT | 1 × L4 ($0.59/h) or RTX 4090 ($0.89/h), RunPod prices from HARDWARE_PATH [S; the 4090 price was not re-checked] | 40-80 GPU-h [E] | $25-70 |
| CGP refinement + final evaluations | laptop + c7a.48xlarge spot ($3.40/h [S]) | 5-10 box-h [E] | $17-34 |
| Side track T1-T4 | same box | ~100 CPU-h ≈ 0.5-1 box-h [E] | ~$2-4 |
| **Total** | | | **about $45-110 [E]; cap at $150** |

### Pre-registered success criteria

Every body is scored on 1,024 fresh paired lives. The bars are re-measured in the new world: the reflex written in bits (R), the router written in bits (Q), the event-centroid ceiling (C) and the lone cell (L). "Excess F" means F minus L.

| # | Criterion | Pass if |
|---|---|---|
| S1 | Runtime speed | bit engine ≥ 10x lives per core over the kernel, with world and growth included (target 20x) |
| S2 | Sim matches runtime | same netlist: torch hard-mode F and C-engine F agree within 1 SE |
| S3 | Visible | GIFs M0-M3 by the end of week 2; M4 by the end of week 3 |
| S4 | Performance | best grown gate body F ≥ R with no more cells than R uses (the pilot: 0 of 10 GRN seeds beat the reflex); stretch: ≥ Q |
| S5 | Compile | hardened student keeps ≥ 90% of its teacher's excess F; ≤ 1,024 gates; LUT6 count reported |
| S6 | No lockstep dependence | excess F within 10% across update density 0.3-0.7 and mean delay 0.5-1.5 units; ≥ 90% in the fully asynchronous replay |
| S7 | Local computation | lateral_off (in-plane spike bits dropped) removes ≥ 50% of F |
| S8 | Bounded growth | final size below the box capacity in ≥ 90% of lives, with no size target anywhere |
| S9 | Learn small, keep it big | rule trained up to cap 64 keeps ≥ 80% of its per-cell earnings at cap 256 without retraining; birth deficit within 1 SE of 0 |
| S10 | Learning within the life | in the sign-flip world, captures in the last third exceed the first third by > 3 SE, and freezing synapse and gene bits at T/4 removes that |

**Kill rules:**
- If M0 fails in bits after a laptop-day, switch the teacher to float state with 4-value messages and distil at the sequence level.
- If no lineage beats R after 48 GPU-hours, stop and read the ceiling (see the outcome table).
- If CGP gives no gain over the distilled body in one laptop-day, stop CGP.

### The decisive comparison against the current model

- **Same rules, same budget.** The same world rules and the same budget (three weeks, ≤ $150) for three pipelines:
  - **Current model, as piloted:** 10 seeds × 24 CPU-h; 0 of 10 beat reflex@hollow3 (+8.69); best s5 +7.06 (−1.63, z −17).
  - **Current model with the search fixed:** side track T3.
  - **Spike-bit tissue.**
- **Each is judged against its own substrate's hand-built reflex, and against the shared ceiling C.** Absolute F is comparable because the world and capture rules are the same. Report capture counts as well as F, so the result does not hinge on how living and spike costs translate between substrates.
- **Reported:**
  - (a) best F minus its own reflex, and the fraction of the reflex-to-ceiling gap closed;
  - (b) dollars and wall-clock to the first body above its reflex;
  - (c) S6 and S7;
  - (d) runtime cost per cell: gates and flip-flops against the GRN tile's 1.5-2 kbit state + 13.5 kbit genome and 0.3-1.6 nJ per cell per unit [E];
  - (e) lives per second per core in each runtime simulator.

**How to read the outcome:**

| Outcome | Meaning | Next |
|---|---|---|
| S4 + S5 + S6 pass | the paradigm works end to end | FPGA run (AWS F2 or an ECP5 board, bit-identical to the simulator); start the mouse-cursor world |
| teacher passes S4, student fails S5 | the gate budget or distillation is the limit | lookup-table cells (LogicNets/DWN), a larger gate budget, or accept the int8 teacher as the runtime (heavier but still legal) |
| teacher fails S4, ceiling C ≫ R | credit assignment through bits is hard | a 4-value-message arm measures what the spike constraint costs |
| teacher fails S4, C ≈ R | the task has no headroom for multi-hop computation | change the task before the substrate: occluded target, message rungs |
| S6 fails | the rule exploits lockstep | wider update-density range, delay jitter, asynchronous replay inside training |
| T3: ES ≫ GA on the kernel | the pilot was largely search-limited | carry ES and paired lives into every substrate; GRN+LIF stays a live option |
| T1 passes | timing alone builds direction | seed the STDP latch into the gate cell; drop the morphogen route in the GRN model too |

---

## 5. Worth keeping in mind, but not first

- **Grown wires (axon slots).** Cells grow directed, delayed wires to cells within radius R, paid per unit of length (your radius gene), and divide Net2Net-style. Use them if earnings per cell stay the gap: s5 earns 9.65 per unit with 115-163 cells, the reflex 9.95 with 56.
  - Najarro, Sudhakaran & Risi 2023, https://arxiv.org/abs/2307.08197: a 162-parameter program grew a CartPole solver; LunarLander was not solved (116 against 200).
  - Plantec et al. 2024, LNDP, https://arxiv.org/abs/2406.09787.
  - In the bit engine a wire slot is a stored target address plus a delay.
- **Fast weights or an in-context learner per face** (VSML, above; BLUR: Sandler et al. 2021, https://arxiv.org/abs/2104.04657). Worth adding once worlds vary within a life and the base tissue chases. It is expensive to meta-train and opaque.
- **Predictive tissue for the cursor and text worlds.** Each cell predicts its next input, and only surprises are sent (send-on-delta, as in EGRU: Subramoney et al. 2023, https://arxiv.org/abs/2206.06178).
  - Evidence: Whittington & Bogacz 2017, https://doi.org/10.1162/neco_a_00949; Salvatori et al. 2022 on arbitrary graphs, https://arxiv.org/abs/2201.13180.
  - It gives hidden planes a job when prediction pays. Risks: the "dark room" (avoiding surprise by avoiding targets), and unproven closed-loop control.
- **Worlds that evolve alongside the bodies.** POET (Wang, Lehman, Clune & Stanley 2019, https://arxiv.org/abs/1901.01753) and OMNI-EPIC (Faldor et al. 2024, https://arxiv.org/abs/2405.15568). The parametric panel above is version 0; LLM-written worlds need a linter against hidden shaped rewards.
- **Organ duplication.** Copy a progenitor before it differentiates, so its whole lineage is duplicated, then let the copies diverge. Use it once the dot, mouse and text ladder exists (Calabretta et al. 2000, https://doi.org/10.1162/106454600568320, metadata only).
- **Cells that take elapsed time as an input.** Closed-form continuous-time (CfC) cells run the same rule in steps and in events, which closes the clock gap for a float runtime (Hasani et al. 2022, https://arxiv.org/abs/2106.13898).
- **Symbolic distillation** of a trained teacher's message and update functions into formulas, as a readable alternative to gates (Cranmer et al. 2020, https://arxiv.org/abs/2006.11287).
- **A privileged teacher.** Train a policy that sees the true target, then have the tissue imitate it per act cell, for dense noise-free supervision (Chen, Zhou, Koltun & Krähenbühl 2019, Learning by Cheating, https://arxiv.org/abs/1912.12294). This is a cheaper teacher than BPTT if stage 1 struggles.
- **Cells as the body:** voxel soft robots, where growth changes the morphology and locomotion and regrowth are directly visible (Nadizar et al. 2022, above; Bhatia et al. 2021, Evolution Gym, https://arxiv.org/abs/2201.09863).
- **Give death a job.** Continual learners lose plasticity unless little-used units are reset (Dohare et al. 2024, Nature, https://doi.org/10.1038/s41586-024-07711-7). Today p_die knockouts cost 0.00 in every evolved body.
- **EventProp on the exact kernel** (Wunderlich & Pehle 2021, https://arxiv.org/abs/2009.08378). Exact gradients for face weights on a frozen grown body, with no stepped twin. It tells whether a morphology is limited by its weights.
- **Variance reduction without shaping.** Control variates from world statistics that do not depend on the genome (target path, initial distance, expected ping counts). They are unbiased, so they respect the "no shaped score" call.
- **A control for "do evolved dynamics matter?".** A fixed critical tissue with only an evolved readout (Zhang, Guichard, Pontes-Filho & Nichele 2026, https://arxiv.org/abs/2606.23115).
- **Hardware precedents.** Embryonics, cell-based self-repairing FPGA tissues (Mange, Sipper, Stauffer & Tempesti 2000, https://doi.org/10.1109/5.842998, metadata only). Thompson 1997, https://doi.org/10.1007/3-540-63173-9_61 (metadata only), is the cautionary case: evolving directly on an FPGA exploited analog physics, which is why evolution should target the bit-exact model and only run rollouts on the chip.
- **Dropped:**
  - NEAT with Lamarckian morphisms (a direct encoding, no growth within the life);
  - CPPN/HyperNEAT (a global geometric genome; its resolution-transfer claim was not verified);
  - separate per-synapse meta-learned programs (the heaviest runtime);
  - a full GPU port of the LIF kernel (6-14 person-weeks for 2-9x per dollar). The dt-equivalence curve from that idea is still worth measuring someday.

### What I am unsure about

- **Whether a bit-interface teacher trains over long horizons.** Straight-through bits for both state and messages, through 32-64-step windows of a closed-loop world, is the biggest technical risk. M0 tests it on day 1-3, and the float fallback is in the kill rules.
- **Whether the distilled student keeps the teacher's behaviour.** Per-step imitation compounds errors in closed loop. DAgger usually fixes this, but here it is untested.
- **The logic benchmark is a stand-in.** It used a random netlist, one ring neighbour, no world and no growth, so 5-15x is an estimate until S1 is measured.
- **GPU figures are estimates.** There is no GPU on this machine.
- **Sync-to-async transfer for control.** DiffLogic CA and Growing NCA report it works for patterns; your v1 collapsed under asynchrony. S6 is there for that.
- **Whether SPECK rewards multi-hop computation at all.** The router's lead is narrow and world-dependent, which is why the ceiling and the held-out panel come first.
- **Whether gates are bio-inspired enough for you.** The tissue level (local cells, spikes, division, death, inherited state) stays biological, but the cell becomes digital logic. If that matters more than silicon cost, the int8 teacher or plastic faces in the GRN cell are the closer-to-biology runtimes.
- **Whether learning gets used.** Evolution or training may ignore the synapse bits unless worlds change within the life. The sign-flip world is there for that, and S10 measures it.
- **The two losses are different.** The 0.19 F lost per child is lost across generations. Function-preserving division within a life does not touch it; only gradients, larger informed mutations, learning (the Baldwin effect) or better selection can.
- **Citations.**
  - The research and judging passes opened each URL above unless it is marked "metadata only" or "not opened".
  - In this synthesis I re-opened LogicNets, DWN, DiffLogic CA, SHAC, Nadizar et al., Persistent ES, Noise-Reuse ES and DAgger, and checked Nehaniv 2004 through Crossref.
  - Web search was exhausted for the session, so recent work that was not fetched directly may be missing.
  - Repo facts were re-checked in RESULTS.md, kernel.c (lines 201 and 1063), src/genome.py (`dup_rate`), docs/LIFE_ABI.md and docs/HARDWARE_PATH.md.
