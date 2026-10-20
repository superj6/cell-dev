"""Contact-world laws and accounting, exercised directly without advanced cell lives."""
import math
from dataclasses import asdict, replace
from types import SimpleNamespace

import numpy as np
import pytest

from src.life import readouts, reference, spec

V = spec.V7


def account(**changes):
    w = spec.world("catch_contact_resources_l4", T=32, patch_count=1, patch_contact_delay=4, **changes)
    life = SimpleNamespace(**asdict(w), seed=11, keep_records=True, catch=True, t_open_abs=w.t0+w.t_open)
    a = reference._Accountant(life)
    for p in a.patches[:w.patch_count]:
        p.next = math.inf
    a.X, a.Y = a.patches[0].x, a.patches[0].y
    return a, w


def click(a, t):
    a._patch_click(t, t >= a.life.t_open_abs)


def value(a, name):
    return a.led[V.L[name]]


def test_layout_and_preset_preserve_cellular_interface_and_old_worlds():
    assert (V.WORLD_SIZE, V.LEDGER_SIZE, V.GENOME_SIZE) == (83, 143, 875)
    assert V.WORLD_KEYS[:82] == spec.V6.WORLD_KEYS and V.LEDGER[:107] == spec.V6.LEDGER
    assert V.INPUTS == spec.V6.INPUTS and V.KNOBS == spec.V6.KNOBS and V.STREAMS == spec.V6.STREAMS
    assert spec.CURRENT is spec.V2
    w = spec.world("catch_contact_resources_l4")
    old = spec.world("catch_resource_patches_l4")
    assert replace(w, name=old.name, stage=old.stage, patch_contact_delay=0) == old
    assert V.pack_world(old)[-1] == 0
    for abi in (spec.V2, spec.V3, spec.V4, spec.V5, spec.V6):
        with pytest.raises(NotImplementedError):
            abi.pack_world(w)


@pytest.mark.parametrize("delay", [-1, math.nan, math.inf, spec.STEP_MIN/2, 2*spec.TIME_MAX])
def test_invalid_delay(delay):
    with pytest.raises(ValueError):
        V.pack_world(spec.world("catch_contact_resources_l4", patch_contact_delay=delay))


def test_disabled_and_combined_work_validation():
    with pytest.raises(ValueError):
        V.pack_world(spec.world("catch_speck_l4", patch_contact_delay=4))
    with pytest.raises(ValueError, match="combined"):
        V.pack_world(spec.world("catch_contact_resources_l4", patch_contact_delay=spec.STEP_MIN))


def test_empty_trigger_fifo_repeated_contacts_and_recurrence():
    a, w = account()
    p = a.patches[0]
    click(a, 0)
    click(a, 0)
    assert p.stock == 0 and not p.contact_pending  # last successful meal never starts a job
    click(a, 0)
    click(a, 1)
    assert (p.contact_starts, p.contact_due, p.contact_pending) == (1, 4, 1)
    p.first = p.next = 2
    p.period = 10
    a.world_to(5)
    assert (p.stock, p.contact_stock, p.origin_n) == (2, 1, 2)
    click(a, 5)
    click(a, 5)
    click(a, 6)
    assert (p.contact_starts, p.contact_due, p.contact_pending) == (2, 10, 1)
    origins = [r[-1] for r in a.wlog if r[0] == reference.W_PATCH_CLICK]
    assert origins == [1, 1, 0, 0, 2, 3, 0]
    assert value(a, "misses") == 3 and value(a, "cost") == 30
    a._patch_finish(9)
    assert a.status == 0
    out = readouts.resource_summary(a.led[:V.LEDGER_SIZE], w, abi=V)
    assert out["contact_totals"]["harvest"] == 1 and out["contact_totals"]["pending_end"] == 1
    assert out["passive_harvest_per_life"] == 1


def test_strict_ties_source_before_contact_and_field_left_limit():
    a, _ = account()
    p = a.patches[0]
    rate = a._patch_rate(p.x, p.y)
    click(a, 0)
    click(a, 0)
    click(a, 0)
    assert a._patch_rate(p.x, p.y) == rate  # unchanged frozen group's field
    p.first = p.next = 4
    p.period = 10
    a.world_to(4)
    click(a, 4)
    assert p.stock == 0 and p.contact_starts == 1
    a.world_to(math.nextafter(4, math.inf))
    assert p.stock == 2 and p.contact_stock == 1 and not p.contact_pending
    events = [r[0] for r in a.wlog if r[1] == reference.bits(4.0)]
    assert events == [20, 11, 19, 23]
    a.patch_left[0] = p.stock
    before = (a.h[:], a.led[:], p.next, p.contact_due)
    a._patch_nearest(5)
    a._patch_rate(p.x, p.y)
    assert before == (a.h, a.led, p.next, p.contact_due)


def test_maturity_spill_clears_pending_and_never_queues_origin():
    a, _ = account()
    p = a.patches[0]
    click(a, 0)
    click(a, 0)
    click(a, 0)
    p.first = p.next = 1
    p.period = 1
    a.world_to(5)
    assert (p.stock, p.origin_n, p.contact_stock, p.contact_pending) == (2, 2, 0, 0)
    assert value(a, "patch_contact_spill_0") == 1
    a._patch_finish(5)
    assert a.status == 0


@pytest.mark.parametrize("endpoint", [1, 2, 3, 4, 5])
def test_window_pending_carry_and_right_excluded_endpoint(endpoint):
    a, _ = account(t_open=2)
    click(a, 0)
    click(a, 0)
    click(a, 0)
    a.world_to(endpoint)
    a._patch_finish(endpoint)
    assert a.status == 0
    if endpoint <= 2:
        assert not any(a.led[70:])
    else:
        assert value(a, "patch_contact_pending_open_0") == 1
        assert value(a, "patch_contact_maturities_0") == int(endpoint > 4)
        assert value(a, "patch_contact_pending_end_0") == int(endpoint <= 4)
    terminal = [r for r in a.wlog if r[0] == 24][0]
    assert terminal[3] == int(endpoint <= 4)


@pytest.mark.parametrize("name", spec.CONTACT_METRICS)
def test_contact_counter_corruption_is_rejected(name):
    a, w = account()
    click(a, 0)
    click(a, 0)
    click(a, 0)
    a.world_to(5)
    click(a, 5)
    a._patch_finish(6)
    row = np.array(a.led[:V.LEDGER_SIZE])
    row[V.L[f"patch_contact_{name}_0"]] += 1
    with pytest.raises(ValueError):
        readouts.resource_summary(row, w, abi=V)


def test_balanced_but_impossible_contact_subsets_are_rejected():
    a, w = account()
    a._patch_finish(1)
    row = np.array(a.led[:V.LEDGER_SIZE])
    row[V.L["patch_contact_pending_open_0"]] = 2
    row[V.L["patch_contact_pending_end_0"]] = 2
    with pytest.raises(ValueError):
        readouts.resource_summary(row, w, abi=V)
