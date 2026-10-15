Run the unchanged accountant on committed data:

```sh
.venv/bin/python results/cost_incentives_20261015/al_posthoc/replay_public.py --out outputs/<new-directory>
```

The wrapper selects committed AL data and the unchanged literal-accounting dependency. All five scientific output files match the canonical result bytewise; source-location metadata in the summary reflects the public paths.
