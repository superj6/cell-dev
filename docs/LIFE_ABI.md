# One-life kernel ABI and event semantics (ABI 3)

This document is the contract between the C event kernel (`src/life/kernel.c`), the Python reference
(`src/life/reference.py`) and the harness (`src/life/spec.py` and its callers). It fixes the array layouts, inputs,
outputs and the exact event semantics of the model in `docs/ONE_LIFE_DESIGN.md` and of the body world of
`docs/BODY_DESIGN_PROPOSAL.md` (BODY-1 v1, approved 2026-10-07). An independent implementation that follows it
exactly, on the same libm, reproduces every ledger column, log and hash **bitwise**.

`src/life/spec.py` is the Python mirror of every constant, layout and pure function defined here: `spec.V3` is this
document (ABI 3), `spec.V2` is ABI 2. When this document and `spec.V3` disagree, that is a bug; fix one of them and the
tests in `tests/test_life_spec.py` and `tests/test_life_spec_abi3.py`.

Status: ABI 3 covers two world kinds in float64. **World kind 0** is BELL-1 (design stage E1/v1), exactly as in ABI 2.
**World kind 1** is CATCH (BODY-1 v1): the body is a dot on an unbounded screen, a 3D hex-prism tissue rides on it,
sense-plane cells receive Poisson receptor events from the screen point under them, act-plane twitches pull the dot,
and the act cell at the body centre clicks (section 9.7). Both kinds run in GRN and program modes, under the heap and
window schedulers, with forks by replay and the robustness-panel perturbations of section 7.9. The integer twin and
the later world features are reserved (section 13). Section 15 lists every place where this contract makes a choice
that the design left open, or deviates from its pseudo-code, and why; entries 33-61 are ABI 3's.

**Implementation state (2026-10-07).** `spec.CURRENT` is `spec.V2`, so every module-level name of `spec.py`
(`GENOME_SIZE`, `pack_world`, ...) is ABI 2's. `kernel.c` implements ABI 3; `build.run` speaks the caller's ABI
(`spec.CURRENT` by default): it pads ABI-2 tables neutrally, gives bodies z = 0, and returns ABI 2's shapes, with
ABI 2's `all` hash recovered exactly by undoing the 22 extra close folds (`build.unfold_close`). `reference.py`
implements ABI 3 too, written independently from this text, with the same ABI-2 view. Cross-check round 1 of ABI 3
(2026-10-07) found the two bitwise equal on every ABI-3 test life and on about 1,800 random CATCH lives, and fixed only
wording and argument checks (15.57). The switch is `spec.CURRENT = spec.V3`, with BELL-1 bitwise (gate GB1; the golden
BELL lives of `tests/test_life_world_bell.py`, computed by the ABI-2 kernel of 7d3896d, pin it). ABI 2, the previous contract, is this text restricted to world kind 0 on the 2D lattices,
with the sizes listed in 4.2.

Revisions (not yet frozen). ABI numbers count changes of this contract. They are not the design's stages (v1-v7):
ABI 1 and ABI 2 implement stage v1; ABI 3 adds BODY-1 v1.
- **ABI 3** (2026-10-07, BODY-1 v1 approved by the user with the surface-normal pull, hotspot-only clicks, hidden
  planes above the act plane, pilot arms L_max 2 and 4, and the radius gene deferred). Everything is appended, so
  every ABI-2 quantity keeps its index:
  - sites are `(a, b, z)` with a stack height `L_max` (3, 4.3, 7.6); the key packs z so that z = 0 keys are ABI 2's
    (15.34); out-of-stack sites do not exist (15.35); new lattice kinds `hexprism`, `square4prism`, `square8prism`
    and a 3D lattice table `[2 + 7 D]` with unit vectors `[D][3]` (4.3);
  - knobs 21 `zeta` and 22 `g_r` (23 knobs, 8); gene inputs 22 `rho / tau_tr`, 23 `is_S`, 24 `is_M` (25 inputs,
    7.4); the genome has 875 slots and the program table 129 (4.4, 4.5);
  - world keys 41-65 (66 keys: world kind, L_max, stuck_z and the CATCH keys, 4.7); ledger columns 35-56 (57, 4.9);
    a fifth hash family `world` (9.6); a z column in initial bodies (`[1024][4]`, 4.6) and in the fate log (4.11);
  - the RCAND and RECEPTOR events (6.1, 7.10), the records R_RCAND and R_RECEPT, and the CATCH accountant (9.7),
    the first world that sends events to cells (always at least d_min after their cause, 6.3);
  - vertical placement (7.4 step 8) and the forks `lateral_off`, `hidden_off`, `receptor_off` and `motor_off` (12).
  - **Cross-check round 1** (2026-10-07, no life changes): the kernel and the reference agree bitwise on every
    ABI-3 test life and on about 1,800 random CATCH lives. Wording made precise in 4.1 (the load check), 4.3 (an
    out-of-stack slot is never open), 9.7.2 (synchronous firing cancels up to rounding) and 9.7.4 (a second-blob
    click books its value only when counted); five kernel argument checks written down (15.57), which the
    reference now applies too.
  - **BELL-1 is bitwise.** A BELL world (kind 0) on a 2D lattice, with every ABI-2 genome or program padded by
    `spec.V3.pad_genomes` or `spec.V3.pad_program` (new entries 0), lives exactly as under ABI 2: every ledger
    column 0-34, the raster, the fate log's first six columns and the spikes, fate and chem hashes are bitwise
    those of ABI 2. Only the `all` hash differs (it folds 57 ledger columns at close), the new columns hold zeros
    or plane totals, and the `world` hash stays `HASH_INIT` (15.33).
  - **Review fixes** (2026-10-07, before any CATCH run; ABI 3 was not yet frozen, so the number stays): world timers
    have the 2^-10 floor (15.58); the drag counts the projected footprint, every occupied column in any plane, not
    the sense-plane cells alone (15.59; every body of complete columns lives bitwise as before); the default c_miss
    is 2 (15.60; a price, so lives are unchanged and F moves by −misses / T). BELL-1 is untouched by all three.
  - **Red-team tweak RT-T1** (2026-10-08, after the S1 prototype study; ABI 3 still not frozen): the drag counts the
    filled footprint, the projected footprint plus every tile it encloses (9.7.2, 15.61), so a hollow body drags
    like the disk it covers. Every body that never encloses a tile lives bitwise as before (full disks, column
    bodies, hidden stacks, islands, footless drifters); BELL-1 is untouched. One test export is added
    (`life_filled_footprint`, 4.2). A review then found a residual, recorded in 15.61 and not changed: a hole opened
    to the outside by a one-column slit is not filled, so such a body keeps part of the old discount.
  - **SPECK presets** (2026-10-08, before any SPECK run): c_miss 10, so R_cap / c_miss is v1's 50 (15.62). A price
    only: no cell reads it, so lives are unchanged.
- **ABI 2** (2026-10-07, approved before the pilot) removes the gene-network input `flank_best / 2`: x has 22
  entries (7.4 step 3), W is `[16][22]` and the genome has 793 slots (4.4), and `genes_blind` zeroes `x[18..21]`
  (12). Placement keeps `phi * flank(e)`, and program mode keeps its `flank_gate`. Why: section 15.32. A genome whose
  flank weights are 0 lives bitwise as it did under ABI 1.
- ABI 1: cross-check round 1 (2026-10-07) made TICK step 1 set `inc[slot]` only from the slot's current contact
  (7.4, 15.9), made a panel KILL charge the killed cell's last interval (7.9, 15.26), and recorded 15.27. The kernel
  and the reference implement both. Migration step 3 (2026-10-07) fixed the Python mirror of sigma for readouts
  below about -709.78 (section 2: the reference raised OverflowError where the kernel returns 0); the kernel is
  unchanged.

Contents:
1. Overview of the computation
2. Arithmetic conventions
3. Randomness: hash, draws and uids
4. Kernel interface: entry points and arrays
5. State
6. Events, batches and the causality contract
7. Handlers
8. Phenotype decode and derived quantities
9. The accountant: records, world, ledger, logs, hashes (9.2 BELL-1, 9.7 CATCH)
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
- Space is a lattice of **sites** with integer coordinates `(a, b, z)`: planes `z = 0 .. L_max - 1` of a 2D base
  lattice, stacked at unit spacing (a 2D lattice is a prism of one plane, `z = 0`). In the default sparse fabric every
  in-stack coordinate exists; sites outside the stack do not exist at all (15.35). A site holds at most one live
  cell. Sites are the processing entities: every event is addressed to a site, and each site processes its own
  events in time order.
- A site's events with one timestamp form a **batch**, applied in a fixed kind order (section 6.2). A batch reads
  everything that comes from outside the cell as a **left limit** (the state at `t-`).
- Every effect of one site on another is a **message** that arrives at least `d_min` later. So sites never read each
  other's state, and any causally valid processing order gives the same history.
- Handlers emit **records** (spikes, births, deaths, ticks, claims, packets, receptor candidates and deliveries).
  One sequential **accountant** consumes the records of a life in canonical order `(t, sitekey, seq)` (section 9.1).
  Only the accountant computes cross-cell quantities: the world (the BELL lumen, or the CATCH dot, blobs, clicks and
  receptor thinning), the ledger, n(t), extinction and guard checks, logs and hashes. This is what makes
  floating-point sums identical under every scheduler.
- The world is physics, not a cell: it reads cells only through records (left limits), and the only thing it sends
  back is a RECEPTOR event, created by the accountant from a record at `t` and delivered at `t + d_min` (CATCH only;
  in BELL nothing flows back). No cell reads the dot's position, a blob, a clock or any total.

## 2. Arithmetic conventions

- All real quantities are IEEE-754 binary64 (`double`). Time is float64. Each formula is evaluated exactly as
  written, left to right, one rounding per operation, with no fused multiply-add and no reassociation. The kernel is
  compiled with `gcc -O3 -fopenmp -ffp-contract=off` and without `-ffast-math`, `-funsafe-math-optimizations` or
  `-march` flags. In the pseudo-code below, `a + b + c` means `(a + b) + c`.
- Transcendentals: only `exp`, `log` and `tanh` from the C math library (`math.exp`, `math.log` and `math.tanh` in
  Python call the same libm), and in the CATCH world also `cos`, `sin` and `pow` (`math.cos`, `math.sin`,
  `math.pow`). Bitwise agreement between the kernel and the reference assumes the same libm. `floor`, `nextafter`
  and `sqrt` are also used; they are exact (IEEE-754 rounds `sqrt` correctly).
- `TWO_PI = 6.283185307179586` (the double nearest 2 pi; C `2.0 * M_PI`) and `S32 = 0.8660254037844386` (the double
  nearest sqrt(3)/2, `math.sqrt(3) / 2`) are the only irrational constants.
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
sitekey(a, b, z) = ((uint64(uint32(a)) << 32) | uint32(b)) ^ (uint64(z) << 56)
                # two's complement of the int32 coordinates; the height z (0 <= z < 8) is XORed into bits 56-59
```
Signed integer keys enter as their two's complement mod 2^64. Comparisons of `u01` against dyadic probabilities
(`p = 2^-j`) can never tie.

The site key of `z = 0` is ABI 2's `sitekey(a, b)` exactly, so 2D lives keep every key, every frozen draw and the
canonical order. For `|a| < 2^24`, bits 56-63 of `uint32(a) << 32` are copies of a's sign bit, so the XOR is
reversible and keys are distinct for distinct sites with `0 <= z < 16`. Initial cells satisfy `|a|, |b| <= 2^22`
(4.6) and a body has at most `2 n_max <= 2^21` cells (10), so every reachable site has `|a| < 2^24` (15.34).

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
| S_RCAND | 18 | uid, j | CATCH: time of the j-th receptor candidate of a sense-plane cell (7.10) |
| S_RACC | 19 | uid, j | CATCH: thinning draw of that candidate, read by the accountant (9.7.5) |
| S_TURN | 20 | blob, k | CATCH: interval before the k-th turn of a blob |
| S_HEAD | 21 | blob, h | CATCH: heading h of a blob (h = 0 at t0, h = k + 1 after turn k) |
| S_RTIME | 22 | blob, k | CATCH: interval before the k-th timer re-placement of a blob |
| S_PANG | 23 | blob, q | CATCH: angle of placement q of a blob |
| S_PDIST | 24 | blob, q | CATCH: distance of placement q of a blob |
| S_PPRES | 25 | blob, q | CATCH: whether the second blob is present after its placement q |

`blob` is 0 for the target and 1 for the optional second blob; `j`, `k`, `h` and `q` are 0-based counters. The
world streams are keyed by the blob's own counters, never by a cell, so the target's path depends on the body only
through the dot positions at which it is placed.

Frozen physics (keyed by place and birth index) gives every genome in a generation the same physics at the same place,
and the same genome the same body on any fabric. Event draws are keyed by the cell's own counters, so a draw is a
property of the event, never of processing order.

## 4. Kernel interface: entry points and arrays

### 4.1 Build and loading
`src/life/build.py` compiles `kernel.c` with
`gcc -O3 -fopenmp -ffp-contract=off -fPIC -shared -std=c11 -o life_<key>.so kernel.c -lm`, where `<key>` is the
first 16 hex digits of the SHA-256 of the source text plus the flag string. The library is cached by that key
(default directory `~/.cache/cell-dev/life`) and loaded with `ctypes`. It must export the functions below with C
linkage. The caller checks `life_abi_version()` and `life_sizes()` against the ABI the kernel implements before the
first run (`build.KERNEL = spec.V3`: an ABI-3 kernel reports 3 and `spec.V3.SIZES`, whatever `spec.CURRENT` is).

### 4.2 Entry points
```c
int32_t life_abi_version(void);
void    life_sizes(int32_t out[10]);   // abi, genome 875, program 129, world 66, ledger 57, hashes 5, knobs 23,
                                       // max_init 1024, fate_i 7, fate_f 18   (spec.SIZES, in this order)
int32_t life_run(
    int32_t n_lives, int32_t threads,
    const int32_t *lat,          // [2 + 7*D]   lattice table (4.3)
    const double  *unit,         // [D][3]      unit vectors (4.3)
    int32_t n_genomes,           // G           rows of the genome table
    const double  *genomes,      // [G][875]    packed genome tables (4.4); may be NULL if every life is program mode
    int32_t n_programs,          // P           rows of the program table
    const double  *programs,     // [P][129]    program tables (4.5); may be NULL if no life is program mode
    const int32_t *genome_of,    // [n_lives]   row of the table each life's mode uses (programs or genomes)
    const int32_t *init_cells,   // [n_lives][1024][4] explicit initial bodies (4.6); may be NULL
    const int32_t *n_init,       // [n_lives]   0 = one zygote at (0, 0, 0); may be NULL (all 0)
    const double  *world,        // [n_lives][66] world vectors (4.7)
    const uint64_t *seeds,       // [n_lives][4]  life seed, tie seed, order seed, relabel salt (4.8)
    double   *ledger,            // [n_lives][57] out (4.9)
    uint64_t *hashes,            // [n_lives][5]  out (4.10)
    int64_t raster_cap, double *raster_t, uint64_t *raster_uid, int64_t *raster_n,   // [n_lives][cap] (4.11)
    int64_t fate_cap, int64_t *fate_i, double *fate_f, int64_t *fate_n);              // [n_lives][cap][7|18]
```
ABI 2 had `lat [2 + 6 D]`, `unit [D][2]`, genome 793, program 119, `init_cells [64][3]`, world 41, ledger 35, 4 hashes
and `fate_i` 6; its `life_sizes` reported `2, 793, 119, 41, 35, 4, 21, 64, 6, 18`.
All arrays are C-contiguous, row-major, native endianness. Lives run in parallel with OpenMP
(`schedule(dynamic, 1)`, `num_threads(threads)`; `threads < 1` means 1). A capacity of 0 or a NULL pointer turns that
log off.

Return codes: `0` success; `-1` size or ABI mismatch, a NULL table (or `init_cells`) that some life needs,
`genome_of[i]` outside `[0, P)` for a program-mode life or `[0, G)` for a GRN life (each table is bounded by its own
row count, so a life never depends on what else is in the batch), or a NaN or infinity in a table row that some life
uses (4.4, 4.5); `-2` invalid world vector (any rule of 4.7, `spec.validate_world`); `-3` allocation failure; `-4`
invalid lattice table or initial body (duplicate sites, `n_init > 1024`, a program-mode row index out of range, a
cell outside the stack `0 <= z < L_max`, with `|a|` or `|b|` above `2^22`, or on a wall of a dense fabric, 4.6). The
kernel checks every life's arguments before it runs any, so an argument error never leaves partial outputs. When one
call breaks several rules, the code is the first found in this order: the lattice table; then, life by life, the
world vector, the table row (its index, then its finiteness), `n_init`, a NULL `init_cells`, and the initial cells
(15.57). Per-life problems that are not
argument errors are reported in the status column. `build.run` raises `ValueError` for the same errors, and also
when `genome_of` is omitted and a table has neither 1 nor `n_lives` rows.

Test exports (used by `tests/test_life_*` to compare the C functions with `spec.py` bitwise):
```c
uint64_t life_hash64(uint64_t seed, uint64_t stream, int32_t n, const uint64_t *keys);
double   life_normal(uint64_t seed, uint64_t stream, int32_t n, const uint64_t *keys);
void     life_decode(const double y[23], double theta[23]);           // section 8
void     life_readout(const double gt[875], const double g[16], double y[23]);
// CATCH closed forms (9.7), each the spec.py function of the same name:
double   life_halo(double dx, double dy, double sigma);                                   // spec.halo
void     life_dot_gain(double dt, double tau_z, double gam, double out[2]);              // spec.dot_gain: k, e
void     life_blob_heading(uint64_t seed, int32_t blob, uint64_t h, double v_t, double out[2]);
void     life_blob_place(uint64_t seed, int32_t blob, uint64_t q, double x, double y, double r_min, double r_max,
                         double out[2]);
double   life_receptor_next(uint64_t seed, uint64_t uid, uint64_t j, double t_prev, double lam_max);
int64_t  life_filled_footprint(int32_t base, int64_t n, const int32_t *a, const int32_t *b);
         // spec.filled_footprint of the columns (a[i], b[i]) (repeats count once) on base lattice code % 3
         // (0 hex, 1 square4, 2 square8): n_fill of 9.7.2; -1 on allocation failure
```

### 4.3 Lattice table
`spec.V3.lattice_tables(kind)` builds both arrays from the `src/lattice.py` 3D helpers (`offsets3`,
`back_slots3`, `cyclic_neighbours3`, `unit_vectors3`, `rotate3`):
- `lat` int32 `[2 + 7D]`: `code`, `D`, `off_a[D]`, `off_b[D]`, `off_z[D]`, `back[D]`, `prev[D]`, `next[D]`, `rot[D]`.
  Codes and degrees: 0 hex (6), 1 square4 (4), 2 square8 (8), 3 hexprism (8), 4 square4prism (6), 5 square8prism
  (10). A prism stacks planes of its base kind (hex, square4, square8) at unit spacing.
  - Slot `d` points to the neighbour at `(a + off_a[d], b + off_b[d], z + off_z[d])`. The in-plane slots come first,
    in the base kind's `lattice.offsets` order (hex axial `(1,0),(1,-1),(0,-1),(-1,0),(-1,1),(0,1)`; square4
    `(1,0),(0,1),(-1,0),(0,-1)`; square8 adds `(1,1),(-1,1),(-1,-1),(1,-1)`), all with `off_z = 0`. A prism then has
    **up** (`(0, 0, +1)`, slot 6 on hexprism) and **down** (`(0, 0, -1)`, slot 7). A 2D kind has `off_z = 0`
    everywhere; its offsets, back, prev, next and rot are ABI 2's.
  - `back[d]` is the neighbour's slot that points back (found by lookup; on square8 it is `2,3,0,1,6,7,4,5`; on
    hexprism `3,4,5,0,1,2,7,6`). A message sent through slot `d` arrives at the receiver's slot `back[d]`.
  - `prev[d]` and `next[d]` are the clockwise and counter-clockwise angular neighbours of an in-plane slot `d`
    (`lattice.cyclic_neighbours` of the base kind, so always in-plane). A vertical slot has `prev[d] = next[d] = d`:
    it has no angular neighbours, and its flank count (7.4 step 3) is 0 whenever it is empty.
  - `rot[d]` is the slot permutation of one counter-clockwise rotation about the vertical axis; vertical slots are
    fixed. It is used by tests only.
- `unit` float64 `[D][3]`: the unit vector of each slot (`lattice.unit_vectors3`): in-plane slots carry the base
  kind's planar unit vectors (hex `x = a + b/2`, `y = b*sqrt(3)/2`; square8 diagonals normalized) with `z = 0.0`,
  bitwise ABI 2's values; up is `(0, 0, 1)` and down `(0, 0, -1)`. Both implementations read these numbers. Neither
  recomputes them.
- `D` (the lattice degree) is the table's `D` everywhere it appears (`n_view / D`, the D_m decode), so on hexprism
  `D = 8` even where the stack hides a vertical slot (15.36).
- The planar position of site `(a, b, z)` in the body frame (9.7) is `planar(a, b)`: hex and hexprism
  `((double) a + 0.5 * (double) b, (double) b * S32)`; square kinds `((double) a, (double) b)`. It is
  `lattice.to_xy` of the base kind.
- A table is valid (else `life_run` returns -4) iff its code is listed, D is that code's degree, every slot index is
  in `[0, D)`, `back[d]` points back in all three coordinates, no slot has the offset `(0, 0, 0)`, and `off_z` is 0 on
  the base kind's slots and `+1`, `-1` on a prism's last two. The kernel reads the offsets from the table; it may rely on the slot order above.

**Stack and walls.** Site `(a, b, z)` is **in the stack** iff `0 <= z < L_max` (world key 42). Sites outside the
stack do not exist: nothing is sent to them, nothing is ever born there, and a slot pointing out of the stack is never
open (a cell cannot see or claim it). Its view entry holds no contact (EMPTY in both implementations), so it never counts
in `n_view` or `n_out`, but it is not an empty, claimable slot. For a cell at height z, slot d is **in stack** iff
`0 <= z + off_z[d] < L_max`, and **open** iff it is in stack and `view[d] == EMPTY`. A dense disk fabric
(`fabric_R > 0`, test T12) is unchanged: an in-stack site outside the disk is a wall, which is open, can be claimed
and rejects the claim (result 2). On a 2D lattice every slot of a z = 0 cell is in stack.

### 4.4 Genome table (GRN mode)
The raw genome is float32 `[875]` with these fields (`spec.V3.GENOME_FIELDS`; offsets `spec.V3.GENOME_SLICES`). W's
25 columns weigh the 25 inputs x of 7.4 step 3, in that order (ABI 1 had a 23rd column, flank_best / 2: 15.32). A's
23 rows are the 23 knobs of section 8.

| field | shape | offset | raw meaning | packed (float64) value |
|---|---|---|---|---|
| W | [16][25] | 0 | regulation weights, row = regulated gene | row k and column k (k < 16) zeroed if gene k is inactive |
| b | [16] | 400 | basal expression | 0 if inactive |
| lam | [16] | 416 | rate class x | `lambda = 2^-(1 + clip(rint(x + 3), 0, 6))`, 0 if inactive |
| s0 | [16] | 432 | maternal state x | `g0 = sigma(x)`, 0 if inactive |
| Q | [16] | 448 | partition vector | 0 if inactive |
| act | [16] | 464 | active bit | `1.0 if x > 0.5 else 0.0` |
| A | [23][16] | 480 | readout, column = gene | column k zeroed if inactive |
| a0 | [23] | 848 | readout bias | unchanged |
| Dm | [2] | 871 | packet-rate x | `D_m = (0.9 * sigma(x)) / (D * P_MAX)`, `P_MAX = 3.0`, D = lattice degree |
| km | [2] | 873 | decay x | `k_m = 0.005 + 0.3 * sigma(x)` |

**Neutral padding from ABI 2** (`spec.V3.pad_genomes(rows, spec.V2)`, and `LifeLayout.pad` into
`genome.LIFE_DIMS_ABI3`, which is the same). Every field keeps its entries at their (row, column) places and every new
entry is 0: W columns 22-24 (the receptor trace and the two plane cues), A rows 21-22 and a0 entries 21-22 (zeta and
g_r). A padded genome reads `x[22..24]` with weight 0 and decodes `zeta = g_r = q8(0) = 0`. Padding commutes with
packing on the 2D kinds (packing a padded raw genome gives the padded ABI-2 table; tests). In the gene sum
`p = p + W[k][j] * x[j]`, a padded term adds `+0.0 * x = +0.0` (the inputs are never negative), and `p` is never
`-0.0` (it starts at a packed `b[k]`, which is never `-0.0`), so it is unchanged bitwise.

`spec.V3.pack_genomes(params, kind)` produces the packed table, float64 `[G][875]` with the same offsets, and turns
every `-0.0` into `+0.0`. The kernel never reads the raw genome. The packed table holds no NaN or infinity:
`pack_genomes` raises `ValueError` for a raw genome that holds one, and `life_run` returns -1 for a packed row that
holds one (a NaN readout would otherwise index the knob tables of section 8 out of range). An
inactive gene therefore has `g_k = 0` forever, whether or not the kernel skips it: its update is
`0 + 0 * (s - 0) = 0`, and all its outgoing weights are zero. Unit and block metadata (for crossover and mutation)
are in `spec.V3.GENOME_FIELDS`; the kernel ignores them. `genome.LIFE_DIMS_ABI3` is the matching `LifeLayout`: its
plane-cue columns start random in founders (plane-specific expression was needed for every founder the proposal's
census found), and its receptor-trace column starts at 0, like the n_view column; the census (GB10) calibrates
these priors.

### 4.5 Program table (program mode)
Program mode replaces the readout `theta = decode(A.g + a0)` by a fixed program. It is used for the hand-built
references (R25-v1, the L0-L4 ladder, the CATCH ladder of BODY_DESIGN_PROPOSAL.md 3.2) and for cell-layer tests.
`spec.V3.pack_program` builds float64 `[129]`:
- `[0, 115)`: five decoded phenotype rows of 23 knobs each, in knob order (section 8): `alone`, `contact`,
  `juvenile`, `rim`, `zygote`. Values are used as given (off-grid values allowed, for example `g_r = 0.55`), except
  that `w_eff` is always `q8` of its formula.
- `[115, 129)`: `juv_ticks, nv_rim, zyg_row, flank_gate, p_div_lo, k_grow, timer_step, prune, k_keep, k_die,
  Dm0, Dm1, km0, km1` (`Dm` and `km` already decoded, as in 4.4).
Every entry must be finite (`pack_program` raises `ValueError`, and `life_run` returns -1). Semantics are in
section 7.5. `spec.V3.pad_program(row, spec.V2)` turns an ABI-2 program (`[119]`, 21 knobs per row) into this
table with `zeta = g_r = 0` in every row. Hand-built CATCH bodies fix one row per cell (4.6); the selector does not
read the plane (15.50).

### 4.6 Initial body
If `n_init[i] = 0`, life i starts from one zygote at `(0, 0, 0)` with the selector row. Otherwise `init_cells[i]`
holds `n_init[i] <= 1024` rows `(a, b, z, row)`: initial cell j sits at `(a, b, z)` and gets uid index j. Every
initial cell must be in the stack (`0 <= z < L_max`), have `|a|, |b| <= 2^22`, sit on its own site, and, in a dense
fabric (`fabric_R > 0`), sit inside the disk, since a site outside it is a wall that holds no cell (else -4; 15.57).
In program mode, `row >= 0` fixes that cell's program row for its whole life (`-1` = selector), and a row outside
`[-1, 5)` is an error. In GRN mode `row` is ignored (never checked), and every initial cell starts from `g0`. All initial cells are born at `t0` (7.6). `spec.V3.pack_init`
accepts `(a, b)` (z = 0) or `(a, b, z)` cells. The limit of 1024 (ABI 2: 64) holds the hand-built CATCH bodies: ring
3 (37 columns) is 74 cells in two planes and 148 with two hidden planes, ring 6 is 254 and 508 (15.49).

### 4.7 World vector
float64 `[66]`, keys in `spec.V3.WORLD_KEYS` order. `spec.V3.pack_world` validates and packs it. Times marked (rel)
are relative to `t0`. Keys 0-40 are ABI 2's world vector, unchanged. The defaults of keys 44-65 are CATCH v1
(BODY_DESIGN_PROPOSAL.md 2 and 3.1); a BELL world (kind 0) ignores them, and a CATCH world ignores BELL's lumen keys
15-19.

| # | key | default | meaning |
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
| 38-40 | kill_rate, wound_rate, drift_tau | 0 | reserved (stages v2, v3); must be 0 in ABI 1, 2 and 3 |
| 41 | world_kind | 0 | 0 = BELL-1 lumen (9.2), 1 = CATCH (9.7); integer |
| 42 | L_max | 1 | stack height: sites exist for `0 <= z < L_max` (z = 0 sense plane, 1 act plane, 2+ hidden); integer |
| 43 | stuck_z | 0 | panel: height of the stuck site (stuck_a, stuck_b, stuck_z); integer |
| 44 | sigma | 1.5 | target halo width: luminance `exp(-r^2 / (2 sigma^2))` at distance r from its centre |
| 45 | lam_s | 2.0 | receptor events per sense cell per unit added at the halo's centre |
| 46 | lam_bg | 0.05 | background receptor events per sense cell per unit (sensor noise) |
| 47 | g_n | 1.0 | nudge gain: force per unit of twitch per unit of exposed face |
| 48 | drag_exp | 0.5 | drag `gamma = n_fill ^ drag_exp`, n_fill = the filled footprint (9.7.2; the proposal's n_foot, tweaked by 15.59 and 15.61) |
| 49 | th_click | 0.6 | the hotspot clicks when its twitch crosses this upward while the key is armed |
| 50 | th_rel | 0.25 | the key re-arms when the hotspot's twitch is below this |
| 51 | rho_c | 1.0 | capture radius |
| 52 | v_t | 0.1 | blob speed (run and tumble) |
| 53 | tau_turn | 20.0 | mean time between a blob's turns; 0 = never turns |
| 54-55 | R_min, R_max | 2.0, 6.0 | a placement puts a blob at distance U[R_min, R_max] from the dot |
| 56 | t_resp | 50.0 | mean time between timer re-placements; 0 = no timer |
| 57 | R_cap | 100.0 | income per capture of the target |
| 58 | c_miss | 2.0 | cost per click that hits no blob (the proposal's 1.0 let blind clicking pay; 15.60) |
| 59 | c_rec | 0.001 | cost per delivered receptor event per unit of `abs(g_r)` |
| 60 | b2_amp | 0.0 | second blob (S1 candidates; absent in v1): luminance relative to the target; 0 = no second blob |
| 61 | b2_sigma | 1.5 | second blob's halo width |
| 62 | b2_value | 0.0 | value of a click on the second blob: income if positive, cost if negative |
| 63 | b2_rho | 1.0 | second blob's click radius |
| 64 | b2_p | 1.0 | probability that the second blob is present after a placement |
| 65 | b2_mode | 0 | 0 = placed with the target; 1 = its own timer and its own re-placement after a click; integer |

The lattice kind is a property of the call (the lattice table), not of the world vector. World presets
(`spec.PRESETS`): `bell_v1` and `bell_v1_5` (world kind 0, hex, L_max 1); `catch_v1` and `catch_v1_l4` (world kind 1,
hexprism, L_max 4: the user's design, two hidden planes above the act plane) and `catch_v1_l2` (L_max 2: the control
arm). Every catch_v1 preset is BODY_DESIGN_PROPOSAL.md 3.1 (T 1024, BELL's costs and physics, and keys 44-65 at
their defaults) except recorded tweaks: c_miss 2 instead of 1 (15.60) and the drag's footprint counted over
every plane (15.59) with its holes filled (15.61). `catch_speck` (= `catch_speck_l4`, L_max 4) and `catch_speck_l2`
are the S1 candidate SPECK: the catch_v1 preset of the same L_max with sigma 0.6, R_cap 500 and c_miss 10 (15.62),
every other key catch_v1's (docs/LIFE_GATES.md, gates GS1-GS6). ABI 2 refuses them all as not implemented.

World rules (`spec.V3.validate_world`; the kernel's `world_ok` returns -2 for a vector that breaks any of them):
- every entry is finite, and the reserved entries 38-40 are 0;
- T and t0 are integers with `0 < T <= 2^30` and `|t0| <= 2^30`, so every time in a life is resolved to `2^-21` or
  finer; n_max, e_max, fabric_R, oracle_cap, stuck_a, stuck_b, world_kind, L_max, stuck_z and b2_mode are integers;
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
- drop_p and kill_frac lie in `[0, 1]`, and `0 <= noise_rate <= 1024`;
- world_kind is 0 or 1; `1 <= L_max <= 8`; `0 <= stuck_z < L_max`;
- `0 < sigma <= 2^20` and `0 < b2_sigma <= 2^20`; lam_s, lam_bg and b2_amp are non-negative and
  `lambda_max = lam_bg + lam_s * (1.0 + b2_amp) <= 1024`;
- g_n and v_t lie in `[0, 1024]` and drag_exp in `[0, 2]`; `0 <= th_rel < th_click <= 1`;
- rho_c and b2_rho are non-negative and `0 <= R_min <= R_max <= 2^20`; tau_turn and t_resp lie in `[0, 2^30]`
  and are each either 0 (off) or at least `2^-10` (15.58);
- R_cap, c_miss and c_rec are non-negative; b2_value is any finite number; b2_p lies in `[0, 1]`; b2_mode is 0 or 1.

The rules of keys 41-65 hold for every world kind (a BELL world carries the CATCH defaults), so whether a vector is
valid never depends on its kind. `spec.V2.validate_world` raises `NotImplementedError` for a world that needs ABI 3
(world kind 1, a prism lattice, L_max > 1 or stuck_z > 0) and `ValueError` for the ABI-3 flag bits.

So every message delay, every tick period and every mean world-timer interval is at least `2^-10`, time always advances (6.3), and the lumen of 9.2
and the dot of 9.7 stay finite (the speed caps keep `|X|` below about 2^64 within T <= 2^30). (Before these rules, `P0 = 0` put every tick at one instant and `life_run` never returned, and
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
float64 `[n_lives][57]`, columns in `spec.V3.LEDGER` order. "Counted" columns include only records (and world
events, samples) with `t >= t0 + t_open`. The other columns cover the whole life. Columns 0-34 are ABI 2's; columns
35-50 are 0 in a BELL life. "CATCH" marks columns that only a CATCH life fills.

| # | column | counted | definition |
|---|---|---|---|
| 0 | income | yes | BELL: integral of `h_inc * n * max(0, -dR/dt)` (9.2); CATCH: `R_cap` per capture plus `b2_value` per click on a positive second blob (9.7.4) |
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
| 12 | cost | yes | running sum of every charge in canonical order (9.3), including the CATCH charges (9.7) |
| 13 | guard_charge | - | `c_live * n_max * (t1 - t_end)` if a guard tripped, else 0 |
| 14 | net | - | `income - colcost - guard_charge` (9.5) |
| 15 | F | - | `net / (T - t_open)` |
| 16 | n_end | - | live cells at t_end |
| 17 | n_peak | - | max live cells after any time group |
| 18 | t_end | - | end of the life: t1, or the guard time |
| 19 | status | - | bit field (4.12) |
| 20 | events | - | guard event counter at t_end (section 10) |
| 21 | beats | yes | BELL: upward crossings of P through th (0 in CATCH) |
| 22 | P_int | yes | BELL: integral of P dt (0 in CATCH) |
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
| 35 | captures | yes | CATCH: clicks within rho_c of the target (9.7.4) |
| 36 | misses | yes | CATCH: clicks that hit no blob (each charged c_miss) |
| 37 | clicks | yes | CATCH: all clicks |
| 38 | b2_clicks | yes | CATCH: clicks on the second blob (each worth b2_value) |
| 39 | respawns | yes | CATCH: timer re-placements of the target (9.7.3) |
| 40 | nudges | yes | CATCH: act-plane twitches with dz > 0 and a nonzero exposed face (9.7.2) |
| 41 | rec_cand | yes | CATCH: receptor candidates (R_RCAND records) |
| 42 | rec_accept | yes | CATCH: candidates accepted by the world (RECEPTOR events sent) |
| 43 | rec_events | yes | CATCH: RECEPTOR events delivered (7.10) |
| 44 | rec_gain | yes | CATCH: sum of `abs(g_r)` over delivered events (each unit charged c_rec) |
| 45 | samples | yes | CATCH: integer sample times (9.7.6) |
| 46 | dist_sum | yes | CATCH: sum over samples of the dot-to-target distance |
| 47 | zone_samples | yes | CATCH: samples with the target within rho_c of the dot |
| 48 | path | - | CATCH: length of the dot's path |
| 49 | X_end | - | CATCH: dot position at t_end, x |
| 50 | Y_end | - | CATCH: dot position at t_end, y |
| 51 | n_S_end | - | live cells at t_end at z = 0 |
| 52 | n_M_end | - | live cells at t_end at z = 1 |
| 53 | n_H_end | - | live cells at t_end at z >= 2 |
| 54 | live_S | yes | cell-time at z = 0 (live_time's share of the sense plane) |
| 55 | live_M | yes | cell-time at z = 1 |
| 56 | live_H | yes | cell-time at z >= 2 (hidden planes) |

Morphogen conservation: `morph_secreted = morph_decayed + morph_lost + morph_content_end + morph_inflight_end`, up to
float rounding (the tests use a relative tolerance of 1e-12).

### 4.10 Hashes
uint64 `[n_lives][5]`: `all, spikes, fate, chem, world` (section 9.6). Each family starts at
`HASH_INIT = 0x243F6A8885A308D3`. `world` folds the CATCH world's records and events; it stays `HASH_INIT` in a BELL
life.

### 4.11 Raster and fate log
- Raster: one entry per spike, written by the accountant in canonical order: `raster_t[i][j] = t`,
  `raster_uid[i][j] = uid`. `raster_n[i]` is the total number of spikes in the life, which may exceed the capacity.
  Only the first `raster_cap` entries are stored, and overflow sets a status bit.
- Fate log: one entry per birth (including initial cells), death and rejected claim, in canonical order.
  - `fate_i[i][j][7] = kind, uid, mother, a, b, aux, z`. Kinds: 1 birth, 2 death, 3 reject. `aux` is the birth
    index k for a birth, the cause for a death (1 apoptosis, 2 prune, 3 kill), and 0 (occupied) or 1 (wall) for a
    reject. `z` (appended in ABI 3, so the first six columns are ABI 2's) is the site's height.
  - `fate_f[i][j][18] = t, age, g[16]`: `g` at birth or at death (zeros for rejects and in program mode); `age` is
    `t - t_birth` for deaths, 0 otherwise.
  - For a reject, `uid` is the would-be daughter, `mother` is the claimant, and `(a, b, z)` is the target site.

### 4.12 Status bits (ledger column 19, an integer stored as a double)
`1` extinct; `2` guard_cells; `4` guard_events; `8` raster_overflow; `16` fate_overflow; `32` chem_clamp (at least
once); `64` ledger_mismatch (`|cost - colcost| > 1e-9 * max(1, |colcost|)`); `128` capacity (an implementation limit
was reached; the life is invalid and must not be used); `256` wall (at least one wall reject).

## 5. State

### 5.1 Site (persistent: it outlives its occupants)
- `sk` (site key) and `(a, b, z)`, with `0 <= z < L_max`.
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
- Traces: `f`, `r[2]`, `rho` (receptor trace, ABI 3), anchor `t_tr`.
- Twitch: `z`, anchor `t_z`.
- Genes and chemistry: `g[16]`, `m[2]`, inbox (packets that have arrived: `t_arr`, sender uid, slot, `amt[2]`,
  `conc[2]`).
- Phenotype: `theta[23]`, the effective membrane time constant `tau = theta.tau_m * taumis`, and `w_eff[D][2]`.
- Frozen physics: `taumis`, `P_n`.
- Clock: `t_prev` (last tick time, or `t_birth`).
- Division: `claim_pending` (0 or 1).
- Program mode: `timer` and `timer_birth`.
- Receptor (CATCH, z = 0 only): `rec#`, the index j of the cell's next receptor candidate (7.10).

### 5.3 Life (owned by the accountant)
World: BELL `(A, R, t_w, above)` (9.2) or CATCH (9.7.1); `n` (live cells) and the live cells per plane; `inflight`
(claims sent and not yet resolved); ledger columns; hashes; logs; `extinct`; `t_end`.

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
| 3 MEMBRANE | RCAND | self (uid) | - | j: the candidate's index (CATCH, z = 0; 7.10) |
| 3 MEMBRANE | RECEPTOR | uid | d_min, from the world (9.7.5) | j (CATCH; 7.10) |
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
3. **MEMBRANE**: first the current RCAND (if any) emits its record (7.10), then all delivered RECEPTORs, ARRIVALs,
   NOISE kicks and the current THRESHOLD (if any) form one membrane step (7.2) with one summed input and one
   threshold test. The records of this group are emitted in the order R_RCAND, R_RECEPT, R_SPIKE.
4. **TICK** (7.4 / 7.5).
5. **EXO**: KILL, then STUCK (7.9).

Within a group, events whose order matters are sorted by the keys above. The other groups are order-free: arrivals
sum exactly, claims are sorted by daughter uid, and packets are consumed later in `(t_arr, sender uid)` order.

### 6.3 Causality contract
- Every message delay is `>= d_min`.
- Self events (THRESHOLD, TICK, NOISE, RCAND, KILL, STUCK) can be created inside a batch only for a time strictly
  later than the batch, by construction: `t* > t0` in PREDICT (7.1); tick periods are at least `2^-10` (world
  rules, 4.7), and every time in a life is resolved to `2^-21`; and a first tick, noise kick or receptor candidate
  that would round to the batch time is moved to `nextup(t)`.
- The accountant reads cells only through records stamped with the batch time. In BELL nothing flows back from the
  world to cells. In CATCH the world's only effect on cells is a RECEPTOR event, which the accountant creates while
  it consumes a record stamped `t` and which arrives at `t + d_min` (9.7.5), so it obeys the same floor as a message.
Hence a site's batch at t depends only on events created before `t - d_min` elsewhere (the world included), and on
its own past.

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
traces to t:  e = exp(-(t - t_tr) / theta.tau_tr); f = f * e; r[0] = r[0] * e; r[1] = r[1] * e
              rho = rho * e; t_tr = t                                   # rho: ABI 3 (0 forever outside CATCH)
```
PREDICT is called after every membrane step that does not fire, after every FIRE, at every tick (after the phenotype
update) and at birth. A predicted crossing is always strictly after `t0`, and `t0` is never before the current batch
time. Traces are re-anchored only at: batches with at least one delivered ARRIVAL or delivered RECEPTOR, FIRE, and
TICK (and set to 0 at birth). The twitch is re-anchored only at FIRE with `kappa > 0`. The membrane is re-anchored only at the membrane
step, FIRE, the tick re-anchor and birth. Re-anchoring at other times would change the rounding, so it is forbidden.

### 7.2 Membrane step (batch group 3)
Let `Arr` be the delivered ARRIVALs, `Kick` the NOISE kicks, `thr` true iff a current THRESHOLD is in the batch, and
`n_rec` the number of delivered RECEPTORs (7.10; 0 outside CATCH). The step runs if any of the four is present.
```
if n_rec > 0: emit R_RECEPT(uid, n_rec, theta.g_r)                 # before the step, so before any R_SPIKE
if Arr is nonempty or n_rec > 0:
    traces to t;  r[c] = r[c] + count_c   for c = 0, 1   (count_c = arrivals whose mask has bit c)
    rho = rho + (double) n_rec
if t < t_r: return                                       # refractory: input lost, traces already counted
S = sum over Arr of sum_c bit_c(mask) * w_eff[slot][c]  +  sum over Kick of kick      (exact)
if n_rec > 0: S = S + theta.g_r * (double) n_rec          # one rounding, after the exact sum
v = (thr ? 1.0 : vnow(t)) + S
v_a = q10(v); t_a = t
if v_a >= 1.0: FIRE(t) else PREDICT
```
A current THRESHOLD contributes exactly 1.0, so a crossing predicted for this instant is subsumed. It fires unless
same-instant inputs pull the sum below 1. Arrivals and receptor events received while refractory still count in the
traces (and a receptor event is still charged). Without receptor events the step is ABI 2's, operation for
operation. `n_rec` is almost always 0 or 1: a cell's candidates have strictly increasing times, and two of them can
reach the same delivery time only if `c + d_min` rounds two neighbouring doubles together.
`arrivals += |Arr|` and `arrivals_dropped += (dropped arrivals)` are integer counters (counted if
`t >= t0 + t_open`).

### 7.3 FIRE(t)
```
v_a = 0.0; t_a = t; t_r = t + theta.t_ref
traces to t; f = f + 1
spike# += 1
n_live = #{d : view[d] != EMPTY};  n_ch = theta.emit0 + theta.emit1;  n_out = n_live * n_ch
if n_ch > 0 and not F(contacts_off) and not (F(hidden_off) and z >= 2):
    for d = 0 .. D-1 with view[d] != EMPTY:
        if F(lateral_off) and off_z[d] == 0: continue                       # ABI 3 forks (12)
        if drop_p > 0 and draw(seed, S_DROP, uid, spike#, d) < drop_p: continue
        u = draw(seed, S_JIT, uid, spike#, d)
        dl = dc[d] * (1.0 + jit * (2.0 * u - 1.0)) + theta.delta
        if dl < d_min: dl = d_min
        send ARRIVAL(target view[d], mask = emit0 | emit1 << 1) through d, at t + dl
dz = 0.0; zt = 0.0; zn = 0.0
if theta.kappa > 0:
    zt = z * exp(-(t - t_z) / tau_z);  zn = zt + theta.kappa;  if zn > 1.0: zn = 1.0
    dz = zn - zt;  z = zn;  t_z = t
emit R_SPIKE(uid, kappa, n_out, dz, zt, zn)
PREDICT
```
Costs are charged by the accountant on R_SPIKE, including when `contacts_off`, `lateral_off`, `hidden_off` or drops
suppress delivery. The twitch is the cell's own (every plane); only the CATCH world turns an act-plane twitch into a
pull or a click (9.7.2), and it reads `zt` and `zn` from the record, never from the cell. A spike
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
   flank(e) = [view[prev[e]] != EMPTY] + [view[next[e]] != EMPTY]                  # placement, step 8
   flank_best = max over open e of flank(e); 0 if no slot is open                  # program mode only (7.5)
   x[0..15] = g;  x[16+i] = m[i] / (1.0 + m[i]);  x[18] = f / theta_prev.tau_tr;  x[19+c] = r[c] / theta_prev.tau_tr
   x[21] = (double) n_view / (double) D                              # ABI 2: no flank_best input (15.32)
   x[22] = rho / theta_prev.tau_tr                                   # ABI 3: receptor trace (0 outside CATCH)
   x[23] = (world_kind == 1 and z == 0) ? 1.0 : 0.0                  # is_S: the cell touches the screen
   x[24] = (world_kind == 1 and z == 1) ? 1.0 : 0.0                  # is_M: the cell is in the act plane
   if F(genes_blind): x[18..22] = 0.0                                # the plane cues stay (15.38)
4. if not (F(identity_clamp) or F(freeze)):
       for k = 0..15: p = b[k]; for j = 0..24: p = p + W[k][j] * x[j];  s[k] = sigma(p)
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
           emit R_PACKET(uid, view[d], sitekey((a, b, z) + off[d]), amt)
       for i = 0, 1:  m[i] = m[i] - n_view * amt[i]
   emit R_CHEM(sec, dec, clamp)
8. if not (F(division_off) or F(freeze)) and claim_pending == 0 and some slot is open (4.3)
      and theta.p_div > 0 and draw(seed, S_DIV, uid, tick#) < theta.p_div
      and (oracle_cap == 0 or cap_count < oracle_cap):        # heap only; cap_count = (n_alive + n_inflight)(t-), 11.3
       px = 0.0; py = 0.0; pz = 0.0
       for d = 0..D-1: px = px + s_d * unit[d][0]; py = py + s_d * unit[d][1]; pz = pz + s_d * unit[d][2]
       vx = px - theta.chi * py;  vy = py + theta.chi * px;  vz = pz        # p + chi * J p, J = +90 degrees in-plane
       for open e = 0..D-1:
           if off_z[e] == 0:                                                 # in-plane slot: ABI 2's score
               score(e) = unit[e][0] * vx + unit[e][1] * vy + theta.phi * flank(e)
                          + 1e-3 * draw(seed, S_PLACE, uid, div#, e)
           else:                                                             # up or down (prisms only)
               score(e) = unit[e][2] * vz + theta.zeta * unit[e][2]
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
- "Open" is 4.3's: in stack and EMPTY. A slot that points out of the stack is never open, so it is never claimed,
  never counts for "some slot is open", and never enters flank_best.
- Vertical placement (ABI 3, 15.37): `pz` is the vertical component of the same morphogen polarity vector, so a
  vertical gradient steers up and down exactly as an in-plane gradient steers within the plane, and `zeta`
  (knob 21) adds a genetic bias toward up (`zeta > 0`) or down. The chiral term rotates within the plane only. On a
  2D lattice no slot is vertical and the step is ABI 2's, operation for operation (the extra `pz` sum is unused).
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
exists   = (fabric_R == 0) or lattice.in_disk(base kind, a, b, fabric_R)   # claims only reach in-stack sites
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
    reset: view = EMPTY, inc = 0, m = 0, inbox empty, counters 0 (rec# too), claim_pending = 0
           v_a = 0.0; t_a = t; t_r = t; f = r = rho = 0.0; t_tr = t; z = 0.0; t_z = t; t_prev = t; t_birth = t
    g = payload genes (GRN; g0 for initial cells), or timer = timer_birth = payload (program mode)
    theta = decode(readout(g)) or row(selector); w_eff and s_d with every slot empty (s_d = 0)
    emit R_BIRTH(uid, mother, k, initial)
    PREDICT
    t1 = F(lockstep) ? t0 + P0 * (floor((t - t0) / P0) + 1.0) : t + U * P_n;   if t1 <= t: t1 = nextup(t)
    schedule TICK at t1
    panel self events (7.9)
    if world_kind == 1 and z == 0 and lambda_max > 0:                    # the receptor's candidate stream (7.10)
        schedule RCAND(uid, 0) at receptor_next(seed, uid, 0, t, lambda_max)
    for d = 0..D-1 in stack: send BORN(uid, k) through d, at t + d_min
    if mother != 0: send ACK(target mother; uid, k) through bslot, at t + d_min
```
Initial cell j has `uid = hash64(seed, S_ZYG, j) | 1`. All initial cells are born at `t0`, each birth being its
site's batch at `t0`, so their records follow the canonical order like any others. R_BIRTH carries the site
`(a, b, z)` (every record does, through its site key), which the CATCH accountant needs (9.7).

### 7.7 Notices (batch group 1)
Let `d` be the receiver slot, and `nb = (a, b, z) + off[d]` the sender's site. Notices only travel through
in-stack slots, so `nb` is always in the stack.
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
for d = 0..D-1 in stack: send DIED(uid) through d, at t + d_min
```
- Pending self events become stale (a sense cell's next RCAND among them).
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
- **stuck_t** (>= 0): a cell born at `(stuck_a, stuck_b, stuck_z)` before `t0 + stuck_t` schedules STUCK at
  `t0 + stuck_t`.
  At STUCK, the membrane is re-anchored as in TICK step 5 (re-anchor, and FIRE if it reaches 1). Then the cell is
  stuck for life: now and after every later phenotype update, `theta.b = 2, theta.tau_m = 1, theta.t_ref = 0.5` and
  `w_eff = 0` (it fires tonically and ignores input), followed by PREDICT. Receptor input still reaches a stuck
  cell's membrane (it is not a weight), but a stuck cell fires tonically anyway.

### 7.10 Receptors: candidates and deliveries (CATCH, cell side)
Only cells at `z = 0` have a receptor, and only in a CATCH world (rule N1 of the proposal). The world's part, the
thinning and the RECEPTOR it sends, is 9.7.5.
```
candidate stream (scheduled at BIRTH, 7.6; lambda_max = lam_bg + lam_s * (1.0 + b2_amp)):
    c_0 = receptor_next(seed, uid, 0, t_birth, lambda_max)
    receptor_next(seed, uid, j, t_prev, lam) = t_prev - log(draw(seed, S_RCAND, uid, j)) / lam,
                                               moved to nextup(t_prev) if it does not exceed t_prev
RCAND(uid, j) at c_j (group 3, self; stale if the cell is gone):
    emit R_RCAND(uid, j)                                    # first record of the batch's group 3
    rec# = j + 1
    schedule RCAND(uid, j + 1) at receptor_next(seed, uid, j + 1, c_j, lambda_max)
RECEPTOR(uid, j) at c_j + d_min (group 3, from the world; addressed to uid):
    delivered iff uid is the live occupant at t-, not F(receptor_off), and theta.g_r != 0
    (a RECEPTOR that is not delivered vanishes: no trace, no input, no record, no charge)
    the delivered RECEPTORs of the batch enter the membrane step (7.2) as n_rec
```
- A candidate changes nothing in the cell. It only asks the world, through its record, whether the screen point under
  the cell emits an event at `c_j` (9.7.5). The stream runs for every live sense-plane cell, whatever its phenotype,
  so the sequence `c_j` is a property of the cell's birth alone.
- A delivered event adds `theta.g_r` (the phenotype in force at delivery, signed, decoded on the 1/8 grid) to the
  membrane and 1 to the receptor trace `rho`, which decays like `f` and `r` and reaches the genes as `x[22]`. A cell
  whose `g_r` is 0 has no receptor: it receives nothing and pays nothing (15.40).
- Each delivered event is charged `c_rec * abs(g_r)` on R_RECEPT (9.7.5), refractory or not.
- The batch's R_RCAND (at most one: a cell's candidate times strictly increase) precedes its R_RECEPT, which precedes
  any R_SPIKE of the same batch (6.2).

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
| 21 | zeta | `q8(y)` |
| 22 | g_r | `q8(y)` |

Rows 21 (`zeta`, the vertical placement weight of 7.4 step 8) and 22 (`g_r`, the signed receptor gain of 7.10) are
ABI 3's; rows 0-20 decode exactly as in ABI 2. `kappa` (row 8) stays the single effector knob: in CATCH an act-plane
cell's twitch is its motor and, at the hotspot, its key press (9.7.2).

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
| R_BIRTH | uid, mother, k, initial, g | world: BELL world_adv(t), CATCH 9.7.2; `n += 1` and the plane's count `+= 1`; if not initial: `births += 1`, `last_birth = t`; fate log |
| R_SPIKE | uid, kappa, n_out, dz, zt, zn | counted: `spikes += 1; kappa_sum += kappa; contact_events += n_out; cost = cost + c_spike; cost = cost + c_tw * kappa; cost = cost + c_msg * n_out`. If kappa > 0: BELL: world_adv(t); `A = A + dz`; if `above == 0` and `A / n > th`: `above = 1` and (counted) `beats += 1`; CATCH: the stroke of 9.7.2 if the cell is at z = 1. Raster |
| R_TICK | uid, t_prev, sp (TICK step 2; also at a KILL, 7.9) | if `t > t_open_abs`: `dl = t - max(t_prev, t_open_abs)`; `live_time += dl; sec_int += sp * dl; cost = cost + c_live * dl; cost = cost + c_sec * (sp * dl)`; and `live_S`, `live_M` or `live_H` (by the cell's plane) `+= dl` |
| R_CHEM | sec, dec, clamp | `morph_secreted += sec; morph_decayed += dec`; if clamp: status chem_clamp bit; counted: `chem_clamps += clamp` |
| R_PACKET | sender, target, target sk, amt | counted: `packets += 1`; remembered as in flight with `t_arr = t + d_min` (9.4) |
| R_LOST | sender, target, amt | `morph_lost = morph_lost + amt[0] + amt[1]` (emitted by the target site at arrival time) |
| R_CLAIM | mother, daughter, target sk | `inflight += 1`; counted: `claims += 1; cost = cost + c_div` |
| R_RESOLVE | daughter, mother, result | `inflight -= 1`; if result == 2: status wall bit; counted: `rejects += (result == 1); rejects_wall += (result == 2)`; reject: fate log |
| R_DEATH | uid, cause, zt, content, age, g | BELL: world_adv(t); `A = A - zt`; `if A < 0: A = 0`; then `n -= 1` (and the plane's count); BELL: `if n == 0: A = 0`; CATCH: 9.7.2; counted: deaths or kills `+= 1`; `morph_lost = morph_lost + content`; fate log |
| R_RCAND | uid, j | CATCH (9.7.5): counted `rec_cand += 1`; the thinning test at the left limit; if accepted: counted `rec_accept += 1`, and the world sends RECEPTOR(uid, j) to the cell's site at `t + d_min` |
| R_RECEPT | uid, n_rec, g_r | CATCH (9.7.5): counted: `rec_events += n_rec`; `ga = abs(g_r) * (double) n_rec`; `rec_gain = rec_gain + ga`; `cost = cost + c_rec * ga` |

`t_open_abs = t0 + t_open`. A cell's **plane** is S (z = 0), M (z = 1) or H (z >= 2); the plane counts give
`n_S_end`, `n_M_end` and `n_H_end` at close. In a BELL life on a 2D lattice every cell is in plane S, so
`live_S = live_time` bitwise (the same additions in the same order). `last_birth` starts at `t0` and `t_ext` at -1. Integer columns (`arrivals`,
`arrivals_dropped`, `ticks`, `events`) may be counted at the site, because integer sums are order-free. The raster and
fate log set their overflow bits when a capacity is exceeded.

### 9.2 World kind 0: the BELL-1 lumen
State: `A` (the sum of z over live cells, all decaying with `tau_z`), `R` (fill, `R(t0) = 1`), `t_w` (anchor,
`t0`) and `above` (0). `P = A / n`. The world reads cells only through records, which are left limits, and sends
nothing to cells. This section is ABI 2's, unchanged; in a CATCH life none of it runs (income, beats and P_int come
from 9.7 or stay 0).
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
- Charges are added to `cost` in record order with the exact expressions of 9.1 and 9.7, so `cost` is the running
  sum of every action's charge (in CATCH also `c_miss` per miss, `c_rec * abs(g_r)` per delivered receptor event and
  `-b2_value` per click on a negative second blob, at the moment they happen). Apoptosis has no cost. Cells hold no
  energy.
- `t_open` opens the ledger for late-window measurements and forks. Intervals that straddle it are split exactly
  (`world_adv` and R_TICK), and spikes, claims, clicks, receptor events and samples before it are not counted. The
  `morph_*` columns, `n_*`, `t_*`, `status`, `events`, `last_birth`, `path`, `X_end` and `Y_end` always cover the
  whole life. The CATCH world itself (the dot, the blobs, the key) runs the same whether or not the ledger is open.

### 9.4 Packets in flight
The accountant remembers each R_PACKET with `t_arr = t + d_min` (the same float sum as the kernel's) until the
accountant's time passes `t_arr`. On arrival, the target site emits nothing if the packet is delivered and R_LOST if
it is not. At close, `morph_inflight_end` is the sum over the remembered packets with `t_send < t_end <= t_arr` of
`amt[0] + amt[1]`. The packets are taken in increasing `(t_arr, target sk, sender uid)`, and the sum is accumulated
as `s = s + amt[0]; s = s + amt[1]`.

### 9.5 Close
At `t_end` (section 10), after the last time group with `t < t_end`:
```
BELL: world_adv(t_end)
CATCH: the remaining timeline steps before t_end (9.7.1: samples at integer c < t_end, world events at tau < t_end),
       then dot_adv(t_end); X_end = X; Y_end = Y
for each live cell in increasing sk:
    process a closing R_TICK(uid, t_prev, theta.sec0 + theta.sec1) stamped t_end       # living cost up to t_end
    morph_content_end = morph_content_end + content                                    # as in APOPTOSIS
morph_inflight_end (9.4)
guard_charge = guard tripped ? c_live * n_max * (t1 - t_end) : 0.0                  # n_max: world key 26
colcost = c_live*live_time + c_spike*spikes + c_tw*kappa_sum + c_msg*contact_events + c_div*claims + c_sec*sec_int
          + c_miss*misses + c_rec*rec_gain + c_b2*b2_clicks
          (accumulated left to right in this order; c_b2 = b2_value < 0 ? -b2_value : 0.0)
net = income - colcost - guard_charge;  F = net / (T - t_open)
status |= ledger_mismatch if |cost - colcost| > 1e-9 * max(1, |colcost|)
n_end = n; n_S_end, n_M_end, n_H_end = the plane counts; t_end; events; t_ext
```
In a BELL life the three CATCH terms of colcost are `+0.0` each, which leaves colcost (never `-0.0`) bitwise ABI 2's.
`spec.V3.column_cost` and `spec.V3.fitness` re-price a finished ledger under another cost table with the same
expressions.

### 9.6 Logs and hashes
The raster and the fate log are written as the records are consumed (canonical order). The five hash families are
`h = splitmix64(h ^ w)` folded over the words `w` of each record or world event, in the accountant's order (canonical
order for records, the timeline of 9.7.1 for world events), starting from `HASH_INIT`:

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
| R_RCAND | 9, bits(t), uid, j, accepted (0 or 1) | world, all |
| R_RECEPT | 10, bits(t), uid, n_rec, bits(g_r) | world, all |
| CLICK (9.7.4) | 11, bits(t), outcome (0 miss, 1 capture, 2 second blob), bits(X), bits(Y) | world, all |
| PLACE (9.7.3) | 12, bits(t), blob, cause (0 start, 1 click, 2 timer, 3 with the target), bits(x_b), bits(y_b), present | world, all |
| TURN (9.7.3) | 13, bits(t), blob, bits(vx_b), bits(vy_b) | world, all |

Closing R_TICKs are not hashed. At close, `all` also folds `bits(ledger[c])` for c = 0..56 (ABI 2: 0..34). Two runs
agree on a family iff they produced the same records and world events with bitwise-identical words; test T1 compares
all five plus the ledger. In a BELL life the world family stays `HASH_INIT`, and spikes, fate and chem are ABI 2's.

### 9.7 World kind 1: CATCH (BODY-1 v1)
The body is the dot: a point `(X, Y)` on an unbounded screen that only translates. Every cell sits at the fixed
offset `planar(a, b)` (4.3) of its site in the dot's frame, whatever its height. The screen holds the target (blob 0)
and, only if `b2_amp > 0`, a second blob (blob 1, reserved for the S1 candidates; absent in v1). Sense-plane cells
(z = 0) receive receptor events from the screen point under them; act-plane cells (z = 1) pull the dot with their
twitches; the act cell at the hotspot `(0, 0, 1)` clicks. All of this is computed by the accountant from records, in
closed form; nothing here is stepped numerically, and no cell reads any of it. The functions named here are
`spec.py`'s (`dot_gain`, `blob_heading`, `blob_place`, `blob_present`, `poisson_next`, `halo`, `receptor_rate`,
`receptor_accepts`, `exposed_face`, `key_step`, `lambda_max`) and are the exact expressions both implementations use.

#### 9.7.1 State, start and timeline
```
dot:     t_x (anchor time), X, Y (position at t_x), Fx, Fy (total force at t_x), n_foot (live cells at z = 0), gam
body:    P (the columns (a, b) with a live cell in any plane: the projected footprint), n_fill (the filled footprint)
strokes: per act-plane site with a live occupant: fx, fy, t_f (the occupant's own pull, decaying from t_f)
O:       the set of act-plane sites (a, b) (z = 1) with a live occupant, as at the left limit of the time group
key:     armed
blob b:  exists (b = 0 always; b = 1 iff b2_amp > 0); present (blob 0 always; blob 1 from its placement draw);
         t_b, x_b, y_b (anchor), vx_b, vy_b (velocity); counters h_b (next heading), q_b (next placement);
         tau_b, k_b (next turn time and index); r_b, m_b (next timer time and index)
lambda_max = lam_bg + lam_s * (1.0 + b2_amp)
```
Start, before the first time group (the initial births are records of the group at t0):
```
X = Y = Fx = Fy = 0.0;  t_x = t0;  n_foot = 0;  P = {};  n_fill = 0;  gam = 1.0;  armed = 1
for each existing blob b, in increasing b:
    (vx_b, vy_b) = blob_heading(seed, b, 0, v_t);  h_b = 1
    tau_b = tau_turn > 0 ? poisson_next(seed, S_TURN, b, 0, t0, tau_turn) : +inf;  k_b = 1
    r_b = (t_resp > 0 and (b == 0 or b2_mode == 1)) ? poisson_next(seed, S_RTIME, b, 0, t0, t_resp) : +inf;  m_b = 1
for each existing blob b, in increasing b: PLACE(b, 0, t0)            # around the dot at (0, 0)
```
**Timeline.** Besides the time groups of records, the CATCH accountant has two steps of its own: **world events**
(every blob's turns at `tau_b` and timer re-placements at `r_b`) and **samples** (at every integer time c with
`t0 < c < t_end`, 9.7.6). It runs all three in time order, and at one instant x in this order:
1. the sample at x, if x is a sample time;
2. the time group of records at x, in canonical order, then the group's deferred actions (the changes of O, then
   the placements caused by its click, 9.7.2 and 9.7.4);
3. the world events at x, ordered by (kind: timer before turn, then blob).

`world_to(t)` runs every world event with a time below t, in that order. The accountant calls it at the start of
every time group and before every sample. So every record and every sample at t reads the world as it was just
before t (the left limit), and a world event at exactly t takes effect after the records at t. Every sample time c
is a guard-check time of section 10 (after every record with `t < c`, before any event at `t >= c`), so an
implementation takes the sample there, unless the guard trips at c, and takes the remaining samples and world events
before `t_end` at close (9.5). Both schedulers present the same sequence of time groups and guard checks to the
accountant, so its arithmetic, folds and RECEPTOR events are identical.

**Closed forms of the dot.** Between two anchor moves every act-plane twitch decays with the same `tau_z`, so the
total force is `F(t) = F(t_x) exp(-(t - t_x) / tau_z)`, the overdamped dot moves with `V = F / gam`, and
`X(t) - X(t_x) = F(t_x) tau_z (1 - e) / gam` exactly. The direction is constant between anchor moves, so the path
increment is `|X(t) - X(t_x)|`.
```
dot_at(t):                         # t >= t_x; evaluated, the anchor does not move
    if n_foot == 0 or t == t_x: return (X, Y)                # no foot on the screen, no traction (15.44); at the anchor
    (k, e) = dot_gain(t - t_x, tau_z, gam)                   # e = exp(-dt / tau_z); k = tau_z * (1.0 - e) / gam
    return (X + Fx * k, Y + Fy * k)
dot_adv(t):                        # moves the anchor to t
    if t <= t_x: return
    e = exp(-(t - t_x) / tau_z)
    if n_foot > 0:
        k = tau_z * (1.0 - e) / gam;  dx = Fx * k;  dy = Fy * k
        X = X + dx;  Y = Y + dy;  path = path + sqrt(dx * dx + dy * dy)
    Fx = Fx * e;  Fy = Fy * e;  t_x = t
gam = pow((double) n_fill, drag_exp)                         # recomputed whenever P changes and n_fill > 0 (9.7.2)
blob_at(b, t):  dt = t - t_b;  return (x_b + vx_b * dt, y_b + vy_b * dt)
```
`tau_z * (1.0 - e) / gam` is `(tau_z * (1.0 - e)) / gam`. `dot_at` from an older anchor and `dot_adv` compute the
same `X + Fx * k`, so a record that reads the dot after another record of its group moved the anchor gets the same
bits. Drag grows with the square root of the footprint (rule N6): thrust comes from the rim (about sqrt(n) cells), so
the top speed does not depend on body size and growth buys sensing reach, not speed. The footprint is the body's
extent on the screen, the filled footprint of 9.7.2 (tweaks 15.59 and 15.61 of the proposal's sense-plane count).

#### 9.7.2 Bodies and strokes (rules N1, N3, N5)
Actions on the records of a time group at t (after `world_to(t)`):
```
R_BIRTH at (a, b, z):
    dot_adv(t)
    if no other live cell in column (a, b), any plane:                                   # 15.59, 15.61
        add (a, b) to P;  n_fill = filled_footprint(P);  gam = pow((double) n_fill, drag_exp)
    mark (a, b, z) live
    if z == 0: n_foot += 1
    if z == 1: (fx, fy, t_f) of (a, b) = (0.0, 0.0, t);  defer "add (a, b) to O"
R_DEATH at (a, b, z):
    dot_adv(t)
    mark (a, b, z) not live
    if no live cell left in column (a, b):
        remove (a, b) from P;  n_fill = filled_footprint(P);  if n_fill > 0: gam = pow((double) n_fill, drag_exp)
    if z == 0: n_foot -= 1
    if z == 1: e_i = exp(-(t - t_f) / tau_z);  Fx = Fx - fx * e_i;  Fy = Fy - fy * e_i;  defer "remove (a, b) from O"
R_SPIKE at (a, b, 1) with kappa > 0, unless F(motor_off) at t:          # a stroke of an act-plane cell
    dot_adv(t)
    nx = 0.0;  ny = 0.0
    for each in-plane slot d in increasing order:
        if (a + off_a[d], b + off_b[d]) is not in O: nx = nx + unit[d][0];  ny = ny + unit[d][1]
    if dz > 0 and (nx != 0.0 or ny != 0.0):
        gdz = g_n * dz
        e_i = exp(-(t - t_f) / tau_z)
        fx = fx * e_i + gdz * nx;  fy = fy * e_i + gdz * ny;  t_f = t
        Fx = Fx + gdz * nx;  Fy = Fy + gdz * ny
        counted: nudges += 1
    if (a, b) == (0, 0): the key step of 9.7.4, with the record's zt and zn
end of the time group: apply the deferred changes of O, in record order
```
- **The surface-normal pull.** `n` is the cell's exposed face: the sum of the unit vectors toward its in-plane
  neighbour sites in the act plane that hold no live cell (a wall of a dense fabric counts as empty). A rim cell pulls
  the dot toward its open side, an interior cell (`n = 0`) cannot pull, and an isolated cell has `n = 0` exactly (the
  six hex vectors cancel exactly in slot order). Summed over any body the faces cancel, because every shared face is
  counted once in each direction, so tonic or synchronous firing of a whole body never drifts it (exactly in real
  arithmetic; the float64 running force sum leaves a residue near 1e-15, and the tests bound the path of a lockstep
  body of any shape by 1e-9 over 200 units). That removed the
  valleys and the island cheat of the offset law (BODY_DESIGN_PROPOSAL.md 1, 2.2; 15.43).
- **Left limit.** O is the occupancy at t-: a birth or death at t does not change the face of a stroke at t.
- **Onset direction.** A stroke's direction is fixed at its onset, and its pull decays with the twitch. A cell's
  residual pull `f` is removed from F when it dies, so dead cells exert no force (15.43).
- Only act-plane strokes reach the world (N1). A twitch in another plane is charged `c_tw * kappa` like every twitch
  and does nothing. The body is rigid: an act cell pulls whether or not a sense cell is under it, and the force acts
  on the dot through the footprint (`gam`).
- **The footprint** (rule N6, tweaked twice; 15.59, 15.61). The drag is `gam = n_fill ^ drag_exp`. Tile the screen
  with the base lattice's cells at the sites' planar positions (4.3): regular hexagons on hex bases, unit squares on
  square bases. P, the projected footprint, is the set of columns `(a, b)` that hold at least one live cell in any
  plane. A free tile (a column outside P) is **enclosed** if no path of free tiles, each sharing an edge with the
  next, leads from it to infinity; edge-sharing tiles are the six hex neighbours on hex bases and the four
  neighbours `(±1, 0), (0, ±1)` on square bases, also on square8, whose diagonal slots touch only at a corner (so a
  corner contact closes a gap). `n_fill = |P| + (the number of enclosed tiles)`: the area the body covers with its
  holes filled (`spec.filled_footprint`). Islands add their own tiles and what they enclose together, not the gaps
  between them; an island inside a hole is inside the filled area anyway; footless act cells and overhanging hidden
  cells are in P like any cell. n_fill is an integer, so any exact method gives the same bits; the kernel keeps P
  as a list sorted by `(b, a)` (insertion and removal O(|P|)) and, at each change of P, counts the free runs between
  occupied tiles row by row: a row's two unbounded runs and every run of a row next to an empty row are outside,
  runs of adjacent rows that share an edge are joined (union-find), and the bounded runs not joined to the outside
  are enclosed (O(|P|) time and memory; `spec.filled_footprint` does the same after a sort).
- Traction still needs a sense-plane cell (`n_foot > 0`, 15.44). "Live" is the accountant's own view, updated at
  once by each R_BIRTH and R_DEATH (like `n_foot`), not the deferred O: a change at t only sets the drag of the
  intervals after t (`dot_adv(t)` comes first), so the dot's motion up to t uses the footprint at t-, and a time
  group's intermediate footprints, while its births arrive one by one, never act. For a body of complete columns
  without enclosed tiles `n_fill = |P| = n_foot`, so every such body lives exactly as under the proposal's
  sense-plane count; it is world physics, and no cell reads it.

#### 9.7.3 Blobs: run and tumble, placements and timers
```
PLACE(b, cause, t):                                  # cause 0 start, 1 click, 2 timer, 3 with the target
    (X, Y) = dot_at(t)
    (x_b, y_b) = blob_place(seed, b, q_b, X, Y, R_min, R_max);  t_b = t
    if b == 1: present = blob_present(seed, q_b, b2_p)           # draw(seed, S_PPRES, 1, q) < b2_p
    q_b += 1
    fold PLACE words (9.6)
TIMER of blob b, a world event at r_b:
    PLACE(b, 2, r_b);  if b == 0: counted (r_b >= t_open_abs): respawns += 1
    if b == 0 and blob 1 exists and b2_mode == 0: PLACE(1, 3, r_b)
    r_b = poisson_next(seed, S_RTIME, b, m_b, r_b, t_resp);  m_b += 1
TURN of blob b, a world event at tau_b:
    (x_b, y_b) = blob_at(b, tau_b);  t_b = tau_b
    (vx_b, vy_b) = blob_heading(seed, b, h_b, v_t);  h_b += 1
    fold TURN words (9.6)
    tau_b = poisson_next(seed, S_TURN, b, k_b, tau_b, tau_turn);  k_b += 1

blob_heading(seed, b, h, v_t):  phi = TWO_PI * draw(seed, S_HEAD, b, h);  return (v_t * cos(phi), v_t * sin(phi))
blob_place(seed, b, q, x, y, R_min, R_max):
    th = TWO_PI * draw(seed, S_PANG, b, q);  r = R_min + draw(seed, S_PDIST, b, q) * (R_max - R_min)
    return (x + r * cos(th), y + r * sin(th))
poisson_next(seed, stream, b, k, t_prev, mean) = t_prev - mean * log(draw(seed, stream, b, k))
```
- The target always exists. It runs at `v_t` and tumbles to a uniform heading at Poisson rate `1 / tau_turn`. A
  placement puts it at distance `U[R_min, R_max]` from the dot, at a uniform angle, and keeps its heading. It is
  placed at t0, after each capture, and on its own Poisson timer of mean `t_resp`, which runs whatever the captures
  (a timer, not a distance test; rule N10).
- Blob 1 moves like the target with its own streams (key `blob = 1`). With `b2_mode = 0` it has no timer and is
  re-placed whenever the target is (cause 3), present after each placement with probability `b2_p` (the DECOY ramp);
  with `b2_mode = 1` it has its own timer and is re-placed after a click on it (TWIN).
- A world event never moves the dot's anchor; it reads `dot_at`.

#### 9.7.4 The hotspot, clicks, captures and misses (rule N7)
The screen registers a press only at the cursor's hotspot, the dot itself. The act-plane site `(0, 0, 1)`, directly
above the zygote's site, is the only site whose strokes press. Which cell occupies it, and whether any does, is up to
the genome.
```
key step, at a stroke of the occupant of (0, 0, 1) (key_step):
    if armed == 0 and zt < th_rel: armed = 1
    if armed == 1 and zn >= th_click: armed = 0;  CLICK(t)
CLICK(t):
    (X, Y) = dot_at(t)                                    # the anchor: the stroke moved it to t
    (x0, y0) = blob_at(0, t);  ex = X - x0;  ey = Y - y0;  d0 = ex * ex + ey * ey
    counted: clicks += 1
    if d0 <= rho_c * rho_c:                                                       # outcome 1: capture
        counted: captures += 1;  income = income + R_cap
        defer PLACE(0, 1, t);  if blob 1 exists and b2_mode == 0: defer PLACE(1, 3, t)
    elif blob 1 exists and present and d1 <= b2_rho * b2_rho:                     # outcome 2 (d1 from blob 1 likewise)
        if counted:                                       # the income or charge too, so cost and colcost agree
            b2_clicks += 1
            if b2_value > 0: income = income + b2_value
            elif b2_value < 0: cost = cost + (-b2_value)
        if b2_mode == 1: defer PLACE(1, 1, t)
    else:                                                                          # outcome 0: miss
        counted: misses += 1;  cost = cost + c_miss
    fold CLICK words (9.6)
end of the time group, after the changes of O: the deferred placements, in order
```
- "Counted" means `t >= t_open_abs`; placements happen either way, because they are physics.
- Hysteresis (BELL's systole and diastole thresholds, on one cell): a tonic hotspot holds the key down and clicks
  once; its twitch must fall below `th_rel` at a stroke before the next press counts. A cell born at the hotspot
  starts at `z = 0`, so its first stroke re-arms the key (15.45). With the KAPPA grid, one twitch from rest reaches
  `th_click = 0.6` only with `kappa = 1`; two `kappa = 1/2` twitches less than about 4 units apart also do.
- The hotspot cell is an act cell: its stroke first pulls along its face (0 inside a full body), then presses.
- The click reads the blobs at the left limit; a capture's re-placement happens after every record of its group.

#### 9.7.5 Receptors: thinning at the left limit (rule N4)
```
R_RCAND(uid, j) of the cell at (a, b, 0), at time t:
    counted: rec_cand += 1
    (X, Y) = dot_at(t);  (ox, oy) = planar(a, b);  px = X + ox;  py = Y + oy
    (x0, y0) = blob_at(0, t)
    rate = lam_bg + lam_s * halo(px - x0, py - y0, sigma)
    if blob 1 exists and present:
        (x1, y1) = blob_at(1, t);  rate = rate + lam_s * (b2_amp * halo(px - x1, py - y1, b2_sigma))
    accepted = draw(seed, S_RACC, uid, j) * lambda_max < rate                     # receptor_accepts
    fold R_RCAND words (9.6)
    if accepted: counted: rec_accept += 1;  send RECEPTOR(uid, j) to the site (a, b, 0) at t + d_min
halo(dx, dy, sigma) = exp(-(dx * dx + dy * dy) / (2.0 * sigma * sigma))
R_RECEPT(uid, n_rec, g_r):
    counted: rec_events += n_rec;  ga = abs(g_r) * (double) n_rec;  rec_gain = rec_gain + ga;  cost = cost + c_rec * ga
```
- **Thinning.** Candidates arrive at the constant rate `lambda_max`, which bounds the true rate (each halo is at most
  1), and each is kept with probability `rate(t-) / lambda_max`. The kept events are therefore a Poisson process with
  the world's rate at the cell's own screen point, and no cell has a clock. The accept draw is keyed by the
  candidate, so it never depends on processing order.
- The world reads the dot and the blobs at the left limit (9.7.1). `X` is continuous, so `dot_at(t)` is the same
  before and after the group's strokes; a capture at t moves the target only after the group.
- The RECEPTOR is created while the accountant consumes the record stamped t and arrives at `t + d_min`: the
  receptor's transduction latency and the causality floor of 6.3. A RECEPTOR at or after t1 may be dropped. Events
  carry no direction: a cell knows only that its own receptor fired.
- Background events (`lam_bg`) are sensor noise. They also keep the trace of every sense cell that has a receptor
  above 0, a cue its genes can read.

#### 9.7.6 Samples (measurement only)
At every integer time c with `t0 < c < t_end`, at the left limit (9.7.1):
```
world_to(c);  (X, Y) = dot_at(c);  (x0, y0) = blob_at(0, c);  ex = X - x0;  ey = Y - y0;  q = ex * ex + ey * ey
counted (c >= t_open_abs): samples += 1;  dist_sum = dist_sum + sqrt(q);  if q <= rho_c * rho_c: zone_samples += 1
```
A sample changes no state and nothing reads it, so, like the guards, cells cannot sense it. The mean distance to the
target is `dist_sum / samples` and the share of time in the capture zone about `zone_samples / samples`. Extinction
does not stop the world: the blobs keep moving and samples go on until `t_end`, while the dot rests (`n_foot = 0`).

## 10. End of life: T, extinction and guards

- **T**: events with `t < t1` are processed, and the life closes at `t_end = t1`.
- **Extinction**: after a time group, if `n == 0` and `inflight == 0` (for the first time): set the extinct bit and
  `t_ext = t`. Nothing can accrue afterwards: no income because `n = 0`, and no costs because no cells remain. The
  remaining events are all stale or dropped, except packets in flight, which are lost on arrival, and RECEPTORs in
  flight, which find no target. So the queue drains within `d_min`. Implementations must process the drain; they
  may then stop. `t_end` stays `t1`. In CATCH the world goes on to `t_end` without cells (blobs, timers, samples;
  9.7.6); an implementation that stops early runs those steps at close (9.5).
- **Guards** (compute only; cells cannot sense them) are checked at every integer time `c = t0 + 1, ..., t1 - 1`,
  after all records with `t < c` are consumed and before any event at `t >= c` is processed:
  - **guard_cells**: `n >= n_max`.
  - **guard_events**: the event counter exceeds `e_max`. The counter is FIRE count + executed live TICKs + ARRIVAL
    events (delivered or dropped) with `t < c`. Receptor candidates and RECEPTOR events are not counted: their
    rate is bounded by `lambda_max` per sense cell, and the cell guard bounds the cells (15.53).
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
- **A flush can create events.** In CATCH the accountant sends RECEPTOR events (9.7.5) while it consumes a time group
  at t; each lands at `t + d_min > t` and enters the queue like a message. So the run continues after a flush whose
  records created events, even if the queue was empty before it, until no event with `t < t1` is left after the
  final flush.
- At each integer time it checks the guards (and, in CATCH, takes the sample, 9.7.6).
- Stale events may be dropped lazily, but they must not change the guard counter (the counter does not count them).

### 11.2 Window (tests only)
- Windows are `[t0 + k h, t0 + (k + 1) h)`, with `h = 2^-j <= d_min` (`window_h`).
- In each window, the sites with events in it are visited in increasing `hash64(order seed, S_ORDER, k, sk)` (ties:
  increasing sk).
- Each visited site processes its own batches with `t` inside the window in time order, including self events
  created meanwhile.
- Messages land in later windows (`t >= window end`); an implementation should assert this.
- The window's records are then sorted by `(t, sk, seq)` and consumed by the accountant, which flushes each time
  group. RECEPTOR events it creates land at `t + d_min >= window end`, so in a later window, like every message.
- Guards are checked (and CATCH samples taken) at window ends that are integers.

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
| 5 | genes_blind | x[18..22] = 0 (no traces, n_view or receptor trace reach the genes; the plane cues x[23..24] stay; ABI 1 also zeroed its x[22], flank_best) |
| 6 | identity_clamp | g frozen: no gene update, and no partition at division (a daughter starts with her mother's g, and the mother keeps hers; 15.31) |
| 7 | pheno_fixed | theta is decoded at birth only (w_eff is still recomputed) |
| 8 | lockstep | base only: every d_c = d0, delays without jitter (jit and tick_jit treated as 0), no tau or clock mismatch, first ticks on the grid `t0 + j P0` |
| 9 | program_mode | base only: section 7.5 |
| 10 | integer_twin | base only; reserved, rejected in ABI 1, 2 and 3 |
| 11 | lateral_off | FIRE creates no ARRIVAL through in-plane slots (`off_z = 0`); n_out is still charged; vertical spikes are delivered (on a 2D lattice this is contacts_off) |
| 12 | hidden_off | FIRE of a cell at z >= 2 creates no ARRIVAL; n_out is still charged (the hidden cells live, secrete and pay, but their spikes reach no one) |
| 13 | receptor_off | no RECEPTOR is delivered (7.10): no input, no trace, no charge; candidates and the world's thinning go on |
| 14 | motor_off | act-plane twitches have no world effect: no pull, no key step, no click (9.7.2); they are still charged |

Under `lockstep` the kernel ignores `delay_sd`, `jit`, `tau_mis`, `clock_sd` and `tick_jit`. Bits 11-14 are ABI 3's
(`spec.V2.validate_world` refuses them). Cell-side flags (contacts_off to pheno_fixed, lateral_off, hidden_off,
receptor_off) are tested at the batch time; motor_off is tested by the accountant at the stroke's record time.

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
- the two-stage replica: `t_open = 64` plus freeze at 64;
- BODY-1 (BODY_DESIGN_PROPOSAL.md 8, 11): the wire certificate is `contacts_off | chem_off | division_off` at T/2
  (GB6); lateral-off is `lateral_off`, hidden-off `hidden_off`, receptor-off `receptor_off`, motor-off `motor_off`.
  The radius-1 fork waits for the radius gene (13).

## 13. Reserved for later stages
- **Integer twin**: int64 time in 2^-20 units, Q24 g and m, lookup-table exp and ln. Its rounding points are to be
  specified with migration step 3; the flag bit is reserved.
- **v2**: `kill_rate` (exogenous Poisson loss via hash-keyed KILL streams arriving `>= d_min` after their cause) and
  `wound_rate`.
- **v3**: `drift_tau` (random walks of the frozen tau mismatch and d_c, and a drifting tau_R).
- **v4**: per-cell energy E, energy packets, necrosis, failed spikes.
- **v5**: threats. The receptor machinery it needed (S = 1, a RECEPTOR event in group 3, the gain row and the trace
  input) is ABI 3's, built for BODY-1 (7.10, 9.7.5); a threat world adds a world kind, not a new receptor.
- **BODY-1 after S0** (BODY_DESIGN_PROPOSAL.md 8; none launches before it passes the no-cliff test A1-A4):
  - S1 candidates (TWIN, DECOY ramp, interior blindness) need no ABI change: blob 1 (`b2_*`, 9.7.3-9.7.5) and the
    halo width cover them.
  - The radius gene (a per-cell sender reach r in {1, 2}, cap 2, delay `d_c (alpha + (1 - alpha) len)`, charges
    `c_msg * len` per event and `c_wire * len` per unit) and the radius-1 fork: a new knob, a new ABI.
  - Rotation (a tangential nudge share set by the chiral knob), several receptor modalities (S > 1: their traces and
    gain rows are appended), multi-finger presses at `X + o_i`, a signed motor gain (push), and the per-generation
    T draw (a harness setting, switched on only by gate GB11).
Each of these will be a new ABI version with its own world keys and padded genome fields (or, for the T draw, no ABI
change). A genome of an earlier ABI must behave identically after padding.

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

ABI 3 (also asserted in tests/test_life_spec_abi3.py):
sitekey(-1, 2, 1)                             = 0xfeffffff00000002
sitekey(3, -4, 3)                             = 0x03000003fffffffc
sitekey(0, 0, 1)                              = 0x0100000000000000     (sitekey(a, b, 0) = sitekey(a, b))
decode(y + [0.3, -0.7])[21:23]                = [0.25, -0.75]          (zeta, g_r; rows 0-20 as above)
decode_dm(0, D = 8)                           = 0.01875                (hexprism)
hexprism: back = 3,4,5,0,1,2,7,6;  prev/next of slots 6, 7 = themselves;  unit[6] = (0, 0, 1), unit[7] = (0, 0, -1)
exposed_face(hexprism, empty slots {0, 1})    = (1.5, -0.8660254037844386);  all six empty = (0.0, 0.0)
lambda_max(catch_v1)                          = 2.05
receptor_next(42, zygote uid, 0, 0.0, 2.05)   = 0.9337337422296379     (c_0 of the zygote, born at 0)
receptor_next(42, zygote uid, 1, c_0, 2.05)   = 1.3670951439075458
draw(42, S_RACC, zygote uid, 0) * 2.05        = 2.0035396181417187
halo(1.0, 0.5, 1.5)                           = 0.7574651283969664
receptor_rate(catch_v1, (1.0, 0.5), target (0, 0)) = 1.564930256793933   (so candidate 0 is rejected)
blob_heading(42, 0, 0, 0.1)                   = (-0.09998754332570875, 0.0015783471384705633)
blob_heading(42, 1, 0, 0.1)                   = (-0.09050519768911242, 0.04253009747525491)
blob_place(42, 0, 0, 0.0, 0.0, 2.0, 6.0)      = (0.9226993667863177, 3.7675546907873656)
blob_place(42, 1, 0, 0.0, 0.0, 2.0, 6.0)      = (-3.133232594777813, 3.264525461412328)
blob_present(42, 0, 0.5)                      = false                  (draw = 0.8467749902283425)
poisson_next(42, S_TURN, 0, 0, 0.0, 20.0)     = 15.984882681203024     (the target's first turn)
poisson_next(42, S_RTIME, 0, 0, 0.0, 50.0)    = 71.9336107410924       (its first timer re-placement)
drag(37, 0.5)                                 = 6.082762530298219
filled_footprint(ring 3) = filled_footprint(ring 3 + centre) = 37       (hex: the 18 ring-3 tiles enclose 19)
filled_footprint(centre + the six ring-3 corners) = 7                   (islands enclose nothing)
filled_footprint({(1, 0), (0, 1), (-1, 0), (0, -1)}, square8prism) = 5  (tiles touching at corners close the gap)
dot_gain(1.0, 2.5, drag(37, 0.5))             = (k 0.13549762641654428, e 0.6703200460356393)
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

32. **No flank_best input to the gene network (ABI 2, 2026-10-07; approved by the user before the pilot).** The
    design lists `flank_best / 2` among the GRN inputs (TICK step 3; Genome, REGULATION; hard-coded rule 10, whose
    reason is that "gating on n_view alone is about 23% weaker"). Gate G10 re-measured that under ABI 1 on fresh lives
    (144 per point, F* over 61-127 cells, LIFE_GATES.md):
    - R25-v1's genome with a flank_best gate and flank placement: +0.753 ± 0.040;
    - the same genome gated on n_view >= 5 instead (the live-contact fraction, already an input), flank placement
      kept: +0.754 ± 0.042, paired difference −0.001 ± 0.013;
    - the registered weakness (15% here, z 2.9) appears only when flank placement is removed too (n_view gate with
      random placement, the prototype's dir 4: +0.638 ± 0.029).

    So on hex the dedicated input duplicated what n_view already gives the genes, and it was a hand-coded rule; the
    user's goal is to keep only the fixed rules that are needed. ABI 2 therefore:
    - removes `x[22] = flank_best / 2`: x has 22 entries, W is `[16][22]`, the genome has 793 slots (every field
      after W moves down by 16), `genes_blind` zeroes `x[18..21]`, and `ABI_VERSION`, `life_abi_version()` and
      `life_sizes()` report 2 and 793;
    - keeps the placement term `phi * flank(e)` of TICK step 8. It is a genetic knob (phi, row 12, 0 at
      initialization) that evolution can zero;
    - keeps program mode's `flank_gate` (7.5), which the hand-built references use. Program mode is a measurement
      tool, not the organism model, and every program-mode gate is numerically unchanged;
    - rewrites R25-v1's GRN genome (`handbuilt.r25_genome`, gate G9) to gate on n_view >= D - 1 with flank placement:
      G10's +0.754 variant. The re-measured G9, G10 and S8 (and the GRN rows of G6 and G7) are in LIFE_GATES.md.

    Neutrality: an ABI-1 genome whose flank weights are 0 (every founder starts that way) lives bitwise as before
    once that W column is dropped. This was checked against the ABI-1 kernel on 24 fresh lives per case: R25-v1's
    n_view-gated genomes (caps 37 and 91, uncapped, with the lineage timer, square8 with D = 8) and 6 random genomes,
    238 output arrays (ledger, hashes, raster, fate logs), all equal. A genome with nonzero flank weights has no
    neutral conversion: `LifeLayout.from_dict` refuses an ABI-1 save (W with 23 columns) instead of loading it with
    every later field shifted.

    **Hex only (review, 2026-10-07).** G10 ran on hex. On square8 (D = 8), where the same genome gates at
    n_view >= 7, the removal costs the hand-built genome F. Paired against its ABI-1 twin gated on flank_best, on the
    same 288 fresh lives per size (`results/flank_square8/`):
    - n_view gate minus flank_best gate: -0.013 ± 0.010, -0.051 ± 0.020, -0.081 ± 0.052 and -0.165 ± 0.065 at 49,
      81, 121 and 169 cells (z -1.3, -2.5, -1.6, -2.5);
    - F* drops from +1.096 to +1.015 (-7%), both at 121 cells;
    - gates at n_view >= 5, 6 and 7 all stay below the flank_best gate at 81, 121 and 169 cells (144 lives);
    - on hex the same pair is equal (|z| < 1 at 61, 91 and 127 cells), as G10 found.

    The kernel and the pilot were left unchanged: the user approved the removal on the hex evidence and decides whether
    the square8 arm keeps it (LIFE_GATES.md S8).

**ABI 3 (BODY-1 v1, 2026-10-07).** Items 33-56 record each choice ABI 3 makes where `BODY_DESIGN_PROPOSAL.md` left a
detail open, and each small change to the proposal, with its reason. "Tweak" marks a change the user's instruction
allowed ("minor tweaks that help the emergent behaviour, without removing the central goals: local, async, self
discovered"); each keeps sensing, action and messages local, keeps the d_min causality contract (no central clock)
and hand-designs no behaviour (hand-built organisms remain references and gates only).

33. **Append-only layout, and what BELL-1 keeps.** Every ABI-3 array extends its ABI-2 array at the end (knobs,
    inputs, world keys, ledger columns, hash families, fate-log columns, the init rows' z, the genome fields' rows and
    columns), so every ABI-2 quantity keeps its index and `spec.V3.pad_genomes` / `pad_program` are neutral. With a
    padded genome or program, a BELL life on a 2D lattice executes ABI 2's operations exactly: the gene sum adds
    `+0.0` terms (4.4), the new knobs decode to 0 and act nowhere in BELL, no vertical slot exists, no receptor
    stream starts, and the colcost terms are `+0.0` (9.5). So every BELL number of LIFE_GATES.md, program mode and
    GRN mode alike, moves by exactly 0 per life; only the `all` hash changes (it folds 57 ledger columns). This is a
    claim about the contract; gate GB1 checks it on the ABI-3 kernel. What does move: evolution runs. The genome
    has 875 slots instead of 793, so a seed draws different founders and mutations (as ABI 1 to 2 did, RESULTS.md),
    and an ABI-3 founder has 379 mutable entries instead of 337 (the 42 new ones are inert in BELL).
34. **Site key: XOR the height into bits 56-59.** The proposal named substrate's patch, which packs a 3D site into
    2D kernel coordinates as `b' = b K + z`. That changes every z = 0 key (so frozen physics and canonical order of
    every BELL life), and the variant `b' = b + K z` is not injective on an unbounded b. XOR keeps z = 0 keys
    identical and stays injective for `|a| < 2^24` and z < 16, which the coordinate bound of 4.6 guarantees.
35. **Out-of-stack sites do not exist** (proposal 4, rule N2). They are not walls: they are never open, never
    claimable, receive no notice and count in nothing. Substrate's red team measured that treating the stack's
    limits as walls wasted 72.5% of all claims on wall rejects in bounded grown bodies. Dense-disk walls (T12) keep
    their ABI-2 meaning.
36. **Prism tables.** In-plane slots keep the base kind's native order and values bitwise, then up, then down (the
    prototypes' order). A vertical slot is its own angular neighbour, so its flank count is 0 when it is empty and
    flank placement and flank_best are in-plane notions, as in ABI 2. D is the lattice degree everywhere (8 on
    hexprism), also where the stack hides a vertical slot: `n_view / D` then tops out at 7/8 in the bottom and top
    planes, which is information the plane cues carry anyway, and D_m stays a property of genome and lattice.
37. **Vertical placement: the polarity term in 3D (tweak) plus zeta (rule N8).** The proposal adds `zeta * u_z(e)`
    because vertical slots have no in-plane unit vector, so the polarity term `unit(e) . p` scores them 0. ABI 3 also
    takes the polarity vector in 3D: `p` sums `s_d unit(d)` over vertical slots too, and a vertical slot scores
    `u_z vz + zeta u_z`. This is the existing rule (placement follows the received morphogen gradient) without a
    planar special case: no new parameter, and it lets "grow up from the sense plane, not from the act plane" emerge
    from chemistry (a plane-specific secretion is a vertical gradient) as well as from a per-plane zeta, which helps
    with the two growth conjunctions the proposal flags (6). In-plane scores are ABI 2's bitwise.
38. **Plane cues (rule N9): is_S = [z = 0], is_M = [z = 1], and both are 0 outside CATCH (tweak).** They are the
    cell's own local substrate contact (touching the screen; being in the act plane). In BELL there is no screen, so
    the cues are 0 there instead of a constant 1 on every cell: a BELL genome gets no stray second bias input, and
    its life never depends on W columns 23-24. genes_blind zeroes the activity and contact inputs (x[18..22]) but
    not the cues, which describe the substrate rather than activity.
39. **The receptor trace** (`rho`, input `x[22] = rho / tau_tr`, the design's reserved v5 input) counts delivered
    receptor events, decays with the cell's `tau_tr` like `f` and `r`, and is re-anchored with them. Change
    detection is not built in: if adaptation helps, it must come from the cell's own GRN reading this trace.
40. **A cell with g_r = 0 has no receptor (tweak).** A RECEPTOR reaches only a cell whose current `g_r` is nonzero;
    otherwise it vanishes (no input, no trace, no charge). The alternative, a trace that counts events whatever the
    gain, would let every sense cell's genes read the screen for free (`c_rec * 0`), an unpriced slow sensing channel;
    the user asked for costs on actions. `g_r` is signed and on the 1/8 grid (so the membrane sum stays exact in GRN
    mode; program rows may use off-grid gains such as 0.55, added once after the exact sum). The charge
    `c_rec * abs(g_r)` per delivered event (0.001, the proposal's value; the prototype had none) is paid at delivery,
    refractory or not.
41. **Candidates are the cell's own events; thinning is the world's.** Every live sense-plane cell runs a Poisson
    stream of candidates at `lambda_max`, keyed by (uid, j), from its birth, whatever its phenotype; each emits
    R_RCAND, and the accountant keeps it with probability `rate(t-) / lambda_max` (9.7.5). This is the proposal's
    rule (sense design; heap = window verified in a kernel copy). Making the candidate a site event is what lets the
    accountant answer within `d_min` under both schedulers: a candidate drawn by the accountant itself would only be
    seen at the next record, possibly later than `c + d_min`. At most one candidate per cell per instant, and the
    group-3 records come in the order R_RCAND, R_RECEPT, R_SPIKE, so `cost` sums identically everywhere.
42. **The first world that sends to cells.** RECEPTOR is created by the accountant while it consumes a record at t,
    and it arrives at `t + d_min` (6.3): the same floor as every message, so a site's batch at t still depends only
    on what happened before `t - d_min` elsewhere. Schedulers must keep running after a flush that created events
    (11.1). Nothing else flows back: no cell reads X, a blob, a total or a clock.
43. **Strokes (rule N5): direction at onset, and a dead cell stops pulling (tweak).** The prototype fixed each
    twitch increment's direction at its onset (the exposed face at that instant), which keeps one decaying force
    vector and a closed form between anchors; ABI 3 keeps that. It adds one thing: a dying act cell's residual pull is
    removed from the total, as BELL removes a dying cell's twitch from the lumen. Without it a dead cell would pull for
    a few tau_z. Faces read the act-plane occupancy at the left limit (46). Twitches outside the act plane are charged
    `c_tw * kappa` and move nothing (rule N1).
44. **No footprint, no traction (tweak).** With no live sense-plane cell (`n_foot = 0`; reachable only when every
    z = 0 cell has died), the dot does not move. The prototype used `gamma = 1` there, which let a body with no foot
    on the screen move with drag 1. Under rule N6 the drag comes from the footprint, so without one there is nothing
    to push against. This only removes motion; it cannot be exploited.
45. **The key (rule N7).** The prototype's hysteresis rule: at a hotspot stroke, a twitch below `th_rel` re-arms the
    key, then a twitch at or above `th_click` while armed clicks and disarms. The key is world state: it persists
    across occupants, and a newborn at the hotspot (z = 0) re-arms it at its first stroke, so death needs no rule.
    The hotspot site (0, 0, 1) is the one designated place beyond the two planes (decision 2); no cell type is.
46. **Left-limit reads, deferred writes.** Inside a time group every world read uses the state at t-: faces read the
    act-plane occupancy before the group's births and deaths, and clicks and receptor candidates read the blobs before
    the group's re-placements. These writes are deferred to the end of the group; force increments, footprint changes
    and residual removals apply at once, because they only affect intervals after t, and `X` is continuous. World
    events at an instant come after its records, samples before. Exact ties are rare with jittered clocks but certain
    under lockstep, and a rule in canonical (site-key) order would make a stroke's face, or a candidate's view of a
    just-captured target, depend on site keys, which rotation (T7) permutes.
47. **Blobs.** Run and tumble, placement around the dot and the timer follow proposal 3.1. The prototype ran its
    timer as rate-1 checks thinned by `1 / t_resp`; ABI 3 draws exponential intervals of mean `t_resp` directly (the
    same Poisson process, one draw per event). The timer does not reset at a capture (the proposal's "timer, not a
    distance test"). The target is placed at t0 around the dot at (0, 0); a placement keeps the heading. Every world
    stream is keyed by the blob's own counters, so the target's path depends on the body only through the dot
    positions at its placements.
48. **Room for a second blob (proposal 9.5).** Keys 60-65 give S1 candidates a second blob on the same receptor
    modality, with its own width, click value (income or cost), radius, presence probability and placement mode:
    TWIN (`b2_amp 1, b2_value R_cap, b2_mode 1`), DECOY and its ramp (`b2_value < 0, b2_mode 0, b2_p < 1`), and
    interior blindness (sigma alone). A click checks the target first (as the prototype did). With `b2_amp = 0` (v1)
    blob 1 does not exist and consumes no draw. None of these may launch before passing A1-A4.
49. **Initial bodies of up to 1024 cells, within `|a|, |b| <= 2^22`.** The hand-built CATCH ladder (proposal 3.2,
    4.1) runs rings 0-6 in two planes (up to 254 cells) and with silent hidden stacks (up to 508); 64 cannot hold even
    the optimum, ring 3 (74 cells). The bound keeps site keys injective (34).
50. **Program mode is unchanged.** Five selector rows of 23 knobs; the selector does not read the plane. Hand-built
    CATCH bodies fix a row per initial cell (sense rim, centre clicker, motor: three of the five rows). A plane-aware
    program selector would be a hand-coded role for growing references; GB9 and GB13 use the hand GRN instead.
51. **libm: cos, sin and pow join exp, log and tanh; sqrt is exact.** Headings and placements need an angle, and
    the drag law a power. The same-libm assumption covers them.
52. **Samples at integer times.** Mean distance and time in zone are not closed forms (the distance between the
    decelerating dot and the moving target crosses rho_c at transcendental times), so the ledger samples them at the
    guard times, which read nothing back into the life. The prototype used Poisson checks and a trapezoid on its event
    grid, which depends on event density.
53. **The guard counter is unchanged.** Receptor candidates and deliveries are bounded by `lambda_max` per sense cell
    (2.05 by default) and the cell guard bounds the cells, so counting them would only move every CATCH life's guard
    margin.
54. **The forks.** `lateral_off` and `hidden_off` are lesions, like contacts_off: the spikes are charged but not
    delivered, and the cells otherwise live (hidden cells still secrete, so chemistry still crosses planes; name
    chem_off as well to cut it). The proposal wrote "z >= 2 cannot fire"; silencing hidden cells would also remove
    their spike costs, so the fork would mix the value of their computation with an energy saving. `receptor_off` drops deliveries but keeps the world's thinning, so a fork changes
    nothing before t_fork. `motor_off` cuts the world effect of strokes, not the twitch or its cost.
55. **World key ranges.** `tau_turn = 0` and `t_resp = 0` switch turns and the timer off (useful for S1 designs). The
    caps (`lambda_max <= 1024`, `g_n, v_t <= 1024`, lengths `<= 2^20`) bound the event rate and keep positions far
    from overflow over `T <= 2^30`. The CATCH presets keep BELL's guard `n_max = 1024` (the prototypes used 300-400):
    the guard is a compute tool, and its charge, about -20 F for an early trip, is far below every viable body.
56. **Left out of ABI 3, on purpose.** The radius gene (decision 5: after S1), rotation, a signed motor gain (push),
    several receptor modalities, multi-finger presses, and the per-generation T draw (proposal 3.1: only if GB11 finds
    bodies still growing at T; a harness setting) are not in the contract. Each comes with its own revision (13).
57. **Argument checks written down** (cross-check round 1 of ABI 3, 2026-10-07; no life changes). Fuzzing the
    kernel against the reference on random CATCH arguments found five places where the kernel's argument checks,
    unchanged since ABI 2 unless noted, were stricter than or ordered differently from this text, and the reference
    followed the text. The kernel's rule is the sensible one each time, so 4.2, 4.3 and 4.6 now state it and the
    reference applies it:
    - **No initial cell on a wall.** A wall of a dense fabric is a site that fabric does not have (claims to it are
      rejected with result 2), so it cannot hold an initial cell either (-4). The reference ran such a body as if
      the wall site held a cell.
    - **The row of an initial cell is checked in program mode only**, since GRN mode ignores it (the reference
      refused an out-of-range row in GRN mode too).
    - **The key bound `|a|, |b| <= 2^22` holds for ABI-2 calls too**: `build.run` pads an ABI-2 body into ABI 3, and
      the kernel checks the bound there (new in ABI 3); the reference checked it only for ABI-3 calls.
    - **A slot whose offset is `(0, 0, 0)` is not a lattice slot** (the kernel's table check).
    - **A missing `init_cells` with `n_init > 0` is -1** (a NULL array some life needs), and the per-life checks run
      in the kernel's order (4.2), so a call that breaks several rules gets one code everywhere.
    The kernel is unchanged, and the reference now refuses exactly what the kernel refused, so no valid life
    changes anywhere. Tests:
    `test_t12_sparse_and_dense_3d_fabrics_agree_while_the_body_stays_inside` and
    `test_the_kernel_and_the_reference_refuse_the_same_arguments`.

58. **World timers have the step floor too** (review fix, 2026-10-07). `tau_turn` and `t_resp` were allowed anywhere
    in `[0, 2^30]`. A mean interval below half an ulp of t never advanced the timer, and world events do not count
    toward the event guard, so `life_run` never returned (t_resp 1e-20; 1e-5 gave about 4e5 re-placements in 4
    units). Each is now 0 (off) or at least `2^-10`, the floor every delay and tick period already has, so world
    events come at most about 1024 per unit per timer, like receptor candidates (53). No valid life changes. Tests:
    `test_world_timers_below_the_step_floor_are_refused_so_every_life_ends` and the ABI-3 world-range lists.
59. **Drag counts the projected footprint (tweak of rule N6, review fix, 2026-10-07).** The proposal's `gamma =
    n_foot^(1/2)` counted sense-plane cells only, so an act cell with no sense cell under it pulled at no drag. A
    2-cell clicker with two adjacent footless tonic drifters (4 cells) then beat the 4-column body by +0.068 (z 14)
    and every one-step change from it lost F: a 4-cell local optimum (the pilot's kill outcome) next to the column
    ladder. Now `n_col` counts every occupied column `(a, b)` in any plane. The proposal's own reason for the law
    (drag grows with the body's linear size, so top speed does not depend on size) is about the body's extent, which
    footless act cells and overhanging hidden cells add to. Every body of complete columns has `n_col = n_foot`, so
    the ring ladder, the column ladder, the hold body, the islands, the tonic rings and the hidden stacks live
    bitwise as before; only bodies with footless act cells or overhangs change. Traction still needs a sense-plane
    cell (44). Gate GB7 screens runners with 1-3 drifters. Tests: `test_footless_act_cells_add_drag` and the Euler
    check of `test_closed_form_dot_matches_euler_within_0_1_percent`, which now integrates with `n_col`.
60. **c_miss 2, not 1 (tweak of BODY_DESIGN_PROPOSAL.md 3.1, review fix, 2026-10-07).** At c_miss 1 a blind click
    paid on average: a still dot has the wandering target within the capture radius about 1.55% of the time, so a
    click earns 100 x 0.0155 = 1.55 and costs 1. A silent zygote under a slow tonic presser (b 1.5, tau_m 16, t_ref 2,
    kappa 1; about 52 clicks per life) beat the lone zygote by +0.0085 (z 4.2), and a blind relay version passed the
    message certificate. Rule N10 ("the miss cost makes blind clicking lose") was false for slow pressers. At c_miss
    2 the break-even capture rate per click is 2 / 102 = 1.96%, above blind clicking's 1.55%, so blind clicking
    loses at any rate (the same genome: −0.039 below the lone zygote, z −20), while the sensing clicker still beats
    the lone zygote (+0.043, z 19) and the column ladder stays uphill (proposal 3.5 had measured c_miss 2 as inside
    the good region). The world default `c_miss` is 2; the price only changes the bill, so every life is unchanged
    and F moves by −misses / T. Gate GB7 screens blind pressers over the GRN grid.
61. **Drag counts the filled footprint (red-team tweak RT-T1 of rule N6, 2026-10-08).** The S1 prototype study found a
    drag loophole: drag counted footprint cells, so a hollow body kept its reach but shed drag. With the proposal's
    sense-plane count, a sense plane of centre + ring 3 (19 cells) under a full act disk dragged like 19 cells, not
    37 (28% less), and that hollow body was the best tuned reflex there, competing with lateral routing for the wrong
    reason. In this kernel 15.59 already counted the act disk (that body has 37 occupied columns and lives bitwise
    alike before and after this entry), but a body hollow in every plane still dragged like its occupied columns
    alone: the centre column and a ring of 18 columns cover the 37-tile disk and dragged like 19. The proposal's
    reason for the law is the body's extent on the screen (drag grows with its linear size, Stokes-like), and a ring
    has the extent of the disk it bounds, so the drag now counts the filled footprint: the occupied columns plus
    every tile they enclose (9.7.2). Choices:
    - tiles connect through shared edges: the six hex neighbours, and on square bases the four axial ones, also on
      square8, whose diagonal slots touch only at a corner (a corner contact leaves no gap between closed tiles);
    - islands are not merged (no convex hull): the gaps between separate pieces stay free, so the islands of GB7 keep
      their footprint 7, and a body pays for the area it actually closes off;
    - the footprint is the accountant's live view and changes at the record, as in 15.59, so the dot's motion up to t
      uses the footprint at t- and a time group's intermediate footprints never act;
    - **recorded residual (review, 2026-10-08): a slit to the outside reopens a hole.** Only tiles with no edge path
      to infinity are filled, so a body that opens its hole to the outside through a one-column slit gets the drag
      discount back while it spans the same disk. The thick hollow body (centre + rings 2-3 in every plane, n_fill
      37) without the edge-sharing columns (2, 0) and (3, 0) encloses nothing and drags like its 29 columns; closing
      either end of the slit closes the hole again (37, or 36 with the outer notch). Measured (column reflex, 2,048
      paired lives, seeds 41,000,000 + s), against the same slit body with two quiet sense cells (no receptor)
      refilling the slit's columns in the sense plane only, which keeps every act-plane face and pull and closes the
      hole: catch_v1 +0.223 ± 0.010 F (z 21; speed 0.401 against 0.356, the factor sqrt(37 / 29)), so about +0.18 F
      of drag discount after the two quiet cells' upkeep (about 0.04), the size RT-T1 removed from the closed thick
      hollow (−0.157); SPECK +0.177 ± 0.021. Against the closed thick hollow the slit body gains in SPECK (+0.060 ±
      0.025, z 2.4) and loses in catch_v1 (−0.199 ± 0.012), where the two removed columns' pull is worth more. Such
      bodies sit far below the full ring 3 (catch_v1 +1.62 against +3.86, SPECK +0.35 against +5.05), so no gate
      changes. Left open, a decision for the user: the morphological closing of P by the radius-1 disk before the
      fill, or the filled convex hull of each edge-connected piece, would close this slit (both give it 36 tiles)
      and re-price no hand-built gate body without holes (rings, column ladders, runners, islands, the SPECK shapes
      and GS3's path bodies), but they also charge ragged grown bodies for their notches: on the end-of-life bodies
      of the pre-pilot smokes' best genomes (32 lives each) the closing changes 24 of 32 seeded v1 bodies (98.2 →
      100.5 tiles on average), 16 of 32 SPECK unseeded and 12 of 32 SPECK seeded, the hull 25, 24 and 18 (98.2 →
      103.6), GS5's grown routers 6 and 8 of 16 and the GB6 and GB9 column grower 10 and 11 of 32. Either is a
      kernel and spec change with new T-tests and a gate rerun. Test: `test_a_slit_to_the_outside_leaves_the_hole_free`.
    It is world physics computed from occupancy only: no cell reads it, no clock, nothing global flows into a life.
    The kernel keeps P sorted by (b, a) and recounts the filled tiles by row runs at each change of P: O(|P|) time and
    memory per column birth or death (a few thousand operations at the 1024-cell guard), never the bounding box's
    area (a 3,000-tile diagonal line counts in O(n)).
    Measured on paired lives (4,096 per point, seeds 16,000,000 + s, the hand-built column reflex, the kernel of
    8395c12 against this one): in catch_v1 the hollow ring 3 (centre + ring-3 columns, 38 cells) lost
    −0.504 ± 0.005 F (+0.387 → −0.117; speed 0.148 → 0.106, the factor sqrt(19 / 37) = 0.717) and the thick
    hollow ring (rings 2-3 + centre, 62 cells) −0.157 ± 0.008; in SPECK (sigma 0.6, R_cap 500) −0.358 ± 0.012 and
    −0.144 ± 0.016. The full ring 3 and the sense-hollow ring 3 (the prototype's hollow body, act disk full) are
    bitwise unchanged; the latter's lead over the full ring 3 (+0.449 ± 0.011 in catch_v1, +0.358 ± 0.034 in SPECK)
    is all cost (18 fewer sense cells: 0.450 and 0.389 per unit), with income equal within 1 SE, so it is cell
    economy, which the world should keep, not drag. Every body that never encloses a tile lives bitwise as before:
    full disks, column bodies, hidden stacks, islands, turnover, footless drifters, a footless ring that grows a foot
    (golden hashes of the old kernel in `test_bodies_without_holes_live_bitwise_as_before_the_filled_footprint`).
    Random GRN growers change only in lives that enclose a tile while the dot is pulled (a diagnostic of 40 dividing
    and dying genomes, 3 lives each: 17 of 120 lives changed, all of them such lives; 10 more enclosed tiles only
    while still or with a residual force below an ulp of X, and stayed bitwise).
    BELL-1 is untouched (no drag in world kind 0). Tests: `test_the_filled_footprint_fills_holes_and_nothing_else`
    (spec against a flood fill on 1,200 random shapes on every base), `test_the_kernel_fills_the_footprint_like_spec`
    (the export on 2,000 shapes), `test_a_hollow_ring_drags_like_the_filled_disk`,
    `test_footless_cells_enclose_and_islands_do_not`, the Euler and record re-derivation checks (now with the filled
    footprint, including a hollow ring and a GRN body whose holes open and close), and kernel = reference bitwise on
    hole-forming growing and dying bodies (T3: a hollow ring 2 under turnover, a static hollow ring 3, a grower and
    GRN genomes on hexprism, square4prism and square8prism).
62. **SPECK prices a miss at 10 (tweak, 2026-10-08, before any SPECK run).** With R_cap 500 and v1's c_miss 2, a
    blind click breaks even at a 0.4% capture rate (2 / 502), against 1.96% (2 / 102) in v1, and gate GS6 failed:
    the best of 480 blind pressers earned +0.292 ± 0.011 (n 2048), +0.312 above the lone zygote (z 29), though
    0.186 below the sensing 2-cell clicker, and the blind GRN presser and relay +0.26. A blind presser is a
    founder-scale trap of the kind 15.60 removed from v1 (rule N10: the miss cost makes blind clicking lose). c_miss
    10 keeps v1's ratio R_cap / c_miss = 50, so a blind click again breaks even at 2 / 102. Measured on the same
    lives before the change (gates_speck.json at c_miss 2, `at_c_miss_10` blocks): every blind cheat falls below
    the clicker by 0.60-2.86 and below the lone zygote; the sensing clicker loses only its misses' extra price
    (1.94 misses per life: about −0.015 F, so it stays about +0.46 above the lone zygote); router minus the best
    tuned reflex is +2.246 ± 0.101 (z 22.3), unchanged. Islands and runners are unaffected (they lose as before).
    The tuned knobs (handbuilt.SPECK_TUNED) were tuned at c_miss 2 and are not re-tuned. Lives are unchanged: no
    cell reads a price (the kernel only adds it to the ledger's cost tally), so events, fates and hashes are bitwise
    the same and F moves by −8 · misses / T. The gates were rerun at the new presets (docs/LIFE_GATES.md, SPECK).
