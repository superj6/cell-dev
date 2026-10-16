# Exact proposed short-horizon information instrument

Draft for root review, 2026-10-15. This is not a registered policy, a selected winner,
or a release to execute scientific lives. The scratch harness now implements this
full policy plus null and scripted engineering controllers. Root approved the rule
with the both-width expected-gross correction below. It changes no world or cell rule.

## Shared inputs, chronology and stored state

Use the proposed T85 world and hollow3 footprint. Inputs are delivered receptor
events `(own_time, sense_index)`, the fixed constants of the family, initial footprint,
own clock and own command history. No true position, target center, outcome, reward,
phase, sample class, trial index, life seed, phase deadline or actuator-survival
feedback is available. The private harness history contains only commands; its
motion prediction can be wrong after damage. Geometry is relative to the original
body origin and never recentered using true position.

All five instrument roles schedule the same own-clock wakes at relative14,30,65.5.
All receive and pay for all receptor relays throughout life. None queues a stroke
before65.5. Between14 and65.5 all new pings are ignored by decision state. The sample
observation duration is13.5, corresponding to delivered times[0.5,14).

I and E count sample events at each site and compute the specified Poisson LLR at14.
Then they zero and discard the count buffer; no raw sample timestamps survive. E
sets L=0 at30. P,N,B never accumulate sample evidence and keep L=0. Their sample
callbacks do not alter any geometry, action, RNG or auxiliary state. Observer logs
are write-only. I/E have identical physical prefixes; E/P must be bit-identical.

At65.5 initialize geometry from the same prior in every role. Schedule decision
wakes at65.5+n*dt, where dt is one of the two predeclared development values0.25/0.5,
strictly before85. A ping updates inference but does not itself issue an action.
At a tied ping/wake time, ordinary kernel event ordering applies; every callback
uses only events already delivered to it. Extra state is the geometry log weights,
last inference time, selected-target diagnostic, own actuator model and a stopped
flag. No sample-dependent geometry initialization or hidden second channel is allowed.

## Fixed geometry likelihood and integration rule

There are1024 hypotheses in row-major `(angle_index, radius_index)` order:

`theta_j = 2*pi*(j+0.5)/64`, j=0..63;
`r_k = 2+2*(k+0.5)/16`, k=0..15;
`q_n(j,k)=(r_k*cos(theta_j), r_k*sin(theta_j))`, `q_b=-q_n`.

All prior weights are1/1024 because the native draws are uniform angle and uniform
radius, not uniform area. Use double-precision log weights and log-sum-exp
normalization. Do not prune hypotheses or add a moving-target transition model.

For candidate time u, obtain the body's position from its own commanded impulses
at u, not at delivery time. A sensor's point is that prediction plus its fixed
body-frame offset. The rate under each hypothesis is background0.05 plus the two
peak2 Gaussians with widths0.6 and1.2, including their overlapping tails. At a
delivered ping t, first accumulate silence through candidate time `u=t-0.5`, then
add `log(rate_h(sensor,u))`. At a decision wake, first accumulate silence through
`u=t-0.5`. The initial candidate time is65.0. No observation generated before65.0
enters this geometry belief.

Compute each silence contribution as the sum over all19 sensors of the integrated
rate. For every integration interval, split at own scheduled stroke times in the
interval and at globally anchored candidate-time grid points `65+m*0.25`. Evaluate
each resulting subinterval with the midpoint rule. Also split at the interval's
actual endpoints, including receptor times. This fixes the approximation and
accounts for motion at emission time. It is not retuned on development outcomes.
Subtract the common background term or retain it consistently; choose retention
in the source for simpler audit. If weights become nonfinite, flag the life as a
measurement failure and stop the study; do not substitute truth or drop the row.

The emission time's own-position model keeps the full command history. It uses
the same fixed traction, twitch decay and drag constants as the permitted harness
model. There is no cancellation or correction from observed capture outcomes.

## Target alternatives and ordinary actions

At every decision, choose the maximum-posterior geometry hypothesis, with smallest
row-major hypothesis index resolving an exact weight tie. Its two physical centers
are the two candidate goals. This intentionally simple estimator avoids tuning an
additional planner; broad or multimodal uncertainty remains visible in hit coverage.

For each width w, compute `H_w(q)` as the posterior probability that goal q lies
inside that width's ordinary radius1 capture disk. Class probabilities are
`p_n=sigmoid(L)`, `p_b=1-p_n` for I/E/P. For each actual candidate goal q, use the
expected gross score `G(q)=(550*p_n-50)*H_n(q)+(550*p_b-50)*H_b(q)`. This includes
both possible physical-width hits under geometry uncertainty. Choose the candidate
with larger G. Exact score ties
choose the goal nearer the own predicted eventual position; remaining ties choose
the lexicographically smaller `(x,y)` physical goal. No tie rule reads true class,
seed or width label. N always selects the narrow alternative and B the broad one;
all other inference/action code is identical. In particular E/P choose an actual
target alternative, never the midpoint of opposing centers.

For steering, obtain own predicted eventual position from all already queued
commands. Call the existing greedy rim-cell steering helper with error from that
position to the chosen goal, `kmax=1`, `min_align=0.5`, and `tol=0.15`. These three
numbers are fixed, not a development sweep. This schedules at most one stroke per
eligible act cell in that callback. The harness enforces legal kappa rounding,
minimum0.5 same-cell interval and earliest time `callback_time+d0`. All accepted
strokes use ordinary `fire` physics and pay their actual cell costs.

After scheduling those steering strokes, compute the earliest permitted hotspot
time `ta=max(now+d0,last_hotspot_stroke+0.5)`. Predict body position at ta from own
commanded actions, including the newly queued strokes. Compute the posterior
probability that this predicted point lies inside the **selected width's capture
disk**. This physical hit probability must meet the selected threshold0.75/0.9.
It is not multiplied by the probability that the width is the remembered class.
The key/twitch model must also predict a click with kappa1. If both conditions hold
and ta<85, queue one ordinary hotspot spike and set stopped. The instrument issues
no further commands after that attempted tap; pending strokes run and are charged.
If the tap misses, no success or failure input is used to retry.

At L=0, class correctness remains0.5 but the erased controller can still steer and
tap whenever current-scene physical localization is strong. N/B audit fixed-width
preferences. No rule requires a hand-built tissue or this measuring instrument to
win; failure should be separated into sample information, localization, movement,
tap coverage and cost limitations.

## Charges, bounded development and checks still required

Every instrument has56 initial cells with ordinary ticks and maintenance. Each
delivered live-cell receptor event pays `c_rec` plus one relay `c_spike+c_msg`.
Every actual actuator spike pays the native spike/twitch costs. There are no free
actions, world changes or repurposed ledger columns. Central inference itself is
free measuring-tool computation, explicitly distinct from organism attainability.

Only the four declared `(dt,physical_hit_threshold)` settings may be compared on
the64 disjoint development seeds. I's selected setting transfers unchanged to
E/P/N/B. No wider search or subsequent planner rescue is implied. A failure may
motivate a separately reviewed bounded diagnostic, not confirmation reuse.

Before scientific registration, bind reviewed source and inputs to the release.
The32-call harness bridge and eight full-policy engineering lives have passed.
Pure supplied-input tests cover changed hidden fields, normalization, center-sensor
class-null, L erasure, E/P state/action identity and neutral-memory physical tapping.
Three physical E/P pairs match full ledgers/hashes/logs; two I/E pairs share sealed
sample statistics and pre-choice spike prefixes. The physical policy fixtures use
only dt0.5/threshold0.75; the other three declared settings have no extra full-life
engineering evidence. No scientific setting was selected from those fixtures.
