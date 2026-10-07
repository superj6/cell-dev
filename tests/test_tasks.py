import math

import pytest
import torch

from src.cells import CellRule, run_cells
from src.lattice import build_lattice
from src.tasks import RUNGS, Ladder
from src.tasks.base import angles, direction_score


def test_lateral_score_on_hand_made_activity():
    lat = build_lattice("hex", 3)
    alive = torch.ones(1, lat.n, dtype=torch.bool)
    target = torch.tensor([[1.0, 0.0]])
    on_axis = ((lat.pos[:, 1].abs() < 1e-4) & (lat.pos[:, 0] > 0)).float()
    assert float(direction_score(on_axis[None, None], lat.pos, alive, target)) == pytest.approx(1.0, abs=1e-5)
    assert float(direction_score(on_axis.flip(0)[None, None], lat.pos, alive, target)) == pytest.approx(-1.0, abs=1e-5)
    everywhere = torch.ones(1, 1, lat.n)
    assert abs(float(direction_score(everywhere, lat.pos, alive, target))) < 1e-5
    assert float(direction_score(torch.zeros(1, 1, lat.n), lat.pos, alive, target)) == 0.0


def test_angles_are_balanced_and_heldout_sits_between():
    g = torch.Generator().manual_seed(0)
    a = angles(24, g)
    assert sorted((a / (2 * math.pi / 12)).round().long().tolist()) == sorted(list(range(12)) * 2)
    h = angles(12, g, heldout=True) / (2 * math.pi / 12)
    assert torch.allclose(h - h.floor(), torch.full_like(h, 0.5))


def _naive_disk(lat):
    """'Fire where lit': a disk of one cell type that only senses light and sends nothing."""
    alive = (lat.pos.norm(dim=1) <= 3.01)[None]
    rule = CellRule(w=torch.zeros(1, 4, 2), gs=torch.tensor([[[0.5, 0.0]] * 4]), bias=torch.zeros(1, 4),
                    leak=torch.full((1, 4), 0.5), refr=torch.zeros(1, 4, dtype=torch.long), emit=torch.zeros(1, 4, 2))
    return alive, torch.zeros(1, lat.n, dtype=torch.long), rule


@pytest.mark.parametrize("cls", RUNGS)
def test_naive_policy_only_solves_the_first_rung(cls):
    lat = build_lattice("hex", 9)
    alive, types, rule = _naive_disk(lat)
    trials = cls().sample(lat.pos, 48, torch.Generator().manual_seed(0), heldout=True)
    score = float(direction_score(run_cells(lat, alive, types, rule, trials.stim, trials.window).counts, lat.pos,
                                  alive, trials.target).mean())
    if cls.rung_id == 0:
        assert score > 0.5
    else:
        assert score < 0.3, cls.name


def test_ladder_keeps_the_current_rung_whole_and_revisits_one_earlier_rung():
    pos = build_lattice("hex", 4).pos
    lad = Ladder(start=2)
    for seed in range(5):
        t = lad.sample(pos, 12, torch.Generator().manual_seed(seed))
        assert int((t.rung == 2).sum()) == 12  # the current rung keeps its full, balanced set
        old = t.rung[t.rung < 2]
        assert len(old) == 4 and old.unique().numel() == 1  # an even number of extra trials from one earlier rung
        assert t.stim.shape[:2] == t.window.shape
    assert Ladder(start=2, keep_earlier=0.0).sample(pos, 12, torch.Generator().manual_seed(0)).n == 12


def test_message_ladder_keeps_context_pairs_balanced():
    """A cue-blind 'face the light' tissue must score exactly 0 on the context share of a ladder sample."""
    lat = build_lattice("hex", 9)
    lad = Ladder(start=2, rungs=["withdraw", "context", "jump"])
    alive, types, rule = _naive_disk(lat)
    for seed in range(4):
        t = lad.sample(lat.pos, 12, torch.Generator().manual_seed(seed))
        if not (t.rung == lad.rungs[1].rung_id).any():
            continue
        s = direction_score(run_cells(lat, alive, types, rule, t.stim, t.window).counts, lat.pos, alive, t.target)[0]
        assert abs(float(s[t.rung == lad.rungs[1].rung_id].sum())) < 1e-4
