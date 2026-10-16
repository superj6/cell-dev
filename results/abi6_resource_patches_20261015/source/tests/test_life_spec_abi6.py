"""Resource ABI validation and accounting; these checks make no behavioral success claim."""
import math
from dataclasses import replace

import numpy as np
import pytest

from src.life import analysis, readouts, spec

V6 = spec.V6


def world(**overrides):
    return spec.world("catch_resource_patches_l4", **overrides)


def test_resource_layout_preserves_all_previous_prefixes_and_cell_interfaces():
    assert spec.CURRENT is spec.V2
    assert (V6.WORLD_SIZE, V6.LEDGER_SIZE, V6.GENOME_SIZE, V6.HASH_SIZE) == (82, 107, 875, 5)
    assert V6.GENOME_FIELDS == spec.V3.GENOME_FIELDS
    assert V6.INPUTS == spec.V3.INPUTS and V6.KNOBS == spec.V3.KNOBS
    assert V6.FLAGS == spec.V3.FLAGS
    for abi in (spec.V2, spec.V3, spec.V4, spec.V5):
        assert V6.WORLD_KEYS[:abi.WORLD_SIZE] == abi.WORLD_KEYS
        assert V6.LEDGER[:abi.LEDGER_SIZE] == abi.LEDGER
        with pytest.raises(NotImplementedError):
            abi.pack_world(world())
    assert V6.pack_world(spec.world("catch_speck_l4"))[-5:].tolist() == [0.0] * 5
    assert V6.STREAMS == dict(spec.V5.STREAMS, patch_layout=31, patch_rate=32, patch_phase=33)


@pytest.mark.parametrize("changes", [
    {"patch_count": -1}, {"patch_count": 5}, {"patch_count": 1.5}, {"patch_count": 0},
    {"patch_capacity": 0}, {"patch_capacity": 1.5}, {"patch_capacity": 2 ** 20 + 1},
    {"patch_refill_fast": 0}, {"patch_refill_fast": spec.STEP_MIN / 2},
    {"patch_refill_fast": 161}, {"patch_refill_slow": spec.TIME_MAX * 2},
    {"patch_refill_slow": math.inf}, {"patch_landmark": math.nan},
    {"patch_landmark": -0.1}, {"patch_landmark": 1},
    {"T": 2 ** 20, "patch_refill_fast": 1, "patch_refill_slow": 1},
    {"world_kind": 0}, {"v_t": 0.1}, {"tau_turn": 1}, {"t_resp": 1},
    {"b2_amp": 1}, {"b2_value": 1}, {"b2_mode": 1}, {"b2_p": 0.5},
    {"rho_c": 0}, {"R_min": 1.99}, {"lam_s": 400},
    {"visibility_mode": 1, "visibility_on": 5}, {"task_mode": 1},
])
def test_ambiguous_or_unbounded_resource_worlds_are_rejected(changes):
    with pytest.raises((ValueError, NotImplementedError)):
        V6.pack_world(world(**changes))


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_fixed_patch_geometry_is_bounded_and_capture_disks_do_not_overlap(count):
    w = world(patch_count=count)
    for seed in range(16):
        positions = [spec.patch_layout(seed, i, count, w.R_min, w.R_max) for i in range(count)]
        for i, (x, y) in enumerate(positions):
            assert w.R_min <= math.hypot(x, y) <= w.R_max
            for a, b in positions[:i]:
                assert math.hypot(x - a, y - b) > 2 * w.rho_c
        # Source draws cannot alter geometry, and geometry cannot alter source phases/rates.
        for i in range(count):
            period, first = spec.patch_source(seed, i, 80.0, 160.0, 0.0)
            assert period in (80.0, 160.0) and 0 < first < period
            shifted = spec.patch_source(seed, i, 80.0, 160.0, 32.0)
            assert shifted == (period, 32.0 + first)


def test_stock_sensing_has_a_faint_landmark_and_a_constant_candidate_bound():
    w = world(patch_count=1)
    assert spec.lambda_max(w) == 2.05
    for stock, expected in ((2, 2.05), (1, 1.15), (0, 0.25)):
        assert spec.patch_receptor_rate(w, 0, 0, [(0, 0)], [stock]) == pytest.approx(expected)
        assert spec.lambda_max(w) == 2.05
    with pytest.raises(ValueError, match="explicit stocks"):
        spec.receptor_rate(w, 0, 0, (0, 0))


def ledger():
    led = np.zeros((1, V6.LEDGER_SIZE))
    rows = (
        dict(stock_open=2, source=3, supply=2, spill=1, harvest=3, empty=2, stock_end=1,
             initial_harvest=2, refill_harvest=1),
        dict(stock_open=2, source=1, supply=1, spill=0, harvest=1, empty=0, stock_end=2,
             initial_harvest=1, refill_harvest=0),
        dict(stock_open=2, source=0, supply=0, spill=0, harvest=0, empty=0, stock_end=2,
             initial_harvest=0, refill_harvest=0),
    )
    for slot, row in enumerate(rows):
        for metric, value in row.items():
            led[0, V6.L[f"patch_{metric}_{slot}"]] = value
    for name, value in dict(captures=4, misses=3, clicks=7, patch_geometric_misses=1, income=2000).items():
        led[0, V6.L[name]] = value
    return led


def test_resource_readout_separates_origins_and_failed_click_types():
    summary = readouts.resource_summary(ledger(), world())
    assert summary["harvest_per_life"] == 4
    assert summary["initial_harvest_per_life"] == 3
    assert summary["refill_harvest_per_life"] == 1
    assert summary["geometric_misses"] == 1 and summary["totals"]["empty"] == 2
    assert summary["offered_utilization"] == 4 / 10 and summary["spill_share"] == 1 / 4


@pytest.mark.parametrize("name,value", [
    ("patch_source_0", 4), ("patch_supply_0", 3), ("patch_initial_harvest_0", 1),
    ("patch_stock_end_0", 2), ("patch_empty_0", 1.5), ("patch_geometric_misses", -1),
    ("captures", 5), ("misses", 4), ("clicks", 8), ("b2_clicks", 1),
    ("patch_stock_open_3", 1),
])
def test_corrupted_conservation_or_native_totals_are_rejected(name, value):
    row = ledger()
    row[0, V6.L[name]] = value
    with pytest.raises(ValueError):
        readouts.resource_summary(row, world())


def test_balanced_origin_relabeling_cannot_create_initial_food():
    row = ledger()
    row[0, V6.L["patch_initial_harvest_0"]] = 3
    row[0, V6.L["patch_refill_harvest_0"]] = 0
    with pytest.raises(ValueError, match="initial resource harvest"):
        readouts.resource_summary(row, world())


def test_patch_reward_repricing_uses_food_count_and_keeps_original_miss_price():
    row, w = ledger(), world(T=64)
    assert V6.column_cost(row, w)[0] == 30
    assert V6.fitness(row, w)[0] == (2000 - 30) / 64
    assert analysis.catch_F(row, w, R_cap=250)[0] == (1000 - 30) / 64
    assert V6.fitness(row, replace(w, c_miss=5))[0] == (2000 - 15) / 64
