"""Score every genome of a 256-genome population on N lives with seeds shared across the population (common random
numbers, as in a real generation), in the exported tree's kernel. Writes a genomes x lives matrix of F plus kernel
events, end size and status per life.

    python measure.py pops/hex_s0_g10.npz [--lives 128]
    python measure.py smoke:/path/to/run_dir [--lives 128]     # a saved 32-parent population: the 224 children are bred
                                                               # with the run's own crossover and mutation operators
Writes meas/<name>.npz.
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
import zlib
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
TREE = HERE / "tree"
sys.path.insert(0, str(TREE))

from omegaconf import OmegaConf  # noqa: E402
from src.common import load_config  # noqa: E402
from src.evolve import setup  # noqa: E402
from src.life import build, handbuilt, spec  # noqa: E402
from src.life.evaluate import LifeDraw  # noqa: E402

STUDY_SEED = 20261007
STREAM = 0x53454C53  # "SELS": far from every stream the runs use
CHUNK = 8  # lives per kernel call (x 256 genomes = 2048 lives)


def breed(cfg, layout, pop: torch.Tensor, seed: int) -> torch.Tensor:
    """One generation's children of ``pop`` exactly as evolve_life breeds them (crossover by gene unit, then the
    run's mutation operator); returns parents then children."""
    e = cfg.evolve
    mu, lam = int(e.mu), int(e.lam)
    gen = torch.Generator().manual_seed(seed)
    mut_kw = dict(dup_rate=float(e.get("dup_rate", 0.0)), del_rate=float(e.get("del_rate", 0.0)),
                  split=bool(e.get("dup_split", False)), scale_n_mut=bool(e.get("n_mut_scale", True)))
    ia = torch.randint(mu, (lam,), generator=gen)
    if e.breeding == "sex":
        ib = torch.randint(mu, (lam,), generator=gen)
        kids = layout.crossover(pop[ia], pop[ib], gen)
    else:
        kids = pop[ia].clone()
    kids = layout.mutate(kids, gen, int(e.n_mut), float(e.p_cell), ops=[], slot_use=layout.active(pop).sum(0),
                         **mut_kw)
    return torch.cat([pop, kids])


def load(src: str):
    """(name, cfg, genomes [256, 809], gen_F or None, meta)."""
    if src.startswith("smoke:"):
        run = Path(src[len("smoke:"):])
        cfg = OmegaConf.load(run / "config.yaml")
        cfg.threads = 4
        _, layout, _, _ = setup(cfg)
        payload = json.loads((run / "population.json").read_text())
        pop = torch.stack([layout.from_dict(d) for d in payload["genomes"]])
        everyone = breed(cfg, layout, pop, seed=STUDY_SEED + int(cfg.seed))
        name = f"smoke40_{run.name}"
        return name, cfg, everyone, None, {"source": str(run), "gen": int(cfg.evolve.generations),
                                           "kind": str(cfg.lattice.kind), "bred_children": True}
    z = np.load(src)
    over = [f"seed={int(z['seed'])}", "threads=4", *json.loads(str(z["overrides"]))]
    cfg = load_config(str(TREE / "configs" / str(z["config"])), over)
    name = Path(src).stem
    return name, cfg, torch.from_numpy(z["genomes"]), z["gen_F"], {"source": src, "gen": int(z["gen"]),
                                                                    "kind": str(z["kind"]), "bred_children": False}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("--lives", type=int, default=128)
    p.add_argument("--out", default=str(HERE / "meas"))
    a = p.parse_args()
    torch.set_num_threads(1)
    name, cfg, params, gen_F, meta = load(a.src)
    cfg.threads = 4
    _, layout, _, ev = setup(cfg)
    B, N = params.shape[0], a.lives
    key = zlib.crc32(name.encode())
    seeds = [spec.hash64(STUDY_SEED, STREAM, key, life) for life in range(N)]
    world = ev.world()
    cols = {k: np.zeros((B, N)) for k in ("F", "events", "n_end", "n_peak")}
    flags = {k: np.zeros((B, N), dtype=bool) for k in ("guard", "invalid", "extinct")}
    t0 = time.time()
    for i in range(0, N, CHUNK):
        d = LifeDraw(tuple(seeds[i:i + CHUNK]), (world,) * len(seeds[i:i + CHUNK]))
        col = ev.columns(ev.run(params, d), B, d)
        for k in cols:
            cols[k][:, i:i + d.n] = col[k]
        for k in flags:
            flags[k][:, i:i + d.n] = col[k]
        print(json.dumps({"pop": name, "lives_done": i + d.n, "s": round(time.time() - t0, 1)}), flush=True)
    lone = build.run(replace(world, flags=world.flags | handbuilt.PROGRAM_MODE), seeds,
                     programs=handbuilt.lone(handbuilt.LONE_BEST).program, threads=4)
    lone_F = lone.ledger[:, spec.L["F"]].astype(np.float64)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / f"{name}.npz", **cols, **flags, lone_F=lone_F, seeds=np.array(seeds, dtype=np.uint64),
                        gen_F=np.zeros((0,)) if gen_F is None else gen_F, mu=int(cfg.evolve.mu),
                        meta=json.dumps(meta))
    Fm = cols["F"].mean(1)
    print(json.dumps({"done": name, "wall_s": round(time.time() - t0, 1), "lives": B * N,
                      "best_trueF": float(Fm.max()), "lone_F": float(lone_F.mean()),
                      "n_beat_lone": int((Fm > lone_F.mean() + 0.001).sum()),
                      "median_n_end": float(np.median(cols["n_end"])), "guard": float(flags["guard"].mean()),
                      "invalid": float(flags["invalid"].mean()),
                      "max_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024}), flush=True)


if __name__ == "__main__":
    main()
