# ABI 7 contact resources: engineering record

This archive records an implemented, validated environment extension. An empty click at a resource site can
start one delayed packet; repeated taps cannot reset or queue it. Existing food, passive replenishment, local
stock cues, cell rules and prices remain in place. No contact-resource scientific study or evolutionary run
was released. Obstacle navigation is the next research priority; this extension is not its prerequisite.

Read `REPORT.md` for checks and limitations, `CONTRACT.md` for exact semantics, and `validation_summary.json`
for actual counts and resource use. `source/` in the published archive holds the final production/test sources.
`abi6_truth/` preserves the original published legacy cases. `before_kernel_provenance.json` distinguishes an
early intermediate C snapshot from the exact committed original in `before_original/`.

The original failing attempts, unchanged logs, test source before its fix and all subsequent commands are
retained under `validation/`. The three invocation failures occurred before their affected JS cases advanced.
No passed life was rerun to repair those invocation errors.

Verify an installed archive without reading the working checkout:

```bash
python3 results/abi7_contact_resources_20261016/verify.py --archive-only
```

Omit `--archive-only` to additionally check installed source bytes. Verification hashes saved artifacts; it
does not build or run a simulator. The archive intentionally excludes build caches, compiled libraries and
pytest temporary trees. Real-browser rendering was not tested.
