# Another ordinary adaptation step from both D endpoints

P starts two new 16-generation searches from the fixed D51089 and D51090 final endpoints, using the unchanged
ordinary point-mutation policy. Search seeds 52091 and 52092 map to those founders respectively. Each population
starts with one exact founder and 31 ordinary mutated copies; no founder or historical best is protected.

Both new final rank-zero endpoints are fixed before confirmation. All six roles—original s5, row38, both D
founders and both new endpoints—share 256 fresh block102 seeds at T768/1024/1536. Each primary compares a new
endpoint with its own D founder, averaging durations within seed before computing SE. Both signs remain.

PREREG.md gives the full design and limits. inputs/founder_audit.json binds both original D checkpoints and
recorded-genetic replays. initialization.json binds the exact prospective 32-genome populations and RNG states.
seed_audit.json and sources/source_seed_review.json document the full prior/prepared namespace check.

Scope: 37,548 research lives, fixed 14,400 cumulative CPU-second ceiling, at most four simulation threads.
The study waits for O to complete with no active or queued work. Missing either endpoint or any confirmation
role leaves the whole study incomplete. No scope replacement, automatic restart or extension is permitted.

Preparation performs no lives. ready.template.json is descriptive; root review, publication, a milestone commit
and an explicit readiness release precede any launch. The archive retains source and configuration snapshots;
the operational scripts still use their original repository paths.

Pure/mock checks and dry run:

```sh
.venv/bin/python -m pytest -q outputs/autonomous_next_step_20261014/test_prepared.py outputs/autonomous_next_step_20261014/test_monitor.py --basetemp outputs/audit_p_20261014/prepared_tests
.venv/bin/python outputs/autonomous_next_step_20261014/measure.py
.venv/bin/python outputs/autonomous_next_step_20261014/run_budgeted.py
```

No P scientific result is present in this preparation. Future completed-data export must preserve these bytes
and independently audit every raw confirmation row and each paired comparison.
