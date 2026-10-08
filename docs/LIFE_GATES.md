# One-life gates G1-G10 (migration step 3)

BELL-1 gates G1-G10 and S8 first; the BODY-1 gates GB3-GB13 of the CATCH world follow at the end of this file
(`python scripts/life_gates.py --world catch`).

The pre-registered gates of `docs/ONE_LIFE_DESIGN.md` (PRE-REGISTERED GATES), measured in the C kernel on hex with
Q10 membranes, plus the square8 size curve that G10 asks for before any square8 run. Each gate below gives its
criterion, the old registered value, the measured value with the number of lives and the standard error (SE), the
verdict, and one plain-language line.

- Produced by `python scripts/life_gates.py --threads 4` on 2026-10-07; results in `outputs/life_gates/gates.json`
  (kernel library `life_6ed6129a0071cbfe.so`, ABI 1). Run time 363 s on 4 threads, peak memory 0.47 GB.
- Rerun after the review fixes (same day). The kernel change (identity_clamp now freezes g through divisions,
  LIFE_ABI.md 15.31) touches no gate, and every measured number is bitwise the same as in the first run
  (`life_01933c8d622b0dea.so`). What changed: the G3 port check's reference and threshold (G3), G2's scope note, and
  the statement of G10's grn_layer criterion.
- **ABI 2 rerun (2026-10-07, later the same day).** The gene network lost its flank_best input (LIFE_ABI.md 15.32),
  and R25-v1's GRN genome now gates division on n_view ≥ 5 with flank placement kept. Kernel library
  `life_613ca64c40377cf9.so`, ABI 2; `python scripts/life_gates.py --threads 4`, 1115 s on 4 threads on a shared
  machine, peak memory 0.47 GB.
  - Every program-mode number is unchanged: G1, G2, G3, G4, G5 and G8 are identical in gates.json leaf for leaf, and
    so are G6's program rows, G10's program-mode D4 and D5, and S8's program curve and re-tuning screen.
  - Re-measured: G9, G10's GRN block and grn_layer, S8's GRN genome, G6's GRN rows and G7's scope. The ABI-1 values
    of the old genome are kept in each gate's `abi1` entry and below.
  - R25-v1's new genome and its random-placement variant had zero flank weights under ABI 1 too, so they live bitwise
    as before: G10 reproduces their ABI-1 F* to every digit (+0.754151 and +0.638136).
- **Rerun on the integrated tree (2026-10-07, with two-stage selection added to evolution).**
  `python scripts/life_gates.py --threads 4` on the tree that carries both pre-pilot changes reproduced gates.json leaf
  for leaf; only run times and metadata differ (501 s on 4 threads, peak memory 0.47 GB). One rounding slip in this
  document was fixed: G5's default F(169) is −0.24 (−0.2446), not −0.25.
- **Rerun after the review (2026-10-07).** `python scripts/life_gates.py --threads 4` (458 s on 4 threads, peak
  memory 0.47 GB) reproduced every number in gates.json. Only run times, the date and three notes changed: the G9
  and G10 notes now say that the n_view gate matched the flank_best gate on hex, and S8 gained a note with the
  paired square8 comparison against the ABI-1 flank_best genome (S8 below; `results/flank_square8/`).
- **Rerun on the ABI-3 kernel (2026-10-08).** `python scripts/life_gates.py --threads 4` (with the `--world` option
  added, BELL being the default) on kernel library `life_5c65f605cba3402e.so` reproduced gates.json leaf for leaf
  (4144 of 4144 leaves; only run times and metadata differ), as the ABI-3 cross-check had found on its own rerun. That
  run (845 s on 4 threads on a shared machine, peak memory 0.73 GB) now is outputs/life_gates/gates.json, so the pins
  below are active again on this library.
- Pinned by `tests/test_life_gates.py` (slow): each test recomputes part of its gate, asserts the stored numbers
  exactly, and re-judges the stored measurements to reproduce the stored verdicts.
- **Result: 10 of 11 pass. G10 fails on one check:** the flank placement term of layered growth (design D4) adds
  +0.057 ± 0.037 over rate gating alone, which is not resolved at 144 lives. All other D4 and D5 claims hold.

## How the gates measure (re-registration)

- **Why re-register.** The registered G1, G3 and G4 values came from the prototype on 36 lives per point. The
  prototype drew a life's frozen physics from its seed, so every organism registered at 91 cells shared the same 36
  favourable bodies, and F(91) = +0.928 was a high draw. Every gate here uses fresh lives instead.
- **Fresh lives.** Seeds `5,000,000 + s`. The same seeds serve every size, organism and condition (common random
  numbers), so differences between organisms or sizes are paired life by life.
  - They are disjoint from every registration seed: G1 used 0..63; G3/G4 used 91 N + s with s < 36; the port check
    used 400,000 + 91 N + s; the test ladder used 10^6 + 91 N + s.
  - Lives per point: 144 for G1, G4 and most of G10; 288 for the R25-v1 reference curve (G3) and for G9; 48 for G5,
    whose bodies reach 547 cells and whose effect is many SE wide.
- **Screens.** Searches that choose a candidate (G2, D5 and the square8 re-tuning) run on screen seeds
  `6,000,000 + s`. The chosen candidates are then measured on the fresh lives, so a screened candidate's value never
  comes from the lives it was chosen on.
  - Exception: n* and F* (G3, G4, G5, G10, S8) and G1's best lone cell are picked as the argmax on the same fresh
    lives they are reported on. Each such F* is the largest of several means, so it is biased slightly upward (most
    where the top is flat), and a difference between two F* values is less certain than its paired z suggests.
- **Exploration.** The G9 genome was designed on exploration seeds `8,000,000 + s`, which no gate uses.
- **n\*, F\* and the flat top.** n* is the size with the largest mean F among those measured, and F* its mean. The
  flat top lists every size within 2 paired SE of n*.
- **The oracle cap** stops growth at N cells. It is a measurement tool only, as in the design.
- **The old registered values** are kept in each gate's `registered` entry in gates.json.

## Summary

| gate | criterion (short) | measured, fresh lives (mean ± SE, n) | verdict |
|---|---|---|---|
| G1 | best lone cell within 2% of +0.0326 | +0.03281 ± 0.00001 (b 1.625, τ 4, t_ref 4; n 144) | PASS |
| G2 | best messages-off body (program mode) ≤ lone cell at every N ≥ 2 | best +0.0063 ± 0.0007 at N = 2, −0.020, −0.128, −0.368 at 3, 7, 19 (n 144) | PASS |
| G3 | R25-v1 curve rises, is bounded, F* > 10× lone | n* = 61, F* = +0.711 ± 0.017, flat top 61-91; F(91) = +0.697 ± 0.033 (n 288) | PASS |
| G4 | ablation order [n*, F*] | R25-v1 [61, 0.713] > no-LBT [37, 0.530] > naive [37, 0.398] > flood [3, 0.044] > none [1, 0.033] (n 144) | PASS |
| G5 | no frozen heterogeneity: no size bound | F +1.89 (91) → +5.43 ± 0.49 (397), +5.20 ± 0.91 (547); default n* 91, F(547) −8.40 (n 48) | PASS |
| G6 | spikes undelivered from T/2 collapse income | income per cell 31.9e-3 → 1.41e-3 (4.4%; n 144) | PASS |
| G7 | income per cell ≤ the lone-cell rate | largest body life 49.6e-3, against 54.0e-3 for the best lone life (31,392 body lives) | PASS |
| G8 | closed-form lumen vs Euler ≤ 0.1%; bitwise invariance | largest error 0.024%; threads and window scheduler bitwise | PASS |
| G9 | R25-v1 as a GRN genome within 2 SE of the program at 91 | GRN (n_view gate) +0.690 ± 0.032 vs program +0.697 ± 0.033, z −0.15 (n 288) | PASS |
| G10 | D4 and D5 re-measured; GRN layer | D5 holds (z 8.9); GRN: flank placement beats random placement (z 2.8); program: placement term +0.057 ± 0.037 (z 1.5) | **FAIL** |
| S8 | square8 size curve measured, n* interior | n* = 121, F* = +1.151 ± 0.063, flat top 81-121; F(289) −1.12 (n 144) | PASS |

## G1. Best lone cell

- **Criterion.** The best lone cell, exhaustive over the knob grid (b, τ_m, t_ref, κ: 5280 phenotypes), lies within
  2% of the registered +0.0326 on the registration screen (seeds 0..63) and on fresh lives. Also gated:
  - the port check (the kernel matches bell3.c within 1e-4 on the prototype's 10 best lone cells);
  - knobs outside the grid leave a lone life bitwise unchanged;
  - b < 1 costs exactly c_live, and κ = 0 earns nothing.
- **Registered.** +0.0326 (b 1.875, τ 8, t_ref 2).
- **Measured, fresh lives** (144 per phenotype, the 1080 phenotypes with b ≥ 1 and κ > 0; all others are inert, which
  the registration screen checks on every phenotype):
  - best: +0.032808 ± 0.000008 (b 1.625, τ_m 4, t_ref 4, κ 1);
  - the registered pump: +0.032611 ± 0.000010, rank 11;
  - 21 phenotypes lie within 1% of the best, but only the best is within 2 paired SE of itself, because lone lives
    share their frozen physics across phenotypes;
  - income rate of the best: 53.8e-3 per unit; the largest of any lone life: 54.0e-3.
- **Registration screen** (64 lives): the same argmax at +0.032807; the pump +0.032629, rank 9.
- **Verdict.** PASS. The argmax differs from the registered phenotype; that is reported, not gated.
- **In plain words.** A single cell earns +0.033 per time unit. The best lone cell is a slightly different setting
  from the one written in the design, but it is worth only 0.6% more.

## G2. Messages-off bodies

- **Criteria.**
  - below_lone: at every N ≥ 2, the best fresh mean F over all messages-off bodies is at most the lone cell's
    +0.03281.
  - zero_income: L0 earns less than 1e-3 per cell-unit at N ≥ 19.
- **Messages off** means contacts_off from birth: spikes are never delivered, so they have no effect on v or on the
  traces. Contact notices still arrive.
- **The search** (program mode):
  - every homogeneous phenotype that can pump alone (b > 1, κ > 0: 960), grown by layered growth with spikes off;
  - screened at 2, 3 and 7 cells on 8 screen lives each;
  - the 3 best at each size (8 distinct phenotypes), plus L0 and the best lone cell grown into a body, re-measured on
    144 fresh lives at 2, 3, 7 and 19 cells (L0 and the grown lone cell also at 37).
- **Registered** (L0, 36 lives). −0.004, −0.035 and −0.137 at N = 2, 3 and 7, and zero income at N ≥ 19.
- **Measured** (144 fresh lives):

| N | best messages-off body | F (mean ± SE) | income per cell | L0 (vs registered, z) |
|---|---|---|---|---|
| 2 | b 1.625, τ 4, t_ref 2 | +0.0063 ± 0.0007 | 24.8e-3 | −0.0031 ± 0.0007 (+0.43) |
| 3 | b 1.625, τ 4, t_ref 2 | −0.0201 ± 0.0008 | 14.8e-3 | −0.0356 ± 0.0007 (−0.30) |
| 7 | b 1.875, τ 4, t_ref 2.5 | −0.1277 ± 0.0007 | 2.7e-3 | −0.1356 ± 0.0006 (+1.17) |
| 19 | L0 | −0.3685 ± 0.0015 | 0.18e-3 | |
| 37 | L0 | −0.7035 ± 0.0029 | 0.10e-3 | |

- **Verdict.** PASS, for program-mode bodies: the best body is 39 SE below a lone cell at N = 2 and further below
  at every larger N. The search found a slightly better 2-cell body than L0 (+0.006 vs −0.003), still far below a
  lone cell. L0 reproduces its registered points.
- **Scope: program mode only; chemistry is untested** (review note). Program-mode cells cannot read morphogens, so
  this search has no coupling channel left once spikes are off. GRN-mode bodies under contacts_off still have
  chemistry, and the messages_off control evolves there. Chemistry can carry spike timing: a hand-made 2-cell GRN
  body whose cells secrete after their own spikes and raise their drive with their morphogen level lifts Kuramoto R
  from 0.658 (chem_off) to 0.714 on the same lives (96 fresh lives, w_b 1.0), at F about −0.0001, below a lone cell.
  No search of GRN bodies under contacts_off has been run. The only GRN-mode evidence so far is one 40-generation
  messages-off GA (RESULTS.md, smoke), which stayed a lone cell.
- **Not run.** The design's "50-generation GA with messages off stays a lone cell" belongs to the evolution side
  (configs/life_ctl_messages_off.yaml).
- **In plain words.** Without messages, two or more program-mode cells always earn less than one cell, and from 19
  cells on they earn almost nothing. Whether gene-network cells could couple through chemistry instead is not tested
  here.

## G3. The R25-v1 size curve (re-registered)

- **Criteria** (on fresh lives):
  - rises: F increases at every size up to n*, by more than 2 paired SE at every step below the flat top;
  - bounded: n* is interior, and F(331) < 0;
  - beats_lone: F* > 10× the lone cell;
  - port: R25-v1/bell3 (the prototype's exact rule, 576 kernel lives) is within 2 SE of the re-measured bell3.c at
    37, 91 and 169 cells. The reference is bell3.c with the kernel's Irwin-Hall(12) frozen normals on 4608 fresh
    prototype lives per size.
- **Registered** (prototype, 36 lives). n* = 91 at +0.928 ± 0.058.
- **Measured** (288 fresh lives per size, the same seeds at every size):

| N | 1 | 2 | 3 | 7 | 19 | 37 | 61 | 91 | 127 | 169 | 217 | 271 | 331 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F | +0.033 | +0.041 | +0.072 | +0.145 | +0.349 | +0.566 | **+0.711** | +0.697 | +0.419 | −0.220 | −1.018 | −2.100 | −3.509 |
| SE | 0.000 | 0.001 | 0.000 | 0.001 | 0.004 | 0.008 | 0.017 | 0.033 | 0.058 | 0.088 | 0.111 | 0.123 | 0.126 |
| registered | 0.033 | 0.041 | 0.072 | 0.148 | 0.346 | 0.558 | 0.730 | 0.928 | 0.465 | −0.062 | −0.625 | −2.442 | −3.399 |
| F > 0 (frac.) | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.99 | 0.89 | 0.75 | 0.51 | 0.37 | 0.19 | 0.08 |

- **n\*, F\* and the flat top.** n* = 61 with F* = +0.711 ± 0.017. The flat top is 61-91: F(91) − F(61) =
  −0.015, at z −0.5.
  - The median at 91 is higher (+0.82 vs +0.76), but 11% of 91-cell lives go negative.
  - Income per cell falls from 53.6e-3 for a lone cell to 35.7e-3 at 61 cells and 9.9e-3 at 331.
- **Where the old values fail.** Only F(91) differs from the registration by more than 2 SE (z −3.46). The
  prototype's own value at 91 on 4608 fresh lives is +0.726 ± 0.008 (+0.732 ± 0.008 with the kernel's Irwin-Hall
  normals).
- **Port check** (review fix). The first check used the prototype's 1152-life curve (+0.7645 at 91, −0.1045 at
  169) as the reference and a 3 SE threshold. That reference was itself about 2.3 SE high at 91 and low at 169 (against 4608 fresh Gaussian lives), and
  it drew Gaussian frozen normals where the kernel draws Irwin-Hall ones. The reference is now bell3.c with
  Irwin-Hall(12) normals on 4608 lives per size (seeds 9,000,000 + s): +0.5629 ± 0.0017, +0.7324 ± 0.0078 and
  +0.0251 ± 0.0194 at 37, 91 and 169. The kernel's 576 lives (+0.5608 ± 0.0054, +0.7124 ± 0.0220, +0.0509 ± 0.0564)
  give z −0.37, −0.85 and +0.43, all within 2 SE.
  - Irwin-Hall minus Gaussian on the same prototype seeds: +0.0007 ± 0.0024, +0.0060 ± 0.0111 and +0.0278 ± 0.0275
    (unpaired). The lift at large sizes is not resolved at 4608 lives.
  - The milestone-1 check of the kernel on the 36 registration seeds (n* = 91 among 37, 91 and 169) still passes
    and is reported.
- **Verdict.** PASS. The re-registered reference is n* = 61 (flat to 91), F* = +0.71, about 22 times a lone cell.
- **In plain words.** The hand-built heart is best at about 61-91 cells and earns about 22 times what one cell
  earns, not 28 times. Beyond about 130 cells it loses money.

## G4. The ablation ladder (re-registered)

- **Criteria.**
  - chain_F and ladder_F: along each chain, each organism's F* exceeds the next one's by more than 2 paired SE (each
    at its own n*, lives matched by seed);
  - chain_n and ladder_n: n* does not increase along a chain;
  - no_edge: no n* sits at the largest size measured (169; 37 for L0 and L1).
- **Registered** (36 lives). R25-v1 [91, 0.928] > no-LBT [61, 0.573] > naive [37, 0.384] > flood [3, 0.046] > no
  messages [1, 0.033]. Ladder: L4 [91, 0.905], L3 [91, 0.745], L2 [37, 0.434], L1 [3, 0.046], L0 [1, 0.033].
- **Measured** (144 fresh lives per point):

| organism | n* | F* ± SE | flat top | step to the next (ΔF ± SE, z) |
|---|---|---|---|---|
| R25-v1 | 61 | +0.713 ± 0.025 | 61, 91 | +0.183 ± 0.028 (6.5) |
| R25-v1 without listen-before-talk | 37 | +0.530 ± 0.017 | 37, 61 | +0.133 ± 0.034 (3.9) |
| R25-v1 with naive growth | 37 | +0.398 ± 0.030 | 37 | +0.354 ± 0.030 (12.0) |
| L1 flood from the zygote | 3 | +0.044 ± 0.001 | 3 | +0.011 ± 0.001 (19.5) |
| L0 no messages | 1 | +0.0326 | 1 | |
| L4 (AOFF, layered, LBT) | 91 | +0.788 ± 0.033 | 91 | +0.193 ± 0.042 (4.6) |
| L3 (AOFF, layered) | 61 | +0.594 ± 0.034 | 61 | +0.262 ± 0.049 (5.4) |
| L2 (AOFF, naive) | 37 | +0.332 ± 0.032 | 37, 61 | +0.289 ± 0.032 (8.9) |

- **Verdict.** PASS. Every step of both chains is separated by at least 3.9 paired SE. Most registered F* were high
  (by 0.21 for R25-v1, 0.15 for L3, 0.12 for L4), naive growth was not (+0.384 registered vs +0.398); the order
  holds.
- **In plain words.** Each trick (pass messages, grow ring by ring, let newborns listen first) still raises both the
  best size and the earnings, and the best size always stays finite.

## G5. Frozen heterogeneity sets the size bound

- **Criteria.**
  - no_frozen_unbounded: with delay_sd = tau_mis = 0, n* ≥ 397, and F(547) exceeds F(91) by more than 2 paired SE;
  - default_bounded: with the v1 physics, n* ≤ 169 and F(547) < 0.
  - The lockstep control (every d_c = 1, no jitter, no mismatch, clocks in phase) is reported.
- **Registered** (L4, 12 lives). No frozen heterogeneity: +1.71, +2.92, +5.94 and +5.24 at 91, 169, 397 and 547.
- **Measured** (R25-v1, 48 fresh lives):

| condition | 91 | 169 | 271 | 397 | 547 | n* |
|---|---|---|---|---|---|---|
| default | +0.69 ± 0.10 | −0.24 ± 0.22 | −2.45 ± 0.28 | −5.41 ± 0.28 | −8.40 ± 0.29 | 91 |
| no frozen heterogeneity | +1.89 ± 0.08 | +3.26 ± 0.14 | +4.54 ± 0.25 | +5.43 ± 0.49 | +5.20 ± 0.91 | 397 (flat to 547) |
| lockstep | +1.92 ± 0.12 | +3.14 ± 0.24 | +4.20 ± 0.47 | +4.75 ± 0.81 | +4.87 ± 1.13 | 547 (flat 169-547) |

- **Verdict.** PASS: without frozen heterogeneity F(547) − F(91) = +3.31 (paired z 3.7).
  - The curve stops rising near 400 cells: 397 and 547 are statistically equal. The bound moves out past 400 cells
    within the range tested; it is not shown to vanish.
  - With the v1 physics the bound sits at 61-91 cells.
- **In plain words.** What limits the heart's size is that every contact and every cell is slightly different.
  Remove those differences and much bigger hearts pay.

## G6. Spikes undelivered from T/2

- **Criterion.** In the window [T/2, T], income per cell of a contacts_off fork (spikes undelivered from T/2, costs
  still charged) is at most 10% of the intact twin's, for R25-v1 and for its GRN genome (cap 91, 144 fresh lives).
- **Registered.** 35e-3 → 1.0e-3.
- **Measured.**
  - R25-v1: 31.9e-3 → 1.41e-3 (4.4%); window F +0.897 ± 0.066 → −1.947 ± 0.003.
  - The GRN genome (ABI 2, n_view gate): 32.6e-3 → 1.36e-3 (4.2%); window F +0.962 ± 0.057 → −1.951 ± 0.003. The
    ABI-1 genome (flank_best gate) gave the same to the digits shown (32.57e-3 → 1.36e-3).
- **Verdict.** PASS.
- **In plain words.** If the cells stop hearing each other halfway through life, the pumping stops almost at once,
  so the beat is held together by messages on every beat.

## G7. Income per cell never exceeds the lone-cell rate

- **Criteria.**
  - lives_below_lone: every body life (cap > 1) measured by any gate earns at most the largest income per cell-unit
    of any lone life on G1's fresh lives (54.0e-3);
  - means_below_lone: every point's mean is at most the best lone phenotype's mean rate (53.8e-3).
- **Scope.** All bodies of G2-G6, G9, G10 and S8, plus the bursting body B at 37, 91 and 169 cells, including G6's
  [T/2, T] windows: 212 points, 30,960 lives (ABI 1: 215 points and 31,392 lives; G10's GRN block now has two
  genomes, not three). The measured values below are unchanged.
- **Registered.** ≤ 54e-3.
- **Measured.**
  - Largest body life: 49.6e-3 (R25-v1 without LBT, 3 cells).
  - Largest point mean: 47.1e-3.
  - B's largest life: 37.1e-3.
- **Verdict.** PASS.
- **In plain words.** No body, however it is built, earns more per cell than a single cell pumping alone, so
  splitting into sparse bodies cannot farm the pump.

## G8. Closed-form lumen and scheduler invariance

- **Criteria.**
  - The closed-form lumen agrees with explicit Euler (dt 1e-3) within 0.1% on growing R25-v1 bodies of 1, 37 and 91
    cells, and halving dt halves the error.
  - The same lives with 1 and 4 threads are bitwise equal.
  - Uncapped lives under the window scheduler (h 1/2 and 1/8) equal the heap's bitwise.
- **Registered.** 0.03-0.08%.
- **Measured.** Largest error 0.024%; halving ratios 0.40-0.60; threads and window scheduler bitwise.
- **Verdict.** PASS. Tests T1-T5, T11 and T12 run in tests/test_life_time.py. T6-T10 are not implemented (integer
  twin, statistical and evolved-organism tests).
  - Update (2026-10-07, integration step): T6 now runs in float. A start at t0 = 1024 leaves every count equal and
    changes F by at most about 2e-12, within the design's 1e-9. Its integer-twin half, and T7-T10, are still open.
- **In plain words.** The pump is computed exactly, and the result does not depend on how the simulation is
  scheduled.

## G9. R25-v1 as a GRN genome

- **Criteria.**
  - within_2se: at the oracle cap 91, |F_GRN − F_program| ≤ 2 combined SE, over 288 fresh lives (the design asks
    for 36).
  - phenotypes: in every settled gene state the genome decodes exactly the program's row on every knob a program row
    uses.
- **The genome** (`handbuilt.r25_genome`, a raw float32 793-slot genome, run through `spec.pack_genomes` in GRN
  mode). Five active genes:
  - contact (λ 1/2): on when n_view ≥ 1. Its partition is Q −1, so a daughter starts alone.
  - juvenile (λ 1/16, Q +1): a daughter starts at 1, and the gene silences emission for exactly her first 10 own
    ticks.
  - rim gate (λ 1/2, Q −1): on when n_view ≥ 5, read from the live-contact fraction n_view / 6. It switches p_div
    between 1/2 and 1/16. Placement keeps the flank term (φ 2).
  - contact echo (λ 1/2): a one-tick-delayed copy of the contact gene. The readout uses 2·contact − echo, which
    makes the switch from alone to contact exact at the first tick that sees a contact.
  - division reset (λ 1/2, Q −1): cancels the gate gene's forced opening in a mother after a claim.
- **ABI 2 (2026-10-07).** The gene network has no flank_best input any more (LIFE_ABI.md 15.32). Under ABI 1 the
  gate gene read flank_best = 2, exactly like the program's gate. Now it reads n_view, the variant G10 measured as
  good as the flank_best gate in GRN mode (F* +0.754 vs +0.753). The program R25-v1 still gates on flank_best: program
  mode keeps that rule as a hand-built reference. So G9 now compares two equivalent growth rules, not one rule
  written two ways.
- **Registered.** Within 2 SE over 36 lives at cap 91.
- **Measured** (288 fresh lives, the same lives as G3):

| N | program | GRN genome (ABI 2, n_view gate) | z | paired ΔF | ABI 1 genome (flank_best gate), z |
|---|---|---|---|---|---|
| 37 | +0.566 ± 0.008 | +0.564 ± 0.008 | −0.17 | −0.002 ± 0.008 | +0.563 ± 0.008, −0.22 |
| 91 | +0.697 ± 0.033 | +0.690 ± 0.032 | −0.15 | −0.007 ± 0.031 | +0.698 ± 0.030, +0.04 |
| 169 | −0.220 ± 0.088 | −0.207 ± 0.084 | +0.11 | +0.013 ± 0.070 | −0.174 ± 0.083, +0.37 |

- **Every settled state** (alone, juvenile or adult with the gate open or closed, first contact tick, a mother just
  after a claim) decodes exactly the program row.
- **The design's minimal 3-gene sketch** (no echo, no reset) scores +0.652 ± 0.058 at 91 (144 lives; z −0.78
  against the program). With the ABI-1 flank_best gate it scored +0.668 ± 0.054 (z −0.59).
- **Verdict.** PASS.
- **In plain words.** The hand-built heart can be written in the same gene language evolution searches, and it
  scores the same. Its growth gate now counts live neighbours instead of reading a special "flank" signal, and it
  still matches the hand-built program. So the target is reachable in principle.

## G10. D4 (flank placement and gate), D5 (refined t_ref grid), and the GRN layer

- **Criteria.**
  - d4_layered: R25-v1's layered growth (flank placement plus the flank-best rate gate) beats placement only, gate
    only and neither by more than 2 paired SE in F* (program mode).
  - d4_grn_placement (ABI 2; under ABI 1 this was d4_flank_gate): in GRN mode, R25-v1's genome (n_view ≥ 5 gate,
    flank placement) beats the registered alternative by more than 2 paired SE. The alternative is the same n_view
    ≥ 5 gate with random placement, the prototype's dir 4. Since ABI 2 has no flank_best input, the two differ only
    in the placement term. ABI 1's d4_flank_gate compared a flank_best-gated genome with that alternative instead
    (passed, z 2.9).
  - d5_refined: R25-v1 (t_ref 2.5) beats the best phenotype on the old t_ref grid (0.5, 1, 2, 4) by more than 2
    paired SE in F*. The best old-grid phenotype is chosen by a screen at 91 cells on screen seeds.
  - grn_layer: a lone GRN cell with a constant readout is bitwise identical to the program-mode lone cell, and the
    R25-v1 genome is within 2 SE of the program at 37, 91 and 169 cells.
- **Registered.** D4: n_view gating "about 23% weaker" than the flank gate. D5: best old-grid phenotype 0.693 vs
  0.928 at t_ref 2.5.
- **Measured** (144 fresh lives per point).
  - **D4, program mode** (F* over 37-127 cells):

    | variant | n* | F* ± SE | layered minus variant (ΔF ± SE, z) |
    |---|---|---|---|
    | layered (placement + gate) | 61 | +0.713 ± 0.025 | |
    | gate only (φ 0) | 61 | +0.657 ± 0.035 | +0.057 ± 0.037 (**1.5**) |
    | placement only (no gate) | 37 | +0.475 ± 0.031 | +0.239 ± 0.034 (7.1) |
    | neither (random, p 1/2) | 37 | +0.334 ± 0.038 | +0.380 ± 0.043 (8.7) |

  - **D4, GRN mode** (F* over 61-127):
    - ABI 2: R25-v1's genome (n_view gate, flank placement): +0.754 ± 0.042 (n* 91, flat top 61-91);
    - ABI 2: n_view gate with random placement: +0.638 ± 0.029 (n* 61), 15% weaker, ΔF +0.116 ± 0.041, z 2.8;
    - both are bitwise the lives ABI 1 gave the same two genomes (their F* agree to every digit);
    - ABI 1 only (kept in `d4_grn.abi1`): the flank_best gate with flank placement, +0.753 ± 0.040 (n* 91). The
      n_view gate with flank placement differed from it by −0.001 ± 0.013 (paired), and with random placement by
      −0.115 ± 0.040 (z 2.9). This is the evidence for removing the flank_best input.
  - **D5:**
    - The screen (96 coupled rows at 91 cells) picks C1 (b 1.125, τ 1, t_ref 2, w0 −0.75) as the best old-grid
      phenotype, the same one the design registered, and R25-v1 itself as the best refined one.
    - C1 scores +0.481 ± 0.026 (n* 61), against R25-v1's +0.713: ΔF +0.233 ± 0.026, z 8.9.
    - t_ref sweep of R25-v1 at 91 cells: −1.74, −1.77, −1.79, +0.05, **+0.71**, −0.34, −0.36 and −1.63 for t_ref
      0.5 to 4.
  - **GRN layer:** the lone GRN cell is bitwise the program cell; G9's z are −0.17, −0.15 and +0.11 (ABI 1: −0.22,
    +0.04 and +0.37).
- **Verdict.** **FAIL**, on d4_layered only:
  - The rate gate is what matters: without it the body loses +0.24 (z 7.1).
  - The flank term in placement adds only +0.057 ± 0.037, which 144 lives do not resolve.
  - The registered n_view comparison held under ABI 1 (15% weaker, z 2.9), but only because it also removes flank
    placement. With flank placement kept, the n_view ≥ 5 gate is exactly as good as the flank-best gate on hex. So on
    hex the GRN input flank_best / 2 was not needed for layered growth when n_view is available. ABI 2 removed it
    (LIFE_ABI.md 15.32) and kept the placement term φ·flank(e). On square8 the n_view gate is weaker (S8).
  - Under ABI 2 the GRN check isolates that placement term: with the n_view gate, flank placement beats random
    placement by +0.116 ± 0.041 (z 2.8). In program mode, with the flank_best gate, the same term adds only
    +0.057 ± 0.037 (z 1.5). Placement seems to matter more when the rate gate cannot see flanks; the two numbers
    come from different gates and are not a paired comparison.
  - D5 holds strongly: t_ref 2.5 is a sharp optimum, and the refinement of the grid is needed.
- **In plain words.** Refining the refractory-time grid was right. Of the two parts of "layered growth", slowing
  division at the rim matters a lot. Choosing the most enclosed empty spot adds a little in the hand-built program
  that I could not confirm, but clearly helps the gene version. The special "flank" input to the genes was replaced
  by the plain neighbour count, which works as well on hex. On the square grid with diagonal contacts it works
  less well (S8).

## S8. The square8 size curve

- **Criterion.** bounded: R25-v1, as built for hex, has an interior n* on square8 (not the largest size measured,
  and F there below F*).
- **Also reported:**
  - a re-tuning screen for 8 contacts: b, w0, δ and t_ref of the coupled row, with and without the flank gate (72
    variants at 121 cells, 16 screen lives);
  - the R25-v1 genome with n_view weights for D = 8.
- **Registered.** Nothing: G10 only asks that this curve be measured before any square8 run.
- **Measured** (144 fresh lives; sizes are complete squares (2r + 1)^2):

| N | 1 | 9 | 25 | 49 | 81 | 121 | 169 | 225 | 289 |
|---|---|---|---|---|---|---|---|---|---|
| F | +0.033 | +0.197 | +0.479 | +0.803 | +1.086 | **+1.151** | +0.735 | +0.078 | −1.118 |
| SE | 0.000 | 0.001 | 0.004 | 0.012 | 0.026 | 0.063 | 0.118 | 0.170 | 0.222 |

- **n\* and F\*.** n* = 121, F* = +1.151 ± 0.063, flat top 81-121. On hex the same organism has n* 61 and F* +0.711.
- **Re-tuning.** The screen's best variant (b 1.25, w0 −0.75, δ 2, t_ref 2.5, gate on) scores +1.072 at 121 on the
  fresh lives, ΔF −0.079 ± 0.056 against R25-v1. No hex-tuned parameter in the screen needed re-tuning; the screen's
  apparent gain was a winner's curse.
- **The GRN genome** (D = 8; ABI 2, rate gate at n_view ≥ 7) at 121: +0.978 ± 0.073, z −1.79 against the program
  (the reported check, unpaired, passes). Paired on the same lives it is −0.173 ± 0.080 (z −2.18; computed
  separately, not stored in gates.json). On 144 screen lives the same genome is only −0.035 ± 0.074 below the
  program, and gates at n_view ≥ 5 or ≥ 6 give −0.077 ± 0.097 and +0.026 ± 0.065: no threshold is clearly better,
  and the fresh-life shortfall is not reproduced. Unresolved; the genome is not re-tuned. ABI 1's flank_best-gated
  genome scored +1.109 ± 0.068 (z −0.45).
- **The GRN genome without the flank_best input** (review, 2026-10-07; `results/flank_square8/`, pinned by
  `test_square8_n_view_gate_against_the_abi1_flank_gate`). G10's evidence for removing the input came from hex only.
  Here is the same pair on square8: R25-v1's genome gated on n_view ≥ 7 (ABI 2), against its ABI-1 twin gated on
  flank_best, both with flank placement. Paired on the same 288 fresh lives per size (the program's lives are
  bitwise equal in both trees):

  | N | 49 | 81 | 121 | 169 |
  |---|---|---|---|---|
  | flank_best gate (ABI 1) | +0.791 | +1.056 | **+1.096** | +0.893 |
  | n_view gate (ABI 2) | +0.777 | +1.006 | **+1.015** | +0.727 |
  | paired difference (SE) | −0.013 (0.010) | −0.051 (0.020) | −0.081 (0.052) | −0.165 (0.065) |
  | z | −1.3 | −2.5 | −1.6 | −2.5 |

  - F* drops by 7%, and the n_view genome is lower at every size. On hex the same pair is equal (|z| < 1 at 61, 91
    and 127 cells), as G10 found.
  - Gates at n_view ≥ 5, 6 and 7 (144 lives) are all below the flank_best gate at 81, 121 and 169 cells, by
    −0.02 to −0.47.
  - So on square8 the removal costs the hand-built genome F. This matters for the square8 pilot arm, not only for a
    seeded control: there, evolution must find layered growth without the cue that the hand-built genome needs. The
    kernel is unchanged; whether the square8 arm should keep flank_best is the user's decision.
- **Verdict.** PASS.
- **In plain words.** On the square grid with diagonal contacts, the same heart grows bigger (about 121 cells) and
  earns about 60% more than on hex. The hex settings work there as they are. The gene version of the heart lost
  about 7% there when its special "flank" input was removed; on hex it lost nothing.

## Deviations from the design, and choices it left open

1. **Fresh lives with common random numbers.** The design asks for 36 lives per point. Every gate here uses 144 or
   288 fresh lives (48 for G5), with the same seeds across sizes, organisms and conditions. This is the
   re-registration the user asked for. The registered values are kept in gates.json.
2. **G1.** The fresh re-registration covers the 1080 phenotypes with b ≥ 1 and κ > 0. The other 4200 are inert on
   the registration screen.
3. **G2.**
   - The design's messages-off GA control belongs to the evolution side, so a program-mode search replaces it here.
   - "Messages off" switches off spikes only. Contact notices still flow. Program-mode cells cannot read morphogens.
4. **G3.**
   - n* moved from 91 to 61 on fresh lives. The top is flat from 61 to 91.
   - "Rises" requires a positive step at every size up to n*, and a step of more than 2 SE below the flat top.
5. **G4.**
   - Both the design's ablation chain and the prototype's L0-L4 ladder are gated.
   - The registered n* values (91, 61) are now 61, 37 for R25-v1 and no-LBT.
6. **G5.**
   - The gate measures R25-v1, the design's reference, instead of the registration's L4.
   - "No frozen heterogeneity" sets delay_sd = tau_mis = 0 and keeps the clock spread, as the prototype did.
   - Up to 547 cells, the bound moves out past 400 cells rather than vanishing.
7. **G6.** The GRN genome is gated too. Forks are replays (LIFE_ABI.md 12).
8. **G7.**
   - "The lone-cell rate" is the largest income rate of any lone life on G1's fresh lives.
   - Points at cap 1 are lone cells and are excluded.
9. **G9.**
   - The genome has 5 genes. Two of them (contact echo, division reset) go beyond the design's 3-gene sketch.
   - They were chosen on exploration seeds, because the sketch's gate gene, forced open in a mother by its
     partition, made the GRN body divide too fast after each claim (−0.06 at 91 on exploration lives).
   - The sketch itself is reported (+0.652 ± 0.058 at 91 under ABI 2, within 2 SE; +0.668 ± 0.054 under ABI 1).
   - Since ABI 2 the genome's rate gate reads n_view, not flank_best (LIFE_ABI.md 15.32), while the program still
     gates on flank_best. G9 therefore compares two growth rules that G10 measured as equally good on hex, not one
     rule written twice.
   - One known difference remains: a juvenile mother becomes adult at her first division (Q +1, as the design
     specifies). The program keeps her silent until her own tick 10.
10. **G10.**
    - The design's G10 sentence ("G1-G4 hold within 2 SE with Q10 and the full GRN layer") is checked for G1 and the
      R25-v1 curve of G3 only (grn_layer): the lone GRN cell is bitwise the program cell, and R25-v1's GRN genome is
      within 2 SE of the program at 37, 91 and 169 cells. G2 and G4 are not run in GRN mode (see G2's scope note).
      Q10 is always on in the kernel.
    - D4's n_view comparison was first run with flank placement kept, which showed no difference. It was then
      corrected to the registered definition (random placement, e5 dir 4). Both are reported. The d4_layered
      criterion was fixed before any fresh measurement and fails.
11. **S8.** The square8 sizes are complete squares rather than hexagonal numbers.
12. **One bug fixed (spec/reference).** `spec.sigmoid` raised OverflowError for x below about −709.78, where C
    returns exactly 0. A genome with such a readout would have crashed the reference while the kernel ran it. It now
    returns 0.0 there, mirroring C (LIFE_ABI.md section 2). The kernel is unchanged, so T1-T12 stay bitwise.
13. **Not done.**
    - The integer twin and tests T7-T10 (G8 note; T6 runs in float since the integration step).
    - The optional lineage-timer gene of G9, for uncapped size control: built (`r25_genome(timer=...)`), not
      measured.
14. **ABI 2: the gene network's flank_best input was removed (2026-10-07, approved by the user before the pilot).**
    - Why: under ABI 1, G10 measured an n_view gate with flank placement as good as the flank_best gate in GRN mode
      on hex (+0.754 vs +0.753, paired −0.001 ± 0.013). The dedicated input was a hand-coded rule that n_view already
      covers on hex. Details and the neutrality check: LIFE_ABI.md 15.32.
    - Not on square8 (review, 2026-10-07): there the n_view-gated genome is below its flank_best-gated ABI-1 twin at
      every size (F* −7%; z −2.5 at 81 and 169 cells), and no n_view threshold closes the gap (S8).
    - What was re-measured: G9, G10's GRN block and grn_layer, S8's GRN genome, G6's GRN rows and G7's scope. Every
      program-mode number is unchanged (G1-G5 and G8 identical leaf for leaf in gates.json).
    - What changed in the criteria: G10's d4_flank_gate became d4_grn_placement, because its flank_best-gated genome
      can no longer be built. The ABI-1 measurements are kept in gates.json (`abi1` entries) and in
      `scripts/life_gates.py` (`ABI1`).

---

# BODY-1 gates GB3-GB13 (the CATCH world, ABI 3)

The pre-registered gates of `docs/BODY_DESIGN_PROPOSAL.md` (section 11) that need the real kernel before any
evolution run in the CATCH world: the hand-built ladder, the cheats, the wire certificate, the 2-hop positive control,
start robustness, the column reflex written as a GRN genome, and the cost of hidden planes. Each gate gives its
criterion, the registered (proposal) value, the measured value with lives and SE, the verdict, and one plain line.

- Produced by `python scripts/life_gates.py --world catch --threads 4` on 2026-10-08 (UTC), after the review fixes
  below; results in `outputs/life_gates/gates_catch.json` (kernel library `life_f5513afc9e42df92.so`, ABI 3). Run time
  808 s on 4 threads on a shared machine.
- **Review fixes (2026-10-08) changed the world and two gates** (LIFE_ABI.md 15.58-15.60):
  - **c_miss 2** (was the proposal's 1): a slow blind presser beat the lone zygote at c_miss 1 (+0.0085, z 4.2). Every
    life is unchanged; every F moves by −misses / T (the clicker by −0.026, ring 3 by −0.042).
  - **The drag counts the projected footprint** (every occupied column in any plane, not the sense-plane cells only):
    a clicker with two footless tonic drifters beat the 4-column body at drag 1 (+0.068, z 14) and was a 4-cell
    local optimum. Every body of complete columns lives bitwise as before, so of the bodies below only the runners
    and the blind spam-runner changed.
  - **GB6** forks receptor_off too and must catch a blind relay clicker; **GB7** screens blind pressers over the GRN
    grid, adds two blind GRN genomes, and screens runners with 1, 2 and 3 drifters.
  - The run before the fixes (kernel `life_5c65f605cba3402e.so`, c_miss 1, the old drag) also passed 9 of 9; its
    numbers are in the git history of this file.
- Pinned by `tests/test_life_gates.py` (slow), as for G1-G10: each test recomputes part of its gate, asserts the stored
  numbers exactly when gates_catch.json was written by the library in use, and re-judges the stored verdicts.
- GB1 (BELL-1 bitwise under ABI 3) and GB2 (heap = window for CATCH lives) are tests (`test_life_world_bell.py`,
  `test_life_time.py`); GB10 (the founder census) and GB11 (growth stops, read from the pilot) belong to the census and
  the pilot. GB3-GB9, GB12 and GB13 are here.
- **Result: 9 of 9 pass.**

## How the CATCH gates measure

- **Bodies.** `src/life/handbuilt.py` (BODY-1 section): program-mode bodies placed at t0, one fixed program row per
  cell, copied from the prototype's `common.rows_A` with its off-grid values (centre sensor g_r 0.55, drifters b 1.1,
  the presser's kappa 0.6). Sensors relay every receptor event on channel 0, the motor above each listens (w0 1,
  kappa 1, t_ref 4), and the centre sensor is a coincidence detector. World `catch_v1` (L_max 4, the user's design);
  a body without hidden cells lives bitwise alike at L_max 2 (GB13).
- **Fresh lives.** Seeds `15,000,000 + s`, shared by every body and every world (common random numbers), so steps
  between bodies are paired life by life. 2048 lives per point for bodies of at most 14 cells, 512 for larger ones,
  256 for the forks (GB6) and the genome (GB9). Screens that choose a candidate (the runners, the blind pressers, the
  grower's window) use `16,000,000 + s`; the gates and the genome were designed on exploration seeds `7,000,000 + s`,
  which no gate uses.
- **The prototype reference.** The proposal's numbers come from 128-512 lives each. For the port checks the prototype
  (`body_design/critique/cursor.c`, an unchanged copy, md5 `10e2811877882af7c2ef1616e48eeecf`) was re-run on 1024-4096
  fresh prototype lives per point (seeds `cur.seeds_for(n, 700000 + i)`), with the same bodies; the values are stored in
  `life_gates.PROTOTYPE_CATCH`. The prototype has no receptor charge and ran at c_miss 1, so the kernel's F is re-priced
  at its prices (`analysis.PROTOTYPE_PRICES`: c_rec 0, c_miss 1) from its own ledger before the comparison. Prices
  never change a life, so this is exact. A port check passes at 3 combined SE per point (several points per gate).
  Bodies with footless act cells (the runners and the spam-runner) are not ported after the drag tweak, since the
  prototype's drag counted sense-plane cells only; before it they ported within 0.8 SE. Correlated luck: all bodies
  share the target paths of a seed, so one seed set moves every body the same way, and the port z values below are
  not independent.

## Summary

| gate | criterion (short) | measured, fresh lives (mean ± SE) | verdict |
|---|---|---|---|
| GB3 | lone zygote below the 2-cell clicker by 2 SE | −0.0203 vs +0.0237 ± 0.0023, paired +0.044 ± 0.002 (z 19; n 2048) | PASS |
| GB4 | ring curve rises to an interior optimum, F* > 20× clicker; prototype within 3 SE | n* = ring 3 (74 cells), F* = +3.892 ± 0.025, 164× the clicker; max port z 2.67 | PASS |
| GB5 | no column step below its parent by 2 SE, 3 orders (+ ring 1 → 2); prototype within 3 SE | 29 of 30 steps uphill, none down; max port z 2.71 | PASS |
| GB6 | contacts+chem+division off at T/2, and receptor_off at T/2, each remove ≥ 95% of second-half income; the blind relay is caught | 99.6-100% at rings 0-6 and on two grown GRN bodies, under both forks; blind relay: certificate 100%, receptor_off 0% | PASS |
| GB7 | every cheat loses (blind ones to the clicker and the lone zygote, islands to ring 1, runners with 1-3 drifters not above the 4-cell column) | best blind presser −0.046 (lone −0.020), blind GRN genomes −0.061, spam-runner −0.510, tonic rings −0.523 / −1.024, islands −0.226 (ring 1 +0.996); runners +0.060 / +0.043 / +0.053 vs the 4-cell column +0.071 | PASS |
| GB8 | 2-hop centre hold pays at ring 1; lateral-off removes ≥ 50% of the gain | +0.484 ± 0.011 (prototype +0.463); lateral-off removes 100% | PASS |
| GB9 | the column reflex as a GRN genome matches its program twin | rings 0 and 1 grow exactly (256/256); after growth z +0.05 and −0.04; grown 80-cell disk −0.031 ± 0.042 vs its twins | PASS |
| GB12 | v1 inside the good start region; the clicker margin vanishes where the prototype's does | v1 uphill at every first step; clicker earns at v_t 0.2 and R_cap 200, not at v_t 0.05 and R_cap 50 | PASS |
| GB13 | silent hidden cells cost exactly c_live; L_max 2 = L_max 4 | residual ≤ 8e-14; bitwise equal for program rings and grown GRN bodies | PASS |

## GB3. The first division pays

- **Criterion.** The lone zygote (the centre sensor alone, no act cell) is below the 2-cell clicker (one upward
  division) by more than 2 paired SE; the lone zygote has no click and no income.
- **Registered.** −0.020 against +0.045 ± 0.004 (proposal 3.2, crit, n 512, c_miss 1).
- **Measured** (2048 lives). Lone −0.0203. Clicker +0.0237 ± 0.0023 (26.2 misses per life at c_miss 2; at the
  prototype's prices +0.0494, prototype +0.0420 ± 0.0016, z +2.7). Step +0.0440 ± 0.0023, z 19.
- **Verdict.** PASS.
- **Porting note.** The kernel's clicker sits above the prototype's on every seed set measured: +0.0458 ± 0.0008 pooled
  over 16,384 extra kernel lives at the prototype's prices (seeds 30,000,000 and 40,000,000 + s, not stored), against
  +0.0420 ± 0.0016, about +9% (z 2.1). This fresh set is luckier. Unresolved; candidates are the kernel's Q10 membrane
  register and its tick re-anchors (the prototype has neither), which shift the centre sensor's coincidence window
  slightly. At ring 3 the same check gives +3.908 ± 0.009 against +3.907 ± 0.013 (no offset).
- **In plain words.** One cell that only senses loses its upkeep; the moment it divides once upward and the daughter
  presses the button when the mother sees the target twice in quick succession, the pair earns money. At c_miss 2 it
  earns about half of what it earned at c_miss 1, still 19 SE above the lone cell.

## GB4. The ring ladder

- **Criteria.** rises: every ring step up to n* positive by more than 2 paired SE; interior: n* is not the largest ring
  and F there is below F* by more than 2 SE; ratio: F* > 20 × F(ring 0); port: every ring within 3 SE of the prototype.
- **Registered.** Monotone to an interior optimum at ring 3 (74 cells), +3.849 (synth) / +3.907 ± 0.051 (crit), 65-87 ×
  the clicker (c_miss 1); −3.19 at ring 6.
- **Measured** (2048 lives for rings 0-1, 512 for 2-6; F, F at the prototype's prices, prototype, z):

| ring (cells) | F ± SE | F, prototype prices | prototype (n) | z | captures | misses | speed |
|---|---|---|---|---|---|---|---|
| 0 (2) | +0.0237 ± 0.0023 | +0.0494 | +0.0420 ± 0.0016 (4096) | +2.67 | 1.2 | 26.2 | 0 |
| 1 (14) | +0.9962 ± 0.0079 | +1.0594 | +1.0497 ± 0.0056 (4096) | +0.99 | 14.5 | 61.3 | 0.387 |
| 2 (38) | +2.9290 ± 0.0241 | +2.9840 | +2.9544 ± 0.0132 (2048) | +1.07 | 39.4 | 47.1 | 0.379 |
| **3 (74)** | **+3.8921 ± 0.0245** | +3.9510 | +3.9069 ± 0.0126 (2048) | +1.60 | 57.3 | 43.3 | 0.412 |
| 4 (122) | +3.3622 ± 0.0199 | +3.4376 | +3.3912 ± 0.0134 (1024) | +1.94 | 62.7 | 51.6 | 0.413 |
| 5 (182) | +0.9718 ± 0.0180 | +1.0728 | +1.0873 ± 0.0127 (1024) | −0.66 | 51.7 | 70.6 | 0.345 |
| 6 (254) | −3.3167 ± 0.0173 | −3.1823 | −3.2099 ± 0.0121 (1024) | +1.32 | 23.7 | 99.7 | 0.250 |

- Paired steps: +0.972 (z 119), +1.920 (70), +0.963 (32), then −0.530 (−21), −2.390, −4.289. n* = ring 3, flat top
  {3}; ring 6 is 7.21 below it. F* / F(ring 0) = 164 (80 at c_miss 1: the clicker pays most of the miss cost).
- **Verdict.** PASS.
- **In plain words.** Adding whole rings of sensing columns pays up to three rings (74 cells); beyond that the upkeep
  of cells that only see what the rim already sees wins, and at six rings the body loses money. The kernel
  reproduces the prototype's curve.

## GB5. Column by column

- **Criteria.** no_valley: no step below its parent by more than 2 paired SE, in three orders of adding the six ring-1
  columns to the clicker (adjacent, opposite pairs first, alternating) and in angular order from ring 1 to ring 2;
  port: every partial body within 3 SE of the prototype. Uphill steps are counted, not gated.
- **Registered.** Every intermediate step uphill in every order tried (synth: +0.045 → +0.091 → +0.222 → +0.310 →
  +0.448 → +0.747 → +1.045).
- **Measured** (2048 lives up to 14 cells, 512 beyond):

| order | 2 cells | 4 | 6 | 8 | 10 | 12 | 14 |
|---|---|---|---|---|---|---|---|
| adjacent | +0.024 | +0.071 | +0.203 | +0.291 | +0.443 | +0.694 | +0.996 |
| opposite pairs first | +0.024 | +0.071 | +0.094 | +0.253 | +0.472 | +0.694 | +0.996 |
| alternating | +0.024 | +0.071 | +0.109 | +0.155 | +0.403 | +0.694 | +0.996 |

  - Every step of the three orders is uphill (z 5.4 to 36.4; the faintest is the opposite pair, +0.023 ± 0.004).
  - Ring 1 → ring 2, one column at a time: +1.009, +1.128, +1.189, +1.342, +1.376, +1.508, +1.663, +1.882, +2.065,
    +2.350, +2.542, +2.731, +2.929. Steps z 1.6 to 10.9; one step (3 → 4 added columns, +0.035 ± 0.022) is flat, none
    falls.
  - Port: 22 partial bodies, largest |z| 2.71 (adjacent, 12 cells), as before the fixes (the same lives).
- **Verdict.** PASS (29 of 30 steps uphill, none down).
- **In plain words.** However the first columns are added, each one makes the body richer: there is no valley to
  cross on the way from two cells to a full disk.

## GB6. The wire certificate

- **Criteria.** wire: a fork at T/2 with `contacts_off | chem_off | division_off` (t_open = T/2; the twin has
  t_open = T/2 only) removes at least 95% of the second half's income, and so does a fork with `receptor_off`, at every
  ring 0-6 and, beyond the registration, on two grown bodies of the column genome (ring 1, and the window-0.16 disk of
  about 80 cells), whose cells could also talk through morphogens. blind_relay_caught: the blind relay clicker
  (`handbuilt.BLIND_RELAY_GRN`: a zygote with no receptor fires tonically and relays to the motor above it) passes the
  certificate but keeps at least half its income under receptor_off, so the joint check rejects it.
- **Registered.** ≥ 95% (proposal S0 criterion 3); prototype: contacts-off drops every body to its costs.
- **Why receptor_off** (review fix). The certificate shows that the income needs messages, not that it needs
  sensing: the blind relay needs every message and senses nothing, and it scored msg_reliance 1.0 in the pipeline. A
  passing certificate plus receptor_off means a sense-to-act wire. The CATCH runs now report `sense_reliance` next to
  `msg_reliance` (`clones.SENSE`).
- **Measured** (256 lives): certificate 100% (ring 0), 99.7%, 99.7%, 99.8%, 99.8%, 99.8%, 99.7% (rings 1-6), 99.6% and
  99.7% (GRN ring 1 and disk); receptor_off the same to four digits. The residue is at most one capture per life, from
  a spike sent just before T/2. Blind relay: the certificate removes 100%, receptor_off 0%.
- **Verdict.** PASS.
- **In plain words.** Cut the messages, or blind the sensors, halfway through life and the body stops earning at once:
  every bit of income goes through the sense-to-act wire. A body that clicks blindly through a message is caught.

## GB7. Cheats

- **Criteria.** blind_lose: the blind cheats are below the 2-cell clicker and the lone zygote by more than 2 paired
  SE. They are the spam-runner (a tonic presser plus a footless tonic drifter, no messages), the fixed fast presser
  (b 2, tau_m 2, t_ref 2, kappa 0.6), the best of a screen of 480 blind pressers (a silent zygote under a tonic presser,
  b 1.125-2 × every tau_m × every t_ref × kappa 0.5 and 1, 128 screen lives each), the blind GRN presser and the blind
  GRN relay (`handbuilt.blind_genome`, both evolvable genomes grown from one zygote), and blind tonic act planes of
  rings 1 and 2. islands_lose: the islands (the centre column plus six isolated columns at the ring-3 corners, 14
  cells) are below the compact ring 1 by more than 2 SE. runner_not_a_trap: for 1, 2 and 3 adjacent footless tonic
  drifters beside the clicker, the best of the 108 prototype settings (48 screen lives each, then measured fresh) is
  not above the 4-cell column by more than 2 SE and is below the 6-cell column by more than 2 SE. No income at any ring
  with contacts off from birth; each cheat with feet under every act cell within 3 SE of the prototype. Lateral off
  from birth and the 2- and 3-drifter runners' one-step neighbours are reported.
- **Registered.** Spam-runner −0.207, tonic rings −0.351 / −0.844, islands −0.201 against compact ring 1 +1.081,
  runner +0.094 against the 4-cell column +0.091 and the 6-cell +0.222 (proposal 11); none above the 4-cell column.
- **What the review found** (before the fixes, c_miss 1, drag from sense-plane cells): the slow blind presser
  (b 1.5, tau_m 16, t_ref 2, kappa 1, about 52 clicks per life) beat the lone zygote by +0.0085 ± 0.0020, and its GRN
  version by +0.0108 (z 5.5); a clicker with two footless drifters (b 1.5, tau_m 8, t_ref 4, kappa 1) scored
  +0.156, above the 4-cell column by +0.068 (z 14), and every one-step neighbour of it was lower. The old GB7 tested
  one fast presser and one-drifter runners only, so it passed.
- **Measured** (2048 lives; tonic rings 512):

| cheat | F ± SE | prototype (z) | against | paired difference (z) | vs lone zygote (z) |
|---|---|---|---|---|---|
| blind spam-runner | −0.5104 ± 0.0027 | not ported | clicker | −0.534 (−153) | −0.490 (−179) |
| blind fast presser (fixed) | −0.5117 ± 0.0024 | −0.2163 (−0.4) | clicker | −0.535 (−579) | −0.491 (−202) |
| best blind presser (b 1.125, tau_m 16, t_ref 2.5, kappa 1) | −0.0460 ± 0.0015 | — | clicker | −0.070 (−34) | −0.026 (−17) |
| blind GRN presser | −0.0609 ± 0.0020 | — | clicker | −0.085 (−51) | −0.041 (−21) |
| blind GRN relay | −0.0611 ± 0.0020 | — | clicker | −0.085 (−51) | −0.041 (−21) |
| blind tonic ring 1 (14) | −0.5231 ± 0.0048 | −0.3553 (+1.9) | clicker | −0.552 (−136) | −0.503 (−104) |
| blind tonic ring 2 (38) | −1.0236 ± 0.0045 | −0.8505 (+0.9) | clicker | −1.053 (−288) | −1.003 (−222) |
| islands (14) | −0.2258 ± 0.0023 | −0.2027 (+1.5) | ring 1 | −1.222 (−149) | −0.206 (−91) |
| runner, 1 drifter (b 1.5, tau_m 2, t_ref 1, kappa 1) | +0.0600 ± 0.0027 | not ported | 4-cell column | −0.011 (−2.7) | +0.080 (+29) |
| runner, 2 drifters (b 1.1, tau_m 2, t_ref 4, kappa 1) | +0.0425 ± 0.0029 | not ported | 4-cell column | −0.028 (−7.1) | +0.063 (+22) |
| runner, 3 drifters (b 1.5, tau_m 2, t_ref 4, kappa 1) | +0.0526 ± 0.0030 | not ported | 4-cell column | −0.018 (−4.5) | +0.073 (+24) |
| runner, prototype setting (b 1.1, tau_m 2, t_ref 1, kappa 1) | +0.0418 ± 0.0025 | not ported | 4-cell column | −0.029 (−7.6) | +0.062 (+25) |

  - The prototype column of the blind cheats is at its prices (c_miss 1); their F here is at c_miss 2, where each of
    their many misses costs twice as much.
  - Every runner is 0.14-0.16 below the 6-cell column (z −27 to −31). The 2-drifter runner is no longer a local
    optimum: a sensing column at (0, −1) or (0, 1) raises it by +0.027 (z 6.4) and +0.021 (z 4.9); dropping a drifter
    (−0.028), a column on the far side (−0.058, −0.066) and sensing feet under the drifters (−0.042) lower it. From the
    3-drifter runner, dropping a drifter is uphill (+0.017, z 4.6).
  - Contacts off from birth: no click and no income at any ring. Lateral off from birth: |ΔF| ≤ 0.0084 at every ring,
    all within 1.3 paired SE. Not bitwise: in-plane arrivals carry weight 0 in the column reflex, but they still
    re-anchor the receiver's Q10 membrane (the prototype ignored zero-weight arrivals).
- **Verdict.** PASS.
- **In plain words.** Pressing blindly, fast or slow, drifting blindly and spreading out in disconnected pieces all
  lose money; drifting so the target crosses the button more often earns a little, but less than growing one more
  sensing column, and from a drifting body a sensing column is an uphill step.

## GB8. The 2-hop centre hold (positive control)

- **Criteria.** At ring 1 the hold body (the centre sensor also emits on channel 1, and every steering sensor listens to
  it with w1 −1) beats the plain reflex by more than 2 paired SE, and its F is within 3 SE of the prototype's hold body;
  a lateral-off fork from birth removes at least 50% of the gain (the A4 rule). Rings 2-4 are reported.
- **Registered.** +0.440 at ring 1, about 0 beyond (proposal 5).
- **Measured.** Ring 1 (2048 lives): +1.4798 ± 0.0096 against +0.9962, gain +0.4836 ± 0.0106 (z 46; prototype gain
  +0.463; port z +1.3); with lateral off the gain is +0.0002 ± 0.0013 (100% removed). The gain grew from +0.470 at
  c_miss 1: the hold also saves misses (46.9 per life against the plain ring's 61.3). Rings 2, 3, 4 (512 lives): gains −0.001, +0.011, +0.008 (|z| ≤ 1.7; prototype −0.027,
  +0.010, −0.001).
- **Verdict.** PASS.
- **In plain words.** One circuit beyond the plain wire does pay, and the kernel sees it: when the target sits under the
  centre, silencing the ring-1 sensors stops them from dragging the body off it. It pays only at ring 1, where those
  sensors are the rim.

## GB9. The column reflex as a GRN genome (the G9 analogue)

- **The genome** (`handbuilt.column_genome`, a raw float32 875-slot ABI-3 genome run through `spec.V3.pack_genomes` in
  GRN mode from one zygote). Five active genes, seven with the growth window:
  - sense (target is_S) and motor (target is_M) set the phenotype from the plane cues: every z = 0 cell decodes the
    steering sensor, every z = 1 cell the motor.
  - mark (Q +1: 1 in every newborn, decaying) and kin (a latch of mark, inherited) single out the zygote: kin = 0 only
    in the first cell, which keeps the coincidence-detector gain (g_r 0.5, the 1/8 grid's nearest to the prototype's
    0.55) and, in the ring-1 genome, keeps dividing until its slots are full. Nothing local marks the site under the
    hotspot, so lineage does. A single founder gene with Q ≠ 0 does not work: the partition saturates it in every
    dividing mother.
  - fresh (Q +1, self-sustaining): every new sense cell divides exactly once, upward (zeta 2 beats every in-plane
    score), then stops. mark blocks a newborn's division until kin has latched.
  - with a window: a lineage timer (lambda 1/128, inherited) and a grow gene (on in sense cells while the timer is
    below the window) spread a disk of columns by flank placement.
  - The sense term of p_div outweighs every other term, so act cells never divide and no cell enters a hidden plane.
- **Criteria.** phenotypes: every settled gene state decodes exactly its program row; exact_growth: the ring-0 and
  ring-1 genomes grow exactly `ring_body(0)` and `ring_body(1)` in every life at L_max 4 and 2, without rejects or
  hidden cells, complete before t = 192; after_growth: from t = 192 (t_open) each grown ring is within 2 SE of its
  program twin (the same columns, centre g_r 0.5); grower: the windowed genome (window chosen on screen lives) is
  within 2 paired SE of program twins built on each life's own final columns, after growth.
- **Registered.** GB9: a hand GRN column grower within 2 SE of its program twin at its optimum; a single-mutant scan
  reported, including whether one mutation grows a whole ring.
- **Measured** (256 lives):
  - phenotypes: 8 states (sense fresh, sense, sense growing, zygote, motor, fresh motor, newborn sense, newborn act):
    no mismatch; p_div 1/2 exactly where a cell should divide, 0 elsewhere.
  - growth: ring 0 and ring 1 exact in 256 of 256 lives at L_max 4 and at L_max 2 (1 and 13 claims, no reject, no
    hidden cell; last birth by t = 23 and t = 80).
  - after growth: ring 0 +0.0409 ± 0.0072 vs twin +0.0404 (z +0.05); ring 1 +1.0088 ± 0.0261 vs +1.0103 (z −0.04).
    Whole life (with growth): ring 1 +0.955 vs +1.005 (z −1.6: 13 claims at c_div 0.5 and a smaller body for the
    first 50-80 units).
  - grower: window screen (48 lives) F +1.49, +2.20, +2.74, +3.16, **+3.24**, +3.06, +2.59, +1.62 at windows
    0.08-0.22; chosen 0.16. Fresh: 80.0 cells (40 + 40, no hidden), whole life +3.244 ± 0.036; after growth +3.484
    against its twins +3.515, paired −0.031 ± 0.042 (z −0.7); growth done by t = 122. The hand-built ring 3 earns
    +3.89 (at c_miss 2): the grown disks are ragged, not complete rings.
  - The ring-0 and ring-1 genomes differ in three entries (the zygote's starting fresh level, and the founder term of
    the p_div readout, a0 and A[p_div][kin]): one change of the division readout grows the whole ring 1 at once.
- **Verdict.** PASS.
- **Not done.** No single-mutant scan was run. The genome is representable in the layout evolution searches
  (`genome.LIFE_DIMS_ABI3`, no value bounds); whether mutation reaches it from random founders is GB10's question.
- **In plain words.** The column reflex can be written in the same gene language evolution searches: from one cell,
  the genes read only "am I touching the screen" and "am I in the act plane" plus their own lineage, and they grow
  exactly the hand-built 2-cell clicker or ring 1, or a disk of about 80 cells, and earn what the hand-built bodies of
  the same shape earn.

## GB12. Start robustness

- **Criteria.** v1_inside: at v1 every first step (lone → 2 → 4 → 6 → 8 → 14 → 74 cells) is uphill by more than 2
  paired SE and the clicker earns (F > 2 SE above 0); clicker_margin: the clicker earns at v_t 0.2 and R_cap 200 and
  does not at v_t 0.05 and R_cap 50, as in the prototype; port: every point of those four worlds within 3 SE of the
  prototype. c_live 0.04 and rho_c 0.7 are reported.
- **Registered.** Proposal 3.5 (c_miss 1): the clicker earns nothing at v_t 0.05 and R_cap 50; 2 → 4 flat at v_t 0.2,
  R_cap 50, c_live 0.04 and rho_c 0.7.
- **Measured** (2048 lives up to 14 cells, 512 at ring 3, all at c_miss 2; F of lone, 2, 4, 6, 8, 14, 74 cells):

| world | lone | 2 | 4 | 6 | 8 | ring 1 | ring 3 | clicker earns | flat or falling first steps |
|---|---|---|---|---|---|---|---|---|---|
| v1 | −0.020 | +0.024 | +0.071 | +0.203 | +0.291 | +0.996 | +3.89 | yes | none |
| v_t 0.05 | −0.020 | −0.055 | +0.030 | +0.228 | +0.335 | +1.328 | +4.22 | no | lone → 2 falls (z −24) |
| v_t 0.2 | −0.020 | +0.095 | +0.108 | +0.149 | +0.197 | +0.430 | +2.65 | yes | none (2 → 4 +0.013, z 3.2) |
| R_cap 50 | −0.020 | −0.034 | −0.029 | +0.013 | +0.032 | +0.287 | +1.09 | no | lone → 2 falls (z −12); 2 → 4 z 2.7 |
| R_cap 200 | −0.020 | +0.139 | +0.271 | +0.582 | +0.808 | +2.415 | +9.49 | yes | none |
| c_live 0.04 | −0.040 | −0.016 | −0.009 | +0.083 | +0.131 | +0.716 | +2.41 | no | 2 → 4 flat (z 2.0) |
| rho_c 0.7 | −0.020 | −0.025 | −0.011 | +0.050 | +0.084 | +0.416 | +2.73 | no | lone → 2 falls (z −2.8) |

  - Port (at the prototype's prices): the four gated worlds, 28 points, largest |z| 1.67; the two reported worlds,
    largest 2.48.
  - **The cost of c_miss 2.** v1 stays inside the good region (the clicker step is z 19), but closer to its edge: at
    c_miss 1 the clicker still earned at c_live 0.04 (+0.009) and the first step was faintly uphill at rho_c 0.7; now
    the first earners there are the 4- and 6-cell bodies.
- **Verdict.** PASS.
- **In plain words.** v1's settings sit inside the region where every first step pays, but not far inside it: with a
  target half as fast, half the reward, double the upkeep or a smaller capture radius, the 2-cell clicker earns
  nothing and the first earner is a bigger body.

## GB13. The cost of hidden planes

- **Criteria.** silent_hidden_exact: with 1 or 2 silent hidden cells on every column (rings 0-3), every life's F equals
  the plain body's minus c_live per hidden cell, to 1e-9; l2_equals_l4: the program rings 0-3 and the column genome's
  bodies (ring 1 and the window-0.16 disk) live bitwise alike at L_max 4 and L_max 2.
- **Registered.** GB13: the hand GRN column grower at L_max 4 and 2, cells per plane and F; proposal 4.1: each silent
  hidden cell costs exactly c_live.
- **Measured** (64 lives): residuals at most 8.4e-14 (ring 3 with two hidden planes: +2.453 against +3.933, i.e. 74 ×
  0.02 less); all six bodies bitwise equal at L_max 2 and 4 (GRN ring 1: 7 + 7 cells, the disk: 40 + 40, no hidden
  cell). Hidden cells stacked on columns add no column, so the drag tweak leaves them exact.
- **Verdict.** PASS.
- **In plain words.** A cell in a hidden plane that does nothing costs exactly its upkeep and changes nothing else; the
  hand-built genome never puts one there. What hidden planes cost an evolving population is for the L_max arms of the
  pilot to measure.

## Deviations and choices (BODY-1 gates)

1. **Lives per point.** The proposal measured 128-512 lives per point. These gates use 2048 (≤ 14 cells), 512
   (larger) and 256 (GB6, GB9) fresh lives. A smoke run of GB4-GB12 at 1024 / 256 lives, on the same fresh seeds and
   with the same criteria, failed GB5's port check at one point (adjacent, 12 cells, z 3.28; GB12's reported-only
   c_live 0.04 ring 3 was at 3.04) and passed every other check. I then raised the lives before the recorded run,
   for precision, without changing seeds or criteria; the recorded run keeps those first 1024 lives. Extra kernel lives
   on two other seed sets (GB3 note) show that the fresh set is a lucky draw for small bodies.
2. **Port checks** use a re-measured prototype reference (1024-4096 lives per point) and the kernel's F re-priced at
   the prototype's prices (c_rec 0, c_miss 1), at 3 SE per point. The remaining small-body offset (GB3 note) is
   reported, not explained. Bodies with footless act cells are not ported after the drag tweak.
3. **GB5** adds the ring 1 → ring 2 ladder to the three registered orders. **GB6** adds two grown GRN bodies, the
   receptor_off fork and the blind relay. **GB7** adds blind pressers (a screen and two GRN genomes) to the proposal's
   cheats, screens runners with 1-3 drifters, and judges each against the 4-cell column ("none above it",
   registered) and the 6-cell column (the proposal's "not a trap"). **GB12** turns "report where the clicker margin
   vanishes" into a pass rule (it vanishes exactly where the prototype's does) and reports c_live 0.04 and rho_c 0.7.
4. **GB9** compares the genome with an on-grid twin (centre g_r 0.5, since 0.55 is off the GRN grid) and after growth
   (t_open 192), because whole-life F includes growth costs a placed body never pays; whole-life values are reported.
   Its exact growth covers rings 0 and 1; larger bodies come from a growth window and are matched to twins of their
   own shapes. No single-mutant scan.
5. **GB13** checks the cost of silent hidden cells exactly instead of re-measuring the proposal's table, and checks
   L_max 2 = 4 bitwise; the founder-loss part of the proposal's hidden-plane question is GB10's.
6. **Two world tweaks came from the gates' review** (LIFE_ABI.md 15.59, 15.60): c_miss 2 and the projected-footprint
   drag. Both keep the column ladder (complete columns live bitwise as before; F moves by −misses / T). BELL-1 is
   untouched.
