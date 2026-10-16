# Pure selection module: source-review candidate

`pareto.py` and `tests/test_pareto.py` are prepared, not executed. This note does not freeze a study protocol.
No simulator, build, torch or RNG API is imported by the selector. All arrays are supplied by its caller.

The objectives are patch, POOL and persistent capture means (each within its domain), followed by ordinary
production F averaged over all lives. All four maximize. Production F must already include the established
extinction/invalid-life accounting. Physical prices are unchanged. Guard/extinction rows are not discarded.
Nonfinite values and negative/fractional capture counts raise, rather than silently affecting selection.

- `objective_vectors(captures[N,L], production_f[N,L], domains)` returns `[N,4]`; the fixed eight-life pattern is
  `(patch, POOL, patch, persistent)` repeated twice.
- `rank_objectives(objectives[N,4], tie_order)` returns `Ranking` with objective vectors, zero-based front ranks,
  crowding, full local order, and supplied tie order. `.audit()` produces strict-JSON-safe metadata.
- `rank_mean(production_f[N], tie_order)` reproduces native stable scalar ordering from an already drawn permutation.
- `select_shortlist` enforces 256 candidates × eight lives and selects 64. `select_survivors` enforces the 64-row
  mapping, concatenates selected base eight and recheck eight lives, recomputes objectives, and selects 32.
  The integration adapter may instead call the lower-level functions on its already pooled raw arrays.
- `select_endpoint(objectives[32,4], candidate_ids[32])` maximizes the weakest capture fraction relative to fixed
  AO means `(19.046875, 16.029296875, 5.919921875)`, then ordinary F, then unique survivor ID ascending.
  It considers all 32 survivors, draws no tie randomness, and returns one row plus complete endpoint audit data.

Dominance requires at least equality on every objective and strict improvement on at least one. Front rank
precedes crowding. Crowding is normalized separately by each coordinate's range within that front. A constant
coordinate adds zero. Equal coordinate values are grouped: all points in an interior group receive the same
adjacent-distinct-value gap; every minimum/maximum group gets infinite distance. Thus duplicate objective vectors
have equal rank/crowding, including at boundaries. If more infinite-distance points exist than available places,
the supplied tie permutation selects among them. No hidden deduplication or secondary acquisition/F tie exists.
Repeated boundary objective vectors can therefore occupy multiple places; neutral genotype diversity is retained.
This explicit grouped-coordinate rule differs from implementations assigning boundary privileges arbitrarily
within a stable sort. Infinite crowding is serialized as null plus a corresponding `crowding_infinite` flag.

Integration must preserve the native three tie draws per generation: diagnostic256, shortlist256, survivor64.
The module draws none. Final endpoint ordering uses existing genome IDs and must not reorder the evolving population.
`LifeEval.fitness` stays ordinary F. Raw per-life capture/F/status observation is necessary because its aggregate
capture field cannot reconstruct domain means. Final selection uses all sixteen raw lives; ranks, crowding or
per-stage minimum fractions must never be averaged. Endpoint export is separate from the native best-genome export.

Prepared tests cover exhaustive small dominance layers; duplicate/zero-range/crowding boundaries; cutoff ties;
permutation equivariance; positive affine scaling; extreme finite ranges; both 256→64→32 stages and original-row
mapping; an example where averaging pre-pooling minimum fractions chooses the wrong endpoint; exact AO scales and
ID ties; ordinary control ordering; input immutability; strict JSON audit output; malformed shapes/counts/labels,
NaN/infinity, and invalid permutations/IDs. They use only literal or deterministically constructed arrays.
