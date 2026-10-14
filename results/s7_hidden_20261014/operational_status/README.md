# Q stopped before measurement

Q's registered dependency, P, stopped incomplete at its fixed CPU budget. Q's monitor then exited with `monitor_failed` / `ValueError`, before opening its worker log or starting measurement. **Q ran zero research or validation lives and has no scientific outcome.**

Q used 14.165054 CPU-seconds of waiting/monitor overhead under its 3,600-second cap. The planned 6,144 research lives were not executed. P's terminal receipt records 14381.265501 CPU-seconds and an incomplete confirmation. No partial P endpoint comparison is made here.

Exact terminal budgets, release pins, monitor sources and root host/session exit evidence are retained. Both working `measurement/` and `run.log` were absent. The original 103 preparation artifacts, their manifest, and the ten-file offline-analysis bundle plus its manifest remain byte-for-byte unchanged. All 115 original files also matched Git index blobs at archival time.

This directory has a separate manifest. It changes no prepared scientific source or readiness marker. No simulation, restart, rescue, budget extension or new release was performed.

Verify from the repository root:

```sh
.venv/bin/python results/s7_hidden_20261014/operational_status/archive_operational.py --check results/s7_hidden_20261014/operational_status
```
