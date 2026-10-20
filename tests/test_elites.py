"""Behaviour-grid bookkeeping on supplied scores only: no simulator, search or genetic operator calls."""
import math

import numpy as np
import pytest
import torch

from src.elites import Elites, Grid, beats, contest, descriptor_lives, novel, paired, parse_descriptor

TASKS = ("pool", "patches", "decoy")


def conf(**changes):
    base = dict(shape=[4, 4], descriptors=dict(pool=["captures", "misses"],
                                               patches=["patch_harvest_0/patch_source_0", "misses"]),
                bounds=dict(pool=[[0, 32], [0, 64]], patches=[[0, 1], [0, 64]]))
    return dict(base, **changes)


def test_descriptor_syntax_columns_and_ratio_with_zero_denominator():
    assert parse_descriptor("captures") == ("captures", None)
    assert parse_descriptor(" a / b ") == ("a", "b")
    for bad in ("", "a/", "/b", "a/b/c"):
        with pytest.raises(ValueError):
            parse_descriptor(bad)
    elites = Elites(conf(), TASKS, size=5, genes=2)
    assert elites.columns == ("captures", "misses", "patch_harvest_0", "patch_source_0")
    assert [g.task for g in elites.grids] == ["pool", "patches"]  # task order; decoy declares no grid
    life = np.array([[[3, 9, 2, 4], [5, 1, 1, 0]]], dtype=float)  # one genome, two lives
    assert descriptor_lives(life, elites.columns, ("captures", None)).tolist() == [[3, 5]]
    assert descriptor_lives(life, elites.columns, ("patch_harvest_0", "patch_source_0")).tolist() == [[0.5, 0.0]]
    assert elites.describe(elites.grids[1], life).tolist() == [[0.25, 5.0]]


def test_cells_use_fixed_bounds_clip_to_edges_and_reject_nonfinite():
    grid = Grid("pool", [("a", None), ("b", None)], [[0, 4], [0, 8]], [4, 2], size=3, genes=1)
    desc = np.array([[0, 0], [0.99, 7.9], [1, 4], [3.999, 3.999], [-5, 100], [9, -1], [np.nan, 1], [2, np.inf]])
    assert grid.cells(desc).tolist() == [0, 1, 3, 6, 1, 6, -1, -1]


def test_running_mean_with_count_cap():
    grid = Grid("pool", [("a", None), ("b", None)], [[0, 1], [0, 1]], [1, 1], size=2, genes=1)
    grid.place(0, torch.ones(2), 7, 3, torch.tensor([5]), [1.0, 3.0], generation=4, cap=4)
    assert float(grid.value[0]) == 2.0 and int(grid.count[0]) == 2 and int(grid.since[0]) == 4
    grid.observe(0, [5.0, 7.0], cap=4)
    assert float(grid.value[0]) == 4.0 and int(grid.count[0]) == 4
    grid.observe(0, [8.0], cap=4)  # beyond the cap each life weighs 1/cap
    assert float(grid.value[0]) == 5.0 and int(grid.count[0]) == 4
    clone = Grid("pool", [("a", None), ("b", None)], [[0, 1], [0, 1]], [1, 1], size=2, genes=1)
    clone.load(grid.state())
    assert all(torch.equal(getattr(clone, k), getattr(grid, k)) for k in Grid.TENSORS)


def test_paired_estimate_and_one_se_rule():
    inc = np.array([1.0, 2.0, 3.0, 4.0])
    assert paired(inc + 1, inc) == (1.0, 0.0)
    d = np.array([0.5, -0.1, 0.4, 0.0])
    mean, se = paired(inc + d, inc)
    assert mean == pytest.approx(d.mean()) and se == pytest.approx(d.std(ddof=1) / 2)
    assert beats(inc + d, inc, 1.0) == (d.mean() >= d.std(ddof=1) / 2)
    assert not beats(inc + d, inc, 10.0)
    assert not beats(inc - 1, inc, 0.0)  # never a non-positive gain
    assert paired([2.0], [1.0]) == (1.0, math.inf) and not beats([2.0], [1.0], 1.0)  # one life: no SE


def test_contest_fills_empty_cells_and_replaces_only_beyond_one_se():
    cells = np.array([0, 0, 1, 2, 2, -1])
    shared = np.array([[1.0, 1.0, 1.0],   # cell 0 challenger (worse)
                       [2.0, 2.2, 1.9],   # cell 0 best -> beats incumbent 0 clearly
                       [5.0, 5.0, 5.0],   # cell 1, empty -> fills
                       [1.1, 0.9, 1.05],  # cell 2: best but within noise of incumbent
                       [0.0, 0.0, 0.0],
                       [9.0, 9.0, 9.0]])  # no cell (non-finite descriptor)
    filled = np.array([True, False, True, False])
    incumbents = {0: np.array([1.0, 1.1, 1.0]), 2: np.array([1.0, 1.0, 1.0])}
    won = contest(cells, shared, filled, incumbents, z=1.0)
    assert [(a["cell"], a["row"], a["replaced"]) for a in won] == [(0, 1, True), (1, 2, False)]
    d = shared[1] - incumbents[0]
    assert won[0]["d"] == pytest.approx(d.mean()) and won[0]["se"] == pytest.approx(d.std(ddof=1) / math.sqrt(3))
    # The same gain on noisier shared lives stays below one SE.
    noisy = shared.copy()
    noisy[3] = [3.0, -1.0, 1.15]
    assert not [a for a in contest(cells, noisy, filled, incumbents, z=1.0) if a["cell"] == 2]
    assert [a["cell"] for a in contest(cells, noisy, filled, incumbents, z=0.0)] == [0, 1, 2]
    # Ties go to the lower row; skipped rows (copies of an incumbent) never challenge.
    tie = contest(np.array([3, 3]), np.ones((2, 3)), filled, incumbents, z=1.0)
    assert tie == [dict(cell=3, row=0, replaced=False, d=None, se=None)]
    assert contest(np.array([3, 3]), np.ones((2, 3)), filled, incumbents, z=1.0, skip=[0])[0]["row"] == 1


def test_novel_candidates_are_best_of_empty_unrepresented_cells():
    cells = [np.array([0, 1, 1, 2, 3, 3]), np.array([0, 0, 1, 1, 1, 2])]
    scores = [np.array([9.0, 1.0, 2.0, 8.0, 3.0, 4.0]), np.array([1.0, 2.0, 3.0, 9.0, 4.0, 5.0])]
    filled = [np.array([False, False, True, False]), np.array([False, False, False, False])]
    top = [0, 3]  # already raced: row 0 (grid 0 cell 0, grid 1 cell 0) and row 3 (grid 1 cell 1)
    # grid 0: cell 1 -> row 2 (rank 4/5), cell 3 -> row 5 (rank 2/5); cell 2 is filled, cell 0 has a top row.
    # grid 1: cell 2 -> row 5 (1/5); cells 0 and 1 hold top rows. Row 5 appears once.
    assert novel(cells, scores, filled, top, 10) == [5, 2]
    assert novel(cells, scores, filled, top, 1) == [5]
    assert novel(cells, scores, filled, top, 0) == []
    # With only row 3 raced: grid 0 cell 0 -> row 0 (rank 0); grid 1 cell 0 -> row 1 (rank 4/5, after grid 0's
    # equal-rank row 2).
    assert novel(cells, scores, filled, [3], 10) == [0, 5, 2, 1]


def test_parent_cells_events_and_state_round_trip():
    elites = Elites(conf(), TASKS, size=4, genes=2)
    elites.grids[0].place(5, torch.zeros(4), 11, 1, torch.tensor([3, -1]), [1.0], 0, 64)
    elites.grids[1].place(2, torch.ones(4), 12, 2, torch.tensor([4, 5]), [2.0], 0, 64)
    assert elites.filled() == [(0, 5), (1, 2)]
    elites.events += [[3, 0, 5, 11], [9, 0, 6, 13], [9, 1, 2, 12], [12, 1, 3, 14]]
    assert elites.novelty_counts(12, 10) == [2, 1, 0]  # generations 2..11, per training task
    assert elites.novelty_counts(14, 10) == [1, 2, 0]  # generations 4..13
    again = Elites(conf(), TASKS, size=4, genes=2)
    again.load(elites.state())
    assert again.filled() == elites.filled() and again.events == elites.events
    assert again.grids[1].ids[2] == 12 and again.grids[1].origins[2].tolist() == [4, 5]


@pytest.mark.parametrize("changes", [dict(shape=[4]), dict(shape=[0, 4]), dict(descriptors={}),
                                     dict(descriptors=dict(other=["a", "b"]), bounds=dict(other=[[0, 1], [0, 1]])),
                                     dict(bounds=dict(pool=[[0, 32], [0, 64]])),
                                     dict(bounds=dict(pool=[[1, 1], [0, 64]], patches=[[0, 1], [0, 64]])),
                                     dict(cap=0), dict(admit_z=-1), dict(parent_share=1.5), dict(unknown=1)])
def test_invalid_elite_settings(changes):
    with pytest.raises(ValueError):
        Elites(conf(**changes), TASKS, size=4, genes=2)
