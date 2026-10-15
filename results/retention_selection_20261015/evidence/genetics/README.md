# AL recorded-operation audit

The study-local `native_replay.py` reconstructs all 32 imported parents and 224
first offspring from logged crossover masks and float32 point additions. It checks
that both arms began with identical candidate bytes before confirmation. It makes
no random draws and runs no lives.

After both searches complete, run the separate full audit:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  outputs/audit_retention_selection_20261015/genetics/audit_native.py \
  --study outputs/autonomous_retention_selection_20261015 \
  --out outputs/audit_retention_selection_20261015/genetics/complete_native_audit.json
```

This reconstructs all four generations and verifies every final genome and gene
origin against the checkpoint and public population. Ordinary selection checks use
the logged 64-candidate shortlist and its four initial/four additional life scores.
The old helper's five genetic functions are unchanged; its selection checks change
only the initial-life count and corresponding pooling weights.

Native records omit some unsuccessful parents' initial fitness and exact tie
permutations. Therefore this audit cannot independently reconstruct the entire
first-stage top-64 ordering. It checks the recorded shortlist's score order and
pooled top-32 survivors; it does not claim more. Genetic replay uses recorded
operations, not regenerated RNG draws or new fitness evaluations.

The twelve synthetic checks run entirely in memory. No actual search output has
been analyzed during preparation. `full_audit_preparation.json` pins the reviewed
source, tests and source-reuse evidence.
