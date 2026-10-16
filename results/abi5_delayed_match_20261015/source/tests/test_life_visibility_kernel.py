"""ABI4 C boundary tests and whole-life checks; no controller or task-performance gate.

The included-C fixture exposes world operations only to force exact ties that almost surely never occur in a
random life. Its build directory stays inside the configured kernel cache, under outputs for this study.
"""
import ctypes
import math
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.life import build, spec
from tests.life_helpers import CLICKER3, COLUMN3, QUIET3, columns, hexdisk

V4 = spec.V4
F64P = ctypes.POINTER(ctypes.c_double)
U64P = ctypes.POINTER(ctypes.c_uint64)


@pytest.fixture(scope="module")
def world_c():
    cache = Path(os.environ.get("CELL_DEV_CACHE", Path(__file__).resolve().parents[1] / "outputs/visibility-tests"))
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="world-fixture-", dir=cache) as directory:
        directory = Path(directory)
        source = directory / "world_fixture.c"
        source.write_text('#include "' + str(build.SRC.resolve()) + '"\n' + r'''
void *vis_new(int mode, double on, double off, double low, double t0, uint64_t seed) {
  Ctx *c = calloc(1, sizeof(Ctx));
  c->kind = WK_CATCH; c->n = 1; c->seed = seed; c->t0 = t0; c->t_open_abs = t0 + 10.0;
  c->visibility_mode = mode; c->visibility_on = on; c->visibility_off = off; c->visibility_low = low;
  c->tau_z = 8.0; c->rho_c = 1.0; c->R_cap = 500.0;
  for (int i = 0; i < HASH_SIZE; i++) c->H[i] = HASH_INIT;
  catch_start(c);
  return c;
}
void vis_free(void *p) { free(p); }
void vis_to(void *p, double t) { world_to(p, t); }
void vis_place(void *p, double t) { place(p, 0, PL_TIMER, t); }
void vis_clocks(void *p, double timer, double turn) {
  Ctx *c = p; c->blob[0].r = timer; c->blob[0].tau = turn; c->t_resp = 50.0; c->tau_turn = 20.0;
}
void vis_click(void *p, double t) {
  Ctx *c = p; world_to(c, t); catch_click(c, t); group_end(c, t);
}
void vis_read(void *p, double *v, uint64_t *h) {
  Ctx *c = p;
  v[0] = c->bright; v[1] = c->visibility_next; v[2] = (double)c->visibility_k;
  v[3] = (double)c->low_light_captures; v[4] = (double)c->captures;
  v[5] = (double)c->respawns; v[6] = (double)c->blob[0].q; v[7] = c->income;
  h[0] = c->H[H_WORLD]; h[1] = c->H[H_ALL];
}
int vis_world_ok(const double *w) { return world_ok(w); }
''')
        library = directory / "world_fixture.so"
        subprocess.run(["gcc", *build.CFLAGS, "-o", str(library), str(source), "-lm"], check=True,
                       capture_output=True, env=dict(os.environ, TMPDIR=str(directory)))
        lib = ctypes.CDLL(str(library))
        lib.vis_new.argtypes = [ctypes.c_int, *([ctypes.c_double] * 4), ctypes.c_uint64]
        lib.vis_new.restype = ctypes.c_void_p
        for name in ("vis_to", "vis_place", "vis_click"):
            fn = getattr(lib, name)
            fn.argtypes = [ctypes.c_void_p, ctypes.c_double]
            fn.restype = None
        lib.vis_clocks.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_double]
        lib.vis_clocks.restype = None
        lib.vis_free.argtypes = [ctypes.c_void_p]
        lib.vis_free.restype = None
        lib.vis_read.argtypes = [ctypes.c_void_p, F64P, U64P]
        lib.vis_read.restype = None
        lib.vis_world_ok.argtypes = [F64P]
        lib.vis_world_ok.restype = ctypes.c_int
        yield lib


@pytest.fixture
def state(world_c):
    allocated = []

    def create(mode=1, on=5.0, off=0.0, low=0.25, t0=17.0, seed=42):
        p = world_c.vis_new(mode, on, off, low, t0, seed)
        assert p
        allocated.append(p)
        return p

    yield create
    for p in allocated:
        world_c.vis_free(p)


def read(lib, p):
    v, h = np.zeros(8), np.zeros(2, dtype=np.uint64)
    lib.vis_read(p, v.ctypes.data_as(F64P), h.ctypes.data_as(U64P))
    return v, h


def folded(h, words):
    for word in words:
        h = spec.splitmix64(int(h) ^ int(word))
    return h


def bits(value):
    return np.float64(value).view(np.uint64).item()


def test_flash_initial_deadline_is_strict_before_and_transition_hash_is_exact(world_c, state):
    p = state()
    initial, old_hash = read(world_c, p)
    assert initial[:3].tolist() == [1, 22, 0]
    world_c.vis_to(p, 22)
    assert np.array_equal(read(world_c, p)[0], initial)
    assert np.array_equal(read(world_c, p)[1], old_hash)
    world_c.vis_to(p, math.nextafter(22, math.inf))
    after, new_hash = read(world_c, p)
    assert after[:3].tolist() == [0, math.inf, 0]
    expected = [folded(h, [14, bits(22), 0, 0]) for h in old_hash]
    assert new_hash.tolist() == expected
    world_c.vis_to(p, 1000)
    assert np.array_equal(read(world_c, p)[1], new_hash)


@pytest.mark.parametrize("placement", [20.0, 22.0, 25.0])
def test_flash_placement_replaces_deadline_and_restores_brightness(world_c, state, placement):
    p = state()
    world_c.vis_to(p, placement)
    world_c.vis_place(p, placement)
    values, before = read(world_c, p)
    assert values[:3].tolist() == [1, placement + 5, 0]
    world_c.vis_to(p, placement + 5)
    assert np.array_equal(read(world_c, p)[1], before)
    world_c.vis_to(p, math.nextafter(placement + 5, math.inf))
    assert read(world_c, p)[0][0] == 0


def test_timer_then_turn_wins_flash_deadline_tie(world_c, state):
    p = state()
    before = read(world_c, p)[1]
    world_c.vis_clocks(p, 22, 22)
    world_c.vis_to(p, math.nextafter(22, math.inf))
    values, hashes = read(world_c, p)
    assert values[:3].tolist() == [1, 27, 0]
    # Zero placement radius and target speed make both ordinary event records known independently.
    vx, vy = spec.blob_heading(42, 0, 1, 0.0)  # retain the signs of the zero velocities
    records = [12, bits(22), 0, 2, bits(0), bits(0), 1, 13, bits(22), 0, bits(vx), bits(vy)]
    assert hashes.tolist() == [folded(h, records) for h in before]


def test_renewal_intervals_use_stream26_and_continue_across_placement(world_c, state):
    p = state(mode=2, on=20, off=10, low=0)
    first = spec.poisson_next(42, 26, 0, 0, 17.0, 20.0)
    assert read(world_c, p)[0][:3].tolist() == [1, first, 1]
    world_c.vis_place(p, 18)
    assert read(world_c, p)[0][:3].tolist() == [1, first, 1]
    world_c.vis_to(p, first)
    assert read(world_c, p)[0][0] == 1
    world_c.vis_to(p, math.nextafter(first, math.inf))
    second = spec.poisson_next(42, 26, 0, 1, first, 10.0)
    assert read(world_c, p)[0][:3].tolist() == [0, second, 2]
    world_c.vis_place(p, math.nextafter(first, math.inf))
    assert read(world_c, p)[0][:3].tolist() == [0, second, 2]
    world_c.vis_to(p, math.nextafter(second, math.inf))
    third = spec.poisson_next(42, 26, 0, 2, second, 20.0)
    assert read(world_c, p)[0][:3].tolist() == [1, third, 3]


def test_capture_counter_uses_counted_preplacement_state(world_c, state):
    p = state()
    world_c.vis_click(p, 25)  # dark, but before t_open = 27
    assert read(world_c, p)[0][3:5].tolist() == [0, 0]
    world_c.vis_click(p, 30)  # exactly the new deadline: still bright at the left limit
    assert read(world_c, p)[0][3:5].tolist() == [0, 1]
    world_c.vis_click(p, 36)  # counted dark capture, then the deferred placement restores brightness
    values = read(world_c, p)[0]
    assert values[:5].tolist() == [1, 41, 0, 1, 2]
    assert values[7] == 1000


def test_disabled_visibility_adds_no_world_events_or_draws(world_c, state):
    p = state(mode=0, on=0, low=1)
    initial, before = read(world_c, p)
    world_c.vis_to(p, 10000)
    after, hashes = read(world_c, p)
    assert after[:3].tolist() == [1, math.inf, 0]
    assert np.array_equal(initial, after) and np.array_equal(before, hashes)


@pytest.mark.parametrize("changes", [
    {"visibility_mode": 0.5}, {"visibility_mode": 3}, {"visibility_mode": -1},
    {"visibility_mode": 0, "visibility_on": 1}, {"visibility_mode": 0, "visibility_off": 1},
    {"visibility_mode": 0, "visibility_low": 0}, {"visibility_low": -0.01}, {"visibility_low": 1.01},
    {"visibility_mode": 1, "visibility_on": 0}, {"visibility_mode": 1, "visibility_on": spec.STEP_MIN / 2},
    {"visibility_mode": 1, "visibility_on": spec.TIME_MAX * 2}, {"visibility_mode": 1, "visibility_off": 1},
    {"visibility_mode": 2, "visibility_off": 0}, {"visibility_mode": 2, "visibility_off": spec.STEP_MIN / 2},
    {"visibility_mode": 1, "b2_amp": 1}, {"visibility_mode": 1, "world_kind": 0},
    {"visibility_mode": 1, "visibility_low": math.nan}, {"visibility_mode": 1, "visibility_on": math.inf},
])
def test_kernel_rejects_invalid_visibility_vectors_without_python_validation(world_c, changes):
    # This fixture calls the current C kernel directly, bypassing the caller-ABI padding in build.run.
    world = build.KERNEL.pack_world(spec.world("catch_speck_flash5_dim25_l4", T=32, t_open=0))
    for key, value in changes.items():
        world[V4.WORLD_INDEX[key]] = value
    assert world_c.vis_world_ok(world.ctypes.data_as(F64P)) == 0


@pytest.mark.parametrize("preset", ["catch_speck_flash5_dim25_l4", "catch_speck_blink20_20_l4"])
def test_visibility_whole_lives_are_repeatable_and_fast_full_identical(preset):
    w = spec.world(preset, T=64, t_open=0, flags=V4.flags("program_mode"), R_min=0, R_max=0, v_t=0)
    kwargs = dict(programs=V4.pack_program(CLICKER3), init=[(0, 0, 0), (0, 0, 1)], threads=1, abi=V4,
                  raster_cap=500, fate_cap=20)
    full = build.run(w, [41, 42], **kwargs)
    again = build.run(w, [41, 42], **kwargs)
    fast = build.run(w, [41, 42], fast=True, **kwargs)
    assert np.array_equal(full.hashes, again.hashes)
    for other in (again, fast):
        for field in ("ledger", "raster_t", "raster_uid", "raster_n", "fate_i", "fate_f", "fate_n"):
            left, right = getattr(full, field), getattr(other, field)
            assert np.array_equal(left.view(np.uint8), right.view(np.uint8)), field
    assert (fast.hashes == spec.HASH_INIT).all()
    assert (full["status"] == 0).all()
    assert (full["low_light_captures"] <= full["captures"]).all()


@pytest.mark.parametrize("mode,on,off", [(1, 5, 0), (2, 20, 20)])
def test_low_multiplier_one_preserves_all_legacy_physical_columns(mode, on, off):
    neutral = spec.world("catch_speck_l4", T=32, t_open=0, flags=V4.flags("program_mode"))
    from dataclasses import replace
    visibility = replace(neutral, visibility_mode=mode, visibility_on=on, visibility_off=off)
    kwargs = dict(programs=V4.pack_program(CLICKER3), init=[(0, 0, 0), (0, 0, 1)], threads=1, abi=V4)
    baseline = build.run(neutral, [42], **kwargs)
    result = build.run(visibility, [42], **kwargs)
    assert np.array_equal(baseline.ledger[:, :57].view(np.uint64), result.ledger[:, :57].view(np.uint64))
    assert not np.array_equal(baseline.hashes[:, [0, 4]], result.hashes[:, [0, 4]])


def test_complete_darkness_removes_target_pings_but_keeps_background():
    from dataclasses import replace
    # No actions or timer replacements: every target candidate after t8 occurs in the low-light phase.
    neutral = spec.world("catch_speck_l4", T=16, t_open=8, flags=V4.flags("program_mode"),
                         lam_s=64, lam_bg=0, t_resp=0, v_t=0, R_min=0, R_max=0)
    dark = replace(neutral, visibility_mode=1, visibility_on=5, visibility_low=0)
    background = replace(dark, lam_bg=4)
    kwargs = dict(programs=V4.pack_program(QUIET3), threads=1, abi=V4)
    result = build.run([neutral, dark, background], [42, 42, 42], **kwargs)
    assert result["rec_accept"][0] > 0
    assert result["rec_accept"][1] == result["rec_events"][1] == 0
    assert result["rec_accept"][2] > 0
    assert (result["rec_cand"] > 0).all() and (result["status"] == 0).all()


@pytest.mark.parametrize("preset", ["catch_speck_flash5_dim25_l4", "catch_speck_blink20_20_l4"])
def test_visibility_is_bitwise_equal_across_threads_and_schedulers(preset):
    from dataclasses import replace
    w = spec.world(preset, T=96, t_open=0, flags=V4.flags("program_mode"))
    kwargs = dict(programs=COLUMN3, init=columns(hexdisk(1), hidden=1), abi=V4,
                  raster_cap=8192, fate_cap=512)
    baseline = build.run(w, [41, 42], threads=1, **kwargs)
    # Reuse the existing column fixture; only execution scheduling changes.
    for window_h, fast in ((0, False), (0.25, False), (0.25, True)):
        other = build.run(replace(w, window_h=window_h), [41, 42], threads=2, fast=fast, **kwargs)
        for field in ("ledger", "raster_t", "raster_uid", "raster_n", "fate_i", "fate_f", "fate_n"):
            left, right = getattr(baseline, field), getattr(other, field)
            assert np.array_equal(left.view(np.uint8), right.view(np.uint8)), (window_h, fast, field)
        if fast:
            assert (other.hashes == spec.HASH_INIT).all()
        else:
            assert np.array_equal(baseline.hashes, other.hashes), window_h
    assert (baseline["status"] == 0).all()
    assert (baseline["rec_events"] > 0).all() and (baseline["contact_events"] > 0).all()
