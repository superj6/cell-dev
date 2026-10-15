# Watch the persistent-target comparison

Open [the standalone viewer](../atlas/persistent_target.html) in a browser. It compares the original and
selected D90/L92 genomes from completed AE in its exact existing ABI3 world. Both start paused; Play/Pause,
Restart, lineage and playback-speed controls affect viewing only. Switching away from the tab pauses it.
Targets are not draggable, and the page exposes no world or organism-rule controls.

The single displayed seed is 52,300,000, the first of AE's 512 confirmation seeds, chosen by position rather
than outcome. L92's mutant catches two targets versus its parent's three on this particular life, although its
512-life capture advantage is +.41797 ± .10489. D90 catches four versus three on this seed despite its unresolved
negative average capture change. The page retains these examples and displays the aggregate means ± paired
SE. Illustrations do not establish typical performance or a prediction mechanism.

`bodies.json` exports all four unchanged published float32 genomes through the existing ABI3 packing function.
The world and shared tables are pinned; the page embeds the maintained `lifesim.js` unchanged. No C or Python
life, new research life, new genotype, price change, world change or kernel build was introduced.

Four JS replays used this already-published seed and compared all 57 physical ledger columns bitwise against
AE's retained C records: 228 exact matches, all statuses zero. A single Node process used 10.375161 CPU-seconds
and exited, under a 120-second child CPU ceiling. This is engineering replay, not four additional independent
observations. `validation_budget.json` and `replay_stdout.json` preserve the evidence. The first export helper
used a wrong archive subdirectory; it stopped before any outputs or simulations. Its source and error are retained.

`test_viewer.js` uses a small DOM/canvas and simulator mock to check 60 control/render assertions at two widths:
paused startup, fixed roles/world/seed, play/pause, hidden-tab pause, lineage changes, completion, restart,
responsive canvas dimensions and finite drawing coordinates. It runs no engine lives. No real browser binary
was available in this environment, so a rendered browser screenshot was not captured.

Rebuild from the repository root without simulation:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/ae_watchable_20261014/build.py
node results/ae_watchable_20261014/test_viewer.js
```

`check_replay.js` can repeat the four engineering lives with the retained truth; it does not overwrite fixtures.
The as-run export/validation helpers retain their one-time output safeguards. All files are listed by hash in
`manifest.json`; the standalone HTML is also pinned as an external artifact. The simulator's existing LGPL
notice and license link are preserved in the page.
