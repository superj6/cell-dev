# Resource-patch evolution — complete

Eight ordinary generations from all 32 AO survivors improve trained-patch fitness **0.595798 ±0.161773 F**,
mostly through lower costs. Food acquisition gains remain unresolved; POOL and reserved-combination food
acquisition decline. No new cumulative resource-allocation primitive is demonstrated.

- [Results and interpretation](REPORT.md)
- [Complete comparison tables](TABLES.md)
- [Frozen scientific design](PROTOCOL.md)
- [Independent accounting](reviews/independent_accounting.json)
- [Recorded-genetics replay](native_replay_result.json)
- [Original prospective README](registration_history/README.md)

All 28,222 calls complete in 1724.714517 CPU seconds with peak owned RSS 359.39 MiB. All 7,680 confirmation
statuses are zero and owned workers are cleared. The archive preserves raw/scored batches, fixed endpoints,
full populations, checkpoints, source/input pins, startup evidence, original registration and the zero-call
launcher correction. It does not replace the fixed generation-eight endpoint with the midpoint.

Verify artifact hashes and terminal bindings without simulation:

```sh
.venv/bin/python results/resource_patch_evolution_20261015/verify.py
```

The verifier checks provenance and complete counts; the retained independent audit supplies the arithmetic
checks. Fast confirmation hashes are constants, not trajectory evidence. This is one continuation with 512
fresh paired lives per world, not independent replicated searches or formal world admission.
