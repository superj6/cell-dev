# Fixed structural-operator comparison

Two preregistered 16-generation searches test silent duplication plus deletion against matched ordinary evolution. Every endpoint is fixed as final population rank zero; both signs and both replicates are retained.

| Contrast | Duration-mixture mean ± SE | >3 SE | ≥0.5 F |
|---|---:|---|---|
| g_s51089_final_rank0 versus d_s51089_final_rank0 | -0.252376 ± 0.209347 | False | False |
| g_s51090_final_rank0 versus d_s51090_final_rank0 | +0.325372 ± 0.193455 | False | False |
| g_s51089_final_rank0 versus founder_row38 | +0.745382 ± 0.188688 | True | True |
| g_s51090_final_rank0 versus founder_row38 | +1.196512 ± 0.191940 | True | True |
| g_s51089_final_rank0 versus pilot_s5 | +1.477254 ± 0.166046 | True | True |
| g_s51090_final_rank0 versus pilot_s5 | +1.928384 ± 0.178708 | True | True |

Each mixture averages T=768, 1024 and 1536 within the same seed before computing SE across 256 fresh shared seeds. Complete production fitness, costs, guards and extinction charges are retained.

Research lives: 37,548; separate neutrality validation: 18. Monitored worker CPU: 10942.922 seconds, within the fixed 14,400-second cap.

This is a two-replicate comparison of duplication, deletion and the existing gene-count-scaled point mutation policy. Active gene count and duplicate ancestry do not establish functional use. Life-level SE does not measure uncertainty across evolutionary searches.

Raw fixed endpoints, complete checkpoints/lineage, all confirmation ledger fields, neutrality evidence and source/numerical pins are preserved. Duplicate confirmation row files are omitted after exact aggregate reconciliation; their original hashes remain in row_index.json.

[Prospective protocol](PREREG.md) · [Preparation](PREPARATION.md)

```sh
.venv/bin/python results/structural_20261013/analyze.py --study results/structural_20261013
```
