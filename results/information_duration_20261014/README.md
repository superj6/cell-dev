# N: information payoff at two durations — preparation

This fixed comparison tests the retained default C4 controller and five existing
reflex references in the original fast base/POOL worlds at T=768 and T=1536.
It uses 512 paired lives per candidate and condition: 12,288 research lives,
plus 40 bounded validation lives within the same 3,600-CPU-second allocation.
No tuning or organism change is involved. The external controller is only a
measurement instrument.

Read [PREREG.md](PREREG.md) for the fixed scope, contrasts, limitations and
failure rules, and [protocol.json](protocol.json) for exact parameters and pins.
The queue waits for L to complete; it uses at most two workers. This preparation
contains no release, budget record, measurement or outcome.

The previous headline used d0=0.5 and d_min=0.25, which this experiment retains.
The old-conduction settings of experiment F are not used. Fixed C4 defaults and
the retained per-world reflex knobs are copied without retuning. All primary
contrasts remain separate by world and duration.

From the repository root, pure checks are:

```sh
.venv/bin/python outputs/autonomous_information_duration_20261014/measure.py
.venv/bin/python -m pytest -q outputs/autonomous_information_duration_20261014/test_prepared.py outputs/autonomous_information_duration_20261014/test_validation.py outputs/autonomous_information_duration_20261014/test_monitor.py --basetemp outputs/audit_n_20261014/prelaunch_tests
```

The public preparation includes unchanged recovered inputs, the fixed protocol,
scripts/tests and a numerical-source snapshot. Its `ready.template.json` is a
non-releasing template. `provenance.json` hashes every public preparation file.
Completed raw data and an independent analyzer will be added after completion.
