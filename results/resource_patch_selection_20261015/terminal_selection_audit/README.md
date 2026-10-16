This independent saved-data audit is prepared before terminal outcomes are read. Run it only after the
parent reports the scientific study complete. It imports neither the registered selector nor any repository
execution module. Torch is loaded only to decode a pinned checkpoint with `weights_only=True`.

Front depth is computed by a lexicographically ordered dominance DAG traversal. Crowding is recomputed
using scalar equal-value groups, and Python tuple sorting determines the two stage orders and the common
joint endpoint. NumPy means retain registered floating-point rounding; a separate scalar `math.fsum`
calculation bounds aggregate-F roundoff. No ranking or endpoint helper is reused from study sources.

Coverage: both arms, four generations, two stage rankings per generation, all three recorded tie
permutations, all 20,480 selection lives, final32 endpoint candidates, exact genome/ID ordering, initial
parent bytes, and equality of all first-generation candidate genotypes between arms. Native genetic replay
and full per-life physical accounting remain separate audits. Merely checking recorded permutations does
not regenerate or prove the native RNG stream.

After terminal readiness, the bounded saved-data command is:

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  .venv/bin/python outputs/resource_patch_selection_20261015/terminal_selection_audit/audit_selection.py \
  --run --out outputs/resource_patch_selection_20261015/reviews/independent_selection.json
```

The parent supplies external CPU/wall/address-space limits and `/usr/bin/time` logging. An absent receipt
path is required. Failure logs must be retained; there is no automatic retry or source amendment. The
`--self-test` branch uses seven literal fixtures, does not import Torch, and reads no study files.
