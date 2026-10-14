# Duplicated-origin gene contribution: prospective preparation only

J measures every active duplicated-origin gene in both fixed G endpoints with the existing deletion operator,
then confirms one fixed choice per endpoint on independent lives. [PREREG.md](PREREG.md) specifies the full rule,
seed blocks, whole-life interpretation and limits. No G endpoint or fitness outcome was inspected to prepare it.

At most 19,456 research genome-lives are scheduled on blocks98 and99, with a two-worker/7,200-CPU-second cap.
The actual count depends only on active duplication ancestry. Both H and I must complete before J starts.
Preparation does not create ready.json or launch simulation. Startup golden checks are outside research counts
and inside the CPU cap. Every endpoint and every sign is retained; no stage is extended after an outcome.

The working path is `outputs/autonomous_duplicate_use_20261014/`. Restore the archived preparation there before
reproducing tests or running:

```sh
.venv/bin/pytest -o addopts='' -q outputs/autonomous_duplicate_use_20261014/test_measure.py \
  outputs/autonomous_duplicate_use_20261014/test_monitor.py \
  outputs/autonomous_duplicate_use_20261014/test_single_branch.py
.venv/bin/python outputs/autonomous_duplicate_use_20261014/measure.py
.venv/bin/python outputs/autonomous_duplicate_use_20261014/run_budgeted.py
```

Both entry points default to dry-run. Root owns review, registration, milestone commit and release. Use only the
resource monitor with `--run` after a reviewed readiness record exists. A saved budget prevents automatic reset.
Completed scoring rows are atomic and hash-checked. All 57 ledger fields and production fitness accounting are
preserved, as are the exact knockout genomes, genetic ancestry and independent-confirmation selection record.
