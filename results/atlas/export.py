"""Export one evolved organism to a compact JSON for the visualization page.

    from export import export
    export("outputs/memory_sweep/square8_sex_s0", "memory4", title="...", task="memory", pool=24, select=[0, 3])

Schema (all site indices refer to `pos`):
  id, title, run, task, lattice {kind, radius}, pos [[x, y], ...]
  growth: [{"alive": [site...], "types": [type per alive site]} per development step]
  final:  {"alive": [...], "types": [...]}
  rules:  [{type, count, w[C], gains[light, cue], bias, leak, refr, emit[C]} for each type present]
  trials: [{label, T, light: [digits string per tick, one 0-9 char per site], cue: [...], window: [0/1 per tick],
            target [x, y], spikes: [[site...] per tick], spikesNoMsg: [[site...] per tick], score, scoreNoMsg}]
  stats:  {heldout, noMessages, shuffledTypes, oneType, cells, types, essential}  (48 held-out trials)
  importance: [score lost when that cell is removed, per final.alive entry]
  mechanism, evidence: filled in by the caller (plain-language explanation and how it was checked)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

REPO = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, REPO)

from omegaconf import OmegaConf  # noqa: E402

from src.cells import decode_cells, run_cells  # noqa: E402
from src.evolve import setup  # noqa: E402
from src.genome import Layout  # noqa: E402
from src.measure import knockouts  # noqa: E402
from src.tasks import build_task  # noqa: E402
from src.tasks.base import concat, direction_score  # noqa: E402

OUT = str(Path(__file__).resolve().parent / "data")


def _digits(x: torch.Tensor, scale: float) -> str:
    q = (x / max(scale, 1e-9) * 9).round().clamp(0, 9).int().tolist()
    return "".join(str(v) for v in q)


def load(run_dir: str):
    run_dir = run_dir if run_dir.startswith("/") else f"{REPO}/{run_dir}"
    cfg = OmegaConf.load(f"{run_dir}/config.yaml")
    _, params = Layout.load(f"{run_dir}/best_genome.json")
    lattice, layout, _, ev = setup(cfg)
    return run_dir, cfg, lattice, layout, ev, params.reshape(1, -1)


def export(run_dir: str, oid: str, *, title: str, task: str, pool: int = 12, seed: int = 0, heldout: bool = True,
           select=None, labels=None, trials=None, mechanism: str = "", evidence: str = "") -> dict:
    torch.set_num_threads(2)
    run_dir, cfg, lat, layout, ev, best = load(run_dir)
    tis = ev.develop(best, record=True)
    rule = decode_cells(layout, best, cfg.cells.quantize)
    t = build_task(task, float(cfg.task.length))
    if trials is None:
        trials = t.sample(lat.pos, pool, torch.Generator().manual_seed(seed), heldout=heldout)
    if select is not None:
        idx = torch.tensor(select)
        trials = type(trials)(stim=trials.stim[idx], window=trials.window[idx], target=trials.target[idx],
                              rung=trials.rung[idx])
    act = run_cells(lat, tis.alive, tis.types, rule, trials.stim, trials.window, record=True)
    act0 = run_cells(lat, tis.alive, tis.types, rule, trials.stim, trials.window, record=True, messages=False)
    kw = dict(min_spikes=cfg.task.min_spikes, kind=cfg.task.score)
    s = direction_score(act.counts, lat.pos, tis.alive, trials.target, **kw)[0]
    s0 = direction_score(act0.counts, lat.pos, tis.alive, trials.target, **kw)[0]

    near = lat.pos.norm(dim=1) <= 6.0
    alive_idx = tis.alive[0].nonzero()[:, 0]
    out_trials = []
    for e in range(trials.n):
        light, cue = trials.stim[e, :, :, 0], trials.stim[e, :, :, 1]
        lscale = float(light[:, near].max()) if float(light.max()) > 0 else 1.0
        cscale = float(cue.max()) if float(cue.max()) > 0 else 1.0
        out_trials.append({
            "label": (labels[e] if labels else f"trial {e + 1}"),
            "T": int(trials.window.shape[1]),
            "light": [_digits(light[k], lscale) for k in range(light.shape[0])],
            "cue": [_digits(cue[k], cscale) for k in range(cue.shape[0])],
            "window": [int(v > 0) for v in trials.window[e].tolist()],
            "target": [round(float(v), 4) for v in trials.target[e]],
            "spikes": [act.raster[k, 0, e].nonzero()[:, 0].tolist() for k in range(act.raster.shape[0])],
            "spikesNoMsg": [act0.raster[k, 0, e].nonzero()[:, 0].tolist() for k in range(act0.raster.shape[0])],
            "score": round(float(s[e]), 3), "scoreNoMsg": round(float(s0[e]), 3),
        })

    gen = torch.Generator().manual_seed(seed + 1)
    ko_trials = t.sample(lat.pos, int(cfg.task.heldout_trials), gen, heldout=True)
    ko = knockouts(ev, best, ko_trials, torch.Generator().manual_seed(0))
    types_present = tis.types[0, alive_idx].unique().tolist()
    rules = [{
        "type": int(k), "count": int((tis.types[0, alive_idx] == k).sum()),
        "w": [round(float(v), 3) for v in rule.w[0, k]], "gains": [round(float(v), 3) for v in rule.gs[0, k]],
        "bias": round(float(rule.bias[0, k]), 3), "leak": round(float(rule.leak[0, k]), 4),
        "refr": int(rule.refr[0, k]), "emit": [int(v) for v in rule.emit[0, k]],
    } for k in types_present]
    data = {
        "id": oid, "title": title, "run": run_dir.replace(REPO + "/", ""), "task": task,
        "lattice": {"kind": lat.kind, "radius": lat.radius},
        "pos": [[round(float(x), 4), round(float(y), 4)] for x, y in lat.pos.tolist()],
        "growth": [{"alive": a[0].nonzero()[:, 0].tolist(), "types": ty[0][a[0]].tolist()} for a, ty in tis.history],
        "final": {"alive": alive_idx.tolist(), "types": tis.types[0, alive_idx].tolist()},
        "rules": rules, "trials": out_trials,
        "stats": {"heldout": round(ko["base"], 3), "noMessages": round(ko["no_messages"], 3),
                  "shuffledTypes": round(ko["shuffled_types"], 3), "oneType": round(ko["one_type_best"], 3),
                  "cells": ko["n_cells"], "types": ko["types_used"], "essential": ko.get("essential_cells")},
        "importance": [round(float(ko["knockout_map"][i]), 4) for i in alive_idx.tolist()],
        "mechanism": mechanism, "evidence": evidence,
    }
    import os
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/{oid}.json", "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
    return data


__all__ = ["export", "load", "concat"]
