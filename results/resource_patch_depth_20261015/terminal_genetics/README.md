# Saved-data genetic and selection audit

Source-only helper for protocol `86593f759c5c17823d4eaff19800728229f757eb2ffc82b2f54660e9b32653bb`. It may run once only after root review and the study, budget, and measurement completion markers all report complete and the owned processes have cleared.

`run_checks.py --run --out <new receipt path>` runs one process with one CPU affinity, one thread, 10 CPU seconds, 30 wall seconds, 2 GiB address space, and an initial 4 GiB host-memory floor. Root should add external `/usr/bin/time` logging and retain any failure; there is no automatic retry. No simulator, build adapter, evolution driver, selector, or random API is called.

The checker binds the full ordered 32-row import, source/config identity, native checkpoint and logs, all eight selection NPZs, 1,792 recorded offspring and 3,584 point additions, every one of the 2,048 scored candidate rows, all 32 final rows, crossover ancestry and origin registry, public population metadata, and the native rank-zero export. Each NPZ is decompressed once. The old recorded-operation arithmetic is unchanged; an optional callback observes each already reconstructed candidate table before retention, avoiding a duplicate genetic replay.

The independent selection reducer is adapted from the preceding completed comparison. It recomputes the four objectives from base32 and pooled64 lives, all 16 Pareto rankings, front depths, grouped-coordinate crowding, and the 24 supplied native tie permutations. It uses a lexicographic dominance traversal and scalar value groups, without importing the production selector. Saved capture counts and ordinary F remain the source observations; their 81,920 selection lives are not rerun. NumPy mean rounding is shared, with scalar `fsum` bounds on F means.

The fresh endpoint panel and confirmation accounting belong to the separate measurement audit. Native rank zero is not treated as the reporting endpoint. The replay does not resample genetic or tie-generator streams, infer functionality from ancestry, or establish memory.

`SOURCE_READY.json` binds the four helper sources, the reviewed prior sources, and source-only checks. No terminal check, supplied-array test, build, life, or random draw has been executed during this preparation.
