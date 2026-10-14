# Whole-life interaction between a copied gene and its source

M measured all four fixed G51090 arms on 512 shared fresh block100 lives at T1024 in fast POOL.
The primary contrast is intact − copy knockout − source knockout + double knockout.
Its paired fitness interaction is **+0.000000 ± 0.000000 SE**.

| Contrast | Paired fitness difference ± SE |
|---|---:|
| Intact − copy_KO | +0.000000 ± 0.000000 |
| Intact − source_KO | +7.276966 ± 0.129090 |
| Intact − double_KO | +7.276966 ± 0.129090 |

Both signs and all three losses remain. The absolute 0.5 F and three-SE flags are descriptive;
an unresolved measurement is not an equivalence proof. Either interaction sign can arise through
development or nonlinear task fitness, so its sign does not categorically establish redundancy.

**G51089:** Disconnected copy; physical and fitness effects analytically zero. No M G51089 life was simulated. See analytical_proof/PROOF.md.
The pre-release rationale is in AMENDMENT.md. The original eight-role
preparation remains under superseded_4096/; it was replaced before M release or measurement.

Completed 2,048 research lives in 410.154069 cumulative
CPU-seconds (cap 1,800; two workers). Two startup golden lives are separate from research and inside CPU.
Guarded and extinct lives retain their ordinary penalties.

measurement/ preserves all raw rows and contrasts; operations/ retains release/resource receipts.
prelaunch/ preserves the complete amended public preparation. summary.json contains independent
genetic replay, exact source/copy mappings, every ledger contrast, costs and morphology.

Recompute without simulation or compilation (Python + NumPy):

```sh
python analyze.py --study . --check
```

Interpretation limits:

- The paired four-arm contrast measures whole-life genetic interaction in the fixed G51090 endpoint.
- Every knockout acts from birth and may change development, morphology, physiology and later computation.
- Either interaction sign may arise from development or nonlinear task fitness; sign alone is not a redundancy label.
- The extant source-origin gene may have changed since duplication; ancestry does not imply identical current roles.
- No intervention isolates an adult gene-specific mechanism, expanded computation or a new algorithm.
- The fixed G51090 endpoint and all effect signs remain; no selection or additional lives follow the result.
- Three-SE and absolute 0.5F flags are descriptive; life-level SE does not describe variability across searches.
- These results do not establish that duplication was necessary for a function to evolve or that its policy is better.
- Independent replay reconstructs recorded genetics, not RNG draws or evolutionary selection.
- Checkpoint hashes and the original checkpoint-validation receipt are retained; this NumPy analyzer does not deserialize checkpoint objects.
