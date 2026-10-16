# Depth-study paused preview preparation

This directory contains source only. After the depth study completes, these helpers can create a standalone
paused viewer for `AO`, `G8_joint`, `Pareto4_joint` and `depth8_joint` in the trained three-patch world at T1024.
All four cases use the predetermined first confirmation seed **52530000**. No behavior or aggregate result
has been inspected to select the example. The earlier published reporting genomes remain unchanged.

The page reuses the existing resource-patch viewer and ABI6 engine. A fixed selector switches among the four
genomes; Play and Replay retain the same seed. It exposes no patch or seed controls. Stock, source and harvest
labels are observer information; cells receive only the existing local scalar receptor pings. Native displayed
F excludes the production scorer's extinction surcharge. A single example cannot establish generalization,
a reusable strategy, memory or aggregate improvement.

The exact validation inventory is **four stepped JS lives** and **zero new C/Python lives, builds or genetic
random draws**. The unchanged simulator uses the saved case seed internally. Preparation retains the original
fast-C `raw/patch.npz` cohort and pins its source, world and raw/packed genomes. Native flattened rows
0, 512, 1024 and 1536 are the first of each genotype's 512 confirmation seeds. Each JS replay must match all
107 native ledger float bits (428 values total); returned ledgers are saved before validation. Fast-C hashes
are constants, so no full-C trajectory-hash or raster comparison is claimed. Two supplied-state UI mounts
and four supplied page-dispatch checks use no simulated lives. No real-browser test is planned.

The separate package budget is **15 CPU / 60 wall seconds**, including a conservative **3 CPU / 5 wall**
preparation, static-check and saved-verification reserve. The unchanged owned-worker monitor allows at most
12 CPU / 55 wall seconds for replay and assembly, with one worker, one numerical thread, one CPU affinity,
1 GiB owned RSS, 2 GiB worker address space, and a 4 GiB host memory floor. Node retains the previously used
`--single-threaded --max-old-space-size=256` flags. Every attempt and failure is retained; there is no automatic
retry or cap expansion. No runtime receipt or HTML exists before execution.

After terminal completion and source review, run the following once from the repository root. These commands
record preparation, the owned replay/assembly process, and saved-byte verification separately. The engine
runs only in the middle command. Source checks and all outside-runtime work must fit the reserved budget.

```sh
P=outputs/resource_patch_depth_preview_20261015
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
/usr/bin/time -v -o "$P/preparation_resources.txt" \
  timeout 10s .venv/bin/python "$P/prepare.py" --run \
  >"$P/preparation_stdout.txt" 2>"$P/preparation_stderr.txt"
/usr/bin/time -v -o "$P/execution_resources.txt" \
  timeout 60s .venv/bin/python "$P/run.py" --run \
  >"$P/execution_stdout.json" 2>"$P/execution_stderr.txt"
/usr/bin/time -v -o "$P/verification_resources.txt" \
  timeout 10s .venv/bin/python "$P/verify.py" \
  >"$P/verification.json" 2>"$P/verification_stderr.txt"
```

On success, open `resource_patch_depth.html`. `execution_record.json` binds the terminal scientific evidence,
fixed input cohort and sources; `validation.json`, `replay_result.json` and `execution/budget.json` retain
comparison and ownership evidence. `verify.py` reads saved bytes only. Publication is separate; these helpers
do not write to the public results directory or modify the scientific study.
