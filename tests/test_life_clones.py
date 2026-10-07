"""Counterfactual forks of a genome's life (src/life/clones.py): the twin is the life itself, a fork that changes
nothing continues bitwise, spikes undelivered from t_f deliver nothing but are still charged, and a control that
holds the kernel's single fork slot is reported instead of forked."""
from dataclasses import replace

import numpy as np
import pytest
import torch

from src.genome import LifeDims, LifeLayout
from src.life import build, clones, spec
from tests.life_helpers import bits

LAY = LifeLayout(LifeDims())
W = spec.world(T=200.0, oracle_cap=30)
SEEDS = [11, 12]


@pytest.fixture(scope="module")
def talker() -> np.ndarray:
    """A packed founder that grows, spikes and sends contact events (p_die is 0 in every founder)."""
    x = LAY.random(256, torch.Generator().manual_seed(5))
    gt = LAY.pack(x)
    res = build.run(W, [11] * 256, genomes=gt, genome_of=np.arange(256), threads=4)
    i = next(i for i in range(256) if res["contact_events"][i] > 2000 and res["n_peak"][i] >= 20
             and res["arrivals"][i] > 1000 and not res.status("guard_cells")[i])
    return gt[i:i + 1]


def test_fork_worlds():
    w = clones.fork_world(W, 100.0, "contacts_off")
    assert (w.t_fork, w.t_open, w.fork_flags) == (100.0, 100.0, spec.FLAGS["contacts_off"])
    twin = clones.fork_world(W, 100.0, None)
    assert twin.fork_flags == 0 and twin.t_open == 100.0
    frozen = replace(W, t_fork=50.0, fork_flags=spec.FLAGS["freeze"])  # the freeze-after-growth control
    assert clones.fork_world(frozen, 100.0, "chem_off") is None
    both = clones.fork_world(frozen, 50.0, "chem_off")
    assert both.fork_flags == spec.FLAGS["freeze"] | spec.FLAGS["chem_off"] and both.t_fork == 50.0


def test_the_twin_is_the_life_with_its_ledger_opened_at_the_fork(talker):
    twin = clones.fork_world(W, 100.0, None)
    a = build.run(twin, SEEDS, genomes=talker, raster_cap=50_000)
    b = build.run(replace(W, t_open=100.0), SEEDS, genomes=talker, raster_cap=50_000)
    assert np.array_equal(bits(a.ledger), bits(b.ledger)) and np.array_equal(a.hashes, b.hashes)
    whole = build.run(W, SEEDS, genomes=talker, raster_cap=50_000)
    for i in range(2):  # the same spikes as the unforked life
        assert np.array_equal(bits(a.spikes(i)[0]), bits(whole.spikes(i)[0]))


def test_a_fork_that_changes_nothing_continues_bitwise(talker):
    rows = clones.run_forks(talker, W, SEEDS, [0.5], ["apoptosis_off"], threads=2)  # founders never die
    assert len(rows) == 1 and rows[0]["d_income"] == 0.0 and rows[0]["d_F"] == 0.0
    a = build.run(clones.fork_world(W, 100.0, "apoptosis_off"), SEEDS, genomes=talker)
    b = build.run(clones.fork_world(W, 100.0, None), SEEDS, genomes=talker)
    assert np.array_equal(bits(a.ledger), bits(b.ledger)) and np.array_equal(a.hashes, b.hashes)


def test_spikes_undelivered_from_t_are_still_charged(talker):
    rows = {r["condition"]: r for r in clones.run_forks(talker, W, SEEDS, [0.5], clones.CONDITIONS, threads=2)}
    assert set(rows) == set(clones.CONDITIONS)
    deaf = rows["contacts_off"]
    assert deaf["arrivals_fork"] < 0.05 * deaf["arrivals_twin"]  # only spikes sent before the fork still land
    late = replace(clones.fork_world(W, 100.0, "contacts_off"), t_open=110.0)  # after every in-flight spike
    res = build.run(late, SEEDS, genomes=talker)
    assert np.all(res["arrivals"] == 0) and np.all(res["arrivals_dropped"] == 0)
    assert np.all(res["contact_events"] > 0)
    assert np.allclose(res["cost"], spec.column_cost(res.ledger, late), rtol=1e-12)  # c_msg still in the bill
    assert rows["chem_off"]["n_end_fork"] > 0 and all(r["lives"] == 2 for r in rows.values())


def test_forks_under_a_control_that_holds_the_fork_slot():
    frozen = replace(W, t_fork=50.0, fork_flags=spec.FLAGS["freeze"])
    gt = LAY.pack(LAY.random(2, torch.Generator().manual_seed(6)))
    rows = clones.run_forks(gt, frozen, SEEDS, [0.25, 0.5], ["contacts_off"])
    done = [r for r in rows if "skipped" not in r]
    assert len(rows) == 4 and len(done) == 2 and all(r["t_fork"] == 50.0 for r in done)
    assert clones.reliance(rows) is not None or all(r["income_twin"] == 0 for r in done)
