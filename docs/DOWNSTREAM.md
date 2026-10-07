# Downstream paths: how cell-dev findings could be used

Produced on 2026-10-06 by the `downstream-paths` workflow (6 domain researchers with sourced precedents, a realism critic,
a completeness critic, and a roadmap synthesis), then reviewed. Statuses and probe numbers come from a read-only robustness
probe the completeness critic ran on saved organisms; treat them as provisional until re-run in the main harness.
Correction applied: the roadmap first described the horseshoe as hand-built; it is the evolved withdraw organism.

## Top three paths
1. Make organisms survive realistic execution, and select for it
This means the integer fixed-point model, the robustness panel, noise-envelope evolution and selection for canalized development (near-term items N1 and N2).

Why it ranks first:
- It is the gate. Every physical downstream use depends on it: digital tile, skin, swarm, analog, self-repair and the motif library.
- It is cheap: one 200-generation run takes about 10-20 minutes, so 10 seeds per condition fit overnight.
- The probe already shows both the problem and why it is probably fixable:
  - Integer arithmetic at 10 fractional bits is exact on every organism tested.
  - Under 0.05 v-noise or 10% mismatch, 5 of 6 organisms lose at least 30% of their score.
  - At async p=0.5, every organism scores 0.12 or less.
  - Memory organisms are not canalized: the 75-cell memory scores 0.51-0.69 on other developmental tie-break seeds.
  - Robustness varies between organisms that look the same: two context winners at 0.91 and 0.90 keep 0.88 and 0.07 under 10% mismatch. That is heritable variation that selection is not seeing today, so selecting for it has a real chance.
- Both outcomes are useful:
  - Pass (at least 0.6 held-out with 80% retention under the shared envelope on 2 or more rungs, at a modest score cost): the tactile, MCU-board, swarm and analog paths open.
  - Fail: hardware claims narrow honestly to bit-exact synchronous digital logic.
  - Either way, the table of which motifs survive which fault model is itself a result. Reverberating memory dies under spike drops, while one context organism tolerates noise and the other tolerates drops.
- First demo: the panel as standard results columns for all saved organisms (1-2 days), then context and withdraw × {plain, envelope} × 10 seeds.

2. A certified message-necessity benchmark, strengthened with formal bounds
This covers near-term items N3, N6 and N7, released through GECCO BBSR or ALIFE 2027 first and NeurIPS Datasets & Benchmarks after a JAX/CAX port.

Why:
- It is the most transferable thing the project owns, and it keeps its value whether or not any organism ever leaves simulation.
- Several fields have a documented problem here:
  - Emergent-communication research keeps finding channels that turn out to be unnecessary (Lowe et al. 2019).
  - Long-range-graph claims collapsed once baselines were tuned (Tönshoff et al. 2023).
  - The DishBrain dispute is about uncontrolled simpler explanations (Balci et al. 2023).
  - Few in-materio papers report a coupling-off control.
- cell-dev already has what those lack: an exhaustive enumeration of single-cell rules (8,448 quantized rules), cheat search, stimulus audits and hand-built ceilings.
- Make it stronger than any competitor's:
  - prove no-message ceilings for small multi-cell tissues with SAT or bounded model checking on the integer model;
  - add beeping-model light-cone lower bounds (decision time at least the hop distance);
  - fix the readout so 1-2 spikes cannot win (today they decide 100% of 4-cell-latch trials and 89% of jump trials);
  - certify messages-off floors for continuous parameters and for gradient-trained NCA and GRU cells.
- Honest scope: the certificate currently holds only for quantized cells. Jump breaks unquantized (0.55 with messages off), and I expect withdraw to as well. If so, ship it as a quantized-cell benchmark, which still suits neuromorphic and digital local learners and alt-arcs as a new level, and drop the wet-lab and material pitches.
- Likely users: NCA researchers (CAX, NCAtorch), GNN, swarm and physical-reservoir groups.

3. An evolved in-sensor reflex tile
The chain runs integer golden model → bit-exact RTL and FPGA → tactile sheet on hexagonal microcontroller boards (mid-term items M1 and M3, then long-term items L1 and L2).

Why:
- It is the most concrete useful endpoint, and it matches the project's design exactly:
  - every taxel senses only where it sits;
  - wires run only to neighbours;
  - the configuration is under 1 kbit (271 × 3 + 4 × 36 = 957 bits);
  - there is no per-synapse memory;
  - the output is a direction, not a frame.
- Real systems name wiring and latency as their bottleneck: the ACES event-coded skin and the HEX-o-SKIN hexagonal skin cells.
- The neuron arithmetic is already standard silicon: TrueNorth's per-input-type weight table and Xylo's v - (v >> dash) leak. So the risk is not "can it be built" but "does it beat a microcontroller".
- It is conditional on #1 and on the cross-fabric test N4. Today withdraw seed 1 falls from 0.82 to 0.31 with 10% dead cells.
- Success bar:
  - beat a threshold-plus-centroid microcontroller on wire count, ticks to decision or graceful degradation;
  - use no more cells or contact events than the hand design;
  - compete with a continuous NCA on a real sensor array (Dacre et al. 2025) and with learned-rule smart bricks (Moreno et al. 2026).
- If the application fails, the RTL still pays for itself as golden test vectors and as hard area numbers.

Why the obvious alternatives are not in the top three
- The continuous life (M6) is the project's scientific core and its main route to the ALife and evolution-of-nervous-systems audiences. It is not yet a transfer path, so its instrumentation goes into "build now".
- Loihi is not plannable: Lava has been archived since May 2026.
- The analog, chemical, neuristor and biology paths need robustness first and a partner lab.
- A motif library is premature. Only the 4-cell latch is a minimal evolved design, and it is fragile: about 0.27 at 10% mismatch, as reported by the probe.

## Success criteria (gates before any outside claim)
HOW TO READ THIS
Each criterion below is a number that can be measured on the laptop. Where data exist, I give the current status. Status comes from RESULTS.md and from a read-only robustness probe of saved organisms on 960 held-out trials, which the completeness reviewer ran this session (scratchpad probe.py, probe_a.jsonl and probe_b.jsonl). I re-read those files. They hold 5 organisms. The 4-cell-latch numbers were reported by the reviewer but are not in the saved files, so treat them as reported, not re-checked. Each criterion also names the downstream paths it gates. Nothing should be pitched outside the project until its gate passes, and each path's kill criterion should be written down before the path starts.

S0. Statistical bar for any claim used outside the project (gates all external claims)
- Requirements: at least 10 seeds; at least 960 held-out trials per final organism, with the trial seeds saved; 95% bootstrap confidence intervals; paired tests for knockouts and ablations; the winner's-curse correction reported.
- Status: fails. Runs use 3 seeds and 48 held-out trials, which gives a standard error of 0.02-0.045. jump_f8 seed 1 scores 0.80 on its 48 saved trials but 0.73 on 960. Twenty disjoint 48-trial sets for that organism range from 0.61 to 0.80.

S1. Bit-exact integer semantics (gates RTL/FPGA, ASIC, NIR/Lava export, formal verification, the zoo)
- Requirement: an integer potential with F fractional bits and a defined shift-rounding rule reproduces the float32 held-out score within 0.01 and the spike rasters tick for tick on at least 1,000 trials. The register width is set from the logged range of v.
- Status: passes at F=10 on all 5 probed organisms, and float64 equals float32 everywhere.
  - F=6 drifts: withdraw falls from 0.82 to 0.77, context hex from 0.90 to 0.73.
  - F=3 breaks withdraw (0.10).
  - Measured v spans -123 to +6.2. That means an 18-19-bit register at F=10, unless a saturating clamp is tested and holds.
- The swarm and emergence reports' figure of "about 10 bits of state per cell" is too low. A realistic figure is about 25 bits per site: an 18-19-bit v, a 2-bit refractory counter, 2 spike flags, an alive bit and a 2-bit type.

S2. Shared robustness envelope (gates every physical path: skin, swarm, MCU boards, neuristor, SCAMP, analog, self-repair, motif library)
- Requirement: keep at least 80% of the held-out score under ALL of the following at once:
  - integer F=10;
  - Gaussian v-noise of 0.05 threshold units per tick;
  - 10% per-cell mismatch on weights and gains;
  - 10% dropped spike deliveries;
  - asynchronous updates with p=0.9;
  - 10% dead cells after growth;
  - any developmental tie-break seed.
- Stretch goal: async p=0.5, plus one stuck-firing cell.
- Status: no organism passes. The closest is context square8 seed 1. It barely notices v-noise or mismatch (0.90 and 0.88 from 0.91), but keeps only 68-71% under drops, async 0.9 and dead cells, each applied alone. Every organism scores 0.12 or less at async p=0.5.
- Robustness varies by organism, not by rung. Two context winners at 0.91 and 0.90 hold 0.88 and 0.07 under 10% mismatch. The reverberating 75-cell memory falls to 0.01 under 10% drops but holds 0.80 under v-noise. Selection cannot currently see any of this.
- Path-specific add-ons:
  - Digital ASIC: dead and stuck cells only.
  - Swarm and skin: 10-30% message loss, 1-3-tick delays, irregular graphs.
  - Analog and neuristor: 20-30% mismatch plus continuous parameters.

S3. Canalized development (gates boot-time self-configuration, self-repair, the biology framing)
- Requirement: across at least 8 other developmental tie-break seeds, the worst score is at least 0.8 times the base score. Growing with 10% of sites blocked also keeps at least 0.8 times the base score.
- Status: fails for memory organisms. The 75-cell hex memory scores 0.51-0.69 on every other seed; the 4-cell latch is reported at 0.03 or less on 4 of 8 seeds. Withdraw seed 1 (0.76-0.82), jump (0.70-0.76) and context hex seed 2 (0.78-0.93) are much better.

S4. Message necessity outside the quantized cell (gates the benchmark beyond quantized cells, and the coupling-off protocol for physical and wet-lab pitches)
- Requirements:
  - With messages off, the best organism stays at or below 0.15 held-out under (a) continuous parameters, (b) input and membrane noise, and (c) the strongest messages-off version of each external model class (gradient NCA, GRU cell).
  - A ceiling with messages on of at least 0.7.
  - Multi-cell no-message bounds proved (SAT/bounded model checking up to k cells, or a light-cone argument) rather than found by search.
- Status: holds for quantized single cells only. Jump breaks unquantized: 0.55 with messages off. The withdraw bound is a quantization argument (no quantized cell first fires spontaneously after tick 10), so I expect it to fail too. That is a prediction, not yet measured.

S5. A readout that cannot be won by one spike (gates every claim that uses the lateral score)
- Requirement: either at most 30% of trials are decided by 2 or fewer window spikes, or at least one local readout scores within 0.1 of the lateral score. Candidate local readouts: edge-sector majority, the first k spikes, or one actuator bit per edge cell.
- Status: trials decided by 2 or fewer spikes are 100% for the 4-cell latch, 89% for jump and 26-44% for the others. base.yaml has min_spikes = 1.

S6. Evolved versus hand-designed cost (gates the claim "automated discovery of tiny circuits", the motif library and the ASIC tile)
- Requirement, in the style of the Humies criteria: the evolved organism matches the hand-built score with no more cells and no more contact events per decision.
- Status: the hand designs win on size.
  - Withdraw: 13 hand-built cells score 0.73; the evolved organism has 48 cells and 0.82 on one seed.
  - Context: 7 hand-built cells against about 45 evolved.
  - Jump: 19 hand-built cells at 0.68; evolved organisms reach 0.40-0.51.
  - The only minimal evolved design is the 4-cell latch.

S7. Baseline set every downstream claim must report
- hand design;
- a central decoder (a microcontroller computing threshold plus centroid over the full stimulus);
- the best no-message cheat;
- a random reservoir with a fitted readout;
- a fixed one-type disk;
- random search at an equal evaluation budget.
These are the honest competitors. On memory, random search (0.81) and a fixed disk (0.88) already match evolution. On withdraw, random search won (0.65 against 0.49).

S8. Generalization and scale (gates skins, tiling, SCAMP, swarms)
- Requirements:
  - The same genome on a fabric twice the radius (271 sites to about 1,000) keeps at least 80% of its score.
  - Hex to square8 to a jittered or irregular graph keeps at least 80% when development is re-run on the new graph.
  - Held-out score of at least 0.8 on at least 2 rungs.
- Status: untested except hex to square8 via replay.py. Withdraw waves are already tuned to the training poke distances.

S9. Energy, honestly measured (gates any energy claim)
- Requirements: report contact events (spikes times emit channels times live neighbours) per decision and ticks to decision. Make no joule or watt claim until an end-to-end measurement exists against a microcontroller or a shipping part. Innatera Pulsar quotes 400-600 µW for always-on sensing; EONS on microCaspian measured 2 mW for a 49-neuron evolved SNN.
- Status: contact events run 3 to 14 times the spike count. Withdraw seed 1: 2.96 events against 0.51 spikes per tick. Context square8: 152 against 11.2. The cost term in fitness charges spikes, which misprices what hardware would spend.

S10. Search-method claim (gates the EvoStar or GECCO paper)
- Requirement: crossover beats mutation-only on at least 3 rungs at 10 or more seeds, with non-overlapping confidence intervals. The withdraw reversal is reported: 8 founders with crossover scored 0.38 held-out against 0.49 for mutation only.
- Status: shown at n=3 on jump (0.51 against 0.24) and on context across all lattices.

S11. Continuous life: selected signalling (gates the ALIFE paper, the evolution-of-nervous-systems paper and the ecology/adversarial phase)
- Requirements:
  - In at least 5 replicate worlds, lineage survival or intake drops when counterfactual clones are run with messages off, and that dependence rises over evolutionary time.
  - It does not happen in two control worlds: one with messages off, one with uniform resources.
  - Activity statistics beat neutral shadow runs (Bedau).
  - Do not call it "open-ended" until there is novelty-plus-learnability evidence (Hughes et al. 2024) and the MODES metrics do not plateau.
- Status: not built. Prototype scripts exist under scratchpad/one_life.

S12. Kill criteria, written before each path starts
Example: "if noise-envelope evolution cannot reach 0.6 held-out with 80% retention on any rung in 10 seeds, close the analog, swarm and skin paths and scope the hardware claims to bit-exact synchronous digital logic."

## Tiers: near, mid, long term
STARTING POINT (honest inventory; this changes what can be ported)
- Hand-built, not evolved: the 13-cell C-ring that routes a wave away from a poke (the withdraw proof). Correction: the 10-cell "horseshoe" in the atlas is the EVOLVED withdraw organism (withdraw_v2 seed 1), not a hand design. The context hub (7 cells) and the jump sender/relay disk (19 cells) are hand-built too.
- No messages: the evolved "motion hub" scores 0.36 held-out with messages on or off. It works by placing cell types, so it is not a learned motion detector.
- Evolved organisms that do depend on messages:
  - the 4-cell inhibitory latch: square8 seed 0, 0.87, one type, w=-2, leak 1/16;
  - the 2-type context organisms: 45-78 cells, 0.73-0.91;
  - withdraw seed 1: 48 cells, 0.82-0.83, falls to 0.05 when its types are shuffled;
  - small one-type jump organisms: 9-50 cells, 0.40-0.73.
- Evolved memory organisms are reverberating tissues of 75-100 cells. A fixed disk and random search match them.
- Timing caveat: for one person on a laptop, expect anything involving hardware, robots or a partner lab to take 3-5 times the optimistic estimates below. One 200-generation run (about 52k evaluations) takes about 10-20 minutes, so 10-seed sweeps fit overnight.

NEAR TERM (weeks 1-6, laptop only; these are gates, and each result decides which later doors open)

N1. Integer fixed-point model as the definition of the simulator
- What: F=10, an 18-19-bit v (or a tested saturating clamp), a defined shift-rounding rule, 8-bit stimulus input. Keep float32 as a cross-check.
- Effort: 1-3 days. Depends on: nothing.
- First demo: re-score every saved best_genome.json. Pass means held-out within 0.01 and messages-off still 0.
- Unlocks: M1 (RTL), M2 (NIR/Lava), N6 (formal checks), the zoo.
- Already passes in the probe. This step makes it official and removes the float32 round-up firing quirk.

N2. Robustness panel and selection for robustness: the decisive experiment
- What:
  - (a) Add the S2 panel (plus quantize=false, a lattice swap and 8 tie-break seeds) as standard columns in results.jsonl. Minutes per run.
  - (b) Evolve under a noise envelope: fresh tie-break seed, v-noise, mismatch, drops, async p of about 0.9 and dead cells, drawn fresh per evaluation as trials already are, with a contact-event cost (Jakobi's envelope of noise).
- First demo: context and withdraw × {plain, envelope} × 10 seeds, overnight.
- Kill: if no rung reaches 0.6 held-out with 80% retention, close the analog, swarm, skin and neuristor paths.
- If it passes: M1, M3 and later L2-L4 become justified.
- Either way it yields a publishable table of which message motifs survive which fault models. For example, reverberating memory dies under spike drops, while the context organisms split between drop-tolerant and noise-tolerant.

N3. Cheat hunters with continuous parameters and noise, on all message rungs
- What: the existing red-team harness plus quantize=false and a noise term.
- Effort: days.
- If the withdraw and context floors stay at 0.15 or below, the benchmark extends to continuous models, and a coupling-off protocol for physical reservoirs and cultured networks becomes pitchable.
- If not (my expectation for withdraw), scope every certificate to quantized cells and drop the wet-lab and material pitches.

N4. Cross-fabric and network realism
- What:
  - an irregular or jittered graph builder (the lattice is already a padded neighbour table);
  - 1-3-tick link delays and 10-30% message loss;
  - the same genome on a fabric twice the radius.
- Note: grown type maps do not port; development must re-run on the new graph. The diffusion stability bound uses lattice.full_contact, so irregular degree changes growth.
- Effort: about 1 week.
- Pass (0.6 or more on withdraw and context under loss and jitter, after N2) opens the MCU-board, skin and swarm demos. Fail closes them at near-zero cost.

N5. When does signalling pay? A threshold sweep
- What: sweep poke distance, memory delay and the fraction of cells that can sense the cue, against the best message-free solution, net of contact-event cost (scripts/sweep.py).
- Effort: about 1 week.
- A clean threshold that holds across lattices directly designs the continuous-life environments (M6). It is also the seed of an evolution-of-nervous-systems argument; see the skin-brain thesis (Keijzer et al. 2013).

N6. Formal certificates (the gap no report proposed)
- What: on the integer model, a tissue is a finite-state synchronous system. Use SAT, SMT or bounded model checking to:
  - prove the no-message ceiling for all k-cell tissues up to small k;
  - prove the 4-cell latch's behaviour over all directions and delays within the tick horizon, or find a counterexample.
- Pen-and-paper part: in the beeping-network model, a light-cone or indistinguishability argument shows that no messages-off tissue solves withdraw and that decision time is at least the hop distance.
- Effort: 1-3 weeks. Limit: state space restricts it to about 20 cells or fewer and bounded horizons.
- This is what gradient-trained NCA and GNN competitors cannot offer.

N7. Benchmark package skeleton (after N3)
- What: tasks, certify.py, frozen held-out splits, documented leak bounds (jump about 0.13, context 0.17, withdraw 0.02), and a baseline table.
- Baselines: random search, fixed disk, evolution with and without crossover, messages-off, and one CMA-ES (evosax) or CAX NCA baseline held to the messages-off floor.
- Effort: 1-2 weeks.

Optional short paper
- What: crossover across founder breeds, with 10 seeds on 3 rungs.
- Venues: EvoStar 2027, deadline 1 Nov 2026, 26 days away (tight); GECCO 2027 is more realistic.
- Must report the withdraw reversal and compare against ALPS and Hierarchical Fair Competition.

MID TERM (2-6 months; mostly conditional on the near-term gates)

M1. Bit-exact RTL tissue
- Depends on: N1, and N2 for a robustness table.
- What: Verilator or cocotb co-simulation of the 4-cell latch, withdraw seed 1 and one context organism, matching the integer model's rasters tick for tick. Then a Yosys resource report giving LUTs and flip-flops per site and the maximum tick rate. Then an ECP5-85-class FPGA (a fully parallel 271-site fabric likely does not fit an iCE40) or a time-multiplexed engine, with buttons or photodiodes in and LEDs out.
- Effort: 1-3 weeks if fluent in HDL, longer otherwise.
- Value: real area numbers and a "genome compiles to logic" artifact.
- Honest limit: TrueNorth (per-input-type weight tables) and Xylo (v - (v >> dash) leak) show the neuron math is already in silicon. This proves buildability, not advantage. Using the FPGA as an evolution accelerator is unrealistic (realism about 3), because the stimulus, development compiler and scoring would all have to move onto the chip.

M2. Neuromorphic portability test
- Depends on: N1.
- What: export once to NIR, which reaches Rockpool/Xylo, Sinabs/Speck, SpiNNaker2, Lava and others, and cross-check against Lava's bit-accurate CPU LIF model. Any drift in score is a free portability measurement.
- Platform status:
  - Lava is archived (GitHub archived=true, last push 2026-05-13), so a Loihi 2 hardware run cannot be planned.
  - Xylo has 16 input channels, which caps local sensing at about 16 cells.
  - Whether NIR supports refractory and reset semantics is unverified.

M3. Tactile reflex sheet
- Depends on: N2 and N4 passing.
- What, in order:
  - simulated taxel patch: variable pressure blobs, multi-touch, sliding contact, 5-10% dead taxels;
  - firmware on 19-37 hex microcontroller boards with asynchronous neighbour messages (DIY-feasible);
  - or the open embedded-NCA platform of Woiwode et al. 2025.
- Must beat a threshold-plus-centroid microcontroller on wiring, latency or graceful degradation, not accuracy.
- Competitors: Dacre et al. 2025 (a continuous NCA on a real sensor array) and the smart bricks of Moreno et al. 2026.

M4. Information-dynamics atlas
- What: local transfer entropy and active information storage (JIDT/IDTxl) on spikes and voltage, checked against knockouts.
- Doubles as the task-free message detector the continuous life needs.
- Needs voltage logging, because the latch stores its state below threshold.

M5. Evolution versus surrogate-gradient training on the fixed-disk quantized tissue, plus a CAX NCA comparison held to certified floors
- Answers whether the contribution is the search method or the substrate.

M6. Continuous life v1 (the user's plan; the main science)
- Depends on: N5 for environment design. Probably needs a faster simulator: int16 or bit-packed, or JAX.
- Contents: energy intake, in-world reproduction, lineage logging and periodic messages-off counterfactual clones from day one.
- Expect a plateau by default (Bedau; PBT-NCA collapses).
- Success is S11.

M7. Readout becomes actuation
- What: a 2D mass-spring body; withdraw becomes "move away from the poke".
- Red-team it: one oscillator per voxel can walk without messages.

M8. Ecology factorial as the first adversarial phase
- Factors: clonal versus chimeric tissues, jammer cells, spike cost.
- Floreano et al. 2007 predicts honest signalling only under high relatedness.

M9. Lifetime plasticity per cell type (bridge to alt-arcs)
- Note the conflict: a weight per contact is exactly the synapse memory the hardware pitch says cell-dev avoids.

LONG TERM (6+ months; needs partners or fabrication; speculative)

L1. Tiny ASIC tile on an open-PDK shuttle
- Status: Tiny Tapeout is live and was reported with SKY26d and GF26c open.
- Only after M1 and N2. It is a credibility demo, not a result. A hand-designed latch would be smaller, and isolating one design's power on a shared die is doubtful (unverified).

L2. Real e-skin or printed electronics with a partner lab
- Context: the HEX-o-SKIN hexagonal cells and ACES event-coded skin show the demand.
- Printed electronics needs tolerance to 20-30% device variation, which no organism shows today.

L3. Swarm or modular robots
- Smart bricks or open embedded-NCA hardware are more accessible than Kilobots (commercial availability unverified; the product page returns 404).
- Timing-based mechanisms (jump, withdraw) are most at risk under IR message delays.

L4. Analog and material substrates
- Options:
  - VO2 thermal-neuristor lattices (Qiu 2023; Zhang 2024);
  - SCAMP in-pixel processing (Dudek group);
  - light-programmed BZ droplets (Gorecki, Epstein or Adamatzky groups).
- All need robustness under N2 first, and a single-isotropic-channel re-evolution, because heat and diffusion carry no channel label or sign. Their value is design principles, not computing power.

L5. On-chip development and self-repair ("Embryonics without coordinates")
- Needs canalization (S3) first.
- A GRN at every site likely costs more area than the cell it configures, so compile-time growth wins unless faults are frequent.

L6. Biology
- Pitch only the coupling-off control protocol for MEA and micropattern cultures, and only if N3 holds.
- The evolution-of-nervous-systems theory paper comes from M6.
- Do not pitch neurobot layouts or the 4-cell latch as a biological spec. Gap junctions have no signed inhibition, and ticks have no units.

L7. Open-endedness claims and the ALIFE 2027 paper (Prague, 19-23 July 2027; deadline not yet posted)

UNLOCK MAP (if X succeeds, do Y next; if it fails, do Z)
- Integer F=10 equivalence (already passing): RTL/FPGA, NIR/Lava export, formal verification and the zoo become worth doing.
- Robustness evolvable (N2 passes): tactile sheet and MCU boards, then the swarm, neuristor and SCAMP simulations, then the ASIC tile and the motif library.
  - If it fails: claim bit-exact synchronous digital only, and publish the fault-model table.
- Canalization evolvable: boot-time self-configuration and self-repair, and the developmental-biology framing.
- Floors survive continuous parameters and noise (N3): a broad benchmark across NCA, GNN and SNN, plus coupling-off protocols for physical reservoirs and cultured neurons.
  - If they fail: a quantized-cell benchmark still serves neuromorphic and digital local learners.
- Signalling threshold found (N5): the continuous-life environment design and an evolution-of-nervous-systems argument.
- Signalling selected in the continuous life (S11): the ALIFE paper, then the ecology/adversarial phase and the actuation path.
- Crossover holds at n of 10 or more: the EvoStar or GECCO methods paper.
- Nothing passes: deliverables are the quantized-cell benchmark with formal certificates, the robustness/fault-model table, and the search-methods paper. All three remain useful.

WHAT WILL NOT TRANSFER (do not claim)
- Growth itself: silicon does not divide, so development becomes a configuration-time compiler.
- Exact one-hop-per-tick timing on asynchronous substrates: every organism scores 0.12 or less at async p=0.5.
- Signed two-channel coupling on heat, diffusion or gap-junction media.
- The free global readout: it must be built (an adder tree or AER address stream) or become actuation.
- Energy figures in arbitrary units, and back-of-envelope pJ and µW estimates.
- Fault tolerance and self-repair: none measured, and the current data argue against them.
- "Novel capability": each mechanism has a hand-designed counterpart (wavefront routing, the Reichardt/sEMD motion detector, the winner-take-all latch). The defensible claim is narrower: small, local circuits with certified message use, found automatically under a hardware cost model, and only once S1, S2 and S6 hold.
- "Open-ended" and "emergent communication": the channels are 2 binary lines with no symbols.
- The organisms as biological predictions.

## Build into the experiments now
Each item is cheap, minutes to a couple of days. Most cannot be reconstructed later, so add them before the next sweeps and before the continuous life starts. This is a read-only task, so these are recommendations; I changed no project files.

1. Integer potential as the default
- What: F=10 fractional bits, an explicit shift-rounding rule, an 8-bit quantized stimulus. Keep float32 as a cross-check flag.
- Also log v min/max and the fraction of firings within 1/16 of threshold.
- Why: hardware, verification and replay all need it.
- Measured: v spans -123 to +6.2, so about 18-19 bits; 20% of the 75-cell memory's firings sit within 1/16 of threshold. Test whether a saturating clamp holds.

2. A robustness panel as standard results.jsonl columns
- Columns:
  - integer F10 and F6;
  - v-noise 0.05 and 0.15;
  - mismatch 10% and 25%;
  - 10% spike drops;
  - async p=0.9 and p=0.5;
  - 5% and 10% dead cells;
  - one stuck-firing cell;
  - 8 other developmental tie-break seeds (min/median);
  - quantize=false;
  - a lattice swap.
- The probe script in the scratchpad already does most of this in minutes per organism.

3. A fresh developmental tie-break per evaluation
- What: draw develop.jitter_seed per evaluation instead of once per run (it is ${seed} in base.yaml).
- Why: the fixed tie-break noise is a hidden overfitting channel; the 4-cell latch is reported at 0.03 or less on half of the other seeds. A one-line change that selects for canalized growth.

4. Noise-envelope evolution options
- What: config flags for per-evaluation v-noise, mismatch, drops, async p and dead cells, so robustness can be selected for, not just measured.
- Add an async update probability to run_cells. A cell that does not update holds its state and sends nothing.

5. A statistically honest final evaluation
- What: at least 960 held-out trials with saved trial seeds and per-trial scores, bootstrap 95% confidence intervals, and paired knockouts.
- Make 10 seeds the rule for any result that will be quoted outside the project.

6. Hardware-relevant cost metrics, logged next to spikes
- What: contact events (spikes × emit channels × live neighbours) per tick and per decision; ticks to decision (the first tick at which the cumulative lean is correct); silent-trial fraction; fraction of trials decided by 2 or fewer window spikes.
- Optionally charge energy per contact event: it runs 3-14 times the spike count, so the current spike cost misprices hardware energy.

7. Local readouts logged next to the lateral score
- What: edge-sector majority, first-k spikes, and one actuator bit per edge cell.
- Why: tells early whether results depend on the omniscient global readout. Also consider raising min_spikes above 1.

8. Static cost of each organism
- What: configuration bits, state bits per site, maximum fan-in, live cells (a proxy for static leakage), and cell count against the hand-built reference (the S6 bar).

9. The full knockout map plus per-channel and per-type emit knockouts
- measure.knockouts already computes knockout_map; run.py does not save it.
- This is the ground truth for the information-dynamics atlas and for mechanism labels.

10. Lineage logging
- What: parent indices and crossover unit masks for survivors each generation, a breed ID per individual, population diversity (mean pairwise genome distance, breeds still represented), and the final 32×250 population, not just the best genome.
- Why: without this, MODES/hstrat analyses and crossover-provenance claims are impossible after the fact.

11. Golden vectors
- What: rasters plus voltages for a fixed set of held-out trials of each best organism.
- Uses: RTL equivalence tests, NIR/Lava drift tests, information dynamics, zoo entries.

12. A baseline row in every table
- hand design;
- a central decoder ceiling (threshold plus centroid over the full stimulus);
- best no-message cheat;
- random reservoir with a fitted readout;
- fixed disk;
- random search at equal budget.

13. Two cheap knobs for transfer questions
- What: an irregular or jittered neighbour-graph builder (the table is already padded with -1), and evaluation on a fabric twice the radius.
- Why: answers the cross-fabric and scale questions without new physics.

14. For the continuous life, from day one
- periodic counterfactual clones with messages off, per lineage;
- birth and death events with parent IDs (hstrat-compatible);
- an energy-budget breakdown (intake, living, firing, contact events, division);
- sampled rasters and voltages;
- the same robustness flags, so signalling can emerge under realistic noise rather than be fragile from the start.

15. Pre-registered kill criteria
- What: one line per planned path, written before the run, in the run's notes.
- Example: "envelope evolution fails to reach 0.6 with 80% retention on any rung in 10 seeds → close the analog, swarm and skin paths."

## References
Verification tags
- [checked] I resolved the title and year myself this pass, through the Crossref API, the arXiv API, the GitHub API or an HTTP 200 fetch.
- [researcher] A research or critique agent checked it this session; I did not re-check it.
- [unverified] Noted as such.
- Content descriptions beyond titles are the researchers' summaries.

SILICON AND NEUROMORPHIC
- Esser et al. 2016, TrueNorth neuron: per-input-type 4-entry weight table, integer threshold. https://arxiv.org/abs/1603.08270 [checked]
- Merolla et al. 2014, TrueNorth (Science). https://doi.org/10.1126/science.1254642 [researcher]
- SynSense Xylo docs: v - (v >> dash) leak, 16 input channels. https://rockpool.ai/devices/xylo-overview.html [checked]
- Lava (Intel Loihi SDK). The repo is archived, last push 2026-05-13. https://github.com/lava-nc/lava [checked via GitHub API]
- Pedersen et al. 2024, Neuromorphic Intermediate Representation (NIR). https://doi.org/10.1038/s41467-024-52259-9 and https://github.com/neuromorphs/NIR [checked]. NIR support for refractory and reset semantics [unverified].
- Frenkel et al., ODIN, a 28 nm digital SNN core. https://arxiv.org/abs/1804.07858 [researcher]
- Ghawaly, Schuman et al. 2025, EONS-evolved SNNs on microCaspian: 2 mW. https://arxiv.org/abs/2510.20997 [checked]
- Innatera Pulsar: 400-600 µW always-on sensing. https://www.innatera.com/newsroom/innatera-unveils-pulsar-the-worlds-first-mass-market-neuromorphic-microcontroller-for-the-sensor-edge/ [researcher]
- Dudek et al., SCAMP pixel-processor arrays. https://personalpages.manchester.ac.uk/staff/p.dudek/scamp/ [researcher]
- Tiny Tapeout (open-PDK shuttles). https://tinytapeout.com/ [checked]

EVOLVABLE AND DEVELOPMENTAL HARDWARE (prior art and cautions)
- Thompson 1997, An evolved circuit, intrinsic in silicon, entwined with physics. https://doi.org/10.1007/3-540-63173-9_61 [checked]
- Mange et al. 2000, Embryonics. https://doi.org/10.1109/5.842998 [checked]
- Sipper et al. 1997, Firefly evolware. https://doi.org/10.1109/icec.1997.592292 [researcher]
- Chua & Yang 1988, Cellular neural networks. https://doi.org/10.1109/31.7600 [researcher]
- Bose et al. 2015, evolution in materio (nanoparticle network). https://doi.org/10.1038/nnano.2015.207 [checked]
- Dean, Schuman & Birdwell 2014, DANNA, an evolved spiking lattice on FPGA. https://doi.org/10.1007/978-3-319-08123-6_11 [researcher]

ROBUSTNESS AND SIM-TO-REAL
- Jakobi 1997, envelope of noise. https://doi.org/10.1177/105971239700600205 [checked]
- Mordvintsev et al. 2020, Growing NCA: robustness comes from training with damage. https://distill.pub/2020/growing-ca/ [checked]
- Siegal & Bergman 2002, Waddington's canalization revisited. https://doi.org/10.1073/pnas.102303999 [checked]
- Kriegman et al. 2020, xenobot pipeline with a robustness filter before building. https://doi.org/10.1073/pnas.1910837117 [checked]

FORMAL MODELS AND VERIFICATION (gap filled by the completeness review)
- Cornejo & Kuhn 2010, Deploying Wireless Networks with Beeps (the beeping model). https://doi.org/10.1007/978-3-642-15763-9_15 [checked]
- Afek et al. 2011, A Biological Solution to a Fundamental Distributed Computing Problem. https://doi.org/10.1126/science.1193210 [checked]
- Emek & Wattenhofer 2013, Stone Age Distributed Computing. https://doi.org/10.1145/2484239.2484244 [checked]
- De Maria et al. 2016, verification of LIF neuronal archetypes as synchronous reactive programs. https://doi.org/10.1007/978-3-319-47151-8_7 [checked]
- Koza 2010, human-competitive results (the Humies bar). https://doi.org/10.1007/s10710-010-9112-3 [checked]

BENCHMARK NEED AND COMPETITORS
- Lowe et al. 2019, On the Pitfalls of Measuring Emergent Communication. https://arxiv.org/abs/1903.05168 [checked]
- Tönshoff et al. 2023, Where Did the Gap Go? (LRGB). https://arxiv.org/abs/2309.00367 [checked]
- Balci et al. 2023, response to the DishBrain claims. https://doi.org/10.1016/j.neuron.2023.02.009 [checked]
- Miotti et al. 2025, Differentiable Logic CA (learned local rules as gate circuits). https://arxiv.org/abs/2506.04912 [checked]
- Etcheverry et al. 2026, Reasoning with Neural Cellular Automata. https://arxiv.org/abs/2609.36126 [checked]
- Nadizar et al. 2022, embodied Spiking Neural Cellular Automata: the closest spiking local-message prior art. https://arxiv.org/abs/2204.02099 [checked]
- Faldor & Cully 2024, CAX. https://arxiv.org/abs/2410.02651 [researcher]

SKIN, SENSOR SHEETS AND MODULES (application targets)
- Lee et al. 2019, ACES asynchronously coded electronic skin. https://doi.org/10.1126/scirobotics.aax2198 [checked]
- Mittendorfer & Cheng 2011, HEX-o-SKIN hexagonal skin cells with neighbour links. https://doi.org/10.1109/tro.2011.2106330 [checked]
- Dacre et al. 2025, an NCA for decentralized sensing on a real soft sensor array. https://arxiv.org/abs/2502.01242 [checked]
- Moreno et al. 2026, Smart cellular bricks for decentralized shape classification and damage recovery. https://doi.org/10.1038/s41467-026-75166-7 [checked]
- Beal, Pianini & Viroli 2015, aggregate programming (the engineered-protocol baseline). https://doi.org/10.1109/MC.2015.261 [checked]

MATERIAL SUBSTRATES (long-term, speculative)
- Zhang et al. 2024, thermal neuristor networks. https://doi.org/10.1038/s41467-024-51254-4 [checked]
- Qiu et al. 2023, cascaded thermal neuristors. https://doi.org/10.1002/adma.202306818 [researcher]
- Motoike et al. 2001, ring memory on an excitable field (BZ). https://doi.org/10.1103/physreve.63.036220 [checked]
- Dillavou et al. 2022, decentralized physics-driven learning. https://doi.org/10.1103/physrevapplied.18.014040 [checked]

EMERGENCE, OPEN-ENDEDNESS AND THE CONTINUOUS LIFE
- Hughes et al. 2024, Open-Endedness is Essential for ASI (the definition to meet). https://proceedings.mlr.press/v235/hughes24a.html [checked]
- Dolson et al. 2019, MODES toolbox. https://doi.org/10.1162/artl_a_00280 [checked]
- Berdica et al. 2026, PBT-NCA "Evolving Many Worlds" (collapse failure modes). https://arxiv.org/abs/2604.11248 [checked]
- Masumori et al. 2026, information dynamics in growing NCA. https://arxiv.org/abs/2607.12403 [checked]
- Lizier et al. 2008, local transfer entropy. https://arxiv.org/abs/0811.2690 [researcher]
- Floreano et al. 2007, evolutionary conditions for communication in robots. https://doi.org/10.1016/j.cub.2007.01.058 [checked]
- Keijzer et al. 2013, the skin-brain thesis. https://doi.org/10.1177/1059712312465330 [researcher]
- Zador 2019, A critique of pure learning (genomic-bottleneck framing). https://doi.org/10.1038/s41467-019-11786-6 [checked]

VENUES
- EvoStar 2027, deadline 1 Nov 2026. https://www.evostar.org/2027/ [checked]
- GECCO 2027, deadline not posted. https://gecco-2027.sigevo.org/ [researcher]
- ALIFE 2027, Prague. https://alife.org/conference/ [researcher]

UNVERIFIED OR OPEN
- SpiNNaker's six-link hex-like chip mesh.
- Whether Speck can host recurrent lattices.
- Kilobot commercial availability (the product page returns 404).
- Xylo dev-kit availability.
- Power isolation for one design on a Tiny Tapeout die.
- Whether EvoGym, Kilombo and ARGoS install and run here.
- The 4-cell-latch probe numbers: reported by the reviewer but absent from the saved probe files.
- The researchers' cost and area estimates (0.25 µW, 12.7 pJ/event, 100-200 LUTs per site): back-of-envelope, not measured. Do not quote them externally.
