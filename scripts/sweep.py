"""Run a lattice x breeding x seed matrix for one config, several runs at a time.

    python scripts/sweep.py --config configs/memory.yaml --lattices hex,square4,square8 --breeding sex,asex \
        --seeds 0,1,2,3,4 --jobs 4 --threads 3 --name memory_sweep [key=value ...]

Each run writes to outputs/<name>/<lattice>_<breeding>_s<seed>/; logs go to logs/<name>/. A failed run is
recorded and the matrix keeps going. Life-mode configs (``mode: life``) prefix the run directory with the
condition (``life.control``), so the full model and its controls can share one sweep name, and each finished run
prints its headline numbers (life: F, size, income, extinction rate and peak size of the best genome). In life mode
``--lattices`` and ``--breeding`` default to the config's own ``lattice.kind`` and ``evolve.breeding``, so a control
config that changes them (square8, asex) is not overridden back to hex / sex.

    python scripts/sweep.py --config configs/life_bell.yaml --seeds 0,1,2 --jobs 3 --threads 3 --name life_pilot
    python scripts/sweep.py --config configs/life_ctl_messages_off.yaml --seeds 0,1,2 --name life_pilot
"""
from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.common import load_config  # noqa: E402

HEADLINE = dict(trials=("valid_score", "heldout_score", "heldout_no_messages", "n_cells"),
                life=("F", "F_se", "n_cells", "n_peak", "income", "extinction_rate", "msg_reliance"))


def headline(results: Path, mode: str) -> str:
    """The finished run's headline numbers from its results row (mode-aware)."""
    try:
        row = json.loads(results.read_text().splitlines()[-1])
    except (OSError, IndexError, ValueError):
        return ""
    return " ".join(f"{k}={row[k]:.4g}" if isinstance(row.get(k), (int, float)) else f"{k}={row.get(k)}"
                    for k in HEADLINE[mode])


def axes(lattices: str | None, breeding: str | None, cfg, mode: str) -> tuple[list[str], list[str]]:
    """Lattice and breeding axes of the matrix. Unset axes default to hex / sex in trials mode (as before) and to the
    config's own values in life mode."""
    if lattices is None:
        lattices = str(cfg.lattice.kind) if mode == "life" else "hex"
    if breeding is None:
        breeding = str(cfg.evolve.breeding) if mode == "life" else "sex"
    return lattices.split(","), breeding.split(",")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--lattices", default=None, help="default: hex (trials) or the config's lattice.kind (life)")
    p.add_argument("--breeding", default=None, help="default: sex (trials) or the config's evolve.breeding (life)")
    p.add_argument("--seeds", default="0")
    p.add_argument("--jobs", type=int, default=3)
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--name", required=True)
    p.add_argument("overrides", nargs="*")
    args = p.parse_args()
    cfg = load_config(str(repo_root / args.config) if not Path(args.config).is_absolute() else args.config,
                      args.overrides)
    mode = str(cfg.get("mode", "trials"))
    prefix = f"{cfg.life.get('control', 'full')}_" if mode == "life" else ""
    logs = repo_root / "logs" / args.name
    logs.mkdir(parents=True, exist_ok=True)
    lattices, breedings = axes(args.lattices, args.breeding, cfg, mode)
    matrix = list(itertools.product(lattices, breedings, args.seeds.split(",")))
    pending, running, failed = list(matrix), [], []
    while pending or running:
        while pending and len(running) < args.jobs:
            lat, breed, seed = pending.pop(0)
            run = f"{prefix}{lat}_{breed}_s{seed}"
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
                summary = headline(repo_root / "outputs" / args.name / run / "results.jsonl", mode)
                print(f"{status} {run} {summary}".rstrip(), flush=True)
        time.sleep(2)
    print(f"finished {len(matrix)} runs, {len(failed)} failed: {failed}")
