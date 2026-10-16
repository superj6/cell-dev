This is a source-only test design for the final patch contract, SHA256
`15c3f7d7006bd274c2e7c9c06d6a89bd264dd8128be8579286dda70c1d740d77`.
It schedules no execution or scientific cases. Final sizes are world82 and ledger107, with initial/refill
harvest blocks99–102/103–106 following geometric misses98.
The independent tests can live in `tests/test_abi6_boundaries.py` and `tests/test_abi6_legacy.py`, following
the included-C fixture pattern in `tests/test_abi5_kernel_boundaries.py`. Scripted fixture states test rules;
their harvesting is not a hand-built organism admission gate.

1. **Immediate finite spending.** Inject one patch with K2, two initial packets, and no source before a fixed
   group. Three ordered same-group hit attempts must harvest twice then produce one empty miss. Geometry and
   source deadline stay unchanged; income is1,000, failed-click charge10, and total clicks3. Receptor candidates
   anywhere in that group see the same pre-group stock; the next group sees the depleted value. Repeat with
   one admitted-source packet, zero stock, another slot and a geometric miss. No packet may be spent twice.

2. **Source/click ties.** For initially empty, one-stock and full states, force a source exactly at the click
   timestamp. The click and receptor candidates use the left limit; source processing occurs only when time
   advances beyond the group. An empty click misses then replenishes. A full patch harvested at that time can
   admit the source; without the click that source spills. Check source/supply/spill and available stock after
   every step. Two sources at one timestamp use slot order; two slots' counters do not alias.

3. **Window and endpoint accounting.** Force sources/clicks immediately before, exactly at and after opening.
   Opening stock is captured before events at opening, pre-window harvesting changes real stock but not counted
   harvest, and arrivals at opening count once when subsequently processed. A source or click exactly at the
   actual endpoint is right-excluded. A guard at/before opening leaves all appended window columns zero.
   A guard after opening closes at its actual time with the existing guard charge. Extinction continues the
   world to T, allowing source admission/spill after cell death while preserving the production surcharge.
   An explicit t0 translation and pre-window depletion case check that neither phase nor refill is restarted.

4. **Packet provenance.** Once the convention is frozen, mix remaining initial and source-origin packets and
   verify harvest labels under that convention, including a window opening after earlier initial harvest.
   Full-life initial harvest cannot exceed n*K; source-origin harvest cannot exceed earlier admitted supply.
   Initial packets are never counted as source arrivals, and a spilled source never becomes harvestable.
   Tagging packets must not change the receptor field, income, stock schedule or trajectories.

5. **Exact conservation and corruption.** For each active slot enforce source=supply+spill and
   opening_stock+supply=harvest+closing_stock; also enforce captures=sum(harvest),
   misses=sum(empty)+geometric and clicks=captures+misses. Check nonnegative integers, stock bounds and unused
   slot zeros. Inject one inconsistent source, stock or harvest counter and require the existing mismatch bit
   in each backend; do not silently fix it. Independently reconstruct income, all ordinary physical costs,
   guard charge and native/production F. Classify legitimate guards/extinction separately from corruption.

6. **Fixed geometry, streams and numerical order.** Test count1–4, smallest allowed radii, extreme allowed
   periods and K, equal periods, first-phase-zero/nextup behavior and the event-work bound. Verify disjoint
   capture disks, ordered scalar-component sums, the constant candidate envelope and no reset when stock
   changes. Source index times must use first+j*period rather than repeated addition. Delayed receptor delivery
   may carry old stock evidence. Force full-width counter words in the new source/hash records. Repainting and
   observer polling must leave event order, RNG streams and hashes unchanged.

7. **Boundary-specific parity and legacy neutrality.** Use a small fixed fixture inventory for C/reference/JS
   at the ties above, comparing complete ledgers, full hashes and supported spike records. C full/fast ledgers
   must agree; constant fast hashes do not prove trajectories. Exercise both C schedulers where supported.
   Keep old ABI2/3/4/5 world/ledger shapes, fixture bytes and full hashes unchanged under neutral V6 padding,
   including old delayed matching and the ABI2 fast projection. Old callers must reject enabled patch fields;
   new neutral fields must consume no patch streams/events. Retain existing legacy expected values.

The smallest useful first implementation checks are deterministic helpers plus the injected boundary fixture.
Actual backend-call counts and resource limits belong in the later execution inventory; this document creates
neither a simulation allowance nor a broad retest obligation. Native observer claims must match real outputs:
without a validated C visit/click trace, aggregate harvests cannot certify switching, waiting or revisit timing.
