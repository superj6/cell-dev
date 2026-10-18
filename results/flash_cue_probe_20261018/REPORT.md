# Flash cue dependence after 120 generations

Three lineages show an increased acquisition benefit from target cues, beyond the improvement that survives
when target cues are absent. AO's added cue benefit is unresolved. All four also improve acquisition in the
signal-off world, so the observed adaptation contains both cue-dependent and cue-independent contributions.

This diagnostic fixes the previously selected `dark_specialist` genomes at g0 and g120 in each lineage.
It reuses their 512 zero-residual-brightness confirmation cases and adds the same seeds with only `lam_s=0`.
The normal world still presents a five-unit flash after each ordinary target placement. No endpoint was
reselected. The shared panel was already revealed; this is an interpretation follow-up, not fresh confirmation.

| Lineage | Normal capture gain | Signal-off capture gain | Added cue benefit: captures | Added cue benefit: low-light captures |
|---|---:|---:|---:|---:|
| AO_s7 | +0.455 ±0.080 | +0.438 ±0.040 | +0.018 ±0.088 | -0.051 ±0.086 |
| D90_Z_s5 | +1.227 ±0.081 | +0.215 ±0.035 | +1.012 ±0.090 | +0.939 ±0.088 |
| speck_s6 | +0.508 ±0.060 | +0.205 ±0.036 | +0.303 ±0.070 | +0.227 ±0.068 |
| speck_s8 | +1.059 ±0.068 | +0.482 ±0.041 | +0.576 ±0.080 | +0.551 ±0.080 |

Values are whole-life means ± paired SE over 512 shared seeds. “Added cue benefit” is the per-seed four-way
interaction `(g120 normal−g120 off)−(g0 normal−g0 off)`. D90, s6 and s8 exceed three SE for both acquisition
interactions; AO does not. These are descriptive contrasts across four fixed lineages, not a new selection gate.
All four have positive capture gains without target signal exceeding three SE. This rules out attributing the
entire gain to improved cue use, but also rules out explaining the three resolved cue interactions solely by
performance in the blind condition.

Both initial and final genomes in every lineage benefit from normal target cues. Final normal-minus-off capture
benefits are AO 1.592 ±0.076, D90 2.041 ±0.080, s6 0.836 ±0.058 and s8 1.111 ±0.070. The change in that benefit is the
interaction above, not the final cue effect alone. All lineages click and miss more after training in both
conditions, with smaller mean bodies and lower total costs. All final mean ordinary F values on this zero-light
rung remain negative. Full means/SE, F, costs, clicks, misses and body sizes are in `summary.json`.

Removing the cue changes total receptor activity and can change development, motion, and subsequent target
replacements. It does not isolate spatial decoding from cue-triggered clicking or mature circuitry from altered
development. Background rate stays 0.05, but the candidate bound falls from 2.05 to 0.05, so the two conditions do
not share identical background events. Counter-keyed streams avoid shifting a single global random sequence.
Low-light capture labels follow each trajectory's own placements. No neural-memory mechanism is established.

All four jobs completed on their first attempt: **4096 new native lives**, plus 4096 reused normal rows.
Execution used **434.720257 CPU /64.862628 wall seconds**, peak 1,077,293,056 owned RSS bytes, within the
1800 CPU/900 wall, four × two-thread, 8 GiB RSS and 4 GiB host-reserve limits. Every owned job exited 0 and cleared.
The independent saved-array audit checks all 16 raw-file hashes, 8192 counted ledgers, native costs/net/F,
zero statuses, fixed genotype/world/seed bindings and every reported moment. Fast-C hashes remain constant;
there is no full-trajectory hash claim.

The first saved-reader check used an unnecessarily strict net reconciliation tolerance and stopped on
2.75e−10 floating-point accumulation differences. Its source/logs are retained in `audit_attempt1/`; only
that comparison was changed to the established 1e−9 tolerance. No lives or scientific inputs were repeated or
changed. Audit CPU totals 6.41 seconds; preparation used 3.31 seconds, separately recorded. Production source
is pinned at `54c531026528b824bae7d670c3092ffe7abc9d39`. This diagnostic changes no frozen endpoint or original flash-study result.
