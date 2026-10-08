"""Time-model tests T1-T6, T11 and T12 (docs/ONE_LIFE_DESIGN.md, TESTS): whole lives, including growth and death,
must not depend on the scheduler, the tie order, cell labels, threads, batch composition, the fabric size or (in
float, to 1e-9) the start time. The second half runs the same tests on 3D CATCH bodies (ABI 3: hex prisms, receptor
events sent by the world, strokes, clicks, re-placed targets), and T3 compares the kernel with the reference there."""
from dataclasses import replace

import numpy as np
import pytest

from src.life import build, spec
from src.life import handbuilt as hb
from src.life import reference as ref
from tests.life_helpers import (
    ALONE,
    BUSY,
    COLUMN3,
    GROWER3,
    HEX7,
    PM3,
    R3,
    ROW,
    TURNOVER3,
    TURNOVER_BODY,
    V3,
    catch,
    columns,
    enclosed_tiles,
    grn3,
    grn_genome,
    hexdisk,
    kernel,
    kernel3,
    mismatch,
    r25,
    reference,
    reference3,
    same,
)

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


def _assert_scheduler_free(w, seeds, run=kernel, **kw):
    """T1: the window scheduler at h = 1/2, 1/4, 1/8, each with 3 visit orders, equals the heap bitwise."""
    base = run(w, [[s, 0, 0, 0] for s in seeds], **kw)
    for h in (0.5, 0.25, 0.125):
        for order in (1, 2, 3):
            win = run(replace(w, window_h=h), [[s, 0, 1000 * order + s, 0] for s in seeds], **kw)
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


# ============================================================================ ABI 3: the time tests on 3D CATCH bodies
# Every CATCH life below runs the full world of LIFE_ABI.md 9.7: receptor candidates thinned at the left limit and
# delivered d_min later (the first world that sends events to cells), act-plane strokes, the hotspot key, clicks,
# captures, misses, run-and-tumble targets and timer re-placements, on hex prisms of 2 or 4 planes.
LOCK3 = V3.flags("lockstep")
RING1 = columns(hexdisk(1))
TWIN = dict(b2_amp=1.0, b2_value=100.0, b2_mode=1)  # TWIN: a second, paying blob with its own timer
DECOY = dict(b2_amp=1.0, b2_value=-5.0, b2_p=0.5)  # DECOY ramp: a costly second blob, present after half the placements


def _coverage(res: build.Lives, *cols: str) -> None:
    """The lives exercised what the test is about (each named column is nonzero in at least one life)."""
    assert all(res[c].sum() > 0 for c in cols), {c: res[c].sum() for c in cols}
    assert not (res.status("capacity") | res.status("ledger_mismatch")).any()


def test_t1_window_scheduler_equals_heap_on_catch_bodies():
    # program mode: a column body with a hidden plane, a body with turnover in both control planes, both blob modes
    base = _assert_scheduler_free(catch("catch_v1_l4", T=150.0), [3, 5, 11, 17], run=kernel3, program=COLUMN3,
                                  init=columns(hexdisk(1), hidden=1))
    _coverage(base, "clicks", "captures", "misses", "respawns", "nudges", "rec_events", "path")
    base = _assert_scheduler_free(catch(T=200.0), [1, 5, 7], run=kernel3, program=TURNOVER3, init=TURNOVER_BODY)
    _coverage(base, "births", "deaths", "rejects", "clicks", "captures", "rec_events")
    for blob, seeds in ((TWIN, [1, 6]), (DECOY, [4, 5])):
        base = _assert_scheduler_free(catch(T=200.0, **blob), seeds, run=kernel3, program=COLUMN3, init=RING1)
        _coverage(base, "b2_clicks", "clicks", "respawns")
    # GRN mode: one zygote grows into 2 and 4 planes, with deaths, receptors and clicks
    base = _assert_scheduler_free(catch("catch_v1_l4", T=60.0), [25, 26, 27], run=kernel3, genome=grn3(25))
    _coverage(base, "births", "deaths", "rec_events", "clicks", "n_H_end", "n_M_end")
    base = _assert_scheduler_free(catch(T=60.0, n_max=400), [21, 22], run=kernel3, genome=grn3(21))
    _coverage(base, "births", "rec_events", "nudges")


def test_t1_window_scheduler_equals_heap_on_catch_bodies_under_lockstep_ties():
    # lockstep puts strokes, births, deaths, candidates and samples of different sites at the same instants
    base = _assert_scheduler_free(catch(T=100.0, flags=LOCK3), [3, 4], run=kernel3, program=COLUMN3, init=RING1)
    _coverage(base, "clicks", "nudges", "rec_events")
    base = _assert_scheduler_free(catch("catch_v1_l4", T=60.0, flags=LOCK3), [5, 6], run=kernel3, program=GROWER3)
    _coverage(base, "births", "deaths", "rec_events")
    base = _assert_scheduler_free(catch(T=50.0, flags=LOCK3), [26, 27], run=kernel3, genome=grn3(25))
    _coverage(base, "births", "deaths", "clicks")


def test_t2_random_tie_keys_give_bitwise_identical_catch_lives():
    for w, kw in ((catch(T=150.0), dict(program=TURNOVER3, init=TURNOVER_BODY)),
                  (catch(T=100.0, flags=LOCK3), dict(program=COLUMN3, init=RING1)),
                  (catch("catch_v1_l4", T=60.0, flags=LOCK3), dict(program=GROWER3)),
                  (catch("catch_v1_l4", T=50.0), dict(genome=grn3(25)))):
        seeds = [5, 6]
        base = kernel3(w, seeds, **kw)
        for tie in range(1, 7):
            assert same(base, kernel3(w, [[s, tie * 7919 + s, 0, 0] for s in seeds], **kw)), (w.name, tie)


def test_t2_the_oracle_cap_is_tie_free_on_catch_bodies_under_lockstep():
    for w, kw, seeds in ((catch("catch_v1_l4", T=80.0, oracle_cap=30, flags=LOCK3), dict(program=GROWER3), [5, 6]),
                         (catch(T=60.0, oracle_cap=25, flags=LOCK3), dict(genome=grn3(25)), [25, 26])):
        base = kernel3(w, seeds, **kw)
        for tie in range(1, 7):
            assert same(base, kernel3(w, [[s, tie * 7919 + s, 0, 0] for s in seeds], **kw)), tie
        assert not mismatch(kernel3(w, [[seeds[1], 3, 0, 0]], **kw), 0, reference3(w, seeds[1], tie=3, **kw))
        assert base["n_peak"].max() >= w.oracle_cap  # the cap binds


# T3 in ABI 3: the reference and the kernel agree bitwise on small CATCH bodies with growth, deaths, receptor events,
# clicks, captures, misses and timer re-placements
_FOOTLESS = [(a, b, 1, R3["contact"]) for a, b in hexdisk(1) if (a, b) != (0, 0)] + [(0, 0, 1, R3["juvenile"])]
# a footless act ring whose centre divides down (zeta -2): no traction until the foot is born, then the dot moves
_TONIC3 = V3.pack_program(V3.theta(b=2.0, tau_m=1, t_ref=0.5, kappa=1), alone=V3.theta(b=1.1, tau_m=4, t_ref=1,
                                                                                       kappa=1),
                          juvenile=V3.theta(b=1.5, tau_m=2, t_ref=1, kappa=1, p_div=1.0, zeta=-2))
_RING2 = [s for s in hexdisk(2) if max(abs(s[0]), abs(s[1]), abs(s[0] + s[1])) == 2]
# the turnover rows on the centre and ring-2 columns: six enclosed tiles that open when a rim column dies and close
# again when motors divide into the gap
_RING3 = [s for s in hexdisk(3) if max(abs(s[0]), abs(s[1]), abs(s[0] + s[1])) == 3]
_HOLLOW2_TURNOVER = [(a, b, z, R3["rim"] if (a, b, z) == (0, 0, 1) else r) for a, b, z, r in columns([(0, 0)] + _RING2)]
_T3_FAST_3 = [
    ("column ring 1", catch(T=200.0), dict(program=COLUMN3, init=RING1), 42, {}),
    ("column turnover", catch(T=200.0), dict(program=TURNOVER3, init=TURNOVER_BODY), 9, {}),
    ("grower L4 lockstep", catch("catch_v1_l4", T=80.0, flags=LOCK3), dict(program=GROWER3), 5, {}),
    ("footless then a foot", catch(T=60.0), dict(program=_TONIC3, init=_FOOTLESS), 4, {}),
    ("stuck hotspot", catch(T=100.0, stuck_t=20.0, stuck_z=1), dict(program=COLUMN3, init=RING1), 2, {}),
    ("twin t_open", catch(T=200.0, t_open=50.5, **TWIN), dict(program=COLUMN3, init=RING1), 6, {}),
    ("grn L4 window", catch("catch_v1_l4", T=50.0, window_h=0.125), dict(genome=grn3(25)), 25, dict(order=5)),
    ("grn L2 guard", catch(T=200.0, n_max=10), dict(genome=grn3(25)), 25, {}),
    # RT-T1 (15.61): bodies whose filled footprint has holes that open and close while they move
    ("hollow ring 2 turnover", catch(T=200.0), dict(program=TURNOVER3, init=_HOLLOW2_TURNOVER), 11, {}),
    ("grn L4 holes", catch("catch_v1_l4", T=80.0, oracle_cap=60), dict(genome=grn3(5031, p_die=0.6, p_div=1.1)), 12,
     {}),
]
_T3_SLOW_3 = [
    ("column L4 hidden", catch("catch_v1_l4", T=120.0), dict(program=COLUMN3, init=columns(hexdisk(1), hidden=2)), 3,
     {}),
    ("column kill panel", catch(T=120.0, kill_t=40.0, kill_frac=0.4), dict(program=COLUMN3, init=RING1), 2, {}),
    ("column noise drop", catch(T=100.0, noise_rate=0.15, drop_p=0.1), dict(program=COLUMN3, init=RING1), 9, {}),
    ("column lockstep window", catch(T=100.0, flags=LOCK3, window_h=0.5), dict(program=COLUMN3, init=RING1), 3,
     dict(order=2)),
    ("column t0 -37 window", catch(T=100.0, t0=-37.0, window_h=0.25), dict(program=COLUMN3, init=RING1), 11,
     dict(order=1)),
    ("column t0 1024 tie salt", catch(T=100.0, t0=1024.0), dict(program=COLUMN3, init=RING1), 12,
     dict(tie=5, salt=7)),
    ("twin", catch(T=200.0, **TWIN), dict(program=COLUMN3, init=RING1), 6, {}),
    ("twin without timers", catch(T=150.0, b2_amp=0.5, b2_value=50.0, b2_mode=1, t_resp=0.0),
     dict(program=COLUMN3, init=RING1), 7, {}),
    ("still target, no turns", catch(T=150.0, drag_exp=0.0, v_t=0.0, tau_turn=0.0), dict(program=COLUMN3,
                                                                                         init=RING1), 14, {}),
    ("drag 1, gain 2", catch(T=150.0, drag_exp=1.0, g_n=2.0), dict(program=COLUMN3, init=RING1), 13, {}),
    ("no light", catch(T=60.0, lam_s=0.0, lam_bg=0.0), dict(program=COLUMN3, init=RING1), 1, {}),
    ("dense fabric R1", catch(T=150.0, fabric_R=1), dict(program=COLUMN3, init=RING1), 42, {}),
    ("dense fabric R2 grn", catch("catch_v1_l4", T=60.0, fabric_R=2), dict(genome=grn3(25)), 25, {}),
    ("square4prism", catch(T=100.0, lattice="square4prism"),
     dict(program=COLUMN3, init=columns([(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)])), 3, {}),
    ("square8prism grn", catch("catch_v1_l4", T=40.0, lattice="square8prism"), dict(genome=grn3(25)), 25, {}),
    ("motor and lateral off", catch("catch_v1_l4", T=120.0, t_fork=50.0, fork_flags=V3.flags("motor_off",
                                                                                            "lateral_off")),
     dict(program=COLUMN3, init=columns(hexdisk(1), hidden=1)), 3, {}),
    ("receptor and hidden off", catch("catch_v1_l4", T=60.0, t_fork=30.0, fork_flags=V3.flags("receptor_off",
                                                                                             "hidden_off")),
     dict(genome=grn3(25)), 25, {}),
    ("grower L2", catch(T=150.0), dict(program=GROWER3), 6, {}),
    ("grn L4 tie salt", catch("catch_v1_l4", T=60.0), dict(genome=grn3(25)), 25, dict(tie=7, salt=3)),
    ("grn L2 cap", catch(T=60.0, oracle_cap=40), dict(genome=grn3(21)), 21, {}),
    ("grn L4 genes blind", catch("catch_v1_l4", T=50.0, flags=V3.flags("genes_blind")), dict(genome=grn3(25)), 25,
     {}),
    ("hollow ring 3 static", catch(T=200.0), dict(program=COLUMN3, init=columns([(0, 0)] + _RING3)), 11, {}),
    ("grower L2 holes", catch(T=150.0), dict(program=GROWER3), 13, {}),
    ("grn L2 holes", catch(T=80.0, oracle_cap=60), dict(genome=grn3(5032, p_die=0.6, p_div=1.1)), 13, {}),
    ("grn square4prism holes", catch(T=80.0, oracle_cap=60, lattice="square4prism"),
     dict(genome=grn3(5020, p_die=0.6, p_div=1.1)), 11, {}),
    ("grn square8prism holes", catch(T=80.0, oracle_cap=60, lattice="square8prism"),
     dict(genome=grn3(5020, p_die=0.6, p_div=1.1)), 11, {}),
    ("bell on a prism", spec.world(T=60.0, lattice="hexprism", L_max=3), dict(genome=grn3(25)), 25, {}),
]


def _t3_catch(label, w, kw, seed, sched):
    k = kernel3(w, [[seed, sched.get("tie", 0), sched.get("order", 0), sched.get("salt", 0)]], **kw)
    r = reference3(w, seed, **kw, **sched)
    assert not mismatch(k, 0, r), (label, mismatch(k, 0, r))
    assert not int(r.status) & (spec.STATUS["capacity"] | spec.STATUS["ledger_mismatch"])
    return r


def test_t3_reference_equals_kernel_bitwise_on_catch_bodies():
    rs = [_t3_catch(*case) for case in _T3_FAST_3]
    for case, r in zip(_T3_FAST_3, rs):  # the RT-T1 cases enclose tiles while they move, grow and die (15.61)
        if "holes" in case[0] or "hollow" in case[0]:
            assert enclosed_tiles(r.fate_i, r.fate_f, case[1].lattice) > 0 and r["deaths"] > 10 and r["path"] > 3
    tot = {c: sum(r[c] for r in rs) for c in ("births", "deaths", "rejects", "rec_events", "clicks", "captures",
                                               "misses", "b2_clicks", "respawns", "nudges")}
    assert min(tot.values()) > 0, tot  # the list covers every CATCH path the test is named for
    assert any(r.status & spec.STATUS["guard_cells"] for r in rs) and max(r["n_peak"] for r in rs) <= 128


@pytest.mark.slow
@pytest.mark.parametrize("label,w,kw,seed,sched", _T3_SLOW_3, ids=[c[0] for c in _T3_SLOW_3])
def test_t3_reference_equals_kernel_bitwise_on_every_catch_condition(label, w, kw, seed, sched):
    r = _t3_catch(label, w, kw, seed, sched)
    if "holes" in label or "hollow" in label:  # RT-T1 (15.61): the filled footprint differs from the columns
        assert enclosed_tiles(r.fate_i, r.fate_f, w.lattice) > 0 and r["path"] > 3


@pytest.mark.slow
def test_t3_reference_equals_kernel_on_random_catch_genomes_and_programs():
    rng = np.random.default_rng(2027)
    for i in range(24):  # random readout biases, both stacks, random second blobs and forks
        shift = dict(b=rng.uniform(0.5, 1.8), w0=rng.uniform(-1.5, 1.0), emit0=rng.uniform(-0.5, 1.5),
                     kappa=rng.uniform(0.0, 2.0), p_div=rng.uniform(0.4, 1.2), p_die=rng.uniform(-0.5, 0.6),
                     g_r=rng.uniform(-1.5, 1.5), zeta=rng.uniform(-2.0, 2.0), pol0=rng.uniform(-1, 1))
        extra = dict(oracle_cap=40)
        if i % 3 == 0:
            extra.update(b2_amp=float(rng.uniform(0.3, 1.5)), b2_value=float(rng.choice([-5.0, 50.0])),
                         b2_mode=i % 2, b2_p=float(rng.uniform(0.2, 1.0)), b2_sigma=float(rng.uniform(1.0, 2.5)))
        if i % 4 == 1:
            extra.update(t_fork=15.0, fork_flags=V3.flags(*rng.choice(
                ["receptor_off", "lateral_off", "hidden_off", "motor_off", "chem_off"], 2, replace=False)))
        w = catch(("catch_v1_l2", "catch_v1_l4")[i % 2], T=40.0, **extra)
        g = grn3(3000 + i, **shift)
        assert not mismatch(kernel3(w, [3000 + i], genome=g), 0, reference3(w, 3000 + i, genome=g)), (i, extra)
    for i in range(10):  # random column programs on random column sets, 0-2 hidden planes, some in lockstep
        cols = [c for c in hexdisk(1) if c == (0, 0) or rng.random() < 0.8]
        sense = V3.theta(g_r=float(rng.choice([0.5, 1.0, -0.5, 0.25])), emit0=1, emit1=float(rng.random() < 0.3),
                         tau_m=float(rng.choice([1, 2, 4])), t_ref=0.5, delta=float(rng.choice([0, 0.5])),
                         p_die=float(rng.choice([0.0, 2.0 ** -6])))
        centre = V3.theta(g_r=0.55, emit0=1, tau_m=1, t_ref=0.5, kappa=float(rng.choice([0, 0.25])))
        motor = V3.theta(w0=float(rng.choice([1, 0.75, 1.25])), w1=float(rng.choice([0, -0.5])),
                         kappa=float(rng.choice([0.5, 1.0])), t_ref=float(rng.choice([2, 4])), tau_m=1,
                         b=float(rng.choice([0, 0.5])), p_div=float(rng.choice([0.0, 1 / 32])))
        hid = V3.theta(b=float(rng.choice([0.0, 1.5])), tau_m=4, t_ref=2, emit0=1, w0=0.5)
        prog = V3.pack_program(motor, alone=sense, juvenile=centre, rim=hid)
        w = catch("catch_v1_l4", T=80.0, flags=LOCK3 if i % 4 == 0 else 0)
        init = columns(cols, hidden=int(rng.integers(0, 3)))
        k = kernel3(w, [[4000 + i, i, 0, i % 3]], program=prog, init=init)
        assert not mismatch(k, 0, reference3(w, 4000 + i, program=prog, init=init, tie=i, salt=i % 3)), i
    for i in range(12):  # random selector growers from one zygote: every row divides, places by zeta and polarity
        rows = [V3.theta(b=float(rng.choice([0.0, 1.125, 1.5])), tau_m=float(rng.choice(spec.TAU_M)),
                         t_ref=float(rng.choice(spec.T_REF)), w0=float(rng.choice(spec.Q8_GRID)),
                         emit0=float(rng.random() < 0.6), kappa=float(rng.choice(spec.KAPPA)),
                         g_r=float(rng.choice([0.0, 0.5, 1.0, -0.5])), zeta=float(rng.choice([-2, -1, 0, 1, 2])),
                         p_div=float(rng.choice([1 / 16, 1 / 4, 1 / 2])), p_die=float(rng.choice([0.0, 1 / 32])),
                         phi=float(rng.choice(spec.PHI)), sec0=0.25, pol0=float(rng.choice([0.0, 1.0, -1.0])),
                         a0=float(rng.choice([0.0, 0.5])), chi=float(rng.choice([0.0, 0.5]))) for _ in range(5)]
        prog = V3.pack_program(rows[1], alone=rows[0], juvenile=rows[2], rim=rows[3], zygote=rows[4],
                               juv_ticks=float(rng.integers(0, 4)), nv_rim=float(rng.integers(0, 5)),
                               zyg_row=float(rng.integers(2)), Dm0=0.05, km0=0.05, prune=float(rng.integers(2)),
                               k_keep=1.0, k_die=6.0, timer_step=1.0, k_grow=float(rng.integers(2, 10)))
        w = catch(("catch_v1_l2", "catch_v1_l4")[i % 2], T=60.0, n_max=120, flags=LOCK3 if i % 5 == 0 else 0)
        k = kernel3(w, [[5000 + i, 0, 0, i]], program=prog)
        assert not mismatch(k, 0, reference3(w, 5000 + i, program=prog, salt=i)), i


def test_t3_reference_equals_kernel_when_receptor_deliveries_merge_on_a_coarse_clock():
    """The rare group-3 paths (LIFE_ABI.md 6.2, 7.2, 7.10): near |t| = 2^30 time has a resolution of 2^-22, so with
    1000 candidates per unit some candidate steps are nextup, an odd d_min lets two deliveries round to one instant
    (n_rec = 2), and a candidate can share its batch with a delivery (R_RCAND before R_RECEPT)."""
    prog = V3.pack_program(V3.theta(g_r=0.125, b=0.5, tau_m=1, t_ref=0.5, w0=0.25, emit0=1, kappa=0.5),
                           alone=V3.theta(g_r=0.25, b=-1, tau_m=2, t_ref=0.5, emit0=1, w0=0.5, kappa=1))
    body = [(0, 0, 0, R3["contact"]), (1, 0, 0, R3["alone"]), (0, 0, 1, R3["alone"]), (1, 0, 1, R3["contact"])]
    w = catch(T=8.0, t0=2.0 ** 30 - 16, d_min=0.5 + 3 * 2.0 ** -24, lam_bg=1000.0, lam_s=0.0, t_resp=0.0)
    merged = shared = 0
    for seed in (1, 2):
        k = kernel3(w, [seed], program=prog, init=body)
        r = reference3(w, seed, program=prog, init=body, records=True)
        assert not mismatch(k, 0, r), mismatch(k, 0, r)
        assert same(k, kernel3(replace(w, window_h=0.25), [[seed, 0, 3, 0]], program=prog, init=body))
        merged += sum(p[1] == 2 for _t, _sk, _q, kind, p in r.records if kind == ref.R_RECEPT)
        batches = {}
        for t, sk, _q, kind, _p in r.records:
            batches.setdefault((t, sk), set()).add(kind)
        shared += sum(ref.R_RCAND in v and ref.R_RECEPT in v for v in batches.values())
    assert merged > 0 and shared > 0


def test_t5_catch_lives_do_not_depend_on_labels_threads_or_their_batch():
    gt = V3.pack_genomes(np.stack([grn3(25), grn3(21)]), "hexprism")
    progs = np.stack([COLUMN3, TURNOVER3, GROWER3])
    worlds = [catch(T=120.0, flags=PM3), catch("catch_v1_l4", T=50.0), catch(T=150.0, flags=PM3, window_h=0.25),
              spec.world(T=60.0, lattice="hexprism", L_max=3), catch("catch_v1_l4", T=60.0, flags=PM3 | LOCK3),
              catch(T=100.0, flags=PM3, **TWIN)]
    rows = [0, 0, 1, 1, 2, 0]
    bodies = [RING1, [(0, 0)], TURNOVER_BODY, [(0, 0)], [(0, 0)], RING1]
    seeds = [2, 25, 7, 21, 6, 8]

    def go(order, salt=0, threads=1):
        return build.run([worlds[i] for i in order], [[seeds[i], 0, 0, salt] for i in order], genomes=gt,
                         programs=progs, genome_of=[rows[i] for i in order], init=[bodies[i] for i in order],
                         threads=threads, raster_cap=4096, fate_cap=4096, abi=V3)

    alone = [go([i]) for i in range(len(worlds))]
    for order, salt, threads in (([0, 1, 2, 3, 4, 5], 0, 1), ([5, 4, 3, 2, 1, 0], 1, 4), ([2, 0, 4, 1, 5, 3], 12345, 2),
                                 ([1, 1, 3, 0, 2, 4, 5, 5], 2 ** 63 + 5, 3)):
        mixed = go(order, salt, threads)
        for j, i in enumerate(order):
            one = build.Lives(mixed.ledger[j:j + 1], mixed.hashes[j:j + 1], mixed.raster_t[j:j + 1],
                              mixed.raster_uid[j:j + 1], mixed.raster_n[j:j + 1], mixed.fate_i[j:j + 1],
                              mixed.fate_f[j:j + 1], mixed.fate_n[j:j + 1], abi=V3)
            assert same(alone[i], one), (order, salt, threads, i)
    assert alone[0]["captures"][0] > 0 and alone[1]["births"][0] > 20 and alone[2]["deaths"][0] > 0
    assert alone[3].hashes[0, 4] == spec.HASH_INIT and alone[5]["b2_clicks"][0] > 0


def test_t6_time_translation_moves_catch_F_by_less_than_1e9():
    """T6 on CATCH bodies: the zygote, the world and its targets start at t0 = 1024. Only the rounding of absolute
    times changes, so every count is equal (clicks, captures, receptor decisions included) and |dF| < 1e-9."""
    for w, kw, seeds in ((catch(T=200.0), dict(program=COLUMN3, init=columns(hexdisk(1), hidden=0)), range(8)),
                         (catch(T=200.0), dict(program=TURNOVER3, init=TURNOVER_BODY), range(8)),
                         (catch("catch_v1_l4", T=80.0, n_max=150), dict(genome=grn3(25)), range(6))):
        a, b = kernel3(w, list(seeds), **kw), kernel3(replace(w, t0=1024.0), list(seeds), **kw)
        for col in ("spikes", "births", "deaths", "claims", "n_end", "arrivals", "ticks", "clicks", "captures",
                    "misses", "respawns", "nudges", "rec_cand", "rec_accept", "rec_events", "samples",
                    "zone_samples"):
            assert np.array_equal(a[col], b[col]), col
        assert np.max(np.abs(a["F"] - b["F"])) < 1e-9 and np.max(np.abs(a["X_end"] - b["X_end"])) < 1e-9
        assert a["clicks"].sum() > 0 and a["rec_events"].sum() > 0


def test_t11_catch_deaths_refills_and_extinction_are_window_invariant():
    # every cell can die; motors refill the act plane; whole bodies go extinct while the world runs on
    w = catch(T=128.0)
    dieout = V3.pack_program(V3.theta(w0=1.0, kappa=1.0, t_ref=4.0, tau_m=2, p_div=1 / 32, p_die=1 / 16),
                             alone=V3.theta(g_r=1.0, emit0=1, tau_m=2, t_ref=1, p_die=1 / 32),
                             juvenile=V3.theta(g_r=0.55, emit0=1, tau_m=2, t_ref=1, p_die=1 / 32))
    seeds = list(range(12))
    base = _assert_scheduler_free(w, seeds, run=kernel3, program=dieout, init=columns([(0, 0), (1, 0)]))
    extinct = base.status("extinct")
    assert 2 <= extinct.sum() <= 10 and base["births"].sum() > 0
    assert np.all(base["samples"] == w.T - 1)  # extinction never stops the world (9.7.6)
    for i in np.flatnonzero(extinct):
        kinds, f = base.fates(i)
        assert base["n_end"][i] == 0 and kinds[-1, 0] == 2 and f[-1, 0] == base["t_ext"][i]
        assert np.all(f[:, 0] <= base["t_ext"][i])


def test_t12_sparse_and_dense_3d_fabrics_agree_while_the_body_stays_inside():
    seeds = list(range(8))
    for w, kw in ((catch("catch_v1_l4", T=80.0, oracle_cap=40), dict(genome=grn3(25))),
                  (catch(T=120.0, oracle_cap=40), dict(program=GROWER3)),
                  (catch(T=120.0), dict(program=TURNOVER3, init=TURNOVER_BODY))):
        sparse = kernel3(w, seeds, **kw)
        for R in (12, 20):
            dense = kernel3(replace(w, fabric_R=R), seeds, **kw)
            assert not dense.status("wall").any()
            assert same(sparse, dense), (w.name, R)
        assert sparse["n_peak"].max() > 20 and sparse["births"].sum() > 0
    # the converse: a wall that binds changes the life (walls reject claims, and an act cell facing one pulls)
    w = catch("catch_v1_l4", T=80.0, oracle_cap=40)
    walled = kernel3(replace(w, fabric_R=1), seeds, genome=grn3(25))
    assert walled.status("wall").all() and walled["n_peak"].max() <= 7 * 4
    assert not np.any(np.all(walled.ledger == kernel3(w, seeds, genome=grn3(25)).ledger, axis=1))
    # a wall is a site the fabric does not have: no initial cell may sit there (LIFE_ABI.md 4.6, 15.57), in either ABI
    ring2 = columns(hexdisk(2))
    for kw in (dict(fabric_R=1), dict(fabric_R=1, lattice="square8prism")):
        with pytest.raises(ValueError, match="-4"):
            kernel3(catch(T=20.0, **kw), [1], program=COLUMN3, init=ring2)
        with pytest.raises(ref.ArgError) as err:
            reference3(catch(T=20.0, **kw), 1, program=COLUMN3, init=ring2)
        assert err.value.rc == -4
    assert kernel3(catch(T=20.0, fabric_R=1), [1], program=COLUMN3, init=RING1)["n_end"][0] == 14  # inside: fine
    flat = spec.world(T=20.0, fabric_R=1)
    with pytest.raises(ValueError, match="-4"):
        kernel(flat, [1], program=BUSY, init=hexdisk(2))
    with pytest.raises(ref.ArgError):
        reference(flat, 1, program=BUSY, init=hexdisk(2))
