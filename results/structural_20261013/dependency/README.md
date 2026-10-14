# Two fixed continuation replicates

Each run starts from the same previously selected s5 row38 founder: one exact copy and 31 ordinary mutated copies. Ordinary sexual evolution runs 16 generations with 32 parents, 224 offspring, three initial lives and four recheck lives on the top64. All parents are reevaluated; the founder and historical best are not protected.

Final population rank zero is fixed before fresh confirmation. Both endpoints, founder and original pilot are measured on the same 256 seeds at each of T768/1024/1536. The primary averages the three paired effects within seed; SE uses 256 clusters.

| Search | Additional gain versus founder (mean ± SE) | >3 SE | ≥0.5 F |
| --- | ---: | --- | --- |
| s51089_final_rank0 | +0.632730 ± 0.187591 | True | True |
| s51090_final_rank0 | +0.756045 ± 0.202185 | True | True |

Completed research lives: 36,012. Monitored CPU: 10013.037438 seconds, within the 10,800-second cap.

The archive retains final checkpoints, all populations and lineage, search/validation curves, source/configuration/numerical pins, and every confirmation ledger column. Duplicate per-row NPZ files are omitted; their original hashes remain in row_index.json, and the equivalent aggregate data are directly covered by archive provenance.

Independent reanalysis (no simulation):

```sh
python results/continuation_20261013/analyze.py --study results/continuation_20261013 --out outputs/continuation_reanalysis
```

Requires NumPy, PyTorch, OmegaConf and Matplotlib from the project environment. Frozen src is included for schema/hash definitions. operations/run_budgeted.py records the executed launch and cap logic; its original relative paths are provenance, not a standalone archived launcher.

- Two fixed exploratory continuation replicates do not estimate general search reliability.
- The final population rank-zero genome was frozen before confirmation; no validation-best reselection occurred.
- Search fitness and selected-body descriptors are winner-biased and use changing durations and seeds.
- Periodic validation uses 16 fresh lives at T1024 and describes successive selected genomes; it is not an independent repeated measurement of one fixed organism.
- The duration mixture averages three paired effects within each shared seed before computing SE over 256 seed clusters. The endpoints also share those seeds.
- Guarded lives retain the production continuation charge; capacity or ledger mismatch blocks inference.
- These data concern adaptation from a preselected founder in fast-conduction POOL, not a new algorithm.
- Saved numerical pins are compared without executing numerical golden checks or any simulation.
