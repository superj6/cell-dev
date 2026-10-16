# Source-only preparation interface

`prepare_inputs.materialize_inputs(revision)` requires the passed, unreserved block151 audit and exact
completed milestone revision `5d556443e91d558de8de27ab2e5dc7ae11a51415`. It imports no simulator/build
entrypoint and makes no random draw. The caller owns the protocol, reservation, release and runner.

- `inputs/genomes.npy`: float32 `[97,875]`, ordered G8 rows0–31, mean4 rows0–31, pareto4 rows0–31, AO rank0.
- `inputs/rows.json`: rows with index, label, group, local row, native ID, raw SHA and fixed reported-endpoint
  annotation; dimensions, all population identities and original source pins. Repeated genotypes remain rows.
- Exact five ABI6 worlds, production pins, numerical identity and AO normalization constants returned from
  the completed comparison. `inputs/evaluator_config.yaml` retains unchanged physical/extinction accounting.
- `inputs/accounting.py` copies the completed analyzer byte-for-byte. `inputs/patch_truth.json` and
  `inputs/startup_identity.json` support the unchanged four startup calls.
- Each population's actual JSON/checkpoint/config/identity is copied and all32 raw vectors are checked.
  Only mean4/pareto4 final `g003.npz`, endpoint-selection receipt and lineage are copied for cached16 comparison;
  G8 has no comparable per-life capture table. No former synthetic tests or review trees are copied.

The return value has `groups`, `seeds`, `worlds`, `genome_input`, `rows_input`, `config_input`,
`accounting_input`, `expected_numerical_identity`, `extinct_charge`, source/input pins and reference scales.
`materialized_inputs.json` records this result. Creating it does not reserve or release anything.

The namespace scanner uses the preceding accepted inventory and its referenced cache, then visits the
current results/outputs trees. It reopens each distinct unchanged seed payload and reads every changed/new
NPZ's seed members, including completed comparison and viewer files. JSON and text hits are retained for
explicit classification against actual numeric IDs; an old block label alone establishes no collision.
Own prospective source is excluded. The scanner produces no passing receipt until a separate literal review.

Proposed scan command, **not executed**:

```sh
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /usr/bin/time -v -o outputs/resource_patch_population_20261015/namespace/resources.txt \
  .venv/bin/python outputs/resource_patch_population_20261015/namespace/audit_namespace.py --run \
  > outputs/resource_patch_population_20261015/namespace/stdout.json \
  2> outputs/resource_patch_population_20261015/namespace/stderr.txt
```

The scanner enforces40CPU/60wall seconds,2GiB address space, one CPU affinity and4GiB host headroom.
This is within the proposed60CPU/60wall preparation-plus-terminal allowance; external timing includes startup
and subprocesses. Hold execution for root's source review and authorization. No scientific calls, builds,
random draws, input materialization or reservation have occurred during this preparation.
