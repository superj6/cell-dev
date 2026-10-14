# Fixed-panel decoy-gradient diagnostic: preparation

This diagnostic reuses all 64 ordinary mutants of each original s5/s7 parent, without choosing them by their
prior-world scores. The world is exactly F's existing ABI-3 decoy world at the original conduction speed.
No external controller enters any organism. [Frozen protocol](prereg_draft.md).

Screen every parent/mutant on 32 shared block95 lives; re-score the top four mutants and parent on 512 block96
lives; freeze one mutant per parent before independent 512-life block97 confirmation. Exact ties use original
row index. All negative results remain. This totals 11,328 scientific lives, plus the existing E1 golden pair.

The work directory is `outputs/autonomous_decoy_gradient_20261014/`. The 3,600 CPU-second cap is shared across
all stages, with two workers; the monitor waits for G to finish, then may run beside H's two workers.
No simulation or new mutant generation
occurs during preparation. A root-created readiness file releases the fixed protocol; none is created here.

```sh
.venv/bin/python outputs/autonomous_decoy_gradient_20261014/prepare.py
.venv/bin/python outputs/autonomous_decoy_gradient_20261014/measure.py
.venv/bin/python outputs/autonomous_decoy_gradient_20261014/run_budgeted.py
```

The last two commands are dry-run by default. Synthetic tests cover selection, negative outcomes, paired
capture/poison/miss accounting, both-winner freezing, dependency scheduling and source-pin refusal. They run
no life simulator. All engine/search and existing measurement helpers remain unchanged.

After release, `budget.json` records resource state; `measurement/report.json` records scientific completeness.
An exit code alone does not establish completion. Completed rows are atomic and byte-hashed; restarting an
interrupted study requires explicit accounting for its spent budget. The monitor never silently resets it.
