# R stopped before measurement

P reached its fixed CPU limit with confirmation incomplete. Q then failed its prerequisite, and R stopped on its registered Q dependency. R exited with `monitor_failed` / `ValueError` before opening a worker log or starting measurement. **R ran zero research or validation lives and has no scientific outcome.** Effective-weight-update dependence remains unmeasured.

R used 10.228412 CPU-seconds of waiting/monitor overhead under its 3600-second cap. The planned 4608 research lives were not executed. The existing offline analyzer correctly returns `incomplete` / `monitor_failed` before opening measurement outcomes.

Exact terminal P/Q/R budgets, source/release pins and root host/session exit evidence are retained. Both working `measurement/` and `run.log` were absent. All 109 original preparation artifacts, their manifest, and all 40 offline-analysis artifacts plus their manifest remain byte-identical. All 151 preserved files also matched Git index blobs at archival time.

This directory has a separate manifest. No simulation, scientific-source edit, restart, rescue, budget extension or new release occurred.

Verify from the repository root:

```sh
.venv/bin/python results/weight_updates_20261014/operational_status/archive_operational.py --check results/weight_updates_20261014/operational_status
```
