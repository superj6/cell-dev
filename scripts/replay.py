"""Re-grow a saved organism, score it, and write growth / activity GIFs, optionally on another lattice or task.

    python scripts/replay.py outputs/ladder_hex_sex_s0 [--task motion] [--lattice square8] [--trials 4]

Genomes do not reference the lattice, so ``--lattice`` tests how a design "ports" to a different fabric.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from omegaconf import OmegaConf  # noqa: E402

from src.cells import decode_cells, run_cells  # noqa: E402
from src.evolve import setup  # noqa: E402
from src.genome import Layout  # noqa: E402
from src.render import activity_gif, development_gif  # noqa: E402
from src.tasks import build_task  # noqa: E402

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("run_dir")
    p.add_argument("--task", default=None, help="task to show (default: the run's task; ladder shows every rung)")
    p.add_argument("--lattice", default=None)
    p.add_argument("--trials", type=int, default=2)
    p.add_argument("--out", default=None)
    args = p.parse_args()
    run = Path(args.run_dir)
    cfg = OmegaConf.load(run / "config.yaml")
    if args.lattice:
        cfg.lattice.kind = args.lattice
    _, params = Layout.load(run / "best_genome.json")
    lattice, layout, _, ev = setup(cfg)
    best = params.reshape(1, -1)
    out = Path(args.out or run / "replay")
    out.mkdir(parents=True, exist_ok=True)
    tissue = ev.develop(best, record=True)
    development_gif(lattice, tissue.history, out / f"growth_{lattice.kind}.gif")
    print(f"{lattice.kind}: {int(tissue.n_cells[0])} cells, {int(tissue.types[0][tissue.alive[0]].unique().numel())} types")
    task_name = args.task or cfg.task.name
    default_rungs = ["light", "brightness", "memory", "motion", "flicker"]
    names = list(cfg.task.get("rungs") or default_rungs) if task_name == "ladder" else [task_name]
    gen = torch.Generator().manual_seed(123)
    rule = decode_cells(layout, best, cfg.cells.quantize)
    for name in names:
        task = build_task(name, float(cfg.task.length))
        scored = task.sample(lattice.pos, int(cfg.task.heldout_trials), gen, heldout=True)
        res = ev(best, scored)
        print(f"  {name:10s} held-out score {float(res.score[0]):+.3f}  energy {float(res.energy[0]):.3f}")
        shown = task.sample(lattice.pos, args.trials, gen, heldout=True)
        act = run_cells(lattice, tissue.alive, tissue.types, rule, shown.stim, shown.window, record=True,
                        messages=bool(cfg.cells.get("messages", True)))
        for e in range(args.trials):
            activity_gif(lattice, tissue.alive[0], tissue.types[0], act.raster[:, 0, e], shown.stim[e], shown.window[e],
                         shown.target[e], out / f"{name}_{lattice.kind}_{e}.gif", label=name)
    print(f"GIFs in {out}")
