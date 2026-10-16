# Delayed-matching continuation: improved economy without demonstrated matching

The fixed 24-generation continuation improves trained-world fitness by **1.194293 ±0.101150 F**, but does
not establish cue-dependent choice. Lower physical costs supply 0.941535 F, about 79% of the mean gain.
The final organism chooses the broad physical target in 470 of 489 completed T85 choices (96.11%).
POOL capture performance falls to 79.15% of its starting value. This is an efficiency/specialization result,
not the cumulative matching capability sought.

All values below come from the complete frozen [summary](summary.json), independently recounted from every
native row. Differences are paired means ± SE across 512 shared lives unless stated otherwise. Three-SE
bounds are descriptive; this is one evolutionary continuation, not a replicated search-policy comparison.

## Conditional choice and its alternatives

In these retained T85 lives, every fixed genome encounters one choice opportunity per life. All roles
see 248 narrow-cue and 264 broad-cue opportunities. The task itself permits earlier responders to open
a second opportunity before T85. The registered generation-24 rank-zero genome remains primary.

| Fixed genome | Correct narrow / opportunities | Correct broad / opportunities | Correct / completed choices | Unfinished | Broad physical hits / completed |
|---|---:|---:|---:|---:|---:|
| AO start | 7 /248 | 228 /264 | 235 /460 (51.09%) | 52 | 445 /460 (96.74%) |
| Generation 8 | 5 /248 | 219 /264 | 224 /433 (51.73%) | 79 | 424 /433 (97.92%) |
| Generation 24 | 12 /248 | 245 /264 | 257 /489 (52.56%) | 23 | 470 /489 (96.11%) |

Completion rises from 89.84% to 95.51% over the ancestor. Correct narrow choices increase only
0.009766 ±0.008511 per life. The observer's conditional response is the probability of a narrow physical
hit after a narrow cue minus that probability after a broad cue. Among completed choices it changes from
−0.002648 to +0.022855; the paired gain is **0.025503 ±0.023872**, unresolved. The corresponding
per-opportunity gain is 0.023949 ±0.022242, also unresolved. Class frequencies and completion rates matter;
overall accuracy near one half is not the primary test of information use.

The diagnostic worlds do not establish a new conditional response either:

| World | Final minus start F | Conditional-response gain among completed choices | Final broad-hit share |
|---|---:|---:|---:|
| Trained matching T85 | +1.194293 ±0.101150 | +0.025503 ±0.023872 | 96.11% |
| Repeated matching T1024 | +0.555224 ±0.027316 | +0.006070 ±0.003697 | 98.23% |
| Short blank, T85 | +1.301697 ±0.181664 | +0.041610 ±0.029412 | 93.22% |
| Reserved delay/distance combination | +0.729445 ±0.101688 | −0.022660 ±0.027172 | 95.36% |

Repeated matching does add correct narrow choices (+0.072266 ±0.019188 per life), but physical narrow
hits after broad cues also increase; the conditional-response gain remains unresolved. Repeated trials
are clustered by life for uncertainty. Shorter blanks alter the number of opportunities too, so this is
not an isolated memory-duration intervention. The reserved combination is limited parameter transfer,
not broad generalization. Its fitness gain comes entirely from savings: income changes −0.275735 F and
cost savings add +1.005181 F. Native `captures` counts the narrow physical slot in these matching worlds;
it must never be read as correct choices.

## What improved and what was lost

In trained T85, income adds +0.252757 ±0.094172 F; cost savings add +0.941535 ±0.016937 F.
The largest savings are fewer missed clicks (+0.536765 F), maintenance (+0.249689 F) and division
(+0.121358 F). Missed clicks fall by 4.5625 per life. Mean final cell count falls from 81.26 to 63.35.
Fewer empty actions are useful efficiency, but these whole-life totals do not isolate phase-dependent
withholding, a memory mechanism or a changed circuit. Wrong-choice costs slightly increase.

The generation-8 to generation-24 trained-world gain is +0.707124 ±0.098714 F, comprising +0.379136
income and +0.327988 savings. Thus the later trajectory includes better acquisition/completion as well
as economy. It still does not resolve conditional cue use, and older acquisition worsens.

| Older world | AO-start captures/life | Generation-24 captures/life | Paired change | Point retention |
|---|---:|---:|---:|---:|
| POOL | 15.763672 | 12.476562 | −3.287109 ±0.235408 | 79.15% |
| Persistent target | 5.912109 | 5.162109 | −0.750000 ±0.140817 | 87.31% |
| Longer intermittent darkness | 4.044922 | 3.589844 | −0.455078 ±0.112698 | 88.75% |

All three capture losses are resolved by the descriptive three-SE bounds. For POOL, even the upper
three-SE bound of the explicit 90% retention margin is negative (margin −1.710742 ±0.222076).
The persistent and longer-gap 90% margins remain unresolved; that differs from proving a loss exceeding
10%. Relative to the older AM reference, the final endpoint passes the persistent/longer-gap 90%
diagnostics but fails POOL. Generation 8 passes only the own-start POOL 90% diagnostic; it does not replace
the registered final endpoint. From generation 8 to 24, POOL loses a further 2.496094 ±0.219939 captures.

These findings show why net fitness, mixed-task selection and shared ancestry are insufficient evidence
of cumulative capability. The source population, midpoint and final full populations remain archived.
No endpoint has been selected after seeing confirmation results.

## Execution and verification

One ordinary search imported every ordered survivor of AO balanced24, using native RNG53233, 32 parents,
224 offspring, whole-gene crossover and two point additions. Structural operators stayed off. Selection
used four matching T85, two POOL and two persistent lives per eight, with eight further lives for the top64.
Prices and local asynchronous cell rules were unchanged. Four fixed genomes faced seven worlds on the
512 fresh shared seeds in block146. The two native nonselection growth diagnostics used the declared
T42 adapter; the principal matching task remained T85.

All **75,894 research +8 startup =75,902 calls** completed in **4,676.217354 CPU /2,315.306468 wall seconds**.
Search consumed 3,692.879535 CPU seconds; confirmation consumed 983.337819. Peak owned RSS was
346.78125 MiB. All 14,336 confirmation statuses are zero; every owned worker/group cleared. No scientific
retry, cap extension, reduced matrix or scientific-source change occurred. Preparation had a conservative
120 CPU/120 wall allowance; its separately measured subtotal was 46.98 CPU/28.03 wall seconds, with
unmetered short source/tests work explicitly disclosed in the preparation accounting.

The frozen reader and recorded-genetics replay passed in 5.62 externally measured CPU/5.62 wall seconds,
reconstructing all 5,376 offspring and 10,752 point additions and binding all32 midpoint/final rows.
The independent recount checked every one of the 56 raw/scored files and all 25,772 numerical summary
values; the maximum absolute difference is 2.91e−11. It used 1.70 CPU/1.69 wall seconds. These are saved-data
checks with zero new lives, builds or genetic draws. Genetic replay verifies recorded operations and
survivors; it does not independently establish selection rankings from unlogged parent scores.

The staged public archive also reproduces the frozen summary byte-for-byte and the recorded-genetics
result exactly. Packaging used 0.49 CPU/0.49 wall seconds; saved-data replay used 3.02 CPU/3.02 wall
seconds. Those checks run no lives or builds. Their receipts and the verified pre-receipt manifest remain
in `publication_history/`; final manifest verification also covers the added receipts.

A separate fixed illustration batch added exactly 12 C-full replays and 12 JS replays. All 840 full-C
versus retained-fast-C ledger comparisons and 840 JS versus full-C ledger comparisons agree. JS also
matches all 60 full-C trajectory hashes and 4,067 spike time/UID pairs. Supplied-state UI checks
pass; browser rendering is untested. Execution plus assembly used 6.79 CPU/6.71 wall seconds, with all
owned processes cleared. These 24 illustration replays are separate from the 75,902 scientific/startup
calls. The [viewer](../../results/atlas/delayed_match_evolution.html) exposes only three predetermined genomes
and the first four confirmation seeds. It is illustrative, not the basis for the statistical conclusions.

Protocol: `2941610e25eb55f5e3b4ca2f0be91db46931573b24788bb85709c5b8464d9345`.
Summary: `80963876c2df5b3a8bd3305ec9fe5b9c21783d6a8831e0c80a223f3b3fe91a33`.
Prospective commit: `382761c`. The complete archive preserves the original registration under
`registration_history/`, raw/scored bytes, checkpoints, logs, frozen readers and independent audit.

## Next direction

I would not extend this exact search merely because its net fitness rose. The desired conditional ability
is unresolved and old acquisition declined. This one continuation does not prove that matching is
unreachable, that more generations cannot work, or that prices/search operators are optimal.

The next priority is a persistent, depletable resource environment in which familiar pursuit pays
immediately and nearby additions can help independently: fewer empty actions, switching between patches,
and useful revisits. Only harvested resources minus physical costs would pay; no named behavior or
hand-designed circuit would be rewarded. Fixed physical laws and locally visible consequences should
allow several profitable partial strategies. Information-payoff controls must still establish that richer
use of observations can earn enough to matter; a hand-built winning tissue is not required.

Choose and register the next full source population explicitly, retaining this result as a comparison;
the new endpoint should keep earlier useful abilities and transfer to reserved combinations without
per-case evolution. The complete AO balanced population is the leading starting candidate because this
continuation adds no demonstrated matching skill and loses substantial POOL acquisition. That is a
future-study choice, not replacement of this study's final endpoint. See the
[cumulative-primitives assessment](discussion/cumulative_primitives_direction.md). No new world or
evolution run is released by this report. Local compute remains adequate; no paid resources are needed.
