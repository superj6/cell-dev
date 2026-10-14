# Watch the s7 continuation endpoints

[Open the standalone viewer](../watch.html). It starts paused, showing row 29 beside the final rank-zero genome
from search 51891. Either side can show original s7, row 29, or either fixed continuation endpoint. POOL is the
training and confirmation world. Base is labeled a transfer illustration.

The fixed descriptive seed is **51,840,000**, reused from the earlier viewers without choosing a favorable life.
The user can change it. Playback speed changes display timing, not cell rules. Each displayed life lasts 1024
units; the evidence panel reports separate confirmation across all three registered durations. Swapping the
selected genomes reverses the measured contrast while retaining its paired standard error.

The HTML embeds all genomes and the unchanged `lifesim.js` engine, so it works offline. The adjacent engine
source and `COPYING.LGPL-2.1` retain its GNU C Library math code notice and license. No organism rule changed.

Viewer provenance is separate from the scientific archive's `../provenance.json`; all 207 sealed scientific
artifacts remain unchanged. The viewer's `provenance.json` binds genomes, engine, worlds, template and HTML.

## Validation

`ui_validation.json` records synthetic DOM/canvas checks of pause/play, restart, seed entry, both genome selectors,
swapped comparisons, same-genome comparisons, world switching, speed, background pause and replay. The actual
engine is syntax-checked and its bytes hashed; these controls run no simulator lives. A browser rendering check
has not been performed.

All eight T32 cases passed: each C life matches stepped execution and state reads in the embedded JS engine
bitwise across all 57 ledger columns and five hashes. The one-worker validation used 11.250013 of 15 CPU-seconds.
These eight C lives and eight JS replays provide no new research evidence or full-life parity claim.
`validation.json` and `parity_budget.json` preserve the result; `parity_plan.json` preserves the original plan.

From the repository root, preparation and synthetic checks are:

```sh
.venv/bin/python outputs/autonomous_s7_20261014/viewer/build_watch.py
.venv/bin/python outputs/autonomous_s7_20261014/viewer/validate_watch.py
```

Only after the root scheduler releases a worker:

```sh
.venv/bin/python outputs/autonomous_s7_20261014/viewer/validate_watch.py --simulate --released-worker
.venv/bin/python outputs/autonomous_s7_20261014/viewer/build_watch.py --publish
```

An existing parity budget prevents accidental repetition. Incomplete validation must be reported rather than
silently rerun with a fresh budget. The viewer's hashes and controls can be checked without simulation.
