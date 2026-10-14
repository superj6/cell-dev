"""Test-time knockouts on a grown organism, to show whether its structure and messages are actually used.

- messages off: cells still sense and fire, but nothing passes between neighbours;
- shuffled types: the same cell types, randomly re-placed among the living cells;
- one type: every cell becomes the same type (the best such type is reported);
- single-cell knockout map: the score drop when each cell is removed (cells whose loss costs > 0.05 are "essential").
"""
from __future__ import annotations

import torch

from src.cells import CellRule, decode_cells, run_cells
from src.tasks.base import Trials, direction_score


def _expand(rule: CellRule, n: int) -> CellRule:
    return CellRule(*[getattr(rule, f).expand(n, *getattr(rule, f).shape[1:]) for f in CellRule.__dataclass_fields__])


def _score(ev, alive, types, rule, trials: Trials, messages=True) -> torch.Tensor:
    act = run_cells(ev.lattice, alive, types, rule, trials.stim, trials.window, messages=messages)
    return direction_score(act.counts, ev.lattice.pos, alive, trials.target, ev.cfg.task.min_spikes,
                           ev.cfg.task.score).mean(1)


@torch.inference_mode()
def knockouts(ev, params: torch.Tensor, trials: Trials, gen: torch.Generator, shuffles: int = 8,
              cell_map: bool = True) -> dict:
    params = params.reshape(1, -1)
    tissue = ev.develop(params)
    rule = decode_cells(ev.layout, params, ev.cfg.cells.quantize)
    alive, types = tissue.alive, tissue.types
    msgs = bool(ev.cfg.cells.get("messages", True))  # a no-message control run is scored without messages throughout
    out = {"n_cells": int(alive.sum()), "base": float(_score(ev, alive, types, rule, trials, messages=msgs)[0]),
           "no_messages": float(_score(ev, alive, types, rule, trials, messages=False)[0])}

    live_idx = alive[0].nonzero()[:, 0]
    shuffled = types.repeat(shuffles, 1)
    for s in range(shuffles):
        perm = live_idx[torch.randperm(len(live_idx), generator=gen)]
        shuffled[s, live_idx] = types[0, perm]
    out["shuffled_types"] = float(_score(ev, alive.repeat(shuffles, 1), shuffled, _expand(rule, shuffles), trials,
                                         messages=msgs).mean())

    K = ev.layout.dims.types
    one = torch.arange(K)[:, None].expand(K, alive.shape[1]) * alive.long()
    by_type = _score(ev, alive.repeat(K, 1), one, _expand(rule, K), trials, messages=msgs)
    out["one_type_best"] = float(by_type.max())
    out["types_used"] = int(types[0, live_idx].unique().numel())

    if cell_map and len(live_idx) > 0:
        masks = alive.repeat(len(live_idx), 1)
        masks[torch.arange(len(live_idx)), live_idx] = False
        drop = out["base"] - _score(ev, masks, types.repeat(len(live_idx), 1), _expand(rule, len(live_idx)), trials,
                                     messages=msgs)
        full = torch.zeros(alive.shape[1])
        full[live_idx] = drop
        out["knockout_map"] = full
        out["essential_cells"] = int((drop > 0.05).sum())
    return out
