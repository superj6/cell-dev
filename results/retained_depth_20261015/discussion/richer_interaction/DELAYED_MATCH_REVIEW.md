**Review verdict: the concrete delayed-matching contract is technically ready for scoped implementation.** The [ABI5 proposal](../../docs/ABI5_DELAYED_MATCH_PROPOSAL.md) resolves the material gaps identified in the [initial candidate](RICHER_INTERACTION_CANDIDATE.md). This is a source/document review: the reviewer performed no implementation, registration or simulation and did not inspect AO outcomes. After this review, the root agent reported the user's instruction, ‘you don't need my permission for these things’; the scoped implementation may proceed under that authorization. This review does not create a separate approval gate.

Reviewed proposal SHA-256: `239f68a70017fff1b69eac4f85fdda3dbe174643fe22a0a9a24ee00bc3f09468`.

The original blockers and their resolution are:

| Issue | Resolution in the reviewed proposal |
|---|---|
| Geometry/current-scene independence | Fresh axis, radius and side assignment are independent of sample class conditional on the body's choice-onset state. Sample-dependent movement, morphology, chemicals and motor state are legitimate retained information. Centers are stationary after their respective onsets. |
| Widths/equal peaks | Equal Gaussian component amplitude is distinguished from summed-field intensity and integrated signal. The cue is Gaussian width/intensity profile; abstract brightness-independent shape recognition is not claimed. Fixed preferences remain measured alternatives. |
| Conditional reward and costs | Physical `captures`/`b2_clicks` retain slot-hit meanings. New class-specific correct/wrong counts drive conditional reward/penalty in the kernel and scorer. Mode 0 preserves the old formula. Wrong choices must not also be charged as misses. |
| Random streams | New counter-hash purposes are keyed by trial index, independent of cell/legacy streams and correctness. Receptor candidates keep one constant two-component bound across all phases. |
| Timing and pending pings | Existing strict-before `world_to` semantics persist. A click exactly at timeout can resolve the trial first. Immediate eligibility consumption plus deferred physical removal prevents repeated same-group rewards without changing that group's receptor field. Pending deliveries remain intact; `blank_min>d_min` guarantees raw sample pings arrive before choices. |
| Trial/window boundaries | First SAMPLE starts at `t0`; `t_open` opens accounting without resetting physics. Per-class opened/carry-in/correct/wrong/timeout/unfinished counts conserve opportunities. Actual life end or guard termination can leave a choice unfinished. Extinction preserves the existing world-to-T progression, including later opportunities/timeouts. |
| Task-mode compatibility | Explicit V5, seven appended fields, a neutral legacy mode and a small stationary CATCH-only combination prevent accidental visibility/renewal/motion mixtures. This exceeds the [ABI4 approval](../../docs/ABI4_VISIBILITY_PROPOSAL.md) and correctly requires a new decision. |
| C/Python/JS scope | Includes packing, loading, export, scoring and maintained automatic JS two-choice physics/rendering. It preserves legacy pins and rejects interactive dragging. It does not silently promise arbitrary historical two-blob or unsupported JS modes. |
| Pilot versus admission | The loose 128-pair proposal is replaced by a real call inventory and at least 512 fresh tuning-disjoint pairs for admission. A smaller pilot remains diagnostic. |

**Finite details to settle during implementation, within those approved semantics:**

- Freeze stream IDs after 26, exact keys/uniform arithmetic, class/side bit thresholds and draw timing. A simple implementation draws each trial's independent latent tuple once at sample onset. Preserve old streams/counters. Trial start times remain response-dependent, even though latent draws are independent; pair by trial index rather than assuming identical wall-clock phases.
- Fix physical slot identity independently of correctness; narrow and broad fixed slots with randomized side assignment are sufficient. Apply the mode-specific wrong-choice cost in C close, Python reference, `spec.column_cost`/fitness repricing, JS and readouts. Reconcile event-summed and reconstructed costs without retaining the old slot-1 harm term as an additional charge.
- Define carry-in at the left limit of `t0+t_open` for a nonempty accounting interval. A choice opening exactly at that instant is opened in-window; one resolving there was carried in. Exclude events exactly at `t_end`. Cancel a stale timeout after an exact-deadline hit. No phase boundary rearms the hotspot or resets cellular/motor state.
- Define tagged world hash records and their fold order, including trial initialization, phase changes, frozen choice assignment, resolution and terminal phase. New raw V5 `all` hashes may differ through appended ledger folds; legacy caller projections must remain byte-identical. Keep `CURRENT=V2` and strict checkpoint/source pins unless separately authorized.
- The proposal's nearest-active-choice distance/zone convention is coherent: count only CHOICE samples, document that mode-specific meaning, and never include an absent/stale target. Use the new task readouts for matching performance.
- Require C/Python parity over the supported mode, C fast/full ledger equality, and C/Python/JS full-mode parity over their common supported subset. Fast hash constants do not establish replay. Focus fixtures on both classes/sides, all boundary ties, repeated clicks, pending pings, nonzero `t0`, window crossings, life-end/guard/extinction and invalid combinations. Existing bodies are execution fixtures; they need not win.

**Interpretation and admission:** +500/−50 gives a sample-blind successful chooser +225 expected payoff per resolved opportunity before costs. Positive fitness alone therefore does not establish matching. Class-conditioned choices, coverage, timeouts/unfinished trials, payoff per opportunity, costs and elapsed-time fitness are all needed; opportunity throughput is behavior-dependent.

The external information instrument should receive only the same receptor pings and ordinary action/cost interface, without true class/phase/target coordinates or identity from simulator bookkeeping. Free central computation remains an acknowledged measurement advantage. A sample-denied comparison can also alter pre-choice actions, charges and retained body state. For the capability-specific contrast, narrowly remove or randomize the instrument's retained sample-class estimate while preserving current-scene processing and other state, with matched pre-choice action policy where needed. That tests the instrument's use of history, not an evolved cellular mechanism.

[Plan 0.4](../../docs/TASK_VARIATION_PLAN.md#L582) currently requires at least 512 fresh tuning-disjoint pairs, an information gap exceeding 3 SE and at least 1 F at the reflex's footprint, a specific-capability contrast at those thresholds, and the do-less comparison. An engineering pass or 128-pair diagnostic cannot replace those requirements. Freeze arms, seeds, lifetime, actual backend/controller calls and resource caps before later launch. No hand-built winning-body prerequisite or further mechanism gate is needed to prepare this port.

Reviewed source SHA-256 values:

- `src/life/spec.py`: `2a3d55ec9447c38299514b146afe08e207f4e85beb96ec7938a05bc3a97db0fc`
- `src/life/kernel.c`: `3b683af571ecda2faccbd1ab2506250095b8d30e9218e8d8e5d4528866cd8683`
- `src/life/reference.py`: `8622382fa3de3f568980c131674a48823f06ffb2bdd587f920d6badcbe457662`
- `docs/ABI4_VISIBILITY_PROPOSAL.md`: `97917c3c53890d544820b3e888d03a3bfa109863778970e8a0ce7f2a78758131`
