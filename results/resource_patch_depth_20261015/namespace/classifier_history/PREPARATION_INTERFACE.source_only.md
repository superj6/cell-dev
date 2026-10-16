# Exact depth-study preparation interface

Source-only preparation against completed milestone `1a7f38bd3222bacf27367fd99998d87776c34ec5`. No namespace scan, reservation, input materialization, build, simulated life, or genetic draw has occurred in this preparation.

`prepare_inputs.materialize_inputs(revision)` verifies that exact revision, a passed unreserved namespace audit, complete public source manifests, and unchanged production files before writing an exclusive `inputs/` directory. Root owns configuration, protocol, reservation, and execution. The function returns `population_start`, reference records, source/input pins, six world records, three selection-world definitions, native and panel seed lists, the prior numerical identity, and accounting/startup helper paths; the complete result is also written to `materialized_inputs.json`.

All 32 ordered Pareto4 rows are decoded from the published population and checked byte-for-byte against its generation-4 checkpoint and the completed population panel. New IDs are `0..31`; original IDs and row hashes remain in `population_start.old_to_new`. The checkpoint is evidence of source rows; its RNG state is not installed into the new search.

The three references are ordered `AO`, `G8_joint`, `Pareto4_joint` in `inputs/references.npy` (raw float32, shape `[3,875]`) and `inputs/references.json`. Their source panel indices/native IDs are `96/5336`, `20/1795`, and `90/918`. Each record includes its source group/local row, raw hash, standalone genome path/hash, and prospective-comparator annotation. The importer verifies these rows occupy first place in the prior development-only joint ordering. This is a new-study comparator choice; historical endpoints and claims remain unchanged.

The first five worlds are exact copies of the completed panel: `patch`, `pool`, `persistent`, `blink80_20`, and `transfer`. `reserved_capacity3` changes only trained-patch count to 4, capacity to 3, placement radii to 2.5–4.5, and refill periods to 60/180. Source inspection of ABI6 validation permits these values: four slots, positive capacity, `R_min >= 2*rho_c`, ordered refill periods, and only 76 possible source events under the validator's bound. Materialization will invoke the existing validator and pack 82 world fields with 107 ledger columns. Physical prices remain unchanged.

Only necessary scientific inputs are copied: the full population/checkpoint/config/identity, small prior manifests, three reference genomes and the compact array, unchanged startup truth/identity, and the validated accounting reducer (`0ac39bb7b11a754f73acff2b77c0690ce4b525b688664da34cc6006b9da1373b`). The completed 97-row panel, its summary, and complete source archives are checked through their public manifest hashes rather than duplicated.

The namespace scanner reuses the latest public population inventory only for stat-to-payload membership. It reopens every distinct unchanged seed payload and inspects all changed/new NPZ seed members, including the completed panel and viewer. Candidate whole blocks are `[52520000,52530000)` and `[52530000,52540000)`; actual endpoint and confirmation panels use 32 and 512 IDs respectively. Native seed `53236` yields 564 unique life IDs: 512 generation IDs, 48 held-out IDs at generations **0, 4, 7**, and four final IDs. The 54 native diagnostic calls include two half-duration repeats of the first final pair. Pure source extraction derives the IDs without importing the engine or drawing randomness. The classifier rejects unclassified declarations/errors and distinguishes older 43-million-base block labels from actual 52-million IDs.

Proposed command, pending root review and explicit scan release (one CPU, 40 CPU seconds, 60 wall seconds, 2 GiB address space, at least 4 GiB host headroom; no reservation):

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -v -o outputs/resource_patch_depth_20261015/namespace/scan_resources.txt timeout 65s /home/jgon/project/ml/cell-dev/.venv/bin/python outputs/resource_patch_depth_20261015/namespace/audit_namespace.py --run > outputs/resource_patch_depth_20261015/namespace/scan_stdout.txt 2> outputs/resource_patch_depth_20261015/namespace/scan_stderr.txt
```

After the single scan, inspect literal hits, finalize their classification, and run only that classifier under a separately logged small bound. No automatic rescan, materialization, or release follows.
