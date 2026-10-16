# Prospective terminal packaging helpers

These helpers are prepared while research runs. Preparation reads source and registration metadata only;
the packaging and replay entry points have not run. They do not modify frozen study source or public results.

After `budget.json`, `study_complete.json`, and `measurement_complete.json` all say `complete`, root supplies
the frozen reader's saved summary, the successful `native_replay.complete_replay` receipt, terminal README,
and terminal report. The independent all-row audit must also have passed. Stage into a **new direct child
of `outputs/`**, using the root virtual environment and external resource logging:

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  .venv/bin/python outputs/delayed_match_evolution_20261015/terminal_package/pack.py \
  --study outputs/delayed_match_evolution_20261015 \
  --summary <saved-summary.json> --native-replay <recorded-genetics-receipt.json> \
  --readme <terminal-README.md> --report <terminal-REPORT.md> \
  --out outputs/delayed_match_evolution_terminal_stage_20261015
```

Optional `--include <study-relative-path>` retains additional root terminal analysis/review evidence.
The helper preserves the complete prospective archive and moves its original README, verifier and manifest
to `registration_history/`. It adds all native run files, midpoint and final checkpoints, checkpoint-bound
logs, phase attempts/budgets/startup truth, terminal metadata, independent audit, canonical summary and
recorded-genetics receipt. Binaries and build caches are excluded. The 28 raw and 28 scored confirmation
files become `raw_scored.tar.gz`: exactly 56 sorted regular USTAR members with normalized ownership/times,
all verified against `row_index.json` before and after packing. It refuses changed prospective files or
existing destinations. Root reviews and publishes the stage; the helper never writes `results/`.

Verification and saved-data replay of the staged or subsequently published archive:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <archive>/verify.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python <archive>/replay.py \
  --out outputs/delayed_match_evolution_saved_replay_20261015
```

Replay verifies the archive, stages production dependencies from git revision
`968bb81f2e146e2e729bca43004628d78a6e9b99`, securely extracts only the 56 declared regular members,
then imports the unchanged frozen `common`, `analyze`, `native_replay` and `replay_ops` files. The summary
must reproduce byte for byte; the recorded-genetics result must match structurally and bind all final and
midpoint rows. No simulator/build modules may be imported. The recorded replay verifies additions,
crossover, lineage, retained order and checkpoint/log consistency; it does not re-sample the genetic RNG
or independently establish ranking from unavailable parent scores.

Each packaging or replay process is separately bounded to 60 CPU / 120 wall seconds, one numerical thread,
2 GiB address space, 512 MiB RSS, and a 4 GiB host-memory floor. Failures and partial output are retained;
there is no automatic retry. The standalone verifier performs only bounded-size archive/file hashing and
git source reads; use external resource logging when invoking it separately. No new scientific calls,
builds, random draws or public changes are authorized by preparing these helpers.
