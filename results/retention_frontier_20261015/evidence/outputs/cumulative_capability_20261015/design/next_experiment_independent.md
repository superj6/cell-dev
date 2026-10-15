# A small retention and edge-case diagnostic before further evolution

Recommendation: first measure the same three frozen genomes in four fixed environments. Keep the proposed
12-generation AJ continuation held. This is a useful, affordable test of where the accumulated lineage works
and fails; it does not yet test whether another round of evolution can repair a failure.

The three roles should be the exact archived L92 endpoint, its AE L92 row-31 descendant, and AI control's final
rank-zero descendant. Keep all three roles even if bytes coincide. This gives an ancestral acquisition baseline,
the first persistent-target adaptation, and the latest confirmed capture-performing descendant. AI control gained
0.695313 ± 0.127998 captures over AE L92 in its latest persistent-world confirmation, but its F gain was still
mostly economy. Its population median contracted sharply, and the acquisition-performing endpoint is larger
than that median. Neither its endpoint result nor the population archive establishes that all 32 survivors retain
earlier abilities.

| Fixed environment | Purpose | Difference from current persistent world |
| --- | --- | --- |
| Exact archived fast POOL used for L92 | Measure retention of the earlier task | Restore the complete archived world, including its conduction and cue physics |
| Exact V/AE persistent target | Recheck the current capability | None; ABI4 neutral visibility must preserve the old physical values |
| Persistent target with `tau_turn=100` | Nearby change in motion reliability | Only the mean time between turns changes from 200 to 100 |
| Persistent target with renewal visibility `mode=2, on=80, off=5, low=0` | Nearby interruption of sensory evidence | Only the existing four visibility fields change |

Use T1024 and the unchanged physical prices throughout. Do not substitute the stock blink preset: that would
also restore its slower target and turn schedule. Renewal intervals are exponential, so `off=5` means a five-unit
average, not a maximum. The target keeps moving while its target-derived receptor signal disappears; background
events remain. This is implemented by existing ABI4 physics, and no visibility state is supplied to cells. The
renewal schedule is exogenous and asynchronous. It is not a new global clock in the organism.

Measure all 12 genome/world combinations on 256 shared fresh seed IDs: **3,072 research lives**. Freeze the
whole matrix and genotype bytes before revealing any outcome. These four environments become development
cases after this diagnostic, even though the life seeds are fresh. Do not later call an evolutionary gain on these
same settings held-out task generalization. Do not replace an unfavourable genome or world after viewing results.

The two leading estimates are AI control minus L92 captures in ancestral POOL, and AI control minus AE L92
captures in the current persistent world. Report all three lineage differences in every world as well. For each
edge, report both the absolute loss relative to the unchanged persistent world and the per-seed interaction
`(AI - AE)_edge - (AI - AE)_persistent`. Include the analogous AI-minus-L92 contrast as descriptive context.
Compute interactions from paired raw vectors; do not combine SEs as if environments were independent. Equal
seed IDs provide common random numbers, not identical target trajectories or independent evolutionary repeats.

Lead with captures, then net F and its capture-income, ordinary-cost, guard and extinction components. Report
low-light captures, clicks/misses, path, cell counts and live-time as diagnostics. A score increase from lower cost
does not establish retained acquisition. Likewise, a non-significant loss does not establish retention. Report
uncertainty bounds; if a binary retained/not-retained decision is needed, specify an acceptable capture-loss margin
before release rather than choosing it after seeing these data. With 256 lives, marginal differences may remain
unresolved; no automatic sample extension or extra world sweep is justified by that outcome.

Each life should develop from the same genome's zygote under its assigned world, with no weight or genotype
updates. This measures whole-genome transfer, including any developmental response. It cannot by itself show
that an unchanged developed circuit handled the perturbation: body size or cell roles could change. A later
existing-flag freeze/lesion experiment can address that if there is a useful effect. Dark captures can also arise
from previous actuation, coasting or search; they are not alone evidence of memory or prediction.

## Why not choose a different starting organism now?

The cross-world 130-row audit may identify a valuable fixed comparison genotype, but those historical panels
are development data. A genotype chosen for looking good across them needs fresh confirmation and should not
quietly replace a continuing lineage. The smallest first matrix needs only the three lineage roles above. A
shared-panel candidate can be a later explicitly named alternative if it offers a clear capability advantage.
In particular, D90 row54 repeatedly wins by economy; that is not a reason to discard the acquisition-performing
L92 lineage for it.

If a later bounded search is justified, retaining all 32 AI control survivors is the better continuation default
than resetting from one promising panel genotype: it preserves the actual surviving genetic diversity without
inventing new founder mutations. Preserve row order and duplicates, and do not import stale fitness or RNG
state. The existing AJ population loader can do this. However, the full population has not been independently
tested across tasks, so importing it is continuity of material, not proof of capability retention. A fixed endpoint
tested after a short search must still be evaluated directly on the old tasks. Do not launch the current AJ
12-generation same-world plan unchanged, and do not average new/old task scores into a mixed selection objective
without a separate concrete contract.

## Cost and boundaries

The reviewed maximum across 65 historical AE L92 screen rows is 0.202397 CPU-seconds per life; AI control's
persistent confirmation costs 0.069102. Using the former as a provisional floor gives
`180 + 1.5 * 3072 * 0.2023968126875 = 1112.6445` CPU-seconds. This is an estimate, not a bound on how these
genomes develop in another world. A **1,800 CPU-second total hard cap**, one two-thread worker and no retries or
extensions is a reasonable initial proposal, subject to the operations review of the exact retained timings.
The 180-second startup allowance must include every build, numerical-identity golden, validation call and
descendant CPU. The standard identity costs two ABI3 golden lives; these are additional to the 3,072 research
lives. If a per-world calibration is desired, predeclare three genomes × four worlds × two seeds = 24 additional
lives, retain them separately, and count 3,098 total calls. That is an optional resource gate, not permission to
tune the worlds or select candidates from calibration outcomes. Do not silently add it to a 3,074-call contract.

This diagnostic stays within the standing category of minor existing-world constants and measurement; it does
not change cell rules, prices, genotype format, ABI, controller behaviour, or a world in response to a population.
The source explicitly supports the proposed visibility fields. Existing V/X2/AD information-payoff evidence
motivates investigation but does not establish the exact combined world's payoff or isolate a capability there.
An observed organism failure cannot reject that world. Before adding it to selection, separately document its
information-payoff evidence and the intended admission interpretation; do not substitute a hand-built-body gate.
Larger runs, a family/curriculum selection contract, price changes, population-responsive worlds, new organism
channels, new behaviour or a new ABI are not authorized by this note. Root review, a concrete bounded report,
fresh namespace audit and normal release remain separate from this source-only recommendation.

Evidence: `docs/HANDOFF.md` standing requirements/approvals and current generalization clarification;
`docs/TASK_VARIATION_PLAN.md` section 0 and 0.4; `src/life/spec.py` visibility fields and packing;
`src/life/kernel.c` `world_visibility`, `catch_start`, and receptor-rate modulation;
`results/exploratory_reserve_replication_20261014/{analysis_result/summary.json,confirmation/report.json}`;
`outputs/audit_population_depth_20261015/historical_cost_review.json`; and
`outputs/audit_exploratory_reserve_replication_20261014/next_direction_independent.md`.

This review wrote only this note. It selected no seeds, copied no scientific inputs, drew no genotypes, compiled
no libraries, ran no lives, and made no production or frozen-study changes.
