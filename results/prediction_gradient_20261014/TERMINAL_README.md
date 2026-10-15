# AE completed: persistent-target mutation screen

AE evaluated all 130 unchanged Y panel rows in the exact V persistent-target world, then confirmed the selected mutant from each background against its own parent on 512 fresh paired lives. Selection retained D90 row 54 and L92 row 31. All 6,208 research lives and ten startup/calibration lives completed in **1,226.079103 aggregate CPU-seconds**, including compilation, startup and cleanup. All 6,216 raw lives had status zero; the two recorded ABI3 numerical goldens also matched.

Both selected mutants improved production fitness:

| Winner minus parent | Fitness | Captures | Capture income, in fitness units | Ordinary cost savings, in fitness units |
| --- | ---: | ---: | ---: | ---: |
| D90 row 54 | +1.73327 ± 0.07687 | −0.32813 ± 0.14990 | −0.16022 ± 0.07319 | +1.89349 ± 0.01880 |
| L92 row 31 | +0.72874 ± 0.05238 | +0.41797 ± 0.10489 | +0.20409 ± 0.05122 | +0.52466 ± 0.01074 |

Values are paired means ± one standard error over 512 lives. D90's fitness gain comes from lower costs; its capture change does not clear the registered three-SE diagnostic. L92 has a small resolved capture gain, while most of its fitness gain comes from lower costs. Guard and extinction charges contribute zero to both contrasts. These two fixed mutation neighborhoods do not establish an evolved prediction or memory algorithm, and historical Y scores are not a paired comparison of world effects.

The unchanged reader's [summary](analysis_result/summary.json) and [128 paired arrays](analysis_result/paired_vectors.npz) are preserved alongside all 138 raw calibration, screen and confirmation rows. The independent raw recount and separate frozen-reader invocation match the summary and arrays exactly. Recorded-operation replay verifies all 130 retained panel rows and 256 recorded point mutations without new genetic draws. The [figure](figures/capture_and_economy.png) separates capture income from physical costs.

The public [prelaunch manifest](prelaunch/manifest.json) preserves all 324 prepared artifacts. All 235 released local pins and 35 production pins remain unchanged. The terminal [manifest](manifest.json) also covers startup library bytes, phase acknowledgments, complete raw measurements, resource/process receipts, independent reviews, final figures, and explicitly unreleased future-direction notes. The frozen prospective ARCHIVE.md and historical source/test records remain intact. Full historical namespace provenance still requires the exact committed repository artifacts described in NAMESPACE_PROVENANCE.md.

Portable offline reanalysis: `python analysis/analyze.py --study . --out NEW_DIRECTORY`. Packaging and reanalysis execute no new lives or kernel builds.
