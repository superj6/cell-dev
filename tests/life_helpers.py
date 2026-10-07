"""Shared organisms, runners and comparisons for the one-life tests (tests/test_life_*.py)."""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from src import lattice
from src.life import build, spec
from src.life import reference as ref

PM = spec.flags("program_mode")
CAP = 4096  # raster and fate-log capacity used by the comparisons
HEX7 = [(0, 0), (1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
ALONE = spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1)  # the best lone cell (design gate G1)
SILENT = spec.theta()  # never fires, never divides
ROW = spec.PROGRAM_ROW

# world values that spec.validate_world refuses and the kernel and the reference answer with -2 (LIFE_ABI.md 4.7)
INVALID_WORLD_VALUES = [
    dict(P0=0.0), dict(P0=-1.0), dict(P0=1e-4), dict(P0=2.0, clock_sd=1.0, tick_jit=0.9), dict(clock_sd=1.5),
    dict(clock_sd=-0.1), dict(delay_sd=2.0), dict(tick_jit=-2.0), dict(tick_jit=1.0), dict(jit=-0.1),
    dict(tau_mis=1.0), dict(tau_z=0.0), dict(tau_R=0.0), dict(tau_e=-1.0), dict(d0=0.0), dict(d_min=0.0),
    dict(d_min=1e-9), dict(th_lo=0.7), dict(th=1.0), dict(th_lo=-0.1), dict(h_inc=-1.0), dict(c_live=-0.02),
    dict(c_div=-0.5), dict(n_max=0), dict(n_max=20.5), dict(n_max=2 ** 21), dict(e_max=-1), dict(oracle_cap=20.5),
    dict(oracle_cap=-1), dict(fabric_R=-1), dict(fabric_R=2.5), dict(drop_p=2.0), dict(kill_frac=-1.0),
    dict(noise_rate=-0.1), dict(noise_rate=1e6), dict(stuck_a=2 ** 31), dict(t0=2.0 ** 31), dict(T=2.0 ** 31),
    dict(jit=float("nan")), dict(tau_z=float("inf")),
]
# the edges of those ranges, which are valid
EDGE_WORLD_VALUES = [
    dict(P0=0.25), dict(clock_sd=1.0), dict(delay_sd=1.0), dict(jit=0.0, tau_mis=0.0, tick_jit=0.0), dict(th_lo=0.0),
    dict(drop_p=1.0, kill_frac=1.0), dict(noise_rate=1024.0), dict(d_min=2.0 ** -10), dict(n_max=1), dict(e_max=0),
    dict(c_live=0.0, h_inc=0.0), dict(t0=-1024.0),
]


def r25(p_div_lo: float = 1 / 16, chem: bool = False, **contact_extra) -> np.ndarray:
    """R25-v1 as a phenotype program (LIFE_ABI.md 7.5); ``contact_extra`` adds knobs to the contact row."""
    contact = spec.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1, p_div=0.5, phi=2,
                         **contact_extra)
    alone = spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1, p_div=0.5, phi=2)
    juv = contact.copy()
    juv[spec.K["emit0"]] = 0.0
    sc = dict(Dm0=0.05, Dm1=0.02, km0=0.05, km1=0.1) if chem else {}
    return spec.pack_program(contact, alone=alone, juvenile=juv, juv_ticks=10, flank_gate=2, p_div_lo=p_div_lo, **sc)


# turnover, secretion, polarity, directional gain and chirality on the contact row, so every handler runs
BUSY = r25(chem=True, p_die=2.0 ** -6, sec0=0.3, sec1=0.1, pol0=1.0, a0=0.5, chi=0.5)


def grn_genome(seed: int = 6) -> np.ndarray:
    """A raw float32 8-gene genome whose readout is biased to be tonic, inhibitory, emitting, contractile,
    dividing and dying, with random regulation, chemistry and directional gain."""
    rng = np.random.default_rng(seed)
    g = (rng.normal(0, 1, spec.GENOME_SIZE) * 0.7).astype(np.float32)
    act = spec.genome_view(g, "act")
    act[:] = 0.0
    act[:8] = 1.0
    a0 = spec.genome_view(g, "a0")
    for knob, shift in (("b", 1.3), ("w0", -0.8), ("emit0", 0.8), ("kappa", 1.5), ("p_div", 1.4), ("p_die", 0.3)):
        a0[spec.K[knob]] += shift
    return g


def program_world(w: spec.World) -> spec.World:
    return replace(w, flags=w.flags | PM)


def kernel(w: spec.World, seeds, *, program=None, genome=None, init=None, threads: int = 1,
           cap: int = CAP) -> build.Lives:
    """Run lives through the C kernel; ``genome`` is a raw float32 genome (or a list of them, one per life)."""
    if program is not None:
        return build.run(program_world(w), seeds, programs=program, init=init, threads=threads, raster_cap=cap,
                         fate_cap=cap)
    gt = spec.pack_genomes(np.atleast_2d(np.asarray(genome, dtype=np.float32)), w.lattice)
    return build.run(w, seeds, genomes=gt, init=init, threads=threads, raster_cap=cap, fate_cap=cap)


def reference(w: spec.World, seed: int, *, program=None, genome=None, init=None, tie: int = 0, order: int = 0,
              salt: int = 0, cap: int = CAP) -> ref.LifeResult:
    cells = None if init is None else [tuple(c[:2]) for c in init]
    rows = None if init is None else [c[2] if len(c) > 2 else -1 for c in init]
    return ref.run(w, program=program, genome=genome, cells=cells, rows=rows, seed=seed, tie_seed=tie,
                   order_seed=order, salt=salt, raster_cap=cap, fate_cap=cap)


def bits(a) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def same(a: build.Lives, b: build.Lives) -> bool:
    """Bitwise equality of two kernel batches: ledger, hashes, raster and fate log."""
    if not (np.array_equal(bits(a.ledger), bits(b.ledger)) and np.array_equal(a.hashes, b.hashes)):
        return False
    for i in range(len(a.ledger)):
        ta, ua = a.spikes(i)
        tb, ub = b.spikes(i)
        fa, ga = a.fates(i)
        fb, gb = b.fates(i)
        if not (np.array_equal(bits(ta), bits(tb)) and np.array_equal(ua, ub) and np.array_equal(fa, fb)
                and np.array_equal(bits(ga), bits(gb))):
            return False
    return True


def mismatch(k: build.Lives, i: int, r: ref.LifeResult) -> list[str]:
    """What differs between kernel life i and a reference life (empty when they agree bitwise)."""
    out = [c for j, c in enumerate(spec.LEDGER) if bits(k.ledger[i, j]) != bits(r.ledger[j])]
    out += [f"hash:{h}" for j, h in enumerate(spec.HASHES) if int(k.hashes[i, j]) != int(r.hashes[j])]
    t, u = k.spikes(i)
    if not (np.array_equal(bits(t), bits(r.raster_t)) and np.array_equal(u, r.raster_uid)):
        out.append("raster")
    fi, ff = k.fates(i)
    if not (np.array_equal(fi, r.fate_i) and np.array_equal(bits(ff), bits(r.fate_f))):
        out.append("fate")
    if k.raster_n[i] != r.raster_n or k.fate_n[i] != r.fate_n:
        out.append("log counts")
    return out


def conservation_error(led) -> np.ndarray:
    """Relative morphogen-mass imbalance (LIFE_ABI.md 4.9)."""
    led = np.atleast_2d(led)
    L = spec.L
    out = led[:, L["morph_decayed"]] + led[:, L["morph_lost"]] + led[:, L["morph_content_end"]]
    out = out + led[:, L["morph_inflight_end"]]
    return np.abs(led[:, L["morph_secreted"]] - out) / np.maximum(led[:, L["morph_secreted"]], 1e-300)


def as_u64(x: int) -> int:
    return int(x) & spec.MASK64


# ------------------------------------------------------------------------------------------ frozen physics mirror
def _lock(w: spec.World) -> bool:
    return bool(w.flags & spec.FLAGS["lockstep"])


def taumis(w: spec.World, seed: int, a: int, b: int, k: int = 0) -> float:
    if _lock(w):
        return 1.0
    return 1.0 + w.tau_mis * (2.0 * spec.draw(seed, spec.S_TAU, spec.sitekey(a, b), k) - 1.0)


def clock(w: spec.World, seed: int, a: int, b: int, k: int = 0) -> float:
    if _lock(w):
        return w.P0
    return w.P0 * math.exp(w.clock_sd * spec.normal(seed, spec.S_CLK, spec.sitekey(a, b), k))


def tick_times(w: spec.World, seed: int, uid: int, a: int, b: int, t_birth: float, t_max: float, k: int = 0):
    """A cell's own clock (LIFE_ABI.md 7.4 step 9 and 7.6): its tick times below t_max."""
    P_n = clock(w, seed, a, b, k)
    if _lock(w):
        t = w.t0 + w.P0 * (math.floor((t_birth - w.t0) / w.P0) + 1.0)
    else:
        t = t_birth + spec.draw(seed, spec.S_PHASE, spec.sitekey(a, b), k) * P_n
    if t <= t_birth:
        t = math.nextafter(t_birth, math.inf)
    jit = 0.0 if _lock(w) else w.tick_jit
    out, j = [], 0
    while t < t_max:
        out.append(t)
        t = t + P_n * (1.0 + jit * (2.0 * spec.draw(seed, spec.S_TICK, uid, j) - 1.0))
        j += 1
    return out


def contact_delay(w: spec.World, seed: int, src, dst, k_src: int = 0, k_dst: int = 0) -> float:
    """Frozen delay of the directed contact src -> dst, as the sender's view holds it (LIFE_ABI.md 7.7)."""
    if _lock(w):
        return w.d0
    z = spec.normal(seed, spec.S_DC, spec.sitekey(*src), spec.sitekey(*dst), (k_src << 32) | k_dst)
    return w.d0 * math.exp(w.delay_sd * z)


def spike_delay(w: spec.World, seed: int, uid: int, spike_no: int, slot: int, dc: float, delta: float) -> float:
    """LIFE_ABI.md 7.3: max(d_min, dc (1 + jit (2u - 1)) + delta), u keyed by the sender's own spike count."""
    jit = 0.0 if _lock(w) else w.jit
    u = spec.draw(seed, spec.S_JIT, uid, spike_no, slot)
    dl = dc * (1.0 + jit * (2.0 * u - 1.0)) + delta
    return w.d_min if dl < w.d_min else dl


def slot_of(kind: str, src, dst) -> int:
    return lattice.offsets(kind).index((dst[0] - src[0], dst[1] - src[1]))


def uid0(seed: int, j: int) -> int:
    return spec.uid_initial(seed, j)


def fate_uid(x: int) -> int:
    """A uid as the fate log stores it (int64) -> uint64."""
    return int(x) & spec.MASK64
