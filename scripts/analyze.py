"""Knockouts for a saved organism on every rung, plus a PNG map of which cells matter.

    python scripts/analyze.py outputs/ladder_hex_sex_s0 [--rungs light,memory]

Columns: base score; with messages off; with cell types shuffled among the cells; best single-type tissue; how many
cells are essential (removing one costs > 0.05). The map shades each cell by the score lost when it is removed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from omegaconf import OmegaConf  # noqa: E402
from PIL import ImageDraw  # noqa: E402

from src.evolve import setup  # noqa: E402
from src.genome import Layout  # noqa: E402
from src.measure import knockouts  # noqa: E402
from src.render import SCALE, _cell_polygon, _to_px, draw  # noqa: E402
from src.tasks import build_task  # noqa: E402


def importance_png(lattice, tissue, drop, path, title):
    img = draw(lattice, tissue.alive[0], tissue.types[0], caption=title)
    d = ImageDraw.Draw(img, "RGBA")
    size = int(2 * (lattice.radius + 1.5) * SCALE)
    top = float(drop.max()) if float(drop.max()) > 0 else 1.0
    for i in tissue.alive[0].nonzero()[:, 0].tolist():
        a = max(0.0, float(drop[i])) / top
        if a > 0:
            poly = _to_px(lattice, _cell_polygon(lattice, tuple(lattice.pos[i].tolist())), size)
            d.polygon(poly, fill=(200, 0, 0, int(220 * a)))
    img.save(path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("run_dir")
    p.add_argument("--rungs", default=None, help="comma list; default: the run's task, or its ladder rungs")
    args = p.parse_args()
    run = Path(args.run_dir)
    cfg = OmegaConf.load(run / "config.yaml")
    _, params = Layout.load(run / "best_genome.json")
    lattice, layout, _, ev = setup(cfg)
    gen = torch.Generator().manual_seed(7)
    tissue = ev.develop(params.reshape(1, -1))
    print(f"{run.name}: {int(tissue.n_cells[0])} cells on {lattice.kind}\n")
    print("| rung | score | messages off | shuffled types | one type | essential cells |")
    print("|---|---|---|---|---|---|")
    if args.rungs:
        names = args.rungs.split(",")
    elif cfg.task.name == "ladder":
        names = list(cfg.task.get("rungs") or ["light", "brightness", "memory", "motion", "flicker"])
    else:
        names = [cfg.task.name]
    for name in names:
        trials = build_task(name, float(cfg.task.length)).sample(lattice.pos, int(cfg.task.heldout_trials), gen,
                                                                 heldout=True)
        ko = knockouts(ev, params, trials, gen)
        print(f"| {name} | {ko['base']:+.2f} | {ko['no_messages']:+.2f} | {ko['shuffled_types']:+.2f} | "
              f"{ko['one_type_best']:+.2f} | {ko.get('essential_cells')} |")
        importance_png(lattice, tissue, ko["knockout_map"], run / f"importance_{name}.png",
                       f"{name}: red = score lost when the cell is removed")
