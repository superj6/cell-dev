"""Trials, stimulus fields and the spatial readout shared by every task.

There are no input or output cells. Every site gets a stimulus value per channel (channel 0 = light, channel 1 = cue)
and the environment reads *where* the firing ends up: the activity vector is the spike-weighted sum of each cell's
offset from the body centre over the response window. A trial scores how decisively that firing sits on the target
side (see ``direction_score``), and 0 if the tissue stays silent. Targets are balanced over directions, so chance,
constant and one-cell answers score 0.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import torch

ANGLES = 12  # training directions: multiples of 30 degrees; held-out directions sit halfway between


@dataclass
class Trials:
    stim: torch.Tensor  # [E, T, N, S]
    window: torch.Tensor  # [E, T] response-window weights
    target: torch.Tensor  # [E, 2] unit vectors
    rung: torch.Tensor  # [E] long, which rung each trial came from

    @property
    def n(self) -> int:
        return self.window.shape[0]


def unit(theta: torch.Tensor) -> torch.Tensor:
    return torch.stack([torch.cos(theta), torch.sin(theta)], dim=-1)


def angles(n: int, gen: torch.Generator, heldout: bool = False) -> torch.Tensor:
    """Balanced directions: every training angle once per 12 trials (random order and subset when n < 12)."""
    k = torch.cat([torch.randperm(ANGLES, generator=gen) for _ in range(math.ceil(n / ANGLES))])[:n].float()
    return (k + (0.5 if heldout else 0.0)) * (2 * math.pi / ANGLES)


def light_gradient(pos: torch.Tensor, u: torch.Tensor, brightness: torch.Tensor, length: float) -> torch.Tensor:
    """Exponential light field from direction u: [E, N]; equals ``brightness`` at the fabric centre."""
    return brightness[:, None] * torch.exp((u @ pos.T) / length)


def log_uniform(n: int, lo: float, hi: float, gen: torch.Generator) -> torch.Tensor:
    return torch.exp(math.log(lo) + (math.log(hi) - math.log(lo)) * torch.rand(n, generator=gen))


def concat(trials: list[Trials]) -> Trials:
    """Stack trials with different lengths by zero-padding the end of shorter ones."""
    T = max(t.window.shape[1] for t in trials)

    def pad(x: torch.Tensor) -> torch.Tensor:
        extra = T - x.shape[1]
        return torch.cat([x, torch.zeros(x.shape[0], extra, *x.shape[2:])], dim=1) if extra else x

    return Trials(stim=torch.cat([pad(t.stim) for t in trials]), window=torch.cat([pad(t.window) for t in trials]),
                  target=torch.cat([t.target for t in trials]), rung=torch.cat([t.rung for t in trials]))


def activity_vector(counts: torch.Tensor, pos: torch.Tensor, alive: torch.Tensor) -> torch.Tensor:
    """counts [B, E, N] -> spike-weighted offsets from the body centre [B, E, 2]."""
    af = alive.float()
    centre = (af @ pos) / af.sum(1, keepdim=True).clamp(min=1)  # [B, 2]
    rel = (pos[None] - centre[:, None]) * af[..., None]  # [B, N, 2]
    return torch.einsum("ben,bnd->bed", counts, rel)


def direction_score(counts: torch.Tensor, pos: torch.Tensor, alive: torch.Tensor, target: torch.Tensor,
                    min_spikes: float = 1.0, kind: str = "lateral") -> torch.Tensor:
    """Per-trial score [B, E]; 0 when fewer than ``min_spikes`` spikes fell in the window.

    ``lateral`` (default): spike-weighted mean cosine of each firing cell's offset from the body centre, i.e.
    (a . target) / sum(spikes * |offset|). It is 1 only when all firing sits on the target side, about 0 for a slight
    lean, and negative for the wrong side: "which half fires more", for any direction.
    ``cos``: cos(activity vector, target), which ignores magnitude, so a slight lean already gets full credit.
    """
    a = activity_vector(counts, pos, alive)
    if kind == "lateral":
        af = alive.float()
        centre = (af @ pos) / af.sum(1, keepdim=True).clamp(min=1)
        dist = (pos[None] - centre[:, None]).norm(dim=-1) * af  # [B, N]
        denom = torch.einsum("ben,bn->be", counts, dist)
    elif kind == "cos":
        denom = a.norm(dim=-1)
    else:
        raise ValueError(f"unknown score kind {kind!r}")
    score = (a * target[None]).sum(-1) / denom.clamp(min=1e-6)
    ok = (counts.sum(-1) >= min_spikes) & (denom > 1e-6)
    return torch.where(ok, score, torch.zeros_like(score))


class Task:
    name = "task"
    rung_id = 0

    def __init__(self, length: float = 4.0):
        self.length = length  # light-field length scale (sites per e-fold)

    def sample(self, pos: torch.Tensor, n: int, gen: torch.Generator, heldout: bool = False) -> Trials:
        raise NotImplementedError

    def _empty(self, n: int, T: int, N: int, S: int = 2) -> tuple[torch.Tensor, torch.Tensor]:
        return torch.zeros(n, T, N, S), torch.zeros(n, T)
