# S: spending more life samples per selection, with fewer generations

This prospective comparison tests whether doubling the number of life samples used by
selection improves final fixed-genotype fitness enough to compensate for halving the
number of generations. It follows the completed D/G/L selection diagnostic, which found
frequent parent and leader changes after rechecking. That diagnostic does not establish
that larger scoring budgets improve evolution. Both founders and run seeds below are
fixed regardless of the still-unread P outcomes.

S uses the unchanged local asynchronous biology, world, genome ABI and ordinary sexual
mutation policy. There is no new behavior, global channel, clock, population-responsive
world, or hand-built-body admission test. No compute is rented.

## Fixed policies and founders

| Search pair | D founder | P policy | S policy |
| --- | --- | --- | --- |
| 52091 | D51089 generation 16, rank 0 | 16 generations, 3 initial + 4 recheck lives | 8 generations, 6 initial + 8 recheck lives |
| 52092 | D51090 generation 16, rank 0 | 16 generations, 3 initial + 4 recheck lives | 8 generations, 6 initial + 8 recheck lives |

Both policies have 32 parents and 224 offspring per generation and recheck the initial
best 64 candidates. All parents are reevaluated. The pooled score selects 32 parents;
there is no protected founder, historical-best retention, endpoint replacement or
validation-based reselection. S's only policy changes are life counts and generation
count. Control labels and output/input paths change for bookkeeping.

Each S initialization uses exactly the same 32 raw genomes, recorded point mutations,
and before/after genetics RNG states as its paired P initialization. This is checked by
pure production setup/fill before release; no lives are simulated. Identical starts do
not make later evolutionary trajectories identical once selection differs.

Each branch spends 16,384 selection genome-lives:

- P: 16 × (256 × 3 + 64 × 4).
- S: 8 × (256 × 6 + 64 × 8).

This is an equal selection-life comparison. It is not an equal CPU comparison. S uses
the first eight duration draws; P uses sixteen, so their realized duration mixture and
duration-adjusted selection exposure can differ. Actual monitored CPU and both duration
lists will be reported. Each S branch has 18,944 T1024-equivalent selection lives;
P52091 has 20,480 and P52092 has 17,920. The study does not claim to isolate scoring quality from the
necessary reduction in evolutionary generations.

## References freeze before either S search

After R is complete and its queue is empty, the monitor first runs a pure reference
freezing phase under the same CPU cap. That phase requires all of P to be complete and
uses the previously reviewed, frozen P offline analyzer to audit both P searches and
confirmation, including source pins, exact initialization, checkpoint identity and
recorded genetic replay. It executes no numerical golden checks or research lives.

The exact P generation-16 rank-zero endpoints, their checkpoints/lineage/configs and
completed audit receipt, plus both D founders, are copied and hashed together in an
atomic `references/` directory. A partial freeze or changed input fails closed. The
monitor verifies that receipt before starting either S search and again before every
later phase and final completion. No S search starts while either P endpoint is missing.

## Prospective namespaces and life counts

The run seeds intentionally remain 52091 and 52092. Initial and recheck life IDs overlap
P where the unchanged production seed function gives the same generation/life index.
Some P recheck IDs become S initial IDs; shared validation and final diagnostic IDs are
also intentional. The independent namespace receipt enumerates those exact overlaps,
the new hashed IDs, every prior/prepared registration through R, and the fresh block.
No overlap with another study or with confirmation is permitted.

Fresh confirmation uses block 105: 52,050,000 through 52,050,255. Each ID is deliberately
shared across all six genotypes and all three durations. No new smoke-test IDs are used.
Existing startup golden checks reuse their established seed 11 and remain inside the
CPU cap, separately from the registered research-life count.

S plans 37,484 research genome-lives:

- 32,768 selection lives across the two searches.
- 96 periodic validation lives: generations 0, 4 and 7 × 16 × two searches.
- 12 tiny final diagnostic lives: three two-life evaluations × two searches.
- 4,608 fresh confirmation lives: six fixed roles × three durations × 256 seeds.

`heldout=[]` suppresses held-out simulations. Four tiny diagnostic lives are half length.
Reference auditing and initialization generation simulate zero lives.

## Fixed confirmation and contrasts

All six raw genomes are frozen before the first confirmation score, in this order:
D51089, D51090, P52091 final rank 0, P52092 final rank 0, S52091 final rank 0, and S52092
final rank 0. S endpoints must come from their complete generation-8 checkpoint.
Every role is measured at T=768, 1024 and 1536 in the unchanged fast-conduction POOL
world. All full ledger columns, guarded/extinct scores, raw row hashes, status counts,
morphology and accounting decomposition are retained.

The two primary paired contrasts are S52091 − P52091 and S52092 − P52092. Four secondary
contrasts retain S52091 − D51089, S52092 − D51090, P52091 − D51089 and P52092 − D51090.
Each comparison first averages its three duration differences within each shared life
seed, then reports the mean and sample SE over 256 seed clusters. A positive primary
mean above 3 SE and at least 0.5 F is a descriptive threshold. Both endpoints, all
contrasts, negative effects and unresolved outcomes are retained; there is no extension
or endpoint selection based on confirmation. Individual-duration results are secondary.

These life-level SEs describe the fixed endpoint genotypes. With only two fixed founder
and run-seed pairs, they do not measure uncertainty across evolutionary searches or
general policy reliability. The policies share initial genomes and some life IDs;
their outcomes are paired, not independent replicates.

## Resource and completion rule

The fixed ceiling is 14,400 cumulative CPU-seconds, with a parent stop threshold of
14,380 seconds. It includes the monitor's own/waiting CPU, pure reference auditing,
workers/descendants, engine startup checks and confirmation. At most four search
threads run: two searches with two threads each. Confirmation has two threads. CPU
placement stays within CPUs 0–11. S waits for completed, empty R; that dependency chain
also places S after P and Q. Exact parent binding, remaining CPU limits, bounded
TERM-then-group-KILL cleanup and immutable source/readiness pins are required.

Any missing P or S endpoint, incomplete reference audit, source change, failed search,
missing confirmation role, invalid capacity/accounting state or exhausted cap makes the
whole comparison incomplete. No partial primary claim, replacement, restart, budget
reset, new rental or extension is authorized. Research simulations start only after
root review, public registration and release.
