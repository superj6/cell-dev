import math

import pytest
import torch

from src.cells import CellRule, run_cells
from src.lattice import build_lattice
from src.tasks import task_class
from src.tasks.base import direction_score
from src.tasks.context import ContextTask

LAT = build_lattice("hex", 5)  # same site positions as the default radius-9 fabric, fewer empty sites to simulate


def _score(alive, types, rule, trials, messages=True) -> torch.Tensor:
    act = run_cells(LAT, alive, types, rule, trials.stim, trials.window, messages=messages)
    return direction_score(act.counts, LAT.pos, alive, trials.target)[0]


def _naive_disk():
    """'Fire where lit': a disk of one cell type that only senses light and sends nothing."""
    alive = (LAT.pos.norm(dim=1) <= 3.01)[None]
    rule = CellRule(w=torch.zeros(1, 4, 2), gs=torch.tensor([[[0.5, 0.0]] * 4]), bias=torch.zeros(1, 4),
                    leak=torch.full((1, 4), 0.5), refr=torch.zeros(1, 4, dtype=torch.long), emit=torch.zeros(1, 4, 2))
    return alive, torch.zeros(1, LAT.n, dtype=torch.long), rule


def _context_switch():
    """7 cells: a hub H at the centre, bright cells B at 0/120/240 degrees and dim cells D at 60/180/300 degrees.

    Any cue-sensing cell fires during the cue (B relays it to D on channel 1). H and D then ping-pong on channel 0
    (refractory 1 locks them to period 2), which holds the context through the dark gap and inhibits B. When the
    light comes on, D cells on the bright side drop out of the loop and the dim-side ones keep it going, so cued
    firing sits at -u; the hub's own spikes sit at the body centre and do not count. Without the cue H and D stay
    silent and B fires where lit (+u).
    """
    alive = (LAT.pos.norm(dim=1) <= 1.01)[None]
    sector = torch.round(torch.atan2(LAT.pos[:, 1], LAT.pos[:, 0]) / (math.pi / 3)).long() % 6
    ring = alive[0] & (LAT.pos.norm(dim=1) > 0.5)
    types = torch.zeros(1, LAT.n, dtype=torch.long)
    types[0, ring & (sector % 2 == 0)] = 1
    types[0, ring & (sector % 2 == 1)] = 2
    rule = CellRule(
        w=torch.tensor([[[1.0, 0.0], [-2.0, 0.0], [2.0, 0.75], [0.0, 0.0]]]),  # H, B, D, unused
        gs=torch.tensor([[[0.0, 2.0], [1.0, 2.0], [-1.5, 2.0], [0.0, 0.0]]]),
        bias=torch.tensor([[0.0, -0.625, 0.375, 0.0]]),
        leak=torch.full((1, 4), 0.5),
        refr=torch.tensor([[1, 1, 1, 0]]),
        emit=torch.tensor([[[1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, 0.0]]]),
    )
    return alive, types, rule


def _cue_ticks(stim):  # [E, T, N, 2] -> [E, T] bool, cue on anywhere
    return stim[..., 1].sum(-1) > 0


def test_registry_finds_the_task():
    assert task_class("context") is ContextTask and ContextTask.rung_id >= 10


@pytest.mark.parametrize("heldout", [False, True])
def test_trials_are_paired_balanced_and_short(heldout):
    task = ContextTask()
    t = task.sample(LAT.pos, 48, torch.Generator().manual_seed(1), heldout=heldout)
    E, T = t.window.shape
    assert E == 48 and T <= 40 and t.stim.shape == (48, T, LAT.n, 2)
    cued = _cue_ticks(t.stim).any(1)
    assert cued[24:].all() and not cued[:24].any()
    # each cued trial is the twin of an uncued one: same light and window, opposite target
    assert torch.equal(t.stim[24:, ..., 0], t.stim[:24, ..., 0]) and torch.equal(t.window[24:], t.window[:24])
    assert torch.allclose(t.target[24:], -t.target[:24])
    for half in (t.target[:24], t.target[24:]):  # directions balanced within each half
        assert half.sum(0).norm() < 1e-4
    k = torch.atan2(t.target[:, 1], t.target[:, 0]) / (2 * math.pi / 12)  # held-out: halfway between training
    off = (k - k.round()).abs()
    assert torch.allclose(off, torch.full_like(off, 0.5 if heldout else 0.0), atol=1e-3)
    # the cue is a small spot near the centre and ends before the light comes on
    spot = t.stim[24:, ..., 1].amax(1)  # [24, N]
    assert ((spot.sum(1) >= 1) & (spot.sum(1) <= 7)).all()
    assert float((LAT.pos.norm(dim=1)[None] * spot).max()) <= task.cue_reach + task.cue_radius + 1e-3
    light_on = t.stim[..., 0].sum(-1) > 0
    assert not (_cue_ticks(t.stim) & light_on).any() and not (_cue_ticks(t.stim) & (t.window > 0)).any()
    assert (t.window.sum(1) == task.view).all()


def test_heldout_gap_is_longer():
    task = ContextTask()

    def gaps(heldout):
        t = task.sample(LAT.pos, 48, torch.Generator().manual_seed(2), heldout=heldout)
        cue_end = _cue_ticks(t.stim[24:]).float().cumsum(1).argmax(1)
        onset = (t.stim[24:, ..., 0].sum(-1) > 0).float().argmax(1)
        return onset - cue_end - 1

    train, held = gaps(False), gaps(True)
    assert int(train.min()) >= task.train_gap[0] and int(train.max()) <= task.train_gap[1]
    assert int(held.min()) > int(train.max())


def test_cue_site_carries_no_direction():
    small = build_lattice("hex", 3)  # holds every possible cue spot
    t = ContextTask().sample(small.pos, 4000, torch.Generator().manual_seed(3))
    spot = t.stim[2000:, ..., 1].amax(1)
    where = (spot @ small.pos) / spot.sum(1, keepdim=True)
    assert abs(float((where * t.target[2000:]).sum(1).mean())) < 0.1  # standard error about 0.03


def test_ignoring_the_cue_scores_zero():
    trials = ContextTask().sample(LAT.pos, 48, torch.Generator().manual_seed(0), heldout=True)
    alive, types, rule = _naive_disk()
    s = _score(alive, types, rule, trials)
    assert float(s[:24].mean()) > 0.5  # it does face the light ...
    assert abs(float(s.mean())) < 0.15  # ... but the cued twins cancel it
    alive, types, rule = _context_switch()
    rule.gs[..., 1] = 0.0  # the hand-built organism, made blind to the cue
    assert abs(float(_score(alive, types, rule, trials).mean())) < 1e-4


def test_hand_built_context_switch_needs_messages():
    alive, types, rule = _context_switch()
    assert int(alive.sum()) == 7
    for seed in (0, 1):
        trials = ContextTask().sample(LAT.pos, 48, torch.Generator().manual_seed(seed), heldout=True)
        s = _score(alive, types, rule, trials)
        assert float(s.mean()) >= 0.6 and float(s[24:].mean()) >= 0.6
        assert abs(float(_score(alive, types, rule, trials, messages=False).mean())) < 0.2
