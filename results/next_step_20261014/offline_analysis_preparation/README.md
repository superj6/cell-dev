# P offline analysis preparation

This separate bundle prepares the completed-data audit and exporter. It changes none of the 76 artifacts or
manifest in the released P preparation. No active P outcomes were read and no lives were simulated.

The analyzer checks both assigned D founders and full recorded genetics, the new searches and all 18 raw
confirmation rows. Each primary uses the endpoint minus its own D founder and averages durations within seed.
Both signs and production guard/extinction penalties remain. An incomplete study produces no outcome claims.
Export preserves and verifies the original preparation, including retries, and reanalyzes the copied archive
before publishing a final manifest. Raw confirmation CPU cannot exceed cumulative monitored CPU.

Independent review passed all 45 pure/synthetic tests, lint and the 120-column check. The small copied input and
initialization fixtures support the tests; they are the same frozen preparation bytes already published above.

Run the synthetic suite without simulation:

```sh
.venv/bin/python -m pytest -q results/next_step_20261014/offline_analysis_preparation/test_analyze.py --basetemp outputs/audit_p_20261014/public_analysis_tests
```

After the full study completes, reanalyze without simulation:

```sh
.venv/bin/python results/next_step_20261014/offline_analysis_preparation/analyze.py --study outputs/autonomous_next_step_20261014 --out outputs/autonomous_next_step_20261014/analysis
```

Publishing completed results is a separate operation. Source preparation and launch pins stay unchanged.
