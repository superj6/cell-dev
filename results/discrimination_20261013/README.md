# Discrimination: the fixed recovered controller measurement

Seven fixed candidates share 512 fresh T1024 lives in the existing harmful-decoy world,
using old conduction d0=1 and d_min=0.5. All seven candidates and negative results are retained.

| Comparison | Paired ΔF ± SE |
|---|---:|
| Full − selected whole reflex (retuned) | +11.753571 ± 0.169693 |
| Full − frozen reflex | +12.083609 ± 0.172756 |
| Full − retuned reflex | +11.753571 ± 0.169693 |
| Full − matched ablation | +9.902062 ± 0.194431 |

The unchanged descriptive plan-0.4 checks give **pass**:

- information gap: passes.
- specific part: passes.
- do less: passes.

The best of three fixed do-less variants is `smaller_frozen`: +0.966488 ± 0.107490 F versus the selected reflex.

All differences are formed within a shared seed before SE is estimated over 512 pairs.
Reference selection uses each candidate's whole mean; it never picks a different reflex per life.

| Candidate | Mean F ± SE | Captures | Poison clicks |
|---|---:|---:|---:|
| frozen | 0.532342 ± 0.091121 | 9.039 | 40.588 |
| retuned | 0.862380 ± 0.085562 | 9.098 | 35.209 |
| smaller_frozen | 1.828869 ± 0.085330 | 9.539 | 32.072 |
| smaller_transferred | 1.718413 ± 0.076831 | 8.584 | 24.023 |
| quieter | 0.257400 ± 0.071818 | 6.486 | 26.307 |
| full | 12.615951 ± 0.157197 | 30.443 | 6.830 |
| ablated | 2.713889 ± 0.147491 | 17.020 | 64.420 |

All 3,584 candidate-lives completed in 496.441665 monitored CPU-seconds,
within the fixed 1,800-second cap with two workers. No candidate or sample-size extension followed
results.

The independent audit reconstructs every F from all 57 ledger columns, checks byte-exact raw-score
JSON roundtrips, candidate/library/source receipts, all 12 saved callback replays and generated C
source. `rows/` preserves full ledgers, diagnostics, latency and timing. `operations/` preserves the
actual compiled library, generated C, runner, release, manifest and budget. `original/` preserves
the pinned source inputs.
`prelaunch/` preserves the complete original preparation archive and its offline validator. The
preparation's zero-hash wording is corrected in [ERRATA.md](ERRATA.md); frozen bytes are unchanged.

Recompute without simulation or compilation (Python + NumPy; Matplotlib only for `--plot`):

```bash
python analyze.py --study . --check
```

Interpretation limits:

- The unchanged recovered controller is an external measuring tool, never an organism policy.
- Model 1 versus 0 removes broad decoy belief, ping attribution, steering avoidance and tap veto; the effect does not isolate one classifier or tap mechanism.
- Controller parameters were transferred from ring5 to hollow3 without fresh tuning; a failure does not establish that the information is useless.
- The better whole reflex and best do-less candidate are chosen on these outcomes. Their paired SEs are conditional and descriptive, without selection adjustment; both fixed-reflex comparisons are reported.
- Only three fixed do-less candidates were measured, not an exhaustive optimum.
- All cells, receptor pings, virtual relay spikes and actions pay; central controller computation is free.
- This study uses old conduction d0=1, d_min=0.5 and T1024; it supplies no duration-transfer evidence.
- Existing replay/parity evidence covers bounded T64 lives, not universal long-duration parity.
- Fast event hashes retain HASH_INIT (0x243f6a8885a308d3) and are not replay evidence; file hashes protect stored bytes. The preparation's claim of zero hashes is corrected in ERRATA.md without changing its pins.
- A passing descriptive measurement never automatically admits the world into selection.
