"""Development: every genome grows a tissue from one seed cell, using only local information.

Per step, each living cell (batched over B genomes):
1. senses its own gene products, the morphogens at its site, the fraction of occupied neighbour slots and its age;
2. updates its gene state through the genome's GRN;
3. secretes morphogens, which diffuse over the lattice (absorbing edges) and decay;
4. may divide into an empty neighbouring site, chosen by how its gene state weighs the morphogens there.
   Two cells claiming one site: the higher divide logit wins. The daughter gets ``g + asym*Q``, the mother ``g - asym*Q``.
Growth is deterministic per genome and independent of what else is in the batch (tie jitter is seeded per run).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import torch

from src.genome import Layout
from src.lattice import Lattice

D_SAFETY = 0.9  # diffusion coefficient stays below 1/contact for explicit-Euler stability


@dataclass
class Tissue:
    alive: torch.Tensor  # [B, N] bool
    g: torch.Tensor  # [B, N, G] gene state
    types: torch.Tensor  # [B, N] long (0 on empty sites)
    divisions: torch.Tensor  # [B] long
    history: list = field(default_factory=list)  # per step (alive, types) when recorded

    @property
    def n_cells(self) -> torch.Tensor:
        return self.alive.sum(1)


def decode_grn(layout: Layout, params: torch.Tensor, lattice: Lattice) -> dict:
    v = lambda name: layout.view(params, name)  # noqa: E731
    d_max = D_SAFETY / lattice.full_contact
    return {
        "W": v("W"), "b": v("b"), "E": v("E"), "e0": v("e0"), "U": v("U"), "u0": v("u0"), "Q": v("Q"),
        "s0": torch.sigmoid(v("s0")),
        "D": d_max * torch.sigmoid(v("D")),
        "k": 0.01 + 0.3 * torch.sigmoid(v("k")),
    }


def diffuse(lattice: Lattice, morph: torch.Tensor, D: torch.Tensor, k: torch.Tensor, substeps: int) -> torch.Tensor:
    """Explicit-Euler diffusion over the lattice with absorbing edges, then decay. morph [B, N, M]; D, k [B, M]."""
    contact, full = lattice.contact[None, :, :, None], lattice.full_contact
    for _ in range(substeps):
        lap = (lattice.gather(morph) * contact).sum(2) - full * morph
        morph = (1 - k[:, None]) * (morph + D[:, None] * lap)
    return morph


def _effectors(g, p):
    return torch.einsum("bng,bag->bna", g, p["E"]) + p["e0"][:, None]


def develop(lattice: Lattice, layout: Layout, params: torch.Tensor, steps: int = 24, rate: float = 0.5,
            min_cycle: int = 2, substeps: int = 4, secretion: float = 0.5, jitter_seed: int = 0,
            record: bool = False) -> Tissue:
    dims = layout.dims
    G, M = dims.genes, dims.morph
    B, N, Dn = params.shape[0], lattice.n, lattice.d
    p = decode_grn(layout, params, lattice)
    slot_ok = lattice.mask[None]  # [1, N, D]
    nbr = lattice.nbr.clamp(min=0)[None].expand(B, N, Dn)

    jit = torch.Generator().manual_seed(jitter_seed)
    jit_dir = torch.rand(N, Dn, generator=jit) * 1e-3
    jit_cell = torch.rand(N, generator=jit) * 1e-3

    alive = torch.zeros(B, N, dtype=torch.bool)
    alive[:, lattice.center] = True
    g = torch.zeros(B, N, G)
    g[:, lattice.center] = p["s0"]
    age = torch.zeros(B, N)
    morph = torch.zeros(B, N, M)
    divisions = torch.zeros(B, dtype=torch.long)
    history = []
    idx = torch.arange(N).expand(B, N)
    t_idx = 2 + M  # first type logit

    for _ in range(steps):
        af = alive.float()
        nb_alive = lattice.gather(af[..., None])[..., 0]  # [B, N, D]
        n_frac = nb_alive.sum(-1) / Dn
        x = torch.cat([g, morph, n_frac[..., None], (age.clamp(max=8) / 8)[..., None]], dim=-1)
        pre = torch.einsum("bni,bgi->bng", x, p["W"]) + p["b"][:, None]
        g = ((1 - rate) * g + rate * torch.sigmoid(pre)) * af[..., None]
        y = _effectors(g, p)

        morph = morph + secretion * torch.sigmoid(y[..., 2:t_idx]) * af[..., None]
        morph = diffuse(lattice, morph, p["D"], p["k"], substeps)

        empty_nb = slot_ok & (nb_alive < 0.5)
        div_logit = y[..., 0]
        want = alive & (div_logit > 0) & (age >= min_cycle) & empty_nb.any(-1)
        if want.any():
            v = torch.tanh(torch.einsum("bng,bmg->bnm", g, p["U"]) + p["u0"][:, None])
            score = (v[:, :, None, :] * lattice.gather(morph)).sum(-1) + jit_dir
            choice = score.masked_fill(~empty_nb, float("-inf")).argmax(-1)  # [B, N]
            target = torch.gather(nbr, 2, choice[..., None])[..., 0]
            target = torch.where(want, target, torch.zeros_like(target))
            strength = torch.where(want, div_logit + jit_cell, torch.full_like(div_logit, float("-inf")))
            best = torch.full((B, N), float("-inf")).scatter_reduce(1, target, strength, "amax")
            win = want & (strength >= best.gather(1, target))
            first = torch.full((B, N), N).scatter_reduce(1, target, torch.where(win, idx, N), "amin")
            win = win & (idx == first.gather(1, target))  # exact ties: lowest mother index
            bb, mm = win.nonzero(as_tuple=True)
            tt = target[bb, mm]
            q = torch.sigmoid(y[bb, mm, 1])[:, None] * p["Q"][bb]
            gm = g[bb, mm]
            g[bb, tt] = (gm + q).clamp(0, 1)
            g[bb, mm] = (gm - q).clamp(0, 1)
            alive[bb, tt] = True
            age[bb, mm] = -1  # both restart their cycle at 0 after the increment below
            age[bb, tt] = -1
            divisions += win.sum(1)
        age = (age + 1) * alive
        if record:
            types = _effectors(g, p)[..., t_idx:].argmax(-1) * alive
            history.append((alive.clone(), types))

    types = _effectors(g, p)[..., t_idx:].argmax(-1) * alive
    return Tissue(alive=alive, g=g, types=types, divisions=divisions, history=history)
