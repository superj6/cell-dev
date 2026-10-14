# Selection resampling diagnostic: completed D, G and L

This audit compares the saved initial three-life mean with the four fresh recheck lives, and the
actual parents chosen from their pooled seven-life mean. It covers all 96 generations in six
completed searches, retaining every one of the 6,144 shortlisted candidate records.

| Run | Replaced parent slots | Mean replaced / 32 | Leader IDs changed | Strict top displacement |
| --- | ---: | ---: | ---: | ---: |
| D_s51089 | 192 / 512 | 12.00 | 15 / 16 | 15 / 16 |
| D_s51090 | 190 / 512 | 11.88 | 13 / 16 | 13 / 16 |
| G_s51089 | 189 / 512 | 11.81 | 12 / 16 | 12 / 16 |
| G_s51090 | 184 / 512 | 11.50 | 11 / 16 | 11 / 16 |
| L_s51891 | 187 / 512 | 11.69 | 13 / 16 | 13 / 16 |
| L_s51892 | 178 / 512 | 11.12 | 12 / 16 | 12 / 16 |

“Strict top displacement” means no original maximum-score candidate shares the recorded pooled
maximum, and the recorded last survivor scores below the maximum. In that case all pooled maxima
are present among the saved survivors; an unselected candidate is bounded by the recorded cutoff.
This classification uses actual saved pooled scores, not reconstructed means.
Identity changes with overlapping top-score sets are reported separately;
they are not treated as clear winner reversals. Parent replacements use the exact logged shortlist
order and survivor set, including their actual random tie decisions.

| Run | Recheck − base mean | Median | RMS | Mean within-generation rank correlation |
| --- | ---: | ---: | ---: | ---: |
| D_s51089 | -1.070 | -0.970 | 2.035 | 0.012 |
| D_s51090 | -1.739 | -1.743 | 2.337 | 0.024 |
| G_s51089 | -1.081 | -1.038 | 2.029 | 0.042 |
| G_s51090 | -1.709 | -1.686 | 2.354 | 0.061 |
| L_s51891 | -1.315 | -1.196 | 1.988 | 0.043 |
| L_s51892 | -0.979 | -1.030 | 1.723 | 0.034 |

Life-duration breakdown (all groups retained):

| Run and T | Generations | Mean replaced / 32 | Strict top displacements | Recheck − base mean |
| --- | ---: | ---: | ---: | ---: |
| D_s51089_T768 | 5 | 12.80 | 5 | -1.768 |
| D_s51089_T1024 | 8 | 11.25 | 7 | -0.773 |
| D_s51089_T1536 | 3 | 12.67 | 3 | -0.699 |
| D_s51090_T768 | 5 | 10.80 | 4 | -1.619 |
| D_s51090_T1024 | 6 | 12.33 | 4 | -1.606 |
| D_s51090_T1536 | 5 | 12.40 | 5 | -2.019 |
| G_s51089_T768 | 5 | 12.00 | 4 | -1.816 |
| G_s51089_T1024 | 8 | 11.38 | 6 | -0.746 |
| G_s51089_T1536 | 3 | 12.67 | 2 | -0.747 |
| G_s51090_T768 | 5 | 10.40 | 3 | -1.642 |
| G_s51090_T1024 | 6 | 11.17 | 5 | -1.515 |
| G_s51090_T1536 | 5 | 13.00 | 3 | -2.010 |
| L_s51891_T768 | 6 | 13.00 | 5 | -1.684 |
| L_s51891_T1024 | 2 | 9.00 | 2 | -1.063 |
| L_s51891_T1536 | 8 | 11.38 | 6 | -1.102 |
| L_s51892_T768 | 5 | 12.20 | 4 | -1.268 |
| L_s51892_T1024 | 6 | 9.83 | 5 | -0.759 |
| L_s51892_T1536 | 5 | 11.60 | 3 | -0.953 |

Across these records, 1120 of 3,072 parent slots changed (36.5%). There were 76 strict top displacements, 0 changed leader IDs with overlapping top sets, and 0 unresolved top-set comparisons.

The smallest strict displacement margin, using actual recorded scores or the survivor cutoff as
an upper bound for an unselected initial leader, is
0.000067 F.

These are descriptive totals, not independent replicate estimates. `summary.json` also reports every
run separately by life duration; `generations.json` preserves tie sets and rank intervals;
`candidates.csv` preserves the exact saved means, signed differences and actual selected ranks.

The recheck used 24,576 of the 98,304 selection genome-lives (25%). Logged evaluation wall time
attributes 25.2% to rechecking. This elapsed-time ratio
is not a CPU-budget measurement and does not predict the cost of another policy.

The logs establish that finite life samples often change immediate selection. They cannot tell us
whether those changes improve later independent fitness, or whether spending the same compute on
more candidates or generations would do better. A future fixed-budget comparison could test that;
these diagnostics alone do not justify increasing the scoring budget.

## Limits

- Every candidate was shortlisted using its initial three-life mean; the observed score changes are conditional.
- Four recheck lives use fresh shared seeds at the same T. World difficulty and common seeds correlate candidates.
- Repeated and related genomes, sequential selection, and varying T prevent treating candidate rows as independent.
- D and G use matched run/life seeds; their records are not independent replicates.
- Logged changed counts use the recheck shortlist ranking, not the separate earlier one-stage tie draw.
- Recorded survivor order and pooled fitness are authoritative; saved stage means are only a consistency audit.
- Missing per-life scores prevent an exact pooling-error bound; the reconstruction tolerance is empirical.
- Exact top-score sets are shown among logged candidates; a full tied set may extend beyond a recorded cutoff.
- Mean, median, RMS and rank summaries describe conditional disagreement, not an unconditional noise sigma or SE.
- No individual training-life scores are in these lineage records; per-genotype life variance is not recoverable.
- Parent or leader turnover does not establish improved fresh fitness or equal-compute search efficiency.
- No active P outcomes, research simulations, new protocol, source changes, or new selection policy were used.

## Reproduce

From the repository root:

```sh
.venv/bin/python results/selection_noise_20261014/analyze.py --out outputs/selection_noise_reanalysis
```

Only completed public D/G/L archives are read. Every artifact in each original provenance manifest
is checked before lineage analysis. No simulation or engine import is performed.
