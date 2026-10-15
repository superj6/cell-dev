"""Rung 1, face the light: a light gradient comes from a random direction; point the activity toward it.

Two cells that fire when lit already score (about 0.64 on average); more cells point more precisely.
"""
from __future__ import annotations

import torch

from src.tasks.base import Task, Trials, angles, light_gradient, unit


class LightTask(Task):
    name = "light"
    rung_id = 0
    ticks, warmup = 16, 8

    def brightness(self, n: int, gen: torch.Generator, heldout: bool) -> torch.Tensor:
        return torch.ones(n)

    def sample(self, pos, n, gen, heldout=False) -> Trials:
        u = unit(angles(n, gen, heldout))
        field = light_gradient(pos, u, self.brightness(n, gen, heldout), self.length)  # [E, N]
        stim, window = self._empty(n, self.ticks, pos.shape[0])
        stim[..., 0] = field[:, None]
        window[:, self.warmup:] = 1.0
        return Trials(stim=stim, window=window, target=u, rung=torch.full((n,), self.rung_id))
