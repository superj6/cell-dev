# Nearby organism mutations in the existing decoy world

The unchanged original s5/s7 panels each contain their parent and all 64 ordinary mutants. The world
matches F exactly: existing ABI3 harmful decoy, T1024, old conduction and unchanged prices.

| Parent | Frozen mutant row | Fresh paired ΔF ± SE | Descriptive 3-SE direction | ≥0.5 F |
|---|---:|---:|---|---|
| s5 | 32 | +1.431097 ± 0.095965 | positive | yes |
| s7 | 1 | +1.178231 ± 0.102315 | positive | yes |

Screening used 32 shared block95 lives. Exactly four mutant rows per parent were rescored on
512 fresh block96 lives; both winning genotypes were frozen before either block97 confirmation.
All signs are retained. Each primary estimate uses 512 paired differences, preserving covariance.

| Parent | Initial positive-mean fraction | Initial >3-SE fraction | Top four original rows |
|---|---:|---:|---|
| s5 | 0.6875 | 0.0312 | [32, 10, 27, 41] |
| s7 | 0.3125 | 0.0156 | [1, 40, 12, 53] |

Fresh absolute fitness and changes in captures/body size:

| Parent | Parent F | Winner F | Δ captures ± SE | Δ terminal cells ± SE |
|---|---:|---:|---:|---:|
| s5 | -1.671160 | -0.240063 | +0.734375 ± 0.184188 | -38.525391 ± 0.541851 |
| s7 | -0.719958 | +0.458273 | +0.941406 ± 0.189953 | -22.660156 ± 0.343045 |

Mean contributions to the same paired fitness gain:

| Parent | Capture income | Poison-cost saving | Miss-cost saving | Other-cost saving |
|---|---:|---:|---:|---:|
| s5 | +0.358582 | +0.015926 | +0.067005 | +0.989584 |
| s7 | +0.459671 | +0.157928 | +0.046253 | +0.514379 |

The full accounting, including guard/extinction terms and per-component paired SEs, is in
`summary.json`. Body size and ordinary costs matter when interpreting a positive gain; these
nearby improvements do not by themselves identify a discrimination mechanism.

All 11,328 research genome-lives completed in 3105.780628 monitored CPU-seconds (cap3,600).
Two existing T200 startup golden lives are separate validation within that CPU cap.

Every one of 144 raw checkpoints is preserved, including all 130 initial rows, full ledgers and
production-scored columns. `summary.json` records all rescores, confirmation accounting and health.
`inputs/` preserves original genomes/mutation logs, `operations/` preserves release/resource records,
and `prelaunch/` preserves the full original preparation archive without changing frozen bytes.

Recompute without simulation or compilation (Python + NumPy; Matplotlib only for `--plot`):

```bash
python analyze.py --study . --check
```

Interpretation limits:

- All 64 preexisting mutants per parent are included, without filtering on their earlier-world scores.
- The screen and rescore are selection-biased; fresh confirmation supplies the primary fixed-winner evidence.
- Both selected winners are retained even if worse than the parent. No extra candidates or life extensions occur.
- Two backgrounds and a fixed 64-mutant panel per background do not estimate general evolvability.
- Positive nearby gains do not establish a discrimination circuit, local algorithm or long-term accumulation.
- The world uses old conduction, while earlier base/POOL diagnostics used fast conduction; between-study comparisons are not controlled world-only contrasts.
- The controller that motivated this world never enters the organism. No admission or selection change follows.
- Guards and extinction retain production penalties; invalid capacity/accounting failures block inference.
- Three-SE and >=0.5-F flags, beneficial fractions and selected references are descriptive, not multiplicity-adjusted discovery claims.
