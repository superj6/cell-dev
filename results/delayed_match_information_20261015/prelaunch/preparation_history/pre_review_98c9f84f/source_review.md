# Independent instrument source review

2026-10-15. **No material source blocker found for the specified T85 information diagnostic.**
This review read source and existing engineering records only: zero new simulator calls,
builds, library loads or random draws. Scientific execution remains root-controlled.

The implemented sample channel is the stated scalar L. Only I/E accumulate the 19 sample
counts, only during delivered times [0.5,14); both seal the same Poisson LLR at 14 and clear
the count buffer. E sets L to zero at 30. P/N/B never accumulate it. Geometry and action
state remain untouched by sample pings; geometry starts from the same prior at 65.5.
The sealed diagnostic is write-only. Thus erasure removes the sample-dependent decision
state without changing the paid physical prefix or current-scene inference.

The opaque controller API exposes fixed footprint/physics, own time, receptor callbacks
and own commands. `matching.c` is compiled separately and cannot see the kernel context
definition. It reads no actual class, phase, deadline, seed, reward, target, body position
or actuator-survival result. This is an auditable source boundary, not a security sandbox
against arbitrary malicious C. The wrapper's initial UID bookkeeping stays private.

The geometry likelihood uses both Gaussian tails and uniform angle/radius quadrature.
It evaluates each observation at emission time t−d_min. The core retains the whole own
impulse history, so a query into the past reconstructs position from commands that had
occurred by that time. Silence integration splits at command impulses, the anchored 0.25
grid and actual observation endpoints. Normalization flags nonfinite weights through
diagnostic 15 instead of substituting world truth. No outcome corrects the motion model;
prediction may be wrong after damage, as the specification explicitly permits.

The corrected expected gross score includes both width hit probabilities:
`(550*p_n−50)*H_n(q)+(550*(1−p_n)−50)*H_b(q)`. Neutral L chooses an actual opposing
target through this same planner. Exact ties use own eventual distance and physical
coordinates. The tap threshold uses the selected width's physical hit probability,
without multiplying by class correctness. Consequently erasure does not itself disable
tapping. N/B change only the chosen width. Steering, legal kappa quantization, conduction
latency, same-cell spacing, key prediction and stopping after one attempted tap match
the specified rule. The hotspot position check includes newly queued steering commands.

The kernel bridge charges every delivered live-cell ping for receptor reception and
one virtual relay spike/contact, independently of whether the policy uses the ping.
Actual actuator events pass through ordinary fire and its native costs; all 56 cells
retain ordinary maintenance. Central inference remains free external computation and
does not establish attainability by a local developing tissue. Scientific inputs must
bind the exact preset, footprint, inert program, latency and relay-charge settings:
the matcher validates only some of these constants and is not a generic-world policy.
The scientific driver must stop on diagnostic 15 or corrupt/truncated measurement output;
legitimate guard/extinction outcomes remain part of the declared analysis.

I checked all 11 source hashes in the policy receipt against current files and literally
reread all eight saved policy NPZs. Three E/P pairs match bitwise in native ledgers, all
hashes, rasters, fates and post-erasure diagnostics. Both I/E pairs have identical sealed
L and pre-choice rasters. Each life satisfies per-class opportunity conservation,
`rec_gain = relay contact_events = delivered callback count`, raster/spike count,
56×85 cell-time, native reward and cost reconstruction, and F. The largest absolute
native-cost reconstruction difference is 2.1742607714259066e−12.

The evidence has specific limits. The pure supplied-input replay changes inaccessible
hidden fields while stubbing motion, steering and key behavior; it demonstrates source
interface independence and policy arithmetic, not a closed-loop physical replay in
different worlds. The eight kernel policy lives cover I/E/P at dt 0.5 and threshold 0.75,
including one shifted-time E/P pair. N/B and the other declared settings are source-
reviewed branches, not additional backend fixtures. The earlier 32 bridge lives used
the earlier core before the own-history accessor extension; their historical pins are
preserved, and the eight policy lives bind the current core. Together these are the
40 authorized engineering calls, not scientific tuning or confirmation. No extra calls
are requested. Scientific payoff, successful movement/localization, GRN attainability
and repeated-trial generalization remain unmeasured.

Nonblocking documentation correction: the reviewed specification's introductory and
closing prose still describe the policy as unimplemented. Update that current-status
wording when preparing scientific sources; retain the historical receipts and these
reviewed hashes. The behavioral specification and implementation agree.

| Reviewed file | SHA256 |
| --- | --- |
| `INSTRUMENT_SPEC_DRAFT.md` | `b47aebe9472780171080df281365af6ac98dd515bd12b9a75c8d5d1188a9eed9` |
| `harness/matching.c` | `71d6df574ba3ff42d933820b848edc7c9063507b4d68eecec14829119c53f748` |
| `harness/ctl_core.c` | `0126208bede9356e2deadf383e8df93d7da058cf22a64153072828de36facee8` |
| `harness/ctl_api.h` | `fb92279a84526f5628d703d0249f0059dd88ed8d6310231fe5da17d22a5e06eb` |
| `harness/test_matching.c` | `9614a51e39febf91ed43791aa06dc9e1e4f4a1267f7e28c598fb32c21949bc13` |
| `harness/check_policy.py` | `6020e5dae78df9184fc8749b50ced312760a8bf1381c9527f73485cfb36f9885` |
| `policy_engineering/receipt.json` | `6c5f6654e23a0c3e1f6be7c4a7aee365bd69b243e83fc3f766049231255648e2` |
| `engineering_retry/receipt.json` | `64a0ad99e1a4b37deab2147ca0b5fee1f7e7f39a8773c164dcefc9db945d0fed` |
| `harness_validation_receipt.json` | `407398ec54c506dd532ca1dac400a00d9aa1b0d772820f110ae790ea709246f1` |
