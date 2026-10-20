"""Learning-progress allocation on supplied numbers only: no simulator, search or genetic operator calls."""
import math

import numpy as np
import pytest

from src.allocate import Allocator, apportion, lp_weights, progress, residual_variance, slope

TASKS = ("a", "b", "c")


def conf(**changes):
    return dict(dict(mode="lp", budget=24, floor=2, cap=8, mix=0.2, period=5, window=30, probe_top=4,
                     probe_lives=8), **changes)


@pytest.mark.parametrize("total,weights,floor,cap,expected", [
    (24, [1, 1, 1, 1, 1, 1, 1, 1], 2, 8, [3] * 8),
    (24, [1, 1, 1, 1, 1], 2, 8, [5, 5, 5, 5, 4]),  # remainder ties go to the earlier task
    (12, [0, 0, 0], 2, 8, [4, 4, 4]),  # zero weight: equal shares of the flexible lives
    (12, [1, 0, 0], 2, 8, [8, 2, 2]),
    (24, [10, 1, 1], 2, 12, [12, 6, 6]),  # the capped excess is shared by the others in proportion
    (24, [10, 1, 0], 2, 12, [12, 10, 2]),
    (24, [1, 2, 3], 2, 8, [8, 8, 8]),  # every quota reaches the cap in turn
    (20, [1, 2, 3], 2, 8, [5, 7, 8]),  # c capped at 8; a and b split the other 8 as 2.67 and 5.33
    (7, [1, 1, 1], 2, 8, [3, 2, 2]),
    (6, [5, 3, 1], 2, 8, [2, 2, 2]),
    (9, [2, 1, 0], 0, 9, [6, 3, 0]),  # race-style proportional apportionment, zeros allowed
])
def test_apportion_floor_cap_and_largest_remainder(total, weights, floor, cap, expected):
    lives = apportion(total, weights, floor, cap)
    assert lives == expected
    assert sum(lives) == total and all(floor <= n <= cap for n in lives)


def test_apportion_is_largest_remainder_of_the_flexible_lives():
    # Flexible 12 lives over quotas 12 * w / sum(w): 1.6, 3.2, 7.2 -> floors 1, 3, 7 (11) + one to the largest
    # remainder (0.6, first task).
    assert apportion(18, [1, 2, 4.5], 2, 12) == [4, 5, 9]
    # A float weight vector that does not sum exactly still gives integers that sum exactly (rational arithmetic).
    w = [0.1, 0.2, 0.3, 0.4, 1 / 3, 2 / 3, math.pi, math.e]
    for total in range(16, 65):
        lives = apportion(total, w, 2, 8)
        assert sum(lives) == total and min(lives) >= 2 and max(lives) <= 8


@pytest.mark.parametrize("args", [(5, [1, 1, 1], 2, 8), (25, [1, 1, 1], 2, 8), (6, [1, -1, 1], 2, 8),
                                  (6, [1, math.inf, 1], 2, 8), (6, [], 2, 8), (6, [1, 1, 1], 3, 2),
                                  (6.0, [1, 1, 1], 2, 8)])
def test_apportion_rejects_infeasible_or_bad_inputs(args):
    with pytest.raises(ValueError):
        apportion(*args)


def test_slope_and_progress_on_synthetic_series():
    g = np.arange(0, 35, 5)
    rng = np.random.default_rng(3)
    noise = rng.normal(0, 0.01, len(g))
    rising = list(zip(g, 0.02 * g + noise))
    falling = list(zip(g, -0.02 * g + noise))
    flat = list(zip(g, 1.0 + noise))
    beta, se = slope(rising)
    x, y = np.array(rising).T
    fit = np.polyfit(x, y, 1)
    resid = y - np.polyval(fit, x)
    assert beta == pytest.approx(fit[0], rel=1e-12)
    assert se == pytest.approx(math.sqrt(resid @ resid / (len(x) - 2) / ((x - x.mean()) ** 2).sum()), rel=1e-12)
    a_up, a_down = progress(rising), progress(falling)
    assert a_up > 10 and a_down > 10  # absolute progress: forgetting earns measurement too
    assert a_up == pytest.approx(max(0, abs(beta) / se - 1))
    assert progress(flat) < 2
    assert progress(rising[:2]) == 0.0  # fewer than three points: no evidence
    assert progress([(5, 1.0), (10, 1.0), (15, 1.0)]) == 0.0  # flat and exact: SE 0, no progress
    assert progress([(5, 1.0), (10, 2.0), (15, 3.0)]) == math.inf  # exact nonflat line


def test_lp_weights_formula_and_fallbacks():
    w = lp_weights([3.0, 1.0, 0.0], [0.0, 0.0, 0.0], 0.2)
    assert w == pytest.approx([0.2 / 3 + 0.8 * 0.75, 0.2 / 3 + 0.8 * 0.25, 0.2 / 3])
    assert sum(w) == pytest.approx(1)
    assert lp_weights([0, 0, 0], [0, 0, 0], 0.2) == pytest.approx([1 / 3] * 3)
    assert lp_weights([0, 0, 0], [0, 2, 0], 0.5) == pytest.approx([1 / 6, 1 / 6 + 0.5, 1 / 6])
    assert lp_weights([math.inf, 1, math.inf], [0, 0, 0], 0.2) == pytest.approx([0.2 / 3 + 0.4, 0.2 / 3,
                                                                                0.2 / 3 + 0.4])


def test_residual_variance_is_two_way_anova_interaction():
    genome, life = np.array([0.0, 1.0, 5.0])[:, None], np.array([0.0, -2.0, 3.0, 7.0])[None, :]
    assert residual_variance(genome + life) == pytest.approx(0.0, abs=1e-24)  # additive effects carry no noise
    x = genome + life + np.array([[1, -1, 0, 0], [-1, 1, 0, 0], [0, 0, 0, 0]], dtype=float)
    r = x - x.mean(1, keepdims=True) - x.mean(0, keepdims=True) + x.mean()
    assert residual_variance(x) == pytest.approx((r ** 2).sum() / (2 * 3))
    assert residual_variance(x[:1]) is None and residual_variance(x[:, :1]) is None


def test_allocator_recomputes_only_at_block_starts_and_follows_progress_and_noise():
    alloc = Allocator(conf(budget=18, floor=2, cap=10), TASKS)
    first = alloc.begin(0, [0, 0, 0])
    assert alloc.lives == [6, 6, 6] and first["w"] == pytest.approx([1 / 3] * 3) and first["sigma"] == [1, 1, 1]
    rng = np.random.default_rng(11)
    for g in range(1, 5):
        assert alloc.begin(g, [3, 3, 3]) is None and alloc.lives == [6, 6, 6]
        alloc.observe_noise(g, [4.0, 4.0, None])
    for p in range(5, 40, 5):  # task a improves steadily, b and c are flat noise (35: the block's own probe)
        alloc.add_probe(p, [0.1 * p + rng.normal(0, 0.05), rng.normal(0, 0.05), rng.normal(0, 0.05)])
    for g in range(30, 35):
        alloc.observe_noise(g, [1.0, 1.0, 1.0])
    block = alloc.begin(35, [0, 0, 0])
    assert block["generation"] == 35 and block["probe_points"] == 6 and block["noise_generations"] == 5
    assert block["a"][0] > 10 and block["a"][1] < 3
    assert alloc.lives[0] == 10 and sum(alloc.lives) == 18 and min(alloc.lives) >= 2
    # Neyman: equal weights, task c twice as noisy -> c gets the larger share of the flexible lives.
    noisy = Allocator(conf(budget=18, floor=2, cap=10), TASKS)
    noisy.begin(0, [0, 0, 0])
    for g in range(0, 5):
        noisy.observe_noise(g, [1.0, 1.0, 4.0])
    noisy.begin(5, [0, 0, 0])
    assert noisy.lives == [5, 5, 8]
    # Novelty: nu_t = weight * min(cap, events).
    novel = Allocator(conf(budget=18, floor=2, cap=10, novelty_cap=3, novelty_weight=1.0), TASKS)
    record = novel.begin(0, [7, 0, 1])
    assert record["nu"] == [3, 0, 1] and novel.lives[0] > novel.lives[2] > novel.lives[1]


def test_uniform_mode_is_equal_whatever_the_measurements():
    alloc = Allocator(conf(mode="uniform", budget=16), ("a", "b", "c", "d", "e"))
    alloc.begin(0, [3, 0, 0, 0, 0])
    assert alloc.lives == [4, 3, 3, 3, 3]
    for g in range(5):
        alloc.observe_noise(g, [9.0, 1.0, 1.0, 1.0, 1.0])
    alloc.add_probe(5, [1, 0, 0, 0, 0])
    alloc.begin(5, [3, 3, 3, 3, 3])
    assert alloc.lives == [4, 3, 3, 3, 3]


def test_state_round_trip_and_race_allocation():
    alloc = Allocator(conf(), TASKS)
    alloc.begin(0, [0, 0, 0])
    alloc.observe_noise(0, [1.0, None, 2.0])
    alloc.add_probe(5, [1.0, 2.0, 3.0])
    clone = Allocator(conf(), TASKS)
    clone.load(alloc.state)
    assert clone.state == alloc.state and clone.lives == alloc.lives
    assert alloc.race(24) == alloc.lives  # the same allocation when the race has the budget's lives
    alloc.state["allocation"] = [12, 8, 4]
    assert alloc.race(12) == [6, 4, 2] and alloc.race(5) == [2, 2, 1]


def test_probe_schedule():
    alloc = Allocator(conf(period=5), TASKS)
    assert [g for g in range(0, 21) if alloc.probe_due(g)] == [5, 10, 15, 20]
    assert not any(Allocator(conf(mode="uniform", probe_lives=0), TASKS).probe_due(g) for g in range(20))


@pytest.mark.parametrize("changes", [dict(mode="greedy"), dict(budget=5), dict(budget=25), dict(floor=0),
                                     dict(cap=1), dict(mix=1.5), dict(period=0), dict(probe_lives=0),
                                     dict(novelty_cap=-1), dict(unknown=1), dict(budget=24.0), dict(floor=True)])
def test_invalid_allocation_settings(changes):
    with pytest.raises(ValueError):
        Allocator(conf(**changes), TASKS)
    with pytest.raises(ValueError):
        Allocator(conf(), ())
