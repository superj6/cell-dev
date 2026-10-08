"""Run a lattice x breeding x seed matrix for one config, several runs at a time.

    python scripts/sweep.py --config configs/memory.yaml --lattices hex,square4,square8 --breeding sex,asex \
        --seeds 0,1,2,3,4 --jobs 4 --threads 3 --name memory_sweep [key=value ...]

Each run writes to outputs/<name>/<lattice>_<breeding>_s<seed>/; logs go to logs/<name>/ (``--out`` and ``--logs``
move the two roots, e.g. into a scratch directory for a dry run). A failed run is
recorded and the matrix keeps going. Life-mode configs (``mode: life``) prefix the run directory with the
condition (``life.control``), so the full model and its controls can share one sweep name, and each finished run
prints its headline numbers (life: F, size, income, extinction rate and peak size of the best genome). In life mode
``--lattices`` and ``--breeding`` default to the config's own ``lattice.kind`` and ``evolve.breeding``, so a control
config that changes them (square8, asex) is not overridden back to hex / sex.

``--config`` takes several comma-separated configs (equal arms): their runs share the job slots and start in seed
order (arm 1 seed 0, arm 2 seed 0, arm 1 seed 1, ...), so the arms progress together. Life runs record the git
revision and whether the tree was dirty in their results rows; the sweep prints both when it starts.

    python scripts/sweep.py --config configs/life_bell.yaml --seeds 0,1,2 --jobs 3 --threads 3 --name life_pilot
    python scripts/sweep.py --config configs/life_bell.yaml,configs/life_bell_square8.yaml --seeds 0,1 --name pilot
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
from src.run import git_state  # noqa: E402

HEADLINE = dict(trials=("valid_score", "heldout_score", "heldout_no_messages", "n_cells"),
                life=("F", "F_se", "n_cells", "n_peak", "income", "extinction_rate", "msg_reliance", "sense_reliance"))


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


def matrix(arms: list[tuple[str, object]], lattices: str | None, breeding: str | None, seeds: list[str]) -> list[dict]:
    """The runs of a sweep over ``arms`` (config path, loaded config): one arm keeps the lattice x breeding x seed
    order; several arms interleave by seed (arm order within a seed). Raises if two runs would share a directory."""
    per_arm = []
    for path, cfg in arms:
        mode = str(cfg.get("mode", "trials"))
        prefix = f"{cfg.life.get('control', 'full')}_" if mode == "life" else ""
        lats, breeds = axes(lattices, breeding, cfg, mode)
        per_arm.append([dict(config=path, mode=mode, lattice=lat, breeding=b, seed=s, run=f"{prefix}{lat}_{b}_s{s}")
                        for lat, b, s in itertools.product(lats, breeds, seeds)])
    runs = per_arm[0] if len(per_arm) == 1 else [r for s in seeds for runs in per_arm for r in runs if r["seed"] == s]
    names = [r["run"] for r in runs]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise ValueError(f"runs would share an output directory: {dup} (give the arms distinct control or lattice)")
    return runs


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--lattices", default=None, help="default: hex (trials) or the config's lattice.kind (life)")
    p.add_argument("--breeding", default=None, help="default: sex (trials) or the config's evolve.breeding (life)")
    p.add_argument("--seeds", default="0")
    p.add_argument("--jobs", type=int, default=3)
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--name", required=True)
    p.add_argument("--out", default="outputs", help="root of the run directories (relative to the repo or absolute)")
    p.add_argument("--logs", default="logs", help="root of the run logs (relative to the repo or absolute)")
    p.add_argument("overrides", nargs="*")
    args = p.parse_args()
    paths = args.config.split(",")
    arms = [(c, load_config(str(repo_root / c) if not Path(c).is_absolute() else c, args.overrides)) for c in paths]
    runs = matrix(arms, args.lattices, args.breeding, args.seeds.split(","))
    logs = repo_root / args.logs / args.name  # an absolute --logs replaces repo_root
    logs.mkdir(parents=True, exist_ok=True)
    git = git_state()
    print(f"git {git['git_rev']} {'DIRTY' if git['git_dirty'] else 'clean'}; {len(runs)} runs", flush=True)
    pending, running, failed = list(runs), [], []
    while pending or running:
        while pending and len(running) < args.jobs:
            r = pending.pop(0)
            cmd = [sys.executable, "-m", "src.run", "--config", r["config"], f"lattice.kind={r['lattice']}",
                   f"evolve.breeding={r['breeding']}", f"seed={r['seed']}", f"threads={args.threads}",
                   f"logging.output_dir={args.out}/{args.name}/{r['run']}", *args.overrides]
            fh = open(logs / f"{r['run']}.log", "w")
            running.append((r, subprocess.Popen(cmd, cwd=repo_root, stdout=fh, stderr=subprocess.STDOUT), fh))
            print(f"started {r['run']}", flush=True)
        for item in list(running):
            r, proc, fh = item
            if proc.poll() is not None:
                fh.close()
                running.remove(item)
                status = "done" if proc.returncode == 0 else f"FAILED ({proc.returncode})"
                if proc.returncode:
                    failed.append(r["run"])
                summary = headline(repo_root / args.out / args.name / r["run"] / "results.jsonl", r["mode"])
                print(f"{status} {r['run']} {summary}".rstrip(), flush=True)
        time.sleep(2)
    print(f"finished {len(runs)} runs, {len(failed)} failed: {failed}")
