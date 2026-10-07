"""Run evolve_life from the exported tree and snapshot the whole mu+lambda population (parents first, then children)
at chosen generations, exactly as the generation's evaluator sees it (before scoring).

    python grow.py CONFIG OUT_PREFIX --seed S --gens 0 10 30 60 [overrides ...]

Writes OUT_PREFIX_g{G}.npz with genomes [256, 809] float32, the generation's own 3-life F per genome and its seeds.
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

TREE = Path(__file__).resolve().parent / "tree"
sys.path.insert(0, str(TREE))

from src.common import load_config  # noqa: E402
from src.evolve import evolve_life  # noqa: E402
from src.life import evaluate as E  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("config")
    p.add_argument("prefix")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--gens", type=int, nargs="+", required=True)
    p.add_argument("overrides", nargs="*")
    a = p.parse_args()
    targets = set(a.gens)
    over = [f"seed={a.seed}", f"evolve.generations={max(targets) + 1}", "threads=4", "clones.every=0",
            "evolve.heldout_every=100000", *a.overrides]
    cfg = load_config(str(TREE / "configs" / a.config), over)
    tags: dict[tuple, tuple] = {}
    draw0, call0 = E.LifeEvaluator.draw, E.LifeEvaluator.__call__

    def draw(self, purpose, index, *args, **kw):
        d = draw0(self, purpose, index, *args, **kw)
        tags[d.seeds] = (purpose, int(index))
        return d

    def call(self, params, d):
        res = call0(self, params, d)
        purpose, g = tags.get(d.seeds, (None, None))
        if purpose == "gen" and g in targets and params.shape[0] == int(cfg.evolve.mu) + int(cfg.evolve.lam):
            out = Path(f"{a.prefix}_g{g}.npz")
            np.savez_compressed(out, genomes=params.numpy().astype(np.float32), gen_F=res.trial_scores.numpy(),
                                gen_seeds=np.array(d.seeds, dtype=np.uint64), mu=int(cfg.evolve.mu),
                                config=a.config, overrides=json.dumps(a.overrides), seed=a.seed, gen=g,
                                kind=str(cfg.lattice.kind))
            print(json.dumps({"saved": str(out), "gen": g, "best_gen_F": float(res.fitness.max()),
                              "median_n": float(res.n_cells.median())}), flush=True)
        return res

    E.LifeEvaluator.draw, E.LifeEvaluator.__call__ = draw, call
    t0 = time.time()

    def log(row):
        if "gen" in row:
            print(json.dumps({k: row[k] for k in ("gen", "fitness", "mean_fitness", "median_n_cells", "pop_guard",
                                                  "pop_lone", "t_gen") if k in row}), flush=True)
        else:
            print(json.dumps({k: v for k, v in row.items() if not isinstance(v, list)}), flush=True)

    evolve_life(cfg, log=log, out=None)
    print(json.dumps({"done": a.prefix, "wall_s": round(time.time() - t0, 1),
                      "max_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024}), flush=True)


if __name__ == "__main__":
    main()
