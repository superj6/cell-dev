# Independent review: delayed-matching information instrument

2026-10-15. Source and saved-data review only: no simulation, build, new seed selection or scientific random draw.

Reviewed [INFORMATION_PAYOFF_PLAN.md](../abi5_delayed_match_20261015/coordination/INFORMATION_PAYOFF_PLAN.md),
SHA256 `9bb6936ac2fd2735ff6b53700743d6d5e687878e275fe69e00cde7d44a87f437`, against the ABI5 proposal,
the isolated world/scoring implementation, plan section 0.4, and the historical controller API.

**Disposition: suitable for source preparation.** The timing, controls and accounting form a coherent
information diagnostic. Scientific execution still needs the plan's exact source/input freeze and bounded
runtime inventory. The principal remaining implementation detail is the neutral-posterior action rule below;
no broader controller search or new admission requirement is needed.

## Retained evidence and action policy

The proposed I/E comparison can isolate the contribution of retained sample evidence in this external
instrument. All instrument arms have the same inert footprint, receptor charges and absence of commands
before t65.5. They seal sample evidence into L, discard other sample history, and initialize identical choice
geometry inference. E erases only L at t30. The proposed bitwise E/P command and ledger comparison is a useful
direct check against unintended sample channels. Own efference, queued commands, diagnostics and inference
buffers must not retain a second sample-dependent input. Free central computation and an external clock remain
instrument privileges, not capabilities added to tissue.

Freeze an action rule in which **L=0 still allows ordinary pursuit and clicking at a real choice**. Do not
steer toward the posterior-average midpoint between the two targets: that would cripple the erased arm.
The 0.75/0.9 tap threshold must refer to the **physical hit probability of the selected target**, conditional
on current geometry, not rewarded-choice correctness. With L=0 the correctness probability is at most 0.5;
using a correctness threshold above 0.5 would silence E by construction. Select target alternatives by a fixed
expected-payoff/hit rule, with sample-independent tie-breaking; retain the same planner and motor capacities
in I/E/P/N/B. Pin quadrature weights, target selection, steering objective and the tap event definition before
scientific registration. The fixed narrow/broad controls remain important checks against an unnecessarily weak
neutral-posterior policy. If either matches I, report that limitation even if another contrast passes.

## Timing, geometry and physical costs

The fixed bounds are valid for this preset. Deliveries in [0.5,14) originate in the sample, with exposure
duration 13.5. Erasure at t30 lies after all sample deliveries and before the first possible choice. With no
earlier movement or click, the first choice is present at t65.5 and cannot time out strictly before t85.
Emission-time sensor coordinates, including delivery delay, must be reconstructed from own actions.
Fresh geometry inference must include both Gaussian tails and must not use L. Geometry is independent of
sample class conditional on body state; the identical inactive prefix makes that condition particularly clean.

The late instrument can resolve at most one opportunity. An unrestricted reflex can open a second choice
after t75, and may retain sample consequences through its ordinary dynamics. Whole-life F must retain those
actions, rewards, costs and extra opportunities. First-trial readouts are a separate matching diagnostic and
cannot replace whole-life admission comparisons. No realized phase, timeout, correctness or success feedback
may enter controller decisions, including the rule for stopping after an attempted tap.

The ideal equal-coverage first-trial difference is (500−225)/85 = 3.235294 F. At equal costs and full coverage,
exceeding 1 F needs accuracy above 0.5+85/550 = 65.4545%; actual coverage and extra costs can erase this margin.
Thus the 1 F bar is feasible algebraically, not established empirically. A blind reflex completing two choices
could earn expected gross 450, leaving only 50/85 = 0.588235 F below a perfect one-choice instrument before
cost differences. This is another reason to retain whole-life comparison and avoid a guaranteed-headroom claim.
Report all physical charges; equal prefixes cancel in I−E, while action and coverage costs legitimately differ.

## Controls, scope and development

The finite reflex panel, disjoint tuning seeds, retained R0/R1 comparisons, same-footprint instrument, fixed-width
controls and four quiet/smaller controls address the main alternatives. “Best” must remain explicitly conditional
on those measured panels. The paired do-less margin is algebraically correct. Its extra lower-three-SE condition
is a declared conservative operational choice; do not present it as additional wording from plan section 0.4.
Report class-specific coverage/correctness and the full class-by-choice table, so one-class selective action is
not described as general matching. All 512 seeds are life clusters, including any additional trials.

T85 is a diagnostic, not an automatically chosen evolutionary setting or admission of the repeated T1024 world.
A fixed footprint has spatial sensors at birth, whereas a GRN develops from one cell. I inspected existing
engineering fates in `../abi5_delayed_match_20261015/validation/truth_conservation_fix/truth.json`
(SHA256 `7c0a040ec715fdf65ed51a285f48c46a1c9b1440f6f1774fab3d819462c844db`). The two unguarded historical s5
fixtures, seeds 42000002/42000003, first gain off-center sense cells at relative t3.827282/t4.602746;
they have 13/11 off-center senses at t14 and 16/14 at t15. These existing traces show that early spatial sensing
is possible in those fixtures, but they are not AN/AO and establish neither continuing-lineage accessibility
nor matching. Inspect available lineage development evidence when choosing the next setting, without turning
a hand-built winner into a gate. Preserve repeated-trial support in the harness for subsequent measurement.

The arithmetic is consistent: 40 engineering + 1,024 development + 5,632 confirmation = 6,696 maximum calls.
All backends, compilation, failed engineering attempts and cleanup must count within the stated 3,600 CPU-second
budget, including its engineering sublimit and confirmation reserve. Throughput and controller quality remain
unknown. Insufficient budget yields an incomplete bounded study, not fewer confirmation seeds or removed arms.

No production, proposal, frozen archive, viewer or study result was changed by this review.

## Final wording check

The revised plan SHA256 `bfddd13cbce7067bb0a049d2df2c7988b1256a3a7821657af44d42ecd6e6382c` explicitly adds
real-target selection at L=0, sample-independent ties, the physical-hit threshold, and the T85/developmental
scope limitation. These resolve the substantive wording concerns. **Accepted for the planned source
preparation and bounded engineering checks**, subject to verifying those already stated semantics in the
actual controller implementation before scientific registration. This review does not claim instrument
performance, admit a world, or release scientific execution.

The final plan SHA256 `4d5ba8428e4a2769132d90fbdd7a948c2a49ea1ca7472b2f76833ba40452a15f` also retains
section 0.4's existing do-less point threshold and reports paired three-SE margins as uncertainty, without
adding another admission gate. This supersedes the earlier draft's conservative extra gate discussed above.
Acceptance is unchanged; no further conceptual correction is outstanding.
