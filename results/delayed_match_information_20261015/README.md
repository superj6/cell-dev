# Delayed matching: remembering the cue pays

The completed external measurement isolates a useful contribution from earlier-cue memory in the exact
short T85 task. Remembering the sample adds **2.945493 ±0.143336 F** over erasing it (512 paired lives).
The instrument makes 479 correct choices, one wrong choice and leaves 32 unfinished; its memory-erased version
makes 246 correct and 236 wrong choices, leaving 30 unfinished. These are measuring instruments, not evolved cells.

All registered section 0.4 information, memory and do-less criteria pass. The reference reflex family makes
zero completed choices, so that comparison is limited to the declared finite family. Fixed narrow and broad
preferences also score about 3 F below the remembering instrument. This admits this exact T85 selection world;
it does not establish an evolutionary gradient, local neural memory, or repeated T1024 admission.

All 6,656 scientific calls plus 40 engineering calls complete. Scientific execution uses 573.692021 CPU seconds;
including 50.93 seconds allocated to prior engineering/preparation gives 624.622021 seconds, below the 3,600 cap.
Peak owned memory is 329.61 MiB, with all owned workers cleared. Independent raw arithmetic and paired replay
checks pass. Later saved-data auditing and packaging are metered separately; they add no simulations.

Read the [report](REPORT.md), [independent recount](terminal_audit/REPORT.md),
[protocol](prelaunch/PROTOCOL.md), [instrument specification](prelaunch/instrument_spec.md),
[engineering evidence](ENGINEERING_EVIDENCE.md), and [policy review](source_review.md).
The original prospective archive documents remain in `registration_history/`.

All scientific raw NPZ bytes are preserved in `raw.tar.gz`, with exact `prelaunch/raw/...` member paths.
Engineering binaries and caches are omitted; sources, build receipts and engineering raw files are retained.
Historical namespace inventories remain at the public paths in `namespace_references.json`.

Verify without a simulator:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/delayed_match_information_20261015/verify.py
```

Replay the frozen analysis into a new output directory without generating new lives:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python results/delayed_match_information_20261015/replay.py \
  --out outputs/delayed_match_information_replay
```

Continuing local evolution remains covered by the user's standing autonomy instruction.
