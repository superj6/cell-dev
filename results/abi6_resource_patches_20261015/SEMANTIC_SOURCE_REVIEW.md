# ABI 6 semantic source review

Independent source review, 2026-10-15, against contract
`15c3f7d7006bd274c2e7c9c06d6a89bd264dd8128be8579286dda70c1d740d77`.
This review performed no simulator calls, builds, or genetic draws. The root separately reported that the
initial bounded pass passed all new world boundary, C/reference, observer and retained full-output comparisons;
its six failures concern legacy test cap/exception expectations and are being corrected separately.

No unresolved physical-law discrepancy was found in the reviewed implementation. Source streams, geometry and
source timestamps use the declared operation order. Sources advance strictly below a query; same-time receptor
candidates use frozen opening stock while successive clicks consume actual stock. Sources do not restart on
harvest. Opening snapshots precede counted mutations; initial-food provenance remains tied to the original
endowment; endpoint-time sources are excluded; extinction continues source processing through the declared end.
Terminal records contain physical stocks even when an empty accounting window makes appended counters zero.

The C and reference close checks enforce slot conservation and internal initial-food conservation. The Python
readout additionally checks active/inactive slot constraints, capacity, physical click totals and absence of
legacy/matching outcomes. A balanced corrupted ledger could previously relabel refill food as initial food.
This review added the necessary `initial_harvest <= stock_open` check and one synthetic corruption case.
The exact internal `initial_open = initial_harvest + initial_end` identity cannot be reconstructed from the
ledger alone; the engine checks it, and observer records retain the terminal initial remainder.

Neutral new world fields leave old branches and arithmetic intact; older callers reject enabled patches.
The added ledger folds are explicitly projected away for old ABIs. The probe only reads patch state or repeats
pure rate/hash calculations; its event hook records source/click provenance before forwarding unchanged words.
Nearest-patch samples include empty patches, and old single-target interpretations reject patch worlds.

JS uses the same active physics, copied observer state and group-local field snapshot. Its new constructor
validation initially omitted `t0` and effective-duration accounting-window bounds. The JS owner was asked to
add patch-scoped finite/integer/bounded `t0` and `0 <= t_open < effective T` guards, including shorter `opts.T`
overrides. This was resolved in JS SHA
`6b4e9ee31bce67f92e037d9bfeb15f629bec52af2b1b3d71cf978c63a9dc8834`, source-reviewed afterward. That amendment
also adds the direct-click opening hook and the root-requested full-word source-arrival counter hash. These
changes preserve valid-world trajectories. The supported
JS scope remains automatic CATCH without the legacy unsupported scheduler/noise/oracle modes. No browser or
additional replay claim is made by this source review.

Reviewed file pins (before the requested JS input-guard amendment):

| File | SHA256 |
| --- | --- |
| `src/life/spec.py` | `91f286fa460bda49a0dfbc0365e337e5ace42e32ac2839f355b6bcf78c6e4958` |
| `src/life/probe.py` | `b0c8c9cdccb77d9e52d7fbe71a9c92da4135fd7d3c66b07192695941b8f15bee` |
| `src/life/readouts.py` | `c4669e8a4d151366582ca2f028a8c1a95cb5e10c0797f32a7a455322aafbdf03` |
| `tests/test_life_spec_abi6.py` | `3330db5b6041d7bb662fca6bcd5f177dbe2fd7d1b177f63925a3bef675187cdc` |
| `src/life/kernel.c` | `ceaa928a22b53287478da62651527a98bf235373c38fcddffca9c812e82a9a21` |
| `src/life/reference.py` | `74b209e8e819faa27cd55f47fdc480c42b9b7d1045d6f157e59165fab661116f` |
| `results/atlas/play/lifesim.js` | `ab425f6c80b738794a594a8e597aeb3f510dfa6ff09bca33c2171d2c03104a78` |

The readout amendment passed static Ruff and whitespace checks; its synthetic test has not been executed in
this review. No scientific payoff, learning, strategy, or evolutionary accessibility claim follows from these
engineering checks.
