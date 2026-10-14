"""Pure scientific-contract tests for U; no simulation or numerical-identity startup."""
from __future__ import annotations

import copy
import importlib.util
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location("U_measure_tests", HERE / "measure.py")
measure = importlib.util.module_from_spec(loader)
loader.loader.exec_module(measure)

from src.life import spec  # noqa: E402


def base():
    return spec.world("catch_speck_l4", T=1024, d0=1.0, d_min=0.5, b2_amp=1.0,
                      b2_sigma=1.2, b2_value=-50.0, b2_p=1.0, b2_mode=1)


def state():
    return {"generation": 4, "curves": [{"gen": g, "pop_invalid": 0, "pop_mismatch": 0,
                                          "recheck_invalid": 0} for g in range(4)]}


def test_exact_world_and_intervention_differences():
    worlds = measure.condition_worlds(base())
    assert list(worlds) == measure.CONDITIONS
    original = asdict(base())
    diffs = {name: {key for key, value in asdict(world).items() if value != original[key]}
             for name, world in worlds.items()}
    assert diffs == {"trained": set(), "width_swapped": {"sigma", "b2_sigma"},
                     "frozen": {"t_fork", "t_open", "fork_flags"},
                     "frozen_lateral_off": {"t_fork", "t_open", "fork_flags"}}
    assert worlds["frozen"].fork_flags == 16
    assert worlds["frozen_lateral_off"].fork_flags == 2064
    assert worlds["frozen"].T - worlds["frozen"].t_open == 480
    assert worlds["width_swapped"].sigma == 1.2
    assert worlds["width_swapped"].b2_sigma == .6


@pytest.mark.parametrize("change", [{"d0": .5}, {"sigma": .4}, {"T": 1536}, {"b2_value": 0}, {"t_open": 1}])
def test_changed_base_world_rejected(change):
    with pytest.raises(ValueError, match="base world"):
        measure.condition_worlds(replace(base(), **change))


def test_valid_complete_checkpoint_only():
    assert measure.validate_search_state(state()) == {"pop_invalid": 0, "pop_mismatch": 0, "recheck_invalid": 0}
    bad = state()
    bad["generation"] = 3
    with pytest.raises(ValueError, match="incomplete"):
        measure.validate_search_state(bad)
    bad = state()
    bad["curves"].reverse()
    with pytest.raises(ValueError, match="ordered"):
        measure.validate_search_state(bad)


@pytest.mark.parametrize("key", ["pop_invalid", "pop_mismatch", "recheck_invalid"])
@pytest.mark.parametrize("value", [0.01, float("nan")])
def test_unhealthy_search_rejected(key, value):
    bad = state()
    bad["curves"][2][key] = value
    with pytest.raises(ValueError, match="block inference"):
        measure.validate_search_state(bad)


def rows():
    return {"trained": {2: {"F": np.array([10., 14., 12.])}, 0: {"F": np.array([7., 4., 10.])}},
            "width_swapped": {2: {"F": np.array([8., 7., 9.])}, 0: {"F": np.array([5., 5., 8.])}}}


def test_interaction_sign_and_within_seed_covariance():
    values = measure.paired_interaction(rows(), "trained", "width_swapped", 2, 0)
    np.testing.assert_array_equal(values, [0, 8, 1])
    # Correlated common offsets cancel before SE estimation.
    changed = copy.deepcopy(rows())
    for arm in changed.values():
        for row in arm.values():
            row["F"] += [1000, -1000, 999]
    np.testing.assert_array_equal(measure.paired_interaction(changed, "trained", "width_swapped", 2, 0), values)


def test_mismatched_windows_forbidden():
    with pytest.raises(ValueError, match="windows"):
        measure.paired_interaction(rows(), "trained", "frozen", 2, 0)


@pytest.mark.parametrize("bad", [np.array([1.]), np.array([1., 2.]), np.array([1., np.nan, 2.]),
                                 np.ones((3, 1))])
def test_bad_interaction_arrays_rejected(bad):
    changed = rows()
    changed["trained"][2]["F"] = bad
    with pytest.raises(ValueError):
        measure.paired_interaction(changed, "trained", "width_swapped", 2, 0)


def ledger_row(world, captures, poison, misses, other_cost, guard=0, extinct=0):
    row = {key: np.zeros(3) for key in spec.V3.LEDGER}
    row.update({"F_kernel": np.zeros(3), "extinct_charge": np.full(3, float(extinct)),
                "window": np.full(3, world.T - world.t_open)})
    for key, value in (("captures", captures), ("b2_clicks", poison), ("misses", misses),
                       ("guard_charge", guard)):
        row[key] = np.broadcast_to(np.asarray(value, dtype=float), (3,)).copy()
    row["income"] = world.R_cap * row["captures"]
    row["cost"] = spec.b2_cost(world) * row["b2_clicks"] + world.c_miss * row["misses"] + other_cost
    row["F_kernel"] = (row["income"] - row["cost"] - row["guard_charge"]) / row["window"]
    row["F"] = row["F_kernel"] - row["extinct_charge"]
    return row


@pytest.mark.parametrize("name", ["trained", "frozen"])
def test_accounting_exact_separates_do_less_from_capture_gain(name):
    world = measure.condition_worlds(base())[name]
    parent = ledger_row(world, [5, 6, 7], [10, 12, 14], [4, 4, 4], 80, guard=7, extinct=.25)
    winner = ledger_row(world, [6, 7, 8], [8, 10, 12], [2, 2, 2], 20, guard=5, extinct=.1)
    report = measure.decoy_comparison(winner, parent, world)
    p = report["decoy_fitness_contributions"]
    window = world.T - world.t_open
    assert p["capture_income"]["mean"] == pytest.approx(500 / window)
    assert p["poison_cost_saving"]["mean"] == pytest.approx(100 / window)
    assert p["miss_cost_saving"]["mean"] == pytest.approx(20 / window)
    assert p["other_cost_saving"]["mean"] == pytest.approx(60 / window)
    assert p["guard_charge_saving"]["mean"] == pytest.approx(2 / window)
    assert p["extinction_charge_saving"]["mean"] == pytest.approx(.15)
    assert abs(p["residual"]["mean"]) < 1e-10


def test_corrupt_fitness_accounting_rejected():
    world = base()
    parent = ledger_row(world, 5, 10, 4, 80)
    winner = ledger_row(world, 6, 8, 2, 20)
    winner["F"][0] += 1
    with pytest.raises(ValueError, match="accounting"):
        measure.decoy_comparison(winner, parent, world)


def test_fixed_confirmation_scope_and_life_count():
    assert len(measure.SEEDS) == 512 and len(set(measure.SEEDS)) == 512
    assert measure.SEEDS == list(range(52_060_000, 52_060_512))
    assert len(measure.LABELS) * len(measure.CONDITIONS) * len(measure.SEEDS) == 8192
    assert measure.RUNS == [53091, 53092]
    assert 2 * 4 * (256 * 3 + 64 * 4) + 2 * 2 * 16 + 2 * 3 * 2 + 8192 == 16460


def test_prepared_scope_when_available():
    path = HERE / "protocol.json"
    if not path.exists():
        pytest.skip("pure preparation not yet frozen")
    protocol = json.loads(path.read_text())
    assert protocol["world"] == asdict(base())
    assert protocol["startup_validation_genome_lives"] == 6
    assert protocol["search_cpu_seconds"] == 3600
    assert protocol["max_cpu_seconds"] == 7200
    assert protocol["confirmation"]["conditions"] == measure.CONDITIONS
    assert protocol["confirmation"]["labels"] == measure.LABELS
