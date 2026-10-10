# Central-controller harness: ceilings and information-matched gaps for CATCH / SPECK worlds

Scratch measurement tool (2026-10-10). Nothing here edits the repo. It answers, per world, without anyone having
to hand-build the tissue that solves it:

1. **Ceiling**: what does a *privileged* central controller that reads the true hidden state earn?
2. **Information test**: does an *information-matched* central controller beat the best reflex? It sees only the
   receptor pings its body's sense cells receive, its own past actions and its own clock. It acts only through its
   own act-plane cells and the hotspot tap, at least one conduction hop after the pings it used. If it beats the
   best reflex, the information is in the sense stream and the world pays for using it. Whether a *local* tissue can
   do the same is what evolution must find out.

These controllers are measuring sticks, like `oracle_cap`. They are never part of an organism. The organism's
in-life rules stay local, asynchronous and self-discovered.

## Files

| file | what |
|---|---|
| `make_ckernel.py` | builds the scratch kernel `ckernel(.c/.so)` and `ckernel_fast.so`. It applies the repo `kernel.c` + the capability study's world patches (`taskvar/capabilities/make_xkernel.py`, copied verbatim; all 14 still apply once each to today's kernel) + the controller-mode patches. `--ctl my.c` compiles extra controllers into your own `--out` library |
| `ctl_api.h` | the C API a controller sees (callbacks, actions, own-action models, privileged truth, registration) |
| `ctl_core.c` | harness core: registry, per-life setup, ping / wake hooks, `ctl_fire`, `ctl_wake`, `ctl_truth`, efference model, `ctl_steer`, the exported `ctl_life_run` |
| `ctl_builtin.c` | built-in controllers: 0 null, 1 C0, 2 C1, 3 C2, 4 C3, 5 C4, 99 replay |
| `harness.py` | Python API: worlds, footprints, `ctl_run`, `ctl_batch`, `tissue_run`, reference reflexes, statistics, `es_tune` |
| `reflex_knobs.json` | re-tuned reflex@hollow3 knob sets per world (prior studies + this harness's re-tunes; `collect_reflex_knobs.py`, `retune_reflex.py`) |
| `validate.py`, `summarize.py` | the validation run (`tests/validation.json`, `tests/validation.md`, `tests/validate.log`) |
| `tests/replay.py` | replay test: a tissue body's act-plane raster replayed through the controller path |
| `examples/example_ctl.c` | template for an external controller |

Python: `/home/jgon/project/ml/cell-dev/.venv/bin/python`, cwd `/home/jgon/project/ml/cell-dev`,
`PYTHONPATH=/home/jgon/project/ml/cell-dev:<this dir>`.

## Python API

```python
import harness as H
fp  = H.footprint("hollow3")            # reflex@hollow3's shape: sense = centre + ring 3, act = disk 3 (56 cells)
                                        # "ring4" = router@ring4's (disk 4 in both planes, 122 cells); "disk{k}" = ring{k};
                                        # "disk4x4" = disk 4 in all four planes of the L4 stack (hidden planes inert, cost only)
sd  = H.seeds(256, block=2)             # fresh_seeds(n, 43_000_000 + 10_000 * block)
res = H.ctl_run(H.C4, H.bayes_params("pool"), fp, "pool", sd, threads=6)
res["F"], res["captures"], res.diag, res.latency      # a build.Lives (ledger, hashes, raster, fates) + .diag [n,16]
ref = H.tissue_run(H.reflex("hollow3"), "pool", sd, threads=6)   # tissue body on the SAME scratch kernel
H.paired(res, ref)                      # {'mean','se','z','n'} of the per-life F difference (common random numbers)
name, ref, means = H.best_reflex("pool", sd)  # better of the frozen reflex and the recorded re-tunes, on these lives
```

- **`ctl_run(cid, params, fp, world, seeds, *, extra=None, threads=4, latency="d0", privileged=None,
  charge="relay", t_ref_min=0.5, quant=False, lib=None, fast=True, raster_cap=0, fate_cap=0)`**
  - `cid`: an int, or one id per life.
  - `params`: one vector, or one row per life (batch tuning).
  - `extra`: one shared float array.
  - `latency`: `"d0"`, `"dmin"` or a number (see the latency rule).
  - `privileged`: defaults to the controller's registered flag.
  - `charge`: what each delivered ping costs.
    - `"relay"` (default): `c_rec` + one relay spike (`c_spike + c_msg`), the cheapest tissue that carries every
      ping up one hop.
    - `"receptor"`: `c_rec` only.
    - `"none"`.
  - `t_ref_min`: the minimum interval between strokes of one act cell (0.5, the GRN grid's smallest `t_ref`).
  - `quant`: rounds `kappa` up to the GRN grid {0.25, 0.5, 1}.
  - `fast=False` uses the full build, which keeps hashes.
  - Returns `CtlLives` (a `build.Lives`, so `analysis` helpers and `res["F"]` work).
    - `.diag[:, 0..4]`: pings delivered, wakes, strokes commanded, clicks commanded (key model), refused calls.
    - `.diag[:, 5..15]`: written by the controller.
- **`ctl_batch(cid, cand, fp, world, seeds, **kw)`** → F matrix `[n_cand, n_seeds]`. Every candidate runs on the same
  lives, in one call.
- **`es_tune(cid, x0, fp, world, tune_seeds, iters, popsize, lives_per_gen, mask, lo, hi, ...)`**: separable CMA-ES
  (diagonal covariance) with common random numbers within a generation. It returns `x`, `F` (re-measured on all
  `tune_seeds`) and the history. Default bounds come from the controller's `CtlSpec`.
- **`tissue_run(org, world, seeds, ...)`**: `hb.Body` or `hb.GrnBody` on the scratch kernel. With every scratch slot
  at 0 it is bitwise the repo kernel, apart from two outputs.
  - Ledger columns 21/22 are repurposed: 21 counts captures made while the target is dark; 22 counts captures at
    `t >= t_mark` (`t_flip`, else `kill_t`, else T/2).
  - The `all` hash differs because it folds the ledger.
- **Worlds**: `H.WORLDS` names or `H.WorldSpec(name, preset, over={repo keys}, x={scratch slots},
  draws={slot: (lo, hi)})`.
  - Scratch slots: `blink_on`, `blink_off` (< 0 = FLASH), `t_flip`, `e_on`, `e_off`, `dark_amp`, `dim_flag`.
  - Per-life draws come from the life seed, so every body gets the same `t_flip` in the same life.

  | name | settings |
  |---|---|
  | `base1` | today's SPECK `catch_speck_l4`: d0 1, d_min 0.5 |
  | `base` | d0 0.5, d_min 0.25 |
  | `pool` | sigma 0.4, lam_s 4, d0 0.5, d_min 0.25 |
  | `blink20` / `blink20f` | blink on 20 / off 20 |
  | `flash6` | visible for 6 after each placement |
  | `flip_mid` / `flip_midf` | t_flip ~ U[256, 768] per life |
  | `lead` / `leadf` | v_t 0.3, tau_turn 200 |
  | `decoy_lite`, `decoy_wide`, `same_peak`, `food_twin` | b2 blobs |
  | `wound25`, `wound50` | kill_t 512, kill_frac 0.25 / 0.5 |

  The `...f` variants use d0 0.5 / d_min 0.25. `blink20`, `flip_mid` and `lead` use today's d0, like the prior
  study. Use `H.WORLDS["blink20"].with_("x", d0=0.5, ...)` for combinations.
- **References**: `H.reflex(shape, knobs=None)` and `H.router(shape, knobs=None)` give the frozen SPECK bodies, or
  role bodies with re-tuned knobs. `H.retuned_reflex_knobs()` reads the recorded re-tunes. `H.best_reflex` follows
  the plan's rule: the better of the frozen and re-tuned reflex, *on the lives being scored*.
- **Parameters**:
  - `H.params(cid, name=value, ...)`.
  - `H.bayes_params(world, **kw)` (C4: fills in the world rules).
  - `H.rnn_params(fp, n_h, ...)` / `H.rnn_size` (C3).
- **Other controllers**: `H.registered(lib)` lists the ids compiled into a library. `H.register(H.CtlSpec(...))`
  gives your id names, defaults, bounds and a privileged flag on the Python side. This is optional; without it, pass
  `privileged=` explicitly.

## What controller mode changes in the kernel (and what it does not)

`ctl_life_run` is `life_run` with a controller per life. The footprint is placed at t0 as inert program cells (no
GRN, b 0, g_r 0, never fire on their own) in `hb.role_cells` order, so their uids equal a hand-built body's. Every
world process is the kernel's own code, unchanged:

- dot and drag;
- target and blob processes;
- receptor candidates and thinning;
- strokes and their surface-normal pull, including the flipped law after `t_flip`;
- the key's hysteresis, clicks and captures;
- wounds;
- the accountant, ledger and prices.

Patches, active only inside `ctl_life_run`:
- Cells schedule no TICK and no NOISE events. Living cost is charged by the kernel's own closing R_TICK, or the one
  at a KILL, from `t_birth`. So `live_time` equals a ticking body's up to summation order (relative difference about
  1e-14).
- Every RECEPTOR delivered to a live footprint sense cell (and not `receptor_off`) calls the controller's `ping` at
  the delivery time.
- Two new EXO events:
  - `X_FORCE` is a commanded stroke. It runs the kernel's `fire()` with the commanded kappa, n_out 0, so it is charged
    `c_spike + c_tw*kappa`. It is dropped if the cell has died.
  - `X_WAKE` is a controller wake-up.
- `life_run` (tissue bodies) is untouched by these patches.

## The controller hook (C)

```c
#include "ctl_api.h"
typedef struct { ... } MySt;
static int  my_init(Ctl *k)                 { k->st = calloc(1, sizeof(MySt)); ctl_wake(k, k->t0); return 0; }
static void my_ping(Ctl *k, double t, int s) { /* sense cell s got a ping at t */ }
static void my_wake(Ctl *k, double t)        { /* ... */ ctl_fire(k, a, kappa, t); ctl_wake(k, t + 0.25); }
static void my_fini(Ctl *k)                  { free(k->st); }
static const CtlDef MY = {1001, "my controller", my_init, my_ping, my_wake, my_fini};
CTL_REGISTER(MY)
```

What a controller sees in `Ctl *k`:
- **Footprint**: `n_sense`, `n_act`, `hot` (act index of the hotspot (0,0,1)) and `centre` (sense index of
  (0,0,0)). Also `sense_ab/act_ab`, the planar `sense_xy/act_xy`, `act_face` (each act cell's exposed face at t0) and
  `n_fill`.
- **Body physics constants**: `tau_z`, `g_n`, `gam`, `th_click`, `th_rel`, `d_min`, `d0`, `latency`, `t_ref_min`,
  `t0`, `T`.
- **Parameters**: `p[np]`, `extra[n_extra]`; also `priv` and `quant`.
- **Controller-owned**: `st` (your state) and `diag[5..15]` (your outputs).

Actions (the only way to affect the world):
- `ctl_fire(k, a, kappa, t)` schedules a stroke of act cell `a` at **max(t, now + latency, last stroke of a +
  t_ref_min)**. It returns the time, or -1. The harness enforces this; a controller cannot act sooner.
- `ctl_wake(k, t)` asks for a `wake` callback at t (strictly later than now).
- `ctl_steer(k, dx, dy, t, kmax, min_align, tol)` is a greedy helper. It schedules rim strokes whose eventual
  displacement approximates (dx, dy), under the assumed motor sign.

Models of the controller's own actions (allowed for every controller; they never read the world):
- `ctl_twitch(k, a, t)` and `ctl_last_fire(k, a)`: commanded twitch and last stroke of a cell.
- `ctl_key_armed(k)` and `ctl_tap_would_click(k, kappa, t)`: the key model.
- `ctl_eff_pos(k, t, &x, &y)` and `ctl_eff_final`: the **efference copy**, where its own strokes alone would have
  moved the dot.
- `ctl_pending_disp(k, t, ...)`: the displacement still to come from strokes at or after now.
- `ctl_set_motor_sign(k, ±1)`: tells these models which motor law to assume.

These models are exact while every commanded cell is alive and the assumed law is the true one. Wounds and an
undetected flip make them drift, which is the point for those capabilities.

Privileged only: `ctl_truth(k, &tr)` fills `CtlTruth` at the left limit of `now`:
- dot position, force and drag;
- target offset and velocity, visibility, flip state and t_flip;
- blob 1 existence, presence, epoch, offset, velocity, value and radius;
- key state, hotspot twitch, and live sense / act counts;
- world constants.

It returns 0 for information-matched controllers. Future draws (next turn, next timer, placement) are never exposed.

**The information rule** (a convention, documented and reviewable): an information-matched controller uses only its
pings, its callback times, its own actions and the models of them above, the footprint, its parameters and the
body-physics constants in `Ctl`.
- It must not read `k->_c` or anything private (fields starting with `_`).
- It must not read per-life hidden state; for example, `t_flip` lives in the world vector, and the controller
  never sees that vector.
- World *rules* that are fixed across a world's lives may enter through the parameters. Examples: halo width, rates,
  placement law, timer, blink rates. C4 does this through `bayes_params`. A tuned or evolved body can absorb such
  constants.

### Adding a controller

1. Write `my_ctl.c` like `examples/example_ctl.c`.
   - Pick an id >= 1000 (0-99 are built-in).
   - Prefix every static name: all controllers share one translation unit with the kernel.
   - Use `CTL_REGISTER`. A later registration of the same id replaces the earlier one.
2. Build your own library (do not overwrite this directory's `.so` files):
   `python make_ckernel.py --fast --out /your/dir/ck_fast.so --ctl /your/dir/my_ctl.c`
   (and once more without `--fast` and with another `--out` if you need hashes).
3. Run it: `H.ctl_run(1001, p, fp, world, seeds, lib="/your/dir/ck_fast.so", privileged=False)`. Optionally call
   `H.register(H.CtlSpec(1001, "name", priv, names, default, lo, hi))` for defaults and tuner bounds.
4. Check it: `H.registered(lib)` lists the compiled ids. A controller whose `init` returns nonzero marks its lives
   with the capacity status bit (128).

## The latency rule

In the tissue, a receptor event is read from the screen at the candidate time `c_j`. It is delivered to the sense
cell at `c_j + d_min` (transduction, LIFE_ABI 9.7.5), and the sense cell fires at once. Its ARRIVAL reaches the act
cell above after one vertical contact delay `dl = dc * (1 + jit * (2u - 1)) + theta.delta`, floored at `d_min`. Here
`dc = d0 * exp(delay_sd * N(0,1))` is frozen per contact (LIFE_ABI 7.3, 7.7), so the median hop is `d0`. The act cell
strokes on arrival.

The harness reproduces this as follows:
- The controller receives each ping at the delivery time `c_j + d_min`, exactly when a sense cell would.
- Any stroke it commands happens at `>= (time of the callback that decided it) + latency`. A callback at time t has
  seen only pings delivered at or before t.
- **Default `latency = d0`**, the world's median one-hop delay with delta 0: 1.0 in today's base, 0.5 at d0 0.5. It
  is recorded per life in `res.latency`.
- `latency="dmin"` gives the causality floor (d_min). A number gives any other value.
- The full receptor-to-stroke latency is therefore `d_min + d0`, the same as reflex@hollow3's median chain.
- Lognormal hop spread (delay_sd 0.1) and jitter (±10%) are not reproduced; they average out (C0 vs reflex below).

## Built-in controllers

| id | name | mode | what |
|---|---|---|---|
| 0 | null | - | never acts. Used by the stream-equality test |
| 1 | C0 central reflex | info | Each sense column's ping strokes that column's act cell; centre pings tap. Column refractory 0.5, tap refractory 4, optional centre coincidence. Calibration against reflex@hollow3 |
| 2 | C1 privileged pursuit | priv | Every dt it reads the truth and steers the dot's eventual position (drift + pending strokes) onto the target extrapolated by latency + lead, using the true flip state at the stroke time. It taps when the predicted distance at the stroke time is < 0.8 rho_c and the key will click. It never taps near a negative blob 1, chases a nearer positive blob 1, and `use_dark=0` gives a "perfect sensing + memory" variant |
| 3 | C2 generic tracker | info | Pings in the efference frame, exponential forgetting (tau_f), background-subtracted centroid, steer to it, tap when the evidence is strong and centred (or the centre cell's own evidence is high), optional blind arc search. 15 parameters |
| 4 | C3 tiny RNN | info | Fixed tick dt. Input: ping counts per sense cell since the last tick + key state + hotspot twitch. tanh recurrent layer of n_h units; a stroke per act cell when its output exceeds thr. `H.rnn_size(fp, n_h)` parameters |
| 5 | C4 Bayes grid tracker | info + world rules | Posterior over the target position on a 0.2 grid, with visible / dark mass. Updated by ping likelihoods, no-ping evidence, diffusion, the timer's re-placement, blink transitions, and the capture its own clicks imply. Taps when the posterior mass under the dot at the stroke time is >= q_tap; steers to the best rho_c box. World rules come from `bayes_params(world)` |
| 99 | replay | test | Replays a schedule of strokes (`tests/replay.py`) |

Each controller's parameter layout is in the comment block above it in `ctl_builtin.c` and in
`H.CONTROLLERS[cid].names`.

## Validation

VALIDATION_PLACEHOLDER

## Known limitations

- **The sticks are bounds of a particular kind.**
  - C1 is a heuristic pursuit policy, not an optimal one, so its F is a lower bound on the true ceiling.
  - C2 and C4 are approximate observers. C4 uses diffusion as its motion model (no velocity state), a body position
    quantized to the grid, square-box steering and an assumed placement law. Their F is a lower bound on what
    information-matched control can earn.
  - "C4 does not beat the reflex" therefore does not prove the information is absent. "C4 beats the reflex" does
    prove it is present and worth using.
- **Central computation is free.** Controllers pay for strokes (`c_spike + c_tw*kappa`), pings (per `charge`),
  misses and c_live per footprint cell, but nothing for memory, arithmetic or messages between distant cells. A
  tissue that does the same computation pays for its neurons and messages. Its fixed footprint pays no development
  cost either; the prior study measured that grown bodies earn 1.8-3.2 F less than program bodies. The gaps
  measured here are upper bounds on what a grown local tissue could gain.
- **Continuous kappa.** Without `quant=True`, a controller can command any twitch increment in (0, 1]. The GRN grid
  has {0.25, 0.5, 1}; program rows can be off-grid.
- **Action rate.** One stroke per act cell per `t_ref_min` (0.5). There is no limit on how many cells stroke at once.
- **Own-action models assume an intact body.** They use the t0 faces, footprint and drag, and the assumed motor sign.
  - With wounds, strokes of dead cells are silently dropped and the models drift. Information-matched controllers
    are not told which cells died.
  - The hotspot can die; C1 then keeps commanding taps that never happen (wound25: commanded 176 vs real 132 clicks).
- **Truth is the present, not the future.** It does not include the next turn, the timer or placement draws.
- **Heap scheduler only.** `ctl_life_run` refuses window-scheduler worlds (code -5). Lives are deterministic, and
  independent of thread count.
  - Ties at exactly equal times between a controller event and another site's event are broken by the tie seed,
    like any tie.
  - A stroke at exactly a wake time is kept "pending" for privileged planning, because the truth is a left limit.
- **Ping charge model.** `"relay"` charges one contact per ping; a reflex@hollow3 sense cell's spike has n_out 1-3.
  C0 vs the tissue reflex shows the net cost difference is negligible (about 0.002 per ping).
- **Footprints have no hidden planes**, except `disk{k}x4` for cost. Controllers do not model hidden-plane latency.
- **Flip draws differ from the prior study.** `flip_mid` draws t_flip ~ U[256, 768] from the life seed (numpy), not
  with the prior study's `flip_family`, so lives are not the prior study's lives. (They never were: seed blocks
  differ.)
- **Scratch ledger columns.** Columns 21/22 mean dark / late captures in CATCH on this kernel only.
- **Speed.** Everything is below 0.03 CPU-s per life except C4: 0.13-0.25 CPU-s per life on this loaded machine
  (0.21 with the blink model). Its grid passes dominate; `h` 0.25 or `W` 6 cut that by about 30%.
- **C3 is a hook, not a result.** A 292-weight generic RNN did not learn to catch in a short tuning run.
- **Mixing call styles.** `ctl_run` with a per-life `cid` array works, but every life still uses one footprint and one
  `charge` setting per call.

## Recovery note (2026-10-10)

The machine rebooted and wiped /tmp. This directory was rebuilt by replaying the harness agent's file writes from its
transcript (`../recover/replay.py`); `make_ckernel.py` and `--fast` rebuild the kernels and `tests/test_harness.py`
passes 19/19. Lost and not recoverable: `reflex_knobs.json` (the prior studies' re-tuned reflex knobs; their sources
are gone), `tests/validation.json/.md` and the C4 tuned parameters. `H.best_reflex` therefore falls back to the frozen
reflex until you re-tune with `retune_reflex.py` (it records 'rt-harness' entries). The first-look numbers in
`../cached/harness.json` were measured before the reboot.
