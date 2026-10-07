# Selection study (2026-10-07): which two-stage selection to run in the pilot

The study behind RESULTS.md, "Pilot preparation", part 1. It ran under kernel ABI 1, on a copy of the code at commit
f2142c8.

## What is here

- `report_all.txt`, `table_stages.txt`, `compact_table.txt`: the replay study. It replays one generation's choice of
  32 parents on measured genome × life F matrices (`scripts/sim.py`) and ranks the schemes by regret.
- `escape.json`: how each scheme treats the bodies of hex seed 0's plateau escape (generations 12-16).
- `fwd20_summary.txt`, `fwd50_summary.txt`: the forward runs. Each runs 20 or 50 generations of breeding and
  selection from a saved population, then scores the final 32 parents on 32 fresh shared lives.
- `data/` (tracked, 0.7 MB). Everything needed to audit or rerun the forward runs:
  - `data/fwd/*.json` and `data/fwd50/*.json`: one row per replicate, scheme and checkpoint, with each final
    parent's F (`per_genome`), `median_n` and `body_share` (the share of parents with a mean end size ≥ 1.5 cells).
  - `data/logs/fwd*.log`: the same rows as JSON lines. Some 50-generation runs were split, so their first part
    exists only as a log: `fwd50_A.log` holds reps 0-17 and `fwd50_B1644.log` holds reps 0-20.
  - `data/pops/esc_hex_s0_g*.npz` (hex seed 0 around its plateau escape) and `data/pops/hex_s0_g30.npz` (a
    population of small bodies). Each is a whole 256-genome population with its generation's seeds and 3-life F.
- `scripts/`: every script of the study, unchanged.
- **Not tracked** (24 MB, too big for git): the other 100 population snapshots (`pops/`), the measured matrices
  (`meas/`, 15 MB), the replay results (`simres/`) and the other logs. A copy of the whole study directory, without
  `tree/`, is kept locally in `outputs/selection_study/`. Like all of `outputs/`, it exists only on this machine.

## Reproducing

The scripts expect the study's layout: the scripts and the data in one directory, next to `tree/`, an export of
f2142c8. They read data paths relative to the working directory.

```bash
W=$(mktemp -d) && mkdir "$W/tree"
cp results/selection_study/scripts/* "$W" && cp -r results/selection_study/data/* "$W"
git archive f2142c8 | tar -x -C "$W/tree"      # the study's tree/ was exactly this export
cd "$W" && PY=/path/to/cell-dev/.venv/bin/python
$PY fwd_summary.py                             # fwd20_summary.txt from data/fwd/esc_g12*.json
$PY fwd50_summary.py                           # fwd50_summary.txt from data/logs/fwd50_*.log
```

The stored rows came from the saved `forward.py`, run with `--select_first --final_lives 32`. The default for
`--final_lives` is 64, which gives other final F but the same body shares.

| file | command (after `$PY forward.py`) |
|---|---|
| fwd/esc_g12.json | `pops/esc_hex_s0_g12.npz fwd/esc_g12.json --select_first --final_lives 32 --gens 20 --reps 0 … 15 --schemes A B2:64:4 B1:64:4` |
| fwd/esc_g12_r16.json, _r32.json | the same with `--reps 16 … 31` and `--reps 32 … 47` |
| fwd/bodies_g30.json | `pops/hex_s0_g30.npz fwd/bodies_g30.json --select_first --final_lives 32 --gens 20 --checkpoints 10 --reps 0 … 7 --schemes A B1:64:4 B2:64:4` |
| fwd50/*.json and logs/fwd50_*.log | `pops/esc_hex_s0_g12.npz … --select_first --final_lives 32 --gens 50 --checkpoints 20 35`, one scheme per file (A, B1:64:4 = the chosen key, B2:64:4 = recheck lives only) |
| logs/fwd_esc_g12_C4*.log | partial runs of scheme C:4 (4 lives for everyone), reps 0 and 24-26 |

Checked bitwise with the recipe above on 2026-10-07: esc_g12 reps 3 and 7 (schemes A and
B1:64:4, every per-genome F), esc_g12_r16 rep 16 and esc_g12_r32 rep 33 (A and B2:64:4), bodies_g30 rep 0 (A, both
checkpoints), fwd50 rep 18 (A and B2:64:4) and rep 21 (B1:64:4), all three checkpoints each, and the C:4 logs'
reps 0 and 24. The rows of fwd50_A.log and fwd50_B1644.log (reps 0-17 and 0-20) were not rerun.

The replay table needs `meas/` and `simres/` from `outputs/selection_study/`. Copy them into the working directory,
then run `$PY compact_table.py` (or `report.py`, `table.py`). To regenerate them: `grow.py` for the population
snapshots (job lists `grow_jobs*.txt`), `measure.py` for the matrices (`measure_all.sh`), and `run_sim.py` for the
replays.
