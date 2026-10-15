AE candidate namespace audit (not a reservation)

The proposed schedules use base 51,000,000 and stride 10,000: block 128 calibration (2 IDs), block 129 screen (32 IDs), and block 130 confirmation (512 IDs). The audit checks all three whole blocks, not only those 546 IDs. The standard ABI3 numerical golden intentionally retains seed 11 and is outside the fresh research schedule.

`candidate_namespace_inventory.json` combines the previously accepted same-host inventory with all new or changed NPZ paths. Each distinct historical seed payload was reopened and checked against these new blocks; an earlier no-overlap conclusion was never reused for a different range. Exact raw seed-payload hashes support reuse across byte-equivalent copies. Seed arrays and the AD research identity metadata were read; scientific outcome and genotype arrays were not.

`candidate_namespace_review.json` classifies all apparent matches and synthetic errors. AD's upper endpoint 52,280,000 is exclusive, so it does not reserve that ID. Old prediction block 130 uses base 43,000,000 and therefore refers to a different range. All 515 registered AD IDs are explicitly disjoint; all 58 AD raw files match their public copies, and all 13 research identity lists match the registered 512-ID research schedule. The validation arrays lack their own seed metadata; their three IDs are bound by the frozen protocol and validator source.

`final_namespace_delta.json` checks changes after the candidate inventory and the independent reader's shared fixture freeze. `seed_audit.json` is the compact exact-stage receipt for a later root registration. These files do not reserve or authorize any study run.

Historical namespace evidence is content-addressed in `history_references.json`: exact repository path, public commit and SHA256 for every referenced object. Those already published objects are not copied here again. Full historical proof requires that repository material; this folder alone is not a complete historical namespace archive. There is no network fetch or silent alternate-source fallback. The same-host stat tuples are an optimization for change detection, not a claim that every whole NPZ was rehashed. A fresh filesystem must treat changed tuples as changed files.

The older audit_prediction_gradient_20261014 proposal and its tentative blocks 110/111/112 remain historical and are not the AE schedule.
