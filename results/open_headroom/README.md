# Open headroom study (2026-10-10)

The record behind `docs/TASK_VARIATION_PLAN.md` section 0. Worlds are judged by what the sense information pays, using
central controllers that are measurement tools only. Whether we can hand-build a body that wins is no longer the test.

- `harness/`: the controller harness, with its own README.
  - `make_ckernel.py` builds a scratch copy of `src/life/kernel.c` with the prototype world keys (blink, flash, motor
    flip) and a central controller mode.
  - `ctl_*.c` and `harness.py` hold the controllers C0-C4 and the Python API.
  - `tests/test_harness.py` checks stream equality with inert bodies, bitwise replay of tissue spikes, determinism and
    the latency rule.
  - Paths assume the harness lives in `outputs/openhr/harness/`.
- `controllers/`: the study-specific controllers and scoring scripts.
  - `mem_ctl.c` (C5 memory tracker) and `t8_score.py` for memory.
  - `sw_ctl.c` and `cu_ctl.c` (flip detector) and `score2.py` for switching.
  - `make_vctl.py` (C4 with ablation switches) and `test_replay_leak.py` (the ping-replay leakage test) for the headline.
- `data/`: results.
  - `headline.json`: 1,024 lives, base and POOL.
  - `memory.json`, `switching.json`.
  - `harness_first_look.json`.
  - `open_ended_literature.json` and `open_ended_design.json`: the verified literature survey and the options mapped onto
    cell-dev (co-evolving prey, a world archive, competition).
- `recover_replay.py`: how the harness was rebuilt from its agent's transcript after a reboot wiped `/tmp`.

Seeds: `fresh_seeds(n, 43,000,000 + 10,000·block)`, with these block ranges:
- harness: 0-9;
- memory: 100-119;
- switching: 140-159;
- headline: 400-419.
