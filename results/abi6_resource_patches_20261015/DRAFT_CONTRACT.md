# ABI 6 draft: persistent, depletable food patches

Status: concrete draft for source review, 2026-10-15. No implementation, simulation, build, seed reservation,
information-payoff result or evolutionary run is produced by this document. It follows the completed-result
direction in [cumulative_primitives_direction.md](../delayed_match_evolution_20261015/discussion/cumulative_primitives_direction.md)
and [TASK_VARIATION_PLAN.md section 0](../../docs/TASK_VARIATION_PLAN.md).

Three stationary patches start stocked. A hotspot click in a stocked patch removes one packet and earns the
ordinary food income. The patch stays where it was. Independent, fixed source arrivals replenish its finite
stock; arrivals at a full patch spill. Stock controls the strength of its familiar Gaussian field, with a faint
field left when empty. Existing pursuit can obtain the first food without solving a new preliminary task.
Waiting, switching patches and returning can each be useful, but none earns a behavior bonus or is compulsory.

The world has four patch slots so a later count/composition transfer can use the same ABI. The initial preset
uses three. Slot capacity is separate from the number of packets held by each patch.

## Organism interface and objective

Keep the genome, gene inputs, local asynchronous clocks, receptor events/delays, messages, development, movement,
hotspot hysteresis and all existing physical prices unchanged. A sense cell receives only the existing scalar
Poisson input at its own screen location. Cells receive no patch ID, coordinates, map, stock register, source
rate, reward, task label, phase or shared clock. A patch's stock changes its physical local field; ledger income
is not sensory feedback. Pending receptor events are never canceled when stock changes.

Only successful harvesting pays `R_cap`; both an empty-patch click and a geometric miss pay the existing
`c_miss` charge. All ordinary cell, spike, twitch, message, division, secretion, receptor, guard and production
extinction charges remain. Prices and world laws never respond to population performance. Resources are local
world state, not a new organism energy store or a new survival rule.

## Minimal world extension

Retain explicit `V2`, `V3`, `V4`, `V5`; add explicit `V6`. The caller default stays `V2`. Append five float64
fields to the 77-entry ABI 5 world, giving `WORLD_SIZE=82`:

| Index | Name | Neutral | Enabled meaning |
|---:|---|---:|---|
| 77 | `patch_count` | 0 | Exact integer 1–4; zero keeps the existing world modes |
| 78 | `patch_capacity` | 0 | Exact positive integer packets per patch; all patches start full |
| 79 | `patch_refill_fast` | 0 | Period of the faster fixed source law |
| 80 | `patch_refill_slow` | 0 | Period of the slower fixed source law |
| 81 | `patch_landmark` | 0 | Fraction of full Gaussian amplitude retained at zero stock |

No extra mode, initial-stock, reward, radius, width, layout-scale or source-probability parameter is needed.
Existing `sigma`, `lam_s`, `lam_bg`, `rho_c`, `R_min`, `R_max` and `R_cap` supply those meanings. Rate class is
an independent fair draw per patch. Equal fast/slow periods are permitted as a control. Capacity/count transfers
and new period pairs require no ABI change; arbitrary coordinates, more than four patches, distinct appearance
classes, continuous inflow or valves would require another explicit contract.

All appended fields are finite. With count zero the other four must be zero. With count positive require:

- CATCH (`world_kind=1`), `task_mode=0` with all six task durations zero, neutral visibility `(0,0,0,1)`;
- `v_t=tau_turn=t_resp=0`; legacy second blob disabled: `b2_amp=b2_value=0`, `b2_mode=0`, `b2_p=1`;
- `1 <= patch_capacity <= 2^20`, integer; `2^-10 <= fast <= slow <= 2^30`; `0 <= landmark < 1`;
- `rho_c>0`, `R_min >= 2*rho_c`, and the existing finite length bounds and `R_min<=R_max`;
- `lambda_max = lam_bg + lam_s*patch_count <= 1024`;
- `patch_count * (ceil(T/patch_refill_fast)+1) <= 2^20`, bounding source-event work independently of cell activity.

The conservative radius condition guarantees disjoint capture disks for every supported count without random
rejection or a seed-dependent invalid-world outcome. Gaussian tails overlap; “nonoverlapping patches” refers to
the physical capture disks, not the unbounded Gaussian tails. The source-event bound is validation, not an
additional behavioral penalty or an alteration of the cell event guard. Older ABIs reject enabled patch fields.

## Placement and independent source laws

Append streams `S_PATCH_LAYOUT=31`, `S_PATCH_RATE=32`, `S_PATCH_PHASE=33`. Existing stream numbers and counters
stay unchanged. Use the existing float64 `draw`, `TWO_PI`, `sin`, `cos` and `nextup` implementations.

At `t0`, before initial cell records, set inactive slots to canonical zero state. For `n=patch_count`:

```text
theta0 = TWO_PI * draw(seed, S_PATCH_LAYOUT, 0, 0)
for i = 0 .. n-1:
    theta = theta0 + (TWO_PI * double(i)) / double(n)
    r = R_min + (R_max-R_min) * draw(seed, S_PATCH_LAYOUT, i, 1)
    x[i] = r*cos(theta); y[i] = r*sin(theta)
    period[i] = fast if draw(seed, S_PATCH_RATE, i, 0) < 0.5 else slow
    phase[i] = period[i] * draw(seed, S_PATCH_PHASE, i, 0)
    first[i] = t0 + phase[i]
    if first[i] <= t0: first[i] = nextup(t0)
    arrival_index[i] = 0
    next[i] = first[i]
    stock[i] = patch_capacity
```

For arrival index `j`, its timestamp is `first[i] + double(j)*period[i]`, evaluated in that order, without
repeated addition. The time/period bounds ensure later indices advance. Patch centers never move or respawn;
they remain relative to the initial world origin, not the organism's later position. Different independent radii
break the exact center symmetry of an equal-radius regular polygon. This compact annular layout is deliberately
limited; translation/rotation or new seeds alone are weak transfer claims.

Positions, initial stock, Gaussian width and full/empty amplitudes do not encode rate class. All patches have
identical appearance at equal stock. The phase draw is independent of the class draw; its conversion to a time
uses that patch's period. Rate and phase become inferable only from physical depletion/recovery observations.
All-fast and all-slow lives are retained (each has probability 1/8 with three patches), not filtered out.

Each source arrival creates exactly one offered packet. If `stock<K`, increment stock and admitted supply;
otherwise increment spill. Spill is lost; no backlog accumulates. The source schedule is never reset, delayed
or accelerated by a click, visit, depletion, extinction, accounting window or fork. Harvesting changes available
stock and whether later arrivals spill; it does not change the external source. These are world event times,
not clock signals delivered to cells. In particular, a hidden “time since last harvest” cell input is absent.

## Scalar field and event order

At a receptor candidate, use the stock at the timestamp's left limit. Start `rate=lam_bg`, then add active
patches in ascending slot order:

```text
fraction = double(stock_left[i]) / double(K)
amplitude = landmark + (1.0-landmark)*fraction
component = lam_s * (amplitude * halo(px-x[i], py-y[i], sigma))
rate = rate + component
```

Thin the unchanged `(uid,j)` candidate stream at the constant lifetime bound
`lam_bg + lam_s*double(patch_count)`. Stock changes never rescale or restart candidate clocks. Accepted events
still arrive after `d_min`, with the current delivery phenotype and the existing receptor charge. There is no
patch-identity channel. The faint field preserves a location, not a guaranteed ability to identify or revisit it.

`world_to(t)` processes source events strictly before `t`, in timestamp order with slot index breaking exact
ties. At an arrival it uses the scheduled timestamp, not the next cell event's timestamp. Integer distance/zone
samples and the cell record group at exactly an arrival time see stock before that arrival. The arrival is
processed after that timestamp's group when the timeline next advances. Events exactly at the actual life
endpoint are excluded.

At group entry, freeze `stock_left[4]` for receptor-candidate calculations. A click checks the body hotspot
against each active capture disk using the existing squared-distance arithmetic. Disks are disjoint. If it hits
a patch with positive available stock, decrement available stock immediately, increment its harvest count,
increment `captures` and add `R_cap` income when counted. Later clicks in the same group cannot spend that
packet again. If it hits an empty patch, increment that patch's empty count and `misses`; outside every disk,
increment geometric misses and `misses`. Both failures add `c_miss`. No click moves a patch or creates a packet.
The frozen receptor field lasts through the group; the next group's left limit uses the resulting stock.

Ordinary hotspot hysteresis and canonical record order remain decisive. Stock depletion is not an additional
cooldown. Queued receptor events can report the previous stock after depletion. At an exact source/click tie,
an empty click misses and the subsequent source can refill it; a full patch can be harvested and then accept
that source packet. This is a declared left-limit convention, not a correctness rule.

Extinction preserves CATCH's world continuation through `T`; sources can refill and spill after all cells die.
A guard instead closes at its existing actual endpoint, with its existing charge. No cell-visible reset occurs.

## Conservation ledger and observer readouts

Append nine blocks of four integer-valued float64 columns, plus geometric misses: `LEDGER_SIZE=107`.

| Indices | Names, for slot `i=0..3` | Window meaning |
|---|---|---|
| 70–73 | `patch_stock_open_i` | Stock immediately before the accounting window opens |
| 74–77 | `patch_source_i` | Offered packets from scheduled sources |
| 78–81 | `patch_supply_i` | Offered packets admitted into stock |
| 82–85 | `patch_spill_i` | Offered packets lost because stock was full |
| 86–89 | `patch_harvest_i` | Successful one-packet harvests |
| 90–93 | `patch_empty_i` | Clicks inside that disk with no available packet |
| 94–97 | `patch_stock_end_i` | Stock immediately before the actual endpoint |
| 98 | `patch_geometric_misses` | Clicks outside all capture disks |
| 99–102 | `patch_initial_harvest_i` | Harvested packets from the t0 initial endowment |
| 103–106 | `patch_refill_harvest_i` | Harvested packets admitted by later sources |

The counted window is `[t0+t_open,t_end)`. Capture opening stock after all earlier actions/arrivals, before any
action or arrival exactly at opening. At `t_open=0`, opening stock is the initial endowment `K`; initial endowment
is not counted again as a source arrival. Pre-window harvesting and spilling change the real stock. If the actual
endpoint is at or before opening, all appended columns are zero. Otherwise closing stock includes all and only
earlier world changes. Inactive slots and count-zero worlds produce zero appended columns.

Track `initial_remaining[i]=K` from t0, solely for provenance. Harvest initial packets first: when this value is
positive, decrement it and classify the meal as initial; otherwise classify the meal as refill. Admitted source
packets never increment initial_remaining. This FIFO attribution changes no field, availability, income or cell
input because packets are physically identical. Never relabel remaining packets at t_open. Track the internal
initial count at window opening and close; their difference must equal window initial_harvest. Pre-window meals
update provenance but do not increment window counters. The two new harvest blocks split actual food obtained,
so initial meals cannot be mistaken for a replenishment/revisit gain.

Enforce these exact integer identities for each active patch and the aggregate at close in C/Python/JS:

```text
source = supply + spill
stock_open + supply = harvest + stock_end
stock_open + source = harvest + spill + stock_end
harvest = initial_harvest + refill_harvest
initial_open_internal = initial_harvest + initial_end_internal
captures = sum_i harvest_i
misses = sum_i empty_i + geometric_misses
clicks = captures + misses
0 <= stock_open, stock_end <= K
```

Use the existing ledger-mismatch status bit for an impossible accounting identity; do not repair counters.
All counts are nonnegative integers. Income is added per harvest in event order; the usual numerical tolerance
applies when independently reconstructing floating energy totals. `captures` now means total successful food
harvests in patch mode; `b2_clicks`, `respawns`, `low_light_captures` and all delayed-matching counters are zero.
Mode-zero and delayed-matching meanings remain unchanged. Cost reconstruction can retain the ordinary CATCH
formula because there is no second-blob charge and every failed click already contributes to `misses`.

Existing integer `samples`, `dist_sum`, `zone_samples` measure distance/occupancy relative to the nearest patch,
including empty patches. Label that meaning explicitly; proximity alone is not food acquisition. Report per-patch
source/supply/spill/harvest/initial_harvest/refill_harvest/empty counts, aggregate harvested income and every physical cost component. Useful
ratios include harvested packets / `(opening stock + source)` and spill/source, with zero-denominator handling.
Report source-class and layout-conditioned allocation using observer-only metadata, not cell inputs.

Expose patch positions, stock, source period/next time and click outcomes only to the implementation observer
and browser state/trace. Successful switches/revisits and waiting durations require that trace; they must not
be inferred from aggregate harvest counts. The minimal ABI adds no new returned trace table: C hashes plus
conservation ledgers are mandatory; C trace instrumentation, if needed for a later diagnostic, must be separately
specified and validated before claiming those timing readouts. Python/JS observer displays do not establish a
C trace capability. Neither increasing late harvest nor rate-conditioned allocation alone establishes learning.

## Hashes and compatibility

Keep the existing five families. Append world/all records, using full uint64 integer words and float64 bit words:

| Code | Ordered words |
|---:|---|
| 18 | `18, bits(t0), i, bits(x), bits(y), bits(period), bits(first), K` for each active slot |
| 19 | `19, bits(t), i, arrival_index, stock_before, stock_after, admitted` for each source arrival |
| 20 | `20, bits(t), outcome, slot, stock_before, stock_after, origin` for each click |
| 21 | `21, bits(t_end), i, stock_end, initial_remaining` for each active slot at close |

Record 20 outcomes are geometric miss=0, harvest=1, empty=2; geometric miss uses slot sentinel4 and zero stocks.
Its origin is0 for either miss,1 for an initial-endowment harvest,2 for a refill harvest.
Fold it before the unchanged CLICK record11, whose legacy outcome is1 for any successful patch harvest and0
for either miss. Terminal records follow final world advancement and conservation checks, before close-ledger
folds. Source record19 uses the current index, then advances it. Initial/terminal slots fold in ascending order.
Count-zero worlds emit no records18–21 and consume no streams31–33. Observer sampling/painting emits no hash.

The kernel can allocate V6 buffers while older callers preserve exact arrays and full hashes through neutral
padding and reversal of appended close-ledger folds. Preserve the historical ABI2 fast projection; fast hash
constants are not replay truth. V5 delayed matching must retain its original 70 columns and all five full hashes.
The neutral V6 `all` hash includes its additional zero ledger folds by design. Genomes/programs remain identical;
checkpoints retain strict source/binary identity and require explicit, recorded population import across changed
engine identities. No old checkpoint is silently reinterpreted. Historical source/viewer copies stay untouched.

The maintained JS engine supports patch mode only in automatic simulation, rejecting target dragging, manual
removal, adding targets or changing stock during a life. Reuse its existing local cell engine. Renderer labels
must distinguish food harvested, empty actions, geometric misses, stock and source supply. Period/stock overlays
are explicitly observer information. Rendering cannot alter candidate clocks or world event order.

## Provisional preset and physical scale accounting

Propose `catch_resource_patches_l4`: inherit SPECK's original physics/prices and use `T=1024`, count3, capacity2,
fast80, slow160, landmark0.1; `sigma=0.6`, `lam_s=2`, `lam_bg=0.05`, `rho_c=1`, `R_min=2`, `R_max=4`,
`R_cap=500`, `c_miss=10`, with the neutral/stationary settings above. These numbers are design values for review,
not tuned results or an assumption that a particular tissue will win. The two-law choice keeps the first
measurement finite and follows the direction note; continuous rate distributions can be a later contract.

- Initial stock offers six packets, 3,000 gross energy, and never expires before the first visit. Identical
  Gaussian peaks preserve a familiar acquisition problem. At full/one/zero packets the component peak is
  respectively2/1.1/0.2; the background remains0.05. A single meal needs no productivity inference.
- Pairwise center distances in the three-patch layout lie between `2*sqrt(3)` and `4*sqrt(3)`, approximately
  3.46–6.93; the shortest gaps between capture disks are1.46–4.93. This is local travel, not a new large map.
  The stock cue need not be sensed at the hotspot: the developing sensory footprint uses its ordinary offsets.
- The exact motor law gives integrated displacement `tau_z*delta_force/gamma` for an isolated decaying force
  increment. With `tau_z=2.5` and hypothetical filled footprints19/37/61, one unit of coherent force gives
  0.574/0.411/0.320 distance. The disk gaps span roughly3–16 such aligned impulses. This is a dimensional
  comparison, not a realizable motor policy, speed guarantee or hand-built-body success test; cancellations,
  movement orientation, clicking, development and reaction delays matter.
- If net travel speeds were0.1/0.2/0.4, those gaps would take approximately15–49 /7–25 /4–12 time units.
  No such speed is assumed. Periods80/160 give a provisional separation from these travel scales and allow
  about13/6 source cycles during T1024. A competent physical control must measure whether the separation is real.
- Ideal continuous camping at a fast/slow patch offers6.25/3.125 gross energy per unit time, plus its two initial
  packets. Three sources offer9.375–18.75 gross energy per unit, with mean14.0625; the initial endowment adds
  2.9296875 to the whole-life gross upper bound. Thus the expectation of offered food is17.0 F approximately
  (16.9921875 exactly before rounding), not expected attained fitness. Overflow, endpoint stock, misses and all
  physical costs reduce it. The fastest patch contributes at most half of long-run offered supply, leaving room
  for allocation while allowing profitable camping. This arithmetic does not establish an information gap.
- Upkeep alone for constant32/64/128-cell bodies is0.64/1.28/2.56 per time unit. Waiting80–160 costs respectively
  51.2–102.4 /102.4–204.8 /204.8–409.6 before other charges, versus500 per packet. These illustrative sizes are
  not selected organisms. Initial food, camping and travel all have plausible positive gross margins; actual
  development, sensing and control costs must be measured.

The main tradeoff is deliberate: a reactive stock follower may already collect most value. If active camping,
greedy pursuit or patrol captures nearly all attainable food, this ecology has weak additional information
payoff even though its conservation laws are sound. We will not force switching or add a reward for memory to
rescue that result. Fixed recovery periods are learnable regularities, not an organism clock. Future irregular
sources would be a separately declared physical law, not an unreported difficulty adjustment.

## Information-payoff measurement to prepare after engineering

First validate actions/accounting and a small diagnostic panel, with exact call/CPU/memory caps announced before
execution. Then freeze a finite controller family, its tuning cases, physical footprints and parameters before
at least512 fresh paired confirmation lives disjoint from tuning. No seeds, arms, budgets or run release are
registered here. No hand-built tissue must succeed as a world-admission gate.

The declared competitors must physically harvest food: (C) home to a patch and actively camp, with local-stock
click gating and declared timing variants; (G) pursue the best currently observed stock under a short sensory
history; (P) a fixed patrol among locations estimated from the same receptor stream, with honest travel and click
costs. Retain strong variants including a useful first-patch choice and a useful patrol order, chosen on tuning
only. Their algorithms may know the published distribution, never the realized hidden rate, phase, map, seed or
stock. A “camping upper bound” with privileged best-patch knowledge is an accounting ceiling, not a fair observed
competitor. Zero-harvest references signal an action-limited comparison, not evidence for an information claim.

The first information instrument needs only current-stock sensing; memory is not an admission prerequisite.
Use a paired stock-neutral observation intervention with identical physical patch positions, source arrivals,
capacity, depletion, harvesting, travel and prices. Replace each patch's stock-dependent field amplitude by a
fixed positive amplitude independent of true stock/source class, while retaining its Gaussian location and the
faint landmark/localization opportunity. This is a declared observation intervention in the measuring harness,
not a new cell input or an alteration of physical food availability. Use the same receptor-candidate stream,
scalar modality, delays and action interface; charge all actually delivered receptor events under original prices.
No success/empty/capture event, ledger income, stock register, confidence derived from unmasked input, or raw
native receptor path may leak into the stock-neutral controller. Its clicks and movement remain enabled. It can
still home, harvest initial food, wait under the known source distribution and patrol.

Freeze active stock-neutral controls with useful click schedules on tuning data, including full-strength
localization and declared lower fixed-amplitude variants so extra receptor expense is not mistaken for information
payoff. Evaluate the informed instrument at the strongest finite active reflex's own footprint. Report changes
in harvested packets (split initial/refill), income and each cost term; require an acquisition contrast to say
that stock information bought food. If a result is only cheaper sensing/activity, describe that narrower result.
Before formal registration pin the observation-mask/cost comparison precisely, including whether a supplementary
common receptor-cost accounting comparison is needed. None of this grants the controller true coordinates:
localization must still come from its permitted local receptor stream and its own action/position estimates.

A later, separate mechanism question can retain versus erase per-location stock/recovery history while keeping
common geometry estimation, current sensory processing and action machinery enabled. That contrast would test
retained recovery evidence, not every form of memory; it is not a mandatory first-patch payoff gate. Fixed patrol
and camping remain legitimate profitable partial strategies. External computation/state are disclosed as free
instrument computation, while cells/receptors/relays/actions are charged normally. Instrument success is not an
evolved implementation or an accessible mutational path.

Include quieter/smaller variants of the strongest active reflex, and null/replay/interface checks that establish
no hidden-state access. Before registration pin exact inference/action rules and what counts as recent history,
including receptor-delivery delay and the instrument's own position/action estimates. Do not build an endless
controller optimization loop to manufacture a winning body. Diagnose observation-limited versus action-limited
failure, and preserve failures with the original cases.

Apply section0.4 unchanged: at least1 F and more than3 paired SE for the information gap and the current-stock
mechanism contrast; the best do-less gain must be less than one quarter of the information gap. Show uncertainty
for do-less without inventing a new three-SE gate. Also report harvested food/income, supply utilization, spill,
empty and geometric misses, travel and each cost component, with life-cluster uncertainty. An F gain caused only
by reduced activity is not evidence that information bought additional food. “Best” always means the best of
the frozen finite family, and every planned role/class remains in the report.

Engineering correctness, information payoff, evolutionary accessibility and cumulative evolved capability are
separate conclusions. A future ordinary continuation should use one declared full ancestral population and one
fixed final endpoint, evaluate earlier pursuit contexts, and reserve count/layout/period combinations from
selection. Same-genome retention and transfer support functional reuse; ancestry, world stock as external
memory, or an external measuring program alone do not establish neural memory or superiority to handwritten
programs. The completed delayed-matching endpoint and report remain unchanged.
