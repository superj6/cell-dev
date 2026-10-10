# Plan: getting more advanced circuits to emerge through task variation

*2026-10-10. Built from four groundwork studies (capabilities, niche map, literature, engineering), a headroom study
that tested hand-built positive controls on fresh lives, and two critics who re-ran the key checks. Key artifacts are in
`results/taskvar_study/` (the rest of the scratch work under `taskvar/` is not kept).*

## The short version

- **Only two of the six target capabilities have proven headroom today.** Headroom here means a hand-built body with
  that capability beats the best reflex on fresh lives, using world settings that already exist.
  - **Routing (multi-hop relay)** passes strongly.
  - **Regeneration** passes, by a narrower margin.
  - **Memory, prediction, context switching and discrimination** do not. Every hand-built control for them lost to the
    re-tuned reflex, or failed for a reason we can name. Adding those worlds now would mostly select "be smaller" or
    "do nothing".
- **The world matters more than variety.** The most important fact is where routing actually pays once the body has
  to *grow*, not just be wired by hand. In the small-bright-target world with fast conduction ("POOL"), a GRN-grown
  router beats the best reflex by **+3.83 F** and our best evolved body, s5, by **+2.85 F**. Elsewhere the grown
  router's lead shrinks to +0.6 F (fast conduction alone) or about 0 (today's base world).
  - POOL is also the only world where evolved bodies already beat the reflex (s5 +1.16). The hand-built path from
    the reflex toward routing never falls below the reflex there.
  - The literature warns that scoring several worlds at once does little. Switching the world over time is what built
    modular circuits.
- **So the first experiment separates "a better world" from "variety".** It has five arms on today's organism:
  1. **B:** base world, the control.
  2. **P:** POOL, fixed.
  3. **F:** a family of worlds drawn per life.
  4. **M:** the world alternates every E generations (Kashtan's modularly varying goals).
  5. **W:** the family plus mid-life wounds.
  - Size: 12 seeds x 500 generations per arm, plus a quick continuation of the four best pilot populations.
  - Cost: about 750-1,950 CPU-h, or **$15-35 on one rented 192-core spot box** (cap $120).
  - Calendar: about 2 weeks of engineering and gates on the laptop first.
- **Within-life world switches wait.** That means a motor flip, a blinking target or a change in which blob pays. The
  only within-life change in round 1 is the wound. The others need a passing GRN control first, and a scratch track
  below works on that in parallel.

### Terms used below

- **F**: fitness, which is income per unit time minus the cost of cells, spikes, messages and misses.
- **Best reflex**: the hand-built column reflex, re-tuned in the world being tested. We always take the better of the
  re-tuned and original versions *on fresh lives*, because re-tuning overfits its tuning lives by 0.15-0.5 F.
- **Program body / grown body**:
  - A program body is hand-built and fully formed at time 0.
  - A grown (GRN) body develops from one cell, like an evolved one, so it pays for its own development.
  - Program bodies overstate the headroom that evolution can reach by 1.8-3.2 F.
- **lateral_off**: a fork of the same life with in-plane (neighbour-to-neighbour) messages blocked. The F it removes
  measures how much a body relies on lateral computation.
- **Relayed share**: the probes trace each motor spike back to the receptor event that started it. A chain is
  "relayed" if it crossed at least one in-plane hop. The reflex scores 0, the hand router 0.36-0.58, s5 0.22-0.39 and
  s7 0.62-0.68.
- **Paired lives / SE**: every body is scored on the same random lives (common random numbers), and leads are given
  as mean ± standard error of the per-life difference.

---

## 1. What we target first, and why

### Where each capability stands (all on fresh, paired lives)

| # | Capability | Best positive control vs best reflex | Verdict |
|---|---|---|---|
| 1 | **Routing / multi-hop relay** | Program router in POOL **+5.83 ± 0.10** (1,024 lives); lateral_off costs -11.43. Grown router in POOL **+3.83 ± 0.14**, and +2.85 ± 0.14 over s5 (512 lives). Relay chains show latency in steps of one hop (0.50 / 1.01 / 1.53 / 1.99 at d0 0.5). | **Target first** |
| 6 | **Regeneration / size regulation** | Grown regenerating router (regen7) in wounded lives: +1.79 ± 0.11 over its non-regenerating twin, +1.09 ± 0.13 over the reflex. Blocking division at the wound costs -2.11. Size holds: 125 cells after the wound against 123 unwounded. | **Target second** |
| 4 | Context switching (motor flip) | A perfect switcher would gain +2.10 F per life, and a forced latch in the hidden planes works (+3.25 in flipped lives; hidden_off removes it). But the honest local trigger scores -3.02 ± 0.24: it latches in 90% of *unflipped* lives. | Needs a GRN slow-gene trigger first |
| 5 | Discrimination (wide decoy) | Centre-surround body -0.05 ± 0.12. The tuner switched the veto off. | No control |
| 2 | Memory (blinking target) | Best of four memory bodies +0.27 ± 0.10. Naive holds lose 1.4-6.8 F. | No control |
| 3 | Prediction (fast straight targets) | No interceptor exists. At v_t 0.4 a motionless 2-cell clicker ties the reflex (+0.61 vs +0.67). | No control |

### Why routing first

1. **It survives the cost of growing, but only in the right world.** A GRN-grown router with the same knobs beats the
   reflex as follows:

   | World | Grown router | Program router |
   |---|---|---|
   | Base (d0 1) | +0.06 | +2.26 |
   | Fast conduction (d0 0.5) | +0.55 to +0.60 | +3.4 to +3.8 |
   | POOL | **+3.83** | +5.68 |

   POOL is sigma 0.4, lam_s 4, d0 0.5 and d_min 0.25. A tiny bright halo lights about one sense cell, so one column
   alone gets sparse, noisy evidence and has to pool and relay it.
2. **Evolution is already on the path there.** POOL is the only world where evolved bodies beat the best reflex: s5
   +1.16 ± 0.08 (lateral_off removes 86% of its post-development F), s7 +0.32 ± 0.07.
   - The hand-built growth path from the reflex toward the router never drops below the reflex. Filling the interior
     with relaying sensors (ring 3 plus 4 columns at relay gain 0.25) reaches +2.73 F. It is not monotone, though:
     later steps dip by up to -0.86 ± 0.09.
   - With fast conduction alone, the path has no downhill step (smallest step +0.04 ± 0.11; first step +1.01 ± 0.12).
   - At today's base, the path first dips (-0.23 ± 0.09).
3. **It buys the most selection information per CPU-second.** That information is the router-vs-reflex z² per CPU-s:
   22.7 in POOL, 16.3 at d0 0.5 and 5.5 in base.

### Why regeneration second

- Wounds use world keys that already exist (`kill_t`, `kill_frac`).
- The control is a *grown* GRN genome, which shows the capability is reachable in the genome space evolution searches.
- No evolved body regrows usefully: s5 refills 24-42% of killed sites, and blocking its division at the wound changes
  F by about 0. regen7 refills 78%.
- It also gives division a job after development, and the literature backs it: damage during training made neural-CA
  regeneration robust (Mordvintsev et al. 2020).
- Caveats:
  - It tests development more than circuitry.
  - On the whole family, the larger *non-regenerating* program router still has the higher F (regen7 minus router@ring4
    is +0.40 ± 0.14 in wounded lives and -0.95 over the family).
  - No control uses apoptosis, so this does not yet give death a job.

### What variety can and cannot do here (honest framing)

- **Scoring many worlds at once gave "virtually no speedup"** for evolving modular circuits (Kashtan, Noor & Alon
  2007, opened by the literature study). Goals that *alternate over generations* and share subproblems sped evolution
  10-1,000x and produced modular circuits (Kashtan & Alon 2005).
- **Our routing family asks for no new circuit.** The base-tuned router does as well on it as a family-tuned one
  (+3.03 vs +3.08 F). Variety here tests robustness and generalisation. The new circuit has to come from the world.
- **So the experiment includes a fixed-world arm (P)** to tell "variety helped" apart from "POOL is a better world".

---

## 2. The task-variation design

### 2.1 One fixed change to the base: fast conduction everywhere

- **The change:** d0 0.5 and d_min 0.25 in every life of every arm (call N5).
  - A message hop takes half as long, about 0.5 time units, against a membrane integration time of 2-4.
  - Newborn cells discover their contacts twice as fast.
- **Gate already met:** on fresh lives the re-tuned router leads the re-tuned reflex by +4.52, and lateral_off
  removes 71-92% of the router's F.
- **Not a per-life draw:** d0 is cell physics, so drawing it per life would randomise the organism rather than the task.
- **Status:** a world constant under your standing approval for minor tweaks. I am reporting it because it re-baselines
  gates GS1-GS6, which will be re-run.

### 2.2 The family across lives (arms F, M, W)

- **What changes per life:** only task keys. Prices stay fixed (R_cap 500, c_miss 10, c_live 0.02).
- **c_live is load-bearing:** at x3 the router's lead falls from +3.08 to +0.44. Freeze it.
- **Base world** (catch_speck_l4 at d0 0.5): sigma 0.6, lam_s 2, lam_bg 0.05, v_t 0.1, tau_turn 20, R 2-6, t_resp 50.

| Member | Keys changed | Weight | Program-router lead (d0 0.5) | Why it is in |
|---|---|---|---|---|
| base | none | 25% | +3.46 ± 0.33 | Stepping stone: the 2-cell clicker and S0 champion earn here (A1). It keeps today's skills paid. |
| **pool** | sigma 0.4, lam_s 4 | **25%** | +3.67 ± 0.26 (grown, re-tuned +3.83) | The only world where routing survives growth and evolution is already climbing. |
| bright | lam_s 4 | 12.5% | +5.26 ± 0.39 | Rich evidence. Rewards relaying it while the target crosses the interior. |
| noisy | lam_bg 0.2 | 12.5% | +2.99 ± 0.27 | Rewards coincidence detection: interior relays must reject background events. |
| slow | v_t 0.05 | 12.5% | +4.50 ± 0.34 | The target lingers over the interior, where only relays can steer. |
| quick | v_t 0.3 | 12.5% | +0.55 ± 0.22 | Does *not* favour our router. It keeps the family from being tailored to our hand body (rule N6) and is a world where pooling bodies do relatively well. |

- **Source of the leads:** critic c1, 1,024 fresh lives, about 128 per member.
- **What gate G1 measures before launch:** grown-router leads for every member except pool, and every member at
  T 768 and 1536. Every number above was measured at T 1024 only.
- **Left out, with the measured reason:**
  - wide halos (sigma >= 0.9): the re-tuned router wins only as a bigger reflex, with lateral share 0.31 / 0.00;
  - twin or second food: lead +0.45, and the twin world selects smaller bodies (genetic correlation of F with end
    size -0.61);
  - near placement R 1-4: +0.78;
  - every b2 decoy world: routers lose -0.9 to -3.1, and the reflex wins by clicking less.

**How lives get their member:**
- A hash of (run seed, purpose, generation, life slot) picks the member, with no stateful generator, so common random
  numbers and resume both hold.
- Stratified slots: over any 8 consecutive life slots each member appears in proportion to its weight (2, 2, 1, 1,
  1, 1).
- Every genome in a generation sees the *same* members in the same slots. The mixture therefore adds no noise to the
  ranking within a generation. It only changes which worlds a generation is judged on.
- With 3 + 4 lives per generation, the per-life family behaves like fast random switching, with a period of about one
  generation. That is the literature's "too fast to build modules" regime, and it is why arm M exists.

**Justification for the fixed weights:** they are designer choices, set once in the config before launch and never
changed during a run. Base gets 25% as the stepping stone (POST_PILOT_CALLS L1). POOL gets 25% because both critics
asked that the region where evolved bodies already pay be weighted above the router-favouring members. The other four
share the rest equally.

### 2.3 Wounds: the one within-life change (arm W)

- **Who is wounded:** 50% of lives are left unwounded. In the rest, a uid-random fraction of cells dies once, at
  kill_t = u·T.
  - u ~ U[0.25, 0.75]. It is given as a fraction of the drawn life length, because T is drawn per generation from
    {768, 1024, 1536}.
  - kill_frac is 0.25 or 0.5, in equal shares.
- **Why this dose:** it is the measured V2 family, where regen7 passed.
- **How it combines with members:** the wound draw is independent of the member draw, so W = the family in F plus
  wounds.
- **Readouts:**
  - Because the life before kill_t is bit-identical to its twin, each wound is an exact paired fork.
  - division_off at kill_t measures what regrowth is worth.
  - Report separately the lives that lost the hotspot (0,0,1) or the centre sensor. That site is a designed identity
    (Q6).
- **Not this round:** the reserved per-cell hazard `kill_rate` (Q5) stays for a later round, because it needs work in
  all three engines.

### 2.4 Switching over generations (arm M, Kashtan's modularly varying goals)

- **How it works:** the whole population's world alternates between two goals every E generations, on a fixed
  calendar that ignores the population. Within a generation, every life comes from the current goal.
- **Goals:**
  - **A = pool:** sparse, bright evidence. Sensors should fire on single events and pool laterally.
  - **B = noisy:** dense background. Sensors need coincidences to reject background events.
  - Both share the relay subproblem ("get interior evidence to the rim motors") and differ in the sensor threshold and
    relay gain. That is the closest match we have to Kashtan's "shared modules, one threshold changes".
  - If noisy fails gate G1, the fallback order is bright, then slow.
- **Choosing E:**
  - E is 30 generations. Kashtan used 20 and found a useful window spanning orders of magnitude.
  - Gate G4 fixes E once before launch: 30 if re-adaptation after a switch takes 15 generations or fewer, 100 if it
    takes 15-50, and the arm is dropped if it takes more than 50.
  - E never changes during the run.
- **Limitation:** true modular goals (approach one blob, avoid another) wait for a discrimination control.

### 2.5 Within-life world switches: designed now, launched later

The flip, blink and payoff-swap worlds do open large F gaps (flip -5.5 F, blink 20/20 -5.0 F for the reflex), but no
local body recovers them yet.

**Gate before any of them enters selection:** a GRN-grown control must beat both the best reflex and the best fixed
alternative body by more than 3 SE on a 50/50 mixture of lives. A genes_blind fork after the switch must also remove
that gain; this is the fixed-weight control of Soltoggio 2008.

**Design rules for when the gate passes,** already prototyped and bitwise-checked in `engineering/kernel_x.c` and
`xref.py`:
- **Switch process:** a two-state telegraph process at Poisson world times.
- **No timing cue:** the start state is drawn from the stationary distribution, so "state A comes first" cannot act as
  a cue.
- **Which keys may switch:** only world-side keys read by the accountant, and never prices.
- **lambda_max:** fixed per life, as the maximum over both states.
- **Ledger:** per-state columns, with no relabelling of existing ones.
- **Cues:** any cue is a property of an object, never a world-wide rate shift. The background-rate cue doubled misses
  and acts as a body-wide broadcast.
- **Flicker:** if used, its phase is random per placement, never anchored at t0.

### 2.6 Stepping stones and curriculum

- Base keeps 25% of lives in every family arm, so A1 holds and the small-body rung stays paid. A1 is checked per member
  in G1.
- There is no population-triggered ramp or curation: the dropped c_miss-ramp pattern stays dropped.
- Fresh-start arms begin from the usual founder census (16,384 genomes, top 8). It uses the same random genomes in
  every arm, each screened in its own arm's world.
- **Early read (Phase 1a):** continue the pilot's four best SPECK populations (s5, s6, s7, s8; `population.json`) for 300
  generations each in B, P and F. This is the quickest test of whether POOL pushes today's poolers toward routing. They
  are labelled continuations, because the generator state was not saved.

### 2.7 How fitness aggregates over the family

- **Selection fitness = the plain mean of F over a generation's lives, each life in its own member.** No per-world
  scale constants are used.
- **Why raw F:** every member uses the same prices, so F is in the same currency everywhere. A capture is worth 500 in
  every world. Members that pay more carry more weight because the world pays more there, not because of a number we
  picked.
- **The alternative, if you prefer it:** divide each member's F by a fixed constant measured once (the grown router's
  F there).
  - It is a hidden designer weighting toward that body's strengths, so I do not recommend it.
  - Never use ranks within the population: ranks detach cell cost from F and break "growth bounded by physics plus
    costs".
- **Reported but never selected on:** per-member raw F, per-member F normalised by the best reflex, and the lead over
  the best reflex.

### 2.8 Held-out worlds (generalisation)

- **How they are scored:** each held-out world gets its own best reflex (re-tuned there, better of frozen and re-tuned
  on fresh lives). Each final best is scored on 1,024 fresh lives, with lateral_off.
- **The generalisation score** is the number of held-out worlds where the best beats that reflex by more than 3 SE with
  lateral_off removing at least 50% of the lead (an ANNECS-like count). Arms B and P see the same held-outs, so
  "trained on a family" is compared with "trained in one world".

| Held-out | Keys (d0 0.5 throughout) | What it tests |
|---|---|---|
| H1 noisy pool | sigma 0.4, lam_s 4, lam_bg 0.2 | New combination of two trained axes |
| H2 mid halo, faster | sigma 0.5, v_t 0.2 | Interpolation plus a speed between trained values |
| H3 bright and slow | lam_s 4, v_t 0.05 | Combination; program router +7.2 here |
| H4 far placement | R_min 3, R_max 8 | Untrained axis |
| H5 long stays | t_resp 100 | Untrained axis |
| H6 long life | T 2048 | Untrained life length |
| H7 new wound dose | kill_frac 0.35 at 0.6 T | Untrained wound (trained only in W) |
| H8 wide halo (report only) | sigma 0.9 | Expected to favour the reflex; a sanity check |

---

## 3. Engineering work, in order

"Config" means no code change once the harness exists. Effort is in person-days (pd).

| # | Step | Effort | Config-only? | Approval |
|---|---|---|---|---|
| done | Random tie-breaking (N1, `rank_desc`) and the fast kernel build | done | - | - |
| E1 | **Checkpoint and resume, with determinism pinning** (N2). Save the population, ids, origins, generation, the torch generator *and* the tie generator, plus log offsets, every 25 generations. `run.py --resume`. Pin ATEN_CPU_CAPABILITY=avx2, torch, libm FMA path and kernel .so SHA; golden-life replay at start. Test: 3 + resume + 3 generations equals 6, byte for byte, with wall times stripped. | 1-1.5 | no | none |
| E2 | **d0 0.5 / d_min 0.25 base.** Re-run GS1-GS6, re-tune the reflex and the router (3-4 CPU-h), and check window_h <= d_min. | 0.5 | yes | report only |
| E3 | **Family harness** in `evaluate.py`, behind a config flag that is off by default: hash-keyed per-life member draw with stratified slots; member id in `World.name` (metadata, outside the kernel vector); `kill_u` as a fraction of the drawn T; per-member validation and final tables. Tests: CRN equality, recheck alignment, member shares. The prototype `engineering/fam_eval.py` already runs inside `evolve_life`. | 2 | members are config | Q3 to *use* it |
| E4 | **Generation calendar** for arm M: phase = floor(g / E) mod 2 selects the member list. Unit test. | 0.5 | E is config | yes (schedule) |
| E5 | **KILL port to lifesim.js** (it throws on kill_t >= 0 today) plus new truth lives for the wound worlds. Keeps kernel = reference = JS for every world in the matrix. No b2 port is needed, because no b2 world is in the plan. | 0.5-1 | no | none |
| E6 | **Readouts and analysis script:** see the readout list below this table. | 1.5-2 | no | none |
| E7 | **Phase-0 gate scripts** (G1-G4 below) and the pre-registration file (`results/taskvar/prereg.md`, committed before launch). | 1.5 | no | none |
| E8 | **Rental launch kit:** pinned image, bitwise replay check on the new host, elastic threads (`sweep.py --max-threads`). | 0.5 | no | decision 2 |

Readouts produced by E6:
- per-member lead over the best reflex and over s5;
- lateral_off share;
- P.chains: relayed share, share with 2 or more in-plane hops (`lat_hops >= 2`), latency by hop count;
- hidden_off;
- regrowth panel from the fate logs (sites refilled, rim against hotspot/centre, births after the kill, final size
  against the unwounded size);
- reflex@hollow2 against hollow3 per member (the "be smaller" check);
- correlation between F and end size;
- selection information per CPU-second per member.

**Total before launch:** about 9-10 pd, roughly 2 weeks on the laptop, with no rented compute. After the run: analysis
2-3 pd; atlas and playground 2-3 pd.

**Scratch control track** (parallel, no repo edits, about 4-6 pd, 30-50 CPU-h). It unlocks capabilities 2-5 for round 2:
- **C1, flip trigger:** a GRN annulus body with a slow gene (lambda about 1/128 per tick, integrating 100-300 time
  units) that toggles the inner and outer motor pathways.
  - V4's diagnosis says program cells (tau_m <= 16) cannot integrate long enough.
  - Test first whether the consequence the world already shows is enough. After a capture the target is re-placed,
    so its halo vanishes from under the body. Do that before asking for the tap-cell consequence bit (decision 3).
- **C2, discrimination:** a two-hop surround through a hidden relay, or an "avoid" pathway, against the same-peak wide
  decoy.
- **C3, memory:** a body-wide "nobody sees it" veto carried by a hidden-plane flood, as a GRN genome with six or more
  cell types. Lowest priority, after four failures.
- **Prediction:** waits for face weights (X1) or another direction primitive.

**Gated later work** (only if a scratch control passes): the epoch bundle in kernel.c, reference.py and lifesim.js
(about 3.5-4 pd, plus 1-1.5 pd JS, plus about 1 pd for a JS b2 port if blobs are involved), with an ABI number and Q4.

---

## 4. The experiment

### 4.1 Phase 0: gates on the laptop (about 60 CPU-h)

Confirmation lives come from `fresh_seeds(n, seed0 = 40,800,000 + 5,000·block)`:
- blocks 0-9 for gates;
- blocks 10-19 for final confirmations;
- blocks 20-39 for held-outs;
- no block above 39, which keeps every seed below 41M.

| Gate | What it checks | Pass rule | If it fails |
|---|---|---|---|
| G0 | GS1-GS6 at d0 0.5 | Gates pass as re-baselined | Fix before anything else |
| G1 | Grown router (router_genome, re-tuned on the family) against max(frozen, re-tuned reflex) and against s5, on 1,024 fresh lives at T 768 / 1024 / 1536, per member. Also A1 per member, and selection information per CPU-s. | Family mixture: grown router > best reflex and > s5 by more than 3 SE, with lateral_off removing >= 50%. POOL: the same (expected from +3.83 / +2.85). | Family fails: drop F and M; W becomes POOL + wounds. POOL fails: stop and re-plan. |
| G2 | DFE pre-test: 256 random s5 mutants on paired lives in base (d0 0.5) and in POOL | Report only: fraction of beneficial mutants (> 2 SE) per world, and whether they raise lateral share | Informs interpretation; does not block |
| G3 | regen7 against its twin with kill at u·T, at all three T | > 3 SE in wounded lives at each T | Drop W |
| G4 | Re-adaptation: s5 population for 40 generations in pool, then switch to noisy; generations to regain the pre-switch lead within 1 SE of a no-switch twin | Sets E (30 / 100 / drop), once | M dropped if re-adaptation takes more than 50 generations |

### 4.2 Phase 1: the matrix (one rented box)

All arms use today's organism (ABI 3, L_max 4, no face weights, gene duplication off), so the arms differ only in the
world. Every other setting is as in the pilot: (32 + 224) selection, 3 + 4 lives with recheck, T drawn per generation,
fast kernel build, checkpoints every 25 generations.

| Arm | World | Seeds x generations | Question |
|---|---|---|---|
| **B** | base SPECK at d0 0.5 | 12 x 500 | Control. Also the N5 re-baseline of the pilot. |
| **P** | POOL fixed | 12 x 500 | Does the right *world* produce routers? |
| **F** | family per life (section 2.2) | 12 x 500 | Does fast, random variety add anything beyond POOL? |
| **M** | pool <-> noisy every E generations | 12 x 500 | Does slow, structured switching (Kashtan) add what F does not? |
| **W** | F + wounds (section 2.3) | 12 x 500 | Does regeneration evolve, and does it cost routing? |
| 1a | continuations of pilot s5, s6, s7, s8 in B, P and F | 12 runs x 300 | Early read: do today's poolers climb toward routing? |

- **Seeds:** run seeds 100-111 in every arm (the pilot used 0-9), so founders come from the same random genomes in
  every arm.
- **Extension:** the top 4 runs by valid lead over generations 480-500, from any arm, go on to 1,000 generations via
  resume (X5).
- **Common yardsticks:** every final best is scored in base, POOL and the family mixture, plus its own training
  distribution.

### 4.3 Budget

Per-life cost is 0.065 s (idle-core model, s5-size body) to 0.16 s (loaded-laptop pilot rate), divided by 1.21 for the
fast build. A generation is about 1,070 lives. POOL and bright worlds cost about 1.2-1.4x per life because receptor
candidates double; wounded lives cost about 0.8-0.9x.

| Item | CPU-h (idle estimate to loaded upper bound) |
|---|---|
| Phase 0 gates (laptop) | about 60 |
| Main matrix: 60 runs x 500 generations | 500-1,450 |
| Phase 1a continuations: 12 runs x 300 generations | 60-140 |
| Extension: 4 runs x 500 more generations | 30-100 |
| Final scoring, lesions, held-outs, held-out reflex re-tunes, probes | 70-150 |
| Scratch control track (laptop) | 30-50 |
| **Total** | **about 750-1,950** |

- **Rented:** one c7a.48xlarge (192 cores) runs the matrix plus continuations in about 4-10 hours of wall time,
  including setup and the bitwise replay check.
  - Spot ($3.40/h): **$15-35**. On demand ($9.85/h): $40-100. **Cap: $120.**
  - The extension runs on the laptop in 1-2 days, or for 2-3 more spot hours.
- **Laptop only:** about 4-8 days for the matrix.

### 4.4 Pre-registered success criteria (written to `prereg.md` before launch)

**Routing (primary).**
- **R1, router count per arm.** A seed counts if its final best meets both conditions on 1,024 fresh lives in its
  training distribution:
  - it beats max(frozen, re-tuned reflex) by more than 3 paired SE;
  - lateral_off (forked at t 256) removes at least 50% of that lead.

  This is the pilot's router test, unchanged.
  - Programme success: at least 1 router in any arm (the pilot had 0 of 10).
  - Comparisons: P against B (does the world matter?), F against P and M against F (does variety matter?), using
    Fisher's exact test, one-sided p < 0.05. With 12 seeds against 12, 0 against 4 gives p ≈ 0.05.
- **R2, beyond pooling (the grown-body bar).** In POOL, the best beats s5 by more than 3 SE. s5 is already +1.16 over
  the reflex there, and the grown router +2.85 over s5.
- **R3, multi-hop signature (reported for every best).** These are descriptive: s7 already has a high relayed share
  and still trails in F, so R1 is the test.
  - relayed share of rim-motor receptor chains, against s5 0.22-0.39, s7 0.62-0.68, router 0.45-0.58;
  - share of chains with 2 or more in-plane hops;
  - median latency by hop count, which for a relay should rise in steps of about 0.5 (= d0).
  - "Multi-hop" is claimed only if chains with 2 or more hops make up at least 15% of receptor chains, with that
    stepped latency.

**Regeneration (arm W, with the same metrics computed for B and F bests for comparison).**
- **G-1:** in wounded lives the best beats its own division_off-at-kill fork by more than 3 SE.
- **G-2:** at least 50% of killed sites are refilled by T. s5 refills 24-42%, regen7 78%. Rim and hotspot/centre are
  reported separately.
- **G-3:** final size is within ±20% of the unwounded final size (no overgrowth).
- **Success:** at least 3 of 12 W seeds pass G-1 to G-3, against 0 expected in B and F.
- **Death:** a p_die knockout in wounded lives. We claim that death has a job only if it costs at least 0.5 F at z > 3.

**Generalisation.** The held-out count (section 2.8) per best, compared F and M against P (Mann-Whitney, one-sided).

**Switching (arm M).**
- Re-adaptation time after each switch: generations until the valid lead is back within 1 SE of the pre-switch value.
  The literature predicts it shrinks across switches, toward 5 generations or fewer.
- Generations to first reach R1-level lead, against P and F.

**"Be smaller" guards (reported every 50 generations).**
- Median end size of the bests.
- Population correlation of F with end size.
- reflex@hollow2 minus hollow3 per member.
- s5-style lateral share of the bests. A drop below 0.3 is a flag; the pilot's SPECK bests were at 0.63-1.07.

**Memory (a side readout).** hidden_off cost for every best. Any cost above 0.5 F at z > 3 would be news, because the
hidden planes have so far been inert.

### 4.5 Kill and stop rules

- **K0:** G1 and G3 outcomes as in the Phase 0 table. These are decided before any money is spent.
- **K1, stuck start:** at generation 200, if 8 or more of an arm's 12 seeds are still at 4 cells or fewer, stop that
  arm. Resume keeps the option to revisit.
- **K2, laggard variety arm:** at generation 200, stop F, M or W if its median lead over the best reflex, measured in
  POOL on 256 fresh lives (the common yardstick), is more than 2 F below P's. B always runs, as the control.
- **K3, budget:** stop at $120 or 2,000 CPU-h, whichever comes first.
- **Never:** no arm is stopped or steered by a mechanism readout. Selection uses F only.

### 4.6 What each outcome would mean

| Outcome | Reading | Next |
|---|---|---|
| P > B on routers | The world was the barrier | Cross POOL with face weights (X1) or gene duplication (Pilot 2 matrix) |
| F or M > P | Variety itself helps | Widen the family as new controls pass |
| M > F ≈ P | Structured switching over time is what matters (as Kashtan found) | Build more alternating goal pairs |
| 0 routers anywhere | Search or expressivity is the barrier, not the world | Pilot 2 diagnostics D1-D3, face weights, or the substrate track |
| W regenerates | Regrowth is reachable by evolution | `kill_rate` (Q5) in all three engines, and give death a job |

---

## 5. Making results visible

**Atlas** (`results/atlas/`), a new part called "Task variation":
- **World cards:** one replay GIF per family member and held-out, showing the reflex and the router in the same life.
- **Arm curves:** lead over the best reflex and lateral share, per generation, per arm. It also marks the switch
  generations for M.
- **A routing card per final best and every router found:**
  - relayed share;
  - hop histogram;
  - latency against hop count;
  - lesion bars (lateral_off, hidden_off, division_off at the wound);
  - comparison values for reflex, s5, s7 and the hand router.
- **Regeneration film strip:** the body before the wound, just after it and at T, with refilled sites coloured, taken
  from fate logs (`extract.py` traces the median-F life as today).
- **Scoreboard:** every pre-registered criterion, pass or fail, per arm.

**Playground** (`results/atlas/play/`):
- **World presets:**
  - a menu for the six members and the held-outs;
  - every key already runs in lifesim.js;
  - each preset gets new kernel-equal truth lives in `test_lifesim.js`.
- **Wound button** (after the E5 KILL port): kill 25% or 50% of cells at random, or with a brush, and watch the body
  regrow and catch again. Like target dragging, the brush is an interactive add-on; the KILL handler itself is exact.
- **Relay overlay:**
  - colour each twitch by whether its causing chain started in another column, so routing is visible live;
  - built from a light parentage tracer in lifesim.js (about 1 pd), checked against P.trace on scripted lives.
- **Side by side:** the reflex and an evolved best on the same world seed.

---

## 6. Decisions needed from you, and open risks

### Decisions (each explained first)

1. **Fitness over a family of worlds** (Q3 / decision 8).
   - *What it means:* each life draws one of six world settings with fixed weights, and fitness is the plain average
     F, with no rescaling. Prices and organism rules are unchanged.
   - *Question:* use this in arms F, M and W?
   - *Recommendation:* yes, with raw F and fixed weights.
2. **Wounds in selection** (distinct from Q5's `kill_rate`).
   - *What it means:* in half of arm W's lives a random 25% or 50% of cells die once, at a random point mid-life. This
     uses the existing panel keys, so cells are lost by world events and regrowth is entirely the genome's business.
   - *Question:* allow this as a selection axis in arm W?
   - *Recommendation:* yes.
3. **A fixed switching calendar over generations** (arm M).
   - *What it means:* the whole population's world alternates between pool and noisy every E generations. The calendar
     is set before the run and ignores how the population is doing, so it is a property of the environment, unlike
     the dropped c_miss ramp. It is the one form of variation with direct published evidence for building modular
     circuits.
   - *Question:* allow it?
   - *Recommendation:* yes.
4. **Rent one 192-core box** (decision 2).
   - Expected cost $15-35 spot, capped at $120.
   - It happens only after resume (E1) and the bitwise check on the new host (E8) exist.
5. **For your information, not a question:** fast conduction (d0 0.5, d_min 0.25) becomes the base world for every arm
   (N5, a minor tweak under your standing approval). It re-baselines gates GS1-GS6.
6. **Not asked now:**
   - within-life epochs (Q4);
   - the tap-cell consequence bit (decision 3);
   - face weights (Q1 / X1).

   They come back only if the scratch controls show they are needed. Face weights can later be crossed with the
   winning world. If you also want the spike-bit tissue (roadmap decision 1), the same worlds, gates and criteria carry
   over to it.

### Open risks

1. **Variety may add nothing.** The simultaneous mixture is the design the literature found least useful, and our
   family needs no new circuit. Arm P is there so that this outcome is still informative.
2. **Selection noise against small steps.** Steps along the path are worth 0.04-1.0 F, while the paired per-life SD is
   about 3-4 F with only 3 + 4 lives per generation. POOL has only about 13 captures per life. If no arm moves,
   Pilot 2's D3 test (4x lives) is the next check.
3. **Evolution may settle on pooling.** In POOL, pooling already beats the reflex, so it is a comfortable local
   optimum. R2 (beat s5) is the bar that tells pooling from routing.
4. **"Be smaller."** POOL shrinks the size penalty (hollow2 only -0.42 behind). The guards in 4.4 watch for it.
5. **Wounds may reward redundancy rather than regrowth.** The larger non-regenerating router is still competitive. G-1
   (against the division_off fork) separates the two. The fixed hotspot makes wounds partly a test of "regrow the
   designed site".
6. **Untested life lengths.** All headroom was measured at T 1024; G1 and G3 recheck at 768 and 1536.
7. **c_live is load-bearing.** At x3 the routing lead nearly vanishes, so prices are frozen for the whole programme.
8. **Four capabilities have no route yet.** Memory, prediction, context switching and discrimination stay out until
   the scratch controls pass. This round may show routing and regeneration only. Those two are the capabilities the
   measurements say are within reach.

---

### Evidence and literature

**Scratch evidence** (copies in `results/taskvar_study/` where listed; the rest is not kept):
- `headroom/results_summary.json`, `headroom/confirm_v{1,2,5}.json`, `headroom/p1_chains.json`;
- `critic/c1_v1.log` (family re-run, J.w1 = 0 lesion, price sensitivity);
- `critic/c2_path.log` and `c2b_*.log` (growth paths);
- `critic/c3_wound.log`;
- `critic/c4_grn.log` and `c5_grn_tuned.log` (grown-router headroom);
- `nichemap/table.csv` (48 worlds, CPU model);
- `capabilities/regen7.py`;
- `engineering/fam_eval.py`, `kernel_x.diff`, `exp4_effects.json`;
- `literature/decoy_headroom.json`.

**Literature** (opened by the literature study):
- Kashtan & Alon 2005, PNAS, doi 10.1073/pnas.0503610102;
- Kashtan, Noor & Alon 2007, PNAS, doi 10.1073/pnas.0611630104;
- Parter, Kashtan & Alon 2008, PLoS Comput Biol, doi 10.1371/journal.pcbi.1000206;
- Clune, Mouret & Lipson 2013, arXiv 1207.2743;
- Mordvintsev et al. 2020, Distill, "Growing Neural Cellular Automata";
- Albantakis et al. 2014, PLoS Comput Biol, doi 10.1371/journal.pcbi.1003966;
- Soltoggio et al. 2008;
- Risi, Hughes & Stanley 2010, doi 10.1177/1059712310379923;
- Botero et al. 2015, PNAS, doi 10.1073/pnas.1408589111.
