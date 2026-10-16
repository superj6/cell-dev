# ABI 6 draft source-impact and validation map

This is an implementation map for [DRAFT_CONTRACT.md](DRAFT_CONTRACT.md), not code changes or a run release.
Only the new files in this output directory have been written. Preserve all published/pinned historical sources.

| Maintained surface | Proposed change and compatibility boundary |
|---|---|
| `src/life/spec.py` | Append five World fields, V6 world82/ledger107, streams31–33 and exact source/field/placement helpers. Freeze `WORLD_KEYS_V5` at the old boundary instead of allowing its current `ALL_WORLD_KEYS` alias to grow. Add the explicit resource preset, validation and column meanings. Keep genome875, program/body/layout/flags and V2 default unchanged. |
| `src/life/kernel.c` | Set native ABI6 sizes. Add a separate fixed Patch[4] world-state array, source timeline, left-limit stock snapshot and immediate harvest eligibility; do not enlarge/reinterpret the legacy two-blob state. Integrate into init/world_to/group_begin/catch_click/close/receptor acceptance. Source bookkeeping is external to cells. Preserve all old branches and record streams. |
| `src/life/reference.py` | Mirror operations and arithmetic order literally; V6 internal ledger/default padding with V2–V5 output projection. Preserve integer source/stock counters and all source/click/window ties. Expose observer patch state without adding gene inputs. |
| `src/life/build.py` | Native KERNEL becomes V6; accept explicit V6 calls, neutral-pad older worlds, allocate new ledgers and reverse appended close folds for old full hashes. No genome transformation is needed for V3–V6. Preserve ABI2 fast projection and make no replay claim about constant fast hashes. |
| `src/life/evaluate.py`, `src/life/analysis.py`, `src/life/readouts.py` | Add explicit ABI6 selection/loading and named patch readouts wherever version lists are fixed. Reuse ordinary harvest/miss scoring and production extinction surcharge. Never treat a raw click or empty contact as food. Include per-slot conservation and cost reconstruction in downstream validation. |
| `src/life/probe.py` | Support the explicit ABI and observer field where applicable. If a later study needs C visit/dwell/return timing, specify a real observer trace and test it before claiming those readouts; the minimal ABI contract does not promise a new C trace table. |
| `src/checkpoint.py`, `src/run.py`, caller/config/import code | Check source/kernel/version identity rather than bypassing it. Historical golden lives should keep their old caller bytes/hashes; add a separate V6 golden fixture. Record any population migration explicitly with unchanged genotype/population bytes and new source identity. No lineage or endpoint is selected by this draft. |
| `results/atlas/play/lifesim.js` | Add explicit ABI6 patch state/event branch and ledger107. Match full hash/event/numeric order, constant lifetime receptor bound, group snapshots and terminal conservation. Auto mode only for patches; reject dragging/adding/removing/stock edits. Existing ABI3/4/5 supported subset remains unchanged. |
| Maintained viewer/export/checker helpers | Add an automatic patch presentation with stock/supply/harvest/empty/geometric labels and observer-only period overlays. Export fixed genomes/cases and full C truth; compare all107 ledgers, five hashes and spike rasters. Retain C fate logs; do not claim a JS fate-table API. Rendering cannot influence source advancement or physics. |
| `docs/LIFE_ABI.md`, focused tests | Publish the reviewed exact contract only with implementation. Add tests listed below; do not modify old expected bytes to accommodate a regression. |

The first implementation should support count1–4 as a single tested world mode. Scientific use initially remains
count3. This costs four small fixed arrays and four-slot ledger blocks, while avoiding a new ABI merely to test
count4 composition. The extra source law has two rates with fixed equal prior, not an extensible object engine.
Alternative continuous inflow is deferred: fractional stock, partial-packet capture and floating conservation
would add semantics without improving the first causal interaction. Arbitrary placement with rejection is also
deferred: the rotated variable-radius ring gives exact bounded work and guaranteed disjoint capture disks.

Minimum engineering matrix, to be inventoried and budgeted before execution:

1. Pure validation/helpers: count0–4, inactive/neutral values, invalid task/visibility/blob combinations, length
   and arrival-work bounds, rate independence stream keys, geometry, stock-to-field law and full candidate bound.
2. Supply/harvest fixtures: initial two packets, immediate repeated depletion, empty versus geometric misses,
   capped supply/spill, FIFO initial/refill attribution across t_open, no source reset on harvest, no respawn, and all-fast/all-slow/equal-period cases. Bodies are
   execution fixtures, with no success gate. An injected inconsistent counter must flag a mismatch in each backend.
3. Boundaries: source before/at/after clicks, two sources tied, multiple clicks in a timestamp group, receptor
   candidates on both sides of a harvest, queued delivery after depletion, source/click exactly at accounting
   opening, pre-window depletion, no overlap with the window, actual endpoint exclusion, guard and extinction.
4. C full/fast ledger agreement, C/Python full bits and observer state on fixed engineering cases; JS full common
   subset truth with stepped/one-shot replay, render polling invariance and all five hashes plus spike raster.
   Keep every seed/call and failure. Check all active slots and unused-slot zeros.
5. Existing ABI2/3/4/5 fixtures unchanged, including delayed matching: old caller shapes and full hashes, neutral
   V6 projection, thread/scheduler determinism, t0 translation and checkpoint/resume/import identities. Tests must
   include patch mode under both supported C schedulers and the JS supported subset explicitly.
6. Null/replay controller harness equivalence before an information experiment, with ordinary action/receptor
   charges and no true patch/rate/stock/clock input. A supplied-stream/UI mock is not physical replay or a browser
   rendering test. Actual saved-data accounting should reconstruct the source/supply/harvest/spill equations.

No testing budget or scientific cases are selected here. A later engineering release needs exact fixtures,
calls across every backend, source pins, process/resource caps and a preserved first-attempt receipt. The root
can review and delegate this already-authorized local work after terminal publication; this draft adds no new
user approval boundary.
