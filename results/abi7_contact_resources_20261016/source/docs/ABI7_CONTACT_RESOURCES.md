# ABI 7: food grown by empty-site contact

ABI 7 adds a delayed consequence to existing patch clicks. Cell inputs, genomes, asynchronous clocks,
development, movement, receptors, hotspot hysteresis and prices are unchanged. `catch_contact_resources_l4`
is the ABI 6 resource preset with `patch_contact_delay=80`. This is an environment extension, not evidence
of evolved planning, memory or superior acquisition.

Append world index 82 `patch_contact_delay`, giving 83 entries. Zero disables contact growth. Positive delay
must lie in `[STEP_MIN,TIME_MAX]` and requires enabled patches. Older ABIs reject enabled contact growth.
No RNG stream is added. Retain the passive schedules, initial capacity, Gaussian field and candidate bound.
Require `n*(ceil(T/fast)+ceil(T/delay)+2)<=2^20` when enabled; retain the old passive bound when disabled.

An existing hotspot click inside a capture disk first reads current available stock. Positive stock yields
one ordinary harvest, and never starts growth even if it empties the site. Zero stock is a miss charged the
existing `c_miss`; if no job is pending it starts one packet due at `t+delay`. Repeated clicks cannot reset,
queue or accelerate it. Maturity offers one packet, admitting it if stock is below capacity or spilling it
otherwise, then clears pending. There is no automatic restart. A later empty click can start a new job.
Pending jobs have no sensory cue; increased ready stock changes only the existing local field. Queued
receptor deliveries are retained, and receptor candidates use the group's frozen left-limit stock.

World events are ordered by `(timestamp,slot,kind)`, passive source kind 0 before contact maturity kind 1.
Process only events strictly before the cell group or actual endpoint. A click exactly at maturity therefore
sees the prior stock and still-pending job. Accounting snapshots at `t_open` precede equal-time events.
Extinction continues the world to the usual endpoint; guards stop at their actual endpoint.

Packets are physically identical, but provenance is FIFO: the original `initial_remaining` is the oldest
prefix, followed by a capacity-bounded ring of admitted passive/contact origins 2/3. Spill enqueues nothing.
Harvest initial packets as origin 1; afterward pop the oldest ring origin. Contact origin changes no cue,
reward or behavior. FIFO bookkeeping is enabled only for contact worlds; neutral worlds retain the old path.

Keep existing indices 0–106. Append `patch_contact_<metric>_<slot>` for slots 0–3, in this order:

| Metric | Indices |
|---|---|
| starts | 107–110 |
| maturities | 111–114 |
| supply | 115–118 |
| spill | 119–122 |
| harvest | 123–126 |
| pending_open | 127–130 |
| pending_end | 131–134 |
| stock_open | 135–138 |
| stock_end | 139–142 |

The ledger has 143 columns. Existing source/supply/spill/refill totals include both passive and contact
arrivals. Contact columns are subsets, so passive quantities are differences. Initial packets are never
relabeled at window opening. All new columns are zero when disabled, inactive, or endpoint<=opening.
Pending snapshots are 0/1. Require the old stock/click identities plus, per slot:

```
pending_open + starts = maturities + pending_end
maturities = contact_supply + contact_spill
contact_stock_open + contact_supply = contact_harvest + contact_stock_end
contact_harvest <= total_refill_harvest
starts <= empty_clicks
contact_supply <= total_supply; contact_spill <= total_spill; maturities <= total_source
0 <= contact_stock_open <= stock_open; 0 <= contact_stock_end <= stock_end
```

Internal checks additionally reconcile FIFO length and contact inventory. Counts are nonnegative integers;
use the existing ledger-mismatch status for corruption. Starting remains a potentially productive nonharvest
action, counted in misses. Contact harvest records provenance, not counterfactual extra food.

Append world/all records, all integer words uint64 and float words IEEE-754 bits:

| Code | Words |
|---|---|
| 22 start | `22,bits(t),slot,job_index,bits(due)` |
| 23 maturity | `23,bits(due),slot,job_index,stock_before,stock_after,admitted` |
| 24 end | `24,bits(endpoint),slot,pending,bits(due if pending else +0),contact_stock,lifetime_starts` |

`job_index` is the lifetime zero-based start index. Increment lifetime starts after the start record;
maturity uses `lifetime_starts-1`. A start record precedes the existing patch click record 20, then CLICK 11.
Record 20 origin is 0 miss / 1 initial / 2 passive / 3 contact (3 only in enabled worlds). All existing terminal
21 records in slot order precede all contact terminal 24 records in slot order. Disabled worlds emit no 22–24.
Observer reads emit no records and advance no clocks. No new returned trace table is required.

Retain explicit ABI 2–6 arrays and hashes by neutral padding and reversing appended close-ledger folds.
The default caller stays ABI 2. Neutral ABI 7 has the same physical behavior; its all hash includes the 36
additional zero close-ledger folds. Genomes, programs and cell inputs retain their layouts. Checkpoint identity
remains strict across changed sources/binaries; historical archives and source copies are immutable.
