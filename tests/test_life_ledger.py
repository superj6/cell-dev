"""Ledger and chemistry-accounting tests (docs/ONE_LIFE_DESIGN.md, TESTS: test_life_ledger.py): F T = income minus
every charge, with the columns rebuilt independently from the logs; morphogen mass is conserved; packets are consumed
in arrival-time order."""
import builtins
from dataclasses import replace

import numpy as np

from src.life import reference as ref
from src.life import spec
from tests.life_helpers import BUSY, conservation_error, grn_genome, kernel, mismatch, r25, reference

L = spec.L
UNIFORM_SEC = spec.pack_program(  # one secretion rate in every row, so secreted mass is checkable by hand
    spec.theta(b=1.125, tau_m=1, t_ref=2.5, w0=-1, emit0=1, delta=2, kappa=1, p_div=0.5, phi=2, p_die=2 ** -5,
               sec0=0.25),
    alone=spec.theta(b=1.875, tau_m=8, t_ref=2, kappa=1, p_div=0.5, sec0=0.25), Dm0=0.05, km0=0.05)

LIVES = [  # (label, world, organism): growth, turnover, forks, guards, panel kills, walls, extinction
    ("busy", spec.world(T=200.0, oracle_cap=60), dict(program=BUSY)),
    ("busy t_open contacts_off", spec.world(T=200.0, oracle_cap=60, t_open=80.0, t_fork=80.0,
                                            fork_flags=spec.flags("contacts_off")), dict(program=BUSY)),
    ("busy guard", spec.world(T=200.0, n_max=40), dict(program=BUSY)),
    ("busy kill panel", spec.world(T=200.0, oracle_cap=60, kill_t=100.0, kill_frac=0.4), dict(program=BUSY)),
    ("busy kill t_open", spec.world(T=200.0, oracle_cap=60, kill_t=100.0, kill_frac=0.4, t_open=99.5),
     dict(program=BUSY)),
    ("busy wall", spec.world(T=200.0, fabric_R=3), dict(program=BUSY)),
    ("uniform secretion", spec.world(T=200.0, oracle_cap=40), dict(program=UNIFORM_SEC)),
    ("grn", spec.world(T=100.0, oracle_cap=30), dict(genome=grn_genome())),
    ("grn panel", spec.world(T=100.0, oracle_cap=30, kill_t=40.0, kill_frac=0.5, noise_rate=0.1), dict(
        genome=grn_genome(5))),
    ("extinction", spec.world(T=100.0), dict(program=spec.pack_program(spec.theta(b=1.875, tau_m=8, t_ref=2,
                                                                                   kappa=1, p_die=2 ** -4)))),
]


def _cell_time(kinds, f, t_from, t_end):
    """Integral of n dt over [t_from, t_end], rebuilt from the birth and death log."""
    born, died = {}, {}
    for (kind, uid, *_), (t, *_r) in zip(kinds.tolist(), f.tolist()):
        if kind == 1:
            born[uid] = t
        elif kind == 2:
            died[uid] = t
    total = 0.0
    for uid, tb in born.items():
        a, b = max(tb, t_from), min(died.get(uid, t_end), t_end)
        total += max(0.0, b - a)
    return total


def _check_ledger(res, i, w):
    led = res.ledger[i]
    t_open = w.t0 + w.t_open
    col = spec.column_cost(led, w)
    assert led[L["net"]] == led[L["income"]] - col - led[L["guard_charge"]]
    assert abs(led[L["F"]] * (w.T - w.t_open) - led[L["net"]]) <= 1e-12 * max(1.0, abs(led[L["net"]]))
    assert spec.fitness(led, w) == led[L["F"]]
    assert abs(led[L["cost"]] - col) <= 1e-9 * max(1.0, col)
    assert not int(led[L["status"]]) & (spec.STATUS["ledger_mismatch"] | spec.STATUS["capacity"])
    kinds, f = res.fates(i)
    assert res.fate_n[i] <= res.fate_i.shape[1] and res.raster_n[i] <= res.raster_t.shape[1]  # complete logs
    counted = f[:, 0] >= t_open
    initial = (kinds[:, 0] == 1) & (kinds[:, 2] == 0)
    assert led[L["births"]] == np.sum((kinds[:, 0] == 1) & ~initial & counted)
    assert led[L["deaths"]] == np.sum((kinds[:, 0] == 2) & (kinds[:, 5] != 3) & counted)
    assert led[L["kills"]] == np.sum((kinds[:, 0] == 2) & (kinds[:, 5] == 3) & counted)
    assert led[L["rejects"]] == np.sum((kinds[:, 0] == 3) & (kinds[:, 5] == 0) & counted)
    assert led[L["rejects_wall"]] == np.sum((kinds[:, 0] == 3) & (kinds[:, 5] == 1) & counted)
    assert led[L["n_end"]] == np.sum(kinds[:, 0] == 1) - np.sum(kinds[:, 0] == 2)
    if w.t_open == 0:  # with a late ledger opening, claims sent before it may resolve after it
        resolved = led[L["births"]] + led[L["rejects"]] + led[L["rejects_wall"]]
        assert resolved <= led[L["claims"]] <= resolved + led[L["n_end"]] + led[L["deaths"]] + led[L["kills"]]
    t, _ = res.spikes(i)
    assert led[L["spikes"]] == np.sum(t >= t_open)
    cell_time = _cell_time(kinds, f, t_open, led[L["t_end"]])
    assert abs(led[L["live_time"]] - cell_time) <= 1e-9 * max(1.0, cell_time), (led[L["live_time"]], cell_time)


def test_f_times_t_is_income_minus_every_charge():
    for label, w, kw in LIVES:
        seeds = [1, 2, 3]
        res = kernel(w, seeds, **kw)
        for i, s in enumerate(seeds):
            try:
                _check_ledger(res, i, w)
            except AssertionError as e:
                raise AssertionError(f"{label} seed {s}: {e}") from e
        if label in ("busy", "busy kill panel", "grn panel", "extinction"):
            assert not mismatch(res, 0, reference(w, 1, **kw)), label
    kill = kernel(LIVES[3][1], [1, 2, 3], **LIVES[3][2])
    assert kill["kills"].sum() > 10 and kernel(LIVES[9][1], [1, 2, 3], **LIVES[9][2]).status("extinct").any()


def test_uniform_secretion_is_charged_and_secreted_consistently():
    w = spec.world(T=200.0, oracle_cap=40)
    res = kernel(w, [1, 2, 3], program=UNIFORM_SEC)
    sec = 0.25
    for i in range(3):
        led = res.ledger[i]
        assert abs(led[L["sec_int"]] - sec * led[L["live_time"]]) <= 1e-9 * led[L["sec_int"]]
        # mass is produced at completed tick intervals: all of the cell time except each cell's open last interval
        gap = led[L["sec_int"]] - led[L["morph_secreted"]]
        assert 0.0 < gap < sec * 3.0 * (led[L["n_end"]] + led[L["deaths"]] + led[L["kills"]])  # interval <= 2.97


def test_morphogen_mass_is_conserved():
    cases = [(w, kw) for _, w, kw in LIVES]
    cases += [(spec.world(T=150.0, oracle_cap=40, t_fork=50.0, fork_flags=spec.flags("chem_off")), dict(program=BUSY)),
              (spec.world(T=150.0, oracle_cap=40, flags=spec.flags("chem_off")), dict(program=BUSY)),
              (spec.world(T=150.0, oracle_cap=40, P0=4.0, clock_sd=0.3), dict(program=BUSY)),
              (spec.world(T=150.0, oracle_cap=40, t0=1024.0), dict(genome=grn_genome())),
              (spec.world(T=100.0, window_h=0.25, n_max=30), dict(genome=grn_genome(3)))]
    terms = np.zeros(5)
    for w, kw in cases:
        res = kernel(w, [1, 2, 3], **kw)
        assert np.all(conservation_error(res.ledger) < 1e-12), w
        cols = ("morph_secreted", "morph_decayed", "morph_lost", "morph_content_end", "morph_inflight_end")
        terms += np.array([res[c].sum() > 0 for c in cols])
    assert np.all(terms >= 3)  # every term of the balance is exercised
    clamp = kernel(spec.world(T=150.0, oracle_cap=40, P0=4.0, clock_sd=0.3), [1, 2, 3], program=BUSY)
    assert clamp.status("chem_clamp").any() and np.all(clamp.status("chem_clamp") == (clamp["chem_clamps"] > 0))
    dry = kernel(spec.world(T=150.0, oracle_cap=40, flags=spec.flags("chem_off")), [1, 2, 3], program=BUSY)
    assert np.all(dry["packets"] == 0) and np.all(dry["morph_lost"] > 0) and np.all(dry["morph_inflight_end"] == 0)


def _inbox_stats(monkeypatch):
    """Instrument the reference's TICK: how many ticks consume two or more packets from one slot."""
    stats = dict(ticks=0, multi=0)
    orig = ref._Life.tick

    def tick(self, c, t):
        due = [p[2] for p in c.inbox if p[0] <= t]
        stats["ticks"] += 1
        stats["multi"] += len(due) > len(set(due))
        return orig(self, c, t)

    monkeypatch.setattr(ref._Life, "tick", tick)
    return stats


def test_packets_are_consumed_in_arrival_time_order(monkeypatch):
    """With spread clocks a cell often finds several packets from one contact at its tick. The kernel matches the
    reference, which consumes them in (t_arr, sender uid) order; consuming the same packets in the reverse order
    changes the life, so the agreement pins the order."""
    w = spec.world(T=150.0, oracle_cap=30, clock_sd=0.4, tick_jit=0.3)
    stats = _inbox_stats(monkeypatch)
    lives = [(BUSY, None, 3), (None, grn_genome(), 13)]
    true = []
    for prog, g, seed in lives:
        kw = dict(program=prog) if prog is not None else dict(genome=g)
        r = reference(w, seed, **kw)
        assert not mismatch(kernel(w, [seed], **kw), 0, r)
        true.append(r)
    assert stats["multi"] > 0.1 * stats["ticks"]

    def sorted_(it, key=None, reverse=False):
        out = builtins.sorted(it, key=key, reverse=reverse)
        if out and isinstance(out[0], tuple) and len(out[0]) == 7 and isinstance(out[0][0], float):
            out.reverse()  # inbox packets (t_arr, sender, slot, amt0, amt1, conc0, conc1): newest first
        return out

    monkeypatch.setattr(ref, "sorted", sorted_, raising=False)
    for (prog, g, seed), r in zip(lives, true):
        kw = dict(program=prog) if prog is not None else dict(genome=g)
        assert reference(w, seed, **kw).hashes.tobytes() != r.hashes.tobytes()


def test_a_slot_only_remembers_the_concentration_of_its_current_contact(monkeypatch):
    """LIFE_ABI.md 15.9: a dead neighbour's last concentration does not persist. After every tick, a slot's stored
    concentration is 0 or comes from the last packet consumed from the contact now in that slot, even when the dead
    neighbour's last packet was still queued when its DIED notice arrived. The kernel agrees bitwise."""
    bad = dict(n=0, slots=0)
    orig = ref._Life.tick
    last = {}

    def tick(self, c, t):
        for p in sorted([p for p in c.inbox if p[0] <= t], key=lambda p: (p[0], p[1])):
            last[(c.uid, p[2])] = p[1]
        orig(self, c, t)
        for d in range(self.D):
            bad["slots"] += 1
            if c.inc[d] != [0.0, 0.0] and (c.view[d] == 0 or last.get((c.uid, d)) != c.view[d]):
                bad["n"] += 1

    monkeypatch.setattr(ref._Life, "tick", tick)
    prog = r25(chem=True, p_die=2 ** -3, sec0=0.3, pol0=1.0, a0=0.5)
    w = spec.world(T=200.0, oracle_cap=40, clock_sd=0.4, tick_jit=0.3)
    refills = 0
    for seed in range(6):
        r = reference(w, seed, program=prog)
        assert not mismatch(kernel(w, [seed], program=prog), 0, r)
        refills += int(np.sum((r.fate_i[:, 0] == 1) & (r.fate_i[:, 5] >= 1)))
    assert refills >= 20 and bad["slots"] > 5000 and bad["n"] == 0, (refills, bad)


def test_chemistry_off_keeps_the_ledger_and_the_spikes_of_a_chemistry_blind_body():
    """Packets carry mass and concentration only: with pol = a = 0 a body's spikes and claims do not depend on them."""
    blind = r25(chem=True, sec0=0.3)
    w = spec.world(T=150.0, oracle_cap=40)
    wet = kernel(w, [1, 2], program=blind)
    dry = kernel(replace(w, flags=spec.flags("chem_off")), [1, 2], program=blind)
    assert np.all(wet["packets"] > 100) and np.all(dry["packets"] == 0)
    assert np.array_equal(wet.hashes[:, 1], dry.hashes[:, 1]) and np.array_equal(wet.hashes[:, 2], dry.hashes[:, 2])
    for c in ("income", "spikes", "claims", "live_time", "sec_int", "cost", "F"):
        assert np.array_equal(wet[c], dry[c]), c
