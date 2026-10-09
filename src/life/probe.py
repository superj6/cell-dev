"""Probe toolkit for interpreting how CATCH bodies work (cell-dev, ABI 3). See docs/PROBE.md.

Usage (from the repository root; on a shared machine under ``nice -n 19``):

    from src.life import probe as P
    org, preset = P.load("speck_lmax4_hexprism_sex_s5")      # or P.hand("router@ring4")
    tr = P.trace(org, P.SEEDS[0], preset)                      # one fully logged life (pure-Python reference)
    P.tuning(tr); P.ccg(tr); P.act_drivers(tr); P.chains(tr)   # probes on the trace
    P.lesion(org, preset, "lateral_off", t_fork=256, n_lives=128)   # kernel fork, paired dF

Design
- ``trace`` runs one life in ``src/life/reference.py`` (bitwise equal to the C kernel) through a subclass that only
  *observes*: hooks on birth, death, FIRE, the membrane step, TICK, ``send`` and the CATCH accountant (strokes, clicks,
  placements, samples). It checks the life's F against the kernel's on the same seed (``check=True``), so a trace is
  the real life, not a re-simulation.
- The same subclass implements per-cell / per-channel / per-slot *message* lesions after ``t_fork`` (``Lesion``),
  which the kernel has no fork for. A lateral-slot lesion reproduces the kernel's ``lateral_off`` fork bitwise
  (``check_lesion_equivalence``).
- ``trace_kernel`` is the fast partial alternative (kernel raster + fate log): cells, spikes (no channel mask, no
  receptor events, no world trajectory), knobs at birth. Enough for ``ccg`` and ``act_drivers`` on many lives.
Nothing here writes into the repository.
"""
from __future__ import annotations

import json
import math
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.genome import Layout
from src.life import analysis, reference, spec
from src.life import handbuilt as hb

ROOT = Path(__file__).resolve().parents[2]  # the repository

V3 = spec.V3
K = V3.K
KNOBS = V3.KNOBS
SEED0 = 30_000_000  # this toolkit's life seeds (disjoint from the pre-registered ranges)
SEEDS = analysis.fresh_seeds(4096, seed0=SEED0)
S32 = reference.S32
_R = reference
_KE0, _KE1, _KKAP, _KGR = K["emit0"], K["emit1"], K["kappa"], K["g_r"]
# hexprism slots (LIFE_ABI.md 4.3): 6 in-plane, then up, then down
OFF = ((1, 0, 0), (1, -1, 0), (0, -1, 0), (-1, 0, 0), (-1, 1, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1))
UNIT = ((1.0, 0.0), (0.5, -S32), (-0.5, -S32), (-1.0, 0.0), (-0.5, S32), (0.5, S32), (0.0, 0.0), (0.0, 0.0))
CONTINUOUS_KNOBS = ("asym", "sec0", "sec1")
CAUSES = {0: "input", 1: "threshold", 2: "tick", 3: "input+threshold", -1: "other"}
OUTCOMES = {0: "miss", 1: "capture", 2: "blob1"}
_F64 = struct.Struct("<d")
_Q64 = struct.Struct("<Q")


def _f(bits: int) -> float:
    return _F64.unpack(_Q64.pack(bits))[0]


def planar(a, b):
    """Planar offset of column (a, b) in the dot's frame (hex base, LIFE_ABI.md 4.3)."""
    return float(a) + 0.5 * float(b), float(b) * S32


def hexdist(a: int, b: int) -> int:
    return max(abs(a), abs(b), abs(a + b))


def plane(z: int) -> str:
    return "S" if z == 0 else ("M" if z == 1 else "H")


def cell_class(a: int, b: int, z: int) -> str:
    """Default class label: C = centre sense (0,0,0), S = other sense, K = hotspot (0,0,1), M = other act,
    H = hidden."""
    if z == 0:
        return "C" if (a, b) == (0, 0) else "S"
    if z == 1:
        return "K" if (a, b) == (0, 0) else "M"
    return "H"


# ================================================================================================= bodies
def load(run: str, root: str | Path | None = None):
    """(GrnBody, preset) for <root>/<run>/best_genome.json (root: outputs/catch_pilot; read-only). The preset is the
    run's own world: the ``world:`` key of its config.yaml (as scripts/catch_pilot_analysis.py reads it), else the
    results row, else the name rule (speck* -> catch_speck_l4, lmax2* -> catch_v1_l2, otherwise catch_v1_l4). In this
    pilot that gives speck_* -> catch_speck_l4, lmax4_* and seeded_* -> catch_v1_l4, lmax2_* -> catch_v1_l2."""
    d = (ROOT / "outputs" / "catch_pilot" if root is None else Path(root)) / run
    _, g = Layout.load(d / "best_genome.json")
    g = np.asarray(g, dtype=np.float32).reshape(-1)
    preset = "catch_speck_l4" if run.startswith("speck") else ("catch_v1_l2" if run.startswith("lmax2")
                                                                  else "catch_v1_l4")
    cfg, res = d / "config.yaml", d / "results.jsonl"
    found = None
    if cfg.exists():
        for line in cfg.read_text().splitlines():
            k, _, v = line.partition(":")
            if k.strip() == "world" and v.strip() in spec.PRESETS:
                found = v.strip()
                break
    if found is None and res.exists():
        try:
            found = json.loads(res.read_text().splitlines()[0]).get("world")
        except (ValueError, IndexError):
            pass
    return hb.GrnBody(run, g), (found if found in spec.PRESETS else preset)


def hand(name: str):
    """(Body, "catch_speck_l4") for a tuned hand-built SPECK body, e.g. "reflex@hollow3" or "router@ring4"."""
    return hb.speck_body(name), "catch_speck_l4"


def is_program(org) -> bool:
    return isinstance(org, hb.Body)


def _world(org, preset: str, **world) -> spec.World:
    return org.world(preset, **world)


# ============================================================================================ lesions (reference)
@dataclass
class Lesion:
    """Block message delivery after ``t_fork`` (relative to t0) in the reference simulator.

    An ARRIVAL the sender would send through slot d after t_fork has the channel bits ``channels`` removed when the
    sender matches every given filter; if no bit is left, it is not sent (spikes are still charged n_out, as with the
    kernel's lateral_off / hidden_off). Filters: ``slots`` "all" | "lateral" | "up" | "down" | "vertical";
    ``planes`` sender heights (2 stands for every z >= 2); ``sites`` sender sites (a, b, z); ``where(site, cell)`` any
    predicate on the sender (``cell.th`` is its current phenotype list, ``cell.uid`` its uid)."""
    t_fork: float
    channels: int = 3
    slots: str = "all"
    planes: tuple | None = None
    sites: set | None = None
    where: object = None

    def mask(self, life, src, d: int) -> int:
        oz = OFF[d][2]
        s = self.slots
        if s != "all":
            if (s == "lateral" and oz != 0) or (s == "up" and oz != 1) or (s == "down" and oz != -1) or \
                    (s == "vertical" and oz == 0):
                return 0
        if self.planes is not None and min(src.z, 2) not in self.planes:
            return 0
        if self.sites is not None and (src.a, src.b, src.z) not in self.sites:
            return 0
        if self.where is not None and not self.where(src, src.occ):
            return 0
        return self.channels


# ===================================================================================== the observing simulator
class _TAcct(_R._Accountant):
    """The reference accountant plus logs of the CATCH world (exact positions at record times)."""

    def __init__(self, life):
        self.t_place, self.t_click, self.t_turn, self.t_samp, self.t_stroke = [], [], [], [], []
        self.t_pos = {}
        super().__init__(life)

    def _fold_world(self, words) -> None:
        k = words[0]
        if k == _R.W_CLICK:
            self.t_click.append((_f(words[1]), int(words[2]), _f(words[3]), _f(words[4])))
        elif k == _R.W_PLACE:
            self.t_place.append((_f(words[1]), int(words[2]), int(words[3]), _f(words[4]), _f(words[5])))
        elif k == _R.W_TURN:
            self.t_turn.append((_f(words[1]), int(words[2]), _f(words[3]), _f(words[4])))
        super()._fold_world(words)

    def sample(self, c: float) -> None:
        super().sample(c)
        X, Y = self.dot_at(c)
        x0, y0 = self.blob_at(0, c)
        self.t_samp.append((c, X, Y, x0, y0))

    def group(self, t: float, recs: list) -> None:
        if self.life.catch and self.life.log:
            self.world_to(t)  # group() does this first too; running world events below t twice is a no-op
            for r in recs:
                if r[3] == _R.R_SPIKE or r[3] == _R.R_RECEPT:
                    X, Y = self.dot_at(t)
                    x0, y0 = self.blob_at(0, t)
                    self.t_pos[t] = (X, Y, x0, y0)
                    break
        super().group(t, recs)

    def _rcand(self, t, site, uid, j, counted) -> None:
        L = self.life
        if L.log:
            X, Y = self.dot_at(t)
            ox, oy = L.planar(site.a, site.b)
            x0, y0 = self.blob_at(0, t)
            sig = L.lam_s * spec.halo(X + ox - x0, Y + oy - y0, L.sigma)
            rate = L.lam_bg + sig
            if len(self.blobs) > 1 and self.blobs[1].present:
                x1, y1 = self.blob_at(1, t)
                rate = rate + L.lam_s * (L.b2_amp * spec.halo(X + ox - x1, Y + oy - y1, L.b2_sigma))
            if spec.draw(L.seed, spec.S_RACC, uid, j) * L.lam_max < rate:
                L.rec_sig[(uid, t + L.d_min)] = sig / rate
        super()._rcand(t, site, uid, j, counted)

    def _stroke(self, t, site, dz, zt, zn, counted) -> None:
        if self.life.log:
            L = self.life
            nx = ny = 0.0
            for d in L.planar_slots:
                if (site.a + L.off_a[d], site.b + L.off_b[d]) not in self.O:
                    nx = nx + L.ux[d]
                    ny = ny + L.uy[d]
            X, Y = self.dot_at(t)
            x0, y0 = self.blob_at(0, t)
            self.t_stroke.append((t, site.a, site.b, nx, ny, dz, zt, zn, X, Y, x0, y0))
        super()._stroke(t, site, dz, zt, zn, counted)


class _TLife(_R._Life):
    """reference._Life with observation hooks (``log``) and optional message lesions (``lesion``)."""

    def __init__(self, *args, log: bool = True, lesion: Lesion | None = None, **kw):
        super().__init__(*args, **kw)
        self.log = log
        self.lesion = lesion
        self.lz_t = None if lesion is None else self.t0 + lesion.t_fork
        self.n_blocked = 0
        self.L_birth, self.L_death, self.L_spk, self.L_step, self.L_arr, self.L_rec, self.L_pheno = \
            [], [], [], [], [], [], []
        self.cid = {}  # uid -> cell index (birth order)
        self.arr_src = {}  # (receiver sk, t_arrival, receiver slot) -> sender spike id
        self.rec_sig = {}  # (uid, delivery time) -> P(the event came from the target, not the background)
        self.cause, self.cur_step, self.cur_spk = -1, -1, -1
        # knobs whose changes are logged: every gridded knob; asym, sec0 and sec1 are continuous (sigma-decoded) and
        # change at nearly every tick of a GRN cell, so they are left out (their end values are in knobs_end)
        self.pheno_knobs = [p for p, k in enumerate(KNOBS) if k not in CONTINUOUS_KNOBS]
        self.acct = _TAcct(self)  # replaces the plain accountant (its construction is pure)

    # births and deaths
    def birth(self, t, site, uid, mother, bslot, payload, init, row) -> None:
        super().birth(t, site, uid, mother, bslot, payload, init, row)
        if self.log:
            c = site.occ
            self.cid[uid] = len(self.L_birth)
            self.L_birth.append((uid, site.a, site.b, site.z, t, mother, init, c.k, row, tuple(c.g), tuple(c.th)))

    def apoptosis(self, c, t, cause) -> None:
        if self.log:
            self.L_death.append((c.uid, t, cause, tuple(c.g), tuple(c.th)))
        super().apoptosis(c, t, cause)

    # spikes and their causes
    def fire(self, c, t) -> None:
        if self.log:
            th = c.th
            mask = (1 if th[_KE0] != 0.0 else 0) | (2 if th[_KE1] != 0.0 else 0)
            self.cur_spk = len(self.L_spk)
            s = c.site
            self.L_spk.append((t, self.cid.get(c.uid, -1), s.a, s.b, s.z, mask, th[_KKAP], self.cause, self.cur_step))
        super().fire(c, t)
        self.cur_spk = -1

    def membrane(self, c, t, arr, kicks, thr, n_rec=0) -> None:
        if not self.log:
            return super().membrane(c, t, arr, kicks, thr, n_rec)
        refr = t < c.t_r
        sid = len(self.L_step)
        v0 = 0.0 if refr else (1.0 if thr else self.vnow(c, t))
        rin = c.th[_KGR] * float(n_rec) if (n_rec and not refr) else 0.0
        sk = c.site.sk
        for slot, mask in arr:
            contrib = 0.0
            if not refr:
                if mask & 1:
                    contrib = contrib + c.w_eff[slot][0]
                if mask & 2:
                    contrib = contrib + c.w_eff[slot][1]
            self.L_arr.append((sid, slot, mask, contrib, self.arr_src.pop((sk, t, slot), -1), c.view[slot]))
        if n_rec:
            self.L_rec.append((t, self.cid.get(c.uid, -1), n_rec, c.th[_KGR], refr, sid,
                               self.rec_sig.pop((c.uid, t), np.nan)))
        self.cause = 3 if (thr and (arr or n_rec)) else (1 if thr else 0)
        self.cur_step = sid
        n0 = c.nspk
        super().membrane(c, t, arr, kicks, thr, n_rec)
        s = c.site
        self.L_step.append((t, self.cid.get(c.uid, -1), s.a, s.b, s.z, v0, rin, refr, c.nspk > n0, thr, len(arr)))
        self.cause, self.cur_step = -1, -1

    def tick(self, c, t) -> None:
        if not self.log:
            return super().tick(c, t)
        old = c.th[:]
        self.cause, self.cur_step = 2, -1
        super().tick(c, t)
        self.cause = -1
        if c.th != old:
            ci = self.cid.get(c.uid, -1)
            for p in self.pheno_knobs:
                if c.th[p] != old[p]:
                    self.L_pheno.append((t, ci, p, old[p], c.th[p]))

    def send(self, src, d, t, ev) -> None:
        if ev[0] == _R.ARRIVAL:
            lz = self.lesion
            if lz is not None and self.bt >= self.lz_t:
                blk = lz.mask(self, src, d)
                if blk and (ev[2] & blk):
                    self.n_blocked += 1
                    m = ev[2] & ~blk
                    if m == 0:
                        return
                    ev = (ev[0], ev[1], m)
            if self.log:
                dst = self.neighbour(src, d)
                self.arr_src[(dst.sk, t, self.back[d])] = self.cur_spk
        super().send(src, d, t, ev)


def _inputs(org, w: spec.World):
    """Kernel-format inputs of one life of ``org`` in world ``w`` (as reference.run builds them)."""
    lat, unit = V3.lattice_tables(w.lattice)
    latd = _R._lattice(lat, unit, V3)
    if is_program(org):
        init = [tuple(int(v) for v in c) for c in org.cells]
        wv, gt, prog, cells = _R._prepare(V3.pack_world(w), latd, None, np.asarray(org.program, np.float64), init, V3)
    else:
        gtab = V3.pack_genomes(np.asarray(org.genome)[None], w.lattice)[0]
        wv, gt, prog, cells = _R._prepare(V3.pack_world(w), latd, gtab, None, None, V3)
    return wv, latd, gt, prog, cells


def _life(org, seed: int, w: spec.World, log: bool, lesion: Lesion | None) -> _TLife:
    wv, latd, gt, prog, cells = _inputs(org, w)
    return _TLife(wv, latd, gt, prog, cells, (int(seed), 0, 0, 0), 0, 0, False, out_abi=V3, log=log, lesion=lesion)


# ============================================================================================== traces
@dataclass
class Trace:
    """One fully logged life. Every table is a pandas DataFrame; ``cid`` (cell index in birth order) links them.

    cells      cid, uid, a, b, z, x, y, plane, cls, t_birth, t_death (inf if alive at the end), death_cause, mother
               (uid), mother_cid, initial, k, row (program row or -1), n_spikes, n_rec
    knobs_birth / knobs_end   [cid x 23 knobs] phenotype at birth and at death or the end of the life
    genes_birth / genes_end   [cid x 16] gene state at birth and at death or the end (zeros in program mode)
    pheno_changes  t, cid, knob, old, new: every change of a gridded knob at a tick (GRN mode re-decodes at every
               tick; the continuous knobs asym, sec0, sec1 change almost every tick and are not logged)
    spikes     sid, t, cid, a, b, z, cls, mask (channel bits at fire time: 1 = ch0, 2 = ch1), kappa, cause (input,
               threshold, tick, input+threshold), step (membrane step id or -1), X, Y (dot), tx, ty (target)
    steps      step, t, cid, a, b, z, v0 (membrane before this step's input; 1.0 if a threshold crossing), rin
               (receptor input g_r n_rec), refractory, fired, thr, n_arr
    arrivals   step, t, cid (receiver), slot (receiver's slot), dir (lat/up/down: where the SENDER sits relative to the
               receiver: up = from the cell above), sa, sb, sz (sender site), s_cid, s_sid (sender spike id, -1 if
               unknown), mask, contrib (w_eff . mask; 0 while refractory)
    receptors  t, cid, a, b, n_rec, g_r, refractory, step, p_signal, X, Y, tx, ty (delivered receptor events;
               p_signal = lam_s halo / rate at the candidate, the probability that the event came from the target
               rather than the background lam_bg)
    traj       t (integers 0..T-1), X, Y (dot), tx, ty (target, blob 0): the accountant's samples (left limits)
    strokes    t, a, b, cid, nx, ny (exposed face at the stroke), dz, zt, zn, pulled (dz > 0 and face != 0),
               X, Y, tx, ty: every act-plane twitch with kappa > 0
    clicks     t, outcome (capture / miss / blob1), X, Y, tx, ty
    placements t, blob, cause (0 start, 1 click, 2 timer, 3 with target), x, y
    ledger     dict of the 57 ledger columns; F; status
    meta       seed, preset, org, seconds, kernel_F (when checked), n_blocked (lesion)
    """
    cells: pd.DataFrame
    knobs_birth: pd.DataFrame
    knobs_end: pd.DataFrame
    genes_birth: pd.DataFrame
    genes_end: pd.DataFrame
    pheno_changes: pd.DataFrame
    spikes: pd.DataFrame
    steps: pd.DataFrame
    arrivals: pd.DataFrame
    receptors: pd.DataFrame
    traj: pd.DataFrame
    strokes: pd.DataFrame
    clicks: pd.DataFrame
    placements: pd.DataFrame
    ledger: dict
    meta: dict = field(default_factory=dict)

    @property
    def F(self) -> float:
        return float(self.ledger["F"])

    def spike_times(self, cid: int) -> tuple[np.ndarray, np.ndarray]:
        """(times, channel masks) of cell ``cid``'s spikes."""
        s = self.spikes[self.spikes.cid == cid]
        return s.t.to_numpy(), s["mask"].to_numpy()

    def summary(self) -> str:
        c = self.cells
        alive = c[np.isinf(c.t_death)]
        led = self.ledger
        return (f"{self.meta.get('org')} seed {self.meta.get('seed')}: F {self.F:+.3f}, "
                f"captures {led['captures']:.0f}, misses {led['misses']:.0f}, cells end {len(alive)} "
                f"(S {sum(alive.z == 0)}, M {sum(alive.z == 1)}, "
                f"H {sum(alive.z >= 2)}), born {len(c)}, spikes {len(self.spikes)}, receptor events "
                f"{int(self.receptors.n_rec.sum()) if len(self.receptors) else 0}, strokes {len(self.strokes)}, "
                f"trace {self.meta.get('seconds', 0):.1f} s")


def _pos_cols(df: pd.DataFrame, pos: dict) -> pd.DataFrame:
    if len(df):
        p = np.array([pos.get(t, (np.nan,) * 4) for t in df.t.to_numpy()])
        df["X"], df["Y"], df["tx"], df["ty"] = p[:, 0], p[:, 1], p[:, 2], p[:, 3]
    else:
        for k in ("X", "Y", "tx", "ty"):
            df[k] = pd.Series(dtype=float)
    return df


def trace(org, seed: int, preset: str, *, check: bool = True, lesion: Lesion | None = None, **world) -> Trace:
    """One life of ``org`` (hb.GrnBody or hb.Body) with life seed ``seed`` in ``spec.world(preset, **world)``, fully
    logged by the observing reference simulator. ``check`` runs the same life in the kernel (no lesion) and raises if
    F differs (bitwise). ``lesion`` (``Lesion``) blocks messages after its t_fork."""
    w = _world(org, preset, **world)
    t_start = time.time()
    life = _life(org, seed, w, True, lesion)
    res = life.run()
    secs = time.time() - t_start
    A = life.acct
    # cells
    bl = life.L_birth
    n = len(bl)
    uid2cid = {r[0]: i for i, r in enumerate(bl)}
    t_death = np.full(n, np.inf)
    cause = np.zeros(n, dtype=np.int64)
    g_end = np.array([r[9] for r in bl], dtype=np.float64).reshape(n, spec.G_MAX)
    th_end = np.array([r[10] for r in bl], dtype=np.float64).reshape(n, V3.P)
    for uid, t, cs, g, th in life.L_death:
        i = uid2cid[uid]
        t_death[i], cause[i], g_end[i], th_end[i] = t, cs, g, th
    for s in life.sites.values():
        c = s.occ
        if c is not None and c.uid in uid2cid:
            i = uid2cid[c.uid]
            g_end[i], th_end[i] = c.g, c.th
    a = np.array([r[1] for r in bl], dtype=np.int64)
    b = np.array([r[2] for r in bl], dtype=np.int64)
    z = np.array([r[3] for r in bl], dtype=np.int64)
    xy = np.array([planar(ai, bi) for ai, bi in zip(a, b)]).reshape(n, 2)
    cells = pd.DataFrame(dict(
        cid=np.arange(n), uid=np.array([r[0] for r in bl], dtype=np.uint64), a=a, b=b, z=z, x=xy[:, 0], y=xy[:, 1],
        plane=[plane(v) for v in z], cls=[cell_class(*v) for v in zip(a, b, z)],
        t_birth=np.array([r[4] for r in bl]), t_death=t_death, death_cause=cause,
        mother=np.array([r[5] for r in bl], dtype=np.uint64),
        mother_cid=np.array([uid2cid.get(r[5], -1) for r in bl], dtype=np.int64),
        initial=np.array([r[6] >= 0 for r in bl]), k=np.array([r[7] for r in bl], dtype=np.int64),
        row=np.array([r[8] for r in bl], dtype=np.int64)))
    kb = pd.DataFrame(np.array([r[10] for r in bl]).reshape(n, V3.P), columns=list(KNOBS))
    ke = pd.DataFrame(th_end, columns=list(KNOBS))
    gcols = [f"g{k}" for k in range(spec.G_MAX)]
    gb = pd.DataFrame(np.array([r[9] for r in bl]).reshape(n, spec.G_MAX), columns=gcols)
    ge = pd.DataFrame(g_end, columns=gcols)
    ph = pd.DataFrame(life.L_pheno, columns=["t", "cid", "p", "old", "new"])
    ph["knob"] = [KNOBS[p] for p in ph.p]
    ph = ph[["t", "cid", "knob", "old", "new"]]
    # spikes
    sp = pd.DataFrame(life.L_spk, columns=["t", "cid", "a", "b", "z", "mask", "kappa", "cause", "step"])
    sp.insert(0, "sid", np.arange(len(sp)))
    sp["cls"] = [cell_class(*v) for v in zip(sp.a, sp.b, sp.z)]
    sp["cause"] = sp.cause.map(CAUSES)
    sp = _pos_cols(sp, A.t_pos)
    cells["n_spikes"] = np.bincount(sp.cid.to_numpy(), minlength=n)[:n] if len(sp) else 0
    st = pd.DataFrame(life.L_step, columns=["t", "cid", "a", "b", "z", "v0", "rin", "refractory", "fired", "thr",
                                            "n_arr"])
    st.insert(0, "step", np.arange(len(st)))
    ar = pd.DataFrame(life.L_arr, columns=["step", "slot", "mask", "contrib", "s_sid", "view_uid"])
    if len(ar):
        stp = st.set_index("step")
        ar["t"] = stp.t.to_numpy()[ar.step.to_numpy()]
        ar["cid"] = stp.cid.to_numpy()[ar.step.to_numpy()]
        ra, rb, rz = (stp[k].to_numpy()[ar.step.to_numpy()] for k in ("a", "b", "z"))
        off = np.array(OFF)
        sl = ar.slot.to_numpy()
        ar["sa"], ar["sb"], ar["sz"] = ra + off[sl, 0], rb + off[sl, 1], rz + off[sl, 2]
        ar["dir"] = np.where(off[sl, 2] == 0, "lat", np.where(off[sl, 2] > 0, "up", "down"))
        ssid = ar.s_sid.to_numpy()
        spc = sp.cid.to_numpy()
        vc = np.array([uid2cid.get(int(u), -1) for u in ar.view_uid], dtype=np.int64)
        ar["s_cid"] = np.where(ssid >= 0, spc[np.clip(ssid, 0, max(len(spc) - 1, 0))] if len(spc) else -1, vc)
    else:
        for k in ("t", "cid", "sa", "sb", "sz", "dir", "s_cid"):
            ar[k] = pd.Series(dtype=float)
    ar = ar[["step", "t", "cid", "slot", "dir", "sa", "sb", "sz", "s_cid", "s_sid", "mask", "contrib"]]
    rc = pd.DataFrame(life.L_rec, columns=["t", "cid", "n_rec", "g_r", "refractory", "step", "p_signal"])
    if len(rc):
        rc["a"] = cells.a.to_numpy()[rc.cid.to_numpy()]
        rc["b"] = cells.b.to_numpy()[rc.cid.to_numpy()]
    else:
        rc["a"], rc["b"] = pd.Series(dtype=int), pd.Series(dtype=int)
    rc = _pos_cols(rc, A.t_pos)
    cells["n_rec"] = np.bincount(rc.cid.to_numpy(), weights=rc.n_rec.to_numpy(), minlength=n)[:n] if len(rc) else 0
    # world
    pl = pd.DataFrame(A.t_place, columns=["t", "blob", "cause", "x", "y"])
    p0 = pl[(pl.blob == 0)].iloc[0]
    samp = [(w.t0, 0.0, 0.0, float(p0.x), float(p0.y))] + A.t_samp
    tj = pd.DataFrame(samp, columns=["t", "X", "Y", "tx", "ty"])
    sk = pd.DataFrame(A.t_stroke, columns=["t", "a", "b", "nx", "ny", "dz", "zt", "zn", "X", "Y", "tx", "ty"])
    if len(sk):
        key = {(t, a_, b_): c_ for t, c_, a_, b_, z_ in zip(sp.t, sp.cid, sp.a, sp.b, sp.z) if z_ == 1}
        sk.insert(3, "cid", [key.get((t, a_, b_), -1) for t, a_, b_ in zip(sk.t, sk.a, sk.b)])
    else:
        sk.insert(3, "cid", pd.Series(dtype=int))
    sk["pulled"] = (sk.dz > 0) & ((sk.nx != 0) | (sk.ny != 0))
    ck = pd.DataFrame(A.t_click, columns=["t", "outcome", "X", "Y"])
    if len(ck):
        tg = [life_blob_at(A, pl, t) for t in ck.t]
        ck["tx"], ck["ty"] = [p[0] for p in tg], [p[1] for p in tg]
    ck["outcome"] = ck.outcome.map(OUTCOMES)
    led = {name: float(res.ledger[i]) for i, name in enumerate(V3.LEDGER)}
    meta = dict(seed=int(seed), preset=preset, org=getattr(org, "name", "?"), seconds=secs,
                n_blocked=life.n_blocked, world=w)
    if check and lesion is None:
        kl = org.run([int(seed)], threads=1, preset=preset, **world)
        kF = float(kl["F"][0])
        meta["kernel_F"] = kF
        if kF != led["F"]:
            raise AssertionError(f"trace F {led['F']!r} != kernel F {kF!r}: the observer changed the life")
    return Trace(cells, kb, ke, gb, ge, ph, sp, st, ar, rc, tj, sk, ck, pl, led, meta)


def life_blob_at(acct, placements: pd.DataFrame, t: float):
    """Target position at a click time (the left limit: the click reads the blob before its re-placement). Uses the
    sample/record position log when the click's time group logged one, else NaN."""
    p = acct.t_pos.get(t)
    return (p[2], p[3]) if p is not None else (np.nan, np.nan)


def trace_many(org, seeds, preset: str, **kw) -> list[Trace]:
    return [trace(org, s, preset, **kw) for s in seeds]


# ------------------------------------------------------------------------------------- fast partial traces
@dataclass
class KTrace:
    """A kernel life: cells (as in Trace, from the fate log), spikes (sid, t, cid, a, b, z, cls; mask = the emit
    bits of the phenotype at birth, which GRN cells may change later), knobs_birth, ledger. No receptor events,
    membrane steps or world trajectory."""
    cells: pd.DataFrame
    knobs_birth: pd.DataFrame
    spikes: pd.DataFrame
    ledger: dict
    meta: dict = field(default_factory=dict)

    @property
    def F(self) -> float:
        return float(self.ledger["F"])


def trace_kernel(org, seeds, preset: str, *, threads: int = 2, raster_cap: int = 400_000, fate_cap: int = 40_000,
                 **world) -> list[KTrace]:
    """Kernel lives with raster and fate log, as ``KTrace`` objects (one per seed)."""
    t_start = time.time()
    lv = org.run(list(seeds), threads=threads, preset=preset, raster_cap=raster_cap, fate_cap=fate_cap, **world)
    secs = (time.time() - t_start) / max(len(seeds), 1)
    w = _world(org, preset, **world)
    gt = None if is_program(org) else V3.pack_genomes(np.asarray(org.genome)[None], w.lattice)[0]
    out = []
    for i, s in enumerate(seeds):
        if lv.raster_n[i] > raster_cap or lv.fate_n[i] > fate_cap:
            raise ValueError(f"life {i}: raster or fate log overflow; raise the caps")
        fi, ff = lv.fates(i)
        rows, uid2cid, td = [], {}, {}
        for r, fr in zip(fi.tolist(), ff.tolist()):
            if r[0] == 1:
                uid2cid[r[1]] = len(rows)
                rows.append((r[1], r[3], r[4], r[6], fr[0], r[2], r[5], fr[2:]))
            elif r[0] == 2:
                td[uid2cid[r[1]]] = (fr[0], r[5])
        n = len(rows)
        a = np.array([r[1] for r in rows], dtype=np.int64)
        b = np.array([r[2] for r in rows], dtype=np.int64)
        z = np.array([r[3] for r in rows], dtype=np.int64)
        xy = np.array([planar(ai, bi) for ai, bi in zip(a, b)]).reshape(n, 2)
        cells = pd.DataFrame(dict(
            cid=np.arange(n), uid=np.array([r[0] for r in rows], dtype=np.int64).view(np.uint64), a=a, b=b, z=z,
            x=xy[:, 0], y=xy[:, 1], plane=[plane(v) for v in z], cls=[cell_class(*v) for v in zip(a, b, z)],
            t_birth=np.array([r[4] for r in rows]), t_death=np.array([td.get(j, (np.inf, 0))[0] for j in range(n)]),
            death_cause=np.array([td.get(j, (0, 0))[1] for j in range(n)]),
            mother_cid=np.array([uid2cid.get(r[5], -1) for r in rows], dtype=np.int64)))
        if is_program(org):
            prog = np.asarray(org.program, np.float64)
            rowof = {(c[0], c[1], c[2]): c[3] for c in org.cells}
            th = np.array([prog[rowof[(ai, bi, zi)] * V3.P:(rowof[(ai, bi, zi)] + 1) * V3.P]
                           for ai, bi, zi in zip(a, b, z)]).reshape(n, V3.P)
        else:
            th = np.array([V3.phenotype(gt, r[7]) for r in rows]).reshape(n, V3.P)
        kb = pd.DataFrame(th, columns=list(KNOBS))
        rt, ru = lv.spikes(i)
        ru64 = ru.astype(np.uint64).view(np.int64)
        cidx = np.array([uid2cid[int(u)] for u in ru64], dtype=np.int64)
        sp = pd.DataFrame(dict(sid=np.arange(len(rt)), t=rt, cid=cidx, a=a[cidx], b=b[cidx], z=z[cidx]))
        sp["cls"] = cells.cls.to_numpy()[cidx]
        sp["mask"] = ((th[cidx, _KE0] != 0).astype(int) | 2 * (th[cidx, _KE1] != 0).astype(int))
        cells["n_spikes"] = np.bincount(cidx, minlength=n)
        led = {name: float(lv.ledger[i, j]) for j, name in enumerate(V3.LEDGER)}
        out.append(KTrace(cells, kb, sp, led, dict(seed=int(s), preset=preset, org=getattr(org, "name", "?"),
                                                   seconds=secs)))
    return out


# ============================================================================================ 3. tuning
BEARING_BINS = 8
DIST_EDGES = (0.0, 1.0, 2.0, 3.0, 4.0, 6.0, np.inf)  # target distance from the dot
CELL_DIST_EDGES = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, np.inf)  # target distance from the cell's own screen point


def _bearing_bin(dx, dy, nb=BEARING_BINS):
    ang = np.arctan2(dy, dx)
    return np.floor((ang / (2 * np.pi) * nb + 0.5)).astype(np.int64) % nb


def _wrap(a):
    return (np.asarray(a) + np.pi) % (2 * np.pi) - np.pi


def tuning(tr: Trace, *, min_spikes: int = 10, dist_edges=DIST_EDGES, cell_edges=CELL_DIST_EDGES,
           near: float | None = None) -> pd.DataFrame:
    """Per-cell tuning from a trace. Occupancy is the integer samples (1 unit each) while the cell is alive; spikes are
    binned by the exact dot and target positions at their record time.

    Columns per cell: cid, cls, a, b, z, n_spikes, rate (spikes per unit), rate_b0..7 (rate vs the target's bearing
    from the dot, bin k centred on k * 45 degrees, counter-clockwise from +x), rate_d0.. (vs target distance from the
    dot, ``dist_edges``), rate_c0.. (vs distance from the cell's own screen point, ``cell_edges``), vs (vector
    strength of the bearing tuning, 0 untuned .. 1 one direction), pref (preferred bearing, degrees), own (the cell's
    own direction from the body centre, degrees; NaN at the centre), pref_minus_own (degrees). ``near`` restricts the
    bearing tuning to samples / spikes with the target within that distance of the dot.
    Act cells add from their strokes: n_pull, face (mean exposed-face direction, degrees), align (force-weighted mean
    cos(face, target bearing) over pulling strokes: +1 = always pulls toward the target, 0 = chance), toward (fraction
    of pulls with cos > 0), pull_rate_b0..7 (pulling strokes per unit vs target bearing)."""
    c = tr.cells
    tj = tr.traj
    st = tj.t.to_numpy()
    dx, dy = tj.tx.to_numpy() - tj.X.to_numpy(), tj.ty.to_numpy() - tj.Y.to_numpy()
    sb = _bearing_bin(dx, dy)
    sdist = np.hypot(dx, dy)
    sd = np.digitize(sdist, dist_edges[1:-1])
    ok_b = np.ones(len(st), bool) if near is None else sdist <= near
    nd, nc = len(dist_edges) - 1, len(cell_edges) - 1
    sp = tr.spikes
    rows = []
    th_b = 2 * np.pi * np.arange(BEARING_BINS) / BEARING_BINS
    for r in c.itertuples():
        alive = (st >= r.t_birth) & (st < r.t_death)
        occ_t = float(alive.sum())
        s = sp[sp.cid == r.cid]
        if occ_t <= 0:
            continue
        ex, ey = s.tx.to_numpy() - s.X.to_numpy(), s.ty.to_numpy() - s.Y.to_numpy()
        kdist = np.hypot(ex, ey)
        kb = _bearing_bin(ex, ey)
        ok_k = np.ones(len(s), bool) if near is None else kdist <= near
        occ_b = np.bincount(sb[alive & ok_b], minlength=BEARING_BINS).astype(float)
        cnt_b = np.bincount(kb[ok_k], minlength=BEARING_BINS).astype(float)
        rb = np.divide(cnt_b, occ_b, out=np.full(BEARING_BINS, np.nan), where=occ_b > 0)
        occ_d = np.bincount(sd[alive], minlength=nd).astype(float)
        cnt_d = np.bincount(np.digitize(kdist, dist_edges[1:-1]), minlength=nd).astype(float)
        rd = np.divide(cnt_d, occ_d, out=np.full(nd, np.nan), where=occ_d > 0)
        # distance from the cell's own point (x, y) on the screen
        cdist_s = np.hypot(dx - r.x, dy - r.y)
        cdist_k = np.hypot(ex - r.x, ey - r.y)
        occ_c = np.bincount(np.digitize(cdist_s[alive], cell_edges[1:-1]), minlength=nc).astype(float)
        cnt_c = np.bincount(np.digitize(cdist_k, cell_edges[1:-1]), minlength=nc).astype(float)
        rcl = np.divide(cnt_c, occ_c, out=np.full(nc, np.nan), where=occ_c > 0)
        rr = np.nan_to_num(rb)
        vsum = rr.sum()
        vec = (rr * np.exp(1j * th_b)).sum()
        vs = float(abs(vec) / vsum) if vsum > 0 else np.nan
        pref = float(np.degrees(np.angle(vec))) if vsum > 0 else np.nan
        own = float(np.degrees(math.atan2(r.y, r.x))) if (r.a, r.b) != (0, 0) else np.nan
        row = dict(cid=r.cid, cls=r.cls, a=r.a, b=r.b, z=r.z, n_spikes=len(s), rate=len(s) / occ_t, vs=vs, pref=pref,
                   own=own, pref_minus_own=float(np.degrees(_wrap(np.radians(pref - own)))) if own == own and
                   pref == pref else np.nan)
        row.update({f"rate_b{k}": rb[k] for k in range(BEARING_BINS)})
        row.update({f"rate_d{k}": rd[k] for k in range(nd)})
        row.update({f"rate_c{k}": rcl[k] for k in range(nc)})
        if r.z == 1 and len(tr.strokes):
            k_ = tr.strokes[(tr.strokes.cid == r.cid) & tr.strokes.pulled]
            row["n_pull"] = len(k_)
            if len(k_):
                fx, fy = k_.nx.to_numpy(), k_.ny.to_numpy()
                ux, uy = k_.tx.to_numpy() - k_.X.to_numpy(), k_.ty.to_numpy() - k_.Y.to_numpy()
                nn, uu = np.hypot(fx, fy), np.hypot(ux, uy)
                cs = (fx * ux + fy * uy) / np.maximum(nn * uu, 1e-12)
                wgt = k_.dz.to_numpy() * nn
                row["face"] = float(np.degrees(math.atan2(fy.mean(), fx.mean())))
                row["align"] = float((wgt * cs).sum() / wgt.sum())
                row["toward"] = float((cs > 0).mean())
                pb = np.bincount(_bearing_bin(ux, uy), minlength=BEARING_BINS).astype(float)
                pr = np.divide(pb, occ_b, out=np.full(BEARING_BINS, np.nan), where=occ_b > 0)
                row.update({f"pull_rate_b{k}": pr[k] for k in range(BEARING_BINS)})
        rows.append(row)
    out = pd.DataFrame(rows)
    out["tuned"] = out.n_spikes >= min_spikes
    return out


def steering(tr: Trace) -> dict:
    """Body-level steering from the strokes: n strokes, pulls, force-weighted mean cos(face, target bearing) over all
    pulls (``align``), fraction toward, and the same split by target distance (near: target within 2 of the dot)."""
    k = tr.strokes[tr.strokes.pulled] if len(tr.strokes) else tr.strokes
    if not len(k):
        return dict(strokes=len(tr.strokes), pulls=0)
    fx, fy = k.nx.to_numpy(), k.ny.to_numpy()
    ux, uy = k.tx.to_numpy() - k.X.to_numpy(), k.ty.to_numpy() - k.Y.to_numpy()
    nn, uu = np.hypot(fx, fy), np.hypot(ux, uy)
    cs = (fx * ux + fy * uy) / np.maximum(nn * uu, 1e-12)
    wgt = k.dz.to_numpy() * nn
    near = uu <= 2.0
    out = dict(strokes=len(tr.strokes), pulls=len(k), align=float((wgt * cs).sum() / wgt.sum()),
               toward=float((cs > 0).mean()))
    for tag, m in (("near", near), ("far", ~near)):
        if m.any():
            out[f"align_{tag}"] = float((wgt[m] * cs[m]).sum() / wgt[m].sum())
            out[f"pulls_{tag}"] = int(m.sum())
    return out


def tuning_table(tun: pd.DataFrame, cls=None, min_spikes: int = 10) -> str:
    """Compact text: per class, cells, mean rate, mean vector strength, |pref - own| (median, degrees), and for act
    cells align / toward."""
    lines = []
    for k, g in tun.groupby("cls"):
        if cls is not None and k not in cls:
            continue
        gt = g[g.n_spikes >= min_spikes]
        s = (f"{k}: cells {len(g)} (tuned {len(gt)}), rate {g.rate.mean():.3f}/u, vs {gt.vs.mean():.2f}, "
             f"|pref-own| med {np.nanmedian(np.abs(gt.pref_minus_own)) if len(gt) else np.nan:.0f} deg")
        if "align" in g and g["align"].notna().any():
            s += f", align {g['align'].mean():+.2f}, toward {g['toward'].mean():.2f}"
        lines.append(s)
    return "\n".join(lines)


# ============================================================================================== 4. flow
def _site_index(cells: pd.DataFrame) -> dict:
    out: dict = {}
    for r in cells.itertuples():
        out.setdefault((r.a, r.b, r.z), []).append(r.cid)
    return out


def _spike_lists(tr) -> dict:
    s = tr.spikes
    out = {}
    for cid, t in zip(s.cid.to_numpy(), s.t.to_numpy()):
        out.setdefault(int(cid), []).append(t)
    return {k: np.sort(np.array(v)) for k, v in out.items()}


def neighbour_pairs(cells: pd.DataFrame):
    """Ordered neighbour pairs (i, j, direction) with overlapping lifetimes; direction is where j sits relative to
    i: lat, up (j above i) or down."""
    idx = _site_index(cells)
    tb, td = cells.t_birth.to_numpy(), cells.t_death.to_numpy()
    out = []
    for r in cells.itertuples():
        for da, db, dz in OFF:
            for j in idx.get((r.a + da, r.b + db, r.z + dz), ()):
                if min(td[r.cid], td[j]) > max(tb[r.cid], tb[j]):
                    out.append((r.cid, j, "lat" if dz == 0 else ("up" if dz > 0 else "down")))
    return out


def ccg(trs, *, max_lag: float = 5.0, bin: float = 0.25, label=None, follow=(0.5, 3.0)) -> pd.DataFrame:
    """Spike cross-correlograms between neighbour pairs, aggregated by (sender class, direction, receiver class).

    ``trs`` is a Trace / KTrace or a list of them (counts add up). For each ordered pair (i -> j) of neighbours alive
    together, lags t_j - t_i in (0, max_lag] of j's spikes after each i spike, in bins of ``bin``; ``expected`` is the
    count for independent stationary trains (n_i n_j / T_overlap per unit lag). ``label(cells_row)`` gives the class
    (default ``cell_class``: C, S, K, M, H). Columns: pre, dir (lat / up = receiver above sender / down), post, pairs,
    n_pre (sender spikes), counts, expected (arrays), ratio (counts / expected per bin), peak_lag (centre of the bin
    with the largest excess), peak_ratio, sharp (peak_ratio / the median ratio at lags >= 2: a transmission peak
    stands out of the broad shared-input correlation; ~1 = no direct transmission), p_follow (fraction of sender
    spikes followed by a receiver spike within ``follow``), p_chance (the same expected by chance),
    lift = p_follow / p_chance."""
    if not isinstance(trs, (list, tuple)):
        trs = [trs]
    edges = np.arange(0.0, max_lag + 1e-12, bin)
    nb = len(edges) - 1
    agg: dict = {}
    for tr in trs:
        cells = tr.cells
        lab = (cells.cls.to_numpy() if label is None else np.array([label(r) for r in cells.itertuples()]))
        spk = _spike_lists(tr)
        tb, td = cells.t_birth.to_numpy(), cells.t_death.to_numpy()
        T_end = float(tr.ledger["t_end"])
        for i, j, d in neighbour_pairs(cells):
            lo, hi = max(tb[i], tb[j]), min(td[i], td[j], T_end)
            if hi <= lo:
                continue
            ti = spk.get(i, np.empty(0))
            tj = spk.get(j, np.empty(0))
            ti = ti[(ti >= lo) & (ti < hi)]
            tj = tj[(tj >= lo) & (tj < hi)]
            key = (lab[i], d, lab[j])
            a = agg.setdefault(key, dict(pairs=0, n_pre=0, counts=np.zeros(nb), expected=np.zeros(nb), fol=0.0,
                                         fol_exp=0.0))
            a["pairs"] += 1
            a["n_pre"] += len(ti)
            if len(ti) == 0:
                continue
            rate_j = len(tj) / (hi - lo)
            a["expected"] += len(ti) * rate_j * np.diff(edges)
            if len(tj):
                cnt = np.searchsorted(tj, ti[:, None] + edges[None, :], side="right")
                a["counts"] += np.diff(cnt, axis=1).sum(axis=0)
                f0 = np.searchsorted(tj, ti + follow[0], side="right")
                f1 = np.searchsorted(tj, ti + follow[1], side="right")
                a["fol"] += float(((f1 - f0) > 0).sum())
                a["fol_exp"] += len(ti) * (1.0 - math.exp(-rate_j * (follow[1] - follow[0])))
    rows = []
    centres = 0.5 * (edges[:-1] + edges[1:])
    for (pre, d, post), a in sorted(agg.items()):
        ratio = np.divide(a["counts"], a["expected"], out=np.full(nb, np.nan), where=a["expected"] > 0)
        exc = a["counts"] - a["expected"]
        k = int(np.argmax(exc)) if a["n_pre"] else 0
        pf = a["fol"] / a["n_pre"] if a["n_pre"] else np.nan
        pc = a["fol_exp"] / a["n_pre"] if a["n_pre"] else np.nan
        far = ratio[centres >= 2.0]
        base = float(np.nanmedian(far)) if np.isfinite(far).any() else np.nan
        rows.append(dict(pre=pre, dir=d, post=post, pairs=a["pairs"], n_pre=a["n_pre"], counts=a["counts"],
                         expected=a["expected"], ratio=ratio, peak_lag=float(centres[k]), peak_ratio=float(ratio[k]),
                         sharp=float(ratio[k] / base) if base and base > 0 else np.nan,
                         p_follow=pf, p_chance=pc, lift=pf / pc if pc and pc > 0 else np.nan))
    return pd.DataFrame(rows)


def ccg_table(df: pd.DataFrame, min_pre: int = 20) -> str:
    """Compact text of ``ccg``: one line per class with enough sender spikes."""
    out = []
    for r in df.itertuples():
        if r.n_pre < min_pre:
            continue
        rs = " ".join(f"{x:4.1f}" if x == x else "  . " for x in r.ratio[:12])
        out.append(f"{r.pre:>2} -{r.dir:>4}-> {r.post:<2} pairs {r.pairs:4d} pre {r.n_pre:6d}  peak {r.peak_lag:4.2f} "
                   f"x{r.peak_ratio:5.1f} sharp {r.sharp:5.1f}  P(follow) {r.p_follow:.3f} vs {r.p_chance:.3f} "
                   f"(lift {r.lift:5.2f})  "
                   f"ratio[0..3]: {rs}")
    return "\n".join(out)


def act_drivers(trs, *, window=(0.5, 3.0), radius: int = 2, shuffle_seed: int = 0) -> pd.DataFrame:
    """For every act-cell spike (z = 1) at t: which neighbours spiked in [t - window[1], t - window[0]].

    Per act spike: own_sense (the sense cell of the same column, (a, b, 0)), other_sense_r1 / _r2 (a sense cell of a
    column at hex distance 1 / up to ``radius`` from it; not a contact of the act cell), act_nb (an in-plane act
    neighbour), hidden (the cell above), none (no neighbour at all), own_first (own sense spiked and was the latest of
    the column-and-ring-1 sense spikes), and lat_own (latency t - the latest own-sense spike in the window).
    Returns one row per act class (K, M, all) with the fractions, the same fractions at shuffled times (each act
    spike moved to a uniform time in its cell's life: chance level), and the latency quartiles."""
    if not isinstance(trs, (list, tuple)):
        trs = [trs]
    recs = []
    rng = np.random.default_rng(shuffle_seed)
    for tr in trs:
        cells = tr.cells
        idx = _site_index(cells)
        spk = _spike_lists(tr)
        bysite = {}
        for site, cids in idx.items():
            ts = np.sort(np.concatenate([spk.get(c_, np.empty(0)) for c_ in cids])) if cids else np.empty(0)
            bysite[site] = ts
        T_end = float(tr.ledger["t_end"])
        act = tr.spikes[tr.spikes.z == 1]
        tb = cells.t_birth.to_numpy()
        td = np.minimum(cells.t_death.to_numpy(), T_end)

        def hit(site, lo, hi, bysite=bysite):
            ts = bysite.get(site)
            if ts is None or not len(ts):
                return None
            k = np.searchsorted(ts, hi, side="right") - 1
            return ts[k] if k >= 0 and ts[k] >= lo else None

        for shuffled in (False, True):
            for r in act.itertuples():
                t = r.t if not shuffled else rng.uniform(tb[r.cid], td[r.cid])
                lo, hi = t - window[1], t - window[0]
                own = hit((r.a, r.b, 0), lo, hi)
                ring = {}
                for da in range(-radius, radius + 1):
                    for db in range(-radius, radius + 1):
                        h = hexdist(da, db)
                        if 0 < h <= radius:
                            x = hit((r.a + da, r.b + db, 0), lo, hi)
                            if x is not None:
                                ring[h] = max(ring.get(h, -np.inf), x)
                actn = any(hit((r.a + da, r.b + db, 1), lo, hi) is not None for da, db, dz in OFF[:6])
                hid = hit((r.a, r.b, 2), lo, hi) is not None
                recs.append(dict(shuffled=shuffled, cls=r.cls, own_sense=own is not None,
                                 other_sense_r1=1 in ring, other_sense_rN=bool(ring), act_nb=actn, hidden=hid,
                                 none=(own is None and not actn and not hid),
                                 own_first=own is not None and own >= ring.get(1, -np.inf),
                                 lat_own=(t - own) if own is not None else np.nan))
    df = pd.DataFrame(recs)
    rows = []
    if not len(df):
        return pd.DataFrame()
    for cls in ("K", "M", "all"):
        g = df if cls == "all" else df[df.cls == cls]
        if not len(g):
            continue
        real, sh = g[~g.shuffled], g[g.shuffled]
        row = dict(cls=cls, act_spikes=len(real))
        for k in ("own_sense", "other_sense_r1", "other_sense_rN", "act_nb", "hidden", "none", "own_first"):
            row[k] = float(real[k].mean())
            row[k + "_chance"] = float(sh[k].mean())
        q = real.lat_own.dropna()
        row["lat_own_q"] = tuple(np.round(np.quantile(q, [0.25, 0.5, 0.75]), 3)) if len(q) else ()
        rows.append(row)
    return pd.DataFrame(rows)


def relabel(tr, t_ref: float | None = None, interior: int = 6):
    """Role labels from the occupancy at ``t_ref`` (default: the middle of the life), in handbuilt's vocabulary:
    sense cells C (centre), J (interior: ``interior`` or more of its 6 in-plane neighbour sites alive at t_ref) or S
    (rim); act cells K (hotspot), I (interior) or M (rim, exposed); hidden H. Cells not alive at t_ref are labelled
    by the same rule applied at their own mid-life. Updates ``tr.cells.cls`` and ``tr.spikes.cls`` in place and
    returns ``tr``."""
    c = tr.cells
    T_end = float(tr.ledger["t_end"])
    t_ref = T_end / 2 if t_ref is None else t_ref
    tb, td = c.t_birth.to_numpy(), np.minimum(c.t_death.to_numpy(), T_end)
    idx = _site_index(c)
    lab = []
    for r in c.itertuples():
        t = t_ref if tb[r.cid] <= t_ref < td[r.cid] else 0.5 * (tb[r.cid] + td[r.cid])
        n_nb = 0
        for da, db, _ in OFF[:6]:
            if any(tb[j] <= t < td[j] for j in idx.get((r.a + da, r.b + db, r.z), ())):
                n_nb += 1
        if r.z == 0:
            lab.append("C" if (r.a, r.b) == (0, 0) else ("J" if n_nb >= interior else "S"))
        elif r.z == 1:
            lab.append("K" if (r.a, r.b) == (0, 0) else ("I" if n_nb >= interior else "M"))
        else:
            lab.append("H")
    c["cls"] = lab
    tr.spikes["cls"] = np.array(lab, dtype=object)[tr.spikes.cid.to_numpy()]
    return tr


# --------------------------------------------------------------------------------- exact causal chains (Trace)
def _primary(tr: Trace):
    """For each spike: (kind, parent sid, contribution). kind: 'rec' (own receptor input was the largest input of
    the firing step), 'arr' (an arrival was; parent = its sender spike, -1 if unknown), 'tonic' (threshold crossing
    or tick re-anchor with no input), 'resid' (fired on an input step whose inputs were all <= 0: the residual
    membrane carried it)."""
    sp = tr.spikes
    st = tr.steps
    ar = tr.arrivals
    rin = st.rin.to_numpy()
    best_c = np.full(len(st), -np.inf)
    best_p = np.full(len(st), -1, dtype=np.int64)
    best_dir = np.array([""] * len(st), dtype=object)
    if len(ar):
        o = np.argsort(-ar.contrib.to_numpy(), kind="stable")
        a_step, a_c, a_sid, a_dir = (ar[k].to_numpy()[o] for k in ("step", "contrib", "s_sid", "dir"))
        first = np.unique(a_step, return_index=True)[1]
        best_c[a_step[first]] = a_c[first]
        best_p[a_step[first]] = a_sid[first]
        best_dir[a_step[first]] = a_dir[first]
    kinds, parents, contrib, dirs = [], [], [], []
    for cause, step in zip(sp.cause.to_numpy(), sp.step.to_numpy()):
        if step < 0 or cause in ("threshold", "tick", "input+threshold"):
            kinds.append("tonic"), parents.append(-1), contrib.append(0.0), dirs.append("")
            continue
        r, c_ = rin[step], best_c[step]
        if r > 0 and r >= c_:
            kinds.append("rec"), parents.append(-1), contrib.append(r), dirs.append("")
        elif c_ > 0:
            kinds.append("arr"), parents.append(int(best_p[step])), contrib.append(c_), dirs.append(best_dir[step])
        else:
            kinds.append("resid"), parents.append(-1), contrib.append(0.0), dirs.append("")
    return np.array(kinds), np.array(parents, dtype=np.int64), np.array(contrib), np.array(dirs)


def drive_matrix(tr: Trace) -> pd.DataFrame:
    """Who fires whom: for every spike, the class of its largest input in the firing step (receptor, or the sender
    class and direction of the largest arrival; 'tonic' / 'resid' otherwise), counted per receiving class. Columns:
    post, driver, n, share (of the post class's spikes)."""
    kinds, par, _, dirs = _primary(tr)
    sp = tr.spikes
    cls = sp.cls.to_numpy()
    drv = []
    for k, p, d in zip(kinds, par, dirs):
        if k == "arr":
            drv.append(f"{cls[p]}({d})" if p >= 0 else f"?({d})")
        else:
            drv.append(k)
    df = pd.DataFrame(dict(post=cls, driver=drv))
    out = df.groupby(["post", "driver"]).size().rename("n").reset_index()
    out["share"] = out.n / out.groupby("post").n.transform("sum")
    return out.sort_values(["post", "n"], ascending=[True, False]).reset_index(drop=True)


def chains(tr: Trace, *, max_depth: int = 12) -> pd.DataFrame:
    """Exact causal chains of the act-plane spikes. Each spike is followed back through the largest input of its
    firing step (``_primary``) until a receptor event, a tonic spike, a residual-driven spike or an unknown sender.
    One row per act spike: sid, t, cid, cls, a, b, origin (rec / tonic / resid / unknown / deep), origin_cls,
    oa, ob, oz (origin cell's site), origin_dist (hex distance between the origin column and the act column), hops
    (spikes after the origin), lat_hops (links of the chain that are in-plane arrivals), p_signal (for a receptor
    origin: the probability that its receptor event came from the target, not background noise), latency (act spike
    time minus the origin spike time; for rec the receptor-driven spike), path (classes and directions, origin
    first), via_own_sense (the act spike's direct driver is its own column's sense cell)."""
    sp = tr.spikes
    kinds, par, _, dirs = _primary(tr)
    psig = dict(zip(tr.receptors.step.to_numpy(), tr.receptors.p_signal.to_numpy())) if len(tr.receptors) else {}
    steps = sp.step.to_numpy()
    T = sp.t.to_numpy()
    A_, B_, Z_ = sp.a.to_numpy(), sp.b.to_numpy(), sp.z.to_numpy()
    cls = sp.cls.to_numpy()
    rows = []
    for s in np.nonzero(Z_ == 1)[0]:
        path = [s]
        cur = s
        origin = None
        while True:
            k = kinds[cur]
            if k == "arr":
                p = par[cur]
                if p < 0:
                    origin = "unknown"
                    break
                if len(path) > max_depth:
                    origin = "deep"
                    break
                path.append(p)
                cur = p
                continue
            origin = k
            break
        o = path[-1]
        desc = []
        for q in reversed(path):
            desc.append(cls[q] + (f"<{dirs[q]}" if kinds[q] == "arr" else f"[{kinds[q]}]"))
        d1 = path[1] if len(path) > 1 else None
        rows.append(dict(sid=int(s), t=T[s], cid=int(sp.cid.iat[s]), cls=cls[s], a=int(A_[s]), b=int(B_[s]),
                         origin=origin, origin_cls=cls[o], oa=int(A_[o]), ob=int(B_[o]), oz=int(Z_[o]),
                         origin_dist=hexdist(int(A_[o] - A_[s]), int(B_[o] - B_[s])), hops=len(path) - 1,
                         lat_hops=sum(1 for q in path[:-1] if dirs[q] == "lat"),
                         p_signal=psig.get(steps[o], np.nan) if origin == "rec" else np.nan,
                         latency=T[s] - T[o], path=" ".join(desc),
                         via_own_sense=d1 is not None and Z_[d1] == 0 and A_[d1] == A_[s] and B_[d1] == B_[s]))
    return pd.DataFrame(rows)


def chain_summary(ch: pd.DataFrame, pulled_only: bool = False, tr: Trace | None = None) -> pd.DataFrame:
    """Per act class: spikes, share by origin (rec / tonic / resid / unknown / deep), and for receptor-origin chains:
    rec_own_col / rec_other_col (origin in the act cell's own column vs another column), relayed (at least one
    in-plane hop), rec_signal (mean probability that the origin event was the target's, not background),
    lat_by_hops (median latency from the origin spike per hop count), hops_share; via_own_sense (the direct driver
    is the own column's sense cell) and the most common paths. ``pulled_only`` (needs ``tr``) keeps the spikes whose
    stroke pulled the dot."""
    if pulled_only and tr is not None and len(tr.strokes):
        k = tr.strokes[tr.strokes.pulled]
        keys = set(zip(k.t, k.a, k.b))
        ch = ch[[(t, a, b) in keys for t, a, b in zip(ch.t, ch.a, ch.b)]]
    rows = []
    for cls in ("K", "M", "all"):
        g = ch if cls == "all" else ch[ch.cls == cls]
        if not len(g):
            continue
        rec = g[g.origin == "rec"]
        row = dict(cls=cls, spikes=len(g))
        for o in ("rec", "tonic", "resid", "unknown", "deep"):
            row[o] = float((g.origin == o).mean())
        row["rec_own_col"] = float((rec.origin_dist == 0).mean()) if len(rec) else np.nan
        row["rec_other_col"] = float((rec.origin_dist >= 1).mean()) if len(rec) else np.nan
        row["relayed"] = float((rec.lat_hops >= 1).mean()) if len(rec) else np.nan
        row["rec_signal"] = float(rec.p_signal.mean()) if len(rec) else np.nan
        row["lat_by_hops"] = {int(h): round(float(x.latency.median()), 3) for h, x in rec.groupby("hops")} \
            if len(rec) else {}
        row["hops_share"] = {int(h): round(len(x) / len(rec), 3) for h, x in rec.groupby("hops")} if len(rec) else {}
        row["via_own_sense"] = float(g.via_own_sense.mean())
        row["top_paths"] = "; ".join(f"{p} ({n})" for p, n in g.path.value_counts().head(4).items())
        rows.append(row)
    return pd.DataFrame(rows)


def pathway_weights(tr: Trace) -> pd.DataFrame:
    """Effective synaptic weights actually delivered, per pathway (sender class, travel direction, receiver class):
    every non-refractory arrival's contribution w_eff . mask (w_eff includes the morphogen anisotropy a0 / a1 at
    that slot). ``travel`` is the direction the message moved, as in ``ccg``'s ``dir``: up = from the cell below to
    the cell above. Columns: pre, travel, post, n, mean, q10, q50, q90, pos (share > 0), neg (share < 0)."""
    ar = tr.arrivals
    if not len(ar):
        return pd.DataFrame()
    refr = tr.steps.refractory.to_numpy()[ar.step.to_numpy()]
    a = ar[~refr]
    cls = tr.cells.cls.to_numpy()
    pre = np.where(a.s_cid.to_numpy() >= 0, cls[np.clip(a.s_cid.to_numpy(), 0, None)], "?")
    travel = np.array([{"lat": "lat", "up": "down", "down": "up"}[d] for d in a.dir.to_numpy()], dtype=object)
    df = pd.DataFrame(dict(pre=pre, travel=travel, post=cls[a.cid.to_numpy()], w=a.contrib.to_numpy()))
    g = df.groupby(["pre", "travel", "post"]).w
    out = pd.DataFrame(dict(n=g.size(), mean=g.mean(), q10=g.quantile(0.1), q50=g.median(), q90=g.quantile(0.9),
                            pos=g.apply(lambda x: float((x > 0).mean())), neg=g.apply(lambda x: float((x < 0).mean()))))
    return out.reset_index()


def sense_drive(tr: Trace) -> pd.DataFrame:
    """Sense-plane spikes split by what fired them (own receptor, a lateral sense arrival, an act-plane arrival from
    above, tonic, residual) per sense class (C, S) and per ring (hex distance of the column from the centre)."""
    kinds, par, _, dirs = _primary(tr)
    sp = tr.spikes
    m = sp.z.to_numpy() == 0
    ring = [hexdist(a, b) for a, b in zip(sp.a, sp.b)]
    lab = []
    for k, d in zip(kinds, dirs):
        lab.append(k if k != "arr" else f"arr_{d}")
    df = pd.DataFrame(dict(cls=sp.cls.to_numpy(), ring=ring, drv=lab))[m]
    out = df.groupby(["cls", "ring", "drv"]).size().rename("n").reset_index()
    out["share"] = out.n / out.groupby(["cls", "ring"]).n.transform("sum")
    return out


# ============================================================================================== 5. lesions
def _flags(flags) -> int:
    if isinstance(flags, int):
        return flags
    if isinstance(flags, str):
        flags = [f for f in flags.replace("+", ",").split(",") if f]
    return V3.flags(*flags)


def development_end(org, preset: str, n_lives: int = 32, seed0: int = SEED0, threads: int = 2, **world) -> dict:
    """When growth stops: quantiles of the last birth time and the end size over ``n_lives`` kernel lives."""
    lv = org.run(analysis.fresh_seeds(n_lives, seed0), threads=threads, preset=preset, **world)
    lb, ne = lv["last_birth"], lv["n_end"]
    return dict(last_birth_q=tuple(np.round(np.quantile(lb, [0.5, 0.9, 1.0]), 1)),
                n_end_q=tuple(np.round(np.quantile(ne, [0.1, 0.5, 0.9]), 1)))


def lesion(org, preset: str, flagname, t_fork: float, n_lives: int = 128, seed0: int = SEED0, *, threads: int = 2,
           t_open="fork", base_fork=0, **world) -> dict:
    """Paired effect of a kernel fork: ``flagname`` (a V3 flag name, "a+b" or a list, e.g. "lateral_off",
    "hidden_off", "receptor_off", "motor_off", "contacts_off", "chem_off", "division_off", "freeze", "genes_blind")
    applied from t0 + t_fork (fork_flags), against the unchanged twin (fork_flags 0, same t_fork and t_open), on
    ``fresh_seeds(n_lives, seed0)``. ``t_open`` "fork" (default) counts F over [t_fork, T] only; 0 counts the whole
    life. Returns base and lesioned F summaries, the paired dF (``analysis.paired``: lesioned - base) and the mean
    captures and misses of both arms. ``base_fork`` (flag names) is applied from t_fork in BOTH arms, e.g. "freeze"
    to stop development at t_fork so that the contrast isolates the message lesion from its effect on later growth
    (a body that still grows after t_fork otherwise changes its development under the lesion too)."""
    t_open = t_fork if t_open == "fork" else t_open
    seeds = analysis.fresh_seeds(n_lives, seed0)
    t_start = time.time()
    bf = _flags(base_fork) if base_fork else 0
    base = org.run(seeds, threads=threads, preset=preset, t_fork=t_fork, t_open=t_open, fork_flags=bf, **world)
    les = org.run(seeds, threads=threads, preset=preset, t_fork=t_fork, t_open=t_open,
                  fork_flags=bf | _flags(flagname), **world)
    out = dict(flag=str(flagname) + (f" | base {base_fork}" if base_fork else ""), t_fork=t_fork, t_open=t_open,
               n=n_lives, base=analysis.summary(base["F"]),
               lesion=analysis.summary(les["F"]), dF=analysis.paired(les["F"], base["F"]))
    for k in ("captures", "misses", "n_end"):
        out[k] = (float(base[k].mean()), float(les[k].mean()))
    out["seconds"] = time.time() - t_start
    return out


_JOB = None  # (org, world, lesion) for lesion_ref's worker processes (inherited through fork)


def _ref_job(seed: int):
    org, w, les = _JOB
    life = _life(org, seed, w, False, les)
    r = life.run()
    return float(r["F"]), float(r["captures"]), float(r["misses"]), life.n_blocked


def lesion_ref(org, preset: str, les: Lesion, n_lives: int = 16, seed0: int = SEED0, *, t_open="fork",
               threads: int = 2, procs: int = 1, **world) -> dict:
    """Paired effect of a reference-simulator message lesion (``Lesion``: channel, slot, plane, site or predicate
    filters), which the kernel has no fork for. The twin is a kernel life (bitwise the unlesioned reference life);
    the lesioned arm runs in pure Python, in ``procs`` forked worker processes (keep procs <= 2 on a shared
    machine; about 0.35 GB each). Cost: roughly the trace time per life (docs/PROBE.md)."""
    global _JOB
    t_open = les.t_fork if t_open == "fork" else t_open
    seeds = analysis.fresh_seeds(n_lives, seed0)
    t_start = time.time()
    w = _world(org, preset, t_open=t_open, **world)
    _JOB = (org, w, les)
    if procs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(procs) as pool:
            res = pool.map(_ref_job, seeds, chunksize=1)
    else:
        res = [_ref_job(s) for s in seeds]
    _JOB = None
    base = org.run(seeds, threads=threads, preset=preset, t_open=t_open, **world)
    Fl = np.array([r[0] for r in res])
    return dict(lesion=les, n=n_lives, t_open=t_open, base=analysis.summary(base["F"]), lesioned=analysis.summary(Fl),
                dF=analysis.paired(Fl, base["F"]),
                captures=(float(base["captures"].mean()), float(np.mean([r[1] for r in res]))),
                misses=(float(base["misses"].mean()), float(np.mean([r[2] for r in res]))),
                blocked_per_life=float(np.mean([r[3] for r in res])), seconds=time.time() - t_start)


def check_lesion_equivalence(org, preset: str, t_fork: float, seeds, **world) -> list[tuple[float, float]]:
    """Self-test of the reference lesion: Lesion(t_fork, slots="lateral") must equal the kernel's lateral_off fork
    bitwise. Returns (reference F, kernel F) per seed and raises if any differs."""
    w = _world(org, preset, **world)
    kl = org.run(list(seeds), threads=1, preset=preset, t_fork=t_fork, fork_flags=V3.flags("lateral_off"), **world)
    out = []
    for i, s in enumerate(seeds):
        r = _life(org, s, w, False, Lesion(t_fork, slots="lateral")).run()
        out.append((float(r["F"]), float(kl["F"][i])))
        if out[-1][0] != out[-1][1]:
            raise AssertionError(f"seed {s}: reference lesion F {out[-1][0]!r} != kernel lateral_off {out[-1][1]!r}")
    return out


def fmt_lesion(r: dict) -> str:
    d = r["dF"]
    b = r["base"]
    lz = r.get("lesioned", r.get("lesion"))
    name = r.get("flag", None) or repr(r.get("lesion"))
    return (f"{name} @t_fork {r.get('t_fork', getattr(r.get('lesion'), 't_fork', '?'))}: base {b['mean']:+.3f} "
            f"+- {b['se']:.3f}, lesioned {lz['mean']:+.3f} +- {lz['se']:.3f}, dF {d['mean']:+.3f} +- {d['se']:.3f} "
            f"(z {d['z']:+.1f}, n {d['n']})")


# ============================================================================================== reports
def report(tr: Trace, *, ccg_min_pre: int = 20) -> str:
    """A one-trace text report: summary, steering, tuning by class, CCG, act drivers, chain summary, drive matrix."""
    out = [tr.summary(), f"steering: {steering(tr)}", "tuning:", tuning_table(tuning(tr)),
           "ccg:", ccg_table(ccg(tr), ccg_min_pre)]
    ad = act_drivers(tr)
    out.append("act drivers:\n" + ad.to_string(index=False))
    out.append("chains:\n" + chain_summary(chains(tr)).to_string(index=False))
    dm = drive_matrix(tr)
    out.append("drive matrix:\n" + dm[dm.share >= 0.02].to_string(index=False))
    pw = pathway_weights(tr)
    if len(pw):
        out.append("pathway weights:\n" + pw[pw.n >= 50].round(3).to_string(index=False))
    return "\n".join(out)


def pooled(fn, trs, **kw) -> pd.DataFrame:
    """``fn(tr, **kw)`` (a per-trace DataFrame probe: tuning, chains, drive_matrix, sense_drive) over several traces,
    concatenated with a ``life`` column."""
    return pd.concat([fn(tr, **kw).assign(life=i) for i, tr in enumerate(trs)], ignore_index=True)


def _share(dm: pd.DataFrame, post, drivers) -> float:
    g = dm[dm.post.isin(post)]
    tot = g.n.sum()
    return float(g[g.driver.isin(drivers)].n.sum() / tot) if tot else np.nan


def signature(trs, *, relabel_roles: bool = True) -> dict:
    """The numbers that tell a router from a reflex (docs/PROBE.md, "Signatures"), pooled over traces:
    F; act-spike chains (M = rim act cells: share of receptor-origin chains that start in another column, share with
    at least one lateral hop, origin signal probability, latency by hop count); what fires the sense cells (own
    receptor vs a lateral sense arrival); lateral sense-plane CCG sharpness vs the vertical S -> M one; correlational
    act drivers; steering alignment; sense-cell bearing selectivity."""
    if not isinstance(trs, (list, tuple)):
        trs = [trs]
    if relabel_roles:
        for tr in trs:
            relabel(tr)
    ch = pooled(chains, trs)
    cs = chain_summary(ch).set_index("cls")
    dm = pooled(drive_matrix, trs).groupby(["post", "driver"]).n.sum().reset_index()
    sense = ("S", "J", "C")
    lat_sense = [f"{c}(lat)" for c in sense]
    cg = ccg(trs)
    lat = cg[cg.pre.isin(sense) & cg.post.isin(sense) & (cg.dir == "lat") & (cg.n_pre >= 20)]
    up = cg[cg.pre.isin(sense) & cg.post.isin(("M", "K", "I")) & (cg.dir == "up") & (cg.n_pre >= 20)]
    ad = act_drivers(trs).set_index("cls")
    st = [steering(tr) for tr in trs]
    tun = pooled(tuning, trs)
    tsense = tun[tun.cls.isin(sense) & (tun.n_spikes >= 10)]
    out = dict(lives=len(trs), F=float(np.mean([tr.F for tr in trs])))
    for cls in ("M", "all"):
        if cls in cs.index:
            r = cs.loc[cls]
            out[f"chain_{cls}"] = dict(spikes=int(r.spikes), rec=round(r.rec, 3),
                                       rec_other_col=round(r.rec_other_col, 3), relayed=round(r.relayed, 3),
                                       rec_signal=round(r.rec_signal, 3),
                                       lat_by_hops=r.lat_by_hops, hops_share=r.hops_share, top_paths=r.top_paths)
    out["sense_fired_by_receptor"] = round(_share(dm, sense, ["rec"]), 3)
    out["sense_fired_by_lateral_sense"] = round(_share(dm, sense, lat_sense), 3)
    out["act_fired_from_below"] = round(_share(dm, ("M", "K", "I"), [f"{c}(down)" for c in sense]), 3)
    out["act_fired_by_act_lateral"] = round(_share(dm, ("M", "K", "I"), ["M(lat)", "K(lat)", "I(lat)"]), 3)
    out["ccg_lateral_sense"] = [f"{r.pre}->{r.post} peak {r.peak_lag:.2f} x{r.peak_ratio:.1f} sharp {r.sharp:.1f} "
                                f"lift {r.lift:.2f}" for r in lat.itertuples()]
    out["ccg_sense_up"] = [f"{r.pre}->{r.post} peak {r.peak_lag:.2f} x{r.peak_ratio:.1f} sharp {r.sharp:.1f}"
                           for r in up.itertuples()]
    if "M" in ad.index:
        r = ad.loc["M"]
        out["act_drivers_M"] = dict(own_sense=round(r.own_sense, 3), own_sense_chance=round(r.own_sense_chance, 3),
                                    other_sense_r1=round(r.other_sense_r1, 3),
                                    other_sense_r1_chance=round(r.other_sense_r1_chance, 3),
                                    own_first=round(r.own_first, 3), act_nb=round(r.act_nb, 3),
                                    act_nb_chance=round(r.act_nb_chance, 3), lat_own_q=r.lat_own_q)
    out["steering_align"] = round(float(np.mean([s.get("align", np.nan) for s in st])), 3)
    out["steering_toward"] = round(float(np.mean([s.get("toward", np.nan) for s in st])), 3)
    out["sense_vs_by_cls"] = {k: round(float(g.vs.mean()), 3) for k, g in tsense.groupby("cls")}
    out["sense_pref_minus_own_med"] = {k: round(float(np.nanmedian(np.abs(g.pref_minus_own))), 1)
                                       for k, g in tsense.groupby("cls") if g.pref_minus_own.notna().any()}
    tact = tun[(tun.z == 1) & tun.get("align", pd.Series(np.nan, index=tun.index)).notna()]
    out["act_align_by_cls"] = {k: round(float(g["align"].mean()), 3) for k, g in tact.groupby("cls")}
    return out
