# Independent review: the smallest useful next step after AK

I recommend the single matched four-generation continuation, with the limits below. AK found a concrete loss of old acquisition ability: AI-control caught 38.6% fewer ancestral POOL targets than L92, despite improving on persistent targets and its nearby variants. Comparing continued persistent-only selection with fixed POOL/persistent selection directly tests a plausible cause of further forgetting. Starting both arms from all 32 AI-control survivors preserves the existing population; a new panel around rank zero would test a narrower neighborhood.

This review covers the proposal in `selection_pilot.md` plus the root-approved draft revisions: a fixed 10% persistent-capture margin, confirmation on POOL, persistent, blink80_5 and the previously untested turn100+blink80_5 combination, and the conservative timing rate 0.2041540474 CPU-seconds per life. These are proposed terms, not a release or registration.

## What the cheaper panel could establish

Parent plus 64 ordinary mutants on 32 lives in each of two worlds, followed by parent and one frozen winner on 512 fresh lives per world, costs **6,208 research lives**, plus startup checks. It is the cheaper choice if the immediate question is only whether one nearby mutant improves both tasks. It does not retain the 32-parent population, test accumulation, or isolate how changing selection affects forgetting over generations. A negative panel would not establish that joint improvement is inaccessible.

Merely measuring both worlds needs no family-fitness change. Choosing a winner using their average, a Pareto rule or a capture-retention constraint is a two-context selection decision even if no breeding loop follows. It is not an approval workaround. HANDOFF section 5 explicitly leaves **“raw-F family fitness”** open. Both proposals therefore need a clear decision if joint performance determines which genome advances. I prefer one bounded continuation to another isolated-mutant diagnostic here; do not run both automatically.

## Keep the verdict about acquisition

The 50/50 mean F is minimal pressure to keep the old task relevant, not a retention objective. AK's measured two-world means are approximately **2.3847 (L92), 2.5926 (AE) and 2.4217 (AI-control)**. The average can reward cheaper bodies while allowing large capture losses. Unchanged prices make that a legitimate score outcome, but not progress toward the user's acquisition goal.

Keep mixture-minus-control POOL captures primary, and show both endpoint-minus-AI-start effects in each training context. A positive mixture-minus-control effect alone could mean the control deteriorated. Useful partial recovery requires increased POOL acquisition relative to the starting genome as well, accompanied by the predeclared persistent diagnostic: the paired three-SE lower bound of `mixture − 0.9 × AI-start` captures exceeds zero. That 10% allowance is conventional; it permits some loss and must not be called lossless retention. An unresolved difference is not retained ability. With no fresh L92 role, this study cannot establish recovery to the ancestral level.

The combined turn-and-occlusion case is a useful small transfer test. Keep it out of selection and endpoint choice; after disclosure it becomes a development case. Success there would concern this one combination, not broad generalization, temporal memory or a more complex circuit. Whole-genome development and actuation can explain the effects.

## Cost and inference limits

The proposed **13,388 research / 13,396 total calls** correctly include the three standard identity pairs and the ABI 4 truth pair. The conservative rate projects about **3,339 CPU-seconds for search and 1,121 for confirmation**, including the stated margins, within the 3,600/1,800 phase allocations and 5,400 total cap. Mutated descendants can be slower; retain an incomplete result rather than extending the cap.

Matched first offspring, unchanged genetics and equal evaluated-life budgets make this a useful policy comparison. They do not equalize CPU cost, world difficulty or score variance. Later populations and random-stream consumption may diverge. There is one paired evolutionary realization; 256 confirmation seeds estimate its endpoint effects, not policy reliability across evolution runs. Report captures, income and all costs together, then decide whether further work is justified.

No simulations, genetic draws, policy changes or registration were performed for this review.
