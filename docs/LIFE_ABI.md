# One-life kernel ABI and event semantics (ABI v1)

This document is the contract between the C event kernel (`src/life/kernel.c`), the Python reference
(`src/life/reference.py`) and the harness (`src/life/spec.py` and its callers). It fixes the array layouts, inputs,
outputs and the exact event semantics of the model in `docs/ONE_LIFE_DESIGN.md`. An independent implementation that
follows it exactly, on the same libm, reproduces every ledger column, log and hash **bitwise**.

`src/life/spec.py` is the Python mirror of every constant, layout and pure function defined here. When this document
and `spec.py` disagree, that is a bug; fix one of them and the tests in `tests/test_life_spec.py`.

Status: v1 covers BELL-1 (design stage E1/v1) in float64: GRN and program modes, heap and window schedulers, forks
by replay, and the robustness-panel perturbations listed in section 7.9. The integer twin and the v2-v5 world
features are reserved (section 13). Section 15 lists every place where this contract makes a choice that the design
left open, or deviates from its pseudo-code, and why.

Revisions (ABI v1 is not yet frozen): cross-check round 1 (2026-10-07) made TICK step 1 set `inc[slot]` only from
the slot's current contact (7.4, 15.9), made a panel KILL charge the killed cell's last interval (7.9, 15.26), and
recorded 15.27. The kernel and the reference implement both. Migration step 3 (2026-10-07) fixed the Python
mirror of sigma for readouts below about -709.78 (section 2: the reference raised OverflowError where the kernel
returns 0); the kernel is unchanged.

Contents:
1. Overview of the computation
2. Arithmetic conventions
3. Randomness: hash, draws and uids
4. Kernel interface: entry points and arrays
5. State
6. Events, batches and the causality contract
7. Handlers
8. Phenotype decode and derived quantities
9. The accountant: records, world, ledger, logs, hashes
10. End of life: T, extinction and guards
11. Schedulers
12. Flags and forks
13. Reserved for later stages
14. Test vectors
15. Choices and deviations relative to ONE_LIFE_DESIGN.md

---------------------------------------------------------------------------------------------------------------------

## 1. Overview of the computation

- A **life** is one genome (or program) living from `t0` to `t1 = t0 + T`. Lives are independent. Results must not
  depend on how lives are batched or on the thread count.
- Space is a lattice of **sites** with integer coordinates `(a, b)`. In the default sparse fabric every coordinate
  exists. A site holds at most one live cell. Sites are the processing entities: every event is addressed to a site,
  and each site processes its own events in time order.
- A site's events with one timestamp form a **batch**, applied in a fixed kind order (section 6.2). A batch reads
  everything that comes from outside the cell as a **left limit** (the state at `t-`).
- Every effect of one site on another is a **message** that arrives at least `d_min` later. So sites never read each
  other's state, and any causally valid processing order gives the same history.
- Handlers emit **records** (spikes, births, deaths, ticks, claims, packets). One sequential **accountant** consumes
  the records of a life in canonical order `(t, sitekey, seq)` (section 9.1). Only the accountant computes
  cross-cell quantities: the BELL lumen, the ledger, n(t), extinction and guard checks, logs and hashes. This is
  what makes floating-point sums identical under every scheduler.

## 2. Arithmetic conventions

- All real quantities are IEEE-754 binary64 (`double`). Time is float64. Each formula is evaluated exactly as
  written, left to right, one rounding per operation, with no fused multiply-add and no reassociation. The kernel is
  compiled with `gcc -O3 -fopenmp -ffp-contract=off` and without `-ffast-math`, `-funsafe-math-optimizations` or
  `-march` flags. In the pseudo-code below, `a + b + c` means `(a + b) + c`.
- Transcendentals: only `exp`, `log` and `tanh` from the C math library (`math.exp`, `math.log` and `math.tanh` in
  Python call the same libm). Bitwise agreement between the kernel and the reference assumes the same libm. `floor`
  and `nextafter` are also used; they are exact.
- `rint(x)`: round to nearest, ties to even, keeping the sign of `x` (C `nearbyint` in the default rounding mode, so
  `rint(-0.4) = -0.0`). Python mirror: `math.copysign(float(round(x)), x)`.
- `clip(x, lo, hi)`: `x < lo ? lo : (x > hi ? hi : x)`. `max(x, y)` and `min(x, y)` are defined by the same
  comparisons (`x < y ? y : x` and `x > y ? y : x`), never by `fmin` or `fmax`.
- `sigma(x) = 1.0 / (1.0 + exp(-x))`. Where `exp(-x)` overflows (x below about -709.78) C returns inf and
  sigma is exactly 0.0; Python's `math.exp` raises there instead, so `spec.sigmoid` returns 0.0 explicitly.
- `q8(x) = rint(clip(x, -2, 2) * 8) / 8`: the 1/8 grid on [-2, 2].
- `q10(v) = rint(max(v, -2) * 1024) / 1024`: the Q10 membrane register with floor -2. Implementations may store the
  register as `int32 = rint(max(v, -2) * 1024)`; the value is identical.
- `bits(x)`: the IEEE-754 bit pattern of a double as a uint64.
- `nextup(t)`: the smallest double greater than `t` (C `nextafter(t, INFINITY)`, Python `math.nextafter`).
- Integers: counters are int64; uids, seeds and keys are uint64, and all uint64 arithmetic is mod 2^64.
- Exact sums: effective synaptic weights and noise kicks lie on the 1/8 grid, so sums of them are exact and
  order-free. Integer counters are order-free. Every other cross-cell float sum goes through the accountant.
- Integer-to-double conversions are written `(double) n`; a ratio such as `n_view / D` is a floating division.

## 3. Randomness: hash, draws and uids

```
splitmix64(x):  z = x + 0x9E3779B97F4A7C15
                z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
                z = (z ^ (z >> 27)) * 0x94D049BB133111EB
                return z ^ (z >> 31)
hash64(seed, stream, k1, ..., kn):  h = splitmix64(seed ^ splitmix64(stream)); for each key: h = splitmix64(h ^ key)
u01(h)       = double((h >> 11) | 1) * 2^-53                 # odd multiple of 2^-53, strictly inside (0, 1)
draw(...)    = u01(hash64(...))
normal(...)  = double(sum_{j=0..11} (hash64(..., j) >> 11)) * 2^-53 - 6.0
               # Irwin-Hall(12) - 6: the 12 terms are summed as uint64 (exact), converted once (round to
               # nearest even), so the result is exact, order-free and bounded in [-6, 6]; mean 0, variance 1
sitekey(a, b) = (uint64(uint32(a)) << 32) | uint32(b)        # two's complement of the int32 coordinates
```
Signed integer keys enter as their two's complement mod 2^64. Comparisons of `u01` against dyadic probabilities
(`p = 2^-j`) can never tie.

Uids. `EMPTY = 0`, and every real uid is odd.
- Initial cell `i` (the zygote is `i = 0`): `uid = hash64(seed, S_ZYG, i) | 1`.
- The daughter of mother `uid` from her claim number `div#` (0-based): `hash64(seed, S_UID, uid, div#) | 1`.

Streams (`spec.STREAMS`) and their keys. `seed` is the life seed. `sk` and `k` are the site key and the birth index
of a cell, `#` marks the cell's own counters (section 5.2):

| stream | id | keys | used for |
|---|---|---|---|
| S_ZYG | 1 | i | uid of initial cell i |
| S_UID | 2 | mother uid, div# | daughter uid |
| S_TAU | 3 | sk, k | tau_m mismatch (uniform) |
| S_CLK | 4 | sk, k | clock rate (normal) |
| S_PHASE | 5 | sk, k | first-tick phase (uniform) |
| S_DC | 6 | sk_from, sk_to, (k_from << 32) \| k_to | frozen contact delay of one directed contact (normal) |
| S_JIT | 7 | uid, spike#, d | spike-delay jitter |
| S_DROP | 8 | uid, spike#, d | panel: dropped contact event |
| S_TICK | 9 | uid, tick# | tick-period jitter |
| S_DIE | 10 | uid, tick# | apoptosis draw |
| S_DIV | 11 | uid, tick# | division draw |
| S_PLACE | 12 | uid, div#, e | placement noise for empty slot e |
| S_NOISE | 13 | uid, j | panel: j-th membrane-noise candidate time |
| S_NSIGN | 14 | uid, j | panel: sign of the j-th kick |
| S_KILL | 15 | uid | panel: kill selection |
| S_TIE | 16 | sk | heap tie key (`tie seed` instead of the life seed) |
| S_ORDER | 17 | window index, sk | window visit order (`order seed` instead of the life seed) |

Frozen physics (keyed by place and birth index) gives every genome in a generation the same physics at the same place,
and the same genome the same body on any fabric. Event draws are keyed by the cell's own counters, so a draw is a
property of the event, never of processing order.

## 4. Kernel interface: entry points and arrays

### 4.1 Build and loading
`src/life/build.py` compiles `kernel.c` with
`gcc -O3 -fopenmp -ffp-contract=off -fPIC -shared -std=c11 -o life_<key>.so kernel.c -lm`, where `<key>` is the
first 16 hex digits of the SHA-256 of the source text plus the flag string. The library is cached by that key
(default directory `~/.cache/cell-dev/life`) and loaded with `ctypes`. It must export the functions below with C
linkage. The caller checks `life_abi_version() == spec.ABI_VERSION` and `life_sizes()` against `spec.SIZES` before
the first run.

### 4.2 Entry points
```c
int32_t life_abi_version(void);
void    life_sizes(int32_t out[10]);   // abi, genome 809, program 119, world 41, ledger 35, hashes 4, knobs 21,
                                       // max_init 64, fate_i 6, fate_f 18   (spec.SIZES, in this order)
int32_t life_run(
    int32_t n_lives, int32_t threads,
    const int32_t *lat,          // [2 + 6*D]   lattice table (4.3)
    const double  *unit,         // [D][2]      unit vectors (4.3)
    int32_t n_genomes,           // G           rows of the genome table
    const double  *genomes,      // [G][809]    packed genome tables (4.4); may be NULL if every life is program mode
    int32_t n_programs,          // P           rows of the program table
    const double  *programs,     // [P][119]    program tables (4.5); may be NULL if no life is program mode
    const int32_t *genome_of,    // [n_lives]   row of the table each life's mode uses (programs or genomes)
    const int32_t *init_cells,   // [n_lives][64][3] explicit initial bodies (4.6); may be NULL
    const int32_t *n_init,       // [n_lives]   0 = one zygote at (0, 0); may be NULL (all 0)
    const double  *world,        // [n_lives][41] world vectors (4.7)
    const uint64_t *seeds,       // [n_lives][4]  life seed, tie seed, order seed, relabel salt (4.8)
    double   *ledger,            // [n_lives][35] out (4.9)
    uint64_t *hashes,            // [n_lives][4]  out (4.10)
    int64_t raster_cap, double *raster_t, uint64_t *raster_uid, int64_t *raster_n,   // [n_lives][cap] (4.11)
    int64_t fate_cap, int64_t *fate_i, double *fate_f, int64_t *fate_n);              // [n_lives][cap][6|18]
```
All arrays are C-contiguous, row-major, native endianness. Lives run in parallel with OpenMP
(`schedule(dynamic, 1)`, `num_threads(threads)`; `threads < 1` means 1). A capacity of 0 or a NULL pointer turns that
log off.

Return codes: `0` success; `-1` size or ABI mismatch, a NULL table that some life needs, `genome_of[i]` outside
`[0, P)` for a program-mode life or `[0, G)` for a GRN life (each table is bounded by its own row count, so a life
never depends on what else is in the batch), or a NaN or infinity in a table row that some life uses (4.4, 4.5);
`-2` invalid world vector (any rule of 4.7, `spec.validate_world`); `-3` allocation failure; `-4` invalid lattice
table or initial body (duplicate sites, `n_init > 64`, row index out of range). The kernel checks every life's
arguments before it runs any, so an argument error never leaves partial outputs. Per-life problems that are not
argument errors are reported in the status column. `build.run` raises `ValueError` for the same errors, and also
when `genome_of` is omitted and a table has neither 1 nor `n_lives` rows.

Test exports (used by `tests/test_life_*` to compare the C functions with `spec.py` bitwise):
```c
uint64_t life_hash64(uint64_t seed, uint64_t stream, int32_t n, const uint64_t *keys);
double   life_normal(uint64_t seed, uint64_t stream, int32_t n, const uint64_t *keys);
void     life_decode(const double y[21], double theta[21]);           // section 8
void     life_readout(const double gt[809], const double g[16], double y[21]);
```

### 4.3 Lattice table
`spec.lattice_tables(kind)` builds both arrays from the `src/lattice.py` helpers:
- `lat` int32 `[2 + 6D]`: `code` (0 hex, 1 square4, 2 square8), `D`, `off_a[D]`, `off_b[D]`, `back[D]`, `prev[D]`,
  `next[D]`, `rot[D]`.
  - Slot `d` points to the neighbour at `(a + off_a[d], b + off_b[d])`, in `lattice.offsets(kind)` order (hex
    axial `(1,0),(1,-1),(0,-1),(-1,0),(-1,1),(0,1)`; square4 `(1,0),(0,1),(-1,0),(0,-1)`; square8 adds
    `(1,1),(-1,1),(-1,-1),(1,-1)`).
  - `back[d]` is the neighbour's slot that points back (found by lookup; on square8 it is `2,3,0,1,6,7,4,5`). A
    message sent through slot `d` arrives at the receiver's slot `back[d]`.
  - `prev[d]` and `next[d]` are the clockwise and counter-clockwise angular neighbours of slot `d`
    (`lattice.cyclic_neighbours`).
  - `rot[d]` is the slot permutation of one counter-clockwise lattice rotation. It is used by tests only.
- `unit` float64 `[D][2]`: the unit vector of each slot in the plane (`lattice.unit_vectors`; hex `x = a + b/2`,
  `y = b*sqrt(3)/2`; square8 diagonals normalized). Both implementations read these numbers. Neither recomputes them.

### 4.4 Genome table (GRN mode)
The raw genome is float32 `[809]` with these fields (`spec.GENOME_FIELDS`; offsets `spec.GENOME_SLICES`):

| field | shape | offset | raw meaning | packed (float64) value |
|---|---|---|---|---|
| W | [16][23] | 0 | regulation weights, row = regulated gene | row k and column k (k < 16) zeroed if gene k is inactive |
| b | [16] | 368 | basal expression | 0 if inactive |
| lam | [16] | 384 | rate class x | `lambda = 2^-(1 + clip(rint(x + 3), 0, 6))`, 0 if inactive |
| s0 | [16] | 400 | maternal state x | `g0 = sigma(x)`, 0 if inactive |
| Q | [16] | 416 | partition vector | 0 if inactive |
| act | [16] | 432 | active bit | `1.0 if x > 0.5 else 0.0` |
| A | [21][16] | 448 | readout, column = gene | column k zeroed if inactive |
| a0 | [21] | 784 | readout bias | unchanged |
| Dm | [2] | 805 | packet-rate x | `D_m = (0.9 * sigma(x)) / (D * P_MAX)`, `P_MAX = 3.0`, D = lattice degree |
| km | [2] | 807 | decay x | `k_m = 0.005 + 0.3 * sigma(x)` |

`spec.pack_genomes(params, kind)` produces the packed table, float64 `[G][809]` with the same offsets, and turns
every `-0.0` into `+0.0`. The kernel never reads the raw genome. The packed table holds no NaN or infinity:
`pack_genomes` raises `ValueError` for a raw genome that holds one, and `life_run` returns -1 for a packed row that
holds one (a NaN readout would otherwise index the knob tables of section 8 out of range). An
inactive gene therefore has `g_k = 0` forever, whether or not the kernel skips it: its update is
`0 + 0 * (s - 0) = 0`, and all its outgoing weights are zero. Unit and block metadata (for crossover and mutation)
are in `spec.GENOME_FIELDS`; the kernel ignores them.

### 4.5 Program table (program mode)
Program mode replaces the readout `theta = decode(A.g + a0)` by a fixed program. It is used for the hand-built
references (R25-v1, the L0-L4 ladder) and for cell-layer tests. `spec.pack_program` builds float64 `[119]`:
- `[0, 105)`: five decoded phenotype rows of 21 knobs each, in knob order (section 8): `alone`, `contact`,
  `juvenile`, `rim`, `zygote`. Values are used as given (off-grid values allowed), except that `w_eff` is always
  `q8` of its formula.
- `[105, 119)`: `juv_ticks, nv_rim, zyg_row, flank_gate, p_div_lo, k_grow, timer_step, prune, k_keep, k_die,
  Dm0, Dm1, km0, km1` (`Dm` and `km` already decoded, as in 4.4).
Every entry must be finite (`pack_program` raises `ValueError`, and `life_run` returns -1). Semantics are in
section 7.5.

### 4.6 Initial body
If `n_init[i] = 0`, life i starts from one zygote at `(0, 0)` with the selector row. Otherwise `init_cells[i]` holds
`n_init[i]` rows `(a, b, row)`: initial cell j sits at `(a, b)` and gets uid index j. In program mode, `row >= 0`
fixes that cell's program row for its whole life (`-1` = selector). In GRN mode `row` is ignored, and every initial
cell starts from `g0`. All initial cells are born at `t0` (7.6).

### 4.7 World vector
float64 `[41]`, keys in `spec.WORLD_KEYS` order. `spec.pack_world` validates and packs it. Times marked (rel) are
relative to `t0`.

| # | key | v1 default | meaning |
|---|---|---|---|
| 0 | T | 1024 | life duration; integer |
| 1 | t0 | 0 | start time (integer); test T6 shifts it |
| 2 | t_open | 0 | (rel) ledger opens; earlier records are not counted (section 9.3) |
| 3 | t_fork | 0 | (rel) `fork_flags` apply to events at `t >= t0 + t_fork` |
| 4 | flags | 0 | base flag bits (section 12) |
| 5 | fork_flags | 0 | flag bits added from `t_fork` |
| 6 | d_min | 0.5 | causality floor |
| 7 | d0 | 1.0 | median contact delay |
| 8 | delay_sd | 0.1 | lognormal sigma of frozen contact delays |
| 9 | jit | 0.1 | per-event delay jitter (multiplicative, uniform) |
| 10 | tau_mis | 0.05 | frozen tau_m mismatch (uniform +-) |
| 11 | P0 | 2.0 | nominal clock period |
| 12 | clock_sd | 0.05 | frozen clock-rate spread (log scale) |
| 13 | tick_jit | 0.1 | per-tick period jitter |
| 14 | tau_z | 2.5 | twitch decay |
| 15 | th | 0.6 | systole threshold |
| 16 | th_lo | 0.25 | diastole threshold |
| 17 | tau_R | 6.0 | refill time constant |
| 18 | tau_e | 0.5 | ejection time constant |
| 19 | h_inc | 1.0 | income per unit of ejected fill per cell |
| 20-25 | c_live, c_spike, c_tw, c_msg, c_div, c_sec | 0.02, 0.004, 0.004, 0.001, 0.5, 0.004 | per-action costs (`spec.COSTS`) |
| 26 | n_max | 1024 | live-cell guard |
| 27 | e_max | 5e6 | event guard |
| 28 | fabric_R | 0 | 0 = sparse unbounded fabric; R > 0 = dense disk `lattice.in_disk(kind, a, b, R)` |
| 29 | oracle_cap | 0 | measurement-only size cap (heap scheduler only); 0 = off |
| 30 | window_h | 0 | 0 = heap scheduler; `2^-k <= d_min` = window scheduler |
| 31 | drop_p | 0 | panel: probability that a contact event is dropped |
| 32 | noise_rate | 0 | panel: membrane-noise kicks per cell per unit |
| 33 | kill_t | -1 | (rel) panel: kill time (< 0 = off) |
| 34 | kill_frac | 0 | panel: fraction killed at kill_t |
| 35 | stuck_t | -1 | (rel) panel: the occupant of (stuck_a, stuck_b) becomes stuck-firing (< 0 = off) |
| 36-37 | stuck_a, stuck_b | 0 | panel: stuck site |
| 38-40 | kill_rate, wound_rate, drift_tau | 0 | reserved (v2, v3); must be 0 in ABI v1 |

The lattice kind is a property of the call (the lattice table), not of the world vector.

World rules (`spec.validate_world`; the kernel's `world_ok` returns -2 for a vector that breaks any of them):
- every entry is finite, and the reserved entries 38-40 are 0;
- T and t0 are integers with `0 < T <= 2^30` and `|t0| <= 2^30`, so every time in a life is resolved to `2^-21` or
  finer; n_max, e_max, fabric_R, oracle_cap, stuck_a and stuck_b are integers;
- `0 <= t_open < T`;
- flags and fork_flags hold known bits only, never integer_twin, and fork_flags holds no base-only flag (12);
- window_h is 0 or `2^-k <= d_min` with `k >= 1`, and oracle_cap is 0 under the window scheduler (11.3);
- `d_min >= 2^-10` and `d0 > 0`;
- jit, tau_mis and tick_jit lie in `[0, 1)`; delay_sd and clock_sd lie in `[0, 1]`;
- `P0 > 0`, and the shortest tick period the clock law allows, `P0 * exp(-6 * clock_sd) * (1 - tick_jit)` (frozen
  normals lie in [-6, 6], section 3; `spec.min_tick_period`), is at least `2^-10`. These bounds are applied as
  written under lockstep too, although lockstep ignores clock_sd and tick_jit;
- tau_z, tau_R and tau_e are positive; `0 <= th_lo < th < 1`; h_inc and the six costs are non-negative;
- `1 <= n_max <= 2^20`, `e_max >= 0`, fabric_R and oracle_cap lie in `[0, 2^30]`, and `|stuck_a|, |stuck_b| <= 2^30`;
- drop_p and kill_frac lie in `[0, 1]`, and `0 <= noise_rate <= 1024`.

So every message delay and every tick period is at least `2^-10`, time always advances (6.3), and the lumen of 9.2
stays finite. (Before these rules, `P0 = 0` put every tick at one instant and `life_run` never returned, and
`tau_z = 0` gave `F = NaN` with status 0.) In GRN mode the knob grids add `t_ref >= 0.5` and `tau_m >= 0.95`, so a
life always terminates. Program rows are used as given (4.5), and their knob ranges are the caller's responsibility.

### 4.8 Seeds
uint64 `[n_lives][4]`:
- `seed`: keys every draw of section 3.
- `tie seed`: permutes heap ties (section 11.1).
- `order seed`: the window visit order (section 11.2).
- `relabel salt`: lets an implementation permute its internal cell slots, hash-map layout and allocation order (test
  T5).
Only `seed` may change results.

### 4.9 Ledger
float64 `[n_lives][35]`, columns in `spec.LEDGER` order. "Counted" columns include only records with
`t >= t0 + t_open`. The other columns cover the whole life.

| # | column | counted | definition |
|---|---|---|---|
| 0 | income | yes | integral of `h_inc * n * max(0, -dR/dt)` (9.2) |
| 1 | live_time | yes | integral of n dt (cell-time units) |
| 2 | sec_int | yes | integral of the sum of sec over live cells, dt |
| 3 | spikes | yes | FIRE count |
| 4 | kappa_sum | yes | sum of kappa over spikes |
| 5 | contact_events | yes | sum of n_out over spikes (live slots in view x emitting channels) |
| 6 | claims | yes | CLAIM count (each charged c_div) |
| 7 | births | yes | successful claims (initial cells excluded) |
| 8 | rejects | yes | claims rejected because the site was occupied (or lost a same-instant tie) |
| 9 | rejects_wall | yes | claims to sites outside a dense fabric |
| 10 | deaths | yes | apoptosis and prune deaths |
| 11 | kills | yes | panel kills |
| 12 | cost | yes | running sum of every charge in canonical order (9.3) |
| 13 | guard_charge | - | `c_live * n_max * (t1 - t_end)` if a guard tripped, else 0 |
| 14 | net | - | `income - colcost - guard_charge` (9.5) |
| 15 | F | - | `net / (T - t_open)` |
| 16 | n_end | - | live cells at t_end |
| 17 | n_peak | - | max live cells after any time group |
| 18 | t_end | - | end of the life: t1, or the guard time |
| 19 | status | - | bit field (4.12) |
| 20 | events | - | guard event counter at t_end (section 10) |
| 21 | beats | yes | upward crossings of P through th |
| 22 | P_int | yes | integral of P dt |
| 23 | arrivals | yes | ARRIVAL events delivered to their target |
| 24 | arrivals_dropped | yes | ARRIVAL events whose target uid was gone |
| 25 | packets | yes | morphogen packets sent |
| 26 | morph_secreted | - | sum of sec_m * dt |
| 27 | morph_decayed | - | mass removed by decay |
| 28 | morph_lost | - | content of dying cells plus packets that found their target gone |
| 29 | morph_content_end | - | morphogen in live cells (content plus unconsumed inbox) at t_end |
| 30 | morph_inflight_end | - | packets sent before t_end and arriving at or after it |
| 31 | chem_clamps | yes | ticks at which the 0.9 shipping clamp bound |
| 32 | last_birth | - | time of the last successful claim (t0 if none) |
| 33 | ticks | yes | TICKs executed by live cells |
| 34 | t_ext | - | extinction time, or -1 |

Morphogen conservation: `morph_secreted = morph_decayed + morph_lost + morph_content_end + morph_inflight_end`, up to
float rounding (the tests use a relative tolerance of 1e-12).

### 4.10 Hashes
uint64 `[n_lives][4]`: `all, spikes, fate, chem` (section 9.6). Each family starts at
`HASH_INIT = 0x243F6A8885A308D3`.

### 4.11 Raster and fate log
- Raster: one entry per spike, written by the accountant in canonical order: `raster_t[i][j] = t`,
  `raster_uid[i][j] = uid`. `raster_n[i]` is the total number of spikes in the life, which may exceed the capacity.
  Only the first `raster_cap` entries are stored, and overflow sets a status bit.
- Fate log: one entry per birth (including initial cells), death and rejected claim, in canonical order.
  - `fate_i[i][j][6] = kind, uid, mother, a, b, aux`. Kinds: 1 birth, 2 death, 3 reject. `aux` is the birth index k
    for a birth, the cause for a death (1 apoptosis, 2 prune, 3 kill), and 0 (occupied) or 1 (wall) for a reject.
  - `fate_f[i][j][18] = t, age, g[16]`: `g` at birth or at death (zeros for rejects and in program mode); `age` is
    `t - t_birth` for deaths, 0 otherwise.
  - For a reject, `uid` is the would-be daughter, `mother` is the claimant, and `(a, b)` is the target site.

### 4.12 Status bits (ledger column 19, an integer stored as a double)
`1` extinct; `2` guard_cells; `4` guard_events; `8` raster_overflow; `16` fate_overflow; `32` chem_clamp (at least
once); `64` ledger_mismatch (`|cost - colcost| > 1e-9 * max(1, |colcost|)`); `128` capacity (an implementation limit
was reached; the life is invalid and must not be used); `256` wall (at least one wall reject).

## 5. State

### 5.1 Site (persistent: it outlives its occupants)
- `sk` (site key) and `(a, b)`.
- `births`: the number of births so far at this site. A newborn's birth index is `k = births` before the increment.
- `occupant`: a live cell or none.
- Event queue.
A site that has never been touched has `births = 0` and no occupant. Implementations may create site records lazily.

### 5.2 Cell
- Identity: `uid`, `alive`, `t_birth`, `k` (birth index), `initial index` (or -1), `fixed_row` (program mode,
  initial cells).
- Counters, all starting at 0: `spike#`, `tick#`, `div#`.
- View: for each slot `d`, `view[d]` (a uid or EMPTY) and `dc[d]` (frozen out-delay, valid while `view[d] != EMPTY`).
  `inc[d][2]` holds the concentration carried by the last packet consumed from slot d.
- Membrane: `v_a` (Q10 value), `t_a`, `t_r` (end of refractory), `ver` (uint32 or wider, incremented by every
  PREDICT).
- Traces: `f`, `r[2]`, anchor `t_tr`.
- Twitch: `z`, anchor `t_z`.
- Genes and chemistry: `g[16]`, `m[2]`, inbox (packets that have arrived: `t_arr`, sender uid, slot, `amt[2]`,
  `conc[2]`).
- Phenotype: `theta[21]`, the effective membrane time constant `tau = theta.tau_m * taumis`, and `w_eff[D][2]`.
- Frozen physics: `taumis`, `P_n`.
- Clock: `t_prev` (last tick time, or `t_birth`).
- Division: `claim_pending` (0 or 1).
- Program mode: `timer` and `timer_birth`.

### 5.3 Life (owned by the accountant)
World `(A, R, t_w, above)` (9.2); `n` (live cells); `inflight` (claims sent and not yet resolved); ledger columns;
hashes; logs; `extinct`; `t_end`.

## 6. Events, batches and the causality contract

### 6.1 Kinds
Every event has a time `t`, a target site, a kind and a payload. Cross-site events (messages) are created by a handler
at time `t_s` and arrive at `t_s + delay`, with `delay >= d_min`.

| group (order) | event | addressed to | delay | payload |
|---|---|---|---|---|
| 0 CLAIM | CLAIM | site | d_min | daughter uid, mother uid, `bslot` (the target's slot pointing at the mother), daughter `g[16]` or `timer` |
| 1 NOTICE | BORN | site occupant | d_min | sender uid, sender k |
| 1 NOTICE | PRESENT | uid | d_min | sender uid, sender k |
| 1 NOTICE | ACK | uid (mother) | d_min | daughter uid, daughter k |
| 1 NOTICE | REJECT | uid (mother) | d_min | none |
| 1 NOTICE | DIED | site occupant | d_min | sender uid |
| 2 PACKET | PACKET | uid | d_min | sender uid, `amt[2]`, `conc[2]` |
| 3 MEMBRANE | ARRIVAL | uid | `max(d_min, ...)` (7.3) | mask (bit c = channel c) |
| 3 MEMBRANE | THRESHOLD | self (uid, ver) | - | - |
| 3 MEMBRANE | NOISE | self (uid) | - | kick +-1/8 (panel) |
| 4 TICK | TICK | self (uid) | - | - |
| 5 EXO | KILL, STUCK | self (uid) | - | - (panel) |

Every message also carries its receiver slot `back[d]`, where `d` is the sender's slot it left through. "Addressed to
uid" means the event acts only if that uid is the site's live occupant at `t-`. Otherwise it is dropped: arrivals
count in `arrivals_dropped`, packets are lost (R_LOST), notices vanish. "Addressed to the site occupant" means
whoever is the live occupant at `t-`, if anyone. Self events of a cell that has died or been replaced are stale, as
is a THRESHOLD whose `ver` is no longer the cell's `ver`; stale events are ignored.

### 6.2 The batch
All events at one site with exactly the same `t` form one batch. A batch is processed in this order, and everything
outside the cell is read as a left limit (the site's state at `t-`):

0. **CLAIM**: arbitration against the occupancy at `t-` (7.6). If the site was empty at `t-` and a claim wins, the
   newborn appears at t. The rest of the batch is still evaluated against the `t-` occupant (none), so the newborn
   receives nothing from its own birth batch.
1. **NOTICE**: if the `t-` occupant is alive, its notices are applied in order of (receiver slot, then BORN, PRESENT,
   ACK, REJECT, DIED) (7.7).
2. **PACKET**: each packet goes into the occupant's inbox, or is lost.
3. **MEMBRANE**: all ARRIVALs, NOISE kicks and the current THRESHOLD (if any) form one membrane step (7.2) with one
   summed input and one threshold test.
4. **TICK** (7.4 / 7.5).
5. **EXO**: KILL, then STUCK (7.9).

Within a group, events whose order matters are sorted by the keys above. The other groups are order-free: arrivals
sum exactly, claims are sorted by daughter uid, and packets are consumed later in `(t_arr, sender uid)` order.

### 6.3 Causality contract
- Every message delay is `>= d_min`.
- Self events (THRESHOLD, TICK, NOISE, KILL, STUCK) can be created inside a batch only for a time strictly later than
  the batch, by construction: `t* > t0` in PREDICT (7.1); tick periods are at least `2^-10` (world rules, 4.7),
  and every time in a life is resolved to `2^-21`; and a first tick or noise kick that would round to the batch time
  is moved to `nextup(t)`.
- The accountant reads cells only through records stamped with the batch time, and in v1 nothing flows back from the
  world to cells.
Hence a site's batch at t depends only on events created before `t - d_min` elsewhere, and on its own past.

### 6.4 Ties
- Exact time ties between different sites never interact (6.3), so their processing order is free (tie seed, order
  seed).
- Ties within one site are resolved by the batch order of 6.2.
- Ties between claims are resolved by the lowest daughter uid.
- Ties between records are resolved by the canonical order (9.1).

## 7. Handlers

Notation: `X` is the occupant being processed, `t` the batch time, `F(name)` is true when flag `name` is active at t
(section 12), `theta.knob` is the current phenotype, `tau = theta.tau_m * taumis`, and `D` is the lattice degree.
"Emit R_x" appends a record (section 9) with the next `seq` of this site batch. "Send" creates a message through a
slot: it travels to `(a, b) + off[d]` and arrives at slot `back[d]`.

### 7.1 Membrane between events, and PREDICT
```
anchor:   t0 = max(t_a, t_r);   v0 = (t_a >= t_r) ? v_a : 0.0
vnow(t):  t < t_r ? 0.0 : theta.b + (v0 - theta.b) * exp(-(t - t0) / tau)
PREDICT:  ver += 1
          if theta.b > 1.0 and v0 < 1.0:
              schedule THRESHOLD(uid, ver) at t0 + tau * log((theta.b - v0) / (theta.b - 1.0))
traces to t:  e = exp(-(t - t_tr) / theta.tau_tr); f = f * e; r[0] = r[0] * e; r[1] = r[1] * e; t_tr = t
```
PREDICT is called after every membrane step that does not fire, after every FIRE, at every tick (after the phenotype
update) and at birth. A predicted crossing is always strictly after `t0`, and `t0` is never before the current batch
time. Traces are re-anchored only at: batches with at least one delivered ARRIVAL, FIRE, and TICK (and set to 0 at
birth). The twitch is re-anchored only at FIRE with `kappa > 0`. The membrane is re-anchored only at the membrane
step, FIRE, the tick re-anchor and birth. Re-anchoring at other times would change the rounding, so it is forbidden.

### 7.2 Membrane step (batch group 3)
Let `Arr` be the delivered ARRIVALs, `Kick` the NOISE kicks, and `thr` true iff a current THRESHOLD is in the batch.
The step runs if any of the three is present.
```
if Arr is nonempty:
    traces to t;  r[c] = r[c] + count_c   for c = 0, 1   (count_c = arrivals whose mask has bit c)
if t < t_r: return                                       # refractory: input lost, traces already counted
S = sum over Arr of sum_c bit_c(mask) * w_eff[slot][c]  +  sum over Kick of kick      (exact)
v = (thr ? 1.0 : vnow(t)) + S
v_a = q10(v); t_a = t
if v_a >= 1.0: FIRE(t) else PREDICT
```
A current THRESHOLD contributes exactly 1.0, so a crossing predicted for this instant is subsumed. It fires unless
same-instant inputs pull the sum below 1. Arrivals received while refractory still count in the traces.
`arrivals += |Arr|` and `arrivals_dropped += (dropped arrivals)` are integer counters (counted if
`t >= t0 + t_open`).

### 7.3 FIRE(t)
```
v_a = 0.0; t_a = t; t_r = t + theta.t_ref
traces to t; f = f + 1
spike# += 1
n_live = #{d : view[d] != EMPTY};  n_ch = theta.emit0 + theta.emit1;  n_out = n_live * n_ch
if n_ch > 0 and not F(contacts_off):
    for d = 0 .. D-1 with view[d] != EMPTY:
        if drop_p > 0 and draw(seed, S_DROP, uid, spike#, d) < drop_p: continue
        u = draw(seed, S_JIT, uid, spike#, d)
        dl = dc[d] * (1.0 + jit * (2.0 * u - 1.0)) + theta.delta
        if dl < d_min: dl = d_min
        send ARRIVAL(target view[d], mask = emit0 | emit1 << 1) through d, at t + dl
dz = 0.0
if theta.kappa > 0:
    zt = z * exp(-(t - t_z) / tau_z);  zn = zt + theta.kappa;  if zn > 1.0: zn = 1.0
    dz = zn - zt;  z = zn;  t_z = t
emit R_SPIKE(uid, kappa, n_out, dz)
PREDICT
```
Costs are charged by the accountant on R_SPIKE, including when `contacts_off` or drops suppress delivery. A spike
never fails in v1. `spike#` is incremented before it keys the draws, so a cell's first spike uses `spike# = 1`.
An emit knob counts as on when it is nonzero (decoded values are exactly 0 or 1; a program row may hold others), so
`n_ch` is the number of nonzero emit knobs and `mask` has bit c set iff `emit_c != 0`.

### 7.4 TICK(t), GRN mode
`dt = t - t_prev`. `theta_prev` is theta as it was before this tick (in force on `[t_prev, t)`).
```
1. inbox: for each packet in increasing (t_arr, sender uid):
       m[0] = m[0] + amt[0]; m[1] = m[1] + amt[1]
       if view[slot] == sender uid: inc[slot][0] = conc[0]; inc[slot][1] = conc[1]        # 15.9
   (the inbox is now empty)
2. sp0 = theta_prev.sec0; sp1 = theta_prev.sec1
   emit R_TICK(uid, t_prev, sp0 + sp1)
   ticks += 1 (counted)
3. traces to t
   n_view = #{d : view[d] != EMPTY}
   flank(e) = [view[prev[e]] != EMPTY] + [view[next[e]] != EMPTY]
   flank_best = max over e with view[e] == EMPTY of flank(e); 0 if no slot is empty
   x[0..15] = g;  x[16+i] = m[i] / (1.0 + m[i]);  x[18] = f / theta_prev.tau_tr;  x[19+c] = r[c] / theta_prev.tau_tr
   x[21] = (double) n_view / (double) D;  x[22] = (double) flank_best / 2.0
   if F(genes_blind): x[18..22] = 0.0
4. if not (F(identity_clamp) or F(freeze)):
       for k = 0..15: p = b[k]; for j = 0..22: p = p + W[k][j] * x[j];  s[k] = sigma(p)
       for k = 0..15: g[k] = g[k] + lam[k] * (s[k] - g[k])          # every s[k] from the same, old x
5. if t >= t_r:
       v_a = q10(vnow(t)); t_a = t                                   # with theta_prev
       if v_a >= 1.0: FIRE(t)                                        # with theta_prev
   if not (F(freeze) or F(pheno_fixed)): theta = decode(readout(g))  # section 8; tau = theta.tau_m * taumis
   if not F(freeze): recompute w_eff and s_d (section 8)
   PREDICT
6. if not (F(apoptosis_off) or F(freeze)) and theta.p_die > 0 and draw(seed, S_DIE, uid, tick#) < theta.p_die:
       APOPTOSIS(t, cause 1); return                                 # no next tick
7. md[i] = m[i] * exp(-km[i] * dt);  dec = (m[0] - md[0]) + (m[1] - md[1])
   m[i] = md[i] + sp_i * dt;          sec = sp0 * dt + sp1 * dt
   clamp = 0
   if n_view > 0 and not F(chem_off):
       for i = 0, 1:  q[i] = Dm[i] * dt;  if n_view * q[i] > 0.9: q[i] = 0.9 / n_view; clamp = 1
                      amt[i] = m[i] * q[i]; conc[i] = m[i]
       for d = 0 .. D-1 with view[d] != EMPTY:
           send PACKET(target view[d], amt, conc) through d, at t + d_min
           emit R_PACKET(uid, view[d], sitekey((a, b) + off[d]), amt)
       for i = 0, 1:  m[i] = m[i] - n_view * amt[i]
   emit R_CHEM(sec, dec, clamp)
8. if not (F(division_off) or F(freeze)) and claim_pending == 0 and some view[e] == EMPTY
      and theta.p_div > 0 and draw(seed, S_DIV, uid, tick#) < theta.p_div
      and (oracle_cap == 0 or cap_count < oracle_cap):        # heap only; cap_count = (n_alive + n_inflight)(t-), 11.3
       px = 0.0; py = 0.0; for d = 0..D-1: px = px + s_d * unit[d][0]; py = py + s_d * unit[d][1]
       vx = px - theta.chi * py;  vy = py + theta.chi * px                    # p + chi * J p, J = +90 degrees
       for e = 0..D-1 with view[e] == EMPTY:
           score(e) = unit[e][0] * vx + unit[e][1] * vy + theta.phi * flank(e)
                      + 1e-3 * draw(seed, S_PLACE, uid, div#, e)
       d* = the first e with the largest score (strict > while scanning e upward)
       daughter = hash64(seed, S_UID, uid, div#) | 1
       if F(identity_clamp): for k: gd[k] = g[k]                         # g frozen: no partition (15.31)
       else: for k: qk = theta.asym * Q[k];  gd[k] = clip(g[k] + qk, 0, 1);  g[k] = clip(g[k] - qk, 0, 1)   # 15.29
       send CLAIM(daughter, uid, bslot = back[d*], gd) through d*, at t + d_min
       emit R_CLAIM(uid, daughter, target sk)
       div# += 1;  claim_pending = 1
9. per = P_n * (1.0 + tick_jit * (2.0 * draw(seed, S_TICK, uid, tick#) - 1.0))
   schedule TICK at t + per;  tick# += 1;  t_prev = t
```
- Steps 6 and 8 use `tick#` before its increment (0 at a cell's first tick).
- `n_view * q[i]` and `n_view * amt[i]` multiply by `(double) n_view`.
- `s_d` comes from step 5, and `flank` from step 3; both describe the view at this tick.
- `cap_count` in step 8 is `n_alive + n_inflight` at the left limit `t-` of the tick's time (section 11.3): every
  claimer at one instant sees the same count, whatever the tie order.

### 7.5 Program mode (flag `program_mode`)
The handlers are those of GRN mode, with these differences:
- Genes: step 3 does not build x, and step 4 is replaced by `timer = timer + timer_step` (skipped under
  `identity_clamp` or `freeze`, like the gene update). Claims carry `timer` instead of genes, and the partition is
  skipped (g stays 0).
- Phenotype: step 5 (and BIRTH) sets `theta = row(selector)` instead of decoding, unless `pheno_fixed` or `freeze`
  applies:
  ```
  if the cell has a fixed row (initial cell with row >= 0): that row
  elif zyg_row != 0 and the cell is initial cell 0:           "zygote"
  elif n_view == 0:                                           "alone"
  elif tick# < juv_ticks:                                     "juvenile"      (tick# before its increment)
  elif nv_rim > 0 and n_view < nv_rim:                        "rim"
  else:                                                       "contact"
  ```
  At birth `n_view = 0` and `tick# = 0`.
- Death (step 6): first, if `prune != 0` and `timer_birth >= k_keep` and `timer >= k_die`: APOPTOSIS(t, cause 2).
  Otherwise the `theta.p_die` draw applies as in GRN mode. Both are skipped under `apoptosis_off` or `freeze`.
- Division (step 8): `p = theta.p_div`; if `flank_gate > 0` and `flank_best < flank_gate`, `p = p_div_lo`. Division
  requires `p > 0`, `timer <= k_grow` and `draw(seed, S_DIV, uid, tick#) < p`. The other conditions and the placement
  are unchanged. The daughter gets `timer = timer_birth =` the mother's timer after step 4.
- Chemistry uses the program's `Dm` and `km`.
- An initial cell starts with `timer = timer_birth = 0`.

Example: R25-v1 is `contact = theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1, p_div=0.5,
phi=2)`, `alone = theta(b=1.875, tau_m=8, t_ref=2, kappa=1)` (with the same p_div and phi), `juvenile` = contact with
`emit0 = 0`, and `juv_ticks = 10, flank_gate = 2, p_div_lo = 1/16` (bell3 used `0.5 * 0.1 = 0.05`).

### 7.6 CLAIM arbitration (batch group 0) and BIRTH
```
exists   = (fabric_R == 0) or lattice.in_disk(kind, a, b, fabric_R)
occupied = the site has a live occupant at t-
for the claims of this batch in increasing daughter uid:
    if not exists:                          result = 2 (wall)
    elif occupied or a winner was chosen:   result = 1 (reject)
    else:                                   result = 0 (birth); winner = this claim
    emit R_RESOLVE(daughter, mother, result)
    if result == 0: BIRTH(t, daughter, mother, bslot, genes or timer)
    else: send REJECT(target mother) through bslot, at t + d_min
```
The mother's c_div was charged on R_CLAIM, so it is lost on a reject.

```
BIRTH(t, uid, mother, bslot, payload):          # also used for initial cells (mother = 0, no ACK)
    k = site.births; site.births += 1
    if F(lockstep): taumis = 1.0; P_n = P0
    else: taumis = 1.0 + tau_mis * (2.0 * draw(seed, S_TAU, sk, k) - 1.0)
          P_n    = P0 * exp(clock_sd * normal(seed, S_CLK, sk, k))
    U = draw(seed, S_PHASE, sk, k)
    reset: view = EMPTY, inc = 0, m = 0, inbox empty, counters 0, claim_pending = 0
           v_a = 0.0; t_a = t; t_r = t; f = r = 0.0; t_tr = t; z = 0.0; t_z = t; t_prev = t; t_birth = t
    g = payload genes (GRN; g0 for initial cells), or timer = timer_birth = payload (program mode)
    theta = decode(readout(g)) or row(selector); w_eff and s_d with every slot empty (s_d = 0)
    emit R_BIRTH(uid, mother, k, initial)
    PREDICT
    t1 = F(lockstep) ? t0 + P0 * (floor((t - t0) / P0) + 1.0) : t + U * P_n;   if t1 <= t: t1 = nextup(t)
    schedule TICK at t1
    panel self events (7.9)
    for d = 0..D-1: send BORN(uid, k) through d, at t + d_min
    if mother != 0: send ACK(target mother; uid, k) through bslot, at t + d_min
```
Initial cell j has `uid = hash64(seed, S_ZYG, j) | 1`. All initial cells are born at `t0`, each birth being its
site's batch at `t0`, so their records follow the canonical order like any others.

### 7.7 Notices (batch group 1)
Let `d` be the receiver slot, and `nb = (a, b) + off[d]` the sender's site.
```
DC(k_nb) = F(lockstep) ? d0 : d0 * exp(delay_sd * normal(seed, S_DC, sk, sitekey(nb), (k << 32) | k_nb))
BORN(u', k'):     view[d] = u'; dc[d] = DC(k'); send PRESENT(target u'; uid, k) through d, at t + d_min
PRESENT(u', k'):  (target must be this uid) view[d] = u'; dc[d] = DC(k')
ACK(u', k'):      (target must be this uid) claim_pending = 0; view[d] = u'; dc[d] = DC(k')
REJECT:           (target must be this uid) claim_pending = 0
DIED(u'):         view[d] = EMPTY; inc[d][0] = inc[d][1] = 0.0
```
Here `sk` and `k` are the receiver's. Recomputing `DC` for a contact that is already known gives the same value.
All notices from one site travel with the same delay, so they arrive in the order they were sent. DIED is
unconditional, because no newer notice from that site can precede it. A newborn knows each neighbour from that
neighbour's PRESENT reply at `t_birth + 2 d_min`. A neighbour knows the newborn from BORN at `t_birth + d_min`.

### 7.8 APOPTOSIS(t, cause) and KILL
```
zt = z * exp(-(t - t_z) / tau_z)
content = m[0] + m[1]; then for each inbox packet in (t_arr, sender uid) order: content = content + amt[0] + amt[1]
emit R_DEATH(uid, cause, zt, content, t - t_birth, g)
the cell dies: the site is empty from t on (claims at t were already rejected by the left-limit rule)
for d = 0..D-1: send DIED(uid) through d, at t + d_min
```
- Pending self events become stale.
- Messages in flight to this uid are dropped or lost when they arrive.
- A pending claim still lands, and the ACK or REJECT addressed to the dead mother is dropped.
- After a death inside TICK step 6, the inbox is already empty (step 1).

### 7.9 Panel perturbations (robustness panel; all off in BELL-1 v1)
- **drop_p**: in FIRE (7.3). The contact event is still charged.
- **noise_rate** (> 0): at birth, `tn = t_birth - log(draw(seed, S_NOISE, uid, 0)) / noise_rate` and `j = 0`. Each
  NOISE event at `tn` is a kick `+1/8` if `draw(seed, S_NSIGN, uid, j) >= 0.5`, else `-1/8`, applied in the membrane
  step. It is not counted in the traces. Then `j += 1` and
  `tn = tn - log(draw(seed, S_NOISE, uid, j)) / noise_rate`, with `tn = nextup(previous)` if it would not advance.
- **kill_t** (>= 0): a cell born before `t0 + kill_t` schedules KILL at `t0 + kill_t`. At KILL, if alive and
  `draw(seed, S_KILL, uid) < kill_frac`: emit `R_TICK(uid, t_prev, theta.sec0 + theta.sec1)`, which charges the
  living and secretion cost of `[t_prev, t)` like the closing R_TICK of 9.5 (it is hashed like any R_TICK and does
  not count in `ticks`), then APOPTOSIS(t, cause 3). See 15.26.
- **stuck_t** (>= 0): a cell born at `(stuck_a, stuck_b)` before `t0 + stuck_t` schedules STUCK at `t0 + stuck_t`.
  At STUCK, the membrane is re-anchored as in TICK step 5 (re-anchor, and FIRE if it reaches 1). Then the cell is
  stuck for life: now and after every later phenotype update, `theta.b = 2, theta.tau_m = 1, theta.t_ref = 0.5` and
  `w_eff = 0` (it fires tonically and ignores input), followed by PREDICT.

## 8. Phenotype decode and derived quantities

`readout(g)`: `y[p] = a0[p]`, then `y[p] = y[p] + A[p][k] * g[k]` for `k = 0..15` in order.
`decode(y)` (`spec.decode_knobs`, and `life_decode` in C):

| row | knob | decode |
|---|---|---|
| 0-1 | w0, w1 | `q8(y)` |
| 2 | b | `q8(y)` |
| 3 | tau_m | `TAU_M[int(clip(rint(y + 2), 0, 4))]`, `TAU_M = 1, 2, 4, 8, 16` |
| 4 | t_ref | `0.5 * clip(rint(2y + 4), 1, 8)` |
| 5-6 | emit0, emit1 | `y > 0 ? 1.0 : 0.0` |
| 7 | delta | `DELTA[L(y)]`, `DELTA = 0, 0.5, 1, 2` |
| 8 | kappa | `KAPPA[L(y)]`, `KAPPA = 0, 1/4, 1/2, 1` |
| 9 | p_div | `k = int(clip(rint(4y), 0, 8))`; `k == 0 ? 0 : 2^(k-8)` |
| 10 | asym | `sigma(y)` |
| 11 | p_die | as p_div |
| 12 | phi | `PHI[L(y)]`, `PHI = 0, 0.5, 1, 2` |
| 13-14 | sec0, sec1 | `0.5 * sigma(y)` |
| 15-16 | pol0, pol1 | `q8(2 * tanh(y))` |
| 17 | tau_tr | `TAU_TR[int(clip(rint(y + 1.5), 0, 3))]`, `TAU_TR = 2, 4, 8, 16` |
| 18-19 | a0, a1 | `q8(y)` |
| 20 | chi | `q8(y)` |

`L(y) = int(clip(rint(2y), 0, 3))`. `int()` truncates toward zero, which is exact here because its argument is an
integer-valued double; `-0.0` becomes 0. A valid table never yields a NaN `y` (4.4), but `kernel.c` computes every
table index as `x >= 0 ? (x < hi ? int(x) : hi) : 0`, which equals `int(clip(x, 0, hi))` for every non-NaN `x` and
maps NaN to index 0, so no input can read outside a knob table. `spec.decode_knobs` raises on NaN instead.

Derived at every phenotype update:
```
for d: s_d = 0.0 if view[d] == EMPTY
       else theta.pol0 * (inc[d][0] - m[0]) + theta.pol1 * (inc[d][1] - m[1])
smax = max over d of |s_d|   (0.0 if all are 0)
for d, c: shat = s_d / (smax + 1e-6);  w_eff[d][c] = q8(theta.w_c * (1.0 + theta.a_c * shat))
```
`m` and `inc` are the values after TICK step 1. Slots not in the view (for example a neighbour the cell has not
heard from yet, whose spikes can arrive up to `d_min` before its PRESENT reply) get `shat = 0`, so their weight is
`q8(w_c)`. With `a = 0`, `w_eff = q8(w_c * 1.0) = w_c` exactly: isotropic, bitwise.

## 9. The accountant: records, world, ledger, logs, hashes

### 9.1 Records and canonical order
A record is `(t, sk, seq, kind, payload)`, where `seq` is the record's index within its site batch. The accountant
consumes records in increasing `(t, sk as uint64, seq)` and processes each **time group** (all records with one t)
completely before the next. After each time group it updates `n_peak = max(n_peak, n)` and checks extinction
(section 10). Every scheduler produces the same records with the same keys, so the accountant's arithmetic is
identical.

| record | payload | accountant action (counted parts only if `t >= t0 + t_open`) |
|---|---|---|
| R_BIRTH | uid, mother, k, initial, g | world_adv(t); `n += 1`; if not initial: `births += 1`, `last_birth = t`; fate log |
| R_SPIKE | uid, kappa, n_out, dz | counted: `spikes += 1; kappa_sum += kappa; contact_events += n_out; cost = cost + c_spike; cost = cost + c_tw * kappa; cost = cost + c_msg * n_out`. If kappa > 0: world_adv(t); `A = A + dz`; if `above == 0` and `A / n > th`: `above = 1` and (counted) `beats += 1`. Raster |
| R_TICK | uid, t_prev, sp (TICK step 2; also at a KILL, 7.9) | if `t > t_open_abs`: `dl = t - max(t_prev, t_open_abs)`; `live_time += dl; sec_int += sp * dl; cost = cost + c_live * dl; cost = cost + c_sec * (sp * dl)` |
| R_CHEM | sec, dec, clamp | `morph_secreted += sec; morph_decayed += dec`; if clamp: status chem_clamp bit; counted: `chem_clamps += clamp` |
| R_PACKET | sender, target, target sk, amt | counted: `packets += 1`; remembered as in flight with `t_arr = t + d_min` (9.4) |
| R_LOST | sender, target, amt | `morph_lost = morph_lost + amt[0] + amt[1]` (emitted by the target site at arrival time) |
| R_CLAIM | mother, daughter, target sk | `inflight += 1`; counted: `claims += 1; cost = cost + c_div` |
| R_RESOLVE | daughter, mother, result | `inflight -= 1`; if result == 2: status wall bit; counted: `rejects += (result == 1); rejects_wall += (result == 2)`; reject: fate log |
| R_DEATH | uid, cause, zt, content, age, g | world_adv(t); `A = A - zt`; `if A < 0: A = 0`; `n -= 1`; `if n == 0: A = 0`; counted: deaths or kills `+= 1`; `morph_lost = morph_lost + content`; fate log |

`t_open_abs = t0 + t_open`. `last_birth` starts at `t0` and `t_ext` at -1. Integer columns (`arrivals`,
`arrivals_dropped`, `ticks`, `events`) may be counted at the site, because integer sums are order-free. The raster and
fate log set their overflow bits when a capacity is exceeded.

### 9.2 World: the BELL-1 lumen
State: `A` (the sum of z over live cells, all decaying with `tau_z`), `R` (fill, `R(t0) = 1`), `t_w` (anchor,
`t0`) and `above` (0). `P = A / n`. The world reads cells only through records, which are left limits, and sends
nothing to cells.
```
world_adv(t):                                 # integrate [t_w, t) with the state after the last record
    if t <= t_w: return
    if t_w < t_open_abs < t: adv(t_open_abs, count = 0); adv(t, count = 1)
    else: adv(t, count = (t_w >= t_open_abs))
adv(t, count):
    dt = t - t_w
    if n == 0: t_w = t; return                    # no wall: R frozen, no income
    P0 = A / n;  e = exp(-dt / tau_z)
    if P0 > th:                                   # systole until P falls to th
        s1 = tau_z * log(P0 / th);  if s1 > dt: s1 = dt
        I = tau_z * P0 * (1.0 - exp(-s1 / tau_z)) - th * s1
        Rn = R * exp(-I / ((1.0 - th) * tau_e))
        if count: income = income + h_inc * n * (R - Rn)
        R = Rn
    Pend = P0 * e
    if Pend < th_lo:                              # diastole from the moment P falls below th_lo
        slo = (P0 > th_lo) ? tau_z * log(P0 / th_lo) : 0.0
        dd = dt - slo
        if dd > 0: R = 1.0 - (1.0 - R) * exp(-dd / tau_R)
    if count: P_int = P_int + tau_z * P0 * (1.0 - e)
    if Pend <= th: above = 0
    A = A * e;  t_w = t
```
`h_inc * n * (R - Rn)` is evaluated as `(h_inc * n) * (R - Rn)` with `n` converted to double. Between records P
decays as a single exponential, so the systolic, neutral and diastolic phases of one interval come in that order,
and the closed form is exact (design gate G8 compares it with Euler at dt = 1e-3).

### 9.3 Ledger arithmetic
- Charges are added to `cost` in record order with the exact expressions of 9.1, so `cost` is the running sum of
  every action's charge. Apoptosis has no cost. In v1 cells hold no energy.
- `t_open` opens the ledger for late-window measurements and forks. Intervals that straddle it are split exactly
  (`world_adv` and R_TICK), and spikes and claims before it are not counted. The `morph_*` columns, `n_*`, `t_*`,
  `status`, `events` and `last_birth` always cover the whole life.

### 9.4 Packets in flight
The accountant remembers each R_PACKET with `t_arr = t + d_min` (the same float sum as the kernel's) until the
accountant's time passes `t_arr`. On arrival, the target site emits nothing if the packet is delivered and R_LOST if
it is not. At close, `morph_inflight_end` is the sum over the remembered packets with `t_send < t_end <= t_arr` of
`amt[0] + amt[1]`. The packets are taken in increasing `(t_arr, target sk, sender uid)`, and the sum is accumulated
as `s = s + amt[0]; s = s + amt[1]`.

### 9.5 Close
At `t_end` (section 10), after the last time group with `t < t_end`:
```
world_adv(t_end)
for each live cell in increasing sk:
    process a closing R_TICK(uid, t_prev, theta.sec0 + theta.sec1) stamped t_end       # living cost up to t_end
    morph_content_end = morph_content_end + content                                    # as in APOPTOSIS
morph_inflight_end (9.4)
guard_charge = guard tripped ? c_live * n_max * (t1 - t_end) : 0.0                  # n_max: world key 26
colcost = c_live*live_time + c_spike*spikes + c_tw*kappa_sum + c_msg*contact_events + c_div*claims + c_sec*sec_int
          (accumulated left to right in this order)
net = income - colcost - guard_charge;  F = net / (T - t_open)
status |= ledger_mismatch if |cost - colcost| > 1e-9 * max(1, |colcost|)
n_end = n; t_end; events; t_ext
```
`spec.column_cost` and `spec.fitness` re-price a finished ledger under another cost table with the same expressions.

### 9.6 Logs and hashes
The raster and the fate log are written as the records are consumed (canonical order). The four hash families are
`h = splitmix64(h ^ w)` folded over the words `w` of each record, in canonical order, starting from `HASH_INIT`:

| record | words | families |
|---|---|---|
| R_SPIKE | 1, bits(t), uid, bits(kappa), n_out | spikes, all |
| R_BIRTH | 2, bits(t), uid, mother, sk, k | fate, all |
| R_DEATH | 3, bits(t), uid, cause | fate, all |
| R_CLAIM | 4, bits(t), mother, daughter, target sk | fate, all |
| R_RESOLVE | 5, bits(t), daughter, result | fate, all |
| R_PACKET | 6, bits(t), sender, target, bits(amt[0]), bits(amt[1]) | chem, all |
| R_LOST | 7, bits(t), sender, target, bits(amt[0]), bits(amt[1]) | chem, all |
| R_TICK | 8, bits(t), uid | all |

Closing R_TICKs are not hashed. At close, `all` also folds `bits(ledger[c])` for c = 0..34. Two runs agree on a
family iff they produced the same records with bitwise-identical words; test T1 compares all four plus the ledger.

## 10. End of life: T, extinction and guards

- **T**: events with `t < t1` are processed, and the life closes at `t_end = t1`.
- **Extinction**: after a time group, if `n == 0` and `inflight == 0` (for the first time): set the extinct bit and
  `t_ext = t`. Nothing can accrue afterwards: no income because `n = 0`, and no costs because no cells remain. The
  remaining events are all stale or dropped, except packets in flight, which are lost on arrival. So the queue drains
  within `d_min`. Implementations must process the drain; they may then stop. `t_end` stays `t1`.
- **Guards** (compute only; cells cannot sense them) are checked at every integer time `c = t0 + 1, ..., t1 - 1`,
  after all records with `t < c` are consumed and before any event at `t >= c` is processed:
  - **guard_cells**: `n >= n_max`.
  - **guard_events**: the event counter exceeds `e_max`. The counter is FIRE count + executed live TICKs + ARRIVAL
    events (delivered or dropped) with `t < c`.
  If either trips, the life closes at `t_end = c` with the guard charge `c_live * n_max * (t1 - t_end)` and no income
  after `c`. The charge caps the loss of a tripped life at `c_live * n_max` per remaining unit. It makes tripping
  worse than staying below the guard only for bodies that would lose less than that per unit; a body that loses more
  (for example about 1000 seizing cells, at about 0.04 per cell-unit) scores better by tripping (15.28).
  Implementations must support at least `2 * n_max` live cells (n can at most about double within one unit,
  because a claim round trip takes at least `2 d_min` and claims happen only at ticks). If their capacity is
  exhausted anyway, they set the capacity bit and stop. That is an implementation failure, not a model outcome.

## 11. Schedulers

Both schedulers process the same events with the same handlers, and they emit the same records. Every ledger
column, log entry and hash must be bitwise identical between them, for any tie seed, order seed and relabel salt.

### 11.1 Heap (production)
- One priority queue per life.
- The order key is `(t, tie, sk, group, within-group key)`, where `tie = hash64(tie seed, S_TIE, sk)`. Any total
  order that keeps each `(t, site)` batch contiguous is valid, and the tie seed permutes sites at equal t (test T2).
- The heap pops a whole batch, processes it, and hands its records to the accountant. When the next batch has a
  larger t, the pending time group is flushed in canonical order.
- At each integer time it checks the guards.
- Stale events may be dropped lazily, but they must not change the guard counter (the counter does not count them).

### 11.2 Window (tests only)
- Windows are `[t0 + k h, t0 + (k + 1) h)`, with `h = 2^-j <= d_min` (`window_h`).
- In each window, the sites with events in it are visited in increasing `hash64(order seed, S_ORDER, k, sk)` (ties:
  increasing sk).
- Each visited site processes its own batches with `t` inside the window in time order, including self events
  created meanwhile.
- Messages land in later windows (`t >= window end`); an implementation should assert this.
- The window's records are then sorted by `(t, sk, seq)` and consumed by the accountant, which flushes each time
  group.
- Guards are checked at window ends that are integers.

### 11.3 Oracle cap
The oracle cap reads global counts, so it is defined only for the heap. It reads `cap_count = n_alive + n_inflight`
at the left limit `t-` of the tick's time: `n_alive` counts live cells and `n_inflight` claims sent minus claims
resolved, after every batch with a time below t and before any batch at t. The heap takes this snapshot whenever it
starts a new time group. Every claimer at one instant therefore sees the same count, whichever site the tie seed
puts first, and the cap is tie-free. When several cells claim at the same instant they can overshoot the cap
together, deterministically. With jittered clocks such ties have measure zero; under lockstep every tick ties
(first ticks on the grid `t0 + j P0`, every period exactly `P0`), so a capped lockstep body can end a few cells above
its cap. It is a measurement tool for size curves (gates G3 and G4, and the lockstep control for G5), never part of
a task. Window runs with a cap are rejected (return code -2). Until 2026-10-07 the cap read the counts in heap
processing order. Under lockstep that made capped lives depend on the tie seed: in a review, 32 of 64 BUSY lives at
cap 20 changed with the tie seed, with |dF| up to 0.17. Off lockstep, the switch left every capped life bitwise
unchanged. That was checked on BUSY at cap 20 (P0 2 and 4), on R25-v1 at caps 37, 91 and 127, and on GRN lives on hex
and square8. Test: `test_t2_the_oracle_cap_is_tie_free_under_lockstep`.

## 12. Flags and forks

`flags` apply from `t0`. `fork_flags` are added for every event at `t >= t0 + t_fork`. A flag is "active at t" if it
is in `flags`, or in `fork_flags` with `t >= t0 + t_fork`. Every handler tests flags at its batch time t, so a
message created before `t_fork` is delivered normally after it.

| bit | flag | effect |
|---|---|---|
| 0 | contacts_off | FIRE creates no ARRIVAL; n_out is still charged; v and traces are untouched |
| 1 | chem_off | TICK step 7 sends no packets and does not reduce m (no transport); secretion and decay go on |
| 2 | apoptosis_off | no deaths in TICK step 6 (p_die and prune) |
| 3 | division_off | no claims |
| 4 | freeze | no gene update, no phenotype or w_eff update, no division, no death (the membrane is still re-anchored at ticks) |
| 5 | genes_blind | x[18..22] = 0 (no traces, n_view or flank reach the genes) |
| 6 | identity_clamp | g frozen: no gene update, and no partition at division (a daughter starts with her mother's g, and the mother keeps hers; 15.31) |
| 7 | pheno_fixed | theta is decoded at birth only (w_eff is still recomputed) |
| 8 | lockstep | base only: every d_c = d0, delays without jitter (jit and tick_jit treated as 0), no tau or clock mismatch, first ticks on the grid `t0 + j P0` |
| 9 | program_mode | base only: section 7.5 |
| 10 | integer_twin | base only; reserved, rejected in ABI v1 |

Under `lockstep` the kernel ignores `delay_sd`, `jit`, `tau_mis`, `clock_sd` and `tick_jit`.

Forks are defined by replay: a fork at `t_f` with condition X is the same life (same seeds) run with
`t_fork = t_f`, `fork_flags = X` and usually `t_open = t_f`. Its unchanged twin is `fork_flags = 0` with the same
`t_open`. An implementation that snapshots the state at `t_f` and continues it instead must produce identical
results; any fork with no change continues bitwise. Design forks map as follows:
- spikes undelivered: contacts_off;
- packets off: chem_off;
- apoptosis off: apoptosis_off;
- division off: division_off;
- identity clamp: identity_clamp;
- freeze-after-growth: freeze at T/4;
- the two-stage replica: `t_open = 64` plus freeze at 64.

## 13. Reserved for later stages
- **Integer twin**: int64 time in 2^-20 units, Q24 g and m, lookup-table exp and ln. Its rounding points are to be
  specified with migration step 3; the flag bit is reserved.
- **v2**: `kill_rate` (exogenous Poisson loss via hash-keyed KILL streams arriving `>= d_min` after their cause) and
  `wound_rate`.
- **v3**: `drift_tau` (random walks of the frozen tau mismatch and d_c, and a drifting tau_R).
- **v4**: per-cell energy E, energy packets, necrosis, failed spikes.
- **v5**: receptors (S = 1, a RECEPTOR event kind in group 3) and threats.
Each of these will be a new ABI version with its own world keys and padded genome fields. A v1 genome must behave
identically after padding.

## 14. Test vectors
(Also asserted in `tests/test_life_spec.py`; a kernel test must reproduce them through the test exports.)
```
splitmix64(0)                                 = 0xe220a8397b1dcdaf
splitmix64(1)                                 = 0x910a2dec89025cc1
hash64(0, 0)                                  = 0xa706dd2f4d197e6f
hash64(1, 2, 3, 4)                            = 0x89f838c6080f2b76     u01 = 0.5389438136554047
hash64(2^64 - 1, 7, -1)                       = 0x6beeacb0a480f707
sitekey(-1, 2)                                = 0xffffffff00000002
sitekey(3, -4)                                = 0x00000003fffffffc
normal(42, S_CLK, sitekey(0, 0), 0)           = 0.25705196441331246
normal(42, S_DC, sitekey(0,0), sitekey(1,0), 0) = 1.039345905501138
draw(42, S_PHASE, sitekey(0, 0), 0)           = 0.5527679572439935
zygote uid, seed 42                           = 0x2791839b6c9caf25
its first daughter (div# 0)                   = 0x64f81c91d3fa48d1
draw(42, S_JIT, zygote uid, 1, 3)             = 0.549803149142197
decode(y), y = [0.3, -2.7, 1.0, 0.5, -0.26, 0.0, 1e-9, 0.3, 0.75, 0.13, 0.0, -2.0, 1.1, 0.0, -1.0, 0.5, -9.0, 0.0,
                2.2, -0.0624, 0.0625]
  = [0.25, -2.0, 1.0, 4.0, 1.5, 0.0, 1.0, 0.5, 0.5, 0.0078125, 0.5, 0.0, 1.0, 0.25, 0.13447071068499755, 0.875,
     -2.0, 8.0, 2.0, -0.0, 0.0]
decode_lambda(-5, -2.5, -0.5, 0, 0.5, 3.4, 10)  = 1/2, 1/2, 1/8, 1/16, 1/32, 1/128, 1/128
decode_dm(0, D = 6) = 0.025;  decode_km(0) = 0.155
```

## 15. Choices and deviations relative to ONE_LIFE_DESIGN.md
Each item either fixes something the design left open or changes its pseudo-code in a way that keeps its intent.
All of them should be read by the user.

1. **Processing entity = site.** The design speaks of cells. Claims are arbitrated by the site (as the design says),
   so a site's claim arbitration and its occupant's events must be one sequential process; otherwise a death and a
   claim less than d_min apart at one site would depend on the window order.
2. **Left limit for the whole batch.** Every event in a batch, not only claims, sees the occupant at `t-`. A newborn
   therefore ignores notices that arrive at its birth instant, and loses nothing, because it gets the same
   information from the PRESENT replies.
3. **DIED is broadcast to all D neighbour sites** (the design says "to every live slot in view"). A cell that dies
   less than `2 d_min` after its birth has not yet heard from its neighbours. With the design's rule, those
   neighbours would keep the dead uid in their view forever: they would never claim the site, and they would pay
   c_msg for spikes to nobody. Only occupied sites receive the broadcast, as with BORN.
4. **Packets are events** (group 2). A packet whose target is gone is lost at its arrival time, at the target site.
   This keeps `morph_lost` and the chem hash scheduler-independent. An implementation may keep inbox-only packets if
   it emits the same R_LOST records. `kernel.c` does: a packet whose target is the live occupant when it is sent goes
   straight into the target's inbox, stamped with `t_arr`, and only a packet whose target is gone when it is sent, or
   dies before `t_arr`, becomes an event (it emits R_LOST at `t_arr`). This removes most heap events (about a third
   of the run time of an R25 body) and leaves every record unchanged.
5. **Exact threshold in the batch.** A current THRESHOLD contributes `v = 1.0` exactly instead of `vnow(t*)`, which
   can round to 1 - 1 ulp. Without this, a subsumed crossing with zero net input could be lost.
6. **The Q10 re-anchor can fire.** The design rounds v at the cell's own events, so the tick re-anchor rounds too. A
   value in `[1 - 2^-11, 1)` rounds to 1, and then the cell fires at the tick (with the old phenotype), instead of
   being stuck above threshold with no crossing scheduled.
7. **Secretion over a tick interval uses the phenotype in force during it** (theta_prev), both for the mass and for
   c_sec. The design's step 7 runs after the re-decode, which would charge one rate and secrete another.
8. **The placement gradient p uses s_d from step 5**: `p = sum_d s_d unit(d)`, with m before the chemistry step and
   the new pol. That is the design's formula with m read before rather than after the tick's own secretion and
   shipping, so the directional weights and the placement see the same field.
9. **inc[d] is reset at DIED**, so a dead neighbour's last concentration does not persist. A packet the dead
   neighbour sent before it died can still be in the receiver's inbox when DIED arrives (or when a new cell is born
   at its site and announces itself), so TICK step 1 adds every packet's mass to `m` but lets a packet set
   `inc[slot]` only if its sender is the contact the cell now holds in that slot (`view[slot] == sender uid`).
   Hence `inc[d]` is always 0 or the concentration of the last packet from the current contact in slot d. A live
   contact's packets always arrive after the receiver knows it (they are sent only once the sender knows the
   receiver, at least `d_min` after the receiver heard the sender's BORN or PRESENT), so the gate drops only stale
   concentrations. (Cross-check round 1: without the gate, 2-4% of a turnover body's slot states held a dead or
   replaced neighbour's concentration.)
10. **Slots not in view have shat = 0** in w_eff. Arrivals can precede a newborn's knowledge of a neighbour by
    `d_min`, so their weight must be defined.
11. **Knob laws the design left open**: delta, kappa and phi use `L(y) = clip(rint(2y), 0, 3)` (the zero level
    holds for y < 0.25, so "mean 0" initializations give about half zeros); tau_tr uses `clip(rint(y + 1.5), 0, 3)`
    (symmetric around 0); the act bit is `x > 0.5`. sec is continuous (`0.5 sigma(y)`), as in the design, so a GRN
    cell never secretes exactly 0. A program row can.
12. **D_m bound**: `P_MAX = 3.0` is a fixed constant (1.5 x P0 = 2), so D_m is a property of the genome and the
    lattice only. With the default spreads, a tick interval is at most `2 e^{0.3} 1.1 = 2.97`, so the 90% bound
    holds by construction. With wider panel clocks or P0 = 4, a clamp `q = 0.9 / n_view` applies and is counted.
13. **Frozen normals are Irwin-Hall(12)**: exact integer sums, bounded in [-6, 6], which also bounds the clock
    period. The tau_m mismatch is uniform `+-tau_mis`, as in bell3. The clock rate and d_c use the normal.
14. **Uids** are `hash | 1` (nonzero; 0 means EMPTY), and the zygote's uid is hashed from the life seed.
15. **Events are counted for the guard as FIRE + TICK + ARRIVAL**, which are model quantities. Heap-internal stale
    entries would make the count implementation-dependent.
16. **Guards are checked at integer times**, so the trip time is identical under both schedulers. The N_max guard
    therefore allows a transient overshoot within one unit.
17. **Extinction** does not shorten `t_end` (it stays t1). The ledger closes naturally, because nothing accrues
    without cells, and `t_ext` records the time.
18. **The oracle cap is heap-only** (it reads global counts), and it reads them at the left limit `t-` of each
    instant (11.3), like claims read occupancy, so it is tie-free under lockstep too.
19. **Forks by replay** with `t_fork` and `t_open`. The design's `fork()` snapshot is an allowed optimization with
    identical results.
20. **chem_off** stops transport (no packets, m not reduced). It does not destroy the packets. That is the cleaner
    "packets undelivered" counterfactual, because mass is conserved.
21. **Lockstep first ticks** sit on the grid `t0 + j P0` (in-phase clocks need a shared phase; this is a control
    condition, never the default).
22. **A first tick or noise kick that rounds to the batch time moves to `nextup(t)`**, so no self event lands in
    its own batch.
23. **Notices carry the sender's birth index** (BORN, PRESENT, ACK), so the receiver can compute the frozen delay
    keyed by both birth counts, as the design requires.
24. **Ledger t_open** generalizes bell3's T_burn for late windows and forks. F divides by `T - t_open`.
25. **The integer twin is deferred** (section 13).
26. **A panel KILL charges the killed cell's last interval** (cross-check round 1). The design's F charges
    `c_live * integral of n dt`; a cell that dies at its own tick is charged up to its death by that tick's R_TICK,
    but a KILL falls between ticks, so without the extra R_TICK of 7.9 the interval `[t_prev, t_kill)` was never
    charged and `live_time` fell short of the cell-time in the birth and death log.
27. **Dying at a tick: secretion is charged but not produced.** TICK step 2 charges `c_sec * sec` for the interval
    that ends at the tick (the cell lived and secreted over it), but a cell that dies at step 6 skips step 7, so that
    interval's secreted mass is never added to `m` (the design orders the steps this way). Mass is still conserved;
    `sec_int` exceeds `morph_secreted` by the open last intervals of dying, killed and surviving cells.
28. **The guard charge bounds the loss; it does not dominate every body below the guard.** The design says the charge
    `c_live * N_max * (T - t_g)` makes "tripping a guard always worse than staying below it" (Life tasks, DEATH AND
    THE WHOLE-BODY GUARD; cheat 9). That holds only for bodies that would lose less than `c_live * N_max` per unit
    below the guard. A body whose net cost per cell-unit is above `c_live` loses less by racing to `N_max` and
    ending its life. Measured (review, 16 lives each): tonic seizing cells (b 2, tau_m 1, t_ref 0.5, both channels,
    kappa 1, p_div 1/2) score F = -20.39 by tripping N_max at t of about 90, and -32.55 when the oracle cap holds them
    at 1000 cells (that run then trips the event guard at about 879, which only cuts its loss). The charge is kept as
    specified: it caps every tripped life near `-c_live * N_max * (T - t_g) / T` (about -20 for an early trip),
    far below any viable genome (founders need F >= 0.02), so it cannot change selection among viable genomes. Strict
    dominance would need a charge at the body's own observed cost rate, a new ledger column. Test:
    `test_the_guard_charge_bounds_the_loss_but_does_not_dominate_a_costlier_body`.
29. **The daughter's genes are clipped to [0, 1] too.** The design's TICK step 8 sends the daughter `g + asym * Q`
    unclipped and clips only the mother, `g = clip(g - asym * Q, 0, 1)` (rule 13 states the partition without a
    clip). Here both are clipped: `gd = clip(g + asym * Q, 0, 1)` (7.4 step 8). The gene update
    `g + lam * (sigma(p) - g)` with `lam <= 1/2` keeps every gene in [0, 1], the range of its sigmoid target and of
    the inputs `x[0..15]` that W was evolved on. An unclipped daughter would start outside that range: Q is a raw,
    unbounded genome entry, so `g + asym * Q` can be large. It would also be partitioned asymmetrically with the
    clipped mother. With Q = +1 (the G9 juvenile gene), the daughter starts at `min(1, g + asym)`, never above the
    gene's range. That matches the design's own description, "daughters start at 1 and mothers at 0" (Identity, R25-v1
    as a genome), and keeps the length of listen-before-talk independent of how far above 1 an unclipped start would
    be. Test: `test_division_clips_the_genes_of_both_daughter_and_mother_to_the_unit_interval`.
30. **World ranges** (4.7). The design fixes the v1 constants but not their admissible ranges. The kernel needs
    ranges for its causality and termination premises (6.3, 10): positive periods, delays and time constants, and
    fractions in [0, 1]. Any vector outside them is an argument error (-2), not a life.

31. **identity_clamp also suspends the division partition** (review fix, 2026-10-07). The design defines the identity
    clamp as "g is frozen from the fork on" (Identity, KNOCKOUTS). The first kernel skipped only the gene update
    (step 4), so each claim still shifted the mother's g by `-asym * Q` and started the daughter at `g + asym * Q`:
    identity kept changing at every division (review: 1877 of 3081 cells that died under a clamp from t = 0 had a g
    at death different from their g at birth). Under the flag, step 8 now sends `gd = g` and leaves the mother's g
    unchanged, so every cell keeps the g it had at the fork, and a cell born from a claim made after the fork starts
    with its mother's. A claim made before the fork carries the partition it was made with (flags are tested at the
    batch time, section 12). Program mode is unchanged (its claims carry the timer, which the flag already freezes).
    Test: `test_identity_clamp_freezes_g_through_divisions`.
