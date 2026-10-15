# Independent prospective analysis of Y

The reviewed protocol is `1880ff6e21b4689031e892d9dc6765a8d9673a35efeefb213acf268f5370adf4`. This package was completed before any Y measurement. It verifies the fixed original65-row panels per founder, all138 raw rows and six aggregates, the whole32-life screening choice, both selections frozen before confirmation, and the first-attempt monitor's phase/source/resource records. No confirmation outcome is emitted unless the complete study passes.

Run the NumPy-only reader against a completed working study or public archive:

```sh
python analysis/analyze.py --study /path/to/study --out /path/to/new/results
```

The output directory must be new. A partial or corrupt study returns `incomplete` with no scientific summary or paired arrays. The reader imports no engine, worker, mutation or simulation code. Archived production sources resolve through `production/`, external dependency records through `original/`, and operational files may be at the study root or `operations/`.

`offline_accounting.py` narrowly adapts study I's production accountant to the58-column ABI4 ledger. It retains natural extinction and paid guards, checks the initial-zygote census, reconstructs all ordinary prices and both penalties, and keeps low-light captures as an unpriced diagnostic. `ACCOUNTING_REVIEW.md` details those semantics. The new complete-study reader adds identity, completeness, selection, aggregate, compiled-byte and monitor-phase checks. Startup validation is exactly the retained two ABI3 seed11 T200 goldens plus eight fixed ABI4 cost-calibration lives; the golden hash and ledger SHA match the already published engineering fixture.

`genetic_replay.py` is a separate, prelaunch audit. It imports Torch and the pinned ordinary mutation helper but prohibits kernel compilation and life simulation. It reproduces all130 registered float32 genome rows and exact operation records, verifies both original founders and the derived ABI4 worlds, and leaves the registered panels unchanged. This independently invokes the same mutation implementation; it is not a separate mutation algorithm. Its final receipt is bound into the release. The script can use the published `production/` source bundle:

```sh
python analysis/genetic_replay.py --study /path/to/study --out /path/to/new/replay.json
```

The complete synthetic test fixture contains138 raw rows and both genuine phase handshakes, with explicitly nonexecutable fake library bytes. Twenty-two focused tests cover complete data, row-order ties, missing/stale rows and aggregates, source/panel identity, startup goldens, paid-phase CPU and incomplete/failed monitors. The143 separate row-accounting tests cover every column plus growth, death, guards, extinction and paired cost signs. These tests run no simulated lives. Historical growing-founder compatibility checks are labelled explicitly and provide no new blink-world evidence.

Report each founder's selected-mutant minus own-parent confirmation separately. Capture and low-light changes and the additive cost/penalty pieces explain what improved. They do not identify memory, prediction, a new algorithm, or a capability-specific world admission. This is a phase0 local-gradient diagnostic, with useful information payoff established separately by X2.
