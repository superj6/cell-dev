# AD: information payoff with a fully dark flash tail

This directory is a source-only, unreleased preparation. No input copying, seed
registration, compilation, simulation or release has occurred. Later preparation
requires root registration and a clean terminal AC process receipt. AC's scientific
success is not a dependency.

AD changes only the existing flash world's `visibility_low` from 0.25 to 0. The
target still becomes bright for five time units after placement; its other motion,
capture and replacement rules remain unchanged. The background signal remains.
All thirteen X2 bodies/controllers and their action rules are retained. The full
C5 instrument and its B ablation change only existing parameter 21 from 0.25 to 0
to describe the declared physical amplitude. Their original and mapped vectors
are pinned. This physical parameter change may change the controller actions.
R0/R1 remain the retained X2 reflex references; they are not optimized for darkness.
A already has zero at that coordinate; its ablation metadata becomes
`[9, 10]` relative to the new full vector.

The planned measurement has 6,656 research lives and 76 validation lives, all under
one inclusive 2,400 CPU-second cap with at most one worker using two threads.
Validation has its own 180 CPU-second ceiling. A fixed calibration gate precedes
research. No retry, extension, candidate selection or tuning is permitted.

`prepare.py`, `validate.py`, `measure.py`, `production_identity.py` and `monitor.py`
all default to dry runs. The only eventual execution path is the root-released
monitor. The scientific worker loads the complete retained ABI3 scratch bundle;
ABI4 bridge and standard identity work runs in isolated child processes. Source
and numerical pins remain strict. See PREREG.md and SCHEMA.md for the fixed matrix.
