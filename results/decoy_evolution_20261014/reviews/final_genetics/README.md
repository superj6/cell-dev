U recorded genetic replay passed for both completed four-generation searches.

The audit reuses the frozen G genetic replay helper and L selection helper. Each run's prospective 32-genome initialization, 896 sexual offspring, full final population, gene origins, checkpoint logs, source/configuration pins, and saved numerical identity receipts agree. The seven-life pooled shortlist selection and final rank-zero identity also agree. Both rank-zero genomes match the already-frozen confirmation metadata.

This is an offline integrity check. It executes no life simulations or numerical goldens and reads only `confirmation/endpoints.json` and `confirmation/genotypes.npz` from the confirmation directory. It does not read or judge partial confirmation outcomes. Search invalid/mismatch summary fields are zero in both runs. Full per-life search ledgers were not retained, so this check cannot reconstruct their costs or every recheck guard life. Recorded inheritance and mutations are replayed; random-number draws are not replayed.

The only adaptation to the reused L selector check supplies the pinned fixed T1024 to an in-memory copy of the U logs, which omit constant duration. No study artifact is edited. Eight targeted checks pass, including rejection of corrupted final genomes/origins, invalid parentage/crossover, structural operators, inconsistent pooled selection, and conflicting duration.

Run from the repository root:

```sh
.venv/bin/python outputs/audit_decoy_evolution_20261014/final_genetics/audit.py
.venv/bin/python outputs/audit_decoy_evolution_20261014/final_genetics/test_audit.py
```

`receipt.json` records every input hash, helper/source pins, detailed per-run checks, and limitations. `tests.txt` records the eight checks. The receipt's CPU count covers the audit process after imports, not the separate unit-test run.
