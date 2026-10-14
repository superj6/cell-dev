"""E7/G2 mutant screen on the production ABI 3 base and POOL worlds.

Default is a dry run. --smoke runs 4 mutants x 2 lives at T=32. --run executes
the specified screen, saving every genome row under outputs/ for restart.
Worlds needing the unapproved ABI 4 port remain pending; this never treats
missing worlds or screen winners as an admission decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

# Same pin as src.run; must precede torch's first CPU dispatch.
os.environ.setdefault("ATEN_CPU_CAPABILITY", "avx2")

import numpy as np
import torch
from omegaconf import OmegaConf

from scripts.taskvar_gates import gradient_report, validate_lives
from src.checkpoint import numerical_identity
from src.genome import Layout
from src.life import analysis, build, spec
from src.life.evaluate import LifeDraw, LifeEvaluator

ROOT = Path(__file__).resolve().parents[1]
COLS = ("F", "F_kernel", "extinct_charge", "n_end", "clicks", "captures", "income", "cost", "live_time",
        "spikes", "packets", "status", "t_end")


def make_mutants(path: Path, count: int, seed: int):
    layout, parent = Layout.load(str(path))
    parent = parent.reshape(-1).float()
    ops = []
    mutants = layout.mutate(parent[None].repeat(count, 1), torch.Generator().manual_seed(seed), 2, 0.5,
                            dup_rate=0.0, del_rate=0.0, split=False, scale_n_mut=True,
                            slot_use=layout.active(parent[None]).sum(0), ops=ops)
    return torch.cat((parent[None], mutants)).numpy(), ops


def atomic_json(path: Path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def run_screen(path: Path, out: Path, name: str, n_mut: int, n_lives: int, duration: float,
               mutation_seed: int, seed_block: int, threads: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    identity = numerical_identity()
    genomes, ops = make_mutants(path, n_mut, mutation_seed)
    cfg_path = path.parent / "config.yaml"
    cfg = OmegaConf.load(cfg_path)
    evaluator = LifeEvaluator(cfg, Layout.load(str(path))[0])
    seeds = analysis.fresh_seeds(n_lives, seed0=51_000_000 + 10_000 * seed_block)
    over = {"T": duration, "d0": 0.5, "d_min": 0.25}
    if name == "pool":
        over.update(sigma=0.4, lam_s=4.0)
    world = spec.world("catch_speck_l4", **over)
    manifest = {"parent_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "world": name,
                "overrides": over, "mutants": n_mut, "seeds": seeds, "mutation_seed": mutation_seed,
                "genomes_sha256": hashlib.sha256(genomes.tobytes()).hexdigest(), "numerical_identity": identity,
                "config_sha256": hashlib.sha256(cfg_path.read_bytes()).hexdigest(),
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "kernel_source_sha256": hashlib.sha256((ROOT / "src/life/kernel.c").read_bytes()).hexdigest(),
                "mutation": {"n_mut": 2, "p_cell": 0.5, "scale_n_mut": True, "dup_rate": 0, "del_rate": 0}}
    saved = out / "manifest.json"
    if saved.exists() and json.loads(saved.read_text()) != manifest:
        raise ValueError(f"{out}: inputs changed; use a new study directory")
    atomic_json(saved, manifest)
    atomic_json(out / "mutation_ops.json", ops)
    np.save(out / "genomes.npy", genomes)
    draw = LifeDraw(tuple(seeds), tuple(world for _ in seeds))
    rows = []
    for i, genome in enumerate(genomes):
        rowpath = out / f"row_{i:04d}.npz"
        if not rowpath.exists():
            result = build.run(world, seeds, genomes=spec.V3.pack_genomes(genome[None], world.lattice),
                               abi=spec.V3, fast=True, threads=threads)
            validate_lives(result, world, allow_guards=True)
            columns = evaluator.columns(result, 1, draw)
            temp = out / f"row_{i:04d}.tmp.npz"
            np.savez_compressed(temp, **{key: columns[key][0] for key in COLS})
            temp.replace(rowpath)
        with np.load(rowpath) as row:
            rows.append({key: row[key].copy() for key in COLS})
    data = {key: np.stack([row[key] for row in rows]) for key in COLS}
    np.savez_compressed(out / "scores.npz", seeds=np.asarray(seeds, dtype=np.uint64), **data)
    report = gradient_report(data)
    report.update(world=name, T=duration, stage="screen", seed_block=seed_block,
                  confirmation="pending on disjoint lives", coverage="base/POOL only; ABI 4 worlds pending")
    atomic_json(out / "report.json", report)
    return {key: value for key, value in report.items() if key != "rows"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", choices=(5, 7), type=int, default=5)
    parser.add_argument("--world", choices=("base", "pool"), default="base")
    parser.add_argument("--mutants", type=int, default=256)
    parser.add_argument("--lives", type=int, default=64)
    parser.add_argument("--duration", type=float, default=1024)
    parser.add_argument("--seed-block", type=int, default=10)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/taskvar_e7/gradient")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        args.mutants, args.lives, args.duration, args.seed_block = 4, 2, 32, 0
    if not 0 <= args.seed_block < 100 or not 2 <= args.lives <= 10_000 or args.mutants < 1:
        parser.error("need seed block 0..99, lives 2..10000 and at least one mutant")
    if args.duration <= 0 or args.threads < 1:
        parser.error("duration and threads must be positive")
    if not args.out.resolve().is_relative_to(ROOT / "outputs"):
        parser.error("study output must be inside the repository outputs/ directory")
    name = f"s{args.body}_{args.world}_T{args.duration:g}_b{args.seed_block}"
    out = args.out / name
    if not (args.run or args.smoke):
        print(json.dumps({"status": "dry_run", "genome_lives": (args.mutants + 1) * args.lives,
                          "out": str(out), "note": "Report before launching a full screen."}, indent=2))
        return
    parent = ROOT / f"outputs/catch_pilot/speck_lmax4_hexprism_sex_s{args.body}/best_genome.json"
    report = run_screen(parent, out, args.world, args.mutants, args.lives, args.duration,
                        51_000 + args.body, args.seed_block, args.threads)
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
