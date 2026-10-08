"""Smoke tests of the pure-Python one-life reference (src/life/reference.py, docs/LIFE_ABI.md)."""
import math
from dataclasses import replace

import numpy as np
import pytest

from src import lattice
from src.life import reference as ref
from src.life import spec
from tests.life_helpers import abi1_draw

L = spec.L
ALONE = spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1)  # the best lone cell (design gate G1)


def _r25(abi=None, **extra):
    """R25-v1 as a program (LIFE_ABI.md 7.5) of ``abi`` (default ``spec.CURRENT``), with optional extra knobs on the
    contact row (death, chemistry)."""
    abi = abi or spec.CURRENT
    contact = abi.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1, p_div=0.5, phi=2, **extra)
    alone = abi.theta(b=1.875, tau_m=8, t_ref=2, kappa=1, p_div=0.5, phi=2)
    juv = contact.copy()
    juv[abi.K["emit0"]] = 0.0
    return abi.pack_program(contact, alone=alone, juvenile=juv, juv_ticks=10, flank_gate=2, p_div_lo=0.05,
                            Dm0=0.05, Dm1=0.02, km0=0.05, km1=0.1)


# contact row with turnover, secretion, polarity, directional gain and chirality, so every handler runs
BUSY = _r25(p_die=2.0 ** -6, sec0=0.3, sec1=0.1, pol0=1.0, a0=0.5, chi=0.5)


def _genome(seed: int = 6) -> np.ndarray:
    """A random 8-gene genome with a readout biased to be tonic, inhibitory, emitting, contractile and dividing
    (drawn as under ABI 1, minus the removed flank_best column: ``life_helpers.abi1_draw``)."""
    g = abi1_draw(np.random.default_rng(seed), 0.7)
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


# =============================================================================== ABI 3: 3D sites, receptors, CATCH
V2, V3 = spec.V2, spec.V3
RV3 = V3.PROGRAM_ROW
HEX7 = [(0, 0), (1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def _reflex(g_c: float = 0.55, **motor_extra) -> np.ndarray:
    """The hand-built column reflex (BODY_DESIGN_PROPOSAL.md 3.2) as fixed program rows: a sense cell fires on each
    receptor event and relays it on channel 0, the act cell above it listens (w0 1, kappa 1, t_ref 4), and the centre
    sensor is a coincidence detector (g_r 0.55). Rows: contact = motor, rim = sense, zygote = centre sense."""
    sense = V3.theta(g_r=1.0, emit0=1, tau_m=1, t_ref=0.5)
    centre = V3.theta(g_r=g_c, emit0=1, tau_m=1, t_ref=0.5)
    motor = V3.theta(w0=1, kappa=1, t_ref=4, tau_m=1, **motor_extra)
    return V3.pack_program(motor, alone=V3.theta(), rim=sense, zygote=centre)


def _columns(cols, hidden: int = 0):
    """Cells (a, b, z) and fixed rows of columns: sense plane z = 0, act plane z = 1, then ``hidden`` planes."""
    cells = [(a, b, 0) for a, b in cols] + [(a, b, 1) for a, b in cols]
    rows = [RV3["zygote"] if (a, b) == (0, 0) else RV3["rim"] for a, b in cols] + [RV3["contact"]] * len(cols)
    for z in range(2, 2 + hidden):
        cells += [(a, b, z) for a, b in cols]
        rows += [RV3["alone"]] * len(cols)
    return cells, rows


def _grn3(seed: int, **shift) -> np.ndarray:
    """A random 8-gene ABI-3 genome biased to be tonic, emitting, contractile, dividing, receptive and to place up."""
    g = np.random.default_rng(seed).normal(0, 0.7, V3.GENOME_SIZE).astype(np.float32)
    act = V3.genome_view(g, "act")
    act[:] = 0.0
    act[:8] = 1.0
    a0 = V3.genome_view(g, "a0")
    bias = dict(b=1.3, w0=-0.8, emit0=0.8, kappa=1.5, p_div=0.9, p_die=0.3, g_r=0.8, zeta=1.0)
    bias.update(shift)
    for knob, s in bias.items():
        a0[V3.K[knob]] += s
    return g


def _run3(w, **kw) -> ref.LifeResult:
    return ref.run(w, abi=V3, **kw)


def _consistent(r: ref.LifeResult, w) -> bool:
    """The books close: no ledger mismatch, F re-prices from the columns, and morphogen mass is conserved."""
    led = r.ledger
    return (r.status & spec.STATUS["ledger_mismatch"] == 0 and r["F"] == pytest.approx(float(V3.fitness(led, w)),
                                                                                       abs=1e-12)
            and (led[V3.L["morph_secreted"]] == 0 or _conservation(led) < 1e-12))


def _f64(b: int) -> float:
    """A hash word bits(t) back to the double."""
    return float(np.uint64(b).view(np.float64))


def _plane_of(r: ref.LifeResult) -> dict:
    return {int(np.int64(u).astype(np.uint64)): int(z) for k, u, z in r.fate_i[:, [0, 1, 6]] if k == 1}


def test_abi3_bell_life_is_abi2_bitwise_with_padded_inputs():
    # LIFE_ABI.md 15.33 / gate GB1 on the reference: padding is neutral and only the `all` hash moves
    busy2 = _r25(V2, p_die=2.0 ** -6, sec0=0.3, sec1=0.1, pol0=1.0, a0=0.5, chi=0.5)
    g2 = np.random.default_rng(6).normal(0, 0.7, V2.GENOME_SIZE).astype(np.float32)
    V2.genome_view(g2, "act")[:] = [1.0] * 8 + [0.0] * 8
    for knob, shift in (("b", 1.3), ("w0", -0.8), ("emit0", 0.8), ("kappa", 1.5), ("p_div", 1.4), ("p_die", 0.3)):
        V2.genome_view(g2, "a0")[V2.K[knob]] += shift
    for lat in ("hex", "square8"):
        for kw2, kw3, seed in ((dict(program=busy2), dict(program=V3.pad_program(busy2, V2)), 5),
                               (dict(genome=g2), dict(genome=V3.pad_genomes(g2, V2)), 13)):
            w = spec.world(T=50.0, lattice=lat)
            a, b = ref.run(w, seed=seed, abi=V2, **kw2), _run3(w, seed=seed, **kw3)
            assert a["births"] >= 3 and a["spikes"] > 10  # not trivial lives
            assert a.ledger.size == 35 and b.ledger.size == 57 and a.abi is V2 and b.abi is V3
            assert a.ledger.tobytes() == b.ledger[:35].tobytes() and a.raster_t.tobytes() == b.raster_t.tobytes()
            assert np.array_equal(a.raster_uid, b.raster_uid) and a.fate_f.tobytes() == b.fate_f.tobytes()
            assert np.array_equal(a.fate_i, b.fate_i[:, :6]) and not b.fate_i[:, 6].any()
            assert np.array_equal(a.hashes[1:], b.hashes[1:4]) and a.hashes[0] != b.hashes[0]
            assert b.hashes[4] == spec.HASH_INIT and not b.ledger[35:51].any()
            assert b["live_S"] == b["live_time"] and b["n_S_end"] == b["n_end"] and b["live_M"] == b["live_H"] == 0
            assert b["n_M_end"] == b["n_H_end"] == 0
    w = spec.world(T=50.0, window_h=0.25)
    assert ref.run(w, program=busy2, seed=5, abi=V2).ledger.tobytes() == _run3(w, program=V3.pad_program(busy2, V2),
                                                                              seed=5).ledger[:35].tobytes()


def test_catch_column_reflex_catches_and_matches_the_known_answers():
    w = spec.world("catch_v1_l2", T=200.0)
    cells, rows = _columns(HEX7)
    r = _run3(w, program=_reflex(), cells=cells, rows=rows, seed=42, records=True)
    assert r["captures"] >= 2 and r["F"] > 0.5 and r["clicks"] == r["captures"] + r["misses"] and _consistent(r, w)
    assert r["income"] == 100.0 * r["captures"] and r["nudges"] > 50 and 0.2 < r["path"] / w.T < 0.6
    assert r["samples"] == w.T - 1 and r["n_S_end"] == r["n_M_end"] == 7
    assert r["live_S"] == pytest.approx(7 * w.T, rel=1e-12) and r["live_M"] == pytest.approx(7 * w.T, rel=1e-12)
    assert r["rec_events"] <= r["rec_accept"] < r["rec_cand"] and r["rec_accept"] - r["rec_events"] <= 7
    assert 0.55 * r["rec_events"] < r["rec_gain"] < r["rec_events"] and r["beats"] == r["P_int"] == 0
    uid0 = spec.uid_initial(42, 0)
    world = r.world
    # LIFE_ABI.md 14: the target's placement at t0, the zygote's first candidate (rejected far from the target),
    # the target's first turn and its first timer re-placement
    assert world[0] == (12, ref.bits(0.0), 0, 0, ref.bits(0.9226993667863177), ref.bits(3.7675546907873656), 1)
    first = next(x for x in world if x[0] == 9 and x[2] == uid0)
    assert first == (9, ref.bits(0.9337337422296379), uid0, 0, 0)
    turn = next(x for x in world if x[0] == 13)
    assert turn[1:3] == (ref.bits(15.984882681203024), 0)
    assert turn[3:] == tuple(ref.bits(v) for v in spec.blob_heading(42, 0, 1, 0.1))
    assert next(x for x in world if x[0] == 12 and x[3] == 2)[1] == ref.bits(71.9336107410924)
    # every delivered receptor event arrives d_min after a candidate the world accepted (9.7.5)
    acc = sorted((x[2], _f64(x[1]) + w.d_min) for x in world if x[0] == 9 and x[4] == 1)
    got = sorted((p[0], t) for t, _sk, _seq, kind, p in r.records if kind == ref.R_RECEPT for _ in range(p[1]))
    assert got == [x for x in acc if x[1] < w.T]
    clicks = [x for x in world if x[0] == 11]
    assert len(clicks) == r["clicks"] and sum(x[2] == 1 for x in clicks) == r["captures"]


def test_catch_is_scheduler_invariant():
    cells, rows = _columns(HEX7)
    for w, kw, seed in ((spec.world("catch_v1_l2", T=80.0), dict(program=_reflex(), cells=cells, rows=rows), 1),
                        (spec.world("catch_v1_l4", T=40.0), dict(genome=_grn3(25)), 25)):
        base = _run3(w, seed=seed, **kw)
        assert base["rec_events"] > 20 and base["nudges"] > 0 and _consistent(base, w)
        assert _same(_run3(w, seed=seed, tie_seed=3, salt=5, **kw), base)
        for h in (0.5, 0.125):
            assert _same(_run3(replace(w, window_h=h), seed=seed, order_seed=7, **kw), base)
        assert not _same(_run3(w, seed=seed + 1, **kw), base)


def test_synchronous_act_plane_never_drifts_and_an_isolated_act_cell_cannot_pull():
    # the surface-normal law (9.7.2): faces cancel over any body, so when lockstep makes every act cell twitch
    # together the total force is 0 up to the rounding of its running sum
    tonic = V3.pack_program(V3.theta(b=1.875, tau_m=8, t_ref=2, kappa=1), alone=V3.theta(), rim=V3.theta(),
                            zygote=V3.theta())
    cells, rows = _columns(HEX7)
    lock = spec.world("catch_v1_l2", T=100.0, flags=V3.flags("lockstep"))
    r = _run3(lock, program=tonic, cells=cells, rows=rows, seed=3)
    assert r["nudges"] >= 6 * 10 and r["clicks"] >= 10 and r["path"] < 1e-12 and abs(r["X_end"]) < 1e-12
    free = _run3(spec.world("catch_v1_l2", T=100.0), program=tonic, cells=cells, rows=rows, seed=3)
    assert free["nudges"] >= 60 and free["path"] > 0.01  # jittered clocks: the twitches no longer cancel
    lone = _run3(spec.world("catch_v1_l2", T=100.0), program=tonic, cells=[(0, 0, 0), (0, 0, 1)],
                 rows=[RV3["zygote"], RV3["contact"]], seed=3)
    assert lone["nudges"] == 0 and lone["path"] == 0.0 and lone["clicks"] >= 10 and lone["spikes"] >= 10


def test_receptor_gain_zero_means_no_receptor():
    silent = V3.pack_program(V3.theta(), alone=V3.theta(emit0=1, g_r=0.0))
    w = spec.world("catch_v1", T=100.0)
    r = _run3(w, program=silent, seed=4)
    assert r["rec_cand"] > 150 and r["rec_accept"] > 0 and r["rec_events"] == r["rec_gain"] == 0 and r["spikes"] == 0
    hear = _run3(w, program=V3.pack_program(V3.theta(), alone=V3.theta(g_r=-0.5)), seed=4)
    assert hear["rec_events"] > 0 and hear["rec_gain"] == 0.5 * hear["rec_events"] and hear["spikes"] == 0
    assert hear["cost"] == pytest.approx(0.02 * 100 + 0.001 * hear["rec_gain"], abs=1e-12) and _consistent(hear, w)
    # thinning: with no target luminance every candidate is kept; candidates arrive at lambda_max per unit
    flat = _run3(spec.world("catch_v1", T=200.0, lam_s=0.0, lam_bg=1.0), program=silent, seed=4)
    assert flat["rec_accept"] == flat["rec_cand"] and abs(flat["rec_cand"] - 200.0) < 4 * math.sqrt(200.0)


def test_catch_forks_cut_their_channel():
    cells, rows = _columns(HEX7)
    kw = dict(program=_reflex(), cells=cells, rows=rows, seed=1)
    fork = dict(T=200.0, t_open=60.0, t_fork=60.0)
    twin = _run3(spec.world("catch_v1_l2", **fork), **kw)
    assert twin["clicks"] > 0 and twin["nudges"] > 0 and twin["rec_events"] > 0
    motor = _run3(spec.world("catch_v1_l2", fork_flags=V3.flags("motor_off"), **fork), **kw)
    assert motor["clicks"] == motor["nudges"] == motor["captures"] == 0 and motor["kappa_sum"] > 0
    assert motor["rec_events"] > 0 and motor["respawns"] == twin["respawns"]
    assert _consistent(motor, spec.world("catch_v1_l2", **fork))
    rec = _run3(spec.world("catch_v1_l2", fork_flags=V3.flags("receptor_off"), **fork), **kw)
    assert rec["rec_events"] == rec["rec_gain"] == 0 and rec["rec_accept"] > 0 and rec["clicks"] <= 1
    # the reflex column is vertical: cutting in-plane spikes keeps it working, cutting all contacts stops it
    lat = _run3(spec.world("catch_v1_l2", fork_flags=V3.flags("lateral_off"), **fork), **kw)
    assert lat["nudges"] > 0.5 * twin["nudges"] and lat["clicks"] > 0 and lat["arrivals"] < twin["arrivals"]
    off = _run3(spec.world("catch_v1_l2", fork_flags=V3.flags("contacts_off"), **fork), **kw)
    assert off["nudges"] < 0.05 * twin["nudges"] and off["contact_events"] > 0  # only spikes sent before the fork
    for r in (twin, motor, rec, lat, off):
        assert np.array_equal(r.raster_t[r.raster_t < 60.0], twin.raster_t[twin.raster_t < 60.0])
    # hidden_off: tonic hidden cells (z = 2) keep firing and paying, but none of their spikes is delivered
    hid = V3.pack_program(V3.theta(), alone=V3.theta(b=1.875, tau_m=8, t_ref=2, emit0=1), rim=V3.theta(),
                          zygote=V3.theta())
    cells3, rows3 = _columns(HEX7, hidden=1)
    w4 = spec.world("catch_v1_l4", T=100.0, t_open=30.0, t_fork=30.0)
    on = _run3(w4, program=hid, cells=cells3, rows=rows3, seed=2)
    cut = _run3(replace(w4, fork_flags=V3.flags("hidden_off")), program=hid, cells=cells3, rows=rows3, seed=2)
    assert on["arrivals"] > 100 and cut["arrivals"] < 0.05 * on["arrivals"]
    assert cut["contact_events"] == on["contact_events"] and cut["spikes"] == on["spikes"] > 50


def test_plane_cues_reach_the_genes_only_in_catch():
    # gene 0 follows is_M (or is_S) and sets the bias b: only that plane's cells become tonic; in BELL the cues are 0
    for cue, plane in ((24, 1), (23, 0)):
        g = np.zeros(V3.GENOME_SIZE, dtype=np.float32)
        V3.genome_view(g, "act")[0] = 1.0
        V3.genome_view(g, "W")[0, cue] = 20.0
        V3.genome_view(g, "b")[0] = -10.0
        V3.genome_view(g, "lam")[0] = -3.0  # rate 1/2
        V3.genome_view(g, "s0")[0] = -10.0
        V3.genome_view(g, "a0")[V3.K["b"]] = -1.0
        V3.genome_view(g, "A")[V3.K["b"], 0] = 3.0
        cells = [(a, b, z) for a, b in HEX7[:3] for z in (0, 1)]
        r = _run3(spec.world("catch_v1_l2", T=60.0), genome=g, cells=cells, seed=1)
        zs = _plane_of(r)
        fired = {zs[int(u)] for u in r.raster_uid}
        assert fired == {plane} and r.raster_n > 10, (cue, fired)
        bell = _run3(spec.world(T=60.0, lattice="hexprism", L_max=2), genome=g, cells=cells, seed=1)
        assert bell.raster_n == 0 and bell["rec_cand"] == 0


def test_vertical_placement_follows_zeta_and_never_leaves_the_stack():
    def first_daughter(zeta, z0, L_max=2):
        prog = V3.pack_program(V3.theta(), alone=V3.theta(p_div=1.0, zeta=zeta))
        w = spec.world("catch_v1_l2", T=6.0, L_max=L_max)
        r = _run3(w, program=prog, cells=[(0, 0, z0)], seed=2)
        births = r.fate_i[r.fate_i[:, 0] == 1]
        assert len(births) >= 2 and r["rejects_wall"] == 0
        return tuple(births[1, [3, 4, 6]])
    assert first_daughter(2.0, 0) == (0, 0, 1)  # up beats every in-plane slot
    assert first_daughter(-2.0, 0)[2] == 0  # down is out of the stack, so the daughter stays in the plane
    assert first_daughter(-2.0, 1) == (0, 0, 0)
    assert first_daughter(2.0, 1)[2] == 1  # the act plane is the top of an L_max 2 stack
    assert first_daughter(2.0, 1, L_max=4) == (0, 0, 2)
    # a growing GRN body stays inside the stack, and every plane fills
    w = spec.world("catch_v1_l2", T=40.0)
    r = _run3(w, genome=_grn3(25), seed=25)
    z = r.fate_i[:, 6]
    assert set(z) <= {0, 1} and r["births"] > 5 and r["n_M_end"] > 0 and _consistent(r, w)
    assert r["live_S"] + r["live_M"] + r["live_H"] == pytest.approx(r["live_time"], rel=1e-12)


def test_catch_world_runs_on_after_extinction_and_honours_t_open_and_guards():
    dies = V3.pack_program(V3.theta(), alone=V3.theta(p_die=1.0, g_r=1.0))
    w = spec.world("catch_v1", T=300.0)
    r = _run3(w, program=dies, seed=42)
    assert r.status & spec.STATUS["extinct"] and r["t_ext"] < 2.5 and r["samples"] == w.T - 1
    assert r["respawns"] >= 1 and r["path"] == 0.0 and r["X_end"] == 0.0 and r["dist_sum"] > 2.0 * r["samples"]
    late = _run3(replace(w, t_open=50.0), program=dies, seed=42)
    assert late["samples"] == w.T - 50 and late["respawns"] == r["respawns"] - (71.9336107410924 < 50)
    capped = _run3(spec.world("catch_v1_l2", T=200.0, n_max=8), genome=_grn3(25), seed=25)
    t_end = capped["t_end"]
    assert capped.status & spec.STATUS["guard_cells"] and t_end < 200 and capped["samples"] == t_end - 1


def test_life_run_mirrors_run_under_abi3():
    lat, unit = V3.lattice_tables("hexprism")
    cells, rows = _columns(HEX7)
    body, n = V3.pack_init(cells, rows)
    gt = V3.pack_genomes(_grn3(25), "hexprism")
    worlds = V3.pack_world([spec.world("catch_v1_l2", T=40.0, flags=V3.flags("program_mode")),
                            spec.world("catch_v1_l4", T=30.0)])
    seeds = np.array([[1, 0, 0, 0], [25, 1, 2, 3]], dtype=np.uint64)
    init = np.stack([body, np.zeros_like(body)])
    out = ref.life_run(lat, unit, gt, _reflex()[None], [0, 0], init, [n, 0], worlds, seeds, raster_cap=64,
                       fate_cap=32, abi=V3)
    assert out["rc"] == 0 and out["ledger"].shape == (2, 57) and out["hashes"].shape == (2, 5)
    a = _run3(spec.world("catch_v1_l2", T=40.0), program=_reflex(), cells=cells, rows=rows, seed=1, raster_cap=64,
              fate_cap=32)
    b = _run3(spec.world("catch_v1_l4", T=30.0), genome=_grn3(25), seed=25, tie_seed=1, order_seed=2, salt=3,
              raster_cap=64, fate_cap=32)
    for i, r in enumerate((a, b)):
        assert out["ledger"][i].tobytes() == r.ledger.tobytes() and np.array_equal(out["hashes"][i], r.hashes)
        assert np.array_equal(out["fate_i"][i, :len(r.fate_i)], r.fate_i) and out["fate_n"][i] == r.fate_n
    assert out["fate_i"][0, 7, 6] == 1  # cell 7 is the first act cell (z = 1)
    kw = dict(lat=lat, unit=unit, genomes=gt, programs=_reflex()[None], genome_of=[0, 0], init_cells=init,
              n_init=[n, 0], world=worlds, seeds=seeds, abi=V3)
    bad_lat = lat.copy()
    bad_lat[2 + 2 * 8 + 6] = 0  # off_z of the up slot
    for args in (dict(init_cells=_set(init, (0, 0, 2), 2)), dict(init_cells=_set(init, (0, 0, 0), 2 ** 22 + 1)),
                 dict(init_cells=_set(init, (0, 1), (0, 0, 0))), dict(lat=bad_lat)):
        assert ref.life_run(**{**kw, **args})["rc"] == -4, args
    assert ref.life_run(**{**kw, "programs": None})["rc"] == -1


def _set(init, idx, value):
    out = init.copy()
    if isinstance(value, tuple):
        out[idx][:3] = value
    else:
        out[idx] = value
    return out


@pytest.mark.slow
@pytest.mark.parametrize("cond", [
    {}, dict(flags=V3.flags("lockstep")), dict(noise_rate=0.15, drop_p=0.1), dict(kill_t=20.0, kill_frac=0.3),
    dict(stuck_t=15.0, stuck_z=1), dict(t_fork=15.0, fork_flags=V3.flags("receptor_off", "lateral_off")),
    dict(t_fork=15.0, fork_flags=V3.flags("motor_off", "hidden_off")), dict(t_open=10.0), dict(fabric_R=2),
    dict(b2_amp=1.0, b2_value=-5.0, b2_p=0.5), dict(b2_amp=1.0, b2_value=100.0, b2_mode=1, b2_sigma=2.0),
    dict(tau_turn=0.0, t_resp=0.0), dict(n_max=12), dict(t0=1024.0),
])
def test_every_catch_condition_is_scheduler_invariant(cond):
    cells, rows = _columns(HEX7, hidden=1)
    for name, args, seed, T in (("catch_v1_l4", dict(program=_reflex(), cells=cells, rows=rows), 1, 60.0),
                                ("catch_v1_l4", dict(genome=_grn3(25)), 25, 40.0),
                                ("catch_v1_l2", dict(genome=_grn3(21)), 21, 25.0)):
        w = spec.world(name, T=T, **cond)
        base = _run3(w, seed=seed, **args)
        assert _consistent(base, w)
        assert _same(_run3(w, seed=seed, tie_seed=3, salt=5, **args), base)
        for h in (0.5, 0.125):
            assert _same(_run3(replace(w, window_h=h), seed=seed, order_seed=7, **args), base)


@pytest.mark.slow
def test_second_blob_modes_place_and_pay_as_specified():
    cells, rows = _columns(HEX7)
    kw = dict(program=_reflex(), cells=cells, rows=rows, seed=4, records=True)
    decoy = spec.world("catch_v1_l2", T=400.0, b2_amp=1.0, b2_value=-5.0, b2_p=0.5)
    r = _run3(decoy, **kw)
    places = [x for x in r.world if x[0] == 12]
    p0, p1 = [x for x in places if x[2] == 0], [x for x in places if x[2] == 1]
    assert len(p0) == len(p1) and all(x[3] in (0, 3) for x in p1) and {x[6] for x in p1} == {0, 1}
    assert r["b2_clicks"] > 0 and _consistent(r, decoy)
    twin = spec.world("catch_v1_l2", T=400.0, b2_amp=1.0, b2_value=100.0, b2_mode=1)
    s = _run3(twin, **kw)
    q1 = [x for x in s.world if x[0] == 12 and x[2] == 1]
    assert {x[3] for x in q1} >= {0, 2} and all(x[6] == 1 for x in q1)
    assert s["income"] == 100.0 * (s["captures"] + s["b2_clicks"]) and _consistent(s, twin)


def _decode_sk(sk: int) -> tuple[int, int, int]:
    """sitekey(a, b, z) -> (a, b, z) for |a| < 2^24 (LIFE_ABI.md 3)."""
    b = sk & 0xFFFFFFFF
    hi = sk >> 32
    top = hi >> 24
    z = (top & 0xF) ^ 0xF if top & 0xF0 == 0xF0 else top
    a = hi ^ (z << 24)
    return a - (a >> 31 << 32), b - (b >> 31 << 32), z


def _rederive_world(w, r: ref.LifeResult, seed: int, every: int = 8) -> dict:
    """Rebuild the CATCH world from a life's records and world log alone (9.7): every stroke's force decays from its
    onset until its cell dies, and the dot is the sum of their exact integrals over the footprint's intervals (a
    different formula from the accountant's anchor updates). The drag counts occupied columns in any plane, and
    traction needs a sense-plane cell (15.44, 15.59). Returns the largest position error at the clicks and at
    the end, and the counts of click outcomes and receptor decisions (every ``every``-th candidate) that this
    rebuilt world contradicts."""
    units, offs = lattice.unit_vectors("hex"), lattice.offsets("hex")
    strokes, live, foot, occ, n_foot, cols = [], {}, [(w.t0, 0, 0)], set(), 0, {}
    recs, i = r.records, 0
    while i < len(recs):  # one time group at a time: faces read the act plane at the group's left limit
        j = i
        while j < len(recs) and recs[j][0] == recs[i][0]:
            j += 1
        dO = []
        for t, sk, _seq, kind, p in recs[i:j]:
            a, b, z = _decode_sk(sk)
            if kind in (ref.R_BIRTH, ref.R_DEATH):
                cols[(a, b)] = cols.get((a, b), 0) + (1 if kind == ref.R_BIRTH else -1)
                n_foot += (1 if kind == ref.R_BIRTH else -1) if z == 0 else 0
                foot.append((t, n_foot, sum(c > 0 for c in cols.values())))
            if kind in (ref.R_BIRTH, ref.R_DEATH) and z == 1:
                dO.append((kind == ref.R_BIRTH, (a, b)))
                for s in live.pop((a, b), []) if kind == ref.R_DEATH else []:
                    s[3] = t
            elif kind == ref.R_SPIKE and z == 1 and p[1] > 0 and p[3] > 0:
                n = np.sum([units[d] for d, (da, db) in enumerate(offs) if (a + da, b + db) not in occ] or [(0, 0)], 0)
                if np.abs(n).max() > 1e-9:
                    strokes.append([t, w.g_n * p[3] * n[0], w.g_n * p[3] * n[1], math.inf])
                    live.setdefault((a, b), []).append(strokes[-1])
        for add, ab in dO:
            (occ.add if add else occ.discard)(ab)
        i = j
    edges = foot + [(math.inf, 0, 0)]

    def dot(t):
        X = Y = 0.0
        for t_i, cx, cy, stop in strokes:
            for (a0, n, nc), (a1, _, _) in zip(edges[:-1], edges[1:]):
                lo, hi = max(a0, t_i), min(a1, t, stop)
                if hi > lo and n > 0:
                    k = w.tau_z * (math.exp(-(lo - t_i) / w.tau_z) - math.exp(-(hi - t_i) / w.tau_z)) / nc ** w.drag_exp
                    X, Y = X + cx * k, Y + cy * k
        return X, Y

    col = {int(np.int64(u).astype(np.uint64)): (int(a), int(b)) for k, u, a, b in r.fate_i[:, [0, 1, 3, 4]] if k == 1}
    anchor, vel, present = {}, {b: spec.blob_heading(seed, b, 0, w.v_t) for b in (0, 1)}, {0: True, 1: True}
    blob = {}
    out = dict(err=0.0, clicks=0, bad_clicks=0, cands=0, bad_cands=0)
    for x in r.world:
        t = _f64(x[1])
        if x[0] in (12, 13):  # a placement or a turn re-anchors blob x[2]
            b = x[2]
            if x[0] == 13:
                anchor[b] = (t, *blob[b](t))
                vel[b] = (_f64(x[3]), _f64(x[4]))
            else:
                anchor[b] = (t, _f64(x[4]), _f64(x[5]))
                present[b] = bool(x[6])
            ta, xa, ya = anchor[b]
            blob[b] = lambda s, ta=ta, xa=xa, ya=ya, v=vel[b]: (xa + v[0] * (s - ta), ya + v[1] * (s - ta))
        elif x[0] == 11:
            X, Y = dot(t)
            out["err"] = max(out["err"], abs(X - _f64(x[3])), abs(Y - _f64(x[4])))
            hit2 = w.b2_amp > 0 and present[1] and math.dist((X, Y), blob[1](t)) <= w.b2_rho
            outcome = 1 if math.dist((X, Y), blob[0](t)) <= w.rho_c else (2 if hit2 else 0)
            out["clicks"] += 1
            out["bad_clicks"] += outcome != x[2]
        elif x[0] == 9 and x[3] % every == 0:
            a, b = col[x[2]]
            X, Y = dot(t)
            p = (X + a + 0.5 * b, Y + b * math.sqrt(3) / 2)
            rate = w.lam_bg + w.lam_s * math.exp(-math.dist(p, blob[0](t)) ** 2 / (2 * w.sigma ** 2))
            if w.b2_amp > 0 and present[1]:
                rate += w.lam_s * w.b2_amp * math.exp(-math.dist(p, blob[1](t)) ** 2 / (2 * w.b2_sigma ** 2))
            u = spec.draw(seed, spec.S_RACC, x[2], x[3]) * spec.lambda_max(w)
            out["cands"] += 1
            out["bad_cands"] += abs(u - rate) > 1e-9 and (u < rate) != bool(x[4])
    X, Y = dot(r["t_end"])
    out["err"] = max(out["err"], abs(X - r["X_end"]), abs(Y - r["Y_end"]))
    return out


@pytest.mark.slow
def test_the_catch_world_rederives_from_the_records():
    cells, rows = _columns(HEX7)
    reflex = dict(program=_reflex(), cells=cells, rows=rows)
    for w, kw, seed in ((spec.world("catch_v1_l2", T=200.0), reflex, 42),
                        (spec.world("catch_v1_l2", T=200.0, b2_amp=1.0, b2_value=-5.0, b2_p=0.5), reflex, 4),
                        (spec.world("catch_v1_l2", T=200.0, b2_amp=1.0, b2_value=100.0, b2_mode=1), reflex, 6),
                        (spec.world("catch_v1_l4", T=60.0), dict(genome=_grn3(25)), 25),
                        (spec.world("catch_v1_l4", T=30.0), dict(genome=_grn3(31)), 31)):
        r = _run3(w, seed=seed, records=True, **kw)
        out = _rederive_world(w, r, seed)
        assert out["err"] < 1e-12 and out["bad_clicks"] == out["bad_cands"] == 0, (w.name, seed, out)
        assert out["clicks"] == r["clicks"] > 0 and out["cands"] > 0.1 * r["rec_cand"] > 10
