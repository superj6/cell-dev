Prepared F discrimination measurement. No scientific or new validation lives have run.

Fixed design:7 candidates×512 shared block30 lives,T1024,old SPECK conduction,2 workers,1,800 cumulative CPU-s.
The controller and audited measurement/harness sources are unchanged. See prereg_draft.txt before release.

Preparation and dry run (no simulation/compilation):
  .venv/bin/python outputs/autonomous_discrimination_20261013/measure.py --prepare
  .venv/bin/python outputs/autonomous_discrimination_20261013/measure.py
  .venv/bin/python outputs/autonomous_discrimination_20261013/run_budgeted.py

Focused tests (synthetic arrays and mocked processes only):
  .venv/bin/python -m pytest -q outputs/autonomous_discrimination_20261013/test_prepared.py
  .venv/bin/ruff check outputs/autonomous_discrimination_20261013/*.py

Root release: report/register F, freeze the scripts, and write ready.json as the exact object
  {"protocol.json":SHA256(protocol.json),"measure.py":SHA256(measure.py),
   "run_budgeted.py":SHA256(run_budgeted.py)}
No ready.json is prepared automatically. After two worker slots are free:
  .venv/bin/python outputs/autonomous_discrimination_20261013/run_budgeted.py --run

After a finalized interruption or failure, the same command with --resume verifies pins and reuses committed
candidates within the original remaining CPU budget. Interrupt the monitor with SIGINT/SIGTERM for a finalized
accounting record. Unexpected monitor death kills its worker; a running/unfinalized budget record refuses
automatic resume because consumed CPU is not reconciled. Completed studies cannot be rescored. Interrupted
uncommitted candidates may repeat; committed candidate directories never do.

Artifacts after launch:protocol/ready/library/manifest identity records;budget.json across all attempts;
rows/<candidate>/{row.npz,checkpoint.json};scores.json for the unchanged admission checker;admission.json;
report.json with paired fitness/accounting readouts;measurement.log. Atomic row NPZs preserve every ledger
column,controller diagnostics,latency,exact candidate/seeds/manifest identity,and timing. The fast build produces
zero event hashes; recorded SHA256 hashes validate saved bytes and are not represented as event replay evidence.

Strict report interpretation: a broad decoy-model effect may combine better ping interpretation, steering and
tap veto. The inherited tuning footprint differs from the scored hollow3 footprint; do-less coverage is three
fixed candidates. A result never launches a selection world, proves a local circuit can achieve it, or supplies
G0/G2–G5. Prediction's nonisolating ablation is outside this study.
