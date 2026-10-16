# Candidate fixed-genome transfer check

This is one future option, not a registered study or a recommendation to interrupt AO. It uses completed evidence through AN only. AO outcomes were not inspected. The question is whether an acquired improvement survives nearby changes while the *same unchanged genome* retains its older tasks.

AN improved captures in 80/20 renewal darkness and an untrained faster-turn combination, but its later endpoint lost POOL captures. Almost all acquisition was in bright periods; dark-capture gains and the interaction against steady visibility remained unresolved. All five AN/AO contexts are now development-known. See the [completed AN report](../../../results/occlusion_acquisition_20261015/REPORT.md).

## Four unused combinations

Start from AN's exact `blink80_20` world in its [protocol](../../../results/occlusion_acquisition_20261015/protocol.json): target speed 0.3, mean turn interval 200, exponential bright/dark means 80/20, dark target-rate multiplier zero. Keep every other field, original prices, T=1024, and local rules unchanged. The table gives the complete differences from that baseline; these are means, not periodic schedules.

| Candidate | Changed fields | What it tests / scope |
|---|---|---|
| Intermediate motion and occlusion | `tau_turn=150`, `visibility_off=10` | Parameter interpolation between the known turn intervals 100/200 and dark means 5/20, in an unused combination. This is the mildest transfer case. |
| Faster switching at equal long-run visibility | `visibility_on=40`, `visibility_off=10` | Half the renewal timescale, with the same stationary dark fraction (20%) as 80/20. This separates sensitivity to temporal scale from average cue availability. Finite lives start bright, so realized dark time is not held exactly equal. |
| Faster moving target during occlusion | `v_t=0.35` | A modest speed extrapolation beyond this lineage's 0.3 development setting; tests whether its acquisition survives changed motion rather than just new blink timings. |
| Longer unavailable cues | `visibility_off=40` | A stronger occlusion extrapolation beyond this lineage's dark mean 20. It also reduces average cue availability, so it does not isolate memory duration. |

“Unused” means no matching combination in the reviewed completed public records: 190 protocol paths, 41 distinct payloads, and 73 embedded world dictionaries after excluding AO and synthetic fixture directories; zero parse errors. The older [headroom memory cases](../../../results/open_headroom/data/memory.json) include 20/10, 20/20, 10/30, 5/5 and flash cases, but not these combinations. A targeted archived source/config search found only a synthetic rejection test mentioning `visibility_off=40`. This is recorded-exposure evidence, not a claim about unrecorded scratch work; recheck additions before any eventual registration.

## Fixed endpoints and inherited anchors

A small concrete version uses two already fixed endpoints: [AM's original-price winner](../../../results/occlusion_acquisition_20261015/inputs/AM_current_start.json) and [AN's generation-eight rank-zero genome](../../../results/occlusion_acquisition_20261015/runs/acquisition/best_genome.json). Both were chosen before these candidate outcomes exist. Do not substitute generation four, tune a genotype, or choose a different world after viewing transfer results.

Retain exact POOL and persistent old-task anchors plus the trained 80/20 anchor. Four new conditions plus three anchors, two fixed genomes and 256 fresh paired lives would be 3,584 research lives, before ordinary startup checks; this is a sizing illustration, not an allocation or release. Use one fixed sample size, retain all outcomes, and report each context separately. New conditions must stay outside evolutionary selection if they are to test transfer.

Lead with paired capture changes, absolute captures and old-task retention. Show original F, capture income, living/movement/communication/miss costs, clicks, aggregate capture accuracy, body sizes, and bright/dark captures alongside them. An F gain alone can be economy. Positive effects in selected cases cannot hide losses elsewhere; any multiple-condition success rule must be fixed before execution.

## What this would not establish

The implemented [world parameters](../../../src/life/spec.py) and [visibility events](../../../src/life/kernel.c) supply all required dynamics, without a new ABI or a global input to cells. Darkness removes target-driven receptor rate, not background events, motion, turns or target replacement. Inertia, holding direction and clicking can still pay; dark capture alone does not prove memory.

This suite tests nearby unseen parameters. A different information demand—such as existing per-placement flashes or decoy discrimination—is a separate option, not another blink setting. Repeatedly varying blink timings cannot establish broad generalization or a richer algorithm. Even a clean result here would show limited transfer of two fixed genomes, not reliable evolution across seeds, a causal circuit mechanism, or cumulative retention indefinitely.
