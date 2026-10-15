This retrospective was specified after AN finished and before inspecting any AO outcomes. It reprices the same 512 paired seeds for AN’s fixed start, generation 4 and generation 8 in POOL, persistent and blink80_20. The mixture is 25%/25%/50%; capture value stays 500. No life, genotype, production price or selection rule was changed.

At original prices, generation 8 minus generation 4 has mixed F **+0.10780 ± 0.04885 SE**, but captures **−0.22510 ± 0.09820**. Maintenance savings contribute +0.20406 F, while capture income falls 0.10991 and miss charges rise 0.00933. Thus the positive mean F difference is primarily economy; it does not itself exceed three SE.

The selective repricing results for that same paired difference are:

| Changed price | Multiplier | Mixed ΔF ± paired SE |
|---|---:|---:|
| Maintenance | 0 | −0.09626 ± 0.04759 |
| Maintenance | 0.25 | −0.04525 ± 0.04777 |
| Maintenance | 0.5 | +0.00577 ± 0.04804 |
| Maintenance | 1 | +0.10780 ± 0.04885 |
| Maintenance | 2 | +0.31186 ± 0.05144 |
| Miss | 0.5 | +0.11246 ± 0.04895 |
| Miss | 1 | +0.10780 ± 0.04885 |
| Miss | 2 | +0.09847 ± 0.04873 |
| Miss | 4 | +0.07980 ± 0.04885 |

The continuous mean crossings are **0.471735× maintenance** (c_live≈0.009435) and **12.551725× miss price** (c_miss≈125.52). These are descriptive ratios, without crossing confidence intervals. Only the 2× maintenance result above exceeds three SE; lowering maintenance does not establish a reliably superior generation-4 phenotype.

Generation 8 remains below both earlier phenotypes in POOL throughout these grids and above them in persistent and blink80_20 by mean F. The mixed mean ranking changes from g8>g4>start to g4>g8>start at maintenance multipliers 0 and 0.25. Doubling maintenance or raising miss price to 2–4 swaps the near-tied start/g4 POOL order. All absolute scores and three paired contrasts per world are in `summary.json`.

The pinned kernel uses c_live/c_miss only for accounting (kernel.c:1261,1475,1913–1933); they do not feed cell dynamics. Maintenance also prices guard and extinction penalties (evaluate.py:261–270), which this calculation scales; all nine analyzed rows have status zero. Therefore these are exact mathematical repricings of retained trajectories, within floating-point tolerance, not predictions of altered evolution. Ledger values and hashes would change.

Maintenance is the more influential selective penalty here. Neither crossing identifies an optimal price or a richer algorithm. Shared-seed mixtures preserve covariance; 512 lives are not evolutionary replicates. Reproduce with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/an_cost_sensitivity_20261015/analyze.py --out outputs/an_cost_sensitivity_reanalysis.json`; the script verifies every retained raw/source pin and uses the reviewed literal accountant.
