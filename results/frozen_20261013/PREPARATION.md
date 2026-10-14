# Lateral dependence with tissue held fixed: preparation

This archive prepares a fixed experiment; it contains no block-92 scientific results yet. The working directory
remains `outputs/autonomous_frozen_20261013/`, including when the archived monitor is used. Launch requires root's
explicit `ready.json`; preparation only writes `ready.template.json`.

The experiment compares the original s5 parent with its already selected row-38 descendant in fast POOL.
Each genotype receives the same 512 new seeds under four conditions: normal, frozen, lateral transmission off,
and both frozen and lateral transmission off. There are 4,096 genome-lives. Life ends at 1536; interventions
begin at 768 and fitness is counted over 800–1536. The primary effect subtracts the winner's advantage with
frozen lateral transmission off from its advantage in the intact frozen condition, within each seed before
estimating uncertainty. See the [frozen protocol excerpt](protocol_excerpt.md) and [protocol data](protocol.json).

Freeze prevents further gene, phenotype and effective-weight updates, division claims and death decisions.
Claims already sent can still produce newborns. Under these fixed settings, their structural notices finish
before 768.75; the bounded spike delays place pre-fork deliveries before 771.003. Opening accounting at 800
excludes this settling interval. It does not erase earlier dynamical state. Membrane activity, receptors,
vertical spikes and chemical transport continue. `lateral_off` prevents creation of new in-plane spike
messages; outgoing-message charges remain and messages already in flight are processed normally.

The analysis will check zero post-open births/deaths and equal frozen tissue counts across paired lesion arms,
including the expected constant-population cell-time integral on guard-free complete lives. Guard and extinction
penalties remain in fitness. Parent and descendant may have different tissue footprints, and freeze itself changes
computation. This tests conditional function of held-fixed tissue, without claiming maturity or a new circuit.

The monitor waits until the continuation study has no queued jobs and at most one two-worker job. Its pinned
state machine can subsequently launch at most one two-worker confirmation, so E's two workers keep the combined
maximum at four. Pure file hashes are checked before and after waiting; numerical golden replay only happens
inside the scientific runner after that slot is available. The monitor checks at two-second intervals, requests
termination at 3,588 child CPU-seconds, forces termination after a two-second grace period, and applies a Linux
process CPU soft/hard limit of 3,599/3,600 seconds. Existing budget records or unexplained cached results block
automatic restart.

Validation includes 16 mock monitor checks with zero simulated lives, plus root's previously completed 16
validation-only full-length genome-lives on block 8 (3.874 process CPU-seconds). Those lives passed the frozen
tissue checks and are preserved as aggregate ledgers. They are not block-92 evidence. Measured sources, prior
inputs, monitor dependency, protocol and tests are hashed in `provenance.json`.

```bash
.venv/bin/python results/frozen_20261013/run_budgeted.py
.venv/bin/pytest -q results/frozen_20261013/test_run_budgeted.py
```
