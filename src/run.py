"""Entry point: evolve, then write curves, the best genome, a results row, knockouts and GIFs.

    python -m src.run --config configs/light.yaml [key=value ...]

Outputs in ``logging.output_dir``: config.yaml, curves.jsonl (one row per generation), results.jsonl (one row per
run, appended), best_genome.json, and growth / activity GIFs of the best organism.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from omegaconf import OmegaConf

from src.cells import decode_cells, run_cells
from src.common import load_config, log_event
from src.evolve import evolve
from src.measure import knockouts
from src.render import activity_gif, development_gif


def first_evals_at(curves: list[dict], threshold: float, key: str = "valid", rung: int | None = None) -> int | None:
    """Evaluations at the first checkpoint reaching ``threshold`` (on ``rung`` only, for ladder runs)."""
    for row in curves:
        if rung is not None and row.get("rung") != rung:
            continue
        if row.get(key) is not None and row[key] >= threshold:
            return row["evals"]
    return None


def write_gifs(r: dict, out: Path, gen: torch.Generator, n_trials: int = 2) -> None:
    ev, task, best = r["evaluator"], r["task"], r["best"].reshape(1, -1)
    gifs = out / "gifs"
    gifs.mkdir(exist_ok=True)
    tissue = ev.develop(best, record=True)
    development_gif(ev.lattice, tissue.history, gifs / "growth.gif")
    rung = task.rungs[task.rung] if hasattr(task, "rungs") else task
    trials = rung.sample(ev.lattice.pos, n_trials, gen, heldout=True)
    rule = decode_cells(ev.layout, best, ev.cfg.cells.quantize)
    act = run_cells(ev.lattice, tissue.alive, tissue.types, rule, trials.stim, trials.window, record=True,
                    messages=bool(ev.cfg.cells.get("messages", True)))
    for e in range(n_trials):
        activity_gif(ev.lattice, tissue.alive[0], tissue.types[0], act.raster[:, 0, e], trials.stim[e],
                     trials.window[e], trials.target[e], gifs / f"activity_{e}.gif", label=rung.name)


def main(cfg) -> Path:
    out = Path(cfg.logging.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    OmegaConf.save(cfg, out / "config.yaml")
    t0 = time.time()
    with open(out / "curves.jsonl", "w") as curves_fh:
        def log(row):
            log_event(**row)
            if "gen" in row:
                curves_fh.write(json.dumps(row) + "\n")
                curves_fh.flush()

        r = evolve(cfg, log=log)
    wall = time.time() - t0
    r["layout"].save(r["best"], out / "best_genome.json")

    gen = torch.Generator().manual_seed(int(cfg.seed) + 20_000)
    ev, task = r["evaluator"], r["task"]
    rung = task.rungs[task.rung] if hasattr(task, "rungs") else task
    trials = rung.sample(ev.lattice.pos, int(cfg.task.heldout_trials), gen, heldout=True)
    ko = knockouts(ev, r["best"], trials, gen)
    final = ev(r["best"].reshape(1, -1), trials).take(0)
    valid = ev(r["best"].reshape(1, -1), rung.sample(ev.lattice.pos, int(cfg.task.heldout_trials), gen)).take(0)
    row = {
        "name": out.name, "task": cfg.task.name, "lattice": cfg.lattice.kind, "breeding": cfg.evolve.breeding,
        "seed": int(cfg.seed), "evals": r["evals"], "wall_s": round(wall, 1), "rung": r["rung"], "rung_name": rung.name,
        "valid_score": valid["score"], "heldout_score": ko["base"], "heldout_no_messages": ko["no_messages"],
        "heldout_shuffled_types": ko["shuffled_types"], "heldout_one_type": ko["one_type_best"],
        "types_used": ko["types_used"], "essential_cells": ko.get("essential_cells"),
        "n_cells": final["n_cells"], "energy": final["energy"], "spikes_per_tick": final["spikes"],
        "evals_to_skill": (first_evals_at(r["curves"], float(cfg.evolve.advance_at), rung=r["rung"] if hasattr(task, "rungs") else None)
                           if r["curves"] else (r["evals"] if valid["score"] >= float(cfg.evolve.advance_at) else None)),
        "advances": [(c["gen"], c["evals"], c["advanced_to"]) for c in r["curves"] if "advanced_to" in c],
    }
    with open(out / "results.jsonl", "w") as fh:  # one run per directory
        fh.write(json.dumps(row) + "\n")
    log_event(event="result", **row)
    if cfg.logging.gif:
        write_gifs(r, out, gen)
    return out / "results.jsonl"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("overrides", nargs="*")
    args = p.parse_args()
    main(load_config(args.config, args.overrides))
