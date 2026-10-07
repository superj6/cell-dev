import math

import pytest
import torch

from src.cells import CellRule, run_cells
from src.lattice import build_lattice
from src.tasks import task_class
from src.tasks.base import direction_score
from src.tasks.jump import JumpTask, paired_angles

LAT = build_lattice("hex", 5)  # positions match the default radius-9 fabric; flashes and bodies fit inside
R = LAT.pos.norm(dim=1)


@pytest.fixture(autouse=True, scope="module")
def _few_threads():  # these simulations are tiny; many threads only contend (and the machine may be busy)
    before = torch.get_num_threads()
    torch.set_num_threads(2)
    yield
    torch.set_num_threads(before)


def _held(n=48, seed=0):
    return JumpTask().sample(LAT.pos, n, torch.Generator().manual_seed(seed), heldout=True)


def _train(n=48, seed=2):
    return JumpTask().sample(LAT.pos, n, torch.Generator().manual_seed(seed))


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


def _onsets(trials):
    """Per trial: (A's onset, B's onset)."""
    lit = trials.stim[..., 0] > 0
    out = []
    for e in range(trials.n):
        ticks = lit[e].any(-1).nonzero()[:, 0].tolist()
        out.append((ticks[0], ticks[2]))
    return out


def _relay_organism():
    """19 cells (disk of radius 2): relays on one of the three hex sublattices, senders on the other two.

    Sender (type 0): light gain 3/8, so a lit sender stays below threshold on a flash's first tick (2.1 * 3/8 = 0.79)
    and fires on its second tick, which the window never reads. It weighs relay spikes (channel 1) at 3/8 and leaks 1/8
    per tick, so a relayed spike primes it for several ticks: a primed sender that gets lit fires on the first tick,
    which the window reads. Relay (type 1): blind to light, fires once on any sender spike (channel 0).
    A's lit senders fire, relays pass it on, and B's senders (up to 2 hops further) are primed when B flashes: only B
    fires on a read tick. B's own relays act after B's read ticks, and A's senders were lit before any prime arrived.
    """
    r = torch.round(LAT.pos[:, 1] * 2 / math.sqrt(3)).long()
    q = torch.round(LAT.pos[:, 0] - r / 2).long()
    alive = (R <= 2.01)[None]
    types = (((q - r) % 3 == 0).long())[None] * alive
    sender = dict(gs=[0.375, 0.0], w=[0.0, 0.375], leak=0.125, refr=3, emit=[1.0, 0.0])
    relay = dict(w=[1.0, 0.0], refr=3, emit=[0.0, 1.0])
    return alive, types, _rule([sender, relay])


def test_registry_finds_the_task_and_trials_are_well_formed():
    assert task_class("jump") is JumpTask and JumpTask.rung_id >= 10
    task = JumpTask()
    assert task.ticks <= 40
    for heldout in (False, True):
        n = 24
        tr = task.sample(LAT.pos, n, torch.Generator().manual_seed(1), heldout=heldout)
        assert tr.stim.shape == (n, task.ticks, LAT.n, 2) and tr.window.shape == (n, task.ticks)
        assert torch.allclose(tr.target.norm(dim=1), torch.ones(n)) and float(tr.stim[..., 1].abs().sum()) == 0.0
        ang = torch.atan2(tr.target[:, 1], tr.target[:, 0]) / (2 * math.pi / 12)
        off = ang - (0.5 if heldout else 0.0)
        assert (off - off.round()).abs().max() < 1e-3
        assert sorted(((off.round().long()) % 12).tolist()) == sorted(list(range(12)) * 2)  # balanced
        first, last = task.heldout_onset if heldout else task.train_onset
        lit = tr.stim[..., 0] > 0  # [E, T, N]
        spots = []
        for e in range(n):
            ticks = lit[e].any(-1).nonzero()[:, 0].tolist()
            t0 = ticks[0]
            gap = ticks[2] - t0
            assert gap in (task.heldout_gaps if heldout else task.train_gaps) and first <= t0 <= last
            assert ticks == [t0, t0 + 1, t0 + gap, t0 + gap + 1]  # two 2-tick flashes
            a, b = lit[e, t0], lit[e, t0 + gap]
            assert not (a & b).any() and a.any() and b.any()  # identical-size spots, never overlapping
            jump = LAT.pos[b].mean(0) - LAT.pos[a].mean(0)
            assert float(jump @ tr.target[e]) > 1.5 and float(LAT.pos[a | b].mean(0).norm()) < 2.0
            read = [t for t in range(task.ticks) if tr.window[e, t] > 0 and t >= t0]
            assert read == [t0, t0 + gap, t0 + 2 * gap]
            assert tr.window[e, :t0].sum() == task.rest and tr.window[e, t0 - task.rest: t0].all()
            spots.append((t0, gap, a, b))
        # u and -u in the same block of 12 flash the same two spots in opposite orders, with the same timing
        for i in range(n):
            j = [j for j in range(n) if j // 12 == i // 12 and torch.allclose(tr.target[j], -tr.target[i], atol=1e-5)]
            assert len(j) == 1
            (t0, gap, a, b), (t0j, gapj, aj, bj) = spots[i], spots[j[0]]
            assert (t0, gap) == (t0j, gapj) and torch.equal(a, bj) and torch.equal(b, aj)


@pytest.mark.parametrize("n", [9, 17])
def test_a_cut_block_keeps_whole_pairs(n):  # e.g. 9 jump trials out of 12 on a ladder that keeps earlier rungs
    theta = paired_angles(n, torch.Generator().manual_seed(3))
    k = (theta / (2 * math.pi / 12)).round().long() % 12
    for b in range(0, n, 12):
        kb = k[b:b + 12].tolist()
        assert len(set(kb)) == len(kb)
        assert sum((x + 6) % 12 in kb for x in kb) >= 2 * (len(kb) // 2)  # at most one trial without its -u partner


def test_fire_where_lit_disk_scores_zero_although_it_fires_on_the_read_ticks():
    alive = (R <= 3.01)[None]
    score, act = _score(alive, torch.zeros(1, LAT.n, dtype=torch.long), _rule([dict(gs=[0.5, 0.0])]), _held())
    assert abs(score) < 0.15
    assert float((act.counts.sum(-1) > 0).float().mean()) == 1.0  # it does respond on both onsets in every trial


@pytest.mark.parametrize("cell", [
    dict(gs=[0.375, 0.0], bias=0.125, leak=0.5, refr=1),  # settles just below threshold (exactly at it if level were 2)
    dict(gs=[0.125, 0.0], bias=0.125, leak=0.125, refr=0),  # slowest positive ramp
    dict(gs=[0.25, 0.0], bias=0.125, leak=0.25, refr=0),  # ramp that decides onset firing until tick 11
    dict(gs=[0.125, 0.0], bias=0.125, leak=0.0625, refr=3),  # slowest tonic oscillator (period 14)
])
def test_single_cell_clocks_do_not_tell_the_flashes_apart(cell):
    """No single-cell clock fires more at B than at A. (The tonic one leans the other way: about -0.08 over 480
    held-out trials, -0.21 on this 48-trial set. Firing at A cannot be turned around without messages, and with
    messages a clock is bounded by the test below.)"""
    alive = (R <= 2.01)[None]
    for trials in (_held(), _train()):
        score, _ = _score(alive, torch.zeros(1, LAT.n, dtype=torch.long), _rule([cell]), trials, messages=False)
        assert -0.25 < score < 0.1


def test_a_body_wide_clock_can_barely_tell_which_flash_came_second():
    """B always comes D ticks after A, so a clock (time since the trial began) is a shortcut needing no A-to-B traffic.

    The strongest one: every lit body cell fires on its flash's onset tick iff the onset is at or after tick tau (else
    on the unread second tick). Over a uniform onset range of W ticks it separates A from B in at most D/W of the
    trials.
    Then a real one (red-team, scored 0.50 held-out when onsets were 15-22 and D was 5-6): an unlit tonic cell at the
    body centre (offset 0, so its own spikes cost nothing) whose spikes build up in a ring of light senders that emit
    nothing, making them fire on the onset tick only late in the trial.
    """
    alive = (R <= 3.01)[None]
    for trials, bound in ((_held(480, 5), 0.25), (_train(480, 6), 0.2)):  # here 0.196 and 0.173 (0.58 / 0.38 before)
        lit = trials.stim[..., 0] > 0
        onset = lit & ~torch.cat([torch.zeros_like(lit[:, :1]), lit[:, :-1]], 1)
        for tau in range(trials.window.shape[1] + 1):
            fire = onset & (torch.arange(trials.window.shape[1])[None, :, None] >= tau)
            counts = (fire.float() * trials.window[..., None]).sum(1)[None] * alive[:, None].float()
            assert float(direction_score(counts, LAT.pos, alive, trials.target).mean()) < bound, tau
    ring = (R <= 1.01)[None]
    types = ((R > 0.5).long() * ring[0])[None]
    clock = dict(bias=1 / 8, leak=1 / 16, refr=1, emit=[0.0, 1.0])  # spikes at ticks 10, 22, 34
    sender = dict(gs=[0.25, 0.0], w=[0.0, 0.5], leak=1 / 16, refr=2)
    for trials in (_held(96), _train(96)):
        assert _score(ring, types, _rule([clock, sender]), trials)[0] < 0.15


def test_hand_built_relay_organism_needs_messages_and_the_interaction_of_the_flashes():
    alive, types, rule = _relay_organism()
    assert int(alive.sum()) == 19
    trials = _held(96)  # ~0.67 here and over 480 trials; 48-trial sets range 0.61-0.71
    with_msgs, act = _score(alive, types, rule, trials)
    without, _ = _score(alive, types, rule, trials, messages=False)
    assert with_msgs >= 0.6, with_msgs
    assert abs(without) < 0.2, without
    assert _score(alive, types, rule, _train())[0] >= 0.6
    # superposition: run each flash alone; their summed responses (minus the blank run) must score nothing, so the
    # score comes from A's activity changing B's response, not from either flash on its own
    a_only, b_only = trials.stim.clone(), trials.stim.clone()
    for e, (_, tb) in enumerate(_onsets(trials)):
        a_only[e, tb:] = 0
        b_only[e, :tb] = 0
    counts = [run_cells(LAT, alive, types, rule, s, trials.window).counts
              for s in (a_only, b_only, torch.zeros_like(trials.stim))]
    alone = direction_score((counts[0] + counts[1] - counts[2]).clamp(min=0), LAT.pos, alive, trials.target).mean()
    assert abs(float(alone)) < 0.1
