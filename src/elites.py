"""Behaviour grids that keep distinct abilities per training task (MAP-Elites style; docs/OPEN_WORLDS.md 6.4).

Training bookkeeping outside the organism. A grid has ``shape`` cells over two behaviour descriptors of one task,
with fixed bounds. Each descriptor is a per-life ledger column, or a per-life ratio ``"a/b"`` of two columns (0 where
``b`` is 0); a genome's descriptor is its mean over its lives of that task, and values outside the bounds fall into
the edge cells. Rules (``evolve.elites``):

- a cell holds one elite: its genome, ID, breed, gene origins and a running mean of its own-task scores over all its
  own-task lives, with the count capped at ``cap`` (beyond it each new life has weight 1/cap);
- incumbents relive the generation's lives of their task every generation (paired with every candidate), and leave
  only when replaced;
- per cell the best candidate on the shared lives challenges; it fills an empty cell, or replaces the incumbent when
  its paired mean gain over the shared lives is positive and at least ``admit_z`` standard errors (common random
  numbers);
- ``parent_share`` of each generation's children take parent A from a uniformly random filled cell (own RNG);
- a "new ability" is a newly filled cell whose value is at least the median of the cells filled before the
  generation, confirmed when its mean over ``confirm_lives`` fresh paired lives is at least the median elite's
  (the lower-median cell). Confirmed events feed the allocator's novelty term.
"""
from __future__ import annotations

import math
from numbers import Integral

import numpy as np
import torch

DEFAULTS = dict(shape=[4, 4], descriptors={}, bounds={}, cap=64, admit_z=1.0, parent_share=0.25, confirm_lives=8)


def parse_descriptor(text) -> tuple[str, str | None]:
    """``"a"`` -> (a, None); ``"a/b"`` -> (a, b)."""
    parts = [p.strip() for p in str(text).split("/")]
    if not 1 <= len(parts) <= 2 or not all(parts):
        raise ValueError(f"descriptor {text!r} must be a ledger column or a ratio 'a/b'")
    return parts[0], (parts[1] if len(parts) == 2 else None)


def descriptor_lives(columns, names, descriptor) -> np.ndarray:
    """Per-life descriptor values ``[..., L]`` from per-life columns ``[..., L, D]`` named ``names``."""
    columns = np.asarray(columns, dtype=np.float64)
    a = columns[..., names.index(descriptor[0])]
    if descriptor[1] is None:
        return a
    b = columns[..., names.index(descriptor[1])]
    return np.divide(a, b, out=np.zeros_like(a), where=b != 0)


def paired(challenger, incumbent) -> tuple[float, float]:
    """Mean paired difference over shared lives and its standard error (inf below two lives)."""
    d = np.asarray(challenger, dtype=np.float64) - np.asarray(incumbent, dtype=np.float64)
    if not d.size:
        return 0.0, math.inf
    se = float(d.std(ddof=1) / math.sqrt(d.size)) if d.size >= 2 else math.inf
    return float(d.mean()), se


def beats(challenger, incumbent, z: float) -> bool:
    mean, se = paired(challenger, incumbent)
    return mean > 0 and mean >= z * se


def contest(cells, shared, filled, incumbent_shared, z: float, skip=()) -> list[dict]:
    """Admissions of one grid in one generation. ``cells[i]`` is candidate i's cell (-1: none), ``shared[i]`` its
    scores on the shared lives, ``filled[c]`` whether cell c had an incumbent and ``incumbent_shared[c]`` that
    incumbent's scores on the same lives. Per cell (ascending), the best candidate by shared mean (lowest index on
    ties, ``skip`` excluded) fills an empty cell or replaces the incumbent if it ``beats`` it."""
    cells = np.asarray(cells)
    shared = np.asarray(shared, dtype=np.float64)
    means = shared.mean(axis=1) if shared.size else np.zeros(len(cells))
    skip = set(int(i) for i in skip)
    out = []
    for c in sorted(set(int(x) for x in cells[cells >= 0])):
        rows = [int(i) for i in np.flatnonzero(cells == c) if int(i) not in skip]
        if not rows:
            continue
        best = max(rows, key=lambda i: (means[i], -i))
        if not filled[c]:
            out.append(dict(cell=c, row=best, replaced=False, d=None, se=None))
            continue
        d, se = paired(shared[best], incumbent_shared[c])
        if d > 0 and d >= z * se:
            out.append(dict(cell=c, row=best, replaced=True, d=d, se=None if math.isinf(se) else se))
    return out


def novel(cells, scores, filled, top, k: int) -> list[int]:
    """Up to ``k`` behaviourally novel candidates over grids: per grid, the best candidate (by its task score) of
    each cell that is empty and holds none of the ``top`` candidates. Ordered by the candidate's rank fraction on
    that task (0 = best), then grid, then cell; each candidate once. ``cells``, ``scores`` and ``filled`` are per
    grid lists."""
    top = set(int(i) for i in top)
    entries = []
    for gi, (c, s, f) in enumerate(zip(cells, scores, filled)):
        c, s = np.asarray(c), np.asarray(s, dtype=np.float64)
        n = len(s)
        order = np.argsort(-s, kind="stable")
        frac = np.empty(n)
        frac[order] = np.arange(n) / max(n - 1, 1)
        taken = {int(c[i]) for i in top if c[i] >= 0}
        best = {}
        for i in range(n):
            cell = int(c[i])
            if i in top or cell < 0 or f[cell] or cell in taken:
                continue
            if cell not in best or s[i] > s[best[cell]]:
                best[cell] = i
        entries += [(float(frac[i]), gi, cell, i) for cell, i in best.items()]
    chosen = []
    for _, _, _, i in sorted(entries):
        if len(chosen) >= k:
            break
        if i not in chosen:
            chosen.append(i)
    return chosen


class Grid:
    """One task's grid; tensors only, so its state checkpoints exactly."""

    def __init__(self, task: str, descriptors, bounds, shape, size: int, genes: int):
        self.task, self.descriptors = task, list(descriptors)
        self.bounds, self.shape = [[float(lo), float(hi)] for lo, hi in bounds], [int(n) for n in shape]
        C = self.shape[0] * self.shape[1]
        self.filled = torch.zeros(C, dtype=torch.bool)
        self.genomes = torch.zeros(C, size, dtype=torch.float32)
        self.ids = torch.full((C,), -1, dtype=torch.long)
        self.breeds = torch.full((C,), -1, dtype=torch.long)
        self.origins = torch.full((C, genes), -1, dtype=torch.long)
        self.value = torch.zeros(C, dtype=torch.float64)
        self.count = torch.zeros(C, dtype=torch.long)
        self.since = torch.full((C,), -1, dtype=torch.long)

    TENSORS = ("filled", "genomes", "ids", "breeds", "origins", "value", "count", "since")

    @property
    def n_cells(self) -> int:
        return self.shape[0] * self.shape[1]

    def cells(self, desc) -> np.ndarray:
        """Cell index of each descriptor row ``[N, 2]`` (clipped to the edge cells; -1 if not finite)."""
        desc = np.asarray(desc, dtype=np.float64).reshape(-1, 2)
        ok = np.isfinite(desc).all(axis=1)
        k = []
        for j in (0, 1):
            lo, hi = self.bounds[j]
            n = self.shape[j]
            u = np.where(ok, (desc[:, j] - lo) / (hi - lo), 0.0)
            k.append(np.clip(np.floor(u * n), 0, n - 1).astype(np.int64))
        return np.where(ok, k[0] * self.shape[1] + k[1], -1)

    def observe(self, cell: int, scores, cap: int) -> None:
        """Fold own-task life scores into the cell's running mean (count capped at ``cap``)."""
        m, n = float(self.value[cell]), int(self.count[cell])
        for x in np.asarray(scores, dtype=np.float64).reshape(-1):
            n = min(n + 1, cap)
            m += (float(x) - m) / n
        self.value[cell], self.count[cell] = m, n

    def place(self, cell: int, genome, identity: int, breed: int, origins, scores, generation: int, cap: int):
        self.filled[cell] = True
        self.genomes[cell] = genome
        self.ids[cell], self.breeds[cell], self.since[cell] = int(identity), int(breed), int(generation)
        self.origins[cell] = origins
        self.value[cell], self.count[cell] = 0.0, 0
        self.observe(cell, scores, cap)

    def state(self) -> dict:
        return {k: getattr(self, k).clone() for k in self.TENSORS}

    def load(self, state: dict) -> None:
        for k in self.TENSORS:
            setattr(self, k, state[k].clone())


class Elites:
    """The behaviour grids of the training tasks that declare descriptors, in task order."""

    def __init__(self, conf, tasks, size: int, genes: int):
        raw = dict(conf or {})
        unknown = set(raw) - set(DEFAULTS)
        if unknown:
            raise ValueError(f"unknown evolve.elites keys {sorted(unknown)}")
        c = {**DEFAULTS, **raw}
        self.tasks = tuple(tasks)
        shape = list(c["shape"])
        if len(shape) != 2 or any(isinstance(n, bool) or not isinstance(n, Integral) or n < 1 for n in shape):
            raise ValueError("evolve.elites.shape must be two positive integers")
        descriptors, bounds = dict(c["descriptors"] or {}), dict(c["bounds"] or {})
        if not descriptors:
            raise ValueError("evolve.elites needs descriptors for at least one training task")
        if set(descriptors) - set(self.tasks) or set(bounds) != set(descriptors):
            raise ValueError("evolve.elites descriptors and bounds must name the same training tasks")
        for name, value, low in (("cap", c["cap"], 1), ("confirm_lives", c["confirm_lives"], 0)):
            if isinstance(value, bool) or not isinstance(value, Integral) or value < low:
                raise ValueError(f"evolve.elites.{name} must be an integer >= {low}")
        self.cap, self.confirm_lives = int(c["cap"]), int(c["confirm_lives"])
        self.admit_z, self.parent_share = float(c["admit_z"]), float(c["parent_share"])
        if not math.isfinite(self.admit_z) or self.admit_z < 0 or not 0 <= self.parent_share <= 1:
            raise ValueError("evolve.elites needs admit_z >= 0 and parent_share in [0, 1]")
        self.grids = []
        for task in self.tasks:
            if task not in descriptors:
                continue
            parsed = [parse_descriptor(d) for d in descriptors[task]]
            box = [list(b) for b in bounds[task]]
            if len(parsed) != 2 or len(box) != 2 or any(len(b) != 2 or not float(b[0]) < float(b[1]) for b in box):
                raise ValueError(f"evolve.elites task {task!r} needs two descriptors and two [lo, hi] bounds, lo < hi")
            self.grids.append(Grid(task, parsed, box, shape, size, genes))
        self.events: list[list] = []  # [generation, task index, cell, id] of confirmed new abilities

    @property
    def columns(self) -> tuple[str, ...]:
        """The raw ledger columns the descriptors read, in first-use order."""
        names = []
        for grid in self.grids:
            for a, b in grid.descriptors:
                names += [n for n in (a, b) if n is not None and n not in names]
        return tuple(names)

    def describe(self, grid: Grid, life_columns) -> np.ndarray:
        """Descriptors ``[N, 2]``: each genome's mean over the given lives of its per-life values."""
        return np.stack([descriptor_lives(life_columns, self.columns, d).mean(axis=-1) for d in grid.descriptors],
                        axis=-1)

    def filled(self) -> list[tuple[int, int]]:
        return [(gi, int(c)) for gi, grid in enumerate(self.grids) for c in torch.nonzero(grid.filled)[:, 0]]

    def novelty_counts(self, g: int, window: int) -> list[int]:
        """Confirmed new cells per training task in generations ``g - window`` .. ``g - 1``."""
        counts = [0] * len(self.tasks)
        for generation, ti, _, _ in self.events:
            if g - window <= generation < g:
                counts[ti] += 1
        return counts

    def state(self) -> dict:
        return {"grids": [grid.state() for grid in self.grids], "events": [list(e) for e in self.events]}

    def load(self, state: dict) -> None:
        for grid, saved in zip(self.grids, state["grids"], strict=True):
            grid.load(saved)
        self.events = [list(e) for e in state["events"]]

    def payload(self, layout) -> dict:
        """JSON summary for population snapshots: every filled cell's elite."""
        out = {}
        for grid in self.grids:
            cells = torch.nonzero(grid.filled)[:, 0].tolist()
            out[grid.task] = {"descriptors": ["/".join(n for n in d if n) for d in grid.descriptors],
                              "bounds": grid.bounds, "shape": grid.shape, "cells": cells,
                              "ids": grid.ids[cells].tolist(), "breeds": grid.breeds[cells].tolist(),
                              "values": grid.value[cells].tolist(), "counts": grid.count[cells].tolist(),
                              "since": grid.since[cells].tolist(),
                              "genomes": [layout.to_dict(grid.genomes[c]) for c in cells]}
        return out
