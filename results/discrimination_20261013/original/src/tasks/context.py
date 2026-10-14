"""Context switch: a brief cue spot near the centre decides whether to face the light or turn away from it.

Trials come in pairs that share a light direction u and all timings. In the uncued trial nothing happens until a light
gradient from u comes on; the target is +u. In the cued trial a small cue spot (channel 1, the site and its lattice
neighbours, 2-3 ticks) first appears at a random site within ``cue_reach`` of the fabric centre, then, after a dark gap,
the same light comes on; the target is -u. Scoring covers the late part of the light period.

Why it needs messages:
- Any tissue that ignores the cue fires identically in both trials of a pair, so its scores cancel exactly (0).
- The cue's site and timing are drawn independently of u, so they carry no information about the answer.
- Only the few cells under the spot can sense the cue, and only before the light. Without messages a leaky
  integrate-and-fire cell cannot turn "I saw the cue" into extra firing later (sub-threshold charge only decays toward
  its light-driven level), so at best the cue silences the cells under the spot. That turns some cued trials from -s to
  0, but only when the spot happens to cover every cell that would fire, which a 7-site spot rarely does.
So the context has to be broadcast through the tissue, held through the gap, and used to flip the light response.

Held-out: directions halfway between the training ones, and a much longer cue-to-light gap.
"""
from __future__ import annotations

import torch

from src.tasks.base import Task, Trials, angles, light_gradient, unit


def paired_angles(m: int, gen: torch.Generator, heldout: bool = False) -> torch.Tensor:
    """m directions spread evenly over the circle (every other one of a balanced ``angles(2m)`` draw), shuffled.

    With m = 6 this is a random one of the two 60-degree families, with m = 12 or 24 every direction appears equally
    often, so the directions within each half (cued, uncued) sum to zero.
    """
    k = angles(2 * m, gen, heldout).sort().values
    start = int(torch.randint(2, (1,), generator=gen))
    k = k[start::2][:m]
    return k[torch.randperm(k.shape[0], generator=gen)]


class ContextTask(Task):
    name = "context"
    rung_id = 10
    cue_reach = 2.0  # cue spot centred on a site at most this far from the fabric centre
    cue_radius = 1.0  # spot = the centre site and every site within this distance (hex: 7 sites)
    cue_start = (1, 3)  # first cue tick
    cue_ticks = (2, 3)
    train_gap, heldout_gap = (4, 8), (12, 20)  # dark ticks between the cue's end and light onset
    warmup, view = 3, 8  # light stays on for warmup + view ticks; only the last ``view`` ticks are scored

    def sample(self, pos, n, gen, heldout=False) -> Trials:
        N = pos.shape[0]
        n_cued = n // 2
        m = n - n_cued  # one uncued trial per pair, plus one unpaired uncued trial when n is odd
        lo, hi = self.heldout_gap if heldout else self.train_gap
        T = self.cue_start[1] + self.cue_ticks[1] + hi + self.warmup + self.view

        u = unit(paired_angles(m, gen, heldout))  # [m, 2]
        start = torch.randint(self.cue_start[0], self.cue_start[1] + 1, (m,), generator=gen)
        dur = torch.randint(self.cue_ticks[0], self.cue_ticks[1] + 1, (m,), generator=gen)
        gap = torch.randint(lo, hi + 1, (m,), generator=gen)
        onset = start + dur + gap
        field = light_gradient(pos, u, torch.ones(m), self.length)  # [m, N]

        stim, window = self._empty(m, T, N)
        for e in range(m):
            a = int(onset[e])
            stim[e, a: a + self.warmup + self.view, :, 0] = field[e]
            window[e, a + self.warmup: a + self.warmup + self.view] = 1.0

        # cued twins: same light and timing, plus a cue spot at a site near the centre chosen independently of u
        near = (pos.norm(dim=1) <= self.cue_reach + 1e-3).nonzero().squeeze(1)
        centre = near[torch.randint(near.shape[0], (n_cued,), generator=gen)]
        spot = ((pos[None] - pos[centre][:, None]).norm(dim=-1) <= self.cue_radius + 1e-3).float()  # [n_cued, N]
        cued = stim[:n_cued].clone()
        for e in range(n_cued):
            a = int(start[e])
            cued[e, a: a + int(dur[e]), :, 1] = spot[e]

        return Trials(stim=torch.cat([stim, cued]), window=torch.cat([window, window[:n_cued]]),
                      target=torch.cat([u, -u[:n_cued]]), rung=torch.full((n,), self.rung_id))
