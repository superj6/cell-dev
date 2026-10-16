# ABI5 controller harness: preparation only

This directory instruments a pinned copy of the isolated ABI5 kernel. It contains
the delayed-matching information policy, null, supplied-action replay and callback-script
engineering controllers. There is no scientific payoff result here.

`prepare_sources.py` records the source origins and mechanically adapts the historical
open-headroom controller core. `make_ckernel.py` adds callback and commanded-action
hooks only. No old prototype world patches, ledger repurposing, hidden truth API,
seed accessor, or phase/class input are carried forward. All ABI5 fields retain
their meanings. Arbitrary supported ABI5 durations and repeated trials remain valid.

The public `ctl_api.h` has an opaque controller handle. Controllers compile in separate
translation units and can inspect fixed footprint/physics, their supplied parameters,
receptor callbacks, their own clock and own commanded-action models. Kernel internals
exist only in the core translation unit. This is an auditable interface boundary,
not a security sandbox against malicious native code. Source review remains required.

Actions use the existing `fire` physics, at least one `d0` after the callback,
per-cell separation at least 0.5, and kappa rounded up to {0.25,0.5,1}. Dead addressed
actuators drop commands at delivery. A command model can consequently differ from
physical movement after damage; no survival or execution feedback is supplied.
Receptor relay charging emits the usual receptor and one-relay-spike accounting
records. Original inert-cell ticks and notices remain, preserving the ordinary
maintenance accumulation order. Noise must be zero in controller mode.

Unlike the old core, efference keeps every commanded impulse. Queries for past
emission positions use only that history; `ctl_eff_pos(t_delivery-d_min)` no longer
silently returns the position at delivery. Motor sign is fixed to ordinary pull.

Ordinary `life_run` must match the pinned engine byte-for-byte. Null mode with relay
charging disabled must match the same ordinary inert tissue. Script/replay must
match charged physical ledgers/raster/fates; their extra wake events intentionally
change simulator event counts and the all-ledger close hash. These permitted
differences will be listed from the exact engineering assertions, not inferred away.

Root accepted an engineering maximum of 40 backend calls, T<=85, 120 cumulative
CPU seconds, single worker/thread, 8 GiB address space, 4 GiB RSS, 4 GiB host free
floor. All40 calls are complete; the exact32+8 inventory and evidence are recorded
in `../ENGINEERING_EVIDENCE.md`. No additional engineering lives are authorized.
No scientific seed block is allocated by this directory. Proposal, not registration:
`../../abi5_delayed_match_20261015/coordination/INFORMATION_PAYOFF_PLAN.md`.
