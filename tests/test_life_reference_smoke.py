"""Smoke tests of the pure-Python one-life reference (src/life/reference.py, docs/LIFE_ABI.md)."""
import math

import numpy as np
import pytest

from src.life import reference as ref
from src.life import spec

L = spec.L
ALONE = spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1)  # the best lone cell (design gate G1)


def _r25(**extra):
    """R25-v1 as a program (LIFE_ABI.md 7.5), with optional extra knobs on the contact row (death, chemistry)."""
    contact = spec.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1, p_div=0.5, phi=2, **extra)
    alone = spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1, p_div=0.5, phi=2)
    juv = contact.copy()
    juv[spec.K["emit0"]] = 0.0
    return spec.pack_program(contact, alone=alone, juvenile=juv, juv_ticks=10, flank_gate=2, p_div_lo=0.05,
                             Dm0=0.05, Dm1=0.02, km0=0.05, km1=0.1)


# contact row with turnover, secretion, polarity, directional gain and chirality, so every handler runs
BUSY = _r25(p_die=2.0 ** -6, sec0=0.3, sec1=0.1, pol0=1.0, a0=0.5, chi=0.5)


def _genome(seed: int = 6) -> np.ndarray:
    """A random 8-gene genome with a readout biased to be tonic, inhibitory, emitting, contractile and dividing."""
    rng = np.random.default_rng(seed)
    g = (rng.normal(0, 1, spec.GENOME_SIZE) * 0.7).astype(np.float32)
    a, b = spec.GENOME_SLICES["act"]
    g[a:b] = 0.0
    g[a:a + 8] = 1.0
    a0 = spec.genome_view(g, "a0")
    for knob, shift in (("b", 1.3), ("w0", -0.8), ("emit0", 0.8), ("kappa", 1.5), ("p_div", 1.4), ("p_die", 0.3)):
        a0[spec.K[knob]] += shift
    return g


def _same(r1: ref.LifeResult, r2: ref.LifeResult) -> bool:
    """Bitwise equality of every output (ledger, hashes, raster and fate log)."""
    return all(getattr(r1, f).tobytes() == getattr(r2, f).tobytes()
               for f in ("ledger", "hashes", "raster_t", "raster_uid", "fate_i", "fate_f"))


def _conservation(led) -> float:
    lost = led[L["morph_decayed"]] + led[L["morph_lost"]] + led[L["morph_content_end"]] + led[L["morph_inflight_end"]]
    return abs(led[L["morph_secreted"]] - lost) / max(led[L["morph_secreted"]], 1e-300)


def test_lone_pump_reproduces_gate_g1():
    w = spec.world()
    r = ref.run(w, program=spec.pack_program(ALONE, alone=ALONE), seed=1)
    assert 0.031 < r["F"] < 0.035 and 0.052 < r["income"] / w.T < 0.055  # design: +0.0326, income 54e-3
    assert r["claims"] == 0 and r["n_end"] == 1 and r["contact_events"] == 0 and r.status == 0
    assert r["live_time"] == w.T and r["beats"] > 100
    col = float(spec.column_cost(r.ledger, w))
    assert r["net"] == r["income"] - col and abs(r["cost"] - col) < 1e-12
    assert r["F"] == pytest.approx(float(spec.fitness(r.ledger, w)), abs=1e-15)
    isi = np.diff(r.raster_t)  # tonic period tau ln(b / (b - 1)) + t_ref, up to Q10 rounding at the ticks
    tau = 8.0 * (1.0 + 0.05 * (2.0 * spec.draw(1, spec.S_TAU, spec.sitekey(0, 0), 0) - 1.0))
    assert np.allclose(isi, tau * math.log(1.875 / 0.875) + 2.0, rtol=2e-3)
    assert r.fate_n == 1 and r.fate_i[0].tolist()[:2] == [1, int(np.uint64(spec.uid_initial(1, 0)).astype(np.int64))]


def test_silent_zygote_pays_only_for_living():
    r = ref.run(spec.world(T=200.0), program=spec.pack_program(spec.theta()), seed=2)
    assert r["spikes"] == 0 and r["income"] == 0 and r["F"] == pytest.approx(-0.02, abs=1e-15)


def test_schedulers_and_tie_orders_agree_bitwise():
    w = spec.world(T=100.0)
    base = ref.run(w, program=BUSY, seed=5)
    assert base["births"] >= 20 and base["deaths"] >= 3 and base["rejects"] >= 3 and base["arrivals"] > 100
    for tie, salt in ((1, 0), (2, 99)):
        assert _same(ref.run(w, program=BUSY, seed=5, tie_seed=tie, salt=salt), base)
    for h in (0.5, 0.25, 0.125):
        for order in (0, 1):
            assert _same(ref.run(spec.world(T=100.0, window_h=h), program=BUSY, seed=5, order_seed=order), base)
    assert not _same(ref.run(w, program=BUSY, seed=6), base)


def test_grn_life_closes_its_books():
    g = _genome()
    w = spec.world(T=60.0, oracle_cap=12)
    r = ref.run(w, genome=g, seed=13)
    assert r["births"] >= 10 and r["deaths"] >= 3 and r["packets"] > 500 and r["arrivals"] > 500
    assert r.status & spec.STATUS["ledger_mismatch"] == 0 and _conservation(r.ledger) < 1e-12
    assert r["F"] == pytest.approx(float(spec.fitness(r.ledger, w)), abs=1e-15)
    assert np.all(r.fate_f[:, 2:] >= 0) and np.any(r.fate_f[:, 2:10] > 0)  # gene snapshots in the fate log
    assert _same(ref.run(w, genome=g, seed=13, tie_seed=7, salt=3), r)
    w2 = spec.world(T=60.0)
    assert _same(ref.run(spec.world(T=60.0, window_h=0.25), genome=g, seed=13, order_seed=2), ref.run(w2, genome=g,
                                                                                                       seed=13))


def test_extinction_ends_accrual():
    dies = spec.pack_program(spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1, p_die=1.0))
    r = ref.run(spec.world(T=100.0), program=dies, seed=6)
    assert r.status & spec.STATUS["extinct"] and r["n_end"] == 0 and r["deaths"] == 1 and r["t_end"] == 100.0
    t_ext = r["t_ext"]
    assert 0 < t_ext < 2.5 and r["live_time"] == t_ext and r.fate_i[-1, 0] == 2 and r.fate_f[-1, 1] == t_ext


def test_guards_close_the_life_with_a_charge():
    w = spec.world(T=100.0, n_max=5)
    r = ref.run(w, program=BUSY, seed=5)
    assert r.status & spec.STATUS["guard_cells"] and r["t_end"] == int(r["t_end"]) and r["t_end"] < 100.0
    assert r["n_end"] >= 5 and r["guard_charge"] == 0.02 * 5 * (100.0 - r["t_end"])
    assert r["F"] == pytest.approx(float(spec.fitness(r.ledger, w)), abs=1e-15)
    e = ref.run(spec.world(T=100.0, e_max=300), program=BUSY, seed=5)
    assert e.status & spec.STATUS["guard_events"] and e["events"] > 300


def test_contacts_off_fork_charges_but_delivers_nothing():
    w = spec.world(T=100.0, t_fork=40.0, t_open=40.0, fork_flags=spec.flags("contacts_off"))
    r = ref.run(w, program=BUSY, seed=5)
    twin = ref.run(spec.world(T=100.0, t_open=40.0), program=BUSY, seed=5)
    assert r["contact_events"] > 0 and twin["arrivals"] > 0
    assert r["arrivals"] + r["arrivals_dropped"] < 0.2 * twin["arrivals"]  # only spikes sent before the fork land
    full = ref.run(spec.world(T=100.0), program=BUSY, seed=5)
    pre = [x for x in full.raster_t if x < 40.0]
    assert np.array_equal(r.raster_t[:len(pre)], pre)  # identical history before the fork


def test_dense_fabric_wall_rejects_claims():
    r = ref.run(spec.world(T=100.0, fabric_R=1), program=BUSY, seed=5)
    assert r["rejects_wall"] > 0 and r.status & spec.STATUS["wall"] and r["n_peak"] <= 7
    walls = r.fate_i[(r.fate_i[:, 0] == 3) & (r.fate_i[:, 5] == 1)]
    assert len(walls) == r["rejects_wall"] and all(max(abs(a), abs(b), abs(a + b)) > 1 for a, b in walls[:, 3:5])


def test_life_run_mirrors_the_kernel_entry_point():
    lat, unit = spec.lattice_tables("hex")
    gt = spec.pack_genomes(_genome())
    progs = np.stack([BUSY, BUSY])
    worlds = spec.pack_world([spec.world(T=40.0, flags=spec.flags("program_mode")), spec.world(T=40.0)])
    seeds = np.array([[5, 0, 0, 0], [13, 1, 2, 3]], dtype=np.uint64)
    body, n = spec.pack_init([(0, 0), (1, 0)])
    init = np.stack([body, np.zeros_like(body)])
    out = ref.life_run(lat, unit, gt, progs, [1, 0], init, [n, 0], worlds, seeds, raster_cap=64, fate_cap=32)
    assert out["rc"] == 0
    a = ref.run(spec.world(T=40.0), program=BUSY, seed=5, cells=[(0, 0), (1, 0)], raster_cap=64, fate_cap=32)
    b = ref.run(spec.world(T=40.0), genome=_genome(), seed=13, tie_seed=1, order_seed=2, salt=3, raster_cap=64,
                fate_cap=32)
    for i, r in enumerate((a, b)):
        assert out["ledger"][i].tobytes() == r.ledger.tobytes() and np.array_equal(out["hashes"][i], r.hashes)
        assert out["raster_n"][i] == r.raster_n and out["fate_n"][i] == r.fate_n
        assert np.array_equal(out["raster_t"][i, :len(r.raster_t)], r.raster_t)
        assert np.array_equal(out["fate_i"][i, :len(r.fate_i)], r.fate_i)
    assert out["fate_i"][0, 1, 0] == 1 and out["fate_i"][0, 1, 3:5].tolist() == [1, 0]
    bad_world = worlds.copy()
    bad_world[1, spec.WORLD_INDEX["window_h"]] = 0.3
    dup = init.copy()
    dup[0, 1, :2] = 0
    for args, rc in (({"genome_of": [1, 2]}, -1), ({"world": bad_world}, -2), ({"init_cells": dup}, -4),
                     ({"programs": None}, -1)):
        kw = dict(lat=lat, unit=unit, genomes=gt, programs=progs, genome_of=[1, 0], init_cells=init, n_init=[n, 0],
                  world=worlds, seeds=seeds)
        kw.update(args)
        assert ref.life_run(**kw)["rc"] == rc


@pytest.mark.slow
@pytest.mark.parametrize("cond", [
    {}, dict(noise_rate=0.15), dict(drop_p=0.1), dict(kill_t=40.0, kill_frac=0.3), dict(stuck_t=30.0),
    dict(flags=spec.flags("lockstep")), dict(t_fork=30.0, fork_flags=spec.flags("chem_off")),
    dict(t_fork=30.0, fork_flags=spec.flags("freeze")), dict(t_fork=20.0, fork_flags=spec.flags("apoptosis_off",
                                                                                                "division_off")),
    dict(t_fork=20.0, fork_flags=spec.flags("identity_clamp", "genes_blind", "pheno_fixed")), dict(fabric_R=2),
    dict(n_max=6), dict(e_max=400), dict(t0=1024.0), dict(P0=4.0), dict(clock_sd=0.2, tick_jit=0.3),
])
def test_every_condition_is_scheduler_invariant(cond):
    for args, seed, T in ((dict(program=BUSY), 5, 100.0), (dict(genome=_genome()), 13, 50.0)):
        base = ref.run(spec.world(T=T, **cond), seed=seed, **args)
        assert base.status & spec.STATUS["ledger_mismatch"] == 0 and _conservation(base.ledger) < 1e-12
        assert _same(ref.run(spec.world(T=T, **cond), seed=seed, tie_seed=3, salt=5, **args), base)
        for h in (0.5, 0.125):
            assert _same(ref.run(spec.world(T=T, window_h=h, **cond), seed=seed, order_seed=7, **args), base)
