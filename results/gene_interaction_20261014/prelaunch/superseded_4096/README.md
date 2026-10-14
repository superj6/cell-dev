# Source/copy gene interaction — prospective preparation

M compares intact, copied-gene knockout, source-gene knockout and double knockout for both fixed structural-search
endpoints. All eight roles share 512 fresh T1024 fast POOL lives. The primary is the paired four-arm interaction;
every sign, single loss and double loss remains. This measures whole-life genetic interaction, including development.

PREREG.md specifies the design. genomes.json and genotypes.npy freeze the two origin-resolved gene pairs and all
interventions before scoring. seed_audit.json records the independent namespace check. The study uses existing
genome deletion and simulation helpers; preparation adds no simulation and changes no existing pinned source.

Resource scope: 4,096 research lives, 3,600 cumulative CPU-seconds, two workers, waiting for L's complete resource
record. ready.template.json is descriptive and does not release the study. No outcome-dependent extension.

Pure/mock tests and dry-run commands:

```sh
.venv/bin/python -m pytest -q outputs/autonomous_gene_interaction_20261014/test_measure.py outputs/autonomous_gene_interaction_20261014/test_monitor.py --basetemp outputs/audit_m_20261014/prepared_tests
.venv/bin/python outputs/autonomous_gene_interaction_20261014/measure.py
.venv/bin/python outputs/autonomous_gene_interaction_20261014/run_budgeted.py
```

The eventual monitored command requires a separately released ready.json:

```sh
.venv/bin/python outputs/autonomous_gene_interaction_20261014/run_budgeted.py --run
```

This public preparation includes source snapshots and the exact completed-G inputs used for genetic replay.
The launcher uses original repository paths; the archive does not itself schedule work. No scientific result is
present yet. A later independent completed-data export must preserve this preparation and audit every raw row.
