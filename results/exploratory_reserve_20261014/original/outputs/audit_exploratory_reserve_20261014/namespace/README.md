# AH candidate namespace audit

This is a candidate audit, not a reservation or authorization to prepare inputs.
The proposed native run seed is **53226**, intentionally shared by the control
and reserve arms. The proposed confirmation block is **135** at base 51,000,000;
the 512 used IDs would be **52,350,000–52,350,511**. The collision check covers
the entire half-open block **[52,350,000, 52,360,000)** and all native hashed IDs.

The existing four-generation schedule has 64 distinct native life IDs per arm:
28 generation IDs, 32 validation IDs, and four final IDs. Both arms deliberately
share all 64. The two final index-zero IDs are evaluated at T=1024 and reused
for the T=512 half-duration diagnostic, giving 66 logical stage seed uses per
arm. Candidate sharing within a generation is also intentional. This amounts
to 4,134 research lives per arm, plus 1,536 confirmation lives across the three
fixed roles: 9,804 research lives. Three existing numerical identity invocations
would contribute six standard seed-11 golden lives, for 9,810 total calls.
The native run seed also keys the genetic stream; deriving its life-seed
schedule here does not run that stream or generate genomes. The proposed
reserve lottery has its own stateless domain and creates no additional life ID.

`candidate_namespace_review.json` classifies the initial audit. The scan reopened
one representative of every distinct historical seed payload against these new
candidates, then read all seed members of changed or added NPZs. It also checked
declared JSON schedules and source literals. The twelve initial numeric matches
and eight text matches are the excluded upper endpoint of prior AG block 134.
All 138 completed AG canonical/public raw-row pairs have equal bytes and use
only the 546 registered AG IDs. No outcome or genotype arrays were loaded.

`final_namespace_delta.py` is the registration-time check after source and test
fixtures settle. The later unexecuted root registration draft is a proposed use,
not earlier research. A passing `seed_audit.json` will remain explicitly
unregistered and unreserved; root registration is a separate action. New files
or changes after that check require another compact delta before registration.

The full historical proof is not contained in this folder alone.
`history_references.json` identifies 21 already committed repository artifacts
by exact path, containing commit and SHA256, avoiding another 36.8 MB copy.
Those objects must be available locally for full historical verification;
there is no network fetch or unverified live-source substitution. Unchanged
file reuse is based on recorded stat identity and pinned seed-payload hashes,
not a claim that every complete historical NPZ was freshly hashed. Previously
classified immutable synthetic malformed fixtures stay covered by the prior
proof. The initial AH scan encountered no new malformed NPZ or JSON.

All audit operations are source/metadata only: no registration, copied
scientific inputs, genetic draws, compilation or simulation.
