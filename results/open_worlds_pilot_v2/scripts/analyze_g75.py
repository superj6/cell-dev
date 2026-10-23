"""Pilot v2 behaviour check at generation 75: the same tests as analyze_g50.py (fresh seeds 8_300_000 + i)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_g50 import OUT, standout_elites, top_over_generations  # noqa: E402

RUNS = ("D90_Z_s5_LP", "AO_s7_LP", "AO_s7_U")
res = {"top": {}, "elites": []}
for run_name in RUNS:
    res["elites"] += standout_elites(run_name, 75)
    (OUT / "g75.json").write_text(json.dumps(res, indent=1))
for run_name in RUNS:
    res["top"][run_name] = top_over_generations(run_name, (75,))
    print(run_name, "top done", flush=True)
    (OUT / "g75.json").write_text(json.dumps(res, indent=1))
print("done", flush=True)
