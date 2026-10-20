# Open worlds: concurrent, open-ended task worlds (design for review)

Status: design draft, 2026-10-19. Nothing here is implemented, seeded or launched. It replaces the "more
pursuit variants" direction of TASK_VARIATION_PLAN.md for the next phase. It keeps every standing rule:
- one continuous life;
- no clock;
- local, asynchronous cell rules;
- genome-driven cell death;
- behaviour discovered by evolution, never written in;
- worlds judged by what their information pays.

Supporting measurements are in `outputs/behavior_20261019/` (behaviour review of the multitask run) and
`outputs/open_worlds_design_20261019/` (engine, search and limits audits).

## 0. Summary

**What the user asked for (2026-10-19):**
- tasks that are not brought in stages;
- each task open-ended, with room for many new abilities;
- tasks that resemble real problems, with many variables and partial information;
- compute allocated partly by where something new is improving, while every task always gets some.

**What this proposes:**
- Six task worlds, all in training from generation 0 (the sixth is optional, §3.6).
- One shared physics: odour plumes in a meandering current, walls, moving predators and prey, carrying food home,
  planting.
- One shared set of senses: gene-tuned odour receptors, flow, vibration, touch, a sun compass and light.
- Fitness stays net energy.
- Selection keeps per-world scores, a breeding archive of distinct behaviours, and a learning-progress allocator with
  a fixed floor of lives per world.

**Cost:**
- Engineering: about 4–7 weeks of agent work on the engine estimates, including exact C/Python matching. The JS
  viewer comes later.
- Compute: a life costs about 2–3× today's, mostly from the extra receptor streams. A pilot is about 330–500
  CPU-hours (2–3 laptop days). The main run is about 1,150–4,000 CPU-hours. The upper end is the reason to consider
  rented compute.

**Decisions needed are listed in §9.** The first is whether predation can end a life.

## 1. Why the current worlds stall

Measured in the 2026-10-19 behaviour review of four lineages × 250 generations:

- **Every task is "find a glow, go to it, tap".** One sense (a scalar brightness field), one currency (food), one
  action. The same reflex partly solves all eight tasks. The gains evolution found were reflex tuning:
  - tapping only near food (far taps fell 50–65%; catch per tap 0.22 → 0.35 in AO, 0.19 → 0.36 in s8);
  - cheaper steering (strokes halved, aim kept or improved);
  - staying at patches until empty (departures from empty patches 0.50 → 0.82 in s6).
- **New demands are thin slices on top of a reflex that already earns most of the reward.**
  - Matching: "go to the bigger glow" earns 45% of the maximum without memory.
  - Dark flash: most catches come within 5 units of the flash ending, a lunge rather than a remembered search.
    Aim at the last-seen spot falls to zero by 5–10 units in every genome.
  - Harmful decoy: harmful and good targets differ only in blob width within the same brightness field, and no
    lineage steers toward good food rather than harmful (aim ≈ 0).
- **No task requires a sequence of different behaviours within one trial**, so nothing rewards mode switches or held
  state.
- **The internal machinery that could do more is idle or narrow.**
  - Hidden cells are inert in all four lineages.
  - The gene layer is essential: blinding genes to activity costs 8–12 catches.
  - One lineage (D90) holds a cue across the matching gap in its slow genes, but the cue pushes its choice the wrong
    way (shift −0.072). The effect vanishes when gene updates are frozen. A single mutation flips it to +0.028.
- **Selection is too noisy to see small steps.** At 2 lives per task, measurement noise is 0.5–2.6 fitness, larger than
  a useful step (§6.2).

## 2. Principles for the new worlds

1. **Concurrent, not staged.** Every world is in training from generation 0. No world waits for another to be
   mastered, and none is retired. Engineering may land in pieces; training starts only when the full first set
   exists (§8).
2. **Open-ended.** Each world must offer many independent routes to improvement:
   - sensing, discrimination, timing, memory, inference, movement, risk management and resource management;
   - a ceiling far above the reflex;
   - no single trick worth most of the reward.

   Checked by headroom measurement before use (§7).
3. **Real-world structure.** Many variables are drawn per life from wide ranges. Information is partial, noisy and
   intermittent. Hidden variables (where a source is, whether a predator is hunting, what a plant's state is) must be
   inferred.
4. **One physics, one set of senses.** All worlds are built from the same ingredients (§4), so an ability that appears
   in one world can pay in another. Each world emphasises one objective but contains the other ingredients at random
   background levels.
5. **Locality.** A cell senses only what is at its own site. Senses are physical fields the world computes at the cell's
   screen point. Which cells sense what is decided by each cell's genes. No global channel, no clock, no world state
   reaches cells.
6. **World entities may follow written rules; the organism may not.** Predators, prey and pests are simple rule-based
   agents, part of the environment. They react to the individual organism, never to the population. Co-evolving
   opponents would be population-responsive and are out of scope without the user's approval.
7. **Fitness is task performance.**
   - It is net energy over the life: food value earned, minus the frozen physical costs, minus damage.
   - There is no shaped score.
   - Each world's net energy is its selection objective.
8. **Hand-built bodies are yardsticks, not gates.** Nature's known strategies (§3) are benchmarks to beat.

## 3. The worlds

Each world is defined by the ingredient levels it draws per life. Ranges below are initial proposals in current units:
- the body moves at 0.07–0.32 units per time unit;
- bodies span about 4 hex rings;
- T = 1024 by default; T = 2048 is an option for the home-base and farming worlds;
- R_cap 500 per standard food unit; frozen costs c_live 0.02, c_miss 10.

Every world also draws background levels of the other ingredients: a weak current, distractor odour sources and, in
some lives, a few walls. A world is a region of one shared parameter space, not a separate game.

### 3.1 Plume foraging

**Goal.** Net energy from food sources that are smelled rather than seen.

**World.**
- 3–8 sources, each releasing odour puffs at Poisson times (rate 0.3–2 per unit). Each puff carries a blend over the
  odour species.
- Puffs drift with a uniform current whose direction turns at Poisson times (mean 30–300 units) and whose speed is
  0.02–0.3. They spread as they age and vanish after 50–300 units.
- **Sources:**
  - value 250–1000 per unit eaten;
  - stock 2–6, depleting as eaten and regrowing after 60–300;
  - blends overlap.
- **Toxic look-alikes** share part of a food blend (food A+B, toxin A+C) and cost 250–1500 when eaten.
- Some lives have light from some sources; most have none.

**Hidden.**
- The source position is never sensed directly, only puffs downstream.
- Contact is intermittent; whether a source is depleted is only visible as weaker odour.

**Room for abilities:**
- moving upstream when odour is detected and casting sideways when it is lost;
- using flow to tell upstream from downstream;
- telling blends apart (food versus toxin, rich versus poor);
- remembering where good sources were;
- leaving depleted sources;
- choosing which plume to follow.

**Natural yardsticks:** moth surge-and-cast; *E. coli*-style temporal comparison; infotaxis (§10).

### 3.2 Predator field

**Goal.** Eat while staying alive.

**World.**
- Food as in §3.1 at moderate density, some of it placed in the open and some near cover.
- Two predator modes, mixed per life:
  - ambush predators sit still with a weak odour and strike within a short radius;
  - pursuit predators wander, detect the organism within 2–6 units (with probability per look), then chase.
- Risk varies over space, so some areas are dangerous and some are safe refuges ("landscape of fear").
- 1–4 predators in total; pursuit predators behave as follows.
  - Speed 0.1–0.35, so some are faster than the body.
  - They give up after 20–150 units and rest 50–150 after contact.
  - Each predator emits its own odour and, in some lives, shades light.
- Shelters are regions (radius 1–2) where predators cannot detect the organism.
- Damage per contact: 1000–3000 (2–6 food units).
- Optionally, contact can end the life (decision 1, §9).

**Hidden.**
- Predators are smelled or felt before they are close.
- Whether a predator is hunting is not directly signalled.

**Room for abilities:**
- detecting danger from odour or flow;
- freezing versus fleeing;
- running to shelter and waiting;
- feeding when predators are resting or far away;
- trading food value against risk;
- telling predator odour from food odour.

**Natural yardsticks:** freeze-or-flee decisions; risk-sensitive foraging; the "landscape of fear" (§10).

### 3.3 Home-base foraging

**Goal.** Bring food back to a home site.

**World.**
- A home disk (radius 1–2) at the body's start, marked by a faint home odour within 1–3 units.
- Food 4–15 units away, sometimes behind walls, corridors or gaps.
- Tapping food picks up an item; capacity 1–3 items, with extra drag while loaded.
- A tap inside the home disk delivers the load at 2–3× the value of eating on the spot. Eating on the spot is still
  allowed, at base value.
- Currents push the body; walls block movement, light and odour.

**Hidden.**
- Home cannot be sensed from afar.
- Routes are blocked out of sight.
- The organism knows whether it is loaded only through drag and its own state.

**Room for abilities:**
- getting around obstacles;
- keeping track of the way home (path integration);
- using odour landmarks;
- remembering routes and productive areas;
- deciding when to carry rather than eat;
- choosing trip lengths.

**Natural yardsticks:** desert-ant path integration; central-place foraging theory (§10).

### 3.4 Evasive prey

**Goal.** Catch prey that react to the organism.

**World.**
- 2–6 prey of up to three behaviour types, drawn per life:
  - darters flee at 0.15–0.4 when the organism comes within 1.5–4;
  - freezers stop moving and stop emitting odour when alarmed;
  - burrowers run to the nearest refuge and stay hidden for 30–150.
- Prey emit odour and sometimes light. Alarm is probabilistic per look.
- Capture by tap within the capture radius, worth 500–1500.
- Walls in some lives allow cornering.

**Hidden.**
- Alarmed prey go quiet or hide.
- Prey type must be inferred from how they react.

**Room for abilities:**
- stalking (a slow approach to avoid alarm);
- intercepting a fleeing prey's path;
- ambushing near refuges;
- cornering against walls;
- telling prey types apart and choosing among them.

### 3.5 Farming

**Goal.** Shape the environment for later gain.

**World.**
- Fertile ground regions marked by a soil odour.
- Tapping an empty fertile spot plants a seed at a small energy cost. It ripens after 60–200, stays ripe for 40–150,
  then spoils.
- Ripe plants emit odour.
- Pests (rule-based agents) wander and eat ripe crops.
- Weeds spread into tended ground unless removed by taps. Crops grow well only where they are tended, as in
  damselfish algal gardens (§10).
- Passive wild food is scarce.

**Hidden.**
- Planted but unripe sites emit nothing.
- Ripening times vary.
- Pests are smelled only nearby.

**Room for abilities:**
- planting and returning at the right time;
- tending a territory;
- keeping away from areas where pests are active;
- spacing plantings;
- trading the cost of planting against wild foraging.

This generalises ABI 7's contact food, where a real "farming" signal already appeared: contact-produced harvest rose in
all four lineages.

### 3.6 Group living (optional for this phase; see §9)

**Goal.** The group's total energy.

**World.** 2–6 bodies grown from the same genome share a world with food and predators.
- Each body emits a world-provided body odour.
- Bodies are not neighbours of each other's cells, so they interact only through the world.

**Room for abilities:**
- spacing out;
- following one another to food;
- joint vigilance;
- division of labour.

**Why it's optional:** it needs multi-body support in the engine (8–12 agent-days plus JS) and costs about K× per life
for K bodies, so it is a candidate for a later phase rather than this one.

### 3.7 The existing eight conditions

POOL, persistent, the two flash conditions, delayed matching, patches, contact food and harmful decoy stay as a
report-only panel. They are not training objectives. The panel checks that old abilities are not silently lost.

## 4. Shared physics and senses (ABI 8)

### 4.1 Senses: generic, gene-tuned modality slots

Biology: each receptor cell expresses particular receptor proteins, chosen by gene regulation. A smell is coded by the
pattern across many receptor types, and receptors mostly report change.

Design:
- The genome gets S_MAX = 10 generic modality slots, added once: light, 4 odour species, flow, vibration, touch,
  sun, and 1 spare.
- Each sense cell has a signed gain per modality, read out from its genes like today's single `g_r`. Each modality has
  its own receptor trace, which feeds back into the gene network.
- Which cells smell what, and whether a cell responds to touch or flow, is therefore decided by evolution, cell by cell.
- **What the slots hold:**
  - slot 0 is today's light field, unchanged;
  - world keys bind the other slots to physical fields: odour species k, touch, or flow.
- Each delivered event costs `c_rec · |g_r[m]|`, so sensing everything is not free.

**Mechanics (from the engine brief):**
- Append the new receptor-trace inputs after `is_M`, and the new gain rows after `g_r`.
- Old genomes pad with zeros. They are blind to the new slots and pay nothing for them, and evolve their gains up.
- Each modality has its own candidate stream on new random streams, keyed by cell, modality and count.
- The membrane input becomes `Σ_m g_r[m] · n_rec[m]`. It stays exact on the 1/8 grid.

**Fields:**
- **Odour species k:** concentration `C_k` is the sum over live puffs (§4.2). The receptor rate is
  `lam_bg + lam_s · C_k / (C_k + K)`. This saturating transduction is standard receptor biology, and it keeps the
  thinning bound at `lam_bg + lam_s`.
- **Flow:** `lam_bg + lam_f · clip(−(U_rel · n)/u_max, 0, 1)`, where U_rel is the current minus the body's own
  velocity and n is the cell's exposed face. Upstream-facing rim cells fire more, like antennae or a lateral line.
- **Touch:** `lam_t` while the cell's screen point is within `r_t` of a wall or agent.
- **Vibration:** `lam_v · Σ_agents (speed/v_max) · exp(−d²/2r_v²)`, with r_v about one body length. This is the
  near-field sense of a moving predator or prey, like canal neuromasts. It is separate from the steady flow sense.
- **Sun (compass):** a direction field `s` that drifts slowly (mean turn time ≥ T). The rate is
  `lam_bg + lam_c · max(0, n · s)` on the cell's exposed face. It is a local reading of a physical field, like
  polarised skylight for ants. It lets path integration evolve, because heading can be sensed. Strokes already give the
  tissue local self-motion signals.
- **Light:** today's halo field. Walls can occlude it (§4.3).

**Receptor adaptation (recommended).** Each sense cell gets a gene-read adaptation time constant per modality. The
receptor then reports the rate relative to its own recent average, giving "on" and "off" responses. The default is no
adaptation, so it is evolvable rather than fixed.

In biology adaptation sits physically in the receptor. *E. coli* compares roughly the last 1 s against the 3 s before
it. ON/OFF pairs are enough for worm klinotaxis and drive fly upwind runs versus local search (§10). The gene layer
could also evolve it, but slowly.

**No sense of internal energy.** Ledger-level energy is a whole-body quantity, so feeding it to cells would be a
global channel.

### 4.2 Odour puffs and the current

- **Current:** uniform in space, piecewise constant in time, turning at Poisson world events (like today's blob
  turns).
- **Puff motion:** a shared advection integral gives every puff centre in closed form.
- **Spread:** `σ² = σ0² + 2D · age`. Amplitude scales as `σ0²/σ²`.
- **Cost control:** puffs are summed in creation order with a cutoff at `d² > c · σ²`.
- **Walls** absorb puffs whose centre crosses them; the hit time is one division.
- **Why discrete puffs:** they give real intermittency. This follows the filament model of Farrell et al. 2002 and
  its 2D variant in Singh et al. 2023.
  - In real turbulence, whiff and blank durations are heavy-tailed (p(t) ∼ t^−3/2), which rewards memory of the
    last contact and casting.
  - Lives mix near-ground releases (nearly continuous, gradient-climbable) with free-stream releases (patchy), so
    both gradient strategies and surge-and-cast pay.
- **Release and meander settings:** release rates and meander statistics are drawn per life. Starting points: wind
  switches with mean period about 3× the puff release interval, heading SD about 45°, truncated at ±60°.
- **Fallbacks:**
  - a steady Gaussian plume per source, which is cheaper but has no intermittency;
  - spatially varying currents, which are excluded because they need an ODE.

### 4.3 Walls

- Walls are axis-aligned boxes, randomised by rotations, reflections and translations.
- The body is a swept point with a closed-form hit time on its decaying-force path:
  `t_hit = t_x − τ · log(1 − k_hit · γ/τ)`.
- Frictionless sliding drops the force component that points into the face.
- Contact changes ("kinks") are world events.
- Walls occlude light with a slab test and absorb odour.
- This follows the existing proposal (`outputs/obstacle_navigation_design_20261016/PROPOSAL.md`). It is the riskiest
  block for exactness and needs fuzzing (§8).

### 4.4 Agents (predators, prey, pests)

- Agents are kinematic: piecewise-linear paths with "look" events on their own random streams (every 1–3 units, or at
  Poisson times).
- **Look events:**
  - at each look an agent reads the body position and applies its rule (wander, chase, flee, freeze, hide or rest);
  - headings are set with sqrt normalisation, without atan2, so JS can match bitwise.
- **Contact:**
  - contact is checked at looks and at clicks (squared distance against the radius);
  - the exact continuous contact time between the decelerating body and a moving agent is transcendental, so it is
    deliberately not used.
- **Signals:** agents emit an odour species and can shade light.

### 4.5 Carrying and home

- A load counter, capacity 1–3.
- Tapping food picks up an item instead of eating it.
- A tap inside the home disk delivers every item and pays its value.
- Extra drag while loaded gives a physical cue.
- Provenance is tracked first-in-first-out, as in ABI 6.

### 4.6 Planting

- ABI 7's four fixed slots become a capped list of plants (about 16).
- A plant moves through planted → ripening → ripe → spoiled.
- The field strength is a pure piecewise function of time, and spoiling is a world event.

### 4.7 Energy and death

- Income is the value of food eaten or delivered.
- Costs are unchanged: maintenance, spikes, strokes, messages, division, secretion, misses, plus receptors per modality.
- Damage from predators and toxins is a ledger cost.
- Option: predator contact ends the life when accumulated damage passes a threshold (decision 1). Cells' own
  genome-driven death is unchanged.

### 4.8 What does not change

- Cell rules, spike timing and lattice.
- Growth and death rules.
- Frozen prices.
- One life per evaluation, with no clock, no reward input and no world state given to cells.

## 5. How each life is drawn

- **Parameters:** each world has 10–20 parameters drawn per life from the ranges in §3 on world seed streams. Examples:
  - source count, values and blends;
  - current speed and turn rate;
  - predator count, speed and detection range;
  - wall layout;
  - prey types;
  - ripening times.
- **Background levels:** every life also draws background levels of the other ingredients.
- **Held-out regions:** for each world some parameter regions are never used in training. They are kept for transfer
  tests, for example stronger currents than ever trained, more predators, unseen wall layouts, and new blend overlaps.
- **Held-out combinations:** some cross-world mixtures are also held out, such as home-base foraging under predation,
  or farming with evasive pests.

## 6. Search

All numbers below are from the search and compute audit (`outputs/open_worlds_design_20261019/search/`).

### 6.1 Every world in every generation

- Each candidate is evaluated in every world in every generation. The score per world is mean net energy.
- Selection uses epsilon-lexicase over per-world scores, as now.
- Parents are re-evaluated on fresh lives each generation.

### 6.2 Lives per world and noise

- **Measured noise and correlations:**
  - per-life noise is 0.7–3.7 fitness by task;
  - two genomes on the same seeds correlate 0.2–0.4, and 0.4–0.65 for close relatives.
- **Ranking a single 0.2-fitness step at 2 SE** would take hundreds of lives in noisy worlds, which is out of reach.
- **What a toy model of the search shows:**
  - progress comes mainly from generations;
  - very noisy worlds with rare small gains need about 8 lives, or the population drifts downhill;
  - extra lives spent near the selection cut-off ("racing") help most.
- **Plan:**
  - each candidate gets 24 lives per generation: a floor of 2 per world (about 50%), and 12 lives allocated (§6.3), with
    at most 8 per world;
  - the top 96 of 320 candidates, plus up to 16 behaviourally novel candidates, get 24 more lives on the same
    allocation;
  - survivors end up with 8–16 lives per world.

### 6.3 Learning-progress allocation, with a floor

Recomputed every 5 generations and fixed within each 5-generation block. Allocator state is checkpointed.

**Weights:**
- `w_t = 0.2/K + 0.8 · (a_t + ν_t) / Σ(a + ν)`, falling back to uniform if every term is zero.
- `a_t = max(0, |β̂_t| / SE(β̂_t) − 1)`, where β̂_t is the slope over the last 30 generations of a fixed-seed probe
  (the top 4 world-t elites on 8 fixed lives, run every 5 generations, about 0.5% of lives).
- Taking the absolute value means a world where abilities are being forgotten also gets more measurement.
- `ν_t = min(3, newly confirmed behaviour cells in world t in the last 10 generations)` (§6.4).

**Lives:** `L_t = 2 + round(12 · w_t · σ_t / Σ w · σ)`, which is Neyman allocation: lives in proportion to importance
times noise.

All constants are config values. The uniform arm (§6.6) tests whether allocation matters at all.

**Why the absolute value and the floor:**
- In a Minecraft multi-task study, absolute learning progress discovered 82 of 107 items, against 17–70 for uniform
  sampling.
- Counting only improvement caused cycles of forgetting and rediscovery (Kanitscheider et al. 2021).
- Lenski et al. 2003 found complex functions evolved only while simpler ones stayed rewarded (23/50 populations, versus
  0/50 when only the complex one paid), so no world is ever dropped.

**Two later extensions (decisions 6–7, §9):**
- **Within-world allocation over parameter regions:** sample regions of a world's parameter space by their own
  absolute learning progress, as in ALP-GMM (Portelas et al. 2019).
- **An alternating-emphasis arm:** the floor stays, but extra lives rotate between worlds on a fixed period.
  - Kashtan, Noor & Alon 2007 found that switching between goals that share sub-goals sped up evolution 25–700×.
  - Pursuing all goals simultaneously gave no speedup.
  - Our allocator already shifts emphasis over time. An explicit rotation would test the effect directly.

### 6.4 An archive that keeps distinct abilities

- **The existing archive stays:** the 64-slot Pareto archive.
- **New: a behaviour grid per world.**
  - It is MAP-Elites style: 4×4 cells over two behaviour measures per world, with fixed bounds.
  - An elite's value is the running mean over its own-world lives.
  - A newcomer replaces an incumbent only if it beats it on shared lives by at least 1 SE.
  - Incumbents are re-checked on their own world each generation (about 4% of lives), and leave only when replaced.
  - 25% of children take one parent from a random filled cell.
- **"New ability"** means a newly filled cell scoring at or above the world's elite median, confirmed on 8 more paired
  lives.

**Initial behaviour measures:**

| World | Measure 1 | Measure 2 |
|---|---|---|
| Plume | upstream progress per odour contact | sideways casting after losing contact |
| Predator | share of time in shelter while a predator hunts | freeze share (speed ≈ 0) with a predator within 3 units |
| Home-base | items delivered per trip | straightness of the return path |
| Evasive prey | approach speed in the last 3 units | capture rate per alarm |
| Farming | plantings per life | share of harvests within the ripe window |

### 6.5 Variation

- Gene duplication and deletion are on in one arm (dup 0.02, del 0.01, silent copies). This lets spare gene slots take
  new roles without disturbing development.
- Duplication costs about +30% CPU per life when all spare slots are filled.
- Mutation count is unchanged, apart from scaling with active genes.

### 6.6 Arms and founders

**Three arms, paired by founder population and run seed:**
- **U:** uniform allocation, the control;
- **LP:** learning-progress allocation;
- **LP+D:** learning-progress allocation plus duplication.

**Founders:** the four multitask lineages (AO, D90, s6, s8), with their full populations and archives padded to ABI 8.
They start blind to the new senses.

**Optional fourth founder:** a from-scratch random population, which tests whether inherited reflexes help or trap.

**Generations:**
- Main run: G = 400.
- Before it, a pilot: G = 100, 2 lineages × 3 arms. The pilot measures cost per life, noise, correlations and allocator
  behaviour on the new worlds.
- The pilot runs every world. It is a calibration, not a stage.

## 7. Checking each world before use

**Port the information-matched controller harness to the current engine,** behind a compile flag so it stops
breaking with each ABI. Add an optional raster log of receptor events per modality.

**Per world, on paired seeds, measure:**
- a privileged ceiling controller that reads the true world state;
- a matched-information controller that sees only the sense cells' events, with the same latency, footprint and costs;
- ablations of the matched controller, removing memory, inference (for example source or predator localisation),
  discrimination (blend identity) and risk modelling.

**Admission:**
- the matched gap over the best evolved or reflex body is large (> 3 SE and ≥ 1 food unit);
- at least three ablations each remove a resolved share of it.

That is the operational test of "many routes to improvement". Worlds that fail are retuned, not dropped from the set.

**Theory baselines beside the controllers:**
- infotaxis for plume search (a Bayesian searcher using the true plume statistics);
- the marginal value theorem for patch leaving.

Evolution should approach or beat them.

**A cheaper first bound:** decode hidden variables offline from the matched receptor raster. Examples: where the
source is, whether a predator is hunting, food versus toxin. This needs no controller.

## 8. Engineering plan

Training starts only when worlds 3.1–3.5 all exist. Engineering order is not a training order.

| Step | Work | Agent-days (engine brief) |
|---|---|---|
| 0 | Harness port to HEAD, `LIFE_CTL` hooks, receptor raster | 2–3 |
| 1 | ABI 8a: genome modality slots (S_MAX 10), receptor adaptation knob, generic slots on existing fields | 4–6 |
| 2 | Odour sources, puffs, current; flow and sun senses | 5–7 |
| 3 | Carrying and home; planting | 4–6 |
| 4 | Agents, vibration sense | 3–5 |
| 5 | Walls and touch (fuzzing time included) | 5–7 |
| 6 | Search changes (§6): allocation-aware draws with seeds keyed by world and replicate, allocator, behaviour grid, novelty candidates, tooling | ~7 |
| 7 | Headroom measurement per world (§7) | 2–4 per world |
| 8 | Optional: multi-body (ABI 9) for §3.6 | 8–12 (+4–6 JS) |

**Total without multi-body:** roughly 30–45 agent-days by these estimates. ABI 5–7 each landed in about a day against
similar per-block estimates, so the realised time may be shorter.

**Exactness contract:**
- **C and Python:** bitwise for everything, under both schedulers, with the fast and full builds giving the same ledger.
- **JS:** single-body blocks only, after training engineering is done.
- **Math:** all new math stays inside the set JS ports bitwise (exp, log, sin, cos, tanh, sqrt and arithmetic). No
  atan2, hypot, general pow or erf.

**Tests:**
- closed-form exports compared with `spec.py`;
- at least 1,000 random short lives per block, kernel against reference;
- legacy replays: ABI 7 truth under V7 and under neutral V8;
- conservation of food, items and plants;
- boundary cases: corners, record-time hits, cutoffs;
- a cost budget per block, benchmarked on `results/multitask_20261018/selected_genomes.json`.

## 9. Decisions for the user

1. **Can predation end a life?** Recommended: yes, after accumulated damage passes a threshold. Otherwise contact is
   only a cost. Ending the life is the realistic pressure toward avoidance, at some loss of information per life.
2. **Group living in this phase?** Recommended: not in this phase. It adds 12–18 agent-days and about K× compute.
3. **Compute.** At 2–3× today's cost per life:
   - **Pilot** (G = 100, 2 lineages × 3 arms): 330–500 CPU-hours. It fits on the laptop.
   - **Main run, lean** (3 arms × 3 lineages, G = 300): 1,150–1,700 CPU-hours.
   - **Main run, full** (3 arms × 4 lineages, G = 400): 2,700–4,000 CPU-hours.
   - Laptop wall-clock: about 6.5–10 days lean, 15–23 days full (about 176 CPU-hours per day).
   - Rented, approximate public prices to verify before use: about $55–150 on-demand or $20–60 spot per
     3,000 CPU-hours.
   - Spending needs the user's approval when we get there.
4. **JS viewer timing.** Recommended: after the worlds are trained. C/Python exactness is enough for science.
5. **From-scratch founder arm.** Recommended: include it in the pilot only.
6. **Allocation within worlds over parameter regions (ALP-GMM style).** Recommended: after the pilot, if world-level
   allocation helps.
7. **Alternating-emphasis arm** (Kashtan 2007). Recommended: make it the pilot's fourth arm only if compute allows;
   otherwise run it after the main comparison.
8. **Growing new world variants from the population's performance (POET-style).** This would make the world respond
   to the population, so it needs explicit approval. Recommended: not in this phase. The wide fixed ranges plus
   learning-progress allocation already give plenty of room.

## 10. References

All references were verified by search or by opening the source on 2026-10-19. [FT] means full text was read;
[AB] means abstract or publisher page only.

**Sensing**
- Malnic, Hirono, Sato & Buck (1999). Combinatorial receptor codes for odors. *Cell* 96:713–723. [AB]
- Chess, Simon, Cedar & Axel (1994). Allelic inactivation regulates olfactory receptor gene expression. *Cell* 78:823–834. [AB]
- Vosshall, Wong & Axel (2000). An olfactory sensory map in the fly brain. *Cell* 102:147–159. [AB]
- Segall, Block & Berg (1986). Temporal comparisons in bacterial chemotaxis. *PNAS* 83:8987–8991. doi:10.1073/pnas.83.23.8987 [AB]
- Berg & Tedesco (1975). Transient response to chemotactic stimuli in *E. coli*. *PNAS* 72:3235–3239. [AB]
- Barkai & Leibler (1997). Robustness in simple biochemical networks. *Nature* 387:913–917. doi:10.1038/43199 [AB]
- Montgomery, Baker & Carton (1997). The lateral line can mediate rheotaxis in fish. *Nature* 389:960–963. doi:10.1038/40135 [AB]
- Curcic-Blake & van Netten (2006). Source location encoding in the fish lateral line canal. *J Exp Biol* 209:1548–1559. [AB]
- Yorozu et al. (2009). Distinct sensory representations of wind and near-field sound in the *Drosophila* brain. *Nature* 458:201–205. doi:10.1038/nature07843 [AB]
- Chalfie et al. (1985). The neural circuit for touch sensitivity in *C. elegans*. *J Neurosci* 5:956–964. [AB]
- Iino & Yoshida (2009). Parallel use of two behavioral mechanisms for chemotaxis in *C. elegans*. *J Neurosci* 29:5370–5380. doi:10.1523/JNEUROSCI.3633-08.2009 [FT]
- Gray, Hill & Bargmann (2005). A circuit for navigation in *C. elegans*. *PNAS* 102:3184–3191. doi:10.1073/pnas.0409009101 [FT]
- Hills, Brockie & Maricq (2004). Dopamine and glutamate control area-restricted search behavior in *C. elegans*. *J Neurosci* 24:1217–1225. [FT]

**Plumes and plume tracking**
- Farrell, Murlis, Long, Li & Cardé (2002). Filament-based atmospheric dispersion model to achieve short time-scale structure of odor plumes. *Environ Fluid Mech* 2:143–169. [AB]
- Celani, Villermaux & Vergassola (2014). Odor landscapes in turbulent environments. *Phys Rev X* 4:041015. doi:10.1103/PhysRevX.4.041015 [FT]
- Connor, McHugh & Crimaldi (2018). Quantification of airborne odor plumes using planar laser-induced fluorescence. *Exp Fluids* 59:137. [FT]
- Kennedy & Marsh (1974). Pheromone-regulated anemotaxis in flying moths. *Science* 184:999–1001. [AB]
- Vickers & Baker (1994). Reiterative responses to single strands of odor promote sustained upwind flight and odor source location by moths. *PNAS* 91:5756–5760. [AB]
- van Breugel & Dickinson (2014). Plume-tracking behavior of flying *Drosophila* emerges from a set of distinct sensory-motor reflexes. *Curr Biol* 24:274–286. [AB]
- Álvarez-Salvado et al. (2018). Elementary sensory-motor transformations underlying olfactory navigation in walking fruit-flies. *eLife* 7:e37815. [AB]
- Vergassola, Villermaux & Shraiman (2007). "Infotaxis" as a strategy for searching without gradients. *Nature* 445:406–409. doi:10.1038/nature05464 [FT]
- Buehlmann, Graham, Hansson & Knaden (2014). Desert ants locate food by combining high sensitivity to food odors with extensive crosswind runs. *Curr Biol* 24:960–964. [FT]

**Predation, risk and foraging**
- Laundré, Hernández & Altendorf (2001). Wolves, elk, and bison: reestablishing the "landscape of fear" in Yellowstone. *Can J Zool* 79:1401–1409. [FT]
- Lima & Dill (1990). Behavioral decisions made under the risk of predation. *Can J Zool* 68:619–640. [AB]
- Brown (1988). Patch use as an indicator of habitat preference, predation risk, and competition. *Behav Ecol Sociobiol* 22:37–47. [AB]
- Charnov (1976). Optimal foraging, the marginal value theorem. *Theor Popul Biol* 9:129–136. [AB]
- Huey & Pianka (1981). Ecological consequences of foraging mode. *Ecology* 62:991–999. [AB]
- Eilam (2005). Die hard: a blend of freezing and fleeing as a dynamic defense. *Neurosci Biobehav Rev* 29:1181–1191. [AB]
- Yilmaz & Meister (2013). Rapid innate defensive responses of mice to looming visual stimuli. *Curr Biol* 23:2011–2015. [FT]
- Vale, Evans & Branco (2017). Rapid spatial learning controls instinctive defensive behavior in mice. *Curr Biol* 27:1342–1349. [AB]

**Navigation and central-place foraging**
- Wehner (2003). Desert ant navigation: how miniature brains solve complex tasks. *J Comp Physiol A* 189:579–588. [AB]
- Müller & Wehner (1988). Path integration in desert ants, *Cataglyphis fortis*. *PNAS* 85:5287–5290. [AB]
- Wittlinger, Wehner & Wolf (2006). The ant odometer: stepping on stilts and stumps. *Science* 312:1965–1967. [AB]
- Orians & Pearson (1979). On the theory of central place foraging. In *Analysis of Ecological Systems*, pp. 155–177. [secondary]

**Niche construction**
- Mueller, Rehner & Schultz (1998). The evolution of agriculture in ants. *Science* 281:2034–2038. [AB]
- Hata & Kato (2006). A novel obligate cultivation mutualism between damselfish and *Polysiphonia* algae. *Biol Lett* 2:593–596. [AB]

**Open-endedness and allocation**
- Lenski, Ofria, Pennock & Adami (2003). The evolutionary origin of complex features. *Nature* 423:139–144. doi:10.1038/nature01568 [FT]
- Yaeger (1994). PolyWorld: life in a new context. *Artificial Life III*, pp. 263–298. [FT]
- Wang, Lehman, Rawal, Zhi, Li, Clune & Stanley (2020). Enhanced POET. *ICML*, PMLR 119:9940–9951. [FT]
- Lehman & Stanley (2011). Abandoning objectives: evolution through the search for novelty alone. *Evol Comput* 19:189–223. [AB]
- Mouret & Clune (2015). Illuminating search spaces by mapping elites. arXiv:1504.04909. [AB]
- Oudeyer, Kaplan & Hafner (2007). Intrinsic motivation systems for autonomous mental development. *IEEE TEC* 11:265–286. [FT]
- Matiisen, Oliver, Cohen & Schulman (2017). Teacher-Student Curriculum Learning. arXiv:1707.00183. [FT]
- Portelas, Colas, Hofmann & Oudeyer (2019). Teacher algorithms for curriculum learning of deep RL in continuously parameterized environments. *CoRL*; arXiv:1910.07224. [FT]
- Jiang, Grefenstette & Rocktäschel (2021). Prioritized Level Replay. *ICML*, PMLR 139:4940–4950. [FT]
- Kanitscheider et al. (2021). Multi-task curriculum learning in a complex, visual, hard-exploration domain: Minecraft. arXiv:2106.14876. [FT]
- Kashtan, Noor & Alon (2007). Varying environments can speed up evolution. *PNAS* 104:13711–13716. [FT]

**Evolved embodied agents**
- Sims (1994). Evolving virtual creatures. *SIGGRAPH '94*, pp. 15–22. [FT]
- Beer (2003). The dynamics of active categorical perception in an evolved model agent. *Adaptive Behavior* 11:209–243. [AB]
- Izquierdo & Lockery (2010). Evolution and analysis of minimal neural circuits for klinotaxis in *C. elegans*. *J Neurosci* 30:12908–12917. [FT]
- de Croon, O'Connor, Nicol & Izzo (2013). Evolutionary robotics approach to odor source localization. *Neurocomputing* 121:481–497. [FT]
- Singh, van Breugel, Rao & Brunton (2023). Emergent behaviour and neural dynamics in artificial agents tracking odour plumes. *Nat Mach Intell*. doi:10.1038/s42256-022-00599-w [FT]
- Joachimczak, Kowaliw, Doursat & Wróbel (2013). Evolutionary design of soft-bodied animats with decentralized control. *Artif Life Robotics* 18:152–160. [AB]

## 11. As built (2026-10-20)

**Engine:** ABI 8, bitwise in C and Python (contract: `docs/LIFE_ABI.md`, ABI 8 extension). Worlds 3.1–3.5 exist;
group living (3.6) does not.

**Per-life worlds:** `src/life/ecology.py` draws every life's world from its life seed alone. Task world names
`eco:<family>` in `life.training_tasks` use it (`LifeEvaluator._life_world`). Families: `plume`, `predator`, `home`,
`prey`, `farm`, and a held-out region of each (`<family>_transfer`), kept for confirmation.

**Fixed modality bindings (the same in every family):**

| Slot | Sense | Rate law |
|---|---|---|
| 1–4 | odours A–D: A food, B richness or prey, C toxin, soil and home, D danger | bg 0.05, s 2, K 0.5 |
| 5 | flow | K 0.25 |
| 6 | touch | bg 0.02, s 4, K 0.6 |
| 7 | vibration | K 3 |
| 8 | sun | s 1 |
| 9 | spare | unbound |

What each odour means is a property of the world; the genome only sets per-slot gains. Padded founders start with
all nine gains at 0, so they sense nothing new until mutation opens a slot.

**Choices made while building:**
- **Receptor adaptation (4.1) is not implemented.** The receptor traces that reach the genes already low-pass each
  modality, so a body can compare fast cell activity with slow traces. Revisit if plume search stalls on saturation.
- **Puffs pass through walls; agents and the body stop at walls.** Walls block light (occlusion).
- **Predation can end a life (decision 9.1).** Damage accumulates per hit (predator hits cost 800–3,000 each). After
  `kill_hits` hits (2–4 in the predator family, 3 elsewhere) the life ends at the next integer time with status
  `killed`, and no guard charge.
  - F still divides by the whole window, so a killed body stops earning.
  - The smallest kill costs about 1.6 F per 1,024-unit life, and a silent zygote scores −0.02. An early death
    therefore never beats staying small.
- **Weeds (3.5) are not implemented;** pests eat ripe plants instead.
- **Math:** see the ABI 8 section of `docs/LIFE_ABI.md` for the functions the new code uses.

**Search:** as in §6, in `src/open_search.py`, `src/allocate.py` and `src/elites.py` (`docs/SEARCH.md`,
"Open-world search").
- Behaviour descriptors are ABI 8 ledger columns (`configs/open_worlds_base.yaml`):

  | World | Descriptors |
  |---|---|
  | Plume | upstream path, crosswind path |
  | Predator | shelter share, freeze share under threat |
  | Home-base | deliveries per pick, time at home |
  | Evasive prey | prey caught, alarms |
  | Farming | plantings, harvests per planting |

- Bounds were set once from the padded founders at T = 1,024, so founders fill the lowest one or two cells of
  each axis.

**Founders on the new worlds (D90 and AO populations and archives, T = 1,024):**
- Every world pays a little: mean F is −1.2 to +0.4 per world, and the best genome reaches +0.8 to +3.3.
- No founder carries food home.
- Predators kill 57% of predator-world lives.
- From-scratch random genomes stay single cells (F ≈ −0.02 on every world).

**Cost:** 70–240 ms of CPU per T = 1,024 life (farm is the most expensive); the old patch world costs 158 ms.

**Pilot (launched 2026-10-20):**
- 2 lineages (D90, AO) × 3 arms (U, LP, LPD), plus one from-scratch population in arm LP, G = 100 each.
- On the laptop, 4 workers × 2 threads at nice 10.
- Study directory: `outputs/open_worlds_pilot/` (launch manifest, frozen checkout, resolved configs, queue).
