# Whole-population acquisition diagnostic — complete

All 97 fixed genomes completed the five-world, 32-life development panel: **15,524 total calls** in
861.07 CPU seconds, with 344.30 MiB peak owned RSS. Independent accounting and rank checks pass.

The cached first-choice genomes rank 29th and 25th within their surviving populations on the new panel.
Pareto selection increases population-average POOL acquisition; its previously reported endpoint's large
pursuit losses are not established population-wide. Useful variation remains, without a confirmed new
joint winner. No further evolution or endpoint substitution occurs in this diagnostic.

Read [REPORT.md](REPORT.md), [TABLES.md](TABLES.md), the [population plot](population_acquisition.svg),
and [cached/fresh ranks](cached_fresh_ranks.svg). The full row table is `population_rows.csv`.

The original prospective manifest, README and publication helpers remain under `registration/`.
Frozen protocol/source/input bytes are unchanged. Native ledgers, scores, startup records, ownership budgets,
reviews and the saved-data audit's preserved I/O failure are included. Build caches and synthetic temporary
fixture trees are excluded. Earlier public archives supply the explicitly pinned namespace and accounting
references.

Verify hashes and receipts without simulations or builds from the repository root:

```sh
.venv/bin/python results/resource_patch_population_20261015/verify.py
```

Source revision: `5d556443e91d558de8de27ab2e5dc7ae11a51415`.
Prospective publication: `c994f779eda9bf97b7d2588d774f13d3f0cb268e`.
