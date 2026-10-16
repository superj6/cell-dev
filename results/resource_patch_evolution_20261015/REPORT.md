# Resource continuation improves economy, with acquisition tradeoffs

Eight ordinary generations from the full AO population improve trained resource-patch fitness by
**0.595798 ±0.161773 F**, but do not establish improved resource acquisition. Lower physical costs supply
0.436534 F, about **73.27%** of the mean gain. Total captures change **+0.326172 ±0.328844** and replenished
food **+0.373047 ±0.302795**. Empty-patch attempts increase. Earlier POOL acquisition and acquisition in the
reserved patch combination decline. This is a useful economy result, not demonstrated cumulative acquisition,
resource allocation, memory or a new reusable algorithm.

All uncertainties below are paired life-level SE across 512 shared fresh seeds, except the absolute means.
Three-SE bounds are descriptive. This is one evolutionary continuation, not a replicated estimate of search
reliability. Generation 8 remains primary; generation 4 is a fixed passive observation.

## Fixed design

All 32 ordered AO balanced24 survivors seed the search. Their 875 float32 parameters are unchanged at import;
IDs are remapped in order and scores/RNG are fresh. This is genetic inheritance, not a resumed AO random stream.
Each of eight generations evaluates 32 parents and 224 ordinary offspring, with two scaled point additions
per offspring and ordinary crossover. The top 64 receive eight recheck lives. Selection and recheck repeat
the fixed `(patch, POOL, patch, persistent)` sequence twice. Physical prices, the world laws and local asynchronous
cell rules remain unchanged. No prescribed behavior enters the organism.

The fixed AO starting genome and generation-4/generation-8 rank-zero endpoints each receive 512 shared lives
in five worlds: trained patches, POOL, persistent pursuit, earlier longer cue gaps, and a reserved combination
of four patches, radius 3–5 and refill periods 100/200. The latter combination never enters selection. The same
unchanged genome faces every world; no per-world winner is chosen. All worlds use T1024; production F is native
physical F minus the ordinary extinction surcharge. FIFO counters separate initial from replenished food, not visit order.

## Acquisition and fitness

| World | Start captures | Generation 4 | Generation 8 | Final minus start captures ±SE | Final minus start F ±SE |
|---|---:|---:|---:|---:|---:|
| Trained patches | 19.046875 | 19.859375 | 19.373047 | +0.326172 ±0.328844 | +0.595798 ±0.161773 |
| POOL | 16.029297 | 14.607422 | 14.167969 | −1.861328 ±0.216181 | −0.560391 ±0.104002 |
| Persistent pursuit | 5.919922 | 5.517578 | 5.611328 | −0.308594 ±0.138287 | +0.233100 ±0.068173 |
| Longer cue gaps | 4.142578 | 3.814453 | 3.921875 | −0.220703 ±0.112785 | +0.261093 ±0.055780 |
| Reserved patch combination | 17.519531 | 16.994141 | 16.136719 | −1.382813 ±0.267868 | −0.289727 ±0.128349 |

On trained patches, replenished harvest changes from 13.328125 to 13.701172; initial harvest changes from
5.718750 to 5.671875. Physical costs fall from 2356.545279 to 1909.534166 energy, saving **447.011113 ±13.274349**.
Maintenance supplies 281.118951 energy of the savings and missed attempts another 113.828125. Average final
cell count falls from 83.121094 to 68.984375; distance travelled falls by 34.406038 ±2.748447.

Geometric misses fall **13.347656 ±0.895338**, while attempts at empty patches rise **1.964844 ±0.297662**
(7.632812→9.597656). Total misses therefore fall 11.382812 ±0.864022. These distinctions matter: fewer overall
misses do not mean better use of depletion information. Extra food contributes 0.159264 F to the mean gain,
and ordinary savings contribute 0.436534 F. The food gain itself remains unresolved.

The midpoint has a suggestive acquisition increase of 0.812500 ±0.331204 captures and 0.824219 ±0.306736
replenished packets; neither clears the descriptive three-SE level. From generation 4 to 8, captures change
−0.486328 ±0.297075 and fitness −0.121221 ±0.143847 while costs fall another 119.033543 ±11.122030. This does
not establish a continuing acquisition trend or justify substituting the midpoint for the final endpoint.

## Retention and transfer

POOL loses **1.861328 ±0.216181 captures**, retaining 88.39% by the ratio of means. Persistent pursuit and
longer cue gaps retain 94.79% and 94.67%; their absolute losses remain unresolved at three SE. All three
paired 90% retention margins remain unresolved: POOL −0.258398 ±0.204970, persistent +0.283398 ±0.131994,
and longer gaps +0.193555 ±0.106867. Thus POOL's absolute loss is clear, but a loss exceeding 10% is not
established by this diagnostic. Retention percentages are point estimates without ratio SE.

Reserved transfer loses **1.382813 ±0.267868 total captures** and **0.929688 ±0.216024 replenished packets**.
From generation 4 to 8 it loses another 0.857422 ±0.255778 captures and 0.720703 ±0.206763 replenished packets.
Final-minus-start food income contributes −0.675201 F, partly offset by 0.385475 F of savings. This is a clear
food loss even though the fitness difference is unresolved at three SE. The revealed combination is now
development evidence for future studies; it cannot continue to be described as unseen after study selection
uses these results.

These outcomes support separating inherited reuse from newly accumulated capability. The ancestor already
uses depletion-dependent sensory cues profitably, as the preceding modulation study shows. This continuation
has not demonstrated an additional food-acquisition primitive that retains or broadens that competence.
One short run does not establish a substrate ceiling or that further evolution cannot succeed.

## Execution and verification

All **28,214 research +8 startup =28,222 calls** complete. Search accounts for 20,534 research calls and
confirmation for 7,680. All 15 confirmation batches have status zero throughout, with no extinction or guard.
Runtime uses **1724.714517 CPU /857.732643 wall seconds**: search 1277.698322 CPU and confirmation 447.016195 CPU.
Peak owned RSS is **359.394531 MiB**. Both owned process groups and every recorded worker identity are cleared.
There is no scientific retry, cap extension, reduced evaluation matrix or post-launch scientific-source edit.

The registered package allowance is 5400 CPU/3600 wall seconds, including 120 CPU/120 wall reserved for
preparation and terminal work; runtime caps are 5280/3480. Conservatively allocating the entire reserve gives
1844.714517 CPU/977.732643 wall seconds against those package limits. Resource logs retain actual metered
preparation, analysis and audit work. One two-thread worker runs at a time, with a 4 GiB RSS stop, 8 GiB address
space bound and 4 GiB host reserve. No paid compute is used.

A launcher preflight initially raises `KeyError: pid_namespace` before any attempt, build or life. The original
release and failure record remain in `prelaunch_launcher_history/`. A separate launcher binds the namespace
and published inputs, then invokes the unchanged frozen monitor. The one scientific attempt completes. This
zero-call correction is not concealed or counted as a research retry.

Independent scalar accounting verifies all **821,760 ledger values**, 38,400 fast constant hash words,
23,040 scored values, and **20,979 summary numeric values**, including costs, source counts, stock/FIFO
conservation, paired SE and retention margins. The fast hashes are schema checks, not trajectory proofs.
Separate startup full/fast truth checks cover the complete 107-column ledger and five full hashes.
Recorded-operation replay reproduces **1792 offspring, 3584 point additions and all 32 midpoint/final rows**;
it reconstructs saved genetic operations rather than redrawing RNG. The audit uses 2.74 CPU seconds and
runs no new lives or builds. See `reviews/independent_accounting.json` and `native_replay_result.json`.

Full absolute and paired tables and fitness decompositions are in [TABLES.md](TABLES.md); all eight physical
cost components are retained in [summary.json](summary.json).
Raw native batches remain separate from scored returns. This exploratory study makes no formal section 0.4
admission claim and no claim of memory, learned refill periods, visit order or superiority to handwritten algorithms.

Protocol: `0b0fd4e0fd2392f3f03f7f6bf5822714d64ce312aa20887770d0338c9c452da1`.
Summary: `f819c039ddb9a8751148b73afb4bdb7445fe7a5ca2d755bf7118490b0598c554`.
Prospective publication: `742f5e75ff9d8564457d662a624be6dae26b4306`.
