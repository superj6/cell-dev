Static decode accessibility of the 32 frozen inherited genomes. No lives, builds or random draws.

Input SHA256: `56f81eaf0418a6589cca6505d33215c3e1448893d5285b7e909875217a7a6d19`. Script/source pins and all 736 intervals are in [audit.json](audit.json); the same intervals and initial outputs are in [readout_bounds.csv](readout_bounds.csv).

Each active gene varies independently over [0,1] for this bound; inactive slots remain zero. The script uses exact scalar methods extracted from pinned spec.py, preserves float32 genome values and ordered float64 readouts, and independently verifies all extrema at 8,192 cube vertices. Exact rational affine bounds are retained as well. Equal endpoint values prove constancy for the documented nondecreasing discrete decoders. Continuous sigmoid readouts are declared constant only when every active coefficient is zero; floating saturation is not treated as a proof.

| Knob | Genomes proved constant /32 | Constant values (genomes) | Decoded range across all boxes | Initial decoded values |
|---|---:|---|---|---|
| w0 | 0 | — | -0.75…2 | 2 |
| w1 | 0 | — | -2…2 | -0.625, -0.5, -0, 0.125, 0.25, 0.375, 0.875 |
| b | 0 | — | -2…1 | -1.375, -1, -0.75 |
| tau_m | 0 | — | 1…16 | 1, 2 |
| t_ref | 0 | — | 2…4 | 4 |
| emit0 | 0 | — | 0…1 | 1 |
| emit1 | 27 | 0 (27) | 0…1 | 0 |
| delta | 27 | 0 (27) | 0…0.5 | 0 |
| kappa | 0 | — | 0…1 | 0.25, 0.5, 1 |
| p_div | 0 | — | 0…1 | 1 |
| asym | 0 | — | 0.0036652763…0.65211991 | 0.035601497…0.16350027; 23 values |
| p_die | 2 | 0 (2) | 0…0.015625 | 0 |
| phi | 0 | — | 0…2 | 0, 0.5, 1 |
| sec0 | 0 | — | 0.010568335…0.31212246 | 0.03362651, 0.033669698, 0.087739248, 0.090579524, 0.092001755, 0.092693132, 0.092797087, 0.12422522 |
| sec1 | 0 | — | 0.016265025…0.47867034 | 0.13834528…0.25362578; 15 values |
| pol0 | 0 | — | 0.625…2 | 2 |
| pol1 | 0 | — | -1.375…2 | 1.625, 1.75, 1.875 |
| tau_tr | 0 | — | 2…16 | 4 |
| a0 | 0 | — | -2…0.625 | -2, -1.75, -1.625, -1.5, -1.375, -1 |
| a1 | 0 | — | -0.625…2 | 0.875, 1.125, 1.25, 1.375, 1.5, 1.75, 1.875, 2 |
| chi | 0 | — | -2…1.875 | -1, -0.875, -0.75 |
| zeta | 0 | — | -2…2 | 0.5, 1.125, 1.25, 1.375, 1.5, 1.625, 1.875 |
| g_r | 0 | — | -2…2 | 0.125, 0.75, 0.875, 1, 1.625, 1.75 |

These are marginal bounds, not reachable-state measurements. Different readout extrema can require different gene states. Initial outputs describe the zygote before local cues and activity, not the developed tissue. Nonconstant bounds establish available decoded variation in the abstract box, not a functioning sensory pathway. Constant base channel weights can coexist with chemically varying directional gains. Membrane activity, message timing, chemistry, gene recurrence and morphology can retain information even when individual phenotype knobs are constant. This does not test memory lifetime or whole-life neutrality.

No gate, selection change or cell redesign follows. Resource caps are 30 CPU seconds, 60 wall seconds and 512 MiB RSS. A stricter 512 MiB address-space limit was applied, below the authorized 2 GiB ceiling; the process is single-threaded and imports no native simulation/numerical library. Full process usage is recorded externally in resources.txt, with internal accounting in resources.json.
