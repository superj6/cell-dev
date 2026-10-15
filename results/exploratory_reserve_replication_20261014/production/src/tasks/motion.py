"""Rung 4, motion: a light spot drifts across the fabric in a random direction; point the way it is moving.

Scored over the whole symmetric pass, so "fire where lit" (which points at the spot) averages to about 0.
Caveat (code review, 2026-10-06): this does NOT force messages. A single uniform cell type with messages off (tonic
cells that the passing light silences, i.e. single-cell adaptation plus timing) reaches about 0.3-0.5, and evolved
motion solutions use type placement rather than messaging. For a rung that needs information to travel, use ``jump``.
"""
from __future__ import annotations

import math

import torch

from src.tasks.base import Task, Trials, angles, unit


class MotionTask(Task):
    name = "motion"
    rung_id = 3
    half_path, spot_sigma, peak, view = 8.0, 1.5, 2.0, 6.0
    train_speeds, heldout_speeds = (0.5, 1.0), (0.75, 1.5)

    def sample(self, pos, n, gen, heldout=False) -> Trials:
        speeds = torch.tensor(self.heldout_speeds if heldout else self.train_speeds)
        speed = speeds[torch.randint(len(speeds), (n,), generator=gen)]
        T = int(math.ceil(2 * self.half_path / float(speeds.min()))) + 1
        u = unit(angles(n, gen, heldout))
        perp = torch.stack([-u[:, 1], u[:, 0]], dim=-1)
        offset = (torch.rand(n, generator=gen) * 3.0 - 1.5)[:, None] * perp
        t = torch.arange(T).float()
        along = -self.half_path + speed[:, None] * t[None]  # [E, T] position along the path
        centre = along[..., None] * u[:, None] + offset[:, None]  # [E, T, 2]
        d2 = ((pos[None, None] - centre[:, :, None]) ** 2).sum(-1)  # [E, T, N]
        stim = torch.zeros(n, T, pos.shape[0], 2)
        live = along <= self.half_path
        stim[..., 0] = self.peak * torch.exp(-d2 / (2 * self.spot_sigma ** 2)) * live[..., None]
        window = ((along.abs() <= self.view) & live).float()
        return Trials(stim=stim, window=window, target=u, rung=torch.full((n,), self.rung_id))
