# Ongoing phenotype and effective receive-weight updates

R compares fixed row 38 and both D generation-16 rank-0 descendants under three existing controls: structure
held fixed (S), structure plus gene state and phenotype held fixed (C), and full freeze (F). The primary paired
effect asks whether each descendant gains more than row 38 from allowing ongoing effective receive-weight
updates under a fixed phenotype: `(D-row38)C - (D-row38)F`.

Nine arms share 512 fresh block 104 seeds, giving 4,608 research lives. Fast POOL runs to T1536, interventions
start at 768 and accounting opens at 800. The cumulative monitor/worker/descendant cap is 3,600 CPU-seconds with
two workers, waiting only for Q completion. This is preparation only; no readiness marker authorizes a launch.

PREREG.md specifies all 16 contrasts, retained penalties and limits. semantic_proof/ explains the exact existing
code paths and the independent review. The contrast includes local chemical/contact updates and early transient
carryover; it does not isolate pure memory or learning. The R design precedes O outcome inspection. Both
endpoints and both signs remain, with no world-admission, behavior or ABI change.

Inputs include exact D endpoints/checkpoints and recorded genetic replay. sources/ preserves numerical and
helper snapshots, while namespace_sources/ preserves the independent freshness audit inputs. The readiness
file is a template only. From the repository root, pure checks are:

```sh
.venv/bin/python -m pytest -q outputs/autonomous_weight_updates_20261014/test_measure.py \
  outputs/autonomous_weight_updates_20261014/test_monitor.py \
  --basetemp outputs/audit_r_20261014/review_tests
.venv/bin/python outputs/autonomous_weight_updates_20261014/measure.py
.venv/bin/python outputs/autonomous_weight_updates_20261014/run_budgeted.py
```
