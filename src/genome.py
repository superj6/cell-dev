"""Genome: one flat parameter vector per individual, with named slices in two blocks.

- ``grn``: the developmental gene-regulatory network (how cells divide and differentiate);
- ``cell``: the spiking rule of each cell type (what grown cells do).

Crossover works on whole *units*, so children inherit each unit intact from one parent:
each gene (its regulatory row, its product's effects, its asymmetry and maternal level), each cell type (its whole
rule), and the remaining global parameters. Genes regulate each other through the rows they own, so a regulatory
input travels with the gene being regulated, as cis-regulatory DNA does.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class Dims:
    genes: int = 8
    morph: int = 2
    types: int = 4
    channels: int = 2
    stim: int = 2

    @property
    def grn_inputs(self) -> int:  # gene products, morphogens, neighbour fraction, age
        return self.genes + self.morph + 2

    @property
    def effectors(self) -> int:  # divide, asym, secrete[M], type logits[K]
        return 2 + self.morph + self.types


@dataclass(frozen=True)
class Field:
    name: str
    shape: tuple
    block: str  # grn | cell
    unit: str  # row | col | elem | global : how entries map onto crossover units
    init_std: float
    sigma: float  # mutation step


def _fields(d: Dims) -> list[Field]:
    G, M, K, C, S, A = d.genes, d.morph, d.types, d.channels, d.stim, d.effectors
    return [
        Field("W", (G, d.grn_inputs), "grn", "row", 1.0, 0.5),
        Field("b", (G,), "grn", "elem", 1.0, 0.5),
        Field("E", (A, G), "grn", "col", 1.5, 0.5),
        Field("e0", (A,), "grn", "global", 1.0, 0.5),
        Field("U", (M, G), "grn", "col", 1.0, 0.5),
        Field("u0", (M,), "grn", "global", 0.5, 0.5),
        Field("Q", (G,), "grn", "elem", 0.5, 0.25),
        Field("s0", (G,), "grn", "elem", 1.5, 0.5),
        Field("D", (M,), "grn", "global", 1.0, 0.5),
        Field("k", (M,), "grn", "global", 1.0, 0.5),
        Field("w", (K, C), "cell", "row", 0.75, 0.25),
        Field("gs", (K, S), "cell", "row", 0.75, 0.25),
        Field("bias", (K,), "cell", "elem", 0.5, 0.25),
        Field("leak", (K,), "cell", "elem", 1.0, 0.6),
        Field("refr", (K,), "cell", "elem", 1.0, 0.6),
        Field("emit", (K, C), "cell", "row", 1.0, 1.0),
    ]


class Layout:
    """Named slices of the flat genome plus the per-entry metadata that mutation and crossover need."""

    def __init__(self, dims: Dims):
        self.dims = dims
        self.fields = _fields(dims)
        self.slices: dict[str, tuple[int, int, tuple]] = {}
        units, blocks, init_std, sigma = [], [], [], []
        G, K = dims.genes, dims.types
        offset = 0
        for f in self.fields:
            n = math.prod(f.shape)
            self.slices[f.name] = (offset, offset + n, f.shape)
            offset += n
            idx = torch.arange(n).reshape(f.shape)
            base = 0 if f.block == "grn" else G  # gene units come first, then type units, then one global unit
            if f.unit == "row":
                u = base + (idx // f.shape[1]) if len(f.shape) == 2 else base + idx
            elif f.unit == "col":
                u = base + (idx % f.shape[1])
            elif f.unit == "elem":
                u = base + idx
            else:
                u = torch.full_like(idx, G + K)
            units.append(u.reshape(-1))
            blocks.append(torch.full((n,), 0 if f.block == "grn" else 1))
            init_std.append(torch.full((n,), f.init_std))
            sigma.append(torch.full((n,), f.sigma))
        self.size = offset
        self.n_units = G + K + 1
        self.unit_of = torch.cat(units)
        self.block_of = torch.cat(blocks)
        self.init_std = torch.cat(init_std)
        self.sigma = torch.cat(sigma)

    def view(self, params: torch.Tensor, name: str) -> torch.Tensor:
        a, b, shape = self.slices[name]
        return params[..., a:b].reshape(*params.shape[:-1], *shape)

    def random(self, n: int, gen: torch.Generator, scale: float = 1.0) -> torch.Tensor:
        return torch.randn(n, self.size, generator=gen) * self.init_std * scale

    def mutate(self, params: torch.Tensor, gen: torch.Generator, n_mut: int = 2, p_cell: float = 0.5) -> torch.Tensor:
        """Each child mutates ``n_mut`` entries inside one block (grn or cell), chosen per child."""
        B = params.shape[0]
        block = (torch.rand(B, 1, generator=gen) < p_cell).long()  # 1 = cell block
        in_block = self.block_of[None, :] == block
        scores = torch.rand(B, self.size, generator=gen).masked_fill(~in_block, -1.0)
        pick = scores.topk(n_mut, dim=1).indices
        noise = torch.randn(B, n_mut, generator=gen) * self.sigma[pick]
        out = params.clone()
        out.scatter_add_(1, pick, noise)
        return out

    def crossover(self, pa: torch.Tensor, pb: torch.Tensor, gen: torch.Generator) -> torch.Tensor:
        """Uniform crossover over units: each gene, cell type and the global unit comes whole from one parent."""
        bits = torch.rand(pa.shape[0], self.n_units, generator=gen) < 0.5
        return torch.where(bits[:, self.unit_of], pa, pb)

    def to_dict(self, params: torch.Tensor) -> dict:
        return {f.name: self.view(params, f.name).tolist() for f in self.fields}

    def from_dict(self, d: dict) -> torch.Tensor:
        return torch.cat([torch.tensor(d[f.name], dtype=torch.float32).reshape(-1) for f in self.fields])

    def save(self, params: torch.Tensor, path) -> None:
        payload = {"dims": self.dims.__dict__, "params": self.to_dict(params)}
        with open(path, "w") as fh:
            json.dump(payload, fh)

    @staticmethod
    def load(path) -> tuple["Layout", torch.Tensor]:
        with open(path) as fh:
            payload = json.load(fh)
        layout = Layout(Dims(**payload["dims"]))
        return layout, layout.from_dict(payload["params"])
