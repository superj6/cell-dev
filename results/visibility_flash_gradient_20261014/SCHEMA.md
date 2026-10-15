AC producer and reader interface

`protocol.json` is absent until authorized one-time preparation. It will bind `study`,
`world_decision`, `worlds` (flash/blink complete dataclass values), `monitor_scope`, ordered
`roles`, `blink_selected_rows`, `seeds` (calibration 2, screen 32, confirm 512), exact
`panel_genotype_sha256`, `historical_blink_cpu_per_life`, retained Y protocol, selection rule,
primary contrasts, interaction orientation, metadata-only `numerical_identity`, complete retained
`expected_numerical_identity`, `expected_startup_metadata`, local `file_pins` and production
`production_pins`.

Future `registration.json` requires status registered, the exact roles,
`panel_policy=entire_Y_panels_unchanged_regardless_of_AB_outcomes`, seeds, `seed_audit_sha256`, and
`AB_terminal.file_pins` with the root-relative AB terminal budget. No AB success or summary is
required. The seed audit has status passed and the same three-key seeds mapping. Root separately
supplies `resource_clearance.json` and later `ready.json` with complete source/review pins. Neither
source-only preparation nor this schema supplies release authority.

Retained inputs will live at `inputs/Y/inputs/{D90,L92}/` with original genomes.npy, parent.json,
config.yaml, mutation_ops.json and panel_manifest.json. The Y protocol, selection, startup identity,
terminal budget/summary and genetic replay remain under inputs/Y at their original relative paths.
All 130 historical screen NPZs and both complete row_index.json files are copied under
`inputs/Y/measurement/{D90,L92}/`. Only the copied screen rows support rates; unneeded historical
calibration/confirmation entries in the retained row indexes are not treated as copied new data.
`inputs/historical_blink_costs.json` pins each copied timing row. Four derived configurations change
only `life.world` from the retained config; original files remain unchanged.

Runtime rows use unchanged Y `scoring.RowStore` and raw float64[n,58] ABI4 ledgers, uint64 seeds,
scalar genome_index, scalar CPU/wall seconds, JSON identity and 61 production-named columns (58
ledger names plus F_kernel, extinct_charge, window). Named F is production fitness; raw ledger F
remains kernel fitness. Row indexes map stage-relative NPZ paths to exact file SHA256 and CPU
seconds. Stage scores.npz retains seeds, genome_indices and all 61 columns.

The two screen stores are `measurement/screen/{D90,L92}/`, each with calibration/row_0000.npz and
row_0001.npz (two lives), then screen/row_0000.npz through row_0064.npz (32 lives). Identity is
`{protocol_sha256, background, world:"flash", stage, genome_index, genome_sha256, seeds}`. The two
confirmation stores are `measurement/confirm/{flash,blink}/`, each with confirm/row_0000.npz through
row_0005.npz (512 lives). Identity is `{protocol_sha256, world, roles, confirmation_roles_sha256,
stage:"confirm", genome_index, genome_sha256, seeds}`. Role is determined by the fixed ordered role
list and genome_index. All 146 raw rows are retained.

`selection.json` maps D90/L92 to `{genome_row,raw_sha256}`. Runtime `confirmation_genotypes.npz`
contains float32[6,875] genomes and the six ordered roles. `confirmation_roles.json` binds those
roles, their original panel_rows, genotype hashes, selection hash, protocol hash and NPZ file hash.
No duplicate role is removed. Both winners and this table exist before confirmation-cost gating and
before any confirmation life.

`calibration_projection.json` contains flash_batch_max_cpu_per_life, monitored startup_cpu_seconds,
twelve confirmation_role_rates, screen/confirmation projections, fixed thresholds 3390/3790 and
feasible. `confirmation_projection.json` contains the twelve actual selected-row rates, confirmation
projection, threshold3790 and feasible. Both include a cost-uncertainty limitation.

The worker requests `calibration_complete` with protocol hash, validation_lives10, startup identity
hash and row_index_sha256 for screen/D90 and screen/L92. `screens_complete` additionally binds
scientific_genome_lives4160, selection hash, confirmation roles/table hashes and the two expanded
screen indexes. Monitor receipts bind status allowed, protocol/attempt/request hashes, cumulative
CPU, exact row_snapshot and artifact_pins. The calibration receipt freezes startup identity; the
screen receipt freezes selection, both projections and both confirmation role/table files. The
monitor rechecks acknowledged hashes at later boundaries and terminal completion.

Monitor phases are startup_calibration → startup_screen → confirmation, owned by one persistent
two-thread worker. Its OS limit covers the total allocation. `attempt.json.monitor` and persisted
budget process_identities use exactly pid, ppid, pgid, start_ticks (plus a name in the budget). The
live parent checker may inspect sid, but readers must not require sid in persisted receipts. Budget
records cumulative CPU, all three caps, screen-transition CPU, phase receipts, status/reason,
queue/running/completed processes, process groups and release pins. First-attempt artifacts prevent
retries.

Final report requires complete status, exact scope, research_genome_lives10304, validation_lives10,
total_genome_lives10314, summed raw-row CPU, both screen summaries, both confirmation summaries and
four row_index_sha256 entries keyed screen/D90, screen/L92, confirm/flash, confirm/blink. Its
contrasts are named `within__<world>__<A>_minus_<B>` for H−P/B−P/H−B and
`interaction__<A>_minus_<B>` for H−P/H−B. There are 16 contrast groups. Each has paired summaries
for all 61 columns plus bright_captures, capture_income, ordinary_cost, guard_cost, extinction_cost
(66 metrics). Interactions always mean flash minus blink, computed per seed. The independent reader
may retain additional cost-category vectors. It must require complete data and reconcile the exact
report, cost gates, source/seed identities, fixed selection and all original raw rows before issuing
any outcome.

Public Y stores its budget at `operations/budget.json`; the explicit source map copies those exact
bytes to canonical `inputs/Y/budget.json`. Other retained paths preserve their public relative names.
