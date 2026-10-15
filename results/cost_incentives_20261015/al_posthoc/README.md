# AL: cost contributions and post hoc score sensitivity

Maintenance dominates the observed cost penalty. On persistent targets it is
80.25% of AI-start's ordinary cost, 73.97% of the control endpoint's, and 79.36%
of the mixture endpoint's. Spike plus message charges are only 0.57%, 0.35% and
0.72%, respectively. A communication discount therefore has little effect on
these particular recorded bodies.

The mixture endpoint catches **2.558594 ± 0.160285** more persistent targets than
the control, yet has **−0.356124 ± 0.075793 F** at the original prices. Its extra
capture income is +1.249313 F per unit time, while extra ordinary cost is
−1.605437, of which −1.307917 is maintenance. Mean final cell counts are 64.64
for AI-start, 23.68 for control, and 90.36 for mixture. These are whole-body
comparisons; larger bodies or more activity do not prove better computation.

The following table re-scores exactly those same persistent-target lives.
Entries are mixture-minus-control F, mean ± paired SE. Capture value stays 500.

| Cost multiplier | All ordinary costs | Living cost only | Spike + message costs only |
|---|---:|---:|---:|
| 0.25 | +0.847954 ± 0.077225 | +0.624814 ± 0.076263 | −0.345725 ± 0.075851 |
| 0.5 | +0.446595 ± 0.076461 | +0.297835 ± 0.075940 | −0.349191 ± 0.075832 |
| 1 | −0.356124 ± 0.075793 | −0.356124 ± 0.075793 | −0.356124 ± 0.075793 |
| 2 | −1.961561 ± 0.077928 | Not requested | Not requested |

The mean-score crossings are about 0.7782 times all ordinary charges or 0.7277
times the living charge alone. They are crossings between these fixed endpoints,
**not optimal biological prices**. At the original `c_live=0.02`, a living-only
multiplier of 0.5 corresponds to 0.01. A new evolution experiment would be needed
to learn what that incentive produces.

The comparison with AI-start is more restrained. Mixture catches
−0.078125 ± 0.199511 fewer persistent targets, an unresolved difference, and its
ordinary cost is 0.649600 higher per unit time. Consequently its point-estimate
F remains below AI-start at every nonnegative uniform cost multiplier; even
with zero ordinary charges the capture-income difference is −0.038147. The
requested 0.25 multiplier narrows its F difference to −0.200547 ± 0.096871; it
does not create a demonstrated capture gain or establish the predeclared 10%
retention criterion. On POOL, mixture's actual capture gain over AI-start is
3.683594 ± 0.298366 and its F gain remains positive across the requested uniform
cost range, including 2× costs.

## Contents and reproduction

`analyze.py` reads AL's 12 completed raw rows through the pinned independent
literal accountant. It requires the successful terminal raw review first.
The output directory `analysis_result/` contains:

- `absolute_cost_contributions.csv`: all three roles in all four worlds,
  original physical captures/F, all nine ordinary charge categories and cost shares.
- `paired_cost_contributions.csv`: both endpoints minus AI-start in each world,
  plus the already reported mixture-minus-control comparison.
- `counterfactual_scores.csv`: each paired score at all requested multipliers.
- `mean_score_crossings.csv`: optional point-estimate crossings, with no optimum claim.
- `summary.json` and `paired_arrays.npz`: full provenance and 240 fixed-life
  vectors (120 paired, 120 absolute). Scale 1 reproduces original F exactly.

Run from the repository with a new output path:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  outputs/cost_incentives_20261015/al_posthoc/analyze.py --out <new-output-directory>
```

No raw lives are duplicated here: `summary.json` identifies their paths and
SHA-256 hashes. The exact completed AL protocol, endpoint identities, raw row
hashes and the independent accountant source are checked before scoring.
`execution.stdout.json` and `execution.stderr.txt` preserve the first successful
execution. `artifact_manifest.json` pins this script and all outputs.

This was requested after AL completed and is exploratory. All scenarios retain
the actual physical trajectories, captures and original production F. Guard and
extinction charges are held at their recorded values; every AL confirmation life
has status zero, so these charges are all zero. A real change to `c_live` also
changes those penalty coefficients, but that distinction has no numerical effect
on these particular lives. Paired uncertainty uses the complete per-seed score
difference, retaining covariance. Three-SE bounds are descriptive, with no
multiple-comparison adjustment. No prices, engines, genotypes or selection runs
were changed, and no new lives were simulated.
