"""Headroom check per eco world (docs/OPEN_WORLDS.md 7, simplified): evolved founders against controllers.

    .venv/bin/python -m scripts.eco_headroom --out outputs/headroom_20261020

Not a gate (the worlds are never gated on hand-built controllers); a yardstick for how much room each world offers
beyond what the evolved bodies do now, and for which information sources pay. Three parts, each cached in --out:

1. ``evolved``: the founder populations of the open-world pilot (D90_Z_s5, AO_s7; read-only from
   outputs/open_worlds_pilot/inputs). Every genome is screened on lives disjoint from the paired panel, the best 8 per
   lineage (mean F) are run on the paired panel (64 life seeds per family by default) with the kernel, exactly as the
   pilot's evaluator builds the worlds (``LifeEvaluator._task_world``). Their path gives the controllers' speed limit.
2. ``controllers``: controllers that drive the dot directly inside ``reference._Accountant`` (the bitwise Python spec
   of the eco world: the same click resolution, contact radii, agents, puffs, damage, kill and income), on the same
   worlds and life seeds, so every world random stream (puffs, current turns, agent looks) is shared with the evolved
   lives. No cells: the dot is driven by setting its force, capped at the evolved bodies' speed.
3. ``summary``: paired comparisons per family, written to summary.json (README.md is written by hand from it).

Controllers (``CONTROLLERS``), each on every panel world with the same speed cap and the key's click interval;
stochastic ones run ``--reps`` replicates of their own random streams per world seed, averaged within the seed:
- ``still``: never moves or clicks (zero line). ``blind`` / ``blind_slow`` / ``sit_click``: no sensing at all; a
  random walk clicking every 2.2 / 10 units, or sitting still at the start clicking every 5 (tests for income
  without information).
- ``light``: the light-chaser reflex (climb the light seen by the sense cells, tap near the peak, else wander), an
  approximation of what the evolved founders do.
- ``partial``: only senses a body could have at its sense cells (Poisson-noisy receptor events of light, odours A-D,
  flow, touch and vibration at 13 points of a body of radius 3, 3 cells each) plus an efference copy of its own
  motion and its load (drag); surge-and-cast plume following with blend discrimination, prey pursuit, fleeing from
  danger, home return by path integration, planting and harvesting on fertile soil, spatial memory of sources,
  plots, prey and danger spots (``Partial``).
- ``partial_nomem`` / ``partial_noident`` / ``partial_novib`` / ``partial_noflow`` / ``partial_nolight``: ablations
  of ``partial`` that remove one information source each (memory and path integration; odour identity, i.e. only the
  sum of the four species; vibration; flow; light). ``partial_clean``: ``partial`` with noise-free receptor rates.
  All variants share their random streams (common random numbers) so they differ only where the senses differ.
- ``privileged``: reads the true world state (positions, stocks, regrowth times, toxin identity, agent states and
  velocities, plant ripening, refuges, shelters, walls) and plans greedily with a wall-aware path planner.

Controllers report gross income and eco costs only: they pay no body running cost (cells, spikes, strokes,
receptors), only the miss charge of their empty clicks, which is reported separately.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):  # one thread per worker process
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.life import ecology, reference, spec  # noqa: E402

V8 = spec.V8
LI = V8.L
FAMILIES = ecology.FAMILIES
SEED_BASE = 7_000_000  # paired panel: ecology.realize(family, SEED_BASE + i)
SCREEN_BASE = 7_500_000  # screening lives for picking the best founders (disjoint from the panel)
LINEAGES = ("D90_Z_s5", "AO_s7")
POP_DIR = ROOT / "outputs/open_worlds_pilot/inputs"
CONFIG = ROOT / "configs/open_worlds_pilot_U.yaml"
ECO_INCOME = ("eco_food_income", "eco_prey_income", "eco_harvest_income", "eco_deliver_income", "eco_digest_income")
ECO_COST = ("eco_toxin_cost", "eco_damage_cost", "eco_plant_cost")
REPORT = ("income", *ECO_INCOME, *ECO_COST, "eco_killed", "captures", "F", "cost", "misses", "clicks", "path",
          "t_end", "eco_food_eaten", "eco_toxin_eaten", "eco_prey_caught", "eco_planted", "eco_harvested",
          "eco_picked", "eco_delivered", "eco_digested", "eco_hits", "eco_pest_eaten", "eco_spoiled", "eco_alarms",
          "eco_detections", "eco_wall_contacts", "eco_shelter_samples", "eco_home_samples", "eco_loaded_samples",
          "eco_upflow_path", "eco_crossflow_path", "eco_near_food_samples", "samples", "n_end", "n_S_end", "nudges")


# ------------------------------------------------------------------------------------------------ the worlds
_EV = None


def evaluator(out: Path):
    """The pilot's evaluator (configs/open_worlds_pilot_U.yaml): the same world construction as training."""
    global _EV
    if _EV is None:
        from src.common import load_config
        from src.evolve import setup

        cfg = load_config(str(CONFIG), [f"logging.output_dir={out / '_unused'}"])
        _, layout, _, ev = setup(cfg)
        _EV = (layout, ev)
    return _EV


def eco_world(ev, family: str, seed: int, T: float = 1024.0) -> spec.World:
    return ev._task_world(dict(name=family, world=f"eco:{family}", overrides={}, weight=1), T, seed)


def panel_seeds(n: int, base: int = SEED_BASE) -> list[int]:
    return [base + i for i in range(n)]


# ------------------------------------------------------------------------------------------- part 1: evolved
def run_evolved(out: Path, n_seeds: int, n_screen: int, top: int, threads: int) -> dict:
    """Screen every founder genome, then run the best ``top`` per lineage on the paired panel."""
    import torch

    from src.life import build
    from src.search import load_population

    path = out / "evolved.npz"
    if path.exists():
        z = np.load(path, allow_pickle=False)
        meta = json.loads((out / "evolved_meta.json").read_text())
        if meta["n_seeds"] == n_seeds:
            return dict(ledger=z["ledger"], meta=meta)
    layout, ev = evaluator(out)
    pops, names = [], []
    for lin in LINEAGES:
        pop, _info = load_population(POP_DIR / f"{lin}_population.json", layout, 32)
        pops.append(pop)
        names += [f"{lin}#{i}" for i in range(len(pop))]
    allpop = torch.cat(pops)
    gt = ev.table(allpop)
    G = len(gt)

    def batch(seeds_by_family, genomes_idx):
        worlds, seeds = [], []
        for fam, seeds_f in seeds_by_family.items():
            for s in seeds_f:
                worlds.append(eco_world(ev, fam, s))
                seeds.append(s)
        L = len(seeds)
        B = len(genomes_idx)
        t0 = time.time()
        lv = build.run([worlds[j] for _ in range(B) for j in range(L)], [seeds[j] for _ in range(B) for j in range(L)],
                       genomes=gt, genome_of=np.repeat(np.asarray(genomes_idx), L), kind=ev.kind, threads=threads,
                       abi=V8, fast=True)
        print(f"  {B} genomes x {L} lives in {time.time() - t0:.0f}s", flush=True)
        return lv.ledger.reshape(B, L, -1)

    print("screening founders", flush=True)
    scr = batch({f: panel_seeds(n_screen, SCREEN_BASE) for f in FAMILIES}, list(range(G)))
    F = scr[:, :, LI["F"]].mean(axis=1)
    chosen = []
    for k in range(len(LINEAGES)):
        idx = np.arange(32 * k, 32 * (k + 1))
        best = idx[np.argsort(-F[idx], kind="stable")[:top]]
        chosen += [int(i) for i in best]
    print("panel", flush=True)
    led = batch({f: panel_seeds(n_seeds) for f in FAMILIES}, chosen)  # [B, 5 * n_seeds, LEDGER]
    led = led.reshape(len(chosen), len(FAMILIES), n_seeds, -1)
    meta = dict(n_seeds=n_seeds, seed_base=SEED_BASE, screen_seeds=n_screen, screen_base=SCREEN_BASE, top=top,
                chosen=[names[i] for i in chosen], screen_F=[float(F[i]) for i in chosen],
                screen_F_all={names[i]: float(F[i]) for i in range(G)}, families=list(FAMILIES),
                ledger_names=list(V8.LEDGER))
    np.savez_compressed(path, ledger=led)
    (out / "evolved_meta.json").write_text(json.dumps(meta, indent=1))
    return dict(ledger=led, meta=meta)


def speed_limit(evolved: dict) -> dict:
    """Per-life mean speed (path / t_end) of the evolved panel lives; the controllers' cap is its 90th percentile."""
    led = evolved["ledger"]
    v = led[..., LI["path"]] / np.maximum(led[..., LI["t_end"]], 1.0)
    clicks = led[..., LI["clicks"]] / np.maximum(led[..., LI["t_end"]], 1.0)
    q = np.percentile(v, [10, 50, 90, 99])
    return dict(v_mean=float(v.mean()), v_p10=float(q[0]), v_median=float(q[1]), v_p90=float(q[2]),
                v_p99=float(q[3]), v_max=float(v.max()), cap=float(q[2]),
                per_genome_median=[float(x) for x in np.median(v.reshape(v.shape[0], -1), axis=1)],
                clicks_per_unit_mean=float(clicks.mean()), clicks_per_unit_p90=float(np.percentile(clicks, 90)))


# --------------------------------------------------------------------------- part 2: the dot inside the accountant
H = 0.25  # control step; integer times (samples, kill checks) fall on steps exactly
CLICK_DT = 2.2  # the key's fastest re-arm: the hotspot twitch must fall from th_click 0.6 below th_rel 0.25 (tau_z 2.5)
KILLED = spec.STATUS["killed"]


class Sim:
    """One eco life with no cells: the world, ledger and rules of ``reference._Accountant``, the dot driven by setting
    its force once per step (the same force law, wall kinks, drag and click resolution as a body's strokes and key).

    Speed cap: the force is capped at ``vmax * gam0`` with gam0 = 1, so the dot's speed never exceeds ``vmax`` and a
    loaded dot is slower by its drag (gam = gam0 (1 + drag * items)), as a body of fixed stroke strength would be."""

    def __init__(self, w: spec.World, seed: int, vmax: float, click_dt: float = CLICK_DT):
        lat, unit = V8.lattice_tables(w.lattice)
        latd = reference._lattice(lat, unit, V8)
        zero = V8.pack_genomes(np.zeros((1, V8.GENOME_SIZE), np.float32), w.lattice)[0]
        wv, gt, prog, cells = reference._prepare(V8.pack_world(w), latd, zero, None, None, V8)
        self.life = reference._Life(wv, latd, gt, prog, cells, (int(seed), 0, 0, 0), 0, 0, False, out_abi=V8)
        a = self.a = self.life.acct
        a.n_foot = 1  # the dot moves (no cells: n_foot only gates motion and wall kinks)
        a.gam0 = 1.0
        a._eco_set_gam()
        self.w, self.seed, self.T = w, int(seed), float(w.T)
        self.tau = self.life.tau_z
        self.k_h = self.tau * (1.0 - math.exp(-H / self.tau))  # displacement per unit force over one step
        self.vmax, self.click_dt = float(vmax), float(click_dt)
        self.last_click = -math.inf
        self.clicks_wanted = 0
        self.t = 0.0
        self.rho = self.life.rho_c

    def velocity(self) -> tuple[float, float]:
        a = self.a
        fx, fy = a._eff()
        return fx / a.gam, fy / a.gam

    def run(self, ctl) -> np.ndarray:
        a, T = self.a, self.T
        t, c, t_end, gb = 0.0, 1.0, T, 0
        while t < T:
            if t == c:
                if c <= T - 1.0:
                    if a.eco_dead:  # the kernel ends a killed life at the next integer time (guards_upto)
                        t_end, gb = c, KILLED
                        break
                    a.sample(c)
                c += 1.0
            a.world_to(t)
            a.src_left = [S["stock"] for S in a.src]
            a.dot_adv(t)
            self.t = t
            vx, vy, click = ctl.act(self, t)
            gam = a.gam
            fx, fy = vx * H * gam / self.k_h, vy * H * gam / self.k_h
            n, fmax = math.hypot(fx, fy), self.vmax * a.gam0
            if n > fmax:
                fx, fy = fx * fmax / n, fy * fmax / n
            a.Fx, a.Fy = fx, fy
            a._eco_kink()
            if click:
                self.clicks_wanted += 1
                if t - self.last_click >= self.click_dt:
                    before = len(a.items)
                    a._eco_click(t, True)
                    self.last_click = t
                    ctl.clicked(self, t, len(a.items) - before)
            a._end_group(t)
            t += H
        a.close(t_end, gb, V8.LEDGER_SIZE)
        return np.array(a.led[:V8.LEDGER_SIZE], dtype=np.float64)


def click_outcome(a, t: float, X: float, Y: float) -> tuple[str, float]:
    """What a click at (X, Y) at time t would do, without doing it (the resolution order of ``_eco_click``)."""
    r2 = a.life.rho_c * a.life.rho_c
    for g in a.ag:
        if 3 <= g["type"] <= 5 and g["state"] != 3:
            x, y = a._ag_pos(g, t)
            if (X - x) ** 2 + (Y - y) ** 2 <= r2:
                return "prey", g["value"]
    for P in a.plants:
        if P["state"] == 2 and (X - P["x"]) ** 2 + (Y - P["y"]) ** 2 <= r2:
            return "harvest", a.plant_value
    for S in a.src:
        if S["stock"] > 0 and (X - S["x"]) ** 2 + (Y - S["y"]) ** 2 <= r2:
            if S["value"] < 0:
                return "toxin", S["value"]
            if a.carry_cap > 0 and len(a.items) < a.carry_cap:
                return "pick", S["value"]
            return "food", S["value"]
    if a.carry_cap > 0 and a.items:
        hx, hy, hr = a.home[:3]
        if (X - hx) ** 2 + (Y - hy) ** 2 <= hr * hr:
            return "deliver", sum(v for v, _d, _i in a.items) * a.carry_mult
    if a.plant_cap > 0:
        fertile = any((X - fx) ** 2 + (Y - fy) ** 2 <= r * r for fx, fy, r in a.fertile)
        free, near = -1, False
        for i in range(a.plant_cap):
            P = a.plants[i]
            if P["state"] == 0:
                if free < 0:
                    free = i
                continue
            if (X - P["x"]) ** 2 + (Y - P["y"]) ** 2 <= r2:
                near = True
        if fertile and not near and free >= 0:
            return "plant", -a.plant_cost
    return "miss", -a.life.c_miss


# ------------------------------------------------------------------------------------- receptor fields (vectorised)
def _halo(P, x, y, sigma):
    dx, dy = P[:, 0] - x, P[:, 1] - y
    return np.exp(-(dx * dx + dy * dy) / (2.0 * sigma * sigma))


def _seg_hits(S, P, boxes):
    """[m, n]: does the segment from emitter S[i] to point P[j] cross the open box of any wall (slab test)."""
    hit = np.zeros((len(S), len(P)), dtype=bool)
    sx, sy = S[:, 0][:, None], S[:, 1][:, None]
    ex, ey = P[None, :, 0] - sx, P[None, :, 1] - sy
    with np.errstate(divide="ignore", invalid="ignore"):
        for x0, x1, y0, y1 in boxes:
            ax, bx = (x0 - sx) / ex, (x1 - sx) / ex
            lox, hix = np.minimum(ax, bx), np.maximum(ax, bx)
            inx = (x0 < sx) & (sx < x1)
            lox = np.where(ex == 0.0, np.where(inx, -np.inf, np.inf), lox)
            hix = np.where(ex == 0.0, np.where(inx, np.inf, -np.inf), hix)
            ay, by = (y0 - sy) / ey, (y1 - sy) / ey
            loy, hiy = np.minimum(ay, by), np.maximum(ay, by)
            iny = (y0 < sy) & (sy < y1)
            loy = np.where(ey == 0.0, np.where(iny, -np.inf, np.inf), loy)
            hiy = np.where(ey == 0.0, np.where(iny, np.inf, -np.inf), hiy)
            s_in, s_out = np.maximum(lox, loy), np.minimum(hix, hiy)
            hit |= (s_in < s_out) & (s_out > 0.0) & (s_in < 1.0)
    return hit


def odour(a, t: float, P: np.ndarray) -> np.ndarray:
    """[n, 4] odour concentrations C_k at world points P (``_Accountant._eco_conc``, summed in another order)."""
    C = np.zeros((len(P), spec.N_SPEC))
    if a.puffs:
        ax, ay = a._cur_A(t)
        key = (len(a.puffs), a.puffs[0][0], a.puffs[-1][0])
        cache = getattr(a, "_hr_puffs", None)
        if cache is None or cache[0] != key:
            cache = (key, np.array([(pt, ox, oy, *am) for pt, ox, oy, am in a.puffs]))
            a._hr_puffs = cache
        arr = cache[1]
        age = t - arr[:, 0]
        s02 = a.puff_sig0 * a.puff_sig0
        s2 = s02 + 2.0 * a.puff_D * age
        dx = P[:, 0][:, None] - (arr[:, 1] + ax)[None]
        dy = P[:, 1][:, None] - (arr[:, 2] + ay)[None]
        d2 = dx * dx + dy * dy
        wgt = (s02 / s2)[None] * np.exp(-d2 / (2.0 * s2)[None])
        wgt = np.where((d2 > a.puff_cut * s2[None]) | (age > a.puff_life)[None], 0.0, wgt)
        C += wgt @ arr[:, 3:3 + spec.N_SPEC]
    for g in a.ag:
        if g["vis"] and any(g["b"]):
            x, y = a._ag_pos(g, t)
            C += _halo(P, x, y, g["sigma"])[:, None] * np.asarray(g["b"])[None]
    hx, hy, hr, hs, hb = a.home
    if hr > 0.0 and any(hb):
        C += _halo(P, hx, hy, hs)[:, None] * np.asarray(hb)[None]
    if any(a.soil_b):
        for fx, fy, _r in a.fertile:
            C += _halo(P, fx, fy, a.soil_sig)[:, None] * np.asarray(a.soil_b)[None]
    if any(a.plant_b):
        for Pl in a.plants:
            if Pl["vis"]:
                C += _halo(P, Pl["x"], Pl["y"], a.plant_sig)[:, None] * np.asarray(a.plant_b)[None]
    return C


def light(a, t: float, P: np.ndarray, centre=None) -> np.ndarray:
    """[n] light receptor rates at P (``_Accountant._eco_light``), walls occluding."""
    L = a.life
    em = []  # (x, y, strength, sigma)
    for i, S in enumerate(a.src):
        if S["light"] != 0.0:
            em.append((S["x"], S["y"], S["light"] * a._eco_amp(i, a.src_left[i]), S["sigma"]))
    if a.plant_light != 0.0:
        for Pl in a.plants:
            if Pl["vis"]:
                em.append((Pl["x"], Pl["y"], a.plant_light, a.plant_sig))
    for g in a.ag:
        if g["vis"] and g["light"] != 0.0:
            x, y = a._ag_pos(g, t)
            em.append((x, y, g["light"], g["sigma"]))
    rate = np.full(len(P), L.lam_bg)
    if not em:
        return rate
    E = np.asarray(em)
    if centre is not None:  # emitters too far to matter anywhere on the body
        far = np.hypot(E[:, 0] - centre[0], E[:, 1] - centre[1]) > 3.5 + 7.0 * E[:, 3]
        E = E[~far]
        if not len(E):
            return rate
    dx = P[:, 0][None] - E[:, 0][:, None]
    dy = P[:, 1][None] - E[:, 1][:, None]
    contrib = E[:, 2][:, None] * np.exp(-(dx * dx + dy * dy) / (2.0 * E[:, 3] ** 2)[:, None])
    if a.occlude and a.walls:
        contrib = np.where(_seg_hits(E[:, :2], P, a.walls), 0.0, contrib)
    return rate + L.lam_s * contrib.sum(axis=0)


def vibration(a, t: float, P: np.ndarray, K: float) -> np.ndarray:
    V = np.zeros(len(P))
    for g in a.ag:
        if g["vis"] and g["speed"] != 0.0 and t < g["t_stop"]:
            x, y = a._ag_pos(g, t)
            V += (g["speed"] / a.vib_vref) * _halo(P, x, y, K)
    return V


def touch(a, t: float, P: np.ndarray, K: float) -> np.ndarray:
    hit = np.zeros(len(P), dtype=bool)
    for x0, x1, y0, y1 in a.walls:
        dx = np.where(P[:, 0] < x0, x0 - P[:, 0], np.where(P[:, 0] > x1, P[:, 0] - x1, 0.0))
        dy = np.where(P[:, 1] < y0, y0 - P[:, 1], np.where(P[:, 1] > y1, P[:, 1] - y1, 0.0))
        hit |= dx * dx + dy * dy <= K * K
    for g in a.ag:
        if g["vis"]:
            x, y = a._ag_pos(g, t)
            hit |= (P[:, 0] - x) ** 2 + (P[:, 1] - y) ** 2 <= K * K
    return hit


# the body's sense points: the centre, a ring at 1.5 and a ring at 3 (the founders' sense cells reach radius 3-4.4,
# mean 2.2; 30-42 sense cells, so each point stands for 3 cells); flow is read on the outer ring's faces
_ANG = np.arange(6) * (np.pi / 3.0)
SENSE_OFF = np.vstack([[0.0, 0.0], np.c_[1.5 * np.cos(_ANG), 1.5 * np.sin(_ANG)],
                       np.c_[3.0 * np.cos(_ANG + np.pi / 6), 3.0 * np.sin(_ANG + np.pi / 6)]])
FACE_N = np.c_[np.cos(_ANG + np.pi / 6), np.sin(_ANG + np.pi / 6)]
CELLS_PER_POINT = 3
SUM_X2 = float((SENSE_OFF[:, 0] ** 2).sum())
MOD = ecology.MODS  # slot -> rate law (bg, s, K)


def rate_law(C, m):
    q = MOD[m]
    return q["lam_bg"] + q["lam_s"] * (C / (C + q["K"]))


def inv_law(r, m):
    """Concentration from a (noisy) receptor rate under slot m's saturating law, clipped to [0, 20]."""
    q = MOD[m]
    x = np.clip((r - q["lam_bg"]) / q["lam_s"], 0.0, 0.952)
    return np.minimum(q["K"] * x / (1.0 - x), 20.0)


class Senses:
    """What a body's sense cells report: Poisson receptor events at the 13 sense points (3 cells each), smoothed with
    a 2-unit trace; flow on the six outer faces (2-unit trace). ``noise=False`` reads the expected rates instead.
    ``channels`` limits what is computed (a controller that ignores a sense need not pay for it)."""

    ALL = ("od", "li", "vb", "tc", "fl")

    def __init__(self, rng, noise=True, tau=2.0, tau_flow=2.0, ident=True, channels=ALL):
        self.rng, self.noise, self.ident, self.channels = rng, noise, ident, tuple(channels)
        seed = int(rng.integers(1 << 62))
        self.rngs = {k: np.random.default_rng([seed, j]) for j, k in enumerate(self.ALL)}
        self.a1, self.a2 = H / tau, H / tau_flow
        self.state = None

    def read(self, sim, t):
        a = sim.a
        X, Y = a.X, a.Y
        P = SENSE_OFF + np.array([X, Y])
        r = {}
        ch = self.channels
        if "od" in ch:
            C = odour(a, t, P)
            if self.ident:
                r["od"] = np.stack([rate_law(C[:, k], k + 1) for k in range(4)], axis=1)
            else:  # one receptor type that responds to the sum of the species
                r["od"] = rate_law(C.sum(axis=1), 1)[:, None]
        if "li" in ch:
            r["li"] = light(a, t, P, centre=(X, Y))
        if "vb" in ch:
            V = vibration(a, t, P, MOD[7]["K"]) if a.ag else np.zeros(len(P))
            r["vb"] = MOD[7]["lam_bg"] + MOD[7]["lam_s"] * (V / (V + 1.0))
        if "tc" in ch:
            r["tc"] = np.where(touch(a, t, P, MOD[6]["K"]), MOD[6]["lam_bg"] + MOD[6]["lam_s"], MOD[6]["lam_bg"])
        if "fl" in ch:
            vx, vy = sim.velocity()
            ux, uy = a.cur_ux - vx, a.cur_uy - vy
            pf = -(ux * FACE_N[:, 0] + uy * FACE_N[:, 1]) / MOD[5]["K"]
            r["fl"] = MOD[5]["lam_bg"] + MOD[5]["lam_s"] * np.clip(pf, 0.0, 1.0)
        if self.noise:  # one noise stream per channel, so removing a sense leaves the others' draws unchanged
            n = CELLS_PER_POINT * H
            out = {k: self.rngs[k].poisson(v * n) / n for k, v in r.items()}
        else:
            out = r
        if self.state is None:
            self.state = {k: np.full(v.shape, 0.05) for k, v in out.items()}
            if "tc" in self.state:
                self.state["tc"][:] = MOD[6]["lam_bg"]
        for k, v in out.items():
            al = self.a2 if k == "fl" else self.a1
            self.state[k] += (v - self.state[k]) * al
        return self.state

    @staticmethod
    def flow_estimate(fl):
        """U_rel from the six face rates: faces facing upstream fire; least squares on the unsaturated ones."""
        q = MOD[5]
        y = np.clip((fl - q["lam_bg"]) / q["lam_s"], 0.0, 1.0)
        on = y > 0.08
        if on.sum() < 2:
            if on.sum() == 1:
                k = int(np.argmax(y))
                return -FACE_N[k] * q["K"] * y[k]
            return np.zeros(2)
        A = FACE_N[on]
        b = -q["K"] * y[on]
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        return sol


DET = 1.0  # pooled receptor-rate excess (summed over the 13 sense points) that counts as contact: ~3 SD of noise


def _peak(X):
    """The sense point at the body's centre (the only one within the capture radius) is strongly stimulated and no
    inner-ring point is clearly stronger."""
    return X[0] >= 0.45 and X[0] >= X[1:7].max() - 0.15


def unit(v):
    n = math.hypot(v[0], v[1])
    return (v[0] / n, v[1] / n) if n > 1e-12 else (0.0, 0.0)


def grad(Cp):
    """Spatial gradient over the sense points of a field sampled at SENSE_OFF (least-squares plane)."""
    c = Cp - Cp.mean()
    return np.array([(c * SENSE_OFF[:, 0]).sum() / SUM_X2, (c * SENSE_OFF[:, 1]).sum() / SUM_X2])


# --------------------------------------------------------------------------------------------- simple controllers
class Still:
    name = "still"

    def act(self, sim, t):
        return 0.0, 0.0, False

    def clicked(self, sim, t, d_load):
        pass


class Blind:
    """A correlated random walk at the speed cap that clicks every ``every`` units, with no sensing at all."""

    def __init__(self, sim, every=CLICK_DT, move=True, name="blind", rep=0):
        self.rng = np.random.default_rng([sim.seed & spec.MASK64, 0xB11D, int(every * 100), int(move), rep])
        self.h = self.rng.uniform(0, 2 * np.pi)
        self.every, self.move, self.name = every, move, name
        self.next = 0.0

    def act(self, sim, t):
        self.h += self.rng.normal(0.0, 0.35 * math.sqrt(H))
        click = t >= self.next
        if click:
            self.next = t + self.every
        v = sim.vmax if self.move else 0.0
        return v * math.cos(self.h), v * math.sin(self.h), click

    def clicked(self, sim, t, d_load):
        pass


class LightChaser:
    """The founders' reflex, approximately: climb the light the sense cells see, tap at the peak, else wander."""

    name = "light"

    def __init__(self, sim, noise=True, rep=0):
        self.rng = np.random.default_rng([sim.seed & spec.MASK64, 0x11647, rep])
        self.sen = Senses(self.rng, noise=noise, channels=("li",))
        self.h = self.rng.uniform(0, 2 * np.pi)

    def act(self, sim, t):
        s = self.sen.read(sim, t)
        ex = np.maximum(s["li"] - MOD[1]["lam_bg"], 0.0)  # light uses the world's lam_bg 0.05, lam_s 2
        if ex.max() > 0.12:
            w = ex / ex.sum()
            cx, cy = (w[:, None] * SENSE_OFF).sum(axis=0)
            peak = ex[0] > 0.2 and ex[0] >= 0.8 * ex[1:7].max()
            d = math.hypot(cx, cy)
            v = sim.vmax * min(1.0, d / 1.0)
            ux, uy = unit((cx, cy))
            self.h = math.atan2(uy, ux) if d > 0.3 else self.h
            return v * ux, v * uy, peak
        self.h += self.rng.normal(0.0, 0.35 * math.sqrt(H))
        return sim.vmax * math.cos(self.h), sim.vmax * math.sin(self.h), False

    def clicked(self, sim, t, d_load):
        pass


# ------------------------------------------------------------------------------------- partial-information forager
class Partial:
    """Only what a body's sense cells and its own motion could tell it (``Senses``; its load through drag; the
    outcome of a click is never sensed, except a change of load). Behaviours in priority order:

    1. flee: odour D dominant over B (ident), or a strong and rising vibration (a mover speeding up or closing in)
       without a prey odour (vib), away from its gradient for 6 units; danger spots are remembered and avoided (mem);
       a steady vibration is approached when this life's movers have smelled of prey more often than of danger
       (vib + mem + ident); a danger that does not vibrate (an ambusher) is remembered and steered around (mem);
    2. carry home when loaded: path integration back to the start (mem), then the home blend B+C (ident), tap there;
    3. tap at a peak: food odour A (or the summed odour without ident; light when lit), vetoed when the blend is
       toxin-like (C with A, ident); a prey peak (B without A, ident); leave a site after 4 taps, or when a tap stops
       adding load in a carrying world; its plume is not followed back for 25 units (mem);
    4. chase prey up the B gradient; if a strong prey odour vanishes (a freezer goes quiet), tap where it was (mem);
    5. surge: upstream (flow) plus up the A gradient while food odour is fresh; light gradient when lit;
    6. soil (C alone, ident): climb to the soil peak, sow a 7-spot plot spaced 1.1 apart, come back after 60 units and
       harvest the spots whose ripe odour (A) is there, re-sow; without memory sow where the soil is and harvest any
       ripe odour peak;
    7. cast crosswind (growing sweeps) for 30 units after the last contact; then search: a correlated random walk,
       kept within 11 units of the start and sent to old sites by path integration (mem).
    """

    def __init__(self, sim, mem=True, ident=True, vib=True, flow=True, light=True, noise=True, name="partial", rep=0):
        # the same streams in every variant (common random numbers): behaviour, path-integration noise, receptors
        self.rng = np.random.default_rng([sim.seed & spec.MASK64, 0x9A27, rep])
        self.rng_pi = np.random.default_rng([sim.seed & spec.MASK64, 0x9A28, rep])
        self.mem, self.ident, self.vib, self.flow, self.light = mem, ident, vib, flow, light
        ch = ["od", "tc"] + (["li"] if light else []) + (["vb"] if vib else []) + (["fl"] if flow else [])
        self.sen = Senses(np.random.default_rng([sim.seed & spec.MASK64, 0x9A29, rep]), noise=noise, ident=ident,
                          channels=ch)
        self.name = name
        self.pi = np.zeros(2)
        self.pi_gain = 1.0 + 0.03 * self.rng_pi.standard_normal()
        self.vib_slow, self.prey_prior, self.prey_on, self.danger_on = 0.0, 0, False, False
        self.prev = (sim.a.X, sim.a.Y)
        self.h = self.rng.uniform(0, 2 * np.pi)
        self.U = np.zeros(2)
        self.t_contact, self.up = -math.inf, None
        self.visited = []  # [(pos, t)]
        self.bad = []  # [(pos, t, r)]
        self.site, self.site_clicks, self.site_noload = None, 0, 0
        self.leave_until, self.leave_dir = -math.inf, (1.0, 0.0)
        self.flee_until, self.flee_dir = -math.inf, (1.0, 0.0)
        self.carry_world, self.load = False, 0
        self.soil, self.plots = None, []  # plots: [pos, t_last, n]
        self.plot_i = 0
        self.prey_mem, self.prey_strong_t = None, -math.inf
        self.cast_side, self.cast_next, self.cast_T = 1.0, -math.inf, 2.0
        self.wall_until, self.wall_dir = -math.inf, (1.0, 0.0)
        self.home_tries = 0
        self.last_soil_click = -math.inf
        self.pending = None
        self.bug, self.bug_dir = None, np.array([1.0, 0.0])
        self.T = sim.T

    # ---------------------------------------------------------------------------------------------- helpers
    def _pi_update(self, a):
        dx, dy = a.X - self.prev[0], a.Y - self.prev[1]
        self.prev = (a.X, a.Y)
        if self.mem and (dx or dy):
            th = 0.03 * self.rng_pi.standard_normal()
            g = self.pi_gain * (1.0 + 0.05 * self.rng_pi.standard_normal())
            c, s_ = math.cos(th), math.sin(th)
            self.pi += g * np.array([c * dx - s_ * dy, s_ * dx + c * dy])

    def _toward(self, vec, v):
        ux, uy = unit(vec)
        return v * ux, v * uy

    def _avoid(self, vx, vy):
        """Steer around remembered danger spots (mem)."""
        if not self.mem or not self.bad:
            return vx, vy
        for pos, _t, r in self.bad:
            off = self.pi - pos
            d = float(np.hypot(*off))
            if d < r + 1.0:
                n = off / max(d, 1e-6)
                vdotn = vx * n[0] + vy * n[1]
                if vdotn < 0:
                    vx, vy = vx - vdotn * n[0], vy - vdotn * n[1]
                vx, vy = vx + 0.3 * n[0] * (r + 1.0 - d), vy + 0.3 * n[1] * (r + 1.0 - d)
        return vx, vy

    def _walk(self, sim, t, s, bias=None):
        """Correlated random walk; turn away from touched walls; ``bias``: a direction to drift toward."""
        self.h += self.rng.normal(0.0, 0.35 * math.sqrt(H))
        if bias is not None:
            bh = math.atan2(bias[1], bias[0])
            dh = (bh - self.h + math.pi) % (2 * math.pi) - math.pi
            self.h += 0.15 * dh
        v = (sim.vmax * math.cos(self.h), sim.vmax * math.sin(self.h))
        return self._wall(sim, t, s, v)

    def _wall(self, sim, t, s, v):
        """Touch on the side the body is moving toward (outer ring): slide along the wall for a while."""
        if t < self.wall_until:
            return self.wall_dir[0] * sim.vmax, self.wall_dir[1] * sim.vmax
        tc = s["tc"] > MOD[6]["lam_bg"] + 1.0
        if tc[7:].any():
            n = SENSE_OFF[7:][tc[7:]].sum(axis=0)
            if n[0] * v[0] + n[1] * v[1] > 0 and math.hypot(*sim.velocity()) < 0.3 * sim.vmax:
                side = 1.0 if self.rng.random() < 0.5 else -1.0
                d = unit((-n[1] * side, n[0] * side))
                self.wall_dir, self.wall_until = d, t + 5.0
                self.h = math.atan2(d[1], d[0])
                return d[0] * sim.vmax, d[1] * sim.vmax
        return v

    def _goto(self, sim, t, s, off):
        """Move toward a goal offset (path integration) around walls, Bug-style: when a touched wall blocks the
        goal side, follow it on one side until the goal side is free and the body is closer than where it hit."""
        vmax = sim.vmax
        d = float(np.hypot(*off))
        g = np.array(unit(off))
        tc = s["tc"][7:] > MOD[6]["lam_bg"] + 1.0
        n = SENSE_OFF[7:][tc].sum(axis=0) if tc.any() else np.zeros(2)
        nh = np.array(unit(n))
        goal_side = tc.any() and float(nh @ g) > 0.3
        if self.bug is None and goal_side and math.hypot(*sim.velocity()) < 0.5 * vmax:
            t1, t2 = np.array([-nh[1], nh[0]]), np.array([nh[1], -nh[0]])
            self.bug = dict(d_hit=d, side=1.0 if t1 @ g >= t2 @ g else -1.0, t0=t, flips=0)
        if self.bug is not None:
            b = self.bug
            if (not tc.any() and d < b["d_hit"]) or (not goal_side and d < b["d_hit"] - 0.3) or t - b["t0"] > 90:
                self.bug = None
            else:
                if t - b["t0"] > 45 and b["flips"] == 0:
                    b["side"], b["flips"] = -b["side"], 1
                if tc.any():
                    tang = np.array([-nh[1], nh[0]]) * b["side"]
                    self.bug_dir = tang + 0.15 * nh
                return self._toward(self.bug_dir, vmax)
        return self._toward(off, min(vmax, d / H))

    def _near_visited(self, t, r=2.5, window=25.0):
        return self.mem and any(t - tv < window and np.hypot(*(self.pi - pv)) < r for pv, tv in self.visited)

    # ------------------------------------------------------------------------------------------------ act
    def act(self, sim, t):
        a = sim.a
        self.pending = None
        s = self.sen.read(sim, t)
        self._pi_update(a)
        self.load = len(a.items)  # felt as drag
        vmax = sim.vmax
        vb = sim.velocity()
        if self.flow:
            Ur = Senses.flow_estimate(s["fl"])
            self.U += (Ur + np.array(vb) - self.U) * (H / 10.0)  # the current turns every 30-200 units
        up = unit((-self.U[0], -self.U[1])) if self.flow and np.hypot(*self.U) > 0.015 else None
        X = s["od"] - 0.05  # receptor-rate excess over background at each sense point (unclipped)
        E = X.sum(axis=0)  # pooled over the body
        tot = X.sum(axis=1)
        top = np.argsort(-tot)[:4]
        Cp = np.array([float(inv_law(s["od"][top, k].mean(), k + 1)) for k in range(X.shape[1])])
        if self.ident:
            XA, XB, XC, XD = X[:, 0], X[:, 1], X[:, 2], X[:, 3]
            cA, cB, cC, cD = Cp
            on = E > DET
            toxic = on[0] and cC > 0.3 * cA + 0.02 and cD < 0.5 * cC + 0.05
            food = on[0] and not toxic and cD < 0.6 * cA
            prey = on[1] and cA < 0.5 * cB and cD < 0.5 * cB and cC < 0.3 * cB
            danger = on[3] and cB < 0.4 * cD and cA < 0.5 * cD
            homeo = on[2] and cB > 0.25 * cC and cA < 0.3 * cC and cD < 0.3 * cC
            soil = on[2] and cA < 0.25 * cC and cB < 0.2 * cC and cD < 0.25 * cC
        else:  # one receptor for the summed odour: every odour is "food"
            XA = X[:, 0]
            XB = XC = XD = np.zeros(13)
            food, toxic, prey, danger, homeo, soil = E[0] > DET, False, False, False, False, False
        Xl = (s["li"] - 0.05) if self.light else np.zeros(13)
        gD = grad(XD)
        if self.mem and self.ident:  # within-life prior: have moving things smelled of prey or of danger?
            if prey and not self.prey_on:
                self.prey_prior += 1
            if danger and not self.danger_on:
                self.prey_prior -= 1
        self.prey_on, self.danger_on = prey, danger
        vib_lure, Xv, pv = False, None, None
        if self.vib:
            Xv = s["vb"] - 0.05
            pv = float(Xv.sum())
            rising = pv > 2.0 and pv > 1.5 * self.vib_slow + 0.5  # a mover speeding up or closing in
            self.vib_slow += (pv - self.vib_slow) * (H / 6.0)
            if rising and not (self.ident and (prey or E[1] > DET)):
                danger = True
                gD = grad(Xv)
            vib_lure = (not rising and pv > 1.0 and self.prey_prior > 0 and not danger)
        # 1. flee
        if danger:
            away = -gD if np.hypot(*gD) > 0.01 else -SENSE_OFF[int(np.argmax(XD if XD.any() else tot))]
            if np.hypot(*away) < 1e-9:
                away = np.array([math.cos(self.h), math.sin(self.h)])
            self.flee_dir, self.flee_until = unit(away), t + 6.0
            # close to a danger source that does not move (strong D, little vibration: an ambusher): remember it
            if self.mem and self.ident and pv is not None and XD.max() > 0.6 and pv < 1.0:
                spot = self.pi + SENSE_OFF[int(np.argmax(XD))] * 0.5
                if not any(np.hypot(*(spot - p_)) < 1.0 for p_, _t, _r in self.bad):
                    self.bad.append((spot, t, 2.5))
        if t < self.flee_until:
            vx, vy = self._wall(sim, t, s, (self.flee_dir[0] * vmax, self.flee_dir[1] * vmax))
            return vx, vy, False
        # 3. a peak under the body: tap
        pk_food = food and _peak(XA)
        pk_light = self.light and _peak(Xl) and not toxic
        pk_prey = prey and _peak(XB)
        if (pk_food or pk_light or pk_prey) and not (t < self.leave_until):
            if pk_prey:
                self.prey_mem, self.prey_strong_t = self.pi.copy(), t
            here = self.pi.copy() if self.mem else np.array([a.X, a.Y])  # site bookkeeping only
            if self.site is None or np.hypot(*(here - self.site)) > 1.2:
                self.site, self.site_clicks, self.site_noload = here, 0, 0
            if self.site_clicks >= 4 or (self.carry_world and self.site_noload >= 1):
                self._leave(t, up)
            else:
                f = XB if (pk_prey and not pk_food) else (Xl if (pk_light and not pk_food) else XA)
                g = grad(f)
                sp = 0.6 * vmax if pk_prey else 0.25 * vmax
                vx, vy = self._toward(g, sp) if np.hypot(*g) > 0.05 else (0.0, 0.0)
                return vx, vy, True
        # 2. carry home
        if self.load > 0 and self.carry_world and (self.mem or self.ident):
            return self._home(sim, t, s, XB + XC, homeo)
        if toxic and self.mem and XA.max() > 0.8:  # a toxin source nearby: remember, keep away
            spot = self.pi + SENSE_OFF[int(np.argmax(XA))]
            if not any(np.hypot(*(spot - p_)) < 1.0 for p_, _t, _r in self.bad):
                self.bad.append((spot, t, 1.2))
        # 4. prey
        if prey and not (t < self.leave_until):
            g = grad(XB)
            d = g if np.hypot(*g) > 0.03 else SENSE_OFF[int(np.argmax(XB))]
            if XB.max() > 0.8:
                self.prey_mem, self.prey_strong_t = self.pi + SENSE_OFF[int(np.argmax(XB))] * 0.5, t
            vx, vy = self._toward(d, vmax)
            return (*self._avoid(vx, vy), False)
        if vib_lure and not (t < self.leave_until):  # something moving nearby, and movers have been prey here
            g = grad(Xv)
            if np.hypot(*g) > 0.03:
                vx, vy = self._toward(g, vmax)
                return (*self._wall(sim, t, s, self._avoid(vx, vy)), False)
        if self.mem and self.ident and self.prey_mem is not None and t - self.prey_strong_t < 20.0:
            off = self.prey_mem - self.pi  # a strong prey odour went quiet (a freezer): tap where it was
            if np.hypot(*off) < 0.4:
                if t - self.prey_strong_t > 10.0:
                    self.prey_mem = None
                return 0.0, 0.0, True
            vx, vy = self._toward(off, min(vmax, np.hypot(*off) / H))
            return vx, vy, False
        # 5. surge on food odour or light
        lit = self.light and Xl.sum() > DET and not toxic
        if (food or lit) and not (t < self.leave_until) and not (self._near_visited(t) and XA.max() < 1.0):
            self.t_contact = t
            self.cast_T, self.cast_next = 2.0, t + 2.0
            if lit and (not food or Xl.max() > XA.max()):
                g = grad(Xl)
                d = g if np.hypot(*g) > 0.03 else SENSE_OFF[int(np.argmax(Xl))]
            else:
                g = grad(XA)
                d = np.array(unit(g if np.hypot(*g) > 0.03 else SENSE_OFF[int(np.argmax(XA))]))
                if up is not None:
                    d = d + 0.8 * np.array(up)
                    self.up = up
                else:
                    self.up = unit(d)
            vx, vy = self._toward(d, vmax)
            vx, vy = self._wall(sim, t, s, self._avoid(vx, vy))
            return vx, vy, False
        # 6. soil and plots
        if soil or (self.mem and self.soil is not None):
            r = self._farm(sim, t, s, XA, XC, soil)
            if r is not None:
                return r
        # 7. leave / cast / search
        if t < self.leave_until:
            vx, vy = self._wall(sim, t, s, (self.leave_dir[0] * vmax, self.leave_dir[1] * vmax))
            return vx, vy, False
        if t - self.t_contact < 30.0 and self.up is not None:
            if t >= self.cast_next:
                self.cast_side = -self.cast_side
                self.cast_T *= 1.4
                self.cast_next = t + self.cast_T
            u_ = self.up if up is None else up
            cw = (-u_[1] * self.cast_side, u_[0] * self.cast_side)
            d = (cw[0] + 0.25 * u_[0], cw[1] + 0.25 * u_[1])
            vx, vy = self._toward(d, vmax)
            return (*self._wall(sim, t, s, self._avoid(vx, vy)), False)
        bias = None
        if self.mem:
            if np.hypot(*self.pi) > 11.0:
                bias = -self.pi
            else:
                old = [(tv, k) for k, (pv, tv) in enumerate(self.visited) if t - tv > 120.0]
                if old:
                    tv, k = min(old)
                    off = self.visited[k][0] - self.pi
                    if np.hypot(*off) < 1.5:  # nothing here now: look again later
                        self.visited[k] = (self.visited[k][0], t)
                    bias = off
        vx, vy = self._walk(sim, t, s, bias)
        return (*self._avoid(vx, vy), False)

    def _leave(self, t, up):
        if self.mem and self.site is not None:
            self.visited.append((self.site.copy(), t))
        self.site, self.site_clicks, self.site_noload = None, 0, 0
        if up is not None:
            side = 1.0 if self.rng.random() < 0.5 else -1.0
            self.leave_dir = (-up[1] * side, up[0] * side)
        else:
            th = self.rng.uniform(0, 2 * np.pi)
            self.leave_dir = (math.cos(th), math.sin(th))
        self.leave_until = t + 5.0
        self.t_contact = -math.inf

    def _home(self, sim, t, s, Xh, homeo):
        vmax = sim.vmax
        if homeo:  # the home blend B + C (ident)
            if (Xh[0] > 0.8 and Xh[0] >= Xh[1:7].max() - 0.2) or (self.mem and np.hypot(*self.pi) < 0.6):
                return 0.0, 0.0, True
            g = grad(Xh)
            vx, vy = self._toward(g if np.hypot(*g) > 0.03 else SENSE_OFF[int(np.argmax(Xh))], vmax)
            return (*self._wall(sim, t, s, (vx, vy)), False)
        if self.mem:
            off = -self.pi
            d = float(np.hypot(*off))
            if d < 0.6:
                self.home_tries += 1
                if self.home_tries > 6:  # path integration drifted: search around the believed home
                    self.pi += self.rng.normal(0.0, 0.8, 2)
                    self.home_tries = 0
                return 0.0, 0.0, True
            vx, vy = self._goto(sim, t, s, off)
            return vx, vy, False
        vx, vy = self._walk(sim, t, s)
        return vx, vy, False

    def _farm(self, sim, t, s, XA, XC, soil):
        vmax = sim.vmax
        g = grad(XC)
        if not self.mem:  # reactive: stay on the soil, sow where it is, harvest ripe odour peaks (step 3)
            if not soil:
                return None
            if XC[0] < 0.5 * XC.max():
                vx, vy = self._toward(g, vmax)
                return vx, vy, False
            click = t - self.last_soil_click > 6.0
            if click:
                self.last_soil_click = t
            vx, vy = self._walk(sim, t, s, bias=g if np.hypot(*g) > 0.03 else None)
            return 0.5 * vx, 0.5 * vy, click
        if self.soil is None:
            if XC[0] > 0.3 and np.hypot(*g) < 0.08:
                self.soil = self.pi.copy()
                spots = [self.soil.copy()] + [self.soil + 1.1 * np.array([math.cos(k * math.pi / 3),
                                                                        math.sin(k * math.pi / 3)])
                                              for k in range(6)]
                self.plots = [[q, -math.inf, 0] for q in spots]
            else:
                vx, vy = self._toward(g if np.hypot(*g) > 0.02 else SENSE_OFF[int(np.argmax(XC))], 0.7 * vmax)
                return (*self._wall(sim, t, s, (vx, vy)), False)
        if t > self.T - 70.0 and not any(t - q[1] >= 55.0 for q in self.plots):
            return None
        # the next plot due: never sown, or sown >= 60 units ago (ripening takes 60-200)
        due = [k for k, q in enumerate(self.plots) if q[2] == 0 or t - q[1] >= 60.0]
        if not due:
            off = self.soil - self.pi
            if np.hypot(*off) > 1.5:
                vx, vy = self._goto(sim, t, s, off)
                return vx, vy, False
            return 0.0, 0.0, False
        k = min(due, key=lambda j: np.hypot(*(self.plots[j][0] - self.pi)))
        off = self.plots[k][0] - self.pi
        d = float(np.hypot(*off))
        if d > 0.15:
            vx, vy = self._goto(sim, t, s, off)
            return vx, vy, False
        q = self.plots[k]
        ripe = bool(XA[0] > 0.9)
        if q[2] == 0 or ripe or t - q[1] >= 200.0:
            # sow (never sown / spoiled by now) or harvest (ripe odour here); after a harvest the next tap re-sows
            self.pending = (k, ripe)
            return 0.0, 0.0, True
        q[1] = t - 40.0  # not ripe yet: look again in 20 units
        return 0.0, 0.0, False

    def clicked(self, sim, t, d_load):
        if self.pending is not None:  # a plot tap that happened (the key may refuse a request)
            k, ripe = self.pending
            q = self.plots[k]
            q[1], q[2] = t, (0 if ripe else q[2] + 1)
            self.pending = None
            return
        if d_load > 0:
            self.carry_world = True
        if self.site is not None:
            self.site_clicks += 1
            if self.carry_world and d_load <= 0:
                self.site_noload += 1
        if d_load < 0:
            self.home_tries = 0


ABLATIONS = dict(partial={}, partial_nomem=dict(mem=False), partial_noident=dict(ident=False),
                 partial_novib=dict(vib=False), partial_noflow=dict(flow=False), partial_nolight=dict(light=False),
                 partial_clean=dict(noise=False))


DETERMINISTIC = ("still", "sit_click", "privileged")  # no random stream: one replicate is enough


def make_controller(name: str, sim: Sim, rep: int = 0):
    if name == "still":
        return Still()
    if name == "blind":
        return Blind(sim, rep=rep)
    if name == "blind_slow":
        return Blind(sim, every=10.0, name="blind_slow", rep=rep)
    if name == "sit_click":
        return Blind(sim, every=5.0, move=False, name="sit_click", rep=rep)
    if name == "light":
        return LightChaser(sim, rep=rep)
    if name in ABLATIONS:
        return Partial(sim, name=name, rep=rep, **ABLATIONS[name])
    if name == "privileged":
        return Privileged(sim)
    raise KeyError(name)


# ------------------------------------------------------------------------------------------ privileged planner
class Router:
    """Shortest paths for the dot's centre around walls: the walls inflated by the body radius are the obstacles;
    a visibility graph over their corners (pushed out by ``m``) with all-pairs distances precomputed."""

    def __init__(self, walls, rb, m=0.15):
        eps = 1e-6
        self.boxes = [(x0 - rb + eps, x1 + rb - eps, y0 - rb + eps, y1 + rb - eps) for x0, x1, y0, y1 in walls]
        self.full = [(x0 - rb, x1 + rb, y0 - rb, y1 + rb) for x0, x1, y0, y1 in walls]
        pts = []
        for x0, x1, y0, y1 in self.full:
            pts += [(x0 - m, y0 - m), (x0 - m, y1 + m), (x1 + m, y0 - m), (x1 + m, y1 + m)]
        pts = [q for q in pts if not self.inside(q)]
        self.nodes = np.asarray(pts, dtype=float).reshape(-1, 2)
        N = len(self.nodes)
        if N:
            vis = ~_seg_hits(self.nodes, self.nodes, self.boxes)
            d = np.hypot(*(self.nodes[:, None, :] - self.nodes[None, :, :]).transpose(2, 0, 1))
            D = np.where(vis, d, np.inf)
            np.fill_diagonal(D, 0.0)
            for k in range(N):
                D = np.minimum(D, D[:, k:k + 1] + D[k:k + 1, :])
            self.D = D
        self.cache = {}

    def inside(self, q):
        return any(x0 < q[0] < x1 and y0 < q[1] < y1 for x0, x1, y0, y1 in self.full)

    def outside(self, q):
        """The nearest point to q that the dot's centre can occupy (q itself when free)."""
        q = (float(q[0]), float(q[1]))
        for _ in range(3):
            moved = False
            for x0, x1, y0, y1 in self.full:
                if x0 < q[0] < x1 and y0 < q[1] < y1:
                    c = [(q[0] - x0, (x0 - 0.02, q[1])), (x1 - q[0], (x1 + 0.02, q[1])),
                         (q[1] - y0, (q[0], y0 - 0.02)), (y1 - q[1], (q[0], y1 + 0.02))]
                    q = min(c)[1]
                    moved = True
            if not moved:
                break
        return q

    def _vis_to_nodes(self, Q, key=None):
        if key is not None and key in self.cache:
            return self.cache[key]
        v = ~_seg_hits(np.asarray(Q, float).reshape(-1, 2), self.nodes, self.boxes)
        if key is not None:
            self.cache[key] = v
        return v

    def dists(self, p, Q, keys=None):
        """Path lengths from p to each point of Q [k, 2], and the first waypoint toward each."""
        Q = np.asarray(Q, float).reshape(-1, 2)
        direct = np.hypot(Q[:, 0] - p[0], Q[:, 1] - p[1])
        if not self.boxes or not len(Q):
            return direct, Q.copy()
        clear = ~_seg_hits(np.asarray([p], float), Q, self.boxes)[0]
        out, way = direct.copy(), Q.copy()
        if clear.all():
            return out, way
        if not len(self.nodes):
            out[~clear] = direct[~clear] * 3.0 + 20.0
            return out, way
        vp = self._vis_to_nodes([p])[0]
        dp = np.where(vp, np.hypot(self.nodes[:, 0] - p[0], self.nodes[:, 1] - p[1]), np.inf)
        via = dp[:, None] + self.D  # [i, j]: p -> i -> ... -> j
        A = via.min(axis=0)
        first = via.argmin(axis=0)
        for k in np.flatnonzero(~clear):
            vq = self._vis_to_nodes([Q[k]], None if keys is None else keys[k])[0]
            tot = np.where(vq, A + np.hypot(self.nodes[:, 0] - Q[k, 0], self.nodes[:, 1] - Q[k, 1]), np.inf)
            j = int(np.argmin(tot))
            if np.isfinite(tot[j]):
                out[k] = tot[j]
                way[k] = self.nodes[first[j]]
            else:
                out[k] = direct[k] * 3.0 + 20.0
        return out, way


class Privileged:
    """Reads the true world state and plans greedily: the target with the best value per unit time (food with its
    stock and regrowth, ripe or ripening plants, prey by interception or at their refuge before they reappear,
    planting spots on fertile soil, delivery home); avoids ambushers, flees chasing predators (to a shelter if it is
    closer than the predator), never clicks unless the click resolves to income."""

    name = "privileged"

    def __init__(self, sim):
        a = sim.a
        self.router = Router(a.walls, a.r_body)
        self.target = None  # (kind, index, point, score, t_ready)
        self.t_plan = -math.inf
        self.spots = self._plant_spots(a)
        self.T = sim.T
        self.n_avoid = 0

    @staticmethod
    def _plant_spots(a):
        out = []
        for fx, fy, r in a.fertile:
            s = 1.1
            for i in range(-6, 7):
                for j in range(-6, 7):
                    x, y = fx + s * (i + 0.5 * j), fy + s * (0.8660254 * j)
                    if (x - fx) ** 2 + (y - fy) ** 2 <= (r - 0.02) ** 2:
                        out.append((x, y))
        return out

    def _speed(self, sim):
        a = sim.a
        return sim.vmax * (sim.k_h / H) * a.gam0 / a.gam

    def _ambushers(self, a, t):
        out = []
        for g in a.ag:
            if g["type"] == 2 and not (g["state"] == 2 and g["until"] > t + 6.0):
                out.append((g["x"], g["y"], g["r_contact"] + 0.4))
        return out

    def _risky(self, q, amb):
        return any((q[0] - x) ** 2 + (q[1] - y) ** 2 <= r * r for x, y, r in amb)

    def _plan(self, sim, t):
        a = sim.a
        p = (a.X, a.Y)
        u = max(self._speed(sim), 1e-3)
        amb = self._ambushers(a, t)
        preds = [(a._ag_pos(g, t), g) for g in a.ag if g["type"] == 1]
        C = []  # (kind, idx, point, gain, t_ready, handle, key)
        T = self.T
        n_items = len(a.items)
        # food sources
        for i, S in enumerate(a.src):
            if S["value"] <= 0:
                continue
            q = self.router.outside((S["x"], S["y"]))
            if (q[0] - S["x"]) ** 2 + (q[1] - S["y"]) ** 2 > 0.95 ** 2:
                continue  # unreachable: a wall keeps the dot's centre beyond the capture radius
            C.append(("src", i, q, 0.0, 0.0, 0.0, ("s", i)))
        for i, P in enumerate(a.plants):
            if P["state"] in (1, 2):
                C.append(("plant", i, (P["x"], P["y"]), 0.0, 0.0, 0.0, None))
        for i, g in enumerate(a.ag):
            if 3 <= g["type"] <= 5:
                C.append(("prey", i, None, 0.0, 0.0, 0.0, None))
        free_slots = sum(1 for k in range(a.plant_cap) if a.plants[k]["state"] == 0)
        if (a.plant_cap > 0 and free_slots and t + a.ripen[1] + 12.0 < T
                and 0.8 * a.plant_value > a.plant_cost):
            free = [q for q in self.spots if click_outcome(a, t, q[0], q[1])[0] == "plant"]
            if free:
                d0 = [(q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 for q in free]
                for k in np.argsort(d0)[:3]:
                    C.append(("sow", -1, free[k], 0.0, 0.0, 0.0, ("f", free[k])))
        if a.carry_cap > 0 and n_items:
            hx, hy, hr = a.home[:3]
            C.append(("home", -1, (hx, hy), 0.0, 0.0, 0.0, ("h",)))
        if not C:
            return None
        # prey points by interception
        pts, keys = [], []
        for c in C:
            if c[0] == "prey":
                g = a.ag[c[1]]
                if g["state"] == 3:
                    q = (g["rx"], g["ry"])
                else:
                    x, y = a._ag_pos(g, t)
                    moving = t < g["t_stop"] and g["speed"] > 0
                    vx, vy = (g["vx"], g["vy"]) if moving else (0.0, 0.0)
                    dx, dy = x - p[0], y - p[1]
                    A_, B_, C_ = vx * vx + vy * vy - u * u, 2 * (dx * vx + dy * vy), dx * dx + dy * dy
                    tau = None
                    if abs(A_) < 1e-12:
                        tau = -C_ / B_ if B_ < 0 else None
                    else:
                        disc = B_ * B_ - 4 * A_ * C_
                        if disc >= 0:
                            r1, r2 = (-B_ - math.sqrt(disc)) / (2 * A_), (-B_ + math.sqrt(disc)) / (2 * A_)
                            pos = [r for r in (r1, r2) if r > 0]
                            tau = min(pos) if pos else None
                    if tau is None:
                        tau = math.hypot(dx, dy) / u * 2.0
                    tau = min(tau, 40.0)
                    if moving:
                        tau_m = min(tau, g["t_stop"] - t)
                        q = (x + vx * tau_m, y + vy * tau_m)
                    else:
                        q = (x, y)
                    q = self.router.outside(q)
                pts.append(q)
                keys.append(None)
            else:
                pts.append(c[2])
                keys.append(c[6])
        dist, way = self.router.dists(p, pts, keys)
        best, scores = None, {}
        for k, c in enumerate(C):
            kind, i = c[0], c[1]
            q = pts[k]
            ta = t + dist[k] / u
            if self._risky(q, amb):
                continue
            gain, handle, ready = 0.0, 0.0, ta
            if kind == "src":
                S = a.src[i]
                n_av = S["stock"]
                if S["period"] > 0 and ta >= S["next"]:
                    n_av = min(S["cap"], n_av + 1 + int((ta - S["next"]) // S["period"]))
                if n_av == 0:
                    if S["period"] <= 0 or S["next"] > T - 2:
                        continue
                    ready, n_av = S["next"], 1
                take = n_av
                if a.carry_cap > 0:
                    room = max(0, a.carry_cap - n_items)
                    picks = min(take, room)
                    hx, hy = a.home[:2]
                    back = math.hypot(q[0] - hx, q[1] - hy) / u * 1.2
                    per_pick = S["value"] * (a.carry_mult if ready + back < min(ready + a.carry_digest, T) else
                                             (1.0 if ready + a.carry_digest < T else 0.0))
                    gain = picks * per_pick + (take - picks) * S["value"]
                else:
                    gain = take * S["value"]
                handle = (take - 1) * CLICK_DT
            elif kind == "plant":
                P = a.plants[i]
                ready = max(ta, P["t_ripe"]) if P["state"] == 1 else ta
                if ready >= P["t_spoil"] - 0.5 or ready > T - 1:
                    continue
                gain = a.plant_value
            elif kind == "prey":
                g = a.ag[i]
                if g["state"] == 3:
                    nl = g["next_look"]
                    t_re = nl if nl >= g["until"] else nl + g["look"] * math.ceil((g["until"] - nl) / g["look"])
                    ready = max(ta, t_re)
                    if ready > T - 1:
                        continue
                gain = g["value"]
            elif kind == "sow":
                gain = 0.8 * a.plant_value - a.plant_cost
            elif kind == "home":
                for v, due, _id in a.items:
                    if due > ta:
                        gain += a.carry_mult * v - (v if due < T else 0.0)
                if gain <= 0:
                    continue
                if n_items >= a.carry_cap:
                    gain *= 1.5  # a full load blocks picking: delivering frees the carrier
            risk = 1.0
            for (x, y), g in preds:
                if g["state"] in (0, 1) and (q[0] - x) ** 2 + (q[1] - y) ** 2 <= (g["r_sense"] + 1.0) ** 2:
                    risk = 0.4
            score = risk * gain / (ready - t + handle + 1.0)
            cand = (kind, i, q, score, ready, tuple(way[k]))
            scores[(kind, i if kind != "sow" else q)] = cand
            if best is None or score > best[3]:
                best = cand
        return best, scores

    def _threat(self, sim, t):
        """Flee vector (unit) from a chasing pursuit predator, or (0, 0); repulsion from wanderers and ambushers."""
        a = sim.a
        p = np.array([a.X, a.Y])
        flee, rep, shelter = None, np.zeros(2), None
        for g in a.ag:
            if g["type"] != 1:
                continue
            x, y = a._ag_pos(g, t)
            d = math.hypot(p[0] - x, p[1] - y)
            if g["state"] == 1 and d < 2.0 * g["r_sense"] + 0.5:
                best = None
                for sx, sy, r in a.shelters:
                    ds = math.hypot(p[0] - sx, p[1] - sy)
                    dpred = math.hypot(x - sx, y - sy)
                    if ds <= r - 0.1:
                        best = ("in", sx, sy)
                        break
                    if ds < dpred and (best is None or ds < best[3]):
                        best = ("go", sx, sy, ds)
                if best is not None:
                    shelter = best
                else:
                    f = unit((p[0] - x, p[1] - y))
                    flee = f if flee is None else unit((flee[0] + f[0], flee[1] + f[1]))
            elif g["state"] == 0 and d < g["r_sense"] + 1.5:
                rep += (p - np.array([x, y])) / max(d, 0.3) * (g["r_sense"] + 1.5 - d)
        return flee, rep, shelter

    def act(self, sim, t):
        a = sim.a
        p = (a.X, a.Y)
        u = self._speed(sim)
        click = False
        kind = click_outcome(a, t, a.X, a.Y)[0]
        if kind in ("prey", "harvest", "food", "pick", "deliver"):
            click = True
        elif kind == "plant" and t + a.ripen[1] + 12.0 < self.T and 0.8 * a.plant_value > a.plant_cost:
            click = True
        flee, rep, shelter = self._threat(sim, t)
        if shelter is not None:
            if shelter[0] == "in":
                return 0.0, 0.0, click
            q = self.router.outside(shelter[1:3])
            _d, w = self.router.dists(p, [q])
            v = unit((w[0][0] - p[0], w[0][1] - p[1]))
            return u * v[0] / 0.95, u * v[1] / 0.95, click
        if flee is not None:
            return u * flee[0] / 0.95, u * flee[1] / 0.95, click
        if self.target is None or t - self.t_plan >= 1.0 or self._done(a, t):
            plan = self._plan(sim, t)
            new, scores = plan if plan is not None else (None, {})
            cur = None
            if self.target is not None and not self._done(a, t):
                k0 = self.target[0], (self.target[1] if self.target[0] != "sow" else self.target[2])
                cur = scores.get(k0)
            self.target = cur if (cur is not None and new is not None and new[3] <= 1.25 * cur[3]) else new
            self.t_plan = t
        if self.target is None:
            return 0.0, 0.0, click
        kind_t, i, q, _s, ready, _w = self.target
        if kind_t == "prey":  # moving target: re-aim each step
            g = a.ag[i]
            if g["state"] != 3:
                x, y = a._ag_pos(g, t)
                moving = t < g["t_stop"] and g["speed"] > 0
                lead = min(math.hypot(x - p[0], y - p[1]) / max(u, 1e-3), 8.0)
                if moving:
                    lead = min(lead, g["t_stop"] - t)
                    q = (x + g["vx"] * lead, y + g["vy"] * lead)
                else:
                    q = (x, y)
                q = self.router.outside(q)
        dist, way = self.router.dists(p, [q])
        w = way[0]
        dx, dy = w[0] - p[0], w[1] - p[1]
        d = math.hypot(dx, dy)
        if dist[0] < 0.01:
            vx, vy = 0.0, 0.0
        else:
            sp = min(u / 0.95, d / H)  # arrive without overshooting
            vx, vy = sp * dx / max(d, 1e-9), sp * dy / max(d, 1e-9)
        # keep out of ambush disks and away from wandering predators
        v = np.array([vx, vy]) + 0.15 * rep
        for x, y, r in self._ambushers(a, t):
            off = np.array([p[0] - x, p[1] - y])
            dd = float(np.hypot(*off))
            nxt = np.array(p) + v * 2.0 - np.array([x, y])
            if dd < r + 1.2 and np.hypot(*nxt) < r + 0.1:
                n = off / max(dd, 1e-6)
                tang = v - n * float(v @ n)
                v = tang + n * (0.3 * u if dd < r + 0.2 else 0.0)
                self.n_avoid += 1
        return float(v[0]), float(v[1]), click

    def _done(self, a, t):
        if self.target is None:
            return True
        kind, i = self.target[0], self.target[1]
        if kind == "src":
            S = a.src[i]
            return S["stock"] == 0 and (S["period"] <= 0 or self.target[4] < t - 1)
        if kind == "plant":
            return a.plants[i]["state"] == 0
        if kind == "prey":
            g = a.ag[i]
            return g["state"] == 3 and self.target[4] <= t - 10
        if kind == "home":
            return not a.items
        if kind == "sow":
            q = self.target[2]
            if (a.X - q[0]) ** 2 + (a.Y - q[1]) ** 2 < 0.15 ** 2 and click_outcome(a, t, a.X, a.Y)[0] != "plant":
                return True  # at the spot but the click would not sow (a neighbour within the capture radius)
            return click_outcome(a, t, q[0], q[1])[0] != "plant"
        return False

    def clicked(self, sim, t, d_load):
        pass


CONTROLLERS = ("still", "blind", "blind_slow", "sit_click", "light", "partial", "partial_nomem", "partial_noident",
               "partial_novib", "partial_noflow", "partial_nolight", "partial_clean", "privileged")


def _job(args):
    out, family, i, name, vmax, rep = args
    _layout, ev = evaluator(Path(out))
    seed = SEED_BASE + i
    w = eco_world(ev, family, seed)
    t0 = time.process_time()
    sim = Sim(w, seed, vmax)
    ctl = make_controller(name, sim, rep)
    led = sim.run(ctl)
    row = dict(family=family, i=i, seed=seed, controller=name, rep=rep, cpu=time.process_time() - t0,
               clicks_wanted=sim.clicks_wanted)
    row.update({c: float(led[LI[c]]) for c in REPORT})
    return row


def run_controllers(out: Path, n_seeds: int, vmax: float, names, procs: int, reps: int) -> list[dict]:
    """Every controller on every (family, seed) of the panel, ``reps`` replicates of its own random streams (one
    for deterministic controllers), in seed-major order, resumable (controllers.jsonl)."""
    import multiprocessing as mp

    path = out / "controllers.jsonl"
    done = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done[(r["family"], r["i"], r["controller"], r.get("rep", 0))] = r
    jobs = [(str(out), f, i, n, vmax, k) for i in range(n_seeds) for f in FAMILIES for n in names
            for k in range(1 if n in DETERMINISTIC else reps) if (f, i, n, k) not in done]
    print(f"controllers: {len(jobs)} lives to run ({len(done)} cached), {procs} processes, vmax {vmax:.4f}",
          flush=True)
    t0 = time.time()
    with open(path, "a") as fh:
        if procs <= 1:
            it = map(_job, jobs)
        else:
            pool = mp.get_context("fork").Pool(procs, maxtasksperchild=200)
            it = pool.imap(_job, jobs, chunksize=1)
        for k, r in enumerate(it):
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            done[(r["family"], r["i"], r["controller"], r["rep"])] = r
            if (k + 1) % 100 == 0:
                el = time.time() - t0
                eta = el / (k + 1) * (len(jobs) - k - 1) / 60
                print(f"  {k + 1}/{len(jobs)} in {el / 60:.1f} min (eta {eta:.0f} min)",
                      flush=True)
        if procs > 1:
            pool.close()
            pool.join()
    return [r for r in done.values() if r["i"] < n_seeds and r["controller"] in names]


# ------------------------------------------------------------------------------------------- part 3: summary
ABLATION_SOURCE = dict(partial_nomem="memory + path integration", partial_noident="odour identity",
                       partial_novib="vibration", partial_noflow="flow", partial_nolight="light")
METRICS = ("gross", "eco_net", "click_net", *ECO_INCOME, *ECO_COST, "eco_killed", "captures", "misses", "clicks",
           "path", "speed")


def _metrics(get) -> dict:
    """Per-life metric arrays from a column getter. gross = income (all eco income); eco_net = gross minus the eco
    costs (toxin, damage, planting); click_net = eco_net minus the miss charge (c_miss 10 per empty click)."""
    m = {k: get(k) for k in (*ECO_INCOME, *ECO_COST, "eco_killed", "captures", "misses", "clicks", "path")}
    m["gross"] = get("income")
    m["eco_net"] = m["gross"] - sum(m[k] for k in ECO_COST)
    m["click_net"] = m["eco_net"] - 10.0 * m["misses"]
    m["speed"] = m["path"] / np.maximum(get("t_end"), 1.0)
    return m


def _ms(x):
    x = np.asarray(x, dtype=float)
    return [float(x.mean()), float(x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else float("nan")]


def world_checks(ev, family: str, n: int) -> dict:
    """Properties of the drawn worlds themselves (no controller): reachability, light, plume cap, start on soil."""
    unreach, n_food, lit_food, lit_lives, cap_bind, on_soil, n_walls, cur = 0, 0, 0, 0, 0, 0, [], []
    lit_toxin, n_toxin = 0, 0
    for i in range(n):
        w = eco_world(ev, family, SEED_BASE + i)
        e = spec.eco_view(w)
        walls = [tuple(e[f"wall{k}_{f}"] for f in spec.WALL_FIELDS) for k in range(int(e["eco_n_wall"]))]
        n_walls.append(len(walls))
        cur.append(e["eco_cur_speed"])
        router = Router(walls, e["eco_r_body"])
        any_lit, rate = False, 0.0
        for k in range(int(e["eco_n_src"])):
            x, y, v = e[f"src{k}_x"], e[f"src{k}_y"], e[f"src{k}_value"]
            rate += e[f"src{k}_puff"]
            if v > 0:
                n_food += 1
                q = router.outside((x, y))
                if (q[0] - x) ** 2 + (q[1] - y) ** 2 > w.rho_c ** 2:
                    unreach += 1
                if e[f"src{k}_light"] > 0:
                    lit_food += 1
                    any_lit = True
            else:
                n_toxin += 1
                lit_toxin += e[f"src{k}_light"] > 0
        lit_lives += any_lit
        cap_bind += rate * e["eco_puff_life"] > e["eco_puff_cap"]
        on_soil += any(e[f"fertile{k}_x"] ** 2 + e[f"fertile{k}_y"] ** 2 <= e[f"fertile{k}_r"] ** 2
                       for k in range(int(e["eco_n_fertile"])))
    return dict(lives=n, food_sources=n_food, food_unreachable_frac=unreach / max(n_food, 1),
                food_lit_frac=lit_food / max(n_food, 1), lives_with_lit_food=lit_lives / n,
                toxins=n_toxin, toxins_lit_frac=lit_toxin / max(n_toxin, 1),
                puff_cap_binds_frac=cap_bind / n, start_on_fertile_frac=on_soil / n,
                walls_mean=float(np.mean(n_walls)), current_speed_mean=float(np.mean(cur)))


def summarize(out: Path, n_seeds: int, names) -> dict:
    z = np.load(out / "evolved.npz")
    evo = z["ledger"]  # [genome, family, seed, ledger]
    meta = json.loads((out / "evolved_meta.json").read_text())
    speed = json.loads((out / "speed.json").read_text())
    rows = [json.loads(x) for x in (out / "controllers.jsonl").read_text().splitlines() if x.strip()]
    reps = {}
    for r in rows:  # replicates of one (family, controller, seed) are averaged within the seed
        reps.setdefault((r["family"], r["controller"], r["i"]), []).append(r)
    by = {}
    for (fam, name, i), rs in reps.items():
        avg = {k: float(np.mean([q[k] for q in rs])) for k in (*REPORT, "cpu")}
        avg["n_rep"] = len(rs)
        by.setdefault((fam, name), {})[i] = avg
    n = min(n_seeds, evo.shape[2])
    _layout, ev = evaluator(out)
    S = dict(config=dict(seed_base=SEED_BASE, seeds_per_family=n, T=1024.0, control_step=H, click_interval=CLICK_DT,
                         speed_cap=speed["cap"], sense_points=len(SENSE_OFF), cells_per_point=CELLS_PER_POINT,
                         trace_tau=2.0, detection_threshold=DET, evolved=meta["chosen"],
                         evolved_screen=dict(lives_per_family=meta["screen_seeds"], seed_base=meta["screen_base"])),
             speed=speed, families={})
    for fi, fam in enumerate(FAMILIES):
        E = evo[:, fi, :n, :]
        evm = _metrics(lambda k, E=E: E[..., LI[k]])  # [G, S]
        mean_evo = {k: v.mean(axis=0) for k, v in evm.items()}  # population mean per seed
        g_best = int(np.argmax(evm["eco_net"].mean(axis=1)))
        best_evo = {k: v[g_best] for k, v in evm.items()}
        fam_out = dict(evolved_mean={k: _ms(v) for k, v in mean_evo.items()},
                       evolved_best=dict(genome=meta["chosen"][g_best],
                                         **{k: _ms(v) for k, v in best_evo.items()}),
                       evolved_lineages={lin: {k: _ms(v[8 * j:8 * (j + 1)].mean(axis=0)) for k, v in evm.items()
                                               if k in ("gross", "eco_net", "eco_killed")}
                                         for j, lin in enumerate(LINEAGES)},
                       evolved_body_running_cost=_ms((E[..., LI["cost"]] - sum(E[..., LI[c]] for c in ECO_COST)
                                                      ).mean(axis=0)),
                       evolved_F=_ms(E[..., LI["F"]].mean(axis=0)),
                       controllers={}, vs_evolved={}, ablations={})
        C = {}
        for name in names:
            d = by.get((fam, name), {})
            if not all(i in d for i in range(n)):
                continue
            C[name] = _metrics(lambda k, d=d: np.array([d[i][k] for i in range(n)]))
            fam_out["controllers"][name] = {k: _ms(v) for k, v in C[name].items()}
            fam_out["controllers"][name]["cpu_s"] = float(np.mean([d[i]["cpu"] for i in range(n)]))
            fam_out["controllers"][name]["replicates"] = int(min(d[i]["n_rep"] for i in range(n)))
        for name in C:
            fam_out["vs_evolved"][name] = {k: _ms(C[name][k] - mean_evo[k]) for k in ("gross", "eco_net",
                                                                                      "click_net")}
        if "partial" in C and "light" in C:
            fam_out["partial_minus_light"] = {k: _ms(C["partial"][k] - C["light"][k]) for k in ("gross", "eco_net")}
        if "partial" in C:
            gap = fam_out["vs_evolved"]["partial"]["eco_net"][0]
            paying = 0
            for ab, src in ABLATION_SOURCE.items():
                if ab not in C:
                    continue
                dn = _ms(C["partial"]["eco_net"] - C[ab]["eco_net"])
                dg = _ms(C["partial"]["gross"] - C[ab]["gross"])
                res = dn[0] > 3 * dn[1]
                paying += bool(res)
                fam_out["ablations"][ab] = dict(source=src, drop_eco_net=dn, drop_gross=dg, resolved=bool(res),
                                                share_of_partial_gap=dn[0] / gap if gap > 0 else None)
            fam_out["sources_paying"] = paying
            fam_out["three_sources_pay"] = paying >= 3
            if "partial_clean" in C:
                fam_out["receptor_noise_cost"] = _ms(C["partial_clean"]["eco_net"] - C["partial"]["eco_net"])
        for name in ("blind", "blind_slow", "sit_click"):
            if name in C:
                cn = _ms(C[name]["click_net"])
                fam_out.setdefault("sensing_free", {})[name] = dict(click_net=cn, gross=_ms(C[name]["gross"]),
                                                                    pays=bool(cn[0] > 3 * cn[1] and cn[0] > 0))
        fam_out["world_checks"] = world_checks(ev, fam, n)
        S["families"][fam] = fam_out
    (out / "summary.json").write_text(json.dumps(S, indent=1))
    print_tables(S)
    return S


def print_tables(S):
    def f(x, k=0):
        return f"{x[0]:,.{k}f} ± {x[1]:,.{k}f}"
    for fam, d in S["families"].items():
        print(f"\n### {fam}\n")
        print("| body | gross income | eco costs (toxin / damage / planting) | eco net | killed | misses |")
        print("|---|---|---|---|---|---|")
        em = d["evolved_mean"]
        print(f"| evolved (mean of 16) | {f(em['gross'])} | {em['eco_toxin_cost'][0]:,.0f} / "
              f"{em['eco_damage_cost'][0]:,.0f} / {em['eco_plant_cost'][0]:,.0f} | {f(em['eco_net'])} | "
              f"{em['eco_killed'][0]:.2f} | {em['misses'][0]:.0f} |")
        eb = d["evolved_best"]
        print(f"| evolved best ({eb['genome']}) | {f(eb['gross'])} | {eb['eco_toxin_cost'][0]:,.0f} / "
              f"{eb['eco_damage_cost'][0]:,.0f} / {eb['eco_plant_cost'][0]:,.0f} | {f(eb['eco_net'])} | "
              f"{eb['eco_killed'][0]:.2f} | {eb['misses'][0]:.0f} |")
        for name, c in d["controllers"].items():
            print(f"| {name} | {f(c['gross'])} | {c['eco_toxin_cost'][0]:,.0f} / {c['eco_damage_cost'][0]:,.0f} / "
                  f"{c['eco_plant_cost'][0]:,.0f} | {f(c['eco_net'])} | {c['eco_killed'][0]:.2f} | "
                  f"{c['misses'][0]:.0f} |")
        if d.get("ablations"):
            print("\n| ablation (source removed) | drop in eco net (paired) | drop in gross | resolved (>3 SE) "
                  "| share of partial-evolved gap |")
            print("|---|---|---|---|---|")
            for x in d["ablations"].values():
                sh = "" if x["share_of_partial_gap"] is None else f"{100 * x['share_of_partial_gap']:.0f}%"
                ok = 'yes' if x['resolved'] else 'no'
                print(f"| {x['source']} | {f(x['drop_eco_net'])} | {f(x['drop_gross'])} | {ok} | {sh} |")
            print(f"\nsources paying: {d['sources_paying']} (>= 3: {d['three_sources_pay']})")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="outputs/headroom_20261020")
    p.add_argument("--seeds", type=int, default=64)
    p.add_argument("--screen", type=int, default=8)
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--parts", default="evolved,controllers,summary")
    p.add_argument("--controllers", default=",".join(CONTROLLERS))
    p.add_argument("--procs", type=int, default=2, help="controller worker processes (one thread each)")
    p.add_argument("--vmax", type=float, default=None, help="speed cap (default: from the evolved panel)")
    p.add_argument("--ctl-seeds", type=int, default=None, help="controller seeds (default --seeds)")
    p.add_argument("--reps", type=int, default=2, help="replicates per (seed, stochastic controller)")
    args = p.parse_args()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    parts = args.parts.split(",")
    if "evolved" in parts:
        evo = run_evolved(out, args.seeds, args.screen, args.top, args.threads)
        lim = speed_limit(evo)
        (out / "speed.json").write_text(json.dumps(lim, indent=1))
        print(json.dumps(lim, indent=1))
    names = [n for n in args.controllers.split(",") if n]
    n_ctl = args.ctl_seeds or args.seeds
    if "controllers" in parts:
        vmax = args.vmax if args.vmax is not None else json.loads((out / "speed.json").read_text())["cap"]
        run_controllers(out, n_ctl, vmax, names, args.procs, args.reps)
    if "summary" in parts:
        summarize(out, n_ctl, names)


if __name__ == "__main__":
    main()
