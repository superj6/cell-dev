# Watch the reserve-policy replication

Open [the standalone viewer](../atlas/exploratory_reserve_replication.html) to compare the fixed AE L92
starting body, ordinary-selection endpoint and exploratory-reserve endpoint from completed AI. It starts
paused and offers play/pause, restart and playback speed. The three aggregate contrasts stay above the animation.

Across 512 fresh paired lives, reserve loses **0.513672 ± 0.119015 captures** to ordinary selection, reversing
AH's advantage. Ordinary selection gains **0.695313 ± 0.127998 captures** over its start, although most fitness
gain remains economy. These are fixed-genome comparisons, not 512 independent evolutionary searches or evidence
of a new algorithm. See the [complete study](../exploratory_reserve_replication_20261014/TERMINAL_README.md).

The illustration uses seed **52,360,000**, chosen in advance as the first confirmation seed. It shows
**9 / 8 / 5 captures** for start / ordinary / reserve, so the ordinary endpoint loses to its start on this
particular life despite its positive aggregate gain. The seed was retained without searching for a prettier
example. Equal initial seeds do not imply identical later target paths: placement depends on each body's
position and captures. Each panel displays its own simulation time.

The exact published float32 genotypes and existing ABI3 world are exported through the existing packer.
The embedded `lifesim.js`, cell rules, prices and world remain unchanged. Three bounded Node replays match
all **171 physical ledger values** bitwise against the retained C lives, with zero statuses, using
**5.198112 child CPU-seconds**. These are engineering replays of existing observations, not new research lives.
Mock UI checks cover 84 assertions at two widths, including pause, restart, completion and hidden-tab behavior.

A separate guarded Firefox diagnostic captures one desktop screenshot after exactly three initializations,
all at time zero, with no `advance` or `run` calls. All three aggregate rows and panels render correctly.
The browser did not exit by the cleanup threshold and was terminated after **43.048262 wall seconds**,
using **2.608106 child CPU-seconds**; its recorded process group was cleared. The attempt remains labeled
`incomplete_no_retry`. It does not validate playback, long-run Firefox arithmetic or other browsers.
No completed simulation life occurred in this diagnostic. Its profile and cache stay in the working output
directory; the public archive keeps the diagnostic source, screenshot and execution evidence.

`VIEWER_STATUS.json` describes the earlier build before that browser attempt. The original source-only
README and pre-browser HTML are retained as history. The publication candidate changes only the validation
footer to describe the later diagnostic accurately. `manifest.json` binds every archived file and the standalone
HTML. The existing math-port LGPL notice/link is preserved; this does not choose a license for the project.

The as-run export, validation and build helpers keep their original one-time safeguards and paths. To repeat
the mock UI check without simulation from the repository root:

```sh
node results/ai_watchable_20261014/test_viewer.js
```

Root export authorization initially rejected an incorrect expected review-status string before writing any
output or running a life; the corrected authorization and error record are retained. Process IDs in the Node
and Firefox receipts belong to their recorded tool PID namespaces and must not be used as host process IDs.
