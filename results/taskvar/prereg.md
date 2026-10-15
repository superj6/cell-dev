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

### I. A fixed nearby-mutant panel in the decoy world (2026-10-14)

- Question: does the existing decoy world offer useful nearby steps from original evolved s5 and s7? F measured
  that its sense information can pay. This separate diagnostic tests ordinary organism mutations, with no
  controller behavior entering the tissue and no automatic world-admission or selection change.
- Use the complete original tables from `results/pool_mutants_20261013/genomes/s{5,7}_pool.npy`: each original
  parent plus its 64 ordinary point mutants. Preserve exact float32 bytes, row order, generation manifests and
  mutation logs. No new mutants, hand-selected alleles, or filtering by prior base/POOL outcomes.
- World exactly matches F: existing ABI3 discrimination, T1024, d0=1, d_min=0.5, b2_amp=1, b2_sigma=1.2,
  b2_value=-50, b2_p=1, b2_mode=1, with every price unchanged. This uses the original slower conduction, not
  fast POOL; comparisons with earlier-world outcomes are not controlled world-only contrasts.
- Both parent panels share 32 block95 seeds for screening. Per panel, select exactly four mutant rows by mean
  production F; exact ties use ascending original row index. The parent is a reference, not a shortlisted mutant.
- Re-score those four mutants and their parent on 512 block96 seeds. Freeze the highest-mean mutant from each
  panel, breaking exact ties by original row, before confirming either winner. Keep a winner even if worse than
  the parent. Confirm both winners and both parents on 512 block97 seeds, with no extra candidates or extensions.
- Counts: screen 130×32=4,160; rescore 10×512=5,120; confirmation 4×512=2,048; **11,328 scientific genome-lives**.
  Blocks95/96/97 are disjoint, share lives within each stage, and do not overlap the original panel's evaluations
  or F. E1 startup full/fast golden replay is separate validation, included in the overall CPU cap.
- Primary: each winner minus its original parent on fresh confirmation, paired per seed before mean/SE.
  Report raw effects and descriptive >3-SE and ≥0.5-F flags, both signs, screen beneficial fractions, rescore
  results, captures, clicks, poison clicks, end and hidden-cell counts. No claim of multiplicity-adjusted discovery.
- Decompose paired F into capture income, poison-cost saving, miss-cost saving, other cost saving, guard and
  extinction charges. Require the pieces to reconstruct fitness. Shape or reduced clicking alone does not
  establish discrimination or a new algorithm; the fixed 64-mutant panels do not estimate general evolvability.
- All rows retain production guard/extinction penalties. Capacity failures, ledger mismatches, unexplained
  incomplete lives, source/numerical drift or corrupted caches make the study incomplete rather than dropping
  selected lives. Hash and save each completed row; freeze both selected genotypes before fresh confirmation.
- One shared cap of **3,600 CPU-seconds**, at most two simulation workers on CPUs0–11. The external monitor
  stops before the cap and preserves partial evidence. No automatic retry/reset or score-based budget extension.
  Wait until G is complete with no active or queued jobs, then run alongside H's two workers if it is still active.
  I does not depend on H's result. Require a root-created `ready.json` after protocol review/commit.
- No organism rule, ABI, price, hand-designed behavior, rented compute, population-responsive world or default
  world changes. This is a bounded diagnostic, not the full all-world G2 gradient study.


### J. Contribution of duplicated-origin genes (prepared 2026-10-14, before G completes)

J asks whether an individual gene descended from a duplication contributes to the performance of either fixed G
endpoint. It uses the existing deletion operator as a measurement intervention, with no new organism behavior,
channel, clock, world response, price or ABI change. It is separate from the G comparison of mutation policies.

The two endpoints are fixed as each G run's final population rank 0 at generation 16 (seeds 51089 and 51090).
They are inspected only after G completes. Full recorded crossover, point mutation, duplication and deletion
operations must replay to the exact checkpoint population and innovation-origin registry. An eligible gene has
an active slot and origin ID >=16. Every such gene is included, even if its outgoing weights are zero; none is
chosen by fitness, morphology, expression or presumed importance. No active duplicate-origin genes means that
endpoint's branch is reported as not applicable, with no replacement endpoint or alternative intervention.

For each eligible gene, `Layout.delete` clears its active bit and silences weights read from inactive genes.
Kernel packing masks its own regulation/state and its outgoing regulatory and phenotype effects. The resulting
runtime table must match a canonical copy with only that active bit cleared. All single-gene knockout genomes,
raw hashes, runtime-table hashes, slots and origin IDs are frozen before any scoring. The knockout acts from birth
in every cell, so it can change development, morphology and later computation together. Gene deletion has no
separate direct fitness reward; the ordinary task ledger and prices determine its effect.

Stage 1 measures each applicable intact endpoint and every eligible single-gene knockout on the same 512 fresh
seeds 51,980,000 through 51,980,511 (block98). Every life uses fast POOL (d0=.5, d_min=.25, sigma=.4, lam_s=4), T1024,
with full-life accounting and no fork. Report all paired intact-minus-knockout effects, their SEs, complete costs,
income and guard/extinction penalties. Negative and unresolved losses remain in the result.

For each applicable endpoint, choose the gene with the largest mean paired intact-minus-knockout loss; an exact
tie chooses the smallest slot. This choice is made regardless of sign, including when all initial losses are
negative or zero. Freeze the choice and candidate-row mapping before stage 2. The chosen knockout and its intact
endpoint then share another 512 fresh seeds 51,990,000 through 51,990,511 (block99), with the identical T1024 world.
All confirmation roles share these seeds, and both endpoint confirmations are retained. No candidate or life
extension follows the outcome. There is no genotype deduplication; each prescribed role is scored explicitly.

Fresh confirmation supplies the primary evidence after selecting among genes. A positive loss beyond 3 SE and
above 0.5 F is flagged descriptively; the original 8-of-20-run G-use criterion is not evaluated with two endpoints.
A confirmed loss establishes that this duplicated-origin gene contributes to this fixed genotype's whole-life
performance. The gene may replace an original gene or share an existing role. It does not establish expanded
computation, an adult circuit or a new algorithm. An individual null effect does not prove zero function or exclude
redundancy/epistasis. Life-level SE does not estimate uncertainty across independent evolutionary searches.

The upper bound is 16 eligible genes per endpoint: deletion can replace original slots, so the limit is not eight.
Stage 1 therefore has at most 32 knockout plus two intact rows (17,408 lives). Stage 2 has at most two selected
knockout plus two intact rows (2,048 lives). Total research lives are at most 19,456; exact counts are recorded from
the frozen candidate set. Empty branches incur no research lives. Numerical-identity startup golden checks are
separate from research counts and included in CPU accounting. Preparation uses pure genome operations, synthetic
scores and mocked workers; it performs no scientific or validation life simulations.

The cumulative resource cap is 7,200 worker CPU-seconds with two simulation threads, including imports, startup
checks, both stages and incomplete rows. The external monitor stops at 7,188 CPU-seconds, sends TERM, then KILL
after at most two wall seconds, with worker CPU limits and parent-death termination as independent safeguards.
There is no budget extension or automatic restart/reset. The monitor waits until both H and I are complete with
empty active/queued records; this also follows G completion. Their scientific outcomes do not alter J. Dependency
protocols and monitors are pinned at readiness after root review. An abnormal predecessor stop requires operational
review, and does not license a silent restart. All raw rows, decisions, negative results and any incomplete-work
receipt are preserved. Invalid capacity/accounting mismatches stop the study; penalized guards stay in every
fitness comparison.

### K. Fixed traces of the founder and both ordinary continuation endpoints (2026-10-14)

Use the existing E6 observer to describe how the row38 founder and both fixed D endpoints turn sensory events
into movement. The three genomes are exactly those in H, fixed independently of H/G/I/J outcomes. Each is traced
on seeds51,890,000..51,890,003 (previously unallocated block89) in normal fast POOL at T1536. Iterate seed first,
then founder/D51089/D51090. There is no seed, endpoint or favorable-trajectory selection and no intervention.

Twelve reference traces are paired with twelve full C-kernel validation lives. All 57 ledger columns must match
bitwise. This is stronger than the existing observer's F-only check, but is not an event-hash comparison. The
numerical-identity startup's two T200 golden runs are separate validation, included in the CPU cap. Save all raw
trace tables losslessly as numeric/string NumPy columns, with no object pickle; reload and recompute each readout
before accepting the life. Invalid/guarded/truncated or mismatched traces stop the study and preserve partial
artifacts; they are never replaced by a different seed. These are descriptive traces, not a fitness screen.

Report the existing search signature and largest-input relay-chain summaries over both the full life and800..1536.
The latter is the same accounting interval as H, but these normal lives keep growing: they are not H's frozen arms.
Silence means no delivered receptor ping anywhere for at least0.5 time units, including background pings and initial
silence. Report silent time and analytically integrated distance, total distance, integer-sample capture-zone
occupancy, clicks/captures and clicks per capture. Missing ratios remain null. Movement during silence does not
show that silence is used as evidence; larger bodies also change ping frequency and mechanical motion.

Chain depth is fixed at12. Report all receptor, tonic, residual, unknown and depth-limited origins; lateral-hop
shares use receptor-origin chains only. Keep per-life results and K/M/all motor groups, including one-hop and
multi-hop latencies. Paths credit the largest input at the firing step and omit previous subthreshold integration;
they do not prove that a path alone caused the spike. Any paired summaries compare fixed seeds before averaging,
retain all signs, and are descriptive with n=4 and no success threshold. These readouts may suggest follow-up
interventions; they do not establish a new algorithm, mature tissue, hidden-layer function or matched-footprint
information use.

One worker on CPUs0–11 runs under a fixed1,800-worker-CPU-second cap, stopping at1,788 then TERM/KILL within two
wall seconds, with an independent CPU limit and parent-death termination. No restart, seed substitution, or budget
extension. Wait for both H and I to complete with empty queues, independent of their scientific results. K may
then run beside J's two workers (three simulation workers total); a separately bounded one-worker viewer check
still fits the standing four-worker limit. Require root readiness after review and commit. No src/helper changes,
organism rules, hand-designed behavior, ABI, prices, rental or population-responsive world are introduced.

### L. Further adaptation in the second original lineage (prepared 2026-10-14)

L asks whether ordinary production evolution can find further useful steps from the original s7 POOL winner,
row29. This is a second starting lineage beyond the s5 branch used in D. The founder is fixed by its original
nearby-mutant study selection, including its weak original fresh confirmation; no G/H/I/J/K result selects it.
Neither a hand-built organism nor presumed behavior determines admission or whether this experiment proceeds.

The fixed founder is `results/pool_mutants_20261013/genomes/s7_pool_winner.json`, exact raw FP32 SHA256
`c34e8ec8dff4682b99d9ca0e090d226fa1733366fa8f4c84e5a1ce000bdeb358`. Its bytes must equal row29 of the complete
original s7 mutant table. The original s7 parent is retained as a separate confirmation reference. Source files,
numerical identity, input provenance, complete original mutant table and mutation operations are pinned.

Two independent fixed run seeds, 51891 and 51892, each receive exactly16 generations. Every run initializes one
exact row29 founder plus31 ordinary point-mutated copies, then uses the unchanged 32+224 sexual production search:
three shared initial lives for all256 candidates, four further lives for the top64, and the ordinary pooled
seven-life selection of32 survivors. Point mutations use the existing two-block policy and active-gene scaling;
duplication/deletion rates remain zero. There is no protected founder, best-ever archive or adaptive extension.
The exact prospective32-genome initial populations, all31 recorded mutation operations and the mutation RNG states
before/after initialization are saved in `initialization.json` and `initialization/`. These are receipts of the pure
production initializer; the search still constructs its initial population through the unchanged production path.

The sole search world is the existing fast-conduction POOL: d0=.5, d_min=.25, sigma=.4, lam_s=4, all other prices
and world settings unchanged. The existing per-generation duration draw chooses768,1024 or1536. All in-life
rules remain local and asynchronous under the unchanged ABI3 engine; there is no global clock or new channel.
Preparation changes only seed, founder path, run label and output path relative to the reviewed D configurations.

Each endpoint is exactly final population rank0 from its complete generation16 checkpoint. Full ordered search
history, configuration/numerical pins, invalid/mismatch counts and raw genome identity must agree before inference.
No periodic validation score, tiny final diagnostic, body feature or apparent behavior may replace this endpoint.
The two endpoints are frozen together before any fresh confirmation is scored. Both are retained regardless of sign.

Confirmation scores four fixed roles: original s7, row29, endpoint51891 and endpoint51892. Each shares the256 fresh
seeds51,900,000 through51,900,255 (decimal block90), separately at T768,T1024 and T1536 in the same fast POOL. Primary
effects are each endpoint minus row29; secondary effects are each endpoint minus original s7. Within each seed,
average the three duration-specific fitness differences with equal weights, then calculate the mean and sample SE
over256 seed clusters. Do not treat768 duration-life observations as independent. Both endpoint comparisons share
these seeds. Positive effects beyond3SE and at least0.5F are descriptive flags, with no extension or admission gate.

Record every duration's paired effects, capture income, all costs, guard/extinction charges, cells, clicks, path and
message counts. Ordinary guard penalties stay in fitness. Invalid capacity or accounting mismatches stop inference;
the failure record and all consumed work remain. A confirmed gain establishes further whole-life adaptation for
these fixed starting conditions. It does not establish expanded computation, a new algorithm, general reliability,
or superior efficiency versus the s5 lineage. Initial founder selection and only two searches limit generalization.

The fixed life count is32,768 selection lives,160 periodic validation lives,12 tiny final diagnostic lives
(including four half-duration lives), and3,072 fresh confirmation lives:36,012 research genome-lives total.
The12 diagnostics are not additional selection rechecks. Existing E1 startup full/fast golden checks remain inside
the CPU budget and outside the research count; with three successful worker processes this is six golden lives.
The generated392 distinct hash-derived training/diagnostic seeds are checked prospectively against both new run
lists,58,690 original pilot seeds,392 D/G seeds, the fresh confirmation set and every reserved decimal51M block.
The original tiny half-duration diagnostics intentionally reuse each run's final0 seeds.

The cumulative cap is14,400 worker CPU-seconds, including both searches, confirmation, imports, compiler descendants,
startup checks and incomplete rows. At most four simulation threads run: two two-thread searches, followed by one
two-thread confirmation. Workers stay on available CPUs0–11. The external monitor uses live process-tree CPU,
parent-death termination and remaining CPU limits; it stops before the hard cap, sends TERM, then KILL after at most
two wall seconds. No automatic restart, resource reset, extension, paid compute or additional validation is authorized.

L waits until both J (`outputs/autonomous_duplicate_use_20261014`) and K (`outputs/autonomous_traces_20261014`) report
complete with no active or queued work. Their outcomes do not change L. Dependency protocol/monitor hashes are fixed
in the readiness template. Abnormal predecessors stop the queue for operational review. This preparation creates
no readiness marker and launches nothing; root must finish review, register and release the concrete study first.

### M. Whole-life interaction between a copied gene and its source lineage

This amended study measures the fixed G51090 endpoint. Its four interventions are intact, delete its active
copied-origin gene, delete the extant gene carrying that duplication's source origin, and delete both. All four
prescribed roles share 512 new seeds at T1024 in fast POOL, for 2,048 research lives. There is no candidate
selection, tuning, replacement endpoint, role deduplication or outcome-dependent extension.

Before any release or M measurement, J's exactly zero observed copy-knockout effects motivated a source audit.
G51089's copy is analytically disconnected in both relevant backgrounds, so its physical and fitness interaction
is zero without simulation. G51090 retains a possible emit1 output; a bounded-state counterexample prevents a
universal decoder-silence proof, without establishing reachability. AMENDMENT.md and analytical_proof/PROOF.md
record this rationale. The original 4,096-life preparation is preserved under superseded_4096/ in the public
archive. It is superseded and is not the current launch scope.

The endpoint is G51090's final population rank 0 at generation 16. Completed G archive provenance, original
founder, configuration, checkpoint and complete recorded genetic operations are verified before preparation.
Genetic replay must reconstruct every retained population and origin registry exactly. The eligible copied
gene is the unique active gene with innovation origin >=16. Its recorded source_origin_id is resolved against
the final active origins, never its former slot number. The mapping and all four raw genomes and runtime-table
hashes are frozen in genomes.json/genotypes.npy before any scoring.

The fixed mapping is copy slot 9/origin 21 with source slot 0/origin 0. If it cannot be verified, preparation stops
without substituting another gene. The extant source may have changed since duplication. J results motivated
the documented pre-release audit; no J score or selection record enters the scientific runner or selects an arm.

Each knockout uses existing Layout.delete from the untouched intact endpoint. The double knockout applies both
deletions, and both deletion orders must give identical raw bytes. Packed runtime tables must equal a canonical
copy of the intact genome with exactly the prescribed active bits cleared. Genes are removed from birth in every
cell; development, shape, physiology and later computation may all change. Ordinary task accounting determines
fitness, with no direct reward for deleting a gene.

The proposed block 100 contains seeds 52,000,000 through 52,000,511. It is fixed only after the independently
recorded namespace audit checks previous and prepared training, confirmation and validation seed registrations.
All four roles use this same ordered list. Existing helper block-number guards are not changed; the new runner
passes the explicit audited list to the existing RowStore. World parameters are catch_speck_l4, d0=.5,
d_min=.25, sigma=.4 and lam_s=4, T1024, full-life accounting, no fork, and all existing prices unchanged.

The primary paired vector is
`F_intact - F_copyKO - F_sourceKO + F_doubleKO`.
Mean and sample SE are calculated from these 512 within-seed contrasts, preserving covariance among all four
arms. Both signs are retained. Descriptive flags are abs(mean)>3SE and abs(mean)>=0.5F;
an exact zero is unresolved. There is no equivalence claim from a small or unresolved result and no extra lives.

Secondary results retain each intact-minus-single/double-knockout loss, full ledger columns, income and costs,
guard/extinction charges, capture/action counts, integrated cell-time and terminal sense/motor/hidden counts.
Invalid capacity or accounting mismatches stop measurement as incomplete. Penalized guarded and extinct lives
remain in the comparisons. Morphology and resource differences are described alongside the interactions.

The interaction measures nonadditivity of these gene deletions in whole-life task fitness. Either sign can arise
through development or nonlinear fitness, so sign alone is not a categorical redundancy or complementarity label.
The study does not isolate an adult mechanism, establish expanded computation or a new algorithm, demonstrate
that duplication was necessary for a function to evolve, or establish structural-search policy superiority.
Uncertainty across fresh life seeds does not estimate variation across independent evolutionary searches.

The cumulative cap is 1,800 CPU-seconds with two simulation threads, including measurement startup, all incomplete
rows and the monitor's own CPU. The monitor counts its process tree and reaped children, stops at 1,788 seconds,
sends TERM then KILL after at most two wall seconds, and independently applies a parent-computed remaining CPU
limit and exact-parent-death binding. No reset or automatic restart is permitted. Success requires worker exit 0,
a complete scientific report with exactly 2,048 research lives, unchanged release pins, and total CPU below cap.

M waits for outputs/autonomous_s7_20261014 to finish with status complete and empty running/queued records;
L's scientific outcome does not alter M. An abnormal predecessor blocks launch and leaves a failure receipt.
Preparation performs pure genome operations and synthetic/mocked tests only. Numerical startup golden checks
occur only after worker release; their lives are separate from research counts and their CPU is inside the cap.
No organism channel, clock, behavior, ABI, selection world or price changes. No readiness marker or simulation
is created by preparation. Root review, public registration and release precede launch.

### N. Fixed information/reference comparison at two durations (2026-10-14)

Prepared on 2026-10-14, before any N simulation or score. This document fixes a
measurement of the retained external C4 controller and existing reflex bodies.
It does not change an organism, an ABI, an evolutionary selection world, or any
in-life rule. The external controller remains an instrument for measuring the
value of sensory information.

#### Question and fixed inputs

Does the recovered default C4 controller's advantage over fixed reflex bodies
remain at T=768 and T=1536 in the original headline base and POOL worlds?

The original headline used **d0=0.5 and d_min=0.25**. Those values are retained in
both worlds. POOL additionally has sigma=0.4 and lam_s=4; all other world values
and prices are the original `catch_speck_l4` values. Consequently this is a
duration transfer relative to those headline worlds, not relative to the old
conduction settings of experiment F. Full world dictionaries are frozen in
`protocol.json`.

Every world/duration cell has exactly these six fixed candidates:

1. Default C4, built-in controller id 5, with its exact recovered 21 parameters
   and hollow3 footprint (56 cells). The retained separately tuned C4 parameters
   are archived for provenance but are never used.
2. Frozen hollow3 reflex (56 cells).
3. The retained per-world retuned hollow3 reflex (56 cells).
4. Frozen hollow2 reflex (32 cells).
5. The same retained per-world retuned knobs transferred to hollow2 (32 cells).
6. The retained per-world retuned hollow3 reflex with the existing `K.t_ref=8`
   quieter setting.

All parameters, exact program hashes and body cells are fixed before scoring.
There is no retuning, body search, candidate replacement, winner follow-up, or
new controller behavior. The original recovered C4 source and replay wrapper
are copied byte-for-byte. Controller action costs, relay charges and delivery
latency use the existing measurement harness; computation is free.

#### Samples, counts and comparisons

All six candidates receive the same ordered 512 seeds in both worlds for each
duration. T=768 uses block 40, seeds **51,400,000–51,400,511**. T=1536 uses block
41, seeds **51,410,000–51,410,511**. The prospective namespace audit found no
overlap with retained earlier smoke/validation samples or the enumerated pilot,
D/G and L training/validation seeds. Its source receipts are archived. Distinct
duration blocks mean that duration changes are not paired across durations.

Research count is **6 × 2 worlds × 2 durations × 512 = 12,288 candidate lives**.
Every fixed comparison is retained, including negative effects. Primary
comparisons are C4 minus frozen reflex and C4 minus retuned reflex, separately
in each of the four world/duration cells. Means and SEs are calculated from
within-seed differences; no life or candidate is selected away.

All three smaller/quieter contrasts against the best whole frozen/retuned
reference are also reported, along with all five C4-minus-reference contrasts.
“Best” means greatest mean fitness over the whole 512-life candidate, never the
best reference separately for each life. Exact mean ties use listed candidate
order. The fixed comparisons carry the primary interpretation. Best-reference
SEs reuse the scored sample and are descriptive, without selection correction.

For continuity with the plan, report whether the C4 gap over the best whole
frozen/retuned reference exceeds three SEs and reaches 1 F, and whether the best
smaller/quieter gain is below one quarter of that gap. These are descriptive
checks, not a world-admission decision. Also retain full income, poison/miss,
cost, cell and event accounting for every contrast. This narrow measurement
does not establish full G5 across capability worlds or what evolution can use.

#### Bounded validation inside the same resource cap

Before research scoring, run exactly **40 T=64 validation lives** at one worker,
using seeds 51,099,000–51,099,003 (block 9, offset 9000). They are separate from
the previous block-9 smoke seeds and all research samples. No validation seed
or case is replaced if it fails.

For each world, two seeds compare built-in C4 with its unchanged logged copy.
Each copy's retained ping sequence is then replayed with real receptors disabled
in the same life, another life, and the existing altered-world leak check;
recorded actions must be byte-identical. Closed-loop controls on two different
seeds must establish sensitivity to changed ping input. This accounts for 12
controller lives per world. Two scratch reflex and two production reflex lives
check world parity, and two null-controller and two inert-body lives check world
stream parity, bringing the count to 20 per world and 40 total.

The existing scratch harness uses historical diagnostics in ledger columns
21/22; these columns and the combined all-state hash are excluded only from the
documented scratch-versus-production identity check. Every other ledger column
and component hash must match. Controller-copy checks compare every ledger
column, all five hashes and the first 12 diagnostic columns. Replay retains
every ping and action; an empty, truncated or oversized log fails validation.

The research fast library and full validation library are built from unchanged
pinned source. Generated C/library hashes are recorded before research rows.
Full per-life validation arrays, logs and all research arrays are retained.

#### Failure, resource and scheduling rules

The total hard allocation is **3,600 CPU-seconds and at most two workers**,
including compilation, validation, monitor work and research. The monitor stops
at a 3,588-second threshold to leave termination room; it accounts for live
compiler/worker descendants, binds worker lifetime to its exact parent process,
and applies the remaining CPU limit before launch. No automatic retry, resource
reset or cap extension is allowed. A failed or incomplete study remains so.

The queue waits only for exact pinned L completion with no active or queued
work. It can then share the four-worker allocation with another two-worker
measurement. Readiness is a separate explicit release artifact. Preparation,
pure mocks and dry runs create no readiness or scientific work.

Guards, capacity failures, source/ABI/numerical mismatches or incomplete lives
fail the entire affected candidate and study. No failed life is omitted from an
otherwise scored candidate. Each 512-life row is validated and saved atomically;
source and release pins are rechecked before each row and before completion.
The final monitor requires all 12,288 research lives and all 40 validation lives,
as well as successful process exit and unchanged pins. No outcome determines
additional samples or a change of direction within this experiment.

#### Reproducibility and checks before release

`protocol.json` freezes worlds, candidates, seeds, source hashes, numerical
identity and the L dependency. `input_sources.json` identifies recovered
artifacts; `inputs/` and `sources/` retain their bytes. The release template
additionally pins the scientific scripts, this preregistration and the pure
science tests. The public preparation preserves the numerical source snapshot.

The pure test suite covers the complete 24-row workflow, complete 40-life
validation workflow, fixed sample/candidate mapping, retained negative effects,
failure handling, exact-parent binding, cumulative CPU accounting, dependency
and source checks, no restart, and final actual-count enforcement. These tests
use synthetic arrays and mocked launch functions; they simulate no lives.

### O. Local gene-regulatory inputs with cell composition held constant (2026-10-14)

Prepared after H's completed result, before any O life. H found that broad freeze removes
0.914 ± 0.214 F of D51090's gain over row38, while D51089's corresponding effect is unresolved.
Freeze stops gene/phenotype updates as well as division and death. O separates these processes using
existing ABI 3 interventions. Both original D endpoints remain fixed, regardless of their H outcomes.

#### Fixed comparison

Use the exact row38 founder and D51089/D51090 generation 16 population-rank0 genomes archived by H.
All three share 512 fresh block101 seeds, 52,010,000 through 52,010,511, in each of three arms:

1. **Structure held fixed:** division_off + apoptosis_off. Genes, phenotypes, effective weights,
   neural activity and chemicals continue updating under their existing local rules.
2. **Structure held fixed plus genes_blind:** the same, but five inputs to the GRN are set to zero.
   These are the own-spike trace, two incoming-spike traces, contact-count fraction and receptor trace
   (ABI inputs 18 through 22). Current genes, morphogens and plane cues remain available. Receptor events
   still drive neurons and spike messages still travel.
3. **Freeze:** the existing broad freeze flag, matching H's interpretation.

All worlds use fast POOL, T1536, d0=0.5, d_min=0.25, sigma=0.4 and lam_s=4, with unchanged prices.
The fork begins at 768 and accounting opens at 800. Every condition/genotype/seed is retained, in fixed
condition order and then founder/D51089/D51090 order. There is no candidate selection or tuning.
Three genotypes × three conditions × 512 seeds gives **4,608 research genome-lives**.

The independently reviewed namespace receipt checks this block against the enumerated historical pilot,
D/G/L training and diagnostic seeds, prior declared measurement ranges, and the prospective M/N ranges.
The same O seeds are intentionally shared across all nine arms.

#### Estimands

The two primary contrasts are each endpoint's added dependence on the five masked GRN inputs:

`(D − row38)structure − (D − row38)structure+genes_blind`.

Subtract within each seed before computing mean and sample SE across 512 seed clusters. Report both signs
and both endpoints, with descriptive positive/negative 3-SE flags and no endpoint selection. There is no
multiplicity-adjusted discovery claim and no estimate of reliability across evolutionary searches.

Secondary contrasts retain every arm's endpoint-minus-founder gain, each genotype's own input-mask loss,
and structure-minus-freeze effects and their endpoint-versus-founder interactions. Report capture income,
all costs, guard/extinction charges, clicks, path, terminal cells and hidden cells alongside fitness.

The input mask removes static contact information as well as activity traces. A loss therefore does not
by itself show adaptation, memory or use of changing evidence. The structure-minus-freeze contrast also
includes phenotype and effective-weight updates. Different genotypes retain different footprints and
pre-fork states; this is not a matched-footprint comparison or a test of a copied gene's function.

#### Checks and resources

All inputs, source/numerical identity, helpers, protocol and monitor are pinned before release. The three
interventions share pre-fork events. The settling interval exceeds the existing bounded pending claim,
notice and spike delays; it does not erase their earlier effects. Every scored arm must have zero births
and deaths during 800..1536 and last birth before 800. Complete triplets within each genotype must have
equal total and per-plane counts, t_end=1536, and cell-time equal to 736 times terminal count.

Valid guarded/extinct lives retain their ordinary production penalties in all fitness estimates. Only
the constant-composition checks condition on complete triplets. Capacity/accounting implementation errors,
changed structure or incomplete coverage prevent completed inference; retain all partial evidence.

Use at most **two simulation workers**, CPUs 0–11, after both M and N are complete with empty queues.
The **3,600 CPU-second cap includes monitor/waiting CPU, worker descendants and startup validation**.
Stop at 3,588, then TERM and bounded KILL; install remaining-budget RLIMIT and exact parent-death binding.
No automatic reset, seed substitution or extension. Existing two T200 startup golden lives are validation
inside the CPU cap and outside the 4,608 research count. Preparation and mock tests simulate no lives.

All work stays in `outputs/autonomous_regulation_20261014/`; publish preparation and complete or incomplete
results under `results/regulation_20261014/`. No organism behavior, ABI, price or selection world changes.

### P. A further ordinary adaptation step from both fixed D endpoints (2026-10-14)

P asks whether the unchanged ordinary production search finds another useful step from each fixed D endpoint.
Search seed 52091 starts from D51089; search seed 52092 starts from D51090. Both founders are D's generation-16
final population rank-zero genomes. No H, L, M, N or O outcome chooses a founder, changes scope or replaces an arm.
This is a new seeded population for each founder, not a resume of D's population or random-number stream.

Preparation verifies the completed D archive, final checkpoint, configuration and every recorded genetic
operation. The source lineage must reconstruct the final population and origin registry exactly, and the
founder JSON must equal checkpoint rank zero byte for byte. Both founders, row38 and original pilot s5 are
retained as fixed inputs. Preparation records the exact 32-genome initial population and RNG-state hashes for
each new seed using the unchanged production setup/fill: one exact founder plus 31 ordinary point-mutated copies.

Both searches use the same ordinary 32-parent plus 224-offspring sexual policy for 16 generations. All parents
are reevaluated; neither founder nor historical best is protected. Duplication and deletion rates remain zero.
The unchanged scorer uses three initial lives and four recheck lives for the top 64, with equal draws from
T768, T1024 and T1536 in fast POOL. Relative to the corresponding D configuration, only the new random seed,
seed-genome path, descriptive control label and output directory may change. Existing in-life rules and prices
remain fixed; behavior is discovered by evolution.

Both new generation-16 final rank-zero endpoints are fixed together before fresh confirmation. There is no
best-validation or best-ever reselection. If either search lacks a complete endpoint, or any confirmation role
is missing, the entire study remains incomplete. Partial evidence is retained, with no replacement or extension.

The six confirmation roles, in order, are original s5, row38, D51089, D51090, the new s52091 endpoint and the new
s52092 endpoint. All six use the same 256 fresh block102 seeds, 52,020,000 through 52,020,255, at each of T768,
T1024 and T1536. The independently recorded namespace audit checks the exact 392 new search/diagnostic IDs and
confirmation seeds against retained pilot/D/G/L IDs and all prior/prepared F–O measurement and validation
registrations, including N's 51,099,000 through 51,099,003 validation seeds. No helper seed-range guard changes.

The primary contrasts are s52091 minus its own D51089 founder and s52092 minus its own D51090 founder. For each
shared seed, the three duration effects are averaged first; mean and sample SE then use 256 seed clusters.
Secondary contrasts compare each new endpoint with row38 and original s5 using the same paired calculation.
Both endpoints and every sign are retained. Mean>3SE and mean>=0.5F are descriptive flags, not an extension rule.
Every raw ledger, capture-income term, cost and morphology measure is retained; guarded and extinct lives keep
their ordinary penalties. Capacity or accounting implementation failures stop endpoint inference.

Research accounting is 32,768 selection lives, 160 periodic-validation lives, 12 tiny final-diagnostic lives
and 4,608 independent-confirmation lives: 37,548 in total. Validation occurs five times per run, at generations
0,4,8,12,15, with 16 lives each. The heldout list is empty, so no heldout simulations occur. Existing numerical
startup golden checks are separate from research counts and included in CPU usage.

The cumulative hard ceiling is 14,400 CPU-seconds, counting the monitor, live descendants and reaped children.
At most four simulation threads run: two two-thread searches, then a single two-thread confirmation process.
CPU affinity is limited to 0–11. More developed founders may cost more per life; completion within the ceiling
is not promised. No reset, automatic restart, scope reduction or budget extension is permitted. The new monitor
records resource use before spawning, uses a parent-computed remaining CPU limit and parent-death binding, and
cleans the owned process group after bounded termination. Success requires both searches and all confirmation
roles, exit 0, complete reports, unchanged pins and CPU below the ceiling.

P waits for outputs/autonomous_regulation_20261014 (O) to report complete with no active or queued workers.
O's outcome does not alter P. An abnormal predecessor blocks launch. Root review, independent science/monitor
review, a published protocol, a milestone commit and a concrete scope/cap report precede any readiness or run.
Preparation performs only pure genome operations, source checks and synthetic/mocked tests.

Two fixed founder branches do not estimate general evolutionary reliability. Fresh life-seed SE describes
these fixed genotypes, not variation across independent searches. Fitness gain does not establish a new
algorithm, adult mechanism or expanded computation. No world-admission decision, organism behavior, ABI,
channel, clock, price, spending or population-responsive world is introduced.

### Q. Hidden and lateral spike dependence of fixed continuation endpoints (prepared 2026-10-14)

The completed L study found further gains in both fixed final descendants of s7 row29. Q asks whether those
additional gains rely more on spike messages sent by hidden-plane cells after tissue growth has been held fixed.
Hidden cells are those at lattice height z >= 2. This measurement adds no behavior, world response, organism
channel, clock, price or ABI change. It uses existing ABI 3 interventions only.

L had small mean hidden-cell counts; that does not select an arm or imply a hidden benefit.

All three genotypes are fixed before scoring: row29, L seed 51891 final population rank 0, and L seed 51892 final
population rank 0, each from generation 16. Raw genotype hashes and their completed L checkpoint hashes are pinned.
Both endpoints remain in every comparison, irrespective of sign; there is no selection by Q scores or morphology.

The twelve arms are three genotypes crossed with normal, freeze, freeze+lateral_off and freeze+hidden_off.
All arms share 512 fresh seeds 52,030,000 through 52,030,511 (block103), giving 6,144 research genome-lives.
The world is POOL with fast conduction (d0=.5, d_min=.25, sigma=.4, lam_s=4), T1536. Interventions start at 768;
fitness and additive counts use the common accounting interval 800..1536 (736 time units), including normal arms.
All other physics and prices match L and E. Whole-life counters such as path and terminal tissue counts are
labeled separately from interval fitness/capture/cost accounting.

The primary contrast for each L endpoint is
`(L-row29)freeze - (L-row29)freeze+hidden_off`, computed within each life before mean and SE across 512 seeds.
Secondary contrasts report the analogous added lateral dependence, each endpoint's gain in every condition,
normal gain minus frozen gain, and each genotype's own hidden/lateral lesion loss. Both positive and negative
effects are retained. Three-SE flags are descriptive; an unresolved effect is not zero. Both descendants were
selected by L evolution, not by Q, but their life-level SE does not measure uncertainty over search replicates.
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

P is a resource dependency only. Its outcomes never select, omit or revise Q genomes or contrasts.

The fixed cap is 3,600 cumulative CPU-seconds, two simulation threads, with no extension or automatic reset. The
monitor counts its own CPU, including waiting, plus worker/descendant CPU. It stops at 3,588 seconds and sends
TERM and then KILL after at most two wall
seconds; child CPU limits and parent-death termination are independent safeguards. Q waits until P's resource
record is complete with no active or queued jobs. P's scientific outcome does not change the protocol. An
abnormal P stop requires operational review before Q can launch. No readiness marker or process is created by
preparation. Existing E validation supports the fixed accounting window; Q preparation tests synthetic rows
and mocked processes only. Numerical-identity startup golden checks run after worker release; they are separate
from the 6,144 research lives and their CPU is included in the cap. No extra validation lives are scheduled.

### R. Ongoing phenotype and effective receive-weight updates (prepared 2026-10-14)

Full freeze holds gene state, decoded cell properties and effective incoming spike weights fixed at once.
R separates these existing operations with three controls. The design was fixed before O outcome inspection;
no O result chooses a genotype, condition or comparison. This is external measurement with existing ABI 3
interventions; it adds no organism behavior, channel, clock, price or population-responsive world.

All three genotypes are fixed: s5 row 38 and both D generation-16 final population rank-0 endpoints, search seeds
51089 and 51090. Their raw genotype hashes, completed checkpoints, health records and full recorded genetic
replay are pinned. Both descendants remain in every comparison regardless of sign or morphology.

The nine arms cross those genotypes with three conditions, all activated at the common experimental fork 768:

- S: division_off + apoptosis_off (flags 12), holding structure fixed after pending claims settle.
- C: S + identity_clamp + pheno_fixed (flags 204), also holding gene state and decoded phenotype fixed while
  locally modulated effective receive weights continue updating.
- F: existing freeze (flags 16), additionally holding those effective receive weights fixed.

All arms share 512 fresh block 104 seeds, 52,040,000 through 52,040,511, giving 4,608 research genome-lives.
The world is unchanged fast POOL: d0=.5, d_min=.25, sigma=.4, lam_s=4 and T1536. Fitness and additive ledger
counts use the common 800..1536 accounting interval, 736 time units. All other physics and prices match D/E/H.
Whole-life counters such as path and terminal cell counts are distinguished from interval capture/cost data.

For each D endpoint, the primary contrast is `(D-row38)C - (D-row38)F`, computed per seed before its mean and SE.
It asks whether ongoing local effective receive-weight updates contribute more to that endpoint's advantage
than to its founder's, conditional on fixed phenotype. Secondary contrasts are each endpoint's analogous added
S-minus-C effect, all six endpoint gains in S/C/F, and each genotype's own C-minus-F and S-minus-C effects. All
16 paired vectors and all 60 raw ledger columns are retained. The added S-minus-C and C-minus-F vectors telescope
to gainS-minus-gainF, but their SEs must not be added: they share seeds and covariance. Three-SE flags are
only descriptive. Negative and unresolved effects remain; unresolved is not equivalence. Life-level SE concerns
these fixed descendants, not repeatability over evolutionary searches.

The source proof is preserved in semantic_proof/. In GRN mode, C and F skip the same gene update, phenotype
readout, new division and tick apoptosis branches. Their remaining cell-physics update difference is derive(),
which recomputes quantized receive weights from the fixed phenotype and local chemical/contact state. Its other
output only affects disabled division placement. Incoming spikes use the cached weights at arrival time.
Chemistry, receptors, membrane dynamics, spike generation and ordinary charges continue in every arm.

C-minus-F is a conditional ongoing effective receive-weight update effect, including early transient carryover
and subsequent changes in spikes, movement, captures and costs. It is not a pure memory or learning test. The
weight update does not directly read activity or receptor traces; with fixed secretion and phenotype,
its evolution can reflect autonomous chemical relaxation from the pre-fork state. A positive C-minus-F alone
does not demonstrate sensory adaptation, learned weights or use of changing evidence. There
is no modeled GRN/readout/derive computation fee; host CPU changes are separate from organism fitness. S-minus-C
includes continuing gene/phenotype updates and readout catch-up: pre-fork division partitions the mother's genes
after phenotype decoding, so a later readout may change phenotype even without a new gene-update step. This is
why identity_clamp alone is not the chosen control. Network feedback prevents additive mechanistic attribution.

Claims copy daughter genes at send time, never reread the mother at resolution, and still resolve after the
fork. Pending birth can occur before 768.25; associated presence notices settle before 768.75. Birth decodes
phenotype and initializes weights unconditionally in C and F. Every existing cell's first post-fork tick occurs
before 770.969690, latest pending newborn tick before 771.219690, and pre-fork spike arrivals before 771.002166.
These bounds precede accounting open 800. Chemistry continues indefinitely; settling does not erase membrane
states, past chemistry, cached weights or moving-world history. Early differences may persist into measurement.
No claim of adult maturity, a new algorithm or matching footprints across genotypes is made.

All nine arms must have zero measured births/deaths and last_birth < 800. Within each genotype, complete,
guard-free matched S/C/F triplets must have equal terminal total/sense/motor/hidden counts, t_end 1536, and
live_time equal to 736 times terminal count within integration tolerance. Guard/extinct rows stay in fitness;
only their structural-check exclusion is counted. Capacity and ledger mismatch are implementation failures
that leave the study incomplete. Income, every cost and ordinary guard/extinction penalties are retained.

The fixed cap is 3,600 cumulative CPU-seconds with two simulation threads, no extension or automatic reset.
The monitor counts its own CPU, including waiting, plus worker and descendant CPU; it stops at 3,588 seconds,
then sends TERM and KILL with a bounded two-second wait. Child limits and exact-parent death termination provide
independent safeguards. R waits only for Q to report complete with empty active and queued jobs. Q's results
never change R; an abnormal Q stop requires operational review before launch.

Preparation runs only source checks, saved D genetic replay and pure/mock tests. Existing fixed-window checks
are reused. The two standard numerical-identity startup goldens run only after worker release, reuse seed 11
at T200, are separate from 4,608 research lives, and count toward the same CPU cap. No extra validation lives,
readiness marker or launch is created by preparation.

### S. Scoring-budget comparison — prepared and held (2026-10-14)

The complete prospective protocol and independent reviews are preserved in
`results/scoring_budget_20261014/`. S is **held at the user's wrap-up request**. No readiness marker, reference
freeze, resource record or simulation exists; this preparation is not authorization to launch.

The comparison uses the same D founders, run seeds 52091/52092, initial 32 genomes and post-initialization RNG
states as P. S would run eight generations with six initial and eight recheck lives, against P's sixteen with
three and four. Both spend 16,384 selection genome-lives per branch. Duration-weighted exposure differs
(S 18,944 T1024-equivalent lives per branch; P 20,480/17,920), and actual CPU would be reported separately.
Both completed P generation 16 rank0 references must be audited and frozen together before either S search.
Both S generation 8 rank0 endpoints are fixed before fresh six-role D/P/S confirmation.

Block 105 is reserved: 52,050,000 through 52,050,255, shared across three durations and all six roles. Primary
effects compare each S endpoint with its matched P endpoint, with durations averaged within each seed before
SE. Secondary S/P−ownD comparisons retain both branches and every sign. The proposed scope is 37,484 research
lives under 14,400 cumulative CPU-seconds, at most four search threads, with R as a resource dependency.
All 103 pure/mock checks pass; no research lives were simulated by preparation. The copied full PREREG and
protocol control the detailed accounting, source pins, incomplete-study rules and limitations.

### U. Ordinary evolution in the existing harmful-decoy world (2026-10-14)

The user's renewed autonomous-work instruction authorizes this bounded existing-world pilot. The complete
frozen protocol, source/seed/initialization reviews and synthetic accounting checks are in
`results/decoy_evolution_20261014/`. Two fixed I winners each start an ordinary four-generation 32+224 search,
with run seeds 53091/53092 and unchanged 3+4 evaluation. Both generation-4 rank0 endpoints are fixed before
fresh scoring. Both founders and endpoints share 512 block106 seeds in trained, width-swapped, frozen and
frozen-lateral-off conditions. Primary effects are each endpoint minus its own founder in the trained world.
Width reversal also changes sensing geometry; freeze suppresses growth and regulatory updates. Full captures,
harmful clicks and costs accompany every contrast; none alone proves discrimination or a new algorithm.

The 7,200 cumulative CPU-second cap permits at most 3,600 for search, reserving half for confirmation. At most
four search workers or two confirmation workers run. The fixed scope is 16,460 research lives plus six startup
T200 validation lives. Block107 remains reserved for validation. Incomplete stages block outcome inference;
no restart, endpoint replacement, extension or partial-study claim is allowed. No old study is reopened.

### V. Information payoff in the existing fast persistent-target world (2026-10-14)

The frozen protocol and independent reviews are in `results/prediction_information_20261014/`. Seven unchanged
external instruments/references share 512 fresh block108 seeds at T1024: whole and smaller frozen/retuned
reflexes, a quieter reflex, and the recovered full/ablated particle filter. The existing ABI 3 world changes
only target speed to .3 and mean turn interval to 200; ordinary conduction and all prices remain fixed.
The full controller is measured at the whole reflex's 56-cell footprint. Primary contrasts are full minus
best whole reflex and full minus broad moving-target-model ablation. Both fixed-reflex comparisons and the
three do-less variants remain in the report. Selecting the best reference makes its SE conditional/descriptive.

The ablation removes velocity and turning throughout filtering, propagation, capture modeling and anticipatory
actions. It cannot isolate prediction; that admission question remains incomplete whatever the result.
The instrument never enters an organism, and free controller computation does not establish local attainability.

The total cap is 3,600 CPU-seconds with two workers for 3,584 research lives. Four fixed block109 calibration
lives consumed 11.558130849 CPU-seconds including compilation/startup, already inside that cap. Their scores
do not select parameters or count as scientific evidence. Twelve retained action replays match exactly;
all calibration ledger columns and fitness independently reconcile. Research release requires host-level proof
that every U process/group exited, irrespective of U's scientific outcome. Partial candidate batches, guards,
invalids or mismatches block inference; no rows are censored. No research lives have run at registration.

### X. Information payoff when target cues dim or disappear (2026-10-14)

The user-approved flash and irregular-blink ABI4 presets retain ordinary conduction and SPECK prices.
The frozen protocol in `results/visibility_information_20261014/` specifies thirteen fixed candidates per
world, each on 512 shared fresh T1024 seeds. I is the unchanged historical C5 at hollow3 (56 cells); R0/R1
are the frozen and historical per-world retuned reflexes at that same footprint. A removes the broad
visibility model; B suppresses actions while the controller believes the target is dark. Eight fixed smaller
or quieter references reproduce the historical scoring script. No controller is retuned or put into an organism.

Block113 is reserved for research, seeds 52,130,000 through 52,130,511. Block116 is reserved for validation,
seeds 52,160,000/1. The final numeric inventory and text-formula review find no prior overlap. Blocks114/115
are held suggestions for a separate duration extension and remain unreserved. W remains an unreleased
moving-target gradient outline; X does not release it or any closed-batch study.

Primary information contrasts are I minus each fixed reflex and minus the better whole-sample reference.
All eight do-less contrasts, paired quarter-gap margins, captures, low-light captures and cost components
are retained. Selected-reference summaries are descriptive. Neither broad ablation isolates memory; the
capability-specific condition and G5 duration transfer remain incomplete whatever these results show.

The first-attempt-only cap is 3,600 cumulative CPU-seconds for 13,312 research lives plus exactly 82 validation
calls. Validation includes 16 scratch/production physical-bridge lives, 24 full/fast lives, 30 callback/action
record/replay/control lives and 12 cost-calibration lives. It must finish within 180 CPU-seconds included in
the total cap. At most two one-thread research workers run. Compilation, failures, monitor and descendants
count toward the cap. Raw ABI sizes, source/numerical pins and actual monitor ownership are checked before
dispatch. Any validation failure, guard, unexpected extinction, invalid/missing row or budget/cleanup failure
leaves the study incomplete. There is no retry, resume, sample replacement or parameter change.

The independent analyzer reconstructs candidates and all 57 scratch ledger columns without engine imports.
Both callbacks and requested actions must replay exactly; the production low-light readout is bridged explicitly.
Root release follows reviewed preparation, terminal U/V resource clearance and public prospective publication.
At registration, no X library has been compiled and no X life has been simulated.

### X2. Initialization repair with the same fixed scientific comparison (2026-10-14)

X stopped at its runtime-identity check before compilation or any life, consuming 0.716548 CPU-seconds.
Its immutable first-attempt archive is `results/visibility_information_20261014/`; no result is inferred.
X2 is separately registered at `results/visibility_information_x2_20261014/`. It imports Torch before
discovering/checking numerical libraries, consistently with preparation. Exact runtime equality remains
required. Fresh, frozen-source-first and production-import-first processes now agree; a deliberately
system-OpenMP-first process remains rejected. No controller, organism, world or scoring behavior changes.

All 26 candidate definitions, both packed worlds, the 13,312 + 82 call matrix, analysis rules and seed lists
remain byte-for-byte unchanged. Registered but unconsumed blocks113/116 transfer to X2; no new seed search
occurs, and blocks114/115 remain held and unreserved. The new total/validation caps are 3,599/179 CPU-seconds,
so adding X's failed startup gives maxima 3,599.716548/179.716548, below the original 3,600/180 allocations.
X2 retains its own first-attempt lock, no resume/replacement, complete-batch analysis and process cleanup.
Its resource clearance binds X's terminal budget in addition to U/V. At this amendment, X2 has compiled no
library and simulated no life. The real fixed validation package still precedes every research row.

### Y. Ordinary mutation accessibility in irregular blink (2026-10-14)

Complete X2 evidence supports useful information payoff in both approved visibility worlds. This bounded
diagnostic selects irregular blink, where the cue disappears, without requiring a constructed body or evolved
founder to win. It measures accessible ordinary mutations around the exact confirmed D90 and L92 endpoints
(rows 3 of the D/L confirmation genotype arrays), not a memory mechanism or a large selection rollout.

Each background receives the unchanged ordinary mutation policy: 64 mutants, two scaled mutations, cell
probability .5, and no duplication/deletion/split. Preserve duplicate/no-op mutants. Generate each panel once
with RNG seeds 53117/53118 and freeze all 65 rows and operations before scoring. Both panels and their parents
share 32 screen seeds from block 117 (52,170,000–52,170,031). Select the highest mean production F among rows 1–64
within each background, breaking ties by row order, even if its parent comparison is negative. Freeze both
winners before either confirmation. Each winner and its own parent share 512 fresh block 118 seeds
(52,180,000–52,180,511); no rescore stage or endpoint replacement is included.

The exact production ABI4 blink preset at T1024 retains ordinary conduction and SPECK prices. Old founder
POOL/fast-conduction overrides are removed in explicit derived configs; original configs remain archived.
Every raw 58-column ledger, ordinary guard/extinction penalty and cost component is retained. Primary
comparisons are paired mutant-minus-own-parent F, separately for D90/L92. Report captures, dark/bright
captures, capture income, cost savings, body size and activity. More dark captures alone cannot distinguish
memory from coasting, chance or morphology; an unresolved confirmation does not prove no useful mutation exists.

The first-attempt-only limit is 5,400 cumulative CPU-seconds with one two-thread worker. Startup and screens
have a 3,400-second ceiling, leaving 2,000 for confirmation and cleanup; both have ten-second stopping margins.
Scope is 6,208 research plus ten validation lives. Startup calls the existing numerical identity once, including
two deliberate ABI3 seed 11/T200 goldens, then evaluates each parent and its predetermined first mutant on
block 119 seeds 52,190,000/1 (eight ABI4 calibration lives). Compilation, startup, failures, monitor and descendants
count. Expected source/runtime metadata is pinned beforehand; newly captured library/golden hashes are
identified as such rather than described as independently replayed proof.

Calibration uses each background's larger parent/first-mutant CPU per life. With a 1.5 safety factor, observed
startup/calibration plus projected screening must fit 3,390 seconds, and projected confirmation must fit 1,990.
Otherwise the unchanged study stops incomplete before screening. These rates cannot bound unseen mutants;
aggregate caps remain enforced. No automatic retry, resume, scope reduction, sample replacement or budget
extension is allowed. Complete fixed coverage and independent raw/genetic/accounting checks precede inference.
Prospective artifacts are preserved at `results/visibility_gradient_20261014/`; preparation runs no simulations.
