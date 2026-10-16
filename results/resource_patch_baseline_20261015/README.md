# Resource-patch inherited baseline

The fixed AO genome transfers to the new resource world without further evolution: 21.44 food packets per life,
including 15.50 replenished packets, on32 shared development lives. The older AM reference collects 16.34 total,
including 10.91 replenished. All 32 inherited population rows are retained and reported; none is selected anew.

[Report](REPORT.md) gives results, uncertainty, older-task comparisons and limitations.
[Protocol](PROTOCOL.md) is the frozen prospective 456-call registration. `summary.json`, `per_life.csv` and all 456
native NPZ rows preserve the evidence; `reviews/independent_accounting.json` records independent reconciliation.
The source-only next-options note predates outcomes. No information-payoff admission or newly evolved patch
algorithm is claimed.

Verify archive bytes and installed production sources without simulations:

```sh
.venv/bin/python results/resource_patch_baseline_20261015/archive.py --verify
```

After later production changes, add `--archive-only`. The complete pinned production source is retained under
`production/`. Runtime and analysis sources are retained at the archive root; raw provenance is bound by the
protocol, row index and manifest. The original logs and release-setup correction are preserved.
