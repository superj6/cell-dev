"""Entry point: evolve, then write curves, the best genome, a results row, knockouts and GIFs.

    python -m src.run --config configs/light.yaml [key=value ...]

Outputs in ``logging.output_dir``: config.yaml, curves.jsonl (one row per generation), results.jsonl (one row per
run, appended), best_genome.json, and growth / activity GIFs of the best organism.

With ``mode: life`` (configs/life*.yaml) the run also writes lineage.jsonl, clones.jsonl and population.json, and its
results row describes the best genome's lives on fresh seeds (F, size, income, extinction, counterfactual forks)
instead of trial scores and knockouts. It also records the code the run started from (``git_rev``, ``git_dirty``) and
the selection scheme (``recheck_k``, ``recheck_lives``, ``recheck_key``) with what the recheck did to bodies
(``recheck_bodies``, ``recheck_bodies_onestage``, ``recheck_body_losses``: ``src.evolve.recheck_bodies``).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import torch
from omegaconf import OmegaConf

from src.cells import decode_cells, run_cells
from src.common import load_config, log_event
from src.evolve import evolve, recheck_bodies, recheck_plan, run_mode
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
    if run_mode(cfg) == "life":
        return main_life(cfg)
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



# ======================================================================================================== mode: life
FORK_FINAL_TIMES = (0.5,)  # design G6: spikes undelivered from T/2
REPO = Path(__file__).resolve().parents[1]


def git_state(root: Path = REPO) -> dict:
    """The code a run uses: ``git_rev`` (HEAD) and ``git_dirty`` (tracked changes or untracked files that .gitignore
    does not cover); both None outside a git checkout or without git."""
    def git(*args) -> str:  # --no-optional-locks: never writes the index, so concurrent runs and git commands are safe
        return subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args], capture_output=True, text=True,
                              check=True, timeout=60).stdout

    try:
        return {"git_rev": git("rev-parse", "HEAD").strip(), "git_dirty": bool(git("status", "--porcelain").strip())}
    except (OSError, subprocess.SubprocessError):
        return {"git_rev": None, "git_dirty": None}


class GenomeOrganism:
    """One raw life genome in the run's base world, shaped like ``handbuilt.Organism`` for ``analysis.size_curve``."""

    def __init__(self, ev, params: torch.Tensor):
        self.ev, self.table = ev, ev.table(params.reshape(1, -1))

    def run(self, seeds, *, cap: int = 0, threads: int = 1, **world):
        from src.life import build

        return build.run(self.ev.world(oracle_cap=cap, **world), seeds, genomes=self.table, kind=self.ev.kind,
                         threads=threads, abi=self.ev.abi)


def save_population(r: dict, path: Path) -> None:
    """The final population, best first: ids, breeds, last fitness, slot origins (innovation ids) and genomes."""
    lay, fit = r["layout"], r["fitness"]
    payload = {"dims": lay.dims.__dict__, "ids": [int(i) for i in r["ids"]], "breeds": [int(b) for b in r["breeds"]],
               "fitness": None if fit is None else [float(f) for f in fit], "origins": r["origins"].tolist(),
               "genomes": [lay.to_dict(p) for p in r["population"]]}
    with open(path, "w") as fh:
        json.dump(payload, fh)


def final_life(cfg, r: dict) -> dict:
    """The best genome and the top ``final_top`` on ``final_lives`` fresh lives, the best genome's counterfactual
    forks at T/2 and, if configured, its own size curve under the oracle cap (design: Final evaluation).

    Every F here is measured under the run's base physics, whatever the selection lives were (the envelope control
    changes selection only). ``F_envelope`` is the best genome on the same final lives under envelope physics, for
    every condition, so robustness compares across conditions; ``top_best_F`` is the best of the top re-measured on
    lives separate from the ones it was picked on. In CATCH the beat statistics (BELL's) are skipped, the row adds the
    best genome's captures, misses, clicks, cells per plane, path and mean distance to the target per life, and
    ``msg_reliance`` is the income lost under the message certificate (``clones.CERTIFICATE``) when it is forked, and
    ``sense_reliance`` the income lost when the receptors are (``clones.SENSE``; None if not forked): a blind relay
    clicker has msg_reliance 1 and sense_reliance 0."""
    import numpy as np

    from src.life import analysis, clones
    from src.life.evaluate import life_seed

    ev, lc, cc = r["evaluator"], cfg.life, cfg.get("clones") or {}
    top = r["population"][: int(lc.final_top)]
    draw = ev.draw("final", 0, lives=int(lc.final_lives))
    col = ev.columns(ev.run(top, draw), len(top), draw)
    window = col["window"]
    F, live = col["F"][0], np.maximum(col["live_time"][0], 1e-300)
    s = analysis.summary(F)
    n_end = col["n_end"][0]
    out = {"F": s["mean"], "F_se": s["se"], "F_median": s["median"], "F_frac_pos": s["frac_pos"], "lives": s["n"],
           "n_cells": float(n_end.mean()), "n_end_q": [float(x) for x in np.quantile(n_end, [0.1, 0.25, 0.5, 0.75, 0.9])],
           "n_peak": float(col["n_peak"][0].mean()), "body": float((col["live_time"][0] / window[0]).mean()),
           "income": float((col["income"][0] / window[0]).mean()),
           "energy": float(((col["income"][0] - col["net"][0]) / window[0] + col["extinct_charge"][0]).mean()),
           "income_per_cell": float((col["income"][0] / live).mean()),
           "spikes_per_cell": float((col["spikes"][0] / live).mean()),
           "contact_events_per_cell": float((col["contact_events"][0] / live).mean()),
           "extinction_rate": float(col["extinct"][0].mean()), "guard_rate": float(col["guard"][0].mean()),
           "invalid_lives": int(col["invalid"][0].sum()), "mismatch_lives": int(col["mismatch"].sum()),
           "top_F": [float(x) for x in col["F"].mean(axis=1)], "final_seeds": [int(x) for x in draw.seeds]}
    # the selected best was ranked on a few lives (winner's curse): also report the best of the top, picked on the
    # final lives and re-measured on as many separate lives (a value is never reported on the lives it was picked on)
    k = int(np.argmax(out["top_F"]))
    redraw = ev.draw("final", 1, lives=int(lc.final_lives))
    re_F = ev.columns(ev.run(top[k: k + 1], redraw), 1, redraw)["F"][0]
    re = analysis.summary(re_F)
    out.update(top_best_rank=k, top_best_F_pick=out["top_F"][k], top_best_F=re["mean"], top_best_F_se=re["se"])
    out["F_ci95"] = list(analysis.bootstrap_ci(F))
    if ev.has_envelope:  # robustness: the same final lives under envelope physics, paired with F
        env = ev.draw("final", 0, lives=int(lc.final_lives), envelope=True)
        F_env = ev.columns(ev.run(top[:1], env), 1, env)["F"][0]
        se, d = analysis.summary(F_env), analysis.paired(F_env, F)
        out.update(F_envelope=se["mean"], F_envelope_se=se["se"], d_F_envelope=d["mean"], d_F_envelope_se=d["se"])
    if ev.catch:
        best = {k: v[0] for k, v in col.items()}
        out.update({k: float(best[c].mean()) for k, c in (("captures", "captures"), ("misses", "misses"),
                                                           ("clicks", "clicks"), ("n_S", "n_S_end"),
                                                           ("n_M", "n_M_end"), ("n_H", "n_H_end"), ("path", "path"))})
        out["mean_distance"] = float((best["dist_sum"] / np.maximum(best["samples"], 1.0)).mean())
    else:
        out.update(phase_stats(ev, top[:1], draw.seeds[: min(int(lc.get("phase_lives", 16)), draw.n)]))
    n_fork = min(int(lc.get("final_fork_lives", 16)), draw.n)
    conds = [str(x) for x in cc.get("conditions", clones.CONDITIONS)]
    base = ev.world()
    times = FORK_FINAL_TIMES if not base.fork_flags else (base.t_fork / base.T,)  # a control holds the fork slot
    frows = clones.run_forks(ev.table(top[:1]), base, draw.seeds[:n_fork], times, conds, kind=ev.kind,
                             threads=ev.threads, abi=ev.abi)
    out["forks"] = {f"{x['condition']}@{x['frac']:g}": {k: x.get(k) for k in ("d_income", "d_income_se", "d_F",
                                                                               "ipc_twin", "ipc_fork", "skipped")}
                    for x in frows}
    out["msg_reliance"] = clones.reliance(frows, clones.message_condition(conds))
    sense = clones.sense_condition(conds)  # CATCH: does the income also need the receptors (a sensing wire)?
    out["sense_reliance"] = clones.reliance(frows, sense) if sense else None
    out.update(death_income(ev, top[:1], draw.seeds[:n_fork]))
    sizes = [int(n) for n in (lc.get("size_curve") or [])]
    if sizes:  # the same lives at every size (common random numbers, as in the gates), so sizes compare paired
        seeds = [life_seed(int(cfg.seed), "sizecurve", 0, s) for s in range(int(lc.size_curve_lives))]
        curve = analysis.size_curve(GenomeOrganism(ev, r["best"]), sizes, seeds=seeds, threads=ev.threads)
        out["size_curve"] = {str(n): [c["mean"], c["se"], c["n_end"]] for n, c in curve.items()}
        out["size_curve_argmax"] = max(curve, key=lambda n: curve[n]["mean"])
        out["size_curve_flat_top"] = analysis.best_size({n: c["F"] for n, c in curve.items()})["flat_top"]
    return out


PHASE_WINDOW = 0.125  # beat statistics over the last eighth of the life (the prototype's [900, 1024))


def phase_stats(ev, genome, seeds) -> dict:
    """Beat synchrony of one genome over the last ``PHASE_WINDOW`` of its lives (design: Kuramoto R, local phase
    order and the trap flag). The lives are replayed with their spike raster and fate log, and the ledger opened at
    the window, so income per cell is the window's. A life whose raster overflows or whose body hit a guard has no
    phase statistics."""
    import numpy as np

    from src.life import analysis, build

    seeds = [int(x) for x in seeds]
    if not seeds:
        return {}
    w = ev.world()
    t0 = w.T * (1.0 - PHASE_WINDOW)
    res = build.run(ev.world(t_open=t0), seeds, genomes=ev.table(genome), kind=ev.kind, threads=ev.threads,
                    raster_cap=1 << 16, fate_cap=1 << 13, abi=ev.abi)
    Rs, loc, per, traps, ipcs = [], [], [], [], []
    for i in range(len(seeds)):
        if res.status("raster_overflow")[i] or res.status("fate_overflow")[i] or res["t_end"][i] < w.t0 + w.T:
            continue
        rt, ru = res.spikes(i)
        fi, ff = res.fates(i)
        st = analysis.phase_order(rt, ru, fi, ff, ev.kind, w.t0 + t0, w.t0 + w.T)
        ipc = float(analysis.income_rate(res)[i])
        ipcs.append(ipc)
        if np.isfinite(st["R"]):
            Rs.append(st["R"])
            per.append(st["period"])
        if np.isfinite(st["local"]):
            loc.append(st["local"])
            traps.append(analysis.is_trap(ipc, st["local"]))

    def mean(x):
        return float(np.mean(x)) if x else None

    return {"phase_lives": len(seeds), "phase_lives_used": len(ipcs), "kuramoto_R": mean(Rs), "local_order": mean(loc),
            "beat_period": float(np.median(per)) if per else None, "trap_rate": mean(traps),
            "income_per_cell_late": mean(ipcs)}


DEATH_WINDOW = 2.0  # design, cheat 8: "income within 2 units of deaths is logged"
DEATH_MAX_WINDOWS = 32  # merged windows measured per life and side (an evenly spaced subset beyond that)


def _merge(starts, length: float, lo: float, hi: float) -> list[tuple[float, float]]:
    """Union of the windows [s, s + length) clipped to [lo, hi), as sorted disjoint intervals."""
    out = []
    for s in sorted(float(x) for x in starts):
        a, b = max(s, lo), min(s + length, hi)
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _subset(windows: list, k: int) -> list:
    if len(windows) <= k:
        return windows
    import numpy as np

    return [windows[j] for j in np.unique(np.linspace(0, len(windows) - 1, k).round().astype(int))]


def death_income(ev, genome, seeds, window: float = DEATH_WINDOW, max_windows: int = DEATH_MAX_WINDOWS) -> dict:
    """Income around deaths (design, Cheats and controls 8: a dying relaxed cell lowers n, which can lift P = A/n
    over th at no cost; apoptosis_off forks measure the same effect bundled with pruning and turnover).

    Each life is replayed with its fate log. The windows after its counted deaths, [t_d, t_d + ``window``), and the
    windows before them, [t_d - ``window``, t_d), are merged per side, and the income of a window [a, b) is
    I(a) - I(b), where I(x) is the income of the same life with its ledger opened at x: cells never read t_open
    (forks by replay, LIFE_ABI.md 9.3 and 12), so every replay is the same life. A side with more than
    ``max_windows`` merged windows is measured on an evenly spaced subset and its rate extrapolated to all of them.
    Lives that hit a guard or overflow the fate log are left out.

    Returns ``death_lives`` (lives used), ``deaths_per_life``, ``death_window_frac`` (share of the counted time after
    deaths), ``death_income_share`` (share of the income earned there), ``death_lift`` (income rate after deaths over
    the rate just before them, pooled over lives: 1 means deaths do not bump the pump) and ``death_lift_rest`` (after
    deaths over the rest of the life, which also reflects when deaths happen). Lifts are None without deaths.
    """
    from dataclasses import replace

    import numpy as np

    from src.life import build

    seeds = [int(x) for x in seeds]
    if not seeds:
        return {}
    w = ev.world()
    table = ev.table(genome)
    res = build.run(w, seeds, genomes=table, kind=ev.kind, threads=ev.threads, fate_cap=1 << 13, abi=ev.abi)
    lives, jobs = [], []
    for i, seed in enumerate(seeds):
        if res.status("fate_overflow")[i] or res["t_end"][i] < w.t0 + w.T:
            continue
        kinds, ff = res.fates(i)
        t_d = ff[kinds[:, 0] == 2, 0] - w.t0
        t_d = t_d[t_d >= w.t_open]
        post = _merge(t_d, window, w.t_open, w.T)
        pre = _merge(t_d - window, window, w.t_open, w.T)
        sides = {"post": (post, _subset(post, max_windows)), "pre": (pre, _subset(pre, max_windows))}
        opens = sorted({x for _, sub in sides.values() for ab in sub for x in ab if x < w.T})
        lives.append(dict(i=i, deaths=len(t_d), sides=sides, opens=opens, first=len(jobs)))
        jobs += [(seed, x) for x in opens]
    if not lives:
        return {"death_lives": 0}
    opened = {}  # income of each replay, by job index
    if jobs:
        rep = build.run([replace(w, t_open=float(x)) for _, x in jobs], [s for s, _ in jobs], genomes=table,
                        kind=ev.kind, threads=ev.threads, abi=ev.abi)
        opened = {j: float(v) for j, v in enumerate(rep["income"])}
    span = w.T - w.t_open
    tot = dict(post=0.0, post_len=0.0, pre=0.0, pre_len=0.0, income=0.0)
    for life in lives:
        at = {x: opened[life["first"] + j] for j, x in enumerate(life["opens"])}
        tot["income"] += float(res["income"][life["i"]])
        for side, (merged, sub) in life["sides"].items():
            U = sum(b - a for a, b in merged)
            if U:
                inc = sum(at[a] - at.get(b, 0.0) for a, b in sub) * U / sum(b - a for a, b in sub)
                tot[side] += inc
                tot[side + "_len"] += U
    rest, rest_len = tot["income"] - tot["post"], span * len(lives) - tot["post_len"]

    def ratio(x, lx, y, ly):
        return (x / lx) / (y / ly) if lx > 0 and ly > 0 and y > 0 else None

    return {"death_lives": len(lives), "deaths_per_life": float(np.mean([x["deaths"] for x in lives])),
            "death_window_frac": tot["post_len"] / (span * len(lives)),
            "death_income_share": tot["post"] / tot["income"] if tot["income"] > 0 else None,
            "death_lift": ratio(tot["post"], tot["post_len"], tot["pre"], tot["pre_len"]),
            "death_lift_rest": ratio(tot["post"], tot["post_len"], rest, rest_len)}


def main_life(cfg) -> Path:
    """Life-mode run: evolve, then save the best genome and the population and write the life results row."""
    out = Path(cfg.logging.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    OmegaConf.save(cfg, out / "config.yaml")
    git = git_state()  # at the start: the code that is loaded
    t0 = time.time()
    with open(out / "curves.jsonl", "w") as curves_fh:
        def log(row):
            log_event(**row)
            if "gen" in row:
                curves_fh.write(json.dumps(row) + "\n")
                curves_fh.flush()

        r = evolve(cfg, log=log, out=out)
    wall = time.time() - t0
    r["layout"].save(r["best"], out / "best_genome.json")
    save_population(r, out / "population.json")
    t1 = time.time()
    fin = final_life(cfg, r)
    lc, e = cfg.life, cfg.evolve
    k, lives, key = recheck_plan(e, int(e.mu), int(e.mu) + int(e.lam))
    row = {"name": out.name, "mode": "life", "control": str(lc.get("control", "full")), "world": str(lc.world),
           "lattice": str(cfg.lattice.kind), "breeding": str(cfg.evolve.breeding), "seed": int(cfg.seed), **git,
           "L_max": int(r["evaluator"].world().L_max), "abi": int(r["evaluator"].abi.version),
           "selection_physics": "envelope" if r["evaluator"].envelope.get("enabled", False) else "base",
           "recheck_k": k, "recheck_lives": lives, "recheck_key": key if k else None, **recheck_bodies(r["curves"]),
           "evals": r["evals"], "wall_s": round(wall, 1), "final_s": round(time.time() - t1, 1),
           "generations": len(r["curves"]), "founders_sampled": r["founders"]["sampled"],
           "valid_score": r["valid"], "heldout_score": r["heldout"], **fin,
           "evals_to_skill": first_evals_at(r["curves"], float(lc.skill_at)) if r["curves"] else None}
    with open(out / "results.jsonl", "w") as fh:
        fh.write(json.dumps(row) + "\n")
    log_event(event="result", **row)
    return out / "results.jsonl"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("overrides", nargs="*")
    args = p.parse_args()
    main(load_config(args.config, args.overrides))
