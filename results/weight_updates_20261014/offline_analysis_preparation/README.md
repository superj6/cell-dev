# R completed-data analysis preparation

This separate bundle contains the reviewed offline analyzer, NumPy genetic replay helper, synthetic tests and
validation/review receipts. It changes none of the original 109 preparation artifacts or their provenance.
Copied inputs and scientific sources are fixed preparation fixtures for tests, not R measurement outcomes.

All 69 pure/synthetic tests pass. They cover all nine raw rows, 57 ledger columns and 60 scored columns, all 16
paired contrasts, complete-only reporting, signed effects and covariance, every income/cost/penalty component,
constant tissue in all S/C/F arms, guarded fitness retention, differing secretion costs, corruption rejection,
exact fixed D ancestry, archive preservation and input auditing without a repository fallback.

The primary contrasts are each descendant's added C-minus-F effect over row38. Secondary effects include added
S-minus-C and all individual gains/losses. Every comparison keeps both endpoints and signs. Weight changes can
reflect autonomous chemical relaxation; these contrasts alone do not demonstrate memory or sensory adaptation.

From the repository root, run only the offline tests:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q \
  results/weight_updates_20261014/offline_analysis_preparation/test_analysis.py \
  results/weight_updates_20261014/offline_analysis_preparation/test_analysis_workflow.py \
  --basetemp outputs/audit_r_20261014/public_analysis_tests
```

After the target study completes, reanalyze without simulation or compilation:

```sh
OPENBLAS_NUM_THREADS=1 .venv/bin/python \
  results/weight_updates_20261014/offline_analysis_preparation/analyze.py \
  --study outputs/autonomous_weight_updates_20261014
```

The analyzer checks the target's completed resource record before reading measurement data. Publishing a final
archive is a separate operation; it preserves the original preparation and reanalyzes every copied raw row.
Python and NumPy suffice for reanalysis; Matplotlib is used only when making figures. Test dependencies include
pytest. The source/fixture tests run inside this pinned repository, while completed exports include all sources.

`provenance.json` belongs to this bundle only. `preparation_seal.json` records the unchanged parent preparation.
No scientific outcomes were read, no lives simulated, and no readiness or resource record created by this bundle.
