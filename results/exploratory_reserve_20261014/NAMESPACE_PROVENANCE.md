# Historical namespace provenance

The current AH seed audit and its initial/final scans are included under
`original/outputs/audit_exploratory_reserve_20261014/namespace/`. They cover the
64 native life IDs deliberately shared by both arms, the entire proposed
confirmation block 135, the 512 registered confirmation IDs, and completed AG
canonical/public seed-bearing artifacts. The audit's candidate-only wording
is preserved; the separate exact `registration.json` records the subsequent
root reservation.

Twenty-one older public proof objects, totaling 36,833,599 bytes, are referenced
by content hash instead of copied again. `namespace/history_references.json`
inside the path above gives each exact repository path, containing public commit,
byte size and SHA256. The archive manifest repeats that reference map. Full
historical provenance verification needs those repository objects locally, with
all hashes checked; this folder alone is not the full historical inventory.
There is no implicit network fetch or unverified live-source replacement.

Current scientific source, world, initial population, copied timing inputs,
configs and independent offline reader are present in the archive. Their
verification does not depend on the omitted historical inventories.
