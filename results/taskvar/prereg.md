# Task-variation preregistration, 2026-10-13

Status: engineering and bounded validation only. Commit this file before any full gate measurement or evolution
launch. No large run, rental, ABI change, revised family, calendar, wounds in selection or population-responsive
world is authorized by this file. The pending decisions in `docs/HANDOFF.md` section 5 still apply.

## Admission and evidence

- `docs/TASK_VARIATION_PLAN.md` section 0 supersedes older hand-built gates. No world is rejected because a hand
  body fails. No hand-built body is required to admit a world.
- At least 512 fresh, paired lives; controller/reflex tuning and scoring seeds disjoint. Select the better whole
  frozen or re-tuned reflex by its fresh mean, never a different reference per life.
- At the reflex footprint, the information controller's gain must be at least 1 F and strictly exceed 3 paired SE.
- A capability's matched ablation must remove at least 1 F and strictly exceed 3 paired SE. This comparison can
  use a larger footprint, provided full and ablated controllers have the same footprint. The reflex-footprint
  information test remains mandatory.
- The best tested quieter/smaller reflex must gain strictly less than one quarter of the information gap.
  Report the candidate set; a limited search cannot establish an exhaustive best.
- Controllers remain external measurement tools. Require a replay leakage audit and scratch-world parity before
  accepting their evidence. Pin controller, harness, kernel, adapter and config sources. Report paired mean and SE.
- G2 is descriptive. It cannot admit, reject, stop or steer a world or population.
- Missing measurements are **incomplete**, not failed worlds. Two-life smoke results are never admission evidence.

## Gate map and launch dependencies

| Gate | Current meaning and executable path | Status before a large run |
|---|---|---|
| G0 | After E2 rebases conduction, run `python -m scripts.life_gates --world speck --threads 2 --out outputs/taskvar_e7/g0`. The current CLI has no global conduction override. | Not re-run here; current defaults are not the E2 baseline. Legacy hand-body comparisons are descriptive, never world admission. |
| G1 | `python -m scripts.taskvar_gates <scores.json>...`; plan 0.4 information admission. | Offline checker ready. New 512-life confirmation is unmeasured. No automatic launch authorization. |
| G2 | `python -m scripts.taskvar_gradient`; production base/POOL mutant screen, dry-run by default. | Four-mutant T32 smoke only. Full 256-mutant screens and fresh confirmations pending. Flash/blink/flip gradient requires E9 or separately validated scratch-genome integration. |
| G3 | Wounded-life readouts and G-1 to G-3 below; existing regen7 is a descriptive compatibility check. | Not run. W requires the user's wounds/family decisions and relevant world admission. The old regen7-win requirement is removed. No W runner is launched. |
| G4 | Re-adaptation measurement sets a calendar only after the user approves the calendar and pairing. | No runner/experiment launched. Revised POOL ↔ POOL+flip mix needs E9; do not silently fall back to old noisy pairing. |
| G5 | `python -m scripts.taskvar_gates <records...> --g5-worlds base pool ...`; requires G1 at T=768 and 1536 for every listed world. | Aggregator ready; all new duration measurements pending. Within-life worlds wait for E9 and parity. |

Base/POOL production launch also needs E1 replay, E2 and applicable engineering checks. F/M/W depend on the
unanswered decisions and E9. Passing a statistical gate never overrides those dependencies.

## Prediction and discrimination

- Reuse the interrupted study's existing PF and D2 controllers, archived unchanged in `measurement/`; no controller
  enters an organism. Recover parameter vectors and provenance rather than running old scripts with side effects.
- Score full and ablated controllers at hollow3, with the frozen/refitted hollow3 reflex and explicit do-less
  candidates. Parameters from larger tuning footprints are transferred; report that limitation.
- Prediction candidate: v_t=0.3, tau_turn=200, existing SPECK conduction (d0=1, d_min=0.5). Its recovered ablation
  sets v_m and tau_turn to zero. This tests the moving-target model, including between-ping tracking propagation
  and anticipatory actions; it does not isolate action-only lookahead. Report that contrast descriptively. The
  current config conservatively leaves the named prediction-specific gate incomplete; no claim that prediction
  fails follows. An action-only contrast or an explicit broader capability definition is follow-up work.
- Discrimination candidate: b2_amp=1, b2_sigma=1.2, b2_value=-50, b2_p=1, b2_mode=1, otherwise existing SPECK.
  D2 model=0 disables the decoy model; every other parameter is fixed. The smaller transferred reflex uses hollow3
  knobs at hollow2; it is not an independently tuned hollow2 reflex.
- Existing recovered scores do not satisfy current admission: prediction has only 8 test lives; discrimination
  has 1,024 ring5 full-controller lives but lacks matched-footprint and ablation rows. Neither has a recovered
  verified audit that can substitute for the new source-bound replay.
- The generic prototype aliases BELL constants to decoy on/off epochs. These two ABI 3 studies explicitly disable
  that unused feature in their scratch build, leaving validated world vectors unchanged. Require tissue ledger
  and world-hash parity against production, plus null/inert world parity. No large timer approximates disabling it.
- Before full measurement, report the proposed CPU/thread budget and audit results. Default scoring is 512 lives
  at T=1024; no extension is chosen after looking at a favorable score. Any extension is preregistered separately.

## Gradient protocol

- Same 256 random mutants of each parent (pilot s5, s7) in each admitted world. Use the saved pilot mutation
  operator: n_mut=2 scaled by active genes, p_cell=0.5, duplication/deletion off. Seed the mutation pool by parent.
- Initial screen: 64 paired lives at T=1024. Report the fraction with ΔF > 2 SE, full effect distribution, and
  changes in end size, clicks, captures and guard incidence. Size/click associations do not establish causation.
- Compute guard mutants remain in the denominator with their production fitness penalty; capacity failures,
  ledger mismatches, corrupt and unexplained incomplete lives invalidate the batch. Genome extinction is valid
  and uses the saved production extinction charge.
- Preserve genomes, mutation operations, per-life scores/statuses, seeds and numerical identity. Resume requires
  identical code, .so/libm, torch/ATEN, config and genomes. Checkpoint every completed genome row.
- Follow-up protocol: score the top 5% by screen mean on 512 disjoint lives; then confirm selected winners on
  another 512 disjoint lives. Lesion confirmed winners on fresh paired lives before calling a gain computational.
  The current runner implements the initial screen; selected-mutant confirmation/lesion orchestration remains
  follow-up work. Report screened and confirmed fractions separately; do not call selected fractions an unbiased DFE.

## Reserved fresh seeds

Use `fresh_seeds(n, seed0=51_000_000 + 10_000*block)`, at most 10,000 lives per block. Preserve life order.

| Blocks | Purpose |
|---|---|
| 0–9 | Bounded validation only; 0 gradient, 1/2 capability smoke, 3/4 replay |
| 10 | G2 screen, shared across parents/worlds for pairing |
| 11–12 | G2 re-score and independent confirmation |
| 20 | Prediction fresh measurement |
| 30 | Discrimination fresh measurement |
| 40–41 | G5 T=768 / 1536 |
| 50–59 | Reserved confirmations |
| 60–69 | Held-outs, never tuning |
| 70–79 | New tuning, never fresh scores |
| 80–99 | Unallocated |

Recovered knobs used historical 44.2M/44.6M tuning blocks; their ranges are recorded in the measurement configs.
New tuning must preserve the disjointness above and record any additional seed use before scoring.

## Success criteria retained from the plan

- R1: final best beats best reflex by >3 paired SE on 1,024 fresh lives; lateral_off at t=256 removes at least
  half that lead. At least one seed is programme progress. Compare P/B, F/P and M/F by one-sided Fisher p<0.05.
- R2: in POOL, best beats s5 by >3 paired SE.
- R3, descriptive: relayed receptor chains, share with at least two lateral hops, and latency by hop count.
  Claim multi-hop only with at least 15% two-hop chains and stepped latency.
- G-1: wounded best beats its division_off-at-kill fork by >3 SE. G-2: at least half killed sites refilled by T,
  reporting rim and hotspot/centre separately. G-3: final size within ±20% of unwounded size. W success requires
  at least 3/12 seeds meeting all three. B/F provide comparisons. Death's job requires the plan's 0.5 F, z>3 lesion.
- BH1: best beats the recorded hand-body yardstick by >3 SE on 1,024 fresh paired lives. This is an outcome,
  never a world gate. BH2: gain in flip/flash/blink with at least half explained by the specified capability lesion
  or dim captures. BH3: `(F_best-F_reflex)/(F_C4-F_reflex)` at the same footprint; >25% in base/POOL is progress.
- BH4, descriptive: distance during ping silence, capture-zone occupancy, clicks per capture, flip recovery,
  and dim captures. Missing ABI 4 readouts remain unmeasured.
- Keep the plan's generalisation comparison and K1/K2/K3 stop rules. No mechanism readout steers evolution.
  Money limits describe a future approved run, not permission to rent or spend now.
