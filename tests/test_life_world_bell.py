"""BELL-1 lumen tests (docs/ONE_LIFE_DESIGN.md, TESTS: test_life_world_bell.py): the closed-form lumen against Euler
integration, no pay for tonic saturation, the lone-cell reference point, and income per cell bounded by the lone rate.
Since ABI 3 (CATCH) the kernel also carries a second world kind; golden BELL lives pin BELL bitwise across that bump."""
import itertools

import numpy as np
import pytest

from src.life import build, spec
from src.life import reference as ref
from tests.life_helpers import BUSY, HEX7, PM, grn_genome, kernel, mismatch, r25, reference

PUMP = spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1)  # the design's best lone cell (gate G1)
FAST = spec.theta(b=2.0, tau_m=1, t_ref=0.5, kappa=1)  # fastest tonic firing: z never decays below th


def _euler_income(t_sp, uid_sp, n: int, w: spec.World, dt: float = 1e-3, chunk: int = 2000) -> float:
    """Explicit Euler (step dt) of the BELL-1 lumen for a fixed body of n cells with kappa = 1 (z = 1 at a spike):
    P = mean z, dR/dt = -R (P - th) / ((1 - th) tau_e) in systole, (1 - R) / tau_R in diastole, 0 between."""
    steps = int(round(w.T / dt))
    ts = w.t0 + np.arange(steps) * dt
    P = np.zeros(steps)
    for u in np.unique(uid_sp):
        ti = t_sp[uid_sp == u]
        k = np.searchsorted(ti, ts, side="right")
        last = np.where(k > 0, ti[np.maximum(k - 1, 0)], -np.inf)
        P += np.exp(-(ts - last) / w.tau_z)
    P /= n
    sys_rate = np.where(P > w.th, (P - w.th) / ((1.0 - w.th) * w.tau_e), 0.0)
    dia = P < w.th_lo
    a = np.where(dia, 1.0 - dt / w.tau_R, 1.0 - dt * sys_rate)  # R_{j+1} = a_j R_j + b_j
    b = np.where(dia, dt / w.tau_R, 0.0)
    R, income = 1.0, 0.0
    for s in range(0, steps, chunk):  # affine scan, exact enough within chunks where prod(a) >= 0.98^20
        aa, bb = a[s:s + chunk], b[s:s + chunk]
        c = np.cumprod(aa)
        nxt = c * (R + np.cumsum(bb / c))
        states = np.concatenate(([R], nxt[:-1]))
        income += float(np.sum(states * sys_rate[s:s + chunk])) * dt * n * w.h_inc
        R = float(nxt[-1])
    return income


def test_closed_form_lumen_matches_euler_within_0_1_percent():
    contact = spec.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1)  # R25-v1 coupled inhibitor
    w = spec.world(flags=spec.flags("division_off"))
    for prog, init, n in ((spec.pack_program(PUMP), None, 1), (spec.pack_program(contact, alone=PUMP), HEX7, 7)):
        for seed in (3, 4):
            res = kernel(w, [seed], program=prog, init=init, cap=1 << 16)
            t, u = res.spikes(0)
            closed = res["income"][0]
            euler = _euler_income(t, u, n, w)
            assert closed > 10 and abs(closed - euler) / euler < 1e-3, (n, seed, closed, euler)


def test_fast_tonic_firing_earns_nothing():
    """No refill without relaxation: P never falls below th, so the lumen empties once and then pays nothing."""
    for prog, init, n in ((spec.pack_program(FAST), None, 1), (spec.pack_program(FAST, alone=FAST), HEX7, 7)):
        w = spec.world(flags=spec.flags("division_off"))
        res = kernel(w, list(range(4)), program=prog, init=init)
        assert np.all(res["spikes"] > 700 * n) and np.all(res["beats"] == 1)
        assert np.all(res["income"] <= n * w.h_inc * (1 + 1e-12)) and np.all(res["F"] < -0.02)  # one fill at most
        late = kernel(spec.world(t_open=512.0, flags=spec.flags("division_off")), list(range(4)), program=prog,
                      init=init)
        assert np.all(late["income"] < 1e-12) and np.all(late["beats"] == 0)
    slow = kernel(spec.world(), list(range(4)), program=spec.pack_program(PUMP))
    assert np.all(slow["income"] > 50.0)


def test_a_lone_cell_scores_about_plus_0_033():
    w = spec.world()
    res = kernel(w, list(range(16)), program=spec.pack_program(PUMP))
    assert abs(res["F"].mean() - 0.0326) < 3e-4 and np.all(np.abs(res["F"] - 0.0326) < 1.5e-3)
    assert np.all(res["n_end"] == 1) and np.all(res["births"] == 0) and np.all(res["contact_events"] == 0)
    for i in (0, 1):
        assert not mismatch(res, i, reference(w, i, program=spec.pack_program(PUMP)))
    # exhaustive over the knob grid that matters for a lone cell (b > 1, tau_m, t_ref, kappa): the best is +0.033
    combos = list(itertools.product([k / 8 for k in range(9, 17)], spec.TAU_M, spec.T_REF, spec.KAPPA))
    progs = np.stack([spec.pack_program(spec.theta(b=b, tau_m=t, t_ref=r, kappa=k)) for b, t, r, k in combos])
    lives = 4
    grid = build.run(spec.world(flags=PM), [s for _ in combos for s in range(lives)], programs=progs,
                     genome_of=np.repeat(np.arange(len(combos)), lives), threads=4)
    F = grid["F"].reshape(-1, lives).mean(axis=1)
    best = F.max()
    assert 0.032 < best < 0.034 and F[combos.index((1.875, 8.0, 2.0, 1.0))] > 0.99 * best
    assert np.all(F[[i for i, c in enumerate(combos) if c[3] == 0.0]] < -0.02)  # no contraction, no income


def test_income_per_cell_never_exceeds_the_lone_rate():
    w = spec.world(flags=PM)
    combos = list(itertools.product([k / 8 for k in range(9, 17)], spec.TAU_M, spec.T_REF))
    progs = np.stack([spec.pack_program(spec.theta(b=b, tau_m=t, t_ref=r, kappa=1)) for b, t, r in combos])
    lone = build.run(w, list(range(len(combos))), programs=progs, threads=4)
    rate = (lone["income"] / lone["live_time"]).max()
    assert 0.053 < rate < 0.055  # the design's lone income rate, 54e-3
    best = 0.0
    bodies = [(spec.world(oracle_cap=c), dict(program=r25())) for c in (7, 19, 37, 61, 91)]
    bodies += [(spec.world(T=512.0, oracle_cap=120), dict(program=BUSY)),
               (spec.world(T=256.0, oracle_cap=60), dict(genome=grn_genome())),
               (spec.world(oracle_cap=37, t_fork=512.0, fork_flags=spec.flags("contacts_off")), dict(program=r25())),
               (spec.world(flags=spec.flags("division_off")), dict(program=spec.pack_program(PUMP), init=HEX7)),
               (spec.world(flags=spec.flags("division_off", "lockstep")), dict(program=spec.pack_program(PUMP),
                                                                               init=HEX7))]
    for wb, kw in bodies:
        res = kernel(wb, list(range(8)), threads=4, **kw)
        per_cell = res["income"] / res["live_time"]
        assert np.all(per_cell <= rate), (wb, per_cell.max() / rate)
        best = max(best, per_cell.max())
    assert best > 0.8 * rate  # the bound is approached by small synchronized bodies, never exceeded


# ===================================================================== BELL regression across the ABI-3 bump
# The `all` hash of 3 lives (seeds 11-13) per case, computed by the ABI-2 kernel of commit 7d3896d (before ABI 3).
# `all` folds every record word and every ABI-2 ledger column, so equality pins each life bitwise (LIFE_ABI.md 9.6,
# 15.33: program and GRN mode move by exactly 0 per life). Cases built by _golden_cases below.
BELL_GOLDEN = {
    "R25-v1 cap 37": ("1d1818084bb0e44a", "4d00268c2881f451", "0c577819df5883cf"),
    "lone pump": ("8aac5d89c1996638", "cc4c872511d4fa30", "77de9b76fe12a47a"),
    "BUSY hex": ("48979066167ae48a", "08804346ff679d6b", "37aedb8abe439aee"),
    "BUSY square8": ("4dd6f7bf610fdbdf", "d04a2a126d91dc85", "1e1c245ac19239b5"),
    "BUSY square4": ("5e48096d8d8f6e02", "ae5d77c81106c07a", "20a690df903688c0"),
    "BUSY lockstep HEX7": ("b7839925a1e7fe21", "6a4569eeda864352", "1ce400b1d585b95d"),
    "BUSY panel": ("210ca53dafbd9f25", "bb81c11bc0e77a74", "d2d12afab6d45ca4"),
    "BUSY window guard": ("2611d125a14c5f04", "8685d9b85a29b5e2", "3f0ceeacef9bd5c4"),
    "BUSY contacts_off fork": ("5da7fb8a593e0ab6", "bfca431ac503f85e", "4cac9f5859a72294"),
    "BUSY t0 1024": ("a6140473477816ed", "65ae3aa5812fbb8f", "2d9ead179302b898"),
    "BUSY wall R2": ("3a0b71e12def42fe", "555b9557ed976365", "295641315a024976"),
    "GRN hex cap 20": ("9b7f4c33c128086c", "ece197aa612632ec", "32570942f22cc224"),
    "GRN square8 cap 16": ("0a3676e60cc2bc85", "e7e911806a949901", "0199bcee0eb9815b"),
    "GRN freeze fork": ("55066d2d7826279a", "b57d27111069bcb8", "333b360275d185c9"),
}


def _golden_cases(theta, pack_program, pack_genomes, world, flags, genome_size, genome_view, K):
    """The golden BELL lives, built from ABI-2 packers only (the same code produced the goldens on HEAD)."""
    coupled = theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1)
    pump = theta(b=1.875, tau_m=8, t_ref=2, kappa=1)

    def knobs(row, **kw):
        out = np.array(row, dtype=np.float64)
        for k, v in kw.items():
            out[K[k]] = float(v)
        return out

    def r25(chem=False, **extra):
        contact = knobs(coupled, p_div=0.5, phi=2, **extra)
        return pack_program(contact, alone=knobs(pump, p_div=0.5, phi=2), juvenile=knobs(contact, emit0=0, emit1=0),
                            juv_ticks=10, flank_gate=2, p_div_lo=1 / 16,
                            **(dict(Dm0=0.05, Dm1=0.02, km0=0.05, km1=0.1) if chem else {}))

    busy = r25(chem=True, p_die=2.0 ** -6, sec0=0.3, sec1=0.1, pol0=1.0, a0=0.5, chi=0.5)
    rng = np.random.default_rng(6)
    g = (rng.normal(0, 0.7, genome_size)).astype(np.float32)
    act = genome_view(g, "act")
    act[:] = 0.0
    act[:8] = 1.0
    a0 = genome_view(g, "a0")
    for knob, shift in (("b", 1.3), ("w0", -0.8), ("emit0", 0.8), ("kappa", 1.5), ("p_div", 1.4), ("p_die", 0.3)):
        a0[K[knob]] += shift
    pm, lock = flags("program_mode"), flags("lockstep")
    hex7 = [(0, 0), (1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
    return {  # label: (world, kwargs of build.run)
        "R25-v1 cap 37": (world(oracle_cap=37, flags=pm), dict(programs=r25())),
        "lone pump": (world(flags=pm), dict(programs=pack_program(pump))),
        "BUSY hex": (world(T=200.0, flags=pm), dict(programs=busy)),
        "BUSY square8": (world(T=150.0, lattice="square8", flags=pm), dict(programs=busy)),
        "BUSY square4": (world(T=150.0, lattice="square4", flags=pm), dict(programs=busy)),
        "BUSY lockstep HEX7": (world(T=150.0, flags=pm | lock), dict(programs=busy, init=hex7)),
        "BUSY panel": (world(T=120.0, oracle_cap=20, noise_rate=0.1, drop_p=0.1, kill_t=60.0, kill_frac=0.3,
                             stuck_t=40.0, flags=pm), dict(programs=busy)),
        "BUSY window guard": (world(T=120.0, window_h=0.25, n_max=20, flags=pm), dict(programs=busy)),
        "BUSY contacts_off fork": (world(T=150.0, oracle_cap=20, t_fork=60.0, t_open=60.0, flags=pm,
                                         fork_flags=flags("contacts_off")), dict(programs=busy)),
        "BUSY t0 1024": (world(T=150.0, t0=1024.0, oracle_cap=20, flags=pm), dict(programs=busy)),
        "BUSY wall R2": (world(T=150.0, fabric_R=2, flags=pm), dict(programs=busy)),
        "GRN hex cap 20": (world(T=96.0, oracle_cap=20), dict(genomes=pack_genomes(g, "hex"))),
        "GRN square8 cap 16": (world(T=80.0, lattice="square8", oracle_cap=16),
                               dict(genomes=pack_genomes(g, "square8"))),
        "GRN freeze fork": (world(T=100.0, oracle_cap=20, t_fork=50.0, t_open=50.0, fork_flags=flags("freeze")),
                            dict(genomes=pack_genomes(g, "hex"))),
    }


def _golden():
    V2 = spec.V2
    return _golden_cases(V2.theta, V2.pack_program, V2.pack_genomes, spec.world, V2.flags, V2.GENOME_SIZE,
                         V2.genome_view, V2.K)


def test_bell_lives_are_bitwise_those_of_the_abi2_kernel():
    """GB1 as a regression test: every golden BELL life, program mode and GRN mode, through the ABI-3 kernel in ABI
    2's shapes, and in ABI 3's shapes with neutrally padded tables (the `all` hash then folds 57 ledger columns, and
    undoing the 22 extra folds gives ABI 2's; the world hash stays HASH_INIT)."""
    V3 = spec.V3
    cases = _golden()
    assert set(cases) == set(BELL_GOLDEN)
    for label, (w, kw) in cases.items():
        want = np.array([int(h, 16) for h in BELL_GOLDEN[label]], dtype=np.uint64)
        two = build.run(w, [11, 12, 13], abi=spec.V2, **kw)
        assert np.array_equal(two.hashes[:, 0], want), label
        pad = {k: (V3.pad_program(v, spec.V2) if k == "programs" else V3.pad_genomes(v, spec.V2)) if k != "init"
               else v for k, v in kw.items()}
        three = build.run(w, [11, 12, 13], abi=V3, **pad)
        assert np.array_equal(build.unfold_close(three.hashes[:, 0], three.ledger, 35), want), label
        assert np.array_equal(three.hashes[:, 1:4], two.hashes[:, 1:]) and np.all(three.hashes[:, 4] == spec.HASH_INIT)
        assert np.array_equal(three.ledger[:, :35].view(np.uint64), two.ledger.view(np.uint64)), label


@pytest.mark.slow
def test_the_reference_reproduces_the_abi2_golden_bell_lives():
    for label, (w, kw) in _golden().items():
        if w.T > 200 or label.startswith("BUSY hex") or "lockstep" in label:
            continue  # the long and the big lives are the kernel's (above)
        prog, genome = kw.get("programs"), kw.get("genomes")
        cells = kw.get("init")
        r = ref.run(w, program=prog, genome_table=None if genome is None else genome[0], cells=cells, seed=12,
                    abi=spec.V2)
        assert int(r.hashes[0]) == int(BELL_GOLDEN[label][1], 16), label
