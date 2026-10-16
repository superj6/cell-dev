# Delayed-matching evolution — complete

One 24-generation continuation improved trained matching fitness by **1.194293 ±0.101150 F**, chiefly
through lower costs, without demonstrating cue-dependent matching. The final genome selected the broad
physical target in 96.11% of completed choices. POOL captures fell by 20.85%; the desired cumulative
capability was not established.

Read [TERMINAL_REPORT.md](TERMINAL_REPORT.md) for conditional-choice results, costs, retention, limitations
and the next direction. [summary.json](summary.json) is the unchanged frozen analysis;
[terminal_audit/REPORT.md](terminal_audit/REPORT.md) records the independent all-row recount.
The [fixed-case viewer](../atlas/delayed_match_evolution.html) shows actual evolved organisms.

All 75,902 scientific/startup calls completed within the original limits: 4,676.217354 CPU seconds,
2,315.306468 wall seconds, 346.78 MiB peak owned RSS. All confirmation statuses are zero and workers cleared.
Recorded-genetics replay verifies every offspring and all32 midpoint/final rows. A separate12C+12JS
illustration batch passed; no browser rendering test is claimed.

`raw_scored.tar.gz` preserves all28 native and28 scored NPZ files unchanged. Native run files include the
full ordered input population, checkpoint, midpoint, lineage logs and fixed endpoints. Original prospective
README/manifest/verifier remain under `registration_history/`. Source inputs, reviews, startup truth,
ownership/resource receipts and all planned results are retained.

From the repository root, verify and reproduce the saved-data analysis without running any life:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/delayed_match_evolution_20261015/verify.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/delayed_match_evolution_20261015/replay.py \
  --out outputs/delayed_match_evolution_saved_replay_new
```

The replay destination must be absent. Replay stages the pinned production dependencies from git968bb81,
requires the frozen summary to match byte-for-byte, and replays recorded genetic operations with no new
genetic draws. Scope and limits are in [terminal_package/README.md](terminal_package/README.md).

Protocol `2941610e…64d9345`; summary `80963876…3fe91a33`; prospective commit `382761c`.
