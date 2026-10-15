# Capture-value sensitivity on completed AC observations

This post hoc diagnostic reprices the same fixed AC confirmation outcomes at
capture values 500, 1,000 and 2,000. It keeps physical costs, guard charges and
extinction charges unchanged. No new lives, genetic draws, compilation, genome
selection or production-price changes occurred.

All 12 fixed within-world contrasts are retained: H−P, B−P and H−B for D90 and
L92 in flash and blink. Each uses AC's same 512 paired seeds; three prices produce
36 vectors. P is the original founder, B the retained blink-selected mutant, and H
the flash-selected mutant. For each seed, the calculation is:

`new ΔF = original ΔF + (capture_value / 500 − 1) × original Δcapture_income`.

Each complete paired vector is formed before computing its mean and standard
error. The complete signed results, including unresolved results, are in
[summary.json](summary.json). For illustration, H−B is:

| World and lineage | Value 500 | Value 1,000 | Value 2,000 |
| --- | ---: | ---: | ---: |
| Flash D90 | 0.941 ± 0.100 | 0.061 ± 0.195 | −1.699 ± 0.386 |
| Blink D90 | 0.453 ± 0.083 | −0.930 ± 0.165 | −3.695 ± 0.330 |
| Flash L92 | 0.382 ± 0.092 | 0.719 ± 0.184 | 1.392 ± 0.368 |
| Blink L92 | 0.027 ± 0.082 | 0.003 ± 0.164 | −0.045 ± 0.329 |

Values are mean changes in F ± one paired standard error. Reweighting captures
substantially changes the D90 comparison. It does not show what evolution would
produce under another reward, or add independent evidence of behavior, memory or
algorithmic sophistication. The grid was chosen after seeing AC's economy/capture
tradeoff, and its three-standard-error flags are descriptive, without a new
prospective or multiple-comparison guarantee. AC's original primary results remain
unchanged.

## Replay and evidence

The compact archive is sufficient to reproduce all 36 vectors and summary values
bit for bit using NumPy, from any working directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python /path/to/capture_value_sensitivity_20261014/replay.py
```

Use ordinary Python execution with assertions enabled. The replay checks the
saved script/plan/vector hashes, reconstructs the 36 results from 24 extracted
input vectors, and checks their exact means, standard errors and sign flags. Its
successful run from `/` is retained in `verification/`.

This compact replay does not independently reconstruct physical costs from raw
ledgers. The separately preserved [independent raw review](audit/independent_review.json)
checked all twelve 512-life, 58-column confirmation ledgers, exact role/genotype
and seed identities, ordinary costs, guard/extinction terms and every repriced
contrast. All 36 raw-derived linear vectors matched bit for bit. Directly
repricing each complete score first differed by at most 7.11e−15 due to arithmetic
order. The pinned source review found capture value affects recorded income and
final scoring, not organism observations or physical dynamics; score and overall
hash bytes need not remain unchanged under a repriced execution.

[provenance.json](provenance.json) maps all original working paths to 23 immutable
AC public references at commit
`8076858474069021f1328a373c121dcde5c24239`, each with its SHA-256 and byte count.
Raw AC files are referenced rather than duplicated here. The 24 compact input
vectors were additionally verified bit for bit against AC's published vectors.

`analyze.py` and `package_inputs.py` are preserved exactly as run; they document
the original write-once analysis/extraction and its working-tree paths.
`audit/review.py` is the exact successful raw-review script, whose working paths
are mapped by the provenance record. The audit retains its execution receipt,
stdout, empty stderr and two earlier draft-helper errors: a mistaken field name
and a relative-path mismatch. Those helper corrections did not alter the analysis
or its results.

[manifest.json](manifest.json) records every archived artifact's SHA-256 and size,
excluding the manifest itself. Original working and audit artifacts were copied
byte for byte.
