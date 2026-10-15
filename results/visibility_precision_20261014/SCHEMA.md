# AB prospective interfaces

No scientific protocol, inputs, registered seeds or runtime artifacts exist at source-only preparation.

`registration.json`: status registered; fixed runs list; paired_native_seeds {D90:int, L92:int}; 512 confirmation_seeds;
founder_policy `both_Z_final_rank0_regardless_of_AA_or_confirmation`; seed_audit_sha256; Z_complete with Z-relative
file_pins and repo-relative reviewed summary_path/summary_sha256. Root owns registration, clearance and ready.
`seed_audit.json`: status passed; same paired seeds/confirmation; run_life_seeds keyed by all four job IDs;
intentional_overlap keyed by background, each exact sorted intersection. Background unions and confirmation disjoint.

`protocol.json`: runs [D90_depth, D90_precision, L92_depth, L92_precision]; paired_native_seeds; run_settings[run]
exactly {background, policy, seed, generations, initial_lives, recheck_lives}; configs[run] {path, sha256}; founder_mapping
keyed D90/L92 {start_file, raw_sha256, Z_role_index, Z_endpoint}; reference_files contains two Z start JSON paths.
world, full expected_numerical_identity, pure numerical_identity, production_pins and file_pins follow Z.
Cost projection retains all six original/Y/Z timing rows, lineage maxima and both fixed formulas/thresholds.
Scope fields: search_genome_lives 16504, confirmation_genome_lives 3072, planned_genome_lives 19576,
startup_validation_genome_lives 10, max_cpu_seconds 9000, search_cpu_seconds 7200, max_simulation_threads 4.
confirmation has exact labels, 512 seeds, threads 2, primary_pairs [[3, 2], [5, 4]], gain_pairs [[2, 0], [3, 0], [4, 1], [5, 1]].

`initialization.json`: status pure_genetic_preparation, simulation_calls 0, backgrounds mapping D90/L92 to one
population_file/file_sha256/population_raw_sha256/before-and-after RNG hash/copies record; runs maps all four job
IDs to their background. `generation_claim.json` is created exclusively before the two setup/fill calls. There
are only two generated 32×875 float32 tables; native searches later reproduce them from the identical founder/seed.
Preparation pins all copied Z inputs/timing rows, exact configs, operations, tables and source closure.

Native runs write `runs/<run_id>/` using unchanged src.run/checkpoint. Depth ends at generation 4, precision at 1;
the evaluator still counts genome evaluations: 1024/256 respectively; recheck life count is 1024 in either arm.
Native initial calls use 3 or 12 and rechecks 4 or 16; guard-count reconstruction must respect each arm. Raw search
per-life ledgers are not retained; native summaries/recorded selection/genetic replay are the search coverage.

`confirmation/endpoints.json`: six labels/seeds/genotype raw hashes; endpoints keyed four run IDs with checkpoint,
genome-file/raw, determinism/log pins, actual generation 4/1, rank 0, health; exact identity/ready/world/protocol pins;
matched_first_cohort keyed background binds prepared population and equal recorded genetic instructions.
`confirmation/genotypes.npz`: float32[6, 875], labels. All endpoints freeze before first scientific row.

Six `confirmation/blink/row_0000.npz`..`row_0005.npz` retain Z's full 58-column raw ledger, all named production
columns, ordered seeds, genome index, scalar CPU/wall and JSON identity {protocol_sha256, stage:confirmation,
endpoints_sha256, role, genome_index, genome_sha256}. F is production F_kernel minus extinction charge, with guard
charge already in F_kernel. The accountant must retain correct initial 1 + births − deaths − kills whole-life census;
wall rejections/other rejections and arrived/dropped events are disjoint counters. AA's late-window rules do not apply.
row_index.json maps blink row path→{sha256, cpu_seconds}; scores.npz stacks all named columns [6, 512].

`confirmation/report.json`: complete, report_only, genome_lives 3072, paired_seeds 512, confirmation_startup_validation_lives 2,
protocol/endpoints/genotypes hashes, row_cpu_seconds, absolute metrics; primary keyed precision_D90/precision_L92;
gain keyed all four endpoint labels. Each comparison uses the exact saved paired rows; no across-run SE claim.

Monitor job names evolve_<run_id>, confirmation. Z monitor lifecycle is retained: attempt has monitor and ready hash;
budget has phase, CPU cap/phase cap/reserve, search_stage_cpu_seconds, running/queued/completed, identities/groups,
ready, status/reason/exit. Persisted identities have pid, ppid, pgid, start_ticks (plus name), **no sid**. Search phase
contains up to 2 workers; confirmation starts after every search group exits. Ready separately pins final independent
analysis/reviews. Missing/failed/partial evidence cannot emit a complete scientific conclusion.
