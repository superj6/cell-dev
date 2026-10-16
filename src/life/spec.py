"""The one-life contract: constants, hashing, phenotype decode, costs, world presets and kernel packing.

This module is the Python mirror of ``docs/LIFE_ABI.md``. The C kernel and the Python reference both implement that
document; every function here that computes a model quantity (hash draws, knob decode, gene-rate decode, the CATCH
world's closed forms) uses the same IEEE-754 float64 operations in the same order, so results agree bitwise on the
same libm.

Four caller ABIs coexist; the C kernel implements ABI 5:
- ``V2`` is ABI 2 (BELL-1 on 2D lattices).
- ``V3`` is ABI 3: BELL-1 plus BODY-1 v1 (the CATCH world, 3D prism lattices,
  receptors, plane cues).
- ``V4`` adds flash and renewal target visibility and a low-light capture readout, with unchanged cell rules.
- ``V5`` adds delayed cue matching, retaining the same genome, inputs and local cell rules.
``CURRENT`` remains the legacy caller default, ABI 2. Every module-level layout name (``GENOME_SIZE``,
``pack_world``, ``LEDGER``, ...) belongs to that default. Visibility and delayed matching require explicit ``V4``
and ``V5`` respectively; existing callers retain their earlier shapes and behavior.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields, replace

import numpy as np

from src import lattice as _lat

# ---------------------------------------------------------------------------------------------------------- dims
G_MAX = 16  # gene slots
G_INIT = 8  # active gene slots at initialization
M = 2  # morphogens
C = 2  # spike channels

P_MAX = 3.0  # tick-interval bound used by the D_m decode (1.5 x the reference P0 = 2)
CHEM_SHIP_MAX = 0.9  # a tick never ships more than this fraction of its morphogen
V_FLOOR = -2.0  # membrane register floor
Q10 = 1024.0  # membrane register resolution (2^10 steps per unit)
SHAT_EPS = 1e-6  # directional-gain normalizer
PLACE_NOISE = 1e-3  # weight of the hash term in division placement
EMPTY = 0  # uid of "no cell" in a view (real uids are odd)

# ---------------------------------------------------------------------------------------------------------- hash
MASK64 = (1 << 64) - 1
TWO_M53 = 2.0 ** -53

# draw streams: hash64(seed, stream, *keys); the keys of each stream are listed in LIFE_ABI.md section 3
S_ZYG, S_UID, S_TAU, S_CLK, S_PHASE, S_DC, S_JIT, S_DROP, S_TICK = 1, 2, 3, 4, 5, 6, 7, 8, 9
S_DIE, S_DIV, S_PLACE, S_NOISE, S_NSIGN, S_KILL, S_TIE, S_ORDER = 10, 11, 12, 13, 14, 15, 16, 17
# ABI 3 (the CATCH world): receptor candidates and their thinning, blob turns, headings, timer respawns, placements
S_RCAND, S_RACC, S_TURN, S_HEAD, S_RTIME, S_PANG, S_PDIST, S_PPRES = 18, 19, 20, 21, 22, 23, 24, 25
STREAMS_V2 = dict(zyg=S_ZYG, uid=S_UID, tau=S_TAU, clk=S_CLK, phase=S_PHASE, dc=S_DC, jit=S_JIT, drop=S_DROP,
                  tick=S_TICK, die=S_DIE, div=S_DIV, place=S_PLACE, noise=S_NOISE, nsign=S_NSIGN, kill=S_KILL,
                  tie=S_TIE, order=S_ORDER)
STREAMS_V3 = dict(STREAMS_V2, rcand=S_RCAND, racc=S_RACC, turn=S_TURN, head=S_HEAD, rtime=S_RTIME, pang=S_PANG,
                  pdist=S_PDIST, ppres=S_PPRES)
S_VISIBILITY = 26
STREAMS_V4 = dict(STREAMS_V3, visibility=S_VISIBILITY)
S_TASK_CLASS, S_TASK_DURATION, S_TASK_GEOMETRY, S_TASK_SIDE = 27, 28, 29, 30
STREAMS_V5 = dict(STREAMS_V4, task_class=S_TASK_CLASS, task_duration=S_TASK_DURATION,
                  task_geometry=S_TASK_GEOMETRY, task_side=S_TASK_SIDE)
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


Z_SHIFT = 56  # ABI 3: a site's height z is XORed into bits 56-59 of its key
L_MAX_MAX = 8  # ABI 3: largest stack height (planes z = 0 .. L_max - 1)
COORD_MAX_3D = 2 ** 22  # ABI 3: |a| and |b| of an initial cell, so every reachable |a| < 2^24 and keys stay injective


def sitekey(a: int, b: int, z: int = 0) -> int:
    """64-bit key of integer site coordinates: (uint32(a) << 32 | uint32(b)) XOR (z << 56).

    z = 0 gives the ABI-2 key exactly. For |a| < 2^24 bits 56-63 of uint32(a) << 32 are copies of a's sign, so with
    0 <= z < 16 the key is injective (LIFE_ABI.md 3)."""
    return (((a & 0xFFFFFFFF) << 32) | (b & 0xFFFFFFFF)) ^ ((z & 0xF) << Z_SHIFT)


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
KNOBS_V2 = ("w0", "w1", "b", "tau_m", "t_ref", "emit0", "emit1", "delta", "kappa", "p_div", "asym", "p_die", "phi",
            "sec0", "sec1", "pol0", "pol1", "tau_tr", "a0", "a1", "chi")
KNOBS_V3 = KNOBS_V2 + ("zeta", "g_r")  # ABI 3: vertical placement weight, receptor gain (modality 0, signed)

TAU_M = (1.0, 2.0, 4.0, 8.0, 16.0)
T_REF = tuple(0.5 * k for k in range(1, 9))
DELTA = (0.0, 0.5, 1.0, 2.0)
KAPPA = (0.0, 0.25, 0.5, 1.0)
PHI = (0.0, 0.5, 1.0, 2.0)
TAU_TR = (2.0, 4.0, 8.0, 16.0)
P_FATE = (0.0,) + tuple(2.0 ** (k - 8) for k in range(1, 9))
Q8_GRID = tuple(k / 8 for k in range(-16, 17))
GRIDS_V3 = dict(w0=Q8_GRID, w1=Q8_GRID, b=Q8_GRID, tau_m=TAU_M, t_ref=T_REF, emit0=(0.0, 1.0), emit1=(0.0, 1.0),
                delta=DELTA, kappa=KAPPA, p_div=P_FATE, p_die=P_FATE, phi=PHI, pol0=Q8_GRID, pol1=Q8_GRID,
                tau_tr=TAU_TR, a0=Q8_GRID, a1=Q8_GRID, chi=Q8_GRID, zeta=Q8_GRID, g_r=Q8_GRID)
RANGES = dict(asym=(0.0, 1.0), sec0=(0.0, 0.5), sec1=(0.0, 0.5))  # continuous knobs

# gene-network inputs x (LIFE_ABI.md 7.4 step 3); ABI 3 appends the receptor trace and the two plane cues
INPUTS_V2 = tuple(f"g{k}" for k in range(G_MAX)) + ("m0", "m1", "f", "r0", "r1", "n_view")
INPUTS_V3 = INPUTS_V2 + ("rho", "is_S", "is_M")


def _level(table, y: float) -> float:  # 4-level knobs: index clip(round(2y), 0, 3)
    return table[int(clip(rint(2.0 * y), 0.0, 3.0))]


def _fate(y: float) -> float:
    k = int(clip(rint(4.0 * y), 0.0, 8.0))
    return 0.0 if k == 0 else 2.0 ** (k - 8)


def _decode21(y: list[float]) -> list[float]:
    """The 21 knobs of ABI 2 (LIFE_ABI.md section 8, rows 0-20)."""
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


def _genome_fields(nin: int, p: int) -> tuple[GField, ...]:
    return (
        GField("W", (G_MAX, nin), "reg", "row"),
        GField("b", (G_MAX,), "reg", "elem"),
        GField("lam", (G_MAX,), "reg", "elem"),
        GField("s0", (G_MAX,), "reg", "elem"),
        GField("Q", (G_MAX,), "reg", "elem"),
        GField("act", (G_MAX,), "reg", "elem"),
        GField("A", (p, G_MAX), "pheno", "col"),
        GField("a0", (p,), "pheno", "global"),
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


PACKED_NAMES = dict(W="W", b="b", lam="lam", s0="g0", Q="Q", act="act", A="A", a0="a0", Dm="Dm", km="km")

# ---------------------------------------------------------------------------------------------- program mode
PROGRAM_ROWS = ("alone", "contact", "juvenile", "rim", "zygote")
PROGRAM_SCALARS = ("juv_ticks", "nv_rim", "zyg_row", "flank_gate", "p_div_lo", "k_grow", "timer_step", "prune",
                   "k_keep", "k_die", "Dm0", "Dm1", "km0", "km1")
PROGRAM_DEFAULTS = dict(juv_ticks=0.0, nv_rim=0.0, zyg_row=0.0, flank_gate=0.0, p_div_lo=0.0, k_grow=1e300,
                        timer_step=2.0, prune=0.0, k_keep=1e300, k_die=1e300, Dm0=0.0, Dm1=0.0, km0=0.0, km1=0.0)

# ---------------------------------------------------------------------------------------------- costs and flags
COSTS = dict(c_live=0.02, c_spike=0.004, c_tw=0.004, c_msg=0.001, c_div=0.5, c_sec=0.004)

FLAGS_V2 = dict(contacts_off=1 << 0, chem_off=1 << 1, apoptosis_off=1 << 2, division_off=1 << 3, freeze=1 << 4,
                genes_blind=1 << 5, identity_clamp=1 << 6, pheno_fixed=1 << 7, lockstep=1 << 8, program_mode=1 << 9,
                integer_twin=1 << 10)
# ABI 3 forks (LIFE_ABI.md 12): in-plane spikes undelivered, hidden cells' spikes undelivered, no receptor deliveries,
# no world effect of act-plane twitches
FLAGS_V3 = dict(FLAGS_V2, lateral_off=1 << 11, hidden_off=1 << 12, receptor_off=1 << 13, motor_off=1 << 14)

# ---------------------------------------------------------------------------------------------- worlds
WORLD_KINDS = dict(bell=0, catch=1)


@dataclass(frozen=True)
class World:
    """One evaluation world. Times ``t_open``, ``t_fork``, ``kill_t`` and ``stuck_t`` are relative to ``t0``.

    The fields after ``drift_tau`` are ABI 3's (LIFE_ABI.md 4.7): the world kind, the stack height, and the CATCH
    world's keys. Their defaults are the CATCH v1 values (BODY_DESIGN_PROPOSAL.md 3.1); a BELL world ignores them."""
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
    # ---- ABI 3
    world_kind: int = 0  # 0 = BELL-1 lumen, 1 = CATCH (BODY-1 v1)
    L_max: int = 1  # stack height: sites exist for 0 <= z < L_max (z = 0 sense plane, 1 act plane, 2+ hidden)
    stuck_z: int = 0  # panel: height of the stuck site
    sigma: float = 1.5  # target halo width
    lam_s: float = 2.0  # receptor event rate added at the halo's centre, per sense cell per unit
    lam_bg: float = 0.05  # background receptor event rate (sensor noise)
    g_n: float = 1.0  # nudge gain: force per unit of twitch per unit of exposed face
    drag_exp: float = 0.5  # drag gamma = n_fill ** drag_exp (n_fill: the filled footprint, filled_footprint)
    th_click: float = 0.6  # the hotspot clicks when its twitch crosses this upward while the key is armed
    th_rel: float = 0.25  # the key re-arms when the hotspot's twitch is below this
    rho_c: float = 1.0  # capture radius
    v_t: float = 0.1  # blob speed (run and tumble)
    tau_turn: float = 20.0  # mean time between turns (0 = never turns)
    R_min: float = 2.0  # placement distance from the dot: U[R_min, R_max]
    R_max: float = 6.0
    t_resp: float = 50.0  # mean time between timer re-placements (0 = no timer)
    R_cap: float = 100.0  # income per capture
    c_miss: float = 2.0  # cost per click that hits no blob (tweak: the proposal's 1 let blind clicking pay; 15.60)
    c_rec: float = 0.001  # cost per delivered receptor event per unit of |g_r|
    b2_amp: float = 0.0  # second blob (S1 candidates): luminance relative to the target; 0 = no second blob
    b2_sigma: float = 1.5
    b2_value: float = 0.0  # click value: income if > 0, cost if < 0
    b2_rho: float = 1.0
    b2_p: float = 1.0  # probability that the second blob is present after a placement
    b2_mode: int = 0  # 0 = placed with the target; 1 = its own timer and its own re-placement after a click
    # ---- ABI 4: target visibility; these world states are never cell inputs.
    visibility_mode: int = 0  # 0 steady, 1 flash after placement, 2 alternating exponential intervals
    visibility_on: float = 0.0  # flash bright duration or mean renewal bright duration
    visibility_off: float = 0.0  # mean renewal low-light duration
    visibility_low: float = 1.0  # target-rate multiplier during low light; background stays unchanged
    # ---- ABI 5: delayed matching; all state remains external to the cells.
    task_mode: int = 0  # 0 legacy, 1 delayed matching by cue width
    sample_min: float = 0.0
    sample_max: float = 0.0
    blank_min: float = 0.0
    blank_max: float = 0.0
    choice_T: float = 0.0
    reset_T: float = 0.0


_META = ("name", "stage", "implemented", "lattice", "lives")
ALL_WORLD_KEYS = tuple(f.name for f in fields(World) if f.name not in _META)
WORLD_KEYS_V3_NEW = ALL_WORLD_KEYS[ALL_WORLD_KEYS.index("world_kind"):ALL_WORLD_KEYS.index("visibility_mode")]
WORLD_KEYS_V2 = ALL_WORLD_KEYS[:ALL_WORLD_KEYS.index("world_kind")]
WORLD_KEYS_V3 = WORLD_KEYS_V2 + WORLD_KEYS_V3_NEW
WORLD_KEYS_V4 = ALL_WORLD_KEYS[:ALL_WORLD_KEYS.index("task_mode")]
WORLD_KEYS_V5 = ALL_WORLD_KEYS
RESERVED_WORLD_KEYS = ("kill_rate", "wound_rate", "drift_tau")
INT_WORLD_KEYS = ("n_max", "e_max", "fabric_R", "oracle_cap", "stuck_a", "stuck_b", "world_kind", "L_max", "stuck_z",
                  "b2_mode", "visibility_mode", "task_mode")
# world ranges (LIFE_ABI.md 4.7): time stays resolvable at 2^-21 or finer, and no delay or period is below STEP_MIN
TIME_MAX = 2.0 ** 30  # bound on T and |t0|
STEP_MIN = 2.0 ** -10  # smallest d_min and smallest possible tick period
SD_MAX = 1.0  # frozen log-normal spreads (delay_sd, clock_sd)
NOISE_MAX = 1024.0  # membrane-noise kicks per cell per unit
N_MAX_MAX = 2 ** 20  # live-cell guard
INT_FIELD_MAX = 2 ** 30  # fabric_R, oracle_cap, |stuck_a|, |stuck_b|
RATE_MAX = 1024.0  # ABI 3: receptor candidates per sense cell per unit (lambda_max)
SPEED_MAX = 1024.0  # ABI 3: g_n and v_t, so the dot and the blobs stay far from overflow within T <= 2^30
LENGTH_MAX = 2.0 ** 20  # ABI 3: sigma, b2_sigma and R_max

PRESETS = {
    "bell_v1": World(),
    # v1.5 changes reporting only (no oracle cap anywhere; n_end must sit near the genome's own argmax)
    "bell_v1_5": World(name="bell_v1_5", stage="v1.5"),
    # later stages: parameters recorded here, not implemented by the kernel yet (pack_world refuses them)
    "bell_v2": World(name="bell_v2", stage="v2", implemented=False, kill_rate=1 / 500),
    "bell_v3": World(name="bell_v3", stage="v3", implemented=False, drift_tau=200.0),
    # BODY-1 v1 (BODY_DESIGN_PROPOSAL.md 3.1, approved): the dot is the body; L_max 4 is the user's design (two
    # hidden planes above the act plane) and L_max 2 the control arm. ABI 3 only. Recorded tweaks (LIFE_ABI.md 15.59-
    # 15.61): the World default c_miss is 2, and the kernel's drag counts every occupied column plus the tiles they
    # enclose (the filled footprint).
    "catch_v1": World(name="catch_v1", stage="body-s0", lattice="hexprism", world_kind=1, L_max=4),
    "catch_v1_l4": World(name="catch_v1_l4", stage="body-s0", lattice="hexprism", world_kind=1, L_max=4),
    "catch_v1_l2": World(name="catch_v1_l2", stage="body-s0", lattice="hexprism", world_kind=1, L_max=2),
    # SPECK, the S1 candidate (BODY_DESIGN_PROPOSAL.md 8, "interior blindness", measured by the S1 prototype study):
    # catch_v1 with a small target halo (sigma 0.6) worth five times as much (R_cap 500) and a miss priced five times
    # as much (c_miss 10, so a blind click breaks even at v1's capture rate, 2 / 102; at c_miss 2 a blind presser beat
    # the lone zygote, GS6, LIFE_ABI.md 15.62); every other key and the recorded tweaks are catch_v1's. Gates GS1-GS6
    # (docs/LIFE_GATES.md) test it in the kernel; the _l4 / _l2 names mirror the catch_v1 arms.
    "catch_speck": World(name="catch_speck", stage="body-s1", lattice="hexprism", world_kind=1, L_max=4, sigma=0.6,
                         R_cap=500.0, c_miss=10.0),
    "catch_speck_l4": World(name="catch_speck_l4", stage="body-s1", lattice="hexprism", world_kind=1, L_max=4,
                            sigma=0.6, R_cap=500.0, c_miss=10.0),
    "catch_speck_l2": World(name="catch_speck_l2", stage="body-s1", lattice="hexprism", world_kind=1, L_max=2,
                            sigma=0.6, R_cap=500.0, c_miss=10.0),
}


for _name, _visibility in {
    "catch_speck_flash5_dim25_l4": dict(visibility_mode=1, visibility_on=5.0, visibility_low=0.25),
    "catch_speck_blink20_20_l4": dict(visibility_mode=2, visibility_on=20.0, visibility_off=20.0,
                                    visibility_low=0.0),
}.items():
    PRESETS[_name] = replace(PRESETS["catch_speck_l4"], name=_name, stage="visibility-v4", **_visibility)

PRESETS["catch_delayed_match_l4"] = replace(
    PRESETS["catch_speck_l4"], name="catch_delayed_match_l4", stage="delayed-match-v5", task_mode=1,
    sample_min=15.0, sample_max=25.0, blank_min=20.0, blank_max=40.0, choice_T=50.0, reset_T=5.0,
    v_t=0.0, tau_turn=0.0, t_resp=0.0, b2_amp=1.0, b2_p=1.0, b2_mode=0,
    b2_sigma=1.2, b2_value=-50.0, b2_rho=1.0, R_min=2.0, R_max=4.0)


def world(name: str = "bell_v1", **overrides) -> World:
    return replace(PRESETS[name], **overrides)


def _is_window(h: float, d_min: float) -> bool:
    if h == 0.0:
        return True
    k = round(-math.log2(h)) if h > 0 else 0
    return h > 0 and k >= 1 and h == 2.0 ** -k and h <= d_min


def min_tick_period(w: World) -> float:
    """The shortest tick period the clock law allows (frozen normals lie in [-6, 6]; LIFE_ABI.md 4.7)."""
    return w.P0 * math.exp(-6.0 * w.clock_sd) * (1.0 - w.tick_jit)


# ---------------------------------------------------------------------------------------------- outputs
LEDGER_V2 = ("income", "live_time", "sec_int", "spikes", "kappa_sum", "contact_events", "claims", "births",
             "rejects", "rejects_wall", "deaths", "kills", "cost", "guard_charge", "net", "F", "n_end", "n_peak",
             "t_end", "status", "events", "beats", "P_int", "arrivals", "arrivals_dropped", "packets",
             "morph_secreted", "morph_decayed", "morph_lost", "morph_content_end", "morph_inflight_end",
             "chem_clamps", "last_birth", "ticks", "t_ext")
# ABI 3 appends the CATCH world's columns and the per-plane cell counts (LIFE_ABI.md 4.9)
LEDGER_V3 = LEDGER_V2 + ("captures", "misses", "clicks", "b2_clicks", "respawns", "nudges", "rec_cand",
                         "rec_accept", "rec_events", "rec_gain", "samples", "dist_sum", "zone_samples", "path",
                         "X_end", "Y_end", "n_S_end", "n_M_end", "n_H_end", "live_S", "live_M", "live_H")

STATUS = dict(extinct=1 << 0, guard_cells=1 << 1, guard_events=1 << 2, raster_overflow=1 << 3,
              fate_overflow=1 << 4, chem_clamp=1 << 5, ledger_mismatch=1 << 6, capacity=1 << 7, wall=1 << 8)
LEDGER_V4 = LEDGER_V3 + ("low_light_captures",)
TASK_LEDGER = tuple(f"{metric}_{cls}" for metric in (
    "choice_opportunities", "choice_carry_in", "correct_choices", "wrong_choices", "choice_timeouts",
    "unfinished_choices") for cls in ("narrow", "broad"))
LEDGER_V5 = LEDGER_V4 + TASK_LEDGER

HASHES_V2 = ("all", "spikes", "fate", "chem")
HASHES_V3 = HASHES_V2 + ("world",)

FATE_KINDS = dict(birth=1, death=2, reject=3)
DEATH_CAUSES = dict(apoptosis=1, prune=2, kill=3)
FATE_I_V2 = ("kind", "uid", "mother", "a", "b", "aux")  # aux: birth index k | death cause | reject: 1 = wall
FATE_I_V3 = FATE_I_V2 + ("z",)
FATE_F = ("t", "age") + tuple(f"g{k}" for k in range(G_MAX))
FATE_F_SIZE = len(FATE_F)

LATTICE_CODES_V2 = dict(hex=0, square4=1, square8=2)
LATTICE_CODES_V3 = dict(LATTICE_CODES_V2, hexprism=3, square4prism=4, square8prism=5)


# ========================================================================================================= the ABIs
class Abi:
    """Every constant, layout and packing function of one kernel ABI (2, 3 or 4) of docs/LIFE_ABI.md.

    ABI 3 is ABI 2 with appended entries everywhere: knobs (zeta, g_r), gene inputs (rho, is_S, is_M), world keys,
    ledger columns, a fifth hash family, a z column in the fate log and in initial bodies, and the prism lattices.
    Every ABI-2 quantity keeps its index, so a padded ABI-2 genome or program reads the same values (``pad_genomes``,
    ``pad_program``)."""

    def __init__(self, version: int):
        if version not in (2, 3, 4, 5):
            raise ValueError(f"unknown ABI {version}")
        v3 = version >= 3
        self.version = version
        self.S = 1 if v3 else 0  # receptor modalities
        self.KNOBS = KNOBS_V3 if v3 else KNOBS_V2
        self.P = len(self.KNOBS)
        self.K = {name: i for i, name in enumerate(self.KNOBS)}
        self.GRIDS = {k: v for k, v in GRIDS_V3.items() if k in self.K}  # knobs on a grid; RANGES: continuous ones
        self.INPUTS = INPUTS_V3 if v3 else INPUTS_V2
        self.NIN = len(self.INPUTS)
        self.GENOME_FIELDS = _genome_fields(self.NIN, self.P)
        self.GENOME_SLICES = _slices(self.GENOME_FIELDS)
        self.GENOME_SIZE = max(b for _, b in self.GENOME_SLICES.values())
        self.PROGRAM_SIZE = len(PROGRAM_ROWS) * self.P + len(PROGRAM_SCALARS)
        self.PROGRAM_ROW = {name: i for i, name in enumerate(PROGRAM_ROWS)}
        self.PROGRAM_SCALAR = {name: len(PROGRAM_ROWS) * self.P + i for i, name in enumerate(PROGRAM_SCALARS)}
        self.MAX_INIT = 1024 if v3 else 64
        self.INIT_COLS = 4 if v3 else 3  # (a, b, row) | (a, b, z, row)
        self.LATTICE_CODES = LATTICE_CODES_V3 if v3 else LATTICE_CODES_V2
        self.FLAGS = FLAGS_V3 if v3 else FLAGS_V2
        self.BASE_ONLY_FLAGS = self.FLAGS["lockstep"] | self.FLAGS["program_mode"] | self.FLAGS["integer_twin"]
        self.UNSUPPORTED_FLAGS = self.FLAGS["integer_twin"]  # reserved (rejected by every ABI so far)
        self.STREAMS = (STREAMS_V5 if version >= 5 else
                        STREAMS_V4 if version >= 4 else STREAMS_V3 if v3 else STREAMS_V2)
        self.WORLD_KEYS = (WORLD_KEYS_V5 if version >= 5 else
                           WORLD_KEYS_V4 if version >= 4 else WORLD_KEYS_V3 if v3 else WORLD_KEYS_V2)
        self.WORLD_SIZE = len(self.WORLD_KEYS)
        self.WORLD_INDEX = {k: i for i, k in enumerate(self.WORLD_KEYS)}
        self.LEDGER = LEDGER_V5 if version >= 5 else LEDGER_V4 if version >= 4 else LEDGER_V3 if v3 else LEDGER_V2
        self.L = {name: i for i, name in enumerate(self.LEDGER)}
        self.LEDGER_SIZE = len(self.LEDGER)
        self.HASHES = HASHES_V3 if v3 else HASHES_V2
        self.HASH_SIZE = len(self.HASHES)
        self.FATE_I = FATE_I_V3 if v3 else FATE_I_V2
        self.FATE_I_SIZE = len(self.FATE_I)
        self.FATE_F_SIZE = FATE_F_SIZE
        self.SIZES = dict(abi=version, genome=self.GENOME_SIZE, program=self.PROGRAM_SIZE, world=self.WORLD_SIZE,
                          ledger=self.LEDGER_SIZE, hashes=self.HASH_SIZE, knobs=self.P, max_init=self.MAX_INIT,
                          fate_i=self.FATE_I_SIZE, fate_f=self.FATE_F_SIZE)

    def __repr__(self) -> str:
        return f"Abi({self.version})"

    # ------------------------------------------------------------------------------------------ phenotype
    def decode_knobs(self, y) -> list[float]:
        """theta = decode(y) for the readout values y = A.g + a0 (LIFE_ABI.md section 8)."""
        y = [float(v) for v in y]
        out = _decode21(y)
        if self.version >= 3:
            out += [q8(y[21]), q8(y[22])]  # zeta, g_r
        return out

    def readout(self, gt_row, g) -> list[float]:
        """y_p = a0[p] + sum_k A[p][k] g[k], accumulated left to right over k = 0..15 (packed genome table row)."""
        A = gt_row[self.GENOME_SLICES["A"][0]:self.GENOME_SLICES["A"][1]]
        a0 = gt_row[self.GENOME_SLICES["a0"][0]:self.GENOME_SLICES["a0"][1]]
        out = []
        for p in range(self.P):
            y = float(a0[p])
            for k in range(G_MAX):
                y = y + float(A[p * G_MAX + k]) * float(g[k])
            out.append(y)
        return out

    def phenotype(self, gt_row, g) -> list[float]:
        return self.decode_knobs(self.readout(gt_row, g))

    def theta(self, **knobs) -> np.ndarray:
        """A decoded phenotype vector by knob name (program mode); unnamed knobs take neutral defaults."""
        th = dict(w0=0.0, w1=0.0, b=0.0, tau_m=1.0, t_ref=0.5, emit0=0.0, emit1=0.0, delta=0.0, kappa=0.0,
                  p_div=0.0, asym=0.0, p_die=0.0, phi=0.0, sec0=0.0, sec1=0.0, pol0=0.0, pol1=0.0, tau_tr=2.0,
                  a0=0.0, a1=0.0, chi=0.0)
        if self.version >= 3:
            th.update(zeta=0.0, g_r=0.0)
        bad = set(knobs) - set(th)
        if bad:
            raise KeyError(f"unknown knobs {sorted(bad)}")
        th.update({k: float(v) for k, v in knobs.items()})
        return np.array([th[k] for k in self.KNOBS], dtype=np.float64)

    # ------------------------------------------------------------------------------------------ genomes
    def genome_view(self, params, name: str) -> np.ndarray:
        """Named field of genome rows ``[..., GENOME_SIZE]`` with its natural shape."""
        a, b = self.GENOME_SLICES[name]
        shape = next(f.shape for f in self.GENOME_FIELDS if f.name == name)
        params = np.asarray(params)
        return params[..., a:b].reshape(*params.shape[:-1], *shape)

    def lattice_degree(self, kind: str) -> int:
        """D, the number of slots of a lattice kind (8 on hexprism: 6 in-plane, up, down)."""
        if kind not in self.LATTICE_CODES:
            raise ValueError(f"lattice {kind!r} is not part of ABI {self.version}")
        return len(_lat.offsets3(kind))

    def pack_genomes(self, params, kind: str = "hex") -> np.ndarray:
        """Raw float32 genomes ``[B, GENOME_SIZE]`` -> the kernel's float64 genome table (same offsets).

        Decodes lam -> lambda, s0 -> g0 = sigma(s0), act -> 0/1, Dm and km -> rates; zeroes every row, column and
        entry that belongs to an inactive gene slot, so inactive genes stay exactly 0 whether or not the kernel skips
        them.
        """
        raw = np.asarray(params, dtype=np.float32)
        if raw.ndim == 1:
            raw = raw[None]
        if raw.shape[-1] != self.GENOME_SIZE:
            raise ValueError(f"genome rows must have {self.GENOME_SIZE} entries, got {raw.shape[-1]}")
        if not np.all(np.isfinite(raw)):
            rows = sorted({int(r) for r in np.argwhere(~np.isfinite(raw))[:, 0]})
            raise ValueError(f"genome rows {rows} hold NaN or infinity")
        D = self.lattice_degree(kind)
        view = self.genome_view
        out = raw.astype(np.float64)
        for r in range(out.shape[0]):
            row = out[r]
            act = np.array([1.0 if x > 0.5 else 0.0 for x in view(row, "act")])
            W = view(row, "W").copy()
            W[act == 0, :] = 0.0
            W[:, :G_MAX][:, act == 0] = 0.0
            A = view(row, "A").copy()
            A[:, act == 0] = 0.0
            vals = dict(
                W=W.reshape(-1),
                b=view(row, "b") * act,
                lam=np.array([decode_lambda(x) for x in view(row, "lam")]) * act,
                s0=np.array([sigmoid(x) for x in view(row, "s0")]) * act,
                Q=view(row, "Q") * act,
                act=act,
                A=A.reshape(-1),
                a0=view(row, "a0"),
                Dm=np.array([decode_dm(x, D) for x in view(row, "Dm")]),
                km=np.array([decode_km(x) for x in view(row, "km")]),
            )
            for name, (a, b) in self.GENOME_SLICES.items():
                row[a:b] = vals[name]
            out[r] = row + 0.0  # turn -0.0 from masking into +0.0
        return np.ascontiguousarray(out)

    def pad_genomes(self, params, src: Abi) -> np.ndarray:
        """Embed raw genome rows of an older ABI into this one neutrally (LIFE_ABI.md 4.4): every field keeps its
        entries at their (row, column) places and every new entry is 0. Works on raw and on packed rows."""
        x = np.asarray(params)
        lead = x.shape[:-1]
        if x.shape[-1] != src.GENOME_SIZE or src.version > self.version:
            raise ValueError(f"cannot pad ABI {src.version} rows of {x.shape[-1]} entries into ABI {self.version}")
        parts = []
        for f, g in zip(src.GENOME_FIELDS, self.GENOME_FIELDS):
            out = np.zeros((*lead, *g.shape), dtype=x.dtype)
            out[(..., *[slice(0, n) for n in f.shape])] = src.genome_view(x, f.name)
            parts.append(out.reshape(*lead, -1))
        return np.concatenate(parts, axis=-1)

    # ------------------------------------------------------------------------------------------ programs
    def pack_program(self, contact, alone=None, juvenile=None, rim=None, zygote=None, **scalars) -> np.ndarray:
        """Program-mode organism -> float64 ``[PROGRAM_SIZE]``: five decoded phenotype rows (missing rows copy
        ``contact``) followed by the selector and growth scalars (LIFE_ABI.md sections 4.5 and 7.5)."""
        bad = set(scalars) - set(PROGRAM_SCALARS)
        if bad:
            raise KeyError(f"unknown program scalars {sorted(bad)}")
        rows = dict(alone=alone, contact=contact, juvenile=juvenile, rim=rim, zygote=zygote)
        out = np.zeros(self.PROGRAM_SIZE, dtype=np.float64)
        P = self.P
        for name, i in self.PROGRAM_ROW.items():
            r = np.asarray(contact if rows[name] is None else rows[name], dtype=np.float64)
            if r.shape != (P,):
                raise ValueError(f"program row {name!r} must have {P} knobs")
            out[i * P:(i + 1) * P] = r
        sc = dict(PROGRAM_DEFAULTS)
        sc.update({k: float(v) for k, v in scalars.items()})
        for name, i in self.PROGRAM_SCALAR.items():
            out[i] = sc[name]
        if not np.all(np.isfinite(out)):
            raise ValueError("a program holds NaN or infinity")
        return out

    def pad_program(self, prog, src: Abi) -> np.ndarray:
        """An older ABI's program table row -> this ABI's: every row gains the new knobs at 0 (zeta = g_r = 0)."""
        x = np.asarray(prog, dtype=np.float64)
        if x.shape != (src.PROGRAM_SIZE,) or src.version > self.version:
            raise ValueError(f"cannot pad an ABI {src.version} program of {x.shape} into ABI {self.version}")
        out = np.zeros(self.PROGRAM_SIZE, dtype=np.float64)
        n = len(PROGRAM_ROWS)
        for i in range(n):
            out[i * self.P:i * self.P + src.P] = x[i * src.P:(i + 1) * src.P]
        out[n * self.P:] = x[n * src.P:]
        return out

    def pack_init(self, cells, rows=None) -> tuple[np.ndarray, int]:
        """Explicit initial body -> int32 ``[MAX_INIT, INIT_COLS]`` and the count. ABI 2 cells are ``(a, b)``;
        ABI 3 cells are ``(a, b)`` or ``(a, b, z)`` (z = 0 if omitted). ``rows`` gives a fixed program row per cell
        (-1 = selector). Cell 0 plays the zygote's role (uid index 0)."""
        cells = [tuple(int(v) for v in c) for c in cells]
        if not 1 <= len(cells) <= self.MAX_INIT:
            raise ValueError(f"an initial body has 1..{self.MAX_INIT} cells")
        if self.version >= 3:
            if any(len(c) not in (2, 3) for c in cells):
                raise ValueError("ABI 3 initial cells are (a, b) or (a, b, z)")
            cells = [c if len(c) == 3 else (c[0], c[1], 0) for c in cells]
            if any(max(abs(a), abs(b)) > COORD_MAX_3D or not 0 <= z < L_MAX_MAX for a, b, z in cells):
                raise ValueError(f"initial cells need |a|, |b| <= 2^22 and 0 <= z < {L_MAX_MAX}")
        elif any(len(c) != 2 for c in cells):
            raise ValueError("ABI 2 initial cells are (a, b)")
        if len(set(cells)) != len(cells):
            raise ValueError("initial cells must sit on distinct sites")
        rows = [-1] * len(cells) if rows is None else list(rows)
        out = np.zeros((self.MAX_INIT, self.INIT_COLS), dtype=np.int32)
        for i, (c, r) in enumerate(zip(cells, rows)):
            out[i] = (*c, r)
        return out, len(cells)

    # ------------------------------------------------------------------------------------------ lattice
    def lattice_tables(self, kind: str) -> tuple[np.ndarray, np.ndarray]:
        """The kernel's lattice table and unit vectors (LIFE_ABI.md 4.3).

        ABI 2: ``(int32 [2 + 6 D], float64 [D, 2])``: code, D, off_a, off_b, back, cyc_prev, cyc_next, rot.
        ABI 3: ``(int32 [2 + 7 D], float64 [D, 3])``: code, D, off_a, off_b, off_z, back, cyc_prev, cyc_next, rot.
        ``rot`` is the slot permutation of one counter-clockwise lattice rotation (for tests; the kernel ignores it).
        """
        if kind not in self.LATTICE_CODES:
            raise ValueError(f"lattice {kind!r} is not part of ABI {self.version}")
        if self.version < 3:
            off = _lat.offsets(kind)
            D = len(off)
            cyc = _lat.cyclic_neighbours(kind)
            rot = _lat.slot_map(kind, lambda a, b: _lat.rotate(kind, a, b))
            tab = [self.LATTICE_CODES[kind], D] + [a for a, _ in off] + [b for _, b in off] + _lat.back_slots(kind)
            tab += [p for p, _ in cyc] + [n for _, n in cyc] + rot
            unit = np.array(_lat.unit_vectors(kind), dtype=np.float64)
            return np.array(tab, dtype=np.int32), np.ascontiguousarray(unit)
        off = _lat.offsets3(kind)
        D = len(off)
        cyc = _lat.cyclic_neighbours3(kind)
        rot = _lat.slot_map3(kind, lambda a, b, z: _lat.rotate3(kind, a, b, z))
        tab = [self.LATTICE_CODES[kind], D] + [o[0] for o in off] + [o[1] for o in off] + [o[2] for o in off]
        tab += _lat.back_slots3(kind) + [p for p, _ in cyc] + [n for _, n in cyc] + rot
        unit = np.array(_lat.unit_vectors3(kind), dtype=np.float64)
        return np.array(tab, dtype=np.int32), np.ascontiguousarray(unit)

    # ------------------------------------------------------------------------------------------ flags, worlds
    def flags(self, *names: str) -> int:
        out = 0
        for n in names:
            out |= self.FLAGS[n]
        return out

    def validate_world(self, w: World) -> None:
        """The world rules of LIFE_ABI.md 4.7 (the kernel returns -2 for a vector that breaks any of them). Under
        ABI 2 a world that needs ABI 3 (CATCH, a prism lattice, L_max > 1) is refused as not implemented."""
        v = self.version
        if not w.implemented or any(getattr(w, k) != 0 for k in RESERVED_WORLD_KEYS):
            raise NotImplementedError(f"world {w.name!r} (stage {w.stage}) is not implemented by ABI v{v}")
        if w.lattice not in LATTICE_CODES_V3:
            raise ValueError(f"unknown lattice {w.lattice!r}")
        if v < 3 and (w.lattice not in self.LATTICE_CODES or w.world_kind != 0 or w.L_max != 1 or w.stuck_z != 0):
            raise NotImplementedError(f"world {w.name!r} (world kind {w.world_kind}, lattice {w.lattice}, L_max "
                                      f"{w.L_max}) needs ABI v3; this is ABI v{v}")
        bad = [k for k in ALL_WORLD_KEYS if not math.isfinite(float(getattr(w, k)))]
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
            x = getattr(w, nm)
            if x & ~sum(self.FLAGS.values()) or x & self.UNSUPPORTED_FLAGS:
                raise ValueError(f"{nm}: unknown or unsupported flag bits {x:#x} for ABI v{v}")
        if w.fork_flags & self.BASE_ONLY_FLAGS:
            raise ValueError("lockstep, program_mode and integer_twin can only be base flags")
        if not (w.d_min >= STEP_MIN and w.d0 > 0):
            raise ValueError("d_min >= 2^-10 and d0 > 0 are required")
        if not all(0 <= getattr(w, k) < 1 for k in ("jit", "tau_mis", "tick_jit")):
            raise ValueError("jit, tau_mis and tick_jit must lie in [0, 1)")
        if not (0 <= w.delay_sd <= SD_MAX and 0 <= w.clock_sd <= SD_MAX):
            raise ValueError(f"delay_sd and clock_sd must lie in [0, {SD_MAX}]")
        if not w.P0 > 0 or min_tick_period(w) < STEP_MIN:
            raise ValueError("P0 > 0 and a smallest tick period P0 exp(-6 clock_sd) (1 - tick_jit) >= 2^-10 are "
                             "required")
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
        _validate_body_keys(w)
        _validate_visibility_keys(w)
        _validate_task_keys(w)
        if v < 4 and w.visibility_mode != 0:
            raise NotImplementedError(f"target visibility needs ABI v4; this is ABI v{v}")
        if v < 5 and w.task_mode != 0:
            raise NotImplementedError(f"delayed matching needs ABI v5; this is ABI v{v}")

    def pack_world(self, w) -> np.ndarray:
        """World (or a list of worlds, one per life) -> float64 ``[WORLD_SIZE]`` / ``[B, WORLD_SIZE]``."""
        many = isinstance(w, (list, tuple))
        ws = list(w) if many else [w]
        out = np.zeros((len(ws), self.WORLD_SIZE), dtype=np.float64)
        for i, x in enumerate(ws):
            self.validate_world(x)
            out[i] = [float(getattr(x, k)) for k in self.WORLD_KEYS]
        return out if many else out[0]

    # ------------------------------------------------------------------------------------------ ledger
    def column_cost(self, led, w: World | None = None) -> np.ndarray:
        """Sum of per-action costs rebuilt from ledger columns (the left-to-right order of LIFE_ABI.md 9.5)."""
        w = w or PRESETS["bell_v1"]
        led = np.asarray(led, dtype=np.float64)
        L = self.L
        c = w.c_live * led[..., L["live_time"]]
        c = c + w.c_spike * led[..., L["spikes"]]
        c = c + w.c_tw * led[..., L["kappa_sum"]]
        c = c + w.c_msg * led[..., L["contact_events"]]
        c = c + w.c_div * led[..., L["claims"]]
        c = c + w.c_sec * led[..., L["sec_int"]]
        if self.version >= 3:
            c = c + w.c_miss * led[..., L["misses"]]
            c = c + w.c_rec * led[..., L["rec_gain"]]
            wrong = (led[..., L["wrong_choices_narrow"]] + led[..., L["wrong_choices_broad"]]
                     if w.task_mode else led[..., L["b2_clicks"]])
            c = c + b2_cost(w) * wrong
        return c

    def guard_charge(self, led, w: World | None = None) -> np.ndarray:
        """c_live N_max (t0 + T - t_end) for lives ended by a guard, else 0."""
        w = w or PRESETS["bell_v1"]
        led = np.asarray(led, dtype=np.float64)
        guard = STATUS["guard_cells"] | STATUS["guard_events"]
        tripped = (led[..., self.L["status"]].astype(np.int64) & guard) != 0
        return np.where(tripped, w.c_live * w.n_max * (w.t0 + w.T - led[..., self.L["t_end"]]), 0.0)

    def fitness(self, led, w: World | None = None) -> np.ndarray:
        """F from ledger columns under the costs of ``w`` (re-pricing a finished life with another cost table)."""
        w = w or PRESETS["bell_v1"]
        led = np.asarray(led, dtype=np.float64)
        income = (w.R_cap * (led[..., self.L["correct_choices_narrow"]] +
                            led[..., self.L["correct_choices_broad"]])
                  if w.task_mode else led[..., self.L["income"]])
        net = income - self.column_cost(led, w) - self.guard_charge(led, w)
        return net / (w.T - w.t_open)


def _validate_task_keys(w: World) -> None:
    """ABI 5 delayed matching; neutral fields preserve all older world semantics."""
    durations = (w.sample_min, w.sample_max, w.blank_min, w.blank_max, w.choice_T, w.reset_T)
    if w.task_mode not in (0, 1):
        raise ValueError("task_mode must be 0 or 1")
    if w.task_mode == 0:
        if any(x != 0 for x in durations):
            raise ValueError("legacy task_mode requires all task durations zero")
        return
    if not all(STEP_MIN <= x <= TIME_MAX for x in durations):
        raise ValueError("task durations must lie in [2^-10, 2^30]")
    if w.sample_min > w.sample_max or w.blank_min > w.blank_max or w.blank_min <= w.d_min:
        raise ValueError("task duration ranges must be ordered and blank_min must exceed d_min")
    if w.world_kind != 1 or w.visibility_mode != 0 or (w.v_t, w.tau_turn, w.t_resp) != (0, 0, 0):
        raise ValueError("delayed matching requires stationary CATCH with neutral visibility and no renewal")
    if (w.b2_amp, w.b2_p, w.b2_mode) != (1, 1, 0):
        raise ValueError("delayed matching requires b2_amp=b2_p=1 and b2_mode=0")
    if not w.sigma < w.b2_sigma or w.rho_c != w.b2_rho or 2 * w.R_min <= w.rho_c + w.b2_rho:
        raise ValueError("delayed matching requires ordered distinct widths, equal radii and disjoint choices")
    if w.b2_value >= 0:
        raise ValueError("delayed matching requires negative b2_value for the wrong-choice charge")


def _validate_visibility_keys(w: World) -> None:
    """ABI 4 world-only visibility; mode zero has one neutral representation."""
    if w.visibility_mode not in (0, 1, 2):
        raise ValueError("visibility_mode must be 0, 1 or 2")
    if not 0 <= w.visibility_low <= 1:
        raise ValueError("visibility_low must lie in [0, 1]")
    if w.visibility_mode == 0:
        if (w.visibility_on, w.visibility_off, w.visibility_low) != (0, 0, 1):
            raise ValueError("steady visibility requires on=off=0 and low=1")
        return
    if w.world_kind != 1 or w.b2_amp != 0:
        raise ValueError("enabled visibility requires a single-target CATCH world")
    if not STEP_MIN <= w.visibility_on <= TIME_MAX:
        raise ValueError("visibility_on must lie in [2^-10, 2^30]")
    if w.visibility_mode == 1:
        if w.visibility_off != 0:
            raise ValueError("flash visibility requires visibility_off=0")
    elif not STEP_MIN <= w.visibility_off <= TIME_MAX:
        raise ValueError("renewal visibility_off must lie in [2^-10, 2^30]")


def _validate_body_keys(w: World) -> None:
    """The rules of the ABI-3 world keys (LIFE_ABI.md 4.7). They hold for every world, BELL included, so a world's
    validity never depends on which ABI packs it."""
    if w.world_kind not in WORLD_KINDS.values():
        raise ValueError(f"world_kind must be one of {sorted(WORLD_KINDS.values())}")
    if not 1 <= w.L_max <= L_MAX_MAX or not 0 <= w.stuck_z < w.L_max:
        raise ValueError(f"1 <= L_max <= {L_MAX_MAX} and 0 <= stuck_z < L_max are required")
    if not (0 < w.sigma <= LENGTH_MAX and 0 < w.b2_sigma <= LENGTH_MAX):
        raise ValueError("sigma and b2_sigma must lie in (0, 2^20]")
    if not (w.lam_s >= 0 and w.lam_bg >= 0 and w.b2_amp >= 0 and lambda_max(w) <= RATE_MAX):
        raise ValueError(f"lam_s, lam_bg and b2_amp must be non-negative, with lambda_max <= {RATE_MAX}")
    if not (0 <= w.g_n <= SPEED_MAX and 0 <= w.v_t <= SPEED_MAX and 0 <= w.drag_exp <= 2):
        raise ValueError(f"g_n and v_t must lie in [0, {SPEED_MAX}] and drag_exp in [0, 2]")
    if not 0 <= w.th_rel < w.th_click <= 1:
        raise ValueError("0 <= th_rel < th_click <= 1 is required")
    if not (w.rho_c >= 0 and w.b2_rho >= 0 and 0 <= w.R_min <= w.R_max <= LENGTH_MAX):
        raise ValueError("rho_c, b2_rho >= 0 and 0 <= R_min <= R_max <= 2^20 are required")
    if not (0 <= w.tau_turn <= TIME_MAX and 0 <= w.t_resp <= TIME_MAX):
        raise ValueError("tau_turn and t_resp must lie in [0, 2^30] (0 = off)")
    if 0 < w.tau_turn < STEP_MIN or 0 < w.t_resp < STEP_MIN:
        raise ValueError("tau_turn and t_resp must be 0 (off) or at least 2^-10, like every period, so world time "
                         "always advances")
    if not (w.R_cap >= 0 and w.c_miss >= 0 and w.c_rec >= 0):
        raise ValueError("R_cap, c_miss and c_rec must be non-negative")
    if not (0 <= w.b2_p <= 1 and w.b2_mode in (0, 1)):
        raise ValueError("b2_p must lie in [0, 1] and b2_mode be 0 or 1")


# ================================================================================ CATCH world closed forms (ABI 3)
# Pure functions of LIFE_ABI.md 9.7, written with the operations and the order both implementations must use.
TWO_PI = 6.283185307179586  # the double nearest 2 pi (C: 2.0 * M_PI)


def b2_cost(w: World) -> float:
    """Charge per click on the second blob: -b2_value if it is negative, else 0 (a positive value is income)."""
    return -w.b2_value if w.b2_value < 0 else 0.0


def lambda_max(w: World) -> float:
    """Candidate rate of every sense-plane receptor: lam_bg + lam_s (1 + b2_amp), an upper bound of the true rate."""
    return w.lam_bg + w.lam_s * (1.0 + w.b2_amp)


def halo(dx: float, dy: float, sigma: float) -> float:
    """exp(-(dx^2 + dy^2) / (2 sigma^2)), the luminance of a blob at offset (dx, dy) from its centre."""
    return math.exp(-(dx * dx + dy * dy) / (2.0 * sigma * sigma))


def receptor_rate(w: World, px: float, py: float, blob0: tuple | None, blob1: tuple | None = None) -> float:
    """True receptor rate at world point (px, py), with ``None`` for either absent blob.
    A delayed-match caller supplies the active scene for the current phase; this helper has no phase state."""
    signal = w.lam_s * halo(px - blob0[0], py - blob0[1], w.sigma) if blob0 is not None else 0.0
    rate = w.lam_bg + signal
    if blob1 is not None:
        rate = rate + w.lam_s * (w.b2_amp * halo(px - blob1[0], py - blob1[1], w.b2_sigma))
    return rate


def receptor_accepts(seed: int, uid: int, j: int, rate: float, lam_max: float) -> bool:
    """Thinning: candidate j of the receptor of cell uid is accepted iff u lambda_max < rate."""
    return draw(seed, S_RACC, uid, j) * lam_max < rate


def receptor_next(seed: int, uid: int, j: int, t_prev: float, lam_max: float) -> float:
    """Time of candidate j: t_prev - log(u_j) / lambda_max, moved to nextup(t_prev) if it does not advance (t_prev
    is the birth time for j = 0, else candidate j - 1)."""
    t = t_prev - math.log(draw(seed, S_RCAND, uid, j)) / lam_max
    return t if t > t_prev else math.nextafter(t_prev, math.inf)


def poisson_next(seed: int, stream: int, blob: int, k: int, t_prev: float, mean: float) -> float:
    """World timers (turns: S_TURN, mean tau_turn; re-placements: S_RTIME, mean t_resp): t_prev - mean log(u_k)."""
    return t_prev - mean * math.log(draw(seed, stream, blob, k))


def drag(n_fill: int, drag_exp: float) -> float:
    """gamma = n_fill ** drag_exp (C pow), for a filled footprint of n_fill >= 1 tiles (``filled_footprint``,
    LIFE_ABI.md 9.7.2)."""
    return math.pow(float(n_fill), drag_exp)


def edge_steps_up(kind: str) -> tuple[int, int]:
    """``(dlo, dhi)``: the a-offsets of the tiles that share an edge with tile (a, b) in row b + 1 (hex: a - 1 and a;
    square: a). Tiles share an edge iff their sites are at unit distance, so square8's diagonal slots, whose tiles
    touch only at a corner, are not edge steps."""
    base = _lat.base_kind(kind)
    up = [da for da, db in _lat.offsets(base) if db == 1 and math.isclose(math.hypot(*_lat.to_xy(base, da, db)), 1.0)]
    return min(up), max(up)


def filled_footprint(cols, kind: str = "hexprism") -> int:
    """n_fill, the drag's footprint (LIFE_ABI.md 9.7.2, 15.61): the tiles of the occupied columns ``cols`` (the
    projected footprint: every (a, b) with a live cell in any plane) plus every tile they enclose, i.e. every free
    tile with no path of edge-sharing free tiles to infinity (holes are filled; islands add their own tiles and what
    they enclose together, not the gaps between them).

    Row runs, O(n) after the sort: each row b that holds occupied tiles splits into free runs between them; its two
    unbounded runs, and every run of a row next to an empty row, are outside; runs of adjacent rows that share an edge
    are joined (union-find); the enclosed tiles are the bounded runs not joined to the outside. The kernel computes
    the same integer with the same method on its sorted column list."""
    cs = sorted({(int(a), int(b)) for a, b in cols}, key=lambda s: (s[1], s[0]))
    if not cs:
        return 0
    dlo, dhi = edge_steps_up(kind)
    rows: dict[int, list[int]] = {}
    for a, b in cs:  # rows in increasing b, sites in increasing a
        rows.setdefault(b, []).append(a)
    inf = math.inf
    lo, hi, par = [-inf], [inf], [0]  # run 0 is the outside; a run is the free tiles [lo, hi] of its row

    def find(x: int) -> int:
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    span: dict[int, tuple[int, int]] = {}
    for b, aa in rows.items():
        runs = [(-inf, aa[0] - 1)] + [(x + 1, y - 1) for x, y in zip(aa, aa[1:]) if y > x + 1] + [(aa[-1] + 1, inf)]
        open_row = b - 1 not in rows or b + 1 not in rows  # it touches an empty row: every run is outside
        s = len(par)
        for x, y in runs:
            lo.append(x)
            hi.append(y)
            par.append(0 if open_row or x == -inf or y == inf else len(par))
        span[b] = (s, len(par))
        if b - 1 in rows:  # join each run of row b - 1 to the runs of row b it shares an edge with
            (p, pe), (q, qe) = span[b - 1], span[b]
            while p < pe and q < qe:
                l1, h1 = lo[p] + dlo, hi[p] + dhi
                if max(l1, lo[q]) <= min(h1, hi[q]):
                    x, y = find(p), find(q)
                    par[max(x, y)] = min(x, y)
                if h1 < hi[q]:
                    p += 1
                elif hi[q] < h1:
                    q += 1
                else:
                    p, q = p + 1, q + 1
    return len(cs) + sum(int(hi[r] - lo[r]) + 1 for r in range(1, len(par))
                         if lo[r] != -inf and hi[r] != inf and find(r) != 0)


def dot_gain(dt: float, tau_z: float, gam: float) -> tuple[float, float]:
    """``(k, e)`` for an interval dt: e = exp(-dt / tau_z) decays the force, and the dot moves by F k with
    k = tau_z (1 - e) / gamma (the exact integral of F e^(-s / tau_z) / gamma over the interval)."""
    e = math.exp(-dt / tau_z)
    return tau_z * (1.0 - e) / gam, e


def blob_heading(seed: int, blob: int, h: int, v_t: float) -> tuple[float, float]:
    """Velocity of heading h of a blob (h = 0 at t0, h = k + 1 after its turn k): v_t (cos phi, sin phi)."""
    phi = TWO_PI * draw(seed, S_HEAD, blob, h)
    return v_t * math.cos(phi), v_t * math.sin(phi)


def blob_place(seed: int, blob: int, q: int, x: float, y: float, r_min: float, r_max: float) -> tuple[float, float]:
    """Placement q of a blob around the dot at (x, y): angle 2 pi u, distance R_min + u' (R_max - R_min)."""
    th = TWO_PI * draw(seed, S_PANG, blob, q)
    r = r_min + draw(seed, S_PDIST, blob, q) * (r_max - r_min)
    return x + r * math.cos(th), y + r * math.sin(th)


def blob_present(seed: int, q: int, b2_p: float) -> bool:
    """Whether the second blob is present after its placement q: u < b2_p."""
    return draw(seed, S_PPRES, 1, q) < b2_p


def exposed_face(kind: str, empty_slots) -> tuple[float, float]:
    """n = the sum of the in-plane unit vectors of the slots in ``empty_slots``, taken in increasing slot order."""
    units = _lat.unit_vectors(_lat.base_kind(kind))
    nx, ny = 0.0, 0.0
    for d in sorted(set(empty_slots)):
        if d < len(units):
            nx = nx + units[d][0]
            ny = ny + units[d][1]
    return nx, ny


def key_step(armed: bool, zt: float, zn: float, th_click: float, th_rel: float) -> tuple[bool, bool]:
    """The hotspot key at one of its twitches (zt before, zn after): ``(armed after, click)``."""
    if not armed and zt < th_rel:
        armed = True
    if armed and zn >= th_click:
        return False, True
    return armed, False


# ======================================================================================== the module-level ABI
V2 = Abi(2)
V3 = Abi(3)
V4 = Abi(4)
V5 = Abi(5)
CURRENT = V2  # legacy caller default; explicit newer contracts remain available

ABI_VERSION = CURRENT.version
S, P, NIN = CURRENT.S, CURRENT.P, CURRENT.NIN
KNOBS, K, GRIDS, INPUTS = CURRENT.KNOBS, CURRENT.K, CURRENT.GRIDS, CURRENT.INPUTS
GENOME_FIELDS, GENOME_SLICES, GENOME_SIZE = CURRENT.GENOME_FIELDS, CURRENT.GENOME_SLICES, CURRENT.GENOME_SIZE
PROGRAM_SIZE, PROGRAM_ROW, PROGRAM_SCALAR = CURRENT.PROGRAM_SIZE, CURRENT.PROGRAM_ROW, CURRENT.PROGRAM_SCALAR
MAX_INIT = CURRENT.MAX_INIT
LATTICE_CODES = CURRENT.LATTICE_CODES
FLAGS, BASE_ONLY_FLAGS, UNSUPPORTED_FLAGS = CURRENT.FLAGS, CURRENT.BASE_ONLY_FLAGS, CURRENT.UNSUPPORTED_FLAGS
STREAMS = CURRENT.STREAMS
WORLD_KEYS, WORLD_SIZE, WORLD_INDEX = CURRENT.WORLD_KEYS, CURRENT.WORLD_SIZE, CURRENT.WORLD_INDEX
LEDGER, L, LEDGER_SIZE = CURRENT.LEDGER, CURRENT.L, CURRENT.LEDGER_SIZE
HASHES, HASH_SIZE = CURRENT.HASHES, CURRENT.HASH_SIZE
FATE_I, FATE_I_SIZE = CURRENT.FATE_I, CURRENT.FATE_I_SIZE
SIZES = CURRENT.SIZES

decode_knobs = CURRENT.decode_knobs
readout = CURRENT.readout
phenotype = CURRENT.phenotype
theta = CURRENT.theta
genome_view = CURRENT.genome_view
pack_genomes = CURRENT.pack_genomes
pack_program = CURRENT.pack_program
pack_init = CURRENT.pack_init
lattice_tables = CURRENT.lattice_tables
flags = CURRENT.flags
validate_world = CURRENT.validate_world
pack_world = CURRENT.pack_world
column_cost = CURRENT.column_cost
guard_charge = CURRENT.guard_charge
fitness = CURRENT.fitness
