"""Cell-layer tests (docs/ONE_LIFE_DESIGN.md, TESTS: test_life_cells.py): exact LIF timing, relay delays, the
refractory rule, same-time summation, Q10 rounding only at the cell's own events, and isotropy when a = 0."""
import math
from dataclasses import replace

import numpy as np
import pytest

from src.life import reference as ref
from src.life import spec
from tests.life_helpers import (
    ROW,
    contact_delay,
    kernel,
    mismatch,
    reference,
    same,
    slot_of,
    spike_delay,
    taumis,
    tick_times,
)

K = spec.K
LOCK = spec.flags("lockstep")


def _lone(th):
    return spec.pack_program(th, alone=th)


def _lone_lif(w, seed, th, T):
    """Independent model of a lone cell (LIFE_ABI.md 7.1-7.4): closed-form crossings, v rounded to Q10 only at the
    cell's own events (its ticks and spikes), the tick re-anchor skipped while refractory."""
    b, t_ref = th[K["b"]], th[K["t_ref"]]
    tau = th[K["tau_m"]] * taumis(w, seed, 0, 0)
    ticks = tick_times(w, seed, spec.uid_initial(seed, 0), 0, 0, 0.0, T)
    va, ta, tr = 0.0, 0.0, 0.0
    spikes, i = [], 0

    def crossing():
        t0, v0 = (tr, 0.0) if ta < tr else (ta, va)
        return t0 + tau * math.log((b - v0) / (b - 1.0)) if b > 1.0 and v0 < 1.0 else math.inf

    tc = crossing()
    while True:
        tk = ticks[i] if i < len(ticks) else math.inf
        if min(tc, tk) >= T:
            return np.array(spikes)
        if tc <= tk:  # threshold first: a tick at the same instant is processed after the membrane step
            spikes.append(tc)
            va, ta, tr = 0.0, tc, tc + t_ref
        else:
            i += 1
            if tk >= tr:
                t0, v0 = (tr, 0.0) if ta < tr else (ta, va)
                va, ta = spec.q10(b + (v0 - b) * math.exp(-(tk - t0) / tau)), tk
                if va >= 1.0:
                    spikes.append(tk)
                    va, ta, tr = 0.0, tk, tk + t_ref
        tc = crossing()


@pytest.mark.parametrize("b,tau_m,t_ref", [(1.875, 8, 2), (1.125, 1, 2.5), (2.0, 16, 0.5), (1.5, 2, 4)])
def test_tonic_period_is_exact_between_own_events(b, tau_m, t_ref):
    th = spec.theta(b=b, tau_m=tau_m, t_ref=t_ref, kappa=1)
    w = spec.world(P0=1e7)  # the private clock never ticks in the life: v is anchored only at spikes
    for seed in range(3):
        res = kernel(w, [seed], program=_lone(th))
        assert res["ticks"][0] == 0
        rise = tau_m * taumis(w, seed, 0, 0) * math.log(b / (b - 1.0))
        t, _ = res.spikes(0)
        assert len(t) > 1024 / (rise + t_ref) - 2
        assert abs(t[0] - rise) < 1e-12 and np.all(np.abs(np.diff(t) - (rise + t_ref)) < 1e-12)


@pytest.mark.parametrize("lock", [False, True])
def test_q10_rounding_happens_only_at_the_cells_own_events(lock):
    """With its clock ticking, a lone cell's spike train equals the independent model bitwise: v is rounded at its
    ticks and nowhere else, and intervals with no tick in their rising phase are the exact LIF period."""
    w = spec.world(flags=LOCK if lock else 0)
    exact = rounded = 0
    for th in (spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1), spec.theta(b=2.0, tau_m=1, t_ref=4, kappa=1),
               spec.theta(b=1.5, tau_m=1, t_ref=3, kappa=1)):
        for seed in range(3):
            t, _ = kernel(w, [seed], program=_lone(th)).spikes(0)
            r = reference(w, seed, program=_lone(th))
            model = _lone_lif(w, seed, th, w.T)
            assert np.array_equal(t, model) and np.array_equal(r.raster_t, model)
            b, t_ref = th[K["b"]], th[K["t_ref"]]
            period = th[K["tau_m"]] * taumis(w, seed, 0, 0) * math.log(b / (b - 1.0)) + t_ref
            ticks = np.array(tick_times(w, seed, spec.uid_initial(seed, 0), 0, 0, 0.0, w.T))
            for t1, t2 in zip(t[:-1], t[1:]):
                quiet = not np.any((ticks >= t1 + t_ref) & (ticks <= t2))  # a tick re-anchor may fire (ABI 15.6)
                if quiet:
                    assert abs(t2 - t1 - period) < 1e-12
                    exact += 1
                elif abs(t2 - t1 - period) > 1e-9:
                    rounded += 1
    assert exact > 100 and rounded > 100


def test_a_cell_is_untouched_by_events_elsewhere():
    """A lone pump keeps its spike train bitwise while a growing body lives far away on the same fabric."""
    prog = spec.pack_program(spec.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1, p_div=0.5,
                                        phi=2, p_die=2 ** -6, sec0=0.3, pol0=1.0),
                             alone=spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1, p_div=0.5),
                             rim=spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1), Dm0=0.05, km0=0.05)
    w = spec.world(T=150.0, oracle_cap=300)
    solo = kernel(w, [9], program=prog, init=[(0, 0, ROW["rim"])])
    both = kernel(w, [9], program=prog, init=[(0, 0, ROW["rim"]), (40, 0, -1)], cap=1 << 18)
    assert both["births"][0] > 200 and both["spikes"][0] > 5 * solo["spikes"][0] and both["status"][0] == 0
    t1, u1 = solo.spikes(0)
    t2, u2 = both.spikes(0)
    assert np.array_equal(t1, t2[u2 == u1[0]])


@pytest.mark.parametrize("lock", [False, True])
def test_relay_arrival_times_equal_the_summed_delays(lock):
    """A -> B -> C on a line: B and C fire at arrival, so their spikes sit exactly at the summed contact delays."""
    src = spec.theta(b=1.5, tau_m=2, t_ref=3, emit0=1, delta=0.0)
    relay = spec.theta(b=0.0, tau_m=1, t_ref=0.5, w0=2.0, emit0=1, delta=0.5)
    sink = spec.theta(b=0.0, tau_m=1, t_ref=0.5, w0=2.0)
    prog = spec.pack_program(relay, zygote=src, rim=sink)
    A, B, C = (0, 0), (1, 0), (2, 0)
    init = [(*A, ROW["zygote"]), (*B, ROW["contact"]), (*C, ROW["rim"])]
    w = spec.world(T=300.0, flags=LOCK if lock else 0)
    for seed in (1, 2, 3):
        res = kernel(w, [seed], program=prog, init=init)
        assert not mismatch(res, 0, reference(w, seed, program=prog, init=init))
        t, u = res.spikes(0)
        ua, ub, uc = (spec.uid_initial(seed, j) for j in range(3))
        ta, tb, tc = t[u == ua], t[u == ub], t[u == uc]
        dab, dbc = contact_delay(w, seed, A, B), contact_delay(w, seed, B, C)
        sab, sbc = slot_of("hex", A, B), slot_of("hex", B, C)
        exp_b = np.array([x + spike_delay(w, seed, ua, j + 1, sab, dab, 0.0) for j, x in enumerate(ta)])
        exp_c = np.array([x + spike_delay(w, seed, ub, j + 1, sbc, dbc, 0.5) for j, x in enumerate(tb)])
        assert len(ta) > 40 and np.array_equal(tb, exp_b[exp_b < w.T]) and np.array_equal(tc, exp_c[exp_c < w.T])
        if lock:
            assert np.allclose(tc - ta[:len(tc)], 2.5, rtol=0.0, atol=1e-12)  # d0 + (d0 + delta)


def test_input_during_refractory_is_lost():
    """A detector with a long refractory period fires at an arrival iff it is not refractory; input that lands while it
    is refractory leaves no trace on v (it never fires when the refractory period ends)."""
    src = spec.theta(b=2.0, tau_m=1, t_ref=0.5, emit0=1)
    det = spec.theta(b=0.0, tau_m=1, t_ref=4.0, w0=2.0)
    prog = spec.pack_program(det, zygote=src)
    A, B = (0, 0), (1, 0)
    init = [(*A, ROW["zygote"]), (*B, ROW["contact"])]
    w = spec.world(T=200.0)
    lost = 0
    for seed in (4, 5):
        res = kernel(w, [seed], program=prog, init=init)
        assert not mismatch(res, 0, reference(w, seed, program=prog, init=init))
        t, u = res.spikes(0)
        ua, ub = spec.uid_initial(seed, 0), spec.uid_initial(seed, 1)
        d = contact_delay(w, seed, A, B)
        arr = [x + spike_delay(w, seed, ua, j + 1, slot_of("hex", A, B), d, 0.0) for j, x in enumerate(t[u == ua])
               if x >= 0.5]  # A knows B from B's BORN notice at d_min
        fired, t_r = [], 0.0
        for x in sorted(arr):
            if x >= w.T:
                break
            if x >= t_r:
                fired.append(x)
                t_r = x + 4.0
            else:
                lost += 1
        assert np.array_equal(t[u == ub], fired)
    assert lost > 100


def _trace_genome() -> np.ndarray:
    """Gene 0 is driven by the received-spike trace r0 and sets the secretion rate, which the ledger integrates."""
    g = np.zeros(spec.GENOME_SIZE, dtype=np.float32)
    spec.genome_view(g, "act")[0] = 1.0
    spec.genome_view(g, "W")[0, 19] = 4.0
    spec.genome_view(g, "b")[0] = -2.0
    spec.genome_view(g, "lam")[0] = -3.0  # lambda = 1/2
    spec.genome_view(g, "s0")[0] = -2.0
    spec.genome_view(g, "A")[K["sec0"], 0] = 3.0
    a0 = spec.genome_view(g, "a0")
    for knob, y in (("b", 2.0), ("tau_m", -2.0), ("t_ref", 2.0), ("emit0", 1.0), ("kappa", -1.0), ("sec0", -1.0)):
        a0[K[knob]] = y
    return g


def test_arrivals_during_refractory_still_count_in_the_traces(monkeypatch):
    """Two tonic cells with a 4-unit refractory period ignore each other's spikes (w = 0), but their received-spike
    traces drive a gene that sets secretion. The kernel equals the reference, which counts every delivered arrival in
    the traces; a variant that skips refractory arrivals in the traces integrates a different secretion."""
    g = _trace_genome()
    gt = spec.pack_genomes(g)[0]
    th = spec.phenotype(gt, spec.genome_view(gt, "s0"))  # the zygote's phenotype, from g0 = sigma(s0)
    assert th[K["t_ref"]] == 4.0 and th[K["b"]] == 2.0 and th[K["emit0"]] == 1.0 and th[K["w0"]] == 0.0
    w = spec.world(T=200.0)
    init = [(0, 0), (1, 0)]
    counts = dict(refractory=0)
    orig = ref._Life.membrane

    def counting(self, c, t, arr, kicks, thr):
        counts["refractory"] += len(arr) if t < c.t_r else 0
        return orig(self, c, t, arr, kicks, thr)

    monkeypatch.setattr(ref._Life, "membrane", counting)
    true = reference(w, 3, genome=g, init=init)
    assert counts["refractory"] > 0.6 * true["arrivals"] > 40
    assert not mismatch(kernel(w, [3], genome=g, init=init), 0, true)

    def untraced(self, c, t, arr, kicks, thr):
        if t < c.t_r:
            return None
        return orig(self, c, t, arr, kicks, thr)

    monkeypatch.setattr(ref._Life, "membrane", untraced)
    variant = reference(w, 3, genome=g, init=init)
    assert variant["spikes"] == true["spikes"] and variant["sec_int"] != true["sec_int"]


@pytest.mark.parametrize("w_exc,w_inh", [(1.0, -1.0), (1.0, -0.5), (1.5, -0.75)])
def test_same_time_excitation_and_inhibition_sum_in_either_order(w_exc, w_inh):
    """In lockstep two identical tonic senders fire at the same instants; a receiver gets channel 0 from one and
    channel 1 from the other at the same time. One summed input and one threshold test: it never fires (a sequential
    excitation-first update would fire every time), whatever the tie order, salt or window."""
    e = spec.theta(b=1.5, tau_m=2, t_ref=1, emit0=1)
    i = spec.theta(b=1.5, tau_m=2, t_ref=1, emit1=1)
    rx = spec.theta(b=0.0, tau_m=1, t_ref=0.5, w0=w_exc, w1=w_inh)
    prog = spec.pack_program(rx, alone=e, juvenile=i)
    init = [(0, 0, ROW["contact"]), (1, 0, ROW["alone"]), (0, 1, ROW["juvenile"])]
    w = spec.world(T=150.0, flags=LOCK)
    base = kernel(w, [3], program=prog, init=init)
    t, u = base.spikes(0)
    assert np.array_equal(t[u == spec.uid_initial(3, 1)], t[u == spec.uid_initial(3, 2)])
    assert base["arrivals"][0] > 50 and not np.any(u == spec.uid_initial(3, 0))
    for tie in range(1, 6):
        assert same(base, kernel(w, [[3, tie, 0, tie * 31]], program=prog, init=init))
    for h in (0.5, 0.125):
        assert same(base, kernel(replace(w, window_h=h), [[3, 0, int(h * 8), 0]], program=prog, init=init))
    assert not mismatch(base, 0, reference(w, 3, program=prog, init=init, salt=7))


def test_zero_directional_gain_gives_isotropic_weights_bitwise():
    """With a = 0 the receiver weights ignore the morphogen field (w_eff = q8(w (1 + 0 shat)) = w): a body with
    polarity and chemistry spikes bitwise like the same body without polarity; a = 1/2 changes the spikes."""
    def body(pol: float, a: float):
        contact = spec.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=1, kappa=1, sec0=0.3, sec1=0.1,
                             pol0=pol, pol1=-pol, a0=a)
        return spec.pack_program(contact, alone=contact, Dm0=0.05, Dm1=0.03, km0=0.05, km1=0.1)

    hexes = [(0, 0), (1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1), (2, 0), (2, -1), (-2, 1)]
    w = spec.world(T=200.0, flags=spec.flags("division_off"))
    seeds = [1, 2, 3]
    iso = kernel(w, seeds, program=body(1.0, 0.0), init=hexes)
    assert np.all(iso["packets"] > 100) and np.all(iso["spikes"] > 100)
    assert same(iso, kernel(w, seeds, program=body(0.0, 0.0), init=hexes))
    assert same(iso, kernel(w, seeds, program=body(-1.5, 0.0), init=hexes))
    aniso = kernel(w, seeds, program=body(1.0, 0.5), init=hexes)
    assert not np.any(aniso.hashes[:, 1] == iso.hashes[:, 1])
    assert not mismatch(aniso, 0, reference(w, 1, program=body(1.0, 0.5), init=hexes))
