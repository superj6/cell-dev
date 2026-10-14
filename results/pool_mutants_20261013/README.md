# Nearby mutations in base and POOL

This bounded study asks whether ordinary random mutations offer useful steps from the evolved s5 and s7 bodies,
and whether those steps depend on lateral spikes. It changes no organism rules, fitness prices or world defaults.
It does not admit or reject worlds and does not require a hand-built body to win.

The protocol was committed before scoring in `d90665f`:
[preregistration](../taskvar/prereg.md#bounded-autonomous-diagnostic-2026-10-13).
The scoring and confirmation runners were frozen before their respective measurements.

## Findings

Three of four parent/world comparisons clear both registered confirmation thresholds (mean gain >3 SE and
at least +0.5 F). They involve two successful unique genotypes: the same s5 mutant wins in both worlds.

| Parent/world | Winner genome row | Fresh gain, F ± SE | Gain removed by lateral lesion, F ± SE |
|---|---:|---:|---:|
| s5 / base | 38 | +0.846 ± 0.136 | +2.110 ± 0.211 |
| s5 / POOL | 38 | +0.638 ± 0.116 | +1.644 ± 0.160 |
| s7 / base | 15 | +0.755 ± 0.129 | +1.400 ± 0.178 |
| s7 / POOL | 29 | +0.263 ± 0.092 | +0.273 ± 0.133 |

The first three gains come from extra capture income despite higher costs and larger bodies. Their message lesion
interactions also exceed 3 SE. An interaction larger than the intact gain is possible: those mutants become worse
than their parents when lateral spikes are blocked. s7/POOL misses both confirmation thresholds, and its lesion
interaction also misses 3 SE; it remains an uncertain, small improvement.

These results establish useful nearby steps around both parents under the measured settings. They do not establish
new routing or memory. The selected changes affect gene regulation and initial gene levels; none directly changes a
spike-channel weight. For s5, one mutation changes the response to an internal chemical signal and the other changes
the response to the local motor-plane cue. Allele names do not establish the resulting circuit mechanism.

An exploratory ranking check finds that the successful s5 mutant scores no better than its parent in 30.0% of
three-life base batches and 31.8% of three-life POOL batches. Normal selection shortlists on three lives before
rechecking. This motivates a controlled test of evaluation reliability; it does not prove that ranking noise caused
earlier search outcomes. First check these winners across the normal life-length mixture, then test whether a second
mutational step can accumulate under ordinary versus more precise scoring.

The study completed all 26,752 planned genome-lives. Monitored simulation CPU plus the benchmark allowance totaled
5,185 seconds (1.44 CPU-hours), below the two-hour cap, with at most four simulation workers. All eight jobs completed
successfully. Independent reanalysis of the public raw archive reproduced the complete summary and cross-world
results exactly. The confirmation tooling passed 39 focused tests, including exact row resume and source checks.

## Protocol and interpretation

- Generate 64 ordinary point-mutated genomes per parent, with the same genomes in base and POOL. Keep the active
  gene slots fixed. Both worlds use faster conduction, `d0=0.5, d_min=0.25`; POOL also uses `sigma=0.4, lam_s=4`.
- Screen on 32 paired lives. Re-score the top four per parent/world on 512 fresh paired lives, then freeze one
  winner even if its gain is negative. Confirm that winner against its parent on another 512 fresh lives.
- Independently compare parent and winner with lateral spikes intact and blocked after time 256, using 256 fresh
  paired lives for all four arms. Report `(winner-parent) intact - (winner-parent) blocked`.
- Use T=1024 and full-life accounting throughout. Seed blocks 80, 81, 82 and 83 separate the four stages. Positive
  confirmation requires more than 3 paired SE; +0.5 F is the separately registered practical threshold.
- Retain production extinction and compute-guard penalties. Reject capacity failures, ledger mismatches and
  unexplained incomplete lives. Decompose fitness into income, costs and guard/extinction charges.

The lesion blocks lateral spike arrivals; chemical exchange continues. An interaction can establish added reliance
on those spikes, but the lesion can also change later development. It cannot identify a new algorithm or isolate
adult circuit operation. The parents evolved with slower conduction; some gains may adapt to the faster setting.
Two parents and one generation of mutations do not establish sustained evolutionary accumulation. T1024 gains do
not establish robustness across the three life lengths used by normal evolution.

The 64-by-32 screen is a separately registered exploration, not the full 256-by-64, all-world G2 study. Confirmation
rates among selected winners do not estimate the fraction of all mutations that are beneficial.

## Evidence and reproduction

- `summary.json`: independently recomputed paired results, accounting and operational budget.
- `confirmation_and_lateral.png`: confirmation and four-arm interaction with ±3 SE.
- `cross_world_screen.json`, `screen_cross_world.png`: all 64 matched mutations per parent, exploratory.
- `screens/`: aggregate raw scores, original manifests, frozen selections and runner reports.
- `parents/`, `genomes/`: original configurations, parents, complete mutation pools/operations and selected genomes.
- `winner_mutations.json`: exact allele changes with distinctions between chemical regulation and spike messaging.
- `provenance.json`, `analysis_validation.json`: hashes and public-archive reanalysis checks.
- `operations/`, `sources/`: operational records and source snapshots. Invoke the repository scripts below for
  simulations; archived snapshots record the measured implementation.

Recompute and validate the public evidence, without simulating any new lives:

```bash
.venv/bin/python results/pool_mutants_20261013/analyze.py \
  --study results/pool_mutants_20261013 \
  --out outputs/pool_mutants_reanalysis --export
```

The simulation commands default to dry-run. For each body `5,7` and world `base,pool`, the measured arguments were:

```bash
.venv/bin/python -m scripts.taskvar_gradient --body 5 --world base \
  --mutants 64 --lives 32 --duration 1024 --seed-block 80 --threads 2 \
  --out outputs/autonomous_pool_20261013/screens
.venv/bin/python -m scripts.taskvar_confirm \
  --screen outputs/autonomous_pool_20261013/screens/s5_base_T1024_b80 \
  --parent results/pool_mutants_20261013/parents/s5/best_genome.json \
  --rescore-block 81 --confirm-block 82 --lesion-block 83 --lesion-lives 256 --threads 2
```

Actual execution used `--run`, AVX2 torch dispatch, `OMP_WAIT_POLICY=PASSIVE`, at most two simultaneous two-thread
jobs, and a study-wide two-CPU-hour cap. Exact simulation replay additionally requires the manifest's numerical and
source identity. On a fresh checkout, restore the archived `parents/sN/{best_genome.json,config.yaml}` to
`outputs/catch_pilot/speck_lmax4_hexprism_sex_sN/` before running the screen CLI, which uses that original path.
Use a new study directory for replay. Local incremental row checkpoints remain under
`outputs/autonomous_pool_20261013/`; the public archive keeps each aggregate once, without duplicating row files.

The small-batch ranking analysis is post hoc: split the independent confirmation pairs into disjoint batches and
count how often the mutant's mean advantage is nonpositive. Batch sizes 3 and 7 match the initial and pooled life
counts of normal selection. This measures pairwise noise; it does not replay a 256-candidate selection tournament.
