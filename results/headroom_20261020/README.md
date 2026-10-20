# Eco-world headroom check (2026-10-20)

**These numbers are for the first ABI 8 worlds (eco v1).** The world problems found here led to the eco v2 rules
(docs/LIFE_ABI.md 9.8.7, docs/OPEN_WORLDS.md §11), which the pilot now trains on. Raw per-life rows stay in
`outputs/headroom_20261020/`; this copy keeps the report, `summary.json` and `speed.json`.

This is a simplified version of the per-world check in docs/OPEN_WORLDS.md §7. It asks two questions of each of the
five eco worlds:
- how much more could a body earn than the current evolved bodies do;
- which information sources pay for it.

It is a yardstick, not a gate. No world is admitted, rejected or retuned on these numbers.

Rerun with `.venv/bin/python -m scripts.eco_headroom --out outputs/headroom_20261020`. It runs at nice 15 on two
threads, and every part is cached in this directory:
- the evolved part took about 13 min on one thread;
- the controllers took about 2.5 h on two processes, on a loaded laptop.

Files in this directory:
- `summary.json`: every number below, with SEs;
- `controllers.jsonl`: one row per controller life;
- `evolved.npz` and `evolved_meta.json`: the evolved bodies' full ledgers, and which genomes;
- `speed.json`: the speed cap.

## Bottom line

- **Every world has a lot of room above the evolved founders.**
  - The privileged ceiling earns 20k–44k gross per life against the founders' 0.4k–3.0k: a gap of 18k–43k, 11–22 SE.
  - The partial-information controller adds +2.2k to +4.1k eco net over the founders in every world, all > 4 SE
    and all at least 4 food units (500 each).
  - Against the stronger reflex yardstick (the light-chaser), the partial gap is resolved in predator, home and
    farm. It is not resolved in plume (2.0 SE) or prey (2.8 SE).
- **The founders sit near the no-sensing floor.**
  - A random walk that clicks blindly at the key's top rate earns nearly their gross in plume (2.3k vs 3.0k) and in
    home (1.7k vs 1.7k). Only the miss charge makes it lose money.
  - In predator and farm the founders' eco net is about zero or negative.
- **The partial controller reaches only 8–19% of the privileged ceiling.** Much of the remaining gap is surely my
  controller's weakness, not missing information, so the partial numbers are lower bounds.
- **No world shows three information sources that each pay a resolved share, with this controller.**
  - plume: flow (+1.8k ± 0.5k).
  - prey: memory (+1.5k ± 0.3k) and odour identity (+2.3k ± 0.4k).
  - farm: memory (+2.7k ± 0.4k).
  - predator and home: none. Near misses at 2–2.4 SE are identity and light in predator, and flow in home.
  - Vibration pays nowhere, and identity is negative in farm and home (see the world problems below).

  These are properties of this hand-written controller's use of each sense. A zero or negative drop does not show
  that the source cannot pay.
- **Suspected world problems (details below).**
  - The farm can be farmed by a body that never senses or moves, when it starts on soil (9% of lives).
  - Freezing gives no protection in any rule.
  - Shelters are invisible to every sense.
  - The sun slot carries no information.
  - The 128-puff cap, not the puff life, sets plume length in most plume lives.

## Key tables (mean ± SE over 64 worlds per family, paired differences)

**Gross income per life** (all eco income: food, prey, harvest, delivery, digestion):

| world | evolved (16 founders) | light-chaser | partial | privileged | partial − evolved | privileged − evolved |
|---|---|---|---|---|---|---|
| plume | 3,021 ± 319 | 4,495 ± 520 | 4,852 ± 581 | 24,793 ± 1,020 | 1,831 ± 662 | 21,772 ± 990 |
| predator | 2,250 ± 269 | 3,293 ± 441 | 5,890 ± 626 | 20,162 ± 1,201 | 3,641 ± 576 | 17,912 ± 1,113 |
| home | 1,694 ± 186 | 1,534 ± 255 | 4,306 ± 492 | 32,337 ± 1,521 | 2,613 ± 502 | 30,644 ± 1,469 |
| prey | 2,189 ± 209 | 2,841 ± 382 | 4,045 ± 416 | 20,458 ± 1,738 | 1,856 ± 395 | 18,269 ± 1,684 |
| farm | 421 ± 89 | 965 ± 202 | 3,486 ± 450 | 43,908 ± 2,505 | 3,065 ± 429 | 43,487 ± 2,468 |

**Eco net per life** (gross − toxin, damage and planting costs; misses and body running cost excluded):

| world | evolved (16 founders) | light-chaser | partial | privileged | partial − evolved | privileged − evolved |
|---|---|---|---|---|---|---|
| plume | 1,174 ± 403 | 2,576 ± 642 | 4,242 ± 616 | 24,793 ± 1,020 | 3,069 ± 664 | 23,620 ± 1,058 |
| predator | -408 ± 382 | 428 ± 568 | 3,736 ± 760 | 19,518 ± 1,272 | 4,143 ± 631 | 19,925 ± 1,162 |
| home | 995 ± 270 | 1,030 ± 286 | 3,943 ± 521 | 32,337 ± 1,521 | 2,948 ± 506 | 31,343 ± 1,478 |
| prey | 1,545 ± 290 | 2,357 ± 385 | 3,728 ± 464 | 20,458 ± 1,738 | 2,183 ± 417 | 18,913 ± 1,721 |
| farm | -102 ± 193 | 221 ± 289 | 2,945 ± 425 | 38,974 ± 2,476 | 3,046 ± 419 | 39,075 ± 2,412 |

The light-chaser approximates the founders, which were evolved on glow worlds and are blind to the new slots. Its gross is
0.9×–2.3× theirs, the same order.

The founders' eco net hides their running cost:
- they pay about 1.1k–1.4k per life in body running cost (cells, spikes, strokes and misses);
- their mean F is −0.18 (plume), −1.46 (predator), −0.38 (home), +0.18 (prey) and −1.42 (farm).

**Ablations of the partial controller:** the paired drop in eco net when one source is removed. Bold means resolved,
i.e. more than 3 paired SE.

| world | memory | odour identity | vibration | flow | light | sources paying (>3 SE) |
|---|---|---|---|---|---|---|
| plume | -181 ± 387 | 694 ± 461 | -177 ± 197 | **1,786 ± 516** | 423 ± 219 | 1 |
| predator | 148 ± 305 | 951 ± 394 | -500 ± 411 | 360 ± 353 | 440 ± 214 | 0 |
| home | 758 ± 484 | -863 ± 878 | -284 ± 233 | 941 ± 411 | 161 ± 241 | 0 |
| prey | **1,537 ± 342** | **2,277 ± 436** | -20 ± 320 | -7 ± 203 | 9 ± 169 | 2 |
| farm | **2,657 ± 434** | -1,121 ± 459 | 49 ± 126 | 115 ± 157 | 24 ± 133 | 1 |

Receptor noise itself costs little. The noise-free variant `partial_clean` is within 1.3 SE of `partial` in plume,
predator, prey and farm, and +0.9k ± 0.5k in home.

## How it was measured

**Worlds and seeds.** Five families, 64 worlds each: `ecology.realize(family, 7_000_000 + i, T=1024)` for
i = 0..63, built exactly as the pilot's evaluator builds them (`configs/open_worlds_pilot_U.yaml`,
`LifeEvaluator._task_world`). Every body and controller lives the same 320 worlds with the same life seed. So the
puffs, current turns, agent looks and plant ripening draws are the same for all of them, and every comparison is
paired by world.

**Evolved bodies.** The pilot's founders: the D90_Z_s5 and AO_s7 populations, 32 genomes each, read-only from
`outputs/open_worlds_pilot/inputs/`.
- All 64 genomes were screened on 8 other worlds per family (seeds 7_500_000 + i).
- The best 8 per lineage by mean F were run on the panel with the C kernel (`build.run(..., abi=V8, fast=True)`).
- "Evolved" below is the mean of these 16 genomes per world. "Evolved best" is the single genome with the best eco net
  on the panel itself, so it is chosen in-sample and is optimistic.

**Controllers.** They drive the dot inside `reference._Accountant`, the Python spec of the eco world, with no cells.
- The world rules are the accountant's own: click resolution, capture radius 1, wall kinks and sliding, carry drag,
  agents, puffs, damage, kill at the next integer time, and income.
- Each step (0.25 units) the controller sets the dot's force.
- **Speed cap 0.208.** This is the 90th percentile of the evolved bodies' per-life mean speed (path / t_end; median
  0.155, maximum 0.354). It caps the instantaneous speed, so a moving controller averages about 0.198. A loaded dot
  is slower by its drag.
- **Click interval at least 2.2 units.** This is the key's fastest re-arm: the hotspot twitch must decay from 0.6
  below 0.25 with tau_z 2.5. The evolved bodies click 0.027 times per unit on average; the controllers click more.
- **Costs.** Controllers pay no body running cost (cells, spikes, strokes, receptors). They pay only the miss charge
  (10 per empty click), which is reported separately.

**Metrics.**
- Gross income is the ledger's `income`: food eaten + prey + harvest + delivery + digestion of carried items.
- Eco costs are toxin + damage + planting.
- **Eco net = gross − eco costs.** This is the main comparison.
- Means ± SE are over the 64 worlds. Differences are paired by world.
- The stochastic controllers ran 2 replicates of their own random streams per world, averaged within the world.

## The controllers

- **privileged**: reads the true world state and plans greedily, by value per unit time, over:
  - food sources with their stock and regrowth times;
  - ripe and ripening plants;
  - prey, intercepted from their true velocity, or awaited at their refuge before they reappear;
  - free sowing spots on fertile soil (a grid spaced 1.1);
  - delivery home, valued at (multiplier − 1) × the items that would still be carried.

  It routes around walls on a visibility graph of the inflated wall corners, and keeps out of ambushers' strike
  disks. It flees a chasing pursuer, to a shelter if the shelter is closer to it than to the predator. It never
  clicks unless the click resolves to income. Greedy is not optimal, so this is a lower bound on the true ceiling.
- **partial**: only what a body could sense.
  - **Senses.** 13 sense points (the centre, a ring at 1.5 and a ring at 3; the founders' sense cells reach radius
    3–4.4) with 3 cells each, each cell reporting Poisson receptor events under the world's own rate laws (2-unit
    traces):
    - light;
    - odours A–D;
    - flow on the six outer faces (the current relative to the body);
    - touch;
    - vibration.
  - **Own state.** An efference copy of its own motion (noisy path integration: 3% gain error, 5% and 0.03 rad per
    step), and its load (drag). It never senses whether a click paid, except through a change of load.
  - **Detection** uses the excess rate pooled over the body. **Tap decisions** use the centre point, the only one
    within the capture radius.
  - **Behaviours, in priority order:**
    1. Flee odour D (danger), or a strong and rising vibration. Remember a danger that does not vibrate (an
       ambusher) and steer around it.
    2. Tap at a food or light peak, unless the blend is toxin-like (C with A). Leave a site after 4 taps, or when a
       tap stops adding load.
    3. Carry home when loaded: path integration with a Bug-style wall follower, then the home blend B+C.
    4. Chase prey odour (B without A or C). Tap where a strong prey odour went quiet (a freezer).
    5. Approach steady vibration when this life's movers have smelled of prey.
    6. Surge upstream (flow) and up the food-odour gradient.
    7. On soil (C alone): climb to its peak, sow a 7-spot plot, return every 60 units, harvest spots with ripe odour,
       re-sow.
    8. Cast crosswind for 30 units, then search within 11 units of home and revisit old sites.
- **Ablations of partial**, each removing one source:
  - `nomem`: no path integration, no spatial memory (sites, plots, toxin and ambusher spots, a vanished prey) and
    no within-life prior; reactive only.
  - `noident`: one receptor for the sum of the four odours, so no blend discrimination.
  - `novib`: no vibration.
  - `noflow`: no flow sense.
  - `nolight`: no light.

  `partial_clean` is partial with noise-free receptor rates. All variants share their random streams (common random
  numbers), so they differ only where the senses differ.
- **light**: the light-chaser reflex. It climbs the light seen by the sense points and taps when the centre is
  brightest, else does a correlated random walk. This approximates the founders, which were evolved on glow worlds
  and are blind to the new slots.
- **Sensing-free baselines**:
  - `still`: never moves or clicks.
  - `blind`: a random walk clicking every 2.2 units.
  - `blind_slow`: the same random walk, clicking every 10 units.
  - `sit_click`: sits at the start clicking every 5 units.

## Per-world detail

Columns:
- gross, then its parts (food / prey / harvest / delivery / digestion);
- eco costs (toxin / damage / planting);
- eco net;
- killed: the fraction of lives ended by predators;
- clicks and misses per life;
- speed: path / t_end.

#### plume

| body | gross | food / prey / harvest / delivery / digestion | toxin / damage / planting | eco net | killed | clicks | misses | speed |
|---|---|---|---|---|---|---|---|---|
| evolved, mean of 16 | 3,021 ± 319 | 3,021 / 0 / 0 / 0 / 0 | 950 / 898 / 0 | 1,174 ± 403 | 0.13 | 29 | 23 | 0.167 |
| evolved best (D90_Z_s5#1, in-sample) | 3,622 ± 451 | 3,622 / 0 / 0 / 0 / 0 | 629 / 680 / 0 | 2,313 ± 556 | 0.09 | 35 | 28 | 0.204 |
| still | 0 ± 0 | 0 / 0 / 0 / 0 / 0 | 0 / 788 / 0 | -788 ± 252 | 0.14 | 0 | 0 | 0.000 |
| blind | 2,299 ± 227 | 2,299 / 0 / 0 / 0 / 0 | 525 / 607 / 0 | 1,166 ± 316 | 0.03 | 447 | 443 | 0.197 |
| blind_slow | 722 ± 79 | 722 / 0 / 0 / 0 / 0 | 145 / 411 / 0 | 166 ± 130 | 0.02 | 102 | 101 | 0.197 |
| sit_click | 0 ± 0 | 0 / 0 / 0 / 0 / 0 | 0 / 788 / 0 | -788 ± 252 | 0.14 | 189 | 189 | 0.000 |
| light | 4,495 ± 520 | 4,495 / 0 / 0 / 0 / 0 | 1,175 / 744 / 0 | 2,576 ± 642 | 0.13 | 75 | 66 | 0.164 |
| partial | 4,852 ± 581 | 4,852 / 0 / 0 / 0 / 0 | 53 / 557 / 0 | 4,242 ± 616 | 0.06 | 122 | 114 | 0.154 |
| partial_nomem | 5,804 ± 605 | 5,804 / 0 / 0 / 0 / 0 | 883 / 497 / 0 | 4,423 ± 679 | 0.05 | 148 | 138 | 0.171 |
| partial_noident | 5,312 ± 583 | 5,312 / 0 / 0 / 0 / 0 | 1,022 / 741 / 0 | 3,548 ± 686 | 0.13 | 176 | 167 | 0.165 |
| partial_novib | 4,963 ± 581 | 4,963 / 0 / 0 / 0 / 0 | 53 / 490 / 0 | 4,420 ± 625 | 0.08 | 130 | 122 | 0.154 |
| partial_noflow | 3,563 ± 517 | 3,563 / 0 / 0 / 0 / 0 | 42 / 1,064 / 0 | 2,456 ± 599 | 0.16 | 148 | 142 | 0.141 |
| partial_nolight | 4,455 ± 572 | 4,455 / 0 / 0 / 0 / 0 | 70 / 565 / 0 | 3,819 ± 613 | 0.05 | 130 | 124 | 0.154 |
| partial_clean | 4,749 ± 593 | 4,749 / 0 / 0 / 0 / 0 | 80 / 450 / 0 | 4,219 ± 615 | 0.06 | 162 | 155 | 0.132 |
| privileged | 24,793 ± 1,020 | 24,793 / 0 / 0 / 0 / 0 | 0 / 0 / 0 | 24,793 ± 1,020 | 0.00 | 38 | 0 | 0.122 |

#### predator

| body | gross | food / prey / harvest / delivery / digestion | toxin / damage / planting | eco net | killed | clicks | misses | speed |
|---|---|---|---|---|---|---|---|---|
| evolved, mean of 16 | 2,250 ± 269 | 2,250 / 0 / 0 / 0 / 0 | 104 / 2,553 / 0 | -408 ± 382 | 0.41 | 22 | 18 | 0.158 |
| evolved best (AO_s7#7, in-sample) | 2,650 ± 470 | 2,650 / 0 / 0 / 0 / 0 | 73 / 2,500 / 0 | 77 ± 631 | 0.39 | 20 | 16 | 0.141 |
| still | 0 ± 0 | 0 / 0 / 0 / 0 / 0 | 0 / 1,632 / 0 | -1,632 ± 361 | 0.30 | 0 | 0 | 0.000 |
| blind | 1,648 ± 195 | 1,648 / 0 / 0 / 0 / 0 | 113 / 1,983 / 0 | -448 ± 255 | 0.23 | 384 | 382 | 0.197 |
| blind_slow | 561 ± 81 | 561 / 0 / 0 / 0 / 0 | 39 / 1,677 / 0 | -1,155 ± 173 | 0.19 | 92 | 91 | 0.197 |
| sit_click | 0 ± 0 | 0 / 0 / 0 / 0 / 0 | 0 / 1,632 / 0 | -1,632 ± 361 | 0.30 | 170 | 170 | 0.000 |
| light | 3,293 ± 441 | 3,293 / 0 / 0 / 0 / 0 | 212 / 2,654 / 0 | 428 ± 568 | 0.48 | 51 | 46 | 0.167 |
| partial | 5,890 ± 626 | 5,890 / 0 / 0 / 0 / 0 | 49 / 2,106 / 0 | 3,736 ± 760 | 0.33 | 141 | 131 | 0.152 |
| partial_nomem | 5,633 ± 669 | 5,633 / 0 / 0 / 0 / 0 | 363 / 1,682 / 0 | 3,588 ± 778 | 0.24 | 146 | 136 | 0.169 |
| partial_noident | 5,725 ± 622 | 5,725 / 0 / 0 / 0 / 0 | 434 / 2,506 / 0 | 2,785 ± 794 | 0.43 | 146 | 136 | 0.165 |
| partial_novib | 6,089 ± 708 | 6,089 / 0 / 0 / 0 / 0 | 48 / 1,806 / 0 | 4,236 ± 843 | 0.28 | 146 | 137 | 0.155 |
| partial_noflow | 5,304 ± 652 | 5,304 / 0 / 0 / 0 / 0 | 15 / 1,913 / 0 | 3,376 ± 781 | 0.29 | 145 | 137 | 0.149 |
| partial_nolight | 5,769 ± 600 | 5,769 / 0 / 0 / 0 / 0 | 151 / 2,322 / 0 | 3,296 ± 750 | 0.35 | 136 | 127 | 0.154 |
| partial_clean | 5,243 ± 622 | 5,243 / 0 / 0 / 0 / 0 | 84 / 1,965 / 0 | 3,194 ± 754 | 0.34 | 165 | 156 | 0.138 |
| privileged | 20,162 ± 1,201 | 20,162 / 0 / 0 / 0 / 0 | 0 / 644 / 0 | 19,518 ± 1,272 | 0.09 | 31 | 0 | 0.118 |

#### home

| body | gross | food / prey / harvest / delivery / digestion | toxin / damage / planting | eco net | killed | clicks | misses | speed |
|---|---|---|---|---|---|---|---|---|
| evolved, mean of 16 | 1,694 ± 186 | 565 / 0 / 0 / 25 / 1,104 | 205 / 494 / 0 | 995 ± 270 | 0.09 | 27 | 24 | 0.143 |
| evolved best (D90_Z_s5#30, in-sample) | 2,015 ± 268 | 686 / 0 / 0 / 31 / 1,298 | 188 / 479 / 0 | 1,348 ± 334 | 0.08 | 36 | 32 | 0.177 |
| still | 0 ± 0 | 0 / 0 / 0 / 0 / 0 | 0 / 342 / 0 | -342 ± 154 | 0.08 | 0 | 0 | 0.000 |
| blind | 1,704 ± 226 | 648 / 0 / 0 / 81 / 975 | 70 / 330 / 0 | 1,305 ± 246 | 0.02 | 454 | 451 | 0.182 |
| blind_slow | 721 ± 103 | 125 / 0 / 0 / 94 / 502 | 57 / 246 / 0 | 417 ± 134 | 0.02 | 102 | 101 | 0.186 |
| sit_click | 0 ± 0 | 0 / 0 / 0 / 0 / 0 | 0 / 342 / 0 | -342 ± 154 | 0.08 | 197 | 197 | 0.000 |
| light | 1,534 ± 255 | 511 / 0 / 0 / 0 / 1,023 | 117 / 386 / 0 | 1,030 ± 286 | 0.06 | 49 | 46 | 0.162 |
| partial | 4,306 ± 492 | 410 / 0 / 0 / 3,591 / 306 | 5 / 359 / 0 | 3,943 ± 521 | 0.05 | 51 | 46 | 0.148 |
| partial_nomem | 3,374 ± 273 | 938 / 0 / 0 / 576 / 1,860 | 62 / 127 / 0 | 3,185 ± 296 | 0.02 | 52 | 46 | 0.168 |
| partial_noident | 5,720 ± 899 | 281 / 0 / 0 / 5,397 / 42 | 306 / 608 / 0 | 4,806 ± 942 | 0.12 | 155 | 148 | 0.158 |
| partial_novib | 4,514 ± 522 | 444 / 0 / 0 / 3,729 / 340 | 5 / 282 / 0 | 4,227 ± 541 | 0.03 | 51 | 46 | 0.150 |
| partial_noflow | 3,416 ± 402 | 453 / 0 / 0 / 2,765 / 198 | 9 / 405 / 0 | 3,002 ± 434 | 0.07 | 65 | 61 | 0.140 |
| partial_nolight | 4,136 ± 474 | 509 / 0 / 0 / 3,336 / 291 | 12 / 342 / 0 | 3,782 ± 497 | 0.05 | 53 | 48 | 0.148 |
| partial_clean | 5,146 ± 639 | 682 / 0 / 0 / 4,113 / 351 | 0 / 332 / 0 | 4,813 ± 673 | 0.05 | 49 | 43 | 0.126 |
| privileged | 32,337 ± 1,521 | 5,870 / 0 / 0 / 24,251 / 2,216 | 0 / 0 / 0 | 32,337 ± 1,521 | 0.00 | 34 | 0 | 0.141 |

#### prey

| body | gross | food / prey / harvest / delivery / digestion | toxin / damage / planting | eco net | killed | clicks | misses | speed |
|---|---|---|---|---|---|---|---|---|
| evolved, mean of 16 | 2,189 ± 209 | 280 / 1,909 / 0 / 0 / 0 | 0 / 644 / 0 | 1,545 ± 290 | 0.10 | 25 | 22 | 0.164 |
| evolved best (D90_Z_s5#0, in-sample) | 3,012 ± 428 | 278 / 2,734 / 0 / 0 / 0 | 0 / 500 / 0 | 2,512 ± 479 | 0.06 | 30 | 27 | 0.202 |
| still | 0 ± 0 | 0 / 0 / 0 / 0 / 0 | 0 / 471 / 0 | -471 ± 191 | 0.09 | 0 | 0 | 0.000 |
| blind | 894 ± 97 | 214 / 680 / 0 / 0 / 0 | 0 / 307 / 0 | 587 ± 138 | 0.02 | 453 | 452 | 0.197 |
| blind_slow | 540 ± 77 | 156 / 384 / 0 / 0 / 0 | 0 / 267 / 0 | 273 ± 117 | 0.01 | 102 | 102 | 0.197 |
| sit_click | 68 ± 47 | 0 / 68 / 0 / 0 / 0 | 0 / 471 / 0 | -404 ± 199 | 0.09 | 193 | 193 | 0.000 |
| light | 2,841 ± 382 | 254 / 2,586 / 0 / 0 / 0 | 0 / 483 / 0 | 2,357 ± 385 | 0.08 | 31 | 28 | 0.177 |
| partial | 4,045 ± 416 | 1,009 / 3,036 / 0 / 0 / 0 | 0 / 317 / 0 | 3,728 ± 464 | 0.04 | 78 | 73 | 0.172 |
| partial_nomem | 2,423 ± 318 | 1,503 / 920 / 0 / 0 / 0 | 0 / 232 / 0 | 2,191 ± 350 | 0.03 | 104 | 100 | 0.177 |
| partial_noident | 2,038 ± 298 | 1,661 / 377 / 0 / 0 / 0 | 0 / 587 / 0 | 1,452 ± 388 | 0.11 | 90 | 87 | 0.177 |
| partial_novib | 4,084 ± 367 | 1,635 / 2,449 / 0 / 0 / 0 | 0 / 335 / 0 | 3,749 ± 422 | 0.03 | 123 | 118 | 0.164 |
| partial_noflow | 4,113 ± 431 | 995 / 3,119 / 0 / 0 / 0 | 0 / 378 / 0 | 3,735 ± 476 | 0.05 | 87 | 82 | 0.172 |
| partial_nolight | 4,080 ± 427 | 1,127 / 2,953 / 0 / 0 / 0 | 0 / 361 / 0 | 3,719 ± 477 | 0.04 | 81 | 76 | 0.172 |
| partial_clean | 4,151 ± 413 | 1,029 / 3,122 / 0 / 0 / 0 | 0 / 364 / 0 | 3,787 ± 465 | 0.04 | 72 | 67 | 0.171 |
| privileged | 20,458 ± 1,738 | 1,021 / 19,437 / 0 / 0 / 0 | 0 / 0 / 0 | 20,458 ± 1,738 | 0.00 | 19 | 0 | 0.119 |

#### farm

| body | gross | food / prey / harvest / delivery / digestion | toxin / damage / planting | eco net | killed | clicks | misses | speed |
|---|---|---|---|---|---|---|---|---|
| evolved, mean of 16 | 421 ± 89 | 75 / 0 / 346 / 0 / 0 | 0 / 424 / 98 | -102 ± 193 | 0.06 | 22 | 20 | 0.152 |
| evolved best (D90_Z_s5#0, in-sample) | 764 ± 191 | 106 / 0 / 658 / 0 / 0 | 0 / 426 / 154 | 184 ± 272 | 0.05 | 28 | 25 | 0.185 |
| still | 0 ± 0 | 0 / 0 / 0 / 0 / 0 | 0 / 316 / 0 | -316 ± 180 | 0.05 | 0 | 0 | 0.000 |
| blind | 207 ± 43 | 137 / 0 / 71 / 0 / 0 | 0 / 376 / 253 | -422 ± 118 | 0.01 | 455 | 450 | 0.198 |
| blind_slow | 85 ± 19 | 77 / 0 / 9 / 0 / 0 | 0 / 309 / 155 | -379 ± 103 | 0.01 | 103 | 100 | 0.198 |
| sit_click | 502 ± 212 | 0 / 0 / 502 / 0 / 0 | 0 / 316 / 52 | 134 ± 273 | 0.05 | 199 | 197 | 0.000 |
| light | 965 ± 202 | 106 / 0 / 859 / 0 / 0 | 0 / 583 / 161 | 221 ± 289 | 0.09 | 34 | 30 | 0.177 |
| partial | 3,486 ± 450 | 121 / 0 / 3,365 / 0 / 0 | 0 / 0 / 541 | 2,945 ± 425 | 0.00 | 40 | 25 | 0.177 |
| partial_nomem | 694 ± 74 | 261 / 0 / 434 / 0 / 0 | 0 / 55 / 352 | 287 ± 90 | 0.01 | 70 | 63 | 0.180 |
| partial_noident | 5,601 ± 562 | 203 / 0 / 5,399 / 0 / 0 | 0 / 508 / 1,027 | 4,066 ± 622 | 0.08 | 205 | 178 | 0.160 |
| partial_novib | 3,396 ± 424 | 147 / 0 / 3,249 / 0 / 0 | 0 / 0 / 500 | 2,896 ± 399 | 0.00 | 43 | 29 | 0.177 |
| partial_noflow | 3,327 ± 428 | 108 / 0 / 3,219 / 0 / 0 | 0 / 0 / 498 | 2,829 ± 403 | 0.00 | 50 | 35 | 0.173 |
| partial_nolight | 3,466 ± 484 | 109 / 0 / 3,357 / 0 / 0 | 0 / 0 / 545 | 2,921 ± 456 | 0.00 | 40 | 25 | 0.178 |
| partial_clean | 3,500 ± 421 | 106 / 0 / 3,394 / 0 / 0 | 0 / 18 / 527 | 2,955 ± 390 | 0.00 | 55 | 40 | 0.164 |
| privileged | 43,908 ± 2,505 | 469 / 0 / 43,439 / 0 / 0 | 0 / 0 / 4,934 | 38,974 ± 2,476 | 0.00 | 159 | 0 | 0.139 |

What the tables say per world:
- **plume.**
  - Flow is the one resolved source: surging upstream.
  - Light (+0.4k ± 0.2k) and identity (+0.7k ± 0.5k) are about 1.5–2 SE. Without identity the controller eats
    toxins (1.0k).
  - The founders and the light-chaser pay about 1k each in toxins, many of them lit (34% of plume toxins carry light).
  - Without memory the gross rises but the toxin cost rises with it, so eco net is unchanged.
- **predator.**
  - Damage dominates: the founders pay 2.6k and are killed in 41% of lives.
  - Even `still` is killed in 30% of lives, because pursuers wander to it. The privileged controller is killed in 9%
    (6 of 64) despite full knowledge.
  - Without identity, toxin and damage costs and kills rise (+951 ± 394, 2.4 SE).
- **home.**
  - The ceiling is mostly delivery: 24k of the privileged 32k.
  - Partial delivers 3.6k. Without memory (no path integration) delivery falls to 0.6k. Memory's net drop is only
    +0.76k ± 0.48k because undelivered items still digest at base value (1.9k digestion without memory).
  - Without identity the controller taps at every odour peak, including home's, and delivers more (5.4k). That is my
    homing rule being too strict, not identity being useless.
- **prey.**
  - Identity and memory both pay: tell prey odour from food odour, and tap where a freezer went quiet.
  - The privileged controller's 19k from prey relies on knowing refuges and camping there for reappearance; a body
    could only learn these by memory.
  - 82% of darters outrun the speed cap while alarmed.
- **farm.**
  - Memory pays the most here: returning to plots after 60 units.
  - The ceiling (44k gross) is the highest of all worlds, and it is almost all one loop: sow every free spot on a
    1.1 grid, harvest on ripening, re-sow.
  - Without identity the controller taps at every odour peak, the soil peak included. So it sows densely and earns
    more (5.6k vs 3.5k): blanket tapping on soil beats my careful 7-spot plot.

## Suspected world problems (with evidence)

1. **Farm pays a body that never senses or moves.**
   - 6 of 64 farm lives (9%) start on fertile soil, because fertile disks are not kept clear of the start the way walls
     are.
   - In those lives `sit_click` (no movement, a tap every 5 units) earns 3.5k–9.9k gross, +0.9k to +7.4k after its
     miss charge (lives 18, 21, 22, 43, 56 and 62).
   - That compares with 0.4k for the founders and 3.5k for the partial controller on average.
   - More generally, planting returns 300–900 for a 20–100 seed with only a capture radius (1.0) of spacing.
     Blanket tapping on soil pays, and the farm ceiling is one repetitive loop worth about 2× any other world.
   - Worth considering: keep soil off the start, and make farming need management (spacing, tending, pests or
     weeds) rather than tapping.
2. **Freezing has no effect.**
   - In `_Accountant._ag_look`, a pursuit predator detects the body on distance, shelter and a random draw only. An
     ambusher strikes on the same.
   - Neither reads the body's speed. So "freezing versus fleeing" (§3.2) is not a trade-off in the rules.
   - The predator world's second behaviour descriptor (still samples under threat) measures a behaviour with no
     consequence.
3. **Shelters are invisible.**
   - No receptor field includes them: `_eco_conc`, `_eco_light` and touch cover puffs, agents, home, soil, plants and
     walls only.
   - Yet 64 of 96 pursuit predators in the predator family (67%) are faster than the body's speed cap. Against those
     only a shelter helps.
   - A body can find a shelter only by luck or by remembering where chases ended.
4. **The sun slot is uninformative.** The sun heading is fixed for the whole life (`eco_sun_heading`; no drift as built).
   The dot never rotates, so each cell's sun rate is a constant of its position in the body. Heading is already
   world-fixed, and path integration works without it.
5. **Plume length is set by the puff cap.**
   - With 128 puffs shared by all sources, plume lives keep on average only 67% of the nominal puff life (minimum 31%).
   - 61% of plume lives lose more than a quarter of it (89% have release rate × puff life > 128).
   - More sources therefore means shorter plumes, and `eco_puff_life` is partly nominal.
6. **The current never moves the body.** `dot_at` ignores the current, although §3.3 says currents push the body. This
   is not broken, but flow is then sensed only as current minus self-motion. A body cannot drift-sense its position.
7. **Not problems, but worth knowing.**
   - Food made unreachable by walls is rare (0–1.4% of sources).
   - Lit toxins (16–44% of toxins) punish a pure light reflex.
   - Carried items digest at base value, so carrying is never worse than eating, except for items picked within a
     digestion time of the end of life.
   - The miss charge (10) is what keeps blind clicking unprofitable: −3.2k to −4.9k per life at the key's top rate.

## What could not be measured, and caveats

**Not done.**
- No receptor-raster decoding (the "cheaper first bound" of §7).
- No infotaxis or marginal-value baselines.
- No transfer families.
- No matched controller with the body's exact latency, footprint and costs (§7 asks for one).

**The controllers are hand-written heuristics.**
- Partial-information numbers are lower bounds on what the information allows, and the ablations describe this
  controller's use of each sense. Its use of vibration, and of identity in farm and home, is visibly weak.
- The privileged planner is greedy: no lookahead and no multi-target routes. It too is a lower bound on the true
  ceiling.

**Possible bias.**
- I debugged the controllers on panel worlds 0–11, a small in-sample bias in their favour.
- "Evolved best" is picked on the panel itself, so it is optimistic.

**The comparison is not fully matched.**
- Controllers pay no body running cost and no receptor cost.
- They sense every modality with every point (13 points × 3 cells; the founders have 30–42 sense cells).
- They subtract their own velocity from the flow (an efference copy).
- They click 1.5×–6× as often as the founders, within the key's limit.
- Their mean speeds (0.12–0.18) are close to the founders' (0.14–0.17).

**Noise.**
- Per-life outcomes are heavy-tailed: finding a rich or lit source early decides a life.
- Even with 64 worlds and 2 controller replicates, SEs are 0.1k–0.9k on ablation drops. Effects below about 0.5k–1.5k
  (depending on the world) are not resolved.

## After the eco v2 fix (same 64 seeds per world, no-sensing and reflex controllers only)

`outputs/headroom_20261020_v2/`. Eco net per life:

| World | Controller | v1 | v2 |
|---|---|---:|---:|
| Farm | sit at the start and tap every 5 | 134 (best life 9,254) | 0 (best life 0) |
| Farm | random walk, blind tapping | −422 | −592 (tramples 5.8 plants per life) |
| Farm | light-chaser | 221 | −406 |
| Predator | never moves: share of lives killed | 0.30 | 0.00 |
| Predator | light-chaser: share of lives killed | 0.48 | 0.45 |

- Plume, home and prey are unchanged for these controllers.
- A blind random walk still nets about +1.2k in plume and home before miss charges, because food is dense.
- The partial-information and privileged controllers were not rerun.
