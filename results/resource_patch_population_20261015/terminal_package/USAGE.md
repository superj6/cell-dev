# Terminal staging helper

Source prepared while the diagnostic runs. Do not execute before root signals completion and the saved
summary, cleared budget and `reviews/independent_review.json` all exist. No active outcomes were read during
this preparation, and no helper or synthetic test was executed.

After source review, root supplies the terminal README and REPORT and runs once, with external logs in
`outputs/resource_patch_population_20261015/terminal_package_logs/` (excluded from staging):

```sh
.venv/bin/python outputs/resource_patch_population_20261015/terminal_package/pack.py \
  --readme outputs/resource_patch_population_20261015/TERMINAL_README.md \
  --report outputs/resource_patch_population_20261015/REPORT.md
```

The default destination is the required absent `outputs/resource_patch_population_terminal_stage_20261015`.
The helper enforces15CPU/30wall seconds,2GiB address space, one CPU affinity and4GiB host headroom.
It stages and verifies once; it never replaces the public archive. Original prospective manifest, README,
publisher and verifier are preserved under `registration/`; all other prospective bytes remain in place.
Raw/scored batches, startup truth, owned execution evidence, terminal review, closed top-level logs,
`publication_logs/prospective_*`, REPORT/TABLES, the all-row CSV and both SVG/PNG plot pairs are included.
Build/matplotlib caches, test fixture trees and open packaging logs are excluded.

The terminal verifier is stdlib-only and binds exact frozen inputs/sources, both completion markers and the
cleared budget,20raw+20scored files, four retained startup calls, and the independent accounting/ranking
receipt. Table/plot source, summary and file hashes are bound through `tables_receipt.json`.
It checks retained public provenance and committed production bytes without simulations or builds.
Publication and any incorporation of the external packaging resource receipt remain root-owned.
