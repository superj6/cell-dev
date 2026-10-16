"""Force ABI5 world boundaries directly; no behavioral admission criterion or hand-built winner.

The C fixture executes world operations without any cell simulation. The final probe check makes exactly
one C backend call and one observing-reference call, each a 24-unit life with the established seed11.
"""
import ctypes
import math
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.life import build, probe, readouts, spec
from src.life import handbuilt as hb

V5 = spec.V5
F64P = ctypes.POINTER(ctypes.c_double)
U64P = ctypes.POINTER(ctypes.c_uint64)
STATE_NAMES = ("phase", "next", "class", "trial", "consumed", "pending_gap", "present0", "present1",
               "x0", "y0", "x1", "y1", "choice_start", "clicks", "captures", "b2_clicks", "misses",
               "income", "cost", "low_light_captures", "samples", "zone_samples", "dist_sum", "status") + spec.TASK_LEDGER


@pytest.fixture(scope="module")
def world_c():
    cache = Path(os.environ.get("CELL_DEV_CACHE", Path(__file__).resolve().parents[1] / "outputs/abi5-tests"))
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="matching-fixture-", dir=cache) as directory:
        directory = Path(directory)
        source = directory / "matching_fixture.c"
        source.write_text('#include "' + str(build.SRC.resolve()) + '"\n' + r'''
void *dm_new(double open, uint64_t seed) {
  Ctx *c = calloc(1, sizeof(Ctx));
  c->kind = WK_CATCH; c->n = 1; c->seed = seed; c->t_open_abs = open;
  c->task_mode = 1; c->sample_min = c->sample_max = 2.0;
  c->blank_min = c->blank_max = 3.0; c->choice_T = 4.0; c->reset_T = 1.0;
  c->tau_z = 2.5; c->rho_c = c->b2_rho = 1.0; c->R_cap = 500.0;
  c->sigma = 0.5; c->b2_sigma = 1.2; c->b2_amp = c->b2_p = 1.0;
  c->R_min = 2.0; c->R_max = 4.0; c->c_miss = 2.0; c->c_b2 = 50.0;
  c->task_choice_start = INFINITY;
  for (int i = 0; i < HASH_SIZE; i++) c->H[i] = HASH_INIT;
  catch_start(c);
  return c;
}
void dm_free(void *p) { free(p); }
void dm_to(void *p, double t) { world_to(p, t); }
void dm_choice(void *p, int cls, double t, double x, double y) {
  Ctx *c = p; c->task_class = cls;
  c->X = x; c->Y = y; c->t_x = t; c->Fx = c->Fy = 0.0;
  task_enter(c, t, TASK_CHOICE);
}
void dm_move(void *p, int slot, double t) {
  Ctx *c = p; blob_at(&c->blob[slot], t, &c->X, &c->Y);
  c->t_x = t; c->Fx = c->Fy = 0.0;
}
void dm_click(void *p, double t) { world_to(p, t); catch_click(p, t); }
void dm_end(void *p, double t) { group_end(p, t); }
void dm_finish(void *p, double t) { world_to(p, t); dot_adv(p, t); task_close(p, t); }
void dm_corrupt_count(void *p, int counter, int cls) { ((Ctx *)p)->task_counts[counter][cls]++; }
void dm_read(void *p, double *v, uint64_t *h) {
  Ctx *c = p;
  const double values[24] = {c->task_phase, c->task_next, c->task_class, (double)c->task_trial,
    c->task_consumed, c->task_defer_gap, c->blob[0].present, c->blob[1].present,
    c->blob[0].x, c->blob[0].y, c->blob[1].x, c->blob[1].y, c->task_choice_start,
    (double)c->clicks, (double)c->captures, (double)c->b2_clicks, (double)c->misses,
    c->income, c->cost, (double)c->low_light_captures, (double)c->samples, (double)c->zone, c->dist_sum,
    (double)c->status};
  for (int i = 0; i < 24; i++) v[i] = values[i];
  for (int i = 0; i < TC_COUNT; i++) for (int cls = 0; cls < 2; cls++)
    v[24 + 2*i + cls] = (double)c->task_counts[i][cls];
  h[0] = c->H[H_WORLD]; h[1] = c->H[H_ALL];
}
int dm_world_ok(const double *w) { return world_ok(w); }
''')
        library = directory / "matching_fixture.so"
        subprocess.run(["gcc", *build.CFLAGS, "-o", str(library), str(source), "-lm"], check=True,
                       capture_output=True, env=dict(os.environ, TMPDIR=str(directory)))
        lib = ctypes.CDLL(str(library))
        lib.dm_new.argtypes = [ctypes.c_double, ctypes.c_uint64]
        lib.dm_new.restype = ctypes.c_void_p
        lib.dm_free.argtypes = [ctypes.c_void_p]
        lib.dm_free.restype = None
        for name in ("dm_to", "dm_click", "dm_end", "dm_finish"):
            getattr(lib, name).argtypes = [ctypes.c_void_p, ctypes.c_double]
            getattr(lib, name).restype = None
        lib.dm_choice.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_double, ctypes.c_double, ctypes.c_double]
        lib.dm_choice.restype = None
        lib.dm_move.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_double]
        lib.dm_move.restype = None
        lib.dm_corrupt_count.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        lib.dm_corrupt_count.restype = None
        lib.dm_read.argtypes = [ctypes.c_void_p, F64P, U64P]
        lib.dm_read.restype = None
        lib.dm_world_ok.argtypes = [F64P]
        lib.dm_world_ok.restype = ctypes.c_int
        yield lib


@pytest.fixture
def state(world_c):
    allocated = []

    def create(t_open=0.0, seed=11):
        p = world_c.dm_new(t_open, seed)
        assert p
        allocated.append(p)
        return p

    yield create
    for p in allocated:
        world_c.dm_free(p)


def _read(lib, p):
    v, h = np.zeros(len(STATE_NAMES)), np.zeros(2, dtype=np.uint64)
    lib.dm_read(p, v.ctypes.data_as(F64P), h.ctypes.data_as(U64P))
    return dict(zip(STATE_NAMES, v)), h


def _fold(hashes, words):
    out = []
    for h in hashes:
        for word in words:
            h = spec.splitmix64(int(h) ^ int(word))
        out.append(h)
    return out


def _bits(x):
    return np.float64(x).view(np.uint64).item()


def _total(values, metric):
    return values[f"{metric}_narrow"] + values[f"{metric}_broad"]


def test_c_phase_transitions_are_strict_and_clear_absent_geometry(world_c, state):
    p = state()
    values, hashes = _read(world_c, p)
    assert values["phase"] == 0 and values["next"] == 2
    cls = int(values["class"])
    assert hashes.tolist() == _fold([spec.HASH_INIT] * 2, [15, _bits(0), 0, 0, cls, 0, 0, 0, 0])
    for boundary, old_phase, next_phase in ((2, 0, 1), (5, 1, 2), (9, 2, 3), (10, 3, 0)):
        world_c.dm_to(p, boundary)
        assert _read(world_c, p)[0]["phase"] == old_phase
        world_c.dm_to(p, math.nextafter(boundary, math.inf))
        values, _ = _read(world_c, p)
        assert values["phase"] == next_phase
        if next_phase in (1, 3):
            assert all(values[key] == 0 for key in ("present0", "present1", "x0", "y0", "x1", "y1"))
    assert values["trial"] == 1 and _total(values, "choice_timeouts") == 1


@pytest.mark.parametrize("cls,slot", [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_c_click_tie_latches_one_outcome_then_defers_scene_removal(world_c, state, cls, slot):
    p = state()
    world_c.dm_choice(p, cls, 5, 0, 0)
    world_c.dm_move(p, slot, 9)
    before, hashes = _read(world_c, p)
    world_c.dm_click(p, 9)
    correct = cls == slot
    x, y = before[f"x{slot}"], before[f"y{slot}"]
    expected = _fold(hashes, [16, _bits(9), 0, cls, 1 if correct else 2, slot,
                             11, _bits(9), slot + 1, _bits(x), _bits(y)])
    values, hashes = _read(world_c, p)
    assert hashes.tolist() == expected
    assert values["next"] == math.inf and values["consumed"] == values["pending_gap"] == 1
    assert values["present0"] == values["present1"] == 1
    assert values["captures"] == int(slot == 0) and values["b2_clicks"] == int(slot == 1)
    assert _total(values, "correct_choices") == int(correct)
    assert _total(values, "wrong_choices") == int(not correct)
    assert values["income"] == 500 * int(correct) and values["cost"] == 50 * int(not correct)
    world_c.dm_click(p, 9)
    repeated, repeated_hashes = _read(world_c, p)
    assert repeated_hashes.tolist() == _fold(hashes, [11, _bits(9), 0, _bits(x), _bits(y)])
    assert repeated["clicks"] == 2 and repeated["misses"] == 1
    assert repeated["cost"] == values["cost"] + 2
    world_c.dm_end(p, 9)
    world_c.dm_to(p, math.nextafter(9, math.inf))
    after, _ = _read(world_c, p)
    assert after["phase"] == 3 and after["next"] == 10
    assert after["present0"] == after["present1"] == 0
    assert _total(after, "choice_timeouts") == 0 and after["low_light_captures"] == 0


@pytest.mark.parametrize("t_open,end,opened,carry,timeout,unfinished", [
    (0, 9, 1, 0, 0, 1), (5, 9, 1, 0, 0, 1), (6, 9, 0, 1, 0, 1),
    (6, 10, 0, 1, 1, 0), (8, 7, 0, 0, 0, 0), (8, 8, 0, 0, 0, 0),
])
def test_c_terminal_accounting_respects_actual_end_and_window(
        world_c, state, t_open, end, opened, carry, timeout, unfinished):
    p = state(t_open=t_open)
    world_c.dm_choice(p, 1, 5, 0, 0)
    world_c.dm_to(p, end)
    before, hashes = _read(world_c, p)
    world_c.dm_finish(p, end)
    values, after = _read(world_c, p)
    assert [_total(values, key) for key in ("choice_opportunities", "choice_carry_in", "choice_timeouts",
                                          "unfinished_choices")] == [opened, carry, timeout, unfinished]
    assert opened + carry == timeout + unfinished
    assert after.tolist() == _fold(hashes, [17, _bits(end), int(before["trial"]), int(before["phase"]),
                                          int(before["class"])])


@pytest.mark.parametrize("t_open,click,opened,carry,correct", [(5, 7, 1, 0, 1), (6, 7, 0, 1, 1), (8, 7, 0, 0, 0)])
def test_c_click_carry_is_counted_only_when_resolution_enters_window(
        world_c, state, t_open, click, opened, carry, correct):
    p = state(t_open=t_open)
    world_c.dm_choice(p, 1, 5, 0, 0)
    world_c.dm_move(p, 1, click)
    world_c.dm_click(p, click)
    world_c.dm_end(p, click)
    world_c.dm_finish(p, 9)
    values, _ = _read(world_c, p)
    assert [_total(values, key) for key in ("choice_opportunities", "choice_carry_in", "correct_choices")] == [
        opened, carry, correct]
    assert _total(values, "unfinished_choices") == _total(values, "choice_timeouts") == 0
    assert values["income"] == correct * 500


def test_c_geometry_depends_on_current_body_and_independent_streams(world_c, state):
    positions = []
    for cls in (0, 1):
        p = state(seed=42)
        world_c.dm_choice(p, cls, 5, 7, -3)
        values, _ = _read(world_c, p)
        positions.append(tuple(values[key] for key in ("x0", "y0", "x1", "y1")))
    assert positions[0] == positions[1]
    theta = spec.TWO_PI * spec.draw(42, 29, 0, 0)
    r = 2 + 2 * spec.draw(42, 29, 0, 1)
    dx, dy = r * math.cos(theta), r * math.sin(theta)
    positive, negative = (7 + dx, -3 + dy), (7 - dx, -3 - dy)
    expected = positive + negative if spec.draw(42, 30, 0, 0) < .5 else negative + positive
    assert np.asarray(positions[0]).tobytes() == np.asarray(expected).tobytes()


def test_c_close_flags_class_imbalance_even_when_aggregate_counts_balance(world_c, state):
    p = state()
    # The aggregate equation balances; the narrow and broad equations each fail.
    world_c.dm_corrupt_count(p, 0, 0)  # TC_OPEN, narrow
    world_c.dm_corrupt_count(p, 4, 1)  # TC_TIMEOUT, broad
    world_c.dm_finish(p, 2)
    values, _ = _read(world_c, p)
    assert _total(values, "choice_opportunities") == _total(values, "choice_timeouts") == 1
    assert int(values["status"]) & spec.STATUS["ledger_mismatch"]


@pytest.mark.parametrize("changes", [
    {"task_mode": -1}, {"task_mode": .5}, {"task_mode": 2}, {"task_mode": 0},
    {"sample_min": 0}, {"sample_min": 26}, {"sample_max": math.inf},
    {"blank_min": .5}, {"blank_min": 41}, {"blank_max": math.nan},
    {"choice_T": spec.STEP_MIN / 2}, {"reset_T": spec.TIME_MAX * 2},
    {"world_kind": 0}, {"v_t": .1}, {"tau_turn": 1}, {"t_resp": 1},
    {"visibility_mode": 1, "visibility_on": 1},
    {"b2_amp": 0}, {"b2_p": .5}, {"b2_mode": 1}, {"b2_sigma": .5},
    {"rho_c": .5}, {"R_min": 1}, {"b2_value": 0},
])
def test_c_validator_rejects_invalid_task_vectors_directly(world_c, changes):
    # This fixture calls the internal native validator directly, so newer tails must be padded.
    w = build.KERNEL.pack_world(spec.world("catch_delayed_match_l4"))
    assert world_c.dm_world_ok(w.ctypes.data_as(F64P)) == 1
    for key, value in changes.items():
        w[V5.WORLD_INDEX[key]] = value
    assert world_c.dm_world_ok(w.ctypes.data_as(F64P)) == 0


def test_abi5_probe_observation_preserves_full_ledger_and_spikes():
    # Exactly two new backend calls: one observing Python life and one ordinary C life.
    program = V5.pack_program(V5.theta(b=.5, w0=1, emit0=1, g_r=1, kappa=1))
    org = hb.Body("two-cell execution fixture", program, ((0, 0, 0, -1), (0, 0, 1, -1)))
    preset = "catch_delayed_match_l4"
    options = dict(T=24, sample_min=2, sample_max=3, blank_min=3, blank_max=4, choice_T=4, reset_T=1)
    trace = probe.trace(org, 11, preset, abi=V5, check=False, **options)
    result = build.run(org.world(preset, **options), [11], programs=program, init=list(org.cells),
                       abi=V5, threads=1, raster_cap=128, fate_cap=16)
    assert trace.meta["abi"] == 5 and len(trace.ledger) == 70
    assert np.asarray(list(trace.ledger.values())).tobytes() == result.ledger[0].tobytes()
    assert trace.spikes.t.to_numpy().tobytes() == result.spikes(0)[0].tobytes()
    assert trace.placements.empty
    assert set(trace.task_events.kind) == {15, 16, 17}
    assert trace.task_events.iloc[-1].kind == 17 and trace.task_events.iloc[-1].t == 24
    assert {"trial", "phase", "sample_class", "chosen_class", "correct"} <= set(trace.clicks.columns)
    summary = readouts.matching_summary(result.ledger)
    for cls in ("narrow", "broad"):
        assert summary["classes"][cls]["wrong_choices"] == trace.ledger[f"wrong_choices_{cls}"]
