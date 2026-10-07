"""Lattices as neighbour tables, so every operation is a gather and lattice kinds are swappable.

A ``Lattice`` has N sites with 2D positions (unit spacing between neighbouring centres), a padded neighbour table
``nbr[N, D]`` (-1 where a slot is empty) with its ``mask``, and a weight per contact. Edge sites simply have fewer
neighbours: there is no wraparound. ``build_lattice`` gives every kind a disk-shaped fabric so kinds are comparable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import torch

# neighbour offsets in each lattice's own integer coordinates
_HEX_AXIAL = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
_SQUARE4 = [(1, 0), (0, 1), (-1, 0), (0, -1)]
_SQUARE8 = _SQUARE4 + [(1, 1), (-1, 1), (-1, -1), (1, -1)]


@dataclass
class Lattice:
    kind: str
    pos: torch.Tensor  # [N, 2] float32
    nbr: torch.Tensor  # [N, D] int64, -1 where the slot is empty
    mask: torch.Tensor  # [N, D] bool
    contact: torch.Tensor  # [N, D] float32, 0 where the slot is empty
    center: int  # site nearest the origin (where the seed starts)
    radius: float  # fabric radius in position units

    @property
    def n(self) -> int:
        return self.pos.shape[0]

    @property
    def d(self) -> int:
        return self.nbr.shape[1]

    @property
    def full_contact(self) -> float:
        """Total contact weight of an interior site (used for absorbing-boundary diffusion)."""
        return float(self.contact.sum(1).max())

    def gather(self, x: torch.Tensor) -> torch.Tensor:
        """``x[..., N, F]`` -> neighbour values ``[..., N, D, F]``; empty slots read 0."""
        pad = torch.zeros(*x.shape[:-2], 1, x.shape[-1], dtype=x.dtype, device=x.device)
        xp = torch.cat([x, pad], dim=-2)
        idx = torch.where(self.mask, self.nbr, torch.full_like(self.nbr, self.n)).reshape(-1)
        return xp.index_select(xp.dim() - 2, idx).reshape(*x.shape[:-2], self.n, self.d, x.shape[-1])


def _build(kind: str, coords, offsets, to_xy, radius: float, contact: str) -> Lattice:
    index = {c: i for i, c in enumerate(coords)}
    nbr = torch.full((len(coords), len(offsets)), -1, dtype=torch.long)
    for i, (a, b) in enumerate(coords):
        for k, (da, db) in enumerate(offsets):
            j = index.get((a + da, b + db))
            if j is not None:
                nbr[i, k] = j
    pos = torch.tensor([to_xy(a, b) for a, b in coords], dtype=torch.float32)
    mask = nbr >= 0
    if contact == "uniform":
        weight = mask.float()
    elif contact == "inverse_distance":  # diagonal (corner) contacts count less
        dist = (pos[:, None, :] - pos[nbr.clamp(min=0)]).norm(dim=-1)
        dist = torch.where((dist - 1).abs() < 1e-5, torch.ones_like(dist), dist)  # unit contacts weigh exactly 1
        weight = torch.where(mask, 1.0 / dist.clamp(min=1e-6), torch.zeros_like(dist))
    else:
        raise ValueError(f"unknown contact mode {contact!r}")
    center = int(pos.norm(dim=1).argmin())
    return Lattice(kind=kind, pos=pos, nbr=nbr, mask=mask, contact=weight, center=center, radius=float(radius))


def hex_lattice(radius: int, contact: str = "uniform") -> Lattice:
    """Hexagonal fabric of side ``radius`` (3r(r+1)+1 sites), 6 neighbours per interior site."""
    coords = [(q, r) for q in range(-radius, radius + 1) for r in range(-radius, radius + 1) if abs(q + r) <= radius]
    return _build("hex", coords, _HEX_AXIAL, lambda q, r: (q + r / 2, r * math.sqrt(3) / 2), radius, contact)


def square_lattice(radius: int, neighbours: int = 4, contact: str = "uniform") -> Lattice:
    """Disk of a square grid (sites within radius + 0.5), with 4 (edge) or 8 (edge + corner) neighbours."""
    offsets = {4: _SQUARE4, 8: _SQUARE8}[neighbours]
    r2 = (radius + 0.5) ** 2
    coords = [(i, j) for i in range(-radius, radius + 1) for j in range(-radius, radius + 1) if i * i + j * j <= r2]
    return _build(f"square{neighbours}", coords, offsets, lambda i, j: (float(i), float(j)), radius + 0.5, contact)


def build_lattice(kind: str = "hex", radius: int = 9, contact: str = "uniform") -> Lattice:
    if kind == "hex":
        return hex_lattice(radius, contact)
    if kind in ("square4", "square8"):
        return square_lattice(radius, int(kind[-1]), contact)
    raise ValueError(f"unknown lattice kind {kind!r} (hex | square4 | square8)")


# Sparse-fabric helpers for the one-life kernel (docs/LIFE_ABI.md). Slots keep each kind's native order above;
# ``cyclic_order`` gives the angular order that flank counts and the chiral term need.
_OFFSETS = {"hex": _HEX_AXIAL, "square4": _SQUARE4, "square8": _SQUARE8}
_SQRT3_2 = math.sqrt(3) / 2


def offsets(kind: str) -> list[tuple[int, int]]:
    """Neighbour offsets of ``kind`` in its own integer coordinates, in the native slot order."""
    if kind not in _OFFSETS:
        raise ValueError(f"unknown lattice kind {kind!r} (hex | square4 | square8)")
    return list(_OFFSETS[kind])


def to_xy(kind: str, a: int, b: int) -> tuple[float, float]:
    """Position of integer coordinates (a, b) in the plane (unit spacing between edge neighbours)."""
    if kind == "hex":
        return (a + b / 2, b * _SQRT3_2)
    offsets(kind)
    return (float(a), float(b))


def unit_vectors(kind: str) -> list[tuple[float, float]]:
    """Unit vector from a site towards each slot's neighbour (square8 diagonals normalized)."""
    out = []
    for da, db in offsets(kind):
        x, y = to_xy(kind, da, db)
        n = math.hypot(x, y)
        out.append((x, y) if abs(n - 1.0) < 1e-12 else (x / n, y / n))
    return out


def back_slots(kind: str) -> list[int]:
    """``back[d]``: the slot of the neighbour that points back at us, found by lookup (not ``(d + D/2) % D``)."""
    off = offsets(kind)
    return [off.index((-da, -db)) for da, db in off]


def cyclic_order(kind: str) -> list[int]:
    """Slots sorted by angle, counter-clockwise from +x."""
    ang = [math.atan2(y, x) % (2 * math.pi) for x, y in unit_vectors(kind)]
    return sorted(range(len(ang)), key=lambda d: ang[d])


def cyclic_neighbours(kind: str) -> list[tuple[int, int]]:
    """Per slot ``(prev, next)``: the angularly adjacent slots clockwise and counter-clockwise."""
    cyc = cyclic_order(kind)
    D = len(cyc)
    out = [(0, 0)] * D
    for i, d in enumerate(cyc):
        out[d] = (cyc[(i - 1) % D], cyc[(i + 1) % D])
    return out


def rotation_steps(kind: str) -> int:
    """Number of rotations in the lattice's rotation group (60 degrees on hex, 90 degrees on square lattices)."""
    offsets(kind)
    return 6 if kind == "hex" else 4


def rotate(kind: str, a: int, b: int, k: int = 1) -> tuple[int, int]:
    """Rotate coordinates counter-clockwise by ``k`` elementary steps (60 degrees on hex, 90 on square)."""
    for _ in range(k % rotation_steps(kind)):
        a, b = (-b, a + b) if kind == "hex" else (-b, a)
    return a, b


def mirror(kind: str, a: int, b: int) -> tuple[int, int]:
    """Reflect coordinates across the x axis (y -> -y)."""
    offsets(kind)
    return (a + b, -b) if kind == "hex" else (a, -b)


def slot_map(kind: str, fn) -> list[int]:
    """Slot permutation ``p`` induced by a coordinate map: ``offsets[p[d]] == fn(*offsets[d])``."""
    off = offsets(kind)
    return [off.index(tuple(fn(da, db))) for da, db in off]


def in_disk(kind: str, a: int, b: int, radius: int) -> bool:
    """Whether (a, b) belongs to the dense disk fabric of ``radius`` (the same sites ``build_lattice`` makes)."""
    if kind == "hex":
        return max(abs(a), abs(b), abs(a + b)) <= radius
    offsets(kind)
    return a * a + b * b <= (radius + 0.5) ** 2
