# Independent source and actual-input review

2026-10-15. **Accepted for the fixed baseline after root release and worker clearance.** No simulation,
library build, library load or new random draw was performed by this review. Execution remains root-owned.

Reviewed final protocol SHA256
`35a4af4a9ab1f78bf15732ff4a0af73763b41ed7cad97c61921252343eac4bf7`, based on source revision
`968bb81f2e146e2e729bca43004628d78a6e9b99`. All 32 production-source, nine input and six study-source pins
match actual files. The six scripts parse. No release, attempt, raw output, startup or build-cache artifact
existed at final review.

I independently loaded the public endpoint manifest, all six source/copied JSON genomes, the float32 raw
array and float64 packed array. Public file hashes, raw genotype hashes, role order and all array bytes match.
Repacking the six 875-element raw genotypes with ABI5 yields the saved packed bytes exactly. Neither a
rank replacement nor a new genotype is introduced.

Both saved 77-field world vectors match the actual `catch_delayed_match_l4` preset exactly at T85/T1024.
Only T differs; t0/t_open are zero, prices/timings/geometry/cell rules remain default and flags are zero.
The worker passes one listed seed, one listed genome, ABI5 and one thread to each call. The actual schedule
matches the independent Cartesian reconstruction: 2 durations × 6 roles × 32 seeds = 384 C-fast lives,
followed by six predetermined C-full T85 repeats of seed 52430000. All 390 paths are unique; startup has no lives.

Seeds are exactly 52430000–52430031, intentionally shared across roles and durations. The block143
reservation excludes later confirmation. I reviewed the namespace reader and its recorded evidence: no
numeric NPZ collision or parsing error, 13 JSON matches individually verified as AO's excluded upper endpoint,
and disjoint registered intervals. The audit rereads distinct historical seed payloads and changed files,
rather than reusing an earlier block's no-collision verdict. Prior inventories remain referenced and pinned.
This review did not rerun the repository-wide inventory; it checked the actual seed array, audit pins, literal
classifications, registrations and source logic.

Analysis checks each life's integer/nonnegative class counters and opportunity conservation; reconstructs
conditional income, wrong-choice costs, ordinary physical costs, guard charge, net and F; retains guard/extinction
outcomes; and rejects accounting/capacity/truncated-log errors. Class-to-physical-choice mapping is correct.
All six full/fast ledger rows must match bitwise, with complete predetermined fate logs. Missing coverage or
validation failure cannot produce a valid completion marker. Native F and guard-charge reconciliation uses
the declared numerical tolerance; raw native ledgers remain intact.

The CSV fidelity correction is appropriate: native_F/native_guard_charge are preserved alongside reconstructed
F/guard_charge. Final analyzer SHA256 is
`10545ca6d272165cf078867a78f95dc64a4dc2bfc8c2ce4b5905ddc546da255a`.
Prior analyzer/protocol/READY/prose bytes are retained under `preparation_history/native_csv_fidelity/`.
Compared with protocol `7fdab30877cddbb21be091fa3f3f779626b944a3cca25b0870cd8e37d86a5380`, only source pins
changed; all genomes, worlds, seeds, schedule, namespace evidence and resource limits are unchanged.

The monitor enforces one one-thread worker, one-CPU affinity, 600 cumulative CPU seconds, 900 wall seconds,
2 GiB summed RSS, 8 GiB worker address space and 4 GiB available-host-memory floor. It accounts for compilation,
analysis and descendants, binds ownership/release, records cleanup and refuses a repeated attempt. Runtime
release must bind the final protocol hash; no scientific retry or added call is implicit.

Interpretation remains descriptive development evidence. The six first-seed fate logs measure physical
sensory-plane occupancy, not receptor gain or usable cue information. If a guarded full repeat ends before a
snapshot cutoff, its carried-forward last logged occupancy is not observed post-terminal development; consult
the corresponding native t_end/status when interpreting that snapshot. All statuses and outcomes remain
retained. Thirty-two seeds do not satisfy the 512-seed information-payoff criterion, and positive F or physical
slot hits do not establish matching, neural memory or generalization. No further prelaunch blocker was found.
