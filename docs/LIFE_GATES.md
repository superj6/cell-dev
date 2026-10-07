# One-life gates G1-G10 (migration step 3)

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
| G9 | R25-v1 as a GRN genome within 2 SE of the program at 91 | GRN +0.698 ± 0.030 vs program +0.697 ± 0.033, z +0.04 (n 288) | PASS |
| G10 | D4 and D5 re-measured; GRN layer | D5 holds (z 8.9); flank gate beats the n_view gate (z 2.9); placement term +0.057 ± 0.037 (z 1.5) | **FAIL** |
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
| default | +0.69 ± 0.10 | −0.25 ± 0.22 | −2.45 ± 0.28 | −5.41 ± 0.28 | −8.40 ± 0.29 | 91 |
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
  - The GRN genome: 32.6e-3 → 1.36e-3 (4.2%).
- **Verdict.** PASS.
- **In plain words.** If the cells stop hearing each other halfway through life, the pumping stops almost at once,
  so the beat is held together by messages on every beat.

## G7. Income per cell never exceeds the lone-cell rate

- **Criteria.**
  - lives_below_lone: every body life (cap > 1) measured by any gate earns at most the largest income per cell-unit
    of any lone life on G1's fresh lives (54.0e-3);
  - means_below_lone: every point's mean is at most the best lone phenotype's mean rate (53.8e-3).
- **Scope.** All bodies of G2-G6, G9, G10 and S8, plus the bursting body B at 37, 91 and 169 cells, including G6's
  [T/2, T] windows: 215 points, 31,392 lives.
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
- **The genome** (`handbuilt.r25_genome`, a raw float32 809-slot genome, run through `spec.pack_genomes` in GRN
  mode). Five active genes:
  - contact (λ 1/2): on when n_view ≥ 1. Its partition is Q −1, so a daughter starts alone.
  - juvenile (λ 1/16, Q +1): a daughter starts at 1, and the gene silences emission for exactly her first 10 own
    ticks.
  - flank gate (λ 1/2, Q −1): on when flank_best = 2. It switches p_div between 1/2 and 1/16.
  - contact echo (λ 1/2): a one-tick-delayed copy of the contact gene. The readout uses 2·contact − echo, which
    makes the switch from alone to contact exact at the first tick that sees a contact.
  - division reset (λ 1/2, Q −1): cancels the gate gene's forced opening in a mother after a claim.
- **Registered.** Within 2 SE over 36 lives at cap 91.
- **Measured** (288 fresh lives, the same lives as G3):

| N | program | GRN genome | z | paired ΔF |
|---|---|---|---|---|
| 37 | +0.566 ± 0.008 | +0.563 ± 0.008 | −0.22 | −0.003 ± 0.008 |
| 91 | +0.697 ± 0.033 | +0.698 ± 0.030 | +0.04 | +0.002 ± 0.029 |
| 169 | −0.220 ± 0.088 | −0.174 ± 0.083 | +0.37 | +0.045 ± 0.072 |

- **Every settled state** (alone, juvenile or adult with the gate open or closed, first contact tick, a mother just
  after a claim) decodes exactly the program row.
- **The design's minimal 3-gene sketch** (no echo, no reset) scores +0.668 ± 0.054 at 91 (144 lives; z −0.59
  against the program).
- **Verdict.** PASS.
- **In plain words.** The hand-built heart can be written in the same gene language evolution searches, and it
  scores the same. So the target is reachable in principle.

## G10. D4 (flank placement and gate), D5 (refined t_ref grid), and the GRN layer

- **Criteria.**
  - d4_layered: R25-v1's layered growth (flank placement plus the flank-best rate gate) beats placement only, gate
    only and neither by more than 2 paired SE in F* (program mode).
  - d4_flank_gate: in GRN mode, the flank-best gate with flank placement beats the registered alternative by more
    than 2 paired SE. The alternative is an n_view ≥ 5 gate with random placement, the prototype's dir 4.
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
    - flank gate: +0.753 ± 0.040 (n* 91);
    - n_view gate with random placement: +0.638 ± 0.029, 15% weaker, ΔF +0.115 ± 0.040, z 2.9;
    - n_view gate with flank placement: +0.754 ± 0.042, ΔF −0.001 ± 0.013.
  - **D5:**
    - The screen (96 coupled rows at 91 cells) picks C1 (b 1.125, τ 1, t_ref 2, w0 −0.75) as the best old-grid
      phenotype, the same one the design registered, and R25-v1 itself as the best refined one.
    - C1 scores +0.481 ± 0.026 (n* 61), against R25-v1's +0.713: ΔF +0.233 ± 0.026, z 8.9.
    - t_ref sweep of R25-v1 at 91 cells: −1.74, −1.77, −1.79, +0.05, **+0.71**, −0.34, −0.36 and −1.63 for t_ref
      0.5 to 4.
  - **GRN layer:** the lone GRN cell is bitwise the program cell; G9's z are −0.22, +0.04 and +0.37.
- **Verdict.** **FAIL**, on d4_layered only:
  - The rate gate is what matters: without it the body loses +0.24 (z 7.1).
  - The flank term in placement adds only +0.057 ± 0.037, which 144 lives do not resolve.
  - The registered n_view comparison holds (15% weaker, z 2.9), but only because it also removes flank placement.
    With flank placement kept, the n_view ≥ 5 gate is exactly as good as the flank-best gate. So the 19th GRN input
    (flank_best / 2) is not needed for layered growth when n_view is available.
  - D5 holds strongly: t_ref 2.5 is a sharp optimum, and the refinement of the grid is needed.
- **In plain words.** Refining the refractory-time grid was right. Of the two parts of "layered growth", slowing
  division at the rim matters a lot. Choosing the most enclosed empty spot adds a little that I could not confirm,
  and the special "flank" input to the genes could be replaced by the plain neighbour count.

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
- **The GRN genome** (D = 8) at 121: +1.109 ± 0.068, z −0.45 against the program.
- **Verdict.** PASS.
- **In plain words.** On the square grid with diagonal contacts, the same heart grows bigger (about 121 cells) and
  earns about 60% more than on hex. The hex settings work there as they are.

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
   - The sketch itself is reported (+0.668 ± 0.054 at 91, within 2 SE).
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
