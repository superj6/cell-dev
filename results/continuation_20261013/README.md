# Two short production continuations

Registered before launch in `results/taskvar/prereg.md`, section D. Two 16-generation runs use the frozen s5 row38
founder in fast POOL. The endpoint is final population rank zero, confirmed on 256 fresh paired lives at each of
T768/1024/1536. The budget is three CPU-hours, with at most four simulation workers.

This directory initially archives preparation only; no result is claimed. Working files and all long-running jobs
are under `outputs/autonomous_continuation_20261013/`. `prepare.py` and `run_budgeted.py` are frozen copies of the
working scripts. To prepare a separate execution, copy the scripts into an `outputs/<study>/` directory first;
regenerate its configs and protocol there and audit new seed reservations before any new research run. The runner
defaults to dry-run and requires reviewed readiness pins. It never silently resumes a spent compute budget.

The protocol records exact genome and source hashes, the full seed audit, initialization behavior and life counts.
Only report-only diagnostics are reduced; the production breeding, mutation and selection rules are unchanged.
