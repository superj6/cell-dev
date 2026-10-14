"""Rung 3, remember: a short flash from a random direction, a random dark delay, then a uniform "go" cue on
channel 1. Point toward where the flash was while the cue is on.
Caveat (code review, 2026-10-06): the training delays (4-10 ticks) sit inside a slow cell's leak trace, so one cell
type with messages off reaches about 0.5 on training-distribution ("valid") trials. Only the held-out delays (12-18)
exclude that; every evolved memory solution so far nevertheless scores 0.00 with messages off on both splits.
"""
from __future__ import annotations

import torch

from src.tasks.base import Task, Trials, angles, light_gradient, unit


class MemoryTask(Task):
    name = "memory"
    rung_id = 2
    flash, cue = 4, 8
    train_delay, heldout_delay = (4, 10), (12, 18)

    def sample(self, pos, n, gen, heldout=False) -> Trials:
        lo, hi = self.heldout_delay if heldout else self.train_delay
        delay = torch.randint(lo, hi + 1, (n,), generator=gen)
        T = self.flash + hi + self.cue
        u = unit(angles(n, gen, heldout))
        field = light_gradient(pos, u, torch.ones(n), self.length)
        stim, window = self._empty(n, T, pos.shape[0])
        stim[:, : self.flash, :, 0] = field[:, None]
        for e in range(n):
            start = self.flash + int(delay[e])
            stim[e, start: start + self.cue, :, 1] = 1.0
            window[e, start: start + self.cue] = 1.0
        return Trials(stim=stim, window=window, target=u, rung=torch.full((n,), self.rung_id))
