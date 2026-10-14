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
| 10 | G2 screen, shared across parents/worlds; start at 51,100,002 (first two seeds spent in validation) |
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

Validation correction (2026-10-13): a second-step CLI smoke accidentally used block10 seeds 51,100,000 and
51,100,001 for four genomes at T32 (eight lives). They are spent, even though these were plumbing checks.
The scientific G2 screen must start at 51,100,002 or use a newly registered block. The final smoke CLI uses
validation blocks8/9. No scientific blocks85–88 were used for validation.

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

## Bounded autonomous diagnostic (2026-10-13)

The user authorized autonomous work on the most promising direction after the initial engineering report. This
addendum fixes a smaller exploratory cohort before seeing its mutant scores. It does not complete the full G2
protocol above or authorize the evolution matrix, paid compute, ABI changes or new organism rules.

- Question: are useful improvements near pilot s5/s7, and does POOL make them easier to find than base?
- Worlds: existing ABI 3 SPECK, both with d0=0.5/d_min=0.25; POOL additionally sigma=0.4/lam_s=4. All prices frozen.
  These are explicit diagnostic overrides; production presets remain unchanged. T=1024 throughout.
- Screen: 64 random mutants per parent, identical genomes across worlds, 32 paired lives. Existing pilot mutation
  operator and deterministic seeds 51005/51007. This finite batch is distinct from the registered 256-mutant cohort;
  changing torch batch size need not preserve a mutation prefix. Retain every mutant and guard penalty.
- Re-score: the top ceil(5% * 64)=4 mutants per parent/world, by screen mean, ties by mutant index, on 512 fresh
  paired lives with their parent. Choose exactly one winner per parent/world from this stage, regardless of sign.
- Confirmation: winner and parent on another 512 paired lives. Report all four comparisons, even failed ones.
  A positive confirmed gain must exceed 3 paired SE; label gains >=0.5 F as practically substantial in this
  diagnostic. Report raw effects and SE regardless of these labels. No additional candidate search after looking.
- Lesion: parent and chosen winner, each intact and lateral_off from t=256, on 256 new paired lives. All four
  arms use t_open=0, so they measure the same full-life fitness. Report the paired interaction
  (winner-parent)_intact - (winner-parent)_lateral_off. This measures how much incremental gain depends on messages
  after t=256, not whether a novel algorithm evolved. Remaining development may also be affected by the lesion.
- Report fitness change as more income minus cost change and extinction-charge change. Report captures, misses,
  cell-time, end size and guard frequency. Cost reduction or size/click associations alone do not prove computation.
- Seeds: reserve formerly unallocated 51M blocks 80(screen), 81(re-score), 82(confirmation), 83(lesion), 84(optional
  descriptive context). The same stage seeds are shared across parents and worlds; stage sets are disjoint.
  Block5 held 32 parent-only benchmark lives; these never enter scoring or candidate selection.
- Compute: 8,320 screen + 10,240 re-score + 4,096 confirmation + 4,096 lesion lives = 26,752 total. A 32-life
  benchmark estimates 0.136 CPU-s/life (~1.01 CPU-h); mutant growth can cost more. At most four worker threads,
  stop at two CPU-hours across the study, preserving completed rows. No extension based on favorable results.
- Artifacts: outputs/autonomous_pool_20261013/; freeze genomes, candidate indices, source/numerical identities,
  raw per-life arrays and resource accounting. Commit concise results and selected genomes after analysis.

## Autonomous follow-through: duration transfer and a second step (2026-10-13)

The user clarified that useful autonomous experiments should continue after each milestone. The completed bounded
study is archived at `results/pool_mutants_20261013/` (commit `fbf5351`). The following choices are fixed before new
scores. They change neither organism rules nor production search/world defaults, and they do not gate worlds.

### A. Fixed-mutant transfer

- Keep all four prior parent/world winners, including the weaker s7/POOL result: s5 row38 in base and POOL,
  s7 row15 in base, s7 row29 in POOL. Parent genomes/configs and winner bytes come from the committed archive.
- Evaluate each parent and winner on 256 fresh paired lives at fast conduction (`d0=0.5,d_min=0.25`) for each
  T=768,1024,1536. Also evaluate each pair at T1024 with the original conduction (`d0=1,d_min=0.5`). Other world
  constants and prices remain fixed. Total: 4 comparisons × 2 genomes × 4 conditions × 256 = 8,192 lives.
- Use block85 for the same ordered 256 seeds in every condition. This permits paired contrasts across durations
  and conduction settings. These seeds are disjoint from discovery, rescoring, confirmation and prior lesions.
- Report each duration's paired gain and an equal-duration mixture: average the three fast-condition fitness
  differences per seed, then compute mean and SE across the 256 seed clusters. Do not count correlated durations
  as independent lives. Report `(winner-parent)fast - (winner-parent)old` at T1024 on the same seeds.
- Report all effects and costs, with >3-SE positive/negative labels and a separate +0.5-F practical label for the
  mixture. No genome is dropped, reselected or extended after observing these outcomes. This diagnoses transfer;
  old conduction in POOL does not recreate the parents' original base-world training distribution.

### B. Fixed second-generation candidates, two scoring budgets

- Fix the starting genome now as the s5 row38 mutant in POOL-fast at T1024. Experiment A does not switch this
  founder or this world. This tests another local step at T1024, not a normal multi-generation continuation.
- Generate 224 ordinary point-mutated offspring using the prior operator (`n_mut=2`, scaled by active genes,
  `p_cell=0.5`, no duplication/deletion/split), mutation seed51086. Freeze genomes and mutation operations before
  scoring. The candidate table has 225 rows; ranking expands the parent row into 32 identical parent entries and
  adds the 224 children, giving the production 256-entry competition.
- Score all 225 candidate rows on 28 shared lives from block86. Replay the production top64/keep32 selector with
  two budgets: first3 + next4 lives, and first12 + next16 lives. Within each rule the initial and recheck lives are
  disjoint. The higher-budget rule shares the initial prefix with the lower-budget rule. Use the production
  pooled-mean and random-tie code, including its diagnostic initial tie draw. Each rule starts its own tie RNG at
  seed51086 + TIE_SEED(7919001) = 7970087; mutation and tie streams remain separate.
- Freeze exactly one best final-ranked genotype per rule, even if it is the starting parent. Confirm both chosen
  genotypes, the starting mutant and original pilot s5 on 512 fresh shared lives from block87. Identical genotypes
  may share one evaluation, retaining their identity mapping. Maximum: 225×28 + 4×512 = 8,348 genome-lives.
- Primary contrasts: each chosen genotype versus the starting mutant, versus original s5, and the higher-budget
  choice versus the ordinary-budget choice. Report paired mean/SE and >3-SE/+0.5-F descriptive labels. Report both
  selectors regardless of outcome; no extra candidate search or life extension follows a favorable result.
- A further confirmed gain establishes one additional accessible step in this pool. A difference between choices
  diagnoses scoring sensitivity in this pool, not general search superiority. More scoring costs more compute;
  this is not a comparison of search strategies at equal CPU budgets. Identical starting parents and fixed T1024
  deliberately simplify crossover and duration variation. Do not call this a production continuation.

### Shared execution and evidence

- Reserve blocks85 (transfer),86 (second-step candidate scoring),87 (second-step confirmation). At most 16,540
  planned lives across A/B. The previous study's measured ~0.194 CPU-s/life suggests roughly one CPU-hour allowing
  for longer T. Use a combined two-CPU-hour cap and at most four simulation worker threads on the local host.
- Preserve every completed row atomically under `outputs/autonomous_followthrough_20261013/`, including full
  production ledgers, source/numerical identity, seeds and genome hashes. Keep valid extinction/guard penalties;
  reject capacity/mismatch/corrupt or unexplained incomplete lives. Do not edit pinned engine/search sources during
  the measurements. Commit artifacts and results at the milestone, then continue with the next useful experiment.

### C. Separate the two discovered s5 changes

- Question: does the confirmed s5 improvement require both mutations together, or is there a useful intermediate
  step? Measure the original parent, mutation A alone, mutation B alone and the observed pair AB. A is flat
  slot41 (`W[1,16]`, chemical m0 input); B is slot124 (`W[4,24]`, local is_M input). Copy the exact float32 alleles
  from archived row38. Verify that AB reconstructs that winner bitwise. These are measurement reversions of
  discovered alleles; no designed circuit or new allele value enters evolution.
- Fix 512 shared fresh lives from block88, T1024, in both base-fast and POOL, with prices and all other constants
  unchanged: 4 genotypes × 2 worlds × 512 = 4,096 lives. No tuning, selection or extension follows these scores.
- The primary contrast in each world is the per-life fitness interaction `AB - A - B + parent`, with mean and SE
  across the paired lives. This asks whether the combined effect differs from the sum of the two separate effects.
  Also report A-parent, B-parent, AB-A, AB-B and AB-parent, plus captures, cost/income rates and body size.
- Label a contrast positive or negative only beyond 3 SE; unresolved does not mean zero. Report both orders of
  mutation acquisition. Fitness interaction or a useful intermediate does not establish a new algorithm, and
  these growth-network changes need not act only in mature tissue. These measurements do not gate worlds.
- Use a separate 0.5-CPU-hour cap, two workers, with no more than four simulation workers across all studies.
  Start when the shared worker budget permits. Store all raw rows and identity pins under the existing
  `outputs/autonomous_followthrough_20261013/factorial/` directory and archive results at the next milestone.
