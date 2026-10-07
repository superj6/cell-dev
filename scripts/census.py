"""Random-genome census per lattice: how many grow, how big, how fast to simulate, and what random search reaches.

    python scripts/census.py --config configs/base.yaml [--samples 2048] [key=value ...]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import torch

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.common import load_config  # noqa: E402
from src.evolve import setup  # noqa: E402
from src.tasks import RUNGS  # noqa: E402

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/base.yaml")
    p.add_argument("--samples", type=int, default=2048)
    p.add_argument("--lattices", default="hex,square4,square8")
    p.add_argument("overrides", nargs="*")
    args = p.parse_args()
    print("| lattice | sites | grew >1 | >=10 cells | median cells | max cells | develop genomes/s | "
          + " | ".join(f"{c.name} best / p99" for c in RUNGS) + " |")
    print("|" + "---|" * (7 + len(RUNGS)))
    for kind in args.lattices.split(","):
        cfg = load_config(args.config, [f"lattice.kind={kind}", *args.overrides])
        torch.set_num_threads(int(cfg.threads))
        lattice, layout, _, ev = setup(cfg)
        gen = torch.Generator().manual_seed(int(cfg.seed))
        params = layout.random(args.samples, gen, float(cfg.genome.init_scale))
        t0 = time.time()
        n = torch.cat([ev.develop(params[i: i + 256]).n_cells for i in range(0, args.samples, 256)]).float()
        rate = args.samples / (time.time() - t0)
        cells = [f"{(n > 1).float().mean():.2f}", f"{(n >= 10).float().mean():.2f}", f"{n.median():.0f}", f"{n.max():.0f}",
                 f"{rate:.0f}"]
        for cls in RUNGS:
            trials = cls(float(cfg.task.length)).sample(lattice.pos, 48, gen, heldout=True)
            s = ev(params, trials).score
            cells.append(f"{s.max():.2f} / {s.quantile(0.99):.2f}")
        print(f"| {kind} | {lattice.n} | " + " | ".join(cells) + " |", flush=True)
