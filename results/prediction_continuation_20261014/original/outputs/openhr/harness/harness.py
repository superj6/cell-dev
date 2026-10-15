"""Central-controller measuring sticks for the CATCH/SPECK worlds (scratch harness; nothing here edits the repo).

    import sys; sys.path.insert(0, HARNESS_DIR)
    import harness as H
    fp = H.footprint("hollow3")
    res = H.ctl_run(H.C2, H.default_params(H.C2), fp, "pool", H.seeds(256, block=2), threads=6)
    res["F"], res.diag                         # a build.Lives (ledger, hashes, ...) plus .diag [n, 16], .latency [n]
    ref = H.tissue_run(H.reflex("hollow3"), "pool", H.seeds(256, block=2), threads=6)
    H.paired(res, ref)                          # mean +- SE of the per-life F difference (same seeds = same lives)

Worlds are named WorldSpecs (WORLDS) or WorldSpec objects: repo world keys (``over``) plus the scratch kernel's
prototype slots (``x``: blink_on, blink_off, t_flip, e_on, e_off, dark_amp, dim_flag) and per-life draws (t_flip ~
U[lo, hi] from the life seed). Tissue bodies (hb.Body / hb.GrnBody) run on the same scratch kernel (tissue_run), so
controller and tissue lives share target paths and ping streams exactly whenever their actions agree.
See README.md for the controller hook and the latency rule.
"""
from __future__ import annotations

import ctypes
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field, replace

import numpy as np

REPO = "/home/jgon/project/ml/cell-dev"
if REPO not in sys.path:
    sys.path.insert(0, REPO)
from src.life import analysis, build, spec  # noqa: E402
from src.life import handbuilt as hb  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = spec.V3
L = V3.L
KERNEL = build.KERNEL
SEED_BASE = 43_000_000  # this study: fresh_seeds(n, SEED_BASE + 10_000 * block); the harness owns blocks 0-9
NDIAG = 16
_i32, _i64, _u64, _f64 = ctypes.c_int32, ctypes.c_int64, ctypes.c_uint64, ctypes.c_double
_P = ctypes.POINTER

# ----------------------------------------------------------------------------------------------- controllers
NULL, C0, C1, C2, C3, C4, REPLAY = 0, 1, 2, 3, 4, 5, 99


@dataclass(frozen=True)
class CtlSpec:
    id: int
    name: str
    priv: bool
    names: tuple  # parameter names (layout of the vector)
    default: tuple
    lo: tuple = ()
    hi: tuple = ()


CONTROLLERS: dict[int, CtlSpec] = {}


def register(cs: CtlSpec) -> CtlSpec:
    """Python-side description of a controller id (for defaults, bounds and the privileged flag)."""
    CONTROLLERS[cs.id] = cs
    return cs


register(CtlSpec(NULL, "null", False, (), ()))
register(CtlSpec(C0, "C0 central reflex", False,
                 ("kappa_m", "refr_m", "kappa_tap", "refr_tap", "n_coinc", "win_coinc", "centre_steer"),
                 (1.0, 0.5, 1.0, 4.0, 1.0, 1.0, 0.0),
                 (0.05, 0.0, 0.6, 0.5, 1.0, 0.1, 0.0), (1.0, 4.0, 1.0, 8.0, 4.0, 4.0, 1.0)))
register(CtlSpec(C1, "C1 privileged pursuit", True,
                 ("dt", "gain", "lead", "kmax", "min_align", "tol", "tap_r", "tap_kappa", "use_dark", "chase_food",
                  "poison_margin", "hold_r"),
                 (0.25, 1.0, 1.0, 1.0, 0.5, 0.15, 0.8, 1.0, 1.0, 1.0, 0.3, 0.0),
                 (0.05, 0.1, 0.0, 0.1, 0.0, 0.0, 0.2, 0.6, 0.0, 0.0, 0.0, 0.0),
                 (1.0, 2.0, 5.0, 1.0, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)))
register(CtlSpec(C2, "C2 generic tracker", False,
                 ("tau_f", "bg", "gain", "tol", "r_tap", "s_tap", "dt", "kmax", "reset", "s_steer", "c_tap",
                  "min_align", "t_keep", "search_step", "search_turn"),
                 (3.0, 0.05, 1.0, 0.2, 0.5, 1.5, 0.25, 1.0, 0.0, 0.5, 0.0, 0.5, 24.0, 0.0, 0.0),
                 (0.3, 0.0, 0.1, 0.0, 0.05, 0.0, 0.05, 0.1, 0.0, 0.0, 0.0, 0.0, 2.0, 0.0, -1.0),
                 (20.0, 0.3, 2.0, 1.0, 1.5, 6.0, 1.0, 1.0, 1.0, 4.0, 4.0, 0.95, 80.0, 1.5, 1.0)))
register(CtlSpec(C3, "C3 tiny RNN", False, ("n_h", "dt", "thr", "...weights"), ()))
register(CtlSpec(REPLAY, "replay", True, ("n", "...(t_rel, act, kappa)"), ()))
C4_NAMES = ("sigma", "lam_s", "lam_bg", "v_t", "tau_eff", "R_min", "R_max", "t_resp", "rho_c", "blink_on", "blink_off",
            "dt", "h", "W", "blur_every", "gain", "kmax", "min_align", "tol", "q_tap", "steer_min")
register(CtlSpec(C4, "C4 Bayes grid tracker", False, C4_NAMES,
                 (0.6, 2.0, 0.05, 0.1, 5.0, 2.0, 6.0, 50.0, 1.0, 0.0, 0.0, 0.5, 0.2, 7.0, 2.0, 1.0, 1.0, 0.5, 0.15,
                  0.3, 0.0),
                 (0.2, 0.1, 0.001, 0.0, 0.1, 0.0, 0.5, 5.0, 0.3, 0.0, -1.0, 0.1, 0.1, 4.0, 0.25, 0.1, 0.1, 0.0, 0.0,
                  0.01, 0.0),
                 (2.0, 8.0, 0.5, 1.0, 50.0, 6.0, 12.0, 400.0, 1.5, 100.0, 100.0, 1.0, 0.4, 10.0, 4.0, 2.0, 1.0, 0.95,
                  1.0, 0.95, 0.5)))


def default_params(cid: int) -> np.ndarray:
    return np.array(CONTROLLERS[cid].default, dtype=np.float64)


def params(cid: int, **kw) -> np.ndarray:
    """Default parameter vector of ``cid`` with named overrides."""
    cs = CONTROLLERS[cid]
    p = default_params(cid)
    for k, v in kw.items():
        p[cs.names.index(k)] = v
    return p


def bayes_params(world, **kw) -> np.ndarray:
    """C4 parameters with the world's fixed rules filled in from the world spec (sigma, lam_s, lam_bg, v_t, R_min,
    R_max, t_resp, rho_c, blink_on / blink_off); tau_eff defaults to min(tau_turn, 5) (0 = never turns -> 5)."""
    ws = world_spec(world)
    w = spec.world(ws.preset, **ws.over)
    p = default_params(C4)
    names = CONTROLLERS[C4].names
    for k in ("sigma", "lam_s", "lam_bg", "v_t", "R_min", "R_max", "t_resp", "rho_c"):
        p[names.index(k)] = float(getattr(w, k))
    tt = float(w.tau_turn)
    p[names.index("tau_eff")] = min(tt, 5.0) if tt > 0 else 5.0
    p[names.index("blink_on")] = float(ws.x.get("blink_on", 0.0))
    p[names.index("blink_off")] = float(ws.x.get("blink_off", 0.0))
    for k, v in kw.items():
        p[names.index(k)] = v
    return p


def rnn_size(fp: "Footprint", n_h: int) -> int:
    nin = len(fp.sense) + 2
    return 3 + n_h * nin + n_h * n_h + n_h + len(fp.act) * n_h + len(fp.act)


def rnn_params(fp: "Footprint", n_h: int, dt: float = 0.5, thr: float = 0.5, w=None, rng=None, scale=0.3):
    n = rnn_size(fp, n_h)
    p = np.zeros(n)
    p[0], p[1], p[2] = n_h, dt, thr
    if w is not None:
        p[3:] = w
    elif rng is not None:
        p[3:] = rng.normal(0, scale, n - 3)
    return p


# ------------------------------------------------------------------------------------------------ the library
_libs: dict[str, ctypes.CDLL] = {}


def lib_path(fast: bool = True) -> str:
    return os.path.join(HERE, "ckernel_fast.so" if fast else "ckernel.so")


def load(path: str | None = None, fast: bool = True) -> ctypes.CDLL:
    """The scratch controller kernel (built by make_ckernel.py). ``path``: an agent's own build with extra
    controllers (make_ckernel.py --out DIR/x.so --ctl my.c); default: this directory's fast / full build."""
    path = path or lib_path(fast)
    if path not in _libs:
        if not os.path.exists(path):
            sys.path.insert(0, HERE)
            import make_ckernel
            make_ckernel.build(path, (), fast=path.endswith("_fast.so"))
        lib = ctypes.CDLL(path)
        build._declare(lib)
        lib.ctl_life_run.restype = _i32
        lib.ctl_life_run.argtypes = [
            _i32, _i32, _P(_i32), _P(_f64), _i32, _P(_f64), _P(_i32), _P(_i32), _P(_i32), _P(_f64), _P(_u64),
            _P(_f64), _P(_u64), _i64, _P(_f64), _P(_u64), _P(_i64), _i64, _P(_i64), _P(_f64), _P(_i64),
            _P(_i32), _P(_f64), _i32, _P(_f64), _P(_f64), _P(_i32), _P(_f64), _i32, _P(_f64)]
        lib.ctl_count.restype = _i32
        lib.ctl_info.restype = _i32
        lib.ctl_info.argtypes = [_i32, ctypes.c_char_p, _i32]
        _libs[path] = lib
    return _libs[path]


def registered(path: str | None = None) -> dict[int, str]:
    """Controller ids compiled into a library and their names."""
    lib = load(path)
    out = {}
    buf = ctypes.create_string_buffer(128)
    for i in range(lib.ctl_count()):
        cid = lib.ctl_info(i, buf, 128)
        out[cid] = buf.value.decode()
    return out


def _ptr(a, t):
    return None if a is None else a.ctypes.data_as(_P(t))


# ------------------------------------------------------------------------------------------------- worlds
XSLOT = dict(blink_on=38, blink_off=39, t_flip=40, e_on=17, e_off=18, dark_amp=16, dim_flag=19)
W_D0, W_DMIN = 7, 6


@dataclass(frozen=True)
class WorldSpec:
    """A CATCH world for the scratch kernel: ``preset`` + repo key overrides ``over`` + scratch slots ``x`` (scalars)
    + per-life uniform draws ``draws`` {slot: (lo, hi)} (drawn from the life seed, so every body gets the same value
    in the same life)."""
    name: str
    preset: str = "catch_speck_l4"
    over: dict = field(default_factory=dict)
    x: dict = field(default_factory=dict)
    draws: dict = field(default_factory=dict)

    def with_(self, name: str | None = None, x: dict | None = None, draws: dict | None = None, **over) -> "WorldSpec":
        return WorldSpec(name or self.name, self.preset, dict(self.over, **over), dict(self.x, **(x or {})),
                         dict(self.draws, **(draws or {})))


FAST = dict(d0=0.5, d_min=0.25)
DECOY_LITE = dict(b2_amp=1.0, b2_sigma=1.5, b2_value=-50.0, b2_p=0.5, b2_mode=0)
WORLDS = {w.name: w for w in (
    WorldSpec("base1"),                                   # today's SPECK: d0 1, d_min 0.5
    WorldSpec("base", over=dict(FAST)),                   # the plan's base: d0 0.5, d_min 0.25
    WorldSpec("pool", over=dict(FAST, sigma=0.4, lam_s=4.0)),
    WorldSpec("blink20", x=dict(blink_on=20.0, blink_off=20.0)),           # d0 1 (prior study's blink)
    WorldSpec("blink20f", over=dict(FAST), x=dict(blink_on=20.0, blink_off=20.0)),
    WorldSpec("flash6", x=dict(blink_on=6.0, blink_off=-1.0)),
    WorldSpec("flip_mid", draws=dict(t_flip=(256.0, 768.0))),             # d0 1 (prior study's flip)
    WorldSpec("flip_midf", over=dict(FAST), draws=dict(t_flip=(256.0, 768.0))),
    WorldSpec("lead", over=dict(v_t=0.3, tau_turn=200.0)),                 # d0 1 (prior study's lead)
    WorldSpec("leadf", over=dict(FAST, v_t=0.3, tau_turn=200.0)),
    WorldSpec("decoy_lite", over=dict(DECOY_LITE)),
    WorldSpec("decoy_wide", over=dict(b2_amp=1.0, b2_sigma=1.5, b2_value=-100.0, b2_p=1.0, b2_mode=0)),
    WorldSpec("same_peak", over=dict(b2_amp=1.0, b2_sigma=1.2, b2_value=-25.0, b2_p=0.3, b2_mode=0)),
    WorldSpec("food_twin", over=dict(b2_amp=1.0, b2_sigma=0.6, b2_value=500.0, b2_p=1.0, b2_mode=1)),
    WorldSpec("wound25", over=dict(kill_t=512.0, kill_frac=0.25)),
    WorldSpec("wound50", over=dict(kill_t=512.0, kill_frac=0.5)),
)}


def world_spec(w) -> WorldSpec:
    if isinstance(w, WorldSpec):
        return w
    if isinstance(w, str):
        return WORLDS[w]
    raise TypeError("a world is a WORLDS name or a WorldSpec")


def life_draw(seed: int, slot: str, lo: float, hi: float) -> float:
    """Per-life uniform draw keyed by (life seed, slot name): the same value for every body in that life."""
    key = int(np.frombuffer(slot.encode().ljust(8, b"\0")[:8], dtype=np.uint64)[0])
    u = np.random.default_rng([int(seed) & spec.MASK64, key]).random()
    return float(lo + (hi - lo) * u)


def world_vectors(w, seed_rows: np.ndarray, flags: int = 0) -> tuple[np.ndarray, list]:
    """(world vectors [n, 66] with the scratch slots filled, the spec.World of life 0) for ``w`` on these seeds."""
    ws = world_spec(w)
    base = spec.world(ws.preset, **ws.over)
    base = replace(base, flags=base.flags | flags)
    vec = KERNEL.pack_world(base)
    n = len(seed_rows)
    out = np.repeat(vec[None, :], n, axis=0)
    for k, v in ws.x.items():
        out[:, XSLOT[k]] = v
    for k, (lo, hi) in ws.draws.items():
        out[:, XSLOT[k]] = [life_draw(int(s[0]), k, lo, hi) for s in seed_rows]
    return np.ascontiguousarray(out), base


def seeds(n: int, block: int, first: int = 0) -> list[int]:
    """Fresh life seeds of this study's block (0-9 belong to the harness)."""
    return analysis.fresh_seeds(n, seed0=SEED_BASE + 10_000 * block, first=first)


# --------------------------------------------------------------------------------------------- footprints
INERT = V3.theta(tau_m=2.0, t_ref=1.0)  # never fires, no receptor: b 0, g_r 0, kappa 0, emit 0
INERT_PROGRAM = V3.pack_program(INERT, alone=INERT, juvenile=INERT, rim=INERT, zygote=INERT)


@dataclass(frozen=True)
class Footprint:
    """A fixed body: sense sites (z = 0), act sites (z = 1), and ``hidden`` inert planes above the act sites (they
    only cost c_live; a full L4 stack is hidden = 2). Cell order = hb.role_cells order (sense, then act), so uids match
    the hand-built body of the same shape."""
    name: str
    sense: tuple
    act: tuple
    hidden: int = 0

    def cells(self) -> list:
        base = [(a, b, z, 0) for a, b, z, _ in hb.role_cells(list(self.sense), list(self.act))]
        return base + [(a, b, 2 + h, 0) for h in range(self.hidden) for a, b in self.act]

    @property
    def n_cells(self) -> int:
        return len(self.sense) + len(self.act) * (1 + self.hidden)

    def inert_body(self) -> hb.Body:
        """The inert program body with this footprint (same cells, same order): the stream-equality reference."""
        return hb.Body(f"inert@{self.name}", INERT_PROGRAM, tuple(self.cells()), about="inert footprint")


def footprint(name: str) -> Footprint:
    """``hollow{k}`` (reflex@hollow3's shape: sense = centre + ring k, act = disk k), ``ring{k}`` (router@ring4's:
    both planes disk k), ``disk{k}`` (= ring{k}), ``disk{k}x4`` (disk k in all four planes of the L4 stack)."""
    import re
    m = re.fullmatch(r"disk(\d+)x4", name)
    if m:
        d = tuple(hb.disk(int(m.group(1))))
        return Footprint(name, d, d, hidden=2)
    m = re.fullmatch(r"disk(\d+)", name)
    if m:
        name = f"ring{m.group(1)}"
    sense, act = hb.speck_shape(name)
    return Footprint(name, tuple(sense), tuple(act))


# --------------------------------------------------------------------------------------------- runs
class CtlLives(build.Lives):
    diag: np.ndarray
    latency: np.ndarray
    cid: np.ndarray


def _pack_init(cells, n):
    return build._init(list(cells), n, V3)


def ctl_run(cid, params_, fp: Footprint, world, seeds_, *, extra=None, threads: int = 4, latency="d0",
            privileged: bool | None = None, charge: str = "relay", t_ref_min: float = 0.5, quant: bool = False,
            lib: str | None = None, fast: bool = True, raster_cap: int = 0, fate_cap: int = 0) -> CtlLives:
    """Lives of controller ``cid`` (an int, or one per life) with ``params_`` (one vector, or one row per life) on
    footprint ``fp`` in ``world`` (a WORLDS name or WorldSpec) on ``seeds_``.

    latency: "d0" (default: the world's median one-hop contact delay d0), "dmin" (the causality floor d_min), or a
    number; recorded per life in ``.latency``. charge: "none", "receptor" (c_rec per ping, as a g_r 1 sense cell) or
    "relay" (receptor + one relay spike per ping: c_spike + c_msg, the cheapest tissue that conveys every ping one
    hop). t_ref_min: minimum interval between strokes of one act cell (0.5 = the GRN grid's smallest t_ref).
    privileged: default = the controller's registered flag. quant: round kappa up to {0.25, 0.5, 1}.
    """
    sd = build._seeds(seeds_)
    n = len(sd)
    wv, base = world_vectors(world, sd, flags=V3.flags("program_mode"))
    cids = np.full(n, cid, dtype=np.int32) if np.isscalar(cid) else np.ascontiguousarray(cid, dtype=np.int32)
    P = np.atleast_2d(np.asarray(params_, dtype=np.float64))
    if P.shape[1] == 0:
        P = np.zeros((1, 1))
    if P.shape[0] == 1 and n > 1:
        P = np.repeat(P, n, axis=0)
    P = np.ascontiguousarray(P)
    if P.shape[0] != n:
        raise ValueError(f"{P.shape[0]} parameter rows for {n} lives")
    if latency == "d0":
        lat = wv[:, W_D0].copy()
    elif latency == "dmin":
        lat = wv[:, W_DMIN].copy()
    else:
        lat = np.full(n, float(latency))
    lat = np.ascontiguousarray(lat)
    tref = np.full(n, float(t_ref_min))
    fl = np.zeros(n, dtype=np.int32)
    for i, c in enumerate(cids):
        pv = CONTROLLERS[int(c)].priv if (privileged is None and int(c) in CONTROLLERS) else bool(privileged)
        fl[i] = (1 if pv else 0) | {"none": 0, "receptor": 2, "relay": 6}[charge] | (8 if quant else 0)
    ex = np.ascontiguousarray(np.zeros(1) if extra is None else np.asarray(extra, dtype=np.float64))
    cells, counts = _pack_init(fp.cells(), n)
    lat_t, unit = KERNEL.lattice_tables(base.lattice)
    prog = np.ascontiguousarray(INERT_PROGRAM[None, :])
    gof = np.zeros(n, dtype=np.int32)
    ledger = np.zeros((n, KERNEL.LEDGER_SIZE))
    hashes = np.zeros((n, KERNEL.HASH_SIZE), dtype=np.uint64)
    diag = np.zeros((n, NDIAG))
    out = CtlLives(ledger, hashes, abi=V3)
    if raster_cap > 0:
        out.raster_t = np.zeros((n, raster_cap)); out.raster_uid = np.zeros((n, raster_cap), dtype=np.uint64)
        out.raster_n = np.zeros(n, dtype=np.int64)
    if fate_cap > 0:
        out.fate_i = np.zeros((n, fate_cap, KERNEL.FATE_I_SIZE), dtype=np.int64)
        out.fate_f = np.zeros((n, fate_cap, KERNEL.FATE_F_SIZE)); out.fate_n = np.zeros(n, dtype=np.int64)
    L_ = load(lib, fast)
    rc = L_.ctl_life_run(
        n, threads, _ptr(lat_t, _i32), _ptr(unit, _f64), 1, _ptr(prog, _f64), _ptr(gof, _i32), _ptr(cells, _i32),
        _ptr(counts, _i32), _ptr(wv, _f64), _ptr(sd, _u64), _ptr(ledger, _f64), _ptr(hashes, _u64), raster_cap,
        _ptr(out.raster_t, _f64), _ptr(out.raster_uid, _u64), _ptr(out.raster_n, _i64), fate_cap,
        _ptr(out.fate_i, _i64), _ptr(out.fate_f, _f64), _ptr(out.fate_n, _i64),
        _ptr(cids, _i32), _ptr(P, _f64), P.shape[1], _ptr(lat, _f64), _ptr(tref, _f64), _ptr(fl, _i32),
        _ptr(ex, _f64), len(ex), _ptr(diag, _f64))
    if rc != 0:
        raise ValueError(f"ctl_life_run returned {rc}: " + (build.RETURN_CODES.get(rc) or
                         "unknown controller id, non-program life, window scheduler or negative latency"))
    out.diag, out.latency, out.cid = diag, lat, cids
    return out


def ctl_batch(cid, cand: np.ndarray, fp: Footprint, world, seeds_, **kw) -> np.ndarray:
    """F of every candidate parameter vector (rows of ``cand``) on every seed (common random numbers): [n_cand, n]."""
    cand = np.atleast_2d(np.asarray(cand, dtype=np.float64))
    sd = list(seeds_)
    m, n = len(cand), len(sd)
    res = ctl_run(cid, np.repeat(cand, n, axis=0), fp, world, sd * m, **kw)
    return res["F"].reshape(m, n)


def tissue_run(org, world, seeds_, *, threads: int = 4, fast: bool = True, lib: str | None = None,
               raster_cap: int = 0, fate_cap: int = 0, flags: int = 0) -> build.Lives:
    """Lives of a tissue body (hb.Body program body or hb.GrnBody genome) on the SAME scratch kernel (life_run,
    unchanged by controller mode) in ``world``."""
    sd = build._seeds(seeds_)
    n = len(sd)
    is_prog = isinstance(org, hb.Body)
    fl = (V3.flags("program_mode") | org.flags if is_prog else 0) | flags
    wv, base = world_vectors(world, sd, flags=fl)
    lat_t, unit = KERNEL.lattice_tables(base.lattice)
    if is_prog:
        prog, gen = np.ascontiguousarray(np.atleast_2d(org.program)), None
        cells, counts = _pack_init(org.cells, n)
    else:
        prog, gen = None, np.ascontiguousarray(np.atleast_2d(org.table(base.lattice)))
        cells, counts = (None, None)
    gof = np.zeros(n, dtype=np.int32)
    ledger = np.zeros((n, KERNEL.LEDGER_SIZE))
    hashes = np.zeros((n, KERNEL.HASH_SIZE), dtype=np.uint64)
    out = build.Lives(ledger, hashes, abi=V3)
    if raster_cap > 0:
        out.raster_t = np.zeros((n, raster_cap)); out.raster_uid = np.zeros((n, raster_cap), dtype=np.uint64)
        out.raster_n = np.zeros(n, dtype=np.int64)
    if fate_cap > 0:
        out.fate_i = np.zeros((n, fate_cap, KERNEL.FATE_I_SIZE), dtype=np.int64)
        out.fate_f = np.zeros((n, fate_cap, KERNEL.FATE_F_SIZE)); out.fate_n = np.zeros(n, dtype=np.int64)
    L_ = load(lib, fast)
    rc = L_.life_run(
        n, threads, _ptr(lat_t, _i32), _ptr(unit, _f64), 0 if gen is None else len(gen), _ptr(gen, _f64),
        0 if prog is None else len(prog), _ptr(prog, _f64), _ptr(gof, _i32), _ptr(cells, _i32), _ptr(counts, _i32),
        _ptr(wv, _f64), _ptr(sd, _u64), _ptr(ledger, _f64), _ptr(hashes, _u64), raster_cap,
        _ptr(out.raster_t, _f64), _ptr(out.raster_uid, _u64), _ptr(out.raster_n, _i64), fate_cap,
        _ptr(out.fate_i, _i64), _ptr(out.fate_f, _f64), _ptr(out.fate_n, _i64))
    if rc != 0:
        raise ValueError(f"life_run returned {rc}: {build.RETURN_CODES.get(rc, 'unknown error')}")
    return out


# --------------------------------------------------------------------------------------------- reference bodies
def reflex(shape: str = "hollow3", knobs: dict | None = None, name: str | None = None) -> hb.Body:
    """reflex@<shape> with the frozen SPECK knobs (or ``knobs``, a re-tuned set)."""
    if knobs is None:
        return hb.speck_body(f"reflex@{shape}") if f"reflex@{shape}" in hb.SPECK_TUNED else \
            hb.speck_body("reflex@hollow3", shape)
    return hb.role_body(dict(knobs, **hb.speck_fixed("reflex")), shape, name or f"reflex rt@{shape}")


def router(shape: str = "ring4", knobs: dict | None = None) -> hb.Body:
    if knobs is None:
        return hb.speck_body(f"router@{shape}")
    return hb.role_body(dict(knobs, **hb.speck_fixed("router")), shape, f"router rt@{shape}")


def retuned_reflex_knobs() -> dict:
    """Re-tuned reflex@hollow3 knobs per world from the prior studies (reflex_knobs.json; see its 'source')."""
    p = os.path.join(HERE, "reflex_knobs.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def best_reflex(world, seeds_, threads: int = 4, extra_candidates: dict | None = None) -> tuple[str, build.Lives, dict]:
    """The better, on these (fresh) lives, of the frozen reflex@hollow3 and every re-tuned set recorded for this
    world (and ``extra_candidates`` {name: knobs}). Returns (name, lives, {name: mean F})."""
    name = world_spec(world).name
    cands = {"reflex@hollow3": None}
    for k, v in retuned_reflex_knobs().get(name, {}).items():
        cands[k] = v["knobs"]
    cands.update(extra_candidates or {})
    res = {k: tissue_run(reflex("hollow3", v), world, seeds_, threads=threads) for k, v in cands.items()}
    means = {k: float(r["F"].mean()) for k, r in res.items()}
    best = max(means, key=means.get)
    return best, res[best], means


# --------------------------------------------------------------------------------------------- statistics
def F(res) -> np.ndarray:
    return np.asarray(res["F"], dtype=np.float64)


def paired(a, b) -> dict:
    """Mean +- SE of the per-life difference a - b (lives matched by seed). a, b: Lives or F arrays."""
    fa = F(a) if hasattr(a, "ledger") else np.asarray(a)
    fb = F(b) if hasattr(b, "ledger") else np.asarray(b)
    return analysis.paired(fa, fb)


def summary(res, cols=("F", "captures", "misses", "clicks", "b2_clicks", "spikes", "cost", "income", "path")) -> dict:
    out = {k: float(res[k].mean()) for k in cols}
    out["F_se"] = float(F(res).std(ddof=1) / math.sqrt(len(F(res)))) if len(F(res)) > 1 else 0.0
    out["n"] = int(len(F(res)))
    return out


def pfmt(d: dict) -> str:
    return f"{d['mean']:+.2f} +- {d['se']:.2f}"


# --------------------------------------------------------------------------------------------- tuner
def es_tune(cid, x0, fp: Footprint, world, tune_seeds, *, sigma0=None, lo=None, hi=None, iters: int = 30,
            popsize: int = 16, lives_per_gen: int | None = None, threads: int = 4, seed: int = 0, log=print,
            mask=None, **kw) -> dict:
    """Separable CMA-ES (diagonal covariance, rank-mu update) on mean F over tuning lives with common random numbers:
    every candidate of a generation is scored on the same lives. ``lives_per_gen``: a fresh subset of ``tune_seeds``
    per generation (None = all of them every generation). ``mask``: indices of the parameters to tune (others fixed).
    Returns {x, F (mean over all tune_seeds at the end), history}. Parameters are clipped to [lo, hi]."""
    rng = np.random.default_rng(seed)
    cs = CONTROLLERS.get(cid)
    x0 = np.asarray(x0, dtype=np.float64).copy()
    lo = np.asarray(lo if lo is not None else (cs.lo if cs and cs.lo else x0 - 1e9), dtype=np.float64)
    hi = np.asarray(hi if hi is not None else (cs.hi if cs and cs.hi else x0 + 1e9), dtype=np.float64)
    idx = np.arange(len(x0)) if mask is None else np.asarray(mask)
    d = len(idx)
    span = np.where(np.isfinite(hi - lo) & (hi - lo < 1e8), hi - lo, np.maximum(np.abs(x0), 1.0))
    sig = np.asarray(sigma0 if sigma0 is not None else 0.2 * span, dtype=np.float64)
    if sig.ndim == 0:
        sig = np.full(len(x0), float(sig))
    sig = sig[idx]
    mu = popsize // 2
    w = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1)); w /= w.sum()
    mueff = 1.0 / (w ** 2).sum()
    cc, cs_ = 4.0 / (d + 4.0), (mueff + 2.0) / (d + mueff + 5.0)
    c1 = 2.0 / ((d + 1.3) ** 2 + mueff)
    cmu = min(1 - c1, 2 * (mueff - 2 + 1 / mueff) / ((d + 2) ** 2 + mueff))
    c1, cmu = c1 * (d + 2) / 3, cmu * (d + 2) / 3  # separable CMA learning rates
    damps = 1 + 2 * max(0, math.sqrt((mueff - 1) / (d + 1)) - 1) + cs_
    chiN = math.sqrt(d) * (1 - 1 / (4 * d) + 1 / (21 * d * d))
    m = x0[idx].copy(); C = np.ones(d); pc = np.zeros(d); ps = np.zeros(d); s = 1.0
    sd_all = list(tune_seeds)
    hist = []
    best = (-np.inf, x0.copy())
    for g in range(iters):
        sub = sd_all if lives_per_gen is None else list(rng.choice(sd_all, lives_per_gen, replace=False))
        z = rng.standard_normal((popsize, d))
        y = z * np.sqrt(C)
        cand = np.repeat(x0[None, :], popsize, axis=0)
        cand[:, idx] = np.clip(m + s * sig * y, lo[idx], hi[idx])
        cand[0, idx] = np.clip(m, lo[idx], hi[idx])  # the mean itself is always scored
        t0 = time.time()
        Fm = ctl_batch(cid, cand, fp, world, sub, threads=threads, **kw).mean(axis=1)
        order = np.argsort(-Fm)
        if Fm[order[0]] > best[0]:
            best = (float(Fm[order[0]]), cand[order[0]].copy())
        ysel = (cand[order[:mu]][:, idx] - m) / (s * sig)
        m_old = m.copy()
        m = m + s * sig * (w @ ysel)
        m = np.clip(m, lo[idx], hi[idx])
        ystep = (m - m_old) / (s * sig)
        ps = (1 - cs_) * ps + math.sqrt(cs_ * (2 - cs_) * mueff) * ystep / np.sqrt(C)
        hsig = np.linalg.norm(ps) / math.sqrt(1 - (1 - cs_) ** (2 * (g + 1))) < (1.4 + 2 / (d + 1)) * chiN
        pc = (1 - cc) * pc + hsig * math.sqrt(cc * (2 - cc) * mueff) * ystep
        C = (1 - c1 - cmu) * C + c1 * pc ** 2 + cmu * (w @ ysel ** 2)
        s *= math.exp((cs_ / damps) * (np.linalg.norm(ps) / chiN - 1))
        hist.append(dict(g=g, F_mean_cand=float(Fm[0]), F_best=float(Fm[order[0]]), sigma=float(s), sec=time.time() - t0))
        if log:
            log(f"es g{g:3d} F(mean) {Fm[0]:+.3f} best {Fm[order[0]]:+.3f} s {s:.3f} ({time.time() - t0:.1f}s)")
    xm = x0.copy(); xm[idx] = m
    fin = ctl_batch(cid, np.stack([xm, best[1]]), fp, world, sd_all, threads=threads, **kw).mean(axis=1)
    x = xm if fin[0] >= fin[1] else best[1]
    return dict(x=x, F=float(max(fin)), F_mean_vec=float(fin[0]), F_best_seen=float(fin[1]), history=hist)
