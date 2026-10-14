# Copied-gene connections during the completed structural searches

The two final copied genes had no measured knockout effect in J/M. Carriers of those copied-gene origins nevertheless include
variants with nonzero coefficient paths to cell-property readouts. Final neutrality does not mean that the
mutation operators never connected copied genes to the rest of the genome.

This descriptive audit reconstructs every offspring and survivor in the two completed G searches. A path
starts at an active copied gene, follows nonzero regulatory coefficients through active genes, and ends at
one of the 23 phenotype readouts. Both positive and negative coefficients count as edges; no small-weight threshold is used. A path describes
potential coupling; it does not show that the gene state changes the decoded property in a reachable life,
or that any resulting change improves fitness.

| Recorded quantity | G51089 | G51090 |
|---|---:|---:|
| Duplication events | 73 | 71 |
| New origins retained in their birth generation | 5 | 14 |
| Origins ever having an offspring with a readout path | 4 | 11 |
| Origins ever having a retained carrier with a readout path | 2 | 7 |
| Offspring copy-carrier observations | 804 | 3,309 |
| Such observations with a readout path | 256 | 1,336 |
| Survivor copy-carrier observations | 120 | 520 |
| Such observations with a readout path | 37 | 193 |

These are counts of related genomes and repeated carriers, not independent trials or estimates of positive
selection. A candidate with several copied genes contributes several carrier observations. The same survivor
can appear in multiple generations. Crossover can transfer, combine or erase paths; an innovation ID names a
gene's ancestry, not the ancestry of every outgoing coefficient.

G51089's final copy, slot 14/origin 56, has no outgoing route to a readout, matching M's disconnection proof.
Across its earlier carrier descendants, 12 of 90 offspring observations had such a route, and one was retained.
G51090's final copy, slot 9/origin 21, reaches only readout 6 (emit1), matching M's bounded-state analysis;
783 of 1,406 offspring observations of that origin had a route. Its final tested ledger/fitness effects
remain zero on J/M's registered lives. Intermediate genotypes were not tested for fitness dependence here.

The complete record preserves each innovation, offspring and survivor observation, plus every opportunity
for point mutation in an inherited copy carrier. Point mutations occur before duplication and deletion;
a newly duplicated gene is not point-mutated again in that offspring. A carrier counted before those structural
operations can subsequently be deleted. Incoming/private changes are separated from direct readout and
other-gene outgoing changes. None of these counts diagnoses the reason a variant survived.

All raw final genomes and origin matrices match the archived populations exactly; per-generation origin
registries also match. Independent review checks 8,194 genome observations and 4,755 copy records using
packed coefficients and a separate transitive-closure implementation, plus 944 synthetic graphs. Seven
additional semantic tests cover edge direction, signs, multi-hop routes, inactive intermediaries, self-loops,
exact zeros and inactive-copy rejection. No new lives or active-study outcomes were used.

From the repository root, using Python and NumPy only:

```sh
OPENBLAS_NUM_THREADS=1 .venv/bin/python results/copy_connectivity_20261014/analyze.py \
  --out outputs/copy_connectivity_reanalysis
```

The analyzer checks the original G archive's manifest and every artifact, and pins the existing portable
genetic replay helper in the reviewed weight-update analysis bundle. This is completed-data analysis only;
no new knockout study was prepared or launched before the user's wrap-up request.
