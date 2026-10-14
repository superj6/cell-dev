"""Spiking cells on a grown tissue: a quantized leaky integrate-and-fire rule per cell type.

Each tick, a cell sums the spikes its lattice neighbours sent on each channel last tick (weighted per channel),
adds the stimulus at its own site (gain per stimulus channel) and a bias, leaks, and fires at threshold 1. After firing
it resets to 0 and is refractory for R ticks; its spike goes out on the channels its type emits. Nothing else is
visible to a cell, so every computation is local. Parameters are quantized (weights in 1/8 steps over [-2, 2], leak a
power of two, small integer refractory counts) so each cell type maps onto a small fixed-point circuit.
Known limitation: the potential is a float32, not a true fixed-point register. A cell whose potential converges to
exactly the threshold from below (e.g. bias = leak = 1/2) can round up to 1.0 after about 24 ticks and fire, which
exact arithmetic never would. A code review found this changes one saved score by 0.0007; a fixed-point integer
potential is the clean fix.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch

from src.genome import Layout
from src.lattice import Lattice

LEAKS = torch.tensor([1 / 2, 1 / 4, 1 / 8, 1 / 16])


@dataclass
class CellRule:
    w: torch.Tensor  # [B, K, C] weight per incoming channel
    gs: torch.Tensor  # [B, K, S] gain per stimulus channel
    bias: torch.Tensor  # [B, K]
    leak: torch.Tensor  # [B, K] fraction of v lost per tick
    refr: torch.Tensor  # [B, K] long, refractory ticks after a spike
    emit: torch.Tensor  # [B, K, C] {0, 1}: channels a spike goes out on


def _q(x: torch.Tensor, quantize: bool) -> torch.Tensor:
    x = x.clamp(-2.0, 2.0)
    return torch.round(x * 8) / 8 if quantize else x


def decode_cells(layout: Layout, params: torch.Tensor, quantize: bool = True) -> CellRule:
    v = lambda name: layout.view(params, name)  # noqa: E731
    leak_i = (v("leak") + 1.5).round().clamp(0, 3).long()
    return CellRule(
        w=_q(v("w"), quantize),
        gs=_q(v("gs"), quantize),
        bias=_q(v("bias"), quantize),
        leak=LEAKS[leak_i],
        refr=(v("refr") + 1.5).round().clamp(0, 3).long(),
        emit=(v("emit") > 0).float(),
    )


def _per_cell(x: torch.Tensor, types: torch.Tensor) -> torch.Tensor:
    """Per-type parameters [B, K, ...] -> per-site maps [B, N, ...]."""
    B, N = types.shape
    idx = types.reshape(B, N, *([1] * (x.dim() - 2))).expand(B, N, *x.shape[2:])
    return torch.gather(x, 1, idx)


@dataclass
class Activity:
    counts: torch.Tensor  # [B, E, N] spikes inside each trial's response window
    spikes: torch.Tensor  # [B] mean spikes per tick (whole tissue, all trials)
    raster: torch.Tensor | None = None  # [T, B, E, N] bool, when recorded


def run_cells(lattice: Lattice, alive: torch.Tensor, types: torch.Tensor, rule: CellRule, stim: torch.Tensor,
              window: torch.Tensor, messages: bool = True, record: bool = False) -> Activity:
    """Simulate E trials per genome.

    stim: [E, T, N, S] stimulus at every site (shared by all genomes); window: [E, T] response-window weights.
    """
    B, N = alive.shape
    E, T = window.shape
    C = rule.w.shape[-1]
    w = _per_cell(rule.w, types)[:, None]  # [B, 1, N, C]
    gs = _per_cell(rule.gs, types)[:, None]  # [B, 1, N, S]
    bias = _per_cell(rule.bias, types)[:, None]  # [B, 1, N]
    leak = _per_cell(rule.leak, types)[:, None]
    refr = _per_cell(rule.refr, types)[:, None].expand(B, E, N)
    emit = _per_cell(rule.emit, types)[:, None]  # [B, 1, N, C]
    live = alive[:, None]  # [B, 1, N]
    contact = lattice.contact[None, :, :, None]

    v = torch.zeros(B, E, N)
    ref = torch.zeros(B, E, N, dtype=torch.long)
    spk = torch.zeros(B, E, N, C)
    counts = torch.zeros(B, E, N)
    total = torch.zeros(B)
    raster = []
    for t in range(T):
        drive = (gs * stim[None, :, t]).sum(-1) + bias  # [B, E, N]
        if messages:
            n_c = (lattice.gather(spk.reshape(B * E, N, C)) * contact).sum(2).reshape(B, E, N, C)
            drive = drive + (w * n_c).sum(-1)
        refractory = ref > 0
        v = torch.where(refractory, torch.zeros_like(v), v - leak * v + drive)
        fire = live & ~refractory & (v >= 1.0)
        v = torch.where(fire, torch.zeros_like(v), v)
        ref = torch.where(fire, refr, (ref - 1).clamp(min=0))
        f = fire.float()
        spk = f[..., None] * emit
        counts += f * window[None, :, t, None]
        total += f.sum((1, 2))
        if record:
            raster.append(fire.clone())
    return Activity(counts=counts, spikes=total / (E * T), raster=torch.stack(raster) if record else None)
