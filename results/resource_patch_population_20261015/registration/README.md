# Whole-population resource-patch development diagnostic

**Prospective: zero scientific or startup lives executed.** Planned total: 15,524 calls
(15,520 research + four retained startup checks). Namespace inspection and source/input checks are preparation.

This panel measures all 32 ordered survivors from G8, mean4 and pareto4, plus unchanged AO rank zero.
All 97 genomes face the same 32 fresh development seeds in the five current worlds: trained patches,
POOL, persistent pursuit, longer cue gaps and the previously tested transfer combination. Worlds, prices,
genomes and previously reported endpoints stay fixed. There is no evolution or endpoint replacement.

The question is whether the saved populations contain joint candidates overlooked by noisy cached endpoint
scores, or instead show acquisition/retention tradeoffs throughout. Every row remains in the report.
The minimum normalized capture statistic and weighted production F describe the population; choosing the
best of 97 noisy rows would not constitute independent winner confirmation. This is development evidence,
not a new generalization claim or evidence of a capacity ceiling.

Package limits: 2,700 CPU seconds / 1,800 wall seconds, including 60 CPU / 60 wall seconds for preparation and terminal
work. One worker uses two threads, at most 4 GiB RSS / 8 GiB address space, with 4 GiB host memory reserved.
Development seeds are 52510000–52510031; block 151 is audited separately from historical block labels.

`PROTOCOL.md` and `protocol.json` define the frozen study. `inputs/rows.json` and `inputs/genomes.npy`
preserve exact row order/identity. Source, actual-input reviews and preparation failures/corrections are
retained; temporary synthetic fixture trees and caches are excluded. Historical namespace inventories are
referenced by public path and SHA256 rather than copied again.

Verify the archive without simulations or builds from the repository root:

```sh
.venv/bin/python results/resource_patch_population_20261015/verify_public.py
```

The verifier checks every included file, frozen sources/inputs, public provenance and committed production
dependencies. It needs the repository's earlier public archives and Git revision
`5d556443e91d558de8de27ab2e5dc7ae11a51415`.
