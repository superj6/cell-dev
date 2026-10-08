"""Smoke tests of the one-life C kernel (src/life/kernel.c through src/life/build.py): it builds, its test exports
match spec.py bitwise, a lone cell pumps, and small bodies agree bitwise across schedulers (LIFE_ABI.md 11).

The kernel implements ABI 3 (``build.KERNEL``); ``build.run`` speaks ``spec.CURRENT``'s ABI at its boundary. The raw
``life_run`` calls below use ABI 3's arrays. The CATCH world (BODY-1 v1, LIFE_ABI.md 9.7) is tested at the end."""
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from src.life import build, spec
from src.life import reference as ref
from tests.life_helpers import EDGE_WORLD_VALUES, INVALID_WORLD_VALUES

Y14 = [0.3, -2.7, 1.0, 0.5, -0.26, 0.0, 1e-9, 0.3, 0.75, 0.13, 0.0, -2.0, 1.1, 0.0, -1.0, 0.5, -9.0, 0.0, 2.2,
       -0.0624, 0.0625]
THETA14 = [0.25, -2.0, 1.0, 4.0, 1.5, 0.0, 1.0, 0.5, 0.5, 0.0078125, 0.5, 0.0, 1.0, 0.25, 0.13447071068499755, 0.875,
           -2.0, 8.0, 2.0, -0.0, 0.0]
HEX7 = [(0, 0), (1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def _bits(a) -> np.ndarray:
    return np.ascontiguousarray(a, dtype=np.float64).view(np.uint64)


def _program():
    """R25-like body plan with apoptosis, chemistry and directional gain, so every handler runs."""
    contact = spec.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1, p_div=0.5, phi=2,
                         p_die=2 ** -5, sec0=0.2, pol0=1, a0=0.5, chi=0.5)
    alone = spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1, p_div=0.5, phi=2, sec0=0.2)
    juvenile = contact.copy()
    juvenile[spec.K["emit0"]] = 0.0
    return spec.pack_program(contact, alone=alone, juvenile=juvenile, juv_ticks=10, flank_gate=2, p_div_lo=1 / 16,
                             Dm0=0.02, km0=0.05)


def _genome(seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    raw = rng.normal(0.0, 0.6, spec.GENOME_SIZE).astype(np.float32)
    spec.genome_view(raw, "act")[:] = [1.0] * 8 + [0.0] * 8
    a0 = spec.genome_view(raw, "a0")
    a0[spec.K["b"]] += 1.0
    a0[spec.K["p_div"]] += 1.5
    a0[spec.K["emit0"]] += 1.0
    a0[spec.K["p_die"]] -= 0.5
    return spec.pack_genomes(raw)


def _same(a: build.Lives, b: build.Lives) -> bool:
    return np.array_equal(_bits(a.ledger), _bits(b.ledger)) and np.array_equal(a.hashes, b.hashes)


def _conservation_error(res: build.Lives) -> np.ndarray:
    sec = res["morph_secreted"]
    out = res["morph_decayed"] + res["morph_lost"] + res["morph_content_end"] + res["morph_inflight_end"]
    return np.abs(sec - out) / np.maximum(sec, 1e-300)


def test_kernel_builds_and_its_exports_match_spec_bitwise():
    lib = build.load()
    assert lib.life_abi_version() == build.KERNEL.version == 3 and build.library_path().exists()
    assert build.hash64(1, 2, 3, 4) == spec.hash64(1, 2, 3, 4) == 0x89F838C6080F2B76
    assert build.hash64(spec.MASK64, 7, -1) == 0x6BEEACB0A480F707
    assert build.normal(42, spec.S_CLK, spec.sitekey(0, 0), 0) == 0.25705196441331246
    assert build.normal(42, spec.S_DC, spec.sitekey(0, 0), spec.sitekey(1, 0), 0) == 1.039345905501138
    assert np.array_equal(_bits(build.decode(Y14)), _bits(THETA14))
    rng = np.random.default_rng(0)
    halves = np.array([k / 8 for k in range(-40, 41)])  # rounding ties of every grid
    for i in range(300):
        y = rng.normal(0.0, 2.0, spec.P) if i % 2 else rng.choice(halves, spec.P)
        assert np.array_equal(_bits(build.decode(y)), _bits(spec.decode_knobs(y)))
        row, g = rng.normal(0.0, 1.0, spec.GENOME_SIZE), rng.random(spec.G_MAX)
        assert np.array_equal(_bits(build.readout(row, g)), _bits(spec.readout(row, g)))


def test_lone_pump_and_silent_zygote():
    pump = spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1)
    w = spec.world(flags=spec.flags("program_mode"))
    res = build.run(w, list(range(8)), programs=spec.pack_program(pump), raster_cap=200, fate_cap=4)
    assert abs(res["F"].mean() - 0.0326) < 1e-3  # design gate G1: +0.0326
    assert np.all(res["n_end"] == 1) and np.all(res["births"] == 0) and np.all(res["status"] == 0)
    assert np.all(res["live_time"] == w.T) and np.all(res["beats"] == res["spikes"])
    assert np.array_equal(_bits(spec.fitness(res.ledger, w)), _bits(res["F"]))  # F re-priced from the columns
    t, uid = res.spikes(0)
    assert len(t) == res["spikes"][0] and np.all(np.diff(t) > 0) and np.all(uid == spec.uid_initial(0, 0))
    kinds, _ = res.fates(0)
    assert kinds.shape[0] == 1 and kinds[0, 0] == 1  # one birth: the zygote
    silent = build.run(w, [0], programs=spec.pack_program(spec.theta(b=0.5, tau_m=8, t_ref=2)))
    assert silent["F"][0] == -0.02 and silent["spikes"][0] == 0


def test_small_body_is_bitwise_identical_across_schedulers():
    prog = _program()
    base = spec.world(T=64.0, flags=spec.flags("program_mode"))
    lock = replace(base, flags=spec.flags("program_mode", "lockstep"))  # exact delays, grid clocks: many exact ties
    lives = [3, 5, 11]
    for w, init in ((base, None), (base, HEX7), (lock, HEX7)):
        ref = build.run(w, [[s, 0, 0, 0] for s in lives], programs=prog, init=init)
        assert np.all(ref["births"] > 0) and ref["deaths"].sum() > 0 and np.all(ref["packets"] > 0)
        assert not ref.status("ledger_mismatch").any() and not ref.status("capacity").any()
        assert np.all(_conservation_error(ref) < 1e-12)
        runs = [build.run(w, [[s, tie, 0, 977 * tie] for s in lives], programs=prog, init=init) for tie in (1, 2)]
        runs += [build.run(replace(w, window_h=h), [[s, 0, o, o] for s in lives], programs=prog, init=init)
                 for h, o in ((0.5, 1), (0.125, 2))]
        runs.append(build.run(w, lives, programs=prog, init=init, threads=2))
        assert all(_same(ref, r) for r in runs)


def test_grn_genome_lives_agree_across_schedulers():
    gt = _genome()
    w = spec.world(T=64.0)
    ref = build.run(w, [7, 8, 9], genomes=gt, fate_cap=256)
    assert np.all(ref["n_peak"] > 1) and np.all(ref["ticks"] > 0)
    assert np.all(_conservation_error(ref) < 1e-12) and not ref.status("ledger_mismatch").any()
    kinds, f = ref.fates(0)
    born = kinds[:, 0] == 1
    s0 = slice(*spec.GENOME_SLICES["s0"])
    assert np.array_equal(f[born][0, 2:], gt[0, s0])  # the zygote starts from g0 = sigma(s0)
    win = build.run(replace(w, window_h=0.25), [[s, 0, 4, 1] for s in (7, 8, 9)], genomes=gt, fate_cap=256)
    assert _same(ref, win)


def test_forks_switch_off_spikes_and_packets_but_keep_the_charges():
    prog = _program()
    # spikes sent before t_fork still arrive after it (delays < 4.1), so the ledger opens at t_fork + 8
    base = spec.world(T=96.0, flags=spec.flags("program_mode"), t_open=56.0, t_fork=48.0)
    intact = build.run(base, [5], programs=prog, init=HEX7)
    deaf = build.run(replace(base, fork_flags=spec.flags("contacts_off")), [5], programs=prog, init=HEX7)
    dry = build.run(replace(base, fork_flags=spec.flags("chem_off")), [5], programs=prog, init=HEX7)
    assert intact["arrivals"][0] > 0 and deaf["arrivals"][0] == 0 and deaf["contact_events"][0] > 0
    assert intact["packets"][0] > 0 and dry["packets"][0] == 0
    assert np.all(_conservation_error(dry) < 1e-12)
    still = build.run(replace(base, fork_flags=0, t_fork=10.0), [5], programs=prog, init=HEX7)
    assert _same(intact, still)  # a fork that changes nothing continues bitwise


PM = spec.flags("program_mode")
KV3 = build.KERNEL  # the kernel's own ABI (3): the layout of every raw life_run argument


def _vector(world=(), flags: int = PM, abi=spec) -> np.ndarray:
    """A one-life world vector of ``abi`` (``spec.CURRENT``'s by default) patched entry by entry, bypassing
    pack_world's validation."""
    base = dict(world).pop("_preset", "bell_v1")
    wv = abi.pack_world(spec.world(base, T=8.0, flags=flags))[None].copy()
    for k, v in dict(world).items():
        if k != "_preset":
            wv[0, abi.WORLD_INDEX[k]] = v
    return wv


def _kernel_table(t, size3: int, pad):
    """A table for the raw kernel: ABI-2 rows are padded neutrally to ABI 3 (LIFE_ABI.md 4.4, 4.5)."""
    if t is None:
        return None
    t = np.atleast_2d(np.asarray(t, dtype=np.float64))
    if t.shape[1] != size3:
        t = np.stack([pad(row) for row in t])
    return np.ascontiguousarray(t)


def _call(world=(), *, lat=None, n_init=None, init=None, flags: int = PM, genomes=None, programs=_program(),
          genome_of: int = 0, kind: str = "hex") -> int:
    """life_run on one life straight through ctypes with ABI-3 arrays (no build.run checks); returns its code."""
    lat_k, unit = KV3.lattice_tables(kind)
    lat = lat_k if lat is None else lat
    gt = _kernel_table(genomes, KV3.GENOME_SIZE, lambda r: KV3.pad_genomes(r, spec.V2))
    pg = _kernel_table(programs, KV3.PROGRAM_SIZE, lambda r: KV3.pad_program(r, spec.V2))
    P = build._ptr
    wv = _vector(world, flags, KV3)
    led, hs = np.zeros((1, KV3.LEDGER_SIZE)), np.zeros((1, KV3.HASH_SIZE), dtype=np.uint64)
    seeds, go = np.zeros((1, 4), dtype=np.uint64), np.array([genome_of], dtype=np.int32)
    return build.load().life_run(
        1, 1, P(lat, build._i32), P(unit, build._f64), 0 if gt is None else len(gt), P(gt, build._f64),
        0 if pg is None else len(pg), P(pg, build._f64), P(go, build._i32), P(init, build._i32), P(n_init, build._i32),
        P(wv, build._f64), P(seeds, build._u64), P(led, build._f64), P(hs, build._u64), 0, None, None, None, 0, None,
        None, None)


def test_invalid_arguments_are_rejected_by_the_kernel():
    assert _call() == 0
    assert _call({"window_h": 0.25, "oracle_cap": 5.0}) == -2
    assert _call({"window_h": 0.3}) == -2 and _call({"window_h": 1.0}) == -2
    assert _call({"flags": float(spec.flags("program_mode", "integer_twin"))}) == -2
    assert _call({"fork_flags": float(spec.flags("lockstep"))}) == -2
    assert _call({"T": 8.5}) == -2 and _call({"kill_rate": 0.1}) == -2
    assert _call(flags=0) == -1  # GRN life without a genome table
    # genome_of is checked against the row count of the table the life's mode uses (4.2)
    three = np.stack([_genome()[0]] * 3)
    assert _call(flags=0, genomes=three, genome_of=2) == 0
    assert _call(genomes=three, genome_of=2) == -1  # a program life: its table has one row
    assert _call(genome_of=-1) == -1 and _call(genome_of=1) == -1
    body = np.zeros((1, KV3.MAX_INIT, KV3.INIT_COLS), dtype=np.int32)
    assert _call(n_init=np.array([2], dtype=np.int32), init=body) == -4  # two cells on one site
    bad = KV3.lattice_tables("hex")[0].copy()
    bad[1] = 5
    assert _call(lat=bad) == -4
    with pytest.raises(ValueError):
        build.run(spec.world(flags=PM), [0], programs=_program(), init=[(0, 0), (0, 0)])


@pytest.mark.parametrize("bad", INVALID_WORLD_VALUES, ids=str)
def test_every_invalid_world_is_refused_by_the_kernel_and_the_reference(bad):
    assert _call(bad) == -2  # at once: P0 = 0 used to hang life_run, tau_z = 0 to give F = NaN with status 0
    with pytest.raises(ref.ArgError) as e:
        ref._check_world(_vector(bad)[0])
    assert e.value.rc == -2


@pytest.mark.parametrize("ok", EDGE_WORLD_VALUES, ids=str)
def test_the_edges_of_the_world_ranges_run(ok):
    assert _call(ok) == 0
    ref._check_world(_vector(ok)[0])


_NON_FINITE = """
import numpy as np
from src.life import build, spec
from src.life import reference as ref
from tests.test_life_kernel_smoke import _call, _genome, _program
gt = _genome()
for idx, v in ((spec.GENOME_SLICES["a0"][0] + spec.K["tau_m"], np.nan), (spec.GENOME_SLICES["a0"][0] + spec.K["delta"],
               np.nan), (spec.GENOME_SLICES["W"][0], np.inf), (spec.GENOME_SLICES["A"][0] + 5, -np.inf)):
    bad = gt.copy()
    bad[0, idx] = v
    assert _call(flags=0, genomes=bad) == -1
    assert _call(flags=0, genomes=np.stack([gt[0], bad[0]]), genome_of=0) == 0  # only the rows lives use are read
    lat, unit = spec.lattice_tables("hex")
    out = ref.life_run(lat, unit, bad, None, [0], None, None, spec.pack_world(spec.world(T=8.0))[None], [[0] * 4])
    assert out["rc"] == -1
bad = _program().copy()
bad[spec.PROGRAM_ROW["contact"] * spec.P + spec.K["tau_m"]] = np.nan
assert _call(programs=bad) == -1
th = build.decode([np.nan] * spec.P)  # every table index is clipped, NaN to the lowest level
assert (th[spec.K["tau_m"]], th[spec.K["tau_tr"]], th[spec.K["delta"]], th[spec.K["p_div"]]) == (1.0, 2.0, 0.0, 0.0)
hi, lo = build.decode([np.inf] * spec.P), build.decode([-np.inf] * spec.P)
assert (hi[spec.K["tau_m"]], hi[spec.K["kappa"]], hi[spec.K["p_die"]], lo[spec.K["tau_m"]]) == (16.0, 1.0, 1.0, 1.0)
print("ok")
"""


def test_non_finite_tables_are_refused_and_decode_never_indexes_outside_its_tables():
    # 4.4: a NaN readout used to index TAU_M[INT_MIN] and kill the process (SIGSEGV); run in a child to survive that
    root = Path(__file__).resolve().parents[1]
    res = subprocess.run([sys.executable, "-c", _NON_FINITE], cwd=root, capture_output=True, text=True, timeout=300)
    assert res.returncode == 0 and res.stdout.strip() == "ok", (res.returncode, res.stderr[-2000:])


# ================================================================================ ABI 3 and the CATCH world (9.7)
V3 = spec.V3
CPM = V3.flags("program_mode")
_th = V3.theta
# the prototype's hand-built column reflex (BODY_DESIGN_PROPOSAL.md 3.2), one fixed program row per initial cell
SENSE = _th(g_r=1.0, emit0=1, tau_m=2, t_ref=1)  # relays its receptor events on channel 0
MOTOR = _th(w0=1.0, kappa=1.0, t_ref=4.0, tau_m=2)  # act cell: one channel-0 arrival fires a full twitch
CLICKER = _th(g_r=0.55, emit0=1, tau_m=2, t_ref=1)  # centre coincidence sensor (single noise events do not click)
QUIET = _th(tau_m=2, t_ref=1)  # never fires
COLUMN = V3.pack_program(MOTOR, alone=SENSE, juvenile=CLICKER, rim=QUIET)
R3 = V3.PROGRAM_ROW


def _hexdisk(k: int) -> list[tuple[int, int]]:
    return [(a, b) for a in range(-k, k + 1) for b in range(-k, k + 1) if max(abs(a), abs(b), abs(a + b)) <= k]


def _columns(sites, hidden: int = 0) -> list[tuple[int, int, int, int]]:
    """Sense cell under an act cell at every site (the centre sensor is the clicker); then `hidden` quiet cells on
    each column, listed after every control-plane cell so the control cells keep their uids."""
    body = [(a, b, 0, R3["juvenile"] if (a, b) == (0, 0) else R3["alone"]) for a, b in sites]
    body += [(a, b, 1, R3["contact"]) for a, b in sites]
    return body + [(a, b, 2 + h, R3["rim"]) for h in range(hidden) for a, b in sites]


def _catch(name: str = "catch_v1", **kw) -> spec.World:
    return spec.world(name, flags=kw.pop("flags", CPM), **kw)


def _run3(w, seeds, **kw) -> build.Lives:
    return build.run(w, seeds, abi=V3, **kw)


def _grn3(seed: int) -> np.ndarray:
    """A raw 8-gene ABI-3 genome that senses, emits, twitches, divides and grows upward, with random weights on the
    receptor trace and the plane cues."""
    rng = np.random.default_rng(seed)
    g = (rng.normal(0, 1, V3.GENOME_SIZE) * 0.6).astype(np.float32)
    act = V3.genome_view(g, "act")
    act[:] = 0.0
    act[:8] = 1.0
    a0 = V3.genome_view(g, "a0")
    for k, s in (("b", 0.6), ("w0", 0.8), ("emit0", 0.8), ("kappa", 1.5), ("p_div", 1.6), ("p_die", -0.3),
                 ("g_r", 0.8), ("zeta", 1.0), ("sec0", 0.5), ("pol0", 0.8), ("a0", 0.5)):
        a0[V3.K[k]] += s
    V3.genome_view(g, "W")[:8, 22:25] = rng.normal(0, 2.0, (8, 3))
    return g


def _same3(a: build.Lives, b: build.Lives) -> bool:
    """Bitwise equality of ledgers and hashes, and of the raster and fate logs when both runs kept them."""
    if not (_same(a, b) and np.array_equal(a.raster_n, b.raster_n) and np.array_equal(a.fate_n, b.fate_n)):
        return False
    for i in range(len(a.ledger) if a.raster_t is not None and a.fate_i is not None else 0):
        (ta, ua), (tb, ub) = a.spikes(i), b.spikes(i)
        (fa, ga), (fb, gb) = a.fates(i), b.fates(i)
        if not (np.array_equal(_bits(ta), _bits(tb)) and np.array_equal(ua, ub) and np.array_equal(fa, fb)
                and np.array_equal(_bits(ga), _bits(gb))):
            return False
    return True


def test_abi3_exports_match_spec_bitwise():  # LIFE_ABI.md 4.2 and 14
    z = spec.uid_initial(42, 0)
    c0 = build.receptor_next(42, z, 0, 0.0, 2.05)
    assert c0 == 0.9337337422296379 and build.receptor_next(42, z, 1, c0, 2.05) == 1.3670951439075458
    assert build.halo(1.0, 0.5, 1.5) == 0.7574651283969664
    assert build.blob_heading(42, 0, 0, 0.1) == (-0.09998754332570875, 0.0015783471384705633)
    assert build.blob_place(42, 1, 0, 0.0, 0.0, 2.0, 6.0) == (-3.133232594777813, 3.264525461412328)
    assert build.dot_gain(1.0, 2.5, spec.drag(37, 0.5)) == (0.13549762641654428, 0.6703200460356393)
    assert build.decode(Y14 + [0.3, -0.7])[21:].tolist() == [0.25, -0.75]
    assert np.array_equal(_bits(build.decode(Y14 + [0.3, -0.7])[:21]), _bits(THETA14))
    rng = np.random.default_rng(1)
    for _ in range(300):
        s, u, j = int(rng.integers(0, 2 ** 63)), int(rng.integers(0, 2 ** 63)) | 1, int(rng.integers(0, 10 ** 6))
        t, (dx, dy), x = float(rng.random() * 4096), rng.normal(0, 4, 2), rng.normal(0, 100, 2)
        assert build.receptor_next(s, u, j, t, 2.05) == spec.receptor_next(s, u, j, t, 2.05)
        assert build.halo(dx, dy, 1.5) == spec.halo(dx, dy, 1.5)
        assert build.blob_heading(s, j % 2, j, 0.1) == spec.blob_heading(s, j % 2, j, 0.1)
        assert build.blob_place(s, j % 2, j, *x, 2.0, 6.0) == spec.blob_place(s, j % 2, j, *x, 2.0, 6.0)
        assert build.dot_gain(t / 100, 2.5, 1.0 + t / 512) == spec.dot_gain(t / 100, 2.5, 1.0 + t / 512)
        y, row, g = rng.normal(0, 2, 23), rng.normal(0, 1, 875), rng.random(16)
        assert np.array_equal(_bits(build.decode(y)), _bits(V3.decode_knobs(y)))
        assert np.array_equal(_bits(build.readout(row, g)), _bits(V3.readout(row, g)))


def test_the_close_unfold_inverts_splitmix64():
    x = np.random.default_rng(2).integers(0, 2 ** 63, 200, dtype=np.uint64) * np.uint64(3)
    mixed = np.array([spec.splitmix64(int(v)) for v in x], dtype=np.uint64)
    assert np.array_equal(build._unmix(mixed), x)
    led = np.random.default_rng(3).normal(0, 9, (200, 57))
    h = x.copy()
    for c in range(35, 57):  # what the close of an ABI-3 life adds after ABI 2's 35 columns
        h = np.array([spec.splitmix64(int(a) ^ int(b)) for a, b in zip(h, led[:, c].view(np.uint64))], dtype=np.uint64)
    assert np.array_equal(build.unfold_close(h, led, 35), x)


def test_a_bell_life_through_the_abi3_kernel_is_abi2_bitwise():
    # spec.CURRENT's (ABI 2) view of a life against the raw ABI-3 outputs of the padded tables (LIFE_ABI.md 15.33);
    # the saved ABI-2 library agreed with both on 103 BELL cases (program and GRN mode, every lattice and scheduler)
    prog, gt = _program(), _genome()
    panel = spec.world(T=96.0, flags=PM, noise_rate=0.2, drop_p=0.1)
    for w, kw2, kw3 in ((panel, dict(programs=prog, init=HEX7),
                         dict(programs=V3.pad_program(prog, spec.V2), init=HEX7)),
                        (spec.world(T=96.0, lattice="square8"), dict(genomes=gt),
                         dict(genomes=V3.pad_genomes(gt, spec.V2)))):
        a = build.run(w, [3, 4, 5], raster_cap=4096, fate_cap=1024, **kw2)
        b = build.run(w, [3, 4, 5], raster_cap=4096, fate_cap=1024, abi=V3, **kw3)
        assert a.ledger.shape == (3, 35) and b.ledger.shape == (3, 57) and a.fate_i.shape[2] == 6
        assert np.array_equal(_bits(a.ledger), _bits(b.ledger[:, :35]))
        assert np.array_equal(a.hashes[:, 1:], b.hashes[:, 1:4])
        assert np.array_equal(a.hashes[:, 0], build.unfold_close(b.hashes[:, 0], b.ledger, 35))
        assert np.all(b.hashes[:, 4] == spec.HASH_INIT) and not b.ledger[:, 35:51].any()  # no world in BELL
        assert np.array_equal(_bits(b["live_S"]), _bits(b["live_time"])) and np.array_equal(b["n_S_end"], b["n_end"])
        assert np.array_equal(a.fate_i, b.fate_i[:, :, :6]) and not b.fate_i[:, :, 6].any()
        assert np.array_equal(_bits(a.raster_t), _bits(b.raster_t)) and b["births"].sum() > 0


def test_catch_lone_zygote_and_the_two_cell_clicker():
    w = _catch(T=1024.0)
    lone = _run3(w, range(64), programs=COLUMN, init=[(0, 0, 0, R3["juvenile"])], threads=4)
    assert not lone["clicks"].any() and not lone["nudges"].any() and not lone["path"].any()
    assert np.all(lone["F"] < -0.02) and np.all(lone["F"] > -0.0215)  # upkeep, its own spikes and receptor charges
    assert np.all(lone["samples"] == 1023) and np.all(lone["n_S_end"] == 1) and lone["rec_events"].min() > 0
    clicker = _run3(w, range(512), programs=COLUMN, init=_columns([(0, 0)]), threads=4)
    m, se = clicker["F"].mean(), clicker["F"].std(ddof=1) / np.sqrt(512)
    assert m > lone["F"].mean() + 4 * se and m > 0  # the first division already earns (prototype +0.045 +- 0.004)
    assert not clicker["nudges"].any() and not clicker["path"].any()  # one act cell: its exposed face is exactly 0
    deaf = _run3(replace(w, flags=CPM | V3.flags("contacts_off")), range(64), programs=COLUMN, init=_columns([(0, 0)]))
    assert not deaf["clicks"].any() and np.all(deaf["F"] < lone["F"].max())


def test_catch_ledger_identities_and_conservation():
    w = _catch(T=320.0)
    body = _run3(w, range(6), programs=COLUMN, init=_columns(_hexdisk(1), hidden=1), threads=2)
    grown = _run3(replace(w, flags=0, n_max=200), range(6), genomes=V3.pack_genomes(_grn3(3), "hexprism"), threads=2)
    late = _run3(replace(w, t_open=17.5), range(6), programs=COLUMN, init=_columns(_hexdisk(1)), threads=2)
    assert np.all(late["samples"] == w.T - 18)  # integer samples c >= t0 + t_open
    for res in (body, grown, late):
        assert not res.status("ledger_mismatch").any() and not res.status("capacity").any()
        assert np.array_equal(res["clicks"], res["captures"] + res["misses"] + res["b2_clicks"])
        assert np.array_equal(res["income"], w.R_cap * res["captures"])
        assert np.all(res["rec_cand"] >= res["rec_accept"]) and np.all(res["zone_samples"] <= res["samples"])
        assert np.array_equal(res["n_S_end"] + res["n_M_end"] + res["n_H_end"], res["n_end"])
        live = res["live_S"] + res["live_M"] + res["live_H"]
        assert np.allclose(live, res["live_time"], rtol=1e-12)
        assert np.all(_conservation_error(res) < 1e-12)
    for res in (body, grown):  # with t_open = 0 every delivered event was accepted, and F re-prices exactly
        assert np.all(res["rec_accept"] >= res["rec_events"]) and np.all(res["samples"] == w.T - 1)
        assert np.array_equal(_bits(V3.fitness(res.ledger, w)), _bits(res["F"]))
    assert np.array_equal(_bits(V3.fitness(late.ledger, replace(w, t_open=17.5))), _bits(late["F"]))
    assert np.all(body["n_H_end"] == 7) and body["captures"].sum() > 0 and body["nudges"].min() > 0
    assert grown["births"].sum() > 0 and grown["rec_events"].sum() > 0 and grown["n_M_end"].max() > 0


def test_catch_lives_agree_across_schedulers():
    cases = [(_catch(T=96.0), dict(programs=COLUMN, init=_columns(_hexdisk(1), hidden=1))),
             (_catch(T=96.0, flags=CPM | V3.flags("lockstep")), dict(programs=COLUMN, init=_columns(_hexdisk(1)))),
             (_catch(T=96.0, b2_amp=1.0, b2_value=100.0, b2_mode=1, t_resp=20.0),
              dict(programs=COLUMN, init=_columns(_hexdisk(1)))),
             (_catch("catch_v1_l2", T=96.0, flags=0, n_max=120), dict(genomes=V3.pack_genomes(_grn3(1), "hexprism"))),
             (_catch(T=96.0, flags=0), dict(genomes=V3.pack_genomes(_grn3(3), "hexprism")))]
    lives = [3, 5, 11]
    for w, kw in cases:
        ref_ = _run3(w, [[s, 0, 0, 0] for s in lives], raster_cap=8192, fate_cap=4096, **kw)
        assert ref_["rec_events"].sum() > 0 and ref_["births"].sum() + ref_["clicks"].sum() > 0
        runs = [_run3(w, [[s, tie, 0, 977 * tie] for s in lives], raster_cap=8192, fate_cap=4096, **kw)
                for tie in (1, 2)]
        runs += [_run3(replace(w, window_h=h), [[s, 0, o, 13 * o] for s in lives], raster_cap=8192, fate_cap=4096,
                       **kw) for h, o in ((0.5, 1), (0.125, 2))]
        runs.append(_run3(w, lives, threads=3, raster_cap=8192, fate_cap=4096, **kw))
        assert all(_same3(ref_, r) for r in runs), w
        assert np.any(ref_.hashes[:, 4] != spec.HASH_INIT)


def test_catch_forks():
    body = _columns(_hexdisk(1))
    base = _catch(T=320.0, t_fork=160.0, t_open=168.0)  # spikes and receptor events sent before t_fork land by +8

    def fork(*names, **kw):
        w = replace(base, fork_flags=V3.flags(*names) if names else 0)
        return _run3(w, range(6), programs=kw.pop("programs", COLUMN), init=kw.pop("init", body), threads=2)

    intact = fork()
    assert intact["arrivals"].min() > 0 and intact["nudges"].min() > 0 and intact["rec_events"].min() > 0
    assert _same3(intact, _run3(replace(base, t_fork=20.0), range(6), programs=COLUMN, init=body, threads=2))
    deaf = fork("contacts_off")
    assert not deaf["arrivals"].any() and not deaf["clicks"].any() and deaf["contact_events"].min() > 0
    still = fork("motor_off")  # twitches charged, no world effect
    assert not still["nudges"].any() and not still["clicks"].any() and still["kappa_sum"].min() > 0
    numb = fork("receptor_off")  # the world still thins candidates; nothing reaches a cell
    assert not numb["rec_events"].any() and not numb["rec_gain"].any() and numb["rec_accept"].min() > 0
    assert np.array_equal(numb["rec_cand"], intact["rec_cand"])
    pair = [(0, 0, 0, R3["alone"]), (1, 0, 0, R3["alone"])]  # in-plane messages only
    assert fork(init=pair)["arrivals"].min() > 0 and not fork("lateral_off", init=pair)["arrivals"].any()
    column = _columns([(0, 0)])  # vertical messages only: lateral_off changes nothing
    assert _same3(fork(init=column), fork("lateral_off", init=column))
    # a firing hidden cell on top of a deaf column: hidden_off silences its deliveries, not its charges
    talker = V3.pack_program(MOTOR, alone=QUIET, juvenile=_th(b=1.25, tau_m=2, t_ref=2, emit0=1))
    stack = [(0, 0, 0, R3["alone"]), (0, 0, 1, R3["contact"]), (0, 0, 2, R3["juvenile"])]
    loud, mute = fork(init=stack, programs=talker), fork("hidden_off", init=stack, programs=talker)
    assert loud["arrivals"].min() > 0 and loud["clicks"].min() > 0
    assert not mute["arrivals"].any() and not mute["clicks"].any()
    assert np.array_equal(mute["contact_events"], loud["contact_events"])


def test_catch_body_physics():
    w = _catch(T=256.0)
    def run(init, w=w, programs=COLUMN):
        return _run3(w, range(4), programs=programs, init=init)

    # an island act cell has no exposed face and never pulls; an act plane without a footprint has no traction
    island = run(_columns([(0, 0)]) + [(3, 0, 0, R3["alone"]), (3, 0, 1, R3["contact"])])
    assert not island["nudges"].any() and not island["path"].any() and island["rec_events"].min() > 0
    tonic = V3.pack_program(_th(b=2.0, tau_m=1, t_ref=0.5, kappa=1), juvenile=_th(b=1.1, tau_m=4, t_ref=1, kappa=1))
    ring = [(a, b, 1, R3["contact"]) for a, b in _hexdisk(1) if (a, b) != (0, 0)]
    footless = run(ring, programs=tonic)
    assert footless["nudges"].min() > 0 and not footless["path"].any() and not footless["X_end"].any()
    # the key: a tonic hotspot holds it down and clicks once; a slow one releases below th_rel and clicks every spike
    held = run([(0, 0, 1, R3["contact"])], programs=tonic)
    slow = run([(0, 0, 1, R3["juvenile"])], programs=tonic)
    assert np.all(held["clicks"] == 1) and held["spikes"].min() > 100
    assert np.array_equal(slow["clicks"], slow["spikes"]) and slow["spikes"].min() > 5
    # silent hidden cells change nothing in the world and cost exactly their upkeep
    plain, stacked = run(_columns(_hexdisk(1))), run(_columns(_hexdisk(1), hidden=2))
    assert np.array_equal(plain.hashes[:, 4], stacked.hashes[:, 4])  # the world hash
    assert np.array_equal(plain.hashes[:, 1], stacked.hashes[:, 1])  # the spikes hash
    assert np.allclose(plain["F"] - stacked["F"], w.c_live * 14, rtol=0, atol=1e-12)
    assert np.allclose(stacked["live_H"], 14 * w.T, rtol=1e-12) and plain["captures"].sum() > 0
    # g_r = 0: no receptor at all (no trace, no input, no charge), while the world still thins its candidates
    blind = run([(0, 0, 0, R3["rim"]), (0, 0, 1, R3["contact"])])
    assert not blind["rec_events"].any() and blind["rec_accept"].min() > 0 and not blind["spikes"].any()
    # extinction does not stop the world: the target keeps moving and re-placing, and the samples go on
    dying = run([(0, 0, 0, R3["alone"])], programs=V3.pack_program(_th(p_die=1.0), alone=_th(g_r=1.0, p_die=1.0)),
                w=replace(w, t_resp=10.0))
    assert dying.status("extinct").all() and np.all(dying["samples"] == 255) and dying["respawns"].min() > 5


def test_catch_guard_trip_ends_the_timeline():
    w = _catch(T=256.0, flags=0, n_max=40)
    res = _run3(w, range(3), genomes=V3.pack_genomes(_grn3(1), "hexprism"))
    assert res.status("guard_cells").all()
    t_end = res["t_end"]
    assert np.all(t_end == np.floor(t_end)) and np.all(t_end < w.T) and np.array_equal(res["samples"], t_end - 1)
    assert np.allclose(res["guard_charge"], w.c_live * w.n_max * (w.T - t_end))


def test_catch_lives_do_not_depend_on_their_batch():
    gt = V3.pack_genomes(np.stack([_grn3(3), _grn3(4)]), "hexprism")
    bell = spec.world(lattice="hexprism", L_max=3, T=64.0)
    cw, cg = _catch(T=64.0), _catch(T=64.0, flags=0)
    worlds = [cw, bell, cg, cw]
    mixed = _run3(worlds, [5, 6, 7, 8], genomes=gt, programs=COLUMN, genome_of=[0, 1, 0, 0],
                  init=[_columns(_hexdisk(1)), [(0, 0)], [(0, 0)], _columns([(0, 0)])], threads=2)
    alone = [_run3(cw, [5], programs=COLUMN, init=_columns(_hexdisk(1))),
             _run3(bell, [6], genomes=gt[1:]), _run3(cg, [7], genomes=gt[:1]),
             _run3(cw, [8], programs=COLUMN, init=_columns([(0, 0)]))]
    for i, one in enumerate(alone):
        assert np.array_equal(_bits(mixed.ledger[i]), _bits(one.ledger[0]))
        assert np.array_equal(mixed.hashes[i], one.hashes[0])
    assert mixed.hashes[1, 4] == spec.HASH_INIT and mixed["n_H_end"][1] + mixed["n_M_end"][1] > 0  # BELL in 3D grows


# ABI-3 world values that spec.V3.validate_world refuses: the kernel answers -2 (LIFE_ABI.md 4.7)
INVALID_ABI3_VALUES = [
    dict(world_kind=2), dict(world_kind=0.5), dict(L_max=0), dict(L_max=9), dict(L_max=2.5), dict(stuck_z=4),
    dict(stuck_z=-1), dict(sigma=0.0), dict(b2_sigma=-1.0), dict(sigma=2.0 ** 21), dict(lam_s=-1.0),
    dict(lam_bg=-0.1), dict(b2_amp=-0.5), dict(lam_s=1024.0), dict(g_n=-1.0), dict(g_n=2048.0), dict(v_t=-0.1),
    dict(drag_exp=-0.1), dict(drag_exp=2.5), dict(th_click=0.2), dict(th_rel=-0.1), dict(th_click=1.5),
    dict(rho_c=-1.0), dict(R_min=7.0), dict(R_max=2.0 ** 21), dict(tau_turn=-1.0), dict(t_resp=-1.0),
    dict(t_resp=1e-20), dict(tau_turn=2.0 ** -11), dict(t_resp=1e-5),
    dict(R_cap=-1.0), dict(c_miss=-1.0), dict(c_rec=-0.1), dict(b2_p=1.5), dict(b2_mode=2), dict(sigma=float("nan")),
    dict(b2_value=float("inf")), dict(flags=float(1 << 15)), dict(fork_flags=float(spec.V3.flags("program_mode"))),
]
EDGE_ABI3_VALUES = [
    dict(tau_turn=0.0, t_resp=0.0), dict(tau_turn=2.0 ** -10, t_resp=2.0 ** -10), dict(v_t=0.0), dict(L_max=1),
    dict(L_max=8, stuck_z=7), dict(drag_exp=0.0),
    dict(th_rel=0.0, th_click=1.0), dict(rho_c=0.0, R_min=6.0), dict(lam_s=0.0, lam_bg=0.0), dict(b2_value=-25.0),
    dict(b2_amp=1.0, b2_sigma=1.6, b2_p=0.0, b2_mode=1), dict(lam_bg=0.0, lam_s=512.0, b2_amp=1.0), dict(world_kind=0),
    dict(fork_flags=float(spec.V3.flags("lateral_off", "hidden_off", "receptor_off", "motor_off")), t_fork=4.0),
]


@pytest.mark.parametrize("bad", INVALID_ABI3_VALUES, ids=str)
def test_every_invalid_abi3_world_is_refused_by_the_kernel_and_by_spec(bad):
    assert _call({"_preset": "catch_v1", **bad}, kind="hexprism") == -2
    with pytest.raises(ValueError):
        V3.pack_world(spec.world("catch_v1", **{k: (int(v) if k.endswith("flags") else v) for k, v in bad.items()}))


@pytest.mark.parametrize("ok", EDGE_ABI3_VALUES, ids=str)
def test_the_edges_of_the_abi3_world_ranges_run(ok):
    assert _call({"_preset": "catch_v1", **ok}, kind="hexprism") == 0
    V3.pack_world(spec.world("catch_v1", **{k: (int(v) if k.endswith("flags") else v) for k, v in ok.items()}))


def test_invalid_3d_bodies_and_lattices_are_rejected():
    def body(*cells):
        b = np.zeros((1, KV3.MAX_INIT, KV3.INIT_COLS), dtype=np.int32)
        b[0, :len(cells)] = cells
        return dict(n_init=np.array([len(cells)], dtype=np.int32), init=b)

    catch = {"_preset": "catch_v1"}  # L_max 4
    assert _call(catch, kind="hexprism", **body((0, 0, 0, 0), (0, 0, 1, 1), (0, 0, 3, 2))) == 0
    assert _call(catch, kind="hexprism", **body((0, 0, 0, 0), (0, 0, 4, 1))) == -4  # outside the stack
    assert _call(kind="hexprism", **body((0, 0, 1, 0))) == -4  # BELL default: L_max 1
    assert _call(catch, kind="hexprism", **body((0, 0, 1, 0), (0, 0, 1, 1))) == -4  # two cells on one site
    assert _call(catch, kind="hexprism", **body((2 ** 22, -2 ** 22, 0, 0))) == 0
    assert _call(catch, kind="hexprism", **body((2 ** 22 + 1, 0, 0, 0))) == -4  # beyond the key bound
    assert _call(catch, kind="hexprism", **body((0, 0, -1, 0))) == -4
    assert _call(catch, kind="square8prism", **body(*[(a, 0, z, 0) for a in range(300) for z in range(3)])) == 0
    assert build.run(spec.world(T=8.0, flags=PM), [0], programs=_program(), init=[(0, 0, 1)])["n_end"][0] == 1
    with pytest.raises(ValueError):  # ABI 2 (spec.CURRENT) refuses a CATCH world
        build.run(spec.world("catch_v1", flags=PM), [0], programs=_program())
    lat = KV3.lattice_tables("hexprism")[0]
    D = 8
    for idx, val in ((2 + 2 * D + 6, 0), (2 + 2 * D + 0, 1), (2 + 3 * D + 6, 6), (2 + 6 * D + 1, 8), (1, 6), (0, 6)):
        bad = lat.copy()
        bad[idx] = val
        assert _call(catch, lat=bad, kind="hexprism") == -4, (idx, val)


def _both(world=(), *, lat=None, cells=None, n_init=None, flags: int = CPM, genomes=None, programs=COLUMN,
          kind: str = "hexprism") -> tuple[int, int]:
    """The return codes of the kernel (raw ctypes) and of the reference's ``life_run`` on the same ABI-3 arrays;
    ``cells`` are initial rows (a, b, z, row), and ``n_init`` overrides their count (with ``cells`` None: no array)."""
    init = None
    if cells is not None:
        init = np.zeros((1, KV3.MAX_INIT, KV3.INIT_COLS), dtype=np.int32)
        init[0, :len(cells)] = cells
    n = np.array([len(cells) if n_init is None else n_init], dtype=np.int32) if cells is not None or n_init else None
    k = _call(world, lat=lat, n_init=n, init=init, flags=flags, genomes=genomes, programs=programs, kind=kind)
    lat_k, unit = KV3.lattice_tables(kind)
    r = ref.life_run(lat_k if lat is None else lat, unit, genomes, programs, [0], init, n,
                     _vector(world, flags, KV3), np.zeros((1, 4), dtype=np.uint64), abi=V3)["rc"]
    return k, r


def test_the_kernel_and_the_reference_refuse_the_same_arguments():
    # LIFE_ABI.md 4.2, 4.3, 4.6 and 15.57: every argument error gets the same code from both implementations, also
    # when one call breaks several rules
    catch, gt = {"_preset": "catch_v1"}, V3.pack_genomes(_grn3(3), "hexprism")
    ring2 = [(a, b, z, 0) for a, b in _hexdisk(2) for z in (0, 1)]
    nan = COLUMN.copy()
    nan[R3["contact"] * V3.P + V3.K["tau_m"]] = np.nan
    zero = KV3.lattice_tables("hexprism")[0].copy()
    zero[2 + 0] = zero[2 + 3] = 0  # slots 0 and 3 both point at their own site; back[] still points back
    cases = [
        (dict(world=catch), 0),
        (dict(world=catch, cells=ring2), 0),
        (dict(world={**catch, "fabric_R": 1.0}, cells=ring2), -4),  # a cell on a wall of the dense disk
        (dict(world={**catch, "fabric_R": 2.0}, cells=ring2), 0),
        (dict(world=catch, cells=[(0, 0, 0, 7)], flags=0, genomes=gt, programs=None), 0),  # GRN mode ignores rows
        (dict(world=catch, cells=[(0, 0, 0, 5)]), -4), (dict(world=catch, cells=[(0, 0, 0, -2)]), -4),
        (dict(world=catch, lat=zero), -4),
        (dict(world=catch, n_init=1), -1),  # initial cells announced, no array
        (dict(world=catch, n_init=KV3.MAX_INIT + 1), -4),
        (dict(world=catch, n_init=KV3.MAX_INIT + 1, programs=nan), -1),  # the table row is checked first
        (dict(world={**catch, "T": 8.5}, lat=zero), -4),  # the lattice table before the world
        (dict(world={**catch, "T": 8.5}, programs=nan), -2),  # the world before the table row
        (dict(world=catch, cells=[(2 ** 22 + 1, 0, 0, 0)]), -4), (dict(world=catch, cells=[(0, 0, 4, 0)]), -4),
        (dict(world=catch, cells=[(1, 1, 1, 0), (1, 1, 1, 2)]), -4),
        (dict(world=catch, cells=[(0, 0, 0, 0)], flags=0, genomes=None, programs=None), -1),
    ]
    for kw, want in cases:
        assert _both(**kw) == (want, want), (kw.get("world"), want, _both(**kw))
    # the ABI-2 boundary pads bodies into ABI 3, so the key bound and the wall rule hold there too
    w2 = spec.world(T=8.0, flags=PM)
    for w, body in ((w2, [(2 ** 22 + 1, 0)]), (replace(w2, fabric_R=1), [(0, 0), (2, 0)])):
        with pytest.raises(ValueError, match="-4"):
            build.run(w, [0], programs=_program(), init=body)
        with pytest.raises(ref.ArgError) as err:
            ref.run(w, program=_program(), cells=body, abi=spec.V2)
        assert err.value.rc == -4


# the prototype's column ladder in CATCH-T (BODY_DESIGN_PROPOSAL.md 3.2: F and SE per ring, crit's fresh lives)
PROTOTYPE_RINGS = {0: (0.045, 0.004), 1: (1.040, 0.022), 2: (2.891, 0.050), 3: (3.907, 0.051), 4: (3.489, 0.037)}


@pytest.mark.slow
def test_catch_column_ladder_reproduces_the_prototype_curve():
    # gates GB3, GB4 and GB6 in program mode: the lone zygote is below the 2-cell clicker, the ring curve rises to an
    # interior optimum with F* > 20x the clicker, contacts-off leaves every ring at its costs, and each ring is within
    # 4 SE of the independent prototype (which had no Q10 membrane, no c_rec and instant contact views), compared at
    # the prototype's miss price c_miss 1 (the world's is 2, LIFE_ABI.md 15.60; a price never changes a life)
    w = _catch("catch_v1_l2", T=1024.0)
    seeds = [7_000_000 + s for s in range(512)]
    lone = _run3(w, seeds, programs=COLUMN, init=[(0, 0, 0, R3["juvenile"])], threads=4)["F"]
    F, SE = {}, {}
    for k, (f_proto, se_proto) in PROTOTYPE_RINGS.items():
        n = 512 if k == 0 else 128
        res = _run3(w, seeds[:n], programs=COLUMN, init=_columns(_hexdisk(k)), threads=4)
        off = _run3(replace(w, flags=CPM | V3.flags("contacts_off")), seeds[:n], programs=COLUMN,
                    init=_columns(_hexdisk(k)), threads=4)
        F[k], SE[k] = res["F"].mean(), res["F"].std(ddof=1) / np.sqrt(n)
        assert not off["income"].any() and off["F"].mean() < lone.mean()
        Fp = V3.fitness(res.ledger, replace(w, c_miss=1.0))
        assert abs(Fp.mean() - f_proto) < 4 * np.hypot(SE[k], se_proto), (k, Fp.mean(), SE[k], f_proto)
        assert not res.status("ledger_mismatch").any() and not res.status("guard_cells").any()
    assert lone.mean() < F[0] - 2 * SE[0]
    assert F[0] < F[1] < F[2] < F[3] and F[4] < F[3] and F[3] > 20 * F[0]
