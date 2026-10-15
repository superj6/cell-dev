# AM recorded-operation audit

This offline audit adapts the completed AL audit to AM's two generation-selection prices: `current_value` uses R_cap500 and `high_value` uses R_cap2000. Both use eight initial and eight recheck lives, with the same fixed 50/50 POOL/persistent allocation. Native diagnostics and confirmation keep R_cap500. No organism rules or physical costs change.

After root confirms both searches are complete, execute the prepared wrapper once:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python outputs/audit_capture_value_selection_20261015/genetics/execute_full_audit.py
```

The wrapper refuses an existing `outputs/autonomous_capture_value_selection_20261015/terminal_review/native` destination and checks the prepared sources and both completion markers before copying exact helper bytes and running them. It saves command/environment, stdout/stderr and child CPU/wall receipts. The audit uses one thread and imports no engine, evaluator or numerical-identity runner. It does not make random draws, build libraries or simulate lives.

For a packaged study, the core entrypoint accepts explicit paths:

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 ATEN_CPU_CAPABILITY=avx2 \
  /absolute/repo/.venv/bin/python /absolute/archive/terminal_review/native/audit_native.py \
  --study /absolute/archive --out /absolute/new-output/complete_native_audit.json
```

It reconstructs all 32 imported parents and every recorded offspring across four generations, checks gene origins and every final row against the checkpoint and public population, and verifies both first 256-genome cohorts are identical. Configurations, checkpoints, numerical/source identities, recorded initial/recheck seeds and eight-plus-eight pooling are bound. The ordinary genetic primitives remain byte-identical to AL. The fifteen synthetic tests use small in-memory records, including corrupted operations and old four-plus-four schedules.

Selection checks are deliberately limited: logs retain the ordered 64-genome shortlist and its initial/recheck mean scores, so the audit verifies their score order and pooled top32 survivors. Missing unsuccessful-parent scores and exact tie permutations prevent an independent reconstruction of the entire first-stage top64 ranking. Pooled means are checked with the inherited numerical tolerance because per-life selection scores are not retained. Genetic replay applies recorded operations; it does not regenerate the random stream. Guarded search lives retain their original penalties and recorded aggregate counts. Legacy native `selection_physics=base` describes the disabled envelope, not the generation-world/price adapter; the extended `retention_selection` identity is authoritative.

`full_audit_preparation.json` pins the helpers, provenance and exact synthetic test artifacts. It records source-only preparation, not a result of auditing an actual AM search.
