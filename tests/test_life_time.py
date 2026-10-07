"""Time-model tests T1-T6, T11 and T12 (docs/ONE_LIFE_DESIGN.md, TESTS): whole lives, including growth and death,
must not depend on the scheduler, the tie order, cell labels, threads, batch composition, the fabric size or (in
float, to 1e-9) the start time."""
from dataclasses import replace

import numpy as np
import pytest

from src.life import build, spec
from src.life import handbuilt as hb
from tests.life_helpers import ALONE, BUSY, HEX7, ROW, grn_genome, kernel, mismatch, r25, reference, same

LOCK = spec.flags("lockstep")
# heavy turnover: the zygote may die before it divides, so some lives go extinct and many sites are refilled
TURNOVER = spec.pack_program(
    spec.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1, p_div=0.5, phi=2, p_die=2 ** -3,
               sec0=0.2, pol0=1.0),
    alone=spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1, p_div=0.25, p_die=0.25),
    Dm0=0.05, km0=0.05)
# every life grows a little and then dies out
DIEOUT = spec.pack_program(
    spec.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1, p_div=0.5, phi=2, p_die=0.5, sec0=0.2,
               pol0=1.0),
    alone=spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1, p_div=0.5, p_die=2 ** -4), Dm0=0.05, km0=0.05)


def _assert_scheduler_free(w, seeds, **kw):
    """T1: the window scheduler at h = 1/2, 1/4, 1/8, each with 3 visit orders, equals the heap bitwise."""
    base = kernel(w, [[s, 0, 0, 0] for s in seeds], **kw)
    for h in (0.5, 0.25, 0.125):
        for order in (1, 2, 3):
            win = kernel(replace(w, window_h=h), [[s, 0, 1000 * order + s, 0] for s in seeds], **kw)
            assert same(base, win), (h, order)
    return base


def test_t1_window_scheduler_equals_heap_on_growing_dying_lives():
    seeds = [3, 5, 11, 17]
    base = _assert_scheduler_free(spec.world(T=200.0), seeds, program=BUSY)
    assert np.all(base["births"] >= 20) and base["deaths"].sum() >= 10 and np.all(base["packets"] > 100)
    assert base["rejects"].sum() > 0 and np.all(base["arrivals"] > 100)
    base = _assert_scheduler_free(spec.world(T=96.0), [7, 8, 9], genome=grn_genome())
    assert np.all(base["n_peak"] > 5) and base["deaths"].sum() > 0 and np.all(base["packets"] > 0)
    assert not (base.status("capacity") | base.status("ledger_mismatch")).any()


def test_t1_window_scheduler_equals_heap_under_lockstep_ties():
    # every d_c = 1, no jitter, clocks in phase: exact time ties at almost every event
    base = _assert_scheduler_free(spec.world(T=150.0, flags=LOCK), [3, 4], program=BUSY, init=HEX7)
    assert np.all(base["births"] > 10) and base["deaths"].sum() > 0


def test_t2_random_tie_keys_give_bitwise_identical_lives():
    for w, kw in ((spec.world(T=200.0), dict(program=BUSY)), (spec.world(T=150.0, flags=LOCK), dict(program=BUSY)),
                  (spec.world(T=96.0), dict(genome=grn_genome()))):
        seeds = [5, 6]
        base = kernel(w, seeds, **kw)
        for tie in range(1, 10):
            assert same(base, kernel(w, [[s, tie * 7919 + s, 0, 0] for s in seeds], **kw)), tie


def test_t2_the_oracle_cap_is_tie_free_under_lockstep():
    # lockstep ticks tie at every grid point; the cap reads n_alive + n_inflight at the left limit of each instant
    # (LIFE_ABI.md 11.3), so same-instant claimers all see one count and may overshoot the cap together
    for w, kw, seeds in ((spec.world(T=150.0, oracle_cap=20, flags=LOCK), dict(program=BUSY), [3, 5, 6, 7]),
                         (spec.world(T=100.0, oracle_cap=20, flags=LOCK), dict(genome=grn_genome()), [1, 2])):
        base = kernel(w, seeds, **kw)
        for tie in range(1, 9):
            assert same(base, kernel(w, [[s, tie * 7919 + s, 0, 0] for s in seeds], **kw)), tie
        assert not mismatch(kernel(w, [[seeds[1], 3, 0, 0]], **kw), 0, reference(w, seeds[1], tie=3, **kw))
        assert base["n_peak"].max() > 20  # the cap binds, and same-instant claimers overshoot it


def test_t2_reference_tie_keys_and_salts_are_bitwise_free():
    w = spec.world(T=100.0, oracle_cap=20)
    base = reference(w, 5, program=BUSY)
    for tie, salt in ((1, 0), (2, 3), (99, 12345)):
        assert not mismatch(kernel(w, [[5, tie, 0, salt]], program=BUSY), 0, reference(w, 5, program=BUSY, tie=tie,
                                                                                        salt=salt))
        assert reference(w, 5, program=BUSY, tie=tie, salt=salt).ledger.tobytes() == base.ledger.tobytes()


# T3: the pure-Python reference and the kernel agree bitwise (20 cells or fewer, T <= 200)
_T3_FAST = [
    ("lone pump", spec.world(T=200.0), dict(program=spec.pack_program(ALONE, alone=ALONE)), 1, {}),
    ("busy cap20", spec.world(T=200.0, oracle_cap=20), dict(program=BUSY), 5, {}),
    ("busy lockstep cap20", spec.world(T=150.0, oracle_cap=20, flags=LOCK), dict(program=BUSY), 3, {}),
    ("busy window guard", spec.world(T=120.0, window_h=0.25, n_max=20), dict(program=BUSY), 4, dict(order=3)),
    ("grn cap20", spec.world(T=150.0, oracle_cap=20), dict(genome=grn_genome()), 13, {}),
    ("grn square8 cap16", spec.world(T=80.0, lattice="square8", oracle_cap=16), dict(genome=grn_genome()), 1, {}),
    ("busy panel", spec.world(T=120.0, oracle_cap=20, noise_rate=0.1, drop_p=0.1, kill_t=60.0, kill_frac=0.3,
                              stuck_t=40.0), dict(program=BUSY), 5, {}),
    ("growth then extinction", spec.world(T=100.0), dict(program=DIEOUT), 4, {}),
]
_T3_SLOW = [
    ("busy t_open", spec.world(T=150.0, t_open=37.0, oracle_cap=20), dict(program=BUSY), 5, {}),
    ("busy tie salt", spec.world(T=150.0, oracle_cap=20), dict(program=BUSY), 5, dict(tie=3, salt=9)),
    ("busy window 1/8", spec.world(T=100.0, window_h=0.125, n_max=20), dict(program=BUSY), 11, dict(order=4)),
    ("busy window 1/2 lockstep", spec.world(T=100.0, window_h=0.5, n_max=20, flags=LOCK), dict(program=BUSY), 5,
     dict(order=1)),
    ("busy contacts_off fork", spec.world(T=150.0, oracle_cap=20, t_fork=60.0, t_open=60.0,
                                          fork_flags=spec.flags("contacts_off")), dict(program=BUSY), 5, {}),
    ("busy chem_off fork", spec.world(T=150.0, oracle_cap=20, t_fork=30.0, fork_flags=spec.flags("chem_off")),
     dict(program=BUSY), 5, {}),
    ("busy freeze fork", spec.world(T=150.0, oracle_cap=20, t_fork=80.0, fork_flags=spec.flags("freeze")),
     dict(program=BUSY), 5, {}),
    ("busy apoptosis/division off", spec.world(T=150.0, oracle_cap=20, t_fork=40.0,
                                               fork_flags=spec.flags("apoptosis_off", "division_off")),
     dict(program=BUSY), 5, {}),
    ("busy wall R2", spec.world(T=150.0, fabric_R=2), dict(program=BUSY), 5, {}),
    ("busy guard events", spec.world(T=150.0, e_max=500), dict(program=BUSY), 5, {}),
    ("busy t0 1024", spec.world(T=150.0, t0=1024.0, oracle_cap=20), dict(program=BUSY), 5, {}),
    ("busy P0 4 clamps", spec.world(T=150.0, P0=4.0, oracle_cap=20), dict(program=BUSY), 5, {}),
    ("busy wide clocks", spec.world(T=150.0, clock_sd=0.3, tick_jit=0.3, oracle_cap=20), dict(program=BUSY), 5, {}),
    ("busy square4", spec.world(T=150.0, lattice="square4", oracle_cap=20), dict(program=BUSY), 5, {}),
    ("busy square4 window", spec.world(T=100.0, lattice="square4", window_h=0.25, n_max=20), dict(program=BUSY), 5,
     dict(order=2)),
    ("busy hex7 rows", spec.world(T=100.0, oracle_cap=20), dict(program=BUSY, init=[(0, 0, ROW["zygote"])] + [
        (a, b, -1) for a, b in HEX7[1:]]), 4, {}),
    ("busy panel t0", spec.world(T=150.0, t0=1024.0, oracle_cap=20, noise_rate=0.1, drop_p=0.1, kill_t=60.0,
                                 kill_frac=0.3, stuck_t=40.0), dict(program=BUSY), 5, {}),
    ("grn window 1/2", spec.world(T=60.0, window_h=0.5, n_max=20), dict(genome=grn_genome()), 13, dict(order=5)),
    ("grn blind clamp fixed", spec.world(T=100.0, oracle_cap=20, t_fork=40.0,
                                         fork_flags=spec.flags("identity_clamp", "genes_blind", "pheno_fixed")),
     dict(genome=grn_genome()), 13, {}),
    ("grn freeze t_open", spec.world(T=100.0, oracle_cap=20, t_fork=50.0, t_open=50.0,
                                     fork_flags=spec.flags("freeze")), dict(genome=grn_genome()), 13, {}),
    ("grn lockstep", spec.world(T=100.0, oracle_cap=20, flags=LOCK), dict(genome=grn_genome()), 1, {}),
    ("grn panel", spec.world(T=100.0, oracle_cap=20, noise_rate=0.15, drop_p=0.2, kill_t=50.0, kill_frac=0.5,
                             stuck_t=20.0), dict(genome=grn_genome()), 1, {}),
    ("grn wide clocks P0 4", spec.world(T=150.0, oracle_cap=20, P0=4.0, clock_sd=0.3, tick_jit=0.3),
     dict(genome=grn_genome()), 1, {}),
    ("grn square4", spec.world(T=100.0, lattice="square4", oracle_cap=20), dict(genome=grn_genome()), 1, {}),
]


def _t3(label, w, kw, seed, sched):
    kw = dict(kw)
    k = kernel(w, [[seed, sched.get("tie", 0), sched.get("order", 0), sched.get("salt", 0)]], **kw)
    r = reference(w, seed, **kw, **sched)
    assert not mismatch(k, 0, r), (label, mismatch(k, 0, r))
    assert not int(r.status) & (spec.STATUS["capacity"] | spec.STATUS["ledger_mismatch"])
    assert label == "lone pump" or 4 <= r["n_peak"] <= 30  # small bodies, but real ones


@pytest.mark.parametrize("label,w,kw,seed,sched", _T3_FAST, ids=[c[0] for c in _T3_FAST])
def test_t3_reference_equals_kernel_bitwise(label, w, kw, seed, sched):
    _t3(label, w, kw, seed, sched)


@pytest.mark.slow
@pytest.mark.parametrize("label,w,kw,seed,sched", _T3_SLOW, ids=[c[0] for c in _T3_SLOW])
def test_t3_reference_equals_kernel_bitwise_on_every_condition(label, w, kw, seed, sched):
    _t3(label, w, kw, seed, sched)


@pytest.mark.slow
def test_t3_reference_equals_kernel_on_random_genomes_and_programs():
    rng = np.random.default_rng(2026)
    for i in range(12):
        w = spec.world(T=float(rng.choice([60, 100, 150])), oracle_cap=int(rng.integers(6, 21)))
        k = kernel(w, [100 + i], genome=grn_genome(100 + i))
        assert not mismatch(k, 0, reference(w, 100 + i, genome=grn_genome(100 + i))), i
    for i in range(8):
        rows = []
        for _ in range(5):
            th = spec.theta(b=rng.choice(spec.Q8_GRID[16:]), tau_m=rng.choice(spec.TAU_M), t_ref=rng.choice(
                spec.T_REF), w0=rng.choice(spec.Q8_GRID), w1=rng.choice(spec.Q8_GRID), emit0=rng.integers(2),
                emit1=rng.integers(2), delta=rng.choice(spec.DELTA), kappa=rng.choice(spec.KAPPA),
                p_div=rng.choice(spec.P_FATE[5:]), p_die=rng.choice(spec.P_FATE[:5]), phi=rng.choice(spec.PHI),
                sec0=rng.random() * 0.5, pol0=rng.choice(spec.Q8_GRID), a0=rng.choice(spec.Q8_GRID),
                chi=rng.choice(spec.Q8_GRID))
            rows.append(th)
        prog = spec.pack_program(rows[1], alone=rows[0], juvenile=rows[2], rim=rows[3], zygote=rows[4],
                                 juv_ticks=float(rng.integers(0, 5)), nv_rim=float(rng.integers(0, 4)),
                                 zyg_row=float(rng.integers(2)), Dm0=0.05, km0=0.05)
        w = spec.world(T=120.0, oracle_cap=20)
        k = kernel(w, [200 + i], program=prog)
        assert not mismatch(k, 0, reference(w, 200 + i, program=prog)), i


# T4: bio's counterexample, a relay triangle with delta = 0 and opposite-sign channels, in lockstep (exact ties)
def _triangle(i_emits: bool = True):
    e = spec.theta(b=1.5, tau_m=2, t_ref=1, w0=0.5, w1=0.5, emit0=1)
    i = spec.theta(b=1.5, tau_m=2, t_ref=1, w0=0.5, w1=0.5, emit1=1.0 if i_emits else 0.0)
    relay = spec.theta(b=0.0, tau_m=1, t_ref=0.5, w0=1.0, w1=-1.0, emit0=1)
    prog = spec.pack_program(relay, alone=e, juvenile=i)
    init = [(0, 0, ROW["contact"]), (1, 0, ROW["alone"]), (0, 1, ROW["juvenile"])]
    return prog, init


def test_t4_relay_triangle_is_invariant_under_tie_orders():
    w = spec.world(T=200.0, flags=LOCK)
    prog, init = _triangle()
    seeds = [1, 2]
    base = kernel(w, seeds, program=prog, init=init)
    relay = spec.uid_initial(1, 0)
    t, u = base.spikes(0)
    te, ti = t[u == spec.uid_initial(1, 1)], t[u == spec.uid_initial(1, 2)]
    assert len(te) > 30 and np.array_equal(te, ti)  # the two senders fire at exactly the same instants
    assert not np.any(u == relay)  # +1 and -1 arriving together sum to 0: the relay never fires
    for tie in range(1, 10):
        assert same(base, kernel(w, [[s, tie, 0, tie] for s in seeds], program=prog, init=init)), tie
    for h, order in ((0.5, 1), (0.25, 2), (0.125, 3)):
        assert same(base, kernel(replace(w, window_h=h), [[s, 0, order, 0] for s in seeds], program=prog,
                                 init=init))
    assert not mismatch(base, 0, reference(w, 1, program=prog, init=init))
    prog_e, _ = _triangle(i_emits=False)  # control: excitation alone drives the relay on every sender spike
    t, u = kernel(w, [1], program=prog_e, init=init).spikes(0)
    assert np.sum(u == relay) >= 0.9 * np.sum(u == spec.uid_initial(1, 1))


def test_t5_relabelling_threads_and_batch_composition_are_bitwise_free():
    gt = spec.pack_genomes(grn_genome())
    progs = np.stack([BUSY, r25(chem=True), TURNOVER])
    worlds = [spec.world(T=150.0, flags=spec.flags("program_mode")),
              spec.world(T=150.0, flags=spec.flags("program_mode", "lockstep")), spec.world(T=96.0),
              spec.world(T=150.0, flags=spec.flags("program_mode"), window_h=0.25), spec.world(T=100.0)]
    rows = [0, 1, 0, 2, 0]
    seeds = [[5, 0, 0, 0], [6, 0, 0, 0], [13, 0, 0, 0], [7, 0, 0, 0], [21, 0, 0, 0]]

    def go(order, salt=0, threads=1):
        out = build.run([worlds[i] for i in order], [[seeds[i][0], 0, 0, salt] for i in order],
                        genomes=np.stack([gt[0]] * 3), programs=progs, genome_of=[rows[i] for i in order],
                        threads=threads, raster_cap=4096, fate_cap=4096)
        return out

    alone = [go([i]) for i in range(5)]
    for order, salt, threads in (([0, 1, 2, 3, 4], 0, 1), ([4, 3, 2, 1, 0], 1, 4), ([2, 0, 4, 1, 3], 12345, 2),
                                 ([1, 1, 3, 0, 2, 4, 4], 2 ** 63 + 5, 3)):
        mixed = go(order, salt, threads)
        for j, i in enumerate(order):
            one = build.Lives(mixed.ledger[j:j + 1], mixed.hashes[j:j + 1], mixed.raster_t[j:j + 1],
                              mixed.raster_uid[j:j + 1], mixed.raster_n[j:j + 1], mixed.fate_i[j:j + 1],
                              mixed.fate_f[j:j + 1], mixed.fate_n[j:j + 1])
            assert same(alone[i], one), (order, salt, threads, i)
    assert alone[0]["births"][0] > 20 and alone[2]["births"][0] > 0


def test_t5_each_life_indexes_only_the_table_of_its_own_mode():
    # a genome table with 3 rows and a program table with 1: the program life must be the life it is alone
    # (genome_of is checked against its own table's row count, LIFE_ABI.md 4.2), never a read past the program table
    wp, wg = spec.world(T=150.0, flags=spec.flags("program_mode")), spec.world(T=96.0)
    gt = spec.pack_genomes(np.stack([grn_genome(6), grn_genome(7), grn_genome(8)]))
    caps = dict(raster_cap=4096, fate_cap=4096)
    alone = build.run(wp, [5], programs=r25(), **caps)
    mixed = build.run([wg, wg, wp], [13, 14, 5], genomes=gt, programs=r25(), **caps)
    last = build.Lives(mixed.ledger[2:], mixed.hashes[2:], mixed.raster_t[2:], mixed.raster_uid[2:],
                       mixed.raster_n[2:], mixed.fate_i[2:], mixed.fate_f[2:], mixed.fate_n[2:])
    assert same(alone, last) and alone["births"][0] > 20
    for go in ([0, 1, 2], [0, 3, 0], [-1, 0, 0]):
        with pytest.raises(ValueError, match="outside the (program|genome) table"):
            build.run([wg, wg, wp], [13, 14, 5], genomes=gt, programs=r25(), genome_of=go)
    with pytest.raises(ValueError, match="explicit genome_of"):  # 2 rows for 4 lives: no silent default
        build.run(wp, [5, 6, 7, 8], programs=np.stack([r25(), BUSY]))
    with pytest.raises(ValueError, match="its table was not given"):
        build.run([wg, wp], [13, 5], genomes=gt[:1])


def test_t6_time_translation_moves_F_by_less_than_1e9():
    """T6 in float: the zygote and the world start at t0 = 1024 instead of 0. Only the rounding of absolute times
    changes, so every count is equal and |dF| < 1e-9 (measured: at most about 2e-12). The hashes differ, because they
    fold the absolute event times."""
    seeds = list(range(5_000_000, 5_000_004))
    cases = [(hb.R25_V1_GRN.run, dict(cap=37)), (hb.R25_V1.run, dict(cap=19))]
    for run, kw in cases:
        _assert_translated(run(seeds, threads=2, **kw), run(seeds, threads=2, t0=1024.0, **kw))
    tab = spec.pack_genomes(np.stack([grn_genome(s) for s in range(12)]))  # growing, dying, messaging genomes
    w = spec.world(T=256.0)
    a = build.run(w, [21] * 12, genomes=tab, genome_of=np.arange(12), threads=2)
    b = build.run(replace(w, t0=1024.0), [21] * 12, genomes=tab, genome_of=np.arange(12), threads=2)
    assert a["deaths"].sum() > 0 and a["births"].sum() > 0
    _assert_translated(a, b)


def _assert_translated(a, b):
    for col in ("spikes", "births", "deaths", "claims", "rejects", "n_end", "n_peak", "arrivals", "ticks", "packets"):
        assert np.array_equal(a[col], b[col]), col
    assert np.max(np.abs(a["F"] - b["F"])) < 1e-9


def test_t11_deaths_refills_and_extinction_are_window_invariant():
    w = spec.world(T=128.0)
    seeds = list(range(24))
    base = _assert_scheduler_free(w, seeds, program=TURNOVER)
    extinct = base.status("extinct")
    assert 2 <= extinct.sum() <= 22
    refills = 0
    for i in range(len(seeds)):
        kinds, f = base.fates(i)
        refills += int(np.sum((kinds[:, 0] == 1) & (kinds[:, 5] >= 1)))  # births at a site whose cell had died
        if extinct[i]:
            assert base["n_end"][i] == 0 and kinds[-1, 0] == 2 and f[-1, 0] == base["t_ext"][i]
    assert refills >= 20 and base["deaths"].sum() >= 50
    lock = _assert_scheduler_free(replace(w, flags=LOCK), seeds[:8], program=TURNOVER)
    assert lock["deaths"].sum() > 0


def test_t12_sparse_and_dense_fabrics_agree_while_the_body_stays_inside():
    seeds = list(range(16))
    for kind, kw, cap in (("hex", dict(program=r25()), 61), ("square8", dict(program=r25()), 61),
                          ("hex", dict(genome=grn_genome()), 40)):
        w = spec.world(T=256.0, lattice=kind, oracle_cap=cap)
        sparse = kernel(w, seeds, **kw)
        for R in (14, 20):
            dense = kernel(replace(w, fabric_R=R), seeds, **kw)
            assert not dense.status("wall").any()
            assert same(sparse, dense), (kind, R)
        assert sparse["n_peak"].max() > 30
    # the converse: a wall that binds is the only way a body can feel the fabric
    w = spec.world(T=256.0, oracle_cap=61)
    small = kernel(replace(w, fabric_R=3), seeds, program=r25())
    sparse = kernel(w, seeds, program=r25())
    walled = small.status("wall")
    assert walled.all()
    assert not np.any(np.all(small.ledger == sparse.ledger, axis=1) & walled)
