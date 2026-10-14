# ABI 4 visibility port: engineering evidence

The approved flash and irregular renewal-blink worlds now run in C, the Python reference and the maintained
browser simulator. Four world fields and one low-light capture column are appended. Genome structure, cell
inputs, messages and local asynchronous organism rules are unchanged. No new research selection run is included.

The exact contract and caller examples are in [LIFE_ABI.md](../../docs/LIFE_ABI.md).
Use explicit `spec.V4` or `life.abi: 4`; legacy defaults remain unchanged. The two presets inherit
`catch_speck_l4` prices and old conduction. Strict checkpoint/source checks remain in place.

| Check | Coverage and result |
| --- | --- |
| Pre-port compatibility | 32 recorded ABI 2/3 lives reproduce every ledger/hash/raster/fate byte in full and fast modes. Permanent fixtures are in `tests/data/abi4_legacy/`. |
| C/Python/browser agreement | 16 T96 cases, unchanged atlas bodies 0/7, both presets, neutral ABI 3/4, time offsets, accounting windows, multiplier 1 and end boundary. All ledger bytes, five full-mode hashes and retained spike logs agree. C/Python also compare full fate arrays. Six cases include low-light captures. |
| Boundaries | Focused C, Python and JS tests cover initial state, expiry/ties, placement resets, renewal continuity, validation, background sensing and capture accounting. |
| Determinism | Both new worlds match across one/two threads and heap/window scheduling; full/fast physical outputs agree. Browser capped stepping preserves full hashes. |
| Checkpoint/resume | Six tests pass: uninterrupted six generations matches three plus resume plus three in BELL, CATCH, flash and blink; strict pin/log integrity tests pass too. |
| Prototype bridge | Twelve T64 cases (24 backend lives) match all 55 unchanged physical columns, complete spike/fate logs and local hash families. Scratch dark captures map exactly to ABI 4 column 57, including positive flash/blink fixtures. |
| Measurement tools | Explicit ABI 4 ledger validation, tracing and lesion support; low-light click observations reconcile with the accounting window. |

The default regression suite covered 861 distinct tests including the six checkpoint tests. Its initial isolated
run passed 850 of 855 non-checkpoint tests; the five issues were an absent environment symlink, historical logs
missing from Git, and line-length style. Targeted reruns pass all 23 affected/related checks. The missing historical
logs were published unchanged in commit `859ddc8`. The 127 slow tests were excluded. Separate browser checks pass
33 old wound cases, eight standard cases, 18 interactive checks, 12 visibility boundaries, 16 truth cases and five
export tests. Ruff and whitespace checks pass for changed code.

`final_truth/truth.json` and `final_js.txt` are the final C/Python/browser evidence. `initial_validation/` preserves
earlier exact receipts, including scheduler and resume tests. `finalization.json` verifies that the only source
changes after resume validation were two docstring line wraps, and records the regression fixes. Earlier fixture
source hashes remain as recorded; they are not rewritten to claim later versions. `scratch_bridge/` preserves the
original prototype bridge; its portable replay uses the retained ABI 3 base rather than importing the new kernel
into an old unchecked harness. New visibility records deliberately change scratch-versus-production world/all hashes.

Verify archive and source bytes without simulation:

```sh
.venv/bin/python results/abi4_visibility_20261014/verify.py
```

Replay browser truth without regenerating it:

```sh
node results/atlas/play/test_visibility.js --truth results/abi4_visibility_20261014/final_truth/truth.json
```

For a fresh bounded C/Python export, choose a new directory under `outputs/` and run
`PYTHONPATH=. .venv/bin/python results/atlas/play/export_visibility.py --out outputs/<new-validation>/`.
Do not overwrite historical fixtures or weaken old checkpoint pins. Historical controller harnesses require their
pinned ABI 3 source environment and verified raw buffer sizes; the new kernel is ABI 4.

These results establish implementation agreement and compatibility. They do not establish memory, prediction,
information payoff in a new treatment, or any new evolved algorithm. Fresh information measurements and bounded
evolution remain separate studies; the large selection matrix, motor flip and rented compute remain outside scope.
