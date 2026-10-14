# Hidden and lateral messages in fixed continuation tissues

Three fixed genotypes share 512 fresh seeds across four interventions. Both final D descendants are
retained regardless of sign. Tissue is frozen at 768; common accounting covers 800..1536.

| Fixed endpoint | Added hidden dependence, ΔF ± SE | Descriptive 3-SE flag |
|---|---:|---|
| d_s51089_final_rank0 | -0.193358 ± 0.190377 | unresolved |
| d_s51090_final_rank0 | +0.793516 ± 0.207213 | positive |

The primary difference is `(endpoint−row38)freeze − (endpoint−row38)freeze+hidden_off`.
Subtraction happens within each life before uncertainty is calculated over 512 paired seeds.

| Contrast | ΔF ± SE |
|---|---:|
| d s51089 final rank0: gain: normal | +0.971579 ± 0.175790 |
| d s51089 final rank0: gain: freeze | +0.814473 ± 0.179847 |
| d s51089 final rank0: gain: freeze+lateral off | -2.027394 ± 0.079524 |
| d s51089 final rank0: gain: freeze+hidden off | +1.007831 ± 0.180616 |
| d s51089 final rank0: added hidden dependence | -0.193358 ± 0.190377 |
| d s51089 final rank0: added lateral dependence | +2.841867 ± 0.193945 |
| d s51089 final rank0: gain lost under freeze | +0.157105 ± 0.212690 |
| d s51090 final rank0: gain: normal | +1.341160 ± 0.173453 |
| d s51090 final rank0: gain: freeze | +0.426818 ± 0.190340 |
| d s51090 final rank0: gain: freeze+lateral off | -2.043098 ± 0.087184 |
| d s51090 final rank0: gain: freeze+hidden off | -0.366698 ± 0.208972 |
| d s51090 final rank0: added hidden dependence | +0.793516 ± 0.207213 |
| d s51090 final rank0: added lateral dependence | +2.469915 ± 0.202396 |
| d s51090 final rank0: gain lost under freeze | +0.914342 ± 0.213749 |
| founder row38: frozen hidden loss | +0.162000 ± 0.109050 |
| founder row38: frozen lateral loss | +7.413457 ± 0.151620 |
| d s51089 final rank0: frozen hidden loss | -0.031358 ± 0.147218 |
| d s51089 final rank0: frozen lateral loss | +10.255324 ± 0.151631 |
| d s51090 final rank0: frozen hidden loss | +0.955516 ± 0.172397 |
| d s51090 final rank0: frozen lateral loss | +9.883372 ± 0.160427 |

All 6,144 research genome-lives completed within 2674.948141 worker CPU-seconds (cap 3,600).
The worker also ran two existing T200 numerical-identity golden lives, counted separately from
research.
Complete guard-free frozen triplets: [512, 512, 512], in row38 / D51089 / D51090 order.
Guard/extinct exclusions apply only to structural validation; every valid fitness row is retained.

`measurement/` preserves all twelve full raw row checkpoints, aggregates, paired vectors and reports.
`inputs/`, `sources/` and `operations/` preserve exact genomes, protocols, source and resource
receipts.
`prelaunch/` retains the complete original preparation archive without altering its pinned bytes.

Recompute without simulation or compilation (Python + NumPy; Matplotlib only for `--plot`):

```bash
python analyze.py --study . --check
```

Interpretation limits:

- These are conditional spike-message effects in two fixed evolved descendants, not proof of a new algorithm.
- Hidden-off prevents new sends from z>=2; incoming and already emitted spikes, firing and chemistry continue. The suppressed messages retain their ordinary charge and can affect other cells indirectly.
- The three genotypes may have different frozen bodies and internal states; footprints are not matched.
- Freeze also stops gene-regulatory and phenotype/effective-weight updates. Normal-minus-freeze does not isolate development, and no adult-maturity claim follows.
- The settling interval removes bounded pending structural deliveries, not prior membrane, chemical or world history.
- Structural checks compare terminal population counts and cell-time, not equality of complete internal states.
- Both descendants and both signs are retained. Three-SE flags are descriptive; unresolved effects are not zero.
- Life-level SE describes these fixed genotypes on 512 shared seeds, not uncertainty across evolution replicates.
- Guards and extinction retain production penalties. Only complete guard-free triplets enter structural checks.
- Fitness, captures and additive costs use 800..1536; path, last birth and terminal counts describe whole lives.
