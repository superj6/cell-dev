"""Pure supplied-array checks; no simulator, build, torch or random draws."""
from __future__ import annotations

import importlib.util
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pytest

MODULE = Path(__file__).resolve().parents[1] / "pareto.py"
SPEC = importlib.util.spec_from_file_location("resource_patch_pareto_under_test", MODULE)
pareto = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pareto
SPEC.loader.exec_module(pareto)


def life_captures(domain_values, repeats=1):
    return np.asarray(domain_values, dtype=np.float64)[:, np.asarray(pareto.PATTERN * repeats)]


def test_capture_objectives_are_domain_means_but_f_is_life_weighted():
    cap = life_captures([[20, 10, 5], [4, 30, 6]])
    fit = life_captures([[10, 0, 0], [-4, 2, 6]])
    got = pareto.objective_vectors(cap, fit)
    np.testing.assert_array_equal(got, [[20, 10, 5, 5], [4, 30, 6, 0]])


def test_dominance_fronts_have_strict_and_all_maximize_semantics():
    values = [[4, 4, 4, -1], [3, 3, 3, -2], [3, 3, 3, -2], [2, 2, 2, -3], [5, 0, 0, -4]]
    ranking = pareto.rank_objectives(values, [4, 3, 2, 1, 0])
    np.testing.assert_array_equal(ranking.ranks, [0, 1, 1, 2, 0])
    np.testing.assert_array_equal(ranking.order, [4, 0, 2, 1, 3])


def test_exhaustive_four_dimensional_grid_fronts():
    values = np.asarray(list(itertools.product(range(3), repeat=4)), dtype=np.float64)
    ranking = pareto.rank_objectives(values, list(reversed(range(len(values)))))
    # In this complete lattice, each step downward in coordinate sum adds one dominance layer.
    np.testing.assert_array_equal(ranking.ranks, 8 - values.sum(axis=1))
    assert np.all(np.diff(ranking.ranks[ranking.order]) >= 0)


def test_crowding_uses_front_ranges_distinct_groups_and_equal_duplicates():
    values = [[0, 4, 10, 10], [1, 3, 10, 10], [1, 3, 10, 10], [2, 2, 10, 10], [4, 0, 10, 10]]
    ranking = pareto.rank_objectives(values, [4, 2, 3, 0, 1])
    np.testing.assert_array_equal(ranking.ranks, np.zeros(5))
    np.testing.assert_array_equal(ranking.crowding, [np.inf, 1, 1, 1.5, np.inf])
    np.testing.assert_array_equal(ranking.order, [4, 0, 3, 2, 1])


def test_duplicate_boundary_points_and_crowding_capacity_follow_supplied_order():
    ranking = pareto.rank_objectives([[0, 4, 0, 0], [0, 4, 0, 0], [4, 0, 0, 0], [2, 2, 0, 0]], [1, 2, 3, 0])
    assert np.isinf(ranking.crowding[:3]).all()
    np.testing.assert_array_equal(ranking.order[:2], [1, 2])
    assert ranking.crowding[3] == 2


@pytest.mark.parametrize("count", [1, 2, 32, 256])
def test_all_identical_front_has_zero_crowding_and_only_tie_order(count):
    supplied = np.arange(count - 1, -1, -1)
    ranking = pareto.rank_objectives(np.tile([2., 1., 0., -10.], (count, 1)), supplied)
    np.testing.assert_array_equal(ranking.ranks, np.zeros(count))
    np.testing.assert_array_equal(ranking.crowding, np.zeros(count))
    np.testing.assert_array_equal(ranking.order, supplied)


def test_zero_range_coordinate_does_not_manufacture_boundaries():
    ranking = pareto.rank_objectives([[0, 4, 3, 3], [1, 3, 3, 3], [2, 2, 3, 3], [3, 1, 3, 3], [4, 0, 3, 3]])
    np.testing.assert_array_equal(np.isinf(ranking.crowding), [True, False, False, False, True])
    np.testing.assert_array_equal(ranking.crowding[1:4], [1, 1, 1])


def test_front_rank_precedes_even_infinite_crowding():
    ranking = pareto.rank_objectives([[5, 5, 5, 5], [2, 3, 2, 2], [3, 2, 2, 2]], [2, 1, 0])
    np.testing.assert_array_equal(ranking.order, [0, 2, 1])
    assert ranking.crowding[0] == 0
    assert np.isinf(ranking.crowding[1:]).all()


def test_positive_coordinate_scaling_and_translation_leave_ranking_unchanged():
    values = np.asarray([[0, 4, 0, -8], [1, 3, 0, -4], [2, 2, 0, -2], [4, 0, 0, -1]], dtype=np.float64)
    original = pareto.rank_objectives(values, [2, 1, 3, 0])
    changed = pareto.rank_objectives(values * [2, 4, 8, 16] + [32, 64, 128, 256], [2, 1, 3, 0])
    np.testing.assert_array_equal(changed.ranks, original.ranks)
    np.testing.assert_array_equal(changed.order, original.order)
    np.testing.assert_allclose(changed.crowding, original.crowding, rtol=0, atol=1e-14)


def test_relabeling_candidates_and_tie_permutation_is_equivariant():
    values = np.asarray([[0, 4, 0, 0], [1, 3, 0, 0], [1, 3, 0, 0], [4, 0, 0, 0], [0, 0, 0, -1]])
    ties = np.asarray([2, 3, 0, 4, 1])
    permutation = np.asarray([4, 2, 0, 1, 3])
    inverse = np.argsort(permutation)
    original = pareto.rank_objectives(values, ties)
    changed = pareto.rank_objectives(values[permutation], inverse[ties])
    np.testing.assert_array_equal(permutation[changed.order], original.order)
    np.testing.assert_array_equal(changed.ranks, original.ranks[permutation])
    np.testing.assert_array_equal(changed.crowding, original.crowding[permutation])


def test_large_finite_signed_range_does_not_overflow_crowding():
    maximum = np.finfo(np.float64).max
    ranking = pareto.rank_objectives([[0, 2, 0, maximum], [1, 1, 0, 0], [2, 0, 0, -maximum]])
    assert ranking.crowding[1] == 3
    assert not np.isnan(ranking.crowding).any()


def test_both_stages_apply_pareto_and_map_recheck_rows_to_original_candidates():
    domain = np.zeros((256, 3))
    domain[:64, 0] = np.arange(64)
    domain[:64, 1] = np.arange(63, -1, -1)
    base_cap = life_captures(domain)
    base_fit = np.zeros((256, 8))
    base_fit[64:] = -100
    first = pareto.select_shortlist(base_cap, base_fit, np.arange(255, -1, -1))
    assert len(first.selected) == 64
    assert set(first.selected.tolist()) == set(range(64))
    assert first.lives_per_candidate == 8
    # Recheck rewards exactly the latter 32 original candidates, regardless of shortlist order.
    new_cap = np.zeros((64, 8))
    new_cap[first.selected >= 32] = 1000
    second = pareto.select_survivors(base_cap, base_fit, first.selected, new_cap, np.zeros((64, 8)),
                                     np.arange(63, -1, -1))
    assert len(second.selected) == 32
    assert set(second.selected.tolist()) == set(range(32, 64))
    assert second.lives_per_candidate == 16
    np.testing.assert_array_equal(second.candidate_indices, first.selected)
    np.testing.assert_array_equal(second.selected, first.selected[second.ranking.order[:32]])
    expected = pareto.objective_vectors(np.concatenate([base_cap[first.selected], new_cap], axis=1),
                                       np.concatenate([base_fit[first.selected], np.zeros((64, 8))], axis=1),
                                       pareto.PATTERN * 2)
    np.testing.assert_array_equal(second.ranking.objectives, expected)


def test_endpoint_nonlinear_minimum_is_taken_after_pooling_all_sixteen_lives():
    base = np.zeros((32, 3))
    new = np.zeros((32, 3))
    base[0], new[0] = [40, 2, 10], [0, 40, 10]
    base[1] = new[1] = [18, 16, 6]
    base_objectives = pareto.objective_vectors(life_captures(base), np.zeros((32, 8)))
    new_objectives = pareto.objective_vectors(life_captures(new), np.zeros((32, 8)))
    pooled = pareto.objective_vectors(np.concatenate([life_captures(base), life_captures(new)], axis=1),
                                     np.zeros((32, 16)), pareto.PATTERN * 2)
    actual = pareto.select_endpoint(pooled, range(32))
    wrong = (pareto.select_endpoint(base_objectives, range(32)).worst_fraction
             + pareto.select_endpoint(new_objectives, range(32)).worst_fraction) / 2
    assert actual.selected == 0
    assert int(np.argmax(wrong)) == 1
    np.testing.assert_array_equal(pooled[0], [20, 21, 10, 0])


def test_endpoint_uses_fixed_ao_scales_then_f_then_native_id_ascending():
    values = np.zeros((32, 4))
    reference = np.asarray([19.046875, 16.029296875, 5.919921875])
    np.testing.assert_array_equal(pareto.AO_REFERENCE, reference)
    values[:4, :3] = [[2, 2, 2], [2, 2, 2], [2, 2, 2], [1, 100, 100]] * reference
    values[:4, 3] = [-5, -4, -4, 10000]
    ids = [5324, 5323, 5322, 5325, *range(10000, 10028)]
    endpoint = pareto.select_endpoint(values, ids)
    assert endpoint.selected == 2
    np.testing.assert_array_equal(endpoint.order[:4], [2, 1, 0, 3])
    np.testing.assert_array_equal(endpoint.worst_fraction[:4], [2, 2, 2, 1])
    assert endpoint.audit()["selected_id"] == 5322


def test_endpoint_uses_all_survivors_without_pareto_front_filter():
    values = np.zeros((32, 4))
    values[0, :3] = pareto.AO_REFERENCE
    values[1, :3] = np.asarray(pareto.AO_REFERENCE) * [2, 1, 1]
    assert pareto.rank_objectives(values).ranks[1] < pareto.rank_objectives(values).ranks[0]
    assert pareto.select_endpoint(values, range(32)).selected == 0  # same minimum and F: lower ID


def test_inputs_are_never_mutated_and_audit_is_strict_json_safe():
    values = np.asarray([[0., 2., 0., 0.], [1., 1., 0., 0.], [2., 0., 0., 0.]])
    ties = np.asarray([2, 1, 0])
    values_before, ties_before = values.copy(), ties.copy()
    ranking = pareto.rank_objectives(values, ties)
    np.testing.assert_array_equal(values, values_before)
    np.testing.assert_array_equal(ties, ties_before)
    decoded = json.loads(json.dumps(ranking.audit(), allow_nan=False))
    assert decoded["crowding"] == [None, 2., None]
    assert decoded["crowding_infinite"] == [True, False, True]
    stage = pareto.select_shortlist(np.zeros((256, 8)), np.zeros((256, 8)))
    assert len(json.loads(json.dumps(stage.audit(), allow_nan=False))["selected"]) == 64
    endpoint = pareto.select_endpoint(np.zeros((32, 4)), range(32))
    assert json.loads(json.dumps(endpoint.audit(), allow_nan=False))["selected"] == 0


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_objectives_fail_before_ranking(bad):
    values = np.zeros((3, 4))
    values[1, 2] = bad
    with pytest.raises(ValueError, match="finite"):
        pareto.rank_objectives(values)


@pytest.mark.parametrize("bad", [[], [[1, 2, 3]], np.zeros((0, 4)), np.zeros((2, 4, 1))])
def test_invalid_objective_shapes_fail(bad):
    with pytest.raises(ValueError):
        pareto.rank_objectives(bad)


@pytest.mark.parametrize("bad", [[0, 0, 2], [0, 1], [0, 1, 3], [-1, 0, 1], [0., 1., 2.], [False, True, True]])
def test_tie_order_must_be_an_exact_integer_permutation(bad):
    with pytest.raises(ValueError, match="permutation"):
        pareto.rank_objectives(np.zeros((3, 4)), bad)


@pytest.mark.parametrize("bad", [-1., 0.5, np.nan, np.inf])
def test_invalid_capture_counts_are_not_silently_excluded(bad):
    counts = np.zeros((2, 8))
    counts[0, 0] = bad
    with pytest.raises(ValueError):
        pareto.objective_vectors(counts, np.zeros((2, 8)))


@pytest.mark.parametrize("bad", [[0] * 8, [0, 1, 0, 3, 0, 1, 0, 2], list(pareto.PATTERN[:-1]),
                                 [float(x) for x in pareto.PATTERN]])
def test_domain_assignment_must_be_complete_and_explicit(bad):
    with pytest.raises(ValueError, match="domain"):
        pareto.objective_vectors(np.zeros((2, 8)), np.zeros((2, 8)), bad)


def test_nonfinite_or_mismatched_production_f_is_rejected():
    with pytest.raises(ValueError):
        pareto.objective_vectors(np.zeros((2, 8)), np.zeros((3, 8)))
    fit = np.zeros((2, 8))
    fit[0, 0] = np.nan
    with pytest.raises(ValueError):
        pareto.objective_vectors(np.zeros((2, 8)), fit)


@pytest.mark.parametrize("shape", [(255, 8), (256, 7), (64, 8)])
def test_shortlist_exact_inventory_is_enforced(shape):
    with pytest.raises(ValueError):
        pareto.select_shortlist(np.zeros(shape), np.zeros(shape))


@pytest.mark.parametrize("short", [list(range(63)), [0] * 64, list(range(193, 257)),
                                   [float(x) for x in range(64)]])
def test_recheck_requires_exact_unique_base_mapping(short):
    with pytest.raises(ValueError):
        pareto.select_survivors(np.zeros((256, 8)), np.zeros((256, 8)), short,
                               np.zeros((64, 8)), np.zeros((64, 8)))


def test_recheck_new_rows_and_life_counts_are_exact():
    with pytest.raises(ValueError):
        pareto.select_survivors(np.zeros((256, 8)), np.zeros((256, 8)), range(64),
                               np.zeros((63, 8)), np.zeros((63, 8)))
    with pytest.raises(ValueError):
        pareto.select_survivors(np.zeros((256, 8)), np.zeros((256, 8)), range(64),
                               np.zeros((64, 16)), np.zeros((64, 16)))


def test_recheck_does_not_ignore_malformed_nonshortlisted_base_counts():
    counts = np.zeros((256, 8))
    counts[255, 0] = -1
    with pytest.raises(ValueError):
        pareto.select_survivors(counts, np.zeros((256, 8)), range(64), np.zeros((64, 8)), np.zeros((64, 8)))


def test_endpoint_exact_survivor_count_and_nonnegative_means():
    with pytest.raises(ValueError):
        pareto.select_endpoint(np.zeros((31, 4)), range(31))
    values = np.zeros((32, 4))
    values[0, 0] = -1
    with pytest.raises(ValueError):
        pareto.select_endpoint(values, range(32))


@pytest.mark.parametrize("ids", [list(range(31)), [0] * 32, list(range(-1, 31)),
                                 [float(x) for x in range(32)], [True] * 32])
def test_endpoint_requires_real_unique_native_ids(ids):
    with pytest.raises(ValueError, match="candidate_ids"):
        pareto.select_endpoint(np.zeros((32, 4)), ids)


def test_scalar_control_order_matches_native_stable_permutation_semantics():
    fitness = np.asarray([2., -1., 2., 3., -1.])
    supplied = [4, 2, 1, 0, 3]
    np.testing.assert_array_equal(pareto.rank_mean(fitness, supplied), [3, 2, 0, 4, 1])
    np.testing.assert_array_equal(pareto.rank_mean(fitness), [3, 0, 2, 1, 4])
    np.testing.assert_array_equal(fitness, [2., -1., 2., 3., -1.])


@pytest.mark.parametrize("bad", [[], [[1.]], [np.nan], [np.inf], [-np.inf]])
def test_scalar_control_rejects_invalid_fitness(bad):
    with pytest.raises(ValueError):
        pareto.rank_mean(bad)
