# Body-steering design proposal (BODY-1)

Produced 2026-10-07 by the `body-design` workflow (prior-work survey, 4 measured designs, 4 red teams, synthesis, final critique). Status: PROPOSAL for discussion; nothing implemented. Prototypes and data: scratchpad `body_design/` (session-local).

**Status update (2026-10-08).** Approved by the user on 2026-10-07 (decisions 1-3 and 5 as recommended; pilot arms L_max 2 and 4; the radius gene after S1) and implemented as kernel ABI 3. The text below is kept as approved. Changes made since, each with its measured reason: `docs/LIFE_ABI.md` section 15 (entries 37-62; in particular c_miss 2 instead of 1, because a slow blind presser beat the lone cell at c_miss 1 and rule N10 did not hold; drag from the projected footprint instead of sense-plane cells, because footless tonic drifters made a 4-cell local optimum; and, after the S1 red team, drag from the filled footprint, holes counted, because hollow bodies kept their reach but shed drag) and `RESULTS.md` (BODY-1 v1). Gate GB11, read from the pre-pilot smoke runs (not yet the pilot's top 64 genomes), found evolved CATCH bodies still growing at T in 89-98% of their lives, so the per-generation life length (decision 6, removed rule N12) is back on as section 11 prescribes: T from {768, 1024, 1536}, one per generation, judged lives at 1024 (`RESULTS.md`, Pre-pilot). SPECK (section 8, S1 candidate 3) passed A1-A4 in the kernel and
runs in the pilot next to S0, with a miss priced at 10 so that R_cap / c_miss stays v1's (entry 62); its criteria are
pre-registered in `RESULTS.md` (Pre-pilot, part 10).

## Open questions for the user

1. **How should "where the cell is" move the dot?**
   - (a) Each act cell pulls along the line from the body centre to itself (your literal wording).
   - (b) Only act cells at the edge of the act layer pull, outward from the side that touches empty space.
   - Recommended: (b). On the same bodies and lives, (a) penalises every lopsided body and lets scattered islands of cells win (+2.22). Under (b), every growth step is uphill and islands do nothing (−0.20).
   - The cost of (b): full round bodies earn about 20% less at their best, interior act cells cannot pull, and timing patterns such as waves cannot move the body.

2. **Where can clicks happen?** Only at the dot's centre (the hotspot), or any act cell pressing at its own spot.
   - Recommended: centre only in v1.
   - Why: it keeps "move there, then click", and it makes a 2-cell body the first that earns (+0.045). It is the one place the rules single out beyond your two layers. No cell type is designated.

3. **Should hidden layers exist in v1?**
   - Recommended: run the v1 pilot twice, with two hidden layers above the act layer (your design) and without them. Keep them for later stages if that run climbs as well.
   - Why, measured:
     - Putting the hidden layer between sensing and acting is worse at every size, and its first step only costs.
     - Hidden layers above are free unless cells grow there, but random genomes often do. That cut working starting genomes from 11 to 8 per 8,192 and nearly erased the 2-cell body's margin.
     - Nothing in v1 rewards hidden cells yet.

4. **How do we get starting genomes?**
   - Recommended: give each cell an input saying which layer it is in, then run a census in the real kernel, with and without hidden layers. If fewer than 1 in 2,000 random genomes work, add a clearly labelled seeded-ancestor arm.
   - Why: in the prototype, about 1 in 1,000 layer-specific genomes worked (95% CI 1 in 2,400 to 1 in 520), and none that used one setting for every layer.

5. **May v1 prove only the one-hop "wire" while the computation stage is still being designed?**
   - Recommended: yes. Launch the v1 gates and pilot now. In parallel, test second-stage worlds in the prototype, starting with TWIN (two identical targets; a plain reflex stalls between them). Launch none until one passes the "no cliff" test: the v1 winner still earns, computation beats the best reflex, growth still pays, and switching off lateral messages removes the gain.
   - Why: the planned DECOY stage failed when measured. The v1 winner lost 1.5 to 3 or more per unit, and not growing became the best strategy, which is the old single-cell trap.

6. **How long is a life?**
   - Recommended: a fixed T of 1024. Draw T per generation only if a kernel test finds evolved bodies still growing at the end of life.
   - Why: in the prototype, changing T from 512 to 2048 changed F per unit time by less than 0.2 and never changed which growth setting was best. A fixed rule needs a measured reason.

7. **What about the first-step margin?**
   - Recommended: keep v1's world settings (target speed 0.1, reward 100, upkeep 0.02 per cell), and add a kernel gate that re-checks the first steps at half and double target speed and reward.
   - Why: the 2-cell body earns only because the moving target sometimes crosses the still dot. With slow targets or reward 50 it earns nothing, and at several other settings the 2 → 4-cell step goes flat.

8. **When should the radius gene come in?**
   - Recommended: after the first computation stage passes, with cap 2 and a per-length cost.
   - Why: a wider radius hurts the plain reflex, and its earlier wins were in worlds where every cell clicks at its own spot. Those results did not carry over to the cursor setup.

9. **Defaults kept from the synthesis:**
   - stacked hex layers;
   - drag growing with the square root of the footprint, which gives the same top speed at every size;
   - two-stage selection (shortlist 64, 4 extra lives);
   - SapiMouse as the main human-cursor data set, Balabit second, after checking both licences.

---

# BODY-1: a grown spiking tissue that steers a dot

Synthesis proposal, revised after a critique pass, 2026-10-07. Status: PROPOSAL for discussion. Nothing in the repo has
changed.

Inputs:
- the user's request (the body is the dot; one plane senses, one plane acts, the rest are hidden);
- four designs (`sense`, `compute`, `substrate`, `useful`) and their four red-team reports;
- the verified literature list (`research/refs_verified.json`), the one-life design and the kernel docs;
- measurements made for the synthesis (`synth/`, about 30 CPU-minutes);
- a critique pass that re-ran and extended them (`critique/`, about 70 CPU-minutes).

How claims are labelled:
- **(synth)**: measured for the synthesis, in `body_design/synth/`.
- **(crit)**: measured in the critique pass, in `body_design/critique/`.
  - Its prototype copy reproduces synth bitwise (rings 0, 1 and 3: +0.059, +1.055, +3.849).
  - It adds two things: a stack-height cap (`lmax`) and an optional decoy blob.
- **(sense)**, **(compute)**, **(substrate)**, **(useful)**: measured by that design. **-RT** means its red team.
- **estimate**: not measured.

All F values are per unit time over one life of T = 1024, given as mean ± SE over fresh lives, with n stated.
- Every number comes from the CURSOR prototype, a copy of useful-RT's.
  - It is a clockless event engine with the kernel's LIF, delay and causality rules.
  - It has no GRN, morphogens or apoptosis, and growth in it is a stand-in rule.
- So every number must be re-measured in the real kernel before anything is launched. Section 11 lists those
  re-measurements as gates.

---

## What the critique changed

1. **The planned stage S1 (DECOY) fails in this interface.** I built it and measured it (crit).
   - In every variant tried, every body bigger than ring 1 earns less than a silent lone cell.
   - The body that wins v1 loses 1.5 to 3 or more per unit in S1.
   - Lateral inhibition does beat the best tuned reflex, by +0.1 to +1.8 per unit. But the best move in the world
     becomes "do not grow", which is the single-cell trap again.
   - S1 is now an open design step with a pre-registered acceptance test (section 8), not a ready stage.
2. **The hidden planes are now measured in the v1 world (CATCH-T)**, as the user asked.
   - Hidden-between (sense, then hidden, then act) adds a first step that only costs (−0.040, below the lone cell's
     −0.020) and cuts the peak by 45%.
   - Hidden-above is free only while nothing grows there. Each silent hidden cell costs exactly c_live. A 2-cell clicker
     topped by two hidden cells earns +0.005.
   - In the founder proxy, allowing hidden planes (L_max 4) gives 8 founders per 8,192 genomes, against 11 with only the
     two control planes (L_max 2), on the same genomes.
   - Recommendation: keep hidden-above, and run L_max 4 and L_max 2 as two arms of the v1 pilot.
3. **The respawn radius does not set the body size**, contrary to the old section 3.3.
   - Farther targets make the best body *smaller*: R_max 4, 6, 9, 12 gives an optimum at ring 3, 3, 2 and 1.
   - A wider halo makes it bigger: σ = 2 moves the optimum to ring 4.
   - Section 3.3 is rewritten.
4. **Random life length is dropped as a default.**
   - In the prototype, F per unit time moves by less than 0.2 between T = 512 and 2048 for every growth setting, and
     the best setting is the same.
   - It becomes conditional on a kernel gate (GB11).
5. **The first steps are robust in their own knobs but sensitive to world settings.**
   - The 2-cell clicker beats the lone cell in 24 of 40 settings of its own knobs.
   - But with slow targets (v_t 0.05) it earns nothing.
   - With v_t 0.2, R_cap 50, c_live 0.04 or ρ_c 0.7, the 2 → 4-cell step is flat.
   - The 2 → 4-cell step is also a weak signal for selection: about 57 paired lives for a 2-SE call.
   - New gate: GB12.
6. **The founder census was re-run** with a fresh seed and twice the genomes.
   - Result: 8 genuine founders per 8,192 genomes at L_max 4 (1 in 1,024; 95% CI 1 in 2,370 to 1 in 520). Three of the
     8 are 2-cell clickers.
   - The synthesis census had actually run with 8 planes, not 4. Numbers are now given per L_max.
7. **Smaller fixes.**
   - The click hotspot is named as the one place designated beyond the two planes (rule N7).
   - The surface-normal law's two costs are stated:
     - about 20% lower peak F than the offset law on complete symmetric bodies;
     - it cannot reward waves or synchrony.
   - Compute estimates are corrected.

---

## 0. The proposal in one page

**The body is the dot.** It is a point on an unbounded 2D screen and it only translates (no rotation in v1). The tissue
rides on it in a 3D hex-prism lattice, with every cell at a fixed offset in the dot's frame.

```
   side view (the dot slides across the screen; z points out of the screen)

   z=3  .  .  h  .  .        hidden cells: message only (pilot arm L_max 4; absent in arm L_max 2)
   z=2  .  h  h  h  .
   z=1  M  M  M  M  M        ACT plane: a twitch nudges the dot (by the cell's exposed face); the centre one clicks
   z=0  S  S  S  S  S        SENSE plane: each cell gets receptor events from the screen point under itself
  ======================     the screen (the 2D world: targets, later cursor traces and text)
               ^ zygote starts here, at the body centre, z=0
```

**Sensing is local.** Only sense-plane cells (z = 0) have receptors. Each one gets Poisson receptor events at a rate
set by the world at its own screen point, delivered d_min later. The gain g_r is genetic, and so is its sign.

**Acting is local.** Only act-plane cells (z = 1) move the dot.
- A twitch pulls the dot toward the side where that cell touches empty space (its exposed face). This is the
  *surface-normal law*, a change from the literal "along the offset from the centre"; section 2.2 explains why.
- The screen registers a press only at the cursor's hotspot, the body centre. The act cell there clicks when its twitch
  crosses a threshold.

**Messaging is local.** Contacts are the 8 lattice neighbours (6 in-plane, up, down). A radius gene (cap 2, paid per
unit of wire length) waits for a later stage.

**World v1 is CATCH-T.** A wandering target with a soft halo. A click on it pays; a click elsewhere costs. Targets
reappear near the dot after a capture and on a random timer. Measured with hand-built bodies (synth; re-measured on
fresh lives, crit):
- A lone cell earns nothing (−0.020).
- One division upward gives a 2-cell "sense here, click here" reflex that earns +0.045 ± 0.004 (n 512).
- From there, every column added, in every order tried, raises mean F. No valleys, lopsided bodies included.
- F peaks at 74 cells (+3.91 ± 0.05, crit; +3.85 synth) and falls to −3.19 at 254 cells. Growth is bounded by world
  physics plus costs.
- Contacts-off drops every body to its costs. The cheats tried all lose: blind clickers, tonic drifters, disconnected
  islands, runners.

**What v1 does not do.** It does not make computation beyond the one-hop sense→act "wire" pay at its optimum.
- All four earlier prototypes and two relay tests agree. One 2-hop circuit pays, but only at 14 cells (+0.44).
- The stage meant to fix this, DECOY, failed when measured in this interface (crit, section 8).
- So v1 is the stage that grows a body and fixes the interface. Designing the first stage where computation pays is
  explicit open work, with an acceptance test.

**The main risks are founders and the first steps.**
- Founders: random genomes that grow a working sense→act body are rare. In the proxy, about 8 per 8,192
  plane-specific genomes (crit). The plan is a kernel census first, with a seeded-ancestor arm as a declared hedge
  (section 7).
- First steps: uphill in expectation, but the 2 → 4-cell step is small next to life-to-life noise (section 3.5).

---

## 1. What the synthesis measured, and why it changed the recommendation

The four designs disagreed on the nudge law, the drag law and the world. The red teams found a different serious flaw in each.

| flaw | found by | design |
|---|---|---|
| lopsided bodies are fitness valleys | sense-RT, compute-RT, useful-RT | offset law |
| disconnected "island" bodies beat compact ones (+0.90 vs +0.22) | sense-RT | rigid body plus offset law |
| a massless dot makes thrust free, so growth buys speed rather than sensing | sense-RT | massless dot |
| respawning on loss lets a 3-cell "runner" win | useful-RT | respawn rule |
| the size optimum is set by an unjustified drag exponent | useful-RT | drag law |
| a 1-to-9-cell cliff (substrate's own finding); claims wasted on the stack wall (substrate-RT) | substrate, substrate-RT | 3D stack, offset law |

The substrate red team had found that the surface-normal law gives a monotone curve in its FOLLOW-1 world. The synthesis
combined that law with the useful red team's fixes, in one world, on the same seeds (synth, `s1`–`s6`):

| body (cells) | offset law | surface-normal law |
|---|---|---|
| centre column only, the 2-cell clicker (2) | +0.045 ± 0.006 | +0.045 ± 0.006 |
| centre + 1 column (4) | +0.021 ± 0.007 | +0.091 ± 0.008 |
| centre + 2 adjacent (6) | −0.019 ± 0.007 | +0.222 ± 0.012 |
| centre + 3 adjacent (8) | −0.047 ± 0.007 | +0.310 ± 0.015 |
| centre + 4 (10) | −0.033 ± 0.009 | +0.448 ± 0.016 |
| ring 1 minus one column (12) | −0.019 ± 0.010 | +0.747 ± 0.020 |
| ring 1 (14) | +0.255 ± 0.015 | +1.045 ± 0.021 |
| ring 1 + 3 adjacent ring-2 columns (20) | −0.256 ± 0.009 | +1.368 ± 0.026 |
| **islands**: centre + 6 columns at the ring-3 corners (14) | **+2.220 ± 0.023** | −0.203 ± 0.006 |

n = 256 lives per cell, the same lives in both columns, CATCH-T world, hand-built column reflex.
- Symmetric bodies (centre + opposite pair; centre + 3 alternating) score the same under both laws, as they should.
- The surface-normal law removes the lopsided valley and closes the island cheat.
- With drag proportional to the square root of the footprint, top speed no longer depends on body size: 0.38 to 0.41
  for 14 to 122 cells (synth `s2`). Growth then buys sensing reach, not speed. That answers the free-thrust critique.
- **What it costs (synth `s1`, n 64, re-read by crit).** On complete symmetric rings the offset law earns more:
  - it peaks at +5.02 (ring 4), against +4.03 (ring 3) for the surface-normal law;
  - only rim cells can pull under the surface-normal law.
  - This is the price of having no valleys, and the reason the surface-normal optimum is one ring smaller.

The recommendation follows from these measurements.

---

## 2. The interface

### 2.1 Body
- **What it is.** The dot is a point X(t) on an unbounded 2D screen. The tissue is rigid in the dot's frame.
  - Site (a, b, z) has planar offset o = (a + b/2, b·√3/2), at lattice spacing 1 screen unit.
  - The zygote's column (0, 0, z) is the body centre.
- **No rotation in v1, by rule.** A cursor has no heading. The world ignores the torque of off-axis forces in v1, and
  a spread-out sense plane can measure spatial gradients without turning.
  - Rotation (torque from a tangential nudge share set by a chiral knob) is staged for later (S2+). It answers the
    audit's "body cannot turn" and "handedness" blockers when they matter.
- **Physics.** The dot is overdamped: V = F_total / γ, with γ = n_foot^{1/2}.
  - n_foot is the number of sense-plane cells, the footprint touching the screen.
  - X integrates in closed form between events, because every twitch decays with the same τ_z = 2.5.
  - The world, not any cell, adds up the forces and counts the footprint, as rigid-body physics does. No cell reads X,
    F_total or n_foot.

### 2.2 Moving: the surface-normal pull (resolves the "nudge law" question)
A spike of an act-plane cell with κ > 0 is the existing twitch: z_i += κ (cap 1, decay τ_z). While z_i decays, it
applies a force to the dot:

```
F_i(t) = g_n · z_i(t) · n_i,    n_i = sum of unit vectors toward the EMPTY in-plane neighbour sites of cell i
```

- n_i is read by the world from site occupancy at t− (the left limit). It is the cell's exposed face.
- A rim cell pulls the dot toward its open side. An interior cell has no open side and cannot pull.
- Picture cilia or legs that grip only where a cell meets the outside.

```
  act plane from above (hex drawn as rows)          offset law (the user's literal wording):
      .   .   .   .                                  every cell pulls along centre -> itself,
    .   M   M   .        rim M: pulls outward         interior cells too
      M   M   M          middle M: n = 0, no pull
    .   M   M   .                                    surface-normal law (recommended):
      .   .   .   .                                  only exposed faces pull, outward
```

Why this law, and not "along the offset from the centre":
1. **The sum over any body shape is exactly zero.** Every shared face is counted once in each direction. So uniform or
   tonic firing never drifts the body, and lopsided bodies are not valleys (table in section 1).
   - Under the offset law, a lopsided body has a standing pull. Every prototype that measured partial bodies under it
     found valleys (−0.15 to −0.87; useful, sense-RT, compute-RT).
2. **Islands are inert.** An isolated act cell has n = 0, which closes the "spread out for free" cheat (+2.22 under the
   offset law vs −0.20).
3. **It is still "where the cell is"**, as the user asked: the pull depends on the cell's place on the body's
   surface. For a compact disk it points roughly along the offset anyway.
4. **Physical precedent.** In Volvox and Trichoplax, only surface cells beat cilia against the medium (Drescher 2010;
   Smith 2019 in the research list).

What the law cannot do (stated so nobody is surprised later):
- The force is linear in each twitch, and every body sums to zero. So a body-wide synchronous burst, and a travelling
  wave in either direction, give zero net force.
  - The expressivity audit warned about exactly this for a "linear free-surface push".
- In v1 this is wanted: no tonic or noise drift. But it means locomotion is purely rate-coded ("which side fires
  more"), and no gait-like timing computation can pay through the motor law.
- A CRAWL-style law (a twitch moves the body toward a neighbour that contracted just before), as the audit suggested, is
  a later option if a stage needs timing-coded actuation.

Convention: **pull** (the body moves toward the acting cell's side). The sign is fixed in v1, so κ ≥ 0.
- Pull makes the one-hop column (sense cell → act cell above it) a correct taxis.
- Push also works in one hop, through tonic act cells that the sensor below inhibits (compute-RT +0.345; substrate-RT
  +1.06 to +1.14). So the sign does not force extra messages either way. Pull is simply the simpler foothold.
- A signed κ (avoidance) is a later option.

Drag γ = n_foot^{1/2}, the fixed rule with the clearest reason:
- Thrust grows with the rim (about √n cells), and drag grows with the body's linear size (Stokes-like, about √n).
- So the top speed does not depend on size (measured, above).
- Per-cell drag (exponent 1) makes big bodies slow: speed 0.57 → 0.10 from 14 to 254 cells (synth `s1`).
- Drag that does not grow with size (exponent 0) makes motors free, and loop gain grows with n (useful-RT, offset law:
  bodies run away from ring 3 on).

Gain g_n = 1. Measured alternatives at the same drag (synth `s1`, n = 64): g_n 0.5 peaks at +1.61 (74 cells) and g_n 2
peaks at +3.32 (74 cells), against +4.03 at g_n 1.

### 2.3 Sensing (resolves "how a clockless model senses" and "how the sense plane samples")
- **Candidates.** Every sense-plane cell owns a hash-keyed Poisson candidate stream at rate λ_max = λ_bg + λ_s,
  keyed by (seed, uid, own receptor counter).
- **Acceptance.** The accountant accepts a candidate at time t with probability (λ_bg + λ_s·I_m(X(t−) + o_i)) / λ_max,
  where I_m is screen layer m at the cell's own world point. An accepted candidate becomes a RECEPTOR event delivered
  at t + d_min, and adds g_r[m] to the membrane.
  - The accountant evaluates the world at the left limit, as the substrate design specified, so the window scheduler
    stays exact.
  - The sense prototype verified heap = window bitwise with receptors in a kernel copy (6 of 6 GRN lives with growth;
    sense and sense-RT).
- **Locality.** No cell reads X, the target, a clock or any total.
- **Values in v1.** One layer (target luminance), λ_s = 2, λ_bg = 0.05.
  - The background rate is sensor noise. It also gives every z = 0 cell a nonzero receptor trace, a cue the GRN can
    read.
- **Change detection is not hard-coded.** If it helps, it must emerge from a cell's own adaptation (the slow
  threshold and bias of its GRN).
- **Cost.** An accepted event costs c_rec·|g_r| with c_rec = 0.001. Estimate: about 0.01 per unit at the optimum. It
  is not in the prototype.

### 2.4 Clicking (resolves "how discrete choices come out without output cells")
- **The hotspot.** The screen registers a press only at the cursor's hotspot X, the body centre, as in a GUI. The act
  cell that sits there, (0, 0, 1), is the only cell that can press.
  - A click happens at X when that cell's twitch crosses th_click = 0.6 upward while the key is armed.
  - The key re-arms when the twitch falls below th_rel = 0.25. This is BELL's systole and diastole hysteresis.
  - A tonic tip holds the key down, giving one click. Holding the key while moving gives drag-and-drop for later
    stages.
- **This is a designated place.** It is the one place the world singles out beyond the user's two planes. Which cells
  drive the tip, and whether the centre cell exists at all, is genetic. Decision 2 asks the user to accept it.
- **Choices are places.** A choice is "move there, then click", as in a GUI.
- **The centre cell can also pull.** It is an act cell, so its twitch also pulls along its exposed face. In a full body
  that face is zero.
- **Multi-finger presses come later.** Any act cell pressing at its own site X + o_i is a later option, for worlds
  with several items under the footprint (compute's POP-1). It is not used in v1, because it makes moving optional.

### 2.5 Which questions this resolves

| design question | resolution | evidence |
|---|---|---|
| plane arrangement | sense z=0, act z=1 directly above; hidden planes above the act plane | section 4.1 (crit, CATCH-T) plus all 4 earlier prototypes |
| nudge law | surface-normal pull | section 1 table |
| drag | γ = n_foot^{1/2}; overdamped; closed form | size-neutral top speed (synth) |
| rotation | none in v1 | staged |
| what the dot does in v1 | catch a wandering target by clicking on it | section 3 |
| sense sampling | thinned Poisson at the cell's own screen point, +d_min | all four designs; heap = window bitwise (sense) |
| clicks | hotspot at the body centre, key hysteresis | 2-cell clicker earns (useful, synth, crit) |
| zygote plane | z=0 at the centre; reaches z=1 by one upward division | section 4 |

---

## 3. World v1: CATCH-T

### 3.1 Rules
- **Screen.** Unbounded. One target y(t) with halo I(x) = exp(−|x − y|²/(2σ²)), σ = 1.5.
- **Target motion.** It runs and tumbles at v_t = 0.1, turning to a uniformly random heading at Poisson rate 1/20.
- **Capture.** A click with |X − y| ≤ ρ_c = 1 is a capture, paid R_cap = 100.
- **Respawn.** After a capture, and at Poisson times of mean t_resp = 50 (a timer, not a distance test), the target
  reappears at distance U[2, 6] from the dot, at a uniformly random angle.
  - This is a world rule that cells cannot sense.
  - It replaces respawn-on-loss, which let a 3-cell runner beat everything below ring 1 (useful-RT: +0.259 vs the
    clicker +0.030).
- **Misses.** A click elsewhere costs c_miss = 1.
- **Other costs** (BELL's, unchanged): c_live 0.02 per cell per unit; c_spike 0.004; c_tw 0.004·κ; c_msg 0.001 per
  contact event; c_div 0.5 per claim; c_sec 0.004·sec; c_rec 0.001·|g_r| per receptor event.
- **Fitness.** F = (income − costs)/T over one continuous life from one zygote. There is no size term and no readout term.
- **Life length.** Fixed, T = 1024.
  - The synthesis proposed drawing T per generation from {768, 1024, 1536}, against genomes that grow forever.
  - Measured (crit `c3`, n 48 per cell), for grown column disks, gen_max 0–12:
    - F per unit time changes by less than 0.2 between T = 512 and T = 2048 at every gen_max;
    - the best gen_max is 3 for fixed T and for both random sets tried;
    - grow-forever settings (gen_max ≥ 8) hit the 400-cell guard and lose −6.0 to −7.5 at every T.
  - Growth in the prototype finishes within about 50 units, so T barely matters there.
  - In a kernel GRN that grows slowly it might (sense-RT: 52 / 139 / 479 cells at T = 512 / 1024 / 2048 in DOT-1). So
    random T is a switch that gate GB11 turns on only if evolved bodies are still growing at T.

### 3.2 Measured curves (hand-built column reflex)

Sense cells relay receptor events on channel 0. Each act cell above a sensor listens (w0 = 1, κ = 1, t_ref = 4). The
centre sensor is a coincidence detector (g_r 0.55), so noise does not trigger clicks.

**Full rings** (synth `s2`, n = 128; crit column = fresh lives, n 128–512):

| ring k | cells | F (synth) | F (crit, fresh lives) | contacts-off F | captures / life | mean speed |
|---|---|---|---|---|---|---|
| zygote alone | 1 | −0.020 ± 0.000 (n 512) | −0.020 (n 512) | — | 0 | 0 |
| 0 (2-cell clicker) | 2 | +0.059 ± 0.011 | +0.045 ± 0.004 (n 512) | −0.040 | 1.3 | 0 |
| 1 | 14 | +1.055 ± 0.032 | +1.040 ± 0.022 (n 256) | −0.288 | 14.5 | 0.39 |
| 2 | 38 | +2.969 ± 0.057 | +2.891 ± 0.050 | −0.786 | 39.3 | 0.38 |
| **3** | **74** | **+3.849 ± 0.050** | **+3.907 ± 0.051** | −1.533 | 56.2 | 0.41 |
| 4 | 122 | +3.416 ± 0.037 | +3.489 ± 0.037 | −2.529 | 62.5 | 0.41 |
| 5 | 182 | +1.098 ± 0.036 | — | −3.768 | 51.9 | 0.35 |
| 6 | 254 | −3.189 ± 0.037 | — | −5.250 | 23.7 | 0.25 |

**Column by column.**
- synth (n = 256): 2 cells +0.045 → 4 cells +0.091 → 6 cells +0.222 → 8 cells +0.310 → 10 cells +0.448 → 12 cells +0.747
  → 14 cells +1.045.
- crit, fresh lives (n = 512 up to 8 cells): +0.045 → +0.097 → +0.226 → +0.322.
- Other orders also rise: opposite pair +0.122; three alternating +0.213 (synth).
- Ring 1 plus random ring-2 columns (synth; 4 draws each, n = 128):
  - +1 column: +1.03 to +1.21;
  - +3 columns: +1.22 to +1.45;
  - +6 columns: +1.66 to +1.81;
  - ring 2 minus 3 random columns: +2.29 to +2.44 (3 draws).
  - None is below the body it grew from by more than its SE.

**Grown bodies**, with one growth knob (the lineage-generation cap gen_max), n = 64 (synth):

| gen_max | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| mean cells | 2 | 14 | 34 | 64 | 102 | 144 | 202 |
| F | +0.042 | +0.990 | +2.430 | **+3.464** | +3.211 | +1.992 | −0.716 |

### 3.3 What sets the size optimum (rewritten after crit)

The synthesis said the optimum sits where the sense footprint covers the respawn radius. Measured, that is wrong (crit
`c2`, rings 0–6, n 96 per cell, SE 0.01–0.07):

| world change | ring 0 | 1 | 2 | 3 | 4 | 5 | 6 | best ring |
|---|---|---|---|---|---|---|---|---|
| R_max 4 | +0.10 | +1.78 | +5.16 | **+6.35** | +5.34 | +2.20 | −2.93 | 3 |
| R_max 6 (v1) | +0.05 | +1.10 | +2.88 | **+3.97** | +3.34 | +1.13 | −3.25 | 3 |
| R_max 9 | +0.01 | +0.43 | **+0.95** | +0.94 | +0.46 | −0.80 | −3.66 | 2 (tie with 3) |
| R_max 12 | −0.00 | **+0.28** | +0.24 | −0.14 | −0.84 | −2.04 | −4.18 | 1 |
| σ 1.0 | +0.07 | +1.06 | +1.48 | **+2.07** | +0.74 | −2.64 | −4.85 | 3 |
| σ 2.0 | +0.02 | +0.40 | +1.25 | +3.17 | **+3.49** | +2.39 | −0.02 | 4 |

What this shows:
1. **The optimum is an economic balance, not a reach match.** A ring is worth adding while the extra captures it buys
   pay for its c_live.
   - Farther targets lower the income of every body, so the optimum *shrinks* (ring 3 → 1 as R_max goes 6 → 12).
   - A wider halo lets each sensor see farther, which makes rim cells more valuable, so the optimum *grows* (σ 2 →
     ring 4).
2. **Only the rim can pull.** In a big body, a target that appears inside the footprint is seen only by interior
   sensors, whose act cells cannot pull. Misses rise from 43 at ring 3 to 100 at ring 6 (synth).
   - This "interior blindness" is the one thing a better message-passing algorithm could fix (routing interior
     information to the rim).
3. **c_live grows linearly**: 1.48 per unit at ring 3, 5.08 at ring 6.

So bounded growth comes from world physics plus costs, with no size target. The world knobs that set body size are σ and
the income-to-cost ratio (R_cap / c_live), not R_max. For bigger bodies later, widen the halo or raise R_cap.

The user's first growth motive, more sensory area, is measured to pay up to about 74 cells. The second, more
computation, has a measurable niche (point 2), but no hand-built circuit has filled it yet (section 5).

### 3.4 Why this world and not the other v1 candidates

| candidate | first earner | early curve | main measured problem |
|---|---|---|---|
| DOT-1, progress income (sense) | 7 cells | valleys outside 3-fold symmetry | islands and free thrust (sense-RT) |
| TAG-1, stay-on-target (compute) | 7 cells | 1–4-column arcs below the lone cell | lost-forever targets; noisy (compute-RT) |
| FOLLOW-1 + surface normal (substrate-RT) | 6 cells (L-tromino) | monotone from 3 columns | 1→2 cells and 2→4 cells are cost-only steps; founders about 1 in 55,000 |
| **CATCH-T + surface normal (synth, crit)** | **2 cells** | **monotone in every order tried** | computation beyond the wire pays only at small size |

CATCH-T is the only candidate where the very first division (zygote → the cell above it) already earns. That is the
smallest sense-act reflex arc, matching the 2-cell eyespot-to-cilium circuit of the annelid larva (Jékely 2008).

### 3.5 How robust the first steps are (new, crit)

**In the clicker's own knobs** (crit `c2`, n 512 per setting).
- The grid: centre-sensor gain g_r 0.25–1.25 (8 values) × motor settings (t_ref 1, 4, 8 at κ 1; κ 0.5 and 0.25 at
  t_ref 4).
- 24 of the 40 settings beat the lone cell by more than 2 SE, and 17 are net positive by more than 2 SE.
- The best is the strictest coincidence detector: g_r 0.25 gives +0.059 ± 0.005.
- Failures:
  - κ 0.25 always fails: one twitch never reaches the click threshold 0.6.
  - g_r ≥ 0.625 with t_ref 1 fails: the tip clicks on noise.
- Varying the motor's w0 and bias at g_r 0.625: 9 of 12 settings earn.
- So the first stepping stone is a broad region, not a knife edge.

**In the world's settings** (crit `c2`, one change at a time, ×½ or ×2):

| world change | lone | 2-cell clicker | 4 | 6 | 8 | ring 1 (14) | ring 3 (74) | first steps uphill? |
|---|---|---|---|---|---|---|---|---|
| v1 settings | −0.020 | +0.051 ± 0.005 | +0.092 ± 0.006 | +0.220 | +0.327 | +1.022 | +3.875 | yes |
| v_t 0.05 (slow target) | −0.020 | **−0.019 ± 0.003** | +0.049 | +0.254 | +0.353 | +1.424 | +4.276 | clicker earns nothing |
| v_t 0.2 (fast target) | −0.020 | +0.116 ± 0.006 | **+0.114 ± 0.007** | +0.153 | +0.212 | +0.470 | +2.767 | 2 → 4 flat |
| R_cap 50 | −0.020 | **−0.007 ± 0.002** | **−0.007 ± 0.003** | +0.035 | +0.066 | +0.331 | +1.116 | first earner at 6 cells |
| c_live 0.04 | −0.040 | +0.011 ± 0.005 | **+0.012 ± 0.006** | +0.100 | +0.167 | +0.742 | +2.395 | 2 → 4 flat |
| ρ_c 0.7 | −0.020 | +0.010 ± 0.004 | +0.014 ± 0.005 | +0.064 | +0.125 | +0.523 | +2.821 | 2 → 4 nearly flat |
| t_resp 25 / 100; c_miss 0.5 / 2; R_cap 200; λ_bg 0.025 / 0.1; τ_turn 10 / 40 | | | | | | | | yes, all 9 |

n: 512 lives (bodies up to 4 cells), 256 (6–8 cells), 128 (ring 1), 96 (ring 3).
- The 2-cell clicker earns only because the wandering target sometimes crosses the still dot. Slow targets, low reward
  or high upkeep remove that.
- v1's settings sit inside the good region, but not far inside. Gate GB12 re-checks this in the kernel.

**As a signal for selection** (crit `c3`, paired: the same 256 lives for each body):

| step | ΔF ± SE (paired) | per-life SD of ΔF | paired lives for a 2-SE call |
|---|---|---|---|
| lone → 2-cell clicker | +0.077 ± 0.007 | 0.112 | 9 |
| 2 → 4 cells | +0.046 ± 0.011 | 0.172 | **57** |
| 4 → 6 | +0.127 ± 0.015 | 0.238 | 15 |
| 6 → 8 | +0.092 ± 0.017 | 0.277 | 37 |
| 8 → 10 | +0.162 ± 0.019 | 0.310 | 15 |
| 10 → 12 | +0.222 ± 0.023 | 0.363 | 11 |
| 12 → 14 (ring 1) | +0.387 ± 0.024 | 0.386 | 4 |
| ring 1 → ring 2 | +1.862 ± 0.041 | 0.659 | 1 |
| ring 2 → ring 3 | +0.959 ± 0.043 | 0.693 | 3 |
| ring 3 → ring 4 | −0.527 ± 0.035 | 0.562 | — (downhill) |

- Common random numbers help little: the paired SD is only 0–23% below the unpaired one.
- With 3 to 7 lives per genome, single-column steps between 2 and 8 cells are uphill but faint.
- Two things help:
  - Selection acts on many mutants at once, not on a single 2-SE test.
  - A mutation that lets the zygote divide sideways may grow a whole ring in one step. In the proxy, gen_max 0 → 1 jumps
    from +0.04 to +0.99. Gate GB9 measures whether the kernel GRN works the same way.

---

## 4. Substrate

- **3D from the start, but shallow.** Hex prism lattice (hex planes stacked), D = 8 contacts: 6 in-plane, up, down.
  - **Planes:** z = 0 sense, z = 1 act, then hidden planes above the act plane up to a hard cap L_max. The pilot runs
    two arms, L_max = 4 (the user's design, two hidden planes) and L_max = 2 (the two control planes only); section 4.1.
  - **Out-of-stack sites do not exist.** They are invisible to a cell's view: never EMPTY, never claimable, not
    counted in n_view.
    - This fixes the wall-reject drain substrate-RT measured: 72.5% of all claims in bounded grown bodies were rejects
      against the stack wall, at about one cell's c_live.
  - z < 0 is the screen.
- **Why hex prism and not simple cubic.**
  - Every BELL gate and every CATCH number here is on hex.
  - Simple cubic gave the best FOLLOW-1 reflex (+1.38 vs +1.08 on fcc; substrate), but a single cubic layer at
    radius 1 failed BELL synchrony (substrate).
  - Square8-prism (D = 10) is a later arm. The kernel is lattice-generic.
- **Zygote and growth.** The zygote sits at (0, 0, 0), the only place a lone cell gets world input.
  - It reaches the act plane by dividing into the empty slot above. Hidden planes are reached the same way.
  - Placement keeps the kernel's rule (argmax of polarity, chirality and flank terms plus a hash) and adds one term,
    ζ·u_z(e), with genetic ζ ∈ [−2, 2] (q8).
    - Without it, vertical slots score 0, because they have no in-plane unit vector.
    - The sense design's 6-gene hand GRN used ζ plus a "fresh" gene, so every new sensor's first division went up. It
      grew column disks from one cell in a kernel copy (74 cells, +1.49 in DOT-1; sense).
    - ζ is read out per cell by the GRN, so it can differ by plane. A genome whose act cells also divide upward
      fills the hidden planes with cells that cost upkeep and do nothing in v1 (section 4.1).
- **Plane-cue GRN inputs.** Two inputs, is_S and is_M: the cell's own plane, a local substrate contact (touching the
  screen; carrying motors).
  - Without them, a homogeneous phenotype fires its motors in lateral storms. Every homogeneous ring lost money in
    CATCH (ring 1 −0.21 to −0.35; useful-RT). In the census, no homogeneous genome founded (section 7).
  - With them, vertical receiver polarity can emerge from existing machinery: a plane-specific secretion gives a
    vertical morphogen difference, which the dormant directional gain a[c] turns into "listen downward". Estimate,
    not measured.
- **Radius gene (staged, not in v1).**
  - A per-cell sender reach r ∈ {1, 2}, hard cap 2, in-plane only. Vertical contacts, notices, claims and packets stay
    at radius 1.
  - Delay = d_c·(α + (1 − α)·len) with α = 0.5. The kernel copy is bitwise-equal to the repo kernel at r = 1
    (substrate's `kr/patch.py`).
  - Cost:
    - c_msg·len per delivered contact event (energy proportional to wire length);
    - plus a standing c_wire = 0.0005·Σ len per cell per unit, so silent cells cannot keep long wires for free.
  - Why stage it:
    - In the plain reflex, radius only hurts: Moore-26 drops +1.38 to +0.76 (substrate).
    - Radius pays where a site's right action depends on sites more than one hop away. Centre-surround clicks paid only
      at radius 2 (compute: radius 1, nothing beat silence; radius 2, +0.033 ± 0.005 over silence). Big synchronised
      BELL bodies paid too (169 cells: r = 1 −0.12 ± 0.38; r = 2 +2.81 ± 0.17; substrate, real kernel).
    - Caveat from crit: those wins were in worlds where any cell acts at its own site. The cursor-interface version of
      a centre-surround world (DECOY) failed (section 8), so radius waits for a stage that passes the acceptance test.
  - Open issue: long contacts need their own polarity. The current patch sets s_d = 0 on non-adjacent slots, so long
    contacts are isotropic (substrate-RT).
- **Penalising cell count and radius.** Cell count is penalised by c_live and c_div, radius by c_msg·len and c_wire,
  plus the hard caps. There is no size or radius target.

### 4.1 Plane arrangement and the start-small curve (new, crit `c1`, CATCH-T, same lives across arrangements)

The user asked what the hidden planes do to the start-small curve. Three arrangements, hand-built column reflex:
- **adjacent**: sense z=0, act z=1.
- **adjacent + silent hidden**: the same, with 1 or 2 silent hidden cells stacked on every column. This is what a genome
  gets if its act cells divide upward and the hidden cells do nothing.
- **between**: sense z=0, relay z=1, act z=2. Every behaviour then needs two hops.

| body | adjacent | + 1 silent hidden / column | + 2 silent hidden / column | between (relay column) |
|---|---|---|---|---|
| zygote alone | −0.020 (n 512) | — | — | −0.020 |
| first 2 cells | clicker +0.045 ± 0.004 | — | — | sense + relay **−0.040** (no act cell yet) |
| centre column | +0.045 ± 0.004 (2 cells) | +0.025 (3) | **+0.005 (4)** | +0.023 ± 0.004 (3) |
| centre + 1 column | +0.097 ± 0.006 (4) | +0.057 (6) | +0.017 (8) | +0.059 ± 0.006 (6) |
| centre + 2 adjacent | +0.226 ± 0.009 (6) | +0.166 (9) | +0.106 (12) | +0.196 ± 0.010 (9) |
| centre + 3 adjacent | +0.322 ± 0.011 (8) | +0.242 (12) | +0.162 (16) | +0.279 ± 0.011 (12) |
| ring 1 | +1.040 ± 0.022 (14) | +0.900 (21) | +0.760 (28) | +0.981 ± 0.023 (21) |
| ring 2 | +2.891 ± 0.050 (38) | +2.511 (57) | +2.131 (76) | **+2.151 ± 0.048 (57), the peak** |
| ring 3 | **+3.907 ± 0.051 (74), the peak** | +3.167 (111) | +2.427 (148) | +1.984 ± 0.044 (111) |
| ring 4 | +3.489 ± 0.037 (122) | +2.269 (183) | +1.049 (244) | +0.988 ± 0.038 (183) |

n: 512 lives (up to 4 columns), 256 (ring 1), 128 (rings 2–4). The silent-hidden columns use the same lives as
adjacent, so their SE equals adjacent's. Contacts-off drops every between-body to its costs.

What it shows:
- **Between is worse at every size.**
  - Its first two cells only cost (−0.040, below the lone cell). That is exactly the kind of step the BELL-1 lesson
    says to avoid.
  - Its peak is 45% lower (+2.15 vs +3.91), at a smaller body.
  - The relay adds upkeep, spikes, messages and latency, and in v1 it computes nothing.
- **Above is free only while nothing grows there.** Each silent hidden cell costs exactly c_live = 0.02 per unit. With
  two silent hidden cells on it, the 2-cell clicker's margin over the lone cell shrinks from +0.065 to +0.025.
- **Founders** (section 7, same 8,192 genomes): 11 genuine at L_max 2, 8 at L_max 4 or 8.
  - The 3 lost genomes grow 1, 9 and 33 hidden cells above their act cells at L_max 4, and fall from +0.03, +0.07 and
    +0.30 to +0.01, −0.13 and −0.29 (crit `c7`, 24 lives each).
  - The best founder earns +0.99 ± 0.07 at L_max 2 and +0.60 ± 0.08 at L_max 4, where it carries 18 useless hidden
    cells.
- **Recommendation.**
  - Hidden planes go above the act plane (unchanged).
  - In v1 they are an option that costs a little at the start and earns nothing yet. So the v1 pilot runs both
    L_max 4 (the user's design) and L_max 2 (control).
  - If the L_max 4 arm climbs as well, keep it for every later stage. If it climbs clearly worse, open the hidden planes
    at the first stage where depth must pay.
- **A useful property of hidden-above** (design note, not measured): interior act cells have n = 0, so they can pass
  signals up to hidden cells without moving the body. Rim act cells are the motors. A division of labour inside the
  act plane can therefore emerge without any new rule.

---

## 5. Messages, and whether computation pays

**Necessary by construction, and measured.** Sensing and acting are different cells, so every earning behaviour needs a message.
- Contacts-off from t = 0 leaves income at exactly 0 for every body (synth; useful; crit for the between arrangement).
- Every ring in the table above falls to its costs.
- In the kernel, the certificate must fork contacts_off together with chem_off and division_off, after growth.
  - Morphogen packets and claims carry state between planes, so a slow chemical reflex is possible (sense-RT, compute-RT).

**Computation beyond the wire, measured (synth):**

ΔF of each added circuit against the plain column reflex on the same lives (n = 256 per cell):

| added circuit | ring 1 (14) | ring 2 (38) | ring 3 (74, the optimum) | ring 4 (122) | ring 5 (182) |
|---|---|---|---|---|---|
| plain reflex F, for scale | +1.07 | +2.98 | +3.90 | +3.35 | +1.06 |
| centre "hold": the centre sensor inhibits the ring-1 sensors (2 hops) | **+0.440** | +0.002 | +0.002 | +0.003 | — |
| isotropic lateral relay in the sense plane, best of 30 settings | — | −0.083 | +0.002 | −0.001 | **+0.284** |
| polarised outward relay (radial receiver gain), best of 48 | — | −1.614 | −2.529 | −3.004 | −2.495 |
| isotropic lateral inhibition, best of 32 settings (crit `c4`, n 256 paired) | −0.125 ± 0.030 | −0.355 ± 0.041 | −0.902 ± 0.041 | −0.894 ± 0.028 | — |

- A lateral-off fork returns every changed body to the plain reflex.
- The hold pays only where the cells it silences are rim cells, which is ring 1.
- The isotropic relay pays only beyond the optimum (ring 5), not at it.
- The polarised relay floods every rim with relayed background noise. That shows a *naive* router fails, not that
  routing cannot pay.
- Lateral inhibition costs money in v1 at every size (crit).

This agrees with every earlier prototype:
- the reflex is "each sensor pulls toward itself" plus one forced hop;
- lateral-off changes nothing at the optimum (useful-RT: ΔF = 0 at rings 0–7);
- the two-plane column reaches 66–93% (sense-RT), or 92–102% with relay costs refunded (substrate-RT), of the forbidden
  one-plane reflex.

So, said plainly: **v1 certifies a wire, plus one small 2-hop circuit.** Depth and breadth must be made to pay by a later
world feature. compute's rule for choosing that feature still stands: *computation pays when the right action at one
site depends nonlinearly on other sites, and the rewarded class must be one a reflex is biased against*. But crit adds a
second condition, learned the hard way in section 8: *the new feature must not make the existing reflex lose money*,
or the population's best move becomes shrinking.

---

## 6. Start small: reachability by mutation

- **Step 1, zygote → 2-cell clicker.** One upward division, plus plane-specific expression:
  - the act daughter listens to the zygote's channel with κ ≥ about 0.6, so one twitch reaches the click threshold;
  - the zygote emits on that channel and has g_r > 0.
  - Coincidence detection matters, but over a broad range: g_r 0.25–0.875 works with motor t_ref ≥ 4 (section 3.5).
    With g_r ≥ 1 the clicker earns at most +0.013 (crit; −0.005 ± 0.010, useful).
  - With plane cues this is 1–3 mutations from a genome that already divides (estimate).
- **Steps 2+, adding columns.** Each new sense cell divides up once, then sideways while its lineage timer runs.
  - In the prototype this is one knob, and every intermediate step is uphill in expectation (section 3.2). The steps
    from 2 to 8 cells are faint for selection (section 3.5).
  - Caveat (useful-RT P4, re-measured by synth). If the same lineage timer also stops the upward division, the rim of
    the sense disk has no act cells, and early sizes fall into a valley:
    - gen_max 1–2: −0.08 to +0.005;
    - gen_max 3: +0.88, against +3.46 in the exempt version (synth, n = 64; prototype placement knob ψ = 1, the analogue
      of ζ).
  - The GRN must therefore let "divide up once" run separately from the in-plane timer.
    - The hand GRN of the sense design does this with a "fresh" gene plus ζ. That is evidence the GRN can express it.
    - Its mutational neighbourhood under the new law is unmeasured (gate GB9).
  - The act cells must *not* also divide upward, or the column carries useless hidden cells (section 4.1). That is a
    second conjunction the GRN must express through the plane cue.
- **Physiology.** Tuning within a size is easy: 6–11% of single mutants improved F (sense; DOT-1, offset law).
- **Ring-to-ring steps.**
  - Under the offset law they were valleys: 0 of 2,400 mutants were both bigger and better (sense).
  - Populations still left ring 1 within about 20 generations (2 of 2 seeds; sense-RT).
  - Under the surface-normal law, partial rings are uphill (section 3.2), so the ring step should stop being a valley.
    This is an estimate until a kernel mutational scan (gate GB9) confirms it.

---

## 7. Founders

The founder census proxy runs CATCH-T with the surface-normal law.
- It draws random rows per plane, with the same random law as useful-RT.
- Every genome with income in its census life is re-measured on 24 fresh lives.
- "Genuine" means fresh F > 0 and more than 2 SE above the silent zygote.

**Synthesis census** (synth `s6`, seed 1, 4,096 genomes per family). This ran with the prototype's default 8 planes,
not the 4 the proposal names.

| family | lone cell | hit the 300-cell guard | any income in the census life | genuine on 24 fresh lives |
|---|---|---|---|---|
| H: one random row for every plane | 56.6% | 9.2% | 2.9% | **0** |
| P: independent random row per plane | 56.2% | 2.8% | 3.2% | **3** (34 cells +0.730 ± 0.084; two 2-cell clickers +0.053, +0.011) |
| C: per plane, reflex-centred initial means | 56.2% | 5.3% | 3.4% | **1** (50 cells +0.579 ± 0.066) |

**Critique census** (crit, family P, fresh seed 11, 8,192 genomes; the same genomes at each stack cap):

| L_max | lone cell | hit the guard | mean cells | genuine | rate (95% CI) | 2-cell clickers among them | best founder |
|---|---|---|---|---|---|---|---|
| 2 (control planes only) | 54.9% | 0.0% | 23 | **11** | 1 in 745 (1 in 1,490 to 1 in 416) | 4 | 35 cells, +0.991 ± 0.067 |
| 4 (user's design) | 54.9% | 1.1% | 31 | **8** | 1 in 1,024 (1 in 2,370 to 1 in 520) | 3 | 53 cells, +0.597 ± 0.083 (same genome) |
| 8 | 54.9% | 3.0% | 35 | **8** | 1 in 1,024 | 3 | as L_max 4 |

Pooled at 8 planes (synth + crit), the rate is 11 in 12,288: 1 in 1,117, 95% CI 1 in 2,240 to 1 in 624.

What the census shows:
- **Homogeneous genomes never found a working body.** So the plane cue (or plane-specific expression) is needed,
  which agrees with useful-RT.
- **About 1 in 1,000 plane-specific genomes is a real founder.** BELL's founder budget is 8,192 samples per seed. That
  would give about 8 founders per seed (CI about 3.5 to 16) at L_max 4, *if* the kernel GRN behaves like this proxy.
- **Founders come in two kinds:** 2-cell clickers (+0.03 to +0.06) and column bodies of 6–91 cells (+0.07 to +0.99).
- **Hidden planes cost about a quarter of the founders**, by wasting cells on upward growth (section 4.1).
- **Reflex-centred means did not help** in the synthesis census (1 vs 3, not significant).
- **The surface-normal law did not change the rate.** The bottleneck is the sense→act wiring conjunction, not the
  body shape: the synth P founders are the same genomes useful-RT found under the offset law.

Earlier, under other laws and worlds:
- CATCH with the offset law: 0, 1 and 3 genuine per 4,096 (useful-RT).
- FOLLOW-1 with the kernel's real growth: a joint rate of about 1 in 55,000 (substrate-RT).
- DOT-1: 0 of 12,288 (sense).

Plan (each step is a gate; nothing hard-codes a role):
1. Add the plane-cue inputs and **initialisation means** centred on a reflex.
   - The means: sense cells emit ch0 with g_r +0.5; act cells w0 +0.5; b mean 0.
   - These are priors, not rules. Every entry stays mutable.
2. Run a kernel census of 8,192 GRN genomes at L_max 4 and at L_max 2, with the multi-life recheck. Report the
   genuine-founder rate and the bodies.
3. If the rate is at least 1 in 2,000 (at least 4 expected per 8,192-sample founder budget), start from census
   founders, as BELL does.
   - If it is lower, run two arms:
     - (a) unseeded, with a larger founder budget;
     - (b) a **seeded ancestor**: the smallest hand-written GRN that grows the 2-cell clicker, declared as such.
   - Report both. Arm (b) answers "does evolution climb from here"; arm (a) answers "can it start".

---

## 8. Staged environments

Each stage changes one thing. Each has:
- its own red team: blind, tonic, runner, island and one-plane cheats, plus the inert dot;
- a hand-built reference;
- a best tuned reflex R, and the best reflex with a per-cell slow state, Rg (single-cell memory without messages,
  compute);
- forks: contacts-off, lateral-off, hidden-off, radius-1;
- a pre-registered kill criterion;
- and, new after crit, the **no-cliff acceptance test** below, passed in the prototype and then in the kernel *before*
  the stage is launched.

**No-cliff acceptance test for every stage after S0** (pre-registered):
- **A1. The old champion still earns.** The previous stage's champion (the best hand-built body, and later the best
  evolved one) earns F > 0 and above the lone cell in the new world.
- **A2. Computation beats the reflex.** A hand-built circuit that uses the intended computation (lateral, hidden or
  radius-2 messages) beats the best tuned R and Rg by more than 3 SE, at a body size within one ring of the previous
  optimum.
- **A3. Growth still pays.** That circuit's F at its own optimum is above every smaller body's F and above the lone
  cell's.
- **A4. The gain is real computation.** The matching fork (lateral-off, hidden-off or radius-1) removes at least 50% of
  the gain.

### 8.1 The DECOY stage, measured: it fails A1 and A3 (crit `c4`, `c5`)

DECOY as specified:
- a second blob on the same channel;
- the target is small (σ_t 0.6) and pays; the decoy is broad (σ_d 1.6) and costs c_dec 25 when clicked;
- the decoy respawns with the target.

Results: best of a tuned grid (R: 8 settings; lateral inhibition LI: 32), confirmed on 256 fresh lives:

| ring (cells) | best tuned reflex R | best lateral inhibition LI | LI − R (paired) | LI with lateral-off |
|---|---|---|---|---|
| 0 (2) | −0.038 ± 0.007 | — | — | — |
| 1 (14) | −0.518 ± 0.015 | −0.250 ± 0.008 | +0.269 ± 0.016 | −0.737 |
| 2 (38) | −2.050 ± 0.019 | −0.804 ± 0.006 | +1.246 ± 0.019 | −2.141 |
| 3 (74) | −3.024 ± 0.021 | −1.565 ± 0.004 | +1.459 ± 0.020 | −3.528 |
| 4 (122) | −4.352 ± 0.017 | −2.534 ± 0.004 | +1.818 ± 0.016 | −4.710 |

The silent lone cell earns −0.020, so it beats every body in this table.
- Why it fails:
  - The ring-3 reflex catches 2.2 targets per life (56.7 in v1) and clicks the decoy 68 times.
  - Its income falls from 5.53 to 0.22 per unit, while its costs almost double (1.7 → 3.2 per unit), because the
    broad decoy keeps the whole sense plane firing.
  - The body parks under the broad blob.
  - LI stops the decoy clicks (about 2 per life) but also stops catching targets (0.3 per life).
- **Eight milder variants** (σ_t 1.0 or 1.5, σ_d 2.5 or 4.0, c_dec 5 or 15). These are search numbers on 64 lives,
  best of grid, so optimistic:
  - the untuned S0 champion loses at every ring (−0.09 to −2.21);
  - LI beats R in all 24 world × ring cells;
  - but ring 2 and ring 3 lose money everywhere (best LI −0.15 to −1.57);
  - the best body anywhere is ring 1 (LI −0.01 to +0.29); in one variant nothing beats the lone cell.
- **The small target alone** (σ_t 0.6, no decoy) is a poor world too: R peaks at rings 1–2 (+0.36, +0.35), and LI loses
  to R at every ring.
- **What this means.** Computation does pay *relative to the reflex*, so compute's rule holds. But the decoy turns v1's
  champion into a heavy loser, and the best body becomes the lone cell or ring 1.
  - A population moved from S0 into this world would be selected to shrink. That is the single-cell trap, recreated.
  - The POP-1 numbers that motivated DECOY (compute) came from a world where every act cell clicks at its own site.
    They did not transfer to the cursor interface.

### 8.2 Stage table (revised)

| stage | adds one thing | success (evolved, on 64 fresh lives) | non-evolved baselines |
|---|---|---|---|
| **S0 CATCH-T** (v1) | the body, sensing, nudges, clicks; growth from one cell | (1) ≥ 5 of 10 seeds reach F ≥ +2.0, the ring-2 level, within 500 generations; (2) final bodies of 30–120 cells, within ±20% of their own capped argmax; (3) a contacts+chem+division-off fork at T/2 removes ≥ 95% of second-half income; (4) beats the best runner (+0.094) by ≥ 10×. Kill: ≥ 8 of 10 seeds at ≤ 4 cells after 500 generations | hand-built ladder (section 3.2); best runner; blind clicker; lone cell; a non-local event-centroid controller (upper bound, to build) |
| **S1** (to be designed; must pass A1–A4) | one world feature that makes lateral computation pay without hurting the S0 reflex | beat the best tuned R and Rg by > 3 SE; the lateral-off fork removes ≥ 50% of the gain; F above the S0 champion's F in S1 | candidates below, each measured in the prototype first |
| S1r | the radius gene in the S1 world, as its own step | the radius-1 fork removes ≥ 50% of the radius gain | — |
| **S2 BLINK + LEAD** | the target goes dark for 5–20 units; later, a target faster than the dot that must be intercepted | beat R + Rg by ≥ 0.1; the hidden-off fork costs ≥ 30% (does depth pay?); passes A1–A4 first | compute: occlusion +0.05, matched by Rg (so Rg is mandatory); a Reichardt-style hand interceptor (to build) |
| **S2b** (optional) | rotation: a tangential nudge share set by the chiral knob χ | heading control appears; mirror test | — |
| **S3 FOLLOW-HUMAN** | the human cursor on its own layer; income for overlap with its *future* position y(t + Δ), Δ = 0 → 50 → 100 → 200 ms; a press within ±ε of a human click pays | on held-out SapiMouse users: beat Kalman-CV RMSE at Δ = 100 ms and reach click AUC ≥ 0.68, with < 300 cells | useful, measured (table below) |
| **S4 READ** | a strip of glyphs as local receptor patterns plus a blank; an on-screen keyboard; click the key that fills the blank | above the n-gram baseline with matched context; the contacts, lateral and hidden forks each remove most income | n-gram orders 1–5; a char-GRU given the same fovea-limited view |

**S1 candidates, in the order to try them (all estimates, none measured):**
1. **TWIN.** Two identical targets, both of which pay.
   - Under the surface-normal law, a reflex body that sees both is pulled both ways and stalls between them. A lateral
     winner-take-all (each side inhibits the other) commits to one.
   - Because both targets pay, the S0 reflex still earns when one target is clearly nearer, so A1 should hold.
   - Computation should pay most at sizes where both targets often fall under the footprint, which pushes toward
     bigger bodies, not smaller.
2. **DECOY-ramp.** The same decoy, but only at a fraction p of respawns, or at reduced amplitude.
   - p (or the amplitude) rises between generations only while the population's median F stays above the S0 champion's
     F in that world.
   - This is a curriculum across generations, decided outside any life, so it breaks no locality rule. It must still
     pass A1–A4 at its final setting.
3. **Interior blindness.** A smaller target halo (σ_t about 1), so targets appearing inside the footprint matter more.
   Routing interior information to the rim should pay. The naive routers built so far failed (section 5).

Robustness stages from the one-life design run alongside: turnover and kills (v2), drift (v3), energy (v4). Energy
intake and adversaries come after S2.

**Measured S3 yardsticks** (useful; RMSE in px on held-out users, with 1 time unit = 10 ms):

| data | Δ | hold-last | const. velocity | Kalman CV | GRU |
|---|---|---|---|---|---|
| synthetic minimum-jerk | 100 ms | 83.2 | 26.4 | 24.2 | 12.0 |
| SapiMouse (30 test users) | 50 ms | 91.6 | 73.4 | 72.5 | 56.7 |
| SapiMouse | 100 ms | 162 | 167 | 168 | 117 |
| SapiMouse | 200 ms | 260 | 357 | 361 | 223 |
| Balabit (RDP-batched) | 100 ms | 80.4 | 159 | 102 | 75.3 |

- Click within 200 ms, as logistic AUC on kinematics: synthetic 0.95, Balabit 0.59, SapiMouse 0.68.
- Hold-last is hard to beat on the hit-within-16-px measure: the GRU scores 0.53 against hold-last's 0.54 at 50 ms.
  Always report it as the floor.
- Data:
  - SapiMouse: 120 users, about 16 ms events. Primary.
  - Balabit: 10 users; RDP batching makes velocity predictors worse; the repo has no license file. Secondary.
- Scale: human cursor speeds are about 20 px per time unit, so g_n or the screen scale must be raised before S3.

---

## 9. Kernel and ABI changes (proposed ABI 3)

**Reused unchanged:**
- the clockless event engine with heap and window schedulers;
- batches, ties and the causality contract;
- exact LIF and PREDICT; two channels; delays and jitter;
- private gene clocks; GRN tick and readout; morphogen packets;
- earliest-claim division, ACK/REJECT, apoptosis, CONTACT notices;
- hash randomness and common random numbers;
- forks by replay; the ledger; guards; the oracle cap;
- program mode (hand-built references); OpenMP over lives;
- the two-stage selection loop;
- the genome conventions (σ field, mutation operator, crossover by unit).

**Changed or added:**
1. **3D sites.** sitekey packs z, or b' = b + K·z as in substrate's verified patch.
   - Lattice code "hex prism" (D = 8); back/cyc tables extended to up and down.
   - L_max is a world key (2 or 4 in the pilot). Out-of-stack sites are invisible (section 4).
   - Physics tables are keyed by (a, b, z).
2. **Knobs.** g_r[m] (the reserved v5 receptor-gain rows) and ζ (vertical placement). κ is reused as the single
   effector knob. NK 21 → 23. The radius knob comes later.
3. **GRN inputs.** The receptor trace (reserved v5) plus is_S and is_M. NIN 22 → 25. The genome grows from 793 to about 875
   slots; new fields are neutral pads.
4. **RECEPTOR event** (batch group 3; reserved for v5). It is accepted by the accountant at the left limit and
   delivered at +d_min. Record R_RECEPT charges c_rec.
5. **World kind CATCH** in the accountant, next to BELL:
   - dot state (X, F) in closed form;
   - target path with hash-keyed turns;
   - timer respawn;
   - hotspot key state; captures and misses;
   - surface-normal force from the occupancy map, which the accountant already tracks through R_BIRTH and R_DEATH.
   - New world keys: σ, λ_s, λ_bg, g_n, drag exponent, th_click, th_rel, ρ_c, v_t, τ_turn, R_min, R_max, t_resp,
     R_cap, c_miss, c_rec, L_max, and an optional per-generation T draw (off by default; GB11).
   - New ledger columns: income, captures, misses, respawns, clicks, nudges, receptor events, mean distance,
     time in zone, cells per plane.
   - Leave room for a second blob (decoy or twin) with its own σ and click value, so S1 candidates can be tested in the
     kernel without another ABI change.
6. **New forks:**
   - lateral_off (drop in-plane arrivals; about 5 lines in useful-RT's prototype);
   - hidden_off (z ≥ 2 cannot fire);
   - receptor_off; motor_off;
   - later, radius1.
7. **Tests.** The Python reference gains the world. The window scheduler stays a bitwise oracle.

**BELL-1 stays** as world kind 0 and as the regression suite.
- A BELL genome padded to ABI 3, living on z = 0 only with receptors off, must reproduce G1–G10 and S8 bitwise.
- This keeps the verified kernel honest while the body world is added.

**Migration order.**
1. 3D fabric, with BELL bitwise.
2. Receptors plus CATCH, with the Python reference and heap = window.
3. Gates GB1–GB8 and GB12 on program-mode bodies.
4. The hand GRN column grower (GB9, GB13).
5. The kernel census (GB10) at both L_max.
6. The S0 pilot (GB11 is read from it).
7. In parallel with the pilot: the S1 design study in the prototype (A1–A4).

---

## 10. Hard-coded rules

The one-life design's rules 1–22 stay; rule 20 (the BELL lumen law) applies only in world kind 0.

**New or changed rules, each with its reason:**

| # | rule | why it is necessary |
|---|---|---|
| N1 | Two control planes: receptors exist only at z = 0, and only z = 1 twitches reach the world | the user's design; it makes messages necessary and forbids the one-plane reflex (+0.26 to +4.27 in other worlds) |
| N2 | Stack z ∈ [0, L_max); L_max = 4 (user's design) or 2 (control arm) in the S0 pilot; out-of-stack sites do not exist and are invisible | z < 0 is the screen; the cap bounds compute; invisibility stops the wall-reject drain; the measured cost of allowing hidden planes in S0 (founders 8 vs 11 per 8,192) is why both arms run |
| N3 | The body is a rigid, overdamped dot that translates only in v1 | the user's body; a cursor has no heading; rotation is staged |
| N4 | Receptor law: thinned Poisson at the cell's own screen point, delivered at +d_min, genetic gain | the world-to-cell causality contract; Poisson is clockless sampling; noise is physics |
| N5 | Surface-normal pull: F_i = g_n·z_i(t)·n_i over the empty in-plane neighbours, read at t− | local "where" physics; zero net drift for any shape; removes valleys and island cheats (measured); costs about 20% of peak F and cannot reward waves (section 2.2) |
| N6 | Drag γ = n_foot^{1/2}, computed by the world | thrust ∝ rim and drag ∝ linear size, so top speed is size-neutral (measured); growth buys sensing, not speed |
| N7 | The hotspot: the screen registers a press only at X, so the act cell at the body centre clicks on an upward threshold crossing; key hysteresis | a discrete act needs a threshold; hysteresis stops spam; a cursor has one hotspot. It is the one designated *place* beyond the two planes (decision 2) |
| N8 | A vertical placement term ζ·u_z(e), on a global up axis | vertical slots have no in-plane direction; the screen physically defines up |
| N9 | Plane-cue GRN inputs is_S and is_M | measured need: homogeneous bodies storm and lose at every size (useful-RT), and found no founders in 4,096 (synth) |
| N10 | World: timer respawn relative to the dot; capture radius; miss cost | measured: loss-triggered respawn creates a runner trap; the miss cost makes blind clicking lose (−0.207) |
| N11 | Costs: BELL's plus c_rec and c_miss; later c_msg·len and c_wire for radius | the user's "costs for actions"; they bound size and radius locally |

**Removed from the default:** the synthesis's N12 (life length drawn per generation). Measured to make no difference in
the prototype (section 3.1). It returns only if gate GB11 shows that evolved bodies are still growing at T.

**Not hard-coded** (genetic):
- which cells in each plane sense or act, and how strongly (g_r, κ);
- every membrane and messaging knob;
- division direction (ζ plus the existing terms), growth timing, death, and whether any cell enters a hidden plane;
- the radius (from the radius stage).
- No cell *type* is designated. The hotspot is a place on the screen, not a cell type.

---

## 11. Cheats, controls and gates

**Cheat table for CATCH-T with the surface-normal law** (synth; n in brackets):

| strategy | messages? | F | verdict |
|---|---|---|---|
| silent lone zygote [512] | no | −0.020 | floor |
| blind spam-runner: tonic presser + footless tonic drifter, contacts off [512] | no | −0.207 ± 0.006 | loses |
| tonic act ring, blind (14 / 38 cells) [128] | no | −0.351 / −0.844 | loses |
| islands: centre + 6 ring-3 corner columns [128] | yes | −0.201 ± 0.009 (compact ring 1: +1.081) | closed by the surface-normal law (offset law: +2.22) |
| runner: clicker + one tonic drifter, best of 108 [512] | 1 hop | +0.094 ± 0.006 (clicker +0.044) | legitimate kinesis; about equal to the 4-cell column (+0.091) and below the 6-cell one (+0.222), so not a trap |
| every ring, contacts off [128] | none delivered | costs only | wire certified |
| every ring, lateral off [128] | vertical only | unchanged | v1 pays no lateral computation (section 5) |
| hidden-between bodies, contacts off [128–512] (crit) | none delivered | costs only | wire certified in that arrangement too |
| one-plane reflex | none needed | +0.26 to +4.27 in other worlds | forbidden by rule N1; not run in CATCH-T |

Still to red-team in the kernel:
- a slow chemical reflex through packets (the fork set must name chem_off);
- respawn-timer exploitation;
- spokes (thin chains with an act tip; legal, an emergent structure);
- growth into hidden planes (cost measured in section 4.1; whether evolution removes it is the L_max arm comparison);
- grow-forever genomes (GB11).

**Pre-registered gates before any evolution run** (all in the real kernel):
- GB1. BELL G1–G10 and S8 bitwise under ABI 3 with padded genomes.
- GB2. heap = window bitwise for CATCH lives with growth and receptors.
- GB3. Lone zygote ≤ the 2-cell clicker − 2 SE.
- GB4. The hand-built ring curve is monotone up to an interior optimum, with F* > 20× the clicker. The prototype gives
  65× (synth) to 87× (crit: +3.91 / +0.045).
- GB5. The column-by-column curve has no step below its parent by more than 2 SE, in 3 orders.
- GB6. Contacts+chem+division-off at T/2 removes ≥ 95% of second-half income at every ring.
- GB7. Every cheat in the table re-measured; none above the 4-cell column.
- GB8. The hold circuit gain at ring 1 is reproduced (a positive control that 2-hop circuits can be seen).
- GB9. A hand GRN column grower within 2 SE of its program twin at its optimum; a single-mutant scan of it reported,
  including whether one mutation grows a whole ring (the big jump that makes the faint 2 → 8-cell steps matter less).
- GB10. Kernel founder census at L_max 4 and L_max 2 (section 7).
- GB11 (new). **Growth stops.** For the top 64 genomes of the S0 pilot, body size at T/2 and at T. If more than 10% are
  still growing by more than 10%, switch on the per-generation T draw.
- GB12 (new). **Start robustness.** GB3 and GB5 repeated at v_t 0.05 and 0.2 and at R_cap 50 and 200. Report where the
  clicker margin vanishes (prototype: at v_t 0.05 and R_cap 50) and keep v1's settings inside the good region.
- GB13 (new). **Hidden-plane cost.** The hand GRN column grower at L_max 4 and 2. Report cells per plane and F.
- Stage gates: no later stage launches until it passes A1–A4 (section 8), first in the prototype, then in the kernel.

---

## 12. Compute

- **Measured (synth).** The prototype costs 0.21–0.27 µs per cell per time unit on one thread under load 8, with no
  GRN: 3.0 ms per 14-cell life, 20.3 ms per 74-cell life, 49.2 ms per 182-cell life.
- **Measured (sense-RT).** The real kernel copy with receptors and GRN ticks costs 0.72–0.95 µs per cell-unit: 65 ms
  per 74-cell life at 29 MB.
- **Estimate per generation.** 256 genomes × 3 lives plus 64 × 4 rechecks is 1,024 lives.
  - Near the optimum (60–80 cells, 65–75 ms per life): about 66–77 s CPU, about 17–19 s wall on 4 threads.
  - While bodies are at most 14 cells: about 10 s CPU, about 2.5 s wall.
  - Genomes that hit the 300-cell guard (1.1% of random genomes at L_max 4, 3% at L_max 8) cost about 0.3 s per life.
    Early on that adds roughly 3–10 s CPU per generation.
- **Estimate per seed.** 500 generations take about 0.35–2.6 h wall on 4 threads, depending on time spent near the
  optimum.
- **Estimate for the pilot.**
  - 2 arms (L_max 4, L_max 2) × 10 seeds = 20 runs, which is 7–52 h of one 4-thread job.
  - On this laptop's 8 useful threads, as two 4-thread jobs: about 3.5–26 h.
  - A seeded-ancestor arm, if needed, adds half again.
  - Memory: about 30 MB per life, so about 120 MB per 4-thread process.
- **The kernel census** of 8,192 genomes per L_max takes minutes. In the prototype it took 150–175 s on one thread.
- **The S1 design study** in the prototype costs CPU-minutes per candidate world. The two DECOY scans here took about
  55 CPU-minutes (an upper bound: wall time × 4 threads).

---

## 13. What success enables (downstream)

1. **In-sensor reflex tiles** (DOWNSTREAM path 3), now with an actuator.
   - The sense plane over the act plane is a taxel sheet over contractile segments, or a pixel layer over logic.
   - Sony's IMX500 stacks a pixel die on a logic die; Prophesee's stacked event sensors bond per pixel.
   - Every wire is local, the configuration is genome-sized, and the output is motion, not a frame.
2. **Event-camera attention and tracking.** The dot is a region of interest or fovea, and the tissue nudges it toward
   a moving object with no global readout (compare Delbruck's goalie and Renner's Loihi tracker in the research list).
3. **Pointer prediction and assistive pointing** (S3):
   - latency compensation 50–100 ms ahead;
   - tremor smoothing;
   - click anticipation.
   - Measured yardsticks already exist (section 8).
4. **A certified message-necessity benchmark with a closed-loop track** (DOWNSTREAM path 2). The two-plane rule plus
   forks certify the wire. Later stages certify computation, with tuned reflex and single-cell-memory baselines that most
   emergent-communication results lack, and with the no-cliff test that keeps those stages honest.
5. **Science.** Bounded growth would be shown to pay through sensing area (v1) and then through computation (later
   stages), in one continuous, clockless life, starting from one cell. That would be a clean result on the evolution
   of nervous systems ("first sense-act arcs, then interneurons").

---

## 14. Honest risks and what failed

- **The first world built to make computation pay (DECOY) failed** in this interface (section 8.1). Until an S1 candidate
  passes A1–A4, the project has a working first stage and no measured second stage.
- **Founders** may be too rare in the kernel. That would force the seeded-ancestor arm (section 7).
- **The first steps are faint.** Uphill in expectation, but the 2 → 4-cell step needs about 57 paired lives for a
  2-SE call. And it depends on world settings: it vanishes with slow targets or low reward (section 3.5).
- **Hidden planes cost something in S0 and earn nothing yet.** About a quarter fewer founders, and silent stacks eat the
  clicker's margin. The L_max arms measure whether this matters for evolution.
- **Computation does not pay at v1's optimum.** Three hand-built lateral circuits failed at the optimum, one of them
  badly. Whether evolution finds routing for "interior blindness" is open.
- **The growth path through the real GRN is unmeasured** under the new law. Two conjunctions are known traps: "divide up
  once" must run separately from the in-plane timer, and act cells must not keep dividing up (sections 4.1 and 6).
- **The surface-normal law departs from the user's literal "offset" wording.** It costs about 20% of peak F and rules out
  wave-coded locomotion. The user must agree to it (question 1).
- **Prototype numbers are not kernel numbers.** The prototype has no GRN, morphogens or apoptosis, and its contact
  view lags are simplified. Gates GB1–GB13 re-measure everything.
- **Per-life noise is high.** The per-life SD at the optimum is about 0.57, so neighbouring sizes (rings 3 and 4,
  ΔF 0.43–0.53) are only marginally resolved with 7 lives. Two-stage selection helps; the bounded-size claim should be
  judged on 64+ fresh lives.
- **Compute used.** The synthesis used about 30 CPU-minutes; one run (the polarised relay) was stopped after ring 5. The
  critique used about 70 CPU-minutes, slightly over its one-hour budget, mostly on the DECOY scan. The other two
  founder-census families (H, C) were not re-run.

---

## 15. Decisions for the user

Each decision comes with a plain explanation and a recommended default.

1. **The nudge law: which meaning of "where the cell is"?**
   - (a) Its offset from the centre: every act cell pulls along the line from the centre to itself.
   - (b) Its exposed face: only act cells at the edge of the act plane pull, outward from their open side.
   - **Default: (b).** Same lives, same bodies: (a) has valleys for every lopsided body and lets disconnected islands
     win (+2.22); (b) is uphill at every step and the islands are inert (−0.20).
   - The cost of (b): interior act cells are useless as motors; full symmetric bodies earn about 20% less at their best;
     and timing patterns (waves, synchrony) cannot move the body.
2. **Clicking: only at the hotspot, or any act cell pressing at its own spot?**
   - **Default: hotspot only in v1.** It keeps "move, then click", and it makes the 2-cell body the first earner.
   - Be aware that this is the one *place* the rules single out beyond your two planes. No cell type is designated.
   - Multi-spot pressing can return if a later world has several items under the body.
3. **Hidden planes in v1.**
   - **Default: run both arms in the S0 pilot**, L_max 4 (your design, two hidden planes above the act plane) and L_max 2.
   - Why: hidden planes above are measured to cost about a quarter of the founders and to eat the first step's margin
     when cells grow there. Nothing in v1 rewards them yet. Hidden-between is worse at every size.
   - Keep L_max 4 afterwards if its arm climbs as well.
4. **Founders: census first, seeded ancestor only as a declared hedge?**
   - **Default: yes.** Run a kernel census with plane-cue inputs at both L_max. If fewer than 1 in 2,000 genomes are real
     founders, add a seeded arm next to the unseeded one.
   - The proxy rate is about 1 in 1,000 (CI 1 in 2,400 to 1 in 520).
5. **Is v1 allowed to be a "wire" world, with the computation stage still to be designed?**
   - **Default: yes.** Start the S0 gates and pilot now. In parallel, test S1 candidates (TWIN first) in the prototype
     against the no-cliff test A1–A4. Launch no S1 until one passes.
   - Why: DECOY, the planned S1, made the S0 champion lose heavily and made "do not grow" the best strategy.
6. **Life length.**
   - **Default: fixed T = 1024.** Draw T per generation only if gate GB11 finds bodies still growing at the end.
   - Why: in the prototype, T made no measurable difference, and every fixed rule needs a measured reason.
7. **Radius gene.**
   - **Default: deferred** to the stage after the first computation stage passes, with cap 2 and cost c_msg·len per
     event plus c_wire·len per unit.
   - Measured: radius hurts the plain reflex, and its wins so far were in worlds where every cell clicks at its own spot.
8. **Unchanged defaults:**
   - lattice: hex prism;
   - drag: γ = √(footprint), which gives a size-neutral top speed;
   - selection: two-stage (K64 L4);
   - S3 data: SapiMouse primary, Balabit secondary, 1 time unit = 10 ms; check the licences first.

---

## 16. Files

All under `/tmp/claude-1000/-home-jgon-project-ml-cell-dev/aefb0c66-3af5-49c4-936c-154d6434706c/scratchpad/body_design/`:
- `proposal.md`: this file. The pre-critique version is `critique/proposal_pre_critique.md`.
- `synth/cursor.c`, `synth/cur.py`, `synth/common.py`: a copy of useful-RT's prototype plus:
  - the surface-normal law (world key `nlaw`);
  - a receiver-polarity proxy (row knob `s1`).
  - With `nlaw` = 0 it reproduces useful-RT bitwise (ring 1 +0.271).
- `synth/s1_scan.*` (laws × drag × gain), `synth/s2_battery.*` (rings, forks, partial bodies, growth, cheats, hold),
  `synth/s3_lateral.*`, `synth/s4_polar.*`, `synth/s5_contrast.*`, `synth/s6_census.py` and its logs and JSON.
- `critique/cursor.c`, `critique/cur.py`, `critique/common.py`: the synth prototype plus:
  - a stack cap (world key `lmax`);
  - an optional decoy blob (`dec`, `sig_d`, `rho_d`, `c_dec`).
  - With both off it reproduces synth bitwise. `critique/cursor_nodecoy.c` is the copy before the decoy was added.
- `critique/c1_planes.*`: plane arrangements (adjacent, silent hidden stacks, hidden-between).
- `critique/c2_world.*`: optimum vs R_max and σ; the clicker knob landscape; ×½ / ×2 world sensitivity.
- `critique/c3_T.*`: life length vs growth; paired selection signal per step.
- `critique/c4_decoy.*`, `critique/c5_decoy_scan.*`: the DECOY stage and eight milder variants.
- `critique/c_census.py`, `critique/c_census_P_L{2,4,8}.log`, `critique/c_census_P_L{2,4,8}_s11.json`: founder census
  per stack cap; `critique/c7_check.*`: clicker-grid counts and the founders lost to hidden-plane growth.
- Earlier work: `sense/`, `compute/`, `substrate/`, `useful/`, their `redteam_*/` folders, and `research/`.
