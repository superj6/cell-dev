# Y terminal archive

Y completed 6,208 research lives and 10 validation lives using 1768.464936 CPU-seconds, including startup, compilation and cleanup. The eight calibration lives and two ABI3 compatibility goldens are included.

The [full summary](analysis_result/summary.json) and [paired vectors](analysis_result/paired_vectors.npz) reproduce with `python postanalysis/analyze.py --study . --out NEW_DIRECTORY`. Each selected mutant is compared with its own evolved founder on 512 fresh paired seeds, after a separate 32-life screen.

The original frozen analyzer rejected the actual process receipt before producing outcomes: it required a session ID that the monitor never recorded. Its code and failure record remain intact. The separately reviewed reader in [postanalysis/](postanalysis/) checks the four recorded identity fields and retains parent/group, source, phase, resource and scientific checks. It makes no claim of archived session-ID evidence and changes no simulation or scientific criterion.

All owned processes have exited. [prelaunch/manifest.json](prelaunch/manifest.json) preserves the published preparation. Every prepared artifact and released source pin remains unchanged. [manifest.json](manifest.json) covers the appended raw rows, binaries, phase handoffs, resource records, final analysis and reviews.

This is a local mutation-gradient diagnostic in the approved irregular-blink world. Fitness and dark-capture effects do not by themselves identify memory, prediction or a new algorithm. Archiving and offline analysis run no new lives.
