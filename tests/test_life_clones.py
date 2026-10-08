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


# ------------------------------------------------------------------------------------------- BODY-1 (ABI 3)
V3 = spec.V3
CATCH = spec.world("catch_v1_l4", T=200.0)


@pytest.fixture(scope="module")
def catch_talker() -> np.ndarray:
    """A packed ABI-3 founder whose CATCH body spikes across planes (in-plane and vertical contacts)."""
    from src.genome import LIFE_DIMS_ABI3

    lay = LifeLayout(LIFE_DIMS_ABI3)
    gt = lay.pack(lay.random(256, torch.Generator().manual_seed(8)), "hexprism")
    res = build.run(CATCH, [11] * 256, genomes=gt, genome_of=np.arange(256), threads=4, abi=V3)
    i = next(i for i in range(256) if res["arrivals"][i] > 500 and 8 <= res["n_end"][i] <= 300
             and res["n_M_end"][i] > 0 and res["n_H_end"][i] > 0)
    return gt[i:i + 1]


def test_conditions_join_flags_and_the_certificate_is_three_lesions():
    assert clones.condition_flags(None) == 0
    assert clones.condition_flags(clones.CERTIFICATE) == V3.flags("contacts_off", "chem_off", "division_off")
    assert clones.condition_flags("lateral_off+hidden_off") == V3.flags("lateral_off", "hidden_off")
    for bad in ("lateral", "contacts_off+nope", "lockstep", "program_mode"):  # unknown names and base-only flags
        with pytest.raises(ValueError):
            clones.condition_flags(bad)
    assert clones.message_condition(clones.CATCH_CONDITIONS) == clones.CERTIFICATE
    assert clones.message_condition(clones.CONDITIONS) == "contacts_off"
    w = clones.fork_world(CATCH, 100.0, clones.CERTIFICATE)
    assert w.fork_flags == clones.condition_flags(clones.CERTIFICATE) and w.t_open == 100.0
    with pytest.raises(ValueError):  # ABI 2 refuses the ABI-3 forks
        spec.V2.validate_world(replace(W, fork_flags=V3.FLAGS["lateral_off"]))


def test_catch_forks_run_under_abi3_and_the_certificate_delivers_nothing(catch_talker):
    """BODY-1 forks (proposal 8, GB6): every CATCH condition runs as one ABI-3 batch; after the certificate at T/2
    no spike lands once the spikes in flight have, no cell is born, and the bill still holds every charge."""
    rows = {r["condition"]: r for r in clones.run_forks(catch_talker, CATCH, SEEDS, [0.5], clones.CATCH_CONDITIONS,
                                                        threads=2, abi=V3)}
    assert set(rows) == set(clones.CATCH_CONDITIONS) and all("skipped" not in r for r in rows.values())
    cert, lat = rows[clones.CERTIFICATE], rows["lateral_off"]
    assert cert["arrivals_fork"] < 0.05 * cert["arrivals_twin"]
    assert lat["arrivals_fork"] < lat["arrivals_twin"]  # in-plane spikes dropped, vertical ones still land
    late = replace(clones.fork_world(CATCH, 100.0, clones.CERTIFICATE), t_open=110.0)
    res = build.run(late, SEEDS, genomes=catch_talker, abi=V3)
    assert np.all(res["arrivals"] == 0) and np.all(res["births"] == 0) and np.all(res["packets"] == 0)
    assert np.all(res["contact_events"] > 0)  # spikes are still charged
    assert np.allclose(res["cost"], V3.column_cost(res.ledger, late), rtol=1e-12)
    hid = rows["hidden_off"]
    assert hid["arrivals_fork"] <= hid["arrivals_twin"]
    with pytest.raises(ValueError):  # the ABI-2 default refuses a CATCH world
        clones.run_forks(catch_talker, CATCH, SEEDS, [0.5], ["contacts_off"])


def test_a_blind_relay_passes_the_certificate_but_not_the_sensing_fork():
    """Review fix: the certificate alone (msg reliance 1) does not show sensing. A blind tonic zygote relaying to the
    motor above it needs every message and no receptor, so receptor_off removes nothing; the sensing clicker loses
    all of its income under both forks."""
    from src.life import handbuilt as hb
    assert clones.SENSE in clones.CATCH_CONDITIONS and clones.sense_condition(clones.CATCH_CONDITIONS) == clones.SENSE
    assert clones.sense_condition(clones.CONDITIONS) is None
    seeds = list(range(40, 56))
    for org, sensing in ((hb.BLIND_RELAY_GRN, 0.0), (hb.COLUMN_GRN_RING0, 1.0)):
        rows = clones.run_forks(org.table(), spec.world("catch_v1"), seeds, [0.5], clones.CATCH_CONDITIONS,
                                threads=4, abi=V3)
        assert clones.reliance(rows, clones.CERTIFICATE) == pytest.approx(1.0, abs=0.02), org.name
        assert clones.reliance(rows, clones.SENSE) == pytest.approx(sensing, abs=0.02), org.name
