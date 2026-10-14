### J. Contribution of duplicated-origin genes (prepared 2026-10-14, before G completes)

J asks whether an individual gene descended from a duplication contributes to the performance of either fixed G
endpoint. It uses the existing deletion operator as a measurement intervention, with no new organism behavior,
channel, clock, world response, price or ABI change. It is separate from the G comparison of mutation policies.

The two endpoints are fixed as each G run's final population rank 0 at generation 16 (seeds 51089 and 51090).
They are inspected only after G completes. Full recorded crossover, point mutation, duplication and deletion
operations must replay to the exact checkpoint population and innovation-origin registry. An eligible gene has
an active slot and origin ID >=16. Every such gene is included, even if its outgoing weights are zero; none is
chosen by fitness, morphology, expression or presumed importance. No active duplicate-origin genes means that
endpoint's branch is reported as not applicable, with no replacement endpoint or alternative intervention.

For each eligible gene, `Layout.delete` clears its active bit and silences weights read from inactive genes.
Kernel packing masks its own regulation/state and its outgoing regulatory and phenotype effects. The resulting
runtime table must match a canonical copy with only that active bit cleared. All single-gene knockout genomes,
raw hashes, runtime-table hashes, slots and origin IDs are frozen before any scoring. The knockout acts from birth
in every cell, so it can change development, morphology and later computation together. Gene deletion has no
separate direct fitness reward; the ordinary task ledger and prices determine its effect.

Stage 1 measures each applicable intact endpoint and every eligible single-gene knockout on the same 512 fresh
seeds 51,980,000 through 51,980,511 (block98). Every life uses fast POOL (d0=.5, d_min=.25, sigma=.4, lam_s=4), T1024,
with full-life accounting and no fork. Report all paired intact-minus-knockout effects, their SEs, complete costs,
income and guard/extinction penalties. Negative and unresolved losses remain in the result.

For each applicable endpoint, choose the gene with the largest mean paired intact-minus-knockout loss; an exact
tie chooses the smallest slot. This choice is made regardless of sign, including when all initial losses are
negative or zero. Freeze the choice and candidate-row mapping before stage 2. The chosen knockout and its intact
endpoint then share another 512 fresh seeds 51,990,000 through 51,990,511 (block99), with the identical T1024 world.
All confirmation roles share these seeds, and both endpoint confirmations are retained. No candidate or life
extension follows the outcome. There is no genotype deduplication; each prescribed role is scored explicitly.

Fresh confirmation supplies the primary evidence after selecting among genes. A positive loss beyond 3 SE and
above 0.5 F is flagged descriptively; the original 8-of-20-run G-use criterion is not evaluated with two endpoints.
A confirmed loss establishes that this duplicated-origin gene contributes to this fixed genotype's whole-life
performance. The gene may replace an original gene or share an existing role. It does not establish expanded
computation, an adult circuit or a new algorithm. An individual null effect does not prove zero function or exclude
redundancy/epistasis. Life-level SE does not estimate uncertainty across independent evolutionary searches.

The upper bound is 16 eligible genes per endpoint: deletion can replace original slots, so the limit is not eight.
Stage 1 therefore has at most 32 knockout plus two intact rows (17,408 lives). Stage 2 has at most two selected
knockout plus two intact rows (2,048 lives). Total research lives are at most 19,456; exact counts are recorded from
the frozen candidate set. Empty branches incur no research lives. Numerical-identity startup golden checks are
separate from research counts and included in CPU accounting. Preparation uses pure genome operations, synthetic
scores and mocked workers; it performs no scientific or validation life simulations.

The cumulative resource cap is 7,200 worker CPU-seconds with two simulation threads, including imports, startup
checks, both stages and incomplete rows. The external monitor stops at 7,188 CPU-seconds, sends TERM, then KILL
after at most two wall seconds, with worker CPU limits and parent-death termination as independent safeguards.
There is no budget extension or automatic restart/reset. The monitor waits until both H and I are complete with
empty active/queued records; this also follows G completion. Their scientific outcomes do not alter J. Dependency
protocols and monitors are pinned at readiness after root review. An abnormal predecessor stop requires operational
review, and does not license a silent restart. All raw rows, decisions, negative results and any incomplete-work
receipt are preserved. Invalid capacity/accounting mismatches stop the study; penalized guards stay in every
fitness comparison.
