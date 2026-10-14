# E7 preparation

This directory preserves reproducible measurement inputs and a preregistration. It contains no new world-admission
result. Full Phase 0 measurements and all evolution launches remain pending a budget report and applicable decisions.

## Bounded validation

From the repository root:

```bash
.venv/bin/python -m scripts.taskvar_replay prediction --out outputs/taskvar_e7/audit
.venv/bin/python -m scripts.taskvar_replay discrimination --out outputs/taskvar_e7/audit
.venv/bin/python -m scripts.taskvar_measure prediction --smoke --audit outputs/taskvar_e7/audit/prediction/audit.json
.venv/bin/python -m scripts.taskvar_measure discrimination --smoke --audit outputs/taskvar_e7/audit/discrimination/audit.json
.venv/bin/python -m scripts.taskvar_gradient --smoke
```

Use a new output directory if an artifact already exists. The replay defaults to two T=64 lives per full/ablated
variant; each recorded stream is replayed in the same life, another life and a different hidden world with real
receptors disabled. Action and requested-wake records compare byte for byte; closed-loop controls must differ.
Callback/action NPZ logs and source hashes are kept beside `audit.json`. Replay logs grow dynamically and abort on
allocation failure rather than silently truncating. The scratch compiler's blob-epoch adapter is measurement only.

Measurements compare 7 fixed candidates on two T=32 lives in smoke mode. They save scores incrementally and output
`incomplete`, even when a large difference appears. Audit and measurement configs, source hashes and harness identity
must match. Guard/capacity/mismatch/incomplete samples are rejected. The production gradient path retains legitimate
compute guards with their fitness penalty and reports their frequency.

The score and gradient commands default to dry-run without `--smoke` or `--run`. A full 512-life measurement is
3,584 candidate-lives; a 256-mutant/64-life screen is 16,448 genome-lives per parent/world. These are budgets to report
before execution. No full run was launched in this pass.

## Offline admission format

`python -m scripts.taskvar_gates path/to/scores.json` reads paired raw fitness arrays. Records identify `world`, `T`,
`seeds`, `tuning_seeds`, `reflex_footprint`, optional `capability`, and named `runs` with `kind`, `footprint`, `F`.
Kinds: `frozen_reflex`, `retuned_reflex`, `information`, `ablation`, `do_less`. Supplied life statuses/end times are
validated; new runners always save them. Information controllers set `privileged=false`, `source_sha256` and a
passing `replay_audit`. Scratch records also need `world_parity_audit` and a matching `harness_identity`.

Ablations name `ablation_of`, `mechanism`, `source_sha256`, full/ablated `params`, `disabled_parameters` indices and
`isolates_capability`. Full and ablated controllers share their source and footprint; only declared parameters may
change. Optional `capability_controller` selects a different information controller for the capability contrast,
including a larger footprint. The primary information gain always uses the reflex footprint. Do-less compares the
best of the explicitly tested variants. No hand-built winner or privileged ceiling can substitute for these tests.

`--g5-worlds base pool ...` aggregates records and requires every listed world at both T=768 and T=1536. Missing
records are incomplete. This is an evidence checker, not an approval or launch mechanism.

## Recovery caveats

- `measurement/*_ctl.c` are unchanged copies of the interrupted PF and D2 sources under `outputs/openhr/`.
- JSON configs preserve recovered parameters and tuning ranges. Their knobs were tuned at ring4/ring5 and are
  transferred to hollow3 for the new own-footprint test. Fresh retuning can improve those lower bounds.
- Prediction's old archive has 8 test lives; its old aggregate used a one-third do-less cutoff and omitted required
  own-footprint/specific checks. Never reuse its `ADMIT` verdict.
- Discrimination's old poison_broad archive has 1,024 lives, but no full-controller hollow3 score or matched ablation.
  It also used the generic scratch epoch defaults. It needs the new parity-checked measurement.
- Old gradient data cover partial 128-mutant screens; several confirmations/worlds are missing. These are recovered
  diagnostics, not the preregistered 256-mutant, all-admitted-world study.
- The prediction ablation removes the moving-target model, including tracking propagation; it cannot support an
  action-only lookahead claim. The conservative config leaves its named capability admission incomplete.
- E9 worlds, G3 wounded selection, G4 calendar work, full G5 and selected-mutant confirmation tooling are pending;
  see `prereg.md`. No production world defaults, ABI or in-life rules were changed by these scripts.
