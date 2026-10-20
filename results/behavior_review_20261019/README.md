# Behaviour review of the multitask run (2026-10-19)

A read-only analysis of the generation 0 and 250 reporting genomes from `results/multitask_20261018/`
(`selected_genomes.json`). It asks what behaviours changed, where the gains come from, and whether there is evidence
that more sophistication could arise.

## Contents
- **`scripts/`:** the analysis code, written against the repo at `b19a526`.
  - **Raw traces:** `traces.py` recorded 480 fully logged reference lives (8 genomes × 8 training tasks, paired seeds),
    each checked bitwise against the kernel's F. Raw traces stay under `outputs/behavior_20261019/traces/`.
  - **`analyze.py`:**
    - pursuit metrics;
    - dark-flash steering by time since the flash ended;
    - patch visits and planted-food harvests;
    - cue decoding in delayed matching.
  - **`lesions.py`:** kernel forks from t=200 (growth ends by about t=25–60), scored over [200, 1024] on 128 paired
    lives. The four forks switch off sideways messages, hidden cells, the genes' view of activity, or gene updates
    (`lateral_off`, `hidden_off`, `genes_blind`, `freeze`).
  - **`mutants.py`:** 192 ordinary mutants of each generation-250 genome, screened on 32 lives of dark flash and of
    matching. The top 4 per task were confirmed on 256 fresh paired lives.
- **`report_*.json`, `lesions_summary.json`, `mutants.json`, `matching_trials.json`:** the results.

**Seeds:** `spec.hash64(45_919_000, 7, offset, i)`. The mutant generator uses torch seed 45919.

## Findings

**Tap gating.** Taps made far from the target fell by 50–65%, and food per tap rose: AO 0.22 → 0.35, s8 0.19 → 0.36,
D90 0.30 → 0.38.

**Steering.**
- AO, s6 and s8 halved their strokes and slowed down, keeping or improving aim (s8's stroke alignment with the target
  went from 0.13 to 0.33).
- D90 instead became a faster, more active pursuer.

**Patches.**
- Time at patches rose (s6 0.09 → 0.32, s8 0.24 → 0.36).
- Departures happen more often once the patch is empty (s6 0.50 → 0.82, D90 0.60 → 0.75).

**Tap-grown food.**
- Bodies tap empty patches more (3.0–3.6 → 5.0–5.6 plantings per life) and are more often present when the planted
  food matures (AO 0.06 → 0.26).
- The same habit appears in the plain patch world, so this is lingering and tapping, not planning.

**Harmful decoy.**
- No lineage aims at the good target rather than the harmful one: stroke alignment with the good target is about 0.
- Fewer harmful taps come from tapping less overall.
- D90 is the exception. Its good-food catches doubled, and switching off sideways messages now costs it −0.95 catches,
  where in its ancestor it helped (+0.74). The interaction is −1.70 ± 0.27.

**Dark flash.**
- Aim at the last-seen target position fades to 0 within 5–10 time units after the flash, in all eight genomes.
- Most dark-phase catches happen within 5 units of the flash.
- The best single mutants raise dark-phase catches by 0.3–1.2 per life, by moving and tapping more. Only AO's mutant
  104 (a gene-rate change) is net-positive (+0.22 F).

**Hidden cells.** Switching them off has no effect anywhere. AO has none, and the hidden cells of s6 and s8 never fire.

**The gene layer runs behaviour in real time.**
- Blinding the genes to activity costs 8–12 catches in POOL and patches.
- AO came to rely heavily on ongoing gene updates: freezing them costs it 9.8 catches in POOL at generation 250,
  against 3.0 at generation 0.

**Matching.**
- The cue can be decoded from tissue activity during the sample at 0.73–0.98 accuracy and early in the blank at
  0.66–0.82.
- Late in the blank it is at chance for AO and s6, and about 0.60–0.63 for D90 and s8.
- D90 at generation 250 carries the cue into its choice with the wrong sign: P(choose broad | broad sample) minus
  P(choose broad | narrow sample) = −0.072. This shift vanishes when gene updates are frozen or sideways messages are
  switched off.
- Mutant 178 (A[5,1] −0.61) flips the shift to +0.028, at a cost of fewer completed trials.
- No single mutation improves matching in AO, s6 or s8 (all within ±0.005).

The design that follows from this review is in [docs/OPEN_WORLDS.md](../../docs/OPEN_WORLDS.md).
