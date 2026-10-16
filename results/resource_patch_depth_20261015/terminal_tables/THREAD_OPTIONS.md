# Four local threads for a future study

**Recommendation:** four C life workers are a reasonable next-study setting, after one small ABI6 parity and
resource check. Source structure strongly supports unchanged per-life results, but current evidence does not
establish actual four-thread ABI6 execution or negligible memory growth. Leave this registered two-thread run
unchanged.

The C entry point uses OpenMP `parallel for schedule(dynamic,1) num_threads(threads)` over independent lives.
Each `run_one` allocates its own mutable `Ctx`, reads shared immutable inputs, and writes a disjoint output row.
There is no cross-life floating-point reduction or shared random stream; the critical section only records an
allocation/error return code. Canonical event ordering remains inside each life. Compilation uses
`-ffp-contract=off` and no fast-math. Python aggregates the returned rows in a fixed order after C finishes.
See [kernel loop](../../../src/life/kernel.c#L2677), [private context](../../../src/life/kernel.c#L2513),
[build adapter](../../../src/life/build.py#L350), and [evaluator](../../../src/life/evaluate.py#L217).

Existing tests compare ledgers, hashes and logs under different batches and requested thread counts 1–4
([BELL/CATCH tests](../../../tests/test_life_time.py#L240)); visibility explicitly compares one and two
threads. However, the latest ABI6 regression monitor set `OMP_THREAD_LIMIT=2`, so a test requesting four
could only obtain at most two. The specific [patch/reference tests](../../../tests/test_abi6_kernel_reference.py)
use one thread. Those results support the implementation but are not a measured four-thread patch guarantee.

Memory should grow by extra concurrent life contexts, queues, inboxes, thread stacks and allocator retention;
it should not multiply the whole Python process or the shared batch/output tables by two. These temporary
allocations depend on realized development and activity, so “no meaningful growth” needs measurement. At this
review's read-only snapshot, allowed CPU affinity was **0–13**, load averages were **3.69/3.40/2.94**, and
`MemAvailable` was **19.79 GiB**. The visible leaf cgroup had `memory.max=max`; CPU quota files were unavailable,
so affinity alone is not a quota guarantee. This snapshot suggests headroom, not a promise about future load.

One important configuration detail: `cfg.threads` also calls `torch.set_num_threads` in
[evolve_life](../../../src/evolve.py#L469). Changing it is broader than C parallelism. Prefer a fixed four-worker
**kernel share with the existing PyTorch setting retained** for the initial comparison; `LifeEvaluator.kernel_threads`
already supports a separate share. A future monitor must explicitly permit four workers through affinity and
`OMP_THREAD_LIMIT`, while retaining one BLAS thread and existing RSS/address-space/host-headroom limits.
The current monitor deliberately strips the share override and enforces two threads. Its sources and checkpoint
configuration must remain frozen; a future setup must declare its new execution settings before release.

**Small meaningful check:** use eight fixed ABI6 lives: two existing genomes × two existing engineering seeds
× trained patches/reserved-capacity3, at the unchanged full duration. Run that same panel with full and fast
kernels at two and four actual OpenMP workers: **32 engineering life executions in four batch calls**. Compare
all 107 ledger values bitwise after restoring row order, all five full-mode hashes, and derived production F.
Fast hashes are constants and supply no parity evidence. Use no raster/fate logging, identical cached binaries,
and a fixed reverse row order in the four-thread batches. Record process CPU, wall time and peak RSS in fresh
processes; check that the OpenMP limit/affinity permit four workers and observe four threads doing CPU work.

If parity passes and measured memory remains comfortably inside the existing caps, use four kernel workers
for the next bounded study. The timing is a rough throughput check, not a scaling benchmark or promise of twice
the speed; more threads may reduce wall time without reducing CPU charged to the study. No simulation, build,
runtime edit, or extra compute was performed for this recommendation.
