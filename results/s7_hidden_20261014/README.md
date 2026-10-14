# Message dependence in the s7 continuation

Q applies the existing H design to the fixed s7 row 29 founder and both final generation-16 L descendants.
The twelve arms cross three genotypes with normal, freeze, freeze+lateral_off and freeze+hidden_off. Both
descendants and both effect signs remain. The primary comparison asks whether each descendant's gain over
row 29 depends more on messages sent by hidden cells after growth has been held fixed.

All arms share 512 fresh block 103 seeds, giving 6,144 research lives. The world is fast POOL at T1536, with
interventions at 768 and accounting from 800 through 1536. The cumulative monitor/worker/descendant CPU cap is
3,600 seconds and the worker count is two. Q waits only for P to complete with no active or queued work.
P outcomes do not change any Q choice. This archive is preparation only and contains no readiness marker.

`PREREG.md` specifies the hypotheses, intervention semantics, accounting and interpretation limits. The
genotypes, both final checkpoints, full recorded genetic replay, source hashes and seed audit are preserved.
`sources/` contains exact source snapshots; `namespace_sources/` preserves the inputs used by the independent
freshness audit. `ready.template.json` is a template, not authorization to launch.

Pure preparation checks from the repository root are:

```sh
.venv/bin/python -m pytest -q outputs/autonomous_s7_hidden_20261014/test_measure.py \
  outputs/autonomous_s7_hidden_20261014/test_monitor.py \
  --basetemp outputs/audit_q_20261014/review_tests
.venv/bin/python outputs/autonomous_s7_hidden_20261014/measure.py
.venv/bin/python outputs/autonomous_s7_hidden_20261014/run_budgeted.py
```

No controller behavior, ABI, global communication, clock, population-responsive world or world-admission rule
changes. A hidden-message effect can be indirect; a null effect is not equivalence. Freeze also changes GRN and
phenotype computation, so its contrast does not isolate development. Different genotypes can have different
frozen bodies and states. Life-level uncertainty describes the fixed descendants, not search reproducibility.
