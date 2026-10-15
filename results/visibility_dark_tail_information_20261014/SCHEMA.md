# AD producer and reader interface

This is a source-only interface. No actual protocol, input bundle or seeds exist.

`registration.json` will require status `registered`, the ordered thirteen `roles`,
`candidate_policy = retained_X2_flash_controllers_with_physical_amplitude_only`,
`seeds = {validation: [three IDs], research: [512 IDs]}`, and `seed_audit_sha256`.
`AC_terminal.file_pins` must bind the clean terminal working AC budget. AC may be
complete or incomplete; no AC outcome or genotype is an input. The root separately
supplies `resource_clearance.json` with prior process identities, groups and budget
pins. Source-only work does not create either record.

`protocol.json` retains the X2 format: `worlds.flash5_dark` has `base_world`,
`scratch_slots`, the 66-value `packed_world`, `production`, and ordered `candidates`.
Each candidate includes its exact program/cell arrays and byte hashes, controller
parameters or reflex knobs, body flags and footprint. The production object has
the 70-value packed world and ABI4 sizes. ABI3 sizes remain exactly
`[3, 875, 129, 66, 57, 5, 23, 1024, 7, 18]`; both the explicit version and ten
ordered sizes must match before any simulation/data-buffer call.

Other protocol fields: `seeds` (the 512 research IDs), `validation_seeds` (three),
`monitor_scope`, `validation_matrix`, `candidate_transfer`,
`historical_cpu_per_life`, `expected_numerical_identity`, metadata-only
`numerical_identity`, `production_pins`, `production_module_pins`, `file_pins`,
and the unchanged X2 `analysis`/`raw_ledger_aliases`. Historical X2 rows and exact
identities are retained under `inputs/X2/rows/flash5_dim25/<role>/`. Original and
mapped I/B parameters are in `inputs/candidate_transfer.json`. The complete
original ABI3/harness/controller source bundle is under `original/`; it is not
copied until registration and the single authorized preparation.

Research rows remain `rows/flash5_dark/<role>/row.npz`, committed by directory
rename after fsync. Each row contains `ledger` float64[512,57], `hashes`
uint64[512,5], controller `diag`/`latency` when applicable, scalar `cpu_seconds`
and `wall_seconds`, and a canonical JSON `identity`. Identity is exactly
`{protocol_sha256, world, candidate, seeds}`. The sibling `checkpoint.json`
contains that identity and `row_sha256`. `rows/flash5_dark/complete.json` binds all
thirteen checkpoints and reports 6,656 calls. Research hashes from the fast kernel
are not replay evidence. Raw columns 21/22 retain the scratch names
`dark_captures`/`late_captures`, with no reinterpretation of original production
columns. The independent reader must use the corrected X2 static-body accountant,
including initial cells excluded from births and disjoint event counters.

`validation/report.json` retains status, total `simulation_calls = 76`, protocol,
source and production pins, `libraries`, `checks`, and `artifacts`. It additionally
contains `validation_matrix`, `identity` (the startup receipt reference),
`calibration_cpu_seconds` (thirteen three-life batch totals), and the exact
`calibration_projection` result. All artifacts carry relative path, SHA, T, seeds,
library label and call count. NPZ artifacts retain scalar CPU/wall timing;
replay-log NPZs have zero calls. `validation/startup_identity.json` is JSON with
the exact retained standard identity, one invocation, two ABI3 calls at seed 11,
T200, source/protocol binding, and scalar CPU/wall. Its compiler child CPU is
charged by the monitor, not that process-time scalar. The independently built
full/fast production libraries remain in `build-cache/` for terminal archiving.

The validation first-two-seed call mapping and all artifact names otherwise follow
X2, replacing only world label `flash5_dim25` with `flash5_dark`; calibration uses
all three seeds for all roles. A calibration gate failure writes its projection
but cannot write a complete validation report or start research.

`validation_budget.json` is written by the monitor only after the validation
worker and descendants exit. It binds the report hash, protocol hash, actual
cumulative CPU and 180 cap. The monitor rechecks it before/during research.
`attempt.json` records the monitor PID/start identity and release SHA before spawn.
Persisted monitor process identities have exactly `pid`, `ppid`, `pgid`,
`start_ticks` (plus the role/name field in the budget list); they do not persist
`sid`. Live child ownership additionally verifies session membership. The nested
production identity/bridge processes inherit the validation worker's process
group and are accounted/reaped through that group. No elastic thread file is used.

The terminal `budget.json` records cumulative CPU, validation CPU, phase, exit
status, completed commands, running/queued work and all recorded leader identities
and owned groups. First attempt only: any prior attempt, validation, row, log or
build-cache artifact refuses a new run. `ready.json` is root-owned and separately
pins final independent reader and review artifacts as well as the protocol/input
pins; preparation never creates it.
