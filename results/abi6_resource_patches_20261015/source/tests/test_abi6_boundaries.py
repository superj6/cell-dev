"""Direct ABI6 world operations: no advanced cell lives or behavioral admission gate.

One included-C shared-library fixture compiles only when executed. Tests force source
times and physical stocks to expose ordering, accounting and corruption boundaries.
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

F64P = ctypes.POINTER(ctypes.c_double)
U64P = ctypes.POINTER(ctypes.c_uint64)
PC_NAMES = ("open", "source", "supply", "spill", "harvest", "empty", "end", "initial", "refill")
BASE_NAMES = ("clicks", "captures", "misses", "income", "cost", "status", "geometric", "opened",
              "samples", "zone", "dist_sum", "b2_clicks", "respawns", "low_light_captures")
SLOT_NAMES = ("x", "y", "period", "first", "next", "index", "stock", "left", "initial_left", "initial_open")
STATE_NAMES = BASE_NAMES + tuple(f"{name}_{i}" for i in range(4) for name in SLOT_NAMES) + tuple(
    f"{name}_{i}" for name in PC_NAMES for i in range(4))


@pytest.fixture(scope="module")
def patch_c():
    cache = Path(os.environ.get("CELL_DEV_CACHE", Path(__file__).resolve().parents[1] / "outputs/abi6-tests"))
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="patch-fixture-", dir=cache) as directory:
        directory = Path(directory)
        source = directory / "patch_fixture.c"
        source.write_text('#include "' + str(build.SRC.resolve()) + '"\n' + r'''
void *rp_new(int count, int capacity, double open, double t0, uint64_t seed) {
  Ctx *c = calloc(1, sizeof(Ctx));
  c->kind = WK_CATCH; c->n = 1; c->seed = seed; c->t0 = t0; c->t_open_abs = t0 + open;
  c->patch_count = count; c->patch_capacity = capacity;
  c->patch_fast = 80.0; c->patch_slow = 160.0; c->patch_landmark = 0.1;
  c->tau_z = 2.5; c->rho_c = 1.0; c->R_cap = 500.0; c->c_miss = 10.0;
  c->sigma = 0.6; c->lam_bg = 0.05; c->lam_s = 2.0; c->lam_max = 0.05 + 2.0 * count;
  c->R_min = 2.0; c->R_max = 4.0;
  for (int i = 0; i < HASH_SIZE; i++) c->H[i] = HASH_INIT;
  catch_start(c);
  return c;
}
void rp_free(void *p) { free(p); }
void rp_slot(void *p, int i, double x, double y, int stock, int initial,
             double first, double period, uint64_t index) {
  Ctx *c = p; Patch *v = &c->patch[i];
  v->x = x; v->y = y; v->stock = stock; v->initial_remaining = initial;
  v->first = first; v->period = period; v->arrival_index = index;
  v->next = first + (double)index * period; c->patch_left[i] = stock;
}
void rp_to(void *p, double t) { world_to(p, t); }
void rp_begin(void *p, double t) { group_begin(p, t); }
void rp_end(void *p, double t) { group_end(p, t); }
void rp_click(void *p, double t) { catch_click(p, t); }
void rp_sample(void *p, double t) { catch_sample(p, t); }
void rp_finish(void *p, double t) { world_to(p, t); dot_adv(p, t); patch_close(p, t); }
void rp_move(void *p, double x, double y, double t) {
  Ctx *c = p; c->X = x; c->Y = y; c->t_x = t; c->Fx = c->Fy = 0.0;
}
double rp_rate(void *p, double x, double y) { return patch_rate(p, x, y); }
void rp_corrupt(void *p, int kind, int slot, int delta) {
  Ctx *c = p;
  if (kind < PC_COUNT) c->patch_counts[kind][slot] += delta;
  else if (kind == PC_COUNT) c->patch[slot].stock += delta;
  else if (kind == PC_COUNT + 1) c->patch[slot].initial_remaining += delta;
  else if (kind == PC_COUNT + 2) c->captures += delta;
  else if (kind == PC_COUNT + 3) c->misses += delta;
  else if (kind == PC_COUNT + 4) c->clicks += delta;
  else c->patch_geometric_misses += delta;
}
void rp_read(void *p, double *v, uint64_t *h) {
  Ctx *c = p;
  const double base[] = {(double)c->clicks, (double)c->captures, (double)c->misses,
    c->income, c->cost, (double)c->status, (double)c->patch_geometric_misses, c->patch_opened,
    (double)c->samples, (double)c->zone, c->dist_sum, (double)c->b2_clicks,
    (double)c->respawns, (double)c->low_light_captures};
  int k = 0;
  for (int i = 0; i < 14; i++) v[k++] = base[i];
  for (int i = 0; i < 4; i++) {
    Patch *a = &c->patch[i];
    const double slot[] = {a->x, a->y, a->period, a->first, a->next, (double)a->arrival_index,
      (double)a->stock, (double)c->patch_left[i], (double)a->initial_remaining, (double)c->patch_initial_open[i]};
    for (int j = 0; j < 10; j++) v[k++] = slot[j];
  }
  for (int j = 0; j < PC_COUNT; j++) for (int i = 0; i < 4; i++) v[k++] = (double)c->patch_counts[j][i];
  h[0] = c->H[H_WORLD]; h[1] = c->H[H_ALL];
}
int rp_world_ok(const double *w) { return world_ok(w); }
''')
        library = directory / "patch_fixture.so"
        subprocess.run(["gcc", *build.CFLAGS, "-o", str(library), str(source), "-lm"], check=True,
                       capture_output=True, env=dict(os.environ, TMPDIR=str(directory)))
        lib = ctypes.CDLL(str(library))
        ptr, dbl, integer, u64 = ctypes.c_void_p, ctypes.c_double, ctypes.c_int, ctypes.c_uint64
        declarations = {
            "rp_new": ([integer, integer, dbl, dbl, u64], ptr), "rp_free": ([ptr], None),
            "rp_slot": ([ptr, integer, dbl, dbl, integer, integer, dbl, dbl, u64], None),
            "rp_move": ([ptr, dbl, dbl, dbl], None), "rp_rate": ([ptr, dbl, dbl], dbl),
            "rp_corrupt": ([ptr, integer, integer, integer], None), "rp_read": ([ptr, F64P, U64P], None),
            "rp_world_ok": ([F64P], integer),
        }
        declarations.update({name: ([ptr, dbl], None) for name in
                             ("rp_to", "rp_begin", "rp_end", "rp_click", "rp_sample", "rp_finish")})
        for name, (arguments, result) in declarations.items():
            getattr(lib, name).argtypes, getattr(lib, name).restype = arguments, result
        yield lib


@pytest.fixture
def state(patch_c):
    allocated = []

    def create(count=1, capacity=2, t_open=0.0, t0=0.0, forced=True):
        p = patch_c.rp_new(count, capacity, t_open, t0, 11)
        assert p
        allocated.append(p)
        if forced:
            for i in range(count):
                patch_c.rp_slot(p, i, 3.0 + 3.0 * i, 0.0, capacity, capacity, math.inf, 10.0, 0)
        return p

    yield create
    for p in allocated:
        patch_c.rp_free(p)


def _read(lib, p):
    values, hashes = np.zeros(len(STATE_NAMES)), np.zeros(2, dtype=np.uint64)
    lib.rp_read(p, values.ctypes.data_as(F64P), hashes.ctypes.data_as(U64P))
    return dict(zip(STATE_NAMES, values)), hashes


def _bits(value):
    return np.float64(value).view(np.uint64).item()


def _fold(hashes, *records):
    result = []
    for value in hashes:
        for words in records:
            for word in words:
                value = spec.splitmix64(int(value) ^ int(word))
        result.append(value)
    return result


def _hit(lib, p, t, slot=0):
    lib.rp_move(p, 3 + 3 * slot, 0, t)
    lib.rp_click(p, t)


def _balanced(v, count=1):
    for i in range(count):
        assert v[f"source_{i}"] == v[f"supply_{i}"] + v[f"spill_{i}"]
        assert v[f"open_{i}"] + v[f"supply_{i}"] == v[f"harvest_{i}"] + v[f"end_{i}"]
        assert v[f"harvest_{i}"] == v[f"initial_{i}"] + v[f"refill_{i}"]
        assert v[f"initial_open_{i}"] == v[f"initial_{i}"] + v[f"initial_left_{i}"]
    assert v["captures"] == sum(v[f"harvest_{i}"] for i in range(count))
    assert v["misses"] == v["geometric"] + sum(v[f"empty_{i}"] for i in range(count))
    assert v["clicks"] == v["captures"] + v["misses"]
    assert not int(v["status"]) & spec.STATUS["ledger_mismatch"]


def test_same_group_has_finite_stock_but_frozen_receptor_field(patch_c, state):
    p = state()
    patch_c.rp_begin(p, 1)
    rate_before = patch_c.rp_rate(p, 3, 0)
    before, hashes = _read(patch_c, p)
    for _ in range(3):
        _hit(patch_c, p, 1)
        assert patch_c.rp_rate(p, 3, 0) == rate_before
    v, actual = _read(patch_c, p)
    records = []
    for outcome, stock_before, stock_after, origin in ((1, 2, 1, 1), (1, 1, 0, 1), (2, 0, 0, 0)):
        records += [[20, _bits(1), outcome, 0, stock_before, stock_after, origin],
                    [11, _bits(1), int(outcome == 1), _bits(3), _bits(0)]]
    assert actual.tolist() == _fold(hashes, *records)
    assert [v[k] for k in ("clicks", "captures", "misses", "income", "cost", "stock_0")] == [3, 2, 1, 1000, 10, 0]
    assert v["next_0"] == before["next_0"] == math.inf
    patch_c.rp_end(p, 1)
    patch_c.rp_begin(p, 2)
    assert patch_c.rp_rate(p, 3, 0) == 0.05 + 2.0 * 0.1
    patch_c.rp_finish(p, 3)
    _balanced(_read(patch_c, p)[0])


@pytest.mark.parametrize("stock,click,harvest,supply,spill", [
    (0, True, 0, 1, 0), (1, True, 1, 1, 0), (2, True, 1, 1, 0), (2, False, 0, 0, 1),
])
def test_source_tie_uses_left_stock_then_admits_or_spills(patch_c, state, stock, click, harvest, supply, spill):
    p = state()
    patch_c.rp_slot(p, 0, 3, 0, stock, stock, 5, 10, 0)
    patch_c.rp_begin(p, 5)
    assert _read(patch_c, p)[0]["source_0"] == 0
    if click:
        _hit(patch_c, p, 5)
    patch_c.rp_end(p, 5)
    patch_c.rp_to(p, math.nextafter(5, math.inf))
    v, _ = _read(patch_c, p)
    assert [v[k] for k in ("harvest_0", "source_0", "supply_0", "spill_0")] == [harvest, 1, supply, spill]
    assert v["stock_0"] == stock - harvest + supply
    patch_c.rp_finish(p, 6)
    _balanced(_read(patch_c, p)[0])


def test_simultaneous_sources_fold_in_slot_order_and_keep_independent_stocks(patch_c, state):
    p = state(count=2)
    patch_c.rp_slot(p, 0, 3, 0, 0, 0, 5, 10, 0)
    patch_c.rp_slot(p, 1, 6, 0, 2, 2, 5, 10, 0)
    _, before = _read(patch_c, p)
    patch_c.rp_to(p, math.nextafter(5, math.inf))
    v, after = _read(patch_c, p)
    assert after.tolist() == _fold(before, [19, _bits(5), 0, 0, 0, 1, 1], [19, _bits(5), 1, 0, 2, 2, 0])
    assert (v["supply_0"], v["spill_0"], v["supply_1"], v["spill_1"]) == (1, 0, 0, 1)
    patch_c.rp_finish(p, 6)
    _balanced(_read(patch_c, p)[0], 2)


@pytest.mark.parametrize("t0", [0.0, -32.0, 32.0])
def test_pre_window_harvest_and_fifo_initial_refill_provenance(patch_c, state, t0):
    p = state(t_open=5, t0=t0)
    patch_c.rp_slot(p, 0, 3, 0, 2, 2, t0 + 3, 2, 0)
    patch_c.rp_begin(p, t0 + 1)
    _hit(patch_c, p, t0 + 1)
    patch_c.rp_end(p, t0 + 1)
    patch_c.rp_begin(p, t0 + 5)  # source at3 admitted before open; source at5 is still pending
    v, _ = _read(patch_c, p)
    assert (v["open_0"], v["initial_open_0"], v["source_0"], v["captures"]) == (2, 1, 0, 0)
    _hit(patch_c, p, t0 + 5)
    _hit(patch_c, p, t0 + 5)
    patch_c.rp_end(p, t0 + 5)
    patch_c.rp_begin(p, t0 + 6)
    _hit(patch_c, p, t0 + 6)
    patch_c.rp_end(p, t0 + 6)
    patch_c.rp_finish(p, t0 + 7)  # source exactly7 excluded
    v, _ = _read(patch_c, p)
    assert [v[k] for k in ("source_0", "supply_0", "harvest_0", "initial_0", "refill_0", "end_0")] == [1, 1, 3, 1, 2, 0]
    assert v["income"] == 1500 and v["cost"] == 0
    _balanced(v)


@pytest.mark.parametrize("end,opened,source,stock_end", [(4, 0, 0, 0), (5, 0, 0, 0), (6, 2, 1, 2)])
def test_close_before_at_after_open_and_terminal_source_exclusion(patch_c, state, end, opened, source, stock_end):
    p = state(t_open=5)
    patch_c.rp_slot(p, 0, 3, 0, 2, 2, 5, 1, 0)
    patch_c.rp_to(p, end)
    _, hashes = _read(patch_c, p)
    patch_c.rp_finish(p, end)
    v, actual = _read(patch_c, p)
    assert (v["open_0"], v["source_0"], v["end_0"]) == (opened, source, stock_end)
    assert actual.tolist() == _fold(hashes, [21, _bits(end), 0, 2, 2])
    if end <= 5:
        assert all(v[f"{name}_{i}"] == 0 for name in PC_NAMES for i in range(4))
    else:
        _balanced(v)


def test_empty_patch_remains_localizable_and_geometric_miss_is_separate(patch_c, state):
    p = state(count=2)
    patch_c.rp_slot(p, 0, 3, 0, 0, 0, math.inf, 10, 0)
    patch_c.rp_begin(p, 1)
    _hit(patch_c, p, 1)
    _hit(patch_c, p, 1, slot=1)
    patch_c.rp_move(p, 20, 0, 1)
    _, hashes = _read(patch_c, p)
    patch_c.rp_click(p, 1)
    v, actual = _read(patch_c, p)
    assert actual.tolist() == _fold(hashes, [20, _bits(1), 0, 4, 0, 0, 0],
                                    [11, _bits(1), 0, _bits(20), _bits(0)])
    assert (v["empty_0"], v["empty_1"], v["geometric"], v["income"], v["cost"]) == (1, 0, 1, 500, 20)
    patch_c.rp_move(p, 3, 0, 2)
    patch_c.rp_sample(p, 2)
    v, _ = _read(patch_c, p)
    assert (v["samples"], v["zone"], v["dist_sum"]) == (1, 1, 0)
    assert v["b2_clicks"] == v["respawns"] == v["low_light_captures"] == 0
    patch_c.rp_finish(p, 3)
    _balanced(_read(patch_c, p)[0], 2)


@pytest.mark.parametrize("kind,delta", [(0, 1), (1, 1), (2, 1), (3, -1), (4, 1), (5, -1),
                                        (7, 1), (8, 1), (9, 1), (10, -1), (11, 1), (12, 1), (13, 1), (14, 1)])
def test_close_flags_corrupt_counters_without_repairing_them(patch_c, state, kind, delta):
    p = state()
    patch_c.rp_begin(p, 1)
    _hit(patch_c, p, 1)
    patch_c.rp_corrupt(p, kind, 0, delta)
    before, _ = _read(patch_c, p)
    patch_c.rp_finish(p, 2)
    v, _ = _read(patch_c, p)
    assert int(v["status"]) & spec.STATUS["ledger_mismatch"]
    for key in ("open_0", "source_0", "supply_0", "spill_0", "harvest_0", "empty_0", "initial_0", "refill_0",
                "stock_0", "initial_left_0", "captures", "misses", "clicks", "geometric"):
        assert v[key] == before[key]


def test_cross_slot_corruption_cannot_hide_behind_balanced_global_totals(patch_c, state):
    p = state(count=2)
    patch_c.rp_begin(p, 1)
    _hit(patch_c, p, 1)
    patch_c.rp_corrupt(p, 4, 0, -1)
    patch_c.rp_corrupt(p, 4, 1, 1)
    patch_c.rp_corrupt(p, 7, 0, -1)
    patch_c.rp_corrupt(p, 7, 1, 1)
    patch_c.rp_finish(p, 2)
    v, _ = _read(patch_c, p)
    assert v["captures"] == v["harvest_0"] + v["harvest_1"] == 1
    assert int(v["status"]) & spec.STATUS["ledger_mismatch"]


def test_source_hash_uses_full_counter_and_indexed_timestamp_arithmetic(patch_c, state):
    p = state()
    index, period, first = 2 ** 32 + 7, 0.1, 0.3
    timestamp = first + float(index) * period
    patch_c.rp_slot(p, 0, 3, 0, 0, 0, first, period, index)
    _, hashes = _read(patch_c, p)
    patch_c.rp_to(p, math.nextafter(timestamp, math.inf))
    v, actual = _read(patch_c, p)
    assert actual.tolist() == _fold(hashes, [19, _bits(timestamp), 0, index, 0, 1, 1])
    assert v["next_0"] == first + float(index + 1) * period
    assert v["index_0"] == index + 1


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_initial_layout_streams_hashes_and_unused_slots(patch_c, state, count):
    p = state(count=count, forced=False)
    v, hashes = _read(patch_c, p)
    records = []
    for i in range(count):
        theta = spec.TWO_PI * spec.draw(11, 31, 0, 0) + (spec.TWO_PI * float(i)) / float(count)
        radius = 2 + (4 - 2) * spec.draw(11, 31, i, 1)
        x, y = radius * math.cos(theta), radius * math.sin(theta)
        period = 80 if spec.draw(11, 32, i, 0) < .5 else 160
        first = period * spec.draw(11, 33, i, 0)
        if first <= 0:
            first = math.nextafter(0, math.inf)
        assert (v[f"x_{i}"], v[f"y_{i}"], v[f"period_{i}"], v[f"first_{i}"]) == (x, y, period, first)
        records.append([18, _bits(0), i, _bits(x), _bits(y), _bits(period), _bits(first), 2])
        for j in range(i):
            assert math.hypot(x - v[f"x_{j}"], y - v[f"y_{j}"]) > 2
    assert hashes.tolist() == _fold([spec.HASH_INIT] * 2, *records)
    assert all(v[f"{name}_{i}"] == 0 for i in range(count, 4) for name in SLOT_NAMES)


@pytest.mark.parametrize("changes", [
    {"patch_count": -1}, {"patch_count": .5}, {"patch_count": 5}, {"patch_count": 0},
    {"patch_capacity": 0}, {"patch_capacity": .5}, {"patch_capacity": 2 ** 20 + 1},
    {"patch_refill_fast": spec.STEP_MIN / 2}, {"patch_refill_fast": 161},
    {"patch_refill_slow": spec.TIME_MAX * 2}, {"patch_refill_slow": math.inf},
    {"patch_landmark": -1}, {"patch_landmark": 1}, {"patch_landmark": math.nan},
    {"world_kind": 0}, {"task_mode": 1}, {"sample_min": 1},
    {"visibility_mode": 1, "visibility_on": 1}, {"visibility_low": .5},
    {"v_t": .1}, {"tau_turn": 1}, {"t_resp": 1}, {"b2_amp": .1}, {"b2_value": 1},
    {"b2_mode": 1}, {"b2_p": .5}, {"rho_c": 0}, {"R_min": 1.9},
    {"lam_s": 342}, {"T": spec.TIME_MAX, "patch_refill_fast": 1},
])
def test_native_validator_rejects_invalid_patch_combinations(patch_c, changes):
    vector = spec.V6.pack_world(spec.world("catch_resource_patches_l4"))
    assert patch_c.rp_world_ok(vector.ctypes.data_as(F64P)) == 1
    for key, value in changes.items():
        vector[spec.V6.WORLD_INDEX[key]] = value
    assert patch_c.rp_world_ok(vector.ctypes.data_as(F64P)) == 0


@pytest.mark.parametrize("changes", [
    {"patch_count": 1}, {"patch_count": 4}, {"patch_capacity": 1}, {"patch_capacity": 2 ** 20},
    {"patch_landmark": 0}, {"patch_refill_fast": 160, "patch_refill_slow": 160},
    {"patch_refill_fast": spec.TIME_MAX, "patch_refill_slow": spec.TIME_MAX},
    {"T": 1, "patch_refill_fast": spec.STEP_MIN, "patch_refill_slow": spec.STEP_MIN},
])
def test_native_validator_accepts_declared_patch_boundaries(patch_c, changes):
    vector = spec.V6.pack_world(spec.world("catch_resource_patches_l4", **changes))
    assert patch_c.rp_world_ok(vector.ctypes.data_as(F64P)) == 1
