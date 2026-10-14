# Hidden and lateral message dependence: preparation only

H measures the unchanged row38 founder and both fixed D final descendants in four conditions, after holding
tissue development fixed where specified. The primary question is whether each descendant's additional gain
depends more on messages from cells in the hidden planes. See [PREREG.md](PREREG.md) for exact interventions,
paired contrasts, limitations and the resource cap.

There are 6,144 planned lives on fresh block94, two workers, and a 3,600-worker-CPU-second cap. H waits for G to
finish. Preparation has run no scientific or validation lives; the tests use synthetic arrays and mocked workers.
The existing engine and measurement helpers remain unchanged. The archive pins each source and fixed input.

Restore these preparation files to `outputs/autonomous_hidden_20261014/` before reproducing validation:

```sh
.venv/bin/pytest -o addopts='' -q outputs/autonomous_hidden_20261014/test_measure.py \
  outputs/autonomous_hidden_20261014/test_monitor.py
.venv/bin/python outputs/autonomous_hidden_20261014/measure.py
.venv/bin/python outputs/autonomous_hidden_20261014/run_budgeted.py
```

Both entry points default to dry-run. Root must review/register/commit the protocol before copying the readiness
template to ready.json and calling the monitor with `--run`. Never launch the measurement process separately.
Completed rows are atomic with strict hashes; an existing resource record prevents an unaccounted restart.
All 57 raw ledger fields and production fitness accounting are preserved for independent reanalysis.
Pinned numerical-identity startup golden checks use CPU within the cap and are separate from research lives.
