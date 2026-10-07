# Does the n_view gate replace the flank_best gene input on square8? (2026-10-07)

ABI 2 removed the gene network's flank_best input. The evidence was gate G10, measured on hex only. There, R25-v1's
GRN genome gated on n_view ≥ 5 scored as well as the same genome gated on flank_best (F* +0.754 vs +0.753). This
folder holds the same paired comparison on square8 (D = 8, n_view ≥ 7), which is now a full pilot arm. The comparison
was asked for by a review. `sq8_pair.py` ran once in the ABI-1 tree (`git archive f2142c8`, gate `flank`) and once
in the ABI-2 tree. `pair.npz` holds the per-life F of both runs. The program's lives at 81 cells are bitwise equal in
both trees, so the two genomes saw the same lives.

| lattice, cells | flank_best gate (ABI 1) | n_view gate (ABI 2) | paired difference | z | lives |
|---|---|---|---|---|---|
| square8, 49 | +0.791 ± 0.008 | +0.777 ± 0.010 | −0.013 ± 0.010 | −1.3 | 288 |
| square8, 81 | +1.056 ± 0.020 | +1.006 ± 0.021 | −0.051 ± 0.020 | −2.5 | 288 |
| square8, 121 | +1.096 ± 0.044 | +1.015 ± 0.046 | −0.081 ± 0.052 | −1.6 | 288 |
| square8, 169 | +0.893 ± 0.072 | +0.727 ± 0.071 | −0.165 ± 0.065 | −2.5 | 288 |
| hex, 61 / 91 / 127 | | | +0.002 / +0.001 / −0.004 | +0.8 / +0.1 / −0.3 | 144 |

- On square8, F* (both at 121 cells) drops from +1.096 to +1.015, which is 7% lower. The n_view genome is lower at
  every size, by 2.5 SE at 81 and at 169 cells. On hex the two gates are equal, as G10 found.
- No n_view threshold closes the gap. Gates at n_view ≥ 5, 6 and 7 on 144 lives, against the flank_best gate at
  81, 121 and 169 cells: ≥ 5: −0.021, −0.121, −0.467; ≥ 6: −0.072, −0.159, −0.125; ≥ 7: −0.071, −0.131, −0.227
  (SE 0.03-0.13).
- A likely reason (not tested): square8 has 8 contact slots in a ring, so an empty slot can have 2 live flanks while
  2 or more other slots are empty too. The flank_best gate opens there and the n_view ≥ 7 gate does not. A lower
  n_view threshold also opens in layouts where no empty slot has 2 live flanks.
- This is a hand-built genome. Evolution may find other gates. The pilot evolves without the input on both lattices
  unless the user decides otherwise.

Pinned by `tests/test_life_gates.py::test_square8_n_view_gate_against_the_abi1_flank_gate` (slow). It re-measures the
ABI-2 side at 81 cells bitwise and recomputes the table from `pair.npz`.
