import math

import pytest
import torch

from src.cells import CellRule, run_cells
from src.lattice import build_lattice
from src.tasks import task_class
from src.tasks.base import direction_score
from src.tasks.withdraw import WithdrawTask

LAT = build_lattice("hex", 5)  # positions match the default radius-9 fabric; pokes and bodies fit inside
R = LAT.pos.norm(dim=1)


def _held(n=48, seed=0):
    return WithdrawTask().sample(LAT.pos, n, torch.Generator().manual_seed(seed), heldout=True)


def _score(alive, types, rule, trials, messages=True):
    act = run_cells(LAT, alive, types, rule, trials.stim, trials.window, messages=messages)
    return float(direction_score(act.counts, LAT.pos, alive, trials.target).mean()), act


def _rule(rows):
    """Up to 4 cell types from dicts of w, gs, bias, leak, refr, emit (missing types are silent)."""
    rule = CellRule(w=torch.zeros(1, 4, 2), gs=torch.zeros(1, 4, 2), bias=torch.zeros(1, 4),
                    leak=torch.full((1, 4), 0.5), refr=torch.zeros(1, 4, dtype=torch.long), emit=torch.zeros(1, 4, 2))
    for k, row in enumerate(rows):
        for name, value in row.items():
            getattr(rule, name)[0, k] = torch.tensor(value)
    return rule


def _ring_organism():
    """13 cells: a C-shaped ring of 11 relays on ring 2 (gap at the bottom), a silent centre and one silent connector.

    Relays fire when poked or when any neighbour fired last tick, then stay refractory for 2 ticks, so a poke starts a
    wave in each direction along the ring; the waves reach the far side 4-6 ticks later, in the response ticks.
    """
    ring = (R > 1.5) & (R < 2.5) & ((LAT.pos - torch.tensor([0.0, -3 ** 0.5])).norm(dim=1) > 0.1)
    silent = (R < 0.1) | ((LAT.pos - torch.tensor([1.0, 0.0])).norm(dim=1) < 0.1)
    alive = (ring | silent)[None]
    types = torch.where(silent, 1, 0)[None] * alive
    relay = dict(w=[1.0, 0.0], gs=[1.0, 0.0], refr=2, emit=[1.0, 0.0])
    return alive, types, _rule([relay, {}])


def test_registry_finds_the_task_and_trials_are_well_formed():
    assert task_class("withdraw") is WithdrawTask and WithdrawTask.rung_id >= 10
    task = WithdrawTask()
    for heldout in (False, True):
        tr = task.sample(LAT.pos, 24, torch.Generator().manual_seed(1), heldout=heldout)
        assert tr.stim.shape == (24, task.ticks, LAT.n, 2) and tr.window.shape == (24, task.ticks)
        assert task.ticks <= 40
        assert torch.allclose(tr.target.norm(dim=1), torch.ones(24))
        lit = tr.stim[..., 0] > 0  # [E, T, N]
        poke_ticks = lit.any(-1)  # [E, T]
        for e in range(24):
            ticks = poke_ticks[e].nonzero()[:, 0]
            assert 1 <= len(ticks) <= 2
            start, end = int(ticks[0]), int(ticks[-1])
            assert tr.window[e, start: end + 3].sum() == 0  # no window on the poke or the 2 ticks after it
            assert tr.window[e, end + 3:].sum() == task.response and tr.window[e, :start].sum() == start  # rest = every pre-poke tick
            assert start > 10  # after the latest first spontaneous spike of any quantized rule
            spot = LAT.pos[lit[e, start]].mean(0)
            assert float(spot @ tr.target[e]) < -1.0  # the poke sits on the side opposite the target
        ang = torch.atan2(-tr.target[:, 1], -tr.target[:, 0]) / (2 * math.pi / 12)
        off = ang - (0.5 if heldout else 0.0)
        assert (off - off.round()).abs().max() < 1e-3


def test_fire_where_lit_disk_scores_about_zero():
    alive = (R <= 3.01)[None]
    rule = _rule([dict(gs=[0.5, 0.0])])
    score, act = _score(alive, torch.zeros(1, LAT.n, dtype=torch.long), rule, _held())
    assert abs(score) < 0.15
    assert float(act.counts.sum()) == 0.0  # its poke responses never leak into the window


def test_tonic_firing_silenced_by_the_poke_is_diluted_by_the_rest_ticks():
    """'Withdraw by subtraction', the strongest no-message cheat found: two tonic cells at (+-2, 0), joined through the
    centre by silent cells, that the poke silences (light gain -2, slow leak). Without the rest ticks it would pay."""
    tonic = (LAT.pos[:, 1].abs() < 0.1) & ((LAT.pos[:, 0].abs() - 2).abs() < 0.1)
    alive = (tonic | ((LAT.pos[:, 1].abs() < 0.1) & (LAT.pos[:, 0].abs() < 1.1)))[None]
    types = torch.where(tonic, 0, 1)[None] * alive
    rule = _rule([dict(gs=[-2.0, 0.0], bias=0.5, leak=0.0625), {}])
    score, act = _score(alive, types, rule, _held(), messages=False)
    assert float(act.counts.sum()) > 0 and score < 0.15
    trials = _held()
    onset = (trials.stim[..., 0] > 0).any(-1).float().argmax(1)  # first poke tick per trial
    trials.window = trials.window * (torch.arange(trials.window.shape[1])[None] >= onset[:, None])  # drop the rest ticks
    assert _score(alive, types, rule, trials, messages=False)[0] > 0.2


def test_hand_built_ring_needs_messages():
    alive, types, rule = _ring_organism()
    assert int(alive.sum()) == 13
    trials = _held()
    with_msgs, _ = _score(alive, types, rule, trials)
    without, _ = _score(alive, types, rule, trials, messages=False)
    assert with_msgs >= 0.6
    assert without < 0.2


@pytest.mark.parametrize("heldout", [False, True])
def test_one_type_relay_disk_crosses_the_body(heldout):
    """The simplest message-passing answer, a radius-2 disk of one relay type, already gets well above chance."""
    alive = (R <= 2.01)[None]
    rule = _rule([dict(w=[1.0, 0.0], gs=[1.0, 0.0], refr=2, emit=[1.0, 0.0])])
    trials = WithdrawTask().sample(LAT.pos, 48, torch.Generator().manual_seed(2), heldout=heldout)
    score, _ = _score(alive, torch.zeros(1, LAT.n, dtype=torch.long), rule, trials)
    off, _ = _score(alive, torch.zeros(1, LAT.n, dtype=torch.long), rule, trials, messages=False)
    assert score > 0.35 and off == 0.0
