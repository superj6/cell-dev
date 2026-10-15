AC: retained-panel flash gradient

Question: can the same ordinary mutations that were available in Y produce capture-supported
improvement in flash, and do flash-selected and blink-selected mutants differ across the two
approved environments?

Inputs and selection

Reuse the exact complete Y float32[65,875] panels, including the original founders at row 0 and
every recorded mutant at rows 1–64. Retain their original layouts, configurations, mutation
operations, manifests, source identities and recorded genetic replay. B_D90 is Y row 58; B_L92 is Y
row 24. These roles are fixed regardless of AA, AB or new confirmation outcomes. No new candidate
genotypes are generated.

The worlds are `catch_speck_flash5_dim25_l4` and `catch_speck_blink20_20_l4`, each at T=1024 with
t_open=0, no interventions and unchanged production guard/extinction charging. Only the flash world
is screened: 65 rows × 32 shared seeds × two backgrounds. Select H by mean production F among rows
1–64, with the lowest row index breaking exact ties. Keep the selected mutant even if it loses to
row 0. Freeze both H rows, all six role identities and the complete confirmation genotype table
before any confirmation or confirmation-cost decision.

Confirmation uses the ordered roles `P_D90,P_L92,B_D90,B_L92,H_D90,H_L92` in both worlds. All twelve
role/world rows receive the same 512 seeds. Duplicate genomes remain explicit and are evaluated
again. Calibration, screen and confirmation namespaces are disjoint; the seed11 numerical golden is
deliberate legacy engineering replay. Exact research namespaces require separate root review and
registration; none are reserved by this source document.

Statistics and interpretation

Primary effects are H_D90−P_D90 and H_L92−P_L92 in flash production F. Retain H−P, B−P and H−B in
each world, and the interactions `(H−P)_flash − (H−P)_blink` and `(H−B)_flash − (H−B)_blink`. Form
every interaction per seed and then summarize the paired vector. Report both backgrounds separately,
all signs, means and standard errors; a descriptive three-SE threshold does not change selection,
sample size or inclusion. The 512 life pairs do not constitute 512 evolutionary replicates.

Decompose F differences into capture income, ordinary-cost savings, guard-charge savings and
extinction-charge savings. Retain captures, low-light captures, bright captures and all raw ledger
columns. Capture-supported improvement requires a resolved positive capture-income effect as well as
a resolved positive primary F effect; this is descriptive, not an admission gate. Positive world
interaction alone does not establish that H beats B in flash. Reciprocal specialization would
require H>B in flash and B>H in blink. Flash and blink jointly differ in residual cue strength,
visibility scheduling and placement reset semantics, so these comparisons cannot isolate memory,
persistence or one environmental feature.

All valid negative, extinct and guarded lives remain in the result. Capacity errors, nonfinite
ledgers, accounting mismatch, source/identity mismatch or unflagged incomplete lives invalidate
completion. Whole-life production F is raw kernel F minus the retained extinction charge. The
initial zygote is excluded from births: `1 + births − deaths − kills = n_end`. Do not impose
static-body assumptions or subset relations between disjoint reject/drop counters.

Exact calls and resources

One worker, two simulation threads, first attempt only. Standard `numerical_identity()` is invoked
exactly once, inside the monitored worker: two ABI3 seed11 T200 full/fast compatibility lives. Eight
actual ABI4 flash calibration lives are rows 0 and 1 × two seeds × two backgrounds. Research calls
are 2×65×32 + 2×6×512 = 10,304; total calls are 10,314. Calibration and numerical goldens are never
used for genotype selection.

The cumulative hard cap is 7,200 CPU-seconds, including all owned descendants, compiler children,
monitor costs and teardown. Startup/calibration has a hard ceiling of 180, and startup/screening a
cumulative ceiling of 3,400. The remaining 3,800 is reserved for confirmation. Monitor stopping
thresholds are 170, 3,390 and 7,190. The persistent worker's OS CPU limit covers the total
allocation; monitor phase acknowledgments enforce the earlier ceilings.

Cost check 1: let f_p be the maximum of the two flash calibration batch CPU totals divided by two
for background p. Require monitored startup CPU + 1.5×2080×sum(f_p) ≤ 3390. For confirmation, assign
each background's three flash roles rate f_p. Assign its blink P/B rates from the exact historical Y
screen rows and its unknown H rate the maximum across all 65 historical rows. Require `180 +
1.5×512×sum(all twelve role rates) ≤ 3790`. The monitor recomputes this gate before authorizing
screening.

Cost check 2: after both H selections freeze, use the exact 32-life flash rates and historical
32-life blink rates for rows 0, B and H in each background. Retain duplicate roles in the sum.
Require the same `180 + 1.5×512×sum(all twelve rates) ≤ 3790` before confirmation. The monitor
independently recomputes the saved projection and freezes its artifact hash. These estimates are
planning margins, not bounds on unobserved lives; hard caps still apply. Any failed gate/cap leaves
the first attempt incomplete, without reselection, row omission, retry or extension.

Dependencies and release

Y must have complete reviewed panels and unchanged source/configuration provenance. AB is only an
operational dependency: its pinned budget must be terminal and its processes cleared, whether its
science completed or not. No AB score determines this experiment. Root owns future registration,
preparation authorization, publication and release. This source-only draft does none of those
actions.
