"""Run a lattice x breeding x seed matrix for one config, several runs at a time.

    python scripts/sweep.py --config configs/memory.yaml --lattices hex,square4,square8 --breeding sex,asex \
        --seeds 0,1,2,3,4 --jobs 4 --threads 3 --name memory_sweep [key=value ...]

Each run writes to outputs/<name>/<lattice>_<breeding>_s<seed>/; logs go to logs/<name>/. A failed run is
recorded and the matrix keeps going.
"""
from __future__ import annotations

import argparse
import itertools
import subprocess
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--lattices", default="hex")
    p.add_argument("--breeding", default="sex")
    p.add_argument("--seeds", default="0")
    p.add_argument("--jobs", type=int, default=3)
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--name", required=True)
    p.add_argument("overrides", nargs="*")
    args = p.parse_args()
    logs = repo_root / "logs" / args.name
    logs.mkdir(parents=True, exist_ok=True)
    matrix = list(itertools.product(args.lattices.split(","), args.breeding.split(","), args.seeds.split(",")))
    pending, running, failed = list(matrix), [], []
    while pending or running:
        while pending and len(running) < args.jobs:
            lat, breed, seed = pending.pop(0)
            run = f"{lat}_{breed}_s{seed}"
            cmd = [sys.executable, "-m", "src.run", "--config", args.config, f"lattice.kind={lat}",
                   f"evolve.breeding={breed}", f"seed={seed}", f"threads={args.threads}",
                   f"logging.output_dir=outputs/{args.name}/{run}", *args.overrides]
            fh = open(logs / f"{run}.log", "w")
            running.append((run, subprocess.Popen(cmd, cwd=repo_root, stdout=fh, stderr=subprocess.STDOUT), fh))
            print(f"started {run}", flush=True)
        for item in list(running):
            run, proc, fh = item
            if proc.poll() is not None:
                fh.close()
                running.remove(item)
                status = "done" if proc.returncode == 0 else f"FAILED ({proc.returncode})"
                if proc.returncode:
                    failed.append(run)
                print(f"{status} {run}", flush=True)
        time.sleep(2)
    print(f"finished {len(matrix)} runs, {len(failed)} failed: {failed}")
