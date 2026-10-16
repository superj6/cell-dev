# Persistent resource patches: C/Python implementation impact

Source-only review of production commit `26ec466e1cd1430ae0f82b0816666328036d4542` (2026-10-15).
No production edits, builds, lives or random draws. ABI6 is proposed; the patch contract owns the final
field list, physical law and record words. The reviewed [draft](DRAFT_CONTRACT.md) uses integer packet
arrivals and `patch_count`; final contract SHA256 is
`15c3f7d7006bd274c2e7c9c06d6a89bd264dd8128be8579286dda70c1d740d77`.
This note identifies implementation seams, not a new release. No C/reference semantic blocker was found.

## Minimal coherent scope

Use the draft's appended `patch_count` (zero disabled, 1–4 enabled) within CATCH (`world_kind=1`), mutually
exclusive with delayed matching and visibility. Keep `task_mode=0` and its durations neutral in patch worlds. Existing
`task_mode` checks are boolean throughout the kernel/reference/scorer; overloading it with value 2 would
activate matching semantics. A new world kind would instead require changes to every CATCH predicate,
including plane cues, candidate generation, mechanics and evaluator classification. Neither is needed.

Reuse the existing local receptor, hotspot press, traction, force decay, drag and all physical charges.
Patch stock and coordinates belong to the world accountant, never a cell input. No genome, program,
knob, GRN-input, lattice, initial-body, communication or scheduler redesign is required. Keep old branches
intact and dispatch to patch helpers only when enabled; do not refactor legacy arithmetic while adding it.

## Layout and Python boundary

Current caller shapes are:

| ABI | World | Ledger | Genome | Program | Hashes |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | 41 | 35 | 793 | 119 | 4 |
| 3 | 66 | 57 | 875 | 129 | 5 |
| 4 | 70 | 58 | 875 | 129 | 5 |
| 5 | 77 | 70 | 875 | 129 | 5 |

ABI6 appends `patch_count`, `patch_capacity`, `patch_refill_fast`, `patch_refill_slow`, `patch_landmark`
at indices 77–81 (`WORLD_SIZE=82`) and observer ledger fields at index 70. The final ledger has 107
columns: initial-harvest provenance99–102 and refill-harvest provenance103–106 follow geometric misses98. Keep the ABI3–5 genome
layout of 875 parameters, 16 regulatory slots, 25 inputs and 23 knobs; five hash families; fate integer
width 7 and float width 18. `spec.CURRENT` stays V2; BODY-1 layouts continue to default to V3.

- **`src/life/spec.py`:** append `World` defaults, freeze `WORLD_KEYS_V5` at the new field boundary
  (it currently equals `ALL_WORLD_KEYS`), then define V6 world/ledger/stream sets and instantiate `V6`.
  Extend `Abi.__init__`, integer-field lists, validation and explicit-version rejection. Give disabled
  patch fields one neutral representation so old calls cannot silently carry enabled patches. Add an
  explicit preset only after its numerical parameters are agreed. Existing stream IDs 1–30 stay fixed;
  new patch streams start after 30. Counter keys and arithmetic order must be contractual.
- **`src/life/build.py`:** set `KERNEL=V6`, accept V6 in `_abi`, update documented shapes. `_worlds`
  validates under the requested caller ABI then packs the full kernel vector; this already supplies
  neutral newer defaults. Existing `run` projection truncates the ledger and undoes appended close
  folds for full-mode `all`; retain ABI2's special fast-hash convention. No C-call signature change is
  needed if only world/ledger lengths grow. Update `life_sizes` and native version accordingly. All explicit
  ABI2/3/4/5 arrays and full hashes must remain identical, not merely local cell behavior.
- **`src/life/reference.py`:** add V6 alias, `_LI`, ledger allocation, `_FLOAT_KEYS`/`_INT_KEYS`,
  `_Life` world-index source, `_V6_DEFAULTS` and `_prepare` padding. Retain caller-specific close-fold
  length and returned shapes. Mirror the patch accountant independently in the same operation order.
- **`src/life/evaluate.py`:** add explicit `life.abi=6` mapping and accept the unchanged genome fields.
  `columns` already enumerates the selected ABI ledger dynamically. Keep native F, invalid-row handling,
  extinction surcharge, seed purposes, fixed-order aggregation and ordinary selection unchanged.
  No new `LifeEval` fields are needed for selection; report patch units from retained native columns.

## C world and reference-accountant seams

| C location | Python reference counterpart | Patch responsibility |
| --- | --- | --- |
| `Ctx`, world/ledger enums; `world_ok`; `run_one` | `_Accountant` state; `_Life.__init__`; `spec` validation | Fixed-size/bounded patch state, parameters, rate bound and validation |
| `catch_start` (1527) | `_catch_start` (236) | Initialize fixed world coordinates and stocks before initial cell records; no legacy replacement timers |
| `world_to` (1485) | `world_to` (449) | Patch-world advance only if the physical law has events; preserve strict-below-time ordering |
| `catch_click` (1565) | `_click` / patch-specific helper near 518 | Select physical hit, limit actual harvest by available stock, book income/miss, stage writes |
| `catch_candidate` (1776) | `_rcand` near 593 | Sum patch receptor contributions in fixed patch-ID order using existing thinning and delayed delivery |
| `catch_sample` (1506) | `sample` (474) | Observer distances/availability; define whether nearest patch or nearest harvestable patch, including none |
| `group_begin` / `group_end` (1968/1972) | `group` near 618 | Left-limit scene, deterministic same-time harvest reservation and final stock commit |
| `close_life` (2021) | `close` (825) | Advance to actual endpoint, resource conservation, new ledger values, terminal world record then close folds |

Line numbers describe this pinned source, not future edits. Use a separate fixed `Patch[4]` array rather than stretching the two legacy `Blob` slots and deferred
placement queue. No patch interaction invokes `defer_place`: harvesting changes stock, not coordinates.
The source timeline fits `world_to` with its declared positive-period and arrival-count bounds; it needs
no new cell scheduler or events in the cell heap.

The draft resolves the main cross-engine details as follows:

1. **Integer resource state.** Initialize fixed coordinates/full stock before cell births. Source times are
   `first + double(index)*period`, never repeated addition. Process only times strictly below the query,
   breaking source ties by slot. Query/sampling/rendering never alters source anchors, phases or counters.
2. **Same-time clicks and pings.** Freeze `stock_left` at group entry for all candidate rates. Harvest
   decrements available stock immediately in canonical record order; later presses cannot spend the same
   packet. Pending receptor deliveries and all cell/motor states survive depletion. An exact-time source
   follows that timestamp's actions. No partial packets: each success removes one, otherwise it misses.
3. **Fixed thinning bound.** Set patch-mode `lam_max=lam_bg+lam_s*double(patch_count)` before any births,
   validate it against 1024, and retain existing candidate/thinning streams. Add components in slot order,
   with the exact draft nesting for amplitude, halo and `lam_s`. Do not reschedule candidates on depletion.
4. **Windows and endpoints.** Invoke a lazy opening-stock hook before the first source/action with
   timestamp at or above opening. `world_to(t)` must capture this boundary before crossing it, not afterward.
   Also handle no counted events and closing before/at opening (all appended columns zero). Sources continue
   through T after extinction; guards stop them at the actual endpoint. Endpoint-time sources are excluded.
5. **Hashes.** Streams31–33 and records18–21 are separate from legacy/matching. Fold initialization slots
   in order, source outcomes with the current arrival index, patch click20 before ordinary click11, and
   terminal stock21 before ledger close folds. Neutral worlds use none. Fast hashes remain constants.

### Proposed shared C/reference state and observer interface

These names permit root-owned probe changes without depending on private simulation control:

| Reference API/state | C analogue | Contract |
| --- | --- | --- |
| `self.patches`, exactly four `_Patch` records | `Patch patch[4]` | Public observer fields `x,y,period,first,next,arrival_index,stock`; inactive entries canonical zero; `initial_remaining` tracks unconsumed t0 stock |
| `self.patch_left`, four integers | `patch_left[4]` | Snapshot used exclusively for the current group's receptor field |
| `_patch_start()` | `patch_start(Ctx*)` | Initial geometry, stock and source timing; records18; called instead of legacy blob setup |
| `_patch_window_before(t)` | `patch_window_before(Ctx*,t)` | One-time opening snapshot before the first eligible mutation; never a cell event |
| `_patch_source(i)` | `patch_source(Ctx*,i)` | One scheduled source event, counters/spill/stock/hash, then next timestamp |
| `_patch_click(t,counted)` | `patch_click(Ctx*,t)` | Actual-stock eligibility and one-packet depletion, record20 then11; no source restart |
| `_patch_rate(px,py)` returns `(rate,signal)` | `patch_rate(...)` | Pure field from `patch_left`; rate begins at background, signal at zero, each adds the same component in slot order; signal is observer metadata only |
| `_patch_nearest(t)` returns `(x,y)` | nearest-patch loop in `catch_sample` | Geometry-only nearest center from analytic dot position, including empty patches; ties favor lowest slot |
| `_patch_finish(t_end)` | `patch_close(Ctx*,t_end)` | Opening fallback, endpoint stock, exact identities/provenance checks and terminal records |
| `_fold_world(words)` | existing `fold(world/all,...)` | Sole event observer hook; Python records decode18–21 without modifying stock or schedule |

Source-event processing occurs in `world_to`; `group`/`group_begin` then captures the opening boundary and
copies current stock into `patch_left` before dispatching records. A nearest-center observer query does not
advance time. `_TAcct.group` may call `world_to(t)` twice because processing strictly earlier sources is
idempotent, but must not reset `patch_left` inside `_rcand` or after a click. Root should decode provenance
from record20 origin (0 miss, 1 initial, 2 refill), record21 initial remainder and these state fields; it must not infer it from stock magnitude. This is an
interface proposal to finalize alongside the contract, not an implemented API.

## Accounting, observation and fitness

The draft preserves `clicks`/`misses` as physical press counters and defines `captures=sum(patch_harvest)`
in enabled patch worlds. `b2_clicks`, `respawns`, low-light and matching counters remain zero. Per-slot
source/supply/spill/harvest/empty/open/end fields and geometric misses reconstruct exact packet conservation.
Provenance counters refer to the actual t0 endowment, with initial packets consumed first; `t_open` never
relabels packets. Switching/revisit diagnostics never enter income as separate bonuses.

`spec.Abi.column_cost`, C `close_life` and reference `close` must agree with event charges. Neutral
`b2_value` avoids interpreting patch presses as wrong-choice costs. `R_cap` is the price per packet. An explicit patch branch in
`fitness` can reconstruct `R_cap*sum(patch_harvest)`; the current nonmatching branch retains stored income
and would not reprice a changed harvest price. Declare this repricing behavior explicitly. Preserve all mode0 and matching
branches. `LifeEvaluator.columns` preserves raw native F and separately applies its existing extinction
surcharge; report both and keep legitimate guards/extinction in study accounting.

`src/life/probe.py` needs more than a version whitelist. `_TAcct._fold_world`, `_observed_target`,
`_rcand`, `sample` and `trace` currently assume legacy/matching blobs, one initial blob0 placement and
outcome labels `capture`/`blob1`. Add observer-only patch events/stock snapshots and correct rate logging;
avoid fabricated target coordinates or a placement-table `iloc[0]` failure. Observers must not mutate
stock. Append optional trace data rather than changing old trace columns. Refuse old single-target
tuning/steering summaries when their meaning is undefined. `trace_kernel` remains partial: its native
raster/fate arrays do not provide full world trajectories.

`src/life/readouts.py` must admit V6 in validation and trace metadata dispatch, retain legacy matching
count checks (zero in patch mode), and add patch conservation checks. Let matching summaries accept V6
matching rows if supported, but never label patch rows as matching correctness. Study reports can use
the new ledger directly without changing evolution's generic score schema.

## Determinism, ownership and bounded verification

`src/checkpoint.py` pins all production Python sources, the kernel, compiler flags, both compiled hashes,
config, numerical libraries and the existing ABI3 golden. An ABI6 source change correctly invalidates an
old exact resume, even if genomes and legacy trajectories remain identical. Import an archived full ordered
population into a newly declared continuation; do not weaken checkpoint validation or rewrite old identity
receipts. No checkpoint format, genotype loader, crossover/mutation or seed-purpose change is necessary.
`build` caches by source+flags; use fresh processes after code changes because loaded libraries are memoized.
Do not call `numerical_identity()` during source preparation: it builds, runs two golden lives and draws
a numerical-identity noise vector.

Root's assigned division: this reviewer owns `kernel.c`, `reference.py` and their focused C/reference tests;
root owns `spec.py`, `build.py`, `evaluate.py`, `analysis.py`, `probe.py`, `readouts.py`, checkpoint fixtures
and ABI docs; delayed_match_js owns `results/atlas/play/lifesim.js`, viewer/export/replay and JS tests;
circuit_options independently supplies semantic fixtures/review. New world/ledger indices, streams, hash words, geometry, refill/harvest arithmetic and event order
are shared contract inputs, not decisions each owner makes independently. Existing browser scope limits
remain explicit. Do not regenerate archived bodies, truth files, viewers or completed-study sources.

After the final contract and root implementation release, a small counted validation matrix should cover
raw validation and layout/padding; stocked/depleted harvest, source arrivals/spill and provenance; same-time contention and pending pings; shifted
`t0`/fractional `t_open`; guard/extinction closure; heap/window and C full/fast/Python agreement; JS full
ledger/hash/spike replay and render-chunk invariance. Reuse retained ABI2/3 byte fixtures and existing
ABI4/5 regression evidence, adding neutral-V6 projection checks. These verify engineering semantics,
not information payoff, developmental accessibility or an evolutionary capability. No tests ran here.

## Key reviewed source pins

| File | SHA256 |
| --- | --- |
| `src/life/spec.py` | `8a74b75aa7c06be2f25fd3a012f56fe78c112354bc8311e0075f4db41ee5fbb8` |
| `src/life/kernel.c` | `20f7d3ee288e62bd3b65bc8c8c151866f60cfe86b46facc317a6695433d7861d` |
| `src/life/reference.py` | `aa11783a8956937c8b323b77394e0be9816a9c877f4395db70ab5a3b6f2e732c` |
| `src/life/build.py` | `718ab8540c01fe7109f06e009aeb5582907996a3ae69bf5171236f2ceba2202b` |
| `src/life/evaluate.py` | `732d3d099b05ed7afb48248bd2f1f404df98a313b053419531e134d21c3334d4` |
| `src/life/probe.py` | `7a2236d0118f7943fadb0175afc1fef571c4154a4936c059d24a3211d690c797` |
| `src/life/readouts.py` | `fc4b672ecc20753a41f1807fa756f7ae8db4a5c6c86e6a26bda2d45dde4d31bd` |
| `src/checkpoint.py` | `835d5529e40d8651511c5ee1ac5e682b9b1efd5b0a1b045f3200e6f16ab5df1b` |
| `results/atlas/play/lifesim.js` | `817c870eec0ad53e142e1fc83b6d5c95e0040e8e0dc1c68b94af16174f1dc841` |
