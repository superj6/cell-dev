"""BELL-1 lumen tests (docs/ONE_LIFE_DESIGN.md, TESTS: test_life_world_bell.py): the closed-form lumen against Euler
integration, no pay for tonic saturation, the lone-cell reference point, and income per cell bounded by the lone rate."""
import itertools

import numpy as np

from src.life import build, spec
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
