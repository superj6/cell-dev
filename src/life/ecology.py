"""Open worlds (docs/OPEN_WORLDS.md): per-life eco worlds drawn from wide parameter ranges.

Each family is a region of one shared parameter space (OPEN_WORLDS.md 3, 5): it emphasises one objective and carries
the other ingredients at random background levels. ``realize(family, seed)`` turns a life seed into one concrete
``spec.World`` (ABI 8) deterministically; nothing here runs inside a life, and nothing reaches the cells except through
the world's physical fields (odour, flow, touch, vibration, sun and light at each cell's own site).

Senses are bound identically in every family (OPEN_WORLDS.md 4.1): slots 1-4 odour species A-D, 5 flow, 6 touch,
7 vibration, 8 sun; slot 9 is spare. The odour palette is shared too, so a learned meaning transfers: A food,
B richness and prey, C toxin, soil and home, D danger.
"""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from src.life import spec

MODS = {1: dict(kind="odour", arg=0, lam_bg=0.05, lam_s=2.0, K=0.5),
        2: dict(kind="odour", arg=1, lam_bg=0.05, lam_s=2.0, K=0.5),
        3: dict(kind="odour", arg=2, lam_bg=0.05, lam_s=2.0, K=0.5),
        4: dict(kind="odour", arg=3, lam_bg=0.05, lam_s=2.0, K=0.5),
        5: dict(kind="flow", lam_bg=0.05, lam_s=2.0, K=0.25),
        6: dict(kind="touch", lam_bg=0.02, lam_s=4.0, K=0.6),
        7: dict(kind="vibration", lam_bg=0.05, lam_s=2.0, K=3.0),
        8: dict(kind="sun", lam_bg=0.05, lam_s=1.0, K=1.0)}
MOD_BLOCK = spec.mod_block(MODS)
BASE = "catch_speck_l4"
FAMILIES = ("plume", "predator", "home", "prey", "farm")
_SALT = {name: i + 1 for i, name in enumerate(FAMILIES)}
_SALT.update({f"{name}_transfer": 100 + i for i, name in enumerate(FAMILIES)})


class _Draw:
    def __init__(self, seed: int, salt: int):
        self.rng = np.random.default_rng([int(seed) & spec.MASK64, int(salt)])

    def u(self, lo: float, hi: float) -> float:
        return float(self.rng.uniform(lo, hi))

    def i(self, lo: int, hi: int) -> int:  # inclusive
        return int(self.rng.integers(lo, hi + 1))

    def p(self, q: float) -> bool:
        return bool(self.rng.random() < q)

    def angle(self) -> float:
        return float(self.rng.uniform(0.0, 2.0 * math.pi))


class _Builder:
    def __init__(self, d: _Draw, arena: float = 14.0):
        self.d, self.e = d, {}
        self.n = dict(src=0, ag=0, wall=0, shelter=0, fertile=0)
        self.arena = arena
        self.e.update(eco_mode=2, eco_arena=arena, eco_r_body=1.5, eco_kill_hits=3, eco_occlude=1,
                      eco_landmark=0.1, eco_vib_vref=0.2, eco_sun_heading=d.angle(),
                      eco_home_sigma=1.0, eco_plant_sigma=0.8, eco_soil_sigma=1.5,
                      eco_puff_sigma0=d.u(0.3, 0.6), eco_puff_D=d.u(0.005, 0.04), eco_puff_life=d.u(40.0, 100.0),
                      eco_puff_cut=16.0, eco_puff_cap=256)

    # -- geometry helpers
    def free_point(self, r_lo: float, r_hi: float, clear: float = 0.5, tries: int = 64):
        """A point at radius [r_lo, r_hi] from the start, at least ``clear`` outside every wall so far."""
        for _ in range(tries):
            r, th = self.d.u(r_lo, r_hi), self.d.angle()
            x, y = r * math.cos(th), r * math.sin(th)
            if all(not (x0 - clear < x < x1 + clear and y0 - clear < y < y1 + clear)
                   for x0, x1, y0, y1 in self.walls()):
                return x, y
        return x, y

    def walls(self):
        return [tuple(self.e[f"wall{i}_{f}"] for f in spec.WALL_FIELDS) for i in range(self.n["wall"])]

    # -- entities
    def current(self, lo: float, hi: float, p_turn: float = 0.8):
        d = self.d
        self.e.update(eco_cur_speed=d.u(lo, hi), eco_cur_heading=d.angle(),
                      eco_cur_turn=d.u(30.0, 200.0) if d.p(p_turn) else 0.0, eco_cur_turn_max=d.u(0.3, 1.0))

    def wall(self, x0, x1, y0, y1, keep_clear: float = 2.5):
        """A box, refused if it would cover the start (the body begins at the origin)."""
        k = keep_clear
        if self.n["wall"] >= spec.N_WALL or (x0 - k < 0 < x1 + k and y0 - k < 0 < y1 + k):
            return
        i = self.n["wall"]
        self.e.update({f"wall{i}_x0": x0, f"wall{i}_x1": x1, f"wall{i}_y0": y0, f"wall{i}_y1": y1})
        self.n["wall"] += 1

    def random_walls(self, k: int, r_lo: float = 3.0, r_hi: float = 9.0):
        d = self.d
        for _ in range(k):
            r, th = d.u(r_lo, r_hi), d.angle()
            cx, cy = r * math.cos(th), r * math.sin(th)
            long, thick = d.u(2.0, 6.0), d.u(0.3, 0.8)
            if d.p(0.5):
                self.wall(cx - long / 2, cx + long / 2, cy - thick / 2, cy + thick / 2)
            else:
                self.wall(cx - thick / 2, cx + thick / 2, cy - long / 2, cy + long / 2)

    def source(self, x, y, value, blend, cap=None, period=None, puff=None, light=None):
        if self.n["src"] >= spec.N_SRC:
            return
        d, i = self.d, self.n["src"]
        cap = d.i(2, 5) if cap is None else cap
        period = (d.u(60.0, 300.0) if d.p(0.8) else 0.0) if period is None else period
        q = dict(x=x, y=y, value=value, cap=cap, period=period, phase=d.u(0.0, period) if period else 0.0,
                 light=(d.u(0.3, 1.0) if d.p(0.3) else 0.0) if light is None else light, sigma=0.6,
                 puff=d.u(0.2, 0.6) if puff is None else puff)
        q.update({f"b{k}": float(v) for k, v in enumerate(blend)})
        self.e.update({f"src{i}_{f}": v for f, v in q.items()})
        self.n["src"] += 1

    def food(self, r_lo, r_hi, **kw):
        d = self.d
        x, y = self.free_point(r_lo, r_hi)
        rich = d.u(0.0, 0.6)
        self.source(x, y, 250.0 + 1250.0 * rich + d.u(-50.0, 50.0), (1.0, rich, 0.0, 0.0), **kw)

    def toxin(self, r_lo, r_hi, **kw):
        d = self.d
        x, y = self.free_point(r_lo, r_hi)
        self.source(x, y, -d.u(300.0, 1200.0), (d.u(0.6, 1.0), 0.0, d.u(0.5, 1.0), 0.0), **kw)

    def agent(self, kind: str, **q):
        if self.n["ag"] >= spec.N_AG:
            return
        i = self.n["ag"]
        base = dict(type=spec.AGENT_TYPES[kind], sigma=1.0, light=0.0, rx=0.0, ry=0.0)
        base.update(q)
        self.e.update({f"ag{i}_{f}": float(base.get(f, 0.0)) for f in spec.AG_FIELDS})
        self.n["ag"] += 1

    def predator(self, kind: str = "pursuit", fast: tuple = (0.1, 0.35)):
        d = self.d
        x, y = self.free_point(5.0, 11.0)
        if kind == "pursuit":
            self.agent("pursuit", x=x, y=y, v1=d.u(0.03, 0.08), v2=d.u(*fast), r_sense=d.u(2.0, 6.0), p=d.u(0.3, 0.9),
                       r_contact=d.u(0.8, 1.3), value=d.u(800.0, 2500.0), look=d.u(1.0, 2.5), t_state=d.u(20.0, 120.0),
                       t_rest=d.u(40.0, 150.0), b3=1.0, b2=0.3)
        else:
            self.agent("ambush", x=x, y=y, r_sense=0.0, p=d.u(0.3, 0.9), r_contact=d.u(1.0, 1.8),
                       value=d.u(1000.0, 3000.0), look=d.u(1.0, 2.5), t_rest=d.u(30.0, 100.0), b3=d.u(0.2, 0.6),
                       b2=0.2)

    def prey(self, kind: str):
        d = self.d
        x, y = self.free_point(3.0, 10.0)
        rx, ry = self.free_point(3.0, 10.0)
        self.agent(kind, x=x, y=y, v1=d.u(0.03, 0.08), v2=d.u(0.15, 0.4), r_sense=d.u(1.5, 4.0), p=d.u(0.3, 0.9),
                   r_contact=0.0, value=d.u(500.0, 1500.0), look=d.u(1.0, 2.0), t_state=d.u(10.0, 40.0),
                   t_rest=d.u(30.0, 150.0), light=d.u(0.3, 0.8) if d.p(0.4) else 0.0, b1=1.0, b3=0.2, rx=rx, ry=ry)

    def pest(self):
        d = self.d
        x, y = self.free_point(4.0, 10.0)
        self.agent("pest", x=x, y=y, v1=d.u(0.03, 0.06), v2=d.u(0.1, 0.2), r_sense=d.u(3.0, 8.0), r_contact=0.8,
                   look=d.u(1.5, 3.0), b3=0.5, b1=0.3)

    def disk(self, kind: str, x, y, r):
        if self.n[kind] >= spec.N_DISK:
            return
        i = self.n[kind]
        self.e.update({f"{kind}{i}_x": x, f"{kind}{i}_y": y, f"{kind}{i}_r": r})
        self.n[kind] += 1

    def background(self, p_pred=0.3, p_toxin=0.5, p_walls=0.3, cur=(0.02, 0.1)):
        d = self.d
        if self.e.get("eco_cur_speed") is None:
            self.current(*cur)
        if d.p(p_walls):
            self.random_walls(d.i(1, 2))
        if d.p(p_toxin):
            self.toxin(3.0, 10.0)
        if d.p(p_pred):
            self.predator("pursuit", fast=(0.08, 0.2))

    def world(self, T: float = 1024.0) -> spec.World:
        for k, v in self.n.items():
            self.e[f"eco_n_{k}"] = v
        return spec.eco_world(BASE, mod=MOD_BLOCK, eco=spec.eco_block(**self.e), T=T, v_t=0.0, tau_turn=0.0,
                              t_resp=0.0)


def _plume(d: _Draw, transfer: bool) -> spec.World:
    b = _Builder(d)
    b.current(*((0.25, 0.4) if transfer else (0.03, 0.25)))
    if d.p(0.3):
        b.random_walls(d.i(1, 2))
    for _ in range(d.i(3, 6)):
        b.food(3.0, 9.0, puff=d.u(0.3, 0.8))
    for _ in range(d.i(0, 2) + (1 if transfer else 0)):
        b.toxin(3.0, 9.0, puff=d.u(0.3, 0.8))
    if d.p(0.3):
        b.predator("pursuit", fast=(0.08, 0.2))
    return b.world()


def _predator(d: _Draw, transfer: bool) -> spec.World:
    b = _Builder(d)
    b.current(0.02, 0.1)
    for _ in range(d.i(1, 3)):
        r = d.u(1.0, 2.0)
        x, y = b.free_point(r + 1.0, r + 7.0)  # never over the start: shelter is found, not given
        b.disk("shelter", x, y, r)
    for _ in range(d.i(3, 6)):
        b.food(3.0, 10.0)
    if d.p(0.4):
        b.toxin(3.0, 10.0)
    n_pred = d.i(5, 6) if transfer else d.i(1, 4)
    for _ in range(n_pred):
        b.predator("pursuit" if d.p(0.6) else "ambush")
    if d.p(0.3):
        b.random_walls(d.i(1, 2))
    b.e["eco_kill_hits"] = d.i(2, 4)
    return b.world()


def _home(d: _Draw, transfer: bool) -> spec.World:
    b = _Builder(d)
    b.current(0.02, 0.12)
    b.e.update(eco_home_x=0.0, eco_home_y=0.0, eco_home_r=d.u(1.2, 2.0), eco_home_b2=0.6, eco_home_b1=0.4,
               eco_carry_cap=d.i(1, 3), eco_carry_mult=d.u(2.0, 3.0), eco_carry_digest=d.u(60.0, 200.0),
               eco_carry_drag=d.u(0.1, 0.5))
    n_w = d.i(5, 8) if transfer else d.i(2, 6)
    b.random_walls(n_w, 3.0, 8.0)
    for _ in range(d.i(3, 6)):
        b.food(4.0, 12.0, cap=d.i(2, 4))
    if d.p(0.3):
        b.toxin(4.0, 12.0)
    if d.p(0.3):
        b.predator("pursuit", fast=(0.08, 0.2))
    return b.world()


def _prey(d: _Draw, transfer: bool) -> spec.World:
    b = _Builder(d)
    b.current(0.02, 0.1)
    kinds = ("darter", "freezer", "burrower")
    for _ in range(d.i(2, 6)):
        b.prey(kinds[d.i(0, 2)])
    if d.p(0.6 if transfer else 0.4):
        b.random_walls(d.i(1, 4))
    for _ in range(d.i(0, 2)):
        b.food(3.0, 10.0, cap=1)
    if d.p(0.2):
        b.predator("pursuit", fast=(0.08, 0.2))
    return b.world()


def _farm(d: _Draw, transfer: bool) -> spec.World:
    b = _Builder(d)
    b.current(0.02, 0.1)
    for _ in range(d.i(1, 3)):
        r = d.u(1.5, 3.0)
        x, y = b.free_point(r + 1.0, r + 5.0)  # never under the start: soil is found, not given
        b.disk("fertile", x, y, r)
    lo = d.u(60.0, 120.0)
    b.e.update(eco_plant_cap=d.i(8, 16), eco_plant_cost=d.u(20.0, 100.0), eco_ripen_min=lo,
               eco_ripen_max=lo + d.u(0.0, 80.0), eco_ripe_window=d.u(40.0, 150.0), eco_plant_value=d.u(300.0, 900.0),
               eco_plant_light=d.u(0.3, 0.8) if d.p(0.5) else 0.0, eco_plant_b0=0.8, eco_plant_b1=0.6,
               eco_soil_b2=d.u(0.3, 0.6))
    for _ in range(d.i(2, 4) if transfer else d.i(1, 3)):
        b.pest()
    for _ in range(d.i(0, 2)):
        b.food(3.0, 10.0, cap=1, period=0.0)
    if d.p(0.2):
        b.predator("pursuit", fast=(0.08, 0.2))
    return b.world()


_MAKERS = dict(plume=_plume, predator=_predator, home=_home, prey=_prey, farm=_farm)


def realize(family: str, seed: int, T: float | None = None, **overrides) -> spec.World:
    """One concrete ABI 8 world of ``family`` (or ``family_transfer``, a held-out region) for life seed ``seed``."""
    base, transfer = (family[:-len("_transfer")], True) if family.endswith("_transfer") else (family, False)
    if base not in _MAKERS:
        raise KeyError(f"unknown eco family {family!r}; families: {FAMILIES}")
    w = _MAKERS[base](_Draw(seed, _SALT[family]), transfer)
    if T is not None:
        w = replace(w, T=float(T))
    if overrides:
        w = replace(w, **overrides)
    spec.V8.validate_world(w)
    return w
