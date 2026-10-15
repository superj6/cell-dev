# AD prospective measurement

Status: source-only and unregistered. This is a one-world information-payoff
diagnostic, not an evolved-organism result or a test that admits a world because
one constructed controller wins. The controller algorithms and bodies are retained;
only their declared dark amplitude is matched to the world.

## Fixed physical and controller changes

Use `catch_speck_flash5_dim25_l4` at T = 1,024 and change only
`visibility_low: 0.25 -> 0`. Keep all other physical fields, prices and flags
identical. In the retained scratch representation this is only `dark_amp` at
world-array coordinate 16, with `dim_flag = 777`, `blink_on = 5`, and
`blink_off = -1` unchanged. The production ABI4 coordinate is 69. Scratch and
production event/hash formats differ, so the bridge checks the same documented
physical ledger/hash subset as X2, including dark captures mapped to ABI4 column
57; it does not claim equality of complete world/event hashes.

R0 and R1 are retained reflex references from X2, not reflexes optimized for this
fully dark world. Reuse R0, R1, I, A, B, D0 through D7 in that order, including every existing body,
program, reflex knob, C5 parameter, action cost, latency and footprint. The only
numeric controller parameter edits are I/B coordinate 21, from 0.25 to 0, matching
the known physical amplitude. A's vector is unchanged, and A's changed-coordinate
metadata becomes [9, 10]; B remains [26]. No outcomes inform these edits. Preserve
the exact original and mapped vectors. Source `mem_ctl.c` remains byte-identical.

C5's existing flash belief uses an exponential transition hazard although the
world's bright deadline is fixed at five units. This remains a documented
instrument limitation. A is a broad visibility/model ablation; B changes an
existing dark-state movement preference. Neither isolates useful memory or a
single algorithmic capability.

## Calls and seeds

Use three fresh paired validation IDs, denoted v0/v1/v2, and 512 separate fresh
paired research IDs. No IDs are selected or registered by this source draft.
Repeated uses of v0/v1 are deliberate engineering comparisons.

| Validation component | Fixed mapping | Calls |
| --- | --- | ---: |
| Physical bridge, T128 | R0/R1 × v0/v1 × scratch/production | 8 |
| Full/fast, T128 | I/A/B × v0/v1 × full/fast | 12 |
| Callback replay, T128 | I/A/B × five calls described below | 15 |
| Cost calibration, T1024 | All 13 roles × v0/v1/v2 | 39 |
| Standard identity, T200 | Existing ABI3 seed 11 once full and once fast | 2 |

For each I/A/B callback case: record v0; replay those callbacks with receptor
delivery disabled on v0, on v1, and on the fixed alternate physical world using
v1; finally run the ordinary recorded controller on v1 as the closed-loop control.
The replay must reproduce the full callback and requested-action arrays byte for
byte, instrumentation must preserve the unwrapped result, and truth access must
remain zero. The alternate physical settings remain X2's fixed engineering test.

Validation totals 76 calls. Research uses every role on all 512 shared IDs,
13 × 512 = 6,656 calls. Overall total: 6,732. There is exactly one standard
`numerical_identity()` invocation, in an owned isolated production subprocess.
Its two compatibility lives do not test the dark world and are labeled accordingly.
No standard identity call is made during preparation or in the scratch process.

## Budget and fixed feasibility gate

One concurrent worker, at most two threads. Validation and research workers run
sequentially. Compiler/production children inherit the owned validation process
group; all process and child CPU, failures and teardown are included. Total cap:
2,400 CPU-seconds; validation cap: 180. The monitor stops new work at 2,390 and
170 respectively, then kills/reaps its process groups. No retry or resume.

The thirteen pinned X2 flash rows cost 569.166600145 CPU-seconds for 6,656 lives.
The whole two-world X2 validation, including compilation and owned processes,
cost 68.524434 CPU-seconds. These are planning evidence, not a guarantee about
the darker world or the new three-life batches.

For each role r, define `cost_r = max(new_calibration_batch_CPU_r / 3,
retained_X2_role_CPU_r / 512)`. Research starts only if
`180 + 1.5 × 512 × sum(cost_r) <= 2390`. The new batch CPU includes both threads;
the historical floor prevents a small cheap calibration batch from replacing the
existing measured cost. All thirteen roles enter the calculation, with no pruning,
resizing or retuning. An infeasible estimate or any failed validation leaves the
study incomplete. The monitor, rather than this estimate, enforces the hard cap.

## Inference and failures

Keep X2's registered raw full-ledger fitness, both fixed I−R0 and I−R1 contrasts,
the better whole-mean retained reflex reference, all eight do-less comparisons and both broad
I−A/I−B contrasts. Information payoff must be at least 1 F and exceed three paired standard
errors; the existing do-less quarter-gap check remains. Select no controller using
the new outcomes. Any missing row, malformed ledger, static-body extinction,
guard or runtime failure makes complete status false. The static instrument uses
raw accountant F, without the separate evolving-organism extinction penalty.

An information gap supports the value of available observations in this physical
world. It does not show that an evolved organism uses memory, that C5 is optimal,
or that low-light captures require retained information: earlier steering,
coasting, local dynamics and changing architecture remain alternatives. Formal
capability-specific admission and G5 duration expansion remain incomplete/held.
