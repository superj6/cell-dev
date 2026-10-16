# ABI5 delayed matching: bounded information-payoff measurement

Prepared 2026-10-15. **Proposal and source preparation only: no scientific life, tuning, seed registration, or admission decision has occurred.** Root has authorized preparing an isolated controller harness; its engineering checks have a separate explicit small call budget below. This document does not release scientific execution.

The question is whether remembering **observed sample receptor events** helps a fixed body make the later conditional choice, enough to pay its physical costs. Use the ordinary ABI5 world, an external information instrument, competing tissue reflexes, and fixed controls. A successful hand-built tissue is never a gate. Instrument success would establish available information payoff for this exact short-duration world, not an evolved algorithm, local attainability, or repeated-task admission.

## Rules and existing methods to reuse

[TASK_VARIATION_PLAN.md sections 0.1 and 0.4](../worktree/docs/TASK_VARIATION_PLAN.md) require at least 512 fresh paired lives, disjoint tuning and scoring, an information gain of at least 1 F and more than three paired SE at the reflex's footprint, a similarly large capability-specific component, and a best measured do-less gain below one quarter of the information gap. The mutation-gradient test is reported when measured; it is not an admission requirement. [The authorized ABI5 proposal](../worktree/docs/ABI5_DELAYED_MATCH_PROPOSAL.md) requires class-conditional choices, coverage, unfinished opportunities, correct pricing, and ordinary cell costs.

Reuse the action enforcement, inert footprints, receptor-delivery callbacks, relay charging, own-action models and replay audits in [the open-headroom harness](../worktree/results/open_headroom/harness/README.md), [ctl_api.h](../worktree/results/open_headroom/harness/ctl_api.h), and [ctl_core.c](../worktree/results/open_headroom/harness/ctl_core.c). Reuse the source/library pins, fixed raw rows, paired analysis, incomplete-attempt handling and resource accounting patterns in [prediction information](../worktree/results/prediction_information_20261014/prelaunch/README.md) and [visibility information X2](../worktree/results/visibility_information_x2_20261014/README.md).

Do not reuse the historical prototype-world patches, repurposed ledger columns, or historical post-scoring choice of a best reflex. Build scratch instrumentation against the current ABI5 engine; all 77 world fields and 70 ledger meanings remain intact. Keep old evidence unchanged. Past visibility interventions also disabled useful actions; their results do not establish a memory-specific effect. The present intervention instead erases one retained sample statistic while preserving current-choice sensing and motor capability.

## Exact world and the useful clock bounds

Use `catch_delayed_match_l4`, with only `T=85`, `t0=t_open=0` changed. Preserve sample duration U[15,25], blank U[20,40], choice duration 50, reset 5, widths 0.6/1.2, equal peaks 2, background 0.05, equal capture radii 1, choice distance U[2,4], reward 500, wrong-choice charge 50 and miss charge 10. Preserve the preset's `d_min=0.5`, `d0=1`, other prices, asynchronous tissue rules and genome format.

The first sample starts at t0, a rule an instrument may know. Its own clock provides the following conservative bounds without revealing realized phase transitions:

| Instrument time | Permitted operation and reason |
|---|---|
| Receptor deliveries `d_min <= t < 14` | Record sample evidence. Every such event was generated while the first sample was present. |
| `t=30` | Erase the sample statistic in the ablated arm. This lies after the latest possible sample delivery and before the earliest choice. |
| `t=65+d_min=65.5` | Initialize current-choice inference from a common prior and begin accepting new choice observations. Every retained observation now comes from the two-choice scene. |
| Earliest action `t=66.5` | Enforce an additional `d0` conduction hop after the first choice observation/callback. |
| `t=85` | Right-excluded life end. No initial choice can time out strictly earlier than this. |

Every information/control arm has an identical inert body and makes **no movement, tap or queued motor command before 65.5**. It never acts on sample evidence early. It may then steer and tap using the usual act cells; all command deadlines must remain strictly below 85. It stops commanding new actions after its first attempted tap. Success feedback is not available to the controller. Any already queued strokes remain ordinary physical actions and are charged.

These instrument arms can resolve at most their first choice: after a hit at or after 66.5, a second choice cannot open before 106.5. **An unrestricted reflex can resolve early and open a second choice just after t75.** Do not suppress that opportunity, truncate its reward, or call every arm a one-opportunity life. Native whole-life F includes everything for every arm. A separate observer-only first-trial analysis isolates matching behavior. Competing reflexes may retain sample consequences in motion, twitch or refractory state; they are not described as rigorously sample-blind.

This is admission evidence only for the specified T85 world. Sustained matching over successive trials, uncertain trial starts, T1024 selection, longer delays and transfer remain unmeasured. Reserve those duration/geometry combinations from development. A later repeated-task proposal needs its own measurement; the short-world result is not silently promoted to it.

Treat T85 as a diagnostic, not a selected evolutionary setting. The continuing GRN lineage develops from one cell, whereas the instrument starts with its full sensory footprint; a useful footprint may become available only after some of the first sample has passed. Existing historical s5 engineering fixtures do develop off-center sensors during that sample (first births near relative t3.83/4.60 and 13/11 off-center sensors by t14), but those fixtures are not the continuing lineage and do not establish its accessibility. Read existing developmental traces before choosing a later setting. Neither fixed-body instrument success nor a hand-built body success is a gate. The scratch harness must preserve arbitrary ABI5 durations and repeated trials, so repeated-trial inference/readouts can be the next measurement without another physics patch.

## Information instrument and clean retention contrast

Use the existing `hollow3` footprint: 19 sense sites (center plus ring 3), 37 act sites (disk 3), total 56 cells, identical to the ordinary `reflex@hollow3` reference. Static inert cells pay maintenance throughout the life. Off-center sites matter: a stationary center receptor sees the same peak rate for both samples and has zero shape evidence by itself.

During the fixed sample observation window the body is at its initial origin, as is the stationary sample. For sample class c and sense site s, compute the known rate

`r_c(s) = lam_bg + lam_s * exp(-||offset_s||² / (2 sigma_c²))`.

From observed delivered counts `n_s` and observation duration `14-d_min`, form the Poisson log-likelihood ratio

`L = sum_s [n_s log(r_narrow(s)/r_broad(s)) - (14-d_min)(r_narrow(s)-r_broad(s))]`.

Use a 1/2 prior and the resulting narrow-class posterior. This uses events and the absence of events, never the sampled true class. At t14, seal L and discard the sample counters and raw history. L is the **only sample-derived value that any later decision routine may read**. No class-dependent diagnostic, cached target, random-state update, command, position change or localization buffer may act as a second channel. Observer logs are write-only from the controller's perspective.

At t65.5 all instrument arms initialize the same fresh geometry belief. The two stationary choice centers are opposite about the known stationary body origin; their common radius is in [2,4], and narrow/broad side is unknown. A fixed quadrature over oriented narrow-target angle and radius uses only newly delivered pings, silence, known world rules, sensor geometry and the controller's own commanded motion. Account for `d_min` when associating a delivery with the sensory position at its candidate time. The narrower/broader Gaussian likelihoods include their overlapping tails. Geometry inference must not use L: L changes which inferred width is desirable, not what the current scene is believed to be.

Reuse `ctl_steer` and the commanded key/twitch model. Actions are ordinary act-cell spikes with kappa on the existing {0.25,0.5,1} grid, minimum per-cell interval 0.5, and at least one additional `d0` hop after the information used. No teleportation, direct click API, free force, reward input, true position, target position, phase, phase deadline, trial index, sample class or life seed is exposed to the instrument. The instrument's clock and knowledge of fixed duration bounds are permitted measuring-tool privileges under section 0.1; none are added to an organism.

Before scientific registration, freeze quadrature weights, steering objective and the choice between actual narrow/broad target alternatives. At L=0 the same rule must choose a target alternative using expected payoff and physical hit probability, with class-independent deterministic ties; it must not steer to the mean of opposite target centers. The tuned tap threshold is **physical hit probability at the selected target conditional on current-scene geometry**, not joint probability of a correctly rewarded match. A correctness threshold above 0.5 would suppress E's taps by construction and invalidate the retention comparison. N/B use exactly the same estimator, target-selection mechanics, steering and physical-hit threshold.

The full and erased instruments have identical physical state and event histories before decisions. E computes the same L as I, then assigns `L=0` at its own t30 wake. Every other state and future action rule remains unchanged. P never accumulates L and processes only the post-65.5 stream for choices, while receiving and paying for the same earlier receptor relays. E and P must produce bit-identical command traces and ledgers in paired lives; disagreement is a leak or implementation failure, not scientific evidence. In I, retain L through the blank interval. Compare I−E as the specific contribution of retained sample evidence, without disabling present-cue tracking, taps or steering.

The algorithm is an external measuring instrument with free central computation. It is neither a tissue design nor a claim about where evolved memory would reside. If this finite instrument fails, report the estimate and limitations; do not conclude the world lacks usable information or demand a hand-built winning body.

## Draft candidate arms and limited development

| Role | Fixed definition at confirmation |
|---|---|
| I | Retained sample L; current-choice inference and ordinary actions. |
| E | Same selected instrument, only L erased at t30. |
| P | Post-blank-only controller: no retained sample evidence; same relay charges and current-choice rule. Expected bitwise E/P equality. |
| N | Same current-choice instrument, fixed narrow preference; no sample information. |
| B | Same current-choice instrument, fixed broad preference; no sample information. |
| R0 | Unchanged ordinary tissue `reflex@hollow3`, unrestricted for the full life. |
| R1 | One hollow3 reflex chosen on disjoint tuning lives from the fixed small panel below; unrestricted. |
| D0 | Entirely quiescent hollow3 tissue: maintenance-only limiting control. |
| D1 | R1 with all sense gains multiplied by 1/2; same 56 cells. |
| D2 | R1 with each nonzero act-cell kappa lowered one allowed grid step, including the hotspot; same 56 cells. |
| D3 | R1's role knobs on `hollow2` (13 sense plus 19 act cells, 32 total). |

“Best” means best within these declared measured families. No claim covers every possible reflex or do-less strategy. R0 remains a separate fixed reference even if R1 wins development. All four D arms remain in confirmation rather than choosing a favorable one afterward.

Proposed development is 64 paired lives, separate from confirmation. Test exactly 12 reflex parameter slots: sensor gain factors {0.5,1,2} × motor kappa factors {0.5,1} × hotspot kappa factors {0.5,1}, all relative to R0 and decoded on legal grids. Freeze the exact decoded tables, including any duplicates, before these lives. Select R1 by mean whole-life F, with source-table order breaking ties. No additional hill climb.

Test four predeclared instrument variants on the same 64 development lives: decision wake period {0.25,0.5} × tap hit-probability threshold {0.75,0.9}. Keep the sample likelihood, 64-angle × 16-radius geometry quadrature, action latency, footprint and charging fixed. Select I by mean whole-life F with table-order tie-breaking; E/P/N/B inherit its exact selected non-memory parameters. These are 16 × 64 = **1,024 development calls**, regardless of the outcome. Any numerical/operator correction afterward must be source-reviewed before confirmation; it cannot use confirmation observations to select parameters.

Confirm all 11 roles on **512 fresh paired lives**, totaling **5,632 confirmation calls**. Use the same 512 environment seed IDs for all roles, retain their original order and all outcomes, and save each seed-level result. These are 512 independent life clusters, not a larger sample made by counting within-life trials. Shared seeds couple environment draws; different actions can change subsequent receptor streams and opportunity times.

Do not assign unverified block numbers in this proposal. Before execution, audit the current namespace registry, reserve one development block and one separate confirmation block, materialize and hash every seed array, and freeze exact source/input/library/arm tables and call inventory. Reused 42M engineering fixtures are prohibited from either scientific panel. No confirmation seed is used for calibration, tuning, debugging, visualization selection or replacement. The first listed confirmation seed may later illustrate the result without searching for a favorable replay.

## What is reported and what would satisfy section 0.4

For every role, retain all 70 native ledger columns, guard/extinction outcomes, and observer-only trial records. Independently reconstruct income as `500*(correct_n+correct_b)`, wrong cost as `50*(wrong_n+wrong_b)`, every ordinary physical cost and final F. Reconcile each class's `opportunities+carry_in = correct+wrong+timeouts+unfinished`. In addition to whole-life F, report first-trial class × {narrow hit, broad hit, no completed choice}, current-scene coverage, misses, completion time, posterior calibration, correct-per-opportunity, accuracy among completed choices, reward per opportunity and the full cost decomposition. Report both sample classes separately, even when one looks unfavorable.

A sample-blind completed choice earns expected gross 225 before costs; positive income or positive F is insufficient. The ideal difference between perfectly matched and blind completed first choices is 275/85 = **3.2353 F** before differences in physical costs and coverage. That is useful headroom above the 1 F admission bar, not a promised attainable gain. The late-action window is only 18.5 time units after earliest action, so localization and movement can consume much of it. Quiet/small controls may also expose substantial maintenance-driven advantage.

Use per-seed paired differences and the sample standard deviation divided by sqrt(512). For formal admission of this exact T85 world:

1. I−R0 **and** I−R1 each have mean at least 1 F and greater than three paired SE. Reporting both avoids choosing a flattering reflex after scoring. I−N and I−B accompany these comparisons as fixed-preference checks.
2. I−E has mean at least 1 F and greater than three paired SE, and E/P equality passes. This supports a retained-sample-statistic contribution in the instrument. Also show class-specific acquisition gains so a one-class selective strategy cannot masquerade as general matching.
3. Every measured do-less gain is below one quarter of the information gap. Compute paired margins `0.25*I + 0.75*R - D_j` for each R in {R0,R1} and each D arm. The existing section-0.4 criterion requires all mean margins positive. Also report all lower three-SE margins as uncertainty and stronger evidence when positive; these are not an added admission gate. Describe uncertain margins explicitly.

These are prespecified operational/descriptive three-SE criteria, not a claim of familywise p-values. An incomplete study or failed accounting/identity check has no admission verdict. No rows are discarded to improve a result. The gradient test, evolved descendants, old-task retention, long-life repetition and held-out delay/geometry transfer are explicitly **unmeasured** here; they are later choices, not hidden gates requiring successful tissue construction.

## Fixed budget and engineering scope

Proposed scientific envelope: **3,600 cumulative CPU-seconds**, 5,400 wall seconds, one one-thread worker at a time, 8 GiB address-space ceiling, 4 GiB RSS stop and a 4 GiB host-available-memory floor. Include compilation, calibration, development, confirmation, failed attempts and teardown in the same ledger. Reserve at least 2,400 CPU-seconds for confirmation/cleanup before development ends; use the first fixed development batch only to assess throughput. If the remaining fixed panel does not fit, stop incomplete and prepare a separately bounded revision. Do not shrink the 512-life confirmation or silently reduce arms. There is no paid compute, evolutionary search or production-world modification.

Before scientific registration, prepare the ABI5 scratch harness under `outputs/delayed_match_information_20261015/harness/`. A proposed **40-call engineering maximum**, T≤85, reused engineering seeds only, fits a **120 CPU-second sublimit** inside the 3,600 total: eight production/scratch tissue passthrough calls (four pairs), eight null/inert comparison calls (four pairs), eight scripted-action/replay calls (four pairs), eight same-ping-stream hidden-state-independence replay calls (four pairs), four full/fast calls (two pairs), and four C/Python bridge calls (two pairs). Freeze the exact inputs and declared comparisons before dispatch. No full information-controller policy is implemented until root coordinates its final specification.

The scratch `life_run` path must match production ordinary tissue byte-for-byte on ledgers, hashes and logged events. Controller-mode null/replay checks must explicitly distinguish unchanged physical outcomes from intentional instrumentation counters and relay charges; historical harness claims do not excuse undocumented differences in tick counts, accumulation order or hashes. Independently reconstruct all charged quantities and record every permitted difference. Full hashes are replay evidence; fast hash constants are not.

Before any scientific release, require a source audit showing that controller translation units cannot read kernel internals, hidden truth, reward or environment seed; `ctl_truth` is unavailable to the unprivileged information instrument. Replaying the same supplied ping/time stream and own command history under different hidden sample classes, deadlines, positions and seeds must produce identical actions. Also test latency, per-cell refractory limits, quantization, refused post-end actions, extinct actuators, equal prefix costs, L-only erasure, E/P equality and the sample-center information null. These are measurement-validity checks, never a requirement that a hand-built tissue win.

The proposed full package therefore contains **6,696 simulator calls maximum: 40 engineering + 1,024 development + 5,632 confirmation**. Engineering-only retries consume the same call/CPU ceilings and are retained; scientific retry/resume is not implied. Publish the actual frozen counts and resource envelope before launching. This proposal itself runs none of them.
