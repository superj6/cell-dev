"""Check: re-running a snapshot on its own generation's seeds through measure.py's path gives the generation's F.

    python check_repro.py pops/hex_s0_g10.npz
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "tree"))

from src.evolve import setup  # noqa: E402
from src.life.evaluate import LifeDraw  # noqa: E402

import measure  # noqa: E402


def main() -> None:
    src = sys.argv[1]
    name, cfg, params, gen_F, _ = measure.load(src)
    _, _, _, ev = setup(cfg)
    seeds = tuple(int(s) for s in np.load(src)["gen_seeds"])
    d = LifeDraw(seeds, (ev.world(),) * len(seeds))
    col = ev.columns(ev.run(params, d), params.shape[0], d)
    print(name, "max |dF| =", float(np.abs(col["F"] - gen_F).max()), "shape", gen_F.shape)


if __name__ == "__main__":
    main()
