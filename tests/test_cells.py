import torch

from src.cells import LEAKS, CellRule, decode_cells, run_cells
from src.genome import Dims, Layout
from src.lattice import build_lattice


def _relay_rule(refr=2):
    """Type 0: relays any channel-0 spike from a neighbour, emits on channel 0, refractory so it cannot echo back."""
    return CellRule(w=torch.tensor([[[1.0, 0.0]] * 4]), gs=torch.tensor([[[1.0, 0.0]] * 4]), bias=torch.zeros(1, 4),
                    leak=torch.full((1, 4), 0.5), refr=torch.full((1, 4), refr, dtype=torch.long),
                    emit=torch.tensor([[[1.0, 0.0]] * 4]))


def _chain(lat, length=6):
    """Sites along +x from the centre."""
    idx = [int(((lat.pos - torch.tensor([float(k), 0.0])).norm(dim=1)).argmin()) for k in range(length)]
    alive = torch.zeros(1, lat.n, dtype=torch.bool)
    alive[0, idx] = True
    return idx, alive


def _kick(lat, site, T):
    stim = torch.zeros(1, T, lat.n, 2)
    stim[0, 0, site, 0] = 1.0
    return stim, torch.ones(1, T)


def test_spike_travels_exactly_one_hop_per_tick():
    for kind in ("hex", "square4", "square8"):
        lat = build_lattice(kind, 6)
        idx, alive = _chain(lat)
        stim, window = _kick(lat, idx[0], 10)
        act = run_cells(lat, alive, torch.zeros(1, lat.n, dtype=torch.long), _relay_rule(), stim, window, record=True)
        fire_tick = [int(act.raster[:, 0, 0, i].nonzero()[0]) for i in idx]
        assert fire_tick == list(range(len(idx))), kind
        assert int(act.raster[:, 0, 0].sum()) == len(idx)  # each cell fires once: no echoes


def test_messages_off_blocks_relay_and_dead_sites_stay_silent():
    lat = build_lattice("hex", 6)
    idx, alive = _chain(lat)
    stim, window = _kick(lat, idx[0], 10)
    types = torch.zeros(1, lat.n, dtype=torch.long)
    act = run_cells(lat, alive, types, _relay_rule(), stim, window, messages=False, record=True)
    assert int(act.raster.sum()) == 1
    stim[0, :, :, 0] = 5.0  # bright everywhere
    act = run_cells(lat, alive, types, _relay_rule(), stim, window, record=True)
    assert not act.raster[:, 0, 0][:, ~alive[0]].any()


def test_refractory_period_spaces_spikes():
    lat = build_lattice("hex", 2)
    alive = torch.zeros(1, lat.n, dtype=torch.bool)
    alive[0, lat.center] = True
    rule = _relay_rule(refr=2)
    rule.bias[:] = 2.0  # always above threshold
    T = 12
    act = run_cells(lat, alive, torch.zeros(1, lat.n, dtype=torch.long), rule, torch.zeros(1, T, lat.n, 2),
                    torch.ones(1, T), record=True)
    assert act.raster[:, 0, 0, lat.center].nonzero()[:, 0].tolist() == list(range(0, T, 3))


def test_decoded_rule_is_quantized():
    lay = Layout(Dims())
    rule = decode_cells(lay, lay.random(64, torch.Generator().manual_seed(1), scale=3.0))
    for x in (rule.w, rule.gs, rule.bias):
        assert x.abs().max() <= 2.0 and torch.equal(x * 8, (x * 8).round())
    assert set(rule.leak.unique().tolist()) <= set(LEAKS.tolist())
    assert rule.refr.min() >= 0 and rule.refr.max() <= 3
    assert set(rule.emit.unique().tolist()) <= {0.0, 1.0}
