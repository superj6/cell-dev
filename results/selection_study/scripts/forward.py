"""Multi-generation check of selection schemes: from a saved population's 32 parents, run G generations of evolve_life's
breeding (crossover by gene unit + the run's mutation operator, same generator calls) with selection by scheme A
(3 shared lives), B (3 lives, then the top K rescored on L2 more shared lives; key 1 = all lives, 2 = recheck only)
or C (n lives for all), then score the final 32 parents on 64 fresh shared lives.

    python forward.py SRC OUT --gens 20 --reps 0 1 2 3 --schemes A B2:64:4 C:4

SRC is a pops/*.npz snapshot (its first 32 genomes are the parents) or smoke:<run dir>. Every scheme of one
replicate starts from the same parents with the same breeding generator seed and the same generation lives.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import zlib
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tree"))
sys.path.insert(0, str(HERE))

from src.evolve import setup  # noqa: E402
from src.life import spec  # noqa: E402
from src.life.evaluate import LifeDraw  # noqa: E402

import measure  # noqa: E402

STREAM = 0x46575244  # "FWRD"


def lives(world, key: int, *idx: int, n: int) -> LifeDraw:
    seeds = tuple(spec.hash64(measure.STUDY_SEED, STREAM, key, *idx, life) for life in range(n))
    return LifeDraw(seeds, (world,) * n)


def run(cfg, layout, ev, parents: torch.Tensor, scheme: str, rep: int, gens: int, key: int,
        first: torch.Tensor | None = None, checkpoints: tuple = ()) -> list[tuple]:
    """``first``: a whole mu+lambda population that generation 0 selects from without breeding. Returns
    (generations done, parents, extra lives so far) after ``gens`` and at each checkpoint."""
    e = cfg.evolve
    mu, lam = int(e.mu), int(e.lam)
    gen = torch.Generator().manual_seed(1000 + rep)
    mut_kw = dict(dup_rate=float(e.get("dup_rate", 0.0)), del_rate=float(e.get("del_rate", 0.0)),
                  split=bool(e.get("dup_split", False)), scale_n_mut=bool(e.get("n_mut_scale", True)))
    world, pop, extra, out = ev.world(), parents.clone(), 0, []
    parts = scheme.split(":")
    for g in range(gens):
        if g == 0 and first is not None:
            everyone = first
        else:
            ia = torch.randint(mu, (lam,), generator=gen)
            ib = torch.randint(mu, (lam,), generator=gen)
            kids = layout.crossover(pop[ia], pop[ib], gen)
            kids = layout.mutate(kids, gen, int(e.n_mut), float(e.p_cell), ops=[],
                                 slot_use=layout.active(pop).sum(0), **mut_kw)
            everyone = torch.cat([pop, kids])
        if parts[0] == "C":
            n = int(parts[1])
            f = ev(everyone, lives(world, key, rep, g, n=n)).fitness
            extra += everyone.shape[0] * (n - 3)
            order = f.argsort(descending=True, stable=True)[:mu]
        else:
            f = ev(everyone, lives(world, key, rep, g, n=3)).fitness
            order = f.argsort(descending=True, stable=True)
            if parts[0] in ("B1", "B2"):
                K, L2 = int(parts[1]), int(parts[2])
                sl = order[:K]
                d2 = lives(world, key, rep, g, n=3 + L2)
                d2 = LifeDraw(d2.seeds[3:], d2.worlds[3:])  # the next L2 lives of the same generation stream
                r = ev(everyone[sl], d2).fitness
                k = r if parts[0] == "B2" else (3 * f[sl] + L2 * r) / (3 + L2)
                order = sl[k.argsort(descending=True, stable=True)]
                extra += K * L2
            order = order[:mu]
        pop = everyone[order]
        if g + 1 in checkpoints or g + 1 == gens:
            out.append((g + 1, pop, extra))
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("out")
    p.add_argument("--gens", type=int, default=20)
    p.add_argument("--reps", type=int, nargs="+", default=[0, 1, 2, 3])
    p.add_argument("--schemes", nargs="+", default=["A", "B2:64:4", "C:4"])
    p.add_argument("--final_lives", type=int, default=64)
    p.add_argument("--select_first", action="store_true", help="generation 0 selects from SRC's whole population")
    p.add_argument("--checkpoints", type=int, nargs="*", default=[], help="also score the parents after these gens")
    a = p.parse_args()
    torch.set_num_threads(1)
    name, cfg, everyone, _, meta = measure.load(a.src)
    cfg.threads = 4
    _, layout, _, ev = setup(cfg)
    parents = everyone[: int(cfg.evolve.mu)]
    key = zlib.crc32(name.encode())
    rows = []
    for rep in a.reps:
        for sc in a.schemes:
            t0 = time.time()
            for g, pop, extra in run(cfg, layout, ev, parents, sc, rep, a.gens, key,
                                     first=everyone if a.select_first else None, checkpoints=tuple(a.checkpoints)):
                idx = (999_999, rep) if g == a.gens else (999_998, rep, g)  # shared across schemes of a rep
                fin = ev(pop, lives(ev.world(), key, *idx, n=a.final_lives))
                ts = fin.trial_scores.numpy()
                row = dict(src=name, rep=rep, scheme=sc, gens=g, extra_lives=extra,
                           mean_F=float(ts.mean()), rank0_F=float(ts[0].mean()), best_F=float(ts.mean(1).max()),
                           per_genome=[float(x) for x in ts.mean(1)],
                           median_n=float(np.median(fin.n_cells.numpy())),
                           body_share=float((fin.n_cells.numpy() >= 1.5).mean()), s=round(time.time() - t0, 1))
                rows.append(row)
                print(json.dumps({k: v for k, v in row.items() if k != "per_genome"}), flush=True)
    Path(a.out).write_text(json.dumps(rows))


if __name__ == "__main__":
    main()
