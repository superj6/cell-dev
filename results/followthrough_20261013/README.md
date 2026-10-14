# Following useful mutations through duration, selection and allele effects

All experiments keep the organism local and asynchronous and use existing ABI 3 worlds and prices. The genotypes and comparisons were frozen before scoring; transfer outcomes select no replacement genotype.

[Watch the original s5 parent beside its first-step descendant](watch.html). The page starts paused and uses a fixed illustrative seed; these single lives were not used to choose a genotype. Source, exact bodies, license and short parity checks are in `watch/`.

## Transfer of the first-step winners

The equal duration mixture averages each seed's gains at T768, T1024 and T1536 before calculating SE. The conduction interaction subtracts the old-conduction gain from the fast-conduction gain at T1024.

| Fixed winner | Duration-mixture gain, F ± SE | Old-conduction T1024 gain | Fast − old gain |
|---|---:|---:|---:|
| s5 / base | +0.586 ± 0.167 | -0.132 ± 0.166 | +0.768 ± 0.241 |
| s5 / pool | +0.953 ± 0.170 | +0.212 ± 0.136 | +0.721 ± 0.227 |
| s7 / base | +0.532 ± 0.160 | -0.011 ± 0.164 | +0.574 ± 0.245 |
| s7 / pool | +0.440 ± 0.120 | +0.107 ± 0.113 | +0.316 ± 0.172 |

These are unchanged winners, including the earlier weak s7/POOL result. The same s5 genotype appears in two worlds; four comparisons do not mean four independent discoveries. All four duration averages are positive by more than three SE on this batch. The old-conduction gains are unresolved; the fast-minus-old interaction exceeds three SE for the s5 genotype in both worlds. This supports conduction-dependent expression of that genotype's advantage, without identifying the mechanism.

## A second step under two scoring budgets

One fixed pool has 224 ordinary mutants of the prior s5 winner, plus 32 copies of that founder in the selector. Both selectors shortlist 64 and retain 32. The lower budget uses 3 + 4 lives; the higher uses 12 + 16. One winner from each is frozen and measured on 512 independent paired lives.

| Selector | Chosen candidate row | Additional gain over first-step winner, F ± SE | Total over original s5 |
|---|---:|---:|---:|
| 3 + 4 | 148 | +0.064 ± 0.142 | +1.012 ± 0.129 |
| 12 + 16 | 148 | +0.064 ± 0.142 | +1.012 ± 0.129 |

Higher-budget winner minus lower-budget winner: **+0.000 ± 0.000 F**.

This is a single cloned-parent candidate pool at T1024. It can demonstrate another available step or a difference between two selector choices; it cannot establish typical search efficiency, equal-compute superiority, or reliable long-term accumulation.

Both rules chose the identical genotype, so the high-minus-low comparison is exactly zero. This cohort supplies no winner-quality separation between the two scoring budgets. Fresh confirmation does not resolve an additional gain over the first-step founder, so this cohort does not confirm a second accumulation step.

## Effects of the two already discovered s5 alleles

A copies the evolved W[1,16] allele, which reads the first internal chemical signal. B copies W[4,24], which reads the local motor-plane cue. AB is the exact prior winner. These are fixed measurement reversions of evolved values, with no allele tuning.

| World | A − parent | B − parent | AB − parent | AB − A − B + parent |
|---|---:|---:|---:|---:|
| base | +0.548 ± 0.138 | -0.143 ± 0.053 | +0.550 ± 0.140 | +0.145 ± 0.075 |
| pool | +1.064 ± 0.115 | -0.009 ± 0.042 | +0.984 ± 0.112 | -0.071 ± 0.065 |

The interaction measures nonadditive fitness. These alleles change gene regulation and development; the measurements do not establish a new routing algorithm or an adult-only mechanism. A alone improves fitness by more than three SE in both worlds. Neither B's added effect on A nor the interaction clears three SE; this batch gives no evidence that B is required for the gain. An unresolved contrast is not evidence of zero effect.

## Evidence and limits

- `summary.json` independently reconstructs paired effects, income and cost changes from aggregate arrays.
- Experiment directories preserve all aggregate NPZ files, original manifests and reports; second-step genomes and operations and the four factorial genotypes are included when complete.
- `inputs/prior/` preserves the prior parent/configuration/genotype artifacts used by these experiments. `sources/` preserves the measured runner and helper sources.
- The [prior archive's lesion clarification](inputs/prior/ERRATA.md) states that new lateral spike messages are suppressed after the fork, while messages already in flight are processed normally. Pinned original archive files remain unchanged.
- `behavior_from_ledgers/` preserves a retrospective analysis of the earlier 512-life confirmations, with zero additional simulated lives. It reports movement, sampled occupancy, clicks/capture and development; these are descriptive associations and do not isolate adult circuit function.
- `validation/second_step_final_audit.json` records 294 short validation-only genome-lives. The first smoke consumed reserved G2 seeds 51,100,000 and 51,100,001 at T32; exclude both from future G2 evidence. The final smoke used validation blocks 8 and 9, and none of the scientific blocks 85–88.
- `operations/` contains available external CPU-monitor records. Intermediate exports may contain a running-monitor snapshot; every experiment's own completed row CPU is also retained.
- `provenance.json` hashes public artifacts. `analyze.py` can rebuild all reported statistics and figures without simulating new lives.
- None of these measurements admits or rejects a world, measures matched-footprint information use, or proves long-term evolutionary accumulation. Fitness remains task income minus the existing costs.

```bash
.venv/bin/python results/followthrough_20261013/analyze.py \
  --study results/followthrough_20261013 --out outputs/followthrough_reanalysis --export --allow-partial
```
