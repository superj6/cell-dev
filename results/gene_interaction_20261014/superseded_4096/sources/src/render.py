"""Draw tissues and spiking activity on any lattice with PIL, and write GIFs.

Cells are filled with their type colour; a cell that fires this tick is drawn white with a type-coloured rim. Empty
sites are tinted by the light falling on them. Arrows: black = target direction, red = activity direction so far.
"""
from __future__ import annotations

import math

import torch
from PIL import Image, ImageDraw

from src.lattice import Lattice

PALETTE = [(230, 97, 1), (33, 113, 181), (35, 139, 69), (106, 81, 163), (178, 24, 43), (120, 120, 120)]
EMPTY = (236, 236, 236)
SCALE = 16  # pixels per lattice unit


def _cell_polygon(lattice: Lattice, xy: tuple[float, float]) -> list[tuple[float, float]]:
    x, y = xy
    if lattice.kind == "hex":  # pointy-top hexagon, unit spacing between centres
        r = 1 / math.sqrt(3)
        return [(x + r * math.cos(math.radians(30 + 60 * k)), y + r * math.sin(math.radians(30 + 60 * k)))
                for k in range(6)]
    return [(x - 0.5, y - 0.5), (x + 0.5, y - 0.5), (x + 0.5, y + 0.5), (x - 0.5, y + 0.5)]


def _to_px(lattice: Lattice, pts, size: int):
    c = size / 2
    return [(c + px * SCALE, c - py * SCALE) for px, py in pts]


def draw(lattice: Lattice, alive: torch.Tensor, types: torch.Tensor, fire: torch.Tensor | None = None,
         light: torch.Tensor | None = None, cue: float = 0.0, target: torch.Tensor | None = None,
         activity: torch.Tensor | None = None, caption: str = "") -> Image.Image:
    size = int(2 * (lattice.radius + 1.5) * SCALE)
    img = Image.new("RGB", (size, size + 18), (255, 255, 255) if cue <= 0 else (255, 244, 214))
    d = ImageDraw.Draw(img)
    lmax = float(light.max()) if light is not None and float(light.max()) > 0 else 1.0
    for i in range(lattice.n):
        poly = _to_px(lattice, _cell_polygon(lattice, tuple(lattice.pos[i].tolist())), size)
        if bool(alive[i]):
            col = PALETTE[int(types[i]) % len(PALETTE)]
            if fire is not None and bool(fire[i]):
                d.polygon(poly, fill=(255, 255, 255), outline=col, width=3)
            else:
                d.polygon(poly, fill=col, outline=(255, 255, 255))
        else:
            t = 0.0 if light is None else min(1.0, float(light[i]) / lmax)
            fill = tuple(int(EMPTY[k] * (1 - t) + (255, 214, 80)[k] * t) for k in range(3))
            d.polygon(poly, fill=fill, outline=(255, 255, 255))
    centre = size / 2
    for vec, col in ((target, (0, 0, 0)), (activity, (220, 30, 30))):
        if vec is not None and float(torch.as_tensor(vec).norm()) > 0:
            v = torch.as_tensor(vec, dtype=torch.float32)
            v = v / v.norm() * (lattice.radius * 0.8)
            end = (centre + float(v[0]) * SCALE, centre - float(v[1]) * SCALE)
            d.line([(centre, centre), end], fill=col, width=3)
            d.ellipse([end[0] - 4, end[1] - 4, end[0] + 4, end[1] + 4], fill=col)
    if caption:
        d.text((6, size), caption, fill=(0, 0, 0))
    return img


def save_gif(frames: list[Image.Image], path, duration: int = 120) -> None:
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=duration, loop=0)


def development_gif(lattice: Lattice, history: list, path, b: int = 0) -> None:
    frames = [draw(lattice, alive[b], types[b], caption=f"growth step {t + 1}: {int(alive[b].sum())} cells")
              for t, (alive, types) in enumerate(history)]
    save_gif(frames, path, duration=150)


def activity_gif(lattice: Lattice, alive: torch.Tensor, types: torch.Tensor, raster: torch.Tensor,
                 stim: torch.Tensor, window: torch.Tensor, target: torch.Tensor, path, label: str = "") -> None:
    """One trial: raster [T, N] bool, stim [T, N, S], window [T], target [2]."""
    centre = (alive.float() @ lattice.pos) / alive.float().sum().clamp(min=1)
    rel = (lattice.pos - centre) * alive.float()[:, None]
    acc = torch.zeros(2)
    frames = []
    for t in range(raster.shape[0]):
        acc = acc + float(window[t]) * (raster[t].float()[:, None] * rel).sum(0)
        tag = "respond" if float(window[t]) > 0 else ""
        frames.append(draw(lattice, alive, types, fire=raster[t], light=stim[t, :, 0], cue=float(stim[t, :, 1].max()),
                           target=target, activity=acc, caption=f"{label} tick {t} {tag}"))
    save_gif(frames, path, duration=140)
