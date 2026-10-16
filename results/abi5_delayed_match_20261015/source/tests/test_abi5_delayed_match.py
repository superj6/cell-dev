"""ABI5 Python contract and short parity checks; fixtures are correctness checks, not performance gates."""
import math
from dataclasses import replace

import numpy as np
import pytest

from src.life import analysis, build, spec
from src.life import reference as ref
from tests.life_helpers import mismatch

V5 = spec.V5


def _world(**overrides):
    return spec.world("catch_delayed_match_l4", **(dict(
        T=24.0, sample_min=2.0, sample_max=2.0, blank_min=3.0, blank_max=3.0,
        choice_T=4.0, reset_T=1.0) | overrides))


def _life(w=None, seed=11):
    """Construct an accountant without advancing cell events."""
    w = replace(w or _world(), flags=V5.flags("program_mode"))
    lat, unit = V5.lattice_tables(w.lattice)
    latd = ref._lattice(lat, unit, V5)
    wv, gt, program, cells = ref._prepare(
        V5.pack_world(w), latd, None, V5.pack_program(V5.theta()), None, V5)
    return ref._Life(wv, latd, gt, program, cells, (seed, 0, 0, 0), 0, 0, True, out_abi=V5)


def _total(a, metric):
    return sum(a.led[V5.L[f"{metric}_{cls}"]] for cls in ("narrow", "broad"))


def _move_to_slot(a, slot, t):
    a.X, a.Y = a.blob_at(slot, t)
    a.t_x, a.Fx, a.Fy = t, 0.0, 0.0


def test_layout_is_append_only_and_default_stays_legacy():
    assert spec.CURRENT is spec.V2
    assert (V5.WORLD_SIZE, V5.LEDGER_SIZE, V5.HASH_SIZE, V5.GENOME_SIZE) == (77, 70, 5, 875)
    assert V5.WORLD_KEYS[:70] == spec.V4.WORLD_KEYS
    assert V5.LEDGER[:58] == spec.V4.LEDGER
    assert V5.GENOME_FIELDS == spec.V3.GENOME_FIELDS
    assert V5.STREAMS["task_class"] == 27 and V5.STREAMS["task_side"] == 30
    assert V5.pack_world(spec.world())[-7:].tolist() == [0.0] * 7
    for abi in (spec.V2, spec.V3, spec.V4):
        with pytest.raises((ValueError, NotImplementedError)):
            abi.pack_world(_world())


@pytest.mark.parametrize("changes", [
    {"task_mode": 0.5}, {"task_mode": 2}, {"task_mode": 0},
    {"sample_min": 0}, {"sample_max": math.inf}, {"blank_min": math.nan},
    {"sample_min": 3}, {"blank_min": 4}, {"blank_min": 0.5},
    {"choice_T": spec.STEP_MIN / 2}, {"reset_T": spec.TIME_MAX * 2},
    {"world_kind": 0}, {"v_t": 0.1}, {"tau_turn": 1}, {"t_resp": 1},
    {"visibility_mode": 1, "visibility_on": 1},
    {"b2_amp": 0}, {"b2_p": 0.5}, {"b2_mode": 1},
    {"b2_sigma": 0.5}, {"b2_rho": 0.5}, {"R_min": 1}, {"b2_value": 0},
])
def test_invalid_task_worlds_are_rejected(changes):
    with pytest.raises((ValueError, NotImplementedError)):
        V5.pack_world(_world(**changes))


def test_phase_boundaries_are_left_limits_and_phase_hashes_clear_absent_positions():
    a = _life(_world(t0=100.0)).acct
    assert a.task_phase == ref.TASK_SAMPLE and a.task_next == 102.0
    assert [b.present for b in a.blobs] == [a.task_class == 0, a.task_class == 1]
    assert a.wlog[0] == (15, ref.bits(100.0), 0, 0, a.task_class, 0, 0, 0, 0)
    for boundary, old, new in ((102.0, ref.TASK_SAMPLE, ref.TASK_BLANK),
                               (105.0, ref.TASK_BLANK, ref.TASK_CHOICE),
                               (109.0, ref.TASK_CHOICE, ref.TASK_GAP),
                               (110.0, ref.TASK_GAP, ref.TASK_SAMPLE)):
        a.world_to(boundary)
        assert a.task_phase == old
        a.world_to(math.nextafter(boundary, math.inf))
        assert a.task_phase == new
        if new in (ref.TASK_BLANK, ref.TASK_GAP):
            assert not any(b.present for b in a.blobs)
            assert a.wlog[-1][-4:] == (0, 0, 0, 0)
    assert a.task_trial == 1 and _total(a, "choice_timeouts") == 1


def test_choice_geometry_is_class_independent_and_centered_at_current_body():
    states = [_life(seed=42).acct for _ in range(2)]
    for cls, a in enumerate(states):
        a.task_class = cls
        a.X, a.Y, a.t_x = 7.0, -3.0, 5.0
        a._task_enter(ref.TASK_CHOICE, 5.0)
    positions = [[(b.x, b.y) for b in a.blobs] for a in states]
    assert positions[0] == positions[1]
    x0, y0 = positions[0][0]
    x1, y1 = positions[0][1]
    assert (x0 + x1) / 2 == pytest.approx(7.0)
    assert (y0 + y1) / 2 == pytest.approx(-3.0)
    assert 2.0 <= math.hypot(x0 - 7.0, y0 + 3.0) <= 4.0


@pytest.mark.parametrize("cls,slot", [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_click_correctness_is_conditional_on_sample_and_repeat_is_a_miss(cls, slot):
    a = _life().acct
    a.task_class = cls
    a._task_enter(ref.TASK_CHOICE, 5.0)
    _move_to_slot(a, slot, 9.0)
    a.world_to(9.0)  # the exact deadline still belongs to the choice
    a._click(9.0, True)
    a._click(9.0, True)
    correct = slot == cls
    assert a.task_consumed and a.task_next == math.inf
    assert _total(a, "correct_choices") == int(correct)
    assert _total(a, "wrong_choices") == int(not correct)
    assert a.led[V5.L["captures"]] == int(slot == 0)
    assert a.led[V5.L["b2_clicks"]] == int(slot == 1)
    assert a.led[V5.L["income"]] == (500.0 if correct else 0.0)
    assert a.led[V5.L["cost"]] == (0.0 if correct else 50.0) + a.life.c_miss
    assert a.led[V5.L["clicks"]] == 2 and a.led[V5.L["misses"]] == 1
    assert [record[0] for record in a.wlog[-3:]] == [16, 11, 11]
    assert all(b.present for b in a.blobs)  # scene removal waits for group end
    a._end_group(9.0)
    a.world_to(math.nextafter(9.0, math.inf))
    assert a.task_phase == ref.TASK_GAP and _total(a, "choice_timeouts") == 0
    assert not any(b.present for b in a.blobs)


@pytest.mark.parametrize("t_open,end,opportunities,carry,timeouts,unfinished", [
    (0, 9, 1, 0, 0, 1), (5, 9, 1, 0, 0, 1),
    (6, 9, 0, 1, 0, 1), (6, 10, 0, 1, 1, 0),
    (8, 7, 0, 0, 0, 0), (8, 8, 0, 0, 0, 0),
])
def test_carry_in_and_unfinished_follow_actual_right_excluded_endpoint(
        t_open, end, opportunities, carry, timeouts, unfinished):
    a = _life(_world(t_open=t_open)).acct
    a.world_to(end)
    a._task_finish(end)
    assert [_total(a, key) for key in ("choice_opportunities", "choice_carry_in",
                                      "choice_timeouts", "unfinished_choices")] == [
        opportunities, carry, timeouts, unfinished]
    assert opportunities + carry == timeouts + unfinished
    assert a.wlog[-1] == (17, ref.bits(float(end)), a.task_trial, a.task_phase, a.task_class)


def test_receptor_presence_and_constant_candidate_bound(monkeypatch):
    life = _life(_world(lam_s=2.0, lam_bg=0.5))
    a, site = life.acct, ref._Site(0, 0, 0)
    assert life.lam_max == 4.5
    for phase, rate in ((ref.TASK_SAMPLE, 2.5), (ref.TASK_BLANK, 0.5), (ref.TASK_GAP, 0.5)):
        a._task_enter(phase, 0.0)
        for threshold in (rate - 1e-12, rate, rate + 1e-12):
            monkeypatch.setattr(spec, "draw", lambda *args, value=threshold / life.lam_max: value)
            a._rcand(0.0, site, 17, 0, False)
            assert a.wlog[-1][4] == int(threshold < rate)
        assert life.lam_max == 4.5
    w = _world(lam_s=2.0, lam_bg=0.5)
    assert spec.receptor_rate(w, 0.0, 0.0, None, None) == 0.5
    assert spec.receptor_rate(w, 0.0, 0.0, None, (0.0, 0.0)) == 2.5


def test_sampling_uses_nearest_choice_and_skips_other_phases():
    a = _life().acct
    a.sample(1.0)
    a.sample(3.0)
    assert a.led[V5.L["samples"]] == 0
    a.world_to(6.0)
    _move_to_slot(a, 1, 6.0)
    a.sample(6.0)
    assert a.led[V5.L["samples"]] == a.led[V5.L["zone_samples"]] == 1
    assert a.led[V5.L["dist_sum"]] == 0


def test_repricing_uses_correctness_counts_instead_of_physical_slot_counts():
    w, led = _world(), np.zeros(V5.LEDGER_SIZE)
    for key, value in {"captures": 99, "b2_clicks": 88, "income": 99999,
                       "correct_choices_narrow": 2, "correct_choices_broad": 3,
                       "wrong_choices_narrow": 1, "wrong_choices_broad": 2}.items():
        led[V5.L[key]] = value
    assert V5.column_cost(led, w) == 150
    assert V5.fitness(led, w) == (2500 - 150) / w.T
    assert analysis.catch_F(led, w, b2_value=-100)[0] == (2500 - 300) / w.T


def test_reference_close_flags_class_imbalance_even_when_aggregate_counts_balance():
    a = _life().acct
    a.led[V5.L["choice_opportunities_narrow"]] = 1
    a.led[V5.L["choice_timeouts_broad"]] = 1
    a.close(2.0, 0, V5.LEDGER_SIZE)
    assert int(a.led[V5.L["status"]]) & spec.STATUS["ledger_mismatch"]


def test_short_whole_lives_match_c_reference_and_scheduler():
    # 8 lives total: one C baseline pair, Python pair, C window pair and C fast pair.
    w = _world(sample_max=3.0, blank_max=4.0, flags=V5.flags("program_mode"))
    program = V5.pack_program(V5.theta(b=0.5, w0=1.0, emit0=1.0, g_r=1.0, kappa=1.0))
    cells, seeds = [(0, 0, 0), (0, 0, 1)], [11, 42]
    kwargs = dict(programs=program, init=cells, threads=1, abi=V5, raster_cap=128, fate_cap=16)
    base = build.run(w, seeds, **kwargs)
    for i, seed in enumerate(seeds):
        reference = ref.run(w, program=program, cells=cells, seed=seed, raster_cap=128, fate_cap=16, abi=V5)
        assert mismatch(base, i, reference) == []
    window = build.run(replace(w, window_h=0.25), seeds, **kwargs)
    fast = build.run(w, seeds, fast=True, **kwargs)
    for other in (window, fast):
        for key in ("ledger", "raster_t", "raster_uid", "raster_n", "fate_i", "fate_f", "fate_n"):
            assert getattr(base, key).tobytes() == getattr(other, key).tobytes(), key
    assert base.hashes.tobytes() == window.hashes.tobytes()
    assert (fast.hashes == spec.HASH_INIT).all()
    assert (base["status"] == 0).all()
    for cls in ("narrow", "broad"):
        assert np.array_equal(base[f"choice_opportunities_{cls}"] + base[f"choice_carry_in_{cls}"],
                              sum(base[f"{metric}_{cls}"] for metric in (
                                  "correct_choices", "wrong_choices", "choice_timeouts", "unfinished_choices")))
