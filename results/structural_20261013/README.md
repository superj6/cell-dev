# Structural-operator comparison: preparation only

Two fixed 16-generation searches will test the previously approved silent-duplication/deletion policy against
the matching ordinary-evolution searches in D. No scientific G lives have been run by this preparation.

[PREREG.md](PREREG.md) defines the comparison, exact life counts, fresh block93 confirmation, neutrality check,
resource cap and limits of interpretation. [protocol.json](protocol.json) freezes the machine-readable inputs.
The preparation and monitor tests use raw genome operations and synthetic processes/data only.

The working location remains `outputs/autonomous_structural_20261013/`. Restore the archived preparation files
there before reproducing tests or running. `run_budgeted.py` and `measure.py` default to dry-run; actual launch
requires root's reviewed `ready.json` and `--run`. The archive includes a readiness template only.
The monitor waits for D/E and already released F work, then runs neutrality, two searches, and fixed confirmation.
The cap is 14,400 worker CPU-seconds and four simulation threads, with no automatic restart or extension.

Reproduce validation from the repository root with:

```sh
.venv/bin/pytest -o addopts='' -q outputs/autonomous_structural_20261013/test_prepared.py \
  outputs/autonomous_structural_20261013/test_monitor_measure.py
.venv/bin/python outputs/autonomous_structural_20261013/run_budgeted.py
.venv/bin/python outputs/autonomous_structural_20261013/measure.py
```

Pinned existing production sources remain in the repository; the archive includes helper snapshots, prepared
configurations, exact initial genotypes, D dependency pins and the numerical identity used by D. Sources may not
change between preparation and execution. Final endpoints, complete ledgers, life contrasts and independent
analysis will be archived after completion, including negative results or any incomplete-work receipt.
