"""Forced C world boundaries, without advanced cells or a behavioral admission gate.

Compile only in the integration owner's bounded session. All scratch/diagnostic files
stay below CELL_DEV_CACHE (or this study), including compiler diagnostics.
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

ROOT = Path(__file__).resolve().parents[3]
PC = ("open", "source", "supply", "spill", "harvest", "empty", "end", "initial", "refill")
CC = ("starts", "maturities", "supply", "spill", "harvest", "pending_open", "pending_end", "stock_open", "stock_end")
BASE = ("clicks", "captures", "misses", "income", "cost", "status", "fail", "opened")
SLOT = ("stock", "initial_left", "next", "pending", "due", "lifetime_starts", "contact_stock", "head", "length")
NAMES = BASE + tuple(f"{name}_{i}" for i in range(4) for name in SLOT) + tuple(
    f"{name}_{i}" for name in PC for i in range(4)) + tuple(f"contact_{name}_{i}" for name in CC for i in range(4))
F64P, U64P = ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_uint64)


@pytest.fixture(scope="module")
def contact_c():
    cache = Path(os.environ.get("CELL_DEV_CACHE", ROOT / "outputs/abi7_contact_resources_20261016/cache"))
    cache.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="contact-boundary-", dir=cache))
    source = directory / "fixture.c"
    source.write_text('#include "' + str(build.SRC.resolve()) + '"\n' + r'''
void *ar_new(int count, int capacity, double open, double t0, double delay) {
  Ctx *c = calloc(1, sizeof(Ctx));
  if (!c) return NULL;
  c->kind = WK_CATCH; c->n = 1; c->seed = 11; c->t0 = t0; c->t_open_abs = t0 + open;
  c->patch_count = count; c->patch_capacity = capacity; c->patch_contact_delay = delay;
  c->patch_fast = 80; c->patch_slow = 160; c->patch_landmark = 0.1;
  c->tau_z = 2.5; c->rho_c = 1; c->R_cap = 500; c->c_miss = 10;
  c->sigma = 0.6; c->lam_bg = 0.05; c->lam_s = 2; c->lam_max = 0.05 + 2 * count;
  c->R_min = 2; c->R_max = 4;
  for (int i = 0; i < HASH_SIZE; i++) c->H[i] = HASH_INIT;
  catch_start(c);
  for (int i = 0; i < count; i++) {
    c->patch[i].x = 3 + 3 * i; c->patch[i].y = 0;
    c->patch[i].first = c->patch[i].next = INFINITY;
  }
  return c;
}
void ar_free(void *p) { if (p) { ctx_free(p); free(p); } }
void ar_source(void *p, int i, double first, double period) {
  Patch *a = &((Ctx *)p)->patch[i];
  a->first = a->next = first; a->period = period; a->arrival_index = 0;
}
void ar_move(void *p, int slot, double t) {
  Ctx *c = p; c->X = slot < 0 ? 100 : c->patch[slot].x; c->Y = 0;
  c->t_x = t; c->Fx = c->Fy = 0;
}
void ar_begin(void *p, double t) { group_begin(p, t); }
void ar_end(void *p, double t) { group_end(p, t); }
void ar_click(void *p, double t) { catch_click(p, t); }
void ar_to(void *p, double t) { world_to(p, t); }
void ar_finish(void *p, double t) { world_to(p, t); dot_adv(p, t); patch_close(p, t); }
double ar_rate(void *p, double x) { return patch_rate(p, x, 0); }
void ar_lifetime(void *p, int slot, uint64_t starts) { ((Ctx *)p)->patch[slot].contact_starts = starts; }
int ar_origin(void *p, int slot, int offset) {
  Ctx *c = p; Patch *a = &c->patch[slot];
  return a->origins[(a->origin_head + offset) % c->patch_capacity];
}
void ar_corrupt(void *p, int kind, int delta) {
  Ctx *c = p; Patch *a = &c->patch[0];
  if (kind < CC_COUNT) c->contact_counts[kind][0] += delta;
  else if (kind == CC_COUNT) a->origin_n += delta;
  else if (kind == CC_COUNT + 1) a->contact_stock += delta;
  else if (kind == CC_COUNT + 2) a->origins[a->origin_head] = (uint8_t)delta;
  else if (kind == CC_COUNT + 3) a->origin_head = delta;
  else if (kind == CC_COUNT + 4) a->contact_pending = delta;
  else if (kind == CC_COUNT + 5) a->contact_due = (double)delta;
  else if (kind == CC_COUNT + 6) a->contact_starts = (uint64_t)delta;
}
void ar_read(void *p, double *v, uint64_t *h) {
  Ctx *c = p; int k = 0;
  const double base[] = {c->clicks, c->captures, c->misses, c->income, c->cost, c->status, c->fail, c->patch_opened};
  for (int j = 0; j < 8; j++) v[k++] = base[j];
  for (int i = 0; i < 4; i++) {
    Patch *a = &c->patch[i];
    const double values[] = {a->stock, a->initial_remaining, a->next, a->contact_pending, a->contact_due,
      (double)a->contact_starts, a->contact_stock, a->origin_head, a->origin_n};
    for (int j = 0; j < 9; j++) v[k++] = values[j];
  }
  for (int j = 0; j < PC_COUNT; j++) for (int i = 0; i < 4; i++) v[k++] = c->patch_counts[j][i];
  for (int j = 0; j < CC_COUNT; j++) for (int i = 0; i < 4; i++) v[k++] = c->contact_counts[j][i];
  h[0] = c->H[H_WORLD]; h[1] = c->H[H_ALL];
}
int ar_world_ok(const double *w) { return world_ok(w); }
''')
    library = directory / "fixture.so"
    result = subprocess.run(["gcc", *build.CFLAGS, "-o", str(library), str(source), "-lm"],
                            capture_output=True, text=True, env=dict(os.environ, TMPDIR=str(directory)))
    (directory / "compiler_stdout.txt").write_text(result.stdout)
    (directory / "compiler_stderr.txt").write_text(result.stderr)
    result.check_returncode()
    lib = ctypes.CDLL(str(library))
    ptr, dbl, integer, u64 = ctypes.c_void_p, ctypes.c_double, ctypes.c_int, ctypes.c_uint64
    declarations = {
        "ar_new": ([integer, integer, dbl, dbl, dbl], ptr), "ar_free": ([ptr], None),
        "ar_source": ([ptr, integer, dbl, dbl], None), "ar_move": ([ptr, integer, dbl], None),
        "ar_rate": ([ptr, dbl], dbl), "ar_lifetime": ([ptr, integer, u64], None),
        "ar_origin": ([ptr, integer, integer], integer), "ar_corrupt": ([ptr, integer, integer], None),
        "ar_read": ([ptr, F64P, U64P], None), "ar_world_ok": ([F64P], integer),
    }
    declarations.update({name: ([ptr, dbl], None) for name in
                         ("ar_begin", "ar_end", "ar_click", "ar_to", "ar_finish")})
    for name, (arguments, result) in declarations.items():
        getattr(lib, name).argtypes, getattr(lib, name).restype = arguments, result
    return lib


@pytest.fixture
def state(contact_c):
    allocated = []

    def create(count=1, capacity=2, t_open=0.0, t0=0.0, delay=4.0):
        p = contact_c.ar_new(count, capacity, t_open, t0, delay)
        assert p
        allocated.append(p)
        assert _read(contact_c, p)[0]["fail"] == 0
        return p

    yield create
    for p in allocated:
        contact_c.ar_free(p)


def _read(lib, p):
    values, hashes = np.zeros(len(NAMES)), np.zeros(2, dtype=np.uint64)
    lib.ar_read(p, values.ctypes.data_as(F64P), hashes.ctypes.data_as(U64P))
    return dict(zip(NAMES, values)), hashes.tolist()


def _hit(lib, p, t, slot=0, count=1):
    lib.ar_begin(p, t)
    lib.ar_move(p, slot, t)
    for _ in range(count):
        lib.ar_click(p, t)
    lib.ar_end(p, t)


def _bits(t):
    return np.float64(t).view(np.uint64).item()


def _fold(hashes, *records):
    out = []
    for h in hashes:
        for record in records:
            for word in record:
                h = spec.splitmix64(h ^ int(word))
        out.append(h)
    return out


def _balanced(v, count=1):
    assert v["status"] == v["fail"] == 0
    for i in range(count):
        assert v[f"open_{i}"] + v[f"supply_{i}"] == v[f"harvest_{i}"] + v[f"end_{i}"]
        assert v[f"source_{i}"] == v[f"supply_{i}"] + v[f"spill_{i}"]
        assert v[f"contact_pending_open_{i}"] + v[f"contact_starts_{i}"] == (
            v[f"contact_maturities_{i}"] + v[f"contact_pending_end_{i}"])
        assert v[f"contact_maturities_{i}"] == v[f"contact_supply_{i}"] + v[f"contact_spill_{i}"]
        assert v[f"contact_stock_open_{i}"] + v[f"contact_supply_{i}"] == (
            v[f"contact_harvest_{i}"] + v[f"contact_stock_end_{i}"])


def test_only_empty_before_click_starts_and_same_group_repeats_do_not_reset(contact_c, state):
    p = state()
    contact_c.ar_begin(p, 1)
    contact_c.ar_move(p, 0, 1)
    rate = contact_c.ar_rate(p, 3)
    _before, hashes = _read(contact_c, p)
    for _ in range(2):
        contact_c.ar_click(p, 1)
        assert _read(contact_c, p)[0]["pending_0"] == 0
    records = [[20, _bits(1), 1, 0, 2, 1, 1], [11, _bits(1), 1, _bits(3), _bits(0)],
               [20, _bits(1), 1, 0, 1, 0, 1], [11, _bits(1), 1, _bits(3), _bits(0)],
               [22, _bits(1), 0, 0, _bits(5)]]
    for _ in range(2):
        contact_c.ar_click(p, 1)
        records.extend([[20, _bits(1), 2, 0, 0, 0, 0], [11, _bits(1), 0, _bits(3), _bits(0)]])
    v, actual = _read(contact_c, p)
    assert actual == _fold(hashes, *records)
    assert [v[k] for k in ("captures", "misses", "income", "cost", "contact_starts_0", "due_0")] == [
        2, 2, 1000, 20, 1, 5]
    assert contact_c.ar_rate(p, 3) == rate  # receptor stock stays at the group's left limit
    contact_c.ar_end(p, 1)
    _hit(contact_c, p, 3)
    assert _read(contact_c, p)[0]["due_0"] == 5
    contact_c.ar_finish(p, 4)
    _balanced(_read(contact_c, p)[0])


def test_exact_due_click_cannot_harvest_or_restart_pending_job(contact_c, state):
    p = state()
    _hit(contact_c, p, 1, count=3)
    _hit(contact_c, p, 5)
    v, _ = _read(contact_c, p)
    assert (v["pending_0"], v["stock_0"], v["contact_starts_0"], v["contact_maturities_0"]) == (1, 0, 1, 0)
    contact_c.ar_to(p, math.nextafter(5, math.inf))
    _hit(contact_c, p, 6)
    assert _read(contact_c, p)[0]["pending_0"] == 0  # harvesting the last packet does not start
    _hit(contact_c, p, 7)
    contact_c.ar_finish(p, 8)
    v, _ = _read(contact_c, p)
    assert (v["contact_starts_0"], v["contact_harvest_0"], v["due_0"]) == (2, 1, 11)
    _balanced(v)


@pytest.mark.parametrize("passive_first,expected_origins", [(4.0, (2, 3)), (6.0, (3, 2))])
def test_post_initial_fifo_follows_arrival_order(contact_c, state, passive_first, expected_origins):
    p = state()
    _hit(contact_c, p, 1, count=3)
    contact_c.ar_source(p, 0, passive_first, 100)
    contact_c.ar_to(p, 7)
    assert tuple(contact_c.ar_origin(p, 0, i) for i in range(2)) == expected_origins
    _hit(contact_c, p, 7)
    v, _ = _read(contact_c, p)
    assert v["contact_harvest_0"] == int(expected_origins[0] == 3)
    _hit(contact_c, p, 8)
    contact_c.ar_finish(p, 9)
    v, _ = _read(contact_c, p)
    assert (v["initial_0"], v["refill_0"], v["contact_harvest_0"]) == (2, 2, 1)
    _balanced(v)


def test_initial_prefix_remains_older_than_admitted_passive(contact_c, state):
    p = state()
    _hit(contact_c, p, 1)
    contact_c.ar_source(p, 0, 2, 100)
    _hit(contact_c, p, 3)
    v, _ = _read(contact_c, p)
    assert (v["initial_0"], v["refill_0"], v["length_0"]) == (2, 0, 1)
    _hit(contact_c, p, 4)
    contact_c.ar_finish(p, 5)
    _balanced(_read(contact_c, p)[0])


def test_maturity_spills_and_clears_without_reserving_or_restarting(contact_c, state):
    p = state()
    _hit(contact_c, p, 1, count=3)
    contact_c.ar_source(p, 0, 2, 1)
    contact_c.ar_to(p, 6)
    v, _ = _read(contact_c, p)
    assert (v["stock_0"], v["pending_0"], v["contact_maturities_0"], v["contact_spill_0"],
            v["contact_supply_0"], v["length_0"]) == (2, 0, 1, 1, 0, 2)
    assert tuple(contact_c.ar_origin(p, 0, i) for i in range(2)) == (2, 2)
    contact_c.ar_finish(p, 6)
    _balanced(_read(contact_c, p)[0])


def test_event_ties_order_slot_before_kind_and_passive_before_contact(contact_c, state):
    p = state(count=2, capacity=1)
    for slot in range(2):
        _hit(contact_c, p, 1, slot=slot, count=2)
    for slot in range(2):
        contact_c.ar_source(p, slot, 5, 100)
    _, hashes = _read(contact_c, p)
    contact_c.ar_to(p, math.nextafter(5, math.inf))
    v, actual = _read(contact_c, p)
    records = []
    for slot in range(2):
        records.extend([[19, _bits(5), slot, 0, 0, 1, 1], [23, _bits(5), slot, 0, 1, 1, 0]])
    assert actual == _fold(hashes, *records)
    assert v["contact_spill_0"] == v["contact_spill_1"] == 1
    contact_c.ar_finish(p, 6)
    _balanced(_read(contact_c, p)[0], 2)


@pytest.mark.parametrize("t0", [-32.0, 0.0, 32.0])
@pytest.mark.parametrize("opening", [5.0, 6.0])
def test_pending_or_contact_stock_carries_across_opening(contact_c, state, t0, opening):
    p = state(t_open=opening, t0=t0)
    _hit(contact_c, p, t0 + 1, count=3)
    contact_c.ar_begin(p, t0 + opening)
    v, _ = _read(contact_c, p)
    assert (v["contact_pending_open_0"], v["contact_stock_open_0"]) == (
        (1, 0) if opening == 5 else (0, 1))
    contact_c.ar_end(p, t0 + opening)
    _hit(contact_c, p, t0 + 7)
    contact_c.ar_finish(p, t0 + 8)
    v, _ = _read(contact_c, p)
    assert v["contact_starts_0"] == 0 and v["contact_harvest_0"] == 1
    assert v["contact_maturities_0"] == int(opening == 5)
    _balanced(v)


@pytest.mark.parametrize("end,opening", [(4.0, 0.0), (5.0, 0.0), (6.0, 0.0), (4.0, 5.0), (5.0, 5.0)])
def test_endpoint_exclusion_and_terminal_records(contact_c, state, end, opening):
    p = state(t_open=opening)
    _hit(contact_c, p, 1, count=3)
    contact_c.ar_to(p, end)
    v, hashes = _read(contact_c, p)
    contact_c.ar_finish(p, end)
    after, actual = _read(contact_c, p)
    assert actual == _fold(hashes, [21, _bits(end), 0, int(v["stock_0"]), int(v["initial_left_0"])],
                          [24, _bits(end), 0, int(v["pending_0"]),
                           _bits(v["due_0"] if v["pending_0"] else 0), int(v["contact_stock_0"]), 1])
    if end <= opening:
        assert all(after[f"contact_{name}_{i}"] == 0 for name in CC for i in range(4))
    else:
        _balanced(after)
        assert after["contact_pending_end_0"] == int(end <= 5)


def test_job_hashes_keep_full_uint64_start_index(contact_c, state):
    p = state()
    index = 2 ** 32 + 7
    contact_c.ar_lifetime(p, 0, index)
    _hit(contact_c, p, 1, count=2)
    _, hashes = _read(contact_c, p)
    _hit(contact_c, p, 2)
    assert _read(contact_c, p)[1] == _fold(hashes, [22, _bits(2), 0, index, _bits(6)],
        [20, _bits(2), 2, 0, 0, 0, 0], [11, _bits(2), 0, _bits(3), _bits(0)])
    _, hashes = _read(contact_c, p)
    contact_c.ar_to(p, 7)
    assert _read(contact_c, p)[1] == _fold(hashes, [23, _bits(6), 0, index, 0, 1, 1])
    contact_c.ar_finish(p, 8)
    _balanced(_read(contact_c, p)[0])


def test_all_old_terminal_records_precede_all_contact_terminal_records(contact_c, state):
    p = state(count=2)
    _hit(contact_c, p, 1, count=3)
    _, hashes = _read(contact_c, p)
    contact_c.ar_finish(p, 4)
    assert _read(contact_c, p)[1] == _fold(hashes,
        [21, _bits(4), 0, 0, 0], [21, _bits(4), 1, 2, 2],
        [24, _bits(4), 0, 1, _bits(5), 0, 1], [24, _bits(4), 1, 0, _bits(0), 0, 0])


def test_lifetime_starts_include_distinct_carry_in_and_in_window_job(contact_c, state):
    p = state(t_open=4)
    _hit(contact_c, p, 1, count=3)
    contact_c.ar_to(p, 4)
    _hit(contact_c, p, 6)
    _hit(contact_c, p, 7)
    contact_c.ar_lifetime(p, 0, 1)  # would cover only the counted start, omitting the carry-in job
    contact_c.ar_finish(p, 8)
    v, _ = _read(contact_c, p)
    assert (v["contact_pending_open_0"], v["contact_starts_0"]) == (1, 1)
    assert int(v["status"]) & spec.STATUS["ledger_mismatch"]


@pytest.mark.parametrize("kind,delta", [(0, 1), (1, 1), (2, 1), (3, -1), (4, 1), (5, 2), (7, -1),
                                        (9, 1), (10, 1), (11, 9), (12, -1), (13, 2), (14, 0), (15, 0)])
def test_corrupt_contact_counts_and_queue_are_flagged(contact_c, state, kind, delta):
    p = state()
    _hit(contact_c, p, 1, count=3)
    contact_c.ar_to(p, 6)  # one ready contact packet, no pending job
    contact_c.ar_corrupt(p, kind, delta)
    before, _ = _read(contact_c, p)
    # Keep an invalid pending deadline after close; a nonpending deadline cannot schedule an event.
    if kind == 13:
        contact_c.ar_corrupt(p, 14, 100)
    contact_c.ar_finish(p, 7)
    after, _ = _read(contact_c, p)
    assert int(after["status"]) & spec.STATUS["ledger_mismatch"]
    for name in ("starts", "maturities", "supply", "spill", "harvest", "pending_open", "stock_open"):
        assert before[f"contact_{name}_0"] == after[f"contact_{name}_0"]


def test_disabled_and_geometric_clicks_never_start(contact_c, state):
    p, q = state(delay=0), state()
    _hit(contact_c, p, 1, count=4)
    _hit(contact_c, q, 1, slot=-1)
    for item in (p, q):
        contact_c.ar_finish(item, 6)
        v, _ = _read(contact_c, item)
        assert v["lifetime_starts_0"] == 0
        assert all(v[f"contact_{name}_{i}"] == 0 for name in CC for i in range(4))


@pytest.mark.parametrize("delay", [-1.0, spec.STEP_MIN / 2, spec.TIME_MAX * 2, math.nan, math.inf])
def test_raw_validator_rejects_bad_delay(contact_c, delay):
    w = spec.V7.pack_world(spec.world("catch_resource_patches_l4", T=1024))
    w[82] = delay
    assert contact_c.ar_world_ok(w.ctypes.data_as(F64P)) == 0


def test_raw_validator_enforces_neutral_and_combined_source_work(contact_c):
    w = spec.V7.pack_world(spec.world("catch_resource_patches_l4", T=1024, patch_contact_delay=80))
    assert contact_c.ar_world_ok(w.ctypes.data_as(F64P)) == 1
    w[82] = spec.STEP_MIN
    assert contact_c.ar_world_ok(w.ctypes.data_as(F64P)) == 0
    w = spec.V7.pack_world(spec.world("catch_speck_l4", T=1024))
    w[82] = 80
    assert contact_c.ar_world_ok(w.ctypes.data_as(F64P)) == 0
