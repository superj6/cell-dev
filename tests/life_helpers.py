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


def abi1_draw(rng, scale: float) -> np.ndarray:
    """``GENOME_SIZE`` normals drawn as under ABI 1, whose W had one more column (flank_best / 2, removed in ABI 2:
    LIFE_ABI.md 15.32): that column is dropped, so a seed gives the test genome it gave before, minus that input."""
    G, NIN = spec.G_MAX, spec.NIN
    g = (rng.normal(0, 1, spec.GENOME_SIZE + G) * scale).astype(np.float32)
    return np.concatenate([g[:G * (NIN + 1)].reshape(G, NIN + 1)[:, :NIN].reshape(-1), g[G * (NIN + 1):]])


def grn_genome(seed: int = 6) -> np.ndarray:
    """A raw float32 8-gene genome whose readout is biased to be tonic, inhibitory, emitting, contractile,
    dividing and dying, with random regulation, chemistry and directional gain."""
    g = abi1_draw(np.random.default_rng(seed), 0.7)
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
    """What differs between kernel life i and a reference life (empty when they agree bitwise), in the kernel
    batch's ABI (``spec.CURRENT`` unless the run asked for another)."""
    if k.ledger.shape[1] != len(r.ledger) or k.hashes.shape[1] != len(r.hashes):
        return ["abi"]
    out = [c for j, c in enumerate(k.layout.LEDGER) if bits(k.ledger[i, j]) != bits(r.ledger[j])]
    out += [f"hash:{h}" for j, h in enumerate(k.layout.HASHES) if int(k.hashes[i, j]) != int(r.hashes[j])]
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


# ------------------------------------------------------------------------------------- ABI 3: 3D bodies and CATCH
V3 = spec.V3
PM3 = V3.flags("program_mode")
R3 = V3.PROGRAM_ROW
# the hand-built column reflex (BODY_DESIGN_PROPOSAL.md 3.2), one fixed program row per initial cell
SENSE3 = V3.theta(g_r=1.0, emit0=1, tau_m=2, t_ref=1)  # relays every receptor event on channel 0
MOTOR3 = V3.theta(w0=1.0, kappa=1.0, t_ref=4.0, tau_m=2)  # act cell: one channel-0 arrival fires a full twitch
CLICKER3 = V3.theta(g_r=0.55, emit0=1, tau_m=2, t_ref=1)  # centre coincidence sensor: one noise event never clicks
QUIET3 = V3.theta(tau_m=2, t_ref=1)  # never fires (a silent hidden cell)
COLUMN3 = V3.pack_program(MOTOR3, alone=SENSE3, juvenile=CLICKER3, rim=QUIET3)


def hexdisk(k: int) -> list[tuple[int, int]]:
    """The hex sites within ring k of the origin (1, 7, 19, 37, ... sites)."""
    return [(a, b) for a in range(-k, k + 1) for b in range(-k, k + 1) if max(abs(a), abs(b), abs(a + b)) <= k]


def columns(sites, hidden: int = 0, rows=COLUMN3) -> list[tuple[int, int, int, int]]:
    """A sense cell under an act cell at every site (the centre sensor is the clicker), then ``hidden`` quiet cells
    on each column, as initial cells ``(a, b, z, row)`` of ``COLUMN3``. The control planes come first, so their
    cells keep their uids whatever the hidden planes hold."""
    body = [(a, b, 0, R3["juvenile"] if (a, b) == (0, 0) else R3["alone"]) for a, b in sites]
    body += [(a, b, 1, R3["contact"]) for a, b in sites]
    return body + [(a, b, 2 + h, R3["rim"]) for h in range(hidden) for a, b in sites]


def catch(name: str = "catch_v1_l2", **kw) -> spec.World:
    """A CATCH preset (BODY_DESIGN_PROPOSAL.md 3.1) with overrides."""
    return spec.world(name, **kw)


def grn3(seed: int, **shift) -> np.ndarray:
    """A raw 8-gene ABI-3 genome biased to be tonic, emitting, contractile, dividing, dying, receptive and to place
    upward, with random weights on the receptor trace and the plane cues; ``shift`` changes the readout biases."""
    rng = np.random.default_rng(seed)
    g = (rng.normal(0, 0.7, V3.GENOME_SIZE)).astype(np.float32)
    act = V3.genome_view(g, "act")
    act[:] = 0.0
    act[:8] = 1.0
    bias = dict(b=1.3, w0=-0.8, emit0=0.8, kappa=1.5, p_div=0.9, p_die=0.3, g_r=0.8, zeta=1.0)
    bias.update(shift)
    a0 = V3.genome_view(g, "a0")
    for knob, s in bias.items():
        a0[V3.K[knob]] += s
    V3.genome_view(g, "W")[:8, 22:25] = rng.normal(0, 2.0, (8, 3)).astype(np.float32)
    return g


def enclosed_tiles(fate_i, fate_f, kind: str = "hexprism") -> int:
    """The most tiles a body enclosed (its filled footprint minus its occupied columns, LIFE_ABI.md 15.61) after any
    time group of its life, rebuilt from its complete fate log: > 0 iff the drag ever counted a hole."""
    ev = sorted((fr[0], row[0], row[1] & spec.MASK64, row[3], row[4]) for row, fr in
                zip(np.asarray(fate_i).tolist(), np.asarray(fate_f).tolist()) if row[0] in (1, 2))
    cols, col_of, most = {}, {}, 0
    for j, (t, kind_, uid, a, b) in enumerate(ev):
        if kind_ == 1:
            col_of[uid] = (a, b)
            cols[(a, b)] = cols.get((a, b), 0) + 1
        else:
            ab = col_of[uid]
            cols[ab] -= 1
            if cols[ab] == 0:
                del cols[ab]
        if j + 1 == len(ev) or ev[j + 1][0] != t:  # after the whole group: what the drag sees
            most = max(most, spec.filled_footprint(cols, kind) - len(cols))
    return most


def kernel3(w: spec.World, seeds, *, program=None, genome=None, init=None, threads: int = 1,
            cap: int = CAP) -> build.Lives:
    """Lives through the C kernel in ABI 3's shapes; ``init`` cells are ``(a, b)``, ``(a, b, z)`` or
    ``(a, b, z, row)``; ``genome`` is a raw ABI-3 genome (or one per life)."""
    if program is not None:
        return build.run(replace(w, flags=w.flags | PM3), seeds, programs=program, init=init, threads=threads,
                         raster_cap=cap, fate_cap=cap, abi=V3)
    gt = V3.pack_genomes(np.atleast_2d(np.asarray(genome, dtype=np.float32)), w.lattice)
    return build.run(w, seeds, genomes=gt, init=init, threads=threads, raster_cap=cap, fate_cap=cap, abi=V3)


def reference3(w: spec.World, seed: int, *, program=None, genome=None, init=None, tie: int = 0, order: int = 0,
               salt: int = 0, cap: int = CAP, records: bool = False) -> ref.LifeResult:
    """One life through the Python reference in ABI 3's shapes (the arguments of ``kernel3``)."""
    cells = None if init is None else [tuple(c[:3]) if len(c) > 2 else (c[0], c[1], 0) for c in init]
    rows = None if init is None else [c[3] if len(c) > 3 else -1 for c in init]
    return ref.run(w, program=program, genome=genome, cells=cells, rows=rows, seed=seed, tie_seed=tie,
                   order_seed=order, salt=salt, raster_cap=cap, fate_cap=cap, records=records, abi=V3)


# turnover in both control planes: sensors die, the hotspot's motor dies often, and motors divide into the gaps (the
# daughters take the selector's contact row, a motor); initial body: TURNOVER_BODY
TURNOVER3 = V3.pack_program(V3.theta(w0=1.0, kappa=1.0, t_ref=4.0, tau_m=2, p_div=1 / 32),
                            alone=V3.theta(g_r=1.0, emit0=1, tau_m=2, t_ref=1, p_die=2 ** -5), juvenile=CLICKER3,
                            rim=V3.theta(w0=1.0, kappa=1.0, t_ref=4.0, tau_m=2, p_die=1 / 8))
TURNOVER_BODY = [(a, b, z, R3["rim"] if (a, b, z) == (0, 0, 1) else r) for a, b, z, r in columns(hexdisk(1))]
# a selector-driven grower from one zygote: the zygote (its own row) senses and divides, upward first (zeta 2);
# daughters sense, relay, twitch, divide slowly and die; newborns with contacts are motors for 2 ticks
GROWER3 = V3.pack_program(
    V3.theta(g_r=0.5, emit0=1, w0=0.5, kappa=1, t_ref=4, tau_m=2, p_div=1 / 16, p_die=2 ** -6, zeta=-1),
    alone=V3.theta(g_r=1.0, emit0=1, tau_m=2, t_ref=1, p_div=0.5, zeta=2),
    zygote=V3.theta(g_r=0.55, emit0=1, tau_m=2, t_ref=1, p_div=0.5, zeta=2, kappa=0.5), juvenile=MOTOR3, juv_ticks=2,
    zyg_row=1)
