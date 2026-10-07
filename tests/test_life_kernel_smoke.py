"""Smoke tests of the one-life C kernel (src/life/kernel.c through src/life/build.py): it builds, its test exports
match spec.py bitwise, a lone cell pumps, and small bodies agree bitwise across schedulers (LIFE_ABI.md 11)."""
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
    assert lib.life_abi_version() == spec.ABI_VERSION and build.library_path().exists()
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


def _vector(world=(), flags: int = PM) -> np.ndarray:
    """A one-life world vector patched entry by entry, bypassing spec.pack_world's validation."""
    wv = spec.pack_world(spec.world(T=8.0, flags=flags))[None].copy()
    for k, v in dict(world).items():
        wv[0, spec.WORLD_INDEX[k]] = v
    return wv


def _call(world=(), *, lat=None, n_init=None, init=None, flags: int = PM, genomes=None, programs=_program(),
          genome_of: int = 0) -> int:
    """life_run on one life straight through ctypes (no build.run checks); returns its code."""
    lat_hex, unit = spec.lattice_tables("hex")
    lat = lat_hex if lat is None else lat
    gt, pg = (None if t is None else np.ascontiguousarray(np.atleast_2d(t), dtype=np.float64) for t in (genomes, programs))
    P = build._ptr
    wv = _vector(world, flags)
    led, hs = np.zeros((1, spec.LEDGER_SIZE)), np.zeros((1, spec.HASH_SIZE), dtype=np.uint64)
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
    body = np.zeros((1, spec.MAX_INIT, 3), dtype=np.int32)
    assert _call(n_init=np.array([2], dtype=np.int32), init=body) == -4  # two cells on one site
    bad = spec.lattice_tables("hex")[0].copy()
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
