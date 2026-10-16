# Empty-site taps can grow additional food

Source/design proposal, 2026-10-16. No implementation, simulation, seed reservation or evolutionary run.

Recommend one additive extension of the existing resource world: an ordinary tap at an empty patch starts
one packet that matures 80 time units later. Immediately stocked food and independent passive refill remain.
A successful harvest does not start this process. This gives an existing, sometimes unproductive action a
delayed physical consequence without prescribing a route, wait, revisit or internal algorithm.

## Exact first world

Use `catch_resource_patches_l4` at T1024, unchanged except for contact maturation enabled at delay 80:
three stationary sites, capacity two each, initial stock two each, radius-one capture disks, randomized
ABI6 placement at radii 2–4, Gaussian width 0.6, and independent passive source periods 80/160 with their
existing random phases. Passive source times never depend on contacts. Every other cell, motion, sensory,
developmental and physical-price parameter remains identical to this preset.

Each site has one additional pending flag and deadline, initially empty/infinite. For an actual hotspot
click, use the existing geometry and hysteresis; occupancy, motion through the disk and ordinary motor
strokes alone do not trigger growth.

1. If stock immediately before the click is positive, harvest one packet under the existing rules. Even if
   this empties the site, it starts no job.
2. If stock is zero, the click remains an ordinary miss charged `c_miss=10`. If no job is pending, set its
   deadline to `click_time + 80`. Starting pays no income. If already pending, leave its deadline unchanged.
3. At that deadline, offer exactly one packet: admit it if stock is below two, otherwise spill it. Clear the
   pending flag either way. Another later empty click can start another job. There is no automatic restart,
   queue, deadline reset, reservation of stock space or retained backlog.
4. Harvesting any ready packet earns the unchanged `R_cap=500`. All existing cellular, receptor, signaling,
   movement, division, secretion, miss, guard and extinction charges remain. There is no planting bonus or
   additional planting fee; the triggering action already incurs its ordinary physical charges.

Mature stock has the exact existing local cue: component amplitude `0.1 + 0.9 * stock / 2`, multiplying the
same Gaussian in the existing scalar receptor field. Empty sites retain their faint landmark. Pending jobs
have no extra cue; maturity is visible only through increased available stock. Cells receive no site ID,
stock register, success bit, reward, deadline, world phase or shared clock. Existing candidate streams,
thinning bounds, receptor delay and queued sensory events remain unchanged. Remembering a past contact
could help, but current-stock responses remain legitimate useful behavior.

## Event and accounting contract

Extend ABI6's world event merge, not the cell scheduler: process events strictly before each cell timestamp;
break world ties by slot, then passive source before contact maturity. Freeze receptor stocks at group entry,
while clicks consume current stock immediately. At an exact maturity/click tie, the click sees pre-maturity
stock and the still-pending job; maturity follows that timestamp's group. Events exactly at the actual life
endpoint are excluded. Extinction permits ordinary world continuation; guards close at their actual endpoint.

Retain the existing initial/all-refill split and add contact-origin accounting. Packets are physically
identical; track initial, passive and contact provenance in arrival FIFO order, with initial packets first
and the declared event order resolving ties. This observer bookkeeping changes neither cue nor value.

Existing source/supply/spill/refill columns count all noninitial arrivals in the new mode. Append four-slot
blocks for contact starts, maturities, admitted supply, spill, harvest, pending at window opening/end and
contact-origin stock at opening/end. Passive quantities are the corresponding totals minus contact subsets.
For every accounting window, independently require:

```
pending_open + starts = maturities + pending_end
maturities = contact_supply + contact_spill
contact_stock_open + contact_supply = contact_harvest + contact_stock_end
total_harvest = initial_harvest + passive_harvest + contact_harvest
```

Keep all existing stock/click/cost conservation checks. Starts and maturities are separate from food obtained;
unfinished jobs and spills must remain visible, including jobs crossing the window boundary. Contact-origin
food measures physical provenance, not necessarily extra food relative to a counterfactual trajectory.
Opening snapshots precede equal-time events; appended counters are zero when the endpoint is at/before
window opening. Pending is always zero or one per site.
Implementation can keep `initial_remaining` as a virtual oldest prefix and a capacity-bounded passive/contact
origin queue for later admitted packets; spilled packets never enter that queue.

ABI6 explicitly guarantees exogenous sources, so this cannot be silently encoded as an ABI6 preset.
Recommend an append-only ABI7 with one world scalar `patch_contact_delay`: zero disables the extension;
positive values enable the rule above, requiring patches and a finite delay in `[STEP_MIN, TIME_MAX]`. This gives
83 world entries and 143 ledger columns. Preserve older caller defaults, layouts, hashes and semantics;
neutral ABI7 runs must match ABI6 physical outcomes. Keep the genome and cell-input ABI unchanged.
Disabled patches require delay zero; older ABIs reject an enabled delay.
Require `n * (ceil(T/fast) + ceil(T/delay) + 2) <= 2^20` for combined source work, retain full hash records for starts/completions,
and implement identical C/Python/JS ordering. Existing `patch_click`, `world_to`, `patch_rate` and close
accounting are the relevant implementation seams; no new RNG stream is needed.

## Why this is a useful next demand

The completed baseline already showed AO collecting replenished food and making about 7.66 empty-site taps
per life. The modulation study showed that visible depletion helps this inherited behavior. The latest
descendant recovered older pursuit without establishing better patch acquisition. These provide an empirical
foothold, not a prediction that planting will work.

An empty tap now changes future supply, rather than merely changing where existing food is collected.
Camping can earn local food; greedy pursuit can follow ready cues; patrol can encounter/activate multiple
sites; revisits can collect earlier consequences. Repeated blind taps remain costly and cannot accelerate
an active job. Independent sites leave food beyond one campsite, but travel costs may still make camping
competitive. No strategy is declared superior, and none is penalized for being simple.

Keeping passive refill is deliberate. Replacing it would make every later meal depend on discovering the
new action chain. Automatically starting on a successful harvest would instead mostly add harvest-triggered
renewal. A common 80-unit delay isolates the added consequence from the existing fast/slow source class.

After engineering review, a small first baseline could hold AO and the new fixed ID1415 unchanged on
32 fresh shared development seeds, with contact maturation off/on: 128 scientific lives, plus a separately
bounded correctness budget. Report total/initial/passive/contact food, pending jobs, empty taps, per-site
tap/start/harvest coverage, all costs and paired F; these counts do not establish visit order or revisits.
Empty starts remain misses for accounting but are potentially productive nonharvest actions, not necessarily
wasted actions. This tests whether inherited behavior already creates and collects delayed
food, and whether the whole-life law adds net acquisition. It cannot establish planning, memory, an optimal
policy, a new circuit or a capacity limit. A null is also compatible with slow access or poorly priced travel.

Do not require a handwritten winning body or a memory-specific controller gap before this baseline. Use its
evidence to decide whether ordinary evolution has a profitable foothold; any later information-payoff claim
must compare declared active alternatives. Keep older tasks as reference checks and reserve new geometry/
timing combinations before selection. No experiment is launched by this proposal.

Sources: `src/life/spec.py` (`catch_resource_patches_l4`, `_validate_patch_keys`, `patch_receptor_rate`);
`src/life/kernel.c` (`patch_source`, `patch_click`, `world_to`, `patch_close`);
`results/abi6_resource_patches_20261015/DRAFT_CONTRACT.md`;
`results/resource_patch_baseline_20261015/REPORT.md`;
`results/resource_patch_modulation_20261015/REPORT.md`;
`results/resource_patch_depth_20261015/REPORT.md` and `NEXT_DECISION.md`.
