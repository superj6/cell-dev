# Completed X2 archive

X2 completed 13,312 research lives and 82 validation lives using 1,348.464197 CPU-seconds, including compilation and teardown. Including the earlier X initialization failure, the total is 1,349.180745 CPU-seconds. All owned processes have exited.

The released analyzer incorrectly counted starting cells as births and rejected the completed data. Its original code and failure record remain unchanged. The separately reviewed correction in [postanalysis/ERRATUM.md](postanalysis/ERRATUM.md) fixes the initial-cell census and removes two unsupported comparisons between disjoint counters. It changes no data, physics, scoring, or scientific criteria. It uses existing records and runs no new lives.

The corrected [summary](postanalysis/working_results/summary.json) and [paired vectors](postanalysis/working_results/paired_vectors.npz) reproduce from this archive using `python postanalysis/analyze.py --study . --out NEW_OUTPUT_DIRECTORY`. These are measurements of fixed external controllers; they do not establish evolved behavior or a specific memory mechanism.

[prelaunch/manifest.json](prelaunch/manifest.json) preserves the published preparation. The original README, PREREG, analyzer and every released source pin remain byte-identical. [manifest.json](manifest.json) covers the appended complete raw rows, validation, generated C sources, four libraries, operational records, and the separate corrected audit.
