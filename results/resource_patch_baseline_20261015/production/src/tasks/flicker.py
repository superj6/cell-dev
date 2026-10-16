"""Rung 5, pick the light: two lights from opposite directions, one flickering fast and one slow, with the same mean
brightness. Point at the fast one. Needs temporal-frequency discrimination plus winner-take-all between sides.
"""
from __future__ import annotations

import torch

from src.tasks.base import Task, Trials, angles, light_gradient, unit


class FlickerTask(Task):
    name = "flicker"
    rung_id = 4
    ticks, warmup = 32, 16
    train_half_periods, heldout_half_periods = (1, 4), (2, 3)  # (fast, slow) ticks on, then the same ticks off

    def sample(self, pos, n, gen, heldout=False) -> Trials:
        fast_h, slow_h = self.heldout_half_periods if heldout else self.train_half_periods
        u = unit(angles(n, gen, heldout))
        u_fast = u  # the fast light comes from the balanced direction u; the slow one from -u
        t = torch.arange(self.ticks)
        phase = torch.randint(0, 2 * slow_h, (n, 1), generator=gen)
        on_fast = (((t[None] + phase) // fast_h) % 2 == 0).float()  # [E, T]
        on_slow = (((t[None] + phase) // slow_h) % 2 == 0).float()
        ones = torch.ones(n)
        f_fast = light_gradient(pos, u_fast, ones, self.length)
        f_slow = light_gradient(pos, -u_fast, ones, self.length)
        stim, window = self._empty(n, self.ticks, pos.shape[0])
        stim[..., 0] = on_fast[..., None] * f_fast[:, None] + on_slow[..., None] * f_slow[:, None]
        window[:, self.warmup:] = 1.0
        return Trials(stim=stim, window=window, target=u_fast, rung=torch.full((n,), self.rung_id))
