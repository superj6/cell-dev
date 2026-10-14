# Watch the continuation endpoints

[Open the standalone viewer](../watch.html). It starts paused, showing row38 beside the final rank-zero genome
from search 51089. Either side can show original s5, row38, or either fixed continuation endpoint. POOL is the
training and confirmation world. Base is clearly labeled a transfer illustration.

The fixed descriptive seed is **51,840,000**, reused from the earlier viewer without choosing a favorable life.
The user can change it. Playback speed changes display timing, not cell rules. Every displayed life lasts 1024
units; the evidence panel reports the separate confirmation across all three registered durations. Swapping the
selected genomes reverses the measured contrast while retaining its paired standard error.

The HTML embeds all genomes and the unchanged `lifesim.js` engine, so it works offline. The adjacent engine
source and `COPYING.LGPL-2.1` retain its GNU C Library math code notice and license. No organism rule changed.

Viewer provenance is separate from the scientific archive's `../provenance.json`; that existing file is unchanged.
`provenance.json` binds the genome files and raw genome bytes, engine, world settings, template and generated HTML.

## Validation

`ui_validation.json` records synthetic DOM/canvas checks of pause/play, restart, seed entry, both genome selectors,
swapped comparisons, same-genome comparisons, world switching, speed, background pause and replay. The actual
engine is syntax-checked and its bytes hashed; these control checks run no simulator lives. A browser rendering
check has not been performed.

The released parity check passed all eight T32 cases: four genomes in both worlds on the fixed descriptive seed.
Each C life matched stepped execution and state reads in the embedded JS engine byte for byte across all 57 ledger
columns and five hashes. The sequential one-worker check used 9.331079 CPU-seconds within its 15-second cap;
`validation.json` and `parity_budget.json` retain the evidence. These 8 C lives and 8 JS replays are short validation,
not full-life parity or new research evidence. The original prospective plan remains in `parity_plan.json`.

From the repository root, preparation and synthetic checks are:

```sh
.venv/bin/python outputs/autonomous_continuation_20261013/viewer/build_watch.py
.venv/bin/python outputs/autonomous_continuation_20261013/viewer/validate_watch.py
```

Only after the root scheduler releases a worker:

```sh
.venv/bin/python outputs/autonomous_continuation_20261013/viewer/validate_watch.py --simulate --released-worker
.venv/bin/python outputs/autonomous_continuation_20261013/viewer/build_watch.py --publish
```

An existing parity budget prevents accidental repetition. Incomplete validation must be reported rather than
silently rerun with a fresh budget. The viewer's hashes and controls can be checked without simulation at any time.
