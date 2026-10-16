The registered T85 information diagnostic passed its section 0.4 thresholds on
512 fresh paired confirmation seeds. Retaining observed sample evidence improved
whole-life fitness by **2.9455 ± 0.1433 F** relative to erasing that evidence.
The retained instrument completed 480/512 choices, with 479 correct and one wrong.
This establishes a payoff from retained sample information for this external,
fully assembled instrument in the exact short-horizon world. It does not establish
an evolved cellular mechanism or admission of a longer repeated task.

The frozen run used 1,024 development calls on seeds 52,440,000–52,440,063 and
5,632 confirmation calls on seeds 52,450,000–52,450,511: eleven roles sharing each
confirmation seed. Development selected instrument setting dt=0.5 and physical-hit
threshold=0.9, and reflex row 0 (the first of four tied maxima). Selection preceded
confirmation. All 6,656 scientific calls completed with native status 0; no row,
seed or arm was replaced. Forty earlier engineering calls bring the package to
6,696 calls. Sources: [protocol](prelaunch/PROTOCOL.md),
[selection](prelaunch/selection.json), [terminal summary](prelaunch/summary.json),
and [independent raw recount](terminal_audit/audit_receipt.json).

All ± values below are one standard error over 512 life clusters; contrast errors
use paired differences. I retains the sealed sample statistic; E erases it at
time 30; P never retains it; N/B choose fixed narrow/broad targets using the same
choice-scene inference and planner. R0 is the unchanged ordinary reflex; R1 is
the development-selected reflex. D0 is inert, D1 reduces R1 sensor gains, D2 reduces
active action gains, and D3 uses the smaller 32-cell footprint. All other roles
start with 56 cells. Exact definitions are in [selected arms](prelaunch/selected_arms.json).

| Role | Whole-life F, mean ± SE |
|---|---:|
| I | 4.349603 ± 0.065334 |
| E | 1.404111 ± 0.141905 |
| P | 1.404111 ± 0.141905 |
| N | 1.435944 ± 0.142257 |
| B | 1.326841 ± 0.141699 |
| R0 | −1.137377 ± 0.000158 |
| R1 | −1.130468 ± 0.000091 |
| D0 | −1.120000 ± <0.000001 |
| D1 | −1.124844 ± 0.000052 |
| D2 | −1.130468 ± 0.000091 |
| D3 | −0.648077 ± 0.000124 |

| Paired contrast | Mean ± SE, F | Registered test |
|---|---:|---|
| I−R0 | 5.4870 ± 0.0654 | Pass: mean ≥1 and >3 SE |
| I−R1 | 5.4801 ± 0.0653 | Pass: mean ≥1 and >3 SE |
| I−E | 2.9455 ± 0.1433 | Pass: mean ≥1 and >3 SE |
| I−N | 2.9137 ± 0.1549 | Descriptive fixed-width control |
| I−B | 3.0228 ± 0.1451 | Descriptive fixed-width control |

E/P matched bitwise on all 512 pairs, including all native ledgers, five hash
families, spikes, fates and post-erasure diagnostics. All 512 I/E pairs shared
the sealed sample summary and pre-choice spike prefix. The controls still made
physical choices: E/P completion coverage was 94.14%, compared with I's 93.75%.
The ablation therefore did not disable clicking or make physical completion rare.

Every do-less point margin, defined as 0.25I+0.75R−D, was positive. The largest
do-less gain was D3−R0=0.4893 F, below one quarter of I−R0 (1.3717 F).
All lower-three-SE margins were also positive, an uncertainty check beyond the
registered point criterion rather than an added admission gate.

| Margin | Against R0, mean ± SE | Against R1, mean ± SE |
|---|---:|---:|
| D0 | 1.3544 ± 0.0163 | 1.3595 ± 0.0163 |
| D1 | 1.3592 ± 0.0163 | 1.3644 ± 0.0163 |
| D2 | 1.3648 ± 0.0163 | 1.3700 ± 0.0163 |
| D3 | 0.8824 ± 0.0163 | 0.8876 ± 0.0163 |

Each role encountered 257 narrow-class and 255 broad-class opportunities. There
were no carry-ins or timeouts. Counts below are correct/wrong/unfinished; coverage
means any completed physical choice. E and P have identical results. Each of the
six roles in the last row independently has the displayed counts.

| Role | Narrow counts | Narrow coverage | Broad counts | Broad coverage |
|---|---:|---:|---:|---:|
| I | 242 / 0 / 15 | 94.16% | 237 / 1 / 17 | 93.33% |
| E, P | 130 / 110 / 17 | 93.39% | 116 / 126 / 13 | 94.90% |
| N | 249 / 0 / 8 | 96.89% | 0 / 239 / 16 | 93.73% |
| B | 0 / 242 / 15 | 94.16% | 240 / 0 / 15 | 94.12% |
| R0, R1, D0, D1, D2, D3 | 0 / 0 / 257 | 0% | 0 / 0 / 255 | 0% |

I's conditional accuracy among completed choices was 100% for narrow and 99.58%
for broad; correct choices per opportunity were 94.16% and 92.94%. E/P's completed
choice accuracy was 54.17% and 47.93%, respectively. The fixed-width controls
completed both classes but were rewarded only for their preferred class. These
class results support matching beyond a fixed-width bias. Positive F alone would
be insufficient because a blind completed choice has positive expected gross return.

The sealed sample classifier was correct on 511/512 cases (99.80%): 257/257
narrow, 254/255 broad. One broad sample was classified narrow. Pooled Brier score
was 0.0007084 and log loss 0.0018133; class-specific values were respectively
0.0000000249 / 0.0000222 for narrow and 0.0014223 / 0.0036184 for broad. All 512
labels were available from the sole native opened opportunity; none was missing.
These are observer-side classification readouts, distinct from the 479 correct
physical choices and 32 unfinished opportunities. True class, phase, seed and
target coordinates never entered the controller.
[Class-conditional calibration](terminal_calibration.json) retains the exact values.

Each instrument arm issued one tap callback per life. Mean callback times were
70.3691 (I), 69.6094 (E/P), 70.3916 (N) and 70.4541 (B). These are attempted-tap
times, not observed capture times. Actual capture times and a reflex first-trial
decomposition were not instrumented. Whole-life accounting retained any possible
extra reflex opportunity; none occurred in this run.

The following are mean energy costs per T85 life, before division by 85 to
obtain F. Division, secretion and guard charges were zero for every role.
Messages and receptors are separate native charges. Income is 500 per correct
choice; the wrong-choice charge is 50 per wrong choice.

| Role | Income | Maintenance | Spikes | Twitch | Messages | Receptors | Misses | Wrong | Total cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| I | 467.7734 | 95.2000 | 1.4115 | 0.0683 | 0.3273 | 0.3273 | 0.6250 | 0.0977 | 98.0572 |
| E | 240.2344 | 95.2000 | 1.3560 | 0.0499 | 0.3231 | 0.3231 | 0.5859 | 23.0469 | 120.8850 |
| P | 240.2344 | 95.2000 | 1.3560 | 0.0499 | 0.3231 | 0.3231 | 0.5859 | 23.0469 | 120.8850 |
| N | 243.1641 | 95.2000 | 1.3888 | 0.0690 | 0.3213 | 0.3213 | 0.4688 | 23.3398 | 121.1088 |
| B | 234.3750 | 95.2000 | 1.4382 | 0.0699 | 0.3334 | 0.3334 | 0.5859 | 23.6328 | 121.5935 |
| R0 | 0 | 95.2000 | 1.0667 | 0 | 0 | 0.4103 | 0 | 0 | 96.6770 |
| R1 | 0 | 95.2000 | 0.6846 | 0 | 0 | 0.2052 | 0 | 0 | 96.0898 |
| D0 | 0 | 95.2000 | 0 | 0 | 0 | 0 | 0 | 0 | 95.2000 |
| D1 | 0 | 95.2000 | 0.3092 | 0 | 0 | 0.1026 | 0 | 0 | 95.6117 |
| D2 | 0 | 95.2000 | 0.6846 | 0 | 0 | 0.2052 | 0 | 0 | 96.0898 |
| D3 | 0 | 54.4000 | 0.5255 | 0 | 0 | 0.1610 | 0 | 0 | 55.0865 |

The scientific monitor used 573.692 CPU seconds and 609.873 wall seconds, with
peak owned RSS 329.61 MiB. Adding the prior 50.93 CPU / 46.38 wall allocation gives
624.622 CPU / 656.253 wall seconds. The independent raw recount added 8.78 CPU /
8.80 wall seconds; packaging and class-calibration analysis added 2.42 CPU / 2.43
wall seconds. Through those terminal checks, measured/allocated totals are
**635.82 CPU / 667.48 wall seconds**, below the cumulative 3,600 CPU / 5,400 wall
caps. Publication verification is accounted separately. Execution used one worker
and one thread, an 8 GiB address-space cap, a 4 GiB RSS cap and a 4 GiB host-memory
floor. The monitor finished successfully with no owned worker or descendant left.
See [budget](prelaunch/budget.json), [audit resources](terminal_audit/audit_resources.txt)
and [packaging resources](terminal_package_resources.txt).

[raw.tar.gz](raw.tar.gz) preserves all 6,656 original NPZ byte streams in sorted
`prelaunch/raw/...` members, with normalized tar metadata and fixed gzip mtime.
Every archived member was rehashed against the original row index; originals remain
in place. Archive SHA256 is
`9274b34264776f021de0f8c03e95c137a75566ad1f5db5e482833bd4eaf44291`.
The [archive receipt](raw_archive_receipt.json) pins inputs, metadata and calibration.
Packaging and all terminal analysis made zero simulator calls, builds or random draws.

The strong retained-versus-erased contrast isolates useful sample information
within the matched external instrument. The ordinary finite reflex and do-less
families made no movement or choices, so their large F gaps also include a
competent action policy; they do not establish superiority over all reflex designs.
N/B and E/P provide the active-policy controls. The instrument's inference and
memory are external computations, with native physical receptor/relay/action
charges, not an evolved implementation with measured cellular computational cost.
Its preassembled footprint does not establish accessibility from the continuing
lineage's one-cell developmental start. Repeated-trial matching, T1024 admission,
evolved behavior and a mutation gradient remain unmeasured. No continuation or
additional simulation follows automatically from this report.
