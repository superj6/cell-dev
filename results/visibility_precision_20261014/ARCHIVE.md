# AB terminal archive

AB completed 19,576 research lives and ten existing ABI3 startup compatibility lives in 3028.748398 CPU-seconds, including compilation and cleanup. Both fixed Z endpoints received four 3+4-life generations and one 12+16-life generation, with 4,096 selection calls per branch. Four fixed final endpoints and two starts then received 512 shared fresh confirmation lives.

The [summary](analysis_result/summary.json) and [450 paired arrays](analysis_result/paired_vectors.npz) reproduce with `python analysis/analyze.py --study . --out NEW_DIRECTORY`. The frozen reader passed unchanged. Recorded-operation replay verifies both matched 256-genome first cohorts and all four final 32-genome populations; it samples no new randomness or lives.

Precision-minus-depth F is -0.17843 +/-0.07883 for D90 and -0.13330 +/-0.07509 for L92; neither clears three standard errors. D90 precision catches 0.95117 +/-0.16147 more than depth, but its own-start gain is unresolved. D90 depth improves F 0.37224 +/-0.07738 through ordinary cost savings 0.72510 +/-0.01305 while losing 0.72266 +/-0.16122 captures. No endpoint establishes an own-start capture or dark-capture gain. This trades precision against depth, with only two founder/run pairs; it does not isolate precision, match CPU, or establish memory or a more sophisticated algorithm.

All six processes and five owned groups exited. [prelaunch/manifest.json](prelaunch/manifest.json) preserves all 176 prepared artifacts; all 79 released local and 35 production pins remain unchanged. [manifest.json](manifest.json) covers four native run directories, six raw confirmation rows, library bytes, process/resource receipts, independent reviews and figures. Twenty-one initial-search guarded evaluation calls retain penalties; all 3,072 raw confirmation statuses are zero. Per-life search ledgers were not retained.

Packaging and offline analysis execute no new lives or kernel builds.
