"""Pure-Python specification of one life (docs/LIFE_ABI.md), written independently of the C kernel.

Every handler of the ABI (sections 6-12) is transcribed here with the same float64 operations in the same order, so on
the same libm its ledger, hashes, raster and fate log agree bitwise with ``kernel.c``. It is meant for tiny bodies
(about 20 cells, T up to about 200) in tests: whole lives are seconds, not milliseconds.

Both schedulers of section 11 are implemented: the heap (``window_h = 0``, ties permuted by the tie seed) and the
conservative window scheduler (``window_h = 2^-k``, sites visited in order-seed order). The relabel salt permutes the
order in which same-batch events leave the heap, which must not change anything.

Where the ABI leaves a detail open, this file chooses:
- emit knobs are read as booleans (nonzero = on), so ``n_out`` is an integer;
- packets lost in one batch emit R_LOST in increasing (sender uid, receiver slot) order;
- notices with equal (receiver slot, kind) keep the sender site's send order;
- a capacity of 0 turns a log off without setting its overflow bit;
- fate-log reject entries are written for both occupied (aux 0) and wall (aux 1) results.
"""
from __future__ import annotations

import heapq
import math
import struct
from dataclasses import dataclass, fields, replace

import numpy as np

from src import lattice as _lat
from src.life import spec

EMPTY = spec.EMPTY
_D_KIND = {0: "hex", 1: "square4", 2: "square8"}
_INF = float("inf")
_PACK_D = struct.Struct("<d")
_PACK_Q = struct.Struct("<Q")

# event kinds; kind // 10 is the batch group of section 6.2 (within NOTICE the kind order is the ABI's)
CLAIM = 0
BORN, PRESENT, ACK, REJECT, DIED = 10, 11, 12, 13, 14
PACKET = 20
ARRIVAL, THRESHOLD, NOISE = 30, 31, 32
TICK = 40
KILL, STUCK = 50, 51

# records; the id is also the first hash word (section 9.6)
R_SPIKE, R_BIRTH, R_DEATH, R_CLAIM, R_RESOLVE, R_PACKET, R_LOST, R_TICK, R_CHEM = 1, 2, 3, 4, 5, 6, 7, 8, 9
H_ALL, H_SPIKES, H_FATE, H_CHEM = 0, 1, 2, 3
_FAMILY = {R_SPIKE: H_SPIKES, R_BIRTH: H_FATE, R_DEATH: H_FATE, R_CLAIM: H_FATE, R_RESOLVE: H_FATE,
           R_PACKET: H_CHEM, R_LOST: H_CHEM}

(KW0, KW1, KB, KTAU, KREF, KE0, KE1, KDEL, KKAP, KPDIV, KASYM, KPDIE, KPHI, KSEC0, KSEC1, KPOL0, KPOL1, KTTR,
 KA0, KA1, KCHI) = range(spec.P)
assert [spec.K[n] for n in spec.KNOBS] == list(range(spec.P)) and spec.KNOBS[KA0] == "a0" and spec.KNOBS[KCHI] == "chi"

_F = spec.FLAGS
_ST = spec.STATUS
_LI = spec.L
_PS = {name: i - len(spec.PROGRAM_ROWS) * spec.P for name, i in spec.PROGRAM_SCALAR.items()}
_ROW = spec.PROGRAM_ROW


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
    __slots__ = ("sk", "a", "b", "births", "occ", "nsend")

    def __init__(self, a: int, b: int):
        self.sk = spec.sitekey(a, b)
        self.a, self.b = a, b
        self.births = 0
        self.occ = None  # the live occupant, or None
        self.nsend = 0  # messages sent from this site (deterministic tie-break among equal notices)


class _Cell:
    __slots__ = ("uid", "mother", "alive", "t_birth", "k", "init", "row", "site", "nspk", "ntick", "ndiv", "view",
                 "dc", "inc", "v_a", "t_a", "t_r", "ver", "f", "r0", "r1", "t_tr", "z", "t_z", "g", "m", "inbox",
                 "th", "tau", "w_eff", "s", "taumis", "P_n", "t_prev", "pending", "timer", "timer_birth", "stuck")


@dataclass
class LifeResult:
    """Outputs of one life in the layouts of LIFE_ABI.md 4.9-4.11."""
    ledger: np.ndarray  # float64 [35], columns spec.LEDGER
    hashes: np.ndarray  # uint64 [4]: all, spikes, fate, chem
    raster_t: np.ndarray  # float64 [min(raster_n, cap)]
    raster_uid: np.ndarray  # uint64
    raster_n: int
    fate_i: np.ndarray  # int64 [rows, 6]: kind, uid, mother, a, b, aux
    fate_f: np.ndarray  # float64 [rows, 18]: t, age, g[16]
    fate_n: int
    records: list | None = None  # canonical records (t, sk, seq, kind, payload) when asked for

    def __getitem__(self, name: str) -> float:
        return float(self.ledger[_LI[name]])

    @property
    def status(self) -> int:
        return int(self.ledger[_LI["status"]])


# ------------------------------------------------------------------------------------------------------- accountant
class _Accountant:
    """Section 9: consumes records in canonical order; owns the world, the ledger, the logs and the hashes."""

    def __init__(self, life: _Life):
        self.life = life
        self.A, self.R, self.t_w, self.above = 0.0, 1.0, life.t0, 0
        self.n = 0
        self.inflight = 0
        self.led = [0.0] * spec.LEDGER_SIZE
        self.led[_LI["last_birth"]] = life.t0
        self.led[_LI["t_ext"]] = -1.0
        self.status = 0
        self.extinct = False
        self.n_peak = 0
        self.h = [spec.HASH_INIT] * spec.HASH_SIZE
        self.raster_t: list[float] = []
        self.raster_uid: list[int] = []
        self.raster_n = 0
        self.fate: list[tuple] = []
        self.fate_n = 0
        self.flying: list[tuple] = []  # remembered packets (t_arr, target sk, sender, amt0, amt1, t_send)
        self.records = [] if life.keep_records else None

    # world (9.2)
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

    def _tick_cost(self, t: float, t_prev: float, sp: float) -> None:
        L, led = self.life, self.led
        if t > L.t_open_abs:
            dl = t - _max(t_prev, L.t_open_abs)
            led[_LI["live_time"]] += dl
            led[_LI["sec_int"]] += sp * dl
            led[_LI["cost"]] = led[_LI["cost"]] + L.c_live * dl
            led[_LI["cost"]] = led[_LI["cost"]] + L.c_sec * (sp * dl)

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
        for rec in recs:
            if self.records is not None:
                self.records.append(rec)
            _, sk, _, kind, p = rec
            tb = bits(t)
            if kind == R_SPIKE:
                uid, kap, n_out, dz = p
                if counted:
                    led[_LI["spikes"]] += 1.0
                    led[_LI["kappa_sum"]] += kap
                    led[_LI["contact_events"]] += float(n_out)
                    led[_LI["cost"]] = led[_LI["cost"]] + L.c_spike
                    led[_LI["cost"]] = led[_LI["cost"]] + L.c_tw * kap
                    led[_LI["cost"]] = led[_LI["cost"]] + L.c_msg * float(n_out)
                if kap > 0:
                    self.world_adv(t)
                    self.A = self.A + dz
                    if self.above == 0 and self.A / self.n > L.th:
                        self.above = 1
                        if counted:
                            led[_LI["beats"]] += 1.0
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
                self._tick_cost(t, t_prev, sp)
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
                daughter, mother, res, a, b = p
                self.inflight -= 1
                if res == 2:
                    self.status |= _ST["wall"]
                if counted:
                    led[_LI["rejects"]] += 1.0 if res == 1 else 0.0
                    led[_LI["rejects_wall"]] += 1.0 if res == 2 else 0.0
                if res != 0:
                    self._log_fate((3, daughter, mother, a, b, res - 1, t, 0.0, (0.0,) * spec.G_MAX))
                self._fold(kind, (5, tb, daughter, res))
            elif kind == R_BIRTH:
                uid, mother, k, initial, g, a, b = p
                self.world_adv(t)
                self.n += 1
                if not initial:
                    if counted:
                        led[_LI["births"]] += 1.0
                    led[_LI["last_birth"]] = t
                self._log_fate((1, uid, mother, a, b, k, t, 0.0, g))
                self._fold(kind, (2, tb, uid, mother, sk, k))
            elif kind == R_DEATH:
                uid, cause, zt, content, age, g, mother, a, b = p
                self.world_adv(t)
                self.A = self.A - zt
                if self.A < 0:
                    self.A = 0.0
                self.n -= 1
                if self.n == 0:
                    self.A = 0.0
                if counted:
                    led[_LI["kills" if cause == 3 else "deaths"]] += 1.0
                led[_LI["morph_lost"]] = led[_LI["morph_lost"]] + content
                self._log_fate((2, uid, mother, a, b, cause, t, age, g))
                self._fold(kind, (3, tb, uid, cause))
            else:  # pragma: no cover
                raise AssertionError(f"unknown record kind {kind}")
        if self.n > self.n_peak:
            self.n_peak = self.n
        if self.n == 0 and self.inflight == 0 and not self.extinct:
            self.extinct = True
            self.status |= _ST["extinct"]
            led[_LI["t_ext"]] = t
        if len(self.flying) > 256:
            self.flying = [x for x in self.flying if x[0] >= t]

    def close(self, t_end: float, guard_bits: int) -> None:
        """Section 9.5, after the last time group with t < t_end."""
        L, led = self.life, self.led
        self.world_adv(t_end)
        for sk in sorted(L.sites):
            c = L.sites[sk].occ
            if c is None:
                continue
            self._tick_cost(t_end, c.t_prev, c.th[KSEC0] + c.th[KSEC1])
            led[_LI["morph_content_end"]] = led[_LI["morph_content_end"]] + L.content(c)
        s = 0.0
        for _t_arr, _tsk, _snd, a0, a1, _t_send in sorted(x for x in self.flying if x[5] < t_end <= x[0]):
            s = s + a0
            s = s + a1
        led[_LI["morph_inflight_end"]] = s
        self.status |= guard_bits
        gc = L.c_live * float(L.n_max) * (L.t1 - t_end) if guard_bits else 0.0
        col = L.c_live * led[_LI["live_time"]]
        col = col + L.c_spike * led[_LI["spikes"]]
        col = col + L.c_tw * led[_LI["kappa_sum"]]
        col = col + L.c_msg * led[_LI["contact_events"]]
        col = col + L.c_div * led[_LI["claims"]]
        col = col + L.c_sec * led[_LI["sec_int"]]
        net = led[_LI["income"]] - col - gc
        led[_LI["guard_charge"]] = gc
        led[_LI["net"]] = net
        led[_LI["F"]] = net / (L.T - L.t_open)
        if abs(led[_LI["cost"]] - col) > 1e-9 * _max(1.0, abs(col)):
            self.status |= _ST["ledger_mismatch"]
        led[_LI["n_end"]] = float(self.n)
        led[_LI["n_peak"]] = float(self.n_peak)
        led[_LI["t_end"]] = t_end
        led[_LI["events"]] = float(L.events)
        led[_LI["arrivals"]] = float(L.n_arr)
        led[_LI["arrivals_dropped"]] = float(L.n_drop)
        led[_LI["ticks"]] = float(L.n_ticks)
        led[_LI["status"]] = float(self.status)
        ha = self.h[H_ALL]
        for x in led:
            ha = spec.splitmix64(ha ^ bits(x))
        self.h[H_ALL] = ha


# ------------------------------------------------------------------------------------------------------------- life
class _Life:
    """One life: sites, cells, the event queue, the handlers of section 7 and a scheduler of section 11."""

    def __init__(self, wv, lat: dict, gt, prog, init, seeds, raster_cap: int, fate_cap: int, keep_records: bool):
        wi = spec.WORLD_INDEX
        wv = [float(x) for x in wv]
        for key in ("T", "t0", "t_open", "t_fork", "d_min", "d0", "delay_sd", "jit", "tau_mis", "P0", "clock_sd",
                    "tick_jit", "tau_z", "th", "th_lo", "tau_R", "tau_e", "h_inc", "c_live", "c_spike", "c_tw",
                    "c_msg", "c_div", "c_sec", "window_h", "drop_p", "noise_rate", "kill_t", "kill_frac",
                    "stuck_t", "e_max"):
            setattr(self, key, wv[wi[key]])
        for key in ("flags", "fork_flags", "n_max", "fabric_R", "oracle_cap", "stuck_a", "stuck_b"):
            setattr(self, key, int(wv[wi[key]]))
        self.t1 = self.t0 + self.T
        self.t_open_abs = self.t0 + self.t_open
        self.t_fork_abs = self.t0 + self.t_fork
        self.lockstep = bool(self.flags & _F["lockstep"])
        if self.lockstep:
            self.jit = 0.0
            self.tick_jit = 0.0
        self.program = bool(self.flags & _F["program_mode"])
        self.seed, self.tie_seed, self.order_seed, self.salt = (int(s) & spec.MASK64 for s in seeds)
        self.raster_cap, self.fate_cap, self.keep_records = int(raster_cap), int(fate_cap), keep_records

        self.kind, self.D = lat["kind"], lat["D"]
        self.off_a, self.off_b, self.back = lat["off_a"], lat["off_b"], lat["back"]
        self.prev, self.next, self.ux, self.uy = lat["prev"], lat["next"], lat["ux"], lat["uy"]

        if self.program:
            p = [float(x) for x in prog]
            self.rows = [p[i * spec.P:(i + 1) * spec.P] for i in range(len(spec.PROGRAM_ROWS))]
            sc = p[len(spec.PROGRAM_ROWS) * spec.P:]
            for name, i in _PS.items():
                setattr(self, "p_" + name, sc[i])
            self.Dm = (self.p_Dm0, self.p_Dm1)
            self.km = (self.p_km0, self.p_km1)
        else:
            g = [float(x) for x in gt]
            sl = spec.GENOME_SLICES
            self.W = g[sl["W"][0]:sl["W"][1]]
            self.gb = g[sl["b"][0]:sl["b"][1]]
            self.lam = g[sl["lam"][0]:sl["lam"][1]]
            self.g0 = g[sl["s0"][0]:sl["s0"][1]]
            self.Q = g[sl["Q"][0]:sl["Q"][1]]
            self.A = g[sl["A"][0]:sl["A"][1]]
            self.a0 = g[sl["a0"][0]:sl["a0"][1]]
            self.Dm = tuple(g[sl["Dm"][0]:sl["Dm"][1]])
            self.km = tuple(g[sl["km"][0]:sl["km"][1]])
        self.init = init  # [(a, b, row)]

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
        self.next_c = self.t0 + 1.0  # next integer time at which the guards are checked
        self.acct = _Accountant(self)

    # ----------------------------------------------------------------------------------------------- plumbing
    def flag(self, name: str, t: float) -> bool:
        bit = _F[name]
        return bool(self.flags & bit) or (bool(self.fork_flags & bit) and t >= self.t_fork_abs)

    def site(self, a: int, b: int) -> _Site:
        sk = spec.sitekey(a, b)
        s = self.sites.get(sk)
        if s is None:
            s = self.sites[sk] = _Site(a, b)
        return s

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
        tie = self.tie_cache.get(site.sk)
        if tie is None:
            tie = self.tie_cache[site.sk] = spec.hash64(self.tie_seed, spec.S_TIE, site.sk)
        heapq.heappush(self.heap, (t, tie, site.sk, key, ev))

    def send(self, src: _Site, d: int, t: float, ev: tuple) -> None:
        """A message through slot d of ``src``; ``ev[1]`` is filled with the receiver slot back[d]."""
        dst = self.site(src.a + self.off_a[d], src.b + self.off_b[d])
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
        c.t_tr = t

    def membrane(self, c: _Cell, t: float, arr: list, kicks: list, thr: bool) -> None:
        if arr:
            self.traces(c, t)
            n0 = n1 = 0
            for _slot, mask in arr:
                n0 += mask & 1
                n1 += (mask >> 1) & 1
            c.r0 = c.r0 + float(n0)
            c.r1 = c.r1 + float(n1)
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
        if n_ch > 0 and not self.flag("contacts_off", t):
            mask = e0 | (e1 << 1)
            for d in range(self.D):
                if c.view[d] == EMPTY:
                    continue
                if self.drop_p > 0 and spec.draw(self.seed, spec.S_DROP, c.uid, c.nspk, d) < self.drop_p:
                    continue
                u = spec.draw(self.seed, spec.S_JIT, c.uid, c.nspk, d)
                dl = c.dc[d] * (1.0 + self.jit * (2.0 * u - 1.0)) + th[KDEL]
                if dl < self.d_min:
                    dl = self.d_min
                self.send(c.site, d, t + dl, (ARRIVAL, c.view[d], mask))
        dz = 0.0
        kap = th[KKAP]
        if kap > 0:
            zt = c.z * math.exp(-(t - c.t_z) / self.tau_z)
            zn = zt + kap
            if zn > 1.0:
                zn = 1.0
            dz = zn - zt
            c.z = zn
            c.t_z = t
        self.emit(R_SPIKE, (c.uid, kap, n_out, dz))
        self.predict(c)

    # -------------------------------------------------------------------------------------------- phenotype (8)
    def decode(self, c: _Cell) -> list[float]:
        g, A, a0 = c.g, self.A, self.a0
        y = []
        for p in range(spec.P):
            acc = a0[p]
            for k in range(spec.G_MAX):
                acc = acc + A[p * spec.G_MAX + k] * g[k]
            y.append(acc)
        return spec.decode_knobs(y)

    def select(self, c: _Cell, n_view: int) -> list[float]:
        """Program-mode selector of section 7.5 (tick# before its increment)."""
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
        # 3. inputs
        self.traces(c, t)
        view = c.view
        n_view = sum(1 for u in view if u != EMPTY)
        flank = [0] * D
        fb = 0
        any_empty = False
        for e in range(D):
            if view[e] == EMPTY:
                any_empty = True
                flank[e] = (view[self.prev[e]] != EMPTY) + (view[self.next[e]] != EMPTY)
                if flank[e] > fb:
                    fb = flank[e]
        # 4. genes (or the program timer)
        if not (self.flag("identity_clamp", t) or self.flag("freeze", t)):
            if self.program:
                c.timer = c.timer + self.p_timer_step
            else:
                ttr = c.th[KTTR]  # no flank_best input since ABI 2 (LIFE_ABI.md 15.32): fb serves the program gate
                x = list(c.g) + [c.m[0] / (1.0 + c.m[0]), c.m[1] / (1.0 + c.m[1]), c.f / ttr, c.r0 / ttr,
                                 c.r1 / ttr, n_view / D]
                if self.flag("genes_blind", t):
                    for j in range(18, spec.NIN):
                        x[j] = 0.0
                s = []
                for k in range(spec.G_MAX):
                    p = self.gb[k]
                    row = k * spec.NIN
                    for j in range(spec.NIN):
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
                nsk = spec.sitekey(c.site.a + self.off_a[d], c.site.b + self.off_b[d])
                self.emit(R_PACKET, (c.uid, view[d], nsk, amt0, amt1))
            m[0] = m[0] - nv * amt0
            m[1] = m[1] - nv * amt1
        self.emit(R_CHEM, (sec, dec, clamp))
        # 8. division
        if not (self.flag("division_off", t) or freeze) and c.pending == 0 and any_empty:
            p = th[KPDIV]
            ok = True
            if self.program:
                if self.p_flank_gate > 0 and fb < self.p_flank_gate:
                    p = self.p_p_div_lo
                ok = c.timer <= self.p_k_grow
            if (ok and p > 0 and spec.draw(self.seed, spec.S_DIV, c.uid, c.ntick) < p
                    and (self.oracle_cap == 0 or self.cap_count < self.oracle_cap)):
                self.divide(c, t, flank)
        # 9. next tick
        per = c.P_n * (1.0 + self.tick_jit * (2.0 * spec.draw(self.seed, spec.S_TICK, c.uid, c.ntick) - 1.0))
        self.push(t + per, c.site, (TICK, c.uid))
        c.ntick += 1
        c.t_prev = t

    def divide(self, c: _Cell, t: float, flank: list) -> None:
        th = c.th
        px = py = 0.0
        for d in range(self.D):
            px = px + c.s[d] * self.ux[d]
            py = py + c.s[d] * self.uy[d]
        vx = px - th[KCHI] * py
        vy = py + th[KCHI] * px
        best, best_sc = -1, 0.0
        for e in range(self.D):
            if c.view[e] != EMPTY:
                continue
            sc = (self.ux[e] * vx + self.uy[e] * vy + th[KPHI] * float(flank[e])
                  + spec.PLACE_NOISE * spec.draw(self.seed, spec.S_PLACE, c.uid, c.ndiv, e))
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
        tsk = spec.sitekey(c.site.a + self.off_a[best], c.site.b + self.off_b[best])
        self.emit(R_CLAIM, (c.uid, daughter, tsk))
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
        c.nspk = c.ntick = c.ndiv = 0
        c.pending = 0
        c.v_a, c.t_a, c.t_r, c.ver = 0.0, t, t, 0
        c.f = c.r0 = c.r1 = 0.0
        c.t_tr = t
        c.z, c.t_z, c.t_prev = 0.0, t, t
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
        self.emit(R_BIRTH, (uid, mother, k, init >= 0, tuple(c.g), site.a, site.b))
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
        if self.stuck_t >= 0 and (site.a, site.b) == (self.stuck_a, self.stuck_b) and t < self.t0 + self.stuck_t:
            self.push(self.t0 + self.stuck_t, site, (STUCK, uid))
        for d in range(D):
            self.send(site, d, t + self.d_min, (BORN, uid, k))
        if mother != 0:
            self.send(site, bslot, t + self.d_min, (ACK, mother, uid, k))

    def apoptosis(self, c: _Cell, t: float, cause: int) -> None:
        zt = c.z * math.exp(-(t - c.t_z) / self.tau_z)
        content = self.content(c)
        self.emit(R_DEATH, (c.uid, cause, zt, content, t - c.t_birth, tuple(c.g), c.mother, c.site.a, c.site.b))
        c.alive = False
        c.site.occ = None
        c.inbox = []
        self.n_alive -= 1
        for d in range(self.D):
            self.send(c.site, d, t + self.d_min, (DIED, c.uid))

    def dc_of(self, c: _Cell, d: int, k_nb: int) -> float:
        if self.lockstep:
            return self.d0
        nsk = spec.sitekey(c.site.a + self.off_a[d], c.site.b + self.off_b[d])
        z = spec.normal(self.seed, spec.S_DC, c.site.sk, nsk, ((c.k << 32) | k_nb) & spec.MASK64)
        return self.d0 * math.exp(self.delay_sd * z)

    # ------------------------------------------------------------------------------------------- batch (6.2)
    def batch(self, t: float, site: _Site, evs: list) -> None:
        self.bt, self.bsk, self.seq = t, site.sk, 0
        occ = site.occ  # the live occupant at t-
        claims, notices, packets, arrivals, thrs, noises, exo = [], [], [], [], [], [], []
        tick = None
        for ev in evs:
            g = ev[0] // 10
            if g == 0:
                claims.append(ev)
            elif g == 1:
                notices.append(ev)
            elif g == 2:
                packets.append(ev)
            elif ev[0] == ARRIVAL:
                arrivals.append(ev)
            elif ev[0] == THRESHOLD:
                thrs.append(ev)
            elif ev[0] == NOISE:
                noises.append(ev)
            elif ev[0] == TICK:
                tick = ev
            else:
                exo.append(ev)
        # 0. claims, against the occupancy at t-
        if claims:
            exists = self.fabric_R == 0 or _lat.in_disk(self.kind, site.a, site.b, self.fabric_R)
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
                self.emit(R_RESOLVE, (daughter, mother, res, site.a, site.b))
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
        # 3. membrane
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
        if arr or kicks or thr:
            self.membrane(occ, t, arr, kicks, thr)
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
        """Check the guards at integer times c <= x not yet checked (section 10); return (c, bits) on a trip."""
        while self.next_c <= x and self.next_c <= self.t1 - 1.0:
            c = self.next_c
            gb = 0
            if self.acct.n >= self.n_max:
                gb |= _ST["guard_cells"]
            if self.events > self.e_max:
                gb |= _ST["guard_events"]
            if gb:
                return c, gb
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
        for j, (a, b, row) in enumerate(self.init):
            site = self.site(a, b)
            self.bt, self.bsk, self.seq = self.t0, site.sk, 0
            payload = 0.0 if self.program else tuple(self.g0)
            self.birth(self.t0, site, spec.uid_initial(self.seed, j), 0, -1, payload, j, row if self.program else -1)
        self.feed(recs)

    def run_heap(self):
        heap = self.heap
        pending: list = []
        t_group = None
        while heap and heap[0][0] < self.t1:
            t = heap[0][0]
            if pending and t > t_group:
                self.feed(pending)
                pending = []
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
        if pending:
            self.feed(pending)
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
            self.feed(recs)
            k_next = k + 1
        return self.guards_upto(self.t1 - 1.0)

    def run(self) -> LifeResult:
        self.start()
        trip = self.run_window() if self.window_h > 0 else self.run_heap()
        t_end, gb = trip if trip else (self.t1, 0)
        self.acct.close(t_end, gb)
        return self.result()

    def result(self) -> LifeResult:
        a = self.acct
        fi = np.array([[r[0], _i64(r[1]), _i64(r[2]), r[3], r[4], r[5]] for r in a.fate], dtype=np.int64)
        ff = np.array([[r[6], r[7], *r[8]] for r in a.fate], dtype=np.float64)
        return LifeResult(
            ledger=np.array(a.led, dtype=np.float64), hashes=np.array(a.h, dtype=np.uint64),
            raster_t=np.array(a.raster_t, dtype=np.float64), raster_uid=np.array(a.raster_uid, dtype=np.uint64),
            raster_n=a.raster_n, fate_i=fi.reshape(-1, spec.FATE_I_SIZE), fate_f=ff.reshape(-1, spec.FATE_F_SIZE),
            fate_n=a.fate_n, records=a.records)


def _i64(u: int) -> int:
    return u - (1 << 64) if u >= 1 << 63 else u


# ------------------------------------------------------------------------------------------------------- arguments
def _lattice(lat, unit) -> dict:
    tab = [int(x) for x in np.asarray(lat).ravel()]
    if len(tab) < 2 or tab[0] not in _D_KIND:
        raise ArgError(-4, "invalid lattice table")
    kind, D = _D_KIND[tab[0]], tab[1]
    if D != len(_lat.offsets(kind)) or len(tab) != 2 + 6 * D:
        raise ArgError(-4, "lattice table size does not match its code")
    off_a, off_b, back, prev, nxt = (tab[2 + i * D: 2 + (i + 1) * D] for i in range(5))
    for d in range(D):
        if not (0 <= back[d] < D and 0 <= prev[d] < D and 0 <= nxt[d] < D):
            raise ArgError(-4, "lattice slot index out of range")
        if (off_a[back[d]], off_b[back[d]]) != (-off_a[d], -off_b[d]):
            raise ArgError(-4, "back[] does not point back")
    u = np.asarray(unit, dtype=np.float64).reshape(D, 2)
    return dict(kind=kind, D=D, off_a=off_a, off_b=off_b, back=back, prev=prev, next=nxt,
                ux=[float(x) for x in u[:, 0]], uy=[float(x) for x in u[:, 1]])


def _check_world(wv) -> None:
    """Return code -2 for the vectors that ``spec.validate_world`` would refuse."""
    wv = np.asarray(wv, dtype=np.float64)
    if wv.shape != (spec.WORLD_SIZE,) or not np.all(np.isfinite(wv)):
        raise ArgError(-2, "world vector must hold 41 finite numbers")
    vals = {}
    for f_ in fields(spec.World):
        if f_.name not in spec.WORLD_INDEX:
            continue
        x = float(wv[spec.WORLD_INDEX[f_.name]])
        if f_.type in ("int", int):
            if x != int(x):
                raise ArgError(-2, f"{f_.name} must be an integer")
            x = int(x)
        vals[f_.name] = x
    try:
        spec.validate_world(spec.World(**vals))
    except (ValueError, NotImplementedError) as e:
        raise ArgError(-2, str(e)) from None


def run_life(world_vec, lat, unit, *, genome_table=None, program=None, init=None, seeds=(0, 0, 0, 0),
             raster_cap: int = 0, fate_cap: int = 0, records: bool = False) -> LifeResult:
    """One life from kernel-format inputs: world float64 [41], lattice tables (4.3), a packed genome row [793]
    (GRN mode) or a program row [119] (program mode), an initial body [(a, b, row)] (None = one zygote at (0, 0)),
    and the four seeds (life, tie, order, relabel salt)."""
    _check_world(world_vec)
    latd = _lattice(lat, unit)
    flags = int(world_vec[spec.WORLD_INDEX["flags"]])
    prog_mode = bool(flags & _F["program_mode"])
    if prog_mode and program is None:
        raise ArgError(-1, "program mode needs a program table")
    if not prog_mode and genome_table is None:
        raise ArgError(-1, "GRN mode needs a packed genome table")
    if prog_mode and np.asarray(program).shape != (spec.PROGRAM_SIZE,):
        raise ArgError(-1, "program rows have 119 entries")
    if not prog_mode and np.asarray(genome_table).shape != (spec.GENOME_SIZE,):
        raise ArgError(-1, f"packed genome rows have {spec.GENOME_SIZE} entries")
    if not np.all(np.isfinite(np.asarray(program if prog_mode else genome_table, dtype=np.float64))):
        raise ArgError(-1, "a table row holds NaN or infinity")
    cells = [(0, 0, -1)] if not init else [(int(a), int(b), int(r)) for a, b, r in init]
    if len(cells) > spec.MAX_INIT or len({(a, b) for a, b, _ in cells}) != len(cells):
        raise ArgError(-4, "initial body: more than 64 cells or duplicate sites")
    if any(not -1 <= r < len(spec.PROGRAM_ROWS) for _, _, r in cells):
        raise ArgError(-4, "initial body: program row out of range")
    life = _Life(world_vec, latd, genome_table, program, cells, seeds, raster_cap, fate_cap, records)
    return life.run()


def run(w: spec.World, *, genome=None, genome_table=None, program=None, cells=None, rows=None, seed: int = 0,
        tie_seed: int = 0, order_seed: int = 0, salt: int = 0, raster_cap: int = 4096, fate_cap: int = 4096,
        records: bool = False) -> LifeResult:
    """Convenience wrapper: a ``spec.World``, a raw float32 genome [793] (or its packed table) or a program
    (``spec.pack_program``, which switches on ``program_mode``), and an optional explicit initial body."""
    if program is not None:
        w = replace(w, flags=w.flags | _F["program_mode"])
    lat, unit = spec.lattice_tables(w.lattice)
    if genome is not None:
        genome_table = spec.pack_genomes(genome, w.lattice)[0]
    init = None
    if cells is not None:
        rws = [-1] * len(cells) if rows is None else list(rows)
        init = [(a, b, r) for (a, b), r in zip(cells, rws)]
    return run_life(spec.pack_world(w), lat, unit, genome_table=genome_table, program=program, init=init,
                    seeds=(seed, tie_seed, order_seed, salt), raster_cap=raster_cap, fate_cap=fate_cap,
                    records=records)


def life_run(lat, unit, genomes, programs, genome_of, init_cells, n_init, world, seeds, raster_cap: int = 0,
             fate_cap: int = 0, threads: int = 1) -> dict:
    """The kernel entry point ``life_run`` (LIFE_ABI.md 4.2) with numpy arrays in and out.

    Returns ``rc`` and the output arrays ``ledger [n,35]``, ``hashes [n,4]``, ``raster_t``/``raster_uid [n,cap]``,
    ``raster_n [n]``, ``fate_i [n,cap,6]``, ``fate_f [n,cap,18]`` and ``fate_n [n]``. ``threads`` is ignored.
    """
    genome_of = np.asarray(genome_of, dtype=np.int32).ravel()
    n = len(genome_of)
    rc, cap_r, cap_f = 0, max(int(raster_cap), 0), max(int(fate_cap), 0)
    out = dict(ledger=np.zeros((n, spec.LEDGER_SIZE)), hashes=np.zeros((n, spec.HASH_SIZE), dtype=np.uint64),
               raster_t=np.zeros((n, cap_r)), raster_uid=np.zeros((n, cap_r), dtype=np.uint64),
               raster_n=np.zeros(n, dtype=np.int64), fate_i=np.zeros((n, cap_f, spec.FATE_I_SIZE), dtype=np.int64),
               fate_f=np.zeros((n, cap_f, spec.FATE_F_SIZE)), fate_n=np.zeros(n, dtype=np.int64))
    world = np.asarray(world, dtype=np.float64).reshape(n, spec.WORLD_SIZE)
    seeds = np.asarray(seeds, dtype=np.uint64).reshape(n, 4)
    gts = None if genomes is None else np.asarray(genomes, dtype=np.float64).reshape(-1, spec.GENOME_SIZE)
    prs = None if programs is None else np.asarray(programs, dtype=np.float64).reshape(-1, spec.PROGRAM_SIZE)
    body = None if init_cells is None else np.asarray(init_cells, dtype=np.int32).reshape(n, spec.MAX_INIT, 3)
    nin = np.zeros(n, dtype=np.int32) if n_init is None else np.asarray(n_init, dtype=np.int32).ravel()
    try:
        _lattice(lat, unit)
        jobs = []
        for i in range(n):
            _check_world(world[i])
            gi = int(genome_of[i])
            prog_mode = bool(int(world[i][spec.WORLD_INDEX["flags"]]) & _F["program_mode"])
            table = prs if prog_mode else gts  # each table has its own row count
            if table is None or not 0 <= gi < len(table):
                raise ArgError(-1, "a life needs a table that was not given, or genome_of is outside it")
            if not 0 <= nin[i] <= spec.MAX_INIT or (nin[i] > 0 and body is None):
                raise ArgError(-4, "invalid n_init")
            init = None if nin[i] == 0 else [tuple(int(v) for v in body[i, j]) for j in range(nin[i])]
            jobs.append((world[i], table[gi], prog_mode, init, [int(s) for s in seeds[i]]))
        for i, (wv, row, prog_mode, init, sd) in enumerate(jobs):
            res = run_life(wv, lat, unit, genome_table=None if prog_mode else row, program=row if prog_mode else None,
                           init=init, seeds=sd, raster_cap=cap_r, fate_cap=cap_f)
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
