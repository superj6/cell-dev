# Independent completed-data analysis preparation

This separate bundle contains Q's reviewed offline analyzer, exact NumPy genetic replay helper, synthetic tests
and both validation/review receipts. It does not change the 103 artifacts or provenance of the original study
preparation. The copied protocol and L confirmation manifest are fixed test inputs, not Q outcomes.

All 48 tests pass without compiling a kernel, simulating lives or reading active Q/P outcomes. Tests cover the
complete twelve-row workflow, paired signs and covariance, penalties, frozen-tissue checks, source/genotype pins,
completed-study gates, corruption detection and preservation of the original preparation during export.

From the repository root:

```sh
.venv/bin/python -m pytest -q results/s7_hidden_20261014/offline_analysis_preparation/test_analysis.py \
  results/s7_hidden_20261014/offline_analysis_preparation/test_analysis_workflow.py \
  --basetemp outputs/audit_q_20261014/offline_bundle_review
```

The analyzer refuses conclusions until its target's own resource record is complete. It reconstructs all twenty
paired contrasts from retained raw rows and checks all sixty scored columns. Future export preserves the
original preparation before writing a result archive and independently checks the copied data.

`provenance.json` belongs only to this bundle. `preparation_seal.json` records the unchanged parent provenance.
No readiness marker or scientific execution is created by this bundle.
