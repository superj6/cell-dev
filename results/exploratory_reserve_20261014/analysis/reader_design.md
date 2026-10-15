# AH independent reader design — source-only, unbound

No protocol, study inputs, stage IDs, new genetic draws, compiled libraries or
lives are created by this work. The unchanged AF ABI3 accountant and ordinary
recorded-genetics helper are retained, with the original AF reader, native audit
and selection helper saved under `analysis/history/`. The producer schema is
being coordinated before implementation; the list below describes requirements,
not an invented final serialization contract.

The study has one fixed AE L92 start and two four-generation searches: ordinary
control and the exploratory reserve. Both use the same initial population,
native RNG seed and life draws. The first 224 offspring plus 32 parents must be
reconstructed byte-for-byte and matched before selection. Subsequent cohorts are
not expected to match. Final generation 3 is ordinary in both arms. Confirm the
start and both completed final population-rank-zero endpoints on the same 512
fresh lives, including duplicate roles. Counts are 8,268 native calls plus 1,536
confirmation calls and exactly three standard two-life identity checks: 9,810
total. Search diagnostics have native summary coverage; only the three final
confirmation rows have full raw 57-column ledger coverage.

The new audit is concentrated on the policy:

- Recompute the two distinct fresh-child lottery positions with an independent
  SHA256/rejection-sampling implementation once the producer's exact byte format
  is fixed. Eligible positions are the 224 newly created children only. No F,
  genotype, ancestry or body property enters the draw. Generation-keyed external
  state must not enter cells or alter the native genetic/tie RNG streams.
- Verify all 256 candidate IDs and initial F values against child/parent records;
  verify full ranking permutations, finite values and nonincreasing F. Preserve
  the native diagnostic, initial recheck and pooled rank call counts and sizes.
  Tied candidates follow the recorded native ranking, not a new index tie rule.
- For treatment generations 0–2, the recheck set is the two protected offspring
  plus the best 62 unprotected candidates, ordered by the complete initial
  ranking. Its survivors are the two protected plus the best 30 others, ordered
  by the complete pooled ranking. Verify both exclusions, no duplication, equal
  seven-life pooling and rank-zero fitness. Ordinary control/final selection must
  reproduce the original native recheck behavior exactly.
- Metadata must live in the existing checkpoint-covered lineage records. Validate
  complete checkpoint log hashes/lengths and all ordinary genetic replay. Bind
  the external adapter, driver and policy hashes through both config and extended
  checkpoint identity; the base numerical identity alone only pins `src`.
- Reconcile the prospectively matched first cohort independently, every final
  genome and the fixed three confirmation roles. Preserve guard/extinction
  charges and reject invalid/nonfinite or incomplete evidence. All first-attempt
  resource and four-field process-identity checks reuse the reviewed AF path.

Primary comparison is reserve minus control; both endpoint-minus-start contrasts
remain. The unchanged AF accountant supplies 73 paired vectors per contrast,
including physical quantities and capture/cost/guard/extinction decomposition:
219 vectors across the three pairs. No low-light column exists in ABI3. Retain
all signs. Paired 512-life uncertainty concerns fixed genomes, not policy
reliability across evolutionary searches.

Focused tests should target the new lottery and exclusion rules, protected
children already inside the ordinary cutoff, exact ties, inactive/final behavior,
rank ordering, bad metadata and adapter identity omissions. Reuse existing
accounting and lifecycle tests/evidence rather than duplicate large fixture
trees. Recorded ancestry can show descent from a protected child; it cannot prove
that protection was a necessary stepping stone or reconstruct unevaluated
ordinary counterfactual recheck scores.
