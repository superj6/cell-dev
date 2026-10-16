**Deeper continuation registered (2026-10-16).** The full 32-row Pareto population now receives eight more
generations with 32 initial and 32 recheck lives per candidate, retaining the existing acquisition objectives,
world allocation, physical prices and genetic operators. This follows the completed evidence that useful
variation survives and small cached samples rank reporting genomes poorly. It tests combined depth and
denser evaluation, not the causal superiority of either change.

After search, a separate 32-life panel in each training world selects one final survivor by weakest relative
acquisition, weighted ordinary fitness, then ID. Its genome is frozen before 512 fresh lives in six worlds,
alongside unchanged AO and development-selected G8/Pareto4 ancestors. The new reserved case has four
capacity-three patches, placement radii 2.5–4.5 and refill periods 60/180. Initial stock and replenished
harvest remain separate. Historical reporting endpoints are not replaced.

Maximum **97,342 calls** (97,334 research +8 startup), under **10,800 CPU /7,200 wall seconds**, including
180 seconds preparation/terminal allowance. One two-thread worker at a time, 4 GiB owned RSS, 8 GiB address
space and 4 GiB host-memory reserve. The native seed and two fresh panel blocks pass collision review.
Source checks, 14 supplied-data tests and exact-input review precede publication and runtime release.
Evidence: `results/resource_patch_depth_20261015/`. This registration records no new organism outcome.
Reassess cumulative acquisition and retention after this bounded continuation, then reconsider a richer
accessible interaction rather than automatically making another selection tweak.
