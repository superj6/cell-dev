# Open-world pilot v2 (2026-10-20 to 2026-10-23)

**Design.** Five eco worlds (plume, predator, home, prey, farm) trained together from generation 0 on ABI 8 with
the eco v2 rules ([docs/OPEN_WORLDS.md](../../docs/OPEN_WORLDS.md) §11).
- **Founders:** the D90 and AO multitask populations and archives, padded to ABI 8, so they start blind to the
  nine new senses.
- **Arms:** U (uniform lives per world), LP (learning-progress allocation) and LPD (LP plus gene duplication), plus
  one from-scratch population in arm LP.
- **Runs:** 100 generations each; 7 runs, 439 CPU-hours on the laptop.

The study directory is `outputs/open_worlds_pilot_v2/` (frozen checkout 0dd707e).

**Measurements.** All on fresh paired lives (seeds 8_300_000+ and 8_400_000+, never used in training); scripts are in
`scripts/`.
- Each run's top 8 genomes at generations 0, 25, 50, 75 and 100.
- Standout behaviour-grid genomes, re-tested on 24 lives each.
- Lesions that switch off all, or one, of the new senses.
- Full cell-level traces of four bodies (`probe.trace` on eco lives, checked bitwise against the kernel).

## Results

**1. Every world improved, and the gains carry over to held-out variants** (top 8 at generation 100 against
founders, F per life ± paired SE, 24 lives):

| Run | Plume | Predator | Home | Prey | Farm |
|---|---|---|---|---|---|
| D90 U, trained | +2.48 ± 0.78 | +2.17 ± 1.18 | +3.36 ± 0.52 | +1.97 ± 0.33 | +1.17 ± 0.23 |
| D90 U, held-out | +1.13 ± 0.90 | +2.24 ± 0.81 | +2.25 ± 0.71 | +1.64 ± 0.31 | +1.03 ± 0.12 |
| AO U, trained | +1.95 ± 0.67 | +2.44 ± 1.10 | +1.87 ± 0.46 | +1.06 ± 0.22 | +0.50 ± 0.25 |
| AO U, held-out | +0.27 ± 0.56 | +1.30 ± 0.57 | +2.29 ± 0.63 | +0.70 ± 0.24 | +0.70 ± 0.12 |

**2. The new senses carry the gain.** Switching them off costs more than the whole gain in several worlds (D90 U:
predator 3.8 ± 1.1, home 4.1 ± 0.6). The main tool is a smell discriminator:
- odour B (rich food) excites the receiving cell, while toxin and danger odours inhibit it;
- that one trick is reused in four worlds;
- toxins eaten in plume fell from about 2 to about 0.5 per life.

**3. Most of the progress came in the first 25–30 generations.** After that the fixed-seed probe scores were flat.

**4. Specialists appeared in the behaviour grids but did not spread** (generation 50 and 75 checks):
- **Upstream swimming** (up to 92 units per life), driven by the flow sense.
- **Hiding in shelter** (41% of the life), driven by touch.
- **Profitable farming** (+0.6 to +0.7 F; one life with 14 plantings, 12 harvests and +4.0 F).

The final populations stay generalist foragers that swim downstream (−2 to −4.5 units upstream per life), barely
shelter, deliver 0.1–0.2 items home per life and mostly do not farm. Only AO LP plants: 6 times and 1.3 harvests per
life.

**5. LP allocation did not help measurably.**
- Probe means were the same in both lineages (2.19 against 2.22; 1.91 against 1.92).
- On fresh lives, D90 showed no resolved difference.
- AO LP gained farm (+0.62 ± 0.23) and lost home (−0.78 ± 0.35; held-out −1.52 ± 0.39).
- LP filled more grid cells (70–75 against 61–67).

LPD ended where LP did.

**6. Bodies halved in size** (D90 65 → 25–32 cells, AO 48 → 25–32), and hidden cells are unused.

**7. The from-scratch population stayed single cells for about 55 generations.** It was multicellular (about 10
cells) by generation 99 and earned a little in plume and prey.

## Circuits (four traced lives)

- **Upstream swimmer (25 cells).**
  - Only the sensing cells facing the current receive flow (about 1,000 events each against about 50 on the far
    side).
  - Each sensing cell excites the movement cell above it, which inhibits it back (a pulsed column).
  - The movement cells under the current-facing edge twitch most, so the body is pulled into the current: in 94% of
    32-unit windows it moved toward the side that felt the current.
- **Farmer (27 cells).** Its tap cell is excited by the central sensing cell (+0.97) and inhibited by every
  surrounding movement cell (−0.2 to −0.44). It taps only when nearly still, which gives 0 wasted taps. In the
  generalist the same links are excitatory (+0.2): 131 misses against 7 meals in its traced life.
- **Shelter-hider (28 cells).** Touch fires constantly inside cover. Strong mutual inhibition among its movement cells
  damps its movement while touch is active.
- **All four bodies:**
  - genes retune excitability, message weights and light gain about 26,000 times per life, while the new-sense
    gains stay fixed;
  - none uses hidden cells;
  - none shows persistent activity (memory).

## Diagnosis and what followed

The populations converged on one generalist reflex, and selection across five worlds discarded the specialists'
children. The worlds also had a built-in clash: toxin, soil and home all smelled of odour C, so the toxin-avoidance
circuit worked against finding home and soil.

The follow-up study (`configs/open_worlds_v3.yaml`) keeps the engine, senses and cells unchanged. It changes:
- **the worlds:** generator v3 has a clean palette, larger payoffs for harder behaviour, per-life situations that
  call for different strategies, and nine families;
- **breeding:** half of the first parents come from the grids.

Its control is pilot v2 continued unchanged.
