"""Supplied-array selection tests; no simulator, search or genetic operator calls."""
import numpy as np
import pytest
import torch

from src.selection import epsilon_lexicase, pareto_order, pareto_ranking, unique_genome_indices


def generator(seed=17):
    return torch.Generator(device="cpu").manual_seed(seed)


def test_exact_lexicase_keeps_specialists_not_the_scalar_average_winner():
    values = [[10, 0], [0, 10], [6, 6]]
    selected = epsilon_lexicase(values, 100, generator=generator(), epsilon_multiplier=0)
    assert set(selected.tolist()) == {0, 1}
    assert len(selected) > len(set(selected.tolist()))  # mating is with replacement


def test_mad_near_elite_boundary_and_midpoint_median():
    # median=6, MAD=4. Inclusive threshold=6 admits the near-elite rows2 and3.
    values = [[0], [0], [6], [6], [10], [10]]
    selected = epsilon_lexicase(values, 200, generator=generator())
    assert set(selected.tolist()) == {2, 3, 4, 5}
    strict = epsilon_lexicase(values, 100, generator=generator(), epsilon_multiplier=0)
    assert set(strict.tolist()) == {4, 5}


def test_even_population_mad_uses_midpoints():
    # Median5.5 gives MAD5 and threshold9. Lower medians instead give MAD1/threshold13.
    values = [[0], [1], [10], [14]]
    selected = epsilon_lexicase(values, 100, generator=generator())
    assert set(selected.tolist()) == {2, 3}


def test_configurable_mad_multiplier():
    values = [[0], [0], [6], [6], [10], [10]]
    selected = epsilon_lexicase(values, 200, generator=generator(), epsilon_multiplier=2.5)
    assert set(selected.tolist()) == set(range(6))


def test_without_replacement_removes_winner_and_recomputes_best():
    result = epsilon_lexicase([[1], [3], [2]], 3, generator=generator(), replace=False, epsilon_multiplier=0)
    assert result.tolist() == [1, 2, 0]


def test_without_replacement_degenerate_population_is_permutation():
    result = epsilon_lexicase(np.ones((12, 5)), 12, generator=generator(), replace=False)
    assert sorted(result.tolist()) == list(range(12))


def test_determinism_torch_numpy_equivalence_and_no_input_mutation():
    values = torch.tensor([[10., 1., 2.], [2., 8., 2.], [5., 4., 2.], [4., 5., 2.]])
    before, global_state = values.clone(), torch.get_rng_state().clone()
    a = epsilon_lexicase(values, 50, generator=generator())
    b = epsilon_lexicase(values.numpy(), 50, generator=generator())
    assert torch.equal(a, b) and torch.equal(values, before)
    assert torch.equal(torch.get_rng_state(), global_state)
    assert a.device.type == "cpu" and a.dtype == torch.int64


def test_lexicase_positive_task_scaling_and_offsets():
    values = np.array([[10., 0.], [0., 10.], [6., 6.], [4., 5.]])
    changed = values * [8., .25] + [-100., 20.]
    assert torch.equal(epsilon_lexicase(values, 100, generator=generator()),
                       epsilon_lexicase(changed, 100, generator=generator()))


def test_zero_and_singleton_selections_do_not_draw_rng():
    gen = generator()
    before = gen.get_state().clone()
    assert epsilon_lexicase([[1, 2]], 0, generator=gen).numel() == 0
    assert epsilon_lexicase([[1, 2]], 5, generator=gen).tolist() == [0] * 5
    assert torch.equal(before, gen.get_state())


@pytest.mark.parametrize("kwargs", [dict(k=-1), dict(k=1.5), dict(k=True), dict(k=3, replace=False),
                                   dict(k=1, epsilon_multiplier=-1), dict(k=1, epsilon_multiplier=np.inf),
                                   dict(k=1, epsilon_multiplier=np.nan), dict(k=1, replace=1)])
def test_invalid_lexicase_arguments_do_not_advance_rng(kwargs):
    gen = generator()
    before = gen.get_state().clone()
    with pytest.raises(ValueError):
        epsilon_lexicase([[1, 2], [2, 1]], generator=gen, **kwargs)
    assert torch.equal(before, gen.get_state())


@pytest.mark.parametrize("values", [[], [1, 2], np.zeros((2, 0)), [[1, np.nan]], [[np.inf]], [[1j]]])
def test_nonfinite_or_bad_shapes_rejected(values):
    with pytest.raises(ValueError):
        epsilon_lexicase(values, 1, generator=generator())
    with pytest.raises(ValueError):
        pareto_order(values, generator=generator())


def test_explicit_generator_required():
    with pytest.raises(ValueError):
        epsilon_lexicase([[1]], 1, generator=None)
    with pytest.raises(ValueError):
        pareto_order([[1]], generator=None)


def test_pareto_fronts_and_arbitrary_task_count():
    values = [[3, 1, 1, 1, 1], [1, 3, 1, 1, 1], [2, 2, 1, 1, 1], [1, 1, 1, 1, 1], [0, 0, 0, 0, 0]]
    ranking = pareto_ranking(values, generator=generator())
    assert ranking.ranks.tolist() == [0, 0, 0, 1, 2]
    assert set(ranking.order[:3].tolist()) == {0, 1, 2}
    assert ranking.order[-2:].tolist() == [3, 4]
    assert ranking.crowding[2] == 2 and ranking.crowding[3] == 0


def test_pareto_duplicate_groups_share_crowding_and_endpoint_ties():
    values = [[0, 4], [0, 4], [1, 3], [2, 2], [3, 1], [4, 0], [4, 0]]
    ranking = pareto_ranking(values, generator=generator())
    assert ranking.ranks.tolist() == [0] * 7
    assert ranking.crowding.tolist() == [np.inf, np.inf, 1., 1., 1., np.inf, np.inf]
    endpoints = {0, 1, 5, 6}
    assert ranking.order[:4].tolist() == [i for i in ranking.tie_order.tolist() if i in endpoints]
    assert ranking.order[4:].tolist() == [i for i in ranking.tie_order.tolist() if i not in endpoints]


def test_pareto_constants_and_single_task():
    ranking = pareto_ranking(np.ones((8, 3)), generator=generator())
    assert ranking.ranks.tolist() == [0] * 8
    assert ranking.crowding.tolist() == [0.] * 8
    assert torch.equal(ranking.order, ranking.tie_order)
    assert pareto_order([[4], [2], [3]], generator=generator()).tolist() == [0, 2, 1]


def test_pareto_seed_determinism_scaling_and_only_supplied_rng():
    values = np.array([[0., 4.], [1., 3.], [2., 2.], [3., 1.], [4., 0.]])
    before, state = values.copy(), torch.get_rng_state().clone()
    a = pareto_ranking(values, generator=generator())
    b = pareto_ranking(torch.from_numpy(values * [8., .25]), generator=generator())
    assert torch.equal(a.order, b.order) and torch.equal(a.crowding, b.crowding)
    assert np.array_equal(values, before) and torch.equal(torch.get_rng_state(), state)
    expected_gen = generator()
    expected_ties = torch.randperm(len(values), generator=expected_gen)
    actual_gen = generator()
    actual = pareto_ranking(values, generator=actual_gen)
    assert torch.equal(actual.tie_order, expected_ties)
    assert torch.equal(actual_gen.get_state(), expected_gen.get_state())


def test_pareto_extreme_finite_ranges_do_not_overflow():
    ranking = pareto_ranking([[-1e308, 1e308], [0, 0], [1e308, -1e308]], generator=generator())
    assert ranking.crowding.tolist() == [np.inf, 2., np.inf]


def test_exact_genome_dedup_preserves_first_dtype_and_signed_zero():
    values = np.array([[1, 2], [3, 4], [1, 2], [0., 2], [-0., 2]], dtype=np.float32)
    before = values.copy()
    assert unique_genome_indices(values).tolist() == [0, 1, 3, 4]
    assert unique_genome_indices(torch.from_numpy(values)).tolist() == [0, 1, 3, 4]
    assert np.array_equal(values, before)
    # Noncontiguous views are compared by logical row bytes, not memory layout.
    assert unique_genome_indices(values[:, ::-1]).tolist() == [0, 1, 3, 4]
    assert unique_genome_indices(np.empty((0, 875), np.float32)).numel() == 0


@pytest.mark.parametrize("values", [[1, 2], np.zeros((2, 0)), [[np.nan]], [[np.inf]]])
def test_invalid_genome_dedup(values):
    with pytest.raises(ValueError):
        unique_genome_indices(values)
