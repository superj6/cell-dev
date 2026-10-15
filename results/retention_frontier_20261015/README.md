# AK: retention and nearby edge cases

One actual lineage, three unchanged genomes, four worlds, 256 fresh paired seeds.
The aim is to measure cumulative capture capability alongside physical cost before choosing the next evolutionary challenge.

The fixed roles are ancestral POOL endpoint L92, its ordinary mutant AE_L92 (Y row31), and AI ordinary control descended from AE_L92. Worlds are exact ancestral POOL, the current persistent-target world, persistent with mean turn time 100, and persistent with irregular visibility (mean 80 on / 5 off, zero residual cue). Irregular dark intervals are exponentially distributed, not bounded at five. All prices, local organism rules and developmental dynamics remain fixed.

Primary contrasts are AI_control minus L92 captures in POOL and AI_control minus AE_L92 captures in persistent. All within-world pairs, environment contrasts and interactions are retained. A conventional 10% capture-loss tolerance is diagnosed using paired new−0.9×old vectors and their lower three-SE bound; failure to resolve a loss does not establish retention. This tolerance is diagnostic only, never a reward or selection gate.

There are 3,072 research lives and four existing startup replay lives, one worker with two simulation threads, and hard limits of 2,400 CPU-seconds / 1,800 wall seconds. Preparation executes no life or genetic operation. One attempt only; incomplete data produce no scientific outcome. No paid compute.

All environments revealed here become development data. Future final evaluation needs separate parameter combinations and seeds. The lineage was chosen after its prior capture improvement; three stages are not three evolutionary replications. POOL differs in several physical parameters. Short dark-gap success does not establish memory, prediction or a new algorithm.

The NumPy-only frozen reader reproduces physical accounting from all raw columns and checks source/input identity, startup truth, full coverage and resource cleanup:

```
OPENBLAS_NUM_THREADS=1 .venv/bin/python results/retention_frontier_20261015/analyze.py --study results/retention_frontier_20261015 --out outputs/your_fresh_retention_analysis
```

This command is useful after terminal publication. Before that, the reader refuses missing runtime data. `production/` preserves pinned source for independent accounting; `original/` preserves the exact original input files. Operational and source-review receipts are in `evidence/`. The worker requires an explicit exact-protocol release and owned monitor session; do not run it as an unbudgeted diagnostic.
