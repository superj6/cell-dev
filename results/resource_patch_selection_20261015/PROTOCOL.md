# Matched resource acquisition selection comparison

This bounded exploratory study tests whether preserving useful partial acquisition variants helps one
evolved organism retain and combine abilities. The preceding eight-generation mean-F pilot improved economy
but did not establish increased patch acquisition; POOL and reserved-combination acquisition declined.
This study changes reproductive selection. World physics, prices, genome, local asynchronous cell rules,
crossover and mutation remain fixed. No controller, behavioral sequence or population-responsive world is added.

## Starting material and matched arms

Both arms import all 32 ordered survivors of the completed resource-patch generation-eight population.
All 875 float 32 parameters and row order match its checkpoint. IDs remap to 0..31; fitness and native RNG start
fresh. This preserves genes, not the prior random stream. Native seed 53235 and all draw IDs are shared between
arms. Their initial candidate genomes match; subsequent parents and therefore genetic draws' consequences
can diverge. One matched pair does not establish reliability across independent evolutionary searches.

Each arm runs exactly four generations with 32 parents+224 offspring, ordinary crossover and two scaled point
additions per offspring. Duplication/deletion remain disabled. Both use identical eight-life exposure:
`patch, POOL, patch, persistent`, repeated twice. Top 64 candidates receive eight additional lives with the same
allocation, yielding 8 patch/4 POOL/4 persistent lives. All worlds last 1024 and retain original physical prices.
No adaptive resampling, exposure changes or cap extensions occur.

The `mean` arm uses ordinary mean production F at both 256→64 and 64→32 selection stages. Production F is
native physical F minus the ordinary extinction surcharge; invalid-life handling remains native. The `pareto`
arm instead ranks four maximizing objectives: mean captures separately in patch/POOL/persistent, and mean
production F across all lives. A candidate dominates another if it is at least as good on every objective and
strictly better on at least one. Successive nondominated fronts rank first. Within a front, normalized crowding
favors distinct outcomes; equal coordinate groups receive equal contributions, constant coordinates zero,
and each boundary group infinite crowding. Exact duplicates remain tied; excess boundary candidates are
resolved by the supplied native tie permutation. This deliberate rule can retain specialists or noisy extremes.

Both shortlist and survivor stages use their arm's rule. The final stage recomputes objective vectors from
all 16 lives, rather than averaging nonlinear rankings. The ordinary pre-recheck permutation of 256 candidates
and recheck permutations of 256 and 64 retain the native tie-generator schedule in both arms. No mutation RNG
is consumed by objective calculation. Selected `fitness` and `trial_scores` remain ordinary F; Pareto order is
not mislabeled as fitness. Selection captures, F, identities, seeds, ranks and decisions are retained for replay.
Invalid/capacity/mismatch source rows stop interpretation; guards and extinctions retain ordinary accounting.

In the Pareto arm, native rank-zero curves and final diagnostics describe the first selected row, not the
highest-F or common-rule reporting genome. The native pre-recheck body comparison still uses scalar-F order;
`recheck_changed` instead compares survivors with the arm's own first-stage order. Retained selection arrays
make these distinctions explicit; confirmation of the separately fixed joint genome is the scientific result.

## One common fixed endpoint per arm

After generation 4, choose one reporting genome from each final 32 using only their already returned 16-life
selection records. Maximize the minimum of the three per-domain capture means divided by fixed original-AO
reference means `[19.046875,16.029296875,5.919921875]` in patch/POOL/persistent order. Break exact ties by ordinary
aggregate F, then ascending native survivor ID. Apply this same rule to both arms, without restricting either
endpoint to a Pareto front. No extra tie draw or endpoint-evaluation life is added.

Export `joint_genome.json` and a receipt binding all 32 candidate vectors, IDs, chosen row and source checkpoint.
Keep the native rank-zero genome/diagnostics explicitly separate. This common endpoint rule can amplify
selection noise and gives cost little influence when acquisition differs; fresh confirmation must expose both
problems. A collection of specialists is not evidence that one organism generalizes.

## Fixed confirmation

Four unchanged genomes—original AO, preceding patch 8 rank 0, mean 4 joint and pareto 4 joint—each face 512 common fresh
lives in five worlds: trained patches, POOL, persistent pursuit, longer cue gaps, and one newly reserved patch
combination. The new combination changes only count 2, radius 3.5–5.5 and refill 60/180 from the training patch world.
The previous count 4/radius 3–5/refill 100–200 combination is now revealed development evidence and is not reused
as unseen transfer. Confirmation seeds 52500000..52500511 are disjoint from all 100 native life IDs and recorded
earlier lives. The whole half-open block[52500000,52510000) is reserved. Older harness block 150 has a different
43 million base; the audit binds its disjoint actual seed range rather than trusting block labels.

Primary contrast is pareto 4−mean 4 on patch acquisition, alongside refill origin, productionF, empty attempts
and all physical costs. Also report each final endpoint against both ancestors, plus priorpatch 8−AO as
descriptive context. Old-world 90%capture retention against original AO remains a paired diagnostic, not a
selection constraint or admission gate. Report absolute and paired mean±SE over lives, descriptive 3 SE bounds,
all guards/extinctions, total/initial/refill food, missed attempts, tissue and every cost component. Ratios of
mean capture are point estimates only. Neither endpoint can be replaced using confirmation or transfer results.

## Calls, resources and completion

Per arm:4×(256×8+64×8)=10240 selection calls; nativevalidation at zero-basedgenerations 0 and 3 adds 32; ordinary
final diagnostics add 6, including 2 growth lives atT 512. Thus each search has 10278 research+4 startup=10282 calls.
Both searches total 20556 research+8 startup. Confirmation has 4×5×512=10240 research+4 startup. Complete maximum:
**30796 research+12 startup=30808 calls**. Startup per phase is the retainedABI 3 golden full/fast identity pair and
ABI 6 patch full/fast truth pair. No midpoint lives, new founder search or extra endpoint scoring occurs.

The package allocation is 5400 CPU /3600 wall seconds, including 120 CPU /120 wall for preparation and terminal work.
Monitored execution gets 5280 CPU /3480 wall; both searches together get 4080 CPU, preserving 1200 CPU for confirmation
and cleanup. Run one owned worker at a time with two kernel threads,4 GiB combinedRSS stop,8 GiB address space,
4 GiB available-host reserve and 10 seconds cleanup margin. Work stays under this `outputs/` study directory.
No money or rented compute. A partial run is preserved rather than automatically retried, topped up or reduced.

Before release: review and run meaningful supplied-array adapter/reader checks, audit seeds, bind all exact
inputs/sources/numerical identity, publish this prospective protocol and report the budget. Terminal work
reconciles all 20 raw/scored batches, confirms selection/genetic records, reports complete costs and outcomes,
archives failures if any, verifies worker cleanup and publishes the fixed results. This is exploration under
the explicit plan revision; it claims neither formal information-payoff admission nor memory, visit order,
learned replenishment timing, broad generality or superiority to handwritten programs.
