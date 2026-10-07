"""The one-life contract: constants, hashing, phenotype decode, costs, world presets and kernel packing.

This module is the Python mirror of ``docs/LIFE_ABI.md``. The C kernel and the Python reference both implement that
document; every function here that computes a model quantity (hash draws, knob decode, gene-rate decode) uses the
same IEEE-754 float64 operations in the same order, so results agree bitwise on the same libm.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields, replace

import numpy as np

from src import lattice as _lat

ABI_VERSION = 2  # 2: the GRN input flank_best/2 was removed (LIFE_ABI.md 15.32)

# ---------------------------------------------------------------------------------------------------------- dims
G_MAX = 16  # gene slots
G_INIT = 8  # active gene slots at initialization
M = 2  # morphogens
C = 2  # spike channels
S = 0  # receptor modalities (v1)
P = 21  # phenotype knobs
NIN = G_MAX + 6  # regulatory inputs: g[16], m/(1+m)[2], f/tau_tr, r/tau_tr[2], n_view/D

P_MAX = 3.0  # tick-interval bound used by the D_m decode (1.5 x the reference P0 = 2)
CHEM_SHIP_MAX = 0.9  # a tick never ships more than this fraction of its morphogen
V_FLOOR = -2.0  # membrane register floor
Q10 = 1024.0  # membrane register resolution (2^10 steps per unit)
SHAT_EPS = 1e-6  # directional-gain normalizer
PLACE_NOISE = 1e-3  # weight of the hash term in division placement
MAX_INIT = 64  # cells in an explicit initial body
EMPTY = 0  # uid of "no cell" in a view (real uids are odd)

# ---------------------------------------------------------------------------------------------------------- hash
MASK64 = (1 << 64) - 1
TWO_M53 = 2.0 ** -53

# draw streams: hash64(seed, stream, *keys); the keys of each stream are listed in LIFE_ABI.md section 3
S_ZYG, S_UID, S_TAU, S_CLK, S_PHASE, S_DC, S_JIT, S_DROP, S_TICK = 1, 2, 3, 4, 5, 6, 7, 8, 9
S_DIE, S_DIV, S_PLACE, S_NOISE, S_NSIGN, S_KILL, S_TIE, S_ORDER = 10, 11, 12, 13, 14, 15, 16, 17
STREAMS = dict(zyg=S_ZYG, uid=S_UID, tau=S_TAU, clk=S_CLK, phase=S_PHASE, dc=S_DC, jit=S_JIT, drop=S_DROP,
               tick=S_TICK, die=S_DIE, div=S_DIV, place=S_PLACE, noise=S_NOISE, nsign=S_NSIGN, kill=S_KILL,
               tie=S_TIE, order=S_ORDER)
HASH_INIT = 0x243F6A8885A308D3  # initial value of every log-hash family


def splitmix64(x: int) -> int:
    """The SplitMix64 finalizer (Steele et al.), on unsigned 64-bit integers."""
    z = (x + 0x9E3779B97F4A7C15) & MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return z ^ (z >> 31)


def hash64(seed: int, stream: int, *keys: int) -> int:
    """Counter hash: fold each key (two's complement, mod 2^64) through splitmix64."""
    h = splitmix64((seed & MASK64) ^ splitmix64(stream & MASK64))
    for k in keys:
        h = splitmix64(h ^ (k & MASK64))
    return h


def u01(h: int) -> float:
    """Uniform in the open interval (0, 1): an odd multiple of 2^-53, so it never equals 0, 1 or a dyadic p."""
    return float((h >> 11) | 1) * TWO_M53


def draw(seed: int, stream: int, *keys: int) -> float:
    return u01(hash64(seed, stream, *keys))


def normal(seed: int, stream: int, *keys: int) -> float:
    """Irwin-Hall(12) - 6: mean 0, variance 1, support [-6, 6]; integer sum, so exact and order-free."""
    s = 0
    for j in range(12):
        s += hash64(seed, stream, *keys, j) >> 11
    return float(s) * TWO_M53 - 6.0


def sitekey(a: int, b: int) -> int:
    """64-bit key of integer site coordinates: uint32(a) << 32 | uint32(b)."""
    return ((a & 0xFFFFFFFF) << 32) | (b & 0xFFFFFFFF)


def uid_initial(seed: int, index: int) -> int:
    return hash64(seed, S_ZYG, index) | 1


def uid_daughter(seed: int, mother: int, div_count: int) -> int:
    return hash64(seed, S_UID, mother, div_count) | 1


# ------------------------------------------------------------------------------------------------- numeric helpers
def sigmoid(x: float) -> float:
    """1 / (1 + exp(-x)) as C evaluates it: where exp(-x) overflows to inf (x < about -709.78) the result is 0.0;
    Python's math.exp raises there instead, so that case is mirrored explicitly."""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0


def clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)


def rint(x: float) -> float:
    """Round half to even keeping the sign of x, exactly as C ``nearbyint`` (so rint(-0.4) is -0.0)."""
    return math.copysign(float(round(x)), x)


def q8(x: float) -> float:
    """Clip to [-2, 2] and round to the 1/8 grid."""
    return rint(clip(x, -2.0, 2.0) * 8.0) / 8.0


def q10(v: float) -> float:
    """Membrane register: floor at -2, then round to the 2^-10 grid."""
    return rint(max(v, V_FLOOR) * Q10) / Q10


# ---------------------------------------------------------------------------------------------- phenotype knobs
KNOBS = ("w0", "w1", "b", "tau_m", "t_ref", "emit0", "emit1", "delta", "kappa", "p_div", "asym", "p_die", "phi",
         "sec0", "sec1", "pol0", "pol1", "tau_tr", "a0", "a1", "chi")
K = {name: i for i, name in enumerate(KNOBS)}

TAU_M = (1.0, 2.0, 4.0, 8.0, 16.0)
T_REF = tuple(0.5 * k for k in range(1, 9))
DELTA = (0.0, 0.5, 1.0, 2.0)
KAPPA = (0.0, 0.25, 0.5, 1.0)
PHI = (0.0, 0.5, 1.0, 2.0)
TAU_TR = (2.0, 4.0, 8.0, 16.0)
P_FATE = (0.0,) + tuple(2.0 ** (k - 8) for k in range(1, 9))
Q8_GRID = tuple(k / 8 for k in range(-16, 17))
GRIDS = dict(w0=Q8_GRID, w1=Q8_GRID, b=Q8_GRID, tau_m=TAU_M, t_ref=T_REF, emit0=(0.0, 1.0), emit1=(0.0, 1.0),
             delta=DELTA, kappa=KAPPA, p_div=P_FATE, p_die=P_FATE, phi=PHI, pol0=Q8_GRID, pol1=Q8_GRID,
             tau_tr=TAU_TR, a0=Q8_GRID, a1=Q8_GRID, chi=Q8_GRID)
RANGES = dict(asym=(0.0, 1.0), sec0=(0.0, 0.5), sec1=(0.0, 0.5))  # continuous knobs


def _level(table, y: float) -> float:  # 4-level knobs: index clip(round(2y), 0, 3)
    return table[int(clip(rint(2.0 * y), 0.0, 3.0))]


def _fate(y: float) -> float:
    k = int(clip(rint(4.0 * y), 0.0, 8.0))
    return 0.0 if k == 0 else 2.0 ** (k - 8)


def decode_knobs(y) -> list[float]:
    """theta = decode(y) for the 21 readout values y = A.g + a0 (LIFE_ABI.md section 8)."""
    y = [float(v) for v in y]
    return [
        q8(y[0]), q8(y[1]), q8(y[2]),
        2.0 ** clip(rint(y[3] + 2.0), 0.0, 4.0),
        0.5 * clip(rint(2.0 * y[4] + 4.0), 1.0, 8.0),
        1.0 if y[5] > 0.0 else 0.0, 1.0 if y[6] > 0.0 else 0.0,
        _level(DELTA, y[7]), _level(KAPPA, y[8]),
        _fate(y[9]), sigmoid(y[10]), _fate(y[11]), _level(PHI, y[12]),
        0.5 * sigmoid(y[13]), 0.5 * sigmoid(y[14]),
        q8(2.0 * math.tanh(y[15])), q8(2.0 * math.tanh(y[16])),
        TAU_TR[int(clip(rint(y[17] + 1.5), 0.0, 3.0))],
        q8(y[18]), q8(y[19]), q8(y[20]),
    ]


def readout(gt_row, g) -> list[float]:
    """y_p = a0[p] + sum_k A[p][k] g[k], accumulated left to right over k = 0..15 (packed genome table row)."""
    A = gt_row[GENOME_SLICES["A"][0]:GENOME_SLICES["A"][1]]
    a0 = gt_row[GENOME_SLICES["a0"][0]:GENOME_SLICES["a0"][1]]
    out = []
    for p in range(P):
        y = float(a0[p])
        for k in range(G_MAX):
            y = y + float(A[p * G_MAX + k]) * float(g[k])
        out.append(y)
    return out


def phenotype(gt_row, g) -> list[float]:
    return decode_knobs(readout(gt_row, g))


def theta(**knobs) -> np.ndarray:
    """A decoded phenotype vector by knob name (program mode); unnamed knobs take neutral defaults."""
    th = dict(w0=0.0, w1=0.0, b=0.0, tau_m=1.0, t_ref=0.5, emit0=0.0, emit1=0.0, delta=0.0, kappa=0.0, p_div=0.0,
              asym=0.0, p_die=0.0, phi=0.0, sec0=0.0, sec1=0.0, pol0=0.0, pol1=0.0, tau_tr=2.0, a0=0.0, a1=0.0,
              chi=0.0)
    bad = set(knobs) - set(th)
    if bad:
        raise KeyError(f"unknown knobs {sorted(bad)}")
    th.update({k: float(v) for k, v in knobs.items()})
    return np.array([th[k] for k in KNOBS], dtype=np.float64)


# ---------------------------------------------------------------------------------------------- gene decode
def decode_lambda(x: float) -> float:
    """Gene rate class: 2^-(1 + clip(round(x + 3), 0, 6)), i.e. 1/2 .. 1/128 per own tick."""
    return 2.0 ** -(1.0 + clip(rint(float(x) + 3.0), 0.0, 6.0))


def decode_dm(x: float, D: int) -> float:
    """Per-contact packet fraction per time unit, 0.9 sigma(x) / (D P_MAX)."""
    return (CHEM_SHIP_MAX * sigmoid(float(x))) / (D * P_MAX)


def decode_km(x: float) -> float:
    """Morphogen decay rate per time unit, 0.005 + 0.3 sigma(x)."""
    return 0.005 + 0.3 * sigmoid(float(x))


# ---------------------------------------------------------------------------------------------- genome layout
@dataclass(frozen=True)
class GField:
    name: str
    shape: tuple
    block: str  # reg | pheno (mutation blocks)
    unit: str  # row | col | elem | global: how entries map onto crossover units (gene k or the global unit)


GENOME_FIELDS = (
    GField("W", (G_MAX, NIN), "reg", "row"),
    GField("b", (G_MAX,), "reg", "elem"),
    GField("lam", (G_MAX,), "reg", "elem"),
    GField("s0", (G_MAX,), "reg", "elem"),
    GField("Q", (G_MAX,), "reg", "elem"),
    GField("act", (G_MAX,), "reg", "elem"),
    GField("A", (P, G_MAX), "pheno", "col"),
    GField("a0", (P,), "pheno", "global"),
    GField("Dm", (M,), "reg", "global"),
    GField("km", (M,), "reg", "global"),
)


def _slices(flds) -> dict[str, tuple[int, int]]:
    out, off = {}, 0
    for f in flds:
        n = math.prod(f.shape)
        out[f.name] = (off, off + n)
        off += n
    return out


GENOME_SLICES = _slices(GENOME_FIELDS)
GENOME_SIZE = max(b for _, b in GENOME_SLICES.values())  # 793
PACKED_NAMES = dict(W="W", b="b", lam="lam", s0="g0", Q="Q", act="act", A="A", a0="a0", Dm="Dm", km="km")


def genome_view(params, name: str) -> np.ndarray:
    """Named field of genome rows ``[..., GENOME_SIZE]`` with its natural shape."""
    a, b = GENOME_SLICES[name]
    shape = next(f.shape for f in GENOME_FIELDS if f.name == name)
    params = np.asarray(params)
    return params[..., a:b].reshape(*params.shape[:-1], *shape)


def pack_genomes(params, kind: str = "hex") -> np.ndarray:
    """Raw float32 genomes ``[B, 793]`` -> the kernel's float64 genome table ``[B, 793]`` (same offsets).

    Decodes lam -> lambda, s0 -> g0 = sigma(s0), act -> 0/1, Dm and km -> rates; zeroes every row, column and entry
    that belongs to an inactive gene slot, so inactive genes stay exactly 0 whether or not the kernel skips them.
    """
    raw = np.asarray(params, dtype=np.float32)
    if raw.ndim == 1:
        raw = raw[None]
    if raw.shape[-1] != GENOME_SIZE:
        raise ValueError(f"genome rows must have {GENOME_SIZE} entries, got {raw.shape[-1]}")
    if not np.all(np.isfinite(raw)):
        rows = sorted({int(r) for r in np.argwhere(~np.isfinite(raw))[:, 0]})
        raise ValueError(f"genome rows {rows} hold NaN or infinity")
    D = len(_lat.offsets(kind))
    out = raw.astype(np.float64)
    for r in range(out.shape[0]):
        row = out[r]
        act = np.array([1.0 if x > 0.5 else 0.0 for x in genome_view(row, "act")])
        W = genome_view(row, "W").copy()
        W[act == 0, :] = 0.0
        W[:, :G_MAX][:, act == 0] = 0.0
        A = genome_view(row, "A").copy()
        A[:, act == 0] = 0.0
        vals = dict(
            W=W.reshape(-1),
            b=genome_view(row, "b") * act,
            lam=np.array([decode_lambda(x) for x in genome_view(row, "lam")]) * act,
            s0=np.array([sigmoid(x) for x in genome_view(row, "s0")]) * act,
            Q=genome_view(row, "Q") * act,
            act=act,
            A=A.reshape(-1),
            a0=genome_view(row, "a0"),
            Dm=np.array([decode_dm(x, D) for x in genome_view(row, "Dm")]),
            km=np.array([decode_km(x) for x in genome_view(row, "km")]),
        )
        for name, (a, b) in GENOME_SLICES.items():
            row[a:b] = vals[name]
        out[r] = row + 0.0  # turn -0.0 from masking into +0.0
    return np.ascontiguousarray(out)


# ---------------------------------------------------------------------------------------------- program mode
PROGRAM_ROWS = ("alone", "contact", "juvenile", "rim", "zygote")
PROGRAM_SCALARS = ("juv_ticks", "nv_rim", "zyg_row", "flank_gate", "p_div_lo", "k_grow", "timer_step", "prune",
                   "k_keep", "k_die", "Dm0", "Dm1", "km0", "km1")
PROGRAM_DEFAULTS = dict(juv_ticks=0.0, nv_rim=0.0, zyg_row=0.0, flank_gate=0.0, p_div_lo=0.0, k_grow=1e300,
                        timer_step=2.0, prune=0.0, k_keep=1e300, k_die=1e300, Dm0=0.0, Dm1=0.0, km0=0.0, km1=0.0)
PROGRAM_SIZE = len(PROGRAM_ROWS) * P + len(PROGRAM_SCALARS)  # 119
PROGRAM_ROW = {name: i for i, name in enumerate(PROGRAM_ROWS)}
PROGRAM_SCALAR = {name: len(PROGRAM_ROWS) * P + i for i, name in enumerate(PROGRAM_SCALARS)}


def pack_program(contact, alone=None, juvenile=None, rim=None, zygote=None, **scalars) -> np.ndarray:
    """Program-mode organism -> float64 ``[119]``: five decoded phenotype rows (missing rows copy ``contact``)
    followed by the selector and growth scalars (LIFE_ABI.md sections 4.5 and 7.5)."""
    bad = set(scalars) - set(PROGRAM_SCALARS)
    if bad:
        raise KeyError(f"unknown program scalars {sorted(bad)}")
    rows = dict(alone=alone, contact=contact, juvenile=juvenile, rim=rim, zygote=zygote)
    out = np.zeros(PROGRAM_SIZE, dtype=np.float64)
    for name, i in PROGRAM_ROW.items():
        r = np.asarray(contact if rows[name] is None else rows[name], dtype=np.float64)
        if r.shape != (P,):
            raise ValueError(f"program row {name!r} must have {P} knobs")
        out[i * P:(i + 1) * P] = r
    sc = dict(PROGRAM_DEFAULTS)
    sc.update({k: float(v) for k, v in scalars.items()})
    for name, i in PROGRAM_SCALAR.items():
        out[i] = sc[name]
    if not np.all(np.isfinite(out)):
        raise ValueError("a program holds NaN or infinity")
    return out


def pack_init(cells, rows=None) -> tuple[np.ndarray, int]:
    """Explicit initial body: ``[(a, b), ...]`` (+ optional fixed program row per cell, -1 = selector) -> int32
    ``[MAX_INIT, 3]`` and the count. Cell 0 plays the zygote's role (uid index 0)."""
    cells = list(cells)
    if not 1 <= len(cells) <= MAX_INIT:
        raise ValueError(f"an initial body has 1..{MAX_INIT} cells")
    if len(set(map(tuple, cells))) != len(cells):
        raise ValueError("initial cells must sit on distinct sites")
    rows = [-1] * len(cells) if rows is None else list(rows)
    out = np.zeros((MAX_INIT, 3), dtype=np.int32)
    for i, ((a, b), r) in enumerate(zip(cells, rows)):
        out[i] = (a, b, r)
    return out, len(cells)


# ---------------------------------------------------------------------------------------------- lattice table
LATTICE_CODES = dict(hex=0, square4=1, square8=2)


def lattice_tables(kind: str) -> tuple[np.ndarray, np.ndarray]:
    """``(int32 [2 + 6 D], float64 [D, 2])``: code, D, off_a, off_b, back, cyc_prev, cyc_next, rot; unit vectors.

    ``rot`` is the slot permutation of one counter-clockwise lattice rotation (for tests; the kernel ignores it).
    """
    off = _lat.offsets(kind)
    D = len(off)
    cyc = _lat.cyclic_neighbours(kind)
    rot = _lat.slot_map(kind, lambda a, b: _lat.rotate(kind, a, b))
    tab = [LATTICE_CODES[kind], D] + [a for a, _ in off] + [b for _, b in off] + _lat.back_slots(kind)
    tab += [p for p, _ in cyc] + [n for _, n in cyc] + rot
    unit = np.array(_lat.unit_vectors(kind), dtype=np.float64)
    return np.array(tab, dtype=np.int32), np.ascontiguousarray(unit)


# ---------------------------------------------------------------------------------------------- costs and flags
COSTS = dict(c_live=0.02, c_spike=0.004, c_tw=0.004, c_msg=0.001, c_div=0.5, c_sec=0.004)

FLAGS = dict(contacts_off=1 << 0, chem_off=1 << 1, apoptosis_off=1 << 2, division_off=1 << 3, freeze=1 << 4,
             genes_blind=1 << 5, identity_clamp=1 << 6, pheno_fixed=1 << 7, lockstep=1 << 8, program_mode=1 << 9,
             integer_twin=1 << 10)
BASE_ONLY_FLAGS = FLAGS["lockstep"] | FLAGS["program_mode"] | FLAGS["integer_twin"]
UNSUPPORTED_FLAGS = FLAGS["integer_twin"]  # reserved (rejected by every ABI so far)


def flags(*names: str) -> int:
    out = 0
    for n in names:
        out |= FLAGS[n]
    return out


# ---------------------------------------------------------------------------------------------- worlds
@dataclass(frozen=True)
class World:
    """One evaluation world. Times ``t_open``, ``t_fork``, ``kill_t`` and ``stuck_t`` are relative to ``t0``."""
    name: str = "bell_v1"
    stage: str = "v1"
    implemented: bool = True
    lattice: str = "hex"
    lives: int = 3
    T: float = 1024.0
    t0: float = 0.0
    t_open: float = 0.0
    t_fork: float = 0.0
    flags: int = 0
    fork_flags: int = 0
    d_min: float = 0.5
    d0: float = 1.0
    delay_sd: float = 0.1
    jit: float = 0.1
    tau_mis: float = 0.05
    P0: float = 2.0
    clock_sd: float = 0.05
    tick_jit: float = 0.1
    tau_z: float = 2.5
    th: float = 0.6
    th_lo: float = 0.25
    tau_R: float = 6.0
    tau_e: float = 0.5
    h_inc: float = 1.0
    c_live: float = COSTS["c_live"]
    c_spike: float = COSTS["c_spike"]
    c_tw: float = COSTS["c_tw"]
    c_msg: float = COSTS["c_msg"]
    c_div: float = COSTS["c_div"]
    c_sec: float = COSTS["c_sec"]
    n_max: int = 1024
    e_max: int = 5_000_000
    fabric_R: int = 0  # 0 = sparse unbounded fabric; R > 0 = dense disk of radius R (test T12)
    oracle_cap: int = 0  # measurement tool only (heap scheduler); 0 = off
    window_h: float = 0.0  # 0 = heap scheduler; 1/2, 1/4, 1/8 = window scheduler (tests)
    drop_p: float = 0.0
    noise_rate: float = 0.0
    kill_t: float = -1.0
    kill_frac: float = 0.0
    stuck_t: float = -1.0
    stuck_a: int = 0
    stuck_b: int = 0
    kill_rate: float = 0.0  # reserved (v2)
    wound_rate: float = 0.0  # reserved (v2)
    drift_tau: float = 0.0  # reserved (v3)


_META = ("name", "stage", "implemented", "lattice", "lives")
WORLD_KEYS = tuple(f.name for f in fields(World) if f.name not in _META)
WORLD_SIZE = len(WORLD_KEYS)
WORLD_INDEX = {k: i for i, k in enumerate(WORLD_KEYS)}
RESERVED_WORLD_KEYS = ("kill_rate", "wound_rate", "drift_tau")
INT_WORLD_KEYS = ("n_max", "e_max", "fabric_R", "oracle_cap", "stuck_a", "stuck_b")
# world ranges (LIFE_ABI.md 4.7): time stays resolvable at 2^-21 or finer, and no delay or period is below STEP_MIN
TIME_MAX = 2.0 ** 30  # bound on T and |t0|
STEP_MIN = 2.0 ** -10  # smallest d_min and smallest possible tick period
SD_MAX = 1.0  # frozen log-normal spreads (delay_sd, clock_sd)
NOISE_MAX = 1024.0  # membrane-noise kicks per cell per unit
N_MAX_MAX = 2 ** 20  # live-cell guard
INT_FIELD_MAX = 2 ** 30  # fabric_R, oracle_cap, |stuck_a|, |stuck_b|

PRESETS = {
    "bell_v1": World(),
    # v1.5 changes reporting only (no oracle cap anywhere; n_end must sit near the genome's own argmax)
    "bell_v1_5": World(name="bell_v1_5", stage="v1.5"),
    # later stages: parameters recorded here, not implemented by the kernel yet (pack_world refuses them)
    "bell_v2": World(name="bell_v2", stage="v2", implemented=False, kill_rate=1 / 500),
    "bell_v3": World(name="bell_v3", stage="v3", implemented=False, drift_tau=200.0),
}


def world(name: str = "bell_v1", **overrides) -> World:
    return replace(PRESETS[name], **overrides)


def _is_window(h: float, d_min: float) -> bool:
    if h == 0.0:
        return True
    k = round(-math.log2(h)) if h > 0 else 0
    return h > 0 and k >= 1 and h == 2.0 ** -k and h <= d_min


def validate_world(w: World) -> None:
    """The world rules of LIFE_ABI.md 4.7 (the kernel returns -2 for a vector that breaks any of them)."""
    if not w.implemented or any(getattr(w, k) != 0 for k in RESERVED_WORLD_KEYS):
        raise NotImplementedError(f"world {w.name!r} (stage {w.stage}) is not implemented by ABI v{ABI_VERSION}")
    if w.lattice not in LATTICE_CODES:
        raise ValueError(f"unknown lattice {w.lattice!r}")
    bad = [k for k in WORLD_KEYS if not math.isfinite(float(getattr(w, k)))]
    if bad:
        raise ValueError(f"non-finite world values: {bad}")
    if w.T <= 0 or w.T != int(w.T) or w.t0 != int(w.t0):
        raise ValueError("T and t0 must be integers (guards are checked at integer times)")
    if w.T > TIME_MAX or abs(w.t0) > TIME_MAX:
        raise ValueError("T and |t0| must be at most 2^30, so that time keeps a resolution of 2^-21 or finer")
    bad = [k for k in INT_WORLD_KEYS if float(getattr(w, k)) != int(getattr(w, k))]
    if bad:
        raise ValueError(f"integer world values expected: {bad}")
    if not 0 <= w.t_open < w.T:
        raise ValueError("t_open must lie in [0, T)")
    if not _is_window(w.window_h, w.d_min):
        raise ValueError("window_h must be 0 (heap) or 2^-k <= d_min with k >= 1")
    if w.window_h > 0 and w.oracle_cap > 0:
        raise ValueError("the oracle cap reads global counts and is defined for the heap scheduler only")
    for nm in ("flags", "fork_flags"):
        v = getattr(w, nm)
        if v & ~sum(FLAGS.values()) or v & UNSUPPORTED_FLAGS:
            raise ValueError(f"{nm}: unknown or unsupported flag bits {v:#x}")
    if w.fork_flags & BASE_ONLY_FLAGS:
        raise ValueError("lockstep, program_mode and integer_twin can only be base flags")
    if not (w.d_min >= STEP_MIN and w.d0 > 0):
        raise ValueError("d_min >= 2^-10 and d0 > 0 are required")
    if not all(0 <= getattr(w, k) < 1 for k in ("jit", "tau_mis", "tick_jit")):
        raise ValueError("jit, tau_mis and tick_jit must lie in [0, 1)")
    if not (0 <= w.delay_sd <= SD_MAX and 0 <= w.clock_sd <= SD_MAX):
        raise ValueError(f"delay_sd and clock_sd must lie in [0, {SD_MAX}]")
    if not w.P0 > 0 or min_tick_period(w) < STEP_MIN:
        raise ValueError("P0 > 0 and a smallest tick period P0 exp(-6 clock_sd) (1 - tick_jit) >= 2^-10 are required")
    if not (w.tau_z > 0 and w.tau_R > 0 and w.tau_e > 0):
        raise ValueError("tau_z, tau_R and tau_e must be positive")
    if not 0 <= w.th_lo < w.th < 1:
        raise ValueError("0 <= th_lo < th < 1 is required")
    if not all(getattr(w, k) >= 0 for k in ("h_inc", *COSTS)):
        raise ValueError("h_inc and the costs must be non-negative")
    if not (1 <= w.n_max <= N_MAX_MAX and w.e_max >= 0):
        raise ValueError(f"1 <= n_max <= {N_MAX_MAX} and e_max >= 0 are required")
    if not (0 <= w.fabric_R <= INT_FIELD_MAX and 0 <= w.oracle_cap <= INT_FIELD_MAX):
        raise ValueError("fabric_R and oracle_cap must lie in [0, 2^30]")
    if not (0 <= w.drop_p <= 1 and 0 <= w.kill_frac <= 1):
        raise ValueError("drop_p and kill_frac must lie in [0, 1]")
    if not 0 <= w.noise_rate <= NOISE_MAX:
        raise ValueError(f"noise_rate must lie in [0, {NOISE_MAX}]")
    if abs(w.stuck_a) > INT_FIELD_MAX or abs(w.stuck_b) > INT_FIELD_MAX:
        raise ValueError("|stuck_a| and |stuck_b| must be at most 2^30")


def min_tick_period(w: World) -> float:
    """The shortest tick period the clock law allows (frozen normals lie in [-6, 6]; LIFE_ABI.md 4.7)."""
    return w.P0 * math.exp(-6.0 * w.clock_sd) * (1.0 - w.tick_jit)


def pack_world(w) -> np.ndarray:
    """World (or a list of worlds, one per life) -> float64 ``[WORLD_SIZE]`` / ``[B, WORLD_SIZE]``."""
    many = isinstance(w, (list, tuple))
    ws = list(w) if many else [w]
    out = np.zeros((len(ws), WORLD_SIZE), dtype=np.float64)
    for i, x in enumerate(ws):
        validate_world(x)
        out[i] = [float(getattr(x, k)) for k in WORLD_KEYS]
    return out if many else out[0]


# ---------------------------------------------------------------------------------------------- outputs
LEDGER = ("income", "live_time", "sec_int", "spikes", "kappa_sum", "contact_events", "claims", "births", "rejects",
          "rejects_wall", "deaths", "kills", "cost", "guard_charge", "net", "F", "n_end", "n_peak", "t_end",
          "status", "events", "beats", "P_int", "arrivals", "arrivals_dropped", "packets", "morph_secreted",
          "morph_decayed", "morph_lost", "morph_content_end", "morph_inflight_end", "chem_clamps", "last_birth",
          "ticks", "t_ext")
L = {name: i for i, name in enumerate(LEDGER)}
LEDGER_SIZE = len(LEDGER)

STATUS = dict(extinct=1 << 0, guard_cells=1 << 1, guard_events=1 << 2, raster_overflow=1 << 3,
              fate_overflow=1 << 4, chem_clamp=1 << 5, ledger_mismatch=1 << 6, capacity=1 << 7, wall=1 << 8)
HASHES = ("all", "spikes", "fate", "chem")
HASH_SIZE = len(HASHES)

FATE_KINDS = dict(birth=1, death=2, reject=3)
DEATH_CAUSES = dict(apoptosis=1, prune=2, kill=3)
FATE_I = ("kind", "uid", "mother", "a", "b", "aux")  # aux: birth index k | death cause | reject: 1 = wall
FATE_F = ("t", "age") + tuple(f"g{k}" for k in range(G_MAX))
FATE_I_SIZE, FATE_F_SIZE = len(FATE_I), len(FATE_F)

SIZES = dict(abi=ABI_VERSION, genome=GENOME_SIZE, program=PROGRAM_SIZE, world=WORLD_SIZE, ledger=LEDGER_SIZE,
             hashes=HASH_SIZE, knobs=P, max_init=MAX_INIT, fate_i=FATE_I_SIZE, fate_f=FATE_F_SIZE)


def column_cost(led, w: World | None = None) -> np.ndarray:
    """Sum of per-action costs rebuilt from ledger columns (the left-to-right order of LIFE_ABI.md 9.5)."""
    w = w or PRESETS["bell_v1"]
    led = np.asarray(led, dtype=np.float64)
    c = w.c_live * led[..., L["live_time"]]
    c = c + w.c_spike * led[..., L["spikes"]]
    c = c + w.c_tw * led[..., L["kappa_sum"]]
    c = c + w.c_msg * led[..., L["contact_events"]]
    c = c + w.c_div * led[..., L["claims"]]
    return c + w.c_sec * led[..., L["sec_int"]]


def guard_charge(led, w: World | None = None) -> np.ndarray:
    """c_live N_max (t0 + T - t_end) for lives ended by a guard, else 0."""
    w = w or PRESETS["bell_v1"]
    led = np.asarray(led, dtype=np.float64)
    tripped = (led[..., L["status"]].astype(np.int64) & (STATUS["guard_cells"] | STATUS["guard_events"])) != 0
    return np.where(tripped, w.c_live * w.n_max * (w.t0 + w.T - led[..., L["t_end"]]), 0.0)


def fitness(led, w: World | None = None) -> np.ndarray:
    """F from ledger columns under the costs of ``w`` (re-pricing a finished life with another cost table)."""
    w = w or PRESETS["bell_v1"]
    led = np.asarray(led, dtype=np.float64)
    net = led[..., L["income"]] - column_cost(led, w) - guard_charge(led, w)
    return net / (w.T - w.t_open)
