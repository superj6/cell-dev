# Moving-target information: completed

The unchanged external moving-target controller gains **+17.168891 ± 0.217671 F** over the better whole reflex at the same 56-cell footprint. Removing its broad motion model loses **12.958032 ± 0.224547 F**. All seven fixed candidates completed 512 shared fresh T1024 lives (3,584 candidate-lives) in the existing fast, persistent-target ABI 3 world.

| Paired comparison | Mean F difference ± paired SE |
| --- | ---: |
| Full controller − better whole reflex (`retuned`) | +17.168891 ± 0.217671 |
| Full controller − frozen whole reflex | +17.258915 ± 0.218154 |
| Full controller − broad model ablation | +12.958032 ± 0.224547 |
| Best fixed do-less candidate − better whole reflex | +0.341977 ± 0.077174 |

The gain over the better whole reflex comes chiefly from **34.486328 ± 0.446245 extra captures per life**: capture income supplies +16.839027 F, fewer misses +0.383816, and other costs −0.053952. The full controller makes 4.816406 ± 0.554675 fewer total clicks. Reference selection and SE are descriptive and conditional on these fixed candidates; both whole-reference contrasts are retained.

The controller source and parameters are unchanged. Its ablation removes the broad moving-target model, including tracking and action prediction. **Prediction-specific admission will remain incomplete**, even if that broad model helps. This is an information measuring instrument with free central computation, never an evolved organism or a proven performance ceiling.

The study completed on its first attempt in **320.819621 of 3,600 CPU-seconds**, including the 11.558131-second calibration. Readiness was registered only after every U process and owned process group exited; this resource dependency did not depend on U's scientific outcome. All V processes and owned groups have now exited too. Exact terminal records and host checks are retained.

The four fixed calibration lives completed, including compilation/startup, in **11.558130849 CPU-seconds** under the separate 30-second cap. That entire cost carries into the research study's **3,600 CPU-second total**, with at most two workers. Calibration scores are not reported as scientific evidence or used to choose parameters. All four full ledgers and exact compiled library bytes are preserved.

Existing source-bound validation covers 12 exact action replays, differing closed-loop controls, and bounded production-tissue/null-world parity at T64. The twenty-five synthetic preparation tests verify candidate identity, checkpoint integrity/accounting, cumulative budgets, process-group termination, and the resource dependency. The source/config/harness pins still match that evidence.

`PREREG.md` records the question, contrasts, limitations, seeds and stop rules. `original/` preserves exact source inputs and callback replay records; `calibration/` preserves all calibration ledgers. `namespace_inventory.json` retains the exhaustive scan: its sole numerical match is U's excluded half-open boundary, and its malformed JSON entries are named synthetic test fixtures. `namespace_audit.json` records that adjudication.

Validate the preserved preparation without simulation or compilation:

```bash
.venv/bin/python results/prediction_information_20261014/validate_preparation.py
```

The working study is `outputs/autonomous_prediction_information_20261014/`. Public artifacts are evidence snapshots; they are not an instruction to relaunch or rerun calibration. `preparation/` and `prelaunch/` retain the prospective metadata. `rows/` contains complete raw outcomes, and `summary.json` and `independent_contrasts.npz` contain the independent reconstruction.

Preparation was hardened after calibration to bind the exact unchanged library, receipt and calibration rows into the scientific protocol. The original calibration code is preserved under `calibration_original/`; no calibration was repeated and no budget was reset.

Independent review also prompted unconditional cleanup of the entire owned process group after leader exit, Linux subreaper accounting for orphaned descendants, and exact parent-PID checks before a worker starts. These monitor changes are source-pinned; the original calibration monitor remains preserved.

Resume also refuses unresolved cleanup errors or live prior V monitor/worker identities and process groups. Exited U alone cannot authorize overlapping V workers.

The independent NumPy-only analyzer is also frozen before release. Its 33 author tests and 14 independent
tests pass without simulation. It reconstructs all 57 ledger columns and paired comparisons from a complete
first attempt, including exact source/library identities and cumulative CPU accounting. **This pilot will
not resume after any failure.** A later resume would require repaired and reviewed exception-attempt
accounting; that unused path does not affect a complete initial attempt. The original preparation metadata
is preserved in `preparation/`.

Independent analysis reconciles all 57 ledger columns, candidate/source/library identity, seed coverage, and cumulative CPU accounting. Its 33 author and 14 independent synthetic tests pass. The measured information gap and do-less comparisons pass the registered descriptive checks; prediction-specific admission remains incomplete.

Reanalyze raw rows without simulation:

```sh
.venv/bin/python results/prediction_information_20261014/analyze.py --study results/prediction_information_20261014
```
