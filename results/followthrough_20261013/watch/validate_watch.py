"""Four fixed T32 JS/C parity checks plus synthetic UI checks; explicit --simulate required."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")
ROOT = next(path for path in Path(__file__).resolve().parents if (path / "src/life/spec.py").exists())
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulate", action="store_true")
    args = parser.parse_args()
    result = subprocess.run(["node", str(HERE / "test_watch.js")], capture_output=True, text=True, check=True)
    report = {"ui": json.loads(result.stdout), "browser_visual_inspection": "unavailable; no browser binary installed"}
    if not args.simulate:
        print(json.dumps(report, indent=2))
        return
    workers = 0
    for relative in ("autonomous_followthrough_20261013/budget_ab.json",
                     "autonomous_followthrough_20261013/budget_factorial.json",
                     "autonomous_continuation_20261013/budget.json"):
        path = ROOT / "outputs" / relative
        if path.exists():
            record = json.loads(path.read_text())
            for pid in record.get("running", {}):
                if Path(f"/proc/{pid}").exists():
                    workers += 2
    if workers > 3:
        raise RuntimeError(f"defer bounded validation: {workers} scientific workers are active")
    import numpy as np

    from src.life import build, spec

    data = json.loads((HERE / "bodies.json").read_text())
    cases = []
    for name in ("pool", "base"):
        overrides = {"sigma": 0.4, "lam_s": 4.0} if name == "pool" else {}
        world = spec.world("catch_speck_l4", T=32, d0=0.5, d_min=0.25, **overrides)
        for body in data["bodies"]:
            result = build.run(world, [data["default_seed"]], genomes=np.asarray([body["genome"]]),
                               abi=spec.V3, kind="hexprism", threads=1)
            cases.append({"world": name, "body": body["name"], "seed": data["default_seed"], "T": 32,
                          "ledger": {key: repr(float(result.ledger[0, i])) for i, key in enumerate(spec.V3.LEDGER)},
                          "hashes": {key: f"{int(value):016x}" for key, value in
                                     zip(spec.V3.HASHES, result.hashes[0])}})
    (HERE / "truth_T32.json").write_text(json.dumps(cases, indent=2) + "\n")
    result = subprocess.run(["node", str(HERE / "verify_parity.js")], capture_output=True, text=True, check=True)
    report.update(parity=json.loads(result.stdout), kernel_lives=4, browser_engine_lives=4, duration=32,
                  default_seed=data["default_seed"], active_scientific_workers_before_check=workers,
                  html_sha256=hashlib.sha256((HERE / "watch.html").read_bytes()).hexdigest(),
                  engine_sha256=data["engine_sha256"], scope="Short validation only; no claim of new long-life parity.")
    (HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
