# Local gene-regulation inputs with cell structure held constant

Three fixed genotypes share 512 fresh seeds across three interventions. Both final 16-generation
D descendants are retained. Interventions begin at 768; common accounting covers 800..1536.

| Fixed endpoint | Added GRN-input dependence, ΔF ± SE | Descriptive 3-SE flag |
|---|---:|---|
| d_s51089_final_rank0 | +2.849005 ± 0.174679 | positive |
| d_s51090_final_rank0 | +2.939516 ± 0.176084 | positive |

The primary difference is `(endpoint−row38)structure − (endpoint−row38)structure+genes_blind`.
Subtraction happens within each life before uncertainty is calculated over 512 paired seeds.
All three arms stop new division and apoptosis decisions. The first keeps normal gene regulation;
the second masks five local GRN inputs; full freeze also stops gene/phenotype/effective-weight updates.
Ordinary receptor events, neuron firing, spike messages, morphogens and plane cues remain.

| Contrast | ΔF ± SE |
|---|---:|
| d s51089 final rank0: gain: structure | +0.851021 ± 0.173529 |
| d s51089 final rank0: gain: structure+genes blind | -1.997984 ± 0.036972 |
| d s51089 final rank0: gain: freeze | +0.671842 ± 0.194392 |
| d s51089 final rank0: added input dependence | +2.849005 ± 0.174679 |
| d s51089 final rank0: added regulation effect | +0.179178 ± 0.218864 |
| d s51090 final rank0: gain: structure | +1.094272 ± 0.172768 |
| d s51090 final rank0: gain: structure+genes blind | -1.845244 ± 0.040224 |
| d s51090 final rank0: gain: freeze | +0.601159 ± 0.196851 |
| d s51090 final rank0: added input dependence | +2.939516 ± 0.176084 |
| d s51090 final rank0: added regulation effect | +0.493113 ± 0.230494 |
| founder row38: input loss | +10.325559 ± 0.135165 |
| founder row38: regulation effect | +0.110515 ± 0.143611 |
| d s51089 final rank0: input loss | +13.174564 ± 0.155021 |
| d s51089 final rank0: regulation effect | +0.289694 ± 0.164771 |
| d s51090 final rank0: input loss | +13.265075 ± 0.146261 |
| d s51090 final rank0: regulation effect | +0.603628 ± 0.179574 |

All 16 contrasts include independently reconstructed income, each ordinary cost, guard and
extinction contributions with paired SEs in `summary.json`. These pieces sum within each seed.

All 4,608 research genome-lives completed in 2283.250535 monitored CPU-seconds (cap 3,600).
Two existing T200 numerical-identity golden lives are separate validation inside that cap.
Complete guard-free constant-structure triplets: [512, 512, 512], in row38 / D51089 / D51090 order.
Guard/extinct exclusions apply only to structural validation; every valid fitness row is retained.

`measurement/` preserves all nine full raw checkpoints, aggregates, paired vectors and reports.
`inputs/`, `sources/`, `dependencies/` and `operations/` preserve genomes, source and resource
receipts.
`motivation_H/` binds these fixed inputs to the completed H archive and original D provenance.
`prelaunch/` preserves the complete original preparation without changing its pinned bytes.

Recompute without simulation or compilation (Python + NumPy; Matplotlib only for `--plot`):

```bash
python analyze.py --study . --check
```

Interpretation limits:

- The intervention masks local GRN inputs 18–22: own/incoming spike traces, contact fraction and receptor trace.
- Current genes, morphogens and sense/act plane cues remain; ordinary neuron receptor events and spikes continue.
- This tests ongoing dependence on specified local GRN inputs, not memory or a new algorithm.
- The mask also removes static contact information; a loss alone does not establish adaptation or use of changing evidence.
- Structure-minus-freeze also includes phenotype and effective-weight updates; it is not a pure GRN-state test.
- Both fixed descendants retain their different footprints and pre-fork states; there is no matched-body claim.
- Pending pre-fork events settle before 800, but this does not erase earlier membrane, chemical or world history.
- Structural checks compare terminal counts and cell-time, not equality of complete internal states.
- Both descendants and signs are retained. Three-SE flags are descriptive; unresolved effects are not zero.
- Life-level SE describes these fixed genotypes on 512 shared seeds, not uncertainty across evolution replicates.
- Guards/extinction retain production penalties. Only complete guard-free triplets enter structural checks.
- Fitness, captures and additive costs use 800..1536; path, last birth and terminal counts describe whole lives.
