### I. A fixed nearby-mutant panel in the decoy world (2026-10-14)

- Question: does the existing decoy world offer useful nearby steps from original evolved s5 and s7? F measured
  that its sense information can pay. This separate diagnostic tests ordinary organism mutations, with no
  controller behavior entering the tissue and no automatic world-admission or selection change.
- Use the complete original tables from `results/pool_mutants_20261013/genomes/s{5,7}_pool.npy`: each original
  parent plus its 64 ordinary point mutants. Preserve exact float32 bytes, row order, generation manifests and
  mutation logs. No new mutants, hand-selected alleles, or filtering by prior base/POOL outcomes.
- World exactly matches F: existing ABI3 discrimination, T1024, d0=1, d_min=0.5, b2_amp=1, b2_sigma=1.2,
  b2_value=-50, b2_p=1, b2_mode=1, with every price unchanged. This uses the original slower conduction, not
  fast POOL; comparisons with earlier-world outcomes are not controlled world-only contrasts.
- Both parent panels share 32 block95 seeds for screening. Per panel, select exactly four mutant rows by mean
  production F; exact ties use ascending original row index. The parent is a reference, not a shortlisted mutant.
- Re-score those four mutants and their parent on 512 block96 seeds. Freeze the highest-mean mutant from each
  panel, breaking exact ties by original row, before confirming either winner. Keep a winner even if worse than
  the parent. Confirm both winners and both parents on 512 block97 seeds, with no extra candidates or extensions.
- Counts: screen 130×32=4,160; rescore 10×512=5,120; confirmation 4×512=2,048; **11,328 scientific genome-lives**.
  Blocks95/96/97 are disjoint, share lives within each stage, and do not overlap the original panel's evaluations
  or F. E1 startup full/fast golden replay is separate validation, included in the overall CPU cap.
- Primary: each winner minus its original parent on fresh confirmation, paired per seed before mean/SE.
  Report raw effects and descriptive >3-SE and ≥0.5-F flags, both signs, screen beneficial fractions, rescore
  results, captures, clicks, poison clicks, end and hidden-cell counts. No claim of multiplicity-adjusted discovery.
- Decompose paired F into capture income, poison-cost saving, miss-cost saving, other cost saving, guard and
  extinction charges. Require the pieces to reconstruct fitness. Shape or reduced clicking alone does not
  establish discrimination or a new algorithm; the fixed 64-mutant panels do not estimate general evolvability.
- All rows retain production guard/extinction penalties. Capacity failures, ledger mismatches, unexplained
  incomplete lives, source/numerical drift or corrupted caches make the study incomplete rather than dropping
  selected lives. Hash and save each completed row; freeze both selected genotypes before fresh confirmation.
- One shared cap of **3,600 CPU-seconds**, at most two simulation workers on CPUs0–11. The external monitor
  stops before the cap and preserves partial evidence. No automatic retry/reset or score-based budget extension.
  Wait until G is complete with no active or queued jobs, then run alongside H's two workers if it is still active.
  I does not depend on H's result. Require a root-created `ready.json` after protocol review/commit.
- No organism rule, ABI, price, hand-designed behavior, rented compute, population-responsive world or default
  world changes. This is a bounded diagnostic, not the full all-world G2 gradient study.
