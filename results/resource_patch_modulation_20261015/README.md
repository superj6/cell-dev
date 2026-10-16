# Resource stock-modulation diagnostic

Completed fixed-genome measurement with saved-data analysis recovery. Start with [REPORT.md](REPORT.md).
All original evidence is retained, including the post-return analyzer error. No life was repeated.

- `PROTOCOL.md`, `protocol.json`, `release.json`: frozen design and exact release.
- `inputs/`: both genotypes, native/generated C, and 72 explicitly reused baseline rows.
- `raw/`, `row_index.json`: all 148 new returns, with native 107-column ledgers and five hashes.
- `compiler_diagnostics/`: all six isolated build commands and their diagnostics.
- `measurement_complete.json`, `budget.json`, worker logs: original failed-analysis attempt, with all calls returned.
- `terminal_recovery/`, `analyze_terminal.py`, `terminal_read.py`, `terminal_recovery.json`: exact metadata repair,
  original evidence copies, independent review and successful saved-data recovery.
- `per_life.csv`, `summary.json`: 212 combined rows and paired development comparisons.
- `reviews/independent_accounting.json`: independent all-row numerical and provenance audit.
- `production/`, `manifest.json`: immutable engine snapshots and complete artifact hashes.

Verify the public archive without compiling or simulating:

```sh
.venv/bin/python results/resource_patch_modulation_20261015/archive.py --verify
```

Add `--archive-only` after production sources change. Native production pins originate at `71591f3`;
the preceding inherited-baseline milestone is `19886ff`. The isolated renderer is measurement-only.
