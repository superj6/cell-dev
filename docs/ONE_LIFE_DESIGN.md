# One continuous, clockless life: design proposal

Produced 2026-10-06 by the `one-life-design` workflow (4 designers, 3 judges, synthesis), with the verified expressivity
audit (`scratchpad/one_life/audit_ranked.json`) and the red-teamed BELL-1 task (`scratchpad/one_life/bounded_task.json`)
as binding inputs. Status: PROPOSAL, awaiting the user's approval; nothing is implemented yet.

## Summary
Each genome gets one continuous life with no clock. A zygote grows into a body by local division, each cell on its own jittered clock. Its cells spike, change identity and die under the same local event rules from t = 0 to T = 1024. Every effect of one cell on another takes at least d_min = 0.5, so the model has no global step and no update order. The organism is the agreed one-life model: exact leaky integrate-and-fire (LIF) cells, two unlabeled spike channels, a gene network on private clocks whose quantized readout sets every physiological and fate knob, in-tissue morphogen packets, and earliest-claim division. Three things are added: genome-driven apoptosis that empties sites so neighbours can refill them (death is required); a separate contractility (effector) knob; and directional, chiral and gene-duplication capacity from the expressivity audit, all dormant at the start.

The first world is BELL-1, a single lumen pumped by the whole body:
- It pays only when most cells contract together, and it refills only when all of them relax.
- Cells sense nothing from it, so the beat can only be agreed through spikes between neighbours.
- Fitness is pumped volume minus per-action costs. Cells hold no energy, nothing can starve, and there is no size term.

Measured in the clockless prototype:
- A lone cell earns +0.033, and every body without messages earns less.
- A leaderless delayed-inhibition organism with layered growth and newborns that listen before they talk peaks at about 91 cells (+0.93, 28 times a lone cell) and loses money beyond that.
- So bounded growth is optimal, and every better message-passing algorithm raises both the best size and the earnings.

Later stages change one thing at a time: turnover and wounds, drifting heterogeneity, energy and starvation, threats, location-dependent roles, then crawling and foraging. All of them run on a C event kernel. Measured costs: 0.14-0.18 µs per cell per time unit for spikes plus the world, and 0.21 µs per gene tick. The kernel's own window scheduler and a Python reference serve as bitwise test oracles.

## Time model (no central clock)
THE MODEL (independent of any simulator)
- Time t is a real number. There is no step counter, no tick, and no variable that two cells read. No cell input is a function of t, so cells cannot see a clock.
- A cell's state changes only at its own events:
  - ARRIVAL: a spike from a contact.
  - THRESHOLD: its own membrane drifting to 1. Predicted in closed form and invalidated by a per-cell version counter.
  - TICK: its own private metabolic clock. Genes, identity, chemistry, death and division happen only here.
  - CONTACT: a neighbour was born, is present, or died.
  - ACK / REJECT: the answer to its own division claim.
  - From v2: KILL (exogenous loss). From v5: RECEPTOR.
- Morphogen packets go into the receiver's inbox and are consumed at the receiver's next own tick.
- Between events everything is closed form: membrane, traces, twitch decay, and the BELL lumen (R, P). No equation in the model is stepped numerically.

CAUSALITY CONTRACT (the one global physics rule)
- Every effect of one cell on another takes at least d_min = 0.5. This covers spikes, contact notices, division claims, ACK/REJECT, morphogen packets, and energy packets from v4.
- Spike delay from i to contact j: d = max(d_min, d_c[i->j]·(1 + 0.1·(2u − 1)) + δ_i).
  - d_c is lognormal (σ = 0.1) around 1. It is frozen when the contact forms, keyed by hash(life seed, both coordinates, both birth counts, direction).
  - u = hash(life seed, sender uid, the sender's OWN spike count, slot). It is drawn per event and per cell, not from an organism-wide counter (the audit's residual).
  - δ_i ∈ {0, 0.5, 1, 2} is genetic.
  - The jitter multiplies the WHOLE base delay, so relays with δ = 0 are never exactly in lockstep. This fixes bio's measured tie bug: 6380, 6393 and 6386 spikes under three tie orders, and a relay that fired 5, 3 or 1 times.
- Neighbours learn of a birth or a death at +d_min. A newborn learns its neighbours from CONTACT(present) replies at +2·d_min.
- The world (the lumen) reads cells only as left limits: state strictly before t. In v1 it sends nothing to cells. From v2 on, every world-to-cell effect arrives at least d_min after its cause and comes from hash-keyed Poisson streams.
- Only a cell's effects on itself are instantaneous.

TIES (order-free by rule)
(a) Events at different cells less than d_min apart cannot affect each other (Chandy-Misra-Bryant lookahead). So every causally valid processing order gives the same history.
(b) A cell's events with an identical timestamp form one batch, applied in a fixed kind order:
  1. contact notices, ACK and REJECT;
  2. all arrivals summed into one input with one threshold test (a crossing predicted for the same instant is subsumed);
  3. the tick.
(c) A claim reads the site's occupancy as a left limit. If two claims reach one site at the same instant, the lower hash(mother uid, division count) wins.
(d) Twitches, births and deaths with one timestamp form one world batch.
Continuous delays and jittered clocks make exact ties a measure-zero event. The rules cover the rest.

LOCAL CLOCKS (slow layer)
- Cell n ticks with period P_n·(1 + 0.1·(2u_k − 1)), where P_n = P0·exp(0.05·z_n), P0 = 2, and z_n comes from the frozen-physics hash. Its first tick falls at a random phase after birth.
- The gene update is a discrete map applied at the cell's own ticks. That map IS the model; it is not an ODE that the clock integrates.
- So P0 is a local model parameter, not a numerical step. This answers the judge's measurement that P0 = 2 is a biased ODE integrator (+0.024 fitness at 4.8 SE).

RANDOMNESS
- Frozen physics (contact delays, tau mismatch, clock rate and phase) is keyed by (life seed, site coordinates, birth count at that site). Consequences:
  - the same place has the same physics for every genome in a generation (true common random numbers);
  - the same genome grows the same body on any fabric size (audit item 5c).
- Event draws are keyed by (life seed, uid, the cell's own counter, stream). They cover delay jitter, tick jitter, division and death draws, placement noise, and drops in the robustness panel.
- A draw is a property of an event, never of processing order.

REGISTERS
- v: Q10 int32, rounded only at the cell's own events (DOWNSTREAM item 1).
- Time: float64.
- g and m: float64. They stay continuous because the audit showed 10-bit gene rounding freezes slow genes 1/16 short of their target.
- Integer twin (compile flag), for bit-exact cross-machine replay and hardware: int64 time in 2^-20 units, Q24 for g and m, and lookup-table exp and ln.

DEATH IN THE TIME MODEL
- Apoptosis is decided at the dying cell's own tick, so it is a self-event.
- Its effect on others travels as CONTACT(died) at +d_min.
- Spikes already in flight to the dead cell are dropped on arrival by a uid check. Packets in its inbox are lost and logged.
- A claim reaching the site after the death finds it empty (left limit) and wins. A claim arriving before the death is rejected.
- The world removes the dead cell's z from the lumen mean at the death time. Nothing flows back to cells.

SIMULATORS
- Production: a C kernel with one binary heap per life, structure-of-arrays state, and OpenMP over lives. Lives are independent, so results do not depend on thread count or batch composition.
- Test scheduler, in the same kernel: conservative windows [k·h, (k+1)·h) with h ≤ d_min.
  - Cells are visited in a seeded random order, and each processes its own events in time order.
  - The world accountant then consumes the window's log sorted by (t, uid).
  - Both schedulers share every arithmetic routine, so whole lives can be compared bitwise.
- Specification: a pure-Python heapq reference of the same model, bitwise equal on short lives (same libm).

WHY RESULTS CANNOT DEPEND ON A SHARED STEP OR UPDATE ORDER
- Lookahead (a) plus the batch and tie rules (b-d).
- State is anchored at events, and threshold crossings are closed form.
- Randomness is keyed to events.
- The model contains no numerical integration.
- Today's failure cannot occur: every current organism collapses to 0.12 or less under asynchronous updates because one hop takes exactly one global tick. Here a hop takes 1 ± 10% × frozen mismatch + δ, and asynchrony is the native regime.

ALREADY MEASURED ON PROTOTYPES
- async_bio:
  - window sizes h = 1, 1/2, 1/4 and 1/8 gave bitwise-identical lives (6258 spikes);
  - the heap reference under random tie orders matched to 1.4e-14;
  - the C kernel matched to 1.1e-13.
- env_stream:
  - h = 0.5, 0.25 and 0.125 bitwise identical (204,940 spikes in 256 lives);
  - a heapq simulation with random tie order differed by exactly 0.0.
- clockless_feas/evlife.c: bitwise identical across thread counts, batch compositions and tie-order permutations.
- task_bell/bell3.c (BELL world with local division):
  - 1 and 4 threads give identical results;
  - the closed-form lumen agrees with Euler integration (dt 1e-3) to 0.03-0.08%.

TESTS (CI, tests/test_life_time.py; whole lives including growth and death)
- T1: window scheduler at h = 0.5, 0.25 and 0.125, each with 3 random cell orders. The event-log hash (spikes, births, deaths, claims, packets, ledger) must equal the heap scheduler's bitwise.
- T2: random tie keys in the heap give bitwise-identical results.
- T3: Python reference vs kernel, bitwise (20 cells or fewer, T ≤ 200).
- T4: bio's counterexample, the relay triangle with δ = 0 and opposite-sign channels, is invariant under 10 tie orders.
- T5: site relabelling, thread count and batch composition are all bitwise.
- T6: time translation (zygote and world start at t0 = 1024). Bitwise in the integer twin; |ΔF| < 1e-9 in float.
- T7: rotation equivariance (60° on hex, 90° on square8) leaves F statistically equal. Mirror equivariance holds when χ = 0, so handedness enters only through χ.
- T8: for evolved organisms, spike phases modulo P0, τ_R, τ_z and τ_e are uniform (KS p > 0.01). This rules out a hidden frame clock.
- T9: integer-twin time quantum 2^-16 vs 2^-20, and twin vs float. The signed paired ΔF must be within 2 SE and below half the lifetime yardstick (ΔF between two lives of the same genome). This is the "halve the step" test for the only quantization left.
- T10: P0 ∈ {1, 2, 4}, reported as a signed paired ΔF ± SE. It is a model-sensitivity number, not pass/fail.
- T11: deaths, refills and extinction under the window scheduler are bitwise identical.
- T12: a sparse fabric and a dense radius-14 fabric give bitwise-identical lives while the body stays inside radius 14, so cells cannot sense the fabric.
- A lockstep control (every d_c = 1, no jitter, no mismatch, clocks in phase) runs as its own condition, never as the default.

## What a cell does when it updates
There is no global tick. Below are cell n's state and the handlers that run at its own events, for v1. Additions in later stages are marked.

STATE OF CELL n
- Identity: alive; uid = H(mother uid, mother's division count); site (axial coordinates); counters spike#, tick#, div#.
- view[D]: a uid or "empty" for each contact slot. Changed only by CONTACT and ACK.
- Membrane: v_a (Q10), t_a, t_r (end of refractory), ver.
- Phenotype θ: 21 knobs, plus cached w_eff[D][2] (directional receiver weights per slot).
- Traces with one anchor time: f (own spikes) and r[2] (received spikes per channel). Their time constant tau_tr comes from θ.
- Twitch: z, t_z.
- Genes and chemistry: g[16] (inactive slots stay 0), morphogen content m[2], and inc[D][2] (the sender concentration in the last packet from each slot).
- Clock and division: P_n, t_prev, claim_pending.
- Inbox: packets (t_arr, sender uid, slot, amount[2], conc[2]).
- From v4: energy E.

MEMBRANE BETWEEN EVENTS
  v(t) = 0                                               for t < t_r
  v(t) = b + (v0 − b)·exp(−(t − max(t_a, t_r))/τ_m)      otherwise
  where v0 = v_a if t_a ≥ t_r, else 0.

PREDICT
  ver += 1
  if b > 1 and v0 < 1: schedule THRESHOLD(ver) at max(t_a, t_r) + τ_m·ln((b − v0)/(b − 1))

BATCH(t): all of cell n's events at exactly t
1. Notices:
   - CONTACT(born, uid', slot d): view[d] = uid'; reply CONTACT(present, uid_n) to slot d at t + d_min.
   - CONTACT(present, uid'): view[d] = uid'.
   - CONTACT(died): view[d] = empty.
   - ACK(d*): claim_pending = 0; view[d*] = daughter.
   - REJECT: claim_pending = 0.
2. Drop arrivals whose target uid is not the current occupant. Decay traces to t; r[c] += count_c (counted even while refractory).
3. If t ≥ t_r:
     v = v(t) + Σ over arrivals of w_eff[slot][c]
     v = max(v, −2); round to Q10; (v_a, t_a) = (v, t)
4. If v ≥ 1: FIRE(t). Otherwise PREDICT.
5. If a TICK is also due at t, run it now.

THRESHOLD(t*, ver)
  if ver is current: FIRE(t*); otherwise ignore

FIRE(t)
  v_a = 0; t_a = t; t_r = t + t_ref; f += 1; spike# += 1
  n_out  = (#live slots in view) × (#channels with emit = 1)
  ledger += c_spike + c_tw·κ + c_msg·n_out          # v1: accounting only; a spike never fails
  for each live slot d in view, if any emit:
      send ARRIVAL(mask = emit, target uid = view[d], slot = back[d]) at
          t + max(d_min, d_c[d]·(1 + 0.1·(2·H(seed, uid, spike#, d, JIT) − 1)) + δ)
      # panel only: dropped if H(seed, uid, spike#, d, DROP) < p_drop
      # contacts-off fork: never created, so no effect on v or on traces
  if κ > 0:
      world.advance(t)
      Δz = min(1, z(t) + κ) − z(t); z += Δz; t_z = t
      world.add(Δz)
  PREDICT
  # v4+: if E < cost the spike fails: reset and refractory still happen, but there is no output and no twitch

TICK(t_k), the cell's own clock, with Δ = t_k − t_prev
1. Packets: consume inbox packets with t_arr ≤ t_k in order (t_arr, sender uid): m += amount; inc[slot] = conc.
2. Ledger: += Δ·(c_live + c_sec·Σ_m sec[m]).
3. Decay traces to t_k, then build the 23 inputs:
     x = [g(16), m/(1+m)(2), f/tau_tr, r/tau_tr(2), n_view/D, flank_best/2]
   flank_best = max over empty slots e in view of the number of known-live slots among e's two cyclic neighbours (0 if no slot is empty).
4. Genes (active slots only, float64):
     g_k ← g_k + λ_k·(σ(W_k·x + b_k) − g_k)
5. Identity:
   - First re-anchor the membrane with the old θ: v_a = v(t_k), t_a = t_k, unless refractory.
   - Decode θ = decode(A·g + a0).
   - Recompute the directional weights:
       s_d     = Σ_m pol[m]·(inc[d][m] − m[m])      for each live slot d
       ŝ_d     = s_d / (max_k |s_k| + 1e-6)
       w_eff[d][c] = q8(clip(w[c]·(1 + a[c]·ŝ_d), −2, 2))
   - PREDICT with the new b and τ_m.
6. Death (apoptosis): if H(seed, uid, tick#, DIE) < p_die: APOPTOSIS(t_k) and return.
7. Chemistry:
     m = m·exp(−k_m·Δ) + sec·Δ
     for each live slot d: send PACKET(amount = m·D_m·Δ, conc = m), arriving t_k + d_min
     m −= n_view·m·D_m·Δ                                  # exactly conservative
8. Division: if H(seed, uid, tick#, DIV) < p_div, no claim is pending, and some slot in view is empty:
     p = Σ_m pol[m]·Σ_{live d} (inc[d][m] − m[m])·unit(d)          # gradient estimate built only from received packets
     score(e) = unit(e)·(p + χ·J·p) + φ·flank(e) + 1e-3·H(seed, uid, div#, e)   over empty slots e
     d* = argmax score; ledger += c_div
     send CLAIM(site of d*, genes g + asym·Q, mother uid, div#), arriving t_k + d_min
     g = clip(g − asym·Q, 0, 1); div# += 1; claim_pending = 1
   J is a 90° rotation in the lattice's cyclic slot order. flank(e) is the number of known-live slots among e's two cyclic neighbours.
9. Schedule the next TICK at t_k + P_n·(1 + 0.1·(2·H(seed, uid, tick#, CLK) − 1)); tick# += 1; t_prev = t_k.

APOPTOSIS(t). The same handler runs for KILL in v2 and for necrosis from v4.
- world.advance(t); world.remove(z_n(t)); alive = 0.
- Send CONTACT(died, uid) to every live slot in view at t + d_min.
- The inbox is discarded; its morphogen mass is lost and logged.
- Arrivals and packets still in flight are dropped when they arrive.
- A pending claim still lands. ACK or REJECT addressed to the dead uid is dropped.
- Log (t, uid, site, mother uid, cause, age, g snapshot).
- If no live cell remains and no claim is in flight: EXTINCT(t).
- From v4: apoptosis splits E evenly into energy packets to live contacts at +d_min; necrosis loses E.

CLAIM arriving at site s at time t (the site is substrate and arbitrates by arrival time)
- Site empty at t− (left limit): BIRTH. Two claims at the same instant: the lower H(mother uid, div#) wins.
- Site occupied: send REJECT to the claimant at t + d_min. The c_div already charged is lost.

BIRTH(t)
- uid' = H(mother uid, div#).
- g from the claim; v = 0; traces 0; z = 0; m = 0; view all empty.
- Frozen physics (tau mismatch, clock rate) from H(seed, coordinates, birth count at s).
- First TICK at t + U·P_n.
- World: n += 1, with z = 0.
- Send CONTACT(born) to all D slots at t + d_min (only occupied slots receive it), and ACK to the mother at t + d_min.

EXTINCT(t)
- The ledger closes at t, the life ends early (no income and no costs after), and it is flagged.

WORLD, v1 BELL-1 LUMEN (environment physics, advanced lazily at every twitch, birth and death)
- P(t) = (1/n(t))·Σ over live cells of z_i(t−). Every z decays with τ_z = 2.5, so between cell events P decays as one exponential.
- R(0) = 1.
  - Diastole, while P < 0.25: dR/dt = (1 − R)/τ_R, with τ_R = 6.
  - Systole, while P > 0.6: dR/dt = −R·(P − 0.6)/(0.4·τ_e), with τ_e = 0.5.
  - Otherwise dR/dt = 0.
- Income rate = h·n(t)·max(0, −dR/dt) during systole, with h = 1. Integrated in closed form, as world_adv does in bell3.c.
- Cells receive nothing from the world.

## Genome
NEW GENOME: kind 'life', 809 float32 slots
About 345 entries are mutable at initialization; today's genome has 250. Dims:
- G_max = 16 gene slots, 8 of them active at initialization;
- M = 2 morphogens;
- C = 2 spike channels;
- S = 0 receptor modalities in v1 (1 from v5, 3 from v7);
- P = 21 phenotype knobs;
- NIN = G_max + 7 = 23 regulatory inputs.

REGULATION (one crossover unit per gene slot)
- W [16 × 23] = 368. How each gene responds to its inputs:
  - genes (16);
  - m/(1+m) (2);
  - own-spike trace (1);
  - received-spike traces per channel (2);
  - live-contact fraction (1);
  - best empty slot's flank count / 2 (1).
  A row belongs to the regulated gene's unit. Columns that come from inactive genes stay zero and are never mutated.
- b [16]: basal expression.
- lam [16]: rate class, λ = 2^−(1 + clip(round(x + 3), 0, 6)) ∈ {1/2, …, 1/128} per own tick, i.e. about 4 to 256 time units. Replaces the global GRN rate of 0.5.
- s0 [16]: zygote (maternal) state, through a sigmoid.
- Q [16]: asymmetric partition vector at division.
- act [16]: active bit (0 or 1). Never changed by Gaussian mutation; set at initialization (the first 8 slots) and by the duplication and deletion operators.

PHENOTYPE READOUT
This replaces the 4 types, the type logits, the effector matrix E/e0 and U/u0.
- A [21 × 16] = 336: each column belongs to its gene's unit.
- a0 [21]: in the global unit.
- θ = decode(A·g + a0), with these rows:

| row | knob | decode | what it controls |
|---|---|---|---|
| 0-1 | w[c] | 1/8 steps, [−2, 2] | receiver weight per spike channel |
| 2 | b | 1/8 steps, [−2, 2] | tonic drive v_inf (tonic iff b > 1) |
| 3 | τ_m | 2^clip(round(x+2), 0, 4) ∈ {1, 2, 4, 8, 16}, ±5% frozen mismatch | membrane leak |
| 4 | t_ref | 0.5·clip(round(2x+4), 1, 8) ∈ {0.5, …, 4} | refractory period (BELL D5 grid) |
| 5-6 | emit[c] | x > 0 | channels a spike goes out on |
| 7 | δ | {0, 0.5, 1, 2} | extra conduction delay |
| 8 | κ | {0, 1/4, 1/2, 1} | contractility, i.e. the effector gain (audit item 1) |
| 9 | p_div | k = clip(round(4x), 0, 8); p = 0 if k = 0, else 2^(k−8) | division probability per own tick |
| 10 | asym | σ(x) | partition strength |
| 11 | p_die | same law as p_div | apoptosis probability per own tick (death is required) |
| 12 | φ | {0, 1/2, 1, 2} | weight of flanked (concave) slots in placement (BELL D4) |
| 13-14 | sec[m] | 0.5·σ(x) per unit | secretion |
| 15-16 | pol[m] | 2·tanh(x), in 1/8 steps | polarity sensitivity to each morphogen |
| 17 | tau_tr | {2, 4, 8, 16} | activity-trace time constant |
| 18-19 | a[c] | 1/8 steps, [−2, 2], initialized at 0 | directional receiver gain (audit item 6) |
| 20 | χ | 1/8 steps, [−2, 2], initialized at 0 | chiral term in placement (audit item 9) |

- Rows 0-8 and 18-19 are spiking, messaging and actuation. Rows 9-17 and 20 are fate, growth and chemistry.
- Every row is continuous in g, so identity is a point in gene space, not a type.

CHEMISTRY (global unit)
- Dm [2]: per-contact packet fraction per time unit, D_m = 0.9·σ(x)/(D·P_max). A tick therefore never ships out more than 90%.
- km [2]: decay rate, 0.005 + 0.3·σ(x) per time unit.

LATER-STAGE FIELDS
These are added by a neutral pad (zero weights), so a v1 winner behaves identically after padding.
- v5 and v7: receptor gain rows gs[S] and receptor-trace inputs u[S].
- v4: an energy input E/E_ref and a share knob.

REMOVED FIELDS
- The per-type cell block (w, gs, bias, leak, refr, emit for K = 4 types).
- The type logits and the effector matrix E/e0.
- U/u0.
- D and k defined per development step.
- The age input.

OPERATORS
- Crossover: uniform over 17 units (16 gene slots plus 1 global unit).
  - A gene travels with its regulatory row, rate, maternal level, Q and phenotype column, as cis-regulatory DNA does.
  - A population-wide slot registry makes the slot index an innovation ID (audit item 8).
  - It returns the unit mask for lineage logging.
- Mutation: n_mut = 2 entries inside one block (regulation or phenotype), with the block chosen with p = 0.5. Current sigmas. Active entries only.
- Duplication (audit item 8), enabled at migration step 6:
  - copy an active gene's row, b, lam, s0 and Q into a free slot;
  - split its outgoing columns (its W column and A column) half and half between the two copies.
  - This is exactly neutral: the audit measured |ΔF| < 6e-8 in 32 of 32 cases.
- Deletion clears the active bit.
- Rates: duplication 0.02 and deletion 0.01 per child, with n_mut scaling with the number of active genes.

INITIALIZATION (distribution choices, not rules; the census calibrates them)
- Means of a0: b +1.0 (about half the zygotes are tonic); τ_m +0.5; κ +0.5; emit 0; δ 0; p_div 0 (about half divide); p_die −2 (no cell dies at initialization).
- φ starts at 0; a and χ start at exactly 0.
- Homogeneous founders (BELL protocol): the W columns for n_view and flank start at exactly 0, so every cell first runs the zygote's own phenotype.

LAYOUT
- The existing Layout machinery (view, random, mutate, crossover, save, load) is reused.
- Block names are generalized, and n_units = G_max + 1.

## Timescales
FAST: event-driven and exact
- Spike delay ≈ 1:
  - lognormal σ 0.1, frozen per contact;
  - ±10% per event;
  - floor 0.5;
  - plus a genetic δ of 0-2.
- Membrane τ_m: 1-16, with ±5% per-cell mismatch.
- Refractory period: 0.5-4.
- Twitch decay: τ_z = 2.5.
- The BELL beat of R25-v1 lasts about 6.5 units, so a life holds about 150 beats.

BRIDGE BETWEEN SPIKES AND GENES
- Activity traces, with a genome-set tau_tr of 2-16: own spikes, and received spikes per channel. They are the only path from spikes to genes (calcium-like).
- n_view and flank_best come from the cell's contact view.
- Both are read only at the cell's own ticks.

SLOW: each cell's own clock (P0 = 2, ±5% per cell, ±10% per tick, random phase)
- Gene rates run from 1/2 to 1/128 per tick, i.e. about 4-256 units.
  - Fast genes act as adaptation or juvenile timers. R25-v1's listen-before-talk lasts about 10 own ticks, about 20 units.
  - Slow genes act as identity, lineage timers and size control, over about 100-250 units.
- Division:
  - at most one claim in flight per cell;
  - a round trip of at least 2·d_min;
  - rate set by p_div per tick, up to about one division per 2 units.
- Death happens at the cell's own ticks with probability p_die.
- Morphogen packets move one hop per tick (about 2 units per hop). Spikes move one hop per unit, so chemistry is several times slower: it can pattern a body but cannot carry the beat. Chemistry-off forks measure this.

WORLD AND LIFE
- Lumen refill τ_R = 6; ejection τ_e = 0.5.
- Life length T = 1024.

HOW THE LAYERS COEXIST WITHOUT A SCHEDULE
- Growth, physiology and death run concurrently from the zygote on. Nothing gates "grow now, behave later". Whether a cell divides, fires, contracts or dies is decided by its own genes at its own ticks.
- Fast to slow: traces, the contact view and received packets are read at ticks.
- Slow to fast: θ is re-decoded at every tick. The membrane is re-anchored first, so v stays continuous when identity changes.
- Identity changes are staggered by each cell's private phase and rate, so they never happen in lockstep, which could smuggle a shared clock back in.
- No separation of timescales is imposed. Each lineage chooses its λ values:
  - saturating genes or λ = 1/128 for stable physiology;
  - λ = 1/2 with activity inputs for plasticity.

COMPRESSION
- The ratio of gene to membrane timescales is at most about 250, against about 1e5 in biology. The order of the timescales is kept; their ratio is compressed for compute.
- The P0 sweep (T10) reports how sensitive results are to the slow clock.

## Identity
IDENTITY IS CONTINUOUS AND NEVER TYPED
- θ(t) = decode(A·g(t) + a0). There is no argmax, no type table and no fixed effector list.
- g changes at every one of the cell's own ticks, from local inputs only:
  - its own genes;
  - its morphogen content;
  - its own firing and the spikes it receives on each channel;
  - its live-contact fraction;
  - flank_best.
- So a cell can change identity at any time of life:
  - gradually, as g drifts;
  - abruptly, when a knob crosses a quantization boundary or the network switches attractor (transdifferentiation);
  - at division (g ± asym·Q), after which daughters diverge by position and activity;
  - when neighbours die: n_view drops, and re-raising p_div is wound repair.
- Membrane parameters change only at the cell's own ticks, after v is re-anchored, so v stays continuous.

IDENTITIES BELL-1 REWARDS (the GRN can express all of them; see the test below)
- "Alone pump" (n_view = 0): b 1.875, τ 8, t_ref 2, κ 1, no emission. The best lone cell.
- "Coupled inhibitor" (has contacts): b 1.125, τ 1, t_ref 2.5, w0 −1, emits on channel 0, δ 2, κ 1. Delayed mutual inhibition: a leaderless consensus on beat phase.
- "Juvenile listener": the same, but emission is off for its first ~10 own ticks. This is listen-before-talk.
- "Layer filler": high p_div only when flank_best ≥ 2, with φ = 2.
- "Pruner": p_die > 0 once a lineage timer is high (late-born excess cells).

R25-v1 AS A GENOME (tests/test_life_handbuilt.py, gate G9)
- Gene 0, "contact": λ 1/2, driven by n_view.
- Gene 1, "juvenile": Q = +1, so daughters start at 1 and mothers at 0; b ≪ 0; λ = 1/16, so it falls below 0.5 after about 11 own ticks.
- Gene 2, "flank gate": driven by flank_best; it switches p_div between 1/2 and 1/16.
- Optional gene 3, "lineage timer": λ 1/128, inherited; it lowers p_div, which gives uncapped size control.
- The readout columns map these genes onto the knob sets above.
- Required: F within 2 SE of the phenotype-program version, over 36 lives at an oracle cap of 91 cells.

MEASURED, NEVER FED BACK
- Clusters of the quantized fast knobs, weighted by cell-time (k-medoids, k chosen by silhouette).
- Transitions per cell lifetime and residence times.
- Maps: rim vs interior, and birth order.
- Lineage trees coloured by cluster, from the within-life birth and death log.
- Phenotype flicker rate.

KNOCKOUTS (forks of a running life; they replace "types shuffled" and "one type")
- Identity shuffle: g is permuted among living cells.
- Identity uniform: every cell gets the median g.
- Identity clamp: g is frozen from the fork on.
- Cluster kill: every cell of one cluster is removed.

## Life, tasks and fitness
ONE LIFE PER EVALUATION (v1 = BELL-1)
- At t = 0: one zygote at the origin of a sparse, unbounded fabric (hex in v1).
  - g = σ(s0) on active slots; v = 0; first tick at a random phase.
  - The lumen starts full (R = 1). There is no other world object.
- From t = 0 to T = 1024, cells divide, change identity, die and spike under the same rules.
- There are no trials, no response windows, no onsets, no stages and no freeze.
- The world is stationary and cells sense nothing from it, so time carries no signal.
- The only schedule is for measurement: counterfactual forks at T/4, T/2 and 3T/4 run on copies, and the main life is untouched.

ENERGY IN v1 IS ACCOUNTING ONLY (the user's ordering: starvation and intake come later)
- Cells hold no energy. There is no intake, no necrosis and no failed spike, and division is not gated by energy.
- Every action is charged to the organism's ledger:
  - living: c_live = 0.02 per cell per unit;
  - spike: c_spike = 0.004;
  - twitch: c_tw = 0.004·κ per spike;
  - contact event: c_msg = 0.001 per live contact in view × emitted channel;
  - division claim: c_div = 0.5, charged on every claim, including rejected ones;
  - secretion: c_sec = 0.004·sec per unit.
- Apoptosis has no cost.

FITNESS
F = [ ∫_0^T income dt − c_live·∫n dt − c_spike·#spikes − c_tw·Σκ − c_msg·#contact events − c_div·#claims − c_sec·∫Σsec dt ] / T
- No size, biomass, target or readout term.
- Income is pumped volume, i.e. task performance. Costs are accounting.
- Reference points:
  - silent zygote: −0.02;
  - lone pump: +0.033;
  - every body without messages: no better than a lone cell;
  - R25-v1: +0.93 at 91 cells.
- Every life checks the ledger: F·T = income − Σ costs, to within 1e-9.

DEATH AND THE WHOLE-BODY GUARD
- Apoptosis is driven by the genome. At each of its own ticks, a cell with p_die > 0 dies with that probability, drawn by event hash. Nothing culls cells centrally.
- The vacated site is empty again:
  - neighbours learn of it at +d_min and may claim it;
  - claims read occupancy as a left limit.
  This gives turnover, pruning and repair. Measured in BELL: an overgrown 248-cell body scores −1.25, and +0.68 once late-born cells are removed down to 63.
- Accounting at death:
  - living costs stop;
  - the c_div spent on the cell is sunk;
  - its morphogen content is lost and logged.
  From v4, apoptosis returns E to live contacts, and necrosis loses it.
- Extinction: when no live cell remains and no claim is in flight, the life ends.
  - The ledger closes at t_ext. F is still divided by T, with no income and no cost after extinction.
  - Extinct lives are flagged and counted.
  - A dead body can never beat a lone pump (+0.033). Founders must reach F ≥ 0.02, which needs actual pumping, so "die at once" (F ≈ 0) cannot become a foothold.
  - There is no last-cell protection, because it would need non-local knowledge.
- Compute guards, which cells cannot sense:
  - The life ends at N_max = 1024 live cells or 5M events.
  - The remaining time is charged as c_live·N_max·(T − t_g) with zero income, so tripping a guard is always worse than staying below it.

START SMALL
- A lone zygote pumps on its own: +0.033 (income 54e-3, costs about 21e-3 per unit).
- R25-v1 earns more at every size up to its optimum:
  - 2 cells +0.041; 3 cells +0.072 (2.2x a lone cell); 7 cells +0.148;
  - 19 cells +0.346; 37 cells +0.558; 61 cells +0.730; 91 cells +0.928;
  - then 127 cells +0.465, 169 cells −0.062, 271 cells −2.44.
- Each growth step pays only while coupling keeps up, and the best size is finite.

EVALUATION PROTOCOL (BELL v1)
- 3 lives per genome per generation.
- Life seeds are fresh every generation and shared within it. Frozen physics is keyed by coordinates, so these are true common random numbers.
- Parents are re-evaluated every generation.
- Selection: (μ + λ) = (32 + 224); 8 founders; crossover by gene unit; at least 500 generations; at least 10 seeds (the prototype's per-seed success rate was about 1/4 to 1/3).
- Founder sampling:
  - batches of 1024 random genomes, each living once for T = 512;
  - continue until some genome reaches F ≥ 0.02, capped at 8192 genomes;
  - scorers are ranked first;
  - founders are homogeneous: the W weights from n_view and flank start at 0.
- Every 10 generations, counterfactual forks for the top 8 genomes and each surviving breed's best. Each fork starts at T/4, T/2 or 3T/4 and runs to T under one condition:
  (a) contacts off: spikes are not delivered at all, with no effect on v or traces, while costs are still charged;
  (b) morphogen packets off;
  (c) apoptosis off;
  (d) division off;
  (e) identity clamp.
  Paired Δincome is logged per lineage over the generations (DOWNSTREAM S11).
- Final evaluation: the best genome and the top 8 on 64 fresh lives. Report:
  - mean ± SE, median and fraction of lives with F > 0;
  - the n_end distribution;
  - income per cell;
  - spikes and contact events per cell per unit;
  - global Kuramoto R and local phase order;
  - a trap flag: income per cell < 10e-3 with local order > 0.8;
  - the genome's own size curve under an oracle cap, which is a measurement tool only, to check that n_end sits at its own argmax;
  - bootstrap CIs and the saved seeds.

PRE-REGISTERED GATES
The full engine must reproduce these before any selection run. Prototype values are given.
- G1. Best lone cell, exhaustive over the knob grid: +0.0326 (b 1.875, τ 8, t_ref 2).
- G2. Best messages-off body ≤ lone cell at every N ≥ 2: −0.004, −0.035 and −0.137 at N = 2, 3 and 7, and zero income at N ≥ 19. A 50-generation GA with messages off stays a lone cell.
- G3. R25-v1 size curve over 36 lives as listed above, with n* = 91.
- G4. Ablation order, as [n*, F*]: R25-v1 [91, 0.928] > no listen-before-talk [61, 0.573] > naive growth [37, 0.384] > flood from the zygote [3, 0.046] > no messages [1, 0.033].
- G5. Removing frozen heterogeneity removes the size bound.
- G6. With spikes undelivered from T/2, income per cell falls from 35e-3 to 1.0e-3.
- G7. Income per cell ≤ 54e-3 everywhere.
- G8. Closed-form lumen vs Euler (dt 1e-3) within 0.1%; tests T1-T12 pass.
- G9 (new). R25-v1 encoded as a GRN genome is within 2 SE of the program version.
- G10 (new). With Q10 rounding and the full GRN layer, G1-G4 hold within 2 SE. The square8 size curve is measured before any square8 run.

KILL CRITERION (pre-registered)
If after 500 generations 8 or more of 10 seeds stay at 1-2 cells, or the winners' reliance on spikes in the spikes-off forks is about 0, stop. Fix evolvability (initialization priors, mutation, founders) before any later stage.

## Environments
Shared by every stage:
- the twitch actuator (z += κ, τ_z = 2.5);
- the organism model;
- the per-action costs;
- F = net over T.

Each stage changes ONE thing, keeps v1's world otherwise, and needs its own red team and pre-registered gates: the lone-cell floor, the best messages-off body, and a hand-built reference. The stages are ranked simplest first.

E1 / v1: BELL-1, ONE LUMEN, ONE LIFE (the first task; bounded_task v1_spec adopted as is)
- Stimulus dynamics: none.
  - The lumen R refills only while almost every cell is relaxed (P < 0.25).
  - It empties only while more than 60% of the body's possible contraction is present (P > 0.6), and pays in proportion to n.
  - Cells sense nothing from it.
- Fitness: F (pumped volume minus action costs).
- Logged:
  - income per cell, beat period, Kuramoto R, local order, trap flag;
  - n(t), births, rejects, deaths;
  - per-cell phase and each cell's z-weighted share of the ejection (the local readout);
  - spikes and contact events per cell.
- Why ongoing messaging is necessary:
  - Frozen heterogeneity (contact delays σ 0.1, τ ±5%, clocks ±5%) dephases independent oscillators. The beat must be agreed by spikes between neighbours on every beat (about 150 per life) while cells are born and die.
  - Measured: every messages-off body earns less than one cell.
  - Spikes undelivered from T/2 drop income per cell from 35e-3 to 1.0e-3.
  - Traffic is about 0.15 spikes and 0.5-0.8 contact events per cell per unit, for the whole life.
- Why growth is bounded and better algorithms help:
  - The bound comes from c_live against a graded loss of global coherence.
  - Measured ladder, as n* (F*):
    - no messages: 1 (0.033);
    - leader flood: 3 (0.046);
    - delayed mutual inhibition with naive growth: 37 (0.43);
    - plus layered growth: 91 (0.75);
    - plus listen-before-talk: 91 (0.91-0.93).
  - Each algorithmic step raises earnings, and the best size always stays finite. G5: without frozen heterogeneity the bound disappears.
  - Evolved genomes show it too: four GA winners stop at 25-49 cells, where their own capped size curves peak.
- Cheats blocked:
  - tonic saturation: no refill without relaxation, so fast tonic firing earns 0;
  - sparse-body farming: lumen volume ∝ n, so income per cell never exceeds the lone rate;
  - seizures: no refill, plus a cost per contact event;
  - one decisive spike: income accrues per beat over 1024 units;
  - a size term: there is none;
  - clocks: no stimuli, a stationary world, tests T6 and T8;
  - a leader flood: peaks at 3 cells;
  - chemistry bypass: packets move about one hop per 2 units, and chemistry-off forks measure them;
  - death-triggered pressure bumps: a replacement costs 0.5, more than a cell's best income per beat (about 0.35), and income within 2 units of deaths is logged;
  - lockstep: frozen heterogeneity, plus the lockstep control;
  - the fabric wall: the fabric is sparse and never binds (every curve is negative by 271-397 cells).
- Expected emergence:
  - leaderless pulse-coupled consensus;
  - ring-by-ring growth;
  - listen-before-talk newborns;
  - size control by a local stop rule;
  - apoptotic pruning;
  - phase-wave traps, and their avoidance.

E1.5 / v1.5: SIZE CONTROL (same world)
- Change: the oracle cap is removed from all reporting. Success requires n_end within ±15% of the genome's own capped argmax.
- Why: the prototype's inherited timer reaches only 55% of the capped optimum (0.52 vs 0.905, N ± 40). A morphogen- or activity-based stop rule is the next algorithm to find; "stop when arrival spread widens" would be message-driven size sensing.
- Fitness is unchanged.

E2 / v2: TURNOVER AND WOUNDS
- Change:
  - exogenous Poisson cell loss at 1/500 per cell per unit, delivered as hash-keyed KILL events from the world;
  - occasional wounds: every cell within radius 2 of a random live cell dies.
  Cells sense losses only through CONTACT(died).
- Rewards:
  - listen-before-talk;
  - healing of phase defects;
  - size homeostasis (re-raising p_div when n_view drops);
  - apoptosis of cells that fail to entrain.
- Gate: R25-v1 loses less than 30% at the base rate, and messages-off stays at or below a lone cell.

E3 / v3: DRIFTING HETEROGENEITY
- Change:
  - each τ mismatch and each frozen d_c follows a slow random walk (time constant about 200 units, same stationary spread);
  - τ_R drifts in [4, 12], unsensed;
  - per-life world statistics, starting narrow and then widening (audit item 10).
- Rewards gene-level calibration from arrival traces (adaptive drive or δ).
- Measured: τ_R = 12 cuts the v1 reference to F 0.10, and 10% mismatch moves n* to 37.

E4 / v4: ENERGY ON (starvation enters here, per the user's ordering)
- Change:
  - each cell has its own energy E;
  - pump income flows into the body as a smooth trickle, shared by genome-set energy packets. It never arrives as timed events into a GRN input, which would leak the beat;
  - necrosis at E ≤ 0;
  - spikes fail when they cannot be paid;
  - division is gated by energy;
  - apoptosis recycles E to contacts.
  The GRN gains an E/E_ref input and a share knob through a neutral pad.
- Rewards: starvation as a pruning signal, growth paid for by income, division of labour.
- Gate: the ledger closes, and the v1 reference ordering still holds.

E5 / v5: PUMP + THREAT (the first adversarial stage; AMBUSH folded in)
- Change:
  - rare threats, cued only at upstream rim cells: Poisson cues, receptor latency d_min, priced receptors (S = 1);
  - point damage, read as a left limit.
  The lumen must switch from beating to sustained closure before the strike, then resume the beat.
- Rewards: body-wide mode broadcast on the same spike medium without destroying the synchrony consensus. Event messaging is mixed with continuous rhythm.
- From this stage:
  - the default lattice becomes square8, once its gates are measured (audit item 7);
  - Track B probes start, as the measurement bridge to RESULTS.md: experiment's certified touch and mode streams, antithetic twins and a permutation null.

E6 / v6: LOCATION-DEPENDENT WALL (untested)
- Change: only rim cells (fewer than D contacts) form the wall, so P = mean z over rim cells. Interior cells pay c_live but cannot pump, so they must earn as κ = 0 relays.
- Tests whether location-dependent nerve and muscle roles emerge.
- Measure first: it may simply make annuli or small bodies optimal.

E7 / v7: CRAWL, then POND, then SEASONS (closed-loop sensing)
- CRAWL:
  - food patches and odour as Poisson molecule events at each site; receptors S = 3;
  - the ordered-twitch crawl law, under which independent firing gives exactly zero drift;
  - torque taken from the same impulses, a stored pose (x, φ), stimuli evaluated at world positions and placed relative to the live body (audit item 4).
- POND adds:
  - intermittent odour;
  - decoys on the food's own channel;
  - sensor noise (audit item 10);
  - grazers.
- SEASONS: Poisson switches between the pump and crawl regimes.
- Fitness: net energy under the v4 rules.

E8: SHARED WORLD (audit item 12, last)
- First, a genome-controlled propagule effector with steady-state (Moran-style) replacement.
- Then 2-4 genomes on one lattice.

REJECTED FOR v1
- AMBUSH: its messaging is episodic, and the best quiet-time traffic is zero. Moved to v5.
- VENT: readiness without messages ties messaging, and its winner is a one-hop reflex. Its rule that prey settle only on relaxed tissue is kept as an example of blocking cheats through physics.
- compute's startle stream without a rest window: message-free subtraction scores 0.64 at 3-7 cells.
- The eclipse orbit: fire-where-lit scores 0.84 with messages off.
- STORM and HUNT as specified: tonic twitching keeps cells permanently armed.
- The old BEAT: tonic saturation earned 3.2-4x what coupling earned.
- bio's rigid sum-of-normals thrust: it allows message-free arrest.

## Hard-coded rules (each justified)
KEPT: rules fixed by hand in v1, each with why it is necessary

Substrate
1. Lattice: hex by default in v1, with square8 and square4 variants and a cyclic slot order. One cell per site; contacts are lattice neighbours; the fabric is sparse and unbounded.
   Why: this defines "local", exclusion makes growth spatial, and there is no wall a body could sense.
2. Causality contract: every effect of one cell on another takes at least d_min = 0.5 (spikes, contact notices, claims, ACK/REJECT, packets). The world reads cells as left limits. From v2, world-to-cell effects also take at least d_min.
   Why: no action at a distance. It is exactly what makes results independent of step size and update order.
3. Spike delay = max(d_min, d_c·(1 + 0.1·(2u − 1)) + δ). d_c is lognormal (σ 0.1), frozen per directed contact; u is drawn per event.
   Why: conduction physics. The frozen spread is what bounds body size in BELL (G5), and the jitter makes ties a measure-zero event.
4. Same-cell batching, left-limit claims and world reads, hash tie-breaks.
   Why: the remaining exact ties become order-free.
5. Exact LIF: leak toward b, threshold 1, reset 0, floor −2, absolute refractory of at least 0.5 (input ignored), v as Q10 rounded at the cell's own events, and a frozen ±5% τ_m mismatch per cell.
   Why: the minimal excitable unit with timing. The floor bounds the register, the refractory period bounds rates, and mismatch is physics.
6. Two unlabeled spike channels: the sender chooses emit, the receiver weights them, with an optional directional gain from received packets.
   Why: the message substrate, with no fixed meaning or sign.
7. Twitch: z += κ (capped at 1), τ_z = 2.5; κ is genetic.
   Why: the single actuator. It is separate from emit, so muscle and nerve roles can differ (audit item 1).
8. A private metabolic clock: P0 = 2, ±5% per cell, ±10% per tick, random phase.
   Why: slow processes need an instant to happen. A private, jittered clock shares no phase.
9. GRN form g ← g + λ⊙(σ(Wx + b) − g), applied at the cell's own ticks, in float64, with genetic λ.
   Why: some regulatory chemistry must exist; only its form is fixed. It stays continuous so slow genes do not freeze.
10. GRN inputs: genes, morphogen content, activity traces (genome-set τ_tr), live-contact fraction, and flank_best.
   Why: these are the only bridges from events and neighbourhood to genes. flank_best is the one local geometric cue the layered-growth algorithm needs (BELL D4); gating on n_view alone is about 23% weaker.
11. A phenotype readout θ = decode(A·g + a0) onto 21 fixed knobs with fixed grids.
   Why: the knobs are what a cell can physically do. Quantization is hardware realism, and it closed the continuous-parameter clock cheats found on jump.
12. Fate knobs are per-tick probabilities (p_div and p_die on a log2 grid), drawn by event hash.
   Why: genes can then set rates (R25-v1 needs 1/2 vs 1/16) and graded turnover; the hash keeps the draws order-free.
13. Division: needs an empty slot in the cell's own view and no pending claim. The target is the argmax of unit(e)·(p + χJp) + φ·flank(e) + 1e-3·hash. The claim lands at +d_min and the earliest arrival wins. The daughter gets g + asym·Q and the mother g − asym·Q. Every claim costs c_div.
   Why: growth needs a placement rule, and earliest arrival is the only order-free arbitration.
14. Death: apoptosis at the cell's own ticks; the site is emptied and can be claimed; CONTACT(died) arrives at +d_min; messages in flight are dropped; extinction is terminal.
   Why: the user requires it, and it is the only rule that removes cells (pruning, turnover, repair).
15. Morphogens: secretion, first-order decay, and conservative packets sent at the cell's own ticks (+d_min) that carry both amount and concentration; polarity comes from received packets.
   Why: a slow chemical channel and positional cue, with no shared grid.
16. The contact view changes only through CONTACT notices.
   Why: cells know their neighbours only through messages.
17. Counter-based hash randomness: frozen physics keyed by coordinates, events keyed by uid and per-cell counters.
   Why: reproducibility, order independence, common random numbers, and independence from fabric size.
18. A zygote at the origin with maternal state s0.
   Why: the initial condition; start small.

Accounting, world and selection (outside the organism)
19. Per-action costs: c_live 0.02, c_spike 0.004, c_tw 0.004·κ, c_msg 0.001 per contact event, c_div 0.5 per claim, c_sec 0.004·sec. No energy inside cells in v1.
   Why: the user's "different costs for different actions". c_live against frozen heterogeneity is what sets the size bound.
20. BELL-1 lumen law: th 0.6, th_lo 0.25, τ_R 6, τ_e 0.5, h 1, P = mean z over live cells.
   Why: this is the task, and the effect of each constant has been measured.
21. F = net over T; extinction is terminal; guard trips are charged.
   Why: measurable, with partial credit, no size term, and guards that cannot be gamed.
22. T = 1024, 3 lives per evaluation, (μ+λ) with crossover outside the world.
   Why: the horizon does not limit size (n* is the same at T = 512, 1024 and 2048), and 3 lives control noise.

Simulator only (invisible to cells, tested)
- heap vs window scheduler;
- the N_max and event guards;
- float64 vs the integer twin;
- the oracle cap, used for measurement only.

Initialization choices (not rules)
- means of a0: b +1, κ +0.5, p_die −2, a = χ = 0;
- homogeneous founders.

REMOVED FROM THE CURRENT CODE
- The global synchronous tick, every cell updating every tick, and one hop per tick.
- The 24-step growth phase in the dark, the frozen body, and the separate trial phase.
- The 4 discrete types chosen by argmax of type logits, and the per-type rule tables (w, gs, bias, leak, refr, emit).
- The fixed effector list (divide, asym, secrete×2, type logits×4) and the U/u0 direction field.
- The age input, min_cycle, synchronous division arbitration by logit with a lowest-index tie-break, and the tie-break seed fixed per run.
- The global GRN rate 0.5, the fixed secretion constant 0.5, and diffusion over empty fabric with absorbing edges and Euler substeps.
- The fixed 271-site fabric, now sparse with no wall a body could sense.
- Fixed stimulus channel meanings delivered every tick. v1 has no stimuli, and later receptors deliver Poisson events.
- Trials, rest and response windows, onsets, balanced directions, min_spikes, and the pooled lateral readout as fitness. These survive only in the Track B probes from v5.
- External per-tissue energy charges, replaced by a per-action ledger and, from v4, per-cell energy.
- The ladder with in-run rung switches and immigrants, replaced by separate staged runs.
- The 10-bit gene rounding of the previous synthesis.

EXPRESSIVITY AUDIT: DISPOSITION OF EACH TOP BLOCKER (audit_ranked.json)
1. Every spike counts as output. ADOPTED in v1: the κ knob is the effector gain, and only twitches reach the world.
2. The answer is a direction read from a pre-recorded stimulus.
   - ADOPTED in v1, in part: the world is an online process advanced lazily at events, with no frames; fitness is task volume minus costs; the pump law is coincidence-based.
   - ROADMAP: energy-gated spikes (v4), active sensing and closed loop (v5, v7), and a world that reacts to secretions (v7 and later).
3. Fixed response windows cap serial depth. ADOPTED in v1: there are no windows, and latency is priced through the beat.
4. The body cannot turn, and stimuli are tied to the fabric centre. ROADMAP v7, because v1 has no motion and no stimuli: torque from impulses, a stored pose, and stimuli placed relative to the body.
5. The fabric wall sets size. ADOPTED in v1: no baseline income; c_live > 0 bounds size locally (measured n* = 91); a sparse, unbounded fabric; physics tables keyed by coordinates; a charged N_max guard.
6. Input is pooled and isotropic. ADOPTED in v1, dormant: directional gain rows a[c] (initialized at 0), concentrations carried in packets, and per-slot weights. Test: a = 0 is bitwise isotropic.
7. Hex crossings are fragile under jitter. PARTLY ADOPTED.
   - The kernel is lattice-generic (back and cyc tables, sums over D), and square8 is a v1 pilot arm.
   - The default stays hex in v1, because every BELL gate (including n* = 91) was measured on hex and synchrony needs no crossings.
   - The default switches to square8 at v5, once its gates are re-measured.
8. The genome has a fixed size. ADOPTED: 16 slots with active bits from day one. Duplication and deletion are enabled at migration step 6, after continuous identity is verified, as the audit advises.
9. Handedness cannot be inherited. ADOPTED in v1, dormant: a chiral placement term χ (initialized at 0), plus a mirror test.
10. The worlds are too clean. ROADMAP: v3 (drifting heterogeneity, per-life world statistics) and v7 (decoys, sensor noise). v1 must first reproduce its calibrated gates.
11. Selection cannot see robustness. ADOPTED in part: fresh seeds every generation, jitter and frozen mismatch on by default, and an envelope-on pilot arm. The background death hazard comes in v2.
12. No shared world and no in-world reproduction. ROADMAP E8: it needs energy (v4) and stable single-body results first.

Residuals from the audit's already-covered items, adopted:
- contacts-off also drops the trace updates;
- the jitter hash uses each cell's own spike counter;
- every measurement and counterfactual fork runs inside one continuous life.

## Cheats and controls
LOOPHOLES OPENED BY ONE CONTINUOUS LIFE, AND HOW EACH IS BLOCKED OR MEASURED
1. Lockstep hops (bio's δ = 0 tie bug). Jitter now covers the whole base delay, contact mismatch is frozen, and test T4 runs in CI.
2. Tie-order dependence. Blocked by same-cell batches, left-limit claims and world reads, and hash tie-breaks. T1-T3, T5 and T11 are bitwise.
3. Biomass arbitrage (bio's +0.5 per division). There is no biomass or size term, and every claim costs c_div.
4. Tonic saturation (the old BEAT cheat). The lumen refills only in diastole, so fast tonic firing earns 0.
5. Sparse-body farming. Lumen volume ∝ n, and income per cell never exceeds the lone rate (G7).
6. Seizures and flooding. Blocked by: no refill without relaxation; c_msg per contact event; refractory ≥ 0.5; and a charged event guard.
7. Hidden clocks. Blocked by: no age input, no world stimulus, a stationary world, and private jittered clocks. Tested by T6 (time translation) and T8 (phase uniformity). Gene timers that count a cell's own ticks are legitimate internal timers (listen-before-talk, lineage size control), not leaks, because the world carries no time-locked signal.
8. Death exploits:
   - Dying relaxed cells could bump the pressure. A replacement costs c_div = 0.5, more than a cell's best income per beat (about 0.35). Income within 2 units of deaths is logged, and apoptosis-off forks measure the effect.
   - A body could cut its losses by going extinct. This is allowed, but it never beats a lone pump; the founder bar F ≥ 0.02 excludes it as a foothold; the extinction rate is logged.
   - Claims racing into a dying site follow the left-limit rule (T11).
9. Guard gaming (overgrowing to end a life early). The remaining time is charged as N_max cells with zero income.
10. The fabric wall as a size cue. The fabric is sparse and unbounded, frozen physics is keyed by coordinates, and T12 checks it.
11. Chemistry bypass. Morphogen packets are legitimate local signalling but slow (about 2 units per hop). Chemistry-off forks are reported separately, and claims about spike messaging use contacts-off forks only.
12. A leaky messages-off control (audit residual). "Contacts off" now drops arrivals before any effect on v or on traces. Morphogen packets and occupancy notices get their own forks.
13. A hidden compass. Slot directions enter only through dot products with vectors built from received packets (rotation equivariance, T7). Handedness enters only through χ, checked by a mirror test with χ = 0.
14. Overfitting a developmental seed. Life seeds are fresh every generation (shared within it), and the robustness panel adds 8 other seeds.
15. Winner's curse. The GA's reported best was about twice the re-measured value in the prototype, so every claim uses 36-64 fresh lives.
16. Phenotype flicker (a gene near a quantization boundary flips a knob at every tick). Logged; hysteresis is added only if it measurably hurts.

CONTROLS (same harness, same budget; 3 seeds for pilots, 10 for claims)
The full model is compared with:
- messages off from birth, as an evolution condition (expected: it stays a lone cell);
- freeze-after-growth: at T/4, g, θ, division and death freeze. This measures what ongoing development buys;
- a two-stage replica: income is not counted until t = 64, then the body freezes. This is the old pipeline inside the new engine;
- apoptosis off: measures what death buys;
- genes blind: no traces, n_view or flank reach the GRN;
- phenotype fixed at birth;
- chemistry off;
- a lockstep world: every d_c = 1, no jitter, no mismatch, clocks in phase;
- a fixed one-phenotype disk: only a0 evolves, sized by the oracle;
- random search at an equal budget;
- mutation only vs crossover;
- 1 founder vs 8;
- gene duplication on vs off (from migration step 6);
- hex vs square8;
- noise envelope on vs off;
- a seeded control: the population starts from the R25-v1 genome. This tests whether the landscape around the hand design is climbable; it is never the main result;
- a neutral shadow run with random selection, for activity statistics (Bedau).

REFERENCES (measured in the full engine)
- the hand-built ladder L0-L4 and R25-v1, in both program and genome form;
- the exhaustive best lone cell;
- the best messages-off body;
- the silent zygote.

COUNTERFACTUAL CLONES
Every 10 generations, as described in life_and_tasks.

ROBUSTNESS PANEL (results.jsonl columns for every final organism; DOWNSTREAM item 2)
- integer twin, and Q6 v;
- membrane noise: Poisson kicks of ±1/8 at 0.05 and 0.15 per unit;
- mismatch ×2 and ×3 on τ and d_c;
- per-event jitter ±30%;
- clock mismatch 20%;
- 10% of contact events dropped (hash-keyed, so the result is window-invariant);
- 5% and 10% of cells killed at T/2 (repair is possible);
- one stuck-firing cell;
- 8 other life seeds (min and median);
- lattice swap;
- P0 = 1 and P0 = 4;
- held-out physics: th 0.5 and 0.7, τ_R 4 and 12, τ_e 1.

LOCAL READOUTS, logged beside the global income
- per-cell z-weighted share of the ejection;
- per-cell phase lag;
- local order;
- the first k spikes of each beat.

LINEAGE
- Per generation: parent indices, crossover masks, the slot registry, breed IDs, and mean pairwise genome distance.
- Within each life: every birth and death (t, coordinates, uid, mother uid, cause), hstrat-compatible.
- The final population is saved.

STATIC COST
- state bits per site;
- fan-in;
- contact events per beat.

## Compute
PRODUCTION: one discrete-event life per thread task
- State per life:
  - structure-of-arrays over at most N_max = 1024 cells. Each cell has about 120 numbers: membrane anchor, traces, g[16], m[2], inc[D][2], θ[21], w_eff[D][2], view[D] and counters. About 1 MB per life;
  - a sparse-fabric hash map from axial coordinates to cell index (4096 open-addressing slots);
  - a binary heap of about 1-10k events, 32 bytes each;
  - per-cell packet inboxes, so packets create no heap events.
- Batch: 256 genomes × 3 lives = 768 lives per generation, with an OpenMP dynamic schedule, largest expected cost first (from the parent's event count).
- Input: decoded genome tables, float32 [256, 809], packed into per-genome arrays, plus the per-generation life seeds.
- Output: [768, about 24] ledger and statistics columns. Logs (raster, births and deaths, per-cell phase) are kept for top genomes only.

MEASURED THIS SESSION (load average 2, 1-2 threads)
Scripts: /tmp/claude-1000/-home-jgon-project-ml-cell-dev/aefb0c66-3af5-49c4-936c-154d6434706c/scratchpad/one_life/final_synth/timing.py and tick_bench.c.
- The BELL prototype engine task_bell/bell3.c, with R25-v1 under an oracle cap and T = 1024. It covers the fast layer, the lumen, local claims and contact notices, but has no GRN:

| cells | time per life (1 thread) | events per life |
|---|---|---|
| 37 | 4.6-4.9 ms | 69k |
| 91 | 12-13 ms | 174k |
| 169 | 25 ms | 320k |

  That is 67-79 ns per event, about 1.85 events per cell per unit, and 0.14-0.18 µs per cell per unit.
- GRN tick micro-benchmark (12 active genes, 21 inputs, 24 readout rows, quantization, re-anchor and crossing prediction): 0.21 µs per tick, i.e. 0.105 µs per cell per unit at P0 = 2.
- The prototype GA (task_bell/ga.py) ran 500 generations × 288 lives in 356 s on 3 threads.
- Earlier, compute's full evlife.c measured about 1.5 µs per cell per unit under load average 20-70. These new numbers are 3-5x lower and were taken unloaded.

ESTIMATE FOR THE FULL v1 MODEL
- Per cell per unit, unloaded: about 0.17 µs (spikes + world) + 0.11 µs (ticks) + 0.03-0.05 µs (packets, contact notices, claims) ≈ 0.3 µs. Plan for 0.6 µs under load.
- Per life (T = 1024):

| mean body | time per life |
|---|---|
| 10 cells | 3 ms |
| 40 cells | 12 ms |
| 90 cells | 28 ms |

- Per generation (768 lives) on 8 threads:
  - early, with bodies of 5 cells or fewer: about 0.2 s;
  - late, with mean bodies of 40-90 cells: 1.2-3 s.
- 500 generations: about 8-25 min per seed on 8 threads.
- 10 seeds, run as 3 jobs × 3 threads: about 2-4 h, i.e. overnight with controls.
- Founder sampling: about 1 s per batch of 1024 tiny-body lives (T = 512).
- Counterfactual forks every 10 generations (about 16 genomes × 3 fork times × 5 conditions): under 1% extra.
- Final evaluation plus the robustness panel (about 3k lives): about a minute.
- Tests: the window scheduler and the Python reference run only in CI, on short lives (seconds to minutes).

SPEED LEVERS, IF NEEDED
- a 4-ary heap, or a calendar queue over the delay range [0.5, 3.5];
- cached decay factors per cell;
- P0 = 4: this is a model change, so T10 reports its effect;
- float32 membranes in production, with float64 kept in tests;
- skipping inactive gene slots.

## Code plan
REUSE
- src/lattice.py: keep the neighbour offsets and add:
  - cyc: the slot order by angle, needed for flank and χ (_SQUARE8 is not in cyclic order today);
  - back[D]: the opposite slot, found by lookup (bio's (d + D/2) % D is wrong on square8);
  - unit vectors per slot;
  - rotate and mirror helpers for T7;
  - offsets(kind), exported for the kernel's sparse fabric.
  The dense builders stay for the legacy pipeline.
- src/genome.py: keep the Field/Layout machinery (view, random, mutate, crossover, save, load) and add:
  - Dims kind "life" (genes_max 16, genes_init 8, morph 2, channels 2, stim 0, pheno 21) with its field list;
  - an active-gene mask that mutate respects;
  - crossover returning its unit masks;
  - duplicate() and delete();
  - pad(), which adds later-stage fields neutrally.
  The old layout stays as kind "types".
- src/evolve.py:
  - setup() picks the evaluator by cfg.mode ∈ {trials, life};
  - sample_founders (min_founder_score 0.02), fill and the (μ+λ) loop stay unchanged;
  - LifeEvaluator returns the same Eval fields: fitness, score = income rate, energy = cost rate, n_cells, spikes, divisions, trial_scores = [B, L];
  - add lineage.jsonl, the slot registry, and saving the final population.
- src/run.py, src/common.py, scripts/sweep.py and scripts/aggregate.py: mode-aware result rows.
- Legacy: develop.py, cells.py and tasks/ stay as mode: trials, for comparisons and the two-stage reference.
- Scratch prototypes to port:
  - task_bell/bell3.c: lumen world_adv, local claims, flank placement, juvenile handling, CONTACT timing, heap, splitmix hash;
  - task_bell/b3.py and cv.py: harness, fitness, size curves with the oracle cap;
  - task_bell/ga.py: the prototype GA, as a comparison;
  - clockless_feas/evlife.c: GRN tick, OpenMP batching, version counters, same-time summation;
  - async_bio/async_core.py and validity_notick/ctlif.py: window and heap references.

NEW FILES
- src/life/__init__.py
- src/life/spec.py: constants, knob grids and decode (a Python mirror of the kernel), the cost table, world presets (bell_v1, v1.5, v2, v3), and packing of genomes into kernel arrays.
- src/life/kernel.c (about 1200 lines):
  - sparse fabric;
  - heap and window schedulers;
  - handlers: BATCH, THRESHOLD, FIRE, TICK, CLAIM, BIRTH, CONTACT, APOPTOSIS, EXTINCT, and KILL for v2;
  - packet inboxes;
  - the BELL lumen accountant;
  - the ledger and the birth/death log;
  - raster and phase buffers;
  - fork();
  - flags: contacts_off, chem_off, apoptosis_off, division_off, freeze_at, genes_blind, identity_clamp, lockstep, noise, drop_p, kill_frac, stuck_cell, program_mode, oracle_cap, integer_twin, tie_key_seed, order_seed;
  - the compute guards.
- src/life/build.py: compiles with gcc -O3 -fopenmp -ffp-contract=off (no fast-math), caches by source hash, and declares the ctypes signatures. No new Python dependency.
- src/life/reference.py: a pure-Python heapq specification of the same model, for tiny bodies.
- src/life/worlds.py: world presets and per-generation life seeds; later, the KILL and wound streams.
- src/life/evaluate.py: LifeEvaluator.
- src/life/clones.py: counterfactual and knockout forks.
- src/life/panel.py: the robustness panel.
- src/life/handbuilt.py: phenotype-program organisms (L0-L4, R25-v1, B), and R25-v1 as a GRN genome.
- src/life/analysis.py: size curves with the oracle cap, Kuramoto and local order, the trap flag, identity clustering, lineage trees.
- Configs: configs/life.yaml (extends base.yaml; sections mode, life, costs_life, world, envelope, clones, gates), plus life_bell.yaml, life_bell_v2.yaml, life_bell_v3.yaml and life_smoke.yaml.
- Scripts:
  - scripts/life_gates.py: runs G1-G10 and writes gates.json;
  - scripts/life_census.py;
  - scripts/life_sizecurve.py;
  - scripts/life_replay.py: GIFs of the body with spikes, twitches, identity clusters and deaths;
  - scripts/life_lineage.py;
  - scripts/life_panel.py.

TESTS (tests/test_life_*.py; slow ones marked)
- test_life_time.py: T1-T12.
- test_life_cells.py:
  - tonic period = τ_m·ln(b/(b − 1)) + t_ref, to 1e-12;
  - relay arrival times equal the summed delays;
  - input during refractory is lost, but traces still count it;
  - same-time excitatory and inhibitory arrivals give the same result in either order;
  - Q10 rounding happens only at the cell's own events;
  - a = 0 gives isotropic weights, bitwise.
- test_life_growth_death.py:
  - the earliest claim wins, and the loser is still charged;
  - a newborn's view fills from replies at +2·d_min;
  - an arrival at a dead or re-occupied site is dropped by uid;
  - apoptosis empties the site, and a neighbour can refill it;
  - a claim racing a death follows the left-limit rule;
  - extinction ends the life and closes the ledger;
  - a guard trip is charged;
  - no division without an empty slot in view;
  - χ = 0 gives mirror-symmetric bodies.
- test_life_world_bell.py:
  - closed form vs Euler within 0.1%;
  - fast tonic firing earns 0;
  - a lone cell scores F ≈ +0.033;
  - income per cell ≤ the lone-cell rate.
- test_life_ledger.py:
  - F·T = income − Σcosts;
  - morphogen mass is conserved;
  - packets are consumed in arrival-time order.
- test_life_genome.py:
  - crossover keeps units whole;
  - the active mask is honoured;
  - duplication is exactly neutral, and deletion works;
  - pad() is neutral;
  - save/load round-trips;
  - decode ranges are correct.
- test_life_clones.py:
  - contacts_off delivers nothing (no effect on v or traces) but still charges c_msg;
  - a fork with no change continues bitwise.
- test_life_handbuilt.py (slow): G9.
- test_life_gates.py (slow): G1-G8 and G10 against gates.json.
- test_lattice.py: back and cyc tables on hex, square4 and square8.

MIGRATION STEPS (each gated)
1. Kernel fast layer + lumen + local claims in program mode + window scheduler + Python reference. Reproduce bell3 (G1, G3 at 3 sizes, G8). Pass T1-T5.
2. Slow layer (GRN, readout, packets, contacts, apoptosis, extinction, guards) and the ledger. Pass T1-T12, the death tests and G9.
3. Gates G1-G10 on hex with Q10, then the square8 size curve.
4. LifeEvaluator in evolve. Random census (sizes, extinction, lone pumps), founder sampling, lineage and clones.
5. Pilot, 500 generations: 10 seeds of the full model, plus 3 seeds of each control (messages off, freeze-after-growth, apoptosis off, genes blind, square8, envelope on).
6. Turn on duplication and deletion (audit item 8), with a 3-seed A/B comparison.
7. v1.5 analysis, then v2, v3, v4, v5 and so on, each with its own red team and gates.

## Risks
FROM THE BOUNDED-TASK RED TEAM (kept as is)
1. Evolvability is the main risk.
   - From-zygote GA success is about 1 in 4 per seed: 3/14 seeds on the design grid, 2/4 on the fine grid.
   - The other seeds stick at 1-2-cell pump pairs (F ≈ 0.05) or at about 10-cell slow-oscillator bodies (F ≈ 0.1).
   - The winners reach 28-56 cells at a re-measured F of about 0.35, a third of the hand-built 0.93. Evolution has not yet found layered growth or real listen-before-talk.
   - Mitigations: 8 founders plus crossover, at least 10 seeds, more generations, homogeneous founders.
   - The full GRN may be harder or easier to search than the prototype's reduced program. G9 at least shows the target is expressible.
2. The prototype is not the design.
   - It has no GRN, no morphogens and no Q10 rounding.
   - Its alone, contact and juvenile phenotypes are switched directly, not through gene dynamics.
   - The flank rule (D4) and the t_ref grid (D5) must be re-measured (G10).
   - Morphogens can carry phase only slowly. Report chemistry-off forks.
3. Size control.
   - The interior optimum is shown only with an oracle cap.
   - The only local controller tested, an inherited timer, gives N ± 40 and loses about 45% of F.
4. Hand-set constants.
   - The bound is soft physics: the frozen contact-delay spread (σ 0.1) and the 5% tau mismatch, against c_live = 0.02. With both spreads at 0, growth is unbounded.
   - Keep them as fixed physics, and never add per-contact delay plasticity, which could remove the bound.
   - n* moves between 37 and 169 with th, τ_e, the noise levels and τ_R. Always report n* next to the fabric size.
5. Variance. Lives are bimodal at 127 cells and above (SE 0.15-0.35). Use 36-64 lives per claim and report the median and the fraction of lives with F > 0.
6. Location. It matters only through growth geometry and local identity; no position-specific role helped (the rim test was negative). Make no claims of emergent positional roles before v6.
7. Slow convergers. B-like phenotypes are better in the late window (n* 127-217) but lose on whole-life F at T = 1024. T is a choice, not physics.
8. Flat top. F is flat between 61 and 127 cells, so n* is resolved only to about ±30 cells.

DESIGN-LEVEL
9. Death adds dynamics. Random apoptosis could cause extinction spirals or seed phase-wave traps. Countered by the apoptosis-off control, extinction logging, and p_die starting at 0 in every founder.
10. Dormant expressivity rows (a, χ and the extra gene slots) enlarge the search space before they are useful. Initialization at 0 and active-only mutation keep them neutral; the duplication A/B measures what they cost.
11. Keeping hex as the v1 default departs from the audit's square8 recommendation. It is justified because the BELL gates were measured on hex and synchrony needs no wire crossings, but routing will need square8 from v5. The square8 arm in the pilot shows whether BELL itself benefits.
12. v1 has no closed-loop sensing and no locomotion. Active-sensing and steering algorithms (audit items 2 and 4) are not selected until v5-v7.
13. In later stages chemistry may carry the signalling. Claims about spikes and about chemistry are kept separate.
14. Engineering. A C kernel is new to this repo: segfaults and silent model bugs are possible. Mitigated by the Python specification, the same-kernel window scheduler and bitwise CI. Cross-machine exactness needs the integer twin.
15. Compute. Overgrown, very active bodies (170 cells or more) cost about 25 ms per life. The guard and the costs keep them rare.
16. Comparability. F is not comparable with RESULTS.md. Track B probes start only at v5, when receptors exist. Until then, comparisons stay inside the new engine (two-stage replica, freeze-after-growth).
17. Open-endedness. Plateaus are likely; make no claims without novelty-plus-learnability evidence.
18. Fidelity limits.
    - Timescales are compressed (gene/membrane ratio at most about 250).
    - Synapses are current-based, with a reversal floor.
    - The lumen is world physics, not a circuit, so hardware transfer covers the cells, not the world.

## Open questions for the user
1. Is it OK to add a small C program to the repo as the simulator? It would be compiled by the gcc already on the laptop and loaded from Python, with no new packages. Pure torch is about 20 times slower.
2. In the first task, the score is "how much the chamber pumps, minus what each action costs". Cells hold no energy, so nothing can starve. Is that the right reading of "energy only as an accounting cost for now"?
3. Cells die when their genes say so, with some probability each time their own clock ticks, and the empty spot can then be filled by a neighbour. Is a probability fine, or do you want a hard yes/no from the genes?
4. If the whole body dies before the end of its life, I keep what it earned so far and it scores nothing after that. Is that fine, or should dying early carry a penalty?
5. The audit prefers a square lattice with diagonal contacts (8 neighbours), because signals can cross each other more reliably there. The first task was measured on hex. Should v1 start on hex and test square8 alongside it (my proposal), or switch to square8 now?
6. Evolution found the bounded body in only about 1 run in 4. Is 10 seeds × 500 generations (a few hours overnight) acceptable as the standard?
7. Do chemical signals between cells (morphogen packets) count as message passing? I propose reporting chemical and spike signalling separately, and basing any claim about spikes only on copies with spikes switched off.
8. Order of the later stages: cell turnover and wounds, then drifting physics, then energy and starvation, then threats, then crawling. Would you change that order?
9. Should the old tick-based pipeline stay as a comparison, or be retired once the new one works?
