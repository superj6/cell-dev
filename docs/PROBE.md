# Probe toolkit for CATCH bodies (`src/life/probe.py`)

This toolkit is for interpreting how a body (evolved or hand-built) turns receptor events into twitches and clicks:
who fires whom, along which paths, with what latency, and which messages the score depends on. It was checked on the
two hand-built SPECK bodies whose mechanism is known, `reflex@hollow3` and `router@ring4`, and smoke-tested on the
evolved `speck_lmax4_hexprism_sex_s5`. Nothing in the toolkit writes into the repository.

```python
# from the repository root (on a shared machine: nice -n 19 .venv/bin/python ...)
from src.life import probe as P
org, preset = P.load("speck_lmax4_hexprism_sex_s5")    # or P.hand("router@ring4")
tr = P.trace(org, P.SEEDS[0], preset)                   # one fully logged life, checked against the kernel
P.relabel(tr)                                           # role labels C S J / K M I / H from the occupancy
print(P.report(tr))                                     # summary, steering, tuning, CCG, drivers, chains
sig = P.signature([P.trace(org, s, preset) for s in P.SEEDS[:4]])   # the router-vs-reflex numbers
P.lesion(org, preset, "lateral_off", t_fork=256, n_lives=128, base_fork="freeze")   # kernel fork, paired dF
```

`P.SEEDS` is `analysis.fresh_seeds(4096, seed0=30_000_000)`. Every result below uses those seeds, starting at
30,000,000, so none overlaps a pre-registered range.

## How it works

- **`trace` runs the pure-Python reference simulator under observation.** It uses a subclass of `reference._Life` and
  `_Accountant` that only reads the life. Hooks sit on birth, death, FIRE, the membrane step, TICK, `send`, receptor
  candidates, and the CATCH accountant's strokes, clicks, placements and samples. Each traced life's F is checked
  bitwise against the kernel's F on the same seed (`check=True`, the default), so a trace is the real life. All
  traces so far have matched.
- **Spikes are linked into causal chains.** At FIRE the observer writes down which spike produced each ARRIVAL it
  sends, keyed by (receiver site, arrival time, receiver slot). Every arrival in the trace therefore knows its sender
  spike, and every spike knows its membrane step. Following these links gives the exact message-passing graph of a
  life.
- **The same subclass can lesion messages.** `Lesion` blocks ARRIVAL channel bits after `t_fork`, filtered by slot
  direction, sender plane, sender sites or any predicate on the sender. A blocked spike is still charged, as with the
  kernel's `lateral_off`. Check: `Lesion(t, slots="lateral")` reproduces the kernel's `lateral_off` fork bitwise
  (`check_lesion_equivalence`; passed on router@ring4 for 2 seeds and on s5 for 1 seed).
- **`trace_kernel` is a fast partial trace.** It reads the kernel's raster and fate log and gives cells, spikes and
  knobs at birth. It has no channel masks (they come from the emit bits at birth), no receptor events, no membrane
  steps and no world trajectory. `ccg` and `act_drivers` work on it, so these probes can use many lives.

## API

| function | returns |
|---|---|
| `load(run)` | `(hb.GrnBody, preset)` for `outputs/catch_pilot/<run>/best_genome.json`. The preset is the run's own world, read from `config.yaml`, else the results row, else the name rule. This gives speck_* → `catch_speck_l4`, lmax4_* and seeded_* → `catch_v1_l4`, lmax2_* → `catch_v1_l2`. |
| `hand(name)` | `(hb.speck_body(name), "catch_speck_l4")`. |
| `trace(org, seed, preset, *, check=True, lesion=None, **world)` | `Trace` (tables below). `lesion` traces a lesioned life; no kernel check is done then. |
| `trace_kernel(org, seeds, preset, *, threads=2, **world)` | a list of `KTrace` (cells, knobs_birth, spikes, ledger). |
| `relabel(tr, t_ref=None)` | Overwrites `cls` with roles taken from the occupancy at `t_ref` (default T/2). Sense cells: C = centre, J = interior (all 6 in-plane neighbours alive), S = rim. Act cells: K = hotspot, I = interior, M = rim. H = hidden. Without it, `cls` is C/S/K/M/H by site. |
| `tuning(tr, *, min_spikes=10, near=None)` | One row per cell: rate; `rate_b0..7` (vs the target's bearing from the dot; bin k is centred on k·45°, counter-clockwise from +x); `rate_d*` (vs target distance from the dot, edges 0,1,2,3,4,6,∞); `rate_c*` (vs target distance from the cell's own screen point, edges 0,.5,1,1.5,2,3,∞). `vs` is the vector strength of the bearing tuning and `pref` the preferred bearing; `own` is the cell's own direction and `pref_minus_own` the difference. Act cells add `n_pull`, `face` (mean exposed-face direction), `align` (force-weighted mean cos(face, target bearing) over pulling strokes; 0 = chance), `toward` (share of pulls with cos > 0) and `pull_rate_b*`. Occupancy comes from the integer-time samples while the cell is alive. Spikes are binned by the exact positions at their record time. |
| `steering(tr)` | Body-level `align` and `toward` over all pulling strokes, also split into near (target within 2 of the dot) and far. |
| `tuning_table(tun)` | Compact text per class. |
| `ccg(trs, *, max_lag=5, bin=0.25, label=None, follow=(0.5, 3))` | Neighbour-pair cross-correlograms (lags 0 to 5), aggregated by (pre class, dir, post class), over one or more traces. Columns: `counts`, `expected` (independent stationary trains), `ratio`, `peak_lag`, `peak_ratio`, `sharp` (peak ratio / median ratio at lags ≥ 2), `p_follow`, `p_chance`, `lift`. `dir` is lat, up (receiver above sender) or down. |
| `ccg_table(df)` | Compact text. |
| `act_drivers(trs, *, window=(0.5, 3), radius=2)` | For every act spike: which neighbours spiked in [t−3, t−0.5]. Reported: own-column sense cell, sense cells of other columns at hex distance 1 (and up to `radius`), in-plane act neighbours, the hidden cell above, none. Each is given with its chance level (the same spikes moved to uniform times in the cell's life). `own_first` means the own sense cell spiked last among the column and ring 1. Also latency quartiles to the own sense spike. Works on Trace and KTrace. |
| `drive_matrix(tr)` | For every spike, the class and direction of its largest input in the firing step (or `rec`, `tonic`, `resid`), counted per receiving class. |
| `chains(tr)` | One row per act spike, traced back to its origin. `origin` is rec / tonic / resid / unknown / deep. Also `origin_dist` (hex distance from the origin column to the act column), `hops`, `lat_hops`, `latency`, `p_signal` (probability that the origin receptor event came from the target, not background), `path` (e.g. `J[rec] S<lat M<down`) and `via_own_sense`. |
| `chain_summary(ch)` | Per act class: origin shares, `rec_own_col` / `rec_other_col`, `relayed` (at least one lateral hop), `rec_signal`, `lat_by_hops`, `hops_share`, `top_paths`. |
| `pathway_weights(tr)` | Delivered effective weights per (pre, travel, post) pathway. These are the contributions of non-refractory arrivals (w_eff·mask, including the a0/a1 anisotropy). `travel` up = from below to above (the same convention as `ccg`'s `dir`). |
| `sense_drive(tr)` | Sense spikes split by driver (own receptor, `arr_lat`, `arr_up`, tonic, resid), per class and ring. |
| `signature(trs)` | The numbers that separate a router from a reflex (below), pooled over traces. |
| `pooled(fn, trs)` | Runs a per-trace DataFrame probe over several traces and concatenates the results with a `life` column. |
| `lesion(org, preset, flags, t_fork, n_lives=128, seed0=SEED0, *, threads=2, t_open="fork", base_fork=0, **world)` | Kernel fork: `flags` (a name, `"a+b"` or a list) applied from t0 + t_fork via `fork_flags`. The unchanged twin has the same t_fork and t_open. `t_open="fork"` counts F over [t_fork, T]; pass 0 for the whole life. `base_fork` (e.g. `"freeze"`) is applied in both arms, so the contrast isolates the lesion from its effect on later growth. Returns base and lesioned summaries, paired `dF` (`analysis.paired`, lesioned − base), captures, misses and n_end. |
| `Lesion(t_fork, channels=3, slots="all", planes=None, sites=None, where=None)` | Reference message lesion. `slots` is all / lateral / up / down / vertical. `planes` holds sender heights (2 = every z ≥ 2). `sites` is a set of (a,b,z). `where(site, cell)` is any predicate on the sender (`cell.th` is its current phenotype list). |
| `lesion_ref(org, preset, les, n_lives=16, seed0=SEED0, *, procs=1, **world)` | Paired effect of a `Lesion`. The twin is a kernel life (bitwise the unlesioned reference life); the lesioned arm runs in `procs` forked Python workers (use ≤ 2). Pass `fork_flags=V3.flags("freeze"), t_fork=...` in `world` to freeze both arms. |
| `check_lesion_equivalence(org, preset, t_fork, seeds)` | Self-test: the reference lateral Lesion must equal the kernel's lateral_off. |
| `development_end(org, preset, n)` | Quantiles of last birth time and end size. |
| `report(tr)` | A text report for one trace. |

### `Trace` tables (pandas)

`cid` is the cell index in birth order and links the tables.

| table | content |
|---|---|
| `cells` | cid, uid, a, b, z, x, y (planar offset), plane, cls, t_birth, t_death (inf if alive at the end), death_cause, mother (uid), mother_cid, initial, k, row (program row), n_spikes, n_rec |
| `knobs_birth`, `knobs_end` | [cid × 23 knobs]: the kernel's decode (`V3.decode_knobs(readout(g))`, the same as `life_decode`) at birth, and at death or the end of the life |
| `genes_birth`, `genes_end` | [cid × 16]: g at birth, and at death or the end (zeros in program mode) |
| `pheno_changes` | t, cid, knob, old, new: every knob change at a tick |
| `spikes` | sid, t, cid, a, b, z, cls, **mask** (emit bits at fire time: 1 = ch0, 2 = ch1), kappa, cause (input / threshold / tick / input+threshold), step, X, Y (dot), tx, ty (target) at the spike's record time (left limit) |
| `steps` | membrane steps: step, t, cid, site, v0 (membrane before this step's input; 1 for a threshold crossing), rin (receptor input g_r·n_rec), refractory, fired, thr, n_arr |
| `arrivals` | step, t, cid (receiver), slot, dir (where the sender sits: lat / up / down), sa, sb, sz, s_cid, s_sid (sender spike), mask, contrib (w_eff·mask; 0 while refractory) |
| `receptors` | delivered receptor events: t, cid, a, b, n_rec, g_r, refractory, step, p_signal, X, Y, tx, ty |
| `traj` | t = 0..T−1: dot X, Y and target tx, ty (the accountant's integer samples, left limits) |
| `strokes` | every act-plane twitch with kappa > 0: t, a, b, cid, nx, ny (exposed face), dz, zt, zn, pulled, X, Y, tx, ty |
| `clicks` | t, outcome (capture / miss / blob1), X, Y, tx, ty |
| `placements` | t, blob, cause (0 start, 1 capture, 2 timer, 3 with the target), x, y |
| `ledger`, `meta` | the 57 ledger columns; seed, preset, org, seconds, kernel_F, n_blocked |

## Speeds

All timings were taken at nice 19 while the 29-run pilot kept the machine at load average 24-26 on 14 cores, so
wall times vary by about 2x. Memory stays below 0.36 GB per process in every case.

| what | reflex@hollow3 (56 cells) | router@ring4 (122 cells) | s5 (GRN, about 120-140 cells) |
|---|---|---|---|
| `trace` (reference, logged, with kernel check), wall s per life | 10-41 (median 15) | 23-54 (median 29) | 39-46 at load 25 (27 s CPU); 61-175 at load 50-130 |
| reference life for `lesion_ref`, no logging, s per life per worker | ~11 | ~25 | ~37 |
| `trace_kernel`, s per life (threads 1) | ~0.6 | ~0.2 | ~0.23 |
| `lesion` (kernel, 2 × 128 lives, threads 2), s | 8-10 | 18-23 | 20-34 |
| probes on one trace (tuning + ccg + drivers + chains) | < 2 s | ~3 s | ~5 s |

The reference is fast enough to trace a 150-cell body (about 40 s per life). Use full traces for mechanism (4-8
lives) and the kernel for statistics: `lesion` on 128-512 lives, and `trace_kernel` with `ccg` / `act_drivers` on
dozens of lives.

## Validation on the known bodies

Six traced lives per body, seeds 30,000,000-30,000,005, under `catch_speck_l4`.

**What they are designed to do** (`handbuilt.py` role bodies, RESULTS.md GS1-GS6):

- **reflex@hollow3 (the reflex).**
  - Shape: sense plane holds the centre and ring 3 only; act plane is the full rings 0-3.
  - Each steering sensor S (g_r 1, b 0.625, so one receptor event fires it) relays on channel 0 to the act cell
    directly above it. That act cell M (w0 1.5, kappa 1, t_ref 0.5) twitches and pulls outward along its exposed
    face, which is toward the target sitting over that sensor.
  - The centre sensor C drives the hotspot K, which clicks.
  - There is no lateral weight anywhere, so lateral_off should change nothing.
- **router@ring4 (the router).**
  - Shape: complete rings 0-4 in both planes.
  - Interior sensors J (g_r 0.5, b 0.25, emit1 only) detect coincident receptor events and relay on channel 1 to all
    their neighbours.
  - Rim sensors S listen to channel 1 (w1 1.0) and fire on one J relay as well as on their own receptor. They pass it
    up on channel 0 to the rim motor M.
  - So a target over the interior near one side makes that side's rim motors pull toward it. RESULTS.md GS2: +2.25
    over the best reflex. GS4: lateral_off removes 4.3 times that gain.

| probe | reflex@hollow3 | router@ring4 |
|---|---|---|
| F (6 traced lives) | +10.10 | +9.50 |
| **chains, rim act cells M: receptor origin in another column** | **0.000** | **0.385** |
| chains M: at least one lateral hop (`relayed`) | 0.000 | 0.385 |
| chains M: paths | S[rec] → M<down 100% | S[rec] → M<down 61.5%; J[rec] → S<lat → M<down 36.5%; J → J → S → M 1.9% |
| hop count of receptor-origin chains (M) | 1 hop: 100% | 1: 61.5%, 2: 36.5%, 3: 1.9% |
| latency from the origin spike, by hops | 1 hop 1.00 | 1 hop 1.01, 2 hops 2.01, 3 hops 2.99 |
| sense spikes fired by their own receptor / by a lateral sense arrival | 1.00 / 0.00 | 0.73 / 0.27 (rim S: 0.61 / 0.39 from J; J: 0.93 / 0.07) |
| act spikes fired from the sense cell below | 1.00 | 1.00 |
| CCG lateral sense → sense | S→S x2.2 at all lags, **sharp 1.5** (shared target only) | **J→S peak 0.88, x28, sharp 9.4, lift 6.3** (one-hop transmission); S→S x6.7 at lag 0-0.25 (common J input) |
| CCG sense → act (up) | S→M peak 0.88-1.12, x28, sharp 14 | S→M peak 1.12, x29, sharp 15 |
| act drivers M: own-column sense spike in [t−3, t−0.5] | 1.00 (chance 0.15) | 1.00 (chance 0.14) |
| act drivers M: a ring-1 neighbour column's sense spike | 0.42 (chance 0.28) | 0.58 (chance 0.27) |
| act drivers M: own sense was the latest of column + ring 1 | 0.87 | 0.70 |
| latency to the own-sense spike (quartiles) | 0.91 / 1.00 / 1.10 | 0.92 / 1.01 / 1.10 |
| tuning: sense bearing selectivity `vs` | S 0.31 (\|pref−own\| 12°) | J 0.74 (7°), S 0.37 (9°) |
| receptive field (rim S rate vs target distance from the cell: 0-.5, .5-1, 1-1.5, 1.5-2, 2-3) | 0.82, 0.59, 0.25, 0.09, 0.05 | 0.56, 0.44, 0.34, **0.22**, 0.09 (wider: J relays reach about 1 unit inward) |
| act pull alignment `align` / `toward` | +0.18 / 0.64 | +0.23 / 0.68 |
| origin receptor event from the target (`rec_signal`) | 0.29 (71% of motor spikes come from background events) | 0.36 |
| **kernel lateral_off at t_fork 256** (F over [256, T], 128 lives) | **dF +0.000 ± 0.000** (lives unchanged) | **dF −9.26 ± 0.32** (z −29), captures 21.0 → 6.8 |
| kernel lateral_off, whole life (t_fork 0, t_open 0) | +0.000 ± 0.000 | −9.57 ± 0.27 |
| kernel hidden_off / receptor_off / motor_off at 256 | 0 / −9.75 / −9.78 | 0 / −13.14 / −13.20 |
| reference Lesion: channel 1 blocked at 256 (16 lives) | dF 0.000 (nothing emits ch1; 0 arrivals blocked) | dF −9.51 ± 0.81 (kernel lateral_off on the same 16 lives: −9.43 ± 0.82) |
| reference Lesion: other | centre sense cell's output silenced: −9.96 ± 0.61 (captures 16 → 0.06) | sense-plane upward messages blocked: −12.66 ± 0.80 |
| logged lesioned trace (router, ch1 blocked at 256) | — | M relayed 0.42 before the fork, 0.00 after |

### Signatures

**What marks a reflex.** Every act spike's chain is `S[rec] → M<down`: one hop, about 1.0 time unit, from a receptor
event in the act cell's own column. Sense cells are fired only by their own receptor. Lateral sense-plane
correlograms show only shared-input correlation: ratio about 2 at every lag, `sharp` about 1.5. lateral_off after
development changes nothing.

**What marks a router** (in decreasing order of directness):

1. **Chains with a lateral hop.** `chain_summary(...).rec_other_col` and `relayed` are well above 0 (0.385 here, against
   exactly 0). The latency is quantised by hop count (1.0, 2.0, 3.0 time units at d0 1). This is the defining
   property: motors fire on evidence from another column, carried through the sense plane.
2. **Sense cells fired by lateral arrivals.** In `sense_drive` / `drive_matrix`, rim sensors get a large share of
   their spikes from `J(lat)` (0.39, against 0).
3. **A kernel-only proxy, usable on many lives.** The lateral sense → sense CCG has a sharp peak at lag about d0
   (0.75-1.25), with `sharp` well above 1 (router J→S 9.4-9.8; reflex S→S 1.5). Together with this, lateral_off after
   development removes most of F (−9.3 against 0).

**Probes that do not separate them.**

- "Is the act spike preceded by its own column's sense spike?" Yes in both (1.00): in the router the own-column rim
  sensor is the last relay before the motor. The question that separates them is what fired that sense cell, so use
  `chains` or `sense_drive`.
- The correlational "a neighbour column's sense cell spiked before" is higher in the router (0.58 against 0.42; chance
  0.27-0.28). But it is confounded by co-activation from the same target.

## Smoke test on an evolved body: speck_lmax4_hexprism_sex_s5

This is a smoke test, not a finding. It used 4 traced lives (seeds 30,000,000-30,000,003; every F matched the
kernel bitwise) plus kernel and reference lesions. Run `load("speck_lmax4_hexprism_sex_s5")`; it gives
`catch_speck_l4`. The 4 lives ended with 113-136 cells (S 56-63, M 47-58, H 10-17) and had F +6.13 to +8.76.

**Every probe ran on this body.** It shows a body that pools lateral evidence in the sense plane, router-like, plus
two features the hand-built bodies lack:

- **Lateral routing exists, weaker than the hand router's.**
  - **Chains.** 32% of rim-motor (M) spikes start from a receptor event in another column (router 39%, reflex 0%).
    Latencies are quantised by hop count: 0.99, 1.99, 2.98 for 1, 2, 3 hops.
  - **Sense drive.** 33% of rim-sensor spikes and 22% of interior-sensor spikes are fired by lateral sense arrivals.
  - **Delivered weights.** Lateral sense-plane weights are weak and excitatory: J→S +0.55, J→J +0.34, S→S +0.24,
    C→J +0.36. Several arrivals, or one arrival plus a receptor event, are needed to fire a cell. Kernel CCG
    J→S: peak 1.12, x10, sharp 3.8 (router 9.4, reflex 1.5).
- **Sense cells are coincidence detectors.**
  - All cells end with b ≈ −0.65, tau_m 4, t_ref 0.5. Sense cells have g_r ≈ 1.2-1.3, so one receptor event leaves
    the membrane below threshold.
  - Only 57% of receptor events fire their cell. The origins of motor chains are target events 60% of the time
    (`rec_signal`), against 29% in the reflex, where any background event fires a sensor.
- **Recurrent inhibitory feedback** (from `pathway_weights`). Every cell emits on both channels with w0 ≈ +1.1 and
  w1 ≈ −0.8; the slot-dependent anisotropy (a0, a1, pol) makes the sign differ by pathway:
  - sense → act upward, about +2.4 to +2.8: one arrival fires the act cell;
  - act → its own sense cell (downward), −1.3 to −1.6: each twitch resets its sensor;
  - act → hidden, +1.9 to +2.0;
  - hidden → act (downward), −1.0 to −1.2;
  - lateral act → act: mixed sign (M→M mean +0.14, 28% negative).
- **Waste.** Interior act cells (I) fire 600-1900 twitches per life, of which 1-3% pull (their face is closed). Every
  cell has kappa 1, so they all pay the twitch cost.
- **Lesions** (F over [256, T]):

  | lesion | dF |
  |---|---|
  | kernel `lateral_off` at 256 | −5.48 ± 0.32 (n 128; base +7.92) |
  | the same with both arms frozen at 256 | −4.40 ± 0.30 (n 128); −4.38 ± 0.15 (n 512) |
  | `hidden_off` | −0.25 ± 0.25 (frozen: +0.05 ± 0.19), so the hidden plane does not matter for F |
  | `freeze` alone | −0.83 ± 0.28 |
  | reference: sense-plane lateral messages only (24 lives) | −3.51 ± 0.75 (z −4.7), against −5.54 ± 0.59 for the kernel's full `lateral_off` on the same 24 lives |
  | reference: act-plane lateral only, hidden output only (8 lives each) | −0.08 ± 1.09 and +0.48 ± 1.23 (too few lives to call) |

  About two thirds of the lateral dependence therefore lies in the sense plane.
- **Against the pre-registered routing criterion.** With F ≈ 7.9 this genome does not beat `reflex@hollow3` (+8.66),
  so it is not an evolved router by that criterion. It does use a sense-plane routing mechanism of the router's kind.
- **Development.** Growth is mostly done by t = 256 (about 117 of ~122 cells), but rare births go on until about
  t = 800-1000 (last birth: median 814, 90% quantile 976). Gridded knobs change about 2,000 times per life per knob
  family (b, g_r, pol, zeta, a0/a1), so phenotypes are modulated during life. Emit bits never changed, so
  `trace_kernel`'s birth masks are right for this body.
- **Cost.** A traced life took 39 s at load about 25, and 61-175 s while other jobs pushed the load average to
  50-130. Peak memory was 0.35 GB.

## Caveats

- **What chains attribute.**
  - A chain credits each spike to the largest input of its firing step (the "last straw"). For the hand-built bodies
    this is exact: every relay fires on one input.
  - For integrating cells the membrane before the step (`steps.v0`) also carries earlier inputs, and those are not
    followed back.
  - A spike whose inputs in the firing step were all ≤ 0 is labelled `resid`.
  - Threshold crossings and tick re-anchors are labelled `tonic`, including a crossing that coincides with an input.
  - Check `chain_summary` origin shares before reading paths.
- **CCG expected counts assume independent stationary trains.** The moving target co-modulates everything, so ratios
  of 2-6 at every lag mean shared input. Read `sharp` and `peak_lag`:
  - a peak near d0 + delta (about 0.75-1.25 here) means direct transmission;
  - a peak at lag 0-0.25 means a common driver.
- **Positions.**
  - Positions are exact left limits at each record's time.
  - Receptor rows give positions at delivery, which is d_min = 0.5 after the world's candidate. `p_signal` is
    computed at the candidate with the world's own formula.
  - Tuning occupancy uses integer samples (1 unit).
  - Bearings are in the screen frame, which is the body frame, because the body only translates.
- **`relabel` is geometric.** It labels roles from the occupancy at T/2, so roles mean interior or rim, not function.
  Growing GRN bodies change shape: cells not alive at T/2 are labelled at their own mid-life. Pass `t_ref` to change
  this.
- **Kernel lesions after t_fork in a body that is still growing also change the rest of its development.**
  - lateral_off changes the r0/r1 trace inputs of the genes.
  - s5 keeps a few births until t ≈ 800-1000, although it holds about 117 of its ~122 cells by t = 256.
  - Use `base_fork="freeze"` (both arms frozen) to isolate the message effect; freezing alone costs s5 −0.83 ± 0.28.
  - Paired SEs for GRN bodies stay close to unpaired ones, because lives diverge after any change. Use ≥ 128 lives
    (kernel) for a GRN body.
- **The kernel has no per-cell or per-channel lesions** (LIFE_ABI section 12). Its forks are plane- or slot-wide:
  `lateral_off`, `hidden_off`, `receptor_off`, `motor_off`, `contacts_off`, plus chem_off, division_off, freeze,
  genes_blind and the others. The nearest kernel substitutes are:
  - `hidden_off` (all z ≥ 2);
  - the panel's `kill_t` / `kill_frac` (a random fraction killed at one time, not targeted);
  - `stuck_t`, `stuck_a`, `stuck_b`, `stuck_z` (one site forced tonic);
  - genome surgery (`scripts/catch_pilot_analysis.knock`), which also changes development;
  - for program bodies, editing the program row: exact, because they have no development.

  The reference `Lesion` is the exact per-cell / per-channel / per-direction tool, at reference speed (16 router
  lives with 2 workers ≈ 4 min; 24 s5 lives ≈ 8 min).
- **What a `Lesion` does and does not stop.** It silences outgoing messages only: the cell still fires, pays, and
  (in the act plane) pulls and clicks. To remove motor effects use the kernel's `motor_off` (whole act plane).
  `where` is evaluated at send time on the sender's current phenotype.
- **Direction conventions differ by table.**
  - In `arrivals.dir` and in chain paths (`M<down`), the direction is where the sender sits relative to the receiver:
    `M<down` = driven by the cell below.
  - In `ccg.dir` and `pathway_weights.travel`, it is the direction the message moved: `S -up-> M`.
- **Column name clash.** `cells.b` is the hex coordinate and `knobs_*.b` is the bias knob. Join with `rsuffix`.
- **`pheno_changes` skips the continuous knobs.** asym, sec0 and sec1 change at nearly every GRN tick, so they are not
  logged; their end values are in `knobs_end`.
- **`trace_kernel` masks are the emit bits at birth.** GRN cells may change them later; check `pheno_changes` in a
  reference trace. `trace_kernel` also has no receptor events, so it cannot compute chains or tuning.
- **Reference speed depends on body size and spike count.** It is about 0.003-0.005 s per spike-with-messages at the
  current machine load. A body with thousands of tonic cells would need the kernel path.

## E6 readouts (2026-10-13)

`src/life/readouts.py` adds report-only measurements for plan section 0.6. Nothing enters selection or the living
organism. A small validation batch, with one reference trace, is:

```bash
.venv/bin/python scripts/life_readouts.py --body router@ring4 --world pool --out outputs/e6_readouts/router
```

Use `--genome outputs/<run>/best_genome.json` for an evolved body. Defaults are eight 256-unit kernel lives, a fork
at 128, one trace and one thread. These defaults check the plumbing; they do not establish an evolutionary result.
Results are saved after the kernel batch and each trace. Larger batches still need the user's launch approval.

| Readout | Definition and limits |
|---|---|
| Lateral net-F share | `(mean F_base - mean F_lateral_off) / mean F_base`, both counted from the fork. Also reports the paired F loss. A fork can change subsequent development. |
| Lateral share of lead (R1) | Supply the paired best-reflex scores: `(mean F_base - mean F_lateral_off) / (mean F_base - mean F_reflex)`. The reflex must use the same accounting window. |
| Relay chains | Existing largest-input attribution, with origin fractions, latency by hop count, and shares with at least one (`relayed`) or at least two (`relayed_2plus`) in-plane hops. Both shares divide by receptor-origin chains in that act-cell group, separately per life; other origins are excluded. Subthreshold integration is omitted. |
| BH3 | `(mean F_best - mean F_reflex) / (mean F_C4 - mean F_reflex)`, requiring paired fresh lives, the same world/accounting window, and the same footprint identifiers. |
| BH4 silence | Distance after at least `--silence-window` units with no delivered receptor ping anywhere in the body. Default 0.5 is one nominal base-world hop. Includes initial silence after this delay. |
| BH4 occupancy | Share of the ABI's integer-time samples inside the capture radius. This is an estimate of time share, not exact continuous dwell time. |
| BH4 clicking | Clicks divided by captures; null when there are no captures. |
| BH4 flip/dim | Null under ABI 3: flip and dim world state await the approved port; recovery also needs a registered operational definition. |

The motion observer records existing analytic movement segments without adding events or changing the integration
order. Silence distance integrates those segments through each eligible interval, so turns within an interval are
not replaced by a shorter straight chord. Pings include background events: the body does not know their source.
The command rejects guarded, capacity-failed, nonfinite or accounting-invalid lives and truncated logs; ordinary
extinction, wall contact and chemistry-clamp flags are retained in its status counts.

Ratios use the mean of paired numerators divided by the mean denominator, with a covariance-aware delta-method SE.
Negative shares and shares above 100% are retained. Nonpositive denominators produce null. Positive denominators
within three SE of zero are marked unreliable and cannot establish the BH3 quarter-gap criterion.
`readouts.member_comparisons(best, reflex, s5, lateral_off=None)` reports paired leads against both the best reflex
and pilot s5 for one family member. With lesioned scores, it adds both lateral-share definitions. Repeat per member;
the API checks seeds and the full world/accounting window, while allowing different tissue footprints. The small
CLI batch reports only the net-F share until separately scored best-reflex inputs are supplied through this API.

**BH3 data contract.** `readouts.information_share(best, reflex, c4)` accepts three `readouts.Scores` objects.
Each has `F`, `seeds`, `footprints` (one geometry/protocol identifier per life), `world` (all overrides, duration and
accounting window), and `tuning_seeds`. Tuning lives must be disjoint from scoring lives. Save these as JSON under
keys `best`, `reflex`, `c4` and pass `--bh3-scores PATH` to attach a comparison to a report. Its seeds must match the
report, and its world must be `{"preset": "catch_speck_l4", "T": ..., "d0": 0.5, "d_min": 0.25, "t_open": 0.0}`
(plus `sigma: 0.4, lam_s: 4.0` for POOL). Save the C4 parameters and reflex tuning/selection evidence with the scores.

The script deliberately leaves BH3 unmeasured without these scores. Published C4 scores on hollow3 cannot supply
an evolved body's denominator. The scratch harness can score a fixed body footprint; a growing body's final shape
is not its geometry throughout the life, and freezing that shape silently changes development costs and sensing.
A matched development protocol must be specified before calling that comparison exact. A footprint identifier
records that protocol; metadata checks cannot independently prove its implementation.
