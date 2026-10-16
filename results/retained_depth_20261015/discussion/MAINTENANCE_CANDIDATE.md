The cleanest candidate is a study-local **maintenance credit during selection**, keeping every physical world—including its original `c_live`—unchanged. This is an alternative for review after AO, not a selected next study or an optimal-price recommendation. No AO outcomes were consulted.

For each life, let `F0` be the existing production score after its original guard, extinction and invalid-life treatment; `L` is counted `live_time`, `W = T − t_open`, and `c0` is the unchanged world’s maintenance price. For a fixed, predeclared maintenance multiplier `m`:

```text
valid life:   F_selection = F0 + (1 − m) × c0 × L / W
invalid life: F_selection = F0
```

Use `0 ≤ m ≤ 1` for this candidate. Guarded or extinct valid lives receive credit only for their recorded living time. Their original guard charge and extinction penalty remain intact; invalid lives retain the original `−c0 × n_max` floor and receive no credit. Never credit time after death or a guard. All other costs and capture value stay fixed. AN’s nine repriced rows had status zero, so its maintenance sensitivity also describes this formula for those trajectories; future guarded/extinct lives distinguish the two interventions.

The narrow insertion point is a study-local wrapper around [`LifeEvaluator.columns`](../../../src/life/evaluate.py:247): call the original method, preserve its raw/accounting columns, and replace only the selection `F` array for eligible draws. [`_eval`](../../../src/life/evaluate.py:273) then derives both `fitness` and `trial_scores` from that array. This matters because [`pooled`](../../../src/evolve.py:345) rebuilds recheck fitness from concatenated per-life trial scores; modifying only mean fitness would implement an inconsistent policy. Keep reported `score`, `energy`, `net`, and `F_kernel` at original prices, and explicitly label native fitness as the credited selection score. It will no longer equal original-price `score − energy`; retain the baseline/credit distinction in reporting.

`LifeDraw` has no purpose field. Add only a study-local Python draw tag for `purpose='gen'`, preserved by `dataclasses.replace` when [`recheck_draw`](../../../src/evolve.py:331) slices the fresh suffix. Do not infer eligibility from world names. Nonselection validation, tiny finals and startup checks remain unmodified. This requires no C/ABI change, extra RNG draw, controller input or life. Pin the credit rule, multiplier and wrapper in the search/checkpoint identity. Leave ranking, pooling, ties, mutations and world allocation unchanged. An `m=1` fast path should return the original result exactly.

The necessary checks are small:

- Exact control equality and unchanged seeds, worlds, tie/genetic streams and calls.
- Synthetic normal, guarded, extinct and invalid rows: credit only actual counted maintenance; original penalties remain unchanged.
- Both initial and recheck draws use the policy; pooled scores equal concatenated credited trials; other purposes remain original-price.
- Independent raw reconstruction reconciles original F, credit and selection F, including a zero-living-time case.

Freeze both endpoints before fresh, shared-seed confirmation under the original scorer, with no credit. Report captures, original F, maintenance and other costs, body size, and old-capability retention separately. A larger body or higher credited fitness alone is not acquisition or sophisticated computation. This deliberately changes the selection objective despite unchanged dynamics; it needs a distinct study contract and must not be described as ordinary original-F evolution. No implementation, registration, input copying or simulation is authorized by this note.
