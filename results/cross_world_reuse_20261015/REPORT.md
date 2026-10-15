# Shared genomes across four environments

**There is no confirmed broad capture improvement in these records.** Three L92 mutants have positive capture estimates across all four existing screens, but all twelve estimates are unresolved. The strongest confirmed cross-world result is a fitness improvement from economy: D90 row 54 saves substantial costs in every world while losing captures in blink and dim flash.

This is an offline exploratory comparison, not a new experiment. It uses all 130 original Y genomes (65 per parent), with exact byte alignment across Y, AC, AE and AG. The 520 screen rows cover 16,640 already completed lives. Separately, 24 frozen confirmation rows cover 12,288 existing lives and supply 14 mutant–parent comparisons. All inspected raw statuses are zero. No simulation, genetic draw, compilation or engine import was performed.

## What was compared

Each screen estimates every mutant against its own parent on the same 32 life seeds. Different worlds use different seeds, so no elementwise cross-world pairing or pooled cross-world uncertainty is used. Every table retains both parents, every mutant and every negative result. Fitness is decomposed as capture-income change plus ordinary cost savings, guard-charge savings and extinction-charge savings. Positive cost savings mean lower cost.

| World | Existing study | Target and visibility | Raw ledger |
|---|---|---|---|
| Irregular blink | Y | Speed 0.1, turn time 20; irregular on/off periods with mean 20 | ABI4, 58 columns |
| Dim flash | AC | Speed 0.1, turn time 20; five bright time units after every target placement, then visibility 0.25 | ABI4, 58 columns |
| Persistent target | AE | Speed 0.3, turn time 200; continuously visible | ABI3, 57 columns |
| Dark flash | AG | Same flash rule as AC, with visibility 0 after each five-unit flash | ABI4, 58 columns |

All use duration 1024 and the same capture reward and physical prices. Placement includes timer and capture replacement, so flash restarts throughout a life. Persistent target differs in motion as well as visibility; this is not a controlled single-factor comparison. Full world dictionaries and ledger column names are in `analysis_result/summary.json`.

## Exploratory candidates

L92 rows **3, 41 and 59** are the only mutants with positive mean capture changes in all four screens. No D90 mutant does. None of these three L92 rows has a retained 512-life confirmation. Inspecting 128 mutants across four already-used screens creates selection bias; positive signs alone are not evidence of generalization. Even unadjusted, every capture estimate for these three rows is below three paired standard errors.

If one panel candidate is needed for a small subsequent fixed-genome test, **L92 row 3** is the clearest exploratory capture-oriented choice: fitness and capture means increase in all four screens, with little cost reduction. This is a candidate to test, not an established improvement. Row 59 is a reasonable economy comparator; its fitness gains mostly reflect savings. Row 41 slightly loses fitness in persistent and dark-flash worlds.

| L92 row 3 vs parent | Captures/life, mean ± SE | Fitness, mean ± SE | Capture income/time | Ordinary savings/time |
|---|---:|---:|---:|---:|
| Irregular blink | +0.312 ± 0.398 | +0.140 ± 0.194 | +0.1526 | -0.0129 |
| Dim flash | +0.094 ± 0.552 | +0.066 ± 0.265 | +0.0458 | +0.0206 |
| Persistent target | +0.219 ± 0.219 | +0.092 ± 0.106 | +0.1068 | -0.0151 |
| Dark flash | +0.094 ± 0.094 | +0.029 ± 0.054 | +0.0458 | -0.0169 |

Its exact float32 genome SHA256 is `80642e40f333d16571c0d8300a4ab5ba64bc0fcc96632b0bf57b9c35028258fb`, row 3 of the retained L92 panel. No new genotype file was created. D90 rows 13, 18 and 60 meet only the weak nonnegative-capture condition: all measured outcomes equal their parent in all four screens. They are not improvements.

## What existing confirmations actually support

All numbers below use the previously frozen 512-life comparisons; ± denotes one paired standard error. The same D90 row 54 was selected independently by the AC, AE and AG fitness screens, and AC also evaluated it in blink.

| D90 row 54 vs parent | Captures/life | Fitness | Ordinary savings/time |
|---|---:|---:|---:|
| Irregular blink | -2.100 ± 0.171 | +0.796 ± 0.083 | +1.821 |
| Dim flash | -1.459 ± 0.181 | +1.100 ± 0.092 | +1.812 |
| Persistent target | -0.328 ± 0.150 | +1.733 ± 0.077 | +1.893 |
| Dark flash | +0.049 ± 0.069 | +1.829 ± 0.040 | +1.805 |

This is confirmed fitness retention across these four known worlds, chiefly from lower physical costs. Its blink and dim-flash capture losses exceed three paired SE; the persistent and dark-flash capture differences are unresolved. It does not establish a broader capture algorithm.

Other confirmations are narrower: D90 row 58 improves blink captures in both Y (+0.889 ± 0.157) and AC (+0.732 ± 0.161), but AC dim-flash transfer (+0.344 ± 0.172) is unresolved. L92 row 31 improves persistent captures (+0.418 ± 0.105), and L92 row 61 improves dark-flash total captures (+0.221 ± 0.071), while most of their fitness gains come from savings. Those two L92 rows have negative blink/dim-flash capture screen means, with large uncertainty; they have not been confirmed as broadly retaining captures. L92 row 16’s dim-flash confirmation (+0.568 ± 0.191) remains just below the strict three-SE threshold. All 14 comparisons, including unresolved and negative results, are retained in the machine table.

## Limits and artifacts

The four environments are related chase tasks already used for development. There was no selection across multiple worlds and no untouched held-out task in this analysis. Shared ancestry, repeated panels and reused historical comparisons are not independent evolutionary replications. Capture under reduced visibility alone does not demonstrate memory. The three-SE columns are descriptive, not multiplicity-adjusted significance tests.

- `analysis_result/all_genomes_cross_world.csv`: all 130 genomes, four-world capture/F/cost deltas, retention and confirmation availability.
- `analysis_result/screen_table.csv`: all 520 screen rows, absolute means, paired effects and physical cost components.
- `analysis_result/existing_confirmation_table.csv`: all 14 frozen mutant–parent contrasts.
- `analysis_result/paired_vectors.npz`: 12,552 paired metric vectors; `cross_world_correlations.csv` contains descriptive correlations only.
- `analysis_result/input_hashes.json`: exact paths, sizes and SHA256 for every consumed file and the analysis sources; each input row is checked against its published archive manifest and row index.
- `analysis_result/output_hashes.json`, `execution_stdout.json`, `execution_stderr.txt`: output hashes and the successful execution record.

Reproduce without engine imports, into a new output directory:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python \
  outputs/cumulative_capability_20261015/cross_world/analyze.py \
  --out outputs/cumulative_capability_20261015/cross_world/reanalysis
```
