"""Pure-Python specification of one life (docs/LIFE_ABI.md, ABI 7), written independently of the C kernel.

Every handler of the ABI (sections 6-12) is transcribed here with the same float64 operations in the same order, so on
the same libm its ledger, hashes, raster and fate log agree bitwise with ``kernel.c``. It is meant for tiny bodies
(about 20 cells, T up to about 200) in tests: whole lives are seconds, not milliseconds.

The handlers implement ABI 7: sites ``(a, b, z)`` in a stack of ``L_max`` planes, the prism lattices, the receptor
events RCAND and RECEPTOR (7.10), the plane cues and the receptor trace, vertical placement, the forks lateral_off,
hidden_off, receptor_off and motor_off, and both world kinds: the BELL-1 lumen (9.2) and the CATCH world (9.7).
Every entry point takes ``abi`` (default ``spec.CURRENT``):
- ``spec.V7``: ABI-7 arrays (world 83, ledger 143), adding contact-grown food.
- ``spec.V6``: ABI-6 arrays (world 82, ledger 107), adding conserved food patches.
- ``spec.V5``: ABI-5 arrays (world 77, ledger 70), adding delayed cue matching without changing cell rules.
- ``spec.V4``: ABI-4 arrays in and out (world 70, ledger 58); flash/renewal visibility changes target cues only.
- ``spec.V3``: ABI-3 arrays in and out (genome 875, program 129, world 66, ledger 57, 5 hashes, fate_i 7 columns).
- ``spec.V2``: ABI-2 arrays in and out. The inputs are padded neutrally into ABI 7 (``spec.V3.pad_genomes``,
  ``pad_program``, the CATCH and visibility keys at their defaults, z = 0), and outputs are cut back to ABI 2's
  sizes. The ``all`` hash folds only the caller's ledger columns. LIFE_ABI.md 15.33 says this is
  ABI 2 bitwise (gate GB1); the ABI-2 tests of this repository check it against the ABI-2 kernel.

Both schedulers of section 11 are implemented: the heap (``window_h = 0``, ties permuted by the tie seed) and the
conservative window scheduler (``window_h = 2^-k``, sites visited in order-seed order). The relabel salt permutes the
order in which same-batch events leave the heap, which must not change anything.

Where the ABI leaves a detail open, this file chooses:
- emit knobs are read as booleans (nonzero = on), so ``n_out`` is an integer;
- packets lost in one batch emit R_LOST in increasing (sender uid, receiver slot) order;
- notices with equal (receiver slot, kind) keep the sender site's send order;
- a capacity of 0 turns a log off without setting its overflow bit;
- fate-log reject entries are written for both occupied (aux 0) and wall (aux 1) results;
- a slot that points out of the stack holds EMPTY in the view (no cell ever answers from there) but is never open, so
  it is not counted in n_view and never claimed (4.3, worded so since cross-check round 1);
- an RCAND is current iff its uid is the occupant at t- and its j is the cell's rec#;
- world events at one time run in (time, timer before turn before visibility, blob) order, re-reading the earliest;
- a click on a second blob with ``b2_value != 0`` books its income or cost only when the click is counted (like
  ``b2_clicks``, so ``cost`` and ``colcost`` agree; 9.7.4 now says so).
Argument errors get the kernel's codes in the kernel's order (4.2, 15.57): an initial cell on a wall of a dense
fabric is -4, a row is checked in program mode only, the key bound holds for ABI-2 calls too, and a slot with offset
(0, 0, 0) is not a lattice slot.
"""
from __future__ import annotations

import heapq
import math
import struct
from dataclasses import dataclass, fields, replace

import numpy as np

from src import lattice as _lat
from src.life import spec

V2, V3, V4, V5, V6, V7, V8 = spec.V2, spec.V3, spec.V4, spec.V5, spec.V6, spec.V7, spec.V8
EMPTY = spec.EMPTY
_KIND_OF = {code: kind for kind, code in V3.LATTICE_CODES.items()}
_INF = float("inf")
_PACK_D = struct.Struct("<d")
_PACK_Q = struct.Struct("<Q")
S32 = 0.8660254037844386  # the double nearest sqrt(3) / 2 (LIFE_ABI.md 2)

# event kinds; kind // 10 is the batch group of section 6.2 (within NOTICE the kind order is the ABI's)
CLAIM = 0
BORN, PRESENT, ACK, REJECT, DIED = 10, 11, 12, 13, 14
PACKET = 20
ARRIVAL, THRESHOLD, NOISE, RCAND, RECEPTOR, RCANDM, RECEPTORM = 30, 31, 32, 33, 34, 35, 36
TICK = 40
KILL, STUCK = 50, 51

# records; the id is also the first hash word (section 9.6); R_CHEM is not hashed
R_SPIKE, R_BIRTH, R_DEATH, R_CLAIM, R_RESOLVE, R_PACKET, R_LOST, R_TICK = 1, 2, 3, 4, 5, 6, 7, 8
R_RCAND, R_RECEPT = 9, 10
R_RCANDM, R_RECEPTM = 30, 31  # ABI 8 modality records (world family)
R_CHEM = 100
W_CLICK, W_PLACE, W_TURN, W_VISIBILITY = 11, 12, 13, 14  # CATCH accountant world-event first hash words
W_TASK_PHASE, W_TASK_RESOLVE, W_TASK_END = 15, 16, 17
W_PATCH_START, W_PATCH_SOURCE, W_PATCH_CLICK, W_PATCH_END = 18, 19, 20, 21
W_CONTACT_START, W_CONTACT_MATURE, W_CONTACT_END = 22, 23, 24
TASK_SAMPLE, TASK_BLANK, TASK_CHOICE, TASK_GAP = range(4)
H_ALL, H_SPIKES, H_FATE, H_CHEM, H_WORLD = 0, 1, 2, 3, 4
_FAMILY = {R_SPIKE: H_SPIKES, R_BIRTH: H_FATE, R_DEATH: H_FATE, R_CLAIM: H_FATE, R_RESOLVE: H_FATE,
           R_PACKET: H_CHEM, R_LOST: H_CHEM}  # R_RCAND and R_RECEPT fold into the world family (_fold_world)

(KW0, KW1, KB, KTAU, KREF, KE0, KE1, KDEL, KKAP, KPDIV, KASYM, KPDIE, KPHI, KSEC0, KSEC1, KPOL0, KPOL1, KTTR,
 KA0, KA1, KCHI, KZETA, KGR) = range(V3.P)
assert [V3.K[n] for n in V3.KNOBS] == list(range(V3.P)) and V3.KNOBS[KZETA] == "zeta" and V3.KNOBS[KGR] == "g_r"
SM = spec.S_MAX  # ABI 8 modality slots; the gain of modality m is knob KGR + m

_F = V3.FLAGS
_ST = spec.STATUS
_LI = V8.L
_NROW = len(spec.PROGRAM_ROWS)
_PS = {name: i - _NROW * V3.P for name, i in V3.PROGRAM_SCALAR.items()}
_ROW = V3.PROGRAM_ROW
_FLOAT_KEYS = ("T", "t0", "t_open", "t_fork", "d_min", "d0", "delay_sd", "jit", "tau_mis", "P0", "clock_sd",
               "tick_jit", "tau_z", "th", "th_lo", "tau_R", "tau_e", "h_inc", "c_live", "c_spike", "c_tw", "c_msg",
               "c_div", "c_sec", "window_h", "drop_p", "noise_rate", "kill_t", "kill_frac", "stuck_t", "e_max",
               "sigma", "lam_s", "lam_bg", "g_n", "drag_exp", "th_click", "th_rel", "rho_c", "v_t", "tau_turn",
               "R_min", "R_max", "t_resp", "R_cap", "c_miss", "c_rec", "b2_amp", "b2_sigma", "b2_value", "b2_rho",
               "b2_p", "visibility_on", "visibility_off", "visibility_low",
               "sample_min", "sample_max", "blank_min", "blank_max", "choice_T", "reset_T",
               "patch_refill_fast", "patch_refill_slow", "patch_landmark", "patch_contact_delay")
_INT_KEYS = ("flags", "fork_flags", "n_max", "fabric_R", "oracle_cap", "stuck_a", "stuck_b", "world_kind", "L_max",
             "stuck_z", "b2_mode", "visibility_mode", "task_mode", "patch_count", "patch_capacity")
_V3_DEFAULTS = [float(getattr(spec.World(), k)) for k in V3.WORLD_KEYS[V2.WORLD_SIZE:]]
_V4_DEFAULTS = [float(getattr(spec.World(), k)) for k in V4.WORLD_KEYS[V3.WORLD_SIZE:]]
_V5_DEFAULTS = [float(getattr(spec.World(), k)) for k in V5.WORLD_KEYS[V4.WORLD_SIZE:]]
_V6_DEFAULTS = [float(getattr(spec.World(), k)) for k in V6.WORLD_KEYS[V5.WORLD_SIZE:]]
_V7_DEFAULTS = [0.0]
_V8_DEFAULTS = [0.0] * (V8.WORLD_SIZE - V7.WORLD_SIZE)


def bits(x: float) -> int:
    """IEEE-754 bit pattern of a float64 as an unsigned integer."""
    return _PACK_Q.unpack(_PACK_D.pack(x))[0]


def _max(x: float, y: float) -> float:  # the ABI's max: x < y ? y : x
    return y if x < y else x


class ArgError(ValueError):
    """An argument error of ``life_run``; ``rc`` is the kernel's return code (section 4.2)."""

    def __init__(self, rc: int, msg: str):
        super().__init__(msg)
        self.rc = rc


# ------------------------------------------------------------------------------------------------------------ state
class _Site:
    __slots__ = ("sk", "a", "b", "z", "births", "occ", "nsend")

    def __init__(self, a: int, b: int, z: int):
        self.sk = spec.sitekey(a, b, z)
        self.a, self.b, self.z = a, b, z
        self.births = 0
        self.occ = None  # the live occupant, or None
        self.nsend = 0  # messages sent from this site (deterministic tie-break among equal notices)


class _Cell:
    __slots__ = ("uid", "mother", "alive", "t_birth", "k", "init", "row", "site", "nspk", "ntick", "ndiv", "nrec",
                 "view", "dc", "inc", "v_a", "t_a", "t_r", "ver", "f", "r0", "r1", "rho", "t_tr", "tw", "t_tw", "g",
                 "m", "inbox", "th", "tau", "w_eff", "s", "taumis", "P_n", "t_prev", "pending", "timer",
                 "timer_birth", "stuck", "rhom", "nrecm", "pendm")


class _Blob:
    """A CATCH screen blob (9.7.1): anchor (t, x, y), velocity, and its counters and next world-event times."""
    __slots__ = ("i", "present", "t", "x", "y", "vx", "vy", "h", "q", "tau", "k", "r", "m")


@dataclass
class _Patch:
    """ABI6 observer-visible world state; inactive slots have a canonical zero representation."""
    x: float = 0.0
    y: float = 0.0
    period: float = 0.0
    first: float = 0.0
    next: float = 0.0
    arrival_index: int = 0
    stock: int = 0
    initial_remaining: int = 0
    contact_due: float = _INF
    contact_starts: int = 0
    contact_pending: int = 0
    contact_stock: int = 0
    origins: bytearray | None = None
    origin_head: int = 0
    origin_n: int = 0


@dataclass
class LifeResult:
    """Outputs of one life in the caller's explicit ABI 2–8 layouts (LIFE_ABI.md 4.9-4.11)."""
    ledger: np.ndarray  # float64 [abi.LEDGER_SIZE], columns abi.LEDGER
    hashes: np.ndarray  # uint64 [abi.HASH_SIZE]: all, spikes, fate, chem (, world)
    raster_t: np.ndarray  # float64 [min(raster_n, cap)]
    raster_uid: np.ndarray  # uint64
    raster_n: int
    fate_i: np.ndarray  # int64 [rows, abi.FATE_I_SIZE]: kind, uid, mother, a, b, aux (, z)
    fate_f: np.ndarray  # float64 [rows, 18]: t, age, g[16]
    fate_n: int
    records: list | None = None  # canonical records (t, sk, seq, kind, payload) when asked for
    world: list | None = None  # the words of every world-family fold, in fold order (CATCH), when asked for
    abi: spec.Abi = V3

    def __getitem__(self, name: str) -> float:
        return float(self.ledger[self.abi.L[name]])

    @property
    def status(self) -> int:
        return int(self.ledger[self.abi.L["status"]])


# ------------------------------------------------------------------------------------------------------- accountant
class _Accountant:
    """Section 9: consumes records in canonical order; owns the world, the ledger, the logs and the hashes."""

    def __init__(self, life: _Life):
        if not hasattr(life, "eco"):  # accountant tests drive it with a bare namespace of world keys
            life.eco = False
        self.life = life
        self.A, self.R, self.t_w, self.above = 0.0, 1.0, life.t0, 0
        self.n = 0
        self.n_plane = [0, 0, 0]  # live cells in the planes S (z = 0), M (z = 1) and H (z >= 2)
        self.inflight = 0
        self.led = [0.0] * V8.LEDGER_SIZE
        self.led[_LI["last_birth"]] = life.t0
        self.led[_LI["t_ext"]] = -1.0
        self.status = 0
        self.extinct = False
        self.n_peak = 0
        self.h = [spec.HASH_INIT] * V3.HASH_SIZE
        self.raster_t: list[float] = []
        self.raster_uid: list[int] = []
        self.raster_n = 0
        self.fate: list[tuple] = []
        self.fate_n = 0
        self.flying: list[tuple] = []  # remembered packets (t_arr, target sk, sender, amt0, amt1, t_send)
        self.records = [] if life.keep_records else None
        self.wlog = [] if life.keep_records else None
        self.eco_dead = False
        if life.catch:
            self._catch_start()

    # --------------------------------------------------------------------------------------------- BELL (9.2)
    def world_adv(self, t: float) -> None:
        if t <= self.t_w:
            return
        to = self.life.t_open_abs
        if self.t_w < to < t:
            self._adv(to, False)
            self._adv(t, True)
        else:
            self._adv(t, self.t_w >= to)

    def _adv(self, t: float, count: bool) -> None:
        L = self.life
        dt = t - self.t_w
        if self.n == 0:
            self.t_w = t
            return
        P0 = self.A / self.n
        e = math.exp(-dt / L.tau_z)
        if P0 > L.th:
            s1 = L.tau_z * math.log(P0 / L.th)
            if s1 > dt:
                s1 = dt
            I = L.tau_z * P0 * (1.0 - math.exp(-s1 / L.tau_z)) - L.th * s1  # noqa: E741
            Rn = self.R * math.exp(-I / ((1.0 - L.th) * L.tau_e))
            if count:
                self.led[_LI["income"]] += L.h_inc * float(self.n) * (self.R - Rn)
            self.R = Rn
        Pend = P0 * e
        if Pend < L.th_lo:
            slo = L.tau_z * math.log(P0 / L.th_lo) if P0 > L.th_lo else 0.0
            dd = dt - slo
            if dd > 0:
                self.R = 1.0 - (1.0 - self.R) * math.exp(-dd / L.tau_R)
        if count:
            self.led[_LI["P_int"]] += L.tau_z * P0 * (1.0 - e)
        if Pend <= L.th:
            self.above = 0
        self.A = self.A * e
        self.t_w = t

    # -------------------------------------------------------------------------------------------- CATCH (9.7)
    def _catch_start(self) -> None:
        """9.7.1: the dot at rest at (0, 0), the key armed, every existing blob headed, timed and placed at t0."""
        L = self.life
        self.X = self.Y = self.Fx = self.Fy = 0.0
        self.t_x = L.t0
        self.n_foot = 0  # live sense-plane cells: traction (15.44)
        self.cols: dict[tuple, int] = {}  # (a, b) -> live cells in that column: the projected footprint (15.59)
        self.n_fill = 0  # tiles of the filled footprint, the projected one with its holes (drag, 15.61)
        self.gam = 1.0  # read only while n_foot > 0, after it has been set
        self.path = 0.0
        self.armed = True
        self.strokes: dict[tuple, list] = {}  # act-plane (a, b) -> [fx, fy, t_f] of its occupant
        self.O: set = set()  # act-plane (a, b) with a live occupant, at the left limit of the time group
        self.defer_O: list = []
        self.defer_place: list = []
        self.bright = True
        self.visibility_next = _INF
        self.visibility_k = 0
        if L.visibility_mode == 2:
            self.visibility_next = spec.poisson_next(L.seed, spec.S_VISIBILITY, 0, 0, L.t0, L.visibility_on)
            self.visibility_k = 1
        self.blobs = []
        self.eco_dead = False
        if L.eco:
            self._eco_start()
            return
        if L.patch_count:
            self._patch_start()
            return
        for i in range(2 if L.b2_amp > 0 else 1):
            bl = _Blob()
            bl.i, bl.present = i, True
            bl.t, bl.x, bl.y = L.t0, 0.0, 0.0
            bl.vx, bl.vy = spec.blob_heading(L.seed, i, 0, L.v_t)
            bl.h = 1
            bl.tau = spec.poisson_next(L.seed, spec.S_TURN, i, 0, L.t0, L.tau_turn) if L.tau_turn > 0 else _INF
            bl.k = 1
            timed = L.t_resp > 0 and (i == 0 or L.b2_mode == 1)
            bl.r = spec.poisson_next(L.seed, spec.S_RTIME, i, 0, L.t0, L.t_resp) if timed else _INF
            bl.m = 1
            bl.q = 0
            self.blobs.append(bl)
        if L.task_mode:
            self.task_trial = 0
            self.task_class = 0
            self.task_consumed = False
            self.task_pending_gap = False
            self.task_choice_start = _INF
            self.task_carry_counted = False
            self._task_enter(TASK_SAMPLE, L.t0)
        else:
            for bl in self.blobs:
                self.place(bl.i, 0, L.t0)

    def _patch_start(self) -> None:
        L = self.life
        self.patches = [_Patch() for _ in range(4)]
        self.patch_left = [0] * 4
        self.patch_initial_open = [0] * 4
        self.patch_opened = False
        for i in range(L.patch_count):
            p = self.patches[i]
            p.x, p.y = spec.patch_layout(L.seed, i, L.patch_count, L.R_min, L.R_max)
            p.period, p.first = spec.patch_source(L.seed, i, L.patch_refill_fast, L.patch_refill_slow, L.t0)
            p.next = p.first
            p.stock = p.initial_remaining = L.patch_capacity
            if L.patch_contact_delay:
                p.origins = bytearray(L.patch_capacity)
            self.patch_left[i] = p.stock
            self._fold_world((W_PATCH_START, bits(L.t0), i, bits(p.x), bits(p.y),
                              bits(p.period), bits(p.first), L.patch_capacity))

    def _patch_window_before(self, t: float) -> None:
        if self.patch_opened or t < self.life.t_open_abs:
            return
        self.patch_opened = True
        for i in range(self.life.patch_count):
            self.led[_LI[f"patch_stock_open_{i}"]] = float(self.patches[i].stock)
            self.patch_initial_open[i] = self.patches[i].initial_remaining
            if self.life.patch_contact_delay:
                self.led[_LI[f"patch_contact_pending_open_{i}"]] = float(self.patches[i].contact_pending)
                self.led[_LI[f"patch_contact_stock_open_{i}"]] = float(self.patches[i].contact_stock)

    def _patch_origin_push(self, p: _Patch, origin: int) -> None:
        K = self.life.patch_capacity
        if (p.origins is None or not 0 <= p.origin_head < K or not 0 <= p.origin_n < K
                or origin not in (2, 3)):
            self.status |= _ST["ledger_mismatch"]
            return
        p.origins[(p.origin_head + p.origin_n) % self.life.patch_capacity] = origin
        p.origin_n += 1
        p.contact_stock += int(origin == 3)

    def _patch_origin_pop(self, p: _Patch) -> int:
        K = self.life.patch_capacity
        if p.origins is None or not 0 <= p.origin_head < K or not 0 < p.origin_n <= K:
            self.status |= _ST["ledger_mismatch"]
            return 0
        origin = p.origins[p.origin_head]
        if origin not in (2, 3):
            self.status |= _ST["ledger_mismatch"]
        p.origins[p.origin_head] = 0
        p.origin_head = (p.origin_head + 1) % self.life.patch_capacity
        p.origin_n -= 1
        p.contact_stock -= int(origin == 3)
        return origin

    def _patch_contact_start(self, i: int, t: float) -> None:
        p = self.patches[i]
        p.contact_pending = 1
        p.contact_due = t + self.life.patch_contact_delay
        if t >= self.life.t_open_abs:
            self.led[_LI[f"patch_contact_starts_{i}"]] += 1.0
        self._fold_world((W_CONTACT_START, bits(t), i, p.contact_starts, bits(p.contact_due)))
        p.contact_starts += 1

    def _patch_contact_mature(self, i: int) -> None:
        L, p = self.life, self.patches[i]
        t = p.contact_due
        self._patch_window_before(t)
        before = p.stock
        admitted = before < L.patch_capacity
        if admitted:
            p.stock += 1
            self._patch_origin_push(p, 3)
        if t >= L.t_open_abs:
            for name in ("source", "supply" if admitted else "spill"):
                self.led[_LI[f"patch_{name}_{i}"]] += 1.0
            self.led[_LI[f"patch_contact_maturities_{i}"]] += 1.0
            self.led[_LI[f"patch_contact_{'supply' if admitted else 'spill'}_{i}"]] += 1.0
        self._fold_world((W_CONTACT_MATURE, bits(t), i, p.contact_starts - 1, before, p.stock, int(admitted)))
        p.contact_pending = 0
        p.contact_due = _INF

    def _patch_source(self, i: int) -> None:
        L, p = self.life, self.patches[i]
        t = p.next
        self._patch_window_before(t)
        before = p.stock
        admitted = before < L.patch_capacity
        if admitted:
            p.stock += 1
            if L.patch_contact_delay:
                self._patch_origin_push(p, 2)
        if t >= L.t_open_abs:
            self.led[_LI[f"patch_source_{i}"]] += 1.0
            self.led[_LI[f"patch_{'supply' if admitted else 'spill'}_{i}"]] += 1.0
        self._fold_world((W_PATCH_SOURCE, bits(t), i, p.arrival_index, before, p.stock, int(admitted)))
        p.arrival_index += 1
        p.next = p.first + float(p.arrival_index) * p.period

    def _patch_nearest(self, t: float) -> tuple[float, float]:
        X, Y = self.dot_at(t)
        best, point = _INF, (0.0, 0.0)
        for p in self.patches[:self.life.patch_count]:
            dx, dy = X - p.x, Y - p.y
            q = dx * dx + dy * dy
            if q < best:
                best, point = q, (p.x, p.y)
        return point

    def _patch_rate(self, px: float, py: float) -> tuple[float, float]:
        L = self.life
        rate, signal = L.lam_bg, 0.0
        for i in range(L.patch_count):
            p = self.patches[i]
            amplitude = spec.patch_amplitude(self.patch_left[i], L.patch_capacity, L.patch_landmark)
            component = L.lam_s * (amplitude * spec.halo(px - p.x, py - p.y, L.sigma))
            rate = rate + component
            signal = signal + component
        return rate, signal

    def _patch_click(self, t: float, counted: bool) -> None:
        L, led = self.life, self.led
        self._patch_window_before(t)
        X, Y = self.dot_at(t)
        slot, outcome, origin, before, after = 4, 0, 0, 0, 0
        if counted:
            led[_LI["clicks"]] += 1.0
        for i in range(L.patch_count):
            p = self.patches[i]
            dx, dy = X - p.x, Y - p.y
            if dx * dx + dy * dy <= L.rho_c * L.rho_c:
                slot = i
                break
        if slot < 4:
            p = self.patches[slot]
            before = p.stock
            if before > 0:
                outcome = 1
                p.stock -= 1
                origin = 1 if p.initial_remaining > 0 else 2
                if origin == 1:
                    p.initial_remaining -= 1
                elif L.patch_contact_delay:
                    origin = self._patch_origin_pop(p)
                if counted:
                    led[_LI["captures"]] += 1.0
                    led[_LI["income"]] = led[_LI["income"]] + L.R_cap
                    led[_LI[f"patch_harvest_{slot}"]] += 1.0
                    led[_LI[f"patch_{'initial' if origin == 1 else 'refill'}_harvest_{slot}"]] += 1.0
                    if origin == 3:
                        led[_LI[f"patch_contact_harvest_{slot}"]] += 1.0
            else:
                outcome = 2
                if counted:
                    led[_LI[f"patch_empty_{slot}"]] += 1.0
                if L.patch_contact_delay and not p.contact_pending:
                    self._patch_contact_start(slot, t)
            after = p.stock
        elif counted:
            led[_LI["patch_geometric_misses"]] += 1.0
        if outcome != 1 and counted:
            led[_LI["misses"]] += 1.0
            led[_LI["cost"]] = led[_LI["cost"]] + L.c_miss
        self._fold_world((W_PATCH_CLICK, bits(t), outcome, slot, before, after, origin))
        self._fold_world((W_CLICK, bits(t), int(outcome == 1), bits(X), bits(Y)))

    def _patch_finish(self, t_end: float) -> None:
        L, led = self.life, self.led
        if t_end <= L.t_open_abs:
            for name in (*spec.PATCH_LEDGER, *spec.CONTACT_LEDGER):
                led[_LI[name]] = 0.0
        else:
            self._patch_window_before(t_end)
            harvested, empty = 0.0, 0.0
            for i in range(L.patch_count):
                p = self.patches[i]
                led[_LI[f"patch_stock_end_{i}"]] = float(p.stock)
                names = ("stock_open", "source", "supply", "spill", "harvest", "empty", "stock_end",
                         "initial_harvest", "refill_harvest")
                values = [led[_LI[f"patch_{name}_{i}"]] for name in names]
                op, source, supply, spill, h, e, end, ih, rh = values
                if (source != supply + spill or op + supply != h + end or op + source != h + spill + end
                        or h != ih + rh or self.patch_initial_open[i] != ih + p.initial_remaining
                        or not 0 <= op <= L.patch_capacity or not 0 <= end <= L.patch_capacity
                        or not 0 <= p.initial_remaining <= end
                        or any(v < 0 or v != math.floor(v) for v in values)):
                    self.status |= _ST["ledger_mismatch"]
                harvested += h
                empty += e
                if L.patch_contact_delay:
                    led[_LI[f"patch_contact_pending_end_{i}"]] = float(p.contact_pending)
                    led[_LI[f"patch_contact_stock_end_{i}"]] = float(p.contact_stock)
                    cc = {name: led[_LI[f"patch_contact_{name}_{i}"]] for name in spec.CONTACT_METRICS}
                    valid_ring = (p.origins is not None and 0 <= p.origin_head < L.patch_capacity
                                  and 0 <= p.origin_n <= L.patch_capacity)
                    queued = ([p.origins[(p.origin_head + k) % L.patch_capacity] for k in range(p.origin_n)]
                              if valid_ring else [])
                    if (cc["pending_open"] + cc["starts"] != cc["maturities"] + cc["pending_end"]
                            or cc["maturities"] != cc["supply"] + cc["spill"]
                            or cc["stock_open"] + cc["supply"] != cc["harvest"] + cc["stock_end"]
                            or cc["starts"] > e or cc["maturities"] > source or cc["supply"] > supply
                            or cc["spill"] > spill or cc["harvest"] > rh or cc["stock_open"] > op
                            or cc["stock_end"] > end or cc["pending_open"] not in (0, 1)
                            or cc["pending_end"] not in (0, 1)
                            or not 0 <= self.patch_initial_open[i] <= op
                            or cc["stock_open"] > op - self.patch_initial_open[i]
                            or any(v < 0 or v != math.floor(v) for v in cc.values())
                            or p.origin_n + p.initial_remaining != p.stock
                            or not valid_ring or p.contact_stock > p.stock - p.initial_remaining
                            or p.contact_starts < cc["starts"] + cc["pending_open"]
                            or (p.contact_pending and (not math.isfinite(p.contact_due) or p.contact_due < t_end))
                            or (not p.contact_pending and p.contact_due != _INF)
                            or any(x not in (2, 3) for x in queued) or queued.count(3) != p.contact_stock):
                        self.status |= _ST["ledger_mismatch"]
            geom = led[_LI["patch_geometric_misses"]]
            if (geom < 0 or geom != math.floor(geom) or led[_LI["captures"]] != harvested
                    or led[_LI["misses"]] != empty + geom
                    or led[_LI["clicks"]] != led[_LI["captures"]] + led[_LI["misses"]]):
                self.status |= _ST["ledger_mismatch"]
        for i in range(L.patch_count):
            p = self.patches[i]
            self._fold_world((W_PATCH_END, bits(t_end), i, p.stock, p.initial_remaining))
        if L.patch_contact_delay:
            for i in range(L.patch_count):
                p = self.patches[i]
                self._fold_world((W_CONTACT_END, bits(t_end), i, p.contact_pending,
                                  bits(p.contact_due if p.contact_pending else 0.0),
                                  p.contact_stock, p.contact_starts))

    def _task_count(self, metric: str) -> None:
        cls = "narrow" if self.task_class == 0 else "broad"
        self.led[_LI[f"{metric}_{cls}"]] += 1.0

    def _task_enter(self, phase: int, t: float) -> None:
        """Enter an externally scheduled task phase, preserving all cellular state and pending inputs."""
        L = self.life
        self.task_phase = phase
        self.task_consumed = False
        self.task_pending_gap = False
        for bl in self.blobs:
            bl.present = False
            bl.t, bl.x, bl.y, bl.vx, bl.vy = t, 0.0, 0.0, 0.0, 0.0
        if phase == TASK_SAMPLE:
            self.task_class = int(spec.draw(L.seed, spec.S_TASK_CLASS, self.task_trial, 0) >= 0.5)
            self.task_carry_counted = False
            bl = self.blobs[self.task_class]
            bl.present = True
            bl.x, bl.y = self.dot_at(t)
            u = spec.draw(L.seed, spec.S_TASK_DURATION, self.task_trial, 0)
            self.task_next = t + (L.sample_min + (L.sample_max - L.sample_min) * u)
        elif phase == TASK_BLANK:
            u = spec.draw(L.seed, spec.S_TASK_DURATION, self.task_trial, 1)
            self.task_next = t + (L.blank_min + (L.blank_max - L.blank_min) * u)
        elif phase == TASK_CHOICE:
            X, Y = self.dot_at(t)
            theta = spec.TWO_PI * spec.draw(L.seed, spec.S_TASK_GEOMETRY, self.task_trial, 0)
            r = L.R_min + (L.R_max - L.R_min) * spec.draw(L.seed, spec.S_TASK_GEOMETRY, self.task_trial, 1)
            dx, dy = r * math.cos(theta), r * math.sin(theta)
            narrow_positive = spec.draw(L.seed, spec.S_TASK_SIDE, self.task_trial, 0) < 0.5
            p, n = (0, 1) if narrow_positive else (1, 0)
            self.blobs[p].x, self.blobs[p].y = X + dx, Y + dy
            self.blobs[n].x, self.blobs[n].y = X - dx, Y - dy
            self.blobs[0].present = self.blobs[1].present = True
            self.task_choice_start = t
            self.task_carry_counted = False
            self.task_next = t + L.choice_T
            if t >= L.t_open_abs:
                self._task_count("choice_opportunities")
        else:
            self.task_next = t + L.reset_T
        b0, b1 = self.blobs
        self._fold_world((W_TASK_PHASE, bits(t), self.task_trial, phase, self.task_class,
                          bits(b0.x), bits(b0.y), bits(b1.x), bits(b1.y)))

    def _task_carry(self) -> None:
        if self.task_choice_start < self.life.t_open_abs and not self.task_carry_counted:
            self._task_count("choice_carry_in")
            self.task_carry_counted = True

    def _task_resolve(self, t: float, outcome: int, slot: int) -> None:
        """Latch one outcome immediately. Removal follows at group end for clicks, immediately for timeout."""
        self.task_consumed = True
        self.task_next = _INF
        if t >= self.life.t_open_abs:
            self._task_carry()
            self._task_count(("choice_timeouts", "correct_choices", "wrong_choices")[outcome])
            if outcome == 1:
                self.led[_LI["income"]] = self.led[_LI["income"]] + self.life.R_cap
            elif outcome == 2:
                self.led[_LI["cost"]] = self.led[_LI["cost"]] + (-self.life.b2_value)
        self._fold_world((W_TASK_RESOLVE, bits(t), self.task_trial, self.task_class, outcome, slot))

    def _task_advance(self) -> None:
        t = self.task_next
        if self.task_phase == TASK_SAMPLE:
            self._task_enter(TASK_BLANK, t)
        elif self.task_phase == TASK_BLANK:
            self._task_enter(TASK_CHOICE, t)
        elif self.task_phase == TASK_CHOICE:
            self._task_resolve(t, 0, 2)
            self._task_enter(TASK_GAP, t)
        else:
            self.task_trial += 1
            self._task_enter(TASK_SAMPLE, t)

    def _task_finish(self, t_end: float) -> None:
        if self.task_phase == TASK_CHOICE and not self.task_consumed and t_end > self.life.t_open_abs:
            self._task_carry()
            self._task_count("unfinished_choices")
        self._fold_world((W_TASK_END, bits(t_end), self.task_trial, self.task_phase, self.task_class))

    def _fold_world(self, words) -> None:
        if self.wlog is not None:
            self.wlog.append(tuple(words))
        ha, hw = self.h[H_ALL], self.h[H_WORLD]
        for w in words:
            ha = spec.splitmix64(ha ^ (w & spec.MASK64))
            hw = spec.splitmix64(hw ^ (w & spec.MASK64))
        self.h[H_ALL], self.h[H_WORLD] = ha, hw

    def dot_at(self, t: float) -> tuple[float, float]:
        if self.n_foot == 0 or t == self.t_x:
            return self.X, self.Y
        k, _e = spec.dot_gain(t - self.t_x, self.life.tau_z, self.gam)
        if self.life.eco:
            fx, fy = self._eff()
            return self.X + fx * k, self.Y + fy * k
        return self.X + self.Fx * k, self.Y + self.Fy * k

    def dot_adv(self, t: float) -> None:
        if t <= self.t_x:
            return
        tau_z = self.life.tau_z
        e = math.exp(-(t - self.t_x) / tau_z)
        if self.n_foot > 0:
            fx, fy = self._eff() if self.life.eco else (self.Fx, self.Fy)
            k = tau_z * (1.0 - e) / self.gam
            dx = fx * k
            dy = fy * k
            self.X = self.X + dx
            self.Y = self.Y + dy
            self.path = self.path + math.sqrt(dx * dx + dy * dy)
        self.Fx = self.Fx * e
        self.Fy = self.Fy * e
        self.t_x = t

    def blob_at(self, i: int, t: float) -> tuple[float, float]:
        bl = self.blobs[i]
        dt = t - bl.t
        return bl.x + bl.vx * dt, bl.y + bl.vy * dt

    def place(self, i: int, cause: int, t: float) -> None:
        L = self.life
        bl = self.blobs[i]
        X, Y = self.dot_at(t)
        bl.x, bl.y = spec.blob_place(L.seed, i, bl.q, X, Y, L.R_min, L.R_max)
        bl.t = t
        if i == 1:
            bl.present = spec.blob_present(L.seed, bl.q, L.b2_p)
        bl.q += 1
        if i == 0 and L.visibility_mode == 1:
            self.bright = True
            self.visibility_next = t + L.visibility_on
        self._fold_world((W_PLACE, bits(t), i, cause, bits(bl.x), bits(bl.y), 1 if bl.present else 0))

    def _timer(self, bl: _Blob) -> None:
        L = self.life
        t = bl.r
        self.place(bl.i, 2, t)
        if bl.i == 0 and t >= L.t_open_abs:
            self.led[_LI["respawns"]] += 1.0
        if bl.i == 0 and len(self.blobs) > 1 and L.b2_mode == 0:
            self.place(1, 3, t)
        bl.r = spec.poisson_next(L.seed, spec.S_RTIME, bl.i, bl.m, t, L.t_resp)
        bl.m += 1

    def _turn(self, bl: _Blob) -> None:
        L = self.life
        t = bl.tau
        bl.x, bl.y = self.blob_at(bl.i, t)
        bl.t = t
        bl.vx, bl.vy = spec.blob_heading(L.seed, bl.i, bl.h, L.v_t)
        bl.h += 1
        self._fold_world((W_TURN, bits(t), bl.i, bits(bl.vx), bits(bl.vy)))
        bl.tau = spec.poisson_next(L.seed, spec.S_TURN, bl.i, bl.k, t, L.tau_turn)
        bl.k += 1

    def _visibility(self) -> None:
        L = self.life
        t = self.visibility_next
        self.bright = not self.bright
        self._fold_world((W_VISIBILITY, bits(t), 0, int(self.bright)))
        if L.visibility_mode == 2:
            duration = L.visibility_on if self.bright else L.visibility_off
            self.visibility_next = spec.poisson_next(L.seed, spec.S_VISIBILITY, 0, self.visibility_k, t, duration)
            self.visibility_k += 1
        else:
            self.visibility_next = _INF

    def world_to(self, t: float) -> None:
        """Run world events strictly below t, with timers before turns before visibility at equal times."""
        if self.life.eco:
            self._eco_world_to(t)
            return
        if self.life.patch_count:
            while True:
                events = [(self.patches[i].next, i, 0) for i in range(self.life.patch_count)]
                if self.life.patch_contact_delay:
                    events += [(p.contact_due, i, 1) for i, p in enumerate(self.patches[:self.life.patch_count])
                               if p.contact_pending]
                at, i, kind = min(events)
                if not at < t:
                    break
                if kind == 0:
                    self._patch_source(i)
                else:
                    self._patch_contact_mature(i)
            self._patch_window_before(t)
            return
        if self.life.task_mode:
            while self.task_next < t:
                self._task_advance()
            return
        while True:
            best = None
            for bl in self.blobs:
                for key in ((bl.r, 0, bl.i), (bl.tau, 1, bl.i)):
                    if key[0] < t and (best is None or key < best):
                        best = key
            key = (self.visibility_next, 2, 0)
            if key[0] < t and (best is None or key < best):
                best = key
            if best is None:
                return
            bl = self.blobs[best[2]]
            if best[1] == 0:
                self._timer(bl)
            elif best[1] == 1:
                self._turn(bl)
            else:
                self._visibility()

    def sample(self, c: float) -> None:
        """9.7.6: the measurement-only sample at integer time c, at the left limit."""
        L, led = self.life, self.led
        self.world_to(c)
        if L.eco:
            self._eco_sample(c)
            return
        if L.task_mode and self.task_phase != TASK_CHOICE:
            return
        X, Y = self.dot_at(c)
        x0, y0 = self._patch_nearest(c) if L.patch_count else self.blob_at(0, c)
        ex = X - x0
        ey = Y - y0
        q = ex * ex + ey * ey
        if L.task_mode:
            x1, y1 = self.blob_at(1, c)
            ex1, ey1 = X - x1, Y - y1
            q = min(q, ex1 * ex1 + ey1 * ey1)
        if c >= L.t_open_abs:
            led[_LI["samples"]] += 1.0
            led[_LI["dist_sum"]] = led[_LI["dist_sum"]] + math.sqrt(q)
            if q <= L.rho_c * L.rho_c:
                led[_LI["zone_samples"]] += 1.0

    def _task_click(self, t: float, counted: bool) -> None:
        L, led = self.life, self.led
        X, Y = self.dot_at(t)
        slot = 2
        if counted:
            led[_LI["clicks"]] += 1.0
        if self.task_phase == TASK_CHOICE and not self.task_consumed:
            for i, radius in ((0, L.rho_c), (1, L.b2_rho)):
                x, y = self.blob_at(i, t)
                dx, dy = X - x, Y - y
                if dx * dx + dy * dy <= radius * radius:
                    slot = i
                    break
        if slot < 2:
            correct = slot == self.task_class
            self._task_resolve(t, 1 if correct else 2, slot)
            self.task_pending_gap = True
            if counted:
                led[_LI["captures" if slot == 0 else "b2_clicks"]] += 1.0
        elif counted:
            led[_LI["misses"]] += 1.0
            led[_LI["cost"]] = led[_LI["cost"]] + L.c_miss
        self._fold_world((W_CLICK, bits(t), slot + 1 if slot < 2 else 0, bits(X), bits(Y)))

    def _click(self, t: float, counted: bool) -> None:
        if self.life.eco:
            self._eco_click(t, counted)
            return
        if self.life.patch_count:
            self._patch_click(t, counted)
            return
        if self.life.task_mode:
            self._task_click(t, counted)
            return
        L, led = self.life, self.led
        X, Y = self.dot_at(t)
        x0, y0 = self.blob_at(0, t)
        ex = X - x0
        ey = Y - y0
        d0 = ex * ex + ey * ey
        if counted:
            led[_LI["clicks"]] += 1.0
        hit2 = False
        if d0 > L.rho_c * L.rho_c and len(self.blobs) > 1 and self.blobs[1].present:
            x1, y1 = self.blob_at(1, t)
            ex1 = X - x1
            ey1 = Y - y1
            hit2 = ex1 * ex1 + ey1 * ey1 <= L.b2_rho * L.b2_rho
        if d0 <= L.rho_c * L.rho_c:
            outcome = 1
            if counted:
                led[_LI["captures"]] += 1.0
                if L.visibility_mode and not self.bright:
                    led[_LI["low_light_captures"]] += 1.0
                led[_LI["income"]] = led[_LI["income"]] + L.R_cap
            self.defer_place.append((0, 1))
            if len(self.blobs) > 1 and L.b2_mode == 0:
                self.defer_place.append((1, 3))
        elif hit2:
            outcome = 2
            if counted:
                led[_LI["b2_clicks"]] += 1.0
                if L.b2_value > 0:
                    led[_LI["income"]] = led[_LI["income"]] + L.b2_value
                elif L.b2_value < 0:
                    led[_LI["cost"]] = led[_LI["cost"]] + (-L.b2_value)
            if L.b2_mode == 1:
                self.defer_place.append((1, 1))
        else:
            outcome = 0
            if counted:
                led[_LI["misses"]] += 1.0
                led[_LI["cost"]] = led[_LI["cost"]] + L.c_miss
        self._fold_world((W_CLICK, bits(t), outcome, bits(X), bits(Y)))

    def _stroke(self, t: float, site: _Site, dz: float, zt: float, zn: float, counted: bool) -> None:
        """9.7.2: an act-plane twitch pulls the dot along the cell's exposed face; at the hotspot it may click."""
        L = self.life
        self.dot_adv(t)
        a, b = site.a, site.b
        nx = 0.0
        ny = 0.0
        for d in L.planar_slots:
            if (a + L.off_a[d], b + L.off_b[d]) not in self.O:
                nx = nx + L.ux[d]
                ny = ny + L.uy[d]
        if dz > 0 and (nx != 0.0 or ny != 0.0):
            gdz = L.g_n * dz
            st = self.strokes[(a, b)]
            e_i = math.exp(-(t - st[2]) / L.tau_z)
            st[0] = st[0] * e_i + gdz * nx
            st[1] = st[1] * e_i + gdz * ny
            st[2] = t
            self.Fx = self.Fx + gdz * nx
            self.Fy = self.Fy + gdz * ny
            if counted:
                self.led[_LI["nudges"]] += 1.0
            if L.eco:
                self._eco_kink()
        if a == 0 and b == 0:
            self.armed, click = spec.key_step(self.armed, zt, zn, L.th_click, L.th_rel)
            if click:
                self._click(t, counted)

    def _rcand(self, t: float, site: _Site, uid: int, j: int, counted: bool) -> None:
        """9.7.5: thin the candidate at the left limit; an accepted one becomes a RECEPTOR at t + d_min."""
        L, led = self.life, self.led
        if counted:
            led[_LI["rec_cand"]] += 1.0
        X, Y = self.dot_at(t)
        ox, oy = L.planar(site.a, site.b)
        px = X + ox
        py = Y + oy
        if L.eco:
            rate = self._eco_light(t, px, py)
        elif L.patch_count:
            rate, _signal = self._patch_rate(px, py)
        else:
            x0, y0 = self.blob_at(0, t)
            signal = (L.lam_s * spec.halo(px - x0, py - y0, L.sigma)
                      if not L.task_mode or self.blobs[0].present else 0.0)
            if L.visibility_mode:
                signal = (1.0 if self.bright else L.visibility_low) * signal
            rate = L.lam_bg + signal
            if len(self.blobs) > 1 and self.blobs[1].present:
                x1, y1 = self.blob_at(1, t)
                rate = rate + L.lam_s * (L.b2_amp * spec.halo(px - x1, py - y1, L.b2_sigma))
        accepted = spec.draw(L.seed, spec.S_RACC, uid, j) * L.lam_max < rate
        self._fold_world((9, bits(t), uid, j, 1 if accepted else 0))
        if accepted:
            if counted:
                led[_LI["rec_accept"]] += 1.0
            L.push_world(t + L.d_min, site, (RECEPTOR, uid, j))

    def _end_group(self, t: float) -> None:
        for add, ab in self.defer_O:
            target = self.O0 if add >= 2 else self.O  # ABI 8: 2/3 remove/add in the sense plane
            if add & 1:
                target.add(ab)
            else:
                target.discard(ab)
        if self.life.eco:
            for g in self.ag:
                g["vis"] = 1 if (g["state"] != 3 and not (g["type"] == 4 and g["state"] == 1)) else 0
            for P in self.plants:
                P["vis"] = 1 if P["state"] == 2 else 0
        for i, cause in self.defer_place:
            self.place(i, cause, t)
        self.defer_O = []
        self.defer_place = []
        if self.life.task_mode and self.task_pending_gap:
            self.task_pending_gap = False
            self._task_enter(TASK_GAP, t)

    # --------------------------------------------------------------------------------------- the eco world (9.8)
    def _eco_start(self) -> None:
        L, e = self.life, self.life.e
        self.eco_n = {k: int(e[f"eco_{k}"]) for k in ("n_src", "n_ag", "n_wall", "n_shelter", "n_fertile")}
        self.cur_speed, self.cur_head = e["eco_cur_speed"], e["eco_cur_heading"]
        self.cur_turn, self.cur_turn_max = e["eco_cur_turn"], e["eco_cur_turn_max"]
        self.puff_sig0, self.puff_D, self.puff_life = e["eco_puff_sigma0"], e["eco_puff_D"], e["eco_puff_life"]
        self.puff_cut, self.puff_cap, self.landmark = e["eco_puff_cut"], int(e["eco_puff_cap"]), e["eco_landmark"]
        self.sun = (math.cos(e["eco_sun_heading"]), math.sin(e["eco_sun_heading"]))
        self.vib_vref, self.r_body, self.arena = e["eco_vib_vref"], e["eco_r_body"], e["eco_arena"]
        self.eco2 = L.eco_mode == 2
        self.kill_hits, self.occlude = int(e["eco_kill_hits"]), e["eco_occlude"] != 0.0
        self.home = (e["eco_home_x"], e["eco_home_y"], e["eco_home_r"], e["eco_home_sigma"],
                     [e[f"eco_home_b{k}"] for k in range(spec.N_SPEC)])
        self.carry_cap, self.carry_mult = int(e["eco_carry_cap"]), e["eco_carry_mult"]
        self.carry_digest, self.carry_drag = e["eco_carry_digest"], e["eco_carry_drag"]
        self.plant_cap, self.plant_cost = int(e["eco_plant_cap"]), e["eco_plant_cost"]
        self.ripen = (e["eco_ripen_min"], e["eco_ripen_max"], e["eco_ripe_window"])
        self.plant_value, self.plant_sig = e["eco_plant_value"], e["eco_plant_sigma"]
        self.plant_light = e["eco_plant_light"]
        self.plant_b = [e[f"eco_plant_b{k}"] for k in range(spec.N_SPEC)]
        self.soil_sig, self.soil_b = e["eco_soil_sigma"], [e[f"eco_soil_b{k}"] for k in range(spec.N_SPEC)]
        self.puffs: list = []  # (t, ox, oy, a[4]) in release order, the oldest first
        self.cur_ts, self.cur_Ax, self.cur_Ay = L.t0, 0.0, 0.0
        self.cur_ux, self.cur_uy = self.cur_speed * math.cos(self.cur_head), self.cur_speed * math.sin(self.cur_head)
        self.cur_next = (spec.poisson_next(L.seed, spec.S_ECO_CUR, 0, 0, L.t0, self.cur_turn) if self.cur_turn > 0
                         else _INF)
        self.cur_k = 1
        self.src = []
        for i in range(self.eco_n["n_src"]):
            q = {f: e[f"src{i}_{f}"] for f in spec.SRC_FIELDS}
            S = dict(x=q["x"], y=q["y"], value=q["value"], cap=int(q["cap"]), stock=int(q["cap"]), period=q["period"],
                     light=q["light"], sigma=q["sigma"], puff_rate=q["puff"],
                     b=[q[f"b{k}"] for k in range(spec.N_SPEC)], arrival_index=0, puff_k=1)
            first = L.t0 + q["phase"]
            S["first"] = first if first > L.t0 else math.nextafter(L.t0, _INF)
            S["next"] = S["first"] if S["period"] > 0 else _INF
            S["next_puff"] = (spec.poisson_next(L.seed, spec.S_ECO_PUFF, i, 0, L.t0, 1.0 / S["puff_rate"])
                              if S["puff_rate"] > 0 else _INF)
            self.src.append(S)
        self.src_left = [S["stock"] for S in self.src]
        self.ag = []
        for i in range(self.eco_n["n_ag"]):
            q = {f: e[f"ag{i}_{f}"] for f in spec.AG_FIELDS}
            g = dict(q)
            g.update(type=int(q["type"]), state=0, vis=1, t=L.t0, vx=0.0, vy=0.0, speed=0.0, t_stop=_INF, until=L.t0,
                     b=[q[f"b{k}"] for k in range(spec.N_SPEC)], q=0, lt=L.t0, lx=0.0, ly=0.0)
            g["next_look"] = L.t0 + q["look"] * spec.draw(L.seed, spec.S_ECO_AG, i, spec.MASK64)
            self.ag.append(g)
        self.walls = [tuple(e[f"wall{i}_{f}"] for f in spec.WALL_FIELDS) for i in range(self.eco_n["n_wall"])]
        self.shelters = [tuple(e[f"shelter{i}_{f}"] for f in spec.DISK_FIELDS) for i in range(self.eco_n["n_shelter"])]
        self.fertile = [tuple(e[f"fertile{i}_{f}"] for f in spec.DISK_FIELDS) for i in range(self.eco_n["n_fertile"])]
        self.plants = [dict(state=0, vis=0, x=0.0, y=0.0, t_ripe=0.0, t_spoil=0.0, id=0) for _ in range(spec.N_PLANT)]
        self.items: list = []  # [value, due, id]
        self.plant_ids = self.item_ids = 0
        self.blk = [0, 0]  # blocked direction along x, y (+1 / -1 / 0)
        self.blk_w = [0, 0]
        self.kink = (_INF, 0, 0, 0)  # (t, kind, wall, face)
        self.samp = (0.0, 0.0)
        self.gam0 = 1.0
        self.hits_all = 0
        self.eco_dead = False
        self.O0: set = set()
        self._fold_world((48, bits(L.t0), self.eco_n["n_src"], self.eco_n["n_ag"], self.eco_n["n_wall"],
                          bits(self.cur_ux), bits(self.cur_uy)))

    def _eff(self) -> tuple[float, float]:
        fx = 0.0 if (self.blk[0] > 0 and self.Fx > 0.0) or (self.blk[0] < 0 and self.Fx < 0.0) else self.Fx
        fy = 0.0 if (self.blk[1] > 0 and self.Fy > 0.0) or (self.blk[1] < 0 and self.Fy < 0.0) else self.Fy
        return fx, fy

    def _eco_set_gam(self) -> None:
        self.gam = self.gam0 * (1.0 + self.carry_drag * float(len(self.items)))

    @staticmethod
    def _seg_enter(X, Y, ex, ey, x0, x1, y0, y1):
        """(s, face) of the segment P + s E entering the open box, or (inf, 0) (kernel.c seg_enter)."""
        if ex == 0.0:
            if not (x0 < X < x1):
                return _INF, 0
            sx0, sx1 = -_INF, _INF
        else:
            a, b = (x0 - X) / ex, (x1 - X) / ex
            sx0, sx1 = (a, b) if a < b else (b, a)
        if ey == 0.0:
            if not (y0 < Y < y1):
                return _INF, 0
            sy0, sy1 = -_INF, _INF
        else:
            a, b = (y0 - Y) / ey, (y1 - Y) / ey
            sy0, sy1 = (a, b) if a < b else (b, a)
        s_in = sx0 if sx0 > sy0 else sy0
        s_out = sx1 if sx1 < sy1 else sy1
        if not (s_in < s_out) or not (s_out > 0.0) or not (s_in < 1.0):
            return _INF, 0
        return (0.0 if s_in < 0.0 else s_in), (0 if sx0 >= sy0 else 1)

    def _eco_contact(self, kind: int, w: int, face: int) -> None:
        x0, x1, y0, y1 = self.walls[w]
        rb = self.r_body
        if kind == 0:
            fx, fy = self._eff()
            if face == 0:
                self.X = x0 - rb if fx > 0.0 else x1 + rb
                self.blk[0], self.blk_w[0] = (1 if fx > 0.0 else -1), w
            else:
                self.Y = y0 - rb if fy > 0.0 else y1 + rb
                self.blk[1], self.blk_w[1] = (1 if fy > 0.0 else -1), w
            if self.t_x >= self.life.t_open_abs:
                self.led[_LI["eco_wall_contacts"]] += 1.0
        else:
            self.blk[face] = 0
        self._fold_world((44, bits(self.t_x), kind, w, face, bits(self.X), bits(self.Y)))

    def _eco_kink(self) -> None:
        L = self.life
        self.kink = (_INF, 0, 0, 0)
        if not L.eco or not self.walls or self.n_foot == 0:
            return
        rb = self.r_body
        for _ in range(8):
            if self.blk[0] and self.Fx != 0.0 and (self.blk[0] > 0) != (self.Fx > 0.0):
                self.blk[0] = 0
            if self.blk[1] and self.Fy != 0.0 and (self.blk[1] > 0) != (self.Fy > 0.0):
                self.blk[1] = 0
            fx, fy = self._eff()
            if fx == 0.0 and fy == 0.0:
                return
            kinf = L.tau_z / self.gam
            ex, ey = fx * kinf, fy * kinf
            best, bw, bf, bk = _INF, -1, 0, 0
            for w, (x0, x1, y0, y1) in enumerate(self.walls):
                sv, face = self._seg_enter(self.X, self.Y, ex, ey, x0 - rb, x1 + rb, y0 - rb, y1 + rb)
                if sv < best:
                    best, bw, bf, bk = sv, w, face, 0
            if self.blk[0] and ey != 0.0:
                x0, x1, y0, y1 = self.walls[self.blk_w[0]]
                lim = y1 + rb if ey > 0.0 else y0 - rb
                sv = (lim - self.Y) / ey
                if 0.0 <= sv < 1.0 and sv < best:
                    best, bw, bf, bk = sv, self.blk_w[0], 0, 1
            if self.blk[1] and ex != 0.0:
                x0, x1, y0, y1 = self.walls[self.blk_w[1]]
                lim = x1 + rb if ex > 0.0 else x0 - rb
                sv = (lim - self.X) / ex
                if 0.0 <= sv < 1.0 and sv < best:
                    best, bw, bf, bk = sv, self.blk_w[1], 1, 1
            if bw < 0:
                return
            if best > 0.0:
                tk = self.t_x - L.tau_z * math.log(1.0 - best)
                if not tk > self.t_x:
                    tk = math.nextafter(self.t_x, _INF)
                self.kink = (tk, bk, bw, bf)
                return
            self._eco_contact(bk, bw, bf)

    def _eco_amp(self, i: int, stock: int) -> float:
        return self.landmark + (1.0 - self.landmark) * (float(stock) / float(self.src[i]["cap"]))

    def _cur_A(self, t: float) -> tuple[float, float]:
        return self.cur_Ax + self.cur_ux * (t - self.cur_ts), self.cur_Ay + self.cur_uy * (t - self.cur_ts)

    @staticmethod
    def _ag_pos(g: dict, t: float) -> tuple[float, float]:
        tt = t if t < g["t_stop"] else g["t_stop"]
        dt = tt - g["t"]
        return g["x"] + g["vx"] * dt, g["y"] + g["vy"] * dt

    def _look_motion(self, g: dict, t: float, X: float, Y: float) -> float:
        """Eco v2 (9.8.7): the body's mean speed since agent g's previous look, over vib_vref, at most 1."""
        dx, dy, dt = X - g["lx"], Y - g["ly"], t - g["lt"]
        if not dt > 0.0:
            return 1.0
        s = math.sqrt(dx * dx + dy * dy) / dt
        return 1.0 if s >= self.vib_vref else s / self.vib_vref

    def _sheltered(self, x: float, y: float) -> bool:
        for sx, sy, r in self.shelters:
            dx, dy = x - sx, y - sy
            if dx * dx + dy * dy <= r * r:
                return True
        return False

    def _eco_conc(self, k: int, t: float, px: float, py: float) -> float:
        ax, ay = self._cur_A(t)
        C = 0.0
        s02 = self.puff_sig0 * self.puff_sig0
        for pt, ox, oy, a in self.puffs:
            age = t - pt
            if age > self.puff_life or a[k] == 0.0:
                continue
            s2 = s02 + 2.0 * self.puff_D * age
            dx, dy = px - (ox + ax), py - (oy + ay)
            d2 = dx * dx + dy * dy
            if d2 > self.puff_cut * s2:
                continue
            C = C + a[k] * (s02 / s2) * math.exp(-d2 / (2.0 * s2))
        for g in self.ag:
            if not g["vis"] or g["b"][k] == 0.0:
                continue
            x, y = self._ag_pos(g, t)
            C = C + g["b"][k] * spec.halo(px - x, py - y, g["sigma"])
        hx, hy, hr, hs, hb = self.home
        if hr > 0.0 and hb[k] != 0.0:
            C = C + hb[k] * spec.halo(px - hx, py - hy, hs)
        if self.soil_b[k] != 0.0:
            for fx, fy, _r in self.fertile:
                C = C + self.soil_b[k] * spec.halo(px - fx, py - fy, self.soil_sig)
        if self.plant_b[k] != 0.0:
            for P in self.plants:
                if P["vis"]:
                    C = C + self.plant_b[k] * spec.halo(px - P["x"], py - P["y"], self.plant_sig)
        return C

    def _occluded(self, sx: float, sy: float, px: float, py: float) -> bool:
        if not self.occlude:
            return False
        for x0, x1, y0, y1 in self.walls:
            if self._seg_enter(sx, sy, px - sx, py - sy, x0, x1, y0, y1)[0] < 1.0:
                return True
        return False

    def _eco_light(self, t: float, px: float, py: float) -> float:
        L = self.life
        rate = L.lam_bg
        for i, S in enumerate(self.src):
            if S["light"] == 0.0 or self._occluded(S["x"], S["y"], px, py):
                continue
            rate = rate + L.lam_s * ((S["light"] * self._eco_amp(i, self.src_left[i]))
                                     * spec.halo(px - S["x"], py - S["y"], S["sigma"]))
        if self.plant_light != 0.0:
            for P in self.plants:
                if P["vis"] and not self._occluded(P["x"], P["y"], px, py):
                    rate = rate + L.lam_s * (self.plant_light * spec.halo(px - P["x"], py - P["y"], self.plant_sig))
        for g in self.ag:
            if not g["vis"] or g["light"] == 0.0:
                continue
            x, y = self._ag_pos(g, t)
            if not self._occluded(x, y, px, py):
                rate = rate + L.lam_s * (g["light"] * spec.halo(px - x, py - y, g["sigma"]))
        return rate

    def _sense_face(self, site: _Site) -> tuple[float, float]:
        L = self.life
        fx = fy = 0.0
        for d in L.planar_slots:
            if (site.a + L.off_a[d], site.b + L.off_b[d]) not in self.O0:
                fx = fx + L.ux[d]
                fy = fy + L.uy[d]
        n = math.sqrt(fx * fx + fy * fy)
        return (fx / n, fy / n) if n > 0.0 else (0.0, 0.0)

    def _mod_rate(self, m: int, site: _Site, t: float, px: float, py: float) -> float:
        L = self.life
        bg, sc, K, kind = L.mod_bg[m], L.mod_s[m], L.mod_K[m], L.mod_kind[m]
        if kind == 1:
            C = self._eco_conc(L.mod_arg[m], t, px, py)
            return bg + sc * (C / (C + K))
        if kind == 2:
            nx, ny = self._sense_face(site)
            vx = vy = 0.0
            if self.n_foot > 0:
                e = math.exp(-(t - self.t_x) / L.tau_z)
                fx, fy = self._eff()
                vx, vy = fx * e / self.gam, fy * e / self.gam
            ux, uy = self.cur_ux - vx, self.cur_uy - vy
            p = -(ux * nx + uy * ny) / K
            return bg + sc * spec.clip(p, 0.0, 1.0)
        if kind == 3:
            if self.eco2 and self._sheltered(px, py):  # v2: shelter cover is felt
                return bg + sc
            r2 = K * K
            for x0, x1, y0, y1 in self.walls:
                dx = x0 - px if px < x0 else (px - x1 if px > x1 else 0.0)
                dy = y0 - py if py < y0 else (py - y1 if py > y1 else 0.0)
                if dx * dx + dy * dy <= r2:
                    return bg + sc
            for g in self.ag:
                if not g["vis"]:
                    continue
                x, y = self._ag_pos(g, t)
                dx, dy = px - x, py - y
                if dx * dx + dy * dy <= r2:
                    return bg + sc
            return bg
        if kind == 4:
            V = 0.0
            for g in self.ag:
                if not g["vis"] or g["speed"] == 0.0 or not t < g["t_stop"]:
                    continue
                x, y = self._ag_pos(g, t)
                V = V + (g["speed"] / self.vib_vref) * spec.halo(px - x, py - y, K)
            return bg + sc * (V / (V + 1.0))
        if kind == 5:
            nx, ny = self._sense_face(site)
            p = nx * self.sun[0] + ny * self.sun[1]
            return bg + sc * (p if p > 0.0 else 0.0)
        return bg

    def _rcand_m(self, t: float, site: _Site, uid: int, m: int, j: int, counted: bool) -> None:
        L, led = self.life, self.led
        if counted:
            led[_LI[f"mod_cand_{m}"]] += 1.0
        X, Y = self.dot_at(t)
        ox, oy = L.planar(site.a, site.b)
        rate = self._mod_rate(m, site, t, X + ox, Y + oy)
        accepted = spec.draw(L.seed, spec.S_RACC_M, uid, m, j) * L.lam_m[m] < rate
        self._fold_world((30, bits(t), uid, m, j, 1 if accepted else 0))
        if accepted:
            if counted:
                led[_LI[f"mod_accept_{m}"]] += 1.0
            L.push_world(t + L.d_min, site, (RECEPTORM, uid, m, j))

    def _eco_refill(self, i: int) -> None:
        S = self.src[i]
        t = S["next"]
        before = S["stock"]
        if S["stock"] < S["cap"]:
            S["stock"] += 1
        self._fold_world((40, bits(t), i, before, S["stock"]))
        S["arrival_index"] += 1
        S["next"] = S["first"] + float(S["arrival_index"]) * S["period"]

    def _eco_puff(self, i: int) -> None:
        L, S = self.life, self.src[i]
        t = S["next_puff"]
        while self.puffs and t - self.puffs[0][0] > self.puff_life:
            self.puffs.pop(0)
        if len(self.puffs) == self.puff_cap:
            self.puffs.pop(0)
        ax, ay = self._cur_A(t)
        amp = self._eco_amp(i, S["stock"])
        ox, oy = S["x"] - ax, S["y"] - ay
        self.puffs.append((t, ox, oy, [b * amp for b in S["b"]]))
        if t >= L.t_open_abs:
            self.led[_LI["eco_puffs"]] += 1.0
        self._fold_world((41, bits(t), i, S["puff_k"], bits(ox), bits(oy), bits(amp)))
        S["next_puff"] = spec.poisson_next(L.seed, spec.S_ECO_PUFF, i, S["puff_k"], t, 1.0 / S["puff_rate"])
        S["puff_k"] += 1

    def _eco_turn(self) -> None:
        L = self.life
        t = self.cur_next
        self.cur_Ax, self.cur_Ay = self._cur_A(t)
        self.cur_ts = t
        u = spec.draw(L.seed, spec.S_ECO_CUR, 1, self.cur_k)
        self.cur_head = self.cur_head + self.cur_turn_max * (2.0 * u - 1.0)
        self.cur_ux = self.cur_speed * math.cos(self.cur_head)
        self.cur_uy = self.cur_speed * math.sin(self.cur_head)
        self._fold_world((42, bits(t), self.cur_k, bits(self.cur_ux), bits(self.cur_uy)))
        self.cur_next = spec.poisson_next(L.seed, spec.S_ECO_CUR, 0, self.cur_k, t, self.cur_turn)
        self.cur_k += 1

    def _ag_stop(self, g: dict) -> None:
        g["t_stop"] = _INF
        if g["vx"] == 0.0 and g["vy"] == 0.0:
            return
        best = _INF
        for x0, x1, y0, y1 in self.walls:
            sv = self._seg_enter(g["x"], g["y"], g["vx"] * g["look"], g["vy"] * g["look"], x0, x1, y0, y1)[0]
            if sv < best:
                best = sv
        if best < _INF:
            g["t_stop"] = g["t"] + best * g["look"]

    @staticmethod
    def _ag_head(g: dict, dx: float, dy: float, v: float) -> None:
        n = math.sqrt(dx * dx + dy * dy)
        if n > 0.0:
            g["vx"], g["vy"], g["speed"] = v * (dx / n), v * (dy / n), v
        else:
            g["vx"] = g["vy"] = g["speed"] = 0.0

    def _ag_look(self, i: int) -> None:
        L, led = self.life, self.led
        g = self.ag[i]
        t = g["next_look"]
        cnt = t >= L.t_open_abs
        x, y = self._ag_pos(g, t)
        stopped = not t < g["t_stop"] and g["speed"] > 0.0
        g["x"], g["y"], g["t"] = x, y, t
        X, Y = self.dot_at(t)
        dx, dy = X - x, Y - y
        d2 = dx * dx + dy * dy
        rs2 = g["r_sense"] * g["r_sense"]
        rc2 = g["r_contact"] * g["r_contact"]
        shel, st0 = self._sheltered(X, Y), g["state"]
        u0, u1, u2 = (spec.draw(L.seed, spec.S_ECO_AG, i, g["q"], k) for k in range(3))
        hit, plant_hit, tx, ty = False, -1, 0.0, 0.0
        ty_, st = g["type"], g["state"]
        pd = g["p"] * self._look_motion(g, t, X, Y) if self.eco2 and ty_ == 1 else g["p"]  # v2: still is unseen
        g["lt"], g["lx"], g["ly"] = t, X, Y
        if ty_ == 1:
            if st == 2 and t >= g["until"]:
                g["state"] = 0
            if g["state"] == 0 and not shel and d2 <= rs2 and u0 < pd:
                g["state"], g["until"] = 1, t + g["t_state"]
                if cnt:
                    led[_LI["eco_detections"]] += 1.0
            elif g["state"] == 1 and (shel or t >= g["until"] or d2 > 4.0 * rs2):
                g["state"] = 0
            if g["state"] == 1 and d2 <= rc2 and not self.eco_dead:
                hit = True
                g["state"], g["until"] = 2, t + g["t_rest"]
            tx, ty = dx, dy
        elif ty_ == 2:
            if st == 2 and t >= g["until"]:
                g["state"] = 0
            if g["state"] == 0 and not shel and d2 <= rc2 and u0 < g["p"] and not self.eco_dead:
                hit = True
                g["state"], g["until"] = 2, t + g["t_rest"]
                if cnt:
                    led[_LI["eco_detections"]] += 1.0
        elif ty_ in (3, 4, 5):
            if st == 3:
                if t >= g["until"]:
                    g["state"] = 0
                    g["x"], g["y"] = g["rx"], g["ry"]
            elif st == 1:
                if ty_ == 5:
                    qx, qy = g["rx"] - x, g["ry"] - y
                    if qx * qx + qy * qy <= 0.0625:
                        g["state"], g["until"] = 3, t + g["t_rest"]
                    elif t >= g["until"]:
                        g["state"] = 0
                elif t >= g["until"]:
                    g["state"] = 0
            elif d2 <= rs2 and u0 < g["p"]:
                g["state"], g["until"] = 1, t + g["t_state"]
                if cnt:
                    led[_LI["eco_alarms"]] += 1.0
            if ty_ == 3:
                tx, ty = -dx, -dy
            elif ty_ == 5:
                tx, ty = g["rx"] - g["x"], g["ry"] - g["y"]
        elif ty_ == 6:
            best, bi = _INF, -1
            for k, P in enumerate(self.plants):
                if P["state"] != 2:
                    continue
                qx, qy = P["x"] - x, P["y"] - y
                q = qx * qx + qy * qy
                if q <= rs2 and q < best:
                    best, bi = q, k
            if bi >= 0 and best <= rc2:
                plant_hit = bi
                g["state"] = 0
            elif bi >= 0:
                g["state"] = 1
                tx, ty = self.plants[bi]["x"] - x, self.plants[bi]["y"] - y
            else:
                g["state"] = 0
        r2 = g["x"] * g["x"] + g["y"] * g["y"]
        if g["state"] == 0 and ty_ != 2:
            if r2 > self.arena * self.arena:
                self._ag_head(g, -g["x"], -g["y"], g["v1"])
            elif u1 < 0.3 or st0 != 0 or stopped or g["speed"] == 0.0:
                h = spec.TWO_PI * u2
                self._ag_head(g, math.cos(h), math.sin(h), g["v1"])
            else:
                self._ag_head(g, g["vx"], g["vy"], g["v1"])
        elif g["state"] == 1 and ty_ not in (4, 2):
            self._ag_head(g, tx, ty, g["v2"])
        else:
            self._ag_head(g, 0.0, 0.0, 0.0)
        g["vis"] = 1 if (g["state"] != 3 and not (ty_ == 4 and g["state"] == 1)) else 0
        self._ag_stop(g)
        if hit:
            if cnt:
                led[_LI["eco_hits"]] += 1.0
                led[_LI["eco_damage_cost"]] = led[_LI["eco_damage_cost"]] + g["value"]
                led[_LI["cost"]] = led[_LI["cost"]] + g["value"]
            self.hits_all += 1
            if self.kill_hits > 0 and self.hits_all >= self.kill_hits:
                self.eco_dead = True
        if plant_hit >= 0:
            self.plants[plant_hit]["state"] = 0
            self.plants[plant_hit]["vis"] = 0
            if cnt:
                led[_LI["eco_pest_eaten"]] += 1.0
        self._fold_world((45, bits(t), i, g["state"], bits(g["vx"]), bits(g["vy"]),
                          int(hit) | (2 if plant_hit >= 0 else 0), bits(g["x"]), bits(g["y"])))
        g["q"] += 1
        g["next_look"] = t + g["look"]

    def _eco_digest(self) -> None:
        L, led = self.life, self.led
        value, due, iid = self.items[0]
        t = due
        self.dot_adv(t)
        self.items.pop(0)
        if t >= L.t_open_abs:
            led[_LI["eco_digested"]] += 1.0
            led[_LI["eco_digest_income"]] = led[_LI["eco_digest_income"]] + value
            led[_LI["income"]] = led[_LI["income"]] + value
            led[_LI["captures"]] += 1.0
        self._eco_set_gam()
        self._fold_world((46, bits(t), iid, bits(value)))
        self._eco_kink()

    def _eco_plant_event(self, i: int, spoil: bool) -> None:
        P = self.plants[i]
        t = P["t_spoil"] if spoil else P["t_ripe"]
        if spoil:
            P["state"], P["vis"] = 0, 0
            if t >= self.life.t_open_abs:
                self.led[_LI["eco_spoiled"]] += 1.0
        else:
            P["state"], P["vis"] = 2, 1
            if t >= self.life.t_open_abs:
                self.led[_LI["eco_ripened"]] += 1.0
        self._fold_world((47, bits(t), i, P["id"], P["state"]))

    def _eco_world_to(self, t: float) -> None:
        while True:
            best, kind, idx = _INF, -1, -1
            cands = []
            for i, S in enumerate(self.src):
                if S["period"] > 0:
                    cands.append((S["next"], 0, i))
            for i, S in enumerate(self.src):
                if S["puff_rate"] > 0:
                    cands.append((S["next_puff"], 1, i))
            cands.append((self.cur_next, 2, 0))
            for i, g in enumerate(self.ag):
                cands.append((g["next_look"], 3, i))
            cands.append((self.kink[0], 4, 0))
            if self.items:
                cands.append((self.items[0][1], 5, 0))
            for i, P in enumerate(self.plants):
                if P["state"] == 1:
                    cands.append((P["t_ripe"], 6, i))
                elif P["state"] == 2:
                    cands.append((P["t_spoil"], 7, i))
            for tt, k, ix in cands:  # strictly smaller times only: ties keep (kind, index) order
                if tt < best:
                    best, kind, idx = tt, k, ix
            if not best < t:
                return
            if kind == 0:
                self._eco_refill(idx)
            elif kind == 1:
                self._eco_puff(idx)
            elif kind == 2:
                self._eco_turn()
            elif kind == 3:
                self._ag_look(idx)
            elif kind == 4:
                tk, kk, kw, kf = self.kink
                self.dot_adv(tk)
                self._eco_contact(kk, kw, kf)
                self._eco_kink()
            elif kind == 5:
                self._eco_digest()
            else:
                self._eco_plant_event(idx, kind == 7)

    def _eco_click(self, t: float, counted: bool) -> None:
        L, led = self.life, self.led
        X, Y = self.dot_at(t)
        r2 = L.rho_c * L.rho_c
        outcome, idx, val = 0, -1, 0.0
        if counted:
            led[_LI["clicks"]] += 1.0
        for i, g in enumerate(self.ag):
            if outcome:
                break
            if not 3 <= g["type"] <= 5 or g["state"] == 3:
                continue
            x, y = self._ag_pos(g, t)
            dx, dy = X - x, Y - y
            if dx * dx + dy * dy <= r2:
                outcome, idx, val = 5, i, g["value"]
                g["x"], g["y"], g["t"] = x, y, t
                g["vx"] = g["vy"] = g["speed"] = 0.0
                g["t_stop"] = _INF
                g["state"], g["until"] = 3, t + g["t_rest"]
                if counted:
                    led[_LI["eco_prey_caught"]] += 1.0
                    led[_LI["eco_prey_income"]] = led[_LI["eco_prey_income"]] + val
                    led[_LI["income"]] = led[_LI["income"]] + val
                    led[_LI["captures"]] += 1.0
        for i, P in enumerate(self.plants):
            if outcome:
                break
            if P["state"] != 2:
                continue
            dx, dy = X - P["x"], Y - P["y"]
            if dx * dx + dy * dy <= r2:
                outcome, idx, val = 6, i, self.plant_value
                P["state"] = 0
                if counted:
                    led[_LI["eco_harvested"]] += 1.0
                    led[_LI["eco_harvest_income"]] = led[_LI["eco_harvest_income"]] + val
                    led[_LI["income"]] = led[_LI["income"]] + val
                    led[_LI["captures"]] += 1.0
        for i, S in enumerate(self.src):
            if outcome:
                break
            dx, dy = X - S["x"], Y - S["y"]
            if S["stock"] <= 0 or dx * dx + dy * dy > r2:
                continue
            S["stock"] -= 1
            idx, val = i, S["value"]
            if val < 0.0:
                outcome = 2
                if counted:
                    led[_LI["eco_toxin_eaten"]] += 1.0
                    led[_LI["eco_toxin_cost"]] = led[_LI["eco_toxin_cost"]] + (-val)
                    led[_LI["cost"]] = led[_LI["cost"]] + (-val)
            elif self.carry_cap > 0 and len(self.items) < self.carry_cap:
                outcome = 3
                self.items.append((val, t + self.carry_digest, self.item_ids))
                self.item_ids += 1
                if counted:
                    led[_LI["eco_picked"]] += 1.0
                self._eco_set_gam()
            else:
                outcome = 1
                if counted:
                    led[_LI["eco_food_eaten"]] += 1.0
                    led[_LI["eco_food_income"]] = led[_LI["eco_food_income"]] + val
                    led[_LI["income"]] = led[_LI["income"]] + val
                    led[_LI["captures"]] += 1.0
        if outcome == 0 and self.carry_cap > 0 and self.items:
            hx, hy, hr, _hs, _hb = self.home
            dx, dy = X - hx, Y - hy
            if dx * dx + dy * dy <= hr * hr:
                outcome, idx = 4, len(self.items)
                for value, _due, _id in self.items:
                    v = value * self.carry_mult
                    val = val + v
                    if counted:
                        led[_LI["eco_delivered"]] += 1.0
                        led[_LI["eco_deliver_income"]] = led[_LI["eco_deliver_income"]] + v
                        led[_LI["income"]] = led[_LI["income"]] + v
                        led[_LI["captures"]] += 1.0
                self.items = []
                self._eco_set_gam()
        if outcome == 0 and self.plant_cap > 0:
            fertile = any((X - fx) * (X - fx) + (Y - fy) * (Y - fy) <= r * r for fx, fy, r in self.fertile)
            free_slot, near, trample = -1, False, -1
            for i in range(self.plant_cap):
                P = self.plants[i]
                if P["state"] == 0:
                    if free_slot < 0:
                        free_slot = i
                    continue
                dx, dy = X - P["x"], Y - P["y"]
                if dx * dx + dy * dy <= r2:
                    near = True
                    if P["state"] == 1 and trample < 0:
                        trample = i
            if self.eco2 and trample >= 0:  # v2: a tap on a growing plant destroys it
                outcome, idx = 8, trample
                self.plants[trample]["state"] = 0
                self.plants[trample]["vis"] = 0
                if counted:
                    led[_LI["eco_spoiled"]] += 1.0
            elif fertile and not near and free_slot >= 0:
                outcome, idx = 7, free_slot
                P = self.plants[free_slot]
                P.update(state=1, vis=0, x=X, y=Y, id=self.plant_ids)
                self.plant_ids += 1
                rmin, rmax, win = self.ripen
                P["t_ripe"] = t + (rmin + (rmax - rmin) * spec.draw(L.seed, spec.S_ECO_PLANT, P["id"], 0))
                P["t_spoil"] = P["t_ripe"] + win
                if counted:
                    led[_LI["eco_planted"]] += 1.0
                    led[_LI["eco_plant_cost"]] = led[_LI["eco_plant_cost"]] + self.plant_cost
                    led[_LI["cost"]] = led[_LI["cost"]] + self.plant_cost
        if outcome == 0 and counted:
            led[_LI["misses"]] += 1.0
            led[_LI["cost"]] = led[_LI["cost"]] + L.c_miss
        self._fold_world((43, bits(t), outcome, idx, bits(val), bits(X), bits(Y)))
        self._fold_world((W_CLICK, bits(t), 0 if outcome == 0 else 1, bits(X), bits(Y)))
        if outcome in (3, 4):
            self._eco_kink()

    def _eco_sample(self, c: float) -> None:
        L, led = self.life, self.led
        X, Y = self.dot_at(c)
        if c >= L.t_open_abs:
            led[_LI["samples"]] += 1.0
            best = _INF
            for S in self.src:
                if S["stock"] <= 0 or S["value"] <= 0.0:
                    continue
                dx, dy = X - S["x"], Y - S["y"]
                q = dx * dx + dy * dy
                if q < best:
                    best = q
            if best < _INF:
                d = math.sqrt(best)
                led[_LI["dist_sum"]] = led[_LI["dist_sum"]] + d
                if best <= L.rho_c * L.rho_c:
                    led[_LI["zone_samples"]] += 1.0
                if d <= L.rho_c + 1.0:
                    led[_LI["eco_near_food_samples"]] += 1.0
            if self._sheltered(X, Y):
                led[_LI["eco_shelter_samples"]] += 1.0
            threat = False
            for g in self.ag:
                if threat:
                    break
                if g["type"] not in (1, 2):
                    continue
                x, y = self._ag_pos(g, c)
                dx, dy = X - x, Y - y
                q = dx * dx + dy * dy
                if ((g["type"] == 1 and g["state"] == 1 and q <= 36.0)
                        or (g["type"] == 2 and g["state"] != 2 and q <= 9.0)):
                    threat = True
            if threat:
                led[_LI["eco_threat_samples"]] += 1.0
                v = 0.0
                if self.n_foot > 0:
                    e = math.exp(-(c - self.t_x) / L.tau_z)
                    fx0, fy0 = self._eff()
                    fx, fy = fx0 * e / self.gam, fy0 * e / self.gam
                    v = math.sqrt(fx * fx + fy * fy)
                if v < 0.02:
                    led[_LI["eco_still_samples"]] += 1.0
            hx, hy, hr, _hs, _hb = self.home
            if hr > 0.0:
                dx, dy = X - hx, Y - hy
                if dx * dx + dy * dy <= hr * hr:
                    led[_LI["eco_home_samples"]] += 1.0
            if self.items:
                led[_LI["eco_loaded_samples"]] += 1.0
            if self.cur_speed > 0.0:
                ux, uy = self.cur_ux / self.cur_speed, self.cur_uy / self.cur_speed
                mx, my = X - self.samp[0], Y - self.samp[1]
                cr = mx * uy - my * ux
                led[_LI["eco_upflow_path"]] = led[_LI["eco_upflow_path"]] + (-(mx * ux + my * uy))
                led[_LI["eco_crossflow_path"]] = led[_LI["eco_crossflow_path"]] + (-cr if cr < 0.0 else cr)
        self.samp = (X, Y)

    def _eco_finish(self, t_end: float) -> None:
        for i, S in enumerate(self.src):
            if not 0 <= S["stock"] <= S["cap"]:
                self.status |= _ST["ledger_mismatch"]
            self._fold_world((49, bits(t_end), i, S["stock"]))
        if not 0 <= len(self.items) <= min(self.carry_cap, spec.N_ITEM):
            self.status |= _ST["ledger_mismatch"]
        planted = sum(1 for P in self.plants if P["state"] != 0)
        self._fold_world((50, bits(t_end), len(self.items), planted, self.hits_all, int(self.eco_dead)))
        self.led[_LI["eco_killed"]] = float(int(self.eco_dead))


    # ------------------------------------------------------------------------------------------- records (9.1)
    def _fold(self, kind: int, words) -> None:
        fam = _FAMILY.get(kind)
        ha = self.h[H_ALL]
        hf = self.h[fam] if fam is not None else 0
        for w in words:
            ha = spec.splitmix64(ha ^ (w & spec.MASK64))
            if fam is not None:
                hf = spec.splitmix64(hf ^ (w & spec.MASK64))
        self.h[H_ALL] = ha
        if fam is not None:
            self.h[fam] = hf

    def _tick_cost(self, t: float, t_prev: float, sp: float, z: int) -> None:
        L, led = self.life, self.led
        if t > L.t_open_abs:
            dl = t - _max(t_prev, L.t_open_abs)
            led[_LI["live_time"]] += dl
            led[_LI["sec_int"]] += sp * dl
            led[_LI["cost"]] = led[_LI["cost"]] + L.c_live * dl
            led[_LI["cost"]] = led[_LI["cost"]] + L.c_sec * (sp * dl)
            col = "live_S" if z == 0 else ("live_M" if z == 1 else "live_H")
            led[_LI[col]] += dl

    def _log_fate(self, row: tuple) -> None:
        self.fate_n += 1
        cap = self.life.fate_cap
        if cap > 0:
            if len(self.fate) < cap:
                self.fate.append(row)
            else:
                self.status |= _ST["fate_overflow"]

    def group(self, t: float, recs: list) -> None:
        """One time group: records with one t, already sorted by (sk, seq)."""
        L, led = self.life, self.led
        counted = t >= L.t_open_abs
        catch = L.catch
        if catch:
            self.world_to(t)
            if L.patch_count:
                self.patch_left[:] = [p.stock for p in self.patches]
            if L.eco:
                self.src_left = [S["stock"] for S in self.src]
        for rec in recs:
            if self.records is not None:
                self.records.append(rec)
            _, sk, _, kind, p = rec
            site = L.sites[sk]
            tb = bits(t)
            if kind == R_SPIKE:
                uid, kap, n_out, dz, zt, zn = p
                if counted:
                    led[_LI["spikes"]] += 1.0
                    led[_LI["kappa_sum"]] += kap
                    led[_LI["contact_events"]] += float(n_out)
                    led[_LI["cost"]] = led[_LI["cost"]] + L.c_spike
                    led[_LI["cost"]] = led[_LI["cost"]] + L.c_tw * kap
                    led[_LI["cost"]] = led[_LI["cost"]] + L.c_msg * float(n_out)
                if kap > 0:
                    if not catch:
                        self.world_adv(t)
                        self.A = self.A + dz
                        if self.above == 0 and self.A / self.n > L.th:
                            self.above = 1
                            if counted:
                                led[_LI["beats"]] += 1.0
                    elif site.z == 1 and not L.flag("motor_off", t):
                        self._stroke(t, site, dz, zt, zn, counted)
                self.raster_n += 1
                if L.raster_cap > 0:
                    if len(self.raster_t) < L.raster_cap:
                        self.raster_t.append(t)
                        self.raster_uid.append(uid)
                    else:
                        self.status |= _ST["raster_overflow"]
                self._fold(kind, (1, tb, uid, bits(kap), n_out))
            elif kind == R_TICK:
                uid, t_prev, sp = p
                self._tick_cost(t, t_prev, sp, site.z)
                self._fold(kind, (8, tb, uid))
            elif kind == R_CHEM:
                sec, dec, clamp = p
                led[_LI["morph_secreted"]] += sec
                led[_LI["morph_decayed"]] += dec
                if clamp:
                    self.status |= _ST["chem_clamp"]
                    if counted:
                        led[_LI["chem_clamps"]] += 1.0
            elif kind == R_PACKET:
                sender, target, tsk, a0, a1 = p
                if counted:
                    led[_LI["packets"]] += 1.0
                self.flying.append((t + L.d_min, tsk, sender, a0, a1, t))
                self._fold(kind, (6, tb, sender, target, bits(a0), bits(a1)))
            elif kind == R_LOST:
                sender, target, a0, a1 = p
                led[_LI["morph_lost"]] = led[_LI["morph_lost"]] + a0 + a1
                self._fold(kind, (7, tb, sender, target, bits(a0), bits(a1)))
            elif kind == R_CLAIM:
                mother, daughter, tsk = p
                self.inflight += 1
                if counted:
                    led[_LI["claims"]] += 1.0
                    led[_LI["cost"]] = led[_LI["cost"]] + L.c_div
                self._fold(kind, (4, tb, mother, daughter, tsk))
            elif kind == R_RESOLVE:
                daughter, mother, res = p
                self.inflight -= 1
                if res == 2:
                    self.status |= _ST["wall"]
                if counted:
                    led[_LI["rejects"]] += 1.0 if res == 1 else 0.0
                    led[_LI["rejects_wall"]] += 1.0 if res == 2 else 0.0
                if res != 0:
                    self._log_fate((3, daughter, mother, site.a, site.b, res - 1, site.z, t, 0.0, (0.0,) * spec.G_MAX))
                self._fold(kind, (5, tb, daughter, res))
            elif kind == R_BIRTH:
                uid, mother, k, initial, g = p
                if catch:
                    self.dot_adv(t)
                    ab = (site.a, site.b)
                    self.cols[ab] = self.cols.get(ab, 0) + 1
                    if self.cols[ab] == 1:
                        self.n_fill = spec.filled_footprint(self.cols, L.base)
                        if L.eco:
                            self.gam0 = spec.drag(self.n_fill, L.drag_exp)
                            self._eco_set_gam()
                        else:
                            self.gam = spec.drag(self.n_fill, L.drag_exp)
                    if site.z == 0:
                        self.n_foot += 1
                        if L.eco:
                            self.defer_O.append((3, (site.a, site.b)))
                    elif site.z == 1:
                        self.strokes[(site.a, site.b)] = [0.0, 0.0, t]
                        self.defer_O.append((True, (site.a, site.b)))
                    if L.eco:
                        self._eco_kink()
                else:
                    self.world_adv(t)
                self.n += 1
                self.n_plane[min(site.z, 2)] += 1
                if not initial:
                    if counted:
                        led[_LI["births"]] += 1.0
                    led[_LI["last_birth"]] = t
                self._log_fate((1, uid, mother, site.a, site.b, k, site.z, t, 0.0, g))
                self._fold(kind, (2, tb, uid, mother, sk, k))
            elif kind == R_DEATH:
                uid, cause, zt, content, age, g, mother = p
                if catch:
                    self.dot_adv(t)
                    ab = (site.a, site.b)
                    self.cols[ab] -= 1
                    if self.cols[ab] == 0:
                        del self.cols[ab]
                        self.n_fill = spec.filled_footprint(self.cols, L.base)
                        if self.n_fill > 0:
                            if L.eco:
                                self.gam0 = spec.drag(self.n_fill, L.drag_exp)
                                self._eco_set_gam()
                            else:
                                self.gam = spec.drag(self.n_fill, L.drag_exp)
                    if site.z == 0:
                        self.n_foot -= 1
                        if L.eco:
                            self.defer_O.append((2, (site.a, site.b)))
                    elif site.z == 1:
                        st = self.strokes[(site.a, site.b)]
                        e_i = math.exp(-(t - st[2]) / L.tau_z)
                        self.Fx = self.Fx - st[0] * e_i
                        self.Fy = self.Fy - st[1] * e_i
                        self.defer_O.append((False, (site.a, site.b)))
                    if L.eco:
                        self._eco_kink()
                    self.n -= 1
                else:
                    self.world_adv(t)
                    self.A = self.A - zt
                    if self.A < 0:
                        self.A = 0.0
                    self.n -= 1
                    if self.n == 0:
                        self.A = 0.0
                self.n_plane[min(site.z, 2)] -= 1
                if counted:
                    led[_LI["kills" if cause == 3 else "deaths"]] += 1.0
                led[_LI["morph_lost"]] = led[_LI["morph_lost"]] + content
                self._log_fate((2, uid, mother, site.a, site.b, cause, site.z, t, age, g))
                self._fold(kind, (3, tb, uid, cause))
            elif kind == R_RCAND:
                uid, j = p
                self._rcand(t, site, uid, j, counted)
            elif kind == R_RECEPT:
                uid, n_rec, g_r = p
                if counted:
                    led[_LI["rec_events"]] += float(n_rec)
                    ga = abs(g_r) * float(n_rec)
                    led[_LI["rec_gain"]] = led[_LI["rec_gain"]] + ga
                    led[_LI["cost"]] = led[_LI["cost"]] + L.c_rec * ga
                self._fold_world((10, tb, uid, n_rec, bits(g_r)))
            elif kind == R_RCANDM:
                uid, m, j = p
                if catch:
                    self._rcand_m(t, site, uid, m, j, counted)
            elif kind == R_RECEPTM:
                uid, m, n_rec, g_r = p
                ga = abs(g_r) * float(n_rec)
                if counted:
                    led[_LI[f"mod_events_{m}"]] += float(n_rec)
                    led[_LI[f"mod_gain_{m}"]] = led[_LI[f"mod_gain_{m}"]] + ga
                    led[_LI["cost"]] = led[_LI["cost"]] + L.c_rec * ga
                self._fold_world((31, tb, uid, m, n_rec, bits(g_r)))
            else:  # pragma: no cover
                raise AssertionError(f"unknown record kind {kind}")
        if catch:
            self._end_group(t)
        if self.n > self.n_peak:
            self.n_peak = self.n
        if self.n == 0 and self.inflight == 0 and not self.extinct:
            self.extinct = True
            self.status |= _ST["extinct"]
            led[_LI["t_ext"]] = t
        if len(self.flying) > 256:
            self.flying = [x for x in self.flying if x[0] >= t]

    def close(self, t_end: float, guard_bits: int, n_fold: int) -> None:
        """Section 9.5, after the last time group with t < t_end; ``all`` folds the first ``n_fold`` columns."""
        L, led = self.life, self.led
        if L.catch:
            self.world_to(t_end)  # the samples before t_end were taken at the guard checks
            self.dot_adv(t_end)
            if L.task_mode:
                self._task_finish(t_end)
            if L.patch_count:
                self._patch_finish(t_end)
            if L.eco:
                self._eco_finish(t_end)
            led[_LI["path"]] = self.path
            led[_LI["X_end"]] = self.X
            led[_LI["Y_end"]] = self.Y
        else:
            self.world_adv(t_end)
        for sk in sorted(L.sites):
            c = L.sites[sk].occ
            if c is None:
                continue
            self._tick_cost(t_end, c.t_prev, c.th[KSEC0] + c.th[KSEC1], c.site.z)
            led[_LI["morph_content_end"]] = led[_LI["morph_content_end"]] + L.content(c)
        s = 0.0
        for _t_arr, _tsk, _snd, a0, a1, _t_send in sorted(x for x in self.flying if x[5] < t_end <= x[0]):
            s = s + a0
            s = s + a1
        led[_LI["morph_inflight_end"]] = s
        self.status |= guard_bits
        guarded = guard_bits & (_ST["guard_cells"] | _ST["guard_events"])
        gc = L.c_live * float(L.n_max) * (L.t1 - t_end) if guarded else 0.0
        c_b2 = -L.b2_value if L.b2_value < 0 else 0.0
        col = L.c_live * led[_LI["live_time"]]
        col = col + L.c_spike * led[_LI["spikes"]]
        col = col + L.c_tw * led[_LI["kappa_sum"]]
        col = col + L.c_msg * led[_LI["contact_events"]]
        col = col + L.c_div * led[_LI["claims"]]
        col = col + L.c_sec * led[_LI["sec_int"]]
        col = col + L.c_miss * led[_LI["misses"]]
        col = col + L.c_rec * led[_LI["rec_gain"]]
        wrong = (led[_LI["wrong_choices_narrow"]] + led[_LI["wrong_choices_broad"]]
                 if L.task_mode else led[_LI["b2_clicks"]])
        col = col + c_b2 * wrong
        for m in range(1, SM):
            col = col + L.c_rec * led[_LI[f"mod_gain_{m}"]]
        col = col + led[_LI["eco_toxin_cost"]]
        col = col + led[_LI["eco_damage_cost"]]
        col = col + led[_LI["eco_plant_cost"]]
        net = led[_LI["income"]] - col - gc
        led[_LI["guard_charge"]] = gc
        led[_LI["net"]] = net
        led[_LI["F"]] = net / (L.T - L.t_open)
        if abs(led[_LI["cost"]] - col) > 1e-9 * _max(1.0, abs(col)):
            self.status |= _ST["ledger_mismatch"]
        if L.task_mode:
            for cls in ("narrow", "broad"):
                opened = led[_LI[f"choice_opportunities_{cls}"]] + led[_LI[f"choice_carry_in_{cls}"]]
                resolved = sum(led[_LI[f"{key}_{cls}"]] for key in (
                    "correct_choices", "wrong_choices", "choice_timeouts", "unfinished_choices"))
                if opened != resolved:
                    self.status |= _ST["ledger_mismatch"]
        led[_LI["n_end"]] = float(self.n)
        led[_LI["n_peak"]] = float(self.n_peak)
        led[_LI["t_end"]] = t_end
        led[_LI["events"]] = float(L.events)
        led[_LI["arrivals"]] = float(L.n_arr)
        led[_LI["arrivals_dropped"]] = float(L.n_drop)
        led[_LI["ticks"]] = float(L.n_ticks)
        led[_LI["status"]] = float(self.status)
        led[_LI["n_S_end"]] = float(self.n_plane[0])
        led[_LI["n_M_end"]] = float(self.n_plane[1])
        led[_LI["n_H_end"]] = float(self.n_plane[2])
        ha = self.h[H_ALL]
        for x in led[:n_fold]:
            ha = spec.splitmix64(ha ^ bits(x))
        self.h[H_ALL] = ha


# ------------------------------------------------------------------------------------------------------------- life
class _Life:
    """One life: sites, cells, the event queue, the handlers of section 7 and a scheduler of section 11."""

    def __init__(self, wv, lat: dict, gt, prog, init, seeds, raster_cap: int, fate_cap: int, keep_records: bool,
                 out_abi: spec.Abi = V3):
        wi = V8.WORLD_INDEX
        wv = [float(x) for x in wv]
        for key in _FLOAT_KEYS:
            setattr(self, key, wv[wi[key]])
        for key in _INT_KEYS:
            setattr(self, key, int(wv[wi[key]]))
        self.out_abi = out_abi
        self.t1 = self.t0 + self.T
        self.t_open_abs = self.t0 + self.t_open
        self.t_fork_abs = self.t0 + self.t_fork
        self.lockstep = bool(self.flags & _F["lockstep"])
        if self.lockstep:
            self.jit = 0.0
            self.tick_jit = 0.0
        self.program = bool(self.flags & _F["program_mode"])
        self.catch = self.world_kind == 1
        self.lam_max = (self.lam_bg + self.lam_s * float(self.patch_count) if self.patch_count else
                        self.lam_bg + self.lam_s * (1.0 + self.b2_amp))
        # ABI 8: the eco block and the modality slots, by name
        self.e = {k: wv[wi[k]] for k in (*spec.ECO_KEYS, *spec.MOD_KEYS)}
        self.eco_mode = int(self.e["eco_mode"])  # 1: eco world; 2: plus the eco v2 rules (9.8.7)
        self.eco = self.eco_mode >= 1
        if self.eco:
            self.lam_max = self.lam_bg + self.lam_s * spec.eco_light_bound(self.e)
        self.mod_kind, self.mod_arg = [0] * SM, [0] * SM
        self.mod_bg, self.mod_s, self.mod_K, self.lam_m = [0.0] * SM, [0.0] * SM, [0.0] * SM, [0.0] * SM
        for m in range(1, SM):
            q = {f: self.e[f"mod{m}_{f}"] for f in spec.MOD_FIELDS}
            self.mod_kind[m], self.mod_arg[m] = int(q["kind"]), int(q["arg"])
            self.mod_bg[m], self.mod_s[m], self.mod_K[m] = q["lam_bg"], q["lam_s"], q["K"]
            self.lam_m[m] = q["lam_bg"] + q["lam_s"] if self.mod_kind[m] != 0 else 0.0
        self.seed, self.tie_seed, self.order_seed, self.salt = (int(s) & spec.MASK64 for s in seeds)
        self.raster_cap, self.fate_cap, self.keep_records = int(raster_cap), int(fate_cap), keep_records

        self.kind, self.base, self.D = lat["kind"], lat["base"], lat["D"]
        self.off_a, self.off_b, self.off_z, self.back = lat["off_a"], lat["off_b"], lat["off_z"], lat["back"]
        self.prev, self.next = lat["prev"], lat["next"]
        self.ux, self.uy, self.uz = lat["ux"], lat["uy"], lat["uz"]
        self.planar_slots = [d for d in range(self.D) if self.off_z[d] == 0]
        self.hex_xy = self.base == "hex"
        # in-stack slots per height (4.3): slot d of a cell at height z leads to a site that exists
        self.instack = [[0 <= z + self.off_z[d] < self.L_max for d in range(self.D)] for z in range(self.L_max)]

        if self.program:
            p = [float(x) for x in prog]
            self.rows = [p[i * V8.P:(i + 1) * V8.P] for i in range(_NROW)]
            sc = p[_NROW * V8.P:]
            for name, i in _PS.items():
                setattr(self, "p_" + name, sc[i])
            self.Dm = (self.p_Dm0, self.p_Dm1)
            self.km = (self.p_km0, self.p_km1)
        else:
            g = [float(x) for x in gt]
            sl = V8.GENOME_SLICES
            self.W = g[sl["W"][0]:sl["W"][1]]
            self.gb = g[sl["b"][0]:sl["b"][1]]
            self.lam = g[sl["lam"][0]:sl["lam"][1]]
            self.g0 = g[sl["s0"][0]:sl["s0"][1]]
            self.Q = g[sl["Q"][0]:sl["Q"][1]]
            self.A = g[sl["A"][0]:sl["A"][1]]
            self.a0 = g[sl["a0"][0]:sl["a0"][1]]
            self.Dm = tuple(g[sl["Dm"][0]:sl["Dm"][1]])
            self.km = tuple(g[sl["km"][0]:sl["km"][1]])
        self.init = init  # [(a, b, z, row)]

        self.sites: dict[int, _Site] = {}
        self.heap: list = []
        self.ctr = 0
        self.tie_cache: dict[int, int] = {}
        self.local = None  # window scheduler: (sk, local heap, window end) of the site being visited
        self.out = None  # records of the batches being processed
        self.bt, self.bsk, self.seq = 0.0, 0, 0
        self.n_alive = 0  # simulator counts in processing order (oracle cap only)
        self.n_inflight = 0
        self.cap_t = -_INF  # the oracle cap reads n_alive + n_inflight at the left limit of each time (11.3)
        self.cap_count = 0
        self.events = 0  # guard counter: FIRE + live TICK + ARRIVAL (delivered or dropped)
        self.n_arr = self.n_drop = self.n_ticks = 0
        self.next_c = self.t0 + 1.0  # next integer time at which the guards are checked (and CATCH samples taken)
        self.acct = _Accountant(self)

    # ----------------------------------------------------------------------------------------------- plumbing
    def flag(self, name: str, t: float) -> bool:
        bit = _F[name]
        return bool(self.flags & bit) or (bool(self.fork_flags & bit) and t >= self.t_fork_abs)

    def planar(self, a: int, b: int) -> tuple[float, float]:
        """The planar offset of column (a, b) in the dot's frame (4.3)."""
        if self.hex_xy:
            return float(a) + 0.5 * float(b), float(b) * S32
        return float(a), float(b)

    def site(self, a: int, b: int, z: int) -> _Site:
        sk = spec.sitekey(a, b, z)
        s = self.sites.get(sk)
        if s is None:
            if not 0 <= z < self.L_max:
                raise AssertionError("a message or claim left the stack")
            s = self.sites[sk] = _Site(a, b, z)
        return s

    def _tie(self, sk: int) -> int:
        tie = self.tie_cache.get(sk)
        if tie is None:
            tie = self.tie_cache[sk] = spec.hash64(self.tie_seed, spec.S_TIE, sk)
        return tie

    def push(self, t: float, site: _Site, ev: tuple) -> None:
        self.ctr += 1
        key = spec.splitmix64(self.salt ^ self.ctr) if self.salt else self.ctr
        loc = self.local
        if loc is not None and t < loc[2]:
            if site.sk != loc[0] or t <= self.bt:
                raise AssertionError("causality: an event landed inside the current window or batch")
            heapq.heappush(loc[1], (t, key, ev))
            return
        if site.sk == self.bsk and t <= self.bt:
            raise AssertionError("causality: a self event at or before its own batch")
        heapq.heappush(self.heap, (t, self._tie(site.sk), site.sk, key, ev))

    def push_world(self, t: float, site: _Site, ev: tuple) -> None:
        """An event the accountant sends while it consumes a time group (a RECEPTOR, 9.7.5): always to the heap."""
        if self.local is not None:
            raise AssertionError("the accountant runs between batches, never inside a window visit")
        self.ctr += 1
        key = spec.splitmix64(self.salt ^ self.ctr) if self.salt else self.ctr
        heapq.heappush(self.heap, (t, self._tie(site.sk), site.sk, key, ev))

    def neighbour(self, src: _Site, d: int) -> _Site:
        return self.site(src.a + self.off_a[d], src.b + self.off_b[d], src.z + self.off_z[d])

    def send(self, src: _Site, d: int, t: float, ev: tuple) -> None:
        """A message through slot d of ``src``; ``ev[1]`` is filled with the receiver slot back[d]."""
        dst = self.neighbour(src, d)
        src.nsend += 1
        self.push(t, dst, (ev[0], self.back[d], src.nsend) + ev[1:])

    def emit(self, kind: int, payload: tuple) -> None:
        self.out.append((self.bt, self.bsk, self.seq, kind, payload))
        self.seq += 1

    def content(self, c: _Cell) -> float:
        x = c.m[0] + c.m[1]
        for pk in sorted(c.inbox, key=lambda p: (p[0], p[1])):
            x = x + pk[3] + pk[4]
        return x

    # ------------------------------------------------------------------------------------------- membrane (7.1)
    def vnow(self, c: _Cell, t: float) -> float:
        if t < c.t_r:
            return 0.0
        if c.t_a >= c.t_r:
            t0, v0 = c.t_a, c.v_a
        else:
            t0, v0 = c.t_r, 0.0
        b = c.th[KB]
        return b + (v0 - b) * math.exp(-(t - t0) / c.tau)

    def predict(self, c: _Cell) -> None:
        c.ver += 1
        b = c.th[KB]
        if b > 1.0:
            if c.t_a >= c.t_r:
                t0, v0 = c.t_a, c.v_a
            else:
                t0, v0 = c.t_r, 0.0
            if v0 < 1.0:
                self.push(t0 + c.tau * math.log((b - v0) / (b - 1.0)), c.site, (THRESHOLD, c.uid, c.ver))

    def traces(self, c: _Cell, t: float) -> None:
        e = math.exp(-(t - c.t_tr) / c.th[KTTR])
        c.f = c.f * e
        c.r0 = c.r0 * e
        c.r1 = c.r1 * e
        c.rho = c.rho * e
        rh = c.rhom
        for m in range(1, SM):
            rh[m] = rh[m] * e
        c.t_tr = t

    def membrane(self, c: _Cell, t: float, arr: list, kicks: list, thr: bool, n_rec: int = 0, n_rm=None) -> None:
        any_rm = bool(n_rm) and any(n_rm)
        if n_rec > 0:
            self.emit(R_RECEPT, (c.uid, n_rec, c.th[KGR]))
        if any_rm:
            for m in range(1, SM):
                if n_rm[m] > 0:
                    self.emit(R_RECEPTM, (c.uid, m, n_rm[m], c.th[KGR + m]))
        if arr or n_rec > 0 or any_rm:
            self.traces(c, t)
            n0 = n1 = 0
            for _slot, mask in arr:
                n0 += mask & 1
                n1 += (mask >> 1) & 1
            c.r0 = c.r0 + float(n0)
            c.r1 = c.r1 + float(n1)
            c.rho = c.rho + float(n_rec)
            if any_rm:
                for m in range(1, SM):
                    c.rhom[m] = c.rhom[m] + float(n_rm[m])
        if t < c.t_r:
            return
        S = 0.0
        for slot, mask in arr:
            if mask & 1:
                S = S + c.w_eff[slot][0]
            if mask & 2:
                S = S + c.w_eff[slot][1]
        for kick in kicks:
            S = S + kick
        if n_rec > 0:
            S = S + c.th[KGR] * float(n_rec)
        if any_rm:
            for m in range(1, SM):
                if n_rm[m] > 0:
                    S = S + c.th[KGR + m] * float(n_rm[m])
        v = (1.0 if thr else self.vnow(c, t)) + S
        c.v_a = spec.q10(v)
        c.t_a = t
        if c.v_a >= 1.0:
            self.fire(c, t)
        else:
            self.predict(c)

    def reanchor(self, c: _Cell, t: float) -> None:
        """TICK step 5 (and STUCK): round the membrane at t with the phenotype in force; fire if it reaches 1."""
        if t >= c.t_r:
            c.v_a = spec.q10(self.vnow(c, t))
            c.t_a = t
            if c.v_a >= 1.0:
                self.fire(c, t)

    def fire(self, c: _Cell, t: float) -> None:
        th = c.th
        c.v_a = 0.0
        c.t_a = t
        c.t_r = t + th[KREF]
        self.traces(c, t)
        c.f = c.f + 1.0
        c.nspk += 1
        self.events += 1
        n_live = sum(1 for u in c.view if u != EMPTY)
        e0 = 1 if th[KE0] != 0.0 else 0
        e1 = 1 if th[KE1] != 0.0 else 0
        n_ch = e0 + e1
        n_out = n_live * n_ch
        if (n_ch > 0 and not self.flag("contacts_off", t)
                and not (c.site.z >= 2 and self.flag("hidden_off", t))):
            lateral_off = self.flag("lateral_off", t)
            mask = e0 | (e1 << 1)
            for d in range(self.D):
                if c.view[d] == EMPTY:
                    continue
                if lateral_off and self.off_z[d] == 0:
                    continue
                if self.drop_p > 0 and spec.draw(self.seed, spec.S_DROP, c.uid, c.nspk, d) < self.drop_p:
                    continue
                u = spec.draw(self.seed, spec.S_JIT, c.uid, c.nspk, d)
                dl = c.dc[d] * (1.0 + self.jit * (2.0 * u - 1.0)) + th[KDEL]
                if dl < self.d_min:
                    dl = self.d_min
                self.send(c.site, d, t + dl, (ARRIVAL, c.view[d], mask))
        dz = zt = zn = 0.0
        kap = th[KKAP]
        if kap > 0:
            zt = c.tw * math.exp(-(t - c.t_tw) / self.tau_z)
            zn = zt + kap
            if zn > 1.0:
                zn = 1.0
            dz = zn - zt
            c.tw = zn
            c.t_tw = t
        self.emit(R_SPIKE, (c.uid, kap, n_out, dz, zt, zn))
        self.predict(c)

    # -------------------------------------------------------------------------------------------- phenotype (8)
    def decode(self, c: _Cell) -> list[float]:
        g, A, a0 = c.g, self.A, self.a0
        y = []
        for p in range(V8.P):
            acc = a0[p]
            for k in range(spec.G_MAX):
                acc = acc + A[p * spec.G_MAX + k] * g[k]
            y.append(acc)
        return V8.decode_knobs(y)

    def select(self, c: _Cell, n_view: int) -> list[float]:
        """Program-mode selector of section 7.5 (tick# before its increment); it does not read the plane."""
        if c.row >= 0:
            r = c.row
        elif self.p_zyg_row != 0 and c.init == 0:
            r = _ROW["zygote"]
        elif n_view == 0:
            r = _ROW["alone"]
        elif c.ntick < self.p_juv_ticks:
            r = _ROW["juvenile"]
        elif self.p_nv_rim > 0 and n_view < self.p_nv_rim:
            r = _ROW["rim"]
        else:
            r = _ROW["contact"]
        return list(self.rows[r])

    def derive(self, c: _Cell) -> None:
        th = c.th
        smax = 0.0
        for d in range(self.D):
            if c.view[d] == EMPTY:
                sd = 0.0
            else:
                sd = th[KPOL0] * (c.inc[d][0] - c.m[0]) + th[KPOL1] * (c.inc[d][1] - c.m[1])
            c.s[d] = sd
            smax = _max(smax, abs(sd))
        for d in range(self.D):
            shat = c.s[d] / (smax + spec.SHAT_EPS)
            c.w_eff[d][0] = spec.q8(th[KW0] * (1.0 + th[KA0] * shat))
            c.w_eff[d][1] = spec.q8(th[KW1] * (1.0 + th[KA1] * shat))

    def stuck_override(self, c: _Cell) -> None:
        c.th[KB] = 2.0
        c.th[KTAU] = 1.0
        c.th[KREF] = 0.5
        c.tau = c.th[KTAU] * c.taumis
        for d in range(self.D):
            c.w_eff[d][0] = 0.0
            c.w_eff[d][1] = 0.0

    # ------------------------------------------------------------------------------------------------ TICK (7.4)
    def tick(self, c: _Cell, t: float) -> None:
        D = self.D
        self.events += 1
        if t >= self.t_open_abs:
            self.n_ticks += 1
        dt = t - c.t_prev
        # 1. packets
        if c.inbox:
            for _t_arr, snd, slot, a0, a1, c0, c1 in sorted(c.inbox, key=lambda p: (p[0], p[1])):
                c.m[0] = c.m[0] + a0
                c.m[1] = c.m[1] + a1
                if c.view[slot] == snd:  # only the slot's current contact sets its concentration (15.9)
                    c.inc[slot][0] = c0
                    c.inc[slot][1] = c1
            c.inbox = []
        # 2. living and secretion cost over [t_prev, t) with the phenotype in force there
        sp0, sp1 = c.th[KSEC0], c.th[KSEC1]
        self.emit(R_TICK, (c.uid, c.t_prev, sp0 + sp1))
        # 3. inputs; "open" = in stack and EMPTY (4.3)
        self.traces(c, t)
        view = c.view
        z = c.site.z
        instack = self.instack[z]
        n_view = sum(1 for u in view if u != EMPTY)
        flank = [0] * D
        is_open = [False] * D
        fb = 0
        any_open = False
        for e in range(D):
            if instack[e] and view[e] == EMPTY:
                is_open[e] = any_open = True
                flank[e] = (view[self.prev[e]] != EMPTY) + (view[self.next[e]] != EMPTY)
                if flank[e] > fb:
                    fb = flank[e]
        # 4. genes (or the program timer)
        if not (self.flag("identity_clamp", t) or self.flag("freeze", t)):
            if self.program:
                c.timer = c.timer + self.p_timer_step
            else:
                ttr = c.th[KTTR]
                is_s = 1.0 if self.catch and z == 0 else 0.0
                is_m = 1.0 if self.catch and z == 1 else 0.0
                x = list(c.g) + [c.m[0] / (1.0 + c.m[0]), c.m[1] / (1.0 + c.m[1]), c.f / ttr, c.r0 / ttr,
                                 c.r1 / ttr, n_view / D, c.rho / ttr, is_s, is_m]
                x += [c.rhom[m] / ttr for m in range(1, SM)]  # ABI 8 receptor traces
                if self.flag("genes_blind", t):
                    for j in (*range(18, 23), *range(25, 25 + SM - 1)):  # activity, contact, receptors; cues stay
                        x[j] = 0.0
                s = []
                for k in range(spec.G_MAX):
                    p = self.gb[k]
                    row = k * V8.NIN
                    for j in range(V8.NIN):
                        p = p + self.W[row + j] * x[j]
                    s.append(spec.sigmoid(p))
                for k in range(spec.G_MAX):
                    c.g[k] = c.g[k] + self.lam[k] * (s[k] - c.g[k])
        # 5. identity
        self.reanchor(c, t)
        freeze = self.flag("freeze", t)
        if not (freeze or self.flag("pheno_fixed", t)):
            c.th = self.select(c, n_view) if self.program else self.decode(c)
            c.tau = c.th[KTAU] * c.taumis
        if not freeze:
            self.derive(c)
        if c.stuck:
            self.stuck_override(c)
        self.predict(c)
        if self.catch:
            self.mod_activate(c, t)
        th = c.th
        # 6. death
        if not (self.flag("apoptosis_off", t) or freeze):
            if (self.program and self.p_prune != 0 and c.timer_birth >= self.p_k_keep
                    and c.timer >= self.p_k_die):
                self.apoptosis(c, t, 2)
                return
            if th[KPDIE] > 0 and spec.draw(self.seed, spec.S_DIE, c.uid, c.ntick) < th[KPDIE]:
                self.apoptosis(c, t, 1)
                return
        # 7. chemistry
        m = c.m
        md0 = m[0] * math.exp(-self.km[0] * dt)
        md1 = m[1] * math.exp(-self.km[1] * dt)
        dec = (m[0] - md0) + (m[1] - md1)
        m[0] = md0 + sp0 * dt
        m[1] = md1 + sp1 * dt
        sec = sp0 * dt + sp1 * dt
        clamp = 0
        if n_view > 0 and not self.flag("chem_off", t):
            nv = float(n_view)
            q0 = self.Dm[0] * dt
            if nv * q0 > spec.CHEM_SHIP_MAX:
                q0 = spec.CHEM_SHIP_MAX / nv
                clamp = 1
            q1 = self.Dm[1] * dt
            if nv * q1 > spec.CHEM_SHIP_MAX:
                q1 = spec.CHEM_SHIP_MAX / nv
                clamp = 1
            amt0, amt1 = m[0] * q0, m[1] * q1
            conc0, conc1 = m[0], m[1]
            for d in range(D):
                if view[d] == EMPTY:
                    continue
                self.send(c.site, d, t + self.d_min, (PACKET, c.uid, view[d], amt0, amt1, conc0, conc1))
                self.emit(R_PACKET, (c.uid, view[d], self.neighbour(c.site, d).sk, amt0, amt1))
            m[0] = m[0] - nv * amt0
            m[1] = m[1] - nv * amt1
        self.emit(R_CHEM, (sec, dec, clamp))
        # 8. division
        if not (self.flag("division_off", t) or freeze) and c.pending == 0 and any_open:
            p = th[KPDIV]
            ok = True
            if self.program:
                if self.p_flank_gate > 0 and fb < self.p_flank_gate:
                    p = self.p_p_div_lo
                ok = c.timer <= self.p_k_grow
            if (ok and p > 0 and spec.draw(self.seed, spec.S_DIV, c.uid, c.ntick) < p
                    and (self.oracle_cap == 0 or self.cap_count < self.oracle_cap)):
                self.divide(c, t, flank, is_open)
        # 9. next tick
        per = c.P_n * (1.0 + self.tick_jit * (2.0 * spec.draw(self.seed, spec.S_TICK, c.uid, c.ntick) - 1.0))
        self.push(t + per, c.site, (TICK, c.uid))
        c.ntick += 1
        c.t_prev = t

    def divide(self, c: _Cell, t: float, flank: list, is_open: list) -> None:
        th = c.th
        ux, uy, uz = self.ux, self.uy, self.uz
        px = py = pz = 0.0
        for d in range(self.D):
            px = px + c.s[d] * ux[d]
            py = py + c.s[d] * uy[d]
            pz = pz + c.s[d] * uz[d]
        vx = px - th[KCHI] * py
        vy = py + th[KCHI] * px
        vz = pz
        best, best_sc = -1, 0.0
        for e in range(self.D):
            if not is_open[e]:
                continue
            noise = spec.PLACE_NOISE * spec.draw(self.seed, spec.S_PLACE, c.uid, c.ndiv, e)
            if self.off_z[e] == 0:
                sc = ux[e] * vx + uy[e] * vy + th[KPHI] * float(flank[e]) + noise
            else:  # up or down (15.37): the vertical polarity component plus the genetic bias zeta
                sc = uz[e] * vz + th[KZETA] * uz[e] + noise
            if best < 0 or sc > best_sc:
                best, best_sc = e, sc
        daughter = spec.uid_daughter(self.seed, c.uid, c.ndiv)
        if self.program:
            payload = c.timer
        else:
            gd = []
            if self.flag("identity_clamp", t):  # g frozen: no partition (LIFE_ABI.md 15.31)
                gd = list(c.g)
            else:
                for k in range(spec.G_MAX):
                    qk = th[KASYM] * self.Q[k]
                    gd.append(spec.clip(c.g[k] + qk, 0.0, 1.0))
                    c.g[k] = spec.clip(c.g[k] - qk, 0.0, 1.0)
            payload = tuple(gd)
        self.send(c.site, best, t + self.d_min, (CLAIM, daughter, c.uid, self.back[best], payload))
        self.emit(R_CLAIM, (c.uid, daughter, self.neighbour(c.site, best).sk))
        c.ndiv += 1
        c.pending = 1
        self.n_inflight += 1

    # ------------------------------------------------------------------------------------- birth and death (7.6-7.8)
    def birth(self, t: float, site: _Site, uid: int, mother: int, bslot: int, payload, init: int, row: int) -> None:
        sk, k = site.sk, site.births
        site.births += 1
        c = _Cell()
        c.uid, c.mother, c.alive, c.t_birth, c.k, c.init, c.row, c.site = uid, mother, True, t, k, init, row, site
        if self.lockstep:
            c.taumis, c.P_n = 1.0, self.P0
        else:
            c.taumis = 1.0 + self.tau_mis * (2.0 * spec.draw(self.seed, spec.S_TAU, sk, k) - 1.0)
            c.P_n = self.P0 * math.exp(self.clock_sd * spec.normal(self.seed, spec.S_CLK, sk, k))
        U = spec.draw(self.seed, spec.S_PHASE, sk, k)
        D = self.D
        c.view = [EMPTY] * D
        c.dc = [0.0] * D
        c.inc = [[0.0, 0.0] for _ in range(D)]
        c.m = [0.0, 0.0]
        c.inbox = []
        c.nspk = c.ntick = c.ndiv = c.nrec = 0
        c.pending = 0
        c.v_a, c.t_a, c.t_r, c.ver = 0.0, t, t, 0
        c.f = c.r0 = c.r1 = c.rho = 0.0
        c.rhom, c.nrecm, c.pendm = [0.0] * SM, [0] * SM, [0] * SM
        c.t_tr = t
        c.tw, c.t_tw, c.t_prev = 0.0, t, t
        c.stuck = False
        c.s = [0.0] * D
        c.w_eff = [[0.0, 0.0] for _ in range(D)]
        if self.program:
            c.g = [0.0] * spec.G_MAX
            c.timer = c.timer_birth = float(payload)
            c.th = self.select(c, 0)
        else:
            c.g = [float(x) for x in payload]
            c.timer = c.timer_birth = 0.0
            c.th = self.decode(c)
        c.tau = c.th[KTAU] * c.taumis
        self.derive(c)
        site.occ = c
        self.n_alive += 1
        self.emit(R_BIRTH, (uid, mother, k, init >= 0, tuple(c.g)))
        self.predict(c)
        if self.lockstep:
            t1 = self.t0 + self.P0 * (math.floor((t - self.t0) / self.P0) + 1.0)
        else:
            t1 = t + U * c.P_n
        if t1 <= t:
            t1 = math.nextafter(t, _INF)
        self.push(t1, site, (TICK, uid))
        if self.noise_rate > 0:
            tn = t - math.log(spec.draw(self.seed, spec.S_NOISE, uid, 0)) / self.noise_rate
            if tn <= t:
                tn = math.nextafter(t, _INF)
            self.push(tn, site, (NOISE, uid, 0))
        if self.kill_t >= 0 and t < self.t0 + self.kill_t:
            self.push(self.t0 + self.kill_t, site, (KILL, uid))
        if (self.stuck_t >= 0 and (site.a, site.b, site.z) == (self.stuck_a, self.stuck_b, self.stuck_z)
                and t < self.t0 + self.stuck_t):
            self.push(self.t0 + self.stuck_t, site, (STUCK, uid))
        if self.catch and site.z == 0 and self.lam_max > 0:  # the receptor's candidate stream (7.10)
            self.push(spec.receptor_next(self.seed, uid, 0, t, self.lam_max), site, (RCAND, uid, 0))
        if self.catch:
            self.mod_activate(c, t)
        instack = self.instack[site.z]
        for d in range(D):
            if instack[d]:
                self.send(site, d, t + self.d_min, (BORN, uid, k))
        if mother != 0:
            self.send(site, bslot, t + self.d_min, (ACK, mother, uid, k))

    def mod_activate(self, c: _Cell, t: float) -> None:
        """ABI 8 (7.10): start each bound modality's stream while the cell's own gain is nonzero (sense plane)."""
        if c.site.z != 0:
            return
        for m in range(1, SM):
            if self.lam_m[m] > 0 and not c.pendm[m] and c.th[KGR + m] != 0.0:
                c.pendm[m] = 1
                self.push(receptor_next_m(self.seed, c.uid, m, c.nrecm[m], t, self.lam_m[m]), c.site,
                          (RCANDM, c.uid, m, c.nrecm[m]))

    def apoptosis(self, c: _Cell, t: float, cause: int) -> None:
        zt = c.tw * math.exp(-(t - c.t_tw) / self.tau_z)
        content = self.content(c)
        self.emit(R_DEATH, (c.uid, cause, zt, content, t - c.t_birth, tuple(c.g), c.mother))
        c.alive = False
        c.site.occ = None
        c.inbox = []
        self.n_alive -= 1
        instack = self.instack[c.site.z]
        for d in range(self.D):
            if instack[d]:
                self.send(c.site, d, t + self.d_min, (DIED, c.uid))

    def dc_of(self, c: _Cell, d: int, k_nb: int) -> float:
        if self.lockstep:
            return self.d0
        s = c.site
        nsk = spec.sitekey(s.a + self.off_a[d], s.b + self.off_b[d], s.z + self.off_z[d])
        z = spec.normal(self.seed, spec.S_DC, s.sk, nsk, ((c.k << 32) | k_nb) & spec.MASK64)
        return self.d0 * math.exp(self.delay_sd * z)

    # ------------------------------------------------------------------------------------------- batch (6.2)
    def batch(self, t: float, site: _Site, evs: list) -> None:
        self.bt, self.bsk, self.seq = t, site.sk, 0
        occ = site.occ  # the live occupant at t-
        claims, notices, packets, arrivals, thrs, noises, rcands, receptors, exo = [], [], [], [], [], [], [], [], []
        rcandms, receptorms = [], []
        tick = None
        for ev in evs:
            kind = ev[0]
            g = kind // 10
            if g == 0:
                claims.append(ev)
            elif g == 1:
                notices.append(ev)
            elif g == 2:
                packets.append(ev)
            elif kind == ARRIVAL:
                arrivals.append(ev)
            elif kind == THRESHOLD:
                thrs.append(ev)
            elif kind == NOISE:
                noises.append(ev)
            elif kind == RCAND:
                rcands.append(ev)
            elif kind == RECEPTOR:
                receptors.append(ev)
            elif kind == RCANDM:
                rcandms.append(ev)
            elif kind == RECEPTORM:
                receptorms.append(ev)
            elif kind == TICK:
                tick = ev
            else:
                exo.append(ev)
        # 0. claims, against the occupancy at t-
        if claims:
            exists = self.fabric_R == 0 or _lat.in_disk(self.base, site.a, site.b, self.fabric_R)
            won = False
            for ev in sorted(claims, key=lambda e: e[3]):
                _, bslot, _ns, daughter, mother, _bs, payload = ev
                if not exists:
                    res = 2
                elif occ is not None or won:
                    res = 1
                else:
                    res, won = 0, True
                self.n_inflight -= 1
                self.emit(R_RESOLVE, (daughter, mother, res))
                if res == 0:
                    self.birth(t, site, daughter, mother, bslot, payload, -1, -1)
                else:
                    self.send(site, bslot, t + self.d_min, (REJECT, mother))
        counted = t >= self.t_open_abs
        uid = occ.uid if occ is not None else EMPTY
        # 1. notices
        if occ is not None and notices:
            for ev in sorted(notices, key=lambda e: (e[1], e[0], e[2])):
                kind, slot = ev[0], ev[1]
                if kind == BORN:
                    u2, k2 = ev[3], ev[4]
                    occ.view[slot] = u2
                    occ.dc[slot] = self.dc_of(occ, slot, k2)
                    self.send(site, slot, t + self.d_min, (PRESENT, u2, uid, occ.k))
                elif kind == DIED:
                    occ.view[slot] = EMPTY
                    occ.inc[slot][0] = 0.0
                    occ.inc[slot][1] = 0.0
                elif ev[3] != uid:
                    continue
                elif kind == REJECT:
                    occ.pending = 0
                else:  # PRESENT or ACK
                    occ.view[slot] = ev[4]
                    occ.dc[slot] = self.dc_of(occ, slot, ev[5])
                    if kind == ACK:
                        occ.pending = 0
        # 2. packets
        for ev in sorted(packets, key=lambda e: (e[3], e[1])):
            _, slot, _ns, sender, target, a0, a1, c0, c1 = ev
            if target == uid and occ is not None:
                occ.inbox.append((t, sender, slot, a0, a1, c0, c1))
            else:
                self.emit(R_LOST, (sender, target, a0, a1))
        # 3. membrane: the current RCAND's record, then one step for receptors, arrivals, kicks and the threshold
        arr = []
        for ev in arrivals:
            if ev[3] == uid and occ is not None:
                arr.append((ev[1], ev[4]))
        self.events += len(arrivals)
        if counted:
            self.n_arr += len(arr)
            self.n_drop += len(arrivals) - len(arr)
        if occ is None:
            return
        for ev in rcands:
            if ev[1] == uid and ev[2] == occ.nrec:
                j = ev[2]
                self.emit(R_RCAND, (uid, j))
                occ.nrec = j + 1
                self.push(spec.receptor_next(self.seed, uid, j + 1, t, self.lam_max), site, (RCAND, uid, j + 1))
        for ev in sorted(rcandms, key=lambda e: (e[2], e[3])):  # ABI 8: (m, j) order
            _, u, m, j = ev
            if u != uid or j != occ.nrecm[m]:
                continue
            occ.nrecm[m] = j + 1
            if occ.th[KGR + m] != 0.0 and self.lam_m[m] > 0:
                self.emit(R_RCANDM, (uid, m, j))
                self.push(receptor_next_m(self.seed, uid, m, j + 1, t, self.lam_m[m]), site, (RCANDM, uid, m, j + 1))
            else:
                occ.pendm[m] = 0
        n_rec = 0
        if receptors and occ.th[KGR] != 0.0 and not self.flag("receptor_off", t):
            n_rec = sum(1 for ev in receptors if ev[1] == uid)
        n_rm = [0] * SM
        if receptorms and not self.flag("receptor_off", t):
            for ev in receptorms:
                if ev[1] == uid and occ.th[KGR + ev[2]] != 0.0:
                    n_rm[ev[2]] += 1
        kicks = []
        for ev in noises:
            if ev[1] != uid:
                continue
            j = ev[2]
            kicks.append(0.125 if spec.draw(self.seed, spec.S_NSIGN, uid, j) >= 0.5 else -0.125)
            tn = t - math.log(spec.draw(self.seed, spec.S_NOISE, uid, j + 1)) / self.noise_rate
            if tn <= t:
                tn = math.nextafter(t, _INF)
            self.push(tn, site, (NOISE, uid, j + 1))
        thr = any(ev[1] == uid and ev[2] == occ.ver for ev in thrs)
        if any(n_rm):
            self.membrane(occ, t, arr, kicks, thr, n_rec, n_rm)
        elif n_rec:
            self.membrane(occ, t, arr, kicks, thr, n_rec)
        elif arr or kicks or thr:
            self.membrane(occ, t, arr, kicks, thr)  # ABI 2's call, which instrumented tests wrap
        # 4. tick
        if tick is not None and tick[1] == uid:
            self.tick(occ, t)
        # 5. exogenous (panel)
        for ev in sorted(exo, key=lambda e: e[0]):
            if not occ.alive or ev[1] != uid:
                continue
            if ev[0] == KILL:
                if spec.draw(self.seed, spec.S_KILL, uid) < self.kill_frac:
                    self.emit(R_TICK, (uid, occ.t_prev, occ.th[KSEC0] + occ.th[KSEC1]))  # cost of [t_prev, t)
                    self.apoptosis(occ, t, 3)
            else:
                self.reanchor(occ, t)
                occ.stuck = True
                self.stuck_override(occ)
                self.predict(occ)

    # ---------------------------------------------------------------------------------------------- schedulers
    def guards_upto(self, x: float):
        """Check the guards at integer times c <= x not yet checked (section 10), and take the CATCH sample there
        unless a guard trips (9.7.1); return (c, bits) on a trip."""
        while self.next_c <= x and self.next_c <= self.t1 - 1.0:
            c = self.next_c
            gb = 0
            if self.acct.n >= self.n_max:
                gb |= _ST["guard_cells"]
            if self.events > self.e_max:
                gb |= _ST["guard_events"]
            if gb:
                return c, gb
            if self.acct.eco_dead:  # ABI 8: the body was killed before c
                return c, _ST["killed"]
            if self.catch:
                self.acct.sample(c)
            self.next_c = c + 1.0
        return None

    def feed(self, recs: list) -> None:
        """Hand records to the accountant in canonical order, one time group at a time."""
        recs.sort(key=lambda r: (r[0], r[1], r[2]))
        i, n = 0, len(recs)
        while i < n:
            j = i
            t = recs[i][0]
            while j < n and recs[j][0] == t:
                j += 1
            self.acct.group(t, recs[i:j])
            i = j

    def start(self) -> None:
        recs = []
        self.out = recs
        for j, (a, b, z, row) in enumerate(self.init):
            site = self.site(a, b, z)
            self.bt, self.bsk, self.seq = self.t0, site.sk, 0
            payload = 0.0 if self.program else tuple(self.g0)
            self.birth(self.t0, site, spec.uid_initial(self.seed, j), 0, -1, payload, j, row if self.program else -1)
        self.feed(recs)

    def run_heap(self):
        heap = self.heap
        pending: list = []
        t_group = None
        while True:
            if not (heap and heap[0][0] < self.t1):
                if not pending:
                    break
                self.feed(pending)  # a flush can create events (RECEPTORs, 11.1): look at the queue again
                pending = []
                continue
            t = heap[0][0]
            if pending and t > t_group:
                self.feed(pending)
                pending = []
                continue
            trip = self.guards_upto(t)
            if trip:
                return trip
            if t != self.cap_t:
                self.cap_t, self.cap_count = t, self.n_alive + self.n_inflight
            _, _, sk, _, ev = heapq.heappop(heap)
            evs = [ev]
            while heap and heap[0][0] == t and heap[0][2] == sk:
                evs.append(heapq.heappop(heap)[4])
            self.out = pending
            t_group = t
            self.batch(t, self.sites[sk], evs)
        return self.guards_upto(self.t1 - 1.0)

    def run_window(self):
        h, heap = self.window_h, self.heap
        k_next = 0  # first window not processed yet
        while heap and heap[0][0] < self.t1:
            tmin = heap[0][0]
            k = max(k_next, int(math.floor((tmin - self.t0) / h)))
            while k > k_next and self.t0 + k * h > tmin:  # tmin - t0 may round up onto a window edge
                k -= 1
            while self.t0 + (k + 1) * h <= tmin:
                k += 1
            wstart, wend = self.t0 + k * h, self.t0 + (k + 1) * h
            trip = self.guards_upto(wstart)
            if trip:
                return trip
            local: dict[int, list] = {}
            while heap and heap[0][0] < wend:
                t, _, sk, key, ev = heapq.heappop(heap)
                if t < wstart:
                    raise AssertionError("window scheduler: event before its window")
                local.setdefault(sk, []).append((t, key, ev))
            order = sorted(local, key=lambda s: (spec.hash64(self.order_seed, spec.S_ORDER, k, s), s))
            recs: list = []
            self.out = recs
            for sk in order:
                lh = local[sk]
                heapq.heapify(lh)
                self.local = (sk, lh, wend)
                site = self.sites[sk]
                while lh:
                    t = lh[0][0]
                    evs = []
                    while lh and lh[0][0] == t:
                        evs.append(heapq.heappop(lh)[2])
                    self.batch(t, site, evs)
                self.local = None
            self.feed(recs)  # RECEPTORs it creates land at t + d_min >= wend, in a later window
            k_next = k + 1
        return self.guards_upto(self.t1 - 1.0)

    def run(self) -> LifeResult:
        self.start()
        trip = self.run_window() if self.window_h > 0 else self.run_heap()
        t_end, gb = trip if trip else (self.t1, 0)
        self.acct.close(t_end, gb, self.out_abi.LEDGER_SIZE)
        return self.result()

    def result(self) -> LifeResult:
        a, abi = self.acct, self.out_abi
        nfi = abi.FATE_I_SIZE
        fi = np.array([[r[0], _i64(r[1]), _i64(r[2]), r[3], r[4], r[5], r[6]][:nfi] for r in a.fate], dtype=np.int64)
        ff = np.array([[r[7], r[8], *r[9]] for r in a.fate], dtype=np.float64)
        return LifeResult(
            ledger=np.array(a.led[:abi.LEDGER_SIZE], dtype=np.float64),
            hashes=np.array(a.h[:abi.HASH_SIZE], dtype=np.uint64),
            raster_t=np.array(a.raster_t, dtype=np.float64), raster_uid=np.array(a.raster_uid, dtype=np.uint64),
            raster_n=a.raster_n, fate_i=fi.reshape(-1, nfi), fate_f=ff.reshape(-1, spec.FATE_F_SIZE),
            fate_n=a.fate_n, records=a.records, world=a.wlog, abi=abi)


def receptor_next_m(seed: int, uid: int, m: int, j: int, t_prev: float, lam: float) -> float:
    """ABI 8: time of candidate j of modality m >= 1 (stream S_RCAND_M keyed (uid, m, j))."""
    t = t_prev - math.log(spec.draw(seed, spec.S_RCAND_M, uid, m, j)) / lam
    return t if t > t_prev else math.nextafter(t_prev, _INF)


def _i64(u: int) -> int:
    return u - (1 << 64) if u >= 1 << 63 else u


# ------------------------------------------------------------------------------------------------------- arguments
def _abi(abi) -> spec.Abi:
    abi = spec.CURRENT if abi is None else abi
    if abi.version not in (2, 3, 4, 5, 6, 7, 8):  # pragma: no cover
        raise ValueError(f"the reference implements ABI 2 through 8, not {abi.version}")
    return abi


def _lattice(lat, unit, abi=None) -> dict:
    """Parse and check a lattice table (4.3) of ``abi``; ABI-2 tables get off_z = 0 and unit z = 0."""
    abi = _abi(abi)
    v3 = abi.version >= 3
    tab = [int(x) for x in np.asarray(lat).ravel()]
    if len(tab) < 2 or tab[0] not in _KIND_OF or _KIND_OF[tab[0]] not in abi.LATTICE_CODES:
        raise ArgError(-4, "invalid lattice table")
    kind, D = _KIND_OF[tab[0]], tab[1]
    nrow = 7 if v3 else 6
    if D != len(_lat.offsets3(kind)) or len(tab) != 2 + nrow * D:
        raise ArgError(-4, "lattice table size does not match its code")
    cols = [tab[2 + i * D: 2 + (i + 1) * D] for i in range(nrow)]
    if v3:
        off_a, off_b, off_z, back, prev, nxt, rot = cols
    else:
        off_a, off_b, back, prev, nxt, rot = cols
        off_z = [0] * D
    nb = len(_lat.offsets(_lat.base_kind(kind)))
    for d in range(D):
        idx = (back[d], prev[d], nxt[d]) + ((rot[d],) if v3 else ())
        if not all(0 <= i < D for i in idx):
            raise ArgError(-4, "lattice slot index out of range")
        if (off_a[back[d]], off_b[back[d]], off_z[back[d]]) != (-off_a[d], -off_b[d], -off_z[d]):
            raise ArgError(-4, "back[] does not point back")
        if (off_a[d], off_b[d], off_z[d]) == (0, 0, 0):
            raise ArgError(-4, "a slot points at its own site")
        if off_z[d] != (0 if d < nb else (1 if d == nb else -1)):
            raise ArgError(-4, "off_z must be 0 on the base kind's slots and +1, -1 on a prism's last two")
    u = np.asarray(unit, dtype=np.float64).reshape(D, 3 if v3 else 2)
    uz = [float(x) for x in u[:, 2]] if v3 else [0.0] * D
    return dict(kind=kind, base=_lat.base_kind(kind), D=D, off_a=off_a, off_b=off_b, off_z=off_z, back=back,
                prev=prev, next=nxt, ux=[float(x) for x in u[:, 0]], uy=[float(x) for x in u[:, 1]], uz=uz)


def _check_world(wv, abi=None) -> None:
    """Return code -2 for the vectors that ``abi.validate_world`` would refuse."""
    abi = _abi(abi)
    wv = np.asarray(wv, dtype=np.float64)
    if wv.shape != (abi.WORLD_SIZE,) or not np.all(np.isfinite(wv)):
        raise ArgError(-2, f"world vector must hold {abi.WORLD_SIZE} finite numbers")
    vals = {}
    if abi.version >= 8:  # the ABI 8 blocks
        vals["mod"] = tuple(float(wv[abi.WORLD_INDEX[k]]) for k in spec.MOD_KEYS)
        vals["eco"] = tuple(float(wv[abi.WORLD_INDEX[k]]) for k in spec.ECO_KEYS)
    for f_ in fields(spec.World):
        if f_.name not in abi.WORLD_INDEX:
            continue
        x = float(wv[abi.WORLD_INDEX[f_.name]])
        if f_.type in ("int", int):
            if x != int(x):
                raise ArgError(-2, f"{f_.name} must be an integer")
            x = int(x)
        vals[f_.name] = x
    try:
        abi.validate_world(spec.EcoWorld(**vals) if "mod" in vals else spec.World(**vals))
    except (ValueError, NotImplementedError) as e:
        raise ArgError(-2, str(e)) from None


def _prepare(world_vec, latd: dict, genome_table, program, init, abi: spec.Abi) -> tuple:
    """Check one life's arguments and convert them into ABI-7 inputs: (world, genome row, program, cells)."""
    _check_world(world_vec, abi)
    wv = [float(x) for x in np.asarray(world_vec, dtype=np.float64)]
    flags = int(wv[abi.WORLD_INDEX["flags"]])
    prog_mode = bool(flags & abi.FLAGS["program_mode"])
    if prog_mode and program is None:
        raise ArgError(-1, "program mode needs a program table")
    if not prog_mode and genome_table is None:
        raise ArgError(-1, "GRN mode needs a packed genome table")
    if prog_mode and np.asarray(program).shape != (abi.PROGRAM_SIZE,):
        raise ArgError(-1, f"program rows have {abi.PROGRAM_SIZE} entries")
    if not prog_mode and np.asarray(genome_table).shape != (abi.GENOME_SIZE,):
        raise ArgError(-1, f"packed genome rows have {abi.GENOME_SIZE} entries")
    row = np.asarray(program if prog_mode else genome_table, dtype=np.float64)
    if not np.all(np.isfinite(row)):
        raise ArgError(-1, "a table row holds NaN or infinity")
    v3 = abi.version >= 3
    L_max = int(wv[abi.WORLD_INDEX["L_max"]]) if v3 else 1
    if not init:
        cells = [(0, 0, 0, -1)]
    elif v3:
        cells = [tuple(int(v) for v in c) for c in init]
        if any(len(c) != 4 for c in cells):
            raise ArgError(-4, "ABI 3 initial cells are (a, b, z, row)")
    else:
        cells = [(int(a), int(b), 0, int(r)) for a, b, r in init]
    if len(cells) > abi.MAX_INIT or len({c[:3] for c in cells}) != len(cells):
        raise ArgError(-4, f"initial body: more than {abi.MAX_INIT} cells or duplicate sites")
    if prog_mode and any(not -1 <= c[3] < _NROW for c in cells):  # GRN mode ignores the row (4.6)
        raise ArgError(-4, "initial body: program row out of range")
    if any(not 0 <= z < L_max or max(abs(a), abs(b)) > spec.COORD_MAX_3D for a, b, z, _ in cells):
        raise ArgError(-4, "initial body: a cell outside the stack or beyond |a|, |b| <= 2^22")
    R = int(wv[abi.WORLD_INDEX["fabric_R"]])
    if R > 0 and any(not _lat.in_disk(latd["base"], a, b, R) for a, b, _z, _row in cells):
        raise ArgError(-4, "initial body: a cell on a wall of the dense fabric (4.6)")
    if not v3:  # neutral padding into ABI 3 (LIFE_ABI.md 4.4, 4.5, 4.7, 15.33)
        wv = wv + _V3_DEFAULTS
        row = V3.pad_program(row, V2) if prog_mode else V3.pad_genomes(row[None], V2)[0]
    if abi.version < 8:  # ABI 8 genome inputs and gains (zeros: no weight, no gain)
        src = V3 if abi.version >= 3 or not v3 else V3
        row = V8.pad_program(row, src) if prog_mode else V8.pad_genomes(np.asarray(row)[None], src)[0]
    if abi.version < 4:
        wv = wv + _V4_DEFAULTS
    if abi.version < 5:
        wv = wv + _V5_DEFAULTS
    if abi.version < 6:
        wv = wv + _V6_DEFAULTS
    if abi.version < 7:
        wv = wv + _V7_DEFAULTS
    if abi.version < 8:
        wv = wv + _V8_DEFAULTS
    return wv, (None if prog_mode else row), (row if prog_mode else None), cells


def run_life(world_vec, lat, unit, *, genome_table=None, program=None, init=None, seeds=(0, 0, 0, 0),
             raster_cap: int = 0, fate_cap: int = 0, records: bool = False, abi=None) -> LifeResult:
    """One life from kernel-format inputs of ``abi`` (default ``spec.CURRENT``): a world vector (4.7), lattice
    tables (4.3), a packed genome row (GRN mode) or a program row (program mode), an initial body of rows
    ``(a, b, z, row)`` (ABI 3) or ``(a, b, row)`` (ABI 2), None for one zygote at (0, 0, 0), and the four seeds."""
    abi = _abi(abi)
    latd = _lattice(lat, unit, abi)
    wv, gt, prog, cells = _prepare(world_vec, latd, genome_table, program, init, abi)
    life = _Life(wv, latd, gt, prog, cells, seeds, raster_cap, fate_cap, records, out_abi=abi)
    return life.run()


def run(w: spec.World, *, genome=None, genome_table=None, program=None, cells=None, rows=None, seed: int = 0,
        tie_seed: int = 0, order_seed: int = 0, salt: int = 0, raster_cap: int = 4096, fate_cap: int = 4096,
        records: bool = False, abi=None) -> LifeResult:
    """Convenience wrapper: a ``spec.World``, a raw float32 genome of ``abi`` (or its packed table) or a program
    (``abi.pack_program``, which switches on ``program_mode``), and an optional explicit initial body of ``(a, b)``
    or (ABI 3) ``(a, b, z)`` cells with optional program rows."""
    abi = _abi(abi)
    if program is not None:
        w = replace(w, flags=w.flags | abi.FLAGS["program_mode"])
    lat, unit = abi.lattice_tables(w.lattice)
    if genome is not None:
        genome_table = abi.pack_genomes(genome, w.lattice)[0]
    init = None
    if cells is not None:
        rws = [-1] * len(cells) if rows is None else list(rows)
        if abi.version >= 3:
            init = [(c[0], c[1], c[2] if len(c) > 2 else 0, r) for c, r in zip(cells, rws)]
        else:
            init = [(a, b, r) for (a, b), r in zip(cells, rws)]
    return run_life(abi.pack_world(w), lat, unit, genome_table=genome_table, program=program, init=init,
                    seeds=(seed, tie_seed, order_seed, salt), raster_cap=raster_cap, fate_cap=fate_cap,
                    records=records, abi=abi)


def life_run(lat, unit, genomes, programs, genome_of, init_cells, n_init, world, seeds, raster_cap: int = 0,
             fate_cap: int = 0, threads: int = 1, abi=None) -> dict:
    """The kernel entry point ``life_run`` (LIFE_ABI.md 4.2) with numpy arrays of ``abi`` in and out.

    Returns ``rc`` and the output arrays ``ledger [n, LEDGER_SIZE]``, ``hashes [n, HASH_SIZE]``,
    ``raster_t``/``raster_uid [n, cap]``, ``raster_n [n]``, ``fate_i [n, cap, FATE_I_SIZE]``, ``fate_f [n, cap, 18]``
    and ``fate_n [n]``. Every life's arguments are checked before any life runs. ``threads`` is ignored.
    """
    abi = _abi(abi)
    genome_of = np.asarray(genome_of, dtype=np.int32).ravel()
    n = len(genome_of)
    rc, cap_r, cap_f = 0, max(int(raster_cap), 0), max(int(fate_cap), 0)
    out = dict(ledger=np.zeros((n, abi.LEDGER_SIZE)), hashes=np.zeros((n, abi.HASH_SIZE), dtype=np.uint64),
               raster_t=np.zeros((n, cap_r)), raster_uid=np.zeros((n, cap_r), dtype=np.uint64),
               raster_n=np.zeros(n, dtype=np.int64), fate_i=np.zeros((n, cap_f, abi.FATE_I_SIZE), dtype=np.int64),
               fate_f=np.zeros((n, cap_f, spec.FATE_F_SIZE)), fate_n=np.zeros(n, dtype=np.int64))
    world = np.asarray(world, dtype=np.float64).reshape(n, abi.WORLD_SIZE)
    seeds = np.asarray(seeds, dtype=np.uint64).reshape(n, 4)
    gts = None if genomes is None else np.asarray(genomes, dtype=np.float64).reshape(-1, abi.GENOME_SIZE)
    prs = None if programs is None else np.asarray(programs, dtype=np.float64).reshape(-1, abi.PROGRAM_SIZE)
    body = (None if init_cells is None
            else np.asarray(init_cells, dtype=np.int32).reshape(n, abi.MAX_INIT, abi.INIT_COLS))
    nin = np.zeros(n, dtype=np.int32) if n_init is None else np.asarray(n_init, dtype=np.int32).ravel()
    try:
        latd = _lattice(lat, unit, abi)
        jobs = []
        for i in range(n):
            _check_world(world[i], abi)
            gi = int(genome_of[i])
            prog_mode = bool(int(world[i][abi.WORLD_INDEX["flags"]]) & abi.FLAGS["program_mode"])
            table = prs if prog_mode else gts  # each table has its own row count
            if table is None or not 0 <= gi < len(table):
                raise ArgError(-1, "a life needs a table that was not given, or genome_of is outside it")
            if not np.all(np.isfinite(table[gi])):
                raise ArgError(-1, "a table row holds NaN or infinity")
            if not 0 <= nin[i] <= abi.MAX_INIT:
                raise ArgError(-4, "invalid n_init")
            if nin[i] > 0 and body is None:
                raise ArgError(-1, "a life has initial cells but init_cells was not given")
            init = None if nin[i] == 0 else [tuple(int(v) for v in body[i, j]) for j in range(nin[i])]
            prep = _prepare(world[i], latd, None if prog_mode else table[gi], table[gi] if prog_mode else None, init,
                            abi)
            jobs.append((prep, [int(s) for s in seeds[i]]))
        for i, ((wv, gt, prog, cells), sd) in enumerate(jobs):
            res = _Life(wv, latd, gt, prog, cells, sd, cap_r, cap_f, False, out_abi=abi).run()
            out["ledger"][i] = res.ledger
            out["hashes"][i] = res.hashes
            out["raster_n"][i] = res.raster_n
            out["fate_n"][i] = res.fate_n
            nr, nf = len(res.raster_t), len(res.fate_i)
            out["raster_t"][i, :nr] = res.raster_t
            out["raster_uid"][i, :nr] = res.raster_uid
            out["fate_i"][i, :nf] = res.fate_i
            out["fate_f"][i, :nf] = res.fate_f
    except ArgError as e:
        rc = e.rc
        for v in out.values():
            v[...] = 0
    out["rc"] = rc
    return out
