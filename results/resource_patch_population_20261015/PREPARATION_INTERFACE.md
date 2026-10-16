# Preparation interface and audit record

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

Historical proposed command, subsequently reviewed and executed once:

```sh
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /usr/bin/time -v -o outputs/resource_patch_population_20261015/namespace/resources.txt \
  .venv/bin/python outputs/resource_patch_population_20261015/namespace/audit_namespace.py --run \
  > outputs/resource_patch_population_20261015/namespace/stdout.json \
  2> outputs/resource_patch_population_20261015/namespace/stderr.txt
```

The scanner enforced40CPU/60wall seconds,2GiB address space, one CPU affinity and4GiB host headroom.
It examined95,830 NPZ paths, reopening901 distinct unchanged seed payloads, and found no candidate seed
collision. Its177 unreadable files were retained in the original inventory and individually classified as
unchanged historical synthetic placeholders/corruption fixtures with exact prior stat records and literal
7–55-byte contents. The classifier also resolved24 JSON and32 text references, including exclusive bounds,
an older43million-base block label, artifact counts and comma-separated atlas indices.

External scan accounting:10.20CPU/10.25wall seconds,243,636KiB peak RSS. The reviewed classifier passed on
its first execution under5CPU/10wall-second bounds:0.63CPU/0.64wall seconds,174,416KiB. Combined external
usage was10.83CPU/10.89wall seconds. Both runs and all original scan errors remain recorded under `namespace/`.
The passing unreserved audit SHA256 is `68f48ac3c2dffeb487c000f4ff9b7ab0d65f723a3b8029392549c4cf479a34b9`.

Root subsequently materialized the reviewed inputs and reserved development-only block151 in protocol
`6fb2a4f9744ff15377346bde4b2d7af42a7e12087e5f9d2d9cc622af7a5ee33f`.
No scientific/startup lives, builds or random draws occurred in this preparation. The earlier source-only
note is retained in `preparation_history/pre_public_note/`.
