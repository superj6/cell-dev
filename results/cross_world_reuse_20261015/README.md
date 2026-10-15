# Existing-genome comparison across four worlds

This complete offline analysis compares the same 130 genomes in the existing Y blink, AC dim-flash, AE persistent-target and AG dark-flash screens. It also retains all 14 relevant historical mutant–parent confirmation comparisons. See [REPORT.md](REPORT.md) for findings and limitations. No new simulation, mutation or compilation was performed.

All original source and output bytes are preserved. `manifest.json` maps every artifact to its workspace origin and hash. `analysis_result/input_hashes.json` binds 585 already committed repository input files plus the three analysis-source files now copied here. This directory does **not** duplicate the historical raw archives: reproducing it requires the accompanying repository at the recorded input commit (or the same input bytes). There is no network fetch or implicit replacement of missing inputs.

From the repository root, use an explicit repository argument; the preserved script's original default assumes its workspace location:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python \
  results/cross_world_reuse_20261015/analyze.py --repo "$PWD" \
  --out outputs/cross_world_reuse_reanalysis_20261015
```

Use a fresh output directory. The copied source files have the same bytes but new paths, so a public replay's input/output provenance manifests record those three relocated source paths. A later repository commit can also change the summary's `source_commit` provenance field. The scientific tables and paired arrays should remain identical. The exact original invocation is preserved, and the independent root replay matched all eight original output files byte for byte.

The screens were used for selection and this comparison is post hoc. No row selected from this audit is thereby a held-out generalization result. Positive fitness can chiefly reflect cost savings; capture changes are reported separately. Three-SE flags are descriptive and unadjusted for inspecting many mutants and metrics.
