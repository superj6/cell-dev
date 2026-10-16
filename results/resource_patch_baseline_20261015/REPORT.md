# Existing pursuit transfers to persistent resource collection

Without any evolution on the new patch world, the fixed AO genome collects **21.4375 ±0.8636 packets per life**:
5.9375 ±0.0625 initially present and **15.5000 ±0.8531 supplied later**. The older AM reference collects
16.3438 ±1.1462, comprising 5.4375 ±0.2197 initial and 10.9063 ±1.0154 replenished packets.
Uncertainties here are standard errors over 32 shared development lives, not evolutionary replication.

AO's paired advantage is **+5.0938 ±1.4102 captures** and **+2.8504 ±0.7032 F**. Replenished food supplies
4.5938 ±1.2723 additional captures; physical costs also fall 371.9085 ±63.1953 energy per life.
All native statuses are zero, so native and production F agree. This is a useful inherited foothold in a new
interaction. The genomes were fixed before measurement; nothing evolved or was selected on patch outcomes.

| World | AO captures/life | AM captures/life | Paired AO−AM captures |
| --- | ---: | ---: | ---: |
| Resource patches | 21.4375 ±0.8636 | 16.3438 ±1.1462 | +5.0938 ±1.4102 |
| Earlier POOL pursuit | 16.1563 ±0.8544 | 16.0938 ±0.8928 | +0.0625 ±0.9577 |
| Earlier persistent pursuit | 5.3750 ±0.6298 | 5.0000 ±0.4857 | +0.3750 ±0.7278 |

| World | AO production F | AM production F | Paired AO−AM F |
| --- | ---: | ---: | ---: |
| Resource patches | 8.1712 ±0.4288 | 5.3208 ±0.5574 | +2.8504 ±0.7032 |
| Earlier POOL pursuit | 6.0002 ±0.4005 | 5.7587 ±0.4088 | +0.2415 ±0.4539 |
| Earlier persistent pursuit | 0.5500 ±0.3112 | 0.1596 ±0.2237 | +0.3904 ±0.3485 |

The same unchanged genomes face every world. This small panel does not resolve the older-world differences or
establish a 90% retention margin. Because no new adaptation occurred, it cannot test whether future patch
evolution would preserve these older abilities. It does establish direct acquisition by the inherited genomes
in all three settings, without picking a different winner per world.

AO harvests from all three patches in 31/32 lives and two patches in the remaining life; AM reaches all three
in 27/32, two in 3/32 and one in 2/32. This additional descriptive coverage count is derived from retained per-slot
harvest columns after the main analysis; it was not a selection criterion. It establishes multi-patch harvest,
not the order of visits, useful revisits, learned schedules or neural memory. Refilled food alone can come from
camping, and these totals do not identify the control algorithm.

All 32 ordered AO survivors also receive eight shared patch lives each. Every row's mean F is positive, spanning
3.1753–8.6685; mean captures span 13.5–22.875 and replenished captures 8.0–16.875. Across row means the descriptive
averages are 17.7578 total and 12.1836 replenished packets. The row distributions use the same eight seeds and
are not 32 independent searches. No high-scoring row replaces the fixed endpoint.

There is room to investigate improved use of supply, but spill is not automatically attainable profit.
The AO reference receives 30.2188 ±1.0661 scheduled source packets per life, with 11.3750 ±0.9554 spilled while
patches are full. It makes 7.6563 ±0.7862 empty-patch clicks and 41.0938 ±3.9381 geometric misses; the corresponding
AM means are 4.6875 ±0.6860 and 66.4375 ±6.1346. AO travels less on average and has smaller final tissue.
All per-slot stocks, supplies, origins, physical charges and body counts remain in `per_life.csv`.

The next useful experiment is a small sensory intervention on these same fixed ancestors: replace each patch's
stock-dependent amplitude with either constant 1 or constant 0.55, while preserving actual food, locations,
sources, candidate streams, delays, action rules and prices. Actions and development may then diverge naturally.
Comparing both fixed brightnesses will test the whole-life value of depletion cues, with food and costs reported
separately. This is cheaper and more directly connected to existing circuitry than immediately building a new
external allocation program. The source-only options note was written before baseline outcomes.

No patch-world admission, memory mechanism or broad generality claim follows. Formal plan 0.4 admission still
requires separate fresh 512-life information/reflex/do-less comparisons. The next modulation study will explicitly
reuse development seeds and baseline native rows; it will not be called fresh confirmation. Future evolution
should be reconsidered after that evidence, retaining the same-genome older-task checks.

All **448 scientific + 8 engineering = 456 calls** finish in **37.901941 CPU /38.457846 wall seconds**, peak owned
RSS 350,179,328 bytes (333.96 MiB). The complete 90 CPU/120 wall preparation reserve charged conservatively gives
127.901941 CPU/158.457847 wall seconds against the 450/900 package caps. One thread, 2GiB owned RSS, 8GiB address
space and 4 GiB host reserve were enforced; all owned processes are clear. There was no scientific retry or cap
extension. A root release snippet initially expected a shorter review status label; it and a subsequent monitor
invocation stopped before creating an attempt, builds or lives. The corrected setup is retained explicitly.

Independent saved-data accounting verifies all 456 rows, 48,792 native ledger values, 2,280 hash words, 62,024 CSV
numeric values and 7,210 summary numeric values. All four full/fast ledger pairs agree. The audit used 0.31 CPU
seconds, no new lives or builds. Protocol `b1b4cbdb…ded55cc`; production revision `71591f3`; development blocks 147/148.
