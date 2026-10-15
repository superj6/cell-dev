# AI source, registration, and audit contract

## Preparation and registration

The draft contains source only. Root may later authorize exactly one `prepare.py --prepare` invocation. Preparation refuses existing inputs, protocol, initialization, preparation/generation claims, or runtime paths. It copies fixed historical inputs and makes one ordinary 32-row initialization; it does not call numerical_identity, compile C, or simulate a life. Failures are preserved and not retried automatically.

`registration.json` must contain:

- `status: "registered"`, `runs: ["control", "reserve"]`, `founder_policy: "fixed_AE_L92_row31"`.
- Root records `study: "AI paired exploratory reserve replication"`; the prepared protocol has the distinct exact study string below.
- `paired_native_seed`: one unsigned 64-bit integer shared deliberately by both arms.
- `confirmation_seeds`: 512 unique unsigned 64-bit integers, excluding the standard golden seed 11.
- `native_seed_audit_sha256`: SHA256 of canonical `seed_audit.json`.
- `AE_complete.file_pins`: public-AE-relative hashes including `protocol.json`, `selection.json`, `operations/budget.json`, `analysis_result/summary.json`, `confirmation_roles.json`, `confirmation_genotypes.npz`, and `startup_identity.json`.
- `AH_terminal.file_pins`: repository-relative hashes including `outputs/autonomous_exploratory_reserve_20261014/budget.json`; root also retains terminal process clearance. Clean terminal status is required, not scientific success.

`seed_audit.json` has `status: "passed"`, the same `paired_native_seed` and `confirmation_seeds`, `run_life_seeds` keyed `control` and `reserve`, and `intentional_overlap`. Each run's list equals that overlap: 64 ordered native life IDs. Each generation contributes seven IDs; generations 0 and 3 also contribute 16 validation IDs; final indices 0 and 1 contribute two IDs each. Half-life final diagnostics reuse index-zero IDs. The confirmation set is disjoint from those 64 IDs and seed 11. Namespace candidates are not reserved by source preparation.

`resource_clearance.json` separately binds prior budget hashes, exact PID/start-tick identities, and owned process groups. Root alone writes readiness after prospective publication and actual-input review.

Canonical copied inputs include `inputs/AE_summary.json`; `inputs/AE/{protocol,selection,budget,startup_identity,confirmation_roles}.json`; `inputs/AE/confirmation_genotypes.npz`; all 65 AE L92 screen NPZs and their row index under their original measurement paths; original Y L92 panel/provenance under `inputs/AE/inputs/Y/inputs/L92/`; and the pinned native U template `inputs/U_template.yaml`. Public AE `operations/budget.json` maps explicitly to `inputs/AE/budget.json`.

`inputs/AE_cost_rows.json` has `rates` (65 CPU-per-life values), `source_pins` (all 65 timed NPZs plus index), and `projection`. The projection records `rates_cpu_per_life`, `max_cpu_per_life`, `startup_search_projection`, `confirmation_projection`, `confirmation_allowance`, `feasible`, and a limitation. All timing identities and raw shapes are checked; no timing-based genotype exclusion occurs.

`inputs/AE_L92.json` is the exact fixed founder. `initialization/L92.npy` is float32 `[32, 875]`: founder plus 31 ordinary two-point copies. `initialization.json` has `status: "pure_genetic_preparation"`, `simulation_calls: 0`, `backgrounds.L92`, and `runs: {"control": "L92", "reserve": "L92"}`. The L92 record contains `population_file`, `file_sha256`, `population_raw_sha256`, generator-before/after hashes, and `copies` with IDs, parent zero, and recorded mutation operations. It is a replay target; each native worker performs the usual initialization with the same seed.

The two configs are `configs/control.yaml` and `configs/reserve.yaml`. They differ only in output path and selection mode. `cfg.exploratory_reserve` contains `mode`, full `policy`, `policy_sha256`, and adapter/driver `source_pins`. The fixed life and search schedule is identical. A root registration does not itself authorize monitor execution.

## Protocol and identity

`protocol.json` fixes `study: "AI fresh-offspring exploratory reserve replication"`, `abi: 3`, `runs`, `paired_native_seed`, `generations: 4`, `reserve_policy`, two `configs`, one `reference_files` path, `founder_mapping.L92`, exact AE `world` and `world_packing`, `AE_protocol_sha256`, the retained base `expected_numerical_identity`, metadata `numerical_identity`, `production_pins`, `cost_projection`, and all study `file_pins`.

Counts are `search_genome_lives: 8268`, `confirmation_genome_lives: 1536`, `planned_genome_lives: 9804`, `startup_validation_genome_lives: 6`. Caps are `max_cpu_seconds: 5400`, `search_cpu_seconds: 3400`, `max_simulation_threads: 4`. `confirmation` fixes labels `AE_L92, AI_control, AI_reserve`, 512 seeds, `threads: 2`, `primary_pairs: [[2,1]]`, and `gain_pairs: [[1,0],[2,0]]`.

Each search calls original numerical_identity once and compares it with the retained AE base. Its checkpoint/determinism identity then adds `external_selection`, exactly equal to that run's configured selection object. Configuration identity also retains this object. Confirmation invokes original numerical_identity once and uses the base identity; it constructs and validates each endpoint's extended search identity without additional calls. The standard full/fast libraries and identity receipts are retained. Production source is unchanged.

## Reserve lottery and durable native evidence

The lottery hashes ASCII `cell-dev:AH:reserve:v1|<seed>|<generation>|<counter>`, with decimal integers and counter starting at zero. The AH domain and complete adapter/search source bytes are deliberately retained for exact policy replication. Interpret the first eight SHA256 bytes as little-endian unsigned integer. Reject values at or above `floor(2^64 / N) * N`, select index `value % N` from the ordered remaining list, remove it, and repeat until two distinct positions are chosen from 32 through 255. No native RNG is consumed. This is active only for reserve generations 0, 1, and 2.

Each native generation retains the usual lineage fields and an `exploratory_reserve` object with `generation`, `mode`, `active`, `policy_sha256`, `reserve_indices`, `base_F` (all 256 exact input fitness values), `ranking_calls`, `shortlist_indices` (64), `pick_positions` (32 positions within the shortlist), `survivor_indices` (32 candidate positions), `candidate_ids` (256), and `reserve_ids`.

There are exactly three recorded ranking calls per generation: diagnostic size 256, shortlist size 256, pooled size 64. Every record contains `size`, exact input `fitness`, returned `order`, `tie_before_sha256`, and `tie_after_sha256`. Exact pooled fitness is recorded because concatenating seven per-life scores before taking their mean need not be bitwise identical to combining rounded three-life and four-life means. An independent reader checks exact tie permutations and ordering, with a tolerance only for that weighted-mean crosscheck.

The adapter wraps the existing lineage writer, so checkpoint prefix hashes and offsets cover policy metadata. No separate sidecar exists. Control and final generation call the original recheck unchanged. Native checkpoint logs retain all recorded mutation/recombination operations. Independent replay reconstructs the complete first 256 candidate bytes in both arms and both final populations without generating new mutations. The live pilot refuses resume; synthetic tests check restored parent IDs, tie state, and policy metadata across an interruption.

## Endpoint and confirmation artifacts

`runs/control/` and `runs/reserve/` contain unchanged native config/checkpoint, curves, lineage, results, final genome, and determinism formats, augmented only by selection identity and lineage metadata. Four ordered generations and zero finite invalid/mismatch summary flags are required. Native periodic/redraw/half-life diagnostics are summarized, not a raw ledger for every search life; do not claim complete raw-status reconciliation of all search calls.

`confirmation/endpoints.json` freezes both complete generation-4 population rank-zero genotypes before scoring. It contains format, labels, seeds, per-label genotype hashes, `endpoints` keyed by arm, protocol SHA, base numerical identity, ready marker, exact legacy world, and the unchanged selection string: `Both complete generation4 final population rank0 endpoints fixed together before confirmation.` Each endpoint pins checkpoint, selected genome file/raw bytes, determinism, complete log hashes, generation, rank, search health, and `selection_identity`. Checkpoint prefixes remain independently checked.

`matched_first_cohort` is one flat record: `initial_population_raw_sha256`, `recorded_genetics_sha256`, `initial_rows: 32`, `candidate_count: 256`, `offspring_count: 224`, `base_F_exact: true`, and a limitation. The genetics digest is SHA256 of `json.dumps(signature, sort_keys=True).encode()`. Signature fields are `founder_ids`, `copies`, and first-generation `children` restricted to `id, pa, pb, mask, ops`. Both signatures and all 256 base scores must match; the independent reader additionally proves all candidate bytes.

`confirmation/genotypes.npz` holds float32 `[3,875]` `genomes` plus ordered `labels`. `confirmation/persistent/row_0000.npz` through `row_0002.npz` have raw float64 `[512,57]` `ledger`, uint64 seeds, genome index, scalar CPU/wall time, canonical JSON identity, all 57 named columns, and `F_kernel`, `extinct_charge`, `window` (60 named arrays). Named F is production-scored; raw ledger column 15 is kernel F. Identity fields are protocol SHA, `stage: "confirmation"`, endpoints SHA, and role. `confirmation/row_index.json` maps each relative row path to `sha256` and `cpu_seconds`. `persistent/scores.npz` holds the same named arrays stacked `[3,512]`, seeds, and indices.

`confirmation/report.json` holds complete status, 1,536 genome lives, 512 paired seeds, two confirmation startup golden lives, protocol/endpoints/genotype hashes, summed raw-row CPU, absolute metrics, `primary` keyed `AI_reserve`, and `gain` keyed `AI_control` and `AI_reserve`. The independent accountant retains 73 paired vectors for each of those three contrasts, including cost categories: 219 vectors. Full-life census uses one initial cell plus births minus deaths minus kills; initial cells are not births. Keep guard/extinction penalties in F and do not impose inequalities across distinct event counters.

## Monitor and terminal review

The inherited AF monitor owns two search groups followed by one confirmation group. It is a child subreaper, charges reaped and live owned-group CPU, and kills/reaps surviving descendants on normal or exceptional exit. Search stops at 3,390 CPU seconds; total stops at 5,390, within hard caps 3,400/5,400. Child limits and parent identity checks remain active. Both search groups must be gone before the phase transition. CPU equality between arms is neither required nor implied by equal life counts.

Persisted process identity has exactly four fields: `pid`, `ppid`, `pgid`, `start_ticks`. The monitor records four leader identities and three owned groups across a complete run. Session checks are live only; no persisted SID proof is claimed. `attempt.json` binds the monitor identity and ready SHA. `budget.json` binds ready, exact completed job names, no active jobs/queue, exit status, total CPU, and `search_stage_cpu_seconds`. All prior resource clearance hashes and identity records are retained. One attempt only, no resume. Terminal root clearance precedes independent full outcome analysis.

The public archive retains all study pins, runtime logs/checkpoints/raw rows, compiled library bytes, analysis, and operational receipts. Repository-relative source dependencies resolve from `production/`; historical dependencies resolve from `original/`; runtime root receipts may be stored under `operations/`. Original source-only prose and every released byte remain unchanged.
