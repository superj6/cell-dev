<!-- Written 2026-10-09 by the post-pilot design review (results/catch_pilot/design_review.json holds every assessment and critique). Paths like review/evo or review/xp refer to experiment scripts in that session's scratchpad, which are not kept. -->

# Calls after the BODY-1 pilot (2026-10-09)

Sources: the pilot (RESULTS.md section "2026-10-09 — BODY-1 pilot", `results/catch_pilot/`); four review lenses with new
experiments (`review/evo`, `review/task`, `review/rules`, `review/dev`); three critics with their own checks
(`review/purist`, `review/xp`). All new lives came from fresh bases 36.1M-36.6M. No repo file was edited.

Terms used below:
- **lateral_off**: a fork that blocks in-plane messages after development.
- **Re-tuned reflex**: the hand-built column reflex, with its knobs re-optimised in the world being tested.
- **CPU-h**: the pilot's loaded-laptop rate (about 0.1 CPU-s per life). An idle core measured about 2x faster, so
  every CPU-h figure here is an upper bound.

## Bottom line

- **The pilot worked in the way that matters most.** In SPECK, evolution found local message-passing computations
  that carry most of the fitness: neighbour voting, cooperative detection with feedback inhibition, and gain set by
  crowding. The best bodies also stop growing on their own. It did not produce routing that beats the tuned reflex
  (0 of 10).
- **The routing gap is earnings per cell, not catching skill.** s5 earns almost the reflex's income (9.65 against
  9.95) with about twice the cells, and its algorithm needs those cells. The levers that help are the ones that let
  lateral computation earn more per cell. One is faster conduction, which costs no CPU. The other is a direct way for
  a cell to weigh input by the direction it comes from. Today every body builds that out of morphogen chemistry,
  which is costly and fragile.
- **Before spending on large matrices, run three cheap tests to find out what kind of barrier this is:** continue
  the four best runs to 1,000 generations; seed SPECK with the GRN-grown router; compare 4x lives against standard
  lives from the same population.
- **Rule cleanup.**
  - Added: one rule, per-channel face weights (needs your approval).
  - Replaced: four rules (per-time gene and fate laws, a like-with-like gradient, the gene split at ACK) and one
    harness rule (random tie-breaking replaces "parents win ties").
  - Removed: one knob (tau_tr).
  - Nothing that any evolved body uses is removed.
- **Scaling.**
  - Take the exact speedups first: fast mode, early receptor rejection, resume (so spot machines can be used), and
    per-time laws followed by P0 4.
  - Then add task variety, drawn per life inside a measured niche, and later variety within one life.
  - No shaped score, and no forking of mature bodies into many worlds.

## 1. Working and not working

### Working as intended

1. **SPECK is a working start world.** 10 of 10 seeds grow and 7 of 10 reach F >= +4 (median +4.91). The 2-cell
   clicker earns +0.48 above the lone cell, against +0.04 in v1, where the per-life SD is 0.08-0.11.
2. **Evolution found local computation, and that is where the fitness is.**
   - Spearman 0.71 between F and the share of F that lateral_off removes; lateral_off removes 63-107% of F in s5-s9.
   - Three distinct algorithms: s4 voting with an antenna fringe and a latch, s5 cooperative detection with feedback
     inhibition, s2 a crowding gain that adapts within the life.
   - s5 makes as many captures as the tuned reflex (19.8 against 20.4 per life) with 2.3x fewer misses: 49-50% of its
     clicks capture, against 32% for the reflex.
3. **Bounded growth with no size target, in the better half.**
   - s4-s8 stop by T/2, at 91-173 cells.
   - The contact-count brake (the n_view input) evolved in every grown unseeded lineage. Knocking it out sends 14 of 15
     bodies to the 1,024-cell guard.
   - Caveat: the founder prior gives n_view a weight std of 8, against 1-2 for every other input, so the prior
     favours this brake.
4. **Development builds the wiring and recruits its by-products.**
   - In 9 of 10 SPECK bests, 90-100% of act cells are daughters of the sense cell directly below, so the reflex arc is a
     lineage.
   - s4's motor-less fringe became an inward antenna (silencing it costs -1.42 ± 0.42 F).
   - s5's interior act cells became inhibitory interneurons (removing their feedback costs -5.6 F).
   - Resetting to v = 0, above a negative rest, gives each cell a free short memory, worth 0.9-1.4 F in s4.
5. **The world rules that block cheats and control noise do their job.**
   - Without timer re-placement the reflex falls from 8.62 to 1.13, and capture dispersion rises from 1.3-1.7 to
     4.4-7.9.
   - c_miss 10 makes blind pressers lose.
   - The slit residual is unused (largest gain +0.096).
6. **The expensive parts of selection pay.**
   - Recheck lives are 1.2-2.0x as productive as a third first-pass life.
   - Common random numbers (CRN) make small-body comparisons nearly exact (paired SD 0.0015 at 2 cells).
   - Runs can be judged mid-way: the Spearman correlation with final F is 0.79 at generation 200 and 0.94 at 300.
   - Runs were still climbing at 500 generations: median +0.45 F per 100 generations, s5 +0.66.
7. **Faster conduction helps every body, for free.** d0 0.5 / d_min 0.25 adds +0.14 to +1.70 to the evolved bodies,
   +1.99 to the router and +0.99 to the reflex. CPU per life is 0.9-1.0x, measured on an idle core.

### Not working as intended

1. **No evolved router.**
   - 0 of 10 beat reflex@hollow3. The best, s5, is at +7.06 against +8.69 (z -17).
   - The gap is cells, but not cells that can be trimmed. s5 and s6 earn 9.65 and 9.61 against the reflex's 9.95,
     while carrying 115-163 cells against 56.
   - Capping s5 at 74 cells drops it to 5.47 ± 0.58 F, against 8.43 ± 0.90 at 122, so its algorithm needs its cells.
     The router earns 13.69 at 122 cells.
   - The routing niche is also narrow in world space. The router leads by +2.2 in base SPECK, by about 0 with a twin
     target, near placement or decoy-lite, and by -1.28 with sparse receptors.
2. **Direction-specific synapses exist only through morphogen chemistry.**
   - All four dissected bodies get "excite going up, inhibit coming down" from a standing gradient. Making the weights
     isotropic costs s5 -10.10 ± 0.41.
   - Secretion is about 10% of s5's running cost.
   - The same gradient term also steers division placement, so synapse sign and placement are tied together.
   - It breaks when the gene clock slows: s5 loses -10.25 F at a 4x slower clock, through a tick-phase artefact in the
     gradient.
3. **Hidden planes are inert and cost a little.**
   - hidden_off after development changes F by at most +0.04.
   - Regrowing the same genomes without hidden planes gains +0.21 to +0.32 F on average (s6 +0.93).
   - Towers are a juvenile by-product: act cells inherit their mother's divide-upward state and bud within 1.4-2.5
     time units of birth.
   - In BODY-1 a hidden cell reaches the world only through an act cell, so a reactive task gives depth no job.
4. **Selection cannot tell good genomes apart.**
   - The per-life SD of 2.0-2.5 F is Poisson noise in the capture count. The shortlist rank correlation is about 0.03,
     and the per-life reliability is 0.026.
   - Each child is about 0.19 F worse than its parent (40 mutants of s5; 0 of 40 significantly better), so late
     progress is about 0.005 F per generation.
5. **Each run makes one attempt.**
   - Every run collapses to one breed by generation 2-119.
   - The founder screen does not predict which breed wins (the winner's screen rank is anywhere from 0 to 7 of 8).
   - The between-run SD of final F is 1.52.
   - src/run.py cannot resume a run.
6. **v1 start, and the tie rule.**
   - 6 of 10 v1 seeds stay at 1-2 cells.
   - Four v1 populations kept zero children for 244-364 generations, because parents win exact ties. This is the
     stable sort at src/evolve.py:516/523, and it is still in the code.
7. **Half the SPECK lineages develop slowly.**
   - Growers have 3-14 cells at t = 64; stoppers have 22-138.
   - Across the 10 bests, F rank-correlates with early size (rho 0.94-0.96) and not with final size (0.13).
   - Their late growth costs almost nothing: only s3 and s9 are measurably overgrown (+0.42 and +0.53 F available
     from stopping).
   - So "5 of 10 still growing" is mostly slow development, not a failed size bound.
8. **Unused machinery, and narrow specialists.**
   - Apoptosis never fires (0 deaths per life; the p_die knockout is 0.00).
   - delta and tau_tr do nothing (|dF| <= 0.25).
   - The gene count is stuck at 8, because duplication is off.
   - The seeded arms are locked out of chemistry (secretion -800).
   - Evolved bodies keep a little less of their skill in shifted worlds than the reflex: capture retention over four
     shifted worlds is 0.47-0.53 against 0.58. s4's voting breaks under 4x background noise.

## 2. Ranked calls

### Do now: harness, readouts, one world constant (no organism rule)

**N1. Random tie-breaking.**
- **Change:** a random permutation key from its own generator before each of the three stable sorts. Add `kids_kept`
  and `n_tied` to the curves.
- **Why:** 244-364 frozen generations in four v1 runs (src/evolve.py:516/523/361/368). It also matters for any
  rank-based aggregation added later.
- **Rules:** removes an implicit harness rule ("parents win ties"). Runs with no ties stay bitwise identical.
- **Approval:** none.
- **Cost:** a few lines plus a forced-tie test.
- **Test:** the unit test. Then resume the four frozen v1 populations from population.json, with random ties against
  a frozen-tie control on matched RNG, and count generations to more than 4 cells. This is cheap: a 2-cell generation
  takes about 1 s.

**N2. Checkpoint and resume, with determinism pinning.**
- **Change:**
  - save the population, ids and origins, the generator state, the generation and the curves offset every 25
    generations;
  - pin ATEN_CPU_CAPABILITY=avx2, the torch version, a libm fingerprint check and the build flags.
- **Why:** runs can be judged by generation 200-300 and are still climbing at 500. Spot capacity is 45-65% cheaper but
  is unusable without resume. torch.randn and glibc's FMA paths differ between CPUs.
- **Rules:** none.
- **Approval:** none.
- **Cost:** 100-150 lines.
- **Test:** a resumed run equals an uninterrupted one byte for byte (curves and best genome), on one machine type and
  then across two.

**N3. Exact speedups; leave selection as it is.**
- **Adopt:**
  - fast kernel mode for selection lives: 1.24x, or 1.35x with the sparse readout and x86-64-v3;
  - bitwise-exact early receptor rejection (draw the acceptance before the exp calls);
  - per-call threads that grow as runs finish;
  - founder lives capped at n_max 256 (4-5x cheaper founders, same top 8 in both batches tested; check 4 more batches);
  - clone forks every 50 generations.
- **Keep:** 3 + 4 two-stage selection and CRN.
- **Do not build** parent records or a 1-life first stage, and do not pay for the 2+5 A/B. The models behind those
  options are unvalidated (the sibling-load model was off by about 100x), and D3 below tests the question directly.
- **Rules:** none. The gates and golden tests keep the full build, because fast mode leaves the hashes at their
  initial value.
- **Test:** a fixed set of evolution runs gives identical output; report measured CPU per generation, not modelled.

**N4. One readout patch: reported only, never used in selection or in ranking runs.**
- **Readouts:**
  - income lead over the re-tuned reflex, and the share of that lead that lateral_off removes;
  - income per cell at fixed caps (56, 74, 122) against the reflex;
  - a stop-time panel: division_off forks at T/2 and 3T/4, averaged over the T draw. It replaces GB11's
    "share growing", which lumped near-free late growth together with real overgrowth;
  - developmental speed: cells at t = 64 and the share of final size at t = 256;
  - split-half reliability within the shortlist;
  - capture dispersion;
  - active genes and duplicate use;
  - hidden_off cost.
- **Keep F = income - costs.** Reject distance or time-near-target shaping. On the s5 cloud, those proxies predict F
  on other lives at r 0.09, against 0.17-0.19 for F itself. Yet they are 10-17x more heritable per life (ICC
  0.04-0.07 against 0.004), so selection would breed parking near targets, not catching.
- **Cost:** about 80 lines in scripts/catch_pilot_analysis.py; the stop panel takes about 5 min per body.

**N5. Faster conduction (d0 0.5, d_min 0.25), behind a re-tune gate.**
- **Why:**
  - Every body gains, the router more than the reflex, at no CPU cost.
  - The physical case: a contact hop should be much shorter than the membrane's integration time (tau_m 2-4), as in
    tissue. Today one hop costs about one integration window.
  - A side effect: newborns learn their contacts at 2 d_min = 0.5 instead of 1.0, which halves the "blind first tick"
    window.
- **Caveat:** the +3.3 to +3.5 router leads at d0 0.5 were measured with references tuned at d0 1.
- **Rules:** a world constant.
- **Approval:** a minor tweak. I will tell you, because it re-baselines registered gates (a section-15 entry).
- **Cost:** re-tune the reflex and the router (3-4 CPU-h; retune.py exists) and rerun GS1-GS6. Check growth timing and
  that window_h <= d_min.
- **Go/no-go:** the re-tuned router must lead the re-tuned reflex by at least +3.0 F on 1,024 lives, with lateral_off
  removing at least 50% of the lead. Otherwise stay at d0 1.

**N6. A niche map as a standing gate (scripts only).**
- **Reference set:**
  - hand bodies: the re-tuned reflex, the router, the S0 champion, the 2-cell clicker and the lone cell;
  - evolved bodies: s5 and s7 with their lateral_off twins.
- **Grid:** 3-5 levels on each axis (sigma, lam_s, lam_bg, v_t, placement range, b2 twin or decoy, c_miss, d0, T),
  with 256 paired lives per cell.
- **Filter:**
  - The only hard filter is A1: the clicker and the S0 champion must beat the lone cell, so the start-small rung
    survives.
  - A2 (does computation beat the reflex?) is reported against every computing reference, including the evolved
    pooling bodies. That way worlds are not chosen to suit our own hand-built router.
- **Extra columns:** per-life SD of F, captures per life and CPU per life, so every world gets a measured "selection
  information per CPU-second".
- **Cost:** about 15-30 CPU-min per map.

### Next: implement, validate, then one matrix

**X1. Per-channel face weights.** This merges R-face-gains and D-axial-gain, with a correction both critics found.
- **Change:**
  - A cell weighs an arriving spike by channel and by the face it arrives through: beside, from below or from above.
  - w_c stays as the lateral weight. For each channel, add an offset for "from below" and one for "from above" (4
    readout rows), both starting at exactly 0:
    `w_eff[d][c] = q8((w_c + o_face(d),c) * (1 + a_c*shat_d))`.
  - Chemistry still supplies planar direction (s4's fringe).
- **Evidence:**
  - Freezing each cell at a fork and replacing its weights with a per-channel face table keeps F:
    - s5 +0.04 ± 0.51 and +1.12 ± 0.51 (two independent checks);
    - s2 -0.14 and v1 s5 -0.13;
    - s4 and s8 lose about 1 F, because they also use planar direction, which the a_c term keeps.
  - Any gain shared across channels fails: s5 loses -9.6 to -11.8 F (two critics, four parametrisations). s5 uses
    opposite face profiles on its excitatory and inhibitory channels.
  - A 2-knob form (from below w_c(1+u_c), from above w_c(1-u_c)) keeps s5 (+0.51 ± 0.42) only when the lateral weight
    is exact. Fitted symmetrically it loses -3.6 to -4.2.
  - That form ties the lateral weight to the mean of the two vertical weights. It therefore cannot make a relay that
    is quiet sideways and loud vertically. That is why I prefer the 4 rows.
- **Rules:**
  - Replaces "one weight per channel" with "one weight per channel per face class".
  - +4 rows. Dropping tau_tr (X2) takes one back, so the net is +3 rows.
  - Local: the cell uses only which face a spike came through, which the kernel already knows (zeta, rule N8). No
    clock and no designed role.
- **Approval:** needs yours (synapse rule, ABI 4).
- **Cost:**
  - 10-20 kernel lines in derive and decode, plus the reference mirror;
  - a bitwise test that zero offsets change nothing;
  - founders are unchanged by construction.
- **Before the ABI bump:** run the exact parametrisation (ranges and q8 grid) through the frozen projection
  (purist/facefit.py) on s5, s2, v1 s5, s4 and s8. Go ahead if each is within 1 F of the full face table.
- **Decisive test:** matrix arm V (section 4).

**X2. ABI-4 cleanup bundle, validated as a new base for all arms (not as its own arm).**
- **Changes:**
  - (a) Gene relaxation per unit time: `g <- s + (g - s)*exp(-dt/tau_k)`, with the 7 rate classes decoded as time
    constants equal to today's at P0 2. Compute it once per class per tick.
  - (b) Fate hazards per unit time.
  - (c) The gradient compares like with like: the neighbour's shipped concentration against the cell's own at its last
    shipment. A contact with no packet yet gives 0.
  - (d) The mother's gene split is applied at ACK. A REJECT leaves her genes unchanged, and c_div is still charged.
  - (e) Remove the tau_tr row; the trace window is fixed at 8, its knockout value.
  - If an instant gene class is wanted, redesign decode_lambda once for both.
- **Why:**
  - The tick period is today a hidden biological time scale.
  - s5's slowed-clock collapse runs through the phase artefact: lateral shat rises from +0.04 to +0.19 at a 4x slower
    clock, while slowing the genes with the weights held costs only -1.44.
  - 3-16 rejected claims per life shift a mother's genes with no daughter born.
  - tau_tr is null in all 21 bests, and the genes already filter the traces through their own rate classes.
- **Rules:** replaces 4 rules and removes 1 knob.
- **Approval:** a minor tweak by your standard. I will tell you, because it changes every life.
- **Cost:** 40-60 kernel lines, the reference mirror, and tests (a rejected claim leaves g bitwise unchanged; the
  per-time law is exact at constant dt).
- **Validation before adoption:**
  - First prototype (a)-(c) in reference.py. Rerun the slowed-clock x2 and x4 forks and whole-life P0 4 on s5, s2,
    s7 and v1 s5. Pass if the x4 fork costs |dF| < 1 in at least 3 of 4 bodies and the whole-life P0 4 losses shrink.
  - Then re-score the 10 SPECK bests under the full bundle on 256 paired lives, and rerun a founder census.
  - Adopt the bundle if the median best loses less than 0.5 F and the census earner rate stays within ±20%.
- **P0:** keep P0 2. P0 4 is measured at 1.7-1.9x faster at matched body size, but it gets its own arm later (L5),
  because it also halves the maximum division rate, and early size predicts F.

**X3. Gene duplication on (config only).**
- **Change:** dup 0.02, del 0.01, dup_split false (a silent copy that is bitwise neutral).
- **Not yet:** no large mutation steps aimed at genes. In the DFE test on s5, knockout and row-scale steps on working
  genes were 5-6x more harmful per child, with no gain in beneficial mutants.
- **Why:** every unseeded best has exactly 8 active genes, while the GRN router uses 13.
- **Rules:** config only.
- **Approval:** none; I will tell you, since the effective gene count changes.
- **CPU:** at most +5%.
- **Test:** matrix arm G, with a mechanism endpoint. "More than 8 genes" is not a test, because mutation bias alone
  produces it.

**X4. Three diagnostics on ABI 3.** These are Phase 1 of the next experiment (section 4): continuing the best runs, a
router-seeded arm, and 4x lives.

**X5. A run-level portfolio for discovery** (this replaces demes).
- After the matrix, extend the most promising runs to 1,000 or more generations. Rank them by valid F only, never by a
  mechanism readout.
- Make the first cut lenient: keep the top 3/4 at generation 200. s6 ranked 6 of 10 at generation 200 and finished
  third.
- Pre-registered counts always use the full seed set.

### Later (each behind a measured gate; most need your approval)

- **L1. A task family drawn per life.**
  - Extend the existing per-life world draw (keyed by run, generation and life, so CRN holds) to task keys inside the
    niche map. Keep base SPECK at 25-50% of lives.
  - Make c_miss and, later, kill_rate axes of the family, instead of separate stages or ramps.
  - Aggregate with a fixed per-world linear normalisation (F divided by a constant measured once per world), not a
    population percentile. A percentile makes a cell's cost matter only when it changes rank, which detaches the size
    bound from physics plus costs.
  - Keep the twin and decoy share small: in twin worlds the genetic correlation of F with end size is -0.61, so a
    twin-heavy family selects smaller, reflex-like bodies.
  - Guard: s5's lateral_off share must not fall below its base value across the family.
  - Held-out scoring uses in-world differences from the re-tuned reflex.
  - Test with 20 or more seeds per arm, or as a continuation design.
- **L2. Variety within one life ("epochs").**
  - First gate: a hand-built adaptive body must beat both the fixed centre-surround body and the reflex across a
    mixture. For example, one that switches on surround inhibition in decoy-rich phases, built from the existing b2
    keys drawn per life.
  - Then implement scalar redraws of world parameters at Poisson world times (30-50 kernel lines).
  - The blob-type table that retires b2's six special keys comes after that.
  - Adaptation readout: a genes_blind fork after a switch.
- **L3. A wound world.**
  - kill_rate, a reserved key, as a per-cell hazard on each cell's own random key, with refill through the existing
    claims. Add it as a family axis.
  - Add the open-edge morphogen leak only if regrowth fails.
  - Reshape p_die (the fate axis) only inside this world, and only if death stays unused there.
  - Baseline: stoppers regrow only 0-35% of a 25% wound.
- **L4. Temporal tasks and plasticity.**
  - Launch LEAD or BLINK only after a hand interceptor or memory body beats the re-tuned reflex by at least 3 SE.
    The prior occlusion test gained only +0.05, and a single slow cell matched it.
  - Per-contact STDP or a taste signal only if the epoch worlds show that gene-mediated, cell-wide adaptation cannot
    track switches.
- **L5. A P0 4 arm, after X2.** 1.7-1.9x CPU per life, measured. Later, possibly a per-cell tick-period knob with a
  small price; that adds a price, so it needs your approval.
- **L6. Retire chemistry from synapses if it goes unused.** If the a_c knockouts are null in the face-weight bests,
  take a_c*shat out of w_eff at ABI 5. The gradient stays for division placement. That removes 2 rows, so the whole
  direction story nets +1 row.
- **L7. The radius gene, after N5 and X1.**
  - Price it on compute: radius 2 takes in-plane contacts from 6 to 18, so about 1.5-2x CPU for cells that use it.
  - Measuring the radius in 3D would let a hidden cell hear 7 act cells. That is untested, so it should come with a
    hand-built pooling-layer reference.
- **L8. The n_view founder prior.** Document it now in section 15 as a scale calibration (the input arrives as n_view/D).
  At scale-up, test natural units with one uniform prior std: a founder census plus 3 SPECK seeds.
- **L9. Receptor split, step 2** (exact in distribution, not bitwise). Only after the family's ranges are fixed. The
  distance bound must be re-armed at every target re-placement.

### Dropped or declined

- **Multiple simultaneous targets.** A twin target raised captures only 1.38x and shrank the router's lead from +2.17
  to +0.37. Density helps the reflex.
- **A c_miss ramp triggered by population thresholds.**
  - The evidence was re-priced against a reflex that was never re-tuned.
  - The router's lead stays flat across c_miss (+2.15).
  - It is a designer schedule.
  - Instead, make c_miss a family axis (L1).
- **Demes inside a run.** They add drift load near mutation-selection balance and new parameters. Use the run-level
  portfolio (X5).
- **Face gains shared across channels, and a single axial gain.** s5 loses -9.6 to -11.8 F.
- **Mixed mutation operators as the default** (critique evo-5). The DFE on s5 shows them 5-6x more harmful per child on
  working genes, with no beneficial excess.
- **A founder re-screen that prefers multi-cell earners or distinct phenotypes.** That is selection outside fitness.
  If a re-screen is ever built, rank by F only. Size-adaptive lives per generation are deferred: they matter only in
  small-foothold worlds like v1, which is off the critical path.
- **Delaying a newborn's first tick.** N5 halves the blind window anyway, and the blind claims come from the fast
  bursts that predict F. Re-measure after N5 before deciding.
- **Raising c_live, adding any size-stop rule, or using a morphogen leak or an energy store as a stop fix.**
  - At c_live 0.04 the router's lead falls from +2.25 to about +0.93, and at 0.06 it reverses.
  - Late growth is near-neutral, and 5 of 10 lineages stop without help.
- **Merging p_div and p_die now.** There is no task to test it against, and it touches your death requirement (see L3).
- **A frozen-knob mutation mask for delta and chi.** chi is used in 2 of 21 bests (-1.97, -0.97). delta is the only
  delay-line primitive. Both cost nothing to keep.
- **Re-engineering the seeded genome's secretion.** The seeded arms are controls. Revisit only if seeded arms run again.

### Scaling: reframing the task so it scales

Three facts from the pilot set the economics:
- Cost is linear in cell-time (about 1.2-1.5 µs per cell-time unit).
- Noise is Poisson in the number of scored events (about 19 captures per life, at 0.49 F each).
- Development is paid once per life: second-half F exceeds first-half F by 0.8-3.1 in every SPECK best.

What follows from them:
1. **Take the exact levers first.** Fast mode gives 1.24-1.35x. Early receptor rejection helps because receptor
   candidates are about 35% of CPU on a clean two-term fit. Per-time laws, then P0 4, give 1.7-1.9x. Together that is
   roughly 2.5x per life, and resume lets the runs use spot pricing, which roughly halves the dollars again. GPUs do
   not fit this workload (audit).
2. **Choose worlds by measured selection information per CPU-second (N6), not by estimate.** The estimate of 1.5-2x
   from multiple targets turned into a measured 1.38x in captures. Short lives (T 512) gave 1.2-1.4x more information
   per CPU-second in SPECK. But they change what is selected and work against paying for development once, so measure
   on the map before changing T.
3. **Add variety across lives first (L1), then within one life (L2).** Each life then pays for development once and
   is scored on several situations. Mixing worlds raised split-half reliability from 0.18 to about 0.5. Much of that
   extra heritable variance is "be smaller", though, so the ranges come from the niche map, with lateral reliance as a
   guard.
4. **Bounded growth is also the compute budget.** Report cell-time next to the stop panel.
5. **Out of bounds without your approval, and not recommended:** growing one body and forking it into many worlds
   (this breaks one continuous life), and any shaped score.

## 3. Rule cleanup

| Rule or knob | Call | Evidence | What keeps expressivity |
|---|---|---|---|
| Parents win exact ties (harness) | Remove (N1) | 244-364 frozen generations | Nothing is lost; drift returns on plateaus |
| tau_tr knob | Remove at ABI 4, fixed at 8 | null in 21 of 21 (\|dF\| <= 0.25) | the genes' 7 rate classes already filter traces |
| Per-tick gene relaxation and fate probabilities | Replace with per-time laws | the tick period acts as hidden biology; clock fragility | identical at P0 2; P0 becomes a numerical step |
| Gradient term (neighbour post-ship against self pre-ship) | Replace with like-with-like | lateral shat drifts +0.04 to +0.19 at x4 | max-normalisation is kept (s4's fringe uses it) |
| Gene split at claim | Replace with split at ACK | 3-16 rejects per life move genes with no daughter | none is lost; c_div is still charged |
| One weight per channel | Replace with weight per channel per face class (approval) | per-face tables keep F; shared gains fail | chemistry still gives planar direction |
| GB11 "share growing" as the success readout | Replace with the stop-time panel | it lumped near-free late growth with overgrowth | readout only |
| a_c x shat in synapses | Later, conditional removal (L6) | only if null in face-weight bests | the gradient stays for placement |
| b2's six special keys | Later replacement by a blob-type table (L2) | b2 works; a table generalises it | b2 is the K = 2 case |
| Filled-footprint drag and slit residual | Keep; revisit with section 15.61 | slit unused (at most +0.096) | - |

Keep, each with evidence that it earned its place:
- Chemistry, a0/a1, pol and secretion (knockouts cost -7 to -11 F in s5-s7).
- asym, zeta and the plane cues (knockouts cause runaway growth or shrinkage).
- The n_view input.
- Reset to 0 above rest (document it in section 15 as a feature).
- chi and phi (used in 2 of 21 and 1 of 21).
- delta (needed for future delay lines).
- p_die (your requirement; give it a job, L3).
- The rho input.
- Prices: c_live 0.02, R_cap 500 and c_miss 10.
- Timer re-placement, CRN, the two-stage recheck and the founder census.
- The one remaining designed identity is the hotspot at (0,0,1) (Q6).

Net knob ledger: +4 readout rows (face offsets) -1 (tau_tr) = +3 rows now, +51 genome floats. If chemistry later
leaves the synapses (L6), 2 more rows go, for +1 overall.

Verification: keep reference.py bitwise-equal for organism rules. The probe toolkit, and with it every mechanism
account and lesion in the pilot, depends on reference F equalling kernel F. For world-side additions (epochs, the
wound hazard, receptor split step 2), use handler-level models plus invariants. Put all organism changes into one ABI-4
bump with one gate re-baseline.

## 4. The next experiment: "Pilot 2"

Question: what blocks routing, and does a direct direction primitive help?

**Phase 0: laptop, no rental (about 1-2 weeks of engineering)**
- Build N1-N4 and N6.
- Run the N5 re-tune gate (3-4 CPU-h).
- Prototype and validate X2 (about 10 CPU-h).
- Run the X1 projection check (about 2 CPU-h), and implement X1 if you approve it.

**Phase 1: diagnostics on ABI 3, in the pilot world (SPECK L4, d0 1), starting from the pilot's outputs**

- **D1. Continue s5, s6, s7 and s8 from population.json to generation 1,000.** These are labelled continuations; the
  generator state was not saved, so they are not bitwise extensions. Cost about 100 CPU-h.
  - Pre-registered success: at least 1 of 4 final bests either (a) beats reflex@hollow3 by more than 3 paired SE on
    1,024 fresh lives, or (b) has income above the reflex's by more than 3 SE, with lateral_off removing at least half
    of that lead.
  - Reading: success means time is a main barrier, so extension and the portfolio are the cheap path. A failure where
    the late slopes fall below +0.1 F per 100 generations means the barrier is real.
- **D2. A router-seeded SPECK arm.**
  - Seed with the GS5 GRN router genome (handbuilt.router_genome). Over a whole life it scores +8.90, level with the
    reflex, because it pays for its own development; after growth it is +0.39 above.
  - 5 seeds x 200 generations, about 45 CPU-h.
  - Pre-registered "hold": in at least 3 of 5 seeds the final best keeps lateral_off removing at least 50% of F, with
    F >= 8.4. Then selection can keep a router, and the barrier is reaching one; invest in expressivity and search.
  - Pre-registered "erode": in at least 3 of 5 seeds F falls below 7.9, or the lateral share falls below 25%. Then
    selection, noise or cell economy wears routers down; invest in selection information and in the value of routing.
  - Also report any seed that beats the reflex by more than 3 SE.
- **D3. Is ranking noise the binding limit?**
  - From s5's final population, run 100 generations at standard lives (3 + 4) and at 4x lives (12 + 16), with 3
    replicates each.
  - Score each replicate's best, and its top-8 mean, on 512 fresh lives against generation 0. About 75 CPU-h.
  - Pre-registered: if 4x lives gain at least 2x as much per generation as standard lives (bootstrap CI over
    replicates excludes 1x), noise is binding; consider racing or more lives. If the ratio is below 1.3x, keep 3 + 4.
- **Phase 1 total:** about 230 CPU-h. That is about a day on the laptop, or 1-2 h on one 192-core spot box ($5-10).

**Phase 2: the matrix, on the ABI-4 base**

- **World:** SPECK L4, at d0 0.5 / d_min 0.25 if N5 passes, otherwise d0 1.
- **Run settings:** 500 generations, standard selection, fast mode, checkpoints every 25 generations.
- **Seeds:** 20 per arm, with the same seed list in every arm. Founders are identical across arms, because the new
  rows start at 0 and duplication acts only on children.

| arm | change | seeds |
|---|---|---|
| C | control: the ABI-4 cleanup base, duplication off | 20 |
| V | per-channel face weights (X1; only if you approve) | 20 |
| G | duplication on (X3) | 20 |
| C1 (optional) | control at d0 1, to attribute fast conduction alongside | 10 |

**Budget**
- 60 runs x about 20 CPU-h (24 / 1.24 for fast mode) ≈ 1,200 CPU-h, plus about 200 for C1. Idle and server cores
  probably need about half of that.
- On one 192-core box: about 4-8 h of wall time.
  - spot: $15-45 (c7a $3.40/h, c8a $5.53/h);
  - on demand: $40-80 (c7a $9.85/h).
- On the laptop: about 4-6 days.

**Pre-registered endpoints.** All are against the concurrent control C. They are mechanism and count endpoints,
because 20 seeds against 20 can resolve only about 1.4 F in median F (between-run SD 1.52).
- **V-use:** in at least 10 of 20 V bests, zeroing the face offsets after development costs at least 50% of F (z > 3).
- **V-relief:** the median secretion cost per unit time in V bests is at least 30% below C's, and the median a_gain
  knockout loss is at most 1 F (pilot: 5 of 10 bests lost 3.3 or more).
- **G-use:** in at least 8 of 20 G bests, at least one duplicate-derived gene costs more than 0.5 F when knocked out
  (z > 3).
- **Routers (all arms):** count the seeds whose best beats the re-tuned reflex by more than 3 paired SE on 1,024 fresh
  lives, with lateral_off removing at least 50% of the lead.
  - Program success is at least 1 router in any arm (pilot: 0 of 10).
  - V against C uses Fisher's test (0/20 against 5/20 gives p ≈ 0.05).
- **Reported, not judged:**
  - median final F, income lead, and income per cell at the caps;
  - lateral share, and chain depth: the share of rim-motor chains that start in another column (P.chains);
  - hidden_off cost;
  - stop panel: the number of seeds overgrown by more than 0.25 F (pilot 2 of 10);
  - cells at t = 64;
  - active genes, and genes with self-weight >= 4 together with their roles;
  - measured CPU per generation.

**Kill and stop rules**
- If the N5 gate fails, run Phase 2 at d0 1.
- If X2 validation fails, run Phase 2 on ABI 3 plus the face weights. X1 does not depend on X2.
- If an arm's median valid F at generation 200 is more than 2 F below C's, stop that arm. Resume makes it cheap to
  revisit.
- If C at d0 0.5 ends with a median F below +3.4 (the pilot's median minus 1.5), fast conduction hurt evolvability.
  Revisit it before any further matrix at d0 0.5.

**Afterwards:** extend the top 4 runs to 1,000 generations (X5), ranked by valid F over generations 480-500 in any arm.
About 100 CPU-h.

## 5. Decisions needed from you

**Q1. Face weights (ABI 4 synapse rule).**
- *What it is:* today a cell has one weight per transmitter channel, the same for every neighbour. Every evolved body
  needed "listen to the cell below, not the cells beside", and built it out of a chemical gradient. That route costs
  about 10% of s5's running cost, and it breaks if the gene clock changes. The proposal lets each channel's weight
  depend on which face the spike arrives through: beside, from below or from above. The cell already knows which
  face; division uses it.
- *Question:* may cells weigh input per channel by arrival face (4 new readout rows, starting at 0 so nothing changes
  until mutation uses them)?
- *Recommendation:* yes.

**Q2. Hidden planes in reactive stages.**
- *What it is:* in SPECK nothing reaches a hidden cell that has not already passed an act cell, so hidden cells have
  no job. They cost about 0.2-0.3 F (s6 0.9) and up to 28% of cell-time.
- *Question:* run reactive stages at L_max 2, and bring depth back when a task needs memory?
- *Recommendation:* not yet. Keep L_max 4 through Pilot 2. It is your design, the tax is small and equal across arms,
  and arm V may change how depth is used. Drop "hidden cells in use" as a SPECK goal, and decide L2 against L4 for the
  scale-up after Pilot 2.

**Q3. What "task performance" means once worlds vary.**
- *What it is:* each life would draw its own world (halo width, noise, target speed, placement range, miss price)
  from a mapped range. Fitness would be the mean over lives, with each world scaled by a fixed constant measured once.
  Base SPECK would always be reported.
- *Question:* may fitness become performance over a family of CATCH worlds?
- *Recommendation:* yes in principle, after Pilot 2 and the niche map. Use fixed per-world scaling, not ranks within
  the population, so cell costs stay linear and the size bound stays physics plus costs.

**Q4. Variety within one life (epochs).**
- *What it is:* the world switches its statistics at random world times (for example, a decoy-rich phase or a
  fast-target phase). Cells still see only their receptors.
- *Question:* approve this direction?
- *Recommendation:* yes, later. It needs a hand-built adaptive body to show the payoff first. The blob-type table
  would later retire b2's six special keys.

**Q5. A wound world (cells lost during the life).**
- *What it is:* each cell has a small chance of dying from outside causes. This gives regrowth, size regulation and
  genome-driven death a job; today no body regulates its size, and stoppers regrow 0-35% of a wound.
- *Question:* approve kill_rate (already a reserved key) as a later family axis?
- *Recommendation:* yes, later. Add the open-edge leak only if regrowth fails.

**Q6. The hotspot cell at (0,0,1).**
- *What it is:* this site is the last designed identity: only that cell can click. One alternative is that any act
  cell may click, with each click priced by c_miss.
- *Question:* keep it?
- *Recommendation:* keep it for now; revisit when c_miss becomes a family axis.

**Q7. The founder prior on the contact-count input.**
- *What it is:* founders get n_view weights 8x wider than other inputs, which helps the growth brake appear.
- *Question:* accept it, documented as a units calibration?
- *Recommendation:* yes for now, and test a uniform prior in natural units at the scale-up.

I will make the following under your standing approval for minor tweaks and report each one: N1-N6, X2 (if its
validation passes) and X3.

## 6. What I am unsure about

1. **Which barrier blocks routing:** time, reachability, or selection and cell economy. D1-D3 are designed to decide.
2. **Whether evolution will use the face weights.** The frozen projections show the evolved wiring can be expressed;
   they do not show that evolution will use the new primitive or that it will route. s5's lateral E/I near-cancellation
   is fragile: a small error in the lateral weight costs about 4 F.
3. **The cause of the clock fragility.** It rests on one body (s5) and one probe. The alternative is that s5's E/I
   balance is fragile to any change in chemistry dynamics. X2's validation tests this.
4. **The selection models.** E2 and purge.py are unvalidated simulations (the sibling-load model was off by about
   100x; the audit's models overpredict 10-30x). The DFE comes from one parent and 40 mutants (non-broken mean
   -0.14 ± 0.08). "Noise is not the bottleneck" is a hypothesis until D3.
5. **Task variety.** It may favour generalist reflexes over size-hungry pooling. The noise-corrected cross-world genetic
   correlation is 0.54 (CI 0.33-0.85), not 0.25.
6. **The compute split.** Ticks are about 45% of CPU on a clean fit, against 68-74% modelled. CPU per life is 0.05 or
   0.1 s depending on machine load. Server-core speed against this laptop is estimated, not measured. The budgets are
   given as ranges for that reason.
7. **The size of the fast-conduction routing lead.** It is untested until N5's re-tune.
8. **Hidden planes.** I do not know whether any reactive task can give them a job; the 3D radius metric is an
   untested idea.
9. **Early size and F.** It is not settled whether early size causes higher F or just reflects earlier income, and
   whether blind newborn claims help the fast bursts. That is why nothing removes them yet.
10. **v1.** If a small-foothold world comes back into the plan, size-adaptive lives and a founder re-screen become
    worth building.

## Appendix: the pre-pilot critique after the pilot

**Supported:**
- ties to parents (evo; fix N1);
- one breed and one attempt per run (evo; the remedy changes to a run-level portfolio);
- the hop costs a full integration window (neuro), and testing faster conduction first (simplify): N5;
- direction is bought through chemistry, and apical-basal polarity (devbio, neuro, evo): X1, but only in a
  per-channel form;
- like-with-like gradient and gene split at ACK (devbio item 6): X2;
- hidden planes have no job in CATCH/SPECK (neuro): Q2;
- gene count fixed at 8 (devbio, evo, simplify): the diagnosis holds; the benefit is untested, so arm G;
- the seeded arms locked out of chemistry (simplify): confirmed, low priority;
- leave the apoptosis prior until a task rewards removal (evo): L3;
- the founder lottery, for v1 only.

**Weakened:**
- parent records and racing: records change fixation probability within noise; racing is about +8% per life and
  unvalidated, so D3 tests it;
- the mixed mutation operator as the default (the DFE on s5);
- the morphogen leak and the energy store as stop fixes: 5 of 10 lineages stop without them, and late growth is
  near-neutral. The leak survives as a regulation cue in L3;
- the founder lottery in SPECK, where the founders were genuine.

**Refuted:**
- pruning a0/a1 and asym (knockouts cost -8.5 to -10 F, and growth runs away);
- retiring chi (used in 2 of 21 bests);
- any face gain shared across channels (s5 -9.6 to -11.8);
- max-normalisation as the noise source: the noise is the phase artefact, and s4's fringe uses the normalisation.

**Partly declined:**
- freezing reference.py at ABI 3. Keep it bitwise for organism rules, because the probe toolkit depends on it, and use
  invariants for world-side features.

**Untouched by the data; still deferred:**
- Notch-like contact input;
- frozen epigenetic gene class;
- taste signal and STDP;
- energy store as an energy-intake design (your deferral);
- second-moment drag.
