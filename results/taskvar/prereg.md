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

### D. Two short production sexual continuations (2026-10-13)

Question: can ordinary evolution retain and improve the discovered s5 row38 genotype across repeated generations?
This follows the fixed one-step candidate experiment; it is not another mutation-chain screen.

Freeze two independent search seeds, 51089 and 51090, each with 16 generations in POOL-fast. Both begin from the
same archived s5 row38 genome, copied byte-for-byte into this study's inputs/founder_row38.json. Experiment B's
selection or confirmation does not choose the founder. Preserve the production 32+224 sexual loop, three initial
lives plus four recheck lives for the top64, pooled-mean top32 selection, ordinary random ties, n_mut2 scaled by
active genes, p_cell0.5, no duplication/deletion, and common duration draws from 768/1024/1536. World constants:
d0=0.5, d_min=0.25, sigma=0.4, lam_s=4.0. Other world constants and prices retain the SPECK preset.

Existing initialization loads one exact genome and fills the other31 initial parents with ordinary point-mutated
copies. These are not32 identical founders. From generation0 onward, normal gene-unit crossover and point mutation
operate. Parents are reevaluated with offspring and can be dropped; the starting genotype is not protected.
Arbitrary population.json initialization is unsupported. Exact restart uses the E1 checkpoint, including both RNGs,
population identities, slot origins and log offsets. No engine or search source changes are required.

Each run's total target is fixed at16 generations from the start. Checkpoint every4 generations; retain all offspring
lineage entries. Keep report-only16-life validation at generations0,4,8,12,15. Disable report-only inherited heldout
worlds, periodic clones, final forks/death replays, size curves, and envelope comparisons. The minimal existing final
routine uses final_top1/final_lives2: two final0 lives, two final1 lives, and two T512 growth readouts. These diagnostics
never replace final population rank0. The endpoint is exactly best_genome.json, verified against checkpoint population0.

Freeze both final rank0 genomes before the fresh endpoint measurement. Compare those two genotypes, row38 and original
pilot s5 on256 common fresh seeds from block91 (51,910,000..51,910,255), separately at T768,1024,1536 in POOL-fast.
No genotype is selected or replaced using these measurements. All four genotype identities remain in the report, even
if identical or worse. The two primary contrasts are each final genome minus row38, averaged equally across durations
within each seed, then summarized over256 seed clusters. Report every duration and contrasts against original s5 as
secondary context. Use descriptive >3-SE and +0.5-F labels; failures, guard penalties and negative changes remain.
Two search replicates are exploratory evidence of continued progress, not a population-wide estimate of reliability.
No circuit or new algorithm is inferred from fitness alone. Do not pool the correlated durations as768 independent lives.

Seed audit: the392 unique scheduled hashed run seeds (196 per run) are mutually disjoint, outside every reserved
decimal51M block0..99, and disjoint from58,690 enumerated historical pilot seeds. Confirm block91 also avoids those
hashed seeds. Growth-at-half intentionally reuses final0 seeds; duration confirmation intentionally shares block91.
Keep seed_audit.json with all actual run seeds. Existing studies reserve blocks80..88; blocks89/90 remain unallocated.

Budget: 32,768 selection lives +160 validation lives +12 minimal final lives +3,072 confirmation lives =36,012
genome-lives, plus ordinary startup golden replay checks. Four minimal final lives end at T512. Deterministic training
duration means are1040 for seed51089 and1104 for seed51090, totaling34,304 T1024-equivalent selection lives.
Use at most four simulation workers (two evolution jobs with two threads each; subsequent confirmation has two).
The shared hard budget is10,800 CPU-seconds (three CPU-hours), including evolution, diagnostics and confirmation.
Monitor process CPU with a10-second reserve before termination. Budget interruption preserves completed E1 checkpoints
and confirmation rows; report an incomplete experiment if either run or confirmation cannot finish. Do not extend
the cap, add search seeds, replace endpoints, or increase lives after seeing scores.

Execution is prepared under outputs/autonomous_continuation_20261013/. run_budgeted.py defaults to dry-run and requires
a root-created ready.json binding the runner, protocol and measurement helper sources before --run. Preserve source,
numerical and genotype pins, full confirmation ledgers, hashes, seeds, logs and resource accounting. Report and commit
this protocol before launch. Source code must remain fixed while these runs are active.

### E. Lateral dependence with tissue held fixed (2026-10-13)

- Fix original pilot s5 and the archived row38 mutant in POOL-fast, independent of B/D outcomes. Use the existing
  ABI-3 interventions only. Four conditions per genotype: normal, freeze, lateral_off, freeze+lateral_off.
  All lives have T1536, fork at768 and fitness accounting from800 to1536 (a736-unit window).
- The freeze stops further gene/phenotype updates and new division/death decisions. Membrane dynamics, receptor
  inputs, spikes and chemical transport continue. Lateral_off suppresses creation of new in-plane spike messages;
  already emitted messages still arrive. Vertical spikes continue. Neither intervention enters selection.
- A32-unit settling interval excludes pending pre-fork claims and spike deliveries from the measurement window;
  it does not erase earlier membrane, chemical, movement or world history. At these fixed settings claims resolve
  by768.25 and their notices by768.75; the bounded spike-delay formula puts pre-fork deliveries before771.003.
  Assert zero post-open births/deaths and last_birth<800 in frozen arms. For complete guard-free pairs, also assert
  equal final cell count between the two frozen arms and cell-time equal to736 times the constant cell count.
- Use512 common fresh block92 seeds for all eight arms:4,096 genome-lives. Preserve guard/extinction penalties and
  reject capacity/mismatch/corrupt or unexplained incomplete lives. Report structural checks and guard incidence.
- Primary contrast: `(winner-parent)freeze - (winner-parent)freeze+lateral_off`, paired per seed before mean/SE.
  Also report the analogous unfrozen interaction, all four winner-parent contrasts, their difference under freeze,
  each genotype's lateral loss, and gain lost under freeze. Report raw effects with descriptive3-SE signs; do not
  extend lives, replace genotypes or change the measurement window after scores. Keep all income/cost components.
- A positive primary contrast supports increased lateral dependence in tissue held fixed after this intervention.
  The genotypes' footprints differ, so it does not establish a new algorithm or matched-footprint information use.
  A loss of gain under freeze cannot by itself distinguish developmental benefit from computation by gene activity.
  End size, path, n_peak and last_birth remain whole-life descriptors; the F/capture/cost contrast uses800..1536.
- Cap this study at one CPU-hour with two workers, never exceeding four concurrent simulation workers across all
  studies. Save atomic rows, full production ledgers and source/numerical/genome pins under
  `outputs/autonomous_frozen_20261013/`. Archive and report both positive and negative results.

### F. Existing discrimination controller at the reflex footprint (2026-10-14)

Question: at the same 56-cell footprint, does interpreting which glow belongs to a harmful decoy earn more
than ordinary target tracking? Use the existing recovered D2 controller unchanged as an external measuring
tool. It never enters an organism or changes its local asynchronous rules. No new controller is designed.

Use the registered discrimination world: existing ABI 3 SPECK with b2_amp=1, b2_sigma=1.2, b2_value=-50,
b2_p=1, b2_mode=1 and T=1024. Preserve old conduction d0=1, d_min=0.5, every other world constant and every
price. The second blob has its own replacement process; no scratch blinking, decoy epochs or motor flip
is enabled. The existing parity-checked adapter disables the prototype's otherwise aliased decoy-epoch fields.

Freeze seven candidates in the existing taskvar_measure order: frozen hollow3 reflex; recovered retuned
hollow3 reflex; frozen hollow2 reflex; hollow3 reflex knobs transferred to hollow2; recovered hollow3 reflex
with K.t_ref=8; full D2 at hollow3; its matched ablation at hollow3. Full and ablated differ only at parameter
25, model 1 versus model 0. Keep all other recovered parameters, including transfer from their ring5 tuning.
The ablation removes the whole decoy model: ping attribution, decoy belief, steering avoidance and tap veto.
It isolates broad decoy-aware inference and action, not a single classifier or tap rule. Ordinary target
tracking remains. Failure of this fixed transferred controller does not establish that the information is useless.

Score every candidate on the same 512 fresh block-30 seeds, 51,300,000 through 51,300,511: 3,584 candidate-lives
in total. No fresh tuning or extensions chosen after seeing outcomes. These lives are disjoint from recorded
controller/reflex tuning and existing validation. Keep every candidate, including negative results. Controller
actions retain the existing d0 latency, relay charging, t_ref_min=0.5, unquantized kappa and privileged=false.
Cells, receptor pings, virtual relay spikes and actions pay; central controller computation remains free.

Primary contrasts: full minus the better whole frozen/retuned hollow3 reflex, and full minus matched ablated
D2. Pick the better reflex by its fresh whole-candidate mean, never per life. Apply the existing plan 0.4
criteria descriptively: at least 1 F and strictly more than 3 paired SE for both contrasts; the best of the
three specified do-less candidates must gain less than one quarter of the information gap. This limited
do-less set is not an exhaustive optimum. Compute differences within each shared life before estimating
uncertainty. The chosen-reflex SE is conditional and descriptive, not adjusted for selecting that reference
on these same outcomes. Also report full D2 minus each fixed frozen and retuned reflex separately.

Report paired fitness, captures, clicks, misses, poison clicks, travel and capture-zone samples. Decompose
fitness into extra capture income, poison-cost saving, miss-cost saving and other costs. These accounting
pieces do not establish an evolved algorithm. No verdict automatically admits this world into selection.
Any compute guard, capacity failure, ledger mismatch, corrupt result or unexplained incomplete life rejects
the entire affected candidate batch and leaves the study incomplete. Preserve the failed raw evidence when
available; never selectively drop or replace individual lives. Negative, valid scores remain in the analysis.

Existing audits remain source/config identical: two T=64 lives per full/ablated variant, three replay contexts
each (12 bytewise comparisons), production tissue ledger/world parity and null/inert world parity. Saved
callback/action NPZs are checked before use. This bounded evidence is not universal long-duration parity.
No additional validation or scientific lives run during preparation. Numerical pinning reads Python,
NumPy/torch, compiler, libm and source identities without calling golden_life. The generated scratch source
and fast library are hashed before scientific scoring. Fast event hashes are not accumulated and never claimed
as replay evidence; atomic candidate-file SHA256 receipts protect stored ledgers and diagnostics. Post-run
correction (2026-10-14): the fast build retains its initial hash constant `0x243f6a8885a308d3`, rather than zero.
Frozen preparation bytes remain unchanged; the final archive records this documentation erratum.

Use at most two simulation workers and no more than four across all active studies. Launch only after root
reports this protocol and releases source pins in ready.json. A separate monitor enforces one cumulative
1,800 CPU-second cap, including worker startup, compilation and monitoring. Historical hollow3 controller
and reflex timings suggest roughly 750 CPU-seconds; charging both controllers at the old ring5 rate gives
1,365 CPU-seconds. Those old epoch-aliased scores supply timing estimates only, not scientific evidence here.
Stop 10 CPU-seconds before the cap and terminate only this worker's process group. Preserve completed
candidate checkpoints and report incomplete on cap/failure. Do not increase the cap or lives after seeing scores.

Atomic candidate directories contain full ledgers, diagnostics, exact candidate/seed/library/protocol identity,
timing and a byte-hash receipt. Resume verifies all pins and committed candidates. Only an uncommitted
interrupted candidate may repeat within the original cumulative budget; a candidate that failed validation
cannot be replaced automatically. Explicit --resume is required after a finalized interruption/failure.
A running/unfinalized old budget record requires resource reconciliation; the wrapper refuses to reset it.
Complete studies cannot be rescored. Long-running artifacts stay under outputs/autonomous_discrimination_20261013/.
The public preparation archive is results/discrimination_20261013/ and provides an offline hash/protocol checker.

### G. Fixed structural-operator comparison (prepared 2026-10-14)

This study tests whether the already approved silent-duplication and deletion operators help evolution
improve from the fixed eight-gene s5 row38 founder. A silent duplicate copies one gene's incoming regulation
and state while giving the copy no outgoing effect. Evolution can subsequently alter that spare copy.
The experiment supplies no behavior, routing weights, additional organism channel, clock or ABI change.

The two G searches use seeds 51089 and 51090, 16 generations each, and the same fixed founder, initialization,
worlds, life seeds, ordinary selection and diagnostics as the two D searches. The only evolutionary policy
changes are `dup_rate: 0.02` and `del_rate: 0.01`; `dup_split: false` remains fixed. The existing
`n_mut_scale: true` policy is retained. The policy comparison therefore includes deletion and the consequences
of active-gene-scaled mutation, rather than isolating duplication alone.

Each run starts with one exact founder plus 31 ordinary point-mutated copies. Initialization and mutation
generator state match D exactly. Structural operations start with generation-zero offspring; their random
draws then cause the mutation/crossover paths to diverge. Matching run seeds retains common world and life
seeds, not identical subsequent offspring. Selection keeps 32 from a cohort of 256, using three initial lives
and four additional lives for the top 64. There are 32,768 search genome-lives, 160 periodic validation lives,
12 fixed final diagnostic lives, and 4,608 independent confirmation lives: 37,548 research genome-lives total.

Both G endpoints and both D controls are fixed as the final population's rank-zero genome at generation 16.
All four are retained regardless of sign. Endpoints are frozen with their full checkpoint/config/source
identity before confirmation. No outcome from D is read to choose the comparison or its endpoint rule.
The control protocol, configuration and resource monitor are pinned at preparation; D endpoint hashes are
recorded only after D completes. Any invalid or mismatched search-life evidence blocks confirmation and
is reported, without changing endpoints or rerunning a replicate.

Confirmation uses all six fixed genomes in this order: original pilot, row38 founder, D seed51089 endpoint,
D seed51090 endpoint, G seed51089 endpoint, G seed51090 endpoint. Each receives the same 256 fresh seeds
51,930,000 through 51,930,255 (block93) at T=768, 1024 and 1536 in fast-conduction POOL. All measurements use
the full life from t=0. The primary contrasts are each G endpoint minus its matched D endpoint. Secondary
contrasts compare each G endpoint with row38 and the original pilot. For each contrast, the equal-duration
mean is computed within each seed before computing its mean and SE over the 256 seeds; the covariance among
durations is retained. Both signs, all durations and all fixed endpoints are reported. Gains exceeding
three SE and gains at least 0.5 F are identified separately. There is no selection from these results.

Before either G search begins, 18 validation-only full-kernel lives test silent duplication: the unmodified
founder plus one copy of each active source gene0..7 into spare slot8, with `split: false`, on fixed seeds
51,090,000 and 51,090,001 (validation block9), fast POOL T=1024. Every ledger column, event hash, spike time/UID,
and fate integer record must match bitwise. Fate floats may differ only in the added gene's state column,
which must match its source gene bitwise. Recorded status flags must also match; benign wall/chemical-clamp
flags are allowed, but extinction, guards, capacity/mismatch or log overflow fail validation. Fixed log
capacities are 100,000 spikes and 8,192 fates per life. Raw failing evidence is retained and there is no retry.
These 18 lives are outside the research-life count but inside the total CPU cap and have a separate 30-CPU-s cap.

The study has a fixed 14,400 worker-CPU-second cap, including validation, imports/builds, searches and confirmation;
there is no extension. The monitor stops at 14,380 CPU-s, sends TERM, waits at most two wall seconds and then KILL.
The reserve covers polling and shutdown with at most four simulation threads. Child CPU limits and monitor-death
termination provide independent safeguards. Neutrality uses one thread; the two searches use two each;
confirmation uses two. Launch waits for D and E completion and for any already released F work to finish,
independent of their scientific outcomes. No G readiness marker or scientific process is created by preparation.

Two search replicates do not establish general structural-search superiority. Life-level SE measures uncertainty
for these fixed endpoints, not uncertainty across evolutionary searches. A larger active-gene count, expression,
nonzero outgoing weights or duplicate ancestry alone does not establish functional use. Any later claim that
a new gene contributes to fitness requires a separate fixed intervention and independent evidence, with
developmental effects distinguished from computation in held-fixed tissue.

### H. Hidden and lateral spike dependence of fixed continuation endpoints (prepared 2026-10-14)

The completed D study found further gains in both fixed final descendants of s5 row38. H asks whether those
additional gains rely more on spike messages sent by hidden-plane cells after tissue growth has been held fixed.
Hidden cells are those at lattice height z >= 2. This measurement adds no behavior, world response, organism
channel, clock, price or ABI change. It uses existing ABI 3 interventions only.

All three genotypes are fixed before scoring: row38, D seed 51089 final population rank 0, and D seed 51090 final
population rank 0, each from generation 16. Raw genotype hashes and their completed D checkpoint hashes are pinned.
Both endpoints remain in every comparison, irrespective of sign; there is no selection by H scores or morphology.

The twelve arms are three genotypes crossed with normal, freeze, freeze+lateral_off and freeze+hidden_off.
All arms share 512 fresh seeds 51,940,000 through 51,940,511 (block94), giving 6,144 research genome-lives.
The world is POOL with fast conduction (d0=.5, d_min=.25, sigma=.4, lam_s=4), T1536. Interventions start at 768;
fitness and additive counts use the common accounting interval 800..1536 (736 time units), including normal arms.
All other physics and prices match D and E. Whole-life counters such as path and terminal tissue counts are
labeled separately from interval fitness/capture/cost accounting.

The primary contrast for each D endpoint is
`(D-row38)freeze - (D-row38)freeze+hidden_off`, computed within each life before mean and SE across 512 seeds.
Secondary contrasts report the analogous added lateral dependence, each endpoint's gain in every condition,
normal gain minus frozen gain, and each genotype's own hidden/lateral lesion loss. Both positive and negative
effects are retained. Three-SE flags are descriptive; an unresolved effect is not zero. Both descendants were
selected by D evolution, not by H, but their life-level SE does not measure uncertainty over search replicates.
Full ledgers preserve income, every cost and production guard/extinction penalties; guards are not censored.
Invalid capacity or accounting-mismatch failures stop the measurement as incomplete.

`hidden_off` prevents creation of new spike-arrival messages from senders at z >= 2, in all directions. Incoming
messages to hidden cells and already emitted messages still arrive. Hidden cells continue firing, and their
spikes and would-be outgoing messages pay the ordinary charge. Their chemical secretion/transport continues.
The effect can be indirect, through other cells in the remaining network. `lateral_off` similarly suppresses
new in-plane spike sends while retaining charges; vertical sends and chemistry continue.

`freeze` suppresses subsequent GRN/phenotype/effective-weight updates and new division/death decisions, while
membrane activity, receptors, spike generation and chemical transport continue. Claims already sent before 768
can resolve before 768.25; associated presence notices finish before 768.75. Under these fixed physics, pre-fork
spike arrivals finish by 771.002166. Opening accounting at 800 provides a settling interval, without erasing past
membrane states, chemical states or world trajectories. No adult-maturity claim is made.

For each genotype, all three frozen arms must have zero measured births/deaths and last_birth < 800. Complete,
guard-free triplets must have equal terminal total/sense/motor/hidden cell counts, t_end 1536, and live_time equal
to 736 times terminal cell count within integration tolerance. Benign wall/chemical flags are allowed. Guard or
extinct rows remain in the fitness comparisons and their exclusion from the structural check is counted.
Different genotypes may have different frozen tissue and state; this is not a matched-footprint experiment.
Freeze also changes computation, so normal-minus-freeze does not isolate development. A positive hidden or
lateral interaction establishes conditional message dependence; it does not establish a new algorithm.

The fixed cap is 3,600 worker CPU-seconds, two simulation threads, with no extension or automatic reset. The
monitor counts worker/descendant CPU, stops at 3,588 seconds, sends TERM and then KILL after at most two wall
seconds; child CPU limits and parent-death termination are independent safeguards. H waits until G's resource
record is complete with no active or queued jobs. G's scientific outcome does not change the protocol. An
abnormal G stop requires operational review before H can launch. No readiness marker or process is created by
preparation. Existing E validation supports the fixed accounting window; H preparation tests synthetic rows
and mocked processes only. Numerical-identity startup golden checks run after worker release; they are separate
from the 6,144 research lives and their CPU is included in the cap. No extra validation lives are scheduled.
