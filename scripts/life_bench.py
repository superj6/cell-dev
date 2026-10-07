"""Throughput of life-mode evolution: seconds per generation (mu + lambda genomes x lives) at several thread counts.

    python scripts/life_bench.py --config configs/life_bell.yaml --threads 3,8 --generations 10 [key=value ...]

Two populations:
- ``founders``: the run's own start (founder sampling, then 8 founders and their mutants): early generations, mostly
  lone pumps and their mutants, some of which grow until the N_max guard.
- ``r25``: a population descended from the hand-built R25-v1 GRN genome with its lineage timer at weight 1.0
  (``evolve.seed_genome: r25_v1_timer``), whose bodies stop near the reference size of 91-100 cells: a stand-in for a
  late population that has found bounded bodies.

Each generation runs the real ``evolve_life`` loop (breeding, evaluation, lineage bookkeeping, and every
``heldout_every`` / ``clones.every`` generations the valid, held-out and fork lives). The script reports the plain
generation time, the extra cost of a valid + clones round, and their amortized sum. A kernel-only measurement runs
``--kernel-lives`` identical lives of the R25-v1 timer genome per thread count (cost per life and per cell-time unit).
Writes ``<out>/bench.json``.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.common import load_config  # noqa: E402
from src.evolve import evolve_life, seed_genome, setup  # noqa: E402
from src.life import build  # noqa: E402

R25_SIZED = ["evolve.seed_genome=r25_v1_timer", "evolve.seed_timer=1.0"]  # bodies stop near 91-100 cells
POPULATIONS = dict(founders=[], r25=R25_SIZED)


def loop_bench(config: str, threads: int, generations: int, extra: list[str], overrides: list[str]) -> dict:
    """Times ``generations`` generations of evolve_life (no output files)."""
    cfg = load_config(config, [*overrides, *extra, f"threads={threads}", f"evolve.generations={generations}"])
    marks = []
    t0 = time.perf_counter()
    r = evolve_life(cfg, log=lambda row: marks.append((time.perf_counter() - t0, row)), out=None)
    t_founders = next(t for t, row in marks if row.get("event") == "founders")
    rows = [row for _, row in marks if "gen" in row]
    every = int(cfg.evolve.heldout_every)
    plain = [x for x in rows if "valid" not in x and "clones" not in x]
    rounds = [x["t_gen"] for x in rows if "valid" in x or "clones" in x]
    nan = float("nan")
    t_plain = statistics.median([x["t_gen"] for x in plain]) if plain else nan
    t_round = (statistics.mean(rounds) - t_plain) if rounds and plain else nan
    return dict(threads=threads, generations=len(rows), lives=int(cfg.life.lives), genomes=int(cfg.evolve.mu) +
                int(cfg.evolve.lam), t_founders=round(t_founders, 3), founders_sampled=r["founders"]["sampled"],
                t_gen_plain=t_plain, t_eval_plain=statistics.median([x["t_eval"] for x in plain]) if plain else nan,
                t_round_extra=t_round, every=every,
                t_gen_amortized=t_plain + t_round / every, t_total=round(time.perf_counter() - t0, 2),
                body_mean=[round(x["pop_body"], 2) for x in rows], guard=[round(x["pop_guard"], 3) for x in rows],
                best_F=[round(x["fitness"], 4) for x in rows], best_n=[x["n_cells"] for x in rows])


def kernel_bench(config: str, threads: int, lives: int, overrides: list[str]) -> dict:
    """Identical lives of the R25-v1 timer genome in one kernel call: wall time, ms per life, us per cell-time unit."""
    cfg = load_config(config, [*overrides, *R25_SIZED, f"threads={threads}"])
    _, layout, _, ev = setup(cfg)
    table = ev.table(seed_genome(cfg, layout))
    seeds = [7_000_000 + s for s in range(lives)]
    t0 = time.perf_counter()
    res = build.run(ev.world(), seeds, genomes=table, genome_of=np.zeros(lives, dtype=np.int32), kind=ev.kind,
                    threads=threads)
    dt = time.perf_counter() - t0
    cell_time = float(res["live_time"].sum())
    return dict(threads=threads, lives=lives, wall=round(dt, 3), ms_per_life=1e3 * dt / lives,
                us_per_cell_unit_per_thread=1e6 * dt * threads / cell_time, n_end=float(res["n_end"].mean()),
                F=float(res["F"].mean()), events=float(res["events"].mean()))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/life_bell.yaml")
    p.add_argument("--threads", default="3,8")
    p.add_argument("--generations", type=int, default=10)
    p.add_argument("--populations", default="founders,r25")
    p.add_argument("--kernel-lives", type=int, default=768)
    p.add_argument("--out", default="outputs/life_bench")
    p.add_argument("overrides", nargs="*")
    args = p.parse_args()
    config = str(repo_root / args.config) if not Path(args.config).is_absolute() else args.config
    out = dict(load=os.getloadavg(), loop=[], kernel=[])
    for t in (int(x) for x in args.threads.split(",")):
        if args.kernel_lives > 0:
            k = kernel_bench(config, t, args.kernel_lives, args.overrides)
            out["kernel"].append(k)
            print(f"kernel  threads {t}: {k['lives']} R25-timer lives in {k['wall']:.2f} s ({k['ms_per_life']:.2f} ms "
                  f"per life, {k['us_per_cell_unit_per_thread']:.3f} us per cell-unit per thread, n_end "
                  f"{k['n_end']:.1f})", flush=True)
        for name in args.populations.split(","):
            b = loop_bench(config, t, args.generations, POPULATIONS[name], args.overrides)
            b["population"] = name
            out["loop"].append(b)
            print(f"loop    threads {t} {name}: founders {b['t_founders']:.2f} s; plain generation {b['t_gen_plain']:.2f} s "
                  f"(kernel {b['t_eval_plain']:.2f}); valid+clones round +{b['t_round_extra']:.2f} s every {b['every']}; "
                  f"amortized {b['t_gen_amortized']:.2f} s/gen; mean body {np.mean(b['body_mean']):.1f}, guard "
                  f"{np.mean(b['guard']):.3f}", flush=True)
    out["load_end"] = os.getloadavg()
    dest = repo_root / args.out if not Path(args.out).is_absolute() else Path(args.out)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "bench.json").write_text(json.dumps(out, indent=1))
